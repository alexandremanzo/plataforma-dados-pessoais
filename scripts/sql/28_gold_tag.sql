/* =============================================================
   manzo-dados | 28 - Camada Gold: tags (a coluna OBS)
   -------------------------------------------------------------
   gold.dim_tag + gold.ponte_tag
   + DS_OBS em gold.fato_movto_financ e gold.fato_familia

   A coluna OBS das planilhas nao e observacao livre: e um SISTEMA
   DE MARCACAO. Sao 61 valores distintos em 2.280 lancamentos, do
   tipo #Nina, #Escola, #Sedan, #AptoCentro, Viagem07_Praia.

   ELE CRUZA AS BASES. #AptoCentro e #Theo aparecem nas tres origens
   financeiras; #Escola e #Sedan em duas. E um eixo de analise
   proprio - "quanto custou a viagem", "quanto gasto com a Nina",
   "quanto ja foi para o apartamento" - que ate agora estava preso
   na silver, porque nenhum fato levava a coluna adiante.

   POR QUE UMA PONTE, E NAO UMA COLUNA. Um lancamento pode ter mais
   de uma tag: "#Praia-Out22 #AleLia" marca 34 lancamentos que
   sao ao mesmo tempo da viagem e do casal. Uma chave estrangeira
   simples obrigaria a escolher uma, e a outra se perderia. A ponte
   resolve o muitos-para-muitos e absorve tags novas sem mudanca de
   modelo.

   AS GRAFIAS NAO SAO UNIFICADAS, por decisao: Arraial aparece em
   sete formas, e so quem lancou sabe se sao a mesma viagem ou
   viagens diferentes. Unificar por semelhanca de texto arriscaria
   somar coisas distintas. Quando houver a lista revisada, basta um
   de-para, como o das categorias do Itau.

   DS_OBS BRUTO VAI JUNTO nos fatos. A ponte responde por tag; a
   coluna preserva o texto exato, inclusive das duas celulas que
   sao observacao de verdade e nao marcacao.

   Pre-requisitos: 14_gold_movimentacao.sql, 17_gold_familia.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('gold.dim_tag') IS NULL
BEGIN
    CREATE TABLE gold.dim_tag (
        SK_TAG  int IDENTITY(1,1) NOT NULL,
        NM_TAG  varchar(100) NOT NULL,
        DS_TIPO      varchar(30)  NOT NULL,
        DT_CARGA     datetime2(3) NOT NULL
            CONSTRAINT DF_dim_tag_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_tag PRIMARY KEY (SK_TAG),
        CONSTRAINT UQ_dim_tag_nome UNIQUE (NM_TAG)
    );

    SET IDENTITY_INSERT gold.dim_tag ON;
    INSERT INTO gold.dim_tag (SK_TAG, NM_TAG, DS_TIPO)
    VALUES (-1, 'Não informado', 'Não informado');
    SET IDENTITY_INSERT gold.dim_tag OFF;
END
GO

IF OBJECT_ID('gold.ponte_tag') IS NULL
BEGIN
    CREATE TABLE gold.ponte_tag (
        SK_PONTE     int IDENTITY(1,1) NOT NULL,
        HASH_NEGOCIO char(64)     NOT NULL,
        SK_TAG  int          NOT NULL,
        DS_FATO      varchar(40)  NOT NULL,
        DT_CARGA     datetime2(3) NOT NULL
            CONSTRAINT DF_ponte_tag_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_ponte_tag PRIMARY KEY (SK_PONTE),
        CONSTRAINT UQ_ponte_tag UNIQUE (HASH_NEGOCIO, SK_TAG),
        CONSTRAINT FK_ponte_tag FOREIGN KEY (SK_TAG)
            REFERENCES gold.dim_tag (SK_TAG)
    );

    CREATE INDEX IX_ponte_tag_hash ON gold.ponte_tag (HASH_NEGOCIO);
    CREATE INDEX IX_ponte_tag_ctx  ON gold.ponte_tag (SK_TAG);
END
GO

IF COL_LENGTH('gold.fato_movto_financ', 'DS_OBS') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD DS_OBS varchar(500) NULL;
GO

IF COL_LENGTH('gold.fato_familia', 'DS_OBS') IS NULL
    ALTER TABLE gold.fato_familia ADD DS_OBS varchar(500) NULL;
GO

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | As marcacoes da coluna OBS das planilhas, tratadas como o que sao: um '
       + N'eixo de analise. Viagens, pessoas, imoveis, veiculos e projetos - #Nina, '
       + N'#Escola, #AptoCentro, Viagem07_Praia. '
       + N'E COMPARTILHADA PELOS FATOS FINANCEIROS, e e isso que da valor: as mesmas tags '
       + N'aparecem no Itau, no cartao e na conta familia, entao somar por ela responde '
       + N'"quanto custou a viagem" juntando as tres origens de uma vez. '
       + N'As grafias NAO foram unificadas: Arraial aparece em sete formas e so quem '
       + N'lancou sabe se sao a mesma viagem. Quando houver a lista revisada, entra um '
       + N'de-para.';
EXEC dbo.sp_documenta 'gold', 'dim_tag', NULL, @d;

SET @d = N'Chave substituta da tag. -1 representa lancamento sem marcacao.';
EXEC dbo.sp_documenta 'gold', 'dim_tag', 'SK_TAG', @d;
SET @d = N'A tag como foi digitada, incluindo o # quando havia. Preservada sem unificacao.';
EXEC dbo.sp_documenta 'gold', 'dim_tag', 'NM_TAG', @d;
SET @d = N'Natureza da marcacao, inferida do proprio texto: Viagem quando o nome comeca '
       + N'com "Viagem" ou traz destino e data, e Marcacao para o restante. E palpite de '
       + N'apoio a leitura, nao classificacao revisada - corrija por UPDATE quando quiser.';
EXEC dbo.sp_documenta 'gold', 'dim_tag', 'DS_TIPO', @d;
SET @d = N'LINHAGEM: quando a tag entrou na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_tag', 'DT_CARGA', @d;

SET @d = N'GOLD | Liga cada lancamento as suas tags. E tabela PONTE porque a relacao e '
       + N'muitos-para-muitos: um lancamento pode ter mais de uma marcacao - '
       + N'"#Praia-Out22 #AleLia" e ao mesmo tempo a viagem e o casal - e uma tag '
       + N'marca muitos lancamentos. Uma chave estrangeira simples no fato obrigaria a '
       + N'escolher uma e perder a outra. '
       + N'NO POWER BI: ligue dim_tag para ca por SK_TAG e daqui para o fato por '
       + N'HASH_NEGOCIO, com o filtro cruzado nos DOIS SENTIDOS na segunda relacao - sem '
       + N'isso o filtro nao chega ao fato. '
       + N'ATENCAO ao somar: um lancamento com duas tags aparece duas vezes ao cruzar por '
       + N'aqui, entao somar valor sem filtrar uma tag especifica conta em duplicidade.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', NULL, @d;

SET @d = N'Chave substituta da ligacao.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', 'SK_PONTE', @d;
SET @d = N'Identidade do lancamento, a mesma do fato. Serve para os tres fatos porque o '
       + N'hash e unico em toda a plataforma.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', 'HASH_NEGOCIO', @d;
SET @d = N'Chave para gold.dim_tag: qual tag.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', 'SK_TAG', @d;
SET @d = N'Nome do fato a que o lancamento pertence. Existe para tornar a ligacao '
       + N'auditavel e para permitir filtrar a ponte por origem sem consultar os fatos.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', 'DS_FATO', @d;
SET @d = N'LINHAGEM: quando a ligacao foi criada.';
EXEC dbo.sp_documenta 'gold', 'ponte_tag', 'DT_CARGA', @d;

SET @d = N'Texto da coluna OBS da planilha, exatamente como digitado. Na maioria das vezes '
       + N'e uma marcacao (#Nina, Viagem07_Praia) e nesse caso ja esta desmembrada em '
       + N'gold.ponte_tag, que e por onde se deve analisar. Esta coluna existe para '
       + N'auditoria e para os poucos casos em que o campo foi usado como observacao de '
       + N'verdade, e nao como tag.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'DS_OBS', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia', 'DS_OBS', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('dim_tag', 'ponte_tag', 'fato_movto_financ', 'fato_familia')
ORDER BY 1;
GO
