"""
Carga da camada Silver - exames InBody tipados.

Reconstroi cada exame a partir dos campos da bronze e traduz para o
grao do fato de destino: uma linha por exame, metrica e SEGMENTO.

A TRADUCAO E A PONTE ENTRE AS DUAS ORIGENS. Os nomes de metrica aqui
sao os mesmos que a planilha preenchida a mao ja usa desde 2008 - e e
por isso que arquivo e planilha caem na mesma linha do fato, em vez de
criarem duas series paralelas para a mesma coisa.

Uso:
    python carga_silver_inbody.py
"""

import argparse
import hashlib
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from regras_inbody import campos_para_medidas, numero  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados, valor_sql,
)

_INICIO = time.monotonic()

DERIVADAS = ["vl_medida", "vl_referencia_min", "vl_referencia_max",
             "ds_avaliacao", "ds_template", "nm_arquivo"]

# Campos que sao texto e nao devem virar numero: a avaliacao segmentar
# ("Acima") e a versao do leiaute.
TEXTUAIS = ("ds_", "_aval")


def _valor_do_campo(campo: str, bruto):
    if bruto is None or (isinstance(bruto, float) and pd.isna(bruto)):
        return None
    if campo.startswith("ds_") or campo.endswith("_aval"):
        return str(bruto)
    return numero(bruto)


def monta_medidas(bronze: pd.DataFrame) -> pd.DataFrame:
    """
    Um exame por arquivo, um dicionario de campos por exame.

    As chaves com sublinhado - o resultado das conferencias - ficam de
    fora: elas descrevem a LEITURA, nao o corpo, e nao tem lugar num
    fato de composicao corporal.
    """
    linhas = []
    for arquivo, grupo in bronze.groupby("nm_arquivo"):
        campos = {}
        for r in grupo.itertuples():
            if r.ds_campo.startswith("_"):
                continue
            campos[r.ds_campo] = _valor_do_campo(r.ds_campo, r.ds_valor)

        data = grupo["ds_data_exame"].dropna()
        if data.empty:
            continue
        campos["dt_exame"] = date.fromisoformat(data.iloc[0])
        campos["ds_template"] = grupo["ds_template"].dropna().iloc[0] \
            if grupo["ds_template"].notna().any() else None

        for medida in campos_para_medidas(campos):
            medida["nm_arquivo"] = arquivo
            medida["hash_negocio"] = hashlib.sha256(
                f"inbody|{medida['dt_exame']}|{medida['nm_metrica']}|"
                f"{medida['nm_segmento']}".encode("utf-8")).hexdigest()
            linhas.append(medida)

    df = pd.DataFrame(linhas)
    for col in ("vl_medida", "vl_referencia_min", "vl_referencia_max"):
        if col in df.columns:
            df[col] = df[col].map(valor_sql)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        sumiram = []
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(DERIVADAS)} "
            f"FROM silver.avaliacao_inbody", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("avaliacao_inbody", conn, schema="silver",
                         if_exists="append", index=False)


        # REMOVE O QUE DEIXOU DE EXISTIR NA ORIGEM. Esta tabela e uma
        # projecao completa de bronze.avaliacao_inbody: uma medida que sumiu de la
        # nao pode sobreviver aqui.
        #
        # Sem isto, um valor que o extrator passou a REJEITAR ficava
        # para sempre. Foi o que aconteceu com o exame de 13/08/2018:
        # a bronze corrigiu o percentual de gordura para nulo e a
        # silver seguiu com 9,0% - um numero que nenhuma origem
        # afirmava mais.
        #
        # A remocao entra na contagem de atualizados porque E uma
        # mudanca na tabela: convergencia que ignora exclusao diria
        # "nada mudou" enquanto linhas somem.
        vivos = set(df["hash_negocio"])
        sumiram = [h for h in atual["hash_negocio"] if h not in vivos]
        if sumiram:
            conn.execute(text("DELETE FROM silver.avaliacao_inbody WHERE hash_negocio = :h"),
                         [{"h": h} for h in sumiram])
            print(f"  removidas   : {len(sumiram)} medidas que sumiram da origem")

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.avaliacao_inbody SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados) + len(sumiram)


def main() -> int:
    argparse.ArgumentParser(description="Carga silver dos exames InBody").parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.avaliacao_inbody", engine)
    print(f"Lidos {len(bronze)} campos de "
          f"{bronze['nm_arquivo'].nunique()} exames na bronze")

    df = monta_medidas(bronze)
    if df.empty:
        print("Nenhuma medida montada.")
        return SAIDA_SEM_DADOS

    inseridos, atualizados = sincroniza(df, engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.avaliacao_inbody", inseridos, atualizados,
                   inicio=_INICIO)

    if sem_dados(engine, "silver.avaliacao_inbody"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql("""
            SELECT nm_segmento AS segmento, COUNT(DISTINCT nm_metrica) AS metricas,
                   COUNT(*) AS medidas, COUNT(DISTINCT dt_exame) AS exames
            FROM silver.avaliacao_inbody
            GROUP BY nm_segmento ORDER BY medidas DESC
        """, conn).to_string(index=False))

        print()
        print("== massa magra das pernas, por exame ==")
        print(pd.read_sql("""
            SELECT dt_exame,
                   MAX(CASE WHEN nm_segmento = 'Perna esquerda'
                            THEN vl_medida END) AS perna_esq,
                   MAX(CASE WHEN nm_segmento = 'Perna direita'
                            THEN vl_medida END) AS perna_dir
            FROM silver.avaliacao_inbody
            WHERE nm_metrica = 'Massa Magra Segmentar'
            GROUP BY dt_exame ORDER BY dt_exame
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
