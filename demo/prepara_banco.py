"""
Cria o banco da demonstracao e aplica a estrutura de demo/schema.

Espera o SQL Server aceitar conexao (o container leva alguns segundos
para subir), cria o banco se ele nao existir e roda os scripts .sql em
ordem, separando os lotes pelo GO como o sqlcmd faria. Rodar de novo
recria as tabelas do zero.

Uso:
    python demo/prepara_banco.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pyodbc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
from config_db import DB_CONFIG, get_connection  # noqa: E402

SCHEMA = Path(__file__).with_name("schema")


def espera_servidor(tentativas: int = 60) -> None:
    for i in range(tentativas):
        try:
            get_connection("master").close()
            return
        except pyodbc.Error as erro:
            if i == tentativas - 1:
                raise
            print(f"  aguardando o SQL Server ({erro.args[0]})...")
            time.sleep(3)


def main() -> int:
    banco = DB_CONFIG["database"]
    print(f"SQL Server em {DB_CONFIG['server']}, banco {banco}")
    espera_servidor()
    with get_connection("master") as c:
        c.autocommit = True
        c.execute(f"IF DB_ID('{banco}') IS NOT NULL BEGIN ALTER DATABASE [{banco}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
                  f"DROP DATABASE [{banco}]; END")
        c.execute(f"CREATE DATABASE [{banco}]")
    with get_connection() as c:
        c.autocommit = True
        for arq in sorted(SCHEMA.glob("*.sql")):
            lotes = [b for b in re.split(r"^\s*GO\s*$", arq.read_text(encoding="utf-8"), flags=re.M | re.I) if b.strip()]
            for lote in lotes:
                c.execute(lote)
            print(f"  {arq.name}: {len(lotes)} lotes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
