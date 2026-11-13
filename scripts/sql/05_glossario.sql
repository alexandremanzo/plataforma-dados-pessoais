/* =============================================================
   manzo-dados | 05 - Glossario de dados
   -------------------------------------------------------------
   gold.vw_glossario_dados

   Expoe como tabela toda a documentacao gravada no banco via
   MS_Description. Serve de origem para uma pagina de glossario no
   Power BI, e responde a pergunta "o que e esta coluna?" sem
   depender de um documento paralelo que envelhece.

   Uma linha por coluna de bronze, silver e gold, ja com a
   descricao da tabela ao lado - assim o relatorio pode agrupar
   por camada e por tabela sem consulta adicional.

   Pre-requisito: os scripts 00 a 04.
   Idempotente (CREATE OR ALTER).
   ============================================================= */

USE [db-manzo];
GO

CREATE OR ALTER VIEW gold.vw_glossario_dados
AS
SELECT
    s.name                                  AS NM_CAMADA,
    t.name                                  AS NM_TABELA,
    s.name + '.' + t.name                   AS NM_OBJETO,
    c.column_id                             AS NR_ORDEM,
    c.name                                  AS NM_COLUNA,

    -- Tipo legivel: varchar(100), decimal(18,2), int...
    ty.name + CASE
        WHEN ty.name IN ('varchar','char','nvarchar','nchar')
            THEN '(' + CASE WHEN c.max_length = -1 THEN 'max'
                            ELSE CAST(c.max_length /
                                 CASE WHEN ty.name LIKE 'n%' THEN 2 ELSE 1 END AS varchar(10))
                       END + ')'
        WHEN ty.name IN ('decimal','numeric')
            THEN '(' + CAST(c.precision AS varchar(10)) + ','
                     + CAST(c.scale AS varchar(10)) + ')'
        ELSE ''
    END                                     AS DS_TIPO_DADO,

    CASE WHEN c.is_nullable = 0 THEN 'Sim' ELSE 'Não' END        AS FL_OBRIGATORIO,
    CASE WHEN ic.column_id IS NOT NULL THEN 'Sim' ELSE 'Não' END AS FL_CHAVE_PRIMARIA,

    -- Papel da coluna, deduzido do prefixo adotado no projeto.
    CASE
        WHEN c.name LIKE 'SK[_]%'   THEN 'Chave substituta'
        WHEN c.name LIKE 'HASH[_]%' THEN 'Identidade do evento'
        WHEN c.name LIKE 'DT[_]%'   THEN 'Data'
        WHEN c.name LIKE 'VL[_]%'   THEN 'Valor (métrica)'
        WHEN c.name LIKE 'FL[_]%'   THEN 'Indicador (sim/não)'
        WHEN c.name LIKE 'NR[_]%'   THEN 'Número'
        WHEN c.name LIKE 'NM[_]%'   THEN 'Nome'
        WHEN c.name LIKE 'CD[_]%'   THEN 'Código'
        WHEN c.name LIKE 'TP[_]%'   THEN 'Tipo'
        WHEN c.name LIKE 'DS[_]%'   THEN 'Descrição'
        WHEN c.name LIKE 'ds[_]%'   THEN 'Texto de origem'
        WHEN c.name LIKE 'id[_]%'   THEN 'Chave técnica'
        ELSE 'Outro'
    END                                     AS DS_PAPEL,

    CAST(ep_col.value AS nvarchar(4000))    AS DS_DESCRICAO_COLUNA,
    CAST(ep_tab.value AS nvarchar(4000))    AS DS_DESCRICAO_TABELA,

    CASE WHEN ep_col.value IS NULL THEN 'Pendente' ELSE 'Documentada' END
                                            AS DS_STATUS_DOC
FROM sys.tables t
JOIN sys.schemas s   ON s.schema_id = t.schema_id
JOIN sys.columns c   ON c.object_id = t.object_id
JOIN sys.types ty    ON ty.user_type_id = c.user_type_id

LEFT JOIN sys.extended_properties ep_col
       ON ep_col.class = 1 AND ep_col.major_id = t.object_id
      AND ep_col.minor_id = c.column_id AND ep_col.name = 'MS_Description'

LEFT JOIN sys.extended_properties ep_tab
       ON ep_tab.class = 1 AND ep_tab.major_id = t.object_id
      AND ep_tab.minor_id = 0 AND ep_tab.name = 'MS_Description'

-- Marca as colunas que participam da chave primaria.
LEFT JOIN sys.index_columns ic
       ON ic.object_id = c.object_id AND ic.column_id = c.column_id
      AND ic.index_id = (SELECT index_id FROM sys.indexes i
                          WHERE i.object_id = t.object_id AND i.is_primary_key = 1)

WHERE s.name IN ('bronze', 'silver', 'gold');
GO

DECLARE @d nvarchar(3750);
SET @d = N'GLOSSARIO DE DADOS. Uma linha por coluna das camadas bronze, silver e gold, '
       + N'com tipo, obrigatoriedade, papel e a descricao de negocio gravada no proprio '
       + N'banco. E a origem da pagina de glossario do Power BI e o lugar para conferir '
       + N'o que significa qualquer campo do projeto. A coluna DS_STATUS_DOC aponta o que '
       + N'ainda falta documentar.';
EXEC dbo.sp_documenta 'gold', 'vw_glossario_dados', NULL, @d;
GO


/* -------------------------------------------------------------
   Conferencia: cobertura da documentacao por camada
   ------------------------------------------------------------- */

SELECT NM_CAMADA,
       COUNT(DISTINCT NM_TABELA) AS tabelas,
       COUNT(*)                  AS colunas,
       SUM(CASE WHEN DS_STATUS_DOC = 'Documentada' THEN 1 ELSE 0 END) AS documentadas,
       CAST(100.0 * SUM(CASE WHEN DS_STATUS_DOC = 'Documentada' THEN 1 ELSE 0 END)
            / COUNT(*) AS decimal(5,1)) AS pct
FROM gold.vw_glossario_dados
GROUP BY NM_CAMADA
ORDER BY CASE NM_CAMADA WHEN 'bronze' THEN 1 WHEN 'silver' THEN 2 ELSE 3 END;
GO
