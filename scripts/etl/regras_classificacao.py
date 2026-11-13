"""
Alimenta as tres dimensoes de classificacao financeira.

gold.dim_area_financ, gold.dim_categoria_financ e gold.dim_grupo_financ
sao compartilhadas por gold.fato_movto_financ e gold.fato_familia, e as
duas cargas precisam alimenta-las de forma identica.

POR QUE ISTO E UM MODULO, E NAO CODIGO REPETIDO. Antes havia duas
funcoes quase iguais - sincroniza_dimensao() na carga de movimentacao e
sincroniza_categorias() na da familia - e elas divergiram: a correcao
de collation foi aplicada numa e esquecida na outra, e o defeito so
apareceu meses depois, quando uma origem nova trouxe duas caixas da
mesma combinacao. Uma implementacao so nao tem como divergir.
"""

import pandas as pd
from sqlalchemy import text

from util_dados import aplica_flags  # noqa: E402

NAO_CLASSIFICADO = "A classificar"

# (tabela, coluna de chave, coluna de nome, coluna de origem no DataFrame)
DIMENSOES = (
    ("dim_area_financ",      "SK_AREA_FINANC",      "NM_AREA",      "ds_area"),
    ("dim_categoria_financ", "SK_CATEGORIA_FINANC", "NM_CATEGORIA", "ds_categoria"),
    ("dim_grupo_financ",     "SK_GRUPO_FINANC",     "NM_GRUPO",     "ds_grupo"),
)


def chave(valor) -> str:
    """
    Forma comparavel, alinhada a collation do banco.

    O banco usa Latin1_General_CI_AS, que ignora caixa. Comparar em
    Python com distincao de caixa faz a carga achar que o membro e novo,
    tentar inserir, e o banco recusar por violacao de unicidade - foi
    exatamente o que aconteceu quando o historico 2014-2018 trouxe
    "Medicamento" e "Medicamentos" na mesma carga.
    """
    return str(valor).strip().upper() if valor is not None else ""


def sincroniza_classificacao(conn, dados: pd.DataFrame) -> tuple[dict, dict]:
    """
    Insere os membros novos nas tres dimensoes.

    Devolve ({nome_da_dimensao: {chave_comparavel: SK}}, {nome: novos}).
    A carga usa os mapas para resolver as tres chaves de cada linha do
    fato - a COMBINACAO vive no fato, e nao numa dimensao de trios.
    """
    mapas, novos = {}, {}

    for tabela, col_sk, col_nome, col_origem in DIMENSOES:
        def le():
            return pd.read_sql(
                f"SELECT {col_sk}, {col_nome} FROM gold.{tabela}", conn)

        existente = le()
        ja_tem = {chave(n) for n in existente[col_nome]}

        # Deduplica contra o banco E entre si: a canonizacao pode
        # devolver dois valores que so diferem na caixa, e os dois
        # colidiriam no insert mesmo nao existindo antes.
        vistos, novas_linhas = set(), []
        for valor in dados[col_origem].dropna().unique():
            k = chave(valor)
            if k and k not in ja_tem and k not in vistos:
                vistos.add(k)
                linha = {col_nome: valor}
                if tabela == "dim_categoria_financ":
                    linha["FL_CLASSIFICADO"] = valor != NAO_CLASSIFICADO
                novas_linhas.append(linha)

        if novas_linhas:
            # aplica_flags e obrigatorio aqui: FL_CLASSIFICADO e char(1)
            # com CHECK IN ('S','N') desde a padronizacao dos
            # indicadores, e este modulo gravava o booleano do Python.
            #
            # A carga quebrou por nove dias sem ninguem ver, porque o
            # INSERT so acontece quando aparece CATEGORIA NOVA - e ate
            # 05/09 nao apareceu nenhuma. Defeito que espera por dado
            # novo para se manifestar nao aparece no teste da mudanca.
            aplica_flags(pd.DataFrame(novas_linhas)).to_sql(
                tabela, conn, schema="gold", if_exists="append", index=False)
            existente = le()

        mapas[tabela] = {chave(n): sk for sk, n in
                         zip(existente[col_sk], existente[col_nome])}
        novos[tabela] = len(novas_linhas)

    return mapas, novos


def resolve_chaves(dados: pd.DataFrame, mapas: dict) -> dict:
    """
    Traduz area, categoria e grupo de cada linha nas tres chaves.

    Membro nao encontrado vira -1 em vez de erro: o fato prefere
    registrar "nao informado" a recusar o lancamento.
    """
    resultado = {}
    for tabela, col_sk, _, col_origem in DIMENSOES:
        mapa = mapas[tabela]
        resultado[col_sk] = [mapa.get(chave(v), -1) for v in dados[col_origem]]
    return resultado


def remove_membros_orfaos(conn) -> int:
    """
    Apaga membros que nenhum dos dois fatos referencia.

    Sem isto um rotulo abandonado - grafia corrigida na planilha, por
    exemplo - continuaria aparecendo como opcao de filtro no Power BI
    para sempre, sem nunca devolver linha.
    """
    total = 0
    for tabela, col_sk, _, _ in DIMENSOES:
        r = conn.execute(text(f"""
            DELETE FROM gold.{tabela}
             WHERE {col_sk} <> -1
               AND NOT EXISTS (SELECT 1 FROM gold.fato_movto_financ f
                                WHERE f.{col_sk} = gold.{tabela}.{col_sk})
               AND NOT EXISTS (SELECT 1 FROM gold.fato_familia f
                                WHERE f.{col_sk} = gold.{tabela}.{col_sk})
        """))
        total += max(r.rowcount, 0)
    return total
