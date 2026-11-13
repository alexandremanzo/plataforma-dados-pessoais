"""
Calcula, em SQL, o que cada elemento da tela TEM de mostrar.

POR QUE EM SQL E NAO EM DAX. O DAX so roda dentro do Power BI, e la ele
e ao mesmo tempo o que se quer conferir e a unica forma de conferir —
um numero errado concorda consigo mesmo. Refazendo a conta por outro
caminho, a partir da mesma base, uma divergencia aponta erro de verdade.

Cada bloco abaixo reproduz uma medida do painel, com a MESMA exclusao:
nivel ANALITICO e grupo cuja classe nao seja "Nao e gasto" (aporte,
resgate e transferencia nao sao receita nem gasto).

Uso:
    python conferir_numeros.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# O console do Windows e cp1252 e nao sabe escrever ▲ nem ★ — os mesmos
# simbolos que o painel mostra. Sem isto, conferir o numero quebra por
# causa do enfeite.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))

from config_db import get_engine  # noqa: E402

import gerar_painel as g  # noqa: E402

# O corpo comum a quase toda consulta: o fato analitico com as
# dimensoes, ja fora o que nao e receita nem gasto.
BASE_SQL = """
FROM gold.fato_movto_financ f
JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
JOIN gold.dim_origem o ON o.SK_ORIGEM = f.SK_ORIGEM
LEFT JOIN gold.dim_grupo_financ gr ON gr.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
LEFT JOIN gold.dim_categoria_financ cat
       ON cat.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
WHERE f.DS_NIVEL = 'ANALITICO'
  AND ISNULL(gr.DS_COMPRESSIBILIDADE, 'A classificar') <> 'Nao e gasto'
