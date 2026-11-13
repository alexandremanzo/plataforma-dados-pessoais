"""
Monta as tres paginas do painel de gastos (PBIR).

Separado de gerar_painel.py so por tamanho: la fica o modelo, aqui a
tela. A grade vem de gerar_painel.PAGINAS, que tambem alimenta o
desenho do fundo — o mesmo retangulo posiciona o visual e desenha a
moldura, entao os dois nao tem como divergir.
"""

from __future__ import annotations

from pbir import (
    caixa, campo_coluna, campo_medida, cor, cores_por_categoria, lit,
    proj_coluna, proj_medida, visual,
)

import gerar_painel as g


def _eixo(tam=9.0, titulo=False) -> list:
    return [{"properties": {
        "showAxisTitle": lit(titulo), "fontColor": cor(g.TEXTO_FRACO),
        "fontSize": lit(tam)}}]


def _rotulos(tam=9.0, tinta=None) -> list:
    return [{"properties": {"show": lit(True), "fontSize": lit(tam),
                            "color": cor(tinta or g.TEXTO)}}]


def _legenda(pos="Top") -> list:
    return [{"properties": {"show": lit(True), "position": lit(pos),
                            "fontColor": cor(g.TEXTO_FRACO), "fontSize": lit(9.0)}}]


def _sem_legenda() -> list:
    return [{"properties": {"show": lit(False)}}]


def _tabela_objetos() -> dict:
    return {
        "grid": [{"properties": {
            "gridVertical": lit(False), "gridHorizontal": lit(True),
            "gridHorizontalColor": cor(g.BORDA), "rowPadding": lit(3.0),
            "outlineColor": cor(g.BORDA), "outlineWeight": lit(1.0)}}],
        "columnHeaders": [{"properties": {
            "fontColor": cor(g.BRANCO), "backColor": cor(g.PETROLEO),
            "fontSize": lit(9.0), "bold": lit(True),
            "fontFamily": lit(g.FONTE_FORTE)}}],
        "values": [{"properties": {
            "fontColor": cor(g.TEXTO), "fontSize": lit(9.0),
            "fontFamily": lit(g.FONTE),
            "backColorPrimary": cor(g.CARTAO),
            "backColorSecondary": cor("#F7FAFA")}}],
        "total": [{"properties": {"totals": lit(False)}}],
    }


def _cartoes(pag: dict) -> list:
    """Os cinco cartoes da linha de cima. Rotulo e moldura vem do PNG."""
    saida = []
    for i, c in enumerate(pag["cartoes"]):
        x, y, w, h = g.area_do_valor(c)
        saida.append(visual(
            c["nome"], x, y, w, h, "card", z=30 + i,
            estado={"Values": {"projections": [proj_medida(c["medida"])]}},
            objetos={
                "labels": [{"properties": {
                    "color": cor(c["cor"]), "fontSize": lit(24.0),
                    "bold": lit(True), "fontFamily": lit(g.FONTE_FORTE),
                    "labelDisplayUnits": lit(0.0)}}],
                "categoryLabels": [{"properties": {"show": lit(False)}}],
            },
            container=caixa()))
    return saida


def _filtros(pag: dict, defs: list) -> list:
    """Segmentadores da barra de filtros, na ordem em que vem."""
    saida = []
    for i, (nome, tabela, coluna, rotulo) in enumerate(defs):
        x, larg = g.FILTROS_X[i]
        saida.append(visual(
            nome, x, g.FILTRO_Y, larg, g.FILTRO_H, "slicer", z=20 + i,
            estado={"Values": {"projections": [proj_coluna(tabela, coluna)]}},
            objetos={
                "data": [{"properties": {"mode": lit("Dropdown")}}],
                "header": [{"properties": {
                    "show": lit(True), "text": lit(rotulo),
                    "fontColor": cor(g.TEXTO_FRACO), "fontSize": lit(9.0),
                    "background": cor(g.FUNDO), "fontFamily": lit(g.FONTE)}}],
                "items": [{"properties": {
                    "fontColor": cor(g.TEXTO), "fontSize": lit(10.0),
                    "background": cor(g.CARTAO)}}],
            },
            container=caixa()))
    return saida


