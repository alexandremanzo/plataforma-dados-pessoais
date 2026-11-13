/* =============================================================
   Migracao do relatorio pessoal | f_meu_dia
   -------------------------------------------------------------
   Substitui a leitura do CSV publicado do Google Forms pela
   leitura do lake, SEM MUDAR NADA do que o relatorio enxerga.

   POR QUE HA UMA TRADUCAO AQUI. O gold canonizou as respostas:
   "Sim" virou "SIM", "Nao"/"Nao" viraram "NAO", "Jaca" virou
   "JACA". As 35 medidas de f_meu_dia comparam com os valores
   ORIGINAIS - "Sim" aparece 16 vezes no DAX, "Nao" 10, "Jaca" 5.
   Apontar direto para o gold faria todas retornarem zero, com os
   visuais renderizando vazios: nao daria erro, daria silencio.
   A traducao devolve o vocabulario que o relatorio ja espera.

   AGUA VOLTA COMO NUMERO, e nao como texto. A consulta atual
   tipa "Consumo de agua (Litros)" com type number; VL_MEDIDA ja
   e o numero, entao serve direto e sem depender de separador
   decimal.

   DS_PERGUNTA E O CABECALHO DO FORMULARIO, preservado pela
   carga. E por isso que os nomes de coluna saem identicos sem
   nenhum rename: "Cafe da Manha" aqui e o mesmo texto que o
   Google entrega la.

   O dia sem data valida (SK_DATA = -1) fica de fora: sao as duas
   respostas com 31/12/1900 e 08/08/3025 digitadas errado no
   formulario, que o relatorio tambem nao consegue situar.

   O CARIMBO VEM DA BRONZE, e e a unica coluna que precisa dela. O gold
   guardou o DERIVADO (fato_dia.NR_DIAS_ATRASO, dias entre a data
   relatada e o envio) mas nao o carimbo bruto. A coluna nao e usada por
   nenhuma medida nem visual - so esta declarada no modelo, e tirar a
   declaracao seria mexer no modelo, nao na fonte. Se um dia fato_dia
   ganhar DT_CARIMBO, este join sai.
   ============================================================= */

SELECT  c.DT_DATA AS [Data],

        MAX(b.ds_carimbo)                                    AS [Carimbo de data/hora],

        MAX(CASE WHEN h.DS_PERGUNTA = N'Treino'
                 THEN v.DS_TRADUZIDO END)                    AS [Treino],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Cardio'
                 THEN v.DS_TRADUZIDO END)                    AS [Cardio],

        /* numero, nao texto: e assim que a consulta atual tipa */
        MAX(CASE WHEN h.DS_PERGUNTA = N'Consumo de água (Litros)'
                 THEN fh.VL_MEDIDA END)                      AS [Consumo de água (Litros)],

        MAX(CASE WHEN h.DS_PERGUNTA = N'Café da Manhã'
                 THEN v.DS_TRADUZIDO END)                    AS [Café da Manhã],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Almoço'
                 THEN v.DS_TRADUZIDO END)                    AS [Almoço],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Lanche'
                 THEN v.DS_TRADUZIDO END)                    AS [Lanche],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Janta'
                 THEN v.DS_TRADUZIDO END)                    AS [Janta],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Ceia'
                 THEN v.DS_TRADUZIDO END)                    AS [Ceia],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Dia Produtivo'
                 THEN v.DS_TRADUZIDO END)                    AS [Dia Produtivo],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Trabalho'
                 THEN v.DS_TRADUZIDO END)                    AS [Trabalho],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Nina em casa'
                 THEN v.DS_TRADUZIDO END)                    AS [Nina em casa],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Estresse'
                 THEN v.DS_TRADUZIDO END)                    AS [Estresse],
        MAX(CASE WHEN h.DS_PERGUNTA = N'Lazer'
                 THEN v.DS_TRADUZIDO END)                    AS [Lazer]

FROM        gold.fato_dia_habito fh
JOIN        gold.dim_habito      h ON h.SK_HABITO = fh.SK_HABITO
JOIN        gold.dim_calendario  c ON c.SK_DATA   = fh.SK_DATA
LEFT JOIN   bronze.dia_registro  b ON CAST(b.ds_data AS date) = c.DT_DATA

/* O de-para do vocabulario, num lugar so. Valor que o gold venha a
   ter e que nao esteja aqui volta como ele mesmo - visivel na tela,
   em vez de virar nulo e sumir da contagem. */
CROSS APPLY (SELECT CASE fh.DS_RESPOSTA
                        WHEN N'SIM'    THEN N'Sim'
                        WHEN N'NAO'    THEN N'Não'
                        WHEN N'JACA'   THEN N'Jaca'
                        WHEN N'NORMAL' THEN N'Normal'
                        ELSE fh.DS_RESPOSTA
                    END) AS v(DS_TRADUZIDO)

WHERE  fh.SK_DATA <> -1
GROUP BY c.DT_DATA
