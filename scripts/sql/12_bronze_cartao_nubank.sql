/* =============================================================
   manzo-dados | 12 - Camada Bronze: cartao de credito Nubank
   -------------------------------------------------------------
   bronze.cartao_nubank

   Cartao encerrado, usado de 2018 a 2022. Emenda exatamente onde o
   cartao XP comeca (05/2022), fechando a serie de consumo.

   TRES DIFERENCAS EM RELACAO AO CARTAO XP, todas verificadas nos
   dados e nao supostas:

   1. O SINAL E INVERTIDO. No Nubank o gasto e POSITIVO e o credito
      e negativo - o oposto da convencao do XP. A silver inverte para
      que as duas origens possam ser somadas.

   2. OS PAGAMENTOS DA FATURA ESTAO DENTRO DA PLANILHA DO CARTAO.
      Sao 48 linhas "Pagamento recebido" que anulavam os gastos: a
      soma bruta de 2.345 lancamentos dava apenas R$ 2.310, quando os
      gastos reais somam R$ 122.081. A coluna "Extrato" as separa com
      precisao - vale N nessas 48 linhas e S em todas as outras. Por
      isso FL_EXTRATO virou o discriminador de nivel: pagamento de
      fatura e lancamento SINTETICO, gasto e ANALITICO.

   3. A CLASSIFICACAO MANUAL PRATICAMENTE NAO EXISTE - apenas 2,1%
      dos lancamentos tem categoria preenchida. Em compensacao, o
      proprio Nubank categoriza 91% deles em 12 categorias
      (restaurante, transporte, supermercado...), preservadas em
      DS_CATEGORIA_NUBANK. O de-para dessas 12 para o seu vocabulario
      resolve a origem inteira com pouquissimo trabalho manual.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.cartao_nubank') IS NULL
BEGIN
    CREATE TABLE bronze.cartao_nubank (
        id_movimentacao       int IDENTITY(1,1) NOT NULL,

        ds_data               varchar(50)   NULL,
        ds_titulo             varchar(1000) NULL,
        ds_categoria_nubank   varchar(60)   NULL,
        ds_valor              varchar(50)   NULL,
        ds_data_fatura        varchar(50)   NULL,
        ds_tipo_movimentacao  varchar(50)   NULL,

        fl_extrato            varchar(5)    NULL,
        fl_rewards            varchar(5)    NULL,
        ds_arquivo_fatura     varchar(120)  NULL,

        ds_area               varchar(100)  NULL,
        ds_categoria          varchar(100)  NULL,
        ds_grupo              varchar(100)  NULL,
        ds_pessoa_pagar       varchar(100)  NULL,
        ds_pessoa_receber     varchar(200)  NULL,
        ds_cidade             varchar(100)  NULL,
        ds_uf                 varchar(20)   NULL,
        ds_pais               varchar(60)   NULL,
        ds_obs                varchar(1000) NULL,
        ds_projeto            varchar(100)  NULL,
        ds_tag                varchar(100)  NULL,

        nr_ocorrencia         int           NOT NULL,
        hash_negocio          char(64)      NOT NULL,
        nm_arquivo_origem     varchar(260)  NOT NULL,
        nm_aba_origem         varchar(120)  NOT NULL,
        nr_linha_arquivo      int           NULL,
        dt_carga              datetime2(3)  NOT NULL
            CONSTRAINT DF_cartao_nubank_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_cartao_nubank PRIMARY KEY CLUSTERED (id_movimentacao),
        CONSTRAINT UQ_cartao_nubank_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_cartao_nubank_data   ON bronze.cartao_nubank (ds_data);
    CREATE INDEX IX_cartao_nubank_fatura ON bronze.cartao_nubank (ds_data_fatura);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Gastos do cartao Nubank, de 2018 a 2022, quando o cartao foi '
       + N'encerrado. Vem da aba cad-credito de dados-nunbank-completo.xlsx. Emenda a '
       + N'serie do cartao XP, que comeca em 05/2022. ATENCAO: o sinal aqui e invertido '
       + N'em relacao ao XP (gasto e positivo) e os pagamentos de fatura estao misturados '
       + N'aos gastos - a coluna FL_EXTRATO os separa.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'id_movimentacao', @d;

SET @d = N'Data da compra, em formato ISO como texto.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_data', @d;

SET @d = N'Descricao do lancamento como o Nubank a gera: nome do estabelecimento '
       + N'("Durango Burger", "Ebanx Alipay") ou o tipo de evento ("Pagamento recebido", '
       + N'"Estorno de ...", "Rewards - Credito de compra apagada").';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_titulo', @d;

SET @d = N'Categoria atribuida pelo PROPRIO NUBANK, nao por voce: restaurante, transporte, '
       + N'servicos, supermercado, vestuario, viagem, casa, eletronicos, lazer, educacao, '
       + N'saude e outros. Preenchida em 91% dos lancamentos, contra 2% da classificacao '
       + N'manual - por isso e a base do de-para desta origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_categoria_nubank', @d;

SET @d = N'Valor do lancamento como veio da origem. SINAL INVERTIDO em relacao ao cartao '
       + N'XP: aqui gasto e POSITIVO e credito e negativo. A silver inverte para unificar '
       + N'as duas origens.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_valor', @d;

SET @d = N'Data de vencimento da fatura em que o lancamento foi cobrado. Sao 49 faturas.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_data_fatura', @d;

SET @d = N'Natureza informada na planilha: Despesa ou Receita. NAO e confiavel como '
       + N'indicador de sinal - ha 112 linhas marcadas Despesa com valor negativo, que sao '
       + N'pagamentos de fatura, estornos e creditos de rewards.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_tipo_movimentacao', @d;

SET @d = N'DISCRIMINADOR DE NIVEL. Vale N nas 48 linhas de "Pagamento recebido" - o '
       + N'pagamento da fatura, que e lancamento SINTETICO - e S nos 2.297 lancamentos de '
       + N'consumo, que sao ANALITICOS. Separa com precisao o que somar e o que nao somar: '
       + N'sem esse filtro, os pagamentos anulam os gastos e a soma de 4 anos de cartao da '
       + N'R$ 2.310 em vez de R$ 122.081.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'fl_extrato', @d;

SET @d = N'Marca S quando o lancamento e do programa de pontos (credito de compra apagada '
       + N'com Rewards). Sao 94 lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'fl_rewards', @d;

SET @d = N'LINHAGEM DA ORIGEM: nome do CSV de fatura de onde a linha veio '
       + N'("nubank-2018-06.csv"). Sao 49 arquivos, um por fatura, e essa rastreabilidade '
       + N'ja existia na planilha - foi preservada.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_arquivo_fatura', @d;

SET @d = N'CLASSIFICACAO MANUAL nivel 1. Preenchida em apenas 2,2% dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_area', @d;
SET @d = N'CLASSIFICACAO MANUAL nivel 2. Preenchida em apenas 2,1% dos lancamentos - por '
       + N'isso esta origem depende do de-para das categorias do Nubank.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_categoria', @d;
SET @d = N'CLASSIFICACAO MANUAL nivel 3. Preenchida em apenas 2,1% dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_grupo', @d;
SET @d = N'Quem pagou, na anotacao manual.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_pessoa_pagar', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu, na anotacao manual.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_pessoa_receber', @d;
SET @d = N'Cidade do gasto, quando anotada.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_cidade', @d;
SET @d = N'UF do gasto, quando anotada.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_uf', @d;
SET @d = N'Pais do gasto, quando anotado.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_pais', @d;
SET @d = N'Observacao livre.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_obs', @d;
SET @d = N'Projeto vinculado ao gasto. Praticamente nao utilizado.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_projeto', @d;
SET @d = N'Marcador livre, fora da hierarquia de categoria.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'ds_tag', @d;

SET @d = N'Numero da ocorrencia da mesma combinacao de data, titulo, valor e fatura. '
       + N'Necessario porque o cartao nao tem saldo corrente para desempatar compras '
       + N'identicas no mesmo dia.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'nr_ocorrencia', @d;
SET @d = N'IDENTIDADE DO EVENTO. SHA-256 de data + titulo normalizado + valor + data da '
       + N'fatura + numero da ocorrencia. Com constraint UNIQUE.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'hash_negocio', @d;
SET @d = N'LINHAGEM: arquivo de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'nm_aba_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o evento entrou na base.';
EXEC dbo.sp_documenta 'bronze', 'cartao_nubank', 'dt_carga', @d;
GO


/* -------------------------------------------------------------
   De-para das categorias do Nubank para o seu vocabulario
   ------------------------------------------------------------- */

