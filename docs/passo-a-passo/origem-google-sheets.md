# Ler uma planilha do Google no pipeline

Duas origens do projeto vivem no Google e o pipeline as lê direto —
sem exportar `.xlsx` para o Dropbox como as demais:

| Origem | Variável no `.env` | Grão |
|---|---|---|
| Conta família | `PLANILHA_FAMILIA_URL` | um lançamento |
| Meu dia (respostas do Forms) | `PLANILHA_DIA_URL` | um dia |

Este roteiro serve tanto para reconfigurar essas origens quanto para
acrescentar uma planilha nova.

---

## Como funciona

A aba é **publicada como CSV** e o pipeline busca a URL. Sem
credencial, sem API, sem projeto no Google Cloud.

```
Google Sheets  ──publicado como CSV──>  google_sheets.py  ──>  bronze
```

### Por que não a API oficial

A alternativa é a Google Sheets API com conta de serviço, que é mais
restrita: dá acesso apenas a quem você compartilha explicitamente. Foi
a primeira tentativa aqui, e travou num detalhe operacional — a conta
tem vários projetos no Google Cloud, e habilitar a API no projeto certo
exigia navegar o console com precisão. O link publicado resolveu em
minutos.

**O custo é real:** quem tiver a URL vê os dados daquela aba, sem
login. Duas mitigações valem sempre:

- Publique **apenas a aba necessária**, nunca o documento inteiro. As
  abas de análise, metas e qualquer coisa futura continuam privadas.
- Trate a URL como segredo. Ela mora no `.env`, que não é versionado.

Se um dia o dado ficar sensível demais para isso, o caminho é a API —
e a seção de diagnóstico no fim tem o que aprendemos sobre ela.

---

## 1. Publicar a aba

Na planilha: **Arquivo → Compartilhar → Publicar na web**

1. No primeiro seletor, troque *Documento inteiro* pelo **nome da aba**
2. No segundo, troque *Página da web* por **`Valores separados por vírgula (.csv)`**
3. **Publicar** e confirmar

Copie a URL. Ela é diferente da URL de edição:

```
edição:     .../spreadsheets/d/1dDAIuCnJDBU.../edit
publicada:  .../spreadsheets/d/e/2PACX-1vXXXX.../pub?gid=0&single=true&output=csv
```

O `/d/e/2PACX-` é o identificador de publicação. Se sua URL não tem
isso, você copiou a de edição — o módulo detecta e avisa.

## 2. Configurar

No `.env` da raiz do projeto:

```
PLANILHA_FAMILIA_URL=https://docs.google.com/spreadsheets/d/e/2PACX-.../pub?gid=0&single=true&output=csv
```

Expor a variável em `scripts/conf/config_db.py`, ao lado das demais, e
registrar o nome (sem valor) no `.env.example`.

Nada a fazer no Airflow: o `docker-compose.yml` monta o projeto inteiro
em `/opt/projeto`, então o container lê o mesmo `.env` do host.

## 3. Ler

```python
from google_sheets import le_planilha_publicada
df = le_planilha_publicada(PLANILHA_FAMILIA_URL)
```

Devolve um DataFrame com **todas as colunas em texto**. A conversão de
tipo é trabalho da carga, e o módulo oferece dois auxiliares para o
formato que o Google entrega:

```python
from google_sheets import numero_brasileiro, data_brasileira

numero_brasileiro("1.234,56")    # 1234.56
numero_brasileiro("(329,62)")    # -329.62   parênteses = negativo contábil
data_brasileira("17/04/2021")    # "2021-04-17"
```

---

## Armadilhas que já custaram tempo

**O encoding.** O Google não declara o charset no cabeçalho HTTP, e o
`requests` então assume ISO-8859-1. Sem forçar UTF-8, `Descrição` vira
`DescriÃ§Ã£o` — e o estrago só aparece depois, no relatório. O módulo
já força.

**`float("nan")` é uma conversão válida.** Uma célula vazia que chega
como `NaN` passa por `str()`, vira `"nan"`, e `float("nan")` **não
levanta erro** — devolve um número. O resultado é uma linha vazia
entrando na base como se tivesse valor. O `numero_brasileiro` testa
`pd.isna` antes e `math.isfinite` depois.

**A planilha tem mais linhas que lançamentos.** Fórmulas arrastadas
geram uma cauda de linhas sem data e sem valor — na conta família são
725 de 2.074. A carga descarta e informa quantas.

**Publicação cancelada devolve HTML com status 200.** Não dá erro de
rede: o Google devolve uma página de login, e o pandas leria como uma
tabela de uma coluna sem reclamar. O módulo detecta e avisa que a
publicação não está ativa.

**A mesma opção do formulário pode existir em duas grafias.** Reescrever
uma alternativa do Google Forms não reescreve as respostas antigas: no
diário, o "Não" do cardio convive com e sem til desde 2024, porque a
opção foi editada no meio do caminho. Sem normalizar acento e caixa, o
mesmo hábito vira três respostas distintas no relatório.

---

## Escolhendo a chave de negócio

Numa planilha editada à mão, **qualquer campo que você possa corrigir é
um candidato ruim a chave**. Se a identidade do registro depende dele,
a correção não atualiza a linha: cria outra e abandona a errada.

O diário tem o caso extremo — duas respostas foram enviadas com a data
digitada errada (`31/12/1900` e `08/08/3025`). Como a chave é o
**carimbo de data/hora que o Forms atribui no envio** — único,
automático e imutável — corrigir a data na origem chega ao banco como
`UPDATE`.

Quando a origem não oferece um identificador assim, como na conta
família, a chave é composta (data + descrição + valor + ocorrência) e
essa fragilidade é o preço. Prefira sempre o identificador da origem
quando ele existir.

---

## Diagnóstico

| Sintoma | Causa provável |
|---|---|
| `URL é de edição, não de publicação` | Copiou o link do navegador em vez do gerado ao publicar |
| `devolveu uma página HTML em vez de CSV` | A publicação foi cancelada |
| `respondeu 404` | A aba publicada foi renomeada ou removida |
| `colunas esperadas não encontradas` | Colunas renomeadas na planilha — ajuste o dicionário `COLUNAS` da carga |

### Se um dia voltar para a API

Duas coisas precisam estar certas, e o erro de uma se parece com o da
outra:

1. **A API habilitada no projeto certo.** O console abre no último
   projeto usado, e é fácil ativar no errado. Para conferir sem
   depender do console, liste as APIs ativas usando a própria
   credencial:

   ```python
   import google.auth.transport.requests as gr
   from google.oauth2.service_account import Credentials

   cred = Credentials.from_service_account_file(
       CHAVE, scopes=["https://www.googleapis.com/auth/cloud-platform"])
   cred.refresh(gr.Request())
   s = gr.AuthorizedSession(cred)
   r = s.get(f"https://serviceusage.googleapis.com/v1/projects/"
             f"{cred.project_id}/services?filter=state:ENABLED&pageSize=200")
   print(sorted(x["config"]["name"] for x in r.json()["services"]))
   ```

2. **A planilha compartilhada** com o e-mail da conta de serviço, como
   Leitor.

O erro de API desabilitada (`SERVICE_DISABLED`) acontece **antes** do
de compartilhamento, então resolva na ordem: primeiro habilite,
depois compartilhe.
