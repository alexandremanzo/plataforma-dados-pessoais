/* =============================================================
   manzo-dados | 03 - Camada Silver: investimentos XP
   -------------------------------------------------------------
   silver.xp_movimentacao

   Aqui os dados ganham tipo (date, decimal) e classificacao
   uniforme. A categoria e o ativo sao recalculados a partir da
   descricao para TODA a serie, inclusive para os registros que ja
   vinham classificados a mao - assim 2021 e 2026 seguem o mesmo
   criterio, o que nao acontece hoje.

   A classificacao manual original nao e descartada: fica em
   bronze.xp_movimentacao e pode ser comparada com o resultado das
   regras a qualquer momento (ver coluna fl_divergencia_manual).

   Esta e a tabela que alimenta o arquivo consolidado lido pelo
   Power BI enquanto a migracao para o SQL nao acontece.

   Pre-requisitos: 00_utilitarios.sql, 01, 02
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.xp_movimentacao') IS NULL
BEGIN
    CREATE TABLE silver.xp_movimentacao (
        sk_movimentacao        int IDENTITY(1,1) NOT NULL,

        dt_movimentacao        date              NULL,
        dt_liquidacao          date              NULL,
        ds_lancamento          varchar(1000)     NULL,
        vl_transacao           decimal(18,2)     NULL,
        vl_saldo               decimal(18,2)     NULL,

        ds_categoria           varchar(100)      NOT NULL,
        ds_ativo               varchar(200)      NULL,
        fl_rendimento          bit               NOT NULL,
        ds_tipo_movimentacao   varchar(20)       NULL,

        ds_categoria_manual    varchar(100)      NULL,
        fl_divergencia_manual  bit               NOT NULL,

        hash_negocio           char(64)          NOT NULL,
        dt_carga               datetime2(3)      NOT NULL
            CONSTRAINT DF_silver_xp_dt_carga DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_xp_movimentacao PRIMARY KEY CLUSTERED (sk_movimentacao),
        CONSTRAINT UQ_silver_xp_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_xp_dt_mov   ON silver.xp_movimentacao (dt_movimentacao);
    CREATE INDEX IX_silver_xp_categoria ON silver.xp_movimentacao (ds_categoria);
    CREATE INDEX IX_silver_xp_ativo     ON silver.xp_movimentacao (ds_ativo);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Movimentacoes da conta XP limpas, tipadas e classificadas com '
       + N'criterio uniforme. Uma linha por evento financeiro real, sem duplicatas. '
       + N'Derivada de bronze.xp_movimentacao: datas viram date, valores viram decimal, '
       + N'e categoria/ativo sao recalculados a partir da descricao textual do lancamento. '
       + N'E a tabela de referencia para analise de investimentos e a origem do arquivo '
       + N'consolidado consumido hoje pelo Power BI.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', NULL, @d;

SET @d = N'Chave substituta da movimentacao na silver. Sequencial e sem significado de '
       + N'negocio; a identidade estavel do evento e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'sk_movimentacao', @d;

SET @d = N'Data em que a movimentacao ocorreu - o fato economico. Use esta data para '
       + N'apurar resultado (dividendos recebidos no mes, compras realizadas no mes).';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'dt_movimentacao', @d;

SET @d = N'Data em que o dinheiro efetivamente entrou ou saiu da conta. Costuma ser igual '
       + N'a de movimentacao, mas difere em operacoes de bolsa (D+2) e aplicacoes com '
       + N'carencia. Use esta data para fluxo de caixa e conciliacao de saldo.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'dt_liquidacao', @d;

SET @d = N'Descricao original do lancamento, preservada da origem. Mantida na silver por '
       + N'ser a unica forma de auditar como a categoria e o ativo foram deduzidos.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'ds_lancamento', @d;

SET @d = N'Valor da transacao em reais. Positivo = entrada de recurso na conta (dividendo, '
       + N'JCP, rendimento, resgate, venda). Negativo = saida (compra, taxa, imposto, '
       + N'retirada). Somar esta coluna com filtro de categoria da o resultado do periodo.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'vl_transacao', @d;

SET @d = N'Saldo em conta corrente da corretora logo apos o lancamento. ATENCAO: e o saldo '
       + N'de CAIXA, nao o patrimonio investido - dinheiro aplicado em acoes, FIIs ou CDB '
       + N'nao aparece aqui. Nao use como medida de patrimonio.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'vl_saldo', @d;

SET @d = N'Natureza do lancamento, deduzida da descricao por regras: Dividendo, Compra, '
       + N'Operacao Bolsa, IR, IOF, Emolumentos, Taxa de Remuneracao, Resgate, Aplicacao, '
       + N'Transferencia, Retirada, Margem, Subscricao, Investback, Reembolso, Vencimento, '
       + N'Estorno, Multa, Pagamento CC e Outros. "Outros" indica descricao nao reconhecida '
       + N'pelas regras e merece revisao periodica.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'ds_categoria', @d;

SET @d = N'Ativo relacionado ao lancamento, extraido da descricao: ticker de acao ou FII '
       + N'(PETR4, HGLG11), nome de CDB, fundo, COE ou Tesouro Direto. Nulo quando o '
       + N'lancamento nao se refere a um ativo especifico, como transferencia ou taxa de '
       + N'conta. E a chave para analisar rendimento por ativo.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'ds_ativo', @d;

SET @d = N'Indica se o lancamento e remuneracao do patrimonio investido (1) ou nao (0). '
       + N'Verdadeiro para valores positivos nas categorias Dividendo, Investback, '
       + N'Reembolso e Taxa de Remuneracao. Filtrar por este campo da o total de proventos '
       + N'do periodo, sem misturar com aportes e resgates.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'fl_rendimento', @d;

SET @d = N'RECEITA quando o valor e positivo, DESPESA quando negativo. Redundante com o '
       + N'sinal de vl_transacao, mantido porque o relatorio atual do Power BI usa este '
       + N'campo como dimensao.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'ds_tipo_movimentacao', @d;

SET @d = N'Categoria que estava preenchida a mao na planilha mestre, quando havia. Nula '
       + N'para eventos que nunca passaram pela planilha. Guardada para permitir auditar '
       + N'as regras automaticas contra o criterio historico.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'ds_categoria_manual', @d;

SET @d = N'Marca 1 quando a categoria calculada pela regra difere da que estava na planilha '
       + N'mestre. Nao significa erro: pode ser correcao de uma classificacao antiga '
       + N'inconsistente ou um caso que a regra ainda nao cobre. Revisar estes registros '
       + N'e a forma de melhorar as regras ao longo do tempo.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'fl_divergencia_manual', @d;

SET @d = N'Identidade do evento, igual a de bronze.xp_movimentacao. E a chave de ligacao '
       + N'entre as camadas e o que garante que a silver nao duplique registros.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'hash_negocio', @d;

SET @d = N'LINHAGEM: data e hora em que o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'xp_movimentacao', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name IN ('bronze','silver') ORDER BY 1;
GO
