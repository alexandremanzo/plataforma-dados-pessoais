/* =============================================================
   manzo-dados | 04 - Camada Gold: star schema
   -------------------------------------------------------------
   Modelo dimensional consumido pelo Power BI.

   Segue as convencoes de nomenclatura que ja existiam em dbo
   (SK_, NR_, NM_, DS_, VL_, FL_, DT_) para nao criar um segundo
   dialeto no mesmo banco.

   DUAS CORRECOES em relacao ao modelo antigo de dbo:

   1. dim_categoria_investimento e UNICA por nome. No modelo antigo, 7 categorias
      existiam em duplicata (uma linha RECEITA e outra DESPESA para
      o mesmo nome). A carga cruzava por nome, casava com as duas e
      inseria cada lancamento duas vezes - 3.948 linhas de fato para
      2.070 eventos reais.

   2. RECEITA/DESPESA saiu da dimensao e virou atributo do FATO.
      E uma propriedade da transacao (deduzida do sinal do valor),
      nao da categoria: "Margem" pode ser chamada ou estorno.

   O fato tem UNIQUE em HASH_NEGOCIO. Se uma carga futura tentar
   inserir o mesmo evento de novo, o banco recusa - a duplicacao
   deixa de depender de o script estar correto.

   ESCOPO: a gold NAO traz os lancamentos de chamada de margem.
   Sao 1.239 dos 2.500 eventos - metade da base - e representam
   movimentacao operacional de garantia que entra e volta, sem
   efeito patrimonial. Mantidos na silver, que continua sendo o
   registro completo; a lista de exclusao fica em
   scripts/etl/carga_gold_xp.py (CATEGORIAS_EXCLUIDAS).

   Pre-requisitos: 00, 01, 03
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* =============================================================
   1. dim_origem
   ============================================================= */

IF OBJECT_ID('gold.dim_origem') IS NULL
BEGIN
    CREATE TABLE gold.dim_origem (
        SK_ORIGEM       int           NOT NULL,
        CD_ORIGEM       varchar(30)   NOT NULL,
        NM_ORIGEM       varchar(100)  NOT NULL,
        NM_INSTITUICAO  varchar(60)   NOT NULL,
        DS_TIPO_CONTA   varchar(40)   NOT NULL,
        DT_CARGA        datetime2(3)  NOT NULL
            CONSTRAINT DF_dim_origem_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_origem PRIMARY KEY (SK_ORIGEM),
        CONSTRAINT UQ_dim_origem_cd UNIQUE (CD_ORIGEM)
    );
END
GO

MERGE gold.dim_origem AS destino
USING (VALUES
    (-1, 'NAO_INFORMADO', 'Não informado',      'Não informado', 'Não informado'),
    ( 1, 'XP_INVEST',     'XP Investimentos',   'XP',            'Conta de investimento')
) AS fonte (SK_ORIGEM, CD_ORIGEM, NM_ORIGEM, NM_INSTITUICAO, DS_TIPO_CONTA)
   ON destino.SK_ORIGEM = fonte.SK_ORIGEM
WHEN NOT MATCHED THEN
    INSERT (SK_ORIGEM, CD_ORIGEM, NM_ORIGEM, NM_INSTITUICAO, DS_TIPO_CONTA)
    VALUES (fonte.SK_ORIGEM, fonte.CD_ORIGEM, fonte.NM_ORIGEM,
            fonte.NM_INSTITUICAO, fonte.DS_TIPO_CONTA);
GO


/* =============================================================
   2. dim_categoria_investimento
   ============================================================= */

