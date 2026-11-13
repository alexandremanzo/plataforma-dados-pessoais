"""
Carga da camada Bronze - investimentos XP.

Uma tabela, duas origens com papeis diferentes:

    dados-xp.xlsx (aba movto)  -> SEMENTE do historico. Contem
                                  movimentacoes anteriores aos
                                  arquivos de extrato que ainda
                                  existem, entao e a base da tabela.

    xp/extrato-xp.xlsx         -> INCREMENTO. O extrato e baixado
    xp/bkp/*.xlsx                 varias vezes por mes, sempre com a
                                  janela do mes anterior, entao os
                                  arquivos se sobrepoem quase todos.

A carga insere apenas eventos cujo hash_negocio ainda nao existe na
tabela. A semente e processada primeiro, de forma que a classificacao
manual da planilha seja preservada quando o mesmo evento aparecer
depois num extrato.

Idempotente: rodar N vezes produz o mesmo resultado que rodar uma vez.

Uso:
    python carga_bronze_xp.py
    python carga_bronze_xp.py --so-extrato
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402
from regras_xp import normaliza  # noqa: E402
from util_dados import (  # noqa: E402
    SAIDA_SEM_DADOS, detecta_alteracoes, registra_carga, sem_dados,
)

_INICIO = time.monotonic()

SCHEMA = "bronze"
TABELA = "xp_movimentacao"

COLUNAS_BASE = ["ds_movimentacao", "ds_liquidacao", "ds_lancamento",
                "ds_valor", "ds_saldo"]
COLUNAS_MANUAIS = ["ds_categoria_origem", "ds_rendimento_origem", "ds_ativo_origem"]


# =====================================================================
# Identidade do evento
# =====================================================================

def _data_iso(valor) -> str:
    dt = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _numero(valor) -> str:
    num = pd.to_numeric(valor, errors="coerce")
    return "" if pd.isna(num) else f"{num:.2f}"


def calcula_hash(linha: pd.Series) -> str:
    """
    SHA-256 de data + data + descricao + valor + saldo.

    O saldo entra na chave de proposito: e ele que separa duas
    transacoes iguais no mesmo dia (que movem o saldo) de uma linha
    lancada duas vezes (que mantem o mesmo saldo).
    """
    chave = "|".join([
        _data_iso(linha["ds_movimentacao"]),
        _data_iso(linha["ds_liquidacao"]),
        normaliza(linha["ds_lancamento"]),
        _numero(linha["ds_valor"]),
        _numero(linha["ds_saldo"]),
    ])
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


# =====================================================================
# Leitura
# =====================================================================

def _acha_cabecalho(caminho: Path) -> int:
    """
    Descobre a linha do cabecalho no extrato da XP.

    Hoje cai sempre na linha 13, depois do preambulo com dados da
    conta, mas procurar pelo texto evita quebrar se a XP mudar o
    layout do arquivo.
    """
    espiada = pd.read_excel(caminho, header=None, nrows=40)
    for idx, linha in espiada.iterrows():
        if any("MOVIMENTA" in normaliza(c) for c in linha.values):
            return int(idx)
    raise ValueError("cabecalho nao encontrado")


def le_semente(caminho: Path) -> pd.DataFrame:
    """Le a planilha mestre, incluindo a classificacao feita a mao."""
    df = pd.read_excel(caminho, sheet_name="movto").rename(columns={
        "Movimentação": "ds_movimentacao",
        "Liquidação": "ds_liquidacao",
        "Lançamento": "ds_lancamento",
        "Valor (R$)": "ds_valor",
        "Saldo (R$)": "ds_saldo",
        "Categoria": "ds_categoria_origem",
        "Rendimento": "ds_rendimento_origem",
        "Açao": "ds_ativo_origem",
    })
    return _prepara(df, caminho, COLUNAS_BASE + COLUNAS_MANUAIS)


def le_extrato(caminho: Path) -> pd.DataFrame:
    """Le um arquivo de extrato da XP (sem colunas de classificacao)."""
    df = pd.read_excel(caminho, skiprows=_acha_cabecalho(caminho))

    # O arquivo termina com um rodape; a primeira linha sem data
    # marca o fim dos dados.
    vazias = df[df["Movimentação"].isna()].index
    if len(vazias):
        df = df.iloc[: vazias[0]].copy()

    df = df.rename(columns={
        "Movimentação": "ds_movimentacao",
        "Liquidação": "ds_liquidacao",
        "Lançamento": "ds_lancamento",
        "Valor (R$)": "ds_valor",
        "Saldo (R$)": "ds_saldo",
    })
    for col in COLUNAS_MANUAIS:
        df[col] = None
    return _prepara(df, caminho, COLUNAS_BASE + COLUNAS_MANUAIS)


def _prepara(df: pd.DataFrame, caminho: Path, colunas: list[str]) -> pd.DataFrame:
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise ValueError(f"colunas ausentes: {faltando}")

    df = df[colunas].copy()
    df.insert(0, "nr_linha_arquivo", range(1, len(df) + 1))
    df["hash_negocio"] = df.apply(calcula_hash, axis=1)

    for col in ("ds_movimentacao", "ds_liquidacao"):
        df[col] = df[col].map(_data_iso)
    for col in ("ds_valor", "ds_saldo"):
        df[col] = df[col].map(_numero)
    for col in COLUNAS_MANUAIS + ["ds_lancamento"]:
        df[col] = df[col].map(
            lambda v: None if v is None or pd.isna(v) or str(v).strip() == ""
            else str(v).strip()
        )

    df["nm_arquivo_origem"] = caminho.name

    # Dentro de um mesmo arquivo tambem pode haver repeticao (foi o
    # que aconteceu na planilha mestre). Fica a primeira ocorrencia.
    antes = len(df)
    df = df.drop_duplicates(subset="hash_negocio", keep="first")
    return df.assign(_repetidas_no_arquivo=antes - len(df))


# =====================================================================
# Gravacao
# =====================================================================

def sincroniza(df: pd.DataFrame, engine, atualiza: bool = False) -> tuple[int, int, int, int]:
    """
    Insere os eventos ausentes e, opcionalmente, atualiza os existentes.

    O parametro atualiza so vale para a SEMENTE, e a razao e o sentido
    de cada origem: a planilha mestre traz a classificacao feita a mao,
    enquanto os extratos trazem apenas o lancamento cru. Deixar um
    extrato atualizar apagaria a classificacao com nulo, ja que ele nao
    tem essas colunas.

    Sem a atualizacao na semente, classificar um lancamento ja existente
    nunca chegaria ao banco: a classificacao nao entra no hash, entao o
    identificador do evento nao muda.
    """
    repetidas = int(df["_repetidas_no_arquivo"].iloc[0]) if len(df) else 0
    df = df.drop(columns="_repetidas_no_arquivo")

    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(COLUNAS_MANUAIS)} "
            f"FROM {SCHEMA}.{TABELA}", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql(TABELA, conn, schema=SCHEMA, if_exists="append", index=False)

        alterados = []
        if atualiza:
            alterados = detecta_alteracoes(atual, df, "hash_negocio", COLUNAS_MANUAIS)
            if alterados:
                sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_MANUAIS)
                conn.execute(
                    text(f"UPDATE {SCHEMA}.{TABELA} SET {sets}, dt_carga = SYSDATETIME() "
                         f"WHERE hash_negocio = :chave"),
                    alterados,
                )

    return len(novos), len(alterados), len(df) - len(novos), repetidas


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga bronze dos investimentos XP")
    parser.add_argument("--so-extrato", action="store_true")
    parser.add_argument("--so-semente", action="store_true")
    args = parser.parse_args()

    engine = get_engine()

    # Os atualizados passam a ser somados junto com os novos. Antes so
    # o total de novos era acumulado, e registrar "0 atualizados" em
    # gold.fato_carga afirmaria convergencia sem ter contado nada - a
    # unica coisa pior que nao ter o numero e ter um numero falso.
    total_novos = total_alterados = 0

    # A semente vem primeiro para que a classificacao manual seja
    # preservada quando o mesmo evento reaparecer num extrato.
    if not args.so_extrato:
        semente = PATH_DADOS_ORIGEM / "dados-xp.xlsx"
        print("== Semente (planilha mestre) ==")
        if semente.exists():
            # atualiza=True: e a unica origem que traz classificacao.
            novos, alterados, existentes, repetidas = sincroniza(
                le_semente(semente), engine, atualiza=True)
            print(f"  {semente.name:<45} +{novos:<5} novos  {alterados:>4} atualizados  "
                  f"{existentes:>4} sem mudanca  {repetidas:>3} repetidas no arquivo")
            total_novos += novos
            total_alterados += alterados
        else:
            print(f"  AVISO: {semente} nao encontrado")

    if not args.so_semente:
        print("\n== Incrementos (extratos) ==")
        pasta = PATH_DADOS_ORIGEM / "xp"
        arquivos = []
        if (pasta / "extrato-xp.xlsx").exists():
            arquivos.append(pasta / "extrato-xp.xlsx")
        arquivos += sorted((pasta / "bkp").glob("*.xlsx"))

        if not arquivos:
            print(f"  AVISO: nenhum extrato em {pasta}")

        for arq in arquivos:
            try:
                # Sem atualiza: o extrato nao tem as colunas de
                # classificacao e sobrescreveria com nulo o que a
                # planilha mestre ja classificou.
                novos, alterados, existentes, repetidas = sincroniza(
                    le_extrato(arq), engine)
                print(f"  {arq.name:<45} +{novos:<5} novos  "
                      f"{existentes:>4} ja existiam  {repetidas:>3} repetidas no arquivo")
                total_novos += novos
                total_alterados += alterados
            except Exception as exc:
                # Um arquivo com layout inesperado nao derruba os demais.
                print(f"  {arq.name:<45} ERRO: {exc}")

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{TABELA}")
        ).scalar()

    print(f"\nEventos novos nesta execucao: {total_novos}")
    print(f"Total em {SCHEMA}.{TABELA}: {total}")
    registra_carga(engine, f"{SCHEMA}.{TABELA}", total_novos, total_alterados,
                   inicio=_INICIO)

    if sem_dados(engine, f"{SCHEMA}.{TABELA}"):
        return SAIDA_SEM_DADOS
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
