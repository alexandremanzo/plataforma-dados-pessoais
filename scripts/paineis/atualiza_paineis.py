"""
Gera todos os paineis e o hub MZO Analytics em site/.

Cada painel roda isolado: um que falha nao impede os outros, e o codigo
de saida diz quantos falharam. O hub vai por ultimo, porque embute a
versao de cada painel.

Uso:
    python scripts/paineis/atualiza_paineis.py
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAINEIS = ["painel_saude", "painel_familia", "painel_financas", "painel_patrimonio", "painel_investimentos",
           "painel_cartao", "painel_carro", "painel_viagens", "painel_mzo"]


def main() -> int:
    (Path(__file__).resolve().parents[2] / "site").mkdir(exist_ok=True)
    falhas = {}
    for nome in PAINEIS:
        t0 = time.time()
        print(f"--- {nome}", flush=True)
        try:
            __import__(nome).main()
            print(f"ok em {time.time() - t0:.0f}s", flush=True)
        except Exception:
            falhas[nome] = traceback.format_exc()
            print(falhas[nome], flush=True)
    print(f"\n{len(PAINEIS) - len(falhas)} de {len(PAINEIS)} paineis gerados" + (f"; falharam: {', '.join(falhas)}" if falhas else ""))
    return len(falhas)


if __name__ == "__main__":
    raise SystemExit(main())
