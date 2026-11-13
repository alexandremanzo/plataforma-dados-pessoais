"""
Painel de investimentos, em HTML offline.

Le gold.fato_investimento (extrato da XP desde nov/2021) e
gold.fato_posicao_investimento (posicao diaria via Open Finance, desde
15/10/2026), so com SELECT, e embute o resultado no template.

Regras, combinadas com o dono dos dados:

  SO XP. Previdencia e cofrinho ficam fora (nao ha saldo, so aporte).

  FLUXO EXTERNO e o dinheiro que cruza a porta da XP: Transferencia
  (entrada) e Retirada, Pagamento CC e Pagamento ao Banco XP (saida).
  Aplicacao, resgate, compra e venda sao movimentos internos.

  PROVENTOS sao o grupo Proventos do extrato: rendimento de FII,
  dividendo e JCP, juros de LCA e cupom de COE, reembolso de evento e
  taxa de aluguel (BTC). Investback e cashback do cartao: aparece, mas
  fica fora do yield.

  POSICAO: o Open Finance da corretora nao entrega a carteira inteira
  (COE, FII de balcao e alguns fundos ficam de fora). O total oficial e
  por classe sai de uma foto do app (CARTEIRA_APP); o Open Finance da
  o detalhe por ativo. Na demonstracao a foto e gerada junto com os dados.

  RESULTADO ESTIMADO = patrimonio do app + tudo que saiu - tudo que
  entrou. Sem a foto do app, usa posicao + caixa + COE/FII ao custo na
  data do ultimo lancamento, e o numero vira piso.

  PROVENTOS sempre do extrato: a media mensal dos ultimos 12 meses e o
  numero unico usado no topo e na secao de renda passiva.

Saida site/painel-investimentos.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_investimentos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402
import painel_financas as fin  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_investimentos.html")
SAIDA = RAIZ / "site" / "painel-investimentos.html"
# foto da carteira por classe, como o app da corretora mostra; na demo, gerada por demo/gera_dados.py
APP = RAIZ / "demo" / "dados" / "carteira_app.json"

ENTRADAS = {"Transferência"}
SAIDAS = {"Retirada", "Pagamento CC"}
# FII negociado em balcao: paga rendimento mas nao vem no Open Finance
FII_BALCAO: set[str] = set()
NOMES = {"FUNDO INVESTBACK": "Fundo Investback", "BTC ITSA4": "Aluguel ITSA4"}


def le_movimentos(eng) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO, f.VL_SALDO_MOMENTO, f.DS_TIPO_FLUXO, f.SK_LANCAMENTO,
               k.NM_CATEGORIA, k.DS_GRUPO, a.CD_ATIVO, a.DS_CLASSE_ATIVO, f.DS_DETALHE_ORIGINAL
          FROM gold.fato_investimento f
          JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
          JOIN gold.dim_categoria_investimento k ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
          JOIN gold.dim_ativo a ON a.SK_ATIVO = f.SK_ATIVO
    """, eng)


def le_posicao(eng) -> pd.DataFrame:
    # taxa contratada e rentabilidade 12m so existem no bronze
    return pd.read_sql("""
        SELECT c.DT_DATA, p.CD_ATIVO_ORIGEM, p.NM_ATIVO_ORIGEM, p.DS_SUBTIPO, a.DS_CLASSE_ATIVO,
               p.VL_BRUTO, p.VL_LIQUIDO, p.VL_APLICADO, p.DT_VENCIMENTO,
               b.vl_taxa, b.ds_tipo_taxa, b.vl_rentab_12m
          FROM gold.fato_posicao_investimento p
          JOIN gold.dim_calendario c ON c.SK_DATA = p.SK_DATA
          JOIN gold.dim_ativo a ON a.SK_ATIVO = p.SK_ATIVO
          LEFT JOIN bronze.xp_posicao b ON b.hash_negocio = p.HASH_NEGOCIO
         WHERE p.DS_SITUACAO = 'ACTIVE' AND p.VL_BRUTO > 0
    """, eng)


