from pathlib import Path

import pandas as pd

from sklearn.cluster import KMeans
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


RANDOM_STATE = 42
TAMANHO_AMOSTRA = 100_000
K = 2


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
        "NU_NOTA_REDACAO",
    ],
)


redacoes_validas = (
    dados[
        dados["TP_STATUS_REDACAO"] == 1
    ]
    .dropna(
        subset=[
            *COLUNAS_COMPETENCIAS,
            "NU_NOTA_REDACAO",
        ]
    )
    .copy()
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
).copy()


# ---------------------------------------------------------
# Padronização e K-Means
# ---------------------------------------------------------

scaler = StandardScaler()

dados_padronizados = scaler.fit_transform(
    amostra[COLUNAS_COMPETENCIAS]
)


modelo = KMeans(
    n_clusters=K,
    random_state=RANDOM_STATE,
    n_init=10,
)


amostra["cluster"] = modelo.fit_predict(
    dados_padronizados
)


# ---------------------------------------------------------
# Centros na escala original
# ---------------------------------------------------------

centros_originais = scaler.inverse_transform(
    modelo.cluster_centers_
)


centros = pd.DataFrame(
    centros_originais,
    columns=[
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
    ],
)


print("\n" + "=" * 75)
print("CENTROS DOS CLUSTERS")
print("=" * 75)

print(
    centros.round(2).to_string()
)


# ---------------------------------------------------------
# Tamanho dos clusters
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("TAMANHO DOS CLUSTERS")
print("=" * 75)


contagem = (
    amostra["cluster"]
    .value_counts()
    .sort_index()
)


for cluster, quantidade in contagem.items():

    percentual = (
        quantidade
        / len(amostra)
        * 100
    )

    print(
        f"Cluster {cluster}: "
        f"{quantidade:,} "
        f"({percentual:.2f}%)"
    )


# ---------------------------------------------------------
# Nota total por cluster
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("NOTA DA REDAÇÃO POR CLUSTER")
print("=" * 75)


resumo_nota = (
    amostra
    .groupby("cluster")["NU_NOTA_REDACAO"]
    .agg(
        quantidade="count",
        media="mean",
        mediana="median",
        minimo="min",
        maximo="max",
    )
)


print(
    resumo_nota.round(2).to_string()
)


# ---------------------------------------------------------
# Médias observadas por competência
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("MÉDIAS DAS COMPETÊNCIAS POR CLUSTER")
print("=" * 75)


medias = (
    amostra
    .groupby("cluster")[COLUNAS_COMPETENCIAS]
    .mean()
)


medias.columns = [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
]


print(
    medias.round(2).to_string()
)