"""
Desenha a moldura da página como imagem de fundo.

O Power BI não desenha canto arredondado decente, sombra, tarja
colorida nem tipografia fina. Desenhados aqui, desenham-se uma vez e
ficam perfeitos; os visuais entram por cima, transparentes, cuidando só
do dado.

A GRADE VEM DE gerar_painel. O mesmo retângulo que posiciona o visual
desenha a moldura, então não há como divergirem — que é o único jeito
de essa técnica dar errado.

Uso:
    python gerar_fundo.py
    python gerar_fundo.py --previa
"""

from __future__ import annotations

import argparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import gerar_painel as g

ESCALA = 2

F_REG = r"C:\Windows\Fonts\segoeui.ttf"
F_SEMI = r"C:\Windows\Fonts\seguisb.ttf"
F_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"

TITULO = "DASHBOARD DE FINANÇAS GERAL"
SUBTITULO = ("Consolidado de receitas, despesas, meios de pagamento e "
             "oportunidades de economia")
ROT_PERIODO = "Período:"

CT_ROT_E = "CARTÃO DE CRÉDITO"
CT_ROT_D = "OUTROS GASTOS (CONTA CORRENTE / DÉBITO)"
CT_DESC_E = "Faturas recorrentes, compras parceladas e serviços online."
CT_DESC_D = "Pagamentos à vista, Pix, débito e saques em dinheiro."

DQ_TARJA_ROT = "Oportunidades em despesas não essenciais"
CAL_LEGENDA = ("Picos (> R$ 1.000)", "Feriado", "Fim de semana", "Diário comum")
CAL_CORES = ("#FEE2E2", "#EDE9FE", "#FEF3C7", "#FFFFFF")

RODAPE_ESQ = "Origem: db-manzo · gold.fato_movto_financ (nível ANALITICO)"
RODAPE_DIR = ("Aporte, resgate e transferência ficam fora: não são receita "
              "nem gasto.")


def e(v) -> int:
    return int(round(v * ESCALA))


