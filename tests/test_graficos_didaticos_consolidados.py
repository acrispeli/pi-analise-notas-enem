# -*- coding: utf-8 -*-
"""Regressão: metadados consolidados não podem trocar nota por contagem N."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from graficos_educacionais_68 import (
    _fonte_ano, dados_visuais, mostrar_grafico_didatico,
)


class StreamlitFalso:
    def __init__(self):
        self.figuras = []
        self.avisos = []

    def plotly_chart(self, figura, **kwargs):
        self.figuras.append(figura)

    def caption(self, aviso):
        self.avisos.append(aviso)

    def metric(self, *args, **kwargs):
        pass


class TesteGraficosConsolidados(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        base = self.raiz / "outputs" / "json"
        base.mkdir(parents=True)
        for ano in range(2019, 2026):
            overview = {
                "ind001": {
                    "denominator": 500,
                    "national_percentage": 80,
                },
                "kpis": {"valid_essays": 400},
                "ind002": {"n": 400, "mean_score": 590.0 + ano - 2019},
                "ind003": {"n": 400, "median_score": 580 + 20 * (ano - 2019)},
                "ind004": {"n": 400, "std_score": 150.0 + ano - 2019},
                "ind005": {
                    "n": 400,
                    "percentiles": {
                        "p25": 460 + (ano - 2019),
                        "p50": 580 + (ano - 2019),
                        "p75": 700 + (ano - 2019),
                        "p90": 840 + (ano - 2019),
                        "p95": 920 + (ano - 2019),
                    },
                },
            }
            doc = {
                "meta": {"year": ano,
                         "data_status": "consolidado_para_apresentacao"},
                "pages": {"overview": overview},
            }
            (base / f"dashboard_enem_{ano}.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8"
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_fonte_consolidada_e_lida(self):
        doc = _fonte_ano(self.raiz, 2024)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["meta"]["year"], 2024)

    def test_os_quatro_indicadores_selecionam_nota_e_nao_quantidade(self):
        esperado = {
            2: ("valor", 595.0),
            3: ("valor", 680.0),
            4: ("valor", 155.0),
            5: ("p50", 585.0),
        }
        for ind, (chave, valor) in esperado.items():
            with self.subTest(indicador=ind):
                dado = dados_visuais(self.raiz, ind, 2024, "BR")
                self.assertEqual(len(dado), 1)
                self.assertEqual(dado[0][chave], valor)
                self.assertEqual(dado[0]["n"], 400)

    def test_comparacao_historica_e_2024_usam_eixos_corretos(self):
        esperado = {
            2: "Nota média (pontos)",
            3: "Nota mediana (pontos)",
            4: "Dispersão das notas (desvio-padrão) (pontos)",
            5: "Nota de referência",
        }
        for ano in (None, 2024):
            for ind in (2, 3, 4, 5):
                with self.subTest(ano=ano, indicador=ind):
                    st = StreamlitFalso()
                    self.assertTrue(
                        mostrar_grafico_didatico(st, self.raiz, ind, ano, "BR")
                    )
                    self.assertEqual(len(st.figuras), 1)
                    fig = st.figuras[0]
                    eixo = fig.layout.yaxis.title.text or ""
                    # Para um ano, o IND-005 usa "Nota (pontos)"
                    if ind == 5 and ano is not None:
                        self.assertIn("Nota (pontos)", eixo)
                    else:
                        self.assertIn(esperado[ind], eixo)
                    self.assertNotEqual(eixo, "N")
                    if ind in (2, 3, 4) and ano is None:
                        # Além do eixo, o valor permanece junto à bolinha.
                        tr = fig.data[0]
                        self.assertEqual(tr.mode, "lines+markers+text")
                        self.assertEqual(tr.texttemplate, "%{text}")
                        self.assertEqual(len(tr.text), len(tr.y))
                        self.assertIn(",", tr.text[0])
                    if ind == 5 and ano is None:
                        self.assertEqual(
                            {tr.name for tr in fig.data},
                            {"P25", "P50", "P75", "P90", "P95"},
                        )

    def test_ind001_tambem_retorna_visualizacao_com_status_consolidado(self):
        rows = dados_visuais(self.raiz, 1, 2024, "BR")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["validas"], 400)
        self.assertEqual(rows[0]["total"], 500)


if __name__ == "__main__":
    unittest.main()
