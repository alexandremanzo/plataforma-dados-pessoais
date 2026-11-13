/* =============================================================
   manzo-dados | 10 - Classificacao de ativos por classe
   -------------------------------------------------------------
   silver.de_para_classe_ativo

   Classificacao dos ativos em dois niveis, definida manualmente:

       Classe de Ativo   -> Renda Fixa, Renda Variavel, Fundos
                            Imobiliarios, Emprestimo de Ativos,
                            Operacoes Estruturadas, Fundos de
                            Investimento
       Subclasse         -> CDB Pos-Fixado, CDB Pre-Fixado, Acoes,
                            FII, Direito de Subscricao FII, CRI, LCA,
                            Titulo Publico, COE, BTC, ...

   E DADO DE REFERENCIA, nao dado pessoal: descreve o que cada
   instrumento e, nao quanto se tem dele. Por isso mora no repositorio
   e nao numa planilha do Dropbox.

   A subclasse e mais fina que o TP_ATIVO deduzido por regra: separa
   CDB pos de pre-fixado e direito de subscricao da cota do FII, o que
   nenhuma regra automatica conseguiria inferir do texto do extrato.

   Quando um ativo nao consta aqui, a gold cai no TP_ATIVO deduzido e
   marca a procedencia em DS_ORIGEM_CLASSE.

   Pre-requisitos: 00, 01
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.de_para_classe_ativo') IS NULL
BEGIN
    CREATE TABLE silver.de_para_classe_ativo (
        cd_ativo      varchar(200) NOT NULL,
        ds_classe     varchar(60)  NOT NULL,
        ds_subclasse  varchar(60)  NOT NULL,
        dt_carga      datetime2(3) NOT NULL
            CONSTRAINT DF_de_para_classe_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_de_para_classe_ativo PRIMARY KEY (cd_ativo)
    );
END
GO

/* Substituicao completa: este script e a fonte da verdade. */
DELETE FROM silver.de_para_classe_ativo;
GO

INSERT INTO silver.de_para_classe_ativo (cd_ativo, ds_classe, ds_subclasse) VALUES
-- Lista ilustrativa: na base real esta tabela tem uma linha por ativo
-- que ja passou pela carteira. Aqui ficam exemplos de cada classe.
-- Renda variavel
('ITUB4',                'Renda Variável', 'Ações'),
('VALE3',                'Renda Variável', 'Ações'),
('BRVALEACNOR0',         'Renda Variável', 'Ações (ISIN)'),

-- Fundos imobiliarios
('HGLG11',               'Fundos Imobiliários', 'FII'),
('MXRF11',               'Fundos Imobiliários', 'FII'),
-- Uma grafia so: a collation do banco e case-insensitive, entao
-- "Exemplo FII" e "EXEMPLO FII" colidem na chave primaria.
-- A busca do lado do Python tambem ignora caixa.
('EXEMPLO RENDA FII',    'Fundos Imobiliários', 'FII'),
('MXRF13',               'Fundos Imobiliários', 'Direito de Subscrição FII'),

-- Emprestimo de ativos (BTC). Inclui a grafia antiga, so com o
-- mnemonico, e a atual, com o ticker completo.
('BTC VALE',             'Empréstimo de Ativos', 'BTC (Aluguel de Ações)'),
('BTC VALE3',            'Empréstimo de Ativos', 'BTC (Aluguel de Ações)'),

-- Renda fixa
('CDB FLU CDB000EXEMP1', 'Renda Fixa', 'CDB Pós-Fixado'),
('CDB PRE DU CDB000EXE2', 'Renda Fixa', 'CDB Pré-Fixado'),
('CDB',                  'Renda Fixa', 'CDB'),
('LCA EXEMPLO',          'Renda Fixa', 'LCA'),
('TESOURO DIRETO',       'Renda Fixa', 'Título Público'),

-- Fundos de investimento. Os codigos "FUNDOS ..." sao a forma que a
-- extracao produz depois de consolidar os nomes truncados.
('Exemplo FIRF Referenciado DI',        'Fundos de Investimento', 'Fundo de Renda Fixa'),
('FUNDOS EXEMPLO FIRF REFERENCIADO DI', 'Fundos de Investimento', 'Fundo de Renda Fixa'),

-- Operacoes estruturadas
('COE EXEMPLO000', 'Operações Estruturadas', 'COE');
GO


