/* =============================================================
   manzo-dados | 20 - Camada Gold: meu dia
   -------------------------------------------------------------
   gold.dim_habito + gold.fato_dia + gold.fato_dia_habito

   O diario de habitos, pronto para o Power BI.

   POR QUE DOIS FATOS DA MESMA ORIGEM. As duas perguntas que se
   faz a esta base tem formatos incompativeis:

   - "quanta agua bebi por mes", "treinei mais nos dias que a Nina
     esteve em casa?" - precisam de UMA linha por dia, com todas
     as respostas lado a lado. E gold.fato_dia.

   - "como esta a aderencia de cada habito ao longo do tempo?" -
     precisa de UMA linha por dia POR HABITO, senao o grafico
     exige uma medida DAX diferente para cada pergunta do
     formulario, e acrescentar uma pergunta nova quebra o
     relatorio. E gold.fato_dia_habito.

   Modelar so o formato largo tornaria o painel de habitos
   inviavel; modelar so o longo tornaria impossivel somar litros
   de agua sem misturar unidades. Sao 888 e cerca de 10 mil
   linhas - o custo de manter os dois e irrelevante.

   NENHUM DOS DOIS SE LIGA AOS FATOS FINANCEIROS. O unico eixo
   compartilhado e gold.dim_calendario, e ele basta para o
   cruzamento que interessa: gasto e habito na mesma data.

   Pre-requisitos: 00, 01, 04 (calendario), 19
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Dimensao de habito
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_habito') IS NULL
BEGIN
    CREATE TABLE gold.dim_habito (
        SK_HABITO            int IDENTITY(1,1) NOT NULL,
        NM_HABITO            varchar(50)  NOT NULL,
        DS_GRUPO             varchar(30)  NOT NULL,
        DS_PERGUNTA          varchar(100) NOT NULL,
        DS_RESPOSTA_DESEJADA varchar(10)  NULL,
        VL_META_MINIMA       decimal(6,2) NULL,
        DS_UNIDADE           varchar(20)  NULL,
        FL_APURA_ADERENCIA   bit          NOT NULL,
        NR_ORDEM             int          NOT NULL,
        DT_CARGA             datetime2(3) NOT NULL
            CONSTRAINT DF_dim_habito_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_habito PRIMARY KEY (SK_HABITO),
        CONSTRAINT UQ_dim_habito_nome UNIQUE (NM_HABITO)
    );

    SET IDENTITY_INSERT gold.dim_habito ON;
    INSERT INTO gold.dim_habito
        (SK_HABITO, NM_HABITO, DS_GRUPO, DS_PERGUNTA,
         DS_RESPOSTA_DESEJADA, FL_APURA_ADERENCIA, NR_ORDEM)
    VALUES (-1, 'Não informado', 'Não informado', 'Não informado', NULL, 0, 99);
    SET IDENTITY_INSERT gold.dim_habito OFF;
END
GO

/* Habito medido em numero, e nao em sim/nao, precisa de limiar em vez
   de resposta esperada. Acrescentado depois da criacao da tabela. */
IF COL_LENGTH('gold.dim_habito', 'VL_META_MINIMA') IS NULL
    ALTER TABLE gold.dim_habito ADD VL_META_MINIMA decimal(6,2) NULL;
GO
IF COL_LENGTH('gold.dim_habito', 'DS_UNIDADE') IS NULL
    ALTER TABLE gold.dim_habito ADD DS_UNIDADE varchar(20) NULL;
GO


/* Catalogo das perguntas do formulario.

   Insere apenas o que ainda nao existe. NAO atualiza o que ja esta
   la, de proposito: DS_RESPOSTA_DESEJADA, VL_META_MINIMA e
   FL_APURA_ADERENCIA sao REGRA DE NEGOCIO E VIVEM AQUI COMO DADO, nao
   no codigo da carga. Mudar a meta de agua ou decidir que a ceia e
   opcional e um UPDATE nesta tabela seguido de nova carga - sem
   editar script. Rodar este arquivo de novo nao desfaz o ajuste.

   DUAS FORMAS DE MEDIR ADERENCIA, e cada habito usa uma:
   - DS_RESPOSTA_DESEJADA, para o que se responde com sim ou nao
   - VL_META_MINIMA, para o que se responde com um numero

   A agua e o unico do segundo tipo hoje. A meta abaixo e um ponto de
   partida: ajuste para o seu alvo real. */

