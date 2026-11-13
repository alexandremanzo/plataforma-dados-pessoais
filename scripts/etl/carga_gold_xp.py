"""
Carga da camada Gold - star schema de investimentos.

Le silver.xp_movimentacao, alimenta as dimensoes e o fato.

ESCOPO: chamadas de margem ficam de fora. Sao movimentacao de
garantia que entra e volta, sem efeito patrimonial, e representavam
metade dos eventos da base - manteriam o dashboard poluido sem
acrescentar informacao. A silver continua com o registro completo,
entao nada se perde: e uma decisao de apresentacao, nao de dado.

As dimensoes crescem sozinhas: uma categoria ou ativo que aparece
pela primeira vez ganha linha nova, sem cadastro manual. Os codigos
ja existentes nunca sao renumerados, para nao invalidar o fato.

Uso:
    python carga_gold_xp.py
    python carga_gold_xp.py --incluir-margem   # ignora a exclusao
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import get_engine  # noqa: E402
from regras_xp import classifica_tipo_ativo, subclasse_fundo  # noqa: E402
from util_dados import (  # noqa: E402
    aplica_flags, registra_carga, texto_comparavel as _texto, valor_sql as _valor,
)

_INICIO = time.monotonic()

SK_ORIGEM_XP = 1
CATEGORIAS_EXCLUIDAS = {"Margem"}

# Colunas do fato que sao recalculadas a cada carga e, portanto,
# precisam ser comparadas para detectar mudanca de regra.
COLUNAS_FATO = [
    "SK_ORIGEM", "SK_DATA_MOVIMENTACAO", "SK_DATA_LIQUIDACAO",
    "SK_ATIVO", "SK_CATEGORIA_INVESTIMENTO", "VL_TRANSACAO", "VL_SALDO_MOMENTO",
    "FL_RENDIMENTO", "DS_TIPO_FLUXO", "DS_DETALHE_ORIGINAL",
]


# Agrupador usado no dashboard, para nao plotar 24 categorias soltas.
GRUPO_POR_CATEGORIA = {
    "Dividendo": "Proventos", "Investback": "Proventos",
    "Reembolso": "Proventos", "Taxa de Remuneração": "Proventos",

    "IR": "Custos", "IOF": "Custos", "Emolumentos": "Custos",
    "Taxa de intermediação": "Custos", "Multa": "Custos",
    "Ajuste de Custos": "Custos",

    "Compra": "Operação", "Operação Bolsa": "Operação",
    "Subscrição": "Operação", "Débito Subscrição": "Operação",
    "Vencimento": "Operação", "Liquidação": "Operação",
    "Estorno": "Operação",

    "Transferência": "Caixa", "Retirada": "Caixa", "Aplicação": "Caixa",
    "Resgate": "Caixa", "Pagamento CC": "Caixa", "Pagamento": "Caixa",

    "Margem": "Garantia",
}

# Usado apenas quando o ativo nao consta no de-para manual. Espelha a
# taxonomia definida a mao, para que o deduzido e o manual convivam no
# mesmo vocabulario e o dashboard nao mostre dois rotulos para a mesma
# coisa.
CLASSE_POR_TIPO = {
    "Ação":             ("Renda Variável", "Ações"),
    "FII":              ("Fundos Imobiliários", "FII"),
    "Fundo":            ("Fundos de Investimento", "Fundo de Investimento"),
    "CDB":              ("Renda Fixa", "CDB"),
    "CRI":              ("Renda Fixa", "CRI"),
    "LCA/LCI":          ("Renda Fixa", "LCA"),
    "Tesouro Direto":   ("Renda Fixa", "Título Público"),
    "COE":              ("Operações Estruturadas", "COE"),
    "Aluguel BTC":      ("Empréstimo de Ativos", "BTC (Aluguel de Ações)"),
    "Não aplicável":    ("Não aplicável", "Não aplicável"),
}


def _sincroniza_dimensao(conn, tabela: str, coluna_cod: str,
                         valores: pd.DataFrame,
                         atributos: list[str]) -> tuple[dict, int, int]:
    """
    Sincroniza uma dimensao e devolve (mapa codigo -> SK, novos, atualizados).

    A chave substituta de um membro existente NUNCA muda: o fato aponta
    para ela. Ja os atributos derivados de regra (classe do ativo, grupo
    da categoria) sao atualizados, senao uma melhoria nas regras so
    valeria para os membros novos - foi assim que "Valora CRI" continuou
    marcado como nao classificado depois de a regra de CRI existir.
    """
    # A chave segue o nome da tabela sem o prefixo "dim_", e a divisao
    # precisa ser em UMA parte so: com split("_")[1] a
    # dim_categoria_investimento viraria SK_CATEGORIA, que nao existe.
    sk = "SK_" + tabela.split("_", 1)[1].upper()

    def le():
        return pd.read_sql(
            f"SELECT {sk} AS sk, {coluna_cod} AS cod, {', '.join(atributos)} "
            f"FROM gold.{tabela}", conn
        )

    existente = le()
    novos = valores[~valores[coluna_cod].isin(set(existente["cod"]))]

    if len(novos):
        novos.to_sql(tabela, conn, schema="gold", if_exists="append", index=False)
        existente = le()

    # Atualiza atributos que a regra recalculou.
    antes = existente.set_index("cod")
    alterados = [
        {"cod": linha[coluna_cod], **{a: linha[a] for a in atributos}}
        for _, linha in valores.iterrows()
        if linha[coluna_cod] in antes.index
        and any(str(linha[a]) != str(antes.loc[linha[coluna_cod], a]) for a in atributos)
    ]

    if alterados:
        sets = ", ".join(f"{a} = :{a}" for a in atributos)
        conn.execute(
            text(f"UPDATE gold.{tabela} SET {sets}, DT_CARGA = SYSDATETIME() "
                 f"WHERE {coluna_cod} = :cod"),
            alterados,
        )
        existente = le()

    return dict(zip(existente["cod"], existente["sk"])), len(novos), len(alterados)


def remove_orfaos(conn, tabela: str, sk: str) -> int:
    """Apaga membros de dimensao que NENHUM fato referencia.

    QUEM REFERENCIA SAI DO CATALOGO, e nao de uma lista escrita aqui.
    A versao anterior conferia so gold.fato_investimento, porque por
    anos ele foi o unico fato a usar estas dimensoes. Quando nasceu o
    gold.fato_posicao_investimento, a lista ficou desatualizada e a
    carga passou a falhar TODA RODADA: ela tentava apagar 27 ativos
    que vieram da API e tinham posicao mas nenhum evento de fluxo, e a
    chave estrangeira barrava o DELETE.

    O defeito nao estava na FK nem nos 27 ativos - estava em uma lista
    que precisava ser lembrada. Lida de sys.foreign_keys, ela
    acompanha sozinha o proximo fato que aparecer.

    O membro -1 e preservado: ele existe justamente para o caso sem
    valor, e nenhum fato precisa aponta-lo para que ele faca sentido.
    """
    refs = conn.execute(text("""
        SELECT OBJECT_SCHEMA_NAME(fk.parent_object_id) AS esquema,
               OBJECT_NAME(fk.parent_object_id)        AS tabela,
               COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS coluna
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc
          ON fkc.constraint_object_id = fk.object_id
        WHERE fk.referenced_object_id = OBJECT_ID(:alvo)
    """), {"alvo": f"gold.{tabela}"}).fetchall()

    if not refs:
        # Dimensao que ninguem referencia: apagar tudo seria o
        # resultado literal da regra, e obviamente nao e a intencao.
        return 0

    clausulas = " AND ".join(
        f"NOT EXISTS (SELECT 1 FROM {r.esquema}.{r.tabela} r{i} "
        f"WHERE r{i}.{r.coluna} = gold.{tabela}.{sk})"
        for i, r in enumerate(refs))
    return conn.execute(text(
        f"DELETE FROM gold.{tabela} WHERE {sk} <> -1 AND {clausulas}")).rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga gold dos investimentos")
    parser.add_argument("--incluir-margem", action="store_true",
                        help="carrega tambem as chamadas de margem")
    args = parser.parse_args()

    engine = get_engine()
    silver = pd.read_sql("SELECT * FROM silver.xp_movimentacao", engine)
    print(f"Silver: {len(silver)} eventos")

    if not args.incluir_margem:
        antes = len(silver)
        silver = silver[~silver["ds_categoria"].isin(CATEGORIAS_EXCLUIDAS)]
        print(f"  excluidos {antes - len(silver)} de margem "
              f"-> {len(silver)} eventos para a gold")

    with engine.begin() as conn:
        # --- Dimensoes ---
        categorias = pd.DataFrame({
            "NM_CATEGORIA": sorted(silver["ds_categoria"].dropna().unique())
        })
        categorias["DS_GRUPO"] = categorias["NM_CATEGORIA"].map(
            lambda c: GRUPO_POR_CATEGORIA.get(c, "Outros")
        )
        mapa_cat, novas_cat, cat_upd = _sincroniza_dimensao(
            conn, "dim_categoria_investimento", "NM_CATEGORIA", categorias, ["DS_GRUPO"])

        ativos = pd.DataFrame({
            "CD_ATIVO": sorted(silver["ds_ativo"].dropna().unique())
        })
        ativos["NM_ATIVO"] = ativos["CD_ATIVO"]
        ativos["TP_ATIVO"] = ativos["CD_ATIVO"].map(classifica_tipo_ativo)

        # Classe e subclasse vem do de-para manual quando o ativo consta
        # la. Caso contrario sao deduzidas do TP_ATIVO, e a procedencia
        # fica registrada para nao se confundir decisao com deducao.
        # Busca sem distincao de caixa: o banco e case-insensitive e nao
        # aceitaria duas grafias do mesmo codigo, entao o de-para guarda
        # uma so e o casamento aqui precisa acompanhar.
        tabela_classe = pd.read_sql(
            "SELECT cd_ativo, ds_classe, ds_subclasse "
            "FROM silver.de_para_classe_ativo", conn)
        de_para = {
            str(r.cd_ativo).strip().upper(): (r.ds_classe, r.ds_subclasse)
            for r in tabela_classe.itertuples()
        }

        def classe(codigo):
            achado = de_para.get(str(codigo).strip().upper())
            if achado:
                return achado[0], achado[1], "MANUAL"

            tipo = classifica_tipo_ativo(codigo)
            padrao = CLASSE_POR_TIPO.get(
                tipo, ("Não classificado", "Não classificado"))

            # O sufixo do nome do fundo diz a estrategia, entao vale
            # mais que o generico "Fundo de Investimento".
            if tipo == "Fundo":
                return padrao[0], subclasse_fundo(codigo), "DEDUZIDA"
            return padrao[0], padrao[1], "DEDUZIDA"

        classes = [classe(c) for c in ativos["CD_ATIVO"]]
        ativos["DS_CLASSE_ATIVO"] = [c[0] for c in classes]
        ativos["DS_SUBCLASSE_ATIVO"] = [c[1] for c in classes]
        ativos["DS_ORIGEM_CLASSE"] = [c[2] for c in classes]

        mapa_ativo, novos_ativo, ativo_upd = _sincroniza_dimensao(
            conn, "dim_ativo", "CD_ATIVO", ativos,
            ["NM_ATIVO", "TP_ATIVO", "DS_CLASSE_ATIVO",
             "DS_SUBCLASSE_ATIVO", "DS_ORIGEM_CLASSE"])

        print(f"  dim_categoria_investimento: +{novas_cat} novas, {cat_upd} atualizadas")
        print(f"  dim_ativo    : +{novos_ativo} novos, {ativo_upd} atualizados")

        # --- Fato ---
        def sk_data(valor):
            if pd.isna(valor):
                return -1
            return int(pd.Timestamp(valor).strftime("%Y%m%d"))

        fato = pd.DataFrame({
            "SK_ORIGEM": SK_ORIGEM_XP,
            "SK_DATA_MOVIMENTACAO": silver["dt_movimentacao"].map(sk_data),
            "SK_DATA_LIQUIDACAO": silver["dt_liquidacao"].map(sk_data),
            "SK_ATIVO": silver["ds_ativo"].map(lambda a: mapa_ativo.get(a, -1)),
            "SK_CATEGORIA_INVESTIMENTO": silver["ds_categoria"].map(lambda c: mapa_cat.get(c, -1)),
            "VL_TRANSACAO": silver["vl_transacao"],
            "VL_SALDO_MOMENTO": silver["vl_saldo"],
            "FL_RENDIMENTO": silver["fl_rendimento"],
            "DS_TIPO_FLUXO": silver["ds_tipo_movimentacao"],
            "DS_DETALHE_ORIGINAL": silver["ds_lancamento"],
            "HASH_NEGOCIO": silver["hash_negocio"],
        })

        fato = aplica_flags(fato)

        atual = pd.read_sql(f"SELECT HASH_NEGOCIO, {', '.join(COLUNAS_FATO)} "
                            f"FROM gold.fato_investimento", conn)

        novos_fato = fato[~fato["HASH_NEGOCIO"].isin(set(atual["HASH_NEGOCIO"]))]
        if len(novos_fato):
            novos_fato.to_sql("fato_investimento", conn, schema="gold",
                              if_exists="append", index=False)

        # Uma mudanca de regra (nova categoria, ISIN resolvido para
        # ticker) altera as chaves de lancamentos que ja estao no fato.
        # Sem este passo, o modelo continuaria apontando para a
        # classificacao antiga ate alguem recriar a tabela.
        alterados = []
        if len(atual):
            antes = atual.set_index("HASH_NEGOCIO")
            depois = fato[fato["HASH_NEGOCIO"].isin(antes.index)].set_index("HASH_NEGOCIO")
            for h, linha in depois.iterrows():
                anterior = antes.loc[h]
                if any(_texto(linha[c]) != _texto(anterior[c]) for c in COLUNAS_FATO):
                    alterados.append({"h": h, **{c: _valor(linha[c]) for c in COLUNAS_FATO}})

        if alterados:
            sets = ", ".join(f"{c} = :{c}" for c in COLUNAS_FATO)
            conn.execute(
                text(f"UPDATE gold.fato_investimento SET {sets}, DT_CARGA = SYSDATETIME() "
                     f"WHERE HASH_NEGOCIO = :h"),
                alterados,
            )

    print(f"  fato         : +{len(novos_fato)} novos, {len(alterados)} atualizados")

    # Fora do "with" de proposito: registrar de dentro abriria uma
    # segunda conexao para contar linhas que a transacao aberta ainda
    # nao confirmou - leitura errada, e travamento esperando o lock.
    registra_carga(engine, "gold.dim_categoria_investimento",
                   novas_cat, cat_upd, inicio=_INICIO)
    registra_carga(engine, "gold.dim_ativo", novos_ativo, ativo_upd,
                   inicio=_INICIO)
    registra_carga(engine, "gold.fato_investimento",
                   len(novos_fato), len(alterados), inicio=_INICIO)

    # Membros de dimensao que nenhum lancamento referencia mais. Surgem
    # quando uma regra melhora: ao resolver BRITUBACNPR1 para ITUB4, o
    # membro com o ISIN fica orfao. Se ficassem, apareceriam como opcoes
    # vazias nos filtros do Power BI. Os membros -1 sao preservados: eles
    # existem justamente para os casos sem valor.
    with engine.begin() as conn:
        removidos = 0
        for tabela, sk in (("dim_ativo", "SK_ATIVO"),
                           ("dim_categoria_investimento", "SK_CATEGORIA_INVESTIMENTO")):
            removidos += remove_orfaos(conn, tabela, sk)
    if removidos:
        print(f"  dimensoes    : -{removidos} membros orfaos removidos")

    # --- Conferencia ---
    print("\n== Conferencia ==")
    print(pd.read_sql("""
        SELECT
          (SELECT COUNT(*) FROM gold.fato_investimento)                        AS fato_linhas,
          (SELECT COUNT(DISTINCT HASH_NEGOCIO) FROM gold.fato_investimento)    AS fato_eventos,
          (SELECT COUNT(*) FROM silver.xp_movimentacao
            WHERE ds_categoria NOT IN ('Margem'))                            AS silver_sem_margem,
          (SELECT CAST(SUM(VL_TRANSACAO) AS decimal(18,2))
             FROM gold.fato_investimento)                                      AS soma_gold,
          (SELECT CAST(SUM(vl_transacao) AS decimal(18,2))
             FROM silver.xp_movimentacao WHERE ds_categoria NOT IN ('Margem')) AS soma_silver
    """, engine).to_string(index=False))

    print("\n== Grupos de categoria ==")
    print(pd.read_sql("""
        SELECT c.DS_GRUPO, COUNT(*) AS lancamentos,
               CAST(SUM(f.VL_TRANSACAO) AS decimal(18,2)) AS total_rs
        FROM gold.fato_investimento f
        JOIN gold.dim_categoria_investimento c ON c.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
        GROUP BY c.DS_GRUPO ORDER BY SUM(f.VL_TRANSACAO) DESC
    """, engine).to_string(index=False))

    print("\n== Classes de ativo ==")
    print(pd.read_sql("""
        SELECT a.TP_ATIVO, COUNT(DISTINCT a.SK_ATIVO) AS ativos,
               COUNT(*) AS lancamentos,
               CAST(SUM(CASE WHEN f.FL_RENDIMENTO = 'S' THEN f.VL_TRANSACAO ELSE 0 END)
                    AS decimal(18,2)) AS proventos_rs
        FROM gold.fato_investimento f
        JOIN gold.dim_ativo a ON a.SK_ATIVO = f.SK_ATIVO
        GROUP BY a.TP_ATIVO ORDER BY 4 DESC
    """, engine).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
