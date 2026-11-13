"""
Prova que cada visual cai dentro da moldura que o PNG desenhou.

O fundo é uma imagem; o visual é um retângulo posicionado por número.
Quando os dois divergem, o Power BI não reclama — desenha o visual meio
fora da caixa e segue. É o jeito clássico de a técnica de imagem de
fundo dar errado, e só se percebe olhando.

Como aqui o PNG e o visual saem da MESMA constante, divergir exigiria
um erro de contenção: um visual grande demais para o painel onde mora,
ou dois pisando um no outro. São esses que este arquivo procura — mais
a moldura dupla, que é o outro sintoma.

Uso:
    python conferir_layout.py
"""

from __future__ import annotations

import json
import sys

import gerar_painel as g

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VISUAIS = (g.BASE / f"{g.PROJETO}.Report" / "definition" / "pages" /
           g.PAGINA["nome"] / "visuals")

CABECALHO = (g.MARGEM, g.CAB_Y, g.LARGURA - 2 * g.MARGEM, g.CAB_H)

# Visual -> painel em que ele mora. O que nao esta aqui nao tem moldura
# declarada, e isso e um erro: visual sem dono e visual que ninguem
# conferiu.
DONO = {
    "fPeriodo": CABECALHO,
    "vComposicao": "vComposicao",
    "vIndicadores": "vIndicadores",
    "vTotalDespesa": "vCartao", "vCartaoVal": "vCartao",
    "vCartaoPct": "vCartao", "vForaVal": "vCartao", "vForaPct": "vCartao",
    "vCategoria": "vCategoria",
    "vMediaDia": "vCalendario", "vCalendario": "vCalendario",
    "vMeta": "vDestaque", "vEconomia": "vDestaque",
    "vOportunidades": "vDestaque",
}

# A legenda de cores do calendario e desenhada no PNG nos ultimos pixels
# do painel. Nenhum visual pode entrar ali.
_cal = g.PAINEIS["vCalendario"]
RESERVADO = {"vCalendario": (_cal["x"], _cal["y"] + _cal["h"] - 28,
                             _cal["w"], 28)}


def moldura_de(nome: str):
    for c in g.CARTOES:
        if nome in (c["nome"], c["nome"] + "Sub"):
            return (c["x"], c["y"], c["w"], c["h"])
    alvo = DONO.get(nome)
    if alvo is None:
        return None
    if isinstance(alvo, tuple):
        return alvo
    p = g.PAINEIS[alvo]
    return (p["x"], p["y"], p["w"], p["h"])


def dentro(filho, pai) -> bool:
    fx, fy, fw, fh = filho
    px, py, pw, ph = pai
    return fx >= px and fy >= py and fx + fw <= px + pw and fy + fh <= py + ph


def sobrepoe(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax
                or ay + ah <= by or by + bh <= ay)


def desligado(objetos: dict, chave: str) -> bool:
    try:
        return (objetos[chave][0]["properties"]["show"]["expr"]
                ["Literal"]["Value"] == "false")
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

        if not dentro(caixa, (0, 0, g.LARGURA, g.ALTURA)):
            problemas.append(f"{nome} sai da tela: {caixa}")

        m = moldura_de(nome)
        if m is None:
            problemas.append(f"{nome} não tem moldura declarada em DONO")
        elif not dentro(caixa, m):
            problemas.append(f"{nome} {caixa} escapa da moldura {m}")

        # O container mora DENTRO de "visual", não no topo do arquivo.
        cont = v["visual"].get("visualContainerObjects", {})
        for chave in ("background", "border", "title"):
            if not desligado(cont, chave):
                problemas.append(f"{nome} está com '{chave}' ligado — "
                                 f"moldura dupla com o PNG")

        res = RESERVADO.get(DONO.get(nome) if isinstance(DONO.get(nome), str)
                            else None)
        if res and sobrepoe(caixa, res):
            problemas.append(f"{nome} invade a área reservada do PNG {res}")

    nomes = sorted(caixas)
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            if sobrepoe(caixas[a], caixas[b]):
                problemas.append(f"{a} e {b} se sobrepõem: "
                                 f"{caixas[a]} × {caixas[b]}")

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
