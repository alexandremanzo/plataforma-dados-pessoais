/* =============================================================
   manzo-dados | 08 - De-para de categorias da conta Itau
   -------------------------------------------------------------
   silver.de_para_categoria_itau

   Tabela de apoio alimentada por revisao-categorias-itau.xlsx, onde
   os lancamentos sem classificacao sao agrupados por PADRAO de
   operacao (a descricao sem numeros, datas e pontuacao).

   Existe porque as descricoes do Itau embutem data e nome parcial do
   estabelecimento, o que as torna quase unicas: sao 1.842 lancamentos
   sem categoria em 762 padroes distintos. Rotular por padrao permite
   resolver dezenas de lancamentos com uma decisao, e a concentracao
   ajuda - 10 padroes cobrem 78% do volume e 30 cobrem 90%.

   O de-para NAO sobrescreve o que a planilha ja classificou. Ele so
   preenche o que esta como "A classificar", e a silver registra em
   DS_ORIGEM_CLASSIFICACAO de onde cada rotulo veio.

   Pre-requisitos: 00, 01, 07
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.de_para_categoria_itau') IS NULL
BEGIN
    CREATE TABLE silver.de_para_categoria_itau (
        ds_padrao      varchar(300)  NOT NULL,
        ds_area        varchar(100)  NULL,
        ds_categoria   varchar(100)  NULL,
        ds_grupo       varchar(100)  NULL,
        nr_ocorrencias int           NULL,
        vl_volume      decimal(18,2) NULL,
        dt_carga       datetime2(3)  NOT NULL
            CONSTRAINT DF_de_para_itau_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_de_para_categoria_itau PRIMARY KEY (ds_padrao)
    );
END
GO

/* Coluna que registra a procedencia do rotulo. Adicionada depois da
   criacao da silver, entao precisa do IF. */
IF COL_LENGTH('silver.itau_movimentacao', 'ds_origem_classificacao') IS NULL
    ALTER TABLE silver.itau_movimentacao
        ADD ds_origem_classificacao varchar(20) NULL;
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | De-para de categorias por padrao de operacao da conta Itau. '
       + N'Alimentada pela planilha revisao-categorias-itau.xlsx, preenchida a mao. '
       + N'Cada linha rotula um padrao (a descricao sem numeros nem datas) e vale para '
       + N'todos os lancamentos que casam com ele, no historico e nas cargas futuras. '
       + N'Nunca sobrescreve classificacao existente: so preenche o que esta como '
       + N'"A classificar".';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', NULL, @d;

SET @d = N'Padrao da operacao: a descricao do lancamento sem numeros, datas e pontuacao. '
       + N'Ex: "PIX TRANSF ALEXAND" cobre "PIX TRANSF ALEXAND12/01" e '
       + N'"PIX TRANSF  ALEXAND10/08". E a chave da tabela.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'ds_padrao', @d;

SET @d = N'Area atribuida ao padrao na revisao manual. Nulo significa que o padrao foi '
       + N'listado mas ainda nao rotulado.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'ds_area', @d;

SET @d = N'Categoria atribuida ao padrao na revisao manual - o nivel principal de analise.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'ds_categoria', @d;

SET @d = N'Grupo atribuido ao padrao na revisao manual - o nivel mais fino.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'ds_grupo', @d;

SET @d = N'Quantos lancamentos casavam com este padrao quando a lista foi gerada. '
       + N'Serve para priorizar a revisao, nao para calculo.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'nr_ocorrencias', @d;

SET @d = N'Volume absoluto em reais que este padrao representava quando a lista foi '
       + N'gerada. Serve para priorizar a revisao pelo que pesa no bolso.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'vl_volume', @d;

SET @d = N'LINHAGEM: quando o rotulo entrou na tabela.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_itau', 'dt_carga', @d;

SET @d = N'Procedencia do rotulo de categoria: PLANILHA quando veio classificado da aba '
       + N'cad-conta, DE-PARA quando foi atribuido pela tabela de revisao por padrao, e '
       + N'A CLASSIFICAR quando ainda nao tem categoria. Permite medir quanto da base '
       + N'depende de cada fonte e auditar o efeito de uma revisao.';
EXEC dbo.sp_documenta 'silver', 'itau_movimentacao', 'ds_origem_classificacao', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'silver' ORDER BY 1;
GO
