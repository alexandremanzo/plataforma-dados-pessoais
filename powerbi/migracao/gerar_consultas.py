"""
Gera a consulta SQL de cada tabela do relatorio pessoal.

A migracao e FIEL: o relatorio passa a ler o banco em vez do arquivo, e
nao muda um numero. Por isso a origem e a BRONZE, que e a copia sem
transformacao da planilha - o gold curou o dado (tirou saldo de conta,
tirou margem, fundiu o InBody) e usa-lo mudaria valores na tela.

O DE-PARA DE NOMES NAO E DIGITADO AQUI. Cada carga_bronze_*.py ja tem o
dicionario COLUNAS que mapeia o cabecalho original da planilha para a
coluna da bronze; este script inverte esse dicionario. Se a planilha
ganhar uma coluna, o de-para nasce certo na carga e chega aqui sozinho -
em vez de existir em dois lugares e divergir no primeiro descuido.

O CONTRATO VEM DO PROPRIO MODELO. As colunas exigidas sao as declaradas
em cada .tmdl. Coluna que o relatorio espera e a bronze nao tem e
denunciada, nao silenciada: e a unica forma de a migracao falhar de modo
visivel em vez de devolver nulo.

Uso:
    python gerar_consultas.py
    python gerar_consultas.py f_dados_itau
"""

from __future__ import annotations

import ast
import re
import sys
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
ETL = RAIZ / "scripts" / "etl"
MODELO = Path(os.getenv("PATH_MODELO_PBI", "powerbi/legado"))

# tabela do relatorio -> (tabela bronze, script de carga com o de-para,
#                         filtro opcional, distinct)
FONTES = {
    "f_dados_itau":           ("bronze.itau_movimentacao",   "carga_bronze_itau.py"),
    "f_dados_credito_xp":     ("bronze.cartao_xp",           "carga_bronze_cartao_xp.py"),
    "f_dados_credito_nubank": ("bronze.cartao_nubank",       "carga_bronze_cartao_nubank.py"),
    "f_dados_alelia":        ("bronze.familia_movimentacao", "carga_bronze_familia.py"),
    "f_auto":                 ("bronze.auto_manutencao",     "carga_bronze_auto.py"),
    "f_auto_tempo_troca":     ("bronze.auto_intervalo_troca", "carga_bronze_auto.py"),
    "f_avaliacao_fisica":     ("bronze.avaliacao_fisica",    "carga_bronze_avaliacao.py"),
}

# De-paras que a inversao automatica nao resolve, com o motivo de cada um.
# Sao poucos e explicitos de proposito: um mapa silencioso aqui viraria
# coluna trocada na tela.
MAPA_EXTRA = {
    # A carga do Nubank le o CSV cru; o relatorio le a planilha tratada e
    # renomeia depois. "title" e o texto da compra, "Valor" e o tratado.
    "f_dados_credito_nubank": {"title": "ds_titulo", "Valor": "ds_valor"},
    # A carga do XP nao tem dicionario COLUNAS: renomeia em linha, em dois
    # lugares. "Acao" tem o mesmo erro de digitacao na origem e no modelo.
    "f_dados_invest_xp": {
        "Movimentação": "ds_movimentacao", "Liquidação": "ds_liquidacao",
        "Lançamento": "ds_lancamento", "Valor (R$)": "ds_valor",
        "Saldo (R$)": "ds_saldo", "Categoria": "ds_categoria_origem",
        "Rendimento": "ds_rendimento_origem", "Açao": "ds_ativo_origem",
    },
    # A aba "Tempo Troca" e lida por posicao, nao por cabecalho.
    "f_auto_tempo_troca": {"CATEGORIA": "ds_categoria",
                           "Tempo Util KM": "ds_intervalo_km"},
}

# Colunas que a bronze NAO tem, com o porque. Voltam nulas e isso fica
# escrito na consulta - nulo sem explicacao e o que faz alguem perder uma
# tarde.
SEM_NA_BRONZE = {
    "f_dados_credito_nubank": {
        "amount": "a carga guardou so o valor tratado; o bruto do CSV nao entrou",
    },
}

# Colunas que nao vem da origem: os passos seguintes do M as criam
# (renomeacao, coluna condicional). Como a migracao troca so o passo da
# FONTE e preserva o resto da cadeia, elas continuam nascendo sozinhas.
PRODUZIDAS_NO_M = {
    "f_dados_credito_nubank": {"Descrição", "Valor Trat"},
    "f_dados_alelia": {"ind_familia"},
    "f_dados_invest_xp": {"Data Movimentacao", "Tipo Movimento"},
}

# Tabelas que nao podem migrar: a planilha nunca entrou no lake.
COLUNAS_ADICIONAIS = {
    "f_dados_credito_nubank": [
        ("ds_titulo", "title", None),
        (None, "amount",
         "a carga guardou so o valor tratado; o bruto do CSV nao entrou"),
    ],
}

SEM_ORIGEM = {
    "d_Categoria": "dados-parametro.xlsx, aba CATEGORIA",
    "f_dados_invest_xp": "coluna 'fator' de dados-xp-consolidado.xlsx nunca entrou na bronze, e visuais a usam",
    "f_auto_km": "pla-revisao-auto.xls, aba Quilometragem",
    "f_dados_escola": "dados-escola.xlsx, aba META",
}


