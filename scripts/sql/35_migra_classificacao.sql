/* =============================================================
   manzo-dados | 35 - Migra a classificacao para as tres dimensoes
   -------------------------------------------------------------
   Popula dim_area_financ, dim_categoria_financ e dim_grupo_financ
   a partir de dim_categoria_gasto, e acrescenta as tres chaves aos
   fatos gold.fato_movto_financ e gold.fato_familia.

   A PASSAGEM E POR JOIN ATRAVES DA CHAVE ANTIGA, e e isso que
   garante que nenhuma classificacao se perca: cada linha do fato ja
   aponta para um trio, e o trio e desmembrado nos tres membros
   correspondentes. Nao ha reclassificacao nem palpite.

   ESTE SCRIPT NAO REMOVE NADA. A coluna SK_CATEGORIA_GASTO e a
   tabela dim_categoria_gasto continuam de pe ate a conferencia
   provar que os trios batem - a remocao esta no 36, separada de
   proposito, para que a migracao possa ser conferida antes de ser
   irreversivel.

   Pre-requisitos: 34_dim_financ.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Popula as tres dimensoes
   ------------------------------------------------------------- */

INSERT INTO gold.dim_area_financ (NM_AREA)
SELECT DISTINCT g.DS_AREA
FROM gold.dim_categoria_gasto g
WHERE NOT EXISTS (SELECT 1 FROM gold.dim_area_financ d WHERE d.NM_AREA = g.DS_AREA);

INSERT INTO gold.dim_categoria_financ (NM_CATEGORIA, FL_CLASSIFICADO)
SELECT DISTINCT g.DS_CATEGORIA,
       CASE WHEN g.DS_CATEGORIA = 'A classificar' THEN 0 ELSE 1 END
FROM gold.dim_categoria_gasto g
WHERE NOT EXISTS (SELECT 1 FROM gold.dim_categoria_financ d
                   WHERE d.NM_CATEGORIA = g.DS_CATEGORIA);

INSERT INTO gold.dim_grupo_financ (NM_GRUPO)
SELECT DISTINCT g.DS_GRUPO
FROM gold.dim_categoria_gasto g
WHERE NOT EXISTS (SELECT 1 FROM gold.dim_grupo_financ d WHERE d.NM_GRUPO = g.DS_GRUPO);
GO

/* -------------------------------------------------------------
   2. Colunas nos fatos, anulaveis por enquanto
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_movto_financ', 'SK_AREA_FINANC') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD SK_AREA_FINANC int NULL;
GO
IF COL_LENGTH('gold.fato_movto_financ', 'SK_CATEGORIA_FINANC') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD SK_CATEGORIA_FINANC int NULL;
GO
IF COL_LENGTH('gold.fato_movto_financ', 'SK_GRUPO_FINANC') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD SK_GRUPO_FINANC int NULL;
GO

IF COL_LENGTH('gold.fato_familia', 'SK_AREA_FINANC') IS NULL
    ALTER TABLE gold.fato_familia ADD SK_AREA_FINANC int NULL;
GO
IF COL_LENGTH('gold.fato_familia', 'SK_CATEGORIA_FINANC') IS NULL
    ALTER TABLE gold.fato_familia ADD SK_CATEGORIA_FINANC int NULL;
GO
IF COL_LENGTH('gold.fato_familia', 'SK_GRUPO_FINANC') IS NULL
    ALTER TABLE gold.fato_familia ADD SK_GRUPO_FINANC int NULL;
GO

/* -------------------------------------------------------------
   3. Preenche por JOIN atraves da chave antiga
   ------------------------------------------------------------- */

UPDATE f
   SET f.SK_AREA_FINANC      = a.SK_AREA_FINANC,
       f.SK_CATEGORIA_FINANC = c.SK_CATEGORIA_FINANC,
       f.SK_GRUPO_FINANC     = g.SK_GRUPO_FINANC