IF OBJECT_ID('gold.dim_categoria_investimento') IS NULL
BEGIN
    CREATE TABLE gold.dim_categoria_investimento (
        SK_CATEGORIA_INVESTIMENTO  int IDENTITY(1,1) NOT NULL,
        NM_CATEGORIA  varchar(100)      NOT NULL,
        DS_GRUPO      varchar(40)       NOT NULL,
        DT_CARGA      datetime2(3)      NOT NULL
            CONSTRAINT DF_dim_categoria_investimento_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_categoria_investimento PRIMARY KEY (SK_CATEGORIA_INVESTIMENTO),
        -- A constraint que faltava no modelo antigo.
        CONSTRAINT UQ_dim_categoria_investimento_nome UNIQUE (NM_CATEGORIA)
    );

    SET IDENTITY_INSERT gold.dim_categoria_investimento ON;
    INSERT INTO gold.dim_categoria_investimento (SK_CATEGORIA_INVESTIMENTO, NM_CATEGORIA, DS_GRUPO)
    VALUES (-1, 'Não informado', 'Não informado');
    SET IDENTITY_INSERT gold.dim_categoria_investimento OFF;
END
GO


/* =============================================================
   3. dim_ativo
   ============================================================= */

IF OBJECT_ID('gold.dim_ativo') IS NULL
BEGIN
    CREATE TABLE gold.dim_ativo (
        SK_ATIVO   int IDENTITY(1,1) NOT NULL,
        CD_ATIVO   varchar(200)      NOT NULL,
        NM_ATIVO   varchar(200)      NULL,
        TP_ATIVO   varchar(40)       NOT NULL,
        DT_CARGA   datetime2(3)      NOT NULL
            CONSTRAINT DF_dim_ativo_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_ativo PRIMARY KEY (SK_ATIVO),
        CONSTRAINT UQ_dim_ativo_cd UNIQUE (CD_ATIVO)
    );

    SET IDENTITY_INSERT gold.dim_ativo ON;
    INSERT INTO gold.dim_ativo (SK_ATIVO, CD_ATIVO, NM_ATIVO, TP_ATIVO)
    VALUES (-1, 'NAO_APLICAVEL', 'Não aplicável', 'Não aplicável');
    SET IDENTITY_INSERT gold.dim_ativo OFF;
END
GO


/* =============================================================
   4. dim_calendario
   Gerada em portugues. A de dbo veio com nomes em ingles
   ("January", "Wednesday"), o que obrigava a traduzir no Power BI.
   ============================================================= */

IF OBJECT_ID('gold.dim_calendario') IS NULL
BEGIN
    CREATE TABLE gold.dim_calendario (
        SK_DATA        int          NOT NULL,   -- formato AAAAMMDD
        DT_DATA        date         NOT NULL,
        NR_ANO         int          NOT NULL,
        NR_MES         int          NOT NULL,
        NM_MES         varchar(20)  NOT NULL,
        NM_MES_ABREV   char(3)      NOT NULL,
        NR_DIA         int          NOT NULL,
        NR_DIA_SEMANA  int          NOT NULL,
        NM_DIA_SEMANA  varchar(20)  NOT NULL,
        NR_TRIMESTRE   int          NOT NULL,
        NR_SEMESTRE    int          NOT NULL,
        NM_ANO_MES     char(7)      NOT NULL,   -- AAAA-MM, para eixo de grafico
        FL_FIM_SEMANA  bit          NOT NULL,
        DT_CARGA       datetime2(3) NOT NULL
            CONSTRAINT DF_dim_calendario_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_calendario PRIMARY KEY (SK_DATA),
        CONSTRAINT UQ_dim_calendario_data UNIQUE (DT_DATA)
    );

    -- Membro para lancamento sem data de liquidacao.
    INSERT INTO gold.dim_calendario
        (SK_DATA, DT_DATA, NR_ANO, NR_MES, NM_MES, NM_MES_ABREV, NR_DIA,
         NR_DIA_SEMANA, NM_DIA_SEMANA, NR_TRIMESTRE, NR_SEMESTRE,
         NM_ANO_MES, FL_FIM_SEMANA)
    VALUES (-1, '1900-01-01', 1900, 1, 'Não informado', 'N/I', 1,
            1, 'Não informado', 1, 1, '1900-01', 0);
END
GO

