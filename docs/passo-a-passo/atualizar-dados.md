# Atualizar os dados na hora

Você baixou um arquivo novo e quer ver no Power BI agora, sem esperar
as 8h, 12h ou 20h.

**Tempo:** cerca de 2 minutos.

---

## 1. Colocar o arquivo no lugar

Cada origem tem seu destino. O nome do arquivo importa — a carga
procura por ele.

| Origem | O que fazer | Caminho |
|---|---|---|
| **Investimentos XP** | Baixar o extrato no app e renomear para `extrato-xp.xlsx` | `Financeiro\Dados\xp\` |
| **Conta Itaú** | Colar o extrato baixado numa aba nova do arquivo | `Financeiro\Dados\dados-itau.xlsx` |
| **Cartão XP** | Lançar a fatura na aba `MOVTO` | `Financeiro\Dados\dados-xp-credito.xlsx` |
| **Avaliação física** | Lançar o laudo na aba `Avaliações`, uma linha por medida | `Documentos\Planilhas\pla-avaliacao-fisica.xls` |
| **Manutenção do carro** | Lançar a nota da oficina na aba `Avaliações`, uma linha por item — **com o KM** | `Documentos\Planilhas\pla-revisao-auto.xls` |

Duas origens **não têm passo 1**: a conta família e o diário *meu dia*
vivem no Google e o pipeline as lê direto. Basta editar a planilha (ou
responder o formulário) e ir para o passo 2.

Três coisas que **não** são necessárias:

- **Não** apague o extrato anterior. Se quiser guardar, mova para
  `xp\bkp\` — a carga lê os backups também e ignora o que já entrou.
- **Não** escolha o que é novo. A deduplicação é automática, mesmo com
  janelas sobrepostas.
- **Não** se preocupe com a aba do Itaú ter a data no nome. A carga a
  localiza por padrão, não por nome fixo.

---

## 2. Rodar

Abra o PowerShell e cole:

```powershell
cd "C:\caminho\plataforma-dados-pessoais\airflow"
docker compose exec airflow-scheduler airflow dags trigger pipeline_manzo -r manual-$(Get-Date -Format 'MMdd-HHmm')
```

Isso dispara o pipeline completo. As origens sem novidade terminam em
segundos reportando `+0` — não custa nada rodar tudo.

> Se o comando `docker` não for reconhecido, o terminal foi aberto
> antes de alguma instalação. Recarregue o PATH:
> `$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine")`

Espere cerca de 1 minuto.

---

## 3. Conferir se deu certo

```powershell
docker compose exec airflow-scheduler airflow dags list-runs -d pipeline_manzo
```

A primeira linha é a execução mais recente. Procure **`success`**.

Se aparecer `running`, ainda está rodando — espere e rode de novo. Se
aparecer `failed`, vá para o passo 5.

---

## 4. Conferir se os dados entraram

```powershell
cd "C:\caminho\plataforma-dados-pessoais"
..\..\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'scripts/conf'); from config_db import get_engine; import pandas as pd; print(pd.read_sql('SELECT MAX(dt_movimentacao) AS ultimo_investimento FROM silver.xp_movimentacao', get_engine()).to_string(index=False))"
```

A data deve bater com o último lançamento do seu extrato.

**Sinais de que está tudo certo:**

- A data mais recente na base é a do arquivo que você acabou de colocar
- Nenhuma categoria `Outros` apareceu nos lançamentos novos
- O saldo do último lançamento bate com o saldo do cabeçalho do extrato

---

## 5. Atualizar o Power BI

O relatório lê `dados-xp-consolidado.xlsx`, que o pipeline acabou de
regerar. Basta abrir o Power BI e clicar em **Atualizar**.

> Enquanto o Power BI ler esse arquivo, o passo 5 é manual. Quando ele
> passar a ler o SQL direto, some.

---

## 6. Se der errado

### A execução falhou

Veja qual tarefa quebrou:

```powershell
docker compose exec airflow-scheduler airflow tasks states-for-dag-run pipeline_manzo NOME-DA-EXECUCAO
```

E leia o log dela — troque `bronze_xp` pelo nome da tarefa:

```powershell
docker compose exec airflow-scheduler bash -c "find /opt/airflow/logs -path '*bronze_xp*' -name '*.log' | sort | tail -1 | xargs tail -40"
```

Depois de corrigir a causa, limpe o estado da tarefa — ela e as
seguintes reexecutam sozinhas:

```powershell
docker compose exec airflow-scheduler airflow tasks clear pipeline_manzo --yes --task-regex bronze_xp
```

### O Airflow não responde

```powershell
docker compose ps          # os três serviços devem estar Up
docker compose up -d       # sobe o que estiver parado
```

### Erro de conexão com o banco

O SQL Server precisa estar rodando **e** com TCP/IP habilitado:

```powershell
Get-Service MSSQLSERVER
Get-NetTCPConnection -State Listen -LocalPort 1433
```

Se a porta 1433 não aparecer, o protocolo TCP foi desabilitado — sem
ele o container não conecta.

### Os dados não apareceram, mas nada falhou

Provavelmente o arquivo não estava onde a carga procura, ou o nome está
diferente. Confira o passo 1. A carga não reclama de arquivo ausente:
ela avisa e segue.

---

## Rodar só uma origem

Se você só mexeu nos investimentos e quer evitar o resto:

```powershell
cd "C:\caminho\plataforma-dados-pessoais\airflow"
foreach ($t in @("bronze_xp","silver_xp","gold_investimento","exporta_consolidado")) {
  docker compose exec airflow-scheduler airflow tasks test pipeline_manzo $t 2026-08-15
}
```

`tasks test` executa de verdade, mas não grava estado no Airflow — não
conta como execução nem aparece no histórico.

Tarefas por origem:

| Origem | Tarefas, em ordem |
|---|---|
| Investimentos | `bronze_xp` → `silver_xp` → `gold_investimento` → `exporta_consolidado` |
| Conta Itaú | `bronze_itau` → `silver_itau` → `gold_movimentacao` |
| Cartões | `bronze_cartao_xp`, `bronze_cartao_nubank` → `silver_cartao` → `gold_movimentacao` |
| Conta família | `bronze_familia` → `silver_familia` → `gold_familia` |
| Meu dia | `bronze_dia` → `silver_dia` → `gold_dia` |
| Avaliação física | `bronze_avaliacao` → `silver_avaliacao` → `gold_avaliacao` |
| Manutenção do carro | `bronze_auto` → `silver_auto` → `gold_auto` |

---

## Por que rodar de novo é seguro

Todas as cargas são **idempotentes**: cada lançamento tem uma
identidade calculada a partir do próprio conteúdo, e o banco recusa
duplicata por constraint.

Na prática, isso significa que você pode:

- Rodar quantas vezes quiser sem duplicar nada
- Deixar o mesmo extrato na pasta por meses
- Colocar arquivos com períodos sobrepostos
- Reexecutar uma tarefa que falhou no meio

A segunda execução sempre reporta `+0 novos, 0 atualizados`. **Se
reportar outra coisa sem você ter mexido em arquivo nenhum, é sinal de
problema** — vale investigar.
