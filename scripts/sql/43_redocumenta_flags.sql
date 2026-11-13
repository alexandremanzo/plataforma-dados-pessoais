USE [db-manzo];
GO
SET NOCOUNT ON;
GO

/* =============================================================
   manzo-dados | 43 - Redocumenta as duas flags que a conversao
   -------------------------------------------------------------
   O script 42 trocou as colunas FL_ de bit para char(1), e trocar
   uma coluna apaga a extended property junto. As demais voltaram ao
   reaplicar os scripts que as criaram; estas duas nasceram em
   scripts com passos nao repetiveis, entao vem daqui.

   As descricoes ja consideram o dominio S/N.
   Idempotente.
   ============================================================= */

DECLARE @d nvarchar(3750);

SET @d = N'S quando a categoria e uma classificacao de verdade, N no membro "A classificar", '
       + N'que existe para MEDIR O QUE FALTA em vez de esconder. Contar os lancamentos com N '
       + N'da o tamanho do trabalho pendente - hoje 36% dos analiticos.';
EXEC dbo.sp_documenta 'gold', 'dim_categoria_financ', 'FL_CLASSIFICADO', @d;

SET @d = N'A COLUNA QUE IMPORTA. S quando a execucao nao inseriu nem atualizou nada. '
       + N'O projeto tem um contrato explicito: rodar de novo sem mexer na origem tem de '
       + N'convergir em zero. Uma carga que NUNCA converge tem defeito - e sempre teve, so '
       + N'que antes isso dependia de alguem rodar duas vezes e comparar no olho. '
       + N'N e esperado na primeira carga do dia, quando ha dado novo de verdade. '
       + N'PARA CONTAR: use SUM(CASE WHEN FL_CONVERGIU = ''S'' THEN 1 ELSE 0 END), e nao '
       + N'CAST para int - a coluna e char(1) desde a padronizacao dos indicadores.';
EXEC dbo.sp_documenta 'gold', 'fato_carga', 'FL_CONVERGIU', @d;
GO

SELECT NM_CAMADA + '.' + NM_TABELA AS tabela, NM_COLUNA AS coluna
FROM gold.vw_glossario_dados WHERE DS_STATUS_DOC <> 'Documentada';
GO
