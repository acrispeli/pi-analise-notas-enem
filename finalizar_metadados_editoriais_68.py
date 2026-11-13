#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fechamento dos metadados editoriais dos 68 indicadores do Streamlit.

Uso:
  python finalizar_metadados_editoriais_68.py           # prévia, sem alterações
  python finalizar_metadados_editoriais_68.py --aplicar # atualiza fontes locais
  python finalizar_metadados_editoriais_68.py --verificar

Altera apenas o TEXTO dos valores de campos status, data_status e review
explicitamente enumerados. Preserva indicadores, valores, registros, filtros,
dicionários, metodologia e a estrutura do JSON. O novo estado significa
consolidação PARA APRESENTAÇÃO; não equivale a validação acadêmica independente.
O histórico de processamento anterior permanece no Git.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

BRANCH_PERMITIDA = "fix/qualidade-visual-streamlit"
ESTADO_EDITORIAL = b"consolidado_para_apresentacao"
REVISAO_EDITORIAL = b"aprovacao_editorial_pelo_responsavel"

PADRAO = re.compile(
    rb'(?P<prefix>"(?P<campo>status|data_status|review)"\s*:\s*")'
    rb'(?P<valor>draft|rascunho|pendente_revisao_academica_e_privacidade_contextual)'
    rb'(?P<suffix>")',
    flags=re.IGNORECASE,
)


def ajustar_conteudo(conteudo: bytes) -> tuple[bytes, Counter]:
    """Substituição cirúrgica; nenhuma nota ou valor estatístico é modificado."""
    contagens: Counter = Counter()

    def substituir(match: re.Match[bytes]) -> bytes:
        campo = match.group("campo").lower()
        valor = match.group("valor").lower()
        novo = None
        if campo in (b"status", b"data_status") and valor in (b"draft", b"rascunho"):
            novo = ESTADO_EDITORIAL
            contagens["status_rascunho"] += 1
        elif campo == b"review" and valor == b"pendente_revisao_academica_e_privacidade_contextual":
            novo = REVISAO_EDITORIAL
            contagens["revisao_editorial"] += 1
        return (match.group("prefix") + novo + match.group("suffix")) if novo else match.group(0)

    ajustado = PADRAO.sub(substituir, conteudo)
    return ajustado, contagens


def fontes_publicas(raiz: Path) -> list[Path]:
    base = raiz / "outputs" / "json"
    if not base.is_dir():
        raise FileNotFoundError(f"Diretório de resultados inexistente: {base}")
    return sorted(set(base.glob("IND_[0-9][0-9][0-9]_*.json")) |
                  set(base.glob("dashboard_enem_*.json")))


def conferir_branch(raiz: Path) -> None:
    p = subprocess.run(["git", "branch", "--show-current"], cwd=raiz,
                       capture_output=True, text=True, check=True)
    atual = p.stdout.strip()
    if atual != BRANCH_PERMITIDA:
        raise RuntimeError(f"Branch atual {atual!r}; esperada {BRANCH_PERMITIDA!r}. "
                           "A main não será alterada.")


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    destino_temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=caminho.parent,
                                         prefix=".fechamento_", suffix=".json",
                                         delete=False) as f:
            destino_temporario = Path(f.name)
            f.write(conteudo)
        os.replace(destino_temporario, caminho)
    finally:
        if destino_temporario and destino_temporario.exists():
            destino_temporario.unlink()


def executar(raiz: Path, aplicar: bool = False) -> tuple[int, Counter]:
    arquivos = fontes_publicas(raiz)
    if not arquivos:
        raise ValueError("Nenhum JSON IND ou dashboard foi localizado")
    if aplicar:
        conferir_branch(raiz)

    totals: Counter = Counter()
    alterados = 0
    for path in arquivos:
        original = path.read_bytes()
        ajustado, contagem = ajustar_conteudo(original)
        if original == ajustado:
            continue
        # Impede converter um arquivo JSON corrompido em uma saída publicável.
        json.loads(original.decode("utf-8-sig"))
        json.loads(ajustado.decode("utf-8-sig"))
        alterados += 1
        totals.update(contagem)
        print(f"{'Atualizado' if aplicar else 'Prévia':10} {path.relative_to(raiz)} "
              f"(status: {contagem['status_rascunho']}; revisão: {contagem['revisao_editorial']})")
        if aplicar:
            gravar_atomico(path, ajustado)
    print(f"Arquivos examinados: {len(arquivos)}; com ajustes: {alterados}.")
    print("Status de rascunho substituídos:", totals["status_rascunho"])
    print("Revisões editoriais registradas:", totals["revisao_editorial"])
    if not aplicar and alterados:
        print("Prévia apenas: execute com --aplicar para gravar os metadados.")
    return alterados, totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--aplicar", action="store_true", help="Aplicar ajustes na branch de trabalho")
    modo.add_argument("--verificar", action="store_true", help="Falhar se houver estados editoriais antigos")
    ap.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    try:
        alterados, _ = executar(args.raiz.resolve(), args.aplicar)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError,
            json.JSONDecodeError) as exc:
        print(f"ERRO no fechamento: {exc}")
        return 2
    if args.verificar and alterados:
        print("FALHA: existem metadados de rascunho ou revisão antiga nesta instalação.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
