"""
Carga da camada Gold - fato da conta familia.

Le silver.familia_movimentacao e grava em gold.fato_familia.

Reaproveita gold.dim_calendario e as tres dimensoes de
classificacao financeira - as mesmas
dimensao do fato pessoal, o que permite comparar os dois pelo mesmo
eixo de categoria. A dimensao absorve sozinha as combinacoes novas,
entao MORADIA e as demais categorias exclusivas da familia entram sem
nenhum cadastro manual.

Dimensao propria: dim_pessoa, que responde quem pagou.

Uso:
    python carga_gold_familia.py
    python carga_gold_familia.py --resumo
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from regras_localizacao import resolve as resolve_local  # noqa: E402
from regras_localizacao import sincroniza_localizacao  # noqa: E402
from regras_tag import sincroniza_tag, tag_principal_por_hash  # noqa: E402
from regras_classificacao import (  # noqa: E402
    resolve_chaves, sincroniza_classificacao,
)
from util_dados import (  # noqa: E402
    aplica_flags, detecta_alteracoes, registra_carga, valor_sql,
)

_INICIO = time.monotonic()

NAO_CLASSIFICADO = "A classificar"

# Quem e titular da conta, o que e a propria conta conjunta e o que e
# terceiro. A distincao importa: gasto pago pela conta conjunta ja saiu
# do dinheiro aportado pelos dois, entao somar as tres naturezas como
# se fossem equivalentes distorce a divisao real.
TITULARES = {"ALE", "LIA"}
CONTA_CONJUNTA = {"CONTA"}

COLUNAS_FATO = [
    "SK_DATA", "SK_DATA_PAGAMENTO", "SK_PESSOA",
    "SK_AREA_FINANC", "SK_CATEGORIA_FINANC", "SK_GRUPO_FINANC",
    "VL_TRANSACAO", "DS_TIPO_FLUXO", "FL_PAGO", "FL_FUTURO",
    "DS_DETALHE_ORIGINAL", "DS_PESSOA_RECEBER", "SK_LOCALIZACAO", "SK_TAG",
]


def tipo_pessoa(nome) -> str:
    if not nome:
        return "Não informado"
    chave = str(nome).strip().upper()
    if chave in TITULARES:
        return "Titular"
    if chave in CONTA_CONJUNTA:
        return "Conta conjunta"
    return "Terceiro"


def _sk_data(valor):
    if pd.isna(valor):
        return -1
    return int(pd.Timestamp(valor).strftime("%Y%m%d"))


def _chave(*partes) -> tuple:
    """
    Chave de comparacao alinhada a collation do banco.

    O banco usa Latin1_General_CI_AS: ignora caixa e respeita acento.
    Comparar em Python com distincao de caixa faz a carga achar que a
    combinacao e nova, tentar inserir, e o banco recusar por violacao
    de unicidade - foi o que aconteceu com "Manutencao Casa", que ja
    existia com outra caixa.
    """
    return tuple(str(p).strip().upper() if p is not None else "" for p in partes)


def sincroniza_pessoas(conn, dados: pd.DataFrame) -> tuple[dict, int]:
    """Insere as pessoas novas e devolve o mapa nome -> SK."""
    pessoas = pd.DataFrame({
        "NM_PESSOA": sorted(dados["ds_pessoa_pagar"].dropna().unique())
    })
    pessoas["DS_TIPO"] = pessoas["NM_PESSOA"].map(tipo_pessoa)

    def le():
        return pd.read_sql(
            "SELECT SK_PESSOA, NM_PESSOA FROM gold.dim_pessoa", conn)

    existente = le()
    ja_tem = {_chave(n) for n in existente["NM_PESSOA"]}
    novas = pessoas[[_chave(n) not in ja_tem for n in pessoas["NM_PESSOA"]]]

    if len(novas):
        novas.to_sql("dim_pessoa", conn, schema="gold", if_exists="append", index=False)
        existente = le()

    # Chaveado pela forma comparavel: assim um nome que difere so na
    # caixa reaproveita a linha que ja existe, em vez de criar outra.
    return {_chave(n)[0]: sk for sk, n in zip(existente["SK_PESSOA"],
                                              existente["NM_PESSOA"])}, len(novas)


def monta_fato(dados, mapas, mapa_pessoa, mapa_local, tag_por_hash) -> pd.DataFrame:
    hoje = date.today()
    fato = pd.DataFrame({"HASH_NEGOCIO": dados["hash_negocio"]})

    fato["SK_DATA"] = dados["dt_lancamento"].map(_sk_data)
    fato["SK_DATA_PAGAMENTO"] = dados["dt_pagamento"].map(_sk_data)

    # Tres chaves em vez de uma: a COMBINACAO de area, categoria e
    # grupo vive aqui, no fato, e nao numa dimensao de trios.
    for coluna, valores in resolve_chaves(dados, mapas).items():
        fato[coluna] = valores
    fato["SK_PESSOA"] = dados["ds_pessoa_pagar"].map(
        lambda p: mapa_pessoa.get(_chave(p)[0], -1) if pd.notna(p) else -1)

    fato["VL_TRANSACAO"] = dados["vl_transacao"]
    fato["DS_TIPO_FLUXO"] = dados["vl_transacao"].map(
        lambda v: None if pd.isna(v) else ("RECEITA" if v > 0 else "DESPESA"))
    fato["FL_PAGO"] = dados["fl_pago"]
    fato["FL_FUTURO"] = [
        bool(d) and d > hoje for d in dados["dt_lancamento"]
    ]

    fato["DS_DETALHE_ORIGINAL"] = dados["ds_descricao"]
    fato["DS_PESSOA_RECEBER"] = dados["ds_pessoa_receber"]

    # Cidade, UF e pais viraram uma chave; o texto segue na silver.
    fato["SK_LOCALIZACAO"] = [
        resolve_local(mapa_local, c, u, p)
        for c, u, p in zip(dados["ds_cidade"], dados["ds_uf"], dados["ds_pais"])
    ]

    # A tag PRINCIPAL. Quem escolhe qual e gold.vw_tag_principal; a
    # ponte continua guardando todas, e e por ela que se soma por tag.
    fato["SK_TAG"] = [tag_por_hash.get(h, -1) for h in dados["hash_negocio"]]

    for coluna in COLUNAS_FATO:
        fato[coluna] = fato[coluna].map(valor_sql)
    fato = aplica_flags(fato)
    return fato


def resumo(engine) -> None:
    print("\n== Quem bancou os gastos ja realizados ==")
    print(pd.read_sql("""
        SELECT p.NM_PESSOA AS pessoa, p.DS_TIPO AS natureza,
               COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total
        FROM gold.fato_familia f
        JOIN gold.dim_pessoa p ON p.SK_PESSOA = f.SK_PESSOA
        WHERE f.FL_FUTURO = 'N' AND f.VL_TRANSACAO < 0
        GROUP BY p.NM_PESSOA, p.DS_TIPO ORDER BY 4
    """, engine).to_string(index=False))

    print("\n== Maiores categorias ==")
    print(pd.read_sql("""
        SELECT TOP 8 a.NM_AREA AS area, c.NM_CATEGORIA AS categoria,
               COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total
        FROM gold.fato_familia f
        JOIN gold.dim_area_financ a ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
        JOIN gold.dim_categoria_financ c ON c.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
        WHERE f.FL_FUTURO = 'N' AND f.VL_TRANSACAO < 0
        GROUP BY a.NM_AREA, c.NM_CATEGORIA ORDER BY 4
    """, engine).to_string(index=False))

    print("\n== Gasto da familia por ano ==")
    print(pd.read_sql("""
        SELECT d.NR_ANO AS ano, COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total
        FROM gold.fato_familia f
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE f.FL_FUTURO = 'N'
        GROUP BY d.NR_ANO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Comprometido no futuro ==")
    print(pd.read_sql("""
        SELECT COUNT(*) AS parcelas,
               CAST(SUM(VL_TRANSACAO) AS decimal(18,2)) AS total,
               MAX(SK_DATA) AS ate
        FROM gold.fato_familia WHERE FL_FUTURO = 'S'
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold da conta familia")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    dados = pd.read_sql("SELECT * FROM silver.familia_movimentacao", engine)
    print(f"Lidos {len(dados)} lancamentos da silver")

    with engine.begin() as conn:
        mapa_pessoa, novas_pessoas = sincroniza_pessoas(conn, dados)
        mapas, novas_dim = sincroniza_classificacao(conn, dados)
        # A ORDEM IMPORTA: as duas dimensoes sao sincronizadas ANTES de
        # montar o fato, porque agora o fato guarda a chave delas. A
        # ponte tem de estar refeita antes de ler a tag principal - a
        # view le a ponte, e lida cedo devolveria a tag da carga passada.
        novas_tags, ligacoes = sincroniza_tag(
            conn, dict(zip(dados["hash_negocio"], dados["ds_obs"])),
            "fato_familia")
        novos_locais, mapa_local = sincroniza_localizacao(
            conn, zip(dados["ds_cidade"], dados["ds_uf"], dados["ds_pais"]))

        fato = monta_fato(dados, mapas, mapa_pessoa, mapa_local,
                          tag_principal_por_hash(conn, "fato_familia"))

        atual = pd.read_sql(
            f"SELECT HASH_NEGOCIO, {', '.join(COLUNAS_FATO)} "
            f"FROM gold.fato_familia", conn)

        novos = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
        if len(novos):
            novos.to_sql("fato_familia", conn, schema="gold",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, fato, "HASH_NEGOCIO", COLUNAS_FATO)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_FATO)
            conn.execute(
                text(f"UPDATE gold.fato_familia SET {sets}, DT_CARGA = SYSDATETIME() "
                     f"WHERE HASH_NEGOCIO = :chave"),
                alterados,
            )

    print(f"  dim_pessoa         : +{novas_pessoas} novas")
    for tabela, n in novas_dim.items():
        print(f"  {tabela:<19}: +{n} membros novos")
    print(f"  dim_tag            : +{novas_tags} tags novas")
    print(f"  dim_localizacao    : +{novos_locais} lugares novos")
    print(f"  ponte_tag          : {ligacoes} ligacoes")
    print(f"  fato               : +{len(novos)} novos, {len(alterados)} atualizados")
    registra_carga(engine, "gold.fato_familia",
                   len(novos), len(alterados), inicio=_INICIO)

    print("\n== Conferencia silver x gold ==")
    print(pd.read_sql("""
        SELECT (SELECT COUNT(*) FROM silver.familia_movimentacao) AS silver,
               (SELECT COUNT(*) FROM gold.fato_familia) AS gold,
               (SELECT CAST(SUM(vl_transacao) AS decimal(18,2))
                  FROM silver.familia_movimentacao) AS soma_silver,
               (SELECT CAST(SUM(VL_TRANSACAO) AS decimal(18,2))
                  FROM gold.fato_familia) AS soma_gold
    """, engine).to_string(index=False))

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
