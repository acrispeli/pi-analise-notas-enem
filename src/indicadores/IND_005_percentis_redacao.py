# -*- coding: utf-8 -*-
"""IND-005 — Percentis P25, P50, P75, P90 e P95 da redação ENEM 2019–2025.

População POP_VALID: TP_STATUS_REDACAO = 1, NU_NOTA_REDACAO numérica
entre 0 e 1000 (inclusive); UF é SG_UF_PROVA (local de aplicação).

O método é o quantil empírico interpolado linearmente (Hyndman–Fan tipo 7),
igual ao padrão de pandas.Series.quantile e numpy.quantile(method='linear'):
para p entre 0 e 1, a posição é h=(N-1)*p, com interpolação entre os
valores ordenados das posições floor(h) e ceil(h), numeradas de zero.
A contagem exata de cada valor de nota é acumulada por UF; nenhum registro
individual é exportado e não há amostragem. O consolidado histórico é obtido
pela união das frequências de 2019–2025, NÃO pelos percentis anuais.

Pré-requisitos na raiz do projeto:
    outputs/json/IND_001_redacoes_validas.json
    outputs/json/IND_002_nota_media.json
    outputs/json/IND_003_mediana_redacao.json
    outputs/json/IND_004_desvio_padrao_redacao.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

Fontes:
    2019–2023: data/raw/ANO/MICRODADOS_ENEM_ANO.csv
    2024–2025: data/raw/ANO/RESULTADOS_ANO.csv

PowerShell na raiz do repositório:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_005_percentis_redacao.py

Saídas após validações dos sete anos e integrações:
    outputs/indicadores/IND_005_percentis_redacao.csv (224 linhas)
    outputs/json/IND_005_percentis_redacao.json
    outputs/json/dashboard_enem_ANO.json (sete arquivos cumulativos)

Não altera os módulos IND-001 a IND-004 e não altera o Streamlit.
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
INDICADOR = "IND-005"
VERSAO = "2.4.0-ind001-ind002-ind003-ind004-ind005"
PERCENTIS = {"p25": 0.25, "p50": 0.5, "p75": 0.75, "p90": 0.9, "p95": 0.95}
DEFINICAO = (
    "Percentis P25, P50, P75, P90 e P95 da nota NU_NOTA_REDACAO, para "
    "TP_STATUS_REDACAO = 1 e nota numérica entre 0 e 1000, inclusive; "
    "por ano, Brasil e UF de aplicação (SG_UF_PROVA)."
)
METODO = "quantil_empirico_interpolacao_linear_hf7"
NOTA_HISTORICA = (
    "Percentis históricos calculados sobre a distribuição conjunta de todas "
    "as redações válidas de 2019–2025, e não sobre médias de percentis anuais. "
    "O método de interpolação linear é o padrão do Pandas/NumPy (tipo 7). "
    "O consolidado contabiliza participações, não pessoas únicas, e a UF "
    "representa o local de aplicação da prova, não a residência."
)


def origem(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {caminho}")
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def carregar_referencias(raiz: Path) -> tuple[dict[str, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    refs = {}
    for i in range(1, 5):
        nome = f"IND_{i:03d}_" + {
            1: "redacoes_validas", 2: "nota_media", 3: "mediana_redacao",
            4: "desvio_padrao_redacao",
        }[i] + ".json"
        doc = ler_json(pasta / nome)
        identificador = f"IND-{i:03d}"
        if doc.get("indicator", {}).get("id") != identificador:
            raise ValueError(f"{nome}: identificação do indicador incorreta")
        if sorted(item["ano"] for item in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"{nome}: série anual incompleta")
        if len(doc.get("historical", {}).get("ufs", [])) != 27:
            raise ValueError(f"{nome}: histórico não contém 27 UFs")
        refs[identificador] = doc
    dashboards = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"{ano}: dashboard com ano incorreto")
        visao = painel.get("pages", {}).get("overview", {})
        if any(f"ind{i:03d}" not in visao for i in range(1, 5)):
            raise ValueError(f"{ano}: dashboard precisa conter IND-001 a IND-004")
        dashboards[ano] = painel
    return refs, dashboards


def selecionar_posicoes(frequencias: Counter[float], posicoes: set[int]) -> dict[int, float]:
    """Recupera observações ordenadas em posições zero-based sem expandir dados."""
    if not posicoes:
        return {}
    n = sum(frequencias.values())
    if min(posicoes) < 0 or max(posicoes) >= n:
        raise ValueError("Posição de quantil fora dos limites")
    pedidos = sorted(posicoes)
    saida: dict[int, float] = {}
    j = 0
    acumulado = 0
    for nota, freq in sorted(frequencias.items()):
        if not math.isfinite(nota) or not 0 <= nota <= 1000 or freq <= 0:
            raise ValueError(f"Frequência de nota inválida: {nota}: {freq}")
        proximo = acumulado + freq
        while j < len(pedidos) and pedidos[j] < proximo:
            if pedidos[j] < acumulado:
                raise AssertionError("Posições inconsistentes")
            saida[pedidos[j]] = float(nota)
            j += 1
        acumulado = proximo
        if j == len(pedidos):
            break
    if len(saida) != len(pedidos):
        raise AssertionError("Falha ao recuperar as observações do quantil")
    return saida


def quantis_frequencias(frequencias: Counter[float]) -> dict[str, float] | None:
    """Quantis exatos para a distribuição de notas, com interpolação HF7.

    Equivalente ao numpy.quantile(method='linear'), sem expandir contagens.
    """
    n = sum(frequencias.values())
    if n <= 0:
        return None
    extremos: dict[str, tuple[int, int, float]] = {}
    indices = set()
    for nome, p in PERCENTIS.items():
        h = (n - 1) * p
        esquerda = math.floor(h)
        direita = math.ceil(h)
        alfa = h - esquerda
        extremos[nome] = (esquerda, direita, alfa)
        indices.update((esquerda, direita))
    valores = selecionar_posicoes(frequencias, indices)
    return {
        nome: round((1.0 - alfa) * valores[i] + alfa * valores[j], 6)
        for nome, (i, j, alfa) in extremos.items()
    }


def resumir_frequencias(freq: Counter[float]) -> dict:
    n = sum(freq.values())
    if n == 0:
        return {"n_validas": 0, "percentis": None, "iqr": None,
                "soma_notas": 0.0, "media": None, "desvio_padrao": None}
    soma = math.fsum(nota * quantidade for nota, quantidade in freq.items())
    media = soma / n
    var = math.fsum(quantidade * (nota - media) ** 2
                    for nota, quantidade in freq.items()) / n
    percentis = quantis_frequencias(freq)
    assert percentis is not None
    return {
        "n_validas": n,
        "percentis": percentis,
        "iqr": round(percentis["p75"] - percentis["p25"], 6),
        "soma_notas": round(soma, 6),
        "media": round(media, 4),
        "desvio_padrao": round(math.sqrt(var), 4),
    }


def processar_ano(ano: int, raiz: Path, bloco: int) -> tuple[dict, dict[str, Counter[float]]]:
    arquivo = origem(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Microdados não encontrados: {arquivo}")
    freqs = {uf: Counter() for uf in UFS}
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
        nota_bruta = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(nota_bruta.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        valida = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(valida.sum())
        qa["status1_sem_nota"] += int((st1 & nota_bruta.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & nota_bruta.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((valida & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((valida & ~uf_ok & uf.ne("")).sum())
        registros_uf.update(uf.value_counts().to_dict())
        if valida.any():
            grupos = (pd.DataFrame({"uf": uf[valida], "nota": nota[valida]})
                      .groupby(["uf", "nota"], sort=False).size())
            for (sigla, valor), quantidade in grupos.items():
                if sigla in freqs:
                    freqs[sigla][float(valor)] += int(quantidade)

    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: arquivo de origem sem linhas")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: balanço de redações status=1 inconsistente")
    if qa["status1_sem_nota"] or qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: notas inválidas/ausentes para redações status=1")
    if qa["validas_sem_uf"] or qa["validas_uf_desconhecida"]:
        raise ValueError(f"{ano}: há redações válidas sem UF conhecida")
    if sum(registros_uf.values()) != qa["registros"]:
        raise ValueError(f"{ano}: contagem total de UFs não fecha")
    freq_br = Counter()
    ufs = []
    for uf in UFS:
        freq_br.update(freqs[uf])
        resumo = resumir_frequencias(freqs[uf])
        if 0 < resumo["n_validas"] < 30:
            raise ValueError(f"{ano}/{uf}: menos de 30 redações válidas")
        ufs.append({"uf": uf, **resumo, "total_registros": int(registros_uf[uf])})
    brasil = {**resumir_frequencias(freq_br), "total_registros": qa["registros"]}
    if brasil["n_validas"] != qa["validas"]:
        raise ValueError(f"{ano}: soma das 27 UFs diverge do Brasil")
    return {
        "ano": ano, "arquivo_fonte": arquivo.name,
        "brasil": brasil, "ufs": ufs,
        "qualidade": {
            "status": "ok",
            "status1_sem_nota": qa["status1_sem_nota"],
            "status1_nota_invalida": qa["status1_nota_invalida"],
            "validas_sem_uf": qa["validas_sem_uf"],
            "validas_uf_desconhecida": qa["validas_uf_desconhecida"],
            "soma_contagens_uf_igual_brasil": True,
            "metodo": METODO,
        }
    }, freqs


def conferir_grupo(atual: dict, anteriores: list[dict], contexto: str,
                    historico: bool = False) -> None:
    r1, r2, r3, r4 = anteriores
    if not (atual["n_validas"] == r1["redacoes_validas"] ==
            r2["n_validas"] == r3["n_validas"] == r4["n_validas"]):
        raise ValueError(f"{contexto}: N diverge dos IND-001 a IND-004")
    if not historico:
        if not (atual["total_registros"] == r1["total_registros"] ==
                r2["total_registros"] == r3["total_registros"] == r4["total_registros"]):
            raise ValueError(f"{contexto}: total de registros diverge")
    if not math.isclose(atual["soma_notas"], r2["soma_notas"], rel_tol=0, abs_tol=0.01):
        raise ValueError(f"{contexto}: soma de notas diverge do IND-002")
    if atual["media"] != r2["media"] or atual["media"] != r4["media"]:
        raise ValueError(f"{contexto}: média diverge do IND-002/004")
    if atual["percentis"] is None:
        raise ValueError(f"{contexto}: sem percentis (N = 0)")
    if not math.isclose(atual["percentis"]["p50"], r3["mediana"], abs_tol=1e-6, rel_tol=0):
        raise ValueError(f"{contexto}: P50 diverge da mediana do IND-003")
    if abs(atual["desvio_padrao"] - r4["desvio_padrao"]) > 0.0002:
        raise ValueError(f"{contexto}: desvio-padrão diverge do IND-004")
    if any(not 0 <= atual["percentis"][nome] <= 1000 for nome in PERCENTIS):
        raise ValueError(f"{contexto}: percentis fora do intervalo [0,1000]")
    valores = list(atual["percentis"].values())
    if valores != sorted(valores):
        raise ValueError(f"{contexto}: percentis não monotônicos")


def validar_referencias(dados: list[dict], refs: dict[str, dict]) -> None:
    series = {
        ident: {d["ano"]: d for d in doc["years"]} for ident, doc in refs.items()
    }
    for reg in dados:
        ano = reg["ano"]
        grupos = [series[ident][ano] for ident in sorted(refs)]
        conferir_grupo(reg["brasil"], [d["brasil"] for d in grupos], f"{ano}/BR")
        estados = [{v["uf"]: v for v in d["ufs"]} for d in grupos]
        if any(set(estados[i]) != set(UFS) for i in range(4)):
            raise ValueError(f"{ano}: indicador anterior com UFs incompletas")
        for r in reg["ufs"]:
            conferir_grupo(r, [por_uf[r["uf"]] for por_uf in estados],
                           f"{ano}/{r['uf']}")
        reg["qualidade"]["validado_contra_ind001_ind002_ind003_ind004"] = True


def consolidar_historico(dados: list[dict], frequencias: dict[int, dict[str, Counter]],
                          refs: dict[str, dict]) -> dict:
    conj_uf = {uf: Counter() for uf in UFS}
    for ano in ANOS:
        for uf in UFS:
            conj_uf[uf].update(frequencias[ano][uf])
    conj_br = Counter()
    hist_ref = [refs[i]["historical"] for i in sorted(refs)]
    hist_ufs = [{r["uf"]: r for r in h["ufs"]} for h in hist_ref]
    saida_ufs = []
    for uf in UFS:
        conj_br.update(conj_uf[uf])
        r = {"uf": uf, **resumir_frequencias(conj_uf[uf])}
        conferir_grupo(r, [d[uf] for d in hist_ufs], f"Histórico/{uf}", historico=True)
        saida_ufs.append(r)
    brasil = resumir_frequencias(conj_br)
    conferir_grupo(brasil, [h["brasil"] for h in hist_ref], "Histórico/BR", historico=True)
    if brasil["n_validas"] != sum(d["brasil"]["n_validas"] for d in dados):
        raise ValueError("Histórico/BR: N não corresponde à soma das edições")
    return {"periodo": "2019-2025", "brasil": brasil, "ufs": saida_ufs,
            "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    grupos = [(str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"]) for d in dados]
    grupos.append(("2019-2025", historico["brasil"], historico["ufs"], "TODAS_AS_EDICOES"))
    linhas = []
    for periodo, br, ufs, origem_nome in grupos:
        for abrangencia, uf, r in [("BRASIL", "BR", br)] + [("UF", x["uf"], x) for x in ufs]:
            linhas.append({
                "indicador_id": INDICADOR,
                "periodo": periodo,
                "abrangencia": abrangencia,
                "uf": uf,
                "n_validas": r["n_validas"],
                **(r["percentis"] or {k: None for k in PERCENTIS}),
                "amplitude_interquartil": r["iqr"],
                "metodo": METODO,
                "arquivo_fonte": origem_nome,
            })
    if len(linhas) != 224:
        raise AssertionError(f"CSV precisa conter 224 linhas, gerou {len(linhas)}")
    return linhas


def construir_dashboard(d: dict, dados: list[dict], hist: dict,
                        base: dict, refs_ano: dict[str, dict], gerado: str) -> dict:
    ano = d["ano"]
    painel = deepcopy(base)
    overview = painel["pages"]["overview"]
    kpis = overview["kpis"]
    br = d["brasil"]
    if kpis.get("valid_essays") != br["n_validas"]:
        raise ValueError(f"{ano}: KPI valid_essays inconsistente")
    if (kpis.get("mean_score") != refs_ano["IND-002"]["brasil"]["media"] or
            kpis.get("median_score") != br["percentis"]["p50"] or
            kpis.get("std_score") != refs_ano["IND-004"]["brasil"]["desvio_padrao"]):
        raise ValueError(f"{ano}: KPIs do IND-002/003/004 inconsistentes")
    for i in range(1, 5):
        chave = f"ind{i:03d}"
        encontrados = {r["uf"]: r for r in overview[chave]["by_uf"]}
        if set(encontrados) != set(UFS):
            raise ValueError(f"{ano}: {chave} não contém 27 UFs")
        for u in d["ufs"]:
            if encontrados[u["uf"]].get("redacoes_validas" if i == 1 else "n") != u["n_validas"]:
                raise ValueError(f"{ano}/{u['uf']}: N divergente em {chave}")
    painel["meta"]["analysis_version"] = VERSAO
    painel["meta"]["generated_at"] = gerado
    painel["meta"]["data_status"] = "draft"
    aviso = "IND-005 validado computacionalmente; publicação acadêmica pendente."
    if aviso not in painel["meta"].setdefault("warnings", []):
        painel["meta"]["warnings"].append(aviso)
    kpis["percentiles"] = br["percentis"]
    overview["ind005"] = {
        "indicator_id": INDICADOR, "unit": "pontos", "n": br["n_validas"],
        "percentiles": br["percentis"], "iqr": br["iqr"],
        "by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                   "percentiles": u["percentis"], "iqr": u["iqr"]} for u in d["ufs"]],
    }
    painel["pages"]["temporal"]["ind005"] = {
        "indicator_id": INDICADOR,
        "method": METODO,
        "national_by_year": [
            {"year": x["ano"], "n": x["brasil"]["n_validas"],
             "percentiles": x["brasil"]["percentis"], "iqr": x["brasil"]["iqr"]}
            for x in dados
        ],
        "period_total": {"n": hist["brasil"]["n_validas"],
                         "percentiles": hist["brasil"]["percentis"],
                         "iqr": hist["brasil"]["iqr"]},
        "period_by_uf": [{"uf": x["uf"], "n": x["n_validas"],
                          "percentiles": x["percentis"], "iqr": x["iqr"]}
                         for x in hist["ufs"]],
        "note": NOTA_HISTORICA,
    }
    painel["pages"]["methodology"]["ind005"] = {
        "definition": DEFINICAO,
        "calculation": "Quantil tipo 7: h=(N-1)*p, com interpolação linear entre posições ordenadas",
        "population": "POP_VALID, a mesma dos indicadores IND-001 a IND-004",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "precision": "Até 6 casas decimais (interpolação); em geral notas múltiplas de 20",
        "historical_note": NOTA_HISTORICA,
    }
    painel["quality"]["ind005_validation"] = d["qualidade"]
    return painel


def validar_dashboard(painel: dict, raiz: Path) -> str:
    required = {"meta", "filters", "quality", "pages"}
    if not required.issubset(painel):
        raise ValueError("Dashboard sem blocos principais do contrato")
    paginas = {"overview", "competencies", "evaluators", "high_performance",
               "socioeconomic", "ml", "methodology"}
    if not paginas.issubset(painel["pages"]):
        raise ValueError("Dashboard sem todas as páginas obrigatórias")
    raw = json.dumps(painel, ensure_ascii=False, allow_nan=False)
    if "NU_INSCRICAO" in raw or "NU_SEQUENCIAL" in raw:
        raise ValueError("Identificador de participante detectado no dashboard")
    candidatos = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    caminho = next((p for p in candidatos if p.is_file()), None)
    if caminho is None:
        return "validação estrutural básica (schema não encontrado)"
    try:
        import jsonschema
    except ImportError:
        return "validação estrutural básica (instale jsonschema)"
    with caminho.open(encoding="utf-8") as arq:
        jsonschema.validate(painel, json.load(arq))
    return "validado pelo JSON Schema v1.0.0"


def salvar_json(caminho: Path, doc: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as arq:
        json.dump(doc, arq, ensure_ascii=False, indent=2, allow_nan=False)
        arq.write("\n")
    temp.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_suffix(".csv.tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as arq:
        writer = csv.DictWriter(arq, fieldnames=list(linhas[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    temp.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    refs, bases = carregar_referencias(raiz)
    anos = []
    frequencias = {}
    for ano in ANOS:
        print(f"IND-005 | {ano}: processando {origem(ano, raiz).name}...", flush=True)
        reg, contagens = processar_ano(ano, raiz, bloco)
        anos.append(reg)
        frequencias[ano] = contagens
        p = reg["brasil"]["percentis"]
        print(f"  Brasil: n={reg['brasil']['n_validas']:,} | "
              f"P25={p['p25']:.2f} P50={p['p50']:.2f} "
              f"P75={p['p75']:.2f} P90={p['p90']:.2f} "
              f"P95={p['p95']:.2f} | 27 UFs", flush=True)
    validar_referencias(anos, refs)
    historico = consolidar_historico(anos, frequencias, refs)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    serie_anteriores = {
        ident: {x["ano"]: x for x in doc["years"]}
        for ident, doc in refs.items()
    }
    dashboards = {}
    for d in anos:
        ano = d["ano"]
        dashboards[ano] = construir_dashboard(
            d, anos, historico, bases[ano],
            {ident: reg[ano] for ident, reg in serie_anteriores.items()}, timestamp,
        )
    validacoes = {validar_dashboard(doc, raiz) for doc in dashboards.values()}
    modulo = {
        "meta": {
            "indicator_id": INDICADOR,
            "module_schema_version": "ind005-module-1.0.0",
            "analysis_version": VERSAO,
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": timestamp,
            "data_status": "draft",
            "source_files": {str(r["ano"]): r["arquivo_fonte"] for r in anos},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001_ind002_ind003_ind004": "aprovada (N, soma, média, mediana e desvio-padrão)",
            "method": METODO,
            "quantile_probabilities": PERCENTIS,
        },
        "indicator": {
            "id": INDICADOR,
            "name": "Percentis da nota da redação",
            "unit": "pontos",
            "dashboard_json_path": "pages.overview.ind005.percentiles",
        },
        "years": anos,
        "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(anos, historico)
    salvar_csv(raiz / "outputs" / "indicadores" / "IND_005_percentis_redacao.csv", linhas)
    salvar_json(raiz / "outputs" / "json" / "IND_005_percentis_redacao.json", modulo)
    for ano in ANOS:
        salvar_json(raiz / "outputs" / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    print("\nConcluído! Arquivos de saída:")
    print("  outputs/indicadores/IND_005_percentis_redacao.csv")
    print("  outputs/json/IND_005_percentis_redacao.json")
    print("  outputs/json/dashboard_enem_AAAA.json (7 dashboards cumulativos)")
    print(f"  Validação: {', '.join(sorted(validacoes))}")
    print("  Percentis históricos: " + str(historico["brasil"]["percentis"]))
    print("  STATUS: draft (aguarda revisão acadêmica)")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-005 — Percentis ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="Raiz do projeto (padrão: duas pastas acima do script)")
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO,
                        help="Tamanho de bloco do pandas (padrão: 100000)")
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
