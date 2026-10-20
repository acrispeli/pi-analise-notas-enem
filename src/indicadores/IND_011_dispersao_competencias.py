#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-011 | Dispersão das competências C1–C5 (ENEM 2019–2025).

Catálogo: páginas.competencies.dispersion (no JSON: pages.competencies.dispersion).
- POP_VALID: TP_STATUS_REDACAO=1 e nota total numérica no intervalo [0, 1000].
- Desvio-padrão POPULACIONAL (ddof=0), P25 e P75 por quantis empíricos
  tipo 7 (interpolação linear, padrão NumPy); IQR = P75 - P25.
- 7 anos, Brasil, 27 UFs de aplicação, histórico por combinação EXATA
  de todas as frequências (sem amostragem ou média de dispersões).
- Não altera os microdados, não imputa competências, não altera Streamlit.
- A inconsistência de origem em SC/2023 (1 registro, diferença -30)
  permanece na POP_VALID e é reconciliada com o IND-009.
- Depende do IND-009 *corrigido* e do IND-010 *corrigido*, concluídos.

Executar na raiz do repositório:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_011_dispersao_competencias.py
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
INDICADOR = "IND-011"
VERSAO = "2.10.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010-ind011"
METODO = "desvio_padrao_populacional_ddof0_e_iqr_hf7_competencias"
TAMANHO_BLOCO = 100_000
LIMIAR_N = 30
ROTULOS = (
    "Domínio da modalidade escrita formal da língua portuguesa",
    "Compreensão da proposta e desenvolvimento do tema",
    "Seleção, organização e interpretação de informações e argumentos",
    "Conhecimento dos mecanismos linguísticos de argumentação",
    "Elaboração de proposta de intervenção",
)
DEFINICAO = (
    "Dispersão de cada competência C1–C5 (NU_NOTA_COMP1..5, 0–200 pontos) "
    "entre redações válidas: desvio-padrão populacional (ddof=0) e amplitude "
    "interquartil IQR=P75-P25, quantis H&F tipo 7 com interpolação linear."
)
NOTA_HISTORICA = (
    "O consolidado 2019–2025 reúne as frequências observadas de cada competência "
    "em todas as edições, sem amostragem. Desvio-padrão e quantis são recalculados "
    "a partir da distribuição conjunta, não são médias das estatísticas anuais. "
    "Contabiliza participações, não pessoas únicas; SG_UF_PROVA é o local da prova."
)
INTEGRIDADE = (
    "Cinco competências numéricas em [0,200] são obrigatórias para POP_VALID. "
    "Diferenças de origem entre soma C1–C5 e nota total não são corrigidas nem "
    "excluídas; são contadas e conciliadas com IND-009."
)


