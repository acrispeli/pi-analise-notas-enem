r"""Validação inicial dos registros dos CSVs públicos do ENEM (2019–2025).

Não faz cruzamentos entre arquivos, nem testa duplicidade de identificadores.
Executar na raiz do projeto:
    .\.venv\Scripts\python.exe src\preparacao\02_validacao_registros.py
"""

from collections import Counter
from pathlib import Path
import csv

import pandas as pd


RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data" / "raw"
SAIDA = RAIZ / "outputs"
TAMANHO_BLOCO = 100_000

ARQUIVOS = {
    **{
        ano: [f"MICRODADOS_ENEM_{ano}.csv", f"COMPETENCIAS_REDACAO_{ano}.csv"]
        for ano in range(2019, 2024)
    },
    2024: [
        "PARTICIPANTES_2024.csv",
        "RESULTADOS_2024.csv",
        "COMPETENCIAS_REDACAO_2024.csv",
        "ITENS_PROVA_2024.csv",
    ],
    2025: ["PARTICIPANTES_2025.csv", "RESULTADOS_2025.csv"],
}

LIMITES_NOTAS = {"NU_NOTA_REDACAO": (0, 1000)}
LIMITES_NOTAS.update({f"NU_NOTA_COMP{i}": (0, 200) for i in range(1, 6)})
CATEGORICAS = ("TP_STATUS_REDACAO", "TP_PRESENCA_LC")
CHAVES = ("NU_INSCRICAO", "NU_SEQUENCIAL")


def obter_cabecalho(caminho):
    # Apenas o cabeçalho, sem carregar dados na memória.
    with caminho.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        return [col.strip() for col in next(csv.reader(f, delimiter=";"))]


def gravar_csv(caminho, linhas, colunas):
    with caminho.open("w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)


def executar():
    SAIDA.mkdir(parents=True, exist_ok=True)
    resumo, notas, categorias = [], [], []

    for ano, nomes in ARQUIVOS.items():
        for nome in nomes:
            caminho = DADOS / str(ano) / nome
            print(f"\nAnalisando {ano} / {nome}", flush=True)

            if not caminho.is_file():
                resumo.append({
                    "ano": ano, "arquivo": nome, "registros": 0,
                    "chave": "", "chaves_vazias": "", "status": "ARQUIVO AUSENTE",
                })
                print("  Arquivo ausente.")
                continue

            try:
                cabecalho = obter_cabecalho(caminho)
                chaves_presentes = [c for c in CHAVES if c in cabecalho]
                campos_nota = [c for c in LIMITES_NOTAS if c in cabecalho]
                campos_cat = [c for c in CATEGORICAS if c in cabecalho]
                campos = chaves_presentes + campos_nota + campos_cat

                total = 0
                vazios_chave = Counter()
                dados_nota = {
                    campo: Counter({"vazias": 0, "nao_numericas": 0, "fora_faixa": 0})
                    for campo in campos_nota
                }
                frequencias = {campo: Counter() for campo in campos_cat}

                # O CSV completo é percorrido, mas só as colunas necessárias são lidas.
                # Caso não haja nenhuma coluna de interesse, uma coluna basta para contar linhas.
                if not campos:
                    campos = cabecalho[:1]

                blocos = pd.read_csv(
                    caminho,
                    sep=";",
                    usecols=campos,
                    dtype=str,
                    keep_default_na=False,
                    na_filter=False,
                    encoding="utf-8-sig",
                    encoding_errors="replace",
                    chunksize=TAMANHO_BLOCO,
                )

                for indice, bloco in enumerate(blocos, start=1):
                    total += len(bloco)

                    for chave in chaves_presentes:
                        vazios_chave[chave] += int(
                            bloco[chave].str.strip().eq("").sum()
                        )

                    for campo in campos_nota:
                        texto = bloco[campo].str.strip()
                        vazio = texto.eq("")
                        numero = pd.to_numeric(
                            texto.str.replace(",", ".", regex=False),
                            errors="coerce",
                        )
                        minimo, maximo = LIMITES_NOTAS[campo]
                        dados_nota[campo]["vazias"] += int(vazio.sum())
                        dados_nota[campo]["nao_numericas"] += int(
                            (numero.isna() & ~vazio).sum()
                        )
                        dados_nota[campo]["fora_faixa"] += int(
                            ((numero < minimo) | (numero > maximo)).sum()
                        )

                    for campo in campos_cat:
                        valores = bloco[campo].str.strip().replace("", "(vazio)")
                        frequencias[campo].update(valores.value_counts().to_dict())

                    if indice % 10 == 0:
                        print(f"  {total:,} linhas processadas...", flush=True)

                erros_notas = sum(
                    contagem["nao_numericas"] + contagem["fora_faixa"]
                    for contagem in dados_nota.values()
                )
                situacao = (
                    "REVISAR DADOS"
                    if sum(vazios_chave.values()) or erros_notas
                    else "OK"
                )
                resumo.append({
                    "ano": ano,
                    "arquivo": nome,
                    "registros": total,
                    "chave": ", ".join(chaves_presentes),
                    "chaves_vazias": sum(vazios_chave.values()),
                    "status": situacao,
                })

                for campo in campos_nota:
                    contagem = dados_nota[campo]
                    notas.append({
                        "ano": ano, "arquivo": nome, "variavel": campo,
                        "registros": total,
                        "vazias": contagem["vazias"],
                        "percentual_vazias": round(
                            100 * contagem["vazias"] / total, 2
                        ) if total else 0,
                        "nao_numericas": contagem["nao_numericas"],
                        "fora_faixa": contagem["fora_faixa"],
                    })

                for campo, contagens in frequencias.items():
                    for valor, quantidade in sorted(contagens.items()):
                        categorias.append({
                            "ano": ano, "arquivo": nome,
                            "variavel": campo, "valor": valor,
                            "quantidade": quantidade,
                        })

                print(f"  Concluído: {total:,} registros.", flush=True)

            except Exception as erro:
                resumo.append({
                    "ano": ano, "arquivo": nome, "registros": "",
                    "chave": "", "chaves_vazias": "", "status": f"ERRO: {erro}",
                })
                print(f"  ERRO ao ler o arquivo: {erro}", flush=True)

    gravar_csv(
        SAIDA / "validacao_registros_resumo.csv", resumo,
        ["ano", "arquivo", "registros", "chave", "chaves_vazias", "status"],
    )
    gravar_csv(
        SAIDA / "validacao_registros_notas.csv", notas,
        ["ano", "arquivo", "variavel", "registros", "vazias",
         "percentual_vazias", "nao_numericas", "fora_faixa"],
    )
    gravar_csv(
        SAIDA / "validacao_registros_categorias.csv", categorias,
        ["ano", "arquivo", "variavel", "valor", "quantidade"],
    )
    print("\nValidação concluída. Relatórios disponíveis em outputs/.")
    print("Atenção: a unicidade das chaves e os cruzamentos ainda não foram testados.")


if __name__ == "__main__":
    executar()
