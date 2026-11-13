/* =============================================================
   manzo-dados | 39 - Camada Gold: revisao programada
   -------------------------------------------------------------
   gold.dim_revisao_programada
   gold.vw_manutencao_prevista  (reescrita)

   A REGRA PASSA A SER POR VEICULO. Ate aqui o intervalo morava em
   gold.dim_categoria_auto, uma linha por categoria, valendo para
   qualquer carro. Isso e um defeito latente: oleo a 5.000 km e
   regime de Sedan, e o fabricante do SUV manda 10.000. So nao
   mordeu porque a view considera apenas o veiculo ativo, e hoje ha
   um so. Com dois carros mantidos ao mesmo tempo, a regra global
   viraria mentira.

   DUAS FONTES DE REGRA, DECLARADAS. O SUV tem plano de fabrica; o
   Sedan nao. Em vez de escolher uma e descartar a outra, a view
   usa o plano onde ele existe e a sua aba "Tempo Troca" onde nao
   existe, e diz qual das duas esta valendo em DS_ORIGEM_REGRA - no
   mesmo espirito do DS_ORIGEM_CLASSE de dim_ativo, que separa o que
   voce classificou do que a regra deduziu.

   O QUE MUDA NA PREVISAO. Ela deixa de ser so quilometragem. O
   limite que estava documentado na versao anterior - "logo depois
   de uma visita TUDO aparece Em dia por construcao" - existia
   porque o hodometro so e registrado quando o carro vai a oficina.
   O intervalo em meses nao depende disso: ele corre sozinho.

   E APARECE O QUE NUNCA FOI FEITO. A versao anterior exigia
   NR_KM_ULTIMA_TROCA IS NOT NULL e descartava em silencio o item
   que nunca foi trocado - exatamente o que mais importa saber. O
   fluido do cambio CVT vence a 80.000 km, o carro esta com 100.380
   e nao ha registro nenhum dele. Agora isso tem nome: "Sem
   registro".

   Pre-requisitos: 00, 01, 04 (calendario), 26, 38
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. A regra, por veiculo e item
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_revisao_programada') IS NULL
BEGIN
    CREATE TABLE gold.dim_revisao_programada (
        SK_REVISAO_PROGRAMADA   int IDENTITY(1,1) NOT NULL,

        SK_VEICULO              int           NOT NULL,
        SK_CATEGORIA_MANUTENCAO int           NOT NULL,

        NM_ITEM                 varchar(200)  NOT NULL,
        NM_SISTEMA              varchar(120)  NULL,
        NR_INTERVALO_KM         int           NULL,
        NR_INTERVALO_MESES      int           NULL,
        DS_ACAO                 varchar(30)   NULL,
        DS_ESPECIFICACAO        varchar(500)  NULL,

        HASH_NEGOCIO            char(64)      NOT NULL,
        DT_CARGA                datetime2(3)  NOT NULL
            CONSTRAINT DF_dim_revisao_prog_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_dim_revisao_programada PRIMARY KEY (SK_REVISAO_PROGRAMADA),
        CONSTRAINT UQ_dim_revisao_programada_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_dim_revisao_veiculo FOREIGN KEY (SK_VEICULO)
            REFERENCES gold.dim_veiculo (SK_VEICULO),
        CONSTRAINT FK_dim_revisao_categoria FOREIGN KEY (SK_CATEGORIA_MANUTENCAO)
            REFERENCES gold.dim_categoria_auto (SK_CATEGORIA_MANUTENCAO)
    );

    CREATE INDEX IX_dim_revisao_veiculo ON gold.dim_revisao_programada (SK_VEICULO);
END
GO

/* Sem membro -1, e de proposito: nenhum fato aponta para ca. Esta
   tabela e consultada pela view, nao referenciada por chave
   estrangeira de fato nenhum, entao nao ha lancamento orfao que
   precise de um lugar para cair. */


/* -------------------------------------------------------------
   2. A previsao
   ------------------------------------------------------------- */

