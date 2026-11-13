/* =============================================================
   manzo-dados | 17 - Camada Gold: fato da conta familia
   -------------------------------------------------------------
   gold.fato_familia + gold.dim_pessoa

   Gastos em comum de Ale e Lia, em fato proprio.

   POR QUE UM FATO SEPARADO. Este dinheiro nao e o mesmo do fato
   pessoal: os dois fazem aportes para contas conjuntas e a base
   registra o que sai dali. Misturar com gold.fato_movto_financ
   contaria gasto de duas pessoas como se fosse de uma. O Power BI
   tem pagina propria para este assunto.

   O QUE E COMPARTILHADO: dim_calendario e dim_categoria_financ. O
   vocabulario de area, categoria e grupo e o mesmo das origens
   pessoais em dez categorias, e compartilhar a dimensao permite
   comparar "quanto gastei de alimentacao sozinho" com "quanto a
   familia gastou de alimentacao" pelo mesmo eixo. As oito
   categorias exclusivas da familia - MORADIA, DIARISTA, HOSPEDAGEM e
   outras - entram na dimensao na primeira carga, como qualquer
   combinacao nova.

   O QUE E PROPRIO: dim_pessoa, que responde quem pagou. E o eixo
   que motiva a base inteira.

   Pre-requisitos: 00, 01, 04 (calendario), 34 (classificacao), 16
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Dimensao de pessoa
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_pessoa') IS NULL
BEGIN
    CREATE TABLE gold.dim_pessoa (
        SK_PESSOA   int IDENTITY(1,1) NOT NULL,
        NM_PESSOA   varchar(100)      NOT NULL,
        DS_TIPO     varchar(30)       NOT NULL,
        DT_CARGA    datetime2(3)      NOT NULL
            CONSTRAINT DF_dim_pessoa_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_pessoa PRIMARY KEY (SK_PESSOA),
        CONSTRAINT UQ_dim_pessoa_nome UNIQUE (NM_PESSOA)
    );

    SET IDENTITY_INSERT gold.dim_pessoa ON;
    INSERT INTO gold.dim_pessoa (SK_PESSOA, NM_PESSOA, DS_TIPO)
    VALUES (-1, 'Não informado', 'Não informado');
    SET IDENTITY_INSERT gold.dim_pessoa OFF;
END
GO


/* -------------------------------------------------------------
   2. Fato
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_familia') IS NULL
BEGIN
    CREATE TABLE gold.fato_familia (
        SK_LANCAMENTO       int IDENTITY(1,1) NOT NULL,

        SK_DATA             int           NOT NULL,
        SK_DATA_PAGAMENTO   int           NOT NULL,
        SK_AREA_FINANC      int           NOT NULL,
        SK_CATEGORIA_FINANC int           NOT NULL,
        SK_GRUPO_FINANC     int           NOT NULL,
        SK_PESSOA           int           NOT NULL,

        VL_TRANSACAO        decimal(18,2) NULL,
        DS_TIPO_FLUXO       varchar(10)   NULL,
        FL_PAGO             bit           NOT NULL,
        FL_FUTURO           bit           NOT NULL,

        DS_DETALHE_ORIGINAL varchar(1000) NULL,
        DS_PESSOA_RECEBER   varchar(200)  NULL,
        DS_CIDADE           varchar(100)  NULL,
        DS_UF               varchar(20)   NULL,
        DS_PAIS             varchar(60)   NULL,

        HASH_NEGOCIO        char(64)      NOT NULL,
        DT_CARGA            datetime2(3)  NOT NULL
            CONSTRAINT DF_fato_familia_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_familia PRIMARY KEY (SK_LANCAMENTO),
        CONSTRAINT UQ_fato_familia_hash UNIQUE (HASH_NEGOCIO),

        CONSTRAINT FK_fato_fam_data      FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_fam_data_pgto FOREIGN KEY (SK_DATA_PAGAMENTO)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_fam_area FOREIGN KEY (SK_AREA_FINANC)
            REFERENCES gold.dim_area_financ (SK_AREA_FINANC),
        CONSTRAINT FK_fato_fam_cat FOREIGN KEY (SK_CATEGORIA_FINANC)
            REFERENCES gold.dim_categoria_financ (SK_CATEGORIA_FINANC),
        CONSTRAINT FK_fato_fam_grupo FOREIGN KEY (SK_GRUPO_FINANC)
            REFERENCES gold.dim_grupo_financ (SK_GRUPO_FINANC),
        CONSTRAINT FK_fato_fam_pessoa    FOREIGN KEY (SK_PESSOA)
            REFERENCES gold.dim_pessoa (SK_PESSOA)
    );

    CREATE INDEX IX_fato_fam_data      ON gold.fato_familia (SK_DATA);
    CREATE INDEX IX_fato_fam_area  ON gold.fato_familia (SK_AREA_FINANC);
    CREATE INDEX IX_fato_fam_cat   ON gold.fato_familia (SK_CATEGORIA_FINANC);
    CREATE INDEX IX_fato_fam_grupo ON gold.fato_familia (SK_GRUPO_FINANC);
    CREATE INDEX IX_fato_fam_pessoa    ON gold.fato_familia (SK_PESSOA);
END
GO


/* -------------------------------------------------------------
   3. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Quem paga os gastos da familia: Ale, Lia, a conta conjunta ou '
       + N'um terceiro. E o eixo que motiva a base da familia inteira - somar por esta '
       + N'dimensao responde quanto cada um bancou. A grafia foi unificada na silver: a '
       + N'origem trazia "ALE" e "Ale" como se fossem duas pessoas.';
EXEC dbo.sp_documenta 'gold', 'dim_pessoa', NULL, @d;

SET @d = N'Chave substituta da pessoa. -1 representa pagador nao informado.';
EXEC dbo.sp_documenta 'gold', 'dim_pessoa', 'SK_PESSOA', @d;
SET @d = N'Nome de quem pagou, como registrado na planilha.';
EXEC dbo.sp_documenta 'gold', 'dim_pessoa', 'NM_PESSOA', @d;
SET @d = N'Natureza do pagador: Titular para Ale e Lia, Conta conjunta quando o '
       + N'gasto saiu do fundo comum, e Terceiro para os demais. Separa o que cada um '
       + N'bancou do proprio bolso do que saiu do dinheiro ja aportado por ambos - somar '
       + N'as tres categorias como se fossem equivalentes distorce a divisao real.';
EXEC dbo.sp_documenta 'gold', 'dim_pessoa', 'DS_TIPO', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_pessoa', 'DT_CARGA', @d;

SET @d = N'GOLD | Gastos em comum de Ale e Lia, uma linha por lancamento. '
       + N'Fato SEPARADO do pessoal de proposito: este dinheiro vem dos aportes mensais '
       + N'dos dois para as contas conjuntas, e misturar com gold.fato_movto_financ '
       + N'contaria gasto de duas pessoas como se fosse de uma. As transferencias que '
       + N'Alexandre faz para a conta familia aparecem no fato pessoal e sao assunto '
       + N'independente destes gastos. '
       + N'ATENCAO: ha lancamentos com data futura, parcelas que vao ate 2031 - use '
       + N'FL_FUTURO para separar o que ja aconteceu do que esta comprometido.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', NULL, @d;

SET @d = N'Chave substituta do lancamento.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_LANCAMENTO', @d;
SET @d = N'Chave para gold.dim_calendario na data do gasto.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_calendario na data do pagamento efetivo. Vale -1 quando '
       + N'nao informada.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_DATA_PAGAMENTO', @d;
SET @d = N'Chave para gold.dim_area_financ - a MESMA dimensao do fato pessoal.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_AREA_FINANC', @d;
SET @d = N'Chave para gold.dim_categoria_financ - a MESMA do fato pessoal, o '
       + N'que permite comparar gasto proprio e da familia pelo mesmo eixo.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_CATEGORIA_FINANC', @d;
SET @d = N'Chave para gold.dim_grupo_financ - nivel 3, o mais fino.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_GRUPO_FINANC', @d;
SET @d = N'Chave para gold.dim_pessoa: quem pagou.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_PESSOA', @d;

SET @d = N'METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. '
       + N'Aditiva.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'VL_TRANSACAO', @d;
SET @d = N'RECEITA quando o valor e positivo, DESPESA quando negativo.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_TIPO_FLUXO', @d;
SET @d = N'S quando a planilha registra o gasto como pago.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'FL_PAGO', @d;
SET @d = N'1 quando a data do lancamento ainda nao chegou - parcelas a vencer, que vao ate '
       + N'2031. Filtre por 0 para apurar o que de fato aconteceu; por 1 para ver o '
       + N'comprometimento futuro. Somar os dois juntos mistura passado e compromisso.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'FL_FUTURO', @d;

SET @d = N'Descricao original do gasto. Mantida para auditoria da classificacao.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_DETALHE_ORIGINAL', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu. Atributo do fato, e nao dimensao, por '
       + N'ter mais de 400 valores distintos.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_PESSOA_RECEBER', @d;
SET @d = N'Cidade do gasto.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_CIDADE', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_UF', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_PAIS', @d;
SET @d = N'Identidade do evento, herdada da silver. Com constraint UNIQUE.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando o lancamento foi carregado na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('fato_familia', 'dim_pessoa') ORDER BY 1;
GO
