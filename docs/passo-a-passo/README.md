# Passo a passo

Roteiros práticos, escritos para serem seguidos e não lidos. Cada um
resolve uma tarefa do começo ao fim, incluindo o que fazer quando dá
errado.

## Disponíveis

- **[Atualizar os dados na hora](atualizar-dados.md)** — baixou um
  arquivo novo e quer ver no Power BI agora, sem esperar o horário
  agendado.
- **[Ler uma planilha do Google](origem-google-sheets.md)** — publicar
  uma aba como CSV e ligá-la ao pipeline, com as armadilhas de
  encoding e formato que já custaram tempo.
- **[Dar uma chave própria às bases de cadastro manual](chave-id-cadastro-manual.md)**
  — acrescentar a coluna `ID` ao Itaú e ao cartão XP para que
  descrição, valor e data da fatura possam ser corrigidos depois.

## Planejados

- Classificar lançamentos pendentes — resolver o que está como
  *A classificar* usando a planilha de revisão
- Acrescentar uma origem nova de arquivo ao pipeline
- Migrar o Power BI para ler o SQL direto
- Restaurar o ambiente numa máquina nova

---

## Convenção

Os roteiros assumem que você está no PowerShell e que o projeto está em
`C:\caminho\plataforma-dados-pessoais`. Comandos que dependem do
Docker rodam a partir da pasta `airflow`.

Se um comando não for reconhecido (`git`, `docker`), o terminal foi
aberto antes de alguma instalação. Recarregue o PATH:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine")
```
