/* =============================================================
   manzo-dados | 31 - Camada Bronze: historico financeiro
   -------------------------------------------------------------
   bronze.financ_historico

   Lancamentos antigos consolidados a mao numa planilha, cobrindo
   fevereiro de 2014 a maio de 2018 - o periodo ANTERIOR as origens
   atuais, ja que o Itau comeca em outubro de 2016 e os cartoes em
   maio de 2018. Sao 3.950 registros que estendem a serie financeira
   em dois anos e meio para tras.

   NAO HA SOBREPOSICAO COM O QUE JA EXISTE, e isso foi verificado
   antes de carregar: dos 572 lancamentos posteriores ao inicio do
   Itau, NENHUM tem data, valor e descricao identicos a algo ja no
   banco. Os 69 que coincidem so em data e valor tem descricoes
   diferentes - almocos de mesmo valor no mesmo dia. E as formas de
   pagamento aqui sao dinheiro, vale-alimentacao, Visa BB, Visa/CTI
   e Diners: nenhuma e Itau, XP ou Nubank. Sao instrumentos
   distintos, que convivem sem duplicar.

   287 LINHAS NAO SAO MOVIMENTACAO. Tem tipo "Meta", descricao
   "Meta" e grupo "META", somando +R$ 135.522 - sao 24 por
   categoria, ou seja, orcamento mensal planejado de dois anos. A
   bronze as guarda por fidelidade; a silver as marca e o fato as
   exclui. Somadas como receita, inflariam o resultado com dinheiro
   que nunca entrou.

   A COLUNA "Area" DA PLANILHA ESTA VAZIA em todas as linhas. A
   classificacao por area e derivada na silver, com a procedencia
   registrada.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID('bronze.financ_historico') IS NULL
BEGIN
    CREATE TABLE bronze.financ_historico (
        id_lancamento     int IDENTITY(1,1) NOT NULL,

        ds_id_origem      varchar(30)   NOT NULL,
        ds_data           varchar(50)   NULL,
        ds_descricao      varchar(1000) NULL,
        ds_valor          varchar(50)   NULL,
        ds_valor_tratado  varchar(50)   NULL,
        ds_tipo_movimentacao varchar(30) NULL,
        ds_forma_pagamento varchar(60)  NULL,
        ds_data_pgto      varchar(50)   NULL,
        ds_status_pgto    varchar(20)   NULL,

        ds_area           varchar(100)  NULL,
        ds_categoria      varchar(100)  NULL,
        ds_grupo          varchar(100)  NULL,
        ds_pessoa_pagar   varchar(120)  NULL,
        ds_pessoa_receber varchar(200)  NULL,

        ds_cidade         varchar(100)  NULL,
        ds_uf             varchar(20)   NULL,
        ds_pais           varchar(60)   NULL,
        ds_obs            varchar(500)  NULL,
        ds_projeto        varchar(100)  NULL,
        ds_tag            varchar(100)  NULL,

        hash_negocio      char(64)      NOT NULL,
        nm_arquivo_origem varchar(200)  NOT NULL,
        nr_linha_arquivo  int           NULL,
        dt_carga          datetime2(3)  NOT NULL
            CONSTRAINT DF_financ_historico_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_financ_historico PRIMARY KEY CLUSTERED (id_lancamento),
        CONSTRAINT UQ_financ_historico_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_financ_historico_data ON bronze.financ_historico (ds_data);
    CREATE INDEX IX_financ_historico_cat  ON bronze.financ_historico (ds_categoria);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_financ_historico_id'
                  AND object_id = OBJECT_ID('bronze.financ_historico'))
    CREATE UNIQUE INDEX UQ_financ_historico_id
        ON bronze.financ_historico (ds_id_origem);
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Historico financeiro consolidado a mao, de fevereiro/2014 a maio/2018. '
       + N'E o periodo ANTERIOR as origens atuais - o Itau comeca em out/2016 e os cartoes '
       + N'em mai/2018 - e por isso estende a serie em dois anos e meio para tras, cobrindo '
       + N'uma epoca em que o gasto passava por dinheiro, vale-alimentacao e cartoes que '
       + N'nao existem mais. '
       + N'VERIFICADO ANTES DE CARREGAR: nao ha sobreposicao com o que ja estava na base. '
       + N'Nenhum lancamento posterior ao inicio do Itau repete data, valor e descricao de '
       + N'algo existente, e as formas de pagamento aqui sao outras.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'id_lancamento', @d;

SET @d = N'CHAVE DE NEGOCIO. Identificador digitado na coluna ID da planilha. Esta base '
       + N'segue editavel, e o ID e o que permite corrigir descricao, valor ou data depois '
       + N'sem criar um registro novo - o mesmo desenho ja usado no Itau e no cartao XP. '
       + N'Ao contrario daquelas duas, aqui o ID existe desde a primeira carga, entao nao '
       + N'houve migracao de chave. NUNCA REAPROVEITE UM ID de linha excluida.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_id_origem', @d;

SET @d = N'Data do lancamento, em formato ISO como texto.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_data', @d;
SET @d = N'Descricao do lancamento, escrita a mao.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_descricao', @d;
SET @d = N'Valor como digitado, sem sinal de despesa. Ver ds_valor_tratado.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_valor', @d;
SET @d = N'METRICA DA ORIGEM. Valor com sinal: negativo para despesa, positivo para '
       + N'receita. E a coluna que alimenta o fato.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_valor_tratado', @d;

SET @d = N'Despesa, Receita ou META. ATENCAO AO TERCEIRO: as 287 linhas marcadas como Meta '
       + N'nao sao movimentacao, e sim orcamento mensal planejado - 24 por categoria, '
       + N'somando +R$ 135.522. Ficam aqui por fidelidade a origem, a silver as marca em '
       + N'fl_meta e o fato as exclui.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_tipo_movimentacao', @d;

SET @d = N'Instrumento usado: Dinheiro/Debito, visa BB, Vale Alimentacao, Visa/CTI ou '
       + N'Diners. Nenhum deles e Itau, XP ou Nubank - foi o que permitiu concluir que esta '
       + N'base nao duplica as demais. Vazio em 877 linhas, que caem no membro nao '
       + N'informado da dimensao de origem.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_forma_pagamento', @d;

SET @d = N'Data do pagamento efetivo, quando difere da data do lancamento.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_data_pgto', @d;
SET @d = N'Indicador de pagamento: S para pago, N para a pagar. Aparece tambem em minuscula, '
       + N'que a silver unifica.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_status_pgto', @d;

SET @d = N'VAZIA EM TODAS AS LINHAS nesta origem. Preservada para que a bronze continue '
       + N'sendo copia fiel da planilha; a area usada na analise e derivada na silver, a '
       + N'partir da categoria e do grupo, com a procedencia registrada.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2. Sao 15 valores, dos quais tres nao existem nas origens '
       + N'atuais: AJUSTE, FINANCAS e Telefonia.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_categoria', @d;
SET @d = N'CLASSIFICACAO nivel 3, o mais fino. Sao 172 valores.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_grupo', @d;
SET @d = N'Quem pagou, como registrado na planilha.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_pessoa_pagar', @d;
SET @d = N'Estabelecimento ou pessoa que recebeu.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_pessoa_receber', @d;
SET @d = N'Cidade do gasto.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_cidade', @d;
SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_uf', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_pais', @d;

SET @d = N'Observacao livre. NAO ALIMENTA gold.dim_tag, diferente do OBS das demais '
       + N'origens: aqui o campo guarda numeros soltos como "-160" e "556.37", que o '
       + N'interpretador de marcacoes leria como tag. Nesta base quem marca contexto e '
       + N'ds_projeto.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_obs', @d;

SET @d = N'MARCACAO DE CONTEXTO desta origem: Compacto, Hatch 2008, Viagem Exterior, Sedan 2016. '
       + N'E esta coluna, e nao ds_obs, que alimenta gold.dim_tag - o que liga o gasto '
       + N'antigo aos mesmos eixos de viagem e veiculo das origens atuais.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_projeto', @d;

SET @d = N'Coluna Tag da planilha, vazia em todas as linhas. Preservada por fidelidade.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'ds_tag', @d;

SET @d = N'IDENTIDADE DO LANCAMENTO. SHA-256 do ID da planilha. Com constraint UNIQUE: e o '
       + N'banco que impede a duplicacao.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'hash_negocio', @d;
SET @d = N'LINHAGEM: nome do arquivo de onde o lancamento veio.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o lancamento entrou ou foi atualizado na base.';
EXEC dbo.sp_documenta 'bronze', 'financ_historico', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'financ_historico';
GO
