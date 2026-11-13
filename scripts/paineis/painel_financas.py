"""
Painel de financas pessoais, em HTML offline.

Le gold.fato_movto_financ (so SELECT, nivel ANALITICO) desde 2024,
classifica cada lancamento e embute a lista no template; o HTML
recalcula receita, despesa, saldo, categorias e o calendario para o
periodo escolhido.

As regras de classificacao, combinadas com o dono dos dados:

  PATRIMONIO fica fora de receita e despesa. Aporte, resgate,
  previdencia, cofrinho e transferencia entre contas proprias sao
  dinheiro mudando de bolso. Aparecem numa faixa propria.

  RECEITA em tres faixas: salario (grupo Salario), extraordinaria
  (PLR, acerto, FGTS, seguro-desemprego, saque, venda de bem) e outras.

  DESPESA pela compressibilidade do grupo: Essencial, Eventual,
  Compressivel (o que da para cortar). Grupo sem compressibilidade
  herda da area: GASTOS ESSENCIAIS vira Essencial; o resto vira
  "Sem classificacao".

  REEMBOLSO que cai em area de despesa (amigo devolvendo a parte da
  hospedagem, por exemplo) abate o gasto da propria categoria, em vez
  de inflar a receita.

  COMPRA DE BEM (carro, apartamento) e despesa, mas vem marcada: o
  HTML tem uma chave para tira-la e ver o padrao do dia a dia.

  ONDE GASTO sai de DS_PESSOA_RECEBER, normalizado (sem acento, caixa e
  pontuacao) e com as variantes de digitacao unidas a mao (ALIAS). O
  proprio Ale, a Conta Familia e nomes genericos ("Loja", "Pessoa")
  ficam fora do ranking.

  ROTINA x GASTO cruza o gasto variavel do dia com gold.fato_dia
  (trabalho, Nina em casa) e com o calendario (fim de semana, feriado).
  Contas fixas, viagem e compra de bem ficam fora, porque caem num dia
  por calendario e nao por rotina. O registro diario comeca em 2024 e
  tem buracos entre jan e abr/2024: dia sem registro nao entra nas
  comparacoes de trabalho e Nina.

Saida site/painel-financas.html, publicada no GitHub Pages.

Uso:
    python scripts/paineis/painel_financas.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config_db import get_engine  # noqa: E402

TEMPLATE = Path(__file__).with_name("painel_financas.html")
SAIDA = RAIZ / "site" / "painel-financas.html"

INICIO = 20240101          # antes disso as origens eram outras (Nubank, Visa...)

AREAS_PATRIMONIO = {"TRANSFERENCIA", "INVESTIMENTO"}
CATS_PATRIMONIO = {"INVESTIMENTO", "TRANSFERENCIA"}
GRUPOS_PATRIMONIO = {"Cofrinho", "Previdencia", "Resgate", "Investimento", "Mesada"}
GRUPOS_EXTRA = {"PLR", "Acerto", "FGTS", "Seguro Desemprego", "Saque Aniversário"}
AREAS_EXTRA = {"VENDA"}
AREAS_DESPESA = {"ESTILO DE VIDA", "GASTOS ESSENCIAIS"}
GRUPOS_BEM = {"Compra Carro", "Compra Apto"}

CLASSE_DESPESA = {"Essencial": "essencial", "Eventual": "eventual", "Compressivel": "cortavel"}

# recebedor: variantes de digitacao -> chave canonica (ja sem acento e em minusculas)
ALIAS = {"padaria central ltda": "padaria central", "posto avenida 2": "posto avenida", "99pop": "99",
         "self service bom gosto": "self-service bom gosto"}
# o proprio dono, contas proprias e nomes genericos nao sao "lugar"
FORA_RANKING = {"ale", "alexandre manzo", "conta familia", "pessoa", "empresa", "empresa0", "loja",
                "deposito", "itau", "cofrinho itau", "nao informado"}

# rotina: grupos que caem num dia por calendario (contas, mensalidades, viagem), nao por rotina
GRUPOS_FIXOS = {"Conta Familia", "Plano Saude", "Escola", "Rematricula", "Material Escolar", "IPVA", "SEGURO",
                "Seguro Carro", "Internet", "Telefonia", "Streaming", "Academia", "Plano Saude", "Licenciamento",
                "Armazenamento dados", "Netflix", "Spotfy", "Hospedagem", "Viagem", "Avião"}
GRUPOS_MERCADO = {"Mercado", "Compras", "Sacolão", "Hortifrut", "Leite", "Frutas", "Fruta", "Ovos", "Padaria", "Pao", "Água"}
ROTINA = ["Outros variáveis", "Comer fora", "Mercado", "Uber e 99", "Lazer"]


def chave_rec(s) -> str | None:
    if not isinstance(s, str) or not s.strip():
        return None
    k = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    k = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", k)).strip()
    k = ALIAS.get(k, k)
    return None if not k or k in FORA_RANKING else k


def rotina(r) -> int:
    """Balde do gasto no cruzamento com a rotina; -1 = fora (fixo, bem, nao e despesa)."""
    if r.tipo != "D" or r.classe == "reembolso" or r.NM_GRUPO in GRUPOS_FIXOS or r.NM_GRUPO in GRUPOS_BEM:
        return -1
    if r.NM_GRUPO == "Uber":
        return 3
    if r.NM_CATEGORIA == "ALIMENTAÇÃO":
        return 2 if r.NM_GRUPO in GRUPOS_MERCADO else (0 if r.NM_GRUPO in {"Suplemento", "Assinatura", "Utencilios"} else 1)
    if r.NM_CATEGORIA == "LAZER":
        return 4
    return 0


def le(eng) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT c.DT_DATA, f.VL_TRANSACAO, f.DS_TIPO_FLUXO, a.NM_AREA, k.NM_CATEGORIA,
               g.NM_GRUPO, g.DS_COMPRESSIBILIDADE, o.DS_TIPO_CONTA, f.DS_PESSOA_RECEBER
          FROM gold.fato_movto_financ f
          JOIN gold.dim_calendario c       ON c.SK_DATA = f.SK_DATA
          JOIN gold.dim_area_financ a      ON a.SK_AREA_FINANC = f.SK_AREA_FINANC
          JOIN gold.dim_categoria_financ k ON k.SK_CATEGORIA_FINANC = f.SK_CATEGORIA_FINANC
          JOIN gold.dim_grupo_financ g     ON g.SK_GRUPO_FINANC = f.SK_GRUPO_FINANC
          JOIN gold.dim_origem o           ON o.SK_ORIGEM = f.SK_ORIGEM
         WHERE f.DS_NIVEL = 'ANALITICO' AND f.SK_DATA >= {INICIO}
    """, eng)


