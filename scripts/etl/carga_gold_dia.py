"""
Carga da camada Gold - meu dia.

Le silver.dia_registro e grava nos dois fatos:

    gold.fato_dia         um retrato por dia, tudo lado a lado
    gold.fato_dia_habito  uma linha por dia POR HABITO

Sao a mesma informacao em dois formatos, e cada um responde uma
pergunta que o outro nao responde bem: o largo permite cruzar habitos
entre si e somar litros de agua; o longo permite um unico grafico de
aderencia para todas as perguntas do formulario.

A REGRA DE ADERENCIA NAO ESTA AQUI. Ela vive em gold.dim_habito, nas
colunas DS_RESPOSTA_DESEJADA e FL_APURA_ADERENCIA, e esta carga apenas
a aplica. Mudar de ideia sobre o que conta como meta - decidir que a
ceia e opcional, por exemplo - e um UPDATE na dimensao, nao uma
alteracao de codigo.

Uso:
    python carga_gold_dia.py
    python carga_gold_dia.py --resumo
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from util_dados import (  # noqa: E402
    aplica_flags, detecta_alteracoes, registra_carga, valor_sql,
)

_INICIO = time.monotonic()

# Liga cada habito da dimensao a coluna da silver que o responde. Vive
# no codigo porque e mapeamento tecnico, e nao regra de negocio: o que
# muda com frequencia - o que conta como meta - esta na dimensao.
COLUNA_DO_HABITO = {
    "Água": "vl_agua_litros",
    "Treino": "fl_treino",
    "Cardio": "fl_cardio",
    "Café da manhã": "ds_cafe_manha",
    "Almoço": "ds_almoco",
    "Lanche": "ds_lanche",
    "Janta": "ds_janta",
    "Ceia": "ds_ceia",
    "Dia produtivo": "ds_dia_produtivo",
    "Trabalho": "fl_trabalho",
    "Nina em casa": "fl_nina_em_casa",
    "Estresse": "fl_estresse",
    "Lazer": "fl_lazer",
}

COLUNAS_DIA = [
    "SK_DATA", "VL_AGUA_LITROS", "FL_META_AGUA", "NR_REFEICOES_FEITAS",
    "NR_REFEICOES_JACA", "NR_HABITOS_ADERENTES", "NR_HABITOS_APURADOS",
    "FL_TREINO", "FL_CARDIO", "FL_TRABALHO", "FL_NINA_EM_CASA", "FL_ESTRESSE",
    "FL_LAZER", "DS_DIA_PRODUTIVO", "NR_DIAS_ATRASO", "FL_DATA_SUSPEITA",
]
COLUNAS_HABITO = ["SK_DATA", "SK_HABITO", "DS_RESPOSTA", "VL_MEDIDA",
                  "FL_ADERENCIA", "FL_RESPONDIDO"]

# O habito medido em numero, e nao em sim/nao. Nomeado aqui porque a
# carga precisa saber de qual deles sai FL_META_AGUA no fato largo.
HABITO_AGUA = "Água"


def _sk_data(valor, suspeita: bool) -> int:
    """
    Chave do calendario. Data implausivel vira -1.

    O calendario cobre 2015 a 2035; as duas respostas com ano digitado
    errado ficariam fora e quebrariam a chave estrangeira. Apontar para
    o membro "Nao informado" as mantem visiveis no fato, com o defeito
    explicito, em vez de descarta-las em silencio.
    """
    if suspeita or valor is None or pd.isna(valor):
        return -1
    return int(pd.Timestamp(valor).strftime("%Y%m%d"))


def _resposta(valor) -> str | None:
    """Uniformiza bit e texto na mesma escala de resposta."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    if isinstance(valor, bool):
        return "SIM" if valor else "NAO"
    texto = str(valor).strip()
    return texto or None


