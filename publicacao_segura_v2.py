# -*- coding: utf-8 -*-
"""Camada de divulgação pública dos seis indicadores de perfis materiais V2.

Nunca modifica os JSONs estatísticos originais nem substitui células pequenas
por zero. A permissão editorial deve estar explícita; o dado só é visualizado
se o modelo V2 for o esperado. O limite mínimo de 30 registros é uma
salvaguarda adotada pelo projeto, não uma garantia de anonimato.
"""
from __future__ import annotations

from typing import Any

MODELO_V2 = "V2_MCA10_KMeans3_e31f55489e16f296"
PERFIS_V2 = frozenset({55, 56, 57, 58, 59, 68})
MINIMO_PUBLICACAO = 30

# Para indicadores condicionais, até um numerador pequeno pode revelar
# informação de um subgrupo mesmo quando o denominador total é grande.
CONTAGENS_CRITICAS = {
    57: ("n_notas_validas", "n_high_900_1000", "n_near_900_980"),
    58: ("n_near_cluster", "n_com_competencia_valida", "n_com_desconto"),
}


def _contagem_segura(valor: Any) -> bool:
    return (isinstance(valor, int) and not isinstance(valor, bool)
            and valor >= MINIMO_PUBLICACAO)


def preparar_doc_publico_v2(doc: dict, indicador: int) -> tuple[dict | None, int]:
    """Produz uma cópia filtrada; None significa que a fonte não está liberada.

    Regras: modelo fixo V2; autorização registrada; todas as células
    publicadas têm n >= 30 para os campos de contagem disponíveis. Para
    IND-057/058 o critério inclui os numeradores e denominadores sensíveis.
    """
    if indicador not in PERFIS_V2:
        return doc, 0
    if (not isinstance(doc, dict) or
            doc.get("publicacao_autorizada") is not True or
            doc.get("modelo_referencia") != MODELO_V2):
        return None, 0
    resultados = doc.get("results")
    if not isinstance(resultados, list):
        return None, 0
    visiveis = []
    ocultas = 0
    for registro in resultados:
        if not isinstance(registro, dict):
            ocultas += 1
            continue
        if str(registro.get("status", "")).lower() == "nao_aplicavel":
            # Ex.: 2025 sem notas vinculadas; não inventar valor numérico.
            continue
        contagens = [v for k, v in registro.items()
                     if k == "n" or k.startswith("n_")
                     if isinstance(v, int) and not isinstance(v, bool)]
        campos = CONTAGENS_CRITICAS.get(indicador, ())
        incompleta = (any(c not in registro for c in campos)
                      or any(not _contagem_segura(registro[c]) for c in campos))
        insegura = any(not _contagem_segura(v) for v in contagens)
        if incompleta or insegura:
            ocultas += 1
        else:
            visiveis.append(registro.copy())
    protegido = dict(doc)
    protegido["results"] = visiveis
    return protegido, ocultas


def mostrar_aviso_publicacao_v2(st, indicador: int, ocultas: int) -> None:
    """Texto curto, sem divulgar quantidades dos grupos omitidos."""
    if indicador not in PERFIS_V2:
        return
    st.caption(
        "Perfis M1–M3: amostras nacionais, não estimativas da população. "
        "Divulgação pública autorizada pelo responsável pelo projeto, "
        "com supressão de células pequenas e interpretação descritiva."
    )
    if ocultas:
        st.warning(
            "Alguns resultados de subgrupos foram omitidos nesta apresentação "
            "porque possuem menos de 30 observações em alguma contagem relevante. "
            "Ausência de barra, linha ou célula não significa valor zero."
        )
