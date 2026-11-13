"""
Varredura de dados pessoais antes de publicar.

Duas camadas:

  GENERICA (sempre roda, inclusive no CI): padroes que nunca deveriam
  aparecer num repositorio publico - CPF, CNPJ, e-mail, telefone,
  caminhos de usuario do Windows, URL de planilha Google publicada,
  chaves com cara de segredo.

  PRIVADA (so na maquina do autor): uma lista de termos sensiveis
  (nomes de pessoas, estabelecimentos, tags, enderecos) gerada a partir
  do banco real. A lista em si e sensivel, entao NAO e versionada: o
  caminho vem de PII_TERMOS ou de ../.pii_termos.txt, fora do
  repositorio. A busca diferencia maiusculas, para "contagem" (a
  palavra) nao ser confundida com o nome de uma cidade.

Uso:
    python tools/varredura_pii.py            # generica + privada, se houver lista
    python tools/varredura_pii.py --generica # so a generica (CI)

Sai com codigo 1 quando encontra algo.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PULA_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
EXTENSOES = {".py", ".sql", ".md", ".txt", ".json", ".yml", ".yaml", ".tmdl", ".pbir", ".pbism", ".pbip",
             ".ps1", ".cmd", ".cfg", ".toml", ".ini", ".html", ".js", ".css", ".csv", ".example", ""}

# padrao -> descricao. Os exemplos ficticios da documentacao usam a
# faixa reservada (00.000.000/0000-00, 000.000.000-00) e passam.
GENERICOS = {
    r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b": "CPF",
    r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b": "CNPJ",
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}": "e-mail",
    # telefone com DDI ou com separador no numero: um inteiro de 11 digitos
    # solto num JSON de dados e numero, nao telefone
    r"\+55[ .-]?\(?\d{2}\)?[ .-]?9?\d{4}[ .-]?\d{4}\b|\(?\b\d{2}\)?[ .]?9\d{4}[.-]\d{4}\b": "telefone",
    r"[A-Za-z]:\\\\?Users\\\\?[A-Za-z]": "caminho de usuario do Windows",
    r"/d/e/2PACX-[\w-]{10,}": "planilha Google publicada",
    r"docs\.google\.com/spreadsheets/d/[\w-]{20,}": "planilha Google",
    r"(?i)(?:secret|password|senha|token)\s*[=:]\s*['\"]?[A-Za-z0-9/+_-]{12,}": "segredo",
}
# o que pode aparecer de proposito
PERMITIDOS = {"000.000.000-00", "00.000.000/0000-00", "noreply@anthropic.com"}
# placeholders de exemplo (.env.example, docs): dominio reservado ou valor obviamente falso
PLACEHOLDER = re.compile(r"@(example\.com|exemplo\.com|seudominio\.com\.br)$|troque|change_?me|xxxx", re.IGNORECASE)


def arquivos():
    for p in RAIZ.rglob("*"):
        if p.is_file() and not (set(p.relative_to(RAIZ).parts) & PULA_DIRS) and p.suffix.lower() in EXTENSOES:
            if p.name in {".pii_termos.txt"}:
                continue
            yield p


def termos_privados() -> list[str]:
    # fora do repositorio por padrao: a lista nunca fica a um "git add ." de vazar
    caminho = Path(os.getenv("PII_TERMOS", RAIZ.parent / ".pii_termos.txt"))
    if not caminho.exists():
        return []
    return [t.strip() for t in caminho.read_text(encoding="utf-8").splitlines() if t.strip()]


def main() -> int:
    so_generica = "--generica" in sys.argv
    privados = [] if so_generica else termos_privados()
    # uma alternancia so, do termo mais longo ao mais curto: centenas de
    # regex separadas sobre o HTML gerado levariam minutos
    pad_priv = None
    if privados:
        alt = "|".join(re.escape(t) for t in sorted(privados, key=len, reverse=True))
        pad_priv = re.compile(r"(?<![\w])(?:" + alt + r")(?![\w])")
    pad_gen = [(d, re.compile(p)) for p, d in GENERICOS.items()]
    achados = 0
    for arq in arquivos():
        try:
            texto = arq.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            texto = arq.read_text(encoding="latin-1")
        for n, linha in enumerate(texto.splitlines(), 1):
            for desc, rx in pad_gen:
                for m in rx.finditer(linha):
                    if m.group(0) in PERMITIDOS or PLACEHOLDER.search(m.group(0)):
                        continue
                    achados += 1
                    print(f"{arq.relative_to(RAIZ)}:{n}: [{desc}] {m.group(0)[:60]}")
            if pad_priv:
                for m in pad_priv.finditer(linha):
                    achados += 1
                    # nao imprime o termo inteiro: o log do CI ou do terminal pode vazar
                    print(f"{arq.relative_to(RAIZ)}:{n}: [termo privado] {m.group(0)[:2]}***")
    modo = "generica" if so_generica or not privados else f"generica + {len(privados)} termos privados"
    print(f"\nVarredura {modo}: {achados} achado(s).")
    return 1 if achados else 0


if __name__ == "__main__":
    raise SystemExit(main())
