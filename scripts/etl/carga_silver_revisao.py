"""
Carga da camada Silver - plano de revisao do fabricante.

Tipa o que a bronze guardou como texto: "10000" vira int, "12 meses"
vira 12, e a acao cai num dominio de tres valores.

POR QUE O INTERVALO EM MESES IMPORTA TANTO. A previsao de manutencao
so sabia quilometragem, e a quilometragem so entra na base quando o
carro vai a oficina - por isso, logo depois de uma visita, tudo
aparecia "Em dia". O tempo nao depende de ninguem anotar nada: ele
corre sozinho. E a coluna que faz o alerta virar alerta.

Uso:
    python carga_silver_revisao.py
"""

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import detecta_alteracoes, registra_carga  # noqa: E402

_INICIO = time.monotonic()

DERIVADAS = ["nm_modelo", "nm_item", "nm_sistema", "nr_intervalo_km",
             "nr_intervalo_meses", "ds_acao", "ds_especificacao"]

# A origem escreve "Inspeção / Troca" na correia Poly-V. Vira Inspeção:
# o que esta AGENDADO e a inspecao - a troca e consequencia dela, e so
# acontece se a inspecao reprovar. Registrar como troca faria a correia
# aparecer como item vencido a cada 60 mil km sem que nada indique que
# ela precisa ser trocada.
ACAO = {
    "troca": "Troca",
    "inspecao": "Inspeção",
    "servico": "Serviço",
    "inspecao / troca": "Inspeção",
}

_SO_DIGITOS = re.compile(r"\d+")


def _inteiro(valor):
    """
    Primeiro numero do texto, ou nulo.

    Serve tanto para "10000" quanto para "12 meses" - o formato da
    coluna de tempo na origem.
    """
    if valor is None or pd.isna(valor):
        return None
    achado = _SO_DIGITOS.search(str(valor))
    return int(achado.group()) if achado else None


def _acao(valor):
    if valor is None or pd.isna(valor):
        return None
    chave = (str(valor).strip().lower()
             .replace("ç", "c").replace("ã", "a").replace("õ", "o")
             .replace("é", "e").replace("í", "i").replace("ú", "u"))
    if chave not in ACAO:
        print(f"  AVISO: acao {valor!r} nao esta no dominio conhecido - ficou nula.")
        print(f"         Dominio: {sorted(set(ACAO.values()))}. "
              f"Se for legitima, acrescente ao dicionario ACAO deste script.")
    return ACAO.get(chave)


def transforma(bronze: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "hash_negocio": bronze["hash_negocio"],
        "nm_modelo": bronze["ds_modelo"],
        "nm_item": bronze["ds_item"],
        "nm_sistema": bronze["ds_sistema"],
        "nr_intervalo_km": bronze["ds_intervalo_km"].map(_inteiro),
        "nr_intervalo_meses": bronze["ds_intervalo_tempo"].map(_inteiro),
        "ds_acao": bronze["ds_acao"].map(_acao),
        "ds_especificacao": bronze["ds_especificacao"],
    })
    # Nulo de verdade, e nao NaN: um NaN em coluna de texto faz o
    # driver ODBC recusar o comando inteiro.
    for col in ("nr_intervalo_km", "nr_intervalo_meses"):
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            f"SELECT hash_negocio, {', '.join(DERIVADAS)} "
            f"FROM silver.auto_revisao_programada", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("auto_revisao_programada", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.auto_revisao_programada SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def main() -> int:
    argparse.ArgumentParser(
        description="Carga silver do plano de revisao").parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.auto_revisao_programada", engine)
    print(f"Lidos {len(bronze)} itens da bronze")

    inseridos, atualizados = sincroniza(transforma(bronze), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.auto_revisao_programada",
                   inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        print()
        print(pd.read_sql("""
            SELECT ds_acao AS acao, COUNT(*) AS itens,
                   MIN(nr_intervalo_km) AS km_min, MAX(nr_intervalo_km) AS km_max,
                   MIN(nr_intervalo_meses) AS meses_min,
                   MAX(nr_intervalo_meses) AS meses_max
            FROM silver.auto_revisao_programada
            GROUP BY ds_acao ORDER BY itens DESC
        """, conn).to_string(index=False))

        # Um item sem nenhum dos dois intervalos nao entra em previsao
        # nenhuma - ele nao seria alertado nunca e some sem aviso.
        mudos = pd.read_sql("""
            SELECT nm_item, ds_acao FROM silver.auto_revisao_programada
            WHERE nr_intervalo_km IS NULL AND nr_intervalo_meses IS NULL
        """, conn)
        if len(mudos):
            print(f"\n== {len(mudos)} itens sem intervalo em km NEM em meses ==")
            print("   (nao entram na previsao de vencimento)")
            print(mudos.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
