"""
Calcula, em SQL, o alvo de cada medida da aba Financas Geral.

POR QUE EXISTE. A primeira versao da documentacao trazia os numeros
digitados numa tabela. Oito dias depois estavam errados - nao por erro
de conta, mas porque chegou extrato novo: o Itau avancou de 18/09 para
28/09 e o cartao ate 04/10. Numero digitado em documentacao de base
viva envelhece calado, e conferir medida contra alvo errado e pior do
que nao conferir.

Entao o alvo se recalcula. A saida segue a ordem dos blocos do esboco,
para dar para comparar olhando de um lado para o outro.

A JANELA PADRAO E UM MES - o ultimo FECHADO, porque o corrente ainda
esta enchendo e puxaria toda media para baixo. E a mesma visao que a
aba abre.

Cada bloco espelha as medidas do financas-geral.md com os MESMOS tres
filtros: nivel ANALITICO, classe diferente de 'Nao e gasto', e nulo
virando 'A classificar'.

Uso:
    python conferir-financas-geral.py            # ultimo mes fechado
    python conferir-financas-geral.py 2026-09    # um mes especifico
    python conferir-financas-geral.py --12m      # os 12 meses fechados
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))

from config_db import get_engine  # noqa: E402

# ISNULL reproduz a coluna calculada DS_CLASSE do modelo: sem ele, grupo
# nao classificado sumiria da conta em vez de aparecer.
CORPO = """
FROM gold.fato_movto_financ f
JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
JOIN gold.dim_origem o ON o.SK_ORIGEM = f.SK_ORIGEM
LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
LEFT JOIN gold.dim_categoria_financ k
       ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
WHERE f.DS_NIVEL = 'ANALITICO'
  AND ISNULL(g.DS_COMPRESSIBILIDADE, 'A classificar') <> 'Nao e gasto'
  AND c.NM_ANO_MES >= '{ini}' AND c.NM_ANO_MES <= '{fim}'
