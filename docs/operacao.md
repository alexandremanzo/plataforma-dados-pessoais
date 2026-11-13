# Operação

## O ciclo normal

O pipeline roda sozinho **três vezes por dia — 8h, 12h e 20h** (horário
de Brasília), pelo Airflow. Um arquivo colocado na pasta pela manhã
entra ainda no mesmo dia.

São **dez origens**. Oito exigem que você coloque ou edite um arquivo;
duas o pipeline busca sozinho.

### Origens que dependem de você

| Origem | Como obter | Onde colocar |
|---|---|---|
| Investimentos XP | Baixar o extrato no app | `Financeiro\Dados\xp\extrato-xp.xlsx` |
| Conta Itaú | Baixar o extrato e lançar na aba `cad-conta` | `Financeiro\Dados\dados-itau.xlsx` |
| Cartão XP | Lançar a fatura na aba `MOVTO` | `Financeiro\Dados\dados-xp-credito.xlsx` |
| Cartão Nubank | Lançar a fatura na aba `cad-credito` | `Financeiro\Dados\dados-nunbank-completo.xlsx` |
| Avaliação física | Lançar o laudo na aba `Avaliações`, uma linha por medida | `Documentos\Planilhas\pla-avaliacao-fisica.xls` |
| Manutenção do carro | Lançar a nota da oficina na aba `Avaliações` — **com o KM** | `Documentos\Planilhas\pla-revisao-auto.xls` |
| Histórico 2014-2018 | Lançar na aba `cadastro` — **com o `ID`** | `Financeiro\Dados\dados-financ-completo.xlsx` |
| Plano de revisão do carro | Nada a fazer — é o manual do fabricante | `Documentos\Planilhas\Plano_Manutencao_Montadora_SUV_2017.xlsx` |
| Exames de bioimpedância | Salvar a imagem que a nutricionista manda | `Documentos\Documentos\Saúde\Nutricionista\Avaliações\` |

Avaliação física, manutenção e plano de revisão ficam em pasta diferente
das financeiras, apontada por `PATH_PLANILHAS` no `.env`. Os exames de
bioimpedância ficam noutra ainda, em `PATH_EXAMES` — são imagem, e não
arquivo tabular.

**O exame não precisa de digitação.** A carga lê a imagem por OCR e tira
dela cerca de 40 campos, contra os 11 que cabiam no preenchimento manual.
A planilha de avaliação física continua valendo: as duas origens se
completam, com o arquivo na frente e a planilha cobrindo o que o OCR não
leu.

O plano de revisão é a única origem que **não é evento, e sim regra**:
diz o que o fabricante manda fazer, não o que aconteceu. Só muda se você
trocar de carro. Se isso acontecer, monte a planilha nova no mesmo
formato — a carga acha o veículo procurando o nome dele dentro do título
da aba, então `PLANO DE MANUTENÇÃO PREVENTIVA - MONTADORA SEDAN 2016`
encontra o Sedan sozinho, sem configuração nenhuma.

### Origens que o pipeline busca sozinho

| Origem | De onde | Configuração |
|---|---|---|
| Conta família | Aba do Google Sheets publicada como CSV | `PLANILHA_FAMILIA_URL` |
| Meu dia | Respostas do Google Forms, publicadas como CSV | `PLANILHA_DIA_URL` |

Não há etapa de exportar: basta editar a planilha ou responder o
formulário. São as únicas que dependem de rede, e por isso ficam em
ramos isolados — uma planilha fora do ar não impede as demais cargas.

> Como publicar uma aba e as armadilhas de encoding estão em
> [passo-a-passo/origem-google-sheets.md](passo-a-passo/origem-google-sheets.md).

Não há passo de "escolher o que é novo": a deduplicação é automática e
reprocessar é seguro.

---

## O que acontece quando você corrige a origem

Isto vale para todas as nove origens e é o comportamento que mais gera
dúvida.

**Campos fora da chave de negócio propagam até a gold.** Reclassificar,
trocar categoria, corrigir local, observação ou quantidade — é só editar
e rodar. As cargas fazem *upsert* e a correção atravessa as três
camadas.

**Campos que compõem a chave, não.** Alterar um deles muda a identidade
do registro: a carga insere um novo e o antigo fica órfão, sem aviso.

| Base | Chave imutável |
|---|---|
| Investimentos XP | data mov + data liq + descrição + valor + saldo |
| **Conta Itaú** | **coluna `ID` da planilha** |
| **Cartão XP** | **coluna `ID` da planilha** |
| **Histórico 2014-2018** | **coluna `ID` da planilha** |
| Cartão Nubank | data + título + valor + data fatura |
| Conta família | data + descrição + valor + ocorrência |
| Avaliação física | data + item |
| Manutenção do carro | data + veículo + item + ocorrência |
| **Meu dia** | **carimbo do formulário** |

As quatro em negrito têm **identificador próprio**, e nelas tudo o mais é
corrigível — inclusive data, descrição, valor e data da fatura. É a
diferença que permite bater o valor pago no cartão contra a soma dos
itens do mês: quando a conferência mostra que o gasto era da fatura
seguinte, corrigir a data move o lançamento em vez de duplicá-lo.

No *meu dia* o identificador vem de graça, atribuído pelo Google no
envio. No Itaú, no cartão XP e no histórico é uma coluna `ID` digitada — ver
[chave-id-cadastro-manual.md](passo-a-passo/chave-id-cadastro-manual.md)
para as regras de uso. Nas duas, a carga **recusa** se o `ID` faltar ou
repetir.

**Exclusões não propagam.** Apagar uma linha da planilha não a remove do
banco: as cargas comparam o que existe na origem com o que existe no
banco, mas nunca perguntam "o que sumiu?". Corrigir uma data ou um valor
e apagar a linha antiga deixa a antiga viva, inflando os totais.

---

## Rodando à mão

Cada carga é um script independente e idempotente. A ordem importa
apenas dentro de cada ramo — os ramos não dependem uns dos outros,
exceto onde indicado.

```powershell
cd "C:\caminho\plataforma-dados-pessoais"
$py = ".venv\Scripts\python.exe"

