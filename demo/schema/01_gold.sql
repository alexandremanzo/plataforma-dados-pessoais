-- =====================================================================
-- Camada gold da demonstracao: so a estrutura das tabelas que os
-- paineis leem, extraida do schema do projeto. Nenhum dado.
-- As chaves (SK_*) vem prontas do gerador, por isso nao ha IDENTITY.
-- =====================================================================
IF SCHEMA_ID('gold') IS NULL EXEC('CREATE SCHEMA gold');
GO

CREATE TABLE gold.dim_area_financ (
    [SK_AREA_FINANC] int NOT NULL,
    [NM_AREA] varchar(100) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_ativo (
    [SK_ATIVO] int NOT NULL,
    [CD_ATIVO] varchar(200) NOT NULL,
    [NM_ATIVO] varchar(200) NULL,
    [TP_ATIVO] varchar(40) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [DS_CLASSE_ATIVO] varchar(60) NULL,
    [DS_SUBCLASSE_ATIVO] varchar(60) NULL,
    [DS_ORIGEM_CLASSE] varchar(20) NULL,
    [DS_ORIGEM_DADO] varchar(20) NOT NULL
);
GO

CREATE TABLE gold.dim_calendario (
    [SK_DATA] int NOT NULL,
    [DT_DATA] date NOT NULL,
    [NR_ANO] int NOT NULL,
    [NR_MES] int NOT NULL,
    [NM_MES] varchar(20) NOT NULL,
    [NM_MES_ABREV] char(3) NOT NULL,
    [NR_DIA] int NOT NULL,
    [NR_DIA_SEMANA] int NOT NULL,
    [NM_DIA_SEMANA] varchar(20) NOT NULL,
    [NR_TRIMESTRE] int NOT NULL,
    [NR_SEMESTRE] int NOT NULL,
    [NM_ANO_MES] char(7) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_FIM_SEMANA] char(1) NOT NULL,
    [NM_MES_ANO] varchar(20) NULL,
    [NM_DIA_SEMANA_ABREV] varchar(3) NULL,
    [FL_FERIADO] char(1) NOT NULL,
    [NM_FERIADO] varchar(60) NULL,
    [DS_TIPO_FERIADO] varchar(20) NULL
);
GO

CREATE TABLE gold.dim_categoria_auto (
    [SK_CATEGORIA_MANUTENCAO] int NOT NULL,
    [NM_CATEGORIA] varchar(100) NOT NULL,
    [NR_INTERVALO_KM] int NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_TEM_INTERVALO] char(1) NOT NULL
);
GO

CREATE TABLE gold.dim_categoria_financ (
    [SK_CATEGORIA_FINANC] int NOT NULL,
    [NM_CATEGORIA] varchar(100) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_CLASSIFICADO] char(1) NOT NULL
);
GO

