"""
Carga da camada Gold - manutencao do automovel.

Le silver.auto_manutencao e grava em gold.fato_manutencao_auto,
alimentando gold.dim_veiculo e gold.dim_categoria_auto.

As duas dimensoes sao DERIVADAS e reescritas a cada carga: o veiculo
ganha a quilometragem atual e a marca de ativo, e a categoria ganha o
intervalo vindo da tabela de troca. Nao ha cadastro manual - se um
terceiro carro aparecer na planilha, ele entra sozinho.

gold.vw_manutencao_prevista, criada em 39_gold_revisao.sql, le estas
tabelas e responde o que esta vencendo.

Uso:
    python carga_gold_auto.py
    python carga_gold_auto.py --resumo
"""

import argparse
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

COLUNAS_FATO = [
    "SK_DATA", "SK_VEICULO", "SK_CATEGORIA_MANUTENCAO", "NR_VISITA",
    "NR_KM", "VL_GASTO", "NR_QUANTIDADE", "FL_PREVENTIVA", "DS_TIPO",
    "DS_ITEM", "DS_LOCAL", "DS_OBSERVACAO",
]
ATUALIZAVEIS_VEICULO = ["DT_PRIMEIRA", "DT_ULTIMA", "NR_KM_ATUAL",
                        "NR_VISITAS", "FL_ATIVO"]
ATUALIZAVEIS_CATEGORIA = ["NR_INTERVALO_KM", "FL_TEM_INTERVALO"]


def _chave(valor) -> str:
    """Comparacao alinhada a collation do banco (Latin1_General_CI_AS)."""
    return str(valor).strip().upper() if valor is not None else ""


def _upsert_dimensao(conn, tabela, chave_nome, df, atualizaveis) -> tuple[dict, int, int]:
    """Insere o que falta, atualiza o que mudou, devolve o mapa nome -> SK."""
    sk = "SK_" + ("VEICULO" if tabela == "dim_veiculo" else "CATEGORIA_MANUTENCAO")

    def le():
        return pd.read_sql(
            f"SELECT {sk}, {chave_nome}, {', '.join(atualizaveis)} "
            f"FROM gold.{tabela}", conn)

    existente = le()
    ja_tem = {_chave(n) for n in existente[chave_nome]}
    novas = df[[_chave(n) not in ja_tem for n in df[chave_nome]]]
    if len(novas):
        novas.to_sql(tabela, conn, schema="gold", if_exists="append", index=False)
        existente = le()

    # A dimensao e derivada: quilometragem e contagem de visitas mudam
    # a cada manutencao nova, entao ela precisa ser atualizada e nao so
    # acrescida. Comparado pelo nome, na forma que casa com a collation.
    atual = existente.assign(_k=[_chave(n) for n in existente[chave_nome]])
    novo = df.assign(_k=[_chave(n) for n in df[chave_nome]])
    alterados = detecta_alteracoes(atual, novo, "_k", atualizaveis)
    if alterados:
        sets = ", ".join(f"{c} = :{c}" for c in atualizaveis)
        conn.execute(
            text(f"UPDATE gold.{tabela} SET {sets}, DT_CARGA = SYSDATETIME() "
                 f"WHERE UPPER(LTRIM(RTRIM({chave_nome}))) = :chave"),
            alterados,
        )
        existente = le()

    mapa = {_chave(n): s for s, n in zip(existente[sk], existente[chave_nome])}
    return mapa, len(novas), len(alterados)


ATUALIZAVEIS_REVISAO = ["SK_VEICULO", "SK_CATEGORIA_MANUTENCAO", "NM_ITEM",
                        "NM_SISTEMA", "NR_INTERVALO_KM", "NR_INTERVALO_MESES",
                        "DS_ACAO", "DS_ESPECIFICACAO"]

