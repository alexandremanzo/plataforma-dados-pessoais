"""
Painel do carro, em HTML offline.

Junta as duas fontes que falam de automovel sem soma-las:

  CUSTO vem do financeiro (gold.fato_movto_financ, categoria
  TRANSPORTE, nivel ANALITICO): combustivel, IPVA, seguro, oficina,
  estacionamento. E o dinheiro que saiu.

  OFICINA vem de gold.fato_manutencao_auto: o que foi trocado, com que
  quilometragem, onde. O mesmo gasto de revisao aparece nas duas
  fontes; por isso o custo total sai so do financeiro e a oficina so
  detalha.

  VENCENDO vem de gold.vw_manutencao_prevista:
  o plano do fabricante do SUV, km e meses, o que vencer primeiro.

QUILOMETRAGEM e estimada. O hodometro so e anotado na oficina, entao
o km de cada mes sai da interpolacao entre visitas, e depois da
ultima visita segue o ritmo das visitas do carro em uso. Antes da
primeira visita do carro novo, o km usa o mesmo ritmo, projetado para
tras ate a compra. O HTML deixa digitar o km real.

O carro antigo foi vendido em parcelas: sai da previsao e da projecao
depois da ultima visita, e os gastos dele depois disso aparecem a parte.

Saida site/painel-carro.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_carro.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_carro.html")
SAIDA = RAIZ / "site" / "painel-carro.html"

ATIVO = "SUV"
COMPRA_ATIVO = "2025-05-20"     # "Compra SUV" no financeiro
SAIDA_SEDAN = "2025-06-10"     # ultima visita do carro antigo, antes da venda
PRECO_GASOLINA = 6.30           # suposicao; o HTML deixa ajustar

# grupo do financeiro (categoria TRANSPORTE) -> balde de custo.
# Fora daqui fica o que nao e ter carro: Uber, onibus, aviao, aluguel de carro em viagem.
BALDES = {
    "combustivel": ("Combustível", {"Combustivel"}),
    "manutencao": ("Oficina", {"Manutenção", "Revisão", "Manutenção carro", "Lanternagem", "Borracharia", "Reforma"}),
    "seguro": ("Seguro", {"SEGURO", "Seguro Carro"}),
    "impostos": ("IPVA e documentos", {"IPVA", "IMPOSTOS", "Imposto", "Dpvat", "Licenciamento", "Placa", "Vistoria",
                                       "Tranferencia Veiculo", "DOCUMENTO", "TAXA"}),
    "estacionamento": ("Estacionamento e pedágio", {"Estacionamento", "Veloe", "PEDÁGIO"}),
    "acessorios": ("Acessórios e limpeza", {"Acessório", "ACESSÓRIOS", "Limpeza", "Lava Jato", "Utencilios", "Iluminacao"}),
    "multas": ("Multas", {"Multa"}),
    "compra": ("Compra de carro", {"Compra Carro", "COMPRA"}),
}
ORDEM = list(BALDES)
DO_GRUPO = {g: k for k, (_, gs) in BALDES.items() for g in gs}

CARRO_DA_TAG = {"#SUV": "SUV", "#Sedan": "Sedan", "#SedanGL": "Sedan", "Sedan GL": "Sedan",
                "Compacto": "Compacto", "Hatch": "Hatch"}

# categoria da oficina -> sistema do carro
SISTEMA = {
    "Motor e arrefecimento": ["Óleo", "Filtro", "Vela", "Correia", "Polia", "Motor", "Radiador", "Liquido Arrefecimento",
                              "Leque", "Fluido", "Tampa"],
    "Freios": ["Freio"],
    "Suspensão e direção": ["Amortecedor", "Bandeja", "Bucha", "Bieleta", "Direção", "Rolamento", "Alinhamento",
                            "Balanceamento"],
    "Pneus": ["Pneu"],
    "Elétrica": ["Bateria", "Lampada", "Fusivel", "Alarme", "Sensor", "regulador", "Rastreamento", "Chave"],
    "Conforto e acabamento": ["Ar Condicionado", "Vidro", "Palheta", "Limpeza"],
    "Mão de obra": ["Mão de Obra"],
}
SISTEMA_DA_CAT = {c: s for s, cs in SISTEMA.items() for c in cs}


# ---------------------------------------------------------------- leitura
def le_custos(eng) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO, k.NM_CATEGORIA, g.NM_GRUPO, t.NM_TAG
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          LEFT JOIN gold.dim_tag t         ON t.SK_TAG = f.SK_TAG
         WHERE f.DS_NIVEL = 'ANALITICO'
           AND (k.NM_CATEGORIA = 'TRANSPORTE'
                OR (k.NM_CATEGORIA = 'REEMBOLSO' AND t.NM_TAG IN ('#SUV', '#Sedan')))
    """, eng)
    df["balde"] = df["NM_GRUPO"].str.strip().map(DO_GRUPO)
    # reembolso de carro (o farol do SUV, lancado no grupo SEGURO) abate a peca, nao o seguro:
    # no seguro ele derrubaria a mensalidade do simulador de R$ 307 para R$ 207
    df.loc[df["NM_CATEGORIA"] == "REEMBOLSO", "balde"] = "acessorios"
    df = df[df["balde"].notna()].copy()
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    df["valor"] = -df["VL_TRANSACAO"].astype(float)          # gasto positivo, reembolso/venda negativo
    df["carro"] = df["NM_TAG"].map(CARRO_DA_TAG)
    return df[df["valor"] != 0]


