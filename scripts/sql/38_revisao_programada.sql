/* =============================================================
   manzo-dados | 38 - Plano de revisao do fabricante
   -------------------------------------------------------------
   bronze.auto_revisao_programada
   silver.auto_revisao_programada
   silver.de_para_item_revisao

   O QUE ESTA BASE RESOLVE. A previsao de manutencao ate agora so
   sabia quilometragem, e a quilometragem so entra na base quando o
   carro vai a oficina. Por isso, logo depois de uma visita, TUDO
   aparecia como "Em dia" - o alerta nunca alertava. O plano do
   fabricante traz o intervalo EM MESES ao lado do intervalo em km,
   e o tempo corre sozinho, sem depender de ninguem anotar nada.

   NAO E EVENTO, E REGRA. As demais bronzes guardam o que aconteceu;
   esta guarda o que DEVE acontecer. Sao 21 itens de um documento de
   fabrica, nao 21 idas a oficina.

   SO A PRIMEIRA ABA ENTRA. A segunda, "Matriz de Revisoes", e a
   mesma regra reapresentada por marco de 10k a 100k: o que ela
   acrescenta - se num dado marco o item e inspecao ou troca - ja sai
   do intervalo mais a acao. Carrega-la custaria DDL, documentacao,
   script e tarefa na DAG para dado derivado. Mesmo criterio que faz
   carga_bronze_itau.py ler so a aba cad-conta.

   Pre-requisitos: 00, 01
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Bronze - copia fiel da aba, tudo texto
   ------------------------------------------------------------- */

IF OBJECT_ID('bronze.auto_revisao_programada') IS NULL
BEGIN
    CREATE TABLE bronze.auto_revisao_programada (
        id                  int IDENTITY(1,1) NOT NULL,

        ds_modelo           varchar(120)  NULL,
        ds_item             varchar(200)  NULL,
        ds_sistema          varchar(120)  NULL,
        ds_intervalo_km     varchar(60)   NULL,
        ds_intervalo_tempo  varchar(60)   NULL,
        ds_acao             varchar(60)   NULL,
        ds_especificacao    varchar(500)  NULL,

        hash_negocio        char(64)      NOT NULL,
        nm_arquivo_origem   varchar(200)  NULL,
        nm_aba_origem       varchar(120)  NULL,
        nr_linha_arquivo    int           NULL,
        dt_carga            datetime2(3)  NOT NULL
            CONSTRAINT DF_bronze_revisao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_bronze_auto_revisao PRIMARY KEY (id),
        CONSTRAINT UQ_bronze_auto_revisao_hash UNIQUE (hash_negocio)
    );
END
GO


/* -------------------------------------------------------------
   2. Silver - tipada
   ------------------------------------------------------------- */

IF OBJECT_ID('silver.auto_revisao_programada') IS NULL
BEGIN
    CREATE TABLE silver.auto_revisao_programada (
        id                  int IDENTITY(1,1) NOT NULL,

        nm_modelo           varchar(120)  NOT NULL,
        nm_item             varchar(200)  NOT NULL,
        nm_sistema          varchar(120)  NULL,
        nr_intervalo_km     int           NULL,
        nr_intervalo_meses  int           NULL,
        ds_acao             varchar(30)   NULL,
        ds_especificacao    varchar(500)  NULL,

        hash_negocio        char(64)      NOT NULL,
        dt_carga            datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_revisao_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_auto_revisao PRIMARY KEY (id),
        CONSTRAINT UQ_silver_auto_revisao_hash UNIQUE (hash_negocio),
        CONSTRAINT CK_silver_auto_revisao_acao
            CHECK (ds_acao IN ('Troca', 'Inspeção', 'Serviço'))
    );
END
GO


/* -------------------------------------------------------------
   3. De-para: item do fabricante -> o texto que voce escreve
   -------------------------------------------------------------
   POR QUE ELE PRECISA EXISTIR. O fabricante diz "Filtro de Ar do
   Motor"; a nota da oficina, transcrita por voce, diz "Filtro de
   ar". Sua CATEGORIA nao serve de ponte porque e grossa demais -
   "Filtro" cobre quatro itens do plano com intervalos de 10k, 20k,
   20k e 10k, e "Fluido" cobre cinco, de 20k a 80k. Usar a categoria
   obrigaria a adotar sempre o menor intervalo, cobrando o filtro de
   ar 10 mil km antes da hora, todo ciclo.

   O DS_ITEM, sim, serve: ele ja distingue "Filtro de ar", "Filtro de
   oleo" e "Filtro de ar condicionado".

   VARIOS PADROES POR ITEM, de proposito. O texto e livre e tem
   variacao real: "Flitro de óleo" com typo, "FLUIDO DIFERENCIAL
   TRASEIRO" em caixa alta, "Filtro de óleo oc1226" com codigo de
   peca no meio. Uma linha por grafia resolve sem tocar em codigo.
   ------------------------------------------------------------- */

