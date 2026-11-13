"""
Carga da camada Gold - fato de movimentacao.

Une silver.itau_movimentacao e silver.cartao_movimentacao em
gold.fato_movto_financ. Investimentos nao entram: ficam em
gold.fato_investimento.

O QUE ESTA CARGA RESOLVE

1. NIVEL. Um gasto no cartao existe em dois planos - a compra
   detalhada e o pagamento da fatura na conta corrente. Somar os dois
   conta a mesma despesa duas vezes. DS_NIVEL separa:

       SINTETICO  pagamento de fatura (o PAI)
       ANALITICO  o gasto em si (o FILHO), e tambem as despesas
                  diretas da conta corrente

2. VOCABULARIO. As origens divergiam na grafia dos mesmos rotulos -
   41 grafias de categoria para 32 conceitos. A canonizacao escolhe
   uma forma por conceito.

3. SINAL. Ja uniformizado na silver: negativo e saida em todas as
   origens.

Uso:
    python carga_gold_movimentacao.py
    python carga_gold_movimentacao.py --resumo
"""

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from regras_classificacao import (  # noqa: E402
    remove_membros_orfaos, resolve_chaves, sincroniza_classificacao,
)
from regras_localizacao import resolve as resolve_local  # noqa: E402
from regras_localizacao import sincroniza_localizacao  # noqa: E402
from regras_tag import sincroniza_tag, tag_principal_por_hash  # noqa: E402
from util_dados import (  # noqa: E402
    aplica_flags, detecta_alteracoes, registra_carga, valor_sql,
)

_INICIO = time.monotonic()

NAO_CLASSIFICADO = "A classificar"

SK_ORIGEM = {"Itau": 2, "XP": 3, "Nubank": 4}

# O historico 2014-2018 nao tem uma origem so: cada forma de pagamento
# daquela epoca vira uma. A grafia vem canonizada da silver, mas a
# comparacao e por forma comparavel para nao depender de caixa.
SK_ORIGEM_FORMA = {
    "DINHEIRO/DEBITO": 5,
    "VISA BB": 6,
    "VALE ALIMENTAÇÃO": 7,
    "VISA/CTI": 8,
    "DINERS": 9,
}

# Grupo do Itau que identifica o pagamento da fatura do cartao. Nao e
# uma suposicao: sao 34 lancamentos ja classificados assim na planilha,
# com descricao "Cartao de Credito XP".
GRUPO_FATURA_ITAU = "Fatura Crédito"

COLUNAS_FATO = [
    "SK_ORIGEM", "SK_DATA", "SK_DATA_FATURA",
    "SK_AREA_FINANC", "SK_CATEGORIA_FINANC", "SK_GRUPO_FINANC",
    "VL_TRANSACAO", "DS_NIVEL", "DS_TIPO_FLUXO", "NR_PARCELA",
    "DS_DETALHE_ORIGINAL", "DS_PESSOA_PAGAR", "DS_PESSOA_RECEBER",
    "SK_LOCALIZACAO", "SK_TAG",
]


def _conceito(texto) -> str:
    """Chave que ignora caixa e acento, para agrupar grafias do mesmo rotulo."""
    if not isinstance(texto, str):
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def _acentos(texto: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFKD", texto)
               if unicodedata.combining(c))


def canoniza_entre_origens(serie: pd.Series) -> pd.Series:
    """
    Escolhe uma grafia por conceito, entre todas as origens.

    O criterio e a forma ortograficamente correta primeiro e a mais
    frequente depois: entre "SAUDE" (189 vezes, sem acento) e "SAUDE"
    com acento (21 vezes), vence a acentuada; entre "ESTILO DE VIDA"
    (4.160) e "Estilo de Vida" (36), que empatam em acentos, vence a
    frequente.

    canoniza() de util_dados resolve isso dentro de uma origem; esta
    funcao precisa existir porque a divergencia acontece ENTRE origens,
    e so aqui as duas se encontram.
    """
    validos = serie.dropna()
    if validos.empty:
        return serie

    frequencia = validos.value_counts()
    escolha = {}
    for grafia, n in frequencia.items():
        chave = _conceito(grafia)
        atual = escolha.get(chave)
        if atual is None:
            escolha[chave] = (grafia, _acentos(grafia), n)
            continue
        _, ac_atual, n_atual = atual
        ac_novo = _acentos(grafia)
        if (ac_novo, n) > (ac_atual, n_atual):
            escolha[chave] = (grafia, ac_novo, n)

    mapa = {chave: valor[0] for chave, valor in escolha.items()}
    return serie.map(lambda v: mapa.get(_conceito(v), v) if isinstance(v, str) else v)


def _sk_data(valor):
    if pd.isna(valor):
        return -1
    return int(pd.Timestamp(valor).strftime("%Y%m%d"))


