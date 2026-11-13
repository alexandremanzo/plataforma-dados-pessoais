/* =============================================================
   manzo-dados | Análise de investimentos
   -------------------------------------------------------------
   O que a posição vinda da API destravou: até ela existir, o DW
   sabia quanto cada ativo RENDEU e não sabia quanto você TEM dele.
   Cruzar as duas coisas é o que estas consultas fazem.

   AS DUAS FONTES, E O QUE CADA UMA COBRE:

     gold.fato_investimento          fluxo, desde 2021, do extrato
                                     em xlsx. Dividendo, IR, taxa,
                                     operação.

     gold.fato_posicao_investimento  posição, desde out/2026, da API
                                     da Pluggy. Uma foto por dia.

   Por isso "provento acumulado" tem cinco anos e "posição" tem a
   foto mais recente. Não são a mesma janela, e as consultas abaixo
   dizem qual usam.

   PROVENTO é DS_GRUPO = 'Proventos' em dim_categoria_investimento:
   Dividendo, Investback, Reembolso e Taxa de Remuneração. São 858
   eventos e R$ 22.439,74 desde maio/2022, TODOS com ativo
   identificado - o que torna este cruzamento confiável.

   Uso: abra no SSMS e rode um bloco por vez.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* =============================================================
   1. QUANTO TENHO x QUANTO JÁ ME RENDEU
   -------------------------------------------------------------
   A pergunta central. Posição da última foto contra provento
   acumulado, com o yield dos últimos doze meses.

   FULL JOIN de propósito: há ativo com provento e SEM posição -
   você saiu dele e ele continua no histórico - e há ativo com
   posição e sem provento nenhum. Um INNER JOIN esconderia os dois
   casos, que são justamente os interessantes.

   O YIELD É SOBRE A POSIÇÃO DE HOJE, não sobre o custo. Custo de
   aquisição não existe no DW para renda variável: a API só traz
   valor aplicado em renda fixa, e as transações dela alcançam
   doze meses. Então isto responde "quanto esta posição me paga
   por ano", e não "quanto rendeu sobre o que investi".
   ============================================================= */

WITH pos AS (
    SELECT SK_ATIVO, SUM(VL_LIQUIDO) AS vl
    FROM gold.fato_posicao_investimento
    WHERE SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
      AND DS_SITUACAO = 'ACTIVE'
    GROUP BY SK_ATIVO
),
prov AS (
    SELECT f.SK_ATIVO,
           SUM(f.VL_TRANSACAO) AS total,
           SUM(CASE WHEN c.DT_DATA >= DATEADD(month, -12, CAST(GETDATE() AS date))
                    THEN f.VL_TRANSACAO ELSE 0 END) AS m12,
           COUNT(DISTINCT c.NM_ANO_MES) AS meses_pagando,
           MIN(c.DT_DATA) AS primeiro,
           MAX(c.DT_DATA) AS ultimo
    FROM gold.fato_investimento f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
    JOIN gold.dim_categoria_investimento k
      ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
    WHERE k.DS_GRUPO = 'Proventos'
    GROUP BY f.SK_ATIVO
)
SELECT a.NM_ATIVO                                        AS ativo,
       a.TP_ATIVO                                        AS tipo,
       a.DS_ORIGEM_DADO                                  AS origem_cadastro,
       CAST(ISNULL(p.vl, 0)    AS decimal(12,2))         AS posicao,
       CAST(ISNULL(v.total, 0) AS decimal(12,2))         AS provento_total,
       CAST(ISNULL(v.m12, 0)   AS decimal(12,2))         AS provento_12m,
       CAST(100.0 * ISNULL(v.m12, 0) / NULLIF(p.vl, 0)
            AS decimal(6,2))                             AS yield_12m_pct,
       ISNULL(v.meses_pagando, 0)                        AS meses_pagando,
       v.primeiro, v.ultimo,
       CASE WHEN p.vl IS NULL      THEN 'saiu — só histórico'
            WHEN v.total IS NULL   THEN 'nunca pagou'
            WHEN v.m12 = 0         THEN 'parou de pagar'
            ELSE 'ativo e pagando' END                   AS situacao
FROM pos p
FULL JOIN prov v ON v.SK_ATIVO = p.SK_ATIVO
JOIN gold.dim_ativo a ON a.SK_ATIVO = ISNULL(p.SK_ATIVO, v.SK_ATIVO)
WHERE a.SK_ATIVO <> -1
ORDER BY ISNULL(v.total, 0) DESC;
GO

/* =============================================================
   2. YIELD POR CLASSE
   -------------------------------------------------------------
   Onde o dinheiro está contra onde a renda nasce. A diferença
   entre as duas colunas de percentual é o que mostra qual classe
   trabalha mais por real investido.
   ============================================================= */

