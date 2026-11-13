/* =============================================================
   manzo-dados | 24 - Camada Bronze: manutencao do automovel
   -------------------------------------------------------------
   bronze.auto_manutencao + bronze.auto_intervalo_troca

   Historico de revisoes e manutencoes, digitado a mao a partir das
   notas da oficina. Sao 201 lancamentos entre 2016 e 2026,
   somando R$ 31.640, em DOIS veiculos.

   DUAS ABAS SAO ORIGEM, e nao uma:

   - "Avaliacoes" e o historico, ja desempilhado: uma linha por
     item comprado ou servico prestado.

   - "Tempo Troca" e uma TABELA DE REFERENCIA que diz de quantos
     em quantos km cada categoria deve ser trocada. E o que
     transforma o historico em previsao: sem ela sabe-se o que ja
     foi feito, com ela sabe-se o que esta vencendo.

   As outras tres abas nao entram. "Resultados" e "Ultima Troca"
   sao tabelas dinamicas derivadas, e "Quilometragem" e uma celula
   auxiliar delas - diz 155.000 km em 2025, numero que nao
   corresponde a nenhum dos dois carros hoje. A quilometragem
   atual e derivada do proprio historico, por veiculo.

   O arquivo e .xls de verdade (Excel 97-2003, OLE2), como a
   avaliacao fisica: exige xlrd, nao openpyxl.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.auto_manutencao') IS NULL
BEGIN
    CREATE TABLE bronze.auto_manutencao (
        id_manutencao     int IDENTITY(1,1) NOT NULL,

        ds_data           varchar(50)  NULL,
        ds_veiculo        varchar(60)  NULL,
        ds_km             varchar(30)  NULL,
        ds_natureza       varchar(30)  NULL,
        ds_tipo           varchar(30)  NULL,
        ds_item           varchar(200) NULL,
        ds_categoria      varchar(100) NULL,
        ds_quantidade     varchar(30)  NULL,
        ds_valor          varchar(30)  NULL,
        ds_local          varchar(120) NULL,
        ds_observacao     varchar(500) NULL,

        nr_ocorrencia     int          NOT NULL,
        hash_negocio      char(64)     NOT NULL,
        nm_arquivo_origem varchar(200) NOT NULL,
        nr_linha_arquivo  int          NULL,
        dt_carga          datetime2(3) NOT NULL
            CONSTRAINT DF_auto_manutencao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_auto_manutencao PRIMARY KEY CLUSTERED (id_manutencao),
        CONSTRAINT UQ_auto_manutencao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_auto_manutencao_data    ON bronze.auto_manutencao (ds_data);
    CREATE INDEX IX_auto_manutencao_veiculo ON bronze.auto_manutencao (ds_veiculo);
END
GO

IF OBJECT_ID('bronze.auto_intervalo_troca') IS NULL
BEGIN
    CREATE TABLE bronze.auto_intervalo_troca (
        id_intervalo      int IDENTITY(1,1) NOT NULL,

        ds_categoria      varchar(100) NOT NULL,
        ds_intervalo_km   varchar(30)  NULL,

        hash_negocio      char(64)     NOT NULL,
        nm_arquivo_origem varchar(200) NOT NULL,
        dt_carga          datetime2(3) NOT NULL
            CONSTRAINT DF_auto_intervalo_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_auto_intervalo_troca PRIMARY KEY CLUSTERED (id_intervalo),
        CONSTRAINT UQ_auto_intervalo_hash UNIQUE (hash_negocio)
    );
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Historico de revisoes e manutencoes do automovel, uma linha por item '
       + N'comprado ou servico prestado. Digitado a mao a partir das notas da oficina, numa '
       + N'planilha .xls de verdade (Excel 97-2003) - exige xlrd, nao openpyxl. '
       + N'CONTEM DOIS VEICULOS: o Sedan, de 2016 a novembro de 2025, e o SUV a partir '
       + N'dali. Cada um tem seu proprio hodometro, entao qualquer conta de quilometragem '
       + N'precisa ser feita por veiculo - as series nao se somam nem se continuam.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'id_manutencao', @d;
SET @d = N'Data da revisao ou manutencao, em formato ISO como texto. Todos os itens de uma '
       + N'mesma visita a oficina compartilham a data.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_data', @d;
SET @d = N'Veiculo: Sedan ou SUV. Coluna CARRO da origem. Divide a base em duas series '
       + N'independentes de hodometro.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_veiculo', @d;
SET @d = N'Quilometragem do veiculo no momento da manutencao. E o eixo que importa para '
       + N'manutencao preventiva - mais que a data, porque desgaste se mede em rodagem.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_km', @d;
SET @d = N'Coluna REVISAO da origem: "Revisão" quando foi manutencao programada, '
       + N'"Manutenção" quando foi conserto. Distingue o que se planeja do que quebra.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_natureza', @d;
SET @d = N'Coluna TIPO da origem: Produto (peca comprada) ou Serviço (mao de obra prestada).';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_tipo', @d;
SET @d = N'Descricao do item ou servico, escrita a mao. Sao 110 textos distintos, com '
       + N'variacao livre de grafia - por isso a analise se faz por ds_categoria.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_item', @d;
SET @d = N'CLASSIFICACAO da manutencao em 34 categorias: Óleo, Filtro, Freio, Pneu, Mão de '
       + N'Obra. E o eixo de analise e o que liga o historico a tabela de intervalos de '
       + N'troca. A origem traz "Mão de Obra" e "Mão de obra" como se fossem duas - a '
       + N'silver unifica.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_categoria', @d;
SET @d = N'Quantidade de unidades do item. Vazia em tres lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_quantidade', @d;
SET @d = N'METRICA. Valor pago em reais, ja pelo total do item e nao pelo unitario.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_valor', @d;
SET @d = N'Oficina ou loja onde foi feito. Sao 16 estabelecimentos ao longo de 10 anos.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_local', @d;
SET @d = N'Observacao livre, preenchida em 30 lancamentos. Usada para numero de nota e '
       + N'detalhe do servico.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'ds_observacao', @d;

SET @d = N'Numero da ocorrencia do mesmo item na mesma visita. NECESSARIO: dois filtros de '
       + N'ar podem ser trocados no mesmo dia por precos diferentes, e dois amortecedores '
       + N'do mesmo eixo entram como duas linhas. Sao dez lancamentos assim, todos reais - '
       + N'sem o contador, metade deles seria confundida com duplicata e descartada.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'nr_ocorrencia', @d;
SET @d = N'IDENTIDADE DO EVENTO. SHA-256 de data + veiculo + item + numero da ocorrencia. '
       + N'Com constraint UNIQUE: e o banco que impede a duplicacao.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'hash_negocio', @d;
SET @d = N'LINHAGEM: nome do arquivo de onde o lancamento veio.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o lancamento entrou ou foi atualizado na base.';
EXEC dbo.sp_documenta 'bronze', 'auto_manutencao', 'dt_carga', @d;

SET @d = N'BRONZE | De quantos em quantos quilometros cada categoria deve ser trocada. Vem '
       + N'da aba "Tempo Troca" da mesma planilha. E A TABELA QUE TRANSFORMA HISTORICO EM '
       + N'PREVISAO: sozinho, o historico diz o que ja foi feito; cruzado com ela, diz o '
       + N'que esta vencendo. Cobre 13 das 34 categorias, e isso nao e falha - as demais '
       + N'sao corretivas (bandeja, bucha, lampada, mao de obra) e nao se trocam por '
       + N'quilometragem.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', NULL, @d;

SET @d = N'Chave tecnica sequencial.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'id_intervalo', @d;
SET @d = N'Categoria de manutencao, no mesmo vocabulario de bronze.auto_manutencao.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'ds_categoria', @d;
SET @d = N'Intervalo recomendado entre trocas, em quilometros. Vai de 5.000 (oleo) a '
       + N'50.000 (amortecedor e correia).';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'ds_intervalo_km', @d;
SET @d = N'IDENTIDADE. SHA-256 da categoria.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'hash_negocio', @d;
SET @d = N'LINHAGEM: nome do arquivo de onde veio.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: quando o registro entrou ou foi atualizado.';
EXEC dbo.sp_documenta 'bronze', 'auto_intervalo_troca', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('auto_manutencao', 'auto_intervalo_troca') ORDER BY 1;
GO
