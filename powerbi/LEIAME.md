# Painel de controle de gastos

Três páginas sobre `gold.fato_movto_financ`, com uma meta de fatura de
**R$ 4.150** e um indicador para olhar uma vez por dia.

| Página | Responde |
|---|---|
| **Controle do mês** | quanto já entrou na fatura em aberto, quanto ainda cabe, e se o ritmo atual estoura a meta |
| **Histórico** | como a fatura se comportou, e o consumo por natureza ao longo do tempo |
| **Onde dá para cortar** | o gasto compressível separado do essencial e do eventual |

---

## Para gerar o `.pbix`

### 1. Ligue três recursos de visualização (uma vez só)

**Arquivo › Opções e configurações › Opções › Recursos de visualização**:

- `Power BI Project (.pbip) save option`
- `Store semantic model using TMDL format`
- `Store reports using enhanced metadata format (PBIR)`

Reinicie o Desktop. **Sem os três o projeto não abre.**

### 2. Abra, conecte e salve

1. Abra **`Gastos.pbip`**.
2. O Power BI vai pedir credenciais do SQL Server na primeira vez — as
   mesmas do `.env` (`DB_USER` / `DB_SENHA`), em **Banco de dados**.
3. **Arquivo › Salvar como › `Gastos.pbix`**.

O modo é **Import**: os dados entram no arquivo. Para atualizar, clique
**Atualizar** — a carga do Airflow roda todo dia, então uma atualização por
manhã basta.

> O `.pbix` passa a conter seus dados financeiros. Ele está no
> `.gitignore`, junto com `.pbi/cache.abf`. Confira antes de commitar.

---

## Para conferir se está certo

```
python conferir_numeros.py
```

Lê o banco direto e imprime o alvo de cada indicador. Rode antes de abrir o
Power BI: número diferente do alvo vira defeito, em vez de virar dúvida.

```
python conferir_layout.py
```

Confere que a moldura do PNG e a posição do visual saem da mesma constante,
e que nenhum visual ficou com borda ligada por cima de uma moldura que já
existe no fundo.

---

## Para mudar o painel

```
python gerar_fundo.py --previa     # redesenha as molduras
python gerar_painel.py             # regera modelo e relatório, validando
python conferir_layout.py          # confere que os dois concordam
```

**Nesta ordem** — o segundo passo copia os PNGs para dentro do relatório.

| O quê | Onde |
|---|---|
| **Meta da fatura** | `META_PADRAO` em `gerar_painel.py`, ou o parâmetro `pMeta` dentro do Power BI |
| Dias entre fechamento e vencimento | `DIAS_ANTES_FECHAMENTO` / parâmetro `pDiasFechamento` |
| Servidor e banco | parâmetros `pServidor` e `pBanco` |
| Cores | bloco `Paleta` |
| Páginas, painéis e cartões | `PAGINAS` |
| Medidas DAX | lista `MEDIDAS` |
| Visuais | `relatorio.py` |

> Regerar **apaga e refaz** `Gastos.Report` e `Gastos.SemanticModel`. Ajuste
> feito à mão dentro dessas pastas se perde — mexa no gerador.

---

## As duas armadilhas dos dados

Estão tratadas no modelo, mas quem for mexer precisa saber:

**1. `DS_NIVEL = 'SINTETICO'` é pagamento de fatura.** São 86 lançamentos que
representam o total do cartão saindo da conta corrente. Somados junto com as
transações do cartão, contariam tudo duas vezes — e o erro não se denuncia,
só dobra o número. A consulta `Movimentacao` os exclui.

**2. As parcelas ficam gravadas no mês da compra.** Uma revisão em cinco
vezes aparece cinco vezes no mesmo dia. Quem diz o que cai em cada fatura é
`SK_DATA_FATURA` — e é por isso que existem **duas dimensões de data** no
modelo: `dCalendario` (a compra) e `dFatura` (a cobrança).

Uma consequência disso apareceu na conferência e vale registrar: a
**projeção de fechamento** mede o ritmo só sobre a compra **à vista**. Medir
sobre a fatura inteira cobraria a mesma revisão de carro todo dia até o
fechamento — a primeira versão projetava R$ 9.982 onde o certo eram
R$ 5.563.

---

## A classificação do gasto

`gold.dim_grupo_financ.DS_COMPRESSIBILIDADE`, criada pelo script
`scripts/sql/44_compressibilidade.sql`:

| Valor | Significa |
|---|---|
| **Compressível** | discricionário e recorrente — comida fora, assinatura, lazer |
| **Essencial** | moradia, escola, combustível, saúde, imposto |
| **Eventual** | não se repete: revisão, eletrodoméstico, viagem, reforma |
| **Não é gasto** | aporte, resgate, transferência — existe para **não** ser somado |
| *(nula)* | grupo ainda não classificado; aparece como **A classificar** |

**A semeadura é um ponto de partida, não um veredito.** Mudar é um `UPDATE`:

```sql
UPDATE gold.dim_grupo_financ
   SET DS_COMPRESSIBILIDADE = 'Essencial'
 WHERE NM_GRUPO = 'Academia';
```

É seguro editar à mão: `sincroniza_classificacao()` só faz `INSERT` de
membros novos e nunca reescreve linha existente. Grupo novo nasce nulo e
**aparece** no painel como *A classificar* — lacuna que aparece é lacuna que
alguém preenche.

Hoje 137 grupos estão classificados, cobrindo R$ 699,7 mil dos R$ 709,6 mil de
gasto em 24 meses. Os R$ 9,7 mil restantes estão espalhados em 383 grupos
pequenos.

---

## Detalhes que mordem

- **UTF-8 sem BOM** em todo arquivo do projeto PBIP. É o **inverso** da regra
  dos `.sql` deste mesmo repositório, onde o BOM é obrigatório por causa do
  sqlcmd. `pbir.py` confere isso a cada rodada.
- **Se o fundo não aparecer**, o Power BI recusou o `resourcePackages`
  escrito à mão. Contorno de 20 segundos: *Formatar página › Tela de fundo ›
  Procurar*, aponte `fundo-<página>.png`, transparência **0%**, ajuste
  **Ajustar**.
- **O ciclo da fatura é inferido**, não lido de um cadastro: vence dia 15 e
  fecha sete dias antes. Se a XP mudar o vencimento, ajuste
  `DIAS_ANTES_FECHAMENTO` — ou o indicador diário passa a contar errado em
  silêncio.
