"""
Exporta silver.xp_movimentacao para o arquivo lido pelo Power BI.

Gera dados-xp-consolidado.xlsx com exatamente as mesmas colunas, na
mesma ordem e com os mesmos nomes da aba "movto" da planilha mestre -
incluindo a grafia "Açao". A aba de destino tambem se chama "movto".

Isso e proposital: assim a troca no Power BI e so o caminho do
arquivo. Nenhuma etapa do Power Query precisa ser reescrita, porque
tudo que ele referencia por nome continua existindo.

A planilha mestre dados-xp.xlsx NAO e tocada. Ela tem 2 tabelas
dinamicas, 2 graficos e formulas que openpyxl destruiria ao salvar;
alem disso, manter a origem original intacta permite comparar o
resultado novo com o antigo a qualquer momento.

O arquivo e escrito primeiro com extensao .tmp e so depois renomeado.
Sem isso, uma atualizacao do Power BI que caisse no meio da escrita
leria um arquivo pela metade.

Uso:
    python exporta_consolidado_xp.py
    python exporta_consolidado_xp.py --destino "D:\\outro\\caminho.xlsx"
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402

ARQUIVO_PADRAO = "dados-xp-consolidado.xlsx"
ABA = "movto"

# A ordem e a grafia reproduzem a aba movto da planilha mestre.
# "Açao" esta assim de proposito: e o nome que o Power BI espera.
COLUNAS_SAIDA = [
    "Movimentação", "Liquidação", "Lançamento", "Valor (R$)", "Saldo (R$)",
    "Categoria", "Rendimento", "Açao", "fator", "Tipo Movimentação",
]

CONSULTA = """
    SELECT dt_movimentacao, dt_liquidacao, ds_lancamento,
           vl_transacao, vl_saldo, ds_categoria,
           fl_rendimento, ds_ativo, ds_tipo_movimentacao
    FROM silver.xp_movimentacao
    ORDER BY dt_movimentacao, dt_liquidacao, sk_movimentacao
"""


def monta_planilha(engine) -> pd.DataFrame:
    """Le a silver e devolve o DataFrame no formato da planilha mestre."""
    df = pd.read_sql(CONSULTA, engine)

    saida = pd.DataFrame({
        "Movimentação": pd.to_datetime(df["dt_movimentacao"]),
        "Liquidação": pd.to_datetime(df["dt_liquidacao"]),
        "Lançamento": df["ds_lancamento"],
        "Valor (R$)": df["vl_transacao"],
        "Saldo (R$)": df["vl_saldo"],
        "Categoria": df["ds_categoria"],
        # A planilha usa "S" para rendimento e celula vazia para o resto.
        "Rendimento": df["fl_rendimento"].map(lambda v: "S" if v else None),
        "Açao": df["ds_ativo"],
        # Colunas que na planilha eram formula; aqui ja saem calculadas.
        "fator": df["vl_transacao"].map(
            lambda v: None if pd.isna(v) else ("POSITIVO" if v > 0 else "NEGATIVO")
        ),
        "Tipo Movimentação": df["ds_tipo_movimentacao"],
    })
    return saida[COLUNAS_SAIDA]


def escreve(df: pd.DataFrame, destino: Path) -> None:
    """Grava o xlsx de forma atomica."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp.xlsx")

    with pd.ExcelWriter(temporario, engine="openpyxl", datetime_format="YYYY-MM-DD") as w:
        df.to_excel(w, sheet_name=ABA, index=False)

    os.replace(temporario, destino)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta a silver para o Power BI")
    parser.add_argument("--destino", type=Path,
                        default=PATH_DADOS_ORIGEM / ARQUIVO_PADRAO)
    args = parser.parse_args()

    df = monta_planilha(get_engine())
    escreve(df, args.destino)

    print(f"Arquivo gerado: {args.destino}")
    print(f"  aba          : {ABA}")
    print(f"  linhas       : {len(df)}")
    print(f"  periodo      : {df['Movimentação'].min():%d/%m/%Y} a "
          f"{df['Movimentação'].max():%d/%m/%Y}")
    print(f"  colunas      : {len(df.columns)}")

    print("\n  Conferencia rapida:")
    receitas = df.loc[df["Valor (R$)"] > 0, "Valor (R$)"].sum()
    despesas = df.loc[df["Valor (R$)"] < 0, "Valor (R$)"].sum()
    rendimentos = df.loc[df["Rendimento"] == "S", "Valor (R$)"].sum()
    print(f"    entradas   : R$ {receitas:>12,.2f}")
    print(f"    saidas     : R$ {despesas:>12,.2f}")
    print(f"    rendimentos: R$ {rendimentos:>12,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
