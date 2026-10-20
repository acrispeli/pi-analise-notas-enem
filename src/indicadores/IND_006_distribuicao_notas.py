# -*- coding: utf-8 -*-
"""IND-006 — Distribuição das notas da redação (ENEM 2019–2025).

Objetivo (Catálogo): histograma com faixas fixas, quantidade e proporção.
População POP_VALID: TP_STATUS_REDACAO == 1, nota numérica em [0,1000].
UF: SG_UF_PROVA (local da prova, não residência).

Faixas não sobrepostas: [0,100), [100,200), ..., [800,900), [900,1000].
Assim, notas 0 e 1000 também são contabilizadas.

Os microdados são lidos em blocos. As frequências das notas são agregadas,
sem salvar registros individuais e sem amostragem. O período 2019–2025 é
calculado reunindo as frequências, não fazendo médias dos percentuais anuais.

Execução, na raiz do repositório (PowerShell):
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_006_distribuicao_notas.py

Pré-requisitos:
    outputs/json/IND_001_redacoes_validas.json ... IND_005_percentis_redacao.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json
    data/raw/ANO/MICRODADOS_ENEM_ANO.csv  (2019–2023)
    data/raw/ANO/RESULTADOS_ANO.csv        (2024–2025)

Saídas, somente após processar e validar todas as edições:
    outputs/indicadores/IND_006_distribuicao_notas.csv (2240 linhas)
    outputs/json/IND_006_distribuicao_notas.json
    outputs/json/dashboard_enem_ANO.json (2019–2025, preservando IND-001–005)

Não altera o Streamlit nem os scripts anteriores.
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
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
BLOCO_PADRAO = 100_000
INDICADOR = "IND-006"
VERSAO = "2.5.0-ind001-ind002-ind003-ind004-ind005-ind006"
METODO = "histograma_faixas_fixas_100_pontos"
LIMITES = tuple(range(0, 1001, 100))
PERCENTIS = {"p25": 0.25, "p50": 0.50, "p75": 0.75, "p90": 0.90, "p95": 0.95}
DEFINICAO = (
    "Distribuição de NU_NOTA_REDACAO em dez faixas fixas de 100 pontos, "
    "contando e calculando a proporção de redações com TP_STATUS_REDACAO = 1 "
    "e nota numérica de 0 a 1000, inclusive, por ano e UF da prova."
)
NOTA_HISTORICA = (
    "As contagens históricas somam as participações de todas as edições de "
    "2019 a 2025, e as proporções são recalculadas usando o total histórico. "
    "Não representam indivíduos únicos. UF significa local de aplicação da prova."
)


def origem(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito não encontrado: {caminho}")
    with caminho.open(encoding="utf-8") as arq:
        return json.load(arq)


def carregar_referencias(raiz: Path) -> tuple[dict[str, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    nomes = {
        1: "redacoes_validas", 2: "nota_media", 3: "mediana_redacao",
        4: "desvio_padrao_redacao", 5: "percentis_redacao",
    }
    refs = {}
    for i, sufixo in nomes.items():
        doc = ler_json(pasta / f"IND_{i:03d}_{sufixo}.json")
        ident = f"IND-{i:03d}"
        if doc.get("indicator", {}).get("id") != ident:
            raise ValueError(f"Referência {ident} com identificador incorreto")
        if sorted(v.get("ano") for v in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"Referência {ident} sem a série 2019–2025 completa")
        if len(doc.get("historical", {}).get("ufs", [])) != len(UFS):
            raise ValueError(f"Referência {ident}: histórico sem 27 UFs")
        refs[ident] = doc
    dashboards = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"Dashboard {ano}: ano incorreto")
        visao = painel.get("pages", {}).get("overview", {})
        if any(f"ind{i:03d}" not in visao for i in range(1, 6)):
            raise ValueError(f"Dashboard {ano} não contém os indicadores 001–005")
        dashboards[ano] = painel
    return refs, dashboards


def quantis_frequencias(freq: Counter[float]) -> dict[str, float] | None:
    """Quantil HF7 por frequências, compatível com NumPy/Pandas."""
    n = sum(freq.values())
    if n == 0:
        return None
    posicoes = {}
    indices = set()
    for nome, p in PERCENTIS.items():
        h = (n - 1) * p
        esquerda, direita = math.floor(h), math.ceil(h)
        posicoes[nome] = (esquerda, direita, h - esquerda)
        indices.add(esquerda)
        indices.add(direita)
    acumulado, encontrados = 0, {}
    for valor, qtde in sorted(freq.items()):
        if not math.isfinite(valor) or not 0 <= valor <= 1000 or qtde <= 0:
            raise ValueError(f"Nota/frequência fora do domínio: {valor}: {qtde}")
        for i in indices:
            if acumulado <= i < acumulado + qtde:
                encontrados[i] = float(valor)
        acumulado += qtde
    if len(encontrados) != len(indices):
        raise AssertionError("Não foi possível resolver posições dos percentis")
    return {
        nome: round((1 - alpha) * encontrados[i] + alpha * encontrados[j], 6)
        for nome, (i, j, alpha) in posicoes.items()
    }


def faixa_indice(nota: float) -> int:
    if not math.isfinite(nota) or not (0 <= nota <= 1000):
        raise ValueError(f"Nota fora da população válida: {nota}")
    return min(int(nota // 100), 9)  # garante 1000 na última faixa


def resumo_frequencias(freq: Counter[float]) -> dict:
    n = sum(freq.values())
    if n <= 0:
        raise ValueError("População vazia: não é possível publicar histograma")
    soma = math.fsum(nota * quant for nota, quant in freq.items())
    media = soma / n
    variancia = math.fsum(quant * (nota - media) ** 2
                          for nota, quant in freq.items()) / n
    contagens = [0] * 10
    for nota, quant in freq.items():
        contagens[faixa_indice(nota)] += quant
    if sum(contagens) != n:
        raise AssertionError("Soma das faixas não corresponde à quantidade válida")
    faixas = []
    for i, q in enumerate(contagens):
        inicio, fim = LIMITES[i], LIMITES[i + 1]
        ultimo = i == 9
        faixas.append({
            "faixa": f"{inicio}–{fim}" if ultimo else f"{inicio}–<{fim}",
            "limite_inferior": inicio, "limite_superior": fim,
            "superior_inclusivo": ultimo,
            "quantidade": q,
            "proporcao": round(q / n, 8),
            "percentual": round(100 * q / n, 4),
        })
    if abs(sum(f["proporcao"] for f in faixas) - 1) > 0.000001:
        raise AssertionError("As proporções não somam 1 dentro da precisão")
    return {
        "n_validas": n,
        "faixas": faixas,
        "soma_notas": round(soma, 6),
        "media": round(media, 4),
        "mediana": quantis_frequencias(freq)["p50"],
        "percentis": quantis_frequencias(freq),
        "desvio_padrao": round(math.sqrt(variancia), 4),
    }


def processar_ano(ano: int, raiz: Path, bloco: int) -> tuple[dict, dict[str, Counter[float]]]:
    arquivo = origem(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Arquivo de microdados ausente: {arquivo}")
    frequencias = {uf: Counter() for uf in UFS}
    registros_uf = Counter()
    qa = Counter()
    leitor = pd.read_csv(
        arquivo, sep=";", usecols=list(COLUNAS), dtype=str,
        keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    )
    for parte in leitor:
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        nota_txt = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(nota_txt.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        validas = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(validas.sum())
        qa["status1_sem_nota"] += int((st1 & nota_txt.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & nota_txt.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((validas & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((validas & ~uf_ok & uf.ne("")).sum())
        registros_uf.update(uf.value_counts().to_dict())
        if validas.any():
            agrupadas = (pd.DataFrame({"uf": uf[validas], "nota": nota[validas]})
                         .groupby(["uf", "nota"], sort=False).size())
            for (sigla, valor), quantidade in agrupadas.items():
                if sigla in frequencias:
                    frequencias[sigla][float(valor)] += int(quantidade)
    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: fonte sem linhas")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: balanço TP_STATUS_REDACAO=1 inconsistente")
    if qa["status1_sem_nota"] or qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: notas inválidas ou ausentes entre status=1")
    if qa["validas_sem_uf"] or qa["validas_uf_desconhecida"]:
        raise ValueError(f"{ano}: redações válidas com UF ausente/desconhecida")
    if sum(registros_uf.values()) != qa["registros"]:
        raise ValueError(f"{ano}: balanço de registros por UF incorreto")
    conjunto_br = Counter()
    estados = []
    for sigla in UFS:
        conjunto_br.update(frequencias[sigla])
        r = resumo_frequencias(frequencias[sigla])
        if r["n_validas"] < 30:
            raise ValueError(f"{ano}/{sigla}: menos de 30 redações válidas")
        estados.append({"uf": sigla, **r, "total_registros": int(registros_uf[sigla])})
    brasil = {**resumo_frequencias(conjunto_br), "total_registros": qa["registros"]}
    if brasil["n_validas"] != qa["validas"]:
        raise ValueError(f"{ano}: soma das UFs diverge do Brasil")
    for idx in range(10):
        if sum(r["faixas"][idx]["quantidade"] for r in estados) != brasil["faixas"][idx]["quantidade"]:
            raise ValueError(f"{ano}: faixa {idx} diverge entre UFs e Brasil")
    return {
        "ano": ano, "arquivo_fonte": arquivo.name,
        "brasil": brasil, "ufs": estados,
        "qualidade": {
            "status": "ok", "status1_sem_nota": qa["status1_sem_nota"],
            "status1_nota_invalida": qa["status1_nota_invalida"],
            "validas_sem_uf": qa["validas_sem_uf"],
            "validas_uf_desconhecida": qa["validas_uf_desconhecida"],
            "soma_contagens_uf_igual_brasil": True,
            "soma_das_faixas_igual_populacao": True,
            "metodo": METODO,
        },
    }, frequencias


def conferir_grupo(atual: dict, prev: list[dict], contexto: str, historico: bool = False) -> None:
    r1, r2, r3, r4, r5 = prev
    n = atual["n_validas"]
    if n != r1["redacoes_validas"] or any(n != r["n_validas"] for r in prev[1:]):
        raise ValueError(f"{contexto}: população divergente dos IND-001–005")
    if not historico:
        if any(atual["total_registros"] != r["total_registros"] for r in prev):
            raise ValueError(f"{contexto}: quantidade total de registros divergente")
    if not math.isclose(atual["soma_notas"], r2["soma_notas"], rel_tol=0, abs_tol=0.01):
        raise ValueError(f"{contexto}: soma das notas divergente do IND-002")
    if atual["media"] != r2["media"] or atual["media"] != r4["media"]:
        raise ValueError(f"{contexto}: média divergente do IND-002 ou IND-004")
    if not math.isclose(atual["mediana"], r3["mediana"], rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{contexto}: mediana divergente do IND-003")
    if abs(atual["desvio_padrao"] - r4["desvio_padrao"]) > 0.0002:
        raise ValueError(f"{contexto}: desvio-padrão divergente do IND-004")
    for k, p in atual["percentis"].items():
        if not math.isclose(p, r5["percentis"][k], rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"{contexto}: percentil {k} diverge do IND-005")
    if sum(f["quantidade"] for f in atual["faixas"]) != n:
        raise ValueError(f"{contexto}: histograma não soma a população")


def validar_referencias(dados: list[dict], refs: dict[str, dict]) -> None:
    series = {i: {r["ano"]: r for r in j["years"]} for i, j in refs.items()}
    for atual in dados:
        ano = atual["ano"]
        anteriores = [series[f"IND-{i:03d}"][ano] for i in range(1, 6)]
        conferir_grupo(atual["brasil"], [x["brasil"] for x in anteriores], f"{ano}/BR")
        prev_ufs = [{x["uf"]: x for x in doc["ufs"]} for doc in anteriores]
        if any(set(p) != set(UFS) for p in prev_ufs):
            raise ValueError(f"{ano}: UFs das referências incompletas")
        for uf in atual["ufs"]:
            conferir_grupo(uf, [p[uf["uf"]] for p in prev_ufs], f"{ano}/{uf['uf']}")
        atual["qualidade"]["validado_contra_ind001_ind002_ind003_ind004_ind005"] = True


def consolidar_historico(dados: list[dict], freq_anuais: dict[int, dict[str, Counter[float]]],
                          refs: dict[str, dict]) -> dict:
    freq_h_ufs = {uf: Counter() for uf in UFS}
    for ano in ANOS:
        for uf in UFS:
            freq_h_ufs[uf].update(freq_anuais[ano][uf])
    historias = [refs[f"IND-{i:03d}"]["historical"] for i in range(1, 6)]
    prev_ufs = [{r["uf"]: r for r in h["ufs"]} for h in historias]
    conj_br = Counter()
    estados = []
    for uf in UFS:
        conj_br.update(freq_h_ufs[uf])
        r = {"uf": uf, **resumo_frequencias(freq_h_ufs[uf])}
        conferir_grupo(r, [x[uf] for x in prev_ufs], f"Histórico/{uf}", True)
        estados.append(r)
    brasil = resumo_frequencias(conj_br)
    conferir_grupo(brasil, [x["brasil"] for x in historias], "Histórico/BR", True)
    if brasil["n_validas"] != sum(x["brasil"]["n_validas"] for x in dados):
        raise ValueError("Histórico: população inconsistente")
    for i in range(10):
        if sum(x["brasil"]["faixas"][i]["quantidade"] for x in dados) != brasil["faixas"][i]["quantidade"]:
            raise ValueError(f"Histórico: divergência na faixa {i}")
    return {"periodo": "2019-2025", "brasil": brasil, "ufs": estados, "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    conjuntos = [(str(x["ano"]), x["brasil"], x["ufs"], x["arquivo_fonte"]) for x in dados]
    conjuntos.append(("2019-2025", historico["brasil"], historico["ufs"], "TODAS_AS_EDICOES"))
    linhas = []
    for periodo, brasil, ufs, fonte in conjuntos:
        grupos = [("BRASIL", "BR", brasil)] + [("UF", r["uf"], r) for r in ufs]
        for abrangencia, uf, resumo in grupos:
            for faixa in resumo["faixas"]:
                linhas.append({
                    "indicador_id": INDICADOR, "periodo": periodo,
                    "abrangencia": abrangencia, "uf": uf,
                    "faixa": faixa["faixa"],
                    "limite_inferior": faixa["limite_inferior"],
                    "limite_superior": faixa["limite_superior"],
                    "superior_inclusivo": faixa["superior_inclusivo"],
                    "n_validas": resumo["n_validas"],
                    "quantidade": faixa["quantidade"],
                    "proporcao": faixa["proporcao"],
                    "percentual": faixa["percentual"],
                    "metodo": METODO, "arquivo_fonte": fonte,
                })
    if len(linhas) != 2240:
        raise AssertionError(f"Esperadas 2240 linhas, obtidas {len(linhas)}")
    return linhas


def construir_dashboard(d: dict, dados: list[dict], hist: dict,
                         base: dict, refs_ano: dict[str, dict], gerado: str) -> dict:
    ano = d["ano"]
    painel = deepcopy(base)
    overview = painel["pages"]["overview"]
    br = d["brasil"]
    k = overview["kpis"]
    if (k.get("valid_essays") != br["n_validas"] or
            k.get("mean_score") != br["media"] or
            not math.isclose(k.get("median_score"), br["mediana"], abs_tol=1e-6) or
            abs(k.get("std_score") - br["desvio_padrao"]) > 0.0002):
        raise ValueError(f"{ano}: KPIs IND-001–004 divergentes")
    if k.get("percentiles") != br["percentis"]:
        raise ValueError(f"{ano}: percentis no KPI divergem do IND-005")
    for i in range(1, 6):
        chave = f"ind{i:03d}"
        por_uf = {x["uf"]: x for x in overview[chave]["by_uf"]}
        if set(por_uf) != set(UFS):
            raise ValueError(f"{ano}: {chave} não tem 27 UFs")
        for r in d["ufs"]:
            n_uf = por_uf[r["uf"]].get("redacoes_validas" if i == 1 else "n")
            if n_uf != r["n_validas"]:
                raise ValueError(f"{ano}/{r['uf']}: {chave} com população divergente")
    painel["meta"]["analysis_version"] = VERSAO
    painel["meta"]["generated_at"] = gerado
    painel["meta"]["data_status"] = "draft"
    aviso = "IND-006 validado computacionalmente; publicação acadêmica pendente."
    if aviso not in painel["meta"].setdefault("warnings", []):
        painel["meta"]["warnings"].append(aviso)
    # Contrato do catálogo: pages.overview.score_distribution
    overview["score_distribution"] = {
        "indicator_id": INDICADOR, "unit": "redacoes",
        "n": br["n_validas"], "method": METODO,
        "bins": br["faixas"],
        "by_uf": [{"uf": r["uf"], "n": r["n_validas"], "bins": r["faixas"]}
                  for r in d["ufs"]],
    }
    painel["pages"]["temporal"]["ind006"] = {
        "indicator_id": INDICADOR, "method": METODO,
        "national_by_year": [{"year": x["ano"], "n": x["brasil"]["n_validas"],
                              "bins": x["brasil"]["faixas"]} for x in dados],
        "period_total": {"n": hist["brasil"]["n_validas"],
                         "bins": hist["brasil"]["faixas"]},
        "period_by_uf": [{"uf": r["uf"], "n": r["n_validas"], "bins": r["faixas"]}
                         for r in hist["ufs"]],
        "note": NOTA_HISTORICA,
    }
    painel["pages"]["methodology"]["ind006"] = {
        "definition": DEFINICAO,
        "calculation": "Faixas [0,100), ..., [800,900), [900,1000]; count e count/N",
        "population": "POP_VALID, a mesma dos indicadores IND-001 a IND-005",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "precision": "proporção com 8 casas; percentual com 4 casas",
        "historical_note": NOTA_HISTORICA,
    }
    painel["quality"]["ind006_validation"] = d["qualidade"]
    return painel


def validar_dashboard(painel: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(painel):
        raise ValueError("Dashboard sem chaves obrigatórias")
    if not {"overview", "competencies", "evaluators", "high_performance",
            "socioeconomic", "ml", "methodology"}.issubset(painel["pages"]):
        raise ValueError("Dashboard sem páginas do contrato")
    if "NU_INSCRICAO" in json.dumps(painel, ensure_ascii=False):
        raise ValueError("Identificador individual detectado")
    candidatos = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    schema = next((p for p in candidatos if p.is_file()), None)
    if schema is None:
        return "validação estrutural básica (schema não encontrado)"
    try:
        import jsonschema
    except ImportError:
        return "validação estrutural básica (instale jsonschema)"
    with schema.open(encoding="utf-8") as arq:
        jsonschema.validate(painel, json.load(arq))
    return "validado pelo JSON Schema v1.0.0"


def salvar_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".json.tmp")
    with temporario.open("w", encoding="utf-8") as arq:
        json.dump(dados, arq, ensure_ascii=False, indent=2, allow_nan=False)
        arq.write("\n")
    temporario.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".csv.tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as arq:
        escritor = csv.DictWriter(arq, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    refs, dashboards_base = carregar_referencias(raiz)
    dados = []
    freq_anuais = {}
    for ano in ANOS:
        print(f"IND-006 | {ano}: processando {origem(ano, raiz).name}...", flush=True)
        d, freq = processar_ano(ano, raiz, bloco)
        dados.append(d)
        freq_anuais[ano] = freq
        br = d["brasil"]
        print(f"  Brasil: N={br['n_validas']:,} | "
              f"10 faixas | UFs={len(d['ufs'])} | soma faixas={sum(f['quantidade'] for f in br['faixas']):,}",
              flush=True)
    validar_referencias(dados, refs)
    historico = consolidar_historico(dados, freq_anuais, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    refs_anos = {i: {x["ano"]: x for x in ref["years"]} for i, ref in refs.items()}
    dashboards = {
        d["ano"]: construir_dashboard(
            d, dados, historico, dashboards_base[d["ano"]],
            {i: r[d["ano"]] for i, r in refs_anos.items()}, gerado,
        ) for d in dados
    }
    validacoes = {validar_dashboard(p, raiz) for p in dashboards.values()}
    modulo = {
        "meta": {
            "indicator_id": INDICADOR,
            "module_schema_version": "ind006-module-1.0.0",
            "analysis_version": VERSAO,
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado,
            "data_status": "draft",
            "source_files": {str(x["ano"]): x["arquivo_fonte"] for x in dados},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001_ind002_ind003_ind004_ind005": "aprovada (N, soma, média, mediana, desvio-padrão e percentis)",
            "method": METODO,
            "bin_edges": list(LIMITES),
            "last_bin_right_inclusive": True,
        },
        "indicator": {
            "id": INDICADOR, "name": "Distribuição das notas da redação",
            "unit": "redacoes", "dashboard_json_path": "pages.overview.score_distribution",
        },
        "years": dados,
        "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)
    saida = raiz / "outputs"
    salvar_csv(saida / "indicadores" / "IND_006_distribuicao_notas.csv", linhas)
    salvar_json(saida / "json" / "IND_006_distribuicao_notas.json", modulo)
    for ano in ANOS:
        salvar_json(saida / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    print("\nConcluído! Arquivos gerados:")
    print("  outputs/indicadores/IND_006_distribuicao_notas.csv (2240 linhas)")
    print("  outputs/json/IND_006_distribuicao_notas.json")
    print("  outputs/json/dashboard_enem_AAAA.json (sete dashboards cumulativos)")
    print("  Validação: " + ", ".join(sorted(validacoes)))
    print(f"  Histórico: N={historico['brasil']['n_validas']:,} | "
          f"soma faixas={sum(f['quantidade'] for f in historico['brasil']['faixas']):,}")
    print("  STATUS: draft (revisão acadêmica pendente)")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-006 — Distribuição de notas ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="Raiz do repositório (padrão: duas pastas acima do script)")
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO,
                        help="Quantidade de linhas por bloco do pandas")
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
