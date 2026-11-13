"""
Calcula, direto do banco, o que cada indicador do painel deve mostrar.

Existe para separar dois defeitos que se parecem na tela: "a medida esta
errada" e "o dado e assim mesmo". Rodando isto antes de abrir o Power BI,
cada cartao passa a ter um alvo — e numero diferente do alvo vira
defeito, em vez de virar duvida.

Replica a mesma logica do DAX gerado por gerar_painel.py: mesmo ciclo de
fatura, mesma exclusao de SINTETICO, mesma classificacao.

Uso:
    python conferir_numeros.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_db import get_engine  # noqa: E402
from gerar_painel import DIAS_ANTES_FECHAMENTO, META_PADRAO  # noqa: E402

SQL_BASE = """
SELECT  c.DT_DATA          AS dt_compra,
        cf.DT_DATA         AS dt_fatura,
        o.NM_ORIGEM        AS origem,
        o.DS_TIPO_CONTA    AS tipo_conta,
        ISNULL(gr.DS_COMPRESSIBILIDADE, 'A classificar') AS classe,
        gr.NM_GRUPO        AS grupo,
        ct.NM_CATEGORIA    AS categoria,
        f.NR_PARCELA       AS parcela,
        CASE WHEN f.DS_TIPO_FLUXO = 'DESPESA'
             THEN -f.VL_TRANSACAO ELSE 0 END AS gasto
