/* =============================================================
   manzo-dados | 11 - Camada Silver: cartoes de credito
   -------------------------------------------------------------
   silver.cartao_movimentacao

   UMA tabela para todos os cartoes, com DS_CARTAO identificando a
   origem. Hoje recebe o XP; o Nubank entra na sequencia, cobrindo
   2018-2022, e emenda exatamente onde o XP comeca.

   Sao os lancamentos ANALITICOS do modelo de movimentacao: cada
   compra individual. O pagamento da fatura, que aparece na conta
   corrente, e o SINTETICO correspondente. Somar os dois niveis
   contaria a mesma despesa duas vezes - por isso a gold marca o
   nivel e a medida de despesa usa so o analitico.

   Duas datas, com papeis diferentes:

       DT_COMPRA  - quando o gasto aconteceu. Use para saber em que
                    mes voce gastou.
       DT_FATURA  - quando foi cobrado. Use para conciliar com o
                    pagamento na conta corrente e para fluxo de caixa.

   Uma compra parcelada tem uma DT_COMPRA e varias DT_FATURA, algumas
   ainda futuras.

   Pre-requisitos: 00, 01, 09
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.cartao_movimentacao') IS NULL
BEGIN
    CREATE TABLE silver.cartao_movimentacao (
        sk_movimentacao       int IDENTITY(1,1) NOT NULL,
        ds_cartao             varchar(30)       NOT NULL,

        dt_compra             date              NULL,
        dt_fatura             date              NULL,
        ds_descricao          varchar(1000)     NULL,
        nr_parcela            int               NULL,
        vl_transacao          decimal(18,2)     NULL,
        ds_tipo_movimentacao  varchar(20)       NULL,

        ds_area               varchar(100)      NOT NULL,
        ds_categoria          varchar(100)      NOT NULL,
        ds_grupo              varchar(100)      NOT NULL,
        fl_classificado       bit               NOT NULL,

        ds_pessoa_pagar       varchar(100)      NULL,
        ds_pessoa_receber     varchar(200)      NULL,
        ds_cidade             varchar(100)      NULL,
        ds_uf                 varchar(20)       NULL,
        ds_pais               varchar(60)       NULL,
        ds_obs                varchar(1000)     NULL,
        fl_pago               bit               NOT NULL,

        hash_negocio          char(64)          NOT NULL,
        dt_carga              datetime2(3)      NOT NULL
            CONSTRAINT DF_silver_cartao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_cartao PRIMARY KEY CLUSTERED (sk_movimentacao),
        CONSTRAINT UQ_silver_cartao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_cartao_compra    ON silver.cartao_movimentacao (dt_compra);
    CREATE INDEX IX_silver_cartao_fatura    ON silver.cartao_movimentacao (dt_fatura);
    CREATE INDEX IX_silver_cartao_categoria ON silver.cartao_movimentacao (ds_categoria);
    CREATE INDEX IX_silver_cartao_cartao    ON silver.cartao_movimentacao (ds_cartao);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Gastos de cartao de credito, limpos e tipados, de todos os cartoes. '
       + N'DS_CARTAO identifica a origem. Sao os lancamentos ANALITICOS do modelo de '
       + N'movimentacao: cada compra individual. O pagamento da fatura, lancado na conta '
       + N'corrente, e o SINTETICO correspondente - somar os dois contaria a mesma despesa '
       + N'duas vezes. Diferente da conta corrente, esta origem vem quase toda classificada '
       + N'na propria planilha, porque a descricao e escrita por voce e nao pelo banco.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', NULL, @d;

SET @d = N'Chave substituta do lancamento. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'sk_movimentacao', @d;

SET @d = N'Cartao de origem do gasto: XP ou Nubank. Permite comparar o padrao de consumo '
       + N'entre cartoes e emendar as duas series, que nao se sobrepoem no tempo.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_cartao', @d;

SET @d = N'Data em que a COMPRA foi feita. Use para responder "quanto gastei em julho". '
       + N'Nao confundir com dt_fatura: uma compra de julho pode ser cobrada em agosto.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'dt_compra', @d;

SET @d = N'Data de vencimento da FATURA em que o gasto foi cobrado. Use para conciliar com '
       + N'o pagamento lancado na conta corrente e para fluxo de caixa. Uma compra '
       + N'parcelada tem uma data de compra e varias de fatura, parte delas ainda futuras.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'dt_fatura', @d;

SET @d = N'Descricao do gasto, escrita manualmente ("Lanche Nina", "Gasolina"). E o que '
       + N'torna esta origem muito mais classificavel que o extrato bancario.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_descricao', @d;

SET @d = N'Numero da parcela, quando a compra foi parcelada. Nulo em compra a vista. '
       + N'E o que explica faturas com vencimento futuro.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'nr_parcela', @d;

SET @d = N'METRICA. Valor do lancamento em reais, com sinal: negativo e gasto, positivo e '
       + N'estorno. Vem da coluna "Valor Trat" da planilha, e nao de "Valor", cujo sinal e '
       + N'inconsistente nos estornos.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'vl_transacao', @d;

SET @d = N'RECEITA para valores positivos (estornos) e DESPESA para negativos.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'CLASSIFICACAO nivel 1: ESTILO DE VIDA, GASTOS ESSENCIAIS, TRANSFERENCIA. '
       + N'Mesmo vocabulario da conta corrente, o que permite somar as duas origens.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2, o principal para analise de gastos: ALIMENTACAO, '
       + N'TRANSPORTE, CASA, LAZER e outras. Vale "A classificar" quando ausente - raro '
       + N'nesta origem.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO nivel 3, a mais fina: "Combustivel", "Lanche", "Estacionamento".';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_grupo', @d;

SET @d = N'Marca 1 quando o lancamento tem categoria vinda da planilha.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'fl_classificado', @d;

SET @d = N'Quem pagou o gasto.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_pessoa_pagar', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu. E o campo mais proximo de um cadastro '
       + N'de fornecedores nesta base.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_pessoa_receber', @d;
SET @d = N'Cidade do gasto. Muito mais preenchida aqui que na conta corrente, o que torna '
       + N'o cartao a melhor origem para analise geografica de consumo.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_cidade', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_uf', @d;
SET @d = N'Pais do gasto. Util para isolar consumo em viagem.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_pais', @d;
SET @d = N'Observacao livre anotada na planilha.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'ds_obs', @d;

SET @d = N'Marca 1 quando a fatura correspondente ja foi paga e 0 quando ainda vai vencer. '
       + N'Permite separar o que ja saiu do bolso do que esta comprometido - util porque '
       + N'compras parceladas geram faturas futuras.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'fl_pago', @d;

SET @d = N'Identidade do evento, herdada da bronze. Inclui a data da fatura, porque cada '
       + N'parcela de uma compra parcelada e um evento proprio.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'silver' ORDER BY 1;
GO
