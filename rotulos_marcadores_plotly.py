# -*- coding: utf-8 -*-
"""Rótulos fixos junto aos marcadores de séries curtas do Plotly.

Não cria nem modifica métricas; converte apenas a *apresentação* de valores
já existentes, em formato pt-BR. Gráficos densos continuam usando hover.
"""
from __future__ import annotations

import math


def _formatar_pt_br(valor: float, casas: int) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotular_marcadores(fig, *, casas: int | None = 1,
                      max_series: int = 3, max_pontos: int = 8) -> bool:
    """Acrescenta valores ao lado de cada ponto de linhas curtas.

    Retorna False (sem alterações) quando há muitas curvas/pontos ou quando
    a figura não é exclusivamente um gráfico de linhas com marcadores.
    """
    if casas is not None and not 0 <= casas <= 4:
        raise ValueError("casas deve estar entre 0 e 4, ou ser None")
    traces = list(fig.data)
    if not (1 <= len(traces) <= max_series):
        return False
    series = []
    for tr in traces:
        if getattr(tr, "type", None) != "scatter":
            return False
        mode = str(getattr(tr, "mode", "") or "")
        if "lines" not in mode or "markers" not in mode:
            return False
        valores = list(tr.y) if tr.y is not None else []
        if not (2 <= len(valores) <= max_pontos):
            return False
        series.append(valores)

    posicoes = ("top center", "bottom center", "middle right")
    for idx, (tr, valores) in enumerate(zip(traces, series)):
        validos = []
        for val in valores:
            try:
                num = float(val)
                if math.isfinite(num):
                    validos.append(num)
            except (TypeError, ValueError, OverflowError):
                continue
        if casas is None:
            # Protege séries de números pequenos de rótulos "0,0" enganosos.
            significativos = [abs(x) for x in validos if x != 0]
            minimo = min(significativos, default=1)
            maximo = max(significativos, default=0)
            precisao = (3 if minimo < 1 else 0 if maximo >= 10000
                        and all(x.is_integer() for x in validos) else 1)
        else:
            precisao = casas

        textos = []
        for val in valores:
            try:
                num = float(val)
                textos.append(_formatar_pt_br(num, precisao) if math.isfinite(num) else "")
            except (TypeError, ValueError, OverflowError):
                textos.append("")
        tr.update(mode="lines+markers+text", text=textos, texttemplate="%{text}",
                  textposition=posicoes[idx % len(posicoes)],
                  textfont=dict(size=11), cliponaxis=False)
    # Mantém a altura do gráfico e o hover. A margem superior preserva
    # espaço para valores junto ao topo sem encobrir o título.
    atual = fig.layout.margin.t if fig.layout.margin and fig.layout.margin.t else 0
    fig.update_layout(margin=dict(t=max(55, atual)))
    return True
