"""
Carga da camada Bronze - manutencao do automovel.

Le pla-revisao-auto.xls e grava em bronze.auto_manutencao e
bronze.auto_intervalo_troca.

DUAS ABAS SAO ORIGEM. "Avaliacoes" e o historico; "Tempo Troca" e a
tabela que diz de quantos em quantos km cada categoria deve ser
trocada - e o que permite prever vencimento em vez de so arquivar
passado.

As outras tres nao entram: "Resultados" e "Ultima Troca" sao dinamicas
derivadas, e "Quilometragem" e uma celula auxiliar delas, com um numero
de 2025 que nao corresponde a nenhum dos dois carros hoje. A
quilometragem atual sai do proprio historico, por veiculo.

O arquivo e .xls antigo (OLE2) e exige xlrd, como a avaliacao fisica.

Uso:
    python carga_bronze_auto.py
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_PLANILHAS, get_engine  # noqa: E402
from regras_xp import normaliza  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

ARQUIVO = "pla-revisao-auto.xls"
ABA_HISTORICO, ABA_INTERVALO = "Avaliações", "Tempo Troca"

COLUNAS = {
    "DATA": "ds_data",
    "CARRO": "ds_veiculo",
    "KM": "ds_km",
    "REVISAO": "ds_natureza",
    "TIPO": "ds_tipo",
    "ITEM": "ds_item",
    "CATEGORIA": "ds_categoria",
    "UNID": "ds_quantidade",
    "VALOR": "ds_valor",
    "LOCAL": "ds_local",
    "OBSERVAÇÃO": "ds_observacao",
}
DESTINO = list(COLUNAS.values())

# A chave e data + veiculo + item + ocorrencia. Todo o resto pode ser
# corrigido na planilha sem que o lancamento vire outro.
CHAVE_HASH = ["ds_data", "ds_veiculo", "ds_item"]
ATUALIZAVEIS = [c for c in DESTINO if c not in CHAVE_HASH]


def _texto(valor):
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return None
    return str(valor).strip()


def prepara_historico(bruto: pd.DataFrame, nome_arquivo: str) -> pd.DataFrame:
    bruto.columns = [str(c).strip().upper() for c in bruto.columns]
    faltando = [o for o in COLUNAS if o not in bruto.columns]
    if faltando:
        raise ValueError(
            f"A aba {ABA_HISTORICO!r} nao tem as colunas esperadas: {faltando}.\n"
            f"  Encontradas: {list(bruto.columns)}")

    df = bruto.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)

    df["ds_data"] = pd.to_datetime(df["ds_data"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in DESTINO:
        if col != "ds_data":
            df[col] = df[col].map(_texto)

    sem_chave = df["ds_data"].isna() | df["ds_veiculo"].isna() | df["ds_item"].isna()
    descartadas = int(sem_chave.sum())
    df = df[~sem_chave].copy()

    # Duas pecas iguais na mesma visita sao dois gastos reais - dois
    # filtros de ar por precos diferentes, dois amortecedores do mesmo
    # eixo. Sem o contador, metade delas seria tomada por duplicata.
    chave = (df["ds_data"] + "|" + df["ds_veiculo"] + "|"
             + df["ds_item"].map(normaliza))
    df["nr_ocorrencia"] = chave.groupby(chave).cumcount() + 1
    df["hash_negocio"] = [
        hashlib.sha256(f"{k}|{n}".encode("utf-8")).hexdigest()
        for k, n in zip(chave, df["nr_ocorrencia"])
    ]
    df["nm_arquivo_origem"] = nome_arquivo
    return df.assign(_descartadas=descartadas)


def prepara_intervalo(bruto: pd.DataFrame, nome_arquivo: str) -> pd.DataFrame:
    bruto.columns = [str(c).strip().upper() for c in bruto.columns]
    if len(bruto.columns) < 2:
        raise ValueError(f"A aba {ABA_INTERVALO!r} deveria ter duas colunas.")

    df = pd.DataFrame({
        "ds_categoria": bruto.iloc[:, 0].map(_texto),
        "ds_intervalo_km": bruto.iloc[:, 1].map(_texto),
    })
    df = df[df["ds_categoria"].notna()].copy()
    df["hash_negocio"] = [
        hashlib.sha256(normaliza(c).encode("utf-8")).hexdigest()
        for c in df["ds_categoria"]
    ]
    df["nm_arquivo_origem"] = nome_arquivo
    return df


def sincroniza(df, engine, tabela, atualizaveis) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(atualizaveis)} "
            f"FROM bronze.{tabela}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(tabela, conn, schema="bronze",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", atualizaveis)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in atualizaveis)
            conn.execute(
                text(f"UPDATE bronze.{tabela} SET {sets}, dt_carga = SYSDATETIME() "
                     f"WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def main() -> int:
    argparse.ArgumentParser(description="Carga bronze da manutencao auto").parse_args()

    caminho = PATH_PLANILHAS / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: arquivo nao encontrado em {caminho}")
        print("  Confira PATH_PLANILHAS no .env.")
        return 1

    try:
        historico = prepara_historico(
            pd.read_excel(caminho, sheet_name=ABA_HISTORICO, dtype=object),
            caminho.name)
        intervalo = prepara_intervalo(
            pd.read_excel(caminho, sheet_name=ABA_INTERVALO, dtype=object),
            caminho.name)
    except ImportError:
        print("ERRO: falta a biblioteca xlrd, necessaria para ler .xls antigo.")
        print("  pip install xlrd==2.0.2")
        return 1
    except ValueError as erro:
        print(f"ERRO ao ler a planilha:\n  {erro}")
        return 1

    descartadas = int(historico["_descartadas"].iloc[0]) if len(historico) else 0
    historico = historico.drop(columns="_descartadas")

    engine = get_engine()
    novos, alterados = sincroniza(historico, engine, "auto_manutencao", ATUALIZAVEIS)
    novos_i, alterados_i = sincroniza(intervalo, engine, "auto_intervalo_troca",
                                      ["ds_intervalo_km"])

    print(f"== {caminho.name} ==")
    print(f"  aba {ABA_HISTORICO}: +{novos} novos, {alterados} atualizados, "
          f"{descartadas} sem chave descartadas")
    print(f"  aba {ABA_INTERVALO}: +{novos_i} novos, {alterados_i} atualizados")

    # Uma linha por tabela, e nao por script: as duas abas alimentam
    # tabelas distintas, e o grao de gold.fato_carga e a tabela.
    registra_carga(engine, "bronze.auto_manutencao", novos, alterados,
                   descartados=descartadas, inicio=_INICIO)
    registra_carga(engine, "bronze.auto_intervalo_troca", novos_i, alterados_i,
                   inicio=_INICIO)

    if sem_dados(engine, "bronze.auto_manutencao",
                  "bronze.auto_intervalo_troca"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql("""
            SELECT ds_veiculo AS veiculo, COUNT(*) AS lancamentos,
                   COUNT(DISTINCT ds_data) AS visitas,
                   MIN(ds_data) AS primeira, MAX(ds_data) AS ultima,
                   MIN(TRY_CAST(ds_km AS int)) AS km_min,
                   MAX(TRY_CAST(ds_km AS int)) AS km_max,
                   CAST(SUM(TRY_CAST(ds_valor AS decimal(12,2)))
                        AS decimal(12,2)) AS gasto
            FROM bronze.auto_manutencao
            GROUP BY ds_veiculo ORDER BY 4
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
