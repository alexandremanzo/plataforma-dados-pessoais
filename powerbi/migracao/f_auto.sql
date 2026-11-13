/* f_auto <- bronze.auto_manutencao
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_auto.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        TRY_CAST(ds_data AS date)                    AS [DATA],
        ds_natureza                                  AS [REVISAO],
        ds_km                                        AS [KM],
        ds_tipo                                      AS [TIPO],
        ds_item                                      AS [ITEM],
        ds_quantidade                                AS [UNID],
        TRY_CAST(ds_valor AS float)                  AS [VALOR],
        ds_local                                     AS [LOCAL],
        ds_observacao                                AS [OBSERVAÇÃO],
        ds_categoria                                 AS [CATEGORIA],
        ds_veiculo                                   AS [CARRO]
FROM bronze.auto_manutencao
