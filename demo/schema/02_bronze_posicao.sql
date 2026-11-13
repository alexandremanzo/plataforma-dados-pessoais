-- =====================================================================
-- Recorte minimo do bronze que o painel de investimentos le: a taxa
-- contratada e a rentabilidade de 12 meses de cada posicao so existem
-- na resposta crua da corretora. A ligacao com o gold e o HASH_NEGOCIO.
-- =====================================================================
IF SCHEMA_ID('bronze') IS NULL EXEC('CREATE SCHEMA bronze');
GO

CREATE TABLE bronze.xp_posicao (
    hash_negocio  char(64)      NOT NULL,
    vl_taxa       decimal(9,4)  NULL,
    ds_tipo_taxa  varchar(40)   NULL,
    vl_rentab_12m decimal(9,4)  NULL
);
GO