MERGE gold.dim_habito AS destino
USING (VALUES
    ('Água',          'Saúde',          'Consumo de água (Litros)', NULL,  2.00, 'litros', 1,  1),
    ('Treino',        'Saúde',          'Treino',                   'SIM', NULL, NULL,     1,  2),
    ('Cardio',        'Saúde',          'Cardio',                   'SIM', NULL, NULL,     1,  3),
    ('Café da manhã', 'Alimentação',    'Café da Manhã',            'SIM', NULL, NULL,     1,  4),
    ('Almoço',        'Alimentação',    'Almoço',                   'SIM', NULL, NULL,     1,  5),
    ('Lanche',        'Alimentação',    'Lanche',                   'SIM', NULL, NULL,     1,  6),
    ('Janta',         'Alimentação',    'Janta',                    'SIM', NULL, NULL,     1,  7),
    ('Ceia',          'Alimentação',    'Ceia',                     'SIM', NULL, NULL,     1,  8),
    ('Dia produtivo', 'Rotina',         'Dia Produtivo',            NULL,  NULL, NULL,     0,  9),
    ('Trabalho',      'Rotina',         'Trabalho',                 NULL,  NULL, NULL,     0, 10),
    ('Nina em casa',   'Rotina',         'Nina em casa',              NULL,  NULL, NULL,     0, 11),
    ('Estresse',         'Bem-estar', 'Estresse',                    'NAO', NULL, NULL,     1, 12),
    ('Lazer',        'Bem-estar', 'Lazer',                   'SIM', NULL, NULL,     1, 13)
) AS origem (NM_HABITO, DS_GRUPO, DS_PERGUNTA, DS_RESPOSTA_DESEJADA,
             VL_META_MINIMA, DS_UNIDADE, FL_APURA_ADERENCIA, NR_ORDEM)
    ON destino.NM_HABITO = origem.NM_HABITO
WHEN NOT MATCHED BY TARGET THEN
    INSERT (NM_HABITO, DS_GRUPO, DS_PERGUNTA, DS_RESPOSTA_DESEJADA,
            VL_META_MINIMA, DS_UNIDADE, FL_APURA_ADERENCIA, NR_ORDEM)
    VALUES (origem.NM_HABITO, origem.DS_GRUPO, origem.DS_PERGUNTA,
            origem.DS_RESPOSTA_DESEJADA, origem.VL_META_MINIMA,
            origem.DS_UNIDADE, origem.FL_APURA_ADERENCIA, origem.NR_ORDEM);
GO


/* -------------------------------------------------------------
   2. Fato do dia (formato largo, um por dia)
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_dia') IS NULL
BEGIN
    CREATE TABLE gold.fato_dia (
        SK_DIA                int IDENTITY(1,1) NOT NULL,

        SK_DATA               int          NOT NULL,

        VL_AGUA_LITROS        decimal(5,2) NULL,
        FL_META_AGUA          bit          NULL,
        NR_REFEICOES_FEITAS   int          NOT NULL,
        NR_REFEICOES_JACA     int          NOT NULL,
        NR_HABITOS_ADERENTES  int          NOT NULL,
        NR_HABITOS_APURADOS   int          NOT NULL,

        FL_TREINO             bit          NULL,
        FL_CARDIO             bit          NULL,
        FL_TRABALHO           bit          NULL,
        FL_NINA_EM_CASA        bit          NULL,
        FL_ESTRESSE              bit          NULL,
        FL_LAZER             bit          NULL,
        DS_DIA_PRODUTIVO      varchar(20)  NULL,

        NR_DIAS_ATRASO        int          NULL,
        FL_DATA_SUSPEITA      bit          NOT NULL,

        HASH_NEGOCIO          char(64)     NOT NULL,
        DT_CARGA              datetime2(3) NOT NULL
            CONSTRAINT DF_fato_dia_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_dia PRIMARY KEY (SK_DIA),
        CONSTRAINT UQ_fato_dia_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_fato_dia_data FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA)
    );

    CREATE INDEX IX_fato_dia_data ON gold.fato_dia (SK_DATA);
END
GO

/* Acrescentado depois: a agua passou a ter meta diaria. */
IF COL_LENGTH('gold.fato_dia', 'FL_META_AGUA') IS NULL
    ALTER TABLE gold.fato_dia ADD FL_META_AGUA bit NULL;
