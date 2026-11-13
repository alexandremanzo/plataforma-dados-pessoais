"""
Prova que cada visual cai dentro da moldura que o PNG desenhou.

O fundo e uma imagem; o visual e um retangulo posicionado por numero.
Quando os dois divergem, o Power BI nao reclama — desenha o grafico
meio fora da caixa e segue. E o jeito classico de a tecnica de imagem
de fundo dar errado, e so se percebe olhando.

Como aqui o PNG e o visual saem da MESMA constante, divergir exigiria
um erro de contencao: um visual grande demais para o painel onde mora,
ou dois visuais pisando um no outro. Sao esses dois que este arquivo
procura — mais a moldura dupla, que e o outro sintoma.

Uso:
    python conferir_layout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import gerar_painel as g

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VISUAIS = (g.BASE / f"{g.PROJETO}.Report" / "definition" / "pages" /
           g.PAGINA["nome"] / "visuals")

CABECALHO = (g.MARGEM, 8, g.LARGURA - 2 * g.MARGEM, g.CAB_H - 8)


def moldura_de(nome: str) -> tuple | None:
    """A caixa desenhada no PNG dentro da qual este visual tem de caber."""
    if nome in ("fPeriodo", "vAviso"):
        return CABECALHO
    for c in g.CARTOES:
        if nome in (c["nome"], c["nome"] + "Sub"):
            return (c["x"], c["y"], c["w"], c["h"])
    if nome == "vHistorico":
        p = g.PAINEIS["vHistorico"]
        return (p["x"], p["y"], p["w"], p["h"])
    if nome == "vTop5":
        p = g.PAINEIS["vTop5"]
        return (p["x"], p["y"], p["w"], p["h"])
    if nome.startswith("vNe"):
        p = g.PAINEIS["vNaoEssencial"]
        return (p["x"], p["y"], p["w"], p["h"])
    return None


def dentro(filho: tuple, pai: tuple) -> bool:
    fx, fy, fw, fh = filho
    px, py, pw, ph = pai
    return (fx >= px and fy >= py
            and fx + fw <= px + pw and fy + fh <= py + ph)


def sobrepoe(a: tuple, b: tuple) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax
                or ay + ah <= by or by + bh <= ay)


def desligado(objetos: dict, chave: str) -> bool:
    """O container tem de dizer explicitamente que nao desenha nada."""
    try:
        return objetos[chave][0]["properties"]["show"]["expr"]["Literal"]["Value"] == "false"
    except (KeyError, IndexError, TypeError):
        return False


def main() -> int:
    caixas, problemas = {}, []

    for arq in sorted(VISUAIS.glob("*/visual.json")):
        v = json.loads(arq.read_text(encoding="utf-8"))
        nome = v["name"]
        p = v["position"]
        caixa = (p["x"], p["y"], p["width"], p["height"])
        caixas[nome] = caixa

        # 1. cabe na tela
        if not dentro(caixa, (0, 0, g.LARGURA, g.ALTURA)):
            problemas.append(f"{nome} sai da tela: {caixa}")

        # 2. cabe na moldura que o PNG desenhou
        m = moldura_de(nome)
        if m is None:
            problemas.append(f"{nome} não tem moldura declarada em moldura_de()")
        elif not dentro(caixa, m):
            problemas.append(f"{nome} {caixa} escapa da moldura {m}")

        # 3. nada de moldura dupla
        # O container mora DENTRO de "visual", nao no topo do arquivo.
        # Lido no topo, vinha sempre vazio e todo visual era acusado —
        # um conferidor que acusa todo mundo nao confere nada.
        cont = v["visual"].get("visualContainerObjects", {})
        for chave in ("background", "border", "title"):
            if not desligado(cont, chave):
                problemas.append(f"{nome} está com '{chave}' ligado — "
                                 f"moldura dupla com o PNG")

    # 4. nenhum visual pisa em outro
    nomes = sorted(caixas)
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            if sobrepoe(caixas[a], caixas[b]):
                problemas.append(f"{a} e {b} se sobrepõem: "
                                 f"{caixas[a]} × {caixas[b]}")

    # 5. o rodape e area morta: nada pode cair ali
    for nome, (x, y, w, h) in caixas.items():
        if y + h > g.RODAPE_Y:
            problemas.append(f"{nome} invade o rodapé (passa de y={g.RODAPE_Y})")

    print(f"  visuais conferidos   {len(caixas)}")
    print(f"  tela                 {g.LARGURA} x {g.ALTURA}")
    print(f"  pares testados       {len(nomes) * (len(nomes) - 1) // 2}")
    print()
    for p in problemas:
        print(f"  PROBLEMA  {p}")
    if problemas:
        print(f"\n{len(problemas)} problema(s) de layout.")
        return 1
    print("Layout consistente: todo visual dentro da sua moldura, "
          "nenhum sobreposto, nenhuma moldura dupla.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
