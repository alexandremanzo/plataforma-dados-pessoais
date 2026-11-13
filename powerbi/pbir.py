"""
Maquina de escrita de projeto Power BI (PBIP): TMDL, PBIR e validacao.

Nao sabe nada sobre gastos nem sobre este painel — so sabe emitir um
projeto que o Power BI Desktop abre. A regra de negocio fica em
gerar_painel.py.

POR QUE UM MODULO. Esta maquina ja tinha sido escrita uma vez, para
outro painel, e cada detalhe aqui custou uma tentativa frustrada:
UTF-8 SEM BOM (o inverso da regra dos .sql deste mesmo projeto), CRLF,
tabulacao no TMDL, bloco de tres crases para valor multilinha, e a
remocao do "$id" dos schemas para a validacao resolver offline.
Reescrever isso de memoria seria repetir os mesmos erros.

VERSOES DE SCHEMA. Extraidas dos proprios pacotes do Power BI Desktop
instalado (2.157 / 26.08), que grava visualContainer 2.12.0 — mais novo
que o publicado no GitHub. Declaramos a ultima versao PUBLICA, porque e
contra ela que da para validar antes de abrir, e o Desktop aceita
versoes anteriores da mesma familia.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------

SCH = "https://developer.microsoft.com/json-schemas/fabric"
S_VISUAL = f"{SCH}/item/report/definition/visualContainer/2.9.0/schema.json"
S_PAGINA = f"{SCH}/item/report/definition/page/2.1.0/schema.json"
S_PAGINAS = f"{SCH}/item/report/definition/pagesMetadata/1.1.0/schema.json"
S_RELATORIO = f"{SCH}/item/report/definition/report/3.3.0/schema.json"
S_VERSAO = f"{SCH}/item/report/definition/versionMetadata/1.0.0/schema.json"
S_PBIR = f"{SCH}/item/report/definitionProperties/2.0.0/schema.json"
S_PBISM = f"{SCH}/item/semanticModel/definitionProperties/1.0.0/schema.json"
S_PLATAFORMA = f"{SCH}/gitIntegration/platformProperties/2.0.0/schema.json"
S_PBIP = f"{SCH}/pbip/pbipProperties/1.0.0/schema.json"

VERSAO_PBIR = "2.0.0"        # constante R.v2 lida dos pacotes do Desktop
TEMA_BASE = "CY26SU08"
TEMA_VERSOES = {"visual": "2.9.0", "page": "2.1.0", "report": "3.3.0"}

PREFIXO_SCHEMA = f"{SCH}/"
TAB = "\t"


def guid(nome: str) -> str:
    """GUID estavel por nome: regerar nao troca as identidades."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"manzo-pbi/{nome}"))


# ======================================================================
# Escrita em disco
# ======================================================================

