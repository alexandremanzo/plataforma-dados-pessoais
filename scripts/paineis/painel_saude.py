"""
Painel de saude: habitos diarios x avaliacoes fisicas, em HTML offline.

Le o gold (so SELECT), recorta os dias entre cada par de avaliacoes
consecutivas, mede como estavam os habitos em cada periodo e quanto
% de gordura e massa muscular mudaram. Sobre esses periodos calcula
correlacoes e o padrao dos melhores e piores periodos.

O simulador trabalha em COMPOSICAO: peso = massa magra + gordura (kg),
e % de gordura = gordura / peso. Cada habito tem um efeito por mes em
gordura e em massa magra que mistura duas fontes: a fisiologia (conta
de calorias: 7.700 kcal por kg de gordura) como ponto de partida, e a
inclinacao medida nos seus periodos, que pesa tanto quanto a precisao
dela deixa. O ponto de partida e recalibrado para reproduzir o ritmo
medio real desde 2024. (Uma regressao pura foi testada e descartada:
com 17 periodos ela errava mais do que prever a media.)

Tudo vai embutido como JSON no template painel_saude.html; a saida
site/painel-saude.html abre sem internet.

Uso:
    python scripts/paineis/painel_saude.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_saude.html")
SAIDA = RAIZ / "site" / "painel-saude.html"

# Metricas do efeito. "Massa Muscular" (2018+) nunca se mistura com
# "Massa Muscular/Ossea" (ate 2013): sao medidas diferentes.
METRICAS = {
    "gordura": {"sk": 9, "nome": "% de gordura", "unid": "pp", "melhor": "menor"},
    "musculo": {"sk": 2, "nome": "Massa muscular", "unid": "kg", "melhor": "maior"},
}
SK_PESO = 1
SK_GORDURA_KG = 4
# O formulario diario comeca em 2024; avaliacoes antes disso nao tem
# habito para cruzar.
PRIMEIRA_AVALIACAO = 17
COBERTURA_MINIMA = 0.70
REFEICOES_DIA = 5

# Habitos do simulador; plano_pct entra so no diagnostico.
HABITOS = {
    "treino_sem": "Treinos por semana",
    "cardio_sem": "Cardios por semana",
    "agua_l": "Água por dia (L)",
    "jaca_dia": "Refeições jaca por dia",
}
# refeicoes do formulario, na ordem do dia; cada uma e SIM (no plano), JACA ou NAO
REFEICOES = {"cafe": (4, "Café da manhã"), "almoco": (5, "Almoço"), "lanche": (6, "Lanche"),
             "janta": (7, "Janta"), "ceia": (8, "Ceia")}
HABITOS_DIAG = dict(HABITOS, plano_pct="Refeições no plano (%)",
                    **{k + "_pct": f"{nome} no plano (%)" for k, (_, nome) in REFEICOES.items()})
# InBody alem de gordura e musculo: (nome no lake, rotulo, casas, faixa de referencia usual
# do aparelho quando o lake nao traz uma confiavel)
INBODY_EXTRA = [
    ("Gordura Viceral", "Gordura visceral", 0, (1, 9)),
    ("Taxa Metabolica Basal", "Taxa metabólica basal", 0, None),
    ("Agua Corp", "Água corporal", 1, None),
    ("Proteina", "Proteína", 1, None),
    ("Minerais", "Minerais", 2, None),
    ("Relacao Cintura-Quadril", "Relação cintura-quadril", 2, (0.80, 0.90)),
    ("Pontuação Corpo", "Pontuação InBody", 0, (80, 100)),
    ("Massa Livre de Gordura", "Massa livre de gordura", 1, None),
    ("IMC", "IMC", 1, (18.5, 25)),
]

# Efeito de partida de cada habito, por mes, em kg: (media, desvio).
# Gordura pela conta de calorias - cardio ~300 kcal por sessao, treino
# de forca ~200, refeicao jaca ~500 a mais que a do plano, 7.700 kcal
# por kg de gordura; agua sem efeito calorico. Massa magra: treino de
# forca rende pouco em quem ja treina (~0,08 kg/mes por sessao semanal
# a mais); o resto parte de zero. O desvio diz quanto o dado pode puxar.
MES = 30
KCAL_KG = 7700
PRIORI = {
    "g": {"treino_sem": (-200 * MES / 7 / KCAL_KG, 0.08), "cardio_sem": (-300 * MES / 7 / KCAL_KG, 0.10),
          "agua_l": (0.0, 0.15), "jaca_dia": (500 * MES / KCAL_KG, 0.8)},
    "m": {"treino_sem": (0.08, 0.06), "cardio_sem": (0.0, 0.05), "agua_l": (0.0, 0.15), "jaca_dia": (0.0, 0.3)},
}


# ---------------------------------------------------------------- leitura
def le_dias(eng) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT d.SK_DATA, c.DT_DATA, d.VL_AGUA_LITROS, d.FL_META_AGUA, d.FL_TREINO, d.FL_CARDIO,
               d.NR_REFEICOES_FEITAS, d.NR_REFEICOES_JACA, d.DS_DIA_PRODUTIVO, d.FL_TRABALHO,
               d.FL_NINA_EM_CASA, c.FL_FERIADO
          FROM gold.fato_dia d
          JOIN gold.dim_calendario c ON c.SK_DATA = d.SK_DATA
         WHERE d.SK_DATA > 0
    """, eng)
    # resposta de cada refeicao no dia: S (no plano), J (jaca), N (nao fez), - (sem resposta)
    sks = ", ".join(str(sk) for sk, _ in REFEICOES.values())
    ref = pd.read_sql(f"SELECT SK_DATA, SK_HABITO, DS_RESPOSTA FROM gold.fato_dia_habito WHERE SK_HABITO IN ({sks})", eng)
    codigo = {"SIM": "S", "JACA": "J", "NAO": "N"}
    resp = {(r.SK_DATA, r.SK_HABITO): codigo.get(r.DS_RESPOSTA, "-") for r in ref.itertuples()}
    df["refs"] = df["SK_DATA"].map(lambda sk: "".join(resp.get((sk, h), "-") for h, _ in REFEICOES.values()))
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.normalize()
    out = pd.DataFrame({
        "data": df["data"],
        "agua": df["VL_AGUA_LITROS"].astype(float),
        "meta_agua": (df["FL_META_AGUA"] == "S").astype(int),
        "treino": (df["FL_TREINO"] == "S").astype(int),
        "cardio": (df["FL_CARDIO"] == "S").astype(int),
        "feitas": df["NR_REFEICOES_FEITAS"].astype(float),
        "jaca": df["NR_REFEICOES_JACA"].astype(float),
        "refs": df["refs"],
        "produtivo": df["DS_DIA_PRODUTIVO"].map({"SIM": "S", "NAO": "N"}).fillna("O"),
        "trabalho": (df["FL_TRABALHO"] == "S").astype(int),
        "nina": (df["FL_NINA_EM_CASA"] == "S").astype(int),
        "feriado": (df["FL_FERIADO"] == "S").astype(int),
    })
    for i, k in enumerate(REFEICOES):
        r = out["refs"].str[i]
        out[k] = np.where(r == "-", np.nan, (r == "S").astype(float))
    return out.sort_values("data").reset_index(drop=True)


