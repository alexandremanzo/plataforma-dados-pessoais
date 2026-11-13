# Glossário de dados

> Gerado automaticamente a partir das descrições gravadas no
> próprio banco, via `gold.vw_glossario_dados`. Não edite este
> arquivo: altere a descrição no script de DDL correspondente e
> rode `python scripts/etl/exporta_glossario.py`.

Atualizado em 02/10/2026 — 52 tabelas, 664 colunas, 664 documentadas.

## Índice

- **bronze** — [bronze.auto_intervalo_troca](#bronzeauto_intervalo_troca) · [bronze.auto_manutencao](#bronzeauto_manutencao) · [bronze.auto_revisao_programada](#bronzeauto_revisao_programada) · [bronze.avaliacao_fisica](#bronzeavaliacao_fisica) · [bronze.avaliacao_inbody](#bronzeavaliacao_inbody) · [bronze.cartao_nubank](#bronzecartao_nubank) · [bronze.cartao_xp](#bronzecartao_xp) · [bronze.dia_registro](#bronzedia_registro) · [bronze.familia_movimentacao](#bronzefamilia_movimentacao) · [bronze.financ_historico](#bronzefinanc_historico) · [bronze.itau_movimentacao](#bronzeitau_movimentacao) · [bronze.xp_movimentacao](#bronzexp_movimentacao)
- **silver** — [silver.auto_intervalo_troca](#silverauto_intervalo_troca) · [silver.auto_manutencao](#silverauto_manutencao) · [silver.auto_revisao_programada](#silverauto_revisao_programada) · [silver.avaliacao_fisica](#silveravaliacao_fisica) · [silver.avaliacao_inbody](#silveravaliacao_inbody) · [silver.cartao_movimentacao](#silvercartao_movimentacao) · [silver.de_para_categoria_itau](#silverde_para_categoria_itau) · [silver.de_para_categoria_nubank](#silverde_para_categoria_nubank) · [silver.de_para_classe_ativo](#silverde_para_classe_ativo) · [silver.de_para_item_revisao](#silverde_para_item_revisao) · [silver.dia_registro](#silverdia_registro) · [silver.familia_movimentacao](#silverfamilia_movimentacao) · [silver.financ_historico](#silverfinanc_historico) · [silver.itau_movimentacao](#silveritau_movimentacao) · [silver.xp_movimentacao](#silverxp_movimentacao)
- **gold** — [gold.dim_area_financ](#golddim_area_financ) · [gold.dim_ativo](#golddim_ativo) · [gold.dim_calendario](#golddim_calendario) · [gold.dim_categoria_auto](#golddim_categoria_auto) · [gold.dim_categoria_financ](#golddim_categoria_financ) · [gold.dim_categoria_investimento](#golddim_categoria_investimento) · [gold.dim_grupo_financ](#golddim_grupo_financ) · [gold.dim_habito](#golddim_habito) · [gold.dim_localizacao](#golddim_localizacao) · [gold.dim_metrica_corporal](#golddim_metrica_corporal) · [gold.dim_origem](#golddim_origem) · [gold.dim_pessoa](#golddim_pessoa) · [gold.dim_revisao_programada](#golddim_revisao_programada) · [gold.dim_segmento_corporal](#golddim_segmento_corporal) · [gold.dim_tag](#golddim_tag) · [gold.dim_veiculo](#golddim_veiculo) · [gold.fato_avaliacao_fisica](#goldfato_avaliacao_fisica) · [gold.fato_carga](#goldfato_carga) · [gold.fato_dia](#goldfato_dia) · [gold.fato_dia_habito](#goldfato_dia_habito) · [gold.fato_familia](#goldfato_familia) · [gold.fato_investimento](#goldfato_investimento) · [gold.fato_manutencao_auto](#goldfato_manutencao_auto) · [gold.fato_movto_financ](#goldfato_movto_financ) · [gold.ponte_tag](#goldponte_tag)

## bronze

Cópia fiel da origem, sem conversão de tipo. Cada evento uma única vez, com linhagem do arquivo de onde veio.

### bronze.auto_intervalo_troca

BRONZE | De quantos em quantos quilometros cada categoria deve ser trocada. Vem da aba "Tempo Troca" da mesma planilha. E A TABELA QUE TRANSFORMA HISTORICO EM PREVISAO: sozinho, o historico diz o que ja foi feito; cruzado com ela, diz o que esta vencendo. Cobre 13 das 34 categorias, e isso nao e falha - as demais sao corretivas (bandeja, bucha, lampada, mao de obra) e nao se trocam por quilometragem.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_intervalo** | `int` | Sim | Chave técnica | Chave tecnica sequencial. |
| ds_categoria | `varchar(100)` | Sim | Descrição | Categoria de manutencao, no mesmo vocabulario de bronze.auto_manutencao. |
| ds_intervalo_km | `varchar(30)` | Não | Descrição | Intervalo recomendado entre trocas, em quilometros. Vai de 5.000 (oleo) a 50.000 (amortecedor e correia). |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE. SHA-256 da categoria. |
| nm_arquivo_origem | `varchar(200)` | Sim | Nome | LINHAGEM: nome do arquivo de onde veio. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou ou foi atualizado. |

### bronze.auto_manutencao

BRONZE | Historico de revisoes e manutencoes do automovel, uma linha por item comprado ou servico prestado. Digitado a mao a partir das notas da oficina, numa planilha .xls de verdade (Excel 97-2003) - exige xlrd, nao openpyxl. CONTEM DOIS VEICULOS: o Sedan, de 2016 a novembro de 2025, e o SUV a partir dali. Cada um tem seu proprio hodometro, entao qualquer conta de quilometragem precisa ser feita por veiculo - as series nao se somam nem se continuam.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_manutencao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data da revisao ou manutencao, em formato ISO como texto. Todos os itens de uma mesma visita a oficina compartilham a data. |
| ds_veiculo | `varchar(60)` | Não | Descrição | Veiculo: Sedan ou SUV. Coluna CARRO da origem. Divide a base em duas series independentes de hodometro. |
| ds_km | `varchar(30)` | Não | Descrição | Quilometragem do veiculo no momento da manutencao. E o eixo que importa para manutencao preventiva - mais que a data, porque desgaste se mede em rodagem. |
| ds_natureza | `varchar(30)` | Não | Descrição | Coluna REVISAO da origem: "Revisão" quando foi manutencao programada, "Manutenção" quando foi conserto. Distingue o que se planeja do que quebra. |
| ds_tipo | `varchar(30)` | Não | Descrição | Coluna TIPO da origem: Produto (peca comprada) ou Serviço (mao de obra prestada). |
| ds_item | `varchar(200)` | Não | Descrição | Descricao do item ou servico, escrita a mao. Sao 110 textos distintos, com variacao livre de grafia - por isso a analise se faz por ds_categoria. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO da manutencao em 34 categorias: Óleo, Filtro, Freio, Pneu, Mão de Obra. E o eixo de analise e o que liga o historico a tabela de intervalos de troca. A origem traz "Mão de Obra" e "Mão de obra" como se fossem duas - a silver unifica. |
| ds_quantidade | `varchar(30)` | Não | Descrição | Quantidade de unidades do item. Vazia em tres lancamentos. |
| ds_valor | `varchar(30)` | Não | Descrição | METRICA. Valor pago em reais, ja pelo total do item e nao pelo unitario. |
| ds_local | `varchar(120)` | Não | Descrição | Oficina ou loja onde foi feito. Sao 16 estabelecimentos ao longo de 10 anos. |
| ds_observacao | `varchar(500)` | Não | Descrição | Observacao livre, preenchida em 30 lancamentos. Usada para numero de nota e detalhe do servico. |
| nr_ocorrencia | `int` | Sim | Número | Numero da ocorrencia do mesmo item na mesma visita. NECESSARIO: dois filtros de ar podem ser trocados no mesmo dia por precos diferentes, e dois amortecedores do mesmo eixo entram como duas linhas. Sao dez lancamentos assim, todos reais - sem o contador, metade deles seria confundida com duplicata e descartada. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 de data + veiculo + item + numero da ocorrencia. Com constraint UNIQUE: e o banco que impede a duplicacao. |
| nm_arquivo_origem | `varchar(200)` | Sim | Nome | LINHAGEM: nome do arquivo de onde o lancamento veio. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento entrou ou foi atualizado na base. |

### bronze.auto_revisao_programada

BRONZE | Plano de manutencao preventiva do fabricante, copia fiel da aba "Plano de Manutencao SUV 2017". NAO E EVENTO, E REGRA: as demais bronzes guardam o que aconteceu, esta guarda o que DEVE acontecer. A segunda aba do arquivo, "Matriz de Revisoes", nao entra - e a mesma regra reapresentada por marco de 10k a 100k, e o que ela acrescenta ja sai do intervalo mais a acao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id** | `int` | Sim | Outro | Chave tecnica da linha na bronze. |
| ds_modelo | `varchar(120)` | Não | Descrição | Modelo a que o plano se refere, lido do titulo da aba: "SUV 2017". E ele que liga a regra ao veiculo certo - o plano do SUV nao vale para o Sedan. |
| ds_item | `varchar(200)` | Não | Descrição | Item ou componente, como o fabricante o nomeia: "Filtro de Ar do Motor", "Fluido da Transmissao CVT". |
| ds_sistema | `varchar(120)` | Não | Descrição | Sistema do veiculo a que o item pertence: Motor, Freios, Suspensao, Cambio CVT. |
| ds_intervalo_km | `varchar(60)` | Não | Descrição | Intervalo em quilometros, como texto na origem. |
| ds_intervalo_tempo | `varchar(60)` | Não | Descrição | Intervalo de tempo como texto na origem, no formato "12 meses". E A COLUNA QUE MUDA O JOGO: o tempo corre sem depender de o hodometro ser anotado. |
| ds_acao | `varchar(60)` | Não | Descrição | Acao recomendada na origem: Troca, Inspecao, Servico ou "Inspecao / Troca". |
| ds_especificacao | `varchar(500)` | Não | Descrição | Especificacao tecnica: qual oleo, qual fluido, qual norma. Serve na hora de comprar a peca e de conferir o que a oficina usou. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO ITEM. SHA-256 de modelo + item normalizado. A planilha nao tem coluna de ID, mas os nomes vem de um documento de fabrica e sao estaveis por natureza. Com constraint UNIQUE. |
| nm_arquivo_origem | `varchar(200)` | Não | Nome | LINHAGEM: arquivo de origem. |
| nm_aba_origem | `varchar(120)` | Não | Nome | LINHAGEM: aba de origem. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba de origem. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o item entrou na base. |

### bronze.avaliacao_fisica

BRONZE | Avaliacoes fisicas e de bioimpedancia, uma linha por avaliacao e por medida. Digitado a mao a partir dos laudos, numa planilha .xls de verdade (Excel 97-2003) - por isso a carga usa xlrd e nao openpyxl. E A SERIE MAIS LONGA DO PROJETO: 31 avaliacoes entre 2008 e 2026. A origem ja vem desempilhada, com o grao que o fato precisa, entao a carga nao transforma o formato. Le apenas a aba Avaliacoes; a aba Resultados e uma tabela dinamica desatualizada que soma datas diferentes na mesma coluna.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_medicao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data da avaliacao, em formato ISO como texto. Todas as medidas de uma mesma avaliacao compartilham a data - e por ela que se sabe o que foi medido junto. |
| ds_grupo | `varchar(100)` | Não | Descrição | Agrupamento da medida, conforme o laudo: Analise da Composicao corporal, Analise Obesidade, Circunferencias Musculares, Medida Geral, Nivel gordura viceral e Pontuacao. E consistente na origem, e por isso e ele - e nao ds_classe - que a silver usa para classificar. |
| ds_item | `varchar(100)` | Não | Descrição | Nome da medida: Peso, IMC, % Gordura, Braco D, Cintura. Sao 30 itens distintos ao longo da serie, mas nenhuma avaliacao tem todos - ver a nota de eras na documentacao de silver.avaliacao_fisica. |
| ds_medida | `varchar(20)` | Não | Descrição | Unidade da medida: Kg, cm, %, L, Imc, bpm, mmHg, Pontos. Verificado: cada item usa sempre a mesma unidade em toda a serie, sem excecao. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor medido, como texto. Vazio quando a medida nao foi feita naquela avaliacao - "Busto" nunca foi preenchido em nenhuma das seis vezes em que apareceu na planilha. |
| ds_classe | `varchar(30)` | Não | Descrição | NAO USAR PARA CLASSIFICAR. Coluna da origem que parecia rotular o tipo de medida (PESO, MEDIDA, PRESSAO, PRINCIPAL, MACROS), mas e inconsistente: 8 dos 30 itens aparecem com mais de um rotulo, e "% Gordura" ja foi marcado como PRINCIPAL, MEDIDA e PRESSAO em datas diferentes. O padrao muda por ano, o que sugere coluna arrastada com as linhas deslocadas. Guardada por fidelidade a origem e descartada na silver, que classifica por ds_grupo. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DA MEDICAO. SHA-256 de data + item. E o grao natural da origem: verificado que nenhum item se repete na mesma avaliacao, entao o par identifica sozinho. Com constraint UNIQUE: e o banco que impede a duplicacao. |
| nm_arquivo_origem | `varchar(200)` | Sim | Nome | LINHAGEM: nome do arquivo de onde a medicao veio. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando a medicao entrou ou foi atualizada na base. |

### bronze.avaliacao_inbody

BRONZE | Leitura automatica dos exames de bioimpedancia InBody, UMA LINHA POR CAMPO LIDO. O exame chega como imagem - render do software LookinBody, sempre 1640x2310 - e o texto e extraido por OCR recortando regiao a regiao. O grao e o campo, e nao o exame, porque um campo ilegivel nao pode custar o exame inteiro: relendo com o recorte ajustado, troca-se aquele campo e os demais ficam intactos. NAO SUBSTITUI A PLANILHA de avaliacao fisica: as duas origens se juntam na gold, com o arquivo na frente e a planilha preenchendo o que o OCR nao alcancou.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id** | `int` | Sim | Outro | Chave tecnica da linha na bronze. |
| nm_arquivo | `varchar(200)` | Sim | Nome | LINHAGEM: arquivo de onde o campo foi lido. E o unico caminho de volta ate a imagem quando um valor parecer estranho. |
| ds_template | `varchar(40)` | Não | Descrição | Versao do leiaute, lida do rodape do proprio exame: F3/230-B-140219 nos exames ate 2019 e F3/230-C-210120 nos de 2024 em diante. E ela que escolhe o mapa de recortes - as duas versoes nao aceitam o mesmo. Versao desconhecida derruba a carga, em vez de ler coordenadas erradas em silencio. |
| ds_data_exame | `varchar(20)` | Não | Descrição | Data do exame como texto, para agrupar os campos de um mesmo arquivo sem depender de conversao. |
| ds_campo | `varchar(60)` | Sim | Descrição | Nome tecnico do campo lido: vl_peso, magra_3_kg, impedancia_20khz_0. AS CHAVES COMECADAS COM SUBLINHADO NAO SAO MEDIDAS: _problema guarda cada conferencia que falhou naquele exame, e existe para o defeito ficar registrado onde da para consultar, e nao so num log de terminal. |
| ds_valor | `varchar(200)` | Não | Descrição | Valor como o OCR devolveu, ainda em texto. O separador decimal alterna entre virgula e ponto no mesmo exame, e as vezes some - a tipagem e a conferencia acontecem na silver. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO CAMPO. SHA-256 de arquivo + campo. Com constraint UNIQUE, e o que torna a releitura de um exame idempotente. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o campo foi lido. |

### bronze.cartao_nubank

BRONZE | Gastos do cartao Nubank, de 2018 a 2022, quando o cartao foi encerrado. Vem da aba cad-credito de dados-nunbank-completo.xlsx. Emenda a serie do cartao XP, que comeca em 05/2022. ATENCAO: o sinal aqui e invertido em relacao ao XP (gasto e positivo) e os pagamentos de fatura estao misturados aos gastos - a coluna FL_EXTRATO os separa.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_movimentacao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data da compra, em formato ISO como texto. |
| ds_titulo | `varchar(1000)` | Não | Descrição | Descricao do lancamento como o Nubank a gera: nome do estabelecimento ("Durango Burger", "Ebanx Alipay") ou o tipo de evento ("Pagamento recebido", "Estorno de ...", "Rewards - Credito de compra apagada"). |
| ds_categoria_nubank | `varchar(60)` | Não | Descrição | Categoria atribuida pelo PROPRIO NUBANK, nao por voce: restaurante, transporte, servicos, supermercado, vestuario, viagem, casa, eletronicos, lazer, educacao, saude e outros. Preenchida em 91% dos lancamentos, contra 2% da classificacao manual - por isso e a base do de-para desta origem. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor do lancamento como veio da origem. SINAL INVERTIDO em relacao ao cartao XP: aqui gasto e POSITIVO e credito e negativo. A silver inverte para unificar as duas origens. |
| ds_data_fatura | `varchar(50)` | Não | Descrição | Data de vencimento da fatura em que o lancamento foi cobrado. Sao 49 faturas. |
| ds_tipo_movimentacao | `varchar(50)` | Não | Descrição | Natureza informada na planilha: Despesa ou Receita. NAO e confiavel como indicador de sinal - ha 112 linhas marcadas Despesa com valor negativo, que sao pagamentos de fatura, estornos e creditos de rewards. |
| fl_extrato | `varchar(5)` | Não | Indicador (sim/não) | DISCRIMINADOR DE NIVEL. Vale N nas 48 linhas de "Pagamento recebido" - o pagamento da fatura, que e lancamento SINTETICO - e S nos 2.297 lancamentos de consumo, que sao ANALITICOS. Separa com precisao o que somar e o que nao somar: sem esse filtro, os pagamentos anulam os gastos e a soma de 4 anos de cartao da R$ 2.310 em vez de R$ 122.081. |
| fl_rewards | `varchar(5)` | Não | Indicador (sim/não) | Marca S quando o lancamento e do programa de pontos (credito de compra apagada com Rewards). Sao 94 lancamentos. |
| ds_arquivo_fatura | `varchar(120)` | Não | Descrição | LINHAGEM DA ORIGEM: nome do CSV de fatura de onde a linha veio ("nubank-2018-06.csv"). Sao 49 arquivos, um por fatura, e essa rastreabilidade ja existia na planilha - foi preservada. |
| ds_area | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL nivel 1. Preenchida em apenas 2,2% dos lancamentos. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL nivel 2. Preenchida em apenas 2,1% dos lancamentos - por isso esta origem depende do de-para das categorias do Nubank. |
| ds_grupo | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL nivel 3. Preenchida em apenas 2,1% dos lancamentos. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | Quem pagou, na anotacao manual. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu, na anotacao manual. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto, quando anotada. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto, quando anotada. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto, quando anotado. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre. |
| ds_projeto | `varchar(100)` | Não | Descrição | Projeto vinculado ao gasto. Praticamente nao utilizado. |
| ds_tag | `varchar(100)` | Não | Descrição | Marcador livre, fora da hierarquia de categoria. |
| nr_ocorrencia | `int` | Sim | Número | Numero da ocorrencia da mesma combinacao de data, titulo, valor e fatura. Necessario porque o cartao nao tem saldo corrente para desempatar compras identicas no mesmo dia. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 de data + titulo normalizado + valor + data da fatura + numero da ocorrencia. Com constraint UNIQUE. |
| nm_arquivo_origem | `varchar(260)` | Sim | Nome | LINHAGEM: arquivo de origem. |
| nm_aba_origem | `varchar(120)` | Sim | Nome | LINHAGEM: aba de origem. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba de origem. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o evento entrou na base. |

### bronze.cartao_xp

BRONZE | Gastos detalhados do cartao de credito XP, de maio/2022 em diante, vindos da aba MOVTO de dados-xp-credito.xlsx. Sao os lancamentos ANALITICOS do modelo de movimentacao: cada compra individual. O pagamento da fatura, que aparece na conta corrente como "Cartao de Credito XP", e o lancamento SINTETICO correspondente - somar os dois niveis duplicaria a despesa. Diferente da conta corrente, esta origem ja vem 99,4% classificada.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_movimentacao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data da COMPRA, em formato ISO como texto. Nao confundir com a data da fatura: uma compra de julho pode cair na fatura de agosto, e uma compra parcelada aparece em varias faturas. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do gasto. Diferente da conta corrente, aqui e um texto escrito por voce ("Lanche Nina", "Gasolina", "Utensilios casa"), nao o codigo do banco - por isso a classificacao desta origem e muito mais completa. |
| ds_parcela | `varchar(20)` | Não | Descrição | Numero da parcela, quando a compra foi parcelada. Preenchido em cerca de 20% dos lancamentos. E o que explica faturas com vencimento futuro. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor bruto como digitado na planilha. ATENCAO: o sinal e inconsistente nesta coluna - ha estornos gravados como positivo e como negativo. NAO USE para calculo; use ds_valor_tratado. |
| ds_valor_tratado | `varchar(50)` | Não | Descrição | METRICA DA ORIGEM. Valor com sinal consistente: negativo e gasto, positivo e estorno ou credito. E o negativo de ds_valor em 4.165 das 4.174 linhas; nas demais corrige inversoes de sinal feitas na digitacao. E esta a coluna que a silver converte em vl_transacao. |
| ds_tipo_movimentacao | `varchar(50)` | Não | Descrição | Natureza do lancamento conforme a planilha: DESPESA ou RECEITA. |
| ds_area | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 1: ESTILO DE VIDA, GASTOS ESSENCIAIS ou TRANSFERENCIA. Preenchida em 99,9% dos lancamentos. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 2, o principal para analise de gastos: ALIMENTACAO, TRANSPORTE, CASA, LAZER e outras - 14 valores. Preenchida em 99,4%. |
| ds_grupo | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 3, a mais fina: "Combustivel", "Lanche", "Estacionamento" e outros - 321 valores distintos. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | Quem pagou o gasto. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu - 1.044 valores distintos. E o campo mais proximo de um cadastro de fornecedores nesta base. |
| ds_forma_pgto | `varchar(50)` | Não | Descrição | Forma de pagamento. Sempre "C" nesta origem, por ser cartao de credito. |
| ds_descricao_pgto | `varchar(200)` | Não | Descrição | Descricao da forma de pagamento. Sempre "XP Credito" nesta origem. |
| ds_data_pgto | `varchar(50)` | Não | Descrição | DATA DE VENCIMENTO DA FATURA em que o gasto foi cobrado. E o campo que agrupa os gastos em faturas: sao 61 vencimentos distintos, dos quais 11 ainda futuros (parcelas a vencer). E tambem a ponte conceitual com o pagamento lancado na conta corrente. |
| ds_status_pgto | `varchar(20)` | Não | Descrição | Indicador de fatura paga: S para paga, N para a pagar. |
| ds_descricao_status_pgto | `varchar(50)` | Não | Descrição | Versao por extenso do status: "Pago" ou "A Pagar". Sao 3.767 itens ja pagos (R$ 273,1 mil) e 402 a pagar (R$ 31,5 mil). |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade onde o gasto ocorreu. Preenchida em 98,8% - bem melhor que na conta corrente, o que torna esta origem util para analise geografica. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre. Usada em 27,7% dos lancamentos, com marcadores como "#AleLia". |
| nr_ocorrencia | `int` | Sim | Número | Numero da ocorrencia da mesma combinacao de data, descricao, valor e fatura. Necessario porque o cartao nao tem saldo corrente para desempatar compras identicas - dois lanches iguais no mesmo dia sao dois gastos reais. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 de data da compra + descricao normalizada + valor tratado + data da fatura + numero da ocorrencia. Com constraint UNIQUE. |
| nm_arquivo_origem | `varchar(260)` | Sim | Nome | LINHAGEM: arquivo de origem. |
| nm_aba_origem | `varchar(120)` | Sim | Nome | LINHAGEM: aba de origem. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba de origem. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o evento entrou na base. |
| ds_id_origem | `varchar(30)` | Não | Descrição | CHAVE DE NEGOCIO. Identificador proprio do lancamento, digitado na coluna ID da planilha. Substitui a chave composta por data, descricao, valor tratado e data de pagamento. MOTIVO: alem da correcao de descricao e valor, a DATA DA FATURA muda com frequencia - um gasto lancado como sendo da fatura do mes X se revela, na conferencia contra o valor pago, ser do mes Y. Enquanto a data da fatura compunha a chave, esse acerto criava um lancamento novo em vez de mover o existente, e a conferencia nunca fechava. NUNCA REAPROVEITE UM ID de linha excluida. Unicidade imposta por indice unico. |

### bronze.dia_registro

BRONZE | Diario de habitos, uma linha por dia. Vem de um formulario do Google respondido quase diariamente desde janeiro de 2024, lido pela aba de respostas publicada como CSV. E a segunda origem do projeto que nao e arquivo. DIFERENTE DAS DEMAIS BASES, aqui nao ha dinheiro nem transacao: o grao e o dia inteiro, e as colunas sao respostas de formulario. Por isso a base vive em gold.fato_dia, sem nenhuma relacao com os fatos financeiros - o unico eixo que compartilham e o calendario, o que permite cruzar habito e gasto pela mesma data.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_registro** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_carimbo | `varchar(50)` | Sim | Descrição | CHAVE DE NEGOCIO. Momento em que o formulario foi enviado, atribuido pelo Google. E unico e imutavel, por isso identifica a resposta melhor que a data relatada, que e digitada a mao e pode ser corrigida depois. Na pratica o formulario e respondido na manha seguinte: a mediana de atraso e um dia. |
| ds_data | `varchar(50)` | Não | Descrição | Dia a que a resposta se refere, em formato ISO como texto. A origem entrega no formato brasileiro (14/08/2026) e a carga converte, porque o CSV nao carrega tipo. ATENCAO: e digitada a mao e ha erros de digitacao - duas respostas trazem anos impossiveis (1900 e 3025). A silver marca esses casos em fl_data_suspeita. |
| ds_treino | `varchar(20)` | Não | Descrição | Treino de musculacao no dia: Sim ou Nao. |
| ds_cardio | `varchar(20)` | Não | Descrição | Cardio no dia: Sim ou Nao. ATENCAO: a opcao do formulario foi reescrita em 2024 e o negativo convive em duas grafias, "Nao" e "Nao" com til. Sem unificar, o mesmo habito apareceria como tres respostas distintas. |
| ds_agua_litros | `varchar(20)` | Não | Descrição | UNICA MEDIDA NUMERICA da base: litros de agua no dia, entre 0,3 e 3,1. Chega no formato brasileiro, com virgula decimal. |
| ds_cafe_manha | `varchar(20)` | Não | Descrição | Cafe da manha. TRES ESTADOS, e nao dois: Sim, Nao e Jaca - esta ultima indicando refeicao feita fora do plano alimentar. Tratar Jaca como Nao esconderia a diferenca entre pular a refeicao e sair da dieta. |
| ds_almoco | `varchar(20)` | Não | Descrição | Almoco: Sim, Nao ou Jaca (fora do plano alimentar). |
| ds_lanche | `varchar(20)` | Não | Descrição | Lanche: Sim, Nao ou Jaca (fora do plano alimentar). |
| ds_janta | `varchar(20)` | Não | Descrição | Janta: Sim, Nao ou Jaca. E a refeicao que mais sai do plano - quase metade das respostas. |
| ds_ceia | `varchar(20)` | Não | Descrição | Ceia: Sim, Nao ou Jaca. E a refeicao mais frequentemente pulada. |
| ds_dia_produtivo | `varchar(20)` | Não | Descrição | Avaliacao do dia: Normal, Sim ou Nao. NAO E BOOLEANO - Normal e a resposta padrao e responde por oito de cada dez dias; Sim significa dia acima da media. |
| ds_trabalho | `varchar(20)` | Não | Descrição | Houve trabalho no dia: Sim ou Nao. |
| ds_nina_em_casa | `varchar(20)` | Não | Descrição | A filha esteve em casa no dia: Sim ou Nao. |
| ds_estresse | `varchar(20)` | Não | Descrição | Houve discussao no dia: Sim ou Nao. |
| ds_lazer | `varchar(20)` | Não | Descrição | Houve momento a dois no dia: Sim ou Nao. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DA RESPOSTA. SHA-256 do carimbo do formulario. Diferente das demais bronzes, que combinam data, descricao e valor: aqui a origem ja fornece um identificador unico e estavel, entao usar qualquer outro campo so introduziria fragilidade. Com constraint UNIQUE: e o banco que impede a duplicacao. |
| nm_origem | `varchar(120)` | Sim | Nome | LINHAGEM: identifica a origem do dado - a aba de respostas do formulario publicada como CSV, e nao um arquivo. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha no CSV, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando a resposta entrou ou foi atualizada na base. |

### bronze.familia_movimentacao

BRONZE | Gastos em comum de Ale e Lia, lidos direto de uma aba do Google Sheets publicada como CSV. E a primeira origem do projeto que nao e arquivo: nao existe etapa manual de exportar, e o dado carregado e o mesmo que o Power BI ja consome. Os dois fazem aportes mensais para as contas conjuntas, e a base existe para dar transparencia de quem pagou o que. NAO se confunde com as transferencias pessoais para a conta familia, que ficam em silver.itau_movimentacao: sao assuntos independentes, e por isso a familia tem fato proprio em vez de entrar em gold.fato_movto_financ.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_movimentacao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data do lancamento, em formato ISO como texto. A origem entrega no formato brasileiro (17/04/2021) e a carga converte, porque o CSV nao carrega tipo. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do gasto, escrita a mao ("Combustivel", "Pedagios BSB > BH"). Como no cartao, e texto seu e nao codigo de banco - por isso esta origem ja vem bem classificada. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor como digitado na planilha, ja convertido do formato brasileiro. A convencao esperada e despesa positiva, mas em alguns lancamentos ela foi digitada negativa - ver ds_valor_tratado. |
| ds_valor_tratado | `varchar(50)` | Não | Descrição | METRICA DA ORIGEM. Calculado na planilha como o negativo de ds_valor, o que da despesa negativa e receita positiva. ATENCAO: quando o valor foi digitado ja negativo, a formula inverte para positivo e a despesa vira receita. Sao poucos casos, todos de reforma da casa, e a silver os marca em fl_sinal_divergente. |
| ds_tipo_movimentacao | `varchar(50)` | Não | Descrição | DESPESA ou RECEITA, conforme digitado. Aparece com variacoes de caixa ("Despesa", "DEspesa", "DeSPESA") que a silver unifica. |
| ds_area | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 1: GASTOS ESSENCIAIS, ESTILO DE VIDA ou RECEITA. Mesmo vocabulario das demais origens do projeto. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 2, o principal para analise. Tem 18 valores, alguns exclusivos da familia: MORADIA, DIARISTA, INTERNET, ORGANIZACAO, HOSPEDAGEM e CUIDADOS PESSOAIS nao aparecem nas origens pessoais. |
| ds_grupo | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 3, o mais fino: "Aluguel", "Manutencao", "IPTU", "Reforma". |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | QUEM PAGOU - o campo que motiva esta base. Vale ALE, LIA, Conta (quando saiu da conta conjunta) ou o nome de um terceiro. Aparece com variacao de caixa ("ALE" e "Ale") que a silver unifica, senao viram duas pessoas na dimensao. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. Mais de 400 valores distintos, por isso fica como atributo do fato e nao vira dimensao. |
| ds_forma_pgto | `varchar(50)` | Não | Descrição | Forma de pagamento: C para credito, D para debito, entre outras. |
| ds_descricao_pgto | `varchar(200)` | Não | Descrição | Descricao da forma de pagamento, indicando o cartao ou conta usada. |
| ds_data_pgto | `varchar(50)` | Não | Descrição | Data em que o gasto foi efetivamente pago, quando difere da data do lancamento. |
| ds_status_pgto | `varchar(20)` | Não | Descrição | Indicador de pagamento: S para pago, N para a pagar. |
| ds_descricao_status_pgto | `varchar(50)` | Não | Descrição | Versao por extenso do status de pagamento. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto, preenchida na quase totalidade dos lancamentos. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre. Usada para marcar contexto, como "Viagem01_Litoral". |
| ds_pgto_mes | `varchar(20)` | Não | Descrição | Mes de pagamento, calculado na planilha. Redundante com ds_data_pgto, mantido por fidelidade a origem. |
| ds_pgto_ano | `varchar(20)` | Não | Descrição | Ano de pagamento, calculado na planilha. Redundante com ds_data_pgto. |
| nr_ocorrencia | `int` | Sim | Número | Numero da ocorrencia da mesma combinacao de data, descricao e valor. Necessario porque nao ha saldo corrente para desempatar: dois abastecimentos iguais no mesmo dia sao dois gastos reais. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 de data + descricao normalizada + valor + numero da ocorrencia. Com constraint UNIQUE: e o banco que impede a duplicacao. |
| nm_origem | `varchar(120)` | Sim | Nome | LINHAGEM: identifica a origem do dado. Diferente das outras bronzes, aqui nao e um nome de arquivo - e a aba publicada do Google Sheets. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha no CSV, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o evento entrou ou foi atualizado na base. |

### bronze.financ_historico

BRONZE | Historico financeiro consolidado a mao, de fevereiro/2014 a maio/2018. E o periodo ANTERIOR as origens atuais - o Itau comeca em out/2016 e os cartoes em mai/2018 - e por isso estende a serie em dois anos e meio para tras, cobrindo uma epoca em que o gasto passava por dinheiro, vale-alimentacao e cartoes que nao existem mais. VERIFICADO ANTES DE CARREGAR: nao ha sobreposicao com o que ja estava na base. Nenhum lancamento posterior ao inicio do Itau repete data, valor e descricao de algo existente, e as formas de pagamento aqui sao outras.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_lancamento** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_id_origem | `varchar(30)` | Sim | Descrição | CHAVE DE NEGOCIO. Identificador digitado na coluna ID da planilha. Esta base segue editavel, e o ID e o que permite corrigir descricao, valor ou data depois sem criar um registro novo - o mesmo desenho ja usado no Itau e no cartao XP. Ao contrario daquelas duas, aqui o ID existe desde a primeira carga, entao nao houve migracao de chave. NUNCA REAPROVEITE UM ID de linha excluida. |
| ds_data | `varchar(50)` | Não | Descrição | Data do lancamento, em formato ISO como texto. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do lancamento, escrita a mao. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor como digitado, sem sinal de despesa. Ver ds_valor_tratado. |
| ds_valor_tratado | `varchar(50)` | Não | Descrição | METRICA DA ORIGEM. Valor com sinal: negativo para despesa, positivo para receita. E a coluna que alimenta o fato. |
| ds_tipo_movimentacao | `varchar(30)` | Não | Descrição | Despesa, Receita ou META. ATENCAO AO TERCEIRO: as 287 linhas marcadas como Meta nao sao movimentacao, e sim orcamento mensal planejado - 24 por categoria, somando +R$ 135.522. Ficam aqui por fidelidade a origem, a silver as marca em fl_meta e o fato as exclui. |
| ds_forma_pagamento | `varchar(60)` | Não | Descrição | Instrumento usado: Dinheiro/Debito, visa BB, Vale Alimentacao, Visa/CTI ou Diners. Nenhum deles e Itau, XP ou Nubank - foi o que permitiu concluir que esta base nao duplica as demais. Vazio em 877 linhas, que caem no membro nao informado da dimensao de origem. |
| ds_data_pgto | `varchar(50)` | Não | Descrição | Data do pagamento efetivo, quando difere da data do lancamento. |
| ds_status_pgto | `varchar(20)` | Não | Descrição | Indicador de pagamento: S para pago, N para a pagar. Aparece tambem em minuscula, que a silver unifica. |
| ds_area | `varchar(100)` | Não | Descrição | VAZIA EM TODAS AS LINHAS nesta origem. Preservada para que a bronze continue sendo copia fiel da planilha; a area usada na analise e derivada na silver, a partir da categoria e do grupo, com a procedencia registrada. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 2. Sao 15 valores, dos quais tres nao existem nas origens atuais: AJUSTE, FINANCAS e Telefonia. |
| ds_grupo | `varchar(100)` | Não | Descrição | CLASSIFICACAO nivel 3, o mais fino. Sao 172 valores. |
| ds_pessoa_pagar | `varchar(120)` | Não | Descrição | Quem pagou, como registrado na planilha. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. |
| ds_obs | `varchar(500)` | Não | Descrição | Observacao livre. NAO ALIMENTA gold.dim_tag, diferente do OBS das demais origens: aqui o campo guarda numeros soltos como "-160" e "556.37", que o interpretador de marcacoes leria como tag. Nesta base quem marca contexto e ds_projeto. |
| ds_projeto | `varchar(100)` | Não | Descrição | MARCACAO DE CONTEXTO desta origem: Compacto, Hatch 2008, Viagem Exterior, Sedan 2016. E esta coluna, e nao ds_obs, que alimenta gold.dim_tag - o que liga o gasto antigo aos mesmos eixos de viagem e veiculo das origens atuais. |
| ds_tag | `varchar(100)` | Não | Descrição | Coluna Tag da planilha, vazia em todas as linhas. Preservada por fidelidade. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO LANCAMENTO. SHA-256 do ID da planilha. Com constraint UNIQUE: e o banco que impede a duplicacao. |
| nm_arquivo_origem | `varchar(200)` | Sim | Nome | LINHAGEM: nome do arquivo de onde o lancamento veio. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento entrou ou foi atualizado na base. |

### bronze.itau_movimentacao

BRONZE | Movimentacoes da conta corrente do Itau, uma linha por evento real, desde 2016. Alimentada pela aba "cad-conta" de dados-itau.xlsx (semente do historico, ja com classificacao manual) e pela aba de extrato baixada do banco (incremento, apenas data/descricao/valor). A carga insere somente eventos cujo hash_negocio ainda nao existe. Linhas em branco da planilha - resquicio de formula arrastada, sem data nem valor - sao descartadas na carga.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_movimentacao** | `int` | Sim | Chave técnica | Chave tecnica sequencial, sem significado de negocio. |
| ds_data | `varchar(50)` | Não | Descrição | Data do lancamento em formato ISO como texto. Convertida para date na silver. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do lancamento como o Itau a gera, sem padronizacao. Ex: "LOJA-EXEMPLO*CAT-", "PIX TRANSF FULANO14/05", "TBI 0000.00000-0/500". Muitas embutem data e nome parcial do estabelecimento, o que as torna quase unicas e dificulta deduzir categoria automaticamente. |
| ds_valor | `varchar(50)` | Não | Descrição | Valor do lancamento em reais, como texto. Positivo = entrada na conta, negativo = saida. |
| ds_valor_tratado | `varchar(50)` | Não | Descrição | Valor apos ajuste manual feito na planilha. Costuma repetir ds_valor; difere quando houve correcao ou rateio. Preenchido tambem em linhas onde ds_valor esta vazio. |
| ds_tipo_movimentacao | `varchar(50)` | Não | Descrição | Natureza informada na planilha: Receita, Despesa ou "Saldo Conta". ATENCAO: "Saldo Conta" NAO e transacao - sao 141 marcadores de saldo final ou parcial anotados no extrato. A silver os separa e a gold os exclui, senao seriam somados como se fossem movimentacao. |
| ds_area | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL, nivel 1 (mais amplo): TRANSFERENCIA, ESTILO DE VIDA, RENDA, GASTOS ESSENCIAIS, TAXA, EMPRESTIMO, VENDA, INVESTIMENTO e outros. Vazio em cerca de 40% da serie, quase toda anterior a 2024. |
| ds_categoria | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL, nivel 2: TRANSFERENCIA, RENDIMENTO, TRABALHO, CASA, TRANSPORTE, ALIMENTACAO, EDUCACAO e outros - 38 valores distintos. E o nivel usado para analise de gastos. A cobertura salta de cerca de 55% ate 2023 para 99% em 2024 e 2025. |
| ds_grupo | `varchar(100)` | Não | Descrição | CLASSIFICACAO MANUAL, nivel 3 (mais fino): 155 valores como "Movimentacao entre contas", "Combustivel", "Escola Nina", "Almoco". E o nivel de detalhe para acompanhar metas por assunto. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | Quem pagou o lancamento, na anotacao manual da planilha. |
| ds_pessoa_receber | `varchar(100)` | Não | Descrição | Quem recebeu o lancamento, na anotacao manual da planilha. |
| ds_forma_pgto | `varchar(50)` | Não | Descrição | Forma de pagamento anotada na planilha (T = transferencia, entre outras). |
| ds_descricao_pgto | `varchar(200)` | Não | Descrição | Descricao da forma de pagamento, complementando ds_forma_pgto. |
| ds_data_pgto | `varchar(50)` | Não | Descrição | Data do pagamento efetivo, quando diferente da data do lancamento. |
| ds_status_pgto | `varchar(50)` | Não | Descrição | Status do pagamento. Coluna existe na planilha mas nunca foi preenchida - mantida por fidelidade a origem. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade onde ocorreu o gasto. Preenchida em cerca de 19% dos lancamentos. |
| ds_uf | `varchar(20)` | Não | Descrição | Unidade federativa do gasto. Preenchida em cerca de 19% dos lancamentos. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. Preenchido em cerca de 19% dos lancamentos, util para separar gastos de viagem. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre anotada na planilha. Preenchida em cerca de 6% dos casos. |
| ds_projeto | `varchar(100)` | Não | Descrição | Projeto ao qual o gasto se vincula. Praticamente nao utilizado (8 lancamentos). |
| ds_tag | `varchar(100)` | Não | Descrição | Marcador livre para agrupar lancamentos fora da hierarquia de categoria. |
| nr_ocorrencia | `int` | Sim | Número | Numero da ocorrencia da combinacao data + descricao + valor naquele dia. Vale 1 na primeira vez, 2 na segunda e assim por diante. EXISTE PORQUE O EXTRATO DO ITAU NAO TRAZ SALDO: sem ele, duas compras identicas no mesmo dia seriam indistinguiveis e uma das duas se perderia na deduplicacao. Com o contador, se o extrato traz duas e a base ja tem duas, elas casam; se a base tem uma, a segunda entra como nova. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 de data + descricao normalizada + valor + numero da ocorrencia. Tem constraint UNIQUE: e o banco que impede duplicacao, nao o script de carga. |
| nm_arquivo_origem | `varchar(260)` | Sim | Nome | LINHAGEM: arquivo em que o evento foi visto pela primeira vez. |
| nm_aba_origem | `varchar(120)` | Sim | Nome | LINHAGEM: aba de origem. Registrada porque a aba de extrato muda de nome a cada download - traz a data no titulo, como "Extrato Conta Corrente-12072026" - e guardar o nome permite saber de qual extrato o dado veio. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha na aba de origem, a partir de 1 apos o cabecalho. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: data e hora em que o evento entrou na base. |
| ds_id_origem | `varchar(30)` | Não | Descrição | CHAVE DE NEGOCIO. Identificador proprio do lancamento, digitado na coluna ID da planilha. Substitui a chave composta por data, descricao e valor que vigorava antes. MOTIVO: esta base e cadastrada a mao e esses tres campos sao justamente os que mais precisam de correcao posterior - lancar na pressa e completar depois e o uso normal. Enquanto eles compunham a chave, corrigir qualquer um deles criava um registro novo e deixava o antigo orfao, inflando os totais em silencio. Com um identificador sem significado, tudo o mais e atualizavel e a correcao chega ate a gold. NUNCA REAPROVEITE UM ID de linha excluida: o lancamento novo herdaria os dados do antigo. Unicidade imposta por indice unico. |

### bronze.xp_movimentacao

BRONZE | Movimentacoes financeiras da conta XP, uma linha por evento real. Alimentada por duas origens: a planilha mestre dados-xp.xlsx (semente do historico desde 2021) e os arquivos de extrato baixados no app da corretora (incrementos). Como o extrato e baixado varias vezes por mes sempre cobrindo o mes anterior, os arquivos se sobrepoem muito; a carga insere apenas eventos cujo hash_negocio ainda nao existe. A unicidade e imposta pelo banco. Nao ha conversao de tipo aqui - isso e trabalho da silver.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id_movimentacao** | `int` | Sim | Chave técnica | Chave tecnica sequencial. Sem significado de negocio; para relacionar dados entre camadas use hash_negocio. |
| ds_movimentacao | `varchar(50)` | Não | Descrição | Data em que a movimentacao ocorreu (fato economico), em formato ISO como texto. Convertida para date na silver. |
| ds_liquidacao | `varchar(50)` | Não | Descrição | Data em que o dinheiro entrou ou saiu da conta, em formato ISO como texto. Pode ser posterior a movimentacao (ex: bolsa liquida em D+2). Use esta data para fluxo de caixa e a de movimentacao para resultado. |
| ds_lancamento | `varchar(1000)` | Não | Descrição | Descricao textual do lancamento gerada pela XP, sem padronizacao. E o campo do qual a silver deriva a categoria e o ativo. Ex: "DIVIDENDOS DE CLIENTES ALOS3 S/". |
| ds_valor | `varchar(50)` | Não | Descrição | Valor da transacao em reais, como texto com 2 casas. Positivo indica entrada (dividendo, resgate, rendimento) e negativo indica saida (compra, taxa, imposto). |
| ds_saldo | `varchar(50)` | Não | Descrição | Saldo da conta apos o lancamento, como texto com 2 casas. Alem do valor informativo, e o campo que distingue duas transacoes identicas no mesmo dia: transacoes reais movem o saldo, linhas repetidas mantem o mesmo saldo. Por isso participa do hash_negocio. |
| ds_categoria_origem | `varchar(100)` | Não | Descrição | Categoria que ja vinha preenchida manualmente na planilha mestre. Preenchida apenas para eventos vindos dela; nula para eventos novos vindos do extrato. Serve como referencia historica e como gabarito para conferir as regras automaticas - a silver recalcula a categoria para toda a serie. |
| ds_rendimento_origem | `varchar(10)` | Não | Descrição | Marcacao manual de rendimento ("S") herdada da planilha mestre. Nula para eventos vindos do extrato. |
| ds_ativo_origem | `varchar(200)` | Não | Descrição | Ativo informado manualmente na planilha mestre (ticker, CDB, fundo, Tesouro). Nulo para eventos vindos do extrato. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DO EVENTO. SHA-256 da chave de negocio normalizada: data de movimentacao + data de liquidacao + descricao (sem acento, maiuscula, espacos colapsados) + valor + saldo. Duas linhas com o mesmo hash sao o mesmo evento financeiro, venham do arquivo que vierem. Tem constraint UNIQUE: e o banco que impede a duplicacao, nao o script de carga. |
| nm_arquivo_origem | `varchar(260)` | Sim | Nome | LINHAGEM: nome do arquivo em que o evento foi visto pela PRIMEIRA vez. Como o mesmo lancamento aparece em varios extratos, este campo registra a origem que de fato trouxe o dado para a base, nao todas em que ele aparece. |
| nr_linha_arquivo | `int` | Não | Número | LINHAGEM: posicao da linha dentro do arquivo de origem, a partir de 1 apos o cabecalho. Permite auditar um registro abrindo o arquivo original. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: data e hora em que o evento entrou na base. Como a carga so insere novidades, este campo mostra quando cada movimentacao foi descoberta. |

## silver

Dados tipados, classificados e com vocabulário padronizado. Uma tabela por entidade de negócio.

### silver.auto_intervalo_troca

SILVER | Intervalo recomendado de troca por categoria, em quilometros, tipado. Tabela de referencia, e nao de eventos: uma linha por categoria. Cruzada com o historico, responde o que esta vencendo em cada veiculo.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_intervalo** | `int` | Sim | Chave substituta | Chave substituta do intervalo. |
| ds_categoria | `varchar(100)` | Sim | Descrição | Categoria de manutencao, com a grafia unificada - a mesma de silver.auto_manutencao. |
| nr_intervalo_km | `int` | Não | Número | Quilometros entre trocas: 5.000 para oleo, 10.000 para filtro e alinhamento, 50.000 para amortecedor e correia. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade, herdada da bronze. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.auto_manutencao

SILVER | Revisoes e manutencoes do automovel, limpas e tipadas. Uma linha por item de cada visita a oficina. DOIS VEICULOS com hodometros independentes: o Sedan ate novembro de 2025 e o SUV desde entao. Nunca compare ou some quilometragem entre eles. Alimenta gold.fato_manutencao_auto.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_manutencao** | `int` | Sim | Chave substituta | Chave substituta do lancamento. A identidade estavel e hash_negocio. |
| dt_manutencao | `date` | Sim | Data | Data da ida a oficina. |
| nm_veiculo | `varchar(60)` | Sim | Nome | Veiculo: Sedan ou SUV. |
| nr_visita | `int` | Sim | Número | Numero sequencial da visita a oficina, contado POR VEICULO. Uma visita rende varias linhas - pecas e mao de obra na mesma nota - e esta coluna permite somar "quanto custou aquela revisao" sem agrupar por data solta. |
| nr_km | `int` | Não | Número | Quilometragem do veiculo na data. E O EIXO DA MANUTENCAO PREVENTIVA: desgaste se mede em rodagem, nao em calendario. Cada veiculo tem sua propria escala. |
| ds_natureza | `varchar(30)` | Não | Descrição | Natureza declarada na origem: Revisão (programada) ou Manutenção (conserto). |
| fl_preventiva | `bit` | Sim | Indicador (sim/não) | 1 quando foi manutencao programada, 0 quando foi conserto. Separa o gasto que se planeja do que aparece - a proporcao entre os dois diz se a manutencao esta sendo preventiva de fato ou so reagindo a quebra. |
| ds_tipo | `varchar(30)` | Não | Descrição | Produto (peca) ou Serviço (mao de obra). |
| ds_item | `varchar(200)` | Não | Descrição | Descricao do item ou servico, preservada para auditoria. Texto livre, com 110 variacoes - use ds_categoria para analisar. |
| ds_categoria | `varchar(100)` | Sim | Descrição | CLASSIFICACAO em 34 categorias, com a grafia unificada: a origem trazia "Mão de Obra" e "Mão de obra" como se fossem duas. |
| fl_tem_intervalo | `bit` | Sim | Indicador (sim/não) | 1 quando a categoria tem intervalo de troca definido em quilometros e portanto entra na previsao de vencimento. As 21 categorias sem intervalo sao corretivas - nao se troca bandeja, lampada ou mao de obra por rodagem. |
| nr_quantidade | `decimal(10,2)` | Não | Número | Quantidade de unidades do item. |
| vl_gasto | `decimal(12,2)` | Não | Valor (métrica) | METRICA. Valor pago em reais, total do item. Positivo: e sempre despesa, entao nao carrega sinal como os fatos financeiros. |
| ds_local | `varchar(120)` | Não | Descrição | Oficina ou loja onde foi feito. |
| ds_observacao | `varchar(500)` | Não | Descrição | Observacao livre da origem. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da bronze. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.auto_revisao_programada

SILVER | O plano do fabricante tipado: intervalo em km e em meses como numero, acao num dominio fechado. Uma linha por item do plano. Alimenta gold.dim_revisao_programada e, por ela, a previsao de vencimento.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id** | `int` | Sim | Outro | Chave tecnica da linha na silver. |
| nm_modelo | `varchar(120)` | Sim | Nome | Modelo a que o plano se refere. |
| nm_item | `varchar(200)` | Sim | Nome | Item ou componente, na grafia do fabricante. |
| nm_sistema | `varchar(120)` | Não | Nome | Sistema do veiculo a que o item pertence. |
| nr_intervalo_km | `int` | Não | Número | Quilometros entre uma intervencao e a proxima. |
| nr_intervalo_meses | `int` | Não | Número | Meses entre uma intervencao e a proxima. Vale EM PARALELO ao intervalo em km: o fabricante manda seguir o que vencer primeiro. |
| ds_acao | `varchar(30)` | Não | Descrição | Troca, Inspeção ou Serviço. O unico item ambiguo na origem e a correia Poly-V, marcada "Inspecao / Troca", que vira Inspeção: o que esta agendado e a inspecao, a troca e consequencia dela. |
| ds_especificacao | `varchar(500)` | Não | Descrição | Especificacao tecnica da peca ou do fluido. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do item, herdada da bronze. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o item foi carregado na silver. |

### silver.avaliacao_fisica

SILVER | Avaliacoes fisicas tipadas, uma linha por avaliacao e por metrica. A serie vai de 2008 a 2026 mas NAO E HOMOGENEA: ate 2013 o laudo trazia circunferencias e pressao arterial; de 2018 em diante e bioimpedancia. So cinco metricas existem nas duas eras, e FL_SERIE_CONTINUA as identifica. Alimenta gold.fato_avaliacao_fisica.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_medicao** | `int` | Sim | Chave substituta | Chave substituta da medicao. A identidade estavel e hash_negocio. |
| dt_avaliacao | `date` | Sim | Data | Data da avaliacao. As avaliacoes sao IRREGULARES: ha intervalos de um mes e intervalos de mais de tres anos, entre 2013 e 2018 e entre 2019 e 2022. Qualquer media por periodo precisa considerar isso. |
| nr_avaliacao | `int` | Sim | Número | Numero sequencial da avaliacao, de 1 a 31 em ordem de data. Existe porque a pergunta natural e "como estou em relacao a avaliacao anterior", e o intervalo entre elas e irregular - comparar pela data exige saber qual foi a anterior, e esta coluna responde direto. |
| ds_era | `varchar(30)` | Sim | Descrição | Era de medicao: "Ate 2013" para o laudo completo com circunferencias e pressao, "2018 em diante" para a bioimpedancia. Separa o que e comparavel do que nao e. |
| ds_grupo | `varchar(100)` | Sim | Descrição | Agrupamento da metrica, herdado do laudo. Substitui a coluna CLASSE da origem, que era inconsistente. |
| ds_metrica | `varchar(100)` | Sim | Descrição | Nome da metrica medida. ATENCAO: "Massa Muscular" e "Massa Muscular/Ossea" sao metricas DIFERENTES e nunca coexistem - a segunda inclui massa ossea e fica na faixa de 52 a 57 kg contra 30 a 33 kg da primeira. Somar ou plotar as duas como uma serie mostra uma queda de 25 kg que nunca aconteceu. |
| ds_unidade | `varchar(20)` | Não | Descrição | Unidade da metrica: Kg, cm, %, L, bpm, mmHg, Pontos, Imc. Cada metrica usa sempre a mesma. NUNCA agregue medidas de unidades diferentes na mesma conta. |
| vl_medida | `decimal(10,2)` | Não | Valor (métrica) | METRICA. Valor medido. Nulo quando a medida constava do laudo mas nao foi feita. |
| fl_medido | `bit` | Sim | Indicador (sim/não) | 0 quando a linha existe no laudo mas ficou sem valor. Sao 12 casos, dos quais seis sao "Busto", que nunca foi medido nenhuma vez. Distingue "nao foi medido" de "nao consta do laudo", que sao coisas diferentes. |
| fl_serie_continua | `bit` | Sim | Indicador (sim/não) | 1 quando a metrica aparece nas DUAS eras e portanto sustenta um grafico de 2008 a 2026 sem buraco. Sao cinco: Peso, IMC, % Gordura, Massa Gordura e Estatura. Para o painel de evolucao de longo prazo, filtre por esta coluna - as demais metricas produzem linhas que comecam ou terminam no meio do grafico. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade da medicao, herdada da bronze: hash de data + metrica. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.avaliacao_inbody

SILVER | Os exames InBody tipados, uma linha por exame, metrica e SEGMENTO. O segmento entra na chave porque a analise segmentar mede o mesmo indicador em cinco lugares do corpo, e e ela que responde onde falta musculo - o dado que o preenchimento manual nunca capturou. Valor implausivel nao chega aqui: e descartado na leitura, com o motivo registrado. Buraco visivel e melhor que numero plausivel e errado.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **id** | `int` | Sim | Outro | Chave tecnica da linha na silver. |
| dt_exame | `date` | Sim | Data | Data do exame, lida do cabecalho. ATENCAO AO FORMATO: os exames ate 2019 imprimem ano na frente (2018.06.05) e os novos, dia na frente (28.08.2026). |
| nm_metrica | `varchar(100)` | Sim | Nome | Nome da metrica, na mesma grafia de gold.dim_metrica_corporal - e o que permite as duas origens caírem na mesma linha do fato. |
| nm_segmento | `varchar(40)` | Sim | Nome | Parte do corpo: Braço esquerdo, Braço direito, Tronco, Perna esquerda, Perna direita. Vale "Corpo inteiro" nas metricas que nao sao segmentares - e a resposta certa para peso ou IMC, e nao um dado faltando. |
| vl_medida | `decimal(10,2)` | Não | Valor (métrica) | Valor medido, na unidade da metrica. |
| vl_referencia_min | `decimal(10,2)` | Não | Valor (métrica) | Limite inferior da faixa de referencia que o exame imprime ao lado do valor. MUDA A CADA EXAME porque depende de idade e altura, entao e dado do fato e nao constante da dimensao. Nulo quando o OCR nao leu a faixa com seguranca. |
| vl_referencia_max | `decimal(10,2)` | Não | Valor (métrica) | Limite superior da faixa de referencia do exame. |
| ds_avaliacao | `varchar(20)` | Não | Descrição | Como a propria maquina classifica o valor: Abaixo, Normal ou Acima. So existe nas metricas segmentares. |
| ds_template | `varchar(40)` | Não | Descrição | Versao do leiaute de onde a medida veio. |
| nm_arquivo | `varchar(200)` | Não | Nome | LINHAGEM: arquivo de origem. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | IDENTIDADE DA MEDIDA. SHA-256 de data + metrica + segmento. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando a medida foi carregada na silver. |

### silver.cartao_movimentacao

SILVER | Gastos de cartao de credito, limpos e tipados, de todos os cartoes. DS_CARTAO identifica a origem. Sao os lancamentos ANALITICOS do modelo de movimentacao: cada compra individual. O pagamento da fatura, lancado na conta corrente, e o SINTETICO correspondente - somar os dois contaria a mesma despesa duas vezes. Diferente da conta corrente, esta origem vem quase toda classificada na propria planilha, porque a descricao e escrita por voce e nao pelo banco.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_movimentacao** | `int` | Sim | Chave substituta | Chave substituta do lancamento. A identidade estavel e hash_negocio. |
| ds_cartao | `varchar(30)` | Sim | Descrição | Cartao de origem do gasto: XP ou Nubank. Permite comparar o padrao de consumo entre cartoes e emendar as duas series, que nao se sobrepoem no tempo. |
| dt_compra | `date` | Não | Data | Data em que a COMPRA foi feita. Use para responder "quanto gastei em julho". Nao confundir com dt_fatura: uma compra de julho pode ser cobrada em agosto. |
| dt_fatura | `date` | Não | Data | Data de vencimento da FATURA em que o gasto foi cobrado. Use para conciliar com o pagamento lancado na conta corrente e para fluxo de caixa. Uma compra parcelada tem uma data de compra e varias de fatura, parte delas ainda futuras. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do gasto, escrita manualmente ("Lanche Nina", "Gasolina"). E o que torna esta origem muito mais classificavel que o extrato bancario. |
| nr_parcela | `int` | Não | Número | Numero da parcela, quando a compra foi parcelada. Nulo em compra a vista. E o que explica faturas com vencimento futuro. |
| vl_transacao | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor do lancamento em reais, com sinal: negativo e gasto, positivo e estorno. Vem da coluna "Valor Trat" da planilha, e nao de "Valor", cujo sinal e inconsistente nos estornos. |
| ds_tipo_movimentacao | `varchar(20)` | Não | Descrição | RECEITA para valores positivos (estornos) e DESPESA para negativos. |
| ds_area | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 1: ESTILO DE VIDA, GASTOS ESSENCIAIS, TRANSFERENCIA. Mesmo vocabulario da conta corrente, o que permite somar as duas origens. |
| ds_categoria | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 2, o principal para analise de gastos: ALIMENTACAO, TRANSPORTE, CASA, LAZER e outras. Vale "A classificar" quando ausente - raro nesta origem. |
| ds_grupo | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 3, a mais fina: "Combustivel", "Lanche", "Estacionamento". |
| fl_classificado | `bit` | Sim | Indicador (sim/não) | Marca 1 quando o lancamento tem categoria vinda da planilha. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | Quem pagou o gasto. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. E o campo mais proximo de um cadastro de fornecedores nesta base. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto. Muito mais preenchida aqui que na conta corrente, o que torna o cartao a melhor origem para analise geografica de consumo. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. Util para isolar consumo em viagem. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre anotada na planilha. |
| fl_pago | `bit` | Sim | Indicador (sim/não) | Marca 1 quando a fatura correspondente ja foi paga e 0 quando ainda vai vencer. Permite separar o que ja saiu do bolso do que esta comprometido - util porque compras parceladas geram faturas futuras. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da bronze. Inclui a data da fatura, porque cada parcela de uma compra parcelada e um evento proprio. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |
| fl_pagamento_fatura | `bit` | Sim | Indicador (sim/não) | Marca 1 quando a linha e o PAGAMENTO DA FATURA e nao um gasto. Ocorre apenas na origem Nubank, cujo arquivo traz os 48 pagamentos misturados ao consumo - somados, eles anulam os gastos e a serie de 4 anos aparenta R$ 2.310 em vez de R$ 122.168. E o lancamento PAI da fatura, do qual os gastos sao os FILHOS. SEMPRE filtre por fl_pagamento_fatura = 0 ao somar despesa de cartao. |

### silver.de_para_categoria_itau

SILVER | De-para de categorias por padrao de operacao da conta Itau. Alimentada pela planilha revisao-categorias-itau.xlsx, preenchida a mao. Cada linha rotula um padrao (a descricao sem numeros nem datas) e vale para todos os lancamentos que casam com ele, no historico e nas cargas futuras. Nunca sobrescreve classificacao existente: so preenche o que esta como "A classificar".

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **ds_padrao** | `varchar(300)` | Sim | Descrição | Padrao da operacao: a descricao do lancamento sem numeros, datas e pontuacao. Ex: "PIX TRANSF ALEXAND" cobre "PIX TRANSF ALEXAND12/01" e "PIX TRANSF  ALEXAND10/08". E a chave da tabela. |
| ds_area | `varchar(100)` | Não | Descrição | Area atribuida ao padrao na revisao manual. Nulo significa que o padrao foi listado mas ainda nao rotulado. |
| ds_categoria | `varchar(100)` | Não | Descrição | Categoria atribuida ao padrao na revisao manual - o nivel principal de analise. |
| ds_grupo | `varchar(100)` | Não | Descrição | Grupo atribuido ao padrao na revisao manual - o nivel mais fino. |
| nr_ocorrencias | `int` | Não | Número | Quantos lancamentos casavam com este padrao quando a lista foi gerada. Serve para priorizar a revisao, nao para calculo. |
| vl_volume | `decimal(18,2)` | Não | Valor (métrica) | Volume absoluto em reais que este padrao representava quando a lista foi gerada. Serve para priorizar a revisao pelo que pesa no bolso. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o rotulo entrou na tabela. |

### silver.de_para_categoria_nubank

SILVER | De-para das 12 categorias do proprio Nubank para o vocabulario usado nas demais origens. Existe porque o cartao Nubank tem apenas 2% de classificacao manual, mas 91% de categorizacao feita pelo banco: mapear 12 linhas resolve 2.135 lancamentos. Enquanto uma categoria nao for mapeada, os lancamentos dela ficam como "A classificar".

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **ds_categoria_nubank** | `varchar(60)` | Sim | Descrição | Categoria como o Nubank a atribuiu: restaurante, transporte, supermercado, servicos, vestuario, viagem, casa, eletronicos, lazer, educacao, saude, outros. |
| ds_area | `varchar(100)` | Não | Descrição | Area correspondente no seu vocabulario. Nulo enquanto nao mapeada. |
| ds_categoria | `varchar(100)` | Não | Descrição | Categoria correspondente no seu vocabulario. Nulo enquanto nao mapeada. |
| ds_grupo | `varchar(100)` | Não | Descrição | Grupo correspondente no seu vocabulario. Nulo enquanto nao mapeado. |
| nr_lancamentos | `int` | Não | Número | Quantos lancamentos do cartao usam esta categoria. Serve para priorizar. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o mapeamento entrou na tabela. |

### silver.de_para_classe_ativo

REFERENCIA | Classificacao dos ativos em classe e subclasse, definida a mao. E dado de referencia (o que o instrumento e), nao dado pessoal (quanto se tem), por isso vive no repositorio e nao numa planilha. A subclasse e mais fina que o TP_ATIVO deduzido por regra: separa CDB pos de pre-fixado e direito de subscricao da cota do FII - distincoes que nenhuma regra automatica extrairia do texto do extrato.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **cd_ativo** | `varchar(200)` | Sim | Código | Codigo do ativo, igual ao CD_ATIVO de gold.dim_ativo. Inclui grafias antigas (ex: "BTC ITUB") e atuais ("BTC ITUB4") para o de-para continuar valendo se uma regra de extracao mudar. |
| ds_classe | `varchar(60)` | Sim | Descrição | Classe do ativo, o nivel mais amplo: Renda Fixa, Renda Variavel, Fundos Imobiliarios, Fundos de Investimento, Emprestimo de Ativos ou Operacoes Estruturadas. E o nivel para analisar alocacao de patrimonio. |
| ds_subclasse | `varchar(60)` | Sim | Descrição | Subclasse do ativo, o nivel de detalhe: CDB Pos-Fixado, CDB Pre-Fixado, Acoes, FII, Direito de Subscricao FII, CRI, LCA, Titulo Publico, COE, BTC. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na tabela. |

### silver.de_para_item_revisao

SILVER | De-para entre o item do fabricante e o texto que voce escreve na nota da oficina. Existe porque a sua CATEGORIA e grossa demais para servir de ponte: "Filtro" cobre quatro itens do plano com intervalos de 10k, 20k, 20k e 10k, e "Fluido" cobre cinco, de 20k a 80k - casar por categoria obrigaria a adotar sempre o menor intervalo. O DS_ITEM do fato, sim, distingue. VARIAS LINHAS POR ITEM sao esperadas: o texto e livre e tem grafia variada. Item do plano sem mapeamento nao some da previsao - ele e o que aparece como "Sem registro".

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **nm_item_plano** | `varchar(200)` | Sim | Nome | Item do plano do fabricante, na grafia de silver.auto_revisao_programada. |
| **ds_padrao_item** | `varchar(200)` | Sim | Descrição | Trecho de texto a procurar dentro do DS_ITEM do fato, ja sem acento e em minusculas. A comparacao usa collation acento-insensivel, entao "oleo" encontra "óleo". QUANDO MAIS DE UM PADRAO CASA, VENCE O MAIS LONGO - e o que impede "filtro de ar" de roubar o lancamento de "filtro de ar condicionado", e faz "filtro oleo motor" ir para o filtro e nao para o oleo do motor. |
| nr_lancamentos | `int` | Não | Número | Quantos lancamentos do historico este padrao encontrou na ultima carga. Serve para achar padrao que nunca casa - sinal de grafia errada no cadastro. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o mapeamento entrou na tabela. |

### silver.dia_registro

SILVER | Diario de habitos, limpo e tipado. Uma linha por dia respondido. As perguntas de sim/nao viram bit, as refeicoes continuam texto porque tem tres estados, e o consumo de agua vira decimal. Origem: aba de respostas de um formulario do Google publicada como CSV. Alimenta gold.fato_dia e gold.fato_dia_habito.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_registro** | `int` | Sim | Chave substituta | Chave substituta do registro. A identidade estavel e hash_negocio. |
| dt_referencia | `date` | Não | Data | DIA A QUE A RESPOSTA SE REFERE - o eixo temporal da analise. Digitada a mao no formulario, por isso sujeita a erro: quando o ano e implausivel, fl_data_suspeita marca 1 e a data segue como esta, sem correcao automatica. |
| dt_resposta | `datetime2` | Não | Data | Momento do envio do formulario, atribuido pelo Google. E a chave de negocio da origem. Nao confundir com dt_referencia: o formulario e respondido depois do dia que descreve. |
| nr_dias_atraso | `int` | Não | Número | Dias entre o dia relatado e o envio da resposta. Normalmente 1, porque o formulario e preenchido na manha seguinte. Valores altos indicam resposta preenchida de memoria dias depois, o que reduz a confiabilidade do registro. |
| fl_data_suspeita | `bit` | Sim | Indicador (sim/não) | ALERTA DE QUALIDADE. Marca 1 quando dt_referencia esta fora da faixa plausivel (antes de 2020 ou depois de amanha) ou quando falta. Sao erros de digitacao no formulario, nao dados reais. A linha e mantida porque o resto da resposta e valido; na gold esses registros apontam para a data "Nao informado". |
| fl_treino | `bit` | Não | Indicador (sim/não) | 1 quando houve treino de musculacao no dia. |
| fl_cardio | `bit` | Não | Indicador (sim/não) | 1 quando houve cardio no dia. A origem trazia o negativo em duas grafias, com e sem til, por mudanca na opcao do formulario - aqui ja esta unificado. |
| vl_agua_litros | `decimal(5,2)` | Não | Valor (métrica) | METRICA. Litros de agua consumidos no dia, entre 0,3 e 3,1. E a unica medida numerica da base e a unica coluna que faz sentido somar ou tirar media. |
| ds_cafe_manha | `varchar(20)` | Não | Descrição | Cafe da manha: SIM, NAO ou JACA. Mantido como texto, e nao bit, porque sao tres estados: JACA e refeicao feita fora do plano alimentar, situacao diferente de pular a refeicao. |
| ds_almoco | `varchar(20)` | Não | Descrição | Almoco: SIM, NAO ou JACA (fora do plano alimentar). |
| ds_lanche | `varchar(20)` | Não | Descrição | Lanche: SIM, NAO ou JACA (fora do plano alimentar). |
| ds_janta | `varchar(20)` | Não | Descrição | Janta: SIM, NAO ou JACA. E a refeicao que mais sai do plano. |
| ds_ceia | `varchar(20)` | Não | Descrição | Ceia: SIM, NAO ou JACA. E a refeicao mais frequentemente pulada. |
| nr_refeicoes_feitas | `int` | Sim | Número | DERIVADA. Quantas das cinco refeicoes foram feitas dentro do plano, de 0 a 5. Conta apenas SIM. |
| nr_refeicoes_jaca | `int` | Sim | Número | DERIVADA. Quantas das cinco refeicoes sairam do plano alimentar, de 0 a 5. E o indicador de aderencia a dieta: a media fica em torno de 0,6 por dia, e cerca de metade dos dias tem ao menos uma. |
| ds_dia_produtivo | `varchar(20)` | Não | Descrição | Avaliacao do dia: NORMAL, SIM ou NAO. NAO E BOOLEANO - NORMAL e a resposta padrao e cobre oito de cada dez dias, entao contar "diferente de SIM" como dia improdutivo distorceria a leitura. |
| fl_trabalho | `bit` | Não | Indicador (sim/não) | 1 quando houve trabalho no dia. |
| fl_nina_em_casa | `bit` | Não | Indicador (sim/não) | 1 quando a filha esteve em casa no dia. |
| fl_estresse | `bit` | Não | Indicador (sim/não) | 1 quando houve discussao no dia. |
| fl_lazer | `bit` | Não | Indicador (sim/não) | 1 quando houve momento a dois no dia. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade da resposta, herdada da bronze: hash do carimbo do formulario. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.familia_movimentacao

SILVER | Gastos em comum de Ale e Lia, limpos e tipados. Uma linha por gasto real, com quem pagou identificado - e esse o proposito da base: dar transparencia sobre a divisao das despesas da casa. Origem: aba do Google Sheets publicada como CSV, e nao de arquivo, como as origens bancarias. Alimenta gold.fato_familia, separado do fato pessoal.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_movimentacao** | `int` | Sim | Chave substituta | Chave substituta do lancamento. A identidade estavel e hash_negocio. |
| dt_lancamento | `date` | Não | Data | Data do gasto. Ha lancamentos com data futura - sao parcelas a vencer, que vao ate 2031. Filtre por data ate hoje para ver so o que ja aconteceu. |
| dt_pagamento | `date` | Não | Data | Data do pagamento efetivo, quando difere da data do gasto. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do gasto, escrita a mao. Preservada para auditoria. |
| vl_transacao | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. Vem de "Valor Trat" da planilha, ja convertido do formato brasileiro - a origem entrega texto como "1.234,56" e negativo entre parenteses. |
| ds_tipo_movimentacao | `varchar(20)` | Não | Descrição | DESPESA ou RECEITA, com a grafia unificada. A origem trazia quatro variacoes de caixa para a mesma palavra. |
| ds_area | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 1: GASTOS ESSENCIAIS, ESTILO DE VIDA ou RECEITA. |
| ds_categoria | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 2, o principal para analise. Compartilha o vocabulario das origens pessoais em dez categorias (ALIMENTACAO, TRANSPORTE, LAZER...), e tem oito proprias da familia - MORADIA, DIARISTA, HOSPEDAGEM, INTERNET e outras. Compartilhar a dimensao com o fato pessoal permite comparar os dois pela mesma categoria. |
| ds_grupo | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 3, o mais fino: "Aluguel", "IPTU", "Reforma", "Manutencao". |
| fl_classificado | `bit` | Sim | Indicador (sim/não) | Marca 1 quando o lancamento tem categoria vinda da planilha. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | QUEM PAGOU, com a grafia unificada. Vale ALE, LIA, Conta (quando saiu da conta conjunta) ou o nome de um terceiro. E o eixo da transparencia que motiva esta base: somar por esta coluna responde quanto cada um bancou. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. Mais de 400 valores distintos. |
| ds_forma_pgto | `varchar(50)` | Não | Descrição | Forma de pagamento: C para credito, D para debito, entre outras. |
| ds_descricao_pgto | `varchar(200)` | Não | Descrição | Descricao da forma de pagamento, indicando o cartao ou conta usada. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto, preenchida na quase totalidade dos lancamentos. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre, usada para marcar contexto como viagens. |
| fl_pago | `bit` | Sim | Indicador (sim/não) | Marca 1 quando a planilha registra o gasto como pago. Permite separar o que ja saiu do bolso do que esta comprometido - relevante porque ha parcelas com vencimento ate 2031. |
| fl_sinal_divergente | `bit` | Sim | Indicador (sim/não) | ALERTA DE QUALIDADE. Marca 1 quando o sinal do valor contradiz o tipo declarado - uma despesa com valor positivo, por exemplo. Acontece quando o valor e digitado ja negativo na planilha e a formula "Valor Trat = -Valor" o inverte, transformando despesa em receita. Foi assim que cinco reformas apareceram como receita, um desvio de R$ 7.194. Revisar periodicamente os lancamentos marcados. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da bronze. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.financ_historico

SILVER | Historico financeiro de 2014 a 2018, tipado e classificado. Uma linha por lancamento. Alimenta gold.fato_movto_financ ao lado das origens atuais, estendendo a serie dois anos e meio para tras. FILTRE fl_meta = 0 para movimentacao de verdade: 287 linhas sao orcamento planejado e nao dinheiro movimentado.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_lancamento** | `int` | Sim | Chave substituta | Chave substituta do lancamento. A identidade estavel e hash_negocio. |
| dt_lancamento | `date` | Não | Data | Data do lancamento. A serie vai de fevereiro/2014 a maio/2018. |
| dt_pagamento | `date` | Não | Data | Data do pagamento efetivo, quando difere da data do lancamento. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do lancamento, preservada para auditoria. |
| vl_transacao | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. NAO SOME sem filtrar fl_meta = 0 - as linhas de orcamento sao positivas e somariam R$ 135.522 de receita inexistente. |
| ds_tipo_movimentacao | `varchar(20)` | Não | Descrição | DESPESA, RECEITA ou META, com a grafia unificada. |
| fl_meta | `bit` | Sim | Indicador (sim/não) | 1 quando a linha e ORCAMENTO PLANEJADO e nao movimentacao. Sao 287 registros, 24 por categoria, cobrindo dois anos de meta mensal. O fato os exclui; ficam aqui porque descarta-los na carga apagaria informacao que a planilha tem. |
| ds_area | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 1, DERIVADA e nao lida da origem - a coluna Area da planilha esta vazia. Ver ds_origem_area para saber com que confianca cada valor foi atribuido. |
| ds_categoria | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 2, lida da origem. Tres categorias nao existem nas origens atuais: AJUSTE, FINANCAS e Telefonia. |
| ds_grupo | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 3, lida da origem. |
| ds_origem_area | `varchar(20)` | Sim | Descrição | PROCEDENCIA DA AREA, e a coluna que separa evidencia de palpite. PAR_EXATO: a combinacao categoria + grupo ja existia na classificacao, entao a area veio de classificacao anterior sua. CATEGORIA: so a categoria existia, e foi usada a area mais frequente dela - e INFERENCIA, necessaria porque o proprio vocabulario e ambiguo (TRANSPORTE/Combustivel aparece sob duas areas diferentes). A CLASSIFICAR: nem a categoria existia. Trate CATEGORIA como provisorio no relatorio, e refaca a inferencia quando revisar a classificacao. |
| fl_classificado | `bit` | Sim | Indicador (sim/não) | Marca 1 quando o lancamento tem categoria vinda da planilha. |
| ds_forma_pagamento | `varchar(60)` | Não | Descrição | Instrumento de pagamento, com a grafia unificada: a origem trazia "visa BB" e "Visa BB", "Dinheiro/Debito" e "dinheiro/Debito". Vira a origem do fato. |
| ds_pessoa_pagar | `varchar(120)` | Não | Descrição | Quem pagou. |
| ds_pessoa_receber | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto. |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto. |
| ds_obs | `varchar(500)` | Não | Descrição | Observacao livre. NAO vira tag nesta origem - o campo guarda numeros soltos que o interpretador de marcacoes leria errado. Quem marca contexto aqui e ds_projeto. |
| ds_projeto | `varchar(100)` | Não | Descrição | MARCACAO DE CONTEXTO: Compacto, Hatch 2008, Viagem Exterior, Sedan 2016. Alimenta gold.dim_tag pela mesma ponte das demais origens, o que permite somar "quanto custou o Hatch" atravessando bases e decadas. |
| fl_pago | `bit` | Sim | Indicador (sim/não) | 1 quando a planilha registra o lancamento como pago. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do lancamento, herdada da bronze. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |

### silver.itau_movimentacao

SILVER | Movimentacoes da conta corrente do Itau, limpas e tipadas, desde 2016. Uma linha por evento real. A classificacao vem da planilha, nao de regra: o que nao foi classificado a mao aparece como "A classificar", jamais adivinhado. Inclui as linhas de saldo (FL_SALDO = 1), que a gold exclui por nao serem transacao. Os rotulos de area, categoria e grupo tiveram a grafia unificada - "Casa" e "CASA" conviviam na origem e virariam dois membros na dimensao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_movimentacao** | `int` | Sim | Chave substituta | Chave substituta do lancamento na silver. A identidade estavel e hash_negocio. |
| dt_lancamento | `date` | Não | Data | Data em que o lancamento ocorreu na conta. |
| dt_pagamento | `date` | Não | Data | Data do pagamento efetivo, quando anotada na planilha e diferente da data do lancamento. Util para despesas com vencimento posterior. |
| ds_descricao | `varchar(1000)` | Não | Descrição | Descricao do lancamento como o Itau a gera. Preservada integralmente: e a unica forma de identificar o estabelecimento e de auditar a classificacao. |
| vl_transacao | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor do lancamento em reais. Positivo = entrada na conta, negativo = saida. Vem da coluna "Valor" da planilha; "Valor Trat" foi descartada por ser identica em toda a serie. |
| ds_tipo_movimentacao | `varchar(20)` | Não | Descrição | RECEITA, DESPESA ou SALDO. Coerente com o sinal do valor em 100% da serie, o que permitiu deduzi-lo para os lancamentos vindos do extrato, que nao trazem o campo. |
| fl_saldo | `bit` | Sim | Indicador (sim/não) | Marca 1 quando a linha e um marcador de saldo (final ou parcial) anotado no extrato, e nao uma transacao. SEMPRE filtre por FL_SALDO = 0 ao somar valores: saldo somado com movimentacao nao significa nada. A gold ja exclui estas linhas. |
| ds_area | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 1, a mais ampla: TRANSFERENCIA, ESTILO DE VIDA, RENDA, GASTOS ESSENCIAIS, TAXA, EMPRESTIMO e outras. Vale "A classificar" quando a planilha nao preencheu. ATENCAO: nao e uma hierarquia estrita sobre categoria - a mesma categoria aparece sob areas diferentes ao longo do tempo. |
| ds_categoria | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 2, o nivel principal de analise de gastos: TRANSFERENCIA, RENDIMENTO, TRABALHO, CASA, TRANSPORTE, ALIMENTACAO, EDUCACAO e outros. Vale "A classificar" quando a planilha nao preencheu - hoje cerca de 37% da serie, concentrada antes de 2024. |
| ds_grupo | `varchar(100)` | Sim | Descrição | CLASSIFICACAO nivel 3, a mais fina: "Movimentacao entre contas", "Combustivel", "Escola Nina", "Almoco". E o nivel usado para acompanhar metas por assunto. Vale "A classificar" quando ausente. |
| fl_classificado | `bit` | Sim | Indicador (sim/não) | Marca 1 quando o lancamento tem categoria vinda da planilha e 0 quando esta como "A classificar". Filtrar por este campo mostra rapidamente o que ainda precisa de revisao, ordenado por valor. |
| ds_pessoa_pagar | `varchar(100)` | Não | Descrição | Quem pagou, conforme anotacao manual. |
| ds_pessoa_receber | `varchar(100)` | Não | Descrição | Quem recebeu, conforme anotacao manual. |
| ds_forma_pgto | `varchar(50)` | Não | Descrição | Forma de pagamento anotada na planilha. |
| ds_descricao_pgto | `varchar(200)` | Não | Descrição | Descricao complementar da forma de pagamento. |
| ds_cidade | `varchar(100)` | Não | Descrição | Cidade do gasto, quando anotada (cerca de 19% dos lancamentos). |
| ds_uf | `varchar(20)` | Não | Descrição | UF do gasto, quando anotada. |
| ds_pais | `varchar(60)` | Não | Descrição | Pais do gasto, quando anotado. Util para isolar gastos de viagem. |
| ds_obs | `varchar(1000)` | Não | Descrição | Observacao livre anotada na planilha. |
| ds_projeto | `varchar(100)` | Não | Descrição | Projeto vinculado ao gasto. Praticamente nao utilizado na origem. |
| ds_tag | `varchar(100)` | Não | Descrição | Marcador livre, fora da hierarquia de categoria. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada de bronze.itau_movimentacao. Inclui o numero da ocorrencia no dia, porque o extrato do Itau nao traz saldo para desempatar transacoes identicas. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi processado para a silver. |
| ds_origem_classificacao | `varchar(20)` | Não | Descrição | Procedencia do rotulo de categoria: PLANILHA quando veio classificado da aba cad-conta, DE-PARA quando foi atribuido pela tabela de revisao por padrao, e A CLASSIFICAR quando ainda nao tem categoria. Permite medir quanto da base depende de cada fonte e auditar o efeito de uma revisao. |

### silver.xp_movimentacao

SILVER | Movimentacoes da conta XP limpas, tipadas e classificadas com criterio uniforme. Uma linha por evento financeiro real, sem duplicatas. Derivada de bronze.xp_movimentacao: datas viram date, valores viram decimal, e categoria/ativo sao recalculados a partir da descricao textual do lancamento. E a tabela de referencia para analise de investimentos e a origem do arquivo consolidado consumido hoje pelo Power BI.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **sk_movimentacao** | `int` | Sim | Chave substituta | Chave substituta da movimentacao na silver. Sequencial e sem significado de negocio; a identidade estavel do evento e hash_negocio. |
| dt_movimentacao | `date` | Não | Data | Data em que a movimentacao ocorreu - o fato economico. Use esta data para apurar resultado (dividendos recebidos no mes, compras realizadas no mes). |
| dt_liquidacao | `date` | Não | Data | Data em que o dinheiro efetivamente entrou ou saiu da conta. Costuma ser igual a de movimentacao, mas difere em operacoes de bolsa (D+2) e aplicacoes com carencia. Use esta data para fluxo de caixa e conciliacao de saldo. |
| ds_lancamento | `varchar(1000)` | Não | Descrição | Descricao original do lancamento, preservada da origem. Mantida na silver por ser a unica forma de auditar como a categoria e o ativo foram deduzidos. |
| vl_transacao | `decimal(18,2)` | Não | Valor (métrica) | Valor da transacao em reais. Positivo = entrada de recurso na conta (dividendo, JCP, rendimento, resgate, venda). Negativo = saida (compra, taxa, imposto, retirada). Somar esta coluna com filtro de categoria da o resultado do periodo. |
| vl_saldo | `decimal(18,2)` | Não | Valor (métrica) | Saldo em conta corrente da corretora logo apos o lancamento. ATENCAO: e o saldo de CAIXA, nao o patrimonio investido - dinheiro aplicado em acoes, FIIs ou CDB nao aparece aqui. Nao use como medida de patrimonio. |
| ds_categoria | `varchar(100)` | Sim | Descrição | Natureza do lancamento, deduzida da descricao por regras: Dividendo, Compra, Operacao Bolsa, IR, IOF, Emolumentos, Taxa de Remuneracao, Resgate, Aplicacao, Transferencia, Retirada, Margem, Subscricao, Investback, Reembolso, Vencimento, Estorno, Multa, Pagamento CC e Outros. "Outros" indica descricao nao reconhecida pelas regras e merece revisao periodica. |
| ds_ativo | `varchar(200)` | Não | Descrição | Ativo relacionado ao lancamento, extraido da descricao: ticker de acao ou FII (PETR4, HGLG11), nome de CDB, fundo, COE ou Tesouro Direto. Nulo quando o lancamento nao se refere a um ativo especifico, como transferencia ou taxa de conta. E a chave para analisar rendimento por ativo. |
| fl_rendimento | `bit` | Sim | Indicador (sim/não) | Indica se o lancamento e remuneracao do patrimonio investido (1) ou nao (0). Verdadeiro para valores positivos nas categorias Dividendo, Investback, Reembolso e Taxa de Remuneracao. Filtrar por este campo da o total de proventos do periodo, sem misturar com aportes e resgates. |
| ds_tipo_movimentacao | `varchar(20)` | Não | Descrição | RECEITA quando o valor e positivo, DESPESA quando negativo. Redundante com o sinal de vl_transacao, mantido porque o relatorio atual do Power BI usa este campo como dimensao. |
| ds_categoria_manual | `varchar(100)` | Não | Descrição | Categoria que estava preenchida a mao na planilha mestre, quando havia. Nula para eventos que nunca passaram pela planilha. Guardada para permitir auditar as regras automaticas contra o criterio historico. |
| fl_divergencia_manual | `bit` | Sim | Indicador (sim/não) | Marca 1 quando a categoria calculada pela regra difere da que estava na planilha mestre. Nao significa erro: pode ser correcao de uma classificacao antiga inconsistente ou um caso que a regra ainda nao cobre. Revisar estes registros e a forma de melhorar as regras ao longo do tempo. |
| hash_negocio | `char(64)` | Sim | Identidade do evento | Identidade do evento, igual a de bronze.xp_movimentacao. E a chave de ligacao entre as camadas e o que garante que a silver nao duplique registros. |
| dt_carga | `datetime2` | Sim | Data | LINHAGEM: data e hora em que o registro foi processado para a silver. |

## gold

Modelo dimensional pronto para consumo. É a única camada que o Power BI consulta.

### gold.dim_area_financ

GOLD | Nivel 1 da classificacao financeira: GASTOS ESSENCIAIS, ESTILO DE VIDA, RENDA, TRANSFERENCIA e outras. Compartilhada por gold.fato_movto_financ e gold.fato_familia, o que permite comparar gasto pessoal e familiar pelo mesmo eixo. E DIMENSAO PROPRIA, e nao um nivel dentro da categoria, porque a area NAO E PROPRIEDADE DA CATEGORIA nesta base: 23 categorias aparecem sob mais de uma area, e com razao - combustivel para lazer e combustivel para trabalho sao decisoes diferentes tomadas lancamento a lancamento.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_AREA_FINANC** | `int` | Sim | Chave substituta | Chave substituta da area. -1 representa area nao informada. |
| NM_AREA | `varchar(100)` | Sim | Nome | Nome da area, com a grafia unificada entre as origens. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |

### gold.dim_ativo

GOLD | Ativo relacionado ao lancamento: acao, FII, CDB, Tesouro, fundo ou COE. A chave -1 ("Nao aplicavel") atende lancamentos sem ativo, como transferencia e taxa de conta - por isso o fato nunca precisa de SK_ATIVO nulo.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_ATIVO** | `int` | Sim | Chave substituta | Chave substituta do ativo. -1 = lancamento sem ativo especifico. |
| CD_ATIVO | `varchar(200)` | Sim | Código | Codigo do ativo como extraido da descricao: ticker (PETR4, HGLG11), identificador do CDB, nome do fundo ou do COE. Unico na tabela. |
| NM_ATIVO | `varchar(200)` | Não | Nome | Nome por extenso do ativo, quando conhecido. Hoje repete o codigo; reservado para quando houver uma fonte de cadastro de ativos. |
| TP_ATIVO | `varchar(40)` | Sim | Tipo | Classe do ativo, deduzida do formato do codigo: Ação, FII, CDB, Tesouro Direto, Fundo, COE, LCA/LCI, Aluguel BTC ou Não classificado. Permite analisar alocacao por classe sem cadastro manual. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi criado. |
| DS_CLASSE_ATIVO | `varchar(60)` | Não | Descrição | Classe do ativo (Renda Fixa, Renda Variavel, Fundos Imobiliarios...). Vem do de-para manual quando o ativo consta la; caso contrario e deduzida do TP_ATIVO. Use DS_ORIGEM_CLASSE para saber qual foi o caso. |
| DS_SUBCLASSE_ATIVO | `varchar(60)` | Não | Descrição | Subclasse do ativo, mais fina que TP_ATIVO: distingue CDB pos de pre-fixado e direito de subscricao da cota do FII. |
| DS_ORIGEM_CLASSE | `varchar(20)` | Não | Descrição | Procedencia da classificacao: MANUAL quando veio de silver.de_para_classe_ativo e DEDUZIDA quando foi inferida do TP_ATIVO. Permite ver quanto do patrimonio esta classificado por decisao sua e quanto por regra. |

### gold.dim_calendario

GOLD | Dimensao de datas, de 2020 ate o fim do ano seguinte ao atual. Nomes de mes e dia da semana em portugues. Marque-a como Tabela de Datas no Power BI para habilitar inteligencia temporal (acumulado no ano, mesmo periodo do ano anterior). A chave -1 atende lancamento sem data de liquidacao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_DATA** | `int` | Sim | Chave substituta | Chave substituta da data no formato AAAAMMDD (ex: 20260702). Inteiro em vez de date porque ocupa menos e ordena naturalmente. -1 = data nao informada. |
| DT_DATA | `date` | Sim | Data | A data propriamente dita. E esta coluna que deve ser marcada como a data da tabela de datas no Power BI. |
| NR_ANO | `int` | Sim | Número | Ano com 4 digitos. |
| NR_MES | `int` | Sim | Número | Numero do mes (1 a 12). Use para ordenar NM_MES no Power BI. |
| NM_MES | `varchar(20)` | Sim | Nome | Nome do mes por extenso em portugues (Janeiro, Fevereiro...). |
| NM_MES_ABREV | `char(3)` | Sim | Nome | Abreviacao do mes com 3 letras (Jan, Fev...), para eixos estreitos. |
| NR_DIA | `int` | Sim | Número | Dia do mes (1 a 31). |
| NR_DIA_SEMANA | `int` | Sim | Número | Dia da semana como numero, 1 = Domingo e 7 = Sabado. |
| NM_DIA_SEMANA | `varchar(20)` | Sim | Nome | Nome do dia da semana em portugues. |
| NR_TRIMESTRE | `int` | Sim | Número | Trimestre do ano (1 a 4). |
| NR_SEMESTRE | `int` | Sim | Número | Semestre do ano (1 ou 2). |
| NM_ANO_MES | `char(7)` | Sim | Nome | Ano e mes no formato AAAA-MM. Ordena alfabeticamente na ordem correta, o que resolve o eixo de graficos de serie temporal sem coluna de ordenacao auxiliar. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi criado. |
| FL_FIM_SEMANA | `char(1)` | Sim | Indicador (sim/não) | S quando a data cai em sabado ou domingo. |
| NM_MES_ANO | `varchar(20)` | Não | Nome | Mes e ano no formato legivel Jan/2026. CALCULADA a partir de NM_MES_ABREV e NR_ANO, entao dia novo no calendario ja nasce com ela. E a coluna de ROTULO; para ORDENAR ou comparar use NM_ANO_MES, que esta em AAAA-MM e ordena sozinho - por aqui, Abril viria antes de Janeiro. |
| NM_DIA_SEMANA_ABREV | `varchar(3)` | Não | Nome | Dia da semana abreviado: Seg, Ter, Qua, Qui, Sex, Sab, Dom. CALCULADA a partir de NR_DIA_SEMANA. Para ordenar use NR_DIA_SEMANA, em que 1 e domingo. |
| FL_FERIADO | `char(1)` | Sim | Indicador (sim/não) | S quando o dia e feriado nacional OU ponto facultativo; N nos demais. Os dois casos vem com S de proposito: para explicar gasto e rotina, o que importa e se o comercio abriu. Use DS_TIPO_FERIADO para separar o feriado legal do facultativo. |
| NM_FERIADO | `varchar(60)` | Não | Nome | Nome do feriado, nulo quando o dia nao e feriado. Cabe UM nome por dia: se um dia ganhar dois feriados - o que acontece ao acrescentar estadual ou municipal, ja que 21/04 e Tiradentes e Fundacao de Brasilia - o script 47 aborta em vez de escolher sozinho qual sobrevive. |
| DS_TIPO_FERIADO | `varchar(20)` | Não | Descrição | Nacional para o feriado previsto em lei; Facultativo para Carnaval (segunda, terca e quarta de cinzas) e Corpus Christi, que juridicamente sao ponto facultativo e nao feriado. Nulo quando o dia nao e feriado. A lista cobre so o ambito NACIONAL: feriado estadual e municipal nao entraram. |

### gold.dim_categoria_auto

GOLD | As 34 categorias de manutencao, com o intervalo de troca de cada uma. O intervalo vem da aba "Tempo Troca" da planilha e existe em 13 delas; as outras 21 sao corretivas - nao se troca bandeja, lampada ou mao de obra por quilometragem, entao o nulo ali e a resposta certa e nao um cadastro faltando.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_CATEGORIA_MANUTENCAO** | `int` | Sim | Chave substituta | Chave substituta da categoria. -1 representa categoria nao identificada. |
| NM_CATEGORIA | `varchar(100)` | Sim | Nome | Nome da categoria, com a grafia unificada. |
| NR_INTERVALO_KM | `int` | Não | Número | Quilometros recomendados entre trocas: 5.000 para oleo, 10.000 para filtro, 50.000 para amortecedor. Nulo nas categorias corretivas. Alimenta gold.vw_manutencao_prevista. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou ou foi atualizado na dimensao. |
| FL_TEM_INTERVALO | `char(1)` | Sim | Indicador (sim/não) | S quando a categoria tem troca prevista por quilometragem e portanto entra na previsao de vencimento. |

### gold.dim_categoria_financ

GOLD | Nivel 2 da classificacao financeira, e o principal para analise: ALIMENTACAO, TRANSPORTE, LAZER, CASA, SAUDE. Compartilhada pelos fatos pessoal e da familia. "A classificar" e um membro REAL desta dimensao, e nao um nulo: e o que permite medir o tamanho do backlog de classificacao pelo proprio relatorio.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_CATEGORIA_FINANC** | `int` | Sim | Chave substituta | Chave substituta da categoria. -1 representa categoria nao informada. |
| NM_CATEGORIA | `varchar(100)` | Sim | Nome | Nome da categoria, com a grafia unificada entre as origens - a canonizacao escolhe a forma ortograficamente correta primeiro e a mais frequente depois. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |
| FL_CLASSIFICADO | `char(1)` | Sim | Indicador (sim/não) | S quando a categoria e uma classificacao de verdade, N no membro "A classificar", que existe para MEDIR O QUE FALTA em vez de esconder. Contar os lancamentos com N da o tamanho do trabalho pendente - hoje 36% dos analiticos. |

### gold.dim_categoria_investimento

GOLD | Natureza do lancamento (Dividendo, Compra, IR, Margem...). UMA linha por categoria - a constraint UQ_dim_categoria_investimento_nome garante isso. No modelo antigo de dbo, 7 categorias existiam duplicadas (uma versao RECEITA e outra DESPESA), o que fazia a carga inserir cada lancamento duas vezes. RECEITA/DESPESA agora vive no fato, onde e determinada pelo sinal do valor.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_CATEGORIA_INVESTIMENTO** | `int` | Sim | Chave substituta | Chave substituta da categoria. -1 representa categoria nao informada. |
| NM_CATEGORIA | `varchar(100)` | Sim | Nome | Nome da categoria, unico na tabela. Derivado da descricao do lancamento pelas regras em scripts/etl/regras_xp.py. |
| DS_GRUPO | `varchar(40)` | Sim | Descrição | Agrupador de categorias para leitura no dashboard: Proventos (dividendo, JCP, rendimento), Custos (IR, IOF, taxas, emolumentos), Operação (compra, venda, subscricao), Caixa (transferencia, retirada, aplicacao, resgate) e Outros. Evita graficos com 24 fatias. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi criado. |

### gold.dim_grupo_financ

GOLD | Nivel 3 da classificacao financeira, o mais fino: "Almoco", "Aluguel", "Combustivel", "Reforma". E a dimensao mais numerosa das tres. Como a area, e independente e nao aninhada: 103 grupos aparecem sob mais de uma categoria, entao tratar o grupo como filho de uma categoria unica seria falso.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_GRUPO_FINANC** | `int` | Sim | Chave substituta | Chave substituta do grupo. -1 representa grupo nao informado. |
| NM_GRUPO | `varchar(100)` | Sim | Nome | Nome do grupo, com a grafia unificada entre as origens. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |
| DS_COMPRESSIBILIDADE | `varchar(20)` | Não | Descrição | Natureza do gasto, para separar o que da para cortar do que nao da. Compressivel: discricionario e recorrente (comida fora, assinatura, lazer) - e daqui que sai economia sem perda estrutural. Essencial: moradia, escola, combustivel, saude, imposto. Eventual: nao se repete (revisao, eletrodomestico, viagem) - e o que estoura a meta do cartao, e o que deveria sair de um fundo em vez da fatura. Nao e gasto: aporte, resgate e transferencia entre contas, que existem aqui para NAO serem somados como consumo. NULA significa grupo ainda nao classificado, e o painel o mostra como "A classificar" - lacuna que aparece e lacuna que alguem preenche. Preenchida a mao; a carga so insere membros novos e nunca sobrescreve. |

### gold.dim_habito

GOLD | Catalogo das perguntas do diario. Existe para que o painel de habitos seja um grafico so, com uma medida so: sem esta dimensao, cada pergunta do formulario viraria uma medida DAX propria e acrescentar uma pergunta nova exigiria refazer o relatorio. Separa objetivo de contexto - treinar e uma meta, a filha estar em casa e uma circunstancia - e por isso nem todo habito apura aderencia.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_HABITO** | `int` | Sim | Chave substituta | Chave substituta do habito. -1 representa habito nao identificado. |
| NM_HABITO | `varchar(50)` | Sim | Nome | Nome curto do habito, como aparece no relatorio. |
| DS_GRUPO | `varchar(30)` | Sim | Descrição | Agrupamento tematico: Saude, Alimentacao, Rotina ou Bem-estar. Permite ler o painel por bloco em vez de habito a habito. |
| DS_PERGUNTA | `varchar(100)` | Sim | Descrição | Texto original da pergunta no formulario do Google. Guardado porque o rotulo da origem pode mudar sem que o habito mude, e e por ele que a carga liga a coluna do CSV a esta dimensao. |
| DS_RESPOSTA_DESEJADA | `varchar(10)` | Não | Descrição | Resposta que representa o objetivo cumprido, para os habitos medidos em sim/nao. Vale SIM na maioria, NAO em Estresse - onde o sucesso e a ausencia - e nulo tanto nos habitos de contexto quanto nos medidos por numero, que usam VL_META_MINIMA. |
| NR_ORDEM | `int` | Sim | Número | Ordem de exibicao no relatorio, seguindo a sequencia do formulario. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |
| VL_META_MINIMA | `decimal(6,2)` | Não | Valor (métrica) | META DIARIA, para os habitos medidos em NUMERO em vez de sim/nao. A aderencia passa a ser "o valor do dia alcancou este limiar". Hoje so a agua usa: a meta e em litros por dia. Ajustar o alvo e um UPDATE nesta coluna seguido de nova carga - a regra vive aqui como dado, e nao no codigo, e a semeadura do script nao sobrescreve o ajuste. |
| DS_UNIDADE | `varchar(20)` | Não | Descrição | Unidade de VL_META_MINIMA, para o relatorio rotular o numero sem depender de quem monta a visualizacao lembrar qual e. Nula nos habitos de sim/nao. |
| FL_APURA_ADERENCIA | `char(1)` | Sim | Indicador (sim/não) | S quando o habito e uma META e faz sentido medir aderencia. N quando e apenas CONTEXTO: trabalhar, a filha estar em casa e a avaliacao do dia descrevem a circunstancia e nao um objetivo - somar tudo como se fosse meta produziria um indice sem significado. Os de contexto continuam validos como filtro. |

### gold.dim_localizacao

GOLD | Um lugar por linha: cidade, UF e pais que antes se repetiam em cada lancamento dos fatos financeiros. EXISTE PARA RECEBER ATRIBUTO DE LUGAR. Latitude e longitude ja estao aqui, nulas; preenche-las e um UPDATE em cerca de 140 linhas, nao em 15 mil. Regiao, fuso e populacao entram do mesmo jeito, sem tocar nos fatos. AS GRAFIAS NAO FORAM CORRIGIDAS: a mesma cidade aparece sob UF diferente em 53 lancamentos (Belo Horizonte e Cidade A com DF, Brasilia com MG ou sem UF), e cada combinacao e um membro separado. Ao preencher coordenada, atencao: essas cidades tem mais de uma linha e devem receber a MESMA coordenada. A conferencia do script 45 lista quais sao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_LOCALIZACAO** | `int` | Sim | Chave substituta | Chave substituta do lugar. -1 representa lancamento sem localizacao informada. |
| NM_CIDADE | `varchar(100)` | Não | Nome | Cidade como veio da origem, sem unificacao de grafia. Nula quando a origem so informou o pais. |
| SG_UF | `varchar(2)` | Não | Outro | Sigla da unidade federativa, dois caracteres. Nula fora do Brasil e nos lancamentos em que nao foi informada. |
| NM_PAIS | `varchar(60)` | Não | Nome | Pais. Hoje so Brasil e um pais vizinho. |
| NM_LOCALIZACAO | `varchar(166)` | Não | Nome | Rotulo legivel do lugar, no formato Cidade/UF - Pais. CALCULADA E PERSISTED: acompanha sozinha qualquer correcao em cidade, UF ou pais, em vez de envelhecer calada. E a coluna para por num filtro de relatorio. |
| VL_LATITUDE | `decimal(9,6)` | Não | Valor (métrica) | Latitude em graus decimais. Nula ate alguem preencher - o motivo de a dimensao existir. |
| VL_LONGITUDE | `decimal(9,6)` | Não | Valor (métrica) | Longitude em graus decimais. Nula ate alguem preencher. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o lugar entrou na dimensao. |

### gold.dim_metrica_corporal

GOLD | Catalogo das metricas de avaliacao fisica: o que cada numero significa, em que unidade, em que era foi medido e para que lado e melhora. E a dimensao que torna o painel de evolucao legivel - sem ela, o relatorio nao sabe que gordura caindo e bom e massa muscular caindo e ruim.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_METRICA** | `int` | Sim | Chave substituta | Chave substituta da metrica. -1 representa metrica nao identificada. |
| NM_METRICA | `varchar(100)` | Sim | Nome | Nome da metrica, como consta do laudo. |
| DS_GRUPO | `varchar(100)` | Sim | Descrição | Agrupamento do laudo: composicao corporal, obesidade, circunferencias, medida geral, gordura visceral e pontuacao. |
| DS_UNIDADE | `varchar(20)` | Não | Descrição | Unidade da metrica. NUNCA agregue metricas de unidades diferentes na mesma conta - o fato guarda kg, cm, %, litros e pontos na mesma coluna de valor, entao qualquer soma precisa de filtro por metrica. |
| DS_SENTIDO_MELHOR | `varchar(10)` | Não | Descrição | Para que lado a metrica melhora: MAIOR quando subir e bom (massa muscular, agua corporal, circunferencia de braco), MENOR quando cair e bom (gordura, cintura, gordura visceral). NULO onde nao ha resposta universal - peso, IMC e estatura dependem do objetivo do momento, e pressao arterial e melhor dentro de uma faixa e nao num extremo. E o que alimenta FL_MELHOROU no fato. Regra de negocio: ajustavel por UPDATE, sem alterar codigo. |
| DS_ERA | `varchar(30)` | Sim | Descrição | Em que era a metrica foi medida: "Até 2013" (laudo completo, com circunferencias e pressao), "2018 em diante" (bioimpedancia) ou "Ambas". |
| NR_ORDEM | `int` | Sim | Número | Ordem de exibicao no relatorio, agrupada por assunto. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |
| FL_SERIE_CONTINUA | `char(1)` | Sim | Indicador (sim/não) | 1 nas cinco metricas que existem nas DUAS eras de medicao - Peso, IMC, % Gordura, Massa Gordura e Estatura - e portanto sustentam um grafico de 2008 a 2026 sem buraco. FILTRE POR ESTA COLUNA no painel de longo prazo: as demais metricas produzem linhas que comecam ou terminam no meio do periodo. |

### gold.dim_origem

GOLD | Origem do lancamento: de qual conta ou instituicao o dado veio. Existe para que o mesmo fato receba, no futuro, lancamentos do Itau, do cartao de credito e de outras fontes sem precisar de uma tabela por origem. A chave -1 representa origem nao informada.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_ORIGEM** | `int` | Sim | Chave substituta | Chave substituta da origem. Valores fixos definidos no script, nao gerados. |
| CD_ORIGEM | `varchar(30)` | Sim | Código | Codigo tecnico e estavel da origem (ex: XP_INVEST). Use em filtros de codigo, nunca o nome, que pode mudar. |
| NM_ORIGEM | `varchar(100)` | Sim | Nome | Nome da origem como deve aparecer no relatorio. |
| NM_INSTITUICAO | `varchar(60)` | Sim | Nome | Instituicao financeira responsavel pela conta (XP, Itau, Nubank). |
| DS_TIPO_CONTA | `varchar(40)` | Sim | Descrição | Natureza da conta: conta de investimento, conta corrente ou cartao de credito. Permite separar patrimonio de fluxo de caixa do dia a dia. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro foi criado. |

### gold.dim_pessoa

GOLD | Quem paga os gastos da familia: Ale, Lia, a conta conjunta ou um terceiro. E o eixo que motiva a base da familia inteira - somar por esta dimensao responde quanto cada um bancou. A grafia foi unificada na silver: a origem trazia "ALE" e "Ale" como se fossem duas pessoas.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_PESSOA** | `int` | Sim | Chave substituta | Chave substituta da pessoa. -1 representa pagador nao informado. |
| NM_PESSOA | `varchar(100)` | Sim | Nome | Nome de quem pagou, como registrado na planilha. |
| DS_TIPO | `varchar(30)` | Sim | Descrição | Natureza do pagador: Titular para Ale e Lia, Conta conjunta quando o gasto saiu do fundo comum, e Terceiro para os demais. Separa o que cada um bancou do proprio bolso do que saiu do dinheiro ja aportado por ambos - somar as tres categorias como se fossem equivalentes distorce a divisao real. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |

### gold.dim_revisao_programada

GOLD | A regra de revisao que vale para cada veiculo, uma linha por veiculo e item do fabricante - 21 para o SUV. POR QUE POR VEICULO E NAO POR CATEGORIA. dim_categoria_auto guarda um intervalo so, aplicado a qualquer carro: oleo a 5.000 km e regime de Sedan, e o fabricante do SUV manda 10.000. Alem disso a categoria e grossa demais para o plano - "Filtro" cobre quatro itens com intervalos diferentes. NAO E DIMENSAO DE FATO NENHUM: nenhuma chave estrangeira aponta para ca. E uma tabela de REGRA, consultada por gold.vw_manutencao_prevista. Por isso nao tem membro -1.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_REVISAO_PROGRAMADA** | `int` | Sim | Chave substituta | Chave substituta da regra. |
| SK_VEICULO | `int` | Sim | Chave substituta | Chave para gold.dim_veiculo: a que carro esta regra se aplica. O plano do SUV nao vale para o Sedan. |
| SK_CATEGORIA_MANUTENCAO | `int` | Sim | Chave substituta | Chave para gold.dim_categoria_auto: em que categoria da SUA classificacao os lancamentos deste item costumam cair. Serve para cruzar a regra com o gasto no Power BI. Vale -1 quando o item nunca apareceu no historico ou quando o de-para nao o alcanca - e ai a previsao dele sai como "Sem registro". |
| NM_ITEM | `varchar(200)` | Sim | Nome | Item ou componente, na grafia do fabricante. |
| NM_SISTEMA | `varchar(120)` | Não | Nome | Sistema do veiculo: Motor, Freios, Suspensao, Cambio CVT. Agrupa a previsao por area do carro. |
| NR_INTERVALO_KM | `int` | Não | Número | Quilometros entre uma intervencao e a proxima. |
| NR_INTERVALO_MESES | `int` | Não | Número | Meses entre uma intervencao e a proxima. VALE EM PARALELO ao intervalo em km, e o fabricante manda seguir o que vencer primeiro. E a coluna que faz a previsao funcionar sem depender de o hodometro ser anotado. |
| DS_ACAO | `varchar(30)` | Não | Descrição | Troca, Inspeção ou Serviço. Uma inspecao vencida nao tem a mesma urgencia de um fluido vencido, e sem esta coluna as duas apareceriam iguais. |
| DS_ESPECIFICACAO | `varchar(500)` | Não | Descrição | Especificacao tecnica: qual oleo, qual fluido, qual norma. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade da regra, herdada da silver. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando a regra foi carregada na gold. |

### gold.dim_segmento_corporal

GOLD | As cinco partes do corpo que a bioimpedancia mede separadamente, mais o membro de corpo inteiro. E a dimensao que responde ONDE falta musculo, e nao apenas quanto - a pergunta que o preenchimento manual nunca alcancou. O MEMBRO -1 CHAMA-SE "Corpo inteiro" E NAO "Nao informado": para peso, IMC ou taxa metabolica, nao haver segmento e a resposta certa, e nao dado faltando.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_SEGMENTO** | `int` | Sim | Chave substituta | Chave substituta do segmento. Fixa, e nao IDENTITY: sao seis membros que vem do aparelho e nao crescem com o uso. |
| NM_SEGMENTO | `varchar(40)` | Sim | Nome | Nome do segmento: Braço esquerdo, Braço direito, Tronco, Perna esquerda, Perna direita, Corpo inteiro. |
| DS_LADO | `varchar(20)` | Não | Descrição | Esquerdo, Direito ou Central. Permite medir assimetria entre os dois lados sem depender do nome do segmento. |
| DS_REGIAO | `varchar(30)` | Não | Descrição | Membro superior, Membro inferior ou Tronco. Agrupa as duas pernas - e a quebra que mostrou a perda de massa magra concentrada nelas. |
| NR_ORDEM | `int` | Sim | Número | Ordem de exibicao, de cima para baixo no corpo. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou na dimensao. |

### gold.dim_tag

GOLD | As marcacoes da coluna OBS das planilhas, tratadas como o que sao: um eixo de analise. Viagens, pessoas, imoveis, veiculos e projetos - #Nina, #Escola, #AptoCentro, Viagem07_Praia. E COMPARTILHADA PELOS FATOS FINANCEIROS, e e isso que da valor: as mesmas tags aparecem no Itau, no cartao e na conta familia, entao somar por ela responde "quanto custou a viagem" juntando as tres origens de uma vez. As grafias NAO foram unificadas: Arraial aparece em sete formas e so quem lancou sabe se sao a mesma viagem. Quando houver a lista revisada, entra um de-para.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_TAG** | `int` | Sim | Chave substituta | Chave substituta da tag. -1 representa lancamento sem marcacao. |
| NM_TAG | `varchar(100)` | Sim | Nome | A tag como foi digitada, incluindo o # quando havia. Preservada sem unificacao. |
| DS_TIPO | `varchar(30)` | Sim | Descrição | Natureza da marcacao, inferida do proprio texto: Viagem quando o nome comeca com "Viagem" ou traz destino e data, e Marcacao para o restante. E palpite de apoio a leitura, nao classificacao revisada - corrija por UPDATE quando quiser. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando a tag entrou na dimensao. |

### gold.dim_veiculo

GOLD | Os veiculos cujo historico de manutencao a base guarda: Sedan, de 2016 a novembro de 2025, e SUV desde entao. Existe porque CADA UM TEM SEU PROPRIO HODOMETRO - sem separar, os 100 mil km do SUV pareceriam um retrocesso diante dos 158 mil do Sedan, e toda previsao de troca sairia errada.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_VEICULO** | `int` | Sim | Chave substituta | Chave substituta do veiculo. -1 representa veiculo nao identificado. |
| NM_VEICULO | `varchar(60)` | Sim | Nome | Nome do veiculo, como registrado na planilha. |
| DT_PRIMEIRA | `date` | Não | Data | Data da primeira manutencao registrada para este veiculo. |
| DT_ULTIMA | `date` | Não | Data | Data da manutencao mais recente deste veiculo. |
| NR_KM_ATUAL | `int` | Não | Número | Maior quilometragem ja registrada para este veiculo - a melhor estimativa da atual. DERIVADA DO HISTORICO, e nao da aba "Quilometragem" da planilha, que guarda um numero solto de 2025 que nao corresponde a nenhum dos dois carros. E o denominador de toda previsao de troca, entao so fica correta se o hodometro for anotado a cada visita. |
| NR_VISITAS | `int` | Não | Número | Quantas idas a oficina este veiculo teve. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o registro entrou ou foi atualizado na dimensao. |
| FL_ATIVO | `char(1)` | Sim | Indicador (sim/não) | S no veiculo em uso. INFERIDO: e o que tem a manutencao mais recente, porque a planilha nao registra compra nem venda. Se dois carros passarem a ser mantidos ao mesmo tempo, esta regra precisa mudar. |

### gold.fato_avaliacao_fisica

GOLD | A evolucao corporal medida, uma linha por avaliacao e por metrica. E A SERIE MAIS LONGA DO PROJETO: 31 avaliacoes entre 2008 e 2026. ATENCAO: a coluna de valor mistura unidades (kg, cm, %, litros, pontos), entao toda agregacao exige filtro por metrica - somar a coluna inteira nao significa nada. E a serie NAO E HOMOGENEA: so cinco metricas cobrem os 18 anos, identificadas por FL_SERIE_CONTINUA na dimensao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_MEDICAO** | `int` | Sim | Chave substituta | Chave substituta da medicao. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario - o MESMO calendario dos fatos financeiros e do diario, o que permite cruzar avaliacao com habito e com gasto pela data. |
| SK_METRICA | `int` | Sim | Chave substituta | Chave para gold.dim_metrica_corporal: o que foi medido. |
| NR_AVALIACAO | `int` | Sim | Número | Numero sequencial da avaliacao, de 1 a 31 em ordem de data. Permite ordenar e comparar avaliacoes sem depender do intervalo entre elas, que e irregular. |
| VL_MEDIDA | `decimal(10,2)` | Não | Valor (métrica) | METRICA. Valor medido, na unidade da metrica. NAO SOME sem filtrar por metrica: a coluna guarda kg, cm, % e pontos juntos. |
| VL_MEDIDA_ANTERIOR | `decimal(10,2)` | Não | Valor (métrica) | Valor da mesma metrica na avaliacao ANTERIOR em que ela foi medida. Nulo na primeira ocorrencia. Trazido para o fato porque as avaliacoes sao irregulares - de um mes a mais de tres anos entre elas - e "anterior" nao coincide com nenhum periodo do calendario, o que tornaria a comparacao em DAX cara e fragil. |
| VL_VARIACAO | `decimal(10,2)` | Não | Valor (métrica) | Diferenca entre esta medicao e a anterior da mesma metrica. Positivo significa aumento, e nao melhora - para saber se aumentar e bom, use FL_MELHOROU. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade da medicao, herdada da silver: hash de data + metrica. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando a medicao foi carregada na gold. |
| SK_SEGMENTO | `int` | Sim | Chave substituta | Chave para gold.dim_segmento_corporal. Vale -1 (Corpo inteiro) em toda metrica que nao e segmentar - inclusive nas 419 linhas que vieram da planilha, que nunca teve analise segmentar. |
| VL_REFERENCIA_MIN | `decimal(10,2)` | Não | Valor (métrica) | Limite inferior da faixa de referencia impressa no exame ao lado do valor. MUDA A CADA EXAME, porque depende de idade e altura - por isso e coluna do fato e nao atributo da metrica. Nulo nas linhas vindas da planilha. |
| VL_REFERENCIA_MAX | `decimal(10,2)` | Não | Valor (métrica) | Limite superior da faixa de referencia impressa no exame. |
| DS_AVALIACAO | `varchar(20)` | Não | Descrição | Classificacao que a propria maquina imprime: Abaixo, Normal ou Acima. So existe nas metricas segmentares, e e a leitura pronta de quanto o segmento se afasta do ideal calculado para o seu corpo. |
| DS_ORIGEM | `varchar(20)` | Sim | Descrição | De onde a medida veio: InBody quando foi lida do arquivo do exame, Planilha quando foi digitada a mao. AS DUAS ORIGENS SE COMPLETAM - o arquivo entra na frente onde existe, a planilha preenche o que o OCR nao alcancou, e a planilha e a unica fonte das 17 metricas de ate 2013 que o InBody nem mede. No espirito do DS_ORIGEM_CLASSE de dim_ativo. |
| FL_MEDIDO | `char(1)` | Sim | Indicador (sim/não) | N quando a metrica constava do laudo mas ficou sem valor. Distingue "nao foi medido" de "nao consta daquela era". |
| FL_MELHOROU | `char(1)` | Não | Indicador (sim/não) | S quando a variacao foi na direcao desejada para aquela metrica, conforme DS_SENTIDO_MELHOR da dimensao. NULO quando nao ha medicao anterior, quando o valor nao mudou, ou quando a metrica nao tem direcao boa definida - peso e IMC, por exemplo, dependem do objetivo. PARA O PERCENTUAL de metricas que melhoraram numa avaliacao use AVG(CASE WHEN FL_MELHOROU = ''S'' THEN 1.0 WHEN FL_MELHOROU = ''N'' THEN 0.0 END), com os dois ramos: o ELSE 0 contaria como piora o que nao foi avaliado. |

### gold.fato_carga

GOLD | Uma linha por execucao de carga sobre uma tabela: quantas linhas entraram, quantas mudaram e quanto tempo levou. Uma rodada da DAG gera dezenas de linhas aqui. EXISTE PORQUE dt_carga NAO RESPONDE ISSO: ele e sobrescrito no update, entao uma linha atualizada hoje fica indistinguivel de uma inserida hoje. A diferenca so existe no instante da carga. E o unico fato do modelo que fala do PIPELINE e nao das financas - nao se relaciona com nenhum outro, e o unico eixo compartilhado e o calendario.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_CARGA** | `int` | Sim | Chave substituta | Chave substituta da execucao. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario, no dia da execucao. Permite cruzar volume de carga com qualquer outro assunto pela mesma data. |
| DT_EXECUCAO | `datetime2` | Sim | Data | Momento exato do fim da carga, com milissegundos. E por ele que se ordena a sequencia de execucoes dentro de um mesmo dia. |
| DS_CAMADA | `varchar(10)` | Sim | Descrição | Camada da tabela carregada: bronze, silver ou gold. Atributo degenerado - e rotulo tecnico, sem atributo proprio que justifique uma dimensao. |
| DS_TABELA | `varchar(120)` | Sim | Descrição | Nome da tabela carregada, qualificado pelo schema. Atributo degenerado. |
| DS_SCRIPT | `varchar(120)` | Não | Descrição | Nome do script que fez a carga. LINHAGEM: liga o numero ao codigo que o produziu, para saber onde investigar quando algo nao converge. |
| NR_INSERIDOS | `int` | Sim | Número | METRICA. Linhas que ENTRARAM nesta execucao. Aditiva. |
| NR_ATUALIZADOS | `int` | Sim | Número | METRICA. Linhas que ja existiam e MUDARAM nesta execucao. Aditiva. Numero alto sem voce ter mexido na origem e sinal de defeito, e nao de trabalho feito - foi assim que apareceram as 772 atualizacoes fantasma do historico financeiro. |
| NR_DESCARTADOS | `int` | Não | Número | Linhas descartadas por nao serem lancamento - cauda de formula arrastada, linha sem chave. Nulo nas cargas que nao descartam nada. |
| NR_TOTAL | `int` | Não | Número | Total de linhas da tabela DEPOIS da carga. Serve de conferencia: o total tem de crescer exatamente pelo numero de inseridos. |
| NR_SEGUNDOS | `decimal(8,2)` | Não | Número | Duracao da carga em segundos. Uma carga que passa a demorar muito mais que o habitual costuma indicar indice faltando ou origem crescendo. |
| FL_CONVERGIU | `char(1)` | Sim | Indicador (sim/não) | A COLUNA QUE IMPORTA. S quando a execucao nao inseriu nem atualizou nada. O projeto tem um contrato explicito: rodar de novo sem mexer na origem tem de convergir em zero. Uma carga que NUNCA converge tem defeito - e sempre teve, so que antes isso dependia de alguem rodar duas vezes e comparar no olho. N e esperado na primeira carga do dia, quando ha dado novo de verdade. PARA CONTAR: use SUM(CASE WHEN FL_CONVERGIU = 'S' THEN 1 ELSE 0 END), e nao CAST para int - a coluna e char(1) desde a padronizacao dos indicadores. |

### gold.fato_dia

GOLD | Um retrato por dia: todas as respostas do formulario lado a lado. E o formato para cruzar habitos entre si ("treinei mais nos dias de trabalho?") e para somar o consumo de agua, a unica medida numerica da base. Para acompanhar aderencia ao longo do tempo, use gold.fato_dia_habito. COBERTURA: cerca de 93% dos dias desde janeiro de 2024 tem resposta; os dias sem registro simplesmente nao existem aqui, entao contar linhas nao e o mesmo que contar dias do calendario.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_DIA** | `int` | Sim | Chave substituta | Chave substituta do dia registrado. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario - o MESMO calendario dos fatos financeiros, o que permite cruzar habito e gasto pela mesma data. Vale -1 quando a data digitada no formulario e implausivel; ver FL_DATA_SUSPEITA. |
| VL_AGUA_LITROS | `decimal(5,2)` | Não | Valor (métrica) | METRICA. Litros de agua no dia - indicador de controle acompanhado de perto. Unica medida numerica da base: some ou tire media a vontade. As demais colunas sao indicadores, e somar bit nao tem significado alem de "quantos dias". ATENCAO ao usar media por periodo: os dias sem resposta nao existem nesta tabela, entao AVG devolve a media DOS DIAS REGISTRADOS, e nao dos dias do calendario. Para litros por dia corrido, divida a soma pela contagem de datas de gold.dim_calendario no periodo. |
| NR_REFEICOES_FEITAS | `int` | Sim | Número | Quantas das cinco refeicoes foram feitas dentro do plano alimentar, de 0 a 5. |
| NR_REFEICOES_JACA | `int` | Sim | Número | Quantas das cinco refeicoes sairam do plano alimentar, de 0 a 5. Principal indicador de aderencia a dieta. |
| NR_HABITOS_ADERENTES | `int` | Sim | Número | Quantas METAS do dia foram cumpridas. Denominador em NR_HABITOS_APURADOS - a razao entre os dois e a nota do dia. Guardado no fato, e nao calculado no Power BI, para que a nota seja a mesma em qualquer ferramenta que leia a tabela. |
| NR_HABITOS_APURADOS | `int` | Sim | Número | Quantas metas foram efetivamente respondidas no dia. E o denominador correto da nota: usar um numero fixo trataria pergunta em branco como meta perdida. |
| DS_DIA_PRODUTIVO | `varchar(20)` | Não | Descrição | Avaliacao do dia: NORMAL, SIM ou NAO. NAO E BOOLEANO - NORMAL cobre oito de cada dez dias e e a resposta padrao, entao ler "diferente de SIM" como dia ruim inverteria o sentido da escala. |
| NR_DIAS_ATRASO | `int` | Não | Número | Dias entre o dia relatado e o envio do formulario. Normalmente 1. Valores altos indicam resposta preenchida de memoria, menos confiavel. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade da resposta, herdada da silver: hash do carimbo do formulario. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o dia foi carregado na gold. |
| FL_NINA_EM_CASA | `char(1)` | Não | Indicador (sim/não) | S quando a filha esteve em casa. CONTEXTO, nao meta. |
| FL_ESTRESSE | `char(1)` | Não | Indicador (sim/não) | S quando houve discussao no dia. Aqui o objetivo e o zero, e nao o S. |
| FL_CARDIO | `char(1)` | Não | Indicador (sim/não) | S quando houve cardio. |
| FL_DATA_SUSPEITA | `char(1)` | Sim | Indicador (sim/não) | ALERTA DE QUALIDADE. S quando a data digitada no formulario e implausivel. Esses registros apontam para SK_DATA = -1 e ficam fora de qualquer analise temporal ate serem corrigidos na origem. |
| FL_META_AGUA | `char(1)` | Não | Indicador (sim/não) | S quando o consumo de agua do dia alcancou a meta diaria. A meta nao esta aqui: vive em gold.dim_habito.VL_META_MINIMA, para ser ajustavel sem alterar codigo. Mudar a meta e recarregar reescreve esta coluna em toda a serie, o que permite responder "com a meta nova, como teria sido 2024". |
| FL_LAZER | `char(1)` | Não | Indicador (sim/não) | S quando houve momento a dois no dia. |
| FL_TRABALHO | `char(1)` | Não | Indicador (sim/não) | S quando houve trabalho no dia. CONTEXTO, nao meta - serve para segmentar os demais indicadores entre dia util e folga. |
| FL_TREINO | `char(1)` | Não | Indicador (sim/não) | S quando houve treino de musculacao. |

### gold.fato_dia_habito

GOLD | Uma linha por dia POR HABITO - o formato longo do diario. Existe para que o painel de habitos seja um grafico so: com este fato, "% de aderencia por habito por mes" e uma unica medida (AVG de FL_ADERENCIA) segmentada por gold.dim_habito, e uma pergunta nova no formulario entra sem tocar no relatorio. O formato largo equivalente esta em gold.fato_dia. NAO SOME as duas tabelas juntas: sao a mesma informacao em dois formatos.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_DIA_HABITO** | `int` | Sim | Chave substituta | Chave substituta da combinacao dia + habito. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario. Vale -1 quando a data do formulario e implausivel. |
| SK_HABITO | `int` | Sim | Chave substituta | Chave para gold.dim_habito: qual pergunta do formulario esta linha responde. |
| DS_RESPOSTA | `varchar(20)` | Não | Descrição | Resposta padronizada: SIM, NAO, JACA ou NORMAL. Preservada ao lado do indicador porque JACA e NAO contam igual na aderencia mas significam coisas opostas - uma e sair da dieta, a outra e pular a refeicao. No habito de agua, que e medido em numero, traz o valor do dia ja com a unidade ("1,3 litros"); para calcular use VL_MEDIDA ou gold.fato_dia.VL_AGUA_LITROS, nunca esta coluna. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade da linha: hash do carimbo do formulario combinado com o habito. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando a linha foi carregada na gold. |
| VL_MEDIDA | `decimal(6,2)` | Não | Valor (métrica) | Valor do dia para os habitos medidos em NUMERO - hoje so a agua, em litros. Nulo nos habitos de sim/nao. NAO SOME esta coluna sem filtrar o habito: se um dia houver um segundo habito numerico em outra unidade, a soma juntaria litros com outra coisa. Para agua, gold.fato_dia.VL_AGUA_LITROS e o caminho seguro. |
| FL_ADERENCIA | `char(1)` | Não | Indicador (sim/não) | METRICA PRINCIPAL. S quando a resposta bate com o objetivo do habito, N quando nao. NULO nos habitos de contexto, que nao tem objetivo. PARA O PERCENTUAL DE ADERENCIA use AVG(CASE WHEN FL_ADERENCIA = ''S'' THEN 1.0 WHEN FL_ADERENCIA = ''N'' THEN 0.0 END) - a media continua ignorando o nulo sozinha, mas o CASE precisa dos DOIS ramos: trocar o segundo WHEN por um ELSE 0 contaria os habitos de contexto como meta nao cumprida e derrubaria a aderencia sem nada ter acontecido. |
| FL_RESPONDIDO | `char(1)` | Sim | Indicador (sim/não) | S quando a pergunta foi respondida naquele dia. Distingue "nao cumpri a meta" de "nao respondi", que somados dariam uma aderencia artificialmente baixa. |

### gold.fato_familia

GOLD | Gastos em comum de Ale e Lia, uma linha por lancamento. Fato SEPARADO do pessoal de proposito: este dinheiro vem dos aportes mensais dos dois para as contas conjuntas, e misturar com gold.fato_movto_financ contaria gasto de duas pessoas como se fosse de uma. As transferencias que Alexandre faz para a conta familia aparecem no fato pessoal e sao assunto independente destes gastos. ATENCAO: ha lancamentos com data futura, parcelas que vao ate 2031 - use FL_FUTURO para separar o que ja aconteceu do que esta comprometido.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_LANCAMENTO** | `int` | Sim | Chave substituta | Chave substituta do lancamento. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario na data do gasto. |
| SK_DATA_PAGAMENTO | `int` | Sim | Chave substituta | Chave para gold.dim_calendario na data do pagamento efetivo. Vale -1 quando nao informada. |
| SK_PESSOA | `int` | Sim | Chave substituta | Chave para gold.dim_pessoa: quem pagou. |
| VL_TRANSACAO | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor em reais, com sinal: negativo e despesa, positivo e receita. Aditiva. |
| DS_TIPO_FLUXO | `varchar(10)` | Não | Descrição | RECEITA quando o valor e positivo, DESPESA quando negativo. |
| DS_DETALHE_ORIGINAL | `varchar(1000)` | Não | Descrição | Descricao original do gasto. Mantida para auditoria da classificacao. |
| DS_PESSOA_RECEBER | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. Atributo do fato, e nao dimensao, por ter mais de 400 valores distintos. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da silver. Com constraint UNIQUE. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento foi carregado na gold. |
| SK_AREA_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_area_financ - a MESMA dimensao do fato pessoal. |
| SK_CATEGORIA_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_categoria_financ - a MESMA do fato pessoal, o que permite comparar gasto proprio e da familia pelo mesmo eixo. |
| SK_GRUPO_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_grupo_financ - nivel 3, o mais fino. |
| FL_FUTURO | `char(1)` | Sim | Indicador (sim/não) | S quando a data do lancamento ainda nao chegou - parcelas a vencer, que vao ate 2031. Filtre por N para apurar o que de fato aconteceu; por 1 para ver o comprometimento futuro. Somar os dois juntos mistura passado e compromisso. |
| FL_PAGO | `char(1)` | Sim | Indicador (sim/não) | S quando a planilha registra o gasto como pago. |
| SK_LOCALIZACAO | `int` | Sim | Chave substituta | Chave para gold.dim_localizacao: onde o lancamento aconteceu. -1 quando a origem nao informou. Substituiu DS_CIDADE, DS_UF e DS_PAIS, que seguem na silver e na bronze para auditoria. |
| SK_TAG | `int` | Sim | Chave substituta | Chave para gold.dim_tag: a tag PRINCIPAL do lancamento, -1 quando nao ha nenhuma. Substituiu DS_OBS, cujo texto cru segue na silver e na bronze. ATENCAO AO SOMAR POR TAG: um lancamento pode ter mais de uma marcacao e aqui so cabe a principal, entao o total por esta coluna SUBCONTA a tag que perdeu a disputa - hoje #AleLia, com 191 aqui contra 208 na ponte. Para total por tag use gold.ponte_tag; para fatiar no dia a dia, use esta coluna, que nao exige relacao bidirecional nem duplica linha. A escolha e feita por gold.vw_tag_principal. |

### gold.fato_investimento

GOLD | Tabela fato com uma linha por movimentacao financeira. Granularidade: um evento na conta, identificado por HASH_NEGOCIO. Hoje contem apenas a XP Investimentos; o modelo ja comporta outras origens via SK_ORIGEM. A constraint UNIQUE em HASH_NEGOCIO impede que uma carga repetida duplique lancamentos - foi exatamente o que aconteceu no modelo antigo de dbo. ESCOPO: nao inclui chamadas de margem (categoria Margem), que sao garantia operacional sem efeito patrimonial e representavam metade dos eventos. Para o registro completo, consulte silver.xp_movimentacao.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_LANCAMENTO** | `int` | Sim | Chave substituta | Chave substituta do lancamento. |
| SK_ORIGEM | `int` | Sim | Chave substituta | Chave estrangeira para gold.dim_origem: de qual conta veio o lancamento. |
| SK_DATA_MOVIMENTACAO | `int` | Sim | Chave substituta | Chave estrangeira para gold.dim_calendario na data do fato economico. Use esta data para apurar resultado do periodo. |
| SK_DATA_LIQUIDACAO | `int` | Sim | Chave substituta | Chave estrangeira para gold.dim_calendario na data em que o dinheiro entrou ou saiu. Use para fluxo de caixa e conciliacao de saldo. Vale -1 quando ausente. |
| SK_ATIVO | `int` | Sim | Chave substituta | Chave estrangeira para gold.dim_ativo. Vale -1 quando o lancamento nao se refere a um ativo (transferencia, taxa de conta). |
| SK_CATEGORIA_INVESTIMENTO | `int` | Sim | Chave substituta | Chave estrangeira para gold.dim_categoria_investimento. |
| VL_TRANSACAO | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor da transacao em reais. Positivo = entrada de recurso, negativo = saida. E a medida aditiva do modelo: pode ser somada em qualquer combinacao de dimensoes. |
| VL_SALDO_MOMENTO | `decimal(18,2)` | Não | Valor (métrica) | Saldo em conta corrente da corretora apos o lancamento. NAO E ADITIVO: somar esta coluna nao produz nada com sentido. Use apenas como ultimo valor de um periodo. Alem disso e saldo de CAIXA, nao patrimonio investido. |
| DS_TIPO_FLUXO | `varchar(10)` | Não | Descrição | RECEITA quando VL_TRANSACAO e positivo, DESPESA quando negativo. Fica no fato porque depende da transacao, nao da categoria. |
| DS_DETALHE_ORIGINAL | `varchar(1000)` | Não | Descrição | Descricao original do lancamento como veio da XP. Mantida para auditoria: e a unica forma de conferir por que uma categoria ou ativo foi atribuido. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada de silver.xp_movimentacao. Chave de deduplicacao entre as camadas e garantia de unicidade do fato. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento foi carregado na gold. |
| FL_RENDIMENTO | `char(1)` | Sim | Indicador (sim/não) | S quando o lancamento e remuneracao do patrimonio (dividendo, JCP, rendimento, investback, reembolso, taxa de remuneracao com valor positivo). Filtrar por este campo da o total de proventos, sem misturar aporte e resgate. |

### gold.fato_manutencao_auto

GOLD | Revisoes e manutencoes do automovel, uma linha por item de cada visita a oficina. Sao dez anos de historico em dois veiculos. NAO SE MISTURA COM O FATO FINANCEIRO: parte destes gastos aparece tambem na fatura do cartao, e somar os dois contaria a mesma despesa duas vezes. Aqui o assunto e o veiculo - o que foi trocado, com que quilometragem - e nao o dinheiro. O unico eixo compartilhado com as demais bases e o calendario.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_MANUTENCAO** | `int` | Sim | Chave substituta | Chave substituta do lancamento. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario, na data da visita a oficina. |
| SK_VEICULO | `int` | Sim | Chave substituta | Chave para gold.dim_veiculo: qual carro. |
| SK_CATEGORIA_MANUTENCAO | `int` | Sim | Chave substituta | Chave para gold.dim_categoria_auto: o que foi feito. |
| NR_VISITA | `int` | Sim | Número | Numero sequencial da visita a oficina, por veiculo. Agrupe por ele para somar o custo de uma revisao inteira, que se espalha por varias linhas. |
| NR_KM | `int` | Não | Número | Quilometragem do veiculo na data. NAO COMPARE ENTRE VEICULOS: cada um tem sua propria escala, e o carro mais novo tem hodometro menor. |
| VL_GASTO | `decimal(12,2)` | Não | Valor (métrica) | METRICA. Valor pago em reais, total do item. Sempre positivo - e sempre despesa, entao nao carrega sinal como os fatos financeiros. Aditiva. |
| NR_QUANTIDADE | `decimal(10,2)` | Não | Número | Quantidade de unidades do item. |
| DS_TIPO | `varchar(30)` | Não | Descrição | Produto (peca) ou Serviço (mao de obra). Permite separar quanto foi peca e quanto foi trabalho numa mesma nota. |
| DS_ITEM | `varchar(200)` | Não | Descrição | Descricao do item, como escrita na nota. Atributo do fato, e nao dimensao, por ter 110 variacoes de texto livre. |
| DS_LOCAL | `varchar(120)` | Não | Descrição | Oficina ou loja onde foi feito. |
| DS_OBSERVACAO | `varchar(500)` | Não | Descrição | Observacao livre da origem. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da silver. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento foi carregado na gold. |
| FL_PREVENTIVA | `char(1)` | Sim | Indicador (sim/não) | S quando foi revisao programada, N quando foi conserto. A proporcao entre os dois diz se a manutencao esta sendo preventiva ou apenas reagindo a quebra. |

### gold.fato_movto_financ

GOLD | Fluxo de caixa e gastos, unindo a conta corrente do Itau e os cartoes de credito XP e Nubank. Uma linha por movimentacao. Investimentos NAO entram aqui - ficam em gold.fato_investimento. ATENCAO AO NIVEL: um gasto no cartao existe em dois planos - o gasto detalhado (ANALITICO) e o pagamento da fatura na conta corrente (SINTETICO). Somar os dois conta a mesma despesa duas vezes. Para apurar despesa, filtre DS_NIVEL = ANALITICO.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_MOVIMENTACAO** | `int` | Sim | Chave substituta | Chave substituta da movimentacao. |
| SK_ORIGEM | `int` | Sim | Chave substituta | Chave para gold.dim_origem: de qual conta ou cartao veio o lancamento. |
| SK_DATA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario na data do lancamento - a data da compra, no caso do cartao. Use para responder "quanto gastei em julho". |
| SK_DATA_FATURA | `int` | Sim | Chave substituta | Chave para gold.dim_calendario na data de vencimento da fatura. Preenchida apenas para cartao; vale -1 nos lancamentos de conta corrente. Use para fluxo de caixa e para conciliar com o pagamento no extrato. |
| VL_TRANSACAO | `decimal(18,2)` | Não | Valor (métrica) | METRICA. Valor em reais, com sinal: negativo e saida, positivo e entrada. O sinal foi uniformizado entre origens - o cartao Nubank trazia gasto positivo e teve o sinal invertido na silver. E aditiva, mas SOMENTE dentro do mesmo DS_NIVEL. |
| DS_NIVEL | `varchar(12)` | Sim | Descrição | NIVEL DO LANCAMENTO. ANALITICO e o gasto em si - compra no cartao ou despesa direta na conta. SINTETICO e o pagamento da fatura do cartao, que agrega os gastos analiticos daquele periodo. Existem em planos diferentes: somar os dois duplica a despesa. A medida de gasto do dashboard deve filtrar ANALITICO. |
| DS_TIPO_FLUXO | `varchar(10)` | Não | Descrição | RECEITA quando o valor e positivo, DESPESA quando negativo. |
| NR_PARCELA | `int` | Não | Número | Numero da parcela, quando a compra no cartao foi parcelada. Nulo nos demais. |
| DS_DETALHE_ORIGINAL | `varchar(1000)` | Não | Descrição | Descricao original do lancamento, como veio da origem. Mantida para auditoria: e a unica forma de conferir por que uma categoria foi atribuida. |
| DS_PESSOA_PAGAR | `varchar(100)` | Não | Descrição | Quem pagou, conforme anotacao na origem. |
| DS_PESSOA_RECEBER | `varchar(200)` | Não | Descrição | Estabelecimento ou pessoa que recebeu. No cartao, e o campo mais proximo de um cadastro de fornecedores. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade do evento, herdada da silver. Com constraint UNIQUE: e o banco que impede a duplicacao, nao o script de carga. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando o lancamento foi carregado na gold. |
| SK_AREA_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_area_financ - nivel 1 da classificacao. |
| SK_CATEGORIA_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_categoria_financ - nivel 2, o principal para analise. |
| SK_GRUPO_FINANC | `int` | Sim | Chave substituta | Chave para gold.dim_grupo_financ - nivel 3, o mais fino. Os tres sao dimensoes independentes: a combinacao de cada lancamento vive AQUI, no fato, e nao numa dimensao de trios. |
| SK_LOCALIZACAO | `int` | Sim | Chave substituta | Chave para gold.dim_localizacao: onde o lancamento aconteceu. -1 quando a origem nao informou. Substituiu DS_CIDADE, DS_UF e DS_PAIS, que seguem na silver e na bronze para auditoria. |
| SK_TAG | `int` | Sim | Chave substituta | Chave para gold.dim_tag: a tag PRINCIPAL do lancamento, -1 quando nao ha nenhuma. Substituiu DS_OBS, cujo texto cru segue na silver e na bronze. ATENCAO AO SOMAR POR TAG: um lancamento pode ter mais de uma marcacao e aqui so cabe a principal, entao o total por esta coluna SUBCONTA a tag que perdeu a disputa - hoje #AleLia, com 191 aqui contra 208 na ponte. Para total por tag use gold.ponte_tag; para fatiar no dia a dia, use esta coluna, que nao exige relacao bidirecional nem duplica linha. A escolha e feita por gold.vw_tag_principal. |

### gold.ponte_tag

GOLD | Liga cada lancamento as suas tags. E tabela PONTE porque a relacao e muitos-para-muitos: um lancamento pode ter mais de uma marcacao - "#Praia-Out22 #AleLia" e ao mesmo tempo a viagem e o casal - e uma tag marca muitos lancamentos. Uma chave estrangeira simples no fato obrigaria a escolher uma e perder a outra. NO POWER BI: ligue dim_tag para ca por SK_TAG e daqui para o fato por HASH_NEGOCIO, com o filtro cruzado nos DOIS SENTIDOS na segunda relacao - sem isso o filtro nao chega ao fato. ATENCAO ao somar: um lancamento com duas tags aparece duas vezes ao cruzar por aqui, entao somar valor sem filtrar uma tag especifica conta em duplicidade.

| Coluna | Tipo | Obrig. | Papel | Descrição |
| --- | --- | :---: | --- | --- |
| **SK_PONTE** | `int` | Sim | Chave substituta | Chave substituta da ligacao. |
| HASH_NEGOCIO | `char(64)` | Sim | Identidade do evento | Identidade do lancamento, a mesma do fato. Serve para os tres fatos porque o hash e unico em toda a plataforma. |
| SK_TAG | `int` | Sim | Chave substituta | Chave para gold.dim_tag: qual tag. |
| DS_FATO | `varchar(40)` | Sim | Descrição | Nome do fato a que o lancamento pertence. Existe para tornar a ligacao auditavel e para permitir filtrar a ponte por origem sem consultar os fatos. |
| DT_CARGA | `datetime2` | Sim | Data | LINHAGEM: quando a ligacao foi criada. |

---

Colunas em **negrito** compõem a chave primária.
