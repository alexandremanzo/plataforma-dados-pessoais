/* =============================================================
   manzo-dados | 42 - Atributos FL passam de bit para S/N
   -------------------------------------------------------------
   Converte as 23 colunas FL_ da camada GOLD de bit para char(1),
   com dominio S ou N.

   POR QUE SO A GOLD. E a camada que se consulta e que o Power BI le,
   onde o valor precisa ser legivel sem traducao. Bronze e silver
   seguem em bit: ali ninguem olha, e converter so traria risco. As
   cargas ja traduzem tipo entre camadas, entao isto nao cria excecao
   nova - e o mesmo lugar onde texto vira data e virgula vira ponto.

   O QUE MUDA PARA QUEM CONSULTA. A adesao aos habitos era uma medida
   so, AVG(FL_ADERENCIA), e funcionava porque a media ignora sozinha
   os habitos de contexto, que sao NULL. Agora exige uma expressao:

       AVG(CASE WHEN FL_ADERENCIA = 'S' THEN 1.0
                WHEN FL_ADERENCIA = 'N' THEN 0.0 END)

   O CASE SEM O SEGUNDO WHEN E O ERRO A EVITAR: um ELSE 0 no lugar
   dele transformaria "nao apurado" em "nao cumpriu", e a adesao
   despencaria sem nada ter acontecido. O mesmo vale para
   FL_MELHOROU, que e nulo quando nao ha medida anterior.

   O CHECK acrescentado faz o banco recusar qualquer outra letra - o
   dominio deixa de depender de disciplina da carga.

   Pre-requisitos: todos os anteriores
   Idempotente: ja convertida, nao faz nada.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

DECLARE @tabela sysname, @coluna sysname, @nulo bit, @sql nvarchar(max);
DECLARE @convertidas int = 0;

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT t.name, c.name, c.is_nullable
    FROM sys.columns c
    JOIN sys.tables t   ON t.object_id = c.object_id
    JOIN sys.schemas s  ON s.schema_id = t.schema_id
    JOIN sys.types ty   ON ty.user_type_id = c.user_type_id
    WHERE s.name = 'gold' AND c.name LIKE 'FL[_]%' AND ty.name = 'bit'
    ORDER BY t.name, c.name;

OPEN cur;
FETCH NEXT FROM cur INTO @tabela, @coluna, @nulo;

WHILE @@FETCH_STATUS = 0
BEGIN
    /* Coluna temporaria, copia traduzida, troca de nome. ALTER COLUMN
       direto de bit para char converteria 1 em '1', e nao em 'S'. */
    SET @sql = N'
        ALTER TABLE gold.' + QUOTENAME(@tabela)
        + N' ADD ' + QUOTENAME(@coluna + '_SN') + N' char(1) NULL;';
    EXEC sp_executesql @sql;

    SET @sql = N'
        UPDATE gold.' + QUOTENAME(@tabela) + N'
           SET ' + QUOTENAME(@coluna + '_SN') + N' =
               CASE WHEN ' + QUOTENAME(@coluna) + N' = 1 THEN ''S''
                    WHEN ' + QUOTENAME(@coluna) + N' = 0 THEN ''N'' END;';
    EXEC sp_executesql @sql;

    SET @sql = N'
        ALTER TABLE gold.' + QUOTENAME(@tabela)
        + N' DROP COLUMN ' + QUOTENAME(@coluna) + N';';
    EXEC sp_executesql @sql;

    /* sp_rename de coluna exige o nome em tres partes E o @objtype:
       sem ele, renomeia a tabela. */
    SET @sql = N'gold.' + @tabela + N'.' + @coluna + N'_SN';
    EXEC sp_rename @sql, @coluna, 'COLUMN';

    IF @nulo = 0
    BEGIN
        SET @sql = N'
            ALTER TABLE gold.' + QUOTENAME(@tabela)
            + N' ALTER COLUMN ' + QUOTENAME(@coluna) + N' char(1) NOT NULL;';
        EXEC sp_executesql @sql;
    END

    /* O dominio passa a ser do banco, e nao da disciplina da carga. */
    SET @sql = N'
        ALTER TABLE gold.' + QUOTENAME(@tabela)
        + N' ADD CONSTRAINT ' + QUOTENAME('CK_' + @tabela + '_' + @coluna)
        + N' CHECK (' + QUOTENAME(@coluna) + N' IN (''S'', ''N''));';
    EXEC sp_executesql @sql;

    SET @convertidas = @convertidas + 1;
    FETCH NEXT FROM cur INTO @tabela, @coluna, @nulo;
END

CLOSE cur;
DEALLOCATE cur;

PRINT CONCAT('Colunas FL convertidas para char(1): ', @convertidas);
GO

/* As views leem estas colunas e guardam o tipo antigo em cache. Sem o
   refresh, gold.vw_carga_ultima e gold.vw_manutencao_prevista passariam
   a devolver o tipo errado ate alguem recria-las. */
DECLARE @v sysname;
DECLARE cv CURSOR LOCAL FAST_FORWARD FOR
    SELECT s.name + '.' + v.name
    FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id
    WHERE s.name = 'gold';
OPEN cv;
FETCH NEXT FROM cv INTO @v;
WHILE @@FETCH_STATUS = 0
BEGIN
    EXEC sp_refreshview @v;
    FETCH NEXT FROM cv INTO @v;
END
CLOSE cv;
DEALLOCATE cv;
GO

SELECT t.name AS tabela, c.name AS coluna, ty.name AS tipo,
       CASE WHEN c.is_nullable = 1 THEN 'sim' ELSE 'nao' END AS aceita_nulo
FROM sys.columns c
JOIN sys.tables t  ON t.object_id = c.object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.types ty  ON ty.user_type_id = c.user_type_id
WHERE s.name = 'gold' AND c.name LIKE 'FL[_]%'
ORDER BY ty.name DESC, t.name, c.name;
GO

SELECT 'ainda em bit (deve ser 0)' AS conferencia, COUNT(*) AS n
FROM sys.columns c
JOIN sys.tables t  ON t.object_id = c.object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.types ty  ON ty.user_type_id = c.user_type_id
WHERE s.name = 'gold' AND c.name LIKE 'FL[_]%' AND ty.name = 'bit';
GO
