/* =============================================================
   manzo-dados | Consultas: analise de gastos
   -------------------------------------------------------------
   Nao e DDL e nao entra no executa.ps1: sao consultas de analise,
   para rodar a mao no SSMS. Cada bloco e independente.

   Tres indicadores, todos sobre gold.fato_movto_financ:
     1. % de gasto por categoria
     2. % no credito x no debito
     3. gasto diario, para o calendario
     4. a distribuicao diaria - le ANTES de desenhar o calendario

   TRES FILTROS QUE PRECISAM ESTAR EM TODOS OS BLOCOS. Tirar
   qualquer um nao da erro: da numero errado.

   a) DS_NIVEL = 'ANALITICO'. Os 86 SINTETICO sao PAGAMENTOS DE
      FATURA - o total do cartao saindo da conta. Somados junto
      com as compras do cartao, contam o mesmo gasto duas vezes.

   b) DS_TIPO_FLUXO = 'DESPESA'. Receita tem sinal invertido e
      viraria gasto negativo, encolhendo o total.

   c) DS_COMPRESSIBILIDADE <> 'Nao e gasto'. Aporte, resgate e
      transferencia entre contas somam R$ 364,4 mil em 24 meses e
      nao sao consumo: entrariam como a maior "categoria" de
      todas e achatariam o resto.

   A JANELA E 12 MESES FECHADOS. O mes corrente esta pela metade
   e puxaria toda media para baixo.
   ============================================================= */

USE [db-manzo];
GO


/* -------------------------------------------------------------
   1. % de gasto por categoria
   -------------------------------------------------------------
   Sete categorias fazem 90% do gasto. O acumulado esta na
   consulta de proposito: e ele que responde "onde vale mexer".
   ------------------------------------------------------------- */

WITH gasto AS (
    SELECT ISNULL(ct.NM_CATEGORIA, '(sem categoria)') AS nm_categoria,
           -f.VL_TRANSACAO                            AS vl_gasto
    FROM gold.fato_movto_financ f
    JOIN gold.dim_calendario  c  ON c.SK_DATA = f.SK_DATA
    LEFT JOIN gold.dim_categoria_financ ct ON ct.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
    LEFT JOIN gold.dim_grupo_financ     g  ON g.SK_GRUPO_FINANC      = f.SK_GRUPO_FINANC
    WHERE f.DS_NIVEL = 'ANALITICO'
      AND f.DS_TIPO_FLUXO = 'DESPESA'
      AND ISNULL(g.DS_COMPRESSIBILIDADE, '') <> 'Nao e gasto'
      AND c.DT_DATA >= DATEFROMPARTS(YEAR(DATEADD(month, -12, GETDATE())),
                                     MONTH(DATEADD(month, -12, GETDATE())), 1)
      AND c.DT_DATA <  DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
)
SELECT nm_categoria,
       CAST(SUM(vl_gasto) AS decimal(12,2))                      AS vl_total,
       CAST(SUM(vl_gasto) / 12 AS decimal(12,2))                 AS vl_por_mes,
       COUNT(*)                                                  AS qt_lancamentos,
       CAST(100.0 * SUM(vl_gasto) / SUM(SUM(vl_gasto)) OVER ()
            AS decimal(5,1))                                     AS pc_do_total,
       CAST(100.0 * SUM(SUM(vl_gasto)) OVER (ORDER BY SUM(vl_gasto) DESC)
                  / SUM(SUM(vl_gasto)) OVER ()
            AS decimal(5,1))                                     AS pc_acumulado
FROM gasto
GROUP BY nm_categoria
ORDER BY vl_total DESC;
GO


/* -------------------------------------------------------------
   2. % no credito x no debito
   -------------------------------------------------------------
   O TICKET MEDIO E A LEITURA QUE IMPORTA, mais que o percentual:
   os dois pesam parecido no total, mas o credito sao centenas de
   compras pequenas e o debito, dezenas de contas grandes.

   "Conta de investimento" fica fora do agrupamento porque nao e
   forma de pagamento - e movimento de patrimonio.
   ------------------------------------------------------------- */

