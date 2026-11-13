"""
Carga da camada Gold - avaliacao fisica.

Le silver.avaliacao_fisica e grava em gold.fato_avaliacao_fisica,
alimentando gold.dim_metrica_corporal com metricas novas.

CALCULA A VARIACAO ENTRE AVALIACOES. A pergunta do painel e "como
estou em relacao a avaliacao anterior", e as avaliacoes sao
irregulares - de 21 dias a quase cinco anos entre elas. "Anterior" nao
coincide com nenhum periodo do calendario, entao a comparacao em DAX
exigiria navegar por posicao dentro de cada metrica. Feita aqui, vira
coluna.

O SENTIDO DA MELHORA VEM DA DIMENSAO, nao daqui: DS_SENTIDO_MELHOR diz
se subir ou cair e bom para cada metrica. Mudar de ideia e um UPDATE.

Uso:
    python carga_gold_avaliacao.py
    python carga_gold_avaliacao.py --resumo
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

COLUNAS_FATO = [
    "SK_DATA", "SK_METRICA", "SK_SEGMENTO", "NR_AVALIACAO", "VL_MEDIDA",
    "VL_MEDIDA_ANTERIOR", "VL_VARIACAO", "FL_MELHOROU", "FL_MEDIDO",
    "VL_REFERENCIA_MIN", "VL_REFERENCIA_MAX", "DS_AVALIACAO", "DS_ORIGEM",
]

CORPO_INTEIRO = "Corpo inteiro"


def hash_medida(data, metrica, segmento) -> str:
    """
    Identidade da medida: data, metrica e segmento.

    O SEGMENTO ENTROU NA CHAVE quando os exames InBody chegaram, porque
    a analise segmentar mede a mesma metrica em cinco lugares do corpo.
    Sem ele, as cinco leituras de "Massa Magra Segmentar" do mesmo dia
    colidiriam numa linha so.
    """
    texto = f"aval|{data}|{_chave(metrica)}|{_chave(segmento)}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _chave(valor) -> str:
    """Comparacao alinhada a collation do banco (Latin1_General_CI_AS)."""
    return str(valor).strip().upper() if valor is not None else ""


def sincroniza_metricas(conn, dados: pd.DataFrame) -> tuple[dict, int]:
    """
    Acrescenta a dimensao as metricas que ainda nao existem.

    A semeadura do 23_gold_avaliacao.sql ja cadastra as 30 conhecidas
    com o sentido de melhora definido. Esta funcao existe para o caso
    de uma metrica nova aparecer no laudo: ela entra sem travar a
    carga, com o sentido em branco, e o aviso lembra de classificar.
    """
    novas_cols = ["NM_METRICA", "DS_GRUPO", "DS_UNIDADE", "FL_SERIE_CONTINUA",
                  "DS_ERA", "NR_ORDEM"]

    def le():
        return pd.read_sql(
            "SELECT SK_METRICA, NM_METRICA, DS_SENTIDO_MELHOR "
            "FROM gold.dim_metrica_corporal", conn)

    existente = le()
    ja_tem = {_chave(n) for n in existente["NM_METRICA"]}

    candidatas = (dados[["ds_metrica", "ds_grupo", "ds_unidade",
                         "fl_serie_continua", "ds_era"]]
                  .drop_duplicates("ds_metrica"))
    faltando = candidatas[[_chave(n) not in ja_tem
                           for n in candidatas["ds_metrica"]]]

    if len(faltando):
        proxima = int(pd.read_sql(
            "SELECT ISNULL(MAX(NR_ORDEM), 0) + 1 AS n "
            "FROM gold.dim_metrica_corporal WHERE NR_ORDEM < 900",
            conn)["n"].iloc[0])
        novas = pd.DataFrame({
            "NM_METRICA": faltando["ds_metrica"],
            "DS_GRUPO": faltando["ds_grupo"],
            "DS_UNIDADE": faltando["ds_unidade"],
            "FL_SERIE_CONTINUA": faltando["fl_serie_continua"],
            "DS_ERA": faltando["ds_era"],
            "NR_ORDEM": range(proxima, proxima + len(faltando)),
        })[novas_cols]
        novas = aplica_flags(novas)
        novas.to_sql("dim_metrica_corporal", conn, schema="gold",
                     if_exists="append", index=False)
        for nome in faltando["ds_metrica"]:
            print(f"  AVISO: metrica nova '{nome}' entrou na dimensao sem "
                  f"DS_SENTIDO_MELHOR - defina se subir ou cair e melhora")
        existente = le()

    mapa_sk = {_chave(n): sk for sk, n in zip(existente["SK_METRICA"],
                                              existente["NM_METRICA"])}
    mapa_sentido = {_chave(n): s for n, s in zip(existente["NM_METRICA"],
                                                 existente["DS_SENTIDO_MELHOR"])}
    return (mapa_sk, mapa_sentido), len(faltando)


def le_origens(engine) -> pd.DataFrame:
    """
    Junta as duas origens da avaliacao fisica.

    AS DUAS SE COMPLETAM, e nao se substituem. A planilha preenchida a
    mao tem 17 metricas que o InBody nem mede - circunferencias,
    pressao, frequencia cardiaca - e cobre de 2008 a 2013, antes de o
    aparelho existir na rotina. O arquivo do exame tem 15 que a
    planilha nunca teve, entre elas a analise segmentar.

    ONDE AS DUAS FALAM DA MESMA COISA, O ARQUIVO VENCE: ele e o
    documento, e a planilha era a transcricao dele. Mas so vence
    quando tem valor - se o OCR recusou a medida por contradizer as
    conferencias, a linha da planilha assume, e e exatamente para isso
    que ela continua sendo carregada.
    """
    planilha = pd.read_sql("SELECT * FROM silver.avaliacao_fisica", engine)
    planilha = pd.DataFrame({
        "dt": pd.to_datetime(planilha["dt_avaliacao"]).dt.date,
        "metrica": planilha["ds_metrica"],
        "segmento": CORPO_INTEIRO,
        "valor": planilha["vl_medida"],
        "fl_medido": planilha["fl_medido"],
        "ref_min": None, "ref_max": None, "avaliacao": None,
        "origem": "Planilha",
    })

    arquivo = pd.read_sql("SELECT * FROM silver.avaliacao_inbody", engine)
    arquivo = pd.DataFrame({
        "dt": pd.to_datetime(arquivo["dt_exame"]).dt.date,
        "metrica": arquivo["nm_metrica"],
        "segmento": arquivo["nm_segmento"],
        "valor": arquivo["vl_medida"],
        "fl_medido": 1,
        "ref_min": arquivo["vl_referencia_min"],
        "ref_max": arquivo["vl_referencia_max"],
        "avaliacao": arquivo["ds_avaliacao"],
        "origem": "InBody",
    })

    print(f"  planilha: {len(planilha)} medidas em "
          f"{planilha['dt'].nunique()} avaliacoes")
    print(f"  arquivos: {len(arquivo)} medidas em "
          f"{arquivo['dt'].nunique()} exames")

    # O arquivo primeiro: no empate de (data, metrica, segmento), fica
    # a primeira linha, que e a dele.
    juntas = pd.concat([arquivo, planilha], ignore_index=True)
    juntas["_k"] = [
        hash_medida(d, m, s)
        for d, m, s in zip(juntas["dt"], juntas["metrica"], juntas["segmento"])
    ]
    antes = len(juntas)
    juntas = juntas.drop_duplicates(subset="_k", keep="first")

    vindas_do_arquivo = int((juntas["origem"] == "InBody").sum())
    print(f"  juntas  : {len(juntas)} medidas "
          f"({vindas_do_arquivo} do arquivo, "
          f"{len(juntas) - vindas_do_arquivo} da planilha), "
          f"{antes - len(juntas)} sobrepostas")

    # A sequencia da avaliacao continua sendo por DATA, nao por linha:
    # e ela que ordena o grafico de longo prazo.
    datas = sorted(juntas["dt"].unique())
    ordem = {d: i + 1 for i, d in enumerate(datas)}
    juntas["nr_avaliacao"] = [ordem[d] for d in juntas["dt"]]
    return juntas.sort_values(["metrica", "segmento", "nr_avaliacao"])


def migra_hash(conn) -> int:
    """
    Reescreve a identidade das linhas que vieram do esquema antigo.

    Antes dos exames InBody, o fato herdava o hash da planilha, que nao
    conhecia segmento. Agora a identidade e (data, metrica, segmento).
    Sem esta migracao, as 419 linhas existentes ficariam orfas e seriam
    reinseridas como novas - dobrando a serie de 2008 a 2026.

    Roda sozinha e uma vez: na segunda execucao nao ha o que corrigir.
    """
    atual = pd.read_sql("""
        SELECT f.HASH_NEGOCIO, c.DT_DATA, m.NM_METRICA, s.NM_SEGMENTO
        FROM gold.fato_avaliacao_fisica f
        JOIN gold.dim_calendario c        ON c.SK_DATA = f.SK_DATA
        JOIN gold.dim_metrica_corporal m  ON m.SK_METRICA = f.SK_METRICA
        JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
    """, conn)
    if atual.empty:
        return 0

    trocas = [
        {"velho": r.HASH_NEGOCIO, "novo": novo}
        for r in atual.itertuples()
        if (novo := hash_medida(r.DT_DATA, r.NM_METRICA, r.NM_SEGMENTO))
        != r.HASH_NEGOCIO
    ]
    if trocas:
        conn.execute(
            text("UPDATE gold.fato_avaliacao_fisica SET HASH_NEGOCIO = :novo "
                 "WHERE HASH_NEGOCIO = :velho"), trocas)
    return len(trocas)


def monta_fato(dados: pd.DataFrame, mapa_sk: dict, mapa_sentido: dict,
               mapa_seg: dict) -> pd.DataFrame:
    """
    Monta o fato a partir das duas origens ja unidas.

    A COMPARACAO COM A MEDIDA ANTERIOR AGORA E POR METRICA E SEGMENTO.
    Antes bastava a metrica, porque tudo era corpo inteiro; com a
    analise segmentar, comparar "Massa Magra Segmentar" sem separar
    perna esquerda de braco direito misturaria cinco series numa so.
    """
    dados = dados.sort_values(["metrica", "segmento", "nr_avaliacao"]).copy()

    fato = pd.DataFrame({"HASH_NEGOCIO": dados["_k"].values})
    fato["SK_DATA"] = [
        int(pd.Timestamp(d).strftime("%Y%m%d")) for d in dados["dt"]
    ]
    chaves = [_chave(m) for m in dados["metrica"]]
    fato["SK_METRICA"] = [mapa_sk.get(c, -1) for c in chaves]
    fato["SK_SEGMENTO"] = [mapa_seg.get(_chave(s), -1)
                           for s in dados["segmento"]]
    fato["NR_AVALIACAO"] = dados["nr_avaliacao"].values
    fato["VL_MEDIDA"] = dados["valor"].values
    fato["FL_MEDIDO"] = dados["fl_medido"].values
    fato["VL_REFERENCIA_MIN"] = dados["ref_min"].values
    fato["VL_REFERENCIA_MAX"] = dados["ref_max"].values
    fato["DS_AVALIACAO"] = dados["avaliacao"].values
    fato["DS_ORIGEM"] = dados["origem"].values

    # O valor anterior e o da ultima vez que ESTA metrica NESTE
    # segmento foi MEDIDA - pular a medida nao deve criar buraco na
    # comparacao nem inventar variacao contra um nulo.
    medido = dados["valor"].where(dados["fl_medido"].astype(bool))
    fato["VL_MEDIDA_ANTERIOR"] = (
        medido.groupby([dados["metrica"], dados["segmento"]]).shift(1).values)

    # Arredondar na precisao da coluna (decimal 10,2) e o que faz a
    # carga convergir. Sem isso a subtracao em ponto flutuante gera
    # -0,7599999999999998, o banco guarda -0,76, e a carga seguinte
    # acha que mudou - 172 falsas atualizacoes a cada execucao.
    fato["VL_VARIACAO"] = (fato["VL_MEDIDA"] - fato["VL_MEDIDA_ANTERIOR"]).round(2)

    # O sentido vem da dimensao, onde e NULL nas metricas sem direcao
    # boa definida. O pandas devolve esse NULL como NaN, e NaN E
    # TRUTHY: testar so "not sentido" faria o peso aparecer como
    # "piorou" por ter subido - o julgamento que a coluna nula existe
    # justamente para evitar.
    sentidos = [
        None if pd.isna(s := mapa_sentido.get(c)) else str(s).strip().upper()
        for c in chaves
    ]
    fato["FL_MELHOROU"] = [
        None if s is None or pd.isna(v) or v == 0
        else (v > 0 if s == "MAIOR" else v < 0)
        for v, s in zip(fato["VL_VARIACAO"], sentidos)
    ]

    for coluna in COLUNAS_FATO:
        fato[coluna] = fato[coluna].map(valor_sql)
    fato = aplica_flags(fato)
    return fato


def resumo(engine) -> None:
    print("\n== Evolucao das cinco metricas que cobrem os 18 anos ==")
    print(pd.read_sql("""
        SELECT d.NR_ANO AS ano,
               CAST(AVG(CASE WHEN m.NM_METRICA = 'Peso' THEN f.VL_MEDIDA END)
                    AS decimal(6,1)) AS peso_kg,
               CAST(AVG(CASE WHEN m.NM_METRICA = 'IMC' THEN f.VL_MEDIDA END)
                    AS decimal(6,1)) AS imc,
               CAST(AVG(CASE WHEN m.NM_METRICA = '% Gordura' THEN f.VL_MEDIDA END)
                    AS decimal(6,1)) AS pct_gordura,
               CAST(AVG(CASE WHEN m.NM_METRICA = 'Massa Gordura' THEN f.VL_MEDIDA END)
                    AS decimal(6,1)) AS gordura_kg
        FROM gold.fato_avaliacao_fisica f
        JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
        JOIN gold.dim_calendario d ON d.SK_DATA = f.SK_DATA
        WHERE m.FL_SERIE_CONTINUA = 'S'
        GROUP BY d.NR_ANO ORDER BY 1
    """, engine).to_string(index=False))

    print("\n== Ultima avaliacao: o que melhorou e o que piorou ==")
    print(pd.read_sql("""
        SELECT m.NM_METRICA AS metrica, m.DS_UNIDADE AS un,
               f.VL_MEDIDA AS agora, f.VL_MEDIDA_ANTERIOR AS antes,
               f.VL_VARIACAO AS variacao,
               CASE f.FL_MELHOROU WHEN 1 THEN 'melhorou' WHEN 0 THEN 'piorou'
                    ELSE '-' END AS avaliacao
        FROM gold.fato_avaliacao_fisica f
        JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
        WHERE f.NR_AVALIACAO = (SELECT MAX(NR_AVALIACAO)
                                  FROM gold.fato_avaliacao_fisica)
        ORDER BY m.NR_ORDEM
    """, engine).to_string(index=False))

    print("\n== Placar por avaliacao: % de metricas que melhoraram ==")
    print(pd.read_sql("""
        SELECT TOP 10 f.NR_AVALIACAO AS n, MIN(c.DT_DATA) AS data,
               COUNT(f.FL_MELHOROU) AS metricas_com_direcao,
               CAST(100.0 * AVG(CAST(f.FL_MELHOROU AS float))
                    AS decimal(4,1)) AS pct_melhorou
        FROM gold.fato_avaliacao_fisica f
        JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
        GROUP BY f.NR_AVALIACAO
        HAVING COUNT(f.FL_MELHOROU) > 0
        ORDER BY f.NR_AVALIACAO DESC
    """, engine).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold da avaliacao fisica")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    engine = get_engine()
    print("Origens da avaliacao fisica:")
    dados = le_origens(engine)

    # sincroniza_metricas espera o formato da planilha; so ela pode
    # trazer metrica nova sem cadastro previo. As do exame ja entraram
    # pelo DDL, com sentido de melhora definido.
    da_planilha = pd.read_sql("SELECT * FROM silver.avaliacao_fisica", engine)

    with engine.begin() as conn:
        trocados = migra_hash(conn)
        if trocados:
            print(f"  {trocados} identidades migradas para o esquema com "
                  f"segmento")

        (mapa_sk, mapa_sentido), novas_metricas = sincroniza_metricas(
            conn, da_planilha)
        seg = pd.read_sql(
            "SELECT SK_SEGMENTO, NM_SEGMENTO FROM gold.dim_segmento_corporal",
            conn)
        mapa_seg = {_chave(n): s for s, n in zip(seg["SK_SEGMENTO"],
                                                 seg["NM_SEGMENTO"])}
        fato = monta_fato(dados, mapa_sk, mapa_sentido, mapa_seg)

        atual = pd.read_sql(
            f"SELECT HASH_NEGOCIO, {', '.join(COLUNAS_FATO)} "
            f"FROM gold.fato_avaliacao_fisica", conn)

        novos = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
        if len(novos):
            novos.to_sql("fato_avaliacao_fisica", conn, schema="gold",
                         if_exists="append", index=False)

        # REMOVE O QUE NENHUMA DAS DUAS ORIGENS AFIRMA MAIS. O fato e
        # uma projecao completa das duas silvers: medida que sumiu de
        # la nao pode sobreviver aqui.
        #
        # Foi assim que o percentual de gordura de 13/08/2018 ficou
        # preso em 9,0% depois de o extrator passar a rejeita-lo -
        # numero que nem o arquivo nem a planilha sustentavam.
        #
        # A remocao conta como atualizacao porque E mudanca na tabela:
        # convergencia que ignora exclusao diria "nada mudou" enquanto
        # linhas somem.
        vivos = set(fato["HASH_NEGOCIO"])
        sumiram = [h for h in atual["HASH_NEGOCIO"] if h not in vivos]
        if sumiram:
            conn.execute(
                text("DELETE FROM gold.fato_avaliacao_fisica "
                     "WHERE HASH_NEGOCIO = :h"),
                [{"h": h} for h in sumiram])
            print(f"  removidas do fato  : {len(sumiram)} medidas sem origem")

        alterados = detecta_alteracoes(atual, fato, "HASH_NEGOCIO", COLUNAS_FATO)
        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_FATO)
            conn.execute(
                text(f"UPDATE gold.fato_avaliacao_fisica SET {sets}, "
                     f"DT_CARGA = SYSDATETIME() WHERE HASH_NEGOCIO = :chave"),
                alterados,
            )

    print(f"  dim_metrica_corporal: +{novas_metricas} novas")
    print(f"  fato                : +{len(novos)} novos, "
          f"{len(alterados) + len(sumiram)} atualizados")
    registra_carga(engine, "gold.fato_avaliacao_fisica",
                   len(novos), len(alterados) + len(sumiram), inicio=_INICIO)

    print("\n== Conferencia das duas origens contra o fato ==")
    # A conferencia antiga comparava o fato so com a silver da
    # planilha, e passou a acusar 419 contra 1.154 - numero verdadeiro
    # e leitura errada. Agora cada origem e conferida separadamente,
    # que e o que a juncao exige: o total do fato NAO e a soma das
    # duas, porque onde as duas tem o mesmo campo so uma entra.
    print(pd.read_sql("""
        SELECT 'planilha' AS origem,
               (SELECT COUNT(*) FROM silver.avaliacao_fisica) AS na_silver,
               (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica
                 WHERE DS_ORIGEM = 'Planilha') AS no_fato
        UNION ALL
        SELECT 'arquivo InBody',
               (SELECT COUNT(*) FROM silver.avaliacao_inbody),
               (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica
                 WHERE DS_ORIGEM = 'InBody')
        UNION ALL
        SELECT 'total no fato', NULL,
               (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica)
        UNION ALL
        SELECT 'sem metrica (deve ser 0)', NULL,
               (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica
                 WHERE SK_METRICA = -1)
    """, engine).to_string(index=False))

    print("\n== O que a planilha cobriu porque o arquivo nao leu ==")
    print(pd.read_sql("""
        SELECT m.NM_METRICA AS metrica, COUNT(*) AS medidas,
               MIN(c.NR_ANO) AS de, MAX(c.NR_ANO) AS ate
        FROM gold.fato_avaliacao_fisica f
        JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
        JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
        WHERE f.DS_ORIGEM = 'Planilha' AND c.NR_ANO >= 2018
        GROUP BY m.NM_METRICA ORDER BY medidas DESC
    """, engine).to_string(index=False))

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
