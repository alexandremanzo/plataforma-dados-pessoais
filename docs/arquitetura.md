# Arquitetura

## Por que três camadas

O padrão medalhão existe para separar três responsabilidades que, numa
planilha, ficam misturadas: **guardar o que veio**, **decidir o que
significa** e **apresentar para consumo**.

Na prática, a separação se paga quando uma regra muda. Corrigir a
classificação de um lançamento não exige voltar ao arquivo original —
basta reprocessar a silver a partir da bronze, que nunca foi alterada.

```
arquivos ──> bronze ──> silver ──> gold ──> Power BI
             cópia      sentido    consumo
```

### bronze — cópia fiel

Guarda o dado como veio, sem conversão de tipo. Colunas em `varchar`
inclusive para datas e valores, porque um valor inválido não deve
derrubar a carga: ele entra como texto e a silver decide o que fazer.

Cada linha carrega **linhagem**: de qual arquivo veio, de qual aba, e
em que posição. Isso permite auditar qualquer número até a origem.

A bronze guarda **cada evento uma vez**, e não uma cópia de cada
arquivo. A decisão vem do processo real: os extratos são baixados
várias vezes por mês sempre cobrindo o período anterior, então
sobrepõem-se quase totalmente. Persistir tudo seria guardar oito cópias
do mesmo dado. A fidelidade ao bruto não se perde: os arquivos
continuam no disco e a carga é reexecutável a partir deles.

### silver — sentido

Aqui o dado ganha tipo, classificação e vocabulário padronizado. Uma
tabela por entidade de negócio, já unificando origens quando elas têm a
mesma natureza — os dois cartões de crédito, por exemplo, moram na
mesma tabela com uma coluna identificando qual.

É também onde as inconsistências entre origens são resolvidas: sinal do
valor, grafia dos rótulos, e a marcação de linhas que não são
transação.

### gold — consumo

Modelo dimensional em star schema, otimizado para leitura. Fatos
deliberadamente separados:

| Fato | Assunto |
|---|---|
| `fato_investimento` | Movimentações da conta de investimento |
| `fato_movto_financ` | Fluxo de caixa e gastos pessoais — conta corrente e cartões |
| `fato_familia` | Gastos em comum do casal, com quem pagou cada um |
| `fato_dia` | Diário de hábitos — um retrato por dia |
| `fato_dia_habito` | O mesmo diário no formato longo, um dia por hábito |
| `fato_avaliacao_fisica` | Bioimpedância e medidas corporais, 2008 a 2026 |
| `fato_manutencao_auto` | Revisões e consertos do carro, com quilometragem |

Não se misturam porque respondem perguntas diferentes sobre dinheiros
diferentes. Um dividendo e um almoço não pertencem à mesma análise; e o
gasto da família sai de um fundo para o qual duas pessoas aportam —
somá-lo ao pessoal contaria gasto de dois como se fosse de um.

**Mas compartilham dimensões.** `fato_movto_financ` e `fato_familia`
usam as mesmas `dim_area_financ`, `dim_categoria_financ` e
`dim_grupo_financ`, porque o vocabulário de área,
categoria e grupo é o mesmo em boa parte. Isso permite comparar
"quanto gastei de alimentação sozinho" com "quanto a família gastou de
alimentação" pelo mesmo eixo, sem duplicar a dimensão. As categorias
exclusivas de cada lado — `MORADIA` e `DIARISTA` só existem na família —
convivem sem conflito.

O diário de hábitos não tem nada em comum com os fatos financeiros
além do calendário — e é justamente isso que basta: `dim_calendario` é
a mesma tabela, então cruzar gasto e hábito na mesma data não exige
nenhuma ponte adicional.

### Por que o diário tem dois fatos

É a única origem modelada duas vezes, porque as duas perguntas que se
faz a ela têm formatos incompatíveis:

- *"quanta água bebi por mês"*, *"treinei mais nos dias de trabalho?"*
  — precisam de **uma linha por dia**, com tudo lado a lado. É
  `fato_dia`.
- *"como está a aderência de cada hábito ao longo do tempo?"* — precisa
  de **uma linha por dia por hábito**. Sem isso, cada pergunta do
  formulário vira uma medida DAX própria e acrescentar uma pergunta
  nova obriga a refazer o relatório. É `fato_dia_habito`.

Só o formato largo tornaria o painel de hábitos inviável; só o longo
tornaria impossível somar litros de água sem misturar unidades. São 888
e 10.656 linhas — manter os dois não custa nada, e a nota do dia é
calculada uma vez só, na carga, a partir da mesma regra.

