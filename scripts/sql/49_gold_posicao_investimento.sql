/* =============================================================
   manzo-dados | 49 - Camada Gold: posição da carteira
   -------------------------------------------------------------
   gold.fato_posicao_investimento

   O SEGUNDO FATO DE INVESTIMENTO, e o que faltava. O
   fato_investimento guarda FLUXO - dividendo, IR, taxa, operação -
   e responde "quanto se movimentou". Este guarda POSIÇÃO e
   responde "quanto se tem". São perguntas diferentes e por isso
   são fatos diferentes: o grão de um é o evento, o do outro é o
   ativo numa data.

   GRÃO: (SK_DATA, SK_ATIVO_ORIGEM). Uma linha por ativo por foto.
   Carregado todo dia, vira série de patrimônio.

   -------------------------------------------------------------
   SK_ATIVO VEM COM LACUNA, E ELA É DECLARADA
   -------------------------------------------------------------
   Dos 63 ativos da primeira carga, só 27 casam com gold.dim_ativo
   por código ou nome exato. Os 36 restantes - R$ 61.771,03, 59% do
   patrimônio - entram com SK_ATIVO = -1.

   NÃO É DESLEIXO, É RECUSA A ADIVINHAR. A dim_ativo nasceu do
   extrato, que chama os ativos por nome; a Pluggy identifica fundo
   por CNPJ e renda fixa por código do papel. O mesmo ativo existe
   dos dois lados com nomes diferentes:

       extrato            Pluggy
       LCA BANCO BV S/A   LCA - BANCO VOTORANTIM S.A.
       Valora CRI         Valora CRI CDI Renda+ FII RL

   Casar por semelhança de texto foi testado e REPROVADO. O mesmo
   algoritmo que acerta "CDB BANCO DIGIMAIS" com 1,00 dá 0,79 para
   "CDB - BANCO BMG S.A" contra "LCA BANCO BV S/A" - dois bancos
   diferentes, dois papéis diferentes, uma pontuação alta. E 0,62
   para "NTN-B" contra "BTC RENT". Palpite errado aqui soma
   patrimônio de um ativo no outro, e ninguém revisa um número que
   parece plausível.

   O de-para entra quando houver lista revisada, como o das
   categorias do Itaú. Até lá, CD_ATIVO_ORIGEM e NM_ATIVO_ORIGEM
   guardam como a Pluggy chamou cada um, que é o que torna a
   revisão possível depois sem recarregar nada.

   O TOTAL NÃO DEPENDE DISSO. Patrimônio, rentabilidade e alocação
   por tipo saem corretos hoje; o que fica incompleto é cruzar
   posição com fluxo POR ATIVO.

   -------------------------------------------------------------
   POSIÇÃO ENCERRADA ENTRA
   -------------------------------------------------------------
   16 dos 63 estão em TOTAL_WITHDRAWAL, com quantidade e saldo zero
   - FIIs que saíram da carteira e direitos de subscrição já
   exercidos (HGLG12, MXRF12, TRXF12 são recibos, não os FIIs).
   Entram porque somar zero não altera patrimônio e a linha registra
   quando o ativo saiu. Para a carteira viva, filtre
   DS_SITUACAO = 'ACTIVE'.

   Pré-requisitos: 48_bronze_xp_posicao.sql, 04_gold_investimentos.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('gold.fato_posicao_investimento') IS NULL
BEGIN
    CREATE TABLE gold.fato_posicao_investimento (
        SK_POSICAO        bigint IDENTITY(1,1) NOT NULL,
        SK_DATA           int          NOT NULL,
        SK_ORIGEM         int          NOT NULL,
        SK_ATIVO          int          NOT NULL,

        -- como a origem chamou o ativo. É o que permite o de-para
        -- depois, sem recarregar.
        CD_ATIVO_ORIGEM   varchar(60)  NULL,
        NM_ATIVO_ORIGEM   varchar(300) NOT NULL,

        DS_TIPO           varchar(40)  NOT NULL,
        DS_SUBTIPO        varchar(60)  NULL,
        DS_SITUACAO       varchar(30)  NULL,

        QT_COTAS          decimal(24,8) NULL,
        VL_COTA           decimal(24,8) NULL,
        VL_BRUTO          decimal(18,2) NULL,
        VL_LIQUIDO        decimal(18,2) NULL,
        VL_RESGATAVEL     decimal(18,2) NULL,
        VL_APLICADO       decimal(18,2) NULL,
        VL_TAXAS          decimal(18,2) NULL,

        DT_REFERENCIA     date         NULL,
        DT_VENCIMENTO     date         NULL,

        HASH_NEGOCIO      char(64)     NOT NULL,
        DT_CARGA          datetime2(3) NOT NULL
            CONSTRAINT DF_fato_posicao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_posicao_investimento PRIMARY KEY (SK_POSICAO),
        CONSTRAINT UQ_fato_posicao_investimento UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_fato_posicao_data FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_posicao_origem FOREIGN KEY (SK_ORIGEM)
            REFERENCES gold.dim_origem (SK_ORIGEM),
        CONSTRAINT FK_fato_posicao_ativo FOREIGN KEY (SK_ATIVO)
            REFERENCES gold.dim_ativo (SK_ATIVO)
    );

    CREATE INDEX IX_fato_posicao_data ON gold.fato_posicao_investimento (SK_DATA);
    CREATE INDEX IX_fato_posicao_ativo ON gold.fato_posicao_investimento (SK_ATIVO);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Posicao da carteira: um ativo por data de foto. '
       + N'E O PAR DO fato_investimento, nao o substituto. Aquele guarda FLUXO (dividendo, '
       + N'IR, taxa, operacao) e responde "quanto se movimentou"; este guarda POSICAO e '
       + N'responde "quanto se tem". Grao diferente, pergunta diferente. '
       + N'ORIGEM: API da Pluggy (Open Finance), carregada por carga_gold_posicao.py a partir '
       + N'de bronze.xp_posicao. '
       + N'ATENCAO AO SK_ATIVO: so 27 dos 63 ativos casam com dim_ativo hoje; os demais entram '
       + N'com -1 porque a dim nasceu do extrato (nomes) e a Pluggy identifica fundo por CNPJ '
       + N'e renda fixa por codigo do papel. Patrimonio e alocacao saem certos; o que fica '
       + N'incompleto e cruzar posicao com fluxo POR ATIVO. Ver CD_ATIVO_ORIGEM.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', NULL, @d;

SET @d = N'Chave substituta da linha.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'SK_POSICAO', @d;
SET @d = N'Chave para gold.dim_calendario: a data da FOTO - quando a Pluggy atualizou a '
       + N'conexao, igual para toda a leitura. Nao confundir com DT_REFERENCIA, que e por ativo.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_origem. Hoje sempre XP Investimentos.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'SK_ORIGEM', @d;
SET @d = N'Chave para gold.dim_ativo. -1 quando o ativo da Pluggy nao casou com nenhum membro '
       + N'da dimensao - 36 dos 63 na primeira carga, 59% do patrimonio. Casar por semelhanca '
       + N'de texto foi testado e recusado: o algoritmo da 0,79 para "CDB - BANCO BMG S.A" '
       + N'contra "LCA BANCO BV S/A", bancos e papeis diferentes. O de-para entra quando houver '
       + N'lista revisada.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'SK_ATIVO', @d;
SET @d = N'Codigo do ativo como a Pluggy devolveu: ticker para acao e FII, CNPJ para fundo, '
       + N'codigo do papel para renda fixa. E o que torna o de-para possivel depois sem '
       + N'recarregar.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'CD_ATIVO_ORIGEM', @d;
SET @d = N'Nome do ativo como a Pluggy devolveu. Use este para ler enquanto SK_ATIVO for -1.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'NM_ATIVO_ORIGEM', @d;
SET @d = N'EQUITY, FIXED_INCOME ou MUTUAL_FUND, como a API classifica.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DS_TIPO', @d;
SET @d = N'STOCK, REAL_ESTATE_FUND, TREASURY, CDB, LCA, MULTIMARKET_FUND, INVESTMENT_FUND...';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DS_SUBTIPO', @d;
SET @d = N'ACTIVE, PENDING ou TOTAL_WITHDRAWAL. Posicao encerrada permanece com saldo zero: '
       + N'somar zero nao altera patrimonio e a linha registra quando o ativo saiu. Para a '
       + N'carteira viva, filtre ACTIVE.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DS_SITUACAO', @d;
SET @d = N'Quantidade de cotas ou papeis na data da foto.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'QT_COTAS', @d;
SET @d = N'Valor unitario da cota.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_COTA', @d;
SET @d = N'Valor bruto da posicao, antes de impostos.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_BRUTO', @d;
SET @d = N'Saldo LIQUIDO, depois de taxas e impostos. E A METRICA DE PATRIMONIO - some esta, '
       + N'nao a bruta.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_LIQUIDO', @d;
SET @d = N'Quanto estaria disponivel para resgate na data.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_RESGATAVEL', @d;
SET @d = N'Valor originalmente aplicado. SO VEM EM RENDA FIXA - 12 dos 63 na primeira carga, e '
       + N'nenhum dos 35 de renda variavel. NAO serve de custo de aquisicao para acao e FII: '
       + N'para esses o custo so sai das transacoes de compra, e so na janela de 12 meses que '
       + N'o Open Finance alcanca.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_APLICADO', @d;
SET @d = N'Impostos provisionados sobre a posicao.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'VL_TAXAS', @d;
SET @d = N'A data que a API traz em CADA ativo - o dia em que aquela posicao foi confirmada. '
       + N'Diz a IDADE DO PRECO. Numa mesma foto vieram tres datas diferentes; para somar '
       + N'patrimonio use SK_DATA.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DT_REFERENCIA', @d;
SET @d = N'Vencimento do papel. Renda fixa.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DT_VENCIMENTO', @d;
SET @d = N'SHA-256 do id do investimento na Pluggy + data da foto. Torna a carga idempotente.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando a linha entrou.';
EXEC dbo.sp_documenta 'gold', 'fato_posicao_investimento', 'DT_CARGA', @d;
GO

SELECT 'tabela existe' AS conferencia,
       CASE WHEN OBJECT_ID('gold.fato_posicao_investimento') IS NOT NULL
            THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'colunas',
    CAST((SELECT COUNT(*) FROM sys.columns
           WHERE object_id = OBJECT_ID('gold.fato_posicao_investimento')) AS varchar(10))
UNION ALL SELECT 'documentadas',
    CAST((SELECT COUNT(*) FROM sys.extended_properties
           WHERE class = 1 AND major_id = OBJECT_ID('gold.fato_posicao_investimento')
             AND minor_id > 0 AND name = 'MS_Description') AS varchar(10))
UNION ALL SELECT 'chaves estrangeiras',
    CAST((SELECT COUNT(*) FROM sys.foreign_keys
           WHERE parent_object_id = OBJECT_ID('gold.fato_posicao_investimento')) AS varchar(10))
UNION ALL SELECT 'linhas',
    CAST((SELECT COUNT(*) FROM gold.fato_posicao_investimento) AS varchar(10));
GO
