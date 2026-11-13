/* =============================================================
   manzo-dados | Consultas: sequencias de dias consecutivos
   -------------------------------------------------------------
   Nao e DDL e nao entra no executa.ps1: sao consultas de analise,
   para rodar a mao no SSMS. Cada bloco e independente.

   Mede as maiores sequencias de dias consecutivos de cada
   indicador FL_ de gold.fato_dia - comecando por FL_LAZER.

   TRES ARMADILHAS, E TODAS SILENCIOSAS SE IGNORADAS:

   1. A SERIE TEM BURACOS. Sao 72 dias sem registro entre
      01/01/2024 e 23/09/2026 - 70 deles so em 2024. A tecnica
      classica de ilhas usa ROW_NUMBER, que conta LINHAS; se duas
      linhas do mesmo valor estiverem separadas por um dia que
      nao existe, ela as junta e inventa uma sequencia que nunca
      houve. Por isso o agrupamento compara DATEDIFF em DIAS com
      o ROW_NUMBER: so fica constante quando os dias sao mesmo
      consecutivos no calendario.

   2. SK_DATA = -1 E O MEMBRO "NAO INFORMADO". Duas linhas
      apontam para ele e aparecem como 01/01/1900, ja marcadas
      com FL_DATA_SUSPEITA = 'S'. Um dia sem data nao pode estar
      numa sequencia de dias; ficam de fora.

   3. FL_LAZER E ANULAVEL. Hoje nao ha nulo, mas a coluna
      aceita. Nulo nao e "N": e dia sem resposta, e interrompe a
      sequencia como um buraco interrompe.

   Consequencia de tudo isso: 10 sequencias foram cortadas por
   AUSENCIA DE DADO, e nao por mudanca de valor. O bloco 2
   distingue os dois casos, porque "parou porque mudou" e "parou
   porque ninguem anotou" sao coisas diferentes.
   ============================================================= */

USE [db-manzo];
GO


/* -------------------------------------------------------------
   1. As maiores sequencias de FL_LAZER
   -------------------------------------------------------------
   O que foi pedido: as maiores sequencias de dias consecutivos
   com S e com N. Troque 'FL_LAZER' pelo indicador que quiser,
   ou use o bloco 5 para ver todos de uma vez.
   ------------------------------------------------------------- */

WITH dia AS (
    SELECT c.DT_DATA AS dt,
           f.FL_LAZER AS fl
    FROM gold.fato_dia f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    WHERE f.SK_DATA <> -1          /* dia sem data nao entra em sequencia */
      AND f.FL_LAZER IN ('S','N') /* nulo interrompe, nao vira N        */
),
ilha AS (
    /* O AGRUPADOR. DATEDIFF anda com o CALENDARIO e ROW_NUMBER anda
       com as LINHAS: a diferenca so se mantem enquanto os dias forem
       consecutivos de verdade. Um dia faltando faz DATEDIFF pular sem
       ROW_NUMBER pular junto, e a ilha se fecha - que e o que se quer. */
    SELECT dt, fl,
           DATEDIFF(day, '2000-01-01', dt)
         - ROW_NUMBER() OVER (PARTITION BY fl ORDER BY dt) AS grupo
    FROM dia
),
seq AS (
    SELECT fl, MIN(dt) AS dt_inicio, MAX(dt) AS dt_fim, COUNT(*) AS qt_dias
    FROM ilha
    GROUP BY fl, grupo
)
SELECT CASE fl WHEN 'S' THEN 'Sim' ELSE 'Nao' END AS lazer,
       dt_inicio,
       dt_fim,
       qt_dias,
       DATENAME(weekday, dt_inicio) AS comecou_em,
       ROW_NUMBER() OVER (PARTITION BY fl ORDER BY qt_dias DESC, dt_inicio) AS posicao
FROM seq
WHERE qt_dias >= 3
ORDER BY fl DESC, qt_dias DESC, dt_inicio;
GO


