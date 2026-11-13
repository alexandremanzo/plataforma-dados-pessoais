"""
Gera docs/glossario.md a partir das descricoes gravadas no banco.

O glossario nao e escrito a mao: e uma projecao de
gold.vw_glossario_dados, que por sua vez le as extended properties das
tabelas. Assim a documentacao publicada nunca diverge da que esta no
banco - se uma coluna nova entrar sem descricao, ela aparece aqui
marcada como pendente.

Rode depois de qualquer mudanca de DDL:
    python exporta_glossario.py
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PROJECT_ROOT, get_engine  # noqa: E402

DESTINO = PROJECT_ROOT / "docs" / "glossario.md"

DESCRICAO_CAMADA = {
    "bronze": "Cópia fiel da origem, sem conversão de tipo. Cada evento "
              "uma única vez, com linhagem do arquivo de onde veio.",
    "silver": "Dados tipados, classificados e com vocabulário "
              "padronizado. Uma tabela por entidade de negócio.",
    "gold":   "Modelo dimensional pronto para consumo. É a única camada "
              "que o Power BI consulta.",
}
ORDEM = {"bronze": 1, "silver": 2, "gold": 3}


def main() -> int:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT NM_CAMADA, NM_TABELA, NM_OBJETO, NR_ORDEM, NM_COLUNA,
               DS_TIPO_DADO, FL_OBRIGATORIO, FL_CHAVE_PRIMARIA, DS_PAPEL,
               DS_DESCRICAO_COLUNA, DS_DESCRICAO_TABELA, DS_STATUS_DOC
        FROM gold.vw_glossario_dados
        ORDER BY NM_CAMADA, NM_TABELA, NR_ORDEM
    """, engine)

    linhas = [
        "# Glossário de dados",
        "",
        "> Gerado automaticamente a partir das descrições gravadas no",
        "> próprio banco, via `gold.vw_glossario_dados`. Não edite este",
        "> arquivo: altere a descrição no script de DDL correspondente e",
        "> rode `python scripts/etl/exporta_glossario.py`.",
        "",
        f"Atualizado em {date.today():%d/%m/%Y} — "
        f"{df['NM_OBJETO'].nunique()} tabelas, {len(df)} colunas, "
        f"{(df['DS_STATUS_DOC'] == 'Documentada').sum()} documentadas.",
        "",
    ]

    # Índice
    linhas.append("## Índice")
    linhas.append("")
    for camada in sorted(df["NM_CAMADA"].unique(), key=lambda c: ORDEM.get(c, 9)):
        tabelas = df[df["NM_CAMADA"] == camada]["NM_OBJETO"].unique()
        alvos = " · ".join(
            f"[{t}](#{t.replace('.', '')})" for t in sorted(tabelas))
        linhas.append(f"- **{camada}** — {alvos}")
    linhas.append("")

    for camada in sorted(df["NM_CAMADA"].unique(), key=lambda c: ORDEM.get(c, 9)):
        linhas.append(f"## {camada}")
        linhas.append("")
        linhas.append(DESCRICAO_CAMADA.get(camada, ""))
        linhas.append("")

        for objeto in sorted(df[df["NM_CAMADA"] == camada]["NM_OBJETO"].unique()):
            tabela = df[df["NM_OBJETO"] == objeto]
            linhas.append(f"### {objeto}")
            linhas.append("")

            descricao = tabela["DS_DESCRICAO_TABELA"].iloc[0]
            if pd.notna(descricao):
                linhas.append(str(descricao))
                linhas.append("")

            linhas.append("| Coluna | Tipo | Obrig. | Papel | Descrição |")
            linhas.append("| --- | --- | :---: | --- | --- |")
            for _, c in tabela.iterrows():
                nome = f"**{c.NM_COLUNA}**" if c.FL_CHAVE_PRIMARIA == "Sim" else c.NM_COLUNA
                texto = (str(c.DS_DESCRICAO_COLUNA).replace("|", "\\|")
                         if pd.notna(c.DS_DESCRICAO_COLUNA) else "_pendente_")
                linhas.append(
                    f"| {nome} | `{c.DS_TIPO_DADO}` | {c.FL_OBRIGATORIO} | "
                    f"{c.DS_PAPEL} | {texto} |"
                )
            linhas.append("")

    linhas.append("---")
    linhas.append("")
    linhas.append("Colunas em **negrito** compõem a chave primária.")
    linhas.append("")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text("\n".join(linhas), encoding="utf-8")

    pendentes = (df["DS_STATUS_DOC"] != "Documentada").sum()
    print(f"Gerado: {DESTINO}")
    print(f"  tabelas : {df['NM_OBJETO'].nunique()}")
    print(f"  colunas : {len(df)}")
    print(f"  pendentes de descricao: {pendentes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
