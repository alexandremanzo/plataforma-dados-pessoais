/* =============================================================
   manzo-dados | 01 - Criacao das camadas da arquitetura medalhao
   -------------------------------------------------------------
   Cria os schemas bronze, silver e gold no banco db-manzo e
   documenta cada um via extended property (MS_Description).

   Idempotente: pode ser executado quantas vezes for necessario.

   NAO remove nada existente. As tabelas atuais (dbo.fato_lancamentos,
   dbo.dim_*, dbo.dados-xp) continuam intactas em dbo durante a
   transicao e serao migradas tabela a tabela numa etapa posterior.
   ============================================================= */

USE [db-manzo];
GO

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------
   1. Schemas das camadas
   ------------------------------------------------------------- */

IF SCHEMA_ID('bronze') IS NULL
    EXEC('CREATE SCHEMA [bronze]');
GO

IF SCHEMA_ID('silver') IS NULL
    EXEC('CREATE SCHEMA [silver]');
GO

IF SCHEMA_ID('gold') IS NULL
    EXEC('CREATE SCHEMA [gold]');
GO


/* -------------------------------------------------------------
   2. Documentacao dos schemas
   Cada camada carrega sua propria descricao no banco, alimentando
   o glossario de dados do projeto.
   ------------------------------------------------------------- */

DECLARE @camadas TABLE (nome sysname, descricao nvarchar(2000));

INSERT INTO @camadas (nome, descricao) VALUES
('bronze', N'CAMADA BRONZE (Raw). Copia fiel dos arquivos de origem, sem nenhuma '
         + N'transformacao de negocio. Colunas em texto, nomes preservados da origem. '
         + N'Toda tabela carrega metadados de linhagem (arquivo de origem, data de carga). '
         + N'Regra: se o dado precisa ser corrigido, a correcao acontece na silver, nunca aqui. '
         + N'Permite reprocessar todo o pipeline sem voltar aos arquivos originais.'),

('silver', N'CAMADA SILVER (Refined). Dados limpos, tipados e padronizados: datas em date, '
         + N'valores em decimal, textos normalizados e deduplicados. Uma tabela por entidade '
         + N'de negocio, ja unificando origens diferentes (ex: lancamentos de Itau, XP e Nubank '
         + N'no mesmo formato). Ainda em modelo normalizado, sem chaves substitutas.'),

('gold',   N'CAMADA GOLD (Consumo). Modelo dimensional em star schema pronto para o Power BI: '
         + N'tabelas fato com metricas e dimensoes com chaves substitutas (SK). Otimizada para '
         + N'leitura e agregacao. E a unica camada que o Power BI deve consultar.');

DECLARE @nome sysname, @descricao nvarchar(2000);

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT nome, descricao FROM @camadas;

OPEN cur;
FETCH NEXT FROM cur INTO @nome, @descricao;

WHILE @@FETCH_STATUS = 0
BEGIN
    IF EXISTS (
        SELECT 1 FROM sys.extended_properties
        WHERE class = 3                              -- classe 3 = schema
          AND major_id = SCHEMA_ID(@nome)
          AND name = 'MS_Description'
    )
        EXEC sys.sp_updateextendedproperty
             @name = N'MS_Description', @value = @descricao,
             @level0type = N'SCHEMA', @level0name = @nome;
    ELSE
        EXEC sys.sp_addextendedproperty
             @name = N'MS_Description', @value = @descricao,
             @level0type = N'SCHEMA', @level0name = @nome;

    FETCH NEXT FROM cur INTO @nome, @descricao;
END

CLOSE cur;
DEALLOCATE cur;
GO


/* -------------------------------------------------------------
   3. Permissoes do usuario da aplicacao
   O login 'manzo' e quem executa as cargas do Python/Airflow e
   precisa criar e popular tabelas nas tres camadas.

   Hoje 'manzo' e sysadmin e mapeia direto para dbo, entao ja tem
   acesso total e nada precisa ser concedido. O bloco abaixo so
   age se essa situacao mudar (ex: quando o login for rebaixado
   para um usuario comum, que e o correto a medio prazo).
   ------------------------------------------------------------- */

IF IS_SRVROLEMEMBER('sysadmin', 'manzo') = 1
BEGIN
    PRINT 'Login [manzo] e sysadmin (mapeado para dbo): nenhum GRANT necessario.';
END
ELSE
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'manzo')
        CREATE USER [manzo] FOR LOGIN [manzo];

    EXEC('GRANT CREATE TABLE, CREATE VIEW TO [manzo]');
    EXEC('GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, REFERENCES ON SCHEMA::[bronze] TO [manzo]');
    EXEC('GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, REFERENCES ON SCHEMA::[silver] TO [manzo]');
    EXEC('GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, REFERENCES ON SCHEMA::[gold]   TO [manzo]');

    PRINT 'Permissoes concedidas ao usuario [manzo] nas tres camadas.';
END
GO


/* -------------------------------------------------------------
   4. Conferencia
   ------------------------------------------------------------- */

SELECT
    s.name                              AS camada,
    USER_NAME(s.principal_id)           AS proprietario,
    CAST(ep.value AS nvarchar(200))     AS descricao_inicio
FROM sys.schemas s
LEFT JOIN sys.extended_properties ep
       ON ep.class = 3
      AND ep.major_id = s.schema_id
      AND ep.name = 'MS_Description'
WHERE s.name IN ('bronze', 'silver', 'gold')
ORDER BY CASE s.name WHEN 'bronze' THEN 1 WHEN 'silver' THEN 2 ELSE 3 END;
GO