/* Preenche o calendario de 2005 a 2035.

   O intervalo e fixo e generoso de proposito. Ele precisa cobrir a
   ORIGEM MAIS ANTIGA e o COMPROMISSO MAIS DISTANTE, e os dois extremos
   ja surpreenderam TRES VEZES: a conta do Itau comeca em 2016, a conta
   familia tem parcelas ate 2031, e a avaliacao fisica comeca em MAIO
   DE 2008 - dez anos antes do que o calendario cobria. Cada surpresa
   custou uma carga quebrada por chave estrangeira.

   Dai o inicio em 2005: nao porque exista dado ali, mas porque o
   limite so incomoda quando e apertado. Um intervalo calculado a
   partir do ano atual seria pior ainda, quebrando sozinho com o tempo.

   Sao cerca de 11.300 linhas - custo irrelevante para nao ter esse
   tipo de falha. */
DECLARE @ini date = '2005-01-01',
        @fim date = '2035-12-31';

DECLARE @meses TABLE (n int, nome varchar(20), abrev char(3));
INSERT INTO @meses VALUES
 (1,'Janeiro','Jan'),(2,'Fevereiro','Fev'),(3,'Março','Mar'),(4,'Abril','Abr'),
 (5,'Maio','Mai'),(6,'Junho','Jun'),(7,'Julho','Jul'),(8,'Agosto','Ago'),
 (9,'Setembro','Set'),(10,'Outubro','Out'),(11,'Novembro','Nov'),(12,'Dezembro','Dez');

DECLARE @semana TABLE (n int, nome varchar(20));
INSERT INTO @semana VALUES
 (1,'Domingo'),(2,'Segunda-feira'),(3,'Terça-feira'),(4,'Quarta-feira'),
 (5,'Quinta-feira'),(6,'Sexta-feira'),(7,'Sábado');

;WITH datas AS (
    SELECT @ini AS d
    UNION ALL
    SELECT DATEADD(DAY, 1, d) FROM datas WHERE d < @fim
)
INSERT INTO gold.dim_calendario
    (SK_DATA, DT_DATA, NR_ANO, NR_MES, NM_MES, NM_MES_ABREV, NR_DIA,
     NR_DIA_SEMANA, NM_DIA_SEMANA, NR_TRIMESTRE, NR_SEMESTRE,
     NM_ANO_MES, FL_FIM_SEMANA)
SELECT
    CONVERT(int, FORMAT(d, 'yyyyMMdd')),
    d,
    YEAR(d), MONTH(d), m.nome, m.abrev, DAY(d),
    DATEPART(WEEKDAY, d), s.nome,
    DATEPART(QUARTER, d),
    CASE WHEN MONTH(d) <= 6 THEN 1 ELSE 2 END,
    FORMAT(d, 'yyyy-MM'),
    CASE WHEN DATEPART(WEEKDAY, d) IN (1, 7) THEN 1 ELSE 0 END
FROM datas
JOIN @meses  m ON m.n = MONTH(d)
JOIN @semana s ON s.n = DATEPART(WEEKDAY, d)
WHERE NOT EXISTS (SELECT 1 FROM gold.dim_calendario c WHERE c.DT_DATA = datas.d)
OPTION (MAXRECURSION 0);
GO


/* =============================================================
   5. fato_investimento
   ============================================================= */

