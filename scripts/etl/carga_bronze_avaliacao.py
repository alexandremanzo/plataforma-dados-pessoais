"""
Carga da camada Bronze - avaliacao fisica.

Le a aba "Avaliacoes" de pla-avaliacao-fisica.xls e grava em
bronze.avaliacao_fisica.

DUAS PARTICULARIDADES DESTA ORIGEM:

1. O arquivo e .xls DE VERDADE (Excel 97-2003, OLE2), e nao um .xlsx
   renomeado - conferido pela assinatura do arquivo. O pandas exige
   xlrd para isso; openpyxl nao le esse formato.

2. So a aba "Avaliacoes" e lida. A aba "Resultados" e uma tabela
   dinamica montada sobre ela e esta desatualizada: soma duas datas na
   mesma coluna, fazendo o peso de 2019 aparecer como 152 kg em vez de
   77,5. Ler a dinamica traria o erro junto.

A origem ja vem desempilhada - uma linha por avaliacao e por medida -
entao a carga so tipa e identifica, sem mudar o formato.

Uso:
    python carga_bronze_avaliacao.py
"""

import argparse
import time
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_PLANILHAS, get_engine  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

SCHEMA, TABELA = "bronze", "avaliacao_fisica"
ARQUIVO = "pla-avaliacao-fisica.xls"
ABA = "Avaliações"

COLUNAS = {
    "DATA": "ds_data",
    "GRUPO": "ds_grupo",
    "ITEM": "ds_item",
    "MEDIDA": "ds_medida",
    "VALOR": "ds_valor",
    "CLASSE": "ds_classe",
}
DESTINO = list(COLUNAS.values())

# A chave e data + item. Todo o resto pode ser corrigido na planilha
# sem que a medicao vire outra - inclusive o valor, que e justamente o
# que se digita errado ao transcrever um laudo.
CHAVE_HASH = ["ds_data", "ds_item"]
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]


def le_arquivo(caminho: Path) -> pd.DataFrame:
    bruto = pd.read_excel(caminho, sheet_name=ABA, dtype=object)
    bruto.columns = [str(c).strip().upper() for c in bruto.columns]

    faltando = [o for o in COLUNAS if o not in bruto.columns]
    if faltando:
        raise ValueError(
            f"A aba {ABA!r} nao tem as colunas esperadas: {faltando}.\n"
            f"  Encontradas: {list(bruto.columns)}")
    return bruto


def prepara(bruto: pd.DataFrame, nome_arquivo: str) -> pd.DataFrame:
    df = bruto.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    # A data chega como datetime do Excel; vira texto ISO para que a
    # bronze guarde tudo como texto, como as demais.
    datas = pd.to_datetime(df["ds_data"], errors="coerce")
    df["ds_data"] = datas.dt.strftime("%Y-%m-%d")

    for col in DESTINO:
        if col == "ds_data":
            continue
        df[col] = df[col].map(
            lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
            else str(v).strip()
        )

    # Sem data ou sem item nao ha o que identificar: e cauda de planilha.
    sem_chave = df["ds_data"].isna() | df["ds_item"].isna()
    descartadas = int(sem_chave.sum())
    df = df[~sem_chave].copy()

    df["hash_negocio"] = [
        hashlib.sha256(f"{d}|{i}".encode("utf-8")).hexdigest()
        for d, i in zip(df["ds_data"], df["ds_item"])
    ]
    df["nm_arquivo_origem"] = nome_arquivo
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    """Insere as medicoes novas e atualiza as que mudaram na planilha."""
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
    argparse.ArgumentParser(description="Carga bronze da avaliacao fisica").parse_args()

    caminho = PATH_PLANILHAS / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: arquivo nao encontrado em {caminho}")
        print("  Confira PATH_PLANILHAS no .env.")
        return 1

    try:
        bruto = le_arquivo(caminho)
    except ImportError:
        print("ERRO: falta a biblioteca xlrd, necessaria para ler .xls antigo.")
        print("  pip install xlrd==2.0.2")
        return 1
    except ValueError as erro:
        print(f"ERRO ao ler a planilha:\n  {erro}")
        return 1

    engine = get_engine()
    novos, alterados, existiam, descartadas = sincroniza(
        prepara(bruto, caminho.name), engine)

    print(f"== {caminho.name} / aba {ABA} ==")
    print(f"  {len(bruto)} linhas na aba")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} sem chave descartadas")
    registra_carga(engine, "bronze.avaliacao_fisica", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.avaliacao_fisica"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT COUNT(*) AS medicoes,
                   COUNT(DISTINCT ds_data) AS avaliacoes,
                   COUNT(DISTINCT ds_item) AS metricas,
                   MIN(ds_data) AS primeira, MAX(ds_data) AS ultima,
                   SUM(CASE WHEN ds_valor IS NULL THEN 1 ELSE 0 END) AS sem_valor
            FROM {SCHEMA}.{TABELA}
        """, conn).to_string(index=False))

        print("\n== Itens por avaliacao (mostra as duas eras de medicao) ==")
        print(pd.read_sql(f"""
            SELECT LEFT(ds_data, 4) AS ano, COUNT(DISTINCT ds_data) AS avaliacoes,
                   COUNT(*) / COUNT(DISTINCT ds_data) AS itens_por_avaliacao
            FROM {SCHEMA}.{TABELA}
            GROUP BY LEFT(ds_data, 4) ORDER BY 1
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