def le_vendas(eng) -> list:
    df = pd.read_sql("""
        SELECT c.DT_DATA, f.VL_TRANSACAO, g.NM_GRUPO, f.DS_DETALHE_ORIGINAL
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
         WHERE f.DS_NIVEL = 'ANALITICO'
           AND ((k.NM_CATEGORIA = 'VENDA' AND g.NM_GRUPO LIKE '%Sedan%')
                OR (k.NM_CATEGORIA = 'TRANSPORTE' AND g.NM_GRUPO = 'VENDA'))
    """, eng)
    carro = df["NM_GRUPO"].str.contains("Sedan").map({True: "Sedan", False: "Hatch"})
    return [[pd.Timestamp(d).strftime("%Y-%m-%d"), round(float(v), 2), c]
            for d, v, c in zip(df["DT_DATA"], df["VL_TRANSACAO"], carro)]


def le_oficina(eng) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT c.DT_DATA, v.NM_VEICULO, f.NR_VISITA, f.NR_KM, f.VL_GASTO, k.NM_CATEGORIA,
               f.DS_TIPO, f.FL_PREVENTIVA, f.DS_ITEM, f.DS_LOCAL
          FROM gold.fato_manutencao_auto f
          JOIN gold.dim_calendario c     ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_veiculo v        ON v.SK_VEICULO = f.SK_VEICULO
          JOIN gold.dim_categoria_auto k ON k.SK_CATEGORIA_MANUTENCAO = f.SK_CATEGORIA_MANUTENCAO
    """, eng)
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    df["sistema"] = df["NM_CATEGORIA"].map(SISTEMA_DA_CAT).fillna("Outros")
    return df


def le_plano(eng) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT NM_ITEM, NM_SISTEMA, DS_ACAO, NR_INTERVALO_KM, NR_INTERVALO_MESES,
               DT_ULTIMA_TROCA, NR_KM_ULTIMA_TROCA, NR_KM_PROXIMA_TROCA, DT_PROXIMA_TROCA
          FROM gold.vw_manutencao_prevista
         WHERE NM_VEICULO = '{ATIVO}'
    """, eng)


# ---------------------------------------------------------------- quilometragem
def leituras(of: pd.DataFrame) -> dict:
    """Hodometro por carro: [(data, km)], uma leitura por visita."""
    out = {}
    for carro, g in of.groupby("NM_VEICULO"):
        v = g.groupby("data")["NR_KM"].max().sort_index()
        v = v[v.cummax() == v]                                   # leitura menor que a anterior = erro de digitacao
        out[carro] = [(pd.Timestamp(d), float(k)) for d, k in v.items()]
    return out


def ritmo(pts) -> float:
    """km por dia entre a primeira e a ultima leitura."""
    (d0, k0), (d1, k1) = pts[0], pts[-1]
    return (k1 - k0) / max(1, (d1 - d0).days)


