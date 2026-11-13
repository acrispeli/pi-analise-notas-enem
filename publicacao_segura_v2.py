# -*- coding: utf-8 -*-
"""Apresentação agregada dos seis indicadores de perfis materiais V2.

Os resultados publicados continuam amostrais. A decisão editorial do projeto
dispensou a supressão automática por n < 30 nesta interface; contagens pequenas
são mantidas e sinalizadas por causa da instabilidade estatística.
Não se exibem microdados nem se inventam valores indisponíveis.
"""
from __future__ import annotations

MODELO_V2 = "V2_MCA10_KMeans3_e31f55489e16f296"
PERFIS_V2 = frozenset({55, 56, 57, 58, 59, 68})
LIMIAR_AVISO_AMOSTRA = 30


def _contagens(registro: dict) -> list[int]:
    """Localiza apenas contagens n/n_*; notas e médias não são denominadores."""
    return [
        v for k, v in registro.items()
        if (k == "n" or k.startswith("n_"))
        and isinstance(v, int) and not isinstance(v, bool)
    ]


def preparar_doc_publico_v2(doc: dict, indicador: int) -> tuple[dict | None, int]:
    """Retorna resultados agregados completos e número de linhas com n pequeno.

    A autorização e a versão do modelo continuam obrigatórias. Nenhuma linha
    aplicável é suprimida por seu tamanho; ausências formais não viram zeros.
    A contagem retornada serve apenas para aviso estatístico, não para filtrar.
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

    linhas = [
        registro.copy() for registro in resultados
        if isinstance(registro, dict)
        and str(registro.get("status", "")).lower() not in
        ("nao_aplicavel", "indisponivel")
    ]
    pequenas = sum(
        any(n < LIMIAR_AVISO_AMOSTRA for n in _contagens(registro))
        for registro in linhas
    )
    completo = dict(doc)
    completo["results"] = linhas
    return completo, pequenas


def mostrar_aviso_publicacao_v2(st, indicador: int, pequenas: int) -> None:
    """Explica limites dos perfis e, quando necessário, da amostra pequena."""
    if indicador not in PERFIS_V2:
        return
    st.caption(
        "Perfis M1–M3: análises de uma amostra nacional, não estimativas da "
        "população brasileira. Divulgação pública autorizada pelo responsável "
        "pelo projeto; resultados descritivos, sem relação causal comprovada."
    )
    if pequenas:
        st.warning(
            "Este indicador inclui grupos com contagens inferiores a 30. "
            "Esses resultados foram mantidos na apresentação; porcentagens "
            "e médias de grupos pequenos podem ser instáveis. "
            "Uma métrica ausente não deve ser interpretada como zero."
        )
