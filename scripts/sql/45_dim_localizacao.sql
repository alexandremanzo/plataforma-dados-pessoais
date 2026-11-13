/* =============================================================
   manzo-dados | 45 - Camada Gold: dimensao de localizacao
   -------------------------------------------------------------
   gold.dim_localizacao
   + SK_LOCALIZACAO em gold.fato_movto_financ e gold.fato_familia
   - DS_CIDADE, DS_UF, DS_PAIS dos dois fatos

   Cidade, UF e pais eram tres colunas de texto repetidas em cada
   lancamento. Viram uma dimensao com uma linha por lugar, e o fato
   guarda so a chave.

   O QUE ISSO HABILITA. Latitude e longitude ja nascem aqui, nulas.
   Preenche-las passa a ser um UPDATE em cerca de 140 linhas, e nao
   em 15 mil; e qualquer atributo futuro - regiao, fuso, populacao -
   entra do mesmo jeito, sem tocar no fato.

   AS GRAFIAS NAO SAO CORRIGIDAS, por decisao. A mesma cidade
   aparece sob UF diferente em 53 lancamentos:

       Belo Horizonte/DF    13   (contra 477 em MG)
       Cidade A/DF          19   (contra 4.096 em MG)
       Brasilia sem UF      17   Brasilia/MG    1
       Cidade B/MG            1   Cidade C/MG  1   Cidade D/DF  1

   Elas entram como MEMBROS SEPARADOS. A consequencia esta declarada
   porque e real: quando as coordenadas forem preenchidas, "Belo
   Horizonte" tera duas linhas pedindo coordenada, e dar a mesma as
   duas e o certo. A conferencia no fim do script lista essas
   cidades toda vez que ele roda, para que a lacuna nao suma de
   vista. Quando houver a lista revisada, entra um de-para, como o
   das categorias do Itau.

   POR QUE O FATO PERDE AS TRES COLUNAS. A trilha de auditoria nao
   depende delas: ds_cidade, ds_uf e ds_pais seguem na silver e na
   bronze de TODAS as origens, e o gold e reconstruivel a partir
   dali. Manter as colunas e a chave lado a lado seria guardar a
   mesma informacao duas vezes, com as duas livres para divergir.

   O DROP SO ACONTECE SE A CARGA FECHAR. Antes dele ha uma guarda
   que aborta o script se sobrar lancamento com localizacao
   preenchida e SK_LOCALIZACAO = -1. Rodar com a dimensao incompleta
   apagaria o texto sem ter a chave - e e justamente a hora em que
   nao se pode confiar no proprio script.

   Pre-requisitos: 14_gold_movimentacao.sql, 17_gold_familia.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

-- O sqlcmd abre a sessao com QUOTED_IDENTIFIER OFF, e coluna
-- calculada PERSISTED exige ON - sem isto o CREATE TABLE falha com
-- "SET options have incorrect settings". Vale para a sessao inteira,
-- entao fica aqui, antes de qualquer DDL.
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/* -------------------------------------------------------------
   1. A dimensao
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_localizacao') IS NULL
BEGIN
    CREATE TABLE gold.dim_localizacao (
        SK_LOCALIZACAO int IDENTITY(1,1) NOT NULL,
        NM_CIDADE      varchar(100) NULL,
        SG_UF          varchar(2)   NULL,
        NM_PAIS        varchar(60)  NULL,

        -- Calculada e PERSISTED de proposito: rotulo guardado a mao
        -- envelhece calado no dia em que alguem corrigir a UF.
        NM_LOCALIZACAO AS (
            CASE WHEN NM_CIDADE IS NULL AND SG_UF IS NULL AND NM_PAIS IS NULL
                 THEN 'Não informado'
                 ELSE ISNULL(NM_CIDADE, 'Sem cidade')
                      + CASE WHEN SG_UF   IS NOT NULL THEN '/' + SG_UF ELSE '' END
                      + CASE WHEN NM_PAIS IS NOT NULL THEN ' - ' + NM_PAIS ELSE '' END
            END) PERSISTED,

        VL_LATITUDE    decimal(9,6) NULL,
        VL_LONGITUDE   decimal(9,6) NULL,
        DT_CARGA       datetime2(3) NOT NULL
            CONSTRAINT DF_dim_localizacao_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_localizacao PRIMARY KEY (SK_LOCALIZACAO),
        CONSTRAINT UQ_dim_localizacao UNIQUE (NM_PAIS, SG_UF, NM_CIDADE)
    );

    SET IDENTITY_INSERT gold.dim_localizacao ON;
    INSERT INTO gold.dim_localizacao (SK_LOCALIZACAO, NM_CIDADE, SG_UF, NM_PAIS)
    VALUES (-1, NULL, NULL, NULL);
    SET IDENTITY_INSERT gold.dim_localizacao OFF;
END
GO

/* -------------------------------------------------------------
   2. Os lugares, dos dois fatos de uma vez
   ------------------------------------------------------------- */

