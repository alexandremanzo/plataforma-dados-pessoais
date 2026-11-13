"""
Carga da camada Bronze - exames InBody lidos por OCR.

Le a pasta de exames e grava UMA LINHA POR CAMPO em
bronze.avaliacao_inbody.

O grao fino existe para um campo ilegivel nao custar o exame inteiro:
relendo com o recorte ajustado, troca-se aquele campo e os outros
quarenta ficam intactos. E permite auditar de qual arquivo e de qual
regiao cada numero veio.

NAO SUBSTITUI A PLANILHA. As duas origens se completam na gold: o
arquivo entra na frente onde existe, a planilha preenche a lacuna, e
so ela tem as 17 metricas de ate 2013 que o InBody nem mede.

LE SO O QUE AINDA NAO LEU. A imagem de um exame nunca muda, entao
reler nao traz informacao nova - so gasta quinze segundos por exame e,
com versoes diferentes de Tesseract no host e no container, faz a
tabela oscilar entre duas leituras sem nunca convergir.

Uso:
    python carga_bronze_inbody.py
    python carga_bronze_inbody.py --arquivo "2026-08- Bioimpedancia.jpg"
    python carga_bronze_inbody.py --reprocessar   # depois de mudar o extrator
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_EXAMES, get_engine  # noqa: E402
from regras_inbody import ExameIlegivel, le_exame  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

SCHEMA, TABELA = "bronze", "avaliacao_inbody"
ATUALIZAVEIS = ["ds_template", "ds_data_exame", "ds_valor"]


def le_pasta(pasta: Path, filtro: str = None,
             ja_lidos: set = frozenset()) -> tuple[pd.DataFrame, list, list]:
    """
    Le os exames da pasta e devolve as linhas de campo.

    PULA O QUE JA FOI LIDO, e essa e a decisao central desta carga. A
    imagem de um exame NUNCA MUDA: reler o mesmo arquivo nao pode
    trazer informacao nova, so custar tempo - sao cerca de quinze
    segundos por exame, cinco minutos por rodada da DAG.

    E pior que inutil, e ativamente nocivo: o Tesseract do host esta na
    versao 5.4 e o do container na 5.3, e as duas leem alguns campos de
    forma diferente. Relendo a cada rodada, cada execucao desfazia a
    anterior e a tabela nunca convergia - o mesmo defeito que a silver
    do XP teve com duas versoes de pandas.

    Para reler tudo depois de melhorar o extrator: --reprocessar.

    Devolve tambem o que nao pode ser lido e o que foi lido com
    conferencia falhando - as duas listas vao para o terminal, porque
    exame perdido em silencio e o pior desfecho possivel aqui.
    """
    linhas, ilegiveis, com_problema = [], [], []

    for caminho in sorted(pasta.glob("*.jpg")):
        if filtro and filtro.lower() not in caminho.name.lower():
            continue
        if caminho.name in ja_lidos:
            continue
        try:
            campos = le_exame(caminho)
        except ExameIlegivel as erro:
            ilegiveis.append((caminho.name, str(erro)))
            continue

        problemas = campos.pop("_problemas", [])
        if problemas:
            com_problema.append((caminho.name, problemas))

        data = campos.get("dt_exame")
        comum = {"nm_arquivo": caminho.name,
                 "ds_template": campos.get("ds_template"),
                 "ds_data_exame": data.isoformat() if data else None}

        # As chaves com sublinhado guardam o resultado das conferencias.
        # Ficam na bronze junto com as medidas porque sairam da mesma
        # leitura, e porque defeito registrado onde da para consultar
        # vale mais que defeito num log de terminal.
        registros = [(k, v) for k, v in campos.items() if not k.startswith("_")]
        registros += [(f"_problema_{i}", p) for i, p in enumerate(problemas, 1)]

        for campo, valor in registros:
            linhas.append({
                **comum,
                "ds_campo": campo,
                "ds_valor": None if valor is None else str(valor),
                "hash_negocio": hashlib.sha256(
                    f"inbody|{caminho.name}|{campo}".encode("utf-8")).hexdigest(),
            })

    return pd.DataFrame(linhas), ilegiveis, com_problema


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(ATUALIZAVEIS)} "
            f"FROM {SCHEMA}.{TABELA}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(TABELA, conn, schema=SCHEMA, if_exists="append",
                         index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", ATUALIZAVEIS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in ATUALIZAVEIS)
            conn.execute(
                text(f"UPDATE {SCHEMA}.{TABELA} SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga bronze dos exames InBody")
    parser.add_argument("--arquivo", help="le apenas os arquivos cujo nome "
                                          "contenha este texto")
    parser.add_argument("--reprocessar", action="store_true",
                        help="refaz o OCR dos exames ja lidos. So faz sentido "
                             "depois de melhorar o extrator - a imagem em si "
                             "nunca muda")
    args = parser.parse_args()

    pasta = PATH_EXAMES
    if not pasta or not pasta.exists():
        print(f"ERRO: pasta de exames nao encontrada em {pasta}")
        print("  Confira PATH_EXAMES no .env.")
        return 1

    engine = get_engine()
    ja_lidos = set()
    if not args.reprocessar:
        ja_lidos = set(pd.read_sql(
            f"SELECT DISTINCT nm_arquivo FROM {SCHEMA}.{TABELA}",
            engine)["nm_arquivo"])

    df, ilegiveis, com_problema = le_pasta(pasta, args.arquivo, ja_lidos)

    if df.empty and ja_lidos:
        print(f"== Exames InBody ==")
        print(f"  {len(ja_lidos)} exames ja lidos, nenhum arquivo novo.")
        print(f"  +0 novos, 0 atualizados")
        registra_carga(engine, f"{SCHEMA}.{TABELA}", 0, 0, inicio=_INICIO)
        return 0

    if df.empty:
        print(f"Nenhum exame legivel em {pasta}")
        return SAIDA_SEM_DADOS

    novos, alterados = sincroniza(df, engine)
    exames = df["nm_arquivo"].nunique()

    print(f"== Exames InBody ==")
    print(f"  {exames} arquivos lidos, {len(df)} campos")
    print(f"  +{novos} novos, {alterados} atualizados")
    registra_carga(engine, f"{SCHEMA}.{TABELA}", novos, alterados,
                   inicio=_INICIO)

    if ilegiveis:
        print(f"\n== {len(ilegiveis)} arquivos NAO lidos ==")
        for nome, motivo in ilegiveis:
            print(f"  {nome}: {motivo[:90]}")

    if com_problema:
        print(f"\n== {len(com_problema)} exames com conferencia falhando ==")
        print("   Os valores recusados NAO foram gravados; a planilha cobre")
        print("   a lacuna onde tiver o campo.")
        for nome, problemas in com_problema:
            print(f"  {nome}")
            for p in problemas:
                print(f"     - {p[:95]}")

    if sem_dados(engine, f"{SCHEMA}.{TABELA}"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT ds_template AS template, COUNT(DISTINCT nm_arquivo) AS exames,
                   COUNT(*) AS campos,
                   MIN(ds_data_exame) AS primeiro, MAX(ds_data_exame) AS ultimo
            FROM {SCHEMA}.{TABELA}
            WHERE ds_campo NOT LIKE '\\_%' ESCAPE '\\'
            GROUP BY ds_template ORDER BY primeiro
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
