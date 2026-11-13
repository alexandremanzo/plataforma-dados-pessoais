"""
Cliente da API da Pluggy — o caminho ate os investimentos da XP.

POR QUE PLUGGY E NAO A XP DIRETO. A XP nao publica API para pessoa
fisica; o que ela expoe e para assessor e institucional. O caminho que
existe e Open Finance por um agregador, e o "Meu Pluggy" e gratuito por
tempo indeterminado para ate cinco conexoes DO PROPRIO TITULAR - que e
exatamente este caso.

STDLIB, DE PROPOSITO. O projeto usa 'requests' no google_sheets.py, mas
ele nao esta instalado no host Windows: so dentro do container do
Airflow, que o herda do proprio Airflow. Como esta sonda e para rodar
na mao, no host, urllib evita a escolha entre instalar dependencia e
nao rodar.

O SEGREDO NUNCA APARECE. clientId e clientSecret vem do .env e nao sao
impressos, nem em mensagem de erro. A apiKey tambem nao.

Uso como biblioteca:
    from pluggy_api import Pluggy
    api = Pluggy()
    item = api.get(f"/items/{item_id}")
    for inv in api.paginado("/investments", itemId=item_id):
        ...
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

BASE = "https://api.pluggy.ai"
TEMPO_LIMITE = 30

# A apiKey vale 2 horas e o POST /auth tem limite de taxa proprio - a
# documentacao avisa que pedir uma chave por chamada e a forma comum de
# estourar esse limite. Por isso ela e guardada entre execucoes.
#
# O ARQUIVO FICA FORA DO REPOSITORIO, no temp do usuario. Guardado na
# pasta do projeto, bastaria um .gitignore errado para uma credencial
# viva ir parar num commit; no temp isso nao tem como acontecer.
CACHE = Path(tempfile.gettempdir()) / "manzo-pluggy-token.json"
MARGEM_EXPIRACAO = 300          # renova 5 min antes, para nao expirar em voo


class PluggyErro(RuntimeError):
    """Erro da API, com o corpo da resposta — e sem a credencial."""


class Pluggy:
    def __init__(self, client_id: str | None = None,
                 client_secret: str | None = None):
        self._id = client_id or os.getenv("PLUGGY_CLIENT_ID")
        self._segredo = client_secret or os.getenv("PLUGGY_CLIENT_SECRET")
        if not self._id or not self._segredo:
            raise PluggyErro(
                "Faltam PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no .env. "
                "Pegue os dois em dashboard.pluggy.ai, aba Aplicação.")
        self._chave: str | None = None

    # ---------------------------------------------------------------
    # autenticacao
    # ---------------------------------------------------------------

    def _do_cache(self) -> str | None:
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        # A chave e do par de credenciais que a pediu: trocar de
        # aplicacao no dashboard tem de invalidar o cache, e nao
        # reaproveitar uma chave que nao vale mais.
        if d.get("dono") != self._id[-6:]:
            return None
        if d.get("expira_em", 0) - MARGEM_EXPIRACAO < time.time():
            return None
        return d.get("apiKey")

    def _grava_cache(self, chave: str) -> None:
        try:
            CACHE.write_text(json.dumps({
                "apiKey": chave,
                "dono": self._id[-6:],
                "expira_em": time.time() + 2 * 60 * 60,
            }), encoding="utf-8")
        except OSError:
            pass                 # cache e otimizacao, nao requisito

    def chave(self) -> str:
        if self._chave:
            return self._chave
        guardada = self._do_cache()
        if guardada:
            self._chave = guardada
            return guardada
        corpo = json.dumps({"clientId": self._id,
                            "clientSecret": self._segredo}).encode()
        req = urllib.request.Request(
            f"{BASE}/auth", data=corpo, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
                chave = json.loads(r.read())["apiKey"]
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", "replace")[:300]
            if e.code == 401:
                raise PluggyErro(
                    "A Pluggy recusou as credenciais (401). Confira "
                    "PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no .env — "
                    f"e se a aplicação está ativa. Resposta: {detalhe}") from None
            raise PluggyErro(f"POST /auth falhou com HTTP {e.code}: "
                             f"{detalhe}") from None
        except urllib.error.URLError as e:
            raise PluggyErro(f"Não consegui falar com {BASE}: {e.reason}") from None
        self._chave = chave
        self._grava_cache(chave)
        return chave

    # ---------------------------------------------------------------
    # chamadas
    # ---------------------------------------------------------------

    def get(self, caminho: str, **params) -> dict:
        qs = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
        url = f"{BASE}{caminho}" + (f"?{qs}" if qs else "")
        req = urllib.request.Request(
            url, headers={"X-API-KEY": self.chave(),
                          "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", "replace")[:300]
            # A URL vai na mensagem SEM a query, que pode levar ids;
            # o que importa para diagnosticar e o caminho e o codigo.
            raise PluggyErro(f"GET {caminho} devolveu HTTP {e.code}: "
                             f"{detalhe}") from None
        except urllib.error.URLError as e:
            raise PluggyErro(f"GET {caminho} não completou: {e.reason}") from None

    def post(self, caminho: str, corpo: dict) -> dict:
        """POST autenticado. Usado para criar a conexão (item).

        Separado do get de propósito: isto ESCREVE na conta da Pluggy.
        Criar um item é reversível (DELETE /items/{id}), mas é estado
        em serviço de terceiro, e quem lê o código tem de ver isso.
        """
        req = urllib.request.Request(
            f"{BASE}{caminho}", data=json.dumps(corpo).encode(), method="POST",
            headers={"X-API-KEY": self.chave(),
                     "Content-Type": "application/json",
                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", "replace")[:400]
            raise PluggyErro(f"POST {caminho} devolveu HTTP {e.code}: "
                             f"{detalhe}") from None
        except urllib.error.URLError as e:
            raise PluggyErro(f"POST {caminho} não completou: {e.reason}") from None

    def paginado(self, caminho: str, **params):
        """Percorre todas as páginas de um endpoint que devolve results.

        Tolerante de propósito: alguns endpoints devolvem uma LISTA
        direta em vez do envelope {total, totalPages, page, results}, e
        uma sonda que quebra por causa do formato não cumpre o papel
        dela, que é justamente descobrir o formato.
        """
        pagina = 1
        while True:
            d = self.get(caminho, page=pagina,
                         pageSize=params.pop("pageSize", 200), **params)
            if isinstance(d, list):
                yield from d
                return
            resultados = d.get("results", [])
            yield from resultados
            total_paginas = d.get("totalPages") or 1
            if pagina >= total_paginas or not resultados:
                return
            pagina += 1
