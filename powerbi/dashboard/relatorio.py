"""
Monta a página "Finanças Geral" (PBIR), fiel ao esboço em PDF.

Separado de gerar_painel.py só por tamanho: lá fica o modelo, aqui a
tela. A grade vem de gerar_painel, que também alimenta o desenho do
fundo — o mesmo retângulo posiciona o visual e desenha a moldura, então
os dois não têm como divergir.

TODO VISUAL ENTRA TRANSPARENTE. Moldura, título e rótulo são do PNG;
deixar fundo ou borda do Power BI ligados produz moldura dupla, quase
alinhada — e por isso mais feia do que se estivesse claramente fora de
lugar.
"""

from __future__ import annotations

from pbir import (
    caixa, campo_coluna, campo_medida, cor, lit, proj_coluna, proj_medida,
    visual,
)

import gerar_painel as g


# ----------------------------------------------------------------------
# Peças repetidas
# ----------------------------------------------------------------------

def _valor(tinta: str, tam=26.0, alinha="left") -> dict:
    return {
        "labels": [{"properties": {
            "color": cor(tinta), "fontSize": lit(tam), "bold": lit(True),
            "fontFamily": lit(g.FONTE_FORTE), "labelDisplayUnits": lit(0.0),
            "alignment": lit(alinha)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}],
    }


def _texto(tinta: str, tam=9.5, alinha="left", forte=False) -> dict:
    return {
        "labels": [{"properties": {
            "color": cor(tinta), "fontSize": lit(tam),
            "fontFamily": lit(g.FONTE_FORTE if forte else g.FONTE),
            "alignment": lit(alinha)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}],
    }


def _cartao(nome, medida, area, tinta, z, **estilo) -> dict:
    return visual(nome, *area, "card", z=z,
                  estado={"Values": {"projections": [proj_medida(medida)]}},
                  objetos=_valor(tinta, **estilo), container=caixa())


def _cartao_texto(nome, medida, area, tinta, z, **estilo) -> dict:
    return visual(nome, *area, "card", z=z,
                  estado={"Values": {"projections": [proj_medida(medida)]}},
                  objetos=_texto(tinta, **estilo), container=caixa())


def _tabela(cabecalho_fundo=None, tam=10.0, listrado=False) -> dict:
    """Tabela sem moldura: as linhas do PNG já separam o conteúdo."""
    return {
        "grid": [{"properties": {
            "gridVertical": lit(False), "gridHorizontal": lit(True),
            "gridHorizontalColor": cor(g.BORDA), "rowPadding": lit(6.0),
            "outlineColor": cor(g.BORDA), "outlineWeight": lit(0.0)}}],
        "columnHeaders": [{"properties": {
            "fontColor": cor(g.TEXTO_FRACO),
            "backColor": cor(cabecalho_fundo or "#F1F5F9"),
            "fontSize": lit(9.0), "bold": lit(True),
            "fontFamily": lit(g.FONTE_FORTE)}}],
        "values": [{"properties": {
            "fontColor": cor(g.TEXTO), "fontSize": lit(tam),
            "fontFamily": lit(g.FONTE),
            "backColorPrimary": cor(g.CARTAO),
            "backColorSecondary": cor("#F8FAFC" if listrado else g.CARTAO)}}],
        "total": [{"properties": {"totals": lit(False)}}],
    }


def _barras(medida: str, tinta: str) -> list:
    """Barra de dados numa coluna de medida da tabela.

    Se a versão do Desktop ignorar o objeto, a tabela continua certa —
    só sem a barra, e ligá-la é um clique em Formatar > Barras de dados.
    """
    return [{"properties": {
        "show": lit(True), "positiveColor": cor(tinta),
        "axisColor": cor(g.BORDA), "hideText": lit(False)},
        "selector": {"metadata": f"_Medidas.{medida}"}}]


# ----------------------------------------------------------------------
# A página
# ----------------------------------------------------------------------

def visuais() -> list:
    vis = []
    P = g.PAINEIS

    # --- cabeçalho: o seletor de período ------------------------------
    vis.append(visual(
        "fPeriodo", *g.cx(g.SELETOR), "slicer", z=10,
        estado={"Values": {"projections": [
            proj_coluna("dim_calendario", "NM_MES_ANO", "Período")]}},
        objetos={
            "data": [{"properties": {"mode": lit("Dropdown")}}],
            # "Período:" já está desenhado no PNG, à esquerda da caixa.
            "header": [{"properties": {"show": lit(False)}}],
            "items": [{"properties": {
                "fontColor": cor(g.TEXTO), "fontSize": lit(10.5),
                "fontFamily": lit(g.FONTE_FORTE),
                "background": cor(g.BRANCO)}}],
        },
        container=caixa()))

    # --- 1. os quatro cartões do topo ---------------------------------
    for i, c in enumerate(g.CARTOES):
        vis.append(_cartao(c["nome"], c["medida"], g.area_do_valor(c),
                           c["cor"], 20 + i, tam=25.0))
        vis.append(_cartao_texto(c["nome"] + "Sub", c["sub"], g.area_do_sub(c),
                                 g.TEXTO_FRACO, 30 + i, tam=9.5))

    # --- 2. composição de entradas e saídas ----------------------------
    vis.append(visual(
        "vComposicao", *g.area_do_visual(P["vComposicao"]), "tableEx", z=40,
        estado={"Values": {"projections": [
            proj_coluna("Composicao", "Fluxo", "Fluxo"),
            proj_coluna("Composicao", "Item", "Origem / Destino"),
            proj_medida("Valor da composição", "Valor (R$)")]}},
        ordenar=[{"field": campo_coluna("Composicao", "Item"),
                  "direction": "Ascending"}],
        objetos=_tabela(),
        container=caixa()))

    # --- 3. indicadores percentuais ------------------------------------
    vis.append(visual(
        "vIndicadores", *g.area_do_visual(P["vIndicadores"]), "tableEx", z=41,
        estado={"Values": {"projections": [
            proj_coluna("Indicadores", "Indicador", "Indicador"),
            proj_medida("Valor do indicador", "%")]}},
        ordenar=[{"field": campo_coluna("Indicadores", "Indicador"),
                  "direction": "Ascending"}],
        objetos=dict(_tabela(tam=9.5),
                     dataBars=_barras("Valor do indicador", g.AZUL)),
        container=caixa()))

    # --- 4. cartão de crédito x outros gastos --------------------------
    vis.append(_cartao_texto("vTotalDespesa", "Despesa total",
                             g.cx(g.CT_TOTAL), g.TEXTO_FRACO, 50,
                             tam=9.5, alinha="right"))
    vis.append(_cartao("vCartaoVal", "Despesa no cartão", g.cx(g.CT_VAL_E),
                       g.AZUL, 51, tam=24.0))
    vis.append(_cartao("vCartaoPct", "% no cartão", g.cx(g.CT_PCT_E),
                       g.AZUL, 52, tam=13.0, alinha="right"))
    vis.append(_cartao("vForaVal", "Despesa fora do cartão", g.cx(g.CT_VAL_D),
                       g.CIANO, 53, tam=24.0))
    vis.append(_cartao("vForaPct", "% fora do cartão", g.cx(g.CT_PCT_D),
                       g.CIANO, 54, tam=13.0, alinha="right"))

    # --- 5. top 5 de categorias ----------------------------------------
    # O corte em cinco vem da MEDIDA: do sexto em diante tudo volta
    # branco, e a tabela descarta sozinha a linha toda branca. Não
    # depende de filterConfig, que o PBIR grava de forma frágil.
    vis.append(visual(
        "vCategoria", *g.area_do_visual(P["vCategoria"]), "tableEx", z=60,
        estado={"Values": {"projections": [
            proj_medida("Posição da categoria", "#"),
            proj_coluna("dim_categoria_financ", "NM_CATEGORIA", "Categoria"),
            proj_medida("Despesa da categoria", "Valor (R$)"),
            proj_medida("% da categoria", "% Total")]}},
        ordenar=[{"field": campo_medida("Posição da categoria"),
                  "direction": "Ascending"}],
        objetos=dict(_tabela(), dataBars=_barras("% da categoria", g.VERMELHO)),
        container=caixa()))

    # --- 6. calendário --------------------------------------------------
    vis.append(_cartao_texto("vMediaDia", "Gasto médio do dia no mês",
                             g.cx(g.CAL_MEDIA), g.TEXTO_FRACO, 70,
                             tam=9.5, alinha="right"))
    vis.append(visual(
        "vCalendario", *g.cx(g.CAL_MATRIZ), "pivotTable", z=71,
        estado={
            "Rows": {"projections": [
                proj_coluna("dim_calendario", "NR_SEMANA_MES", "Semana")]},
            "Columns": {"projections": [
                proj_coluna("dim_calendario", "NM_DIA_SEMANA_ABREV", "Dia")]},
            "Values": {"projections": [proj_medida("Gasto do dia", "Gasto")]},
        },
        objetos={
            "grid": [{"properties": {
                "gridVertical": lit(True), "gridHorizontal": lit(True),
                "gridVerticalColor": cor(g.BORDA),
                "gridHorizontalColor": cor(g.BORDA),
                "rowPadding": lit(10.0), "outlineWeight": lit(0.0)}}],
            "columnHeaders": [{"properties": {
                "fontColor": cor(g.TEXTO_FRACO), "backColor": cor("#F1F5F9"),
                "fontSize": lit(9.0), "bold": lit(True),
                "fontFamily": lit(g.FONTE_FORTE)}}],
            "rowHeaders": [{"properties": {"show": lit(False)}}],
            "values": [{"properties": {
                "fontColor": cor(g.TEXTO), "fontSize": lit(9.5),
                "fontFamily": lit(g.FONTE)}}],
            "subTotals": [{"properties": {
                "rowSubtotals": lit(False), "columnSubtotals": lit(False)}}],
        },
        container=caixa()))

    # --- 7. oportunidades de corte ---------------------------------------
    vis.append(_cartao_texto("vMeta", "Meta pelos 3 maiores", g.cx(g.DQ_META),
                             g.VERMELHO, 80, tam=10.0, alinha="right",
                             forte=True))
    vis.append(_cartao_texto("vEconomia", "Economia potencial",
                             g.cx(g.DQ_ECONOMIA), g.TARJA_TEXTO, 81,
                             tam=9.5, alinha="right", forte=True))
    # O esboço desenha três caixas. Aqui é uma tabela de três linhas: a
    # medida já corta no terceiro, e três cartões separados exigiriam o
    # grupo no contexto de cada um — o que um cartão não tem.
    vis.append(visual(
        "vOportunidades", *g.cx(g.DQ_TABELA), "tableEx", z=82,
        estado={"Values": {"projections": [
            proj_medida("Posição da oportunidade", "#"),
            proj_coluna("dim_grupo_financ", "NM_GRUPO", "Grupo"),
            proj_coluna("dim_grupo_financ", "NM_CLASSE", "Natureza"),
            proj_medida("Valor da oportunidade", "No mês (R$)")]}},
        ordenar=[{"field": campo_medida("Posição da oportunidade"),
                  "direction": "Ascending"}],
        objetos=dict(_tabela(cabecalho_fundo=g.TARJA_FUNDO, tam=10.5),
                     dataBars=_barras("Valor da oportunidade", g.AMBAR)),
        container=caixa()))
    return vis
