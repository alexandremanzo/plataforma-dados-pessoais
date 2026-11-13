"""
Carga da camada Bronze - conta familia.

Le a aba publicada do Google Sheets e grava em
bronze.familia_movimentacao. Foi a primeira origem do projeto que nao
le arquivo: o dado vem pela rede, da mesma URL que o Power BI consome.
A segunda e o diario em carga_bronze_dia.py.

A conversao de formato acontece aqui, e nao na silver, porque o CSV
entrega tudo como texto no padrao brasileiro - "1.234,56", negativo
entre parenteses, data como 17/04/2021. Deixar isso para depois faria
a bronze guardar strings que nem o proprio banco consegue ordenar.

Carga com upsert: classificar um lancamento na planilha nao muda a
chave de negocio, entao sem atualizar o trabalho de classificar
ficaria preso no Google.

Uso:
    python carga_bronze_familia.py
"""

import argparse
import time
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PLANILHA_FAMILIA_URL, get_engine  # noqa: E402
from google_sheets import (  # noqa: E402
    PlanilhaIndisponivel, data_brasileira, le_planilha_publicada, numero_brasileiro,
)
from regras_xp import normaliza  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

SCHEMA, TABELA = "bronze", "familia_movimentacao"
ORIGEM = "Google Sheets - conta familia, aba Movimentacao"

COLUNAS = {
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
    "Descrição Status Pgto": "ds_descricao_status_pgto",
    "Cidade": "ds_cidade",
    "UF": "ds_uf",
    "País": "ds_pais",
    "OBS": "ds_obs",
    "Pgto Mes": "ds_pgto_mes",
    "Pgto Ano": "ds_pgto_ano",
}
DESTINO = list(COLUNAS.values())
DATAS = ["ds_data", "ds_data_pgto"]
NUMEROS = ["ds_valor", "ds_valor_tratado"]

# Colunas que a planilha pode alterar sem que o evento vire outro.
CHAVE_HASH = ["ds_data", "ds_descricao", "ds_valor"]
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]


def prepara(df: pd.DataFrame) -> pd.DataFrame:
    faltando = [o for o in COLUNAS if o not in df.columns]
    if faltando:
        raise PlanilhaIndisponivel(
            f"A aba publicada nao tem as colunas esperadas: {faltando}.\n"
            "  Se voce renomeou ou reordenou colunas na planilha, ajuste o "
            "dicionario COLUNAS deste script.")

    df = df.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    for col in DATAS:
        df[col] = df[col].map(data_brasileira)
    for col in NUMEROS:
        df[col] = df[col].map(
            lambda v: "" if numero_brasileiro(v) is None else f"{numero_brasileiro(v):.2f}")
    for col in DESTINO:
        if col not in DATAS + NUMEROS:
            df[col] = df[col].map(
                lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
                else str(v).strip()
            )

    # Cauda de formula arrastada: sem data e sem valor. Sao cerca de um
    # terco das linhas do CSV.
    vazias = (df["ds_data"] == "") & (df["ds_valor"] == "")
    descartadas = int(vazias.sum())
    df = df[~vazias].copy()

    chave = (df["ds_data"] + "|"
             + df["ds_descricao"].fillna("").map(normaliza) + "|"
             + df["ds_valor"])
    df["nr_ocorrencia"] = chave.groupby(chave).cumcount() + 1
    df["hash_negocio"] = [
        hashlib.sha256(f"{k}|{n}".encode("utf-8")).hexdigest()
        for k, n in zip(chave, df["nr_ocorrencia"])
    ]

    df["nm_origem"] = ORIGEM
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    """Insere os eventos novos e atualiza os que mudaram na planilha."""
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
    argparse.ArgumentParser(description="Carga bronze da conta familia").parse_args()

    if not PLANILHA_FAMILIA_URL:
        print("ERRO: PLANILHA_FAMILIA_URL nao definida no .env")
        return 1

    try:
        bruto = le_planilha_publicada(PLANILHA_FAMILIA_URL)
    except PlanilhaIndisponivel as erro:
        print(f"ERRO ao ler a planilha:\n  {erro}")
        return 1

    engine = get_engine()
    novos, alterados, existiam, descartadas = sincroniza(prepara(bruto), engine)

    print("== Google Sheets / aba Movimentacao ==")
    print(f"  {len(bruto)} linhas no CSV")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} linhas vazias descartadas")
    registra_carga(engine, "bronze.familia_movimentacao", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.familia_movimentacao"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT COUNT(*) AS eventos,
                   SUM(CASE WHEN ds_categoria IS NULL THEN 1 ELSE 0 END) AS sem_categoria,
                   MIN(ds_data) AS primeiro, MAX(ds_data) AS ultimo,
                   CAST(SUM(TRY_CAST(ds_valor_tratado AS decimal(18,2)))
                        AS decimal(18,2)) AS total
            FROM {SCHEMA}.{TABELA}
        """, conn).to_string(index=False))

        print("\n== Quem pagou ==")
        print(pd.read_sql(f"""
            SELECT ds_pessoa_pagar AS pessoa, COUNT(*) AS lancamentos,
                   CAST(SUM(TRY_CAST(ds_valor_tratado AS decimal(18,2)))
                        AS decimal(18,2)) AS total
            FROM {SCHEMA}.{TABELA}
            GROUP BY ds_pessoa_pagar ORDER BY 2 DESC
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
