USE [db-manzo];
GO
SET NOCOUNT ON;
GO

/* =============================================================
   manzo-dados | 44 - Compressibilidade do gasto
   -------------------------------------------------------------
   Classifica cada GRUPO em quatro naturezas, para o painel separar
   o que da para cortar do que nao da:

     Compressivel  discricionario e recorrente - comida fora,
                   assinatura, lazer. E daqui que sai economia sem
                   perda estrutural.
     Essencial     moradia, escola, combustivel, saude, imposto.
                   Cortar aqui muda a vida, nao o orcamento.
     Eventual      nao se repete: revisao, eletrodomestico, viagem,
                   reforma. E o que estoura a meta do cartao - e o
                   que deveria sair de um fundo, nao da fatura.
     Nao e gasto   aporte, resgate, transferencia entre contas.
                   Existe para NAO ser somado como consumo.

   POR QUE UMA COLUNA, E NAO UMA TABELA NOVA. O grao e exatamente o
   grupo, entao uma tabela 1:1 com dim_grupo_financ seria um join
   que nao paga o preco.

   POR QUE E SEGURO GRAVAR AQUI. sincroniza_classificacao() so faz
   INSERT de membros novos - nunca reescreve linha existente. A
   classificacao a mao sobrevive as cargas. Grupo novo nasce NULL e
   o painel o mostra como "A classificar": valor nao previsto tem de
   aparecer, nao de sumir na conta.

   A SEMEADURA ABAIXO E UM PONTO DE PARTIDA, NAO UM VEREDITO. Sao
   escolhas sobre a vida de quem usa o painel, e quem usa e que
   decide. Mudar e um UPDATE de uma linha.

   Idempotente.
   ============================================================= */

/* -------------------------------------------------------------
   1. A coluna
   ------------------------------------------------------------- */

IF COL_LENGTH('gold.dim_grupo_financ', 'DS_COMPRESSIBILIDADE') IS NULL
BEGIN
    ALTER TABLE gold.dim_grupo_financ
        ADD DS_COMPRESSIBILIDADE varchar(20) NULL;
    PRINT 'Coluna DS_COMPRESSIBILIDADE criada.';
END
ELSE
    PRINT 'Coluna DS_COMPRESSIBILIDADE ja existe.';
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_dim_grupo_financ_DS_COMPRESSIBILIDADE')
    ALTER TABLE gold.dim_grupo_financ
        ADD CONSTRAINT CK_dim_grupo_financ_DS_COMPRESSIBILIDADE
        CHECK (DS_COMPRESSIBILIDADE IN
               ('Compressivel', 'Essencial', 'Eventual', 'Nao e gasto'));
GO

/* -------------------------------------------------------------
   2. A semeadura
   -------------------------------------------------------------
   Nomes de grupo sao globais em dim_grupo_financ - a combinacao com
   area e categoria vive no fato. Entao "Manutencao" e uma linha so,
   usada por carro e por casa; as duas caem em Eventual, e nao ha
   conflito. Onde havia ambiguidade real, escolhi o uso dominante.

   So sobrescreve o que ainda esta NULL: reexecutar nao desfaz ajuste
   seu.
   ------------------------------------------------------------- */

DECLARE @regra TABLE (NM_GRUPO varchar(100) PRIMARY KEY,
                      DS_CLASSE varchar(20));

