/* =============================================================
   manzo-dados | 48 - Camada Bronze: posição da carteira XP
   -------------------------------------------------------------
   bronze.xp_posicao

   O que o DW nunca teve. gold.fato_investimento guarda 1.388
   eventos de FLUXO - dividendo, IR, taxa, operação - e nenhuma
   POSIÇÃO: dá para saber quanto se movimentou, nunca quanto se tem.
   Esta tabela fecha isso: 63 ativos, R$ 104,6 mil, um registro por
   ativo por data de referência.

   ORIGEM: API da Pluggy (conector MeuPluggy, Open Finance), e não
   o extrato em xlsx. São fontes COMPLEMENTARES, não substitutas -
   a comparação na janela comum mostrou por quê:

       extrato  546 eventos  Dividendo 144 · Taxa 132 · IR 53 ...
       API      396 eventos  BUY 238 · SELL 154 · INTEREST 4

   A API entrega NEGOCIAÇÃO POR ATIVO; o extrato entrega FLUXO DE
   CAIXA DA CONTA. E a API só alcança 12 meses, o padrão do Open
   Finance: 2.081 dos 2.627 eventos do extrato são anteriores a
   isso e nunca virão por ali. O download manual continua.

   O GRÃO É (ativo, dt_snapshot). Carregada todo dia, a tabela vira
   série histórica de carteira; carregar duas vezes no mesmo dia não
   duplica, porque o hash cobre as duas colunas.

   DUAS DATAS, E A DIFERENÇA CUSTOU UMA CARGA ERRADA. A primeira
   versão usava a data que a API traz em cada investimento como data
   da foto. Está errado: a API data CADA ATIVO por conta própria,
   com o dia em que aquela posição foi confirmada. Na primeira carga
   real vieram três datas - 35 ativos em 13/10, 12 em 14/10 e 16 em
   15/10 - e somar patrimônio por ela partia UMA foto em três, cada
   uma com um pedaço do dinheiro.

       dt_snapshot     quando a Pluggy atualizou a conexão. Igual
                       para toda a leitura. É POR ELA que se soma
                       patrimônio.
       dt_referencia   a data daquele ativo, como veio. Atributo:
                       diz a idade do preço, não a da foto.

   ATIVO ZERADO VEM JUNTO. Dos 63 da primeira carga, 16 estão em
   TOTAL_WITHDRAWAL com quantidade e saldo zero - posições encerradas
   (KNRI11, HGLG12, MXRF12...). Entram de propósito: some-las do
   patrimônio é somar zero, e tê-las permite saber quando cada uma
   saiu. Quem quer a carteira viva filtra ds_situacao = 'ACTIVE'.

   POR QUE ESTA BRONZE TEM TIPO, E AS OUTRAS NÃO. As demais nascem
   de planilha, onde toda célula é texto e tipar seria inventar. Um
   JSON já chega tipado, e guardar número como texto aqui repetiria
   um erro que este projeto já pagou: a bronze das planilhas guarda
   "300.00" em formato invariante e o modelo é pt-BR, onde o ponto
   é separador de milhar - o mesmo valor virava 30.000, sem aviso.
   Com decimal na origem, esse caminho nem existe.

   DS_PAYLOAD GUARDA O JSON INTEIRO. São 43 campos hoje, dos quais
   10 chegam sempre nulos e outros podem nascer quando a Pluggy
   mudar. As colunas nomeadas cobrem o que se usa; o payload
   garante que nada se perde enquanto ninguém olha.

   Pré-requisitos: 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.xp_posicao') IS NULL
BEGIN
    CREATE TABLE bronze.xp_posicao (
        id_posicao          bigint IDENTITY(1,1) NOT NULL,

        -- identidade
        id_investimento     varchar(60)  NOT NULL,
        id_item             varchar(60)  NOT NULL,
        dt_snapshot         date         NOT NULL,
        dt_referencia       date         NULL,

        -- o ativo
        nm_ativo            varchar(300) NOT NULL,
        cd_ativo            varchar(60)  NULL,
        cd_isin             varchar(30)  NULL,
        ds_tipo             varchar(40)  NOT NULL,
        ds_subtipo          varchar(60)  NULL,
        ds_situacao         varchar(30)  NULL,
        ds_moeda            varchar(10)  NULL,

        -- posição
        qt_cotas            decimal(24,8) NULL,
        vl_cota             decimal(24,8) NULL,
        vl_bruto            decimal(18,2) NULL,   -- amount
        vl_liquido          decimal(18,2) NULL,   -- balance
        vl_resgatavel       decimal(18,2) NULL,   -- amountWithdrawal
        vl_aplicado         decimal(18,2) NULL,   -- amountOriginal, só renda fixa
        vl_taxas            decimal(18,2) NULL,
        vl_taxas2           decimal(18,2) NULL,

        -- renda fixa
        vl_taxa             decimal(12,4) NULL,   -- rate
        ds_tipo_taxa        varchar(40)  NULL,    -- CDI, IPCA...
        ds_periodicidade    varchar(30)  NULL,
        vl_taxa_anual_fixa  decimal(12,4) NULL,
        vl_rentab_12m       decimal(12,4) NULL,
        nm_emissor          varchar(200) NULL,
        cd_emissor_cnpj     varchar(30)  NULL,
        dt_emissao          date         NULL,
        dt_compra           date         NULL,
        dt_vencimento       date         NULL,
        dt_carencia         date         NULL,

        -- o que chegou, inteiro
        ds_payload          nvarchar(max) NULL,

        -- linhagem
        hash_negocio        char(64)     NOT NULL,
        dt_carga            datetime2(3) NOT NULL
            CONSTRAINT DF_xp_posicao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_xp_posicao PRIMARY KEY (id_posicao),
        CONSTRAINT UQ_xp_posicao UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_xp_posicao_data ON bronze.xp_posicao (dt_snapshot);
    CREATE INDEX IX_xp_posicao_ativo ON bronze.xp_posicao (id_investimento, dt_snapshot);
END
GO


DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Posição da carteira XP, um registro por ativo por data de referência, '
       + N'como a API da Pluggy devolveu. '
       + N'E O QUE O DW NAO TINHA: gold.fato_investimento guarda fluxo (dividendo, IR, taxa, '
       + N'operacao) e nenhuma posicao - dava para saber quanto se movimentou, nunca quanto '
       + N'se tem. '
       + N'FONTE COMPLEMENTAR AO EXTRATO, nao substituta. A API entrega negociacao por ativo '
       + N'e alcanca 12 meses (padrao do Open Finance); o extrato entrega fluxo de caixa da '
       + N'conta e cobre desde 2021. Na janela comum sao 396 eventos contra 546, de naturezas '
       + N'diferentes. O download manual do extrato continua necessario. '
       + N'ATENCAO: o consentimento de Open Finance VENCE e a carga para em silencio quando '
       + N'isso acontece.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', NULL, @d;

SET @d = N'Chave tecnica da linha.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'id_posicao', @d;
SET @d = N'Identificador do investimento na Pluggy. Estavel entre cargas, e o que permite '
       + N'seguir o mesmo ativo ao longo do tempo.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'id_investimento', @d;
SET @d = N'Identificador da conexao (item) na Pluggy. Guardado para auditoria: se a conexao '
       + N'for refeita, o id muda e a serie passa a ter duas origens.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'id_item', @d;
SET @d = N'Data da FOTO: quando a Pluggy atualizou a conexao. Igual para toda a leitura, e '
       + N'e por ela que se soma patrimonio. Forma o grao junto com o ativo.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_snapshot', @d;
SET @d = N'A data que a API traz em CADA investimento - o dia em que aquela posicao foi '
       + N'confirmada. NAO e a data da foto: numa mesma leitura vieram tres datas diferentes, '
       + N'e somar patrimonio por aqui parte uma foto em varias. Use dt_snapshot para isso; '
       + N'esta coluna diz a IDADE DO PRECO de cada ativo.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_referencia', @d;
SET @d = N'Nome do ativo como a XP o chama.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'nm_ativo', @d;
SET @d = N'Ticker ou codigo do papel. Veio em 60 dos 63 ativos na primeira carga.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'cd_ativo', @d;
SET @d = N'Codigo ISIN. Veio em 38 dos 63.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'cd_isin', @d;
SET @d = N'EQUITY, FIXED_INCOME ou MUTUAL_FUND.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_tipo', @d;
SET @d = N'Detalhe do tipo: STOCK, REAL_ESTATE_FUND, TREASURY, CDB, LCA, MULTIMARKET_FUND...';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_subtipo', @d;
SET @d = N'ACTIVE, PENDING ou TOTAL_WITHDRAWAL. Posicao encerrada vem com quantidade e '
       + N'saldo ZERO e permanece na tabela de proposito: somar zero nao atrapalha o '
       + N'patrimonio e ter a linha permite saber quando o ativo saiu. Para a carteira viva, '
       + N'filtre ACTIVE - na primeira carga eram 47 ativos vivos de 63 linhas.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_situacao', @d;
SET @d = N'Moeda. BRL em toda a carteira atual.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_moeda', @d;
SET @d = N'Quantidade de cotas ou papeis.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'qt_cotas', @d;
SET @d = N'Valor unitario da cota na data de referencia.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_cota', @d;
SET @d = N'Valor BRUTO da posicao, antes de impostos (campo amount).';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_bruto', @d;
SET @d = N'Saldo LIQUIDO, depois de taxas e impostos (campo balance). E o valor a usar para '
       + N'somar patrimonio.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_liquido', @d;
SET @d = N'Quanto estaria disponivel para resgate.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_resgatavel', @d;
SET @d = N'Valor originalmente aplicado. ATENCAO: so vem em RENDA FIXA - 12 dos 63 ativos na '
       + N'primeira carga, e NENHUM dos 35 de renda variavel. Nao serve de custo de aquisicao '
       + N'para acao e FII; para esses, o custo so sai das transacoes (BUY), e so na janela de '
       + N'12 meses que a API alcanca.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_aplicado', @d;
SET @d = N'Impostos provisionados sobre a posicao.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_taxas', @d;
SET @d = N'Segundo campo de impostos da API (taxes2), sem documentacao de significado. '
       + N'Guardado para nao se perder; nao usar sem conferir.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_taxas2', @d;
SET @d = N'Taxa contratada, em percentual do indexador. Renda fixa.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_taxa', @d;
SET @d = N'Indexador da taxa: CDI, IPCA, PRE. Renda fixa.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_tipo_taxa', @d;
SET @d = N'Periodicidade da taxa (YEARLY, MONTHLY).';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_periodicidade', @d;
SET @d = N'Taxa anual fixa, quando o papel e prefixado.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_taxa_anual_fixa', @d;
SET @d = N'Rentabilidade dos ultimos doze meses, como a instituicao informa. Veio em 12 dos 63.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'vl_rentab_12m', @d;
SET @d = N'Emissor do papel. Renda fixa.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'nm_emissor', @d;
SET @d = N'CNPJ do emissor.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'cd_emissor_cnpj', @d;
SET @d = N'Data de emissao do papel.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_emissao', @d;
SET @d = N'Data da compra. Renda fixa.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_compra', @d;
SET @d = N'Vencimento do papel.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_vencimento', @d;
SET @d = N'Fim da carencia para resgate.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_carencia', @d;
SET @d = N'O JSON inteiro como a API devolveu. Sao 43 campos, dos quais 10 chegam sempre '
       + N'nulos (amountProfit, annualRate, owner, metadata, institution...) e outros podem '
       + N'nascer quando a Pluggy mudar. As colunas nomeadas cobrem o que se usa; isto '
       + N'garante que nada se perca enquanto ninguem olha.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'ds_payload', @d;
SET @d = N'SHA-256 de id_investimento + dt_snapshot. E o que torna a carga idempotente: '
       + N'rodar duas vezes no mesmo dia nao duplica a posicao.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando a linha entrou.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_carga', @d;
GO

SELECT 'bronze.xp_posicao existe' AS conferencia,
       CASE WHEN OBJECT_ID('bronze.xp_posicao') IS NOT NULL THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'colunas',
       CAST((SELECT COUNT(*) FROM sys.columns
              WHERE object_id = OBJECT_ID('bronze.xp_posicao')) AS varchar(10))
UNION ALL SELECT 'documentadas',
       CAST((SELECT COUNT(*) FROM sys.extended_properties
              WHERE class = 1 AND major_id = OBJECT_ID('bronze.xp_posicao')
                AND minor_id > 0 AND name = 'MS_Description') AS varchar(10))
UNION ALL SELECT 'linhas',
       CAST((SELECT COUNT(*) FROM bronze.xp_posicao) AS varchar(10));
GO