"""

REC = "SUM(CASE WHEN f.DS_TIPO_FLUXO = 'RECEITA' THEN f.VL_TRANSACAO ELSE 0 END)"
DES = "SUM(CASE WHEN f.DS_TIPO_FLUXO = 'DESPESA' THEN -f.VL_TRANSACAO ELSE 0 END)"

LIMITE_PICO = 1000        # a medida [Limite de pico]


def brl(v) -> str:
    return ("R$ " + f"{float(v):,.2f}").replace(",", "~").replace(".", ",").replace("~", ".")


def pc(v) -> str:
    return f"{float(v) * 100:.1f}%".replace(".", ",")


def mes_do_indice(i: int) -> str:
    ano, mes = divmod(i - 1, 12)
    return f"{ano:04d}-{mes + 1:02d}"


def um(eng, sql) -> float:
    v = pd.read_sql(sql, eng).iloc[0, 0]
    return 0.0 if v is None else float(v)


def main() -> int:
    eng = get_engine()
    args = [a for a in sys.argv[1:]]
    doze = "--12m" in args
    alvo = next((a for a in args if not a.startswith("--")), None)

    if alvo is None:
        ult = pd.read_sql("""
            SELECT MAX(c.NM_ANO_MES) m
            FROM gold.fato_movto_financ f
            JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
            WHERE f.DS_NIVEL = 'ANALITICO'""", eng).m.iloc[0]
        alvo = mes_do_indice(int(ult[:4]) * 12 + int(ult[5:]) - 1)

    idx = int(alvo[:4]) * 12 + int(alvo[5:])
    ini = mes_do_indice(idx - 11) if doze else alvo
    corpo = CORPO.format(ini=ini, fim=alvo)
    janela = f"{ini} a {alvo}" if doze else alvo

    print(f"=== PERÍODO: {janela} ===")
    print("    (recalculado agora; o mês corrente fica de fora de propósito)\n")

    r = um(eng, f"SELECT {REC} {corpo}")
    d = um(eng, f"SELECT {DES} {corpo}")
    sal = um(eng, f"SELECT {REC} {corpo} AND g.NM_GRUPO = 'Salário'")
    saldo, saldo_sal = r - d, sal - d

    print("1. CARTÕES DO TOPO")
    print(f"   Receita total            {brl(r):>16}")
    print(f"   Despesa total            {brl(d):>16}   {pc(d / r):>7} da receita")
    print(f"   Saldo total              {brl(saldo):>16}   {pc(saldo / r):>7} margem líquida")
    print(f"   Saldo (apenas salário)   {brl(saldo_sal):>16}   {pc(saldo_sal / sal):>7} salário limpo")

    ess = um(eng, f"SELECT {DES} {corpo} AND g.DS_COMPRESSIBILIDADE = 'Essencial'")
    comp = um(eng, f"SELECT {DES} {corpo} AND g.DS_COMPRESSIBILIDADE = 'Compressivel'")

    print("\n2. COMPOSIÇÃO DE ENTRADAS E SAÍDAS")
    print(f"   Receita · Receita Salário       {brl(sal):>16}")
    print(f"   Receita · Outras Receitas       {brl(r - sal):>16}")
    print(f"   Despesa · Despesas Essenciais   {brl(ess):>16}")
    print(f"   Despesa · Despesas Outras       {brl(d - ess):>16}")
    print(f"   -> entradas {brl(sal + (r - sal))} = receita {brl(r)}   "
          f"saídas {brl(ess + (d - ess))} = despesa {brl(d)}")

    print("\n3. INDICADORES PERCENTUAIS")
    print(f"   % Salário / Receita Total                  {pc(sal / r):>8}")
    print(f"   % Despesas Outras / Despesa Total          {pc((d - ess) / d):>8}")
    print(f"   % Saldo (apenas Salário) / Receita Total   {pc(saldo_sal / r):>8}")
    print(f"      (contra {pc(saldo_sal / sal)} do cartão 4, que divide pelo próprio salário)")

    cart = um(eng, f"SELECT {DES} {corpo} AND o.DS_TIPO_CONTA = 'Cartão de crédito'")
    print("\n4. CARTÃO DE CRÉDITO x OUTROS GASTOS")
    print(f"   Cartão de crédito        {brl(cart):>16}   {pc(cart / d):>7}")
    print(f"   Fora do cartão           {brl(d - cart):>16}   {pc((d - cart) / d):>7}")
    tc = pd.read_sql(f"""SELECT o.DS_TIPO_CONTA t, {DES} v {corpo}
        AND f.DS_TIPO_FLUXO='DESPESA' GROUP BY o.DS_TIPO_CONTA ORDER BY 2 DESC""", eng)
    print("   abertura do 'fora do cartão':")
    for x in tc.itertuples():
        if x.t != "Cartão de crédito":
            print(f"      {x.t:<24} {brl(x.v):>14}")

    print("\n5. TOP 5 CATEGORIAS")
    cat = pd.read_sql(f"""SELECT TOP 5 ISNULL(k.NM_CATEGORIA,'(sem categoria)') c, {DES} v
        {corpo} AND f.DS_TIPO_FLUXO='DESPESA'
        GROUP BY k.NM_CATEGORIA HAVING {DES} > 0 ORDER BY 2 DESC""", eng)
    for i, x in enumerate(cat.itertuples(), 1):
        print(f"   {i}. {x.c:<22} {brl(x.v):>14}   {pc(float(x.v) / d):>7}")
    print(f"   demais categorias          {brl(d - float(cat.v.sum())):>14}")

    print("\n6. GASTO POR DIA")
    dias_mes = um(eng, f"""SELECT COUNT(*) FROM gold.dim_calendario c
        WHERE c.NM_ANO_MES >= '{ini}' AND c.NM_ANO_MES <= '{alvo}'""")
    dias_gasto = um(eng, f"SELECT COUNT(DISTINCT f.SK_DATA) {corpo} AND f.DS_TIPO_FLUXO='DESPESA'")
    print(f"   Gasto médio do dia no mês {brl(d / dias_mes):>15}   ({int(dias_mes)} dias corridos)")
    print(f"   Gasto médio por dia com gasto {brl(d / dias_gasto):>11}   ({int(dias_gasto)} dias)")
    cores = pd.read_sql(f"""
        SELECT CASE WHEN v > {LIMITE_PICO} THEN 'pico (> R$ 1.000)'
                    WHEN fer = 'S' THEN 'feriado'
                    WHEN fds = 'S' THEN 'fim de semana'
                    ELSE 'diário comum' END faixa,
               COUNT(*) dias, SUM(v) total
        FROM (SELECT c.DT_DATA, MAX(c.FL_FERIADO) fer, MAX(c.FL_FIM_SEMANA) fds, {DES} v
              {corpo} AND f.DS_TIPO_FLUXO='DESPESA' GROUP BY c.DT_DATA) x
        GROUP BY CASE WHEN v > {LIMITE_PICO} THEN 'pico (> R$ 1.000)'
                      WHEN fer = 'S' THEN 'feriado'
                      WHEN fds = 'S' THEN 'fim de semana'
                      ELSE 'diário comum' END
        ORDER BY 3 DESC""", eng)
    print("   as faixas de cor do calendário:")
    for x in cores.itertuples():
        print(f"      {x.faixa:<20} {int(x.dias):>3} dias   {brl(x.total):>14}   "
              f"média {brl(float(x.total) / x.dias)}")

    print("\n7. O QUE PODE SER CORTADO")
    print(f"   Despesa compressível     {brl(comp):>16}   {pc(comp / d):>7} da despesa")
    top3 = pd.read_sql(f"""SELECT TOP 3 g.NM_GRUPO n, {DES} v
        {corpo} AND f.DS_TIPO_FLUXO='DESPESA' AND g.DS_COMPRESSIBILIDADE='Compressivel'
        GROUP BY g.NM_GRUPO ORDER BY 2 DESC""", eng)
    for i, x in enumerate(top3.itertuples(), 1):
        print(f"   {i}. {x.n:<22} {brl(x.v):>14}")
    meta = float(top3.v.sum())
    print(f"   Meta pelos 3 maiores     {brl(meta):>16}")
    print(f"      {pc(meta / d)} da despesa  ·  {pc(meta / r)} da receita")
    print(f"   Saldo com o corte        {brl(saldo + meta):>16}   "
          f"margem {pc((saldo + meta) / r)}")
    print(f"   Economia anualizada      {brl(meta * 12):>16}")

    inflado = um(eng, f"""SELECT {DES}
        FROM gold.fato_movto_financ f
        JOIN gold.dim_calendario c ON c.SK_DATA = f.SK_DATA
        LEFT JOIN gold.dim_grupo_financ g ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
        WHERE ISNULL(g.DS_COMPRESSIBILIDADE,'A classificar') <> 'Nao e gasto'
          AND c.NM_ANO_MES >= '{ini}' AND c.NM_ANO_MES <= '{alvo}'""")
    print(f"\nO QUE O FILTRO DS_NIVEL EVITA")
    print(f"   sem ele {brl(inflado)} contra {brl(d)} com ele  ->  "
          f"{brl(inflado - d)} de fatura contada em dobro")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
