/* =============================================================
   manzo-dados | 14 - Camada Gold: fato de movimentacao
   -------------------------------------------------------------
   gold.fato_movto_financ

   Fluxo de caixa e gastos, unindo conta corrente e cartoes de
   credito. Investimentos NAO entram aqui: ficam em
   gold.fato_investimento, que tem outra natureza e outro
   vocabulario.

   O PROBLEMA QUE ESTE MODELO RESOLVE

   Um gasto no cartao aparece duas vezes na vida real:

       Itau: "Cartao de Credito XP"  -5.929,11   <- PAI  (sintetico)
             |
             +-- Cartao: mercado        -320,00  <- FILHO (analitico)
             +-- Cartao: posto          -180,00  <- FILHO
             +-- Cartao: farmacia        -95,00  <- FILHO

   Somar os dois niveis conta a mesma despesa duas vezes. DS_NIVEL
   separa os planos: gastos diretos da conta e gastos do cartao sao
   ANALITICO; o pagamento da fatura e SINTETICO.

   PARA SOMAR DESPESA, FILTRE DS_NIVEL = 'ANALITICO'. O nivel
   sintetico serve para conciliar com o extrato bancario e para ver o
   desembolso mensal com cartao.

   VOCABULARIO UNIFICADO

   As origens divergiam na grafia dos mesmos rotulos - 41 grafias de
   categoria para 32 conceitos, com "SAUDE" no cartao e "SAUDE" com
   acento no Itau. A carga canoniza preferindo a forma acentuada e
   desempatando por frequencia, para o relatorio nao mostrar dois
   membros onde existe um.

   Pre-requisitos: 00, 01, 04 (dim_calendario e dim_origem), 07, 11, 13,
                   34 (as tres dimensoes de classificacao)
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Origens de movimentacao
   ------------------------------------------------------------- */

/* As cinco ultimas vem do historico 2014-2018 e nao existem mais: sao
   os instrumentos daquela epoca. Ficam como origens proprias, e nao
   agrupadas num "historico" generico, porque so assim da para ver
   quanto passou por dinheiro e quanto pelo vale-alimentacao. */
MERGE gold.dim_origem AS destino
USING (VALUES
    (2, 'ITAU_CC',          'Itaú Conta Corrente', 'Itaú',       'Conta corrente'),
    (3, 'CARTAO_XP',        'Cartão XP',           'XP',         'Cartão de crédito'),
    (4, 'CARTAO_NUBANK',    'Cartão Nubank',       'Nubank',     'Cartão de crédito'),
    (5, 'DINHEIRO_DEBITO',  'Dinheiro / Débito',   'Diversos',   'Dinheiro e débito'),
    (6, 'VISA_BB',          'Visa Banco do Brasil', 'Banco do Brasil',
                                                                 'Cartão de crédito'),
    (7, 'VALE_ALIMENTACAO', 'Vale Alimentação',    'Benefício',  'Vale-alimentação'),
    (8, 'VISA_CTI',         'Visa Citibank',       'Citibank',   'Cartão de crédito'),
    (9, 'DINERS',           'Diners',              'Diners',     'Cartão de crédito')
) AS fonte (SK_ORIGEM, CD_ORIGEM, NM_ORIGEM, NM_INSTITUICAO, DS_TIPO_CONTA)
   ON destino.SK_ORIGEM = fonte.SK_ORIGEM
WHEN NOT MATCHED THEN
    INSERT (SK_ORIGEM, CD_ORIGEM, NM_ORIGEM, NM_INSTITUICAO, DS_TIPO_CONTA)
    VALUES (fonte.SK_ORIGEM, fonte.CD_ORIGEM, fonte.NM_ORIGEM,
            fonte.NM_INSTITUICAO, fonte.DS_TIPO_CONTA);
GO


