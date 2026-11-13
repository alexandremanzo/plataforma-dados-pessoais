"""
Carga da camada Silver - manutencao do automovel.

Le as duas tabelas bronze, tipa e padroniza, grava em
silver.auto_manutencao e silver.auto_intervalo_troca.

O que esta camada acrescenta:

- NR_VISITA, sequencial da ida a oficina POR VEICULO. Uma visita
  rende varias linhas - pecas e mao de obra na mesma nota - e somar
  "quanto custou aquela revisao" precisa desse agrupamento.

- FL_PREVENTIVA, derivada da natureza declarada: revisao programada
  contra conserto.

- FL_TEM_INTERVALO, que liga a categoria a tabela de troca. So 13 das
  35 tem intervalo, e as outras nao sao cadastro faltando: nao se
  troca mao de obra nem lampada queimada por quilometragem.

O que se unifica: "Mão de Obra" e "Mão de obra" conviviam na origem.

Uso:
    python carga_silver_auto.py
    python carga_silver_auto.py --revisar
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import (  # noqa: E402
    canoniza, detecta_alteracoes, registra_carga, valor_sql,
)

_INICIO = time.monotonic()

DERIVADAS = [
    "dt_manutencao", "nm_veiculo", "nr_visita", "nr_km", "ds_natureza",
    "fl_preventiva", "ds_tipo", "ds_item", "ds_categoria", "fl_tem_intervalo",
    "nr_quantidade", "vl_gasto", "ds_local", "ds_observacao",
]


def _chave(valor) -> str:
    """Comparacao alinhada a collation do banco (Latin1_General_CI_AS)."""
    return str(valor).strip().upper() if valor is not None else ""


def transforma_intervalo(bronze: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})
    df["ds_categoria"] = canoniza(bronze["ds_categoria"])
    df["nr_intervalo_km"] = pd.to_numeric(
        bronze["ds_intervalo_km"], errors="coerce").astype("Int64")
    for coluna in ("ds_categoria", "nr_intervalo_km"):
        df[coluna] = df[coluna].map(valor_sql)
    return df


def transforma(bronze: pd.DataFrame, com_intervalo: set) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    datas = pd.to_datetime(bronze["ds_data"], errors="coerce")
    df["dt_manutencao"] = datas.dt.date
    df["nm_veiculo"] = canoniza(bronze["ds_veiculo"])

    # A visita e contada POR VEICULO: sao dois hodometros e duas
    # historias independentes, entao numerar de forma continua entre
    # eles sugeriria uma sequencia que nao existe.
    #
    # Feito por merge, e nao por chave de texto: juntar veiculo e data
    # numa string exige que os dois lados formatem a data igual, e
    # "2016-10-07" contra "2016-10-07 00:00:00" nao casa - o mapa
    # devolve nulo em tudo e so o banco reclama, la na frente.
    par = pd.DataFrame({"v": df["nm_veiculo"].values, "d": datas.values})
    visitas = par.drop_duplicates().sort_values(["v", "d"])
    visitas["n"] = visitas.groupby("v").cumcount() + 1
    df["nr_visita"] = par.merge(visitas, on=["v", "d"], how="left")["n"].values

    df["nr_km"] = pd.to_numeric(bronze["ds_km"], errors="coerce").astype("Int64")

    df["ds_natureza"] = canoniza(bronze["ds_natureza"])
    df["fl_preventiva"] = (df["ds_natureza"].fillna("").str.upper()
                           .str.startswith("REVIS"))
    df["ds_tipo"] = canoniza(bronze["ds_tipo"])
    df["ds_item"] = bronze["ds_item"]
    df["ds_categoria"] = canoniza(bronze["ds_categoria"])
    df["fl_tem_intervalo"] = [
        _chave(c) in com_intervalo for c in df["ds_categoria"]
    ]

    df["nr_quantidade"] = pd.to_numeric(bronze["ds_quantidade"], errors="coerce")
    df["vl_gasto"] = pd.to_numeric(bronze["ds_valor"], errors="coerce")
    df["ds_local"] = canoniza(bronze["ds_local"])
    df["ds_observacao"] = bronze["ds_observacao"]

    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def sincroniza(df, engine, tabela, colunas) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(colunas)} FROM silver.{tabela}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(tabela, conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", colunas)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in colunas)
            conn.execute(
                text(f"UPDATE silver.{tabela} SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def revisar(engine) -> None:
    print("\n== Gasto por veiculo e natureza ==")
    print(pd.read_sql("""
        SELECT nm_veiculo AS veiculo,
               CASE WHEN fl_preventiva = 1 THEN 'Revisão programada'
                    ELSE 'Conserto' END AS natureza,
               COUNT(*) AS itens,
               CAST(SUM(vl_gasto) AS decimal(12,2)) AS total,
               CAST(100.0 * SUM(vl_gasto) / SUM(SUM(vl_gasto))
                    OVER (PARTITION BY nm_veiculo) AS decimal(4,1)) AS pct
        FROM silver.auto_manutencao
        GROUP BY nm_veiculo, CASE WHEN fl_preventiva = 1
                 THEN 'Revisão programada' ELSE 'Conserto' END
        ORDER BY 1, 4 DESC
    """, engine).to_string(index=False))

    print("\n== Peca contra mao de obra ==")
    print(pd.read_sql("""
        SELECT ds_tipo AS tipo, COUNT(*) AS itens,
               CAST(SUM(vl_gasto) AS decimal(12,2)) AS total
        FROM silver.auto_manutencao GROUP BY ds_tipo ORDER BY 3 DESC
    """, engine).to_string(index=False))

    print("\n== Categorias sem intervalo de troca (corretivas) ==")
    print(pd.read_sql("""
        SELECT COUNT(DISTINCT ds_categoria) AS categorias,
               COUNT(*) AS itens,
               CAST(SUM(vl_gasto) AS decimal(12,2)) AS total
        FROM silver.auto_manutencao WHERE fl_tem_intervalo = 0
    """, engine).to_string(index=False))

    print("\n== Visitas mais caras ==")
    print(pd.read_sql("""
        SELECT TOP 8 nm_veiculo AS veiculo, nr_visita AS n, dt_manutencao,
               nr_km, COUNT(*) AS itens,
               CAST(SUM(vl_gasto) AS decimal(12,2)) AS total
        FROM silver.auto_manutencao
        GROUP BY nm_veiculo, nr_visita, dt_manutencao, nr_km
        ORDER BY 6 DESC
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver da manutencao auto")
    parser.add_argument("--revisar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()

    intervalo_bronze = pd.read_sql("SELECT * FROM bronze.auto_intervalo_troca", engine)
    intervalo = transforma_intervalo(intervalo_bronze)
    novos_i, alt_i = sincroniza(engine=engine, df=intervalo,
                                tabela="auto_intervalo_troca",
                                colunas=["ds_categoria", "nr_intervalo_km"])

    com_intervalo = {_chave(c) for c in intervalo["ds_categoria"]}

    bronze = pd.read_sql("SELECT * FROM bronze.auto_manutencao", engine)
    print(f"Lidos {len(bronze)} lancamentos e {len(intervalo_bronze)} intervalos")

    novos, alterados = sincroniza(
        engine=engine, df=transforma(bronze, com_intervalo),
        tabela="auto_manutencao", colunas=DERIVADAS)

    print(f"  intervalos : +{novos_i} novos, {alt_i} atualizados")
    print(f"  manutencoes: +{novos} novos, {alterados} atualizados")
    registra_carga(engine, "silver.auto_intervalo_troca", novos_i, alt_i,
                   inicio=_INICIO)
    registra_carga(engine, "silver.auto_manutencao", novos, alterados,
                   inicio=_INICIO)

    with engine.connect() as conn:
        total, veiculos, gasto = conn.execute(text("""
            SELECT COUNT(*), COUNT(DISTINCT nm_veiculo),
                   CAST(SUM(vl_gasto) AS decimal(12,2))
            FROM silver.auto_manutencao
        """)).fetchone()
    print(f"Total em silver.auto_manutencao: {total} itens em {veiculos} "
          f"veiculos, R$ {gasto:,.2f}")

    if args.revisar:
        revisar(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