CREATE TABLE gold.dim_categoria_investimento (
    [SK_CATEGORIA_INVESTIMENTO] int NOT NULL,
    [NM_CATEGORIA] varchar(100) NOT NULL,
    [DS_GRUPO] varchar(40) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_grupo_financ (
    [SK_GRUPO_FINANC] int NOT NULL,
    [NM_GRUPO] varchar(100) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [DS_COMPRESSIBILIDADE] varchar(20) NULL
);
GO

CREATE TABLE gold.dim_localizacao (
    [SK_LOCALIZACAO] int NOT NULL,
    [NM_CIDADE] varchar(100) NULL,
    [SG_UF] varchar(2) NULL,
    [NM_PAIS] varchar(60) NULL,
    [NM_LOCALIZACAO] varchar(166) NULL,
    [VL_LATITUDE] decimal(9,6) NULL,
    [VL_LONGITUDE] decimal(9,6) NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_metrica_corporal (
    [SK_METRICA] int NOT NULL,
    [NM_METRICA] varchar(100) NOT NULL,
    [DS_GRUPO] varchar(100) NOT NULL,
    [DS_UNIDADE] varchar(20) NULL,
    [DS_SENTIDO_MELHOR] varchar(10) NULL,
    [DS_ERA] varchar(30) NOT NULL,
    [NR_ORDEM] int NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_SERIE_CONTINUA] char(1) NOT NULL
);
GO

CREATE TABLE gold.dim_origem (
    [SK_ORIGEM] int NOT NULL,
    [CD_ORIGEM] varchar(30) NOT NULL,
    [NM_ORIGEM] varchar(100) NOT NULL,
    [NM_INSTITUICAO] varchar(60) NOT NULL,
    [DS_TIPO_CONTA] varchar(40) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_pessoa (
    [SK_PESSOA] int NOT NULL,
    [NM_PESSOA] varchar(100) NOT NULL,
    [DS_TIPO] varchar(30) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_segmento_corporal (
    [SK_SEGMENTO] int NOT NULL,
    [NM_SEGMENTO] varchar(40) NOT NULL,
    [DS_LADO] varchar(20) NULL,
    [DS_REGIAO] varchar(30) NULL,
    [NR_ORDEM] int NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_tag (
    [SK_TAG] int NOT NULL,
    [NM_TAG] varchar(100) NOT NULL,
    [DS_TIPO] varchar(30) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.dim_veiculo (
    [SK_VEICULO] int NOT NULL,
    [NM_VEICULO] varchar(60) NOT NULL,
    [DT_PRIMEIRA] date NULL,
    [DT_ULTIMA] date NULL,
    [NR_KM_ATUAL] int NULL,
    [NR_VISITAS] int NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_ATIVO] char(1) NOT NULL
);
GO

CREATE TABLE gold.dim_habito (
    [SK_HABITO] int NOT NULL,
    [NM_HABITO] varchar(50) NOT NULL,
    [DS_GRUPO] varchar(30) NOT NULL,
    [DS_PERGUNTA] varchar(100) NOT NULL,
    [DS_RESPOSTA_DESEJADA] varchar(10) NULL,
    [NR_ORDEM] int NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [VL_META_MINIMA] decimal(6,2) NULL,
    [DS_UNIDADE] varchar(20) NULL,
    [FL_APURA_ADERENCIA] char(1) NOT NULL
);
GO

CREATE TABLE gold.dim_revisao_programada (
    [SK_REVISAO_PROGRAMADA] int NOT NULL,
    [SK_VEICULO] int NOT NULL,
    [SK_CATEGORIA_MANUTENCAO] int NOT NULL,
    [NM_ITEM] varchar(200) NOT NULL,
    [NM_SISTEMA] varchar(120) NULL,
    [NR_INTERVALO_KM] int NULL,
    [NR_INTERVALO_MESES] int NULL,
    [DS_ACAO] varchar(30) NULL,
    [DS_ESPECIFICACAO] varchar(500) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO

CREATE TABLE gold.fato_avaliacao_fisica (
    [SK_MEDICAO] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_METRICA] int NOT NULL,
    [NR_AVALIACAO] int NOT NULL,
    [VL_MEDIDA] decimal(10,2) NULL,
    [VL_MEDIDA_ANTERIOR] decimal(10,2) NULL,
    [VL_VARIACAO] decimal(10,2) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [SK_SEGMENTO] int NOT NULL,
    [VL_REFERENCIA_MIN] decimal(10,2) NULL,
    [VL_REFERENCIA_MAX] decimal(10,2) NULL,
    [DS_AVALIACAO] varchar(20) NULL,
    [DS_ORIGEM] varchar(20) NOT NULL,
    [FL_MEDIDO] char(1) NOT NULL,
    [FL_MELHOROU] char(1) NULL
);
GO

CREATE TABLE gold.fato_carga (
    [SK_CARGA] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [DT_EXECUCAO] datetime2(3) NOT NULL,
    [DS_CAMADA] varchar(10) NOT NULL,
    [DS_TABELA] varchar(120) NOT NULL,
    [DS_SCRIPT] varchar(120) NULL,
    [NR_INSERIDOS] int NOT NULL,
    [NR_ATUALIZADOS] int NOT NULL,
    [NR_DESCARTADOS] int NULL,
    [NR_TOTAL] int NULL,
    [NR_SEGUNDOS] decimal(8,2) NULL,
    [FL_CONVERGIU] char(1) NOT NULL
);
GO

CREATE TABLE gold.fato_dia (
    [SK_DIA] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [VL_AGUA_LITROS] decimal(5,2) NULL,
    [NR_REFEICOES_FEITAS] int NOT NULL,
    [NR_REFEICOES_JACA] int NOT NULL,
    [NR_HABITOS_ADERENTES] int NOT NULL,
    [NR_HABITOS_APURADOS] int NOT NULL,
    [DS_DIA_PRODUTIVO] varchar(20) NULL,
    [NR_DIAS_ATRASO] int NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_NINA_EM_CASA] char(1) NULL,
    [FL_CARDIO] char(1) NULL,
    [FL_DATA_SUSPEITA] char(1) NOT NULL,
    [FL_ESTRESSE] char(1) NULL,
    [FL_LAZER] char(1) NULL,
    [FL_META_AGUA] char(1) NULL,
    [FL_TRABALHO] char(1) NULL,
    [FL_TREINO] char(1) NULL
);
GO

CREATE TABLE gold.fato_dia_habito (
    [SK_DIA_HABITO] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_HABITO] int NOT NULL,
    [DS_RESPOSTA] varchar(20) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [VL_MEDIDA] decimal(6,2) NULL,
    [FL_ADERENCIA] char(1) NULL,
    [FL_RESPONDIDO] char(1) NOT NULL
);
GO

CREATE TABLE gold.fato_familia (
    [SK_LANCAMENTO] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_DATA_PAGAMENTO] int NOT NULL,
    [SK_PESSOA] int NOT NULL,
    [VL_TRANSACAO] decimal(18,2) NULL,
    [DS_TIPO_FLUXO] varchar(10) NULL,
    [DS_DETALHE_ORIGINAL] varchar(1000) NULL,
    [DS_PESSOA_RECEBER] varchar(200) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [SK_AREA_FINANC] int NOT NULL,
    [SK_CATEGORIA_FINANC] int NOT NULL,
    [SK_GRUPO_FINANC] int NOT NULL,
    [FL_FUTURO] char(1) NOT NULL,
    [FL_PAGO] char(1) NOT NULL,
    [SK_LOCALIZACAO] int NOT NULL,
    [SK_TAG] int NOT NULL
);
GO

CREATE TABLE gold.fato_investimento (
    [SK_LANCAMENTO] int NOT NULL,
    [SK_ORIGEM] int NOT NULL,
    [SK_DATA_MOVIMENTACAO] int NOT NULL,
    [SK_DATA_LIQUIDACAO] int NOT NULL,
    [SK_ATIVO] int NOT NULL,
    [SK_CATEGORIA_INVESTIMENTO] int NOT NULL,
    [VL_TRANSACAO] decimal(18,2) NULL,
    [VL_SALDO_MOMENTO] decimal(18,2) NULL,
    [DS_TIPO_FLUXO] varchar(10) NULL,
    [DS_DETALHE_ORIGINAL] varchar(1000) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_RENDIMENTO] char(1) NOT NULL
);
GO