def le_origens(engine) -> pd.DataFrame:
    """
    Traz as tres silvers no formato comum do fato.

    DS_TAG_FONTE existe porque a coluna que marca contexto muda de
    origem: no Itau e nos cartoes e o proprio OBS, mas no historico
    2014-2018 o OBS guarda numeros soltos ("-160", "556.37") que o
    interpretador de marcacoes leria como tag. La quem marca contexto e
    a coluna Projeto. O texto inteiro de cada base segue na silver, para
    auditoria - o que muda e so de onde saem as tags. No fato ficou a
    chave da tag principal (SK_TAG), nao mais o texto.
    """
    itau = pd.read_sql("""
        SELECT hash_negocio, dt_lancamento AS dt, NULL AS dt_fatura,
               ds_descricao, NULL AS nr_parcela, vl_transacao,
               ds_area, ds_categoria, ds_grupo,
               ds_pessoa_pagar, ds_pessoa_receber, ds_cidade, ds_uf, ds_pais, ds_obs,
               ds_obs AS ds_tag_fonte,
               ds_grupo AS grupo_bruto, CAST(0 AS bit) AS fl_pagamento_fatura,
               'Itau' AS origem
        FROM silver.itau_movimentacao
        WHERE fl_saldo = 0
    """, engine)

    cartao = pd.read_sql("""
        SELECT hash_negocio, dt_compra AS dt, dt_fatura,
               ds_descricao, nr_parcela, vl_transacao,
               ds_area, ds_categoria, ds_grupo,
               ds_pessoa_pagar, ds_pessoa_receber, ds_cidade, ds_uf, ds_pais, ds_obs,
               ds_obs AS ds_tag_fonte,
               NULL AS grupo_bruto, fl_pagamento_fatura,
               ds_cartao AS origem
        FROM silver.cartao_movimentacao
    """, engine)

    # Historico 2014-2018. Filtra fl_meta: aquelas 287 linhas sao
    # orcamento planejado, e entrariam como +R$ 135.522 de receita que
    # nunca existiu. E a mesma razao pela qual a gold de investimentos
    # exclui margem - a silver guarda, o fato nao conta.
    #
    # DS_NIVEL nao se aplica aqui: nao ha dualidade compra/fatura nesta
    # base, entao todo lancamento e analitico.
    historico = pd.read_sql("""
        SELECT hash_negocio, dt_lancamento AS dt, NULL AS dt_fatura,
               ds_descricao, NULL AS nr_parcela, vl_transacao,
               ds_area, ds_categoria, ds_grupo,
               ds_pessoa_pagar, ds_pessoa_receber, ds_cidade, ds_uf, ds_pais,
               ds_obs, ds_projeto AS ds_tag_fonte,
               NULL AS grupo_bruto, CAST(0 AS bit) AS fl_pagamento_fatura,
               ISNULL(ds_forma_pagamento, '(sem forma)') AS origem
        FROM silver.financ_historico
        WHERE fl_meta = 0
    """, engine)

    return pd.concat([itau, cartao, historico], ignore_index=True)


