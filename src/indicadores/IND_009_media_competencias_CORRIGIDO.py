# -*- coding: utf-8 -*-
"""IND-009 — Média das competências C1–C5 da redação do ENEM (2019–2025).

Catálogo: Competências / Média C1–C5 / POP_VALID / média por competência.
Destino: pages.competencies.summary (array; barras no frontend).

Requer IND-001, IND-002, IND-007, IND-008 e dashboards IND-001–008
já gerados em outputs/json. Execute após a conclusão do IND-008.

PowerShell (na raiz do repositório):
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_009_media_competencias.py

Saídas:
    outputs/indicadores/IND_009_media_competencias.csv (1.120 linhas)
    outputs/json/IND_009_media_competencias.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

Todas as competências valem 0–200. A população é a do IND-001:
TP_STATUS_REDACAO=1 e NU_NOTA_REDACAO numericamente válida em [0,1000].
Em POP_VALID, as cinco competências precisam estar presentes e entre 0 e 200.
Se a soma C1–C5 não bater com NU_NOTA_REDACAO, o registro com competências
válidas continua em POP_VALID; a divergência é contabilizada e auditada por
UF/ano, sem correção ou imputação de nenhuma nota. Competências ausentes ou
fora da escala continuam interrompendo a execução antes da exportação.
O histórico reúne participações, não indivíduos distintos. SG_UF_PROVA
representa a UF de aplicação, não residência. Resultados permanecem DRAFT.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()))
COMP = tuple(f"NU_NOTA_COMP{i}" for i in range(1, 6))
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO", *COMP)
INDICADOR = "IND-009"
VERSAO = "2.8.1-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009"
METODO = "media_aritmetica_competencias_pop_valid"
TAMANHO_BLOCO = 100_000
LIMIAR_POP_VALID = 30
DEFINICAO = (
    "Média aritmética de NU_NOTA_COMP1 a NU_NOTA_COMP5, calculada "
    "separadamente para cada competência (0 a 200 pontos), entre as redações "
    "válidas (TP_STATUS_REDACAO=1 e NU_NOTA_REDACAO numérica de 0 a 1000)."
)
NOTA_HISTORICA = (
    "O consolidado 2019–2025 usa a soma de cada competência dividida pelo "
    "total de redações válidas de todas as edições (média ponderada pelo N). "
    "São participações, não pessoas únicas. SG_UF_PROVA é a UF de aplicação, "
    "não o estado de residência. Comparações são descritivas."
)
ROTULOS = (
    "Domínio da modalidade escrita formal da língua portuguesa",
    "Compreensão da proposta e desenvolvimento do tema",
    "Seleção, organização e interpretação de informações e argumentos",
    "Conhecimento dos mecanismos linguísticos de argumentação",
    "Elaboração de proposta de intervenção",
)


def fonte(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo pré-requisito não encontrado: {caminho}")
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def carregar_referencias(raiz: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    nomes = {1: "redacoes_validas", 2: "nota_media", 7: "situacao_redacao", 8: "notas_1000"}
    refs = {}
    for i, nome in nomes.items():
        doc = ler_json(pasta / f"IND_{i:03d}_{nome}.json")
        if doc.get("indicator", {}).get("id") != f"IND-{i:03d}":
            raise ValueError(f"Referência IND-{i:03d} com identificador incompatível")
        if sorted(d.get("ano") for d in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"Referência IND-{i:03d} sem os sete anos")
        for item in (*doc["years"], doc.get("historical", {})):
            if len(item.get("ufs", [])) != len(UFS) or {u.get("uf") for u in item["ufs"]} != set(UFS):
                raise ValueError(f"IND-{i:03d}: 27 UFs ausentes ou duplicadas")
        refs[i] = doc
    dashboards = {}
    for ano in ANOS:
        p = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if p.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}.json: ano inconsistente")
        overview = p.get("pages", {}).get("overview", {})
        for i in range(1, 6):
            if f"ind{i:03d}" not in overview:
                raise ValueError(f"Dashboard {ano} sem IND-{i:03d}")
        if not all(k in overview for k in ("score_distribution", "essay_status", "ind008")):
            raise ValueError(f"Dashboard {ano} sem IND-006, IND-007 ou IND-008; aguarde a execução deles")
        if p.get("quality", {}).get("ind008_validation", {}).get("status") != "ok":
            raise ValueError(f"Dashboard {ano}: IND-008 ainda não concluído")
        if p.get("pages", {}).get("competencies", {}).get("status") not in ("unavailable", "ok"):
            raise ValueError(f"Dashboard {ano}: página de competências em estado inesperado")
        dashboards[ano] = p
    return refs, dashboards


def competencias_de_somas(n: int, somas: list[float]) -> list[dict]:
    if n <= 0 or len(somas) != 5:
        raise ValueError("Quantidade/competências inválidas")
    resultado = []
    for i, soma in enumerate(somas, 1):
        if not math.isfinite(soma) or not -0.001 <= soma <= 200*n + 0.001:
            raise ValueError(f"Soma impossível de C{i}: {soma} (n={n})")
        resultado.append({
            "competencia": f"C{i}", "variavel": COMP[i-1], "descricao": ROTULOS[i-1],
            "n": n, "soma_notas": round(float(soma), 6),
            "media": round(float(soma) / n, 4), "escala_maxima": 200,
        })
    return resultado


def preparar_grupo(n: int, somas: list[float], total: int | None = None,
                   soma_nota_redacao: float | None = None,
                   n_somas_divergentes: int = 0) -> dict:
    d = {"n_validas": int(n), "competencias": competencias_de_somas(n, somas)}
    if total is not None:
        d["total_registros"] = int(total)
    if soma_nota_redacao is not None:
        d["soma_nota_redacao"] = round(float(soma_nota_redacao), 6)
        d["delta_soma_competencias_menos_nota_redacao"] = round(
            math.fsum(somas) - float(soma_nota_redacao), 6)
        d["n_somas_divergentes"] = int(n_somas_divergentes)
    return d


def validar_soma_competencias(d: dict, soma_nota: float, contexto: str) -> None:
    # A nota total dos microdados deve fechar COM IND-002; a soma das cinco
    # competências pode divergir da nota total em registros da fonte.
    soma_fonte = float(d["soma_nota_redacao"])
    if not math.isclose(soma_fonte, float(soma_nota), rel_tol=0.0, abs_tol=0.02):
        raise ValueError(f"{contexto}: soma NU_NOTA_REDACAO difere de IND-002 ({soma_fonte} vs. {soma_nota})")
    soma_c = math.fsum(c["soma_notas"] for c in d["competencias"])
    delta = float(d["delta_soma_competencias_menos_nota_redacao"])
    if not math.isclose(soma_c - soma_fonte, delta, rel_tol=0.0, abs_tol=0.02):
        raise ValueError(f"{contexto}: divergência calculada não fecha (C1–C5={soma_c}, nota={soma_fonte}, delta={delta})")
    if not d["n_somas_divergentes"] and abs(delta) > 0.02:
        raise ValueError(f"{contexto}: divergência sem registro de qualidade")


def processar_ano(ano: int, raiz: Path, bloco: int = TAMANHO_BLOCO) -> dict:
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Microdados não encontrados: {caminho}")
    qa = Counter()
    totais_uf = Counter()
    ns_uf = Counter({u: 0 for u in UFS})
    somas_uf = defaultdict(lambda: [0.0]*5)
    soma_br = [0.0]*5
    somas_totais_uf = defaultdict(float)
    soma_total_br = 0.0
    divergencias_uf = Counter()
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
        valida = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(valida.sum())
        qa["status1_sem_nota"] += int((st1 & nota_txt.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & nota_txt.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((valida & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((valida & ~uf_ok & uf.ne("")).sum())
        totais_uf.update({str(k): int(v) for k,v in uf.value_counts().items()})
        if not bool(valida.any()):
            continue
        raw = parte.loc[valida, COMP].apply(lambda c: c.str.strip())
        valores = raw.apply(lambda c: pd.to_numeric(c.str.replace(",", ".", regex=False), errors="coerce"))
        valid_comp = valores.notna() & valores.ge(0) & valores.le(200)
        # Os valores ausentes, inválidos e fora da escala nunca são imputados.
        for i, c in enumerate(COMP, 1):
            qa[f"c{i}_ausente"] += int(raw[c].eq("").sum())
            qa[f"c{i}_invalida"] += int((raw[c].ne("") & ~valid_comp[c]).sum())
        completas = valid_comp.all(axis=1)
        qa["validas_competencias_incompletas"] += int((~completas).sum())
        soma_linha = valores.sum(axis=1)
        igual_total = (soma_linha - nota.loc[valida]).abs().le(0.000001)
        divergentes = completas & ~igual_total
        qa["validas_soma_competencias_divergente"] += int(divergentes.sum())
        divergencias_uf.update({str(k): int(v) for k, v in
                                uf.loc[valida].loc[divergentes].value_counts().items()})
        # PRESERVAR todas as redações POP_VALID cujas C1–C5 sejam numéricas e
        # estejam na escala. Não corrigir nem excluir uma nota divergente.
        aproveitar = completas
        if not bool(aproveitar.any()):
            continue
        tab = valores.loc[aproveitar].copy()
        tab["uf"] = uf.loc[valida].loc[aproveitar]
        tab["nota_total"] = nota.loc[valida].loc[aproveitar]
        soma_notas_uf_bloco = tab.groupby("uf", sort=False)["nota_total"].sum()
        somas = tab.groupby("uf", sort=False)[list(COMP)].sum()
        ns = tab.groupby("uf", sort=False).size()
        for codigo, reg in somas.iterrows():
            codigo = str(codigo)
            ns_uf[codigo] += int(ns[codigo])
            somas_totais_uf[codigo] += float(soma_notas_uf_bloco[codigo])
            for i, c in enumerate(COMP):
                somas_uf[codigo][i] += float(reg[c])
        for i, c in enumerate(COMP):
            soma_br[i] += float(tab[c].sum())
        soma_total_br += float(tab["nota_total"].sum())

    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: arquivo de microdados vazio")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: reconciliação de status=1 não fechou")
    erros = [chave for chave in qa if chave.startswith(("c1_", "c2_", "c3_", "c4_", "c5_")) and qa[chave]]
    for chave in ("status1_sem_nota", "status1_nota_invalida", "validas_sem_uf",
                  "validas_uf_desconhecida", "validas_competencias_incompletas"):
        if qa[chave]:
            erros.append(chave)
    if erros:
        detalhe = ", ".join(f"{x}={qa[x]}" for x in sorted(set(erros)))
        raise ValueError(f"{ano}: erro de integridade POP_VALID/competências: {detalhe}")
    if sum(totais_uf.values()) != qa["registros"]:
        raise ValueError(f"{ano}: POP_ALL das UFs não fecha")
    if sum(ns_uf.values()) != qa["validas"]:
        raise ValueError(f"{ano}: população estadual diverge da nacional")
    for i in range(5):
        if not math.isclose(sum(somas_uf[u][i] for u in UFS), soma_br[i], rel_tol=0, abs_tol=0.02):
            raise ValueError(f"{ano}: C{i+1} não fecha entre UFs e Brasil")
    estados = []
    for uf in UFS:
        n = ns_uf[uf]
        if n < LIMIAR_POP_VALID:
            raise ValueError(f"{ano}/{uf}: população válida com n={n} inferior a {LIMIAR_POP_VALID}")
        estados.append({"uf": uf, **preparar_grupo(
            n, somas_uf[uf], totais_uf[uf], somas_totais_uf[uf], divergencias_uf[uf])})
    if not math.isclose(sum(somas_totais_uf[u] for u in UFS), soma_total_br, rel_tol=0, abs_tol=0.02):
        raise ValueError(f"{ano}: soma da nota total não fecha entre UFs e Brasil")
    br = preparar_grupo(qa["validas"], soma_br, qa["registros"],
                        soma_total_br, qa["validas_soma_competencias_divergente"])
    return {
        "ano": ano, "arquivo_fonte": caminho.name, "brasil": br,
        "ufs": estados,
        "qualidade": {
            "status": "ok", "status1_sem_nota": qa["status1_sem_nota"],
            "status1_nota_invalida": qa["status1_nota_invalida"],
            "validas_sem_uf": qa["validas_sem_uf"],
            "validas_uf_desconhecida": qa["validas_uf_desconhecida"],
            "validas_competencias_incompletas": qa["validas_competencias_incompletas"],
            "validas_soma_competencias_divergente": qa["validas_soma_competencias_divergente"],
            "soma_ufs_igual_brasil": True,
            "competencias_no_intervalo_0_200": True,
            "soma_competencias_igual_nota_total": qa["validas_soma_competencias_divergente"] == 0,
            "situacao_soma_competencias": (
                "divergencias_na_fonte" if qa["validas_soma_competencias_divergente"] else "ok"),
            "delta_soma_competencias_menos_nota_redacao": br["delta_soma_competencias_menos_nota_redacao"],
            "metodo": METODO,
        },
    }


def _uf_map(grupo: dict) -> dict[str, dict]:
    return {u["uf"]: u for u in grupo["ufs"]}


def _comparar(d: dict, r1: dict, r2: dict, r7: dict, r8: dict, contexto: str,
              historico: bool = False) -> None:
    n = d["n_validas"]
    if any(n != x for x in (r1["redacoes_validas"], r2["n_validas"],
                            r7["redacoes_status_1"], r8["n_validas"])):
        raise ValueError(f"{contexto}: população difere de IND-001/002/007/008")
    status1 = [x for x in r7["categorias"] if str(x["codigo"]) == "1"]
    if len(status1) != 1 or status1[0]["quantidade"] != n:
        raise ValueError(f"{contexto}: status=1 em IND-007 incompatível")
    if not historico and any(d["total_registros"] != x for x in
                             (r1["total_registros"], r2["total_registros"],
                              r7["total_registros"], r8["total_registros"])):
        raise ValueError(f"{contexto}: POP_ALL diverge dos indicadores anteriores")
    validar_soma_competencias(d, r2["soma_notas"], contexto)
    soma_media = sum(x["media"] for x in d["competencias"])
    delta_media = d["delta_soma_competencias_menos_nota_redacao"] / n
    if abs((soma_media - r2["media"]) - delta_media) > 0.00035:
        raise ValueError(f"{contexto}: soma das médias difere de IND-002 após considerar divergências da fonte")


def validar_referencias(dados: list[dict], refs: dict[int, dict]) -> None:
    ref_ano = {i: {r["ano"]: r for r in doc["years"]} for i, doc in refs.items()}
    for item in dados:
        ano = item["ano"]
        grupo_refs = {i: ref_ano[i][ano] for i in refs}
        _comparar(item["brasil"], *[grupo_refs[i]["brasil"] for i in (1,2,7,8)], str(ano))
        for uf in UFS:
            _comparar(next(x for x in item["ufs"] if x["uf"] == uf),
                      *[_uf_map(grupo_refs[i])[uf] for i in (1,2,7,8)], f"{ano}/{uf}")
        item["qualidade"]["validado_contra_ind001_ind002_ind007_ind008"] = True


def consolidar_historico(dados: list[dict], refs: dict[int, dict]) -> dict:
    def acumular(partes: list[dict]) -> dict:
        n = sum(x["n_validas"] for x in partes)
        somas = [math.fsum(x["competencias"][i]["soma_notas"] for x in partes) for i in range(5)]
        soma_total = math.fsum(x["soma_nota_redacao"] for x in partes)
        n_div = sum(x["n_somas_divergentes"] for x in partes)
        return preparar_grupo(n, somas, soma_nota_redacao=soma_total,
                              n_somas_divergentes=n_div)
    br = acumular([d["brasil"] for d in dados])
    ufs = []
    for uf in UFS:
        grupos = [next(x for x in d["ufs"] if x["uf"] == uf) for d in dados]
        ufs.append({"uf": uf, **acumular(grupos)})
    if br["n_validas"] != sum(u["n_validas"] for u in ufs):
        raise ValueError("Histórico: quantidades das UFs não fecham")
    for i in range(5):
        if not math.isclose(br["competencias"][i]["soma_notas"],
                            sum(u["competencias"][i]["soma_notas"] for u in ufs),
                            rel_tol=0, abs_tol=0.02):
            raise ValueError(f"Histórico: C{i+1} não fecha nas 27 UFs")
    h_refs = {i: doc["historical"] for i, doc in refs.items()}
    _comparar(br, *[h_refs[i]["brasil"] for i in (1,2,7,8)], "histórico Brasil", True)
    for u in ufs:
        uf = u["uf"]
        _comparar(u, *[_uf_map(h_refs[i])[uf] for i in (1,2,7,8)],
                  f"histórico/{uf}", True)
    return {"periodo": "2019-2025", "brasil": br, "ufs": ufs, "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], h: dict) -> list[dict]:
    linhas = []
    recortes = [(str(d["ano"]), d["arquivo_fonte"], d) for d in dados]
    recortes.append(("2019-2025", "TODAS_AS_EDICOES", h))
    for periodo, origem, d in recortes:
        for nivel, uf, grupo in [("BRASIL", "BR", d["brasil"])] + [
            ("UF", u["uf"], u) for u in d["ufs"]
        ]:
            for comp in grupo["competencias"]:
                linhas.append({
                    "indicador_id": INDICADOR, "periodo": periodo, "abrangencia": nivel,
                    "uf": uf, "competencia": comp["competencia"], "variavel": comp["variavel"],
                    "n_validas": grupo["n_validas"], "soma_notas": comp["soma_notas"],
                    "media": comp["media"], "escala_maxima": 200,
                    "n_somas_divergentes": grupo["n_somas_divergentes"],
                    "delta_soma_competencias_menos_nota_redacao": grupo["delta_soma_competencias_menos_nota_redacao"],
                    "populacao": "POP_VALID", "metodo": METODO, "arquivo_fonte": origem,
                })
    esperado = 8 * 28 * 5
    if len(linhas) != esperado:
        raise AssertionError(f"CSV tem {len(linhas)} linhas, esperadas {esperado}")
    return linhas


def item_resumo(c: dict) -> dict:
    return {"competency": c["competencia"], "label": c["descricao"],
            "variable": c["variavel"], "mean_score": c["media"],
            "n": c["n"], "max_score": 200}


def construir_dashboard(d: dict, dados: list[dict], h: dict,
                          base: dict, gerado: str) -> dict:
    ano = d["ano"]
    p = deepcopy(base)
    br = d["brasil"]
    ov = p["pages"]["overview"]
    if ov["kpis"]["valid_essays"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N anterior incompatível")
    if ov["ind002"]["n"] != br["n_validas"] or ov["ind008"]["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N IND-002 ou IND-008 divergente")
    if ov["essay_status"]["n"] != br["total_registros"]:
        raise ValueError(f"Dashboard {ano}: POP_ALL incompatível")
    diferenca_media = br["delta_soma_competencias_menos_nota_redacao"] / br["n_validas"]
    if not math.isclose(sum(c["media"] for c in br["competencias"]) - diferenca_media,
                        ov["kpis"]["mean_score"], rel_tol=0, abs_tol=0.00035):
        raise ValueError(f"Dashboard {ano}: soma das médias C1–C5 não reconcilia com a nota total")
    if {x["uf"] for x in ov["ind008"].get("by_uf", [])} != set(UFS):
        raise ValueError(f"Dashboard {ano}: IND-008 sem as 27 UFs")
    painel_comp = p["pages"]["competencies"]
    painel_comp.pop("reason", None)
    painel_comp["status"] = "ok"
    painel_comp["summary"] = [item_resumo(c) for c in br["competencias"]]
    painel_comp["ind009"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID", "method": METODO,
        "unit": "pontos", "max_score_per_competency": 200, "n": br["n_validas"],
        "by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                   "summary": [item_resumo(c) for c in u["competencias"]]}
                  for u in d["ufs"]],
    }
    p["pages"]["temporal"]["ind009"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID",
        "national_by_year": [{"year": x["ano"], "n": x["brasil"]["n_validas"],
                              "summary": [item_resumo(c) for c in x["brasil"]["competencias"]]}
                             for x in dados],
        "period_total": {"n": h["brasil"]["n_validas"],
                         "summary": [item_resumo(c) for c in h["brasil"]["competencias"]]},
        "period_by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                          "summary": [item_resumo(c) for c in u["competencias"]]}
                         for u in h["ufs"]], "note": NOTA_HISTORICA,
    }
    p["pages"]["methodology"]["ind009"] = {
        "definition": DEFINICAO,
        "calculation": "SUM(NU_NOTA_COMPj) / COUNT(POP_VALID), j=1..5",
        "population": "POP_VALID", "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "precision": "4 casas decimais nas médias; 0–200 por competência",
        "integrity": "C1..C5 precisam estar em 0–200. Divergências existentes entre a soma das competências e a nota total são mantidas, contadas e reconciliadas com IND-002 sem alterar a fonte.",
        "historical_note": NOTA_HISTORICA,
    }
    p["quality"]["ind009_validation"] = deepcopy(d["qualidade"])
    p["meta"]["analysis_version"] = VERSAO
    p["meta"]["generated_at"] = gerado
    p["meta"]["data_status"] = "draft"
    aviso = "IND-009: médias das competências validadas computacionalmente; revisão acadêmica pendente."
    if aviso not in p["meta"].setdefault("warnings", []):
        p["meta"]["warnings"].append(aviso)
    if d["qualidade"]["validas_soma_competencias_divergente"]:
        alerta = (f"IND-009/{ano}: "
                  f"{d['qualidade']['validas_soma_competencias_divergente']} redação(ões) válidas "
                  "têm C1–C5 cuja soma difere da nota total; registros mantidos sem ajuste. "
                  "Revisão da fonte e da metodologia necessária antes de publicar.")
        if alerta not in p["meta"]["warnings"]:
            p["meta"]["warnings"].append(alerta)
    return p


def validar_dashboard(p: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(p):
        raise ValueError("Dashboard sem estrutura básica obrigatória")
    if "NU_INSCRICAO" in json.dumps(p, ensure_ascii=False):
        raise ValueError("Dashboard contém identificadores de participantes")
    schema_paths = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    schema_path = next((x for x in schema_paths if x.is_file()), None)
    if schema_path is None:
        return "validação de estrutura (schema não encontrado)"
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError("JSON Schema encontrado, mas biblioteca jsonschema ausente") from exc
    with schema_path.open(encoding="utf-8") as f:
        jsonschema.validate(p, json.load(f))
    return "JSON Schema v1.0.0"


def salvar_json(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".json.tmp")
    with temporario.open("w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    temporario.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".csv.tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as f:
        gravador = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        gravador.writeheader()
        gravador.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, bloco: int = TAMANHO_BLOCO) -> None:
    refs, originais = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f"IND-009 | {ano}: processando {fonte(ano, raiz).name} ...", flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        medias = ", ".join(f"C{i+1}={c['media']:.4f}" for i, c in enumerate(d["brasil"]["competencias"]))
        print(f"  válidas={d['brasil']['n_validas']:,} | {medias}", flush=True)
        if d["qualidade"]["validas_soma_competencias_divergente"]:
            print(f"  AVISO FONTE: {d['qualidade']['validas_soma_competencias_divergente']} "
                  "redação(ões) com soma C1–C5 diferente da nota total; "
                  "incluídas sem alterar valores, com qualidade documentada.", flush=True)
    validar_referencias(dados, refs)
    h = consolidar_historico(dados, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboards = {d["ano"]: construir_dashboard(d, dados, h, originais[d["ano"]], gerado) for d in dados}
    resultados_validacao = {validar_dashboard(p, raiz) for p in dashboards.values()}
    saida = {
        "meta": {"indicator_id": INDICADOR, "module_schema_version": "ind009-module-1.0.0",
                 "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
                 "generated_at": gerado, "data_status": "draft",
                 "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
                 "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
                 "method": METODO, "comparison_ind001_ind002_ind007_ind008": "aprovada",
                 "historical_note": NOTA_HISTORICA,
                 "source_discrepancies": {
                     str(d["ano"]): {
                         "count": d["qualidade"]["validas_soma_competencias_divergente"],
                         "delta_total": d["qualidade"]["delta_soma_competencias_menos_nota_redacao"]}
                     for d in dados}},
        "indicator": {"id": INDICADOR, "name": "Média C1–C5", "unit": "pontos",
                      "dashboard_json_path": "pages.competencies.summary"},
        "years": dados, "historical": h,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(saida, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, h)
    pasta = raiz / "outputs"
    salvar_csv(pasta / "indicadores" / "IND_009_media_competencias.csv", linhas)
    salvar_json(pasta / "json" / "IND_009_media_competencias.json", saida)
    for ano in ANOS:
        salvar_json(pasta / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    print("\nIND-009 concluído. Saídas:")
    print(f"  IND_009_media_competencias.csv ({len(linhas)} linhas)")
    print("  IND_009_media_competencias.json")
    print("  dashboard_enem_AAAA.json (2019–2025; IND-001–008 preservados)")
    print("  Verificação: " + ", ".join(sorted(resultados_validacao)))
    print(f"  Histórico: {h['brasil']['n_validas']:,} redações válidas")
    print("  STATUS: draft — aguarda auditoria dos resultados reais e revisão acadêmica")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-009 — Médias das competências C1–C5 ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--bloco", type=int, default=TAMANHO_BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser inteiro positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