IF OBJECT_ID('gold.fato_investimento') IS NULL
BEGIN
    CREATE TABLE gold.fato_investimento (
        SK_LANCAMENTO         int IDENTITY(1,1) NOT NULL,

        SK_ORIGEM             int           NOT NULL,
        SK_DATA_MOVIMENTACAO  int           NOT NULL,
        SK_DATA_LIQUIDACAO    int           NOT NULL,
        SK_ATIVO              int           NOT NULL,
        SK_CATEGORIA_INVESTIMENTO          int           NOT NULL,

        VL_TRANSACAO          decimal(18,2) NULL,
        VL_SALDO_MOMENTO      decimal(18,2) NULL,

        FL_RENDIMENTO         bit           NOT NULL,
        DS_TIPO_FLUXO         varchar(10)   NULL,
        DS_DETALHE_ORIGINAL   varchar(1000) NULL,

        HASH_NEGOCIO          char(64)      NOT NULL,
        DT_CARGA              datetime2(3)  NOT NULL
            CONSTRAINT DF_fato_investimento_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_investimento PRIMARY KEY (SK_LANCAMENTO),
        -- Impede estruturalmente a duplicacao que aconteceu em dbo.
        CONSTRAINT UQ_fato_investimento_hash UNIQUE (HASH_NEGOCIO),

        CONSTRAINT FK_fato_inv_origem      FOREIGN KEY (SK_ORIGEM)
            REFERENCES gold.dim_origem (SK_ORIGEM),
        CONSTRAINT FK_fato_inv_dt_movto    FOREIGN KEY (SK_DATA_MOVIMENTACAO)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_inv_dt_liq      FOREIGN KEY (SK_DATA_LIQUIDACAO)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_inv_ativo       FOREIGN KEY (SK_ATIVO)
            REFERENCES gold.dim_ativo (SK_ATIVO),
        CONSTRAINT FK_fato_inv_categoria_investimento   FOREIGN KEY (SK_CATEGORIA_INVESTIMENTO)
            REFERENCES gold.dim_categoria_investimento (SK_CATEGORIA_INVESTIMENTO)
    );

    CREATE INDEX IX_fato_inv_dt_movto  ON gold.fato_investimento (SK_DATA_MOVIMENTACAO);
    CREATE INDEX IX_fato_inv_categoria_investimento ON gold.fato_investimento (SK_CATEGORIA_INVESTIMENTO);
    CREATE INDEX IX_fato_inv_ativo     ON gold.fato_investimento (SK_ATIVO);
END
GO


/* =============================================================
   6. Documentacao
   ============================================================= */

DECLARE @d nvarchar(3750);

-- dim_origem ---------------------------------------------------
SET @d = N'GOLD | Origem do lancamento: de qual conta ou instituicao o dado veio. '
       + N'Existe para que o mesmo fato receba, no futuro, lancamentos do Itau, do '
       + N'cartao de credito e de outras fontes sem precisar de uma tabela por origem. '
       + N'A chave -1 representa origem nao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', NULL, @d;
SET @d = N'Chave substituta da origem. Valores fixos definidos no script, nao gerados.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'SK_ORIGEM', @d;
SET @d = N'Codigo tecnico e estavel da origem (ex: XP_INVEST). Use em filtros de codigo, '
       + N'nunca o nome, que pode mudar.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'CD_ORIGEM', @d;
SET @d = N'Nome da origem como deve aparecer no relatorio.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'NM_ORIGEM', @d;
SET @d = N'Instituicao financeira responsavel pela conta (XP, Itau, Nubank).';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'NM_INSTITUICAO', @d;
SET @d = N'Natureza da conta: conta de investimento, conta corrente ou cartao de credito. '
       + N'Permite separar patrimonio de fluxo de caixa do dia a dia.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'DS_TIPO_CONTA', @d;
SET @d = N'LINHAGEM: quando o registro foi criado.';
EXEC dbo.sp_documenta 'gold', 'dim_origem', 'DT_CARGA', @d;

-- dim_categoria_investimento ------------------------------------------------
SET @d = N'GOLD | Natureza do lancamento (Dividendo, Compra, IR, Margem...). '
       + N'UMA linha por categoria - a constraint UQ_dim_categoria_investimento_nome garante isso. '
       + N'No modelo antigo de dbo, 7 categorias existiam duplicadas (uma versao RECEITA '
       + N'e outra DESPESA), o que fazia a carga inserir cada lancamento duas vezes. '
       + N'RECEITA/DESPESA agora vive no fato, onde e determinada pelo sinal do valor.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_investimento', NULL, @d;
