/* =============================================================
   manzo-dados | 30 - Alinha o vocabulario de "contexto" para "tag"
   -------------------------------------------------------------
   ponte_contexto        -> ponte_tag
   dim_tag.SK_CONTEXTO   -> SK_TAG
   dim_tag.NM_CONTEXTO   -> NM_TAG
   ponte_tag.SK_CONTEXTO -> SK_TAG

   Termina o que o 29 comecou. Ali a dimensao passou a chamar
   dim_tag, mas as colunas e a ponte seguiram com o nome antigo do
   assunto - e "dim_tag.SK_CONTEXTO" convida ao erro de quem le.

   DUAS OBSERVACOES SOBRE RENOMEAR COLUNA:

   1. AS DESCRICOES SOBREVIVEM. As extended properties gravadas pelo
      sp_documenta sao chaveadas por object_id + column_id, e o
      column_id nao muda no rename. Nenhuma documentacao se perde,
      e nao e preciso reaplicar o script de origem.

   2. A CHAVE ESTRANGEIRA SOBREVIVE. FKs sao definidas por
      column_id, nao por nome. Renomear as duas pontas em qualquer
      ordem mantem a integridade - o banco nunca fica com a
      referencia solta.

   ORDEM: a ponte e renomeada antes das suas colunas, e o resto do
   script ja se refere a ela pelo nome novo. Rodar de novo e seguro
   porque cada passo checa se o nome antigo ainda existe.

   Pre-requisitos: 28_gold_tag.sql, 29_renomeia_gold.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. A tabela ponte
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.ponte_contexto') IS NOT NULL
    EXEC sp_rename 'gold.ponte_contexto', 'ponte_tag';
GO

/* -------------------------------------------------------------
   2. As colunas
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_tag', 'SK_CONTEXTO') IS NOT NULL
    EXEC sp_rename 'gold.dim_tag.SK_CONTEXTO', 'SK_TAG', 'COLUMN';
GO
IF COL_LENGTH('gold.dim_tag', 'NM_CONTEXTO') IS NOT NULL
    EXEC sp_rename 'gold.dim_tag.NM_CONTEXTO', 'NM_TAG', 'COLUMN';
GO
IF COL_LENGTH('gold.ponte_tag', 'SK_CONTEXTO') IS NOT NULL
    EXEC sp_rename 'gold.ponte_tag.SK_CONTEXTO', 'SK_TAG', 'COLUMN';
GO

/* -------------------------------------------------------------
   3. Constraints e indices da ponte
   ------------------------------------------------------------- */

DECLARE @de sysname, @para sysname;
DECLARE renomear CURSOR LOCAL FAST_FORWARD FOR
    SELECT * FROM (VALUES
        ('PK_ponte_contexto',    'PK_ponte_tag'),
        ('UQ_ponte_contexto',    'UQ_ponte_tag'),
        ('FK_ponte_contexto',    'FK_ponte_tag'),
        ('DF_ponte_contexto_dt', 'DF_ponte_tag_dt')
    ) AS x(de, para);

OPEN renomear;
FETCH NEXT FROM renomear INTO @de, @para;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF OBJECT_ID('gold.' + @de) IS NOT NULL AND OBJECT_ID('gold.' + @para) IS NULL
    BEGIN
        -- Qualificado pelo schema: sem isso o sp_rename recusa
        -- constraint com "@objname e ambiguo".
        DECLARE @alvo nvarchar(400) = N'gold.' + @de;
        EXEC sp_rename @objname = @alvo, @newname = @para, @objtype = 'OBJECT';
    END
    FETCH NEXT FROM renomear INTO @de, @para;
END
CLOSE renomear;
DEALLOCATE renomear;
GO

DECLARE @i sysname, @novo sysname;
DECLARE indices CURSOR LOCAL FAST_FORWARD FOR
    SELECT * FROM (VALUES
        ('IX_ponte_contexto_hash', 'IX_ponte_tag_hash'),
        ('IX_ponte_contexto_ctx',  'IX_ponte_tag_sk')
    ) AS x(i, novo);

OPEN indices;
FETCH NEXT FROM indices INTO @i, @novo;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes
                WHERE name = @i AND object_id = OBJECT_ID('gold.ponte_tag'))
    BEGIN
        DECLARE @alvoi nvarchar(400) = N'gold.ponte_tag.' + @i;
        EXEC sp_rename @objname = @alvoi, @newname = @novo, @objtype = 'INDEX';
    END
    FETCH NEXT FROM indices INTO @i, @novo;
END
CLOSE indices;
DEALLOCATE indices;
GO

/* -------------------------------------------------------------
   4. Conferencia
   ------------------------------------------------------------- */

SELECT 'ponte_tag existe' AS conferencia,
       CASE WHEN OBJECT_ID('gold.ponte_tag') IS NOT NULL THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'ponte_contexto sumiu',
       CASE WHEN OBJECT_ID('gold.ponte_contexto') IS NULL THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'dim_tag.SK_TAG',
       CASE WHEN COL_LENGTH('gold.dim_tag','SK_TAG') IS NOT NULL THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'dim_tag.NM_TAG',
       CASE WHEN COL_LENGTH('gold.dim_tag','NM_TAG') IS NOT NULL THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'ponte_tag.SK_TAG',
       CASE WHEN COL_LENGTH('gold.ponte_tag','SK_TAG') IS NOT NULL THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'descricoes preservadas',
       CAST((SELECT COUNT(*) FROM sys.extended_properties ep
              WHERE ep.class = 1 AND ep.name = 'MS_Description'
                AND ep.major_id IN (OBJECT_ID('gold.dim_tag'),
                                    OBJECT_ID('gold.ponte_tag'))
                AND ep.minor_id > 0) AS varchar(10)) + ' colunas';

SELECT COUNT(*) AS ligacoes, COUNT(DISTINCT SK_TAG) AS tags_usadas
FROM gold.ponte_tag;
GO