-- UF com mais de dois caracteres viraria truncamento silencioso na
-- insercao. Hoje nao ha nenhuma; a guarda existe para o dia em que
-- a origem mudar.
IF COL_LENGTH('gold.fato_movto_financ', 'DS_UF') IS NOT NULL
BEGIN
    DECLARE @longas int =
        (SELECT COUNT(*) FROM gold.fato_movto_financ WHERE LEN(DS_UF) > 2)
      + (SELECT COUNT(*) FROM gold.fato_familia      WHERE LEN(DS_UF) > 2);
    IF @longas > 0
        THROW 50045, 'Ha UF com mais de 2 caracteres. SG_UF truncaria sem avisar.', 1;
END
GO

IF COL_LENGTH('gold.fato_movto_financ', 'DS_CIDADE') IS NOT NULL
BEGIN
    WITH lugares AS (
        SELECT DS_CIDADE, DS_UF, DS_PAIS FROM gold.fato_movto_financ
        UNION
        SELECT DS_CIDADE, DS_UF, DS_PAIS FROM gold.fato_familia
    )
    INSERT INTO gold.dim_localizacao (NM_CIDADE, SG_UF, NM_PAIS)
    SELECT l.DS_CIDADE, l.DS_UF, l.DS_PAIS
    FROM lugares l
    WHERE (l.DS_CIDADE IS NOT NULL OR l.DS_UF IS NOT NULL OR l.DS_PAIS IS NOT NULL)
      AND NOT EXISTS (
          SELECT 1 FROM gold.dim_localizacao d
          WHERE ISNULL(d.NM_CIDADE, '~') = ISNULL(l.DS_CIDADE, '~')
            AND ISNULL(d.SG_UF,     '~') = ISNULL(l.DS_UF,     '~')
            AND ISNULL(d.NM_PAIS,   '~') = ISNULL(l.DS_PAIS,   '~'));
END
GO