def classifica(r) -> tuple[str, str]:
    """(tipo, classe). tipo: R receita, D despesa, P patrimonio."""
    area, cat, grupo, comp = r.NM_AREA, r.NM_CATEGORIA, r.NM_GRUPO, r.DS_COMPRESSIBILIDADE
    if (area in AREAS_PATRIMONIO or cat in CATS_PATRIMONIO or grupo in GRUPOS_PATRIMONIO
            or comp == "Nao e gasto"):
        return "P", "aporte" if r.DS_TIPO_FLUXO == "DESPESA" else "resgate"
    if r.DS_TIPO_FLUXO == "RECEITA" and area in AREAS_DESPESA:
        return "D", "reembolso"
    if r.DS_TIPO_FLUXO == "RECEITA":
        if grupo == "Salário":
            return "R", "salario"
        if grupo in GRUPOS_EXTRA or area in AREAS_EXTRA:
            return "R", "extra"
        return "R", "outras"
    if comp in CLASSE_DESPESA:
        return "D", CLASSE_DESPESA[comp]
    return "D", "essencial" if area == "GASTOS ESSENCIAIS" else "semclasse"


def gera() -> tuple[str, dict]:
    """Monta o painel e devolve (html, dados); o hub MZO reaproveita os dois."""
    eng = get_engine()
    df = le(eng)
    tipos = df.apply(classifica, axis=1, result_type="expand")
    df["tipo"], df["classe"] = tipos[0], tipos[1]
    df["data"] = pd.to_datetime(df["DT_DATA"]).dt.strftime("%Y-%m-%d")
    df["cat"] = df["NM_CATEGORIA"].str.strip().str.capitalize()
    # grupo digitado todo em maiusculas ("ALMOÇO") ganha so a inicial maiuscula
    df["grupo"] = df["NM_GRUPO"].str.strip().map(lambda g: g.capitalize() if g.isupper() and len(g) > 3 else g)

    # Valor sempre como efeito no bolso: receita positiva, despesa positiva
    # (gasto), reembolso negativo dentro da despesa (abate a categoria).
    v = df["VL_TRANSACAO"].astype(float)
    df["valor"] = v.abs()
    df.loc[df["classe"] == "reembolso", "valor"] = -v.abs()
    # receita negativa (estorno de salario, por exemplo) continua negativa
    df.loc[(df["tipo"] == "R") & (v < 0), "valor"] = v
    df["bem"] = df["grupo"].isin(GRUPOS_BEM).astype(int)
    df["cartao"] = (df["DS_TIPO_CONTA"] == "Cartão de crédito").astype(int)
    df["rot"] = [rotina(r) for r in df.itertuples()]

    # recebedor: chave normalizada; o nome exibido e a grafia mais comum dela
    df["rec_k"] = df["DS_PESSOA_RECEBER"].map(chave_rec)
    df.loc[df["tipo"] != "D", "rec_k"] = None
    nome_rec = (df.dropna(subset=["rec_k"]).assign(o=lambda x: x["DS_PESSOA_RECEBER"].str.strip())
                .groupby("rec_k")["o"].agg(lambda x: x.value_counts().index[0]))
    # TUDO MAIUSCULO ou tudo minusculo vira Titulo; sigla curta ("MG", "BH") continua sigla
    nome_rec = nome_rec.map(lambda n: " ".join(w if n.isupper() and len(w) <= 3 else w.capitalize() for w in n.split())
                            if n.isupper() or n.islower() else n)

    # dicionarios para nao repetir texto em cada linha
    cats = sorted(df["cat"].unique())
    grupos = sorted(df["grupo"].unique())
    recs = sorted(nome_rec.index)
    ic, ig = {c: i for i, c in enumerate(cats)}, {g: i for i, g in enumerate(grupos)}
    ir = {k: i for i, k in enumerate(recs)}
    # [data, valor, tipo, classe, cat, grupo, bem, cartao]; o hub le estas 8 colunas
    linhas = [[r.data, round(r.valor, 2), r.tipo, r.classe, ic[r.cat], ig[r.grupo], r.bem, r.cartao]
              for r in df.itertuples()]
    # paralelo a linhas: [recebedor (-1 sem), balde da rotina (-1 fora)]
    extra = [[ir.get(r.rec_k, -1) if isinstance(r.rec_k, str) else -1, r.rot] for r in df.itertuples()]

    dados = {"gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
             "cats": cats, "grupos": grupos, "linhas": linhas, "extra": extra,
             "recs": [nome_rec[k] for k in recs], "rotina": ROTINA, "dias": le_dias(eng, df["data"].min())}

    # conferencia no terminal: o que cada regra moveu
    print(f"{len(df)} lançamentos de {df['data'].min()} a {df['data'].max()}")
    print(df.groupby(["tipo", "classe"])["valor"].agg(["count", "sum"]).round(0).to_string())
    m = df[df["tipo"].isin(["R", "D"])].copy()
    m["mes"] = m["data"].str[:7]
    p = m.pivot_table(index="mes", columns="tipo", values="valor", aggfunc="sum").fillna(0)
    p["saldo"] = p["R"] - p["D"]
    print(p.tail(13).round(0).to_string())

    top = (df[df["rec_k"].notna() & (df["bem"] == 0) & (df["classe"] != "reembolso")]
           .groupby("rec_k")["valor"].agg(["count", "sum"]).sort_values("sum", ascending=False).head(10))
    print("\nOnde mais gasto (tudo, sem bens):", {nome_rec[k]: round(v) for k, v in top["sum"].items()})

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DADOS__*/null", json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.carimba(html, mzo.atualizacao(eng, ["fato_movto_financ", "fato_dia"]))
    return html, dados


