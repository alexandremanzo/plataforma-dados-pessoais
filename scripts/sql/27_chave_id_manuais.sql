/* =============================================================
   manzo-dados | 27 - Chave propria nas bases de cadastro manual
   -------------------------------------------------------------
   bronze.itau_movimentacao.ds_id_origem
   bronze.cartao_xp.ds_id_origem

   POR QUE ESTA MUDANCA EXISTE.

   Duas bases sao digitadas a mao: a conta do Itau e o cartao XP.
   Nelas e comum lancar na pressa e completar depois - a descricao
   fica em branco, o valor sai errado, ou a fatura e registrada no
   mes X quando na conferencia se descobre que era o mes Y.

   O problema e que data, descricao e valor COMPUNHAM a chave de
   negocio. Corrigir qualquer um deles mudava a identidade do
   registro: a carga inseria um novo e deixava o antigo orfao,
   inflando os totais em silencio. Justamente os campos que mais
   precisam de correcao eram os que nao podiam ser corrigidos.

   A solucao e a mesma ja usada no diario "meu dia", onde a chave e
   o carimbo que o Google atribui: um identificador PROPRIO, que
   nao carrega significado e por isso nunca muda. Aqui ele vem de
   uma coluna ID acrescentada as duas planilhas.

   O QUE ISSO LIBERA: data, descricao, valor e data da fatura
   passam a ser atualizaveis, e a correcao atravessa bronze,
   silver e gold. E o que permite a conferencia entre o valor pago
   no cartao e a soma dos itens da fatura, porque a data da fatura
   pode ser ajustada quando a conferencia mostra que estava errada.

   A coluna nasce anulavel porque as linhas ja carregadas nao tem
   ID: quem as preenche e o migra_chave_id.py, que tambem reescreve
   os hashes no lugar, preservando as chaves substitutas e todo o
   historico. Depois da migracao a carga passa a exigir o ID.

   Pre-requisitos: 06_bronze_itau.sql, 09_bronze_cartao_xp.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* O sqlcmd conecta com QUOTED_IDENTIFIER desligado, e indice FILTRADO
   exige a opcao ligada - sem isso o CREATE INDEX falha com a mensagem
   1934, que nao menciona o filtro e manda procurar em outro lugar. */
SET QUOTED_IDENTIFIER ON;
GO

IF COL_LENGTH('bronze.itau_movimentacao', 'ds_id_origem') IS NULL
    ALTER TABLE bronze.itau_movimentacao ADD ds_id_origem varchar(30) NULL;
GO

IF COL_LENGTH('bronze.cartao_xp', 'ds_id_origem') IS NULL
    ALTER TABLE bronze.cartao_xp ADD ds_id_origem varchar(30) NULL;
GO

/* Unicidade garantida pelo banco, e nao pela carga. Indice filtrado
   porque a coluna e anulavel: antes da migracao as linhas antigas
   ainda nao tem ID, e um UNIQUE comum recusaria mais de um nulo. */
IF NOT EXISTS (SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_itau_id_origem'
                  AND object_id = OBJECT_ID('bronze.itau_movimentacao'))
    CREATE UNIQUE INDEX UQ_itau_id_origem
        ON bronze.itau_movimentacao (ds_id_origem)
        WHERE ds_id_origem IS NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_cartao_xp_id_origem'
                  AND object_id = OBJECT_ID('bronze.cartao_xp'))
    CREATE UNIQUE INDEX UQ_cartao_xp_id_origem
        ON bronze.cartao_xp (ds_id_origem)
        WHERE ds_id_origem IS NOT NULL;
GO

DECLARE @d nvarchar(3750);

SET @d = N'CHAVE DE NEGOCIO. Identificador proprio do lancamento, digitado na coluna ID da '
       + N'planilha. Substitui a chave composta por data, descricao e valor que vigorava '
       + N'antes. MOTIVO: esta base e cadastrada a mao e esses tres campos sao justamente '
       + N'os que mais precisam de correcao posterior - lancar na pressa e completar '
       + N'depois e o uso normal. Enquanto eles compunham a chave, corrigir qualquer um '
       + N'deles criava um registro novo e deixava o antigo orfao, inflando os totais em '
       + N'silencio. Com um identificador sem significado, tudo o mais e atualizavel e a '
       + N'correcao chega ate a gold. '
       + N'NUNCA REAPROVEITE UM ID de linha excluida: o lancamento novo herdaria os dados '
       + N'do antigo. Unicidade imposta por indice unico.';
EXEC dbo.sp_documenta 'bronze', 'itau_movimentacao', 'ds_id_origem', @d;

SET @d = N'CHAVE DE NEGOCIO. Identificador proprio do lancamento, digitado na coluna ID da '
       + N'planilha. Substitui a chave composta por data, descricao, valor tratado e data '
       + N'de pagamento. MOTIVO: alem da correcao de descricao e valor, a DATA DA FATURA '
       + N'muda com frequencia - um gasto lancado como sendo da fatura do mes X se revela, '
       + N'na conferencia contra o valor pago, ser do mes Y. Enquanto a data da fatura '
       + N'compunha a chave, esse acerto criava um lancamento novo em vez de mover o '
       + N'existente, e a conferencia nunca fechava. '
       + N'NUNCA REAPROVEITE UM ID de linha excluida. Unicidade imposta por indice unico.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_id_origem', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name IN ('itau_movimentacao', 'cartao_xp') AND s.name = 'bronze'
ORDER BY 1;
GO
