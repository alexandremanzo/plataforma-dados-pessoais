# Imagem que prepara o banco da demonstracao, gera os dados ficticios e
# monta o site estatico (site/) com o hub e os paineis.
FROM python:3.13-slim

# Driver ODBC 18 da Microsoft, o mesmo que o projeto usa para falar com o SQL Server
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates unixodbc \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY demo/requirements.txt demo/requirements.txt
RUN pip install --no-cache-dir -r demo/requirements.txt

COPY scripts/conf scripts/conf
COPY scripts/paineis scripts/paineis
COPY demo demo

CMD ["python", "demo/build_site.py"]