SET @d = N'Chave substituta da categoria. -1 representa categoria nao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_investimento', 'SK_CATEGORIA_INVESTIMENTO', @d;
SET @d = N'Nome da categoria, unico na tabela. Derivado da descricao do lancamento pelas '
       + N'regras em scripts/etl/regras_xp.py.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_investimento', 'NM_CATEGORIA', @d;
SET @d = N'Agrupador de categorias para leitura no dashboard: Proventos (dividendo, JCP, '
       + N'rendimento), Custos (IR, IOF, taxas, emolumentos), Operação (compra, venda, '
       + N'subscricao), Caixa (transferencia, retirada, aplicacao, resgate) e Outros. '
       + N'Evita graficos com 24 fatias.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_investimento', 'DS_GRUPO', @d;
SET @d = N'LINHAGEM: quando o registro foi criado.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_investimento', 'DT_CARGA', @d;

-- dim_ativo ----------------------------------------------------
SET @d = N'GOLD | Ativo relacionado ao lancamento: acao, FII, CDB, Tesouro, fundo ou COE. '
       + N'A chave -1 ("Nao aplicavel") atende lancamentos sem ativo, como transferencia '
       + N'e taxa de conta - por isso o fato nunca precisa de SK_ATIVO nulo.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', NULL, @d;
SET @d = N'Chave substituta do ativo. -1 = lancamento sem ativo especifico.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'SK_ATIVO', @d;
SET @d = N'Codigo do ativo como extraido da descricao: ticker (PETR4, HGLG11), identificador '
       + N'do CDB, nome do fundo ou do COE. Unico na tabela.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'CD_ATIVO', @d;
SET @d = N'Nome por extenso do ativo, quando conhecido. Hoje repete o codigo; reservado '
       + N'para quando houver uma fonte de cadastro de ativos.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'NM_ATIVO', @d;
SET @d = N'Classe do ativo, deduzida do formato do codigo: Ação, FII, CDB, Tesouro Direto, '
       + N'Fundo, COE, LCA/LCI, Aluguel BTC ou Não classificado. Permite analisar alocacao '
       + N'por classe sem cadastro manual.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'TP_ATIVO', @d;
SET @d = N'LINHAGEM: quando o registro foi criado.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'DT_CARGA', @d;

-- dim_calendario -----------------------------------------------
SET @d = N'GOLD | Dimensao de datas, de 2020 ate o fim do ano seguinte ao atual. '
       + N'Nomes de mes e dia da semana em portugues. Marque-a como Tabela de Datas no '
       + N'Power BI para habilitar inteligencia temporal (acumulado no ano, mesmo periodo '
       + N'do ano anterior). A chave -1 atende lancamento sem data de liquidacao.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', NULL, @d;
SET @d = N'Chave substituta da data no formato AAAAMMDD (ex: 20260702). Inteiro em vez de '
       + N'date porque ocupa menos e ordena naturalmente. -1 = data nao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'SK_DATA', @d;
SET @d = N'A data propriamente dita. E esta coluna que deve ser marcada como a data da '
       + N'tabela de datas no Power BI.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'DT_DATA', @d;
SET @d = N'Ano com 4 digitos.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_ANO', @d;
SET @d = N'Numero do mes (1 a 12). Use para ordenar NM_MES no Power BI.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_MES', @d;
SET @d = N'Nome do mes por extenso em portugues (Janeiro, Fevereiro...).';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_MES', @d;
SET @d = N'Abreviacao do mes com 3 letras (Jan, Fev...), para eixos estreitos.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_MES_ABREV', @d;
SET @d = N'Dia do mes (1 a 31).';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_DIA', @d;
SET @d = N'Dia da semana como numero, 1 = Domingo e 7 = Sabado.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_DIA_SEMANA', @d;
SET @d = N'Nome do dia da semana em portugues.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_DIA_SEMANA', @d;
SET @d = N'Trimestre do ano (1 a 4).';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_TRIMESTRE', @d;
SET @d = N'Semestre do ano (1 ou 2).';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NR_SEMESTRE', @d;
SET @d = N'Ano e mes no formato AAAA-MM. Ordena alfabeticamente na ordem correta, o que '
       + N'resolve o eixo de graficos de serie temporal sem coluna de ordenacao auxiliar.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_ANO_MES', @d;