def km_por_mes(lei: dict, fim: pd.Timestamp) -> tuple[dict, dict]:
    """km rodados em cada mes, somando os carros que eram seus naquele mes."""
    meses = {}
    info = {}
    for carro, pts in lei.items():
        if len(pts) < 2:
            continue
        r = ritmo(pts[-3:] if carro == ATIVO else pts)
        ini, fim_c = pts[0][0], pts[-1][0]
        if carro == ATIVO:
            # antes da 1a visita: mesmo ritmo, para tras, ate a compra
            ini = pd.Timestamp(COMPRA_ATIVO)
            pts = [(ini, pts[0][1] - r * (pts[0][0] - ini).days)] + pts
            fim_c = fim
            pts = pts + [(fim, pts[-1][1] + r * (fim - pts[-1][0]).days)]
        else:
            fim_c = min(fim_c, pd.Timestamp(SAIDA_SEDAN)) if carro == "Sedan" else fim_c
        dias = pd.date_range(ini, fim_c, freq="D")
        x = np.array([(d - ini).days for d, _ in pts], dtype=float)
        y = np.array([k for _, k in pts])
        odo = pd.Series(np.interp([(d - ini).days for d in dias], x, y), index=dias)
        diario = odo.diff().fillna(0)
        for mes, v in diario.groupby(diario.index.strftime("%Y-%m")).sum().items():
            meses[mes] = meses.get(mes, 0) + float(v)
        info[carro] = {"ritmo_dia": round(r, 1), "km_ini": round(pts[0][1]), "ini": ini.strftime("%Y-%m-%d")}
    return {k: round(v) for k, v in sorted(meses.items())}, info


