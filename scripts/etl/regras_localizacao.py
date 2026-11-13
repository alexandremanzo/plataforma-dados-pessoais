"""
Resolucao do lugar de um lancamento para gold.dim_localizacao.

Isolado aqui pelo mesmo motivo de regras_tag.py: as cargas da gold de
movimentacao e de familia precisam interpretar igual. Se divergirem -
uma aparando espaco e a outra nao, uma tratando "" como nulo e a outra
como texto -, o MESMO lugar vira dois membros na dimensao, e o total de
Cidade A passa a sair dividido em duas linhas sem ninguem notar.

AS GRAFIAS NAO SAO UNIFICADAS, por decisao registrada no
45_dim_localizacao.sql: a mesma cidade aparece sob UF diferente em 53
lancamentos, e so quem lancou sabe se foi engano. Grafia nova vira
membro novo, e a conferencia do script 45 lista as cidades com mais de
uma UF toda vez que ele roda.

O que esta funcao FAZ e normalizar ausencia: None, NaN e texto vazio
sao a mesma coisa - lugar nao informado - e precisam cair no mesmo
membro. O que ela NAO faz e adivinhar que "Cidade A/DF" queria dizer
"Cidade A/MG".
"""

from __future__ import annotations

import pandas as pd

# O membro que representa ausencia, criado pelo 45_dim_localizacao.sql.
SK_NAO_INFORMADO = -1


def _texto(valor) -> str | None:
    """None, NaN e '' viram None; o resto vira texto aparado."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    s = str(valor).strip()
    return s or None


def trio(cidade, uf, pais) -> tuple:
    """O trio como vai para o banco: aparado, com a grafia original."""
    return (_texto(cidade), _texto(uf), _texto(pais))


def chave(cidade, uf, pais) -> tuple:
    """
    A chave de COMPARACAO - a mesma igualdade que o banco usa.

    A collation e Latin1_General_CI_AS: IGNORA caixa, RESPEITA acento.
    Comparar em Python de forma sensivel a caixa fazia "serra Alta"
    parecer ausente quando a dimensao ja tinha "Serra Alta", e a
    insercao batia no UNIQUE - a carga da familia quebrou exatamente
    assim. O .upper() preserva o acento, entao "Goiania" e "Goiânia"
    seguem distintas, como no banco.
    """
    return tuple(None if v is None else v.upper()
                 for v in trio(cidade, uf, pais))


def sincroniza_localizacao(conn, trios) -> tuple[int, dict]:
    """
    Cadastra os lugares que faltam e devolve (novos, {chave: SK}).

    A dimensao NAO e podada: um lugar que deixou de aparecer continua
    cadastrado, sem custo, e volta a funcionar se reaparecer. Podar
    quebraria a chave estrangeira dos lancamentos historicos.
    """
    def le_dim():
        return pd.read_sql(
            "SELECT SK_LOCALIZACAO, NM_CIDADE, SG_UF, NM_PAIS "
            "FROM gold.dim_localizacao", conn)

    def mapa_de(df):
        return {chave(c, u, p): sk for sk, c, u, p in
                zip(df["SK_LOCALIZACAO"], df["NM_CIDADE"],
                    df["SG_UF"], df["NM_PAIS"])}

    mapa = mapa_de(le_dim())

    # A chave compara sem caixa; o VALOR guarda a grafia original, que e
    # a que vai para a dimensao. Duas grafias do mesmo lugar na mesma
    # carga entram uma vez so, e a primeira vista e a que fica - mesmo
    # criterio do banco, onde a segunda bateria no UNIQUE.
    #
    # (None, None, None) ja e o membro -1: nunca entra como lugar novo,
    # senao a dimensao ganharia um segundo "Não informado" por carga.
    faltam: dict = {}
    for t in trios:
        k = chave(*t)
        if k not in mapa and k != (None, None, None) and k not in faltam:
            faltam[k] = trio(*t)

    if faltam:
        pd.DataFrame([{"NM_CIDADE": c, "SG_UF": u, "NM_PAIS": p}
                      for c, u, p in sorted(
                          faltam.values(),
                          key=lambda v: tuple(x or "" for x in v))]
                     ).to_sql("dim_localizacao", conn, schema="gold",
                              if_exists="append", index=False)
        mapa = mapa_de(le_dim())

    return len(faltam), mapa


def resolve(mapa: dict, cidade, uf, pais) -> int:
    """A SK do lugar, ou -1 quando nao ha lugar informado."""
    return mapa.get(chave(cidade, uf, pais), SK_NAO_INFORMADO)
