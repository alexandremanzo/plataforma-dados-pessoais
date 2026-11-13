"""
Painel de viagens, em HTML offline.

Le gold.fato_movto_financ (ANALITICO) e gold.fato_familia (so SELECT),
junta os lancamentos de cada viagem, cruza com gold.fato_dia e com as
avaliacoes fisicas, e embute tudo no template. O HTML recorta por
periodo (ano de inicio da viagem).

Como uma viagem e montada, em quatro passos:

  1. SEMENTE. As tags DS_TIPO = 'Viagem' das duas tabelas. Tags duplicadas
     da mesma viagem podem ser unidas em VIAGENS (mesmo id); o nome que
     aparece sai daqui, com as datas reais dos lancamentos.

  2. PELO TEXTO. Lancamento sem tag com cara de viagem (hospedagem,
     passagem, pacote, voo...) e com o destino no texto entra na viagem
     mais proxima, ate 200 dias antes e 120 depois das tags. E assim que
     a hospedagem paga meses antes entra.

  3. PELA CIDADE. Lancamento sem tag numa cidade da viagem (fora de
     casa), de 3 dias antes a 3 dias depois dela, entra marcado.

  4. SEM TAG NENHUMA. O que sobra fora de casa e agrupado por
     proximidade de data; grupo com dois dias ou mais e R$ 300 ou mais
     vira "viagem achada pela cidade". O HTML tem uma chave para
     inclui-las.

PERIODO DA VIAGEM. Hospedagem e passagem sao pagas meses antes, entao o
periodo nao e do primeiro ao ultimo lancamento: e o maior bloco de dias
com gasto na cidade de destino (buracos de ate 10 dias). Sem cidade, o
bloco sai dos gastos do dia a dia (sem hospedagem e passagem). O que
cai antes do bloco e "compra antecipada".

DUPLICADO. O mesmo gasto vem nas duas tabelas quando o Ale pagou algo
da casa no proprio cartao: lancamento da familia (pessoa ALE) com a
mesma data e o mesmo valor de um de financas sai, fica o de financas.

REEMBOLSO. Receita dentro da viagem (amigo pagando a parte, estorno)
abate o custo: custo = despesas - reembolsos.

Saida site/painel-viagens.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_viagens.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_viagens.html")
SAIDA = RAIZ / "site" / "painel-viagens.html"


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).lower().strip()


# ---------------------------------------------------------------- viagens
# tag -> (id da viagem, nome, destino no texto, datas fixas quando nao ha
# gasto no destino para achar o periodo)
VIAGENS = {
    "#Brotas_Abr21": ("brotas21", "Brotas", r"brotas", None),
    "#IlhaGrande_Jul21": ("ilhagrande21", "Ilha Grande", r"ilha grande", None),
    "#Curitiba_Out21": ("curitiba21", "Curitiba e Morretes", r"curitiba|morretes", None),
    "#Gramado_Jul22": ("gramado22", "Serra Gaúcha", r"gramado|canela", None),
    "#Buzios_Nov22": ("buzios22", "Búzios", r"buzios", None),
    "#Salvador_Fev23": ("salvador23", "Salvador", r"salvador", None),
    "#Tiradentes_Jun23": ("tiradentes23", "Tiradentes", r"tiradentes", None),
    "#PortoSeguro_Out23": ("portoseguro23", "Porto Seguro", r"porto seguro", None),
    "#Jeri_Jan24": ("jeri24", "Jericoacoara", r"jericoacoara|jeri", None),
    "#Bonito_Jul24": ("bonito24", "Bonito", r"bonito", None),
    "#MonteVerde_Set24": ("monteverde24", "Monte Verde", r"monte verde", None),
    "#Reveillon_25": ("reveillon25", "Réveillon em Ilhabela", r"ilhabela|reveillon", None),
    "#Maceio_Mai25": ("maceio25", "Maceió e Milagres", r"maceio|milagres", None),
    "#Santiago_Set25": ("santiago25", "Santiago", r"santiago", None),
    "#Natal_Jul26": ("natal26", "Natal", r"natal", None),
}
# destino de quem nao tem gasto no lugar
DESTINO_FIXO: dict[str, str] = {}
# texto que confirma que o lancamento e de viagem (passo 2)
CARA_VIAGEM = re.compile(r"viagem|aeroporto|hosped|pousada|hotel|hostel|passagem|pacote|voo|transfer|buser|onibus|airbnb|booking|reserva|ingresso")
GRUPOS_VIAGEM = {"hospedagem", "hotel", "aereo", "aviao", "pacote", "passagens", "passagem", "viagem", "buser", "onibus", "ingresso", "show"}

# ---------------------------------------------------------------- cidades
# nome no lake (sem acento) -> nome certo, para grafias diferentes da mesma cidade
GRAFIA = {"sp": "São Paulo"}
# nome certo -> (UF ou pais, lat, lon)
COORD = {
    "Campinas": ("SP", -22.91, -47.06), "Valinhos": ("SP", -22.97, -46.99), "São Paulo": ("SP", -23.55, -46.63),
    "Brotas": ("SP", -22.28, -48.13), "Ilhabela": ("SP", -23.78, -45.36), "Monte Verde": ("MG", -22.86, -46.04),
    "Águas de Lindóia": ("SP", -22.48, -46.63), "Holambra": ("SP", -22.63, -47.06), "Ilha Grande": ("RJ", -23.14, -44.17),
    "Búzios": ("RJ", -22.75, -41.88), "Tiradentes": ("MG", -21.11, -44.18), "Curitiba": ("PR", -25.43, -49.27),
    "Morretes": ("PR", -25.48, -48.83), "Gramado": ("RS", -29.38, -50.87), "Canela": ("RS", -29.36, -50.81),
    "Bonito": ("MS", -21.13, -56.49), "Salvador": ("BA", -12.97, -38.50), "Porto Seguro": ("BA", -16.45, -39.06),
    "Jericoacoara": ("CE", -2.80, -40.51), "Maceió": ("AL", -9.67, -35.74), "São Miguel dos Milagres": ("AL", -9.26, -35.37),
    "Natal": ("RN", -5.79, -35.21), "Santiago": ("Chile", -33.45, -70.67),
}
# nome bonito para os que ficaram sem acento no dicionario
BONITO: dict[str, str] = {}
# como a cidade aparece no texto dos lancamentos
APELIDO = {"Águas de Lindóia": r"lindoia", "São Miguel dos Milagres": r"milagres"}
# casa: Campinas e arredores
CASA = {"Campinas", "Valinhos"}
SEM_CIDADE = {"Não informado", "Sem cidade"}

REGIOES = {"RJ": "Litoral RJ e ES", "ES": "Litoral RJ e ES", "SP": "São Paulo", "RS": "Sul", "SC": "Sul", "PR": "Sul",
           "SE": "Nordeste", "CE": "Nordeste", "RN": "Nordeste", "PE": "Nordeste", "AL": "Nordeste", "BA": "Nordeste",
           "MG": "Minas e Centro-Oeste", "GO": "Minas e Centro-Oeste", "DF": "Minas e Centro-Oeste", "MS": "Minas e Centro-Oeste",
           "Chile": "Exterior"}


def cidade(nm: str) -> str:
    """'Belo Horizonte/BH - Brasil' -> 'Belo Horizonte'; 'Lima - Peru' -> 'Lima'."""
    if not isinstance(nm, str) or nm == "Não informado":
        return "Não informado"
    base = re.split(r"/| - ", nm)[0].strip()
    return GRAFIA.get(sem_acento(base), base)


# ---------------------------------------------------------------- categorias
BALDES = [("hosp", "Hospedagem"), ("pass", "Passagens e pacotes"), ("carro", "Carro e estrada"), ("local", "Uber e transporte local"),
          ("rest", "Restaurantes e lanches"), ("merc", "Mercado"), ("bar", "Bares e bebidas"), ("lazer", "Passeios e ingressos"),
          ("outros", "Outros")]
_G = {
    "hosp": "hospedagem hotel airbnb pousada",
    "pass": "aereo aviao pacote passagens passagem viagem buser onibus",
    "carro": "combustivel automovel estacionamento pedagio",
    "local": "uber 99pop taxi transporte metro",
    "merc": "mercado",
    "bar": "butecando bebida cerveja chopp terere",
    "lazer": "ingresso atrativo passeio show cachoeira cinema souvenir",
}
GRUPO_BALDE = {g: b for b, s in _G.items() for g in s.split()}


def balde(cat: str, grupo: str) -> str:
    g, c = sem_acento(grupo), sem_acento(cat)
    if g in GRUPO_BALDE:
        return GRUPO_BALDE[g]
    if g.startswith("viagem"):
        return "pass"
    if c in ("moradia", "hospedagem"):
        return "hosp"
    if c == "alimentacao":
        return "rest"
    if c == "transporte":
        return "local"
    if c == "lazer":
        return "lazer"
    return "outros"


# ---------------------------------------------------------------- leitura
def le_lancamentos(eng) -> pd.DataFrame:
    fin = pd.read_sql("""
        SELECT 'fin' AS fonte, c.DT_DATA, f.VL_TRANSACAO, f.DS_TIPO_FLUXO, f.DS_DETALHE_ORIGINAL AS det,
               k.NM_CATEGORIA, g.NM_GRUPO, a.NM_AREA, l.NM_LOCALIZACAO, t.NM_TAG, t.DS_TIPO AS tipo_tag, 'ALE' AS NM_PESSOA
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_localizacao l      ON l.SK_LOCALIZACAO = f.SK_LOCALIZACAO
          LEFT JOIN gold.dim_tag t         ON t.SK_TAG = f.SK_TAG
         WHERE f.DS_NIVEL = 'ANALITICO'
    """, eng)
    fam = pd.read_sql("""
        SELECT 'fam' AS fonte, c.DT_DATA, f.VL_TRANSACAO, f.DS_TIPO_FLUXO, f.DS_DETALHE_ORIGINAL AS det,
               k.NM_CATEGORIA, g.NM_GRUPO, a.NM_AREA, l.NM_LOCALIZACAO, t.NM_TAG, t.DS_TIPO AS tipo_tag, p.NM_PESSOA
          FROM gold.fato_familia f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_pessoa p           ON p.SK_PESSOA = f.SK_PESSOA
          LEFT JOIN gold.dim_localizacao l ON l.SK_LOCALIZACAO = f.SK_LOCALIZACAO
          LEFT JOIN gold.dim_tag t         ON t.SK_TAG = f.SK_TAG
         WHERE f.FL_FUTURO = 'N' OR f.FL_PAGO = 'S'
    """, eng)
    df = pd.concat([fin, fam], ignore_index=True)
    df = df[df["VL_TRANSACAO"].fillna(0) != 0].copy()
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.normalize()
    df["v"] = df["VL_TRANSACAO"].astype(float)
    df["det"] = df["det"].fillna("").astype(str).str.strip()
    df["detn"] = df["det"].map(sem_acento)
    df["grupo"] = df["NM_GRUPO"].fillna("").str.strip()
    df["gruponorm"] = df["grupo"].map(sem_acento)
    df["cid"] = df["NM_LOCALIZACAO"].map(cidade)
    df["quem"] = df["NM_PESSOA"].map({"ALE": "Ale", "LIA": "Lia", "Conta": "Conta"}).fillna("Outros")
    df["balde"] = [balde(c, g) for c, g in zip(df["NM_CATEGORIA"].fillna(""), df["grupo"])]
    # empreendimento de ferias (Resort): parcela de imovel, nao viagem
    df["resort"] = df["detn"].str.contains(r"(?:^|[^a-z])resort(?:[^a-z]|$)") | (df["NM_TAG"] == "#EmpreendimentoResort")
    # salario, aplicacao e transferencia nao sao gasto nem reembolso de viagem, mesmo com cidade
    df["neutro"] = df["NM_AREA"].isin(["RENDA", "INVESTIMENTO", "TRANSFERENCIA", "SALDO", "CORRECAO"])
    df["fora"] = ~df["cid"].isin(CASA | SEM_CIDADE)
    return df.reset_index(drop=True)


def le_dias(eng) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT c.DT_DATA, d.VL_AGUA_LITROS, d.FL_TREINO, d.FL_CARDIO, d.NR_REFEICOES_FEITAS, d.NR_REFEICOES_JACA
          FROM gold.fato_dia d JOIN gold.dim_calendario c ON c.SK_DATA = d.SK_DATA
         WHERE d.SK_DATA > 0
    """, eng)
    return pd.DataFrame({
        "data": pd.to_datetime(df["DT_DATA"]).dt.normalize(),
        "treino": (df["FL_TREINO"] == "S").astype(float), "cardio": (df["FL_CARDIO"] == "S").astype(float),
        "agua": df["VL_AGUA_LITROS"].astype(float), "feitas": df["NR_REFEICOES_FEITAS"].astype(float),
        "jaca": df["NR_REFEICOES_JACA"].astype(float),
    }).sort_values("data").reset_index(drop=True)


