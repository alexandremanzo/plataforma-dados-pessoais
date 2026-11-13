/* =============================================================
   manzo-dados | 02 - Camada Bronze: investimentos XP
   -------------------------------------------------------------
   UMA tabela: bronze.xp_movimentacao

   Decisao de projeto: a bronze guarda cada evento financeiro UMA
   unica vez, nao uma copia de cada arquivo. O motivo e o processo
   de origem - o extrato e baixado varias vezes por mes sempre com
   a janela do mes anterior, entao os arquivos se sobrepoem quase
   totalmente (329 linhas de arquivo = apenas 170 eventos reais).
   Persistir tudo seria guardar 8 copias do mesmo dado.

   A fidelidade ao bruto nao se perde: os arquivos originais
   continuam no Dropbox e a carga e reexecutavel a partir deles.

   A unicidade e garantida pelo banco (UQ_xp_movimentacao_hash),
   nao pelo script de carga: se a logica do Python falhar, o banco
   recusa a duplicata em vez de aceitar silenciosamente.

   A planilha mestre dados-xp.xlsx e a semente do historico: ela
   contem movimentacoes anteriores aos arquivos de extrato que
   ainda existem, e por isso e a base da tabela.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   Remove o desenho anterior (duas tabelas separadas por origem).
   Nenhum dado se perde: tudo e recarregavel dos arquivos.
   ------------------------------------------------------------- */
DROP TABLE IF EXISTS bronze.xp_extrato;
DROP TABLE IF EXISTS bronze.xp_movto_mestre;
GO


IF OBJECT_ID('bronze.xp_movimentacao') IS NULL
BEGIN
    CREATE TABLE bronze.xp_movimentacao (
        id_movimentacao       int IDENTITY(1,1) NOT NULL,

        -- Dados como vieram da origem, sem conversao de tipo
        ds_movimentacao       varchar(50)       NULL,
        ds_liquidacao         varchar(50)       NULL,
        ds_lancamento         varchar(1000)     NULL,
        ds_valor              varchar(50)       NULL,
        ds_saldo              varchar(50)       NULL,

        -- Classificacao que ja vinha preenchida na planilha mestre
        ds_categoria_origem   varchar(100)      NULL,
        ds_rendimento_origem  varchar(10)       NULL,
        ds_ativo_origem       varchar(200)      NULL,

        -- Identidade e linhagem
        hash_negocio          char(64)          NOT NULL,
        nm_arquivo_origem     varchar(260)      NOT NULL,
        nr_linha_arquivo      int               NULL,
        dt_carga              datetime2(3)      NOT NULL
            CONSTRAINT DF_xp_movimentacao_dt_carga DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_xp_movimentacao PRIMARY KEY CLUSTERED (id_movimentacao),
        CONSTRAINT UQ_xp_movimentacao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_xp_movimentacao_data ON bronze.xp_movimentacao (ds_movimentacao);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Movimentacoes financeiras da conta XP, uma linha por evento real. '
       + N'Alimentada por duas origens: a planilha mestre dados-xp.xlsx (semente do '
       + N'historico desde 2021) e os arquivos de extrato baixados no app da corretora '
       + N'(incrementos). Como o extrato e baixado varias vezes por mes sempre cobrindo '
       + N'o mes anterior, os arquivos se sobrepoem muito; a carga insere apenas eventos '
       + N'cujo hash_negocio ainda nao existe. A unicidade e imposta pelo banco. '
       + N'Nao ha conversao de tipo aqui - isso e trabalho da silver.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', NULL, @d;

SET @d = N'Chave tecnica sequencial. Sem significado de negocio; para relacionar dados '
       + N'entre camadas use hash_negocio.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'id_movimentacao', @d;

SET @d = N'Data em que a movimentacao ocorreu (fato economico), em formato ISO como texto. '
       + N'Convertida para date na silver.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_movimentacao', @d;

SET @d = N'Data em que o dinheiro entrou ou saiu da conta, em formato ISO como texto. '
       + N'Pode ser posterior a movimentacao (ex: bolsa liquida em D+2). Use esta data '
       + N'para fluxo de caixa e a de movimentacao para resultado.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_liquidacao', @d;

SET @d = N'Descricao textual do lancamento gerada pela XP, sem padronizacao. E o campo '
       + N'do qual a silver deriva a categoria e o ativo. '
       + N'Ex: "DIVIDENDOS DE CLIENTES ALOS3 S/".';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_lancamento', @d;

SET @d = N'Valor da transacao em reais, como texto com 2 casas. Positivo indica entrada '
       + N'(dividendo, resgate, rendimento) e negativo indica saida (compra, taxa, imposto).';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_valor', @d;

SET @d = N'Saldo da conta apos o lancamento, como texto com 2 casas. Alem do valor '
       + N'informativo, e o campo que distingue duas transacoes identicas no mesmo dia: '
       + N'transacoes reais movem o saldo, linhas repetidas mantem o mesmo saldo. '
       + N'Por isso participa do hash_negocio.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_saldo', @d;

SET @d = N'Categoria que ja vinha preenchida manualmente na planilha mestre. Preenchida '
       + N'apenas para eventos vindos dela; nula para eventos novos vindos do extrato. '
       + N'Serve como referencia historica e como gabarito para conferir as regras '
       + N'automaticas - a silver recalcula a categoria para toda a serie.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_categoria_origem', @d;

SET @d = N'Marcacao manual de rendimento ("S") herdada da planilha mestre. Nula para '
       + N'eventos vindos do extrato.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_rendimento_origem', @d;

SET @d = N'Ativo informado manualmente na planilha mestre (ticker, CDB, fundo, Tesouro). '
       + N'Nulo para eventos vindos do extrato.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'ds_ativo_origem', @d;

SET @d = N'IDENTIDADE DO EVENTO. SHA-256 da chave de negocio normalizada: data de '
       + N'movimentacao + data de liquidacao + descricao (sem acento, maiuscula, espacos '
       + N'colapsados) + valor + saldo. Duas linhas com o mesmo hash sao o mesmo evento '
       + N'financeiro, venham do arquivo que vierem. Tem constraint UNIQUE: e o banco que '
       + N'impede a duplicacao, nao o script de carga.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: nome do arquivo em que o evento foi visto pela PRIMEIRA vez. Como o '
       + N'mesmo lancamento aparece em varios extratos, este campo registra a origem que '
       + N'de fato trouxe o dado para a base, nao todas em que ele aparece.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'nm_arquivo_origem', @d;

SET @d = N'LINHAGEM: posicao da linha dentro do arquivo de origem, a partir de 1 apos o '
       + N'cabecalho. Permite auditar um registro abrindo o arquivo original.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'nr_linha_arquivo', @d;

SET @d = N'LINHAGEM: data e hora em que o evento entrou na base. Como a carga so insere '
       + N'novidades, este campo mostra quando cada movimentacao foi descoberta.';
EXEC dbo.sp_documenta 'bronze', 'xp_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'bronze' ORDER BY 1;
GO
