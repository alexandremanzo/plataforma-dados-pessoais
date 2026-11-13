# Painel de finanças pessoais

Uma página, seguindo o modelo em `Dashboard_Financas_Pessoais.pdf`:
quatro cartões de topo, histórico de doze meses, top 5 de categorias e o
bloco de gastos não essenciais. Os números do PDF eram fictícios; aqui
todos saem de `db-manzo`.

```
python gerar_fundo.py --previa   # desenha o PNG e a prévia com os visuais marcados
python gerar_painel.py           # gera o PBIP e valida os JSONs contra os schemas
python conferir_modelo.py        # toda referência de medida e coluna resolve?
python conferir_layout.py        # todo visual dentro da moldura, nada sobreposto?
python conferir_numeros.py       # o que cada elemento TEM de mostrar, calculado em SQL
```

Depois: abrir `Financas.pbip` no Power BI Desktop e **Arquivo › Salvar
como › .pbix**. Esse é o único caminho documentado de PBIP para `.pbix` —
o `.pbix` guarda o modelo num `DataModel` binário que não se escreve à
mão.

O Desktop precisa das três opções de visualização ligadas em *Arquivo ›
Opções › Recursos de visualização*: **Power BI Project (.pbip)**,
**Store semantic model using TMDL format** e **Store reports using
enhanced metadata format (PBIR)**.

---

## O que este painel diz que o modelo não dizia

O PDF pressupõe sobra: receita acima da despesa, taxa de poupança
positiva, uma estrela no cartão de saldo. A base diz outra coisa.

| | |
|---|---|
| Meses no vermelho pela receita total | **6 de 12** |
| Meses no vermelho contando só o salário | **12 de 12** |
| Salário médio | R$ 7.715/mês |
| Despesa média | R$ 11.290/mês |

Os meses positivos existem por entrada **não recorrente**: previdência
(R$ 15.899 num lançamento), PLR, FGTS, venda do sedan, saque-aniversário.
Janeiro e março de 2026 sozinhos sustentam o ano.

Por isso o histórico tem **três** linhas e não duas. A terceira,
tracejada e cinza, é só a receita recorrente. Ela existe para que a
despesa cruzando o salário fique visível também nos meses em que o total
fecha positivo — que é a informação que o modelo em PDF não tinha como
mostrar.

---

## As três decisões que explicam o resto

**1. O seletor de período é uma tabela desconectada (`dPeriodo`).**
Se ele filtrasse `dCalendario`, o histórico de doze meses encolheria para
o único mês escolhido: a mesma coluna seria eixo e filtro ao mesmo tempo.
Desconectado, o mês escolhido vira um escalar que cada medida aplica onde
quer.

**2. Sem nada selecionado, o painel abre no último mês com dado.** Não
depende de estado salvo no seletor — o PBIR grava isso de forma frágil e
o Desktop reescreve na primeira edição. Depende do dado.

**3. O mês corrente é marcado como parcial.** Cada origem para num dia
diferente: em setembro/2026 o cartão XP vai até 27/09 e o Itaú até 18/09.
`Dados completos até` é o **menor** dos últimos dias das origens que
movimentaram no mês — a data a partir da qual o número ainda sobe. Sem
isso o cartão de saldo do mês corrente mente por omissão.

---

## Onde ficam as regras

**O que é gasto não essencial** não está escrito em DAX nem em M: está em
`gold.dim_grupo_financ.DS_COMPRESSIBILIDADE`, alimentada por
`scripts/sql/44_compressibilidade.sql`. Reclassificar um grupo é um
`UPDATE`, não uma alteração de painel.

Grupo ainda sem classificação aparece como **"A classificar"**, nunca
como nulo somido na conta — em setembro são R$ 231,91 em 11 lançamentos.
Lacuna que aparece na tela é lacuna que alguém preenche.

