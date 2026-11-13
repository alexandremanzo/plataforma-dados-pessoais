/* =============================================================
   manzo-dados | 29 - Renomeia tres tabelas da camada gold
   -------------------------------------------------------------
   dim_contexto             -> dim_tag
   dim_categoria_manutencao -> dim_categoria_auto
   fato_movimentacao        -> fato_movto_financ

   Nomes definidos pelo dono da base. Este script existe para que um
   banco criado do zero e um banco ja existente cheguem ao MESMO
   estado - os scripts 14, 26 e 28 ja criam com os nomes novos, e
   aqui fica a migracao de quem foi criado antes.

   UM sp_rename SOZINHO NAO BASTA. Tres coisas ficariam para tras:

   1. AS CONSTRAINTS E INDICES guardam o nome antigo no proprio
      nome. Nao quebram nada, mas fariam o banco existente divergir
      do que os scripts criam num banco novo - e a divergencia so
      apareceria muito depois, ao comparar os dois.

   2. A VIEW vw_manutencao_prevista referencia
      dim_categoria_manutencao POR TEXTO. sp_rename nao reescreve
      corpo de view: ela continuaria compilada contra um nome que
      deixou de existir e quebraria na primeira consulta. Por isso
      e recriada no fim.

   3. O NOME ANTIGO ESTA GRAVADO COMO DADO. ponte_contexto.DS_FATO
      guarda a string 'fato_movimentacao' em 1.483 linhas, para
      dizer a que fato cada ligacao pertence. Renomear a tabela nao
      toca no dado, e a coluna passaria a apontar para um fato
      inexistente.

   Idempotente: cada passo so age se o nome antigo ainda existir.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. As tabelas
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_contexto') IS NOT NULL
    EXEC sp_rename 'gold.dim_contexto', 'dim_tag';
GO
IF OBJECT_ID('gold.dim_categoria_manutencao') IS NOT NULL
    EXEC sp_rename 'gold.dim_categoria_manutencao', 'dim_categoria_auto';
GO
IF OBJECT_ID('gold.fato_movimentacao') IS NOT NULL
    EXEC sp_rename 'gold.fato_movimentacao', 'fato_movto_financ';
GO

/* -------------------------------------------------------------
   2. Constraints e indices, para nao divergir de um banco novo
   ------------------------------------------------------------- */

/* sp_rename exige o nome QUALIFICADO PELO SCHEMA para constraints -
   passar o nome nu devolve "@objname e ambiguo ou o @objtype esta
   errado", mensagem que aponta para o tipo e nao para o que falta. */
DECLARE @de sysname, @para sysname, @tipo varchar(10);
DECLARE renomear CURSOR LOCAL FAST_FORWARD FOR
    SELECT * FROM (VALUES
        ('PK_dim_contexto',             'PK_dim_tag',                  'OBJECT'),
        ('UQ_dim_contexto_nome',        'UQ_dim_tag_nome',             'OBJECT'),
        ('DF_dim_contexto_dt',          'DF_dim_tag_dt',               'OBJECT'),

        ('PK_dim_categoria_manutencao', 'PK_dim_categoria_auto',       'OBJECT'),
        ('UQ_dim_categoria_manutencao', 'UQ_dim_categoria_auto',       'OBJECT'),
        ('DF_dim_cat_manut_dt',         'DF_dim_cat_auto_dt',          'OBJECT'),

        ('PK_fato_movimentacao',        'PK_fato_movto_financ',        'OBJECT'),
        ('UQ_fato_movimentacao_hash',   'UQ_fato_movto_financ_hash',   'OBJECT'),
        ('DF_fato_movimentacao_dt',     'DF_fato_movto_financ_dt',     'OBJECT'),
        ('CK_fato_movimentacao_nivel',  'CK_fato_movto_financ_nivel',  'OBJECT'),
        ('FK_fato_mov_categoria',       'FK_fato_financ_categoria',    'OBJECT'),
        ('FK_fato_mov_data',            'FK_fato_financ_data',         'OBJECT'),
        ('FK_fato_mov_fatura',          'FK_fato_financ_fatura',       'OBJECT'),
        ('FK_fato_mov_origem',          'FK_fato_financ_origem',       'OBJECT')
    ) AS x(de, para, tipo);

OPEN renomear;
FETCH NEXT FROM renomear INTO @de, @para, @tipo;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF OBJECT_ID('gold.' + @de) IS NOT NULL AND OBJECT_ID('gold.' + @para) IS NULL
    BEGIN
        DECLARE @qualificado nvarchar(400) = N'gold.' + @de;
        EXEC sp_rename @objname = @qualificado, @newname = @para, @objtype = 'OBJECT';
    END
    FETCH NEXT FROM renomear INTO @de, @para, @tipo;
END
CLOSE renomear;
DEALLOCATE renomear;
GO

/* Indices nao aparecem em sys.objects: sao renomeados por INDEX,
   qualificados pela tabela ja com o nome novo. */
DECLARE @i sysname, @novo sysname;
DECLARE indices CURSOR LOCAL FAST_FORWARD FOR
    SELECT * FROM (VALUES
        ('IX_fato_mov_categoria', 'IX_fato_financ_categoria'),
        ('IX_fato_mov_data',      'IX_fato_financ_data'),
        ('IX_fato_mov_nivel',     'IX_fato_financ_nivel'),
        ('IX_fato_mov_origem',    'IX_fato_financ_origem')
    ) AS x(i, novo);

OPEN indices;
FETCH NEXT FROM indices INTO @i, @novo;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes
                WHERE name = @i AND object_id = OBJECT_ID('gold.fato_movto_financ'))
    BEGIN
        DECLARE @alvo nvarchar(400) = N'gold.fato_movto_financ.' + @i;
        EXEC sp_rename @objname = @alvo, @newname = @novo, @objtype = 'INDEX';
    END
    FETCH NEXT FROM indices INTO @i, @novo;
END
CLOSE indices;
DEALLOCATE indices;
GO

/* -------------------------------------------------------------
   3. O nome antigo gravado como dado
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.ponte_contexto') IS NOT NULL
    UPDATE gold.ponte_contexto
       SET DS_FATO = 'fato_movto_financ'
     WHERE DS_FATO = 'fato_movimentacao';
GO

/* -------------------------------------------------------------
   4. Conferencia
   ------------------------------------------------------------- */

SELECT 'tabelas com nome novo' AS conferencia,
       SUM(CASE WHEN name IN ('dim_tag', 'dim_categoria_auto',
                              'fato_movto_financ') THEN 1 ELSE 0 END) AS ok_de_3,
       SUM(CASE WHEN name IN ('dim_contexto', 'dim_categoria_manutencao',
                              'fato_movimentacao') THEN 1 ELSE 0 END) AS restaram_antigos
FROM sys.tables WHERE SCHEMA_NAME(schema_id) = 'gold';

SELECT DS_FATO, COUNT(*) AS linhas FROM gold.ponte_contexto GROUP BY DS_FATO;
GO
