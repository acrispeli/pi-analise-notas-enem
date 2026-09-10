from pathlib import Path

import pandas as pd

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


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

NOMES_COMPETENCIAS = [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
]


RANDOM_STATE = 42
TAMANHO_AMOSTRA = 100_000


# ---------------------------------------------------------
# Carregamento
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Seleção das redações sem problemas
# ---------------------------------------------------------

redacoes_validas = (
    dados[
        dados["TP_STATUS_REDACAO"] == 1
    ]
    [COLUNAS_COMPETENCIAS]
    .dropna()
)


print(
    f"Redações disponíveis: "
    f"{len(redacoes_validas):,}"
)


# ---------------------------------------------------------
# Amostra reproduzível
# ---------------------------------------------------------

amostra = redacoes_validas.sample(
    n=min(
        TAMANHO_AMOSTRA,
        len(redacoes_validas),
    ),
    random_state=RANDOM_STATE,
)


print(
    f"Amostra utilizada: "
    f"{len(amostra):,}"
)


# ---------------------------------------------------------
# Padronização
# ---------------------------------------------------------

scaler = StandardScaler()

dados_padronizados = scaler.fit_transform(
    amostra
)


# ---------------------------------------------------------
# PCA
# ---------------------------------------------------------

pca = PCA(
    n_components=5
)

pca.fit(
    dados_padronizados
)


# ---------------------------------------------------------
# Variância explicada
# ---------------------------------------------------------

variancia = pd.DataFrame(
    {
        "Componente": [
            "PC1",
            "PC2",
            "PC3",
            "PC4",
            "PC5",
        ],
        "Variância explicada (%)": (
            pca.explained_variance_ratio_
            * 100
        ),
    }
)

variancia["Variância acumulada (%)"] = (
    variancia["Variância explicada (%)"]
    .cumsum()
)


print("\n" + "=" * 75)
print("VARIÂNCIA EXPLICADA")
print("=" * 75)

print(
    variancia.to_string(
        index=False,
        formatters={
            "Variância explicada (%)":
                lambda x: f"{x:.2f}%",
            "Variância acumulada (%)":
                lambda x: f"{x:.2f}%",
        },
    )
)


# ---------------------------------------------------------
# Pesos das competências em cada componente
# ---------------------------------------------------------

pesos = pd.DataFrame(
    pca.components_.T,
    index=NOMES_COMPETENCIAS,
    columns=[
        "PC1",
        "PC2",
        "PC3",
        "PC4",
        "PC5",
    ],
)


print("\n" + "=" * 75)
print("PESOS DAS COMPETÊNCIAS NAS COMPONENTES")
print("=" * 75)

print(
    pesos.round(4).to_string()
)


# ---------------------------------------------------------
# Competências com maior peso absoluto
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("MAIORES PESOS ABSOLUTOS POR COMPONENTE")
print("=" * 75)

for componente in pesos.columns:

    ranking = (
        pesos[componente]
        .abs()
        .sort_values(
            ascending=False
        )
    )

    print(f"\n{componente}")

    for competencia, peso_absoluto in ranking.items():

        peso_original = pesos.loc[
            competencia,
            componente,
        ]

        print(
            f"  {competencia}: "
            f"{peso_original:.4f}"
        )