# ---------------------------------------------------------------- montagem
def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    cu, of, pl = le_custos(eng), le_oficina(eng), le_plano(eng)
    hoje = pd.Timestamp.now().normalize()
    fim_dados = max(pd.Timestamp(cu["data"].max()), hoje)

    lei = leituras(of)
    kmes, info_km = km_por_mes(lei, fim_dados)
    ult_d, ult_km = lei[ATIVO][-1]
    r_ativo = info_km[ATIVO]["ritmo_dia"]
    km_hoje = ult_km + r_ativo * (hoje - ult_d).days

    carros = ["SUV", "Sedan", "Compacto", "Hatch"]
    ic = {c: i for i, c in enumerate(carros)}
    custos = [[r.data, round(r.valor, 2), ORDEM.index(r.balde), ic.get(r.carro, -1)] for r in cu.itertuples()]

    # oficina: uma linha por item
    of = of.sort_values(["data", "NR_VISITA"])
    locais = sorted(of["DS_LOCAL"].fillna("Não informado").unique())
    sistemas = list(SISTEMA) + ["Outros"]
    il, isi = {x: i for i, x in enumerate(locais)}, {x: i for i, x in enumerate(sistemas)}
    oficina = [[r.data, ic[r.NM_VEICULO], int(r.NR_VISITA), int(r.NR_KM), round(float(r.VL_GASTO), 2), r.NM_CATEGORIA,
                isi[r.sistema], 1 if r.DS_TIPO == "Serviço" else 0, 1 if r.FL_PREVENTIVA == "S" else 0,
                r.DS_ITEM or "", il[r.DS_LOCAL if isinstance(r.DS_LOCAL, str) else "Não informado"]]
               for r in of.itertuples()]

    plano = []
    for r in pl.itertuples():
        plano.append({
            "item": r.NM_ITEM, "sistema": r.NM_SISTEMA, "acao": r.DS_ACAO,
            "ikm": None if pd.isna(r.NR_INTERVALO_KM) else int(r.NR_INTERVALO_KM),
            "imes": None if pd.isna(r.NR_INTERVALO_MESES) else int(r.NR_INTERVALO_MESES),
            "ult": None if pd.isna(r.DT_ULTIMA_TROCA) else pd.Timestamp(r.DT_ULTIMA_TROCA).strftime("%Y-%m-%d"),
            "ult_km": None if pd.isna(r.NR_KM_ULTIMA_TROCA) else int(r.NR_KM_ULTIMA_TROCA),
        })

    # premissas do simulador: ultimos 12 meses fechados ate o ultimo lancamento
    ini12 = (pd.Timestamp(cu["data"].max()) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")
    u12 = cu[cu["data"] > ini12]
    sedan_fam = (u12["carro"] == "Sedan") & (u12["data"] > SAIDA_SEDAN)
    por = u12[~sedan_fam].groupby("balde")["valor"].sum()
    meses12 = sorted({d[:7] for d in u12["data"]})[-12:]
    km12 = sum(kmes.get(m, 0) for m in meses12)
    litros12 = por.get("combustivel", 0) / PRECO_GASOLINA
    asx = of[of["NM_VEICULO"] == ATIVO]
    ipva_ativo = float(cu[(cu["balde"] == "impostos") & (cu["data"] >= f"{hoje.year}-01-01")]["valor"].sum())
    ipva_sedan_ant = float(cu[(cu["balde"] == "impostos") & (cu["carro"] == "Sedan")
                               & (cu["data"] >= f"{hoje.year - 1}-01-01") & (cu["data"] < f"{hoje.year}-01-01")]["valor"].sum())
    total_of_km = sum(lei[c][-1][1] - lei[c][0][1] for c in lei if len(lei[c]) > 1)
    sim = {
        "km_mes": round(r_ativo * 365.25 / 12),
        "preco": PRECO_GASOLINA,
        "consumo": round(float(km12 / litros12), 1) if litros12 else 8.0,
        "seguro_mes": round(float(por.get("seguro", 0)) / 12, 2),
        "estac_mes": round(float(por.get("estacionamento", 0)) / 12, 2),
        # 2026 pagou os dois numa guia; a parte do Sedan e estimada pelo IPVA dele no ano anterior
        "ipva_ano": round(max(0.0, ipva_ativo - ipva_sedan_ant)),
        "manut_km": round(float(of["VL_GASTO"].sum()) / total_of_km, 3) if total_of_km else 0.3,
        "km12": km12, "gasto12": {k: round(float(v), 2) for k, v in por.items()},
        "meses12": meses12,
    }

    # Antes de um certo ano o financeiro quase nao registra o carro (oficina R$ 0 em 2018-21,
    # com notas de milhares na oficina; combustivel de R$ 40/mes). Completo = combustivel
    # por mes de cada ano daqui em diante >= metade da mediana dos tres ultimos anos.
    comb = cu[cu["balde"] == "combustivel"].assign(ano=lambda x: x["data"].str[:4])
    meses_ano = cu.assign(ano=cu["data"].str[:4]).groupby("ano")["data"].apply(lambda s: s.str[:7].nunique())
    por_ano = (comb.groupby("ano")["valor"].sum() / meses_ano).dropna()
    ref = por_ano.iloc[-3:].median()
    completo = por_ano.index[-1]
    for ano in reversed(por_ano.index):
        if por_ano[ano] < ref / 2:
            break
        completo = ano

    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "completo_desde": int(completo),
        "hoje": hoje.strftime("%Y-%m-%d"),
        "baldes": [[k, BALDES[k][0]] for k in ORDEM],
        "carros": carros, "custos": custos, "vendas": le_vendas(eng),
        "locais": locais, "sistemas": sistemas, "oficina": oficina,
        "km_mes": kmes,
        "km": {"ultima": ult_d.strftime("%Y-%m-%d"), "ultimo_km": round(ult_km), "ritmo_dia": r_ativo,
               "hoje": round(km_hoje), "compra": COMPRA_ATIVO, "km_compra": info_km[ATIVO]["km_ini"],
               "primeira_visita": asx["data"].min(), "km_primeira": int(asx["NR_KM"].min())},
        "saida_sedan": SAIDA_SEDAN,
        "plano": plano, "sim": sim,
    }

    # conferencia no terminal
    print(f"{len(cu)} lançamentos de custo de {cu['data'].min()} a {cu['data'].max()}")
    print(cu.groupby("balde")["valor"].agg(["count", "sum"]).round(0).to_string())
    print(f"\nÚltimos 12 meses ({meses12[0]} a {meses12[-1]}), sem o Sedan com a família:")
    print(por.round(0).to_string(), f"\n  total sem compra {por.drop('compra', errors='ignore').sum():,.0f}")
    print(f"  km estimados {km12:,} → R$ {por.drop('compra', errors='ignore').sum() / max(1, km12):.2f}/km")
    print(f"\nKm: {ATIVO} {ult_km:,.0f} em {ult_d:%d/%m/%Y}, {r_ativo} km/dia → hoje ~{km_hoje:,.0f}")
    print("Premissas do simulador:", {k: v for k, v in sim.items() if k not in ("gasto12", "meses12")})
    print(f"{len(oficina)} itens de oficina, {len(plano)} itens no plano do {ATIVO}")
    print(f"Combustível por mês em cada ano: {por_ano.round(0).to_dict()} → registro completo desde {completo}")

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=str))
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.carimba(html, mzo.atualizacao(eng, ['fato_manutencao_auto', 'fato_movto_financ']))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
