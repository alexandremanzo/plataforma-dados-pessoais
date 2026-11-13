/* =============================================================
   manzo-dados | 07 - Camada Silver: conta corrente Itau
   -------------------------------------------------------------
   silver.itau_movimentacao

   Tipagem e padronizacao. Diferente do XP, aqui NAO se deduz
   categoria a partir da descricao: as descricoes do banco
   ("LOJA-EXEMPLO*CAT-", "TBI 0000.00000-0/5") sao quase unicas e
   os testes mostraram que inferir produziria mais erro que acerto.
   O que a planilha nao classificou fica como "A classificar".

   Tres decisoes registradas:

   1. A METRICA E "Valor", nao "Valor Trat". As duas colunas sao
      identicas em toda a serie; "Valor Trat" so difere nas 9 linhas
      vindas do extrato, onde esta vazia. E coluna redundante.

   2. AS LINHAS DE SALDO NAO SAO TRANSACAO. Sao 141 marcadores de
      saldo final ou parcial anotados no extrato. Ficam aqui com
      FL_SALDO = 1 e a gold as exclui - somadas, inflariam o fluxo.

   3. A HIERARQUIA AREA > CATEGORIA > GRUPO NAO E ESTRITA. O grupo
      "Reembolso" aparece sob 4 categorias e a categoria "EMPRESTIMO"
      sob 5 areas. Por isso os tres sao atributos independentes do
      lancamento, e nao uma hierarquia navegavel: tratar como
      hierarquia produziria totais ambiguos no Power BI.

   Pre-requisitos: 00, 01, 06
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.itau_movimentacao') IS NULL
BEGIN
    CREATE TABLE silver.itau_movimentacao (
        sk_movimentacao       int IDENTITY(1,1) NOT NULL,

        dt_lancamento         date              NULL,
        dt_pagamento          date              NULL,
        ds_descricao          varchar(1000)     NULL,
        vl_transacao          decimal(18,2)     NULL,

        ds_tipo_movimentacao  varchar(20)       NULL,
        fl_saldo              bit               NOT NULL,

        ds_area               varchar(100)      NOT NULL,
        ds_categoria          varchar(100)      NOT NULL,
        ds_grupo              varchar(100)      NOT NULL,
        fl_classificado       bit               NOT NULL,

        ds_pessoa_pagar       varchar(100)      NULL,
        ds_pessoa_receber     varchar(100)      NULL,
        ds_forma_pgto         varchar(50)       NULL,
        ds_descricao_pgto     varchar(200)      NULL,
        ds_cidade             varchar(100)      NULL,
        ds_uf                 varchar(20)       NULL,
        ds_pais               varchar(60)       NULL,
        ds_obs                varchar(1000)     NULL,
        ds_projeto            varchar(100)      NULL,
        ds_tag                varchar(100)      NULL,

        hash_negocio          char(64)          NOT NULL,
        dt_carga              datetime2(3)      NOT NULL
            CONSTRAINT DF_silver_itau_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_itau PRIMARY KEY CLUSTERED (sk_movimentacao),
        CONSTRAINT UQ_silver_itau_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_itau_data      ON silver.itau_movimentacao (dt_lancamento);
    CREATE INDEX IX_silver_itau_categoria ON silver.itau_movimentacao (ds_categoria);
    CREATE INDEX IX_silver_itau_area      ON silver.itau_movimentacao (ds_area);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Movimentacoes da conta corrente do Itau, limpas e tipadas, desde 2016. '
       + N'Uma linha por evento real. A classificacao vem da planilha, nao de regra: o que '
       + N'nao foi classificado a mao aparece como "A classificar", jamais adivinhado. '
       + N'Inclui as linhas de saldo (FL_SALDO = 1), que a gold exclui por nao serem '
       + N'transacao. Os rotulos de area, categoria e grupo tiveram a grafia unificada - '
       + N'"Casa" e "CASA" conviviam na origem e virariam dois membros na dimensao.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', NULL, @d;

SET @d = N'Chave substituta do lancamento na silver. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'sk_movimentacao', @d;

SET @d = N'Data em que o lancamento ocorreu na conta.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'dt_lancamento', @d;

SET @d = N'Data do pagamento efetivo, quando anotada na planilha e diferente da data do '
       + N'lancamento. Util para despesas com vencimento posterior.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'dt_pagamento', @d;

SET @d = N'Descricao do lancamento como o Itau a gera. Preservada integralmente: e a unica '
       + N'forma de identificar o estabelecimento e de auditar a classificacao.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_descricao', @d;

SET @d = N'METRICA. Valor do lancamento em reais. Positivo = entrada na conta, negativo = '
       + N'saida. Vem da coluna "Valor" da planilha; "Valor Trat" foi descartada por ser '
       + N'identica em toda a serie.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'vl_transacao', @d;

SET @d = N'RECEITA, DESPESA ou SALDO. Coerente com o sinal do valor em 100% da serie, o que '
       + N'permitiu deduzi-lo para os lancamentos vindos do extrato, que nao trazem o campo.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'Marca 1 quando a linha e um marcador de saldo (final ou parcial) anotado no '
       + N'extrato, e nao uma transacao. SEMPRE filtre por FL_SALDO = 0 ao somar valores: '
       + N'saldo somado com movimentacao nao significa nada. A gold ja exclui estas linhas.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'fl_saldo', @d;

SET @d = N'CLASSIFICACAO nivel 1, a mais ampla: TRANSFERENCIA, ESTILO DE VIDA, RENDA, '
       + N'GASTOS ESSENCIAIS, TAXA, EMPRESTIMO e outras. Vale "A classificar" quando a '
       + N'planilha nao preencheu. ATENCAO: nao e uma hierarquia estrita sobre categoria - '
       + N'a mesma categoria aparece sob areas diferentes ao longo do tempo.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2, o nivel principal de analise de gastos: TRANSFERENCIA, '
       + N'RENDIMENTO, TRABALHO, CASA, TRANSPORTE, ALIMENTACAO, EDUCACAO e outros. Vale '
       + N'"A classificar" quando a planilha nao preencheu - hoje cerca de 37% da serie, '
       + N'concentrada antes de 2024.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO nivel 3, a mais fina: "Movimentacao entre contas", "Combustivel", '
       + N'"Escola Nina", "Almoco". E o nivel usado para acompanhar metas por assunto. '
       + N'Vale "A classificar" quando ausente.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_grupo', @d;

SET @d = N'Marca 1 quando o lancamento tem categoria vinda da planilha e 0 quando esta '
       + N'como "A classificar". Filtrar por este campo mostra rapidamente o que ainda '
       + N'precisa de revisao, ordenado por valor.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'fl_classificado', @d;

SET @d = N'Quem pagou, conforme anotacao manual.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_pessoa_pagar', @d;
SET @d = N'Quem recebeu, conforme anotacao manual.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_pessoa_receber', @d;
SET @d = N'Forma de pagamento anotada na planilha.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_forma_pgto', @d;
SET @d = N'Descricao complementar da forma de pagamento.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_descricao_pgto', @d;
SET @d = N'Cidade do gasto, quando anotada (cerca de 19% dos lancamentos).';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_cidade', @d;
SET @d = N'UF do gasto, quando anotada.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_uf', @d;
SET @d = N'Pais do gasto, quando anotado. Util para isolar gastos de viagem.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_pais', @d;
SET @d = N'Observacao livre anotada na planilha.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_obs', @d;
SET @d = N'Projeto vinculado ao gasto. Praticamente nao utilizado na origem.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_projeto', @d;
SET @d = N'Marcador livre, fora da hierarquia de categoria.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_tag', @d;

SET @d = N'Identidade do evento, herdada de bronze.itau_movimentacao. Inclui o numero da '
       + N'ocorrencia no dia, porque o extrato do Itau nao traz saldo para desempatar '
       + N'transacoes identicas.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'silver' ORDER BY 1;
GO