IF OBJECT_ID('silver.de_para_categoria_nubank') IS NULL
BEGIN
    CREATE TABLE silver.de_para_categoria_nubank (
        ds_categoria_nubank varchar(60)  NOT NULL,
        ds_area             varchar(100) NULL,
        ds_categoria        varchar(100) NULL,
        ds_grupo            varchar(100) NULL,
        nr_lancamentos      int          NULL,
        dt_carga            datetime2(3) NOT NULL
            CONSTRAINT DF_de_para_nubank_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_de_para_categoria_nubank PRIMARY KEY (ds_categoria_nubank)
    );
END
GO

/* Nova declaracao: variaveis nao sobrevivem ao GO que separa os lotes. */
DECLARE @d nvarchar(3750);

SET @d = N'SILVER | De-para das 12 categorias do proprio Nubank para o vocabulario usado '
       + N'nas demais origens. Existe porque o cartao Nubank tem apenas 2% de '
       + N'classificacao manual, mas 91% de categorizacao feita pelo banco: mapear 12 '
       + N'linhas resolve 2.135 lancamentos. Enquanto uma categoria nao for mapeada, os '
       + N'lancamentos dela ficam como "A classificar".';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', NULL, @d;

SET @d = N'Categoria como o Nubank a atribuiu: restaurante, transporte, supermercado, '
       + N'servicos, vestuario, viagem, casa, eletronicos, lazer, educacao, saude, outros.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'ds_categoria_nubank', @d;
SET @d = N'Area correspondente no seu vocabulario. Nulo enquanto nao mapeada.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'ds_area', @d;
SET @d = N'Categoria correspondente no seu vocabulario. Nulo enquanto nao mapeada.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'ds_categoria', @d;
SET @d = N'Grupo correspondente no seu vocabulario. Nulo enquanto nao mapeado.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'ds_grupo', @d;
SET @d = N'Quantos lancamentos do cartao usam esta categoria. Serve para priorizar.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'nr_lancamentos', @d;
SET @d = N'LINHAGEM: quando o mapeamento entrou na tabela.';
EXEC dbo.sp_documenta 'silver', 'de_para_categoria_nubank', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('cartao_nubank', 'de_para_categoria_nubank') ORDER BY 1;
GO
