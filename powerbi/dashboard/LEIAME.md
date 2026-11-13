# Dashboard de Finanças Geral

Primeira aba do painel novo, fiel ao esboço em
`Dashboard_Financas_Pessoais (1).pdf`.

```
python gerar_fundo.py --previa   # desenha o PNG e a prévia com os visuais marcados
python gerar_painel.py           # gera o PBIP e valida os JSONs contra os schemas
python conferir_modelo.py        # toda referência de medida e coluna resolve?
python conferir_layout.py        # todo visual dentro da moldura, nada sobreposto?
```

Depois: abrir `Dashboard.pbip` no Power BI Desktop e **Arquivo › Salvar
como › .pbix**. Esse é o único caminho documentado de PBIP para `.pbix`
— o `.pbix` guarda o modelo num `DataModel` binário que não se escreve
à mão.

O Desktop precisa das três opções ligadas em *Arquivo › Opções ›
Recursos de visualização*: **Power BI Project (.pbip)**, **Store
semantic model using TMDL format** e **Store reports using enhanced
metadata format (PBIR)**.

Os alvos de cada número estão em
[`../dax/conferir-financas-geral.py`](../dax/conferir-financas-geral.py);
o racional de cada medida, em
[`../dax/financas-geral.md`](../dax/financas-geral.md).

---

## O modelo é uma cópia das gold

Cinco tabelas, cada uma um `SelectColumns` da gold correspondente, sem
nenhuma transformação no Power Query:

| Tabela | Origem |
|---|---|
| `fato_movto_financ` | `gold.fato_movto_financ` |
| `dim_calendario` | `gold.dim_calendario` |
| `dim_grupo_financ` | `gold.dim_grupo_financ` |
| `dim_categoria_financ` | `gold.dim_categoria_financ` |
| `dim_origem` | `gold.dim_origem` |

**O que precisa ser derivado é coluna calculada em DAX**, e não um
passo escondido no M — assim aparece no modelo, com descrição, e quem
abrir vê que aquilo não veio do banco:

- `dim_grupo_financ` → `DS_CLASSE`, `NM_CLASSE`, `NR_ORDEM_CLASSE`
- `dim_calendario` → `NR_SEMANA_MES`

**Duas tabelas não vêm da gold:** `Composicao` (4 linhas) e
`Indicadores` (3 linhas). São eixos **desconectados** de propósito — os
dois blocos do esboço põem medidas *diferentes* na mesma coluna, e isso
não se faz com dimensão de verdade.

---

## Os três filtros que estão em tudo

| Filtro | O que evita |
|---|---|
| `DS_NIVEL = "ANALITICO"` | contar o cartão duas vezes — a compra e o pagamento da fatura. Em setembro são R$ 7.565 de diferença |
| `DS_CLASSE <> "Nao e gasto"` | aporte, resgate e transferência entrarem como receita ou gasto |
| `KEEPFILTERS` | a medida ignorar o slicer do próprio campo que ela filtra |

O `KEEPFILTERS` é o menos óbvio. Sem ele, `CALCULATE` com filtro
booleano **substitui** o filtro daquela coluna, e o bloco de categorias
mostraria o mesmo total em todas as linhas.

---

## Onde eu me afastei do esboço, e por quê

**1. A estrela virou seta.** O esboço usa ★ nos dois cartões de saldo.
Ela não existe no Segoe UI e sai como quadrado vazio — justo nos
cartões que fecham negativo em metade dos seus meses. `▲`/`▼` dizem a
mesma coisa e dizem o **sinal**, que num cartão de saldo é a informação
principal.

**2. "100% da Renda" virou a abertura da receita.** O subtítulo do
cartão 1 no esboço não informa nada: receita é 100% dela mesma. No
lugar entra `salário 63,6% · outras 36,4%`, que é o que aquele cartão
tem a dizer.

**3. As três caixas de oportunidade viraram uma tabela de três linhas.**
Três cartões separados precisariam do grupo no contexto de filtro de
cada um, e um cartão não tem contexto de linha. A tabela corta no
terceiro pela própria medida (`RANKX`), então o resultado é o mesmo e
funciona de verdade.

**4. "OUTROS GASTOS (PIX / DÉBITO)" virou "(CONTA CORRENTE / DÉBITO)".**
Na sua base o Pix sai da conta corrente e não vem marcado como Pix. O
rótulo antigo prometia um recorte que o dado não tem.

