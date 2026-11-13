# Dar uma chave própria às bases de cadastro manual

Duas bases são digitadas à mão — **conta Itaú** e **cartão XP** — e nelas
é normal lançar na pressa e completar depois: a descrição fica em
branco, o valor sai errado, ou a fatura é registrada no mês X quando na
conferência se descobre que era o mês Y.

O problema é que data, descrição e valor **compunham a chave de
negócio**. Corrigir qualquer um deles mudava a identidade do registro: a
carga inseria um novo e deixava o antigo órfão, inflando os totais em
silêncio. Justamente os campos que mais precisam de correção eram os que
não podiam ser corrigidos.

A solução é uma coluna `ID` na planilha — um número próprio, sem
significado, que nunca muda. É o mesmo desenho do diário *meu dia*, onde
a chave é o carimbo que o Google atribui, e é por isso que lá até a data
é corrigível.

**Depois disso, tudo o mais passa a ser atualizável até a gold.**

---

## A ordem importa

Três passos, nesta sequência. Fora de ordem, a migração não consegue
casar as linhas do banco com as da planilha.

### 1. Acrescentar a coluna `ID`

Em cada uma das duas planilhas:

| Planilha | Aba | Onde |
|---|---|---|
| `dados-itau.xlsx` | `cad-conta` | coluna **U**, depois de `Tag` |
| `dados-xp-credito.xlsx` | `MOVTO` | coluna **U**, depois de `Descrição Status Pgto` |

Escreva `ID` no cabeçalho (linha 1), exatamente assim, em maiúsculas.

> **No fim, nunca no meio.** Inserir uma coluna no começo desloca todas
> as outras e pode quebrar as consultas do Power BI.

### 2. Numerar as linhas existentes

Digite `1` na primeira linha de dados, `2` na segunda, selecione as
duas células e arraste até a última linha com conteúdo.

- Itaú: até a linha **5.008** (são 5.007 lançamentos)
- Cartão XP: até a linha **4.179** (são 4.178 lançamentos)

Não precisa numerar a cauda de linhas vazias — a carga as descarta.

> **Não ordene nem reorganize a planilha antes disso.** A migração
> reproduz a chave antiga para casar cada linha com a do banco, e a
> ordem atual faz parte dela em lançamentos repetidos.

> **Não corrija nada ainda.** Alterar um valor antes da migração muda a
> chave antiga daquela linha e ela deixa de casar. Primeiro os IDs,
> depois a migração, e só então as correções — que a partir dali
> propagam sozinhas.

### 3. Rodar a migração

```powershell
cd "C:\caminho\plataforma-dados-pessoais"
$py = ".venv\Scripts\python.exe"

& $py scripts\etl\migra_chave_id.py             # simula, não altera nada
& $py scripts\etl\migra_chave_id.py --aplicar   # executa
```

**Rode a simulação primeiro e leia o relatório.** Ele mostra, por base:

- quantas linhas casam com o banco — deve ser o total da planilha
- quantas estão na planilha e não no banco — entram como novas
- quantas estão no banco e não na planilha — **serão removidas**

Se "casam com o banco" vier muito abaixo do total, alguma coisa foi
reordenada ou corrigida antes da hora. Não use `--aplicar`; me chame.

Depois:

```powershell
& $py scripts\etl\carga_bronze_itau.py       # deve dar +0 novos, 0 atualizados
& $py scripts\etl\carga_silver_itau.py
& $py scripts\etl\carga_bronze_cartao_xp.py
& $py scripts\etl\carga_silver_cartao.py
& $py scripts\etl\carga_gold_movimentacao.py
```

---

## O que a migração encontrou, na prática

Executada em 17/08/2026. As duas planilhas casaram 100% — 5.007 e 4.178
linhas — e a limpeza removeu **19 registros órfãos**:

| Camada | Removidos | O que eram |
|---|---|---|
| `silver.itau_movimentacao` | 9 | linhas que já não existiam na bronze |
| `bronze.cartao_xp` + `silver.cartao_movimentacao` | 10 | o *antes* de correções já feitas |
| `gold.fato_movto_financ` | 19 | as duas coisas acima |

Os 10 do cartão eram exatamente o problema que motivou tudo: nove
correções de data de fatura (lançadas como 15/08, corrigidas para
15/09) e uma de valor, **somando R$ 637,29 duplicados na gold**.

O fato foi de 11.408 para **11.389** linhas.

### Duas armadilhas que apareceram na execução

**O tipo do ID muda conforme a planilha.** A coluna do Itaú tem 280
linhas de cauda vazias, e isso faz o pandas ler a coluna inteira como
`float`: o ID `1` chega como `1.0`. No cartão XP, sem cauda, chega como
`int`. Como o hash é feito sobre o texto, `"1.0"` e `"1"` dariam hashes
diferentes para o mesmo lançamento — e bastaria você apagar as linhas em
branco do Itaú para os 5.007 hashes mudarem de uma vez.

`normaliza_id()` em `scripts/etl/util_dados.py` resolve: `1`, `1.0`,
`"1"` e `"1.0"` produzem sempre `"1"`. É usada nos **três** lugares que
precisam concordar — as duas cargas e a migração.

**A gold precisava entrar na migração.** `gold.fato_movto_financ` tem
11 mil linhas chaveadas pelo mesmo hash. Reescrever só bronze e silver
teria deixado a gold com o hash velho, e a carga seguinte inseriria tudo
de novo sem remover o antigo — o fato dobraria para ~20.500.

A limpeza da gold usa a regra geral *"linha sem par em nenhuma silver"*,
que não precisa saber de qual origem a linha veio e por isso não tem
como atingir o Nubank, que divide a mesma tabela silver.

---

## No dia a dia, depois disso

**Ao incluir um lançamento**, escreva o próximo número no `ID`. Se
preferir automático, use uma fórmula na coluna:

```
=SE(A2="";"";MÁXIMO($U$1:U1)+1)
```

trocando `A2` por qualquer coluna sempre preenchida. Ela dá o maior ID
já usado mais um, o que evita repetição mesmo se você inserir linhas no
meio.

**Nunca reaproveite o ID de uma linha excluída.** O lançamento novo
herdaria os dados do antigo no banco, silenciosamente.

**Nunca renumere.** Os IDs não precisam ser contínuos nem estar em
ordem; precisam apenas ser únicos e permanentes.

---

## O que a carga recusa

Ela para com erro em vez de carregar errado, porque num cadastro manual
um lançamento perdido só apareceria meses depois, numa conferência que
não fecha:

| Situação | Mensagem |
|---|---|
| Coluna `ID` ausente ou vazia | *não tem a coluna 'ID' preenchida* |
| Linha com dados mas sem `ID` | *N linhas têm dados mas estão sem ID*, com os números das linhas |
| `ID` repetido | *N linhas têm ID REPETIDO*, com exemplos |

Enquanto a coluna não existir, as tarefas `bronze_itau` e
`bronze_cartao_xp` falham no Airflow — de propósito. Nada é corrompido:
as demais origens seguem carregando normalmente.

---

## O que isto liberou

Passam a ser corrigíveis, com a correção chegando até a gold:

- **descrição** deixada em branco na pressa
- **valor** digitado errado
- **data da fatura** — o caso que motivou a mudança, e que agora permite
  bater o valor pago no cartão contra a soma dos itens do mês
- data do lançamento, categoria, área, grupo, pessoa, cidade, observação

Continua **não** propagando: apagar uma linha da planilha não a remove
do banco. Para isso existe a remoção de órfãos da própria migração, que
pode ser rodada de novo quando necessário.
