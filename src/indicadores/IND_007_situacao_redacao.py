# -*- coding: utf-8 -*-
"""IND-007 — Situação da redação (ENEM 2019–2025).

Catálogo: ``pages.overview.essay_status``; população POP_ALL; COUNT e % por
TP_STATUS_REDACAO. Códigos oficiais encontrados nos dicionários 2019–2025:
1, 2, 3, 4, 6, 7, 8 e 9. Status vazio é contabilizado separadamente como
NAO_INFORMADO, não como 'Em Branco' (código 4).

Abrangência: 7 edições, Brasil e 27 UFs de aplicação, mais 2019–2025.
O denominador de cada percentual é TODOS os registros daquele grupo,
não apenas as redações válidas. O histórico soma participações, não pessoas.

Execução (PowerShell, na raiz do repositório):
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_007_situacao_redacao.py

Pré-requisitos: IND-001 e IND-006 em outputs/json/, sete dashboards com IND-001–006,
e CSVs das sete edições em data/raw/<ano>/.

Saídas:
    outputs/indicadores/IND_007_situacao_redacao.csv (2016 linhas)
    outputs/json/IND_007_situacao_redacao.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

O script preserva IND-001 a IND-006 e não altera o Streamlit.
Status acadêmico: draft. Contagens pequenas devem passar por revisão de
supressão/complementaridade antes de publicar dados agregados ao público.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()))
CODIGOS = {
    "1": "Sem problemas",
    "2": "Anulada",
    "3": "Cópia Texto Motivador",
    "4": "Em Branco",
    "6": "Fuga ao tema",
    "7": "Não atendimento ao tipo textual",
    "8": "Texto insuficiente",
    "9": "Parte desconectada",
}
SEM_STATUS = "NAO_INFORMADO"
CATEGORIAS = (*CODIGOS, SEM_STATUS)
LABELS = {**CODIGOS, SEM_STATUS: "Status não informado"}
INDICADOR = "IND-007"
VERSAO = "2.6.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007"
BLOCO_PADRAO = 100_000
LIMIAR_REVISAO = 30
METODO = "distribuicao_categorica_tp_status_redacao_pop_all"
DEFINICAO = (
    "COUNT e porcentagem de todos os registros (POP_ALL) por código oficial de "
    "TP_STATUS_REDACAO, incluindo uma categoria separada para status ausente, "
    "por ano, Brasil e UF de aplicação (SG_UF_PROVA)."
)
NOTA_HISTORICA = (
    "O período 2019–2025 agrega participações das edições, não indivíduos "
    "únicos. A UF indica o local de prova, não residência. Percentuais "
    "utilizam POP_ALL como denominador. Ausência de status não implica "
    "redação em branco: apenas o código 4 significa 'Em Branco'."
)


def origem(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {caminho}")
    with caminho.open(encoding="utf-8") as arq:
        return json.load(arq)


def carregar_referencias(raiz: Path) -> tuple[dict, dict, dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    ind001 = ler_json(pasta / "IND_001_redacoes_validas.json")
    ind006 = ler_json(pasta / "IND_006_distribuicao_notas.json")
    for numero, doc in ((1, ind001), (6, ind006)):
        identificador = f"IND-{numero:03d}"
        if doc.get("indicator", {}).get("id") != identificador:
            raise ValueError(f"Referência {identificador}: ID incorreto")
        if sorted(d["ano"] for d in doc["years"]) != list(ANOS):
            raise ValueError(f"Referência {identificador}: faltam edições")
        if {r["uf"] for r in doc["historical"]["ufs"]} != set(UFS):
            raise ValueError(f"Referência {identificador}: faltam UFs históricas")
    dashboards = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}.json: ano incorreto")
        overview = painel.get("pages", {}).get("overview", {})
        if any(f"ind{i:03d}" not in overview for i in range(1, 6)):
            raise ValueError(f"{ano}: dashboard ainda sem IND-001–005")
        if "score_distribution" not in overview:
            raise ValueError(f"{ano}: IND-006 ainda não foi integrado ao dashboard")
        dashboards[ano] = painel
    return ind001, ind006, dashboards


def resumo_contagens(contagens: Counter[str]) -> dict:
    desconhecidas = set(contagens).difference(CATEGORIAS)
    if desconhecidas:
        raise ValueError(f"Códigos não previstos no dicionário: {desconhecidas}")
    total = sum(contagens.values())
    if total <= 0:
        raise ValueError("POP_ALL vazia para o grupo")
    categorias = []
    for codigo in CATEGORIAS:
        qtd = int(contagens.get(codigo, 0))
        categorias.append({
            "codigo": codigo,
            "rotulo": LABELS[codigo],
            "oficial": codigo in CODIGOS,
            "quantidade": qtd,
            "proporcao": round(qtd / total, 8),
            "percentual": round(qtd / total * 100, 4),
            "requer_revisao_privacidade": 0 < qtd < LIMIAR_REVISAO,
        })
    if sum(r["quantidade"] for r in categorias) != total:
        raise AssertionError("Categorias não somam a população")
    if abs(sum(r["percentual"] for r in categorias) - 100) > 0.001:
        raise AssertionError("Percentuais das categorias não somam 100 dentro da precisão")
    return {
        "total_registros": total,
        "redacoes_status_1": int(contagens.get("1", 0)),
        "status_nao_informado": int(contagens.get(SEM_STATUS, 0)),
        "categorias": categorias,
        "celulas_positivas_inferiores_30": sum(0 < r["quantidade"] < LIMIAR_REVISAO for r in categorias),
    }


def processar_ano(ano: int, raiz: Path, bloco: int) -> tuple[dict, dict[str, Counter[str]]]:
    arquivo = origem(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Microdados não encontrados: {arquivo}")
    cont_ufs: dict[str, Counter[str]] = {uf: Counter() for uf in UFS}
    total_lido = 0
    for parte in pd.read_csv(
        arquivo, sep=";", usecols=["SG_UF_PROVA", "TP_STATUS_REDACAO"],
        dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    ):
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        desconhecidos = set(status.unique()).difference((*CODIGOS, ""))
        if desconhecidos:
            raise ValueError(f"{ano}: código(s) de status não oficiais: {sorted(desconhecidos)!r}")
        invalidas_uf = set(uf.unique()).difference(UFS)
        if invalidas_uf:
            raise ValueError(f"{ano}: UF(s) ausentes ou desconhecidas: {sorted(invalidas_uf)!r}")
        status = status.mask(status.eq(""), SEM_STATUS)
        tab = pd.DataFrame({"uf": uf, "status": status}).groupby(["uf", "status"]).size()
        for (sigla, codigo), quantidade in tab.items():
            cont_ufs[str(sigla)][str(codigo)] += int(quantidade)
        total_lido += len(parte)
    if total_lido <= 0:
        raise ValueError(f"{ano}: arquivo CSV vazio")
    brasil_cont: Counter[str] = Counter()
    estados = []
    for uf in UFS:
        brasil_cont.update(cont_ufs[uf])
        estados.append({"uf": uf, **resumo_contagens(cont_ufs[uf])})
    brasil = resumo_contagens(brasil_cont)
    if brasil["total_registros"] != total_lido:
        raise ValueError(f"{ano}: totais de UF não coincidem com o CSV")
    for codigo in CATEGORIAS:
        if sum(c["quantidade"] for estado in estados for c in estado["categorias"] if c["codigo"] == codigo) != next(c["quantidade"] for c in brasil["categorias"] if c["codigo"] == codigo):
            raise ValueError(f"{ano}: Brasil diverge das UFs no status {codigo}")
    celulas = sum(r["celulas_positivas_inferiores_30"] for r in estados)
    return {
        "ano": ano, "arquivo_fonte": arquivo.name, "brasil": brasil, "ufs": estados,
        "qualidade": {
            "status": "ok", "populacao": "POP_ALL", "registros_lidos": total_lido,
            "status_nao_informado_brasil": brasil["status_nao_informado"],
            "soma_categorias_igual_populacao": True,
            "soma_27_ufs_igual_brasil": True,
            "celulas_uf_positivas_inferiores_30": celulas,
            "revisao_privacidade_obrigatoria_antes_de_publicar": bool(celulas),
            "metodo": METODO,
        },
    }, cont_ufs


def comparar_grupo(grupo: dict, ref001: dict, ref006: dict, contexto: str) -> None:
    if grupo["total_registros"] != ref001["total_registros"]:
        raise ValueError(f"{contexto}: total POP_ALL divergente do IND-001")
    if grupo["redacoes_status_1"] != ref001["redacoes_validas"]:
        raise ValueError(f"{contexto}: status=1 divergente da POP_VALID do IND-001")
    if grupo["redacoes_status_1"] != ref006["n_validas"]:
        raise ValueError(f"{contexto}: status=1 divergente do IND-006")
    if ref006.get("total_registros") is not None and grupo["total_registros"] != ref006["total_registros"]:
        raise ValueError(f"{contexto}: total de registros divergente do IND-006")
    if sum(c["quantidade"] for c in grupo["categorias"]) != grupo["total_registros"]:
        raise ValueError(f"{contexto}: categorias não fecham a contagem")


def validar_referencias(dados: list[dict], ind001: dict, ind006: dict) -> None:
    refs1 = {d["ano"]: d for d in ind001["years"]}
    refs6 = {d["ano"]: d for d in ind006["years"]}
    for d in dados:
        ano = d["ano"]
        r1, r6 = refs1[ano], refs6[ano]
        comparar_grupo(d["brasil"], r1["brasil"], r6["brasil"], f"{ano}/BR")
        u1 = {r["uf"]: r for r in r1["ufs"]}
        u6 = {r["uf"]: r for r in r6["ufs"]}
        if set(u1) != set(UFS) or set(u6) != set(UFS):
            raise ValueError(f"{ano}: referências sem 27 UFs")
        for r in d["ufs"]:
            comparar_grupo(r, u1[r["uf"]], u6[r["uf"]], f"{ano}/{r['uf']}")
        d["qualidade"]["validado_contra_ind001_ind006"] = True


def consolidar_historico(dados: list[dict], frequencias: dict[int, dict[str, Counter[str]]],
                          ind001: dict, ind006: dict) -> dict:
    historico_ufs = {uf: Counter() for uf in UFS}
    for ano in ANOS:
        for uf in UFS:
            historico_ufs[uf].update(frequencias[ano][uf])
    brasil_cont: Counter[str] = Counter()
    estados = []
    ref1 = {r["uf"]: r for r in ind001["historical"]["ufs"]}
    ref6 = {r["uf"]: r for r in ind006["historical"]["ufs"]}
    for uf in UFS:
        brasil_cont.update(historico_ufs[uf])
        estado = {"uf": uf, **resumo_contagens(historico_ufs[uf])}
        comparar_grupo(estado, ref1[uf], ref6[uf], f"Histórico/{uf}")
        estados.append(estado)
    brasil = resumo_contagens(brasil_cont)
    comparar_grupo(brasil, ind001["historical"]["brasil"], ind006["historical"]["brasil"], "Histórico/BR")
    if brasil["total_registros"] != sum(d["brasil"]["total_registros"] for d in dados):
        raise ValueError("Histórico não fecha a soma das edições")
    for codigo in CATEGORIAS:
        h = next(c["quantidade"] for c in brasil["categorias"] if c["codigo"] == codigo)
        soma_anos = sum(next(c["quantidade"] for c in d["brasil"]["categorias"] if c["codigo"] == codigo) for d in dados)
        if h != soma_anos:
            raise ValueError(f"Histórico: código {codigo} não coincide com edições")
    return {"periodo": "2019-2025", "brasil": brasil, "ufs": estados, "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    conjuntos = [(str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"]) for d in dados]
    conjuntos.append(("2019-2025", historico["brasil"], historico["ufs"], "TODAS_AS_EDICOES"))
    linhas = []
    for periodo, brasil, estados, fonte in conjuntos:
        grupos = [("BRASIL", "BR", brasil)] + [("UF", d["uf"], d) for d in estados]
        for abrangencia, uf, d in grupos:
            for c in d["categorias"]:
                linhas.append({
                    "indicador_id": INDICADOR, "periodo": periodo,
                    "abrangencia": abrangencia, "uf": uf,
                    "status_codigo": c["codigo"], "status_rotulo": c["rotulo"],
                    "status_oficial": c["oficial"], "total_registros": d["total_registros"],
                    "quantidade": c["quantidade"], "proporcao": c["proporcao"],
                    "percentual": c["percentual"],
                    "requer_revisao_privacidade": c["requer_revisao_privacidade"],
                    "populacao": "POP_ALL", "metodo": METODO, "arquivo_fonte": fonte,
                })
    esperado = (len(ANOS) + 1) * (len(UFS) + 1) * len(CATEGORIAS)
    if len(linhas) != esperado:
        raise AssertionError(f"Quantidade de linhas incorreta: {len(linhas)} != {esperado}")
    return linhas


def construir_dashboard(d: dict, dados: list[dict], historico: dict, base: dict,
                         gerado: str) -> dict:
    ano = d["ano"]
    painel = deepcopy(base)
    overview = painel["pages"]["overview"]
    br = d["brasil"]
    if overview["kpis"]["valid_essays"] != br["redacoes_status_1"]:
        raise ValueError(f"Dashboard {ano}: quantidade válida alterada")
    dist = overview["score_distribution"]
    if dist["n"] != br["redacoes_status_1"]:
        raise ValueError(f"Dashboard {ano}: IND-006 divergente")
    for i in range(1, 6):
        if f"ind{i:03d}" not in overview:
            raise ValueError(f"Dashboard {ano}: faltando IND-{i:03d}")
    if len(dist["by_uf"]) != 27:
        raise ValueError(f"Dashboard {ano}: IND-006 não contém 27 UFs")
    painel["meta"]["analysis_version"] = VERSAO
    painel["meta"]["generated_at"] = gerado
    painel["meta"]["data_status"] = "draft"
    aviso = "IND-007 aguardando revisão acadêmica e de supressão de células pequenas antes de publicação."
    if aviso not in painel["meta"].setdefault("warnings", []):
        painel["meta"]["warnings"].append(aviso)
    overview["essay_status"] = {
        "indicator_id": INDICADOR, "population": "POP_ALL", "method": METODO,
        "n": br["total_registros"], "categories": br["categorias"],
        "by_uf": [{"uf": r["uf"], "n": r["total_registros"],
                   "categories": r["categorias"]} for r in d["ufs"]],
        "privacy_review_required": d["qualidade"]["revisao_privacidade_obrigatoria_antes_de_publicar"],
    }
    painel["pages"]["temporal"]["ind007"] = {
        "indicator_id": INDICADOR, "population": "POP_ALL",
        "national_by_year": [{"year": x["ano"], "n": x["brasil"]["total_registros"],
                              "categories": x["brasil"]["categorias"]} for x in dados],
        "period_total": {"n": historico["brasil"]["total_registros"],
                         "categories": historico["brasil"]["categorias"]},
        "period_by_uf": [{"uf": r["uf"], "n": r["total_registros"],
                          "categories": r["categorias"]} for r in historico["ufs"]],
        "note": NOTA_HISTORICA,
    }
    painel["pages"]["methodology"]["ind007"] = {
        "definition": DEFINICAO,
        "calculation": "COUNT(status) e 100*COUNT(status)/COUNT(todos os registros); ausentes como categoria separada",
        "population": "POP_ALL (não confundir com POP_VALID)",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "official_status_codes": CODIGOS,
        "historical_note": NOTA_HISTORICA,
        "privacy_note": "Supressão e complementaridade de células pequenas exigem revisão antes da divulgação pública.",
    }
    painel["quality"]["ind007_validation"] = d["qualidade"]
    return painel


def validar_dashboard(painel: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(painel):
        raise ValueError("Dashboard sem chaves obrigatórias")
    if "NU_INSCRICAO" in json.dumps(painel, ensure_ascii=False):
        raise ValueError("Identificador individual detectado")
    candidatos = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    schema = next((c for c in candidatos if c.is_file()), None)
    if schema is None:
        return "estrutura básica (JSON Schema não encontrado)"
    try:
        import jsonschema
    except ImportError:
        return "estrutura básica (instale jsonschema)"
    with schema.open(encoding="utf-8") as f:
        jsonschema.validate(painel, json.load(f))
    return "JSON Schema v1.0.0"


def salvar_json(caminho: Path, obj: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    temp.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    temp.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    ind001, ind006, dashboards_base = carregar_referencias(raiz)
    dados, frequencias = [], {}
    for ano in ANOS:
        print(f"IND-007 | {ano}: processando {origem(ano, raiz).name}...", flush=True)
        doc, freq = processar_ano(ano, raiz, bloco)
        dados.append(doc)
        frequencias[ano] = freq
        br = doc["brasil"]
        print(f"  POP_ALL={br['total_registros']:,} | status=1={br['redacoes_status_1']:,} | "
              f"status ausente={br['status_nao_informado']:,}", flush=True)
    validar_referencias(dados, ind001, ind006)
    historico = consolidar_historico(dados, frequencias, ind001, ind006)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboards = {d["ano"]: construir_dashboard(
        d, dados, historico, dashboards_base[d["ano"]], gerado) for d in dados}
    validacoes = {validar_dashboard(p, raiz) for p in dashboards.values()}
    modulo = {
        "meta": {
            "indicator_id": INDICADOR, "module_schema_version": "ind007-module-1.0.0",
            "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado, "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001_ind006": "aprovada (total POP_ALL, status 1 e 27 UFs)",
            "method": METODO, "official_status_codes": CODIGOS,
            "missing_status_code": SEM_STATUS,
            "privacy_note": "Conferir supressão e complementaridade em células pequenas antes de divulgação pública.",
        },
        "indicator": {"id": INDICADOR, "name": "Situação da redação",
                      "unit": "registros", "dashboard_json_path": "pages.overview.essay_status"},
        "years": dados, "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)
    base = raiz / "outputs"
    salvar_csv(base / "indicadores" / "IND_007_situacao_redacao.csv", linhas)
    salvar_json(base / "json" / "IND_007_situacao_redacao.json", modulo)
    for ano in ANOS:
        salvar_json(base / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    n_pequenas = sum(x["qualidade"]["celulas_uf_positivas_inferiores_30"] for x in dados)
    print("\nIND-007 concluído. Saídas:")
    print(f"  IND_007_situacao_redacao.csv ({len(linhas)} linhas)")
    print("  IND_007_situacao_redacao.json")
    print("  dashboard_enem_AAAA.json (2019–2025, cumulativos)")
    print("  Validação: " + ", ".join(sorted(validacoes)))
    print(f"  Histórico: POP_ALL={historico['brasil']['total_registros']:,} | "
          f"status=1={historico['brasil']['redacoes_status_1']:,}")
    print(f"  Células pequenas (1–29 registros) que exigem revisão: {n_pequenas}")
    print("  STATUS: draft — revisão acadêmica e privacidade pendentes")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-007 — Situação da redação ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Raiz do repositório (padrão: duas pastas acima do script)")
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