CREATE TABLE gold.fato_manutencao_auto (
    [SK_MANUTENCAO] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_VEICULO] int NOT NULL,
    [SK_CATEGORIA_MANUTENCAO] int NOT NULL,
    [NR_VISITA] int NOT NULL,
    [NR_KM] int NULL,
    [VL_GASTO] decimal(12,2) NULL,
    [NR_QUANTIDADE] decimal(10,2) NULL,
    [DS_TIPO] varchar(30) NULL,
    [DS_ITEM] varchar(200) NULL,
    [DS_LOCAL] varchar(120) NULL,
    [DS_OBSERVACAO] varchar(500) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [FL_PREVENTIVA] char(1) NOT NULL
);
GO

CREATE TABLE gold.fato_movto_financ (
    [SK_MOVIMENTACAO] int NOT NULL,
    [SK_ORIGEM] int NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_DATA_FATURA] int NOT NULL,
    [VL_TRANSACAO] decimal(18,2) NULL,
    [DS_NIVEL] varchar(12) NOT NULL,
    [DS_TIPO_FLUXO] varchar(10) NULL,
    [NR_PARCELA] int NULL,
    [DS_DETALHE_ORIGINAL] varchar(1000) NULL,
    [DS_PESSOA_PAGAR] varchar(100) NULL,
    [DS_PESSOA_RECEBER] varchar(200) NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL,
    [SK_AREA_FINANC] int NOT NULL,
    [SK_CATEGORIA_FINANC] int NOT NULL,
    [SK_GRUPO_FINANC] int NOT NULL,
    [SK_LOCALIZACAO] int NOT NULL,
    [SK_TAG] int NOT NULL
);
GO

CREATE TABLE gold.fato_posicao_investimento (
    [SK_POSICAO] bigint NOT NULL,
    [SK_DATA] int NOT NULL,
    [SK_ORIGEM] int NOT NULL,
    [SK_ATIVO] int NOT NULL,
    [CD_ATIVO_ORIGEM] varchar(60) NULL,
    [NM_ATIVO_ORIGEM] varchar(300) NOT NULL,
    [DS_TIPO] varchar(40) NOT NULL,
    [DS_SUBTIPO] varchar(60) NULL,
    [DS_SITUACAO] varchar(30) NULL,
    [QT_COTAS] decimal(24,8) NULL,
    [VL_COTA] decimal(24,8) NULL,
    [VL_BRUTO] decimal(18,2) NULL,
    [VL_LIQUIDO] decimal(18,2) NULL,
    [VL_RESGATAVEL] decimal(18,2) NULL,
    [VL_APLICADO] decimal(18,2) NULL,
    [VL_TAXAS] decimal(18,2) NULL,
    [DT_REFERENCIA] date NULL,
    [DT_VENCIMENTO] date NULL,
    [HASH_NEGOCIO] char(64) NOT NULL,
    [DT_CARGA] datetime2(3) NOT NULL
);
GO
