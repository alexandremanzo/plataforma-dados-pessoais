"""
Pipeline de dados pessoais - orquestracao diaria.

Executa as cargas na ordem de dependencia entre camadas, com as
origens correndo em paralelo ate o ponto em que precisam se encontrar.

    bronze_xp ──> silver_xp ──> gold_investimento ──> exporta_consolidado

    bronze_itau ──> silver_itau ──┐
                                  ├──> gold_movimentacao
    bronze_cartao_xp ─────┐       │
                          ├──> silver_cartao
    bronze_cartao_nubank ─┘       │
    bronze_financ ──> silver_financ ┘

    bronze_familia ──> silver_familia ──> gold_familia

    bronze_dia ──> silver_dia ──> gold_dia

    bronze_avaliacao ──> silver_avaliacao ──> gold_avaliacao

    bronze_auto ──> silver_auto ──> gold_auto

Familia e meu dia leem do Google Sheets em vez de arquivo, e por isso
sao os unicos que dependem de rede. Ficam isolados: uma planilha fora
do ar nao pode impedir as cargas financeiras de rodar.

Os scripts sao os MESMOS que rodam a mao no host - nada foi
reescrito para o Airflow. Isso e possivel porque config_db le a
configuracao do ambiente antes do arquivo .env, e o docker-compose
injeta o endereco do SQL Server e os caminhos do container.

BRONZE VAZIA PARA O RAMO. Se uma carga bronze termina com a tabela sem
nenhuma linha, ela sai com codigo 99 e o Airflow marca a tarefa como
PULADA, nao como falha - e as camadas seguintes daquele ramo sao puladas
junto. Transformar zero linha nao produz nada e costuma quebrar no
primeiro groupby, com um erro que fala de pandas em vez de falar da
origem que sumiu.

Isso NAO tem relacao com "+0 novos, 0 atualizados", que e o contrato de
convergencia e e sinal de saude. O teste e outro: a tabela nao tem
linha nenhuma.

As tarefas que recebem mais de um ramo - silver_cartao, gold_movimentacao
e gold_auto - usam none_failed_min_one_success justamente para que uma
origem vazia nao leve junto as outras que carregaram normalmente. Se o
Nubank vier vazio, o cartao XP continua chegando na silver.

Todas as cargas sao idempotentes: rodar de novo nao duplica nada e
converge em zero insercoes. Por isso o retry e seguro e o catchup
esta desligado - nao existe "processar o dia 12 de novo", existe
apenas "reprocessar o que estiver nos arquivos agora".

Frequencia: tres vezes ao dia, as 8h, 12h e 20h de Brasilia. O dado
nao chega todo dia - o extrato da XP e a fatura do cartao sao baixados
manualmente algumas vezes por mes - mas rodar varias vezes significa
que um arquivo colocado na pasta pela manha entra ainda no mesmo dia,
sem esperar a madrugada seguinte.

O horario e declarado em America/Sao_Paulo, e nao em UTC. O Airflow
interpreta o cron no fuso da start_date, e o padrao dele e UTC: com a
start_date sem fuso, "0 8 * * *" rodaria as 5h da manha no Brasil.
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

FUSO = pendulum.timezone("America/Sao_Paulo")

ETL = "/opt/projeto/scripts/etl"

# O ETL roda num interpretador separado, nao no Python do Airflow.
# Motivo: o pandas exige SQLAlchemy 2.0 e o Airflow 2.10 fixa uma
# versao anterior. Juntos, o pandas deixa de reconhecer a conexao e
# quebra. O venv proprio tem as mesmas versoes do host, entao o mesmo
# script roda identico nos dois lugares.
PYTHON_ETL = "/opt/etl-venv/bin/python"

# Para quem vao os avisos. Vem do ambiente porque o endereco muda de
# maquina e nao pertence ao codigo; o docker-compose repassa do .env.
DESTINATARIOS = [e.strip() for e in os.getenv("SMTP_PARA", "").split(",")
                 if e.strip()]


def avisa_ramo_pulado(context) -> None:
    """
    Manda e-mail quando uma bronze vem vazia e leva o ramo junto.

    Airflow so tem email_on_failure, e pular NAO E FALHAR - sem este
    aviso, um ramo inteiro deixaria de rodar em silencio, e o resumo da
    rodada mostraria a tabela com o numero da vespera sem explicar por
    que. So a tarefa que ORIGINOU o skip cai aqui; as seguintes sao
    puladas pelo scheduler e nao repetem o aviso.
    """
    if not DESTINATARIOS:
        return
    from airflow.utils.email import send_email

    ti = context["task_instance"]
    send_email(
        to=DESTINATARIOS,
        subject=f"manzo-dados · ramo pulado · {ti.task_id}",
        html_content=(
            f"<p><b>{ti.task_id}</b> terminou sem nenhuma linha na tabela "
            f"bronze e as camadas seguintes deste ramo foram puladas.</p>"
            f"<p>Isto nao e falha da carga: nao havia o que transformar. "
            f"Confira a origem antes da proxima rodada.</p>"
            f"<p>Rodada: {context['run_id']}</p>"),
    )


ARGS_PADRAO = {
    "owner": "manzo",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # E-MAIL SO QUANDO DA ERRADO. Aviso imediato e por tarefa. Nao ha
    # mais aviso de sucesso: 28 tarefas tres vezes ao dia dariam 84
    # e-mails diarios, e mesmo um resumo por rodada vira ruido depois de
    # alguns dias iguais. Caixa de entrada silenciosa passa a significar
    # pipeline saudavel - com a ressalva de que Airflow parado tambem
    # fica silencioso, e por isso o relatorio checa carga parada.
    "email": DESTINATARIOS,
    "email_on_failure": bool(DESTINATARIOS),
    "email_on_retry": False,
    "on_skipped_callback": avisa_ramo_pulado,
    # Uma origem que falha nao deve impedir as outras de carregar:
    # cada ramo do pipeline e independente ate a gold.
    "depends_on_past": False,
}


def carga(dag: DAG, task_id: str, script: str, argumentos: str = "",
          espera: str = TriggerRule.ALL_SUCCESS) -> BashOperator:
    """
    Executa um script de carga do projeto.

    skip_on_exit_code=99 e o que liga a inteligencia do pipeline. Uma
    carga bronze que termina com a tabela VAZIA sai com 99; o Airflow
    marca a tarefa como PULADA em vez de falha, e a regra all_success
    para o ramo inteiro ali. Nao adianta transformar o que nao existe -
    e uma origem que sumiu nao e defeito da silver.

    99 ja e o padrao do operador. Esta explicito porque virou decisao de
    projeto, e um padrao que muda de versao levaria a inteligencia junto
    sem ninguem perceber.
    """
    return BashOperator(
        task_id=task_id,
        bash_command=f"{PYTHON_ETL} {ETL}/{script} {argumentos}".strip(),
        skip_on_exit_code=99,
        trigger_rule=espera,
        dag=dag,
    )


with DAG(
    dag_id="pipeline_manzo",
    description="Cargas bronze, silver e gold das financas pessoais",
    default_args=ARGS_PADRAO,
    start_date=pendulum.datetime(2026, 1, 1, tz=FUSO),
    schedule="0 8,12,20 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["manzo", "financeiro"],
    doc_md=__doc__,
) as dag:

    inicio = EmptyOperator(task_id="inicio")
    fim = EmptyOperator(
        task_id="fim", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # --- Investimentos XP -------------------------------------
    bronze_xp = carga(dag, "bronze_xp", "carga_bronze_xp.py")
    silver_xp = carga(dag, "silver_xp", "carga_silver_xp.py")
    gold_investimento = carga(dag, "gold_investimento", "carga_gold_xp.py")
    # Enquanto o Power BI le o arquivo intermediario, ele precisa ser
    # regerado a cada carga. Some quando o relatorio apontar para o SQL.
    exporta = carga(dag, "exporta_consolidado", "exporta_consolidado_xp.py")

    # A POSICAO VEM DA API, nao da planilha - por isso nao pende de
    # bronze_xp. Ela sai de 99 quando a Pluggy esta sincronizando, e o
    # ramo inteiro e pulado: a conexao atualiza uma vez por dia e a DAG
    # roda tres, entao cair no meio de uma atualizacao e rotina.
    bronze_posicao = carga(dag, "bronze_posicao", "carga_bronze_xp_posicao.py")
    gold_posicao = carga(dag, "gold_posicao", "carga_gold_posicao.py")

    # --- Conta corrente Itau ----------------------------------
    bronze_itau = carga(dag, "bronze_itau", "carga_bronze_itau.py")
    silver_itau = carga(dag, "silver_itau", "carga_silver_itau.py")

    # --- Cartoes de credito -----------------------------------
    bronze_cartao_xp = carga(dag, "bronze_cartao_xp", "carga_bronze_cartao_xp.py")
    bronze_cartao_nubank = carga(
        dag, "bronze_cartao_nubank", "carga_bronze_cartao_nubank.py")
    silver_cartao = carga(
        dag, "silver_cartao", "carga_silver_cartao.py",
        espera=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # --- Historico financeiro 2014-2018 -----------------------
    # Periodo anterior as origens atuais, em instrumentos que nao
    # existem mais: dinheiro, vale-alimentacao, Visa BB, Visa/CTI e
    # Diners. Alimenta o mesmo fato, entao gold_movimentacao espera
    # por ele tambem.
    bronze_financ = carga(dag, "bronze_financ", "carga_bronze_financ.py")
    silver_financ = carga(dag, "silver_financ", "carga_silver_financ.py")

    # --- Fato unificado de movimentacao -----------------------
    gold_movimentacao = carga(
        dag, "gold_movimentacao", "carga_gold_movimentacao.py",
        espera=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # --- Conta familia ----------------------------------------
    # As duas origens abaixo nao leem arquivo: buscam uma aba do Google
    # Sheets publicada como CSV. Sao as unicas que dependem de rede, e
    # as unicas que podem falhar por indisponibilidade externa - ficam
    # em ramos proprios, sem travar as demais.
    bronze_familia = carga(dag, "bronze_familia", "carga_bronze_familia.py")
    silver_familia = carga(dag, "silver_familia", "carga_silver_familia.py")
    gold_familia = carga(dag, "gold_familia", "carga_gold_familia.py")

    # --- Meu dia ----------------------------------------------
    # Diario de habitos. Nao tem relacao com as bases financeiras - o
    # unico eixo que compartilham e o calendario - entao roda isolado.
    bronze_dia = carga(dag, "bronze_dia", "carga_bronze_dia.py")
    silver_dia = carga(dag, "silver_dia", "carga_silver_dia.py")
    gold_dia = carga(dag, "gold_dia", "carga_gold_dia.py")

    # --- Avaliacao fisica -------------------------------------
    # Le .xls de outra pasta do Dropbox, montada em /opt/planilhas.
    # A serie mais longa do projeto: 2008 a 2026. Muda poucas vezes
    # por ano, mas roda junto porque nao custa nada.
    bronze_avaliacao = carga(dag, "bronze_avaliacao", "carga_bronze_avaliacao.py")
    silver_avaliacao = carga(dag, "silver_avaliacao", "carga_silver_avaliacao.py")
    gold_avaliacao = carga(
        dag, "gold_avaliacao", "carga_gold_avaliacao.py",
        espera=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # --- Exames InBody, lidos por OCR -------------------------
    # A imagem do exame traz ~40 campos contra os 11 que cabem no
    # preenchimento manual. NAO SUBSTITUI A PLANILHA: as duas origens
    # se completam no fato, com o arquivo na frente e a planilha
    # cobrindo o que o OCR nao leu.
    bronze_inbody = carga(dag, "bronze_inbody", "carga_bronze_inbody.py")
    silver_inbody = carga(dag, "silver_inbody", "carga_silver_inbody.py")

    # --- Manutencao do automovel ------------------------------
    # Le a mesma pasta da avaliacao fisica, tambem em .xls antigo.
    # Muda poucas vezes por ano - so quando o carro vai a oficina.

    bronze_auto = carga(dag, "bronze_auto", "carga_bronze_auto.py")
    silver_auto = carga(dag, "silver_auto", "carga_silver_auto.py")
    gold_auto = carga(
        dag, "gold_auto", "carga_gold_auto.py",
        espera=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # --- Plano de revisao do fabricante -----------------------
    # NAO E EVENTO, E REGRA: o manual do SUV, com o intervalo em km e
    # em MESES de cada item. E o intervalo em meses que faz a previsao
    # funcionar - o hodometro so entra na base quando o carro vai a
    # oficina, mas o tempo corre sozinho.
    # Muda praticamente nunca (so se trocar de carro), e roda junto
    # porque custa dois segundos.
    bronze_revisao = carga(dag, "bronze_revisao", "carga_bronze_revisao.py")
    silver_revisao = carga(dag, "silver_revisao", "carga_silver_revisao.py")

    # --- Relatorio da rodada ----------------------------------
    # Regenera as duas versoes do relatorio e AVISA SO SE HOUVER
    # PROBLEMA: carga parada ou carga que nunca converge. Silencio
    # quando esta tudo bem - o resumo diario existiu por um dia e virou
    # ruido, que e como se para de ler alerta.
    #
    # ALL_DONE de proposito: precisa rodar mesmo quando algo falhou ou
    # foi pulado, que e justamente quando ha o que contar.
    relatorio = carga(
        dag, "relatorio_carga", "relatorio_carga.py",
        "--html --md --email-se-problema",
        espera=TriggerRule.ALL_DONE)

    inicio >> [bronze_xp, bronze_itau, bronze_cartao_xp, bronze_cartao_nubank,
               bronze_familia, bronze_dia, bronze_avaliacao, bronze_auto,
               bronze_financ, bronze_revisao, bronze_inbody, bronze_posicao]

    bronze_xp >> silver_xp >> gold_investimento >> exporta >> fim

    # gold_posicao ESPERA gold_investimento, e nao e por dado - e por
    # concorrencia. Os dois escrevem gold.dim_ativo: um cadastra ativo
    # novo da API, o outro remove membro que nenhum fato referencia. Em
    # paralelo, a limpeza pode rodar entre o INSERT do ativo e o INSERT
    # da posicao, quando o ativo ainda nao tem nada apontando para ele -
    # e apagar o que acabou de nascer. Em serie, isso nao tem janela.
    bronze_posicao >> gold_posicao
    gold_investimento >> gold_posicao >> fim
    bronze_itau >> silver_itau
    [bronze_cartao_xp, bronze_cartao_nubank] >> silver_cartao
    bronze_financ >> silver_financ
    [silver_itau, silver_cartao, silver_financ] >> gold_movimentacao >> fim
    bronze_familia >> silver_familia >> gold_familia >> fim
    bronze_dia >> silver_dia >> gold_dia >> fim
    bronze_avaliacao >> silver_avaliacao
    bronze_inbody >> silver_inbody
    # gold_avaliacao une planilha e arquivo; basta uma das duas ter
    # carregado para valer a pena rodar.
    [silver_avaliacao, silver_inbody] >> gold_avaliacao >> fim
    bronze_auto >> silver_auto
    # O RELATORIO CORRE AO LADO DE "fim", E NAO DEPOIS DELE.
    #
    # Encadeado depois, ele escondia falha: com ALL_DONE ele roda e
    # termina bem mesmo quando algo quebrou, e sendo a ULTIMA tarefa
    # era a unica folha da DAG - o Airflow olha as folhas para decidir
    # o estado da rodada, entao a rodada aparecia VERDE com uma tarefa
    # vermelha dentro. O gold_movimentacao ficou nove dias quebrado com
    # a DAG dizendo "success" em todas as rodadas.
    #
    # Ao lado, "fim" volta a ser folha: ele exige none_failed, herda o
    # upstream_failed e a rodada fica vermelha, como tem de ficar.
    [gold_investimento, exporta, gold_posicao, gold_movimentacao, gold_familia,
     gold_dia, gold_avaliacao, gold_auto] >> relatorio
    bronze_revisao >> silver_revisao
    # gold_auto deduz, para cada item do plano, em que categoria da
    # classificacao os lancamentos caem - entao precisa do historico E
    # da regra prontos.
    [silver_auto, silver_revisao] >> gold_auto >> fim