def le_avaliacoes(eng) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT c.DT_DATA, m.NM_METRICA, f.VL_MEDIDA
          FROM gold.fato_avaliacao_fisica f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
         WHERE f.SK_SEGMENTO = -1 AND f.FL_MEDIDO = 'S' AND m.NM_METRICA IN ('% Gordura', 'Peso')
    """, eng)
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.normalize()
    return df.pivot_table(index="data", columns="NM_METRICA", values="VL_MEDIDA", aggfunc="mean").reset_index()


def le_consumo(eng) -> pd.Series:
    """Gasto de consumo por ano em financas: essencial + estilo de vida."""
    df = pd.read_sql("""
        SELECT c.NR_ANO, -SUM(f.VL_TRANSACAO) v
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c  ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_area_financ a ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
         WHERE f.DS_NIVEL = 'ANALITICO' AND f.DS_TIPO_FLUXO = 'DESPESA' AND a.NM_AREA IN ('GASTOS ESSENCIAIS', 'ESTILO DE VIDA')
         GROUP BY c.NR_ANO
    """, eng)
    return df.set_index("NR_ANO")["v"]


# ---------------------------------------------------------------- montagem
def blocos(datas: list[pd.Timestamp], folga: int) -> list[list[pd.Timestamp]]:
    """Datas ordenadas em blocos com buracos de ate `folga` dias."""
    out: list[list[pd.Timestamp]] = []
    for d in sorted(set(datas)):
        if out and (d - out[-1][-1]).days <= folga:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def periodo(linhas: pd.DataFrame, cidades: set[str]) -> tuple[pd.Timestamp, pd.Timestamp, str]:
    """Inicio e fim da viagem: o maior bloco de dias com gasto no destino."""
    local = linhas[(linhas["v"] < 0) & linhas["cid"].isin(cidades)]
    if len(local) >= 2:
        base, como = local, "destino"
    else:
        dia = linhas[(linhas["v"] < 0) & ~linhas["balde"].isin(["hosp", "pass"])]
        base, como = (dia, "dia a dia") if len(dia) else (linhas, "todos")
    peso = base.groupby("data").size()
    bl = blocos(list(peso.index), 10)
    melhor = max(bl, key=lambda b: (sum(peso[d] for d in b), b[-1]))
    return melhor[0], melhor[-1], como


def tira_duplicados(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """
    Familia (pessoa ALE) com a mesma data e valor de financas sai; e o
    mesmo lancamento de financas repetido so com a cidade "Nao informado"
    tambem (o lake traz alguns em dobro, um com cidade e outro sem).
    """
    df = df.copy()
    df["k"] = df["data"].dt.strftime("%Y-%m-%d") + "|" + df["v"].abs().round(2).astype(str)
    usados: dict[str, int] = {}
    fora = []
    fin = df[df["fonte"] == "fin"]["k"].value_counts().to_dict()
    for i, r in df[(df["fonte"] == "fam") & (df["quem"] == "Ale")].iterrows():
        if usados.get(r.k, 0) < fin.get(r.k, 0):
            usados[r.k] = usados.get(r.k, 0) + 1
            fora.append(i)
    n_fam = len(fora)
    f = df[df["fonte"] == "fin"]
    dup = f[f.duplicated(["k", "det"], keep=False)]
    n_fin = 0
    for _, g in dup.groupby(["k", "det"]):
        sem = g[g["cid"] == "Não informado"]
        com = g[g["cid"] != "Não informado"]
        if len(com) and len(sem):
            corta = sem.index[: min(len(sem), len(com))]
            fora += list(corta)
            n_fin += len(corta)
    return df.drop(index=fora).drop(columns="k"), n_fam, n_fin


def monta_viagens(df: pd.DataFrame):
    livre = pd.Series(True, index=df.index)   # lancamento ainda sem viagem
    trip_de = pd.Series("", index=df.index)
    como = pd.Series("", index=df.index)      # tag, texto, cidade

    # 1. sementes
    meta: dict[str, dict] = {}
    for tag, (vid, nome, chave, datas) in VIAGENS.items():
        idx = df.index[(df["NM_TAG"] == tag) & (df["tipo_tag"] == "Viagem")]
        m = meta.setdefault(vid, {"id": vid, "nome": nome, "chave": chave, "datas": datas, "tags": [], "marcada": True})
        if len(idx):
            m["tags"].append(tag)
            trip_de[idx] = vid
            como[idx] = "tag"
            livre[idx] = False
    livre &= (df["tipo_tag"].fillna("") != "Viagem") & ~df["neutro"]

    # 2. pelo texto: cada lancamento livre vai para a viagem mais proxima que casa
    span = {vid: (df.loc[trip_de == vid, "data"].min(), df.loc[trip_de == vid, "data"].max()) for vid in meta}
    cand = df[livre & ~df["resort"] & (df["detn"].str.contains(CARA_VIAGEM) | df["gruponorm"].isin(GRUPOS_VIAGEM))]
    for i, r in cand.iterrows():
        melhor, dist = None, None
        for vid, m in meta.items():
            a, b = span[vid]
            if pd.isna(a) or not re.search(m["chave"], r.detn):
                continue
            if not (a - pd.Timedelta(days=200) <= r.data <= b + pd.Timedelta(days=120)):
                continue
            d = 0 if a <= r.data <= b else min(abs((r.data - a).days), abs((r.data - b).days))
            if dist is None or d < dist:
                melhor, dist = vid, d
        if melhor:
            trip_de[i] = melhor
            como[i] = "texto"
            livre[i] = False

    # 3. pela cidade, em volta do periodo
    def cidades_de(vid):
        x = df[(trip_de == vid) & df["fora"]]
        return set(x["cid"])

    for vid, m in meta.items():
        lin = df[trip_de == vid]
        cid = cidades_de(vid)
        if not len(lin):
            continue
        ini, fim, _ = periodo(lin, cid) if not m["datas"] else (pd.Timestamp(m["datas"][0]), pd.Timestamp(m["datas"][1]), "fixo")
        # cidade do destino que aparece so sem tag
        dest = {c for c in COORD if re.search(m["chave"], sem_acento(c))}
        janela = (df["data"] >= ini - pd.Timedelta(days=3)) & (df["data"] <= fim + pd.Timedelta(days=3))
        # na cidade da viagem, ou com grupo de viagem (hospedagem, passagem) dentro do periodo
        perto = df[livre & ~df["resort"] & (df["v"] < 0) & janela & ((df["fora"] & df["cid"].isin(cid | dest)) | df["gruponorm"].isin(GRUPOS_VIAGEM))]
        if not cid and dest:
            # sem nada no destino ainda: procura o bloco no destino ate 120 dias depois das tags
            perto = df[livre & df["fora"] & (df["v"] < 0) & df["cid"].isin(dest) & (df["data"] >= span[vid][0])
                       & (df["data"] <= span[vid][1] + pd.Timedelta(days=120))]
        trip_de[perto.index] = vid
        como[perto.index] = "cidade"
        livre[perto.index] = False

    # 4. sem tag: o que sobra fora de casa
    resto = df[livre & df["fora"] & ~df["resort"] & (df["v"] < 0) & (df["data"] <= pd.Timestamp.now())]
    achadas = []
    trechos = []
    for bl in blocos(list(resto["data"]), 2):
        x = resto[resto["data"].between(bl[0], bl[-1])]
        # duas viagens coladas: corta onde muda a regiao do dia
        uf_dia = x.assign(uf=x["cid"].map(lambda c: REGIOES.get(COORD.get(c, ("?",))[0], "?"))).groupby(["data", "uf"])["v"].sum().reset_index()
        uf_dia = uf_dia.loc[uf_dia.groupby("data")["v"].idxmin()].set_index("data")["uf"]
        partes, atual = [], [uf_dia.index[0]]
        for d0, d1 in zip(uf_dia.index[:-1], uf_dia.index[1:]):
            if uf_dia[d1] != uf_dia[d0] and -x.loc[x["data"].isin(atual), "v"].sum() >= 150:
                partes.append(atual)
                atual = []
            atual.append(d1)
        partes.append(atual)
        trechos += [(p[0], p[-1]) for p in partes]
    for ini_b, fim_b in trechos:
        bl = [ini_b, fim_b]
        x = resto[resto["data"].between(ini_b, fim_b)]
        x = x[livre[x.index]]
        if not len(x):
            continue
        dias = x["data"].nunique()
        if -x["v"].sum() >= 600 or (dias >= 2 and -x["v"].sum() >= 300):
            principal = x.groupby("cid")["v"].sum().idxmin()
            vid = f"achada{len(achadas)}"
            achadas.append(vid)
            nome = BONITO.get(principal, principal)
            chave = APELIDO.get(principal, re.escape(sem_acento(principal)))
            meta[vid] = {"id": vid, "nome": nome, "chave": chave, "datas": None, "tags": [], "marcada": False}
            trip_de[x.index] = vid
            como[x.index] = "cidade"
            livre[x.index] = False
            # hospedagem e passagem sem tag com o nome da cidade, ate 120 dias antes
            pre = df[livre & ~df["resort"] & (df["v"] < 0) & df["detn"].str.contains(chave) & (df["detn"].str.contains(CARA_VIAGEM) | df["gruponorm"].isin(GRUPOS_VIAGEM))
                     & (df["data"] >= bl[0] - pd.Timedelta(days=120)) & (df["data"] <= bl[-1] + pd.Timedelta(days=3))]
            trip_de[pre.index] = vid
            como[pre.index] = "texto"
            livre[pre.index] = False

    df = df.assign(viagem=trip_de, como=como)
    return df, meta


def habitos(dias: pd.DataFrame, ini, fim) -> dict | None:
    x = dias[dias["data"].between(ini, fim)]
    if not len(x):
        return None
    return {"n": int(len(x)), "treino": round(float(x["treino"].mean()), 3), "cardio": round(float(x["cardio"].mean()), 3),
            "agua": round(float(x["agua"].mean()), 2), "jaca": round(float(x["jaca"].mean()), 2), "feitas": round(float(x["feitas"].mean()), 2)}


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    import mzo

    eng = get_engine()
    df = le_lancamentos(eng)
    df, meta = monta_viagens(df)
    via = df[df["viagem"] != ""].copy()
    via, n_dup_fam, n_dup_fin = tira_duplicados(via)
    dias = le_dias(eng)
    aval = le_avaliacoes(eng)
    consumo = le_consumo(eng)
    hoje = pd.Timestamp.now().normalize()

    cidades = sorted({c for c in df["cid"].unique() if c in COORD})
    ic = {c: i for i, c in enumerate(cidades)}
    bnome = [b for b, _ in BALDES]
    ib = {b: i for i, b in enumerate(bnome)}
    quem = ["Ale", "Lia", "Conta", "Outros"]
    iq = {q: i for i, q in enumerate(quem)}

    viagens, linhas = [], []
    for vid, m in meta.items():
        lin = via[via["viagem"] == vid].sort_values("data")
        if not len(lin):
            continue
        cid = set(lin.loc[lin["fora"], "cid"])
        if m["datas"]:
            ini, fim, achou = pd.Timestamp(m["datas"][0]), pd.Timestamp(m["datas"][1]), "fixo"
        else:
            ini, fim, achou = periodo(lin, cid)
        desp = float(-lin.loc[lin["v"] < 0, "v"].sum())
        reemb = float(lin.loc[lin["v"] > 0, "v"].sum())
        if desp <= 0:
            continue
        g = lin[lin["v"] < 0]
        por_cid = g[g["cid"].isin(ic)].groupby("cid")["v"].sum().sort_values()
        dest = next((c for c in por_cid.index if c not in CASA), None)
        if dest is None:
            dest = next((c for c in COORD if re.search(m["chave"], sem_acento(c)) and c not in CASA), None)
        if dest is None:
            dest = DESTINO_FIXO.get(vid)
        uf = COORD[dest][0] if dest else None
        antes = g[g["data"] < ini]
        viagens.append({
            "id": vid, "nome": m["nome"], "marcada": m["marcada"], "tags": m["tags"],
            "ini": ini.strftime("%Y-%m-%d"), "fim": fim.strftime("%Y-%m-%d"), "dias": int((fim - ini).days + 1), "achou": achou,
            "compra1": g["data"].min().strftime("%Y-%m-%d"),
            "desp": round(desp, 2), "reemb": round(reemb, 2), "custo": round(desp - reemb, 2),
            "baldes": [round(float(-g.loc[g["balde"] == b, "v"].sum()), 2) for b in bnome],
            "quem": [round(float(-g.loc[g["quem"] == q, "v"].sum()), 2) for q in quem],
            "antecipado": round(float(-antes["v"].sum()), 2),
            "dest": ic.get(dest, -1), "uf": uf, "regiao": REGIOES.get(uf, "Outros") if uf else "Sem destino",
            "cidades": [[ic[c], round(float(-v), 2)] for c, v in por_cid.items() if c in ic and c not in CASA],
            "n": int(len(lin)), "por_texto": int((lin["como"] == "texto").sum()), "por_cidade": int((lin["como"] == "cidade").sum()),
        })

    viagens.sort(key=lambda v: v["ini"])
    for vi, v in enumerate(viagens):
        for r in via[via["viagem"] == v["id"]].sort_values("data").itertuples():
            # [data, viagem, valor (despesa -), balde, quem, cidade, fonte (0 fin, 1 fam), como (0 tag, 1 texto, 2 cidade), descricao]
            linhas.append([r.data.strftime("%Y-%m-%d"), vi, round(r.v, 2), ib[r.balde], iq[r.quem], ic.get(r.cid, -1),
                           0 if r.fonte == "fin" else 1, {"tag": 0, "texto": 1, "cidade": 2}[r.como], r.det[:48]])

    # habitos antes / durante / depois (o registro diario comeca em 2024)
    em_viagem = pd.Series(False, index=dias.index)
    for v in viagens:
        ini, fim = pd.Timestamp(v["ini"]), pd.Timestamp(v["fim"])
        em_viagem |= dias["data"].between(ini, fim)
    for v in viagens:
        ini, fim = pd.Timestamp(v["ini"]), pd.Timestamp(v["fim"])
        if fim < dias["data"].min() or v["achou"] == "fixo" or v["dias"] > 45:
            v["hab"] = None
            continue
        v["hab"] = {"antes": habitos(dias, ini - pd.Timedelta(days=14), ini - pd.Timedelta(days=1)),
                    "durante": habitos(dias, ini, fim),
                    "depois": habitos(dias, fim + pd.Timedelta(days=1), fim + pd.Timedelta(days=14))}
        a = aval[aval["data"] <= ini].tail(1)
        b = aval[(aval["data"] >= fim) & (aval["data"] <= fim + pd.Timedelta(days=60))].head(1)
        if len(a) and len(b) and (b["data"].iloc[0] - a["data"].iloc[0]).days <= 120:
            v["aval"] = {"de": a["data"].iloc[0].strftime("%Y-%m-%d"), "ate": b["data"].iloc[0].strftime("%Y-%m-%d"),
                         "gord": [round(float(a["% Gordura"].iloc[0]), 1), round(float(b["% Gordura"].iloc[0]), 1)],
                         "peso": [round(float(a["Peso"].iloc[0]), 1), round(float(b["Peso"].iloc[0]), 1)]}
    comum = dias[~em_viagem]
    base_hab = habitos(comum, comum["data"].min(), comum["data"].max())

    # avaliacao a avaliacao desde 2024: quanto do intervalo foi em viagem
    pares = []
    av = aval[aval["data"] >= "2024-01-01"].dropna(subset=["% Gordura"]).sort_values("data").reset_index(drop=True)
    for i in range(1, len(av)):
        a, b = av.loc[i - 1], av.loc[i]
        n = (b["data"] - a["data"]).days
        if n <= 0:
            continue
        fora = sum(max(0, (min(b["data"], pd.Timestamp(v["fim"])) - max(a["data"], pd.Timestamp(v["ini"]))).days + 1)
                   for v in viagens if v["dias"] <= 45)
        pares.append([a["data"].strftime("%Y-%m-%d"), b["data"].strftime("%Y-%m-%d"), n, int(fora),
                      round(float(b["% Gordura"] - a["% Gordura"]), 2), round(float(b["Peso"] - a["Peso"]), 2) if pd.notna(b["Peso"]) and pd.notna(a["Peso"]) else None])

    # gasto fora de casa que nao virou viagem (por cidade e ano)
    resto = df[(df["viagem"] == "") & df["fora"] & ~df["resort"] & (df["v"] < 0) & df["cid"].isin(ic)]
    resto = resto.assign(ano=resto["data"].dt.year)
    fora_casa = [[ic[c], int(a), round(float(-g["v"].sum()), 2), int(len(g)), int(g["data"].nunique())]
                 for (c, a), g in resto.groupby(["cid", "ano"])]

    # gasto de viagem por ano e o consumo do ano
    # consumo do ano: financas (essencial + estilo de vida) + o que a conta da familia pagou nas viagens
    fam_ano = via[(via["fonte"] == "fam") & (via["v"] < 0)].groupby(via["data"].dt.year)["v"].sum()
    anos = {int(a): round(float(consumo.get(a, 0.0)) - float(fam_ano.get(a, 0.0)), 2)
            for a in sorted(set(int(x) for x in consumo.index) | set(int(x) for x in fam_ano.index))}

    # gasto com cara de viagem que nao entrou em nenhuma (para taguear)
    solto = df[(df["viagem"] == "") & ~df["resort"] & (df["v"] < -300) & (df["data"] >= "2021-01-01")
               & (df["gruponorm"].isin(GRUPOS_VIAGEM) | df["detn"].str.contains(r"hosped|pousada|airbnb|pacote|passagem|voo"))
              ]
    soltos = [[r.data.strftime("%Y-%m-%d"), round(r.v, 2), r.det[:48], r.fonte] for r in solto.sort_values("data").itertuples()]

    avisos = []
    if n_dup_fam:
        avisos.append(f"{n_dup_fam} lançamentos estavam nas duas tabelas (família, pessoa Ale, e finanças): contados uma vez.")
    if n_dup_fin:
        avisos.append(f"{n_dup_fin} lançamentos de finanças vinham em dobro, um com cidade e outro sem: contados uma vez.")

    dados = {
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"), "hoje": hoje.strftime("%Y-%m-%d"),
        "baldes": BALDES, "quem": quem,
        "cidades": [[BONITO.get(c, c), COORD[c][0], COORD[c][1], COORD[c][2], 1 if c in CASA else 0] for c in cidades],
        "viagens": viagens, "linhas": linhas, "anos": anos, "fora": fora_casa, "pares": pares,
        "base_hab": base_hab, "soltos": soltos, "avisos": avisos,
    }

    # conferencia no terminal
    print(f"{len(viagens)} viagens ({sum(v['marcada'] for v in viagens)} com tag), {len(linhas)} lançamentos")
    for v in viagens:
        print(f"  {v['ini']} {v['dias']:>3}d {'T' if v['marcada'] else '-'} {v['nome'][:28]:<28} custo {v['custo']:>10,.2f}"
              f"  desp {v['desp']:>10,.2f} reemb {v['reemb']:>8,.2f} antec {v['antecipado']:>8,.2f}  [{v['achou']}] texto {v['por_texto']} cidade {v['por_cidade']}")
    print(f"duplicados: família {n_dup_fam}, finanças {n_dup_fin}")
    print(f"gasto de viagem solto (sem viagem, > R$ 300): {len(soltos)}")
    for s in soltos:
        print("   ", s)
    print("pares avaliação:", len(pares), "| base hábitos:", base_hab)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    html = mzo.carimba(html, mzo.atualizacao(eng, ["fato_movto_financ", "fato_familia", "fato_dia"]))
    return html, dados


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
