
from pathlib import Path
import csv

# Localiza automaticamente a raiz do projeto
RAIZ = Path(__file__).resolve().parents[2]

DADOS = RAIZ / "data" / "raw"
SAIDA = RAIZ / "outputs" / "inventario_bases.csv"

# Quantidades previstas nos dicionarios do INEP
ESPERADOS = {}

for ano in range(2019, 2024):
    ESPERADOS[ano] = {
        f"MICRODADOS_ENEM_{ano}.csv": (76, "NU_INSCRICAO"),
        f"COMPETENCIAS_REDACAO_{ano}.csv": (37, "NU_INSCRICAO"),
    }

ESPERADOS[2024] = {
    "PARTICIPANTES_2024.csv": (38, "NU_INSCRICAO"),
    "RESULTADOS_2024.csv": (42, "NU_SEQUENCIAL"),
    "COMPETENCIAS_REDACAO_2024.csv": (37, "NU_INSCRICAO"),
    "ITENS_PROVA_2024.csv": (14, None),
}

ESPERADOS[2025] = {
    "PARTICIPANTES_2025.csv": (38, "NU_INSCRICAO"),
    "RESULTADOS_2025.csv": (70, "NU_SEQUENCIAL"),
}


def ler_colunas(caminho):
    """Le apenas o cabecalho, sem carregar o CSV inteiro."""
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            with caminho.open(
                "r", encoding=codificacao, newline=""
            ) as arquivo:
                colunas = next(csv.reader(arquivo, delimiter=";"))
            return [coluna.strip() for coluna in colunas]
        except UnicodeDecodeError:
            continue

    raise ValueError("Nao foi possivel ler o cabecalho")


def realizar_inventario():
    registros = []

    for ano, arquivos in ESPERADOS.items():
        print(f"\n{'=' * 45}")
        print(f"ENEM {ano}")
        print("=" * 45)

        for nome, (quantidade_prevista, chave) in arquivos.items():
            caminho = DADOS / str(ano) / nome

            registro = {
                "ano": ano,
                "arquivo": nome,
                "tamanho_mb": "",
                "colunas_encontradas": 0,
                "colunas_previstas": quantidade_prevista,
                "chave": chave or "",
                "situacao": "",
            }

            if not caminho.is_file():
                registro["situacao"] = "ARQUIVO AUSENTE"
            else:
                try:
                    colunas = ler_colunas(caminho)

                    registro["tamanho_mb"] = round(
                        caminho.stat().st_size / (1024 ** 2), 2
                    )
                    registro["colunas_encontradas"] = len(colunas)

                    if len(colunas) != quantidade_prevista:
                        registro["situacao"] = "REVISAR COLUNAS"
                    elif chave and chave not in colunas:
                        registro["situacao"] = "REVISAR CHAVE"
                    else:
                        registro["situacao"] = "OK"

                except Exception as erro:
                    registro["situacao"] = f"ERRO: {erro}"

            registros.append(registro)

            print(f"{nome}: {registro['situacao']}")
            print(
                f"  Colunas: {registro['colunas_encontradas']}"
                f" / {quantidade_prevista}"
            )

    SAIDA.parent.mkdir(parents=True, exist_ok=True)

    with SAIDA.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=list(registros[0].keys()),
            delimiter=";"
        )
        escritor.writeheader()
        escritor.writerows(registros)

    print("\nInventario concluido!")
    print(f"Relatorio salvo em: {SAIDA}")


if __name__ == "__main__":
    realizar_inventario()
