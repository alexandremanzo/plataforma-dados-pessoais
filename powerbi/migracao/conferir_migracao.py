"""
Prova que a consulta nova devolve o mesmo que a antiga, celula a celula.

A migracao do relatorio pessoal troca a origem de cada tabela - planilha
por banco - e a unica garantia aceitavel e numerica: mesma quantidade de
linhas, mesmas chaves, mesmos valores. Impressao de que "ficou igual" nao
serve, porque o modo de falhar aqui e SILENCIOSO: o gold canonizou os
valores ("Sim" virou "SIM"), e uma medida que compara com "Sim" passa a
contar zero sem dar erro nenhum. O visual continua desenhando, vazio.

Cada tabela migrada ganha uma entrada em TABELAS com dois SELECTs:
  antiga  - reproduz o que o relatorio le HOJE (em geral a bronze, que e
            a copia fiel da origem)
  nova    - o arquivo .sql que vai para dentro do Power BI

Uso:
    python conferir_migracao.py
    python conferir_migracao.py f_meu_dia
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "conf"))

from config_db import get_engine  # noqa: E402

# A consulta "antiga" nao le a planilha: le a bronze, que a carga trouxe
# da mesma origem sem transformar nada. Evita depender de rede e de
# credencial de planilha publicada so para conferir.
TABELAS = {
    "f_meu_dia": {
        "chave": "Data",
        "antiga": """
            SELECT CAST(ds_data AS date)  AS [Data],
                   ds_carimbo             AS [Carimbo de data/hora],
                   ds_treino              AS [Treino],
                   ds_cardio              AS [Cardio],
                   TRY_CAST(REPLACE(ds_agua_litros, ',', '.') AS float)
                                          AS [Consumo de água (Litros)],
                   ds_cafe_manha          AS [Café da Manhã],
                   ds_almoco              AS [Almoço],
                   ds_lanche              AS [Lanche],
                   ds_janta               AS [Janta],
                   ds_ceia                AS [Ceia],
                   ds_dia_produtivo       AS [Dia Produtivo],
                   ds_trabalho            AS [Trabalho],
                   ds_nina_em_casa         AS [Nina em casa],
                   ds_estresse               AS [Estresse],
                   ds_lazer              AS [Lazer]
            FROM bronze.dia_registro
            WHERE ds_data BETWEEN '2020-01-01' AND '2030-01-01'
        """,
        "nova": "f_meu_dia.sql",
        # Divergencia conhecida e desejada: o formulario tem "Nao" e "Nao"
        # para o mesmo campo, e o gold canonizou as duas. Nenhuma medida
        # nem visual compara Cardio com "Nao", entao nenhum numero muda.
        "esperado": {"Cardio": "normalizacao de acento, sem efeito em medida"},
    },
}


def confere(nome: str, cfg: dict, eng) -> bool:
    antiga = pd.read_sql(cfg["antiga"], eng)
    nova = pd.read_sql((BASE / cfg["nova"]).read_text(encoding="utf-8"), eng)
    ch = cfg["chave"]

    a = antiga.set_index(ch).sort_index()
    n = nova.set_index(ch).sort_index()

    print(f"\n=== {nome} ===")
    print(f"  linhas       antiga {len(a)}   nova {len(n)}")
    so_a, so_n = a.index.difference(n.index), n.index.difference(a.index)
    if len(so_a) or len(so_n):
        print(f"  CHAVES       so na antiga {len(so_a)}   so na nova {len(so_n)}")
        for k in list(so_a)[:3]:
            print(f"     perdida: {k}")
        for k in list(so_n)[:3]:
            print(f"     surgida: {k}")

    faltando = [c for c in a.columns if c not in n.columns]
    sobrando = [c for c in n.columns if c not in a.columns]
    if faltando:
        print(f"  COLUNAS      ausentes na nova: {faltando}")
    if sobrando:
        print(f"  colunas novas (inofensivo): {sobrando}")

    cols = [c for c in a.columns if c in n.columns]
    comum = a.index.intersection(n.index)
    dif = (n.loc[comum, cols].fillna("~").astype(str)
           != a.loc[comum, cols].fillna("~").astype(str))
    total = int(dif.values.sum())
    print(f"  celulas      {dif.size} comparadas, {total} divergentes")

    ok = not (len(so_a) or len(so_n) or faltando)
    for c in cols:
        k = int(dif[c].sum())
        if not k:
            continue
        nota = cfg.get("esperado", {}).get(c)
        marca = f"esperado — {nota}" if nota else "NAO PREVISTO"
        print(f"     {c}: {k} divergencias   [{marca}]")
        if not nota:
            ok = False
            for d in comum[dif[c]][:3]:
                print(f"        {d}  antiga={a.loc[d, c]!r}  nova={n.loc[d, c]!r}")
    return ok


def main() -> int:
    alvo = sys.argv[1] if len(sys.argv) > 1 else None
    eng = get_engine()
    tudo = True
    for nome, cfg in TABELAS.items():
        if alvo and nome != alvo:
            continue
        tudo &= confere(nome, cfg, eng)
    print()
    print("Migracao equivalente." if tudo else "HA DIVERGENCIA NAO PREVISTA.")
    return 0 if tudo else 1


if __name__ == "__main__":
    raise SystemExit(main())