**A regra de aderência é dado, não código.** O que conta como meta
cumprida vive em `dim_habito`, nas colunas `DS_RESPOSTA_DESEJADA`,
`VL_META_MINIMA` e `FL_APURA_ADERENCIA`. A carga apenas aplica. Decidir
que a ceia é opcional, ou mudar a meta de água, é um `UPDATE` seguido
de nova carga — e rodar o script SQL de novo não desfaz o ajuste,
porque a semeadura só insere o que falta.

Há **duas formas de aderir**, e a dimensão diz qual vale para cada
hábito: alcançar um limiar numérico (`VL_META_MINIMA`, hoje só a água,
em litros por dia) ou dar a resposta esperada (`DS_RESPOSTA_DESEJADA`,
todo o resto). A água é o único hábito medido em número, então carrega
o valor em `VL_MEDIDA` no fato longo — mas quem for somar litros deve
usar `fato_dia.VL_AGUA_LITROS`, porque `VL_MEDIDA` passaria a misturar
unidades se um segundo hábito numérico aparecesse.

`FL_META_AGUA`, no fato largo, é copiado do fato longo em vez de
recalculado: a meta é aplicada uma vez só, e as duas tabelas não podem
divergir se o limiar mudar.

A dimensão também separa **meta** de **contexto**: treinar é um
objetivo, ter alguém da família em casa é uma circunstância. Contexto não entra
na nota do dia, mas continua servindo de filtro — e é por ele que se
descobre, por exemplo, que o treino acontece em 66% dos dias de
trabalho contra 16% nas folgas.

### A avaliação física e o problema da série longa

É a série mais longa do projeto — 31 avaliações entre 2008 e 2026 — e a
única cuja **definição mudou no meio do caminho**. Até 2013 o laudo
trazia circunferências, pressão arterial e frequência cardíaca; de 2018
em diante é bioimpedância. Apenas cinco métricas existem nas duas eras:
peso, IMC, % de gordura, massa de gordura e estatura.

Isso não é um defeito a corrigir, é um fato a declarar.
`FL_SERIE_CONTINUA` marca as cinco, e o painel de longo prazo filtra
por ela. Sem isso, o gráfico de 18 anos exibe linhas que começam ou
terminam no meio, e o leitor conclui que algo aconteceu quando o que
mudou foi só o aparelho.

O caso mais perigoso é `Massa Muscular` × `Massa Muscular/Ossea`. Nunca
coexistem: a primeira aparece a partir de 2018 na faixa de 34–37 kg, a
segunda até 2013 na faixa de 58–63 kg, porque inclui massa óssea. São
métricas **distintas** na dimensão, de propósito. Unificá-las pelo nome
parecido produziria uma queda de 25 kg que nunca existiu.

**A variação mora no fato.** As avaliações são irregulares — de 21 dias
a quase cinco anos entre elas — então "avaliação anterior" não coincide
com nenhum período do calendário. `VL_MEDIDA_ANTERIOR` e `VL_VARIACAO`
são calculadas na carga, contra a última vez em que aquela métrica foi
*medida*, e não contra a avaliação anterior: pular uma medida não deve
abrir buraco na comparação.

`DS_SENTIDO_MELHOR` diz para que lado cada métrica melhora, e fica
**nulo** onde não há resposta universal — peso, IMC e estatura dependem
do objetivo do momento; pressão arterial é melhor dentro de uma faixa,
não num extremo. Marcar direção ali seria fingir certeza.

### A manutenção do carro e a única view do modelo

O histórico da oficina sozinho responde *"quanto já gastei"*. A mesma
planilha traz uma segunda aba — `Tempo Troca` — dizendo de quantos em
quantos quilômetros cada categoria deve ser trocada. Cruzadas, as duas
respondem *"o que está vencendo"*, e é aí que a base deixa de ser
arquivo. Daí `gold.vw_manutencao_prevista`.

É view e não tabela porque o resultado depende da quilometragem atual,
que muda a cada carga: materializar convidaria a ler um número velho.

**Dois veículos com hodômetros independentes.** Sedan até novembro de
2025, SUV desde então. `dim_veiculo` existe por causa disso — sem
separar, os 100 mil km do SUV pareceriam um retrocesso diante dos 158
mil do Sedan, e a previsão sairia errada em todas as linhas. A view
considera só o veículo ativo, pelo mesmo motivo: o hodômetro do carro
antigo é maior, então tudo apareceria como vencido.

