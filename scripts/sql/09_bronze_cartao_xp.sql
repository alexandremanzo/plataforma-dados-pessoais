/* =============================================================
   manzo-dados | 09 - Camada Bronze: cartao de credito XP
   -------------------------------------------------------------
   bronze.cartao_xp

   Gastos detalhados do cartao XP, de 05/2022 em diante. Sao os
   lancamentos FILHO do modelo: o pagamento da fatura, que aparece
   na conta corrente, e o PAI. Somar os dois contaria a mesma
   despesa duas vezes.

   Duas particularidades desta origem:

   1. A METRICA E "Valor Trat", NAO "Valor". Diferente da conta
      corrente, onde as duas colunas sao identicas, aqui "Valor" tem
      sinal inconsistente: em 4.165 das 4.174 linhas "Valor Trat" e o
      negativo de "Valor", mas nos estornos as duas aparecem ora
      positivas, ora com sinais trocados. "Valor Trat" e a unica
      coluna com convencao estavel - negativo e gasto, positivo e
      estorno.

   2. "Data Pgto" IDENTIFICA A FATURA. Sao 61 vencimentos distintos,
      e 11 deles ainda sao futuros: correspondem a parcelas a vencer
      de compras ja realizadas. Nao confunda data da compra com data
      da fatura ao apurar um mes.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.cartao_xp') IS NULL
BEGIN
    CREATE TABLE bronze.cartao_xp (
        id_movimentacao          int IDENTITY(1,1) NOT NULL,

        ds_data                  varchar(50)       NULL,
        ds_descricao             varchar(1000)     NULL,
        ds_parcela               varchar(20)       NULL,
        ds_valor                 varchar(50)       NULL,
        ds_valor_tratado         varchar(50)       NULL,
        ds_tipo_movimentacao     varchar(50)       NULL,

        ds_area                  varchar(100)      NULL,
        ds_categoria             varchar(100)      NULL,
        ds_grupo                 varchar(100)      NULL,
        ds_pessoa_pagar          varchar(100)      NULL,
        ds_pessoa_receber        varchar(200)      NULL,
        ds_forma_pgto            varchar(50)       NULL,
        ds_descricao_pgto        varchar(200)      NULL,

        ds_data_pgto             varchar(50)       NULL,
        ds_status_pgto           varchar(20)       NULL,
        ds_descricao_status_pgto varchar(50)       NULL,

        ds_cidade                varchar(100)      NULL,
        ds_uf                    varchar(20)       NULL,
        ds_pais                  varchar(60)       NULL,
        ds_obs                   varchar(1000)     NULL,

        nr_ocorrencia            int               NOT NULL,
        hash_negocio             char(64)          NOT NULL,
        nm_arquivo_origem        varchar(260)      NOT NULL,
        nm_aba_origem            varchar(120)      NOT NULL,
        nr_linha_arquivo         int               NULL,
        dt_carga                 datetime2(3)      NOT NULL
            CONSTRAINT DF_cartao_xp_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_cartao_xp PRIMARY KEY CLUSTERED (id_movimentacao),
        CONSTRAINT UQ_cartao_xp_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_cartao_xp_data     ON bronze.cartao_xp (ds_data);
    CREATE INDEX IX_cartao_xp_fatura   ON bronze.cartao_xp (ds_data_pgto);
    CREATE INDEX IX_cartao_xp_categoria ON bronze.cartao_xp (ds_categoria);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Gastos detalhados do cartao de credito XP, de maio/2022 em diante, '
       + N'vindos da aba MOVTO de dados-xp-credito.xlsx. Sao os lancamentos ANALITICOS '
       + N'do modelo de movimentacao: cada compra individual. O pagamento da fatura, que '
       + N'aparece na conta corrente como "Cartao de Credito XP", e o lancamento '
       + N'SINTETICO correspondente - somar os dois niveis duplicaria a despesa. '
       + N'Diferente da conta corrente, esta origem ja vem 99,4% classificada.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'id_movimentacao', @d;

SET @d = N'Data da COMPRA, em formato ISO como texto. Nao confundir com a data da fatura: '
       + N'uma compra de julho pode cair na fatura de agosto, e uma compra parcelada '
       + N'aparece em varias faturas.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_data', @d;

SET @d = N'Descricao do gasto. Diferente da conta corrente, aqui e um texto escrito por '
       + N'voce ("Lanche Nina", "Gasolina", "Utensilios casa"), nao o codigo do banco - '
       + N'por isso a classificacao desta origem e muito mais completa.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_descricao', @d;

SET @d = N'Numero da parcela, quando a compra foi parcelada. Preenchido em cerca de 20% '
       + N'dos lancamentos. E o que explica faturas com vencimento futuro.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_parcela', @d;

SET @d = N'Valor bruto como digitado na planilha. ATENCAO: o sinal e inconsistente nesta '
       + N'coluna - ha estornos gravados como positivo e como negativo. NAO USE para '
       + N'calculo; use ds_valor_tratado.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_valor', @d;

SET @d = N'METRICA DA ORIGEM. Valor com sinal consistente: negativo e gasto, positivo e '
       + N'estorno ou credito. E o negativo de ds_valor em 4.165 das 4.174 linhas; nas '
       + N'demais corrige inversoes de sinal feitas na digitacao. E esta a coluna que a '
       + N'silver converte em vl_transacao.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_valor_tratado', @d;

SET @d = N'Natureza do lancamento conforme a planilha: DESPESA ou RECEITA.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_tipo_movimentacao', @d;

SET @d = N'CLASSIFICACAO nivel 1: ESTILO DE VIDA, GASTOS ESSENCIAIS ou TRANSFERENCIA. '
       + N'Preenchida em 99,9% dos lancamentos.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_area', @d;

SET @d = N'CLASSIFICACAO nivel 2, o principal para analise de gastos: ALIMENTACAO, '
       + N'TRANSPORTE, CASA, LAZER e outras - 14 valores. Preenchida em 99,4%.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_categoria', @d;

SET @d = N'CLASSIFICACAO nivel 3, a mais fina: "Combustivel", "Lanche", "Estacionamento" '
       + N'e outros - 321 valores distintos.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_grupo', @d;

SET @d = N'Quem pagou o gasto.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_pessoa_pagar', @d;

SET @d = N'Estabelecimento ou pessoa que recebeu - 1.044 valores distintos. E o campo mais '
       + N'proximo de um cadastro de fornecedores nesta base.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_pessoa_receber', @d;

SET @d = N'Forma de pagamento. Sempre "C" nesta origem, por ser cartao de credito.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_forma_pgto', @d;

SET @d = N'Descricao da forma de pagamento. Sempre "XP Credito" nesta origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_descricao_pgto', @d;

SET @d = N'DATA DE VENCIMENTO DA FATURA em que o gasto foi cobrado. E o campo que agrupa '
       + N'os gastos em faturas: sao 61 vencimentos distintos, dos quais 11 ainda futuros '
       + N'(parcelas a vencer). E tambem a ponte conceitual com o pagamento lancado na '
       + N'conta corrente.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_data_pgto', @d;

SET @d = N'Indicador de fatura paga: S para paga, N para a pagar.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_status_pgto', @d;

SET @d = N'Versao por extenso do status: "Pago" ou "A Pagar". Sao 3.767 itens ja pagos '
       + N'(R$ 273,1 mil) e 402 a pagar (R$ 31,5 mil).';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_descricao_status_pgto', @d;

SET @d = N'Cidade onde o gasto ocorreu. Preenchida em 98,8% - bem melhor que na conta '
       + N'corrente, o que torna esta origem util para analise geografica.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_cidade', @d;

SET @d = N'UF do gasto.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_uf', @d;
SET @d = N'Pais do gasto.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_pais', @d;
SET @d = N'Observacao livre. Usada em 27,7% dos lancamentos, com marcadores como "#AleLia".';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'ds_obs', @d;

SET @d = N'Numero da ocorrencia da mesma combinacao de data, descricao, valor e fatura. '
       + N'Necessario porque o cartao nao tem saldo corrente para desempatar compras '
       + N'identicas - dois lanches iguais no mesmo dia sao dois gastos reais.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'nr_ocorrencia', @d;

SET @d = N'IDENTIDADE DO EVENTO. SHA-256 de data da compra + descricao normalizada + '
       + N'valor tratado + data da fatura + numero da ocorrencia. Com constraint UNIQUE.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'hash_negocio', @d;

SET @d = N'LINHAGEM: arquivo de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'nm_arquivo_origem', @d;
SET @d = N'LINHAGEM: aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'nm_aba_origem', @d;
SET @d = N'LINHAGEM: posicao da linha na aba de origem.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando o evento entrou na base.';
EXEC dbo.sp_documenta 'bronze', 'cartao_xp', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = 'bronze' ORDER BY 1;
GO