**O que é receita recorrente** é a lista `GRUPOS_RECORRENTES` em
`gerar_painel.py`, hoje só `["Salário"]`. Conferido em 24 meses: salário
aparece em 22; o segundo colocado em valor (previdência, R$ 112 mil)
aparece em dois. Não há meio-termo a classificar. A lista fica visível no
código de propósito: é um julgamento, não um dado.

**Aporte, resgate e transferência** não entram em lugar nenhum — são a
classe `Nao e gasto`, excluída já nas medidas-base `[Receita]` e
`[Despesa]`.

**A fração de corte** do bloco de oportunidades é o parâmetro `pCorte`
(hoje 0,5 = metade, como no modelo). Muda em *Transformar dados ›
Parâmetros*, sem tocar no código.

---

## A armadilha que já custou uma abertura

**Predicado booleano de `CALCULATE` não pode citar medida.** Escrito
assim, o DAX recusa a medida inteira:

```dax
CALCULATE ( [Receita], dCalendario[NM_ANO_MES] = [Mês de referência] )
```

Nada falha antes de abrir: o gerador roda, os JSONs validam, os `.tmdl`
saem perfeitos. No Desktop, cada visual atingido abre dizendo *"Selecione
ou adicione dados para preencher este visual"* — sem citar a medida nem
o motivo. Foram **20 medidas de 36** e **14 visuais de 18**, porque tudo
que filtra pelo mês passa pelas mesmas três medidas-base.

O conserto é passar por uma `VAR`, e aí o predicado volta a comparar
coluna com escalar:

```dax
VAR _m = [Mês de referência]
RETURN CALCULATE ( [Receita], REMOVEFILTERS ( dCalendario ),
                   dCalendario[NM_ANO_MES] = _m )
```

`conferir_modelo.py` agora procura esse padrão e falha antes de abrir o
Desktop. Dentro de `FILTER` a mesma escrita é legal — `FILTER` recebe
uma tabela, não um predicado —, então o teste olha qual função envolve a
comparação em vez de acusar o padrão em qualquer lugar.

---

## Como o fundo não sai desalinhado

O PNG e a posição de cada visual saem **da mesma constante** em
`gerar_painel.py`. Mover um painel é mudar um número, e as duas coisas
andam juntas por construção. `conferir_layout.py` falha se algum visual
escapar da moldura, pisar em outro ou estiver com fundo, borda ou título
do Power BI ligados — a moldura dupla.

Para regerar o fundo depois de mexer na grade: `python gerar_fundo.py
--previa` e olhar `_previa-financas.png`, que mostra os retângulos dos
visuais sobre o desenho, em 1×.

**Regerar apaga ajustes feitos à mão** dentro de `Financas.Report`.

---

## O que pode não renderizar na primeira abertura

Três propriedades são aceitas pelo schema mas dependem da versão do
Desktop. Nenhuma quebra nada: se forem ignoradas, o visual continua certo,
só menos enfeitado.

| | Se for ignorada | Como ligar à mão |
|---|---|---|
| `dataBars` no top 5 | tabela sem a barra colorida | Formatar › Barras de dados |
| `lineStyle: dashed` | a linha do salário sai sólida, mas cinza | Formatar › Linhas |
| `alignment: left` nos cartões | o número centraliza na caixa | Formatar › Rótulo de chamada |

---

## Arquivos

| | |
|---|---|
| `gerar_painel.py` | grade, paleta, consultas M, 36 medidas, modelo e relatório |
| `relatorio.py` | os 18 visuais da página |
| `gerar_fundo.py` | desenha `fundo-financas.png` (2560×2000, 2× a tela) |
| `conferir_modelo.py` | 54 referências entre medidas e 38 a colunas resolvem |
| `conferir_layout.py` | 18 visuais, 153 pares, moldura e sobreposição |
| `conferir_numeros.py` | o alvo de cada elemento, calculado em SQL |

O `pbir.py` é compartilhado com o painel de Gastos, uma pasta acima.
`gerar_painel.py` põe a pasta-mãe **no fim** do `sys.path`: ela tem um
`relatorio.py` e um `gerar_painel.py` próprios, e na frente sequestraria
os dois imports.
