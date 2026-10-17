from pathlib import Path

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]

ARQUIVO_PARTICIPANTES = (
    RAIZ_PROJETO
    / "data"
    / "raw"
    / "2024"
    / "microdados"
    / "PARTICIPANTES_2024.csv"
)

ARQUIVO_COMPETENCIAS = (
    RAIZ_PROJETO
    / "data"
    / "raw"
    / "2024"
    / "competencias_redacao"
    / "COMPETENCIAS_REDACAO_2024.csv"
)


def carregar_inscricoes(caminho):
    """Carrega apenas a coluna NU_INSCRICAO."""
    return pd.read_csv(
        caminho,
        sep=";",
        encoding="latin-1",
        usecols=["NU_INSCRICAO"],
        dtype={"NU_INSCRICAO": "int64"},
    )


print("Carregando inscrições dos participantes...")
participantes = carregar_inscricoes(ARQUIVO_PARTICIPANTES)

print("Carregando inscrições das competências da redação...")
competencias = carregar_inscricoes(ARQUIVO_COMPETENCIAS)


# ---------------------------------------------------------
# Validação individual das bases
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("PARTICIPANTES")
print("=" * 70)

print(f"Total de registros: {len(participantes):,}")
print(
    f"Inscrições únicas: "
    f"{participantes['NU_INSCRICAO'].nunique():,}"
)
print(
    f"Inscrições duplicadas: "
    f"{participantes['NU_INSCRICAO'].duplicated().sum():,}"
)
print(
    f"Valores ausentes: "
    f"{participantes['NU_INSCRICAO'].isna().sum():,}"
)


print("\n" + "=" * 70)
print("COMPETÊNCIAS DA REDAÇÃO")
print("=" * 70)

print(f"Total de registros: {len(competencias):,}")
print(
    f"Inscrições únicas: "
    f"{competencias['NU_INSCRICAO'].nunique():,}"
)
print(
    f"Inscrições duplicadas: "
    f"{competencias['NU_INSCRICAO'].duplicated().sum():,}"
)
print(
    f"Valores ausentes: "
    f"{competencias['NU_INSCRICAO'].isna().sum():,}"
)


# ---------------------------------------------------------
# Correspondência entre as bases
# ---------------------------------------------------------

competencias_em_participantes = competencias["NU_INSCRICAO"].isin(
    participantes["NU_INSCRICAO"]
)

participantes_em_competencias = participantes["NU_INSCRICAO"].isin(
    competencias["NU_INSCRICAO"]
)


print("\n" + "=" * 70)
print("CORRESPONDÊNCIA ENTRE AS BASES")
print("=" * 70)

print(
    "Registros de competências encontrados em participantes: "
    f"{competencias_em_participantes.sum():,}"
)

print(
    "Registros de competências sem participante correspondente: "
    f"{(~competencias_em_participantes).sum():,}"
)

print(
    "Participantes encontrados na base de competências: "
    f"{participantes_em_competencias.sum():,}"
)

print(
    "Participantes sem registro na base de competências: "
    f"{(~participantes_em_competencias).sum():,}"
)