def le_avaliacoes(eng) -> pd.DataFrame:
    df = pd.read_sql(f"""
        SELECT f.NR_AVALIACAO, c.DT_DATA, f.SK_METRICA, f.VL_MEDIDA, f.DS_ORIGEM
          FROM gold.fato_avaliacao_fisica f
          JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
         WHERE f.SK_SEGMENTO = -1 AND f.FL_MEDIDO = 'S'
           AND f.SK_METRICA IN ({SK_PESO}, {SK_GORDURA_KG}, {METRICAS['gordura']['sk']}, {METRICAS['musculo']['sk']})
           AND f.NR_AVALIACAO >= {PRIMEIRA_AVALIACAO}
    """, eng)
    val = df.pivot_table(index=["NR_AVALIACAO", "DT_DATA"], columns="SK_METRICA",
                         values="VL_MEDIDA").reset_index()
    # Avaliacao com alguma linha do exame conta como InBody; so planilha
    # e outro instrumento (ou digitacao), e o periodo que mistura os dois
    # sai marcado.
    origem = df.groupby("NR_AVALIACAO")["DS_ORIGEM"].agg(
        lambda s: "InBody" if (s == "InBody").any() else "Planilha")
    val = val.join(origem, on="NR_AVALIACAO")
    val = val.rename(columns={"NR_AVALIACAO": "nr", "DT_DATA": "data", "DS_ORIGEM": "origem",
                              SK_PESO: "peso", SK_GORDURA_KG: "gordura_kg", METRICAS["gordura"]["sk"]: "gordura",
                              METRICAS["musculo"]["sk"]: "musculo"})
    val["data"] = pd.to_datetime(val["data"]).dt.normalize()
    if "gordura_kg" not in val:
        val["gordura_kg"] = np.nan
    # exame sem a massa de gordura impressa: peso x %, que e como a maquina calcula
    val["gordura_kg"] = val["gordura_kg"].fillna(val["peso"] * val["gordura"] / 100)
    val["magra"] = val["peso"] - val["gordura_kg"]
    return val.sort_values("nr").reset_index(drop=True)


