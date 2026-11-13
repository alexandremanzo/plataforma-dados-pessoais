"""
Interpretacao da coluna OBS das planilhas como marcacoes (tags).

O campo nao e observacao livre: e um sistema de marcacao que atravessa
as tres origens financeiras. #AptoCentro e #Theo aparecem nas tres,
#Escola e #Sedan em duas. Isolado aqui porque as cargas da gold de
movimentacao e de familia precisam interpretar igual - se divergirem, a
mesma tag vira duas na dimensao.

DUAS CONVENCOES CONVIVEM NA ORIGEM:

  #Tag              -> #Nina, #Escola, #Praia_Out22
  ViagemNN_Local    -> Viagem07_Praia, Viagem06_Aguas Claras

E uma celula pode ter mais de uma marcacao:

  "#Praia-Out22 #AleLia"  -> duas tags, em 34 lancamentos

AS GRAFIAS NAO SAO UNIFICADAS, por decisao. Arraial aparece em sete
formas e so quem lancou sabe se sao a mesma viagem. Separar o que esta
junto e parsing; juntar o que esta separado seria palpite, e um palpite
errado somaria viagens diferentes.
"""

import re

import pandas as pd

# Tamanho e numero de palavras acima dos quais o texto sem "#" deixa de
# parecer marcacao. Calibrado no conteudo real: a maior tag legitima e
# "Viagem06_Aguas Claras" (21 caracteres, 2 palavras), e as duas
# observacoes de verdade tem 33 e 58 caracteres com 6 e 9 palavras.
LIMITE_CARACTERES = 30
LIMITE_PALAVRAS = 3

_RE_TAG = re.compile(r"#[^\s#]+")


def extrai_tags(valor) -> list[str]:
    """
    Devolve as marcacoes de uma celula de OBS.

    Sem "#", a celula inteira e uma marcacao - desde que curta o
    bastante para nao ser frase. Lista vazia significa que o campo foi
    usado como observacao de verdade, e o texto segue preservado na
    silver e na bronze - o fato guarda so a chave da tag principal.
    """
    # O NaN do pandas precisa ser barrado ANTES do str(): str(nan) e
    # "nan", que passa em todos os testes de tag - curto, sem espaco - e
    # marcaria como "nan" todo lancamento sem observacao. Foi o que
    # aconteceu na primeira execucao: 11.406 ligacoes para 2.280
    # lancamentos de fato marcados.
    if valor is None:
        return []
    try:
        if pd.isna(valor):
            return []
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()
    if not texto:
        return []

    if "#" in texto:
        return [t.strip() for t in _RE_TAG.findall(texto)]

    if len(texto) <= LIMITE_CARACTERES and len(texto.split()) <= LIMITE_PALAVRAS:
        return [texto]
    return []


def tipo_tag(nome: str) -> str:
    """
    Palpite sobre a natureza da marcacao, para apoiar a leitura.

    NAO e classificacao revisada: e heuristica sobre o proprio texto, e
    a dimensao aceita correcao por UPDATE. Serve para o relatorio poder
    separar viagem de imovel sem exigir cadastro manual de imediato.
    """
    limpo = nome.lstrip("#").strip()
    baixo = limpo.lower()

    if baixo.startswith("viagem"):
        return "Viagem"
    if baixo.startswith("apto") or baixo.startswith("apartamento"):
        return "Imóvel"
    # Destino seguido de mes/ano: #Serra_Nov23, #Praia-Out22.
    if re.search(r"[_\-](jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"
                 r"[a-z]*[_\-]?\d{2,4}$", baixo):
        return "Viagem"
    if re.search(r"(reveillon|natal|praia|serra|litoral|capital|interior|"
                 r"exterior|ilha|lago|campo|cachoeira)", baixo):
        return "Viagem"
    return "Marcação"


def tag_principal_por_hash(conn, nome_fato: str) -> dict:
    """
    {hash: SK_TAG} da tag PRINCIPAL de cada lancamento do fato.

    A REGRA DE DESEMPATE NAO ESTA AQUI, de proposito. Ela vive em
    gold.vw_tag_principal, criada pelo 46_fato_sk_tag.sql, e esta
    funcao so le. Reescrita em Python, a ordem de prioridade existiria
    em dois lugares e divergiria no primeiro ajuste - em silencio, ja
    que os dois lados continuariam devolvendo uma tag.

    Chamar DEPOIS de sincroniza_tag: a view le a ponte, e a ponte so
    esta correta quando as ligacoes do fato ja foram refeitas.
    """
    import pandas as pd

    df = pd.read_sql(
        "SELECT HASH_NEGOCIO, SK_TAG FROM gold.vw_tag_principal "
        f"WHERE DS_FATO = '{nome_fato}'", conn)
    return dict(zip(df["HASH_NEGOCIO"], df["SK_TAG"]))


def sincroniza_tag(conn, obs_por_hash: dict, nome_fato: str) -> tuple[int, int]:
    """
    Alimenta gold.dim_tag e gold.ponte_tag.

    Recebe {hash: texto do OBS} e cuida de tudo: extrai as tags,
    cadastra as que faltam na dimensao e refaz as ligacoes do fato.

    AS LIGACOES DESTE FATO SAO SUBSTITUIDAS, e nao acrescentadas.
    Tirar uma tag de um lancamento na planilha precisa desfazer a
    ligacao - se so inserisse o que falta, a marcacao removida ficaria
    para sempre, e o total da viagem nunca deixaria de conta-la.

    A dimensao nao e podada: uma tag que deixou de ser usada continua
    cadastrada, sem custo, e volta a funcionar se reaparecer.
    """
    import pandas as pd
    from sqlalchemy import text

    ligacoes = []
    for chave, texto in obs_por_hash.items():
        for tag in extrai_tags(texto):
            ligacoes.append((chave, tag))

    def le_dim():
        return pd.read_sql("SELECT SK_TAG, NM_TAG FROM gold.dim_tag",
                           conn)

    existente = le_dim()
    ja_tem = {str(n).strip().upper() for n in existente["NM_TAG"]}

    vistas, novas = set(), []
    for _, tag in ligacoes:
        k = tag.strip().upper()
        if k not in ja_tem and k not in vistas:
            vistas.add(k)
            novas.append({"NM_TAG": tag, "DS_TIPO": tipo_tag(tag)})

    if novas:
        pd.DataFrame(novas).to_sql("dim_tag", conn, schema="gold",
                                   if_exists="append", index=False)
        existente = le_dim()

    mapa = {str(n).strip().upper(): sk for sk, n in
            zip(existente["SK_TAG"], existente["NM_TAG"])}

    conn.execute(text("DELETE FROM gold.ponte_tag WHERE DS_FATO = :f"),
                 {"f": nome_fato})

    if ligacoes:
        # Deduplica: a mesma tag repetida na mesma celula e uma ligacao
        # so, e o UNIQUE do banco recusaria a segunda.
        linhas = {(h, mapa[t.strip().upper()]) for h, t in ligacoes}
        pd.DataFrame([{"HASH_NEGOCIO": h, "SK_TAG": sk, "DS_FATO": nome_fato}
                      for h, sk in linhas]).to_sql(
            "ponte_tag", conn, schema="gold", if_exists="append", index=False)
        return len(novas), len(linhas)
    return len(novas), 0