def de_para(script: str) -> dict:
    """Le o dicionario COLUNAS de um carga_bronze_*.py e o inverte.

    Sem importar o modulo: ele exige .env, conexao e pacotes que esta
    maquina pode nao ter. O dicionario e literal, entao ast resolve.
    """
    txt = (ETL / script).read_text(encoding="utf-8")
    m = re.search(r"^COLUNAS\s*=\s*(\{.*?^\})", txt, re.M | re.S)
    if not m:
        raise ValueError(f"{script} nao tem dicionario COLUNAS literal")
    d = ast.literal_eval(m.group(1))
    invertido = {}
    for original, bronze in d.items():
        invertido.setdefault(bronze, original)
    return invertido


def tipos_do_m(tabela: str) -> dict:
    """Le do M quais colunas sao tipadas, e para que tipo.

    POR QUE ISTO E OBRIGATORIO. A bronze guarda numero como texto em
    formato INVARIANTE ("300.00", ponto decimal) e o modelo e pt-BR, onde
    o ponto e separador de milhar. Devolver o texto faria o
    Table.TransformColumnTypes ler 300.00 como 30000 - erro de cem vezes,
    sem mensagem nenhuma. Com o tipo ja pronto no SQL, o passo do M vira
    inocuo, que e exatamente o que ele era quando a origem era o Excel.
    """
    txt = (MODELO / f"{tabela}.tmdl").read_text(encoding="utf-8")
    mapa = {}
    # Cada par vem como {"Nome da coluna", type date}. O nome nao contem
    # aspas, entao [^"]+ basta e dispensa escape dentro da classe.
    for col, tipo in re.findall(r'\{"([^"]+)",\s*([^}]+)\}', txt):
        tipo = tipo.strip()
        if tipo.startswith("type ") or tipo.endswith(".Type"):
            mapa[col] = tipo
    return mapa


SQL_POR_TIPO = {
    "type date": "date",
    "type datetime": "datetime2",
    "type number": "float",
    "Int64.Type": "bigint",
}


def colunas_do_modelo(tabela: str) -> list:
    """Colunas que o relatorio declara, na ordem, fora as calculadas."""
    txt = (MODELO / f"{tabela}.tmdl").read_text(encoding="utf-8")
    saida = []
    for m in re.finditer(r"^\tcolumn ('[^']+'|\S+)([^\n]*)\n((?:\t\t[^\n]*\n)*)",
                         txt, re.M):
        nome = m.group(1).strip("'")
        if "=" in m.group(2):          # coluna calculada: vem do DAX
            continue
        fonte = re.search(r"sourceColumn: (.+)", m.group(3))
        saida.append((nome, (fonte.group(1).strip() if fonte else nome)))
    return saida


def monta(tabela: str) -> tuple[str, list]:
    bronze, script = FONTES[tabela]
    try:
        inverso = {v: k for k, v in de_para(script).items()}
    except ValueError:
        inverso = {}                 # carga sem dicionario: so o MAPA_EXTRA
    inverso.update(MAPA_EXTRA.get(tabela, {}))
    faltam = SEM_NA_BRONZE.get(tabela, {})
    do_m = PRODUZIDAS_NO_M.get(tabela, set())
    tipos = tipos_do_m(tabela)

    linhas, ausentes = [], []
    for nome, fonte in colunas_do_modelo(tabela):
        if fonte in faltam:
            linhas.append(f"        CAST(NULL AS varchar(1)){' ':<3} AS [{fonte}]"
                          f"   /* {faltam[fonte]} */")
            continue
        if fonte in do_m:
            continue                 # nasce num passo posterior do M
        col = inverso.get(fonte)
        if col is None:
            ausentes.append(fonte)
            continue
        alvo = SQL_POR_TIPO.get(tipos.get(fonte, ""))
        if alvo:
            expr = f"TRY_CAST({col} AS {alvo})"
            linhas.append(f"        {expr:<44} AS [{fonte}]")
        else:
            linhas.append(f"        {col:<44} AS [{fonte}]")

    # Colunas que o SQL precisa devolver com o nome ANTERIOR ao rename do
    # M: o passo seguinte da cadeia renomeia "title" para "Descricao" e
    # "amount" para "Valor". Entregar ja o nome final faria o rename
    # procurar uma coluna que nao existe, e a consulta quebraria.
    for col, nome, nota in COLUNAS_ADICIONAIS.get(tabela, []):
        expr = col if col else "CAST(NULL AS varchar(1))"
        sufixo = f"   /* {nota} */" if nota else ""
        linhas.append(f"        {expr:<44} AS [{nome}]{sufixo}")

    sql = (f"/* {tabela} <- {bronze}\n"
           f"   Gerado por gerar_consultas.py a partir do de-para de {script}.\n"
           f"   Migracao FIEL: a bronze e a copia sem transformacao da planilha,\n"
           f"   entao nenhum numero do relatorio muda. */\n\n"
           "SELECT\n" + ",\n".join(linhas) + f"\nFROM {bronze}\n")
    return sql, ausentes


def main() -> int:
    alvo = sys.argv[1] if len(sys.argv) > 1 else None
    destino = BASE
    problemas = 0

    for tabela in FONTES:
        if alvo and tabela != alvo:
            continue
        try:
            sql, ausentes = monta(tabela)
        except Exception as e:                            # noqa: BLE001
            print(f"  ERRO {tabela}: {type(e).__name__} {e}")
            problemas += 1
            continue
        (destino / f"{tabela}.sql").write_text(sql, encoding="utf-8")
        n = sql.count(" AS [")
        marca = f"  <-- {len(ausentes)} coluna(s) sem origem: {ausentes}" if ausentes else ""
        print(f"  {tabela:<24} {n:>2} colunas{marca}")
        problemas += len(ausentes)

    if not alvo:
        print("\n=== sem origem no lake (nao da para migrar ainda) ===")
        for t, onde in SEM_ORIGEM.items():
            print(f"  {t:<24} {onde}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