SEGMENTOS = ["Braço esquerdo", "Braço direito", "Tronco", "Perna esquerda", "Perna direita"]
METRICAS_SEG = ["Massa Magra Segmentar", "Gordura Segmentar", "Massa Magra Segmentar %", "Gordura Segmentar %"]
# medidas com fita (so na planilha, 2008-2013), na ordem de cima para baixo
FITA = ["Pescoço", "Ombro", "Tórax", "Braço D", "Braço E", "Antebraço D", "Antebraço E", "Abdomem",
        "Cintura", "Quadril", "Coxa D", "Coxa E", "Perna D", "Perna E"]


def le_membros(eng) -> tuple[dict, dict]:
    """InBody segmentar (braços, tronco, pernas) e as medidas antigas com fita."""
    nomes = ", ".join(f"'{m}'" for m in METRICAS_SEG + FITA)
    df = pd.read_sql(f"""
        SELECT f.NR_AVALIACAO, c.DT_DATA, m.NM_METRICA, s.NM_SEGMENTO, f.VL_MEDIDA
          FROM gold.fato_avaliacao_fisica f
          JOIN gold.dim_calendario c        ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_metrica_corporal m  ON m.SK_METRICA = f.SK_METRICA
          JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
         WHERE f.FL_MEDIDO = 'S' AND m.NM_METRICA IN ({nomes})
    """, eng)
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    num = lambda v: None if pd.isna(v) else round(float(v), 2)

    seg = df[df["NM_METRICA"].isin(METRICAS_SEG)]
    pv = seg.pivot_table(index=["NR_AVALIACAO", "data"], columns=["NM_SEGMENTO", "NM_METRICA"], values="VL_MEDIDA")
    # [data, nr, [[magra kg, gordura kg, magra % do padrao, gordura % do padrao] por segmento]]
    aval = [[d, int(nr), [[num(pv.loc[(nr, d)].get((s, m))) for m in METRICAS_SEG] for s in SEGMENTOS]]
            for nr, d in pv.index]

    fita = df[df["NM_METRICA"].isin(FITA)].pivot_table(index="data", columns="NM_METRICA", values="VL_MEDIDA")
    medidas = [m for m in FITA if m in fita.columns]
    return ({"segmentos": SEGMENTOS, "aval": sorted(aval)},
            {"medidas": [m.replace("Abdomem", "Abdômen") for m in medidas],
             "aval": [[d, [num(fita.loc[d, m]) for m in medidas]] for d in fita.index]})


# ---------------------------------------------------------------- periodos
def resumo_habitos(dias: pd.DataFrame, ini, fim) -> dict:
    """Habitos dos dias em (ini, fim]: o dia da avaliacao conta no periodo que ela fecha."""
    recorte = dias[(dias["data"] > ini) & (dias["data"] <= fim)]
    corridos = (fim - ini).days
    n = len(recorte)
    if n == 0:
        return {"dias": corridos, "registrados": 0, "cobertura": 0.0}
    return {
        "dias": corridos,
        "registrados": n,
        "cobertura": n / corridos,
        "treino_sem": 7 * recorte["treino"].mean(),
        "cardio_sem": 7 * recorte["cardio"].mean(),
        "agua_l": recorte["agua"].mean(),
        "meta_agua_pct": 100 * recorte["meta_agua"].mean(),
        "jaca_dia": recorte["jaca"].mean(),
        "plano_pct": 100 * ((recorte["feitas"] - recorte["jaca"]).clip(lower=0) / REFEICOES_DIA).mean(),
        **{k + "_pct": 100 * recorte[k].mean() for k in REFEICOES},
    }


