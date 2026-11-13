"""
Monta a unica pagina do painel de financas (PBIR).

Separado de gerar_painel.py so por tamanho: la fica o modelo, aqui a
tela. A grade vem de gerar_painel, que tambem alimenta o desenho do
fundo — o mesmo retangulo posiciona o visual e desenha a moldura, entao
os dois nao tem como divergir.

TODO VISUAL ENTRA TRANSPARENTE. Moldura, titulo e rotulo sao do PNG;
deixar o fundo ou a borda do Power BI ligados produz moldura dupla,
quase alinhada — e por isso mais feia do que se estivesse claramente
fora de lugar.
"""

from __future__ import annotations

from pbir import (
    caixa, campo_coluna, campo_medida, cor, lit, proj_coluna, proj_medida,
    visual,
)

import gerar_painel as g


# ----------------------------------------------------------------------
# Pecas repetidas
# ----------------------------------------------------------------------

def _eixo(tam=9.0, titulo=False, mostrar=True) -> list:
    return [{"properties": {
        "show": lit(mostrar), "showAxisTitle": lit(titulo),
        "fontColor": cor(g.TEXTO_FRACO), "fontSize": lit(tam)}}]


def _legenda(pos="TopRight") -> list:
    return [{"properties": {"show": lit(True), "position": lit(pos),
                            "fontColor": cor(g.TEXTO_FRACO),
                            "fontSize": lit(9.0)}}]


def _sem_legenda() -> list:
    return [{"properties": {"show": lit(False)}}]


