"""
Confere que a moldura desenhada e o visual que fica por cima concordam.

A tecnica de imagem de fundo tem um modo de falhar: o PNG e desenhado
num lugar e as posicoes sao digitadas noutro, e no primeiro ajuste os
dois divergem. Aqui a grade e a mesma, entao o teste e barato — reler o
que foi gravado e conferir que bate com a constante.

Confere tambem MOLDURA DUPLA: visual com fundo, borda ou titulo ligado
sobre uma moldura que ja existe no PNG. Duas bordas quase alinhadas ficam
mais feias do que uma claramente fora do lugar.

Uso:
    python conferir_layout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gerar_painel import (  # noqa: E402
    ALTURA, BASE, CAB_H, LARGURA, PAGINAS, PROJETO, area_do_valor,
    area_do_visual, fundo_da,
)

RELATORIO = BASE / f"{PROJETO}.Report"
DEFINICAO = RELATORIO / "definition"
TOLERANCIA = 0.01

# O cartao de situacao e os filtros ocupam a faixa logo abaixo do
# cabecalho; so eles podem comecar antes do fim dele.
NA_FAIXA = {"mSituacao", "mPercent"}


def perto(a, b) -> bool:
    return abs(float(a) - float(b)) <= TOLERANCIA


def main() -> int:
    if not DEFINICAO.exists():
        print(f"ERRO: {DEFINICAO} nao existe. Rode gerar_painel.py antes.")
        return 1

    problemas, conferidos, total = [], 0, 0

    for pag in PAGINAS:
        pasta = DEFINICAO / "pages" / pag["nome"]
        vis = {}
        for f in sorted(pasta.glob("visuals/*/visual.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            vis[d["name"]] = d
        total += len(vis)

        esperado = {n: area_do_visual(p) for n, p in pag["paineis"].items()}
        esperado.update({c["nome"]: area_do_valor(c) for c in pag["cartoes"]})

        for nome, (x, y, w, h) in esperado.items():
            if nome not in vis:
                problemas.append(f"{pag['nome']}/{nome}: nao foi gerado")
                continue
            pos = vis[nome]["position"]
            real = (pos["x"], pos["y"], pos["width"], pos["height"])
            if not all(perto(a, b) for a, b in zip(real, (x, y, w, h))):
                problemas.append(
                    f"{pag['nome']}/{nome}: gravado {real} != grade "
                    f"({x}, {y}, {w}, {h})")
            conferidos += 1

        # o visual cabe dentro da moldura que o PNG desenha
        for nome, p in pag["paineis"].items():
            if nome not in vis:
                continue
            pos = vis[nome]["position"]
            if (pos["x"] < p["x"] - TOLERANCIA or pos["y"] < p["y"] - TOLERANCIA
                    or pos["x"] + pos["width"] > p["x"] + p["w"] + TOLERANCIA
                    or pos["y"] + pos["height"] > p["y"] + p["h"] + TOLERANCIA):
                problemas.append(f"{pag['nome']}/{nome}: transborda a moldura")

        for nome, d in vis.items():
            cont = d["visual"].get("visualContainerObjects", {})
            for chave in ("background", "border", "title"):
                try:
                    v = cont[chave][0]["properties"]["show"]["expr"]["Literal"]["Value"]
                except (KeyError, IndexError, TypeError):
                    continue
                if v == "true":
                    problemas.append(
                        f"{pag['nome']}/{nome}: '{chave}' ligado — "
                        f"moldura dupla com o PNG")

            pos = d["position"]
            if pos["x"] < -TOLERANCIA or pos["y"] < -TOLERANCIA:
                problemas.append(f"{pag['nome']}/{nome}: comeca fora da tela")
            if pos["x"] + pos["width"] > LARGURA + TOLERANCIA:
                problemas.append(f"{pag['nome']}/{nome}: passa da largura")
            if pos["y"] + pos["height"] > ALTURA + TOLERANCIA:
                problemas.append(f"{pag['nome']}/{nome}: passa da altura")
            if nome not in NA_FAIXA and pos["y"] < CAB_H - TOLERANCIA:
                problemas.append(f"{pag['nome']}/{nome}: entra no cabecalho")

        # a imagem de fundo desta pagina esta presente e apontada
        arq = fundo_da(pag["nome"])
        png = RELATORIO / "StaticResources" / "RegisteredResources" / arq
        if not png.exists():
            problemas.append(f"{pag['nome']}: fundo ausente ({arq})")
        conf = json.loads((pasta / "page.json").read_text("utf-8"))
        try:
            alvo = (conf["objects"]["background"][0]["properties"]["image"]
                    ["image"]["url"]["expr"]["ResourcePackageItem"]["ItemName"])
        except (KeyError, IndexError, TypeError):
            alvo = None
        if alvo != arq:
            problemas.append(f"{pag['nome']}: page.json aponta para {alvo!r}")

    # todos os fundos declarados no report.json
    rel = json.loads((DEFINICAO / "report.json").read_text("utf-8"))
    itens = {i["name"] for p in rel.get("resourcePackages", []) for i in p["items"]}
    for pag in PAGINAS:
        if fundo_da(pag["nome"]) not in itens:
            problemas.append(f"report.json nao declara {fundo_da(pag['nome'])}")

    print(f"{len(PAGINAS)} paginas, {total} visuais lidos, "
          f"{conferidos} conferidos contra a grade.")
    if problemas:
        print()
        for p in problemas:
            print(f"  ERRO {p}")
        print(f"\n{len(problemas)} problema(s).")
        return 1
    print("Moldura e visuais alinhados; sem moldura dupla; fundos declarados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