INSERT INTO @regra (NM_GRUPO, DS_CLASSE) VALUES
  -- ---------- Nao e gasto: movimento de patrimonio ----------
  ('Cofrinho','Nao e gasto'), ('Investimento','Nao e gasto'),
  ('Transferencia','Nao e gasto'), ('Transferencia entre contas','Nao e gasto'),
  ('Mesada','Nao e gasto'), ('Aplicacao','Nao e gasto'),
  ('Resgate','Nao e gasto'), ('Rendimento','Nao e gasto'),

  -- ---------- Essencial: moradia, familia, saude, obrigacao ----------
  ('Conta Familia','Essencial'), ('Escola','Essencial'),
  ('Material Escolar','Essencial'), ('Material','Essencial'),
  ('Uniforme','Essencial'), ('Combustivel','Essencial'),
  ('IPVA','Essencial'), ('SEGURO','Essencial'), ('Seguro Carro','Essencial'),
  ('Estacionamento','Essencial'), ('Veloe','Essencial'),
  ('Internet','Essencial'), ('Telefonia','Essencial'),
  ('Medicamento','Essencial'), ('Plano Saude','Essencial'),
  ('Pediatra','Essencial'), ('Consulta','Essencial'), ('Fono','Essencial'),
  ('Odonto','Essencial'), ('Dentista','Essencial'), ('Vacina','Essencial'),
  ('Nutricionista','Essencial'), ('Academia','Essencial'),
  ('Higiene','Essencial'), ('Mercado','Essencial'), ('Sacolao','Essencial'),
  ('Leite','Essencial'), ('Compras','Essencial'),
  ('IRRF','Essencial'), ('Imposto','Essencial'),
  ('Contabilidade','Essencial'), ('Emprestimo','Essencial'),
  ('Aluguel','Essencial'), ('Condominio','Essencial'),
  ('Energia','Essencial'), ('Agua','Essencial'),

  -- ---------- Compressivel: discricionario e recorrente ----------
  ('ALMOCO','Compressivel'), ('Lanche','Compressivel'),
  ('Burguer','Compressivel'), ('Burger','Compressivel'),
  ('Janta','Compressivel'), ('Pizza','Compressivel'),
  ('Japa','Compressivel'), ('Tropeiro','Compressivel'),
  ('Feijoada','Compressivel'), ('Cafe da manha','Compressivel'),
  ('Padaria','Compressivel'), ('Sorvete','Compressivel'),
  ('Acai','Compressivel'), ('Bolo','Compressivel'),
  ('Bebida','Compressivel'), ('Chopp','Compressivel'),
  ('Butecando','Compressivel'), ('Churrasco','Compressivel'),
  ('Streaming','Compressivel'), ('Assinatura','Compressivel'),
  ('Cinema','Compressivel'), ('Ingresso','Compressivel'),
  ('Show','Compressivel'), ('Boliche','Compressivel'),
  ('Evento','Compressivel'), ('Passeio','Compressivel'),
  ('Parque','Compressivel'), ('Clube','Compressivel'),
  ('Voley','Compressivel'), ('Cachoeira','Compressivel'),
  ('Uber','Compressivel'), ('Buser','Compressivel'),
  ('Corte cabelo','Compressivel'), ('Cabelo','Compressivel'),
  ('Rape','Compressivel'), ('Spotfy','Compressivel'),
  ('Armazenamento dados','Compressivel'),

  -- ---------- Eventual: nao se repete, deveria vir de fundo ----------
  ('Compra Carro','Eventual'), ('Revisao','Eventual'),
  ('Manutencao','Eventual'), ('Reforma','Eventual'),
  ('Acessorio','Eventual'), ('Acesorios','Eventual'),
  ('Aviao','Eventual'), ('Viagem','Eventual'), ('Hospedagem','Eventual'),
  ('Pousada','Eventual'), ('Excursao','Eventual'), ('Mala','Eventual'),
  ('Eletrodomestico','Eventual'), ('Eletodomestico','Eventual'),
  ('Eletro','Eventual'), ('Eletronico','Eventual'),
  ('Movel','Eventual'), ('Utencilios','Eventual'),
  ('Untecilios','Eventual'), ('Churrasqueira','Eventual'),
  ('Quadro','Eventual'), ('Vidro','Eventual'), ('Tinta','Eventual'),
  ('Enfeite Natal','Eventual'), ('Celular','Eventual'),
  ('Computador','Eventual'), ('Monitor','Eventual'), ('Fone','Eventual'),
  ('Teclado','Eventual'), ('Relogio','Eventual'), ('Bike','Eventual'),
  ('Fotografia','Eventual'), ('Roupa','Eventual'), ('Roupas','Eventual'),
  ('Blusa','Eventual'), ('Tenis','Eventual'), ('Bota','Eventual'),
  ('Calcado','Eventual'), ('Chuteira','Eventual'),
  ('Suplemento','Eventual'), ('Cosmetico','Eventual'),
  ('Presente','Eventual'), ('Presente Niver','Eventual'),
  ('Presente Natal','Eventual'), ('Niver','Eventual'),
  ('Dia das maes','Eventual'), ('Dia das Criancas','Eventual'),
  ('Pascoa','Eventual'), ('Casamento','Eventual'),
  ('Livro','Eventual'), ('Livros','Eventual'), ('Papelaria','Eventual'),
  ('Estudos','Eventual'), ('Aula Luta','Eventual'),
  ('Salao Festa','Eventual'), ('Brinquedo','Eventual'),
  ('Multa','Eventual'), ('Roubo','Eventual'), ('Limpeza','Eventual');

