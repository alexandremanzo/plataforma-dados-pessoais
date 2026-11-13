# DAX — aba Finanças Geral

Organizado na ordem do esboço, bloco a bloco. Cada seção diz o que o
esboço mostra e entrega as medidas daquele pedaço.

**Nomes de tabela:** `fato_movto_financ`, `dim_grupo_financ`,
`dim_origem`, `dim_categoria_financ`, `dim_calendario` — como o Power BI
nomeia ao importar do SQL. Se você renomeou, é um localizar-e-substituir.

| Bloco do esboço | Seção |
|---|---|
| Cabeçalho · Período | [0](#0-base) |
| 4 cartões do topo | [1](#1-os-quatro-cartões-do-topo) |
| Composição de Entradas e Saídas | [2](#2-composição-de-entradas-e-saídas) |
| Indicadores Percentuais Estratégicos | [3](#3-indicadores-percentuais-estratégicos) |
| Cartão de Crédito × Outros Gastos | [4](#4-cartão-de-crédito--outros-gastos) |
| % Gastos por Categoria | [5](#5--gastos-por-categoria) |
| Gasto por Dia (Calendário) | [6](#6-gasto-por-dia--o-calendário) |
| Destaque: o que pode ser cortado | [7](#7-destaque-o-que-pode-ser-cortado) |

---

## 0. Base

### Três colunas calculadas em `dim_grupo_financ`

```dax
DS_CLASSE = COALESCE ( dim_grupo_financ[DS_COMPRESSIBILIDADE], "A classificar" )
```

**Não é opcional.** 383 dos 520 grupos estão sem classificação. Num
slicer, a coluna crua mostra um item em branco, que se lê como "nada" —
e some da soma sem avisar. Como `"A classificar"` ele aparece, é
clicável, e a lacuna fica visível. São 4,4% da sua despesa.

```dax
NM_CLASSE =
SWITCH (
    dim_grupo_financ[DS_CLASSE],
    "Compressivel", "Compressível",
    "Nao e gasto",  "Não é gasto",
    dim_grupo_financ[DS_CLASSE]
)
```

O banco grava sem acento (a `CHECK` da coluna exige). `NM_CLASSE` vai
para eixo e legenda; `DS_CLASSE` fica para a lógica.

```dax
NR_ORDEM_CLASSE =
SWITCH ( dim_grupo_financ[DS_CLASSE],
    "Compressivel", 1, "Eventual", 2, "Essencial", 3, "A classificar", 4, 5 )
```

Marque `NM_CLASSE` com *Classificar por coluna → NR_ORDEM_CLASSE*.

### Uma coluna calculada em `dim_calendario`

O calendário do bloco 6 precisa de linhas — semana dentro do mês — e
essa coluna não existe no banco:

```dax
NR_SEMANA_MES =
VAR _primeiro = DATE ( dim_calendario[NR_ANO], dim_calendario[NR_MES], 1 )
VAR _desloc   = WEEKDAY ( _primeiro, 1 ) - 1
RETURN
    INT ( ( dim_calendario[NR_DIA] + _desloc - 1 ) / 7 ) + 1
```

`WEEKDAY(_,1)` devolve 1 para domingo, que é a coluna em que seu
calendário começa. O deslocamento empurra o dia 1 para a posição certa
na primeira linha.

### O seletor de período

Slicer em `dim_calendario[NM_MES_ANO]` (`Set/2026`), e em *Coluna →
Classificar por coluna* aponte para `NM_ANO_MES` (`2026-09`), que ordena
sozinho. Esta aba é toda do mês corrente, então o filtro direto no
calendário basta — não precisa de tabela desconectada.

Para o rótulo do cabeçalho, no formato do esboço:

```dax
Período selecionado =
VAR _n = DISTINCTCOUNT ( dim_calendario[NM_ANO_MES] )
RETURN
    IF (
        _n = 1,
        SELECTEDVALUE ( dim_calendario[NM_MES] ) & " / "
            & FORMAT ( SELECTEDVALUE ( dim_calendario[NR_ANO] ), "0" ),
        FORMAT ( _n, "#,0" ) & " meses selecionados"
    )
```

> O `FORMAT ( ..., "0" )` no ano não é enfeite: concatenar um número
> direto com `&` usa o formato regional e sai **2.026**.

---

## 1. Os quatro cartões do topo

Três filtros se repetem em tudo o que vem daqui para baixo, e cada um
evita um erro específico:

| Filtro | O que evita |
|---|---|
| `DS_NIVEL = "ANALITICO"` | contar o cartão duas vezes — a compra e o pagamento da fatura |
| `DS_CLASSE <> "Nao e gasto"` | aporte, resgate e transferência entrarem como receita ou gasto |
| `KEEPFILTERS` | a medida ignorar o slicer do próprio campo que ela filtra |

O `KEEPFILTERS` é o menos óbvio e o que mais importa nesta aba. Sem ele,
`CALCULATE` com filtro booleano **substitui** o filtro daquela coluna: o
bloco 5 mostraria o mesmo total em todas as categorias.

```dax
Receita total =
CALCULATE (
    SUM ( fato_movto_financ[VL_TRANSACAO] ),
    KEEPFILTERS ( fato_movto_financ[DS_TIPO_FLUXO] = "RECEITA" ),
    KEEPFILTERS ( fato_movto_financ[DS_NIVEL] = "ANALITICO" ),
    KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] <> "Nao e gasto" )
)
```

```dax
Despesa total =
VAR _v =
    CALCULATE (
        SUM ( fato_movto_financ[VL_TRANSACAO] ),
        KEEPFILTERS ( fato_movto_financ[DS_TIPO_FLUXO] = "DESPESA" ),
        KEEPFILTERS ( fato_movto_financ[DS_NIVEL] = "ANALITICO" ),
        KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] <> "Nao e gasto" )
    )
RETURN
    IF ( NOT ISBLANK ( _v ), - _v )
```

> **Por que a `VAR` em vez de `- CALCULATE ( ... )`.** A base grava
> despesa como número negativo, então a medida precisa inverter o sinal
> — e inverter o sinal de um resultado vazio é onde o DAX trata branco
> como zero em algumas construções e preserva o branco em outras. A
> `VAR` decide explicitamente: sem linha, devolve branco.
>
> Isso aparece no calendário do bloco 6: com zero, todo dia sem gasto
> ganha um `R$ 0,00`; com branco, o quadrinho fica vazio.

```dax
Saldo total = [Receita total] - [Despesa total]
```

```dax
Receita salário =
CALCULATE ( [Receita total], KEEPFILTERS ( dim_grupo_financ[NM_GRUPO] IN { "Salário" } ) )
```

```dax
Saldo sobre salário = [Receita salário] - [Despesa total]
```

### Os subtítulos dos cartões

```dax
% despesa sobre receita = DIVIDE ( [Despesa total], [Receita total] )
```

```dax
% saldo sobre receita total = DIVIDE ( [Saldo total], [Receita total] )
```
*A "Margem Líquida" do cartão 3.*

```dax
% saldo sobre salário = DIVIDE ( [Saldo sobre salário], [Receita salário] )
```
*O "Salário Limpo" do cartão 4.*

> **O acento em `"Salário"` é obrigatório.** O modelo compara texto sem
> distinguir maiúscula, mas **distinguindo acento** — `"Salario"`
> devolve branco, calado.
>
> A chave `IN { }` é para a lista crescer sem reescrever a medida. Hoje
> só `Salário`: em 24 meses ele aparece em 22. O segundo colocado em
> valor, `Previdencia` com R$ 112 mil, aparece em **dois** — é entrada
> extraordinária, não renda.

---

## 2. Composição de Entradas e Saídas

Quatro linhas com medidas diferentes na mesma coluna. Em Power BI isso
pede uma tabela desconectada: *Modelagem → Nova tabela*.

```dax
Composicao =
DATATABLE (
    "Ordem", INTEGER,
    "Fluxo", STRING,
    "Item",  STRING,
    {
        { 1, "Receita", "Receita Salário" },
        { 2, "Receita", "Outras Receitas" },
        { 3, "Despesa", "Despesas Essenciais" },
        { 4, "Despesa", "Despesas Outras (Não Essenciais)" }
    }
)
```

Marque `Item` com *Classificar por coluna → Ordem*, e **não crie
relacionamento** com nada: ela só serve de eixo.

As duas medidas que faltavam para compor as linhas:

```dax
Outras receitas = [Receita total] - [Receita salário]
```

```dax
Despesa essencial =
CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Essencial" ) )
```

```dax
Despesa outras = [Despesa total] - [Despesa essencial]
```

E o valor que a tabela mostra:

```dax
Valor da composição =
SWITCH (
    SELECTEDVALUE ( Composicao[Item] ),
    "Receita Salário",                  [Receita salário],
    "Outras Receitas",                  [Outras receitas],
    "Despesas Essenciais",              [Despesa essencial],
    "Despesas Outras (Não Essenciais)", [Despesa outras]
)
```

```dax
Cor do fluxo =
IF ( SELECTEDVALUE ( Composicao[Fluxo] ) = "Receita", "#10B981", "#EF4444" )
```

> **`Despesa outras` é subtração, não soma das outras classes.** Dá o
> mesmo número hoje — `Essencial + Compressível + Eventual + A
> classificar = Despesa total` sempre fecha —, mas se amanhã nascer uma
> classe nova na dimensão, a subtração continua certa e a soma passaria
> a deixar dinheiro de fora.

As três classes que compõem "outras", para quando quiser abrir:

```dax
Despesa compressível =
CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Compressivel" ) )
```

```dax
Despesa eventual =
CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "Eventual" ) )
```

```dax
Despesa a classificar =
CALCULATE ( [Despesa total], KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] = "A classificar" ) )
```

---

## 3. Indicadores Percentuais Estratégicos

Mesmo padrão: três linhas, três medidas diferentes.

```dax
Indicadores =
DATATABLE (
    "Ordem",     INTEGER,
    "Indicador", STRING,
    {
        { 1, "% Salário em relação à Receita Total" },
        { 2, "% Despesas Outras em relação à Despesa Total" },
        { 3, "% Saldo (apenas Salário) x Receita Total" }
    }
)
```

```dax
% salário na receita = DIVIDE ( [Receita salário], [Receita total] )
```

```dax
% despesa outras = DIVIDE ( [Despesa outras], [Despesa total] )
```

```dax
% saldo salário sobre receita total = DIVIDE ( [Saldo sobre salário], [Receita total] )
```

> **Este terceiro eu tinha entendido errado.** Na primeira entrega li
> *"% saldo considerando apenas salário x receita total"* como uma
> comparação entre duas taxas. Seu esboço mostra que é uma divisão: o
> saldo calculado só com salário, **dividido pela receita total**. Nos
> números do esboço, R$ 2.116 ÷ R$ 12.616 = 16,8% — e não os 21,3% do
> cartão 4, que divide pelo próprio salário.
>
> As duas convivem no esboço de propósito, e a diferença entre elas é
> informativa: 21,3% é quanto do salário sobrou; 16,8% é quanto esse
> mesmo valor representa de tudo que entrou.

```dax
Valor do indicador =
SWITCH (
    SELECTEDVALUE ( Indicadores[Indicador] ),
    "% Salário em relação à Receita Total",         [% salário na receita],
    "% Despesas Outras em relação à Despesa Total", [% despesa outras],
    "% Saldo (apenas Salário) x Receita Total",     [% saldo salário sobre receita total]
)
```

Formato `0.0%`. Para as barras coloridas do esboço:

```dax
Cor do indicador =
SWITCH ( SELECTEDVALUE ( Indicadores[Ordem] ),
    1, "#2563EB",
    2, "#F59E0B",
    3, "#10B981",
    "#94A3B8" )
```

Visual sugerido: matriz com `Indicador` nas linhas, `[Valor do
indicador]` nos valores, e *Barras de dados* ligadas com a cor por
*Valor do campo → Cor do indicador*.

### Bônus, fora do esboço

```dax
Efeito da receita extraordinária =
[% saldo sobre receita total] - [% saldo sobre salário]
```

Quanto a entrada não recorrente está embelezando o mês. Nos 12 meses
fechados até setembro/2026 são **52,6 pontos**: a taxa sobre receita
total fecha 6 de 12 meses no vermelho; sobre o salário, 12 de 12.

---

## 4. Cartão de Crédito × Outros Gastos

```dax
Despesa no cartão =
CALCULATE ( [Despesa total], KEEPFILTERS ( dim_origem[DS_TIPO_CONTA] = "Cartão de crédito" ) )
```

```dax
Despesa fora do cartão = [Despesa total] - [Despesa no cartão]
```

```dax
% no cartão = DIVIDE ( [Despesa no cartão], [Despesa total] )
```

```dax
% fora do cartão = DIVIDE ( [Despesa fora do cartão], [Despesa total] )
```

> **"Fora do cartão" é subtração, e precisa ser.** `DS_TIPO_CONTA` tem
> **seis** valores, não dois: Cartão de crédito, Conta corrente,
> Dinheiro e débito, Vale-alimentação, Conta de investimento e Não
> informado. Escrever `= "Conta corrente"` para o outro lado perderia
> os quatro restantes, e os dois cartões não somariam 100%.
>
> O rótulo do esboço diz "PIX / DÉBITO". Na sua base isso é quase todo
> **Conta corrente** (o Itaú) — o Pix sai de lá e não vem marcado como
> Pix. Vale ajustar o texto para "Conta corrente e débito", ou deixar
> como está sabendo que é um apelido.

> **Seu número real é o inverso do esboço.** Em setembro/2026: cartão
> **R$ 3.925,97 (40,5%)** contra **R$ 5.770,04 (59,5%)** fora dele. O
> esboço mostra 68/32. Os 17 lançamentos de conta corrente têm ticket
> médio alto — é lá que mora Conta Família, escola e IPVA.

---

## 5. % Gastos por Categoria

```dax
% da categoria na despesa =
DIVIDE (
    [Despesa total],
    CALCULATE ( [Despesa total], REMOVEFILTERS ( dim_categoria_financ ) )
)
```

`REMOVEFILTERS` só na dimensão de categoria: o denominador deixa de ser
a categoria da linha, mas continua respeitando o mês. Com `ALL()` no
lugar, o percentual passaria a ser sobre a base inteira e as fatias não
somariam 100%.

Para o "1., 2., 3." do esboço e o corte no top 5:

```dax
Posição da categoria =
VAR _r = RANKX ( ALLSELECTED ( dim_categoria_financ[NM_CATEGORIA] ), [Despesa total], , DESC )
RETURN
    IF ( _r <= 5, _r )
```

```dax
Despesa da categoria (top 5) =
VAR _r = RANKX ( ALLSELECTED ( dim_categoria_financ[NM_CATEGORIA] ), [Despesa total], , DESC )
RETURN
    IF ( _r <= 5, [Despesa total] )
```

```dax
% da categoria (top 5) =
VAR _r = RANKX ( ALLSELECTED ( dim_categoria_financ[NM_CATEGORIA] ), [Despesa total], , DESC )
RETURN
    IF ( _r <= 5, [% da categoria na despesa] )
```

> **O corte em cinco vem da medida, não de um filtro de visual.** Do
> sexto em diante tudo volta branco, e a tabela descarta sozinha a linha
> em que todas as medidas são brancas. Ordene por `[Posição da
> categoria]` crescente.
>
> **Sobre o "5. Outros" do esboço:** existe mesmo uma categoria chamada
> `OUTROS` na sua base, então pode ser que ela apareça no top 5 por
> conta própria. Não é um balde de resto — se quiser esse balde, é outra
> medida, e aviso que ela confundiria com a categoria de mesmo nome.

Se quiser o resto agrupado mesmo assim:

```dax
Despesa das demais categorias =
VAR _top5 =
    SUMX (
        TOPN ( 5, ALLSELECTED ( dim_categoria_financ[NM_CATEGORIA] ), [Despesa total], DESC ),
        [Despesa total]
    )
RETURN
    CALCULATE ( [Despesa total], REMOVEFILTERS ( dim_categoria_financ ) ) - _top5
```

---

## 6. Gasto por Dia — o calendário

Matriz: `NR_SEMANA_MES` nas linhas, `NM_DIA_SEMANA_ABREV` nas colunas,
`NR_DIA` como valor de cabeçalho. Desligue totais de linha e coluna.

```dax
Gasto do dia = [Despesa total]
```

Alias de propósito: dentro do calendário, "Despesa total" num quadrinho
de um dia lê errado.

```dax
% do dia no mês =
DIVIDE (
    [Despesa total],
    CALCULATE ( [Despesa total], ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) )
)
```

`ALLEXCEPT` preservando `NM_ANO_MES`: tira o dia do filtro e mantém o
mês. O denominador usa **`NM_ANO_MES`** (`2026-09`), a chave — não
`NM_MES_ANO` (`Set/2026`), que é rótulo.

Para o "Média: R$ 261/dia" do cabeçalho do bloco:

```dax
Gasto médio do dia no mês =
VAR _mes =
    CALCULATE ( [Despesa total], ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) )
VAR _dias =
    CALCULATE ( COUNTROWS ( dim_calendario ), ALLEXCEPT ( dim_calendario, dim_calendario[NM_ANO_MES] ) )
RETURN
    DIVIDE ( _mes, _dias )
```

### As três cores da legenda

```dax
Limite de pico = 1000
```

Medida separada para o limiar não ficar escondido dentro de um `IF`.
Para virar controle: *Modelagem → Novo parâmetro → Campo numérico*.

```dax
Cor do dia =
VAR _v   = [Despesa total]
VAR _fds = SELECTEDVALUE ( dim_calendario[FL_FIM_SEMANA] ) = "S"
VAR _fer = SELECTEDVALUE ( dim_calendario[FL_FERIADO] ) = "S"
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( _v ),          "#F8FAFC",   -- dia sem gasto
        _v > [Limite de pico],   "#FEE2E2",   -- pico
        _fer,                    "#EDE9FE",   -- feriado
        _fds,                    "#FEF3C7",   -- fim de semana
        "#FFFFFF"                             -- diário comum
    )
```

A ordem do `SWITCH` é a ordem de prioridade: um pico num domingo pinta
de pico, não de fim de semana — é a informação mais rara das duas.

Ligue em *Formatar → Elementos da célula → Cor de plano de fundo → fx →
Formatar por: Valor do campo → Cor do dia*.

> O feriado só existe aí porque o `47_dim_calendario_atributos.sql`
> colocou `FL_FERIADO` na dimensão. Nos 12 meses fechados até
> setembro/2026 o gasto médio é **R$ 208/dia** em feriado contra
> **R$ 423/dia** em dia comum — metade.

### Apoio

```dax
Dias com gasto =
CALCULATE (
    DISTINCTCOUNT ( fato_movto_financ[SK_DATA] ),
    KEEPFILTERS ( fato_movto_financ[DS_TIPO_FLUXO] = "DESPESA" ),
    KEEPFILTERS ( fato_movto_financ[DS_NIVEL] = "ANALITICO" ),
    KEEPFILTERS ( dim_grupo_financ[DS_CLASSE] <> "Nao e gasto" )
)
```

```dax
Gasto médio por dia com gasto = DIVIDE ( [Despesa total], [Dias com gasto] )
```

> **Dias *com gasto* e dias do mês são coisas diferentes.** Em 12 meses
> houve gasto em **328 dos 365 dias**. A média por dia corrido é
> R$ 372; por dia com gasto, R$ 414. Use a primeira no cabeçalho do
> calendário (é o que o esboço pede) e a segunda quando a pergunta for
> "quanto eu gasto quando gasto".

---

## 7. Destaque: o que pode ser cortado

```dax
% compressível = DIVIDE ( [Despesa compressível], [Despesa total] )
```

### A meta

O esboço traz `Meta: R$ 1.203,50/mês`, que é a soma dos três cartões de
oportunidade. Duas formas de chegar nela — escolha uma:

```dax
Meta pelos 3 maiores =
SUMX (
    TOPN ( 3, ALLSELECTED ( dim_grupo_financ[NM_GRUPO] ), [Despesa compressível], DESC ),
    [Despesa compressível]
)
```

```dax
Corte alvo = 0.5
```

```dax
Potencial de corte = [Despesa compressível] * [Corte alvo]
```

A primeira é o que o esboço desenha: o total dos três grupos que você
vai atacar. A segunda é uma fração de tudo que é compressível. A
primeira é mais honesta como meta — você corta grupos, não percentuais.

```dax
% da meta sobre a despesa = DIVIDE ( [Meta pelos 3 maiores], [Despesa total] )
```

```dax
% da meta sobre a receita = DIVIDE ( [Meta pelos 3 maiores], [Receita total] )
```

> **O esboço diz "Economia Potencial de 15,3% da Renda", mas a conta é
> sobre a despesa:** R$ 1.204 ÷ R$ 7.844 = 15,3%. Sobre a receita daria
> 9,5%. Deixei as duas — troque o rótulo para o que você quis dizer.

### Os três cartões de oportunidade

```dax
Posição da oportunidade =
VAR _r = RANKX ( ALLSELECTED ( dim_grupo_financ[NM_GRUPO] ), [Despesa compressível], , DESC )
RETURN
    IF ( _r <= 3, _r )
```

```dax
Valor da oportunidade =
VAR _r = RANKX ( ALLSELECTED ( dim_grupo_financ[NM_GRUPO] ), [Despesa compressível], , DESC )
RETURN
    IF ( _r <= 3, [Despesa compressível] )
```

> **Os seus três não são os do esboço.** Em setembro/2026 saem
> **ALMOÇO R$ 312,74**, **Butecando R$ 238,51** e **Lanche R$ 223,69** —
> comida fora de casa, não "Assinaturas Digitais". Streaming existe, mas
> é R$ 51/mês na média de 12 meses: cancelar os quatro serviços renderia
> menos do que trocar dois almoços por semana.
>
> A linha "Ação: Cancelar 4 serviços" é texto editorial, não medida. Se
> quiser que ela acompanhe o grupo, crie uma tabela de duas colunas
> (`NM_GRUPO`, `DS_ACAO`) e relacione com `dim_grupo_financ` — aí a ação
> vira dado e você edita sem mexer no relatório.

### O impacto

```dax
Saldo com o corte = [Saldo total] + [Meta pelos 3 maiores]
```

```dax
% saldo com o corte = DIVIDE ( [Saldo com o corte], [Receita total] )
```

```dax
Economia anualizada = [Meta pelos 3 maiores] * 12
```

```dax
Impacto do corte =
VAR _eco   = [Meta pelos 3 maiores]
VAR _saldo = [Saldo total]
VAR _rec   = [Receita total]
RETURN
    "Cortando " & FORMAT ( _eco, "R$ #,0.00" ) & " dos três maiores grupos compressíveis, "
        & "o saldo do mês vai de " & FORMAT ( _saldo, "R$ #,0.00" )
        & " para " & FORMAT ( _saldo + _eco, "R$ #,0.00" )
        & ", e a margem de " & FORMAT ( DIVIDE ( _saldo, _rec ), "0.0%" )
        & " para " & FORMAT ( DIVIDE ( _saldo + _eco, _rec ), "0.0%" ) & "."
```

### A cor do destaque

```dax
Cor da classe =
SWITCH (
    SELECTEDVALUE ( dim_grupo_financ[DS_CLASSE] ),
    "Compressivel",  "#F59E0B",
    "Eventual",      "#2563EB",
    "Essencial",     "#475569",
    "A classificar", "#CBD5E1",
    "#94A3B8"
)
```

O âmbar fica só no compressível: o destaque só funciona se uma coisa
estiver destacada.

---

## A armadilha que já custou uma abertura neste projeto

**Predicado booleano de `CALCULATE` não pode citar medida.** Isto é DAX
inválido, e o Power BI recusa a medida inteira:

```dax
CALCULATE ( [Receita total], dim_calendario[NM_ANO_MES] = [Mês de referência] )
```

Nada avisa ao salvar. O visual abre dizendo *"Selecione ou adicione
dados para preencher este visual"*, sem citar qual medida. No painel
anterior derrubou 20 medidas de 36 e 14 visuais de 18.

O conserto é passar por uma `VAR`:

```dax
VAR _m = [Mês de referência]
RETURN CALCULATE ( [Receita total], REMOVEFILTERS ( dim_calendario ), dim_calendario[NM_ANO_MES] = _m )
```

Vale quando as próximas abas pedirem seletor de período desconectado.

---

## Conferência

```
python conferir-financas-geral.py            # 12 meses fechados
python conferir-financas-geral.py 2026-09    # fecha a janela num mês
```

Imprime o alvo de cada medida acima, calculado em SQL pelo mesmo
critério. Compare com o que o Power BI mostra na mesma janela.

**Os números não estão escritos aqui de propósito.** A primeira versão
desta página trazia uma tabela de valores digitados, e oito dias depois
ela estava errada — não por erro de conta, mas porque chegou extrato
novo: o Itaú avançou de 18/09 para 28/09 e o cartão até 04/10. Conferir
medida contra alvo velho é pior do que não conferir, porque dá a
impressão de que foi conferido.

**Se algum número não bater, o suspeito número um é `DS_NIVEL`.** Sem
esse filtro a despesa de 12 meses vai de R$ 135,8 mil para R$ 206,9 mil
— os R$ 71,1 mil de diferença são o pagamento das faturas contado por
cima das compras que já estão lá dentro.
