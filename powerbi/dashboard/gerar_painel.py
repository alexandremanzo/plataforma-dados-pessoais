"""
Gera o painel "Dashboard de Finanças Geral" (PBIP: TMDL + PBIR).

Fiel ao esboço em PDF: cabeçalho, quatro cartões, composição de
entradas e saídas, indicadores percentuais, cartão de crédito contra
outros gastos, top 5 de categorias, calendário de gastos e o bloco de
oportunidades de corte.

A MODELAGEM E UMA COPIA DAS GOLD, como pedido. Cada tabela e um
SelectColumns da gold correspondente, sem transformacao no Power Query.
O que precisa ser derivado vira COLUNA CALCULADA em DAX, visivel no
modelo, e nao um passo escondido no M:

    dim_grupo_financ   DS_CLASSE, NM_CLASSE, NR_ORDEM_CLASSE
    dim_calendario     NR_SEMANA_MES

Duas tabelas nao vem da gold: Composicao e Indicadores. Sao eixos de
quatro e tres linhas, DESCONECTADOS de proposito - existem porque os
dois blocos do esboco poem medidas DIFERENTES na mesma coluna, e isso
nao se faz com uma dimensao de verdade.

As medidas sao as de powerbi/dax/financas-geral.md. Os alvos se
conferem com powerbi/dax/conferir-financas-geral.py.

Uso:
    python gerar_painel.py
    python gerar_painel.py --validar
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

# APPEND, nao insert(0): a pasta mae tem um relatorio.py e um
# gerar_painel.py proprios, de outro painel. Na frente, ela sequestraria
# os dois imports e este projeto montaria a tela do outro.
sys.path.append(str(BASE.parent))

import pbir                                                      # noqa: E402
from pbir import (                                               # noqa: E402
    S_PAGINA, S_PAGINAS, S_PBIP, S_PBIR, S_PBISM, S_RELATORIO, S_VERSAO,
    TEMA_BASE, TEMA_VERSOES, VERSAO_PBIR, fundo_da_pagina, lit, tmdl_medida,
    tmdl_relacionamentos, tmdl_tabela,
)

PROJETO = "Dashboard"
CACHE_SCHEMAS = BASE.parent / ".schemas"

SERVIDOR_PADRAO = "localhost"
BANCO_PADRAO = "db-manzo"

LIMITE_PICO = 1000        # acima disso o dia do calendario e "pico"

# ----------------------------------------------------------------------
# Paleta — amostrada do esboço
# ----------------------------------------------------------------------

NAVY = "#1E293B"
NAVY_FRACO = "#94A3B8"
AZUL = "#2563EB"
VERDE = "#10B981"
VERMELHO = "#EF4444"
AMBAR = "#F59E0B"
ROXO = "#8B5CF6"
CIANO = "#06B6D4"

FUNDO = "#F8FAFC"
CARTAO = "#FFFFFF"
BORDA = "#E2E8F0"
TEXTO = "#0F172A"
TEXTO_FRACO = "#64748B"
BRANCO = "#FFFFFF"

TARJA_FUNDO = "#FFFBEB"   # a faixa amarela do bloco de oportunidades
TARJA_BORDA = "#FDE68A"
TARJA_TEXTO = "#92400E"
BLOCO_CARTAO = "#EEF2FF"  # o bloco do cartão de crédito
BLOCO_OUTROS = "#ECFEFF"  # o bloco de outros gastos

FONTE = "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
FONTE_FORTE = "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"

RAMPA_TOP5 = [VERMELHO, AMBAR, AZUL, ROXO, CIANO]

# ----------------------------------------------------------------------
# Grade — 1280 x 1140, cinco faixas
# ----------------------------------------------------------------------

LARGURA, ALTURA = 1280, 1140
MARGEM = 16
CAB_Y, CAB_H = 8, 84
RODAPE_Y = 1112
TITULO_H = 38

SELETOR = dict(x=1004, y=22, w=252, h=36)

CARD_Y, CARD_H, CARD_W = 104, 104, 300
CARD_X = [MARGEM + i * (CARD_W + 16) for i in range(4)]


def _c(nome, medida, rotulo, tinta, x, sub):
    return dict(nome=nome, medida=medida, rotulo=rotulo, cor=tinta,
                x=x, y=CARD_Y, w=CARD_W, h=CARD_H, sub=sub)


CARTOES = [
    _c("cReceita",  "Receita total",        "Receita total",          VERDE,     CARD_X[0],
       "Abertura da receita"),
    _c("cDespesa",  "Despesa total",        "Despesa total",          VERMELHO,  CARD_X[1],
       "Selo da despesa"),
    _c("cSaldo",    "Saldo total",          "Saldo total",            AZUL,      CARD_X[2],
       "Selo da margem"),
    _c("cSaldoSal", "Saldo sobre salário",  "Saldo (apenas salário)", AZUL,      CARD_X[3],
       "Selo do salário limpo"),
]

PAINEIS = {
    "vComposicao": dict(x=MARGEM, y=220, w=740, h=204,
                        titulo="Composição de Entradas e Saídas",
                        selo="Abertura"),
    "vIndicadores": dict(x=772, y=220, w=492, h=204,
                         titulo="Indicadores Percentuais Estratégicos",
                         selo="Ratios"),
    "vCartao": dict(x=MARGEM, y=436, w=LARGURA - 2 * MARGEM, h=148,
                    titulo="Visão: Gastos com Cartão de Crédito x Outros Gastos",
                    selo=None),
    "vCategoria": dict(x=MARGEM, y=596, w=620, h=300,
                       titulo="% Gastos por Categoria", selo=None),
    "vCalendario": dict(x=652, y=596, w=612, h=300,
                        titulo="Gasto por Dia (Calendário)", selo=None),
    "vDestaque": dict(x=MARGEM, y=908, w=LARGURA - 2 * MARGEM, h=196,
                      titulo="Destaque: Gastos que Podem Ser Cortados / Otimizados",
                      selo=None),
}

# --- dentro do painel do cartão de crédito ----------------------------
CT_TOTAL = dict(x=940, y=446, w=308, h=22)            # "Total Despesa: ..."
CT_BLOCO_E = dict(x=32, y=474, w=600, h=96)           # só no PNG
CT_BLOCO_D = dict(x=648, y=474, w=600, h=96)          # só no PNG
CT_VAL_E = dict(x=48, y=506, w=330, h=44)
CT_PCT_E = dict(x=486, y=482, w=130, h=24)
CT_VAL_D = dict(x=664, y=506, w=330, h=44)
CT_PCT_D = dict(x=1102, y=482, w=130, h=24)

# --- dentro do calendário ---------------------------------------------
CAL_MEDIA = dict(x=976, y=606, w=272, h=22)
# Para em 868, e nao em 886: os ultimos 28 px do painel sao da legenda
# de cores, desenhada no PNG. A matriz por cima a esconderia.
CAL_MATRIZ = dict(x=660, y=638, w=596, h=230)

# --- dentro do bloco de oportunidades ---------------------------------
DQ_META = dict(x=940, y=918, w=308, h=22)
DQ_TARJA = dict(x=32, y=948, w=1216, h=148)           # só no PNG
DQ_ECONOMIA = dict(x=980, y=958, w=252, h=24)
DQ_TABELA = dict(x=48, y=994, w=1184, h=92)


def area_do_visual(p: dict) -> tuple:
    return (p["x"] + 8, p["y"] + TITULO_H, p["w"] - 16, p["h"] - TITULO_H - 10)


def area_do_valor(c: dict) -> tuple:
    return (c["x"] + 16, c["y"] + 30, c["w"] - 32, 42)


def area_do_sub(c: dict) -> tuple:
    return (c["x"] + 16, c["y"] + 74, c["w"] - 32, 22)


def cx(d: dict) -> tuple:
    return (d["x"], d["y"], d["w"], d["h"])


# ======================================================================
# CAMADA 1 — consultas M: cópia das gold, sem transformação
# ======================================================================

def m_gold(tabela: str, colunas: list) -> str:
    cols = ", ".join(f'"{c}"' for c in colunas)
    return f'''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{{[Schema="gold", Item="{tabela}"]}}[Data],

    // Copia da gold: so a selecao das colunas que esta aba usa. Nada e
    // transformado aqui - o que precisa ser derivado e coluna
    // calculada, que fica visivel no modelo.
    Final  = Table.SelectColumns(Tabela, {{{cols}}}, MissingField.UseNull)
in
    Final'''


M_COMPOSICAO = '''let
    // Eixo de quatro linhas, DESCONECTADO de proposito: o bloco poe
    // medidas DIFERENTES na mesma coluna, e isso nao e dimensao.
    T = #table(
        type table [Ordem = Int64.Type, Fluxo = text, Item = text],
        {
            {1, "Receita", "Receita Salário"},
            {2, "Receita", "Outras Receitas"},
            {3, "Despesa", "Despesas Essenciais"},
            {4, "Despesa", "Despesas Outras (Não Essenciais)"}
        })
in
    T'''

M_INDICADORES = '''let
    T = #table(
        type table [Ordem = Int64.Type, Indicador = text],
        {
            {1, "% Salário em relação à Receita Total"},
            {2, "% Despesas Outras em relação à Despesa Total"},
            {3, "% Saldo (apenas Salário) x Receita Total"}
        })
in
    T'''


# ======================================================================
# CAMADA 2 — colunas calculadas
# ======================================================================

CALC_DS_CLASSE = 'COALESCE ( dim_grupo_financ[DS_COMPRESSIBILIDADE], "A classificar" )'

CALC_NM_CLASSE = '''SWITCH (
    dim_grupo_financ[DS_CLASSE],
    "Compressivel", "Compressível",
    "Nao e gasto",  "Não é gasto",
    dim_grupo_financ[DS_CLASSE]
)'''

CALC_ORDEM_CLASSE = '''// LE A COLUNA DE ORIGEM, NAO A DS_CLASSE. Parece rodeio e nao e:
// DS_CLASSE e ORDENADA por esta coluna, e no modelo tabular
// "ordenar por" conta como dependencia igual a uma referencia de
// formula. Lendo DS_CLASSE aqui, as duas se fechavam num ciclo e o
// Desktop recusava o modelo inteiro com
// "dependencia circular detectada".
//
// Nao precisa de COALESCE: o nulo nao casa com nenhum ramo e cai no
// padrao 4 - que e exatamente a posicao de "A classificar".
SWITCH (
    dim_grupo_financ[DS_COMPRESSIBILIDADE],
    "Compressivel",  1,
    "Eventual",      2,
    "Essencial",     3,
    "Nao e gasto",   5,
    4
)'''

CALC_SEMANA_MES = '''// A linha do calendario. WEEKDAY(_,1) devolve 1 para domingo, que e a
// coluna em que o calendario comeca; o deslocamento empurra o dia 1
// para a posicao certa na primeira linha.
VAR _primeiro = DATE ( dim_calendario[NR_ANO], dim_calendario[NR_MES], 1 )
VAR _desloc = WEEKDAY ( _primeiro, 1 ) - 1
RETURN
    INT ( ( dim_calendario[NR_DIA] + _desloc - 1 ) / 7 ) + 1'''


# ======================================================================
# CAMADA 3 — medidas
# ======================================================================

RS = '"R$" #,0.00'
PCT = "0.0%"

_FILTROS = '''KEEPFILTERS ( fato_movto_financ[DS_TIPO_FLUXO] = "{fluxo}" ),
    KEEPFILTERS ( fato_movto_financ[DS_NIVEL] = "ANALITICO" ),
    KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] <> "Nao e gasto" )'''

DAX_RECEITA = f'''// Os tres filtros que se repetem em tudo:
//   ANALITICO            nao conta o cartao duas vezes (a compra e o
//                        pagamento da fatura)
//   <> "Nao e gasto"     aporte, resgate e transferencia ficam fora
//   KEEPFILTERS          sem ele, o filtro booleano SUBSTITUI o filtro
//                        da coluna, e fatiar por classe mostraria o
//                        mesmo total em todas as linhas
CALCULATE (
    SUM ( fato_movto_financ[VL_TRANSACAO] ),
    {_FILTROS.format(fluxo="RECEITA")}
)'''

DAX_DESPESA = f'''// A base grava despesa NEGATIVA, entao a medida inverte o sinal. A VAR
// existe porque inverter o sinal de um resultado vazio e onde o DAX
// trata branco como zero em algumas construcoes - e no calendario isso
// poria "R$ 0,00" em todo dia sem gasto, em vez de deixar vazio.
VAR _v =
    CALCULATE (
        SUM ( fato_movto_financ[VL_TRANSACAO] ),
        {_FILTROS.format(fluxo="DESPESA")}
    )
RETURN
    IF ( NOT ISBLANK ( _v ), - _v )'''

DAX_PERIODO = '''VAR _n = DISTINCTCOUNT ( dim_calendario[NM_ANO_MES] )
RETURN
    IF (
        _n = 1,
        SELECTEDVALUE ( dim_calendario[NM_MES] ) & " / "
            & FORMAT ( SELECTEDVALUE ( dim_calendario[NR_ANO] ), "0" ),
        FORMAT ( _n, "#,0" ) & " meses selecionados"
    )'''

DAX_ABERTURA_RECEITA = '''// O subtitulo do cartao de receita. O esboco traz "100% da Renda", que
// nao informa nada - receita e 100% dela mesma. No lugar, a abertura.
"salário " & FORMAT ( [% salário na receita], "0.0%" )
    & " · outras " & FORMAT ( 1 - [% salário na receita], "0.0%" )'''

DAX_VALOR_COMPOSICAO = '''SWITCH (
    SELECTEDVALUE ( Composicao[Item] ),
    "Receita Salário",                  [Receita salário],
    "Outras Receitas",                  [Outras receitas],
    "Despesas Essenciais",              [Despesa essencial],
    "Despesas Outras (Não Essenciais)", [Despesa outras]
)'''

DAX_VALOR_INDICADOR = '''SWITCH (
    SELECTEDVALUE ( Indicadores[Indicador] ),
    "% Salário em relação à Receita Total",         [% salário na receita],
    "% Despesas Outras em relação à Despesa Total", [% despesa outras],
    "% Saldo (apenas Salário) x Receita Total",     [% saldo salário sobre receita total]
)'''

DAX_RANK_CAT = '''VAR _r = RANKX ( ALLSELECTED ( dim_categoria_financ[NM_CATEGORIA] ),
                 [Despesa total], , DESC )
RETURN
    IF ( _r <= 5, {0} )'''

DAX_RANK_OPO = '''VAR _r = RANKX ( ALLSELECTED ( dim_grupo_financ[NM_GRUPO] ),
                 [Despesa compressível], , DESC )
RETURN
    IF ( _r <= 3, {0} )'''

DAX_MEDIA_DIA = '''VAR _mes =
    CALCULATE ( [Despesa total], ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) )
VAR _dias =
    CALCULATE ( COUNTROWS ( dim_calendario ), ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) )
RETURN
    DIVIDE ( _mes, _dias )'''

DAX_COR_DIA = '''// A ordem do SWITCH e a ordem de PRIORIDADE: um pico num domingo pinta
// de pico, nao de fim de semana - e a informacao mais rara das duas.
VAR _v = [Despesa total]
VAR _fds = SELECTEDVALUE ( dim_calendario[FL_FIM_SEMANA] ) = "S"
VAR _fer = SELECTEDVALUE ( dim_calendario[FL_FERIADO] ) = "S"
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( _v ),         "#F8FAFC",
        _v > [Limite de pico],  "#FEE2E2",
        _fer,                   "#EDE9FE",
        _fds,                   "#FEF3C7",
        "#FFFFFF"
    )'''

DAX_META = '''// O que o esboco desenha como meta: o total dos tres grupos que voce
// vai atacar. Mais honesto que uma fracao de tudo - corta-se grupo,
// nao percentual.
SUMX (
    TOPN ( 3, ALLSELECTED ( dim_grupo_financ[NM_GRUPO] ), [Despesa compressível], DESC ),
    [Despesa compressível]
)'''

DAX_ECONOMIA_TXT = '''"Economia potencial de " & FORMAT ( [% da meta sobre a despesa], "0.0%" )
    & " da despesa"'''

MEDIDAS = [
    # --- 1. cartões do topo -------------------------------------------
    ("Receita total", DAX_RECEITA, RS,
     "Tudo que entrou no período, fora aporte, resgate e transferência."),
    ("Despesa total", DAX_DESPESA, RS,
     "Tudo que saiu no período, fora aporte, resgate e transferência."),
    ("Saldo total", "[Receita total] - [Despesa total]", RS,
     "Receita menos despesa. Negativo significa período fechado no vermelho."),
    ("Receita salário",
     'CALCULATE ( [Receita total], KEEPFILTERS ( dim_grupo_financ[NM_GRUPO] IN { "Salário" } ) )',
     RS,
     "Só a renda do trabalho. O acento é obrigatório: o modelo distingue acento."),
    ("Saldo sobre salário", "[Receita salário] - [Despesa total]", RS,
     "O que sobraria contando apenas o salário — o 'salário limpo' do esboço."),
    ("% despesa sobre receita", "DIVIDE ( [Despesa total], [Receita total] )", PCT,
     "Quanto da receita foi consumido."),
    ("% saldo sobre receita total", "DIVIDE ( [Saldo total], [Receita total] )", PCT,
     "Margem líquida."),
    ("% saldo sobre salário",
     "DIVIDE ( [Saldo sobre salário], [Receita salário] )", PCT,
     "Quanto do salário sobrou depois de toda a despesa."),
    ("Período selecionado", DAX_PERIODO, None,
     "O mês por extenso, para o cabeçalho."),
    ("Abertura da receita", DAX_ABERTURA_RECEITA, None,
     "Subtítulo do cartão de receita: quanto é salário e quanto é outras."),
    ("Selo da despesa",
     '''FORMAT ( [% despesa sobre receita], "0.0%" ) & " da receita"''',
     None, "Subtítulo do cartão de despesa."),
    # O esboco usa uma estrela nestes dois. Ela nao existe no Segoe UI e
    # sai como quadrado vazio - justo nos cartoes que fecham negativos em
    # metade dos meses. A seta diz a mesma coisa, e diz o SINAL, que num
    # cartao de saldo e a informacao principal.
    ("Selo da margem",
     '''VAR _t = [% saldo sobre receita total]
RETURN
    IF ( _t >= 0, "▲ ", "▼ " ) & FORMAT ( _t, "0.0%" ) & " margem líquida"''',
     None, "Subtítulo do cartão de saldo, com o sinal visível."),
    ("Selo do salário limpo",
     '''VAR _t = [% saldo sobre salário]
RETURN
    IF ( _t >= 0, "▲ ", "▼ " ) & FORMAT ( _t, "0.0%" ) & " salário limpo"''',
     None, "Subtítulo do cartão de saldo sobre salário, com o sinal visível."),

    # --- 2. composição -------------------------------------------------
    ("Outras receitas", "[Receita total] - [Receita salário]", RS,
     "Receita que não é salário: PLR, FGTS, previdência, venda de bem."),
    ("Despesa essencial",
     'CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Essencial" ) )',
     RS, "Despesa nos grupos marcados como essenciais."),
    ("Despesa outras", "[Despesa total] - [Despesa essencial]", RS,
     "Tudo que não é essencial. É subtração e não soma das outras classes: "
     "se nascer uma classe nova na dimensão, a subtração continua certa."),
    ("Despesa compressível",
     'CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Compressivel" ) )',
     RS, "Despesa nos grupos com potencial de corte."),
    ("Despesa eventual",
     'CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Eventual" ) )',
     RS, "Despesa que acontece mas não se repete."),
    ("Despesa a classificar",
     'CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "A classificar" ) )',
     RS, "Despesa em grupo que ainda não foi classificado. Lacuna visível, de propósito."),
    ("Valor da composição", DAX_VALOR_COMPOSICAO, RS,
     "O valor de cada linha do bloco de composição."),

    # --- 3. indicadores ------------------------------------------------
    ("% salário na receita", "DIVIDE ( [Receita salário], [Receita total] )", PCT,
     "Quanto da receita é renda do trabalho."),
    ("% despesa outras", "DIVIDE ( [Despesa outras], [Despesa total] )", PCT,
     "Peso do não essencial na despesa."),
    ("% saldo salário sobre receita total",
     "DIVIDE ( [Saldo sobre salário], [Receita total] )", PCT,
     "O saldo calculado só com salário, dividido pela receita TOTAL. "
     "Diferente de [% saldo sobre salário], que divide pelo próprio salário."),
    ("Valor do indicador", DAX_VALOR_INDICADOR, PCT,
     "O valor de cada linha do bloco de indicadores."),

    # --- 4. cartão x outros --------------------------------------------
    ("Despesa no cartão",
     'CALCULATE ( [Despesa total], KEEPFILTERS ( dim_origem[DS_TIPO_CONTA] = "Cartão de crédito" ) )',
     RS, "A parte da despesa que passou em cartão de crédito."),
    ("Despesa fora do cartão", "[Despesa total] - [Despesa no cartão]", RS,
     "O resto. É SUBTRAÇÃO porque DS_TIPO_CONTA tem seis valores, não dois: "
     "filtrar por 'Conta corrente' perderia débito, vale e os demais."),
    ("% no cartão", "DIVIDE ( [Despesa no cartão], [Despesa total] )", PCT,
     "Peso do cartão na despesa."),
    ("% fora do cartão", "DIVIDE ( [Despesa fora do cartão], [Despesa total] )", PCT,
     "Peso do que não passou no cartão."),

    # --- 5. categorias --------------------------------------------------
    ("% da categoria na despesa",
     "DIVIDE ( [Despesa total], CALCULATE ( [Despesa total], REMOVEFILTERS ( dim_categoria_financ ) ) )",
     PCT, "Peso da categoria na despesa do período."),
    ("Posição da categoria", DAX_RANK_CAT.format("_r"), "0",
     "1 a 5, na ordem de valor. O corte vem da medida: do sexto em diante "
     "tudo volta branco e a tabela descarta a linha sozinha."),
    ("Despesa da categoria", DAX_RANK_CAT.format("[Despesa total]"), RS,
     "Despesa da categoria, só para as cinco maiores."),
    ("% da categoria", DAX_RANK_CAT.format("[% da categoria na despesa]"), PCT,
     "Peso da categoria, só para as cinco maiores."),

    # --- 6. calendário ---------------------------------------------------
    ("Gasto do dia", "[Despesa total]", RS,
     "Alias de [Despesa total]. Dentro do calendário, 'despesa total' num "
     "quadrinho de um dia lê errado."),
    ("% do dia no mês",
     "DIVIDE ( [Despesa total], CALCULATE ( [Despesa total], "
     "ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) ) )", PCT,
     "Quanto o dia representa do mês."),
    ("Gasto médio do dia no mês", DAX_MEDIA_DIA, RS,
     "Despesa do mês dividida pelos dias corridos do mês."),
    ("Limite de pico", f"{LIMITE_PICO}", RS,
     "Acima disso o dia é pico no calendário. Separado para o limiar não "
     "ficar escondido dentro de um IF."),
    ("Cor do dia", DAX_COR_DIA, None,
     "Cor de fundo do quadrinho do calendário. Ligue em Elementos da célula "
     "> Cor de plano de fundo > Formatar por: Valor do campo."),

    # --- 7. oportunidades -------------------------------------------------
    ("% compressível", "DIVIDE ( [Despesa compressível], [Despesa total] )", PCT,
     "Peso do que pode ser cortado."),
    ("Meta pelos 3 maiores", DAX_META, RS,
     "Soma dos três maiores grupos compressíveis — a meta do esboço."),
    ("% da meta sobre a despesa",
     "DIVIDE ( [Meta pelos 3 maiores], [Despesa total] )", PCT,
     "Quanto a meta representa da despesa."),
    ("% da meta sobre a receita",
     "DIVIDE ( [Meta pelos 3 maiores], [Receita total] )", PCT,
     "Quanto a meta representa da receita."),
    ("Economia potencial", DAX_ECONOMIA_TXT, None,
     "O selo do bloco de oportunidades."),
    ("Posição da oportunidade", DAX_RANK_OPO.format("_r"), "0",
     "1 a 3, na ordem de valor entre os grupos compressíveis."),
    ("Valor da oportunidade", DAX_RANK_OPO.format("[Despesa compressível]"), RS,
     "Valor dos três maiores grupos compressíveis."),
    ("Saldo com o corte", "[Saldo total] + [Meta pelos 3 maiores]", RS,
     "O saldo do mês se a meta for cumprida."),
    ("Economia anualizada", "[Meta pelos 3 maiores] * 12", RS,
     "A meta repetida por doze meses."),
    ("Impacto do corte",
     '''VAR _eco = [Meta pelos 3 maiores]
VAR _saldo = [Saldo total]
VAR _rec = [Receita total]
RETURN
    "Cortando " & FORMAT ( _eco, "R$ #,0.00" ) & " dos três maiores grupos, o saldo vai de "
        & FORMAT ( _saldo, "R$ #,0.00" ) & " para " & FORMAT ( _saldo + _eco, "R$ #,0.00" )
        & ", e a margem de " & FORMAT ( DIVIDE ( _saldo, _rec ), "0.0%" )
        & " para " & FORMAT ( DIVIDE ( _saldo + _eco, _rec ), "0.0%" ) & "."''',
     None, "A frase de impacto, com os números do período."),
]


# ======================================================================
# CAMADA 4 — modelo
# ======================================================================

COLS_FATO = ["SK_DATA", "SK_ORIGEM", "SK_CATEGORIA_FINANC", "SK_GRUPO_FINANC",
             "VL_TRANSACAO", "DS_NIVEL", "DS_TIPO_FLUXO", "NR_PARCELA",
             "DS_DETALHE_ORIGINAL"]
COLS_CAL = ["SK_DATA", "DT_DATA", "NR_ANO", "NR_MES", "NM_MES", "NM_MES_ABREV",
            "NM_ANO_MES", "NM_MES_ANO", "NR_DIA", "NR_DIA_SEMANA",
            "NM_DIA_SEMANA", "NM_DIA_SEMANA_ABREV", "FL_FIM_SEMANA",
            "FL_FERIADO", "NM_FERIADO"]
COLS_GRUPO = ["SK_GRUPO_FINANC", "NM_GRUPO", "DS_COMPRESSIBILIDADE"]
COLS_CAT = ["SK_CATEGORIA_FINANC", "NM_CATEGORIA"]
COLS_ORIGEM = ["SK_ORIGEM", "NM_ORIGEM", "NM_INSTITUICAO", "DS_TIPO_CONTA"]


def gera_modelo(raiz: Path) -> None:
    modelo = raiz / f"{PROJETO}.SemanticModel"
    definicao = modelo / "definition"

    pbir.plataforma(modelo / ".platform", "SemanticModel", PROJETO)
    pbir.escreve_json(modelo / "definition.pbism",
                      {"$schema": S_PBISM, "version": "4.0", "settings": {}})
    pbir.escreve(definicao / "database.tmdl",
                 "database\n\tcompatibilityLevel: 1550\n")

    expressoes = [
        "/// Servidor do SQL Server. Único ponto a mudar se o banco se mover.",
        f'expression pServidor = "{SERVIDOR_PADRAO}" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('dash.expr.pServidor')}",
        "",
        "/// Banco de dados.",
        f'expression pBanco = "{BANCO_PADRAO}" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('dash.expr.pBanco')}",
        "",
    ]
    pbir.escreve(definicao / "expressions.tmdl", "\n".join(expressoes))

    medidas = [tmdl_medida(n, d, f, desc) for n, d, f, desc in MEDIDAS]

    tabelas = {
        "fato_movto_financ": tmdl_tabela(
            "fato_movto_financ",
            [("SK_DATA", "int64", {"oculta": True}),
             ("SK_ORIGEM", "int64", {"oculta": True}),
             ("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("VL_TRANSACAO", "decimal", {"oculta": True, "formato": RS,
                                          "descricao": "Despesa é negativa; receita, positiva."}),
             ("DS_NIVEL", "string",
              {"descricao": "ANALITICO ou SINTETICO. Filtre sempre ANALITICO: o "
                            "SINTETICO é o pagamento da fatura e contaria o cartão duas vezes."}),
             ("DS_TIPO_FLUXO", "string", {"descricao": "RECEITA ou DESPESA."}),
             ("NR_PARCELA", "int64", {"formato": "#,0"}),
             ("DS_DETALHE_ORIGINAL", "string",
              {"descricao": "Descrição como veio da origem."})],
            m_gold("fato_movto_financ", COLS_FATO),
            descricao="Cópia de gold.fato_movto_financ: um lançamento por linha."),

        "dim_calendario": tmdl_tabela(
            "dim_calendario",
            [("SK_DATA", "int64", {"oculta": True}),
             ("DT_DATA", "dateTime", {"formato": "dd/MM/yyyy"}),
             ("NR_ANO", "int64", {"formato": "0"}),
             ("NR_MES", "int64", {"oculta": True}),
             ("NM_MES", "string", {"ordena": "NR_MES"}),
             ("NM_MES_ABREV", "string", {"ordena": "NR_MES"}),
             ("NM_ANO_MES", "string",
              {"descricao": "AAAA-MM. É a CHAVE: ordena sozinha e é o que as "
                            "medidas comparam."}),
             ("NM_MES_ANO", "string",
              {"ordena": "NM_ANO_MES",
               "descricao": "Set/2026. É o RÓTULO, para seletor e eixo."}),
             ("NR_DIA", "int64", {"formato": "0"}),
             ("NR_DIA_SEMANA", "int64", {"oculta": True}),
             ("NM_DIA_SEMANA", "string", {"ordena": "NR_DIA_SEMANA"}),
             ("NM_DIA_SEMANA_ABREV", "string", {"ordena": "NR_DIA_SEMANA"}),
             ("FL_FIM_SEMANA", "string"),
             ("FL_FERIADO", "string"),
             ("NM_FERIADO", "string"),
             ("NR_SEMANA_MES", "int64",
              {"calculo": CALC_SEMANA_MES, "formato": "0",
               "descricao": "Semana dentro do mês, 1 a 6. É a linha do calendário — "
                            "não existe na gold, nasce aqui."})],
            m_gold("dim_calendario", COLS_CAL),
            descricao="Cópia de gold.dim_calendario, mais a semana do mês."),

        "dim_grupo_financ": tmdl_tabela(
            "dim_grupo_financ",
            [("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("NM_GRUPO", "string"),
             ("DS_COMPRESSIBILIDADE", "string",
              {"oculta": True,
               "descricao": "Como vem da gold, com nulo em 383 dos 520 grupos. "
                            "Oculta: use DS_CLASSE."}),
             ("DS_CLASSE", "string",
              {"calculo": CALC_DS_CLASSE, "ordena": "NR_ORDEM_CLASSE",
               "descricao": "A classe sem nulo. 383 grupos não têm classificação, e "
                            "em branco num slicer isso se lê como 'nada' em vez de "
                            "'não classificado'."}),
             ("NM_CLASSE", "string",
              {"calculo": CALC_NM_CLASSE, "ordena": "NR_ORDEM_CLASSE",
               "descricao": "A classe com acento, para eixo e legenda. O banco grava "
                            "sem acento porque a CHECK da coluna exige."}),
             ("NR_ORDEM_CLASSE", "int64",
              {"calculo": CALC_ORDEM_CLASSE, "oculta": True,
               "descricao": "Ordena do que se corta para o que não se corta."})],
            m_gold("dim_grupo_financ", COLS_GRUPO),
            descricao="Cópia de gold.dim_grupo_financ, mais a classe tratada."),

        "dim_categoria_financ": tmdl_tabela(
            "dim_categoria_financ",
            [("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("NM_CATEGORIA", "string")],
            m_gold("dim_categoria_financ", COLS_CAT),
            descricao="Cópia de gold.dim_categoria_financ."),

        "dim_origem": tmdl_tabela(
            "dim_origem",
            [("SK_ORIGEM", "int64", {"oculta": True}),
             ("NM_ORIGEM", "string"), ("NM_INSTITUICAO", "string"),
             ("DS_TIPO_CONTA", "string",
              {"descricao": "Seis valores, não dois: Cartão de crédito, Conta "
                            "corrente, Dinheiro e débito, Vale-alimentação, Conta de "
                            "investimento e Não informado."})],
            m_gold("dim_origem", COLS_ORIGEM),
            descricao="Cópia de gold.dim_origem."),

        "Composicao": tmdl_tabela(
            "Composicao",
            [("Ordem", "int64", {"oculta": True}),
             ("Fluxo", "string"),
             ("Item", "string", {"ordena": "Ordem"})],
            M_COMPOSICAO,
            descricao="Eixo do bloco de composição. DESCONECTADA de propósito: o "
                      "bloco põe medidas diferentes na mesma coluna."),

        "Indicadores": tmdl_tabela(
            "Indicadores",
            [("Ordem", "int64", {"oculta": True}),
             ("Indicador", "string", {"ordena": "Ordem"})],
            M_INDICADORES,
            descricao="Eixo do bloco de indicadores. DESCONECTADA, pelo mesmo motivo."),

        "_Medidas": tmdl_tabela(
            "_Medidas", [("Marcador", "int64", {"oculta": True})],
            'let\n    T = #table(type table [Marcador = Int64.Type], {{1}})\nin\n    T',
            medidas=medidas, descricao="Abriga as medidas."),
    }
    for nome, conteudo in tabelas.items():
        pbir.escreve(definicao / "tables" / f"{nome}.tmdl", conteudo)

    # Composicao e Indicadores NAO entram: sao desconectadas.
    pbir.escreve(definicao / "relationships.tmdl", tmdl_relacionamentos([
        ("relData", "fato_movto_financ.SK_DATA", "dim_calendario.SK_DATA", True),
        ("relOrigem", "fato_movto_financ.SK_ORIGEM", "dim_origem.SK_ORIGEM", True),
        ("relCategoria", "fato_movto_financ.SK_CATEGORIA_FINANC",
         "dim_categoria_financ.SK_CATEGORIA_FINANC", True),
        ("relGrupo", "fato_movto_financ.SK_GRUPO_FINANC",
         "dim_grupo_financ.SK_GRUPO_FINANC", True),
    ]))

    ordem = ["pServidor", "pBanco", "fato_movto_financ", "dim_calendario",
             "dim_grupo_financ", "dim_categoria_financ", "dim_origem",
             "Composicao", "Indicadores", "_Medidas"]
    linhas = [
        "model Model", "\tculture: pt-BR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: pt-BR", "\tdataAccessOptions",
        "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        "annotation PBI_QueryOrder = " + json.dumps(ordem, ensure_ascii=False),
        "", "annotation __PBI_TimeIntelligenceEnabled = 0", "",
    ]
    linhas += [f"ref table {pbir.cita(n)}" for n in tabelas]
    pbir.escreve(definicao / "model.tmdl", "\n".join(linhas) + "\n")


# ======================================================================
# CAMADA 5 — relatório
# ======================================================================

PAGINA = {"nome": "financas-geral", "titulo": "Finanças Geral"}
FUNDO_PNG = "fundo-financas-geral.png"


def gera_relatorio(raiz: Path) -> list:
    import relatorio

    rel = raiz / f"{PROJETO}.Report"
    definicao = rel / "definition"

    pbir.plataforma(rel / ".platform", "Report", PROJETO)
    pbir.escreve_json(rel / "definition.pbir", {
        "$schema": S_PBIR, "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{PROJETO}.SemanticModel"}},
    })
    pbir.escreve_json(definicao / "version.json",
                      {"$schema": S_VERSAO, "version": VERSAO_PBIR})

    tem_fundo = (raiz / FUNDO_PNG).exists()
    if tem_fundo:
        destino = rel / "StaticResources" / "RegisteredResources" / FUNDO_PNG
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raiz / FUNDO_PNG, destino)

    relatorio_json = {
        "$schema": S_RELATORIO,
        "themeCollection": {"baseTheme": {
            "name": TEMA_BASE, "reportVersionAtImport": TEMA_VERSOES,
            "type": "SharedResources"}},
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]},
        "annotations": [{"name": "defaultPage", "value": PAGINA["nome"]}],
    }
    if tem_fundo:
        relatorio_json["resourcePackages"] = pbir.pacote_de_recursos(FUNDO_PNG)
    pbir.escreve_json(definicao / "report.json", relatorio_json)

    pbir.escreve_json(definicao / "pages" / "pages.json", {
        "$schema": S_PAGINAS,
        "pageOrder": [PAGINA["nome"]],
        "activePageName": PAGINA["nome"],
    })

    pasta = definicao / "pages" / PAGINA["nome"]
    pbir.escreve_json(pasta / "page.json", {
        "$schema": S_PAGINA,
        "name": PAGINA["nome"],
        "displayName": PAGINA["titulo"],
        "displayOption": "FitToPage",
        "width": LARGURA,
        "height": ALTURA,
        "objects": {
            "background": [{"properties": fundo_da_pagina(
                FUNDO_PNG if tem_fundo else None, FUNDO)}],
            "displayArea": [{"properties": {"verticalAlignment": lit("Top")}}],
        },
    })

    gerados = []
    for v in relatorio.visuais():
        pbir.escreve_json(pasta / "visuals" / v["name"] / "visual.json", v)
        gerados.append(v["name"])
    return gerados


# ======================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="Gera o Dashboard de Finanças Geral")
    p.add_argument("--validar", action="store_true")
    args = p.parse_args()

    if not args.validar:
        for pasta in (BASE / f"{PROJETO}.Report", BASE / f"{PROJETO}.SemanticModel"):
            pbir.apaga_pasta(pasta)

        pbir.escreve_json(BASE / f"{PROJETO}.pbip", {
            "$schema": S_PBIP, "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJETO}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        })
        pbir.escreve(BASE / ".gitignore", "\n".join([
            "# O cache guarda os DADOS do modelo - nunca versionar.",
            "**/.pbi/cache.abf", "**/.pbi/localSettings.json", "*.pbix", "",
            "# Regeneravel por gerar_fundo.py --previa", "_previa-*.png", "",
        ]))

        gera_modelo(BASE)
        visuais = gera_relatorio(BASE)
        print(f"Projeto gerado em {BASE}")
        print(f"  modelo   : 8 tabelas, {len(MEDIDAS)} medidas, 4 relacionamentos")
        print(f"  relatorio: 1 pagina, {len(visuais)} visuais, tela {LARGURA}x{ALTURA}")
        print()

    print("Validando JSONs...")
    erros = pbir.valida(BASE, CACHE_SCHEMAS)
    print()
    if erros:
        print(f"{erros} arquivo(s) com problema.")
        return 1
    print("Todos os JSONs conferidos.")
    print(f"\nAbra {PROJETO}.pbip no Power BI Desktop e use "
          f"Arquivo > Salvar como > .pbix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