GO


/* -------------------------------------------------------------
   3. Fato do dia por habito (formato longo)
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_dia_habito') IS NULL
BEGIN
    CREATE TABLE gold.fato_dia_habito (
        SK_DIA_HABITO   int IDENTITY(1,1) NOT NULL,

        SK_DATA         int          NOT NULL,
        SK_HABITO       int          NOT NULL,

        DS_RESPOSTA     varchar(20)  NULL,
        VL_MEDIDA       decimal(6,2) NULL,
        FL_ADERENCIA    bit          NULL,
        FL_RESPONDIDO   bit          NOT NULL,

        HASH_NEGOCIO    char(64)     NOT NULL,
        DT_CARGA        datetime2(3) NOT NULL
            CONSTRAINT DF_fato_dia_habito_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_dia_habito PRIMARY KEY (SK_DIA_HABITO),
        CONSTRAINT UQ_fato_dia_habito_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_fato_dh_data   FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_dh_habito FOREIGN KEY (SK_HABITO)
            REFERENCES gold.dim_habito (SK_HABITO)
    );

    CREATE INDEX IX_fato_dh_data   ON gold.fato_dia_habito (SK_DATA);
    CREATE INDEX IX_fato_dh_habito ON gold.fato_dia_habito (SK_HABITO);
END
GO

/* Acrescentado depois: habito medido em numero precisa carregar o
   valor, e nao so a resposta em texto. */
IF COL_LENGTH('gold.fato_dia_habito', 'VL_MEDIDA') IS NULL
    ALTER TABLE gold.fato_dia_habito ADD VL_MEDIDA decimal(6,2) NULL;
GO


/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Catalogo das perguntas do diario. Existe para que o painel de habitos '
       + N'seja um grafico so, com uma medida so: sem esta dimensao, cada pergunta do '
       + N'formulario viraria uma medida DAX propria e acrescentar uma pergunta nova '
       + N'exigiria refazer o relatorio. Separa objetivo de contexto - treinar e uma meta, '
       + N'a filha estar em casa e uma circunstancia - e por isso nem todo habito apura '
       + N'aderencia.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', NULL, @d;

SET @d = N'Chave substituta do habito. -1 representa habito nao identificado.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'SK_HABITO', @d;
SET @d = N'Nome curto do habito, como aparece no relatorio.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'NM_HABITO', @d;
SET @d = N'Agrupamento tematico: Saude, Alimentacao, Rotina ou Bem-estar. Permite ler '
       + N'o painel por bloco em vez de habito a habito.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'DS_GRUPO', @d;
SET @d = N'Texto original da pergunta no formulario do Google. Guardado porque o rotulo da '
       + N'origem pode mudar sem que o habito mude, e e por ele que a carga liga a coluna '
       + N'do CSV a esta dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'DS_PERGUNTA', @d;
SET @d = N'Resposta que representa o objetivo cumprido, para os habitos medidos em sim/nao. '
       + N'Vale SIM na maioria, NAO em Estresse - onde o sucesso e a ausencia - e nulo tanto '
       + N'nos habitos de contexto quanto nos medidos por numero, que usam VL_META_MINIMA.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'DS_RESPOSTA_DESEJADA', @d;

SET @d = N'META DIARIA, para os habitos medidos em NUMERO em vez de sim/nao. A aderencia '
       + N'passa a ser "o valor do dia alcancou este limiar". Hoje so a agua usa: a meta e '
       + N'em litros por dia. Ajustar o alvo e um UPDATE nesta coluna seguido de nova '
       + N'carga - a regra vive aqui como dado, e nao no codigo, e a semeadura do script '
       + N'nao sobrescreve o ajuste.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'VL_META_MINIMA', @d;

SET @d = N'Unidade de VL_META_MINIMA, para o relatorio rotular o numero sem depender de '
       + N'quem monta a visualizacao lembrar qual e. Nula nos habitos de sim/nao.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'DS_UNIDADE', @d;
