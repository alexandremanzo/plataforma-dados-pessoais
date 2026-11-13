/* =============================================================
   manzo-dados | 41 - Camada Gold: segmento corporal
   -------------------------------------------------------------
   gold.dim_segmento_corporal          (nova)
   gold.dim_metrica_corporal           (15 metricas novas)
   gold.fato_avaliacao_fisica          (5 colunas novas)

   O FATO NAO MUDA DE GRAO E NAO MUDA DE NOME. Ele ja e "uma linha
   por avaliacao e por metrica" desde 2008, que e exatamente a forma
   certa para absorver quinze metricas novas sem alterar estrutura.
   O modelo antigo pagando dividendo.

   O QUE MUDA E QUE A MESMA METRICA PASSA A TER LUGAR. "Massa Magra
   Segmentar" e uma metrica so, medida em cinco pontos do corpo -
   e nao cinco metricas. Sem o segmento na chave, comparar braco
   esquerdo com direito, ou somar as duas pernas, exigiria decorar
   nomes em vez de agrupar por dimensao.

   DUAS ORIGENS, UMA LINHA. A planilha preenchida a mao continua
   alimentando o fato, inclusive as 17 metricas de ate 2013 que o
   InBody nem mede - circunferencias, pressao, frequencia cardiaca.
   O arquivo do exame entra na frente onde existe, e a planilha
   preenche a lacuna. DS_ORIGEM registra quem venceu em cada linha.

   Pre-requisitos: 00, 01, 04 (calendario), 23, 40
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. A dimensao de segmento
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_segmento_corporal') IS NULL
BEGIN
    CREATE TABLE gold.dim_segmento_corporal (
        SK_SEGMENTO   int          NOT NULL,
        NM_SEGMENTO   varchar(40)  NOT NULL,
        DS_LADO       varchar(20)  NULL,
        DS_REGIAO     varchar(30)  NULL,
        NR_ORDEM      int          NOT NULL,
        DT_CARGA      datetime2(3) NOT NULL
            CONSTRAINT DF_dim_segmento_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_segmento_corporal PRIMARY KEY (SK_SEGMENTO),
        CONSTRAINT UQ_dim_segmento_corporal UNIQUE (NM_SEGMENTO)
    );

    /* O membro -1 chama-se "Corpo inteiro" e NAO "Nao informado":
       para o peso ou o IMC, nao haver segmento e a resposta certa e
       nao um dado faltando. Mesmo espirito do "Nao aplicavel" que
       dim_ativo usa para transferencia e imposto. */
    INSERT INTO gold.dim_segmento_corporal
        (SK_SEGMENTO, NM_SEGMENTO, DS_LADO, DS_REGIAO, NR_ORDEM)
    VALUES (-1, 'Corpo inteiro', NULL, NULL, 0),
           (1, 'Braço esquerdo',  'Esquerdo', 'Membro superior', 1),
           (2, 'Braço direito',   'Direito',  'Membro superior', 2),
           (3, 'Tronco',          'Central',  'Tronco',          3),
           (4, 'Perna esquerda',  'Esquerdo', 'Membro inferior', 4),
           (5, 'Perna direita',   'Direito',  'Membro inferior', 5);
END
GO


