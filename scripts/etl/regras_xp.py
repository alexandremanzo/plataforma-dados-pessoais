"""
Regras de classificacao das movimentacoes da XP.

Traduz a descricao textual do lancamento em categoria, ativo e
marcacao de rendimento. E a unica fonte dessas regras no projeto:
tanto a carga da silver quanto qualquer analise ad-hoc devem
importar daqui, para nao existirem dois criterios em paralelo.

Origem: scripts/prd/trata-arquivo-xp-invest.ipynb, com duas
correcoes em relacao ao original:

1. CASAMENTO POR PALAVRA INTEIRA. O notebook testava substring
   simples, entao o termo 'IR' casava dentro de 'tesouro DIRETO' e
   classificava "LIQUIDACAO TESOURO DIRETO" como imposto de renda.
   Termos curtos e ambiguos agora exigem fronteira de palavra.

2. COMPARACAO SEM ACENTO. A mesma descricao aparece grafada de
   formas diferentes entre o extrato e a planilha ('BALCAO' e
   'BALCAO' com til), o que fazia a regra falhar em parte da serie.
   Descricao e padrao sao normalizados antes de comparar.
"""

import re
import unicodedata

# Categorias em que um valor positivo representa remuneracao do
# patrimonio investido, e nao aporte ou devolucao de principal.
CATEGORIAS_RENDIMENTO = frozenset({
    "Dividendo", "Investback", "Reembolso", "Taxa de Remuneração",
})

# A ORDEM IMPORTA: a primeira regra que casar vence. Cada entrada e um
# par (regex, categoria) - regex explicita em vez de substring, para
# deixar visivel onde a fronteira de palavra e necessaria.
#
# O bloco de cima resolve prefixos que qualificam o lancamento inteiro.
# "IR - RESGATE CDB..." e uma cobranca de imposto sobre um resgate, nao
# um resgate; sem ancorar no inicio, a regra de RESGATE vencia e o
# lancamento era classificado errado.
REGRAS_CATEGORIA: list[tuple[str, str]] = [
    # --- Prefixos que definem a natureza do lancamento ---
    (r"^IR\b",                                    "IR"),
    (r"\bIRRF\b",                                 "IR"),

    # --- Termos especificos ---
    (r"AJUSTE DE CUSTOS",                         "Ajuste de Custos"),
    (r"REPASSE DE JUROS",                         "Dividendo"),
    (r"LIQUIDACAO TESOURO DIRETO",                "Liquidação"),
    (r"TAXA DE INTERMEDIACAO",                    "Taxa de intermediação"),
    (r"TAXA DE REMUNERACAO",                      "Taxa de Remuneração"),
    (r"ESTORNO PREVIA CHAMADA DE MARGEM",         "Margem"),
    (r"ESTORNO DE OPERACOES",                     "Estorno"),
    (r"DEBITO SUBSCRICAO",                        "Débito Subscrição"),
    (r"SUBSCRICAO",                               "Subscrição"),

    # IOF antes de INVESTBACK: "IOF S/ RESGATE FUNDOS - Trend Investback"
    # e cobranca de IOF, nao operacao do fundo.
    (r"\bIOF\b",                                  "IOF"),

    (r"INTEGRALIZACAO DE COTAS",                  "Operação Bolsa"),
    (r"OPERACOES EM BOLSA",                       "Operação Bolsa"),
    (r"FRACOES DE ACOES",                         "Dividendo"),
    (r"JUROS S/ CAPITAL",                         "Dividendo"),
    (r"PGTO JUROS",                               "Dividendo"),
    (r"RENDIMENTO",                               "Dividendo"),
    (r"DIVIDENDOS",                               "Dividendo"),
    (r"REEMB\. EVENTO",                           "Reembolso"),
    (r"REEMBOLSO",                                "Reembolso"),
    (r"TRANSFERENCIA ENVIADA PARA A CONTA DIGITAL", "Pagamento CC"),
    (r"TRANSFERENCIA RECEBIDA DA CONTA DIGITAL",  "Transferência"),
    (r"RECEBIMENTO DE TED",                       "Transferência"),
    (r"RETIRADA EM C/C",                          "Retirada"),
    (r"MARGEM",                                   "Margem"),
    (r"COMPRA",                                   "Compra"),

    # \bIR\b no meio da descricao: pega "IR" como palavra solta mas nao
    # dentro de "tesouro DIRETO", que era o bug do notebook original.
    (r"\bIR\b",                                   "IR"),

    (r"EMOLUMENTOS",                              "Emolumentos"),
    (r"MULTA",                                    "Multa"),
    (r"PAGAMENTO",                                "Pagamento"),
    (r"RESGATE",                                  "Resgate"),
    (r"APLICACAO",                                "Aplicação"),
    (r"VENCIMENTO",                               "Vencimento"),

    # INVESTBACK por ultimo, como rede: a categoria descreve a OPERACAO
    # (aplicacao, resgate, IOF), e o fundo fica registrado em ds_ativo.
    # So cai aqui o lancamento do fundo que nao nomeia nenhuma operacao.
    (r"INVESTBACK",                               "Investback"),
]

