/* =============================================================
   manzo-dados | 37 - Camada Gold: fato das execucoes de carga
   -------------------------------------------------------------
   gold.fato_carga + gold.vw_carga_ultima

   Registra quantas linhas cada carga inseriu e atualizou, a cada
   execucao. Ate agora esse numero era calculado 23 vezes por rodada,
   impresso no terminal e perdido.

   POR QUE UMA TABELA, E NAO O dt_carga. Todas as 43 tabelas tem
   dt_carga, mas ele e SOBRESCRITO no update: uma linha atualizada
   hoje fica indistinguivel de uma inserida hoje. Contar por dt_carga
   responde "o que foi tocado", nunca "o que entrou e o que mudou".
   A distincao so existe no instante da carga, e e ali que precisa ser
   gravada.

   O GRAO E A EXECUCAO DE UMA CARGA SOBRE UMA TABELA. Uma rodada da
   DAG gera dezenas de linhas aqui - uma por tabela tocada.

   FL_CONVERGIU E A COLUNA QUE IMPORTA. O projeto tem um contrato de
   qualidade explicito: a segunda execucao de qualquer carga deve
   reportar zero insercoes e zero atualizacoes. Ate hoje isso era
   conferido no olho, rodando duas vezes e comparando. Com esta
   coluna, uma carga que nunca converge fica visivel sozinha - e foi
   exatamente assim que apareceram as 772 atualizacoes fantasma do
   historico financeiro e as 172 do arredondamento na avaliacao
   fisica.

   CAMADA E TABELA SAO ATRIBUTOS DEGENERADOS, sem dimensao propria:
   sao rotulos tecnicos que nao tem atributo nenhum para pendurar.
   Criar dim_tabela so para guardar o nome seria cerimonia sem
   conteudo.

   Pre-requisitos: 00, 01, 04 (dim_calendario)
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('gold.fato_carga') IS NULL
BEGIN
    CREATE TABLE gold.fato_carga (
        SK_CARGA        int IDENTITY(1,1) NOT NULL,

        SK_DATA         int          NOT NULL,
        DT_EXECUCAO     datetime2(3) NOT NULL,

        DS_CAMADA       varchar(10)  NOT NULL,
        DS_TABELA       varchar(120) NOT NULL,
        DS_SCRIPT       varchar(120) NULL,

        NR_INSERIDOS    int          NOT NULL,
        NR_ATUALIZADOS  int          NOT NULL,
        NR_DESCARTADOS  int          NULL,
        NR_TOTAL        int          NULL,
        NR_SEGUNDOS     decimal(8,2) NULL,
        FL_CONVERGIU    bit          NOT NULL,

        CONSTRAINT PK_fato_carga PRIMARY KEY (SK_CARGA),
        CONSTRAINT FK_fato_carga_data FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA)
    );

    CREATE INDEX IX_fato_carga_data   ON gold.fato_carga (SK_DATA);
    CREATE INDEX IX_fato_carga_tabela ON gold.fato_carga (DS_TABELA);
    CREATE INDEX IX_fato_carga_exec   ON gold.fato_carga (DT_EXECUCAO DESC);
END
GO

/* -------------------------------------------------------------
   A ultima execucao de cada tabela
   ------------------------------------------------------------- */

CREATE OR ALTER VIEW gold.vw_carga_ultima AS
/*
   Uma linha por tabela, com o resultado da execucao mais recente.
   E a leitura de rotina: "esta tudo convergindo?".

   Usa ROW_NUMBER e nao MAX(DT_EXECUCAO) porque duas cargas podem
   terminar no mesmo milissegundo, e o MAX devolveria as duas.
*/
WITH ordenado AS (
    SELECT f.*,
           ROW_NUMBER() OVER (PARTITION BY f.DS_TABELA
                              ORDER BY f.DT_EXECUCAO DESC, f.SK_CARGA DESC) AS rn,
           COUNT(*)    OVER (PARTITION BY f.DS_TABELA) AS NR_EXECUCOES
    FROM gold.fato_carga f
)
SELECT DS_CAMADA,
       DS_TABELA,
       DS_SCRIPT,
       DT_EXECUCAO,
       NR_INSERIDOS,
       NR_ATUALIZADOS,
       NR_DESCARTADOS,
       NR_TOTAL,
       NR_SEGUNDOS,
       FL_CONVERGIU,
       NR_EXECUCOES,
       DATEDIFF(hour, DT_EXECUCAO, SYSDATETIME()) AS NR_HORAS_ATRAS
FROM ordenado
WHERE rn = 1;
GO

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Uma linha por execucao de carga sobre uma tabela: quantas linhas entraram, '
       + N'quantas mudaram e quanto tempo levou. Uma rodada da DAG gera dezenas de linhas '
       + N'aqui. '
       + N'EXISTE PORQUE dt_carga NAO RESPONDE ISSO: ele e sobrescrito no update, entao uma '
       + N'linha atualizada hoje fica indistinguivel de uma inserida hoje. A diferenca so '
       + N'existe no instante da carga. '
       + N'E o unico fato do modelo que fala do PIPELINE e nao das financas - nao se '
       + N'relaciona com nenhum outro, e o unico eixo compartilhado e o calendario.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', NULL, @d;

