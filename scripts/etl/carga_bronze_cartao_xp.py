"""
Carga da camada Bronze - cartao de credito XP.

Le a aba MOVTO de dados-xp-credito.xlsx e grava em bronze.cartao_xp.

Origem unica: nao ha extrato incremental separado como no Itau ou no
XP investimentos. A planilha e alimentada a mao a partir da fatura, e
esta carga apenas a espelha, deduplicando por hash.

ATENCAO A DUAS ARMADILHAS DESTA ORIGEM:

1. A metrica e "Valor Trat", nao "Valor". O sinal de "Valor" e
   inconsistente nos estornos - ha casos gravados como positivo e
   como negativo para o mesmo tipo de evento. "Valor Trat" e a unica
   coluna com convencao estavel.

2. "Data Pgto" e a data da FATURA, nao da compra. Uma compra
   parcelada aparece em varias faturas, inclusive futuras: 11 dos 61
   vencimentos ainda nao ocorreram.

Uso:
    python carga_bronze_cartao_xp.py
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

ARQUIVO = "dados-xp-credito.xlsx"
ABA = "MOVTO"
SCHEMA, TABELA = "bronze", "cartao_xp"

COLUNAS = {
    "ID": "ds_id_origem",
    "Data": "ds_data",
    "Descrição": "ds_descricao",
    "Parcela": "ds_parcela",
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
    "Descrição Status Pgto": "ds_descricao_status_pgto",
    "Cidade": "ds_cidade",
    "UF": "ds_uf",
    "País": "ds_pais",
    "OBS": "ds_obs",
}
DESTINO = list(COLUNAS.values())

# A chave e o ID da planilha, e so ele. TODO O RESTO e atualizavel -
# inclusive a DATA DA FATURA, que antes compunha o hash.
#
# Era o defeito mais caro desta base. Um gasto lancado como sendo da
# fatura do mes X e depois corrigido para o mes Y - o que se descobre
# justamente ao conferir o valor pago contra a soma dos itens - virava
# um lancamento NOVO em vez de mover o existente. O antigo seguia
# somando no mes errado, e a conferencia nunca fechava.
CHAVE_HASH = ['ds_id_origem']
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]
DATAS = ["ds_data", "ds_data_pgto"]
NUMEROS = ["ds_valor", "ds_valor_tratado"]


def _data_iso(valor) -> str:
    dt = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _numero(valor) -> str:
    num = pd.to_numeric(valor, errors="coerce")
    return "" if pd.isna(num) else f"{num:.2f}"


def prepara(df: pd.DataFrame, caminho: Path) -> pd.DataFrame:
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

    vazias = (df["ds_data"] == "") & (df["ds_valor_tratado"] == "")
    descartadas = int(vazias.sum())
    df = df[~vazias].copy()

    # Normaliza ANTES de validar e de hashear. Aqui a coluna hoje vem
    # como int, mas basta acrescentar uma linha em branco na planilha
    # para o pandas passar a ler float e todos os hashes mudarem.
    df["ds_id_origem"] = df["ds_id_origem"].map(normaliza_id)
    valida_id_origem(df["ds_id_origem"], "ID", "cartao XP")
    df["hash_negocio"] = [
        hashlib.sha256(f"cartao-xp|{i}".encode("utf-8")).hexdigest()
        for i in df["ds_id_origem"]
    ]

    # Numero da ocorrencia. NAO E MAIS PARTE DA CHAVE - o ID da planilha
    # resolve a identidade sozinho, e e por isso que a fatura agora pode
    # ser corrigida. Continua calculado porque ainda informa "este e o
    # enesimo lancamento identico", util para achar digitacao repetida.
    chave = (df["ds_data"] + "|"
             + df["ds_descricao"].fillna("").map(normaliza) + "|"
             + df["ds_valor_tratado"] + "|"
             + df["ds_data_pgto"])
    df["nr_ocorrencia"] = chave.groupby(chave).cumcount() + 1

    df["nm_arquivo_origem"] = caminho.name
    df["nm_aba_origem"] = ABA
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    """
    Insere os eventos novos e atualiza os que mudaram na planilha.

    A atualizacao existe por causa da classificacao: ela nao entra no
    hash, entao classificar um lancamento ja existente nao muda o
    identificador do evento. Uma carga que so inserisse deixaria esse
    trabalho preso na planilha, sem nunca chegar ao banco.

    Diferente do XP investimentos, aqui nao ha ressalva: o cartao tem
    origem unica, entao nao existe risco de uma origem sem
    classificacao sobrescrever com nulo o que outra ja classificou.
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
    argparse.ArgumentParser(description="Carga bronze do cartao XP").parse_args()

    caminho = PATH_DADOS_ORIGEM / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: {caminho} nao encontrado")
        return 1

    engine = get_engine()
    df = pd.read_excel(caminho, sheet_name=ABA).rename(columns=COLUNAS)
    try:
        preparado = prepara(df, caminho)
    except ValueError as erro:
        print(f"ERRO na coluna de identidade:\n  {erro}")
        return 1
    novos, alterados, existiam, descartadas = sincroniza(preparado, engine)

    print(f"== {ARQUIVO} / aba {ABA} ==")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} vazias descartadas")
    registra_carga(engine, "bronze.cartao_xp", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.cartao_xp"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        resumo = pd.read_sql(f"""
            SELECT COUNT(*) AS eventos,
                   COUNT(DISTINCT ds_data_pgto) AS faturas,
                   MIN(ds_data) AS primeira_compra, MAX(ds_data) AS ultima_compra,
                   CAST(SUM(TRY_CAST(ds_valor_tratado AS decimal(18,2)))
                        AS decimal(18,2)) AS total
            FROM {SCHEMA}.{TABELA}
        """, conn)
    print()
    print(resumo.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