# ======================================================================
# Pagina 1 — controle do mes
# ======================================================================

def pagina_mes() -> list:
    pag = g.pagina("mes")
    P = pag["paineis"]
    vis = _cartoes(pag)

    # Sem segmentador nesta pagina, de proposito: as medidas do ciclo
    # ignoram filtro de data para saber qual e a fatura em aberto, e um
    # filtro de periodo aqui daria a impressao de mexer no numero sem
    # mexer de fato.

    vis.append(visual("vTermometro", *g.area_do_visual(P["vTermometro"]),
                      "gauge", z=40,
                      estado={
                          "Y": {"projections": [proj_medida("Fatura em aberto")]},
                          "MinValue": {"projections": [proj_medida("Mínimo do termômetro")]},
                          "MaxValue": {"projections": [proj_medida("Máximo do termômetro")]},
                          "TargetValue": {"projections": [proj_medida("Meta da fatura")]},
                      },
                      objetos={
                          "dataPoint": [{"properties": {
                              "fillColor": cor(g.TURQUESA),
                              "targetColor": cor(g.VERMELHO)}}],
                          "labels": [{"properties": {
                              "color": cor(g.TEXTO), "fontSize": lit(20.0),
                              "bold": lit(True)}}],
                          "calloutValue": [{"properties": {
                              "fontSize": lit(20.0), "color": cor(g.PETROLEO)}}],
                      },
                      container=caixa()))

    vis.append(visual("vComposicao", *g.area_do_visual(P["vComposicao"]),
                      "barChart", z=41,
                      estado={"Y": {"projections": [
                          proj_medida("Comprometido na fatura", "Parcelas"),
                          proj_medida("Livre na fatura", "À vista no ciclo")]}},
                      objetos={
                          "dataPoint": [
                              {"properties": {"fill": cor(g.AMBAR)},
                               "selector": {"metadata": "_Medidas.Comprometido na fatura"}},
                              {"properties": {"fill": cor(g.TURQUESA)},
                               "selector": {"metadata": "_Medidas.Livre na fatura"}}],
                          "labels": _rotulos(),
                          "valueAxis": [{"properties": {"show": lit(False)}}],
                          "categoryAxis": _eixo(),
                          "legend": _legenda("Bottom"),
                      },
                      container=caixa()))

    vis.append(visual("vClasse", *g.area_do_visual(P["vClasse"]),
                      "donutChart", z=42,
                      estado={
                          "Category": {"projections": [proj_coluna("dGrupo", "DS_CLASSE",
                                                                   "Natureza")]},
                          "Y": {"projections": [proj_medida("Fatura em aberto")]},
                      },
                      objetos={
                          "dataPoint": cores_por_categoria("dGrupo", "DS_CLASSE",
                                                           g.CORES_CLASSE),
                          "legend": _legenda("Right"),
                          "labels": [{"properties": {
                              "show": lit(True), "fontSize": lit(9.0),
                              "labelStyle": lit("Data value, percent of total")}}],
                          "slices": [{"properties": {"innerRadiusRatio": lit(0.62)}}],
                      },
                      container=caixa()))

    vis.append(visual("vComprometido", *g.area_do_visual(P["vComprometido"]),
                      "columnChart", z=43,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dFatura", "NM_ANO_MES_FATURA", "Fatura")]},
                          "Y": {"projections": [proj_medida("Comprometido à frente",
                                                            "Já comprometido")]},
                      },
                      ordenar=[{"field": campo_coluna("dFatura", "NM_ANO_MES_FATURA"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.AMBAR)}}],
                          "labels": _rotulos(8.5),
                          "valueAxis": [{"properties": {"show": lit(False)}}],
                          "categoryAxis": _eixo(),
                          "legend": _sem_legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vRitmo", *g.area_do_visual(P["vRitmo"]),
                      "columnChart", z=44,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dCalendario", "DT_DATA", "Dia")]},
                          "Y": {"projections": [proj_medida("Gasto do dia no ciclo",
                                                            "Gasto do dia")]},
                      },
                      ordenar=[{"field": campo_coluna("dCalendario", "DT_DATA"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.PETROLEO_MED)}}],
                          "valueAxis": _eixo(),
                          "categoryAxis": _eixo(),
                          "legend": _sem_legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vUltimos", *g.area_do_visual(P["vUltimos"]),
                      "tableEx", z=45,
                      estado={"Values": {"projections": [
                          proj_coluna("dCalendario", "DT_DATA", "Data"),
                          proj_coluna("Movimentacao", "DS_DETALHE_ORIGINAL", "Lançamento"),
                          proj_coluna("dGrupo", "NM_GRUPO", "Grupo"),
                          proj_coluna("dGrupo", "DS_CLASSE", "Natureza"),
                          proj_coluna("dFatura", "NM_ANO_MES_FATURA", "Cai na fatura"),
                          proj_medida("Gasto", "Valor")]}},
                      ordenar=[{"field": campo_coluna("dCalendario", "DT_DATA"),
                                "direction": "Descending"}],
                      objetos=_tabela_objetos(),
                      container=caixa()))
    return vis