SET @d = N'S quando a data cai em sabado ou domingo.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'FL_FIM_SEMANA', @d;
SET @d = N'LINHAGEM: quando o registro foi criado.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'DT_CARGA', @d;

-- fato_investimento ----------------------------------------------
SET @d = N'GOLD | Tabela fato com uma linha por movimentacao financeira. Granularidade: '
       + N'um evento na conta, identificado por HASH_NEGOCIO. Hoje contem apenas a XP '
       + N'Investimentos; o modelo ja comporta outras origens via SK_ORIGEM. '
       + N'A constraint UNIQUE em HASH_NEGOCIO impede que uma carga repetida duplique '
       + N'lancamentos - foi exatamente o que aconteceu no modelo antigo de dbo. '
       + N'ESCOPO: nao inclui chamadas de margem (categoria Margem), que sao garantia '
       + N'operacional sem efeito patrimonial e representavam metade dos eventos. '
       + N'Para o registro completo, consulte silver.xp_movimentacao.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', NULL, @d;
SET @d = N'Chave substituta do lancamento.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_LANCAMENTO', @d;
SET @d = N'Chave estrangeira para gold.dim_origem: de qual conta veio o lancamento.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_ORIGEM', @d;
SET @d = N'Chave estrangeira para gold.dim_calendario na data do fato economico. '
       + N'Use esta data para apurar resultado do periodo.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_DATA_MOVIMENTACAO', @d;
SET @d = N'Chave estrangeira para gold.dim_calendario na data em que o dinheiro entrou ou '
       + N'saiu. Use para fluxo de caixa e conciliacao de saldo. Vale -1 quando ausente.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_DATA_LIQUIDACAO', @d;
SET @d = N'Chave estrangeira para gold.dim_ativo. Vale -1 quando o lancamento nao se '
       + N'refere a um ativo (transferencia, taxa de conta).';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_ATIVO', @d;
SET @d = N'Chave estrangeira para gold.dim_categoria_investimento.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'SK_CATEGORIA_INVESTIMENTO', @d;
SET @d = N'METRICA. Valor da transacao em reais. Positivo = entrada de recurso, negativo = '
       + N'saida. E a medida aditiva do modelo: pode ser somada em qualquer combinacao de '
       + N'dimensoes.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'VL_TRANSACAO', @d;
SET @d = N'Saldo em conta corrente da corretora apos o lancamento. NAO E ADITIVO: somar '
       + N'esta coluna nao produz nada com sentido. Use apenas como ultimo valor de um '
       + N'periodo. Alem disso e saldo de CAIXA, nao patrimonio investido.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'VL_SALDO_MOMENTO', @d;
SET @d = N'S quando o lancamento e remuneracao do patrimonio (dividendo, JCP, rendimento, '
       + N'investback, reembolso, taxa de remuneracao com valor positivo). Filtrar por este '
       + N'campo da o total de proventos, sem misturar aporte e resgate.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'FL_RENDIMENTO', @d;
SET @d = N'RECEITA quando VL_TRANSACAO e positivo, DESPESA quando negativo. Fica no fato '
       + N'porque depende da transacao, nao da categoria.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'DS_TIPO_FLUXO', @d;
SET @d = N'Descricao original do lancamento como veio da XP. Mantida para auditoria: e a '
       + N'unica forma de conferir por que uma categoria ou ativo foi atribuido.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'DS_DETALHE_ORIGINAL', @d;
SET @d = N'Identidade do evento, herdada de silver.xp_movimentacao. Chave de deduplicacao '
       + N'entre as camadas e garantia de unicidade do fato.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando o lancamento foi carregado na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_investimento', 'DT_CARGA', @d;
GO


SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'gold' ORDER BY 1;
GO