def escreve(caminho: Path, texto: str) -> None:
    """UTF-8 SEM BOM e CRLF: exigencia do PBIP.

    ATENCAO: e o INVERSO da regra dos .sql deste projeto, onde o BOM e
    obrigatorio para o sqlcmd nao ler UTF-8 como ANSI. Duas regras
    contrarias no mesmo repositorio.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(texto)


def escreve_json(caminho: Path, dados: dict) -> None:
    escreve(caminho, json.dumps(dados, ensure_ascii=False, indent=2))


def apaga_pasta(pasta: Path, tentativas: int = 6) -> None:
    """Remove a pasta, insistindo enquanto algo a estiver segurando."""
    for tentativa in range(tentativas):
        if not pasta.exists():
            return
        try:
            shutil.rmtree(pasta)
            return
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(0.7)


def plataforma(caminho: Path, tipo: str, nome: str) -> None:
    escreve_json(caminho, {
        "$schema": S_PLATAFORMA,
        "metadata": {"type": tipo, "displayName": nome},
        "config": {"version": "2.0", "logicalId": guid(f"{tipo}.{nome}")},
    })


# ======================================================================
# TMDL
# ======================================================================

def bloco(valor: str, nivel: int) -> str:
    """Bloco multilinha TMDL: conteudo e fecho dois niveis abaixo."""
    dentro = TAB * (nivel + 2)
    corpo = "\n".join(dentro + linha if linha.strip() else ""
                      for linha in valor.split("\n"))
    return "```\n" + corpo + "\n" + dentro + "```"


def cita(nome: str) -> str:
    """TMDL exige aspas simples em nome com espaco ou caractere especial."""
    if nome and all(c.isalnum() or c == "_" for c in nome):
        return nome
    return "'" + nome.replace("'", "''") + "'"


def tmdl_coluna(tabela: str, nome: str, tipo: str, *, oculta=False,
                ordena: str | None = None, formato: str | None = None,
                descricao: str | None = None, origem: str | None = None,
                resume: str = "none", calculo: str | None = None) -> str:
    """Coluna do modelo. Com 'calculo', vira coluna CALCULADA em DAX.

    A diferenca no TMDL e so o cabecalho: coluna calculada declara a
    expressao no proprio 'column X = ...' e NAO tem sourceColumn - ela
    nao vem da consulta, nasce depois que o modelo carrega. Emitir as
    duas coisas faria o Desktop recusar a tabela inteira.
    """
    linhas = []
    if descricao:
        linhas.append(f"{TAB}/// {descricao}")
    if calculo is None:
        linhas.append(f"{TAB}column {cita(nome)}")
    elif "\n" in calculo:
        linhas.append(f"{TAB}column {cita(nome)} = " + bloco(calculo, 1))
    else:
        linhas.append(f"{TAB}column {cita(nome)} = {calculo}")
    linhas.append(f"{TAB*2}dataType: {tipo}")
    if formato:
        linhas.append(f"{TAB*2}formatString: {formato}")
    if oculta:
        linhas.append(f"{TAB*2}isHidden")
    linhas.append(f"{TAB*2}lineageTag: {guid(tabela + '.' + nome)}")
    if ordena:
        linhas.append(f"{TAB*2}sortByColumn: {cita(ordena)}")
    linhas.append(f"{TAB*2}summarizeBy: {resume}")
    if calculo is None:
        linhas.append(f"{TAB*2}sourceColumn: {origem or nome}")
    linhas.append("")
    linhas.append(f"{TAB*2}annotation SummarizationSetBy = Automatic")
    return "\n".join(linhas)


def tmdl_medida(nome: str, dax: str, formato: str | None, descricao: str,
                *, oculta=False) -> str:
    linhas = [f"{TAB}/// {descricao}"]
    if "\n" in dax:
        linhas.append(f"{TAB}measure {cita(nome)} = " + bloco(dax, 1))
    else:
        linhas.append(f"{TAB}measure {cita(nome)} = {dax}")
    if formato:
        linhas.append(f"{TAB*2}formatString: {formato}")
    if oculta:
        linhas.append(f"{TAB*2}isHidden")
    linhas.append(f"{TAB*2}lineageTag: {guid('medida.' + nome)}")
    return "\n".join(linhas)


def tmdl_tabela(nome: str, colunas: list, consulta: str, *,
                medidas=None, descricao: str | None = None,
                oculta=False) -> str:
    partes = []
    if descricao:
        partes.append(f"/// {descricao}")
    partes.append(f"table {cita(nome)}")
    if oculta:
        partes.append(f"{TAB}isHidden")
    partes.append(f"{TAB}lineageTag: {guid('tabela.' + nome)}")
    partes.append("")
    for m in (medidas or []):
        partes.append(m)
        partes.append("")
    for c in colunas:
        partes.append(tmdl_coluna(nome, *c[:2], **(c[2] if len(c) > 2 else {})))
        partes.append("")
    partes.append(f"{TAB}partition {cita(nome)} = m")
    partes.append(f"{TAB*2}mode: import")
    partes.append(f"{TAB*2}source = " + bloco(consulta, 2))
    partes.append("")
    partes.append(f"{TAB}annotation PBI_ResultType = Table")
    return "\n".join(partes) + "\n"


def tmdl_relacionamentos(rels: list) -> str:
    """rels: (nome, 'Fato.Coluna', 'Dim.Coluna', ativo)."""
    partes = []
    for nome, de, para, ativo in rels:
        linhas = [f"relationship {nome}"]
        if not ativo:
            linhas.append(f"{TAB}isActive: false")
        linhas.append(f"{TAB}fromColumn: {de}")
        linhas.append(f"{TAB}toColumn: {para}")
        partes.append("\n".join(linhas))
    return "\n\n".join(partes) + "\n"


# ======================================================================
# PBIR
# ======================================================================

def lit(valor) -> dict:
    """Literal do Power BI: texto entre aspas simples, D em double."""
    if isinstance(valor, bool):
        texto = "true" if valor else "false"
    elif isinstance(valor, int):
        texto = f"{valor}L"
    elif isinstance(valor, float):
        texto = f"{valor}D"
    else:
        texto = "'" + str(valor).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": texto}}}


def cor(hexa: str) -> dict:
    return {"solid": {"color": lit(hexa)}}


def campo_coluna(tabela: str, coluna: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabela}},
                       "Property": coluna}}


def campo_medida(medida: str, tabela: str = "_Medidas") -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": tabela}},
                        "Property": medida}}


def proj_coluna(tabela: str, coluna: str, rotulo: str | None = None) -> dict:
    return {"field": campo_coluna(tabela, coluna),
            "queryRef": f"{tabela}.{coluna}",
            "nativeQueryRef": rotulo or coluna}


def proj_medida(medida: str, rotulo: str | None = None) -> dict:
    return {"field": campo_medida(medida),
            "queryRef": f"_Medidas.{medida}",
            "nativeQueryRef": rotulo or medida}


def caixa() -> dict:
    """Container invisivel: moldura e titulo vem da imagem de fundo.

    Deixar fundo, borda ou titulo ligado produz MOLDURA DUPLA — a do
    PNG mais a do Power BI, quase alinhadas e por isso mais feias do
    que se estivessem claramente fora de lugar.
    """
    return {
        "background": [{"properties": {"show": lit(False)}}],
        "border": [{"properties": {"show": lit(False)}}],
        "title": [{"properties": {"show": lit(False)}}],
        "dropShadow": [{"properties": {"show": lit(False)}}],
        "padding": [{"properties": {"top": lit(0.0), "bottom": lit(0.0),
                                    "left": lit(0.0), "right": lit(0.0)}}],
    }


def seletor(tabela: str, coluna: str, valor: str) -> dict:
    """Escopo de um valor de categoria — usado para cor por categoria."""
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0,
        "Left": campo_coluna(tabela, coluna),
        "Right": {"Literal": {"Value": "'" + valor.replace("'", "''") + "'"}},
    }}}]}


def cores_por_categoria(tabela: str, coluna: str, mapa: dict) -> list:
    return [{"properties": {"fill": cor(hexa)},
             "selector": seletor(tabela, coluna, v)}
            for v, hexa in mapa.items()]


def visual(nome: str, x, y, w, h, tipo: str, *, z=100, estado=None,
           objetos=None, container=None, ordenar=None, filtro=None) -> dict:
    v: dict = {"visualType": tipo}
    if estado is not None:
        consulta: dict = {"queryState": estado}
        if ordenar:
            consulta["sortDefinition"] = {"sort": ordenar, "isDefaultSort": True}
        v["query"] = consulta
    if objetos:
        v["objects"] = objetos
    if container:
        v["visualContainerObjects"] = container
    saida = {
        "$schema": S_VISUAL,
        "name": nome,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h,
                     "tabOrder": z},
        "visual": v,
    }
    if filtro:
        saida["filterConfig"] = filtro
    return saida


def fundo_da_pagina(arquivo: str | None, cor_lisa: str) -> dict:
    """Imagem quando existe, cor lisa quando nao.

    A forma do objeto de imagem foi lida de um .pbix que ja usa fundo,
    nao deduzida. 'Fit' porque o PNG e gerado em 2x: mesma proporcao,
    escalado para a tela, com resolucao de sobra em tela grande.
    """
    if not arquivo:
        return {"color": cor(cor_lisa), "transparency": lit(0.0)}
    return {
        "image": {"image": {
            "name": lit(arquivo),
            "url": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources",
                "PackageType": 1,
                "ItemName": arquivo,
            }}},
            "scaling": lit("Fit"),
        }},
        "transparency": lit(0.0),
    }


def pacote_de_recursos(arquivo: str) -> list:
    """No PBIR o 'type' e texto; no formato antigo era numero (1/100)."""
    return [{
        "name": "RegisteredResources",
        "type": "RegisteredResources",
        "items": [{"name": arquivo, "path": arquivo, "type": "Image"}],
    }]


# ======================================================================
# Validacao contra os schemas publicados
# ======================================================================

def _caminho_local(uri: str, cache: Path) -> Path | None:
    """URL do schema -> arquivo espelhado, preservando a arvore.

    A arvore e espelhada porque os schemas se referenciam por caminho
    RELATIVO; guardados na mesma forma, esses refs resolvem sozinhos.
    """
    if not uri.startswith(PREFIXO_SCHEMA):
        return None
    return cache / uri[len(PREFIXO_SCHEMA):]


def _arquivos_json(raiz: Path) -> list:
    """Todo arquivo do projeto que carrega JSON dentro.

    Nem todos terminam em .json: .pbip, .pbir, .pbism e .platform
    tambem sao, tem "$schema" e quebram o projeto do mesmo jeito.
    """
    padroes = ("*.json", "*.pbip", "*.pbir", "*.pbism", ".platform")
    achados = [a for p in padroes for a in raiz.rglob(p)]
    return sorted({a for a in achados if ".schemas" not in a.parts})


def _valida_basico(raiz: Path) -> int:
    erros = 0
    for arquivo in _arquivos_json(raiz):
        try:
            json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  ERRO {arquivo.relative_to(raiz)}: {e}")
            erros += 1

    for arquivo in sorted(raiz.rglob("*")):
        if ".schemas" in arquivo.parts or not arquivo.is_file():
            continue
        if arquivo.suffix.lower() in (".xlsx", ".pbix", ".png", ".pyc", ".abf"):
            continue
        if arquivo.read_bytes().startswith(b"\xef\xbb\xbf"):
            print(f"  ERRO {arquivo.relative_to(raiz)}: tem BOM; "
                  f"o PBIP exige UTF-8 sem BOM")
            erros += 1
    return erros


def valida(raiz: Path, cache: Path) -> int:
    """Valida cada JSON contra o schema que ele declara.

    Roda ANTES de o Desktop abrir: schema invalido e erro BLOQUEANTE,
    o Power BI se recusa a abrir e so aponta o arquivo.
    """
    try:
        import jsonschema
    except ImportError:
        print("  ! jsonschema nao instalado — validacao estrutural apenas.")
        return _valida_basico(raiz)

    if not cache.exists():
        print(f"  ! schemas nao espelhados em {cache} — estrutural apenas.")
        return _valida_basico(raiz)

    erros = _valida_basico(raiz)
    for arquivo in _arquivos_json(raiz):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        local = _caminho_local(dados.get("$schema", ""), cache)
        if local is None or not local.exists():
            print(f"  --   {arquivo.relative_to(raiz)}  (schema nao espelhado)")
            continue

        esquema = json.loads(local.read_text(encoding="utf-8-sig"))
        esquema.pop("$id", None)

        def carrega(uri: str, _cache=cache):
            alvo = _caminho_local(uri, _cache)
            if alvo is None or not alvo.exists():
                raise FileNotFoundError(f"schema nao espelhado: {uri}")
            doc = json.loads(alvo.read_text(encoding="utf-8-sig"))
            doc.pop("$id", None)
            return doc

        resolvedor = jsonschema.RefResolver(
            base_uri=local.resolve().as_uri(), referrer=esquema,
            handlers={"https": carrega, "http": carrega})
        validador = jsonschema.Draft7Validator(esquema, resolver=resolvedor)
        falhas = sorted(validador.iter_errors(dados),
                        key=lambda e: list(e.absolute_path))
        if falhas:
            for e in falhas[:3]:
                onde = "/".join(str(p) for p in e.absolute_path) or "(raiz)"
                print(f"  ERRO {arquivo.relative_to(raiz)}  [{onde}] "
                      f"{e.message[:150]}")
            erros += len(falhas)
        else:
            print(f"  ok   {arquivo.relative_to(raiz)}")
    return erros
