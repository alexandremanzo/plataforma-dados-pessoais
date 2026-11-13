"""
Relatorio das cargas: o que cada tabela inseriu e atualizou.

Le gold.fato_carga, que as 23 cargas alimentam a cada execucao. Antes
desse fato, o par inseridos/atualizados era calculado, impresso no
terminal e perdido - so quem estivesse olhando a tela na hora via.

O QUE PROCURAR AQUI. O projeto tem um contrato: rodar de novo, sem
mexer na origem, deve dar zero inserido e zero atualizado. Uma tabela
que atualiza linhas em TODA execucao nao esta acompanhando mudanca da
origem, esta com defeito - foi assim que apareceram as 172 atualizacoes
fantasma do arredondamento na avaliacao fisica e as 772 do historico
financeiro. O modo --historico e o que torna esse padrao visivel.

Nao ha regra de negocio aqui: ela esta na view, no banco. Este script
so projeta, como o exporta_glossario.py faz com o dicionario de dados.

Uso:
    python relatorio_carga.py                    # ultima execucao de cada tabela
    python relatorio_carga.py --historico 7      # serie dos ultimos 7 dias
    python relatorio_carga.py --html             # gera docs/relatorio-carga.html
    python relatorio_carga.py --email            # manda o resumo da rodada
    python relatorio_carga.py --email-se-problema  # so avisa se houver problema
    python relatorio_carga.py --vigia            # checagem de fora do Airflow
    python relatorio_carga.py --exigir-convergencia
"""

import argparse
import socket
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import (  # noqa: E402
    DB_CONFIG, PROJECT_ROOT, SMTP, get_engine,
)

DESTINO_HTML = PROJECT_ROOT / "docs" / "relatorio-carga.html"
DESTINO_MD = PROJECT_ROOT / "docs" / "relatorio-carga.md"

ORDEM_CAMADA = {"bronze": 1, "silver": 2, "gold": 3}

# Quantas horas sem rodar ja merecem suspeita. A DAG roda diariamente,
# entao pouco mais de um dia parado indica ramo quebrado - e nao folga.
LIMITE_HORAS = 30

# Com quantos dias de antecedencia avisar que o consentimento de Open
# Finance esta para vencer. Sessenta porque renovar exige entrar no
# navegador, autorizar e conferir - nao e coisa de fazer na vespera, e
# vencido o dado para de chegar sem a API dar erro.
LIMITE_DIAS_CONSENTIMENTO = 60


