"""
Desenha a moldura da pagina como imagem de fundo.

O Power BI nao desenha canto arredondado decente, sombra, tarja colorida
nem tipografia fina. Desenhados aqui, desenham-se uma vez e ficam
perfeitos; os visuais entram por cima, transparentes, cuidando so do
dado.

A GRADE VEM DE gerar_painel. O mesmo retangulo que posiciona o visual
desenha a moldura, entao nao ha como divergirem — que e o unico jeito de
essa tecnica dar errado.

Uso:
    python gerar_fundo.py
    python gerar_fundo.py --previa
"""

from __future__ import annotations

import argparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import gerar_painel as g

ESCALA = 2                  # 2560 x 2000: sobra resolucao para tela grande

F_REG = r"C:\Windows\Fonts\segoeui.ttf"
F_SEMI = r"C:\Windows\Fonts\seguisb.ttf"
F_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"

TITULO = "DASHBOARD DE FINANÇAS PESSOAIS"
SUBTITULO = "Acompanhamento financeiro mensal e visão histórica"
ROTULO_PERIODO = "Período Selecionado:"

NE_DESCRICAO = "Itens com potencial de corte ou renegociação."
NE_ROT_TOTAL = "TOTAL NO MÊS"
NE_ROT_POTENCIAL = "POTENCIAL DE ECONOMIA"
NE_ROT_IMPACTO = "IMPACTO NO PLANEJAMENTO"

RODAPE_ESQ = "Origem: db-manzo · gold.fato_movto_financ (nível ANALITICO)"
RODAPE_DIR = ("Aporte, resgate e transferência ficam fora: não são receita "
              "nem gasto.")


def e(v) -> int:
    return int(round(v * ESCALA))


