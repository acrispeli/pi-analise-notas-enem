from pathlib import Path
import json

import pandas as pd

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
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

PASTA_OUTPUTS = RAIZ_PROJETO / "outputs"

ARQUIVO_SAIDA = (
    PASTA_OUTPUTS
    / "avaliacao_kmeans_2024.json"
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
TAMANHO_AMOSTRA_SILHOUETTE = 10_000

VALORES_K = range(2, 7)


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

tamanho_amostra = min(
    TAMANHO_AMOSTRA,
    len(redacoes_validas),
)

amostra = redacoes_validas.sample(
    n=tamanho_amostra,
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
# Teste de diferentes valores de k
# ---------------------------------------------------------

resultados = []


print("\n" + "=" * 70)
print("AVALIAÇÃO DOS VALORES DE K")
print("=" * 70)


for k in VALORES_K:

    print(f"\nTestando k={k}...")

    modelo = KMeans(
        n_clusters=k,
        random_state=RANDOM_STATE,
        n_init=10,
    )

    rotulos = modelo.fit_predict(
        dados_padronizados
    )

    silhouette = silhouette_score(
        dados_padronizados,
        rotulos,
        sample_size=min(
            TAMANHO_AMOSTRA_SILHOUETTE,
            len(amostra),
        ),
        random_state=RANDOM_STATE,
    )

    resultados.append(
        {
            "k": k,
            "inercia": round(
                float(modelo.inertia_),
                2,
            ),
            "silhouette": round(
                float(silhouette),
                4,
            ),
        }
    )

    print(
        f"Inércia: "
        f"{modelo.inertia_:,.2f}"
    )

    print(
        f"Silhouette: "
        f"{silhouette:.4f}"
    )


# ---------------------------------------------------------
# Melhor silhouette observado
# ---------------------------------------------------------

melhor_resultado = max(
    resultados,
    key=lambda item: item["silhouette"],
)


print("\n" + "=" * 70)
print("MELHOR RESULTADO PELO SILHOUETTE")
print("=" * 70)

print(
    f"k = {melhor_resultado['k']}"
)

print(
    f"Silhouette = "
    f"{melhor_resultado['silhouette']}"
)


# ---------------------------------------------------------
# Exportação
# ---------------------------------------------------------

saida = {
    "ano": 2024,
    "experimento": "kmeans_competencias_redacao",
    "populacao": {
        "criterio": "TP_STATUS_REDACAO = 1",
        "total_redacoes_validas": int(
            len(redacoes_validas)
        ),
        "tamanho_amostra": int(
            len(amostra)
        ),
    },
    "variaveis": [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
    ],
    "pre_processamento": {
        "padronizacao": "StandardScaler",
        "random_state": RANDOM_STATE,
    },
    "avaliacao": resultados,
    "melhor_k_por_silhouette": int(
        melhor_resultado["k"]
    ),
}


PASTA_OUTPUTS.mkdir(
    parents=True,
    exist_ok=True,
)


with open(
    ARQUIVO_SAIDA,
    "w",
    encoding="utf-8",
) as arquivo:

    json.dump(
        saida,
        arquivo,
        ensure_ascii=False,
        indent=2,
    )


print("\nArquivo gerado:")
print(ARQUIVO_SAIDA)