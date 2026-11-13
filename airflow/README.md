# Airflow — orquestração do pipeline

Sobe um Airflow local em Docker que executa as cargas do projeto na
ordem de dependência entre as camadas.

```powershell
cd airflow
copy .env.example .env      # preencha as credenciais
docker compose up -d
```

Interface em <http://localhost:8080>.

## O que a DAG faz

```
bronze_xp ──> silver_xp ──> gold_investimento ──> exporta_consolidado

bronze_itau ──> silver_itau ──┐
                              ├──> gold_movimentacao
bronze_cartao_xp ─────┐       │
                      ├──> silver_cartao
bronze_cartao_nubank ─┘
```

Roda três vezes ao dia — **8h, 12h e 20h de Brasília**. O dado não
chega todo dia (o extrato da XP e a fatura do cartão são baixados à mão
algumas vezes por mês), mas rodar várias vezes significa que um arquivo
colocado na pasta pela manhã entra ainda no mesmo dia.

> O horário é declarado em `America/Sao_Paulo`, não em UTC. O Airflow
> interpreta o cron no fuso da `start_date`, e o padrão dele é UTC —
> uma `start_date` sem fuso faria `0 8 * * *` rodar às 5h da manhã aqui.

Todas as cargas são idempotentes: reexecutar não duplica nada e
converge em zero inserções. É o que torna o *retry* seguro e permite
`catchup=False` sem perder dado.

## Quatro decisões que fazem isso funcionar

**O ETL roda num interpretador separado.** O pandas exige SQLAlchemy
2.0 e o Airflow 2.10 fixa uma versão anterior; instalados juntos, o
pandas deixa de reconhecer a conexão e falha com
`'Connection' object has no attribute 'cursor'`. O venv em
`/opt/etl-venv` tem exatamente as versões do host, então o mesmo
script roda idêntico nos dois lugares.

**O SQL Server é alcançado por `host.docker.internal`.** Dentro do
container, `localhost` é o próprio container. E `Trusted_Connection`
não existe em Linux: a autenticação tem que ser por usuário e senha.

**As variáveis do compose vencem o `.env` do projeto.** `load_dotenv`
não sobrescreve o ambiente, então o container usa seus próprios
caminhos e servidor sem que nenhum script precise saber onde está
rodando.

**O projeto é montado, não copiado.** Editar um script no host reflete
na próxima execução, sem rebuild.

## Pré-requisito no SQL Server

O protocolo **TCP/IP precisa estar habilitado** na instância. Por
padrão o SQL Server aceita apenas memória compartilhada e named pipes,
que funcionam para tudo que roda no Windows mas não para um container
Linux. Sem isso a conexão falha com *Login timeout expired*.

Conferir com:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 1433
```

## Comandos úteis

```powershell
docker compose ps                        # estado dos serviços
docker compose logs airflow-scheduler -f # acompanhar o scheduler
docker compose down                      # parar (preserva o histórico)
docker compose down -v                   # parar e apagar os metadados
```

Rodar uma carga isolada, sem passar pelo Airflow:

```powershell
docker compose exec airflow-scheduler /opt/etl-venv/bin/python /opt/projeto/scripts/etl/carga_bronze_itau.py
```

## Nota

Este setup substitui uma instalação anterior do Airflow, que ficava
fora do repositório e cujo DAG nunca chegou a funcionar — o
`CREATE TABLE` tinha 20 colunas sem nome nem tipo. Aquela pasta pode
ser removida.
