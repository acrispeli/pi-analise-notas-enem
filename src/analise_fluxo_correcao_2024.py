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


COLUNAS_COMP_AV1 = [
    "NU_NOTA_COMP1_AV1",
    "NU_NOTA_COMP2_AV1",
    "NU_NOTA_COMP3_AV1",
    "NU_NOTA_COMP4_AV1",
    "NU_NOTA_COMP5_AV1",
]

COLUNAS_COMP_AV2 = [
    "NU_NOTA_COMP1_AV2",
    "NU_NOTA_COMP2_AV2",
    "NU_NOTA_COMP3_AV2",
    "NU_NOTA_COMP4_AV2",
    "NU_NOTA_COMP5_AV2",
]


COLUNAS = [
    "TP_STATUS_REDACAO",
    "TP_STATUS_REDACAO_AV1",
    "TP_STATUS_REDACAO_AV2",
    "TP_STATUS_REDACAO_AV3",
    "TP_STATUS_REDACAO_AV4",
    "NU_NOTA_AV1",
    "NU_NOTA_AV2",
    "NU_NOTA_AV3",
    "NU_NOTA_AV4",
    "NU_NOTA_REDACAO",
    *COLUNAS_COMP_AV1,
    *COLUNAS_COMP_AV2,
]


print("Carregando dados dos avaliadores...")

dados = pd.read_csv(
    ARQUIVO_COMPETENCIAS,
    sep=";",
    encoding="latin-1",
    usecols=COLUNAS,
)


# ---------------------------------------------------------
# Redações com informação disponível
# ---------------------------------------------------------

redacoes = dados[
    dados["TP_STATUS_REDACAO"].notna()
].copy()


print("\n" + "=" * 75)
print("REDAÇÕES COM INFORMAÇÃO DE CORREÇÃO")
print("=" * 75)

print(f"Quantidade: {len(redacoes):,}")


# ---------------------------------------------------------
# Presença das etapas de avaliação
# ---------------------------------------------------------

tem_av1 = (
    redacoes["TP_STATUS_REDACAO_AV1"].notna()
    | redacoes["NU_NOTA_AV1"].notna()
)

tem_av2 = (
    redacoes["TP_STATUS_REDACAO_AV2"].notna()
    | redacoes["NU_NOTA_AV2"].notna()
)

tem_av3 = (
    redacoes["TP_STATUS_REDACAO_AV3"].notna()
    | redacoes["NU_NOTA_AV3"].notna()
)

tem_av4 = (
    redacoes["TP_STATUS_REDACAO_AV4"].notna()
    | redacoes["NU_NOTA_AV4"].notna()
)


print("\n" + "=" * 75)
print("ETAPAS DE AVALIAÇÃO")
print("=" * 75)

for nome, mascara in [
    ("AV1", tem_av1),
    ("AV2", tem_av2),
    ("AV3", tem_av3),
    ("AV4", tem_av4),
]:

    quantidade = mascara.sum()
    percentual = quantidade / len(redacoes) * 100

    print(
        f"{nome}: "
        f"{quantidade:,} "
        f"({percentual:.2f}%)"
    )


# ---------------------------------------------------------
# Discrepância entre AV1 e AV2
# ---------------------------------------------------------

diferenca_total = (
    redacoes["NU_NOTA_AV1"]
    - redacoes["NU_NOTA_AV2"]
).abs()


discrepancia_total = (
    redacoes["NU_NOTA_AV1"].notna()
    & redacoes["NU_NOTA_AV2"].notna()
    & (diferenca_total > 100)
)


discrepancia_competencia = pd.Series(
    False,
    index=redacoes.index,
)

for coluna_av1, coluna_av2 in zip(
    COLUNAS_COMP_AV1,
    COLUNAS_COMP_AV2,
):

    diferenca = (
        redacoes[coluna_av1]
        - redacoes[coluna_av2]
    ).abs()

    discrepancia_competencia |= (
        redacoes[coluna_av1].notna()
        & redacoes[coluna_av2].notna()
        & (diferenca > 80)
    )


discrepancia_status = (
    redacoes["TP_STATUS_REDACAO_AV1"].notna()
    & redacoes["TP_STATUS_REDACAO_AV2"].notna()
    & (
        redacoes["TP_STATUS_REDACAO_AV1"]
        != redacoes["TP_STATUS_REDACAO_AV2"]
    )
)


discrepancia_oficial = (
    discrepancia_total
    | discrepancia_competencia
    | discrepancia_status
)


print("\n" + "=" * 75)
print("DISCREPÂNCIA ENTRE AV1 E AV2")
print("=" * 75)

for descricao, mascara in [
    ("Diferença total superior a 100 pontos", discrepancia_total),
    (
        "Diferença superior a 80 pontos em alguma competência",
        discrepancia_competencia,
    ),
    ("Divergência de situação", discrepancia_status),
    ("Discrepância por pelo menos um critério", discrepancia_oficial),
]:

    quantidade = mascara.sum()
    percentual = quantidade / len(redacoes) * 100

    print(
        f"{descricao}: "
        f"{quantidade:,} "
        f"({percentual:.2f}%)"
    )


# ---------------------------------------------------------
# Conferência com a presença do terceiro avaliador
# ---------------------------------------------------------

print("\n" + "=" * 75)
print("VALIDAÇÃO DO FLUXO DE CORREÇÃO")
print("=" * 75)

print(
    "Discrepância identificada entre AV1 e AV2: "
    f"{discrepancia_oficial.sum():,}"
)

print(
    "Registros com AV3: "
    f"{tem_av3.sum():,}"
)

print(
    "Discrepância sem AV3: "
    f"{(discrepancia_oficial & ~tem_av3).sum():,}"
)

print(
    "AV3 sem discrepância identificada pelos critérios: "
    f"{(tem_av3 & ~discrepancia_oficial).sum():,}"
)

print(
    "Registros com AV4: "
    f"{tem_av4.sum():,}"
)

# ---------------------------------------------------------
# Investigação dos casos discrepantes sem AV3
# ---------------------------------------------------------

casos_sem_av3 = redacoes[
    discrepancia_oficial & ~tem_av3
].copy()


print("\n" + "=" * 75)
print("CASOS COM DISCREPÂNCIA IDENTIFICADA, MAS SEM AV3")
print("=" * 75)

print(f"Quantidade: {len(casos_sem_av3):,}")

if len(casos_sem_av3) > 0:

    colunas_exibir = [
        "TP_STATUS_REDACAO",
        "NU_NOTA_REDACAO",

        "TP_STATUS_REDACAO_AV1",
        "NU_NOTA_AV1",

        "TP_STATUS_REDACAO_AV2",
        "NU_NOTA_AV2",

        "TP_STATUS_REDACAO_AV3",
        "NU_NOTA_AV3",

        "TP_STATUS_REDACAO_AV4",
        "NU_NOTA_AV4",

        *COLUNAS_COMP_AV1,
        *COLUNAS_COMP_AV2,
    ]

    print(
        casos_sem_av3[colunas_exibir]
        .to_string(index=False)
    )