/* -------------------------------------------------------------
   Atributos de classe na dimensao de ativo
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_ativo', 'DS_CLASSE_ATIVO') IS NULL
    ALTER TABLE gold.dim_ativo ADD DS_CLASSE_ATIVO varchar(60) NULL;
GO
IF COL_LENGTH('gold.dim_ativo', 'DS_SUBCLASSE_ATIVO') IS NULL
    ALTER TABLE gold.dim_ativo ADD DS_SUBCLASSE_ATIVO varchar(60) NULL;
GO
IF COL_LENGTH('gold.dim_ativo', 'DS_ORIGEM_CLASSE') IS NULL
    ALTER TABLE gold.dim_ativo ADD DS_ORIGEM_CLASSE varchar(20) NULL;
GO

/* O membro -1 nao passa pela carga (nao vem da silver), entao a classe
   dele e definida aqui. Sem isso, lancamentos sem ativo apareceriam
   com classe nula no relatorio, em vez de "Nao aplicavel". */
UPDATE gold.dim_ativo
   SET DS_CLASSE_ATIVO = 'Não aplicável',
       DS_SUBCLASSE_ATIVO = 'Não aplicável',
       DS_ORIGEM_CLASSE = 'MANUAL'
 WHERE SK_ATIVO = -1;
GO

DECLARE @d nvarchar(3750);

SET @d = N'REFERENCIA | Classificacao dos ativos em classe e subclasse, definida a mao. '
       + N'E dado de referencia (o que o instrumento e), nao dado pessoal (quanto se tem), '
       + N'por isso vive no repositorio e nao numa planilha. A subclasse e mais fina que o '
       + N'TP_ATIVO deduzido por regra: separa CDB pos de pre-fixado e direito de '
       + N'subscricao da cota do FII - distincoes que nenhuma regra automatica extrairia '
       + N'do texto do extrato.';
EXEC dbo.sp_documenta 'silver', 'de_para_classe_ativo', NULL, @d;

SET @d = N'Codigo do ativo, igual ao CD_ATIVO de gold.dim_ativo. Inclui grafias antigas '
       + N'(ex: "BTC ITUB") e atuais ("BTC ITUB4") para o de-para continuar valendo se '
       + N'uma regra de extracao mudar.';
EXEC dbo.sp_documenta 'silver', 'de_para_classe_ativo', 'cd_ativo', @d;

SET @d = N'Classe do ativo, o nivel mais amplo: Renda Fixa, Renda Variavel, Fundos '
       + N'Imobiliarios, Fundos de Investimento, Emprestimo de Ativos ou Operacoes '
       + N'Estruturadas. E o nivel para analisar alocacao de patrimonio.';
EXEC dbo.sp_documenta 'silver', 'de_para_classe_ativo', 'ds_classe', @d;

SET @d = N'Subclasse do ativo, o nivel de detalhe: CDB Pos-Fixado, CDB Pre-Fixado, Acoes, '
       + N'FII, Direito de Subscricao FII, CRI, LCA, Titulo Publico, COE, BTC.';
EXEC dbo.sp_documenta 'silver', 'de_para_classe_ativo', 'ds_subclasse', @d;

SET @d = N'LINHAGEM: quando o registro entrou na tabela.';
EXEC dbo.sp_documenta 'silver', 'de_para_classe_ativo', 'dt_carga', @d;

SET @d = N'Classe do ativo (Renda Fixa, Renda Variavel, Fundos Imobiliarios...). Vem do '
       + N'de-para manual quando o ativo consta la; caso contrario e deduzida do TP_ATIVO. '
       + N'Use DS_ORIGEM_CLASSE para saber qual foi o caso.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'DS_CLASSE_ATIVO', @d;

SET @d = N'Subclasse do ativo, mais fina que TP_ATIVO: distingue CDB pos de pre-fixado e '
       + N'direito de subscricao da cota do FII.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'DS_SUBCLASSE_ATIVO', @d;

SET @d = N'Procedencia da classificacao: MANUAL quando veio de silver.de_para_classe_ativo '
       + N'e DEDUZIDA quando foi inferida do TP_ATIVO. Permite ver quanto do patrimonio '
       + N'esta classificado por decisao sua e quanto por regra.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'DS_ORIGEM_CLASSE', @d;
GO

SELECT COUNT(*) AS ativos_classificados,
       COUNT(DISTINCT ds_classe) AS classes,
       COUNT(DISTINCT ds_subclasse) AS subclasses
FROM silver.de_para_classe_ativo;
GO
