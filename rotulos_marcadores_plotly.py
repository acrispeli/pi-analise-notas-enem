# -*- coding: utf-8 -*-
"""Anotações permanentes junto aos marcadores de séries curtas do Plotly.

Usa layout.annotations em coordenadas de dados (x, y). Essa forma é
independente da renderização de texttemplate nos traços Scatter e funciona
também quando o Streamlit aplica seu tema ao Plotly. Sem reprocessar métricas.
"""
from __future__ import annotations

import math


def _formatar_pt_br(valor: float, casas: int) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotular_marcadores(fig, *, casas: int | None = 1,
                      max_series: int = 3, max_pontos: int = 8) -> bool:
    """Adiciona rótulos fixos diretamente nas coordenadas dos marcadores.

    Mantém mode, hover e séries originais; usa anotações sem setas com
    pequeno deslocamento em pixels. Em gráficos densos, não altera a figura.
    """
    if casas is not None and not 0 <= casas <= 4:
        raise ValueError("casas deve estar entre 0 e 4, ou ser None")
    traces = list(fig.data)
    if not 1 <= len(traces) <= max_series:
        return False

    series = []
    for tr in traces:
        if getattr(tr, "type", None) != "scatter":
            return False
        modo = str(getattr(tr, "mode", "") or "")
        if "lines" not in modo or "markers" not in modo:
            return False
        xs = list(tr.x) if tr.x is not None else []
        ys = list(tr.y) if tr.y is not None else []
        if not (2 <= len(ys) <= max_pontos and len(xs) == len(ys)):
            return False
        series.append((xs, ys))

    deslocamentos = [(0, 17), (0, -17), (26, 0)]
    for idx, (tr, (xs, ys)) in enumerate(zip(traces, series)):
        validos = []
        for val in ys:
            try:
                numero = float(val)
                if math.isfinite(numero):
                    validos.append(numero)
            except (TypeError, ValueError, OverflowError):
                continue
        if casas is None:
            significativos = [abs(n) for n in validos if n != 0]
            minimo = min(significativos, default=1)
            maximo = max(significativos, default=0)
            precisao = (
                3 if minimo < 1 else
                0 if maximo >= 10000 and all(n.is_integer() for n in validos)
                else 1
            )
        else:
            precisao = casas

        shift_x, shift_y = deslocamentos[idx]
        for x, y in zip(xs, ys):
            try:
                numero = float(y)
                if not math.isfinite(numero):
                    continue
            except (TypeError, ValueError, OverflowError):
                continue
            fig.add_annotation(
                x=x, y=y, xref=getattr(tr, "xaxis", None) or "x",
                yref=getattr(tr, "yaxis", None) or "y",
                text=_formatar_pt_br(numero, precisao),
                showarrow=False, xshift=shift_x, yshift=shift_y,
                font=dict(size=12, color="#24364B"),
                bgcolor="rgba(255,255,255,0.90)",
                borderpad=2, opacity=1,
                captureevents=False,
            )

    # Expande margem superior sem modificar o eixo de valores nem as notas.
    atual = fig.layout.margin.t if fig.layout.margin and fig.layout.margin.t else 0
    fig.update_layout(margin=dict(t=max(65, atual)))
    return True