/* -------------------------------------------------------------
   2. Todas as sequencias, com o motivo de terem terminado
   -------------------------------------------------------------
   E a base para o report: uma linha por sequencia, de qualquer
   tamanho.

   DS_MOTIVO_FIM e a coluna que evita conclusao errada. Uma
   sequencia que termina em "Dia sem registro" pode ter sido
   maior na vida real - so nao da para afirmar. Separar isso de
   "Mudou de valor" e a diferenca entre medir e chutar.
   ------------------------------------------------------------- */

WITH dia AS (
    SELECT c.DT_DATA AS dt, f.FL_LAZER AS fl
    FROM gold.fato_dia f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    WHERE f.SK_DATA <> -1 AND f.FL_LAZER IN ('S','N')
),
ilha AS (
    SELECT dt, fl,
           DATEDIFF(day, '2000-01-01', dt)
         - ROW_NUMBER() OVER (PARTITION BY fl ORDER BY dt) AS grupo
    FROM dia
),
seq AS (
    SELECT fl, MIN(dt) AS dt_inicio, MAX(dt) AS dt_fim, COUNT(*) AS qt_dias
    FROM ilha GROUP BY fl, grupo
),
limite AS (SELECT MAX(dt) AS ultimo FROM dia)
SELECT CASE s.fl WHEN 'S' THEN 'Sim' ELSE 'Nao' END AS lazer,
       s.dt_inicio,
       s.dt_fim,
       s.qt_dias,
       CASE
           WHEN s.dt_fim = l.ultimo                                   THEN 'Em curso'
           WHEN EXISTS (SELECT 1 FROM dia d
                         WHERE d.dt = DATEADD(day, 1, s.dt_fim))      THEN 'Mudou de valor'
           ELSE 'Dia sem registro'
       END AS ds_motivo_fim,
       YEAR(s.dt_inicio)  AS nr_ano,
       MONTH(s.dt_inicio) AS nr_mes
FROM seq s
CROSS JOIN limite l
ORDER BY s.dt_inicio;
GO


/* -------------------------------------------------------------
   3. Resumo por valor
   ------------------------------------------------------------- */

WITH dia AS (
    SELECT c.DT_DATA AS dt, f.FL_LAZER AS fl
    FROM gold.fato_dia f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    WHERE f.SK_DATA <> -1 AND f.FL_LAZER IN ('S','N')
),
ilha AS (
    SELECT dt, fl,
           DATEDIFF(day, '2000-01-01', dt)
         - ROW_NUMBER() OVER (PARTITION BY fl ORDER BY dt) AS grupo
    FROM dia
),
seq AS (
    SELECT fl, MIN(dt) AS dt_inicio, MAX(dt) AS dt_fim, COUNT(*) AS qt_dias
    FROM ilha GROUP BY fl, grupo
)
SELECT CASE fl WHEN 'S' THEN 'Sim' ELSE 'Nao' END AS lazer,
       COUNT(*)                                   AS qt_sequencias,
       SUM(qt_dias)                               AS qt_dias_total,
       MAX(qt_dias)                               AS maior_sequencia,
       CAST(AVG(qt_dias * 1.0) AS decimal(5,1))   AS media_dias,
       MIN(dt_inicio)                             AS primeira,
       MAX(dt_fim)                                AS ultima
FROM seq
GROUP BY fl
ORDER BY fl DESC;
GO


/* -------------------------------------------------------------
   4. A sequencia em curso
   -------------------------------------------------------------
   Para um cartao de report: ha quantos dias o valor atual se
   repete, e desde quando.
   ------------------------------------------------------------- */

WITH dia AS (
    SELECT c.DT_DATA AS dt, f.FL_LAZER AS fl
    FROM gold.fato_dia f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    WHERE f.SK_DATA <> -1 AND f.FL_LAZER IN ('S','N')
),
ilha AS (
    SELECT dt, fl,
           DATEDIFF(day, '2000-01-01', dt)
         - ROW_NUMBER() OVER (PARTITION BY fl ORDER BY dt) AS grupo
    FROM dia
)
SELECT TOP 1
       CASE fl WHEN 'S' THEN 'Sim' ELSE 'Nao' END AS lazer_hoje,
       MIN(dt) AS desde,
       MAX(dt) AS ate,
       COUNT(*) AS qt_dias,
       DATEDIFF(day, MAX(dt), CAST(GETDATE() AS date)) AS dias_sem_registro