def classe_posicao(r) -> str:
    c, s = r.DS_CLASSE_ATIVO, r.DS_SUBTIPO
    if c == "Fundos Imobiliários" or s == "REAL_ESTATE_FUND" or "FII" in r.NM_ATIVO_ORIGEM:
        return "fii"
    if c == "Renda Variável":
        return "acoes"
    if s in ("CDB", "LCA", "TREASURY"):
        return "rf"
    if s == "FIXED_INCOME_FUND" or "FIRF" in r.NM_ATIVO_ORIGEM or " RF " in r.NM_ATIVO_ORIGEM:
        return "fundo_rf"
    if s == "STOCK_FUND" or " CIA " in r.NM_ATIVO_ORIGEM or "FIA" in r.NM_ATIVO_ORIGEM:
        return "fundo_acoes"
    return "multi"


def tipo_provento(r) -> str:
    if r.NM_CATEGORIA == "Investback":
        return "investback"
    if r.NM_CATEGORIA == "Taxa de Remuneração" or r.DS_CLASSE_ATIVO == "Empréstimo de Ativos":
        return "btc"
    cd = r.CD_ATIVO
    if r.DS_CLASSE_ATIVO == "Fundos Imobiliários" or cd.startswith("Valora") or cd in FII_BALCAO:
        return "fii"
    if r.DS_CLASSE_ATIVO == "Renda Variável":
        return "acoes"
    return "rf"   # juros de LCA, cupom de COE, Tesouro


def nome_curto(n: str) -> str:
    n = n.replace(" RL", "").replace(" S.A.", "").replace(" S/A", "").replace(" S.A", "")
    for a, b in [("CDB - ", "CDB "), ("LCA - ", "LCA "), (" SOCIEDADE DE CREDITO, FINANCIAMENTO E INVESTIMENTOS", ""),
                 ("- CREDITO, FINANCIAMENTO E INVESTIMENTO", ""), ("BANCO ", "")]:
        n = n.replace(a, b)
    return " ".join(n.split()).strip(" -")


