"""
Troca a fonte de cada tabela do relatorio pessoal, no .tmdl.

TROCA SO O PASSO DA FONTE. O M de cada tabela comeca com tres passos -
abrir o arquivo, navegar ate a aba, promover o cabecalho - e segue com
renomeacoes, filtros e colunas condicionais. Substituir apenas os tres
primeiros, MANTENDO O NOME do passo de cabecalho, faz toda a cadeia
seguinte continuar valendo sem uma linha alterada. E o que torna isto
uma troca de origem, e nao uma reescrita.

Grava um .antes-migracao ao lado de cada arquivo tocado.

Uso:
    python aplicar.py            # aplica todas
    python aplicar.py --desfazer # volta tudo pelo backup
"""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
MODELO = Path(os.getenv("PATH_MODELO_PBI", "powerbi/legado"))

TABELAS = ["f_dados_itau", "f_dados_credito_xp", "f_dados_credito_nubank",
           "f_dados_alelia", "f_auto", "f_auto_tempo_troca",
           "f_avaliacao_fisica"]

CABECALHO = ("    // Origem migrada de planilha para o lake (bronze).\n"
             "    // SQL comentado em manzo-dados/powerbi/migracao/{tabela}.sql.\n"
             "    // Os passos seguintes do M seguem intactos: o nome do passo de\n"
             "    // cabecalho foi preservado de proposito.")


def compacta(tabela: str) -> str:
    sql = (BASE / f"{tabela}.sql").read_text(encoding="utf-8")
    sql = " ".join(re.sub(r"/\*.*?\*/", " ", sql, flags=re.S).split())
    if '"' in sql:
        raise ValueError(f"{tabela}.sql tem aspas duplas; o M exige dobra-las")
    return sql


def aplica(tabela: str) -> str:
    alvo = MODELO / f"{tabela}.tmdl"
    linhas = alvo.read_text(encoding="utf-8").split("\n")

    i_fonte = next(i for i, l in enumerate(linhas) if re.match(r"\s*Fonte\s*=", l))
    i_prom = next(i for i, l in enumerate(linhas[i_fonte:], i_fonte)
                  if "Table.PromoteHeaders" in l)

    # O nome do passo e o virgula final sao preservados: e deles que os
    # passos seguintes dependem.
    m = re.match(r"(\s*)(#\"[^\"]+\"|\S+)\s*=", linhas[i_prom])
    recuo, passo = m.group(1), m.group(2)
    virgula = "," if linhas[i_prom].rstrip().endswith(",") else ""

    novo = [
        *[recuo + l.strip() for l in
          CABECALHO.format(tabela=tabela).split("\n")],
        recuo + 'Fonte = Sql.Databases("localhost"),',
        recuo + '#"db-manzo" = Fonte{[Name="db-manzo"]}[Data],',
        recuo + f'{passo} = Value.NativeQuery(#"db-manzo", '
                f'"{compacta(tabela)}"){virgula}',
    ]

    # Nunca sobrescreve backup existente: aplicar duas vezes guardaria a
    # versao ja migrada por cima da original, e a original e a unica volta.
    bkp = MODELO / f"{tabela}.tmdl.antes-migracao"
    if not bkp.exists():
        bkp.write_text("\n".join(linhas), encoding="utf-8", newline="")
    alvo.write_text("\n".join(linhas[:i_fonte] + novo + linhas[i_prom + 1:]),
                    encoding="utf-8", newline="")
    return f"passos {i_fonte + 1}-{i_prom + 1} trocados, passo '{passo}' preservado"


def desfaz(tabela: str) -> str:
    bkp = MODELO / f"{tabela}.tmdl.antes-migracao"
    if not bkp.exists():
        return "sem backup"
    (MODELO / f"{tabela}.tmdl").write_text(bkp.read_text(encoding="utf-8"),
                                           encoding="utf-8", newline="")
    return "restaurado"


def main() -> int:
    voltar = "--desfazer" in sys.argv
    for t in TABELAS:
        try:
            print(f"  {t:<24} {desfaz(t) if voltar else aplica(t)}")
        except Exception as e:                              # noqa: BLE001
            print(f"  {t:<24} ERRO {type(e).__name__}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