/* -------------------------------------------------------------
   2. As colunas novas do fato
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_avaliacao_fisica', 'SK_SEGMENTO') IS NULL
BEGIN
    /* As 419 linhas que ja existem sao todas de corpo inteiro: vem da
       planilha, que nunca teve analise segmentar. Por isso o default
       -1 e o NOT NULL logo em seguida. */
    ALTER TABLE gold.fato_avaliacao_fisica
        ADD SK_SEGMENTO int NOT NULL
            CONSTRAINT DF_fato_aval_segmento DEFAULT (-1);

    ALTER TABLE gold.fato_avaliacao_fisica
        ADD VL_REFERENCIA_MIN decimal(10,2) NULL,
            VL_REFERENCIA_MAX decimal(10,2) NULL,
            DS_AVALIACAO      varchar(20)   NULL,
            DS_ORIGEM         varchar(20)   NOT NULL
                CONSTRAINT DF_fato_aval_origem DEFAULT ('Planilha');
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_fato_aval_segmento')
    ALTER TABLE gold.fato_avaliacao_fisica
        ADD CONSTRAINT FK_fato_aval_segmento FOREIGN KEY (SK_SEGMENTO)
            REFERENCES gold.dim_segmento_corporal (SK_SEGMENTO);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_fato_aval_segmento')
    CREATE INDEX IX_fato_aval_segmento
        ON gold.fato_avaliacao_fisica (SK_SEGMENTO);
GO


/* -------------------------------------------------------------
   3. As metricas novas
   -------------------------------------------------------------
   So insere o que falta. DS_SENTIDO_MELHOR e regra de negocio e vive
   aqui como dado, ajustavel por UPDATE - o mesmo contrato das
   metricas que ja existiam. Fica NULO onde nao ha resposta universal:
   impedancia e dado bruto do aparelho, e "melhor" nao se aplica.
   ------------------------------------------------------------- */

;WITH nova(NM_METRICA, DS_GRUPO, DS_UNIDADE, DS_SENTIDO_MELHOR,
           FL_SERIE_CONTINUA, DS_ERA, NR_ORDEM) AS (
    SELECT * FROM (VALUES
        (N'Massa Livre de Gordura',   N'Composição', N'Kg',    N'MAIOR', 0, N'2018 em diante', 31),
        (N'Peso Ideal',               N'Controle',   N'Kg',    NULL,     0, N'2018 em diante', 32),
        (N'Controle de Peso',         N'Controle',   N'Kg',    NULL,     0, N'2018 em diante', 33),
        (N'Controle de Gordura',      N'Controle',   N'Kg',    NULL,     0, N'2018 em diante', 34),
        (N'Controle Muscular',        N'Controle',   N'Kg',    NULL,     0, N'2018 em diante', 35),
        (N'Taxa Metabolica Basal',    N'Metabolismo', N'kcal', N'MAIOR', 0, N'2018 em diante', 36),
        (N'Relacao Cintura-Quadril',  N'Obesidade',  N'Razão', N'MENOR', 0, N'2018 em diante', 37),
        (N'Grau de Obesidade',        N'Obesidade',  N'%',     NULL,     0, N'2018 em diante', 38),
        (N'IMC Normalizado',          N'Obesidade',  N'Imc',   NULL,     1, N'Ambas',          39),
        (N'Massa Magra Segmentar',    N'Segmentar',  N'Kg',    N'MAIOR', 0, N'2018 em diante', 40),
        (N'Massa Magra Segmentar %',  N'Segmentar',  N'%',     N'MAIOR', 0, N'2018 em diante', 41),
        (N'Gordura Segmentar',        N'Segmentar',  N'Kg',    N'MENOR', 0, N'2018 em diante', 42),
        (N'Gordura Segmentar %',      N'Segmentar',  N'%',     N'MENOR', 0, N'2018 em diante', 43),
        (N'Impedancia 20kHz',         N'Bruto',      N'Ohm',   NULL,     0, N'2018 em diante', 44),
        (N'Impedancia 100kHz',        N'Bruto',      N'Ohm',   NULL,     0, N'2018 em diante', 45)
    ) AS v(a, b, c, d, e, f, g)
)
INSERT INTO gold.dim_metrica_corporal
    (NM_METRICA, DS_GRUPO, DS_UNIDADE, DS_SENTIDO_MELHOR,
     FL_SERIE_CONTINUA, DS_ERA, NR_ORDEM)
SELECT n.NM_METRICA, n.DS_GRUPO, n.DS_UNIDADE, n.DS_SENTIDO_MELHOR,
       n.FL_SERIE_CONTINUA, n.DS_ERA, n.NR_ORDEM