IF OBJECT_ID('silver.de_para_item_revisao') IS NULL
BEGIN
    CREATE TABLE silver.de_para_item_revisao (
        nm_item_plano   varchar(200) NOT NULL,
        ds_padrao_item  varchar(200) NOT NULL,
        nr_lancamentos  int          NULL,
        dt_carga        datetime2(3) NOT NULL
            CONSTRAINT DF_de_para_item_revisao_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_de_para_item_revisao
            PRIMARY KEY (nm_item_plano, ds_padrao_item)
    );
END
GO

/* Semente do de-para.
   -------------------------------------------------------------
   So insere o que nao existe: o mapeamento e REGRA DE NEGOCIO e
   vive aqui como dado. Rodar este arquivo de novo nao desfaz um
   ajuste seu, e acrescentar uma grafia nova e um INSERT, nao uma
   alteracao de codigo.

   O que nao esta aqui e porque a evidencia nao sustenta. "Polia
   auxiliar" pode ser o tensor da correia Poly-V, mas quem sabe e
   quem levou o carro. Item sem mapeamento NAO SOME: ele e
   exatamente o que a view mostra como "Sem registro". */

;WITH semente(nm_item_plano, ds_padrao_item) AS (
    SELECT * FROM (VALUES
        (N'Óleo do Motor',                    N'oleo de motor'),
        (N'Óleo do Motor',                    N'oleo motor'),
        (N'Filtro de Óleo do Motor',          N'filtro de oleo'),
        (N'Filtro de Óleo do Motor',          N'filtro oleo motor'),
        (N'Filtro de Óleo do Motor',          N'flitro de oleo'),
        (N'Filtro de Ar do Motor',            N'filtro de ar'),
        (N'Filtro de Combustível (Injeção)',  N'filtro de combustivel'),
        (N'Filtro de Ar-Condicionado (Cabine)', N'filtro de ar condicionado'),
        (N'Filtro de Ar-Condicionado (Cabine)', N'filtro de cabine'),
        (N'Velas de Ignição (Iridium)',       N'vela'),
        (N'Fluido de Freio (DOT 4)',          N'fluido freio'),
        (N'Fluido de Freio (DOT 4)',          N'fluido de freio'),
        (N'Pastilhas de Freio (Diant/Tras)',  N'pastilha'),
        (N'Discos de Freio',                  N'disco de freio'),
        (N'Fluido da Transmissão CVT',        N'cambio automatico'),
        (N'Fluido da Caixa de Transferência (4x4)', N'caixa de transferencia'),
        (N'Fluido da Caixa de Transferência (4x4)', N'caixa transferencia'),
        (N'Fluido do Diferencial Traseiro (4x4)',   N'diferencial traseiro'),
        (N'Líquido de Arrefecimento (Aditivo)',     N'arrefecimento'),
        (N'Líquido de Arrefecimento (Aditivo)',     N'aditivo'),
        (N'Correia de Acessórios (Poly-V)',   N'correia'),
        (N'Fluido de Direção Hidráulica',     N'fluido atf'),
        (N'Amortecedores e Batentes',         N'amortecedor'),
        (N'Amortecedores e Batentes',         N'batente'),
        (N'Amortecedores e Batentes',         N'coxim'),
        (N'Bieletas e Buchas da Barra Estabilizadora', N'bieleta'),
        (N'Bieletas e Buchas da Barra Estabilizadora', N'bucha'),
        (N'Alinhamento e Balanceamento',      N'alinhamento'),
        (N'Alinhamento e Balanceamento',      N'balanceamento'),
        (N'Bateria (12V)',                    N'bateria')
    ) AS v(a, b)
)
INSERT INTO silver.de_para_item_revisao (nm_item_plano, ds_padrao_item)
SELECT s.nm_item_plano, s.ds_padrao_item
FROM semente s
WHERE NOT EXISTS (
    SELECT 1 FROM silver.de_para_item_revisao d
    WHERE d.nm_item_plano = s.nm_item_plano
      AND d.ds_padrao_item = s.ds_padrao_item
);
GO


/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Plano de manutencao preventiva do fabricante, copia fiel da aba '
       + N'"Plano de Manutencao SUV 2017". NAO E EVENTO, E REGRA: as demais bronzes '
       + N'guardam o que aconteceu, esta guarda o que DEVE acontecer. '
       + N'A segunda aba do arquivo, "Matriz de Revisoes", nao entra - e a mesma regra '
       + N'reapresentada por marco de 10k a 100k, e o que ela acrescenta ja sai do '
       + N'intervalo mais a acao.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', NULL, @d;

SET @d = N'Chave tecnica da linha na bronze.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'id', @d;
SET @d = N'Modelo a que o plano se refere, lido do titulo da aba: "SUV 2017". E ele que '
       + N'liga a regra ao veiculo certo - o plano do SUV nao vale para o Sedan.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_modelo', @d;
SET @d = N'Item ou componente, como o fabricante o nomeia: "Filtro de Ar do Motor", '
       + N'"Fluido da Transmissao CVT".';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_item', @d;