def monta_habitos(dados: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """Desempilha o dia em uma linha por habito, aplicando a regra da dimensao."""
    linhas = []
    for _, h in dim.iterrows():
        coluna = COLUNA_DO_HABITO.get(h["NM_HABITO"])
        if coluna is None:
            print(f"  AVISO: habito '{h['NM_HABITO']}' nao tem coluna mapeada "
                  f"em COLUNA_DO_HABITO - ficou sem linhas no fato")
            continue

        # NULL do banco chega como NaN, e NaN E TRUTHY: testar so a
        # verdade do campo faria uma meta inexistente parecer definida.
        meta = h["VL_META_MINIMA"]
        meta = None if pd.isna(meta) else float(meta)
        desejada = h["DS_RESPOSTA_DESEJADA"]
        desejada = None if pd.isna(desejada) else str(desejada).strip().upper()
        apura = bool(h["FL_APURA_ADERENCIA"])

        numerico = meta is not None
        valores = pd.to_numeric(dados[coluna], errors="coerce") if numerico else None
        respostas = (
            valores.map(lambda v: None if pd.isna(v)
                        else f"{v:.1f}".replace(".", ",") + f" {h['DS_UNIDADE']}")
            if numerico else dados[coluna].map(_resposta)
        )

        bloco = pd.DataFrame({
            "HASH_NEGOCIO_DIA": dados["hash_negocio"],
            "SK_DATA": [_sk_data(d, s) for d, s in
                        zip(dados["dt_referencia"], dados["fl_data_suspeita"])],
            "SK_HABITO": int(h["SK_HABITO"]),
            "DS_RESPOSTA": respostas,
            "VL_MEDIDA": valores if numerico else None,
            "FL_RESPONDIDO": respostas.notna(),
        })

        # Duas formas de aderir: alcancar um limiar, ou dar a resposta
        # esperada. Qual delas vale sai da dimensao, nao daqui.
        if apura and numerico:
            bloco["FL_ADERENCIA"] = [
                None if pd.isna(v) else bool(v >= meta) for v in valores
            ]
        elif apura and desejada:
            bloco["FL_ADERENCIA"] = [
                None if r is None else r == desejada for r in respostas
            ]
        else:
            bloco["FL_ADERENCIA"] = None

        linhas.append(bloco)

    # HASH_NEGOCIO_DIA sobrevive no resultado: e por ele que a nota do
    # dia e contada em monta_dia, garantindo que as duas tabelas saiam
    # da mesma regra. Quem chama descarta a coluna depois.
    fato = pd.concat(linhas, ignore_index=True)
    fato["HASH_NEGOCIO"] = [
        hashlib.sha256(f"{d}|{h}".encode("utf-8")).hexdigest()
        for d, h in zip(fato["HASH_NEGOCIO_DIA"], fato["SK_HABITO"])
    ]

    for coluna in COLUNAS_HABITO:
        fato[coluna] = fato[coluna].map(valor_sql)
    fato = aplica_flags(fato)
    return fato


def monta_dia(dados: pd.DataFrame, habitos: pd.DataFrame,
              sk_agua: int | None) -> pd.DataFrame:
    fato = pd.DataFrame({"HASH_NEGOCIO": dados["hash_negocio"]})

    fato["SK_DATA"] = [_sk_data(d, s) for d, s in
                       zip(dados["dt_referencia"], dados["fl_data_suspeita"])]
    fato["VL_AGUA_LITROS"] = dados["vl_agua_litros"]

    # Vem do fato longo, e nao de uma comparacao repetida aqui: assim a
    # meta e aplicada UMA vez, e as duas tabelas nao podem divergir se
    # o limiar mudar na dimensao.
    if sk_agua is not None:
        agua = habitos[habitos["SK_HABITO"] == sk_agua]
        fato["FL_META_AGUA"] = fato["HASH_NEGOCIO"].map(
            dict(zip(agua["HASH_NEGOCIO_DIA"], agua["FL_ADERENCIA"])))
    else:
        fato["FL_META_AGUA"] = None
    fato["NR_REFEICOES_FEITAS"] = dados["nr_refeicoes_feitas"]
    fato["NR_REFEICOES_JACA"] = dados["nr_refeicoes_jaca"]

    for destino, origem in (("FL_TREINO", "fl_treino"),
                            ("FL_CARDIO", "fl_cardio"),
                            ("FL_TRABALHO", "fl_trabalho"),
                            ("FL_NINA_EM_CASA", "fl_nina_em_casa"),
                            ("FL_ESTRESSE", "fl_estresse"),
                            ("FL_LAZER", "fl_lazer")):
        fato[destino] = dados[origem]

    fato["DS_DIA_PRODUTIVO"] = dados["ds_dia_produtivo"]
    fato["NR_DIAS_ATRASO"] = dados["nr_dias_atraso"]
    fato["FL_DATA_SUSPEITA"] = dados["fl_data_suspeita"]

    return _acrescenta_nota(fato, habitos)


def _acrescenta_nota(fato: pd.DataFrame, habitos: pd.DataFrame) -> pd.DataFrame:
    """
    Traz a nota do dia do fato longo para o largo.

    Contada aqui e nao no Power BI para que a nota seja a mesma em
    qualquer ferramenta que leia a tabela - e para que ela nasca da
    MESMA regra que alimenta o fato de habitos, sem risco de as duas
    contas divergirem.
    """
    # FL_ADERENCIA agora e 'S' ou 'N', e nao mais bit: somar a coluna
    # direto concatenaria texto. A contagem passa a ser da letra, e o
    # nulo continua significando "nao apurado" - virar 'N' aqui diria
    # que a meta nao foi cumprida, quando ela nem foi medida.
    nota = (habitos.assign(_aderiu=(habitos["FL_ADERENCIA"] == "S"),
                           _apurado=habitos["FL_ADERENCIA"].notna())
            .groupby("HASH_NEGOCIO_DIA")[["_aderiu", "_apurado"]].sum())

    fato["NR_HABITOS_ADERENTES"] = (
        fato["HASH_NEGOCIO"].map(nota["_aderiu"]).fillna(0).astype(int))
    fato["NR_HABITOS_APURADOS"] = (
        fato["HASH_NEGOCIO"].map(nota["_apurado"]).fillna(0).astype(int))

    for coluna in COLUNAS_DIA:
        fato[coluna] = fato[coluna].map(valor_sql)
    fato = aplica_flags(fato)
    return fato


def _sincroniza(conn, tabela: str, fato: pd.DataFrame,
                colunas: list[str]) -> tuple[int, int]:
    atual = pd.read_sql(
        f"SELECT HASH_NEGOCIO, {', '.join(colunas)} FROM gold.{tabela}", conn)

    novos = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
    if len(novos):
        novos.to_sql(tabela, conn, schema="gold", if_exists="append", index=False)

    alterados = detecta_alteracoes(atual, fato, "HASH_NEGOCIO", colunas)
    if alterados:
        sets = ", ".join(f"{c} = :{c}" for c in colunas)
        conn.execute(
            text(f"UPDATE gold.{tabela} SET {sets}, DT_CARGA = SYSDATETIME() "
                 f"WHERE HASH_NEGOCIO = :chave"),
            alterados,
        )
    return len(novos), len(alterados)


def resumo(engine) -> None:
    print("\n== Agua: litros por dia e dias na meta ==")
    print(pd.read_sql("""
        SELECT d.NR_ANO AS ano, COUNT(*) AS dias,
               CAST(AVG(f.VL_AGUA_LITROS) AS decimal(4,2)) AS media_litros,
               CAST(MIN(f.VL_AGUA_LITROS) AS decimal(4,2)) AS minimo,
               CAST(MAX(f.VL_AGUA_LITROS) AS decimal(4,2)) AS maximo,
               SUM(CASE WHEN f.FL_META_AGUA = 'S' THEN 1.0 WHEN f.FL_META_AGUA = 'N' THEN 0.0 END) AS dias_na_meta,
               CAST(100.0 * AVG(CAST(f.FL_META_AGUA AS float))
                    AS decimal(4,1)) AS pct_na_meta
        FROM gold.fato_dia f
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE f.FL_DATA_SUSPEITA = 'N'
        GROUP BY d.NR_ANO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Agua por mes, os 12 ultimos ==")
    print(pd.read_sql("""
        SELECT TOP 12 d.NM_ANO_MES AS mes, COUNT(*) AS dias,
               CAST(AVG(f.VL_AGUA_LITROS) AS decimal(4,2)) AS media_litros,
               CAST(100.0 * AVG(CAST(f.FL_META_AGUA AS float))
                    AS decimal(4,1)) AS pct_na_meta
        FROM gold.fato_dia f
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE f.FL_DATA_SUSPEITA = 'N'
        GROUP BY d.NM_ANO_MES ORDER BY 1 DESC
    """, engine).to_string(index=False))

    print("\n== Aderencia por habito (so o que e meta) ==")
    print(pd.read_sql("""
        SELECT h.DS_GRUPO AS grupo, h.NM_HABITO AS habito,
               COUNT(*) AS dias,
               CAST(100.0 * AVG(CAST(f.FL_ADERENCIA AS float))
                    AS decimal(4,1)) AS pct_aderencia
        FROM gold.fato_dia_habito f
        JOIN gold.dim_habito h ON h.SK_HABITO = f.SK_HABITO
        WHERE h.FL_APURA_ADERENCIA = 'S' AND f.FL_RESPONDIDO = 'S'
        GROUP BY h.DS_GRUPO, h.NM_HABITO, h.NR_ORDEM ORDER BY h.NR_ORDEM
    """, engine).to_string(index=False))

    print("\n== Nota do dia por ano (metas cumpridas / metas respondidas) ==")
    print(pd.read_sql("""
        SELECT d.NR_ANO AS ano, COUNT(*) AS dias,
               CAST(100.0 * SUM(f.NR_HABITOS_ADERENTES)
                    / NULLIF(SUM(f.NR_HABITOS_APURADOS), 0)
                    AS decimal(4,1)) AS nota,
               CAST(AVG(f.VL_AGUA_LITROS) AS decimal(4,2)) AS agua_litros,
               CAST(AVG(CAST(f.NR_REFEICOES_JACA AS float))
                    AS decimal(4,2)) AS jaca_por_dia
        FROM gold.fato_dia f
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE f.FL_DATA_SUSPEITA = 'N'
        GROUP BY d.NR_ANO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== O contexto muda o habito? (treino por dia de trabalho) ==")
    print(pd.read_sql("""
        SELECT CASE WHEN FL_TRABALHO = 'S' THEN 'dia de trabalho'
                    ELSE 'folga' END AS contexto,
               COUNT(*) AS dias,
               CAST(100.0 * AVG(CAST(FL_TREINO AS float)) AS decimal(4,1)) AS pct_treino,
               CAST(AVG(VL_AGUA_LITROS) AS decimal(4,2)) AS agua_litros,
               CAST(AVG(CAST(NR_REFEICOES_JACA AS float)) AS decimal(4,2)) AS jaca_dia
        FROM gold.fato_dia WHERE FL_DATA_SUSPEITA = 'N' AND FL_TRABALHO IS NOT NULL
        GROUP BY CASE WHEN FL_TRABALHO = 'S' THEN 'dia de trabalho' ELSE 'folga' END
        ORDER BY 1
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold do diario meu dia")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    dados = pd.read_sql("SELECT * FROM silver.dia_registro", engine)
    print(f"Lidos {len(dados)} dias da silver")

    with engine.begin() as conn:
        dim = pd.read_sql(
            "SELECT SK_HABITO, NM_HABITO, DS_RESPOSTA_DESEJADA, VL_META_MINIMA, "
            "DS_UNIDADE, FL_APURA_ADERENCIA "
            "FROM gold.dim_habito WHERE SK_HABITO > 0 ORDER BY NR_ORDEM", conn)

        habitos = monta_habitos(dados, dim)

        so_agua = dim[dim["NM_HABITO"] == HABITO_AGUA]
        sk_agua = int(so_agua["SK_HABITO"].iloc[0]) if len(so_agua) else None
        if sk_agua is None:
            print(f"  AVISO: habito '{HABITO_AGUA}' nao existe na dimensao - "
                  f"FL_META_AGUA ficou nulo no fato_dia")

        dia = monta_dia(dados, habitos, sk_agua)
        habitos = habitos.drop(columns="HASH_NEGOCIO_DIA")

        novos_dia, alt_dia = _sincroniza(conn, "fato_dia", dia, COLUNAS_DIA)
        novos_hab, alt_hab = _sincroniza(conn, "fato_dia_habito", habitos,
                                         COLUNAS_HABITO)

    print(f"  fato_dia       : +{novos_dia} novos, {alt_dia} atualizados")
    print(f"  fato_dia_habito: +{novos_hab} novos, {alt_hab} atualizados")
    registra_carga(engine, "gold.fato_dia", novos_dia, alt_dia, inicio=_INICIO)
    registra_carga(engine, "gold.fato_dia_habito", novos_hab, alt_hab,
                   inicio=_INICIO)

    print("\n== Conferencia silver x gold ==")
    print(pd.read_sql(f"""
        SELECT (SELECT COUNT(*) FROM silver.dia_registro) AS silver_dias,
               (SELECT COUNT(*) FROM gold.fato_dia) AS gold_dias,
               (SELECT COUNT(*) FROM gold.fato_dia_habito) AS gold_habitos,
               (SELECT COUNT(*) FROM silver.dia_registro) * {len(dim)} AS esperado,
               (SELECT CAST(SUM(vl_agua_litros) AS decimal(10,2))
                  FROM silver.dia_registro) AS agua_silver,
               (SELECT CAST(SUM(VL_AGUA_LITROS) AS decimal(10,2))
                  FROM gold.fato_dia) AS agua_gold
    """, engine).to_string(index=False))

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
