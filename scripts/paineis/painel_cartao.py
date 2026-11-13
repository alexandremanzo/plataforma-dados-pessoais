"""
Painel do cartao de credito, em HTML offline.

Le gold.fato_movto_financ (so SELECT): os gastos de todos os cartoes
(nivel ANALITICO), o pagamento das faturas no banco (SINTETICO) e o
investback da XP em gold.fato_investimento. O HTML recorta por
periodo, pelo mes da FATURA (quando o gasto foi cobrado).

Regras:

  COMPRA PARCELADA. O cartao XP grava uma linha por parcela, com a
  mesma data de compra, descricao e valor, e NR_PARCELA crescente. A
  compra e reconstituida juntando essas linhas; o total de parcelas e
  a maior parcela vista. Compra com uma so parcela "1" e a vista.

  EM ABERTO = parcelas com fatura depois do mes de hoje: e a divida
  ja assumida, que vai cair nas proximas faturas.

  PAGO x FATURA. A fatura de um mes e a soma dos lancamentos com
  aquela data de fatura (gastos menos estornos). O pago e o que saiu
  do banco no mesmo mes para o cartao (grupo "Fatura Credito" no Itau;
  pagamento interno no Nubank). Meses sem pagamento registrado ficam
  marcados, e nao contam como diferenca.

  ONDE CORTAR usa a compressibilidade do grupo (Essencial, Eventual,
  Compressivel), a mesma do painel de financas.

Saida site/painel-cartao.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_cartao.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_cartao.html")
SAIDA = RAIZ / "site" / "painel-cartao.html"

NOME_CARTAO = {"Cartão XP": "XP", "Cartão Nubank": "Nubank", "Visa Banco do Brasil": "Visa BB",
               "Visa Citibank": "Citibank", "Diners": "Diners"}
CLASSES = ["Essencial", "Eventual", "Cortável", "Sem classe", "Não é gasto"]
CLASSE = {"Essencial": 0, "Eventual": 1, "Compressivel": 2, "Nao e gasto": 4}
DESCR_MIN = 150          # descricao so vai para o HTML em compra grande ou parcelada


def le(eng) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    gastos = pd.read_sql("""
        SELECT c.DT_DATA, cf.DT_DATA AS DT_FATURA, f.VL_TRANSACAO, f.NR_PARCELA, o.NM_ORIGEM,
               f.DS_DETALHE_ORIGINAL, f.DS_PESSOA_RECEBER, a.NM_AREA, k.NM_CATEGORIA, g.NM_GRUPO,
               g.DS_COMPRESSIBILIDADE, t.NM_TAG, t.DS_TIPO AS DS_TIPO_TAG
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          LEFT JOIN gold.dim_calendario cf ON cf.SK_DATA = f.SK_DATA_FATURA
          JOIN gold.dim_origem o           ON o.SK_ORIGEM = f.SK_ORIGEM
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          LEFT JOIN gold.dim_tag t         ON t.SK_TAG = f.SK_TAG
         WHERE o.DS_TIPO_CONTA = 'Cartão de crédito' AND f.DS_NIVEL = 'ANALITICO'
    """, eng)
    # pagamento de fatura: Itau (cartao XP) e o pagamento interno do Nubank
    pagos = pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO, o.NM_ORIGEM
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_origem o     ON o.SK_ORIGEM = f.SK_ORIGEM
         WHERE f.DS_NIVEL = 'SINTETICO'
    """, eng)
    # investback: o cashback do cartao XP, creditado num fundo da XP
    invest = pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO
          FROM gold.fato_investimento f
          JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
          JOIN gold.dim_categoria_investimento k ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
         WHERE k.NM_CATEGORIA = 'Investback'
    """, eng)
    return gastos, pagos, invest


def classe(r) -> int:
    if r.DS_COMPRESSIBILIDADE in CLASSE:
        return CLASSE[r.DS_COMPRESSIBILIDADE]
    return 0 if r.NM_AREA == "GASTOS ESSENCIAIS" else 3


def meses_entre(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    gastos, pagos, invest = le(eng)
    df = gastos[gastos["VL_TRANSACAO"].fillna(0) != 0].copy()
    df["cartao"] = df["NM_ORIGEM"].map(NOME_CARTAO).fillna(df["NM_ORIGEM"])
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    # cartao antigo sem data de fatura: cobra no mes da compra
    df["fatura"] = pd.to_datetime(df["DT_FATURA"].fillna(df["DT_DATA"])).dt.strftime("%Y-%m")
    df["defasa"] = [max(0, meses_entre(d[:7], f)) for d, f in zip(df["data"], df["fatura"])]
    df["gasto"] = -df["VL_TRANSACAO"].astype(float)          # gasto +, estorno -
    df["cat"] = df["NM_CATEGORIA"].str.strip().str.capitalize()
    df["grupo"] = df["NM_GRUPO"].str.strip().map(lambda g: g.capitalize() if g.isupper() and len(g) > 3 else g)
    df["classe"] = df.apply(classe, axis=1)
    df["receb"] = df["DS_PESSOA_RECEBER"].fillna("").str.strip()
    df["desc"] = df["DS_DETALHE_ORIGINAL"].fillna("").str.strip()
    df["tag"] = df["NM_TAG"].where(df["DS_TIPO_TAG"].isin(["Marcação", "Viagem", "Imóvel"]))
    df["parc"] = df["NR_PARCELA"].fillna(0).astype(int)

    # compra: as parcelas do mesmo item juntas; o resto, uma linha = uma compra
    chave = df["cartao"] + "|" + df["data"] + "|" + df["desc"] + "|" + df["gasto"].abs().round(2).astype(str)
    df["chave"] = chave.where(df["parc"] > 0, "L" + df.index.astype(str))
    g = df.groupby("chave")
    df["ntot"] = g["parc"].transform("max")
    df["total"] = g["gasto"].transform("sum")
    df.loc[df["ntot"] <= 1, "parc"] = 0                      # "1" sozinho e compra a vista
    df.loc[df["ntot"] <= 1, "ntot"] = 0
    df = df.sort_values(["data", "chave", "parc"]).reset_index(drop=True)

    grandes = df[(df["ntot"] > 0) | (df["total"].abs() >= DESCR_MIN)].drop_duplicates("chave")
    ic_compra = {k: i for i, k in enumerate(grandes["chave"])}
    compras = [[r.desc, r.ntot, round(float(r.total), 2)] for r in grandes.itertuples()]

    cartoes = [c for c in ["XP", "Nubank", "Visa BB", "Citibank", "Diners"] if c in set(df["cartao"])]
    cats, grupos = sorted(df["cat"].unique()), sorted(df["grupo"].unique())
    recebs = df["receb"].value_counts().index.tolist()
    tags = sorted(df["tag"].dropna().unique())
    ia, ic, ig, ir, it = ({x: i for i, x in enumerate(v)} for v in (cartoes, cats, grupos, recebs, tags))
    # [data compra, meses ate a fatura, gasto, cartao, cat, grupo, classe, parcela, de n, compra, recebedor, tag]
    linhas = [[r.data, r.defasa, round(r.gasto, 2), ia[r.cartao], ic[r.cat], ig[r.grupo], r.classe,
               r.parc, r.ntot, ic_compra.get(r.chave, -1), ir[r.receb], it[r.tag] if isinstance(r.tag, str) else -1]
              for r in df.itertuples()]

    # pagamentos de fatura, por cartao
    p = pagos.copy()
    p["cartao"] = p["NM_ORIGEM"].map({"Itaú Conta Corrente": "XP", "Cartão Nubank": "Nubank"})
    p = p.dropna(subset=["cartao"])
    p["data"] = pd.to_datetime(p["DT_DATA"]).dt.strftime("%Y-%m-%d")
    pagamentos = [[r.data, round(-float(r.VL_TRANSACAO), 2), ia[r.cartao]] for r in p.sort_values("data").itertuples()]
    ib = invest.copy()
    ib["data"] = pd.to_datetime(ib["DT_DATA"]).dt.strftime("%Y-%m-%d")
    investback = [[r.data, round(float(r.VL_TRANSACAO), 2)] for r in ib.sort_values("data").itertuples()]

    hoje = pd.Timestamp.now()
    dados = {
        "gerado": hoje.strftime("%d/%m/%Y %H:%M"), "hoje": hoje.strftime("%Y-%m-%d"),
        "cartoes": cartoes, "cats": cats, "grupos": grupos, "classes": CLASSES, "recebs": recebs, "tags": tags,
        "compras": compras, "linhas": linhas, "pagamentos": pagamentos, "investback": investback,
    }

    # conferencia no terminal
    mes_hoje = hoje.strftime("%Y-%m")
    print(f"{len(df)} lançamentos de cartão, {df['data'].min()} a {df['data'].max()}; {len(compras)} compras com descrição")
    print(df.groupby("cartao").agg(n=("gasto", "size"), gasto=("gasto", "sum"), ini=("data", "min"), fim=("data", "max")).round(0).to_string())
    fat = df.groupby(["cartao", "fatura"])["gasto"].sum()
    p["mes"] = p["data"].str[:7]
    pg = p.groupby(["cartao", "mes"])["VL_TRANSACAO"].sum().mul(-1)
    cmp_ = pd.DataFrame({"fatura": fat, "pago": pg}).fillna(0)
    cmp_ = cmp_[(cmp_.index.get_level_values(1) <= mes_hoje)]
    cmp_["dif"] = cmp_["pago"] - cmp_["fatura"]
    print("\nPago x fatura (diferenças acima de R$ 1, com pagamento registrado):")
    print(cmp_[(cmp_["pago"] > 0) & (cmp_["dif"].abs() > 1)].round(2).to_string())
    ab = df[df["fatura"] > mes_hoje]
    print(f"\nEm aberto (fatura depois de {mes_hoje}): {ab['gasto'].sum():,.2f}; parcelado {ab[ab['parc'] > 0]['gasto'].sum():,.2f} "
          f"em {ab[ab['parc'] > 0]['chave'].nunique()} compras, até {ab['fatura'].max()}")
    print(f"Investback: {ib['VL_TRANSACAO'].sum():,.2f} em {len(ib)} créditos")
    print(df[df["fatura"].between("2025-11", mes_hoje)].groupby("classe")["gasto"].sum().div(12).round(0).rename(index=dict(enumerate(CLASSES))).to_string())

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.carimba(html, mzo.atualizacao(eng, ['fato_movto_financ', 'fato_investimento']))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
