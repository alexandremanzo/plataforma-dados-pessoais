"""
Confere o modelo gerado SEM abrir o Power BI Desktop.

POR QUE EXISTE. As 36 medidas se referenciam umas as outras pelo nome,
escrito a mao. Uma letra trocada em [Receita total] nao quebra a
geracao, nao quebra a validacao de schema (que so olha a FORMA do JSON,
nao o conteudo do DAX) e so aparece ao abrir o projeto — numa janela de
erro que cita o modelo inteiro e nao a medida culpada.

O mesmo vale para o relatorio: um visual pode projetar uma medida que
nao existe, e o Power BI desenha o visual vazio sem reclamar.

O que e conferido:
  1. toda medida citada dentro de outra medida existe
  2. toda coluna citada no DAX existe na tabela citada
  3. toda medida e toda coluna projetada num visual existem
  4. todo sortByColumn aponta para uma coluna da propria tabela
  5. todo relacionamento aponta para tabela.coluna que existem
  6. todo bloco M tem let/in e delimitadores balanceados

Uso:
    python conferir_modelo.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import gerar_painel as g

MODELO = g.BASE / f"{g.PROJETO}.SemanticModel" / "definition"
RELATORIO = g.BASE / f"{g.PROJETO}.Report" / "definition"

# Funcoes do DAX que nao sao medida e aparecem entre colchetes quando
# alguem erra a sintaxe. Nada aqui hoje; a lista existe para o dia em
# que uma excecao legitima aparecer e nao virar "ignore o alarme".
PERMITIDAS: set = set()


def tabelas() -> dict:
    """tabela -> {colunas}, lendo os .tmdl gerados."""
    saida = {}
    for arq in sorted((MODELO / "tables").glob("*.tmdl")):
        texto = arq.read_text(encoding="utf-8")
        cols = {m.group(1).strip("'")
                for m in re.finditer(r"^\tcolumn ('[^']+'|\S+)", texto, re.M)}
        saida[arq.stem] = cols
    return saida


# O corpo de uma medida termina onde comeca o proximo item da TABELA —
# outra medida, uma coluna, a partition. Sem esse corte, o corpo da
# ULTIMA medida engole o M da propria tabela, e o
# #table(type table [Marcador = Int64.Type]) do _Medidas vira uma
# "coluna inexistente" denunciada na medida errada. Alarme falso treina
# a ignorar o alarme.
FIM_DE_MEDIDA = re.compile(r"^\t(?:///|measure |column |partition |annotation )")


def medidas() -> dict:
    """medida -> corpo do DAX."""
    texto = (MODELO / "tables" / "_Medidas.tmdl").read_text(encoding="utf-8")
    saida = {}
    for p in re.split(r"^\tmeasure ", texto, flags=re.M)[1:]:
        nome = re.match(r"('[^']+'|\S+)", p).group(1).strip("'")
        linhas = p.split("\n")
        corpo = []
        for l in linhas[1:]:
            if FIM_DE_MEDIDA.match(l):
                break
            corpo.append(l)
        saida[nome] = linhas[0] + "\n" + "\n".join(corpo)
    return saida


def refs_de_medida(corpo: str) -> set:
    """[Nome] solto, sem tabela antes — e assim que o DAX cita medida."""
    corpo = re.sub(r"//[^\n]*", "", corpo)       # comentarios
    corpo = re.sub(r"\"(?:[^\"]|\"\")*\"", '""', corpo)   # strings
    return {m.group(1) for m in re.finditer(r"(?<![\w'\]])\[([^\]]+)\]", corpo)}


def refs_de_coluna(corpo: str) -> set:
    """Tabela[Coluna]."""
    corpo = re.sub(r"//[^\n]*", "", corpo)
    corpo = re.sub(r"\"(?:[^\"]|\"\")*\"", '""', corpo)
    return {(m.group(1), m.group(2))
            for m in re.finditer(r"(\w+)\[([^\]]+)\]", corpo)}


COMPARA_COM_MEDIDA = re.compile(
    r"\w+\[[^\]]+\]\s*(?:<>|<=|>=|=|<|>)\s*\[([^\]]+)\]")


def funcao_que_envolve(texto: str, pos: int) -> str:
    """O nome da funcao cujo parentese contem a posicao dada.

    Anda para tras contando parenteses ate a profundidade ficar
    negativa: ali esta o '(' que abriu o argumento onde a expressao
    mora. O identificador imediatamente antes dele e a funcao.
    """
    nivel = 0
    for i in range(pos - 1, -1, -1):
        c = texto[i]
        if c == ")":
            nivel += 1
        elif c == "(":
            if nivel == 0:
                m = re.search(r"(\w+)\s*$", texto[:i])
                return (m.group(1) if m else "").upper()
            nivel -= 1
    return ""


def predicados_invalidos(corpo: str) -> list:
    """Medida citada em predicado booleano de CALCULATE.

    POR QUE ISTO E UM TESTE E NAO UM DETALHE. O DAX proibe citar medida
    num predicado booleano de CALCULATE, e recusa a medida inteira — mas
    a geracao nao falha, o schema valida e os arquivos saem perfeitos.
    O erro so aparece ao abrir o Desktop, e aparece como visual vazio
    pedindo "selecione ou adicione dados", sem dizer qual medida nem por
    que. Aconteceu com as 18 medidas que filtravam pelo mes de
    referencia.

    Dentro de FILTER a mesma escrita e LEGAL, porque FILTER recebe uma
    tabela e nao um predicado — por isso a funcao que envolve a
    comparacao e consultada, em vez de acusar o padrao em qualquer
    lugar.
    """
    limpo = re.sub(r"//[^\n]*", "", corpo)
    limpo = re.sub(r"\"(?:[^\"]|\"\")*\"", '""', limpo)
    saida = []
    for m in COMPARA_COM_MEDIDA.finditer(limpo):
        if funcao_que_envolve(limpo, m.start()) in ("CALCULATE", "CALCULATETABLE"):
            saida.append(m.group(1))
    return saida


def blocos_m() -> list:
    """(tabela, linhas do M) de cada partition."""
    saida = []
    for arq in sorted((MODELO / "tables").glob("*.tmdl")):
        texto = arq.read_text(encoding="utf-8")
        # O conteudo do bloco vem recuado em QUATRO tabs, e o fecho
        # tambem — e o que pbir.bloco() emite no nivel da partition.
        m = re.search(r"\tpartition .* = m\n\t\tmode: import\n"
                      r"\t\tsource = ```\n(.*?)\n\t{4}```", texto, re.S)
        if m:
            saida.append((arq.stem, m.group(1)))
    return saida


def fora_de_string(linha: str) -> str:
    """Tira o conteudo das strings antes de contar delimitador.

    Sem isso, um parentese dentro de um comentario ou de um literal de
    texto acusaria desbalanceamento que nao existe.
    """
    saida, dentro, i = [], False, 0
    while i < len(linha):
        c = linha[i]
        if c == '"':
            if dentro and i + 1 < len(linha) and linha[i + 1] == '"':
                i += 2
                continue
            dentro = not dentro
        elif not dentro:
            saida.append(c)
        i += 1
    return "".join(saida)


def main() -> int:
    tabs, meds = tabelas(), medidas()
    erros = []

    def col_existe(tabela: str, coluna: str) -> bool:
        return tabela in tabs and coluna in tabs[tabela]

    # 1 e 2 — referencias dentro do DAX --------------------------------
    for nome, corpo in meds.items():
        dax = corpo.split("formatString:")[0]
        for ref in refs_de_medida(dax) - {nome}:
            if ref not in meds and ref not in PERMITIDAS:
                erros.append(f"medida '{nome}' cita [{ref}], que não existe")
        for tabela, coluna in refs_de_coluna(dax):
            if not col_existe(tabela, coluna):
                erros.append(f"medida '{nome}' cita {tabela}[{coluna}], "
                             f"que não existe")
        for alvo in predicados_invalidos(dax):
            erros.append(f"medida '{nome}' compara coluna com a medida "
                         f"[{alvo}] dentro de um predicado de CALCULATE — "
                         f"o DAX recusa; passe por uma VAR")

    # 3 — projecoes dos visuais ----------------------------------------
    for arq in sorted(RELATORIO.rglob("visual.json")):
        v = json.loads(arq.read_text(encoding="utf-8"))
        texto = json.dumps(v, ensure_ascii=False)
        for m in re.finditer(r'"Measure":\s*\{[^}]*?"Entity":\s*"([^"]+)"[^}]*?\}'
                             r',\s*"Property":\s*"([^"]+)"', texto):
            if m.group(2) not in meds:
                erros.append(f"{arq.parent.name} projeta a medida "
                             f"'{m.group(2)}', que não existe")
        for m in re.finditer(r'"Column":\s*\{[^}]*?"Entity":\s*"([^"]+)"[^}]*?\}'
                             r',\s*"Property":\s*"([^"]+)"', texto):
            if not col_existe(m.group(1), m.group(2)):
                erros.append(f"{arq.parent.name} projeta "
                             f"{m.group(1)}[{m.group(2)}], que não existe")
        # O seletor por metadata carrega o nome da medida em texto: erra
        # calado, pintando a serie errada ou nenhuma.
        for m in re.finditer(r'"metadata":\s*"_Medidas\.([^"]+)"', texto):
            if m.group(1) not in meds:
                erros.append(f"{arq.parent.name} tem seletor para a medida "
                             f"'{m.group(1)}', que não existe")

    # 4 — sortByColumn --------------------------------------------------
    for arq in sorted((MODELO / "tables").glob("*.tmdl")):
        texto = arq.read_text(encoding="utf-8")
        for m in re.finditer(r"sortByColumn: ('[^']+'|\S+)", texto):
            alvo = m.group(1).strip("'")
            if alvo not in tabs[arq.stem]:
                erros.append(f"{arq.stem} ordena por '{alvo}', que não é "
                             f"coluna da tabela")

    # 5 — relacionamentos -----------------------------------------------
    rel = (MODELO / "relationships.tmdl").read_text(encoding="utf-8")
    for m in re.finditer(r"(from|to)Column: (\w+)\.('[^']+'|\S+)", rel):
        if not col_existe(m.group(2), m.group(3).strip("'")):
            erros.append(f"relacionamento aponta para {m.group(2)}."
                         f"{m.group(3)}, que não existe")

    # 6 — sintaxe do M ---------------------------------------------------
    for tabela, corpo in blocos_m():
        util = [l for l in corpo.split("\n") if l.strip()]
        if util[0].strip() != "let":
            erros.append(f"M de {tabela} não começa com 'let'")
        if not any(l.strip() == "in" for l in util):
            erros.append(f"M de {tabela} não tem 'in'")
            continue
        i = next(k for k, l in enumerate(util) if l.strip() == "in")
        if util[i - 1].rstrip().endswith(","):
            erros.append(f"M de {tabela} tem vírgula antes de 'in'")
        limpo = "".join(fora_de_string(re.sub(r"//[^\n]*", "", l)) for l in util)
        for abre, fecha, rot in (("(", ")", "parênteses"), ("{", "}", "chaves"),
                                 ("[", "]", "colchetes")):
            if limpo.count(abre) != limpo.count(fecha):
                erros.append(f"M de {tabela}: {rot} desbalanceados "
                             f"({limpo.count(abre)} x {limpo.count(fecha)})")

    # --- resultado ------------------------------------------------------
    print(f"  tabelas           {len(tabs)}")
    print(f"  colunas           {sum(len(c) for c in tabs.values())}")
    print(f"  medidas           {len(meds)}")
    print(f"  visuais           {len(list(RELATORIO.rglob('visual.json')))}")
    print(f"  blocos M          {len(blocos_m())}")
    print()
    for e in erros:
        print(f"  ERRO  {e}")
    if erros:
        print(f"\n{len(erros)} problema(s).")
        return 1
    print("Modelo e relatório consistentes: toda referência resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
