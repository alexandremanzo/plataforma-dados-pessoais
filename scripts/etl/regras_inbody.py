"""
Leitura dos exames de bioimpedancia InBody.

O exame chega como imagem: 23 dos 24 arquivos sao render digital do
software LookinBody, sempre 1640x2310, sem inclinacao e com texto
nitido. Nao e foto de papel, e por isso o OCR e viavel.

TRES DESCOBERTAS QUE DEFINIRAM ESTE MODULO
-------------------------------------------
1. OCR DA PAGINA INTEIRA NAO SERVE. Devolve uma sopa de numeros sem
   dono - nao da para saber se "3,54" e do braco esquerdo ou do
   direito - e ainda erra: na pagina inteira o percentual do braco
   direito saiu 18,4% no lugar de 78,4%. Recortando a regiao, o mesmo
   Tesseract acerta.

2. AMPLIAR E BINARIZAR PIORA. A tentacao e triplicar a imagem e
   limiarizar antes de ler. Testado: o recorte cru acerta os dez
   valores da analise segmentar, e a versao ampliada devolve "nd DAK"
   no lugar de "3,54kg". A fonte e fina e o reamostramento a destroi.
   As imagens ja estao na resolucao certa.

3. PARSEAR POR ROTULO ONDE DA, E POR VERSAO ONDE NAO DA. Existem dois
   leiautes - F3/230-B-140219 nos exames antigos e F3/230-C-210120 nos
   novos, que ganharam duas linhas em "Dados adicionais". Procurar o
   rotulo dentro da regiao resolve quase tudo com um mapa so. A coluna
   de valores da composicao foi a excecao: tentei um recorte largo o
   bastante para os dois e o leiaute novo QUEBROU, de treze exames
   conferindo para seis. Ali ha um ajuste por versao, escolhido pelo
   codigo que o proprio rodape imprime.

E A DATA MUDA DE FORMATO ENTRE ELES: 2018.06.05 no antigo, 28.08.2026
no novo. Ler so um formato deixava oito arquivos de fora.

O SEPARADOR DECIMAL E A ARMADILHA PRINCIPAL. O OCR ora devolve "3,60",
ora "3.60", e as vezes perde o separador: "11,2" vira "112". Um valor
dez vezes maior passa despercebido numa planilha, mas quebra as
identidades aritmeticas do exame - e e por isso que elas existem.
"""

import re
from datetime import datetime
from pathlib import Path

import pytesseract
from PIL import Image

# O MESMO CODIGO RODA NOS DOIS LUGARES. No Windows o Tesseract instala
# num caminho fixo que nao entra no PATH; no container ele vem do
# apt e fica em /usr/bin. Apontar so para o caminho do Windows fazia a
# carga morrer dentro do Airflow, depois de funcionar a mao.
_TESSERACT_WINDOWS = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if _TESSERACT_WINDOWS.exists():
    pytesseract.pytesseract.tesseract_cmd = str(_TESSERACT_WINDOWS)

LARGURA_ESPERADA, ALTURA_ESPERADA = 1640, 2310

# Recortes em coordenadas da imagem original. Generosos de proposito: o
# parse acontece por rotulo dentro do texto, entao sobra de margem nao
# atrapalha, enquanto falta de margem corta valor.
REGIOES = {
    # Generoso na vertical: o cabecalho desce alguns pixels nos exames
    # antigos, e um recorte justo perdia a data neles.
    "cabecalho":         (0, 120, 1100, 285),
    "composicao_val":    (695, 330, 860, 595),
    "composicao_faixa":  (835, 330, 1030, 595),
    "obesidade":         (265, 1070, 1100, 1230),
    "pontuacao":         (1050, 355, 1570, 425),
    "controle_peso":     (1050, 530, 1460, 675),
    "dados_adicionais":  (1050, 705, 1570, 930),
    "segmentar_magra":   (60, 1360, 540, 1790),
    "segmentar_gordura": (540, 1360, 1020, 1790),
    "impedancia":        (1150, 2050, 1600, 2145),
    "historico":         (60, 1900, 1040, 2210),
    # O rodape sobe uns 40 pixels no leiaute antigo. A faixa cobre os
    # dois - e e dela que sai a versao do template.
    "rodape":            (0, 2190, 1640, 2310),
}