CREATE OR ALTER VIEW gold.vw_manutencao_prevista AS
/*
   O QUE ESTA VENCENDO, para o veiculo em uso.

   Tres passos: reunir a regra que vale para cada veiculo, achar a
   ultima vez que cada item foi feito, e comparar com onde o carro
   esta hoje - em quilometragem E em tempo.

   O CRITERIO E O QUE VENCER PRIMEIRO, como manda o fabricante
   ("10.000 km ou 12 meses, o que ocorrer antes"). Quando os dois
   existem, vence quem tem menos FOLGA RELATIVA ao proprio
   intervalo: comparar 3.000 km com 4 meses direto nao significa
   nada, mas 30% de um intervalo contra 33% do outro, sim.

   NR_KM_RESTANTE negativo significa VENCIDO.
*/
WITH regra AS (
    -- Plano do fabricante: uma linha por veiculo e item.
    SELECT r.SK_VEICULO,
           r.NM_ITEM                    AS NM_REGRA,
           r.NM_SISTEMA,
           r.SK_CATEGORIA_MANUTENCAO,
           r.NR_INTERVALO_KM,
           r.NR_INTERVALO_MESES,
           r.DS_ACAO,
           CAST('Fabricante' AS varchar(20)) AS DS_ORIGEM_REGRA
    FROM gold.dim_revisao_programada r

    UNION ALL

    -- Sua aba "Tempo Troca", so para o veiculo que nao tem plano de
    -- fabrica carregado. Sem isso o Sedan perderia a previsao que
    -- ja tinha; com isso, nenhum carro fica descoberto.
    SELECT v.SK_VEICULO,
           c.NM_CATEGORIA,
           NULL,
           c.SK_CATEGORIA_MANUTENCAO,
           c.NR_INTERVALO_KM,
           NULL,
           NULL,
           CAST('Sua planilha' AS varchar(20))
    FROM gold.dim_veiculo v
    CROSS JOIN gold.dim_categoria_auto c
    WHERE v.SK_VEICULO > 0
      AND c.FL_TEM_INTERVALO = 'S'
      AND NOT EXISTS (SELECT 1 FROM gold.dim_revisao_programada r
                       WHERE r.SK_VEICULO = v.SK_VEICULO)
),
-- Cada lancamento do historico decide a QUAL item do plano pertence.
-- Quando mais de um padrao casa, vence o mais longo: e o que impede
-- "filtro de ar" de roubar o lancamento de "filtro de ar
-- condicionado".
evento_item AS (
    SELECT f.SK_VEICULO, f.SK_CATEGORIA_MANUTENCAO, f.NR_KM, f.SK_DATA,
           d.nm_item_plano,
           ROW_NUMBER() OVER (PARTITION BY f.SK_MANUTENCAO
                              ORDER BY LEN(d.ds_padrao_item) DESC) AS rn
    FROM gold.fato_manutencao_auto f
    JOIN silver.de_para_item_revisao d
      ON f.DS_ITEM COLLATE Latin1_General_CI_AI
         LIKE '%' + d.ds_padrao_item COLLATE Latin1_General_CI_AI + '%'
),
ultima_fabricante AS (
    SELECT e.SK_VEICULO, e.nm_item_plano AS NM_REGRA,
           MAX(e.NR_KM)   AS NR_KM_ULTIMA_TROCA,
           MAX(cal.DT_DATA) AS DT_ULTIMA_TROCA
    FROM evento_item e
    JOIN gold.dim_calendario cal ON cal.SK_DATA = e.SK_DATA
    WHERE e.rn = 1
    GROUP BY e.SK_VEICULO, e.nm_item_plano
),
ultima_categoria AS (
    SELECT f.SK_VEICULO, c.NM_CATEGORIA AS NM_REGRA,
           MAX(f.NR_KM)     AS NR_KM_ULTIMA_TROCA,
           MAX(cal.DT_DATA) AS DT_ULTIMA_TROCA
    FROM gold.fato_manutencao_auto f
    JOIN gold.dim_categoria_auto c
      ON c.SK_CATEGORIA_MANUTENCAO = f.SK_CATEGORIA_MANUTENCAO
    JOIN gold.dim_calendario cal ON cal.SK_DATA = f.SK_DATA
    GROUP BY f.SK_VEICULO, c.NM_CATEGORIA
),
base AS (
    SELECT v.NM_VEICULO,
           v.DT_PRIMEIRA        AS DT_ENTRADA_BASE,
           v.NR_KM_ATUAL,
           g.NM_REGRA,
           g.NM_SISTEMA,
           g.DS_ACAO,
           g.DS_ORIGEM_REGRA,
           g.NR_INTERVALO_KM,
           g.NR_INTERVALO_MESES,
           u.DT_ULTIMA_TROCA,
           u.NR_KM_ULTIMA_TROCA,
           u.NR_KM_ULTIMA_TROCA + g.NR_INTERVALO_KM AS NR_KM_PROXIMA_TROCA,
           DATEADD(month, g.NR_INTERVALO_MESES, u.DT_ULTIMA_TROCA) AS DT_PROXIMA_TROCA
    FROM regra g
    JOIN gold.dim_veiculo v ON v.SK_VEICULO = g.SK_VEICULO
    LEFT JOIN (
        SELECT SK_VEICULO, NM_REGRA, NR_KM_ULTIMA_TROCA, DT_ULTIMA_TROCA
        FROM ultima_fabricante
        UNION ALL
        SELECT SK_VEICULO, NM_REGRA, NR_KM_ULTIMA_TROCA, DT_ULTIMA_TROCA
        FROM ultima_categoria
    ) u ON u.SK_VEICULO = g.SK_VEICULO AND u.NM_REGRA = g.NM_REGRA
    WHERE v.FL_ATIVO = 'S'
),
folga AS (
    SELECT b.*,
           b.NR_KM_PROXIMA_TROCA - b.NR_KM_ATUAL AS NR_KM_RESTANTE,
           DATEDIFF(month, CAST(SYSDATETIME() AS date),
                    b.DT_PROXIMA_TROCA)          AS NR_MESES_RESTANTES
    FROM base b
)
SELECT NM_VEICULO,
       NM_REGRA           AS NM_ITEM,
       NM_SISTEMA,
       DS_ACAO,
       DS_ORIGEM_REGRA,
       NR_INTERVALO_KM,
       NR_INTERVALO_MESES,
       DT_ENTRADA_BASE,
       DT_ULTIMA_TROCA,
       NR_KM_ULTIMA_TROCA,
       NR_KM_ATUAL,
       NR_KM_PROXIMA_TROCA,
       NR_KM_RESTANTE,
       DT_PROXIMA_TROCA,
       NR_MESES_RESTANTES,
       CASE
           WHEN DT_ULTIMA_TROCA IS NULL THEN NULL
           WHEN NR_KM_RESTANTE IS NULL THEN 'Tempo'
           WHEN NR_MESES_RESTANTES IS NULL THEN 'Km'
           WHEN 1.0 * NR_KM_RESTANTE / NULLIF(NR_INTERVALO_KM, 0)
                <= 1.0 * NR_MESES_RESTANTES / NULLIF(NR_INTERVALO_MESES, 0)
                THEN 'Km'
           ELSE 'Tempo'
       END AS DS_CRITERIO,
       CASE
           WHEN DT_ULTIMA_TROCA IS NULL             THEN 'Sem registro'
           WHEN NR_KM_RESTANTE   <= 0               THEN 'Vencido'
           WHEN NR_MESES_RESTANTES <= 0             THEN 'Vencido'
           WHEN NR_KM_RESTANTE   <= 1000            THEN 'Vence em breve'
           WHEN NR_MESES_RESTANTES <= 1             THEN 'Vence em breve'
           ELSE 'Em dia'
       END AS DS_SITUACAO
