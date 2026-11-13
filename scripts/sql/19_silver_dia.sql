/* =============================================================
   manzo-dados | 19 - Camada Silver: meu dia
   -------------------------------------------------------------
   silver.dia_registro

   Tipagem e padronizacao do diario de habitos. Uma linha por dia.

   O QUE ESTA CAMADA RESOLVE:

   - GRAFIA. O negativo do cardio convive como "Nao" e "Nao" com
     til, porque a opcao do formulario foi reescrita no meio de
     2024. Sem unificar, o mesmo habito viraria tres respostas.

   - TRES ESTADOS NAS REFEICOES. Sim, Nao e Jaca - a ultima
     indicando refeicao feita fora do plano alimentar. Reduzir a
     um booleano perderia a distincao entre pular a refeicao e
     sair da dieta, que sao coisas opostas. Por isso as refeicoes
     viram texto padronizado, e nao bit, e ganham dois contadores
     derivados.

   - DATA IMPLAUSIVEL. Duas respostas trazem anos impossiveis,
     erro de digitacao no formulario. FL_DATA_SUSPEITA as marca em
     vez de descarta-las: o resto da resposta e valido, e apagar
     dado bom por causa de um campo errado e pior que sinalizar.

   Pre-requisitos: 00, 01, 18
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('silver.dia_registro') IS NULL
BEGIN
    CREATE TABLE silver.dia_registro (
        sk_registro        int IDENTITY(1,1) NOT NULL,

        dt_referencia      date          NULL,
        dt_resposta        datetime2(0)  NULL,
        nr_dias_atraso     int           NULL,
        fl_data_suspeita   bit           NOT NULL,

        fl_treino          bit           NULL,
        fl_cardio          bit           NULL,
        vl_agua_litros     decimal(5,2)  NULL,

        ds_cafe_manha      varchar(20)   NULL,
        ds_almoco          varchar(20)   NULL,
        ds_lanche          varchar(20)   NULL,
        ds_janta           varchar(20)   NULL,
        ds_ceia            varchar(20)   NULL,
        nr_refeicoes_feitas int          NOT NULL,
        nr_refeicoes_jaca  int           NOT NULL,

        ds_dia_produtivo   varchar(20)   NULL,
        fl_trabalho        bit           NULL,
        fl_nina_em_casa     bit           NULL,
        fl_estresse           bit           NULL,
        fl_lazer          bit           NULL,

        hash_negocio       char(64)      NOT NULL,
        dt_carga           datetime2(3)  NOT NULL
            CONSTRAINT DF_silver_dia_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_silver_dia PRIMARY KEY CLUSTERED (sk_registro),
        CONSTRAINT UQ_silver_dia_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_silver_dia_data ON silver.dia_registro (dt_referencia);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'SILVER | Diario de habitos, limpo e tipado. Uma linha por dia respondido. '
       + N'As perguntas de sim/nao viram bit, as refeicoes continuam texto porque tem tres '
       + N'estados, e o consumo de agua vira decimal. Origem: aba de respostas de um '
       + N'formulario do Google publicada como CSV. Alimenta gold.fato_dia e '
       + N'gold.fato_dia_habito.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', NULL, @d;

SET @d = N'Chave substituta do registro. A identidade estavel e hash_negocio.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'sk_registro', @d;

SET @d = N'DIA A QUE A RESPOSTA SE REFERE - o eixo temporal da analise. Digitada a mao no '
       + N'formulario, por isso sujeita a erro: quando o ano e implausivel, '
       + N'fl_data_suspeita marca 1 e a data segue como esta, sem correcao automatica.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'dt_referencia', @d;

SET @d = N'Momento do envio do formulario, atribuido pelo Google. E a chave de negocio da '
       + N'origem. Nao confundir com dt_referencia: o formulario e respondido depois do '
       + N'dia que descreve.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'dt_resposta', @d;

SET @d = N'Dias entre o dia relatado e o envio da resposta. Normalmente 1, porque o '
       + N'formulario e preenchido na manha seguinte. Valores altos indicam resposta '
       + N'preenchida de memoria dias depois, o que reduz a confiabilidade do registro.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'nr_dias_atraso', @d;

SET @d = N'ALERTA DE QUALIDADE. Marca 1 quando dt_referencia esta fora da faixa plausivel '
       + N'(antes de 2020 ou depois de amanha) ou quando falta. Sao erros de digitacao no '
       + N'formulario, nao dados reais. A linha e mantida porque o resto da resposta e '
       + N'valido; na gold esses registros apontam para a data "Nao informado".';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_data_suspeita', @d;

SET @d = N'1 quando houve treino de musculacao no dia.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_treino', @d;
SET @d = N'1 quando houve cardio no dia. A origem trazia o negativo em duas grafias, com e '
       + N'sem til, por mudanca na opcao do formulario - aqui ja esta unificado.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_cardio', @d;

SET @d = N'METRICA. Litros de agua consumidos no dia, entre 0,3 e 3,1. E a unica medida '
       + N'numerica da base e a unica coluna que faz sentido somar ou tirar media.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'vl_agua_litros', @d;

SET @d = N'Cafe da manha: SIM, NAO ou JACA. Mantido como texto, e nao bit, porque sao tres '
       + N'estados: JACA e refeicao feita fora do plano alimentar, situacao diferente de '
       + N'pular a refeicao.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_cafe_manha', @d;
SET @d = N'Almoco: SIM, NAO ou JACA (fora do plano alimentar).';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_almoco', @d;
SET @d = N'Lanche: SIM, NAO ou JACA (fora do plano alimentar).';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_lanche', @d;
SET @d = N'Janta: SIM, NAO ou JACA. E a refeicao que mais sai do plano.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_janta', @d;
SET @d = N'Ceia: SIM, NAO ou JACA. E a refeicao mais frequentemente pulada.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_ceia', @d;

SET @d = N'DERIVADA. Quantas das cinco refeicoes foram feitas dentro do plano, de 0 a 5. '
       + N'Conta apenas SIM.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'nr_refeicoes_feitas', @d;
SET @d = N'DERIVADA. Quantas das cinco refeicoes sairam do plano alimentar, de 0 a 5. E o '
       + N'indicador de aderencia a dieta: a media fica em torno de 0,6 por dia, e cerca '
       + N'de metade dos dias tem ao menos uma.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'nr_refeicoes_jaca', @d;

SET @d = N'Avaliacao do dia: NORMAL, SIM ou NAO. NAO E BOOLEANO - NORMAL e a resposta '
       + N'padrao e cobre oito de cada dez dias, entao contar "diferente de SIM" como dia '
       + N'improdutivo distorceria a leitura.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'ds_dia_produtivo', @d;

SET @d = N'1 quando houve trabalho no dia.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_trabalho', @d;
SET @d = N'1 quando a filha esteve em casa no dia.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_nina_em_casa', @d;
SET @d = N'1 quando houve discussao no dia.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_estresse', @d;
SET @d = N'1 quando houve momento a dois no dia.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'fl_lazer', @d;

SET @d = N'Identidade da resposta, herdada da bronze: hash do carimbo do formulario.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'hash_negocio', @d;
SET @d = N'LINHAGEM: quando o registro foi processado para a silver.';
EXEC dbo.sp_documenta 'silver', 'dia_registro', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'dia_registro' ORDER BY 1;
GO
