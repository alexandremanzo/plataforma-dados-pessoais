"""
Conexao centralizada com o SQL Server do projeto.

Nenhum script monta connection string por conta propria: use
get_connection() para pyodbc ou get_engine() para pandas/SQLAlchemy.

As credenciais vem de variaveis de ambiente, lidas tambem de um .env na
raiz do projeto quando ele existe (nunca versionado; ver .env.example).
Sem .env, os valores padrao apontam para o SQL Server da demonstracao
(demo/docker-compose.yml): localhost,14333, banco db-demo, usuario sa.
"""

import os
import urllib.parse
from pathlib import Path

import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine

# --- Localiza a raiz do projeto e carrega o .env, se houver ---------------
# Este arquivo vive em <raiz>/scripts/conf/config_db.py, entao a raiz
# esta dois niveis acima. Variavel ja definida no ambiente (o container
# da demo, por exemplo) tem precedencia sobre o .env.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


# --- Camadas da arquitetura medalhao -------------------------------------
# Nomes dos schemas usados em todo o pipeline. Sempre referencie por estas
# constantes para que um rename futuro seja feito em um lugar so.
BRONZE = "bronze"
SILVER = "silver"
GOLD = "gold"
CAMADAS = (BRONZE, SILVER, GOLD)


# --- Configuracao --------------------------------------------------------
DB_CONFIG = {
    "server": os.getenv("DB_SERVER", "localhost,14333"),
    "database": os.getenv("DB_DATABASE", "db-demo"),
    "driver": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
    "auth": os.getenv("DB_AUTH", "sql").lower(),
    "user": os.getenv("DB_USER", "sa"),
    "password": os.getenv("DB_PASSWORD", "Demo#Paineis2026"),
    "trust_cert": os.getenv("DB_TRUST_CERT", "yes"),
    "timeout": os.getenv("DB_TIMEOUT", "30"),
}

# Caminhos de origem, para os scripts de ingestao nao hardcodarem pastas.
PATH_DADOS_ORIGEM = Path(os.getenv("PATH_DADOS_ORIGEM", ""))
PATH_REPORT = Path(os.getenv("PATH_REPORT", ""))
PATH_PLANILHAS = Path(os.getenv("PATH_PLANILHAS", ""))
# Exames de bioimpedancia (imagem, e nao arquivo tabular).
PATH_EXAMES = Path(os.getenv("PATH_EXAMES", ""))
# Boletos de condominio, em PDF.
PATH_BOLETOS = Path(os.getenv("PATH_BOLETOS", ""))

# Origens que nao sao arquivo. A URL de uma planilha publicada e um
# segredo na pratica (quem a tem le os dados sem login): vive so no .env.
PLANILHA_FAMILIA_URL = os.getenv("PLANILHA_FAMILIA_URL", "")
PLANILHA_DIA_URL = os.getenv("PLANILHA_DIA_URL", "")

# ---------------------------------------------------------------------
# Envio de e-mail (resumo das cargas e alertas). Tudo vazio por padrao:
# sem SMTP configurado, o projeto so nao manda e-mail.
#
# Com verificacao em duas etapas, o Gmail recusa a senha da conta por
# SMTP: e preciso uma senha de aplicativo, que vive apenas no .env.
# ---------------------------------------------------------------------
SMTP = {
    "host": os.getenv("SMTP_HOST", ""),
    "porta": int(os.getenv("SMTP_PORT", "587")),
    "usuario": os.getenv("SMTP_USER", ""),
    # replace e nao so strip: a senha de aplicativo do Google e exibida
    # como "abcd efgh ijkl mnop"; os espacos sao de leitura, nao do segredo.
    "senha": os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip(),
    "de": os.getenv("SMTP_FROM", ""),
    "para": [e.strip() for e in os.getenv("SMTP_PARA", "").split(",") if e.strip()],
}


def _build_conn_str(database: str | None = None) -> str:
    """Monta a connection string ODBC a partir do DB_CONFIG."""
    database = database or DB_CONFIG["database"]

    partes = [
        f"DRIVER={{{DB_CONFIG['driver']}}}",
        f"SERVER={DB_CONFIG['server']}",
        f"DATABASE={database}",
    ]

    if DB_CONFIG["auth"] == "windows":
        partes.append("Trusted_Connection=yes")
    else:
        if not DB_CONFIG["user"] or not DB_CONFIG["password"]:
            raise ValueError("DB_AUTH=sql exige DB_USER e DB_PASSWORD preenchidos.")
        partes.append(f"UID={DB_CONFIG['user']}")
        partes.append(f"PWD={DB_CONFIG['password']}")

    partes.append(f"TrustServerCertificate={DB_CONFIG['trust_cert']}")
    partes.append(f"Connection Timeout={DB_CONFIG['timeout']}")

    return ";".join(partes) + ";"


def get_connection(database: str | None = None) -> pyodbc.Connection:
    """
    Retorna uma conexao pyodbc ativa.

    Levanta a excecao original em caso de falha: engolir o erro e retornar
    None faz o script quebrar mais adiante com uma mensagem sem relacao
    com a causa real.
    """
    return pyodbc.connect(_build_conn_str(database))


def get_engine(database: str | None = None):
    """
    Retorna um engine SQLAlchemy, para uso com pandas (read_sql / to_sql).

    fast_executemany acelera bastante as cargas em lote.
    """
    odbc = urllib.parse.quote_plus(_build_conn_str(database))
    return create_engine(f"mssql+pyodbc:///?odbc_connect={odbc}", fast_executemany=True)


if __name__ == "__main__":
    print(f"Raiz do projeto : {PROJECT_ROOT}")
    print(f"Servidor        : {DB_CONFIG['server']}")
    print(f"Banco           : {DB_CONFIG['database']}")
    print(f"Autenticacao    : {DB_CONFIG['auth']}")
    print()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT @@SERVERNAME, DB_NAME(), SUSER_NAME()")
        servidor, banco, usuario = cursor.fetchone()
        print(f"Conectado em {servidor} / {banco} como {usuario}")

        cursor.execute(
            "SELECT name FROM sys.schemas WHERE name IN (?, ?, ?) ORDER BY name",
            BRONZE, SILVER, GOLD,
        )
        encontrados = [linha[0] for linha in cursor.fetchall()]

    faltando = [c for c in CAMADAS if c not in encontrados]
    print(f"Camadas presentes: {', '.join(encontrados) or 'nenhuma'}")
    if faltando:
        print(f"Camadas faltando : {', '.join(faltando)}")
