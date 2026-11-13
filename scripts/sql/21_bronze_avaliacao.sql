/* =============================================================
   manzo-dados | 21 - Camada Bronze: avaliacao fisica
   -------------------------------------------------------------
   bronze.avaliacao_fisica

   Historico de bioimpedancia e medidas corporais, digitado a mao a
   partir dos laudos. Sao 31 avaliacoes entre 2008 e 2026 - a serie
   mais longa do projeto inteiro, com 18 anos de cobertura.

   A ORIGEM JA VEM DESEMPILHADA, o que e raro: uma linha por
   avaliacao e por medida (DATA, GRUPO, ITEM, MEDIDA, VALOR), em vez
   de uma coluna por medida. O grao natural ja e o do fato, entao a
   carga nao precisa desempilhar nada.

   O ARQUIVO E .xls DE VERDADE (Excel 97-2003, formato OLE2), e nao
   um .xlsx renomeado. Por isso o pandas exige xlrd, e nao openpyxl
   como as demais origens.

   DUAS ABAS, UMA SO INTERESSA. "Avaliacoes" e a origem; "Resultados"
   e uma tabela dinamica montada sobre ela, e esta desatualizada -
   soma duas datas na mesma coluna, o que faz o peso de 2019 aparecer
   como 152 kg em vez de 77,5. Ler a dinamica traria o erro junto.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.avaliacao_fisica') IS NULL
BEGIN
    CREATE TABLE bronze.avaliacao_fisica (
        id_medicao        int IDENTITY(1,1) NOT NULL,

        ds_data           varchar(50)  NULL,
        ds_grupo          varchar(100) NULL,
        ds_item           varchar(100) NULL,
        ds_medida         varchar(20)  NULL,
        ds_valor          varchar(50)  NULL,
        ds_classe         varchar(30)  NULL,

        hash_negocio      char(64)     NOT NULL,
        nm_arquivo_origem varchar(200) NOT NULL,
        nr_linha_arquivo  int          NULL,
        dt_carga          datetime2(3) NOT NULL
            CONSTRAINT DF_avaliacao_fisica_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_avaliacao_fisica PRIMARY KEY CLUSTERED (id_medicao),
        CONSTRAINT UQ_avaliacao_fisica_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_avaliacao_fisica_data ON bronze.avaliacao_fisica (ds_data);
    CREATE INDEX IX_avaliacao_fisica_item ON bronze.avaliacao_fisica (ds_item);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Avaliacoes fisicas e de bioimpedancia, uma linha por avaliacao e por '
       + N'medida. Digitado a mao a partir dos laudos, numa planilha .xls de verdade '
       + N'(Excel 97-2003) - por isso a carga usa xlrd e nao openpyxl. '
       + N'E A SERIE MAIS LONGA DO PROJETO: 31 avaliacoes entre 2008 e 2026. '
       + N'A origem ja vem desempilhada, com o grao que o fato precisa, entao a carga nao '
       + N'transforma o formato. Le apenas a aba Avaliacoes; a aba Resultados e uma tabela '
       + N'dinamica desatualizada que soma datas diferentes na mesma coluna.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'id_medicao', @d;

SET @d = N'Data da avaliacao, em formato ISO como texto. Todas as medidas de uma mesma '
       + N'avaliacao compartilham a data - e por ela que se sabe o que foi medido junto.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_data', @d;

SET @d = N'Agrupamento da medida, conforme o laudo: Analise da Composicao corporal, '
       + N'Analise Obesidade, Circunferencias Musculares, Medida Geral, Nivel gordura '
       + N'viceral e Pontuacao. E consistente na origem, e por isso e ele - e nao '
       + N'ds_classe - que a silver usa para classificar.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_grupo', @d;

SET @d = N'Nome da medida: Peso, IMC, % Gordura, Braco D, Cintura. Sao 30 itens distintos '
       + N'ao longo da serie, mas nenhuma avaliacao tem todos - ver a nota de eras na '
       + N'documentacao de silver.avaliacao_fisica.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_item', @d;

SET @d = N'Unidade da medida: Kg, cm, %, L, Imc, bpm, mmHg, Pontos. Verificado: cada item '
       + N'usa sempre a mesma unidade em toda a serie, sem excecao.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_medida', @d;

SET @d = N'Valor medido, como texto. Vazio quando a medida nao foi feita naquela '
       + N'avaliacao - "Busto" nunca foi preenchido em nenhuma das seis vezes em que '
       + N'apareceu na planilha.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_valor', @d;

SET @d = N'NAO USAR PARA CLASSIFICAR. Coluna da origem que parecia rotular o tipo de '
       + N'medida (PESO, MEDIDA, PRESSAO, PRINCIPAL, MACROS), mas e inconsistente: 8 dos '
       + N'30 itens aparecem com mais de um rotulo, e "% Gordura" ja foi marcado como '
       + N'PRINCIPAL, MEDIDA e PRESSAO em datas diferentes. O padrao muda por ano, o que '
       + N'sugere coluna arrastada com as linhas deslocadas. Guardada por fidelidade a '
       + N'origem e descartada na silver, que classifica por ds_grupo.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'ds_classe', @d;

SET @d = N'IDENTIDADE DA MEDICAO. SHA-256 de data + item. E o grao natural da origem: '
       + N'verificado que nenhum item se repete na mesma avaliacao, entao o par identifica '
       + N'sozinho. Com constraint UNIQUE: e o banco que impede a duplicacao.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'hash_negocio', @d;

SET @d = N'LINHAGEM: nome do arquivo de onde a medicao veio.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando a medicao entrou ou foi atualizada na base.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_fisica', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'avaliacao_fisica';
GO
