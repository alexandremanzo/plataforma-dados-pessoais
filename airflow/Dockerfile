# =============================================================
# manzo-dados | Imagem do Airflow com acesso ao SQL Server
# -------------------------------------------------------------
# A imagem oficial do Airflow nao fala com SQL Server: nao tem o
# driver ODBC da Microsoft nem o pyodbc. Sem isso, qualquer DAG que
# tente carregar dados falha com "Data source name not found".
#
# O driver instalado aqui e o 18, e nao o 17 usado no host Windows.
# Isso muda a string de conexao: o 18 exige criptografia por padrao,
# entao TrustServerCertificate=yes deixa de ser opcional numa
# instancia local sem certificado. O .env do container ja aponta para
# o driver correto.
# =============================================================

FROM apache/airflow:2.10.5

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl gnupg apt-transport-https ca-certificates \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 unixodbc-dev tesseract-ocr \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------
# Interpretador separado para o ETL
# -------------------------------------------------------------
# O ETL NAO roda no Python do Airflow, e o motivo e um conflito real
# de dependencia: o pandas 2.1 em diante exige SQLAlchemy 2.0, e o
# Airflow 2.10 fixa SQLAlchemy abaixo de 2.0. Instalados juntos, o
# pandas nao reconhece a conexao do SQLAlchemy, trata como DBAPI e
# quebra com "'Connection' object has no attribute 'cursor'".
#
# Com um venv proprio, o ETL usa exatamente as mesmas versoes do host
# e o mesmo codigo roda nos dois lugares sem adaptacao. O Airflow
# apenas invoca /opt/etl-venv/bin/python.

# tesseract-ocr le os exames de bioimpedancia, que chegam como imagem.
# So o motor entra: o idioma nao, porque os campos lidos sao numeros e
# o modelo em ingles ja os reconhece - os rotulos vem do recorte, nao
# do OCR.
#
# openpyxl le .xlsx; xlrd le .xls antigo (Excel 97-2003, formato OLE2).
# Sao bibliotecas distintas e nenhuma cobre os dois: a planilha de
# avaliacao fisica e .xls de verdade, e sem xlrd a carga nao abre.

# --timeout e --retries porque esta camada baixa wheels grandes - pandas,
# pymupdf - e o padrao do pip (15 s por leitura, 5 tentativas) ja
# derrubou um build com "Read timed out" num dia de rede lenta. Falhar
# aqui custa os minutos inteiros da camada; esperar mais custa nada.
RUN python -m venv /opt/etl-venv \
 && /opt/etl-venv/bin/pip install --no-cache-dir --timeout 120 --retries 10 --upgrade pip \
 && /opt/etl-venv/bin/pip install --no-cache-dir --timeout 120 --retries 10 \
        pyodbc==5.3.0 \
        pandas==3.0.2 \
        "sqlalchemy==2.0.49" \
        openpyxl==3.1.5 \
        xlrd==2.0.2 \
        python-dotenv==1.0.1 \
        requests==2.32.3 \
        pytesseract==0.3.13 \
        pymupdf==1.24.14 \
 && chown -R airflow:0 /opt/etl-venv

USER airflow
