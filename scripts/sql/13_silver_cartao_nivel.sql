/* =============================================================
   manzo-dados | 13 - Marcador de pagamento de fatura no cartao
   -------------------------------------------------------------
   Acrescenta FL_PAGAMENTO_FATURA a silver.cartao_movimentacao.

   O arquivo do cartao Nubank traz, misturados aos gastos, os 48
   lancamentos de "Pagamento recebido" - o pagamento da propria
   fatura. Somados aos gastos, eles se anulam: a soma bruta de 2.345
   lancamentos dava R$ 2.310 quando o consumo real foi R$ 122.168.

   Esse lancamento e o dado PAI da fatura; os gastos sao os FILHOS.
   O marcador permite que a gold monte os dois niveis sem contar a
   mesma despesa duas vezes.

   O cartao XP nao tem esse problema: la o pagamento da fatura fica
   na conta corrente, nunca no arquivo do cartao. Por isso o marcador
   vale 0 em toda aquela origem.

   Pre-requisitos: 11_silver_cartao.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

IF COL_LENGTH('silver.cartao_movimentacao', 'fl_pagamento_fatura') IS NULL
    ALTER TABLE silver.cartao_movimentacao
        ADD fl_pagamento_fatura bit NOT NULL
            CONSTRAINT DF_cartao_pagto_fatura DEFAULT (0);
GO

DECLARE @d nvarchar(3750);

SET @d = N'Marca 1 quando a linha e o PAGAMENTO DA FATURA e nao um gasto. Ocorre apenas '
       + N'na origem Nubank, cujo arquivo traz os 48 pagamentos misturados ao consumo - '
       + N'somados, eles anulam os gastos e a serie de 4 anos aparenta R$ 2.310 em vez de '
       + N'R$ 122.168. E o lancamento PAI da fatura, do qual os gastos sao os FILHOS. '
       + N'SEMPRE filtre por fl_pagamento_fatura = 0 ao somar despesa de cartao.';
EXEC dbo.sp_documenta 'silver', 'cartao_movimentacao', 'fl_pagamento_fatura', @d;
GO

SELECT COUNT(*) AS colunas,
       SUM(CASE WHEN ep.value IS NOT NULL THEN 1 ELSE 0 END) AS documentadas
FROM sys.columns c
LEFT JOIN sys.extended_properties ep
       ON ep.class = 1 AND ep.major_id = c.object_id
      AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
WHERE c.object_id = OBJECT_ID('silver.cartao_movimentacao');
GO
