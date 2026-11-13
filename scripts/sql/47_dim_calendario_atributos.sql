/* =============================================================
   manzo-dados | 47 - Novos atributos em gold.dim_calendario
   -------------------------------------------------------------
   + NM_MES_ANO            Jan/2026   (calculada)
   + NM_DIA_SEMANA_ABREV   Seg        (calculada)
   + FL_FERIADO            S / N
   + NM_FERIADO            Natal
   + DS_TIPO_FERIADO       Nacional / Facultativo

   NM_ANO_MES NAO MUDA. Ele guarda '2026-12' e e assim de proposito:
   ordena alfabeticamente na ordem certa, o que resolve o eixo de
   serie temporal sem coluna auxiliar. Sessenta referencias em treze
   arquivos dependem disso, e o painel de Financas calcula o mes de
   referencia a partir desse texto - com 'Jan/2026' ele passaria a
   devolver o mes alfabeticamente maior, sem erro nenhum na tela.
   O rotulo legivel entra ao lado, em NM_MES_ANO.

   AS DUAS PRIMEIRAS SAO CALCULADAS E PERSISTED. Nao sao preenchidas
   por UPDATE: derivam de colunas que a tabela ja tem. Assim o
   04_gold_investimentos.sql pode estender o calendario quando
   quiser - os dias novos ja nascem com elas, e nao ha o risco de
   alguem rodar o 04 e esquecer de rodar este.

   OS FERIADOS PRECISAM DE UPDATE, porque dependem da Pascoa, que nao
   e funcao de uma coluna. Por isso este bloco e refeito do zero a
   cada execucao: limpa tudo e marca de novo. Rodar duas vezes da o
   mesmo resultado, e corrigir a lista e alterar o script e rodar.

   O QUE ENTRA: os feriados NACIONAIS. Os nove fixos - com
   Consciencia Negra so a partir de 2024, quando a Lei 14.759/2023
   o tornou nacional - mais a Sexta-feira Santa, que e feriado legal.

   E ENTRAM TAMBEM os quatro dias ligados ao Carnaval e a Corpus
   Christi, marcados como Facultativo. Juridicamente nao sao
   feriado, sao ponto facultativo; na pratica banco e comercio
   fecham, e para explicar gasto e rotina se comportam como feriado.
   FL_FERIADO diz 'S' para os dois tipos; DS_TIPO_FERIADO separa.
   Quarta-feira de Cinzas e caso de meio termo - expediente so a
   partir das 14h - e esta aqui como Facultativo.

   A PASCOA E CALCULADA, nao digitada ano a ano. Algoritmo gregoriano
   anonimo (Meeus/Jones/Butcher). Ha uma guarda adiante conferindo
   quatro anos de data conhecida: errar a Pascoa deslocaria Carnaval
   e Corpus Christi em bloco, e um feriado na terca errada nao chama
   atencao de ninguem.

   Pre-requisitos: 04_gold_investimentos.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

-- Coluna calculada PERSISTED exige QUOTED_IDENTIFIER ON, e o sqlcmd
-- abre a sessao com ele OFF.
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/* -------------------------------------------------------------
   1. Os dois rotulos, calculados
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_calendario', 'NM_MES_ANO') IS NULL
    ALTER TABLE gold.dim_calendario ADD NM_MES_ANO AS (
        CAST(CASE WHEN SK_DATA = -1 THEN 'Não informado'
                  ELSE NM_MES_ABREV + '/' + CAST(NR_ANO AS char(4))
             END AS varchar(20))) PERSISTED;
GO

IF COL_LENGTH('gold.dim_calendario', 'NM_DIA_SEMANA_ABREV') IS NULL
    ALTER TABLE gold.dim_calendario ADD NM_DIA_SEMANA_ABREV AS (
        CAST(CASE WHEN SK_DATA = -1 THEN 'N/I'
                  WHEN NR_DIA_SEMANA = 1 THEN 'Dom'
                  WHEN NR_DIA_SEMANA = 2 THEN 'Seg'
                  WHEN NR_DIA_SEMANA = 3 THEN 'Ter'
                  WHEN NR_DIA_SEMANA = 4 THEN 'Qua'
                  WHEN NR_DIA_SEMANA = 5 THEN 'Qui'
                  WHEN NR_DIA_SEMANA = 6 THEN 'Sex'
                  WHEN NR_DIA_SEMANA = 7 THEN 'Sáb'
             END AS varchar(3))) PERSISTED;
GO

/* -------------------------------------------------------------
   2. As colunas de feriado
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_calendario', 'FL_FERIADO') IS NULL
    ALTER TABLE gold.dim_calendario ADD FL_FERIADO char(1) NOT NULL
        CONSTRAINT DF_dim_calendario_feriado DEFAULT ('N');
GO

IF COL_LENGTH('gold.dim_calendario', 'NM_FERIADO') IS NULL
    ALTER TABLE gold.dim_calendario ADD NM_FERIADO varchar(60) NULL;
GO

IF COL_LENGTH('gold.dim_calendario', 'DS_TIPO_FERIADO') IS NULL
    ALTER TABLE gold.dim_calendario ADD DS_TIPO_FERIADO varchar(20) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
                WHERE name = 'CK_dim_calendario_feriado')
    ALTER TABLE gold.dim_calendario ADD CONSTRAINT CK_dim_calendario_feriado
        CHECK (FL_FERIADO IN ('S', 'N'));
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
                WHERE name = 'CK_dim_calendario_tipo_feriado')
    ALTER TABLE gold.dim_calendario ADD CONSTRAINT CK_dim_calendario_tipo_feriado
        CHECK (DS_TIPO_FERIADO IS NULL
               OR DS_TIPO_FERIADO IN ('Nacional', 'Facultativo'));
GO

/* -------------------------------------------------------------
   3. A Pascoa, e a guarda contra ela sair errada
   ------------------------------------------------------------- */

