"""
Carga da camada Bronze - plano de revisao do fabricante.

Le Plano_Manutencao_Montadora_SUV_2017.xlsx e grava em
bronze.auto_revisao_programada.

NAO E EVENTO, E REGRA. As demais bronzes guardam o que aconteceu -
uma ida a oficina, uma compra, uma resposta de formulario. Esta guarda
o que DEVE acontecer, segundo o fabricante. Sao 21 itens de um manual,
e nao 21 fatos.

LE A PRIMEIRA ABA, PELA POSICAO E NAO PELO NOME. O nome da aba carrega
o modelo ("Plano de Manutencao SUV 2017"), entao um plano de outro
carro teria outro nome e quebraria um script que casasse por texto. A
segunda aba, a matriz de revisoes por marco, nao entra: e a mesma regra
reapresentada, e o que ela acrescenta ja sai do intervalo mais a acao.

Uso:
    python carga_bronze_revisao.py
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

ARQUIVO = "Plano_Manutencao_Montadora_SUV_2017.xlsx"
SCHEMA, TABELA = "bronze", "auto_revisao_programada"

# O cabecalho esta na quarta linha: titulo, subtitulo tecnico, branco,
# cabecalho. As tres primeiras sao apresentacao, nao dado.
LINHA_CABECALHO = 3

COLUNAS = {
    "Item / Componente": "ds_item",
    "Sistema / Categoria": "ds_sistema",
    "Intervalo (Km)": "ds_intervalo_km",
    "Intervalo (Tempo)": "ds_intervalo_tempo",
    "Ação Recomendada": "ds_acao",
    "Especificação / Observação": "ds_especificacao",
}
DESTINO = list(COLUNAS.values())

# O item e a identidade; todo o resto do plano pode ser corrigido sem
# que a regra vire outra.
ATUALIZAVEIS = [c for c in DESTINO if c != "ds_item"] + ["ds_modelo"]


def _texto(valor):
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return None
    return str(valor).strip()


def le_modelo(caminho: Path) -> str:
    """
    Extrai o modelo do titulo da aba.

    O titulo e "PLANO DE MANUTENCAO PREVENTIVA - MONTADORA SUV 2017
    (2.0 16V)". Interessa o trecho depois do travessao e antes do
    parenteses: "MONTADORA SUV 2017". E ele que a gold usa para achar
    o veiculo, procurando o nome do carro dentro desse texto - o plano
    do SUV nao pode valer para o Sedan.
    """
    titulo = pd.read_excel(caminho, sheet_name=0, header=None, nrows=1)
    bruto = _texto(titulo.iloc[0, 0]) or ""
    if " - " in bruto:
        bruto = bruto.split(" - ", 1)[1]
    if "(" in bruto:
        bruto = bruto.split("(", 1)[0]
    modelo = bruto.strip()
    if not modelo:
        raise ValueError(
            f"Nao consegui ler o modelo no titulo da primeira aba de {ARQUIVO}.\n"
            f"  A primeira celula deveria trazer algo como "
            f"'PLANO DE MANUTENCAO PREVENTIVA - MONTADORA SUV 2017'.")
    return modelo


def le_plano(caminho: Path) -> pd.DataFrame:
    bruto = pd.read_excel(caminho, sheet_name=0, header=LINHA_CABECALHO)
    bruto.columns = [str(c).strip() for c in bruto.columns]

    faltando = [o for o in COLUNAS if o not in bruto.columns]
    if faltando:
        raise ValueError(
            f"A primeira aba de {ARQUIVO} nao tem as colunas esperadas: {faltando}.\n"
            f"  Encontradas: {list(bruto.columns)}\n"
            f"  Se o cabecalho mudou de linha, ajuste LINHA_CABECALHO neste script.")

    df = bruto.rename(columns=COLUNAS)[DESTINO].copy()
    df["nr_linha_arquivo"] = range(1, len(df) + 1)
    for col in DESTINO:
        df[col] = df[col].map(_texto)

    # Sem item nao ha regra: e cauda de planilha, nao linha do manual.
    sem_item = df["ds_item"].isna()
    df = df[~sem_item].copy()

    df["ds_modelo"] = le_modelo(caminho)
    df["hash_negocio"] = [
        hashlib.sha256(f"revisao|{normaliza(m)}|{normaliza(i)}".encode("utf-8")).hexdigest()
        for m, i in zip(df["ds_modelo"], df["ds_item"])
    ]
    df["nm_arquivo_origem"] = caminho.name
    df["nm_aba_origem"] = pd.ExcelFile(caminho).sheet_names[0]
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
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
    return len(novos), len(alterados)


def main() -> int:
    argparse.ArgumentParser(
        description="Carga bronze do plano de revisao do fabricante").parse_args()

    caminho = PATH_PLANILHAS / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: arquivo nao encontrado em {caminho}")
        print("  Confira PATH_PLANILHAS no .env.")
        return 1

    engine = get_engine()
    try:
        plano = le_plano(caminho)
    except ValueError as erro:
        print(f"ERRO ao ler a planilha:\n  {erro}")
        return 1

    novos, alterados = sincroniza(plano, engine)

    print(f"== {caminho.name} ==")
    # Planilha sem linha de dado ainda tem titulo: nao pode quebrar aqui,
    # senao o erro fala de pandas em vez de falar da origem vazia, e a
    # guarda de sem_dados logo abaixo nunca chega a rodar.
    modelo = plano["ds_modelo"].iloc[0] if len(plano) else "(planilha sem itens)"
    print(f"  modelo: {modelo}")
    print(f"  +{novos} novos, {alterados} atualizados  ({len(plano)} itens no plano)")
    registra_carga(engine, f"{SCHEMA}.{TABELA}", novos, alterados, inicio=_INICIO)

    if sem_dados(engine, f"{SCHEMA}.{TABELA}"):
        return SAIDA_SEM_DADOS

    with engine.connect() as conn:
        print()
        print(pd.read_sql(f"""
            SELECT ds_sistema AS sistema, COUNT(*) AS itens,
                   MIN(TRY_CAST(ds_intervalo_km AS int)) AS km_min,
                   MAX(TRY_CAST(ds_intervalo_km AS int)) AS km_max
            FROM {SCHEMA}.{TABELA}
            GROUP BY ds_sistema ORDER BY itens DESC, sistema
        """, conn).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