FROM gold.fato_movto_financ f
JOIN gold.dim_categoria_gasto d ON d.SK_CATEGORIA_GASTO = f.SK_CATEGORIA_GASTO
JOIN gold.dim_area_financ      a ON a.NM_AREA      = d.DS_AREA
JOIN gold.dim_categoria_financ c ON c.NM_CATEGORIA = d.DS_CATEGORIA
JOIN gold.dim_grupo_financ     g ON g.NM_GRUPO     = d.DS_GRUPO;

UPDATE f
   SET f.SK_AREA_FINANC      = a.SK_AREA_FINANC,
       f.SK_CATEGORIA_FINANC = c.SK_CATEGORIA_FINANC,
       f.SK_GRUPO_FINANC     = g.SK_GRUPO_FINANC
FROM gold.fato_familia f
JOIN gold.dim_categoria_gasto d ON d.SK_CATEGORIA_GASTO = f.SK_CATEGORIA_GASTO
JOIN gold.dim_area_financ      a ON a.NM_AREA      = d.DS_AREA
JOIN gold.dim_categoria_financ c ON c.NM_CATEGORIA = d.DS_CATEGORIA
JOIN gold.dim_grupo_financ     g ON g.NM_GRUPO     = d.DS_GRUPO;
GO

/* O membro -1 do fato aponta para "A classificar" na dimensao antiga,
   entao o JOIN acima ja o resolve. Isto pega qualquer sobra. */
UPDATE gold.fato_movto_financ
   SET SK_AREA_FINANC = -1, SK_CATEGORIA_FINANC = -1, SK_GRUPO_FINANC = -1
 WHERE SK_AREA_FINANC IS NULL;

UPDATE gold.fato_familia
   SET SK_AREA_FINANC = -1, SK_CATEGORIA_FINANC = -1, SK_GRUPO_FINANC = -1
 WHERE SK_AREA_FINANC IS NULL;
GO

/* -------------------------------------------------------------
   4. NOT NULL e chaves estrangeiras
   ------------------------------------------------------------- */

ALTER TABLE gold.fato_movto_financ ALTER COLUMN SK_AREA_FINANC      int NOT NULL;
ALTER TABLE gold.fato_movto_financ ALTER COLUMN SK_CATEGORIA_FINANC int NOT NULL;
ALTER TABLE gold.fato_movto_financ ALTER COLUMN SK_GRUPO_FINANC     int NOT NULL;
ALTER TABLE gold.fato_familia      ALTER COLUMN SK_AREA_FINANC      int NOT NULL;
ALTER TABLE gold.fato_familia      ALTER COLUMN SK_CATEGORIA_FINANC int NOT NULL;
ALTER TABLE gold.fato_familia      ALTER COLUMN SK_GRUPO_FINANC     int NOT NULL;
GO

IF OBJECT_ID('gold.FK_fato_financ_area') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD CONSTRAINT FK_fato_financ_area
        FOREIGN KEY (SK_AREA_FINANC) REFERENCES gold.dim_area_financ (SK_AREA_FINANC);
IF OBJECT_ID('gold.FK_fato_financ_cat') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD CONSTRAINT FK_fato_financ_cat
        FOREIGN KEY (SK_CATEGORIA_FINANC)
        REFERENCES gold.dim_categoria_financ (SK_CATEGORIA_FINANC);
IF OBJECT_ID('gold.FK_fato_financ_grupo') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD CONSTRAINT FK_fato_financ_grupo
        FOREIGN KEY (SK_GRUPO_FINANC) REFERENCES gold.dim_grupo_financ (SK_GRUPO_FINANC);

IF OBJECT_ID('gold.FK_fato_fam_area') IS NULL
    ALTER TABLE gold.fato_familia ADD CONSTRAINT FK_fato_fam_area
        FOREIGN KEY (SK_AREA_FINANC) REFERENCES gold.dim_area_financ (SK_AREA_FINANC);
