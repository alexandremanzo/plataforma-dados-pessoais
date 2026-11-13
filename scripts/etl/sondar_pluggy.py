"""
Sonda a API da Pluggy e mostra o que a XP realmente devolve.

NAO ESCREVE NO BANCO. Existe para a modelagem vir DEPOIS de ver o dado,
e nao antes: a documentacao da Pluggy diz o que o conector suporta em
geral, mas o que chega depende do que a instituicao declara no
consentimento. Desenhar bronze.xp_posicao a partir da documentacao
seria desenhar a partir de uma promessa.

O que ela responde, em ordem:

  1. a conexao esta viva? qual conector, qual status, de quando e o dado
  2. quantos investimentos, de que tipos, com que saldo
  3. ha TRANSACOES? quantas, de quando ate quando, de que tipos
  4. o que a API traz e o extrato nao traz - e vice-versa

O passo 4 e o que decide a conversa. Hoje bronze.xp_movimentacao tem
2.627 eventos vindos do extrato em xlsx; se a API cobrir a mesma
janela com os mesmos eventos, da para aposentar o download manual. Se
cobrir menos, ela entra como complemento e o extrato fica.

Uso:
    python sondar_pluggy.py                 # resumo
    python sondar_pluggy.py --item <uuid>   # se houver mais de um item
    python sondar_pluggy.py --bruto         # grava o JSON cru para modelar
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "scripts" / "conf"))

from pluggy_api import Pluggy, PluggyErro  # noqa: E402

# O dump fica FORA do repositorio: e a carteira inteira, com ativo,
# quantidade e saldo. Dentro, dependeria de um .gitignore certo.
DESTINO_BRUTO = Path(os.getenv("LOCALAPPDATA", BASE)) / "manzo-pluggy-sonda"


def brl(v) -> str:
    if v is None:
        return "—"
    return ("R$ " + f"{float(v):,.2f}").replace(",", "~").replace(".", ",").replace("~", ".")


def dia(v) -> str:
    if not v:
        return "—"
    return str(v)[:10]


def itens(api: Pluggy, escolhido: str | None) -> list:
    """Os itens (conexões) da aplicação.

    Com --item, usa o que foi passado. Sem ele, tenta listar; se a
    conta não expuser listagem, pede o id explicitamente em vez de
    adivinhar.
    """
    alvo = escolhido or os.getenv("PLUGGY_ITEM_ID")
    if alvo:
        try:
            return [api.get(f"/items/{alvo}")]
        except PluggyErro as e:
            # 404 aqui quase sempre significa item recriado: apagar e
            # reconectar pelo Dashboard gera um id NOVO, e o .env fica
            # apontando para o antigo. Dizer isso poupa procurar
            # problema na credencial, que continua certa.
            if "404" not in str(e):
                raise
            print(f"  O item {alvo[:8]}… não existe mais (404).")
            print("  Se você apagou e reconectou, o id mudou. Pegue o novo")
            print("  em dashboard.pluggy.ai → sua aplicação → o item, no")
            print("  código do topo (tem um ícone de copiar ao lado), e")
            print("  atualize PLUGGY_ITEM_ID no .env.")
            return []
    # A PLUGGY NAO LISTA ITENS. GET /items devolve 401 mesmo com a chave
    # boa - nao e credencial errada, e endpoint que nao existe para o
    # cliente. Quem guarda o id da conexao e voce. A primeira versao
    # desta mensagem dizia "nao consegui listar os itens", o que manda
    # procurar o problema na credencial, que esta certa.
    try:
        return list(api.paginado("/items"))
    except PluggyErro:
        print("  A Pluggy não oferece listagem de conexões: o id da conexão")
        print("  (itemId) fica com você. Pegue em dashboard.pluggy.ai →")
        print("  sua aplicação → Conexões, e rode de novo com:")
        print("     python sondar_pluggy.py --item <uuid>")
        print("  ou ponha PLUGGY_ITEM_ID no .env para não repetir.")
        return []


def main() -> int:
    p = argparse.ArgumentParser(description="Sonda a API da Pluggy")
    p.add_argument("--item", help="id da conexão, se houver mais de uma")
    p.add_argument("--bruto", action="store_true",
                   help="grava o JSON cru, para desenhar as tabelas")
    args = p.parse_args()

    try:
        api = Pluggy()
        # Autentica ANTES de qualquer consulta. Sem isto, uma credencial
        # errada aparecia como "não consegui listar os itens", que manda
        # procurar o problema no lugar errado.
        api.chave()
    except PluggyErro as e:
        print(f"ERRO: {e}")
        return 1

    print("=== 1. CONEXÕES ===")
    try:
        lista = itens(api, args.item)
    except PluggyErro as e:
        print(f"ERRO: {e}")
        return 1
    if not lista:
        return 1

    bruto: dict = {"itens": lista, "investimentos": [], "transacoes": {}}

    for it in lista:
        con = it.get("connector") or {}
        print(f"  item {it.get('id')}")
        print(f"     conector    {con.get('name')} (id {con.get('id')}, "
              f"{con.get('type')})")
        print(f"     status      {it.get('status')} / {it.get('executionStatus')}")
        print(f"     atualizado  {dia(it.get('lastUpdatedAt'))}")
        # O consentimento de Open Finance vence - e quando vence, a
        # integracao para em silencio. Por isso a data aparece aqui.
        if it.get("consecutiveFailedLoginAttempts"):
            print(f"     falhas seguidas de login: "
                  f"{it['consecutiveFailedLoginAttempts']}")
        for campo in ("expiresAt", "consentExpiresAt"):
            if it.get(campo):
                print(f"     consentimento vence em {dia(it[campo])}  <-- anotar")
        if it.get("error"):
            print(f"     ERRO NO ITEM: {it['error']}")

    print("\n=== 2. INVESTIMENTOS ===")
    total_posicao = 0.0
    investimentos: list = []
    for it in lista:
        try:
            achados = list(api.paginado("/investments", itemId=it.get("id")))
        except PluggyErro as e:
            print(f"  não vieram investimentos deste item: {e}")
            continue
        investimentos.extend(achados)

    if not investimentos:
        print("  nenhum investimento retornado.")
        print("  Se a conexão é nova, a primeira sincronização pode levar")
        print("  alguns minutos. Se persistir, o consentimento pode não ter")
        print("  incluído investimentos — refaça em meu.pluggy.ai marcando")
        print("  'Investimentos'.")
    else:
        bruto["investimentos"] = investimentos
        por_tipo = Counter()
        for inv in investimentos:
            t = f"{inv.get('type')}/{inv.get('subtype') or '—'}"
            por_tipo[t] += 1
            total_posicao += float(inv.get("balance") or inv.get("amount") or 0)
        print(f"  {len(investimentos)} investimentos · "
              f"posição somada {brl(total_posicao)}")
        print("\n  por tipo:")
        for t, n in por_tipo.most_common():
            print(f"     {t:<38} {n}")
        print("\n  os dez maiores:")
        maiores = sorted(investimentos,
                         key=lambda i: float(i.get("balance") or i.get("amount") or 0),
                         reverse=True)[:10]
        for inv in maiores:
            print(f"     {str(inv.get('name'))[:40]:<42} "
                  f"{brl(inv.get('balance') or inv.get('amount')):>16}   "
                  f"{inv.get('type')}")
        # Os campos que a posicao traz decidem o desenho de
        # bronze.xp_posicao - por isso a lista de chaves vai impressa.
        chaves = sorted({k for i in investimentos for k in i})
        print(f"\n  campos presentes ({len(chaves)}):")
        print("     " + " · ".join(chaves))

    print("\n=== 3. TRANSAÇÕES ===")
    if not investimentos:
        print("  sem investimentos, não há o que buscar.")
    else:
        total, tipos, datas, com, sem = 0, Counter(), [], 0, 0
        for inv in investimentos:
            try:
                tx = list(api.paginado(f"/investments/{inv['id']}/transactions"))
            except PluggyErro as e:
                print(f"  {str(inv.get('name'))[:30]}: {e}")
                continue
            if tx:
                com += 1
                bruto["transacoes"][inv["id"]] = tx
            else:
                sem += 1
            total += len(tx)
            for t in tx:
                tipos[f"{t.get('type')}/{t.get('movementType') or '—'}"] += 1
                d = t.get("tradeDate") or t.get("date")
                if d:
                    datas.append(str(d)[:10])
        print(f"  {total} transações · {com} investimentos com histórico, "
              f"{sem} sem")
        if datas:
            print(f"  janela: {min(datas)} a {max(datas)}")
        if tipos:
            print("\n  tipos encontrados:")
            for t, n in tipos.most_common():
                print(f"     {t:<28} {n}")
        if total == 0:
            print("\n  A XP cobre transações de Fundos, Renda Fixa, Tesouro,")
            print("  Ações e COE segundo a documentação. Zero aqui significa")
            print("  que o consentimento não as incluiu, ou que a carga ainda")
            print("  não rodou.")

    print("\n=== 4. CONTRA O QUE JÁ EXISTE NO DW ===")
    try:
        import pandas as pd
        from config_db import get_engine
        hoje = pd.read_sql("""
            SELECT COUNT(*) eventos, MIN(ds_movimentacao) de,
                   MAX(ds_movimentacao) ate
            FROM bronze.xp_movimentacao""", get_engine())
        print(f"  bronze.xp_movimentacao: {int(hoje.eventos.iloc[0])} eventos "
              f"(do extrato em xlsx)")
        print(f"  API:                    {total if investimentos else 0} transações")
        print("\n  A comparação evento a evento é o próximo passo, e só faz")
        print("  sentido depois de ver se as janelas se sobrepõem.")
    except Exception as e:                                   # noqa: BLE001
        print(f"  (não consultei o banco: {type(e).__name__})")

    if args.bruto:
        DESTINO_BRUTO.mkdir(parents=True, exist_ok=True)
        alvo = DESTINO_BRUTO / f"sonda-{datetime.now():%Y%m%d-%H%M}.json"
        alvo.write_text(json.dumps(bruto, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"\nJSON cru em {alvo}")
        print("Fora do repositório de propósito: é a carteira inteira.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
