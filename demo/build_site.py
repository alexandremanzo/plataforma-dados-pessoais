"""
Monta a demonstracao de ponta a ponta: banco vazio -> dados ficticios -> site.

  1. demo/prepara_banco.py  cria o banco e a estrutura (demo/schema)
  2. demo/gera_dados.py     preenche a camada gold com a vida inventada
  3. atualiza_paineis.py    gera site/index.html (hub) e site/painel-*.html

O site/ e estatico e autocontido: e o que o GitHub Pages publica.

Uso:
    python demo/build_site.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASSOS = [RAIZ / "demo" / "prepara_banco.py", RAIZ / "demo" / "gera_dados.py",
          RAIZ / "scripts" / "paineis" / "atualiza_paineis.py"]


def main() -> int:
    for passo in PASSOS:
        print(f"\n=== {passo.relative_to(RAIZ)}", flush=True)
        r = subprocess.run([sys.executable, str(passo)], cwd=RAIZ)
        if r.returncode:
            print(f"falhou: {passo.name} (saida {r.returncode})")
            return r.returncode
    print(f"\nSite pronto em {RAIZ / 'site'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
