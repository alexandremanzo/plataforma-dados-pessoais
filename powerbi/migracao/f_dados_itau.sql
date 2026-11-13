/* f_dados_itau <- bronze.itau_movimentacao
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_itau.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        TRY_CAST(ds_data AS date)                    AS [Data],
        ds_descricao                                 AS [Descrição],
        TRY_CAST(ds_valor AS float)                  AS [Valor],
        TRY_CAST(ds_valor_tratado AS float)          AS [Valor Trat],
        ds_tipo_movimentacao                         AS [Tipo Movimentação],
        ds_area                                      AS [Área],
        ds_categoria                                 AS [Categoria],
        ds_grupo                                     AS [Grupo],
        ds_pessoa_pagar                              AS [Pessoa Pagar],
        ds_pessoa_receber                            AS [Pessoa Receber],
        ds_forma_pgto                                AS [Forma Pgto],
        ds_descricao_pgto                            AS [Descrição Pagto],
        TRY_CAST(ds_data_pgto AS date)               AS [Data Pgto],
        ds_status_pgto                               AS [Status Pgto],
        ds_cidade                                    AS [Cidade],
        ds_uf                                        AS [UF],
        ds_pais                                      AS [País],
        ds_obs                                       AS [OBS],
        ds_projeto                                   AS [Projeto],
        ds_tag                                       AS [Tag],
        ds_id_origem                                 AS [ID]
FROM bronze.itau_movimentacao
