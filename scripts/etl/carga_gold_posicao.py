"""
Carga da camada Gold — posição da carteira, de bronze.xp_posicao.

O QUE ESTA CARGA RESOLVE E O QUE ELA RECUSA A RESOLVER.

Resolve: data da foto vira SK_DATA, origem vira SK_ORIGEM, e a posição
sai pronta para somar patrimônio e alocação.

Recusa: casar o ativo por semelhança de texto. A dim_ativo nasceu do
extrato, que chama os ativos por nome; a Pluggy identifica fundo por
CNPJ e renda fixa por código do papel. O mesmo ativo existe dos dois
lados com nomes diferentes - "LCA BANCO BV S/A" contra "LCA - BANCO
VOTORANTIM S.A.".

Casamento difuso foi TESTADO e reprovado: o mesmo algoritmo que acerta
"CDB BANCO DIGIMAIS" com 1,00 dá 0,79 para "CDB - BANCO BMG S.A"
contra "LCA BANCO BV S/A" - dois bancos, dois papéis, uma pontuação
alta. Palpite errado aqui soma patrimônio de um ativo no outro, e
ninguém revisa um número que parece plausível.

Então o casamento é EXATO (código ou nome) e o resto vira -1, visível.
CD_ATIVO_ORIGEM e NM_ATIVO_ORIGEM guardam como a Pluggy chamou cada um,
o que permite aplicar um de-para depois sem recarregar nada.

Uso:
    python carga_gold_posicao.py
    python carga_gold_posicao.py --resumo
    python carga_gold_posicao.py --sem-casar   # lista o que ficou em -1
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))

from config_db import get_engine                             # noqa: E402
from util_dados import registra_carga                        # noqa: E402

_INICIO = time.monotonic()

SK_ATIVO_NAO_CASADO = -1
NM_ORIGEM = "XP Investimentos"

# -----------------------------------------------------------------
# De-para: ativo da Pluggy -> ativo que JA EXISTE na dim com outro nome
# -----------------------------------------------------------------
# Cada entrada foi conferida uma a uma, porque casamento automatico
# aqui erra confiante: o mesmo algoritmo que acerta "CDB BANCO
# DIGIMAIS" com 1,00 da 0,79 para "CDB - BANCO BMG S.A" contra "LCA
# BANCO BV S/A" - dois bancos, dois papeis.
#
# Sao cinco porque sao cinco. Se passar de uns vinte, vira
# silver.de_para_ativo_* como os outros de-paras do projeto; com
# cinco, tabela seria cerimonia sem ganho, e aqui fica visivel para
# quem le a carga.
DE_PARA_ATIVO = {
    "XP Investor Equity Hedge FIC FIM RL":  "FUNDOS XP INVESTOR EQUITY HEDGE",
    "CDB - BANCO DIGIMAIS S.A.":            "CDB BANCO DIGIMAIS S.A.",
    "Trend Ouro FIF Multi RL":              "FUNDOS TREND OURO FIF MULTI RL",
    "XP Macro FIM RL":                      "FUNDOS XP MACRO FIM",
    # O maior da carteira: R$ 25.015,10 de posicao e 15 eventos de
    # provento no fato de fluxo desde ago/2025. O extrato encurta o
    # nome; e o mesmo investimento.
    "Valora CRI CDI Renda+ FII RL":         "Valora CRI",
}

# Vocabulario da dim_ativo (portugues) a partir do subtipo da Pluggy
# (ingles). Sem isto a dimensao ficaria metade numa lingua, metade
# noutra, e TP_ATIVO deixaria de agrupar.
TIPO_POR_SUBTIPO = {
    "STOCK":             "Ação",
    "REAL_ESTATE_FUND":  "FII",
    "ETF":               "ETF",
    "TREASURY":          "Tesouro Direto",
    "CDB":               "CDB",
    "LCA":               "LCA/LCI",
    "LCI":               "LCA/LCI",
    "CRI":               "CRI",
    "CRA":               "CRA",
    "DEBENTURES":        "Debênture",
    "COE":               "COE",
    "INVESTMENT_FUND":   "Fundo",
    "MUTUAL_FUND":       "Fundo",
    "FIXED_INCOME_FUND": "Fundo",
    "MULTIMARKET_FUND":  "Fundo",
    "STOCK_FUND":        "Fundo",
}

CLASSE_POR_TIPO = {
    "Ação":           ("Renda Variável", "Ações"),
    "FII":            ("Fundos Imobiliários", "FII"),
    "ETF":            ("Renda Variável", "ETF"),
    "Fundo":          ("Fundos", "Fundo de Investimento"),
    "Tesouro Direto": ("Renda Fixa", "Tesouro Direto"),
    "CDB":            ("Renda Fixa", "CDB"),
    "LCA/LCI":        ("Renda Fixa", "LCA/LCI"),
    "CRI":            ("Renda Fixa", "CRI"),
    "CRA":            ("Renda Fixa", "CRA"),
    "Debênture":      ("Renda Fixa", "Debênture"),
    "COE":            ("Renda Fixa", "COE"),
}

COLUNAS = ["SK_DATA", "SK_ORIGEM", "SK_ATIVO", "CD_ATIVO_ORIGEM",
           "NM_ATIVO_ORIGEM", "DS_TIPO", "DS_SUBTIPO", "DS_SITUACAO",
           "QT_COTAS", "VL_COTA", "VL_BRUTO", "VL_LIQUIDO", "VL_RESGATAVEL",
           "VL_APLICADO", "VL_TAXAS", "DT_REFERENCIA", "DT_VENCIMENTO",
           "HASH_NEGOCIO"]


def chave(serie: pd.Series) -> pd.Series:
    """Normaliza para comparar: sem espaço nas pontas, sem caixa.

    Acento NÃO é ignorado, de propósito: o banco compara assim
    (Latin1_General_CI_AS) e divergir dele faria o Python achar
    casamento que o SQL não acha, e vice-versa.
    """
    return serie.fillna("").astype(str).str.strip().str.upper()


def resolve_ativo(pos: pd.DataFrame, dim: pd.DataFrame) -> pd.Series:
    """SK_ATIVO por de-para revisado, depois casamento EXATO; -1 no resto."""
    por_codigo = dict(zip(chave(dim.CD_ATIVO), dim.SK_ATIVO))
    por_nome = dict(zip(chave(dim.NM_ATIVO), dim.SK_ATIVO))
    # O de-para vem PRIMEIRO: ele é decisão conferida, e tem de vencer
    # qualquer coincidência de grafia.
    depara = {chave(pd.Series([k]))[0]: por_nome.get(chave(pd.Series([v]))[0])
              for k, v in DE_PARA_ATIVO.items()}
    # O código da Pluggy às vezes é o próprio ticker, que na dim está
    # como NOME - por isso o código também é procurado entre os nomes.
    saida = []
    for cd, nm in zip(chave(pos.cd_ativo), chave(pos.nm_ativo)):
        sk = (depara.get(nm) or por_codigo.get(cd) or por_nome.get(nm)
              or por_nome.get(cd) or por_codigo.get(nm))
        saida.append(int(sk) if sk else SK_ATIVO_NAO_CASADO)
    return pd.Series(saida, index=pos.index)


def sincroniza_ativo(conn, pos: pd.DataFrame) -> int:
    """Cadastra em gold.dim_ativo os ativos que a Pluggy trouxe e a
    dimensão ainda não tinha.

    A IDENTIDADE MUDA POR CLASSE, e isso não é detalhe. Ação e FII são
    o ticker; fundo é o CNPJ; renda fixa é o código do papel - dois
    CDBs do mesmo banco com vencimentos diferentes são ativos
    diferentes, e o nome não os separa. Por isso CD_ATIVO recebe o
    código quando ele existe, e só cai para o nome quando não existe.

    O de-para roda ANTES: o que já existe sob outro nome não vira
    membro novo. Sem isso a dimensão ganharia o mesmo ativo duas vezes
    e somar por ativo passaria a dividir o valor - sem erro nenhum,
    só um número menor.
    """
    dim = pd.read_sql("SELECT SK_ATIVO, CD_ATIVO, NM_ATIVO FROM gold.dim_ativo",
                      conn)
    ja = resolve_ativo(pos, dim)
    faltam = pos[ja == SK_ATIVO_NAO_CASADO].copy()
    if faltam.empty:
        return 0

    # Um ativo por identidade, não por linha: lotes e pares
    # aberto/encerrado do mesmo papel são a mesma coisa.
    faltam["cd"] = faltam.cd_ativo.where(
        faltam.cd_ativo.fillna("").str.strip() != "", faltam.nm_ativo)

    # DEDUPLICA PELO NOME TAMBÉM, não só pelo código. Os papéis do
    # Tesouro vêm duas vezes: uma com ISIN e outra SEM código nenhum -
    # mesmo papel, mesmo vencimento, a segunda é o par zerado. Pelo
    # código elas parecem dois ativos ("BRSTNCLF1RL5" e "LFT") e a
    # dimensão ganhava LFT duas vezes. Fica a linha COM código, que é
    # a identidade de verdade em renda fixa.
    faltam["tem_codigo"] = (faltam.cd_ativo.fillna("").str.strip() != "")
    faltam["k_nome"] = chave(faltam.nm_ativo)
    novos = (faltam.sort_values("tem_codigo", ascending=False)
             .drop_duplicates(subset=["k_nome"])
             .drop_duplicates(subset=["cd"])
             .loc[:, ["cd", "nm_ativo", "ds_subtipo"]])

    # Nome que já existe na dim com OUTRO código entraria como membro
    # novo e viraria duplicata silenciosa. Melhor recusar e pedir uma
    # entrada no de-para.
    nomes_dim = set(chave(dim.NM_ATIVO))
    colide = novos[chave(novos.nm_ativo).isin(nomes_dim)]
    if not colide.empty:
        print("  ATENÇÃO: nome já existe na dim com outro código — "
              "acrescente ao DE_PARA_ATIVO em vez de criar:")
        for r in colide.itertuples():
            print(f"     {r.nm_ativo}")
        novos = novos[~chave(novos.nm_ativo).isin(nomes_dim)]

    if novos.empty:
        return 0

    tipo = novos.ds_subtipo.map(TIPO_POR_SUBTIPO).fillna("Não informado")
    classe = tipo.map(lambda t: CLASSE_POR_TIPO.get(t, ("Não informado",
                                                       "Não informado")))
    pd.DataFrame({
        "CD_ATIVO": novos.cd.str[:100],
        "NM_ATIVO": novos.nm_ativo.str[:200],
        "TP_ATIVO": tipo,
        "DS_CLASSE_ATIVO": [c[0] for c in classe],
        "DS_SUBCLASSE_ATIVO": [c[1] for c in classe],
        # A classificação saiu de um de-para de subtipo, não de revisão
        # sua: DEDUZIDA, como a dimensão já marca nesses casos.
        "DS_ORIGEM_CLASSE": "DEDUZIDA",
        "DS_ORIGEM_DADO": "PLUGGY",
    }).to_sql("dim_ativo", conn, schema="gold", if_exists="append", index=False)
    return len(novos)


def main() -> int:
    p = argparse.ArgumentParser(description="Carga gold da posição")
    p.add_argument("--resumo", action="store_true")
    p.add_argument("--sem-casar", action="store_true",
                   help="lista os ativos que ficaram em -1")
    args = p.parse_args()

    engine = get_engine()
    pos = pd.read_sql("SELECT * FROM bronze.xp_posicao", engine)
    if pos.empty:
        print("bronze.xp_posicao está vazia. Rode carga_bronze_xp_posicao.py.")
        return 1

    # A dimensão é sincronizada ANTES de resolver as chaves, como as
    # outras cargas do projeto fazem com classificação, tag e
    # localização.
    with engine.begin() as conn:
        criados = sincroniza_ativo(conn, pos)
    if criados:
        print(f"  gold.dim_ativo: +{criados} ativos novos (origem PLUGGY)")

    dim = pd.read_sql("SELECT SK_ATIVO, CD_ATIVO, NM_ATIVO FROM gold.dim_ativo",
                      engine)
    origem = pd.read_sql(
        f"SELECT SK_ORIGEM FROM gold.dim_origem WHERE NM_ORIGEM = '{NM_ORIGEM}'",
        engine)
    if origem.empty:
        print(f"ERRO: origem '{NM_ORIGEM}' não existe em gold.dim_origem.")
        return 1
    sk_origem = int(origem.SK_ORIGEM.iloc[0])

    fato = pd.DataFrame({
        # SK_DATA é AAAAMMDD, como o resto do projeto.
        "SK_DATA": pd.to_datetime(pos.dt_snapshot).dt.strftime("%Y%m%d").astype(int),
        "SK_ORIGEM": sk_origem,
        "SK_ATIVO": resolve_ativo(pos, dim),
        "CD_ATIVO_ORIGEM": pos.cd_ativo,
        "NM_ATIVO_ORIGEM": pos.nm_ativo,
        "DS_TIPO": pos.ds_tipo,
        "DS_SUBTIPO": pos.ds_subtipo,
        "DS_SITUACAO": pos.ds_situacao,
        "QT_COTAS": pos.qt_cotas,
        "VL_COTA": pos.vl_cota,
        "VL_BRUTO": pos.vl_bruto,
        "VL_LIQUIDO": pos.vl_liquido,
        "VL_RESGATAVEL": pos.vl_resgatavel,
        "VL_APLICADO": pos.vl_aplicado,
        "VL_TAXAS": pos.vl_taxas,
        "DT_REFERENCIA": pos.dt_referencia,
        "DT_VENCIMENTO": pos.dt_vencimento,
        # O hash vem da bronze: o grão é o mesmo, e reaproveitá-lo faz
        # as duas camadas concordarem por construção.
        "HASH_NEGOCIO": pos.hash_negocio,
    })[COLUNAS]

    # A FK para dim_calendario recusa data fora do intervalo. Melhor
    # descobrir aqui, com a data na mão, do que num erro de integridade.
    faltam = pd.read_sql(
        f"SELECT SK_DATA FROM gold.dim_calendario WHERE SK_DATA IN "
        f"({','.join(map(str, fato.SK_DATA.unique()))})", engine)
    sem_dia = set(fato.SK_DATA) - set(faltam.SK_DATA)
    if sem_dia:
        print(f"ERRO: {sorted(sem_dia)} não existem em dim_calendario. "
              f"O calendário vai até 2035; confira a data da foto.")
        return 1

    casados = int((fato.SK_ATIVO != SK_ATIVO_NAO_CASADO).sum())
    print(f"  {len(fato)} posições · {casados} com ativo casado, "
          f"{len(fato) - casados} em -1")
    nc = fato[fato.SK_ATIVO == SK_ATIVO_NAO_CASADO]
    print(f"     os não casados somam {nc.VL_LIQUIDO.sum():,.2f} "
          f"({nc.VL_LIQUIDO.sum() / fato.VL_LIQUIDO.sum() * 100:.0f}% do patrimônio)")

    with engine.begin() as conn:
        ja = pd.read_sql(
            "SELECT HASH_NEGOCIO FROM gold.fato_posicao_investimento", conn)
        novos = fato[~fato.HASH_NEGOCIO.isin(set(ja.HASH_NEGOCIO))]
        if len(novos):
            novos.to_sql("fato_posicao_investimento", conn, schema="gold",
                         if_exists="append", index=False)

    print(f"  gold.fato_posicao_investimento: +{len(novos)} novas, "
          f"{len(fato) - len(novos)} já existiam")
    registra_carga(engine, "gold.fato_posicao_investimento", len(novos), 0,
                   inicio=_INICIO)

    if args.sem_casar:
        print("\n== Ativos sem casamento na dim_ativo ==")
        print("   (o de-para entra quando houver lista revisada)")
        print(nc[["CD_ATIVO_ORIGEM", "NM_ATIVO_ORIGEM", "DS_SUBTIPO", "VL_LIQUIDO"]]
              .sort_values("VL_LIQUIDO", ascending=False).to_string(index=False))

    if args.resumo:
        print("\n== Patrimônio por classe, última foto ==")
        print(pd.read_sql("""
            WITH u AS (SELECT MAX(SK_DATA) d FROM gold.fato_posicao_investimento)
            SELECT f.DS_TIPO, f.DS_SUBTIPO, COUNT(*) ativos,
                   CAST(SUM(f.VL_LIQUIDO) AS decimal(14,2)) liquido,
                   CAST(100.0 * SUM(f.VL_LIQUIDO) /
                        SUM(SUM(f.VL_LIQUIDO)) OVER () AS decimal(5,1)) pct
            FROM gold.fato_posicao_investimento f, u
            WHERE f.SK_DATA = u.d AND f.DS_SITUACAO = 'ACTIVE'
            GROUP BY f.DS_TIPO, f.DS_SUBTIPO ORDER BY 4 DESC""",
            engine).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
