/* =============================================================
   manzo-dados | 36 - Remove a dimensao de combinacoes
   -------------------------------------------------------------
   Apaga SK_CATEGORIA_GASTO dos dois fatos e a tabela
   gold.dim_categoria_gasto.

   SEPARADO DO 35 DE PROPOSITO. A migracao podia ser conferida antes
   de virar irreversivel, e a conferencia que autoriza este script e
   a do fim do 35: o trio resolvido pelas tres dimensoes novas tem
   de ser identico ao que a dimensao antiga dava, em TODAS as linhas
   dos dois fatos. Deu zero diferencas.

   POR QUE REMOVER, e nao deixar convivendo: dois caminhos para a
   mesma informacao divergem na primeira carga em que so um for
   atualizado, e ai alguem usa o errado no relatorio sem perceber.

   ATENCAO: o Power BI quebra nas visualizacoes que usavam
   dim_categoria_gasto. E consequencia esperada - as tres novas
   substituem, mas as relacoes e medidas precisam ser refeitas.

   Pre-requisitos: 35_migra_classificacao.sql, conferido
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* Trava de seguranca: se por algum motivo as chaves novas nao
   estiverem preenchidas, o script para antes de destruir a origem
   da informacao. */
IF EXISTS (SELECT 1 FROM gold.fato_movto_financ WHERE SK_CATEGORIA_FINANC IS NULL)
   OR EXISTS (SELECT 1 FROM gold.fato_familia WHERE SK_CATEGORIA_FINANC IS NULL)
BEGIN
    RAISERROR('Ha fato sem SK_CATEGORIA_FINANC. Rode o 35 antes.', 16, 1);
    SET NOEXEC ON;
END
GO

/* -------------------------------------------------------------
   1. Chaves estrangeiras e indices que dependem da coluna
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.FK_fato_financ_categoria') IS NOT NULL
    ALTER TABLE gold.fato_movto_financ DROP CONSTRAINT FK_fato_financ_categoria;
IF OBJECT_ID('gold.FK_fato_fam_categoria') IS NOT NULL
    ALTER TABLE gold.fato_familia DROP CONSTRAINT FK_fato_fam_categoria;
GO

IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_fato_financ_categoria'
            AND object_id = OBJECT_ID('gold.fato_movto_financ'))
    DROP INDEX IX_fato_financ_categoria ON gold.fato_movto_financ;
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_fato_fam_categoria'
            AND object_id = OBJECT_ID('gold.fato_familia'))
    DROP INDEX IX_fato_fam_categoria ON gold.fato_familia;
GO

/* -------------------------------------------------------------
   2. As colunas
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_movto_financ', 'SK_CATEGORIA_GASTO') IS NOT NULL
    ALTER TABLE gold.fato_movto_financ DROP COLUMN SK_CATEGORIA_GASTO;
IF COL_LENGTH('gold.fato_familia', 'SK_CATEGORIA_GASTO') IS NOT NULL
    ALTER TABLE gold.fato_familia DROP COLUMN SK_CATEGORIA_GASTO;
GO

/* -------------------------------------------------------------
   3. A tabela
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_categoria_gasto') IS NOT NULL
    DROP TABLE gold.dim_categoria_gasto;
GO

SET NOEXEC OFF;
GO

SELECT 'dim_categoria_gasto removida' AS conferencia,
       CASE WHEN OBJECT_ID('gold.dim_categoria_gasto') IS NULL THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'coluna fora do fato_movto_financ',
       CASE WHEN COL_LENGTH('gold.fato_movto_financ', 'SK_CATEGORIA_GASTO') IS NULL
            THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'coluna fora do fato_familia',
       CASE WHEN COL_LENGTH('gold.fato_familia', 'SK_CATEGORIA_GASTO') IS NULL
            THEN 'sim' ELSE 'NAO' END;
GO
