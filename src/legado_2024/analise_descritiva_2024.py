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

COLUNAS = [
    "TP_STATUS_REDACAO",
    *COLUNAS_COMPETENCIAS,
    "NU_NOTA_REDACAO",
]


print("Carregando dados...")

dados = pd.read_csv(
    ARQUIVO_COMPETENCIAS,
    sep=";",
    encoding="latin-1",
    usecols=COLUNAS,
)


# ---------------------------------------------------------
# Seleção das redações sem problemas
# ---------------------------------------------------------

redacoes_validas = dados[
    dados["TP_STATUS_REDACAO"] == 1
].copy()


print("\n" + "=" * 75)
print("POPULAÇÃO ANALISADA")
print("=" * 75)

print(
    f"Redações sem problemas: "
    f"{len(redacoes_validas):,}"
)


# ---------------------------------------------------------
# Estatísticas descritivas
# ---------------------------------------------------------

resumo = redacoes_validas[
    COLUNAS_COMPETENCIAS
].agg(
    [
        "count",
        "mean",
        "median",
        "std",
        "min",
        "max",
    ]
).T


resumo.columns = [
    "Quantidade",
    "Média",
    "Mediana",
    "Desvio padrão",
    "Mínimo",
    "Máximo",
]


print("\n" + "=" * 75)
print("ESTATÍSTICAS DAS COMPETÊNCIAS")
print("=" * 75)

print(
    resumo.to_string(
        formatters={
            "Quantidade": lambda x: f"{x:,.0f}",
            "Média": lambda x: f"{x:.2f}",
            "Mediana": lambda x: f"{x:.2f}",
            "Desvio padrão": lambda x: f"{x:.2f}",
            "Mínimo": lambda x: f"{x:.0f}",
            "Máximo": lambda x: f"{x:.0f}",
        }
    )
)


# ---------------------------------------------------------
# Competências ordenadas pela média
# ---------------------------------------------------------

medias = (
    redacoes_validas[COLUNAS_COMPETENCIAS]
    .mean()
    .sort_values()
)


print("\n" + "=" * 75)
print("COMPETÊNCIAS ORDENADAS DA MENOR PARA A MAIOR MÉDIA")
print("=" * 75)

for competencia, media in medias.items():
    print(
        f"{competencia}: {media:.2f}"
    )


# ---------------------------------------------------------
# Valores de nota existentes em cada competência
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("VALORES DE NOTA OBSERVADOS")
print("=" * 75)

for competencia in COLUNAS_COMPETENCIAS:

    valores = sorted(
        redacoes_validas[competencia]
        .dropna()
        .unique()
    )

    print(
        f"{competencia}: "
        f"{valores}"
    )