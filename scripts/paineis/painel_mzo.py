"""
MZO Analytics: os oito paineis num arquivo so, com menu lateral.

Roda o gera() de cada painel (saude, familia, financas, patrimonio, investimentos,
cartao, carro, viagens),
tira um resumo de cada um para a pagina inicial e embute os HTMLs como
JSON. O shell cria um iframe por painel quando ele e aberto pela
primeira vez: cada painel fica isolado (CSS, ids, scripts) e desenha os
graficos ja visivel, com a largura certa.

Saida site/index.html: e a pagina que o GitHub Pages publica. Na
demonstracao, todos os numeros saem de dados ficticios (demo/gera_dados.py).

Uso:
    python scripts/paineis/painel_mzo.py
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

import mzo  # noqa: E402
import painel_carro  # noqa: E402
import painel_familia  # noqa: E402
import painel_cartao  # noqa: E402
import painel_financas  # noqa: E402
import painel_investimentos  # noqa: E402
import painel_patrimonio  # noqa: E402
import painel_saude  # noqa: E402
import painel_viagens  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("painel_mzo.html")
SAIDA = RAIZ / "site" / "index.html"

# Dentro do hub a marca de cada painel some (o logo esta na barra lateral)
# e os links de secao rolam dentro do iframe em vez de navegar.
EMBUTE_CSS = "<style>.barra-topo .marca{display:none}.barra-topo{justify-content:flex-end}</style>"
EMBUTE_JS = """<script>document.addEventListener('click',function(e){var a=e.target.closest('a[href^="#"]');if(!a)return;
var t=document.getElementById(a.getAttribute('href').slice(1));if(!t)return;e.preventDefault();
t.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});</script>"""


def ok(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def resumo_saude(d: dict) -> dict:
    av = [a for a in d["avaliacoes"] if a["nr"] >= 17]
    g = [(a["data"], a["gordura"]) for a in av if ok(a["gordura"])]
    m = [(a["data"], a["musculo"]) for a in av if ok(a["musculo"])]
    gk = [(a["data"], a["gordura_kg"]) for a in av if ok(a.get("gordura_kg"))]
    return {
        "principal": {"rot": "% de gordura", "v": g[-1][1], "fmt": "pct1", "delta": g[-1][1] - g[0][1], "bom": "menor",
                      "desde": g[0][0]},
        "kpis": [{"rot": "Gordura", "v": gk[-1][1], "fmt": "kg", "delta": gk[-1][1] - gk[0][1], "bom": "menor"},
                 {"rot": "Massa muscular", "v": m[-1][1], "fmt": "kg", "delta": m[-1][1] - m[0][1], "bom": "maior"}],
        "spark": [v for _, v in g], "spark_rot": "% de gordura em cada avaliação",
        "texto": f"{len(av)} avaliações desde {av[0]['data'][5:7]}/{av[0]['data'][:4]}; a última em {av[-1]['data'][8:]}/{av[-1]['data'][5:7]}.",
    }


def resumo_financas(d: dict) -> dict:
    df = pd.DataFrame(d["linhas"], columns=["data", "valor", "tipo", "classe", "cat", "grupo", "bem", "cartao"])
    df["mes"] = df["data"].str[:7]
    meses = sorted(df["mes"].unique())[-12:]
    x = df[df["mes"].isin(meses)]
    r = x.loc[x["tipo"] == "R", "valor"].sum()
    dsp = x.loc[x["tipo"] == "D", "valor"].sum()
    p = x[x["tipo"].isin(["R", "D"])].pivot_table(index="mes", columns="tipo", values="valor", aggfunc="sum").fillna(0)
    saldo = (p["R"] - p["D"]).reindex(meses, fill_value=0)
    corta = x.loc[x["classe"] == "cortavel", "valor"].sum() / len(meses)
    return {
        "principal": {"rot": "Saldo em 12 meses", "v": float(r - dsp), "fmt": "brl", "sinal": True},
        "kpis": [{"rot": "Receita", "v": float(r), "fmt": "kbrl"}, {"rot": "Despesa", "v": float(dsp), "fmt": "kbrl"},
                 {"rot": "Cortáveis por mês", "v": float(corta), "fmt": "brl"}],
        "spark": [round(float(v), 2) for v in saldo], "spark_rot": "saldo de cada mês",
        "neg": int((saldo < 0).sum()),
        "texto": f"{int((saldo < 0).sum())} de {len(meses)} meses fecharam no vermelho.",
    }


def resumo_investimentos(d: dict) -> dict:
    s = pd.DataFrame(d["serie"], columns=["mes", "ent", "sai", "fii", "acoes", "rf", "btc", "inv", "custo"])
    s["prov"] = s[["fii", "acoes", "rf", "btc"]].sum(axis=1)
    p12 = s["prov"].tail(12).sum()
    patr = d["app"]["total"] if d.get("app") else d["resultado"]["base"]
    return {
        "principal": {"rot": "Patrimônio", "v": float(patr), "fmt": "kbrl",
                      "nota": "app da XP em " + pd.Timestamp(d["app"]["data"] if d.get("app") else d["foto"]).strftime("%d/%m/%Y")},
        "kpis": [{"rot": "Proventos por mês", "v": float(p12 / 12), "fmt": "brl", "nota": "média de 12 meses"},
                 {"rot": "Resultado estimado", "v": float(d["resultado"]["valor"]), "fmt": "kbrl", "sinal": True}],
        "spark": [round(float(v), 2) for v in s["prov"].tail(24)], "spark_rot": "proventos por mês, 24 meses",
        "texto": f"Proventos cobrem {p12 / 12 / d['ref']['fixo']:.0%} do custo fixo da casa.",
    }


def resumo_carro(d: dict) -> dict:
    df = pd.DataFrame(d["custos"], columns=["data", "valor", "balde", "carro"])
    baldes = [b for b, _ in d["baldes"]]
    df["balde"] = df["balde"].map(lambda i: baldes[i])
    # Sedan com a familia e compra de carro ficam fora, como no painel
    fam = (df["carro"] == d["carros"].index("Sedan")) & (df["data"] > d["saida_sedan"])
    df = df[~fam & (df["balde"] != "compra")]
    df["mes"] = df["data"].str[:7]
    meses = sorted(df["mes"].unique())[-24:]
    mes = df[df["mes"].isin(meses)].groupby("mes")["valor"].sum().reindex(meses, fill_value=0)
    m12 = meses[-12:]
    tot = float(mes[m12].sum())
    km = sum(d["km_mes"].get(m, 0) for m in m12)
    plano = [p for p in d["plano"] if p["ult"]]
    return {
        "principal": {"rot": "Custo por mês", "v": tot / 12, "fmt": "brl", "nota": "últimos 12 meses"},
        "kpis": [{"rot": "Custo por km", "v": tot / km if km else None, "fmt": "brl2", "nota": "km estimados"},
                 {"rot": "Combustível por mês", "v": float(df[df["mes"].isin(m12) & (df["balde"] == "combustivel")]["valor"].sum()) / 12,
                  "fmt": "brl"}],
        "spark": [round(float(v), 2) for v in mes], "spark_rot": "custo do carro por mês, 24 meses",
        "texto": f"SUV com ~{d['km']['hoje'] / 1000:.0f} mil km; {len(plano)} itens do plano com data para vencer.",
    }


def resumo_familia(d: dict) -> dict:
    df = pd.DataFrame(d["linhas"], columns=["data", "valor", "pessoa", "cat", "grupo", "pago", "futuro", "ess", "entrada", "proj"])
    hoje = d["hoje"]
    df["mes"] = df["data"].str[:7]
    passado = df[(df["data"] <= hoje) & (df["entrada"] == 0)]
    meses = sorted(passado["mes"].unique())[-24:]
    m12 = meses[-12:]
    u = passado[passado["mes"].isin(m12)]
    desp = -u.loc[u["valor"] < 0, "valor"].sum()
    rec = u.loc[u["valor"] > 0, "valor"].sum()
    ale, lia = (u.loc[(u["valor"] > 0) & (u["pessoa"] == d["pessoas"].index(p)), "valor"].sum() for p in ("Ale", "Lia"))
    gasto = passado[passado["valor"] < 0].groupby("mes")["valor"].sum().reindex(meses, fill_value=0)
    aberto = -df.loc[(df["pago"] == 0) & (df["valor"] < 0), "valor"].sum()
    return {
        "principal": {"rot": "Gasto da casa por mês", "v": float(desp / 12), "fmt": "brl", "nota": "últimos 12 meses"},
        "kpis": [{"rot": "Ale / Lia", "v": float(100 * ale / (ale + lia)) if ale + lia else 0, "fmt": "pct0",
                  "nota": f"{100 * lia / (ale + lia):.0f}% Lia" if ale + lia else ""},
                 {"rot": "A pagar", "v": float(aberto), "fmt": "kbrl", "nota": "lançado e não pago"}],
        "spark": [round(float(-v), 2) for v in gasto], "spark_rot": "gasto da casa por mês, 24 meses",
        "texto": f"Depósitos de {rec / 12:,.0f} por mês contra {desp / 12:,.0f} de gasto em 12 meses.".replace(",", "."),
    }



def resumo_cartao(d: dict) -> dict:
    df = pd.DataFrame(d["linhas"], columns=["data", "defasa", "gasto", "cartao", "cat", "grupo", "classe",
                                            "parc", "ntot", "compra", "receb", "tag"])
    per = pd.PeriodIndex(df["data"].str[:7], freq="M") + df["defasa"].values
    df["fatura"] = per.astype(str)
    mes_hoje = d["hoje"][:7]
    fat = df[df["fatura"] <= mes_hoje].groupby("fatura")["gasto"].sum()
    meses = sorted(fat.index)[-24:]
    m12 = meses[-12:]
    media = float(fat.reindex(m12).mean())
    aberto = float(df.loc[(df["fatura"] > mes_hoje) & (df["parc"] > 0), "gasto"].sum())
    ib = pd.DataFrame(d["investback"], columns=["data", "v"])
    ib12 = float(ib.loc[ib["data"].str[:7].isin(m12), "v"].sum())
    u = df[df["fatura"].isin(m12)]
    cort = float(u.loc[u["classe"] == 2, "gasto"].sum())
    return {
        "principal": {"rot": "Fatura média", "v": media, "fmt": "brl", "nota": "últimos 12 meses"},
        "kpis": [{"rot": "Parcelas em aberto", "v": aberto, "fmt": "kbrl", "nota": "já contratadas"},
                 {"rot": "Investback", "v": ib12, "fmt": "brl", "nota": "em 12 meses"}],
        "spark": [round(float(fat.get(m, 0)), 2) for m in meses], "spark_rot": "fatura por mês, 24 meses",
        "texto": f"{100 * cort / u['gasto'].sum():.0f}% da fatura em gastos cortáveis, R$ {cort / 12:,.0f} por mês.".replace(",", "."),
    }


def resumo_patrimonio(d: dict) -> dict:
    df = pd.DataFrame(d["linhas"], columns=["mes", "inv", "custo", "ap", "prov", "cus", "gan", "car", "car_novo", "fam"])
    h, p = d["hoje_v"], d["parte_ale"]
    # sua parte da casa, contando os vencidos (o padrao do painel)
    df.loc[df["mes"] == d["mes_hoje"], "fam"] = h["fam_comp"] + h["fam_contas"] + h["fam_venc"]
    df["pl"] = df["inv"] - df["car"] - p * df["fam"]
    pl = float(df["pl"].iloc[-1])
    ant = float(df["pl"].iloc[-13]) if len(df) > 12 else None
    rg = pd.DataFrame(d["renda_gasto"], columns=["mes", "renda", "sal", "gasto", "bem", "ap"])
    r12 = rg[rg["mes"] < d["mes_hoje"]].tail(12)
    taxa = float(r12["ap"].sum() / r12["renda"].sum()) if r12["renda"].sum() else None
    div = float(df["car"].iloc[-1] + p * df["fam"].iloc[-1])
    return {
        "principal": {"rot": "Patrimônio líquido", "v": pl, "fmt": "kbrl", "nota": "sua parte da casa",
                      "delta": pl - ant if ant is not None else None, "bom": "maior"},
        "kpis": [{"rot": "Dívidas", "v": div, "fmt": "kbrl", "nota": "cartão + sua parte da casa"},
                 {"rot": "Taxa de poupança", "v": 100 * taxa if taxa is not None else None, "fmt": "pct0", "nota": "12 meses"}],
        "spark": [round(float(v), 2) for v in df["pl"].tail(24)], "spark_rot": "patrimônio líquido por mês, 24 meses (estimado)",
        "texto": f"{div / h['invest']:.0%} dos investimentos já têm destino em parcelas e contas da casa.",
    }


def resumo_viagens(d: dict) -> dict:
    hoje = pd.Timestamp(d["hoje"])
    vs = d["viagens"]
    # custo de viagem por mes de saida, 24 meses
    meses = [p.strftime("%Y-%m") for p in pd.period_range(end=hoje.to_period("M"), periods=24, freq="M")]
    mes = dict.fromkeys(meses, 0.0)
    for v in vs:
        if v["ini"][:7] in mes:
            mes[v["ini"][:7]] += v["custo"]
    u12 = [v for v in vs if pd.Timestamp(v["fim"]) > hoje - pd.Timedelta(days=365)]
    tot = sum(v["custo"] for v in u12)
    dias = sum(v["dias"] for v in u12)
    maior = max(u12, key=lambda v: v["custo"]) if u12 else None
    valor = f"R$ {maior['custo']:,.0f}".replace(",", ".") if maior else ""
    return {
        "principal": {"rot": "Viagens em 12 meses", "v": tot, "fmt": "kbrl", "nota": f"{len(u12)} {'viagem' if len(u12) == 1 else 'viagens'}"},
        "kpis": [{"rot": "Custo por dia", "v": tot / dias if dias else None, "fmt": "brl"},
                 {"rot": "Dias fora", "v": dias, "fmt": "int"}],
        "spark": [round(x, 2) for x in mes.values()], "spark_rot": "custo das viagens por mês de saída, 24 meses",
        "texto": f"A maior foi {maior['nome']}, com {valor}." if maior else "Nenhuma viagem nos últimos 12 meses.",
    }


AREAS = [
    ("saude", "Saúde", "Corpo e hábitos", painel_saude, resumo_saude),
    ("familia", "Família", "A conta da casa", painel_familia, resumo_familia),
    ("financas", "Finanças", "Dinheiro em movimento", painel_financas, resumo_financas),
    ("patrimonio", "Patrimônio", "O que é seu de fato", painel_patrimonio, resumo_patrimonio),
    ("investimentos", "Investimentos", "Carteira que rende", painel_investimentos, resumo_investimentos),
    ("cartao", "Cartão", "Fatura e parcelas", painel_cartao, resumo_cartao),
    ("carro", "Carro", "Custo e manutenção", painel_carro, resumo_carro),
    ("viagens", "Viagens", "Malas e destinos", painel_viagens, resumo_viagens),
]


def embute(html: str) -> str:
    html = html.replace("</head>", EMBUTE_CSS + "</head>", 1)
    return html.replace("</body>", EMBUTE_JS + "</body>", 1)


def main() -> int:
    areas, blocos = [], []
    for chave, nome, sub, mod, resume in AREAS:
        with contextlib.redirect_stdout(io.StringIO()):   # o log de cada painel fica no main dele
            html, dados = mod.gera()
        areas.append({"id": chave, "nome": nome, "sub": sub, "resumo": resume(dados)})
        # "</" escapado para o HTML embutido nao fechar a tag script do hub
        blocos.append(f'<script type="application/json" id="pn-{chave}">'
                      + json.dumps(embute(html), ensure_ascii=False).replace("</", "<\\/") + "</script>")
        print(f"{nome:<15} {len(html) // 1024:>4} KB")

    hub = {"gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"), "areas": areas}
    out = TEMPLATE.read_text(encoding="utf-8")
    out = out.replace("<!--__LOGO__-->", mzo.logo(36, "mzo-lat"))
    out = out.replace("<!--__LOGO_MOB__-->", mzo.logo(28, "mzo-mob"))
    out = out.replace("<!--__SELO__-->", mzo.selo(64, "mzo-hero"))
    out = out.replace("/*__MZO_CSS__*/", mzo.CSS)
    out = out.replace("/*__HUB__*/null", json.dumps(hub, ensure_ascii=False, default=float))
    out = out.replace("<!--__PAINEIS__-->", "\n".join(blocos))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(out, encoding="utf-8")
    print(f"\n{SAIDA}  {len(out) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
