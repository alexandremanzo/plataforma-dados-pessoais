"""
Carga da camada Silver - meu dia.

Le bronze.dia_registro, tipa e padroniza, grava em silver.dia_registro.

O que esta camada decide:

- As perguntas de sim/nao viram bit. As refeicoes NAO viram, porque
  tem tres estados: SIM, NAO e JACA - refeicao feita fora do plano
  alimentar. Espremer isso num booleano juntaria "pulei a refeicao" com
  "comi fora da dieta", que sao o oposto uma da outra.

- Data implausivel e marcada, nao corrigida nem descartada. O resto da
  resposta continua valido, e adivinhar a data certa seria inventar
  dado. A correcao acontece no formulario, e o upsert a propaga.

Uso:
    python carga_silver_dia.py
    python carga_silver_dia.py --revisar   # o que merece atencao
"""

import argparse
import time
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import detecta_alteracoes, valor_sql, registra_carga  # noqa: E402

_INICIO = time.monotonic()

REFEICOES = ["ds_cafe_manha", "ds_almoco", "ds_lanche", "ds_janta", "ds_ceia"]
BOOLEANOS = {
    "fl_treino": "ds_treino",
    "fl_cardio": "ds_cardio",
    "fl_trabalho": "ds_trabalho",
    "fl_nina_em_casa": "ds_nina_em_casa",
    "fl_estresse": "ds_estresse",
    "fl_lazer": "ds_lazer",
}

# Faixa em que uma data de diario e plausivel. O inicio e anterior a
# primeira resposta com folga; o fim e amanha, porque o formulario e
# respondido no dia seguinte e a virada de fuso pode adiantar um dia.
DATA_MINIMA = pd.Timestamp("2020-01-01")

DERIVADAS = [
    "dt_referencia", "dt_resposta", "nr_dias_atraso", "fl_data_suspeita",
    "fl_treino", "fl_cardio", "vl_agua_litros",
    *REFEICOES, "nr_refeicoes_feitas", "nr_refeicoes_jaca",
    "ds_dia_produtivo", "fl_trabalho", "fl_nina_em_casa", "fl_estresse", "fl_lazer",
]


def resposta(valor) -> str | None:
    """
    Padroniza uma resposta do formulario.

    Tira acento e sobe para maiuscula, o que resolve de uma vez a
    duplicidade do cardio: a opcao do formulario foi reescrita em 2024
    e o negativo passou a conviver como "Nao" e "Nao" com til. Sem
    isso, o mesmo habito teria tres respostas distintas.
    """
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return sem_acento.upper()


def _sim(valor) -> bool | None:
    r = resposta(valor)
    return None if r is None else r == "SIM"


