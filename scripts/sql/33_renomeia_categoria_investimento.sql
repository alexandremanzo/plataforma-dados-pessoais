/* =============================================================
   manzo-dados | 33 - dim_categoria -> dim_categoria_investimento
   -------------------------------------------------------------
   gold.dim_categoria             -> gold.dim_categoria_investimento
   dim_categoria.SK_CATEGORIA     -> SK_CATEGORIA_INVESTIMENTO
   fato_investimento.SK_CATEGORIA -> SK_CATEGORIA_INVESTIMENTO

   O nome antigo era generico demais para conviver com a
   classificacao financeira: "dim_categoria" e "dim_categoria_gasto"
   lado a lado nao diziam qual era qual, e SK_CATEGORIA aparecia em
   dois fatos apontando para dimensoes diferentes.

   O 04_gold_investimentos.sql ja cria com os nomes novos; este
   script migra o banco que foi criado antes, para que os dois
   cheguem ao mesmo estado.

   DUAS ARMADILHAS DO sp_rename, ja pagas no 29:
   - constraint exige o nome QUALIFICADO PELO SCHEMA, senao devolve
     "@objname e ambiguo", mensagem que aponta para o tipo errado
   - coluna exige @objtype = 'COLUMN' e o nome em tres partes

   A chave estrangeira sobrevive: FK e definida por column_id, e nao
   por nome. As descricoes do sp_documenta tambem, porque extended
   property e chaveada por object_id + column_id.

   Pre-requisitos: 04_gold_investimentos.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Tabela
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_categoria') IS NOT NULL
   AND OBJECT_ID('gold.dim_categoria_investimento') IS NULL
    EXEC sp_rename 'gold.dim_categoria', 'dim_categoria_investimento';
GO

/* -------------------------------------------------------------
   2. Colunas, nas duas pontas
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_categoria_investimento', 'SK_CATEGORIA') IS NOT NULL
    EXEC sp_rename 'gold.dim_categoria_investimento.SK_CATEGORIA',
                   'SK_CATEGORIA_INVESTIMENTO', 'COLUMN';
GO
IF COL_LENGTH('gold.fato_investimento', 'SK_CATEGORIA') IS NOT NULL
    EXEC sp_rename 'gold.fato_investimento.SK_CATEGORIA',
                   'SK_CATEGORIA_INVESTIMENTO', 'COLUMN';
GO

/* -------------------------------------------------------------
   3. Constraints e indices
   ------------------------------------------------------------- */

DECLARE @de sysname, @para sysname;
DECLARE renomear CURSOR LOCAL FAST_FORWARD FOR
    SELECT * FROM (VALUES
        ('PK_dim_categoria',      'PK_dim_categoria_investimento'),
        ('UQ_dim_categoria_nome', 'UQ_dim_categoria_investimento_nome'),
        ('DF_dim_categoria_dt',   'DF_dim_categoria_investimento_dt'),
        ('FK_fato_inv_categoria', 'FK_fato_inv_categoria_investimento')
    ) AS x(de, para);

OPEN renomear;
FETCH NEXT FROM renomear INTO @de, @para;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF OBJECT_ID('gold.' + @de) IS NOT NULL AND OBJECT_ID('gold.' + @para) IS NULL
    BEGIN
        DECLARE @alvo nvarchar(400) = N'gold.' + @de;
        EXEC sp_rename @objname = @alvo, @newname = @para, @objtype = 'OBJECT';
    END
    FETCH NEXT FROM renomear INTO @de, @para;
END
CLOSE renomear;
DEALLOCATE renomear;
GO

IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_fato_inv_categoria'
            AND object_id = OBJECT_ID('gold.fato_investimento'))
   AND NOT EXISTS (SELECT 1 FROM sys.indexes
                    WHERE name = 'IX_fato_inv_categoria_investimento'
                      AND object_id = OBJECT_ID('gold.fato_investimento'))
    EXEC sp_rename 'gold.fato_investimento.IX_fato_inv_categoria',
                   'IX_fato_inv_categoria_investimento', 'INDEX';
GO

/* -------------------------------------------------------------
   4. Conferencia
   ------------------------------------------------------------- */

SELECT 'tabela renomeada' AS conferencia,
       CASE WHEN OBJECT_ID('gold.dim_categoria_investimento') IS NOT NULL
             AND OBJECT_ID('gold.dim_categoria') IS NULL
            THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'coluna na dimensao',
       CASE WHEN COL_LENGTH('gold.dim_categoria_investimento',
                            'SK_CATEGORIA_INVESTIMENTO') IS NOT NULL
            THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'coluna no fato',
       CASE WHEN COL_LENGTH('gold.fato_investimento',
                            'SK_CATEGORIA_INVESTIMENTO') IS NOT NULL
            THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'descricoes preservadas',
       CAST((SELECT COUNT(*) FROM sys.extended_properties
              WHERE class = 1 AND name = 'MS_Description' AND minor_id > 0
                AND major_id = OBJECT_ID('gold.dim_categoria_investimento'))
            AS varchar(10)) + ' colunas';

SELECT COUNT(*) AS categorias FROM gold.dim_categoria_investimento;
GO