---

## O que o esboço supõe e seus números contrariam

Não mexi nos visuais por isso — é o dado falando —, mas vale saber
antes de olhar a tela pela primeira vez:

| | Esboço | Setembro/2026 real |
|---|---|---|
| Cartão de crédito | 68% da despesa | **40,5%** |
| Saldo apenas salário | +R$ 2.116 | **−R$ 2.436,62** |
| Três maiores cortes | Assinaturas, Delivery, Recorrentes | **ALMOÇO, Butecando, Lanche** |

Fora do cartão são R$ 5.770,04 em apenas 17 lançamentos — é lá que
moram Conta Família, escola e IPVA. E streaming existe, mas é R$ 51/mês
na média de 12 meses: cancelar quatro serviços rende menos do que
trocar dois almoços por semana.

---

## O que pode não renderizar na primeira abertura

Três propriedades são aceitas pelo schema mas dependem da versão do
Desktop. Nenhuma quebra nada: ignoradas, o visual continua certo, só
menos enfeitado.

| | Se for ignorada | Como ligar à mão |
|---|---|---|
| `dataBars` nas tabelas | tabela sem a barra colorida | Formatar › Barras de dados |
| `alignment` nos cartões | o número centraliza na caixa | Formatar › Rótulo de chamada |
| `Cor do dia` no calendário | quadrinhos sem cor de fundo | Elementos da célula › Cor de plano de fundo › fx › Valor do campo |

---

## A armadilha que já custou uma abertura

**"Ordenar por coluna" é dependência, igual a uma referência de
fórmula.** Esta dupla fecha um ciclo e o Desktop recusa o **modelo
inteiro** — não só as duas colunas:

```
DS_CLASSE          ordenada por  →  NR_ORDEM_CLASSE
NR_ORDEM_CLASSE    calculada de  →  DS_CLASSE
```

> *Uma dependência circular foi detectada: dim_grupo_financ[DS_CLASSE],
> dim_grupo_financ[NR_ORDEM_CLASSE], dim_grupo_financ[DS_CLASSE].*

Nada acusa antes de abrir: a geração roda, os schemas validam, cada
referência resolve sozinha. Só o grafo inteiro denuncia.

O conserto foi fazer `NR_ORDEM_CLASSE` ler a **coluna de origem**
(`DS_COMPRESSIBILIDADE`) em vez da calculada. Não precisa de `COALESCE`:
o nulo não casa com nenhum ramo do `SWITCH` e cai no padrão 4 — que é
exatamente a posição de "A classificar".

`conferir_modelo.py` agora monta o grafo de dependências entre colunas
— arestas de fórmula e de ordenação — e falha se achar ciclo.

> Por que o painel de Gastos, uma pasta acima, nunca teve esse
> problema: lá `DS_CLASSE` e `NR_ORDEM_CLASSE` vêm do **Power Query**.
> Coluna de origem não cria dependência no modelo; coluna calculada
> cria.

---

## Como o fundo não sai desalinhado

O PNG e a posição de cada visual saem **da mesma constante** em
`gerar_painel.py`. Mover um painel é mudar um número, e as duas coisas
andam juntas por construção.

`conferir_layout.py` falha se um visual escapar da moldura, pisar em
outro, invadir o rodapé, entrar na faixa que o PNG reserva para a
legenda do calendário, ou estiver com fundo, borda ou título do Power
BI ligados — a moldura dupla.

Para ver o encaixe sem abrir o Desktop: `python gerar_fundo.py --previa`
e olhe `_previa-financas-geral.png`, que mostra os retângulos dos
visuais sobre o desenho, em 1×.

**Regerar apaga ajustes feitos à mão** dentro de `Dashboard.Report`.

---

## Próximas abas

A página se chama `financas-geral`. Para a segunda aba, acrescente uma
entrada em `PAGINA` (vira lista), um dicionário de painéis próprio e um
montador em `relatorio.py` — foi assim que o painel de Gastos, uma
pasta acima, chegou a três páginas.

O `pbir.py` é compartilhado pelos três projetos. `gerar_painel.py` põe
a pasta-mãe **no fim** do `sys.path`: ela tem um `relatorio.py` e um
`gerar_painel.py` próprios, e na frente sequestraria os dois imports.
