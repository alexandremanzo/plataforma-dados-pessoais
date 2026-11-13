"""
Escreve, em docs/modelo-dados.md, a consulta de cada fato com as suas
dimensoes.

POR QUE GERADO, E NAO ESCRITO A MAO. A consulta so vale enquanto
listar TODAS as dimensoes do fato. Escrita uma vez, ela envelhece na
primeira chave nova - e envelhece em silencio, porque continua rodando
e devolvendo numero. Foi o que aconteceu duas vezes neste projeto em
uma semana: a limpeza de orfaos do carga_gold_xp.py conhecia um fato
so, e o fato_posicao_investimento nasceu sem entrar no modelo-dados.

AS LIGACOES SAEM DE sys.foreign_keys, que e o unico lugar onde elas
nao podem estar desatualizadas - e o proprio banco que as impoe.

O ARQUIVO E EDITADO, NAO REESCRITO. O modelo-dados.md e quase todo
prosa escrita a mao, e um gerador que o reescrevesse apagaria o que
tem mais valor nele. Este script troca apenas o conteudo entre
marcadores:

    <!-- consulta:fato_movto_financ -->
    ...aqui...
    <!-- /consulta -->

Uso:
    python exporta_consultas_modelo.py
    python exporta_consultas_modelo.py --conferir   # so valida, nao grava
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))

from config_db import PROJECT_ROOT, get_engine        # noqa: E402

DESTINO = PROJECT_ROOT / "docs" / "modelo-dados.md"

# Colunas que nao dizem nada a quem le o resultado.
RUIDO = {"DT_CARGA", "HASH_NEGOCIO"}

# Quantas colunas descritivas trazer de cada dimensao. Duas porque uma
# costuma ser o rotulo e a outra o que o qualifica (NM_MES e NR_ANO,
# NM_GRUPO e DS_CLASSE). Mais do que isso e uma consulta que ninguem le.
COLS_POR_DIM = 2

# DT_ entra porque em dim_calendario a coluna que interessa e DT_DATA,
# e sem ela a consulta devolvia NM_MES e NM_MES_ABREV - o mes por
# extenso duas vezes, e a data em lugar nenhum. DT_CARGA ja sai por
# RUIDO, entao incluir o prefixo nao traz linhagem para o resultado.
PREFIXO_DESCRITIVO = ("DT_", "NM_", "DS_", "SG_", "CD_")


def ligacoes(engine) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT OBJECT_NAME(fk.parent_object_id)  AS fato,
               COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS coluna,
               OBJECT_NAME(fk.referenced_object_id) AS dim,
               COL_NAME(fkc.referenced_object_id,
                        fkc.referenced_column_id)   AS dim_col
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc
          ON fkc.constraint_object_id = fk.object_id
        WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = 'gold'
          AND OBJECT_NAME(fk.parent_object_id) LIKE 'fato%'
        ORDER BY fato, coluna
    """, engine)


def colunas(engine, tabela: str) -> list[str]:
    return list(pd.read_sql(f"""
        SELECT COLUMN_NAME c FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='gold' AND TABLE_NAME='{tabela}'
        ORDER BY ORDINAL_POSITION""", engine).c)


def apelido(coluna_fk: str) -> str:
    """SK_DATA_FATURA -> data_fatura.

    Derivado da COLUNA e nao da dimensao porque um fato pode apontar
    duas vezes para a mesma: fato_movto_financ liga dim_calendario por
    SK_DATA e por SK_DATA_FATURA. Apelidando pela dimensao, as duas
    colidiriam e a consulta nem compilaria.
    """
    return re.sub(r"^SK_", "", coluna_fk).lower()


