/* =============================================================
   manzo-dados | 34 - Tres dimensoes de classificacao financeira
   -------------------------------------------------------------
   gold.dim_area_financ
   gold.dim_categoria_financ
   gold.dim_grupo_financ

   Substituem gold.dim_categoria_gasto, que guardava a COMBINACAO
   dos tres niveis numa linha so.

   POR QUE SEPARAR. A dimensao antiga tinha 787 linhas para 13
   areas, 44 categorias e 510 grupos - ela era um catalogo de trios
   observados, e nao uma hierarquia. E a hierarquia de fato NAO
   EXISTE nestes dados:

       103 grupos aparecem sob mais de uma categoria
        23 categorias aparecem sob mais de uma area

   TRANSPORTE/Combustivel esta sob ESTILO DE VIDA em 212
   lancamentos e sob GASTOS ESSENCIAIS em 128 - e esta certo:
   combustivel para lazer e combustivel para trabalho sao decisoes
   diferentes. AREA NAO E PROPRIEDADE DA CATEGORIA, e uma decisao
   por lancamento. A dimensao unica fingia uma hierarquia que os
   dados nao tem.

   Com tres dimensoes o fato guarda a combinacao real de cada
   linha, e cada eixo filtra de forma independente.

   O QUE SE PERDE, declarado: o modelo deixa de recusar combinacoes
   que nunca aconteceram. Selecionar RENDA + Alimentacao passa a ser
   possivel e devolve vazio - inofensivo, e o oposto do risco de
   hoje, que e uma combinacao de ocorrencia unica parecer canonica.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('gold.dim_area_financ') IS NULL
BEGIN
    CREATE TABLE gold.dim_area_financ (
        SK_AREA_FINANC int IDENTITY(1,1) NOT NULL,
        NM_AREA        varchar(100) NOT NULL,
        DT_CARGA       datetime2(3) NOT NULL
            CONSTRAINT DF_dim_area_financ_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_area_financ PRIMARY KEY (SK_AREA_FINANC),
        CONSTRAINT UQ_dim_area_financ_nome UNIQUE (NM_AREA)
    );

    SET IDENTITY_INSERT gold.dim_area_financ ON;
    INSERT INTO gold.dim_area_financ (SK_AREA_FINANC, NM_AREA)
    VALUES (-1, 'Não informado');
    SET IDENTITY_INSERT gold.dim_area_financ OFF;
END
GO

IF OBJECT_ID('gold.dim_categoria_financ') IS NULL
BEGIN
    CREATE TABLE gold.dim_categoria_financ (
        SK_CATEGORIA_FINANC int IDENTITY(1,1) NOT NULL,
        NM_CATEGORIA        varchar(100) NOT NULL,
        FL_CLASSIFICADO     bit          NOT NULL,
        DT_CARGA            datetime2(3) NOT NULL
            CONSTRAINT DF_dim_categoria_financ_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_categoria_financ PRIMARY KEY (SK_CATEGORIA_FINANC),
        CONSTRAINT UQ_dim_categoria_financ_nome UNIQUE (NM_CATEGORIA)
    );

    SET IDENTITY_INSERT gold.dim_categoria_financ ON;
    INSERT INTO gold.dim_categoria_financ
        (SK_CATEGORIA_FINANC, NM_CATEGORIA, FL_CLASSIFICADO)
    VALUES (-1, 'Não informado', 0);
    SET IDENTITY_INSERT gold.dim_categoria_financ OFF;
END
GO

IF OBJECT_ID('gold.dim_grupo_financ') IS NULL
BEGIN
    CREATE TABLE gold.dim_grupo_financ (
        SK_GRUPO_FINANC int IDENTITY(1,1) NOT NULL,
        NM_GRUPO        varchar(100) NOT NULL,
        DT_CARGA        datetime2(3) NOT NULL
            CONSTRAINT DF_dim_grupo_financ_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_grupo_financ PRIMARY KEY (SK_GRUPO_FINANC),
        CONSTRAINT UQ_dim_grupo_financ_nome UNIQUE (NM_GRUPO)
    );

    SET IDENTITY_INSERT gold.dim_grupo_financ ON;
    INSERT INTO gold.dim_grupo_financ (SK_GRUPO_FINANC, NM_GRUPO)
    VALUES (-1, 'Não informado');
    SET IDENTITY_INSERT gold.dim_grupo_financ OFF;
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Nivel 1 da classificacao financeira: GASTOS ESSENCIAIS, ESTILO DE VIDA, '
       + N'RENDA, TRANSFERENCIA e outras. Compartilhada por gold.fato_movto_financ e '
       + N'gold.fato_familia, o que permite comparar gasto pessoal e familiar pelo mesmo '
       + N'eixo. '
       + N'E DIMENSAO PROPRIA, e nao um nivel dentro da categoria, porque a area NAO E '
       + N'PROPRIEDADE DA CATEGORIA nesta base: 23 categorias aparecem sob mais de uma '
       + N'area, e com razao - combustivel para lazer e combustivel para trabalho sao '
       + N'decisoes diferentes tomadas lancamento a lancamento.';
EXEC dbo.sp_documenta 'gold', 'dim_area_financ', NULL, @d;

SET @d = N'Chave substituta da area. -1 representa area nao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_area_financ', 'SK_AREA_FINANC', @d;
SET @d = N'Nome da area, com a grafia unificada entre as origens.';
EXEC dbo.sp_documenta 'gold', 'dim_area_financ', 'NM_AREA', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_area_financ', 'DT_CARGA', @d;

SET @d = N'GOLD | Nivel 2 da classificacao financeira, e o principal para analise: '
       + N'ALIMENTACAO, TRANSPORTE, LAZER, CASA, SAUDE. Compartilhada pelos fatos pessoal '
       + N'e da familia. '
       + N'"A classificar" e um membro REAL desta dimensao, e nao um nulo: e o que permite '
       + N'medir o tamanho do backlog de classificacao pelo proprio relatorio.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', NULL, @d;

SET @d = N'Chave substituta da categoria. -1 representa categoria nao informada.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', 'SK_CATEGORIA_FINANC', @d;
SET @d = N'Nome da categoria, com a grafia unificada entre as origens - a canonizacao '
       + N'escolhe a forma ortograficamente correta primeiro e a mais frequente depois.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', 'NM_CATEGORIA', @d;
SET @d = N'0 na linha "A classificar". Fica NESTA dimensao, e nao nas outras duas, porque '
       + N'a categoria e o nivel em que faltar classificacao significa alguma coisa.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', 'FL_CLASSIFICADO', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', 'DT_CARGA', @d;

SET @d = N'GOLD | Nivel 3 da classificacao financeira, o mais fino: "Almoco", "Aluguel", '
       + N'"Combustivel", "Reforma". E a dimensao mais numerosa das tres. '
       + N'Como a area, e independente e nao aninhada: 103 grupos aparecem sob mais de uma '
       + N'categoria, entao tratar o grupo como filho de uma categoria unica seria falso.';
EXEC dbo.sp_documenta 'gold', 'dim_grupo_financ', NULL, @d;

SET @d = N'Chave substituta do grupo. -1 representa grupo nao informado.';
EXEC dbo.sp_documenta 'gold', 'dim_grupo_financ', 'SK_GRUPO_FINANC', @d;
SET @d = N'Nome do grupo, com a grafia unificada entre as origens.';
EXEC dbo.sp_documenta 'gold', 'dim_grupo_financ', 'NM_GRUPO', @d;
SET @d = N'LINHAGEM: quando o registro entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_grupo_financ', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('dim_area_financ', 'dim_categoria_financ', 'dim_grupo_financ')
ORDER BY 1;
GO
