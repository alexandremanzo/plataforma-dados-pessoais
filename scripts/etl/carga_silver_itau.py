"""
Carga da camada Silver - conta corrente Itau.

Le bronze.itau_movimentacao, tipa e padroniza, grava em
silver.itau_movimentacao.

NADA E INFERIDO. Ao contrario do XP, aqui a categoria vem da planilha
ou nao vem: as descricoes do Itau embutem data e nome parcial do
estabelecimento ("LOJA-EXEMPLO*CAT-", "PIX TRANSF FULANO14/05"),
o que as torna quase unicas. Nos testes, dos prefixos mais frequentes
sem categoria poucos tinham referencia no resto da base, e algumas se
contradiziam - a mesma descricao em duas grafias aparecia com
categorias diferentes. Inferir produziria mais erro que acerto.

O que a planilha nao classificou recebe "A classificar" e aparece no
relatorio de revisao, ordenado por valor.

Uso:
    python carga_silver_itau.py
    python carga_silver_itau.py --revisar   # o que falta classificar
"""

import argparse
import time
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from regras_itau import extrai_padrao  # noqa: E402
from util_dados import (  # noqa: E402
    canoniza, texto_comparavel as _texto, valor_sql as _valor,
    registra_carga,
)

_INICIO = time.monotonic()

NAO_CLASSIFICADO = "A classificar"
TIPO_SALDO = "Saldo Conta"

DERIVADAS = [
    "dt_lancamento", "dt_pagamento", "ds_descricao", "vl_transacao",
    "ds_tipo_movimentacao", "fl_saldo", "ds_area", "ds_categoria", "ds_grupo",
    "fl_classificado", "ds_origem_classificacao", "ds_pessoa_pagar",
    "ds_pessoa_receber", "ds_forma_pgto", "ds_descricao_pgto", "ds_cidade",
    "ds_uf", "ds_pais", "ds_obs", "ds_projeto", "ds_tag",
]

ORIGEM_PLANILHA = "PLANILHA"
ORIGEM_DE_PARA = "DE-PARA"
ORIGEM_PENDENTE = "A CLASSIFICAR"


def transforma(bronze: pd.DataFrame, de_para: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    df["dt_lancamento"] = pd.to_datetime(bronze["ds_data"], errors="coerce").dt.date
    df["dt_pagamento"] = pd.to_datetime(bronze["ds_data_pgto"], errors="coerce").dt.date
    df["ds_descricao"] = bronze["ds_descricao"]
    df["vl_transacao"] = pd.to_numeric(bronze["ds_valor"], errors="coerce")

    # As linhas de saldo nao sao transacao e precisam ficar marcadas.
    df["fl_saldo"] = bronze["ds_tipo_movimentacao"].fillna("") == TIPO_SALDO

    # O tipo e coerente com o sinal em 100% da serie, entao pode ser
    # deduzido para os lancamentos vindos do extrato, que nao o trazem.
    def tipo(linha):
        if linha["fl_saldo"]:
            return "SALDO"
        if pd.isna(linha["vl_transacao"]):
            return None
        return "RECEITA" if linha["vl_transacao"] > 0 else "DESPESA"

    df["ds_tipo_movimentacao"] = df.apply(tipo, axis=1)

    for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
        df[coluna] = canoniza(bronze[coluna]).fillna(NAO_CLASSIFICADO)

    df["ds_origem_classificacao"] = [
        ORIGEM_PLANILHA if c != NAO_CLASSIFICADO else ORIGEM_PENDENTE
        for c in df["ds_categoria"]
    ]

    # O de-para preenche o que a planilha deixou em branco. Nunca
    # sobrescreve: o que voce classificou a mao tem precedencia.
    if de_para is not None and len(de_para):
        padroes = df["ds_descricao"].map(extrai_padrao)
        mapa = de_para.set_index("ds_padrao")
        for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
            df[coluna] = [
                mapa.at[p, coluna]
                if (atual == NAO_CLASSIFICADO and p in mapa.index
                    and pd.notna(mapa.at[p, coluna]))
                else atual
                for atual, p in zip(df[coluna], padroes)
            ]
        df["ds_origem_classificacao"] = [
            ORIGEM_DE_PARA if (o == ORIGEM_PENDENTE and c != NAO_CLASSIFICADO) else o
            for o, c in zip(df["ds_origem_classificacao"], df["ds_categoria"])
        ]

    df["fl_classificado"] = df["ds_categoria"] != NAO_CLASSIFICADO

    for col in ("ds_pessoa_pagar", "ds_pessoa_receber", "ds_forma_pgto",
                "ds_descricao_pgto", "ds_cidade", "ds_uf", "ds_pais",
                "ds_obs", "ds_projeto", "ds_tag"):
        df[col] = canoniza(bronze[col])

    for col in DERIVADAS:
        df[col] = df[col].map(_valor)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.itau_movimentacao", conn
        )

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("itau_movimentacao", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = []
        if len(atual):
            antes = atual.set_index("hash_negocio")
            depois = df[df["hash_negocio"].isin(antes.index)].set_index("hash_negocio")
            for h, linha in depois.iterrows():
                anterior = antes.loc[h]
                if any(_texto(linha[c]) != _texto(anterior[c]) for c in DERIVADAS):
                    alterados.append({"h": h, **{c: _valor(linha[c]) for c in DERIVADAS}})

        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.itau_movimentacao SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :h"),
                alterados,
            )

    return len(novos), len(alterados)


