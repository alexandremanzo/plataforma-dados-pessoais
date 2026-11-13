"""
Carga da camada Silver - cartoes de credito.

Le as tabelas bronze de cada cartao e grava em
silver.cartao_movimentacao, uma tabela unica com DS_CARTAO
identificando a origem.

Cada cartao tem sua funcao de transformacao, porque as origens sao
bem diferentes:

    XP      - planilha escrita a mao, 99% classificada no seu
              vocabulario, gasto NEGATIVO.

    Nubank  - export do banco, 2% classificado a mao mas 91%
              categorizado pelo proprio Nubank, gasto POSITIVO, e com
              os pagamentos da fatura misturados aos gastos.

O que a silver uniformiza: sinal (gasto sempre negativo), vocabulario
de categoria (via de-para) e a marcacao do pagamento de fatura.

Como nas demais origens, NADA e inferido: categoria do Nubank so vira
categoria sua quando o de-para for preenchido.

Uso:
    python carga_silver_cartao.py
    python carga_silver_cartao.py --resumo
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

NAO_CLASSIFICADO = "A classificar"

DERIVADAS = [
    "ds_cartao", "dt_compra", "dt_fatura", "ds_descricao", "nr_parcela",
    "vl_transacao", "ds_tipo_movimentacao", "ds_area", "ds_categoria",
    "ds_grupo", "fl_classificado", "ds_pessoa_pagar", "ds_pessoa_receber",
    "ds_cidade", "ds_uf", "ds_pais", "ds_obs", "fl_pago", "fl_pagamento_fatura",
]


def _tipo(valor):
    if pd.isna(valor):
        return None
    return "RECEITA" if valor > 0 else "DESPESA"


def _finaliza(df: pd.DataFrame) -> pd.DataFrame:
    df["ds_tipo_movimentacao"] = df["vl_transacao"].map(_tipo)
    df["fl_classificado"] = df["ds_categoria"] != NAO_CLASSIFICADO
    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def transforma_xp(bronze: pd.DataFrame, _de_para) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})
    df["ds_cartao"] = "XP"

    df["dt_compra"] = pd.to_datetime(bronze["ds_data"], errors="coerce").dt.date
    df["dt_fatura"] = pd.to_datetime(bronze["ds_data_pgto"], errors="coerce").dt.date
    df["ds_descricao"] = bronze["ds_descricao"]
    df["nr_parcela"] = pd.to_numeric(bronze["ds_parcela"], errors="coerce")

    # A metrica e o valor tratado: o sinal da coluna "Valor" e
    # inconsistente nos estornos, ora positivo ora negativo.
    df["vl_transacao"] = pd.to_numeric(bronze["ds_valor_tratado"], errors="coerce")

    for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
        df[coluna] = canoniza(bronze[coluna]).fillna(NAO_CLASSIFICADO)
    for coluna in ("ds_pessoa_pagar", "ds_pessoa_receber", "ds_cidade",
                   "ds_uf", "ds_pais", "ds_obs"):
        df[coluna] = canoniza(bronze[coluna])

    df["fl_pago"] = bronze["ds_status_pgto"].fillna("").str.upper().eq("S")

    # No XP o pagamento da fatura fica na conta corrente, nunca no
    # arquivo do cartao.
    df["fl_pagamento_fatura"] = False
    return _finaliza(df)


def transforma_nubank(bronze: pd.DataFrame, de_para: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})
    df["ds_cartao"] = "Nubank"

    df["dt_compra"] = pd.to_datetime(bronze["ds_data"], errors="coerce").dt.date
    df["dt_fatura"] = pd.to_datetime(bronze["ds_data_fatura"], errors="coerce").dt.date
    df["ds_descricao"] = bronze["ds_titulo"]
    df["nr_parcela"] = None

    # Extrato = N marca as 48 linhas de pagamento da propria fatura.
    pagamento = bronze["fl_extrato"].fillna("").str.upper().eq("N")

    # SINAL: no arquivo do Nubank a convencao e "quanto foi lancado NO
    # CARTAO", entao a compra vem positiva e o pagamento recebido vem
    # negativo. Do ponto de vista do seu bolso os dois sao saida, entao
    # a compra precisa ser invertida e o pagamento NAO - inverter os
    # dois deixaria o pagamento da fatura como entrada de dinheiro,
    # com sinal oposto ao mesmo evento lancado na conta do Itau.
    valor = pd.to_numeric(bronze["ds_valor"], errors="coerce")
    df["vl_transacao"] = valor.where(pagamento, -valor)

    # A classificacao manual existe em 2% dos casos e tem precedencia.
    # O resto vem do de-para das categorias do proprio Nubank.
    manual = {c: canoniza(bronze[c]) for c in ("ds_area", "ds_categoria", "ds_grupo")}
    mapa = de_para.set_index("ds_categoria_nubank") if len(de_para) else None
    categoria_banco = bronze["ds_categoria_nubank"]

    for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
        valores = []
        for atual, cat in zip(manual[coluna], categoria_banco):
            if pd.notna(atual):
                valores.append(atual)
            elif (mapa is not None and pd.notna(cat) and cat in mapa.index
                    and pd.notna(mapa.at[cat, coluna])):
                valores.append(mapa.at[cat, coluna])
            else:
                valores.append(NAO_CLASSIFICADO)
        df[coluna] = valores

    for coluna in ("ds_pessoa_pagar", "ds_pessoa_receber", "ds_cidade",
                   "ds_uf", "ds_pais", "ds_obs"):
        df[coluna] = canoniza(bronze[coluna])

    # Cartao encerrado em 2022: todas as faturas ja foram pagas.
    df["fl_pago"] = True
    df["fl_pagamento_fatura"] = pagamento
    return _finaliza(df)


ORIGENS = {
    "XP": ("bronze.cartao_xp", transforma_xp),
    "Nubank": ("bronze.cartao_nubank", transforma_nubank),
}


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.cartao_movimentacao", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("cartao_movimentacao", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.cartao_movimentacao SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def resumo(engine) -> None:
    print("\n== Consumo por ano e cartao (sem pagamento de fatura) ==")
    print(pd.read_sql("""
        SELECT YEAR(dt_compra) AS ano, ds_cartao AS cartao, COUNT(*) AS itens,
               CAST(SUM(vl_transacao) AS decimal(18,2)) AS total
        FROM silver.cartao_movimentacao WHERE fl_pagamento_fatura = 0
        GROUP BY YEAR(dt_compra), ds_cartao ORDER BY 1, 2
    """, engine).to_string(index=False))

    print("\n== Cobertura da classificacao ==")
    print(pd.read_sql("""
        SELECT ds_cartao AS cartao, COUNT(*) AS itens,
               SUM(CAST(fl_classificado AS int)) AS classificados,
               CAST(100.0 * SUM(CAST(fl_classificado AS int)) / COUNT(*)
                    AS decimal(5,1)) AS pct
        FROM silver.cartao_movimentacao WHERE fl_pagamento_fatura = 0
        GROUP BY ds_cartao ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Pagamentos de fatura isolados (nivel SINTETICO) ==")
    print(pd.read_sql("""
        SELECT ds_cartao AS cartao, COUNT(*) AS lancamentos,
               CAST(SUM(vl_transacao) AS decimal(18,2)) AS total
        FROM silver.cartao_movimentacao WHERE fl_pagamento_fatura = 1
        GROUP BY ds_cartao
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver dos cartoes")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    de_para = pd.read_sql(
        "SELECT ds_categoria_nubank, ds_area, ds_categoria, ds_grupo "
        "FROM silver.de_para_categoria_nubank", engine)
    mapeadas = de_para["ds_categoria"].notna().sum() if len(de_para) else 0
    print(f"De-para Nubank: {mapeadas} de {len(de_para)} categorias mapeadas")

    # Os dois cartoes caem na MESMA tabela, entao o registro e um so,
    # com a soma: o grao de gold.fato_carga e a tabela, nao a origem.
    # Duas linhas aqui fariam a silver do cartao parecer duas cargas.
    total_novos = total_alterados = 0
    for cartao, (tabela, transforma) in ORIGENS.items():
        bronze = pd.read_sql(f"SELECT * FROM {tabela}", engine)
        novos, alterados = sincroniza(transforma(bronze, de_para), engine)
        total_novos += novos
        total_alterados += alterados
        print(f"  {cartao:<8} {len(bronze):>5} na bronze -> "
              f"+{novos} novos, {alterados} atualizados")

    registra_carga(engine, "silver.cartao_movimentacao",
                   total_novos, total_alterados, inicio=_INICIO)

    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM silver.cartao_movimentacao")).scalar()
    print(f"\nTotal em silver.cartao_movimentacao: {n}")

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
