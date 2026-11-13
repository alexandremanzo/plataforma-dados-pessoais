/* f_dados_credito_xp <- bronze.cartao_xp
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_cartao_xp.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        TRY_CAST(ds_data AS date)                    AS [Data],
        ds_descricao                                 AS [Descrição],
        ds_parcela                                   AS [Parcela],
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
        ds_descricao_status_pgto                     AS [Descrição Status Pgto],
        ds_id_origem                                 AS [ID]
FROM bronze.cartao_xp