def _valor(tinta: str, tam=26.0, alinha="left") -> dict:
    """O numero grande de um cartao. O rotulo acima dele vem do PNG."""
    return {
        "labels": [{"properties": {
            "color": cor(tinta), "fontSize": lit(tam), "bold": lit(True),
            "fontFamily": lit(g.FONTE_FORTE), "labelDisplayUnits": lit(0.0),
            "alignment": lit(alinha)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}],
    }


def _texto(tinta: str, tam=9.5, alinha="left", quebra=False) -> dict:
    """Cartao que carrega uma medida de TEXTO, nao um numero."""
    props = {"color": cor(tinta), "fontSize": lit(tam),
             "fontFamily": lit(g.FONTE), "alignment": lit(alinha)}
    if quebra:
        props["wordWrap"] = lit(True)
    return {
        "labels": [{"properties": props}],
        "categoryLabels": [{"properties": {"show": lit(False)}}],
    }


def _cartao(nome: str, medida: str, area: tuple, tinta: str, z: int,
            **estilo) -> dict:
    return visual(nome, *area, "card", z=z,
                  estado={"Values": {"projections": [proj_medida(medida)]}},
                  objetos=_valor(tinta, **estilo), container=caixa())


def _cartao_texto(nome: str, medida: str, area: tuple, tinta: str, z: int,
                  **estilo) -> dict:
    return visual(nome, *area, "card", z=z,
                  estado={"Values": {"projections": [proj_medida(medida)]}},
                  objetos=_texto(tinta, **estilo), container=caixa())


def _area(d: dict) -> tuple:
    return (d["x"], d["y"], d["w"], d["h"])


# ----------------------------------------------------------------------
# A pagina
# ----------------------------------------------------------------------

def visuais() -> list:
    vis = []

    # --- cabecalho: seletor de periodo e aviso de mes parcial ----------
    vis.append(visual(
        "fPeriodo", *_area(g.SELETOR), "slicer", z=10,
        estado={"Values": {"projections": [
            proj_coluna("dPeriodo", "NM_PERIODO", "Período")]}},
        objetos={
            "data": [{"properties": {"mode": lit("Dropdown")}}],
            # Sem cabecalho proprio: "Período Selecionado:" ja esta
            # desenhado no PNG, a esquerda da caixa.
            "header": [{"properties": {"show": lit(False)}}],
            "items": [{"properties": {
                "fontColor": cor(g.TEXTO), "fontSize": lit(10.5),
                "fontFamily": lit(g.FONTE_FORTE),
                "background": cor(g.BRANCO)}}],
        },
        container=caixa()))

    vis.append(_cartao_texto("vAviso", "Aviso do período", _area(g.AVISO),
                             g.NAVY_FRACO, 11, tam=9.0, alinha="right"))

    # --- os quatro cartoes do topo -------------------------------------
    for i, c in enumerate(g.CARTOES):
        vis.append(_cartao(c["nome"], c["medida"], g.area_do_valor(c),
                           c["cor"], 20 + i))
        vis.append(_cartao_texto(c["nome"] + "Sub", c["sub"],
                                 g.area_do_sub(c), g.TEXTO_FRACO, 30 + i))

    # --- historico de doze meses ---------------------------------------
    # A linha de receita recorrente e tracejada de proposito: ela nao e
    # caixa, e referencia. Ver a despesa cruzando o salario em meses que
    # o total fecha positivo e a informacao que o modelo em PDF nao tinha
    # como mostrar, porque os numeros dele eram ficticios.
    vis.append(visual(
        "vHistorico", *g.area_do_visual(g.PAINEIS["vHistorico"]),
        "lineChart", z=40,
        estado={
            "Category": {"projections": [
                proj_coluna("dCalendario", "NM_MES_ANO", "Mês")]},
            "Y": {"projections": [
                proj_medida("Receita (12m)", "Receitas"),
                proj_medida("Despesa (12m)", "Despesas"),
                proj_medida("Receita recorrente (12m)", "Só salário")]},
        },
        ordenar=[{"field": campo_coluna("dCalendario", "NM_MES_ANO"),
                  "direction": "Ascending"}],
        objetos={
            "dataPoint": [
                {"properties": {"fill": cor(g.VERDE)},
                 "selector": {"metadata": "_Medidas.Receita (12m)"}},
                {"properties": {"fill": cor(g.VERMELHO)},
                 "selector": {"metadata": "_Medidas.Despesa (12m)"}},
                {"properties": {"fill": cor(g.TEXTO_FRACO)},
                 "selector": {"metadata": "_Medidas.Receita recorrente (12m)"}},
            ],
            "lineStyles": [
                {"properties": {"strokeWidth": lit(2.5),
                                "lineStyle": lit("solid")},
                 "selector": {"metadata": "_Medidas.Receita (12m)"}},
                {"properties": {"strokeWidth": lit(2.5),
                                "lineStyle": lit("solid")},
                 "selector": {"metadata": "_Medidas.Despesa (12m)"}},
                {"properties": {"strokeWidth": lit(1.5),
                                "lineStyle": lit("dashed")},
                 "selector": {"metadata": "_Medidas.Receita recorrente (12m)"}},
            ],
            "labels": [{"properties": {"show": lit(False)}}],
            "valueAxis": _eixo(),
            "categoryAxis": _eixo(),
            "legend": _legenda("TopRight"),
        },
        container=caixa()))

    # --- top 5 de categorias -------------------------------------------
    # O corte em cinco nao vem de filtro de visual: vem de RANKX dentro
    # da medida, que devolve branco do sexto em diante. Linha com todas
    # as medidas brancas e descartada pela tabela, entao o top 5 nasce
    # sozinho — e nao depende de filterConfig, que o PBIR grava de um
    # jeito que o Desktop reescreve na primeira edicao.
    vis.append(visual(
        "vTop5", *g.area_do_visual(g.PAINEIS["vTop5"]), "tableEx", z=41,
        estado={"Values": {"projections": [
            proj_medida("Posição da categoria", "#"),
            proj_coluna("dCategoria", "NM_CATEGORIA", "Categoria"),
            proj_medida("Despesa da categoria", "Valor (R$)"),
            proj_medida("% da despesa (categoria)", "% da despesa")]}},
        ordenar=[{"field": campo_medida("Posição da categoria"),
                  "direction": "Ascending"}],
        objetos={
            "grid": [{"properties": {
                "gridVertical": lit(False), "gridHorizontal": lit(True),
                "gridHorizontalColor": cor(g.BORDA), "rowPadding": lit(8.0),
                "outlineColor": cor(g.BORDA), "outlineWeight": lit(0.0)}}],
            "columnHeaders": [{"properties": {
                "fontColor": cor(g.TEXTO_FRACO), "backColor": cor("#F1F5F9"),
                "fontSize": lit(9.5), "bold": lit(True),
                "fontFamily": lit(g.FONTE_FORTE)}}],
            "values": [{"properties": {
                "fontColor": cor(g.TEXTO), "fontSize": lit(10.5),
                "fontFamily": lit(g.FONTE),
                "backColorPrimary": cor(g.CARTAO),
                "backColorSecondary": cor(g.CARTAO)}}],
            "total": [{"properties": {"totals": lit(False)}}],
            # A barra colorida do modelo. Se a versao do Desktop ignorar
            # este objeto a tabela continua certa, so sem a barra — e
            # liga-la a mao custa um clique em Formatar > Barras de dados.
            "dataBars": [{"properties": {
                "show": lit(True), "positiveColor": cor(g.AZUL),
                "axisColor": cor(g.BORDA), "hideText": lit(False)},
                "selector": {"metadata": "_Medidas.% da despesa (categoria)"}}],
        },
        container=caixa()))

    # --- bloco de gastos nao essenciais --------------------------------
    vis.append(_cartao("vNeTotal", "Não essencial", _area(g.NE_TOTAL),
                       g.VERMELHO, 50, tam=24.0))
    vis.append(_cartao_texto("vNeTotalSub", "Não essencial em contexto",
                             _area(g.NE_TOTAL_SUB), g.TEXTO_FRACO, 51, tam=9.0))
    vis.append(_cartao("vNePotencial", "Potencial de economia",
                       _area(g.NE_POTENCIAL), g.VERDE, 52, tam=24.0))
    vis.append(_cartao_texto("vNePotencialSub", "Potencial em contexto",
                             _area(g.NE_POTENCIAL_SUB), g.TEXTO_FRACO, 53,
                             tam=9.0))

    # Onde o modelo em PDF trazia tres caixas escritas a mao (streaming,
    # delivery, compras impulsivas), aqui entram os grupos que a base
    # realmente aponta — o de-para ja existe em
    # gold.dim_grupo_financ.DS_COMPRESSIBILIDADE.
    vis.append(visual(
        "vNeGrupos", *_area(g.NE_GRUPOS), "barChart", z=54,
        estado={
            "Category": {"projections": [
                proj_coluna("dGrupo", "NM_GRUPO", "Grupo")]},
            "Y": {"projections": [
                proj_medida("Não essencial do grupo", "No mês")]},
        },
        ordenar=[{"field": campo_medida("Não essencial do grupo"),
                  "direction": "Descending"}],
        objetos={
            "dataPoint": [{"properties": {"fill": cor(g.AMBAR)}}],
            "labels": [{"properties": {
                "show": lit(True), "fontSize": lit(8.5),
                "color": cor(g.TEXTO_FRACO)}}],
            "valueAxis": _eixo(mostrar=False),
            "categoryAxis": _eixo(8.5),
            "legend": _sem_legenda(),
        },
        container=caixa()))

    vis.append(_cartao_texto("vNeImpacto", "Impacto no planejamento",
                             _area(g.NE_IMPACTO), "#065F46", 55,
                             tam=9.5, quebra=True))
    return vis