# Investimentos
& $py scripts\etl\carga_bronze_xp.py
& $py scripts\etl\carga_silver_xp.py
& $py scripts\etl\carga_gold_xp.py
& $py scripts\etl\exporta_consolidado_xp.py

# Conta corrente
& $py scripts\etl\carga_bronze_itau.py
& $py scripts\etl\carga_silver_itau.py

# Cartões
& $py scripts\etl\carga_bronze_cartao_xp.py
& $py scripts\etl\carga_bronze_cartao_nubank.py
& $py scripts\etl\carga_silver_cartao.py

# Histórico financeiro 2014-2018
& $py scripts\etl\carga_bronze_financ.py
& $py scripts\etl\carga_silver_financ.py

# Fato unificado — depende das TRÊS silvers acima
& $py scripts\etl\carga_gold_movimentacao.py

# Conta família
& $py scripts\etl\carga_bronze_familia.py
& $py scripts\etl\carga_silver_familia.py
& $py scripts\etl\carga_gold_familia.py

# Meu dia
& $py scripts\etl\carga_bronze_dia.py
& $py scripts\etl\carga_silver_dia.py
& $py scripts\etl\carga_gold_dia.py

# Avaliação física — gold_avaliacao une a planilha E os exames lidos
& $py scripts\etl\carga_bronze_avaliacao.py
& $py scripts\etl\carga_silver_avaliacao.py
& $py scripts\etl\carga_bronze_inbody.py
& $py scripts\etl\carga_silver_inbody.py
& $py scripts\etl\carga_gold_avaliacao.py

