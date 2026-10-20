# -*- coding: utf-8 -*-
r"""IND-010 — Mediana das competências C1–C5 da redação do ENEM (2019–2025).

Catálogo: Competências / Mediana C1–C5 / POP_VALID / median por competência.
Destino: pages.competencies.summary (complementa médias IND-009, sem substituí-las).

Execute APÓS concluir o IND-009 (ambos atualizam os mesmos arquivos JSON).
PowerShell, na raiz do repositório:
    .\.venv\Scripts\python.exe src\indicadores\IND_010_mediana_competencias.py

Saídas:
    outputs/indicadores/IND_010_mediana_competencias.csv (1.120 linhas)
    outputs/json/IND_010_mediana_competencias.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

Medianas exatas a partir das frequências completas de cada competência; nenhum
microdado é amostrado. O histórico combina frequências de 2019–2025, nunca
as medianas dos anos. POP_VALID: TP_STATUS_REDACAO=1 + nota total válida em
[0,1000]. As cinco competências precisam estar em [0,200]; divergências
entre a soma C1–C5 e a nota total são preservadas e documentadas, sem
imputação ou exclusão. Para cada recorte, quantidades e médias das competências
são conferidas com IND-001, IND-002 e IND-009. Resultados em 'draft', sujeitos à validação acadêmica.
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
COMP = tuple(f"NU_NOTA_COMP{i}" for i in range(1, 6))
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO", *COMP)
INDICADOR = "IND-010"
VERSAO = "2.9.1-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010"
METODO = "mediana_exata_frequencias_competencias_pop_valid"
TAMANHO_BLOCO = 100_000
LIMIAR_POP_VALID = 30
ROTULOS = (
    "Domínio da modalidade escrita formal da língua portuguesa",
    "Compreensão da proposta e desenvolvimento do tema",
    "Seleção, organização e interpretação de informações e argumentos",
    "Conhecimento dos mecanismos linguísticos de argumentação",
    "Elaboração de proposta de intervenção",
)
DEFINICAO = (
    "Mediana de NU_NOTA_COMP1 a NU_NOTA_COMP5, individualmente, em escala "
    "de 0 a 200 pontos, para POP_VALID (TP_STATUS_REDACAO=1 e nota total "
    "numérica entre 0 e 1000), com validação da soma das competências."
)
NOTA_HISTORICA = (
    "O consolidado 2019–2025 foi calculado pela combinação de todas as "
    "frequências das notas C1–C5 dos sete anos; não é a média nem a mediana "
    "das medianas anuais. Conta participações, não indivíduos únicos; "
    "SG_UF_PROVA é o local da prova, não a residência."
)


def fonte(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def mapa_ufs(grupo: dict) -> dict[str, dict]:
    itens = grupo.get("ufs", [])
    if len(itens) != len(UFS) or {x.get("uf") for x in itens} != set(UFS):
        raise ValueError("Referência sem as 27 UFs exatamente uma vez")
    return {x["uf"]: x for x in itens}


def carregar_referencias(raiz: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    modulos = {
        1: "redacoes_validas", 2: "nota_media", 9: "media_competencias",
    }
    referencias = {}
    for numero, nome in modulos.items():
        arquivo = pasta / f"IND_{numero:03d}_{nome}.json"
        doc = ler_json(arquivo)
        if doc.get("indicator", {}).get("id") != f"IND-{numero:03d}":
            raise ValueError(f"{arquivo.name}: indicator.id inconsistente")
        if sorted(x.get("ano") for x in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"{arquivo.name}: sete edições ausentes ou duplicadas")
        for recorte in [*doc["years"], doc.get("historical", {})]:
            mapa_ufs(recorte)
        referencias[numero] = doc

    dashboards = {}
    for ano in ANOS:
        p = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if p.get("meta", {}).get("year") != ano:
            raise ValueError(f"Dashboard {ano}: campo meta.year divergente")
        ov = p.get("pages", {}).get("overview", {})
        for i in range(1, 6):
            if f"ind{i:03d}" not in ov:
                raise ValueError(f"Dashboard {ano}: faltando IND-{i:03d}")
        for chave in ("score_distribution", "essay_status", "ind008"):
            if chave not in ov:
                raise ValueError(f"Dashboard {ano}: faltando {chave}")
        comp = p.get("pages", {}).get("competencies", {})
        if comp.get("status") != "ok" or "ind009" not in comp:
            raise ValueError(f"Dashboard {ano}: IND-009 não concluído — aguarde antes de executar IND-010")
        if p.get("quality", {}).get("ind009_validation", {}).get("status") != "ok":
            raise ValueError(f"Dashboard {ano}: qualidade do IND-009 não confirmada")
        if len(comp.get("summary", [])) != 5:
            raise ValueError(f"Dashboard {ano}: médias C1–C5 incompletas")
        dashboards[ano] = p
    return referencias, dashboards


def mediana_contagens(frequencias: Counter, n: int) -> float:
    """Calcula a mediana exata, com média dos dois centrais quando n é par."""
    if n <= 0 or sum(frequencias.values()) != n:
        raise ValueError(f"Frequências não fecham: n={n}; total={sum(frequencias.values())}")
    alvo1 = (n + 1) // 2  # posição 1-based do elemento central inferior
    alvo2 = (n + 2) // 2  # posição 1-based do elemento central superior
    acumulado = 0
    primeiro = segundo = None
    for nota, quantidade in sorted(frequencias.items()):
        if not math.isfinite(nota) or nota < 0 or nota > 200:
            raise ValueError(f"Valor de competência fora da escala: {nota}")
        if quantidade <= 0:
            raise ValueError(f"Frequência inválida: {quantidade}")
        acumulado += quantidade
        if primeiro is None and acumulado >= alvo1:
            primeiro = float(nota)
        if acumulado >= alvo2:
            segundo = float(nota)
            break
    if primeiro is None or segundo is None:
        raise ValueError("Não foi possível localizar as posições da mediana")
    return round((primeiro + segundo) / 2, 4)


def resumo_competencias(n: int, freq: list[Counter]) -> list[dict]:
    if n <= 0 or len(freq) != 5:
        raise ValueError(f"População ou competências inválidas: {n}")
    return [
        {"competencia": f"C{i+1}", "variavel": COMP[i], "descricao": ROTULOS[i],
         "n": n, "mediana": mediana_contagens(freq[i], n), "escala_maxima": 200}
        for i in range(5)
    ]


def preparar_grupo(n: int, freq: list[Counter], total: int | None = None) -> dict:
    saida = {"n_validas": int(n), "competencias": resumo_competencias(n, freq)}
    if total is not None:
        saida["total_registros"] = int(total)
    return saida


def processar_ano(ano: int, raiz: Path, bloco: int = TAMANHO_BLOCO) -> dict:
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Microdados ausentes: {caminho}")
    qa = Counter()
    totais_uf = Counter()
    n_uf = Counter({uf: 0 for uf in UFS})
    freq_uf = {uf: [Counter() for _ in range(5)] for uf in UFS}

    for parte in pd.read_csv(
        caminho, sep=";", usecols=list(COLUNAS), dtype=str,
        keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    ):
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        nota_texto = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(nota_texto.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        validas = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(validas.sum())
        qa["status1_sem_nota"] += int((st1 & nota_texto.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & nota_texto.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((validas & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((validas & ~uf_ok & uf.ne("")).sum())
        totais_uf.update({str(k): int(v) for k, v in uf.value_counts().items()})
        if not bool(validas.any()):
            continue
        cru = parte.loc[validas, list(COMP)].apply(lambda c: c.str.strip())
        valores = cru.apply(lambda c: pd.to_numeric(
            c.str.replace(",", ".", regex=False), errors="coerce"))
        valid_comp = valores.notna() & valores.ge(0) & valores.le(200)
        for i, coluna in enumerate(COMP, 1):
            qa[f"c{i}_ausente"] += int(cru[coluna].eq("").sum())
            qa[f"c{i}_invalida"] += int((cru[coluna].ne("") & ~valid_comp[coluna]).sum())
        completas = valid_comp.all(axis=1)
        qa["validas_competencias_incompletas"] += int((~completas).sum())
        soma_linha = valores.sum(axis=1)
        comp_total_ok = (soma_linha - nota.loc[validas]).abs().le(0.000001)
        qa["validas_soma_competencias_divergente"] += int((completas & ~comp_total_ok).sum())
        # Medianas usam todas as redações POP_VALID com C1–C5 presentes e
        # dentro da escala, inclusive diferenças observadas na fonte.
        aproveitar = completas
        if not bool(aproveitar.any()):
            continue
        tab = valores.loc[aproveitar].copy()
        tab["uf"] = uf.loc[validas].loc[aproveitar]
        counts = tab["uf"].value_counts()
        for codigo, qtd in counts.items():
            n_uf[str(codigo)] += int(qtd)
        # A contagem de valores únicos por UF mantém a exatidão do cálculo,
        # sem manter em memória as notas individuais de todas as edições.
        for i, coluna in enumerate(COMP):
            frequencias = tab.groupby(["uf", coluna], sort=False).size()
            for (codigo, pontuacao), qtd in frequencias.items():
                freq_uf[str(codigo)][i][float(pontuacao)] += int(qtd)

    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: arquivo fonte vazio")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: reconciliação do status 1 não fechou")
    erros = [k for k in qa if k.startswith(tuple(f"c{i}_" for i in range(1, 6))) and qa[k]]
    for k in ("status1_sem_nota", "status1_nota_invalida", "validas_sem_uf",
              "validas_uf_desconhecida", "validas_competencias_incompletas"):
        if qa[k]:
            erros.append(k)
    if erros:
        raise ValueError(f"{ano}: falha de integridade em POP_VALID: " +
                         ", ".join(f"{k}={qa[k]}" for k in sorted(set(erros))))
    if sum(totais_uf.values()) != qa["registros"] or sum(totais_uf[u] for u in UFS) != qa["registros"]:
        raise ValueError(f"{ano}: POP_ALL não fecha entre Brasil e 27 UFs")
    if sum(n_uf[u] for u in UFS) != qa["validas"]:
        raise ValueError(f"{ano}: POP_VALID não fecha entre Brasil e 27 UFs")

    freq_br = [Counter() for _ in range(5)]
    estados = []
    for codigo in UFS:
        n = n_uf[codigo]
        if n < LIMIAR_POP_VALID:
            raise ValueError(f"{ano}/{codigo}: N válido={n} inferior a {LIMIAR_POP_VALID}")
        estados.append({"uf": codigo, **preparar_grupo(n, freq_uf[codigo], totais_uf[codigo])})
        for i in range(5):
            freq_br[i].update(freq_uf[codigo][i])
    br = preparar_grupo(qa["validas"], freq_br, qa["registros"])
    return {
        "ano": ano, "arquivo_fonte": caminho.name, "brasil": br, "ufs": estados,
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
            "frequencias_completas_sem_amostragem": True,
            "metodo": METODO,
        },
        "_freq_uf": freq_uf, "_freq_br": freq_br,
    }


def validar_grupo(d: dict, frequencias: list[Counter], r1: dict, r2: dict, r9: dict,
                  contexto: str, historico: bool = False) -> None:
    n = d["n_validas"]
    if n != r1["redacoes_validas"] or n != r2["n_validas"] or n != r9["n_validas"]:
        raise ValueError(f"{contexto}: N diverge de IND-001/002/009")
    if not historico and any(d["total_registros"] != r["total_registros"] for r in (r1, r2, r9)):
        raise ValueError(f"{contexto}: POP_ALL diverge dos indicadores anteriores")
    if len(d["competencias"]) != 5 or len(r9.get("competencias", [])) != 5:
        raise ValueError(f"{contexto}: quantidade de competências inesperada")
    soma_total = 0.0
    for i in range(5):
        c, anterior = d["competencias"][i], r9["competencias"][i]
        if c["competencia"] != f"C{i+1}" or anterior["competencia"] != f"C{i+1}":
            raise ValueError(f"{contexto}: ordem de competências incorreta")
        soma = math.fsum(nota * qtd for nota, qtd in frequencias[i].items())
        if not math.isclose(soma, float(anterior["soma_notas"]), rel_tol=0, abs_tol=0.02):
            raise ValueError(f"{contexto}/C{i+1}: soma diverge do IND-009")
        if abs(round(soma/n, 4) - anterior["media"]) > 0.000051:
            raise ValueError(f"{contexto}/C{i+1}: média diverge do IND-009")
        if c["mediana"] != mediana_contagens(frequencias[i], n):
            raise ValueError(f"{contexto}/C{i+1}: mediana diverge das frequências")
        soma_total += soma
    delta_esperado = float(r9["delta_soma_competencias_menos_nota_redacao"])
    if not math.isclose(soma_total - float(r2["soma_notas"]),
                        delta_esperado, rel_tol=0, abs_tol=0.02):
        raise ValueError(f"{contexto}: soma C1–C5 não reconcilia com divergências auditadas pelo IND-009")


def validar_referencias(dados: list[dict], refs: dict[int, dict]) -> None:
    indexes = {i: {a["ano"]: a for a in doc["years"]} for i, doc in refs.items()}
    for d in dados:
        ano = d["ano"]
        refs_ano = {i: indexes[i][ano] for i in indexes}
        validar_grupo(d["brasil"], d["_freq_br"],
                      *[refs_ano[i]["brasil"] for i in (1, 2, 9)], str(ano))
        by_uf = {i: mapa_ufs(refs_ano[i]) for i in (1, 2, 9)}
        for item in d["ufs"]:
            uf = item["uf"]
            validar_grupo(item, d["_freq_uf"][uf],
                          *[by_uf[i][uf] for i in (1, 2, 9)], f"{ano}/{uf}")
        d["qualidade"]["validado_contra_ind001_ind002_ind009"] = True


def consolidar_historico(dados: list[dict], refs: dict[int, dict]) -> dict:
    freq_uf = {uf: [Counter() for _ in range(5)] for uf in UFS}
    for d in dados:
        for uf in UFS:
            for i in range(5):
                freq_uf[uf][i].update(d["_freq_uf"][uf][i])
    n_por_uf = {uf: sum(x["n_validas"] for x in [next(v for v in d["ufs"] if v["uf"] == uf)
                                               for d in dados]) for uf in UFS}
    estados = [{"uf": uf, **preparar_grupo(n_por_uf[uf], freq_uf[uf])} for uf in UFS]
    n_br = sum(d["brasil"]["n_validas"] for d in dados)
    freq_br = [Counter() for _ in range(5)]
    for uf in UFS:
        for i in range(5):
            freq_br[i].update(freq_uf[uf][i])
    br = preparar_grupo(n_br, freq_br)
    if n_br != sum(n_por_uf.values()):
        raise ValueError("Histórico: N nacional diverge da soma de UFs")
    hs = {i: refs[i]["historical"] for i in (1, 2, 9)}
    validar_grupo(br, freq_br, *[hs[i]["brasil"] for i in (1, 2, 9)],
                  "histórico/BR", True)
    by_uf = {i: mapa_ufs(hs[i]) for i in (1, 2, 9)}
    for u in estados:
        uf = u["uf"]
        validar_grupo(u, freq_uf[uf], *[by_uf[i][uf] for i in (1, 2, 9)],
                      f"histórico/{uf}", True)
    return {"periodo": "2019-2025", "brasil": br, "ufs": estados, "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    linhas = []
    recortes = [(str(d["ano"]), d["arquivo_fonte"], d) for d in dados]
    recortes.append(("2019-2025", "TODAS_AS_EDICOES", historico))
    for periodo, origem, recorte in recortes:
        for nivel, uf, grupo in [("BRASIL", "BR", recorte["brasil"])] + [
            ("UF", x["uf"], x) for x in recorte["ufs"]
        ]:
            for c in grupo["competencias"]:
                linhas.append({
                    "indicador_id": INDICADOR, "periodo": periodo, "abrangencia": nivel,
                    "uf": uf, "competencia": c["competencia"], "variavel": c["variavel"],
                    "n_validas": grupo["n_validas"], "mediana": c["mediana"],
                    "escala_maxima": 200, "populacao": "POP_VALID",
                    "metodo": METODO, "arquivo_fonte": origem,
                })
    if len(linhas) != 8 * 28 * 5:
        raise AssertionError(f"CSV gerou {len(linhas)} linhas; esperado 1120")
    if len({(x["periodo"], x["uf"], x["competencia"]) for x in linhas}) != len(linhas):
        raise AssertionError("CSV possui chaves duplicadas")
    return linhas


def item_resumo(c: dict) -> dict:
    return {"competency": c["competencia"], "label": c["descricao"],
            "variable": c["variavel"], "median_score": c["mediana"],
            "n": c["n"], "max_score": 200}


def adicionar_mediana_ao_resumo(resumo_existente: list[dict], novas: list[dict], contexto: str) -> list[dict]:
    if len(resumo_existente) != 5 or len(novas) != 5:
        raise ValueError(f"{contexto}: resumo deve conter C1–C5")
    resultado = deepcopy(resumo_existente)
    for i, (anterior, atual) in enumerate(zip(resultado, novas), 1):
        if anterior.get("competency") != f"C{i}" or atual["competency"] != f"C{i}":
            raise ValueError(f"{contexto}: competência fora de ordem")
        if anterior.get("n") != atual["n"]:
            raise ValueError(f"{contexto}: N diverge das médias anteriores")
        if "mean_score" not in anterior:
            raise ValueError(f"{contexto}: média do IND-009 não encontrada")
        anterior["median_score"] = atual["median_score"]
    return resultado


def construir_dashboard(d: dict, dados: list[dict], h: dict, base: dict, gerado: str) -> dict:
    ano = d["ano"]
    p = deepcopy(base)
    ov = p["pages"]["overview"]
    br = d["brasil"]
    if ov["kpis"]["valid_essays"] != br["n_validas"] or ov["ind002"]["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N anterior diverge do IND-010")
    comp = p["pages"]["competencies"]
    previous = comp["ind009"]
    if previous["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N de IND-009 divergente")
    prev_uf = mapa_ufs({"ufs": previous["by_uf"]})
    for u in d["ufs"]:
        if u["n_validas"] != prev_uf[u["uf"]]["n"]:
            raise ValueError(f"Dashboard {ano}/{u['uf']}: N do IND-009 divergente")
    novo = [item_resumo(c) for c in br["competencias"]]
    comp["summary"] = adicionar_mediana_ao_resumo(comp["summary"], novo, f"{ano}/BR")
    comp["ind010"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID", "method": METODO,
        "unit": "pontos", "max_score_per_competency": 200, "n": br["n_validas"],
        "national_summary": novo,
        "by_uf": [
            {"uf": u["uf"], "n": u["n_validas"],
             "summary": [item_resumo(c) for c in u["competencias"]]}
            for u in d["ufs"]
        ],
    }
    p["pages"]["temporal"]["ind010"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID",
        "national_by_year": [
            {"year": x["ano"], "n": x["brasil"]["n_validas"],
             "summary": [item_resumo(c) for c in x["brasil"]["competencias"]]}
            for x in dados
        ],
        "period_total": {"n": h["brasil"]["n_validas"],
                         "summary": [item_resumo(c) for c in h["brasil"]["competencias"]]},
        "period_by_uf": [
            {"uf": u["uf"], "n": u["n_validas"],
             "summary": [item_resumo(c) for c in u["competencias"]]}
            for u in h["ufs"]
        ], "note": NOTA_HISTORICA,
    }
    p["pages"]["methodology"]["ind010"] = {
        "definition": DEFINICAO,
        "calculation": "MEDIAN(NU_NOTA_COMPj), j=1..5, frequências completas; par: média dos centrais",
        "population": "POP_VALID", "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "precision": "4 casas decimais nas medianas; escala 0–200",
        "integrity": "Competências em 0–200, sem amostragem; divergências da soma frente à nota total registradas, mantidas e conciliadas com as médias IND-009",
        "historical_note": NOTA_HISTORICA,
    }
    p["quality"]["ind010_validation"] = deepcopy(d["qualidade"])
    p["meta"]["analysis_version"] = VERSAO
    p["meta"]["generated_at"] = gerado
    p["meta"]["data_status"] = "draft"
    aviso = "IND-010: medianas C1–C5 validadas computacionalmente; revisão acadêmica pendente."
    if aviso not in p["meta"].setdefault("warnings", []):
        p["meta"]["warnings"].append(aviso)
    if d["qualidade"]["validas_soma_competencias_divergente"]:
        alerta = (f"IND-010/{ano}: "
                  f"{d['qualidade']['validas_soma_competencias_divergente']} redação(ões) "
                  "têm C1–C5 cuja soma difere da nota total; valores originais mantidos. "
                  "Revisão necessária antes de publicar.")
        if alerta not in p["meta"]["warnings"]:
            p["meta"]["warnings"].append(alerta)
    return p


def validar_dashboard(p: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(p):
        raise ValueError("Dashboard sem estrutura obrigatória")
    if "NU_INSCRICAO" in json.dumps(p, ensure_ascii=False):
        raise ValueError("Identificador pessoal incluído indevidamente no dashboard")
    paths = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    path = next((x for x in paths if x.is_file()), None)
    if path is None:
        return "estrutura validada (JSON Schema não encontrado)"
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError("Biblioteca jsonschema é necessária para validar o dashboard") from exc
    with path.open(encoding="utf-8") as f:
        jsonschema.validate(p, json.load(f))
    return "JSON Schema v1.0.0"


def salvar_csv(path: Path, linhas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    temp.replace(path)


def salvar_json(path: Path, conteudo: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    temp.replace(path)


def executar(raiz: Path, bloco: int = TAMANHO_BLOCO) -> None:
    refs, originais = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f"IND-010 | {ano}: processando {fonte(ano, raiz).name} ...", flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        resultado = ", ".join(f"C{i+1}={c['mediana']:.4f}" for i,c in enumerate(d["brasil"]["competencias"]))
        print(f"  válidas={d['brasil']['n_validas']:,} | {resultado}", flush=True)
        if d["qualidade"]["validas_soma_competencias_divergente"]:
            print(f"  AVISO FONTE: {d['qualidade']['validas_soma_competencias_divergente']} "
                  "redação(ões) com divergência C1–C5; mantidas sem imputação.", flush=True)
    validar_referencias(dados, refs)
    historico = consolidar_historico(dados, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboards = {d["ano"]: construir_dashboard(d, dados, historico, originais[d["ano"]], gerado)
                  for d in dados}
    validacoes = {validar_dashboard(p, raiz) for p in dashboards.values()}
    for d in dados:
        d.pop("_freq_uf")
        d.pop("_freq_br")
    saida = {
        "meta": {
            "indicator_id": INDICADOR, "module_schema_version": "ind010-module-1.0.0",
            "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado, "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
            "method": METODO, "comparison_ind001_ind002_ind009": "aprovada",
            "historical_note": NOTA_HISTORICA,
        },
        "indicator": {"id": INDICADOR, "name": "Mediana C1–C5", "unit": "pontos",
                      "dashboard_json_path": "pages.competencies.summary"},
        "years": dados, "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(saida, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)
    pasta = raiz / "outputs"
    salvar_csv(pasta / "indicadores" / "IND_010_mediana_competencias.csv", linhas)
    salvar_json(pasta / "json" / "IND_010_mediana_competencias.json", saida)
    for ano in ANOS:
        salvar_json(pasta / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])
    print("\nIND-010 concluído. Saídas:")
    print(f"  IND_010_mediana_competencias.csv ({len(linhas)} linhas)")
    print("  IND_010_mediana_competencias.json")
    print("  dashboard_enem_AAAA.json (2019–2025; IND-001–009 preservados)")
    print("  Verificação: " + ", ".join(sorted(validacoes)))
    print(f"  Histórico: {historico['brasil']['n_validas']:,} redações válidas")
    print("  STATUS: draft — aguarda execução real, auditoria e revisão acadêmica")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-010 — Mediana das competências C1–C5 ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--bloco", type=int, default=TAMANHO_BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