# ======================================================================
# Pagina 2 — historico
# ======================================================================

def pagina_historico() -> list:
    pag = g.pagina("historico")
    P = pag["paineis"]
    vis = _cartoes(pag)
    vis += _filtros(pag, [
        ("hAno", "dFatura", "NR_ANO_FATURA", "Ano da fatura"),
        ("hOrigem", "dOrigem", "NM_ORIGEM", "Origem"),
        ("hClasse", "dGrupo", "DS_CLASSE", "Natureza"),
        ("hArea", "dArea", "NM_AREA", "Área"),
        ("hCategoria", "dCategoria", "NM_CATEGORIA", "Categoria"),
        ("hGrupo", "dGrupo", "NM_GRUPO", "Grupo"),
    ])

    vis.append(visual("vSerie", *g.area_do_visual(P["vSerie"]),
                      "lineClusteredColumnComboChart", z=40,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dFatura", "NM_ANO_MES_FATURA", "Fatura")]},
                          "Y": {"projections": [proj_medida("Fatura fechada")]},
                          "Y2": {"projections": [proj_medida("Meta da fatura", "Meta")]},
                      },
                      ordenar=[{"field": campo_coluna("dFatura", "NM_ANO_MES_FATURA"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.PETROLEO)}}],
                          "lineStyles": [{"properties": {
                              "strokeWidth": lit(2.0), "lineStyle": lit("dashed")}}],
                          "valueAxis": _eixo(),
                          "categoryAxis": _eixo(),
                          "legend": _legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vClasseTempo", *g.area_do_visual(P["vClasseTempo"]),
                      "stackedAreaChart", z=41,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dCalendario", "NM_ANO_MES", "Mês")]},
                          "Y": {"projections": [proj_medida("Consumo")]},
                          "Series": {"projections": [
                              proj_coluna("dGrupo", "DS_CLASSE", "Natureza")]},
                      },
                      ordenar=[{"field": campo_coluna("dCalendario", "NM_ANO_MES"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": cores_por_categoria("dGrupo", "DS_CLASSE",
                                                           g.CORES_CLASSE),
                          "valueAxis": _eixo(),
                          "categoryAxis": _eixo(),
                          "legend": _legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vSazonal", *g.area_do_visual(P["vSazonal"]),
                      "columnChart", z=42,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dCalendario", "NM_MES_ABREV", "Mês")]},
                          "Y": {"projections": [proj_medida("Consumo")]},
                      },
                      ordenar=[{"field": campo_coluna("dCalendario", "NM_MES_ABREV"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.TURQUESA)}}],
                          "valueAxis": _eixo(),
                          "categoryAxis": _eixo(),
                          "legend": _sem_legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vAnoCat", *g.area_do_visual(P["vAnoCat"]),
                      "barChart", z=43,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dCategoria", "NM_CATEGORIA", "Categoria")]},
                          "Y": {"projections": [proj_medida("Consumo")]},
                      },
                      ordenar=[{"field": campo_medida("Consumo"),
                                "direction": "Descending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.PETROLEO_MED)}}],
                          "labels": _rotulos(8.5),
                          "valueAxis": [{"properties": {"show": lit(False)}}],
                          "categoryAxis": _eixo(),
                          "legend": _sem_legenda(),
                      },
                      container=caixa()))
    return vis


