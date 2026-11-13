"""
Desenha a moldura de cada pagina como uma imagem de fundo.

O Power BI nao desenha canto arredondado decente, sombra nem tipografia
fina. Desenhados aqui, desenham-se uma vez e ficam perfeitos; os visuais
entram por cima, transparentes, cuidando so do dado.

A GRADE VEM DE gerar_painel.PAGINAS. O mesmo retangulo que posiciona o
visual desenha a moldura, entao nao ha como divergirem — que e o unico
jeito de essa tecnica dar errado.

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
F_ICONE = r"C:\Windows\Fonts\segmdl2.ttf"

# Glifos do Segoe MDL2 Assets, conferidos numa folha de contato: o
# codepoint nao se adivinha e o errado vira um quadrado vazio.
ICO_PAGINA = {"mes": "\uE787", "historico": "\uE9D9", "compressivel": "\uE8C7"}
ICO_ALERTA = "\uE814"

RODAPE_ESQ = "Origem: db-manzo · gold.fato_movto_financ"
RODAPE_DIR = "Pagamento de fatura (SINTETICO) fica fora: contaria o cartão duas vezes."


def e(v) -> int:
    return int(round(v * ESCALA))


def fonte(caminho: str, tamanho: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(caminho, e(tamanho))


def sombra(base: Image.Image, retangulos, raio=8, desloc=2, desfoque=6,
           opacidade=24) -> Image.Image:
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for (x, y, w, h) in retangulos:
        d.rounded_rectangle([e(x), e(y + desloc), e(x + w), e(y + h + desloc)],
                            radius=e(raio), fill=(18, 58, 68, opacidade))
    return Image.alpha_composite(
        base, camada.filter(ImageFilter.GaussianBlur(e(desfoque) / 2)))


def painel(d: ImageDraw.ImageDraw, x, y, w, h, *, cor=g.CARTAO, raio=8) -> None:
    d.rounded_rectangle([e(x), e(y), e(x + w), e(y + h)], radius=e(raio),
                        fill=cor, outline=g.BORDA, width=max(1, ESCALA))


def desenha(pag: dict) -> Image.Image:
    img = Image.new("RGBA", (e(g.LARGURA), e(g.ALTURA)), g.FUNDO)

    caixas = [(p["x"], p["y"], p["w"], p["h"]) for p in pag["paineis"].values()]
    caixas += [(c["x"], c["y"], c["w"], c["h"]) for c in pag["cartoes"]]
    img = sombra(img, caixas)
    d = ImageDraw.Draw(img)

    # --- cabecalho ------------------------------------------------------
    d.rectangle([0, 0, e(g.LARGURA), e(g.CAB_H)], fill=g.PETROLEO)
    d.text((e(26), e(g.CAB_H / 2)), ICO_PAGINA.get(pag["nome"], "\uE7C3"),
           font=fonte(F_ICONE, 20), fill=g.TURQUESA, anchor="lm")
    d.text((e(64), e(30)), "Controle de gastos", font=fonte(F_SEMI, 11),
           fill="#7FB3AE", anchor="lm")
    d.text((e(64), e(54)), pag["titulo"], font=fonte(F_BOLD, 19),
           fill=g.BRANCO, anchor="lm")

    larg = d.textlength(pag["titulo"], font=fonte(F_BOLD, 19)) / ESCALA
    d.text((e(64 + larg + 16), e(56)), pag["subtitulo"],
           font=fonte(F_REG, 10), fill="#7FB3AE", anchor="lm")

    d.text((e(g.LARGURA - 26), e(30)), "Meta da fatura", font=fonte(F_REG, 9),
           fill="#7FB3AE", anchor="rm")
    d.text((e(g.LARGURA - 26), e(54)), f"R$ {g.META_PADRAO:,.0f}".replace(",", "."),
           font=fonte(F_BOLD, 17), fill=g.TURQUESA, anchor="rm")

    # --- cartoes --------------------------------------------------------
    for c in pag["cartoes"]:
        painel(d, c["x"], c["y"], c["w"], c["h"])
        d.rounded_rectangle([e(c["x"]), e(c["y"] + 8), e(c["x"] + 4),
                             e(c["y"] + c["h"] - 8)], radius=e(2), fill=c["cor"])
        d.text((e(c["x"] + 16), e(c["y"] + 18)), c["rotulo"].upper(),
               font=fonte(F_SEMI, 8.5), fill=g.TEXTO_FRACO, anchor="lm")

    # --- paineis --------------------------------------------------------
    for chave, p in pag["paineis"].items():
        painel(d, p["x"], p["y"], p["w"], p["h"])
        d.text((e(p["x"] + 16), e(p["y"] + 20)), p["titulo"],
               font=fonte(F_SEMI, 12), fill=g.TEXTO, anchor="lm")

    # --- rodape ---------------------------------------------------------
    d.line([e(g.MARGEM), e(g.RODAPE_Y), e(g.LARGURA - g.MARGEM), e(g.RODAPE_Y)],
           fill=g.BORDA, width=max(1, ESCALA))
    meio = g.RODAPE_Y + (g.ALTURA - g.RODAPE_Y) / 2
    d.text((e(g.MARGEM), e(meio)), RODAPE_ESQ, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="lm")
    d.text((e(g.LARGURA - g.MARGEM), e(meio)), RODAPE_DIR, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="rm")

    return img.convert("RGB")


def previa(pag: dict, img: Image.Image) -> Image.Image:
    """Fundo com os retangulos dos visuais por cima, em 1x.

    Serve para ver se o grafico cai dentro da moldura sem abrir o Power
    BI — la cada tentativa custa abrir o projeto inteiro.
    """
    tela = img.convert("RGBA").resize((g.LARGURA, g.ALTURA), Image.LANCZOS)
    marca = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(marca)
    f = ImageFont.truetype(F_REG, 10)

    caixas = [(n, g.area_do_visual(p)) for n, p in pag["paineis"].items()]
    caixas += [(c["nome"], g.area_do_valor(c)) for c in pag["cartoes"]]
    for nome, (x, y, w, h) in caixas:
        d.rectangle([x, y, x + w, y + h], fill=(31, 168, 154, 38),
                    outline=(31, 168, 154, 200))
        d.text((x + 4, y + 3), nome, font=f, fill=(0, 82, 74, 255))

    if pag["nome"] != "mes":
        for x, larg in g.FILTROS_X:
            d.rectangle([x, g.FILTRO_Y, x + larg, g.FILTRO_Y + g.FILTRO_H],
                        fill=(107, 91, 168, 38), outline=(107, 91, 168, 200))
    return Image.alpha_composite(tela, marca).convert("RGB")


def main() -> int:
    p = argparse.ArgumentParser(description="Desenha os fundos do painel")
    p.add_argument("--previa", action="store_true",
                   help="grava _previa-<pagina>.png com os retangulos por cima")
    args = p.parse_args()

    for pag in g.PAGINAS:
        img = desenha(pag)
        saida = g.BASE / g.fundo_da(pag["nome"])
        img.save(saida, optimize=True)
        print(f"  {saida.name:<28} {img.width}x{img.height} "
              f"({saida.stat().st_size // 1024} KB)")
        if args.previa:
            previa(pag, img).save(g.BASE / f"_previa-{pag['nome']}.png")
    print(f"\n{len(g.PAGINAS)} fundos em {ESCALA}x da tela "
          f"{g.LARGURA}x{g.ALTURA}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