def le_dias(eng, ini: str) -> dict:
    """
    Um caractere por dia, de ini ate hoje: trabalho e Nina em casa vem de
    gold.fato_dia ('1', '0' ou '-' sem registro); feriado do calendario.
    """
    d = pd.read_sql(f"""
        SELECT c.DT_DATA, c.FL_FERIADO, f.FL_TRABALHO, f.FL_NINA_EM_CASA
          FROM gold.dim_calendario c
          LEFT JOIN gold.fato_dia f ON f.SK_DATA = c.SK_DATA
         WHERE c.DT_DATA >= '{ini}' AND c.DT_DATA <= CAST(GETDATE() AS date)
         ORDER BY c.DT_DATA""", eng)
    flag = lambda s: "".join("-" if pd.isna(v) else ("1" if v == "S" else "0") for v in s)
    return {"ini": ini, "trab": flag(d["FL_TRABALHO"]), "nina": flag(d["FL_NINA_EM_CASA"]),
            "fer": "".join("1" if v == "S" else "0" for v in d["FL_FERIADO"])}


def main() -> int:
    import mzo  # identidade MZO Analytics, no mesmo diretorio
    html = mzo.assina(gera()[0])
    SAIDA.write_text(html, encoding="utf-8")
    print(f"\n{SAIDA}  {len(html) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