def periodos(dias: pd.DataFrame, aval: pd.DataFrame, chave: str) -> list[dict]:
    """Um periodo por par de avaliacoes consecutivas QUE TEM a metrica."""
    com = aval[aval[chave].notna()].reset_index(drop=True)
    saida = []
    for i in range(1, len(com)):
        a, b = com.iloc[i - 1], com.iloc[i]
        h = resumo_habitos(dias, a["data"], b["data"])
        delta = float(b[chave] - a[chave])
        p = {
            "de": int(a["nr"]), "ate": int(b["nr"]),
            "ini": a["data"].strftime("%Y-%m-%d"), "fim": b["data"].strftime("%Y-%m-%d"),
            "antes": float(a[chave]), "depois": float(b[chave]),
            "delta": delta, "delta30": 30 * delta / h["dias"],
            "misto": a["origem"] != b["origem"],
            "baixa_cobertura": h["cobertura"] < COBERTURA_MINIMA,
            "origens": [a["origem"], b["origem"]],
        }
        p.update(h)
        p["confiavel"] = not (p["misto"] or p["baixa_cobertura"])
        saida.append(p)
    return saida


# ------------------------------------------------------------- estatistica
def spearman(x, y) -> float:
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1])


def forca(r: float, n: int) -> str:
    """Rotulo honesto: com n pequeno, so |r| alto passa de 'fraca'.
    Limiar de significancia a 5% bicaudal ~ 2/sqrt(n)."""
    lim = 2 / np.sqrt(max(n, 3))
    a = abs(r)
    if a < min(0.3, lim):
        return "fraca"
    if a < lim:
        return "fraca"
    return "forte" if a >= max(0.6, lim + 0.15) else "moderada"


def correlacoes(per: list[dict]) -> list[dict]:
    out = []
    y = np.array([p["delta30"] for p in per])
    for k, nome in HABITOS_DIAG.items():
        x = np.array([p[k] for p in per])
        if len(x) < 4 or x.std() == 0:
            continue
        r = float(np.corrcoef(x, y)[0, 1])
        b, a = np.polyfit(x, y, 1)
        out.append({"habito": k, "nome": nome, "n": len(x), "pearson": r,
                    "spearman": spearman(x, y), "forca": forca(r, len(x)),
                    "incl": float(b), "inter": float(a)})
    return sorted(out, key=lambda c: -abs(c["pearson"]))


