/* f_avaliacao_fisica <- bronze.avaliacao_fisica
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_avaliacao.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        TRY_CAST(ds_data AS date)                    AS [DATA],
        ds_grupo                                     AS [GRUPO],
        ds_item                                      AS [ITEM],
        ds_medida                                    AS [MEDIDA],
        TRY_CAST(ds_valor AS float)                  AS [VALOR],
        ds_classe                                    AS [CLASSE]
FROM bronze.avaliacao_fisica
