/* f_dados_credito_nubank <- bronze.cartao_nubank
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_cartao_nubank.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        TRY_CAST(ds_data AS date)                    AS [date],
        ds_categoria_nubank                          AS [category],
        TRY_CAST(ds_valor AS float)                  AS [Valor],
        TRY_CAST(ds_data_fatura AS date)             AS [Data Pagamento],
        ds_arquivo_fatura                            AS [Arquivo],
        fl_extrato                                   AS [Extrato],
        fl_rewards                                   AS [Rewards],
        ds_tipo_movimentacao                         AS [Tipo Movimentação],
        ds_area                                      AS [Área],
        ds_categoria                                 AS [Categoria],
        ds_grupo                                     AS [Grupo],
        ds_pessoa_pagar                              AS [Pessoa Pagar],
        ds_pessoa_receber                            AS [Pessoa Receber],
        ds_cidade                                    AS [Cidade],
        ds_uf                                        AS [UF],
        ds_pais                                      AS [País],
        ds_obs                                       AS [OBS],
        ds_projeto                                   AS [Projeto],
        ds_tag                                       AS [Tag],
        ds_titulo                                    AS [title],
        CAST(NULL AS varchar(1))                     AS [amount]   /* a carga guardou so o valor tratado; o bruto do CSV nao entrou */
FROM bronze.cartao_nubank
