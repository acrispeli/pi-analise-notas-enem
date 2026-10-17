# -*- coding: utf-8 -*-
"""IND-004 — Desvio-padrão populacional da nota da redação, ENEM 2019–2025.

População POP_VALID: TP_STATUS_REDACAO = 1 e NU_NOTA_REDACAO numérica
entre 0 e 1000, inclusive. UF = SG_UF_PROVA, local da prova.

Método: desvio-padrão POPULACIONAL (ddof=0) de todas as redações válidas,
sem amostragem. Processamento incremental em blocos: combina tamanho,
média e M2 (soma dos desvios quadráticos) pelo algoritmo de variância
combinada, numericamente mais estável do que E[X²] - E[X]².

O consolidado 2019–2025 reúne as distribuições completas: NÃO é a média
simples ou ponderada dos desvios-padrão anuais.

Pré-requisitos (na raiz do projeto):
    outputs/json/IND_001_redacoes_validas.json
    outputs/json/IND_002_nota_media.json
    outputs/json/IND_003_mediana_redacao.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

Fontes:
    2019–2023: data/raw/ANO/MICRODADOS_ENEM_ANO.csv
    2024–2025: data/raw/ANO/RESULTADOS_ANO.csv

Executar no PowerShell, na raiz do repositório:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_004_desvio_padrao_redacao.py

Saídas (escritas apenas após os sete anos passarem nas verificações):
    outputs/indicadores/IND_004_desvio_padrao_redacao.csv (224 linhas)
    outputs/json/IND_004_desvio_padrao_redacao.json
    outputs/json/dashboard_enem_ANO.json (acrescenta IND-004 a IND-001–003)

Não modifica os módulos IND-001, IND-002, IND-003 e não exporta indivíduos.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
))
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
BLOCO_PADRAO = 100_000
INDICADOR = "IND-004"
VERSAO = "2.3.0-ind001-ind002-ind003-ind004"
DEFINICAO = (
    "Desvio-padrão populacional (ddof=0) das notas NU_NOTA_REDACAO de "
    "redações com TP_STATUS_REDACAO = 1 e nota numérica de 0 a 1000, "
    "inclusive, agrupadas por ano e UF da prova (SG_UF_PROVA)."
)
NOTA_HISTORICA = (
    "Desvio-padrão populacional calculado reunindo as observações de "
    "2019–2025; não é a média dos desvios-padrão de cada ano, pois incorpora "
    "variações dentro dos grupos e entre suas médias. São participações em "
    "edições do Enem, não pessoas únicas; UF identifica o local da prova."
)


@dataclass
class Momentos:
    """Momentos centrais combináveis, sem armazenar observações individuais."""
    n: int = 0
    media: float = 0.0
    m2: float = 0.0
    soma: float = 0.0

    def combinar(self, outro: "Momentos") -> None:
        if outro.n <= 0:
            return
        if self.n == 0:
            self.n = outro.n
            self.media = outro.media
            self.m2 = outro.m2
            self.soma = outro.soma
            return
        total = self.n + outro.n
        delta = outro.media - self.media
        self.m2 = (
            self.m2 + outro.m2 + delta * delta * (self.n * outro.n / total)
        )
        self.media += delta * outro.n / total
        self.soma = math.fsum((self.soma, outro.soma))
        self.n = total

    def desvio_padrao(self) -> float | None:
        if self.n == 0:
            return None
        if self.m2 < -1e-6:
            raise ValueError(f"M2 negativo: {self.m2}")
        return round(math.sqrt(max(0.0, self.m2) / self.n), 4)

    def resultado(self) -> dict:
        return {
            "n_validas": self.n,
            "soma_notas": round(self.soma, 6),
            "media": round(self.soma / self.n, 4) if self.n else None,
            "desvio_padrao": self.desvio_padrao(),
        }


def origem(ano: int, raiz: Path) -> Path:
    nome = (f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023
            else f"RESULTADOS_{ano}.csv")
    return raiz / "data" / "raw" / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f"Pré-requisito não encontrado: {caminho}")
    with caminho.open(encoding="utf-8") as arq:
        return json.load(arq)


def carregar_referencias(raiz: Path) -> tuple[dict, dict, dict, dict[int, dict]]:
    pasta = raiz / "outputs" / "json"
    ref1 = ler_json(pasta / "IND_001_redacoes_validas.json")
    ref2 = ler_json(pasta / "IND_002_nota_media.json")
    ref3 = ler_json(pasta / "IND_003_mediana_redacao.json")
    for doc, ident in ((ref1, "IND-001"), (ref2, "IND-002"), (ref3, "IND-003")):
        if doc.get("indicator", {}).get("id") != ident:
            raise ValueError(f"Referência {ident} está com identificação incorreta")
        if sorted(d["ano"] for d in doc.get("years", [])) != list(ANOS):
            raise ValueError(f"Referência {ident} não cobre 2019–2025")
    paines = {}
    for ano in ANOS:
        painel = ler_json(pasta / f"dashboard_enem_{ano}.json")
        if painel.get("meta", {}).get("year") != ano:
            raise ValueError(f"dashboard_enem_{ano}.json: ano incompatível")
        visao = painel.get("pages", {}).get("overview", {})
        if any(nome not in visao for nome in ("ind001", "ind002", "ind003")):
            raise ValueError(f"dashboard_enem_{ano}.json: IND-001–003 incompletos")
        paines[ano] = painel
    return ref1, ref2, ref3, paines


def processar_ano(ano: int, raiz: Path, bloco: int) -> tuple[dict, dict[str, Momentos]]:
    arquivo = origem(ano, raiz)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Arquivo de microdados não encontrado: {arquivo}")
    total_uf = Counter()
    qualidade = Counter()
    momentos_uf = {uf: Momentos() for uf in UFS}
    leitor = pd.read_csv(
        arquivo, sep=";", usecols=list(COLUNAS), dtype=str,
        keep_default_na=False, na_filter=False, encoding="utf-8-sig",
        encoding_errors="replace", chunksize=bloco, on_bad_lines="error",
    )
    for parte in leitor:
        uf = parte["SG_UF_PROVA"].str.strip().str.upper()
        status = parte["TP_STATUS_REDACAO"].str.strip()
        bruto = parte["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(bruto.str.replace(",", ".", regex=False), errors="coerce")
        st1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        valida = st1 & nota_ok
        uf_ok = uf.isin(UFS)

        qualidade["registros"] += len(parte)
        qualidade["status1"] += int(st1.sum())
        qualidade["validas"] += int(valida.sum())
        qualidade["status1_sem_nota"] += int((st1 & bruto.eq("")).sum())
        qualidade["status1_nota_invalida"] += int((st1 & bruto.ne("") & ~nota_ok).sum())
        qualidade["validas_sem_uf"] += int((valida & uf.eq("")).sum())
        qualidade["validas_uf_desconhecida"] += int((valida & ~uf_ok & uf.ne("")).sum())
        total_uf.update(uf.value_counts().to_dict())

        if valida.any():
            # groupby.var usa ddof=1 só dentro do bloco; multiplicar por n-1
            # recupera M2, posteriormente agregado. A saída final é ddof=0.
            grupos = (pd.DataFrame({"uf": uf[valida], "nota": nota[valida]})
                      .groupby("uf", sort=False)["nota"]
                      .agg(["size", "mean", "var", "sum"]))
            for sigla, reg in grupos.iterrows():
                if sigla not in momentos_uf:
                    continue  # o diagnóstico de UF inválida interromperá o script
                n = int(reg["size"])
                m2 = (n - 1) * float(reg["var"]) if n > 1 else 0.0
                momentos_uf[sigla].combinar(Momentos(
                    n=n, media=float(reg["mean"]), m2=m2, soma=float(reg["sum"])
                ))

    if qualidade["registros"] == 0:
        raise ValueError(f"{ano}: fonte sem registros")
    if qualidade["status1"] != (qualidade["validas"] + qualidade["status1_sem_nota"]
                                 + qualidade["status1_nota_invalida"]):
        raise ValueError(f"{ano}: contagem de status 1 não fecha")
    if qualidade["status1_sem_nota"] or qualidade["status1_nota_invalida"]:
        raise ValueError(
            f"{ano}: redações status=1 com nota ausente/inválida: "
            f"{qualidade['status1_sem_nota']} / {qualidade['status1_nota_invalida']}"
        )
    if qualidade["validas_sem_uf"] or qualidade["validas_uf_desconhecida"]:
        raise ValueError(
            f"{ano}: UF ausente/desconhecida entre válidas: "
            f"{qualidade['validas_sem_uf']} / {qualidade['validas_uf_desconhecida']}"
        )
    if sum(total_uf.values()) != qualidade["registros"]:
        raise AssertionError(f"{ano}: contagens totais de UF divergentes")

    brasil = Momentos()
    ufs = []
    for uf in UFS:
        grupo = momentos_uf[uf]
        if 0 < grupo.n < 30:
            raise ValueError(f"{ano}/{uf}: N={grupo.n} menor que o limiar 30")
        brasil.combinar(grupo)
        ufs.append({"uf": uf, **grupo.resultado(), "total_registros": int(total_uf[uf])})
    if brasil.n != qualidade["validas"]:
        raise AssertionError(f"{ano}: soma das 27 UFs diferente do Brasil")
    return {
        "ano": ano,
        "arquivo_fonte": arquivo.name,
        "brasil": {**brasil.resultado(), "total_registros": qualidade["registros"]},
        "ufs": ufs,
        "qualidade": {
            "status": "ok",
            "status1_sem_nota": qualidade["status1_sem_nota"],
            "status1_nota_invalida": qualidade["status1_nota_invalida"],
            "validas_sem_uf": qualidade["validas_sem_uf"],
            "validas_uf_desconhecida": qualidade["validas_uf_desconhecida"],
            "soma_contagens_uf_igual_brasil": True,
            "metodo": "momentos_centrados_combinados_ddof0",
        },
    }, momentos_uf


def conferir_soma(recebido: float, esperado: float, contexto: str) -> None:
    if not math.isclose(recebido, esperado, rel_tol=0, abs_tol=0.01):
        raise ValueError(
            f"{contexto}: soma de notas não confere com IND-002: "
            f"{recebido:.6f} vs {esperado:.6f}"
        )


def validar_anteriores(dados: list[dict], ref1: dict, ref2: dict, ref3: dict) -> None:
    a = {d["ano"]: d for d in ref1["years"]}
    b = {d["ano"]: d for d in ref2["years"]}
    c = {d["ano"]: d for d in ref3["years"]}
    for d in dados:
        ano = d["ano"]
        br = d["brasil"]
        br1, br2, br3 = a[ano]["brasil"], b[ano]["brasil"], c[ano]["brasil"]
        if not (br["n_validas"] == br1["redacoes_validas"] == br2["n_validas"]
                == br3["n_validas"]):
            raise ValueError(f"{ano}/BR: N diferente dos IND-001–003")
        if not (br["total_registros"] == br1["total_registros"]
                == br2["total_registros"] == br3["total_registros"]):
            raise ValueError(f"{ano}/BR: total de registros diferente dos IND-001–003")
        conferir_soma(br["soma_notas"], br2["soma_notas"], f"{ano}/BR")
        if br["media"] != br2["media"]:
            raise ValueError(f"{ano}/BR: média diverge do IND-002")

        por_uf1 = {u["uf"]: u for u in a[ano]["ufs"]}
        por_uf2 = {u["uf"]: u for u in b[ano]["ufs"]}
        por_uf3 = {u["uf"]: u for u in c[ano]["ufs"]}
        if any(set(dic) != set(UFS) for dic in (por_uf1, por_uf2, por_uf3)):
            raise ValueError(f"{ano}: referências não contêm as 27 UFs")
        for u in d["ufs"]:
            uf = u["uf"]
            u1, u2, u3 = por_uf1[uf], por_uf2[uf], por_uf3[uf]
            if not (u["n_validas"] == u1["redacoes_validas"]
                    == u2["n_validas"] == u3["n_validas"]):
                raise ValueError(f"{ano}/{uf}: N diferente dos IND-001–003")
            if not (u["total_registros"] == u1["total_registros"]
                    == u2["total_registros"] == u3["total_registros"]):
                raise ValueError(f"{ano}/{uf}: total de registros diferente dos IND-001–003")
            conferir_soma(u["soma_notas"], u2["soma_notas"], f"{ano}/{uf}")
            if u["media"] != u2["media"]:
                raise ValueError(f"{ano}/{uf}: média diverge do IND-002")
        d["qualidade"]["validado_contra_ind001_ind002_ind003"] = True


def consolidar_historico(dados: list[dict], por_ano_uf: dict[int, dict[str, Momentos]],
                          ref1: dict, ref2: dict, ref3: dict) -> dict:
    conjuntos = {uf: Momentos() for uf in UFS}
    for ano in ANOS:
        for uf in UFS:
            conjuntos[uf].combinar(por_ano_uf[ano][uf])
    brasil = Momentos()
    ufs = []
    r1 = {u["uf"]: u for u in ref1["historical"]["ufs"]}
    r2 = {u["uf"]: u for u in ref2["historical"]["ufs"]}
    r3 = {u["uf"]: u for u in ref3["historical"]["ufs"]}
    for uf in UFS:
        reg = conjuntos[uf]
        brasil.combinar(reg)
        if reg.n != r1[uf]["redacoes_validas"] or reg.n != r2[uf]["n_validas"] or reg.n != r3[uf]["n_validas"]:
            raise ValueError(f"Histórico/{uf}: N difere dos IND-001–003")
        conferir_soma(reg.soma, r2[uf]["soma_notas"], f"Histórico/{uf}")
        if reg.resultado()["media"] != r2[uf]["media"]:
            raise ValueError(f"Histórico/{uf}: média difere do IND-002")
        ufs.append({"uf": uf, **reg.resultado()})
    rbr1 = ref1["historical"]["brasil"]
    rbr2 = ref2["historical"]["brasil"]
    rbr3 = ref3["historical"]["brasil"]
    if not (brasil.n == rbr1["redacoes_validas"] == rbr2["n_validas"]
            == rbr3["n_validas"] == sum(d["brasil"]["n_validas"] for d in dados)):
        raise ValueError("Histórico/BR: N difere das referências")
    conferir_soma(brasil.soma, rbr2["soma_notas"], "Histórico/BR")
    if brasil.resultado()["media"] != rbr2["media"]:
        raise ValueError("Histórico/BR: média difere do IND-002")
    return {
        "periodo": "2019-2025",
        "brasil": brasil.resultado(),
        "ufs": ufs,
        "nota": NOTA_HISTORICA,
    }


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    grupos = [(str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"]) for d in dados]
    grupos.append(("2019-2025", historico["brasil"], historico["ufs"], "TODAS_AS_EDICOES"))
    linhas = []
    for periodo, nacional, estados, arquivo in grupos:
        registros = [("BRASIL", "BR", nacional)] + [("UF", u["uf"], u) for u in estados]
        for abrangencia, uf, d in registros:
            linhas.append({
                "indicador_id": INDICADOR,
                "periodo": periodo,
                "abrangencia": abrangencia,
                "uf": uf,
                "n_validas": d["n_validas"],
                "soma_notas": d["soma_notas"],
                "nota_media": d["media"],
                "desvio_padrao": d["desvio_padrao"],
                "ddof": 0,
                "metodo": "desvio_populacional_distribuicao_conjunta" if periodo == "2019-2025"
                          else "desvio_populacional_ano_uf",
                "arquivo_fonte": arquivo,
            })
    if len(linhas) != 224:
        raise AssertionError(f"CSV deve ter 224 linhas, obteve {len(linhas)}")
    return linhas


def construir_dashboard(d: dict, dados: list[dict], historico: dict,
                        base: dict, ref1_ano: dict, ref2_ano: dict, ref3_ano: dict,
                        gerado: str) -> dict:
    ano = d["ano"]
    painel = deepcopy(base)
    visao = painel["pages"]["overview"]
    kpis = visao["kpis"]
    if kpis.get("valid_essays") != d["brasil"]["n_validas"]:
        raise ValueError(f"{ano}: KPI valid_essays diverge")
    if kpis.get("mean_score") != ref2_ano["brasil"]["media"]:
        raise ValueError(f"{ano}: KPI mean_score diverge")
    if kpis.get("median_score") != ref3_ano["brasil"]["mediana"]:
        raise ValueError(f"{ano}: KPI median_score diverge")
    if visao["ind003"].get("median_score") != ref3_ano["brasil"]["mediana"]:
        raise ValueError(f"{ano}: detalhamento IND-003 diverge")
    for nome, contagem, valor, esperado in (
        ("ind001", "redacoes_validas", None, None),
        ("ind002", "n", "mean_score", ref2_ano),
        ("ind003", "n", "median_score", ref3_ano),
    ):
        anteriores = {r["uf"]: r for r in visao[nome]["by_uf"]}
        if set(anteriores) != set(UFS):
            raise ValueError(f"{ano}: {nome} não cobre 27 UFs")
        valores_esperados = {r["uf"]: r for r in esperado["ufs"]} if esperado else None
        for linha in d["ufs"]:
            uf = linha["uf"]
            if anteriores[uf][contagem] != linha["n_validas"]:
                raise ValueError(f"{ano}/{uf}: {nome} N diverge")
            if valores_esperados is not None:
                campo_valor = "media" if nome == "ind002" else "mediana"
                if anteriores[uf][valor] != valores_esperados[uf][campo_valor]:
                    raise ValueError(f"{ano}/{uf}: {nome} valor diverge")
    painel["meta"]["analysis_version"] = VERSAO
    painel["meta"]["generated_at"] = gerado
    painel["meta"]["data_status"] = "draft"
    aviso = "IND-004 validado computacionalmente; publicação acadêmica pendente."
    if aviso not in painel["meta"].setdefault("warnings", []):
        painel["meta"]["warnings"].append(aviso)
    kpis["std_score"] = d["brasil"]["desvio_padrao"]
    visao["ind004"] = {
        "indicator_id": INDICADOR,
        "unit": "pontos",
        "n": d["brasil"]["n_validas"],
        "std_score": d["brasil"]["desvio_padrao"],
        "ddof": 0,
        "by_uf": [{"uf": u["uf"], "n": u["n_validas"], "std_score": u["desvio_padrao"]}
                  for u in d["ufs"]],
    }
    painel["pages"]["temporal"]["ind004"] = {
        "indicator_id": INDICADOR,
        "ddof": 0,
        "national_by_year": [
            {"year": x["ano"], "n": x["brasil"]["n_validas"],
             "std_score": x["brasil"]["desvio_padrao"]} for x in dados
        ],
        "period_total": {"n": historico["brasil"]["n_validas"],
                         "std_score": historico["brasil"]["desvio_padrao"]},
        "period_by_uf": [
            {"uf": x["uf"], "n": x["n_validas"], "std_score": x["desvio_padrao"]}
            for x in historico["ufs"]
        ],
        "note": NOTA_HISTORICA,
    }
    painel["pages"]["methodology"]["ind004"] = {
        "definition": DEFINICAO,
        "calculation": "sqrt(sum((nota - media)^2) / N) — ddof=0",
        "population": "POP_VALID, a mesma dos IND-001, IND-002 e IND-003",
        "geographic_dimension": "SG_UF_PROVA",
        "source_file": d["arquivo_fonte"],
        "precision": "4 casas decimais no JSON",
        "historical_note": NOTA_HISTORICA,
    }
    painel["quality"]["ind004_validation"] = d["qualidade"]
    return painel


def validar_dashboard(painel: dict, raiz: Path) -> str:
    if not {"meta", "filters", "quality", "pages"}.issubset(painel):
        raise ValueError("Dashboard incompleto: estruturas principais ausentes")
    paginas = {"overview", "competencies", "evaluators", "high_performance",
               "socioeconomic", "ml", "methodology"}
    if not paginas.issubset(painel["pages"]):
        raise ValueError("Dashboard incompleto: páginas obrigatórias ausentes")
    raw = json.dumps(painel, ensure_ascii=False, allow_nan=False)
    if "NU_INSCRICAO" in raw or "NU_SEQUENCIAL" in raw:
        raise ValueError("Identificador individual detectado no dashboard")
    caminhos = (
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    )
    schema = next((c for c in caminhos if c.is_file()), None)
    if schema is None:
        return "validação estrutural básica (schema não encontrado)"
    try:
        import jsonschema
    except ImportError:
        return "validação estrutural básica (instale jsonschema)"
    with schema.open(encoding="utf-8") as arquivo:
        jsonschema.validate(painel, json.load(arquivo))
    return "validado pelo JSON Schema v1.0.0"


def salvar_json(caminho: Path, dado: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".json.tmp")
    with temporario.open("w", encoding="utf-8") as arq:
        json.dump(dado, arq, ensure_ascii=False, indent=2, allow_nan=False)
        arq.write("\n")
    temporario.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".csv.tmp")
    with temporario.open("w", newline="", encoding="utf-8-sig") as arq:
        writer = csv.DictWriter(arq, fieldnames=list(linhas[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, bloco: int = BLOCO_PADRAO) -> None:
    ref1, ref2, ref3, bases = carregar_referencias(raiz)
    dados = []
    momentos = {}
    for ano in ANOS:
        print(f"IND-004 | {ano}: processando {origem(ano, raiz).name}...", flush=True)
        resultado, por_uf = processar_ano(ano, raiz, bloco)
        dados.append(resultado)
        momentos[ano] = por_uf
        br = resultado["brasil"]
        print(f"  Brasil: n={br['n_validas']:,} | desvio-padrão={br['desvio_padrao']:.4f} | 27 UFs", flush=True)

    validar_anteriores(dados, ref1, ref2, ref3)
    historico = consolidar_historico(dados, momentos, ref1, ref2, ref3)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    por_ano1 = {d["ano"]: d for d in ref1["years"]}
    por_ano2 = {d["ano"]: d for d in ref2["years"]}
    por_ano3 = {d["ano"]: d for d in ref3["years"]}
    dashboards = {}
    for d in dados:
        ano = d["ano"]
        dashboards[ano] = construir_dashboard(
            d, dados, historico, bases[ano], por_ano1[ano], por_ano2[ano],
            por_ano3[ano], gerado,
        )
    verificacoes = {validar_dashboard(doc, raiz) for doc in dashboards.values()}

    modulo = {
        "meta": {
            "indicator_id": INDICADOR,
            "module_schema_version": "ind004-module-1.0.0",
            "analysis_version": VERSAO,
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado,
            "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "comparison_ind001_ind002_ind003": "aprovada (N, total de registros e soma/média)",
            "method": "momentos_centrais_combinados_desvio_populacional_ddof0",
            "precision": "4 casas decimais",
        },
        "indicator": {
            "id": INDICADOR,
            "name": "Desvio-padrão da nota da redação",
            "unit": "pontos",
            "ddof": 0,
            "dashboard_json_path": "pages.overview.kpis.std_score",
        },
        "years": dados,
        "historical": historico,
        "dashboard_files": [f"dashboard_enem_{ano}.json" for ano in ANOS],
    }
    json.dumps(modulo, ensure_ascii=False, allow_nan=False)
    linhas = linhas_csv(dados, historico)
    salvar_csv(raiz / "outputs" / "indicadores" / "IND_004_desvio_padrao_redacao.csv", linhas)
    salvar_json(raiz / "outputs" / "json" / "IND_004_desvio_padrao_redacao.json", modulo)
    for ano in ANOS:
        salvar_json(raiz / "outputs" / "json" / f"dashboard_enem_{ano}.json", dashboards[ano])

    print("\nConcluído! Arquivos de saída:")
    print("  outputs/indicadores/IND_004_desvio_padrao_redacao.csv")
    print("  outputs/json/IND_004_desvio_padrao_redacao.json")
    print("  outputs/json/dashboard_enem_AAAA.json (7 arquivos cumulativos)")
    print(f"  Validação: {', '.join(sorted(verificacoes))}")
    print(f"  Desvio-padrão histórico populacional: {historico['brasil']['desvio_padrao']:.4f} "
          f"(n={historico['brasil']['n_validas']:,})")
    print("  STATUS: draft (aguarda revisão acadêmica)")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND-004 — ENEM 2019–2025")
    parser.add_argument("--raiz", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="Raiz do projeto (padrão: duas pastas acima do script)")
    parser.add_argument("--bloco", type=int, default=BLOCO_PADRAO,
                        help="Tamanho dos blocos para leitura (padrão: 100000)")
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser um número positivo")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
