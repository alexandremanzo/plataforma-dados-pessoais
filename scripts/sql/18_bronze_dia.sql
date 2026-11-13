/* =============================================================
   manzo-dados | 18 - Camada Bronze: meu dia
   -------------------------------------------------------------
   bronze.dia_registro

   Diario de habitos. Um formulario do Google, respondido quase
   todo dia desde janeiro de 2024, com perguntas de sim/nao sobre
   treino, alimentacao, trabalho e relacionamento, mais o consumo
   de agua em litros.

   Segunda origem que nao e arquivo: le a aba de respostas do
   Forms publicada como CSV, o mesmo caminho da conta familia.

   O QUE DIFERENCIA ESTA ORIGEM DAS FINANCEIRAS:

   1. O GRAO E O DIA, NAO O EVENTO. As outras bases registram
      transacoes - varias por dia, cada uma um fato novo. Aqui
      cada linha e um retrato de um dia inteiro. Duas linhas para
      a mesma data seriam erro, nao dois acontecimentos.

   2. A CHAVE E O CARIMBO DO FORMULARIO, e nao a data relatada.
      O carimbo e atribuido pelo Google no envio, e unico nas 888
      respostas e nunca muda. A data e digitada a mao e pode estar
      errada - ha duas respostas com 31/12/1900 e 08/08/3025.
      Se a chave fosse a data, corrigir o erro criaria uma linha
      nova e deixaria a errada orfa; sendo o carimbo, a correcao
      chega como atualizacao.

   3. NAO HA VALOR MONETARIO. A unica medida numerica e o consumo
      de agua. O resto sao respostas categoricas.

   Pre-requisitos: 00_utilitarios.sql, 01_cria_camadas.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID('bronze.dia_registro') IS NULL
BEGIN
    CREATE TABLE bronze.dia_registro (
        id_registro       int IDENTITY(1,1) NOT NULL,

        ds_carimbo        varchar(50)  NOT NULL,
        ds_data           varchar(50)  NULL,

        ds_treino         varchar(20)  NULL,
        ds_cardio         varchar(20)  NULL,
        ds_agua_litros    varchar(20)  NULL,

        ds_cafe_manha     varchar(20)  NULL,
        ds_almoco         varchar(20)  NULL,
        ds_lanche         varchar(20)  NULL,
        ds_janta          varchar(20)  NULL,
        ds_ceia           varchar(20)  NULL,

        ds_dia_produtivo  varchar(20)  NULL,
        ds_trabalho       varchar(20)  NULL,
        ds_nina_em_casa    varchar(20)  NULL,
        ds_estresse          varchar(20)  NULL,
        ds_lazer         varchar(20)  NULL,

        hash_negocio      char(64)     NOT NULL,
        nm_origem         varchar(120) NOT NULL,
        nr_linha_arquivo  int          NULL,
        dt_carga          datetime2(3) NOT NULL
            CONSTRAINT DF_dia_registro_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_dia_registro PRIMARY KEY CLUSTERED (id_registro),
        CONSTRAINT UQ_dia_registro_hash UNIQUE (hash_negocio)
    );

    CREATE INDEX IX_dia_registro_data ON bronze.dia_registro (ds_data);
END
GO

DECLARE @d nvarchar(3750);

SET @d = N'BRONZE | Diario de habitos, uma linha por dia. Vem de um formulario do Google '
       + N'respondido quase diariamente desde janeiro de 2024, lido pela aba de respostas '
       + N'publicada como CSV. E a segunda origem do projeto que nao e arquivo. '
       + N'DIFERENTE DAS DEMAIS BASES, aqui nao ha dinheiro nem transacao: o grao e o dia '
       + N'inteiro, e as colunas sao respostas de formulario. Por isso a base vive em '
       + N'gold.fato_dia, sem nenhuma relacao com os fatos financeiros - o unico eixo que '
       + N'compartilham e o calendario, o que permite cruzar habito e gasto pela mesma data.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', NULL, @d;

SET @d = N'Chave tecnica sequencial, sem significado de negocio.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'id_registro', @d;

SET @d = N'CHAVE DE NEGOCIO. Momento em que o formulario foi enviado, atribuido pelo '
       + N'Google. E unico e imutavel, por isso identifica a resposta melhor que a data '
       + N'relatada, que e digitada a mao e pode ser corrigida depois. Na pratica o '
       + N'formulario e respondido na manha seguinte: a mediana de atraso e um dia.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_carimbo', @d;

SET @d = N'Dia a que a resposta se refere, em formato ISO como texto. A origem entrega no '
       + N'formato brasileiro (14/08/2026) e a carga converte, porque o CSV nao carrega '
       + N'tipo. ATENCAO: e digitada a mao e ha erros de digitacao - duas respostas trazem '
       + N'anos impossiveis (1900 e 3025). A silver marca esses casos em fl_data_suspeita.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_data', @d;

SET @d = N'Treino de musculacao no dia: Sim ou Nao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_treino', @d;

SET @d = N'Cardio no dia: Sim ou Nao. ATENCAO: a opcao do formulario foi reescrita em 2024 '
       + N'e o negativo convive em duas grafias, "Nao" e "Nao" com til. Sem unificar, o '
       + N'mesmo habito apareceria como tres respostas distintas.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_cardio', @d;

SET @d = N'UNICA MEDIDA NUMERICA da base: litros de agua no dia, entre 0,3 e 3,1. Chega no '
       + N'formato brasileiro, com virgula decimal.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_agua_litros', @d;

SET @d = N'Cafe da manha. TRES ESTADOS, e nao dois: Sim, Nao e Jaca - esta ultima indicando '
       + N'refeicao feita fora do plano alimentar. Tratar Jaca como Nao esconderia a '
       + N'diferenca entre pular a refeicao e sair da dieta.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_cafe_manha', @d;

SET @d = N'Almoco: Sim, Nao ou Jaca (fora do plano alimentar).';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_almoco', @d;
SET @d = N'Lanche: Sim, Nao ou Jaca (fora do plano alimentar).';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_lanche', @d;
SET @d = N'Janta: Sim, Nao ou Jaca. E a refeicao que mais sai do plano - quase metade das '
       + N'respostas.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_janta', @d;
SET @d = N'Ceia: Sim, Nao ou Jaca. E a refeicao mais frequentemente pulada.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_ceia', @d;

SET @d = N'Avaliacao do dia: Normal, Sim ou Nao. NAO E BOOLEANO - Normal e a resposta '
       + N'padrao e responde por oito de cada dez dias; Sim significa dia acima da media.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_dia_produtivo', @d;

SET @d = N'Houve trabalho no dia: Sim ou Nao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_trabalho', @d;
SET @d = N'A filha esteve em casa no dia: Sim ou Nao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_nina_em_casa', @d;
SET @d = N'Houve discussao no dia: Sim ou Nao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_estresse', @d;
SET @d = N'Houve momento a dois no dia: Sim ou Nao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'ds_lazer', @d;

SET @d = N'IDENTIDADE DA RESPOSTA. SHA-256 do carimbo do formulario. Diferente das demais '
       + N'bronzes, que combinam data, descricao e valor: aqui a origem ja fornece um '
       + N'identificador unico e estavel, entao usar qualquer outro campo so introduziria '
       + N'fragilidade. Com constraint UNIQUE: e o banco que impede a duplicacao.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'hash_negocio', @d;

SET @d = N'LINHAGEM: identifica a origem do dado - a aba de respostas do formulario '
       + N'publicada como CSV, e nao um arquivo.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'nm_origem', @d;
SET @d = N'LINHAGEM: posicao da linha no CSV, a partir de 1 apos o cabecalho.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'nr_linha_arquivo', @d;
SET @d = N'LINHAGEM: quando a resposta entrou ou foi atualizada na base.';
EXEC dbo.sp_documenta 'bronze', 'dia_registro', 'dt_carga', @d;
GO

SELECT s.name + '.' + t.name AS tabela,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = t.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.name = 'dia_registro';
GO