CATEGORIA_PADRAO = "Outros"


def normaliza(texto) -> str:
    """Maiuscula, sem acento, com espacos colapsados."""
    if texto is None:
        return ""
    txt = unicodedata.normalize("NFKD", str(texto))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().upper()


# Pre-compila os padroes uma vez, no import.
_PADROES = [(re.compile(padrao), categoria) for padrao, categoria in REGRAS_CATEGORIA]


def classifica_categoria(descricao) -> str:
    """Devolve a categoria do lancamento, ou 'Outros' se nenhuma regra casar."""
    desc = normaliza(descricao)
    for padrao, categoria in _PADROES:
        if padrao.search(desc):
            return categoria
    return CATEGORIA_PADRAO


def extrai_ativo(descricao) -> str | None:
    """
    Extrai o ativo mencionado na descricao.

    A ordem dos testes vai do formato mais especifico para o mais
    generico, porque varios padroes se sobrepoem: um lancamento de
    fundo de balcao tambem contem algo parecido com ticker.
    """
    desc = normaliza(descricao)

    # 1. Aluguel de acoes (BTC)
    m = re.search(r"BTC\s+[A-Z0-9]{4,}", desc)
    if m:
        return m.group()

    # 2. Fundo fechado de balcao: o nome vem depois da palavra BALCAO
    if "BALCAO" in desc:
        resto = desc.split("BALCAO")[-1].strip()
        resto = re.sub(r"\d{5,}.*", "", resto).strip()
        # A origem as vezes traz lixo de preenchimento antes do nome
        # ("BALCAO AAAAAAAAAA  XP Habitat FII"). Remove sequencias de
        # uma mesma letra repetida, que nunca sao nome de ativo.
        resto = re.sub(r"\b([A-Z])\1{3,}\b", " ", resto).strip()
        resto = re.sub(r"\s+", " ", resto)
        if "VALORA CRI" in resto:
            return "Valora CRI"
        m = re.search(r"(.*?FII)", resto)
        if m:
            return m.group(1).strip()
        return resto.split(" - ")[0].strip() or None

    # 3. Trend Investback: vem antes da regra generica de FUNDOS porque a
    # descricao costuma trazer as duas palavras ("RESGATE FUNDOS - Trend
    # Investback FIC FI"), e a generica devolveria um nome sujo.
    if "INVESTBACK" in desc:
        return "Trend Investback FIC FI"

    # 4. Tesouro Direto
    if "TESOURO DIRETO" in desc:
        return "TESOURO DIRETO"

    # 4. Fundos de investimento
    if "FUNDOS" in desc:
        m = re.search(r"FUNDOS\s+.*?(?=FIC FI|$)(\s*FIC FI)?", desc)
        if m:
            return m.group().strip()

    # 5. LCA / LCI: o emissor vem depois do pipe
    if "LCA" in desc or "LCI" in desc:
        m = re.search(r"\|\s*(LC[AI]\s+.*?)(?=-|\d{2}/|$)", desc)
        if m:
            return m.group(1).strip()

    # 6. COE
    if "COE" in desc:
        m = re.search(r"\|\s*(COE\s+.*)$", desc)
        if m:
            return m.group(1).strip()

    # 7. Ticker de acao ou FII (PETR4, HGLG11, B3SA3) ou codigo ISIN
    m = re.search(r"\b[A-Z][A-Z0-9]{3}\d{1,2}\b|\bBR[A-Z0-9]{10,}\b", desc)
    if m:
        return m.group()

    # 8. CDB. Preserva o indicador de remuneracao (FLU = pos-fixado,
    # PRE DU = pre-fixado): e justamente a distincao usada na
    # classificacao por subclasse, e a versao antiga desta regra a
    # descartava, devolvendo so "CDB <codigo>".
    if "CDB" in desc:
        m = re.search(r"\bCDB\s+(FLU|PRE\s+DU)\s+(CDB[A-Z0-9]+)", desc)
        if m:
            tipo = re.sub(r"\s+", " ", m.group(1))
            return f"CDB {tipo} {m.group(2)}"

        # Formato com emissor depois do pipe: "... | CDB PERNAMBUCANAS"
        m = re.search(r"\|\s*(CDB\s+[A-Z][A-Z\s./()]*)", desc)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()

        return ("CDB " + desc.split("CDB")[-1].strip()).strip()

    return None