SET @d = N'S quando o habito e uma META e faz sentido medir aderencia. N quando e apenas '
       + N'CONTEXTO: trabalhar, a filha estar em casa e a avaliacao do dia descrevem a '
       + N'circunstancia e nao um objetivo - somar tudo como se fosse meta produziria um '
       + N'indice sem significado. Os de contexto continuam validos como filtro.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'FL_APURA_ADERENCIA', @d;
SET @d = N'Ordem de exibicao no relatorio, seguindo a sequencia do formulario.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'NR_ORDEM', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_habito', 'DT_CARGA', @d;

SET @d = N'GOLD | Um retrato por dia: todas as respostas do formulario lado a lado. E o '
       + N'formato para cruzar habitos entre si ("treinei mais nos dias de trabalho?") e '
       + N'para somar o consumo de agua, a unica medida numerica da base. '
       + N'Para acompanhar aderencia ao longo do tempo, use gold.fato_dia_habito. '
       + N'COBERTURA: cerca de 93% dos dias desde janeiro de 2024 tem resposta; os dias sem '
       + N'registro simplesmente nao existem aqui, entao contar linhas nao e o mesmo que '
       + N'contar dias do calendario.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', NULL, @d;

SET @d = N'Chave substituta do dia registrado.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'SK_DIA', @d;
SET @d = N'Chave para gold.dim_calendario - o MESMO calendario dos fatos financeiros, o que '
       + N'permite cruzar habito e gasto pela mesma data. Vale -1 quando a data digitada no '
       + N'formulario e implausivel; ver FL_DATA_SUSPEITA.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'SK_DATA', @d;
SET @d = N'METRICA. Litros de agua no dia - indicador de controle acompanhado de perto. '
       + N'Unica medida numerica da base: some ou tire media a vontade. As demais colunas '
       + N'sao indicadores, e somar bit nao tem significado alem de "quantos dias". '
       + N'ATENCAO ao usar media por periodo: os dias sem resposta nao existem nesta '
       + N'tabela, entao AVG devolve a media DOS DIAS REGISTRADOS, e nao dos dias do '
       + N'calendario. Para litros por dia corrido, divida a soma pela contagem de datas '
       + N'de gold.dim_calendario no periodo.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'VL_AGUA_LITROS', @d;

SET @d = N'S quando o consumo de agua do dia alcancou a meta diaria. A meta nao esta aqui: '
       + N'vive em gold.dim_habito.VL_META_MINIMA, para ser ajustavel sem alterar codigo. '
       + N'Mudar a meta e recarregar reescreve esta coluna em toda a serie, o que permite '
       + N'responder "com a meta nova, como teria sido 2024".';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_META_AGUA', @d;
SET @d = N'Quantas das cinco refeicoes foram feitas dentro do plano alimentar, de 0 a 5.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'NR_REFEICOES_FEITAS', @d;
SET @d = N'Quantas das cinco refeicoes sairam do plano alimentar, de 0 a 5. Principal '
       + N'indicador de aderencia a dieta.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'NR_REFEICOES_JACA', @d;
SET @d = N'Quantas METAS do dia foram cumpridas. Denominador em NR_HABITOS_APURADOS - a '
       + N'razao entre os dois e a nota do dia. Guardado no fato, e nao calculado no Power '
       + N'BI, para que a nota seja a mesma em qualquer ferramenta que leia a tabela.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'NR_HABITOS_ADERENTES', @d;
SET @d = N'Quantas metas foram efetivamente respondidas no dia. E o denominador correto da '
       + N'nota: usar um numero fixo trataria pergunta em branco como meta perdida.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'NR_HABITOS_APURADOS', @d;
SET @d = N'S quando houve treino de musculacao.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_TREINO', @d;
SET @d = N'S quando houve cardio.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_CARDIO', @d;
SET @d = N'S quando houve trabalho no dia. CONTEXTO, nao meta - serve para segmentar os '
       + N'demais indicadores entre dia util e folga.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_TRABALHO', @d;
