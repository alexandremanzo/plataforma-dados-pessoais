"""
Confere a sintaxe do M de cada tabela do .tmdl, antes de abrir o Desktop.

Existe porque o Power BI so reclama de M invalido no MOMENTO DE ABRIR o
projeto - e reclama do projeto inteiro, sem dizer a tabela. Uma virgula
sobrando custou uma tentativa frustrada e uma janela de erro com
trezentas linhas de stack trace que nao citam o arquivo culpado.

Nao e um parser de M: e um conjunto de armadilhas conhecidas, cada uma
correspondendo a um erro que o mecanismo devolve sem localizacao util.

Uso:
    python conferir_m.py
"""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path

MODELO = Path(os.getenv("PATH_MODELO_PBI", "powerbi/legado"))


def bloco_m(texto: str) -> list | None:
    """As linhas do corpo do M, do 'let' ate a expressao final.

    Procura o 'let' SO DEPOIS de 'partition ... = m'. Sem esse escopo, a
    varredura pega tambem os 'let' que aparecem dentro de descricao de
    coluna - ha tabela aqui com um script M inteiro escrito na
    documentacao, e ele nao e codigo que roda.
    """
    linhas = texto.split("\n")
    try:
        part = next(i for i, l in enumerate(linhas)
                    if re.match(r"\s*partition .* = m\s*$", l))
    except StopIteration:
        return None                    # tabela calculada: nao tem M
    # Pula comentario: ha tabela cujo M comeca com um template inteiro
    # comentado, e o primeiro 'let' do arquivo esta la dentro. Conferir
    # codigo morto geraria alarme falso, e alarme falso treina a ignorar
    # o alarme.
    em_bloco = False
    ini = None
    for i in range(part, len(linhas)):
        s = linhas[i].strip()
        if em_bloco:
            em_bloco = "*/" not in s
            continue
        if s.startswith("/*") or s.startswith("///*"):
            em_bloco = "*/" not in s[2:]
            continue
        if s.startswith("//"):
            continue
        if s == "let":
            ini = i
            break
    if ini is None:
        return None
    fim = next((i for i, l in enumerate(linhas[ini:], ini)
                if l.strip() in ("```", "")), len(linhas))
    return linhas[ini:fim]


def fora_de_string(linha: str) -> str:
    """Remove o conteudo das strings, para contar delimitador com seguranca.

    Em M a aspa dupla e escapada dobrando-a, entao "" dentro de string nao
    fecha nada. Tirar as strings antes de contar parentese evita acusar
    desbalanceamento que so existe no texto do SQL embutido.
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


def confere(nome: str) -> list:
    texto = (MODELO / f"{nome}.tmdl").read_text(encoding="utf-8")
    corpo = bloco_m(texto)
    if corpo is None:
        return []                      # tabela sem partition m (calculada)

    erros = []
    util = [l for l in corpo if l.strip()]

    # 1. virgula antes de 'in' - o erro que ja aconteceu
    for i, l in enumerate(util):
        if l.strip() == "in" and i > 0 and util[i - 1].rstrip().endswith(","):
            erros.append("virgula antes de 'in'")

    # 2. let/in presentes e na ordem
    if util[0].strip() != "let":
        erros.append("nao comeca com 'let'")
    if not any(l.strip() == "in" for l in util):
        # Sem 'in' nao ha o que conferir adiante: ou a partition e de uma
        # linha so, ou o bloco terminou antes do que eu esperava. As duas
        # coisas merecem aparecer, e nenhuma justifica quebrar a varredura.
        erros.append("nao tem 'in' (bloco de uma linha ou corte inesperado)")
        return erros

    # 3. delimitadores balanceados, ignorando o que esta dentro de string
    limpo = "".join(fora_de_string(l) for l in util)
    for abre, fecha, rot in (("(", ")", "parenteses"), ("{", "}", "chaves"),
                             ("[", "]", "colchetes")):
        if limpo.count(abre) != limpo.count(fecha):
            erros.append(f"{rot} desbalanceados "
                         f"({limpo.count(abre)} x {limpo.count(fecha)})")

    # 4. aspas em numero par por linha
    for l in util:
        if fora_de_string(l) is None or l.count('"') % 2:
            if l.replace('""', '').count('"') % 2:
                erros.append(f"aspas impares: {l.strip()[:60]}")

    # 5. a expressao depois de 'in' e um passo que existe
    idx = next(i for i, l in enumerate(util) if l.strip() == "in")
    if idx + 1 < len(util):
        final = util[idx + 1].strip()
        passos = {re.match(r"\s*(#\"[^\"]+\"|\w+)\s*=", l).group(1)
                  for l in util[1:idx] if re.match(r"\s*(#\"[^\"]+\"|\w+)\s*=", l)}
        if final not in passos:
            erros.append(f"'in {final[:40]}' nao corresponde a nenhum passo")
    else:
        erros.append("'in' sem expressao depois")

    return erros


# So as tabelas cuja fonte eu troquei. As demais nao foram alteradas e
# ja abriam no Desktop; algumas tem M com "let" aninhado, que um
# conferidor por linha nao sabe ler - varre-las so produziria alarme
# falso, e alarme falso treina a ignorar o alarme.
MIGRADAS = ["f_meu_dia", "f_dados_itau", "f_dados_credito_xp",
            "f_dados_credito_nubank", "f_dados_alelia", "f_auto",
            "f_auto_tempo_troca", "f_avaliacao_fisica"]


def main() -> int:
    total = 0
    for nome in MIGRADAS:
        f = MODELO / f"{nome}.tmdl"
        erros = confere(f.stem)
        estado = "ok" if not erros else "; ".join(erros)
        if erros:
            total += 1
        print(f"  {f.stem:<36} {estado}")
    print()
    print("Sintaxe do M consistente em todas."
          if not total else f"{total} tabela(s) com problema.")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