def fonte(caminho: str, tamanho: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(caminho, e(tamanho))


def sombra(base: Image.Image, retangulos, raio=10, desloc=2, desfoque=6,
           opacidade=20) -> Image.Image:
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for (x, y, w, h) in retangulos:
        d.rounded_rectangle([e(x), e(y + desloc), e(x + w), e(y + h + desloc)],
                            radius=e(raio), fill=(15, 23, 42, opacidade))
    return Image.alpha_composite(
        base, camada.filter(ImageFilter.GaussianBlur(e(desfoque) / 2)))


def painel(d: ImageDraw.ImageDraw, x, y, w, h, *, cor=g.CARTAO,
           borda=g.BORDA, raio=10) -> None:
    d.rounded_rectangle([e(x), e(y), e(x + w), e(y + h)], radius=e(raio),
                        fill=cor, outline=borda, width=max(1, ESCALA))


def rotulo(d: ImageDraw.ImageDraw, x, y, texto, *, tam=8.5, tinta=None,
           f=F_SEMI, ancora="lm") -> None:
    d.text((e(x), e(y)), texto, font=fonte(f, tam),
           fill=tinta or g.TEXTO_FRACO, anchor=ancora)


def desenha() -> Image.Image:
    img = Image.new("RGBA", (e(g.LARGURA), e(g.ALTURA)), g.FUNDO)

    caixas = [(p["x"], p["y"], p["w"], p["h"]) for p in g.PAINEIS.values()]
    caixas += [(c["x"], c["y"], c["w"], c["h"]) for c in g.CARTOES]
    caixas += [(g.MARGEM, 8, g.LARGURA - 2 * g.MARGEM, g.CAB_H - 8)]
    img = sombra(img, caixas)
    d = ImageDraw.Draw(img)

    # --- cabecalho ------------------------------------------------------
    # A barra de acento e desenhada inteira e depois coberta: sobra uma
    # faixa de 8 px com os cantos esquerdos ja arredondados, sem precisar
    # recortar canto a canto.
    cab_y, cab_h = 8, g.CAB_H - 8
    d.rounded_rectangle([e(g.MARGEM), e(cab_y), e(g.MARGEM + 40),
                         e(cab_y + cab_h)], radius=e(10), fill=g.AZUL)
    d.rounded_rectangle([e(g.MARGEM + 8), e(cab_y),
                         e(g.LARGURA - g.MARGEM), e(cab_y + cab_h)],
                        radius=e(10), fill=g.NAVY)

    d.text((e(44), e(38)), TITULO, font=fonte(F_BOLD, 19), fill=g.BRANCO,
           anchor="lm")
    d.text((e(44), e(62)), SUBTITULO, font=fonte(F_REG, 10),
           fill=g.NAVY_FRACO, anchor="lm")

    rotulo(d, g.SELETOR["x"] - 12, g.SELETOR["y"] + g.SELETOR["h"] / 2,
           ROTULO_PERIODO, tam=9.5, tinta=g.NAVY_FRACO, ancora="rm")

    # --- cartoes do topo ------------------------------------------------
    # Tarja colorida no alto, como no modelo: o cartao inteiro sai na cor
    # e o branco entra 5 px abaixo, deixando so a faixa aparecendo.
    for c in g.CARTOES:
        d.rounded_rectangle([e(c["x"]), e(c["y"]), e(c["x"] + c["w"]),
                             e(c["y"] + c["h"])], radius=e(10), fill=c["cor"])
        d.rounded_rectangle([e(c["x"]), e(c["y"] + 5), e(c["x"] + c["w"]),
                             e(c["y"] + c["h"])], radius=e(10), fill=g.CARTAO,
                            outline=g.BORDA, width=max(1, ESCALA))
        rotulo(d, c["x"] + 16, c["y"] + 22, c["rotulo"].upper(), tam=8.5)

    # --- paineis --------------------------------------------------------
    for p in g.PAINEIS.values():
        painel(d, p["x"], p["y"], p["w"], p["h"])
        d.text((e(p["x"] + 16), e(p["y"] + 21)), p["titulo"],
               font=fonte(F_SEMI, 12), fill=g.TEXTO, anchor="lm")

    # --- bloco de nao essenciais ----------------------------------------
    ne = g.PAINEIS["vNaoEssencial"]
    d.text((e(ne["x"] + 16), e(ne["y"] + 46)), NE_DESCRICAO,
           font=fonte(F_REG, 8.5), fill=g.TEXTO_FRACO, anchor="lm")

    t = g.NE_TARJA
    d.rounded_rectangle([e(t["x"]), e(t["y"]), e(t["x"] + t["w"]),
                         e(t["y"] + t["h"])], radius=e(8),
                        fill=g.DESTAQUE_FUNDO, outline=g.DESTAQUE_BORDA,
                        width=max(1, ESCALA))

    rotulo(d, g.NE_TOTAL["x"], g.NE_TOTAL["y"] - 14, NE_ROT_TOTAL)
    rotulo(d, g.NE_POTENCIAL["x"], g.NE_POTENCIAL["y"] - 14, NE_ROT_POTENCIAL,
           tinta="#92400E")

    n = g.NE_NOTA
    d.rounded_rectangle([e(n["x"]), e(n["y"]), e(n["x"] + n["w"]),
                         e(n["y"] + n["h"])], radius=e(8), fill=g.NOTA_FUNDO,
                        outline=g.NOTA_BORDA, width=max(1, ESCALA))
    rotulo(d, n["x"] + 12, n["y"] + 16, NE_ROT_IMPACTO, tinta="#047857")

    # --- rodape ---------------------------------------------------------
    d.line([e(g.MARGEM), e(g.RODAPE_Y), e(g.LARGURA - g.MARGEM), e(g.RODAPE_Y)],
           fill=g.BORDA, width=max(1, ESCALA))
    meio = g.RODAPE_Y + (g.ALTURA - g.RODAPE_Y) / 2
    d.text((e(g.MARGEM), e(meio)), RODAPE_ESQ, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="lm")
    d.text((e(g.LARGURA - g.MARGEM), e(meio)), RODAPE_DIR, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="rm")

    return img.convert("RGB")


def previa(img: Image.Image) -> Image.Image:
    """Fundo com os retangulos dos visuais por cima, em 1x.

    Serve para ver se o visual cai dentro da moldura sem abrir o Power
    BI — la cada tentativa custa abrir o projeto inteiro.
    """
    tela = img.convert("RGBA").resize((g.LARGURA, g.ALTURA), Image.LANCZOS)
    marca = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(marca)
    f = ImageFont.truetype(F_REG, 10)

    # So os paineis que recebem UM visual. O de nao essenciais e apenas
    # moldura: quem ocupa a area dele sao os seis visuais listados
    # adiante, e desenhar a moldura inteira aqui esconderia justamente o
    # encaixe que esta previa existe para conferir.
    caixas = [(n, g.area_do_visual(g.PAINEIS[n]))
              for n in ("vHistorico", "vTop5")]
    caixas += [(c["nome"], g.area_do_valor(c)) for c in g.CARTOES]
    caixas += [(c["nome"] + "Sub", g.area_do_sub(c)) for c in g.CARTOES]
    caixas += [(n, g.caixa_de(v)) for n, v in (
        ("vNeTotal", g.NE_TOTAL), ("vNeTotalSub", g.NE_TOTAL_SUB),
        ("vNePotencial", g.NE_POTENCIAL),
        ("vNePotencialSub", g.NE_POTENCIAL_SUB),
        ("vNeGrupos", g.NE_GRUPOS), ("vNeImpacto", g.NE_IMPACTO),
        ("vAviso", g.AVISO))]

    for nome, (x, y, w, h) in caixas:
        d.rectangle([x, y, x + w, y + h], fill=(37, 99, 235, 36),
                    outline=(37, 99, 235, 200))
        d.text((x + 4, y + 3), nome, font=f, fill=(12, 42, 110, 255))

    s = g.SELETOR
    d.rectangle([s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"]],
                fill=(139, 92, 246, 40), outline=(139, 92, 246, 200))
    d.text((s["x"] + 4, s["y"] + 3), "fPeriodo", font=f, fill=(60, 20, 140, 255))
    return Image.alpha_composite(tela, marca).convert("RGB")


def main() -> int:
    p = argparse.ArgumentParser(description="Desenha o fundo do painel")
    p.add_argument("--previa", action="store_true",
                   help="grava _previa-financas.png com os retângulos por cima")
    args = p.parse_args()

    img = desenha()
    saida = g.BASE / g.FUNDO_PNG
    img.save(saida, optimize=True)
    print(f"  {saida.name:<28} {img.width}x{img.height} "
          f"({saida.stat().st_size // 1024} KB)")
    if args.previa:
        alvo = g.BASE / "_previa-financas.png"
        previa(img).save(alvo)
        print(f"  {alvo.name:<28} prévia em 1x com os visuais marcados")
    print(f"\nFundo em {ESCALA}x da tela {g.LARGURA}x{g.ALTURA}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
