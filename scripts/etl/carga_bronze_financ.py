"""
Carga da camada Bronze - historico financeiro 2014-2018.

Le a aba "cadastro" de dados-financ-completo.xlsx e grava em
bronze.financ_historico. Sao os lancamentos anteriores as origens
atuais: o Itau comeca em out/2016 e os cartoes em mai/2018.

A CHAVE E A COLUNA ID DA PLANILHA, desde a primeira carga. Diferente
do Itau e do cartao XP, que precisaram de migracao para trocar de
chave, aqui nao ha dado carregado - o ID ja e a identidade de saida, e
descricao, valor e data ficam corrigiveis desde o inicio.

As outras duas abas nao entram: "param" e lista de valores validos e
"analise" e uma tabela dinamica.

Uso:
    python carga_bronze_financ.py
"""

import argparse
import time
import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, normaliza_id, registra_carga,
    sem_dados, valida_id_origem,
)

_INICIO = time.monotonic()

SCHEMA, TABELA = "bronze", "financ_historico"
ARQUIVO = "dados-financ-completo.xlsx"
ABA = "cadastro"

COLUNAS = {
    "ID": "ds_id_origem",
    "Data": "ds_data",
    "Descrição": "ds_descricao",
    "Valor": "ds_valor",
    "Valor Trat": "ds_valor_tratado",
    "Tipo Movimentação": "ds_tipo_movimentacao",
    "Forma Pagamento": "ds_forma_pagamento",
    "Data Pgto": "ds_data_pgto",
    "Status Pgto": "ds_status_pgto",
    "Área": "ds_area",
    "Categoria": "ds_categoria",
    "Grupo": "ds_grupo",
    "Pessoa Pagar": "ds_pessoa_pagar",
    "Pessoa Receber": "ds_pessoa_receber",
    "Cidade": "ds_cidade",
    "UF": "ds_uf",
    "País": "ds_pais",
    "OBS": "ds_obs",
    "Projeto": "ds_projeto",
    "Tag": "ds_tag",
}
DESTINO = list(COLUNAS.values())
DATAS = ["ds_data", "ds_data_pgto"]
NUMEROS = ["ds_valor", "ds_valor_tratado"]

CHAVE_HASH = ["ds_id_origem"]
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]


def _data_iso(valor) -> str:
    dt = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _numero(valor) -> str:
    num = pd.to_numeric(valor, errors="coerce")
    return "" if pd.isna(num) else f"{num:.2f}"


def prepara(bruto: pd.DataFrame, caminho: Path) -> pd.DataFrame:
    faltando = [o for o in COLUNAS if o not in bruto.columns]
    if faltando:
        raise ValueError(
            f"A aba {ABA!r} nao tem as colunas esperadas: {faltando}.\n"
            f"  Encontradas: {list(bruto.columns)}")

    df = bruto.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    for col in DATAS:
        df[col] = df[col].map(_data_iso)
    for col in NUMEROS:
        df[col] = df[col].map(_numero)
    for col in DESTINO:
        if col not in DATAS + NUMEROS:
            df[col] = df[col].map(
                lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
                else str(v).strip()
            )

    # Cauda de formula arrastada. O criterio e sem data E sem
    # descricao, e nao "sem valor": a ultima linha da planilha esta
    # inteiramente vazia mas tem "Valor Trat" igual a 0, calculado pela
    # formula sobre uma celula em branco. Filtrar por valor vazio a
    # deixaria passar, e ela chegaria ate a validacao de ID como se
    # fosse um lancamento sem identidade.
    vazias = (df["ds_data"] == "") & df["ds_descricao"].isna()
    descartadas = int(vazias.sum())
    df = df[~vazias].copy()

    df["ds_id_origem"] = df["ds_id_origem"].map(normaliza_id)
    valida_id_origem(df["ds_id_origem"], "ID", "historico financeiro")
    df["hash_negocio"] = [
        hashlib.sha256(f"financ|{i}".encode("utf-8")).hexdigest()
        for i in df["ds_id_origem"]
    ]
    df["nm_arquivo_origem"] = caminho.name
    return df.assign(_descartadas=descartadas)


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int, int, int]:
    descartadas = int(df["_descartadas"].iloc[0]) if len(df) else 0
    df = df.drop(columns="_descartadas")

    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(ATUALIZAVEIS)} "
            f"FROM {SCHEMA}.{TABELA}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(TABELA, conn, schema=SCHEMA, if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", ATUALIZAVEIS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in ATUALIZAVEIS)
            conn.execute(
                text(f"UPDATE {SCHEMA}.{TABELA} SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados), len(df) - len(novos), descartadas


def main() -> int:
    argparse.ArgumentParser(
        description="Carga bronze do historico financeiro").parse_args()

    caminho = PATH_DADOS_ORIGEM / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: {caminho} nao encontrado")
        return 1

    bruto = pd.read_excel(caminho, sheet_name=ABA)
    try:
        preparado = prepara(bruto, caminho)
    except ValueError as erro:
        print(f"ERRO ao preparar a carga:\n  {erro}")
        return 1

    engine = get_engine()
    novos, alterados, existiam, descartadas = sincroniza(preparado, engine)

    print(f"== {ARQUIVO} / aba {ABA} ==")
    print(f"  +{novos} novos  {alterados} atualizados  "
          f"{existiam} sem mudanca  {descartadas} linhas vazias descartadas")
    registra_carga(engine, "bronze.financ_historico", novos, alterados, descartados=descartadas, inicio=_INICIO)

    if sem_dados(engine, "bronze.financ_historico"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT COUNT(*) AS lancamentos,
                   MIN(ds_data) AS primeiro, MAX(ds_data) AS ultimo,
                   SUM(CASE WHEN ds_tipo_movimentacao = 'Meta' THEN 1 ELSE 0 END) AS meta,
                   SUM(CASE WHEN ds_forma_pagamento IS NULL THEN 1 ELSE 0 END) AS sem_forma
            FROM {SCHEMA}.{TABELA}
        """, conn).to_string(index=False))

        print("\n== Por forma de pagamento ==")
        print(pd.read_sql(f"""
            SELECT ISNULL(ds_forma_pagamento, '(sem forma)') AS forma,
                   COUNT(*) AS lancamentos,
                   CAST(SUM(TRY_CAST(ds_valor_tratado AS decimal(18,2)))
                        AS decimal(14,2)) AS total
            FROM {SCHEMA}.{TABELA}
            WHERE ds_tipo_movimentacao <> 'Meta'
            GROUP BY ds_forma_pagamento ORDER BY 2 DESC
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
