/* =============================================================
   manzo-dados | 51 - Vencimento do consentimento na bronze
   -------------------------------------------------------------
   + DT_CONSENTIMENTO_VENCE em bronze.xp_posicao

   O consentimento de Open Finance VENCE em doze meses - 15/10/2027
   nesta conexao - e quando vence a API nao da erro: ela continua
   respondendo, com dado velho ou com lista vazia. A carga tem uma
   guarda contra isso, mas ela so dispara DEPOIS de vencer.

   POR QUE A DATA PRECISA ESTAR NO BANCO. O vigia das cargas roda
   fora do Airflow e fala SO com o SQL Server - e dessa limitacao que
   vem a utilidade dele: ele funciona quando o Docker esta parado, a
   rede caiu ou a API esta fora. Consultar a Pluggy de dentro dele
   devolveria a dependencia que ele existe para nao ter.

   Entao a carga, que ja le o item e ja conhece a data, grava.  O
   vigia le do banco e avisa com antecedencia.

   GUARDADA POR FOTO, e nao numa tabela de parametro. A data muda
   quando o consentimento e renovado, e tendo uma por snapshot fica
   registrado QUANDO a renovacao aconteceu - sem isso, renovar
   apagaria o rastro da renovacao anterior.

   Pre-requisitos: 48_bronze_xp_posicao.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

IF COL_LENGTH('bronze.xp_posicao', 'dt_consentimento_vence') IS NULL
    ALTER TABLE bronze.xp_posicao ADD dt_consentimento_vence date NULL;
GO

DECLARE @d nvarchar(3750);

SET @d = N'Quando o consentimento de Open Finance desta conexao vence, como a API informou '
       + N'na hora da foto. Nula se a API nao informou. '
       + N'EXISTE PARA O VIGIA PODER AVISAR ANTES. O consentimento vence em doze meses e, ao '
       + N'vencer, a API NAO da erro: continua respondendo, com dado velho ou lista vazia. O '
       + N'vigia das cargas roda fora do Airflow e fala so com o SQL Server - consultar a '
       + N'Pluggy de dentro dele devolveria a dependencia que ele existe para nao ter. Entao a '
       + N'carga grava a data e o vigia le daqui. '
       + N'GUARDADA POR FOTO: renovar o consentimento muda a data, e ter uma por snapshot '
       + N'registra QUANDO a renovacao aconteceu.';
EXEC dbo.sp_documenta 'bronze', 'xp_posicao', 'dt_consentimento_vence', @d;
GO

SELECT 'coluna criada' AS conferencia,
       CASE WHEN COL_LENGTH('bronze.xp_posicao','dt_consentimento_vence') IS NOT NULL
            THEN 'sim' ELSE 'NAO' END AS r
UNION ALL SELECT 'linhas ja preenchidas',
    CAST((SELECT COUNT(*) FROM bronze.xp_posicao
           WHERE dt_consentimento_vence IS NOT NULL) AS varchar(10))
UNION ALL SELECT 'documentada',
    CASE WHEN EXISTS (SELECT 1 FROM sys.extended_properties ep
                       WHERE ep.major_id = OBJECT_ID('bronze.xp_posicao')
                         AND ep.name = 'MS_Description'
                         AND ep.minor_id = COLUMNPROPERTY(
                               OBJECT_ID('bronze.xp_posicao'),
                               'dt_consentimento_vence', 'ColumnId'))
         THEN 'sim' ELSE 'NAO' END;
GO