/* -------------------------------------------------------------
   2. Fato
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_movto_financ') IS NULL
BEGIN
    CREATE TABLE gold.fato_movto_financ (
        SK_MOVIMENTACAO      int IDENTITY(1,1) NOT NULL,

        SK_ORIGEM            int           NOT NULL,
        SK_DATA              int           NOT NULL,
        SK_DATA_FATURA       int           NOT NULL,
        SK_AREA_FINANC       int           NOT NULL,
        SK_CATEGORIA_FINANC  int           NOT NULL,
        SK_GRUPO_FINANC      int           NOT NULL,

        VL_TRANSACAO         decimal(18,2) NULL,
        DS_NIVEL             varchar(12)   NOT NULL,
        DS_TIPO_FLUXO        varchar(10)   NULL,
        NR_PARCELA           int           NULL,

        DS_DETALHE_ORIGINAL  varchar(1000) NULL,
        DS_PESSOA_PAGAR      varchar(100)  NULL,
        DS_PESSOA_RECEBER    varchar(200)  NULL,
        DS_CIDADE            varchar(100)  NULL,
        DS_UF                varchar(20)   NULL,
        DS_PAIS              varchar(60)   NULL,

        HASH_NEGOCIO         char(64)      NOT NULL,
        DT_CARGA             datetime2(3)  NOT NULL
            CONSTRAINT DF_fato_movto_financ_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_movto_financ PRIMARY KEY (SK_MOVIMENTACAO),
        CONSTRAINT UQ_fato_movto_financ_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT CK_fato_movto_financ_nivel
            CHECK (DS_NIVEL IN ('ANALITICO', 'SINTETICO')),

        CONSTRAINT FK_fato_financ_origem    FOREIGN KEY (SK_ORIGEM)
            REFERENCES gold.dim_origem (SK_ORIGEM),
        CONSTRAINT FK_fato_financ_data      FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_financ_fatura    FOREIGN KEY (SK_DATA_FATURA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_financ_area  FOREIGN KEY (SK_AREA_FINANC)
            REFERENCES gold.dim_area_financ (SK_AREA_FINANC),
        CONSTRAINT FK_fato_financ_cat   FOREIGN KEY (SK_CATEGORIA_FINANC)
            REFERENCES gold.dim_categoria_financ (SK_CATEGORIA_FINANC),
        CONSTRAINT FK_fato_financ_grupo FOREIGN KEY (SK_GRUPO_FINANC)
            REFERENCES gold.dim_grupo_financ (SK_GRUPO_FINANC)
    );

    CREATE INDEX IX_fato_financ_data      ON gold.fato_movto_financ (SK_DATA);
    CREATE INDEX IX_fato_financ_area  ON gold.fato_movto_financ (SK_AREA_FINANC);
    CREATE INDEX IX_fato_financ_cat   ON gold.fato_movto_financ (SK_CATEGORIA_FINANC);
    CREATE INDEX IX_fato_financ_grupo ON gold.fato_movto_financ (SK_GRUPO_FINANC);
    CREATE INDEX IX_fato_financ_nivel     ON gold.fato_movto_financ (DS_NIVEL);
    CREATE INDEX IX_fato_financ_origem    ON gold.fato_movto_financ (SK_ORIGEM);
END
GO


/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);



SET @d = N'GOLD | Fluxo de caixa e gastos, unindo a conta corrente do Itau e os cartoes de '
       + N'credito XP e Nubank. Uma linha por movimentacao. Investimentos NAO entram aqui - '
       + N'ficam em gold.fato_investimento. '
       + N'ATENCAO AO NIVEL: um gasto no cartao existe em dois planos - o gasto detalhado '
       + N'(ANALITICO) e o pagamento da fatura na conta corrente (SINTETICO). Somar os dois '
       + N'conta a mesma despesa duas vezes. Para apurar despesa, filtre '
       + N'DS_NIVEL = ANALITICO.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', NULL, @d;

SET @d = N'Chave substituta da movimentacao.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_MOVIMENTACAO', @d;
SET @d = N'Chave para gold.dim_origem: de qual conta ou cartao veio o lancamento.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_ORIGEM', @d;
SET @d = N'Chave para gold.dim_calendario na data do lancamento - a data da compra, no '
       + N'caso do cartao. Use para responder "quanto gastei em julho".';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_calendario na data de vencimento da fatura. Preenchida '
       + N'apenas para cartao; vale -1 nos lancamentos de conta corrente. Use para fluxo '
       + N'de caixa e para conciliar com o pagamento no extrato.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_DATA_FATURA', @d;
SET @d = N'Chave para gold.dim_area_financ - nivel 1 da classificacao.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_AREA_FINANC', @d;
SET @d = N'Chave para gold.dim_categoria_financ - nivel 2, o principal para '
       + N'analise.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_CATEGORIA_FINANC', @d;
SET @d = N'Chave para gold.dim_grupo_financ - nivel 3, o mais fino. Os tres '
       + N'sao dimensoes independentes: a combinacao de cada lancamento vive '
       + N'AQUI, no fato, e nao numa dimensao de trios.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_GRUPO_FINANC', @d;

SET @d = N'METRICA. Valor em reais, com sinal: negativo e saida, positivo e entrada. '
       + N'O sinal foi uniformizado entre origens - o cartao Nubank trazia gasto positivo '
       + N'e teve o sinal invertido na silver. E aditiva, mas SOMENTE dentro do mesmo '
       + N'DS_NIVEL.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'VL_TRANSACAO', @d;

SET @d = N'NIVEL DO LANCAMENTO. ANALITICO e o gasto em si - compra no cartao ou despesa '
       + N'direta na conta. SINTETICO e o pagamento da fatura do cartao, que agrega os '
       + N'gastos analiticos daquele periodo. Existem em planos diferentes: somar os dois '
       + N'duplica a despesa. A medida de gasto do dashboard deve filtrar ANALITICO.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_NIVEL', @d;

SET @d = N'RECEITA quando o valor e positivo, DESPESA quando negativo.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_TIPO_FLUXO', @d;
SET @d = N'Numero da parcela, quando a compra no cartao foi parcelada. Nulo nos demais.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'NR_PARCELA', @d;
SET @d = N'Descricao original do lancamento, como veio da origem. Mantida para auditoria: '
       + N'e a unica forma de conferir por que uma categoria foi atribuida.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_DETALHE_ORIGINAL', @d;
SET @d = N'Quem pagou, conforme anotacao na origem.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_PESSOA_PAGAR', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu. No cartao, e o campo mais proximo de um '
       + N'cadastro de fornecedores.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_PESSOA_RECEBER', @d;
SET @d = N'Cidade do gasto, quando conhecida. Bem mais preenchida na origem cartao.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_CIDADE', @d;
SET @d = N'UF do gasto, quando conhecida.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_UF', @d;
SET @d = N'Pais do gasto. Util para isolar consumo em viagem.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_PAIS', @d;
SET @d = N'Identidade do evento, herdada da silver. Com constraint UNIQUE: e o banco que '
       + N'impede a duplicacao, nao o script de carga.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando o lancamento foi carregado na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'gold' ORDER BY 1;
GO
