"""
Carga da camada Bronze - conta corrente Itau.

Origem unica: a aba "cad-conta" de dados-itau.xlsx.

POR QUE SO ESSA ABA. O arquivo tem tambem uma aba de extrato bruto
baixada do banco, mas ela e area de trabalho: voce cola o extrato la e
depois transfere para a cad-conta, classificando. Ler as duas fazia
lancamentos entrarem pelo caminho curto, sem classificacao e sem
passar pela sua revisao. A cad-conta e a fonte da verdade.

A CARGA ATUALIZA, NAO SO INSERE. Este e o ponto que faz a planilha
continuar sendo util: a classificacao nao faz parte da chave de
negocio, entao classificar um lancamento existente nao muda o hash.
Uma carga que so inserisse nunca traria essa mudanca para o banco - o
trabalho de classificar ficaria preso na planilha. Por isso, alem de
inserir o que e novo, a carga compara as colunas de conteudo e
atualiza o que mudou na origem.

Idempotente: rodar N vezes produz o mesmo resultado que rodar uma vez.

Uso:
    python carga_bronze_itau.py
"""

import argparse
import time
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402
from regras_xp import normaliza  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, normaliza_id, registra_carga,
    sem_dados, valida_id_origem,
)

_INICIO = time.monotonic()

ARQUIVO = "dados-itau.xlsx"
ABA = "cad-conta"
SCHEMA, TABELA = "bronze", "itau_movimentacao"

COLUNAS = {
    "ID": "ds_id_origem",
    "Data": "ds_data",
    "Descrição": "ds_descricao",
    "Valor": "ds_valor",
    "Valor Trat": "ds_valor_tratado",
    "Tipo Movimentação": "ds_tipo_movimentacao",
    "Área": "ds_area",
    "Categoria": "ds_categoria",
    "Grupo": "ds_grupo",
    "Pessoa Pagar": "ds_pessoa_pagar",
    "Pessoa Receber": "ds_pessoa_receber",
    "Forma Pgto": "ds_forma_pgto",
    "Descrição Pagto": "ds_descricao_pgto",
    "Data Pgto": "ds_data_pgto",
    "Status Pgto": "ds_status_pgto",
    "Cidade": "ds_cidade",
    "UF": "ds_uf",
    "País": "ds_pais",
    "OBS": "ds_obs",
    "Projeto": "ds_projeto",
    "Tag": "ds_tag",
}
DESTINO = list(COLUNAS.values())
DATAS = ["ds_data", "ds_data_pgto"]
NUMEROS = ["ds_valor", "ds_valor_tratado"]

# A chave e o ID da planilha, e so ele. TODO O RESTO e atualizavel -
# inclusive data, descricao e valor, que antes compunham o hash.
#
# Esta base e digitada a mao, e lancar na pressa e completar depois e o
# uso normal. Enquanto aqueles tres campos eram a identidade, corrigir
# qualquer um deles criava um registro novo e deixava o antigo orfao,
# inflando os totais em silencio. Justamente o que mais precisa de
# correcao era o que nao podia ser corrigido.
CHAVE_HASH = ["ds_id_origem"]
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]


def _data_iso(valor) -> str:
    dt = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _numero(valor) -> str:
    num = pd.to_numeric(valor, errors="coerce")
    return "" if pd.isna(num) else f"{num:.2f}"


def le_planilha(caminho: Path) -> pd.DataFrame:
    """Le a aba cad-conta e prepara as colunas da bronze."""
    df = pd.read_excel(caminho, sheet_name=ABA).rename(columns=COLUNAS)

    for destino in DESTINO:
        if destino not in df.columns:
            df[destino] = None
    df = df[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    for col in DATAS:
        df[col] = df[col].map(_data_iso)
    for col in NUMEROS:
        df[col] = df[col].map(_numero)
    for col in DESTINO:
        if col not in DATAS + NUMEROS:
            df[col] = df[col].map(
                lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
                else str(v).strip()
            )

    # Linhas de formula arrastada: sem data, sem descricao e sem valor.
    vazias = (df["ds_data"] == "") & df["ds_descricao"].isna() & (df["ds_valor"] == "")
    descartadas = int(vazias.sum())
    df = df[~vazias].copy()

    # Normaliza ANTES de validar e de hashear: a coluna do Itau tem
    # cauda vazia, o que faz o pandas ler o ID como float, e "1.0" e
    # "1" dariam hashes diferentes para o mesmo lancamento.
    df["ds_id_origem"] = df["ds_id_origem"].map(normaliza_id)
    valida_id_origem(df["ds_id_origem"], "ID", "conta Itau")
    df["hash_negocio"] = [
        hashlib.sha256(f"itau|{i}".encode("utf-8")).hexdigest()
        for i in df["ds_id_origem"]
    ]

    # Numero da ocorrencia dentro do dia. NAO E MAIS PARTE DA CHAVE -
    # o ID da planilha resolve a identidade sozinho. Continua calculado
    # porque ainda informa "este e o enesimo lancamento identico do
    # dia", o que ajuda a achar digitacao repetida.
    chave = (df["ds_data"] + "|"
             + df["ds_descricao"].fillna("").map(normaliza) + "|"
             + df["ds_valor"])
    df["nr_ocorrencia"] = chave.groupby(chave).cumcount() + 1

    df["nm_arquivo_origem"] = caminho.name
    df["nm_aba_origem"] = ABA
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    """
    Insere os eventos novos e atualiza os que mudaram na planilha.

    A atualizacao existe por causa da classificacao: ela nao entra no
    hash, entao um lancamento classificado depois continua com o mesmo
    identificador. Sem este passo, o trabalho de classificar ficaria
    preso na planilha e nunca chegaria ao banco.
    """
    descartadas = int(df["_descartadas"].iloc[0]) if len(df) else 0
    df = df.drop(columns="_descartadas")

    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(ATUALIZAVEIS)} "
            f"FROM {SCHEMA}.{TABELA}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(TABELA, conn, schema=SCHEMA, if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", ATUALIZAVEIS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in ATUALIZAVEIS)
            conn.execute(
                text(f"UPDATE {SCHEMA}.{TABELA} SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :chave"),
                alterados,
            )

    return len(novos), len(alterados), len(df) - len(novos), descartadas


def main() -> int:
    argparse.ArgumentParser(description="Carga bronze da conta Itau").parse_args()

    caminho = PATH_DADOS_ORIGEM / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: {caminho} nao encontrado")
        return 1

    engine = get_engine()
    try:
        preparado = le_planilha(caminho)
    except ValueError as erro:
        print(f"ERRO na coluna de identidade:\n  {erro}")
        return 1
    novos, alterados, existiam, descartadas = sincroniza(preparado, engine)

    print(f"== {ARQUIVO} / aba {ABA} ==")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} linhas vazias descartadas")
    registra_carga(engine, "bronze.itau_movimentacao", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.itau_movimentacao"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        resumo = pd.read_sql(f"""
            SELECT COUNT(*) AS eventos,
                   SUM(CASE WHEN ds_categoria IS NULL THEN 1 ELSE 0 END) AS sem_categoria,
                   MIN(ds_data) AS primeiro, MAX(ds_data) AS ultimo
            FROM {SCHEMA}.{TABELA}
        """, conn)
    print()
    print(resumo.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