"""

REC = "SUM(CASE WHEN f.DS_TIPO_FLUXO = 'RECEITA' THEN f.VL_TRANSACAO ELSE 0 END)"
DES = "SUM(CASE WHEN f.DS_TIPO_FLUXO = 'DESPESA' THEN -f.VL_TRANSACAO ELSE 0 END)"


def brl(v) -> str:
    if pd.isna(v):
        return "—"
    return ("R$ " + f"{v:,.2f}").replace(",", "~").replace(".", ",").replace("~", ".")


def pct(v) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.1f}%".replace(".", ",")


def mes_do_indice(i: int) -> str:
    """Indice (ano*12 + mes) -> 'AAAA-MM'. O mesmo que o DAX faz.

    Escrito uma vez porque a conta tem uma armadilha: dezembro e o mes
    12, e divmod devolve resto 0 para ele — por isso o -1 antes e o +1
    depois.
    """
    ano, mes = divmod(i - 1, 12)
    return f"{ano:04d}-{mes + 1:02d}"


def main() -> int:
    eng = get_engine()

    # --- mes de referencia: o ultimo com lancamento -------------------
    mes = pd.read_sql(
        f"SELECT MAX(c.NM_ANO_MES) m {BASE_SQL}", eng).m.iloc[0]
    idx = int(mes[:4]) * 12 + int(mes[5:])
    ant = mes_do_indice(idx - 1)

    print(f"=== MÊS DE REFERÊNCIA: {mes}   (anterior: {ant}) ===\n")

    # --- dados completos ate ------------------------------------------
    completo = pd.read_sql(f"""
        SELECT o.NM_ORIGEM, MAX(c.DT_DATA) ultimo, COUNT(*) lanc
        {BASE_SQL} AND c.NM_ANO_MES = '{mes}'
        GROUP BY o.NM_ORIGEM ORDER BY ultimo""", eng)
    print("Origens que movimentaram no mês:")
    for _, r in completo.iterrows():
        print(f"   {r.NM_ORIGEM:<24} até {r.ultimo}   {r.lanc} lançamentos")
    print(f"   -> 'Dados completos até' = {completo.ultimo.min()}  "
          f"(a origem mais atrasada)\n")

    # --- os quatro cartoes do topo ------------------------------------
    kpi = pd.read_sql(f"""
        SELECT c.NM_ANO_MES mes, {REC} receita, {DES} despesa,
               SUM(CASE WHEN f.DS_TIPO_FLUXO = 'DESPESA'
                         AND o.DS_TIPO_CONTA = 'Cartão de crédito'
                        THEN -f.VL_TRANSACAO ELSE 0 END) cartao
        {BASE_SQL} AND c.NM_ANO_MES IN ('{mes}', '{ant}')
        GROUP BY c.NM_ANO_MES""", eng).set_index("mes").astype(float)

    r, d, ca = kpi.loc[mes, ["receita", "despesa", "cartao"]]
    ra, da, caa = kpi.loc[ant, ["receita", "despesa", "cartao"]]
    saldo = r - d

    def var(agora, antes):
        v = (agora - antes) / antes if antes else float("nan")
        seta = "▲ +" if v >= 0 else "▼ −"
        return f"{seta}{abs(v) * 100:.1f}%".replace(".", ",") + " vs mês ant."

    print("CARTÕES DO TOPO")
    print(f"   Receita total      {brl(r):>16}   {var(r, ra)}")
    print(f"   Despesa total      {brl(d):>16}   {var(d, da)}")
    print(f"   Cartão de crédito  {brl(ca):>16}   {var(ca, caa)} · "
          f"{pct(ca / d)} da despesa")
    print(f"   Saldo / economia   {brl(saldo):>16}   "
          f"{'★' if saldo >= 0 else '▼'} {pct(saldo / r)} taxa de poupança\n")

    # --- historico de doze meses --------------------------------------
    # A janela do DAX e _i > _fim - 12 e _i <= _fim: DOZE meses contando
    # o de referencia, logo o primeiro e o indice - 11.
    ini = mes_do_indice(idx - 11)
    hist = pd.read_sql(f"""
        SELECT c.NM_ANO_MES mes, {REC} receita, {DES} despesa,
               SUM(CASE WHEN f.DS_TIPO_FLUXO = 'RECEITA'
                         AND gr.NM_GRUPO IN ({','.join(
                             chr(39) + x.replace(chr(39), chr(39) * 2) + chr(39)
                             for x in g.GRUPOS_RECORRENTES)})
                        THEN f.VL_TRANSACAO ELSE 0 END) recorrente
        {BASE_SQL} AND c.NM_ANO_MES >= '{ini}' AND c.NM_ANO_MES <= '{mes}'
        GROUP BY c.NM_ANO_MES ORDER BY 1""", eng)
    print(f"HISTÓRICO — {len(hist)} meses no eixo (esperado: 12)")
    for _, x in hist.iterrows():
        marca = "  <-- negativo" if x.receita - x.despesa < 0 else ""
        print(f"   {x.mes}  receita {brl(x.receita):>15}   "
              f"despesa {brl(x.despesa):>15}   só salário "
              f"{brl(x.recorrente):>14}{marca}")
    neg = int((hist.receita - hist.despesa < 0).sum())
    negr = int((hist.recorrente - hist.despesa < 0).sum())
    print(f"   -> {neg} de {len(hist)} meses no vermelho pela receita total; "
          f"{negr} de {len(hist)} contando só o salário\n")

    # --- top 5 de categorias -------------------------------------------
    top = pd.read_sql(f"""
        SELECT TOP 5 ISNULL(cat.NM_CATEGORIA, '(sem categoria)') categoria,
               {DES} valor
        {BASE_SQL} AND c.NM_ANO_MES = '{mes}'
        GROUP BY cat.NM_CATEGORIA
        HAVING {DES} > 0 ORDER BY 2 DESC""", eng)
    print("TOP 5 CATEGORIAS")
    for i, x in enumerate(top.itertuples(), 1):
        print(f"   {i}. {x.categoria:<24} {brl(float(x.valor)):>15}   "
              f"{pct(float(x.valor) / d)}")
    print()

    # --- gastos nao essenciais -----------------------------------------
    ne = pd.read_sql(f"""
        SELECT {DES} valor, COUNT(*) lanc
        {BASE_SQL} AND c.NM_ANO_MES = '{mes}'
          AND gr.DS_COMPRESSIBILIDADE = 'Compressivel'""", eng)
    ne_v, ne_n = float(ne.valor.iloc[0]), int(ne.lanc.iloc[0])
    pot = ne_v * g.CORTE_ALVO
    novo = saldo + pot

    print("GASTOS NÃO ESSENCIAIS")
    print(f"   Total no mês          {brl(ne_v):>16}   "
          f"{pct(ne_v / d)} da despesa · {ne_n} lançamentos")
    print(f"   Potencial de economia {brl(pot):>16}   "
          f"cortando {g.CORTE_ALVO:.0%} do não essencial")
    print(f"   Impacto: o saldo vai de {brl(saldo)} para {brl(novo)}, "
          f"e a poupança de {pct(saldo / r)} para {pct(novo / r)}.\n")

    grupos = pd.read_sql(f"""
        SELECT TOP 8 gr.NM_GRUPO grupo, {DES} valor
        {BASE_SQL} AND c.NM_ANO_MES = '{mes}'
          AND gr.DS_COMPRESSIBILIDADE = 'Compressivel'
        GROUP BY gr.NM_GRUPO HAVING {DES} > 0 ORDER BY 2 DESC""", eng)
    print("   Maiores grupos não essenciais do mês:")
    for x in grupos.itertuples():
        print(f"      {x.grupo:<24} {brl(float(x.valor)):>14}")

    # --- a lacuna que precisa continuar visivel ------------------------
    classif = pd.read_sql(f"""
        SELECT ISNULL(gr.DS_COMPRESSIBILIDADE, 'A classificar') classe,
               {DES} valor, COUNT(*) lanc
        {BASE_SQL} AND c.NM_ANO_MES = '{mes}' AND f.DS_TIPO_FLUXO = 'DESPESA'
        GROUP BY gr.DS_COMPRESSIBILIDADE ORDER BY 2 DESC""", eng)
    print("\nDESPESA POR CLASSE (a 'A classificar' tem de aparecer, não sumir)")
    for x in classif.itertuples():
        print(f"   {x.classe:<16} {brl(float(x.valor)):>14}   "
              f"{pct(float(x.valor) / d):>7}   {x.lanc} lançamentos")

    soma = float(classif.valor.sum())
    print(f"\n   soma das classes {brl(soma)} × despesa total {brl(d)}   "
          f"{'confere' if abs(soma - d) < 0.01 else 'DIVERGE'}")
    return 0 if abs(soma - d) < 0.01 else 1


if __name__ == "__main__":
    raise SystemExit(main())
