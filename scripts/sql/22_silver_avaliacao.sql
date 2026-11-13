/* =============================================================
   manzo-dados | 22 - Camada Silver: avaliacao fisica
   -------------------------------------------------------------
   silver.avaliacao_fisica

   Medidas tipadas, com o numero da avaliacao e a era de medicao.

   DUAS ERAS, E ISSO MUDA COMO O GRAFICO DEVE SER LIDO:

   - ate 2013 (6 avaliacoes): laudo completo, com circunferencias,
     pressao arterial e frequencia cardiaca. 24 itens por avaliacao.
   - 2018 em diante (25 avaliacoes): bioimpedancia, 11 itens.

   Apenas CINCO metricas atravessam as duas eras: Peso, IMC,
   % Gordura, Massa Gordura e Estatura. Sao as unicas que sustentam
   um grafico de 2008 a 2026 sem buraco. As demais tem serie parcial,
   e FL_SERIE_CONTINUA existe para que isso seja explicito no
   relatorio em vez de virar uma linha que some pela metade.

   ARMADILHA: "Massa Muscular" e "Massa Muscular/Ossea" NAO sao a
   mesma metrica. Nunca coexistem - a primeira aparece a partir de
   2018 na faixa de 30 a 33 kg, a segunda ate 2013 na faixa de 52 a
   57 kg, porque inclui massa ossea. Plotadas como uma serie unica,
   mostrariam uma queda de 57 para 32 kg que nunca aconteceu. Ficam
   como metricas distintas, de proposito.

   A COLUNA CLASSE DA ORIGEM NAO CHEGA AQUI. Era inconsistente - ver
   a documentacao de bronze.avaliacao_fisica.ds_classe.

   Pre-requisitos: 00, 01, 21
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.avaliacao_fisica') IS NULL
BEGIN
    CREATE TABLE silver.avaliacao_fisica (
        sk_medicao         int IDENTITY(1,1) NOT NULL,

        dt_avaliacao       date          NOT NULL,
        nr_avaliacao       int           NOT NULL,
        ds_era             varchar(30)   NOT NULL,

        ds_grupo           varchar(100)  NOT NULL,
        ds_metrica         varchar(100)  NOT NULL,
        ds_unidade         varchar(20)   NULL,
        vl_medida          decimal(10,2) NULL,
        fl_medido          bit           NOT NULL,
        fl_serie_continua  bit           NOT NULL,

        hash_negocio       char(64)      NOT NULL,
        dt_carga           datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_avaliacao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_avaliacao PRIMARY KEY CLUSTERED (sk_medicao),
        CONSTRAINT UQ_silver_avaliacao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_avaliacao_data    ON silver.avaliacao_fisica (dt_avaliacao);
    CREATE INDEX IX_silver_avaliacao_metrica ON silver.avaliacao_fisica (ds_metrica);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Avaliacoes fisicas tipadas, uma linha por avaliacao e por metrica. '
       + N'A serie vai de 2008 a 2026 mas NAO E HOMOGENEA: ate 2013 o laudo trazia '
       + N'circunferencias e pressao arterial; de 2018 em diante e bioimpedancia. So cinco '
       + N'metricas existem nas duas eras, e FL_SERIE_CONTINUA as identifica. '
       + N'Alimenta gold.fato_avaliacao_fisica.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', NULL, @d;

SET @d = N'Chave substituta da medicao. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'sk_medicao', @d;

SET @d = N'Data da avaliacao. As avaliacoes sao IRREGULARES: ha intervalos de um mes e '
       + N'intervalos de mais de tres anos, entre 2013 e 2018 e entre 2019 e 2022. '
       + N'Qualquer media por periodo precisa considerar isso.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'dt_avaliacao', @d;

SET @d = N'Numero sequencial da avaliacao, de 1 a 31 em ordem de data. Existe porque a '
       + N'pergunta natural e "como estou em relacao a avaliacao anterior", e o intervalo '
       + N'entre elas e irregular - comparar pela data exige saber qual foi a anterior, e '
       + N'esta coluna responde direto.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'nr_avaliacao', @d;

SET @d = N'Era de medicao: "Ate 2013" para o laudo completo com circunferencias e pressao, '
       + N'"2018 em diante" para a bioimpedancia. Separa o que e comparavel do que nao e.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'ds_era', @d;

SET @d = N'Agrupamento da metrica, herdado do laudo. Substitui a coluna CLASSE da origem, '
       + N'que era inconsistente.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'ds_grupo', @d;

SET @d = N'Nome da metrica medida. ATENCAO: "Massa Muscular" e "Massa Muscular/Ossea" sao '
       + N'metricas DIFERENTES e nunca coexistem - a segunda inclui massa ossea e fica na '
       + N'faixa de 52 a 57 kg contra 30 a 33 kg da primeira. Somar ou plotar as duas como '
       + N'uma serie mostra uma queda de 25 kg que nunca aconteceu.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'ds_metrica', @d;

SET @d = N'Unidade da metrica: Kg, cm, %, L, bpm, mmHg, Pontos, Imc. Cada metrica usa '
       + N'sempre a mesma. NUNCA agregue medidas de unidades diferentes na mesma conta.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'ds_unidade', @d;

SET @d = N'METRICA. Valor medido. Nulo quando a medida constava do laudo mas nao foi feita.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'vl_medida', @d;

SET @d = N'0 quando a linha existe no laudo mas ficou sem valor. Sao 12 casos, dos quais '
       + N'seis sao "Busto", que nunca foi medido nenhuma vez. Distingue "nao foi medido" '
       + N'de "nao consta do laudo", que sao coisas diferentes.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'fl_medido', @d;

SET @d = N'1 quando a metrica aparece nas DUAS eras e portanto sustenta um grafico de 2008 '
       + N'a 2026 sem buraco. Sao cinco: Peso, IMC, % Gordura, Massa Gordura e Estatura. '
       + N'Para o painel de evolucao de longo prazo, filtre por esta coluna - as demais '
       + N'metricas produzem linhas que comecam ou terminam no meio do grafico.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'fl_serie_continua', @d;

SET @d = N'Identidade da medicao, herdada da bronze: hash de data + metrica.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_fisica', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'avaliacao_fisica' ORDER BY 1;
GO
