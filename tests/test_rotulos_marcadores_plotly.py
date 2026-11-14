# -*- coding: utf-8 -*-
"""Garantias para rótulos permanentes nos pontos dos gráficos Plotly."""
from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from rotulos_marcadores_plotly import rotular_marcadores
from painel_socio_040_055_059 import renderizar_v2

RAIZ = Path(__file__).resolve().parents[1]


class StreamlitSimulado:
    def __init__(self):
        self.figuras = []
        self.avisos = []

    def plotly_chart(self, fig, **kwargs):
        self.figuras.append(fig)

    def selectbox(self, label, opcoes, **kwargs):
        return list(opcoes)[kwargs.get("index", 0)]

    def caption(self, texto):
        self.avisos.append(str(texto))

    def info(self, texto):
        self.avisos.append(str(texto))

    def warning(self, texto):
        self.avisos.append(str(texto))

    def dataframe(self, *args, **kwargs):
        pass


class TesteRotulosMarcadores(unittest.TestCase):
    def test_media_historica_apresenta_rótulo_pt_br_no_ponto(self):
        anos = list(range(2019, 2026))
        notas = [592.9, 590.2, 636.4, 652.4, 644.8, 659.0, 618.7]
        fig = px.line(pd.DataFrame({"ano": anos, "nota": notas}),
                      x="ano", y="nota", markers=True)
        dados_iniciais = tuple(fig.data[0].y)
        self.assertTrue(rotular_marcadores(fig, casas=1))
        self.assertEqual(tuple(fig.data[0].y), dados_iniciais)
        self.assertEqual(fig.data[0].mode, "lines+markers")
        anotacoes = list(fig.layout.annotations)
        self.assertEqual(len(anotacoes), 7)
        self.assertEqual([a.text for a in anotacoes][0], "592,9")
        self.assertEqual([a.text for a in anotacoes][5], "659,0")
        self.assertEqual([a.text for a in anotacoes][6], "618,7")
        self.assertEqual([a.x for a in anotacoes], anos)
        self.assertEqual([float(a.y) for a in anotacoes], notas)
        self.assertTrue(all(a.showarrow is False for a in anotacoes))
        self.assertTrue(all(a.yshift == 17 for a in anotacoes))
        # A descrição também precisa sobreviver à serialização do Streamlit.
        json_plotly = fig.to_plotly_json()
        self.assertEqual(len(json_plotly["layout"]["annotations"]), 7)

    def test_tres_perfis_tem_posicoes_diferentes(self):
        ano = list(range(2019, 2026))
        df = pd.DataFrame([
            {"ano": a, "Perfil": perfil, "nota": n}
            for perfil, base in (("M1", 560), ("M2", 640), ("M3", 525))
            for a, n in zip(ano, [base + (i * 8) for i in range(7)])
        ])
        fig = px.line(df, x="ano", y="nota", color="Perfil", markers=True)
        self.assertTrue(rotular_marcadores(fig, casas=1))
        self.assertTrue(all(trace.mode == "lines+markers" for trace in fig.data))
        anotacoes = list(fig.layout.annotations)
        self.assertEqual(len(anotacoes), 21)
        self.assertEqual([a.yshift for a in anotacoes],
                         [17] * 7 + [-17] * 7 + [0] * 7)
        self.assertEqual([a.xshift for a in anotacoes],
                         [0] * 14 + [26] * 7)

    def test_nao_aplica_em_grafico_denso_ou_barra(self):
        df = pd.DataFrame([
            {"ano": a, "Competencia": c, "media": 120 + i}
            for i, a in enumerate(range(2019, 2026))
            for c in ("C1", "C2", "C3", "C4", "C5")
        ])
        fig = px.line(df, x="ano", y="media", color="Competencia", markers=True)
        antes = fig.to_json()
        self.assertFalse(rotular_marcadores(fig))
        self.assertEqual(fig.to_json(), antes)
        grande = px.line(x=list(range(20)), y=list(range(20)), markers=True)
        self.assertFalse(rotular_marcadores(grande))
        barra = px.bar(x=["2019", "2020"], y=[592, 590])
        self.assertFalse(rotular_marcadores(barra))

    def test_nulos_sao_vazios_e_contagem_inteira_nao_vira_decimal(self):
        fig = go.Figure(go.Scatter(x=[2019, 2020, 2021, 2022],
                                   y=[1000000, None, 0, 1200000],
                                   mode="lines+markers"))
        self.assertTrue(rotular_marcadores(fig, casas=None))
        self.assertEqual(tuple(a.text for a in fig.layout.annotations),
                         ("1.000.000", "0", "1.200.000"))
        self.assertEqual([a.x for a in fig.layout.annotations],
                         [2019, 2021, 2022])
        self.assertEqual(tuple(fig.data[0].y),
                         (1000000, None, 0, 1200000))

    def test_ind055_real_apresenta_rotulos_sem_mudar_notas(self):
        arq = RAIZ / "outputs" / "json" / "IND_055_perfil_socio_nota.json"
        doc = json.loads(arq.read_text(encoding="utf-8-sig"))
        st = StreamlitSimulado()
        self.assertTrue(renderizar_v2(st, doc, 55, None, "BR"))
        self.assertGreaterEqual(len(st.figuras), 2)
        historico = st.figuras[0]
        self.assertEqual({tr.name for tr in historico.data},
                         {"M1", "M2", "M3"})
        anotacoes = list(historico.layout.annotations)
        self.assertEqual(len(anotacoes),
                         sum(len(tr.y) for tr in historico.data))
        cursor = 0
        for tr in historico.data:
            with self.subTest(perfil=tr.name):
                self.assertEqual(tr.mode, "lines+markers")
                for x, valor in zip(tr.x, tr.y):
                    self.assertTrue(math.isfinite(float(valor)))
                    a = anotacoes[cursor]
                    self.assertEqual(a.x, x)
                    self.assertEqual(float(a.y), float(valor))
                    self.assertEqual(
                        a.text, f"{float(valor):,.1f}".replace(",", "X")
                        .replace(".", ",").replace("X", ".")
                    )
                    cursor += 1


if __name__ == "__main__":
    unittest.main()
