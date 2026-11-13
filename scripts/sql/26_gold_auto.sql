/* =============================================================
   manzo-dados | 26 - Camada Gold: manutencao do automovel
   -------------------------------------------------------------
   gold.dim_veiculo + gold.dim_categoria_auto
   gold.fato_manutencao_auto

   O historico da oficina, pronto para o Power BI - e virado para
   a frente.

   A VIEW E O QUE DA VALOR A BASE. O historico sozinho responde
   "quanto ja gastei"; cruzado com o intervalo de troca de cada
   item e com a quilometragem atual de cada veiculo, responde
   "o que esta vencendo agora". E a diferenca entre um arquivo e um
   alerta. Ela fica em 39_gold_revisao.sql (ver secao 3).

   POR QUE UMA DIMENSAO DE VEICULO. Dois carros com hodometros
   independentes - Sedan ate novembro de 2025, SUV desde entao.
   Sem separar, a quilometragem do SUV (100 mil) pareceria um
   retrocesso em relacao ao Sedan (158 mil), e qualquer previsao
   de troca sairia errada.

   NAO SE LIGA AO FATO FINANCEIRO. Estes gastos podem ate aparecer
   no cartao, mas aqui o assunto e o veiculo e nao o dinheiro: o
   grao e o item da nota da oficina, com quilometragem. Somar os
   dois contaria o mesmo gasto duas vezes.

   Pre-requisitos: 00, 01, 04 (calendario), 25
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Dimensoes
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.dim_veiculo') IS NULL
BEGIN
    CREATE TABLE gold.dim_veiculo (
        SK_VEICULO      int IDENTITY(1,1) NOT NULL,
        NM_VEICULO      varchar(60)  NOT NULL,
        DT_PRIMEIRA     date         NULL,
        DT_ULTIMA       date         NULL,
        NR_KM_ATUAL     int          NULL,
        NR_VISITAS      int          NULL,
        FL_ATIVO        bit          NOT NULL,
        DT_CARGA        datetime2(3) NOT NULL
            CONSTRAINT DF_dim_veiculo_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_veiculo PRIMARY KEY (SK_VEICULO),
        CONSTRAINT UQ_dim_veiculo_nome UNIQUE (NM_VEICULO)
    );

    SET IDENTITY_INSERT gold.dim_veiculo ON;
    INSERT INTO gold.dim_veiculo (SK_VEICULO, NM_VEICULO, FL_ATIVO)
    VALUES (-1, 'Não informado', 0);
    SET IDENTITY_INSERT gold.dim_veiculo OFF;
END
GO

IF OBJECT_ID('gold.dim_categoria_auto') IS NULL
BEGIN
    CREATE TABLE gold.dim_categoria_auto (
        SK_CATEGORIA_MANUTENCAO int IDENTITY(1,1) NOT NULL,
        NM_CATEGORIA            varchar(100) NOT NULL,
        NR_INTERVALO_KM         int          NULL,
        FL_TEM_INTERVALO        bit          NOT NULL,
        DT_CARGA                datetime2(3) NOT NULL
            CONSTRAINT DF_dim_cat_auto_dt DEFAULT (SYSDATETIME()),
        CONSTRAINT PK_dim_categoria_auto PRIMARY KEY (SK_CATEGORIA_MANUTENCAO),
        CONSTRAINT UQ_dim_categoria_auto UNIQUE (NM_CATEGORIA)
    );

    SET IDENTITY_INSERT gold.dim_categoria_auto ON;
    INSERT INTO gold.dim_categoria_auto
        (SK_CATEGORIA_MANUTENCAO, NM_CATEGORIA, NR_INTERVALO_KM, FL_TEM_INTERVALO)
    VALUES (-1, 'Não informado', NULL, 0);
    SET IDENTITY_INSERT gold.dim_categoria_auto OFF;
END
GO


/* -------------------------------------------------------------
   2. Fato
   ------------------------------------------------------------- */

