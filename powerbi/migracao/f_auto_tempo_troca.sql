/* f_auto_tempo_troca <- bronze.auto_intervalo_troca
   Gerado por gerar_consultas.py a partir do de-para de carga_bronze_auto.py.
   Migracao FIEL: a bronze e a copia sem transformacao da planilha,
   entao nenhum numero do relatorio muda. */

SELECT
        ds_categoria                                 AS [CATEGORIA],
        TRY_CAST(ds_intervalo_km AS bigint)          AS [Tempo Util KM]
FROM bronze.auto_intervalo_troca