def transforma(bronze: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({"hash_negocio": bronze["hash_negocio"]})

    referencia = pd.to_datetime(bronze["ds_data"], errors="coerce")
    resposta_em = pd.to_datetime(bronze["ds_carimbo"], dayfirst=True, errors="coerce")

    df["dt_referencia"] = referencia.dt.date
    df["dt_resposta"] = resposta_em
    df["nr_dias_atraso"] = (resposta_em.dt.normalize() - referencia).dt.days

    limite = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    df["fl_data_suspeita"] = referencia.isna() | (referencia < DATA_MINIMA) | (
        referencia > limite)

    # O atraso so faz sentido quando a data e confiavel: com 1900 ou
    # 3025 no campo, o numero seria absurdo e contaminaria a media.
    df.loc[df["fl_data_suspeita"], "nr_dias_atraso"] = None

    for destino, origem in BOOLEANOS.items():
        df[destino] = bronze[origem].map(_sim)

    df["vl_agua_litros"] = pd.to_numeric(
        bronze["ds_agua_litros"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce")

    for coluna in REFEICOES:
        df[coluna] = bronze[coluna].map(resposta)
    df["nr_refeicoes_feitas"] = (df[REFEICOES] == "SIM").sum(axis=1)
    df["nr_refeicoes_jaca"] = (df[REFEICOES] == "JACA").sum(axis=1)

    df["ds_dia_produtivo"] = bronze["ds_dia_produtivo"].map(resposta)

    for coluna in DERIVADAS:
        df[coluna] = df[coluna].map(valor_sql)
    return df


def sincroniza(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as conn:
        atual = pd.read_sql(
            "SELECT hash_negocio, " + ", ".join(DERIVADAS)
            + " FROM silver.dia_registro", conn)

        novos = df[~df["hash_negocio"].isin(set(atual["hash_negocio"]))]
        if len(novos):
            novos.to_sql("dia_registro", conn, schema="silver",
                         if_exists="append", index=False)

        alterados = detecta_alteracoes(atual, df, "hash_negocio", DERIVADAS)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in DERIVADAS)
            conn.execute(
                text(f"UPDATE silver.dia_registro SET {sets}, "
                     f"dt_carga = SYSDATETIME() WHERE hash_negocio = :chave"),
                alterados,
            )
    return len(novos), len(alterados)


def revisar(engine) -> None:
    print("\n== Respostas com data implausivel ==")
    print(pd.read_sql("""
        SELECT dt_resposta AS respondido_em, dt_referencia AS data_digitada
        FROM silver.dia_registro WHERE fl_data_suspeita = 1 ORDER BY dt_resposta
    """, engine).to_string(index=False))

    print("\n== Cobertura por mes (dias com resposta) ==")
    print(pd.read_sql("""
        SELECT FORMAT(dt_referencia, 'yyyy-MM') AS mes, COUNT(*) AS respostas,
               DAY(EOMONTH(MIN(dt_referencia))) AS dias_no_mes
        FROM silver.dia_registro WHERE fl_data_suspeita = 0
        GROUP BY FORMAT(dt_referencia, 'yyyy-MM')
        HAVING COUNT(*) < DAY(EOMONTH(MIN(dt_referencia)))
        ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Habitos por ano ==")
    print(pd.read_sql("""
        SELECT YEAR(dt_referencia) AS ano, COUNT(*) AS dias,
               CAST(AVG(vl_agua_litros) AS decimal(4,2)) AS agua_litros,
               CAST(100.0 * AVG(CAST(fl_treino AS float)) AS decimal(4,1)) AS pct_treino,
               CAST(100.0 * AVG(CAST(fl_cardio AS float)) AS decimal(4,1)) AS pct_cardio,
               CAST(AVG(CAST(nr_refeicoes_jaca AS float)) AS decimal(4,2)) AS jaca_dia,
               CAST(100.0 * AVG(CAST(fl_estresse AS float)) AS decimal(4,1)) AS pct_estresse,
               CAST(100.0 * AVG(CAST(fl_lazer AS float)) AS decimal(4,1)) AS pct_lazer
        FROM silver.dia_registro WHERE fl_data_suspeita = 0
        GROUP BY YEAR(dt_referencia) ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Confiabilidade: atraso entre o dia e a resposta ==")
    print(pd.read_sql("""
        SELECT CASE WHEN nr_dias_atraso <= 1 THEN '0-1 dia'
                    WHEN nr_dias_atraso <= 3 THEN '2-3 dias'
                    WHEN nr_dias_atraso <= 7 THEN '4-7 dias'
                    ELSE 'mais de 7 dias' END AS atraso,
               COUNT(*) AS respostas
        FROM silver.dia_registro WHERE nr_dias_atraso IS NOT NULL
        GROUP BY CASE WHEN nr_dias_atraso <= 1 THEN '0-1 dia'
                      WHEN nr_dias_atraso <= 3 THEN '2-3 dias'
                      WHEN nr_dias_atraso <= 7 THEN '4-7 dias'
                      ELSE 'mais de 7 dias' END
        ORDER BY 2 DESC
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga silver do diario meu dia")
    parser.add_argument("--revisar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    bronze = pd.read_sql("SELECT * FROM bronze.dia_registro", engine)
    print(f"Lidas {len(bronze)} respostas da bronze")

    inseridos, atualizados = sincroniza(transforma(bronze), engine)
    print(f"  inseridos  : {inseridos}")
    print(f"  atualizados: {atualizados}")
    registra_carga(engine, "silver.dia_registro", inseridos, atualizados, inicio=_INICIO)

    with engine.connect() as conn:
        total, suspeitas = conn.execute(text("""
            SELECT COUNT(*), SUM(CAST(fl_data_suspeita AS int))
            FROM silver.dia_registro
        """)).fetchone()
    print(f"Total em silver.dia_registro: {total} ({suspeitas} com data suspeita)")

    if args.revisar:
        revisar(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
