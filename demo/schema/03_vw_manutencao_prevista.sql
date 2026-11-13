-- =====================================================================
-- O que esta vencendo no carro em uso: o plano do fabricante
-- (gold.dim_revisao_programada) contra a ultima vez que cada item foi
-- feito (gold.fato_manutencao_auto), em km E em tempo; vale o que
-- vencer primeiro.
--
-- Versao simplificada da view do projeto: la o historico casa com o
-- plano por um de-para de texto (silver.de_para_item_revisao); aqui o
-- elo e a categoria da manutencao.
-- NR_KM_RESTANTE negativo significa VENCIDO.
-- =====================================================================
CREATE VIEW gold.vw_manutencao_prevista AS
WITH ultima AS (
    SELECT f.SK_VEICULO, f.SK_CATEGORIA_MANUTENCAO,
           MAX(f.NR_KM)     AS NR_KM_ULTIMA_TROCA,
           MAX(c.DT_DATA)   AS DT_ULTIMA_TROCA
      FROM gold.fato_manutencao_auto f
      JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
     GROUP BY f.SK_VEICULO, f.SK_CATEGORIA_MANUTENCAO
),
base AS (
    SELECT v.NM_VEICULO, v.DT_PRIMEIRA AS DT_ENTRADA_BASE, v.NR_KM_ATUAL,
           r.NM_ITEM, r.NM_SISTEMA, r.DS_ACAO, CAST('Fabricante' AS varchar(20)) AS DS_ORIGEM_REGRA,
           r.NR_INTERVALO_KM, r.NR_INTERVALO_MESES,
           u.DT_ULTIMA_TROCA, u.NR_KM_ULTIMA_TROCA,
           u.NR_KM_ULTIMA_TROCA + r.NR_INTERVALO_KM AS NR_KM_PROXIMA_TROCA,
           DATEADD(month, r.NR_INTERVALO_MESES, u.DT_ULTIMA_TROCA) AS DT_PROXIMA_TROCA
      FROM gold.dim_revisao_programada r
      JOIN gold.dim_veiculo v ON v.SK_VEICULO = r.SK_VEICULO
      LEFT JOIN ultima u ON u.SK_VEICULO = r.SK_VEICULO AND u.SK_CATEGORIA_MANUTENCAO = r.SK_CATEGORIA_MANUTENCAO
     WHERE v.FL_ATIVO = 'S'
),
folga AS (
    SELECT b.*, b.NR_KM_PROXIMA_TROCA - b.NR_KM_ATUAL AS NR_KM_RESTANTE,
           DATEDIFF(month, CAST(SYSDATETIME() AS date), b.DT_PROXIMA_TROCA) AS NR_MESES_RESTANTES
      FROM base b
)
SELECT NM_VEICULO, NM_ITEM, NM_SISTEMA, DS_ACAO, DS_ORIGEM_REGRA, NR_INTERVALO_KM, NR_INTERVALO_MESES,
       DT_ENTRADA_BASE, DT_ULTIMA_TROCA, NR_KM_ULTIMA_TROCA, NR_KM_ATUAL, NR_KM_PROXIMA_TROCA,
       NR_KM_RESTANTE, DT_PROXIMA_TROCA, NR_MESES_RESTANTES,
       CASE WHEN DT_ULTIMA_TROCA IS NULL      THEN 'Sem registro'
            WHEN NR_KM_RESTANTE <= 0          THEN 'Vencido'
            WHEN NR_MESES_RESTANTES <= 0      THEN 'Vencido'
            WHEN NR_KM_RESTANTE <= 1000       THEN 'Vence em breve'
            WHEN NR_MESES_RESTANTES <= 1      THEN 'Vence em breve'
            ELSE 'Em dia' END AS DS_SITUACAO
  FROM folga;
GO
