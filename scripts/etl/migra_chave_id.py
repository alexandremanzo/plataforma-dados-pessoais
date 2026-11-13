"""
Migracao unica: troca a chave de negocio das bases de cadastro manual.

Conta Itau e cartao XP passam a ser identificados pela coluna ID da
planilha, em vez da combinacao de data, descricao e valor.

POR QUE A MIGRACAO E NECESSARIA. Trocar a regra sem mais nada faria a
carga seguinte calcular um hash novo para CADA linha ja carregada:
9 mil registros entrariam como novos e os antigos ficariam orfaos,
dobrando os totais. Esta migracao reescreve o hash NO LUGAR, casando
cada linha da planilha com a linha correspondente no banco pelo hash
antigo. Chaves substitutas, datas de carga e o fato de movimentacao
seguem intactos.

COMO ELA CASA AS LINHAS. Para cada linha da planilha calcula os dois
hashes - o antigo, pela regra que vigorava, e o novo, pelo ID - e
atualiza bronze, silver e gold onde o antigo bater.

POR ISSO A ORDEM IMPORTA: acrescente os IDs SEM reordenar a planilha e
SEM corrigir nada ainda. Reordenar muda o numero de ocorrencia das
linhas repetidas e o hash antigo deixa de casar; corrigir um valor
antes muda o hash antigo pelo mesmo motivo. Primeiro os IDs, depois a
migracao, e so entao as correcoes - que a partir dali propagam
sozinhas ate a gold.

Roda em SIMULACAO por padrao. Nada e alterado sem --aplicar.

Uso:
    python migra_chave_id.py                    # simula, nao altera nada
    python migra_chave_id.py --aplicar          # executa
    python migra_chave_id.py --base itau        # so uma das duas
"""

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd
import sqlalchemy
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402
from regras_xp import normaliza  # noqa: E402
from util_dados import normaliza_id  # noqa: E402

COLUNA_ID = "ID"

# Onde o hash de cada base aparece, camada por camada.
#
# A GOLD PRECISA ESTAR AQUI. gold.fato_movto_financ tem 11.4 mil linhas
# chaveadas pelo mesmo hash; reescrever so bronze e silver deixaria a
# gold com o hash velho, e a carga seguinte inseriria tudo de novo sem
# remover o antigo - o fato dobraria.
#
# O terceiro elemento e o FILTRO DE ESCOPO, e existe por causa da
# silver de cartao: ela guarda Nubank na mesma tabela, e a limpeza de
# orfaos nao pode encostar nas linhas do outro cartao.
BASES = {
    "itau": {
        "arquivo": "dados-itau.xlsx",
        "aba": "cad-conta",
        "id_em": "bronze.itau_movimentacao",
        "camadas": [
            ("bronze.itau_movimentacao", "hash_negocio", None),
            ("silver.itau_movimentacao", "hash_negocio", None),
            ("gold.fato_movto_financ", "HASH_NEGOCIO", None),
        ],
    },
    "cartao-xp": {
        "arquivo": "dados-xp-credito.xlsx",
        "aba": "MOVTO",
        "id_em": "bronze.cartao_xp",
        "camadas": [
            ("bronze.cartao_xp", "hash_negocio", None),
            ("silver.cartao_movimentacao", "hash_negocio", "ds_cartao = 'XP'"),
            ("gold.fato_movto_financ", "HASH_NEGOCIO", None),
        ],
    },
}

# A gold recebe as duas bases e tambem o Nubank, entao a limpeza dela
# nao pode sair da lista de uma base so: e feita uma vez, no fim, pela
# regra geral "linha de gold sem par em nenhuma silver".
GOLD_COMPARTILHADA = "gold.fato_movto_financ"


def _data_iso(valor) -> str:
    dt = pd.to_datetime(valor, errors="coerce")
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _numero(valor) -> str:
    num = pd.to_numeric(valor, errors="coerce")
    return "" if pd.isna(num) else f"{num:.2f}"


def _texto(valor):
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return None
    return str(valor).strip()


def le_itau(caminho: Path, aba: str) -> pd.DataFrame:
    """Reproduz EXATAMENTE a chave antiga de carga_bronze_itau.py."""
    bruto = pd.read_excel(caminho, sheet_name=aba)
    df = pd.DataFrame({
        "ds_data": bruto["Data"].map(_data_iso),
        "ds_descricao": bruto["Descrição"].map(_texto),
        "ds_valor": bruto["Valor"].map(_numero),
        "id_origem": (bruto[COLUNA_ID].map(normaliza_id)
                      if COLUNA_ID in bruto.columns else None),
    })
    vazias = (df["ds_data"] == "") & df["ds_descricao"].isna() & (df["ds_valor"] == "")
    df = df[~vazias].copy()

    chave = (df["ds_data"] + "|"
             + df["ds_descricao"].fillna("").map(normaliza) + "|"
             + df["ds_valor"])
    ocorrencia = chave.groupby(chave).cumcount() + 1
    df["hash_antigo"] = [
        hashlib.sha256(f"{k}|{n}".encode("utf-8")).hexdigest()
        for k, n in zip(chave, ocorrencia)
    ]
    return df