def monta_fato(dados: pd.DataFrame, mapas: dict, mapa_local: dict,
               tag_por_hash: dict) -> pd.DataFrame:
    fato = pd.DataFrame({"HASH_NEGOCIO": dados["hash_negocio"]})
    fato["SK_ORIGEM"] = [
        SK_ORIGEM.get(o) or SK_ORIGEM_FORMA.get(str(o).strip().upper(), -1)
        for o in dados["origem"]
    ]
    fato["SK_DATA"] = dados["dt"].map(_sk_data)
    fato["SK_DATA_FATURA"] = dados["dt_fatura"].map(_sk_data)

    # Tres chaves em vez de uma: a COMBINACAO de area, categoria e
    # grupo vive aqui, no fato, e nao numa dimensao de trios.
    for coluna, valores in resolve_chaves(dados, mapas).items():
        fato[coluna] = valores

    fato["VL_TRANSACAO"] = dados["vl_transacao"]

    # O pagamento da fatura e o lancamento sintetico. Vem de duas
    # deteccoes diferentes conforme a origem: no Itau, do grupo que
    # voce mesmo classificou; no cartao Nubank, da coluna Extrato.
    sintetico = (dados["fl_pagamento_fatura"].fillna(False).astype(bool)
                 | (dados["grupo_bruto"] == GRUPO_FATURA_ITAU))
    fato["DS_NIVEL"] = ["SINTETICO" if s else "ANALITICO" for s in sintetico]

    fato["DS_TIPO_FLUXO"] = dados["vl_transacao"].map(
        lambda v: None if pd.isna(v) else ("RECEITA" if v > 0 else "DESPESA"))
    fato["NR_PARCELA"] = dados["nr_parcela"]
    fato["DS_DETALHE_ORIGINAL"] = dados["ds_descricao"]
    for destino, origem in (("DS_PESSOA_PAGAR", "ds_pessoa_pagar"),
                            ("DS_PESSOA_RECEBER", "ds_pessoa_receber")):
        fato[destino] = dados[origem]

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
    print("\n== Movimentacao por nivel ==")
    print(pd.read_sql("""
        SELECT f.DS_NIVEL AS nivel, o.NM_ORIGEM AS origem, COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total
        FROM gold.fato_movto_financ f
        JOIN gold.dim_origem o ON o.SK_ORIGEM = f.SK_ORIGEM
        GROUP BY f.DS_NIVEL, o.NM_ORIGEM ORDER BY 1, 4
    """, engine).to_string(index=False))

    print("\n== Despesa por ano (SO o nivel analitico) ==")
    print(pd.read_sql("""
        SELECT d.NR_ANO AS ano, COUNT(*) AS lancamentos,
               CAST(SUM(CASE WHEN f.VL_TRANSACAO < 0 THEN f.VL_TRANSACAO END)
                    AS decimal(18,2)) AS despesa,
               CAST(SUM(CASE WHEN f.VL_TRANSACAO > 0 THEN f.VL_TRANSACAO END)
                    AS decimal(18,2)) AS receita
        FROM gold.fato_movto_financ f
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE f.DS_NIVEL = 'ANALITICO'
        GROUP BY d.NR_ANO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Maiores categorias de despesa (analitico) ==")
    print(pd.read_sql("""
        SELECT TOP 12 c.DS_AREA AS area, c.DS_CATEGORIA AS categoria,
               COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total
        FROM gold.fato_movto_financ f
        JOIN gold.dim_categoria_financ c ON c.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
        WHERE f.DS_NIVEL = 'ANALITICO' AND f.VL_TRANSACAO < 0
        GROUP BY c.DS_AREA, c.DS_CATEGORIA ORDER BY 4
    """, engine).to_string(index=False))

    print("\n== A dupla contagem que o nivel evita ==")
    print(pd.read_sql("""
        SELECT CAST(SUM(CASE WHEN DS_NIVEL='ANALITICO' AND VL_TRANSACAO<0
                             THEN VL_TRANSACAO END) AS decimal(18,2)) AS despesa_correta,
               CAST(SUM(CASE WHEN DS_NIVEL='SINTETICO'
                             THEN VL_TRANSACAO END) AS decimal(18,2)) AS pagamentos_fatura,
               CAST(SUM(CASE WHEN VL_TRANSACAO<0 THEN VL_TRANSACAO END)
                    AS decimal(18,2)) AS somando_tudo_errado
        FROM gold.fato_movto_financ
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold da movimentacao")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    dados = le_origens(engine)
    print(f"Lidos {len(dados)} lancamentos das silvers")

    # A canonizacao acontece aqui, e nao na silver, porque a divergencia
    # de grafia e ENTRE origens - so neste ponto elas se encontram.
    for coluna in ("ds_area", "ds_categoria", "ds_grupo"):
        antes = dados[coluna].nunique()
        dados[coluna] = canoniza_entre_origens(dados[coluna]).fillna(NAO_CLASSIFICADO)
        print(f"  {coluna}: {antes} grafias -> {dados[coluna].nunique()} conceitos")

    with engine.begin() as conn:
        mapas, novas_dim = sincroniza_classificacao(conn, dados)

        # A ORDEM IMPORTA: as duas dimensoes sao sincronizadas ANTES de
        # montar o fato, porque agora o fato guarda a chave delas. A
        # ponte tem de estar refeita antes de ler a tag principal - a
        # view le a ponte, e lida cedo devolveria a tag da carga passada.
        novas_tags, ligacoes = sincroniza_tag(
            conn, dict(zip(dados["hash_negocio"], dados["ds_tag_fonte"])),
            "fato_movto_financ")
        novos_locais, mapa_local = sincroniza_localizacao(
            conn, zip(dados["ds_cidade"], dados["ds_uf"], dados["ds_pais"]))

        fato = monta_fato(dados, mapas, mapa_local,
                          tag_principal_por_hash(conn, "fato_movto_financ"))

        atual = pd.read_sql(
            f"SELECT HASH_NEGOCIO, {', '.join(COLUNAS_FATO)} "
            f"FROM gold.fato_movto_financ", conn)

        novos = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
        if len(novos):
            novos.to_sql("fato_movto_financ", conn, schema="gold",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, fato, "HASH_NEGOCIO", COLUNAS_FATO)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_FATO)
            conn.execute(
                text(f"UPDATE gold.fato_movto_financ SET {sets}, "
                     f"DT_CARGA = SYSDATETIME() WHERE HASH_NEGOCIO = :chave"),
                alterados,
            )

    print()
    for tabela, n in novas_dim.items():
        print(f"  {tabela:<21}: +{n} membros novos")
    print(f"  dim_tag            : +{novas_tags} tags novas")
    print(f"  ponte_tag          : {ligacoes} ligacoes")
    print(f"  dim_localizacao    : +{novos_locais} lugares novos")
    print(f"  fato               : +{len(novos)} novos, {len(alterados)} atualizados")
    registra_carga(engine, "gold.fato_movto_financ",
                   len(novos), len(alterados), inicio=_INICIO)

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
