"""
Gera o painel de controle de gastos (Power BI Project).

Tres paginas: o controle do mes corrente, o historico e o mapa do que da
para cortar. Emite PBIP (modelo TMDL + relatorio PBIR); o .pbix nasce de
um "Salvar como" no Power BI Desktop, que e o unico caminho documentado
pela Microsoft para essa conversao.

DUAS ARMADILHAS DOS DADOS, TRATADAS AQUI E NAO NO VISUAL:

1. DS_NIVEL = 'SINTETICO' sao PAGAMENTOS DE FATURA - o total do cartao
   saindo da conta corrente. Somar junto com as transacoes do cartao
   contaria tudo duas vezes. A carga do fato ja exclui.

2. As PARCELAS ficam gravadas no mes da COMPRA (uma revisao em cinco
   vezes aparece cinco vezes no mesmo dia). Quem diz o que cai em cada
   fatura e SK_DATA_FATURA - e por isso existem duas dimensoes de data
   aqui, uma da compra e outra da fatura.

Uso:
    python gerar_painel.py
    python gerar_painel.py --validar
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pbir  # noqa: E402
from pbir import (  # noqa: E402
    S_PAGINA, S_PAGINAS, S_PBIP, S_PBIR, S_PBISM, S_RELATORIO, S_VERSAO,
    TEMA_BASE, TEMA_VERSOES, VERSAO_PBIR, caixa, campo_coluna, campo_medida,
    cor, cores_por_categoria, fundo_da_pagina, lit, pacote_de_recursos,
    proj_coluna, proj_medida, tmdl_medida, tmdl_relacionamentos, tmdl_tabela,
    visual,
)

BASE = Path(__file__).resolve().parent
PROJETO = "Gastos"
CACHE_SCHEMAS = BASE / ".schemas"

SERVIDOR_PADRAO = "localhost"
BANCO_PADRAO = "db-manzo"

META_PADRAO = 5000          # a meta da fatura, em reais
DIAS_ANTES_FECHAMENTO = 7   # a fatura vence dia 15 e fecha ~dia 8

# ----------------------------------------------------------------------
# Paleta
# ----------------------------------------------------------------------
# Uma rampa que vai do que nao se discute ao que se corta primeiro: o
# essencial em petroleo, o eventual em ambar, o compressivel em turquesa.
# A cor carrega a mesma informacao que o rotulo.

PETROLEO = "#123A44"
PETROLEO_MED = "#1D5561"
TURQUESA = "#1FA89A"
AMBAR = "#D98A23"
VERMELHO = "#C0453C"
VERDE = "#63A63F"
ROXO = "#6B5BA8"
CINZA = "#9DAFB3"

FUNDO = "#F2F5F6"
CARTAO = "#FFFFFF"
BORDA = "#DFE7E9"
TEXTO = "#16262B"
TEXTO_FRACO = "#5A7076"
BRANCO = "#FFFFFF"

FONTE = "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
FONTE_FORTE = "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"

CORES_CLASSE = {
    "Compressivel": TURQUESA,
    "Essencial": PETROLEO,
    "Eventual": AMBAR,
    "A classificar": CINZA,
}

CORES_SITUACAO = {
    "Dentro da meta": VERDE,
    "No limite": AMBAR,
    "Vai estourar": VERMELHO,
    "Estourada": VERMELHO,
}

# ----------------------------------------------------------------------
# Grade — 1280 x 1000, tres paginas
# ----------------------------------------------------------------------

LARGURA, ALTURA = 1280, 1000
MARGEM = 16
CAB_H = 84
RODAPE_Y = 962
TITULO_H = 38

FILTRO_Y, FILTRO_H = 92, 60
_FX = [16 + i * 212 for i in range(6)]
FILTROS_X = [(x, 200) for x in _FX]

_CARD_Y, _CARD_H = 166, 96
_X5 = [16 + i * 252 for i in range(5)]
_X3 = [16 + i * 420 for i in range(3)]
_X2 = [16, 652]


def _p(x, y, w, h, titulo, **extra):
    return dict(x=x, y=y, w=w, h=h, titulo=titulo, **extra)


def _c(nome, medida, rotulo, tinta, x, *, formato=None, y=_CARD_Y,
       w=240, h=_CARD_H):
    return dict(nome=nome, medida=medida, rotulo=rotulo, cor=tinta,
                x=x, y=y, w=w, h=h, formato=formato)


PAGINAS = [
    {
        "nome": "mes",
        "titulo": "Controle do mês",
        "subtitulo": "quanto já entrou na fatura em aberto e quanto ainda cabe",
        "cartoes": [
            # A faixa que as outras paginas usam para filtros: aqui ela
            # carrega o indicador de olhar uma vez por dia.
            _c("mSituacao", "Situação da meta", "Situação do ciclo", VERDE,
               16, y=FILTRO_Y, w=940, h=FILTRO_H),
            _c("mPercent", "% da meta", "Consumido da meta", PETROLEO,
               968, y=FILTRO_Y, w=296, h=FILTRO_H),
            _c("mFatura", "Fatura em aberto", "Fatura em aberto", PETROLEO, _X5[0]),
            _c("mFalta", "Falta para a meta", "Falta para a meta", TURQUESA, _X5[1]),
            _c("mDias", "Dias até o fechamento", "Dias até fechar", PETROLEO_MED, _X5[2]),
            _c("mPorDia", "Pode gastar por dia", "Pode gastar por dia", VERDE, _X5[3]),
            _c("mProj", "Projeção de fechamento", "Projeção", AMBAR, _X5[4]),
        ],
        "paineis": {
            "vTermometro": _p(_X3[0], 278, 408, 210, "Termômetro da meta"),
            "vComposicao": _p(_X3[1], 278, 408, 210, "Composição da fatura em aberto"),
            "vClasse": _p(_X3[2], 278, 408, 210, "Natureza do que já entrou"),
            "vComprometido": _p(_X2[0], 500, 620, 214,
                                "Já comprometido nas próximas faturas"),
            "vRitmo": _p(_X2[1], 500, 612, 214, "Ritmo diário do ciclo"),
            "vUltimos": _p(MARGEM, 726, LARGURA - 2 * MARGEM, 224,
                           "Últimos lançamentos do ciclo"),
        },
    },
    {
        "nome": "historico",
        "titulo": "Histórico",
        "subtitulo": "como a fatura se comportou ao longo do tempo",
        "cartoes": [
            _c("hMedia", "Média 12 faturas", "Média 12 faturas", PETROLEO, _X5[0]),
            _c("hMediana", "Mediana 12 faturas", "Mediana", PETROLEO_MED, _X5[1]),
            _c("hAcima", "Faturas acima da meta", "Acima da meta", VERMELHO, _X5[2]),
            _c("hExcesso", "Excesso sobre a meta 12m", "Excesso em 12m", AMBAR, _X5[3]),
            _c("hMaior", "Maior fatura 12m", "Maior fatura", ROXO, _X5[4]),
        ],
        "paineis": {
            "vSerie": _p(MARGEM, 278, LARGURA - 2 * MARGEM, 246,
                         "Fatura mês a mês contra a meta"),
            "vClasseTempo": _p(_X2[0], 536, 620, 214,
                               "Consumo por natureza, mês a mês"),
            "vSazonal": _p(_X2[1], 536, 612, 214, "Sazonalidade — média por mês do ano"),
            "vAnoCat": _p(MARGEM, 762, LARGURA - 2 * MARGEM, 188,
                          "Categorias que mais pesaram, por ano"),
        },
    },
    {
        "nome": "compressivel",
        "titulo": "Onde dá para cortar",
        "subtitulo": "o gasto discricionário e recorrente, separado do resto",
        "cartoes": [
            _c("cMes", "Compressível por mês", "Compressível/mês", TURQUESA, _X5[0]),
            _c("cParte", "% compressível", "Do consumo", TURQUESA, _X5[1]),
            _c("cCorte", "Economia se cortar 30%", "Se cortar 30%", VERDE, _X5[2]),
            _c("cEventual", "Eventual por mês", "Eventual/mês", AMBAR, _X5[3]),
            _c("cFundo", "Fundo de eventuais sugerido", "Fundo sugerido", ROXO, _X5[4]),
        ],
        "paineis": {
            "vTopGrupos": _p(_X2[0], 278, 620, 300,
                             "Maiores grupos compressíveis — 12 meses"),
            "vCompMes": _p(_X2[1], 278, 612, 300, "Compressível mês a mês"),
            "vDetalhe": _p(MARGEM, 590, LARGURA - 2 * MARGEM, 360,
                           "Detalhe por grupo — frequência e média mensal"),
        },
    },
]


def area_do_visual(p: dict) -> tuple:
    """O visual entra recuado: o titulo e desenhado no fundo."""
    return (p["x"] + 8, p["y"] + TITULO_H, p["w"] - 16, p["h"] - TITULO_H - 10)


def area_do_valor(c: dict) -> tuple:
    """No cartao o visual mostra so o numero; rotulo vem do PNG.

    Proporcional a altura porque a faixa de situacao usa o mesmo
    desenho de cartao com 60 px em vez de 96.
    """
    return (c["x"] + 14, c["y"] + 26, c["w"] - 28, c["h"] - 34)


def pagina(nome: str) -> dict:
    return next(p for p in PAGINAS if p["nome"] == nome)


def fundo_da(nome: str) -> str:
    return f"fundo-{nome}.png"


# ======================================================================
# CAMADA 1 — consultas M
# ======================================================================

def _sql(schema: str, tabela: str) -> str:
    return (f'Origem{{[Schema="{schema}", Item="{tabela}"]}}[Data]')


def m_tabela(schema: str, tabela: str, passos: str = "") -> str:
    return f'''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = {_sql(schema, tabela)}{passos}
in
    {"Final" if passos else "Tabela"}'''


M_MOVIMENTACAO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="fato_movto_financ"]}[Data],

    // SINTETICO e PAGAMENTO DE FATURA: o total do cartao saindo da conta.
    // Mantido fora daqui porque somar junto com as transacoes do cartao
    // contaria o mesmo gasto duas vezes — e o erro nao se denuncia, so
    // dobra o numero.
    Analitico = Table.SelectRows(Tabela, each [DS_NIVEL] = "ANALITICO"),

    // Parcela marcada como flag: DAX filtra por valor com folga, e
    // "nao e nulo" como filtro de CALCULATE e desconfortavel.
    Parcela = Table.AddColumn(Analitico, "FL_PARCELADO",
                  each if [NR_PARCELA] = null then "N" else "S", type text),
    Valor   = Table.AddColumn(Parcela, "VL_GASTO",
                  each if [DS_TIPO_FLUXO] = "DESPESA" then -[VL_TRANSACAO] else 0,
                  type number),
    Final   = Table.SelectColumns(Valor, {
                  "SK_DATA", "SK_DATA_FATURA", "SK_ORIGEM", "SK_AREA_FINANC",
                  "SK_CATEGORIA_FINANC", "SK_GRUPO_FINANC", "VL_TRANSACAO",
                  "VL_GASTO", "DS_TIPO_FLUXO", "NR_PARCELA", "FL_PARCELADO",
                  "DS_DETALHE_ORIGINAL"}, MissingField.UseNull)
in
    Final'''

M_CALENDARIO = '''let
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="dim_calendario"]}[Data],
    Final  = Table.SelectColumns(Tabela, {
                 "SK_DATA", "DT_DATA", "NR_ANO", "NR_MES", "NM_MES",
                 "NM_MES_ABREV", "NM_ANO_MES", "NR_TRIMESTRE", "NR_DIA"},
                 MissingField.UseNull)
in
    Final'''

M_FATURA = '''let
    // A MESMA dimensao de calendario, servindo de eixo para a DATA DA
    // FATURA. Duas tabelas em vez de uma com relacao inativa porque
    // "quando comprei" e "em que fatura caiu" sao perguntas diferentes e
    // aparecem lado a lado na mesma tela.
    Origem = Sql.Database(pServidor, pBanco),
    Tabela = Origem{[Schema="gold", Item="dim_calendario"]}[Data],
    Usadas = Table.SelectColumns(Tabela, {
                 "SK_DATA", "DT_DATA", "NR_ANO", "NR_MES", "NM_MES",
                 "NM_MES_ABREV", "NM_ANO_MES"}, MissingField.UseNull),
    Renom  = Table.RenameColumns(Usadas, {
                 {"SK_DATA", "SK_FATURA"}, {"DT_DATA", "DT_FATURA"},
                 {"NR_ANO", "NR_ANO_FATURA"}, {"NR_MES", "NR_MES_FATURA"},
                 {"NM_MES", "NM_MES_FATURA"}, {"NM_MES_ABREV", "NM_MES_ABREV_FATURA"},
                 {"NM_ANO_MES", "NM_ANO_MES_FATURA"}})
in
    Renom'''

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
    Final  = Table.SelectColumns(Ordem, {
                 "SK_GRUPO_FINANC", "NM_GRUPO", "DS_CLASSE", "NR_ORDEM_CLASSE"},
                 MissingField.UseNull)
in
    Final'''

M_PARAMETROS = f'''let
    Tabela = #table(
        type table [#"Meta da fatura" = number, #"Dias antes do fechamento" = Int64.Type],
        {{{{pMeta, pDiasFechamento}}}})
in
    Tabela'''


# ======================================================================
# CAMADA 2 — medidas DAX
# ======================================================================

DAX_FATURA_CORRENTE = '''// A fatura em aberto e a proxima data de vencimento que ainda nao
// passou. Nao e o MAX de SK_DATA_FATURA: as parcelas ja lancadas
// alcancam faturas de ate nove meses a frente.
CALCULATE (
    MIN ( dFatura[DT_FATURA] ),
    dFatura[DT_FATURA] >= TODAY (),
    REMOVEFILTERS ( dFatura )
)'''

DAX_FATURA_ABERTO = '''VAR _dt = [Data da fatura corrente]
RETURN
    CALCULATE (
        [Gasto no cartão],
        REMOVEFILTERS ( dFatura ),
        REMOVEFILTERS ( dCalendario ),
        dFatura[DT_FATURA] = _dt
    )'''

DAX_DIAS_FECHAMENTO = '''VAR _fecha = [Data de fechamento]
RETURN MAX ( 0, DATEDIFF ( TODAY (), _fecha, DAY ) )'''

DAX_DIAS_DECORRIDOS = '''// O ciclo abre no fechamento anterior. Minimo de 1 para a divisao do
// ritmo nao estourar no primeiro dia.
VAR _fecha = [Data de fechamento]
VAR _abre = EDATE ( _fecha, -1 )
RETURN MAX ( 1, DATEDIFF ( _abre, TODAY (), DAY ) )'''

DAX_PROJECAO = '''// O ritmo se mede SO sobre a compra a vista do ciclo. As parcelas ja
// entraram inteiras na fatura; dividi-las pelos dias corridos e
// projeta-las adiante seria cobrar a mesma revisao de carro todo dia
// ate o fechamento — foi o que a conferencia pegou.
VAR _aberto = [Fatura em aberto]
VAR _ritmo = DIVIDE ( [Livre na fatura], [Dias decorridos do ciclo] )
RETURN _aberto + _ritmo * [Dias até o fechamento]'''

DAX_SITUACAO = '''VAR _meta = [Meta da fatura]
VAR _aberto = [Fatura em aberto]
VAR _proj = [Projeção de fechamento]
RETURN
    SWITCH (
        TRUE (),
        _aberto > _meta, "Estourada",
        _proj > _meta, "Vai estourar",
        _proj > _meta * 0.85, "No limite",
        "Dentro da meta"
    )'''

DAX_MEDIANA = '''// So faturas FECHADAS: a corrente ainda esta enchendo e puxaria a
// mediana para baixo todo comeco de ciclo.
VAR _corrente = [Data da fatura corrente]
VAR _t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( dFatura[DT_FATURA] ),
            dFatura[DT_FATURA] < _corrente
                && dFatura[DT_FATURA] >= EDATE ( _corrente, -12 )
        ),
        "@v", [Fatura fechada]
    )
RETURN MEDIANX ( _t, [@v] )'''

DAX_MEDIA12 = '''VAR _corrente = [Data da fatura corrente]
VAR _t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( dFatura[DT_FATURA] ),
            dFatura[DT_FATURA] < _corrente
                && dFatura[DT_FATURA] >= EDATE ( _corrente, -12 )
        ),
        "@v", [Fatura fechada]
    )
RETURN AVERAGEX ( _t, [@v] )'''

DAX_ACIMA = '''VAR _meta = [Meta da fatura]
VAR _corrente = [Data da fatura corrente]
VAR _t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( dFatura[DT_FATURA] ),
            dFatura[DT_FATURA] < _corrente
                && dFatura[DT_FATURA] >= EDATE ( _corrente, -12 )
        ),
        "@v", [Fatura fechada]
    )
RETURN COUNTROWS ( FILTER ( _t, [@v] > _meta ) )'''

DAX_EXCESSO = '''VAR _meta = [Meta da fatura]
VAR _corrente = [Data da fatura corrente]
VAR _t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( dFatura[DT_FATURA] ),
            dFatura[DT_FATURA] < _corrente
                && dFatura[DT_FATURA] >= EDATE ( _corrente, -12 )
        ),
        "@v", [Fatura fechada]
    )
RETURN SUMX ( _t, MAX ( 0, [@v] - _meta ) )'''

DAX_MAIOR = '''VAR _corrente = [Data da fatura corrente]
VAR _t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( dFatura[DT_FATURA] ),
            dFatura[DT_FATURA] < _corrente
                && dFatura[DT_FATURA] >= EDATE ( _corrente, -12 )
        ),
        "@v", [Fatura fechada]
    )
RETURN MAXX ( _t, [@v] )'''

DAX_POR_MES = '''// Media mensal sobre os ultimos 12 meses fechados de compra.
VAR _fim = EOMONTH ( TODAY (), -1 )
VAR _ini = EDATE ( _fim, -12 ) + 1
RETURN
    DIVIDE (
        CALCULATE (
            [Consumo],
            REMOVEFILTERS ( dCalendario ),
            REMOVEFILTERS ( dFatura ),
            dCalendario[DT_DATA] >= _ini && dCalendario[DT_DATA] <= _fim,
            dGrupo[DS_CLASSE] = "%s"
        ),
        12
    )'''

MEDIDAS = [
    # --- base
    ("Gasto", "SUM ( Movimentacao[VL_GASTO] )", '"R$" #,0.00',
     "Soma das despesas no filtro atual. Receita entra como zero."),
    ("Consumo",
     'CALCULATE ( [Gasto], dGrupo[DS_CLASSE] <> "Nao e gasto" )', '"R$" #,0.00',
     "Gasto tirando aporte, resgate e transferência — o que é consumo de verdade."),
    ("Gasto no cartão",
     'CALCULATE ( [Gasto], dOrigem[DS_TIPO_CONTA] = "Cartão de crédito" )',
     '"R$" #,0.00', "Gasto apenas nas origens que são cartão de crédito."),
    ("Lançamentos", "COUNTROWS ( Movimentacao )", "#,0",
     "Quantidade de lançamentos no filtro atual."),

    # --- meta e ciclo
    ("Meta da fatura", "MAX ( Parametros[Meta da fatura] )", '"R$" #,0',
     "A meta da fatura. Editável em Transformar dados > Parâmetros."),
    ("Data da fatura corrente", DAX_FATURA_CORRENTE, "dd/MM/yyyy",
     "Próximo vencimento que ainda não passou — a fatura que está enchendo."),
    ("Data de fechamento",
     "[Data da fatura corrente] - MAX ( Parametros[Dias antes do fechamento] )",
     "dd/MM/yyyy", "Quando a fatura em aberto fecha e as compras passam para a seguinte."),
    ("Fatura em aberto", DAX_FATURA_ABERTO, '"R$" #,0.00',
     "O que já caiu na fatura em aberto, incluindo parcelas vindas de compras antigas."),
    ("Falta para a meta", "[Meta da fatura] - [Fatura em aberto]", '"R$" #,0.00',
     "Quanto ainda cabe antes de estourar. Negativo significa meta já ultrapassada."),
    ("% da meta", "DIVIDE ( [Fatura em aberto], [Meta da fatura] )", "0%",
     "Quanto da meta já foi consumido neste ciclo."),
    ("Dias até o fechamento", DAX_DIAS_FECHAMENTO, "#,0",
     "Dias restantes até a fatura fechar."),
    ("Dias decorridos do ciclo", DAX_DIAS_DECORRIDOS, "#,0",
     "Dias já corridos desde a abertura do ciclo."),
    ("Pode gastar por dia",
     "DIVIDE ( MAX ( 0, [Falta para a meta] ), [Dias até o fechamento] )",
     '"R$" #,0.00', "O que ainda cabe, dividido pelos dias que faltam."),
    ("Ritmo diário do ciclo",
     "DIVIDE ( [Livre na fatura], [Dias decorridos do ciclo] )", '"R$" #,0.00',
     "Média diária de compra à vista neste ciclo. Ignora parcelas: elas "
     "não são gasto de hoje, são cobrança de uma compra antiga."),
    ("Projeção de fechamento", DAX_PROJECAO, '"R$" #,0.00',
     "Onde a fatura fecha se o ritmo atual continuar até o fechamento."),
    ("Situação da meta", DAX_SITUACAO, None,
     "Dentro da meta, No limite, Vai estourar ou Estourada."),
    ("Comprometido na fatura",
     'CALCULATE ( [Fatura em aberto], Movimentacao[FL_PARCELADO] = "S" )',
     '"R$" #,0.00', "Parte da fatura em aberto que são parcelas de compras já feitas."),
    ("Livre na fatura",
     "[Fatura em aberto] - [Comprometido na fatura]", '"R$" #,0.00',
     "Parte da fatura em aberto que veio de compras à vista no ciclo."),

    # --- historico
    ("Fatura fechada", "[Gasto no cartão]", '"R$" #,0.00',
     "Total que caiu numa fatura. Use com a dimensão de fatura no eixo."),
    ("Média 12 faturas", DAX_MEDIA12, '"R$" #,0',
     "Média das 12 últimas faturas fechadas — a corrente fica de fora."),
    ("Mediana 12 faturas", DAX_MEDIANA, '"R$" #,0',
     "Mediana das 12 últimas faturas fechadas; resiste a mês atípico."),
    ("Faturas acima da meta", DAX_ACIMA, "#,0",
     "Quantas das 12 últimas faturas fecharam acima da meta."),
    ("Excesso sobre a meta 12m", DAX_EXCESSO, '"R$" #,0',
     "Soma do que passou da meta nas 12 últimas faturas."),
    ("Maior fatura 12m", DAX_MAIOR, '"R$" #,0',
     "A maior fatura fechada nos últimos 12 meses."),

    # --- compressibilidade
    ("Compressível por mês", DAX_POR_MES % "Compressivel", '"R$" #,0',
     "Média mensal do gasto discricionário e recorrente nos 12 meses fechados."),
    ("Eventual por mês", DAX_POR_MES % "Eventual", '"R$" #,0',
     "Média mensal do que não se repete — é o que estoura a fatura."),
    ("Essencial por mês", DAX_POR_MES % "Essencial", '"R$" #,0',
     "Média mensal do que não dá para cortar."),
    ("Consumo por mês",
     '''VAR _fim = EOMONTH ( TODAY (), -1 )
VAR _ini = EDATE ( _fim, -12 ) + 1
RETURN
    DIVIDE (
        CALCULATE (
            [Consumo], REMOVEFILTERS ( dCalendario ), REMOVEFILTERS ( dFatura ),
            dCalendario[DT_DATA] >= _ini && dCalendario[DT_DATA] <= _fim
        ), 12 )''', '"R$" #,0',
     "Média mensal de consumo total nos 12 meses fechados."),
    ("% compressível",
     "DIVIDE ( [Compressível por mês], [Consumo por mês] )", "0.0%",
     "Quanto do consumo mensal é compressível."),
    ("Economia se cortar 30%", "[Compressível por mês] * 0.30", '"R$" #,0',
     "Quanto sobraria por mês cortando 30% do compressível."),
    ("Fundo de eventuais sugerido", "[Eventual por mês]", '"R$" #,0',
     "Quanto guardar por mês para os eventuais saírem do fundo, não da fatura."),

    # --- apoio aos visuais
    ("Mínimo do termômetro", "0", '"R$" #,0', "Piso do termômetro da meta.", ),
    ("Máximo do termômetro",
     "MAX ( [Meta da fatura] * 1.5, [Fatura em aberto] * 1.1 )", '"R$" #,0',
     "Teto do termômetro: sobe junto quando a fatura passa da meta, para a "
     "agulha não encostar no fim da escala e esconder o tamanho do estouro."),
    ("Comprometido à frente",
     """VAR _d = MAX ( dFatura[DT_FATURA] )
