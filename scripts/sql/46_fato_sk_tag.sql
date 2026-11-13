/* =============================================================
   manzo-dados | 46 - A tag principal no fato
   -------------------------------------------------------------
   gold.vw_tag_principal
   + SK_TAG em gold.fato_movto_financ e gold.fato_familia
   - DS_OBS dos dois fatos

   O 28_gold_tag.sql recusou esta coluna, e tinha razao no que
   dizia: um lancamento pode ter mais de uma tag, e uma chave
   estrangeira simples obriga a escolher uma. O que mudou nao foi o
   argumento, foi a MEDIDA dele - 17 lancamentos de 1.643 tem duas
   tags, 1%. Pelo 1% a ponte continua existindo; pelos 99% vale ter
   tambem o caminho simples.

   AS DUAS CONVIVEM, cada uma respondendo o que sabe responder:

     SK_TAG       um valor por lancamento. Fatia sem relacao
                  bidirecional e sem risco de somar em duplicidade.
                  E o caminho do dia a dia.

     ponte_tag    a verdade completa. Para TOTAL POR TAG e esta que
                  deve ser usada - ver a ressalva abaixo.

   A RESSALVA, MEDIDA. Somar por SK_TAG subconta a tag que perdeu a
   disputa. Hoje isso atinge uma so: #AleLia aparece em 208
   lancamentos pela ponte e em 191 por SK_TAG, porque em 17 deles a
   viagem levou a vaga. A conferencia no fim do script imprime essa
   diferenca toda vez que ele roda.

   POR QUE VIAGEM GANHA DE MARCACAO. Nao e preferencia: e o unico
   criterio que nao apaga uma tag inteira. Os 17 lancamentos sao
   "#Praia-Out22 #AleLia", e #Praia-Out22 TEM EXATAMENTE 17
   lancamentos - todos empatados. Se Marcacao vencesse, a tag da
   viagem ficaria com zero e sumiria do caminho simples; vencendo
   Viagem, #AleLia perde 17 de 208 e continua inteira na ponte.

   A REGRA MORA NUMA VIEW, e nao copiada aqui e na carga. Este
   script faz a carga inicial lendo gold.vw_tag_principal, e o ETL
   le a MESMA view a cada execucao. Escrita duas vezes, ela
   divergiria no primeiro ajuste - e a divergencia seria silenciosa,
   porque os dois lados continuariam devolvendo um numero.

   DS_OBS SAI DOS FATOS. O texto cru segue em silver e bronze de
   todas as origens, inclusive os 14 valores que sao numero solto
   ('100', '556.37', '-200') - lancamento cuja celula de valor caiu
   na coluna errada, e que o regras_tag.py ja recusava como tag.

   Pre-requisitos: 28_gold_tag.sql, 30_renomeia_tag.sql
   Idempotente.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. A regra, em um lugar so
   ------------------------------------------------------------- */
GO

CREATE OR ALTER VIEW gold.vw_tag_principal AS
/*
    Qual das tags de um lancamento vai para o fato.

    Ordem: Viagem, Imovel, Marcacao, resto. Empate resolvido pela
    menor SK_TAG, que e a que entrou na dimensao primeiro - criterio
    arbitrario, mas ESTAVEL: sem ele a escolha mudaria de execucao
    para execucao e o fato ficaria instavel sem nada ter mudado na
    origem.
*/
SELECT HASH_NEGOCIO, DS_FATO, SK_TAG
FROM (
    SELECT p.HASH_NEGOCIO, p.DS_FATO, p.SK_TAG,
           ROW_NUMBER() OVER (
               PARTITION BY p.HASH_NEGOCIO, p.DS_FATO
               ORDER BY CASE t.DS_TIPO
                            WHEN 'Viagem'   THEN 1
                            WHEN 'Imóvel'   THEN 2
                            WHEN 'Marcação' THEN 3
                            ELSE 4
                        END,
                        p.SK_TAG) AS ordem
    FROM gold.ponte_tag p
    JOIN gold.dim_tag  t ON t.SK_TAG = p.SK_TAG
) x
WHERE x.ordem = 1;
GO

/* -------------------------------------------------------------
   2. A chave nos dois fatos
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.fato_movto_financ', 'SK_TAG') IS NULL
    ALTER TABLE gold.fato_movto_financ ADD SK_TAG int NOT NULL
        CONSTRAINT DF_fato_movto_financ_tag DEFAULT (-1);
GO

IF COL_LENGTH('gold.fato_familia', 'SK_TAG') IS NULL
    ALTER TABLE gold.fato_familia ADD SK_TAG int NOT NULL
        CONSTRAINT DF_fato_familia_tag DEFAULT (-1);
GO

UPDATE f SET f.SK_TAG = v.SK_TAG
FROM gold.fato_movto_financ f
JOIN gold.vw_tag_principal v
  ON v.HASH_NEGOCIO = f.HASH_NEGOCIO AND v.DS_FATO = 'fato_movto_financ'
WHERE f.SK_TAG <> v.SK_TAG;
GO

UPDATE f SET f.SK_TAG = v.SK_TAG
FROM gold.fato_familia f
JOIN gold.vw_tag_principal v
  ON v.HASH_NEGOCIO = f.HASH_NEGOCIO AND v.DS_FATO = 'fato_familia'
WHERE f.SK_TAG <> v.SK_TAG;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_fato_movto_financ_tag')
    ALTER TABLE gold.fato_movto_financ ADD CONSTRAINT FK_fato_movto_financ_tag
        FOREIGN KEY (SK_TAG) REFERENCES gold.dim_tag (SK_TAG);
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_fato_familia_tag')
    ALTER TABLE gold.fato_familia ADD CONSTRAINT FK_fato_familia_tag
        FOREIGN KEY (SK_TAG) REFERENCES gold.dim_tag (SK_TAG);
GO

/* -------------------------------------------------------------
   3. A guarda, e so entao o DROP
   ------------------------------------------------------------- */

