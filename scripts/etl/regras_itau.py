"""
Regras da conta corrente Itau.

Hoje contem apenas a extracao de PADRAO da descricao, mas e o lugar
para qualquer regra futura desta origem - o equivalente de regras_xp.py.

Diferente do XP, aqui NAO ha deducao de categoria a partir da
descricao. Os testes mostraram que as descricoes do Itau embutem data
e nome parcial do estabelecimento, o que as torna quase unicas: dos
padroes mais frequentes sem categoria, poucos tinham referencia no
resto da base e alguns se contradiziam. A classificacao vem da
planilha ou do de-para preenchido a mao.
"""

import re

_RE_DATA_EMBUTIDA = re.compile(r"\d{2}/\d{2}")
_RE_NUMEROS = re.compile(r"[\d.\-/*]+")
_RE_ESPACOS = re.compile(r"\s+")


def extrai_padrao(descricao) -> str:
    """
    Reduz a descricao ao seu tipo de operacao.

    Remove numeros, datas embutidas e pontuacao, restando so a parte
    que identifica a natureza do lancamento:

        "PIX TRANSF ALEXAND12/01"   -> "PIX TRANSF ALEXAND"
        "PIX TRANSF  ALEXAND10/08"  -> "PIX TRANSF ALEXAND"
        "TBI 0000.00000-0/500"      -> "TBI"

    E a chave do de-para de categorias: rotular um padrao resolve todos
    os lancamentos que casam com ele, no historico e nas cargas futuras.

    ESTA FUNCAO PRECISA SER A UNICA FONTE DO PADRAO. Se a planilha de
    revisao e a carga da silver calcularem o padrao de formas
    diferentes, os rotulos simplesmente nao casam e o de-para nao
    surte efeito - sem erro nenhum, o que seria dificil de perceber.
    """
    texto = str(descricao).upper()
    texto = _RE_DATA_EMBUTIDA.sub(" ", texto)
    texto = _RE_NUMEROS.sub(" ", texto)
    return _RE_ESPACOS.sub(" ", texto).strip()
