/* =============================================================
   manzo-dados | 00 - Utilitarios de documentacao
   -------------------------------------------------------------
   Cria dbo.sp_documenta, usada por todos os scripts de DDL para
   gravar a descricao de schemas, tabelas e colunas no proprio
   banco (extended property MS_Description).

   Essas descricoes sao a fonte do glossario de dados do projeto:
   em vez de manter um documento paralelo que envelhece, a
   documentacao vive junto do objeto e viaja com o backup.

   Idempotente: usa CREATE OR ALTER.
   ============================================================= */

USE [db-manzo];
GO

CREATE OR ALTER PROCEDURE dbo.sp_documenta
    @schema     sysname,
    @tabela     sysname       = NULL,
    @coluna     sysname       = NULL,
    @descricao  nvarchar(3750)
AS
BEGIN
    SET NOCOUNT ON;

    /* O nivel do objeto e deduzido pelos parametros informados:
         schema apenas            -> documenta o schema
         schema + tabela          -> documenta a tabela
         schema + tabela + coluna -> documenta a coluna              */

    DECLARE @existe bit = 0;

    IF @tabela IS NULL
    BEGIN
        IF SCHEMA_ID(@schema) IS NULL
        BEGIN
            RAISERROR('sp_documenta: schema [%s] nao existe.', 16, 1, @schema);
            RETURN;
        END

        SELECT @existe = 1
        FROM sys.extended_properties
        WHERE class = 3
          AND major_id = SCHEMA_ID(@schema)
          AND name = 'MS_Description';

        IF @existe = 1
            EXEC sys.sp_updateextendedproperty N'MS_Description', @descricao,
                 N'SCHEMA', @schema;
        ELSE
            EXEC sys.sp_addextendedproperty N'MS_Description', @descricao,
                 N'SCHEMA', @schema;
        RETURN;
    END

    DECLARE @object_id int = OBJECT_ID(QUOTENAME(@schema) + '.' + QUOTENAME(@tabela));

    IF @object_id IS NULL
    BEGIN
        RAISERROR('sp_documenta: objeto [%s].[%s] nao existe.', 16, 1, @schema, @tabela);
        RETURN;
    END

    /* As extended properties exigem o tipo correto no nivel 1: passar
       'TABLE' para uma view falha com o erro 15135. Como o parametro
       @tabela aceita os dois, o tipo e descoberto aqui.              */
    DECLARE @nivel1 nvarchar(10) =
        CASE WHEN EXISTS (SELECT 1 FROM sys.views WHERE object_id = @object_id)
             THEN N'VIEW' ELSE N'TABLE' END;

    IF @coluna IS NULL
    BEGIN
        SELECT @existe = 1
        FROM sys.extended_properties
        WHERE class = 1 AND major_id = @object_id AND minor_id = 0
          AND name = 'MS_Description';

        IF @existe = 1
            EXEC sys.sp_updateextendedproperty N'MS_Description', @descricao,
                 N'SCHEMA', @schema, @nivel1, @tabela;
        ELSE
            EXEC sys.sp_addextendedproperty N'MS_Description', @descricao,
                 N'SCHEMA', @schema, @nivel1, @tabela;
        RETURN;
    END

    DECLARE @column_id int =
        (SELECT column_id FROM sys.columns
         WHERE object_id = @object_id AND name = @coluna);

    IF @column_id IS NULL
    BEGIN
        RAISERROR('sp_documenta: coluna [%s].[%s].[%s] nao existe.',
                  16, 1, @schema, @tabela, @coluna);
        RETURN;
    END

    SELECT @existe = 1
    FROM sys.extended_properties
    WHERE class = 1 AND major_id = @object_id AND minor_id = @column_id
      AND name = 'MS_Description';

    IF @existe = 1
        EXEC sys.sp_updateextendedproperty N'MS_Description', @descricao,
             N'SCHEMA', @schema, @nivel1, @tabela, N'COLUMN', @coluna;
    ELSE
        EXEC sys.sp_addextendedproperty N'MS_Description', @descricao,
             N'SCHEMA', @schema, @nivel1, @tabela, N'COLUMN', @coluna;
END
GO

PRINT 'dbo.sp_documenta criada/atualizada.';
GO
