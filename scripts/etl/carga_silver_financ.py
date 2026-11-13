"""
Carga da camada Silver - historico financeiro 2014-2018.

Le bronze.financ_historico, tipa e classifica, grava em
silver.financ_historico.

DUAS DECISOES QUE ESTA ORIGEM EXIGE:

1. FL_META separa orcamento de movimentacao. Sao 287 linhas com tipo
   "Meta", 24 por categoria, somando +R$ 135.522 - orcamento mensal
   planejado, nao dinheiro que entrou. Ficam aqui por fidelidade e o
   fato as exclui.

2. A AREA E DERIVADA, porque a coluna da planilha esta vazia em todas
   as linhas. Vem do vocabulario que ja existe nas tres dimensoes
   financeiras, em dois niveis, e ds_origem_area registra qual deles
   decidiu - a distincao entre evidencia e inferencia fica explicita
   na tabela, e nao escondida no codigo.

Uso:
    python carga_silver_financ.py
    python carga_silver_financ.py --revisar
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
    "ds_tipo_movimentacao", "fl_meta", "ds_area", "ds_categoria", "ds_grupo",
    "ds_origem_area", "fl_classificado", "ds_forma_pagamento",
    "ds_pessoa_pagar", "ds_pessoa_receber", "ds_cidade", "ds_uf", "ds_pais",
    "ds_obs", "ds_projeto", "fl_pago",
]


def _chave(valor) -> str:
    return str(valor).strip().upper() if valor is not None else ""


def mapas_de_area(engine) -> tuple[dict, dict]:
    """
    Monta os dois niveis de heranca de area, a partir do que ja foi
    classificado no fato consolidado.

    O peso e o numero de lancamentos, e nao a simples existencia da
    combinacao: a classificacao e ambigua - TRANSPORTE/Combustivel
    existe sob ESTILO DE VIDA em 212 lancamentos e sob GASTOS
    ESSENCIAIS em 128 - entao "a area mais usada" e a unica leitura
    defensavel quando ha empate de existencia.

    O PROPRIO HISTORICO E EXCLUIDO DA REFERENCIA, e isso e essencial.
    Sem o filtro a carga entra num laco: a silver deriva a area das
    frequencias do fato, o fato e alimentado por esta silver, e cada
    execucao desloca as frequencias e re-deriva areas diferentes -
    772 atualizacoes fantasma por rodada, sem nunca convergir. A
    referencia tem de ser o vocabulario que JA existia, que nao depende
    desta carga.
    """
    # text() e obrigatorio para o parametro nomeado: com a string crua
    # o pandas entrega o SQL ao driver sem traduzir :nc, e o pyodbc
    # reclama de "0 parameter markers, but 1 parameters supplied".
    uso = pd.read_sql(text("""
        SELECT a.NM_AREA AS DS_AREA, c.NM_CATEGORIA AS DS_CATEGORIA,
               g.NM_GRUPO AS DS_GRUPO, COUNT(*) AS n
        FROM gold.fato_movto_financ f
        JOIN gold.dim_area_financ      a ON a.SK_AREA_FINANC      = f.SK_AREA_FINANC
        JOIN gold.dim_categoria_financ c ON c.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
        JOIN gold.dim_grupo_financ     g ON g.SK_GRUPO_FINANC     = f.SK_GRUPO_FINANC
        WHERE a.NM_AREA <> :nc
          AND NOT EXISTS (SELECT 1 FROM silver.financ_historico h
                           WHERE h.hash_negocio = f.HASH_NEGOCIO)
        GROUP BY a.NM_AREA, c.NM_CATEGORIA, g.NM_GRUPO
    """), engine, params={"nc": NAO_CLASSIFICADO})

    uso["cat"] = uso["DS_CATEGORIA"].map(_chave)
    uso["gru"] = uso["DS_GRUPO"].map(_chave)

    por_par = (uso.sort_values("n", ascending=False)
                  .drop_duplicates(["cat", "gru"])
                  .set_index(["cat", "gru"])["DS_AREA"].to_dict())
    por_cat = (uso.groupby(["cat", "DS_AREA"])["n"].sum().reset_index()
                  .sort_values("n", ascending=False)
                  .drop_duplicates("cat")
                  .set_index("cat")["DS_AREA"].to_dict())
    return por_par, por_cat


def transforma(bronze: pd.DataFrame, por_par: dict, por_cat: dict) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    df["dt_lancamento"] = pd.to_datetime(bronze["ds_data"], errors="coerce").dt.date
    df["dt_pagamento"] = pd.to_datetime(bronze["ds_data_pgto"], errors="coerce").dt.date
    df["ds_descricao"] = bronze["ds_descricao"]
    df["vl_transacao"] = pd.to_numeric(bronze["ds_valor_tratado"], errors="coerce")

    df["ds_tipo_movimentacao"] = bronze["ds_tipo_movimentacao"].map(
        lambda v: None if v is None or pd.isna(v) else str(v).strip().upper())
    df["fl_meta"] = df["ds_tipo_movimentacao"].fillna("") == "META"

    df["ds_categoria"] = canoniza(bronze["ds_categoria"]).fillna(NAO_CLASSIFICADO)
    df["ds_grupo"] = canoniza(bronze["ds_grupo"]).fillna(NAO_CLASSIFICADO)

    # Heranca em dois niveis, com a procedencia registrada. O par
    # exato e evidencia - aquela combinacao ja foi classificada assim
    # antes; a categoria sozinha e inferencia, e o relatorio precisa
    # saber a diferenca.
    areas, origens = [], []
    for cat, gru in zip(df["ds_categoria"], df["ds_grupo"]):
        area = por_par.get((_chave(cat), _chave(gru)))
        if area:
            areas.append(area)
            origens.append("PAR_EXATO")
            continue
        area = por_cat.get(_chave(cat))
        if area:
            areas.append(area)
            origens.append("CATEGORIA")
        else:
            areas.append(NAO_CLASSIFICADO)
            origens.append(NAO_CLASSIFICADO)
    df["ds_area"] = areas
    df["ds_origem_area"] = origens
    df["fl_classificado"] = df["ds_categoria"] != NAO_CLASSIFICADO

    df["ds_forma_pagamento"] = canoniza(bronze["ds_forma_pagamento"])
    for coluna in ("ds_pessoa_pagar", "ds_pessoa_receber", "ds_cidade",
                   "ds_uf", "ds_pais", "ds_projeto"):
        df[coluna] = canoniza(bronze[coluna])
    df["ds_obs"] = bronze["ds_obs"]

    df["fl_pago"] = bronze["ds_status_pgto"].fillna("").str.strip().str.upper().eq("S")

    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.financ_historico", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("financ_historico", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.financ_historico SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def revisar(engine) -> None:
    print("\n== Procedencia da area ==")
    print(pd.read_sql("""
        SELECT ds_origem_area AS procedencia, COUNT(*) AS lancamentos,
               CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS decimal(4,1)) AS pct
        FROM silver.financ_historico WHERE fl_meta = 0
        GROUP BY ds_origem_area ORDER BY 2 DESC
    """, engine).to_string(index=False))

    print("\n== O que ficou sem area ==")
    print(pd.read_sql("""
        SELECT ds_categoria, ds_grupo, COUNT(*) AS n
        FROM silver.financ_historico
        WHERE ds_origem_area = 'A classificar' AND fl_meta = 0
        GROUP BY ds_categoria, ds_grupo ORDER BY 3 DESC
    """, engine).to_string(index=False))

    print("\n== Gasto por ano, ja sem as metas ==")
    print(pd.read_sql("""
        SELECT YEAR(dt_lancamento) AS ano, COUNT(*) AS lancamentos,
               CAST(SUM(CASE WHEN vl_transacao < 0 THEN vl_transacao END)
                    AS decimal(14,2)) AS despesa,
               CAST(SUM(CASE WHEN vl_transacao > 0 THEN vl_transacao END)
                    AS decimal(14,2)) AS receita
        FROM silver.financ_historico WHERE fl_meta = 0
        GROUP BY YEAR(dt_lancamento) ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== As metas, que o fato vai excluir ==")
    print(pd.read_sql("""
        SELECT COUNT(*) AS linhas,
               CAST(SUM(vl_transacao) AS decimal(14,2)) AS total,
               MIN(dt_lancamento) AS de, MAX(dt_lancamento) AS ate
        FROM silver.financ_historico WHERE fl_meta = 1
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver do historico financeiro")
    parser.add_argument("--revisar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.financ_historico", engine)
    print(f"Lidos {len(bronze)} lancamentos da bronze")

    por_par, por_cat = mapas_de_area(engine)
    print(f"  heranca de area: {len(por_par)} pares e {len(por_cat)} categorias "
          f"conhecidos")

    inseridos, atualizados = sincroniza(transforma(bronze, por_par, por_cat), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.financ_historico", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total, meta = conn.execute(text("""
            SELECT COUNT(*), SUM(CAST(fl_meta AS int)) FROM silver.financ_historico
        """)).fetchone()
    print(f"Total em silver.financ_historico: {total} "
          f"({meta} de orcamento, que o fato exclui)")

    if args.revisar:
        revisar(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