# Ajustes por versao de leiaute, sobre o mapa acima.
#
# POR QUE ISTO EXISTE. Tentei um recorte unico, largo o bastante para
# os dois: o leiaute antigo passou a ler certo e o novo QUEBROU - de
# treze exames conferindo para seis. No antigo a coluna de valores e
# mais estreita e o numero cola no parenteses da faixa ao lado ("8,6"
# vira "86"); no novo, a mesma folga faz o valor e a faixa se
# confundirem ("11,2 (" vira "1124"). Nao ha recorte que sirva aos
# dois, e insistir nisso troca um defeito por outro.
REGIOES_TEMPLATE = {
    "F3/230-B-140219": {
        "composicao_val": (660, 320, 900, 610),
    },
}

# Faixas plausiveis. Servem para pegar o erro mais comum e mais
# perigoso do OCR: o separador decimal que some e multiplica o valor
# por dez. Um numero fora daqui e recusado antes de chegar ao banco.
PLAUSIVEL = {
    "vl_agua_corporal":      (20.0, 70.0),
    "vl_proteina":           (5.0, 25.0),
    "vl_minerais":           (1.5, 7.0),
    "vl_massa_gordura":      (2.0, 60.0),
    "vl_peso":               (35.0, 200.0),
    "vl_imc":                (12.0, 60.0),
    "vl_pgc":                (2.0, 60.0),
    "vl_pontuacao":          (30.0, 120.0),
    "vl_peso_ideal":         (35.0, 150.0),
    "vl_massa_livre_gordura": (25.0, 120.0),
    "vl_massa_muscular_esq": (15.0, 70.0),
    "vl_taxa_metabolica":    (800.0, 3500.0),
    "vl_relacao_cintura_quadril": (0.5, 1.5),
    "vl_gordura_visceral":   (1.0, 30.0),
    "vl_grau_obesidade":     (50.0, 250.0),
    "vl_altura":             (120.0, 220.0),
    "vl_idade":              (5.0, 110.0),
}

SEGMENTOS = ["Braço esquerdo", "Braço direito", "Tronco",
             "Perna esquerda", "Perna direita"]

# O FORMATO DA DATA MUDOU ENTRE OS DOIS LEIAUTES. Os exames ate 2019
# imprimem 2018.06.05, e os de 2024 em diante 28.08.2026 - ano na
# frente contra dia na frente. Ler so um dos dois deixava oito arquivos
# de fora, todos do template antigo.
_DATA_ANO_PRIMEIRO = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
_DATA_DIA_PRIMEIRO = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_HORA = re.compile(r"(\d{2}):(\d{2})")
_ALTURA = re.compile(r"(\d{3})\s*cm", re.I)
_TEMPLATE = re.compile(r"F3/230-([A-Z])-(\d{6})")
# Numero solto, com virgula OU ponto decimal. O sinal negativo entra
# porque "Controle de Peso" vem como "- 0,6".
_NUMERO = re.compile(r"-?\s?\d+(?:[,.]\d+)?")


class ExameIlegivel(Exception):
    """A imagem nao e um exame InBody que este modulo saiba ler."""