**O limite honesto da previsão.** `NR_KM_ATUAL` vem da maior
quilometragem já registrada, e só se registra ao ir à oficina. Logo
depois de uma visita, portanto, tudo aparece como *Em dia* por
construção, e a previsão só ganha sentido conforme o carro roda sem ser
levado. Um alerta de verdade exigiria anotar o hodômetro periodicamente,
com data e veículo — a aba `Quilometragem` da planilha tentava isso,
mas guarda um número solto sem identificar o carro, e por isso não é
usada.

**Não se liga ao fato financeiro**, embora parte destes gastos apareça
na fatura do cartão. Aqui o assunto é o veículo — o que foi trocado, com
que quilometragem — e não o dinheiro; somar os dois contaria a mesma
despesa duas vezes.

---

## Decisões de modelagem

### A hierarquia de categoria não é hierarquia

Os gastos têm três níveis de classificação — área, categoria e grupo —
mas os dados mostraram que **eles não formam uma árvore**: o mesmo
grupo aparece sob categorias diferentes ao longo do tempo, e a mesma
categoria sob áreas diferentes.

Modelar como hierarquia navegável produziria totais ambíguos. A
dimensão tem uma linha por **combinação distinta** dos três, que é o
que os dados de fato são.

### O nível analítico e sintético

Um gasto no cartão existe em dois planos:

```
conta corrente:  pagamento da fatura        <- sintético (o pai)
                 │
cartão:          ├── compra no mercado      <- analítico (os filhos)
                 ├── compra no posto
                 └── compra na farmácia
```

Somar os dois planos conta a mesma despesa duas vezes. O atributo
`DS_NIVEL` os separa, e **a medida de despesa deve filtrar
`ANALITICO`**. O nível sintético serve para conciliar com o extrato
bancário e para ver o desembolso mensal com cartão.

A detecção do nível não é suposta: vem de um campo que cada origem já
fornecia — o grupo de classificação na conta corrente, e uma coluna
indicadora no arquivo do cartão.

### Chaves substitutas nunca são renumeradas

As dimensões crescem sozinhas: um ativo ou categoria que aparece pela
primeira vez ganha linha nova. Mas **a chave de um membro existente
nunca muda**, porque o fato aponta para ela.

Os atributos derivados de regra, ao contrário, são atualizados. Sem
isso, melhorar uma regra só valeria para os registros novos — foi
exatamente o que aconteceu quando uma classe de ativo continuou
marcada como não classificada depois de a regra que a cobria já
existir.

### Membros para ausência de valor

Toda dimensão tem um membro de chave `-1` representando "não
informado" ou "não aplicável". Assim o fato nunca precisa de chave
estrangeira nula, e o relatório mostra um rótulo legível em vez de uma
linha em branco.

---

## Identidade do evento

Cada lançamento tem um `hash_negocio`: um SHA-256 da chave de negócio
normalizada. É o que permite deduplicar entre arquivos e o que liga o
mesmo evento entre as camadas.

A composição da chave muda conforme o que a origem oferece:

| Origem | Chave de negócio |
|---|---|
| Investimentos | data + descrição + valor + **saldo corrente** |
| Conta corrente | data + descrição + valor + **número da ocorrência** |
| Cartões | data + descrição + valor + data da fatura + ocorrência |

O saldo entra na chave de propósito: em um extrato com saldo corrente,
duas transações reais idênticas no mesmo dia têm saldos diferentes,
enquanto uma linha lançada em duplicidade repete o saldo. Foi assim que
20 duplicatas silenciosas foram identificadas com certeza.

Onde não há saldo — o extrato bancário traz apenas data, descrição e
valor — a chave usa um contador de ocorrência. Duas compras idênticas
no mesmo dia são eventos reais e ambas são preservadas.

A constraint é `UNIQUE` no banco. **A duplicação deixa de depender de o
script estar correto.**

---

## Documentação dentro do banco

Toda tabela e toda coluna têm descrição gravada como *extended
property*, aplicada por um utilitário (`dbo.sp_documenta`) que todo
script de DDL usa.

A view `gold.vw_glossario_dados` expõe isso como tabela consultável,
com tipo, obrigatoriedade, papel da coluna e a descrição de negócio.
É a origem do [glossário](glossario.md) e pode virar uma página do
próprio Power BI.

A escolha de manter a documentação no banco, e não num documento
separado, tem uma razão prática: ela viaja com o backup, não se perde
numa reorganização de pastas e fica ao lado do objeto que descreve —
que é onde alguém procura quando tem a dúvida.
