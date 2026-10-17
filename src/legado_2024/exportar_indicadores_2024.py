from pathlib import Path
import json

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

PASTA_OUTPUTS = RAIZ_PROJETO / "outputs"

ARQUIVO_SAIDA = (
    PASTA_OUTPUTS
    / "indicadores_2024.json"
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
# Populações
# ---------------------------------------------------------

com_informacao = dados[
    dados["TP_STATUS_REDACAO"].notna()
]

redacoes_validas = dados[
    dados["TP_STATUS_REDACAO"] == 1
]


# ---------------------------------------------------------
# Estatísticas da redação
# ---------------------------------------------------------

nota_redacao = {
    "media": round(
        float(redacoes_validas["NU_NOTA_REDACAO"].mean()),
        2,
    ),
    "mediana": round(
        float(redacoes_validas["NU_NOTA_REDACAO"].median()),
        2,
    ),
    "minimo": int(
        redacoes_validas["NU_NOTA_REDACAO"].min()
    ),
    "maximo": int(
        redacoes_validas["NU_NOTA_REDACAO"].max()
    ),
}


# ---------------------------------------------------------
# Estatísticas das competências
# ---------------------------------------------------------

competencias = []

for numero, coluna in enumerate(
    COLUNAS_COMPETENCIAS,
    start=1,
):

    competencias.append(
        {
            "competencia": f"C{numero}",
            "media": round(
                float(redacoes_validas[coluna].mean()),
                2,
            ),
            "mediana": round(
                float(redacoes_validas[coluna].median()),
                2,
            ),
        }
    )


# ---------------------------------------------------------
# Objeto final
# ---------------------------------------------------------

indicadores = {
    "ano": 2024,

    "populacao": {
        "total_participantes": len(dados),
        "com_informacao_redacao": len(com_informacao),
        "redacoes_sem_problemas": len(redacoes_validas),
    },

    "nota_redacao": nota_redacao,

    "competencias": competencias,
}


# ---------------------------------------------------------
# Exportação
# ---------------------------------------------------------

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
        indicadores,
        arquivo,
        ensure_ascii=False,
        indent=2,
    )


print("\nArquivo gerado com sucesso:")
print(ARQUIVO_SAIDA)