# =====================================================================
# Resolucao de ISIN para ticker
# =====================================================================
# A XP as vezes identifica o ativo pelo ticker (ITUB4) e as vezes pelo
# ISIN (BRITUBACNPR1), dependendo do tipo de lancamento - reembolso de
# evento e subscricao usam ISIN. Sem resolver, o mesmo ativo aparece
# duas vezes na dimensao e os proventos ficam divididos.
#
# No ISIN brasileiro os caracteres 3-6 sao o mnemonico do emissor (o
# prefixo do ticker) e os seguintes indicam a especie:
#
#     BR | ITUB | ACNPR | 1
#          ^^^^   ^^^^^
#          ticker especie (PR = preferencial -> sufixo 4)

# Casos que o algoritmo nao resolve sozinho, resolvidos por evidencia
# na propria base. Acrescente aqui quando um ISIN novo aparecer sem
# resolucao automatica - e o unico lugar do projeto onde um ativo e
# mapeado a mao, e cada entrada precisa dizer em que se baseia.
DE_PARA_ISIN = {
    # Especie "ARNPC" (preferencial resgatavel) nao segue o padrao ACN*
    # e daria CPLE7, que nao existe. A base mostra que a preferencial
    # em carteira era a CPLE5: em 18/11/2025 ha "Taxa de intermediacao
    # doador CPLE5", o resgate ocorre em 30/12/2025, e a partir de
    # janeiro/2026 so aparecem lancamentos de CPLE3.
    "BRCPLEARNPC5": "CPLE5",
}

SUFIXO_POR_ESPECIE = {
    "OR": "3",   # ordinaria
    "PR": "4",   # preferencial
    "PA": "5",   # preferencial classe A
    "PB": "6",   # preferencial classe B
    "PC": "7",   # preferencial classe C
}

# Especies em que o sufixo e certo. As classes A/B/C sao menos comuns e
# nem toda empresa as emite, entao so aceitamos a resolucao delas se o
# ticker resultante ja existir na base - evidencia em vez de deducao.
ESPECIES_SEGURAS = frozenset({"OR", "PR"})

# O mnemonico do ticker nem sempre e so letras: B3SA3 e M1TA34 tem
# digito no meio. Exigir 4 letras deixava B3SA3 sem classe e sem
# extracao a partir da descricao.
_RE_TICKER = re.compile(r"^[A-Z][A-Z0-9]{3}\d{1,2}$")
_RE_MNEMONICO = re.compile(r"^[A-Z][A-Z0-9]{3}$")
_RE_ISIN = re.compile(r"^BR[A-Z0-9]{10}$")
_RE_COTA_FUNDO = re.compile(r"^R\d{2}M")