def relatorio(engine) -> None:
    print("\n== Procedencia dos rotulos ==")
    print(pd.read_sql("""
        SELECT ds_origem_classificacao AS origem, COUNT(*) AS lancamentos,
               CAST(SUM(ABS(vl_transacao)) AS decimal(18,2)) AS volume_abs
        FROM silver.itau_movimentacao WHERE fl_saldo = 0
        GROUP BY ds_origem_classificacao ORDER BY 2 DESC
    """, engine).to_string(index=False))

    print("\n== Cobertura da classificacao por ano ==")
    print(pd.read_sql("""
        SELECT YEAR(dt_lancamento) AS ano, COUNT(*) AS lancamentos,
               SUM(CAST(fl_classificado AS int)) AS classificados,
               CAST(100.0 * SUM(CAST(fl_classificado AS int)) / COUNT(*)
                    AS decimal(5,1)) AS pct
        FROM silver.itau_movimentacao WHERE fl_saldo = 0
        GROUP BY YEAR(dt_lancamento) ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== O que falta classificar, por peso financeiro ==")
    print(pd.read_sql("""
        SELECT TOP 15 LEFT(ds_descricao, 30) AS descricao,
               COUNT(*) AS ocorrencias,
               CAST(SUM(ABS(vl_transacao)) AS decimal(18,2)) AS volume_abs
        FROM silver.itau_movimentacao
        WHERE fl_saldo = 0 AND fl_classificado = 0
        GROUP BY LEFT(ds_descricao, 30) ORDER BY 3 DESC
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver da conta Itau")
    parser.add_argument("--revisar", action="store_true",
                        help="mostra o que ainda falta classificar")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.itau_movimentacao", engine)
    print(f"Lidos {len(bronze)} eventos da bronze")

    de_para = pd.read_sql(
        "SELECT ds_padrao, ds_area, ds_categoria, ds_grupo "
        "FROM silver.de_para_categoria_itau", engine)
    print(f"De-para de categorias: {len(de_para)} padroes rotulados")

    inseridos, atualizados = sincroniza(transforma(bronze, de_para), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.itau_movimentacao", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM silver.itau_movimentacao")).scalar()
        saldos = conn.execute(
            text("SELECT COUNT(*) FROM silver.itau_movimentacao WHERE fl_saldo = 1")).scalar()
    print(f"Total em silver.itau_movimentacao: {total} ({saldos} sao marcadores de saldo)")

    if args.revisar:
        relatorio(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