SET @d = N'S quando a filha esteve em casa. CONTEXTO, nao meta.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_NINA_EM_CASA', @d;
SET @d = N'S quando houve discussao no dia. Aqui o objetivo e o zero, e nao o S.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_ESTRESSE', @d;
SET @d = N'S quando houve momento a dois no dia.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_LAZER', @d;
SET @d = N'Avaliacao do dia: NORMAL, SIM ou NAO. NAO E BOOLEANO - NORMAL cobre oito de cada '
       + N'dez dias e e a resposta padrao, entao ler "diferente de SIM" como dia ruim '
       + N'inverteria o sentido da escala.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'DS_DIA_PRODUTIVO', @d;
SET @d = N'Dias entre o dia relatado e o envio do formulario. Normalmente 1. Valores altos '
       + N'indicam resposta preenchida de memoria, menos confiavel.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'NR_DIAS_ATRASO', @d;
SET @d = N'ALERTA DE QUALIDADE. S quando a data digitada no formulario e implausivel. '
       + N'Esses registros apontam para SK_DATA = -1 e ficam fora de qualquer analise '
       + N'temporal ate serem corrigidos na origem.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'FL_DATA_SUSPEITA', @d;
SET @d = N'Identidade da resposta, herdada da silver: hash do carimbo do formulario.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando o dia foi carregado na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_dia', 'DT_CARGA', @d;

SET @d = N'GOLD | Uma linha por dia POR HABITO - o formato longo do diario. Existe para que '
       + N'o painel de habitos seja um grafico so: com este fato, "% de aderencia por '
       + N'habito por mes" e uma unica medida (AVG de FL_ADERENCIA) segmentada por '
       + N'gold.dim_habito, e uma pergunta nova no formulario entra sem tocar no '
       + N'relatorio. O formato largo equivalente esta em gold.fato_dia. '
       + N'NAO SOME as duas tabelas juntas: sao a mesma informacao em dois formatos.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', NULL, @d;

SET @d = N'Chave substituta da combinacao dia + habito.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'SK_DIA_HABITO', @d;
SET @d = N'Chave para gold.dim_calendario. Vale -1 quando a data do formulario e '
       + N'implausivel.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_habito: qual pergunta do formulario esta linha responde.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'SK_HABITO', @d;
SET @d = N'Resposta padronizada: SIM, NAO, JACA ou NORMAL. Preservada ao lado do indicador '
       + N'porque JACA e NAO contam igual na aderencia mas significam coisas opostas - uma '
       + N'e sair da dieta, a outra e pular a refeicao. No habito de agua, que e medido em '
       + N'numero, traz o valor do dia ja com a unidade ("1,3 litros"); para calcular use '
       + N'VL_MEDIDA ou gold.fato_dia.VL_AGUA_LITROS, nunca esta coluna.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'DS_RESPOSTA', @d;

SET @d = N'Valor do dia para os habitos medidos em NUMERO - hoje so a agua, em litros. '
       + N'Nulo nos habitos de sim/nao. NAO SOME esta coluna sem filtrar o habito: se um '
       + N'dia houver um segundo habito numerico em outra unidade, a soma juntaria litros '
       + N'com outra coisa. Para agua, gold.fato_dia.VL_AGUA_LITROS e o caminho seguro.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'VL_MEDIDA', @d;
SET @d = N'METRICA PRINCIPAL. S quando a resposta bate com o objetivo do habito, N quando '
       + N'nao. NULO nos habitos de contexto, que nao tem objetivo. '
       + N'PARA O PERCENTUAL DE ADERENCIA use AVG(CASE WHEN FL_ADERENCIA = ''''S'''' THEN 1.0 '
       + N'WHEN FL_ADERENCIA = ''''N'''' THEN 0.0 END) - a media continua ignorando o nulo '
       + N'sozinha, mas o CASE precisa dos DOIS ramos: trocar o segundo WHEN por um ELSE 0 '
       + N'contaria os habitos de contexto como meta nao cumprida e derrubaria a aderencia '
       + N'sem nada ter acontecido.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'FL_ADERENCIA', @d;
SET @d = N'S quando a pergunta foi respondida naquele dia. Distingue "nao cumpri a meta" de '
       + N'"nao respondi", que somados dariam uma aderencia artificialmente baixa.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'FL_RESPONDIDO', @d;
SET @d = N'Identidade da linha: hash do carimbo do formulario combinado com o habito.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando a linha foi carregada na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_dia_habito', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('dim_habito', 'fato_dia', 'fato_dia_habito') ORDER BY 1;
GO
