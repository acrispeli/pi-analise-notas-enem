from pathlib import Path

import pandas as pd


# Caminho da raiz do projeto
RAIZ_PROJETO = Path(__file__).resolve().parents[1]

# Arquivos que serão inspecionados
arquivos = {
    "Participantes": (
        RAIZ_PROJETO
        / "data"
        / "raw"
        / "2024"
        / "microdados"
        / "PARTICIPANTES_2024.csv"
    ),
    "Competências da redação": (
        RAIZ_PROJETO
        / "data"
        / "raw"
        / "2024"
        / "competencias_redacao"
        / "COMPETENCIAS_REDACAO_2024.csv"
    ),
}


for nome, caminho in arquivos.items():
    print("=" * 80)
    print(nome)
    print("=" * 80)

    dados = pd.read_csv(
        caminho,
        sep=";",
        encoding="latin-1",
        nrows=5,
    )

    print(f"Arquivo: {caminho.name}")
    print(f"Quantidade de colunas: {len(dados.columns)}")

    print("\nColunas:")
    for coluna in dados.columns:
        print(f"- {coluna}")

    print("\nPrimeiros 5 registros:")
    print(dados.head())

    print()