# Manutenção do carro — gold_auto precisa do histórico E do plano
& $py scripts\etl\carga_bronze_auto.py
& $py scripts\etl\carga_silver_auto.py
& $py scripts\etl\carga_bronze_revisao.py
& $py scripts\etl\carga_silver_revisao.py
& $py scripts\etl\carga_gold_auto.py
```

Várias cargas aceitam `--revisar` ou `--resumo`, que imprimem um
diagnóstico do que entrou sem alterar nada.

Dentro do container do Airflow, o interpretador é outro:

```powershell
docker compose exec airflow-scheduler /opt/etl-venv/bin/python /opt/projeto/scripts/etl/carga_bronze_itau.py
```

Para disparar pelo Airflow em vez de à mão, veja
[passo-a-passo/atualizar-dados.md](passo-a-passo/atualizar-dados.md).

---

## Uma DAG, várias rodadas

| DAG | Quando | O quê |
|---|---|---|
| `pipeline_manzo` | 8h, 12h e 20h | todas as origens |

Não há sensor de "arquivo novo": a própria bronze lê só o que ainda não
leu e termina em segundos com `0 a ler` quando não há novidade.

> **DAG nova nasce pausada.** O Airflow cria toda DAG com `is_paused`
> ligado; sem `airflow dags unpause <dag_id>` (ou o botão na interface)
> ela aparece na lista e nunca roda.

## As tarefas do pipeline

São **31 tarefas** em onze ramos, ligados apenas por
`inicio` e `fim`:

| Ramo | Tarefas, em ordem |
|---|---|
| Investimentos | `bronze_xp` → `silver_xp` → `gold_investimento` → `exporta_consolidado` |
| Conta Itaú | `bronze_itau` → `silver_itau` |
| Cartões | `bronze_cartao_xp`, `bronze_cartao_nubank` → `silver_cartao` |
| Histórico 2014-2018 | `bronze_financ` → `silver_financ` |
| Fato unificado | `gold_movimentacao` (espera silver_itau, silver_cartao e silver_financ) |
| Conta família | `bronze_familia` → `silver_familia` → `gold_familia` |
| Meu dia | `bronze_dia` → `silver_dia` → `gold_dia` |
| Avaliação física | `bronze_avaliacao` → `silver_avaliacao` |
| Exames InBody | `bronze_inbody` → `silver_inbody` |
| Composição corporal | `gold_avaliacao` (espera silver_avaliacao e silver_inbody) |
| Manutenção do carro | `bronze_auto` → `silver_auto` |
| Plano de revisão | `bronze_revisao` → `silver_revisao` |
| Previsão do carro | `gold_auto` (espera silver_auto e silver_revisao) |

---

## Criando ou atualizando as estruturas

Os scripts SQL são numerados e idempotentes — rodar de novo não destrói
dado.

```powershell
cd scripts\sql
.\executa.ps1                                      # todos, em ordem
.\executa.ps1 -Arquivo 04_gold_investimentos.sql   # só um
```

> Use sempre `executa.ps1`, nunca o `sqlcmd` direto. Ele força a
> codepage UTF-8; sem isso o `sqlcmd` lê o arquivo em ANSI e grava
> `MarÃ§o` no lugar de `Março`. O estrago só aparece depois, no
> relatório.

Numeração atual:

| Faixa | Assunto |
|---|---|
| `00`–`01` | Utilitários e criação das camadas |
| `02`–`05` | Investimentos XP e glossário |
| `06`–`08` | Conta Itaú e de-para de categorias |
| `09`, `11`–`13` | Cartões e nível analítico/sintético |
| `10` | Classe de ativo — é de investimentos, ficou no meio da faixa dos cartões por ordem cronológica |
| `14` | Fato unificado de movimentação |
| `15`–`17` | Conta família |
| `18`–`20` | Meu dia |
| `21`–`23` | Avaliação física |
| `24`–`26` | Manutenção do automóvel |
| `27`, `29`–`30` | Chave por `ID` e renomeações da gold |
| `28` | Tags da coluna OBS |
| `31`–`32` | Histórico financeiro 2014-2018 |
| `33`–`36` | `dim_categoria_investimento` e a divisão em três dimensões financeiras |
| `37` | `fato_carga` e o relatório de cargas |
| `38`–`39` | Plano de revisão do fabricante e a previsão por veículo |
| `40`–`41` | Leitura dos exames InBody e o segmento corporal |
| `42`–`43` | Indicadores `FL_` em S/N, e a redocumentação que a troca de tipo apagou |
| `44` | Compressibilidade da despesa |
| `45` | `dim_localizacao` — cidade, UF e país saem dos fatos |
| `46` | `SK_TAG` nos fatos e a ponte de tags |
| `47` | Atributos novos do calendário: mês/ano, feriado, dia abreviado |
| `48`–`49` | Posição da carteira: bronze da Pluggy e o fato de posição |
| `50`–`51` | Origem do dado em `dim_ativo` e o vencimento do consentimento |

A numeração é **cronológica, não temática**: reflete a ordem em que as
coisas foram construídas, e é o que garante que rodar tudo em sequência
funcione num banco vazio. Não reorganize.

---

## Reconstruindo o container do Airflow

Dois arquivos pedem reconstrução quando mudam, e **cada um pede um
comando diferente**:

| Mudou | O que basta | Por quê |
|---|---|---|
| `dags/*.py`, `scripts/**` | nada | são volumes; o scheduler relê sozinho |
| `airflow/Dockerfile` | `docker compose build --builder manzo` | a imagem precisa ser refeita — e só o builder `manzo` atravessa o PMTU, ver abaixo |
| `airflow/docker-compose.yml` | `docker compose up -d` | o container precisa ser recriado |
| `airflow/.env` | `docker compose up -d` | as variáveis entram na criação |

Na dúvida, rode os dois — `build` seguido de `up -d` é sempre seguro:

```powershell
cd airflow
docker compose build --builder manzo
docker compose up -d
```

> **`--builder manzo` não é opcional.** O builder padrão roda os `RUN` do
> build na bridge do daemon, a MTU 1500, e o `pip` trava baixando
> qualquer wheel grande — ver *Quando o `pip` do build trava: PMTU*
> abaixo, que diz também como recriar o builder se ele sumir.

> **`build` sozinho não aplica mudança de `docker-compose.yml`.** Ele
> refaz a imagem e para por aí; o container em execução continua com a
> montagem antiga. Foi o que quase aconteceu ao incluir a pasta dos
> exames: a imagem já tinha a dependência nova e a carga ainda falharia, por
> não enxergar `/opt/exames`.

Leva de dois a quatro minutos. As camadas de `apt` ficam em cache; o
que roda de novo é o `pip install` do venv de ETL. O scheduler fica
fora do ar nesse intervalo, e isso não acumula atraso: com
`catchup=False`, uma rodada perdida simplesmente não acontece e a
próxima pega tudo, porque toda carga lê o que ainda não leu.

### Conferindo que pegou

```powershell
# a dependência nova entrou na imagem?
docker compose exec airflow-scheduler /opt/etl-venv/bin/python -c "import pymupdf; print(pymupdf.__version__)"

# a pasta nova chegou ao container?
docker compose exec airflow-scheduler ls /opt/exames

# e a carga roda lá dentro?
docker compose exec airflow-scheduler /opt/etl-venv/bin/python /opt/projeto/scripts/etl/carga_bronze_inbody.py
```

A última é a que vale: se ela imprimir **"0 a ler"**, o container
enxerga a pasta e a carga converge. Qualquer uma das três falhando
indica que o `up -d` não chegou a recriar o container.

> **Rode isso no PowerShell, não no Git Bash.** O Git Bash reescreve
> caminho que começa com barra antes de entregá-lo ao `docker`:
> `/opt/etl-venv/bin/python` vira
> `C:/Program Files/Git/opt/etl-venv/bin/python`, e o erro que volta é
> `no such file or directory` — que parece container quebrado e é só
> tradução de caminho. Se precisar do Git Bash, prefixe com
> `MSYS_NO_PATHCONV=1`.

### Antes de reconstruir, confira o `docker-compose.yml`

```powershell
docker compose config
```

Ele resolve as variáveis do `.env` e imprime o arquivo final. Uma
variável faltando aparece aqui como caminho vazio — e um `source`
vazio no bind faz o `up -d` falhar **depois** de o `build` já ter
levado os minutos dele.

### Quando o `pip` do build trava: PMTU

O sintoma engana porque **tudo o que é pequeno funciona**. DNS resolve
na hora, TCP conecta, um `HEAD` ao Google responde em meio segundo — e
qualquer transferência grande para no meio sem erro nenhum, até o
`pip` desistir com `Read timed out`. Foi assim que o `docker compose
build` morreu baixando 1,8 MB do PyPI, enquanto o host baixava o mesmo
arquivo em 3 s.

A causa é um **PMTU blackhole** no caminho de saída do WSL2: pacote de
tamanho cheio é descartado em silêncio e o ICMP que avisaria "reduza"
nunca chega ao container. O Windows não sofre porque negocia PMTU por
conta própria; o container, atrás do NAT, não recebe a notícia.

Medido em container descartável, mesma imagem, só o MTU mudando:

| MTU | 1,8 MB do PyPI |
|---|---|
| 1500 (padrão) | trava além de 70 s |
| 1400 | 14 a 20 s |
| **1350** | **2,2 s** |
| 1300 | 2,2 s — sem ganho |

1350 é o maior valor comprovadamente rápido. São **dois consertos**,
porque container e build andam por redes diferentes:

**Containers** — `networks.default.driver_opts` no `docker-compose.yml`
fixa `com.docker.network.driver.mtu: "1350"`. Mudar isso exige
`docker compose down` antes do `up -d`: rede que já existe **não é
recriada**, e o `up` sozinho deixa a antiga, a 1500, no lugar.

**Build** — o builder padrão (driver `docker`) roda os `RUN` na bridge
do daemon, a 1500, e `build.network: manzo-airflow_default` **não
resolve**: o BuildKit recusa rede nomeada nesse driver. O que resolve é
um builder `docker-container` preso à rede de 1350 — o BuildKit vira um
container nessa rede e herda o MTU:

```powershell
docker buildx create --name manzo --driver docker-container `
    --driver-opt network=manzo-airflow_default --bootstrap
docker compose build --builder manzo
```

Para conferir que o builder está na rede certa:

```powershell
docker exec buildx_buildkit_manzo0 cat /sys/class/net/eth0/mtu    # 1350
```

> **O conserto permanente é no engine, não no projeto.** O builder
> resolve o build, mas um `docker compose pull` de imagem nova — um
> Postgres atualizado, por exemplo — ainda passa pela bridge a 1500 e
> trava do mesmo jeito. Para fechar isso de vez, `"mtu": 1350` em
> `%USERPROFILE%\.docker\daemon.json` (Docker Desktop › Settings ›
> Docker Engine), seguido de reinício do Docker Desktop. Isso reinicia
> o engine inteiro, por isso não foi feito pela carga: é decisão de quem
> opera a máquina.

Para medir de novo, se a rede mudar: um container da imagem do projeto,
como root e com `--cap-add NET_ADMIN`, baixando o MTU de `eth0` por
`ioctl` (`SIOCSIFMTU`, `0x8922`) e tentando um `pip download` com
`--timeout 20 --retries 0`. Não use `ping -M do` nem `ip link`: a
imagem não tem `ping`, e `ip` só funciona como root — os dois falham de
um jeito que parece PMTU e não é.

### Quando o projeto ganha uma pasta de origem

Uma pasta nova entra em **três lugares**, e esquecer qualquer um deles
produz um erro que aponta para outro lugar:

| Onde | O quê | Se faltar |
|---|---|---|
| `.env` da raiz | `PATH_X=C:\...` | a carga rodada à mão no host não acha a pasta |
| `airflow/.env` | `PATH_X_HOST=C:\...` + o bind em `volumes:` do compose | o container não tem a pasta montada |
| `environment:` do compose | `PATH_X: /opt/x` | **o container tem a pasta montada e mesmo assim tenta abrir o caminho do Windows** |

O terceiro é o que morde. O `config_db` faz `load_dotenv` do `.env` da
raiz, e o `python-dotenv` **não sobrescreve** variável que já existe no
ambiente: para as pastas listadas em `environment:` vence o caminho do
container; para uma que não esteja na lista, vaza o caminho do Windows.
Foi exatamente assim com uma pasta nova — montada em `/opt/x`,
visível com `ls`, e a carga reclamando de
um caminho `C:\...` do Windows.

A conferência, de dentro do container, antes de rodar carga nenhuma:

```powershell
docker compose exec airflow-scheduler sh -c 'echo $PATH_EXAMES'   # /opt/exames
```

### Quando o `Dockerfile` ganha uma dependência

Instale a mesma versão no venv do projeto, ou a carga rodada à mão
quebra no import enquanto a do container funciona:

```powershell
& ".venv\Scripts\python.exe" -m pip install "pymupdf==1.24.14"
```

Manter as duas versões iguais é o que sustenta a tabela de
interpretadores em *Pontos de atenção conhecidos* — e um `pip install`
feito só de um lado é justamente como elas se separam.

---

## Tarefas periódicas

### Classificar o que ficou pendente

Lançamentos sem categoria aparecem como *A classificar*. Para
resolvê-los em lote:

```powershell
& $py scripts\etl\exporta_revisao_itau.py   # gera a planilha de revisão
# preencher AREA, CATEGORIA e GRUPO na planilha
& $py scripts\etl\carga_de_para_itau.py     # carrega os rótulos
& $py scripts\etl\carga_silver_itau.py      # aplica aos lançamentos
```

O agrupamento é por **padrão de operação**, não por lançamento — a
descrição sem números nem datas. Rotular uma linha resolve dezenas de
lançamentos, e a lista vem ordenada por volume financeiro, então as
primeiras dezenas cobrem a maior parte do valor.

O de-para nunca sobrescreve o que já estava classificado na planilha:
só preenche o que está em branco. A coluna `ds_origem_classificacao`
registra a procedência de cada rótulo.

### Ajustar uma regra de negócio sem tocar em código

Três decisões vivem no banco, como dado, e mudam com um `UPDATE`
seguido de nova carga. Rodar o script SQL de novo **não** desfaz o
ajuste — a semeadura só insere o que falta.

```sql
-- Meu dia: a meta diária de água, em litros
UPDATE gold.dim_habito SET VL_META_MINIMA = 2.5 WHERE NM_HABITO = N'Água';

-- Meu dia: deixar de contar a ceia como meta
UPDATE gold.dim_habito SET FL_APURA_ADERENCIA = 0 WHERE NM_HABITO = N'Ceia';

-- Avaliação física: para que lado a métrica melhora
UPDATE gold.dim_metrica_corporal SET DS_SENTIDO_MELHOR = 'MENOR'
 WHERE NM_METRICA = N'Peso';
```

Depois rode a gold correspondente: ela reescreve a série inteira com a
regra nova, o que permite perguntar "com esta meta, como teria sido
2024".

### Regenerar o glossário

Depois de qualquer mudança de DDL:

```powershell
& $py scripts\etl\exporta_glossario.py
```

Ele reporta quantas colunas estão sem descrição. **O número tem que ser
zero** — é o contrato de documentação do projeto.

### Reprocessar tudo com regra nova

Mudou uma regra em `regras_xp.py`, `regras_itau.py` ou nas dimensões
acima? Basta rodar a silver e a gold: elas fazem *upsert* e
reclassificam toda a série histórica sem renumerar chaves.

---

## Conferindo se está tudo certo

### O relatório de cargas

```powershell
& $py scripts\etl\relatorio_carga.py                 # última execução de cada tabela
& $py scripts\etl\relatorio_carga.py --historico 7   # série dos últimos 7 dias
& $py scripts\etl\relatorio_carga.py --html --md     # gera as duas versões
```

As duas versões vão para o repositório. O `.md` existe porque o GitHub
não renderiza `.html` na navegação — abre o código-fonte; é ele que você
lê em [relatorio-carga.md](relatorio-carga.md). O `.html` é a página com
os destaques visuais, para abrir no navegador ou publicar.

É a leitura de rotina, e substitui rodar cada carga à mão para ver o
resumo. **30 tabelas** aparecem ali — 10 bronze, 9 silver e 11 gold —,
cada uma com quantas linhas entraram, quantas mudaram, o total depois da
carga, a duração e há quanto tempo rodou.

Cada carga grava a própria linha em `gold.fato_carga` ao terminar, via
`registra_carga()`. **Esse registro nunca derruba a carga**: se a
gravação falhar, sai um aviso no terminal e a carga que deu certo
continua tendo dado certo.

Três estados na coluna à direita:

| estado | significa |
|---|---|
| `ok` | convergiu — nada entrou nem mudou |
| `MOVIMENTO` | inseriu ou atualizou; esperado se entrou dado novo |
| `PARADA` | não roda há mais de 30h — provável ramo quebrado na DAG |

O `--historico` é o que denuncia defeito, porque olha a **proporção**:
uma tabela que se moveu uma vez em quatro apenas trouxe dado novo; a que
se move em *toda* execução não está acompanhando a origem, está com
defeito. É o padrão das 172 atualizações fantasma do arredondamento na
avaliação física e das 772 do histórico financeiro.

O `--exigir-convergencia` faz o script sair com código 1 quando algo não
convergiu. Só use na **segunda** execução seguida: na primeira, inserir
linha nova é o comportamento correto e não deve reprovar nada.

Duas dimensões ainda não aparecem no relatório: as de classificação de
`fato_movto_financ` e `fato_familia`. `sincroniza_classificacao()`
informa quantos membros entraram, mas não quantos mudaram — e registrar
zero ali afirmaria uma convergência que ninguém apurou.

### Os e-mails

**Caixa de entrada silenciosa significa pipeline saudável.** Não há mais
aviso de sucesso — só chega e-mail quando algo precisa de você.

| Quando | Assunto | Quem manda |
|---|---|---|
| Tarefa falhou | `Airflow alert: pipeline_manzo.<tarefa>` | Airflow, na hora |
| Ramo pulado por bronze vazia | `manzo-dados · ramo pulado · bronze_dia` | Airflow, na hora |
| Carga parada ou que nunca converge | `manzo-dados · PROBLEMA · 2 cargas precisam de atenção` | `relatorio_carga`, no fim da rodada |

O terceiro cobre o que os outros dois não veem: **uma carga pode
terminar com sucesso e ainda estar defeituosa.** Foram assim as 772
atualizações fantasma do histórico financeiro, as 172 do arredondamento
na avaliação física e a oscilação do XP entre duas versões do pandas —
as três cargas terminavam verdes. Ele dispara em dois casos:

- **Carga parada** — tabela sem ser tocada há mais de 30h, num pipeline
  que roda 3× por dia. Ramo quebrado ou origem que sumiu.
- **Carga que nunca converge** — moveu linha em *todas* as execuções da
  semana, com no mínimo três. O contrato do projeto diz que rodar de novo
  sem mexer na origem dá zero; quem move sempre não está acompanhando
  mudança, está com defeito.

**Não dispara** quando uma carga simplesmente não convergiu numa rodada:
entrou dado novo e a tabela cresceu, o que é o pipeline trabalhando.
Avisar disso todo dia transformaria o alerta em ruído.

#### O vigia, fora do Airflow

Se o **Airflow parar**, ele não manda e-mail nenhum — e silêncio passaria
a significar as duas coisas opostas. A checagem de carga parada mora
dentro da própria DAG, então não roda justamente quando mais precisaria.

Por isso existe uma tarefa no **Agendador de Tarefas do Windows**:

| | |
|---|---|
| Nome | `manzo-dados vigia` |
| Roda | todo dia às **09:00** |
| Como | usuário **SISTEMA** — não exige ninguém logado |
| O quê | `scripts\vigia-cargas.cmd` |
| Log | `logs\vigia.log` (não versionado) |

Ele não depende de Docker nem de Airflow: só do SQL Server e do SMTP.
**E avisa até quando não consegue checar** — se o banco não responde,
manda e-mail em vez de deixar o erro num log que ninguém lê. Sem isso o
ponto cego apenas desceria um nível.

O assunto desse alerta **nomeia o servidor**:
`manzo-dados · VIGIA · sem resposta de localhost`. Isso não é enfeite —
se o nome ali não for o de sempre, alguém rodou o vigia apontando para
outro lugar e não há nada errado com as cargas. O corpo traz máquina,
servidor, banco e horário pelo mesmo motivo.

O wrapper usa o **venv**, e não o `python` do PATH: o SISTEMA não enxerga
o `site-packages` de `%APPDATA%`, então o `dateutil` some e o pandas nem
carrega. Para usar outro interpretador, defina `PY_MANZO`.

```powershell
schtasks /run    /tn "manzo-dados vigia"     # rodar agora
schtasks /query  /tn "manzo-dados vigia" /v  # ver último resultado
schtasks /delete /tn "manzo-dados vigia" /f  # remover
```

#### Rodando à mão

```powershell
& $py scripts\etl\relatorio_carga.py --email-se-problema   # como a DAG faz
& $py scripts\etl\relatorio_carga.py --email               # manda de qualquer jeito
```

O segundo serve para conferir que o envio está de pé sem esperar dar
problema.

#### Configurando

Tudo vem de `SMTP_*` no `.env` — um único conjunto de valores, lido pelo
Airflow (via `AIRFLOW__SMTP__*`) e pelo script. O `.env` não é
versionado; `.env.example` traz o modelo.

> **A senha não é a da conta.** Com verificação em duas etapas ligada, o
> Google recusa a senha normal por SMTP. Gere uma **senha de aplicativo**
> em <https://myaccount.google.com/apppasswords>. Pode colar no formato
> que o Google mostra, com espaços — eles são removidos na leitura.

Sem a senha preenchida, o script diz exatamente qual chave falta e sai
com código 1, em vez de enviar pela metade ou fingir que enviou.

### Os exames de bioimpedância são lidos uma vez só

`carga_bronze_inbody.py` **pula os arquivos que já leu**. A imagem de
um exame nunca muda, então reler não traz informação nova — só gasta
uns 15 segundos por exame, cinco minutos por rodada da DAG.

E evita um defeito real: o Tesseract do host está na **5.4** e o do
container na **5.3**, e as duas versões leem alguns campos de forma
diferente. Relendo a cada rodada, uma execução desfazia a outra e as
três tabelas do InBody nunca convergiam.

Depois de melhorar o extrator, para reler tudo:

```powershell
& $py scripts\etl\carga_bronze_inbody.py --reprocessar
```

> As versões continuam divergentes. Enquanto estiverem, **rode o
> `--reprocessar` sempre no mesmo lugar** — de preferência pelo
> Airflow, que é quem roda sozinho. Alinhar as duas é o conserto de
> raiz e continua em aberto.

### Quando a bronze vem vazia, o ramo para

Se uma carga bronze termina com a tabela **sem nenhuma linha**, ela sai
com código **99**. O Airflow trata isso como *pulada*, não como falha, e
as camadas seguintes daquele ramo são puladas junto.

```
bronze_dia  (PULADA, saída 99)
   └─ silver_dia  (pulada)
        └─ gold_dia  (pulada)
```

O motivo é prático: transformar zero linha não produz nada e costuma
quebrar no primeiro `groupby`, com uma mensagem que fala de pandas em
vez de falar da origem que sumiu. Pulando, o log diz a verdade e o
histórico da carga fica registrado em `gold.fato_carga` do mesmo jeito.

> **Isto não é o mesmo que `+0 novos, 0 atualizados`.** Aquilo é o
> contrato de convergência do projeto e é sinal de **saúde** — quer
> dizer que a origem não mudou. O teste aqui é outro: a tabela não tem
> linha nenhuma. Na prática só acontece em origem nova, planilha salva
> vazia ou tabela truncada.

**Uma origem vazia não derruba as outras.** As três tarefas que recebem
mais de um ramo — `silver_cartao`, `gold_movimentacao` e `gold_auto` —
usam `none_failed_min_one_success`: basta um pai ter carregado para elas
rodarem. Se o Nubank vier vazio, o cartão XP continua chegando na
silver.

Saída **1 continua sendo falha** e falha de verdade: arquivo não
encontrado, coluna faltando, `ID` repetido. Só o 99 vira skip.

### Os sinais na saída de cada carga

Toda carga imprime um resumo. Os sinais de saúde:

- A **segunda execução converge em zero** — `+0 novos, 0 atualizados`.
  Se uma carga sempre reporta atualizações sem você ter mexido em nada,
  há uma diferença fantasma na comparação, não uma mudança real. Já
  aconteceu duas vezes: uma por `numpy.bool_` não ser `bool`, outra por
  arredondamento de ponto flutuante contra `decimal(10,2)`.
- **Gold e silver conciliam.** As cargas de gold imprimem as duas somas
  lado a lado; devem bater exatamente, descontado o que a gold exclui de
  propósito.
- **Nenhum fato apontando para o membro `-1`.** Qualquer valor acima de
  zero significa dimensão faltando.

Duas ressalvas, para o doc não prometer mais do que existe:

- A contagem de membro `-1` só é impressa por `carga_gold_avaliacao.py`
  e `carga_gold_auto.py`. Nas outras quatro, conferir exige consulta
  manual ao fato.
- Só `carga_gold_xp.py` remove membros de dimensão que nenhum fato
  referencia. As demais dimensões acumulam — inofensivo, mas um rótulo
  abandonado continua aparecendo como opção de filtro no Power BI.

---

## Pontos de atenção conhecidos

**Use sempre o `$py` do venv, nunca o `python` solto do PATH.** Os dois
existem nesta máquina e não têm as mesmas versões:

| Interpretador | pandas |
|---|---|
| `.venv\Scripts\python.exe` — o `$py` documentado | **3.0.2** |
| `/opt/etl-venv/bin/python` — dentro do container | **3.0.2** |
| `python` solto no PATH | 2.3.2 |

O venv e o container estão alinhados, como o `Dockerfile` promete. O
`python` do PATH é que ficou para trás, e a diferença não é cosmética:
uma coluna ausente chega como `None` no pandas 2 e como `NaN` no
pandas 3, e **`NaN` é verdadeiro em Python**. Foi assim que
`silver.xp_movimentacao` passou a oscilar — a carga rodada pelo `python`
solto classificava 54 lançamentos de um jeito e a DAG desfazia na rodada
seguinte, indefinidamente.

O código foi corrigido para funcionar nas duas versões (`pd.notna()` em
vez de `bool()`), mas a regra continua valendo: **rodar carga com o
`python` do PATH é misturar dois ambientes.**

**Ao somar despesa, filtre `DS_NIVEL = 'ANALITICO'`.** Somar os dois
níveis conta o gasto do cartão duas vezes — uma na compra, outra no
pagamento da fatura.

**Transferências entre contas próprias inflam os dois lados.** São
movimentação real, mas não são gasto. A medida de despesa do dashboard
provavelmente deve excluir a área `TRANSFERENCIA`.

**Não some fatos diferentes.** `fato_familia` é dinheiro de duas
pessoas; `fato_manutencao_auto` cruza com a fatura do cartão. Cada um
responde uma pergunta própria — o único eixo que todos compartilham é
`dim_calendario`.

**`vl_saldo` não é aditivo.** É o saldo de caixa no momento do
lançamento, não patrimônio investido.

**`fato_dia` e `fato_dia_habito` são a mesma informação em dois
formatos.** Nunca some as duas juntas.

**Na avaliação física, filtre `FL_SERIE_CONTINUA = 1`** para o gráfico
de longo prazo. Só cinco métricas cobrem os 18 anos; as demais produzem
linhas que começam ou terminam no meio. E `Massa Muscular` não é
`Massa Muscular/Ossea` — unidas, exibem uma queda de 25 kg que nunca
aconteceu.

**Na manutenção do carro, a quilometragem não é comparável entre
veículos.** Cada um tem seu hodômetro, e o carro mais novo tem número
menor. `gold.vw_manutencao_prevista` considera só o veículo ativo por
isso.

**`Sem registro` não é `Vencido`.** O SUV entrou na base em 10/11/2025
já com 94.200 km. Um item do plano sem registro pode ter sido feito
antes de o carro ser seu — a view mostra `DT_ENTRADA_BASE` ao lado
justamente para você separar as duas coisas. Ainda assim é o campo mais
útil da previsão: o fluido do câmbio CVT vence a 80.000 km, o carro está
com 100.380 e não há registro nenhum dele.

**O km só avança quando o carro vai à oficina, e por isso o critério de
tempo costuma ser o que dispara.** `NR_KM_ATUAL` é a maior quilometragem
já registrada, então logo depois de uma revisão a folga em km volta a
ser o intervalo inteiro. O intervalo em meses, vindo do plano do
fabricante, não depende disso — é ele que faz a previsão andar sozinha.
`DS_CRITERIO` diz qual dos dois está mandando em cada linha.

**A aba do extrato do Itaú muda de nome a cada download** — traz a data
no título. A carga usa apenas `cad-conta` e localiza o resto por padrão,
nunca por nome fixo.

**Os arquivos de avaliação física e manutenção são `.xls` de verdade**
(Excel 97-2003), não `.xlsx` renomeados. Exigem `xlrd`; `openpyxl` não
lê esse formato. Se você salvar um deles como `.xlsx`, ajuste o nome no
script da carga.