IF OBJECT_ID('gold.fato_manutencao_auto') IS NULL
BEGIN
    CREATE TABLE gold.fato_manutencao_auto (
        SK_MANUTENCAO           int IDENTITY(1,1) NOT NULL,

        SK_DATA                 int           NOT NULL,
        SK_VEICULO              int           NOT NULL,
        SK_CATEGORIA_MANUTENCAO int           NOT NULL,
        NR_VISITA               int           NOT NULL,

        NR_KM                   int           NULL,
        VL_GASTO                decimal(12,2) NULL,
        NR_QUANTIDADE           decimal(10,2) NULL,
        FL_PREVENTIVA           bit           NOT NULL,
        DS_TIPO                 varchar(30)   NULL,

        DS_ITEM                 varchar(200)  NULL,
        DS_LOCAL                varchar(120)  NULL,
        DS_OBSERVACAO           varchar(500)  NULL,

        HASH_NEGOCIO            char(64)      NOT NULL,
        DT_CARGA                datetime2(3)  NOT NULL
            CONSTRAINT DF_fato_manut_auto_dt DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_fato_manutencao_auto PRIMARY KEY (SK_MANUTENCAO),
        CONSTRAINT UQ_fato_manutencao_auto_hash UNIQUE (HASH_NEGOCIO),
        CONSTRAINT FK_fato_auto_data     FOREIGN KEY (SK_DATA)
            REFERENCES gold.dim_calendario (SK_DATA),
        CONSTRAINT FK_fato_auto_veiculo  FOREIGN KEY (SK_VEICULO)
            REFERENCES gold.dim_veiculo (SK_VEICULO),
        CONSTRAINT FK_fato_auto_categoria FOREIGN KEY (SK_CATEGORIA_MANUTENCAO)
            REFERENCES gold.dim_categoria_auto (SK_CATEGORIA_MANUTENCAO)
    );

    CREATE INDEX IX_fato_auto_data      ON gold.fato_manutencao_auto (SK_DATA);
    CREATE INDEX IX_fato_auto_veiculo   ON gold.fato_manutencao_auto (SK_VEICULO);
    CREATE INDEX IX_fato_auto_categoria ON gold.fato_manutencao_auto (SK_CATEGORIA_MANUTENCAO);
END
GO


/* -------------------------------------------------------------
   3. A view que olha para a frente: gold.vw_manutencao_prevista

   NAO E CRIADA AQUI. Ela nasceu neste script so com quilometragem
   e foi refeita em 39_gold_revisao.sql, com o plano do fabricante
   (km E meses, o que vencer primeiro). Enquanto a versao antiga
   ficava aqui, rodar este script sozinho depois do 39 desfazia a
   nova sem aviso - e o alerta voltava a dizer "Em dia" para tudo.
   ------------------------------------------------------------- */


/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Os veiculos cujo historico de manutencao a base guarda: Sedan, de 2016 a '
       + N'novembro de 2025, e SUV desde entao. Existe porque CADA UM TEM SEU PROPRIO '
       + N'HODOMETRO - sem separar, os 100 mil km do SUV pareceriam um retrocesso diante '
       + N'dos 158 mil do Sedan, e toda previsao de troca sairia errada.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', NULL, @d;
SET @d = N'Chave substituta do veiculo. -1 representa veiculo nao identificado.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'SK_VEICULO', @d;
SET @d = N'Nome do veiculo, como registrado na planilha.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'NM_VEICULO', @d;
SET @d = N'Data da primeira manutencao registrada para este veiculo.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'DT_PRIMEIRA', @d;
SET @d = N'Data da manutencao mais recente deste veiculo.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'DT_ULTIMA', @d;
SET @d = N'Maior quilometragem ja registrada para este veiculo - a melhor estimativa da '
       + N'atual. DERIVADA DO HISTORICO, e nao da aba "Quilometragem" da planilha, que '
       + N'guarda um numero solto de 2025 que nao corresponde a nenhum dos dois carros. '
       + N'E o denominador de toda previsao de troca, entao so fica correta se o hodometro '
       + N'for anotado a cada visita.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'NR_KM_ATUAL', @d;
SET @d = N'Quantas idas a oficina este veiculo teve.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'NR_VISITAS', @d;
SET @d = N'S no veiculo em uso. INFERIDO: e o que tem a manutencao mais recente, porque a '
       + N'planilha nao registra compra nem venda. Se dois carros passarem a ser mantidos '
       + N'ao mesmo tempo, esta regra precisa mudar.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'FL_ATIVO', @d;
SET @d = N'LINHAGEM: quando o registro entrou ou foi atualizado na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_veiculo', 'DT_CARGA', @d;

SET @d = N'GOLD | As 34 categorias de manutencao, com o intervalo de troca de cada uma. O '
       + N'intervalo vem da aba "Tempo Troca" da planilha e existe em 13 delas; as outras '
       + N'21 sao corretivas - nao se troca bandeja, lampada ou mao de obra por '
       + N'quilometragem, entao o nulo ali e a resposta certa e nao um cadastro faltando.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', NULL, @d;
