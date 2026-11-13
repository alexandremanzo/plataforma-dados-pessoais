"""
Identidade MZO Analytics compartilhada pelos paineis.

O logo e um selo arredondado em degrade ouro -> menta com um "M" desenhado
como linha de grafico (sobe, desce, sobe) e o ponto final aceso: a marca
diz "dado" antes de dizer "letra". Ao lado, MZO em Bahnschrift largo e
ANALYTICS espacado.

assina(html, nome) troca a marca do topo de cada painel pela assinatura
MZO, para os arquivos avulsos; o hub (painel_mzo.py) usa o mesmo logo na
barra lateral e esconde a marca de dentro de cada painel.
"""

from __future__ import annotations

import re


def selo(tam: int = 30, uid: str = "mzo") -> str:
    """Selo do logo em SVG. uid evita id de degrade repetido na mesma pagina."""
    return (
        f'<svg class="mzo-selo" width="{tam}" height="{tam}" viewBox="0 0 40 40" fill="none" aria-hidden="true">'
        f'<defs><linearGradient id="{uid}-g" x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse">'
        '<stop stop-color="#f2d38a"/><stop offset=".55" stop-color="#e9c46a"/><stop offset="1" stop-color="#4fd1a5"/></linearGradient></defs>'
        f'<rect x="1" y="1" width="38" height="38" rx="11" fill="url(#{uid}-g)"/>'
        '<path d="M9.5 28.5V12.5l10.5 11 10.5-11v16" stroke="#071013" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="30.5" cy="28.5" r="2.6" fill="#071013"/>'
        '</svg>'
    )


def logo(tam: int = 30, uid: str = "mzo") -> str:
    return (f'<span class="mzo-logo">{selo(tam, uid)}<span class="mzo-txt"><b>MZO</b>'
            '<small>Analytics</small></span></span>')


CSS = """
  .mzo-logo { display: inline-flex; align-items: center; gap: 10px; text-decoration: none; color: #e8f2f0; }
  .mzo-logo .mzo-selo { flex: none; filter: drop-shadow(0 4px 14px rgba(233, 196, 106, .25)); }
  .mzo-txt { display: grid; line-height: 1; gap: 3px; }
  .mzo-txt b { font-family: Bahnschrift, "DIN Alternate", system-ui, sans-serif; font-weight: 700; font-size: 17px; letter-spacing: .14em; }
  .mzo-txt small { font-size: 8.5px; letter-spacing: .38em; text-transform: uppercase; color: #8fa8a5; font-weight: 600; }
  .marca .mzo-sep { width: 1px; height: 26px; background: #2a4a51; margin: 0 6px; }
"""


CSS_ATUAL = """
  .mzo-atual { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: #8fa8a5; margin-left: auto; cursor: help; }
  .mzo-atual i { width: 7px; height: 7px; border-radius: 50%; background: #4fd1a5; box-shadow: 0 0 0 3px rgba(79, 209, 165, .18); flex: none; }
  .mzo-atual b { color: #e8f2f0; font-weight: 600; }
"""


def atualizacao(eng, tabelas: list[str]) -> dict:
    """
    Ultima atualizacao das tabelas gold que o painel le, por gold.fato_carga.

    "dados" e a ultima carga que trouxe linha nova ou alterada; "conferido"
    e a ultima carga que rodou, mesmo sem novidade. O painel mostra a mais
    recente das "dados" e lista cada tabela no title.
    """
    import pandas as pd

    nomes = ", ".join("'" + (t if t.startswith("gold.") else "gold." + t) + "'" for t in tabelas)
    df = pd.read_sql(f"""
        SELECT DS_TABELA, MAX(DT_EXECUCAO) conferido,
               MAX(CASE WHEN NR_INSERIDOS + NR_ATUALIZADOS > 0 THEN DT_EXECUCAO END) dados
          FROM gold.fato_carga WHERE DS_TABELA IN ({nomes}) GROUP BY DS_TABELA""", eng)
    fmt = lambda v: None if pd.isna(v) else pd.Timestamp(v).strftime("%d/%m/%Y %H:%M")
    tabs = {r.DS_TABELA.removeprefix("gold."): {"dados": fmt(r.dados), "conferido": fmt(r.conferido)} for r in df.itertuples()}
    return {"dados": fmt(df["dados"].max()) if df["dados"].notna().any() else None,
            "conferido": fmt(df["conferido"].max()) if len(df) else None, "tabelas": tabs}


def carimba(html: str, info: dict) -> str:
    """Selo "Atualizado dd/mm hh:mm" na barra do topo, depois do menu de secoes."""
    from html import escape

    if not info.get("dados"):
        return html
    det = (f"Última carga conferida em {info['conferido']}\n"
           + "\n".join(f"{t}: dados {v['dados'] or '—'} · conferido {v['conferido'] or '—'}" for t, v in info["tabelas"].items()))
    curto = info["dados"][:5] + info["dados"][10:16]   # "dd/mm hh:mm"
    det = "Dados fictícios de demonstração · Fictional demo data\n" + det
    chip = f'\n    <span class="mzo-atual" title="{escape(det)}"><i></i>Dados fictícios · atualizado <b>{curto}</b></span>'
    # o menu fica colado na marca e o selo vai para a direita
    i = html.index('<nav class="nav"')
    j = html.index("</nav>", i) + len("</nav>")
    html = html[:j] + chip + html[j:]
    return html.replace("</style>", CSS_ATUAL + "</style>", 1)


def assina(html: str, uid: str = "mzo") -> str:
    """Poe o logo MZO antes do icone e do nome do painel, e o CSS dele."""
    html = re.sub(r'<div class="marca">', '<div class="marca">' + logo(28, uid) + '<span class="mzo-sep"></span>', html, count=1)
    return html.replace("</style>", CSS + "</style>", 1)