WITH gasto AS (
    SELECT CASE
               WHEN o.DS_TIPO_CONTA = N'Cartão de crédito' THEN 'Crédito'
               WHEN o.DS_TIPO_CONTA IN (N'Conta corrente', N'Dinheiro e débito',
                                        N'Vale-alimentação') THEN 'Débito'
               ELSE 'Outros'
           END               AS ds_forma,
           o.NM_ORIGEM       AS nm_origem,
           -f.VL_TRANSACAO   AS vl_gasto
    FROM gold.fato_movto_financ f
    JOIN gold.dim_calendario c ON c.SK_DATA   = f.SK_DATA
    JOIN gold.dim_origem     o ON o.SK_ORIGEM = f.SK_ORIGEM
    LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
    WHERE f.DS_NIVEL = 'ANALITICO'
      AND f.DS_TIPO_FLUXO = 'DESPESA'
      AND ISNULL(g.DS_COMPRESSIBILIDADE, '') <> 'Nao e gasto'
      AND c.DT_DATA >= DATEFROMPARTS(YEAR(DATEADD(month, -12, GETDATE())),
                                     MONTH(DATEADD(month, -12, GETDATE())), 1)
      AND c.DT_DATA <  DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
)
SELECT ds_forma,
       CAST(SUM(vl_gasto) AS decimal(12,2))                      AS vl_total,
       COUNT(*)                                                  AS qt_lancamentos,
       CAST(SUM(vl_gasto) / COUNT(*) AS decimal(10,2))           AS vl_ticket_medio,
       CAST(100.0 * SUM(vl_gasto) / SUM(SUM(vl_gasto)) OVER ()
            AS decimal(5,1))                                     AS pc_do_total
FROM gasto
GROUP BY ds_forma
ORDER BY vl_total DESC;
GO


/* -------------------------------------------------------------
   3. Gasto diario - a base do calendario
   -------------------------------------------------------------
   Uma linha por dia COM gasto. Dia sem gasto nao aparece aqui, e
   nao deve mesmo: no calendario ele e a ausencia de celula pintada,
   nao um zero. Foram 41 dias assim em 365.

   Traz dois percentuais porque respondem perguntas diferentes:
   pc_do_mes compara o dia com o proprio mes (o que serve para a
   cor da celula) e pc_do_periodo o situa no ano inteiro.
   ------------------------------------------------------------- */

WITH diario AS (
    SELECT c.DT_DATA        AS dt_dia,
           c.NM_ANO_MES     AS nm_ano_mes,
           c.NR_ANO         AS nr_ano,
           c.NR_MES         AS nr_mes,
           c.NR_DIA         AS nr_dia,
           c.NM_DIA_SEMANA  AS nm_dia_semana,
           c.NR_DIA_SEMANA  AS nr_dia_semana,
           SUM(-f.VL_TRANSACAO) AS vl_gasto,
           COUNT(*)             AS qt_lancamentos
    FROM gold.fato_movto_financ f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
    WHERE f.DS_NIVEL = 'ANALITICO'
      AND f.DS_TIPO_FLUXO = 'DESPESA'
      AND ISNULL(g.DS_COMPRESSIBILIDADE, '') <> 'Nao e gasto'
      AND c.DT_DATA >= DATEFROMPARTS(YEAR(DATEADD(month, -12, GETDATE())),
                                     MONTH(DATEADD(month, -12, GETDATE())), 1)
      AND c.DT_DATA <  DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY c.DT_DATA, c.NM_ANO_MES, c.NR_ANO, c.NR_MES, c.NR_DIA,
             c.NM_DIA_SEMANA, c.NR_DIA_SEMANA
)
SELECT dt_dia, nm_ano_mes, nr_ano, nr_mes, nr_dia,
       nm_dia_semana, nr_dia_semana,
       CAST(vl_gasto AS decimal(12,2))                            AS vl_gasto,
       qt_lancamentos,
       CAST(100.0 * vl_gasto / SUM(vl_gasto) OVER (PARTITION BY nm_ano_mes)
            AS decimal(5,1))                                      AS pc_do_mes,
       CAST(100.0 * vl_gasto / SUM(vl_gasto) OVER ()
            AS decimal(5,2))                                      AS pc_do_periodo,
       /* Percentil do dia dentro do periodo. E POR ELE que a cor do
          calendario deve ser pintada - ver o bloco 4. */
       CAST(100.0 * PERCENT_RANK() OVER (ORDER BY vl_gasto)
            AS decimal(5,1))                                      AS pc_percentil
