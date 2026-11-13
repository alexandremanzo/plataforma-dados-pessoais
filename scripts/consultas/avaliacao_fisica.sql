/* =============================================================
   manzo-dados | Consultas: avaliacao fisica
   -------------------------------------------------------------
   Nao e DDL e nao entra no executa.ps1: sao consultas de analise,
   para rodar a mao no SSMS. Cada bloco e independente.

   O fato guarda chaves substitutas; as dimensoes e que tem nome.
   Sem o join, SELECT * devolve numeros sem significado.

   O GRAO E "uma linha por avaliacao, metrica E SEGMENTO". Uma
   avaliacao com exame InBody rende ~47 linhas: 19 de corpo inteiro
   mais 28 das cinco partes do corpo. As que so tem a planilha
   rendem 11 - e a diferenca e a analise segmentar, que o
   preenchimento manual nunca teve.
   ============================================================= */

USE [db-manzo];
GO

/* -------------------------------------------------------------
   1. Uma avaliacao inteira, com tudo resolvido
   -------------------------------------------------------------
   Troque o numero para ver outra. A ultima e a 33 (28/08/2026).
   ------------------------------------------------------------- */

DECLARE @avaliacao int = 33;

SELECT c.DT_DATA                              AS data,
       f.NR_AVALIACAO                         AS n,
       m.DS_GRUPO                             AS grupo,
       m.NM_METRICA                           AS metrica,
       s.NM_SEGMENTO                          AS segmento,
       m.DS_UNIDADE                           AS unidade,

       f.VL_MEDIDA                            AS valor,
       f.VL_MEDIDA_ANTERIOR                   AS anterior,
       f.VL_VARIACAO                          AS variacao,
       f.FL_MELHOROU                          AS melhorou,

       /* A faixa vem impressa no proprio exame e MUDA A CADA UM,
          porque depende de idade e altura. Nula nas linhas que
          vieram da planilha. */
       f.VL_REFERENCIA_MIN                    AS ref_min,
       f.VL_REFERENCIA_MAX                    AS ref_max,
       CASE WHEN f.VL_REFERENCIA_MIN IS NULL THEN NULL
            WHEN f.VL_MEDIDA < f.VL_REFERENCIA_MIN THEN 'Abaixo da faixa'
            WHEN f.VL_MEDIDA > f.VL_REFERENCIA_MAX THEN 'Acima da faixa'
            ELSE 'Dentro da faixa' END        AS posicao_na_faixa,

       f.DS_AVALIACAO                         AS aval_maquina,
       m.DS_SENTIDO_MELHOR                    AS sentido_bom,
       f.FL_MEDIDO                            AS medido,
       f.DS_ORIGEM                            AS origem
FROM gold.fato_avaliacao_fisica f
JOIN gold.dim_metrica_corporal  m ON m.SK_METRICA  = f.SK_METRICA
JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
JOIN gold.dim_calendario        c ON c.SK_DATA     = f.SK_DATA
WHERE f.NR_AVALIACAO = @avaliacao
ORDER BY m.NR_ORDEM, s.NR_ORDEM;
GO


/* -------------------------------------------------------------
   2. Evolucao de uma metrica ao longo dos anos
   -------------------------------------------------------------
   Para o grafico de longo prazo, filtre FL_SERIE_CONTINUA = 'S':
   so cinco metricas cobrem os 18 anos, e as demais produzem
   linhas que comecam ou terminam no meio.
   ------------------------------------------------------------- */

SELECT c.DT_DATA AS data, f.VL_MEDIDA AS valor, f.VL_VARIACAO AS variacao,
       f.DS_ORIGEM AS origem
FROM gold.fato_avaliacao_fisica f
JOIN gold.dim_metrica_corporal  m ON m.SK_METRICA  = f.SK_METRICA
JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
JOIN gold.dim_calendario        c ON c.SK_DATA     = f.SK_DATA
WHERE m.NM_METRICA  = '% Gordura'
  AND s.NM_SEGMENTO = 'Corpo inteiro'
ORDER BY c.DT_DATA;
GO


/* -------------------------------------------------------------
   3. A analise segmentar no tempo: onde falta musculo
   -------------------------------------------------------------
   E a consulta que o preenchimento manual nunca permitiu, e a que
   mostrou a queda das pernas entre 2022 e 2024.

   DUAS DATAS NAO APARECEM AQUI - 12/12/2022 e 27/09/2024. Elas
   existem na base, mas so com os 11 campos da planilha: a planilha
   nunca teve analise segmentar, entao nao ha o que preencher. A de
   2022 e justamente o pico da serie.
   ------------------------------------------------------------- */

