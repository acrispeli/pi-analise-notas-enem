# -*- coding: utf-8 -*-
"""IND-002 — Nota média da redação (ENEM 2019–2025).

Usa a mesma população do IND-001:
    TP_STATUS_REDACAO == 1 e 0 <= NU_NOTA_REDACAO <= 1000 (nota numérica).

Por que usar RESULTADOS_2024 e RESULTADOS_2025?
    SG_UF_PROVA, TP_STATUS_REDACAO e NU_NOTA_REDACAO estão nesses CSVs.
    Não precisamos de join para este indicador.

Fonte por edição:
    2019–2023: data/raw/AAAA/MICRODADOS_ENEM_AAAA.csv
    2024–2025: data/raw/AAAA/RESULTADOS_AAAA.csv

Pré-requisito: IND-001 já executado e validado tecnicamente:
    outputs/json/IND_001_redacoes_validas.json
    outputs/json/IND_001_dashboard_AAAA.json

Execute na raiz do projeto:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_002_nota_media.py

Saídas:
    outputs/indicadores/IND_002_nota_media.csv       (auditoria, 224 linhas)
    outputs/json/IND_002_nota_media.json             (módulo histórico)
    outputs/json/dashboard_enem_AAAA.json            (7 dashboards progressivos
                                                     com IND-001 + IND-002)

O script NÃO modifica os JSONs do IND-001. Os arquivos de dashboard
progressivo permanecem em 'draft' até aprovação acadêmica. Não exporta
inscrições nem resultados individuais.
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
UFS = tuple(sorted(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
))
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
TAMANHO_BLOCO = 100_000
INDICADOR = "IND-002"
NOME = "Nota média da redação"
DEFINICAO = (
    "Média aritmética de NU_NOTA_REDACAO entre registros com "
    "TP_STATUS_REDACAO = 1 e nota numérica entre 0 e 1000, inclusive. "
    "Cada edição e UF usa somente suas próprias redações válidas."
)
NOTA_HISTORICA = (
    "A média do período 2019–2025 é ponderada pelo número de redações "
    "válidas de cada edição, e não a média simples das médias anuais. "
    "É uma estatística agregada de participações, não de pessoas únicas. "
    "UF refere-se ao local de aplicação da prova; variações anuais são "
    "descritivas e não demonstram causas."
)


def fonte(ano: int, raiz: Path) -> Path:
    nome = (f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023
            else f"RESULTADOS_{ano}.csv")
    return raiz / "data" / "raw" / str(ano) / nome


def media(soma: float, n: int) -> float | None:
    return round(soma / n, 4) if n else None


def normalizar_soma(valor: float) -> float:
    """Arredondar resíduos da soma em ponto flutuante, sem arredondar notas."""
    return round(float(valor), 6)


def contar_ano(ano: int, raiz: Path, bloco: int) -> dict:
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Não localizei {caminho}")

    totais = Counter()
    total_uf = Counter()
    contagem_uf = Counter()
    soma_uf = Counter()
    soma_br = 0.0

    leitor = pd.read_csv(
        caminho,
        sep=";",
        usecols=list(COLUNAS),
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
        encoding_errors="replace",
        chunksize=bloco,
        on_bad_lines="error",
    )
    for pedaco in leitor:
        uf = pedaco["SG_UF_PROVA"].str.strip().str.upper()
        st = pedaco["TP_STATUS_REDACAO"].str.strip()
        txt = pedaco["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(txt.str.replace(",", ".", regex=False), errors="coerce")
        status1 = st.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        valida = status1 & nota_ok
        uf_ok = uf.isin(UFS)

        totais["linhas"] += int(len(pedaco))
        totais["status1"] += int(status1.sum())
        totais["validas"] += int(valida.sum())
        totais["status1_sem_nota"] += int((status1 & txt.eq("")).sum())
        totais["status1_nota_invalida"] += int(
            (status1 & txt.ne("") & ~nota_ok).sum()
        )
        totais["validas_sem_uf"] += int((valida & uf.eq("")).sum())
        totais["validas_uf_desconhecida"] += int(
            (valida & ~uf_ok & uf.ne("")).sum()
        )
        total_uf.update(uf.value_counts().to_dict())

        if valida.any():
            tab = pd.DataFrame({"uf": uf[valida], "nota": nota[valida]})
            grupo = tab.groupby("uf", sort=False)["nota"].agg(["size", "sum"])
            for codigo, linha in grupo.iterrows():
                contagem_uf[str(codigo)] += int(linha["size"])
                soma_uf[str(codigo)] += float(linha["sum"])
            soma_br += float(nota[valida].sum())

    if not totais["linhas"]:
        raise ValueError(f"{ano}: arquivo sem registros")
    if totais["status1"] != totais["validas"] + totais["status1_sem_nota"] + totais["status1_nota_invalida"]:
        raise AssertionError(f"{ano}: status 1 não reconciliou com as notas")
    if totais["status1_sem_nota"] or totais["status1_nota_invalida"]:
        raise ValueError(
            f"{ano}: status=1 com nota vazia/inválida: "
            f"{totais['status1_sem_nota']} vazias, "
            f"{totais['status1_nota_invalida']} inválidas. Revisar origem."
        )
    if totais["validas_sem_uf"] or totais["validas_uf_desconhecida"]:
        raise ValueError(
            f"{ano}: UF ausente/desconhecida em redações válidas: "
            f"{totais['validas_sem_uf']} / {totais['validas_uf_desconhecida']}"
        )
    if sum(contagem_uf.values()) != totais["validas"]:
        raise AssertionError(f"{ano}: número de redações por UF não fecha")
    if sum(total_uf.values()) != totais["linhas"]:
        raise AssertionError(f"{ano}: número de registros por UF não fecha")
    if not math.isclose(sum(soma_uf.values()), soma_br, rel_tol=0, abs_tol=1e-5):
        raise AssertionError(f"{ano}: soma das notas das UFs diverge da soma brasileira")

    ufs = []
    for codigo in UFS:
        n = int(contagem_uf[codigo])
        if 0 < n < 30:
            raise ValueError(f"{ano}/{codigo}: n={n}, inferior ao limiar de divulgação 30")
        ufs.append({
            "uf": codigo,
            "n_validas": n,
            "soma_notas": normalizar_soma(soma_uf[codigo]),
            "media": media(soma_uf[codigo], n),
            "total_registros": int(total_uf[codigo]),
        })

    if sum(x["n_validas"] for x in ufs) != totais["validas"]:
        raise AssertionError(f"{ano}: UFs ≠ Brasil")
    return {
        "ano": ano,
        "arquivo_fonte": caminho.name,
        "brasil": {
            "n_validas": int(totais["validas"]),
            "soma_notas": normalizar_soma(soma_br),
            "media": media(soma_br, totais["validas"]),
            "total_registros": int(totais["linhas"]),
        },
        "ufs": ufs,
        "qualidade": {
            "status": "ok",
            "status1_sem_nota": int(totais["status1_sem_nota"]),
            "status1_nota_invalida": int(totais["status1_nota_invalida"]),
            "validas_sem_uf": int(totais["validas_sem_uf"]),
            "validas_uf_desconhecida": int(totais["validas_uf_desconhecida"]),
            "soma_notas_uf_igual_brasil": True,
            "soma_contagens_uf_igual_brasil": True,
        },
    }


def carregar_ind001(raiz: Path) -> dict:
    caminho = raiz / "outputs" / "json" / "IND_001_redacoes_validas.json"
    if not caminho.is_file():
        raise FileNotFoundError(
            "IND-001 é pré-requisito: execute IND_001_redacoes_validas.py "
            f"antes do IND-002. Arquivo ausente: {caminho}"
        )
    with caminho.open(encoding="utf-8") as arq:
        ind1 = json.load(arq)
    if ind1.get("indicator", {}).get("id") != "IND-001":
        raise ValueError("Referência do IND-001 não tem o ID esperado")
    if sorted(d["ano"] for d in ind1.get("years", [])) != list(ANOS):
        raise ValueError("Referência do IND-001 não possui todos os sete anos")
    return ind1


def validar_contra_ind001(dados: list[dict], ind1: dict) -> None:
    ref_anos = {d["ano"]: d for d in ind1["years"]}
    for d in dados:
        ano = d["ano"]
        ref = ref_anos[ano]
        for campo_002, campo_001 in (
            ("n_validas", "redacoes_validas"),
            ("total_registros", "total_registros"),
        ):
            if d["brasil"][campo_002] != ref["brasil"][campo_001]:
                raise ValueError(
                    f"{ano}: IND-002 {campo_002}={d['brasil'][campo_002]} "
                    f"≠ IND-001 {campo_001}={ref['brasil'][campo_001]}"
                )
        ref_ufs = {u["uf"]: u for u in ref["ufs"]}
        for uf in d["ufs"]:
            r = ref_ufs[uf["uf"]]
            if uf["n_validas"] != r["redacoes_validas"]:
                raise ValueError(f"{ano}/{uf['uf']}: quantidade difere do IND-001")
            if uf["total_registros"] != r["total_registros"]:
                raise ValueError(f"{ano}/{uf['uf']}: total de linhas difere do IND-001")
        d["qualidade"]["validado_contra_ind001"] = True


def historico(dados: list[dict]) -> dict:
    n = sum(d["brasil"]["n_validas"] for d in dados)
    soma = math.fsum(d["brasil"]["soma_notas"] for d in dados)
    if n == 0:
        raise ValueError("Nenhuma redação válida no conjunto de anos")
    por_uf = []
    for codigo in UFS:
        partes = [next(u for u in d["ufs"] if u["uf"] == codigo) for d in dados]
        n_uf = sum(u["n_validas"] for u in partes)
        soma_uf = math.fsum(u["soma_notas"] for u in partes)
        por_uf.append({
            "uf": codigo,
            "n_validas": n_uf,
            "soma_notas": normalizar_soma(soma_uf),
            "media": media(soma_uf, n_uf),
        })
    if sum(u["n_validas"] for u in por_uf) != n:
        raise AssertionError("Histórico: contagem estadual difere da nacional")
    if not math.isclose(sum(u["soma_notas"] for u in por_uf), soma, rel_tol=0, abs_tol=1e-4):
        raise AssertionError("Histórico: soma estadual difere da nacional")
    return {
        "periodo": "2019-2025",
        "brasil": {"n_validas": n, "soma_notas": normalizar_soma(soma),
                   "media": media(soma, n)},
        "ufs": por_uf,
        "nota": NOTA_HISTORICA,
    }


def linhas_auditoria(dados: list[dict], conjunto: dict) -> list[dict]:
    linhas = []
    grupos = [
        (str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"])
        for d in dados
    ]
    grupos.append(("2019-2025", conjunto["brasil"], conjunto["ufs"], "TODAS_AS_EDICOES"))
    for periodo, br, ufs, arq in grupos:
        entradas = [("BRASIL", "BR", br)] + [("UF", u["uf"], u) for u in ufs]
        for abrangencia, codigo, item in entradas:
            linhas.append({
                "indicador_id": INDICADOR,
                "periodo": periodo,
                "abrangencia": abrangencia,
                "uf": codigo,
                "n_validas": item["n_validas"],
                "soma_notas": item["soma_notas"],
                "nota_media": item["media"],
                "metodo": "media_aritmetica_ponderada_por_n" if periodo == "2019-2025"
                          else "media_aritmetica",
                "arquivo_fonte": arq,
            })
    if len(linhas) != 8 * 28:
        raise AssertionError("CSV deveria conter 224 linhas de resultados")
    return linhas


def carregar_dashboard_ind001(raiz: Path, ano: int) -> dict:
    caminho = raiz / "outputs" / "json" / f"IND_001_dashboard_{ano}.json"
    if not caminho.is_file():
        raise FileNotFoundError(f"Falta o dashboard validado do IND-001: {caminho}")
    with caminho.open(encoding="utf-8") as arq:
        p = json.load(arq)
    if p.get("meta", {}).get("year") != ano:
        raise ValueError(f"{ano}: ano inesperado no dashboard do IND-001")
    return p


def integrar_dashboard(ano: dict, dados: list[dict], conj: dict,
                       base: dict, gerado: str) -> dict:
    """Preserva IND-001 e adiciona IND-002, sem alterar a referência anterior."""
    p = deepcopy(base)
    br = ano["brasil"]
    if p["pages"]["overview"]["kpis"].get("valid_essays") != br["n_validas"]:
        raise ValueError(f"{ano['ano']}: KPI valid_essays não bate com IND-002")
    p["meta"]["analysis_version"] = "2.1.0-ind001-ind002"
    p["meta"]["generated_at"] = gerado
    p["meta"]["data_status"] = "draft"
    p["meta"].setdefault("warnings", []).append(
        "IND-002 validado tecnicamente; publicação acadêmica ainda pendente."
    )
    overview = p["pages"]["overview"]
    overview["kpis"]["mean_score"] = br["media"]
    overview["ind002"] = {
        "indicator_id": INDICADOR,
        "unit": "pontos",
        "n": br["n_validas"],
        "mean_score": br["media"],
        "by_uf": [
            {"uf": u["uf"], "n": u["n_validas"], "mean_score": u["media"]}
            for u in ano["ufs"]
        ],
    }
    p["pages"]["temporal"]["ind002"] = {
        "indicator_id": INDICADOR,
        "national_by_year": [
            {"year": d["ano"], "n": d["brasil"]["n_validas"],
             "mean_score": d["brasil"]["media"]}
            for d in dados
        ],
        "period_total": {"n": conj["brasil"]["n_validas"],
                         "mean_score": conj["brasil"]["media"]},
        "period_by_uf": [
            {"uf": u["uf"], "n": u["n_validas"], "mean_score": u["media"]}
            for u in conj["ufs"]
        ],
        "note": NOTA_HISTORICA,
    }
    p["pages"]["methodology"]["ind002"] = {
        "definition": DEFINICAO,
        "calculation": "SUM(NU_NOTA_REDACAO) / COUNT(NU_NOTA_REDACAO)",
        "population": "POP_VALID, mesma população do IND-001",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": ano["arquivo_fonte"],
        "precision": "4 casas decimais no JSON; frontend pode exibir 1 casa",
        "historical_note": NOTA_HISTORICA,
    }
    p["quality"]["ind002_validation"] = ano["qualidade"]
    return p


def validar_json(payload: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(payload):
        raise ValueError("Dashboard sem estrutura mínima do contrato")
    for pagina in ("overview", "competencies", "evaluators", "high_performance",
                   "socioeconomic", "ml", "methodology"):
        if pagina not in payload["pages"]:
            raise ValueError(f"Dashboard sem página obrigatória: {pagina}")
    texto = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if "NU_INSCRICAO" in texto or "NU_SEQUENCIAL" in texto:
        raise ValueError("Identificador individual detectado no payload")
    caminhos_schema = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    caminho_schema = next((p for p in caminhos_schema if p.is_file()), None)
    if caminho_schema is None:
        return "validação estrutural básica (schema não encontrado)"
    try:
        import jsonschema
    except ImportError:
        return "validação estrutural básica (instalar jsonschema)"
    with caminho_schema.open(encoding="utf-8") as arquivo:
        jsonschema.validate(payload, json.load(arquivo))
    return "validado pelo JSON Schema v1.0.0"


def gravar_json(caminho: Path, dado: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dado, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
        arquivo.write("\n")
    temporario.replace(caminho)


def gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, delimiter=";", fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, bloco: int = TAMANHO_BLOCO) -> None:
    referencia = carregar_ind001(raiz)
    anos = []
    for ano in ANOS:
        print(f"IND-002 | {ano}: processando {fonte(ano, raiz).name}...", flush=True)
        d = contar_ano(ano, raiz, bloco)
        anos.append(d)
        print(f"  Brasil: n={d['brasil']['n_validas']:,} | "
              f"média={d['brasil']['media']:.4f} | 27 UFs", flush=True)

    validar_contra_ind001(anos, referencia)
    conj = historico(anos)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")

    dashboards = []
    for ano in anos:
        base = carregar_dashboard_ind001(raiz, ano["ano"])
        novo = integrar_dashboard(ano, anos, conj, base, gerado)
        dashboards.append(novo)
    estados = {validar_json(p, raiz) for p in dashboards}

    modulo = {
        "meta": {
            "indicator_id": INDICADOR,
            "module_schema_version": "ind002-module-1.0.0",
            "analysis_version": "2.1.0-ind001-ind002",
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado,
            "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in anos},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001": "aprovada (N nacional e estadual, por ano)",
            "precision": "4 casas decimais",
        },
        "indicator": {
            "id": INDICADOR,
            "name": NOME,
            "unit": "pontos",
            "dashboard_json_path": "pages.overview.kpis.mean_score",
        },
        "years": anos,
        "historical": conj,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)

    saidas_csv = raiz / "outputs" / "indicadores" / "IND_002_nota_media.csv"
    saidas_json = raiz / "outputs" / "json" / "IND_002_nota_media.json"
    gravar_csv(saidas_csv, linhas_auditoria(anos, conj))
    gravar_json(saidas_json, modulo)
    for d, painel in zip(anos, dashboards):
        gravar_json(raiz / "outputs" / "json" /
                   f"dashboard_enem_{d['ano']}.json", painel)

    print("\nConcluído! Arquivos de saída:")
    print(f"  {saidas_csv}")
    print(f"  {saidas_json}")
    print("  outputs/json/dashboard_enem_AAAA.json (7 anos)")
    print(f"  Validação: {', '.join(sorted(estados))}")
    print(f"  Média histórica ponderada: {conj['brasil']['media']:.4f} "
          f"(n={conj['brasil']['n_validas']:,})")
    print("  STATUS: draft (aguardando conferência acadêmica)")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-002 — ENEM 2019–2025")
    parser.add_argument(
        "--raiz", type=Path, default=Path(__file__).resolve().parents[2],
        help="Pasta raiz do repositório",
    )
    parser.add_argument(
        "--bloco", type=int, default=TAMANHO_BLOCO,
        help="Quantidade de linhas lidas por bloco (padrão: 100000)",
    )
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser maior do que zero")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