SET @d = N'Sistema do veiculo a que o item pertence: Motor, Freios, Suspensao, Cambio CVT.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_sistema', @d;
SET @d = N'Intervalo em quilometros, como texto na origem.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_intervalo_km', @d;
SET @d = N'Intervalo de tempo como texto na origem, no formato "12 meses". E A COLUNA QUE '
       + N'MUDA O JOGO: o tempo corre sem depender de o hodometro ser anotado.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_intervalo_tempo', @d;
SET @d = N'Acao recomendada na origem: Troca, Inspecao, Servico ou "Inspecao / Troca".';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_acao', @d;
SET @d = N'Especificacao tecnica: qual oleo, qual fluido, qual norma. Serve na hora de '
       + N'comprar a peca e de conferir o que a oficina usou.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'ds_especificacao', @d;
SET @d = N'IDENTIDADE DO ITEM. SHA-256 de modelo + item normalizado. A planilha nao tem '
       + N'coluna de ID, mas os nomes vem de um documento de fabrica e sao estaveis por '
       + N'natureza. Com constraint UNIQUE.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'hash_negocio', @d;
SET @d = N'LINHAGEM: arquivo de origem.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'nm_aba_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o item entrou na base.';
EXEC dbo.sp_documenta 'bronze', 'auto_revisao_programada', 'dt_carga', @d;

SET @d = N'SILVER | O plano do fabricante tipado: intervalo em km e em meses como numero, '
       + N'acao num dominio fechado. Uma linha por item do plano. '
       + N'Alimenta gold.dim_revisao_programada e, por ela, a previsao de vencimento.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', NULL, @d;

SET @d = N'Chave tecnica da linha na silver.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'id', @d;
SET @d = N'Modelo a que o plano se refere.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'nm_modelo', @d;
SET @d = N'Item ou componente, na grafia do fabricante.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'nm_item', @d;
SET @d = N'Sistema do veiculo a que o item pertence.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'nm_sistema', @d;
SET @d = N'Quilometros entre uma intervencao e a proxima.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'nr_intervalo_km', @d;
SET @d = N'Meses entre uma intervencao e a proxima. Vale EM PARALELO ao intervalo em km: o '
       + N'fabricante manda seguir o que vencer primeiro.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'nr_intervalo_meses', @d;
SET @d = N'Troca, Inspeção ou Serviço. O unico item ambiguo na origem e a correia Poly-V, '
       + N'marcada "Inspecao / Troca", que vira Inspeção: o que esta agendado e a '
       + N'inspecao, a troca e consequencia dela.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'ds_acao', @d;
SET @d = N'Especificacao tecnica da peca ou do fluido.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'ds_especificacao', @d;
SET @d = N'Identidade do item, herdada da bronze.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o item foi carregado na silver.';
EXEC dbo.sp_documenta 'silver', 'auto_revisao_programada', 'dt_carga', @d;

SET @d = N'SILVER | De-para entre o item do fabricante e o texto que voce escreve na nota '
       + N'da oficina. Existe porque a sua CATEGORIA e grossa demais para servir de ponte: '
       + N'"Filtro" cobre quatro itens do plano com intervalos de 10k, 20k, 20k e 10k, e '
       + N'"Fluido" cobre cinco, de 20k a 80k - casar por categoria obrigaria a adotar '
       + N'sempre o menor intervalo. O DS_ITEM do fato, sim, distingue. '
       + N'VARIAS LINHAS POR ITEM sao esperadas: o texto e livre e tem grafia variada. '
       + N'Item do plano sem mapeamento nao some da previsao - ele e o que aparece como '
       + N'"Sem registro".';
EXEC dbo.sp_documenta 'silver', 'de_para_item_revisao', NULL, @d;

SET @d = N'Item do plano do fabricante, na grafia de silver.auto_revisao_programada.';
EXEC dbo.sp_documenta 'silver', 'de_para_item_revisao', 'nm_item_plano', @d;
SET @d = N'Trecho de texto a procurar dentro do DS_ITEM do fato, ja sem acento e em '
       + N'minusculas. A comparacao usa collation acento-insensivel, entao "oleo" encontra '
       + N'"óleo". QUANDO MAIS DE UM PADRAO CASA, VENCE O MAIS LONGO - e o que impede '
       + N'"filtro de ar" de roubar o lancamento de "filtro de ar condicionado", e faz '
       + N'"filtro oleo motor" ir para o filtro e nao para o oleo do motor.';
EXEC dbo.sp_documenta 'silver', 'de_para_item_revisao', 'ds_padrao_item', @d;
SET @d = N'Quantos lancamentos do historico este padrao encontrou na ultima carga. Serve '
       + N'para achar padrao que nunca casa - sinal de grafia errada no cadastro.';
EXEC dbo.sp_documenta 'silver', 'de_para_item_revisao', 'nr_lancamentos', @d;
SET @d = N'LINHAGEM: quando o mapeamento entrou na tabela.';
EXEC dbo.sp_documenta 'silver', 'de_para_item_revisao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('auto_revisao_programada', 'de_para_item_revisao')
ORDER BY 1;
GO

SELECT COUNT(*) AS padroes_no_de_para,
       COUNT(DISTINCT nm_item_plano) AS itens_mapeados
FROM silver.de_para_item_revisao;
GO
