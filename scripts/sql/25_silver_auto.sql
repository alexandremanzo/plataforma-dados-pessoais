/* =============================================================
   manzo-dados | 25 - Camada Silver: manutencao do automovel
   -------------------------------------------------------------
   silver.auto_manutencao + silver.auto_intervalo_troca

   Manutencoes tipadas, com o vocabulario unificado e a visita a
   oficina identificada.

   O QUE ESTA CAMADA ACRESCENTA:

   - NR_VISITA, o numero sequencial da ida a oficina POR VEICULO.
     Uma visita rende varias linhas - pecas e mao de obra - e a
     pergunta "quanto custou aquela revisao" precisa agrupar por
     visita, nao por data solta.

   - FL_PREVENTIVA, derivada da natureza declarada na origem.
     Separa o que foi programado do que quebrou, que e a distincao
     que decide se o gasto era evitavel.

   - FL_TEM_INTERVALO, que marca as categorias com troca prevista
     por quilometragem. So 13 das 34 tem, e as outras 21 nao sao
     omissao: nao se troca mao de obra nem lampada queimada por
     rodagem.

   O que se unifica: "Mão de Obra" e "Mão de obra" convivem na
   origem e viravam duas categorias na dimensao.

   Pre-requisitos: 00, 01, 24
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.auto_intervalo_troca') IS NULL
BEGIN
    CREATE TABLE silver.auto_intervalo_troca (
        sk_intervalo   int IDENTITY(1,1) NOT NULL,
        ds_categoria   varchar(100) NOT NULL,
        nr_intervalo_km int         NULL,
        hash_negocio   char(64)     NOT NULL,
        dt_carga       datetime2(3) NOT NULL
            CONSTRAINT DF_silver_intervalo_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_silver_auto_intervalo PRIMARY KEY CLUSTERED (sk_intervalo),
        CONSTRAINT UQ_silver_auto_intervalo_hash UNIQUE (hash_negocio),
        CONSTRAINT UQ_silver_auto_intervalo_cat UNIQUE (ds_categoria)
    );
END
GO

IF OBJECT_ID('silver.auto_manutencao') IS NULL
BEGIN
    CREATE TABLE silver.auto_manutencao (
        sk_manutencao     int IDENTITY(1,1) NOT NULL,

        dt_manutencao     date          NOT NULL,
        nm_veiculo        varchar(60)   NOT NULL,
        nr_visita         int           NOT NULL,
        nr_km             int           NULL,

        ds_natureza       varchar(30)   NULL,
        fl_preventiva     bit           NOT NULL,
        ds_tipo           varchar(30)   NULL,
        ds_item           varchar(200)  NULL,
        ds_categoria      varchar(100)  NOT NULL,
        fl_tem_intervalo  bit           NOT NULL,

        nr_quantidade     decimal(10,2) NULL,
        vl_gasto          decimal(12,2) NULL,
        ds_local          varchar(120)  NULL,
        ds_observacao     varchar(500)  NULL,

        hash_negocio      char(64)      NOT NULL,
        dt_carga          datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_auto_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_auto_manutencao PRIMARY KEY CLUSTERED (sk_manutencao),
        CONSTRAINT UQ_silver_auto_manutencao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_auto_data      ON silver.auto_manutencao (dt_manutencao);
    CREATE INDEX IX_silver_auto_veiculo   ON silver.auto_manutencao (nm_veiculo);
    CREATE INDEX IX_silver_auto_categoria ON silver.auto_manutencao (ds_categoria);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Intervalo recomendado de troca por categoria, em quilometros, tipado. '
       + N'Tabela de referencia, e nao de eventos: uma linha por categoria. Cruzada com o '
       + N'historico, responde o que esta vencendo em cada veiculo.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', NULL, @d;
SET @d = N'Chave substituta do intervalo.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', 'sk_intervalo', @d;
SET @d = N'Categoria de manutencao, com a grafia unificada - a mesma de '
       + N'silver.auto_manutencao.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', 'ds_categoria', @d;
SET @d = N'Quilometros entre trocas: 5.000 para oleo, 10.000 para filtro e alinhamento, '
       + N'50.000 para amortecedor e correia.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', 'nr_intervalo_km', @d;
SET @d = N'Identidade, herdada da bronze.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'auto_intervalo_troca', 'dt_carga', @d;

SET @d = N'SILVER | Revisoes e manutencoes do automovel, limpas e tipadas. Uma linha por '
       + N'item de cada visita a oficina. DOIS VEICULOS com hodometros independentes: o '
       + N'Sedan ate novembro de 2025 e o SUV desde entao. Nunca compare ou some '
       + N'quilometragem entre eles. Alimenta gold.fato_manutencao_auto.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', NULL, @d;

SET @d = N'Chave substituta do lancamento. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'sk_manutencao', @d;
SET @d = N'Data da ida a oficina.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'dt_manutencao', @d;
SET @d = N'Veiculo: Sedan ou SUV.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'nm_veiculo', @d;
SET @d = N'Numero sequencial da visita a oficina, contado POR VEICULO. Uma visita rende '
       + N'varias linhas - pecas e mao de obra na mesma nota - e esta coluna permite somar '
       + N'"quanto custou aquela revisao" sem agrupar por data solta.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'nr_visita', @d;
SET @d = N'Quilometragem do veiculo na data. E O EIXO DA MANUTENCAO PREVENTIVA: desgaste '
       + N'se mede em rodagem, nao em calendario. Cada veiculo tem sua propria escala.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'nr_km', @d;
SET @d = N'Natureza declarada na origem: Revisão (programada) ou Manutenção (conserto).';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_natureza', @d;
SET @d = N'1 quando foi manutencao programada, 0 quando foi conserto. Separa o gasto que se '
       + N'planeja do que aparece - a proporcao entre os dois diz se a manutencao esta '
       + N'sendo preventiva de fato ou so reagindo a quebra.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'fl_preventiva', @d;
SET @d = N'Produto (peca) ou Serviço (mao de obra).';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_tipo', @d;
SET @d = N'Descricao do item ou servico, preservada para auditoria. Texto livre, com 110 '
       + N'variacoes - use ds_categoria para analisar.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_item', @d;
SET @d = N'CLASSIFICACAO em 34 categorias, com a grafia unificada: a origem trazia '
       + N'"Mão de Obra" e "Mão de obra" como se fossem duas.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_categoria', @d;
SET @d = N'1 quando a categoria tem intervalo de troca definido em quilometros e portanto '
       + N'entra na previsao de vencimento. As 21 categorias sem intervalo sao corretivas - '
       + N'nao se troca bandeja, lampada ou mao de obra por rodagem.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'fl_tem_intervalo', @d;
SET @d = N'Quantidade de unidades do item.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'nr_quantidade', @d;
SET @d = N'METRICA. Valor pago em reais, total do item. Positivo: e sempre despesa, entao '
       + N'nao carrega sinal como os fatos financeiros.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'vl_gasto', @d;
SET @d = N'Oficina ou loja onde foi feito.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_local', @d;
SET @d = N'Observacao livre da origem.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'ds_observacao', @d;
SET @d = N'Identidade do evento, herdada da bronze.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'auto_manutencao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('auto_manutencao', 'auto_intervalo_troca')
  AND s.name = 'silver' ORDER BY 1;
GO
