#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria de prontidão do Streamlit (68 indicadores, somente leitura).

Uso: python auditar_streamlit_entrega.py
Não recalcula notas, não manipula microdados e não altera JSONs do projeto.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from painel_paginas_contrato_68 import ler_catalogo, fontes_indicador
from publicacao_segura_v2 import PERFIS_V2, preparar_doc_publico_v2

CAMPOS = [
    "indicador", "pagina", "titulo", "estado", "fonte_principal",
    "variantes", "status_dados", "publicacao_autorizada",
    "pendencia_catalogo", "observacoes",
    "revisao_academica_pendente", "linhas_omitidas_publicacao",
]


def auditar_indicador(raiz: Path, indicador: dict) -> dict:
    """Confere presença, sintaxe, ID declarado e sinalizações da fonte."""
    numero = int(indicador["numero"])
    codigo = f"IND-{numero:03d}"
    row = {
        "indicador": codigo,
        "pagina": indicador["pagina"],
        "titulo": indicador["titulo"],
        "estado": "OK",
        "fonte_principal": "",
        "variantes": 0,
        "status_dados": "",
        "publicacao_autorizada": "",
        "pendencia_catalogo": "",
        "observacoes": "",
        "revisao_academica_pendente": "",
        "linhas_omitidas_publicacao": 0,
    }
    restricao = str(indicador.get("restricoes") or "")
    if re.search(r"\b(?:confirmar|pendente|pendentes|revisão|revisao)\b", restricao.casefold()):
        row["pendencia_catalogo"] = restricao

    fontes = fontes_indicador(raiz, numero)
    row["variantes"] = len(fontes)
    if not fontes:
        row["estado"] = "ERRO"
        row["observacoes"] = "Fonte JSON não encontrada pelo mesmo seletor do Streamlit"
        return row

    principal = fontes[0]
    row["fonte_principal"] = principal.relative_to(raiz).as_posix()
    try:
        with principal.open(encoding="utf-8-sig") as f:
            doc = json.load(f)
        if not isinstance(doc, dict) or not doc:
            raise ValueError("A fonte deve conter um objeto JSON não vazio")
        metadados = doc.get("meta")
        if not isinstance(metadados, dict):
            metadados = {}
        # JSONs de perfis V2 declaram o estado em "status" na raiz.
        # Também preservamos os formatos meta.data_status/data_status.
        status = (metadados.get("data_status") or doc.get("data_status") or
                  doc.get("status") or "")
        row["status_dados"] = str(status) if isinstance(status, str) else ""

        autorizado = doc.get("publicacao_autorizada")
        if isinstance(autorizado, bool):
            row["publicacao_autorizada"] = str(autorizado).lower()

        declarado = (metadados.get("indicator_id") or doc.get("indicator_id") or
                     (doc["indicator"].get("id") if isinstance(doc.get("indicator"), dict)
                      else None))
        if declarado and str(declarado).upper() != codigo:
            row["estado"] = "ERRO"
            row["observacoes"] = f"ID da fonte {declarado!r} difere de {codigo}"
        elif status and str(status).casefold() in {"draft", "rascunho"}:
            row["observacoes"] = "Metadados da fonte declaram processamento em rascunho"
        if autorizado is False:
            row["observacoes"] += (
                ("; " if row["observacoes"] else "") +
                "Metadados não autorizam publicação externa"
            )
        revisao = str(doc.get("review") or "")
        if "revisao_academica_formal_pendente" in revisao or "pendente_revisao_academica" in revisao:
            row["revisao_academica_pendente"] = "sim"
        if numero in PERFIS_V2 and autorizado is True:
            protegido, omitidos = preparar_doc_publico_v2(doc, numero)
            if protegido is None:
                row["estado"] = "ERRO"
                row["observacoes"] += "; Proteção V2 não autorizou exibição"
            else:
                row["linhas_omitidas_publicacao"] = omitidos
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        row["estado"] = "ERRO"
        row["observacoes"] = f"Falha ao ler fonte JSON: {type(exc).__name__}: {exc}"
    return row


def executar(raiz: Path, destino: Path) -> tuple[list[dict], Path]:
    catalogo = ler_catalogo(raiz)
    linhas = [auditar_indicador(raiz, item) for item in catalogo["indicadores"]]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    return linhas, destino


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()
    raiz = args.raiz.resolve()
    destino = (args.saida or
               (raiz.parent / "ENEM_EXPORTACOES" / "auditoria_prontidao_streamlit.csv")).resolve()
    if destino == raiz or raiz in destino.parents:
        parser.error("O CSV de auditoria deve ficar fora do repositório.")
    try:
        linhas, saida = executar(raiz, destino)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERRO na auditoria: {exc}")
        return 2

    falhas = [x for x in linhas if x["estado"] == "ERRO"]
    pendentes = [x for x in linhas if x["pendencia_catalogo"]]
    rascunhos = [x for x in linhas if x["status_dados"].casefold() in ("draft", "rascunho")]
    nao_publicar = [x for x in linhas if x["publicacao_autorizada"] == "false"]
    revisao_pendente = [x for x in linhas if x["revisao_academica_pendente"] == "sim"]
    suprimidas = sum(int(x["linhas_omitidas_publicacao"]) for x in linhas)
    print(f"Indicadores conferidos: {len(linhas)} em {len(set(x['pagina'] for x in linhas))} páginas.")
    print(f"Fontes ausentes, inválidas ou inconsistentes: {len(falhas)}")
    print(f"Pendências documentais no catálogo: {len(pendentes)}")
    print(f"Fontes com data_status=rascunho: {len(rascunhos)}")
    print(f"Fontes que declaram publicacao_autorizada=false: {len(nao_publicar)}")
    print(f"Fontes com revisão acadêmica ainda pendente: {len(revisao_pendente)}")
    print(f"Registros agregados ocultados por células pequenas na publicação V2: {suprimidas}")
    print(f"CSV de diagnóstico: {saida}")
    if falhas:
        for x in falhas[:20]:
            print(f"  ERRO {x['indicador']}: {x['observacoes']}")
    if pendentes:
        print("  Pendências do catálogo: " +
              ", ".join(x["indicador"] for x in pendentes))
    if nao_publicar:
        print("  Publicação externa não autorizada declarada nas fontes: " +
              ", ".join(x["indicador"] for x in nao_publicar))
    print("Observação: integridade de fonte NÃO comprova correção estatística, "
          "privacidade nem autorização de publicação.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
