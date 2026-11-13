"""
Carga da camada Bronze - meu dia.

Le a aba de respostas do formulario publicada como CSV e grava em
bronze.dia_registro. Segunda origem do projeto que nao le arquivo.

A CHAVE E O CARIMBO DO FORMULARIO, nao a data relatada. O carimbo e
atribuido pelo Google no envio, e unico e nunca muda; a data e digitada
a mao e ja veio errada duas vezes. Se a chave fosse a data, corrigir o
erro na planilha criaria uma linha nova e deixaria a errada orfa - com
o carimbo, a correcao chega como atualizacao.

Uso:
    python carga_bronze_dia.py
"""

import argparse
import time
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PLANILHA_DIA_URL, get_engine  # noqa: E402
from google_sheets import (  # noqa: E402
    PlanilhaIndisponivel, data_brasileira, le_planilha_publicada,
)
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

SCHEMA, TABELA = "bronze", "dia_registro"
ORIGEM = "Google Sheets - meu dia, respostas do formulario"

COLUNAS = {
    "Carimbo de data/hora": "ds_carimbo",
    "Data": "ds_data",
    "Treino": "ds_treino",
    "Cardio": "ds_cardio",
    "Consumo de água (Litros)": "ds_agua_litros",
    "Café da Manhã": "ds_cafe_manha",
    "Almoço": "ds_almoco",
    "Lanche": "ds_lanche",
    "Janta": "ds_janta",
    "Ceia": "ds_ceia",
    "Dia Produtivo": "ds_dia_produtivo",
    "Trabalho": "ds_trabalho",
    "Nina em casa": "ds_nina_em_casa",
    "Estresse": "ds_estresse",
    "Lazer": "ds_lazer",
}
DESTINO = list(COLUNAS.values())

# Tudo menos o carimbo pode ser corrigido no formulario sem que a
# resposta vire outra - inclusive a data, que e justamente o campo que
# ja precisou de correcao.
ATUALIZAVEIS = [c for c in DESTINO if c != "ds_carimbo"]


def prepara(df: pd.DataFrame) -> pd.DataFrame:
    faltando = [o for o in COLUNAS if o not in df.columns]
    if faltando:
        raise PlanilhaIndisponivel(
            f"A aba publicada nao tem as colunas esperadas: {faltando}.\n"
            "  Se voce acrescentou ou renomeou uma pergunta no formulario, "
            "ajuste o dicionario COLUNAS deste script.")

    df = df.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    for col in DESTINO:
        df[col] = df[col].map(
            lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
            else str(v).strip()
        )
    df["ds_data"] = df["ds_data"].map(lambda v: data_brasileira(v) or None)

    # Sem carimbo nao ha identidade: a linha nao e uma resposta do
    # formulario, e sim cauda de planilha.
    sem_chave = df["ds_carimbo"].isna()
    descartadas = int(sem_chave.sum())
    df = df[~sem_chave].copy()

    df["hash_negocio"] = [
        hashlib.sha256(c.encode("utf-8")).hexdigest() for c in df["ds_carimbo"]
    ]
    df["nm_origem"] = ORIGEM
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    """Insere as respostas novas e atualiza as que mudaram na origem."""
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
    argparse.ArgumentParser(description="Carga bronze do diario meu dia").parse_args()

    if not PLANILHA_DIA_URL:
        print("ERRO: PLANILHA_DIA_URL nao definida no .env")
        return 1

    try:
        bruto = le_planilha_publicada(PLANILHA_DIA_URL)
    except PlanilhaIndisponivel as erro:
        print(f"ERRO ao ler a planilha:\n  {erro}")
        return 1

    engine = get_engine()
    novos, alterados, existiam, descartadas = sincroniza(prepara(bruto), engine)

    print("== Google Sheets / meu dia ==")
    print(f"  {len(bruto)} linhas no CSV")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} sem carimbo descartadas")
    registra_carga(engine, "bronze.dia_registro", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.dia_registro"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT COUNT(*) AS respostas,
                   COUNT(DISTINCT ds_data) AS dias_distintos,
                   MIN(ds_data) AS primeiro, MAX(ds_data) AS ultimo
            FROM {SCHEMA}.{TABELA}
            WHERE ds_data BETWEEN '2020-01-01' AND '2035-12-31'
        """, conn).to_string(index=False))

        fora = pd.read_sql(f"""
            SELECT ds_carimbo AS respondido_em, ds_data AS data_digitada
            FROM {SCHEMA}.{TABELA}
            WHERE ds_data IS NULL
               OR ds_data NOT BETWEEN '2020-01-01' AND '2035-12-31'
            ORDER BY ds_carimbo
        """, conn)
        if len(fora):
            print(f"\n== {len(fora)} com data implausivel (corrigir no formulario) ==")
            print(fora.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