/* A juncao ignora acento e caixa: os grupos vieram de digitacao livre
   ao longo de doze anos, e "Revisao" aqui tem de casar com "Revisão"
   la. A collation do banco e CI_AS - ignora caixa, NAO ignora acento -,
   entao o AI vem explicito. */
UPDATE g
   SET g.DS_COMPRESSIBILIDADE = r.DS_CLASSE
  FROM gold.dim_grupo_financ g
  JOIN @regra r
    ON g.NM_GRUPO COLLATE Latin1_General_CI_AI
     = r.NM_GRUPO COLLATE Latin1_General_CI_AI
 WHERE g.DS_COMPRESSIBILIDADE IS NULL;

PRINT CONCAT('Grupos classificados nesta execucao: ', @@ROWCOUNT);
GO

/* -------------------------------------------------------------
   3. Documentacao - o contrato de zero pendentes
   ------------------------------------------------------------- */

DECLARE @d nvarchar(3750);

SET @d = N'Natureza do gasto, para separar o que da para cortar do que nao da. '
       + N'Compressivel: discricionario e recorrente (comida fora, assinatura, lazer) - '
       + N'e daqui que sai economia sem perda estrutural. '
       + N'Essencial: moradia, escola, combustivel, saude, imposto. '
       + N'Eventual: nao se repete (revisao, eletrodomestico, viagem) - e o que estoura '
       + N'a meta do cartao, e o que deveria sair de um fundo em vez da fatura. '
       + N'Nao e gasto: aporte, resgate e transferencia entre contas, que existem aqui '
       + N'para NAO serem somados como consumo. '
       + N'NULA significa grupo ainda nao classificado, e o painel o mostra como '
       + N'"A classificar" - lacuna que aparece e lacuna que alguem preenche. '
       + N'Preenchida a mao; a carga so insere membros novos e nunca sobrescreve.';
EXEC dbo.sp_documenta 'gold', 'dim_grupo_financ', 'DS_COMPRESSIBILIDADE', @d;
GO

/* -------------------------------------------------------------
   4. Conferencia
   ------------------------------------------------------------- */

SELECT ISNULL(g.DS_COMPRESSIBILIDADE, 'A classificar') AS classe,
       COUNT(DISTINCT g.SK_GRUPO_FINANC)               AS grupos,
       CAST(SUM(-f.VL_TRANSACAO) AS decimal(12,2))     AS gasto_24m
  FROM gold.dim_grupo_financ g
  LEFT JOIN gold.fato_movto_financ f
    ON f.SK_GRUPO_FINANC = g.SK_GRUPO_FINANC
   AND f.DS_NIVEL = 'ANALITICO' AND f.VL_TRANSACAO < 0
   AND f.SK_DATA >= (SELECT MIN(SK_DATA) FROM gold.dim_calendario
                      WHERE DT_DATA >= DATEADD(month, -24, GETDATE()))
 GROUP BY ISNULL(g.DS_COMPRESSIBILIDADE, 'A classificar')
 ORDER BY gasto_24m DESC;
GO

/* Os 20 grupos sem classificacao que mais pesam - a fila de trabalho. */
SELECT TOP 20 g.NM_GRUPO AS grupo,
       CAST(SUM(-f.VL_TRANSACAO) AS decimal(12,2)) AS gasto_24m
  FROM gold.dim_grupo_financ g
  JOIN gold.fato_movto_financ f
    ON f.SK_GRUPO_FINANC = g.SK_GRUPO_FINANC
 WHERE g.DS_COMPRESSIBILIDADE IS NULL
   AND f.DS_NIVEL = 'ANALITICO' AND f.VL_TRANSACAO < 0
   AND f.SK_DATA >= (SELECT MIN(SK_DATA) FROM gold.dim_calendario
                      WHERE DT_DATA >= DATEADD(month, -24, GETDATE()))
 GROUP BY g.NM_GRUPO
 ORDER BY gasto_24m DESC;
GO

/* Contrato do projeto: nenhuma coluna pendente de documentacao. */
SELECT NM_CAMADA + '.' + NM_TABELA AS tabela, NM_COLUNA AS coluna
  FROM gold.vw_glossario_dados
 WHERE DS_STATUS_DOC <> 'Documentada';
GO