# Cada lancamento do historico decide a qual item do plano pertence.
# Quando mais de um padrao casa, VENCE O MAIS LONGO: e o que impede
# "filtro de ar" de roubar o lancamento de "filtro de ar condicionado",
# e manda "filtro oleo motor" para o filtro e nao para o oleo.
# A collation acento-insensivel resolve "oleo" contra "óleo".
SQL_ITEM_POR_CATEGORIA = """
WITH evento_item AS (
    SELECT f.SK_CATEGORIA_MANUTENCAO, d.nm_item_plano, d.ds_padrao_item,
           ROW_NUMBER() OVER (PARTITION BY f.SK_MANUTENCAO
                              ORDER BY LEN(d.ds_padrao_item) DESC) AS rn
    FROM gold.fato_manutencao_auto f
    JOIN silver.de_para_item_revisao d
      ON f.DS_ITEM COLLATE Latin1_General_CI_AI
         LIKE '%' + d.ds_padrao_item COLLATE Latin1_General_CI_AI + '%'
)
SELECT nm_item_plano, ds_padrao_item, SK_CATEGORIA_MANUTENCAO, COUNT(*) AS n
FROM evento_item WHERE rn = 1
GROUP BY nm_item_plano, ds_padrao_item, SK_CATEGORIA_MANUTENCAO
"""


