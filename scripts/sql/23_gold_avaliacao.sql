/* =============================================================
   manzo-dados | 23 - Camada Gold: avaliacao fisica
   -------------------------------------------------------------
   gold.dim_metrica_corporal + gold.fato_avaliacao_fisica

   A evolucao corporal ao longo de 18 anos, pronta para o Power BI.

   POR QUE A VARIACAO ESTA NO FATO. A pergunta que este painel
   responde e "como estou em relacao a avaliacao anterior". Como as
   avaliacoes sao IRREGULARES - de um mes a mais de tres anos entre
   elas - "anterior" nao e "mes passado" nem "ano passado", e a
   comparacao em DAX exigiria navegar por posicao dentro de cada
   metrica. Calculada na carga, vira uma coluna somavel.

   POR QUE O SENTIDO DE MELHORA E DADO, E NAO CODIGO. Para gordura,
   cair e melhorar; para massa muscular, subir. Sem isso o relatorio
   pinta de verde qualquer aumento. DS_SENTIDO_MELHOR vive na
   dimensao e pode ser ajustado com UPDATE, como em gold.dim_habito.

   Reaproveita gold.dim_calendario - o mesmo calendario dos fatos
   financeiros e do diario, o que permite cruzar avaliacao com habito
   pela data.

   Pre-requisitos: 00, 01, 04 (calendario), 22
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Dimensao de metrica corporal
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_metrica_corporal') IS NULL
BEGIN
    CREATE TABLE gold.dim_metrica_corporal (
        SK_METRICA        int IDENTITY(1,1) NOT NULL,
        NM_METRICA        varchar(100) NOT NULL,
        DS_GRUPO          varchar(100) NOT NULL,
        DS_UNIDADE        varchar(20)  NULL,
        DS_SENTIDO_MELHOR varchar(10)  NULL,
        FL_SERIE_CONTINUA bit          NOT NULL,
        DS_ERA            varchar(30)  NOT NULL,
        NR_ORDEM          int          NOT NULL,
        DT_CARGA          datetime2(3) NOT NULL
            CONSTRAINT DF_dim_metrica_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_metrica_corporal PRIMARY KEY (SK_METRICA),
        CONSTRAINT UQ_dim_metrica_nome UNIQUE (NM_METRICA)
    );

    SET IDENTITY_INSERT gold.dim_metrica_corporal ON;
    INSERT INTO gold.dim_metrica_corporal
        (SK_METRICA, NM_METRICA, DS_GRUPO, DS_UNIDADE,
         DS_SENTIDO_MELHOR, FL_SERIE_CONTINUA, DS_ERA, NR_ORDEM)
    VALUES (-1, 'Não informado', 'Não informado', NULL, NULL, 0, 'Não informado', 999);
    SET IDENTITY_INSERT gold.dim_metrica_corporal OFF;
END
GO


/* Catalogo das metricas.

   Insere apenas o que ainda nao existe: DS_SENTIDO_MELHOR e REGRA DE
   NEGOCIO E VIVE AQUI COMO DADO. Rodar este arquivo de novo nao
   desfaz um ajuste feito por UPDATE.

   DS_SENTIDO_MELHOR fica NULO onde nao ha resposta universal - peso,
   IMC e estatura dependem do objetivo de cada momento, e pressao
   arterial e melhor dentro de uma faixa, e nao no extremo. Marcar
   uma direcao ali seria fingir uma certeza que nao existe. */

