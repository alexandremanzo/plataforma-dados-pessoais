/* =============================================================
   manzo-dados | 40 - Leitura automatica dos exames InBody
   -------------------------------------------------------------
   bronze.avaliacao_inbody
   silver.avaliacao_inbody

   A planilha de avaliacao fisica continua existindo e continua
   sendo origem. Estas tabelas nao a substituem: ELAS SE JUNTAM A
   ELA. O arquivo do exame traz cerca de 40 campos, contra os 11
   que cabem no preenchimento manual; onde o OCR nao alcanca, a
   planilha preenche a lacuna.

   POR QUE O GRAO DA BRONZE E O CAMPO, E NAO O EXAME. Um exame com
   um campo ilegivel nao pode ser um exame perdido. Com uma linha
   por campo, reler um recorte ajustado troca aquele campo e deixa
   os outros trinta e nove intactos - e da para auditar de qual
   arquivo e de qual regiao cada numero veio.

   AS CHAVES COMECADAS COM SUBLINHADO nao sao medidas: guardam a
   versao do leiaute e o resultado das conferencias. Ficam aqui
   junto com o resto porque foram produzidas pela mesma leitura, e
   separa-las criaria duas tabelas que so fazem sentido juntas.

   Pre-requisitos: 00, 01
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Bronze - uma linha por campo lido
   ------------------------------------------------------------- */