FROM nova n
WHERE NOT EXISTS (SELECT 1 FROM gold.dim_metrica_corporal d
                   WHERE d.NM_METRICA = n.NM_METRICA);
GO


/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | As cinco partes do corpo que a bioimpedancia mede separadamente, mais o '
       + N'membro de corpo inteiro. E a dimensao que responde ONDE falta musculo, e nao '
       + N'apenas quanto - a pergunta que o preenchimento manual nunca alcancou. '
       + N'O MEMBRO -1 CHAMA-SE "Corpo inteiro" E NAO "Nao informado": para peso, IMC ou '
       + N'taxa metabolica, nao haver segmento e a resposta certa, e nao dado faltando.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', NULL, @d;

SET @d = N'Chave substituta do segmento. Fixa, e nao IDENTITY: sao seis membros que vem do '
       + N'aparelho e nao crescem com o uso.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'SK_SEGMENTO', @d;
SET @d = N'Nome do segmento: Braço esquerdo, Braço direito, Tronco, Perna esquerda, Perna '
       + N'direita, Corpo inteiro.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'NM_SEGMENTO', @d;
SET @d = N'Esquerdo, Direito ou Central. Permite medir assimetria entre os dois lados sem '
       + N'depender do nome do segmento.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'DS_LADO', @d;
SET @d = N'Membro superior, Membro inferior ou Tronco. Agrupa as duas pernas - e a quebra '
       + N'que mostrou a perda de massa magra concentrada nelas.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'DS_REGIAO', @d;
SET @d = N'Ordem de exibicao, de cima para baixo no corpo.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'NR_ORDEM', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_segmento_corporal', 'DT_CARGA', @d;

SET @d = N'Chave para gold.dim_segmento_corporal. Vale -1 (Corpo inteiro) em toda metrica '
       + N'que nao e segmentar - inclusive nas 419 linhas que vieram da planilha, que nunca '
       + N'teve analise segmentar.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'SK_SEGMENTO', @d;
SET @d = N'Limite inferior da faixa de referencia impressa no exame ao lado do valor. '
       + N'MUDA A CADA EXAME, porque depende de idade e altura - por isso e coluna do fato '
       + N'e nao atributo da metrica. Nulo nas linhas vindas da planilha.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'VL_REFERENCIA_MIN', @d;
SET @d = N'Limite superior da faixa de referencia impressa no exame.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'VL_REFERENCIA_MAX', @d;
SET @d = N'Classificacao que a propria maquina imprime: Abaixo, Normal ou Acima. So existe '
       + N'nas metricas segmentares, e e a leitura pronta de quanto o segmento se afasta do '
       + N'ideal calculado para o seu corpo.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'DS_AVALIACAO', @d;
SET @d = N'De onde a medida veio: InBody quando foi lida do arquivo do exame, Planilha '
       + N'quando foi digitada a mao. AS DUAS ORIGENS SE COMPLETAM - o arquivo entra na '
       + N'frente onde existe, a planilha preenche o que o OCR nao alcancou, e a planilha e '
       + N'a unica fonte das 17 metricas de ate 2013 que o InBody nem mede. No espirito do '
       + N'DS_ORIGEM_CLASSE de dim_ativo.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'DS_ORIGEM', @d;
GO

SELECT (SELECT COUNT(*) FROM gold.dim_segmento_corporal) AS segmentos,
       (SELECT COUNT(*) FROM gold.dim_metrica_corporal)  AS metricas,
       (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica) AS linhas_fato,
       (SELECT COUNT(*) FROM gold.fato_avaliacao_fisica
         WHERE SK_SEGMENTO = -1 AND DS_ORIGEM = 'Planilha') AS herdadas_ok;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('dim_segmento_corporal', 'fato_avaliacao_fisica') ORDER BY 1;
GO
