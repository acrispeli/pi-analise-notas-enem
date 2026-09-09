from pathlib import Path

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]

ARQUIVO_COMPETENCIAS = (
    RAIZ_PROJETO
    / "data"
    / "raw"
    / "2024"
    / "competencias_redacao"
    / "COMPETENCIAS_REDACAO_2024.csv"
)

COLUNAS_COMPETENCIAS = [
    "NU_NOTA_COMP1",
    "NU_NOTA_COMP2",
    "NU_NOTA_COMP3",
    "NU_NOTA_COMP4",
    "NU_NOTA_COMP5",
]


print("Carregando dados...")

dados = pd.read_csv(
    ARQUIVO_COMPETENCIAS,
    sep=";",
    encoding="latin-1",
    usecols=[
        "TP_STATUS_REDACAO",
        *COLUNAS_COMPETENCIAS,
    ],
)


# Seleciona apenas redações sem problemas
redacoes_validas = dados[
    dados["TP_STATUS_REDACAO"] == 1
].copy()


print("\n" + "=" * 75)
print("DISTRIBUIÇÃO DAS NOTAS POR COMPETÊNCIA")
print("=" * 75)


for competencia in COLUNAS_COMPETENCIAS:

    print("\n" + "-" * 75)
    print(competencia)
    print("-" * 75)

    frequencia = (
        redacoes_validas[competencia]
        .value_counts()
        .sort_index()
    )

    for nota, quantidade in frequencia.items():

        percentual = (
            quantidade
            / len(redacoes_validas)
            * 100
        )

        print(
            f"Nota {int(nota):3d}: "
            f"{quantidade:>9,} "
            f"({percentual:6.2f}%)"
        )