IF OBJECT_ID('tempdb..#pascoa') IS NOT NULL DROP TABLE #pascoa;

-- Algoritmo gregoriano anonimo. O CROSS APPLY (VALUES ...) deixa cada
-- passo nomear o anterior, o que torna a conta legivel - escrita como
-- uma expressao so, ela seria impossivel de conferir.
SELECT a.ano, DATEFROMPARTS(a.ano, v7.mes, v7.dia) AS dt_pascoa
INTO #pascoa
FROM (SELECT DISTINCT NR_ANO AS ano FROM gold.dim_calendario
       WHERE SK_DATA <> -1) a
CROSS APPLY (VALUES (a.ano % 19, a.ano / 100, a.ano % 100))        v1(a_, b, c)
CROSS APPLY (VALUES (v1.b / 4, v1.b % 4, (v1.b + 8) / 25,
                     v1.c / 4, v1.c % 4))                          v2(d, e, f, i, k)
CROSS APPLY (VALUES ((v1.b - v2.f + 1) / 3))                       v3(g)
CROSS APPLY (VALUES ((19 * v1.a_ + v1.b - v2.d - v3.g + 15) % 30)) v4(h)
CROSS APPLY (VALUES ((32 + 2 * v2.e + 2 * v2.i - v4.h - v2.k) % 7)) v5(l)
CROSS APPLY (VALUES ((v1.a_ + 11 * v4.h + 22 * v5.l) / 451))       v6(m)
CROSS APPLY (VALUES ((v4.h + v5.l - 7 * v6.m + 114) / 31,
                     ((v4.h + v5.l - 7 * v6.m + 114) % 31) + 1))   v7(mes, dia);

-- Quatro anos de data conhecida. Errar a Pascoa deslocaria Carnaval e
-- Corpus Christi em bloco, e feriado na terca errada nao chama a
-- atencao de ninguem - por isso a conferencia e automatica.
DECLARE @erros int = (
    SELECT COUNT(*) FROM (VALUES
        (2024, CAST('2024-03-31' AS date)),
        (2025, CAST('2025-04-20' AS date)),
        (2026, CAST('2026-04-05' AS date)),
        (2027, CAST('2027-03-28' AS date))
    ) AS esperado(ano, dt)
    LEFT JOIN #pascoa p ON p.ano = esperado.ano
    WHERE p.dt_pascoa IS NULL OR p.dt_pascoa <> esperado.dt);

