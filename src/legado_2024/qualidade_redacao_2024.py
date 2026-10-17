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


STATUS_REDACAO = {
    1: "Sem problemas",
    2: "Anulada",
    3: "Cópia Texto Motivador",
    4: "Em Branco",
    6: "Fuga ao tema",
    7: "Não atendimento ao tipo textual",
    8: "Texto insuficiente",
    9: "Parte desconectada",
}


print("Carregando dados da redação...")

dados = pd.read_csv(
    ARQUIVO_COMPETENCIAS,
    sep=";",
    encoding="latin-1",
    usecols=COLUNAS,
)


# ---------------------------------------------------------
# Quantidade total
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("VISÃO GERAL")
print("=" * 70)

print(f"Total de registros: {len(dados):,}")


# ---------------------------------------------------------
# Situação das redações
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("SITUAÇÃO DAS REDAÇÕES")
print("=" * 70)

contagem_status = (
    dados["TP_STATUS_REDACAO"]
    .value_counts(dropna=False)
    .sort_index()
)

for codigo, quantidade in contagem_status.items():

    descricao = STATUS_REDACAO.get(codigo, "Sem informação de redação")

    percentual = quantidade / len(dados) * 100

    print(
        f"{codigo} - {descricao}: "
        f"{quantidade:,} ({percentual:.2f}%)"
    )


# ---------------------------------------------------------
# Valores ausentes
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("VALORES AUSENTES")
print("=" * 70)

for coluna in COLUNAS:

    ausentes = dados[coluna].isna().sum()

    percentual = ausentes / len(dados) * 100

    print(
        f"{coluna}: "
        f"{ausentes:,} ({percentual:.2f}%)"
    )


# ---------------------------------------------------------
# Redações sem problemas
# ---------------------------------------------------------

redacoes_validas = dados[
    dados["TP_STATUS_REDACAO"] == 1
]


print("\n" + "=" * 70)
print("REDAÇÕES SEM PROBLEMAS")
print("=" * 70)

print(
    f"Quantidade: {len(redacoes_validas):,}"
)

print(
    f"Percentual do total: "
    f"{len(redacoes_validas) / len(dados) * 100:.2f}%"
)


# ---------------------------------------------------------
# Faixas das notas
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("FAIXAS DAS NOTAS - REDAÇÕES SEM PROBLEMAS")
print("=" * 70)

for coluna in [
    *COLUNAS_COMPETENCIAS,
    "NU_NOTA_REDACAO",
]:

    minimo = redacoes_validas[coluna].min()
    maximo = redacoes_validas[coluna].max()
    media = redacoes_validas[coluna].mean()

    print(
        f"{coluna}: "
        f"mínimo={minimo}, "
        f"máximo={maximo}, "
        f"média={media:.2f}"
    )


# ---------------------------------------------------------
# Consistência da nota final
# ---------------------------------------------------------

dados_com_notas = dados.dropna(
    subset=[
        *COLUNAS_COMPETENCIAS,
        "NU_NOTA_REDACAO",
    ]
)

soma_competencias = dados_com_notas[
    COLUNAS_COMPETENCIAS
].sum(axis=1)

divergencias = (
    soma_competencias
    != dados_com_notas["NU_NOTA_REDACAO"]
).sum()


print("\n" + "=" * 70)
print("CONSISTÊNCIA DA NOTA FINAL")
print("=" * 70)

print(
    f"Registros com todas as notas disponíveis: "
    f"{len(dados_com_notas):,}"
)

print(
    "Registros em que a soma das cinco competências "
    "difere da nota final: "
    f"{divergencias:,}"
)