SET @d = N'Chave substituta da execucao.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'SK_CARGA', @d;
SET @d = N'Chave para gold.dim_calendario, no dia da execucao. Permite cruzar volume de '
       + N'carga com qualquer outro assunto pela mesma data.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'SK_DATA', @d;
SET @d = N'Momento exato do fim da carga, com milissegundos. E por ele que se ordena a '
       + N'sequencia de execucoes dentro de um mesmo dia.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'DT_EXECUCAO', @d;

SET @d = N'Camada da tabela carregada: bronze, silver ou gold. Atributo degenerado - e '
       + N'rotulo tecnico, sem atributo proprio que justifique uma dimensao.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'DS_CAMADA', @d;
SET @d = N'Nome da tabela carregada, qualificado pelo schema. Atributo degenerado.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'DS_TABELA', @d;
SET @d = N'Nome do script que fez a carga. LINHAGEM: liga o numero ao codigo que o '
       + N'produziu, para saber onde investigar quando algo nao converge.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'DS_SCRIPT', @d;

SET @d = N'METRICA. Linhas que ENTRARAM nesta execucao. Aditiva.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'NR_INSERIDOS', @d;
SET @d = N'METRICA. Linhas que ja existiam e MUDARAM nesta execucao. Aditiva. '
       + N'Numero alto sem voce ter mexido na origem e sinal de defeito, e nao de trabalho '
       + N'feito - foi assim que apareceram as 772 atualizacoes fantasma do historico '
       + N'financeiro.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'NR_ATUALIZADOS', @d;
SET @d = N'Linhas descartadas por nao serem lancamento - cauda de formula arrastada, linha '
       + N'sem chave. Nulo nas cargas que nao descartam nada.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'NR_DESCARTADOS', @d;
SET @d = N'Total de linhas da tabela DEPOIS da carga. Serve de conferencia: o total tem de '
       + N'crescer exatamente pelo numero de inseridos.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'NR_TOTAL', @d;
SET @d = N'Duracao da carga em segundos. Uma carga que passa a demorar muito mais que o '
       + N'habitual costuma indicar indice faltando ou origem crescendo.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'NR_SEGUNDOS', @d;

SET @d = N'A COLUNA QUE IMPORTA. S quando a execucao nao inseriu nem atualizou nada. '
       + N'O projeto tem um contrato explicito: rodar de novo sem mexer na origem tem de '
       + N'convergir em zero. Uma carga que NUNCA converge tem defeito - e sempre teve, so '
       + N'que antes isso dependia de alguem rodar duas vezes e comparar no olho. '
       + N'Zero e esperado na primeira carga do dia, quando ha dado novo de verdade.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'FL_CONVERGIU', @d;

SET @d = N'GOLD | A ultima execucao de cada tabela, uma linha por tabela. E a leitura de '
       + N'rotina: mostra de relance o que carregou, ha quanto tempo e se convergiu. '
       + N'NR_HORAS_ATRAS denuncia carga que parou de rodar - uma tabela que deveria ser '
       + N'atualizada tres vezes ao dia e aparece com 40 horas indica ramo quebrado na DAG.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', NULL, @d;

SET @d = N'Camada da tabela.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'DS_CAMADA', @d;
SET @d = N'Tabela carregada.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'DS_TABELA', @d;
SET @d = N'Script responsavel pela carga.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'DS_SCRIPT', @d;
SET @d = N'Quando a ultima execucao terminou.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'DT_EXECUCAO', @d;
SET @d = N'Linhas inseridas na ultima execucao.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_INSERIDOS', @d;
SET @d = N'Linhas atualizadas na ultima execucao.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_ATUALIZADOS', @d;
SET @d = N'Linhas descartadas na ultima execucao.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_DESCARTADOS', @d;
SET @d = N'Total de linhas da tabela apos a ultima execucao.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_TOTAL', @d;
SET @d = N'Duracao da ultima execucao, em segundos.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_SEGUNDOS', @d;
SET @d = N'S quando a ultima execucao convergiu em zero.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'FL_CONVERGIU', @d;
SET @d = N'Quantas execucoes esta tabela ja teve registradas.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_EXECUCOES', @d;
SET @d = N'Horas desde a ultima execucao. Numero grande em tabela de carga frequente '
       + N'indica ramo parado.';
EXEC dbo.sp_documenta 'gold', 'vw_carga_ultima', 'NR_HORAS_ATRAS', @d;
GO

SELECT s.name + '.' + o.name AS objeto,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = o.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = o.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE o.name IN ('fato_carga', 'vw_carga_ultima') ORDER BY 1;
GO
