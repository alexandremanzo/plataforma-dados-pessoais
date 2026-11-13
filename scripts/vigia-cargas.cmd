@echo off
REM =====================================================================
REM manzo-dados ^| Vigia das cargas - roda FORA do Airflow
REM ---------------------------------------------------------------------
REM Chamado pelo Agendador de Tarefas do Windows, uma vez por dia.
REM
REM POR QUE FORA. Com e-mail so de erro, caixa silenciosa quer dizer
REM "esta tudo bem" - mas Airflow parado tambem fica silencioso. A
REM checagem de carga parada mora dentro da propria DAG, entao ela nao
REM roda justamente quando mais precisaria. Este vigia nao depende de
REM Docker nem de Airflow: so do SQL Server e do SMTP.
REM
REM Roda como SYSTEM, sem exigir usuario logado.
REM
REM Para remover:  schtasks /delete /tn "manzo-dados vigia" /f
REM =====================================================================

setlocal

REM O venv do projeto, e nao o python solto do usuario: SYSTEM nao
REM enxerga o site-packages de %APPDATA%, entao o dateutil some e o
REM pandas nem carrega. O venv e autocontido, fica fora do perfil e
REM usa as MESMAS versoes do container.
if "%PY_MANZO%"=="" set PY_MANZO=%~dp0..\.venv\Scripts\python.exe
set PROJ=%~dp0..
set LOG=%PROJ%\logs\vigia.log

echo.>> "%LOG%"
echo ===== %DATE% %TIME% =====>> "%LOG%"

if not exist "%PY_MANZO%" (
    echo ERRO: interpretador nao encontrado em %PY_MANZO%>> "%LOG%"
    echo Defina PY_MANZO ou corrija o caminho neste arquivo.>> "%LOG%"
    exit /b 2
)

"%PY_MANZO%" "%PROJ%\scripts\etl\relatorio_carga.py" --vigia>> "%LOG%" 2>&1
set CODIGO=%ERRORLEVEL%
echo (saida %CODIGO%)>> "%LOG%"
exit /b %CODIGO%
