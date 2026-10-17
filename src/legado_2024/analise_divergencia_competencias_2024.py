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


COMPETENCIAS = {
    "C1": (
        "NU_NOTA_COMP1_AV1",
        "NU_NOTA_COMP1_AV2",
    ),
    "C2": (
        "NU_NOTA_COMP2_AV1",
        "NU_NOTA_COMP2_AV2",
    ),
    "C3": (
        "NU_NOTA_COMP3_AV1",
        "NU_NOTA_COMP3_AV2",
    ),
    "C4": (
        "NU_NOTA_COMP4_AV1",
        "NU_NOTA_COMP4_AV2",
    ),
    "C5": (
        "NU_NOTA_COMP5_AV1",
        "NU_NOTA_COMP5_AV2",
    ),
}


COLUNAS_NOTAS = [
    coluna
    for par in COMPETENCIAS.values()
    for coluna in par
]


COLUNAS = [
    "TP_STATUS_REDACAO_AV1",
    "TP_STATUS_REDACAO_AV2",
    *COLUNAS_NOTAS,
]


print("Carregando dados...")

dados = pd.read_csv(
    ARQUIVO_COMPETENCIAS,
    sep=";",
    encoding="latin-1",
    usecols=COLUNAS,
)


# ---------------------------------------------------------
# Seleção da população comparável
# ---------------------------------------------------------

comparaveis = dados[
    (dados["TP_STATUS_REDACAO_AV1"] == 1)
    & (dados["TP_STATUS_REDACAO_AV2"] == 1)
].dropna(
    subset=COLUNAS_NOTAS
).copy()


print("\n" + "=" * 80)
print("POPULAÇÃO COMPARÁVEL")
print("=" * 80)

print(
    "Redações com AV1 e AV2 classificados como "
    f"'sem problemas': {len(comparaveis):,}"
)


# ---------------------------------------------------------
# Resumo das diferenças
# ---------------------------------------------------------

resultados = []


for competencia, (coluna_av1, coluna_av2) in COMPETENCIAS.items():

    diferenca = (
        comparaveis[coluna_av1]
        - comparaveis[coluna_av2]
    ).abs()

    quantidade = len(diferenca)

    resultados.append(
        {
            "Competência": competencia,
            "Diferença média": diferenca.mean(),
            "Diferença mediana": diferenca.median(),
            "Concordância exata (%)": (
                (diferenca == 0).mean() * 100
            ),
            "Diferença até 40 (%)": (
                (diferenca <= 40).mean() * 100
            ),
            "Diferença 80 (%)": (
                (diferenca == 80).mean() * 100
            ),
            "Diferença > 80": (
                (diferenca > 80).sum()
            ),
            "Diferença > 80 (%)": (
                (diferenca > 80).mean() * 100
            ),
            "Máxima diferença": diferenca.max(),
        }
    )


resumo = pd.DataFrame(resultados)


print("\n" + "=" * 80)
print("DIVERGÊNCIA ENTRE AV1 E AV2 POR COMPETÊNCIA")
print("=" * 80)

print(
    resumo.to_string(
        index=False,
        formatters={
            "Diferença média": lambda x: f"{x:.2f}",
            "Diferença mediana": lambda x: f"{x:.0f}",
            "Concordância exata (%)": lambda x: f"{x:.2f}%",
            "Diferença até 40 (%)": lambda x: f"{x:.2f}%",
            "Diferença 80 (%)": lambda x: f"{x:.2f}%",
            "Diferença > 80": lambda x: f"{x:,.0f}",
            "Diferença > 80 (%)": lambda x: f"{x:.2f}%",
            "Máxima diferença": lambda x: f"{x:.0f}",
        },
    )
)


# ---------------------------------------------------------
# Ranking pela diferença média
# ---------------------------------------------------------

ranking_media = resumo.sort_values(
    "Diferença média",
    ascending=False,
)


print("\n" + "=" * 80)
print("RANKING POR DIFERENÇA MÉDIA")
print("=" * 80)

for _, linha in ranking_media.iterrows():

    print(
        f"{linha['Competência']}: "
        f"{linha['Diferença média']:.2f} pontos"
    )


# ---------------------------------------------------------
# Ranking pela discrepância oficial por competência
# ---------------------------------------------------------

ranking_discrepancia = resumo.sort_values(
    "Diferença > 80 (%)",
    ascending=False,
)


print("\n" + "=" * 80)
print("RANKING POR DIFERENÇA SUPERIOR A 80 PONTOS")
print("=" * 80)

for _, linha in ranking_discrepancia.iterrows():

    print(
        f"{linha['Competência']}: "
        f"{int(linha['Diferença > 80']):,} "
        f"({linha['Diferença > 80 (%)']:.2f}%)"
    )


# ---------------------------------------------------------
# Distribuição das diferenças
# ---------------------------------------------------------

print("\n" + "=" * 80)
print("DISTRIBUIÇÃO DAS DIFERENÇAS")
print("=" * 80)


for competencia, (coluna_av1, coluna_av2) in COMPETENCIAS.items():

    diferenca = (
        comparaveis[coluna_av1]
        - comparaveis[coluna_av2]
    ).abs()

    distribuicao = (
        diferenca
        .value_counts()
        .sort_index()
    )

    print(f"\n{competencia}")

    for valor, quantidade in distribuicao.items():

        percentual = (
            quantidade
            / len(diferenca)
            * 100
        )

        print(
            f"  {int(valor):3d} pontos: "
            f"{quantidade:>9,} "
            f"({percentual:6.2f}%)"
        )