def le_ultima(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM gold.vw_carga_ultima", engine)
    if df.empty:
        return df
    df["_ordem"] = df["DS_CAMADA"].map(lambda c: ORDEM_CAMADA.get(c, 9))
    return df.sort_values(["_ordem", "DS_TABELA"]).drop(columns="_ordem")


def le_historico(engine, dias: int) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT DS_CAMADA, DS_TABELA, DT_EXECUCAO,
               NR_INSERIDOS, NR_ATUALIZADOS, NR_TOTAL, FL_CONVERGIU
        FROM gold.fato_carga
        WHERE DT_EXECUCAO >= DATEADD(day, -{int(dias)}, SYSDATETIME())
        ORDER BY DS_TABELA, DT_EXECUCAO
    """, engine)


def _estado(linha) -> str:
    """Estado antes do numero: e o que se le de relance."""
    if linha["NR_HORAS_ATRAS"] is not None and linha["NR_HORAS_ATRAS"] > LIMITE_HORAS:
        return "PARADA"
    return "ok" if linha["FL_CONVERGIU"] else "MOVIMENTO"


def imprime_ultima(df: pd.DataFrame) -> None:
    print("== Ultima execucao de cada carga ==\n")
    largura = max(len(t) for t in df["DS_TABELA"])

    for camada in sorted(df["DS_CAMADA"].unique(),
                         key=lambda c: ORDEM_CAMADA.get(c, 9)):
        bloco = df[df["DS_CAMADA"] == camada]
        print(f"-- {camada} ({len(bloco)} tabelas)")
        print(f"   {'tabela'.ljust(largura)}  {'inser':>6} {'atual':>6} "
              f"{'total':>8} {'seg':>6}  {'quando':<16} estado")
        for _, l in bloco.iterrows():
            quando = pd.Timestamp(l["DT_EXECUCAO"]).strftime("%d/%m %H:%M")
            horas = "" if pd.isna(l["NR_HORAS_ATRAS"]) else f" ({int(l['NR_HORAS_ATRAS'])}h)"
            print(f"   {l['DS_TABELA'].ljust(largura)}  "
                  f"{l['NR_INSERIDOS']:>6} {l['NR_ATUALIZADOS']:>6} "
                  f"{'' if pd.isna(l['NR_TOTAL']) else int(l['NR_TOTAL']):>8} "
                  f"{'' if pd.isna(l['NR_SEGUNDOS']) else float(l['NR_SEGUNDOS']):>6} "
                  f" {quando + horas:<16} {_estado(l)}")
        print()


def imprime_historico(df: pd.DataFrame, dias: int) -> None:
    """
    Uma linha por tabela, com o resumo da janela.

    NR_EXECUCOES_MOVEU contra NR_EXECUCOES e o numero que denuncia o
    defeito: uma tabela que se moveu em todas as execucoes nao esta
    acompanhando a origem.
    """
    print(f"== Historico dos ultimos {dias} dias ==\n")
    if df.empty:
        print("  (nenhuma execucao registrada na janela)")
        return

    resumo = df.groupby(["DS_CAMADA", "DS_TABELA"]).agg(
        execucoes=("FL_CONVERGIU", "size"),
        moveu=("FL_CONVERGIU", lambda s: int((~s.astype(bool)).sum())),
        inseridos=("NR_INSERIDOS", "sum"),
        atualizados=("NR_ATUALIZADOS", "sum"),
    ).reset_index()
    resumo["_ordem"] = resumo["DS_CAMADA"].map(lambda c: ORDEM_CAMADA.get(c, 9))
    resumo = resumo.sort_values(["_ordem", "DS_TABELA"])

    largura = max(len(t) for t in resumo["DS_TABELA"])
    print(f"   {'tabela'.ljust(largura)}  {'execs':>6} {'moveu':>6} "
          f"{'inser':>8} {'atual':>8}  observacao")
    for _, l in resumo.iterrows():
        # O sinal e a PROPORCAO, nao a presenca de movimento. Uma carga
        # que se moveu uma vez em quatro apenas trouxe dado novo; a que
        # se move sempre nao esta acompanhando a origem, esta com
        # defeito. Marcar a primeira transformaria o relatorio em ruido.
        nota = ""
        if l["execucoes"] >= 3 and l["moveu"] == l["execucoes"]:
            nota = "<-- moveu em TODAS: investigar"
        elif l["execucoes"] >= 3 and l["moveu"] > l["execucoes"] / 2:
            nota = "<-- moveu na maioria das execucoes"
        print(f"   {l['DS_TABELA'].ljust(largura)}  "
              f"{l['execucoes']:>6} {l['moveu']:>6} "
              f"{l['inseridos']:>8} {l['atualizados']:>8}  {nota}")
    print()


def _milhar(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")


def gera_md(df: pd.DataFrame, destino: Path) -> None:
    """
    Versao em Markdown, para o repositorio.

    Existe porque o GitHub nao renderiza .html na navegacao: abre o
    codigo-fonte. Um relatorio versionado que ninguem consegue ler na
    pagina do repositorio nao esta versionado de verdade.
    """
    gerado = datetime.now()
    convergiram = int(df["FL_CONVERGIU"].astype(bool).sum())
    paradas = int((df["NR_HORAS_ATRAS"].fillna(0) > LIMITE_HORAS).sum())
    total_linhas = _milhar(df["NR_TOTAL"].fillna(0).sum())

    rotulo = {"ok": "convergiu", "MOVIMENTO": "moveu", "PARADA": "**parada**"}

    linhas = [
        "# Saúde das cargas",
        "",
        "> Gerado por `python scripts/etl/relatorio_carga.py --md` a partir de",
        "> `gold.vw_carga_ultima`. Não edite este arquivo: ele é um retrato da",
        "> última execução de cada carga.",
        "",
        f"Retrato de {gerado:%d/%m/%Y às %H:%M} — **{len(df)} tabelas**, "
        f"{convergiram} convergiram, {paradas} paradas há mais de {LIMITE_HORAS}h, "
        f"{total_linhas} linhas sob controle.",
        "",
        "O contrato do projeto: rodar de novo, sem mexer na origem, tem de",
        "convergir em zero. `moveu` é esperado quando entrou dado novo de",
        "verdade — só vira defeito quando se repete em toda execução.",
        "",
    ]

    if convergiram < len(df):
        nomes = ", ".join(
            f"`{t}`" for t in df[~df["FL_CONVERGIU"].astype(bool)]["DS_TABELA"])
        linhas += [f"**Não convergiram na última execução:** {nomes}.", ""]

    for camada in sorted(df["DS_CAMADA"].unique(),
                         key=lambda c: ORDEM_CAMADA.get(c, 9)):
        bloco = df[df["DS_CAMADA"] == camada]
        linhas += [
            f"## {camada} — {len(bloco)} tabelas",
            "",
            "| Estado | Tabela | Inseridas | Atualizadas | Descartadas | "
            "Total | Duração | Última execução |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for _, l in bloco.iterrows():
            desc = "—" if pd.isna(l["NR_DESCARTADOS"]) else _milhar(l["NR_DESCARTADOS"])
            total = "—" if pd.isna(l["NR_TOTAL"]) else _milhar(l["NR_TOTAL"])
            seg = "—" if pd.isna(l["NR_SEGUNDOS"]) else f"{float(l['NR_SEGUNDOS']):.2f}s"
            quando = pd.Timestamp(l["DT_EXECUCAO"]).strftime("%d/%m %H:%M")
            linhas.append(
                f"| {rotulo[_estado(l)]} | `{l['DS_TABELA'].split('.', 1)[1]}` | "
                f"{_milhar(l['NR_INSERIDOS'])} | {_milhar(l['NR_ATUALIZADOS'])} | "
                f"{desc} | {total} | {seg} | {quando} |")
        linhas.append("")

    linhas += [
        "---",
        "",
        "**Descartadas** são linhas que não são lançamento — cauda de fórmula",
        "arrastada, linha sem chave; o traço marca as cargas que não descartam",
        "nada. As dimensões de classificação de `fato_movto_financ` e",
        "`fato_familia` ainda não aparecem aqui: a rotina que as sincroniza",
        "informa quantos membros entraram, mas não quantos mudaram, e registrar",
        "zero inventaria uma convergência que ninguém apurou.",
        "",
    ]

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")


def gera_html(df: pd.DataFrame, destino: Path) -> None:
    """
    Pagina estatica, com os dados embutidos.

    A pagina publicada nao alcanca o SQL Server, entao ela e um retrato
    do momento em que foi gerada - e por isso o carimbo de geracao fica
    visivel no topo, e nao escondido no rodape.
    """
    gerado = datetime.now()
    total = len(df)
    convergiram = int(df["FL_CONVERGIU"].astype(bool).sum())
    paradas = int((df["NR_HORAS_ATRAS"].fillna(0) > LIMITE_HORAS).sum())
    linhas_totais = f"{int(df['NR_TOTAL'].fillna(0).sum()):,}".replace(",", ".")
    ultima = pd.Timestamp(df["DT_EXECUCAO"].max())

    def secao(camada: str) -> str:
        bloco = df[df["DS_CAMADA"] == camada]
        if bloco.empty:
            return ""
        corpo = []
        for _, l in bloco.iterrows():
            estado = _estado(l)
            classe = {"ok": "ok", "MOVIMENTO": "moveu", "PARADA": "parada"}[estado]
            rotulo = {"ok": "convergiu", "MOVIMENTO": "moveu",
                      "PARADA": "parada"}[estado]
            quando = pd.Timestamp(l["DT_EXECUCAO"])
            horas = "" if pd.isna(l["NR_HORAS_ATRAS"]) else int(l["NR_HORAS_ATRAS"])
            # NaN e VERDADEIRO em Python, entao "x or 0" nao protege de
            # nada aqui - tem de ser pd.isna. Ja custou tres defeitos a
            # este projeto.
            desc = ("—" if pd.isna(l["NR_DESCARTADOS"])
                    else f"{int(l['NR_DESCARTADOS']):,}".replace(",", "."))
            total_tab = 0 if pd.isna(l["NR_TOTAL"]) else int(l["NR_TOTAL"])
            seg = 0.0 if pd.isna(l["NR_SEGUNDOS"]) else float(l["NR_SEGUNDOS"])
            corpo.append(f"""      <tr>
        <td><span class="chip {classe}">{rotulo}</span></td>
        <td class="nome">{l['DS_TABELA'].split('.', 1)[1]}</td>
        <td class="num destaque">{int(l['NR_INSERIDOS']):,}</td>
        <td class="num destaque">{int(l['NR_ATUALIZADOS']):,}</td>
        <td class="num fraco">{desc}</td>
        <td class="num">{total_tab:,}</td>
        <td class="num fraco">{seg:.2f}s</td>
        <td class="fraco">{quando:%d/%m %H:%M}<span class="ha"> · {horas}h</span></td>
      </tr>""".replace(",", "."))
        return f"""  <section class="camada {camada}">
    <h2><span class="marca"></span>{camada}<span class="conta">{len(bloco)} tabelas</span></h2>
    <div class="rolagem">
    <table>
      <thead><tr>
        <th>estado</th><th>tabela</th><th class="num">inseridas</th>
        <th class="num">atualizadas</th><th class="num">descartadas</th>
        <th class="num">total</th><th class="num">duração</th><th>última execução</th>
      </tr></thead>
      <tbody>
{chr(10).join(corpo)}
      </tbody>
    </table>
    </div>
  </section>"""

    alerta = ""
    if convergiram < total:
        nomes = ", ".join(
            t.split(".", 1)[1]
            for t in df[~df["FL_CONVERGIU"].astype(bool)]["DS_TABELA"])
        alerta = f"""  <p class="alerta"><strong>{total - convergiram} não convergiram
    na última execução:</strong> {nomes}. Isso é esperado quando entrou dado novo
    de verdade. Se repetir sem você ter mexido na origem, é defeito.</p>"""

    html = f"""<title>Saúde das Cargas</title>
<style>
:root {{
  --tinta: #1b1a17; --tinta-fraca: #6d685e; --tinta-tenue: #98928a;
  --fundo: #faf8f4; --painel: #ffffff; --borda: #e6e1d7;
  --bronze: #a4642a; --prata: #7d8a94; --ouro: #b08307;
  --bom: #2f6f45; --bom-fundo: #e6f0e7;
  --atencao: #8a5a10; --atencao-fundo: #f7eeda;
  --ruim: #94301f; --ruim-fundo: #f8e5e0;
  --serif: ui-serif, Georgia, "Iowan Old Style", "Times New Roman", serif;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --tinta: #ece7dd; --tinta-fraca: #a19a8e; --tinta-tenue: #6f6961;
    --fundo: #14130f; --painel: #1d1b17; --borda: #302c25;
    --bronze: #d08a49; --prata: #a7b4be; --ouro: #dcae3c;
    --bom: #7fc094; --bom-fundo: #1b2b20;
    --atencao: #d9ad5d; --atencao-fundo: #2e2515;
    --ruim: #e08d78; --ruim-fundo: #331a14;
  }}
}}
:root[data-theme="dark"] {{
  --tinta: #ece7dd; --tinta-fraca: #a19a8e; --tinta-tenue: #6f6961;
  --fundo: #14130f; --painel: #1d1b17; --borda: #302c25;
  --bronze: #d08a49; --prata: #a7b4be; --ouro: #dcae3c;
  --bom: #7fc094; --bom-fundo: #1b2b20;
  --atencao: #d9ad5d; --atencao-fundo: #2e2515;
  --ruim: #e08d78; --ruim-fundo: #331a14;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: clamp(1.5rem, 4vw, 3.5rem) clamp(1rem, 4vw, 2rem) 4rem;
  background: var(--fundo); color: var(--tinta);
  font-family: var(--sans); font-size: 15px; line-height: 1.5;
  -webkit-text-size-adjust: 100%;
}}
main {{ max-width: 1080px; margin: 0 auto; display: flex;
       flex-direction: column; gap: 2.5rem; }}
