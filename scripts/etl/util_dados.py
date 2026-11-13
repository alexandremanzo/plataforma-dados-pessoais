"""
Utilitarios compartilhados pelos carregadores das camadas silver e gold.

Reune o que estava duplicado em cada carga. Sao funcoes pequenas, mas
cada uma existe por causa de um problema concreto que ja apareceu no
projeto - os comentarios registram qual.
"""

import pandas as pd


def registra_carga(engine, tabela: str, inseridos: int, atualizados: int,
                   descartados=None, inicio=None) -> None:
    """
    Grava em gold.fato_carga o resultado desta execucao.

    O par (inseridos, atualizados) ja era calculado por todas as cargas
    e so ia para o terminal. Aqui ele passa a durar, o que permite ver a
    serie: uma carga que NUNCA converge tem defeito, e isso so aparece
    comparando execucoes.

    NUNCA DERRUBA A CARGA. Se o registro falhar - tabela ainda nao
    criada, banco ocupado - a carga que ja terminou com sucesso nao
    pode ser considerada falha por causa do log. O aviso vai para o
    terminal e a vida segue.

    tabela: nome qualificado, como "bronze.itau_movimentacao".
    inicio: time.monotonic() do comeco, para medir a duracao.
    """
    import sys
    import time
    from pathlib import Path

    from sqlalchemy import text

    camada = tabela.split(".")[0]
    segundos = round(time.monotonic() - inicio, 2) if inicio else None
    script = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else None

    try:
        with engine.begin() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
            conn.execute(text("""
                INSERT INTO gold.fato_carga
                    (SK_DATA, DT_EXECUCAO, DS_CAMADA, DS_TABELA, DS_SCRIPT,
                     NR_INSERIDOS, NR_ATUALIZADOS, NR_DESCARTADOS, NR_TOTAL,
                     NR_SEGUNDOS, FL_CONVERGIU)
                VALUES
                    (CAST(FORMAT(SYSDATETIME(), 'yyyyMMdd') AS int), SYSDATETIME(),
                     :camada, :tabela, :script,
                     :ins, :atu, :desc, :total, :seg, :conv)
            """), {
                "camada": camada, "tabela": tabela, "script": script,
                "ins": int(inseridos), "atu": int(atualizados),
                "desc": None if descartados is None else int(descartados),
                "total": total, "seg": segundos,
                "conv": flag(int(inseridos) == 0 and int(atualizados) == 0),
            })
    except Exception as erro:                      # noqa: BLE001
        print(f"  (aviso: nao consegui registrar a carga em gold.fato_carga: "
              f"{type(erro).__name__})")


SAIDA_SEM_DADOS = 99
"""
Codigo de saida que o Airflow entende como "pular", e nao como "falhar".

O BashOperator do Airflow 2.10 ja usa 99 por padrao em skip_on_exit_code:
a tarefa fica SKIPPED e, com a regra all_success, as seguintes do mesmo
ramo sao puladas junto. Nao foi preciso operador novo nem sensor - quem
decide e o proprio script, que e quem sabe o que encontrou.
"""


def sem_dados(engine, *tabelas: str) -> bool:
    """
    Diz se a bronze ficou vazia, e portanto nao ha o que propagar.

    POR QUE ISSO IMPORTA. A silver le a bronze e transforma. Sobre zero
    linhas a transformacao nao produz nada, e costuma quebrar antes
    disso: um groupby ou um idxmax sobre DataFrame vazio levanta
    excecao, e o erro que aparece no log fala de pandas, nao da origem
    que sumiu. Parar no ramo certo, com a tarefa marcada como pulada,
    diz a verdade sobre o que aconteceu.

    NAO CONFUNDA COM "+0 novos, 0 atualizados". Aquilo e o contrato de
    convergencia do projeto e e sinal de SAUDE - quer dizer que a
    origem nao mudou. O teste aqui e outro: a tabela nao tem linha
    nenhuma.

    Devolve True quando QUALQUER uma das tabelas esta vazia. Conservador
    de proposito: onde uma carga alimenta duas tabelas, como a do
    automovel, a segunda vazia ja compromete o que vem depois.
    """
    from sqlalchemy import text

    vazias = []
    for tabela in tabelas:
        try:
            with engine.connect() as conn:
                total = conn.execute(
                    text(f"SELECT COUNT(*) FROM {tabela}")).scalar()
        except Exception as erro:                      # noqa: BLE001
            # Nao conseguir contar nao e o mesmo que estar vazia. Na
            # duvida deixa seguir: um "pular" falso esconderia dado bom,
            # e o problema de verdade reaparece na camada seguinte.
            print(f"  (aviso: nao consegui contar {tabela}: "
                  f"{type(erro).__name__} - seguindo mesmo assim)")
            return False
        if not total:
            vazias.append(tabela)

    if not vazias:
        return False

    print()
    print(f"  SEM DADOS: {', '.join(vazias)} sem nenhuma linha apos a carga.")
    print(f"  As camadas seguintes deste ramo serao PULADAS (saida "
          f"{SAIDA_SEM_DADOS}).")
    print("  Isto nao e falha desta carga: nao ha o que transformar. "
          "Confira a origem.")
    return True

