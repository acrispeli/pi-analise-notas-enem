# -*- coding: utf-8 -*-
"""IND-001 | Redações válidas por ano, Brasil e UF (ENEM 2019–2025).

População POP_VALID: TP_STATUS_REDACAO == '1' e NU_NOTA_REDACAO
preenchida, numérica e entre 0 e 1000 (inclusive).

Fontes (todas com SG_UF_PROVA, TP_STATUS_REDACAO, NU_NOTA_REDACAO):
  2019–2023: MICRODADOS_ENEM_AAAA.csv
  2024–2025: RESULTADOS_AAAA.csv
Nenhuma junção individual é necessária para este indicador, inclusive em 2024.

Executar no terminal, a partir da raiz do projeto:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_001_redacoes_validas.py

Saídas:
  outputs/indicadores/IND_001_redacoes_validas.csv
  outputs/json/IND_001_redacoes_validas.json        (módulo histórico completo)
  outputs/json/IND_001_dashboard_AAAA.json          (um payload por ano)

JSONs do dashboard são compatíveis com o contrato estrutural v1.0.0, mas
continuam em status 'draft' até conferência e aprovação dos dados reais.
Não exporta registros individuais nem identificadores de inscrição.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
))
UF_NAO_INFORMADA = "NAO_INFORMADA"
COLUNAS = ("SG_UF_PROVA", "TP_STATUS_REDACAO", "NU_NOTA_REDACAO")
TAMANHO_BLOCO = 100_000
ID_INDICADOR = "IND-001"
DEFINICAO = (
    "Contagem de registros com TP_STATUS_REDACAO = 1 e NU_NOTA_REDACAO "
    "preenchida, numericamente interpretável e no intervalo de 0 a 1000."
)


def fonte(ano: int, raiz: Path) -> Path:
    nome = (f"MICRODADOS_ENEM_{ano}.csv" if ano <= 2023
            else f"RESULTADOS_{ano}.csv")
    return raiz / "data" / "raw" / str(ano) / nome


def percentual(numerador: int, denominador: int) -> float | None:
    return round(100 * numerador / denominador, 4) if denominador else None


def contar_ano(ano: int, raiz: Path, chunksize: int = TAMANHO_BLOCO) -> dict:
    """Varre somente três colunas, em blocos, sem carregar o CSV integral."""
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo obrigatório não encontrado: {caminho}")

    cont = Counter()
    por_uf_total = Counter()
    por_uf_validas = Counter()

    leitor = pd.read_csv(
        caminho, sep=";", usecols=list(COLUNAS), dtype=str,
        keep_default_na=False, na_filter=False,
        encoding="utf-8-sig", encoding_errors="replace",
        chunksize=chunksize, on_bad_lines="error",
    )
    for bloco in leitor:
        uf_origem = bloco["SG_UF_PROVA"].str.strip().str.upper()
        uf_reconhecida = uf_origem.isin(UFS)
        uf = uf_origem.where(uf_reconhecida, UF_NAO_INFORMADA)

        status = bloco["TP_STATUS_REDACAO"].str.strip()
        nota_texto = bloco["NU_NOTA_REDACAO"].str.strip()
        nota = pd.to_numeric(
            nota_texto.str.replace(",", ".", regex=False), errors="coerce"
        )
        status_1 = status.eq("1")
        nota_ok = nota.notna() & nota.between(0, 1000)
        valida = status_1 & nota_ok
        nota_vazia = nota_texto.eq("")

        cont["registros"] += len(bloco)
        cont["status_1"] += int(status_1.sum())
        cont["validas"] += int(valida.sum())
        cont["status_1_sem_nota"] += int((status_1 & nota_vazia).sum())
        cont["status_1_nota_invalida"] += int(
            (status_1 & ~nota_vazia & ~nota_ok).sum()
        )
        cont["validas_uf_ausente"] += int(
            (valida & uf_origem.eq("")).sum()
        )
        cont["validas_uf_nao_reconhecida"] += int(
            (valida & ~uf_reconhecida & uf_origem.ne("")).sum()
        )
        cont["registros_uf_nao_informada"] += int((~uf_reconhecida).sum())

        # value_counts agrega em C, sem iterar sobre milhões de linhas Python.
        por_uf_total.update(uf.value_counts().to_dict())
        por_uf_validas.update(uf[valida].value_counts().to_dict())

    n = cont["registros"]
    if n == 0:
        raise ValueError(f"Arquivo sem registros: {caminho}")
    if cont["status_1"] != (cont["validas"] +
                            cont["status_1_sem_nota"] +
                            cont["status_1_nota_invalida"]):
        raise AssertionError(f"{ano}: status 1 não reconcilia com as notas")
    if sum(por_uf_total.values()) != n:
        raise AssertionError(f"{ano}: total por UF não reconcilia com linhas")
    if sum(por_uf_validas.values()) != cont["validas"]:
        raise AssertionError(f"{ano}: válidas por UF não reconciliam com Brasil")

    # Falhar explicitamente antes de publicar totais estaduais incompletos.
    if cont["status_1_sem_nota"] or cont["status_1_nota_invalida"]:
        raise ValueError(
            f"{ano}: existem registros com status 1 e nota ausente/inválida: "
            f"{cont['status_1_sem_nota']} vazias, "
            f"{cont['status_1_nota_invalida']} inválidas. Revisar base."
        )
    if cont["validas_uf_ausente"] or cont["validas_uf_nao_reconhecida"]:
        raise ValueError(
            f"{ano}: {cont['validas_uf_ausente']} redações válidas sem UF e "
            f"{cont['validas_uf_nao_reconhecida']} com UF não reconhecida. "
            "Não é seguro publicar distribuição por UF sem resolver isso."
        )

    ufs = [
        {
            "uf": sigla,
            "redacoes_validas": int(por_uf_validas[sigla]),
            "total_registros": int(por_uf_total[sigla]),
            "percentual_validas": percentual(
                por_uf_validas[sigla], por_uf_total[sigla]
            ),
            "participacao_no_brasil_pct": percentual(
                por_uf_validas[sigla], cont["validas"]
            ),
        }
        for sigla in UFS
    ]
    if sum(d["redacoes_validas"] for d in ufs) != cont["validas"]:
        raise AssertionError(f"{ano}: soma das 27 UFs é diferente do Brasil")

    return {
        "ano": ano,
        "arquivo_fonte": caminho.name,
        "brasil": {
            "redacoes_validas": int(cont["validas"]),
            "total_registros": int(n),
            "percentual_validas": percentual(cont["validas"], n),
            "status_1": int(cont["status_1"]),
        },
        "ufs": ufs,
        "qualidade": {
            "status": "ok",
            "status_1_sem_nota": int(cont["status_1_sem_nota"]),
            "status_1_nota_invalida": int(cont["status_1_nota_invalida"]),
            "validas_uf_ausente": int(cont["validas_uf_ausente"]),
            "validas_uf_nao_reconhecida": int(cont["validas_uf_nao_reconhecida"]),
            "registros_uf_nao_informada": int(
                cont["registros_uf_nao_informada"]
            ),
            "soma_27_ufs_igual_brasil": True,
        },
    }


def conferir_relatorio_anterior(raiz: Path, dados: list[dict]) -> str:
    """Reconcilia com o relatório do script 02, se existir e tiver as fontes.

    Não usa números fixos no código: a referência vem do diagnóstico executado
    no próprio projeto. Compara tanto linhas quanto status 1 por edição.
    """
    arq_resumo = raiz / "outputs" / "validacao_registros_resumo.csv"
    arq_cat = raiz / "outputs" / "validacao_registros_categorias.csv"
    if not arq_resumo.is_file() or not arq_cat.is_file():
        return "não executada (relatórios do script 02 não localizados)"

    with arq_resumo.open(encoding="utf-8-sig", newline="") as arquivo:
        resumo = {
            (int(r["ano"]), r["arquivo"]): int(r["registros"])
            for r in csv.DictReader(arquivo, delimiter=";")
            if r.get("ano") and r.get("registros")
        }
    with arq_cat.open(encoding="utf-8-sig", newline="") as arquivo:
        status_1 = {
            (int(r["ano"]), r["arquivo"]): int(r["quantidade"])
            for r in csv.DictReader(arquivo, delimiter=";")
            if r.get("ano") and r.get("variavel") == "TP_STATUS_REDACAO"
            and r.get("valor") == "1"
        }

    for d in dados:
        k = (d["ano"], d["arquivo_fonte"])
        if k not in resumo or k not in status_1:
            raise ValueError(
                f"Faltam referências de {k} nos relatórios do script 02. "
                "Rode novamente 02_validacao_registros.py."
            )
        if d["brasil"]["total_registros"] != resumo[k]:
            raise ValueError(f"{k}: registros diferentes do relatório do script 02")
        if d["brasil"]["status_1"] != status_1[k]:
            raise ValueError(f"{k}: status 1 diferente do relatório do script 02")
        # No período 2019–2024, as notas detalhadas estão em arquivo
        # complementar. É possível conferir os totais SEM juntar pessoas.
        if d["ano"] <= 2024:
            chave_complemento = (
                d["ano"], f"COMPETENCIAS_REDACAO_{d['ano']}.csv"
            )
            if chave_complemento in status_1:
                if status_1[chave_complemento] != d["brasil"]["status_1"]:
                    raise ValueError(
                        f"{d['ano']}: quantidade de status 1 difere entre "
                        "microdados/resultados e competências da redação"
                    )
    return "aprovada (totais e status 1 conferidos no script 02)"


def agregar_historico(dados: list[dict]) -> dict:
    total = sum(d["brasil"]["total_registros"] for d in dados)
    validas = sum(d["brasil"]["redacoes_validas"] for d in dados)
    ufs = []
    for sigla in UFS:
        n_uf = sum(
            next(item["total_registros"] for item in d["ufs"]
                 if item["uf"] == sigla)
            for d in dados
        )
        v_uf = sum(
            next(item["redacoes_validas"] for item in d["ufs"]
                 if item["uf"] == sigla)
            for d in dados
        )
        ufs.append({
            "uf": sigla,
            "redacoes_validas": v_uf,
            "total_registros": n_uf,
            "percentual_validas": percentual(v_uf, n_uf),
            "participacao_no_brasil_pct": percentual(v_uf, validas),
        })
    if sum(r["redacoes_validas"] for r in ufs) != validas:
        raise AssertionError("Histórico: UF e Brasil não reconciliam")
    return {
        "anos": [d["ano"] for d in dados],
        "brasil": {
            "redacoes_validas": validas,
            "total_registros": total,
            "percentual_validas": percentual(validas, total),
        },
        "ufs": ufs,
        "nota": (
            "Soma de participações/redações nas edições, não de pessoas "
            "únicas entre anos. UF significa local de aplicação da prova."
        ),
    }


def validar_privacidade(dados: list[dict], historico: dict) -> None:
    """Impede publicação de valores positivos inferiores ao limiar do projeto.

    O antigo limiar 30 foi retirado como bloqueio automático de publicação.
    O IND-001 divulga somente totais estaduais e nacionais. Em caso de
    exceção, a saída deve ser revista em vez de contornar a proteção.
    """
    limite = 1  # Contagens agregadas positivas são divulgáveis; sem piso automático de 30.
    for d in dados:
        for item in [d["brasil"], *d["ufs"]]:
            n = item["redacoes_validas"]
            if 0 < n < limite:
                nome = item.get("uf", "BR")
                raise ValueError(
                    f"{d['ano']}/{nome}: contagem {n} inferior ao mínimo "
                    f"de divulgação ({limite}). Rever supressão antes de publicar."
                )
    for item in [historico["brasil"], *historico["ufs"]]:
        n = item["redacoes_validas"]
        if 0 < n < limite:
            nome = item.get("uf", "BR")
            raise ValueError(
                f"Histórico/{nome}: contagem {n} inferior ao limiar {limite}."
            )


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    linhas = []
    grupos = [
        (str(d["ano"]), d["brasil"], d["ufs"], d["arquivo_fonte"])
        for d in dados
    ]
    grupos.append((
        f"{dados[0]['ano']}-{dados[-1]['ano']}", historico["brasil"],
        historico["ufs"], "SOMA_DAS_EDICOES"
    ))
    for periodo, br, ufs, fonte_csv in grupos:
        for escopo, item in [("BRASIL", {"uf": "BR", **br})] + [
            ("UF", item) for item in ufs
        ]:
            linhas.append({
                "indicador_id": ID_INDICADOR,
                "periodo": periodo,
                "abrangencia": escopo,
                "uf": item["uf"],
                "redacoes_validas": item["redacoes_validas"],
                "total_registros": item["total_registros"],
                "percentual_validas": item["percentual_validas"],
                "participacao_no_brasil_pct": (
                    100.0 if escopo == "BRASIL" and br["redacoes_validas"]
                    else item.get("participacao_no_brasil_pct")
                ),
                "arquivo_fonte": fonte_csv,
            })
    return linhas


def contrato_por_ano(d: dict, dados: list[dict], historico: dict, gerado: str) -> dict:
    """Contrato JSON 1.0.0 com páginas ainda não implementadas indisponíveis."""
    ano = d["ano"]
    nao_implementado = {
        "status": "unavailable", "reason": "indicadores_ainda_nao_implementados"
    }
    return {
        "meta": {
            "schema_version": "1.0.0",
            "analysis_version": "2.0.0-ind001",
            "dataset_version": f"enem-{ano}-csv-publico",
            "generated_at": gerado,
            "year": ano,
            "data_status": "draft",
            "source_files": [d["arquivo_fonte"]],
            "population_definition": DEFINICAO,
            "warnings": [
                "Resultado ainda depende de revisão e aprovação acadêmica.",
                "Consolidado histórico conta participações, não pessoas únicas."
            ],
        },
        "filters": {
            "active": {"year": ano, "population": "valid_essay", "uf_exam": "BR"},
            "available": {
                "year": historico["anos"],
                "population": [{"code": "valid_essay", "label": "Redações válidas"}],
                "uf_exam": ["BR", *UFS],
            },
            "combination_policy": (
                "IND-001 permite ano e UF de aplicação; demais filtros "
                "serão habilitados por indicadores posteriores."
            ),
        },
        "quality": {
            "join_diagnostics": {
                "status": "not_required",
                "reason": "As três variáveis do IND-001 constam na mesma fonte de resultados."
            },
            "missingness": [
                {
                    "variable": "SG_UF_PROVA",
                    "n_missing_valid": d["qualidade"]["validas_uf_ausente"],
                },
                {
                    "variable": "NU_NOTA_REDACAO",
                    "n_missing_status_1": d["qualidade"]["status_1_sem_nota"],
                },
            ],
            "suppression": {
                "min_group_n": 1,
                "suppressed_cells": 0,
                "note": (
                    "Nenhuma supressão automática por contagem menor que 30; apenas agregados."
                )
            },
            "indicator_validation": d["qualidade"],
        },
        "pages": {
            "overview": {
                "status": "ok",
                "kpis": {
                    "valid_essays": d["brasil"]["redacoes_validas"],
                },
                "ind001": {
                    "indicator_id": ID_INDICADOR,
                    "unit": "redacoes",
                    "denominator": d["brasil"]["total_registros"],
                    "national_percentage": d["brasil"]["percentual_validas"],
                    "by_uf": d["ufs"],
                },
            },
            "competencies": dict(nao_implementado),
            "evaluators": dict(nao_implementado),
            "high_performance": dict(nao_implementado),
            "socioeconomic": dict(nao_implementado),
            "ml": dict(nao_implementado),
            "temporal": {
                "status": "ok",
                "indicator_id": ID_INDICADOR,
                "national_by_year": [
                    {"year": r["ano"], **r["brasil"]}
                    for r in dados
                ],
                "period_total": historico["brasil"],
                "period_by_uf": historico["ufs"],
                "note": historico["nota"],
            },
            "methodology": {
                "status": "ok",
                "indicator_id": ID_INDICADOR,
                "definition": DEFINICAO,
                "geographic_dimension": "SG_UF_PROVA",
                "source_file": d["arquivo_fonte"],
                "aggregation": "COUNT por ano e UF; soma anual para Brasil",
                "limitations": historico["nota"],
            },
        },
    }


def validar_json(payload: dict, raiz: Path) -> str:
    """Validação básica sempre; JSON Schema opcional quando disponível."""
    chaves = {"meta", "filters", "quality", "pages"}
    if not chaves.issubset(payload):
        raise ValueError("Payload não contém as seções obrigatórias")
    paginas = {
        "overview", "competencies", "evaluators", "high_performance",
        "socioeconomic", "ml", "methodology"
    }
    if not paginas.issubset(payload["pages"]):
        raise ValueError("Payload não contém as páginas requeridas no schema v1")
    # Não pode conter valores JSON inválidos nem identificadores pessoais.
    serializado = json.dumps(payload, allow_nan=False, ensure_ascii=False)
    if "NU_INSCRICAO" in serializado or "NU_SEQUENCIAL" in serializado:
        raise ValueError("Identificador individual detectado no JSON")

    candidatos = [
        raiz / "docs" / "04_resultados_analises.schema.json",
        raiz / "docs" / "metodologia" / "04_resultados_analises.schema.json",
        raiz / "04_resultados_analises.schema.json",
    ]
    schema = next((c for c in candidatos if c.is_file()), None)
    if not schema:
        return "estrutura obrigatória verificada; schema externo não localizado"
    try:
        import jsonschema  # pip install jsonschema, se necessário
    except ImportError:
        return "estrutura obrigatória verificada; instale jsonschema para validação formal"
    with schema.open(encoding="utf-8") as arq:
        jsonschema.validate(payload, json.load(arq))
    return "validado pelo JSON Schema v1.0.0"


def salvar_json(caminho: Path, payload: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8") as arq:
        json.dump(payload, arq, ensure_ascii=False, indent=2, allow_nan=False)
        arq.write("\n")
    temporario.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as arq:
        escritor = csv.DictWriter(arq, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(caminho)


def executar(raiz: Path, tamanho_bloco: int = TAMANHO_BLOCO) -> None:
    dados = []
    for ano in ANOS:
        print(f"IND-001 | {ano}: lendo {fonte(ano, raiz).name}...", flush=True)
        d = contar_ano(ano, raiz, tamanho_bloco)
        dados.append(d)
        print(f"  Brasil: {d['brasil']['redacoes_validas']:,} redações válidas; "
              f"27 UFs reconciliadas.", flush=True)

    conferencia = conferir_relatorio_anterior(raiz, dados)
    print(f"Conferência com o script 02: {conferencia}")
    historico = agregar_historico(dados)
    validar_privacidade(dados, historico)
    gerado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    saida_ind = raiz / "outputs" / "indicadores"
    saida_json = raiz / "outputs" / "json"

    # Validar todos antes de criar qualquer saída nova.
    dashboard = [contrato_por_ano(d, dados, historico, gerado) for d in dados]
    estados = [validar_json(p, raiz) for p in dashboard]

    modulo = {
        "meta": {
            "indicator_id": ID_INDICADOR,
            "module_schema_version": "ind001-module-1.0.0",
            "analysis_version": "2.0.0-ind001",
            "dataset_version": "enem-2019-2025-csv-publico",
            "generated_at": gerado,
            "data_status": "draft",
            "source_files": {str(d["ano"]): d["arquivo_fonte"] for d in dados},
            "population_definition": DEFINICAO,
            "geographic_dimension": "SG_UF_PROVA",
            "previous_qa_comparison": conferencia,
        },
        "indicator": {
            "id": ID_INDICADOR,
            "name": "Redações válidas analisadas",
            "dashboard_json_path": "pages.overview.kpis.valid_essays",
            "unit": "redacoes",
        },
        "years": dados,
        "historical": historico,
        "dashboard_files": [f"IND_001_dashboard_{d['ano']}.json" for d in dados],
    }
    salvar_csv(saida_ind / "IND_001_redacoes_validas.csv",
               linhas_csv(dados, historico))
    salvar_json(saida_json / "IND_001_redacoes_validas.json", modulo)
    for d, p in zip(dados, dashboard):
        salvar_json(saida_json / f"IND_001_dashboard_{d['ano']}.json", p)

    print("\nConcluído. Saídas:")
    print(f"  {saida_ind / 'IND_001_redacoes_validas.csv'}")
    print(f"  {saida_json / 'IND_001_redacoes_validas.json'}")
    print(f"  {saida_json / 'IND_001_dashboard_AAAA.json'} (7 arquivos)")
    print(f"  Validação do contrato: {', '.join(sorted(set(estados)))}")
    print(f"  Total histórico: {historico['brasil']['redacoes_validas']:,} "
          "participações com redação válida (não pessoas únicas).")
    print("  STATUS: draft — conferir os CSVs reais antes de publicar.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Indicador 001 — ENEM 2019–2025")
    parser.add_argument(
        "--raiz", type=Path, default=Path(__file__).resolve().parents[2],
        help="Raiz do projeto (padrão: duas pastas acima deste script)."
    )
    parser.add_argument(
        "--bloco", type=int, default=TAMANHO_BLOCO,
        help="Tamanho de leitura de CSV em linhas (padrão: 100000)."
    )
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error("--bloco deve ser maior que zero")
    executar(args.raiz.resolve(), args.bloco)


if __name__ == "__main__":
    main()
