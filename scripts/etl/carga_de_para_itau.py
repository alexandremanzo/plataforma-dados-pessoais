"""
Carrega a planilha de revisao preenchida no de-para de categorias.

Le revisao-categorias-itau.xlsx, aproveita apenas as linhas em que
AREA, CATEGORIA ou GRUPO foram preenchidas a mao, e grava em
silver.de_para_categoria_itau.

As colunas SUGESTAO_* sao ignoradas de proposito: elas existem so
como referencia visual na planilha. Se voce concordou com a sugestao,
precisa te-la copiado para a coluna definitiva - assim nunca ha duvida
sobre o que foi decidido por voce e o que foi palpite do sistema.

Depois desta carga, rode carga_silver_itau.py para aplicar os rotulos.

Uso:
    python carga_de_para_itau.py
    python carga_de_para_itau.py --listar   # mostra o que ja esta carregado
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conf"))
from config_db import PATH_DADOS_ORIGEM, get_engine  # noqa: E402

ARQUIVO = "revisao-categorias-itau.xlsx"
ABA = "padroes"
TABELA = "de_para_categoria_itau"


def _limpa(valor):
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return None
    return str(valor).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga do de-para de categorias Itau")
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    engine = get_engine()

    if args.listar:
        print(pd.read_sql("""
            SELECT ds_padrao, ds_area, ds_categoria, ds_grupo,
                   nr_ocorrencias, vl_volume
            FROM silver.de_para_categoria_itau ORDER BY vl_volume DESC
        """, engine).to_string(index=False))
        return 0

    caminho = PATH_DADOS_ORIGEM / ARQUIVO
    if not caminho.exists():
        print(f"ERRO: {caminho} nao encontrado. "
              f"Rode exporta_revisao_itau.py primeiro.")
        return 1

    df = pd.read_excel(caminho, sheet_name=ABA)
    faltando = [c for c in ("PADRAO", "AREA", "CATEGORIA", "GRUPO")
                if c not in df.columns]
    if faltando:
        print(f"ERRO: colunas ausentes na planilha: {faltando}")
        return 1

    for col in ("AREA", "CATEGORIA", "GRUPO"):
        df[col] = df[col].map(_limpa)

    preenchidas = df[df[["AREA", "CATEGORIA", "GRUPO"]].notna().any(axis=1)].copy()

    print(f"Planilha: {len(df)} padroes | {len(preenchidas)} preenchidos")
    if preenchidas.empty:
        print("\nNenhum padrao foi rotulado ainda. Preencha as colunas AREA,")
        print("CATEGORIA e GRUPO na planilha e rode de novo.")
        print(f"\n  {caminho}")
        return 0

    novo = pd.DataFrame({
        "ds_padrao": preenchidas["PADRAO"].astype(str).str.strip(),
        "ds_area": preenchidas["AREA"],
        "ds_categoria": preenchidas["CATEGORIA"],
        "ds_grupo": preenchidas["GRUPO"],
        "nr_ocorrencias": preenchidas.get("OCORRENCIAS"),
        "vl_volume": preenchidas.get("VOLUME_ABS"),
    }).drop_duplicates(subset="ds_padrao", keep="last")

    # Substituicao completa: a planilha e a fonte da verdade do de-para,
    # entao apagar um rotulo la deve apaga-lo aqui tambem.
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM silver.{TABELA}"))
        novo.to_sql(TABELA, conn, schema="silver", if_exists="append", index=False)

    print(f"\nGravados {len(novo)} padroes em silver.{TABELA}")
    cobertura = novo["vl_volume"].sum() if "vl_volume" in novo else 0
    print(f"Volume coberto pelos rotulos: R$ {cobertura:,.2f}")
    print("\nAgora rode carga_silver_itau.py para aplicar aos lancamentos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