FROM diario
ORDER BY dt_dia;
GO


/* -------------------------------------------------------------
   4. A distribuicao - leia antes de escolher a escala de cor
   -------------------------------------------------------------
   O CALENDARIO NAO PODE USAR ESCALA LINEAR. A mediana do dia e
   R$ 173 e o maior dia, R$ 5.171 - trinta vezes mais. Numa escala
   linear, tres dias ficam escuros e trezentos ficam brancos: o
   calendario fica bonito e nao informa nada.

   Pinte por PERCENTIL (a coluna pc_percentil do bloco 3) ou por
   faixa fixa construida sobre estes quantis.
   ------------------------------------------------------------- */

WITH diario AS (
    SELECT c.DT_DATA AS dt_dia, SUM(-f.VL_TRANSACAO) AS vl_gasto
    FROM gold.fato_movto_financ f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
    WHERE f.DS_NIVEL = 'ANALITICO'
      AND f.DS_TIPO_FLUXO = 'DESPESA'
      AND ISNULL(g.DS_COMPRESSIBILIDADE, '') <> 'Nao e gasto'
      AND c.DT_DATA >= DATEFROMPARTS(YEAR(DATEADD(month, -12, GETDATE())),
                                     MONTH(DATEADD(month, -12, GETDATE())), 1)
      AND c.DT_DATA <  DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY c.DT_DATA
)
SELECT DISTINCT
       COUNT(*)                 OVER ()  AS qt_dias_com_gasto,
       CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY vl_gasto) OVER () AS decimal(10,2)) AS p25,
       CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY vl_gasto) OVER () AS decimal(10,2)) AS mediana,
       CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY vl_gasto) OVER () AS decimal(10,2)) AS p75,
       CAST(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY vl_gasto) OVER () AS decimal(10,2)) AS p90,
       CAST(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY vl_gasto) OVER () AS decimal(10,2)) AS p95,
       CAST(MAX(vl_gasto)       OVER () AS decimal(10,2)) AS maior_dia,
       CAST(AVG(vl_gasto)       OVER () AS decimal(10,2)) AS media_dia_com_gasto
FROM diario;
GO


/* -------------------------------------------------------------
   5. Gasto por dia da semana
   -------------------------------------------------------------
   Segunda concentra 29% do gasto do ano, com media diaria quase o
   dobro da de qualquer outro dia. Nao e habito de consumo: sao as
   contas grandes e agendadas caindo na segunda - Conta Familia,
   escola, IPVA, revisao.
   ------------------------------------------------------------- */

WITH diario AS (
    SELECT c.NR_DIA_SEMANA AS nr, c.NM_DIA_SEMANA AS nm, c.DT_DATA AS dt_dia,
           SUM(-f.VL_TRANSACAO) AS vl_gasto
    FROM gold.fato_movto_financ f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
    LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
    WHERE f.DS_NIVEL = 'ANALITICO'
      AND f.DS_TIPO_FLUXO = 'DESPESA'
      AND ISNULL(g.DS_COMPRESSIBILIDADE, '') <> 'Nao e gasto'
      AND c.DT_DATA >= DATEFROMPARTS(YEAR(DATEADD(month, -12, GETDATE())),
                                     MONTH(DATEADD(month, -12, GETDATE())), 1)
      AND c.DT_DATA <  DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
    GROUP BY c.NR_DIA_SEMANA, c.NM_DIA_SEMANA, c.DT_DATA
)
SELECT nm                                                        AS nm_dia_semana,
       COUNT(*)                                                  AS qt_dias,
       CAST(SUM(vl_gasto) AS decimal(12,2))                      AS vl_total,
       CAST(AVG(vl_gasto) AS decimal(10,2))                      AS vl_media_dia,
       CAST(100.0 * SUM(vl_gasto) / SUM(SUM(vl_gasto)) OVER ()
            AS decimal(5,1))                                     AS pc_do_total
FROM diario
GROUP BY nr, nm
ORDER BY nr;
GO
