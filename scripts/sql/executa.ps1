<#
    manzo-dados | Executor dos scripts SQL

    Roda os arquivos .sql na ordem numerica, sempre com a codepage
    correta.

    POR QUE ESTE SCRIPT EXISTE: o sqlcmd le o arquivo de entrada na
    codepage ANSI do sistema, nao em UTF-8. Chamado direto, ele grava
    "Marco" como "MarÃ§o" e "Nao informado" como "NÃ£o informado" -
    e o estrago so aparece depois, no relatorio. O parametro -f 65001
    resolve, mas e facil esquecer de digitar. Use sempre este script.

    Uso:
        .\executa.ps1                      # roda todos, em ordem
        .\executa.ps1 -Arquivo 04_gold_investimentos.sql
#>

param(
    [string]$Arquivo,
    [string]$Servidor = "localhost",
    [string]$Banco    = "db-manzo"
)

$ErrorActionPreference = "Stop"

# Credenciais vem do .env, nunca do codigo.
$env_path = Join-Path $PSScriptRoot "..\..\.env"
if (-not (Test-Path $env_path)) { throw "Arquivo .env nao encontrado em $env_path" }

$cfg = @{}
Get-Content $env_path -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $cfg[$matches[1]] = $matches[2].Trim() }
}

$sqlcmd = (Get-Command sqlcmd -ErrorAction SilentlyContinue).Source
if (-not $sqlcmd) {
    $sqlcmd = "C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE"
}
if (-not (Test-Path $sqlcmd)) { throw "sqlcmd nao encontrado" }

$arquivos = if ($Arquivo) {
    @(Join-Path $PSScriptRoot $Arquivo)
} else {
    Get-ChildItem $PSScriptRoot -Filter "*.sql" | Sort-Object Name | ForEach-Object { $_.FullName }
}

foreach ($f in $arquivos) {
    Write-Host "`n===== $(Split-Path $f -Leaf) =====" -ForegroundColor Cyan
    # -f 65001 = le o arquivo como UTF-8. Sem isso os acentos quebram.
    & $sqlcmd -S $Servidor -d $Banco -U $cfg['DB_USER'] -P $cfg['DB_PASSWORD'] `
              -i $f -f 65001 -b -W
    if (-not $?) { throw "Falhou em $(Split-Path $f -Leaf)" }
}

Write-Host "`nConcluido." -ForegroundColor Green