def le_cartao_xp(caminho: Path, aba: str) -> pd.DataFrame:
    """Reproduz EXATAMENTE a chave antiga de carga_bronze_cartao_xp.py."""
    bruto = pd.read_excel(caminho, sheet_name=aba)
    df = pd.DataFrame({
        "ds_data": bruto["Data"].map(_data_iso),
        "ds_descricao": bruto["Descrição"].map(_texto),
        "ds_valor_tratado": bruto["Valor Trat"].map(_numero),
        "ds_data_pgto": bruto["Data Pgto"].map(_data_iso),
        "id_origem": (bruto[COLUNA_ID].map(normaliza_id)
                      if COLUNA_ID in bruto.columns else None),
    })
    vazias = (df["ds_data"] == "") & df["ds_descricao"].isna() & (
        df["ds_valor_tratado"] == "")
    df = df[~vazias].copy()

    chave = (df["ds_data"] + "|"
             + df["ds_descricao"].fillna("").map(normaliza) + "|"
             + df["ds_valor_tratado"] + "|"
             + df["ds_data_pgto"])
    ocorrencia = chave.groupby(chave).cumcount() + 1
    df["hash_antigo"] = [
        hashlib.sha256(f"{k}|{n}".encode("utf-8")).hexdigest()
        for k, n in zip(chave, ocorrencia)
    ]
    return df


LEITORES = {"itau": le_itau, "cartao-xp": le_cartao_xp}


def valida(df: pd.DataFrame, nome: str) -> list[str]:
    """Recusa a migracao se os IDs nao servirem de chave."""
    problemas = []
    if df["id_origem"].isna().all():
        problemas.append(
            f"A planilha nao tem a coluna {COLUNA_ID!r}, ou ela esta toda vazia.\n"
            f"    Acrescente a coluna e numere as linhas antes de migrar.")
        return problemas

    sem_id = df[df["id_origem"].isna()]
    if len(sem_id):
        problemas.append(
            f"{len(sem_id)} linhas com dados mas SEM {COLUNA_ID}. "
            f"Primeiras linhas da planilha: "
            f"{sorted(sem_id.index[:8] + 2)}")

    repetidos = df[df["id_origem"].notna() & df["id_origem"].duplicated(keep=False)]
    if len(repetidos):
        amostra = sorted(repetidos["id_origem"].unique())[:8]
        problemas.append(
            f"{len(repetidos)} linhas com {COLUNA_ID} REPETIDO. "
            f"Exemplos: {amostra}. Cada linha precisa de um numero unico.")
    return problemas


def migra(nome: str, cfg: dict, engine, aplicar: bool) -> set:
    """Devolve os hashes orfaos encontrados, para a limpeza da gold."""
    print(f"\n{'=' * 66}\n== {nome}  ({cfg['arquivo']} / aba {cfg['aba']})")

    caminho = PATH_DADOS_ORIGEM / cfg["arquivo"]
    if not caminho.exists():
        print(f"   ERRO: arquivo nao encontrado em {caminho}")
        return set()

    df = LEITORES[nome](caminho, cfg["aba"])
    print(f"   {len(df)} linhas com dados na planilha")

    problemas = valida(df, nome)
    if problemas:
        print("\n   MIGRACAO RECUSADA:")
        for p in problemas:
            print(f"    - {p}")
        return set()

    df["hash_novo"] = [
        hashlib.sha256(f"{nome}|{i}".encode("utf-8")).hexdigest()
        for i in df["id_origem"]
    ]
    novos = set(df["hash_novo"])

    tabela_bronze, col_bronze, _ = cfg["camadas"][0]
    with engine.connect() as conn:
        no_banco = set(pd.read_sql(
            f"SELECT {col_bronze} FROM {tabela_bronze}", conn)[col_bronze])

    casam = df[df["hash_antigo"].isin(no_banco)]
    nao_casam = df[~df["hash_antigo"].isin(no_banco)]

    print(f"   casam com o banco         : {len(casam)}")
    print(f"   na planilha e nao no banco: {len(nao_casam)}  "
          f"(entram como novos na proxima carga)")

    # Orfaos POR CAMADA, e nao so na bronze. A silver pode ter linhas
    # que a bronze ja nao tem - foi o caso do Itau, com nove -, e olhar
    # so a bronze as deixaria para tras.
    print("\n   orfaos, camada a camada (serao REMOVIDOS):")
    orfaos_por_camada = {}
    with engine.connect() as conn:
        for tabela, coluna, escopo in cfg["camadas"]:
            if tabela == GOLD_COMPARTILHADA:
                continue  # limpa no fim, pela regra geral
            onde = f" WHERE {escopo}" if escopo else ""
            atual = set(pd.read_sql(
                f"SELECT {coluna} FROM {tabela}{onde}", conn)[coluna])
            sobrando = atual - set(df["hash_antigo"]) - novos
            orfaos_por_camada[tabela] = sobrando
            print(f"     {tabela:<34} {len(sobrando)}")

    todos_orfaos = set().union(*orfaos_por_camada.values()) if orfaos_por_camada \
        else set()

    if not aplicar:
        print("\n   [SIMULACAO] nada foi alterado. Use --aplicar para executar.")
        return todos_orfaos

    pares = [{"novo": n, "antigo": a, "id": i} for n, a, i in
             zip(casam["hash_novo"], casam["hash_antigo"], casam["id_origem"])]

    with engine.begin() as conn:
        for tabela, coluna, escopo in cfg["camadas"]:
            onde = f" AND {escopo}" if escopo else ""
            conn.execute(
                text(f"UPDATE {tabela} SET {coluna} = :novo "
                     f"WHERE {coluna} = :antigo{onde}"), pares)
            print(f"   hash reescrito em {tabela}")

        conn.execute(
            text(f"UPDATE {cfg['id_em']} SET ds_id_origem = :id "
                 f"WHERE hash_negocio = :novo"), pares)
        print(f"   ds_id_origem preenchido em {cfg['id_em']}")

        # Da camada mais baixa para a mais alta.
        for tabela, coluna, escopo in reversed(cfg["camadas"]):
            sobrando = orfaos_por_camada.get(tabela)
            if not sobrando:
                continue
            onde = f" AND {escopo}" if escopo else ""
            r = conn.execute(
                text(f"DELETE FROM {tabela} WHERE {coluna} = :h{onde}"),
                [{"h": h} for h in sobrando])
            print(f"   {r.rowcount} orfaos removidos de {tabela}")

    print("   OK")
    return todos_orfaos