def normaliza_id(valor):
    """
    Forma canonica do ID digitado na planilha.

    POR QUE ISSO E NECESSARIO. O pandas escolhe o tipo da coluna pelo
    conteudo: onde ha linhas vazias na cauda, promove tudo para float e
    o ID 1 chega como 1.0; onde nao ha, mantem int e chega como 1. Como
    o hash e calculado sobre o texto, as duas leituras dariam hashes
    diferentes PARA O MESMO LANCAMENTO.

    Hoje as duas bases sao internamente consistentes, entao funciona.
    Mas basta apagar as linhas em branco da planilha do Itau para o
    pandas passar a ler int, e os 5.007 hashes mudariam de uma vez -
    tudo entraria como novo e tudo o que existe viraria orfao. E o
    mesmo defeito que a chave por ID veio corrigir, rearmado de outro
    jeito.

    Aqui 1, 1.0, "1" e "1.0" produzem sempre "1".
    """
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    # numpy.int64 e numpy.float64 respondem a .item(); str nao.
    if hasattr(valor, "item"):
        valor = valor.item()

    if isinstance(valor, bool):
        return str(valor).strip()
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else str(valor)

    texto = str(valor).strip()
    if not texto:
        return None
    # "1.0" digitado como texto tem o mesmo destino que 1.0 numerico.
    try:
        numero = float(texto)
    except ValueError:
        return texto
    return str(int(numero)) if numero.is_integer() else texto


def valida_id_origem(serie, coluna: str, base: str) -> None:
    """
    Recusa a carga quando o ID da planilha nao serve de chave.

    Falha alto de proposito. A alternativa - descartar a linha sem ID
    ou escolher uma das repetidas - perderia um lancamento em silencio,
    e num cadastro manual isso so apareceria meses depois, na
    conferencia que nao fecha. Melhor a carga parar e dizer onde.
    """
    if serie is None or serie.isna().all():
        raise ValueError(
            f"A planilha de {base} nao tem a coluna {coluna!r} preenchida.\n"
            f"  Ela e a chave de negocio desta base: acrescente a coluna e "
            f"numere as linhas.\n"
            f"  Ver docs/passo-a-passo/chave-id-cadastro-manual.md")

    sem_id = serie[serie.isna()]
    if len(sem_id):
        linhas = sorted(int(i) + 2 for i in sem_id.index[:10])
        raise ValueError(
            f"{len(sem_id)} linhas de {base} tem dados mas estao sem {coluna}.\n"
            f"  Linhas da planilha: {linhas}\n"
            f"  Preencha o {coluna} - sem ele o lancamento nao tem identidade.")

    repetidos = serie[serie.duplicated(keep=False)]
    if len(repetidos):
        exemplos = sorted(repetidos.unique())[:10]
        raise ValueError(
            f"{len(repetidos)} linhas de {base} tem {coluna} REPETIDO.\n"
            f"  Exemplos: {exemplos}\n"
            f"  Cada linha precisa de um numero unico, e um numero de linha "
            f"excluida nunca deve ser reaproveitado.")


