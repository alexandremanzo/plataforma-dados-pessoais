"""
Carga da camada Bronze - cartao de credito Nubank.

Le a aba cad-credito de dados-nunbank-completo.xlsx e grava em
bronze.cartao_nubank. Cartao encerrado, usado de 2018 a 2022.

Ao final, semeia silver.de_para_categoria_nubank com as categorias
encontradas, deixando as colunas de mapeamento em branco para
preenchimento manual. Sao 12 linhas que cobrem 2.135 lancamentos.

Uso:
    python carga_bronze_cartao_nubank.py
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
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

ARQUIVO = "dados-nunbank-completo.xlsx"
ABA = "cad-credito"
SCHEMA, TABELA = "bronze", "cartao_nubank"

COLUNAS = {
    "date": "ds_data",
    "title": "ds_titulo",
    "category": "ds_categoria_nubank",
    "Valor": "ds_valor",
    "Data Pagamento": "ds_data_fatura",
    "Tipo Movimentação": "ds_tipo_movimentacao",
    "Extrato": "fl_extrato",
    "Rewards": "fl_rewards",
    "Arquivo": "ds_arquivo_fatura",
    "Área": "ds_area",
    "Categoria": "ds_categoria",
    "Grupo": "ds_grupo",
    "Pessoa Pagar": "ds_pessoa_pagar",
    "Pessoa Receber": "ds_pessoa_receber",
    "Cidade": "ds_cidade",
    "UF": "ds_uf",
    "País": "ds_pais",
    "OBS": "ds_obs",
    "Projeto": "ds_projeto",
    "Tag": "ds_tag",
}
DESTINO = list(COLUNAS.values())

# Colunas que a origem pode alterar sem que o evento vire outro.
# As que compoem o hash ficam de fora: mudar uma delas significa que
# e um lancamento diferente, nao o mesmo corrigido.
CHAVE_HASH = ['ds_data', 'ds_titulo', 'ds_valor', 'ds_data_fatura']
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]
DATAS = ["ds_data", "ds_data_fatura"]
NUMEROS = ["ds_valor"]


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

    vazias = (df["ds_data"] == "") & (df["ds_valor"] == "")
    descartadas = int(vazias.sum())
    df = df[~vazias].copy()

    chave = (df["ds_data"] + "|"
             + df["ds_titulo"].fillna("").map(normaliza) + "|"
             + df["ds_valor"] + "|"
             + df["ds_data_fatura"])
    df["nr_ocorrencia"] = chave.groupby(chave).cumcount() + 1
    df["hash_negocio"] = [
        hashlib.sha256(f"{k}|{n}".encode("utf-8")).hexdigest()
        for k, n in zip(chave, df["nr_ocorrencia"])
    ]

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

    Vale especialmente para esta origem: o cartao Nubank tem apenas
    2,1% de classificacao manual, entao qualquer revisao futura da
    planilha depende deste passo para surtir efeito.
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


def semeia_de_para(engine) -> None:
    """
    Cria uma linha por categoria do Nubank, sem preencher o mapeamento.

    Preserva o que ja foi mapeado a mao: so acrescenta categorias novas
    e atualiza a contagem, que serve para priorizar a revisao.
    """
    with engine.begin() as conn:
        categorias = pd.read_sql(f"""
            SELECT ds_categoria_nubank, COUNT(*) AS nr_lancamentos
            FROM {SCHEMA}.{TABELA}
            WHERE ds_categoria_nubank IS NOT NULL
            GROUP BY ds_categoria_nubank
        """, conn)

        existentes = set(pd.read_sql(
            "SELECT ds_categoria_nubank FROM silver.de_para_categoria_nubank",
            conn)["ds_categoria_nubank"])

        novas = categorias[~categorias["ds_categoria_nubank"].isin(existentes)]
        if len(novas):
            novas.to_sql("de_para_categoria_nubank", conn, schema="silver",
                         if_exists="append", index=False)

        conn.execute(text("""
            UPDATE d SET d.nr_lancamentos = c.n
            FROM silver.de_para_categoria_nubank d
            JOIN (SELECT ds_categoria_nubank, COUNT(*) AS n
                    FROM bronze.cartao_nubank
                   WHERE ds_categoria_nubank IS NOT NULL
                   GROUP BY ds_categoria_nubank) c
              ON c.ds_categoria_nubank = d.ds_categoria_nubank
        """))
    print(f"  de-para de categorias: +{len(novas)} novas")


def main() -> int:
    argparse.ArgumentParser(description="Carga bronze do cartao Nubank").parse_args()

    caminho = PATH_DADOS_ORIGEM / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: {caminho} nao encontrado")
        return 1

    engine = get_engine()
    df = pd.read_excel(caminho, sheet_name=ABA).rename(columns=COLUNAS)
    novos, alterados, existiam, descartadas = sincroniza(prepara(df, caminho), engine)

    print(f"== {ARQUIVO} / aba {ABA} ==")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} vazias descartadas")
    registra_carga(engine, "bronze.cartao_nubank", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.cartao_nubank"):
        return SAIDA_SEM_DADOS
    semeia_de_para(engine)

    print("\n== Conferencia: gastos x pagamentos de fatura ==")
    print(pd.read_sql(f"""
        SELECT CASE WHEN fl_extrato = 'N' THEN 'Pagamento de fatura (SINTETICO)'
                    ELSE 'Consumo (ANALITICO)' END AS tipo,
               COUNT(*) AS lancamentos,
               CAST(SUM(TRY_CAST(ds_valor AS decimal(18,2))) AS decimal(18,2)) AS total_origem
        FROM {SCHEMA}.{TABELA} GROUP BY fl_extrato ORDER BY 2 DESC
    """, engine).to_string(index=False))

    print("\n== Categorias a mapear (ordenadas por volume) ==")
    print(pd.read_sql("""
        SELECT ds_categoria_nubank AS categoria_nubank, nr_lancamentos,
               ISNULL(ds_categoria, '(a mapear)') AS seu_vocabulario
        FROM silver.de_para_categoria_nubank ORDER BY nr_lancamentos DESC
    """, engine).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