def fonte(caminho: str, tamanho: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(caminho, e(tamanho))


def sombra(base, retangulos, raio=10, desloc=2, desfoque=6, opacidade=20):
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for (x, y, w, h) in retangulos:
        d.rounded_rectangle([e(x), e(y + desloc), e(x + w), e(y + h + desloc)],
                            radius=e(raio), fill=(15, 23, 42, opacidade))
    return Image.alpha_composite(
        base, camada.filter(ImageFilter.GaussianBlur(e(desfoque) / 2)))


def painel(d, x, y, w, h, *, cor=g.CARTAO, borda=g.BORDA, raio=10) -> None:
    d.rounded_rectangle([e(x), e(y), e(x + w), e(y + h)], radius=e(raio),
                        fill=cor, outline=borda, width=max(1, ESCALA))


def rot(d, x, y, texto, *, tam=8.5, tinta=None, f=F_SEMI, ancora="lm") -> None:
    d.text((e(x), e(y)), texto, font=fonte(f, tam),
           fill=tinta or g.TEXTO_FRACO, anchor=ancora)


def desenha() -> Image.Image:
    img = Image.new("RGBA", (e(g.LARGURA), e(g.ALTURA)), g.FUNDO)

    caixas = [(p["x"], p["y"], p["w"], p["h"]) for p in g.PAINEIS.values()]
    caixas += [(c["x"], c["y"], c["w"], c["h"]) for c in g.CARTOES]
    caixas += [(g.MARGEM, g.CAB_Y, g.LARGURA - 2 * g.MARGEM, g.CAB_H)]
    img = sombra(img, caixas)
    d = ImageDraw.Draw(img)

    # --- cabeçalho ------------------------------------------------------
    # A barra de acento é desenhada inteira e depois coberta: sobra uma
    # faixa de 8 px com os cantos esquerdos já arredondados.
    d.rounded_rectangle([e(g.MARGEM), e(g.CAB_Y), e(g.MARGEM + 40),
                         e(g.CAB_Y + g.CAB_H)], radius=e(10), fill=g.AZUL)
    d.rounded_rectangle([e(g.MARGEM + 8), e(g.CAB_Y),
                         e(g.LARGURA - g.MARGEM), e(g.CAB_Y + g.CAB_H)],
                        radius=e(10), fill=g.NAVY)
    d.text((e(44), e(40)), TITULO, font=fonte(F_BOLD, 19), fill=g.BRANCO,
           anchor="lm")
    d.text((e(44), e(64)), SUBTITULO, font=fonte(F_REG, 9.5),
           fill=g.NAVY_FRACO, anchor="lm")
    rot(d, g.SELETOR["x"] - 12, g.SELETOR["y"] + g.SELETOR["h"] / 2,
        ROT_PERIODO, tam=10.0, tinta=g.NAVY_FRACO, ancora="rm")

    # --- cartões do topo ------------------------------------------------
    for c in g.CARTOES:
        d.rounded_rectangle([e(c["x"]), e(c["y"]), e(c["x"] + c["w"]),
                             e(c["y"] + c["h"])], radius=e(10), fill=c["cor"])
        d.rounded_rectangle([e(c["x"]), e(c["y"] + 5), e(c["x"] + c["w"]),
                             e(c["y"] + c["h"])], radius=e(10), fill=g.CARTAO,
                            outline=g.BORDA, width=max(1, ESCALA))
        rot(d, c["x"] + 16, c["y"] + 22, c["rotulo"].upper(), tam=8.5)

    # --- painéis --------------------------------------------------------
    for p in g.PAINEIS.values():
        painel(d, p["x"], p["y"], p["w"], p["h"])
        d.text((e(p["x"] + 16), e(p["y"] + 21)), p["titulo"],
               font=fonte(F_SEMI, 12), fill=g.TEXTO, anchor="lm")
        if p.get("selo"):
            rot(d, p["x"] + p["w"] - 16, p["y"] + 21, p["selo"], tam=9.0,
                ancora="rm")

    # --- cartão de crédito x outros -------------------------------------
    for bloco, tinta, fundo, rotulo, desc in (
            (g.CT_BLOCO_E, g.AZUL, g.BLOCO_CARTAO, CT_ROT_E, CT_DESC_E),
            (g.CT_BLOCO_D, g.CIANO, g.BLOCO_OUTROS, CT_ROT_D, CT_DESC_D)):
        d.rounded_rectangle([e(bloco["x"]), e(bloco["y"]),
                             e(bloco["x"] + bloco["w"]),
                             e(bloco["y"] + bloco["h"])],
                            radius=e(8), fill=fundo, outline=g.BORDA,
                            width=max(1, ESCALA))
        # Risco de acento à esquerda, como no esboço.
        d.rounded_rectangle([e(bloco["x"]), e(bloco["y"] + 8),
                             e(bloco["x"] + 4), e(bloco["y"] + bloco["h"] - 8)],
                            radius=e(2), fill=tinta)
        rot(d, bloco["x"] + 18, bloco["y"] + 20, rotulo, tam=9.0, tinta=tinta)
        rot(d, bloco["x"] + 18, bloco["y"] + bloco["h"] - 16, desc, tam=8.5,
            f=F_REG)

    # --- legenda do calendário ------------------------------------------
    cal = g.PAINEIS["vCalendario"]
    x = cal["x"] + 16
    y = cal["y"] + cal["h"] - 14
    for rotulo, tinta in zip(CAL_LEGENDA, CAL_CORES):
        d.rounded_rectangle([e(x), e(y - 4), e(x + 9), e(y + 5)], radius=e(2),
                            fill=tinta, outline=g.BORDA, width=1)
        d.text((e(x + 14), e(y)), rotulo, font=fonte(F_REG, 8.0),
               fill=g.TEXTO_FRACO, anchor="lm")
        x += 14 + d.textlength(rotulo, font=fonte(F_REG, 8.0)) / ESCALA + 16

    # --- tarja das oportunidades ------------------------------------------
    t = g.DQ_TARJA
    d.rounded_rectangle([e(t["x"]), e(t["y"]), e(t["x"] + t["w"]),
                         e(t["y"] + t["h"])], radius=e(8), fill=g.TARJA_FUNDO,
                        outline=g.TARJA_BORDA, width=max(1, ESCALA))
    rot(d, t["x"] + 16, t["y"] + 22, DQ_TARJA_ROT.upper(), tam=9.0,
        tinta=g.TARJA_TEXTO)

    # --- rodapé -----------------------------------------------------------
    d.line([e(g.MARGEM), e(g.RODAPE_Y), e(g.LARGURA - g.MARGEM), e(g.RODAPE_Y)],
           fill=g.BORDA, width=max(1, ESCALA))
    meio = g.RODAPE_Y + (g.ALTURA - g.RODAPE_Y) / 2
    d.text((e(g.MARGEM), e(meio)), RODAPE_ESQ, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="lm")
    d.text((e(g.LARGURA - g.MARGEM), e(meio)), RODAPE_DIR, font=fonte(F_REG, 9),
           fill=g.TEXTO_FRACO, anchor="rm")
    return img.convert("RGB")


def previa(img: Image.Image) -> Image.Image:
    """Fundo com os retângulos dos visuais por cima, em 1x."""
    tela = img.convert("RGBA").resize((g.LARGURA, g.ALTURA), Image.LANCZOS)
    marca = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(marca)
    f = ImageFont.truetype(F_REG, 10)

    caixas = [(n, g.area_do_visual(g.PAINEIS[n])) for n in
              ("vComposicao", "vIndicadores", "vCategoria")]
    caixas += [(c["nome"], g.area_do_valor(c)) for c in g.CARTOES]
    caixas += [(c["nome"] + "Sub", g.area_do_sub(c)) for c in g.CARTOES]
    caixas += [(n, g.cx(v)) for n, v in (
        ("fPeriodo", g.SELETOR), ("vTotalDespesa", g.CT_TOTAL),
        ("vCartaoVal", g.CT_VAL_E), ("vCartaoPct", g.CT_PCT_E),
        ("vForaVal", g.CT_VAL_D), ("vForaPct", g.CT_PCT_D),
        ("vMediaDia", g.CAL_MEDIA), ("vCalendario", g.CAL_MATRIZ),
        ("vMeta", g.DQ_META), ("vEconomia", g.DQ_ECONOMIA),
        ("vOportunidades", g.DQ_TABELA))]

    for nome, (x, y, w, h) in caixas:
        d.rectangle([x, y, x + w, y + h], fill=(37, 99, 235, 36),
                    outline=(37, 99, 235, 200))
        d.text((x + 4, y + 3), nome, font=f, fill=(12, 42, 110, 255))
    return Image.alpha_composite(tela, marca).convert("RGB")


def main() -> int:
    p = argparse.ArgumentParser(description="Desenha o fundo do painel")
    p.add_argument("--previa", action="store_true")
    args = p.parse_args()

    img = desenha()
    saida = g.BASE / g.FUNDO_PNG
    img.save(saida, optimize=True)
    print(f"  {saida.name:<30} {img.width}x{img.height} "
          f"({saida.stat().st_size // 1024} KB)")
    if args.previa:
        alvo = g.BASE / "_previa-financas-geral.png"
        previa(img).save(alvo)
        print(f"  {alvo.name:<30} prévia em 1x com os visuais marcados")
    print(f"\nFundo em {ESCALA}x da tela {g.LARGURA}x{g.ALTURA}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
