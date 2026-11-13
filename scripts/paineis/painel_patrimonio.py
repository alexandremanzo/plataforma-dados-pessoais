"""
Painel de patrimonio liquido, em HTML offline.

Junta tres paineis que hoje mostram pedacos do mesmo numero, chamando o
gera() de cada um (so SELECT), e le gold.fato_movto_financ para renda e
gasto. Nada novo e gravado no banco.

Regras, combinadas com o dono dos dados:

  PATRIMONIO LIQUIDO = investimentos - parcelas em aberto no cartao -
  o que a familia ainda tem a pagar.

  INVESTIMENTOS e o mesmo total do painel de investimentos: a foto do
  app da XP (data/xp_posicao_app.json) ou, sem ela, posicao + caixa +
  COE/FII ao custo. So XP: previdencia e cofrinho ficam fora, como la.

  CARTAO EM ABERTO e a regra do painel de cartao: parcelas ja
  contratadas com fatura depois do mes de hoje.

  FAMILIA A PAGAR e a regra do painel de familia: tudo com FL_PAGO = N.
  Separado em compromissos a vencer (financiamento do apartamento e
  Resort), contas ja lancadas (condominio, luz, diarista, IPTU) e vencidos nao
  pagos (data passada: parcela prevista do Resort ao lado da paga,
  financiamento em dobro). Os vencidos contam por padrao, como na
  familia; o HTML tem uma chave para ignora-los. A conta e da casa: a visao
  padrao conta so a PARTE DO ALE, na proporcao dos depositos de Ale e
  Lia nos ultimos 12 meses (a mesma do simulador da familia); a visao
  "casa inteira" conta 100%. Os investimentos sao so do Ale nas duas.

  HISTORICO (estimado). O banco nao guarda o valor de mercado da
  carteira mes a mes. O custo acumulado sai do extrato (entradas -
  saidas + proventos - custos); a diferenca para o total de hoje e o
  ganho de mercado, distribuido pelo capital-mes (cada mes recebe a
  fatia proporcional ao custo que estava investido). A divida do cartao
  em cada mes e exata (parcelas compradas ate o mes com fatura depois
  dele). A da familia conta os compromissos com data depois do mes, a
  partir do primeiro lancamento de cada um; as contas lancadas so
  entram no mes de hoje.

  RENDA e GASTO seguem o painel de financas: renda = salario +
  extraordinaria + outras; gasto = despesa sem compra de bem.
  TAXA DE POUPANCA = aporte liquido na XP / renda.

Saida site/painel-patrimonio.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_patrimonio.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402
import mzo  # noqa: E402
import painel_cartao  # noqa: E402
import painel_familia  # noqa: E402
import painel_financas as fin  # noqa: E402
import painel_investimentos  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_patrimonio.html")
SAIDA = RAIZ / "site" / "painel-patrimonio.html"

INICIO_RENDA = 20210101    # renda x gasto; antes de 2024 a classificacao e mais grosseira


def le_financ(eng) -> pd.DataFrame:
    """Renda e gasto mensais com a regua do painel de financas, desde 2021."""
    df = pd.read_sql(f"""
        SELECT c.DT_DATA, f.VL_TRANSACAO, f.DS_TIPO_FLUXO, a.NM_AREA, k.NM_CATEGORIA,
               g.NM_GRUPO, g.DS_COMPRESSIBILIDADE
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
         WHERE f.DS_NIVEL = 'ANALITICO' AND f.SK_DATA >= {INICIO_RENDA}
    """, eng)
    t = df.apply(fin.classifica, axis=1, result_type="expand")
    df["tipo"], df["classe"] = t[0], t[1]
    v = df["VL_TRANSACAO"].astype(float)
    df["valor"] = v.abs()
    df.loc[df["classe"] == "reembolso", "valor"] = -v.abs()
    df.loc[(df["tipo"] == "R") & (v < 0), "valor"] = v
    df["bem"] = df["NM_GRUPO"].str.strip().isin(fin.GRUPOS_BEM)
    df["mes"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m")
    return df


def soma_mes(m: str, n: int) -> str:
    return (pd.Period(m, freq="M") + n).strftime("%Y-%m")


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    with contextlib.redirect_stdout(io.StringIO()):
        _, inv = painel_investimentos.gera()
        _, car = painel_cartao.gera()
        _, fam = painel_familia.gera()
    hoje = pd.Timestamp.now().normalize()
    mes_hoje = hoje.strftime("%Y-%m")

    # ---- investimentos: custo acumulado pelo extrato, ganho distribuido pelo capital-mes
    s = pd.DataFrame(inv["serie"], columns=["mes", "ent", "sai", *inv["tipos"], "custo"]).set_index("mes")
    s["prov"] = s[inv["tipos"]].sum(axis=1)
    meses = pd.period_range(s.index.min(), mes_hoje, freq="M").strftime("%Y-%m").tolist()
    s = s.reindex(meses, fill_value=0.0)
    s["fluxo"] = s["ent"] - s["sai"]
    s["custo_acum"] = (s["fluxo"] + s["prov"] - s["custo"]).cumsum()
    base = float(inv["app"]["total"]) if inv.get("app") else float(inv["resultado"]["base"])
    ganho = base - float(s["custo_acum"].iloc[-1])
    peso = s["custo_acum"].clip(lower=0).cumsum()
    s["ganho"] = ganho * peso / peso.iloc[-1]
    s["valor"] = s["custo_acum"] + s["ganho"]

    # ---- cartao: em aberto ao fim de cada mes (exato), e o calendario do que vai cair
    cl = pd.DataFrame(car["linhas"], columns=["data", "defasa", "gasto", "cartao", "cat", "grupo", "classe",
                                              "parc", "ntot", "compra", "receb", "tag"])
    cl["mc"] = cl["data"].str[:7]
    cl["fatura"] = (pd.PeriodIndex(cl["mc"], freq="M") + cl["defasa"].values).astype(str)
    parc = cl[cl["parc"] > 0]
    ultimo_fut = max(parc["fatura"].max(), mes_hoje)
    cartao_aberto = {m: float(parc.loc[(parc["mc"] <= m) & (parc["fatura"] > m), "gasto"].sum()) for m in meses}
    # contratado no mes = a parte que fica para faturas seguintes
    cartao_novo = parc[parc["fatura"] > parc["mc"]].groupby("mc")["gasto"].sum()
    cartao_fut = parc[parc["fatura"] > mes_hoje].groupby("fatura")["gasto"].sum()
    compras = parc.groupby("compra").agg(ntot=("ntot", "max"), v=("gasto", "sum"), mc=("mc", "first"))
    rec = compras[compras["mc"] >= soma_mes(mes_hoje, -12)]
    ntot_med = float((rec["ntot"] * rec["v"]).sum() / rec["v"].sum()) if len(rec) and rec["v"].sum() else 6.0

    # ---- familia: a pagar (FL_PAGO = N), compromissos x contas lancadas
    fl = pd.DataFrame(fam["linhas"], columns=["data", "valor", "pessoa", "cat", "grupo", "pago", "futuro", "ess", "entrada", "proj"])
    fl["cat_n"] = fl["cat"].map(lambda i: fam["cats"][i])
    fl["grupo_n"] = fl["grupo"].map(lambda i: fam["grupos"][i])
    fl["mes"] = fl["data"].str[:7]
    fl["comp"] = (fl["grupo_n"] == "Financiamento") | (fl["cat_n"] == "Resort")
    desp = fl[fl["valor"] < 0].copy()
    desp["v"] = -desp["valor"]
    aberto = desp[desp["pago"] == 0]
    # chave do compromisso: o financiamento e cada parte do Resort
    desp["chave"] = desp["cat_n"] + "|" + desp["grupo_n"]
    inicio_comp = desp[desp["comp"]].groupby("chave")["data"].min()
    comp = desp[desp["comp"]]
    fam_hist = {}
    for m in meses[:-1]:
        fim = soma_mes(m, 1) + "-01"
        ativos = inicio_comp[inicio_comp < fim].index
        fam_hist[m] = float(comp.loc[comp["chave"].isin(ativos) & (comp["data"] >= fim), "v"].sum())
    hoje_iso = hoje.strftime("%Y-%m-%d")
    aberto = aberto.assign(venc=aberto["data"] < hoje_iso)
    fam_comp_hoje = float(aberto.loc[aberto["comp"] & ~aberto["venc"], "v"].sum())
    fam_contas_hoje = float(aberto.loc[~aberto["comp"] & ~aberto["venc"], "v"].sum())
    fam_venc_hoje = float(aberto.loc[aberto["venc"], "v"].sum())
    fam_hist[mes_hoje] = fam_comp_hoje + fam_contas_hoje + fam_venc_hoje
    # o que vai cair em cada mes; vencido (data passada e nao pago) entra no mes de hoje
    aberto = aberto.assign(mq=aberto["mes"].where(aberto["mes"] >= mes_hoje, mes_hoje))
    fam_fut = aberto.groupby("mq")["v"].sum()
    # tipo: 0 compromisso a vencer, 1 conta lancada, 2 vencido nao pago
    aberto = aberto.assign(tipo=aberto["venc"].map({True: 2, False: 0}).where(aberto["venc"] | aberto["comp"], 1))
    detalhe_fam = (aberto.assign(nome=aberto.apply(lambda r: "Resort · " + r.grupo_n if r.cat_n == "Resort" else r.grupo_n, axis=1))
                   .groupby(["nome", "tipo"]).agg(v=("v", "sum"), n=("v", "size"), ate=("data", "max"))
                   .reset_index().sort_values("v", ascending=False))

    # parte do Ale: depositos de Ale e Lia nos ultimos 12 meses (a base padrao do simulador da familia)
    m12 = [soma_mes(mes_hoje, -i) for i in range(11, -1, -1)]
    dep = fl[(fl["valor"] > 0) & (fl["data"] <= hoje.strftime("%Y-%m-%d")) & fl["mes"].isin(m12)]
    a = dep.loc[dep["pessoa"] == fam["pessoas"].index("Ale"), "valor"].sum()
    j = dep.loc[dep["pessoa"] == fam["pessoas"].index("Lia"), "valor"].sum()
    parte_ale = round(float(a / (a + j)), 4) if a + j else 0.5

    # ---- renda e gasto (regua de financas)
    fd = le_financ(eng)
    renda = fd[fd["tipo"] == "R"].groupby("mes")["valor"].sum()
    gasto = fd[(fd["tipo"] == "D") & ~fd["bem"]].groupby("mes")["valor"].sum()
    bem = fd[(fd["tipo"] == "D") & fd["bem"]].groupby("mes")["valor"].sum()
    salario = fd[(fd["tipo"] == "R") & (fd["classe"] == "salario")].groupby("mes")["valor"].sum()
    meses_r = pd.period_range("2021-01", mes_hoje, freq="M").strftime("%Y-%m").tolist()

    r2 = lambda v: round(float(v), 2)
    # [mes, investido (estimado), custo acumulado, aporte liquido, proventos, custos, ganho no mes,
    #  cartao em aberto, cartao contratado no mes, familia a pagar (100%)]
    linhas = []
    g_ant = 0.0
    for m in meses:
        r = s.loc[m]
        linhas.append([m, r2(r["valor"]), r2(r["custo_acum"]), r2(r["fluxo"]), r2(r["prov"]), r2(r["custo"]),
                       r2(r["ganho"] - g_ant), r2(cartao_aberto[m]), r2(cartao_novo.get(m, 0.0)), r2(fam_hist[m])])
        g_ant = r["ganho"]
    fluxo_mes = s["fluxo"]
    # [mes, renda, salario, gasto sem bem, compra de bem, aporte liquido XP]
    renda_gasto = [[m, r2(renda.get(m, 0)), r2(salario.get(m, 0)), r2(gasto.get(m, 0)), r2(bem.get(m, 0)),
                    r2(fluxo_mes.get(m, 0))] for m in meses_r]

    fut_meses = pd.period_range(soma_mes(mes_hoje, 1), max(ultimo_fut, fam_fut.index.max(), soma_mes(mes_hoje, 1)),
                                freq="M").strftime("%Y-%m").tolist()
    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"), "hoje": hoje.strftime("%Y-%m-%d"), "mes_hoje": mes_hoje,
        "linhas": linhas, "renda_gasto": renda_gasto,
        "hoje_v": {"invest": r2(base), "invest_fonte": ("app da XP em " + pd.Timestamp(inv["app"]["data"]).strftime("%d/%m/%Y"))
                   if inv.get("app") else "Open Finance + caixa + COE/FII ao custo",
                   "custo": r2(s["custo_acum"].iloc[-1]), "ganho": r2(ganho),
                   "cartao": r2(cartao_aberto[mes_hoje]), "fam_comp": r2(fam_comp_hoje), "fam_contas": r2(fam_contas_hoje),
                   "fam_venc": r2(fam_venc_hoje)},
        "parte_ale": parte_ale,
        "fam_detalhe": [[r.nome, int(r.tipo), r2(r.v), int(r.n), r.ate] for r in detalhe_fam.itertuples()],
        # o que cai em cada mes a partir de hoje: [mes, cartao, familia 100%]
        "futuro": [[mes_hoje, 0.0, r2(fam_fut.get(mes_hoje, 0.0))]]
                  + [[m, r2(cartao_fut.get(m, 0.0)), r2(fam_fut.get(m, 0.0))] for m in fut_meses],
        "ntot_med": round(ntot_med, 1),
    }

    # conferencia no terminal
    print(f"Investimentos {base:,.2f} ({dados['hoje_v']['invest_fonte']}); custo acumulado {s['custo_acum'].iloc[-1]:,.2f}; ganho {ganho:,.2f}")
    print(f"Cartão em aberto {cartao_aberto[mes_hoje]:,.2f} (painel do cartão: "
          f"{float(cl.loc[(cl['fatura'] > mes_hoje) & (cl['parc'] > 0), 'gasto'].sum()):,.2f}); parcelas médias {ntot_med:.1f}")
    print(f"Família a pagar {fam_hist[mes_hoje]:,.2f} = compromissos {fam_comp_hoje:,.2f} + contas {fam_contas_hoje:,.2f} + vencidos {fam_venc_hoje:,.2f}"
          f" (painel da família: {-fl.loc[(fl['pago'] == 0) & (fl['valor'] < 0), 'valor'].sum():,.2f}); parte do Ale {parte_ale:.1%}")
    pl_ale = base - cartao_aberto[mes_hoje] - parte_ale * fam_hist[mes_hoje]
    pl_casa = base - cartao_aberto[mes_hoje] - fam_hist[mes_hoje]
    print(f"PL (parte do Ale) {pl_ale:,.2f} | PL (casa inteira) {pl_casa:,.2f}")
    print(detalhe_fam.to_string())
    rg = pd.DataFrame(renda_gasto, columns=["mes", "renda", "sal", "gasto", "bem", "aporte"])
    rg["ano"] = rg["mes"].str[:4]
    print(rg.groupby("ano")[["renda", "sal", "gasto", "bem", "aporte"]].sum().round(0).to_string())
    print(pd.DataFrame(linhas, columns=["mes", "valor", "custo", "aporte", "prov", "custos", "ganho", "car", "car_novo", "fam"])
          .iloc[::6].round(0).to_string())

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    html = mzo.carimba(html, mzo.atualizacao(eng, ["fato_investimento", "fato_posicao_investimento", "fato_movto_financ", "fato_familia"]))
    return html, dados


def main() -> int:
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
