/* =============================================================
   manzo-dados | 06 - Camada Bronze: conta corrente Itau
   -------------------------------------------------------------
   bronze.itau_movimentacao

   Mesma estrutura logica do XP - uma tabela, cada evento uma vez,
   semeada pela planilha mestre e incrementada pelos extratos - mas
   com tres diferencas que o Itau impoe:

   1. NAO HA SALDO NO EXTRATO. O extrato do Itau traz apenas data,
      descricao e valor. No XP, o saldo corrente distinguia duas
      transacoes iguais no mesmo dia de uma linha lancada duas vezes.
      Sem ele, a chave de negocio precisa de NR_OCORRENCIA: a
      n-esima vez que aquela combinacao aparece naquele dia.

   2. AS DUPLICATAS AQUI SAO REAIS. Diferente do XP, onde 20 linhas
      com saldo identico provavam erro de digitacao, as 361 repeticoes
      do Itau estao espalhadas por 32 datas ao longo de 10 anos, em
      grupos de 2 ou 3. E o padrao de compra repetida - dois cafes de
      R$ 7 no mesmo dia - e nao de bloco colado em duplicidade.
      Todas sao preservadas.

   3. A CLASSIFICACAO VEM DA ORIGEM, NAO DE REGRA. As descricoes de
      banco ("LOJA-EXEMPLO*CAT-", "TBI 0000.00000-0/5") nao permitem
      deduzir categoria com confianca: dos prefixos mais frequentes
      sem categoria, poucos tem referencia no restante da base, e
      algumas se contradizem. Por decisao de projeto nada e inferido:
      o que a planilha nao classificou fica como "A classificar".

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.itau_movimentacao') IS NULL
BEGIN
    CREATE TABLE bronze.itau_movimentacao (
        id_movimentacao       int IDENTITY(1,1) NOT NULL,

        -- Dados como vieram da origem, sem conversao de tipo
        ds_data               varchar(50)       NULL,
        ds_descricao          varchar(1000)     NULL,
        ds_valor              varchar(50)       NULL,
        ds_valor_tratado      varchar(50)       NULL,
        ds_tipo_movimentacao  varchar(50)       NULL,

        -- Classificacao preenchida manualmente na planilha
        ds_area               varchar(100)      NULL,
        ds_categoria          varchar(100)      NULL,
        ds_grupo              varchar(100)      NULL,
        ds_pessoa_pagar       varchar(100)      NULL,
        ds_pessoa_receber     varchar(100)      NULL,
        ds_forma_pgto         varchar(50)       NULL,
        ds_descricao_pgto     varchar(200)      NULL,
        ds_data_pgto          varchar(50)       NULL,
        ds_status_pgto        varchar(50)       NULL,
        ds_cidade             varchar(100)      NULL,
        ds_uf                 varchar(20)       NULL,
        ds_pais               varchar(60)       NULL,
        ds_obs                varchar(1000)     NULL,
        ds_projeto            varchar(100)      NULL,
        ds_tag                varchar(100)      NULL,

        -- Identidade e linhagem
        nr_ocorrencia         int               NOT NULL,
        hash_negocio          char(64)          NOT NULL,
        nm_arquivo_origem     varchar(260)      NOT NULL,
        nm_aba_origem         varchar(120)      NOT NULL,
        nr_linha_arquivo      int               NULL,
        dt_carga              datetime2(3)      NOT NULL
            CONSTRAINT DF_itau_movimentacao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_itau_movimentacao PRIMARY KEY CLUSTERED (id_movimentacao),
        CONSTRAINT UQ_itau_movimentacao_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_itau_movimentacao_data ON bronze.itau_movimentacao (ds_data);
    CREATE INDEX IX_itau_movimentacao_cat  ON bronze.itau_movimentacao (ds_categoria);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Movimentacoes da conta corrente do Itau, uma linha por evento real, '
       + N'desde 2016. Alimentada pela aba "cad-conta" de dados-itau.xlsx (semente do '
       + N'historico, ja com classificacao manual) e pela aba de extrato baixada do banco '
       + N'(incremento, apenas data/descricao/valor). A carga insere somente eventos cujo '
       + N'hash_negocio ainda nao existe. Linhas em branco da planilha - resquicio de '
       + N'formula arrastada, sem data nem valor - sao descartadas na carga.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'id_movimentacao', @d;

SET @d = N'Data do lancamento em formato ISO como texto. Convertida para date na silver.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_data', @d;

SET @d = N'Descricao do lancamento como o Itau a gera, sem padronizacao. Ex: '
       + N'"LOJA-EXEMPLO*CAT-", "PIX TRANSF FULANO14/05", "TBI 0000.00000-0/500". '
       + N'Muitas embutem data e nome parcial do estabelecimento, o que as torna quase '
       + N'unicas e dificulta deduzir categoria automaticamente.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_descricao', @d;

SET @d = N'Valor do lancamento em reais, como texto. Positivo = entrada na conta, '
       + N'negativo = saida.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_valor', @d;

SET @d = N'Valor apos ajuste manual feito na planilha. Costuma repetir ds_valor; difere '
       + N'quando houve correcao ou rateio. Preenchido tambem em linhas onde ds_valor '
       + N'esta vazio.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_valor_tratado', @d;

SET @d = N'Natureza informada na planilha: Receita, Despesa ou "Saldo Conta". ATENCAO: '
       + N'"Saldo Conta" NAO e transacao - sao 141 marcadores de saldo final ou parcial '
       + N'anotados no extrato. A silver os separa e a gold os exclui, senao seriam '
       + N'somados como se fossem movimentacao.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'CLASSIFICACAO MANUAL, nivel 1 (mais amplo): TRANSFERENCIA, ESTILO DE VIDA, '
       + N'RENDA, GASTOS ESSENCIAIS, TAXA, EMPRESTIMO, VENDA, INVESTIMENTO e outros. '
       + N'Vazio em cerca de 40% da serie, quase toda anterior a 2024.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_area', @d;

SET @d = N'CLASSIFICACAO MANUAL, nivel 2: TRANSFERENCIA, RENDIMENTO, TRABALHO, CASA, '
       + N'TRANSPORTE, ALIMENTACAO, EDUCACAO e outros - 38 valores distintos. E o nivel '
       + N'usado para analise de gastos. A cobertura salta de cerca de 55% ate 2023 para '
       + N'99% em 2024 e 2025.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO MANUAL, nivel 3 (mais fino): 155 valores como "Movimentacao entre '
       + N'contas", "Combustivel", "Escola Nina", "Almoco". E o nivel de detalhe para '
       + N'acompanhar metas por assunto.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_grupo', @d;

SET @d = N'Quem pagou o lancamento, na anotacao manual da planilha.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_pessoa_pagar', @d;

SET @d = N'Quem recebeu o lancamento, na anotacao manual da planilha.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_pessoa_receber', @d;

SET @d = N'Forma de pagamento anotada na planilha (T = transferencia, entre outras).';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_forma_pgto', @d;

SET @d = N'Descricao da forma de pagamento, complementando ds_forma_pgto.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_descricao_pgto', @d;

SET @d = N'Data do pagamento efetivo, quando diferente da data do lancamento.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_data_pgto', @d;

SET @d = N'Status do pagamento. Coluna existe na planilha mas nunca foi preenchida - '
       + N'mantida por fidelidade a origem.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_status_pgto', @d;

SET @d = N'Cidade onde ocorreu o gasto. Preenchida em cerca de 19% dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_cidade', @d;

SET @d = N'Unidade federativa do gasto. Preenchida em cerca de 19% dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_uf', @d;

SET @d = N'Pais do gasto. Preenchido em cerca de 19% dos lancamentos, util para separar '
       + N'gastos de viagem.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_pais', @d;

SET @d = N'Observacao livre anotada na planilha. Preenchida em cerca de 6% dos casos.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_obs', @d;

SET @d = N'Projeto ao qual o gasto se vincula. Praticamente nao utilizado (8 lancamentos).';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_projeto', @d;

SET @d = N'Marcador livre para agrupar lancamentos fora da hierarquia de categoria.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_tag', @d;

SET @d = N'Numero da ocorrencia da combinacao data + descricao + valor naquele dia. '
       + N'Vale 1 na primeira vez, 2 na segunda e assim por diante. EXISTE PORQUE O '
       + N'EXTRATO DO ITAU NAO TRAZ SALDO: sem ele, duas compras identicas no mesmo dia '
       + N'seriam indistinguiveis e uma das duas se perderia na deduplicacao. Com o '
       + N'contador, se o extrato traz duas e a base ja tem duas, elas casam; se a base '
       + N'tem uma, a segunda entra como nova.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'nr_ocorrencia', @d;

SET @d = N'IDENTIDADE DO EVENTO. SHA-256 de data + descricao normalizada + valor + '
       + N'numero da ocorrencia. Tem constraint UNIQUE: e o banco que impede duplicacao, '
       + N'nao o script de carga.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: arquivo em que o evento foi visto pela primeira vez.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'nm_arquivo_origem', @d;

SET @d = N'LINHAGEM: aba de origem. Registrada porque a aba de extrato muda de nome a cada '
       + N'download - traz a data no titulo, como "Extrato Conta Corrente-12072026" - e '
       + N'guardar o nome permite saber de qual extrato o dado veio.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'nm_aba_origem', @d;

SET @d = N'LINHAGEM: posicao da linha na aba de origem, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'nr_linha_arquivo', @d;

SET @d = N'LINHAGEM: data e hora em que o evento entrou na base.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'bronze' ORDER BY 1;
GO