def resolve_isin(codigo: str, tickers_conhecidos: set[str] | None = None) -> str | None:
    """
    Converte um ISIN brasileiro no ticker correspondente.

    Devolve None quando o codigo nao e um ISIN ou quando a especie e
    ambigua e o ticker deduzido nao consta entre os conhecidos. Nesse
    caso o chamador deve preservar o ISIN: um ativo nao identificado
    atrapalha menos que um ticker inventado.
    """
    if not isinstance(codigo, str) or not _RE_ISIN.match(codigo.strip().upper()):
        return None

    cod = codigo.strip().upper()

    # O de-para manual tem precedencia: e usado justamente para os casos
    # em que a regra geral erraria.
    if cod in DE_PARA_ISIN:
        return DE_PARA_ISIN[cod]

    mnemonico, especie = cod[2:6], cod[6:11]

    # Direito de subscricao (especie R__M): NAO se resolve para ticker.
    # A regra antiga o mandava para o sufixo 11, ou seja, para a cota do
    # proprio FII - o que juntava o direito de subscricao com o ativo
    # subscrito e atribuia a subscricao ao ativo errado. O direito tem
    # ticker proprio (KNCR13 para KNCR11, TRXF13 para TRXF11), mas o
    # sufixo varia por emissao, entao preferimos manter o ISIN e deixar
    # a classificacao para o de-para de classes.
    if _RE_COTA_FUNDO.match(especie):
        return None

    # Unit e cota de fundo usam sufixo 11.
    if especie.startswith(("CDA", "CTF")):
        candidato = f"{mnemonico}11"
        if tickers_conhecidos is None or candidato in tickers_conhecidos:
            return candidato
        return None

    # Acoes: a especie fica nos dois ultimos caracteres (ACNOR, ARNPC...).
    if especie.startswith(("ACN", "ARN")):
        classe = especie[3:5]
        sufixo = SUFIXO_POR_ESPECIE.get(classe)
        if not sufixo:
            return None

        candidato = f"{mnemonico}{sufixo}"
        if classe in ESPECIES_SEGURAS:
            return candidato
        if tickers_conhecidos and candidato in tickers_conhecidos:
            return candidato
        return None

    return None


def normaliza_ativo(codigo: str | None,
                    tickers_conhecidos: set[str] | None = None) -> str | None:
    """
    Padroniza o codigo do ativo, resolvendo ISIN quando possivel.

    Trata tambem os lancamentos de aluguel, em que o ISIN vem depois do
    prefixo BTC ("BTC BRITUBACNPR1" vira "BTC ITUB4"). Assim o aluguel
    de um papel deixa de se fragmentar em dois ativos distintos.
    """
    # Ausencia de ativo chega como None ou, quando o valor passou por
    # uma coluna do pandas, como NaN - que e float e nao tem .strip().
    if not isinstance(codigo, str) or not codigo.strip():
        return None

    cod = codigo.strip()

    if cod.upper().startswith("BTC "):
        resto = cod[4:].strip()
        resolvido = resolve_isin(resto, tickers_conhecidos)
        if resolvido:
            return f"BTC {resolvido}"
        # "BTC ITUB" (mnemonico sem especie): completa se houver um unico
        # ticker conhecido com esse prefixo.
        if tickers_conhecidos and _RE_MNEMONICO.match(resto.upper()):
            candidatos = {t for t in tickers_conhecidos if t.startswith(resto.upper())}
            if len(candidatos) == 1:
                return f"BTC {candidatos.pop()}"
        return cod

    return resolve_isin(cod, tickers_conhecidos) or cod


# =====================================================================
# Consolidacao de nomes de fundo
# =====================================================================
# A XP trunca a descricao num comprimento fixo, e o prefixo do
# lancamento tem tamanho variavel ("TED TER BCO 33 AGE 2271 CTA
# 130164087 - TED APLICACAO FUNDOS ..."), entao o nome do fundo e
# cortado em pontos diferentes conforme a conta de destino:
#
#     FUNDOS TREND BOLSA AMERIC
#     FUNDOS TREND BOLSA AMERICANA
#     FUNDOS TREND BOLSA AMERICANA FIA
#
# Sao o mesmo fundo virando tres ativos distintos na dimensao. A
# consolidacao junta os codigos em que um e prefixo do outro.

_RE_FIF_RF = re.compile(r"\bFIF\s+RF\b")


