#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-012 — Distribuição dos níveis observados nas competências (ENEM 2019–2025).

Catálogo: Competências / Distribuição dos níveis / prioridade P0.
Variáveis NU_NOTA_COMP1..5; população POP_VALID; COUNT e proporção POR VALOR
REALMENTE OBSERVADO; saída matriz em pages.competencies.level_distribution.

NÃO converter notas em faixas pré-definidas ou supor apenas múltiplos de 40.
Preserva, portanto, valores atípicos observados, inclusive C3=10 na exceção
já identificada em SC/2023. Não inventa, corrige nem exclui essas notas.
Valida frequências, somatórios, médias, medianas e dispersões contra IND-001,
IND-002, IND-009, IND-010 e IND-011. O histórico é a SOMA das frequências
observadas, não a média dos percentuais anuais.

Requer todos os indicadores 001–011 concluídos em outputs/json.
Executar na raiz do projeto depois que IND-011 terminar:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_012_distribuicao_niveis_competencias.py

Saídas:
  outputs/indicadores/IND_012_distribuicao_niveis_competencias.csv
  outputs/json/IND_012_distribuicao_niveis_competencias.json
  outputs/json/dashboard_enem_{2019..2025}.json

Somente a análise agregada é gravada; nunca registros individuais. A revisão
acadêmica e de privacidade permanece pendente: sinaliza células com 1–29
ocorrências (limiar conservador do projeto), mas não mascara automaticamente,
pois supressão complementar depende da política de divulgação adotada.
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
ROTULOS = (
    "Domínio da modalidade escrita formal da língua portuguesa",
    "Compreensão da proposta e desenvolvimento do tema",
    "Seleção, organização e interpretação de informações e argumentos",
    "Conhecimento dos mecanismos linguísticos de argumentação",
    "Elaboração de proposta de intervenção",
)
INDICADOR = "IND-012"
VERSAO = "2.11.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010-ind011-ind012"
METODO = "frequencia_proporcao_valor_observado_competencias_pop_valid"
LIMIAR = 30
BLOCO = 100_000
DEFINICAO = (
    "Contagem e proporção de cada pontuação numericamente observada entre 0 e 200 "
    "para cada competência C1–C5 entre redações válidas (TP_STATUS_REDACAO=1 e "
    "NU_NOTA_REDACAO numérica no intervalo 0–1000). Não agrupar nem presumir "
    "apenas múltiplos de 40; cada pontuação efetivamente observada é um nível."
)
NOTA_HISTORICA = (
    "O consolidado de 2019–2025 agrega as frequências absolutas de cada valor "
    "observado nas sete edições e recalcula as proporções pelo total histórico "
    "de redações válidas. São participações, não pessoas únicas. A UF corresponde "
    "ao local de aplicação (SG_UF_PROVA), não ao de residência."
)
INTEGRIDADE = (
    "Todas as cinco competências de POP_VALID devem ser numéricas e estar entre 0 e "
    "200; casos com soma C1–C5 diferente de NU_NOTA_REDACAO são preservados, "
    "sem imputação, correção ou exclusão, e reconciliados com IND-009/010/011."
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
    ufs = grupo.get("ufs", [])
    if len(ufs) != len(UFS) or {u.get("uf") for u in ufs} != set(UFS):
        raise ValueError("Referência incompleta: esperadas 27 UFs sem duplicação")
    return {u["uf"]: u for u in ufs}


def carregar_referencias(raiz: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    nomes = {1: "redacoes_validas", 2: "nota_media", 9: "media_competencias",
             10: "mediana_competencias", 11: "dispersao_competencias"}
    refs = {}
    for num, nome in nomes.items():
        arquivo = pasta / f"IND_{num:03d}_{nome}.json"
        doc = ler_json(arquivo)
        if doc.get("indicator", {}).get("id") != f"IND-{num:03d}":
            raise ValueError(f"{arquivo.name}: indicator.id divergente")
        if sorted(x.get("ano") for x in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"{arquivo.name}: edições ausentes ou duplicadas")
        for grupo in [*doc["years"], doc["historical"]]:
            mapa_ufs(grupo)
        refs[num] = doc
    for ano in ANOS:
        d9 = next(x for x in refs[9]["years"] if x["ano"] == ano)
        d10 = next(x for x in refs[10]["years"] if x["ano"] == ano)
        d11 = next(x for x in refs[11]["years"] if x["ano"] == ano)
        if any("n_somas_divergentes" not in z["brasil"] for z in (d9, d11)) or \
           "validas_soma_competencias_divergente" not in d10.get("qualidade", {}):
            raise ValueError(f"{ano}: utilize IND-009, IND-010 e IND-011 corrigidos")
    dashboards = {}
    for ano in ANOS:
        d = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if d.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}: meta.year incorreto")
        if d.get("meta", {}).get("data_status") != "draft":
            raise ValueError(f"dashboard_enem_{ano}: esperado data_status=draft")
        p = d.get("pages", {}).get("competencies", {})
        if p.get("status") != "ok" or any(k not in p for k in ("ind009", "ind010", "summary", "dispersion")):
            raise ValueError(f"dashboard_enem_{ano}: aguarde IND-011 concluir os sete dashboards")
        if len(p["summary"]) != 5 or len(p["dispersion"].get("national_summary", [])) != 5:
            raise ValueError(f"dashboard_enem_{ano}: C1–C5 incompletas")
        for num in (9, 10, 11):
            if d.get("quality", {}).get(f"ind{num:03d}_validation", {}).get("status") != "ok":
                raise ValueError(f"dashboard_enem_{ano}: qualidade IND-{num:03d} ausente")
        if not all(f"ind{i:03d}" in d["pages"].get("overview", {}) for i in range(1, 6)):
            raise ValueError(f"dashboard_enem_{ano}: indicadores 001–005 ausentes")
        if any(k not in d["pages"]["overview"] for k in ("score_distribution", "essay_status", "ind008")):
            raise ValueError(f"dashboard_enem_{ano}: indicadores 006–008 ausentes")
        dashboards[ano] = d
    return refs, dashboards


def frequencia_estatisticas(freq: Counter, n: int) -> dict:
    """Estatísticas para conciliar com IND-009/010/011, sem inferir níveis."""
    if n <= 0 or sum(freq.values()) != n:
        raise ValueError(f"N ou somatório de níveis incompatível: {n}")
    pares = sorted(freq.items())
    soma = math.fsum(float(v) * int(k) for v, k in pares)
    media = soma / n
    var = math.fsum((float(v) - media) ** 2 * int(k) for v, k in pares) / n
    quantis = {}
    for p in (0.25, 0.5, 0.75):
        h = (n - 1) * p
        baixo = int(math.floor(h))
        alto = min(n - 1, baixo + 1)
        alvos = (baixo, alto)
        resultados = []
        for alvo in alvos:
            acumulado = 0
            achou = False
            for valor, cont in pares:
                acumulado += int(cont)
                if alvo < acumulado:
                    resultados.append(float(valor))
                    achou = True
                    break
            if not achou:
                raise ValueError("Posição de quantil não encontrada")
        quantis[p] = resultados[0] + (h - baixo) * (resultados[1] - resultados[0])
    return {"soma": soma, "media": round(media, 4), "mediana": round(quantis[0.5], 4),
            "p25": round(quantis[0.25], 4), "p75": round(quantis[0.75], 4),
            "iqr": round(quantis[0.75] - quantis[0.25], 4),
            "std": round(math.sqrt(max(0.0, var)), 4), "var": round(var, 4)}


def nivel_json(valor: float) -> int | float:
    """Preserva valores observados; serializa números inteiros sem .0."""
    v = float(valor)
    if not math.isfinite(v) or not 0 <= v <= 200:
        raise ValueError(f"Valor de competência inválido: {valor}")
    return int(v) if v.is_integer() else v


def grupo_resultado(n: int, frequencias: list[Counter],
                    total_registros: int | None = None,
                    n_divergentes: int = 0, delta: float = 0.0) -> dict:
    if n < LIMIAR or len(frequencias) != 5:
        raise ValueError(f"POP_VALID insuficiente ou competências incompletas: n={n}")
    cs = []
    for i, freq in enumerate(frequencias):
        controle = frequencia_estatisticas(freq, n)
        niveis = []
        for valor, quantidade in sorted(freq.items()):
            if quantidade <= 0:
                raise ValueError(f"Frequência inválida em C{i+1}: {valor}={quantidade}")
            valor_normalizado = nivel_json(valor)
            niveis.append({
                "pontuacao": valor_normalizado, "quantidade": int(quantidade),
                "proporcao": round(quantidade / n, 8),
                "percentual": round(100 * quantidade / n, 4),
                "requer_revisao_privacidade": bool(0 < quantidade < LIMIAR),
            })
        cs.append({
            "competencia": f"C{i+1}", "variavel": COMP[i], "descricao": ROTULOS[i],
            "n": n, "escala_maxima": 200, "quantidade_niveis_observados": len(niveis),
            "niveis": niveis,
            "celulas_positivas_inferiores_30": sum(x["requer_revisao_privacidade"] for x in niveis),
            "controle": {"soma_notas": controle["soma"],
                         "media": controle["media"], "mediana": controle["mediana"],
                         "p25": controle["p25"], "p75": controle["p75"],
                         "iqr": controle["iqr"], "desvio_padrao": controle["std"],
                         "variancia": controle["var"], "ddof": 0},
        })
    saida = {"n_validas": n, "competencias": cs,
             "n_somas_divergentes": int(n_divergentes),
             "delta_soma_competencias_menos_nota_redacao": round(float(delta), 6)}
    if total_registros is not None:
        saida["total_registros"] = int(total_registros)
    return saida


def processar_ano(ano: int, raiz: Path, bloco: int = BLOCO) -> dict:
    arquivo = fonte(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Fonte não localizada: {arquivo}")
    qa = Counter()
    todos_uf = Counter({uf: 0 for uf in UFS})
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
        valido = st1 & nota_ok
        uf_ok = uf.isin(UFS)
        qa["registros"] += len(parte)
        qa["status1"] += int(st1.sum())
        qa["validas"] += int(valido.sum())
        qa["status1_sem_nota"] += int((st1 & texto.eq("")).sum())
        qa["status1_nota_invalida"] += int((st1 & texto.ne("") & ~nota_ok).sum())
        qa["validas_sem_uf"] += int((valido & uf.eq("")).sum())
        qa["validas_uf_desconhecida"] += int((valido & ~uf_ok & uf.ne("")).sum())
        todos_uf.update({str(k): int(v) for k, v in uf.value_counts().items()})
        if not bool(valido.any()):
            continue
        crus = parte.loc[valido, list(COMP)].apply(lambda s: s.str.strip())
        valores = crus.apply(lambda s: pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce"))
        completos = valores.notna() & valores.ge(0) & valores.le(200)
        for i, col in enumerate(COMP, 1):
            qa[f"c{i}_ausente"] += int(crus[col].eq("").sum())
            qa[f"c{i}_invalida"] += int((crus[col].ne("") & ~completos[col]).sum())
        linha_ok = completos.all(axis=1)
        qa["validas_competencias_incompletas"] += int((~linha_ok).sum())
        if not bool(linha_ok.any()):
            continue
        cval = valores.loc[linha_ok]
        ufs_validas = uf.loc[valido].loc[linha_ok]
        diferenca = cval.sum(axis=1) - nota.loc[valido].loc[linha_ok]
        divergentes = diferenca.abs() > 1e-6
        qa["validas_soma_competencias_divergente"] += int(divergentes.sum())
        for codigo, quantidade in ufs_validas.value_counts().items():
            n_uf[str(codigo)] += int(quantidade)
        for codigo, quantidade in ufs_validas.loc[divergentes].value_counts().items():
            div_uf[str(codigo)] += int(quantidade)
        if bool(divergentes.any()):
            for codigo, valor in diferenca.loc[divergentes].groupby(ufs_validas.loc[divergentes]).sum().items():
                delta_uf[str(codigo)] += float(valor)
        temp = cval.copy()
        temp["uf"] = ufs_validas
        for i, col in enumerate(COMP):
            for (sigla, pontuacao), quantidade in temp.groupby(["uf", col], sort=False).size().items():
                freq_uf[str(sigla)][i][float(pontuacao)] += int(quantidade)
    if qa["registros"] <= 0:
        raise ValueError(f"{ano}: fonte vazia")
    if qa["status1"] != qa["validas"] + qa["status1_sem_nota"] + qa["status1_nota_invalida"]:
        raise ValueError(f"{ano}: status1 não reconciliado")
    erros = []
    for chave in ("status1_sem_nota", "status1_nota_invalida", "validas_sem_uf",
                  "validas_uf_desconhecida", "validas_competencias_incompletas"):
        if qa[chave]:
            erros.append(f"{chave}={qa[chave]}")
    for i in range(1, 6):
        for suf in ("ausente", "invalida"):
            k = f"c{i}_{suf}"
            if qa[k]:
                erros.append(f"{k}={qa[k]}")
    if erros:
        raise ValueError(f"{ano}: erro de integridade: " + ", ".join(erros))
    if sum(todos_uf.values()) != qa["registros"] or sum(todos_uf[uf] for uf in UFS) != qa["registros"]:
        raise ValueError(f"{ano}: POP_ALL não fecha com as 27 UFs")
    if sum(n_uf[uf] for uf in UFS) != qa["validas"]:
        raise ValueError(f"{ano}: POP_VALID não fecha com as 27 UFs")
    if sum(div_uf.values()) != qa["validas_soma_competencias_divergente"]:
        raise ValueError(f"{ano}: divergências C1–C5 não conciliadas por UF")
    br_freq = [Counter() for _ in range(5)]
    estados = []
    for sigla in UFS:
        estados.append({"uf": sigla, **grupo_resultado(n_uf[sigla], freq_uf[sigla],
                     todos_uf[sigla], div_uf[sigla], delta_uf[sigla])})
        for i in range(5):
            br_freq[i].update(freq_uf[sigla][i])
    br = grupo_resultado(qa["validas"], br_freq, qa["registros"],
                         sum(div_uf.values()), sum(delta_uf.values()))
    pequenas_uf = sum(c["celulas_positivas_inferiores_30"]
                       for u in estados for c in u["competencias"])
    pequenas_br = sum(c["celulas_positivas_inferiores_30"] for c in br["competencias"])
    return {"ano": ano, "arquivo_fonte": arquivo.name, "brasil": br, "ufs": estados,
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
                "celulas_uf_positivas_inferiores_30": pequenas_uf,
                "celulas_brasil_positivas_inferiores_30": pequenas_br,
                "revisao_privacidade_obrigatoria_antes_de_publicar": bool(pequenas_uf or pequenas_br),
                "valores_observados_nao_agrupados": True,
                "soma_frequencias_igual_populacao": True,
                "soma_27_ufs_igual_brasil": True,
                "metodo": METODO,
            }, "_freq_uf": freq_uf, "_freq_br": br_freq}


def validar_grupo(g: dict, frequencias: list[Counter], refs: dict[int, dict], contexto: str,
                   historico: bool = False) -> None:
    n = g["n_validas"]
    if not all(n == refs[i].get("redacoes_validas" if i == 1 else "n_validas")
               for i in (1, 2, 9, 10, 11)):
        raise ValueError(f"{contexto}: POP_VALID não corresponde aos IND-001/002/009/010/011")
    if not historico and not all(g["total_registros"] == refs[i]["total_registros"]
                                for i in (1, 2, 9, 10, 11)):
        raise ValueError(f"{contexto}: POP_ALL não corresponde aos indicadores anteriores")
    if g["n_somas_divergentes"] != refs[9]["n_somas_divergentes"] or \
       g["n_somas_divergentes"] != refs[11]["n_somas_divergentes"]:
        raise ValueError(f"{contexto}: quantidade de divergências de origem mudou")
    for k in (9, 11):
        if not math.isclose(g["delta_soma_competencias_menos_nota_redacao"],
                            float(refs[k]["delta_soma_competencias_menos_nota_redacao"]),
                            rel_tol=0, abs_tol=0.0001):
            raise ValueError(f"{contexto}: delta de origem não confere com IND-{k:03d}")
    for i, comp in enumerate(g["competencias"]):
        ident = f"C{i+1}"
        for j in (9, 10, 11):
            if len(refs[j].get("competencias", [])) != 5 or refs[j]["competencias"][i]["competencia"] != ident:
                raise ValueError(f"{contexto}: referência C1–C5 incompleta ou desordenada")
        if comp["competencia"] != ident:
            raise ValueError(f"{contexto}: competência na ordem incorreta")
        r9 = refs[9]["competencias"][i]
        r10 = refs[10]["competencias"][i]
        r11 = refs[11]["competencias"][i]
        m = comp["controle"]
        if not math.isclose(m["soma_notas"], float(r9["soma_notas"]), rel_tol=0, abs_tol=0.02):
            raise ValueError(f"{contexto}/{ident}: soma de notas diverge IND-009")
        comparacoes = [("media", r9["media"]), ("mediana", r10["mediana"]),
                       ("p25", r11["p25"]), ("p75", r11["p75"]),
                       ("iqr", r11["iqr"]), ("desvio_padrao", r11["desvio_padrao"]),
                       ("variancia", r11["variancia"])]
        for chave, ref in comparacoes:
            if abs(m[chave] - float(ref)) > 0.000051:
                raise ValueError(f"{contexto}/{ident}: {chave}={m[chave]} diferente da referência {ref}")
        if sum(x["quantidade"] for x in comp["niveis"]) != n:
            raise ValueError(f"{contexto}/{ident}: soma das frequências diferente de POP_VALID")
        if not all(comp["niveis"][idx]["pontuacao"] < comp["niveis"][idx + 1]["pontuacao"]
                   for idx in range(len(comp["niveis"]) - 1)):
            raise ValueError(f"{contexto}/{ident}: níveis repetidos ou desordenados")
        if Counter({float(x["pontuacao"]): x["quantidade"] for x in comp["niveis"]}) != frequencias[i]:
            raise ValueError(f"{contexto}/{ident}: níveis não reproduzem distribuição observada")


def validar_referencias(dados: list[dict], refs: dict) -> None:
    indices = {i: {d["ano"]: d for d in doc["years"]} for i, doc in refs.items()}
    for d in dados:
        ano = d["ano"]
        r = {i: indices[i][ano] for i in indices}
        validar_grupo(d["brasil"], d["_freq_br"], {i: r[i]["brasil"] for i in r}, f"{ano}/BR")
        por_uf = {i: mapa_ufs(r[i]) for i in r}
        for u in d["ufs"]:
            sigla = u["uf"]
            validar_grupo(u, d["_freq_uf"][sigla],
                          {i: por_uf[i][sigla] for i in r}, f"{ano}/{sigla}")
        for i in (9, 10, 11):
            if d["qualidade"]["validas_soma_competencias_divergente"] != \
               r[i]["qualidade"]["validas_soma_competencias_divergente"]:
                raise ValueError(f"{ano}: inconsistência de origem diferente de IND-{i:03d}")
        d["qualidade"]["validado_contra_ind001_ind002_ind009_ind010_ind011"] = True


def consolidar_historico(dados: list[dict], refs: dict) -> dict:
    combinados = {uf: [Counter() for _ in range(5)] for uf in UFS}
    for d in dados:
        for uf in UFS:
            for i in range(5):
                combinados[uf][i].update(d["_freq_uf"][uf][i])
    estados = []
    for uf in UFS:
        anuais = [next(x for x in d["ufs"] if x["uf"] == uf) for d in dados]
        estados.append({"uf": uf, **grupo_resultado(
            sum(x["n_validas"] for x in anuais), combinados[uf],
            n_divergentes=sum(x["n_somas_divergentes"] for x in anuais),
            delta=math.fsum(x["delta_soma_competencias_menos_nota_redacao"] for x in anuais))})
    br_freq = [Counter() for _ in range(5)]
    for uf in UFS:
        for i in range(5):
            br_freq[i].update(combinados[uf][i])
    br = grupo_resultado(
        sum(x["brasil"]["n_validas"] for x in dados), br_freq,
        n_divergentes=sum(x["brasil"]["n_somas_divergentes"] for x in dados),
        delta=math.fsum(x["brasil"]["delta_soma_competencias_menos_nota_redacao"] for x in dados))
    if br["n_validas"] != sum(u["n_validas"] for u in estados):
        raise ValueError("Histórico: N Brasil não fecha com as 27 UFs")
    r = {i: doc["historical"] for i, doc in refs.items()}
    validar_grupo(br, br_freq, {i: r[i]["brasil"] for i in r}, "2019-2025/BR", True)
    por_uf = {i: mapa_ufs(r[i]) for i in r}
    for u in estados:
        uf = u["uf"]
        validar_grupo(u, combinados[uf], {i: por_uf[i][uf] for i in r}, f"2019-2025/{uf}", True)
    return {"periodo": "2019-2025", "brasil": br, "ufs": estados,
            "qualidade": {
                "celulas_uf_positivas_inferiores_30": sum(
                    c["celulas_positivas_inferiores_30"] for u in estados for c in u["competencias"]),
                "celulas_brasil_positivas_inferiores_30": sum(
                    c["celulas_positivas_inferiores_30"] for c in br["competencias"]),
                "metodo": METODO},
            "nota": NOTA_HISTORICA}


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    linhas = []
    periodos = [(str(d["ano"]), d["arquivo_fonte"], d) for d in dados]
    periodos.append(("2019-2025", "TODAS_AS_EDICOES", historico))
    for periodo, arquivo, secao in periodos:
        grupos = [("BRASIL", "BR", secao["brasil"])] + [("UF", u["uf"], u) for u in secao["ufs"]]
        for abrangencia, uf, grupo in grupos:
            for c in grupo["competencias"]:
                for nivel in c["niveis"]:
                    linhas.append({
                        "indicador_id": INDICADOR, "periodo": periodo,
                        "abrangencia": abrangencia, "uf": uf,
                        "competencia": c["competencia"], "variavel": c["variavel"],
                        "pontuacao": nivel["pontuacao"], "quantidade": nivel["quantidade"],
                        "proporcao": nivel["proporcao"], "percentual": nivel["percentual"],
                        "n_validas": grupo["n_validas"], "populacao": "POP_VALID",
                        "requer_revisao_privacidade": nivel["requer_revisao_privacidade"],
                        "n_somas_divergentes": grupo["n_somas_divergentes"],
                        "metodo": METODO, "arquivo_fonte": arquivo,
                    })
    if not linhas:
        raise ValueError("Distribuição de níveis vazia")
    if len({(x["periodo"], x["uf"], x["competencia"], x["pontuacao"]) for x in linhas}) != len(linhas):
        raise AssertionError("CSV apresenta chaves duplicadas")
    return linhas


def itens_dashboard(c: dict) -> dict:
    return {"competency": c["competencia"], "label": c["descricao"],
            "variable": c["variavel"], "n": c["n"], "max_score": 200,
            "levels": [{"score": x["pontuacao"], "count": x["quantidade"],
                        "proportion": x["proporcao"], "percentage": x["percentual"],
                        "requires_privacy_review": x["requer_revisao_privacidade"]}
                       for x in c["niveis"]],
            "observed_level_count": c["quantidade_niveis_observados"]}


def construir_dashboard(d: dict, dados: list[dict], historico: dict, base: dict, gerado: str) -> dict:
    ano = d["ano"]
    dash = deepcopy(base)
    comp = dash["pages"]["competencies"]
    br = d["brasil"]
    if dash["pages"]["overview"]["kpis"]["valid_essays"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N do IND-001 não confere")
    if comp["dispersion"]["n"] != br["n_validas"]:
        raise ValueError(f"Dashboard {ano}: N do IND-011 não confere")
    u11 = {u["uf"]: u for u in comp["dispersion"]["by_uf"]}
    if set(u11) != set(UFS):
        raise ValueError(f"Dashboard {ano}: dados IND-011 UF incompletos")
    if any(u["n_validas"] != u11[u["uf"]]["n"] for u in d["ufs"]):
        raise ValueError(f"Dashboard {ano}: N por UF diverge do IND-011")
    for i, item in enumerate(comp["summary"]):
        ci = br["competencias"][i]
        if item.get("competency") != ci["competencia"] or item.get("n") != br["n_validas"]:
            raise ValueError(f"Dashboard {ano}: ordem ou N de C1–C5 incorretos")
        if abs(float(item["mean_score"]) - ci["controle"]["media"]) > 0.000051 or \
           abs(float(item["median_score"]) - ci["controle"]["mediana"]) > 0.000051:
            raise ValueError(f"Dashboard {ano}: resumo IND-009/010 incompatível")
        if abs(float(item["std_score"]) - ci["controle"]["desvio_padrao"]) > 0.000051:
            raise ValueError(f"Dashboard {ano}: resumo IND-011 incompatível")
    comp["level_distribution"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID", "method": METODO,
        "geographic_dimension": "SG_UF_PROVA", "unit": "redacoes",
        "n": br["n_validas"], "national_summary": [itens_dashboard(c) for c in br["competencias"]],
        "by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                   "summary": [itens_dashboard(c) for c in u["competencias"]]}
                  for u in d["ufs"]],
        "privacy_note": "Revisar contagens positivas abaixo de 30 e supressão complementar antes da divulgação.",
    }
    dash["pages"]["temporal"]["ind012"] = {
        "indicator_id": INDICADOR, "population": "POP_VALID", "method": METODO,
        "national_by_year": [{"year": x["ano"], "n": x["brasil"]["n_validas"],
                              "summary": [itens_dashboard(c) for c in x["brasil"]["competencias"]]}
                             for x in dados],
        "period_total": {"n": historico["brasil"]["n_validas"],
                         "summary": [itens_dashboard(c) for c in historico["brasil"]["competencias"]]},
        "period_by_uf": [{"uf": u["uf"], "n": u["n_validas"],
                          "summary": [itens_dashboard(c) for c in u["competencias"]]}
                         for u in historico["ufs"]], "note": NOTA_HISTORICA,
    }
    dash["pages"]["methodology"]["ind012"] = {
        "definition": DEFINICAO, "population": "POP_VALID",
        "geographic_dimension": "SG_UF_PROVA", "source_file": d["arquivo_fonte"],
        "method": METODO, "level_rule": "valores numéricos efetivamente observados, sem faixas predefinidas",
        "denominator": "número de redações válidas por edição e UF, independentemente para C1–C5",
        "proportion": "quantidade no nível / n_validas",
        "percentage": "100 x proporção; quatro casas decimais",
        "privacy_threshold": "contagens positivas de 1 a 29 apenas sinalizadas, não suprimidas",
        "integrity": INTEGRIDADE, "historical_note": NOTA_HISTORICA,
    }
    dash["quality"]["ind012_validation"] = deepcopy(d["qualidade"])
    dash["meta"]["analysis_version"] = VERSAO
    dash["meta"]["generated_at"] = gerado
    dash["meta"]["data_status"] = "draft"
    avisos = dash["meta"].setdefault("warnings", [])
    aviso = "IND-012: frequências por valor observado validadas computacionalmente; revisão acadêmica e privacidade pendentes."
    if aviso not in avisos:
        avisos.append(aviso)
    if d["qualidade"]["revisao_privacidade_obrigatoria_antes_de_publicar"]:
        aviso = "IND-012: existem níveis de competências com 1–29 redações; não publicar sem revisão de privacidade e supressão complementar."
        if aviso not in avisos:
            avisos.append(aviso)
    if br["n_somas_divergentes"]:
        aviso = (f"IND-012/{ano}: {br['n_somas_divergentes']} registro(s) com soma de competências "
                 "divergente da nota total, sem imputação ou exclusão.")
        if aviso not in avisos:
            avisos.append(aviso)
    return dash


def validar_dashboard(d: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(d):
        raise ValueError("Dashboard sem campos essenciais")
    # Não emitir identificadores de participantes; distribuição contém apenas agregados.
    if "NU_INSCRICAO" in json.dumps(d, ensure_ascii=False):
        raise ValueError("Identificador de inscrição encontrado no dashboard")
    possiveis = (raiz / "docs" / "04_resultados_analises.schema.json",
                 raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
                 raiz / "04_resultados_analises.schema.json")
    schema = next((p for p in possiveis if p.is_file()), None)
    if schema is None:
        return "estrutura essencial verificada (schema não localizado)"
    try:
        import jsonschema
    except ImportError as ex:
        raise ImportError("jsonschema é necessário para validar o contrato existente") from ex
    jsonschema.validate(d, ler_json(schema))
    return "JSON Schema v1.0.0"


def salvar_json(caminho: Path, doc: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    tmp.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO) -> None:
    refs, dashboards = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f"IND-012 | {ano}: processando {fonte(ano, raiz).name} ...", flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        resumo = ", ".join(f"C{i+1}={c['quantidade_niveis_observados']} níveis"
                            for i, c in enumerate(d["brasil"]["competencias"]))
        print(f"  válidas={d['brasil']['n_validas']:,} | {resumo}", flush=True)
        if d["qualidade"]["validas_soma_competencias_divergente"]:
            print(f"  AVISO FONTE: {d['qualidade']['validas_soma_competencias_divergente']} "
                  "divergência(s) C1–C5 preservadas", flush=True)
    validar_referencias(dados, refs)
    hist = consolidar_historico(dados, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dashboards_novos = {d["ano"]: construir_dashboard(d, dados, hist, dashboards[d["ano"]], gerado)
                        for d in dados}
    schemas = {validar_dashboard(x, raiz) for x in dashboards_novos.values()}
    for d in dados:
        d.pop("_freq_uf")
        d.pop("_freq_br")
    saida = {
        "meta": {
            "indicator_id": INDICADOR, "module_schema_version": "ind012-module-1.0.0",
            "analysis_version": VERSAO, "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado, "data_status": "draft",
            "source_files": {str(x["ano"]): x["arquivo_fonte"] for x in dados},
            "population_definition": DEFINICAO, "geographic_dimension": "SG_UF_PROVA",
            "method": METODO, "comparison_ind001_ind002_ind009_ind010_ind011": "aprovada",
            "historical_note": NOTA_HISTORICA,
            "privacy_note": "Células de 1–29 requerem revisão e possível supressão complementar antes da publicação.",
            "source_discrepancies": {
                str(x["ano"]): {"count": x["brasil"]["n_somas_divergentes"],
                                 "delta_total": x["brasil"]["delta_soma_competencias_menos_nota_redacao"]}
                for x in dados},
        },
        "indicator": {"id": INDICADOR, "name": "Distribuição dos níveis", "unit": "redacoes",
                      "dashboard_json_path": "pages.competencies.level_distribution"},
        "years": dados, "historical": hist,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    linhas = linhas_csv(dados, hist)
    json.dumps(saida, ensure_ascii=False, allow_nan=False)
    pasta = raiz / "outputs"
    salvar_csv(pasta / "indicadores" / "IND_012_distribuicao_niveis_competencias.csv", linhas)
    salvar_json(pasta / "json" / "IND_012_distribuicao_niveis_competencias.json", saida)
    for ano in ANOS:
        salvar_json(pasta / "json" / f"dashboard_enem_{ano}.json", dashboards_novos[ano])
    pequenas_ufs = sum(x["qualidade"]["celulas_uf_positivas_inferiores_30"] for x in dados)
    print("\nIND-012 concluído:")
    print(f"  IND_012_distribuicao_niveis_competencias.csv ({len(linhas):,} linhas)")
    print("  IND_012_distribuicao_niveis_competencias.json")
    print("  dashboard_enem_2019.json ... dashboard_enem_2025.json atualizados")
    print("  Contrato: " + ", ".join(sorted(schemas)))
    print(f"  Alertas: {pequenas_ufs} células UF/ano com 1–29 ocorrências")
    print("  data_status=draft | publicação e validação acadêmica pendentes")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-012 — frequência de níveis observados C1–C5")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--bloco", type=int, default=BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
