"""
Carga da camada Silver - investimentos XP.

Le bronze.xp_movimentacao, aplica tipagem e classificacao, e grava
em silver.xp_movimentacao.

A silver e inteiramente derivada da bronze, entao poderia ser
reconstruida do zero a cada execucao. Nao e o que acontece aqui: o
script faz upsert por hash_negocio, inserindo o que e novo e
atualizando o que mudou. O motivo e manter sk_movimentacao estavel -
quando a camada gold existir, as chaves das dimensoes vao apontar
para ela, e recriar a tabela renumeraria tudo.

Consequencia pratica util: mudar uma regra em regras_xp.py e rodar
este script reclassifica toda a serie historica, sem tocar nas
chaves.

Uso:
    python carga_silver_xp.py
    python carga_silver_xp.py --divergencias   # relatorio de revisao
"""

import argparse
import time
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import texto_comparavel as _texto, valor_sql as _valor_sql, registra_carga  # noqa: E402
from regras_xp import (  # noqa: E402
    classifica_categoria, consolida_fundos, eh_rendimento, extrai_ativo,
    normaliza, normaliza_ativo, tickers_de, tipo_movimentacao,
)

_INICIO = time.monotonic()

DERIVADAS = ["dt_movimentacao", "dt_liquidacao", "ds_lancamento", "vl_transacao",
             "vl_saldo", "ds_categoria", "ds_ativo", "fl_rendimento",
             "ds_tipo_movimentacao", "ds_categoria_manual", "fl_divergencia_manual"]


def transforma(bronze: pd.DataFrame) -> pd.DataFrame:
    """Aplica tipagem e regras de classificacao sobre a bronze."""
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    # Tipagem: o que nao converter vira nulo em vez de derrubar a carga.
    df["dt_movimentacao"] = pd.to_datetime(
        bronze["ds_movimentacao"], errors="coerce").dt.date
    df["dt_liquidacao"] = pd.to_datetime(
        bronze["ds_liquidacao"], errors="coerce").dt.date
    df["ds_lancamento"] = bronze["ds_lancamento"]
    df["vl_transacao"] = pd.to_numeric(bronze["ds_valor"], errors="coerce")
    df["vl_saldo"] = pd.to_numeric(bronze["ds_saldo"], errors="coerce")

    # Classificacao recalculada para toda a serie, garantindo criterio
    # uniforme entre 2021 e hoje.
    df["ds_categoria"] = bronze["ds_lancamento"].map(classifica_categoria)

    # O ativo sai em duas passadas. A XP identifica o papel ora pelo
    # ticker (ITUB4), ora pelo ISIN (BRITUBACNPR1), conforme o tipo de
    # lancamento. A primeira passada extrai o que houver; a segunda
    # resolve os ISIN usando como referencia os tickers que a propria
    # base ja conhece, para nao inventar codigo que nao existe.
    ativo_bruto = bronze["ds_lancamento"].map(extrai_ativo)
    conhecidos = tickers_de(ativo_bruto)
    ativo = ativo_bruto.map(lambda a: normaliza_ativo(a, conhecidos))

    # Terceira passada, so para fundos: a XP trunca a descricao num
    # comprimento fixo e o mesmo fundo aparece com nomes de tamanhos
    # diferentes. Consolida os codigos que formam cadeia de prefixo.
    familias = consolida_fundos(set(ativo.dropna()))
    df["ds_ativo"] = ativo.map(lambda a: familias.get(a, a))
    df["fl_rendimento"] = [
        eh_rendimento(c, v) for c, v in zip(df["ds_categoria"], df["vl_transacao"])
    ]
    df["ds_tipo_movimentacao"] = df["vl_transacao"].map(tipo_movimentacao)

    # Comparacao com a classificacao manual, quando existia.
    df["ds_categoria_manual"] = bronze["ds_categoria_origem"]
    # pd.notna, e nao bool(): NaN e VERDADEIRO em Python. Enquanto o
    # teste era bool(man), o resultado dependia da versao do pandas -
    # no 2.3 do host um lancamento sem classificacao manual chegava
    # como None (falso, sem divergencia), no 3.0 do container chega
    # como NaN (verdadeiro, divergencia). Eram 54 lancamentos marcados
    # como "voce classificou diferente do automatico" sem nunca terem
    # tido classificacao manual, e a silver do XP oscilava entre os
    # dois valores a cada rodada, conforme quem tivesse rodado por
    # ultimo. Sem classificacao manual nao existe divergencia.
    df["fl_divergencia_manual"] = [
        pd.notna(man) and str(man).strip() != ""
        and normaliza(man) != normaliza(auto)
        for man, auto in zip(df["ds_categoria_manual"], df["ds_categoria"])
    ]

    df["vl_transacao"] = df["vl_transacao"].astype(object).where(df["vl_transacao"].notna(), None)
    df["vl_saldo"] = df["vl_saldo"].astype(object).where(df["vl_saldo"].notna(), None)
    df["ds_ativo"] = df["ds_ativo"].where(pd.notna(df["ds_ativo"]), None)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    """Insere os eventos novos e atualiza os que tiveram valor alterado."""
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.xp_movimentacao", conn
        )

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("xp_movimentacao", conn, schema="silver",
                         if_exists="append", index=False)

        # Compara pelo texto das colunas derivadas: simples e suficiente
        # para o volume desta base.
        alterados = []
        if len(atual):
            antes = atual.set_index("hash_negocio")
            depois = df[df["hash_negocio"].isin(antes.index)].set_index("hash_negocio")
            for h, linha in depois.iterrows():
                anterior = antes.loc[h]
                if any(_texto(linha[c]) != _texto(anterior[c]) for c in DERIVADAS):
                    alterados.append(
                        {"h": h, **{c: _valor_sql(linha[c]) for c in DERIVADAS}}
                    )

        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.xp_movimentacao SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :h"),
                alterados,
            )

    return len(novos), len(alterados)


