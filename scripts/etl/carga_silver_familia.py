"""
Carga da camada Silver - conta familia.

Le bronze.familia_movimentacao, tipa e padroniza, grava em
silver.familia_movimentacao.

Nada e inferido: o que a planilha nao classificou fica como
"A classificar". O que esta camada faz e unificar grafias e marcar
incoerencias, nunca adivinhar.

Uso:
    python carga_silver_familia.py
    python carga_silver_familia.py --revisar   # o que merece atencao
"""

import argparse
import time
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import canoniza, detecta_alteracoes, valor_sql, registra_carga  # noqa: E402

_INICIO = time.monotonic()

NAO_CLASSIFICADO = "A classificar"

DERIVADAS = [
    "dt_lancamento", "dt_pagamento", "ds_descricao", "vl_transacao",
    "ds_tipo_movimentacao", "ds_area", "ds_categoria", "ds_grupo",
    "fl_classificado", "ds_pessoa_pagar", "ds_pessoa_receber",
    "ds_forma_pgto", "ds_descricao_pgto", "ds_cidade", "ds_uf", "ds_pais",
    "ds_obs", "fl_pago", "fl_sinal_divergente",
]


def transforma(bronze: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    df["dt_lancamento"] = pd.to_datetime(bronze["ds_data"], errors="coerce").dt.date
    df["dt_pagamento"] = pd.to_datetime(bronze["ds_data_pgto"], errors="coerce").dt.date
    df["ds_descricao"] = bronze["ds_descricao"]
    df["vl_transacao"] = pd.to_numeric(bronze["ds_valor_tratado"], errors="coerce")

    # DESPESA chega em quatro grafias na origem. Aqui vira maiuscula
    # sempre, porque sao apenas dois valores e caixa alta e o padrao
    # dominante - diferente dos rotulos de categoria, onde a forma mais
    # frequente e preservada para nao deixar o relatorio ilegivel.
    df["ds_tipo_movimentacao"] = bronze["ds_tipo_movimentacao"].map(
        lambda v: None if v is None or pd.isna(v) else str(v).strip().upper())

    for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
        df[coluna] = canoniza(bronze[coluna]).fillna(NAO_CLASSIFICADO)
    df["fl_classificado"] = df["ds_categoria"] != NAO_CLASSIFICADO

    for coluna in ("ds_pessoa_pagar", "ds_pessoa_receber", "ds_forma_pgto",
                   "ds_descricao_pgto", "ds_cidade", "ds_uf", "ds_pais", "ds_obs"):
        df[coluna] = canoniza(bronze[coluna])

    df["fl_pago"] = bronze["ds_status_pgto"].fillna("").str.upper().eq("S")

    # Coerencia entre o tipo declarado e o sinal do valor. Nao corrige:
    # apenas marca, para que a revisao aconteca na planilha, que e a
    # fonte da verdade.
    df["fl_sinal_divergente"] = [
        bool(tipo) and pd.notna(valor) and valor != 0
        and ((tipo == "DESPESA" and valor > 0) or (tipo == "RECEITA" and valor < 0))
        for tipo, valor in zip(df["ds_tipo_movimentacao"], df["vl_transacao"])
    ]

    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.familia_movimentacao", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("familia_movimentacao", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.familia_movimentacao SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def revisar(engine) -> None:
    print("\n== Lancamentos com sinal divergente do tipo ==")
    div = pd.read_sql("""
        SELECT dt_lancamento, LEFT(ds_descricao, 34) AS descricao,
               vl_transacao, ds_tipo_movimentacao AS tipo, ds_categoria
        FROM silver.familia_movimentacao WHERE fl_sinal_divergente = 1
        ORDER BY ABS(vl_transacao) DESC
    """, engine)
    print(div.to_string(index=False) if len(div) else "  nenhum")

    print("\n== Quanto cada um pagou (so o que ja aconteceu) ==")
    print(pd.read_sql("""
        SELECT ds_pessoa_pagar AS pessoa, COUNT(*) AS lancamentos,
               CAST(SUM(vl_transacao) AS decimal(18,2)) AS total,
               CAST(100.0 * SUM(vl_transacao)
                    / SUM(SUM(vl_transacao)) OVER () AS decimal(5,1)) AS pct
        FROM silver.familia_movimentacao
        WHERE dt_lancamento <= CAST(SYSDATETIME() AS date) AND vl_transacao < 0
        GROUP BY ds_pessoa_pagar ORDER BY 3
    """, engine).to_string(index=False))

    print("\n== Maiores categorias ==")
    print(pd.read_sql("""
        SELECT TOP 10 ds_categoria AS categoria, COUNT(*) AS lancamentos,
               CAST(SUM(vl_transacao) AS decimal(18,2)) AS total
        FROM silver.familia_movimentacao WHERE vl_transacao < 0
        GROUP BY ds_categoria ORDER BY 3
    """, engine).to_string(index=False))

    print("\n== Comprometido no futuro (parcelas a vencer) ==")
    print(pd.read_sql("""
        SELECT YEAR(dt_lancamento) AS ano, COUNT(*) AS lancamentos,
               CAST(SUM(vl_transacao) AS decimal(18,2)) AS total
        FROM silver.familia_movimentacao
        WHERE dt_lancamento > CAST(SYSDATETIME() AS date)
        GROUP BY YEAR(dt_lancamento) ORDER BY 1
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver da conta familia")
    parser.add_argument("--revisar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.familia_movimentacao", engine)
    print(f"Lidos {len(bronze)} eventos da bronze")

    inseridos, atualizados = sincroniza(transforma(bronze), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.familia_movimentacao", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total, divergentes = conn.execute(text("""
            SELECT COUNT(*), SUM(CAST(fl_sinal_divergente AS int))
            FROM silver.familia_movimentacao
        """)).fetchone()
    print(f"Total em silver.familia_movimentacao: {total} "
          f"({divergentes} com sinal divergente)")

    if args.revisar:
        revisar(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