header {{ display: flex; flex-direction: column; gap: .35rem; }}
h1 {{ font-family: var(--serif); font-weight: 500; letter-spacing: -.015em;
     font-size: clamp(1.9rem, 5vw, 2.6rem); margin: 0; text-wrap: balance; }}
.sub {{ color: var(--tinta-fraca); max-width: 62ch; margin: 0; }}
.carimbo {{ font-family: var(--mono); font-size: .75rem; color: var(--tinta-tenue);
           text-transform: uppercase; letter-spacing: .08em; margin: .5rem 0 0; }}

.painel {{ display: grid; gap: 1px; background: var(--borda);
          border: 1px solid var(--borda); border-radius: 3px; overflow: hidden;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
.painel div {{ background: var(--painel); padding: 1rem 1.15rem; }}
.painel dt {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .09em;
             color: var(--tinta-tenue); margin: 0 0 .3rem; }}
.painel dd {{ margin: 0; font-family: var(--mono); font-size: 1.6rem;
             font-variant-numeric: tabular-nums; letter-spacing: -.02em; }}
.painel dd small {{ font-size: .8rem; color: var(--tinta-fraca);
                   font-family: var(--sans); letter-spacing: 0; }}

.alerta {{ margin: 0; padding: .9rem 1.1rem; border-radius: 3px;
          background: var(--atencao-fundo); color: var(--atencao);
          border-left: 3px solid currentColor; font-size: .9rem; }}
.alerta strong {{ color: inherit; }}

section h2 {{ display: flex; align-items: center; gap: .6rem; margin: 0 0 .8rem;
             font-family: var(--sans); font-size: .78rem; font-weight: 600;
             text-transform: uppercase; letter-spacing: .14em; }}
.marca {{ width: 26px; height: 3px; border-radius: 2px; background: var(--tinta-tenue); }}
.bronze .marca {{ background: var(--bronze); }}
.silver .marca {{ background: var(--prata); }}
.gold   .marca {{ background: var(--ouro); }}
.conta {{ margin-left: auto; font-weight: 400; letter-spacing: .04em;
         color: var(--tinta-tenue); text-transform: none; }}

.rolagem {{ overflow-x: auto; border: 1px solid var(--borda);
           border-radius: 3px; background: var(--painel); }}
table {{ border-collapse: collapse; width: 100%; font-size: .875rem; }}
th {{ text-align: left; font-weight: 500; font-size: .7rem; text-transform: uppercase;
     letter-spacing: .07em; color: var(--tinta-tenue); padding: .7rem .85rem;
     border-bottom: 1px solid var(--borda); white-space: nowrap; }}
td {{ padding: .6rem .85rem; border-bottom: 1px solid var(--borda);
     white-space: nowrap; }}
tr:last-child td {{ border-bottom: 0; }}
.num {{ text-align: right; font-family: var(--mono);
       font-variant-numeric: tabular-nums; }}
th.num {{ font-family: var(--sans); }}
.nome {{ font-family: var(--mono); font-size: .84rem; }}
.destaque {{ font-weight: 600; }}
.fraco {{ color: var(--tinta-fraca); }}
.ha {{ color: var(--tinta-tenue); }}

.chip {{ display: inline-block; padding: .15rem .5rem; border-radius: 2px;
        font-size: .68rem; text-transform: uppercase; letter-spacing: .07em;
        font-weight: 600; white-space: nowrap; }}
.chip.ok {{ background: var(--bom-fundo); color: var(--bom); }}
.chip.moveu {{ background: var(--atencao-fundo); color: var(--atencao); }}
.chip.parada {{ background: var(--ruim-fundo); color: var(--ruim); }}

footer {{ border-top: 1px solid var(--borda); padding-top: 1.2rem;
         color: var(--tinta-fraca); font-size: .82rem; max-width: 68ch; }}
footer code {{ font-family: var(--mono); font-size: .95em; }}
</style>

<main>
  <header>
    <h1>Saúde das cargas</h1>
    <p class="sub">Quanto cada tabela do <code>db-manzo</code> inseriu e atualizou
      na última execução. O contrato do projeto é simples: rodar de novo, sem
      mexer na origem, tem de convergir em zero.</p>
    <p class="carimbo">Retrato de {gerado:%d/%m/%Y às %H:%M} · última carga {ultima:%d/%m %H:%M}</p>
  </header>

  <dl class="painel">
    <div><dt>Tabelas monitoradas</dt><dd>{total}</dd></div>
    <div><dt>Convergiram</dt><dd>{convergiram}<small> de {total}</small></dd></div>
    <div><dt>Paradas há mais de {LIMITE_HORAS}h</dt><dd>{paradas}</dd></div>
    <div><dt>Linhas sob controle</dt><dd>{linhas_totais}</dd></div>
  </dl>

{alerta}

{secao('bronze')}

{secao('silver')}

{secao('gold')}

  <footer>
    Gerado por <code>scripts/etl/relatorio_carga.py --html</code> a partir de
    <code>gold.vw_carga_ultima</code>. <strong>Descartadas</strong> são linhas que
    não são lançamento — cauda de fórmula arrastada, linha sem chave; o traço
    marca as cargas que não descartam nada. As dimensões de classificação de
    <code>fato_movto_financ</code> e <code>fato_familia</code> ainda não aparecem
    aqui: a rotina que as sincroniza informa quantos membros entraram, mas não
    quantos mudaram, e registrar zero inventaria uma convergência que ninguém
    apurou.
  </footer>
</main>
"""

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")


def _confere_smtp() -> list[str]:
    """Chaves de SMTP que faltam preencher. Vazio quando esta tudo la."""
    NO_ENV = {"host": "SMTP_HOST", "usuario": "SMTP_USER",
              "senha": "SMTP_PASSWORD", "de": "SMTP_FROM", "para": "SMTP_PARA"}
    faltando = [c for c in ("host", "usuario", "senha", "de") if not SMTP[c]]
    if not SMTP["para"]:
        faltando.append("para")
    return [NO_ENV[c] for c in faltando]


def _envia(assunto: str, html: str, texto: str) -> None:
    """Entrega a mensagem. Unico ponto do projeto que fala com o SMTP."""
    import smtplib
    import ssl
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = SMTP["de"]
    msg["To"] = ", ".join(SMTP["para"])
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP["host"], SMTP["porta"], timeout=30) as servidor:
        servidor.starttls(context=ssl.create_default_context())
        servidor.login(SMTP["usuario"], SMTP["senha"])
        servidor.send_message(msg)

    print(f"E-mail enviado para {', '.join(SMTP['para'])}")
    print(f"  assunto: {assunto}")


def roda_vigia() -> int:
    """
    Checagem de fora do Airflow, uma vez por dia.

    POR QUE ELA PRECISA EXISTIR. Com e-mail so de erro, caixa de entrada
    silenciosa quer dizer "esta tudo bem" - mas Airflow parado tambem
    fica silencioso, e as duas situacoes ficam indistinguiveis. A
    checagem de carga parada mora dentro da propria DAG, entao ela nao
    roda justamente quando mais precisaria.

    Este modo roda pelo Agendador de Tarefas do Windows, sem depender de
    Docker, de Airflow nem de o usuario estar logado. Ele so precisa do
    SQL Server, que e outro processo.

    E AVISA ATE QUANDO NAO CONSEGUE CHECAR. Se o banco nao responde, o
    silencio voltaria a significar duas coisas - so que um nivel abaixo.
    Por isso a falha de conexao vira e-mail, e nao apenas um traceback
    num log que ninguem le.
    """
    from datetime import datetime

    agora = datetime.now()
    faltando = _confere_smtp()
    if faltando:
        print("ERRO: vigia sem SMTP configurado - nao ha como avisar de nada.")
        print(f"  Falta no .env: {', '.join(faltando)}")
        return 1

    try:
        engine = get_engine()
        df = le_ultima(engine)
        if df.empty:
            problemas = ["gold.fato_carga esta vazia: nenhuma carga registrou "
                         "execucao. O pipeline pode nunca ter rodado."]
        else:
            problemas = detecta_problemas(engine, df)
    except Exception as erro:                          # noqa: BLE001
        # Qualquer falha aqui e noticia: banco fora do ar, credencial
        # trocada, driver ODBC removido. Nao ha como saber o estado das
        # cargas, e isso precisa chegar em voce.
        detalhe = f"{type(erro).__name__}: {erro}"

        # DE ONDE E PARA ONDE. Sem isto o aviso nao distingue "o SQL
        # Server caiu" de "alguem rodou apontando para outro servidor" -
        # e foi exatamente essa confusao que dois e-mails de teste
        # causaram, com um DB_SERVER forjado que a mensagem nao mostrava.
        contexto = (f"maquina {socket.gethostname()} · servidor "
                    f"{DB_CONFIG['server']} · banco {DB_CONFIG['database']}")
        print(f"VIGIA NAO CONSEGUIU CHECAR ({contexto}): {detalhe}")
        A = chr(34)
        _envia(
            assunto=(f"manzo-dados · VIGIA · sem resposta de "
                     f"{DB_CONFIG['server']}"),
            html=("<div style=" + A + "font-family:Segoe UI,Arial,sans-serif" + A + ">"
                  "<p><b>O vigia rodou mas nao conseguiu consultar o banco.</b></p>"
                  "<table style=" + A + "border-collapse:collapse;margin:0 0 12px" + A + ">"
                  "<tr><td style=" + A + "padding:2px 10px 2px 0;color:#5a636b" + A + ">"
                  "Maquina</td><td style=" + A + "font-family:Consolas,monospace" + A + f">{socket.gethostname()}</td></tr>"
                  "<tr><td style=" + A + "padding:2px 10px 2px 0;color:#5a636b" + A + ">"
                  "Servidor</td><td style=" + A + "font-family:Consolas,monospace" + A + f">{DB_CONFIG['server']}</td></tr>"
                  "<tr><td style=" + A + "padding:2px 10px 2px 0;color:#5a636b" + A + ">"
                  "Banco</td><td style=" + A + "font-family:Consolas,monospace" + A + f">{DB_CONFIG['database']}</td></tr>"
                  "<tr><td style=" + A + "padding:2px 10px 2px 0;color:#5a636b" + A + ">"
                  "Quando</td><td style=" + A + "font-family:Consolas,monospace" + A + f">{agora:%d/%m/%Y as %H:%M}</td></tr>"
                  "</table>"
                  "<p style=" + A + "font-family:Consolas,monospace;font-size:12px;"
                  "background:#f5f5f5;padding:8px" + A + f">{detalhe}</p>"
                  "<p><b>Se o servidor acima nao for o de sempre</b>, alguem rodou "
                  "o vigia apontando para outro lugar e nao ha nada errado com as "
                  "cargas. Sendo o de sempre, confira se o SQL Server esta no ar - "
                  "enquanto isso durar, nao ha como saber se as cargas estao "
                  "rodando.</p></div>"),
            texto=(f"O vigia rodou em {agora:%d/%m/%Y as %H:%M} mas nao conseguiu "
                   f"consultar o banco.{chr(10)}{contexto}{chr(10)}{detalhe}"),
        )
        return 1

    if not problemas:
        print(f"Vigia de {agora:%d/%m %H:%M}: {len(df)} tabelas, nada a comunicar.")
        return 0

    print(f"Vigia de {agora:%d/%m %H:%M}: {len(problemas)} problemas.")
    for p in problemas:
        print(f"  - {p}")
    envia_email(df, problemas)
    return 0


def consentimento_a_vencer(engine) -> list[str]:
    """
    Consentimento de Open Finance perto do fim.

    O TERCEIRO SINAL DO VIGIA, e o unico que avisa ANTES do estrago. Os
    outros dois contam o que ja aconteceu - carga parada, carga que nao
    converge. Este conta o que vai acontecer.

    Precisa existir porque o vencimento NAO SE ANUNCIA: a API continua
    respondendo depois dele, com dado velho ou lista vazia. A carga tem
    guarda contra isso, mas ela so dispara depois de vencido - e aí a
    serie ja tem buraco.

    LE DO BANCO, NAO DA API. O vigia roda fora do Airflow e fala so com
    o SQL Server, e e dessa limitacao que vem a utilidade dele:
    funciona com o Docker parado, a rede fora ou a API caida. Consultar
    a Pluggy aqui devolveria a dependencia que ele existe para nao ter.
    Quem grava a data e a carga, que ja le o item de qualquer forma.

    Tolera a coluna nao existir: o vigia nao pode quebrar por causa de
    um script de migracao que ninguem rodou ainda.
    """
    try:
        df = pd.read_sql(f"""
            SELECT TOP 1 dt_consentimento_vence AS vence,
                   DATEDIFF(day, CAST(SYSDATETIME() AS date),
                            dt_consentimento_vence) AS dias
            FROM bronze.xp_posicao
            WHERE dt_consentimento_vence IS NOT NULL
            ORDER BY dt_snapshot DESC
        """, engine)
    except Exception:                                    # noqa: BLE001
        return []

    if df.empty:
        return []
    dias = int(df["dias"].iloc[0])
    if dias > LIMITE_DIAS_CONSENTIMENTO:
        return []
    quando = pd.Timestamp(df["vence"].iloc[0]).strftime("%d/%m/%Y")
    if dias < 0:
        return [f"o consentimento de Open Finance da XP VENCEU em {quando} "
                f"({abs(dias)} dias atras) - a posicao parou de chegar, e a "
                f"API nao da erro por isso. Reconecte em dashboard.pluggy.ai"]
    return [f"o consentimento de Open Finance da XP vence em {quando}, "
            f"daqui a {dias} dias. Renovar exige autorizar no navegador; "
            f"vencido, a posicao para de chegar sem a API dar erro"]


def detecta_problemas(engine, df: pd.DataFrame) -> list[str]:
    """
    O que merece interromper alguem por e-mail.

    NAO E "nao convergiu". Entrou dado novo e a tabela cresceu: isso e o
    pipeline trabalhando, e avisar toda vez transformaria o alerta em
    ruido - que e como se para de ler alerta. Sao dois sinais, e os dois
    sao raros de proposito:

    1. CARGA PARADA. A tabela nao e tocada ha mais de LIMITE_HORAS, num
       pipeline que roda tres vezes ao dia. Ramo quebrado na DAG, ou
       origem que deixou de existir.

    2. CARGA QUE NUNCA CONVERGE. Moveu linha em TODAS as ultimas
       execucoes. O projeto tem o contrato de que rodar de novo, sem
       mexer na origem, da zero - quem move sempre nao esta acompanhando
       mudanca, esta com defeito. Foi assim que apareceram as 772
       atualizacoes fantasma do historico financeiro, as 172 do
       arredondamento na avaliacao fisica e a oscilacao do XP entre duas
       versoes do pandas. Nenhuma delas seria pega por email_on_failure:
       as tres cargas terminavam com sucesso.

    O que o Airflow ja cobre sozinho nao entra aqui: tarefa que falha
    tem email_on_failure, e bronze vazia tem on_skipped_callback.
    """
    problemas = []

    for _, l in df[df["NR_HORAS_ATRAS"].fillna(0) > LIMITE_HORAS].iterrows():
        problemas.append(
            f"{l['DS_TABELA']} nao roda ha {int(l['NR_HORAS_ATRAS'])} horas")

    problemas += consentimento_a_vencer(engine)

    hist = le_historico(engine, 7)
    if len(hist):
        resumo = hist.groupby("DS_TABELA").agg(
            execucoes=("FL_CONVERGIU", "size"),
            moveu=("FL_CONVERGIU", lambda s: int((~s.astype(bool)).sum())),
            atualizados=("NR_ATUALIZADOS", "sum"),
        ).reset_index()
        teimosas = resumo[(resumo["execucoes"] >= 3)
                          & (resumo["moveu"] == resumo["execucoes"])]
        for _, l in teimosas.iterrows():
            problemas.append(
                f"{l['DS_TABELA']} moveu linha nas {int(l['execucoes'])} "
                f"execucoes da semana ({int(l['atualizados'])} atualizacoes) "
                f"- nunca converge")

    return problemas


def envia_email(df: pd.DataFrame, problemas=None) -> None:
    """
    Manda o resumo da rodada por e-mail.

    UM E-MAIL POR RODADA, E NAO UM POR CARGA. Sao 28 tarefas tres vezes
    ao dia: um aviso por carga daria 84 mensagens diarias, e o efeito
    conhecido disso e a pessoa criar uma regra de caixa de entrada e
    parar de ler - inclusive as falhas. Aqui vai a rodada inteira numa
    tabela, com sucesso e problema lado a lado. A falha continua tendo
    aviso proprio e imediato, mandado pelo Airflow na hora em que
    acontece.

    O ASSUNTO JA CONTA A HISTORIA, para nao ser preciso abrir a mensagem
    quando esta tudo bem.
    """
    faltando = _confere_smtp()
    if faltando:
        chaves = ", ".join(faltando)
        print("ERRO: envio de e-mail nao configurado.")
        print(f"  Falta preencher no .env: {chaves}")
        print("  A senha e uma SENHA DE APLICATIVO do Google, gerada em")
        print("  https://myaccount.google.com/apppasswords - a senha da conta")
        print("  e recusada quando a verificacao em duas etapas esta ligada.")
        raise SystemExit(1)

    nao_convergiram = df[~df["FL_CONVERGIU"].astype(bool)]
    paradas = df[df["NR_HORAS_ATRAS"].fillna(0) > LIMITE_HORAS]
    agora = datetime.now()

    if problemas:
        assunto = (f"manzo-dados · PROBLEMA · {len(problemas)} "
                   + ("carga precisa" if len(problemas) == 1
                      else "cargas precisam") + " de atencao")
    else:
        resumo = []
        if len(nao_convergiram):
            resumo.append(f"{len(nao_convergiram)} nao convergiram")
        if len(paradas):
            resumo.append(f"{len(paradas)} paradas")
        assunto = (f"manzo-dados · {agora:%d/%m %Hh} · "
                   + (", ".join(resumo) if resumo
                      else f"{len(df)} tabelas, tudo convergindo"))

    # Estilo EM LINHA, e nao numa folha no cabecalho: varios clientes de
    # e-mail descartam <style>, e a tabela chegaria sem formatacao.
    cab = ("padding:6px 10px;border-bottom:2px solid #333;text-align:left;"
           "font-size:11px;text-transform:uppercase;letter-spacing:.06em")
    cel = "padding:5px 10px;border-bottom:1px solid #e5e5e5"
    num = cel + ";text-align:right;font-family:Consolas,monospace"
    ROTULO = {"ok": "convergiu", "MOVIMENTO": "moveu", "PARADA": "PARADA"}
    COR = {"ok": "#2f6f45", "MOVIMENTO": "#8a5a10", "PARADA": "#96311f"}

    linhas = []
    for camada in sorted(df["DS_CAMADA"].unique(),
                         key=lambda c: ORDEM_CAMADA.get(c, 9)):
        bloco = df[df["DS_CAMADA"] == camada]
        linhas.append(
            f'<tr><td colspan="6" style="{cel};padding-top:14px;'
            f'font-weight:700">{camada} — {len(bloco)} tabelas</td></tr>')
        for _, l in bloco.iterrows():
            estado = _estado(l)
            total = "—" if pd.isna(l["NR_TOTAL"]) else _milhar(l["NR_TOTAL"])
            seg = ("—" if pd.isna(l["NR_SEGUNDOS"])
                   else f"{float(l['NR_SEGUNDOS']):.1f}s")
            linhas.append(
                f'<tr><td style="{cel}">{l["DS_TABELA"]}</td>'
                f'<td style="{num}">{int(l["NR_INSERIDOS"])}</td>'
                f'<td style="{num}">{int(l["NR_ATUALIZADOS"])}</td>'
                f'<td style="{num}">{total}</td>'
                f'<td style="{num}">{seg}</td>'
                f'<td style="{cel};color:{COR[estado]};font-weight:600">'
                f'{ROTULO[estado]}</td></tr>')

    alerta = ""
    if problemas:
        itens = "".join(f"<li>{p}</li>" for p in problemas)
        alerta = ('<p style="background:#f9e6e1;border-left:3px solid #96311f;'
                  'padding:10px 14px;margin:0 0 16px"><b>Precisa de atencao:</b>'
                  f'<ul style="margin:6px 0 0">{itens}</ul></p>')
    elif len(nao_convergiram):
        nomes = ", ".join(nao_convergiram["DS_TABELA"])
        alerta = ('<p style="background:#f8efdc;border-left:3px solid #8a5a10;'
                  'padding:10px 14px;margin:0 0 16px"><b>Nao convergiram:</b> '
                  f'{nomes}.<br>E esperado quando entrou dado novo. Se repetir '
                  'sem voce ter mexido na origem, e defeito.</p>')

    cabecalho = (
        f'<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;'
        f'color:#16191c;max-width:760px">'
        f'<h2 style="margin:0 0 4px;font-size:18px">Cargas de '
        f'{agora:%d/%m/%Y as %H:%M}</h2>'
        f'<p style="margin:0 0 16px;color:#5a636b">{len(df)} tabelas · '
        f'{len(df) - len(nao_convergiram)} convergiram · {len(paradas)} '
        f'paradas ha mais de {LIMITE_HORAS}h</p>')
    titulos = (f'<tr><th style="{cab}">Tabela</th>'
               f'<th style="{cab};text-align:right">Inseridas</th>'
               f'<th style="{cab};text-align:right">Atualizadas</th>'
               f'<th style="{cab};text-align:right">Total</th>'
               f'<th style="{cab};text-align:right">Duracao</th>'
               f'<th style="{cab}">Estado</th></tr>')
    rodape = ('<p style="margin:18px 0 0;color:#8b949c;font-size:12px">'
              'Gerado por relatorio_carga.py --email. Falha de tarefa tem '
              'aviso proprio, mandado pelo Airflow na hora.</p></div>')

    html = (cabecalho + alerta
            + '<table style="border-collapse:collapse;width:100%">'
            + titulos + chr(10).join(linhas) + "</table>" + rodape)

    texto = [f"Cargas de {agora:%d/%m/%Y as %H:%M}",
             f"{len(df)} tabelas, {len(df) - len(nao_convergiram)} "
             f"convergiram, {len(paradas)} paradas", ""]
    for _, l in df.iterrows():
        texto.append(f"  {l['DS_TABELA']:<38} +{int(l['NR_INSERIDOS']):<6} "
                     f"{int(l['NR_ATUALIZADOS']):<6} {_estado(l)}")

    _envia(assunto, html, chr(10).join(texto))


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatorio das cargas")
    parser.add_argument("--historico", type=int, metavar="DIAS",
                        help="serie dos ultimos N dias, por tabela")
    parser.add_argument("--html", action="store_true",
                        help="gera docs/relatorio-carga.html")
    parser.add_argument("--email", action="store_true",
                        help="manda o resumo por e-mail, haja o que houver")
    parser.add_argument("--vigia", action="store_true",
                        help="checagem de fora do Airflow, para o Agendador "
                             "de Tarefas. Avisa ate quando nao consegue "
                             "consultar o banco")
    parser.add_argument("--email-se-problema", action="store_true",
                        help="so manda e-mail se houver carga parada ou "
                             "carga que nunca converge. E o modo usado pela "
                             "DAG: silencio quando esta tudo bem")
    parser.add_argument("--md", action="store_true",
                        help="gera docs/relatorio-carga.md, que o GitHub "
                             "renderiza na propria pagina do repositorio")
    parser.add_argument("--exigir-convergencia", action="store_true",
                        help="sai com codigo 1 se alguma carga nao convergiu. "
                             "So faz sentido na SEGUNDA execucao seguida: na "
                             "primeira, inserir linha nova e o comportamento "
                             "correto, nao falha.")
    args = parser.parse_args()

    if args.vigia:
        return roda_vigia()

    engine = get_engine()
    df = le_ultima(engine)

    if df.empty:
        print("Nenhuma carga registrada ainda em gold.fato_carga.")
        print("  Rode qualquer carga - elas gravam sozinhas.")
        return 0

    if args.historico:
        imprime_historico(le_historico(engine, args.historico), args.historico)
    else:
        imprime_ultima(df)

    nao_convergiram = df[~df["FL_CONVERGIU"].astype(bool)]
    paradas = df[df["NR_HORAS_ATRAS"].fillna(0) > LIMITE_HORAS]
    print(f"{len(df)} tabelas · {len(df) - len(nao_convergiram)} convergiram · "
          f"{len(paradas)} paradas ha mais de {LIMITE_HORAS}h")

    if len(nao_convergiram):
        print("\nNao convergiram na ultima execucao:")
        for _, l in nao_convergiram.iterrows():
            print(f"  {l['DS_TABELA']:<38} +{l['NR_INSERIDOS']} novos, "
                  f"{l['NR_ATUALIZADOS']} atualizados  ({l['DS_SCRIPT']})")

    if args.html:
        gera_html(df, DESTINO_HTML)
        print(f"\nGerado: {DESTINO_HTML}")

    if args.md:
        gera_md(df, DESTINO_MD)
        print(f"Gerado: {DESTINO_MD}")

    if args.email:
        envia_email(df)

    if args.email_se_problema:
        problemas = detecta_problemas(engine, df)
        if problemas:
            print()
            print(f"{len(problemas)} problemas encontrados:")
            for p in problemas:
                print(f"  - {p}")
            envia_email(df, problemas)
        else:
            print("Nada a comunicar: nenhuma carga parada nem teimosa.")

    return 1 if (args.exigir_convergencia and len(nao_convergiram)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
