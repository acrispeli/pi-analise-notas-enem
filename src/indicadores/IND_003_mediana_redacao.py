# -*- coding: utf-8 -*-
"""IND-003 — Mediana da nota da redação, ENEM 2019–2025.

População: a mesma de IND-001/IND-002, isto é, TP_STATUS_REDACAO = 1
com NU_NOTA_REDACAO numérica entre 0 e 1000, inclusive.
Dimensão geográfica: SG_UF_PROVA (local de aplicação, não residência).

A mediana é EXATA: a frequência de cada nota distinta é contabilizada por
UF e a(s) posição(ões) central(is) da distribuição ordenada são recuperadas
sem amostragem e sem guardar milhões de notas na memória.

A mediana histórica é calculada reunindo as frequências de 2019–2025;
não é a mediana (nem a média) das medianas anuais.

Fontes:
  2019–2023: data/raw/AAAA/MICRODADOS_ENEM_AAAA.csv
  2024–2025: data/raw/AAAA/RESULTADOS_AAAA.csv

Pré-requisitos existentes no projeto:
  outputs/json/IND_001_redacoes_validas.json
  outputs/json/IND_002_nota_media.json
  outputs/json/dashboard_enem_AAAA.json (7 dashboards cumulativos de 001+002)

Execução no PowerShell (a partir da raiz do repositório):
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_003_mediana_redacao.py

Saídas (geradas apenas após validação):
  outputs/indicadores/IND_003_mediana_redacao.csv
  outputs/json/IND_003_mediana_redacao.json
  outputs/json/dashboard_enem_AAAA.json (atualizados: IND-001+IND-002+IND-003)

Não altera os artefatos do IND-001 e IND-002, nem exporta microdados ou IDs.
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
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
))
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
BLOCO_PADRAO = 100_000
INDICADOR = "IND-003"
DEFINICAO = (
    "Mediana exata de NU_NOTA_REDACAO para redações com TP_STATUS_REDACAO = 1 "
    "e nota numérica entre 0 e 1000, inclusive, segundo UF de aplicação."
)
NOTA_HISTORICA = (
    "Mediana calculada a partir da distribuição conjunta das notas de todas "
    "as edições de 2019 a 2025. Não é a média ou mediana das medianas anuais. "
    "Refere-se a participações, não a indivíduos únicos; UF é local de prova."
)


def origem(ano: int, raiz: Path) -> Path:
    nome = f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023 else f"RESULTADOS_{ano}.csv"
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito ausente: {caminho}")
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def mediana_frequencias(frequencias: Counter[float]) -> float | None:
    """Calcula as posições centrais na distribuição ordenada (0–1000)."""
    n = sum(frequencias.values())
    if n == 0:
        return None
    k1 = (n - 1) // 2  # posições zero-based da(s) observação(ões) central(is)
    k2 = n // 2
    acumulado = 0
    esquerda = direita = None
    for nota in sorted(frequencias):
        quantidade = frequencias[nota]
        if quantidade <= 0 or not math.isfinite(nota) or not 0 <= nota <= 1000:
            raise ValueError(f"Distribuição de notas inválida: {nota} → {quantidade}")
        proximo = acumulado + quantidade
        if esquerda is None and acumulado <= k1 < proximo:
            esquerda = nota
        if acumulado <= k2 < proximo:
            direita = nota
            break
        acumulado = proximo
    if esquerda is None or direita is None:
        raise AssertionError("Não foi possível localizar as observações centrais")
    return round((esquerda + direita) / 2, 6)


def checar_soma(soma_atual: float, soma_esperada: float, contexto: str) -> None:
    # Resultados do IND-002 são publicados com 6 casas decimais para a soma.
    if not math.isclose(soma_atual, soma_esperada, rel_tol=0, abs_tol=0.01):
        raise ValueError(
            f"{contexto}: soma de notas difere do IND-002 "
            f"({soma_atual:.6f} vs {soma_esperada:.6f})"
        )


def consultar_referencias(raiz: Path) -> tuple[dict, dict, dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    ind1 = ler_json(pasta / "IND_001_redacoes_validas.json")
    ind2 = ler_json(pasta / "IND_002_nota_media.json")
    if ind1.get("indicator", {}).get("id") != "IND-001":
        raise ValueError("O JSON IND-001 não tem identificação válida")
    if ind2.get("indicator", {}).get("id") != "IND-002":
        raise ValueError("O JSON IND-002 não tem identificação válida")
    for ref, nome in ((ind1, "IND-001"), (ind2, "IND-002")):
        if sorted(item["ano"] for item in ref["years"]) != list(ANOS):
            raise ValueError(f"{nome}: faltam anos da série 2019–2025")
    bases = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}.json: ano incompatível")
        if "ind002" not in painel.get("pages", {}).get("overview", {}):
            raise ValueError(f"dashboard_enem_{ano}.json não contém IND-002")
        bases[ano] = painel
    return ind1, ind2, bases


def consolidar_frequencias(frequencias_uf: dict[str, Counter[float]]) -> Counter[float]:
    brasil = Counter()
    for uf in UFS:
        brasil.update(frequencias_uf[uf])
    return brasil


def processar_ano(ano: int, raiz: Path, bloco: int) -> tuple[dict, dict[str, Counter[float]]]:
    caminho = origem(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo do Inep ausente: {caminho}")
    auditoria = Counter()
    totais_uf = Counter()
    freq_uf: dict[str, Counter[float]] = {uf: Counter() for uf in UFS}

    partes = pd.read_csv(
        caminho, sep=";", usecols=list(COLUNAS), dtype=str, keep_default_na=False,
        na_filter=False, encoding="utf-8-sig", encoding_errors="replace",
        chunksize=bloco, on_bad_lines="error",
    )
    for parte in partes:
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        txt = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(txt.str.replace(",", ".", regex=False), errors="coerce")
        status1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        valida = status1 & nota_ok
        uf_ok = uf.isin(UFS)

        auditoria["linhas"] += len(parte)
        auditoria["status1"] += int(status1.sum())
        auditoria["validas"] += int(valida.sum())
        auditoria["status1_sem_nota"] += int((status1 & txt.eq("")).sum())
        auditoria["status1_nota_invalida"] += int((status1 & txt.ne("") & ~nota_ok).sum())
        auditoria["validas_sem_uf"] += int((valida & uf.eq("")).sum())
        auditoria["validas_uf_desconhecida"] += int((valida & ~uf_ok & uf.ne("")).sum())
        totais_uf.update(uf.value_counts().to_dict())

        if valida.any():
            frequencias_bloco = (
                pd.DataFrame({"uf": uf[valida], "nota": nota[valida]})
                .groupby(["uf", "nota"], sort=False, observed=True)
                .size()
            )
            for (sigla, pontuacao), quantidade in frequencias_bloco.items():
                if sigla not in freq_uf:
                    # Melhor falhar com mensagem clara após contabilização da UF.
                    continue
                freq_uf[sigla][float(pontuacao)] += int(quantidade)

    if not auditoria["linhas"]:
        raise ValueError(f"{ano}: nenhum registro encontrado")
    if auditoria["status1"] != (
        auditoria["validas"] + auditoria["status1_sem_nota"] + auditoria["status1_nota_invalida"]
    ):
        raise ValueError(f"{ano}: status 1 não reconcilia com a população válida")
    if auditoria["status1_sem_nota"] or auditoria["status1_nota_invalida"]:
        raise ValueError(
            f"{ano}: status 1 com nota ausente/inválida: "
            f"{auditoria['status1_sem_nota']} / {auditoria['status1_nota_invalida']}"
        )
    if auditoria["validas_sem_uf"] or auditoria["validas_uf_desconhecida"]:
        raise ValueError(
            f"{ano}: UF ausente ou desconhecida entre redações válidas: "
            f"{auditoria['validas_sem_uf']} / {auditoria['validas_uf_desconhecida']}"
        )
    if sum(totais_uf.values()) != auditoria["linhas"]:
        raise AssertionError(f"{ano}: total de UFs não confere com registros")

    freq_brasil = consolidar_frequencias(freq_uf)
    if sum(freq_brasil.values()) != auditoria["validas"]:
        raise AssertionError(f"{ano}: soma das redações válidas por UF ≠ Brasil")

    ufs = []
    for sigla in UFS:
        contagem = sum(freq_uf[sigla].values())
        if 0 < contagem < 30:
            raise ValueError(f"{ano}/{sigla}: grupo de {contagem} registros, inferior ao limiar 30")
        ufs.append({
            "uf": sigla,
            "n_validas": contagem,
            "mediana": mediana_frequencias(freq_uf[sigla]),
            "total_registros": int(totais_uf[sigla]),
        })
    return {
        "ano": ano,
        "arquivo_fonte": caminho.name,
        "brasil": {
            "n_validas": auditoria["validas"],
            "mediana": mediana_frequencias(freq_brasil),
            "total_registros": auditoria["linhas"],
        },
        "ufs": ufs,
        "qualidade": {
            "status": "ok",
            "status1_sem_nota": auditoria["status1_sem_nota"],
            "status1_nota_invalida": auditoria["status1_nota_invalida"],
            "validas_sem_uf": auditoria["validas_sem_uf"],
            "validas_uf_desconhecida": auditoria["validas_uf_desconhecida"],
            "soma_contagens_uf_igual_brasil": True,
        },
    }, freq_uf


def validar_com_anteriores(
    dados: list[dict], frequencias: dict[int, dict[str, Counter[float]]],
    ind1: dict, ind2: dict,
) -> None:
    por_ano1 = {d["ano"]: d for d in ind1["years"]}
    por_ano2 = {d["ano"]: d for d in ind2["years"]}
    for d in dados:
        ano = d["ano"]
        r1, r2 = por_ano1[ano], por_ano2[ano]
        br = d["brasil"]
        if not (
            br["n_validas"] == r1["brasil"]["redacoes_validas"] == r2["brasil"]["n_validas"]
            and br["total_registros"] == r1["brasil"]["total_registros"] == r2["brasil"]["total_registros"]
        ):
            raise ValueError(f"{ano}: contagens do IND-003 diferem dos IND-001/002")
        soma_br = math.fsum(
            float(ponto) * quantidade
            for freq in frequencias[ano].values() for ponto, quantidade in freq.items()
        )
        checar_soma(soma_br, float(r2["brasil"]["soma_notas"]), f"{ano}/BR")
        u1 = {item["uf"]: item for item in r1["ufs"]}
        u2 = {item["uf"]: item for item in r2["ufs"]}
        if set(u1) != set(UFS) or set(u2) != set(UFS):
            raise ValueError(f"{ano}: conjunto de 27 UFs incompleto nas referências")
        for u in d["ufs"]:
            sigla = u["uf"]
            if not (
                u["n_validas"] == u1[sigla]["redacoes_validas"] == u2[sigla]["n_validas"]
                and u["total_registros"] == u1[sigla]["total_registros"] == u2[sigla]["total_registros"]
            ):
                raise ValueError(f"{ano}/{sigla}: N diverge dos indicadores anteriores")
            soma_uf = math.fsum(
                pontuacao * quantidade for pontuacao, quantidade in frequencias[ano][sigla].items()
            )
            checar_soma(soma_uf, float(u2[sigla]["soma_notas"]), f"{ano}/{sigla}")
        d["qualidade"]["validado_contra_ind001_ind002"] = True


def consolidado_historico(
    dados: list[dict], frequencias: dict[int, dict[str, Counter[float]]],
    ind1: dict, ind2: dict,
) -> dict:
    reunidas = {sigla: Counter() for sigla in UFS}
    for ano in ANOS:
        for sigla in UFS:
            reunidas[sigla].update(frequencias[ano][sigla])
    total_brasil = consolidar_frequencias(reunidas)
    n = sum(total_brasil.values())
    if not (
        n == ind1["historical"]["brasil"]["redacoes_validas"]
        == ind2["historical"]["brasil"]["n_validas"]
        == sum(d["brasil"]["n_validas"] for d in dados)
    ):
        raise ValueError("Histórico: total de redações difere dos IND-001/002")
    checar_soma(
        math.fsum(nota * qtd for nota, qtd in total_brasil.items()),
        float(ind2["historical"]["brasil"]["soma_notas"]),
        "2019–2025/BR",
    )
    ref1 = {u["uf"]: u for u in ind1["historical"]["ufs"]}
    ref2 = {u["uf"]: u for u in ind2["historical"]["ufs"]}
    ufs = []
    for uf in UFS:
        c = reunidas[uf]
        n_uf = sum(c.values())
        if n_uf != ref1[uf]["redacoes_validas"] or n_uf != ref2[uf]["n_validas"]:
            raise ValueError(f"Histórico/{uf}: N difere dos IND-001/002")
        checar_soma(
            math.fsum(nota * qtd for nota, qtd in c.items()),
            float(ref2[uf]["soma_notas"]),
            f"2019–2025/{uf}",
        )
        ufs.append({"uf": uf, "n_validas": n_uf, "mediana": mediana_frequencias(c)})
    if sum(u["n_validas"] for u in ufs) != n:
        raise AssertionError("Histórico: soma de UFs diferente do Brasil")
    return {
        "periodo": "2019-2025",
        "brasil": {"n_validas": n, "mediana": mediana_frequencias(total_brasil)},
        "ufs": ufs,
        "nota": NOTA_HISTORICA,
    }


def linhas_csv(dados: list[dict], hist: dict) -> list[dict]:
    grupos = [
        (str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"])
        for d in dados
    ]
    grupos.append(("2019-2025", hist["brasil"], hist["ufs"], "TODAS_AS_EDICOES"))
    linhas = []
    for periodo, br, ufs, arquivo in grupos:
        for abrangencia, uf, reg in [
            ("BRASIL", "BR", br), *[("UF", u["uf"], u) for u in ufs]
        ]:
            linhas.append({
                "indicador_id": INDICADOR,
                "periodo": periodo,
                "abrangencia": abrangencia,
                "uf": uf,
                "n_validas": reg["n_validas"],
                "nota_mediana": reg["mediana"],
                "metodo": "frequencias_exatas_distribuicao_conjunta" if periodo == "2019-2025"
                          else "frequencias_exatas_ano_uf",
                "arquivo_fonte": arquivo,
            })
    if len(linhas) != 224:
        raise AssertionError(f"CSV do IND-003 deveria conter 224 linhas, gerou {len(linhas)}")
    return linhas


def construir_dashboard(
    d: dict, dados: list[dict], hist: dict, anterior: dict, gerado: str,
    referencia_ind1: dict, referencia_ind2: dict,
) -> dict:
    novo = deepcopy(anterior)
    ano = d["ano"]
    overview = novo["pages"]["overview"]
    kpis = overview["kpis"]
    if kpis.get("valid_essays") != d["brasil"]["n_validas"]:
        raise ValueError(f"{ano}: N no dashboard existente não confere")
    if kpis.get("mean_score") != referencia_ind2["brasil"]["media"]:
        raise ValueError(f"{ano}: média do dashboard difere do IND-002")
    if overview["ind002"].get("mean_score") != referencia_ind2["brasil"]["media"]:
        raise ValueError(f"{ano}: média detalhada do dashboard difere do IND-002")
    anterior_uf1 = {x["uf"]: x for x in overview["ind001"]["by_uf"]}
    anterior_uf2 = {x["uf"]: x for x in overview["ind002"]["by_uf"]}
    originais_uf1 = {x["uf"]: x for x in referencia_ind1["ufs"]}
    originais_uf2 = {x["uf"]: x for x in referencia_ind2["ufs"]}
    if (set(anterior_uf1) != set(UFS) or set(anterior_uf2) != set(UFS)):
        raise ValueError(f"{ano}: dashboard existente não tem as 27 UFs")
    for u in d["ufs"]:
        uf = u["uf"]
        if (anterior_uf1[uf]["redacoes_validas"] != u["n_validas"]
            or anterior_uf1[uf]["redacoes_validas"] != originais_uf1[uf]["redacoes_validas"]):
            raise ValueError(f"{ano}/{uf}: IND-001 no dashboard não confere")
        if (anterior_uf2[uf]["n"] != u["n_validas"]
            or anterior_uf2[uf]["mean_score"] != originais_uf2[uf]["media"]):
            raise ValueError(f"{ano}/{uf}: IND-002 no dashboard não confere")
    novo["meta"]["analysis_version"] = "2.2.0-ind001-ind002-ind003"
    novo["meta"]["generated_at"] = gerado
    novo["meta"]["data_status"] = "draft"
    avisos = novo["meta"].setdefault("warnings", [])
    aviso3 = "IND-003 ainda depende de validação acadêmica para publicação."
    if aviso3 not in avisos:
        avisos.append(aviso3)

    kpis["median_score"] = d["brasil"]["mediana"]
    overview["ind003"] = {
        "indicator_id": INDICADOR,
        "unit": "pontos",
        "n": d["brasil"]["n_validas"],
        "median_score": d["brasil"]["mediana"],
        "by_uf": [
            {"uf": u["uf"], "n": u["n_validas"], "median_score": u["mediana"]}
            for u in d["ufs"]
        ],
    }
    novo["pages"]["temporal"]["ind003"] = {
        "indicator_id": INDICADOR,
        "national_by_year": [
            {"year": item["ano"], "n": item["brasil"]["n_validas"],
             "median_score": item["brasil"]["mediana"]}
            for item in dados
        ],
        "period_total": {
            "n": hist["brasil"]["n_validas"],
            "median_score": hist["brasil"]["mediana"],
        },
        "period_by_uf": [
            {"uf": item["uf"], "n": item["n_validas"], "median_score": item["mediana"]}
            for item in hist["ufs"]
        ],
        "note": NOTA_HISTORICA,
    }
    novo["pages"]["methodology"]["ind003"] = {
        "definition": DEFINICAO,
        "calculation": "mediana exata por contagem das frequências de cada nota",
        "population": "POP_VALID, a mesma dos IND-001 e IND-002",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "historical_note": NOTA_HISTORICA,
    }
    novo["quality"]["ind003_validation"] = d["qualidade"]
    return novo


def validar_painel(painel: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(painel):
        raise ValueError("Dashboard não contém todas as seções estruturais")
    paginas = {
        "overview", "competencies", "evaluators", "high_performance",
        "socioeconomic", "ml", "methodology",
    }
    if not paginas.issubset(painel["pages"]):
        raise ValueError("Dashboard não contém todas as páginas obrigatórias")
    serializado = json.dumps(painel, ensure_ascii=False, allow_nan=False)
    if "NU_INSCRICAO" in serializado or "NU_SEQUENCIAL" in serializado:
        raise ValueError("Identificador individual encontrado no dashboard")

    caminhos = [
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    ]
    schema = next((path for path in caminhos if path.is_file()), None)
    if schema is None:
        return "validação estrutural básica (schema não localizado)"
    try:
        import jsonschema
    except ImportError:
        return "validação estrutural básica (instale jsonschema para validação formal)"
    with schema.open(encoding="utf-8") as arquivo:
        jsonschema.validate(painel, json.load(arquivo))
    return "validado pelo JSON Schema v1.0.0"


def escrever_json(caminho: Path, dado: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dado, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
        arquivo.write("\n")
    temporario.replace(caminho)


def escrever_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(linhas[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    ind1, ind2, dashboards_antigos = consultar_referencias(raiz)
    dados = []
    frequencias = {}
    for ano in ANOS:
        print(f"IND-003 | {ano}: processando {origem(ano, raiz).name}...", flush=True)
        relatorio, histograma = processar_ano(ano, raiz, bloco)
        dados.append(relatorio)
        frequencias[ano] = histograma
        print(
            f"  Brasil: n={relatorio['brasil']['n_validas']:,} | "
            f"mediana={relatorio['brasil']['mediana']} | 27 UFs", flush=True
        )

    validar_com_anteriores(dados, frequencias, ind1, ind2)
    historico = consolidado_historico(dados, frequencias, ind1, ind2)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    referencia_por_ano1 = {item["ano"]: item for item in ind1["years"]}
    referencia_por_ano2 = {item["ano"]: item for item in ind2["years"]}
    paines = {
        d["ano"]: construir_dashboard(
            d, dados, historico, dashboards_antigos[d["ano"]], gerado,
            referencia_por_ano1[d["ano"]], referencia_por_ano2[d["ano"]],
        )
        for d in dados
    }
    validacoes = {validar_painel(p, raiz) for p in paines.values()}

    modulo = {
        "meta": {
            "indicator_id": INDICADOR,
            "module_schema_version": "ind003-module-1.0.0",
            "analysis_version": "2.2.0-ind001-ind002-ind003",
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado,
            "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001_ind002": "aprovada (N, total de registros e soma das notas)",
            "calculation": "mediana exata por frequências; sem amostragem",
        },
        "indicator": {
            "id": INDICADOR,
            "name": "Mediana da nota da redação",
            "unit": "pontos",
            "dashboard_json_path": "pages.overview.kpis.median_score",
        },
        "years": dados,
        "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)

    # Só publicar após validar os sete anos, as referências e os sete painéis.
    destino_csv = raiz / "outputs" / "indicadores" / "IND_003_mediana_redacao.csv"
    destino_json = raiz / "outputs" / "json" / "IND_003_mediana_redacao.json"
    escrever_csv(destino_csv, linhas)
    escrever_json(destino_json, modulo)
    for ano in ANOS:
        escrever_json(raiz / "outputs" / "json" / f"dashboard_enem_{ano}.json", paines[ano])

    print("\nConcluído! Arquivos de saída:")
    print(f"  {destino_csv}")
    print(f"  {destino_json}")
    print("  outputs/json/dashboard_enem_AAAA.json (7 arquivos atualizados)")
    print(f"  Validação: {', '.join(sorted(validacoes))}")
    print(f"  Mediana histórica conjunta: {historico['brasil']['mediana']} "
          f"(n={historico['brasil']['n_validas']:,})")
    print("  STATUS: draft (pendente validação dos resultados reais)")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-003 — ENEM 2019–2025")
    parser.add_argument(
        "--raiz", type=Path, default=Path(__file__).resolve().parents[2],
        help="Raiz do projeto (padrão: duas pastas acima deste arquivo).",
    )
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