def tercis(per: list[dict], melhor: str) -> dict:
    """Habitos medios no terco de melhor resultado contra o terco de pior."""
    ordem = sorted(per, key=lambda p: p["delta30"], reverse=(melhor == "maior"))
    t = max(1, len(ordem) // 3)
    med = lambda grupo, k: float(np.mean([p[k] for p in grupo]))  # noqa: E731
    return {
        "n": t,
        "melhores": {k: med(ordem[:t], k) for k in HABITOS_DIAG} | {"delta30": med(ordem[:t], "delta30")},
        "piores": {k: med(ordem[-t:], k) for k in HABITOS_DIAG} | {"delta30": med(ordem[-t:], "delta30")},
    }


def distribuicao(per: list[dict]) -> dict:
    """Media, desvio e faixa de cada habito entre os periodos, e o tamanho
    tipico da variacao da metrica: e a regua do simulador."""
    out = {}
    for k in HABITOS_DIAG:
        x = np.array([p[k] for p in per], dtype=float)
        out[k] = {"media": float(x.mean()), "desvio": float(x.std()) or 1.0,
                  "min": float(x.min()), "max": float(x.max())}
    curtos = [p["delta"] for p in per if p["dias"] <= 35]
    out["ruido"] = float(np.std(curtos)) if len(curtos) > 1 else None
    out["ruido_n"] = len(curtos)
    return out


# ------------------------------------------------------------- simulador
def modelo_simulador(dias: pd.DataFrame, aval: pd.DataFrame) -> dict:
    """
    Efeito de cada habito, por mes, em gordura (kg) e massa magra (kg).

    Para cada habito mistura a fisiologia (PRIORI) com a inclinacao da
    reta nos seus periodos, cada uma pesando o inverso da sua variancia:
    inclinacao precisa puxa muito, inclinacao ruidosa quase nada. O
    nivel e recalibrado para que, nos habitos medios desde 2024, o
    modelo devolva o ritmo medio que de fato aconteceu.
    """
    com = aval[aval["gordura_kg"].notna() & aval["magra"].notna()].reset_index(drop=True)
    per = []
    for i in range(1, len(com)):
        a, b = com.iloc[i - 1], com.iloc[i]
        h = resumo_habitos(dias, a["data"], b["data"])
        if h["cobertura"] < COBERTURA_MINIMA:
            continue
        per.append(dict(h, g=MES * (b["gordura_kg"] - a["gordura_kg"]) / h["dias"],
                        m=MES * (b["magra"] - a["magra"]) / h["dias"]))
    p = pd.DataFrame(per)
    w = p["dias"].to_numpy(dtype=float)
    hbar = {k: float(np.average(p[k], weights=w)) for k in HABITOS}
    out = {"n": len(p), "hbar": hbar, "efeito": {}, "base": {}, "ruido": {}, "se_base": {}}
    for alvo in ("g", "m"):
        y = p[alvo].to_numpy(dtype=float)
        out["base"][alvo] = float(np.average(y, weights=w))
        out["se_base"][alvo] = float(y.std(ddof=1) / np.sqrt(len(y)))
        out["efeito"][alvo] = {}
        for k in HABITOS:
            x = p[k].to_numpy(dtype=float)
            sxx = ((x - x.mean()) ** 2).sum()
            b1, b0 = np.polyfit(x, y, 1)
            se = float(np.sqrt(((y - (b0 + b1 * x)) ** 2).sum() / (len(y) - 2) / sxx))
            mp, sp = PRIORI[alvo][k]
            prec = 1 / sp ** 2 + 1 / se ** 2
            out["efeito"][alvo][k] = {"priori": mp, "dp_priori": sp, "dados": float(b1), "dp_dados": se,
                                      "usado": (mp / sp ** 2 + b1 / se ** 2) / prec, "dp": float(np.sqrt(1 / prec)),
                                      "peso_dados": float((1 / se ** 2) / prec)}
        pred = out["base"][alvo] + sum(out["efeito"][alvo][k]["usado"] * (p[k] - hbar[k]) for k in HABITOS)
        out["ruido"][alvo] = float(np.std(y - pred, ddof=1))
    return out


def le_inbody_extra(eng) -> dict:
    """Metricas do exame alem de gordura e musculo, com faixa de referencia e sentido melhor."""
    nomes = ", ".join(f"'{m[0]}'" for m in INBODY_EXTRA)
    df = pd.read_sql(f"""
        SELECT f.NR_AVALIACAO, c.DT_DATA, m.NM_METRICA, m.DS_UNIDADE, m.DS_SENTIDO_MELHOR, f.VL_MEDIDA,
               f.VL_REFERENCIA_MIN, f.VL_REFERENCIA_MAX, f.DS_ORIGEM
          FROM gold.fato_avaliacao_fisica f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
         WHERE f.SK_SEGMENTO = -1 AND f.FL_MEDIDO = 'S' AND m.NM_METRICA IN ({nomes})
    """, eng)
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    unid = {"Kg": "kg", "Pontos": "", "Razão": "", "Imc": "", "kcal": "kcal", "L": "L"}
    metricas, series = [], []
    for nome, rotulo, casas, faixa in INBODY_EXTRA:
        d = df[df["NM_METRICA"] == nome].sort_values("data")
        if d.empty:
            continue
        # faixa do proprio exame quando ela e plausivel: a de proteina vem as vezes em % do
        # padrao (89 a 109) para um valor em kg (~11), e essa fica de fora
        r = d.dropna(subset=["VL_REFERENCIA_MIN", "VL_REFERENCIA_MAX"])
        med = float(d["VL_MEDIDA"].median())
        r = r[(r["VL_REFERENCIA_MAX"] > r["VL_REFERENCIA_MIN"]) & (r["VL_REFERENCIA_MAX"] < 2 * r["VL_REFERENCIA_MIN"])
              & (r["VL_REFERENCIA_MIN"] < 2 * med) & (r["VL_REFERENCIA_MAX"] > med / 2)]
        ref, fonte = None, None
        if len(r):
            ref, fonte = [float(r["VL_REFERENCIA_MIN"].iloc[-1]), float(r["VL_REFERENCIA_MAX"].iloc[-1])], "exame"
        elif faixa:
            ref, fonte = list(faixa), "usual"
        sentido = d["DS_SENTIDO_MELHOR"].dropna()
        u = d["DS_UNIDADE"].dropna()
        metricas.append({"id": nome, "nome": rotulo, "unid": unid.get(u.iloc[0], u.iloc[0]) if len(u) else "",
                         "casas": casas, "sentido": sentido.iloc[0].lower() if len(sentido) else None,
                         "ref": ref, "ref_fonte": fonte})
        series.append([[x.data, int(x.NR_AVALIACAO), round(float(x.VL_MEDIDA), 3), x.DS_ORIGEM] for x in d.itertuples()])
    return {"metricas": metricas, "series": series}


# ------------------------------------------------------------- series
def semanal(dias: pd.DataFrame) -> list[dict]:
    """Media movel de 4 semanas, sobre semanas de calendario completas."""
    cal = pd.DataFrame({"data": pd.date_range(dias["data"].min(), dias["data"].max())})
    d = cal.merge(dias, on="data", how="left")
    d["semana"] = d["data"] - pd.to_timedelta(d["data"].dt.weekday, unit="D")
    g = d.groupby("semana").agg(registrados=("treino", "count"), treino=("treino", "sum"),
                                cardio=("cardio", "sum"), agua=("agua", "mean"),
                                jaca=("jaca", "mean"))
    # semana com menos de 4 dias respondidos fica de fora, em vez de
    # puxar a media para zero
    g = g[g["registrados"] >= 4].copy()
    g["treino"] = 7 * g["treino"] / g["registrados"]
    g["cardio"] = 7 * g["cardio"] / g["registrados"]
    r = g[["treino", "cardio", "agua", "jaca"]].rolling(4, min_periods=2).mean()
    return [{"semana": i.strftime("%Y-%m-%d"), **{k: round(float(v), 3) for k, v in row.items()}}
            for i, row in r.iterrows()]


def anual(dias: pd.DataFrame) -> list[dict]:
    out = []
    for ano, g in dias.groupby(dias["data"].dt.year):
        corridos = (date(ano, 12, 31) - date(ano, 1, 1)).days + 1
        if ano == dias["data"].max().year:
            corridos = (dias["data"].max().date() - date(ano, 1, 1)).days + 1
        out.append({"ano": int(ano), "registrados": len(g), "corridos": corridos,
                    "treino_sem": 7 * g["treino"].mean(), "cardio_sem": 7 * g["cardio"].mean(),
                    "agua_l": g["agua"].mean(), "meta_agua_pct": 100 * g["meta_agua"].mean(),
                    "jaca_dia": g["jaca"].mean(),
                    "plano_pct": 100 * ((g["feitas"] - g["jaca"]).clip(lower=0) / REFEICOES_DIA).mean()})
    return out


# ------------------------------------------------------------------ main
def limpa(o):
    if isinstance(o, dict):
        return {k: limpa(v) for k, v in o.items()}
    if isinstance(o, list):
        return [limpa(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 4)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    dias = le_dias(eng)
    aval = le_avaliacoes(eng)

    fim = dias["data"].max()
    ult30 = resumo_habitos(dias, fim - pd.Timedelta(days=30), fim)

    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "dias_ini": dias["data"].min().strftime("%Y-%m-%d"),
        "dias_fim": fim.strftime("%Y-%m-%d"),
        "dias_n": len(dias),
        "meta_agua_dias": int(dias["meta_agua"].sum()),
        "avaliacoes": [{"nr": int(r.nr), "data": r.data.strftime("%Y-%m-%d"), "origem": r.origem,
                        "peso": r.peso, "gordura": r.gordura, "musculo": r.musculo,
                        "gordura_kg": r.gordura_kg, "magra": r.magra}
                       for r in aval.itertuples()],
        "semanal": semanal(dias),
        "anual": anual(dias),
        "ultimos30": ult30,
        "habitos": HABITOS, "habitos_diag": HABITOS_DIAG,
        "metricas": {},
        # serie diaria compacta: o filtro de periodo recalcula os habitos no HTML
        # [data, treino, cardio, agua, jaca, feitas, refeicoes (S/J/N/- na ordem de REFEICOES),
        #  produtivo (S/O/N), trabalho, Nina em casa, feriado, meta de agua]
        "dias": [[r.data.strftime("%Y-%m-%d"), int(r.treino), int(r.cardio),
                  None if pd.isna(r.agua) else round(float(r.agua), 2),
                  None if pd.isna(r.jaca) else int(r.jaca), None if pd.isna(r.feitas) else int(r.feitas),
                  r.refs, r.produtivo, int(r.trabalho), int(r.nina), int(r.feriado), int(r.meta_agua)]
                 for r in dias.itertuples()],
        "refeicoes": {k: nome for k, (_, nome) in REFEICOES.items()},
        "simulador": modelo_simulador(dias, aval),
    }
    dados["membros"], dados["fita"] = le_membros(eng)
    dados["inbody"] = le_inbody_extra(eng)
    print("InBody extra: " + ", ".join(f"{m['nome']} ({len(s_)}, ref {m['ref']} {m['ref_fonte'] or ''})"
                                       for m, s_ in zip(dados["inbody"]["metricas"], dados["inbody"]["series"])))
    print("Refeições no plano (todos os dias): " + ", ".join(f"{nome} {100 * dias[k].mean():.0f}%" for k, (_, nome) in REFEICOES.items()))
    print(f"Membros: {len(dados['membros']['aval'])} avaliações segmentares; fita: {len(dados['fita']['aval'])} "
          f"({', '.join(dados['fita']['medidas'])})")
    for a in dados["membros"]["aval"][-2:]:
        print("  ", a[0], a[2])

    for chave, meta in METRICAS.items():
        per = periodos(dias, aval, chave)
        conf = [p for p in per if p["confiavel"]]
        analise = {nome: {"corr": correlacoes(grupo), "tercis": tercis(grupo, meta["melhor"]),
                          "dist": distribuicao(grupo)}
                   for nome, grupo in (("todos", per), ("confiaveis", conf))}
        # a analise fica so no log: o HTML recalcula para o periodo escolhido
        dados["metricas"][chave] = dict(meta, periodos=per)

        print(f"\n== {meta['nome']}: {len(per)} períodos, {len(conf)} confiáveis")
        for p in per:
            marca = ("misto " if p["misto"] else "") + ("cobertura " if p["baixa_cobertura"] else "")
            print(f"  {p['de']:>2}->{p['ate']:<2} {p['ini']}..{p['fim']} {p['dias']:>4}d "
                  f"cob {p['cobertura']:.0%}  treino {p.get('treino_sem', 0):.1f}  cardio {p.get('cardio_sem', 0):.1f}  "
                  f"agua {p.get('agua_l', 0):.2f}  jaca {p.get('jaca_dia', 0):.2f}  "
                  f"Δ {p['delta']:+.2f}  Δ30 {p['delta30']:+.2f}  {marca}")
        for nome in ("todos", "confiaveis"):
            a = analise[nome]
            print(f"  [{nome}] " + "  ".join(f"{c['habito']} r={c['pearson']:+.2f} ({c['forca']})"
                                            for c in a["corr"]))
            tc = a["tercis"]
            print(f"  [{nome}] tercis n={tc['n']}: melhores Δ30 {tc['melhores']['delta30']:+.2f} "
                  f"x piores {tc['piores']['delta30']:+.2f}; ruído em ≤35 dias ±{a['dist']['ruido']:.2f}")

    sim = dados["simulador"]
    print(f"\n== simulador: {sim['n']} periodos; base gordura {sim['base']['g']:+.3f} kg/mes, magra {sim['base']['m']:+.3f}")
    for alvo in ("g", "m"):
        for k, e in sim["efeito"][alvo].items():
            print(f"  {alvo} {k:<11} priori {e['priori']:+.3f}±{e['dp_priori']:.2f}  dados {e['dados']:+.3f}±{e['dp_dados']:.2f}"
                  f"  -> usado {e['usado']:+.3f}±{e['dp']:.3f} (dados pesam {e['peso_dados']:.0%})")

    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(limpa(dados), ensure_ascii=False, separators=(",", ":")))
    html = mzo.carimba(html, mzo.atualizacao(eng, ["fato_avaliacao_fisica", "fato_dia", "fato_dia_habito"]))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
