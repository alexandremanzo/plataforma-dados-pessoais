"""
Carga da camada Silver - avaliacao fisica.

Le bronze.avaliacao_fisica, tipa e classifica, grava em
silver.avaliacao_fisica.

O que esta camada acrescenta:

- NR_AVALIACAO, o numero sequencial da avaliacao. As avaliacoes sao
  irregulares - de um mes a mais de tres anos entre elas - e a
  pergunta natural e "como estou em relacao a anterior". Sem um
  sequencial, responder isso exige navegar por data dentro de cada
  metrica.

- DS_ERA e FL_SERIE_CONTINUA. A serie nao e homogenea: ate 2013 o
  laudo trazia circunferencias e pressao; de 2018 em diante e
  bioimpedancia. So cinco metricas atravessam as duas eras, e sao as
  unicas que sustentam um grafico de 18 anos sem buraco.

O que esta camada DESCARTA: a coluna CLASSE da origem. Ela parecia
classificar a medida, mas 8 dos 30 itens aparecem com mais de um
rotulo e o padrao muda por ano - sinal de coluna arrastada. A
classificacao vem de GRUPO, que e consistente.

Uso:
    python carga_silver_avaliacao.py
    python carga_silver_avaliacao.py --revisar
"""

import argparse
import time
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import detecta_alteracoes, valor_sql, registra_carga  # noqa: E402

_INICIO = time.monotonic()

CORTE_ERA = pd.Timestamp("2015-01-01")
ERA_ANTIGA, ERA_NOVA = "Até 2013", "2018 em diante"

DERIVADAS = [
    "dt_avaliacao", "nr_avaliacao", "ds_era", "ds_grupo", "ds_metrica",
    "ds_unidade", "vl_medida", "fl_medido", "fl_serie_continua",
]


def transforma(bronze: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    datas = pd.to_datetime(bronze["ds_data"], errors="coerce")
    df["dt_avaliacao"] = datas.dt.date

    # Sequencial da avaliacao, e nao da linha: todas as medidas de uma
    # mesma data compartilham o numero.
    ordem = {d: i for i, d in enumerate(sorted(datas.dropna().unique()), start=1)}
    df["nr_avaliacao"] = datas.map(ordem)

    df["ds_era"] = [ERA_ANTIGA if d < CORTE_ERA else ERA_NOVA for d in datas]

    df["ds_grupo"] = bronze["ds_grupo"]
    df["ds_metrica"] = bronze["ds_item"]
    df["ds_unidade"] = bronze["ds_medida"]

    df["vl_medida"] = pd.to_numeric(bronze["ds_valor"], errors="coerce")
    df["fl_medido"] = df["vl_medida"].notna()

    # Uma metrica so sustenta grafico de longo prazo se foi medida nas
    # duas eras. Calculado a partir dos dados, e nao de lista fixa: se
    # uma metrica antiga voltar a ser medida, ela passa a contar
    # sozinha, sem ninguem lembrar de atualizar o codigo.
    eras_por_metrica = df.groupby("ds_metrica")["ds_era"].nunique()
    continuas = set(eras_por_metrica[eras_por_metrica > 1].index)
    df["fl_serie_continua"] = df["ds_metrica"].isin(continuas)

    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.avaliacao_fisica", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("avaliacao_fisica", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.avaliacao_fisica SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def revisar(engine) -> None:
    print("\n== Metricas que atravessam as duas eras (servem ao grafico longo) ==")
    print(pd.read_sql("""
        SELECT ds_metrica AS metrica, ds_unidade AS un, COUNT(*) AS medicoes,
               MIN(dt_avaliacao) AS primeira, MAX(dt_avaliacao) AS ultima
        FROM silver.avaliacao_fisica WHERE fl_serie_continua = 1
        GROUP BY ds_metrica, ds_unidade ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Metricas de uma era so ==")
    print(pd.read_sql("""
        SELECT ds_era AS era, COUNT(DISTINCT ds_metrica) AS metricas,
               MIN(dt_avaliacao) AS de, MAX(dt_avaliacao) AS ate
        FROM silver.avaliacao_fisica WHERE fl_serie_continua = 0
        GROUP BY ds_era ORDER BY 3
    """, engine).to_string(index=False))

    print("\n== Medidas sem valor ==")
    print(pd.read_sql("""
        SELECT ds_metrica AS metrica, COUNT(*) AS vezes
        FROM silver.avaliacao_fisica WHERE fl_medido = 0
        GROUP BY ds_metrica ORDER BY 2 DESC
    """, engine).to_string(index=False))

    print("\n== Intervalo entre avaliacoes ==")
    print(pd.read_sql("""
        SELECT nr_avaliacao AS n, dt_avaliacao,
               DATEDIFF(day, LAG(dt_avaliacao) OVER (ORDER BY nr_avaliacao),
                        dt_avaliacao) AS dias_desde_anterior
        FROM (SELECT DISTINCT nr_avaliacao, dt_avaliacao
                FROM silver.avaliacao_fisica) a
        ORDER BY nr_avaliacao
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver da avaliacao fisica")
    parser.add_argument("--revisar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.avaliacao_fisica", engine)
    print(f"Lidas {len(bronze)} medicoes da bronze")

    inseridos, atualizados = sincroniza(transforma(bronze), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.avaliacao_fisica", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total, avaliacoes, continuas = conn.execute(text("""
            SELECT COUNT(*), COUNT(DISTINCT dt_avaliacao),
                   COUNT(DISTINCT CASE WHEN fl_serie_continua = 1
                                       THEN ds_metrica END)
            FROM silver.avaliacao_fisica
        """)).fetchone()
    print(f"Total em silver.avaliacao_fisica: {total} medicoes em "
          f"{avaliacoes} avaliacoes ({continuas} metricas de serie continua)")

    if args.revisar:
        revisar(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
