/* =============================================================
   manzo-dados | 16 - Camada Silver: conta familia
   -------------------------------------------------------------
   silver.familia_movimentacao

   Tipagem e padronizacao dos gastos em comum. Como nas demais
   origens, nada e inferido: o que a planilha nao classificou fica
   como "A classificar".

   O QUE ESTA CAMADA UNIFORMIZA:

   - Grafias de rotulo. "DESPESA" aparece de quatro formas na
     origem (DESPESA, Despesa, DEspesa, DeSPESA) e "ALE" de duas.
     Sem unificar, viram membros distintos na dimensao - e a
     transparencia de quem pagou o que, que motiva esta base,
     mostraria a mesma pessoa duas vezes.

   - Coerencia de sinal. FL_SINAL_DIVERGENTE marca lancamentos em
     que o sinal do valor contradiz o tipo declarado. Foi assim que
     cinco reformas apareceram como receita: o valor tinha sido
     digitado negativo e a formula da planilha o inverteu. O
     indicador existe para que isso seja visivel, e nao silencioso.

   Pre-requisitos: 00, 01, 15
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.familia_movimentacao') IS NULL
BEGIN
    CREATE TABLE silver.familia_movimentacao (
        sk_movimentacao      int IDENTITY(1,1) NOT NULL,

        dt_lancamento        date          NULL,
        dt_pagamento         date          NULL,
        ds_descricao         varchar(1000) NULL,
        vl_transacao         decimal(18,2) NULL,
        ds_tipo_movimentacao varchar(20)   NULL,

        ds_area              varchar(100)  NOT NULL,
        ds_categoria         varchar(100)  NOT NULL,
        ds_grupo             varchar(100)  NOT NULL,
        fl_classificado      bit           NOT NULL,

        ds_pessoa_pagar      varchar(100)  NULL,
        ds_pessoa_receber    varchar(200)  NULL,
        ds_forma_pgto        varchar(50)   NULL,
        ds_descricao_pgto    varchar(200)  NULL,
        ds_cidade            varchar(100)  NULL,
        ds_uf                varchar(20)   NULL,
        ds_pais              varchar(60)   NULL,
        ds_obs               varchar(1000) NULL,

        fl_pago              bit           NOT NULL,
        fl_sinal_divergente  bit           NOT NULL,

        hash_negocio         char(64)      NOT NULL,
        dt_carga             datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_familia_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_familia PRIMARY KEY CLUSTERED (sk_movimentacao),
        CONSTRAINT UQ_silver_familia_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_familia_data      ON silver.familia_movimentacao (dt_lancamento);
    CREATE INDEX IX_silver_familia_categoria ON silver.familia_movimentacao (ds_categoria);
    CREATE INDEX IX_silver_familia_pessoa    ON silver.familia_movimentacao (ds_pessoa_pagar);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Gastos em comum de Ale e Lia, limpos e tipados. Uma linha '
       + N'por gasto real, com quem pagou identificado - e esse o proposito da base: dar '
       + N'transparencia sobre a divisao das despesas da casa. Origem: aba do Google '
       + N'Sheets publicada como CSV, e nao de arquivo, como as origens bancarias. '
       + N'Alimenta gold.fato_familia, separado do fato pessoal.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', NULL, @d;

SET @d = N'Chave substituta do lancamento. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'sk_movimentacao', @d;

SET @d = N'Data do gasto. Ha lancamentos com data futura - sao parcelas a vencer, que vao '
       + N'ate 2031. Filtre por data ate hoje para ver so o que ja aconteceu.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'dt_lancamento', @d;

SET @d = N'Data do pagamento efetivo, quando difere da data do gasto.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'dt_pagamento', @d;

SET @d = N'Descricao do gasto, escrita a mao. Preservada para auditoria.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_descricao', @d;

SET @d = N'METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. '
       + N'Vem de "Valor Trat" da planilha, ja convertido do formato brasileiro - a origem '
       + N'entrega texto como "1.234,56" e negativo entre parenteses.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'vl_transacao', @d;

SET @d = N'DESPESA ou RECEITA, com a grafia unificada. A origem trazia quatro variacoes de '
       + N'caixa para a mesma palavra.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'CLASSIFICACAO nivel 1: GASTOS ESSENCIAIS, ESTILO DE VIDA ou RECEITA.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2, o principal para analise. Compartilha o vocabulario das '
       + N'origens pessoais em dez categorias (ALIMENTACAO, TRANSPORTE, LAZER...), e tem '
       + N'oito proprias da familia - MORADIA, DIARISTA, HOSPEDAGEM, INTERNET e outras. '
       + N'Compartilhar a dimensao com o fato pessoal permite comparar os dois pela mesma '
       + N'categoria.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO nivel 3, o mais fino: "Aluguel", "IPTU", "Reforma", "Manutencao".';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_grupo', @d;

SET @d = N'Marca 1 quando o lancamento tem categoria vinda da planilha.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'fl_classificado', @d;

SET @d = N'QUEM PAGOU, com a grafia unificada. Vale ALE, LIA, Conta (quando saiu da conta '
       + N'conjunta) ou o nome de um terceiro. E o eixo da transparencia que motiva esta '
       + N'base: somar por esta coluna responde quanto cada um bancou.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_pessoa_pagar', @d;

SET @d = N'Estabelecimento ou pessoa que recebeu. Mais de 400 valores distintos.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_pessoa_receber', @d;
SET @d = N'Forma de pagamento: C para credito, D para debito, entre outras.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_forma_pgto', @d;
SET @d = N'Descricao da forma de pagamento, indicando o cartao ou conta usada.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_descricao_pgto', @d;
SET @d = N'Cidade do gasto, preenchida na quase totalidade dos lancamentos.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_cidade', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_uf', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_pais', @d;
SET @d = N'Observacao livre, usada para marcar contexto como viagens.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'ds_obs', @d;

SET @d = N'Marca 1 quando a planilha registra o gasto como pago. Permite separar o que ja '
       + N'saiu do bolso do que esta comprometido - relevante porque ha parcelas com '
       + N'vencimento ate 2031.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'fl_pago', @d;

SET @d = N'ALERTA DE QUALIDADE. Marca 1 quando o sinal do valor contradiz o tipo '
       + N'declarado - uma despesa com valor positivo, por exemplo. Acontece quando o '
       + N'valor e digitado ja negativo na planilha e a formula "Valor Trat = -Valor" o '
       + N'inverte, transformando despesa em receita. Foi assim que cinco reformas '
       + N'apareceram como receita, um desvio de R$ 7.194. Revisar periodicamente os '
       + N'lancamentos marcados.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'fl_sinal_divergente', @d;

SET @d = N'Identidade do evento, herdada da bronze.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'familia_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'familia_movimentacao' ORDER BY 1;
GO