IF @erros > 0
    THROW 50048, 'O calculo da Pascoa nao bate com as datas conhecidas.', 1;
GO

/* -------------------------------------------------------------
   4. Os feriados, refeitos do zero
   ------------------------------------------------------------- */

-- Limpa antes de marcar: assim tirar um feriado da lista abaixo
-- realmente o tira do calendario, em vez de deixar a marcacao antiga
-- para sempre.
UPDATE gold.dim_calendario
   SET FL_FERIADO = 'N', NM_FERIADO = NULL, DS_TIPO_FERIADO = NULL
 WHERE FL_FERIADO <> 'N' OR NM_FERIADO IS NOT NULL
    OR DS_TIPO_FERIADO IS NOT NULL;
GO

IF OBJECT_ID('tempdb..#feriado') IS NOT NULL DROP TABLE #feriado;

WITH anos AS (SELECT DISTINCT ano FROM #pascoa),
feriados AS (
    /* --- fixos, nacionais por lei --- */
    SELECT DATEFROMPARTS(ano,  1,  1) dt, 'Confraternização Universal' nm, 'Nacional' tp FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano,  4, 21), 'Tiradentes',                'Nacional' FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano,  5,  1), 'Dia do Trabalho',           'Nacional' FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano,  9,  7), 'Independência do Brasil',   'Nacional' FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano, 10, 12), 'Nossa Senhora Aparecida',   'Nacional' FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano, 11,  2), 'Finados',                   'Nacional' FROM anos
    UNION ALL
    SELECT DATEFROMPARTS(ano, 11, 15), 'Proclamação da República',  'Nacional' FROM anos
    UNION ALL
    -- So a partir de 2024: antes disso nao era feriado nacional, e
    -- marcar para tras inventaria dia nao util em serie historica.
    SELECT DATEFROMPARTS(ano, 11, 20), 'Consciência Negra',         'Nacional' FROM anos WHERE ano >= 2024
    UNION ALL
    SELECT DATEFROMPARTS(ano, 12, 25), 'Natal',                     'Nacional' FROM anos

    /* --- movel, nacional por lei --- */
    UNION ALL
    SELECT DATEADD(day,  -2, dt_pascoa), 'Sexta-feira Santa',       'Nacional' FROM #pascoa

    /* --- moveis, ponto facultativo --- */
    UNION ALL
    SELECT DATEADD(day, -48, dt_pascoa), 'Carnaval (segunda)',      'Facultativo' FROM #pascoa
    UNION ALL
    SELECT DATEADD(day, -47, dt_pascoa), 'Carnaval (terça)',        'Facultativo' FROM #pascoa
    UNION ALL
    SELECT DATEADD(day, -46, dt_pascoa), 'Quarta-feira de Cinzas',  'Facultativo' FROM #pascoa
    UNION ALL
    SELECT DATEADD(day,  60, dt_pascoa), 'Corpus Christi',          'Facultativo' FROM #pascoa
)
SELECT dt, nm, tp INTO #feriado FROM feriados;
GO