def despesa_referencia(eng) -> dict:
    """Despesa media e custo fixo dos ultimos 12 meses, com a regua do painel financeiro."""
    df = fin.le(eng)
    t = df.apply(fin.classifica, axis=1, result_type="expand")
    df["tipo"], df["classe"] = t[0], t[1]
    df["mes"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m")
    v = df["VL_TRANSACAO"].astype(float)
    df["valor"] = v.abs()
    df.loc[df["classe"] == "reembolso", "valor"] = -v.abs()
    df["grupo"] = df["NM_GRUPO"].str.strip().map(lambda g: g.capitalize() if g.isupper() and len(g) > 3 else g)
    meses = sorted(df["mes"].unique())[-12:]
    d = df[(df["tipo"] == "D") & df["mes"].isin(meses) & ~df["grupo"].isin(fin.GRUPOS_BEM)]
    despesa = d["valor"].sum() / len(meses)
    g = d[d["classe"] != "reembolso"].groupby("grupo").agg(v=("valor", "sum"), ms=("mes", "nunique"))
    fixos = g[(g["ms"] >= -(-0.75 * len(meses) // 1)) & (g["v"] / len(meses) >= 30)]
    return {"despesa": round(despesa, 2), "fixo": round(fixos["v"].sum() / len(meses), 2),
            "meses": [meses[0], meses[-1]]}


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    mv = le_movimentos(eng)
    mv["data"] = pd.to_datetime(mv["DT_DATA"])
    mv["mes"] = mv["data"].dt.strftime("%Y-%m")
    v = mv["VL_TRANSACAO"].astype(float)
    mv["v"] = v

    ent = mv["NM_CATEGORIA"].isin(ENTRADAS)
    sai = mv["NM_CATEGORIA"].isin(SAIDAS) | ((mv["NM_CATEGORIA"] == "Pagamento") & (v < 0))
    prov = mv["DS_GRUPO"] == "Proventos"
    cus = mv["DS_GRUPO"] == "Custos"
    mv["tp"] = mv[prov].apply(tipo_provento, axis=1) if prov.any() else None

    # ---- serie mensal: entradas, saidas, proventos por tipo, custos
    meses = pd.period_range(mv["data"].min(), mv["data"].max(), freq="M").strftime("%Y-%m").tolist()
    TIPOS = ["fii", "acoes", "rf", "btc", "investback"]
    serie = []
    for m in meses:
        x = mv[mv["mes"] == m]
        p = x[prov[x.index]]
        serie.append([m, round(x.loc[ent[x.index], "v"].sum(), 2), round(-x.loc[sai[x.index], "v"].sum(), 2),
                      *[round(p.loc[p["tp"] == t, "v"].sum(), 2) for t in TIPOS],
                      round(-x.loc[cus[x.index], "v"].sum(), 2)])

    # janela de 12 meses de CALENDARIO (a mesma da serie mensal), para que
    # a media do topo, a tabela por ativo e o aporte somem o mesmo periodo
    ini12, ini3 = pd.Timestamp(meses[-12] + "-01"), pd.Timestamp(meses[-3] + "-01")

    # ---- posicao: ultimo dia e o dia do ultimo lancamento
    ps = le_posicao(eng)
    ps["data"] = pd.to_datetime(ps["DT_DATA"])
    ps["classe"] = ps.apply(classe_posicao, axis=1)
    diaria = ps.groupby("data")["VL_BRUTO"].sum()
    hoje = ps["data"].max()
    ult_mov = mv["data"].max()
    dia_foto = ps.loc[ps["data"] <= ult_mov, "data"].max() if (ps["data"] <= ult_mov).any() else ps["data"].min()

    def carteira(dia):
        c = ps[ps["data"] == dia].copy()
        return c.sort_values("VL_BRUTO", ascending=False)

    cart = carteira(hoje)
    ativos = [{"nome": nome_curto(r.NM_ATIVO_ORIGEM), "cd": r.CD_ATIVO_ORIGEM, "classe": r.classe,
               "bruto": round(float(r.VL_BRUTO), 2), "liq": round(float(r.VL_LIQUIDO), 2),
               "aplic": None if pd.isna(r.VL_APLICADO) else round(float(r.VL_APLICADO), 2),
               "venc": None if pd.isna(r.DT_VENCIMENTO) else str(r.DT_VENCIMENTO)[:10],
               "taxa": None if pd.isna(r.vl_taxa) else f"{float(r.vl_taxa):g}% {r.ds_tipo_taxa or ''}".strip(),
               "r12": None if pd.isna(r.vl_rentab_12m) else float(r.vl_rentab_12m)}
              for r in cart.itertuples()]

    # ---- fora do Open Finance: COE e FII de balcao, pelo custo de compra
    fora = []
    coe = mv[(mv["NM_CATEGORIA"] == "Compra") & mv["DS_DETALHE_ORIGINAL"].str.contains("COE", na=False)]
    for r in coe.itertuples():
        nome = r.DS_DETALHE_ORIGINAL.replace("Compra de ", "").replace("COMPRA ", "").strip()
        fora.append({"nome": nome, "classe": "coe", "custo": round(-r.v, 2), "data": r.data.strftime("%Y-%m-%d")})
    for cd in sorted(FII_BALCAO):
        c = mv[(mv["CD_ATIVO"] == cd) & (mv["NM_CATEGORIA"] == "Compra")]
        p12 = mv[(mv["CD_ATIVO"] == cd) & prov & (mv["data"] >= ini12)]["v"].sum()
        ult = mv.loc[(mv["CD_ATIVO"] == cd) & prov, "data"].max()
        if pd.isna(ult) or ult < ult_mov - pd.DateOffset(days=60):
            continue   # parou de pagar: ja saiu da carteira
        fora.append({"nome": NOMES.get(cd, cd), "classe": "fii",
                     "custo": round(-c["v"].sum(), 2) if len(c) else None,
                     "data": c["data"].min().strftime("%Y-%m-%d") if len(c) else None, "prov12": round(p12, 2)})
    fora_custo = sum(f["custo"] or 0 for f in fora)

    # ---- resultado estimado: patrimonio do app + tudo que saiu - tudo que entrou.
    # Sem a foto do app, cai para posicao Open Finance + caixa + fora ao custo
    # na data do ultimo lancamento (e vira piso, porque falta o resto).
    app = json.loads(APP.read_text(encoding="utf-8")) if APP.exists() else None
    caixa = float(mv.sort_values(["data", "SK_LANCAMENTO"]).iloc[-1]["VL_SALDO_MOMENTO"])
    pos_foto = float(diaria.get(dia_foto, 0.0))
    entradas, saidas = float(mv.loc[ent, "v"].sum()), float(-mv.loc[sai, "v"].sum())
    if app:
        base = float(app["total"])
    else:
        base = pos_foto + caixa + fora_custo
    resultado = base + saidas - entradas

    # ---- proventos 12m por ativo, e se ainda esta na carteira
    jan = mv[prov & (mv["data"] >= ini12)]
    codigos = {c for c in cart["CD_ATIVO_ORIGEM"] if len(c) > 4}
    detalhes = mv[prov].groupby("CD_ATIVO")["DS_DETALHE_ORIGINAL"].apply(" ".join)
    def na_carteira(cd: str) -> bool:
        # ticker igual, ou o codigo do titulo citado no historico ("Pgto Juros 25C04602211")
        if cd in FII_BALCAO or cd.startswith("COE") or cd in codigos or cd.replace("BTC ", "") in codigos:
            return True
        return any(c in detalhes.get(cd, "") for c in codigos)
    pag = jan[jan["tp"] != "investback"].copy()
    pag["v3"] = pag["v"].where(pag["data"] >= ini3, 0.0)
    pagadores = pag.groupby(["CD_ATIVO", "tp"])[["v", "v3"]].sum().reset_index().sort_values("v", ascending=False)
    pagadores["ativo"] = pagadores["CD_ATIVO"].map(na_carteira)

    # ---- custos por ano, aporte liquido 12m
    mv["ano"] = mv["data"].dt.year
    custos_ano = mv[cus].groupby(["ano", "NM_CATEGORIA"])["v"].sum().unstack(fill_value=0).round(2)
    ap12 = mv[(ent | sai) & (mv["data"] >= ini12)]["v"].sum()

    ref = despesa_referencia(eng)

    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "tipos": TIPOS, "serie": serie,
        "hoje": hoje.strftime("%Y-%m-%d"), "foto": dia_foto.strftime("%Y-%m-%d"), "ult_mov": ult_mov.strftime("%Y-%m-%d"),
        "diaria": [[d.strftime("%Y-%m-%d"), round(float(x), 2)] for d, x in diaria.items()],
        "ativos": ativos, "fora": fora,
        "resultado": {"base": round(base, 2), "pos": round(pos_foto, 2), "caixa": round(caixa, 2), "fora": round(fora_custo, 2),
                      "entradas": round(entradas, 2), "saidas": round(saidas, 2), "valor": round(resultado, 2)},
        "app": app, "of_hoje": round(float(diaria[hoje]), 2),
        "pagadores": [[NOMES.get(r.CD_ATIVO, r.CD_ATIVO), r.tp, round(r.v, 2), round(r.v3, 2), bool(r.ativo)] for r in pagadores.itertuples()],
        "custos_ano": {str(a): {k: float(x) for k, x in linha.items() if x} for a, linha in custos_ano.iterrows()},
        "aporte12": round(float(ap12), 2),
        "ref": ref, "n_mov": int(len(mv)), "ini": mv["data"].min().strftime("%Y-%m-%d"),
    }

    # conferencia no terminal
    print(f"{len(mv)} movimentos de {dados['ini']} a {dados['ult_mov']}; posicao {dados['foto']} e {dados['hoje']}")
    print(f"entradas {entradas:,.2f}  saidas {saidas:,.2f}  liquido {entradas - saidas:,.2f}")
    print(f"patrimonio base {base:,.2f} ({'app ' + app['data'] if app else 'open finance'}) -> resultado {resultado:,.2f}")
    print(f"posicao hoje {diaria[hoje]:,.2f}; aporte liquido 12m {ap12:,.2f}")
    print(cart.groupby("classe")["VL_BRUTO"].sum().round(0).to_string())
    print(pd.DataFrame(fora).to_string())
    s = pd.DataFrame(serie, columns=["mes", "ent", "sai", *TIPOS, "custo"])
    s["ano"] = s["mes"].str[:4]
    print(s.groupby("ano")[["ent", "sai", *TIPOS, "custo"]].sum().round(0).to_string())
    print(pagadores.head(15).to_string())
    print("referencia financas:", ref)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.carimba(html, mzo.atualizacao(eng, ['fato_investimento', 'fato_posicao_investimento']))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