FROM gold.fato_movto_financ f
JOIN gold.dim_calendario  c  ON c.SK_DATA = f.SK_DATA
LEFT JOIN gold.dim_calendario cf ON cf.SK_DATA = f.SK_DATA_FATURA
JOIN gold.dim_origem      o  ON o.SK_ORIGEM = f.SK_ORIGEM
LEFT JOIN gold.dim_grupo_financ     gr ON gr.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
LEFT JOIN gold.dim_categoria_financ ct ON ct.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
WHERE f.DS_NIVEL = 'ANALITICO'
"""


def brl(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"R$ {v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def main() -> int:
    d = pd.read_sql(SQL_BASE, get_engine())
    d["dt_compra"] = pd.to_datetime(d["dt_compra"]).dt.date
    d["dt_fatura"] = pd.to_datetime(d["dt_fatura"]).dt.date
    hoje = date.today()

    cartao = d[d["tipo_conta"] == "Cartão de crédito"]
    consumo = d[d["classe"] != "Nao e gasto"]

    # --- o ciclo -------------------------------------------------------
    futuras = sorted({f for f in cartao["dt_fatura"].dropna() if f >= hoje})
    if not futuras:
        print("Nenhuma fatura futura: nao ha ciclo em aberto para medir.")
        return 1
    corrente = futuras[0]
    fechamento = corrente - timedelta(days=DIAS_ANTES_FECHAMENTO)
    abertura = fechamento - timedelta(days=30)
    dias_ate = max(0, (fechamento - hoje).days)
    dias_corridos = max(1, (hoje - abertura).days)

    na_fatura = cartao[cartao["dt_fatura"] == corrente]
    aberto = na_fatura["gasto"].sum()
    comprometido = na_fatura[na_fatura["parcela"].notna()]["gasto"].sum()
    falta = META_PADRAO - aberto
    # O ritmo se mede so sobre a compra a vista: a parcela ja entrou
    # inteira na fatura e projeta-la adiante cobraria a mesma compra
    # todo dia ate o fechamento.
    ritmo = (aberto - comprometido) / dias_corridos
    projecao = aberto + ritmo * dias_ate

    if aberto > META_PADRAO:
        situacao = "Estourada"
    elif projecao > META_PADRAO:
        situacao = "Vai estourar"
    elif projecao > META_PADRAO * 0.85:
        situacao = "No limite"
    else:
        situacao = "Dentro da meta"

    print("=" * 66)
    print(f"O QUE O PAINEL DEVE MOSTRAR  ·  hoje {hoje.strftime('%d/%m/%Y')}")
    print("=" * 66)
    print()
    print("-- Pagina 1: Controle do mes --")
    print(f"  Situacao do ciclo .......... {situacao}")
    print(f"  Consumido da meta .......... {aberto / META_PADRAO:.0%}")
    print(f"  Fatura em aberto ........... {brl(aberto)}   (vence {corrente:%d/%m/%Y})")
    print(f"  Falta para a meta .......... {brl(falta)}")
    print(f"  Dias ate fechar ............ {dias_ate}   (fecha {fechamento:%d/%m/%Y})")
    print(f"  Pode gastar por dia ........ {brl(max(0, falta) / dias_ate if dias_ate else 0)}")
    print(f"  Projecao de fechamento ..... {brl(projecao)}")
    print()
    print(f"  Comprometido (parcelas) .... {brl(comprometido)}")
    print(f"  A vista no ciclo ........... {brl(aberto - comprometido)}")
    print()
    print("  Natureza do que ja entrou:")
    for cl, v in na_fatura.groupby("classe")["gasto"].sum().sort_values(
            ascending=False).items():
        print(f"    {cl:<16} {brl(v)}")

    # --- faturas futuras ----------------------------------------------
    print()
    print("  Ja comprometido nas proximas faturas:")
    frente = (cartao[cartao["dt_fatura"] > corrente]
              .groupby("dt_fatura")["gasto"].sum())
    for f, v in frente.items():
        print(f"    {f:%m/%Y}  {brl(v):>14}   sobra {brl(META_PADRAO - v)}")

    # --- pagina 2 ------------------------------------------------------
    fechadas = (cartao[(cartao["dt_fatura"] < corrente) & cartao["dt_fatura"].notna()]
                .groupby("dt_fatura")["gasto"].sum())
    ult12 = fechadas.tail(12)
    print()
    print("-- Pagina 2: Historico (12 faturas fechadas) --")
    print(f"  Media ...................... {brl(ult12.mean())}")
    print(f"  Mediana .................... {brl(ult12.median())}")
    print(f"  Acima da meta .............. {(ult12 > META_PADRAO).sum()} de {len(ult12)}")
    print(f"  Excesso sobre a meta ....... {brl((ult12 - META_PADRAO).clip(lower=0).sum())}")
    print(f"  Maior fatura ............... {brl(ult12.max())}")

    # --- pagina 3 ------------------------------------------------------
    fim = date(hoje.year, hoje.month, 1) - timedelta(days=1)
    ini = (fim.replace(day=1) - timedelta(days=365)).replace(day=1)
    janela = consumo[(consumo["dt_compra"] >= ini) & (consumo["dt_compra"] <= fim)]
    por_classe = janela.groupby("classe")["gasto"].sum() / 12
    total_mes = janela["gasto"].sum() / 12

    print()
    print(f"-- Pagina 3: Onde da para cortar ({ini:%m/%Y} a {fim:%m/%Y}) --")
    print(f"  Consumo por mes ............ {brl(total_mes)}")
    for cl in ("Compressivel", "Eventual", "Essencial", "A classificar"):
        v = por_classe.get(cl, 0)
        print(f"  {cl + ' por mes':<26} {brl(v)}   {v / total_mes:.0%}" if total_mes
              else f"  {cl}: {brl(v)}")
    comp = por_classe.get("Compressivel", 0)
    print(f"  Economia se cortar 30% ..... {brl(comp * 0.30)}")
    print(f"  Fundo de eventuais ......... {brl(por_classe.get('Eventual', 0))}")

    print()
    print("  Maiores grupos compressiveis:")
    top = (janela[janela["classe"] == "Compressivel"]
           .groupby("grupo")
           .agg(total=("gasto", "sum"), lanc=("gasto", "size"))
           .sort_values("total", ascending=False).head(10))
    for gr, r in top.iterrows():
        print(f"    {str(gr)[:22]:<24} {brl(r['total']):>14}"
              f"   {brl(r['total'] / 12)}/mes   {int(r['lanc'])} lanc")

    print()
    print("Compare estes numeros com a tela depois de abrir o .pbip.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