def numero(texto):
    """
    Converte o texto lido pelo OCR num float, ou devolve None.

    Aceita virgula e ponto como separador porque o OCR alterna entre os
    dois no mesmo exame - "3,60" numa linha, "124.6" na seguinte.
    """
    if texto is None:
        return None
    achado = _NUMERO.search(str(texto))
    if not achado:
        return None
    try:
        return float(achado.group().replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _ocr(img: Image.Image, regiao: str, template: str = None) -> str:
    """Le uma regiao, respeitando o ajuste da versao de leiaute."""
    box = REGIOES_TEMPLATE.get(template, {}).get(regiao) or REGIOES[regiao]
    return pytesseract.image_to_string(img.crop(box), config="--psm 6")


def _linhas(texto: str) -> list[str]:
    return [l.strip() for l in texto.split("\n") if l.strip()]


def _sem_acento(texto: str) -> str:
    for de, para in (("á", "a"), ("â", "a"), ("ã", "a"), ("é", "e"),
                     ("ê", "e"), ("í", "i"), ("ó", "o"), ("ô", "o"),
                     ("ú", "u"), ("ç", "c")):
        texto = texto.replace(de, para)
    return texto


def _por_rotulo(texto: str, *pedacos: str):
    """
    Acha a linha que contem os pedacos de rotulo e devolve seu numero.

    Compara sem acento e sem caixa porque o OCR erra justamente ai:
    "Relacdo Cintura-Quadii" no lugar de "Relacao Cintura-Quadril". Os
    pedacos sao trechos curtos e distintivos, nao o rotulo inteiro.

    DUAS PRECAUCOES APRENDIDAS NA MARRA. A faixa de referencia vem
    entre parenteses na mesma linha e precisa sair antes, senao o
    limite inferior e lido como se fosse a medida. E o valor e o
    ULTIMO numero da linha, nao o primeiro: o OCR intercala sujeira
    entre o rotulo e o numero - "Taxa MetabdlicaBasal 9 1585 kcal" -
    e o 9 ali nao existe na folha.
    """
    for linha in _linhas(texto):
        if not all(p in _sem_acento(linha.lower()) for p in pedacos):
            continue
        sem_faixa = re.sub(r"\([^)]*\)", " ", linha)
        numeros = [numero(n) for n in _NUMERO.findall(sem_faixa)]
        numeros = [n for n in numeros if n is not None]
        return numeros[-1] if numeros else None
    return None


def _faixa_valida(minimo, maximo, medida=None) -> bool:
    """
    Uma faixa de referencia so vale se for coerente consigo mesma.

    O OCR perde a virgula com frequencia nas faixas - "8,9~10,9" sai
    como "89~10,9" -, e o resultado e um minimo maior que o maximo.
    Faixas do exame sao estreitas, entao um maximo mais de vinte vezes
    o minimo tambem denuncia digito perdido.

    A CONFERENCIA QUE PEGA O RESTO e a propria medida. Quando as duas
    pontas perdem a virgula juntas - "8,9~10,9" virando "89~109" - a
    faixa fica coerente consigo mesma e passaria. Mas a faixa existe
    para dizer se a medida esta dentro dela: se a proteina medida e
    11,2 e a faixa diz 89 a 109, uma das duas leituras esta errada, e
    a faixa e a menos importante das duas.
    """
    if minimo is None or maximo is None or minimo <= 0:
        return False
    if minimo >= maximo:
        return False
    if maximo / minimo > 20:
        return False
    if medida is not None and not (minimo / 2 <= medida <= maximo * 2):
        return False
    return True


def le_template(img: Image.Image) -> str:
    """
    Versao do leiaute, lida do rodape do proprio exame.

    E o que permite um mapa de recortes atender a mais de uma versao, e
    o que faz uma versao desconhecida PARAR a carga em vez de ler
    coordenadas erradas em silencio.
    """
    # Sem template ainda: o recorte do rodape e o unico que precisa
    # servir aos dois leiautes, porque e dele que a versao sai.
    achado = _TEMPLATE.search(_ocr(img, "rodape"))
    return f"F3/230-{achado.group(1)}-{achado.group(2)}" if achado else "desconhecido"


def le_cabecalho(img: Image.Image, template: str = None) -> dict:
    texto = _ocr(img, "cabecalho", template)
    campos = {}

    ano_primeiro = _DATA_ANO_PRIMEIRO.search(texto)
    dia_primeiro = _DATA_DIA_PRIMEIRO.search(texto)
    if ano_primeiro:
        ano, mes, dia = (int(g) for g in ano_primeiro.groups())
    elif dia_primeiro:
        dia, mes, ano = (int(g) for g in dia_primeiro.groups())
    else:
        raise ExameIlegivel(
            "nao achei a data no cabecalho - a imagem pode nao ser um "
            "exame InBody, ou o recorte precisa de ajuste")
    campos["dt_exame"] = datetime(ano, mes, dia).date()
    hora = _HORA.search(texto)
    campos["ds_hora"] = hora.group() if hora else None

    altura = _ALTURA.search(texto)
    campos["vl_altura"] = float(altura.group(1)) if altura else None

    # A idade e o numero solto entre a altura e a data. Procurar por
    # posicao aqui e mais seguro que por rotulo: "Idade" costuma sair
    # como "Idade re" ou colado no valor.
    #
    # O ID DO EXAME SAI PRIMEIRO, e termina em digito solto: "090424-8"
    # entregava idade 8. Ele e removido antes da conta.
    for linha in _linhas(texto):
        if "cm" in linha.lower():
            sobra = re.sub(r"\d{6}\s*-\s*\d", " ", linha)
            sobra = re.sub(r"\d{3}\s*cm", " ", sobra, flags=re.I)
            idades = [int(n) for n in re.findall(r"\b(\d{1,3})\b", sobra)
                      if 5 <= int(n) <= 110]
            if idades:
                campos["vl_idade"] = float(idades[0])
            break
    return campos


def le_composicao(img: Image.Image, template: str = None) -> dict:
    """
    Os cinco valores da composicao corporal, na ordem impressa.

    Aqui a ordem e confiavel: agua, proteina, minerais, gordura e peso
    ocupam cinco linhas fixas, e o proprio exame diz que a ultima e a
    soma das quatro primeiras. E essa soma que confere a leitura.
    """
    nomes = ["vl_agua_corporal", "vl_proteina", "vl_minerais",
             "vl_massa_gordura", "vl_peso"]
    valores = [numero(l) for l in _linhas(_ocr(img, "composicao_val", template))]
    valores = [v for v in valores if v is not None]

    campos = {}
    if len(valores) >= 5:
        campos.update(dict(zip(nomes, valores[:5])))

    # As faixas de referencia mudam com idade e altura, entao valem por
    # exame e nao sao constantes do modelo.
    faixas = _ocr(img, "composicao_faixa", template)
    for nome, linha in zip(nomes, _linhas(faixas)):
        par = re.search(r"(\d+[,.]?\d*)\s*[~-]\s*(\d+[,.]?\d*)", linha)
        if not par:
            continue
        minimo, maximo = numero(par.group(1)), numero(par.group(2))
        if _faixa_valida(minimo, maximo, campos.get(nome)):
            campos[nome + "_min"] = minimo
            campos[nome + "_max"] = maximo
    return campos


def le_obesidade(img: Image.Image, template: str = None) -> dict:
    """
    IMC e percentual de gordura, impressos sob as reguas.

    A REGUA E A ANCORA, e nao a ordem das linhas. Cada indicador ocupa
    duas linhas no OCR - a escala, com uma dezena de marcas, e embaixo
    o valor sozinho -, mas a linha do valor as vezes simplesmente NAO
    e reconhecida. Quando isso acontece com o IMC, contar as linhas de
    valor na ordem entrega o PGC como se fosse IMC: foi assim que um
    exame registrou IMC 19,2 tendo peso 78,4 e 1,79 m.

    As duas reguas se distinguem pelo comeco: a do IMC abre em 10,0 e
    a do PGC em 0,0. O valor pertence a ultima regua vista.
    """
    campos, regua = {}, None
    for linha in _linhas(_ocr(img, "obesidade", template)):
        marcas = re.findall(r"\d+[,.]\d+|\d+", linha)
        if len(marcas) >= 8:
            primeira = numero(marcas[0])
            regua = "vl_imc" if primeira and primeira >= 5 else "vl_pgc"
            continue
        if regua and len(marcas) == 1 and regua not in campos:
            achado = numero(marcas[0])
            if achado is not None:
                campos[regua] = achado
    return campos


def le_paineis(img: Image.Image, template: str = None) -> dict:
    """
    Pontuacao, controle de peso e dados adicionais.

    Tudo por rotulo: e este bloco que muda entre os dois leiautes - o
    novo acrescentou Massa Muscular Esqueletica e Massa Livre de
    Gordura - e procurar por texto atravessa a diferenca sem um mapa
    por versao.
    """
    campos = {}

    pontos = _ocr(img, "pontuacao", template).replace(" ", "")
    achado = re.search(r"(\d{2,3})/100", pontos)
    if achado:
        campos["vl_pontuacao"] = float(achado.group(1))

    peso = _ocr(img, "controle_peso", template)
    campos["vl_peso_ideal"] = _por_rotulo(peso, "peso", "ideal")
    campos["vl_controle_peso"] = _por_rotulo(peso, "controle", "peso")
    campos["vl_controle_gordura"] = _por_rotulo(peso, "controle", "gordura")
    campos["vl_controle_muscular"] = _por_rotulo(peso, "controle", "muscular")

    dados = _ocr(img, "dados_adicionais", template)
    campos["vl_massa_muscular_esq"] = _por_rotulo(dados, "muscular", "esquel")
    campos["vl_massa_livre_gordura"] = _por_rotulo(dados, "livre", "gordura")
    campos["vl_taxa_metabolica"] = _por_rotulo(dados, "metab")
    campos["vl_relacao_cintura_quadril"] = _por_rotulo(dados, "cintura")
    campos["vl_gordura_visceral"] = _por_rotulo(dados, "visceral")
    campos["vl_grau_obesidade"] = _por_rotulo(dados, "obesidade")
    return {k: v for k, v in campos.items() if v is not None}


def _segmentar(texto: str, prefixo: str) -> dict:
    """
    Os cinco segmentos de um dos bonecos.

    O texto sai em blocos de kg, depois %, depois a avaliacao, e na
    ordem esquerda-direita para bracos, tronco sozinho, e
    esquerda-direita para pernas. Os rabiscos do desenho entram como
    lixo no meio, entao filtra-se pelo formato do token.
    """
    kgs = [numero(t) for t in re.findall(r"\d+[,.]\d+\s*kg", texto, re.I)]
    pcts = [numero(t) for t in re.findall(r"\d+[,.]\d+\s*%", texto)]
    aval = re.findall(r"\b(Acima|Normal|Abaixo)\b", texto, re.I)

    campos = {}
    for i, segmento in enumerate(SEGMENTOS):
        chave = f"{prefixo}_{i}"
        if i < len(kgs):
            campos[chave + "_kg"] = kgs[i]
        if i < len(pcts):
            campos[chave + "_pct"] = pcts[i]
        if i < len(aval):
            campos[chave + "_aval"] = aval[i].capitalize()
    return campos


def le_segmentar(img: Image.Image, template: str = None) -> dict:
    campos = _segmentar(_ocr(img, "segmentar_magra", template), "magra")
    campos.update(_segmentar(_ocr(img, "segmentar_gordura", template), "gordura"))
    return campos


def le_impedancia(img: Image.Image, template: str = None) -> dict:
    """
    Dez medidas de impedancia: cinco segmentos em duas frequencias.

    E o dado bruto do aparelho, do qual tudo o mais e derivado. Nao
    entra em nenhuma analise pronta, mas e o unico campo que permitiria
    refazer uma conta se a interpretacao do fabricante mudar.
    """
    linhas = _linhas(_ocr(img, "impedancia", template))
    campos = {}
    freqs = []
    for linha in linhas:
        valores = [numero(v) for v in re.findall(r"\d+[,.]\d+", linha)]
        valores = [v for v in valores if v and 5.0 <= v <= 1000.0]
        if len(valores) >= 4:
            freqs.append(valores[:5])
    for f, freq in enumerate(("20khz", "100khz")):
        if f < len(freqs):
            for i, valor in enumerate(freqs[f]):
                if i < len(SEGMENTOS):
                    campos[f"impedancia_{freq}_{i}"] = valor
    return campos


def confere_identidades(campos: dict) -> list[str]:
    """
    As quatro contas que o proprio exame permite fechar.

    E a conferencia mais valiosa do projeto porque nao depende de
    gabarito externo: roda em todo exame, de graca, e um digito lido
    errado quebra pelo menos uma delas. A tolerancia acompanha o
    arredondamento impresso - a folha mostra uma casa decimal.
    """
    def tem(*chaves):
        return all(campos.get(c) is not None for c in chaves)

    problemas = []

    if tem("vl_agua_corporal", "vl_proteina", "vl_minerais",
           "vl_massa_gordura", "vl_peso"):
        soma = (campos["vl_agua_corporal"] + campos["vl_proteina"]
                + campos["vl_minerais"] + campos["vl_massa_gordura"])
        if abs(soma - campos["vl_peso"]) > 0.25:
            problemas.append(
                f"soma dos componentes {soma:.2f} != peso "
                f"{campos['vl_peso']:.1f} (a folha diz 'A soma acima')")

    if tem("vl_peso", "vl_massa_gordura", "vl_massa_livre_gordura"):
        esperado = campos["vl_peso"] - campos["vl_massa_gordura"]
        if abs(esperado - campos["vl_massa_livre_gordura"]) > 0.25:
            problemas.append(
                f"peso - gordura = {esperado:.2f}, mas massa livre de "
                f"gordura lida = {campos['vl_massa_livre_gordura']:.1f}")

    # peso lido como 0,0 (o "78,0" de 30/10/2026 saiu "TA0'") chega aqui
    # antes da plausibilidade: sem esta guarda, a divisao derrubava a carga
    if tem("vl_massa_gordura", "vl_peso", "vl_pgc") and campos["vl_peso"]:
        esperado = campos["vl_massa_gordura"] / campos["vl_peso"] * 100
        if abs(esperado - campos["vl_pgc"]) > 0.3:
            problemas.append(
                f"gordura/peso = {esperado:.1f}%, mas PGC lido = "
                f"{campos['vl_pgc']:.1f}%")

    if tem("vl_peso", "vl_altura", "vl_imc") and campos["vl_altura"]:
        esperado = campos["vl_peso"] / (campos["vl_altura"] / 100) ** 2
        if abs(esperado - campos["vl_imc"]) > 0.3:
            problemas.append(
                f"peso/altura^2 = {esperado:.1f}, mas IMC lido = "
                f"{campos['vl_imc']:.1f}")

    return problemas


def confere_plausibilidade(campos: dict) -> list[str]:
    """
    Pega o separador decimal que sumiu e multiplicou o valor por dez.

    DESCARTA o valor, e nao apenas avisa. Numero implausivel que chega
    ao banco vira grafico errado meses depois, quando ninguem lembra
    do aviso; o buraco, ao menos, e visivel. O campo vai para o log
    com o valor que foi recusado, para dar para reler depois com o
    recorte ajustado.
    """
    problemas = []
    for chave, (minimo, maximo) in PLAUSIVEL.items():
        valor = campos.get(chave)
        if valor is not None and not (minimo <= valor <= maximo):
            problemas.append(
                f"{chave} = {valor} fora da faixa plausivel "
                f"{minimo}~{maximo} - DESCARTADO (separador decimal perdido?)")
            campos[chave] = None
    return problemas


def recupera_peso(campos: dict) -> list[str]:
    """
    Refaz o peso pelas contas do proprio exame quando a leitura falhou.

    O peso e o numero maior e em negrito da composicao, e e justamente
    o que o Tesseract mais estraga: em 30/10/2026 "78,0" saiu "TA0'" e
    virou 0,0. Ampliar o recorte nao resolve - em 2x saiu "74,0", que
    passa na plausibilidade e esta errado.

    A MAQUINA IMPRIME A MASSA LIVRE DE GORDURA COMO PESO MENOS GORDURA,
    entao peso = massa livre + gordura e exato no arredondamento da
    folha. So vale se a outra identidade concordar: a soma de agua,
    proteina, minerais e gordura ("A soma acima") tem de bater com o
    peso refeito. Se nao bater, o peso fica vazio e a planilha cobre.
    """
    if campos.get("vl_peso") is not None:
        return []
    livre, gordura = campos.get("vl_massa_livre_gordura"), campos.get("vl_massa_gordura")
    partes = [campos.get(c) for c in ("vl_agua_corporal", "vl_proteina", "vl_minerais", "vl_massa_gordura")]
    if not (livre and gordura) or any(p is None for p in partes):
        return []
    peso = round(livre + gordura, 1)
    if abs(sum(partes) - peso) > 0.25:
        return [f"vl_peso nao recuperado: livre+gordura = {peso}, mas a soma "
                f"das parcelas da {sum(partes):.2f}"]
    campos["vl_peso"] = peso
    nota = [f"vl_peso = {peso} RECUPERADO por massa livre + gordura "
            f"(confere com a soma das parcelas, {sum(partes):.2f})"]
    if campos.get("vl_imc") is None and campos.get("vl_altura"):
        campos["vl_imc"] = round(peso / (campos["vl_altura"] / 100) ** 2, 1)
        nota.append(f"vl_imc = {campos['vl_imc']} recalculado por peso/altura^2")
    return nota


def descarta_derivados_conflitantes(campos: dict) -> list[str]:
    """
    Recusa IMC e PGC quando eles contradizem as medidas de origem.

    A PLAUSIBILIDADE SOZINHA NAO PEGA ESTES. Um PGC lido como 3,0 num
    exame cujo gordura/peso da 16,2% e um numero perfeitamente
    plausivel - e perfeitamente errado. Foi assim que quatro exames de
    2018 quase entraram com percentual de gordura de um atleta de elite.

    Sao os DOIS UNICOS campos onde da para saber de quem e a culpa: IMC
    e PGC sao calculados pela maquina a partir de peso, altura e
    gordura, que sao medidas diretas. Se o derivado discorda do
    calculo, o derivado e quem foi lido errado.

    Quando a soma dos componentes falha, ao contrario, nao da para
    saber qual das cinco parcelas errou - e ali nada e descartado, so
    reportado.

    E QUANDO A CONFERENCIA NAO PODE RODAR, ISSO TAMBEM E NOTICIA. Se a
    gordura foi descartada, o teste do PGC fica sem um dos lados e
    simplesmente nao acontece - e um valor errado entra em silencio,
    como se tivesse sido validado. Foi assim que o exame de 13/08/2018
    gravou 9,0% de gordura corporal quando gordura sobre peso dava
    14,8%: o silencio da conferencia que nao rodou pareceu aprovacao.
    """
    problemas = []

    peso, gordura = campos.get("vl_peso"), campos.get("vl_massa_gordura")
    if campos.get("vl_pgc") is not None:
        if peso and gordura:
            esperado = gordura / peso * 100
            if abs(esperado - campos["vl_pgc"]) > 0.3:
                problemas.append(
                    f"vl_pgc = {campos['vl_pgc']} contradiz gordura/peso "
                    f"({esperado:.1f}%) - DESCARTADO, a planilha cobre")
                campos["vl_pgc"] = None
        else:
            problemas.append(
                f"vl_pgc = {campos['vl_pgc']} NAO PODE SER CONFERIDO: falta "
                f"peso ou gordura neste exame. Entrou sem validacao.")

    altura = campos.get("vl_altura")
    if campos.get("vl_imc") is not None:
        if peso and altura:
            esperado = peso / (altura / 100) ** 2
            if abs(esperado - campos["vl_imc"]) > 0.3:
                problemas.append(
                    f"vl_imc = {campos['vl_imc']} contradiz peso/altura^2 "
                    f"({esperado:.1f}) - DESCARTADO, a planilha cobre")
                campos["vl_imc"] = None
        else:
            problemas.append(
                f"vl_imc = {campos['vl_imc']} NAO PODE SER CONFERIDO: falta "
                f"peso ou altura neste exame. Entrou sem validacao.")

    return problemas


def le_exame(caminho) -> dict:
    """
    Le um exame inteiro e devolve os campos mais o resultado das
    conferencias. NAO levanta excecao por valor suspeito: quem decide o
    que fazer com exame duvidoso e a carga, que tem onde registrar.
    """
    img = Image.open(caminho)
    if img.size != (LARGURA_ESPERADA, ALTURA_ESPERADA):
        raise ExameIlegivel(
            f"imagem {img.size[0]}x{img.size[1]}, esperado "
            f"{LARGURA_ESPERADA}x{ALTURA_ESPERADA}. Os recortes valem "
            f"para o render do LookinBody; foto de papel precisa de "
            f"tratamento proprio.")

    # A versao do leiaute e lida ANTES de tudo: e ela que escolhe o
    # mapa de recortes das demais regioes.
    template = le_template(img)
    campos = {"ds_template": template}
    campos.update(le_cabecalho(img, template))
    campos.update(le_composicao(img, template))
    campos.update(le_obesidade(img, template))
    campos.update(le_paineis(img, template))
    campos.update(le_segmentar(img, template))
    campos.update(le_impedancia(img, template))

    campos["_problemas"] = (confere_identidades(campos)
                            + confere_plausibilidade(campos)
                            + recupera_peso(campos)
                            + descarta_derivados_conflitantes(campos))
    return campos


# ---------------------------------------------------------------------
# Do campo lido para a metrica do modelo
# ---------------------------------------------------------------------
# ESTE MAPA E A PONTE ENTRE AS DUAS ORIGENS. A planilha preenchida a
# mao ja alimenta gold.fato_avaliacao_fisica com estes mesmos nomes de
# metrica desde 2008; usar a grafia dela aqui faz o arquivo e a
# planilha caírem na MESMA linha do fato, em vez de criarem duas
# series paralelas para a mesma coisa.
#
# Os nomes a esquerda sao os campos que o OCR produz; os da direita
# tem de existir em gold.dim_metrica_corporal.
MAPA_METRICA = {
    "vl_peso":                    "Peso",
    "vl_massa_muscular_esq":      "Massa Muscular",
    "vl_massa_gordura":           "Massa Gordura",
    "vl_proteina":                "Proteina",
    "vl_minerais":                "Minerais",
    "vl_agua_corporal":           "Agua Corp",
    "vl_imc":                     "IMC",
    "vl_pgc":                     "% Gordura",
    "vl_gordura_visceral":        "Gordura Viceral",
    "vl_pontuacao":               "Pontuação Corpo",
    "vl_altura":                  "Estatura",
    "vl_massa_livre_gordura":     "Massa Livre de Gordura",
    "vl_peso_ideal":              "Peso Ideal",
    "vl_controle_peso":           "Controle de Peso",
    "vl_controle_gordura":        "Controle de Gordura",
    "vl_controle_muscular":       "Controle Muscular",
    "vl_taxa_metabolica":         "Taxa Metabolica Basal",
    "vl_relacao_cintura_quadril": "Relacao Cintura-Quadril",
    "vl_grau_obesidade":          "Grau de Obesidade",
}

# Metricas segmentares: prefixo do campo -> (metrica em kg, metrica em %)
MAPA_SEGMENTAR = {
    "magra":   ("Massa Magra Segmentar", "Massa Magra Segmentar %"),
    "gordura": ("Gordura Segmentar", "Gordura Segmentar %"),
}

CORPO_INTEIRO = "Corpo inteiro"


def campos_para_medidas(campos: dict) -> list[dict]:
    """
    Traduz o resultado da leitura em linhas prontas para a silver.

    Uma linha por metrica e segmento, que e o grao do fato de destino.
    Campo sem valor NAO gera linha: a ausencia tem de ficar visivel
    como buraco, para a planilha poder preenche-lo depois.
    """
    dt = campos.get("dt_exame")
    if dt is None:
        return []

    comum = {"dt_exame": dt, "ds_template": campos.get("ds_template")}
    medidas = []

    for campo, metrica in MAPA_METRICA.items():
        valor = campos.get(campo)
        if valor is None:
            continue
        medidas.append({**comum, "nm_metrica": metrica,
                        "nm_segmento": CORPO_INTEIRO, "vl_medida": valor,
                        "vl_referencia_min": campos.get(campo + "_min"),
                        "vl_referencia_max": campos.get(campo + "_max"),
                        "ds_avaliacao": None})

    for prefixo, (met_kg, met_pct) in MAPA_SEGMENTAR.items():
        for i, segmento in enumerate(SEGMENTOS):
            aval = campos.get(f"{prefixo}_{i}_aval")
            for sufixo, metrica in (("kg", met_kg), ("pct", met_pct)):
                valor = campos.get(f"{prefixo}_{i}_{sufixo}")
                if valor is None:
                    continue
                medidas.append({**comum, "nm_metrica": metrica,
                                "nm_segmento": segmento, "vl_medida": valor,
                                "vl_referencia_min": None,
                                "vl_referencia_max": None,
                                "ds_avaliacao": aval})

    for freq, metrica in (("20khz", "Impedancia 20kHz"),
                          ("100khz", "Impedancia 100kHz")):
        for i, segmento in enumerate(SEGMENTOS):
            valor = campos.get(f"impedancia_{freq}_{i}")
            if valor is None:
                continue
            medidas.append({**comum, "nm_metrica": metrica,
                            "nm_segmento": segmento, "vl_medida": valor,
                            "vl_referencia_min": None,
                            "vl_referencia_max": None, "ds_avaliacao": None})

    return medidas