SET @d = N'Chave substituta da categoria. -1 representa categoria nao identificada.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', 'SK_CATEGORIA_MANUTENCAO', @d;
SET @d = N'Nome da categoria, com a grafia unificada.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', 'NM_CATEGORIA', @d;
SET @d = N'Quilometros recomendados entre trocas: 5.000 para oleo, 10.000 para filtro, '
       + N'50.000 para amortecedor. Nulo nas categorias corretivas. Alimenta '
       + N'gold.vw_manutencao_prevista.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', 'NR_INTERVALO_KM', @d;
SET @d = N'S quando a categoria tem troca prevista por quilometragem e portanto entra na '
       + N'previsao de vencimento.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', 'FL_TEM_INTERVALO', @d;
SET @d = N'LINHAGEM: quando o registro entrou ou foi atualizado na dimensao.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_auto', 'DT_CARGA', @d;

SET @d = N'GOLD | Revisoes e manutencoes do automovel, uma linha por item de cada visita a '
       + N'oficina. Sao dez anos de historico em dois veiculos. '
       + N'NAO SE MISTURA COM O FATO FINANCEIRO: parte destes gastos aparece tambem na '
       + N'fatura do cartao, e somar os dois contaria a mesma despesa duas vezes. Aqui o '
       + N'assunto e o veiculo - o que foi trocado, com que quilometragem - e nao o '
       + N'dinheiro. O unico eixo compartilhado com as demais bases e o calendario.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', NULL, @d;

SET @d = N'Chave substituta do lancamento.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'SK_MANUTENCAO', @d;
SET @d = N'Chave para gold.dim_calendario, na data da visita a oficina.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'SK_DATA', @d;
SET @d = N'Chave para gold.dim_veiculo: qual carro.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'SK_VEICULO', @d;
SET @d = N'Chave para gold.dim_categoria_auto: o que foi feito.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'SK_CATEGORIA_MANUTENCAO', @d;
SET @d = N'Numero sequencial da visita a oficina, por veiculo. Agrupe por ele para somar o '
       + N'custo de uma revisao inteira, que se espalha por varias linhas.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'NR_VISITA', @d;
SET @d = N'Quilometragem do veiculo na data. NAO COMPARE ENTRE VEICULOS: cada um tem sua '
       + N'propria escala, e o carro mais novo tem hodometro menor.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'NR_KM', @d;
SET @d = N'METRICA. Valor pago em reais, total do item. Sempre positivo - e sempre despesa, '
       + N'entao nao carrega sinal como os fatos financeiros. Aditiva.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'VL_GASTO', @d;
SET @d = N'Quantidade de unidades do item.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'NR_QUANTIDADE', @d;
SET @d = N'S quando foi revisao programada, N quando foi conserto. A proporcao entre os '
       + N'dois diz se a manutencao esta sendo preventiva ou apenas reagindo a quebra.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'FL_PREVENTIVA', @d;
SET @d = N'Produto (peca) ou Serviço (mao de obra). Permite separar quanto foi peca e '
       + N'quanto foi trabalho numa mesma nota.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'DS_TIPO', @d;
SET @d = N'Descricao do item, como escrita na nota. Atributo do fato, e nao dimensao, por '
       + N'ter 110 variacoes de texto livre.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'DS_ITEM', @d;
SET @d = N'Oficina ou loja onde foi feito.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'DS_LOCAL', @d;
SET @d = N'Observacao livre da origem.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'DS_OBSERVACAO', @d;
SET @d = N'Identidade do evento, herdada da silver.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'HASH_NEGOCIO', @d;
SET @d = N'LINHAGEM: quando o lancamento foi carregado na gold.';
EXEC dbo.sp_documenta 'gold', 'fato_manutencao_auto', 'DT_CARGA', @d;
GO

SELECT s.name + '.' + o.name AS objeto,
       (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = o.object_id) AS colunas,
       (SELECT COUNT(*) FROM sys.extended_properties ep
         WHERE ep.class = 1 AND ep.major_id = o.object_id
           AND ep.minor_id > 0 AND ep.name = 'MS_Description') AS documentadas
FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE o.name IN ('dim_veiculo', 'dim_categoria_auto',
                 'fato_manutencao_auto')
ORDER BY 1;
GO