def sincroniza_revisao(conn, mapa_veiculo: dict) -> tuple[int, int, list]:
    """
    Grava a regra do fabricante em gold.dim_revisao_programada.

    Devolve (novos, alterados, itens sem lancamento correspondente).

    A CATEGORIA E DEDUZIDA, nao cadastrada: olha em que categoria da
    sua classificacao os lancamentos daquele item costumam cair e
    adota a mais frequente. Item que o historico nunca viu fica com
    -1 e aparece na previsao como "Sem registro" - que e justamente o
    alerta que interessa, e nao uma falha.
    """
    plano = pd.read_sql("SELECT * FROM silver.auto_revisao_programada", conn)
    if plano.empty:
        return 0, 0, []

    # O plano diz "MONTADORA SUV 2017" e a dimensao diz "SUV". Procurar
    # o nome do carro DENTRO do texto do modelo evita uma tabela de
    # configuracao: um plano de outro veiculo acha o dono sozinho.
    reais = {n: s for n, s in mapa_veiculo.items() if int(s) > 0}

    def sk_veiculo(modelo):
        alvo = _chave(modelo)
        for nome, sk in reais.items():
            if nome and nome in alvo:
                return int(sk)
        return None

    plano["SK_VEICULO"] = plano["nm_modelo"].map(sk_veiculo)
    orfaos = plano[plano["SK_VEICULO"].isna()]
    if len(orfaos):
        print(f"  AVISO: {len(orfaos)} itens de plano sem veiculo correspondente "
              f"em gold.dim_veiculo.")
        print(f"         Modelos: {sorted(set(orfaos['nm_modelo']))}")
        print(f"         Conhecidos: {sorted(reais)}. O plano so vale depois que o "
              f"carro aparecer no historico da oficina.")
        plano = plano[plano["SK_VEICULO"].notna()].copy()
    if plano.empty:
        return 0, 0, []

    casamento = pd.read_sql(SQL_ITEM_POR_CATEGORIA, conn)
    dominante = {}
    if len(casamento):
        maior = casamento.sort_values("n", ascending=False).drop_duplicates(
            subset="nm_item_plano")
        dominante = dict(zip(maior["nm_item_plano"], maior["SK_CATEGORIA_MANUTENCAO"]))

        # Padrao que nunca casa e grafia errada no de-para, e nao item
        # que nao existe. Registrar a contagem deixa isso visivel.
        por_padrao = casamento.groupby(
            ["nm_item_plano", "ds_padrao_item"])["n"].sum().reset_index()
        conn.execute(text("UPDATE silver.de_para_item_revisao SET nr_lancamentos = 0"))
        conn.execute(
            text("UPDATE silver.de_para_item_revisao SET nr_lancamentos = :n "
                 "WHERE nm_item_plano = :i AND ds_padrao_item = :p"),
            [{"n": int(r.n), "i": r.nm_item_plano, "p": r.ds_padrao_item}
             for r in por_padrao.itertuples()],
        )

    regra = pd.DataFrame({
        "SK_VEICULO": plano["SK_VEICULO"].astype(int),
        "SK_CATEGORIA_MANUTENCAO": [
            int(dominante.get(i, -1)) for i in plano["nm_item"]],
        "NM_ITEM": plano["nm_item"],
        "NM_SISTEMA": plano["nm_sistema"],
        "NR_INTERVALO_KM": plano["nr_intervalo_km"].map(valor_sql),
        "NR_INTERVALO_MESES": plano["nr_intervalo_meses"].map(valor_sql),
        "DS_ACAO": plano["ds_acao"],
        "DS_ESPECIFICACAO": plano["ds_especificacao"],
        "HASH_NEGOCIO": plano["hash_negocio"],
    })

    atual = pd.read_sql(
        f"SELECT HASH_NEGOCIO, {', '.join(ATUALIZAVEIS_REVISAO)} "
        f"FROM gold.dim_revisao_programada", conn)

    novos = regra[~regra["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
    if len(novos):
        novos.to_sql("dim_revisao_programada", conn, schema="gold",
                     if_exists="append", index=False)

    alterados = detecta_alteracoes(atual, regra, "HASH_NEGOCIO", ATUALIZAVEIS_REVISAO)
    if alterados:
        sets = ", ".join(f"{c} = :{c}" for c in ATUALIZAVEIS_REVISAO)
        conn.execute(
            text(f"UPDATE gold.dim_revisao_programada SET {sets}, "
                 f"DT_CARGA = SYSDATETIME() WHERE HASH_NEGOCIO = :chave"),
            alterados,
        )

    sem_historico = sorted(set(plano["nm_item"]) - set(dominante))
    return len(novos), len(alterados), sem_historico


def monta_veiculos(dados: pd.DataFrame) -> pd.DataFrame:
    v = dados.groupby("nm_veiculo").agg(
        DT_PRIMEIRA=("dt_manutencao", "min"),
        DT_ULTIMA=("dt_manutencao", "max"),
        NR_KM_ATUAL=("nr_km", "max"),
        NR_VISITAS=("nr_visita", "max"),
    ).reset_index().rename(columns={"nm_veiculo": "NM_VEICULO"})

    # Ativo e o de manutencao mais recente. INFERIDO: a planilha nao
    # registra compra nem venda, e o carro que parou de ser mantido e
    # o que foi vendido. Documentado na dimensao.
    v["FL_ATIVO"] = v["DT_ULTIMA"] == v["DT_ULTIMA"].max()

    for c in ATUALIZAVEIS_VEICULO:
        v[c] = v[c].map(valor_sql)
    v = aplica_flags(v)
    return v[["NM_VEICULO", *ATUALIZAVEIS_VEICULO]]


def monta_categorias(dados: pd.DataFrame, intervalos: pd.DataFrame) -> pd.DataFrame:
    mapa = {_chave(c): k for c, k in zip(intervalos["ds_categoria"],
                                         intervalos["nr_intervalo_km"])}
    c = pd.DataFrame({
        "NM_CATEGORIA": sorted(dados["ds_categoria"].dropna().unique())
    })
    c["NR_INTERVALO_KM"] = [mapa.get(_chave(n)) for n in c["NM_CATEGORIA"]]
    c["FL_TEM_INTERVALO"] = c["NR_INTERVALO_KM"].notna()
    c = aplica_flags(c)

    for col in ATUALIZAVEIS_CATEGORIA:
        c[col] = c[col].map(valor_sql)
    return c


def monta_fato(dados, mapa_veiculo, mapa_categoria) -> pd.DataFrame:
    fato = pd.DataFrame({"HASH_NEGOCIO": dados["hash_negocio"]})
    fato["SK_DATA"] = [
        int(pd.Timestamp(d).strftime("%Y%m%d")) for d in dados["dt_manutencao"]
    ]
    fato["SK_VEICULO"] = [
        mapa_veiculo.get(_chave(v), -1) for v in dados["nm_veiculo"]
    ]
    fato["SK_CATEGORIA_MANUTENCAO"] = [
        mapa_categoria.get(_chave(c), -1) for c in dados["ds_categoria"]
    ]
    fato["NR_VISITA"] = dados["nr_visita"]
    fato["NR_KM"] = dados["nr_km"]
    fato["VL_GASTO"] = dados["vl_gasto"]
    fato["NR_QUANTIDADE"] = dados["nr_quantidade"]
    fato["FL_PREVENTIVA"] = dados["fl_preventiva"]
    fato["DS_TIPO"] = dados["ds_tipo"]
    fato["DS_ITEM"] = dados["ds_item"]
    fato["DS_LOCAL"] = dados["ds_local"]
    fato["DS_OBSERVACAO"] = dados["ds_observacao"]

    for coluna in COLUNAS_FATO:
        fato[coluna] = fato[coluna].map(valor_sql)
    fato = aplica_flags(fato)
    return fato


def resumo(engine) -> None:
    print("\n== O QUE ESTA VENCENDO (veiculo em uso) ==")
    print(pd.read_sql("""
        SELECT NM_ITEM AS item, NR_INTERVALO_KM AS intervalo,
               NR_INTERVALO_MESES AS meses, DT_ULTIMA_TROCA,
               NR_KM_RESTANTE AS faltam_km, NR_MESES_RESTANTES AS faltam_meses,
               DS_CRITERIO AS criterio, DS_SITUACAO AS situacao
        FROM gold.vw_manutencao_prevista
        ORDER BY NR_MESES_RESTANTES, NR_KM_RESTANTE
    """, engine).to_string(index=False))

    print("\n== Gasto por veiculo e por ano ==")
    print(pd.read_sql("""
        SELECT v.NM_VEICULO AS veiculo, d.NR_ANO AS ano,
               COUNT(DISTINCT f.NR_VISITA) AS visitas,
               CAST(SUM(f.VL_GASTO) AS decimal(12,2)) AS total
        FROM gold.fato_manutencao_auto f
        JOIN gold.dim_veiculo v ON v.SK_VEICULO = f.SK_VEICULO
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        GROUP BY v.NM_VEICULO, d.NR_ANO ORDER BY 1, 2
    """, engine).to_string(index=False))

    print("\n== Custo por mil km rodados ==")
    print(pd.read_sql("""
        SELECT v.NM_VEICULO AS veiculo,
               MIN(f.NR_KM) AS km_inicial, MAX(f.NR_KM) AS km_final,
               MAX(f.NR_KM) - MIN(f.NR_KM) AS km_rodados,
               CAST(SUM(f.VL_GASTO) AS decimal(12,2)) AS gasto,
               CAST(1000.0 * SUM(f.VL_GASTO)
                    / NULLIF(MAX(f.NR_KM) - MIN(f.NR_KM), 0)
                    AS decimal(10,2)) AS por_mil_km
        FROM gold.fato_manutencao_auto f
        JOIN gold.dim_veiculo v ON v.SK_VEICULO = f.SK_VEICULO
        GROUP BY v.NM_VEICULO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Maiores categorias ==")
    print(pd.read_sql("""
        SELECT TOP 10 c.NM_CATEGORIA AS categoria, COUNT(*) AS itens,
               CAST(SUM(f.VL_GASTO) AS decimal(12,2)) AS total,
               CASE WHEN c.FL_TEM_INTERVALO = 'S' THEN 'preventiva'
                    ELSE 'corretiva' END AS natureza
        FROM gold.fato_manutencao_auto f
        JOIN gold.dim_categoria_auto c
          ON c.SK_CATEGORIA_MANUTENCAO = f.SK_CATEGORIA_MANUTENCAO
        GROUP BY c.NM_CATEGORIA, c.FL_TEM_INTERVALO ORDER BY 3 DESC
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold da manutencao auto")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    dados = pd.read_sql("SELECT * FROM silver.auto_manutencao", engine)
    intervalos = pd.read_sql("SELECT * FROM silver.auto_intervalo_troca", engine)
    print(f"Lidos {len(dados)} lancamentos da silver")

    with engine.begin() as conn:
        mapa_v, novos_v, alt_v = _upsert_dimensao(
            conn, "dim_veiculo", "NM_VEICULO",
            monta_veiculos(dados), ATUALIZAVEIS_VEICULO)
        mapa_c, novos_c, alt_c = _upsert_dimensao(
            conn, "dim_categoria_auto", "NM_CATEGORIA",
            monta_categorias(dados, intervalos), ATUALIZAVEIS_CATEGORIA)

        fato = monta_fato(dados, mapa_v, mapa_c)

        atual = pd.read_sql(
            f"SELECT HASH_NEGOCIO, {', '.join(COLUNAS_FATO)} "
            f"FROM gold.fato_manutencao_auto", conn)

        novos = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
        if len(novos):
            novos.to_sql("fato_manutencao_auto", conn, schema="gold",
                         if_exists="append", index=False)

        # Depois do fato, e nao antes: a categoria de cada item do plano
        # e deduzida dos lancamentos que ja estao gravados.
        novos_r, alt_r, sem_historico = sincroniza_revisao(conn, mapa_v)

        alterados = detecta_alteracoes(atual, fato, "HASH_NEGOCIO", COLUNAS_FATO)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_FATO)
            conn.execute(
                text(f"UPDATE gold.fato_manutencao_auto SET {sets}, "
                     f"DT_CARGA = SYSDATETIME() WHERE HASH_NEGOCIO = :chave"),
                alterados,
            )

    print(f"  dim_veiculo             : +{novos_v} novos, {alt_v} atualizados")
    print(f"  dim_categoria_auto      : +{novos_c} novas, {alt_c} atualizadas")
    print(f"  dim_revisao_programada  : +{novos_r} novas, {alt_r} atualizadas")
    print(f"  fato                    : +{len(novos)} novos, {len(alterados)} atualizados")

    if sem_historico:
        print(f"\n== {len(sem_historico)} itens do plano sem lancamento correspondente ==")
        print("   Aparecem na previsao como 'Sem registro'. Pode ser servico feito")
        print("   antes de o carro ser seu, ou grafia que o de-para ainda nao alcanca")
        print("   (silver.de_para_item_revisao resolve com um INSERT).")
        for item in sem_historico:
            print(f"   - {item}")

    registra_carga(engine, "gold.dim_veiculo", novos_v, alt_v, inicio=_INICIO)
    registra_carga(engine, "gold.dim_revisao_programada", novos_r, alt_r,
                   inicio=_INICIO)
    registra_carga(engine, "gold.dim_categoria_auto", novos_c, alt_c,
                   inicio=_INICIO)
    registra_carga(engine, "gold.fato_manutencao_auto",
                   len(novos), len(alterados), inicio=_INICIO)

    print("\n== Conferencia silver x gold ==")
    print(pd.read_sql("""
        SELECT (SELECT COUNT(*) FROM silver.auto_manutencao) AS silver,
               (SELECT COUNT(*) FROM gold.fato_manutencao_auto) AS gold,
               (SELECT COUNT(*) FROM gold.fato_manutencao_auto
                 WHERE SK_VEICULO = -1 OR SK_CATEGORIA_MANUTENCAO = -1) AS sem_dim,
               (SELECT CAST(SUM(vl_gasto) AS decimal(12,2))
                  FROM silver.auto_manutencao) AS soma_silver,
               (SELECT CAST(SUM(VL_GASTO) AS decimal(12,2))
                  FROM gold.fato_manutencao_auto) AS soma_gold
    """, engine).to_string(index=False))

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