def _forma_comparavel(codigo: str) -> str:
    """
    Forma usada so para comparar, nunca para exibir.

    Trata "FIF RF" e "FIRF" como equivalentes: a CVM 175 renomeou a
    nomenclatura dos fundos, e o mesmo fundo aparece das duas formas.
    O caso do "XP Referenciado" confirma - as duas grafias apontam para
    a mesma conta de destino no extrato.
    """
    texto = _RE_FIF_RF.sub("FIRF", codigo.upper())
    texto = re.sub(r"-+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def consolida_fundos(codigos) -> dict[str, str]:
    """
    Mapeia cada codigo de fundo para o representante da sua familia.

    O representante e o codigo com a forma comparavel mais longa entre
    os que formam cadeia de prefixo com ele - ou seja, o nome menos
    truncado. Codigos que nao sao fundo passam inalterados.

    Aplica-se apenas a nomes de fundo porque so eles sofrem o
    truncamento: ticker e ISIN tem tamanho fixo.
    """
    fundos = [c for c in codigos
              if isinstance(c, str) and c.upper().startswith("FUNDOS ")]
    if not fundos:
        return {}

    norm = {c: _forma_comparavel(c) for c in fundos}
    mapa = {}
    for codigo in fundos:
        familia = [
            outro for outro in fundos
            if norm[outro].startswith(norm[codigo])
            or norm[codigo].startswith(norm[outro])
        ]
        mapa[codigo] = max(familia, key=lambda c: len(norm[c]))
    return mapa


def subclasse_fundo(codigo: str | None) -> str:
    """
    Deduz a estrategia do fundo pelo sufixo do nome.

    A nomenclatura da industria e informativa: FIA e fundo de acoes,
    FIM e multimercado, FIRF e renda fixa. Usar isso e melhor que
    rotular tudo como "Fundo de Investimento", mas continua sendo
    deducao - por isso o resultado entra marcado como DEDUZIDA, e
    qualquer entrada no de-para manual tem precedencia.
    """
    if not codigo:
        return "Fundo de Investimento"
    cod = codigo.upper()

    if re.search(r"\bFIA\b|\bBOLSA\b|\bIBOVESPA\b|\bEQUITY\b|\bACOES\b", cod):
        return "Fundo de Ações"
    if re.search(r"\bFIM\b|\bMULTI\b|\bMACRO\b|\bHEDGE\b|\bOURO\b", cod):
        return "Fundo Multimercado"
    if re.search(r"\bFIRF\b|\bFIF\s+RF\b|\bRF\b|\bREFERENCIADO\b|\bDI\b", cod):
        return "Fundo de Renda Fixa"
    return "Fundo de Investimento"


def classifica_tipo_ativo(codigo: str | None) -> str:
    """Deduz a classe do ativo pelo formato do codigo."""
    if not codigo:
        return "Não classificado"
    cod = codigo.upper()

    if cod.startswith("BTC "):
        return "Aluguel BTC"
    if cod.startswith("CDB"):
        return "CDB"
    if "TESOURO DIRETO" in cod:
        return "Tesouro Direto"
    if "COE" in cod:
        return "COE"
    if re.match(r"^LC[AI]\b", cod):
        return "LCA/LCI"
    if "CRI" in cod:
        return "CRI"
    if "FII" in cod:
        return "FII"
    if "FIC FI" in cod or "FUNDO" in cod or "INVESTBACK" in cod:
        return "Fundo"

    # ISIN que nao resolveu: a especie ainda diz a classe.
    if _RE_ISIN.match(cod):
        especie = cod[6:11]
        if especie.startswith(("CDA", "CTF")) or _RE_COTA_FUNDO.match(especie):
            return "Fundo"
        if especie.startswith(("ACN", "ARN")):
            return "Ação"
        return "Não classificado"

    # Ticker terminado em 11 costuma ser FII, unit ou ETF.
    if re.match(r"^[A-Z][A-Z0-9]{3}11$", cod):
        return "FII"
    if _RE_TICKER.match(cod):
        return "Ação"

    # Nomes com espaco que sobraram vem dos fundos fechados de balcao,
    # cuja descricao traz o nome por extenso em vez de codigo.
    if " " in cod:
        return "Fundo"

    return "Não classificado"


def tickers_de(codigos) -> set[str]:
    """Extrai o conjunto de tickers validos de uma colecao de codigos."""
    return {c.upper() for c in codigos if c and _RE_TICKER.match(str(c).upper())}


def eh_rendimento(categoria: str, valor: float | None) -> bool:
    """Verdadeiro quando o lancamento e remuneracao do patrimonio."""
    if valor is None or valor <= 0:
        return False
    return categoria in CATEGORIAS_RENDIMENTO


def tipo_movimentacao(valor: float | None) -> str | None:
    """RECEITA para valor positivo, DESPESA para negativo."""
    if valor is None:
        return None
    return "RECEITA" if valor > 0 else "DESPESA"
