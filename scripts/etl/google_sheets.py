"""
Leitura de planilhas do Google publicadas como CSV.

O projeto le a conta familia direto do Google, sem passo manual de
exportar. A planilha e publicada em modo somente leitura (Arquivo >
Compartilhar > Publicar na web), aba a aba e no formato CSV, e o
pipeline consome essa URL.

POR QUE NAO A API OFICIAL. A alternativa seria a Google Sheets API com
conta de servico, que e mais restrita - da acesso so a quem voce
compartilha. Foi a primeira tentativa, mas exigia habilitar a API no
projeto certo do Google Cloud, e a conta tem varios projetos. O link
publicado resolve em minutos e nao depende de nenhuma credencial.

O QUE ISSO CUSTA. Quem tiver a URL ve os dados daquela aba, sem login.
Publique apenas a aba necessaria - nunca o documento inteiro - e trate
a URL como segredo: ela mora no .env, que nao e versionado.

Quando uma origem nova do Google entrar (o diario do Google Forms, por
exemplo), reaproveita este modulo.
"""

import io
import math
import re

import pandas as pd
import requests

TEMPO_LIMITE = 30

# A URL publicada tem um identificador proprio, diferente do ID do
# documento: comeca com 2PACX e so existe enquanto a publicacao estiver
# ativa. Serve para distinguir de um link normal colado por engano.
_RE_PUBLICADA = re.compile(r"/spreadsheets/d/e/2PACX-[\w-]+/pub", re.I)
_RE_DOCUMENTO = re.compile(r"/spreadsheets/d/([\w-]{20,})")


class PlanilhaIndisponivel(RuntimeError):
    """A planilha nao pode ser lida, com o motivo provavel no texto."""


def _valida_url(url: str) -> None:
    if not url or not url.strip():
        raise PlanilhaIndisponivel(
            "URL da planilha vazia. Verifique a variavel no .env.")

    if _RE_PUBLICADA.search(url):
        if "output=csv" not in url:
            raise PlanilhaIndisponivel(
                "A URL e de uma planilha publicada, mas nao em CSV. "
                "Ao publicar, escolha 'Valores separados por virgula (.csv)'.")
        return

    if _RE_DOCUMENTO.search(url):
        raise PlanilhaIndisponivel(
            "Esta e a URL de edicao da planilha, nao a de publicacao.\n"
            "  Em Arquivo > Compartilhar > Publicar na web, escolha a aba, "
            "o formato CSV, publique, e use a URL gerada - ela contem "
            "'/d/e/2PACX-' e termina em 'output=csv'.")

    raise PlanilhaIndisponivel(f"URL nao parece ser de uma planilha Google: {url[:60]}")


def le_planilha_publicada(url: str) -> pd.DataFrame:
    """
    Le uma aba publicada como CSV e devolve um DataFrame.

    Todas as colunas vem como texto: a conversao de tipo e trabalho da
    silver, e deixar o pandas adivinhar aqui produziria resultados
    diferentes conforme o conteudo do mes.
    """
    _valida_url(url)

    try:
        resposta = requests.get(url, timeout=TEMPO_LIMITE)
    except requests.RequestException as erro:
        raise PlanilhaIndisponivel(f"Falha de rede ao buscar a planilha: {erro}")

    if resposta.status_code == 404:
        raise PlanilhaIndisponivel(
            "A planilha respondeu 404. A publicacao pode ter sido "
            "cancelada, ou a aba publicada foi renomeada ou removida.")
    if resposta.status_code != 200:
        raise PlanilhaIndisponivel(
            f"A planilha respondeu HTTP {resposta.status_code}.")

    # O Google nao declara o charset no cabecalho, e o requests entao
    # assume ISO-8859-1. Sem forcar UTF-8, "Descricao" com cedilha vira
    # "DescriÃ§Ã£o" - e o estrago so apareceria depois, no relatorio.
    resposta.encoding = "utf-8"

    # Uma planilha nao publicada devolve HTML de login com status 200,
    # e o pandas leria isso como uma tabela de uma coluna sem reclamar.
    inicio = resposta.text.lstrip()[:200].lower()
    if inicio.startswith("<!doctype html") or "<html" in inicio:
        raise PlanilhaIndisponivel(
            "A URL devolveu uma pagina HTML em vez de CSV, o que indica "
            "que a publicacao nao esta ativa.\n"
            "  Confira em Arquivo > Compartilhar > Publicar na web se a "
            "aba continua publicada.")

    df = pd.read_csv(io.StringIO(resposta.text), dtype=str, keep_default_na=False)
    if df.empty:
        raise PlanilhaIndisponivel("A aba publicada esta vazia.")

    # O CSV publicado nao tem valores nulos: celulas vazias viram "".
    # Uniformiza para None, que e o que as cargas esperam.
    return df.replace("", None)


# =====================================================================
# Conversao dos formatos que o Google Sheets exporta
# =====================================================================
# As demais origens do projeto vem de Excel, onde numero e data ja
# chegam tipados. No CSV publicado tudo e texto, no formato brasileiro
# e com a convencao contabil de negativo entre parenteses. Converter
# errado aqui nao daria erro - daria numero errado no relatorio.

def numero_brasileiro(valor) -> float | None:
    """
    Converte "1.234,56" em 1234.56, e "(1.234,56)" em -1234.56.

    O parenteses e notacao contabil para negativo, usada na planilha da
    familia. Tratar como texto qualquer sinal de menos tambem, porque
    as duas formas convivem na origem.
    """
    if valor is None:
        return None

    # NaN precisa de teste proprio: nao e None, str(nan) da "nan", e
    # float("nan") e uma conversao VALIDA em Python - entao passaria
    # pelo try/except sem erro e voltaria como numero.
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()
    if not texto:
        return None

    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1].strip()

    texto = texto.replace("R$", "").replace(" ", "").replace("\xa0", "")
    # Separador de milhar e ponto, decimal e virgula.
    texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = float(texto)
    except ValueError:
        return None

    # Descarta nan e infinito, que float() aceita mas nao sao valor.
    if not math.isfinite(numero):
        return None

    return -numero if negativo else numero


def data_brasileira(valor) -> str:
    """Converte "17/04/2021" no ISO "2021-04-17". Devolve "" se invalida."""
    if valor is None or not str(valor).strip():
        return ""
    dt = pd.to_datetime(str(valor).strip(), errors="coerce", dayfirst=True)
    return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d")