def fonte(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {caminho}")
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def mapa_ufs(grupo: dict) -> dict[str, dict]:
    itens = grupo.get("ufs", [])
    if len(itens) != len(UFS) or {x.get("uf") for x in itens} != set(UFS):
        raise ValueError("Referência incompleta: exigidas 27 UFs sem duplicação")
    return {x["uf"]: x for x in itens}


def carregar_referencias(raiz: Path) -> tuple[dict, dict]:
    pasta = raiz / "outputs" / "json"
    modulos = {1: "redacoes_validas", 2: "nota_media",
               9: "media_competencias", 10: "mediana_competencias"}
    refs = {}
    for numero, nome in modulos.items():
        arquivo = pasta / f"IND_{numero:03d}_{nome}.json"
        doc = ler_json(arquivo)
        if doc.get("indicator", {}).get("id") != f"IND-{numero:03d}":
            raise ValueError(f"{arquivo.name}: indicador incorreto")
        if sorted(x.get("ano") for x in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"{arquivo.name}: faltam anos ou existem duplicações")
        for grupo in [*doc["years"], doc["historical"]]:
            mapa_ufs(grupo)
        refs[numero] = doc
    # Exigir explicitamente a versão com tratamento auditável da fonte.
    if any("n_somas_divergentes" not in d["brasil"] for d in refs[9]["years"]):
        raise ValueError("IND-009 anterior ao tratamento das divergências da fonte: use a versão corrigida")
    if any("validas_soma_competencias_divergente" not in d["qualidade"] for d in refs[10]["years"]):
        raise ValueError("IND-010 anterior ao tratamento das divergências da fonte: use a versão corrigida")

    dashboards = {}
    for ano in ANOS:
        dash = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if dash.get("meta", {}).get("year") != ano:
            raise ValueError(f"Dashboard {ano}: meta.year incompatível")
        comp = dash.get("pages", {}).get("competencies", {})
        if comp.get("status") != "ok" or any(x not in comp for x in ("ind009", "ind010", "summary")):
            raise ValueError(f"Dashboard {ano}: aguarde a conclusão dos IND-009 e IND-010")
        if len(comp["summary"]) != 5:
            raise ValueError(f"Dashboard {ano}: resumo C1–C5 ausente")
        for num in (9, 10):
            if dash.get("quality", {}).get(f"ind{num:03d}_validation", {}).get("status") != "ok":
                raise ValueError(f"Dashboard {ano}: qualidade IND-{num:03d} ainda não confirmada")
        if not all(f"ind{i:03d}" in dash.get("pages", {}).get("overview", {}) for i in range(1, 6)):
            raise ValueError(f"Dashboard {ano}: indicadores 001–005 ausentes")
        if not all(k in dash["pages"]["overview"] for k in ("score_distribution", "essay_status", "ind008")):
            raise ValueError(f"Dashboard {ano}: indicadores 006–008 ausentes")
        dashboards[ano] = dash
    return refs, dashboards


def posicoes_quantiles(freq: Counter, n: int, probs=(0.25, 0.5, 0.75)) -> dict:
    """Quantis empíricos tipo 7: h=(n-1)*p, com interpolação linear."""
    if n <= 0 or sum(freq.values()) != n:
        raise ValueError(f"Frequências não fecham para n={n}")
    alvos = {}
    for p in probs:
        h = (n - 1) * p
        inferior = int(math.floor(h))
        superior = min(n - 1, inferior + 1)
        alvos[p] = (inferior, superior, h - inferior)
    indices = sorted({v for baixo, alto, _ in alvos.values() for v in (baixo, alto)})
    valores = {}
    acumulado = 0
    ix = 0
    for valor, quantidade in sorted(freq.items()):
        if not math.isfinite(valor) or not 0 <= valor <= 200 or quantidade <= 0:
            raise ValueError(f"Frequência/nota de competência inválida: {valor}: {quantidade}")
        while ix < len(indices) and indices[ix] < acumulado + quantidade:
            valores[indices[ix]] = float(valor)
            ix += 1
        acumulado += quantidade
        if ix == len(indices):
            break
    if len(valores) != len(indices):
        raise ValueError("Posições dos quantis não encontradas")
    return {p: valores[baixo] + (valores[alto] - valores[baixo]) * frac
            for p, (baixo, alto, frac) in alvos.items()}


def dispersao_frequencias(freq: Counter, n: int) -> dict:
    q = posicoes_quantiles(freq, n)
    mu = math.fsum(float(nota) * int(k) for nota, k in freq.items()) / n
    # Duas passagens para estabilidade numérica; desvio-padrão POPULACIONAL.
    var = math.fsum(((float(nota) - mu) ** 2) * int(k) for nota, k in freq.items()) / n
    if var < 0 or not math.isfinite(var):
        raise ValueError("Variância não finita")
    return {"media_controle": round(mu, 4), "mediana_controle": round(q[0.5], 4),
            "p25": round(q[0.25], 4), "p75": round(q[0.75], 4),
            "iqr": round(q[0.75] - q[0.25], 4),
            "desvio_padrao": round(math.sqrt(var), 4), "variancia": round(var, 4),
            "ddof": 0}


def grupo_resultado(n: int, freq: list[Counter], total: int | None = None,
                    qtd_div: int = 0, delta: float = 0.0) -> dict:
    if n < LIMIAR_N or len(freq) != 5:
        raise ValueError(f"N de POP_VALID ou número de competências incorreto: n={n}")
    cs = []
    for i, counter in enumerate(freq):
        cs.append({"competencia": f"C{i+1}", "variavel": COMP[i],
                   "descricao": ROTULOS[i], "n": n, "escala_maxima": 200,
                   **dispersao_frequencias(counter, n)})
    saida = {"n_validas": n, "competencias": cs,
             "n_somas_divergentes": int(qtd_div),
             "delta_soma_competencias_menos_nota_redacao": round(float(delta), 6)}
    if total is not None:
        saida["total_registros"] = int(total)
    return saida


def processar_ano(ano: int, raiz: Path, bloco: int = TAMANHO_BLOCO) -> dict:
    arquivo = fonte(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Fonte não encontrada: {arquivo}")
    qa = Counter()
    total_uf = Counter()
    n_uf = Counter({uf: 0 for uf in UFS})
    freq_uf = {uf: [Counter() for _ in range(5)] for uf in UFS}
    div_uf = Counter({uf: 0 for uf in UFS})
    delta_uf = Counter({uf: 0.0 for uf in UFS})

    for parte in pd.read_csv(arquivo, sep=";", usecols=list(COLUNAS), dtype=str,
                             keep_default_na=False, na_filter=False,
                             encoding="utf-8-sig", encoding_errors="replace",
                             chunksize=bloco, on_bad_lines="error"):
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        texto = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(texto.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        validas = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(validas.sum())
        qa["status1_sem_nota"] += int((st1 & texto.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & texto.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((validas & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((validas & ~uf_ok & uf.ne("")).sum())
        total_uf.update({str(k): int(v) for k, v in uf.value_counts().items()})
        if not bool(validas.any()):
            continue
        cru = parte.loc[validas, list(COMP)].apply(lambda c: c.str.strip())
        cval = cru.apply(lambda c: pd.to_numeric(c.str.replace(",", ".", regex=False), errors="coerce"))
        ok = cval.notna() & cval.ge(0) & cval.le(200)
        for i, coluna in enumerate(COMP, 1):
            qa[f"c{i}_ausente"] += int(cru[coluna].eq("").sum())
            qa[f"c{i}_invalida"] += int((cru[coluna].ne("") & ~ok[coluna]).sum())
        completa = ok.all(axis=1)
        qa["validas_competencias_incompletas"] += int((~completa).sum())
        if not bool(completa.any()):
            continue
        valores = cval.loc[completa]
        ufs_ok = uf.loc[validas].loc[completa]
        dif = valores.sum(axis=1) - nota.loc[validas].loc[completa]
        divergente = dif.abs() > 1e-6
        qa["validas_soma_competencias_divergente"] += int(divergente.sum())
        for codigo, val in ufs_ok.value_counts().items():
            n_uf[str(codigo)] += int(val)
        for codigo, contagem in ufs_ok.loc[divergente].value_counts().items():
            div_uf[str(codigo)] += int(contagem)
        if bool(divergente.any()):
            for codigo, valor in dif.loc[divergente].groupby(ufs_ok.loc[divergente]).sum().items():
                delta_uf[str(codigo)] += float(valor)
        tab = valores.copy()
        tab["uf"] = ufs_ok
        for i, coluna in enumerate(COMP):
            for (codigo, pontuacao), quantidade in tab.groupby(["uf", coluna], sort=False).size().items():
                freq_uf[str(codigo)][i][float(pontuacao)] += int(quantidade)

    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: fonte vazia")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: contagem status1 não fecha")
    erros = [k for k in qa if any(k.startswith(f"c{i}_") for i in range(1, 6)) and qa[k]]
    for chave in ("status1_sem_nota", "status1_nota_invalida", "validas_sem_uf",
                  "validas_uf_desconhecida", "validas_competencias_incompletas"):
        if qa[chave]:
            erros.append(chave)
    if erros:
        raise ValueError(f"{ano}: integridade de competências inválida: " +
                         ", ".join(f"{k}={qa[k]}" for k in sorted(set(erros))))
    if sum(total_uf.values()) != qa["registros"] or sum(total_uf[uf] for uf in UFS) != qa["registros"]:
        raise ValueError(f"{ano}: POP_ALL não fecha com 27 UFs")
    if sum(n_uf[uf] for uf in UFS) != qa["validas"]:
        raise ValueError(f"{ano}: POP_VALID não fecha com 27 UFs")
    if sum(div_uf.values()) != qa["validas_soma_competencias_divergente"]:
        raise ValueError(f"{ano}: divergências não reconciliadas por UF")

    br_freq = [Counter() for _ in range(5)]
    estados = []
    for uf in UFS:
        if n_uf[uf] < LIMIAR_N:
            raise ValueError(f"{ano}/{uf}: N={n_uf[uf]} inferior a {LIMIAR_N}")
        estados.append({"uf": uf, **grupo_resultado(
            n_uf[uf], freq_uf[uf], total_uf[uf], div_uf[uf], delta_uf[uf])})
        for i in range(5):
            br_freq[i].update(freq_uf[uf][i])
    br = grupo_resultado(qa["validas"], br_freq, qa["registros"],
                         sum(div_uf.values()), sum(delta_uf.values()))
    return {
        "ano": ano, "arquivo_fonte": arquivo.name, "brasil": br, "ufs": estados,
        "qualidade": {
            "status": "ok", "status1_sem_nota": qa["status1_sem_nota"],
            "status1_nota_invalida": qa["status1_nota_invalida"],
            "validas_sem_uf": qa["validas_sem_uf"],
            "validas_uf_desconhecida": qa["validas_uf_desconhecida"],
            "validas_competencias_incompletas": qa["validas_competencias_incompletas"],
            "validas_soma_competencias_divergente": qa["validas_soma_competencias_divergente"],
            "delta_soma_competencias_menos_nota_redacao": br["delta_soma_competencias_menos_nota_redacao"],
            "situacao_soma_competencias": (
                "divergencias_na_fonte" if qa["validas_soma_competencias_divergente"] else "ok"),
            "ddof": 0, "quantis": "Hyndman-Fan tipo 7 (interpolação linear)",
            "sem_amostragem": True, "soma_27_ufs_igual_brasil": True,
            "metodo": METODO,
        }, "_freq_uf": freq_uf, "_freq_br": br_freq,
    }


def validar_grupo(d: dict, frequencias: list[Counter], r1: dict, r2: dict,
                  r9: dict, r10: dict, contexto: str, historico: bool = False) -> None:
    n = d["n_validas"]
    if not all(n == x for x in (r1["redacoes_validas"], r2["n_validas"],
                               r9["n_validas"], r10["n_validas"])):
        raise ValueError(f"{contexto}: N diverge de IND-001/002/009/010")
    if not historico and not all(d["total_registros"] == x for x in
                               (r1["total_registros"], r2["total_registros"],
                                r9["total_registros"], r10["total_registros"])):
        raise ValueError(f"{contexto}: POP_ALL diverge de IND-001/002/009/010")
    if len(r9.get("competencias", [])) != 5 or len(r10.get("competencias", [])) != 5:
        raise ValueError(f"{contexto}: referências C1–C5 incompletas")
    if d["n_somas_divergentes"] != r9["n_somas_divergentes"]:
        raise ValueError(f"{contexto}: quantidade de divergências C1–C5 difere de IND-009")
    if not math.isclose(d["delta_soma_competencias_menos_nota_redacao"],
                        float(r9["delta_soma_competencias_menos_nota_redacao"]),
                        rel_tol=0, abs_tol=0.0001):
        raise ValueError(f"{contexto}: diferença C1–C5 versus nota total difere de IND-009")
    for i, c in enumerate(d["competencias"]):
        ci = f"C{i+1}"
        if c["competencia"] != ci or r9["competencias"][i]["competencia"] != ci or r10["competencias"][i]["competencia"] != ci:
            raise ValueError(f"{contexto}: ordem das competências incorreta")
        soma = math.fsum(float(v) * int(k) for v, k in frequencias[i].items())
        r9ci = r9["competencias"][i]
        if not math.isclose(soma, float(r9ci["soma_notas"]), rel_tol=0, abs_tol=0.02):
            raise ValueError(f"{contexto}/{ci}: soma não confere com IND-009")
        if abs(c["media_controle"] - float(r9ci["media"])) > 0.000051:
            raise ValueError(f"{contexto}/{ci}: média não confere com IND-009")
        if abs(c["mediana_controle"] - float(r10["competencias"][i]["mediana"])) > 0.000051:
            raise ValueError(f"{contexto}/{ci}: mediana não confere com IND-010")
        if c["p25"] > c["mediana_controle"] or c["mediana_controle"] > c["p75"]:
            raise ValueError(f"{contexto}/{ci}: ordem dos quartis incorreta")
        if abs((c["p75"] - c["p25"]) - c["iqr"]) > 0.00011:
            raise ValueError(f"{contexto}/{ci}: IQR diferente de P75-P25")


def validar_referencias(dados: list[dict], refs: dict) -> None:
    indices = {i: {d["ano"]: d for d in doc["years"]} for i, doc in refs.items()}
    for d in dados:
        ano = d["ano"]
        ra = {i: indices[i][ano] for i in indices}
        validar_grupo(d["brasil"], d["_freq_br"],
                       *[ra[i]["brasil"] for i in (1, 2, 9, 10)], str(ano))
        ru = {i: mapa_ufs(ra[i]) for i in ra}
        for u in d["ufs"]:
            uf = u["uf"]
            validar_grupo(u, d["_freq_uf"][uf],
                           *[ru[i][uf] for i in (1, 2, 9, 10)], f"{ano}/{uf}")
        if d["qualidade"]["validas_soma_competencias_divergente"] != ra[9]["qualidade"]["validas_soma_competencias_divergente"]:
            raise ValueError(f"{ano}: divergências da fonte não conferem com IND-009")
        if d["qualidade"]["validas_soma_competencias_divergente"] != ra[10]["qualidade"]["validas_soma_competencias_divergente"]:
            raise ValueError(f"{ano}: divergências da fonte não conferem com IND-010")
        d["qualidade"]["validado_contra_ind001_ind002_ind009_ind010"] = True


def consolidar_historico(dados: list[dict], refs: dict) -> dict:
    freq_uf = {uf: [Counter() for _ in range(5)] for uf in UFS}
    for d in dados:
        for uf in UFS:
            for i in range(5):
                freq_uf[uf][i].update(d["_freq_uf"][uf][i])
    ufs = []
    for uf in UFS:
        grupo_ano = [next(x for x in d["ufs"] if x["uf"] == uf) for d in dados]
        ufs.append({"uf": uf, **grupo_resultado(
            sum(x["n_validas"] for x in grupo_ano), freq_uf[uf],
            qtd_div=sum(x["n_somas_divergentes"] for x in grupo_ano),
            delta=math.fsum(x["delta_soma_competencias_menos_nota_redacao"] for x in grupo_ano))})
    freq_br = [Counter() for _ in range(5)]
    for uf in UFS:
        for i in range(5):
            freq_br[i].update(freq_uf[uf][i])
    br = grupo_resultado(
        sum(x["brasil"]["n_validas"] for x in dados), freq_br,
        qtd_div=sum(x["brasil"]["n_somas_divergentes"] for x in dados),
        delta=math.fsum(x["brasil"]["delta_soma_competencias_menos_nota_redacao"] for x in dados))
    if br["n_validas"] != sum(u["n_validas"] for u in ufs):
        raise ValueError("Histórico: N das UFs não fecha com BR")
    r = {i: refs[i]["historical"] for i in refs}
    validar_grupo(br, freq_br, *[r[i]["brasil"] for i in (1, 2, 9, 10)], "2019–2025/BR", True)
    ru = {i: mapa_ufs(r[i]) for i in r}
    for u in ufs:
        uf = u["uf"]
        validar_grupo(u, freq_uf[uf], *[ru[i][uf] for i in (1, 2, 9, 10)], f"2019–2025/{uf}", True)
    return {"periodo": "2019-2025", "brasil": br, "ufs": ufs, "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    linhas = []
    periodos = [(str(d["ano"]), d["arquivo_fonte"], d) for d in dados]
    periodos.append(("2019-2025", "TODAS_AS_EDICOES", historico))
    for periodo, arquivo, secao in periodos:
        grupos = [("BRASIL", "BR", secao["brasil"])] + [("UF", u["uf"], u) for u in secao["ufs"]]
        for abrangencia, uf, g in grupos:
            for c in g["competencias"]:
                linhas.append({
                    "indicador_id": INDICADOR, "periodo": periodo,
                    "abrangencia": abrangencia, "uf": uf,
                    "competencia": c["competencia"], "variavel": c["variavel"],
                    "n_validas": g["n_validas"], "media_controle": c["media_controle"],
                    "mediana_controle": c["mediana_controle"], "p25": c["p25"],
                    "p75": c["p75"], "iqr": c["iqr"],
                    "desvio_padrao": c["desvio_padrao"], "variancia": c["variancia"],
                    "ddof": 0, "populacao": "POP_VALID", "metodo": METODO,
                    "n_somas_divergentes": g["n_somas_divergentes"],
                    "delta_soma_competencias_menos_nota_redacao": g["delta_soma_competencias_menos_nota_redacao"],
                    "arquivo_fonte": arquivo,
                })
    if len(linhas) != 8 * 28 * 5:
        raise AssertionError(f"Linhas CSV={len(linhas)}, esperado 1120")
    if len({(x["periodo"], x["uf"], x["competencia"]) for x in linhas}) != len(linhas):
        raise AssertionError("CSV: chaves duplicadas")
    return linhas


def item_dashboard(c: dict) -> dict:
    return {"competency": c["competencia"], "label": c["descricao"],
            "variable": c["variavel"], "n": c["n"], "max_score": 200,
            "std_score": c["desvio_padrao"], "variance": c["variancia"],
            "p25_score": c["p25"], "median_score": c["mediana_controle"],
            "p75_score": c["p75"], "iqr_score": c["iqr"], "ddof": 0}


def construir_dashboard(d: dict, dados: list[dict], h: dict, base: dict, gerado: str) -> dict:
    ano = d["ano"]
    p = deepcopy(base)
    br = d["brasil"]
    comp = p["pages"]["competencies"]
    if comp["ind009"]["n"] != br["n_validas"] or comp["ind010"]["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N divergente de IND-009/010")
    if p["pages"]["overview"]["kpis"]["valid_essays"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: POP_VALID divergente do IND-001")
    u9 = mapa_ufs({"ufs": comp["ind009"]["by_uf"]})
    u10 = mapa_ufs({"ufs": comp["ind010"]["by_uf"]})
    for u in d["ufs"]:
        if u["n_validas"] != u9[u["uf"]]["n"] or u["n_validas"] != u10[u["uf"]]["n"]:
            raise ValueError(f"Dashboard {ano}/{u['uf']}: N divergente no resumo anterior")
    novo = [item_dashboard(c) for c in br["competencias"]]
    if len(comp["summary"]) != 5:
        raise ValueError(f"Dashboard {ano}: resumo de competências incompleto")
    for i, (anterior, atual) in enumerate(zip(comp["summary"], novo), 1):
        if anterior.get("competency") != f"C{i}" or anterior.get("n") != br["n_validas"]:
            raise ValueError(f"Dashboard {ano}: ordem das competências ou população divergente")
        if "mean_score" not in anterior or "median_score" not in anterior:
            raise ValueError(f"Dashboard {ano}: resumos IND-009/010 não concluídos")
        if abs(float(anterior["median_score"]) - atual["median_score"]) > 0.000051:
            raise ValueError(f"Dashboard {ano}: mediana C{i} não confere com IND-010")
        anterior.update({k: atual[k] for k in ("std_score", "variance", "p25_score", "p75_score", "iqr_score", "ddof")})
    comp["dispersion"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID", "method": METODO,
        "std_ddof": 0, "quartile_method": "hyndman_fan_tipo_7_linear",
        "n": br["n_validas"], "unit": "pontos",
        "national_summary": novo,
        "by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                   "summary": [item_dashboard(c) for c in u["competencias"]]}
                  for u in d["ufs"]],
    }
    p["pages"]["temporal"]["ind011"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID",
        "national_by_year": [{"year": x["ano"], "n": x["brasil"]["n_validas"],
                              "summary": [item_dashboard(c) for c in x["brasil"]["competencias"]]}
                             for x in dados],
        "period_total": {"n": h["brasil"]["n_validas"],
                         "summary": [item_dashboard(c) for c in h["brasil"]["competencias"]]},
        "period_by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                          "summary": [item_dashboard(c) for c in u["competencias"]]}
                         for u in h["ufs"]], "note": NOTA_HISTORICA,
    }
    p["pages"]["methodology"]["ind011"] = {
        "definition": DEFINICAO, "population": "POP_VALID",
        "geographic_dimension": "SG_UF_PROVA", "source_file": d["arquivo_fonte"],
        "standard_deviation": "populacional ddof=0, duas passagens, denominador N",
        "quantiles": "Hyndman-Fan tipo 7 (NumPy linear), P25 e P75",
        "iqr": "P75-P25", "precision": "4 casas decimais; 0–200 pontos",
        "integrity": INTEGRIDADE, "historical_note": NOTA_HISTORICA,
    }
    p["quality"]["ind011_validation"] = deepcopy(d["qualidade"])
    p["meta"]["analysis_version"] = VERSAO
    p["meta"]["generated_at"] = gerado
    p["meta"]["data_status"] = "draft"
    avisos = p["meta"].setdefault("warnings", [])
    aviso = "IND-011: dispersão C1–C5 validada computacionalmente; revisão acadêmica ainda pendente."
    if aviso not in avisos:
        avisos.append(aviso)
    if br["n_somas_divergentes"]:
        aviso_fonte = (f"IND-011/{ano}: {br['n_somas_divergentes']} redação(ões) com soma das "
                       "competências divergente da nota total; notas originais preservadas.")
        if aviso_fonte not in avisos:
            avisos.append(aviso_fonte)
    return p


def validar_dashboard(d: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(d):
        raise ValueError("Dashboard sem campos essenciais")
    if "NU_INSCRICAO" in json.dumps(d, ensure_ascii=False):
        raise ValueError("Identificador de participante detectado no dashboard")
    locais = (raiz / "docs" / "04_resultados_analises.schema.json",
              raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
              raiz / "04_resultados_analises.schema.json")
    encontrado = next((p for p in locais if p.is_file()), None)
    if encontrado is None:
        return "estrutura verificada (schema não localizado)"
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError("jsonschema é necessário quando o schema estiver disponível") from exc
    with encontrado.open(encoding="utf-8") as f:
        jsonschema.validate(d, json.load(f))
    return "JSON Schema v1.0.0"


def salvar_json(path: Path, dados: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    tmp.replace(path)


def salvar_csv(path: Path, linhas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    tmp.replace(path)


def executar(raiz: Path, bloco: int = TAMANHO_BLOCO) -> None:
    refs, dashboards = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f"IND-011 | {ano}: processando {fonte(ano, raiz).name} ...", flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        resumo = ", ".join(f"C{i+1}: σ={c['desvio_padrao']:.4f}, IQR={c['iqr']:.4f}"
                            for i, c in enumerate(d["brasil"]["competencias"]))
        print(f"  válidas={d['brasil']['n_validas']:,} | {resumo}", flush=True)
        if d["qualidade"]["validas_soma_competencias_divergente"]:
            print("  AVISO FONTE: " + str(d["qualidade"]["validas_soma_competencias_divergente"])
                  + " registro(s) divergentes C1–C5 preservados e auditados.", flush=True)
    validar_referencias(dados, refs)
    hist = consolidar_historico(dados, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    novos = {d["ano"]: construir_dashboard(d, dados, hist, dashboards[d["ano"]], gerado)
             for d in dados}
    resultados_schema = {validar_dashboard(p, raiz) for p in novos.values()}
    for d in dados:
        d.pop("_freq_uf")
        d.pop("_freq_br")
    saida = {
        "meta": {
            "indicator_id": INDICADOR, "module_schema_version": "ind011-module-1.0.0",
            "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado, "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
            "method": METODO, "comparison_ind001_ind002_ind009_ind010": "aprovada",
            "historical_note": NOTA_HISTORICA,
            "source_discrepancies": {
                str(d["ano"]): {"count": d["brasil"]["n_somas_divergentes"],
                                "delta_total": d["brasil"]["delta_soma_competencias_menos_nota_redacao"]}
                for d in dados},
        },
        "indicator": {"id": INDICADOR, "name": "Dispersão C1–C5", "unit": "pontos",
                      "dashboard_json_path": "pages.competencies.dispersion"},
        "years": dados, "historical": hist,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    linhas = linhas_csv(dados, hist)
    json.dumps(saida, ensure_ascii=False, allow_nan=False)
    pasta = raiz / "outputs"
    salvar_csv(pasta / "indicadores" / "IND_011_dispersao_competencias.csv", linhas)
    salvar_json(pasta / "json" / "IND_011_dispersao_competencias.json", saida)
    for ano in ANOS:
        salvar_json(pasta / "json" / f"dashboard_enem_{ano}.json", novos[ano])
    print("\nIND-011 concluído:")
    print(f"  IND_011_dispersao_competencias.csv ({len(linhas)} linhas)")
    print("  IND_011_dispersao_competencias.json")
    print("  dashboards 2019–2025 atualizados (IND-001–010 preservados)")
    print("  Esquema: " + ", ".join(sorted(resultados_schema)))
    print("  data_status=draft | validação real e acadêmica ainda pendentes")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-011 — dispersão C1–C5 ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--bloco", type=int, default=TAMANHO_BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser inteiro positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