RETURN IF ( _d > [Data da fatura corrente], [Gasto no cartão] )""",
     '"R$" #,0.00',
     "Parcelas que já caem em faturas posteriores à atual. Em branco no "
     "passado, para o gráfico mostrar só o que ainda vem."),
    ("Gasto do dia no ciclo",
     """VAR _fecha = [Data de fechamento]
VAR _abre = EDATE ( _fecha, -1 )
VAR _d = MAX ( dCalendario[DT_DATA] )
RETURN IF ( _d > _abre && _d <= TODAY (), [Gasto no cartão] )""",
     '"R$" #,0.00', "Gasto de cada dia dentro do ciclo em curso."),
    ("Consumo compressível",
     'CALCULATE ( [Consumo], dGrupo[DS_CLASSE] = "Compressivel" )', '"R$" #,0.00',
     "Consumo apenas dos grupos discricionários e recorrentes."),
    ("Meses com gasto",
     "DISTINCTCOUNT ( dCalendario[NM_ANO_MES] )", "#,0",
     "Em quantos meses distintos o grupo apareceu — separa o recorrente do avulso."),
    ("Média mensal",
     "DIVIDE ( [Consumo], [Meses com gasto] )", '"R$" #,0.00',
     "Consumo dividido pelos meses em que houve gasto."),
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
        f"\tlineageTag: {pbir.guid('expr.pServidor')}",
        "",
        "/// Banco de dados.",
        f'expression pBanco = "{BANCO_PADRAO}" '
        'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('expr.pBanco')}",
        "",
        "/// Meta da fatura, em reais. Mudar aqui muda todo o painel.",
        f'expression pMeta = {META_PADRAO} '
        'meta [IsParameterQuery=true, Type="Number", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('expr.pMeta')}",
        "",
        "/// Dias entre o fechamento e o vencimento da fatura.",
        f'expression pDiasFechamento = {DIAS_ANTES_FECHAMENTO} '
        'meta [IsParameterQuery=true, Type="Number", IsParameterQueryRequired=true]',
        f"\tlineageTag: {pbir.guid('expr.pDiasFechamento')}",
        "",
    ]
    pbir.escreve(definicao / "expressions.tmdl", "\n".join(expressoes))

    medidas = [tmdl_medida(n, d, f, desc) for n, d, f, desc in MEDIDAS]

    tabelas = {
        "Movimentacao": tmdl_tabela(
            "Movimentacao",
            [("SK_DATA", "int64", {"oculta": True}),
             ("SK_DATA_FATURA", "int64", {"oculta": True}),
             ("SK_ORIGEM", "int64", {"oculta": True}),
             ("SK_AREA_FINANC", "int64", {"oculta": True}),
             ("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("VL_TRANSACAO", "decimal", {"oculta": True, "formato": '"R$" #,0.00'}),
             ("VL_GASTO", "decimal", {"oculta": True, "formato": '"R$" #,0.00',
                                      "descricao": "Despesa positiva; receita zerada."}),
             ("DS_TIPO_FLUXO", "string", {"descricao": "DESPESA ou RECEITA."}),
             ("NR_PARCELA", "int64", {"formato": "#,0"}),
             ("FL_PARCELADO", "string",
              {"descricao": "S quando o lançamento é parcela de uma compra maior."}),
             ("DS_DETALHE_ORIGINAL", "string",
              {"descricao": "Descrição como veio da origem."})],
            M_MOVIMENTACAO,
            descricao="Fato: um lançamento por linha. SINTETICO (pagamento de "
                      "fatura) fica de fora para não contar o cartão duas vezes."),
        "dCalendario": tmdl_tabela(
            "dCalendario",
            [("SK_DATA", "int64", {"oculta": True}),
             ("DT_DATA", "dateTime", {"formato": "dd/MM/yyyy",
                                      "descricao": "Data da compra."}),
             ("NR_ANO", "int64", {"formato": "0"}),
             ("NR_MES", "int64", {"oculta": True}),
             ("NM_MES", "string", {"ordena": "NR_MES"}),
             ("NM_MES_ABREV", "string", {"ordena": "NR_MES"}),
             ("NM_ANO_MES", "string"),
             ("NR_TRIMESTRE", "int64", {"formato": "0"}),
             ("NR_DIA", "int64", {"formato": "0"})],
            M_CALENDARIO, descricao="Calendário pela data da COMPRA."),
        "dFatura": tmdl_tabela(
            "dFatura",
            [("SK_FATURA", "int64", {"oculta": True}),
             ("DT_FATURA", "dateTime", {"formato": "dd/MM/yyyy",
                                        "descricao": "Vencimento da fatura."}),
             ("NR_ANO_FATURA", "int64", {"formato": "0"}),
             ("NR_MES_FATURA", "int64", {"oculta": True}),
             ("NM_MES_FATURA", "string", {"ordena": "NR_MES_FATURA"}),
             ("NM_MES_ABREV_FATURA", "string", {"ordena": "NR_MES_FATURA"}),
             ("NM_ANO_MES_FATURA", "string")],
            M_FATURA,
            descricao="Calendário pela data da FATURA. Existe porque a parcela "
                      "é gravada no mês da compra, não no da cobrança."),
        "dOrigem": tmdl_tabela(
            "dOrigem",
            [("SK_ORIGEM", "int64", {"oculta": True}),
             ("NM_ORIGEM", "string"), ("NM_INSTITUICAO", "string"),
             ("DS_TIPO_CONTA", "string")],
            m_tabela("gold", "dim_origem"),
            descricao="Conta ou cartão de onde veio o lançamento."),
        "dArea": tmdl_tabela(
            "dArea",
            [("SK_AREA_FINANC", "int64", {"oculta": True}), ("NM_AREA", "string")],
            m_tabela("gold", "dim_area_financ"), descricao="Área do orçamento."),
        "dCategoria": tmdl_tabela(
            "dCategoria",
            [("SK_CATEGORIA_FINANC", "int64", {"oculta": True}),
             ("NM_CATEGORIA", "string"), ("FL_CLASSIFICADO", "string",
                                          {"oculta": True})],
            m_tabela("gold", "dim_categoria_financ"), descricao="Categoria do gasto."),
        "dGrupo": tmdl_tabela(
            "dGrupo",
            [("SK_GRUPO_FINANC", "int64", {"oculta": True}),
             ("NM_GRUPO", "string"),
             ("DS_CLASSE", "string",
              {"ordena": "NR_ORDEM_CLASSE",
               "descricao": "Compressível, Essencial, Eventual, Não é gasto — "
                            "ou A classificar quando o grupo ainda não foi tratado."}),
             ("NR_ORDEM_CLASSE", "int64", {"oculta": True})],
            M_GRUPO, descricao="Grupo do gasto e sua natureza."),
        "Parametros": tmdl_tabela(
            "Parametros",
            [("Meta da fatura", "double", {"oculta": True}),
             ("Dias antes do fechamento", "int64", {"oculta": True})],
            M_PARAMETROS, oculta=True,
            descricao="Traz os parâmetros para dentro do modelo, para o DAX lê-los."),
        "_Medidas": tmdl_tabela(
            "_Medidas", [("Marcador", "int64", {"oculta": True})],
            'let\n    T = #table(type table [Marcador = Int64.Type], {{1}})\nin\n    T',
            medidas=medidas, descricao="Abriga as medidas."),
    }
    for nome, conteudo in tabelas.items():
        pbir.escreve(definicao / "tables" / f"{nome}.tmdl", conteudo)

    pbir.escreve(definicao / "relationships.tmdl", tmdl_relacionamentos([
        ("relData", "Movimentacao.SK_DATA", "dCalendario.SK_DATA", True),
        ("relFatura", "Movimentacao.SK_DATA_FATURA", "dFatura.SK_FATURA", True),
        ("relOrigem", "Movimentacao.SK_ORIGEM", "dOrigem.SK_ORIGEM", True),
        ("relArea", "Movimentacao.SK_AREA_FINANC", "dArea.SK_AREA_FINANC", True),
        ("relCategoria", "Movimentacao.SK_CATEGORIA_FINANC",
         "dCategoria.SK_CATEGORIA_FINANC", True),
        ("relGrupo", "Movimentacao.SK_GRUPO_FINANC", "dGrupo.SK_GRUPO_FINANC", True),
    ]))

    ordem = ["pServidor", "pBanco", "pMeta", "pDiasFechamento", "Movimentacao",
             "dCalendario", "dFatura", "dOrigem", "dArea", "dCategoria",
             "dGrupo", "Parametros", "_Medidas"]
    linhas = [
        "model Model", "\tculture: pt-BR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: pt-BR", "\tdataAccessOptions",
        "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        "annotation PBI_QueryOrder = " + __import__("json").dumps(ordem,
                                                                 ensure_ascii=False),
        "", "annotation __PBI_TimeIntelligenceEnabled = 0", "",
    ]
    linhas += [f"ref table {pbir.cita(n)}" for n in tabelas]
    pbir.escreve(definicao / "model.tmdl", "\n".join(linhas) + "\n")


# ======================================================================
# CAMADA 4 — relatorio
# ======================================================================

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

    # Uma imagem de fundo por pagina. So entram as que existem: sem o
    # PNG, a pagina cai na cor lisa em vez de apontar para um recurso
    # ausente, que o Desktop recusaria.
    fundos = []
    for pag in PAGINAS:
        arq = fundo_da(pag["nome"])
        if (raiz / arq).exists():
            destino = rel / "StaticResources" / "RegisteredResources" / arq
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(raiz / arq, destino)
            fundos.append(arq)

    relatorio_json = {
        "$schema": S_RELATORIO,
        "themeCollection": {"baseTheme": {
            "name": TEMA_BASE, "reportVersionAtImport": TEMA_VERSOES,
            "type": "SharedResources"}},
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]},
        "annotations": [{"name": "defaultPage", "value": PAGINAS[0]["nome"]}],
    }
    if fundos:
        relatorio_json["resourcePackages"] = [{
            "name": "RegisteredResources",
            "type": "RegisteredResources",
            "items": [{"name": a, "path": a, "type": "Image"} for a in fundos],
        }]
    pbir.escreve_json(definicao / "report.json", relatorio_json)

    pbir.escreve_json(definicao / "pages" / "pages.json", {
        "$schema": S_PAGINAS,
        "pageOrder": [p["nome"] for p in PAGINAS],
        "activePageName": PAGINAS[0]["nome"],
    })

    gerados = []
    for pag in PAGINAS:
        pasta = definicao / "pages" / pag["nome"]
        arq = fundo_da(pag["nome"])
        pbir.escreve_json(pasta / "page.json", {
            "$schema": S_PAGINA,
            "name": pag["nome"],
            "displayName": pag["titulo"],
            "displayOption": "FitToPage",
            "width": LARGURA,
            "height": ALTURA,
            "objects": {
                "background": [{"properties": fundo_da_pagina(
                    arq if arq in fundos else None, FUNDO)}],
                "displayArea": [{"properties": {"verticalAlignment": lit("Top")}}],
            },
        })
        for v in relatorio.visuais_da(pag["nome"]):
            destino = pasta / "visuals" / v["name"] / "visual.json"
            pbir.escreve_json(destino, v)
            gerados.append(destino)
    return gerados


# ======================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="Gera o painel de gastos")
    p.add_argument("--validar", action="store_true",
                   help="apenas confere os JSONs ja gerados")
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
            "# Regeneraveis por gerar_fundo.py --previa",
            "_previa-*.png",
            "",
        ]))

        gera_modelo(BASE)
        visuais = gera_relatorio(BASE)
        print(f"Projeto gerado em {BASE}")
        print(f"  modelo   : 9 tabelas, {len(MEDIDAS)} medidas, 6 relacionamentos")
        print(f"  relatorio: {len(PAGINAS)} paginas, {len(visuais)} visuais, "
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