def valor_sql(valor):
    """
    Normaliza um escalar para gravacao no banco e para comparacao.

    Converte tipos do numpy nos equivalentes Python. Isso importa por
    dois motivos: o driver ODBC lida melhor com escalares nativos, e
    isinstance(np.False_, bool) e False no numpy 2.x - o lado lido do
    banco vinha como np.False_ e o calculado como False, fazendo a
    deteccao de mudanca acusar diferenca em todo registro booleano e a
    carga nunca convergir.

    Ausencia de valor vira None: um NaN chegando em coluna de texto faz
    o driver recusar o comando inteiro.
    """
    if hasattr(valor, "item"):
        valor = valor.item()
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return int(valor) if isinstance(valor, bool) else valor


def texto_comparavel(valor) -> str:
    """
    Representacao estavel de um valor, para detectar mudanca real.

    Trata None e NaN como iguais, e normaliza floats inteiros para que
    100.0 e 100 nao sejam vistos como valores diferentes.
    """
    limpo = valor_sql(valor)
    if limpo is None:
        return ""
    if isinstance(limpo, float) and limpo.is_integer():
        return str(int(limpo))
    return str(limpo)


def canoniza(serie: pd.Series) -> pd.Series:
    """
    Unifica grafias do mesmo rotulo mantendo a forma mais usada.

    Na origem convivem "Casa" e "CASA", "Pessoal" e "PESSOAL", "TE",
    "Te" e "te". Sem unificar, viram membros distintos na dimensao - o
    mesmo defeito que duplicava lancamentos no modelo antigo de dbo.

    A forma escolhida e a mais frequente, e nao simplesmente a
    maiuscula: rotulos como "Movimentacao entre contas" ficariam
    ilegiveis em caixa alta no relatorio.
    """
    validos = serie.dropna()
    if validos.empty:
        return serie
    freq = validos.groupby(validos.str.upper()).agg(lambda s: s.value_counts().idxmax())
    return serie.map(lambda v: freq.get(v.upper(), v) if isinstance(v, str) else v)


def detecta_alteracoes(atual: pd.DataFrame, novo: pd.DataFrame,
                       chave: str, colunas: list[str]) -> list[dict]:
    """
    Compara o que esta gravado com o que foi recalculado.

    Devolve uma lista de dicionarios prontos para o executemany do
    UPDATE, contendo apenas as linhas em que alguma coluna mudou de
    fato. Sem isso, uma melhoria de regra nao alcancaria os registros
    ja carregados.
    """
    if atual.empty:
        return []

    antes = atual.set_index(chave)
    depois = novo[novo[chave].isin(antes.index)].set_index(chave)

    alteracoes = []
    for identificador, linha in depois.iterrows():
        anterior = antes.loc[identificador]
        if any(texto_comparavel(linha[c]) != texto_comparavel(anterior[c])
               for c in colunas):
            alteracoes.append(
                {"chave": identificador,
                 **{c: valor_sql(linha[c]) for c in colunas}}
            )
    return alteracoes


def flag(valor):
    """
    Converte um indicador para o dominio S/N da camada gold.

    OS ATRIBUTOS FL_ DA GOLD SAO char(1), e nao bit: eles sao lidos por
    gente e por relatorio, e "S" dispensa traducao onde "1" a exige.
    Bronze e silver seguem em bit - a conversao acontece aqui, no mesmo
    lugar onde texto vira data e virgula vira ponto.

    NULO CONTINUA SENDO NULO, e isso e o mais importante desta funcao.
    FL_ADERENCIA e nulo nos habitos de contexto e FL_MELHOROU e nulo
    quando nao houve medida anterior: transformar essa ausencia em "N"
    diria que a meta nao foi cumprida, quando ela nem foi apurada.
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        limpo = valor.strip().upper()
        return limpo if limpo in ("S", "N") else None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    # numpy.bool_ nao passa em isinstance(x, bool) no numpy 2.x, entao a
    # conversao e por verdade e nao por tipo.
    return "S" if bool(valor) else "N"


def aplica_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Passa toda coluna FL_ do DataFrame pelo dominio S/N.

    Uma chamada por carga, logo antes de gravar, em vez de lembrar de
    converter campo a campo. Colunas que ja estao em S/N atravessam sem
    mudanca, o que torna a funcao segura de aplicar duas vezes.
    """
    for coluna in df.columns:
        if str(coluna).upper().startswith("FL_"):
            df[coluna] = df[coluna].map(flag)
    return df
