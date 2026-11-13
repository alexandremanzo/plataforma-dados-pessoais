/* =============================================================
   manzo-dados | 15 - Camada Bronze: conta familia
   -------------------------------------------------------------
   bronze.familia_movimentacao

   Gastos em comum de Ale e Lia. Os dois fazem aportes
   mensais para as contas conjuntas, e esta base existe para dar
   transparencia de quem pagou o que.

   PRIMEIRA ORIGEM QUE NAO E ARQUIVO. As demais leem .xlsx do
   Dropbox; esta le uma aba do Google Sheets publicada como CSV,
   direto da URL. Nao ha etapa manual de exportar - o dado que
   entra e o mesmo que o Power BI ja consome hoje.

   TRES PARTICULARIDADES DESTA ORIGEM:

   1. TUDO CHEGA COMO TEXTO, no formato brasileiro. Numero vem como
      "1.234,56" e negativo vem em notacao contabil, entre
      parenteses: "(329,62)". Data vem como "17/04/2021". As outras
      origens vem do Excel, onde numero e data ja chegam tipados.

   2. O ARQUIVO TEM MAIS LINHAS QUE LANCAMENTOS. Sao 2.074 linhas
      no CSV para 1.349 lancamentos reais; o resto e cauda de
      formula arrastada, sem data nem valor. Descartadas na carga.

   3. O SINAL DIVERGE EM ALGUMAS LINHAS. A planilha calcula
      "Valor Trat" como o negativo de "Valor", o que funciona
      quando a despesa e digitada positiva. Em cinco lancamentos de
      reforma o valor foi digitado ja negativo, e a formula os
      transformou em receita. A bronze grava fiel a origem; a
      silver marca a divergencia para revisao.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.familia_movimentacao') IS NULL
BEGIN
    CREATE TABLE bronze.familia_movimentacao (
        id_movimentacao          int IDENTITY(1,1) NOT NULL,

        ds_data                  varchar(50)   NULL,
        ds_descricao             varchar(1000) NULL,
        ds_valor                 varchar(50)   NULL,
        ds_valor_tratado         varchar(50)   NULL,
        ds_tipo_movimentacao     varchar(50)   NULL,

        ds_area                  varchar(100)  NULL,
        ds_categoria             varchar(100)  NULL,
        ds_grupo                 varchar(100)  NULL,
        ds_pessoa_pagar          varchar(100)  NULL,
        ds_pessoa_receber        varchar(200)  NULL,
        ds_forma_pgto            varchar(50)   NULL,
        ds_descricao_pgto        varchar(200)  NULL,
        ds_data_pgto             varchar(50)   NULL,
        ds_status_pgto           varchar(20)   NULL,
        ds_descricao_status_pgto varchar(50)   NULL,

        ds_cidade                varchar(100)  NULL,
        ds_uf                    varchar(20)   NULL,
        ds_pais                  varchar(60)   NULL,
        ds_obs                   varchar(1000) NULL,
        ds_pgto_mes              varchar(20)   NULL,
        ds_pgto_ano              varchar(20)   NULL,

        nr_ocorrencia            int           NOT NULL,
        hash_negocio             char(64)      NOT NULL,
        nm_origem                varchar(120)  NOT NULL,
        nr_linha_arquivo         int           NULL,
        dt_carga                 datetime2(3)  NOT NULL
            CONSTRAINT DF_familia_mov_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_familia_movimentacao PRIMARY KEY CLUSTERED (id_movimentacao),
        CONSTRAINT UQ_familia_movimentacao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_familia_mov_data      ON bronze.familia_movimentacao (ds_data);
    CREATE INDEX IX_familia_mov_categoria ON bronze.familia_movimentacao (ds_categoria);
    CREATE INDEX IX_familia_mov_pessoa    ON bronze.familia_movimentacao (ds_pessoa_pagar);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Gastos em comum de Ale e Lia, lidos direto de uma aba do '
       + N'Google Sheets publicada como CSV. E a primeira origem do projeto que nao e '
       + N'arquivo: nao existe etapa manual de exportar, e o dado carregado e o mesmo que '
       + N'o Power BI ja consome. Os dois fazem aportes mensais para as contas conjuntas, '
       + N'e a base existe para dar transparencia de quem pagou o que. '
       + N'NAO se confunde com as transferencias pessoais para a conta familia, que ficam '
       + N'em silver.itau_movimentacao: sao assuntos independentes, e por isso a familia '
       + N'tem fato proprio em vez de entrar em gold.fato_movto_financ.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'id_movimentacao', @d;

SET @d = N'Data do lancamento, em formato ISO como texto. A origem entrega no formato '
       + N'brasileiro (17/04/2021) e a carga converte, porque o CSV nao carrega tipo.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_data', @d;

SET @d = N'Descricao do gasto, escrita a mao ("Combustivel", "Pedagios BSB > BH"). Como '
       + N'no cartao, e texto seu e nao codigo de banco - por isso esta origem ja vem bem '
       + N'classificada.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_descricao', @d;

SET @d = N'Valor como digitado na planilha, ja convertido do formato brasileiro. '
       + N'A convencao esperada e despesa positiva, mas em alguns lancamentos ela foi '
       + N'digitada negativa - ver ds_valor_tratado.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_valor', @d;

SET @d = N'METRICA DA ORIGEM. Calculado na planilha como o negativo de ds_valor, o que da '
       + N'despesa negativa e receita positiva. ATENCAO: quando o valor foi digitado ja '
       + N'negativo, a formula inverte para positivo e a despesa vira receita. Sao poucos '
       + N'casos, todos de reforma da casa, e a silver os marca em fl_sinal_divergente.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_valor_tratado', @d;

SET @d = N'DESPESA ou RECEITA, conforme digitado. Aparece com variacoes de caixa '
       + N'("Despesa", "DEspesa", "DeSPESA") que a silver unifica.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'CLASSIFICACAO nivel 1: GASTOS ESSENCIAIS, ESTILO DE VIDA ou RECEITA. '
       + N'Mesmo vocabulario das demais origens do projeto.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2, o principal para analise. Tem 18 valores, alguns '
       + N'exclusivos da familia: MORADIA, DIARISTA, INTERNET, ORGANIZACAO, HOSPEDAGEM e '
       + N'CUIDADOS PESSOAIS nao aparecem nas origens pessoais.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO nivel 3, o mais fino: "Aluguel", "Manutencao", "IPTU", "Reforma".';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_grupo', @d;

SET @d = N'QUEM PAGOU - o campo que motiva esta base. Vale ALE, LIA, Conta (quando saiu '
       + N'da conta conjunta) ou o nome de um terceiro. Aparece com variacao de caixa '
       + N'("ALE" e "Ale") que a silver unifica, senao viram duas pessoas na dimensao.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_pessoa_pagar', @d;

SET @d = N'Estabelecimento ou pessoa que recebeu. Mais de 400 valores distintos, por isso '
       + N'fica como atributo do fato e nao vira dimensao.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_pessoa_receber', @d;

SET @d = N'Forma de pagamento: C para credito, D para debito, entre outras.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_forma_pgto', @d;
SET @d = N'Descricao da forma de pagamento, indicando o cartao ou conta usada.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_descricao_pgto', @d;
SET @d = N'Data em que o gasto foi efetivamente pago, quando difere da data do lancamento.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_data_pgto', @d;
SET @d = N'Indicador de pagamento: S para pago, N para a pagar.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_status_pgto', @d;
SET @d = N'Versao por extenso do status de pagamento.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_descricao_status_pgto', @d;
SET @d = N'Cidade do gasto, preenchida na quase totalidade dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_cidade', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_uf', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_pais', @d;
SET @d = N'Observacao livre. Usada para marcar contexto, como "Viagem01_Litoral".';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_obs', @d;
SET @d = N'Mes de pagamento, calculado na planilha. Redundante com ds_data_pgto, mantido '
       + N'por fidelidade a origem.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_pgto_mes', @d;
SET @d = N'Ano de pagamento, calculado na planilha. Redundante com ds_data_pgto.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'ds_pgto_ano', @d;

SET @d = N'Numero da ocorrencia da mesma combinacao de data, descricao e valor. Necessario '
       + N'porque nao ha saldo corrente para desempatar: dois abastecimentos iguais no '
       + N'mesmo dia sao dois gastos reais.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'nr_ocorrencia', @d;

SET @d = N'IDENTIDADE DO EVENTO. SHA-256 de data + descricao normalizada + valor + numero '
       + N'da ocorrencia. Com constraint UNIQUE: e o banco que impede a duplicacao.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: identifica a origem do dado. Diferente das outras bronzes, aqui nao e '
       + N'um nome de arquivo - e a aba publicada do Google Sheets.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'nm_origem', @d;

SET @d = N'LINHAGEM: posicao da linha no CSV, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o evento entrou ou foi atualizado na base.';
EXEC dbo.sp_documenta 'bronze', 'familia_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'familia_movimentacao';
GO