def relatorio(engine) -> None:
    """Mostra onde as regras discordam da classificacao manual antiga."""
    print("\n== Categorias atribuidas ==")
    print(pd.read_sql("""
        SELECT ds_categoria AS categoria, COUNT(*) AS eventos,
               SUM(CAST(fl_divergencia_manual AS int)) AS divergem_do_manual
        FROM silver.xp_movimentacao
        GROUP BY ds_categoria ORDER BY COUNT(*) DESC
    """, engine).to_string(index=False))

    print("\n== Lancamentos que nenhuma regra reconheceu (categoria 'Outros') ==")
    outros = pd.read_sql("""
        SELECT TOP 15 LEFT(ds_lancamento, 62) AS lancamento,
               COUNT(*) AS ocorrencias
        FROM silver.xp_movimentacao WHERE ds_categoria = 'Outros'
        GROUP BY LEFT(ds_lancamento, 62) ORDER BY COUNT(*) DESC
    """, engine)
    print(outros.to_string(index=False) if len(outros) else "  nenhum")

    print("\n== Divergencias entre regra e classificacao manual ==")
    div = pd.read_sql("""
        SELECT TOP 20 ds_categoria_manual AS manual, ds_categoria AS regra,
               COUNT(*) AS eventos,
               MIN(LEFT(ds_lancamento, 46)) AS exemplo
        FROM silver.xp_movimentacao WHERE fl_divergencia_manual = 1
        GROUP BY ds_categoria_manual, ds_categoria ORDER BY COUNT(*) DESC
    """, engine)
    print(div.to_string(index=False) if len(div) else "  nenhuma")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver dos investimentos XP")
    parser.add_argument("--divergencias", action="store_true",
                        help="mostra o relatorio de revisao das regras")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.xp_movimentacao", engine)
    print(f"Lidos {len(bronze)} eventos da bronze")

    inseridos, atualizados = sincroniza(transforma(bronze), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.xp_movimentacao", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM silver.xp_movimentacao")).scalar()
    print(f"Total em silver.xp_movimentacao: {total}")

    if args.divergencias:
        relatorio(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