SELECT c.DT_DATA AS data,
       MAX(CASE WHEN s.NM_SEGMENTO = 'Braço esquerdo' THEN f.VL_MEDIDA END) AS braco_esq,
       MAX(CASE WHEN s.NM_SEGMENTO = 'Braço direito'  THEN f.VL_MEDIDA END) AS braco_dir,
       MAX(CASE WHEN s.NM_SEGMENTO = 'Tronco'         THEN f.VL_MEDIDA END) AS tronco,
       MAX(CASE WHEN s.NM_SEGMENTO = 'Perna esquerda' THEN f.VL_MEDIDA END) AS perna_esq,
       MAX(CASE WHEN s.NM_SEGMENTO = 'Perna direita'  THEN f.VL_MEDIDA END) AS perna_dir
FROM gold.fato_avaliacao_fisica f
JOIN gold.dim_metrica_corporal  m ON m.SK_METRICA  = f.SK_METRICA
JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
JOIN gold.dim_calendario        c ON c.SK_DATA     = f.SK_DATA
WHERE m.NM_METRICA = 'Massa Magra Segmentar'
GROUP BY c.DT_DATA
ORDER BY c.DT_DATA;
GO


/* -------------------------------------------------------------
   4. Assimetria entre os dois lados
   -------------------------------------------------------------
   DS_LADO existe na dimensao justamente para isto: comparar
   esquerdo com direito sem depender do nome do segmento.
   ------------------------------------------------------------- */

SELECT c.DT_DATA AS data, s.DS_REGIAO AS regiao,
       MAX(CASE WHEN s.DS_LADO = 'Esquerdo' THEN f.VL_MEDIDA END) AS esquerdo,
       MAX(CASE WHEN s.DS_LADO = 'Direito'  THEN f.VL_MEDIDA END) AS direito,
       MAX(CASE WHEN s.DS_LADO = 'Esquerdo' THEN f.VL_MEDIDA END)
     - MAX(CASE WHEN s.DS_LADO = 'Direito'  THEN f.VL_MEDIDA END) AS diferenca
FROM gold.fato_avaliacao_fisica f
JOIN gold.dim_metrica_corporal  m ON m.SK_METRICA  = f.SK_METRICA
JOIN gold.dim_segmento_corporal s ON s.SK_SEGMENTO = f.SK_SEGMENTO
JOIN gold.dim_calendario        c ON c.SK_DATA     = f.SK_DATA
WHERE m.NM_METRICA = 'Massa Magra Segmentar'
  AND s.DS_LADO IN ('Esquerdo', 'Direito')
GROUP BY c.DT_DATA, s.DS_REGIAO
ORDER BY c.DT_DATA, s.DS_REGIAO;
GO


/* -------------------------------------------------------------
   5. O que a planilha cobriu porque o OCR nao leu
   -------------------------------------------------------------
   As duas origens se completam. Esta consulta mostra onde a
   planilha entrou no lugar do arquivo, de 2018 em diante - e e por
   ela que se decide se vale ajustar o extrator.
   ------------------------------------------------------------- */

SELECT m.NM_METRICA AS metrica, COUNT(*) AS medidas,
       MIN(c.NR_ANO) AS de, MAX(c.NR_ANO) AS ate
FROM gold.fato_avaliacao_fisica f
JOIN gold.dim_metrica_corporal m ON m.SK_METRICA = f.SK_METRICA
JOIN gold.dim_calendario       c ON c.SK_DATA    = f.SK_DATA
WHERE f.DS_ORIGEM = 'Planilha' AND c.NR_ANO >= 2018
GROUP BY m.NM_METRICA
ORDER BY medidas DESC;
GO


/* -------------------------------------------------------------
   6. Divergencia entre as duas origens
   -------------------------------------------------------------
   Onde arquivo e planilha medem a mesma coisa no mesmo dia, so uma
   entra no fato - o arquivo vence. Esta consulta olha a silver das
   duas e mostra onde elas DISCORDAM, que e como se descobre erro
   de digitacao.

   Foi assim que apareceu a estatura de 181 cm na avaliacao de
   uma data de 2026, cercada de 177 em todos os exames.
   ------------------------------------------------------------- */

SELECT p.dt_avaliacao AS data, p.ds_metrica AS metrica,
       p.vl_medida AS na_planilha, a.vl_medida AS no_arquivo,
       ROUND(a.vl_medida - p.vl_medida, 2) AS diferenca
FROM silver.avaliacao_fisica p
JOIN silver.avaliacao_inbody a
  ON a.dt_exame    = p.dt_avaliacao
 AND a.nm_metrica  = p.ds_metrica
 AND a.nm_segmento = 'Corpo inteiro'
WHERE ABS(a.vl_medida - p.vl_medida) > 0.05
ORDER BY ABS(a.vl_medida - p.vl_medida) DESC;
GO