FROM ilha
GROUP BY fl, grupo
ORDER BY MAX(dt) DESC;
GO


/* -------------------------------------------------------------
   5. O mesmo, para TODOS os indicadores do dia
   -------------------------------------------------------------
   E esta que vale levar para o report: uma linha por indicador,
   valor e sequencia. Um segmentador de NM_INDICADOR passa a
   servir para lazer, estresse, treino, cardio e o que mais vier.

   FL_DATA_SUSPEITA fica de fora de proposito: e marca de
   qualidade do dado, nao habito.

   O UNPIVOT descarta nulo por conta propria - o que aqui e
   exatamente o desejado, porque o dia sem resposta some da
   serie e corta a sequencia como um buraco corta.
   ------------------------------------------------------------- */

WITH base AS (
    SELECT c.DT_DATA AS dt,
           f.FL_LAZER, f.FL_ESTRESSE, f.FL_TREINO, f.FL_CARDIO,
           f.FL_TRABALHO, f.FL_META_AGUA, f.FL_NINA_EM_CASA
    FROM gold.fato_dia f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    WHERE f.SK_DATA <> -1
),
longo AS (
    SELECT dt, indicador, valor
    FROM base
    UNPIVOT (valor FOR indicador IN
        (FL_LAZER, FL_ESTRESSE, FL_TREINO, FL_CARDIO,
         FL_TRABALHO, FL_META_AGUA, FL_NINA_EM_CASA)) u
    WHERE valor IN ('S','N')
),
ilha AS (
    SELECT dt, indicador, valor,
           DATEDIFF(day, '2000-01-01', dt)
         - ROW_NUMBER() OVER (PARTITION BY indicador, valor ORDER BY dt) AS grupo
    FROM longo
),
seq AS (
    SELECT indicador, valor,
           MIN(dt) AS dt_inicio, MAX(dt) AS dt_fim, COUNT(*) AS qt_dias
    FROM ilha GROUP BY indicador, valor, grupo
)
SELECT indicador                                        AS nm_indicador,
       CASE valor WHEN 'S' THEN 'Sim' ELSE 'Nao' END    AS ds_valor,
       dt_inicio, dt_fim, qt_dias,
       ROW_NUMBER() OVER (PARTITION BY indicador, valor
                          ORDER BY qt_dias DESC, dt_inicio) AS posicao
FROM seq
ORDER BY nm_indicador, valor DESC, qt_dias DESC;
GO


/* -------------------------------------------------------------
   6. A regua de confianca: cobertura da serie por ano
   -------------------------------------------------------------
   Rode isto ANTES de concluir qualquer coisa dos blocos acima.
   Sequencia medida sobre ano cheio de buraco vale menos: 2024
   tem 70 dias sem registro, 2025 fechou completo e 2026 tem 2.
   ------------------------------------------------------------- */

SELECT YEAR(c.DT_DATA)                                   AS nr_ano,
       COUNT(*)                                          AS dias_registrados,
       DATEDIFF(day, MIN(c.DT_DATA), MAX(c.DT_DATA)) + 1 AS dias_no_intervalo,
       DATEDIFF(day, MIN(c.DT_DATA), MAX(c.DT_DATA)) + 1
           - COUNT(*)                                    AS dias_faltando,
       SUM(CASE WHEN f.FL_LAZER IS NULL THEN 1 ELSE 0 END) AS lazer_sem_resposta
FROM gold.fato_dia f
JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
WHERE f.SK_DATA <> -1
GROUP BY YEAR(c.DT_DATA)
ORDER BY nr_ano;
GO
