# -*- coding: utf-8 -*-
r"""Diagnóstico somente leitura de divergências entre competências e redação.

Colocar opcionalmente em src/indicadores/diagnosticar_IND_009_2023.py.
Executar na raiz do repositório:
    .\.venv\Scripts\python.exe src\indicadores\diagnosticar_IND_009_2023.py

NÃO modifica bases, saídas, dashboards, ou microdados.
Não lê nem exibe NU_INSCRICAO, nomes ou outros identificadores.
Imprime somente valores de nota, UF de prova e posição no arquivo.
Não publicar registros individuais do diagnóstico no repositório.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

COMP = [f"NU_NOTA_COMP{i}" for i in range(1, 6)]
COLUNAS = ["SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO", *COMP]


def executar(raiz: Path, ano: int, bloco: int, max_exemplos: int) -> None:
    origem = (raiz / "data" / "raw" / str(ano) /
              (f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"))
    if not origem.is_file():
        raise FileNotFoundError(f"Microdados não encontrados em: {origem}")
    lidos = validas = completas = divergencias = 0
    incompletas = 0
    print(f"Diagnóstico IND-009 | ano {ano} | arquivo {origem.name}", flush=True)
    print("Somente leitura: nenhum arquivo será alterado.\n", flush=True)
    for parte in pd.read_csv(
        origem, sep=";", usecols=COLUNAS, dtype=str,
        keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    ):
        lidos += len(parte)
        status = parte["TP_STATUS_REDACAO"].str.strip()
        total = pd.to_numeric(
            parte["NU_NOTA_REDACAO"].str.strip().str.replace(",", ".", regex=False),
            errors="coerce",
        )
        filtro = status.eq("1") & total.notna() & total.between(0, 1000)
        validas += int(filtro.sum())
        if not filtro.any():
            continue
        textos = parte.loc[filtro, COMP].apply(lambda x: x.str.strip())
        competencias = textos.apply(lambda x: pd.to_numeric(
            x.str.replace(",", ".", regex=False), errors="coerce"))
        completas_mask = competencias.notna().all(axis=1) & competencias.ge(0).all(axis=1) & competencias.le(200).all(axis=1)
        completas += int(completas_mask.sum())
        incompletas += int((~completas_mask).sum())
        diferenca = competencias.sum(axis=1) - total.loc[filtro]
        diferentes = completas_mask & diferenca.abs().gt(1e-6)
        divergencias += int(diferentes.sum())
        for idx in diferenca.index[diferentes]:
            if divergencias == 0:
                continue
            if max_exemplos > 0:
                notas = [float(competencias.at[idx, c]) for c in COMP]
                print(
                    f"  Registro de dados #{int(idx)+1}: "
                    f"UF={parte.at[idx, 'SG_UF_PROVA']} | nota_total={total.at[idx]:g} | "
                    + " | ".join(f"C{i}={v:g}" for i, v in enumerate(notas, 1))
                    + f" | soma_C={sum(notas):g} | diferenca={diferenca.at[idx]:+g}",
                    flush=True,
                )
                max_exemplos -= 1
    print("\nRESULTADO DO DIAGNÓSTICO", flush=True)
    print(f"Registros lidos: {lidos:,}", flush=True)
    print(f"Redações válidas (POP_VALID): {validas:,}", flush=True)
    print(f"Válidas com cinco competências 0–200: {completas:,}", flush=True)
    print(f"Válidas com competências incompletas: {incompletas:,}", flush=True)
    print(f"Válidas com soma C1–C5 divergente: {divergencias:,}", flush=True)
    print("Nenhum arquivo foi escrito ou modificado.", flush=True)


def main() -> None:
    cli = argparse.ArgumentParser(description="Identificar diferenças entre notas de competências e nota total")
    cli.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    cli.add_argument("--ano", type=int, default=2023)
    cli.add_argument("--bloco", type=int, default=100_000)
    cli.add_argument("--max-exemplos", type=int, default=5)
    args = cli.parse_args()
    if args.bloco <= 0 or args.max_exemplos < 0:
        cli.error("--bloco deve ser >0 e --max-exemplos >=0")
    executar(args.raiz.resolve(), args.ano, args.bloco, args.max_exemplos)


if __name__ == "__main__":
    main()