# ======================================================================
# Pagina 3 — onde da para cortar
# ======================================================================

def pagina_compressivel() -> list:
    pag = g.pagina("compressivel")
    P = pag["paineis"]
    vis = _cartoes(pag)
    vis += _filtros(pag, [
        ("kAno", "dCalendario", "NR_ANO", "Ano"),
        ("kClasse", "dGrupo", "DS_CLASSE", "Natureza"),
        ("kOrigem", "dOrigem", "NM_ORIGEM", "Origem"),
        ("kArea", "dArea", "NM_AREA", "Área"),
        ("kCategoria", "dCategoria", "NM_CATEGORIA", "Categoria"),
        ("kGrupo", "dGrupo", "NM_GRUPO", "Grupo"),
    ])

    vis.append(visual("vTopGrupos", *g.area_do_visual(P["vTopGrupos"]),
                      "barChart", z=40,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dGrupo", "NM_GRUPO", "Grupo")]},
                          "Y": {"projections": [proj_medida("Consumo compressível",
                                                            "Compressível")]},
                      },
                      ordenar=[{"field": campo_medida("Consumo compressível"),
                                "direction": "Descending"}],
                      objetos={
                          "dataPoint": [{"properties": {"fill": cor(g.TURQUESA)}}],
                          "labels": _rotulos(8.5),
                          "valueAxis": [{"properties": {"show": lit(False)}}],
                          "categoryAxis": _eixo(),
                          "legend": _sem_legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vCompMes", *g.area_do_visual(P["vCompMes"]),
                      "lineChart", z=41,
                      estado={
                          "Category": {"projections": [
                              proj_coluna("dCalendario", "NM_ANO_MES", "Mês")]},
                          "Y": {"projections": [
                              proj_medida("Consumo compressível", "Compressível"),
                              proj_medida("Consumo", "Consumo total")]},
                      },
                      ordenar=[{"field": campo_coluna("dCalendario", "NM_ANO_MES"),
                                "direction": "Ascending"}],
                      objetos={
                          "dataPoint": [
                              {"properties": {"fill": cor(g.TURQUESA)},
                               "selector": {"metadata": "_Medidas.Consumo compressível"}},
                              {"properties": {"fill": cor(g.CINZA)},
                               "selector": {"metadata": "_Medidas.Consumo"}}],
                          "valueAxis": _eixo(),
                          "categoryAxis": _eixo(),
                          "legend": _legenda(),
                      },
                      container=caixa()))

    vis.append(visual("vDetalhe", *g.area_do_visual(P["vDetalhe"]),
                      "tableEx", z=42,
                      estado={"Values": {"projections": [
                          proj_coluna("dGrupo", "NM_GRUPO", "Grupo"),
                          proj_coluna("dGrupo", "DS_CLASSE", "Natureza"),
                          proj_coluna("dCategoria", "NM_CATEGORIA", "Categoria"),
                          proj_medida("Consumo", "Total"),
                          proj_medida("Meses com gasto", "Meses"),
                          proj_medida("Média mensal", "Por mês"),
                          proj_medida("Lançamentos")]}},
                      ordenar=[{"field": campo_medida("Consumo"),
                                "direction": "Descending"}],
                      objetos=_tabela_objetos(),
                      container=caixa()))
    return vis


MONTADORES = {
    "mes": pagina_mes,
    "historico": pagina_historico,
    "compressivel": pagina_compressivel,
}


def visuais_da(nome: str) -> list:
    return MONTADORES[nome]()