/* -------------------------------------------------------------
   3. A chave nos dois fatos
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_movto_financ', 'SK_LOCALIZACAO') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD SK_LOCALIZACAO int NOT NULL
        CONSTRAINT DF_fato_movto_financ_loc DEFAULT (-1);
GO

IF COL_LENGTH('gold.fato_familia', 'SK_LOCALIZACAO') IS NULL
    ALTER TABLE gold.fato_familia ADD SK_LOCALIZACAO int NOT NULL
        CONSTRAINT DF_fato_familia_loc DEFAULT (-1);
GO

IF COL_LENGTH('gold.fato_movto_financ', 'DS_CIDADE') IS NOT NULL
BEGIN
    UPDATE f SET f.SK_LOCALIZACAO = d.SK_LOCALIZACAO
    FROM gold.fato_movto_financ f
    JOIN gold.dim_localizacao d
      ON ISNULL(d.NM_CIDADE, '~') = ISNULL(f.DS_CIDADE, '~')
     AND ISNULL(d.SG_UF,     '~') = ISNULL(f.DS_UF,     '~')
     AND ISNULL(d.NM_PAIS,   '~') = ISNULL(f.DS_PAIS,   '~');

    UPDATE f SET f.SK_LOCALIZACAO = d.SK_LOCALIZACAO
    FROM gold.fato_familia f
    JOIN gold.dim_localizacao d
      ON ISNULL(d.NM_CIDADE, '~') = ISNULL(f.DS_CIDADE, '~')
     AND ISNULL(d.SG_UF,     '~') = ISNULL(f.DS_UF,     '~')
     AND ISNULL(d.NM_PAIS,   '~') = ISNULL(f.DS_PAIS,   '~');
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_fato_movto_financ_loc')
    ALTER TABLE gold.fato_movto_financ ADD CONSTRAINT FK_fato_movto_financ_loc
        FOREIGN KEY (SK_LOCALIZACAO) REFERENCES gold.dim_localizacao (SK_LOCALIZACAO);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_fato_familia_loc')
    ALTER TABLE gold.fato_familia ADD CONSTRAINT FK_fato_familia_loc
        FOREIGN KEY (SK_LOCALIZACAO) REFERENCES gold.dim_localizacao (SK_LOCALIZACAO);
GO

/* -------------------------------------------------------------
   4. A guarda, e so entao o DROP
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_movto_financ', 'DS_CIDADE') IS NOT NULL
BEGIN
    DECLARE @orfaos int =
        (SELECT COUNT(*) FROM gold.fato_movto_financ
          WHERE SK_LOCALIZACAO = -1
            AND (DS_CIDADE IS NOT NULL OR DS_UF IS NOT NULL OR DS_PAIS IS NOT NULL))
      + (SELECT COUNT(*) FROM gold.fato_familia
          WHERE SK_LOCALIZACAO = -1
            AND (DS_CIDADE IS NOT NULL OR DS_UF IS NOT NULL OR DS_PAIS IS NOT NULL));

    IF @orfaos > 0
        THROW 50046, 'Ha lancamento com localizacao que nao achou chave. DROP cancelado.', 1;
END
GO

IF COL_LENGTH('gold.fato_movto_financ', 'DS_CIDADE') IS NOT NULL
BEGIN
    ALTER TABLE gold.fato_movto_financ DROP COLUMN DS_CIDADE, DS_UF, DS_PAIS;
    ALTER TABLE gold.fato_familia      DROP COLUMN DS_CIDADE, DS_UF, DS_PAIS;
END
GO

/* -------------------------------------------------------------
   5. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Um lugar por linha: cidade, UF e pais que antes se repetiam em cada '
       + N'lancamento dos fatos financeiros. '
       + N'EXISTE PARA RECEBER ATRIBUTO DE LUGAR. Latitude e longitude ja estao aqui, '
       + N'nulas; preenche-las e um UPDATE em cerca de 140 linhas, nao em 15 mil. Regiao, '
       + N'fuso e populacao entram do mesmo jeito, sem tocar nos fatos. '
       + N'AS GRAFIAS NAO FORAM CORRIGIDAS: a mesma cidade aparece sob UF diferente em 53 '
       + N'lancamentos (Belo Horizonte e Cidade A com DF, Brasilia com MG ou sem UF), e '
       + N'cada combinacao e um membro separado. Ao preencher coordenada, atencao: essas '
       + N'cidades tem mais de uma linha e devem receber a MESMA coordenada. A conferencia '
       + N'do script 45 lista quais sao.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', NULL, @d;

SET @d = N'Chave substituta do lugar. -1 representa lancamento sem localizacao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'SK_LOCALIZACAO', @d;
SET @d = N'Cidade como veio da origem, sem unificacao de grafia. Nula quando a origem so '
       + N'informou o pais.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'NM_CIDADE', @d;
SET @d = N'Sigla da unidade federativa, dois caracteres. Nula fora do Brasil e nos '
       + N'lancamentos em que nao foi informada.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'SG_UF', @d;
SET @d = N'Pais. Hoje so Brasil e um pais vizinho.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'NM_PAIS', @d;
SET @d = N'Rotulo legivel do lugar, no formato Cidade/UF - Pais. CALCULADA E PERSISTED: '
       + N'acompanha sozinha qualquer correcao em cidade, UF ou pais, em vez de envelhecer '
       + N'calada. E a coluna para por num filtro de relatorio.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'NM_LOCALIZACAO', @d;
SET @d = N'Latitude em graus decimais. Nula ate alguem preencher - o motivo de a dimensao '
       + N'existir.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'VL_LATITUDE', @d;
SET @d = N'Longitude em graus decimais. Nula ate alguem preencher.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'VL_LONGITUDE', @d;
SET @d = N'LINHAGEM: quando o lugar entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_localizacao', 'DT_CARGA', @d;

SET @d = N'Chave para gold.dim_localizacao: onde o lancamento aconteceu. -1 quando a '
       + N'origem nao informou. Substituiu DS_CIDADE, DS_UF e DS_PAIS, que seguem na '
       + N'silver e na bronze para auditoria.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_LOCALIZACAO', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia',      'SK_LOCALIZACAO', @d;
GO

/* -------------------------------------------------------------
   6. Conferencia
   ------------------------------------------------------------- */

SELECT 'membros na dimensao' AS conferencia,
       CAST(COUNT(*) AS varchar(20)) AS valor
FROM gold.dim_localizacao
UNION ALL SELECT 'colunas de texto removidas',
    CASE WHEN COL_LENGTH('gold.fato_movto_financ','DS_CIDADE') IS NULL
          AND COL_LENGTH('gold.fato_familia','DS_CIDADE') IS NULL
         THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'movto sem localizacao (-1)',
    CAST((SELECT COUNT(*) FROM gold.fato_movto_financ WHERE SK_LOCALIZACAO = -1) AS varchar(20))
UNION ALL SELECT 'familia sem localizacao (-1)',
    CAST((SELECT COUNT(*) FROM gold.fato_familia WHERE SK_LOCALIZACAO = -1) AS varchar(20))
UNION ALL SELECT 'coordenadas preenchidas',
    CAST((SELECT COUNT(*) FROM gold.dim_localizacao WHERE VL_LATITUDE IS NOT NULL) AS varchar(20));

-- A lacuna declarada no cabecalho, impressa toda vez: cidade que
-- aparece sob mais de uma UF e vai pedir coordenada repetida.
SELECT d.NM_LOCALIZACAO,
       (SELECT COUNT(*) FROM gold.fato_movto_financ f
         WHERE f.SK_LOCALIZACAO = d.SK_LOCALIZACAO) AS lancamentos_movto
FROM gold.dim_localizacao d
WHERE d.NM_CIDADE IN (
        SELECT NM_CIDADE FROM gold.dim_localizacao
        WHERE NM_CIDADE IS NOT NULL
        GROUP BY NM_CIDADE HAVING COUNT(DISTINCT ISNULL(SG_UF,'~')) > 1)
ORDER BY d.NM_CIDADE, lancamentos_movto DESC;
GO
