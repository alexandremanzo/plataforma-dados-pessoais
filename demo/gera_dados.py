"""
Gerador de dados ficticios para a demonstracao dos paineis.

Preenche a camada gold de um banco vazio (demo/schema) com uma vida
inventada, mas coerente entre as areas: o salario que entra e o mesmo
que paga a fatura do cartao, o aporte que sai da conta corrente e o
mesmo que entra na corretora, a viagem que aparece no financeiro e a
mesma que derruba o treino no diario, e as avaliacoes fisicas respondem
aos habitos do periodo.

Nada aqui vem de dado real: os valores saem de distribuicoes escritas a
mao e de uma semente fixa. Os nomes de pessoas (Ale, Lia, Nina),
estabelecimentos e empreendimentos sao ficticios; cidades e tickers sao
publicos e servem so de cenario.

A historia vai de 2019 ate HOJE (a data da execucao, ou DEMO_HOJE no
ambiente), para que o filtro "ano atual" dos paineis sempre tenha dado.
Parcelas, financiamento e compromissos futuros seguem alem de hoje.

Uso:
    python demo/gera_dados.py            # usa o banco do .env / variaveis DB_*
    DEMO_HOJE=2026-11-13 python demo/gera_dados.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
from config_db import get_engine  # noqa: E402

SEMENTE = 20260413
HOJE = pd.Timestamp(os.getenv("DEMO_HOJE") or date.today()).normalize()
INICIO = pd.Timestamp("2019-01-01")
CARGA = datetime.now().replace(microsecond=0)
APP_JSON = RAIZ / "demo" / "dados" / "carteira_app.json"

rng = np.random.default_rng(SEMENTE)


def sk(d) -> int:
    d = pd.Timestamp(d)
    return d.year * 10000 + d.month * 100 + d.day


def hash_de(*partes) -> str:
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()


def r2(v: float) -> float:
    return float(round(v, 2))


# ===================================================================== calendario
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
         "Outubro", "Novembro", "Dezembro"]
SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]


def pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano: int) -> dict:
    p = pascoa(ano)
    f = {date(ano, 1, 1): ("Confraternização Universal", "Nacional"), date(ano, 4, 21): ("Tiradentes", "Nacional"),
         date(ano, 5, 1): ("Dia do Trabalho", "Nacional"), date(ano, 9, 7): ("Independência", "Nacional"),
         date(ano, 10, 12): ("Nossa Senhora Aparecida", "Nacional"), date(ano, 11, 2): ("Finados", "Nacional"),
         date(ano, 11, 15): ("Proclamação da República", "Nacional"), date(ano, 12, 25): ("Natal", "Nacional"),
         p - timedelta(days=48): ("Carnaval", "Ponto facultativo"), p - timedelta(days=47): ("Carnaval", "Ponto facultativo"),
         p - timedelta(days=2): ("Sexta-feira Santa", "Nacional"), p + timedelta(days=60): ("Corpus Christi", "Ponto facultativo")}
    if ano >= 2024:
        f[date(ano, 11, 20)] = ("Consciência Negra", "Nacional")
    return f


def calendario() -> pd.DataFrame:
    dias = pd.date_range("2008-01-01", "2032-12-31", freq="D")
    fer = {}
    for a in range(2008, 2033):
        fer.update(feriados(a))
    linhas = []
    for d in dias:
        f = fer.get(d.date())
        linhas.append({
            "SK_DATA": sk(d), "DT_DATA": d.date(), "NR_ANO": d.year, "NR_MES": d.month, "NM_MES": MESES[d.month - 1],
            "NM_MES_ABREV": MESES[d.month - 1][:3], "NR_DIA": d.day, "NR_DIA_SEMANA": d.weekday() + 1,
            "NM_DIA_SEMANA": SEMANA[d.weekday()], "NR_TRIMESTRE": (d.month - 1) // 3 + 1, "NR_SEMESTRE": 1 if d.month <= 6 else 2,
            "NM_ANO_MES": d.strftime("%Y-%m"), "DT_CARGA": CARGA, "FL_FIM_SEMANA": "S" if d.weekday() >= 5 else "N",
            "NM_MES_ANO": f"{MESES[d.month - 1][:3]}/{d.year}", "NM_DIA_SEMANA_ABREV": SEMANA[d.weekday()][:3],
            "FL_FERIADO": "S" if f else "N", "NM_FERIADO": f[0] if f else None, "DS_TIPO_FERIADO": f[1] if f else None,
        })
    return pd.DataFrame(linhas)


FERIADOS = {}
for _a in range(2008, 2033):
    FERIADOS.update(feriados(_a))


def e_feriado(d) -> bool:
    return pd.Timestamp(d).date() in FERIADOS


# ===================================================================== dimensoes simples
AREAS = ["A classificar", "CORRECAO", "EMPRESTIMO", "ESTILO DE VIDA", "ESTORNO", "GASTOS ESSENCIAIS", "INVESTIMENTO",
         "RECEITA", "RENDA", "SALDO", "TAXA", "TRANSFERENCIA", "VENDA", "REEMBOLSO"]
ORIGENS = [(1, "XP_INVEST", "XP Investimentos", "XP", "Conta de investimento"),
           (2, "ITAU_CC", "Itaú Conta Corrente", "Itaú", "Conta corrente"),
           (3, "CARTAO_XP", "Cartão XP", "XP", "Cartão de crédito"),
           (4, "CARTAO_NUBANK", "Cartão Nubank", "Nubank", "Cartão de crédito")]
PESSOAS = [(11, "ALE", "Titular"), (12, "Conta", "Conta conjunta"), (14, "LIA", "Titular")]
CAT_INVEST = [("Ajuste de Custos", "Custos"), ("Aplicação", "Caixa"), ("Compra", "Operação"), ("Dividendo", "Proventos"),
              ("Emolumentos", "Custos"), ("IOF", "Custos"), ("IR", "Custos"), ("Investback", "Proventos"),
              ("Liquidação", "Operação"), ("Pagamento", "Caixa"), ("Pagamento CC", "Caixa"), ("Reembolso", "Proventos"),
              ("Resgate", "Caixa"), ("Retirada", "Caixa"), ("Taxa de Remuneração", "Proventos"),
              ("Taxa de intermediação", "Custos"), ("Transferência", "Caixa"), ("Vencimento", "Operação")]

# taxonomia do financeiro: grupo -> (compressibilidade); a categoria e a area vem em cada lancamento
GRUPOS = {
    # renda e patrimonio
    "Salário": None, "PLR": None, "13º Salário": None, "Rendimento": "Nao e gasto", "Cofrinho": "Nao e gasto",
    "Investimento": "Nao e gasto", "Resgate": "Nao e gasto", "Fatura Crédito": "Nao e gasto", "Venda Sedan": None,
    # casa e fixos
    "Conta Familia": "Essencial", "Escola": "Essencial", "Material Escolar": "Essencial", "Telefonia": "Essencial",
    "Internet": "Essencial", "Streaming": "Compressivel", "Armazenamento dados": "Compressivel", "Academia": "Essencial",
    # alimentacao
    "Almoço": "Compressivel", "Lanche": "Compressivel", "Janta": "Compressivel", "Pizza": "Compressivel",
    "Burguer": "Compressivel", "Japa": "Compressivel", "Café da manhã": "Compressivel", "Sorvete": "Compressivel",
    "Mercado": "Essencial", "Padaria": "Compressivel", "Hortifrut": "Essencial", "Suplemento": "Eventual",
    # transporte
    "Combustivel": "Essencial", "Uber": "Compressivel", "Estacionamento": "Essencial", "PEDÁGIO": "Essencial",
    "Seguro Carro": "Essencial", "IPVA": "Essencial", "Licenciamento": "Essencial", "Manutenção": "Eventual",
    "Lava Jato": "Compressivel", "Acessório": "Eventual", "Multa": "Compressivel", "Compra Carro": "Eventual",
    "Avião": "Eventual", "Buser": "Compressivel",
    # lazer, pessoal, saude
    "Cinema": "Compressivel", "Bebida": "Compressivel", "Butecando": "Compressivel", "Ingresso": "Compressivel",
    "Evento": "Compressivel", "Hospedagem": "Eventual", "Passeio": "Compressivel",
    "Roupas": "Eventual", "Utencilios": "Eventual", "Papelaria": "Eventual", "Fotografia": "Eventual",
    "Presente Natal": "Eventual", "Presente Niver": "Eventual",
    "Medicamento": "Essencial", "Plano Saude": "Essencial", "Odonto": "Essencial", "Nutricionista": "Essencial", "Exame": "Essencial",
    "Eletrodomestico": "Eventual", "Móvel": "Eventual", "Eletro Eletrônico": "Eventual", "Reforma": "Eventual",
    # familia
    "Aporte": None, "Financiamento": "Essencial", "Condomínio": "Essencial", "Luz": "Essencial", "Água": "Essencial",
    "Gás": "Essencial", "IPTU": "Essencial", "Diarista": "Eventual", "Farmácia": "Essencial", "Entrada": None,
    "ITBI": None, "Cartório": None, "Empreendimento": None, "Pet": "Eventual",
}
CATEGORIAS = ["ALIMENTAÇÃO", "CASA", "EDUCAÇÃO", "ENTRETENIMENTO", "INVESTIMENTO", "LAZER", "PESSOAL", "PRESENTE",
              "SAÚDE", "TRANSPORTE", "Vestuário", "RENDIMENTO", "TRABALHO", "TRANSFERENCIA", "VENDA", "MORADIA",
              "APORTE", "REEMBOLSO", "IMÓVEL"]

# cidades (nome, UF ou pais, pais)
CIDADES = [("Campinas", "SP", "Brasil"), ("Valinhos", "SP", "Brasil"), ("São Paulo", "SP", "Brasil"),
           ("Brotas", "SP", "Brasil"), ("Ilha Grande", "RJ", "Brasil"), ("Curitiba", "PR", "Brasil"), ("Morretes", "PR", "Brasil"),
           ("Gramado", "RS", "Brasil"), ("Canela", "RS", "Brasil"), ("Búzios", "RJ", "Brasil"), ("Salvador", "BA", "Brasil"),
           ("Tiradentes", "MG", "Brasil"), ("Porto Seguro", "BA", "Brasil"), ("Jericoacoara", "CE", "Brasil"),
           ("Bonito", "MS", "Brasil"), ("Monte Verde", "MG", "Brasil"), ("Ilhabela", "SP", "Brasil"), ("Maceió", "AL", "Brasil"),
           ("São Miguel dos Milagres", "AL", "Brasil"), ("Santiago", "Chile", "Chile"), ("Natal", "RN", "Brasil"),
           ("Águas de Lindóia", "SP", "Brasil"), ("Holambra", "SP", "Brasil")]


def nome_local(c, uf, pais) -> str:
    return f"{c} - {pais}" if pais != "Brasil" else f"{c}/{uf} - Brasil"


# ===================================================================== acumuladores
@dataclass
class Banco:
    """Dimensoes com chave crescente e as linhas de cada fato."""
    dims: dict = field(default_factory=dict)
    fatos: dict = field(default_factory=lambda: {k: [] for k in (
        "fato_movto_financ", "fato_familia", "fato_investimento", "fato_posicao_investimento", "fato_dia",
        "fato_dia_habito", "fato_avaliacao_fisica", "fato_manutencao_auto", "fato_carga")})

    def chave(self, dim: str, nome: str) -> int:
        d = self.dims.setdefault(dim, {})
        if nome not in d:
            d[nome] = len(d) + 1
        return d[nome]


B = Banco()
for a in AREAS:
    B.chave("area", a)
for c in CATEGORIAS:
    B.chave("cat", c)
for g in GRUPOS:
    B.chave("grupo", g)
for c, uf, p in CIDADES:
    B.chave("local", nome_local(c, uf, p))
CASA = nome_local("Campinas", "SP", "Brasil")


def tag(nome: str, tipo: str) -> int:
    k = B.chave("tag", nome)
    B.dims.setdefault("tag_tipo", {})[nome] = tipo
    return k


def local(cidade: str) -> int:
    for c, uf, p in CIDADES:
        if c == cidade:
            return B.chave("local", nome_local(c, uf, p))
    return -1


# ===================================================================== financeiro (Ale)
FIN = B.fatos["fato_movto_financ"]
FAT_MES: dict[tuple[int, str], float] = {}     # (origem, AAAA-MM da fatura) -> total


def mes_fatura(d: pd.Timestamp, origem: int, k: int = 0) -> pd.Timestamp:
    """Vencimento da k-esima parcela: o cartao fecha no dia 27 e vence no dia 10 do mes seguinte."""
    m = d.to_period("M") + (1 if d.day <= 27 else 2) + k
    return m.to_timestamp() + pd.Timedelta(days=9)


def lanca(d, valor, area, cat, grupo, origem=2, det="", receber=None, pagar="Ale", loc=-1, tg=-1,
          nivel="ANALITICO", parcela=None, fatura=None):
    d = pd.Timestamp(d)
    fluxo = "RECEITA" if valor > 0 else "DESPESA"
    FIN.append({
        "SK_ORIGEM": origem, "SK_DATA": sk(d), "SK_DATA_FATURA": sk(fatura) if fatura is not None else -1,
        "VL_TRANSACAO": r2(valor), "DS_NIVEL": nivel, "DS_TIPO_FLUXO": fluxo, "NR_PARCELA": parcela,
        "DS_DETALHE_ORIGINAL": det or grupo, "DS_PESSOA_PAGAR": pagar if valor < 0 else receber,
        "DS_PESSOA_RECEBER": receber if valor < 0 else "Ale",
        "SK_AREA_FINANC": B.chave("area", area), "SK_CATEGORIA_FINANC": B.chave("cat", cat),
        "SK_GRUPO_FINANC": B.chave("grupo", grupo), "SK_LOCALIZACAO": loc, "SK_TAG": tg,
    })
    if fatura is not None and nivel == "ANALITICO":
        k = (origem, pd.Timestamp(fatura).strftime("%Y-%m"))
        FAT_MES[k] = FAT_MES.get(k, 0.0) - valor


def cartao_de(d: pd.Timestamp) -> int:
    # Nubank ate fev/2022; depois o XP, com o Nubank so para assinaturas
    return 4 if d < pd.Timestamp("2022-03-01") else 3


def compra(d, valor, area, cat, grupo, det="", receber=None, loc=-1, tg=-1, parcelas=1, origem=None):
    """Gasto no cartao: uma linha por parcela, todas com a data da compra."""
    d = pd.Timestamp(d)
    origem = origem or cartao_de(d)
    if parcelas <= 1:
        lanca(d, -valor, area, cat, grupo, origem, det, receber, loc=loc, tg=tg, fatura=mes_fatura(d, origem))
        return
    p = round(valor / parcelas, 2)
    for k in range(parcelas):
        lanca(d, -p, area, cat, grupo, origem, det, receber, loc=loc, tg=tg, parcela=k + 1, fatura=mes_fatura(d, origem, k))


def escolhe(lista, p=None):
    return lista[rng.choice(len(lista), p=p)]


LOJAS = {
    "Almoço": ["Restaurante Sabor da Casa", "Cantina da Praça", "Bistrô Central", "Self-service Bom Gosto"],
    "Lanche": ["Lanches da Esquina"] * 3 + ["Café Avenida"] * 2 + ["Padaria Central"] * 3 + ["PADARIA CENTRAL"],
    "Café da manhã": ["Padaria Central", "Café Avenida"],
    "Janta": ["Cantina Toscana", "iFood", "Bistrô Central"], "Pizza": ["Pizzaria Napoli", "iFood"],
    "Burguer": ["Burger House", "iFood"], "Japa": ["Sushi Kento"], "Sorvete": ["Gelato Mio"],
    "Mercado": ["Mercado Bom Preço", "Supermercado Família"], "Padaria": ["Padaria Central"], "Hortifrut": ["Hortifruti Verde"],
    "Combustivel": ["Posto Avenida"] * 5 + ["Posto Rota 10"] * 3 + ["Posto Avenida 2"], "Uber": ["Uber"] * 5 + ["99"] * 3 + ["99pop"],
    "Estacionamento": ["Estacionamento Centro", "Garagem Rotativa"], "PEDÁGIO": ["Tag Pedágio"],
    "Cinema": ["Cine Parque"], "Bebida": ["Choperia Lúpulo", "Empório Bebidas"], "Butecando": ["Bar do Zé", "Boteco da Vila"],
    "Ingresso": ["Ingresso Rápido"], "Evento": ["Bilheteria Eventos"],
    "Roupas": ["Loja Estilo", "Moda Casual"], "Utencilios": ["Amazon", "Mercado Livre", "Shopee"],
    "Papelaria": ["Papelaria Lápis"], "Fotografia": ["Foto Digital"],
    "Medicamento": ["Farmácia Vida", "Drogaria São Bento"], "Odonto": ["Clínica Sorriso"], "Nutricionista": ["Nutri Equilíbrio"],
    "Exame": ["Laboratório Diagnóstico"], "Suplemento": ["Loja Suplementos Fit"],
    "Streaming": ["Netflix", "Spotify"], "Armazenamento dados": ["Google One"], "Academia": ["Academia Movimento"],
    "Telefonia": ["Operadora Celular"], "Eletrodomestico": ["Casa & Lar", "Magazine Center"],
    "Móvel": ["Móveis Arte", "Casa & Lar"], "Eletro Eletrônico": ["Magazine Center", "Amazon"],
    "Presente Natal": ["Amazon", "Loja Estilo", "Livraria Página"], "Presente Niver": ["Livraria Página", "Loja Estilo"],
    "Lava Jato": ["Lava Rápido Brilho"], "Acessório": ["Peças & Cia"], "Manutenção": ["Auto Center Avenida"],
}


def loja(g):
    return escolhe(LOJAS.get(g, ["Loja"]))


def salario_mes(d: pd.Timestamp) -> float:
    base = {2019: 8200, 2020: 8700, 2021: 9300, 2022: 10100, 2023: 10900, 2024: 11600, 2025: 12300, 2026: 12900}
    ano = d.year if d.month >= 3 else d.year - 1
    return base.get(ano, base[2026] * 1.05 ** (ano - 2026)) if ano >= 2019 else base[2019]


def quinto_util(ano: int, mes: int) -> pd.Timestamp:
    d, n = pd.Timestamp(ano, mes, 1), 0
    while True:
        if d.weekday() < 5 and not e_feriado(d):
            n += 1
            if n == 5:
                return d
        d += pd.Timedelta(days=1)


# ----------------------------------------------------------------- viagens
@dataclass
class Viagem:
    tag: str | None
    ini: str
    fim: str
    cidades: list
    por_dia: float
    hosp: float
    passagem: float = 0.0
    antecedencia: int = 60
    familia: float = 0.0           # hospedagem paga pela conta da casa
    reembolso: float = 0.0
    hosp_texto: bool = False       # hospedagem sem tag, com o destino no texto
    duplicada: bool = False        # um gasto lancado nas duas tabelas


VIAGENS = [
    Viagem("#Brotas_Abr21", "2021-04-16", "2021-04-20", ["Brotas"], 380, 1400, antecedencia=40),
    Viagem("#IlhaGrande_Jul21", "2021-07-09", "2021-07-13", ["Ilha Grande"], 420, 1650, antecedencia=55),
    Viagem("#Curitiba_Out21", "2021-10-12", "2021-10-17", ["Curitiba", "Morretes"], 470, 2300, passagem=1450, antecedencia=90),
    Viagem("#Gramado_Jul22", "2022-07-14", "2022-07-19", ["Gramado", "Canela"], 560, 2900, passagem=1700, antecedencia=120, hosp_texto=True),
    Viagem("#Buzios_Nov22", "2022-11-12", "2022-11-15", ["Búzios"], 450, 1500, antecedencia=60),
    Viagem("#Salvador_Fev23", "2023-02-17", "2023-02-22", ["Salvador"], 480, 2400, passagem=1900, antecedencia=100),
    Viagem("#Tiradentes_Jun23", "2023-06-08", "2023-06-11", ["Tiradentes"], 400, 1100, antecedencia=35),
    Viagem("#PortoSeguro_Out23", "2023-10-11", "2023-10-16", ["Porto Seguro"], 430, 0, passagem=2100, antecedencia=110, familia=3600, duplicada=True),
    Viagem("#Jeri_Jan24", "2024-01-20", "2024-01-24", ["Jericoacoara"], 520, 1800, passagem=1600, antecedencia=80),
    Viagem("#Bonito_Jul24", "2024-07-18", "2024-07-23", ["Bonito"], 650, 2600, passagem=2300, antecedencia=130),
    Viagem("#MonteVerde_Set24", "2024-09-06", "2024-09-08", ["Monte Verde"], 480, 1200, antecedencia=30),
    Viagem("#Reveillon_25", "2024-12-29", "2025-01-02", ["Ilhabela"], 380, 6400, antecedencia=150, reembolso=3900),
    Viagem("#Maceio_Mai25", "2025-05-01", "2025-05-05", ["Maceió", "São Miguel dos Milagres"], 520, 2100, passagem=2200, antecedencia=95, hosp_texto=True),
    Viagem("#Santiago_Set25", "2025-09-10", "2025-09-15", ["Santiago"], 700, 2900, passagem=3400, antecedencia=140),
    Viagem("#Natal_Jul26", "2026-07-06", "2026-07-12", ["Natal"], 560, 0, passagem=3300, antecedencia=170, familia=4200),
    # sem tag: o painel acha pela cidade
    Viagem(None, "2022-04-21", "2022-04-23", ["Holambra"], 520, 0),
    Viagem(None, "2025-03-08", "2025-03-09", ["Águas de Lindóia"], 650, 0),
]


def dias_de_viagem() -> set:
    s = set()
    for v in VIAGENS:
        for d in pd.date_range(v.ini, v.fim):
            s.add(d.normalize())
    return s


EM_VIAGEM = dias_de_viagem()
VIAGEM_DO_DIA = {d: v for v in VIAGENS for d in pd.date_range(v.ini, v.fim)}


def gera_viagens():
    for v in VIAGENS:
        ini, fim = pd.Timestamp(v.ini), pd.Timestamp(v.fim)
        if ini > HOJE:
            continue
        tg = tag(v.tag, "Viagem") if v.tag else -1
        destino = v.cidades[0]
        antes = ini - pd.Timedelta(days=v.antecedencia)
        if v.hosp:
            # hospedagem paga antes, parcelada
            det = f"Hospedagem {destino}"
            compra(antes, v.hosp, "ESTILO DE VIDA", "LAZER", "Hospedagem", det, "Airbnb" if rng.random() < .5 else "Booking",
                   tg=-1 if v.hosp_texto else tg, parcelas=int(rng.choice([2, 3, 4, 5])))
        if v.passagem:
            compra(antes - pd.Timedelta(days=12), v.passagem, "ESTILO DE VIDA", "TRANSPORTE", "Avião",
                   f"Passagem {destino}", "Companhia Aérea", tg=tg, parcelas=int(rng.choice([3, 5, 6])))
        for d in pd.date_range(ini, fim):
            cid = v.cidades[0] if len(v.cidades) == 1 or d < ini + (fim - ini) / 2 else v.cidades[1]
            loc = local(cid)
            orc = v.por_dia * rng.uniform(.7, 1.3)
            for grupo, cat, fr in (("Almoço", "ALIMENTAÇÃO", .32), ("Janta", "ALIMENTAÇÃO", .30), ("Uber", "TRANSPORTE", .10),
                                   ("Passeio", "LAZER", .14), ("Bebida", "LAZER", .08), ("Mercado", "ALIMENTAÇÃO", .06)):
                if rng.random() < .85:
                    compra(d, orc * fr * rng.uniform(.6, 1.4), "ESTILO DE VIDA", cat, grupo,
                           f"{grupo} {cid}", f"{grupo} {cid}", loc=loc, tg=tg)
        if v.reembolso:
            for k in range(4):
                lanca(fim + pd.Timedelta(days=2 + k), v.reembolso / 4, "ESTILO DE VIDA", "LAZER", "Hospedagem",
                      origem=2, det=f"PIX rateio casa {destino}", receber="Ale", pagar="Amigo", tg=tg)
        if v.familia:
            FAM_VIAGEM.append((antes, v.familia, f"Hotel {destino}", tg, local(destino)))
        if v.duplicada:
            # o Ale pagou um jantar no cartao e lancou tambem na planilha da casa
            d = ini + pd.Timedelta(days=1)
            val = 286.40
            compra(d, val, "ESTILO DE VIDA", "ALIMENTAÇÃO", "Janta", f"Janta {destino}", "Restaurante Orla", loc=local(destino), tg=tg)
            FAM_DUP.append((d, val, f"Janta {destino}", tg, local(destino)))


FAM_VIAGEM: list = []
FAM_DUP: list = []


# ----------------------------------------------------------------- rotina (usada por financas e saude)
def plano_rotina() -> pd.DataFrame:
    """Um registro por dia desde 2019: trabalho, Nina em casa, disciplina latente."""
    dias = pd.date_range(INICIO, HOJE, freq="D")
    ferias = set()
    for ano in range(2019, HOJE.year + 1):
        for ini, n in ((f"{ano}-01-08", 10), (f"{ano}-07-15", 5)):
            ferias |= set(pd.date_range(ini, periods=n))
    disc, linhas = 0.0, []
    for d in dias:
        disc = 0.93 * disc + rng.normal(0, .28)     # fases boas e ruins que duram semanas
        util = d.weekday() < 5 and not e_feriado(d)
        trab = util and d not in ferias and d not in EM_VIAGEM and rng.random() > .04
        semana = d.isocalendar()[1]
        nina = (semana % 2 == 0) or (d.weekday() in (2, 3) and rng.random() < .8)
        linhas.append({"data": d, "trabalho": trab, "nina": bool(nina) and d not in EM_VIAGEM, "disc": disc,
                       "fds": d.weekday() >= 5, "feriado": e_feriado(d), "viagem": d in EM_VIAGEM})
    return pd.DataFrame(linhas).set_index("data")


def gera_financeiro(rot: pd.DataFrame):
    loc_casa = local("Campinas")
    ultimo_mes = None
    for d, r in rot.iterrows():
        mes = d.strftime("%Y-%m")
        if mes != ultimo_mes:
            ultimo_mes = mes
            mensais(d)
        if r.viagem:
            continue
        loc = loc_casa if rng.random() < .72 else -1
        trab, folga = r.trabalho, not r.trabalho
        # comer fora: dia de trabalho almoca perto do escritorio; folga sai a noite
        if trab and rng.random() < .55:
            g = escolhe(["Almoço", "Lanche"], [.65, .35])
            compra(d, rng.gamma(4, 8 if g == "Lanche" else 9), "ESTILO DE VIDA", "ALIMENTAÇÃO", g, receber=loja(g), loc=loc)
        if folga and rng.random() < .62:
            g = escolhe(["Janta", "Pizza", "Burguer", "Japa", "Sorvete", "Café da manhã"], [.3, .2, .2, .12, .08, .1])
            compra(d, rng.gamma(4, 17), "ESTILO DE VIDA", "ALIMENTAÇÃO", g, receber=loja(g), loc=loc)
        if rng.random() < (.12 if trab else .05):
            compra(d, rng.gamma(3, 8), "ESTILO DE VIDA", "TRANSPORTE", "Uber", receber=loja("Uber"), loc=loc)
        if trab and rng.random() < .3:
            compra(d, rng.uniform(8, 22), "ESTILO DE VIDA", "TRANSPORTE", "Estacionamento", receber=loja("Estacionamento"), loc=loc)
        if rng.random() < .13:
            g = escolhe(["Padaria", "Hortifrut", "Mercado"], [.5, .2, .3])
            compra(d, rng.gamma(3, 13), "ESTILO DE VIDA", "ALIMENTAÇÃO", g, receber=loja(g), loc=loc)
        if r.fds and rng.random() < .28:
            g = escolhe(["Cinema", "Bebida", "Butecando", "Ingresso", "Evento"], [.25, .25, .3, .1, .1])
            compra(d, rng.gamma(3, 25), "ESTILO DE VIDA", "LAZER", g, receber=loja(g), loc=loc)
        if rng.random() < .045:
            g = escolhe(["Roupas", "Utencilios", "Papelaria", "Fotografia"], [.45, .4, .1, .05])
            v = rng.gamma(2.2, 70)
            cat = "Vestuário" if g == "Roupas" else "PESSOAL"
            compra(d, v, "ESTILO DE VIDA", cat, g, receber=loja(g), loc=loc, parcelas=3 if v > 300 else 1)
        if rng.random() < .04:
            compra(d, rng.gamma(2.5, 25), "ESTILO DE VIDA", "SAÚDE", "Medicamento", receber=loja("Medicamento"), loc=loc)
        if d.weekday() in (0, 3) and rng.random() < .45:
            compra(d, rng.uniform(190, 300), "GASTOS ESSENCIAIS", "TRANSPORTE", "Combustivel",
                   receber=loja("Combustivel"), loc=loc)
        if rng.random() < .003:
            g = escolhe(["Eletrodomestico", "Móvel", "Eletro Eletrônico"])
            v = rng.uniform(900, 3600)
            compra(d, v, "ESTILO DE VIDA", "CASA", g, f"{g} {loja(g)}", loja(g), loc=loc, parcelas=int(rng.choice([6, 8, 10])))
        # dezembro: presentes
        if d.month == 12 and 5 <= d.day <= 23 and rng.random() < .22:
            compra(d, rng.gamma(2.5, 70), "ESTILO DE VIDA", "PRESENTE", "Presente Natal", receber=loja("Presente Natal"), loc=loc)
        if rng.random() < .008:
            compra(d, rng.gamma(3, 45), "ESTILO DE VIDA", "PRESENTE", "Presente Niver", receber=loja("Presente Niver"), loc=loc)


def mensais(d: pd.Timestamp):
    """O que cai uma vez por mes: salario, contas, assinaturas, aporte."""
    ano, mes = d.year, d.month
    pag = quinto_util(ano, mes)
    if pag <= HOJE:
        s = salario_mes(d)
        lanca(pag, s, "RENDA", "TRABALHO", "Salário", 2, "SALARIO EMPRESA", receber="Ale", pagar="Empresa")
        if mes == 11:
            lanca(pd.Timestamp(ano, 11, 28), s / 2, "RENDA", "TRABALHO", "13º Salário", 2, "13 SALARIO 1A PARC", pagar="Empresa")
        if mes == 12:
            lanca(pd.Timestamp(ano, 12, 18), s / 2 * .82, "RENDA", "TRABALHO", "13º Salário", 2, "13 SALARIO 2A PARC", pagar="Empresa")
        if mes == 2 and ano >= 2020:
            lanca(pd.Timestamp(ano, 2, 20), s * rng.uniform(.9, 1.6), "RENDA", "TRABALHO", "PLR", 2, "PLR EMPRESA", pagar="Empresa")
        lanca(pd.Timestamp(ano, mes, 1) + pd.offsets.MonthEnd(0), rng.uniform(3, 18), "RENDA", "RENDIMENTO", "Rendimento", 2,
              "REND PAGO APLIC AUT", pagar="Itau")
    def fixo(dia, valor, area, cat, grupo, det, receber, origem=2, ini=None):
        dd = pd.Timestamp(ano, mes, min(dia, 28))
        if dd > HOJE or (ini and dd < pd.Timestamp(ini)):
            return
        if origem == 2:
            lanca(dd, -valor, area, cat, grupo, 2, det, receber)
        else:
            compra(dd, valor, area, cat, grupo, det, receber, origem=origem)
    escola = 820 * 1.07 ** max(0, ano - 2021)
    fixo(10, escola, "GASTOS ESSENCIAIS", "EDUCAÇÃO", "Escola", "MENSALIDADE COLEGIO", "Colégio Horizonte", ini="2021-02-01")
    if mes == 2:
        fixo(3, 540, "GASTOS ESSENCIAIS", "EDUCAÇÃO", "Material Escolar", "Material escolar", "Papelaria Lápis", origem=3, ini="2022-03-01")
    fixo(12, 39.9, "ESTILO DE VIDA", "ENTRETENIMENTO", "Streaming", "Netflix", "Netflix", origem=cartao_de(d))
    fixo(15, 21.9, "ESTILO DE VIDA", "ENTRETENIMENTO", "Streaming", "Spotify", "Spotify", origem=cartao_de(d))
    fixo(18, 9.99, "ESTILO DE VIDA", "PESSOAL", "Armazenamento dados", "Google One", "Google One", origem=cartao_de(d))
    fixo(6, 119.9 if ano >= 2023 else 99.9, "ESTILO DE VIDA", "SAÚDE", "Academia", "Academia Movimento", "Academia Movimento", origem=3, ini="2022-03-01")
    fixo(20, 89.9, "GASTOS ESSENCIAIS", "PESSOAL", "Telefonia", "Operadora Celular", "Operadora Celular", origem=3, ini="2022-03-01")
    fixo(14, 210 + 12 * (ano - 2019), "GASTOS ESSENCIAIS", "TRANSPORTE", "Seguro Carro", "SEGURO AUTO", "Seguro Auto Total")
    fixo(7, 520 * 1.08 ** (ano - 2019), "GASTOS ESSENCIAIS", "SAÚDE", "Plano Saude", "PLANO DE SAUDE", "Operadora de Saúde")
    fixo(22, rng.uniform(40, 60), "ESTILO DE VIDA", "TRANSPORTE", "Lava Jato", "Lava Rápido Brilho", "Lava Rápido Brilho", origem=3, ini="2022-03-01")
    fixo(25, rng.uniform(25, 60), "GASTOS ESSENCIAIS", "TRANSPORTE", "PEDÁGIO", "Tag Pedágio", "Tag Pedágio", origem=3, ini="2022-03-01")
    if mes in (1, 2, 3):
        fixo(18, 1050 if ano < 2025 else 1420, "GASTOS ESSENCIAIS", "TRANSPORTE", "IPVA", f"IPVA {ano} {mes}/3", "Detran")
    if mes == 4:
        fixo(8, 165, "GASTOS ESSENCIAIS", "TRANSPORTE", "Licenciamento", f"Licenciamento {ano}", "Detran")
    if mes in (3, 9):
        fixo(16, rng.uniform(220, 380), "ESTILO DE VIDA", "SAÚDE", "Odonto", "Clínica Sorriso", "Clínica Sorriso", origem=cartao_de(d))
    if mes == 6 and ano >= 2024:
        fixo(9, 280, "ESTILO DE VIDA", "SAÚDE", "Exame", "Check-up anual", "Laboratório Diagnóstico", origem=3)
    if ano >= 2024 and mes % 2 == 0:
        fixo(11, 180, "ESTILO DE VIDA", "SAÚDE", "Nutricionista", "Consulta nutri", "Nutri Equilíbrio", origem=3)
    if ano >= 2024 and mes % 3 == 1:
        fixo(19, rng.uniform(150, 230), "ESTILO DE VIDA", "ALIMENTAÇÃO", "Suplemento", "Whey e creatina", "Loja Suplementos Fit", origem=3)
    # conta da casa: o deposito do Ale (o mesmo valor entra em fato_familia)
    dep = deposito_ale(pd.Timestamp(ano, mes, 5))
    if dep and pd.Timestamp(ano, mes, 5) <= HOJE:
        lanca(pd.Timestamp(ano, mes, 5), -dep, "GASTOS ESSENCIAIS", "CASA", "Conta Familia", 2, "PIX CONTA CASA", "Conta Familia")
    # aporte na corretora (o mesmo valor entra em fato_investimento)
    ap = APORTES.get((ano, mes))
    if ap:
        lanca(ap[0], -ap[1], "INVESTIMENTO", "INVESTIMENTO", "Investimento", 2, "TED XP INVESTIMENTOS", "XP Investimentos")
    # cofrinho: guarda no comeco do ano, usa no fim
    if mes in (3, 4, 5) and pd.Timestamp(ano, mes, 12) <= HOJE:
        lanca(pd.Timestamp(ano, mes, 12), -rng.uniform(600, 1500), "TRANSFERENCIA", "INVESTIMENTO", "Cofrinho", 2, "APLICACAO COFRINHO", "Itau")
    if mes == 12 and pd.Timestamp(ano, 12, 2) <= HOJE:
        lanca(pd.Timestamp(ano, 12, 2), rng.uniform(2000, 3500), "TRANSFERENCIA", "INVESTIMENTO", "Cofrinho", 2, "RESGATE COFRINHO", pagar="Itau")


def deposito_ale(d: pd.Timestamp) -> float | None:
    if d < pd.Timestamp("2023-01-01"):
        return None
    meses = (d.year - 2023) * 12 + d.month - 1
    return round(2950 + 16 * meses + rng.uniform(-40, 40), 2)


def deposito_lia(d: pd.Timestamp) -> float:
    meses = (d.year - 2023) * 12 + d.month - 1
    return round(1980 + 11 * meses + rng.uniform(-60, 60), 2)


# ----------------------------------------------------------------- carro
CARROS = {"Sedan": {"sk": 1, "ini": "2016-03-10", "km0": 61000, "ritmo": 38},
          "SUV": {"sk": 2, "ini": "2025-05-20", "km0": 31500, "ritmo": 46}}
COMPRA_SUV = "2025-05-20"
SAIDA_SEDAN = "2025-06-10"
CAT_AUTO = ["Alarme", "Alinhamento", "Amortecedor", "Ar Condicionado", "Balanceamento", "Bandeja", "Bateria", "Bieleta",
            "Bucha", "Chave", "Correia", "Direção", "Filtro", "Fluido", "Freio", "Fusivel", "Lampada", "Leque", "Limpeza",
            "Liquido Arrefecimento", "Motor", "Mão de Obra", "Palheta", "Pneu", "Polia", "Radiador", "Rastreamento",
            "Rolamento", "Sensor", "Tampa", "Vela", "Vidro", "regulador", "Óleo"]
INTERVALO = {"Alinhamento": 10000, "Amortecedor": 50000, "Balanceamento": 10000, "Bateria": 20000, "Correia": 50000,
             "Filtro": 10000, "Fluido": 20000, "Freio": 20000, "Liquido Arrefecimento": 20000, "Palheta": 10000,
             "Pneu": 40000, "Vela": 40000, "Óleo": 5000}
PECA = {"Óleo": 260, "Filtro": 95, "Alinhamento": 120, "Balanceamento": 90, "Freio": 420, "Fluido": 110, "Pneu": 2100,
        "Vela": 380, "Correia": 690, "Bateria": 620, "Palheta": 85, "Amortecedor": 1900, "Liquido Arrefecimento": 140,
        "Mão de Obra": 350, "Lampada": 45, "Ar Condicionado": 260, "Bucha": 310, "Bieleta": 240, "Sensor": 380}
PLANO_SUV = [("Óleo", "Motor", 10000, 12, "Trocar"), ("Filtro", "Motor", 10000, 12, "Trocar"),
                 ("Alinhamento", "Suspensão", 10000, 12, "Verificar"), ("Freio", "Freios", 20000, 24, "Inspecionar"),
                 ("Fluido", "Freios", 20000, 24, "Trocar"), ("Palheta", "Carroceria", 10000, 12, "Trocar"),
                 ("Bateria", "Elétrica", 40000, 36, "Verificar"), ("Vela", "Motor", 40000, 36, "Trocar"),
                 ("Liquido Arrefecimento", "Arrefecimento", 40000, 48, "Trocar"), ("Pneu", "Rodas", 40000, 48, "Verificar"),
                 ("Correia", "Motor", 60000, 60, "Trocar"), ("Amortecedor", "Suspensão", 60000, 60, "Inspecionar")]


def gera_carro():
    of = B.fatos["fato_manutencao_auto"]
    visitas = {"Sedan": ["2019-02-14", "2019-08-20", "2020-03-05", "2020-11-18", "2021-06-09", "2022-01-25", "2022-08-30",
                          "2023-03-21", "2023-10-17", "2024-05-08", "2024-12-03", SAIDA_SEDAN],
               "SUV": ["2025-11-12", "2026-06-16"]}
    nr = 0
    ultimo = {}
    for carro, datas in visitas.items():
        c = CARROS[carro]
        for i, dt in enumerate(datas):
            d = pd.Timestamp(dt)
            if d > HOJE:
                continue
            nr += 1
            km = int(c["km0"] + c["ritmo"] * (d - pd.Timestamp(c["ini"])).days * rng.uniform(.95, 1.05))
            # o que venceu desde a ultima troca, mais um extra eventual
            itens = [k for k, iv in INTERVALO.items() if km - ultimo.get((carro, k), c["km0"] - iv * rng.uniform(.3, .9)) >= iv * .9]
            itens = sorted(set(itens + ["Óleo", "Filtro", "Mão de Obra"] + ([escolhe(["Bucha", "Bieleta", "Sensor", "Lampada", "Ar Condicionado"])]
                                                                          if rng.random() < .5 else [])))
            total = 0.0
            for it in itens:
                v = PECA.get(it, 150) * rng.uniform(.85, 1.2) * (1.04 ** (d.year - 2019))
                total += v
                ultimo[(carro, it)] = km
                of.append({"SK_DATA": sk(d), "SK_VEICULO": c["sk"], "SK_CATEGORIA_MANUTENCAO": CAT_AUTO.index(it) + 1,
                           "NR_VISITA": nr, "NR_KM": km, "VL_GASTO": r2(v), "NR_QUANTIDADE": 4 if it == "Pneu" else 1,
                           "DS_TIPO": "Serviço" if it in ("Mão de Obra", "Alinhamento", "Balanceamento") else "Peça",
                           "DS_ITEM": f"{it} - {carro}", "DS_LOCAL": "Concessionária" if carro == "SUV" else "Auto Center Avenida",
                           "DS_OBSERVACAO": None, "FL_PREVENTIVA": "S" if it in INTERVALO or it == "Mão de Obra" else "N"})
            # a mesma oficina no financeiro, parcelada no cartao
            compra(d, total, "ESTILO DE VIDA", "TRANSPORTE", "Manutenção", f"Revisão {carro} {km:,} km".replace(",", "."),
                   loja("Manutenção"), loc=local("Campinas"), tg=tag(f"#{carro}", "Marcação"), parcelas=3 if total > 1500 else 1,
                   origem=cartao_de(d))
            c["ultima"] = (d, km)
            c["visitas"] = c.get("visitas", 0) + 1
    # troca de carro: compra do SUV a vista, venda do sedan em quatro vezes
    if pd.Timestamp(COMPRA_SUV) <= HOJE:
        lanca(COMPRA_SUV, -78900, "ESTILO DE VIDA", "TRANSPORTE", "Compra Carro", 2, "Compra SUV", "Concessionária",
              tg=tag("#SUV", "Marcação"))
        for k in range(4):
            d = pd.Timestamp("2025-06-20") + pd.DateOffset(months=k)
            if d <= HOJE:
                lanca(d, 13500, "VENDA", "VENDA", "Venda Sedan", 2, f"Venda Sedan {k + 1}/4", pagar="Comprador")


# ----------------------------------------------------------------- investimentos
ATIVOS = [
    # cd, nome, tipo, classe, subclasse, subtipo posicao, peso, retorno mes (preco), provento mes, taxa
    ("CDB ALFA 112 CDI", "CDB BANCO ALFA S.A.", "Renda Fixa", "Renda Fixa", "CDB", "CDB", .16, .0085, 0, (112, "% CDI")),
    ("LCA BETA 94 CDI", "LCA BANCO BETA S.A.", "Renda Fixa", "Renda Fixa", "LCA", "LCA", .10, .0080, 0, (94, "% CDI")),
    ("TESOURO IPCA 2035", "TESOURO IPCA+ 2035", "Renda Fixa", "Renda Fixa", "Tesouro", "TREASURY", .11, .0078, 0, (6.1, "IPCA +")),
    ("CDB GAMA PRE", "CDB BANCO GAMA S.A.", "Renda Fixa", "Renda Fixa", "CDB", "CDB", .05, .0092, 0, (13.2, "Pré")),
    ("FUNDO HORIZONTE FIM", "HORIZONTE MACRO FIC FIM", "Fundo", "Fundos de Investimento", "Multimercado", "MULTIMARKET_FUND", .07, .0070, 0, None),
    ("FUNDO CREDITO FIRF", "CREDITO PRIVADO FIRF CP", "Fundo", "Fundos de Investimento", "Renda Fixa", "FIXED_INCOME_FUND", .06, .0088, 0, None),
    ("HGLG11", "CSHG LOGISTICA FII", "FII", "Fundos Imobiliários", "Logística", "REAL_ESTATE_FUND", .07, .0010, .0078, None),
    ("KNRI11", "KINEA RENDA IMOBILIARIA FII", "FII", "Fundos Imobiliários", "Híbrido", "REAL_ESTATE_FUND", .06, .0005, .0072, None),
    ("XPML11", "XP MALLS FII", "FII", "Fundos Imobiliários", "Varejo", "REAL_ESTATE_FUND", .05, .0012, .0080, None),
    ("MXRF11", "MAXI RENDA FII", "FII", "Fundos Imobiliários", "Papel", "REAL_ESTATE_FUND", .04, -.0005, .0095, None),
    ("ITSA4", "ITAUSA PN", "Ação", "Renda Variável", "Ações", "STOCK", .05, .0080, .0025, None),
    ("TAEE11", "TAESA UNT", "Ação", "Renda Variável", "Ações", "STOCK", .05, .0050, .0040, None),
    ("BBSE3", "BB SEGURIDADE ON", "Ação", "Renda Variável", "Ações", "STOCK", .04, .0090, .0045, None),
    ("WEGE3", "WEG ON", "Ação", "Renda Variável", "Ações", "STOCK", .05, .0120, .0008, None),
]
INVESTBACK = ("FUNDO INVESTBACK", "TREND INVESTBACK FIC FI", "Fundo", "Fundos de Investimento", "Renda Fixa", "FIXED_INCOME_FUND")
APORTES: dict[tuple[int, int], tuple[pd.Timestamp, float]] = {}


def planeja_aportes():
    d = pd.Timestamp("2021-11-08")
    while d <= HOJE:
        n = (d.year - 2021) * 12 + d.month - 11
        v = round(1600 + 36 * n + rng.uniform(-150, 150), -1)
        if d.month == 12:
            v += 2500       # parte do 13o
        if d.month == 2:
            v += 4000       # parte da PLR
        APORTES[(d.year, d.month)] = (d, v)
        d = (d + pd.DateOffset(months=1)).replace(day=8)


def gera_investimentos():
    inv = B.fatos["fato_investimento"]
    ativos = {a[0]: {"def": a, "sk": i + 1, "valor": 0.0, "custo": 0.0, "cotas": 0.0} for i, a in enumerate(ATIVOS)}
    sk_ib = len(ATIVOS) + 1
    sk_btc = len(ATIVOS) + 2
    caixa = 0.0
    n = 0

    def mov(d, valor, cat, cd_sk, det, fluxo=None):
        nonlocal caixa, n
        caixa += valor
        n += 1
        inv.append({"SK_LANCAMENTO": n, "SK_ORIGEM": 1, "SK_DATA_MOVIMENTACAO": sk(d), "SK_DATA_LIQUIDACAO": sk(d),
                    "SK_ATIVO": cd_sk, "SK_CATEGORIA_INVESTIMENTO": [c for c, _ in CAT_INVEST].index(cat) + 1,
                    "VL_TRANSACAO": r2(valor), "VL_SALDO_MOMENTO": r2(caixa),
                    "DS_TIPO_FLUXO": fluxo or ("ENTRADA" if valor > 0 else "SAIDA"), "DS_DETALHE_ORIGINAL": det,
                    "FL_RENDIMENTO": "S" if cat in ("Dividendo", "Taxa de Remuneração", "Investback") else "N"})

    meses = pd.period_range("2021-11", HOJE.to_period("M"), freq="M")
    for m in meses:
        ini = m.to_timestamp()
        # 1. mercado anda (precos e renda fixa), proventos caem no caixa
        for cd, a in ativos.items():
            _, _, _, classe, _, _, _, ret, prov, _ = a["def"]
            choque = rng.normal(0, .045 if classe in ("Renda Variável",) else .025 if classe == "Fundos Imobiliários" else .004)
            a["valor"] *= 1 + ret + choque
            if prov and a["valor"] > 0:
                if classe == "Fundos Imobiliários" or (classe == "Renda Variável" and m.month % 3 == 0):
                    p = a["valor"] * prov * (3 if classe == "Renda Variável" else 1) * rng.uniform(.85, 1.15)
                    d = ini + pd.Timedelta(days=int(rng.integers(13, 25)))
                    if d <= HOJE:
                        mov(d, p, "Dividendo", a["sk"], f"{'Rendimento' if classe == 'Fundos Imobiliários' else 'Dividendos'} {cd}")
        # juros semestrais da LCA e do Tesouro, IR na fonte
        if m.month in (6, 12):
            for cd in ("LCA BETA 94 CDI", "TESOURO IPCA 2035"):
                a = ativos[cd]
                if a["valor"] > 0:
                    j = a["valor"] * .025
                    a["valor"] -= j
                    d = ini + pd.Timedelta(days=14)
                    if d <= HOJE:
                        mov(d, j, "Dividendo", a["sk"], f"Pgto Juros {cd}")
                        if cd.startswith("TESOURO"):
                            mov(d, -j * .15, "IR", a["sk"], f"IR s/ juros {cd}")
        # aluguel de acoes (BTC) de vez em quando
        if rng.random() < .35 and ativos["ITSA4"]["valor"] > 1000:
            d = ini + pd.Timedelta(days=int(rng.integers(3, 27)))
            if d <= HOJE:
                mov(d, ativos["ITSA4"]["valor"] * .003, "Taxa de Remuneração", sk_btc, "Aluguel BTC ITSA4")
        # 2. aporte e compras pelo peso-alvo
        ap = APORTES.get((m.year, m.month))
        if ap and ap[0] <= HOJE:
            d = ap[0]
            mov(d, ap[1], "Transferência", -1, "TED recebida Itaú")
            # retirada para a entrada do apartamento
        if (m.year, m.month) == (2024, 2):
            d = pd.Timestamp("2024-02-19")
            for cd in ("CDB ALFA 112 CDI", "FUNDO CREDITO FIRF"):
                a = ativos[cd]
                v = a["valor"] * .7
                a["valor"] -= v
                a["custo"] *= .3
                mov(d, v, "Resgate", a["sk"], f"Resgate {cd}")
            mov(pd.Timestamp("2024-02-20"), -min(caixa, 30000), "Retirada", -1, "TED enviada Itaú")
        if caixa > 300 and ap and ap[0] <= HOJE:
            d = ap[0] + pd.Timedelta(days=1)
            tot = sum(a["valor"] for a in ativos.values()) + caixa
            falta = {cd: max(0.0, a["def"][6] * tot - a["valor"]) for cd, a in ativos.items()}
            soma = sum(falta.values()) or 1
            verba = caixa - 100
            for cd, f in falta.items():
                v = verba * f / soma
                if v < 50:
                    continue
                a = ativos[cd]
                a["valor"] += v
                a["custo"] += v
                if a["def"][3] in ("Fundos Imobiliários", "Renda Variável"):
                    mov(d, -v, "Compra", a["sk"], f"COMPRA {cd}")
                    mov(d, -v * .0003, "Emolumentos", a["sk"], f"Emolumentos {cd}")
                else:
                    mov(d, -v, "Aplicação", a["sk"], f"Aplicação {a['def'][1]}")
        # investback do cartao XP: ~0,5% da fatura do mes anterior
        fat = FAT_MES.get((3, (m - 1).strftime("%Y-%m")), 0)
        d = ini + pd.Timedelta(days=15)
        if fat > 0 and d <= HOJE:
            mov(d, fat * .005 * rng.uniform(.9, 1.1), "Investback", sk_ib, "Investback cartão XP")
    for a in ativos.values():
        a["cotas"] = round(a["valor"] / (100 if a["def"][2] in ("FII", "Ação") else 1), 4)
    return ativos, caixa, sk_ib, sk_btc


def gera_posicao(ativos: dict, caixa: float, sk_ib: int):
    pos = B.fatos["fato_posicao_investimento"]
    bronze = []
    ib = sum(r["VL_TRANSACAO"] for r in B.fatos["fato_investimento"] if r["SK_ATIVO"] == sk_ib)
    lista = [(cd, a) for cd, a in ativos.items() if a["valor"] > 1]
    lista.append((INVESTBACK[0], {"def": (*INVESTBACK, 0, 0, 0, None), "sk": sk_ib, "valor": ib * 1.06, "custo": ib}))
    for i in range(18, -1, -1):
        d = HOJE - pd.Timedelta(days=i)
        if d.weekday() >= 5:
            continue
        for cd, a in lista:
            cdd, nome, tipo, classe, sub, subtipo, *_ = a["def"]
            fator = 1 - i * .0004 + rng.normal(0, .002 if classe != "Renda Variável" else .01)
            bruto = a["valor"] * fator
            ganho = max(0.0, bruto - a["custo"])
            liq = bruto - (ganho * .15 if classe in ("Renda Fixa", "Fundos de Investimento") and sub != "LCA" else 0)
            h = hash_de("pos", cd, sk(d))
            pos.append({"SK_DATA": sk(d), "SK_ORIGEM": 1, "SK_ATIVO": a["sk"], "CD_ATIVO_ORIGEM": cd, "NM_ATIVO_ORIGEM": nome,
                        "DS_TIPO": tipo, "DS_SUBTIPO": subtipo, "DS_SITUACAO": "ACTIVE",
                        "QT_COTAS": round(bruto / 100, 4) if tipo in ("FII", "Ação") else None,
                        "VL_COTA": 100.0 if tipo in ("FII", "Ação") else None,
                        "VL_BRUTO": r2(bruto), "VL_LIQUIDO": r2(liq), "VL_RESGATAVEL": r2(liq), "VL_APLICADO": r2(a["custo"]),
                        "VL_TAXAS": 0.0, "DT_REFERENCIA": d.date(),
                        "DT_VENCIMENTO": {"CDB": date(2028, 5, 15), "LCA": date(2027, 3, 22), "TREASURY": date(2035, 5, 15)}.get(subtipo),
                        "HASH_NEGOCIO": h})
            taxa = a["def"][9] if len(a["def"]) > 9 else None
            bronze.append({"hash_negocio": h, "vl_taxa": taxa[0] if taxa else None, "ds_tipo_taxa": taxa[1] if taxa else None,
                           "vl_rentab_12m": round(float(rng.uniform(8, 15) if classe != "Renda Variável" else rng.uniform(-6, 24)), 2)})
    # a "foto do app": total por classe, como a corretora mostra
    ultimo = [p for p in pos if p["SK_DATA"] == max(x["SK_DATA"] for x in pos)]
    def classe_app(p):
        cd = p["CD_ATIVO_ORIGEM"]
        if p["DS_SUBTIPO"] == "REAL_ESTATE_FUND":
            return "Fundos Listados"
        if p["DS_SUBTIPO"] == "STOCK":
            return "Renda Variável Brasil"
        if "IPCA" in cd:
            return "Inflação"
        if "PRE" in cd:
            return "Prefixado"
        if p["DS_SUBTIPO"] == "MULTIMARKET_FUND":
            return "Multimercado"
        return "Pós-fixado"
    cls: dict = {}
    for p in ultimo:
        c = cls.setdefault(classe_app(p), {"valor": 0.0, "custo": 0.0})
        c["valor"] += p["VL_BRUTO"]
        c["custo"] += p["VL_APLICADO"] or 0
    ordem = ["Pós-fixado", "Renda Variável Brasil", "Fundos Listados", "Inflação", "Multimercado", "Prefixado"]
    classes = [{"nome": n, "valor": r2(cls[n]["valor"]), "rent": r2(100 * (cls[n]["valor"] / cls[n]["custo"] - 1)) if cls[n]["custo"] else None}
               for n in ordem if n in cls]
    classes.append({"nome": "Saldo em conta", "valor": r2(caixa), "rent": None})
    app = {"_sobre": "Foto da carteira por classe, gerada pelo gerador de dados ficticios da demonstracao.",
           "data": HOJE.strftime("%Y-%m-%d"), "total": r2(sum(c["valor"] for c in classes)), "classes": classes}
    APP_JSON.parent.mkdir(parents=True, exist_ok=True)
    APP_JSON.write_text(json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8")
    return pd.DataFrame(bronze)


# ----------------------------------------------------------------- familia
def gera_familia():
    fam = B.fatos["fato_familia"]
    P = {"ALE": 11, "Conta": 12, "LIA": 14}
    t_apto = tag("#Apartamento", "Imóvel")
    t_ref = tag("#Reforma", "Imóvel")
    t_res = tag("#EmpreendimentoResort", "Marcação")

    def f(d, valor, area, cat, grupo, det, pessoa="Conta", pago=None, tg=-1, loc=-1, receber=None):
        d = pd.Timestamp(d)
        futuro = d > HOJE
        fam.append({"SK_DATA": sk(d), "SK_DATA_PAGAMENTO": -1 if futuro else sk(d), "SK_PESSOA": P[pessoa],
                    "VL_TRANSACAO": r2(valor), "DS_TIPO_FLUXO": "RECEITA" if valor > 0 else "DESPESA",
                    "DS_DETALHE_ORIGINAL": det, "DS_PESSOA_RECEBER": receber,
                    "SK_AREA_FINANC": B.chave("area", area), "SK_CATEGORIA_FINANC": B.chave("cat", cat),
                    "SK_GRUPO_FINANC": B.chave("grupo", grupo), "FL_FUTURO": "S" if futuro else "N",
                    "FL_PAGO": ("N" if futuro else "S") if pago is None else pago, "SK_LOCALIZACAO": loc, "SK_TAG": tg})

    fim_contas = (HOJE + pd.DateOffset(months=1)).to_period("M")
    for m in pd.period_range("2023-01", fim_contas, freq="M"):
        ini = m.to_timestamp()
        d5 = ini + pd.Timedelta(days=4)
        if d5 <= HOJE:
            f(d5, deposito_ale(d5) or 0, "RECEITA", "APORTE", "Aporte", "PIX Ale", "ALE")
            f(d5 + pd.Timedelta(days=1), deposito_lia(d5), "RECEITA", "APORTE", "Aporte", "PIX Lia", "LIA")
        inf = 1.045 ** (m.year - 2023)
        luz = 190 * inf * (1.25 if m.month in (1, 2, 12) else 1) * rng.uniform(.85, 1.15)
        for dia, v, grupo, cat, det in ((10, 540 * inf, "Condomínio", "MORADIA", "Condomínio"),
                                        (15, luz, "Luz", "MORADIA", "Conta de luz"),
                                        (16, 105 * inf * rng.uniform(.85, 1.2), "Água", "MORADIA", "Conta de água"),
                                        (18, 119.9, "Internet", "CASA", "Internet fibra"),
                                        (20, 62 * rng.uniform(.8, 1.3), "Gás", "MORADIA", "Gás")):
            f(ini + pd.Timedelta(days=dia - 1), -v, "GASTOS ESSENCIAIS", cat, grupo, det, receber=grupo)
        if 2 <= m.month <= 11:
            f(ini + pd.Timedelta(days=9), -128 * inf, "GASTOS ESSENCIAIS", "MORADIA", "IPTU", f"IPTU {m.month - 1}/10")
        # mercado da casa, semanal, as vezes pago direto por um dos dois
        for sem in range(4):
            d = ini + pd.Timedelta(days=2 + 7 * sem + int(rng.integers(0, 3)))
            if d <= HOJE:
                quem = escolhe(["Conta", "ALE", "LIA"], [.7, .15, .15])
                f(d, -rng.uniform(200, 340) * inf, "GASTOS ESSENCIAIS", "ALIMENTAÇÃO", "Mercado", "Mercado da semana", quem,
                  receber="Supermercado Família", loc=local("Campinas"))
        for k in (6, 20):
            d = ini + pd.Timedelta(days=k)
            if d <= HOJE:
                f(d, -190, "ESTILO DE VIDA", "CASA", "Diarista", "Diarista")
        if rng.random() < .5 and ini + pd.Timedelta(days=12) <= HOJE:
            f(ini + pd.Timedelta(days=12), -rng.uniform(40, 160), "GASTOS ESSENCIAIS", "SAÚDE", "Farmácia", "Farmácia", receber="Farmácia Vida")
        if rng.random() < .4 and ini + pd.Timedelta(days=22) <= HOJE:
            f(ini + pd.Timedelta(days=22), -rng.uniform(80, 220), "ESTILO DE VIDA", "CASA", "Pet", "Pet shop", receber="Pet shop")

    # apartamento: entrada em 2024 (com deposito extra dos dois) e financiamento ate depois de hoje
    f("2024-02-21", 30000, "RECEITA", "APORTE", "Aporte", "PIX Ale - entrada apto", "ALE")
    f("2024-02-22", 21000, "RECEITA", "APORTE", "Aporte", "PIX Lia - entrada apto", "LIA")
    f("2024-02-26", -48000, "GASTOS ESSENCIAIS", "MORADIA", "Entrada", "Entrada apartamento", tg=t_apto)
    f("2024-03-12", -3900, "GASTOS ESSENCIAIS", "MORADIA", "ITBI", "ITBI apartamento", tg=t_apto)
    f("2024-03-19", -1850, "GASTOS ESSENCIAIS", "MORADIA", "Cartório", "Registro em cartório", tg=t_apto)
    for m in pd.period_range("2024-04", HOJE.to_period("M") + 14, freq="M"):
        f(m.to_timestamp() + pd.Timedelta(days=7), -2380, "GASTOS ESSENCIAIS", "MORADIA", "Financiamento",
          f"Financiamento apto {m.strftime('%m/%Y')}", tg=t_apto)
    for i, (d, v) in enumerate((("2024-05-14", 2600), ("2024-06-11", 1900), ("2024-07-09", 3400))):
        f(d, -v, "ESTILO DE VIDA", "CASA", "Reforma", f"Reforma cozinha {i + 1}/3", tg=t_ref)
    # empreendimento de ferias (ficticio): corretagem, sinal, saldo mensal e taxa anual
    for k in range(3):
        f(pd.Timestamp("2025-03-15") + pd.DateOffset(months=k), -1200, "ESTILO DE VIDA", "IMÓVEL", "Empreendimento",
          f"Resort corretagem {k + 1}/3", tg=t_res)
    for k in range(6):
        f(pd.Timestamp("2025-03-25") + pd.DateOffset(months=k), -850, "ESTILO DE VIDA", "IMÓVEL", "Empreendimento",
          f"Resort sinal {k + 1}/6", tg=t_res)
    for k, m in enumerate(pd.period_range("2025-09", HOJE.to_period("M") + 24, freq="M")):
        f(m.to_timestamp() + pd.Timedelta(days=24), -640, "ESTILO DE VIDA", "IMÓVEL", "Empreendimento",
          f"Resort saldo {k + 1}/60", tg=t_res)
    for ano in range(2025, HOJE.year + 2):
        f(f"{ano}-10-05", -420, "ESTILO DE VIDA", "IMÓVEL", "Empreendimento", f"Resort taxa anual {ano}", tg=t_res)
    # dois lancamentos passados que ficaram sem baixa (o painel mostra como vencidos)
    ult = HOJE.to_period("M") - 2
    f(ult.to_timestamp() + pd.Timedelta(days=14), -205.40, "GASTOS ESSENCIAIS", "MORADIA", "Luz", "Conta de luz (prevista)", pago="N")
    # viagens pagas pela conta da casa, e o jantar lancado nas duas tabelas
    for d, v, det, tg, loc in FAM_VIAGEM:
        f(d, -v, "ESTILO DE VIDA", "LAZER", "Hospedagem", det, tg=tg, loc=loc)
    for d, v, det, tg, loc in FAM_DUP:
        f(d, -v, "ESTILO DE VIDA", "ALIMENTAÇÃO", "Janta", det, "ALE", tg=tg, loc=loc)


# ----------------------------------------------------------------- dia a dia e corpo
HABITOS = [(1, "Treino", "Saúde", "Treino", "SIM", 1, None, None, "S"), (2, "Cardio", "Saúde", "Cardio", "SIM", 2, None, None, "S"),
           (4, "Café da manhã", "Alimentação", "Café da Manhã", "SIM", 4, None, None, "S"),
           (5, "Almoço", "Alimentação", "Almoço", "SIM", 5, None, None, "S"),
           (6, "Lanche", "Alimentação", "Lanche", "SIM", 6, None, None, "S"),
           (7, "Janta", "Alimentação", "Janta", "SIM", 7, None, None, "S"),
           (8, "Ceia", "Alimentação", "Ceia", "SIM", 8, None, None, "S"),
           (9, "Dia produtivo", "Rotina", "Dia Produtivo", None, 9, None, None, "N"),
           (10, "Trabalho", "Rotina", "Trabalho", None, 10, None, None, "N"),
           (11, "Nina em casa", "Rotina", "Nina em casa", None, 11, None, None, "N"),
           (12, "Estresse", "Bem-estar", "Estresse", "NAO", 12, None, None, "S"),
           (13, "Lazer", "Bem-estar", "Lazer", "SIM", 13, None, None, "S"),
           (14, "Água", "Saúde", "Consumo de água (Litros)", None, 1, 2.0, "litros", "S")]
# refeicao -> (prob. no plano, prob. jaca) num dia "medio"
REFEICAO = {4: (.93, .02), 5: (.91, .05), 6: (.68, .07), 7: (.52, .40), 8: (.17, .08)}
INICIO_DIARIO = pd.Timestamp("2024-01-08")
LACUNA = (pd.Timestamp("2024-02-12"), pd.Timestamp("2024-03-22"))


def gera_dias(rot: pd.DataFrame) -> pd.DataFrame:
    dia, hab = B.fatos["fato_dia"], B.fatos["fato_dia_habito"]
    regs = []
    for d, r in rot[rot.index >= INICIO_DIARIO].iterrows():
        if LACUNA[0] <= d <= LACUNA[1] or (rng.random() < .015):
            continue
        tendencia = min(1.0, (d - INICIO_DIARIO).days / 900)
        disc = r.disc + .4 * tendencia
        p_treino = (.62 if r.trabalho else .16) + .08 * disc - (.15 if r.viagem else 0)
        treino = rng.random() < np.clip(p_treino, .02, .95)
        cardio = rng.random() < np.clip((.07 if r.trabalho else .12) + .05 * disc, 0, .6)
        agua = float(np.clip(rng.normal(1.35 + .15 * disc + .1 * treino, .38), .3, 3.6))
        resp = {}
        for h, (ps, pj) in REFEICAO.items():
            pj2 = pj * (1.6 if r.fds or r.viagem or r.feriado else .85) * (1 - .25 * disc)
            ps2 = ps * (1 + .05 * disc) - (pj2 - pj)
            u = rng.random()
            resp[h] = "SIM" if u < np.clip(ps2, .01, .98) else "JACA" if u < np.clip(ps2, .01, .98) + np.clip(pj2, 0, .9) else "NAO"
        feitas = sum(v != "NAO" for v in resp.values())
        jaca = sum(v == "JACA" for v in resp.values())
        estresse = rng.random() < (.14 if r.trabalho else .07) - .03 * disc
        lazer = rng.random() < (.12 if r.trabalho else .38)
        prod = "SIM" if rng.random() < (.26 if (r.fds or not r.trabalho) else .07) else ("NAO" if rng.random() < .006 else "NORMAL")
        sd = sk(d)
        dia.append({"SK_DATA": sd, "VL_AGUA_LITROS": round(agua, 2), "NR_REFEICOES_FEITAS": feitas, "NR_REFEICOES_JACA": jaca,
                    "NR_HABITOS_ADERENTES": int(treino) + int(cardio) + sum(v == "SIM" for v in resp.values()) + int(agua >= 2),
                    "NR_HABITOS_APURADOS": 8, "DS_DIA_PRODUTIVO": prod, "NR_DIAS_ATRASO": int(rng.choice([0, 0, 0, 1, 2, 4])),
                    "FL_NINA_EM_CASA": "S" if r.nina else "N", "FL_CARDIO": "S" if cardio else "N", "FL_DATA_SUSPEITA": "N",
                    "FL_ESTRESSE": "S" if estresse else "N", "FL_LAZER": "S" if lazer else "N",
                    "FL_META_AGUA": "S" if agua >= 2 else "N", "FL_TRABALHO": "S" if r.trabalho else "N", "FL_TREINO": "S" if treino else "N"})
        respostas = {1: "SIM" if treino else "NAO", 2: "SIM" if cardio else "NAO", **resp, 9: prod,
                     10: "SIM" if r.trabalho else "NAO", 11: "SIM" if r.nina else "NAO",
                     12: "SIM" if estresse else "NAO", 13: "SIM" if lazer else "NAO", 14: f"{agua:.2f}"}
        for h, v in respostas.items():
            alvo = next(x[4] for x in HABITOS if x[0] == h)
            hab.append({"SK_DATA": sd, "SK_HABITO": h, "DS_RESPOSTA": v, "VL_MEDIDA": round(agua, 2) if h == 14 else None,
                        "FL_ADERENCIA": ("S" if (agua >= 2 if h == 14 else v == alvo) else "N") if alvo or h == 14 else None,
                        "FL_RESPONDIDO": "S"})
        regs.append({"data": d, "treino": treino, "cardio": cardio, "agua": agua, "jaca": jaca})
    return pd.DataFrame(regs).set_index("data")


METRICAS = [(1, "Peso", "Analise da Composição corporal", "Kg", None, "Ambas", "S"),
            (2, "Massa Muscular", "Analise da Composição corporal", "Kg", "MAIOR", "2018 em diante", "N"),
            (3, "Massa Muscular/Ossea", "Analise da Composição corporal", "Kg", "MAIOR", "Até 2013", "N"),
            (4, "Massa Gordura", "Analise da Composição corporal", "Kg", "MENOR", "Ambas", "S"),
            (5, "Proteina", "Analise da Composição corporal", "Kg", "MAIOR", "2018 em diante", "N"),
            (6, "Minerais", "Analise da Composição corporal", "Kg", "MAIOR", "2018 em diante", "N"),
            (7, "Agua Corp", "Analise da Composição corporal", "L", "MAIOR", "2018 em diante", "N"),
            (8, "IMC", "Analise Obesidade", "Imc", None, "Ambas", "S"),
            (9, "% Gordura", "Analise Obesidade", "%", "MENOR", "Ambas", "S"),
            (10, "Gordura Viceral", "Nivel gordura viceral", "Pontos", "MENOR", "2018 em diante", "N"),
            (11, "Pontuação Corpo", "Pontuação", "Pontos", "MAIOR", "2018 em diante", "N"),
            (12, "Estatura", "Medida Geral", "cm", None, "Ambas", "S"),
            (13, "Frequencia Cardiaca", "Medida Geral", "bpm", "MENOR", "Até 2013", "N")]
FITA = ["Ombro", "Tórax", "Braço D", "Braço E", "Antebraço D", "Antebraço E", "Coxa D", "Coxa E", "Perna D", "Perna E",
        "Cintura", "Abdomem", "Quadril", "Pescoço"]
for _i, _n in enumerate(FITA):
    METRICAS.append((16 + _i, _n, "Circunferencias Musculares", "cm",
                     "MENOR" if _n in ("Cintura", "Abdomem", "Quadril") else ("MAIOR" if _n != "Pescoço" else None), "Até 2013", "N"))
METRICAS += [(31, "Massa Livre de Gordura", "Composição", "Kg", "MAIOR", "2018 em diante", "N"),
             (36, "Taxa Metabolica Basal", "Metabolismo", "kcal", "MAIOR", "2018 em diante", "N"),
             (37, "Relacao Cintura-Quadril", "Obesidade", "Razão", "MENOR", "2018 em diante", "N"),
             (40, "Massa Magra Segmentar", "Segmentar", "Kg", "MAIOR", "2018 em diante", "N"),
             (41, "Massa Magra Segmentar %", "Segmentar", "%", "MAIOR", "2018 em diante", "N"),
             (42, "Gordura Segmentar", "Segmentar", "Kg", "MENOR", "2018 em diante", "N"),
             (43, "Gordura Segmentar %", "Segmentar", "%", "MENOR", "2018 em diante", "N")]
SK_METRICA = {m[1]: m[0] for m in METRICAS}
SEGMENTOS = [(-1, "Corpo inteiro", None, None, 0), (1, "Braço esquerdo", "Esquerdo", "Membro superior", 1),
             (2, "Braço direito", "Direito", "Membro superior", 2), (3, "Tronco", "Central", "Tronco", 3),
             (4, "Perna esquerda", "Esquerdo", "Membro inferior", 4), (5, "Perna direita", "Direito", "Membro inferior", 5)]
ESTATURA = 178.0


def gera_avaliacoes(dias: pd.DataFrame):
    av = B.fatos["fato_avaliacao_fisica"]
    nr = 0

    def mede(d, nr, nome, v, seg=-1, origem="InBody", ref=None):
        av.append({"SK_DATA": sk(d), "SK_METRICA": SK_METRICA[nome], "NR_AVALIACAO": nr, "VL_MEDIDA": round(float(v), 2),
                   "VL_MEDIDA_ANTERIOR": None, "VL_VARIACAO": None, "SK_SEGMENTO": seg,
                   "VL_REFERENCIA_MIN": ref[0] if ref else None, "VL_REFERENCIA_MAX": ref[1] if ref else None,
                   "DS_AVALIACAO": f"Avaliação {nr}", "DS_ORIGEM": origem, "FL_MEDIDO": "S", "FL_MELHOROU": None})

    # planilha antiga, com fita
    peso, gord = 79.0, 18.5
    for dt in ("2010-03-15", "2010-11-09", "2011-06-21", "2012-02-14", "2012-10-03", "2013-08-20"):
        nr += 1
        d = pd.Timestamp(dt)
        peso += rng.normal(.4, .9)
        gord += rng.normal(.2, .8)
        for n_, v in (("Peso", peso), ("% Gordura", gord), ("Massa Gordura", peso * gord / 100),
                      ("Massa Muscular/Ossea", peso * (1 - gord / 100) * .55), ("IMC", peso / (ESTATURA / 100) ** 2),
                      ("Estatura", ESTATURA), ("Frequencia Cardiaca", rng.normal(68, 4))):
            mede(d, nr, n_, v, origem="Planilha")
        base = {"Ombro": 116, "Tórax": 100, "Braço D": 34, "Braço E": 33.5, "Antebraço D": 28, "Antebraço E": 27.6,
                "Coxa D": 57, "Coxa E": 56.5, "Perna D": 38, "Perna E": 37.8, "Cintura": 84, "Abdomem": 86, "Quadril": 99, "Pescoço": 38}
        for n_, v in base.items():
            mede(d, nr, n_, v * (1 + (peso - 79) / 160) + rng.normal(0, .4), origem="Planilha")

    def inbody(d, nr, peso, gkg, origem="InBody"):
        magra = peso - gkg
        mus = magra * .565
        gpct = 100 * gkg / peso
        mede(d, nr, "Peso", peso, origem=origem)
        mede(d, nr, "% Gordura", gpct, origem=origem, ref=(10, 20))
        mede(d, nr, "Massa Gordura", gkg, origem=origem)
        mede(d, nr, "IMC", peso / (ESTATURA / 100) ** 2, origem=origem)
        mede(d, nr, "Estatura", ESTATURA, origem=origem)
        if origem != "InBody":
            return
        mede(d, nr, "Massa Muscular", mus, ref=(31, 38))
        mede(d, nr, "Massa Livre de Gordura", magra)
        mede(d, nr, "Agua Corp", magra * .732, ref=(42.0, 51.4))
        mede(d, nr, "Proteina", magra * .197, ref=(11.2, 13.7))
        mede(d, nr, "Minerais", magra * .069, ref=(3.9, 4.8))
        mede(d, nr, "Taxa Metabolica Basal", 370 + 21.6 * magra)
        mede(d, nr, "Gordura Viceral", max(1, round(2 + (gpct - 12) * .55 + rng.normal(0, .4))))
        mede(d, nr, "Relacao Cintura-Quadril", .80 + (gpct - 12) * .009 + rng.normal(0, .006))
        mede(d, nr, "Pontuação Corpo", 70 + (magra - 60) * .9 - (gpct - 18) * .9 + rng.normal(0, 1))
        partes = {1: (.057, .075), 2: (.059, .075), 3: (.455, .52), 4: (.155, .165), 5: (.157, .165)}
        for s, (fm, fg) in partes.items():
            mm, gg = magra * fm * rng.normal(1, .01), gkg * fg * rng.normal(1, .02)
            mede(d, nr, "Massa Magra Segmentar", mm, seg=s)
            mede(d, nr, "Gordura Segmentar", gg, seg=s)
            mede(d, nr, "Massa Magra Segmentar %", 100 * mm / (magra * fm * .92), seg=s)
            mede(d, nr, "Gordura Segmentar %", 100 * gg / (gkg * fg * .62), seg=s)

    # InBody 2018-2023, duas por ano
    # sem rotina registrada, a gordura sobe devagar ate 2023
    magra, gkg = 63.5, 17.8
    for dt in pd.date_range("2018-06-12", "2023-12-01", freq="7MS")[:10] + pd.Timedelta(days=11):
        nr += 1
        magra += rng.normal(.05, .35)
        gkg = max(12, gkg + rng.normal(.3, .6))
        inbody(dt, nr, magra + gkg, gkg)
    # desde abr/2024: a cada ~6 semanas, respondendo aos habitos do periodo
    while nr < 16:
        nr += 1
    d0 = pd.Timestamp("2024-04-10")
    d = d0
    planilha = {4, 13}      # duas sem exame, so peso e gordura na planilha
    k = 0
    while d <= HOJE:
        nr += 1
        inbody(d, nr, magra + gkg, gkg, origem="Planilha" if k in planilha else "InBody")
        prox = d + pd.Timedelta(days=int(rng.integers(30, 50)))
        janela = dias[(dias.index > d) & (dias.index <= prox)]
        n = (prox - d).days
        if len(janela):
            tr, ca, ja = 7 * janela["treino"].mean(), 7 * janela["cardio"].mean(), janela["jaca"].mean()
        else:
            tr, ca, ja = 3.0, .6, .8
        dg = (-.15 - .14 * (tr - 3.2) - .16 * (ca - .6) + .75 * (ja - .8)) * n / 30 + rng.normal(0, .22)
        dm = (.10 + .09 * (tr - 3.2) - .06 * (ja - .8)) * n / 30 + rng.normal(0, .15)
        if dg < 0:      # perto do piso, perder gordura fica mais dificil
            dg *= float(np.clip((gkg - 10) / 6, .15, 1))
        gkg = gkg + dg
        magra += dm
        d = prox
        k += 1


# ----------------------------------------------------------------- carga e escrita
def dims() -> dict[str, pd.DataFrame]:
    out = {}
    out["dim_calendario"] = calendario()
    out["dim_area_financ"] = pd.DataFrame([{"SK_AREA_FINANC": -1, "NM_AREA": "Não informado"}]
                                          + [{"SK_AREA_FINANC": v, "NM_AREA": k} for k, v in B.dims["area"].items()])
    out["dim_categoria_financ"] = pd.DataFrame([{"SK_CATEGORIA_FINANC": -1, "NM_CATEGORIA": "Não informado", "FL_CLASSIFICADO": "N"}]
                                               + [{"SK_CATEGORIA_FINANC": v, "NM_CATEGORIA": k, "FL_CLASSIFICADO": "S"} for k, v in B.dims["cat"].items()])
    out["dim_grupo_financ"] = pd.DataFrame([{"SK_GRUPO_FINANC": -1, "NM_GRUPO": "Não informado", "DS_COMPRESSIBILIDADE": None}]
                                           + [{"SK_GRUPO_FINANC": v, "NM_GRUPO": k, "DS_COMPRESSIBILIDADE": GRUPOS.get(k)} for k, v in B.dims["grupo"].items()])
    loc = [{"SK_LOCALIZACAO": -1, "NM_CIDADE": None, "SG_UF": None, "NM_PAIS": None, "NM_LOCALIZACAO": "Não informado"}]
    for c, uf, p in CIDADES:
        loc.append({"SK_LOCALIZACAO": B.chave("local", nome_local(c, uf, p)), "NM_CIDADE": c, "SG_UF": uf if p == "Brasil" else None,
                    "NM_PAIS": p, "NM_LOCALIZACAO": nome_local(c, uf, p)})
    out["dim_localizacao"] = pd.DataFrame(loc).assign(VL_LATITUDE=None, VL_LONGITUDE=None)
    out["dim_tag"] = pd.DataFrame([{"SK_TAG": -1, "NM_TAG": "Não informado", "DS_TIPO": "Não informado"}]
                                  + [{"SK_TAG": v, "NM_TAG": k, "DS_TIPO": B.dims["tag_tipo"][k]} for k, v in B.dims.get("tag", {}).items()])
    out["dim_origem"] = pd.DataFrame([{"SK_ORIGEM": -1, "CD_ORIGEM": "NAO_INFORMADO", "NM_ORIGEM": "Não informado",
                                       "NM_INSTITUICAO": "Não informado", "DS_TIPO_CONTA": "Não informado"}]
                                     + [dict(zip(["SK_ORIGEM", "CD_ORIGEM", "NM_ORIGEM", "NM_INSTITUICAO", "DS_TIPO_CONTA"], o)) for o in ORIGENS])
    out["dim_pessoa"] = pd.DataFrame([{"SK_PESSOA": -1, "NM_PESSOA": "Não informado", "DS_TIPO": "Não informado"}]
                                     + [dict(zip(["SK_PESSOA", "NM_PESSOA", "DS_TIPO"], p)) for p in PESSOAS])
    out["dim_categoria_investimento"] = pd.DataFrame([{"SK_CATEGORIA_INVESTIMENTO": -1, "NM_CATEGORIA": "Não informado", "DS_GRUPO": "Não informado"}]
                                                     + [{"SK_CATEGORIA_INVESTIMENTO": i + 1, "NM_CATEGORIA": c, "DS_GRUPO": g} for i, (c, g) in enumerate(CAT_INVEST)])
    at = [{"SK_ATIVO": -1, "CD_ATIVO": "Não informado", "NM_ATIVO": "Não informado", "TP_ATIVO": "Não informado",
           "DS_CLASSE_ATIVO": "Não aplicável", "DS_SUBCLASSE_ATIVO": None}]
    for i, a in enumerate(ATIVOS):
        at.append({"SK_ATIVO": i + 1, "CD_ATIVO": a[0], "NM_ATIVO": a[1], "TP_ATIVO": a[2], "DS_CLASSE_ATIVO": a[3], "DS_SUBCLASSE_ATIVO": a[4]})
    at.append({"SK_ATIVO": len(ATIVOS) + 1, "CD_ATIVO": INVESTBACK[0], "NM_ATIVO": INVESTBACK[1], "TP_ATIVO": "Fundo",
               "DS_CLASSE_ATIVO": "Fundos de Investimento", "DS_SUBCLASSE_ATIVO": "Renda Fixa"})
    at.append({"SK_ATIVO": len(ATIVOS) + 2, "CD_ATIVO": "BTC ITSA4", "NM_ATIVO": "ALUGUEL ITSA4", "TP_ATIVO": "BTC",
               "DS_CLASSE_ATIVO": "Empréstimo de Ativos", "DS_SUBCLASSE_ATIVO": None})
    out["dim_ativo"] = pd.DataFrame(at).assign(DS_ORIGEM_CLASSE="Gerador", DS_ORIGEM_DADO="DEMO")
    out["dim_categoria_auto"] = pd.DataFrame([{"SK_CATEGORIA_MANUTENCAO": -1, "NM_CATEGORIA": "Não informado", "NR_INTERVALO_KM": None, "FL_TEM_INTERVALO": "N"}]
                                             + [{"SK_CATEGORIA_MANUTENCAO": i + 1, "NM_CATEGORIA": c, "NR_INTERVALO_KM": INTERVALO.get(c),
                                                 "FL_TEM_INTERVALO": "S" if c in INTERVALO else "N"} for i, c in enumerate(CAT_AUTO)])
    vei = []
    for nome, c in CARROS.items():
        ult = c.get("ultima", (pd.Timestamp(c["ini"]), c["km0"]))
        km_hoje = ult[1] + c["ritmo"] * max(0, (HOJE - ult[0]).days) if nome == "SUV" else ult[1]
        vei.append({"SK_VEICULO": c["sk"], "NM_VEICULO": nome, "DT_PRIMEIRA": pd.Timestamp(c["ini"]).date(), "DT_ULTIMA": ult[0].date(),
                    "NR_KM_ATUAL": int(km_hoje), "NR_VISITAS": c.get("visitas", 0), "FL_ATIVO": "S" if nome == "SUV" else "N"})
    out["dim_veiculo"] = pd.DataFrame(vei)
    out["dim_revisao_programada"] = pd.DataFrame([
        {"SK_REVISAO_PROGRAMADA": i + 1, "SK_VEICULO": CARROS["SUV"]["sk"], "SK_CATEGORIA_MANUTENCAO": CAT_AUTO.index(it) + 1,
         "NM_ITEM": it, "NM_SISTEMA": sis, "NR_INTERVALO_KM": km, "NR_INTERVALO_MESES": meses, "DS_ACAO": acao,
         "DS_ESPECIFICACAO": None, "HASH_NEGOCIO": hash_de("rev", it)} for i, (it, sis, km, meses, acao) in enumerate(PLANO_SUV)])
    out["dim_habito"] = pd.DataFrame([dict(zip(["SK_HABITO", "NM_HABITO", "DS_GRUPO", "DS_PERGUNTA", "DS_RESPOSTA_DESEJADA",
                                                "NR_ORDEM", "VL_META_MINIMA", "DS_UNIDADE", "FL_APURA_ADERENCIA"], h)) for h in HABITOS])
    out["dim_metrica_corporal"] = pd.DataFrame([dict(zip(["SK_METRICA", "NM_METRICA", "DS_GRUPO", "DS_UNIDADE", "DS_SENTIDO_MELHOR",
                                                          "DS_ERA", "FL_SERIE_CONTINUA"], m)) | {"NR_ORDEM": m[0]} for m in METRICAS])
    out["dim_segmento_corporal"] = pd.DataFrame([dict(zip(["SK_SEGMENTO", "NM_SEGMENTO", "DS_LADO", "DS_REGIAO", "NR_ORDEM"], s)) for s in SEGMENTOS])
    return out


def pagamentos_fatura():
    """Pagamento de cada fatura (nivel SINTETICO): XP pelo Itau, Nubank pelo proprio app."""
    for (origem, mes), v in sorted(FAT_MES.items()):
        d = pd.Timestamp(mes + "-10")
        if d > HOJE or v <= 0:
            continue
        ajuste = rng.choice([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12.9])   # de vez em quando, IOF ou encargo
        lanca(d, -(v + ajuste), "TRANSFERENCIA", "TRANSFERENCIA", "Fatura Crédito", 2 if origem == 3 else 4,
              f"PAGTO FATURA {'XP' if origem == 3 else 'NUBANK'}", "Cartão", nivel="SINTETICO")


def cargas(tabelas: dict) -> pd.DataFrame:
    linhas = []
    for nome, df in tabelas.items():
        for k in range(6):
            quando = (HOJE - pd.Timedelta(days=k)).replace(hour=7)
            linhas.append({"SK_DATA": sk(quando), "DT_EXECUCAO": quando.to_pydatetime(), "DS_CAMADA": "gold", "DS_TABELA": f"gold.{nome}",
                           "DS_SCRIPT": "demo/gera_dados.py", "NR_INSERIDOS": len(df) if k == 5 else int(rng.integers(0, 25)),
                           "NR_ATUALIZADOS": 0, "NR_DESCARTADOS": 0, "NR_TOTAL": len(df), "NR_SEGUNDOS": round(float(rng.uniform(.4, 6)), 1),
                           "FL_CONVERGIU": "S"})
    return pd.DataFrame(linhas)


def prepara(nome: str, df: pd.DataFrame, chave: str | None) -> pd.DataFrame:
    df = df.copy()
    if chave and chave not in df:
        df.insert(0, chave, range(1, len(df) + 1))
    if "DT_CARGA" not in df and nome != "fato_carga":
        df["DT_CARGA"] = CARGA
    if "HASH_NEGOCIO" not in df and nome.startswith("fato_") and nome != "fato_carga":
        df["HASH_NEGOCIO"] = [hash_de(nome, i) for i in range(len(df))]
    return df


CHAVE = {"fato_movto_financ": "SK_MOVIMENTACAO", "fato_familia": "SK_LANCAMENTO", "fato_investimento": None,
         "fato_posicao_investimento": "SK_POSICAO", "fato_dia": "SK_DIA", "fato_dia_habito": "SK_DIA_HABITO",
         "fato_avaliacao_fisica": "SK_MEDICAO", "fato_manutencao_auto": "SK_MANUTENCAO", "fato_carga": "SK_CARGA"}


def completa(eng, tabelas: dict) -> None:
    """Coluna NOT NULL que o gerador deixou vazia ganha o membro "nao informado" do projeto."""
    nn = pd.read_sql("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                     "WHERE TABLE_SCHEMA = 'gold' AND IS_NULLABLE = 'NO'", eng)
    for r in nn.itertuples():
        df = tabelas.get(r.TABLE_NAME)
        if df is None or r.COLUMN_NAME not in df or not df[r.COLUMN_NAME].isna().any():
            continue
        vazio = -1 if r.DATA_TYPE in ("int", "bigint", "smallint") else "N" if r.COLUMN_NAME.startswith("FL_") else "Não informado"
        df[r.COLUMN_NAME] = df[r.COLUMN_NAME].astype(object).where(df[r.COLUMN_NAME].notna(), vazio)
        print(f"  {r.TABLE_NAME}.{r.COLUMN_NAME}: vazios viraram {vazio!r}")


def grava(eng, tabelas: dict, bronze: pd.DataFrame):
    completa(eng, tabelas)
    with eng.begin() as c:
        for nome in tabelas:
            c.execute(text(f"DELETE FROM gold.{nome}"))
        c.execute(text("DELETE FROM bronze.xp_posicao"))
    # INSERT de varias linhas por comando: o fast_executemany do pyodbc dimensiona
    # o buffer de texto pela primeira linha e trunca as seguintes
    lote = lambda df: max(1, 2000 // len(df.columns))
    for nome, df in tabelas.items():
        df.to_sql(nome, eng, schema="gold", if_exists="append", index=False, chunksize=lote(df), method="multi")
        print(f"  gold.{nome:<28} {len(df):>7,} linhas")
    bronze.to_sql("xp_posicao", eng, schema="bronze", if_exists="append", index=False, chunksize=lote(bronze), method="multi")
    print(f"  bronze.xp_posicao{'':<17} {len(bronze):>7,} linhas")


def main() -> int:
    print(f"Gerando dados fictícios até {HOJE:%d/%m/%Y} (semente {SEMENTE})")
    planeja_aportes()
    rot = plano_rotina()
    gera_viagens()
    gera_financeiro(rot)
    # uma compra grande e recente, para o cartao ter parcelas a cair
    compra(HOJE - pd.Timedelta(days=38), 3290, "ESTILO DE VIDA", "CASA", "Eletrodomestico", "Geladeira Casa & Lar",
           "Casa & Lar", loc=local("Campinas"), parcelas=10)
    gera_carro()
    pagamentos_fatura()
    ativos, caixa, sk_ib, _ = gera_investimentos()
    bronze = gera_posicao(ativos, caixa, sk_ib)
    gera_familia()
    dias = gera_dias(rot)
    gera_avaliacoes(dias)

    tabelas = {n: prepara(n, df, None) for n, df in dims().items()}
    for nome, linhas in B.fatos.items():
        if nome == "fato_carga":
            continue
        tabelas[nome] = prepara(nome, pd.DataFrame(linhas), CHAVE[nome])
    tabelas["fato_carga"] = prepara("fato_carga", cargas(tabelas), "SK_CARGA")
    grava(get_engine(), tabelas, bronze)
    print(f"Carteira por classe em {APP_JSON.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