WITH pos AS (
    SELECT p.SK_ATIVO, a.DS_CLASSE_ATIVO AS classe, SUM(p.VL_LIQUIDO) AS vl
    FROM gold.fato_posicao_investimento p
    JOIN gold.dim_ativo a ON a.SK_ATIVO = p.SK_ATIVO
    WHERE p.SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
      AND p.DS_SITUACAO = 'ACTIVE'
    GROUP BY p.SK_ATIVO, a.DS_CLASSE_ATIVO
),
prov AS (
    SELECT f.SK_ATIVO, SUM(f.VL_TRANSACAO) AS m12
    FROM gold.fato_investimento f
    JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
    JOIN gold.dim_categoria_investimento k
      ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
    WHERE k.DS_GRUPO = 'Proventos'
      AND c.DT_DATA >= DATEADD(month, -12, CAST(GETDATE() AS date))
    GROUP BY f.SK_ATIVO
)
SELECT p.classe,
       COUNT(*)                                             AS ativos,
       CAST(SUM(p.vl) AS decimal(14,2))                     AS posicao,
       CAST(100.0 * SUM(p.vl) / SUM(SUM(p.vl)) OVER ()
            AS decimal(5,1))                                AS pct_carteira,
       CAST(SUM(ISNULL(v.m12, 0)) AS decimal(12,2))         AS provento_12m,
       CAST(100.0 * SUM(ISNULL(v.m12, 0)) / SUM(SUM(ISNULL(v.m12, 0))) OVER ()
            AS decimal(5,1))                                AS pct_renda,
       CAST(100.0 * SUM(ISNULL(v.m12, 0)) / NULLIF(SUM(p.vl), 0)
            AS decimal(6,2))                                AS yield_12m_pct
FROM pos p
LEFT JOIN prov v ON v.SK_ATIVO = p.SK_ATIVO
GROUP BY p.classe
ORDER BY posicao DESC;
GO

/* =============================================================
   3. RENDA PASSIVA MÊS A MÊS
   -------------------------------------------------------------
   A série que diz se a renda está crescendo. 'ativos_pagando' ao
   lado do valor separa duas causas de um mês fraco: pagaram
   menos, ou pagaram menos ativos.
   ============================================================= */

