/* =============================================================
   manzo-dados | 50 - Origem do cadastro em gold.dim_ativo
   -------------------------------------------------------------
   + DS_ORIGEM_DADO em gold.dim_ativo

   A dimensão deixa de ter uma origem só. Até aqui todos os 108
   ativos nasceram do extrato em xlsx; a partir da integração com a
   Pluggy, entram ativos que o extrato nunca citou - fundos
   identificados por CNPJ e papéis de renda fixa por código, que
   não aparecem no extrato porque lá o que se vê é o evento de
   caixa, não a carteira.

   NÃO CONFUNDIR COM DS_ORIGEM_CLASSE, que já existia:

       DS_ORIGEM_CLASSE   de onde veio a CLASSIFICAÇÃO do ativo
                          (MANUAL quando você decidiu, DEDUZIDA
                          quando a regra inferiu)

       DS_ORIGEM_DADO     de onde veio o REGISTRO do ativo
                          (EXTRATO, PLUGGY, MANUAL)

   São perguntas diferentes e podem divergir: um ativo vindo da
   Pluggy pode ter classificação revisada à mão, e aí fica
   PLUGGY + MANUAL.

   POR QUE ISSO IMPORTA NA PRÁTICA. Quando um número da carteira
   não bater, a primeira pergunta é "de onde veio este ativo?". Sem
   a coluna, a resposta exige abrir dois pipelines; com ela, é um
   WHERE.

   Os 108 existentes recebem EXTRATO, menos o membro -1
   (Não aplicável), que é MANUAL por construção.

   Pré-requisitos: 04_gold_investimentos.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF COL_LENGTH('gold.dim_ativo', 'DS_ORIGEM_DADO') IS NULL
    ALTER TABLE gold.dim_ativo ADD DS_ORIGEM_DADO varchar(20) NULL;
GO

-- Só preenche o que está nulo: rodar de novo não desfaz uma origem
-- que a carga da Pluggy já tenha gravado.
UPDATE gold.dim_ativo
   SET DS_ORIGEM_DADO = CASE WHEN SK_ATIVO = -1 THEN 'MANUAL' ELSE 'EXTRATO' END
 WHERE DS_ORIGEM_DADO IS NULL;
GO

IF EXISTS (SELECT 1 FROM sys.columns
            WHERE object_id = OBJECT_ID('gold.dim_ativo')
              AND name = 'DS_ORIGEM_DADO' AND is_nullable = 1)
    ALTER TABLE gold.dim_ativo ALTER COLUMN DS_ORIGEM_DADO varchar(20) NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.default_constraints
                WHERE name = 'DF_dim_ativo_origem_dado')
    ALTER TABLE gold.dim_ativo ADD CONSTRAINT DF_dim_ativo_origem_dado
        DEFAULT ('MANUAL') FOR DS_ORIGEM_DADO;
GO

-- Valor fora da lista entra calado e vira dois rótulos para a mesma
-- coisa ('Pluggy' e 'PLUGGY'). A CHECK recusa na hora.
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
                WHERE name = 'CK_dim_ativo_origem_dado')
    ALTER TABLE gold.dim_ativo ADD CONSTRAINT CK_dim_ativo_origem_dado
        CHECK (DS_ORIGEM_DADO IN ('EXTRATO', 'PLUGGY', 'MANUAL'));
GO

DECLARE @d nvarchar(3750);

SET @d = N'De onde veio o REGISTRO do ativo: EXTRATO (planilha de movimentacao da XP), '
       + N'PLUGGY (API de Open Finance) ou MANUAL. '
       + N'NAO CONFUNDIR COM DS_ORIGEM_CLASSE, que diz de onde veio a CLASSIFICACAO do ativo. '
       + N'Sao perguntas diferentes e podem divergir: ativo vindo da Pluggy com classificacao '
       + N'revisada a mao fica PLUGGY + MANUAL. '
       + N'Serve para responder "de onde veio este ativo?" com um WHERE, em vez de abrir dois '
       + N'pipelines - que e a primeira pergunta quando um numero da carteira nao bate.';
EXEC dbo.sp_documenta 'gold', 'dim_ativo', 'DS_ORIGEM_DADO', @d;
GO

SELECT DS_ORIGEM_DADO, COUNT(*) ativos
FROM gold.dim_ativo GROUP BY DS_ORIGEM_DADO ORDER BY 2 DESC;

SELECT 'coluna criada' AS conferencia,
       CASE WHEN COL_LENGTH('gold.dim_ativo','DS_ORIGEM_DADO') IS NOT NULL
            THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'sem nulo',
       CASE WHEN NOT EXISTS (SELECT 1 FROM gold.dim_ativo WHERE DS_ORIGEM_DADO IS NULL)
            THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'CHECK ativa',
       CASE WHEN EXISTS (SELECT 1 FROM sys.check_constraints
                          WHERE name = 'CK_dim_ativo_origem_dado')
            THEN 'sim' ELSE 'NAO' END
UNION ALL SELECT 'documentada',
       CASE WHEN EXISTS (SELECT 1 FROM sys.extended_properties ep
                          WHERE ep.major_id = OBJECT_ID('gold.dim_ativo')
                            AND ep.name = 'MS_Description'
                            AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID('gold.dim_ativo'),
                                                             'DS_ORIGEM_DADO','ColumnId'))
            THEN 'sim' ELSE 'NAO' END;
GO