def limpa_gold(engine, aplicar: bool, orfaos_silver: set) -> None:
    """
    Remove da gold o que nao tem par em nenhuma silver.

    Feito uma vez no fim, e nao dentro de cada base, porque
    gold.fato_movto_financ recebe Itau, cartao XP e Nubank na mesma
    tabela. A regra "sem par em nenhuma silver" nao precisa saber de
    qual origem a linha veio, e por isso nao tem como atingir o Nubank
    por engano.
    """
    condicao = f"""
        FROM {GOLD_COMPARTILHADA} f
        WHERE NOT EXISTS (SELECT 1 FROM silver.itau_movimentacao s
                           WHERE s.hash_negocio = f.HASH_NEGOCIO)
          AND NOT EXISTS (SELECT 1 FROM silver.cartao_movimentacao s
                           WHERE s.hash_negocio = f.HASH_NEGOCIO)
    """
    print(f"\n{'=' * 66}\n== {GOLD_COMPARTILHADA}")
    with engine.connect() as conn:
        quantos = conn.execute(text(f"SELECT COUNT(*) {condicao}")).scalar()

        if not aplicar:
            # Na simulacao a silver ainda esta cheia, entao a consulta
            # acima devolve zero e daria a impressao de que nada seria
            # apagado - para depois apagar dezenove. O numero honesto e
            # o que sobraria DEPOIS da limpeza da silver: as linhas de
            # gold cujo hash esta entre os orfaos que serao removidos.
            previsto = quantos
            if orfaos_silver:
                previsto += conn.execute(
                    text(f"SELECT COUNT(*) FROM {GOLD_COMPARTILHADA} "
                         f"WHERE HASH_NEGOCIO IN :h").bindparams(
                             sqlalchemy.bindparam("h", expanding=True)),
                    {"h": list(orfaos_silver)}).scalar()
            print(f"   linhas que ficarao sem par apos limpar a silver: "
                  f"{previsto}")
            if previsto:
                print("   [SIMULACAO] seriam removidas.")
            return

    print(f"   linhas sem par em nenhuma silver: {quantos}")
    if not quantos:
        return

    with engine.begin() as conn:
        r = conn.execute(text(f"DELETE f {condicao}"))
    print(f"   {r.rowcount} removidas")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra a chave de negocio das bases de cadastro manual")
    parser.add_argument("--aplicar", action="store_true",
                        help="executa de verdade (sem isso, so simula)")
    parser.add_argument("--base", choices=sorted(BASES),
                        help="migra apenas uma das bases")
    args = parser.parse_args()

    if not args.aplicar:
        print("MODO SIMULACAO - nada sera alterado.")

    engine = get_engine()
    orfaos = set()
    for nome, cfg in BASES.items():
        if args.base and nome != args.base:
            continue
        orfaos |= migra(nome, cfg, engine, args.aplicar)

    # So faz sentido depois das duas silvers limpas: se rodar com uma
    # base de fora, a gold ainda tem par para as linhas da outra.
    if not args.base:
        limpa_gold(engine, args.aplicar, orfaos)

    if args.aplicar:
        print("\nAgora rode as cargas normalmente: elas devem reportar "
              "+0 novos, 0 atualizados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
