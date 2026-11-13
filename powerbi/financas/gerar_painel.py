"""
Gera o painel de financas pessoais (PBIP: modelo TMDL + relatorio PBIR).

Uma pagina so, seguindo o modelo em PDF: quatro cartoes de topo, o
historico de doze meses, o top 5 de categorias e o bloco de gastos nao
essenciais. Os numeros do PDF eram ficticios; aqui todos saem do lake.

TRES ESCOLHAS QUE EXPLICAM O RESTO DO ARQUIVO:

1. O SELETOR DE PERIODO E UMA TABELA DESCONECTADA (dPeriodo). Se o
   seletor filtrasse dCalendario, o grafico de doze meses encolheria
   para o unico mes escolhido — o eixo e o filtro seriam a mesma coluna.
   Desconectado, o mes escolhido vira um ESCALAR que cada medida aplica
   onde quer, e o eixo do historico continua livre.

2. SEM NADA SELECIONADO, O PAINEL ABRE NO ULTIMO MES COM DADO. Nao
   depende de estado salvo no seletor, que o PBIR grava de um jeito
   fragil; depende do dado. Mes sem lancamento nenhum nunca abre em
   branco.

3. O MES CORRENTE E MARCADO COMO PARCIAL. Cada origem para num dia
   diferente (o cartao fecha depois da conta corrente), entao
   "dados completos ate" e o MENOR dos ultimos dias das origens que
   movimentaram no mes — a data a partir da qual o numero ainda sobe.
   Sem isso o cartao de saldo do mes corrente mente por omissao.

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
# gerar_painel.py proprios, do painel de Gastos. Posta na frente, ela
# sequestraria os dois imports e este projeto montaria a tela do outro.
# Atras, serve so o que e de fato compartilhado: pbir.py.
sys.path.append(str(BASE.parent))

import pbir                                                      # noqa: E402
from pbir import (                                               # noqa: E402
    S_PAGINA, S_PAGINAS, S_PBIP, S_PBIR, S_PBISM, S_RELATORIO, S_VERSAO,
    TEMA_BASE, TEMA_VERSOES, VERSAO_PBIR, fundo_da_pagina, lit, tmdl_medida,
    tmdl_relacionamentos, tmdl_tabela,
)

PROJETO = "Financas"
CACHE_SCHEMAS = BASE.parent / ".schemas"

SERVIDOR_PADRAO = "localhost"
BANCO_PADRAO = "db-manzo"

# Quanto do gasto nao essencial o bloco de oportunidades supoe cortado.
# O modelo em PDF usa 50%; fica como parametro para nao virar numero
# magico escondido numa medida.
CORTE_ALVO = 0.50

# ----------------------------------------------------------------------
# Paleta — a do modelo em PDF, nao a do painel de Gastos
# ----------------------------------------------------------------------

NAVY = "#1E293B"          # faixa do cabecalho
NAVY_FRACO = "#94A3B8"    # texto secundario sobre a faixa
AZUL = "#2563EB"          # barra de acento e cartao de saldo
VERDE = "#10B981"         # receita
VERMELHO = "#EF4444"      # despesa
AMBAR = "#F59E0B"         # cartao de credito
ROXO = "#8B5CF6"
CIANO = "#06B6D4"

FUNDO = "#F8FAFC"
CARTAO = "#FFFFFF"
BORDA = "#E2E8F0"
TEXTO = "#0F172A"
TEXTO_FRACO = "#64748B"
BRANCO = "#FFFFFF"
NOTA_FUNDO = "#ECFDF5"    # tarja verde-clara do "Impacto no Planejamento"
NOTA_BORDA = "#A7F3D0"
DESTAQUE_FUNDO = "#FFFBEB"
DESTAQUE_BORDA = "#FDE68A"

FONTE = "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
FONTE_FORTE = "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"

# A rampa do top 5, na ordem do ranking — igual a do modelo.
RAMPA_TOP5 = [VERMELHO, AMBAR, AZUL, ROXO, CIANO]

CORES_CLASSE = {
    "Compressivel": AMBAR,
    "Eventual": AZUL,
    "Essencial": "#475569",
    "A classificar": "#CBD5E1",
}

# ----------------------------------------------------------------------
# Grade — 1280 x 1000, uma pagina
# ----------------------------------------------------------------------

LARGURA, ALTURA = 1280, 1000
MARGEM = 16
CAB_H = 84
RODAPE_Y = 962
TITULO_H = 38

# Cabecalho: seletor de periodo e o aviso de mes parcial, a direita.
SELETOR = dict(x=1004, y=12, w=260, h=36)
AVISO = dict(x=1004, y=52, w=260, h=22)

CARD_Y, CARD_H, CARD_W = 100, 104, 300
CARD_X = [MARGEM + i * (CARD_W + 16) for i in range(4)]

HIST = dict(x=MARGEM, y=220, w=LARGURA - 2 * MARGEM, h=252)
TOP5 = dict(x=MARGEM, y=488, w=716, h=464)
NAOESS = dict(x=748, y=488, w=516, h=464)


def _c(nome, medida, rotulo, tinta, x, *, sub=None):
    """Um cartao do topo: valor grande e, embaixo, a linha de contexto."""
    return dict(nome=nome, medida=medida, rotulo=rotulo, cor=tinta,
                x=x, y=CARD_Y, w=CARD_W, h=CARD_H, sub=sub)


CARTOES = [
    _c("cReceita", "Receita total", "Receita total", VERDE, CARD_X[0],
       sub="Variação da receita"),
    _c("cDespesa", "Despesa total", "Despesa total", VERMELHO, CARD_X[1],
       sub="Variação da despesa"),
    _c("cCartao", "Despesa no cartão", "Cartão de crédito", AMBAR, CARD_X[2],
       sub="Cartão em contexto"),
    _c("cSaldo", "Saldo do mês", "Saldo / economia", AZUL, CARD_X[3],
       sub="Poupança em contexto"),
]

# Os visuais do bloco de nao essenciais, dentro do painel NAOESS.
# A tarja ambar e a nota verde sao desenhadas no PNG; aqui ficam so as
# areas que recebem numero.
NE_TARJA = dict(x=1004, y=548, w=252, h=96)      # so no PNG
NE_NOTA = dict(x=764, y=844, w=484, h=102)       # so no PNG
NE_TOTAL = dict(x=764, y=570, w=232, h=44)
NE_TOTAL_SUB = dict(x=764, y=616, w=232, h=20)
NE_POTENCIAL = dict(x=1016, y=570, w=228, h=44)
NE_POTENCIAL_SUB = dict(x=1016, y=616, w=228, h=20)
NE_GRUPOS = dict(x=764, y=656, w=484, h=180)
NE_IMPACTO = dict(x=776, y=874, w=460, h=64)

PAINEIS = {
    "vHistorico": dict(**HIST,
                       titulo="Histórico de Receitas vs Despesas (últimos 12 meses)"),
    "vTop5": dict(**TOP5, titulo="Top 5 Categorias de Gastos"),
    "vNaoEssencial": dict(**NAOESS, titulo="Gastos Não Essenciais (Oportunidades)"),
}


def area_do_visual(p: dict) -> tuple:
    """O visual entra recuado: o titulo do painel e desenhado no fundo."""
    return (p["x"] + 8, p["y"] + TITULO_H, p["w"] - 16, p["h"] - TITULO_H - 10)


def area_do_valor(c: dict) -> tuple:
    """No cartao o visual mostra so o numero; o rotulo vem do PNG."""
    return (c["x"] + 16, c["y"] + 28, c["w"] - 32, 44)


def area_do_sub(c: dict) -> tuple:
    return (c["x"] + 16, c["y"] + 74, c["w"] - 32, 22)


def caixa_de(d: dict) -> tuple:
    return (d["x"], d["y"], d["w"], d["h"])


# ======================================================================
# CAMADA 1 — consultas M
# ======================================================================

def m_tabela(schema: str, tabela: str) -> str:
    return f'''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{{[Schema="{schema}", Item="{tabela}"]}}[Data]
in
    Tabela'''


M_MOVIMENTACAO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="fato_movto_financ"]}[Data],

    // SINTETICO e o pagamento da fatura: o total do cartao saindo da
    // conta. Somado junto com as compras do cartao, contaria o mesmo
    // gasto duas vezes — e o erro nao se denuncia, so dobra o numero.
    Analitico = Table.SelectRows(Tabela, each [DS_NIVEL] = "ANALITICO"),

    // A base guarda despesa NEGATIVA e receita POSITIVA (conferido:
    // 12.745 despesas, todas < 0; 2.302 receitas, todas > 0). As duas
    // colunas abaixo deixam cada fluxo somavel direto, sem ABS espalhado
    // por dezenas de medidas.
    Receita = Table.AddColumn(Analitico, "VL_RECEITA",
                  each if [DS_TIPO_FLUXO] = "RECEITA" then [VL_TRANSACAO] else 0,
                  type number),
    Despesa = Table.AddColumn(Receita, "VL_DESPESA",
                  each if [DS_TIPO_FLUXO] = "DESPESA" then -[VL_TRANSACAO] else 0,
                  type number),
    Final   = Table.SelectColumns(Despesa, {
                  "SK_DATA", "SK_ORIGEM", "SK_CATEGORIA_FINANC",
                  "SK_GRUPO_FINANC", "VL_TRANSACAO", "VL_RECEITA", "VL_DESPESA",
                  "DS_TIPO_FLUXO", "NR_PARCELA", "DS_DETALHE_ORIGINAL"},
                  MissingField.UseNull)
in
    Final'''

M_CALENDARIO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="dim_calendario"]}[Data],

    // NM_MES_ANO ("Set/2026") VEM DO BANCO desde o
    // 47_dim_calendario_atributos.sql. Era derivado aqui e deixou de
    // ser: derivar de novo faria o Table.AddColumn recusar um nome que
    // a origem ja traz, e a atualizacao quebraria inteira.
    //
    // NR_INDICE_MES continua local: existe so para ordenar o eixo, e
    // por texto Abr viria antes de Jan.
    Indice = Table.AddColumn(Tabela, "NR_INDICE_MES",
                 each [NR_ANO] * 12 + [NR_MES], Int64.Type),
    Final  = Table.SelectColumns(Indice, {
                 "SK_DATA", "DT_DATA", "NR_ANO", "NR_MES", "NM_MES",
                 "NM_MES_ABREV", "NM_ANO_MES", "NM_MES_ANO", "NR_INDICE_MES",
                 "NR_DIA", "NM_DIA_SEMANA", "NM_DIA_SEMANA_ABREV",
                 "NR_DIA_SEMANA", "FL_FERIADO", "NM_FERIADO"},
                 MissingField.UseNull)
in
    Final'''

M_PERIODO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="dim_calendario"]}[Data],

    // UM MES POR LINHA, E DESCONECTADA DO FATO DE PROPOSITO. E so daqui
    // que o seletor de periodo filtra. Se ele filtrasse dCalendario, o
    // historico de doze meses encolheria para o mes escolhido, porque
    // seriam a mesma coluna servindo de eixo e de filtro.
    Hoje   = Date.From(DateTime.LocalNow()),
    Limite = Date.AddMonths(Date.StartOfMonth(Hoje), -35),
    Janela = Table.SelectRows(Tabela,
                 each [DT_DATA] >= Limite and [DT_DATA] <= Hoje),
    Meses  = Table.Distinct(Table.SelectColumns(Janela,
                 {"NM_ANO_MES", "NM_MES", "NR_ANO", "NR_MES"})),
    Indice = Table.AddColumn(Meses, "NR_INDICE",
                 each [NR_ANO] * 12 + [NR_MES], Int64.Type),
    Rotulo = Table.AddColumn(Indice, "NM_PERIODO",
                 each [NM_MES] & " / " & Text.From([NR_ANO]), type text),
    Final  = Table.SelectColumns(Rotulo, {"NM_ANO_MES", "NM_PERIODO", "NR_INDICE"})
in
    Final'''

# Os grupos cuja receita se repete todo mes. Conferido em 24 meses:
# Salario aparece em 22 deles; o segundo colocado em valor (Previdencia,
# R$ 112 mil) aparece em DOIS. Nao ha meio-termo a classificar.
GRUPOS_RECORRENTES = ["Salário"]

M_GRUPO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="dim_grupo_financ"]}[Data],

    // Grupo sem classificacao vira rotulo visivel, nao nulo. Lacuna que
    // aparece na tela e lacuna que alguem preenche; nula some na conta.
    Classe = Table.AddColumn(Tabela, "DS_CLASSE",
                 each if [DS_COMPRESSIBILIDADE] = null then "A classificar"
                      else [DS_COMPRESSIBILIDADE], type text),
    Ordem  = Table.AddColumn(Classe, "NR_ORDEM_CLASSE",
                 each if [DS_CLASSE] = "Compressivel" then 1
                      else if [DS_CLASSE] = "Eventual" then 2
                      else if [DS_CLASSE] = "Essencial" then 3
                      else if [DS_CLASSE] = "A classificar" then 4
                      else 5, Int64.Type),

    // Receita recorrente x eventual. A lista e curta e explicita porque
    // a regra e um julgamento, nao um dado: deixa-la aqui, visivel, e
    // melhor do que escondida num CALCULATE.
    Recorrentes = ''' + json.dumps(GRUPOS_RECORRENTES, ensure_ascii=False).replace(
        "[", "{").replace("]", "}") + ''',
    Recorr = Table.AddColumn(Ordem, "DS_RECORRENCIA",
                 each if List.Contains(Recorrentes, [NM_GRUPO]) then "Recorrente"
                      else "Eventual", type text),
    Final  = Table.SelectColumns(Recorr, {
                 "SK_GRUPO_FINANC", "NM_GRUPO", "DS_CLASSE", "NR_ORDEM_CLASSE",
                 "DS_RECORRENCIA"}, MissingField.UseNull)
in
    Final'''

M_PARAMETROS = '''let
    Tabela = #table(
        type table [#"Corte alvo" = number],
        {{pCorte}})
in
    Tabela'''


# ======================================================================
# CAMADA 2 — medidas DAX
# ======================================================================

DAX_ULTIMO_MES = '''// O mes mais recente com lancamento, em 'AAAA-MM'. REMOVEFILTERS
// porque ele e o PADRAO do painel: tem de ser o mesmo numero
// independentemente do que esteja filtrado na tela.
VAR _sk = CALCULATE ( MAX ( Movimentacao[SK_DATA] ), REMOVEFILTERS () )
RETURN
    CALCULATE ( MAX ( dCalendario[NM_ANO_MES] ),
                REMOVEFILTERS (), dCalendario[SK_DATA] = _sk )'''

DAX_MES_REF = '''// O mes que o painel inteiro usa. Vem do seletor desconectado; sem
// selecao, cai no ultimo mes com dado.
VAR _sel = SELECTEDVALUE ( dPeriodo[NM_ANO_MES] )
RETURN
    IF ( ISBLANK ( _sel ), [Último mês com dado], _sel )'''

DAX_INDICE = '''// Ano*12 + mes. Serve para "o mes anterior" e para a janela de doze
// meses virarem subtracao, sem depender de inteligencia de tempo.
VAR _m = [Mês de referência]
RETURN
    IF ( NOT ISBLANK ( _m ), VALUE ( LEFT ( _m, 4 ) ) * 12 + VALUE ( RIGHT ( _m, 2 ) ) )'''

DAX_PERIODO_ROTULO = '''VAR _m = [Mês de referência]
VAR _mes = CALCULATE ( MAX ( dCalendario[NM_MES] ), REMOVEFILTERS ( dCalendario ),
                       dCalendario[NM_ANO_MES] = _m )
VAR _ano = CALCULATE ( MAX ( dCalendario[NR_ANO] ), REMOVEFILTERS ( dCalendario ),
                       dCalendario[NM_ANO_MES] = _m )
RETURN
    _mes & " / " & FORMAT ( _ano, "0" )'''

DAX_COMPLETO_ATE = '''// A MENOR das ultimas datas das origens que movimentaram no mes.
// O cartao fecha depois da conta corrente, entao a data em que o mes
// esta completo DE VERDADE e a da origem mais atrasada — dai para
// frente o numero ainda sobe.
VAR _m = [Mês de referência]
VAR _origens =
    FILTER (
        ALL ( dOrigem ),
        CALCULATE ( COUNTROWS ( Movimentacao ),
                    REMOVEFILTERS ( dCalendario ),
                    dCalendario[NM_ANO_MES] = _m ) > 0 )
RETURN
    MINX (
        _origens,
        VAR _sk = CALCULATE ( MAX ( Movimentacao[SK_DATA] ),
                              REMOVEFILTERS ( dCalendario ),
                              dCalendario[NM_ANO_MES] = _m )
        RETURN
            DATE ( INT ( _sk / 10000 ), MOD ( INT ( _sk / 100 ), 100 ), MOD ( _sk, 100 ) ) )'''

DAX_AVISO = '''// "Em andamento" e o mes CORRENTE DO CALENDARIO, nao o mes cujo
// ultimo lancamento nao caiu no dia 31. Um mes fechado quase nunca tem
// movimento no ultimo dia, e a primeira versao disto marcava todos eles
// como parciais — um aviso que aparece sempre deixa de ser lido.
VAR _ate = [Dados completos até]
VAR _emAndamento = [Mês de referência] = FORMAT ( TODAY (), "yyyy-MM" )
RETURN
    IF (
        ISBLANK ( _ate ), "Sem lançamento no mês",
        IF ( _emAndamento,
             "Mês em andamento · completo até " & FORMAT ( _ate, "dd/MM" ),
             "Mês fechado · dados até " & FORMAT ( _ate, "dd/MM" ) ) )'''

# --- o mes de referencia aplicado -------------------------------------
# REMOVEFILTERS(dCalendario) e nao ALL: o seletor de periodo nao toca
# dCalendario, mas um clique num grafico toca — e o cartao de topo tem
# de continuar sendo o mes inteiro.
#
# A VAR NAO E ENFEITE. Predicado booleano de CALCULATE nao pode citar
# medida: escrito como dCalendario[NM_ANO_MES] = [Mês de referência], o
# DAX recusa a expressao inteira e TODA medida que dependesse dela abria
# o visual pedindo "selecione ou adicione dados". Passando pela VAR, o
# valor chega resolvido e o predicado volta a comparar coluna com
# escalar, que e o que CALCULATE aceita.
_NO_MES = '''VAR _m = [Mês de referência]
RETURN
    CALCULATE ( {0}, REMOVEFILTERS ( dCalendario ), dCalendario[NM_ANO_MES] = _m )'''
_NO_MES_ANTERIOR = '''VAR _i = [Índice do mês] - 1
RETURN
    CALCULATE ( {0},
        FILTER ( ALL ( dCalendario ),
                 dCalendario[NR_ANO] * 12 + dCalendario[NR_MES] = _i ) )'''


def _variacao(medida: str, anterior: str) -> str:
    """Texto da linha de contexto: seta, variacao e o rotulo do modelo."""
    return f'''VAR _ant = [{anterior}]
VAR _d = DIVIDE ( [{medida}] - _ant, _ant )
RETURN
    IF (
        ISBLANK ( _ant ) || _ant = 0, "— sem mês anterior",
        IF ( _d >= 0, "▲ +", "▼ −" ) & FORMAT ( ABS ( _d ), "0.0%" ) & " vs mês ant." )'''


DAX_JANELA_12M = '''// Branco fora da janela de doze meses. O grafico descarta a categoria
// cujas medidas sao todas brancas, entao o eixo nasce com doze pontos
// sem precisar de filtro de visual — que o PBIR grava de forma fragil.
VAR _fim = [Índice do mês]
VAR _i = MAX ( dCalendario[NR_ANO] ) * 12 + MAX ( dCalendario[NR_MES] )
RETURN
    IF ( _i > _fim - 12 && _i <= _fim, {0} )'''

DAX_RANK_CATEGORIA = '''VAR _r = RANKX ( ALLSELECTED ( dCategoria[NM_CATEGORIA] ),
                 [Despesa total], , DESC )
RETURN
    IF ( _r <= 5, {0} )'''

DAX_IMPACTO = '''// A frase do "Impacto no Planejamento" do modelo, com os numeros do
// mes em vez dos ficticios do PDF.
VAR _eco = [Potencial de economia]
VAR _saldo = [Saldo do mês]
VAR _novo = _saldo + _eco
VAR _rec = [Receita total]
RETURN
    "Cortando " & FORMAT ( [Corte alvo], "0%" ) & " dos gastos não essenciais, o saldo do mês vai de "
    & FORMAT ( _saldo, "R$ #,0.00" ) & " para " & FORMAT ( _novo, "R$ #,0.00" )
    & ", e a taxa de poupança de " & FORMAT ( DIVIDE ( _saldo, _rec ), "0.0%" )
    & " para " & FORMAT ( DIVIDE ( _novo, _rec ), "0.0%" ) & "."'''

RS = '"R$" #,0.00'

MEDIDAS = [
    # --- base, no contexto de filtro corrente -------------------------
    ("Receita",
     'CALCULATE ( SUM ( Movimentacao[VL_RECEITA] ), dGrupo[DS_CLASSE] <> "Nao e gasto" )',
     RS, "Receita no filtro atual, fora aporte, resgate e transferência."),
    ("Despesa",
     'CALCULATE ( SUM ( Movimentacao[VL_DESPESA] ), dGrupo[DS_CLASSE] <> "Nao e gasto" )',
     RS, "Despesa no filtro atual, fora aporte, resgate e transferência."),

    # --- o mes de referencia ------------------------------------------
    ("Último mês com dado", DAX_ULTIMO_MES, None,
     "Mês mais recente com lançamento, em AAAA-MM. É o padrão do painel."),
    ("Mês de referência", DAX_MES_REF, None,
     "O mês escolhido no seletor; sem seleção, o último mês com dado."),
    ("Índice do mês", DAX_INDICE, "0",
     "Ano × 12 + mês do mês de referência. Aritmética de meses sem time intelligence."),
    ("Período selecionado", DAX_PERIODO_ROTULO, None,
     "O mês de referência por extenso, como no cabeçalho do modelo."),
    ("Dados completos até", DAX_COMPLETO_ATE, "dd/MM/yyyy",
     "Até quando o mês está completo em TODAS as origens que movimentaram nele."),
    ("Aviso do período", DAX_AVISO, None,
     "Diz se o mês ainda está enchendo e até quando o número é confiável."),

    # --- os quatro cartoes do topo ------------------------------------
    ("Receita total", _NO_MES.format("[Receita]"), RS,
     "Tudo que entrou no mês de referência, inclusive entrada não recorrente."),
    ("Despesa total", _NO_MES.format("[Despesa]"), RS,
     "Tudo que saiu no mês de referência."),
    ("Despesa no cartão",
     'CALCULATE ( [Despesa total], dOrigem[DS_TIPO_CONTA] = "Cartão de crédito" )',
     RS, "A parte da despesa do mês que passou no cartão de crédito."),
    ("Saldo do mês", "[Receita total] - [Despesa total]", RS,
     "Receita menos despesa. Negativo significa mês fechado no vermelho."),
    ("Taxa de poupança", "DIVIDE ( [Saldo do mês], [Receita total] )", "0.0%",
     "Quanto da receita do mês sobrou."),
    ("% do cartão na despesa",
     "DIVIDE ( [Despesa no cartão], [Despesa total] )", "0.0%",
     "Quanto da despesa do mês passou no cartão."),

    # --- mes anterior, para a linha de contexto -----------------------
    ("Receita do mês anterior", _NO_MES_ANTERIOR.format("[Receita]"), RS,
     "Receita do mês imediatamente anterior ao de referência."),
    ("Despesa do mês anterior", _NO_MES_ANTERIOR.format("[Despesa]"), RS,
     "Despesa do mês imediatamente anterior ao de referência."),
    ("Cartão do mês anterior",
     _NO_MES_ANTERIOR.format(
         'CALCULATE ( [Despesa], dOrigem[DS_TIPO_CONTA] = "Cartão de crédito" )'),
     RS, "Gasto no cartão do mês imediatamente anterior."),
    ("Variação da receita", _variacao("Receita total", "Receita do mês anterior"),
     None, "Linha de contexto do cartão de receita."),
    ("Variação da despesa", _variacao("Despesa total", "Despesa do mês anterior"),
     None, "Linha de contexto do cartão de despesa."),
    ("Cartão em contexto",
     '''VAR _ant = [Cartão do mês anterior]
VAR _d = DIVIDE ( [Despesa no cartão] - _ant, _ant )
VAR _seta = IF ( ISBLANK ( _ant ) || _ant = 0, "",
                 IF ( _d >= 0, "▲ +", "▼ −" ) & FORMAT ( ABS ( _d ), "0.0%" ) & " · " )
RETURN
    _seta & FORMAT ( [% do cartão na despesa], "0.0%" ) & " da despesa"''',
     None, "Linha de contexto do cartão de crédito: variação e peso na despesa."),
    ("Poupança em contexto",
     # O modelo usa uma estrela aqui. Ela nao existe no Segoe UI e sai
     # como quadrado vazio — justo no cartao que mais importa, e que
     # fecha negativo em metade dos meses. A seta diz a mesma coisa, com
     # o glifo que o resto da linha ja usa.
     '''VAR _t = [Taxa de poupança]
RETURN
    IF ( _t >= 0, "▲ ", "▼ " ) & FORMAT ( _t, "0.0%" ) & " taxa de poupança"''',
     None, "Linha de contexto do cartão de saldo."),

    # --- historico de doze meses --------------------------------------
    ("Receita (12m)", DAX_JANELA_12M.format("[Receita]"), RS,
     "Receita do mês do eixo, em branco fora da janela de doze meses."),
    ("Despesa (12m)", DAX_JANELA_12M.format("[Despesa]"), RS,
     "Despesa do mês do eixo, em branco fora da janela de doze meses."),
    ("Receita recorrente (12m)",
     DAX_JANELA_12M.format(
         'CALCULATE ( [Receita], dGrupo[DS_RECORRENCIA] = "Recorrente" )'),
     RS,
     "Só a receita que se repete todo mês. Existe para mostrar que a despesa "
     "cruza o salário mesmo nos meses em que o total fecha positivo."),

    # --- top 5 de categorias ------------------------------------------
    ("Despesa da categoria", DAX_RANK_CATEGORIA.format("[Despesa total]"), RS,
     "Despesa do mês na categoria, só para as cinco maiores."),
    ("Posição da categoria", DAX_RANK_CATEGORIA.format("_r"), "0",
     "1 a 5, na ordem de valor. Ordena a tabela do top 5."),
    ("% da despesa (categoria)",
     DAX_RANK_CATEGORIA.format(
         "DIVIDE ( [Despesa total], CALCULATE ( [Despesa total], ALL ( dCategoria ) ) )"),
     "0.0%", "Peso da categoria na despesa do mês."),

    # --- gastos nao essenciais ----------------------------------------
    ("Corte alvo", "MAX ( Parametros[Corte alvo] )", "0%",
     "Fração do gasto não essencial que o bloco de oportunidades supõe cortada."),
    ("Não essencial",
     'CALCULATE ( [Despesa total], dGrupo[DS_CLASSE] = "Compressivel" )', RS,
     "Despesa do mês nos grupos marcados como compressíveis em gold.dim_grupo_financ."),
    ("% não essencial", "DIVIDE ( [Não essencial], [Despesa total] )", "0.0%",
     "Peso do gasto não essencial na despesa do mês."),
    ("Lançamentos não essenciais",
     _NO_MES.format('CALCULATE ( COUNTROWS ( Movimentacao ), '
                    'dGrupo[DS_CLASSE] = "Compressivel" )'),
     "#,0", "Quantos lançamentos compõem o gasto não essencial do mês."),
    ("Não essencial em contexto",
     '''FORMAT ( [% não essencial], "0.0%" ) & " da despesa · "
    & FORMAT ( [Lançamentos não essenciais], "#,0" ) & " lançamentos"''',
     None, "Linha de contexto do total não essencial."),
    ("Potencial de economia", "[Não essencial] * [Corte alvo]", RS,
     "O que sobraria no mês cortando a fração alvo do gasto não essencial."),
    ("Potencial em contexto",
     '"cortando " & FORMAT ( [Corte alvo], "0%" ) & " do não essencial"',
     None, "Linha de contexto do potencial de economia."),
    ("Não essencial do grupo",
     '''VAR _r = RANKX ( ALLSELECTED ( dGrupo[NM_GRUPO] ), [Não essencial], , DESC )
RETURN
    IF ( _r <= 8, [Não essencial] )''',
     RS, "Gasto não essencial do mês por grupo, limitado aos oito maiores."),
    ("Impacto no planejamento", DAX_IMPACTO, None,
     "A frase de impacto do modelo, calculada com os números do mês."),
]


# ======================================================================
# CAMADA 3 — modelo
# ======================================================================

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
        f"\tlineageTag: {pbir.guid('fin.expr.pServidor')}",
        "",
        "/// Banco de dados.",
        f'expression pBanco = "{BANCO_PADRAO}" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('fin.expr.pBanco')}",
        "",
        "/// Fração do gasto não essencial suposta cortada (0,5 = metade).",
        f'expression pCorte = {CORTE_ALVO} '
        'meta [IsParameterQuery=true, Type="Number", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('fin.expr.pCorte')}",
        "",
    ]
    pbir.escreve(definicao / "expressions.tmdl", "\n".join(expressoes))

    medidas = [tmdl_medida(n, d, f, desc) for n, d, f, desc in MEDIDAS]

    tabelas = {
        "Movimentacao": tmdl_tabela(
            "Movimentacao",
            [("SK_DATA", "int64", {"oculta": True}),
             ("SK_ORIGEM", "int64", {"oculta": True}),
             ("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("VL_TRANSACAO", "decimal", {"oculta": True, "formato": RS}),
             ("VL_RECEITA", "decimal",
              {"oculta": True, "formato": RS,
               "descricao": "Valor quando o fluxo é RECEITA; zero quando não é."}),
             ("VL_DESPESA", "decimal",
              {"oculta": True, "formato": RS,
               "descricao": "Valor positivo quando o fluxo é DESPESA; zero quando não é."}),
             ("DS_TIPO_FLUXO", "string", {"descricao": "RECEITA ou DESPESA."}),
             ("NR_PARCELA", "int64", {"formato": "#,0"}),
             ("DS_DETALHE_ORIGINAL", "string",
              {"descricao": "Descrição como veio da origem."})],
            M_MOVIMENTACAO,
            descricao="Fato: um lançamento por linha. O pagamento da fatura "
                      "(SINTETICO) fica de fora para não contar o cartão duas vezes."),
        "dCalendario": tmdl_tabela(
            "dCalendario",
            [("SK_DATA", "int64", {"oculta": True}),
             ("DT_DATA", "dateTime", {"formato": "dd/MM/yyyy",
                                      "descricao": "Data do lançamento."}),
             ("NR_ANO", "int64", {"formato": "0"}),
             ("NR_MES", "int64", {"oculta": True}),
             ("NM_MES", "string", {"ordena": "NR_MES"}),
             ("NM_MES_ABREV", "string", {"ordena": "NR_MES"}),
             ("NM_ANO_MES", "string",
              {"descricao": "AAAA-MM. Ordenável como texto, o que o painel usa."}),
             ("NM_MES_ANO", "string",
              {"ordena": "NR_INDICE_MES",
               "descricao": "Set/2026 — o rótulo do eixo do histórico, vindo "
                            "do banco."}),
             ("NR_INDICE_MES", "int64", {"oculta": True}),
             ("NR_DIA", "int64", {"formato": "0"}),
             ("NM_DIA_SEMANA", "string", {"ordena": "NR_DIA_SEMANA"}),
             ("NM_DIA_SEMANA_ABREV", "string", {"ordena": "NR_DIA_SEMANA"}),
             ("NR_DIA_SEMANA", "int64", {"oculta": True}),
             ("FL_FERIADO", "string",
              {"descricao": "S em feriado nacional e em ponto facultativo."}),
             ("NM_FERIADO", "string",
              {"descricao": "Nome do feriado; vazio nos dias comuns."})],
            M_CALENDARIO, descricao="Calendário pela data do lançamento."),
        "dPeriodo": tmdl_tabela(
            "dPeriodo",
            [("NM_ANO_MES", "string", {"oculta": True}),
             ("NM_PERIODO", "string",
              {"ordena": "NR_INDICE",
               "descricao": "Mês por extenso. É o que o seletor do cabeçalho mostra."}),
             ("NR_INDICE", "int64", {"oculta": True})],
            M_PERIODO,
            descricao="Seletor de período. DESCONECTADA de propósito: se filtrasse "
                      "o calendário, o histórico de doze meses encolheria para o "
                      "mês escolhido."),
        "dOrigem": tmdl_tabela(
            "dOrigem",
            [("SK_ORIGEM", "int64", {"oculta": True}),
             ("NM_ORIGEM", "string"), ("NM_INSTITUICAO", "string"),
             ("DS_TIPO_CONTA", "string",
              {"descricao": "Conta corrente ou Cartão de crédito."})],
            m_tabela("gold", "dim_origem"),
            descricao="Conta ou cartão de onde veio o lançamento."),
        "dCategoria": tmdl_tabela(
            "dCategoria",
            [("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("NM_CATEGORIA", "string"),
             ("FL_CLASSIFICADO", "string", {"oculta": True})],
            m_tabela("gold", "dim_categoria_financ"),
            descricao="Categoria do lançamento — o eixo do top 5."),
        "dGrupo": tmdl_tabela(
            "dGrupo",
            [("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("NM_GRUPO", "string"),
             ("DS_CLASSE", "string",
              {"ordena": "NR_ORDEM_CLASSE",
               "descricao": "Compressivel, Essencial, Eventual, Nao e gasto — ou "
                            "A classificar quando o grupo ainda não foi tratado."}),
             ("NR_ORDEM_CLASSE", "int64", {"oculta": True}),
             ("DS_RECORRENCIA", "string",
              {"descricao": "Recorrente ou Eventual, para separar salário do resto "
                            "da receita."})],
            M_GRUPO, descricao="Grupo do lançamento, sua natureza e sua recorrência."),
        "Parametros": tmdl_tabela(
            "Parametros", [("Corte alvo", "double", {"oculta": True})],
            M_PARAMETROS, oculta=True,
            descricao="Traz o parâmetro de corte para dentro do modelo, para o DAX lê-lo."),
        "_Medidas": tmdl_tabela(
            "_Medidas", [("Marcador", "int64", {"oculta": True})],
            'let\n    T = #table(type table [Marcador = Int64.Type], {{1}})\nin\n    T',
            medidas=medidas, descricao="Abriga as medidas."),
    }
    for nome, conteudo in tabelas.items():
        pbir.escreve(definicao / "tables" / f"{nome}.tmdl", conteudo)

    # dPeriodo NAO entra: e desconectada de proposito.
    pbir.escreve(definicao / "relationships.tmdl", tmdl_relacionamentos([
        ("relData", "Movimentacao.SK_DATA", "dCalendario.SK_DATA", True),
        ("relOrigem", "Movimentacao.SK_ORIGEM", "dOrigem.SK_ORIGEM", True),
        ("relCategoria", "Movimentacao.SK_CATEGORIA_FINANC",
         "dCategoria.SK_CATEGORIA_FINANC", True),
        ("relGrupo", "Movimentacao.SK_GRUPO_FINANC", "dGrupo.SK_GRUPO_FINANC", True),
    ]))

    ordem = ["pServidor", "pBanco", "pCorte", "Movimentacao", "dCalendario",
             "dPeriodo", "dOrigem", "dCategoria", "dGrupo", "Parametros", "_Medidas"]
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
# CAMADA 4 — relatorio
# ======================================================================

PAGINA = {"nome": "visao", "titulo": "Visão do mês"}
FUNDO_PNG = "fundo-financas.png"


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

    # Sem o PNG a pagina cai na cor lisa, em vez de apontar para um
    # recurso ausente — que o Desktop recusaria ao abrir.
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
        destino = pasta / "visuals" / v["name"] / "visual.json"
        pbir.escreve_json(destino, v)
        gerados.append(destino)
    return gerados


# ======================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="Gera o painel de finanças pessoais")
    p.add_argument("--validar", action="store_true",
                   help="apenas confere os JSONs já gerados")
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
            "**/.pbi/cache.abf",
            "**/.pbi/localSettings.json",
            "*.pbix",
            "",
            "# Regeneravel por gerar_fundo.py --previa",
            "_previa-*.png",
            "",
        ]))

        gera_modelo(BASE)
        visuais = gera_relatorio(BASE)
        print(f"Projeto gerado em {BASE}")
        print(f"  modelo   : 8 tabelas, {len(MEDIDAS)} medidas, 4 relacionamentos")
        print(f"  relatorio: 1 pagina, {len(visuais)} visuais, "
              f"tela {LARGURA}x{ALTURA}")
        print()

    print("Validando JSONs...")
    erros = pbir.valida(BASE, CACHE_SCHEMAS)
    print()
    if erros:
        print(f"{erros} arquivo(s) com problema.")
        return 1
    print("Todos os JSONs conferidos.")
    print()
    print(f"Abra {PROJETO}.pbip no Power BI Desktop e use "
          f"Arquivo > Salvar como > .pbix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