SELECT c.NM_ANO_MES                                    AS mes,
       COUNT(*)                                        AS eventos,
       COUNT(DISTINCT f.SK_ATIVO)                      AS ativos_pagando,
       CAST(SUM(f.VL_TRANSACAO) AS decimal(12,2))      AS provento,
       CAST(AVG(SUM(f.VL_TRANSACAO)) OVER (
                ORDER BY c.NM_ANO_MES
                ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
            AS decimal(12,2))                          AS media_movel_12m
FROM gold.fato_investimento f
JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
JOIN gold.dim_categoria_investimento k
  ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
WHERE k.DS_GRUPO = 'Proventos'
GROUP BY c.NM_ANO_MES
ORDER BY c.NM_ANO_MES DESC;
GO

/* =============================================================
   4. CONCENTRAÇÃO
   -------------------------------------------------------------
   Quanto da carteira depende de poucos ativos, e quantos são
   pequenos demais para mover o resultado - esses custam atenção
   e corretagem sem pagar por isso.
   ============================================================= */

WITH pos AS (
    SELECT a.NM_ATIVO, a.TP_ATIVO, SUM(p.VL_LIQUIDO) AS vl
    FROM gold.fato_posicao_investimento p
    JOIN gold.dim_ativo a ON a.SK_ATIVO = p.SK_ATIVO
    WHERE p.SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
      AND p.DS_SITUACAO = 'ACTIVE' AND p.VL_LIQUIDO > 0
    GROUP BY a.NM_ATIVO, a.TP_ATIVO
)
SELECT NM_ATIVO AS ativo, TP_ATIVO AS tipo,
       CAST(vl AS decimal(12,2))                                  AS posicao,
       CAST(100.0 * vl / SUM(vl) OVER () AS decimal(5,2))         AS pct,
       CAST(100.0 * SUM(vl) OVER (ORDER BY vl DESC
                                  ROWS UNBOUNDED PRECEDING)
            / SUM(vl) OVER () AS decimal(5,1))                    AS pct_acumulado,
       ROW_NUMBER() OVER (ORDER BY vl DESC)                       AS posicao_ranking
FROM pos
ORDER BY vl DESC;
GO

/* =============================================================
   5. CALENDÁRIO DE VENCIMENTOS
   -------------------------------------------------------------
   Só renda fixa tem vencimento, e é a única parte da carteira em
   que o caixa volta numa data conhecida. Serve para planejar
   reinvestimento e para não ser pego por concentração de
   vencimento num ano só.
   ============================================================= */

SELECT YEAR(DT_VENCIMENTO)                         AS ano,
       COUNT(*)                                    AS papeis,
       CAST(SUM(VL_LIQUIDO) AS decimal(12,2))      AS valor,
       CAST(100.0 * SUM(VL_LIQUIDO) / SUM(SUM(VL_LIQUIDO)) OVER ()
            AS decimal(5,1))                       AS pct_da_renda_fixa,
       MIN(DT_VENCIMENTO)                          AS primeiro_vencimento
FROM gold.fato_posicao_investimento
WHERE SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
  AND DS_SITUACAO = 'ACTIVE' AND DT_VENCIMENTO IS NOT NULL
GROUP BY YEAR(DT_VENCIMENTO)
ORDER BY ano;
GO

/* =============================================================
   6. O QUE SAIU DA CARTEIRA MAS AINDA APARECE
   -------------------------------------------------------------
   Ativo com provento e sem posição. Duas leituras possíveis, e a
   consulta não decide entre elas:

     - você vendeu, e o histórico fica (correto)
     - o ativo existe na dim DUAS VEZES, com nomes diferentes, e a
       posição foi para o outro membro (erro de cadastro)

   A segunda acontece: XP HABITAT FII e XPHB11 são o mesmo fundo,
   um cadastrado por nome e outro por ticker, ambos vindos do
   extrato. Quando o provento não zera há meses, desconfie.
   ============================================================= */

WITH pos AS (
    SELECT SK_ATIVO FROM gold.fato_posicao_investimento
    WHERE SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
      AND DS_SITUACAO = 'ACTIVE' AND VL_LIQUIDO > 0
    GROUP BY SK_ATIVO
)
SELECT a.NM_ATIVO                                   AS ativo,
       a.TP_ATIVO                                   AS tipo,
       a.DS_ORIGEM_DADO                             AS origem_cadastro,
       CAST(SUM(f.VL_TRANSACAO) AS decimal(12,2))   AS provento_total,
       MAX(c.DT_DATA)                               AS ultimo_provento,
       DATEDIFF(month, MAX(c.DT_DATA), GETDATE())   AS meses_sem_pagar
FROM gold.fato_investimento f
JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA_MOVIMENTACAO
JOIN gold.dim_ativo a ON a.SK_ATIVO = f.SK_ATIVO
JOIN gold.dim_categoria_investimento k
  ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
WHERE k.DS_GRUPO = 'Proventos'
  AND f.SK_ATIVO NOT IN (SELECT SK_ATIVO FROM pos)
  AND a.SK_ATIVO <> -1
GROUP BY a.NM_ATIVO, a.TP_ATIVO, a.DS_ORIGEM_DADO
ORDER BY provento_total DESC;
GO

/* =============================================================
   7. POSIÇÃO QUE NUNCA PAGOU PROVENTO
   -------------------------------------------------------------
   Nem toda posição sem provento é problema. Fundo de investimento
   normalmente NÃO distribui - o ganho fica na cota, e aparecer
   aqui é o esperado. FII e ação que nunca pagaram, não: ou são
   recentes, ou o ativo está cadastrado duas vezes e o provento foi
   para o outro membro.

   A coluna 'esperado' separa os dois casos, para a lista não virar
   uma lista de suspeitas que se ignora por ser sempre a mesma.

   NÃO HÁ DETECÇÃO AUTOMÁTICA DE DUPLICATA AQUI, e isso é decisão.
   A primeira versão desta consulta cruzava "só posição" com "só
   provento" pelo tipo do ativo, e produzia pares falsos em série -
   oito ativos diferentes casados com o mesmo "Trend Investback"
   só porque todos eram Fundo. Casar por semelhança de texto já foi
   testado neste projeto e reprovado: 0,79 para "CDB - BANCO BMG
   S.A" contra "LCA BANCO BV S/A". Fica a lista; a decisão é sua.

   Duplicata conhecida, para referência: XP HABITAT FII e XPHB11
   são o mesmo fundo, um cadastrado por nome e outro por ticker,
   ambos vindos do extrato.
   ============================================================= */

SELECT a.NM_ATIVO                                        AS ativo,
       a.TP_ATIVO                                        AS tipo,
       a.DS_ORIGEM_DADO                                  AS origem_cadastro,
       CAST(SUM(p.VL_LIQUIDO) AS decimal(12,2))          AS posicao,
       CASE WHEN a.TP_ATIVO IN ('Fundo', 'ETF')
            THEN 'sim — fundo acumula na cota'
            ELSE 'NÃO — investigar' END                  AS esperado
FROM gold.fato_posicao_investimento p
JOIN gold.dim_ativo a ON a.SK_ATIVO = p.SK_ATIVO
WHERE p.SK_DATA = (SELECT MAX(SK_DATA) FROM gold.fato_posicao_investimento)
  AND p.DS_SITUACAO = 'ACTIVE' AND p.VL_LIQUIDO > 0
  AND NOT EXISTS (
      SELECT 1 FROM gold.fato_investimento f
      JOIN gold.dim_categoria_investimento k
        ON k.SK_CATEGORIA_INVESTIMENTO = f.SK_CATEGORIA_INVESTIMENTO
      WHERE f.SK_ATIVO = a.SK_ATIVO AND k.DS_GRUPO = 'Proventos')
GROUP BY a.NM_ATIVO, a.TP_ATIVO, a.DS_ORIGEM_DADO
ORDER BY CASE WHEN a.TP_ATIVO IN ('Fundo', 'ETF') THEN 1 ELSE 0 END,
         posicao DESC;
GO
