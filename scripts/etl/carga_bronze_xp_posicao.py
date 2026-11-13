"""
Carga da camada Bronze — posição da carteira XP, via API da Pluggy.

O GRAO E (ativo, data de referencia). A API sempre devolve a posicao
de hoje; rodada todo dia, a tabela vira serie historica de carteira.
Rodar duas vezes no mesmo dia nao duplica - o hash cobre as duas
colunas e a carga so insere o que ainda nao existe.

A CARGA SE RECUSA A RODAR COM A CONEXAO DOENTE. Antes de ler qualquer
posicao ela confere o status do item. Isso importa mais do que parece:
o consentimento de Open Finance VENCE, e quando vence a API continua
respondendo - devolvendo lista vazia ou dado velho. Gravar isso como
"posicao do dia" criaria um buraco na serie que ninguem veria, porque
o grafico simplesmente mostraria a carteira encolhendo.

NAO SUBSTITUI O EXTRATO. A API alcanca 12 meses e entrega negociacao
por ativo; o extrato cobre desde 2021 e entrega fluxo de caixa da
conta. Sao fontes complementares - ver o cabecalho do
48_bronze_xp_posicao.sql.

Uso:
    python carga_bronze_xp_posicao.py
    python carga_bronze_xp_posicao.py --resumo
    python carga_bronze_xp_posicao.py --forcar   # ignora o status do item
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))

import os                                                    # noqa: E402

from config_db import get_engine                             # noqa: E402
from pluggy_api import Pluggy, PluggyErro                     # noqa: E402
from util_dados import registra_carga                        # noqa: E402

_INICIO = time.monotonic()

# Status em que o dado do item pode ser lido.
STATUS_CONFIAVEL = {"UPDATED"}

# Status PASSAGEIROS: a Pluggy esta sincronizando agora. A DAG roda tres
# vezes ao dia e a conexao atualiza uma; cair no meio de uma atualizacao
# e normal, nao defeito. Nesses casos a carga sai com 99, que o
# BashOperator do projeto trata como PULADA - alerta que toca sozinho
# todo dia deixa de ser lido, e aí o alerta de verdade some junto.
STATUS_PASSAGEIRO = {"UPDATING", "CREATING", "LOGIN_IN_PROGRESS"}

# Qualquer outro - WAITING_USER_INPUT, LOGIN_ERROR, OUTDATED - exige
# acao humana: consentimento vencido, reconexao. Esses falham de
# verdade, com codigo 1, porque ninguem vai agir sem ser avisado.
SAIDA_PULAR = 99

# De-para da API para a tabela, em UM lugar so. Cada entrada e
# (campo da API, coluna, conversor).
TEXTO = lambda v: None if v is None else str(v)[:300]          # noqa: E731
DATA = lambda v: None if not v else str(v)[:10]                # noqa: E731
NUM = lambda v: None if v is None else float(v)                # noqa: E731

CAMPOS = [
    ("id",                   "id_investimento",    TEXTO),
    ("itemId",               "id_item",            TEXTO),
    # A data que vem AQUI e a daquele ativo, nao a da foto - numa
    # mesma leitura vieram tres datas diferentes. A da foto entra
    # depois, de dt_snapshot, igual para todas as linhas.
    ("date",                 "dt_referencia",      DATA),
    ("name",                 "nm_ativo",           TEXTO),
    ("code",                 "cd_ativo",           TEXTO),
    ("isin",                 "cd_isin",            TEXTO),
    ("type",                 "ds_tipo",            TEXTO),
    ("subtype",              "ds_subtipo",         TEXTO),
    ("status",               "ds_situacao",        TEXTO),
    ("currencyCode",         "ds_moeda",           TEXTO),
    ("quantity",             "qt_cotas",           NUM),
    ("value",                "vl_cota",            NUM),
    ("amount",               "vl_bruto",           NUM),
    ("balance",              "vl_liquido",         NUM),
    ("amountWithdrawal",     "vl_resgatavel",      NUM),
    ("amountOriginal",       "vl_aplicado",        NUM),
    ("taxes",                "vl_taxas",           NUM),
    ("taxes2",               "vl_taxas2",          NUM),
    ("rate",                 "vl_taxa",            NUM),
    ("rateType",             "ds_tipo_taxa",       TEXTO),
    ("ratePeriodicity",      "ds_periodicidade",   TEXTO),
    ("fixedAnnualRate",      "vl_taxa_anual_fixa", NUM),
    ("lastTwelveMonthsRate", "vl_rentab_12m",      NUM),
    ("issuer",               "nm_emissor",         TEXTO),
    ("issuerCNPJ",           "cd_emissor_cnpj",    TEXTO),
    ("issueDate",            "dt_emissao",         DATA),
    ("purchaseDate",         "dt_compra",          DATA),
    ("dueDate",              "dt_vencimento",      DATA),
    ("gracePeriodDate",      "dt_carencia",        DATA),
]

COLUNAS = ([c for _, c, _ in CAMPOS]
           + ["dt_snapshot", "dt_consentimento_vence", "ds_payload",
              "hash_negocio"])


def confere_item(api: Pluggy, item_id: str, forcar: bool) -> dict:
    it = api.get(f"/items/{item_id}")
    st = it.get("status")
    con = (it.get("connector") or {}).get("name")
    print(f"  conexão {con} · {st}/{it.get('executionStatus')} · "
          f"atualizada {str(it.get('lastUpdatedAt'))[:10]}")
    if it.get("consentExpiresAt"):
        venc = str(it["consentExpiresAt"])[:10]
        faltam = (pd.Timestamp(venc) - pd.Timestamp.utcnow().tz_localize(None)).days
        marca = "  <-- RENOVAR" if faltam < 30 else ""
        print(f"  consentimento vence em {venc} ({faltam} dias){marca}")
    if st in STATUS_CONFIAVEL or forcar:
        return it
    if st in STATUS_PASSAGEIRO:
        print(f"\n  A Pluggy está sincronizando ('{st}'). Nada a fazer agora — "
              f"a próxima rodada pega.")
        raise SystemExit(SAIDA_PULAR)
    raise SystemExit(
        f"\nA conexão está em '{st}', e isso não se resolve sozinho.\n"
        f"Causas: consentimento vencido (vence em 12 meses e a API continua "
        f"respondendo), ou conexão que precisa ser refeita.\n"
        f"Reconecte em dashboard.pluggy.ai, ou use --forcar se souber o que "
        f"está fazendo.")


def monta(investimentos: list, dt_snapshot: str,
          dt_consentimento: str | None) -> pd.DataFrame:
    linhas = []
    for inv in investimentos:
        linha = {col: conv(inv.get(api_k)) for api_k, col, conv in CAMPOS}
        linha["dt_snapshot"] = dt_snapshot
        # A data vem do ITEM, nao do investimento: e atributo da
        # conexao. Guardada por foto para que renovar o consentimento
        # deixe rastro de QUANDO foi renovado.
        linha["dt_consentimento_vence"] = dt_consentimento
        # O payload inteiro: 43 campos hoje, dos quais 10 sempre nulos,
        # e outros que podem nascer quando a Pluggy mudar.
        linha["ds_payload"] = json.dumps(inv, ensure_ascii=False)
        # O hash usa dt_snapshot, e NAO dt_referencia: duas leituras no
        # mesmo dia tem de colidir, e a data de cada ativo nao serve
        # para isso - ela muda sozinha conforme a XP confirma preco.
        chave = f"{linha['id_investimento']}|{dt_snapshot}"
        linha["hash_negocio"] = hashlib.sha256(chave.encode()).hexdigest()
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=COLUNAS)


def resumo(engine) -> None:
    print("\n== Carteira por tipo, na última data ==")
    print(pd.read_sql("""
        WITH ult AS (SELECT MAX(dt_snapshot) d FROM bronze.xp_posicao)
        SELECT p.ds_tipo, p.ds_subtipo, COUNT(*) ativos,
               CAST(SUM(p.vl_liquido) AS decimal(14,2)) liquido
        FROM bronze.xp_posicao p, ult
        WHERE p.dt_snapshot = ult.d AND p.ds_situacao = 'ACTIVE'
        GROUP BY p.ds_tipo, p.ds_subtipo
        ORDER BY 4 DESC""", engine).to_string(index=False))
    print("\n== Série de patrimônio ==")
    print(pd.read_sql("""
        SELECT dt_snapshot,
               SUM(CASE WHEN ds_situacao = 'ACTIVE' THEN 1 ELSE 0 END) ativos,
               SUM(CASE WHEN ds_situacao <> 'ACTIVE' THEN 1 ELSE 0 END) encerrados,
               CAST(SUM(vl_liquido) AS decimal(14,2)) patrimonio
        FROM bronze.xp_posicao GROUP BY dt_snapshot
        ORDER BY 1 DESC""", engine).to_string(index=False))


def main() -> int:
    p = argparse.ArgumentParser(description="Carga bronze da posição XP")
    p.add_argument("--resumo", action="store_true")
    p.add_argument("--forcar", action="store_true",
                   help="carrega mesmo com a conexão fora de UPDATED")
    args = p.parse_args()

    item_id = os.getenv("PLUGGY_ITEM_ID")
    if not item_id:
        print("ERRO: falta PLUGGY_ITEM_ID no .env.")
        return 1

    try:
        api = Pluggy()
        item = confere_item(api, item_id, args.forcar)
        investimentos = list(api.paginado("/investments", itemId=item_id))
    except PluggyErro as e:
        print(f"ERRO: {e}")
        return 1

    if not investimentos:
        print("A API não devolveu nenhum investimento. Nada foi gravado.")
        return 1

    # A data da FOTO vem do item, não do relógio nem do campo date de
    # cada investimento: é quando a Pluggy atualizou a conexão, e
    # portanto a idade real deste conjunto de posições.
    snap = str(item.get("lastUpdatedAt") or pd.Timestamp.utcnow())[:10]
    vence = (str(item["consentExpiresAt"])[:10]
             if item.get("consentExpiresAt") else None)
    fato = monta(investimentos, snap, vence)
    vivos = fato[fato.ds_situacao == "ACTIVE"]
    print(f"\n  {len(fato)} posições · foto de {snap}")
    print(f"     {len(vivos):>2} ativas      líquido {vivos.vl_liquido.sum():,.2f}")
    print(f"     {len(fato) - len(vivos):>2} encerradas  (TOTAL_WITHDRAWAL, saldo zero)")

    engine = get_engine()
    with engine.begin() as conn:
        ja = pd.read_sql("SELECT hash_negocio FROM bronze.xp_posicao", conn)
        novos = fato[~fato.hash_negocio.isin(set(ja.hash_negocio))]
        if len(novos):
            novos.to_sql("xp_posicao", conn, schema="bronze",
                         if_exists="append", index=False)

        # A DATA DO CONSENTIMENTO E ATUALIZADA, nao so inserida. Ela e
        # metadado da CONEXAO, nao da posicao: renovar o consentimento
        # muda a data, e uma carga que so insere nunca a corrigiria - o
        # vigia seguiria avisando de um vencimento que ja foi resolvido.
        # Atualiza so a foto corrente, para as anteriores guardarem o
        # que valia na epoca delas.
        if vence:
            conn.execute(text(
                "UPDATE bronze.xp_posicao SET dt_consentimento_vence = :v "
                "WHERE dt_snapshot = :d "
                "  AND (dt_consentimento_vence IS NULL "
                "       OR dt_consentimento_vence <> :v)"),
                {"v": vence, "d": snap})

    print(f"  bronze.xp_posicao: +{len(novos)} novas, "
          f"{len(fato) - len(novos)} já existiam")
    registra_carga(engine, "bronze.xp_posicao", len(novos), 0, inicio=_INICIO)

    if args.resumo:
        resumo(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