FROM folga;
GO


/* -------------------------------------------------------------
   3. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | A regra de revisao que vale para cada veiculo, uma linha por veiculo e '
       + N'item do fabricante - 21 para o SUV. '
       + N'POR QUE POR VEICULO E NAO POR CATEGORIA. dim_categoria_auto guarda um intervalo '
       + N'so, aplicado a qualquer carro: oleo a 5.000 km e regime de Sedan, e o '
       + N'fabricante do SUV manda 10.000. Alem disso a categoria e grossa demais para o '
       + N'plano - "Filtro" cobre quatro itens com intervalos diferentes. '
       + N'NAO E DIMENSAO DE FATO NENHUM: nenhuma chave estrangeira aponta para ca. E uma '
       + N'tabela de REGRA, consultada por gold.vw_manutencao_prevista. Por isso nao tem '
       + N'membro -1.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', NULL, @d;

SET @d = N'Chave substituta da regra.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'SK_REVISAO_PROGRAMADA', @d;
SET @d = N'Chave para gold.dim_veiculo: a que carro esta regra se aplica. O plano do SUV '
       + N'nao vale para o Sedan.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'SK_VEICULO', @d;
SET @d = N'Chave para gold.dim_categoria_auto: em que categoria da SUA classificacao os '
       + N'lancamentos deste item costumam cair. Serve para cruzar a regra com o gasto no '
       + N'Power BI. Vale -1 quando o item nunca apareceu no historico ou quando o de-para '
       + N'nao o alcanca - e ai a previsao dele sai como "Sem registro".';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'SK_CATEGORIA_MANUTENCAO', @d;
SET @d = N'Item ou componente, na grafia do fabricante.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'NM_ITEM', @d;
SET @d = N'Sistema do veiculo: Motor, Freios, Suspensao, Cambio CVT. Agrupa a previsao por '
       + N'area do carro.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'NM_SISTEMA', @d;
SET @d = N'Quilometros entre uma intervencao e a proxima.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'NR_INTERVALO_KM', @d;
SET @d = N'Meses entre uma intervencao e a proxima. VALE EM PARALELO ao intervalo em km, e '
       + N'o fabricante manda seguir o que vencer primeiro. E a coluna que faz a previsao '
       + N'funcionar sem depender de o hodometro ser anotado.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'NR_INTERVALO_MESES', @d;
SET @d = N'Troca, Inspeção ou Serviço. Uma inspecao vencida nao tem a mesma urgencia de um '
       + N'fluido vencido, e sem esta coluna as duas apareceriam iguais.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'DS_ACAO', @d;
SET @d = N'Especificacao tecnica: qual oleo, qual fluido, qual norma.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'DS_ESPECIFICACAO', @d;
SET @d = N'Identidade da regra, herdada da silver.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando a regra foi carregada na gold.';
EXEC dbo.sp_documenta 'gold', 'dim_revisao_programada', 'DT_CARGA', @d;

SET @d = N'GOLD | O QUE ESTA VENCENDO no veiculo em uso. Para cada item previsto, cruza a '
       + N'ultima vez que foi feito com o intervalo recomendado - em quilometragem E em '
       + N'tempo - e diz quanto falta. '
       + N'O CRITERIO E O QUE VENCER PRIMEIRO, como manda o fabricante. '
       + N'DUAS FONTES DE REGRA: o plano de fabrica onde ele existe (SUV) e a aba "Tempo '
       + N'Troca" da sua planilha onde nao existe (Sedan), declaradas em DS_ORIGEM_REGRA. '
       + N'Considera apenas o veiculo ATIVO: prever troca de carro que nao se tem mais e '
       + N'ruido, e como o hodometro do antigo e maior, tudo apareceria vencido. '
       + N'MOSTRA O QUE NUNCA FOI FEITO. A versao anterior desta view exigia haver uma '
       + N'troca anterior e descartava em silencio justamente o item nunca trocado. Agora '
       + N'ele aparece como "Sem registro" - e e ali que esta o alerta caro, como o fluido '
       + N'do cambio CVT.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', NULL, @d;

SET @d = N'Veiculo em uso.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NM_VEICULO', @d;
SET @d = N'Item previsto. Vem do plano do fabricante ou, na falta dele, da categoria da sua '
       + N'planilha - veja DS_ORIGEM_REGRA.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NM_ITEM', @d;
SET @d = N'Sistema do veiculo a que o item pertence. Nulo quando a regra vem da sua '
       + N'planilha, que nao classifica por sistema.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NM_SISTEMA', @d;
SET @d = N'Troca, Inspeção ou Serviço. Separa o que precisa de oficina do que precisa so de '
       + N'um olhar.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DS_ACAO', @d;
SET @d = N'De onde vem a regra: Fabricante (plano oficial do modelo) ou Sua planilha (aba '
       + N'"Tempo Troca"). Existe para a previsao nao dar a impressao de ter uma origem so.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DS_ORIGEM_REGRA', @d;
SET @d = N'Quilometros recomendados entre intervencoes.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_INTERVALO_KM', @d;
SET @d = N'Meses recomendados entre intervencoes. Nulo quando a regra vem da sua planilha, '
       + N'que so tem quilometragem.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_INTERVALO_MESES', @d;
SET @d = N'Data da primeira manutencao registrada para este veiculo. LEIA JUNTO COM "Sem '
       + N'registro": o SUV entrou na base com 94.200 km ja rodados, entao nao haver '
       + N'registro de um item NAO significa que ele nunca foi feito - significa que nao '
       + N'foi feito por voce, desde que o carro e seu.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DT_ENTRADA_BASE', @d;
SET @d = N'Data em que este item foi feito pela ultima vez neste veiculo.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DT_ULTIMA_TROCA', @d;
SET @d = N'Quilometragem em que este item foi feito pela ultima vez.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_KM_ULTIMA_TROCA', @d;
SET @d = N'Quilometragem atual do veiculo, derivada da maior ja registrada.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_KM_ATUAL', @d;
SET @d = N'Quilometragem em que a proxima intervencao vence.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_KM_PROXIMA_TROCA', @d;
SET @d = N'Quantos quilometros faltam. NEGATIVO SIGNIFICA VENCIDO.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_KM_RESTANTE', @d;
SET @d = N'Data em que a proxima intervencao vence pelo criterio de tempo: ultima troca '
       + N'mais o intervalo em meses. Nao depende de o hodometro ser anotado.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DT_PROXIMA_TROCA', @d;
SET @d = N'Quantos meses faltam. NEGATIVO SIGNIFICA VENCIDO.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'NR_MESES_RESTANTES', @d;
SET @d = N'Qual dos dois criterios vence primeiro: Km ou Tempo. Quando os dois existem, '
       + N'compara a FOLGA RELATIVA ao proprio intervalo - 3.000 km e 4 meses nao sao '
       + N'comparaveis direto, mas 30% de um intervalo contra 33% do outro, sim. Nulo '
       + N'quando o item nunca foi registrado.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DS_CRITERIO', @d;
SET @d = N'Leitura pronta: Vencido, Vence em breve (menos de 1.000 km ou 1 mes), Em dia, ou '
       + N'Sem registro para o item que o plano preve e o historico nunca viu. '
       + N'"Sem registro" NAO E "vencido": pode ser item feito antes de o carro ser seu. '
       + N'Confira contra DT_ENTRADA_BASE.';
EXEC dbo.sp_documenta 'gold', 'vw_manutencao_prevista', 'DS_SITUACAO', @d;
GO

SELECT s.name + '.' + o.name AS objeto,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = o.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = o.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE o.name IN ('dim_revisao_programada', 'vw_manutencao_prevista')
ORDER BY 1;
GO