-- Nenhuma data pode aparecer duas vezes: NM_FERIADO guarda um nome so,
-- e um segundo feriado no mesmo dia escolheria sozinho qual sobrevive.
-- Com a lista nacional isso nao acontece; a guarda existe para o dia
-- em que alguem acrescentar feriado estadual ou municipal.
IF EXISTS (SELECT 1 FROM #feriado GROUP BY dt HAVING COUNT(*) > 1)
    THROW 50049, 'Ha mais de um feriado na mesma data. NM_FERIADO so cabe um.', 1;
GO

UPDATE c
   SET c.FL_FERIADO      = 'S',
       c.NM_FERIADO      = f.nm,
       c.DS_TIPO_FERIADO = f.tp
  FROM gold.dim_calendario c
  JOIN #feriado f ON f.dt = c.DT_DATA
 WHERE c.SK_DATA <> -1;
GO

/* -------------------------------------------------------------
   5. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'Mes e ano no formato legivel Jan/2026. CALCULADA a partir de NM_MES_ABREV e '
       + N'NR_ANO, entao dia novo no calendario ja nasce com ela. '
       + N'E a coluna de ROTULO; para ORDENAR ou comparar use NM_ANO_MES, que esta em '
       + N'AAAA-MM e ordena sozinho - por aqui, Abril viria antes de Janeiro.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_MES_ANO', @d;

SET @d = N'Dia da semana abreviado: Seg, Ter, Qua, Qui, Sex, Sab, Dom. CALCULADA a partir '
       + N'de NR_DIA_SEMANA. Para ordenar use NR_DIA_SEMANA, em que 1 e domingo.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_DIA_SEMANA_ABREV', @d;

SET @d = N'S quando o dia e feriado nacional OU ponto facultativo; N nos demais. '
       + N'Os dois casos vem com S de proposito: para explicar gasto e rotina, o que '
       + N'importa e se o comercio abriu. Use DS_TIPO_FERIADO para separar o feriado '
       + N'legal do facultativo.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'FL_FERIADO', @d;

SET @d = N'Nome do feriado, nulo quando o dia nao e feriado. Cabe UM nome por dia: se um '
       + N'dia ganhar dois feriados - o que acontece ao acrescentar estadual ou municipal, '
       + N'ja que 21/04 e Tiradentes e Fundacao de Brasilia - o script 47 aborta em vez de '
       + N'escolher sozinho qual sobrevive.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'NM_FERIADO', @d;

SET @d = N'Nacional para o feriado previsto em lei; Facultativo para Carnaval (segunda, '
       + N'terca e quarta de cinzas) e Corpus Christi, que juridicamente sao ponto '
       + N'facultativo e nao feriado. Nulo quando o dia nao e feriado. '
       + N'A lista cobre so o ambito NACIONAL: feriado estadual e municipal nao entraram.';
EXEC dbo.sp_documenta 'gold', 'dim_calendario', 'DS_TIPO_FERIADO', @d;
GO

/* -------------------------------------------------------------
   6. Conferencia
   ------------------------------------------------------------- */

SELECT 'dias no calendario' AS conferencia,
       CAST(COUNT(*) AS varchar(20)) AS valor FROM gold.dim_calendario
UNION ALL SELECT 'feriados marcados',
    CAST((SELECT COUNT(*) FROM gold.dim_calendario WHERE FL_FERIADO = 'S') AS varchar(20))
UNION ALL SELECT '  dos quais Nacional',
    CAST((SELECT COUNT(*) FROM gold.dim_calendario WHERE DS_TIPO_FERIADO = 'Nacional') AS varchar(20))
UNION ALL SELECT '  dos quais Facultativo',
    CAST((SELECT COUNT(*) FROM gold.dim_calendario WHERE DS_TIPO_FERIADO = 'Facultativo') AS varchar(20))
-- Escrito em duas metades porque o T-SQL nao trata predicado como
-- valor: (a = b) <> (c IS NOT NULL) e erro de sintaxe, nao comparacao.
UNION ALL SELECT 'incoerente (S sem nome, ou nome sem S)',
    CAST((SELECT COUNT(*) FROM gold.dim_calendario
           WHERE (FL_FERIADO = 'S' AND NM_FERIADO IS NULL)
              OR (FL_FERIADO <> 'S' AND NM_FERIADO IS NOT NULL)) AS varchar(20))
UNION ALL SELECT 'rotulo vazio',
    CAST((SELECT COUNT(*) FROM gold.dim_calendario
           WHERE NM_MES_ANO IS NULL OR NM_DIA_SEMANA_ABREV IS NULL) AS varchar(20));

-- Uma amostra para conferir a olho: os feriados do ano corrente.
SELECT DT_DATA, NM_DIA_SEMANA_ABREV, NM_MES_ANO, NM_FERIADO, DS_TIPO_FERIADO
FROM gold.dim_calendario
WHERE FL_FERIADO = 'S' AND NR_ANO = YEAR(GETDATE())
ORDER BY DT_DATA;
GO
