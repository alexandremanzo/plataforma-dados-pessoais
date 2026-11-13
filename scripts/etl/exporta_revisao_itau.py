"""
Gera a planilha de revisao de categorias da conta Itau.

Agrupa os lancamentos sem classificacao por PADRAO de operacao - a
descricao sem numeros, datas e pontuacao - de forma que rotular uma
linha resolva dezenas de lancamentos de uma vez.

Traz uma coluna de sugestao com a categoria que VOCE ja usou para
aquele mesmo padrao em outros lancamentos, junto do percentual de
concordancia. A sugestao e informativa: nada e aplicado ate que as
colunas AREA / CATEGORIA / GRUPO sejam preenchidas a mao.

Por que por padrao e nao por descricao: as descricoes do Itau embutem
data e nome parcial do estabelecimento, o que as torna quase unicas.
Rotular uma a uma seriam 1.800 decisoes; por padrao sao algumas dezenas.

Depois de preencher, rode carga_de_para_itau.py.

Uso:
    python exporta_revisao_itau.py
"""

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402
from regras_itau import extrai_padrao  # noqa: E402

ARQUIVO = "revisao-categorias-itau.xlsx"
ABA = "padroes"

COLUNAS = [
    "PADRAO", "OCORRENCIAS", "VOLUME_ABS", "VALOR_LIQUIDO",
    "PRIMEIRA", "ULTIMA", "EXEMPLOS",
    "SUGESTAO_AREA", "SUGESTAO_CATEGORIA", "SUGESTAO_GRUPO", "CONCORDANCIA_PCT",
    "AREA", "CATEGORIA", "GRUPO",
]


def main() -> int:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT ds_descricao, ds_area, ds_categoria, ds_grupo,
               vl_transacao, dt_lancamento, fl_classificado
        FROM silver.itau_movimentacao WHERE fl_saldo = 0
    """, engine)
    df["padrao"] = df["ds_descricao"].map(extrai_padrao)

    pendentes = df[~df["fl_classificado"]]
    classificados = df[df["fl_classificado"]]

    # Para cada padrao ja classificado, guarda a combinacao mais usada
    # e o quanto ela domina - e a "sugestao" mostrada ao lado.
    referencia = {}
    for pad, g in classificados.groupby("padrao"):
        combo = g.groupby(["ds_area", "ds_categoria", "ds_grupo"]).size()
        (area, cat, grupo), n = combo.sort_values(ascending=False).items().__next__()
        referencia[pad] = (area, cat, grupo, round(100 * n / len(g), 1))

    linhas = []
    for pad, g in pendentes.groupby("padrao"):
        area, cat, grupo, pct = referencia.get(pad, ("", "", "", None))
        exemplos = " ;; ".join(g["ds_descricao"].dropna().unique()[:3])
        linhas.append({
            "PADRAO": pad,
            "OCORRENCIAS": len(g),
            "VOLUME_ABS": round(g["vl_transacao"].abs().sum(), 2),
            "VALOR_LIQUIDO": round(g["vl_transacao"].sum(), 2),
            "PRIMEIRA": g["dt_lancamento"].min(),
            "ULTIMA": g["dt_lancamento"].max(),
            "EXEMPLOS": exemplos[:250],
            "SUGESTAO_AREA": area,
            "SUGESTAO_CATEGORIA": cat,
            "SUGESTAO_GRUPO": grupo,
            "CONCORDANCIA_PCT": pct,
            "AREA": None, "CATEGORIA": None, "GRUPO": None,
        })

    saida = pd.DataFrame(linhas, columns=COLUNAS).sort_values(
        "VOLUME_ABS", ascending=False)

    destino = PATH_DADOS_ORIGEM / ARQUIVO
    temporario = destino.with_suffix(".tmp.xlsx")
    with pd.ExcelWriter(temporario, engine="openpyxl",
                        datetime_format="YYYY-MM-DD") as w:
        saida.to_excel(w, sheet_name=ABA, index=False)
        ws = w.sheets[ABA]
        larguras = {"A": 34, "B": 13, "C": 14, "D": 14, "E": 12, "F": 12,
                    "G": 46, "H": 20, "I": 20, "J": 22, "K": 17,
                    "L": 20, "M": 20, "N": 22}
        for col, larg in larguras.items():
            ws.column_dimensions[col].width = larg
        ws.freeze_panes = "A2"
    os.replace(temporario, destino)

    com_sug = saida["CONCORDANCIA_PCT"].notna().sum()
    print(f"Arquivo gerado: {destino}")
    print(f"  padroes a revisar : {len(saida)}")
    print(f"  com sugestao      : {com_sug}")
    print(f"  sem referencia    : {len(saida) - com_sug}")
    print(f"  volume total      : R$ {saida['VOLUME_ABS'].sum():,.2f}")
    print()
    print("  Preencha as colunas AREA, CATEGORIA e GRUPO (as tres ultimas).")
    print("  As colunas SUGESTAO_* sao apenas referencia do seu proprio")
    print("  historico - copie se concordar, ou escreva outra coisa.")
    print()
    print("  Os 12 padroes de maior volume:")
    print(saida.head(12)[["PADRAO", "OCORRENCIAS", "VOLUME_ABS",
                          "SUGESTAO_CATEGORIA", "CONCORDANCIA_PCT"]]
          .to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
