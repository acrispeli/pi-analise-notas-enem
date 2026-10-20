# -*- coding: utf-8 -*-
"""IND-008 — Notas 1000 na redação do ENEM (2019–2025).

Catálogo mestre: Alto desempenho / overview / Notas 1000.
Pergunta: Quantas redações atingiram 1000?
Método: count(NU_NOTA_REDACAO == 1000) e proporção na POP_VALID.
Destino: pages.overview.kpis.perfect_scores (objeto).

POP_VALID: TP_STATUS_REDACAO == '1' e nota numérica no intervalo [0, 1000].
Abrangência: Brasil, 27 UFs de aplicação, cada ano e histórico 2019–2025.
O histórico soma participações entre edições, NÃO pessoas distintas.

IMPORTANTE: Execute SOMENTE após a conclusão do IND-007; os scripts atualizam
os mesmos dashboards. O IND-008 requer o JSON do IND-007 e sua integração.

No PowerShell, a partir da raiz do repositório:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_008_notas_1000.py

Saídas (apenas depois da validação completa dos sete anos):
    outputs/indicadores/IND_008_notas_1000.csv        (224 registros)
    outputs/json/IND_008_notas_1000.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

O script não altera o visualizador Streamlit. Resultados mantidos como DRAFT;
contagens por UF entre 1 e 29 exigem revisão de privacidade/supressão.
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
INDICADOR = "IND-008"
VERSAO = "2.7.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008"
METODO = "contagem_exata_nota_1000_pop_valid"
BLOCO_PADRAO = 100_000
LIMIAR_REVISAO = 30
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
DEFINICAO = (
    "Quantidade e proporção de redações com NU_NOTA_REDACAO exatamente igual "
    "a 1000 entre redações válidas (TP_STATUS_REDACAO = 1 e nota numérica "
    "de 0 a 1000), por ano, Brasil e UF de aplicação (SG_UF_PROVA)."
)
NOTA_HISTORICA = (
    "O total histórico soma redações/participações entre 2019 e 2025, "
    "sem identificar pessoas únicas. O percentual histórico é "
    "100 * total_notas_1000 / total_redacoes_validas do período. "
    "SG_UF_PROVA representa o local de aplicação da prova, não a residência."
)


def origem(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {caminho}")
    with caminho.open(encoding="utf-8") as arq:
        return json.load(arq)


def carregar_referencias(raiz: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    arquivos = {
        1: "redacoes_validas", 6: "distribuicao_notas", 7: "situacao_redacao",
    }
    refs: dict[int, dict] = {}
    for indice, sufixo in arquivos.items():
        doc = ler_json(pasta / f"IND_{indice:03d}_{sufixo}.json")
        identificador = f"IND-{indice:03d}"
        if doc.get("indicator", {}).get("id") != identificador:
            raise ValueError(f"Referência {identificador}: identificador incorreto")
        if sorted(item.get("ano") for item in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"Referência {identificador}: faltam anos de 2019–2025")
        if {r.get("uf") for r in doc.get("historical", {}).get("ufs", [])} != set(UFS):
            raise ValueError(f"Referência {identificador}: histórico sem as 27 UFs")
        for d in doc["years"]:
            if {r.get("uf") for r in d.get("ufs", [])} != set(UFS):
                raise ValueError(f"Referência {identificador} em {d['ano']}: sem 27 UFs")
        refs[indice] = doc
    dashboards = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}.json: ano incorreto")
        visao = painel.get("pages", {}).get("overview", {})
        for i in range(1, 6):
            if f"ind{i:03d}" not in visao:
                raise ValueError(f"Dashboard {ano} ainda sem IND-{i:03d}")
        if "score_distribution" not in visao or "essay_status" not in visao:
            raise ValueError(
                f"Dashboard {ano} precisa conter IND-006 e IND-007. "
                "Aguarde a conclusão do IND-007 antes de executar."
            )
        if painel.get("quality", {}).get("ind007_validation", {}).get("status") != "ok":
            raise ValueError(f"Dashboard {ano}: IND-007 não consta como processado")
        dashboards[ano] = painel
    return refs, dashboards


def resumo(n_validas: int, n_perfeitas: int) -> dict:
    n_validas = int(n_validas)
    n_perfeitas = int(n_perfeitas)
    if n_validas <= 0 or n_perfeitas < 0 or n_perfeitas > n_validas:
        raise ValueError(f"Contagem impossível: validas={n_validas}, nota_1000={n_perfeitas}")
    return {
        "n_validas": n_validas,
        "n_notas_1000": n_perfeitas,
        "proporcao": round(n_perfeitas / n_validas, 8),
        "percentual": round(100 * n_perfeitas / n_validas, 4),
        "requer_revisao_privacidade": 0 < n_perfeitas < LIMIAR_REVISAO,
    }


def processar_ano(ano: int, raiz: Path, bloco: int) -> dict:
    caminho = origem(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Base de microdados ausente: {caminho}")
    validas_uf = Counter({uf: 0 for uf in UFS})
    perfeitas_uf = Counter({uf: 0 for uf in UFS})
    registros_uf = Counter()
    qa = Counter()
    for parte in pd.read_csv(
        caminho, sep=";", usecols=list(COLUNAS), dtype=str,
        keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    ):
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        nota_txt = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(nota_txt.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        validas = st1 & nota_ok
        perfeitas = validas & nota.eq(1000)
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(validas.sum())
        qa["notas1000"] += int(perfeitas.sum())
        qa["status1_sem_nota"] += int((st1 & nota_txt.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & nota_txt.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((validas & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((validas & ~uf_ok & uf.ne("")).sum())
        registros_uf.update({str(k): int(v) for k, v in uf.value_counts().items()})
        validas_uf.update({str(k): int(v) for k, v in uf[validas].value_counts().items()})
        perfeitas_uf.update({str(k): int(v) for k, v in uf[perfeitas].value_counts().items()})
    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: base vazia")
    if qa["status1"] != (qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]):
        raise ValueError(f"{ano}: balanço de status=1 não fecha")
    if qa["status1_sem_nota"] or qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: existem notas inválidas ou ausentes entre status=1")
    if qa["validas_sem_uf"] or qa["validas_uf_desconhecida"]:
        raise ValueError(f"{ano}: redações válidas sem UF ou com UF desconhecida")
    if sum(registros_uf.values()) != qa["registros"]:
        raise ValueError(f"{ano}: contagem dos registros não fecha")
    estados = []
    for uf in UFS:
        if validas_uf[uf] < LIMIAR_REVISAO:
            raise ValueError(f"{ano}/{uf}: menos de 30 redações válidas; revisão necessária")
        estados.append({"uf": uf, "total_registros": registros_uf[uf],
                        **resumo(validas_uf[uf], perfeitas_uf[uf])})
    if sum(r["n_validas"] for r in estados) != qa["validas"]:
        raise ValueError(f"{ano}: Brasil não fecha a soma de redações válidas das UFs")
    if sum(r["n_notas_1000"] for r in estados) != qa["notas1000"]:
        raise ValueError(f"{ano}: Brasil não fecha a soma das notas 1000 das UFs")
    return {
        "ano": ano, "arquivo_fonte": caminho.name,
        "brasil": {"total_registros": qa["registros"],
                   **resumo(qa["validas"], qa["notas1000"])},
        "ufs": estados,
        "qualidade": {
            "status": "ok", "status1_sem_nota": qa["status1_sem_nota"],
            "status1_nota_invalida": qa["status1_nota_invalida"],
            "validas_sem_uf": qa["validas_sem_uf"],
            "validas_uf_desconhecida": qa["validas_uf_desconhecida"],
            "total_perfeitas_uf_igual_brasil": True,
            "celulas_uf_positivas_inferiores_30": sum(r["requer_revisao_privacidade"] for r in estados),
            "metodo": METODO,
        },
    }


def quantidade_status_um(ref007: dict) -> int:
    itens = [r for r in ref007.get("categorias", []) if str(r.get("codigo")) == "1"]
    if len(itens) != 1:
        raise ValueError("IND-007: categoria de status=1 não encontrada de forma única")
    return int(itens[0]["quantidade"])


def comparar_grupo(d: dict, r1: dict, r6: dict, r7: dict, contexto: str) -> None:
    n = d["n_validas"]
    if n != r1["redacoes_validas"] or n != r6["n_validas"] or n != r7["redacoes_status_1"]:
        raise ValueError(f"{contexto}: POP_VALID diverge dos indicadores IND-001/006/007")
    if n != quantidade_status_um(r7):
        raise ValueError(f"{contexto}: status 1 no IND-007 não fecha com POP_VALID")
    for r in (r1, r7):
        if d["total_registros"] != r["total_registros"]:
            raise ValueError(f"{contexto}: POP_ALL diverge do IND-001/007")
    if "total_registros" in r6 and d["total_registros"] != r6["total_registros"]:
        raise ValueError(f"{contexto}: POP_ALL diverge do IND-006")
    faixas = r6.get("faixas", [])
    if len(faixas) != 10:
        raise ValueError(f"{contexto}: IND-006 não possui dez faixas")
    if d["n_notas_1000"] > faixas[-1]["quantidade"]:
        raise ValueError(f"{contexto}: notas 1000 superam total de notas de 900 a 1000 no IND-006")
    if d["n_notas_1000"] > n:
        raise ValueError(f"{contexto}: quantidade de notas 1000 supera POP_VALID")


def validar_referencias(dados: list[dict], refs: dict[int, dict]) -> None:
    series = {i: {r["ano"]: r for r in refs[i]["years"]} for i in (1, 6, 7)}
    for d in dados:
        ano = d["ano"]
        r1, r6, r7 = (series[i][ano] for i in (1, 6, 7))
        comparar_grupo(d["brasil"], r1["brasil"], r6["brasil"], r7["brasil"], f"{ano}/BR")
        grupos = [{x["uf"]: x for x in r["ufs"]} for r in (r1, r6, r7)]
        for grupo in d["ufs"]:
            uf = grupo["uf"]
            comparar_grupo(grupo, grupos[0][uf], grupos[1][uf], grupos[2][uf], f"{ano}/{uf}")
        d["qualidade"]["validado_contra_ind001_ind006_ind007"] = True


def consolidar_historico(dados: list[dict], refs: dict[int, dict]) -> dict:
    estados = []
    hist_refs = {i: {r["uf"]: r for r in refs[i]["historical"]["ufs"]} for i in (1, 6, 7)}
    for uf in UFS:
        itens = [next(grupo for grupo in d["ufs"] if grupo["uf"] == uf) for d in dados]
        r = {"uf": uf,
             "total_registros": sum(x["total_registros"] for x in itens),
             **resumo(sum(x["n_validas"] for x in itens),
                      sum(x["n_notas_1000"] for x in itens))}
        comparar_grupo(r, hist_refs[1][uf], hist_refs[6][uf], hist_refs[7][uf], f"Histórico/{uf}")
        estados.append(r)
    total_validas = sum(d["brasil"]["n_validas"] for d in dados)
    total_perfeitas = sum(d["brasil"]["n_notas_1000"] for d in dados)
    brasil = {"total_registros": sum(d["brasil"]["total_registros"] for d in dados),
              **resumo(total_validas, total_perfeitas)}
    comparar_grupo(brasil, refs[1]["historical"]["brasil"],
                   refs[6]["historical"]["brasil"],
                   refs[7]["historical"]["brasil"], "Histórico/BR")
    if sum(x["n_notas_1000"] for x in estados) != total_perfeitas:
        raise ValueError("Histórico: notas 1000 das UFs não fecham com Brasil")
    return {"periodo": "2019-2025", "brasil": brasil, "ufs": estados,
            "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    saida = []
    contextos = [(str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"]) for d in dados]
    contextos.append(("2019-2025", historico["brasil"], historico["ufs"], "TODAS_AS_EDICOES"))
    for periodo, brasil, ufs, fonte in contextos:
        for nivel, uf, dado in [("BRASIL", "BR", brasil)] + [("UF", r["uf"], r) for r in ufs]:
            saida.append({
                "indicador_id": INDICADOR, "periodo": periodo,
                "abrangencia": nivel, "uf": uf,
                "n_validas": dado["n_validas"], "n_notas_1000": dado["n_notas_1000"],
                "proporcao": dado["proporcao"], "percentual": dado["percentual"],
                "total_registros": dado["total_registros"],
                "requer_revisao_privacidade": dado["requer_revisao_privacidade"],
                "populacao": "POP_VALID", "metodo": METODO, "arquivo_fonte": fonte,
            })
    esperado = (len(ANOS) + 1) * (len(UFS) + 1)
    if len(saida) != esperado:
        raise AssertionError(f"CSV tem {len(saida)} registros, esperados {esperado}")
    return saida


def construir_dashboard(d: dict, dados: list[dict], historico: dict,
                         base: dict, gerado: str) -> dict:
    ano = d["ano"]
    p = deepcopy(base)
    visao = p["pages"]["overview"]
    br = d["brasil"]
    if visao["kpis"]["valid_essays"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: POP_VALID divergente")
    if visao["score_distribution"]["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: IND-006 divergente")
    if visao["essay_status"]["n"] != br["total_registros"]:
        raise ValueError(f"Dashboard {ano}: IND-007 divergente no total de registros")
    if quantidade_status_um({"categorias": visao["essay_status"]["categories"]}) != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: IND-007 divergente no status 1")
    if {r["uf"] for r in visao["score_distribution"].get("by_uf", [])} != set(UFS):
        raise ValueError(f"Dashboard {ano}: IND-006 sem as 27 UFs")
    if {r["uf"] for r in visao["essay_status"].get("by_uf", [])} != set(UFS):
        raise ValueError(f"Dashboard {ano}: IND-007 sem as 27 UFs")
    # Os resultados existentes são preservados; acrescenta apenas IND-008.
    p["meta"]["analysis_version"] = VERSAO
    p["meta"]["generated_at"] = gerado
    p["meta"]["data_status"] = "draft"
    aviso = "IND-008: revisão acadêmica e de supressão de contagens pequenas necessária antes da divulgação pública."
    if aviso not in p["meta"].setdefault("warnings", []):
        p["meta"]["warnings"].append(aviso)
    visao["kpis"]["perfect_scores"] = {
        "count": br["n_notas_1000"], "proportion": br["proporcao"],
        "percentage": br["percentual"], "n_valid": br["n_validas"],
    }
    visao["ind008"] = {
        "indicator_id": INDICADOR, "unit": "redacoes", "population": "POP_VALID",
        "method": METODO, "n": br["n_validas"],
        "perfect_scores": br["n_notas_1000"],
        "proportion": br["proporcao"], "percentage": br["percentual"],
        "by_uf": [{"uf": r["uf"], "n": r["n_validas"],
                   "perfect_scores": r["n_notas_1000"], "proportion": r["proporcao"],
                   "percentage": r["percentual"],
                   "privacy_review_required": r["requer_revisao_privacidade"]} for r in d["ufs"]],
        "privacy_review_required": d["qualidade"]["celulas_uf_positivas_inferiores_30"] > 0,
    }
    p["pages"]["temporal"]["ind008"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID",
        "national_by_year": [{"year": x["ano"],
                              "n": x["brasil"]["n_validas"],
                              "perfect_scores": x["brasil"]["n_notas_1000"],
                              "proportion": x["brasil"]["proporcao"],
                              "percentage": x["brasil"]["percentual"]} for x in dados],
        "period_total": {"n": historico["brasil"]["n_validas"],
                         "perfect_scores": historico["brasil"]["n_notas_1000"],
                         "proportion": historico["brasil"]["proporcao"],
                         "percentage": historico["brasil"]["percentual"]},
        "period_by_uf": [{"uf": r["uf"], "n": r["n_validas"],
                          "perfect_scores": r["n_notas_1000"],
                          "proportion": r["proporcao"],
                          "percentage": r["percentual"]} for r in historico["ufs"]],
        "note": NOTA_HISTORICA,
    }
    p["pages"]["methodology"]["ind008"] = {
        "definition": DEFINICAO,
        "calculation": "SUM(TP_STATUS_REDACAO == 1 AND NU_NOTA_REDACAO == 1000) / N_POP_VALID",
        "population": "POP_VALID", "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"], "precision": "proporção: 8 decimais; percentual: 4 decimais",
        "historical_note": NOTA_HISTORICA,
        "privacy_note": "Dados agregados internos; revisar supressão de contagens entre 1 e 29 antes de publicar por UF.",
    }
    p["quality"]["ind008_validation"] = d["qualidade"]
    return p


def validar_dashboard(p: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(p):
        raise ValueError("Dashboard sem estrutura obrigatória")
    if "NU_INSCRICAO" in json.dumps(p, ensure_ascii=False):
        raise ValueError("Identificador individual inesperado no dashboard")
    candidatos = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    schema = next((x for x in candidatos if x.is_file()), None)
    if schema is None:
        return "estrutura básica (Schema não localizado)"
    try:
        import jsonschema
    except ImportError:
        return "estrutura básica (instale jsonschema)"
    with schema.open(encoding="utf-8") as f:
        jsonschema.validate(p, json.load(f))
    return "JSON Schema v1.0.0"


def salvar_json(caminho: Path, obj: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    tmp.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    tmp.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    referencias, bases = carregar_referencias(raiz)
    dados: list[dict] = []
    for ano in ANOS:
        print(f"IND-008 | {ano}: lendo {origem(ano, raiz).name} ...", flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        print(f"  validas={d['brasil']['n_validas']:,} | "
              f"nota1000={d['brasil']['n_notas_1000']:,} | "
              f"percentual={d['brasil']['percentual']:.4f}%", flush=True)
    validar_referencias(dados, referencias)
    historico = consolidar_historico(dados, referencias)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboards = {d["ano"]: construir_dashboard(d, dados, historico, bases[d["ano"]], gerado)
                  for d in dados}
    resultados_validacao = {validar_dashboard(p, raiz) for p in dashboards.values()}
    saida = {
        "meta": {
            "indicator_id": INDICADOR, "module_schema_version": "ind008-module-1.0.0",
            "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado, "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
            "method": METODO, "comparison_ind001_ind006_ind007": "aprovada (N, POP_ALL, status 1 e faixa 900–1000)",
            "privacy_note": "Revisar supressão de células de UF com 1–29 notas 1000 antes de publicar.",
        },
        "indicator": {"id": INDICADOR, "name": "Notas 1000", "unit": "redacoes",
                      "dashboard_json_path": "pages.overview.kpis.perfect_scores"},
        "years": dados, "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(saida, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)
    pasta = raiz / "outputs"
    salvar_csv(pasta / "indicadores" / "IND_008_notas_1000.csv", linhas)
    salvar_json(pasta / "json" / "IND_008_notas_1000.json", saida)
    for ano in ANOS:
        salvar_json(pasta / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    n_pequenas = sum(d["qualidade"]["celulas_uf_positivas_inferiores_30"] for d in dados)
    print("\nIND-008 concluído. Saídas:")
    print(f"  IND_008_notas_1000.csv ({len(linhas)} registros)")
    print("  IND_008_notas_1000.json")
    print("  dashboard_enem_AAAA.json (2019–2025; IND-001–008 preservados)")
    print("  Validação: " + ", ".join(sorted(resultados_validacao)))
    print(f"  Histórico: {historico['brasil']['n_notas_1000']:,} redações com nota 1000 "
          f"em {historico['brasil']['n_validas']:,} redações válidas")
    print(f"  Células estaduais 1–29 a revisar antes da publicação: {n_pequenas}")
    print("  STATUS: draft — revisão acadêmica/privacidade pendentes")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-008: notas 1000 da redação ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Raiz do repositório (padrão: duas pastas acima deste arquivo)")
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco precisa ser inteiro positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