MERGE gold.dim_metrica_corporal AS destino
USING (VALUES
    -- Composicao corporal
    ('Peso',                 'Analise da Composição corporal', 'Kg',     NULL,    1, 'Ambas',           1),
    ('Massa Muscular',       'Analise da Composição corporal', 'Kg',     'MAIOR', 0, '2018 em diante',  2),
    ('Massa Muscular/Ossea', 'Analise da Composição corporal', 'Kg',     'MAIOR', 0, 'Até 2013',        3),
    ('Massa Gordura',        'Analise da Composição corporal', 'Kg',     'MENOR', 1, 'Ambas',           4),
    ('Proteina',             'Analise da Composição corporal', 'Kg',     'MAIOR', 0, '2018 em diante',  5),
    ('Minerais',             'Analise da Composição corporal', 'Kg',     'MAIOR', 0, '2018 em diante',  6),
    ('Agua Corp',            'Analise da Composição corporal', 'L',      'MAIOR', 0, '2018 em diante',  7),
    -- Obesidade
    ('IMC',                  'Analise Obesidade',              'Imc',    NULL,    1, 'Ambas',           8),
    ('% Gordura',            'Analise Obesidade',              '%',      'MENOR', 1, 'Ambas',           9),
    ('Gordura Viceral',      'Nivel gordura viceral',          'Pontos', 'MENOR', 0, '2018 em diante', 10),
    ('Pontuação Corpo',      'Pontuação',                      'Pontos', 'MAIOR', 0, '2018 em diante', 11),
    -- Medida geral
    ('Estatura',             'Medida Geral',                   'cm',     NULL,    1, 'Ambas',          12),
    ('Frequencia Cardiaca',  'Medida Geral',                   'bpm',    'MENOR', 0, 'Até 2013',       13),
    ('Pressao Sistólica',    'Medida Geral',                   'mmHg',   NULL,    0, 'Até 2013',       14),
    ('Pressao Diastólica',   'Medida Geral',                   'mmHg',   NULL,    0, 'Até 2013',       15),
    -- Circunferencias: musculo cresce, cintura encolhe
    ('Ombro',                'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       16),
    ('Tórax',                'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       17),
    ('Braço D',              'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       18),
    ('Braço E',              'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       19),
    ('Antebraço D',          'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       20),
    ('Antebraço E',          'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       21),
    ('Coxa D',               'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       22),
    ('Coxa E',               'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       23),
    ('Perna D',              'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       24),
    ('Perna E',              'Circunferencias Musculares',     'cm',     'MAIOR', 0, 'Até 2013',       25),
    ('Cintura',              'Circunferencias Musculares',     'cm',     'MENOR', 0, 'Até 2013',       26),
    ('Abdomem',              'Circunferencias Musculares',     'cm',     'MENOR', 0, 'Até 2013',       27),
    ('Quadril',              'Circunferencias Musculares',     'cm',     'MENOR', 0, 'Até 2013',       28),
    ('Pescoço',              'Circunferencias Musculares',     'cm',     NULL,    0, 'Até 2013',       29),
    ('Busto',                'Circunferencias Musculares',     'cm',     NULL,    0, 'Até 2013',       30)
) AS origem (NM_METRICA, DS_GRUPO, DS_UNIDADE, DS_SENTIDO_MELHOR,
             FL_SERIE_CONTINUA, DS_ERA, NR_ORDEM)
    ON destino.NM_METRICA = origem.NM_METRICA
WHEN NOT MATCHED BY TARGET THEN
    INSERT (NM_METRICA, DS_GRUPO, DS_UNIDADE, DS_SENTIDO_MELHOR,
            FL_SERIE_CONTINUA, DS_ERA, NR_ORDEM)
    VALUES (origem.NM_METRICA, origem.DS_GRUPO, origem.DS_UNIDADE,
            origem.DS_SENTIDO_MELHOR, origem.FL_SERIE_CONTINUA,
            origem.DS_ERA, origem.NR_ORDEM);
GO


/* -------------------------------------------------------------
   2. Fato
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_avaliacao_fisica') IS NULL
BEGIN
    CREATE TABLE gold.fato_avaliacao_fisica (
        SK_MEDICAO         int IDENTITY(1,1) NOT NULL,

        SK_DATA            int           NOT NULL,
        SK_METRICA         int           NOT NULL,
        NR_AVALIACAO       int           NOT NULL,

        VL_MEDIDA          decimal(10,2) NULL,
        VL_MEDIDA_ANTERIOR decimal(10,2) NULL,
        VL_VARIACAO        decimal(10,2) NULL,
        FL_MELHOROU        bit           NULL,
        FL_MEDIDO          bit           NOT NULL,

        HASH_NEGOCIO       char(64)      NOT NULL,
        DT_CARGA           datetime2(3)  NOT NULL
            CONSTRAINT DF_fato_avaliacao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_avaliacao_fisica PRIMARY KEY (SK_MEDICAO),
        CONSTRAINT UQ_fato_avaliacao_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_fato_aval_data    FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_aval_metrica FOREIGN KEY (SK_METRICA)
            REFERENCES gold.dim_metrica_corporal (SK_METRICA)
    );

    CREATE INDEX IX_fato_aval_data    ON gold.fato_avaliacao_fisica (SK_DATA);
    CREATE INDEX IX_fato_aval_metrica ON gold.fato_avaliacao_fisica (SK_METRICA);
END
GO


/* -------------------------------------------------------------
   3. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Catalogo das metricas de avaliacao fisica: o que cada numero significa, '
       + N'em que unidade, em que era foi medido e para que lado e melhora. E a dimensao '
       + N'que torna o painel de evolucao legivel - sem ela, o relatorio nao sabe que '
       + N'gordura caindo e bom e massa muscular caindo e ruim.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', NULL, @d;

SET @d = N'Chave substituta da metrica. -1 representa metrica nao identificada.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'SK_METRICA', @d;
SET @d = N'Nome da metrica, como consta do laudo.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'NM_METRICA', @d;
SET @d = N'Agrupamento do laudo: composicao corporal, obesidade, circunferencias, medida '
       + N'geral, gordura visceral e pontuacao.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'DS_GRUPO', @d;
SET @d = N'Unidade da metrica. NUNCA agregue metricas de unidades diferentes na mesma '
       + N'conta - o fato guarda kg, cm, %, litros e pontos na mesma coluna de valor, '
       + N'entao qualquer soma precisa de filtro por metrica.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'DS_UNIDADE', @d;

SET @d = N'Para que lado a metrica melhora: MAIOR quando subir e bom (massa muscular, '
       + N'agua corporal, circunferencia de braco), MENOR quando cair e bom (gordura, '
       + N'cintura, gordura visceral). NULO onde nao ha resposta universal - peso, IMC e '
       + N'estatura dependem do objetivo do momento, e pressao arterial e melhor dentro de '
       + N'uma faixa e nao num extremo. E o que alimenta FL_MELHOROU no fato. Regra de '
       + N'negocio: ajustavel por UPDATE, sem alterar codigo.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'DS_SENTIDO_MELHOR', @d;

SET @d = N'1 nas cinco metricas que existem nas DUAS eras de medicao - Peso, IMC, '
       + N'% Gordura, Massa Gordura e Estatura - e portanto sustentam um grafico de 2008 a '
       + N'2026 sem buraco. FILTRE POR ESTA COLUNA no painel de longo prazo: as demais '
       + N'metricas produzem linhas que comecam ou terminam no meio do periodo.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'FL_SERIE_CONTINUA', @d;

SET @d = N'Em que era a metrica foi medida: "Até 2013" (laudo completo, com '
       + N'circunferencias e pressao), "2018 em diante" (bioimpedancia) ou "Ambas".';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'DS_ERA', @d;
SET @d = N'Ordem de exibicao no relatorio, agrupada por assunto.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'NR_ORDEM', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_metrica_corporal', 'DT_CARGA', @d;

SET @d = N'GOLD | A evolucao corporal medida, uma linha por avaliacao e por metrica. '
       + N'E A SERIE MAIS LONGA DO PROJETO: 31 avaliacoes entre 2008 e 2026. '
       + N'ATENCAO: a coluna de valor mistura unidades (kg, cm, %, litros, pontos), entao '
       + N'toda agregacao exige filtro por metrica - somar a coluna inteira nao significa '
       + N'nada. E a serie NAO E HOMOGENEA: so cinco metricas cobrem os 18 anos, '
       + N'identificadas por FL_SERIE_CONTINUA na dimensao.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', NULL, @d;

SET @d = N'Chave substituta da medicao.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'SK_MEDICAO', @d;
SET @d = N'Chave para gold.dim_calendario - o MESMO calendario dos fatos financeiros e do '
       + N'diario, o que permite cruzar avaliacao com habito e com gasto pela data.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_metrica_corporal: o que foi medido.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'SK_METRICA', @d;
SET @d = N'Numero sequencial da avaliacao, de 1 a 31 em ordem de data. Permite ordenar e '
       + N'comparar avaliacoes sem depender do intervalo entre elas, que e irregular.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'NR_AVALIACAO', @d;

SET @d = N'METRICA. Valor medido, na unidade da metrica. NAO SOME sem filtrar por metrica: '
       + N'a coluna guarda kg, cm, % e pontos juntos.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'VL_MEDIDA', @d;
SET @d = N'Valor da mesma metrica na avaliacao ANTERIOR em que ela foi medida. Nulo na '
       + N'primeira ocorrencia. Trazido para o fato porque as avaliacoes sao irregulares - '
       + N'de um mes a mais de tres anos entre elas - e "anterior" nao coincide com nenhum '
       + N'periodo do calendario, o que tornaria a comparacao em DAX cara e fragil.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'VL_MEDIDA_ANTERIOR', @d;
SET @d = N'Diferenca entre esta medicao e a anterior da mesma metrica. Positivo significa '
       + N'aumento, e nao melhora - para saber se aumentar e bom, use FL_MELHOROU.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'VL_VARIACAO', @d;
SET @d = N'S quando a variacao foi na direcao desejada para aquela metrica, conforme '
       + N'DS_SENTIDO_MELHOR da dimensao. NULO quando nao ha medicao anterior, quando o '
       + N'valor nao mudou, ou quando a metrica nao tem direcao boa definida - peso e IMC, '
       + N'por exemplo, dependem do objetivo. '
       + N'PARA O PERCENTUAL de metricas que melhoraram numa avaliacao use '
       + N'AVG(CASE WHEN FL_MELHOROU = ''''S'''' THEN 1.0 WHEN FL_MELHOROU = ''''N'''' THEN 0.0 '
       + N'END), com os dois ramos: o ELSE 0 contaria como piora o que nao foi avaliado.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'FL_MELHOROU', @d;
SET @d = N'N quando a metrica constava do laudo mas ficou sem valor. Distingue "nao foi '
       + N'medido" de "nao consta daquela era".';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'FL_MEDIDO', @d;
SET @d = N'Identidade da medicao, herdada da silver: hash de data + metrica.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando a medicao foi carregada na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_avaliacao_fisica', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('dim_metrica_corporal', 'fato_avaliacao_fisica') ORDER BY 1;
GO