-- Lancamento que a ponte conhece e o fato nao marcou: a carga nao
-- fechou, e apagar DS_OBS agora perderia a unica copia no gold.
IF COL_LENGTH('gold.fato_movto_financ', 'DS_OBS') IS NOT NULL
BEGIN
    DECLARE @orfaos int =
        (SELECT COUNT(*) FROM gold.fato_movto_financ f
          JOIN gold.vw_tag_principal v
            ON v.HASH_NEGOCIO = f.HASH_NEGOCIO AND v.DS_FATO = 'fato_movto_financ'
         WHERE f.SK_TAG = -1)
      + (SELECT COUNT(*) FROM gold.fato_familia f
          JOIN gold.vw_tag_principal v
            ON v.HASH_NEGOCIO = f.HASH_NEGOCIO AND v.DS_FATO = 'fato_familia'
         WHERE f.SK_TAG = -1);

    IF @orfaos > 0
        THROW 50047, 'Ha lancamento com tag na ponte e SK_TAG = -1. DROP cancelado.', 1;
END
GO

IF COL_LENGTH('gold.fato_movto_financ', 'DS_OBS') IS NOT NULL
BEGIN
    ALTER TABLE gold.fato_movto_financ DROP COLUMN DS_OBS;
    ALTER TABLE gold.fato_familia      DROP COLUMN DS_OBS;
END
GO

/* -------------------------------------------------------------
   4. Documentacao
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'GOLD | Decide QUAL das tags de um lancamento vai para a coluna SK_TAG do fato, '
       + N'quando ha mais de uma. Ordem: Viagem, Imovel, Marcacao, resto; empate pela menor '
       + N'SK_TAG, que e estavel entre execucoes. '
       + N'EXISTE PARA A REGRA NAO SER ESCRITA DUAS VEZES: o script 46 faz a carga inicial '
       + N'lendo daqui e o carga_gold_movimentacao.py le daqui a cada execucao. Copiada nos '
       + N'dois lugares, ela divergiria no primeiro ajuste, e em silencio - os dois lados '
       + N'continuariam devolvendo um numero. '
       + N'Mudar a regra e alterar esta view e recarregar; nao ha mais nenhum lugar a tocar.';
EXEC dbo.sp_documenta 'gold', 'vw_tag_principal', NULL, @d;

SET @d = N'Chave para gold.dim_tag: a tag PRINCIPAL do lancamento, -1 quando nao ha '
       + N'nenhuma. Substituiu DS_OBS, cujo texto cru segue na silver e na bronze. '
       + N'ATENCAO AO SOMAR POR TAG: um lancamento pode ter mais de uma marcacao e aqui so '
       + N'cabe a principal, entao o total por esta coluna SUBCONTA a tag que perdeu a '
       + N'disputa - hoje #AleLia, com 191 aqui contra 208 na ponte. Para total por tag '
       + N'use gold.ponte_tag; para fatiar no dia a dia, use esta coluna, que nao exige '
       + N'relacao bidirecional nem duplica linha. A escolha e feita por '
       + N'gold.vw_tag_principal.';
EXEC dbo.sp_documenta 'gold', 'fato_movto_financ', 'SK_TAG', @d;
EXEC dbo.sp_documenta 'gold', 'fato_familia',      'SK_TAG', @d;
GO

/* -------------------------------------------------------------
   5. Conferencia
   ------------------------------------------------------------- */

SELECT 'lancamentos com tag (movto)' AS conferencia,
       CAST(COUNT(*) AS varchar(20)) AS valor
FROM gold.fato_movto_financ WHERE SK_TAG <> -1
UNION ALL SELECT 'lancamentos com tag (familia)',
    CAST((SELECT COUNT(*) FROM gold.fato_familia WHERE SK_TAG <> -1) AS varchar(20))
UNION ALL SELECT 'DS_OBS removida dos dois fatos',
    CASE WHEN COL_LENGTH('gold.fato_movto_financ','DS_OBS') IS NULL
          AND COL_LENGTH('gold.fato_familia','DS_OBS') IS NULL
         THEN 'sim' ELSE 'NAO' END;

-- A ressalva do cabecalho, medida toda vez: onde SK_TAG subconta.
SELECT t.NM_TAG, t.DS_TIPO,
       COUNT(*) AS pela_ponte,
       SUM(CASE WHEN f.SK_TAG = t.SK_TAG THEN 1 ELSE 0 END) AS por_sk_tag,
       COUNT(*) - SUM(CASE WHEN f.SK_TAG = t.SK_TAG THEN 1 ELSE 0 END) AS diferenca
FROM gold.ponte_tag p
JOIN gold.dim_tag t ON t.SK_TAG = p.SK_TAG
JOIN gold.fato_movto_financ f ON f.HASH_NEGOCIO = p.HASH_NEGOCIO
WHERE p.DS_FATO = 'fato_movto_financ'
GROUP BY t.NM_TAG, t.DS_TIPO, t.SK_TAG
HAVING COUNT(*) <> SUM(CASE WHEN f.SK_TAG = t.SK_TAG THEN 1 ELSE 0 END)
ORDER BY diferenca DESC;
GO