IF OBJECT_ID('bronze.avaliacao_inbody') IS NULL
BEGIN
    CREATE TABLE bronze.avaliacao_inbody (
        id                int IDENTITY(1,1) NOT NULL,

        nm_arquivo        varchar(200) NOT NULL,
        ds_template       varchar(40)  NULL,
        ds_data_exame     varchar(20)  NULL,
        ds_campo          varchar(60)  NOT NULL,
        ds_valor          varchar(200) NULL,

        hash_negocio      char(64)     NOT NULL,
        dt_carga          datetime2(3) NOT NULL
            CONSTRAINT DF_bronze_inbody_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_bronze_avaliacao_inbody PRIMARY KEY (id),
        CONSTRAINT UQ_bronze_avaliacao_inbody_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_bronze_inbody_arquivo ON bronze.avaliacao_inbody (nm_arquivo);
    CREATE INDEX IX_bronze_inbody_campo   ON bronze.avaliacao_inbody (ds_campo);
END
GO


/* -------------------------------------------------------------
   2. Silver - uma linha por exame, metrica e segmento
   -------------------------------------------------------------
   O grao ja e o do fato de destino, que e "uma linha por avaliacao
   e por metrica" desde 2008. O segmento entra como terceira parte
   da chave porque a analise segmentar mede o mesmo indicador em
   cinco lugares do corpo - e e ela que responde onde falta musculo.
   ------------------------------------------------------------- */

IF OBJECT_ID('silver.avaliacao_inbody') IS NULL
BEGIN
    CREATE TABLE silver.avaliacao_inbody (
        id                 int IDENTITY(1,1) NOT NULL,

        dt_exame           date         NOT NULL,
        nm_metrica         varchar(100) NOT NULL,
        nm_segmento        varchar(40)  NOT NULL,

        vl_medida          decimal(10,2) NULL,
        vl_referencia_min  decimal(10,2) NULL,
        vl_referencia_max  decimal(10,2) NULL,
        ds_avaliacao       varchar(20)   NULL,

        ds_template        varchar(40)  NULL,
        nm_arquivo         varchar(200) NULL,
        hash_negocio       char(64)     NOT NULL,
        dt_carga           datetime2(3) NOT NULL
            CONSTRAINT DF_silver_inbody_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_avaliacao_inbody PRIMARY KEY (id),
        CONSTRAINT UQ_silver_avaliacao_inbody_hash UNIQUE (hash_negocio),
        CONSTRAINT CK_silver_inbody_avaliacao
            CHECK (ds_avaliacao IS NULL
                   OR ds_avaliacao IN ('Abaixo', 'Normal', 'Acima'))
    );

    CREATE INDEX IX_silver_inbody_data ON silver.avaliacao_inbody (dt_exame);
END
GO


/* -------------------------------------------------------------
   3. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Leitura automatica dos exames de bioimpedancia InBody, UMA LINHA POR '
       + N'CAMPO LIDO. O exame chega como imagem - render do software LookinBody, sempre '
       + N'1640x2310 - e o texto e extraido por OCR recortando regiao a regiao. '
       + N'O grao e o campo, e nao o exame, porque um campo ilegivel nao pode custar o '
       + N'exame inteiro: relendo com o recorte ajustado, troca-se aquele campo e os '
       + N'demais ficam intactos. '
       + N'NAO SUBSTITUI A PLANILHA de avaliacao fisica: as duas origens se juntam na gold, '
       + N'com o arquivo na frente e a planilha preenchendo o que o OCR nao alcancou.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', NULL, @d;

SET @d = N'Chave tecnica da linha na bronze.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'id', @d;
SET @d = N'LINHAGEM: arquivo de onde o campo foi lido. E o unico caminho de volta ate a '
       + N'imagem quando um valor parecer estranho.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'nm_arquivo', @d;
SET @d = N'Versao do leiaute, lida do rodape do proprio exame: F3/230-B-140219 nos exames '
       + N'ate 2019 e F3/230-C-210120 nos de 2024 em diante. E ela que escolhe o mapa de '
       + N'recortes - as duas versoes nao aceitam o mesmo. Versao desconhecida derruba a '
       + N'carga, em vez de ler coordenadas erradas em silencio.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'ds_template', @d;
SET @d = N'Data do exame como texto, para agrupar os campos de um mesmo arquivo sem '
       + N'depender de conversao.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'ds_data_exame', @d;
SET @d = N'Nome tecnico do campo lido: vl_peso, magra_3_kg, impedancia_20khz_0. '
       + N'AS CHAVES COMECADAS COM SUBLINHADO NAO SAO MEDIDAS: _problema guarda cada '
       + N'conferencia que falhou naquele exame, e existe para o defeito ficar registrado '
       + N'onde da para consultar, e nao so num log de terminal.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'ds_campo', @d;
SET @d = N'Valor como o OCR devolveu, ainda em texto. O separador decimal alterna entre '
       + N'virgula e ponto no mesmo exame, e as vezes some - a tipagem e a conferencia '
       + N'acontecem na silver.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'ds_valor', @d;
SET @d = N'IDENTIDADE DO CAMPO. SHA-256 de arquivo + campo. Com constraint UNIQUE, e o que '
       + N'torna a releitura de um exame idempotente.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o campo foi lido.';
EXEC dbo.sp_documenta 'bronze', 'avaliacao_inbody', 'dt_carga', @d;

SET @d = N'SILVER | Os exames InBody tipados, uma linha por exame, metrica e SEGMENTO. '
       + N'O segmento entra na chave porque a analise segmentar mede o mesmo indicador em '
       + N'cinco lugares do corpo, e e ela que responde onde falta musculo - o dado que o '
       + N'preenchimento manual nunca capturou. '
       + N'Valor implausivel nao chega aqui: e descartado na leitura, com o motivo '
       + N'registrado. Buraco visivel e melhor que numero plausivel e errado.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', NULL, @d;

SET @d = N'Chave tecnica da linha na silver.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'id', @d;
SET @d = N'Data do exame, lida do cabecalho. ATENCAO AO FORMATO: os exames ate 2019 '
       + N'imprimem ano na frente (2018.06.05) e os novos, dia na frente (28.08.2026).';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'dt_exame', @d;
SET @d = N'Nome da metrica, na mesma grafia de gold.dim_metrica_corporal - e o que permite '
       + N'as duas origens caírem na mesma linha do fato.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'nm_metrica', @d;
SET @d = N'Parte do corpo: Braço esquerdo, Braço direito, Tronco, Perna esquerda, Perna '
       + N'direita. Vale "Corpo inteiro" nas metricas que nao sao segmentares - e a '
       + N'resposta certa para peso ou IMC, e nao um dado faltando.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'nm_segmento', @d;
SET @d = N'Valor medido, na unidade da metrica.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'vl_medida', @d;
SET @d = N'Limite inferior da faixa de referencia que o exame imprime ao lado do valor. '
       + N'MUDA A CADA EXAME porque depende de idade e altura, entao e dado do fato e nao '
       + N'constante da dimensao. Nulo quando o OCR nao leu a faixa com seguranca.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'vl_referencia_min', @d;
SET @d = N'Limite superior da faixa de referencia do exame.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'vl_referencia_max', @d;
SET @d = N'Como a propria maquina classifica o valor: Abaixo, Normal ou Acima. So existe '
       + N'nas metricas segmentares.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'ds_avaliacao', @d;
SET @d = N'Versao do leiaute de onde a medida veio.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'ds_template', @d;
SET @d = N'LINHAGEM: arquivo de origem.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'nm_arquivo', @d;
SET @d = N'IDENTIDADE DA MEDIDA. SHA-256 de data + metrica + segmento.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando a medida foi carregada na silver.';
EXEC dbo.sp_documenta 'silver', 'avaliacao_inbody', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'avaliacao_inbody' ORDER BY 1;
GO