IF OBJECT_ID('gold.FK_fato_fam_cat') IS NULL
    ALTER TABLE gold.fato_familia ADD CONSTRAINT FK_fato_fam_cat
        FOREIGN KEY (SK_CATEGORIA_FINANC)
        REFERENCES gold.dim_categoria_financ (SK_CATEGORIA_FINANC);
IF OBJECT_ID('gold.FK_fato_fam_grupo') IS NULL
    ALTER TABLE gold.fato_familia ADD CONSTRAINT FK_fato_fam_grupo
        FOREIGN KEY (SK_GRUPO_FINANC) REFERENCES gold.dim_grupo_financ (SK_GRUPO_FINANC);
GO

CREATE INDEX IX_fato_financ_area  ON gold.fato_movto_financ (SK_AREA_FINANC);
CREATE INDEX IX_fato_financ_cat   ON gold.fato_movto_financ (SK_CATEGORIA_FINANC);
CREATE INDEX IX_fato_financ_grupo ON gold.fato_movto_financ (SK_GRUPO_FINANC);
GO

DECLARE @d nvarchar(3750);
SET @d = N'Chave para gold.dim_area_financ - nivel 1 da classificacao.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_AREA_FINANC', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_AREA_FINANC', @d;
SET @d = N'Chave para gold.dim_categoria_financ - nivel 2, o principal para analise.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_CATEGORIA_FINANC', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_CATEGORIA_FINANC', @d;
SET @d = N'Chave para gold.dim_grupo_financ - nivel 3, o mais fino. Os tres niveis sao '
       + N'dimensoes independentes: a combinacao de cada lancamento vive AQUI, no fato, e '
       + N'nao numa dimensao de trios.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_GRUPO_FINANC', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'SK_GRUPO_FINANC', @d;
GO

/* -------------------------------------------------------------
   5. A CONFERENCIA QUE AUTORIZA O 36
   ------------------------------------------------------------- */

SELECT 'movto: trios diferentes do original' AS conferencia, COUNT(*) AS n
FROM gold.fato_movto_financ f
JOIN gold.dim_categoria_gasto d ON d.SK_CATEGORIA_GASTO = f.SK_CATEGORIA_GASTO
JOIN gold.dim_area_financ      a ON a.SK_AREA_FINANC      = f.SK_AREA_FINANC
JOIN gold.dim_categoria_financ c ON c.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
JOIN gold.dim_grupo_financ     g ON g.SK_GRUPO_FINANC     = f.SK_GRUPO_FINANC
WHERE a.NM_AREA <> d.DS_AREA OR c.NM_CATEGORIA <> d.DS_CATEGORIA
   OR g.NM_GRUPO <> d.DS_GRUPO
UNION ALL
SELECT 'familia: trios diferentes do original', COUNT(*)
FROM gold.fato_familia f
JOIN gold.dim_categoria_gasto d ON d.SK_CATEGORIA_GASTO = f.SK_CATEGORIA_GASTO
JOIN gold.dim_area_financ      a ON a.SK_AREA_FINANC      = f.SK_AREA_FINANC
JOIN gold.dim_categoria_financ c ON c.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
JOIN gold.dim_grupo_financ     g ON g.SK_GRUPO_FINANC     = f.SK_GRUPO_FINANC
WHERE a.NM_AREA <> d.DS_AREA OR c.NM_CATEGORIA <> d.DS_CATEGORIA
   OR g.NM_GRUPO <> d.DS_GRUPO;

SELECT 'dim_area_financ' AS dimensao, COUNT(*) AS linhas FROM gold.dim_area_financ
UNION ALL SELECT 'dim_categoria_financ', COUNT(*) FROM gold.dim_categoria_financ
UNION ALL SELECT 'dim_grupo_financ', COUNT(*) FROM gold.dim_grupo_financ;
GO
