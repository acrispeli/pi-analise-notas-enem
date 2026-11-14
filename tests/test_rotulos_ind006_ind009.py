# -*- coding: utf-8 -*-
"""Regressão visual: dez faixas do IND-006 e 35 marcadores do IND-009."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd
import plotly.express as px

from painel_revisao_geral_68 import _anual_basico, _historico, _recorte_ano
from rotulos_marcadores_plotly import rotular_historico_competencias
from visualizacao_final_enem import melhorar_figura

RAIZ = Path(__file__).resolve().parents[1]


class StreamlitFalso:
    def __init__(self):
        self.figuras = []

    def plotly_chart(self, fig, **kwargs):
        # Espelha a camada de acabamento realmente instalada no Streamlit.
        melhorar_figura(fig)
        self.figuras.append(fig)

    def dataframe(self, *args, **kwargs):
        pass

    def caption(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def expander(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TesteRotulosInd006Ind009(unittest.TestCase):
    def test_ind006_dez_faixas_com_percentuais_visiveis(self):
        valores = [0.0004, 0.03, 0.8, 5.7, 15.2, 23.0, 24.1, 14.2, 11.4, 5.5696]
        rec = {"faixas": [
            {"faixa": f"{i * 100}–<{(i + 1) * 100}",
             "percentual": valor}
            for i, valor in enumerate(valores)
        ]}
        st = StreamlitFalso()
        self.assertTrue(_anual_basico(st, 6, rec))
        self.assertEqual(len(st.figuras), 1)
        fig = st.figuras[0]
        self.assertEqual(len(fig.data), 1)
        tr = fig.data[0]
        self.assertEqual(list(tr.y), valores)
        self.assertEqual(len(tr.text), 10)
        self.assertEqual(tr.texttemplate, "%{text}")
        self.assertEqual(tr.textposition, "outside")
        self.assertEqual(tr.text[0], "0,0004%")
        self.assertEqual(tr.text[1], "0,03%")
        self.assertEqual(tr.text[4], "15,2%")
        self.assertEqual(tr.text[5], "23%")
        self.assertGreaterEqual(fig.layout.margin.t, 68)

    def test_ind009_mostra_todos_os_pontos_das_cinco_competencias(self):
        series = []
        for ano in range(2019, 2026):
            competencias = [
                {"competencia": comp, "media": float(110 + (ano - 2019) + i * 8)}
                for i, comp in enumerate(("C1", "C2", "C3", "C4", "C5"))
            ]
            series.append((ano, {"competencias": competencias}))
        st = StreamlitFalso()
        self.assertTrue(_historico(st, 9, series))
        self.assertEqual(len(st.figuras), 1)
        fig = st.figuras[0]
        self.assertEqual(len(fig.data), 5)
        self.assertEqual(fig.layout.height, 520)
        self.assertEqual(len(fig.layout.annotations), 35)
        self.assertEqual(
            {a.text for a in fig.layout.annotations if a.x == "2019"},
            {"110,0", "118,0", "126,0", "134,0", "142,0"}
        )
        for trace in fig.data:
            for x, y in zip(trace.x, trace.y):
                self.assertTrue(any(
                    a.x == x and float(a.y) == float(y)
                    for a in fig.layout.annotations
                ))
        self.assertTrue(all(a.showarrow is False for a in fig.layout.annotations))
        self.assertEqual(len(fig.to_plotly_json()["layout"]["annotations"]), 35)

    def test_ind006_dados_reais_preservados(self):
        arq = RAIZ / "outputs/json/IND_006_distribuicao_notas.json"
        doc = json.loads(arq.read_text(encoding="utf-8-sig"))
        anos = dict(_recorte_ano(doc, 6, "BR"))
        self.assertIn(2025, anos)
        dados = anos[2025]["faixas"]
        self.assertEqual(len(dados), 10)
        st = StreamlitFalso()
        self.assertTrue(_anual_basico(st, 6, anos[2025]))
        grafico = st.figuras[0]
        self.assertEqual(list(grafico.data[0].y),
                         [float(linha["percentual"]) for linha in dados])
        self.assertEqual(len(grafico.data[0].text), 10)

    def test_ind009_dados_reais_2019_a_2025(self):
        arq = RAIZ / "outputs/json/IND_009_media_competencias.json"
        doc = json.loads(arq.read_text(encoding="utf-8-sig"))
        anos = _recorte_ano(doc, 9, "BR")
        self.assertEqual([ano for ano, _ in anos], list(range(2019, 2026)))
        st = StreamlitFalso()
        self.assertTrue(_historico(st, 9, anos))
        fig = st.figuras[0]
        self.assertEqual(len(fig.data), 5)
        self.assertEqual(len(fig.layout.annotations), 35)
        self.assertTrue(all(a.text and "," in a.text
                            for a in fig.layout.annotations))

    def test_sem_rotulos_para_series_inadequadas(self):
        anos = list(range(2019, 2026))
        df = pd.DataFrame({
            "ano": anos * 5,
            "valor": list(range(7)) * 5,
            "serie": sum(([f"P{i}"] * 7 for i in range(1, 6)), []),
        })
        fig = px.line(df, x="ano", y="valor", color="serie", markers=True)
        anterior = fig.to_json()
        self.assertFalse(rotular_historico_competencias(fig))
        self.assertEqual(fig.to_json(), anterior)


if __name__ == "__main__":
    unittest.main()
