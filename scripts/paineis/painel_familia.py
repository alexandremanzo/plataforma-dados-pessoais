"""
Painel da conta familia, em HTML offline.

Le gold.fato_familia (so SELECT): aportes de Ale e Lia na conta
conjunta (receita) e os gastos da casa (despesa), pagos pela conta ou
direto do bolso de cada um. O HTML recorta tudo por periodo.

Regras combinadas com o dono dos dados:

  % POR PESSOA sai do que cada um depositou de fato (os aportes), e
  nao de uma regra. O simulador divide o total na mesma proporcao (os
  depositos de cada um nos meses da base, calculada no HTML) para dizer
  quanto cada um deveria depositar.

  A PAGAR = tudo que esta com FL_PAGO = N, passado ou futuro. Os
  lancamentos passados nao pagos contam como em aberto; o painel lista
  os vencidos para conferencia.

  Resort e um empreendimento de ferias ficticio (lancamentos "Resort ..."):
  corretagem, sinal, saldo, taxas e condominio.

  ENTRADA DO APARTAMENTO (#Apartamento fora do financiamento, 2024)
  e despesa, mas vem marcada: o HTML tem uma chave para tira-la e ver
  o padrao do dia a dia, como a compra de bem no painel de financas.

Saida site/painel-familia.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_familia.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_familia.html")
SAIDA = RAIZ / "site" / "painel-familia.html"

PROJETOS_APTO = {"#Apartamento": "Compra do apartamento", "#Reforma": "Reforma da cozinha"}


def le(eng) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO, f.DS_TIPO_FLUXO, f.FL_PAGO, f.FL_FUTURO,
               p.NM_PESSOA, a.NM_AREA, k.NM_CATEGORIA, g.NM_GRUPO, t.NM_TAG, t.DS_TIPO AS DS_TIPO_TAG,
               f.DS_DETALHE_ORIGINAL
          FROM gold.fato_familia f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_pessoa p           ON p.SK_PESSOA = f.SK_PESSOA
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          LEFT JOIN gold.dim_tag t         ON t.SK_TAG = f.SK_TAG
    """, eng)


def tipo_gav(det: str) -> str | None:
    """Parte do Resort pelo texto do lancamento; None quando nao e Resort."""
    if not isinstance(det, str) or not det.upper().startswith("RESORT"):
        return None
    d = det.lower()
    for chave, nome in (("corretagem", "Corretagem"), ("sinal", "Sinal"), ("saldo", "Saldo"),
                        ("taxa", "Taxas"), ("condom", "Condomínio")):
        if chave in d:
            return nome
    return "Outros"


def projeto(r) -> str | None:
    if r.NM_TAG in PROJETOS_APTO:
        return PROJETOS_APTO[r.NM_TAG]
    if r.DS_TIPO_TAG == "Viagem":
        # "Viagem03_Praia" -> "Praia (03)"; "#Serra_Jul22" -> "Serra Jul22"
        m = re.match(r"Viagem(\d+)_(.+)", r.NM_TAG)
        return "Viagem · " + (f"{m.group(2)} ({m.group(1)})" if m else r.NM_TAG.lstrip("#").replace("_", " ").replace("-", " "))
    if r.resort:
        return "Resort Vale Azul"
    return None


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    df = le(eng)
    df = df[df["VL_TRANSACAO"].fillna(0) != 0].copy()
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    df["resort"] = df["DS_DETALHE_ORIGINAL"].map(tipo_gav)
    df["cat"] = df["NM_CATEGORIA"].str.strip().str.capitalize()
    df.loc[df["resort"].notna(), "cat"] = "Resort"
    df["grupo"] = df["NM_GRUPO"].str.strip()
    df.loc[df["resort"].notna(), "grupo"] = df["resort"]
    df["proj"] = df.apply(projeto, axis=1)
    # a entrada do apartamento (tudo de #Apartamento que nao e parcela do financiamento)
    df["entrada"] = ((df["NM_TAG"] == "#Apartamento") & (df["grupo"] != "Financiamento")
                     & (df["DS_TIPO_FLUXO"] == "DESPESA")).astype(int)
    df["essencial"] = (df["NM_AREA"] == "GASTOS ESSENCIAIS").astype(int)
    pessoa = df["NM_PESSOA"].map({"ALE": "Ale", "LIA": "Lia", "Conta": "Conta"}).fillna("Outros")
    df["pessoa"] = pessoa

    pessoas = ["Ale", "Lia", "Conta", "Outros"]
    cats = sorted(df["cat"].unique())
    grupos = sorted(df["grupo"].unique())
    projs = sorted(df["proj"].dropna().unique())
    ip, ic, ig, ij = ({x: i for i, x in enumerate(v)} for v in (pessoas, cats, grupos, projs))
    # [data, valor (receita +, despesa -), pessoa, cat, grupo, pago, futuro, essencial, entrada, projeto]
    linhas = [[r.data, round(float(r.VL_TRANSACAO), 2), ip[r.pessoa], ic[r.cat], ig[r.grupo],
               1 if r.FL_PAGO == "S" else 0, 1 if r.FL_FUTURO == "S" else 0, r.essencial, r.entrada,
               ij[r.proj] if isinstance(r.proj, str) else -1]
              for r in df.sort_values("data").itertuples()]

    # aporte de hoje: o ultimo mes com aporte dos dois
    ap = df[(df["DS_TIPO_FLUXO"] == "RECEITA") & df["pessoa"].isin(["Ale", "Lia"])]
    ap = ap[ap["data"] <= pd.Timestamp.now().strftime("%Y-%m-%d")]
    ult = ap["data"].str[:7].max()
    aporte_atual = ap[ap["data"].str[:7] == ult].groupby("pessoa")["VL_TRANSACAO"].sum().round(2).to_dict()

    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "hoje": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "pessoas": pessoas, "cats": cats, "grupos": grupos, "projs": projs, "linhas": linhas,
        "aporte_atual": aporte_atual, "aporte_mes": ult,
    }

    # conferencia no terminal
    hoje = dados["hoje"]
    print(f"{len(df)} lançamentos de {df['data'].min()} a {df['data'].max()} (hoje {hoje})")
    print(df.groupby(["DS_TIPO_FLUXO", "pessoa"])["VL_TRANSACAO"].sum().round(0).to_string())
    g = df[df["resort"].notna()]
    print(f"\nResort pago {-g[g['FL_PAGO'] == 'S']['VL_TRANSACAO'].sum():,.2f} | a pagar {-g[g['FL_PAGO'] == 'N']['VL_TRANSACAO'].sum():,.2f}"
          f" ({(g['FL_PAGO'] == 'N').sum()} lançamentos, até {g['data'].max()})")
    aberto = df[(df["FL_PAGO"] == "N") & (df["DS_TIPO_FLUXO"] == "DESPESA")]
    print(f"A pagar total {-aberto['VL_TRANSACAO'].sum():,.2f}; vencido (antes de hoje) {-aberto[aberto['data'] < hoje]['VL_TRANSACAO'].sum():,.2f}")
    print(f"Entrada do apartamento: {-df[df['entrada'] == 1]['VL_TRANSACAO'].sum():,.2f} "
          f"{df[df['entrada'] == 1].groupby('grupo')['VL_TRANSACAO'].sum().round(0).to_dict()}")
    print(f"Aporte atual ({ult}): {aporte_atual}")
    print("Projetos:", df.dropna(subset=["proj"]).groupby("proj")["VL_TRANSACAO"].sum().round(0).sort_values().head(12).to_dict())

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.carimba(html, mzo.atualizacao(eng, ['fato_familia']))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