def monta(engine, fato: str, refs: pd.DataFrame) -> str:
    cols_fato = colunas(engine, fato)
    sks = set(refs.coluna)
    medidas = [c for c in cols_fato
               if c not in sks and c not in RUIDO and not c.startswith("SK_")]

    linhas = [f"    f.{c}" for c in medidas]
    joins = []
    for r in refs.itertuples():
        ap = apelido(r.coluna)
        desc = [c for c in colunas(engine, r.dim)
                if c.startswith(PREFIXO_DESCRITIVO) and c not in RUIDO]
        for c in desc[:COLS_POR_DIM]:
            # Alinha pelo que o leitor ve - "apelido.COLUNA" inteiro -,
            # e nao so pela coluna: com apelidos de tamanhos diferentes,
            # alinhar pela coluna desalinha a lista toda.
            linhas.append(f"    {ap + '.' + c:<34} AS {ap}_{c.lower()}")
        # LEFT JOIN mesmo com a chave sendo NOT NULL e tendo membro -1.
        # Custa nada aqui e garante que a consulta nunca ESCONDA linha
        # do fato - que e o oposto do que se quer de uma consulta de
        # exploracao do modelo.
        joins.append(f"LEFT JOIN gold.{r.dim} {ap}\n"
                     f"       ON {ap}.{r.dim_col} = f.{r.coluna}")

    return ("SELECT\n" + ",\n".join(linhas)
            + f"\nFROM gold.{fato} f\n" + "\n".join(joins) + ";")


def confere(engine, sql: str) -> str | None:
    """Roda a consulta com TOP 0: valida sem trazer dado."""
    try:
        pd.read_sql(sql.replace("SELECT\n", "SELECT TOP 0\n", 1)
                       .rstrip(";"), engine)
        return None
    except Exception as e:                               # noqa: BLE001
        return str(e)[:160]


def aplica(texto: str, fato: str, bloco: str) -> tuple[str, bool]:
    """Troca o conteudo entre os marcadores deste fato.

    O PONTO TEMPERADO NAO E FRESCURA. A versao ingenua deste padrao
    era "(abre\\n).*?(\\n fecha)", e ela APAGOU TRES SECOES do
    documento numa unica execucao. Num bloco VAZIO - que e o estado
    de todo marcador recem-inserido - a quebra de linha logo apos o
    marcador de abertura ja foi consumida, entao o ".*?" nao encontra
    o fechamento imediato e se estende ate o fechamento do bloco
    SEGUINTE, levando junto tudo o que houver entre os dois.

    "(?:(?!<!-- consulta:).)*?" nao consegue atravessar outro marcador
    de abertura: no pior caso a substituicao falha, e falhar e
    infinitamente melhor do que apagar prosa escrita a mao.
    """
    abre = f"<!-- consulta:{fato} -->"
    fecha = "<!-- /consulta -->"
    padrao = re.compile(
        re.escape(abre) + r"(?:(?!<!-- consulta:).)*?" + re.escape(fecha),
        re.S)
    if not padrao.search(texto):
        return texto, False
    # Lambda na substituicao: o SQL gerado tem barras e grupos que o
    # re interpretaria como referencia de captura.
    return padrao.sub(lambda _: f"{abre}\n{bloco}\n{fecha}", texto, count=1), True


def main() -> int:
    p = argparse.ArgumentParser(description="Consultas do modelo no markdown")
    p.add_argument("--conferir", action="store_true",
                   help="valida as consultas sem gravar o arquivo")
    args = p.parse_args()

    engine = get_engine()
    refs = ligacoes(engine)
    texto = DESTINO.read_text(encoding="utf-8")

    aplicados, faltando, quebrados = 0, [], 0
    for fato, g in refs.groupby("fato"):
        sql = monta(engine, fato, g)
        erro = confere(engine, sql)
        if erro:
            print(f"  QUEBRADA  {fato}: {erro}")
            quebrados += 1
            continue
        bloco = f"```sql\n{sql}\n```"
        texto, achou = aplica(texto, fato, bloco)
        if achou:
            aplicados += 1
            print(f"  ok  {fato:<28} {len(g)} dimensões")
        else:
            faltando.append(fato)

    if faltando:
        print(f"\n  sem marcador no documento ({len(faltando)}):")
        for f in faltando:
            print(f"     <!-- consulta:{f} -->  ...  <!-- /consulta -->")

    if quebrados:
        print(f"\n{quebrados} consulta(s) não compilaram. Nada foi gravado.")
        return 1

    if not args.conferir:
        DESTINO.write_text(texto, encoding="utf-8")
        print(f"\n{aplicados} consulta(s) escritas em {DESTINO.name}.")
    else:
        print(f"\n{aplicados} consulta(s) válidas. Nada gravado (--conferir).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
