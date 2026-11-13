/* =============================================================
   manzo-dados | 32 - Camada Silver: historico financeiro
   -------------------------------------------------------------
   silver.financ_historico

   Tipagem, classificacao e as duas decisoes que esta origem exige.

   1. FL_META SEPARA ORCAMENTO DE MOVIMENTACAO. Sao 287 linhas com
      tipo "Meta" e grupo "META", 24 por categoria, somando
      +R$ 135.522 - orcamento mensal planejado de dois anos, nao
      dinheiro que entrou. Ficam aqui por fidelidade e sao excluidas
      no fato, do mesmo jeito que a gold de investimentos exclui
      margem.

   2. A AREA E DERIVADA, PORQUE A ORIGEM NAO A TEM. A coluna Area da
      planilha esta vazia em todas as linhas, mas categoria e grupo
      estao preenchidos. A area vem do vocabulario que ja existe nas
      tres dimensoes financeiras, em dois niveis, e DS_ORIGEM_AREA
      registra qual deles decidiu:

        PAR_EXATO     categoria + grupo ja existem juntos       ~74%
        CATEGORIA     so a categoria existe, usa a mais comum   ~23%
        A classificar nem isso                                   ~3%

      A distincao importa e nao e formalidade. PAR_EXATO e
      EVIDENCIA: aquela combinacao ja foi classificada assim antes.
      CATEGORIA e INFERENCIA, e existe porque a propria
      classificacao e ambigua - TRANSPORTE/Combustivel
      aparece sob ESTILO DE VIDA em 212 lancamentos e sob GASTOS
      ESSENCIAIS em outros 128. Marcar a procedencia permite ao
      relatorio confiar num e tratar o outro como provisorio, e
      permite refazer so a inferencia quando houver revisao.

   Pre-requisitos: 00, 01, 34 (dimensoes de classificacao), 31
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.financ_historico') IS NULL
BEGIN
    CREATE TABLE silver.financ_historico (
        sk_lancamento      int IDENTITY(1,1) NOT NULL,

        dt_lancamento      date          NULL,
        dt_pagamento       date          NULL,
        ds_descricao       varchar(1000) NULL,
        vl_transacao       decimal(18,2) NULL,
        ds_tipo_movimentacao varchar(20) NULL,
        fl_meta            bit           NOT NULL,

        ds_area            varchar(100)  NOT NULL,
        ds_categoria       varchar(100)  NOT NULL,
        ds_grupo           varchar(100)  NOT NULL,
        ds_origem_area     varchar(20)   NOT NULL,
        fl_classificado    bit           NOT NULL,

        ds_forma_pagamento varchar(60)   NULL,
        ds_pessoa_pagar    varchar(120)  NULL,
        ds_pessoa_receber  varchar(200)  NULL,
        ds_cidade          varchar(100)  NULL,
        ds_uf              varchar(20)   NULL,
        ds_pais            varchar(60)   NULL,
        ds_obs             varchar(500)  NULL,
        ds_projeto         varchar(100)  NULL,
        fl_pago            bit           NOT NULL,

        hash_negocio       char(64)      NOT NULL,
        dt_carga           datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_financ_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_financ_historico PRIMARY KEY CLUSTERED (sk_lancamento),
        CONSTRAINT UQ_silver_financ_historico_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_financ_data ON silver.financ_historico (dt_lancamento);
    CREATE INDEX IX_silver_financ_cat  ON silver.financ_historico (ds_categoria);
    CREATE INDEX IX_silver_financ_meta ON silver.financ_historico (fl_meta);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Historico financeiro de 2014 a 2018, tipado e classificado. Uma linha '
       + N'por lancamento. Alimenta gold.fato_movto_financ ao lado das origens atuais, '
       + N'estendendo a serie dois anos e meio para tras. '
       + N'FILTRE fl_meta = 0 para movimentacao de verdade: 287 linhas sao orcamento '
       + N'planejado e nao dinheiro movimentado.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', NULL, @d;

SET @d = N'Chave substituta do lancamento. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'sk_lancamento', @d;
SET @d = N'Data do lancamento. A serie vai de fevereiro/2014 a maio/2018.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'dt_lancamento', @d;
SET @d = N'Data do pagamento efetivo, quando difere da data do lancamento.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'dt_pagamento', @d;
SET @d = N'Descricao do lancamento, preservada para auditoria.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_descricao', @d;

SET @d = N'METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. '
       + N'NAO SOME sem filtrar fl_meta = 0 - as linhas de orcamento sao positivas e '
       + N'somariam R$ 135.522 de receita inexistente.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'vl_transacao', @d;

SET @d = N'DESPESA, RECEITA ou META, com a grafia unificada.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_tipo_movimentacao', @d;

SET @d = N'1 quando a linha e ORCAMENTO PLANEJADO e nao movimentacao. Sao 287 registros, '
       + N'24 por categoria, cobrindo dois anos de meta mensal. O fato os exclui; ficam '
       + N'aqui porque descarta-los na carga apagaria informacao que a planilha tem.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'fl_meta', @d;

SET @d = N'CLASSIFICACAO nivel 1, DERIVADA e nao lida da origem - a coluna Area da planilha '
       + N'esta vazia. Ver ds_origem_area para saber com que confianca cada valor foi '
       + N'atribuido.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_area', @d;
SET @d = N'CLASSIFICACAO nivel 2, lida da origem. Tres categorias nao existem nas origens '
       + N'atuais: AJUSTE, FINANCAS e Telefonia.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_categoria', @d;
SET @d = N'CLASSIFICACAO nivel 3, lida da origem.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_grupo', @d;

SET @d = N'PROCEDENCIA DA AREA, e a coluna que separa evidencia de palpite. '
       + N'PAR_EXATO: a combinacao categoria + grupo ja existia na classificacao, '
       + N'entao a area veio de classificacao anterior sua. '
       + N'CATEGORIA: so a categoria existia, e foi usada a area mais frequente dela - e '
       + N'INFERENCIA, necessaria porque o proprio vocabulario e ambiguo '
       + N'(TRANSPORTE/Combustivel aparece sob duas areas diferentes). '
       + N'A CLASSIFICAR: nem a categoria existia. '
       + N'Trate CATEGORIA como provisorio no relatorio, e refaca a inferencia quando '
       + N'revisar a classificacao.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_origem_area', @d;

SET @d = N'Marca 1 quando o lancamento tem categoria vinda da planilha.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'fl_classificado', @d;

SET @d = N'Instrumento de pagamento, com a grafia unificada: a origem trazia "visa BB" e '
       + N'"Visa BB", "Dinheiro/Debito" e "dinheiro/Debito". Vira a origem do fato.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_forma_pagamento', @d;

SET @d = N'Quem pagou.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_pessoa_pagar', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_pessoa_receber', @d;
SET @d = N'Cidade do gasto.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_cidade', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_uf', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_pais', @d;

SET @d = N'Observacao livre. NAO vira tag nesta origem - o campo guarda numeros soltos que '
       + N'o interpretador de marcacoes leria errado. Quem marca contexto aqui e '
       + N'ds_projeto.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_obs', @d;

SET @d = N'MARCACAO DE CONTEXTO: Compacto, Hatch 2008, Viagem Exterior, Sedan 2016. Alimenta '
       + N'gold.dim_tag pela mesma ponte das demais origens, o que permite somar "quanto '
       + N'custou o Hatch" atravessando bases e decadas.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'ds_projeto', @d;

SET @d = N'1 quando a planilha registra o lancamento como pago.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'fl_pago', @d;
SET @d = N'Identidade do lancamento, herdada da bronze.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'financ_historico', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'financ_historico' ORDER BY 1;
GO
