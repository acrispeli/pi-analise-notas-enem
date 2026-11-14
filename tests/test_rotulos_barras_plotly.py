# -*- coding: utf-8 -*-
"""Regressão: valores sobre colunas e barras curtas realmente renderizadas."""
from __future__ import annotations

import unittest

import pandas as pd
import plotly.express as px

from painel_revisao_geral_68 import _anual_basico
from visualizacao_final_enem import melhorar_figura


class StreamlitComAcabamento:
    """Simula st.plotly_chart já interceptado por instalar_melhorias_visuais."""
    def __init__(self):
        self.figuras = []

    def plotly_chart(self, figura, **kwargs):
        melhorar_figura(figura)
        self.figuras.append(figura)

    def expander(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def dataframe(self, *args, **kwargs):
        pass

    def markdown(self, *args, **kwargs):
        pass

    def caption(self, *args, **kwargs):
        pass


class TesteRotulosBarras(unittest.TestCase):
    def test_ind009_cinco_colunas_coloridas_exibem_notas(self):
        # Reproduz px.bar(... color='competencia') usado pelo IND-009:
        # são cinco TRACOS, e o barmode padrão é relative, sem pilhas reais.
        dados = [
            {"competencia": c, "media": n}
            for c, n in zip(("C1", "C2", "C3", "C4", "C5"),
                            (120.1, 137.8, 119.5, 127.2, 114.1))
        ]
        st = StreamlitComAcabamento()
        self.assertTrue(_anual_basico(st, 9, {"competencias": dados}))
        self.assertEqual(len(st.figuras), 1)
        fig = st.figuras[0]
        self.assertEqual(len(fig.data), 5)
        for tr, expected in zip(fig.data, ("120,1", "137,8", "119,5", "127,2", "114,1")):
            self.assertEqual(tr.type, "bar")
            self.assertEqual(tr.texttemplate, "%{text}")
            self.assertEqual(list(tr.text), [expected])
            self.assertEqual(tr.textposition, "outside")
            self.assertEqual(tr.cliponaxis, False)
        self.assertGreaterEqual(fig.layout.margin.t, 82)

    def test_barras_horizontais_curtas_tambem_recebem_valores(self):
        df = pd.DataFrame({
            "Categoria": ["A", "B", "C"],
            "Média": [48.5, 62.0, 71.3],
        })
        fig = px.bar(df, x="Média", y="Categoria",
                     color="Categoria", orientation="h")
        valores = [list(tr.x) for tr in fig.data]
        melhorar_figura(fig)
        self.assertEqual([list(tr.text) for tr in fig.data],
                         [["48,5"], ["62,0"], ["71,3"]])
        self.assertTrue(all(tr.textposition == "outside" for tr in fig.data))
        self.assertEqual([list(tr.x) for tr in fig.data], valores)
        self.assertGreaterEqual(fig.layout.margin.r, 100)

    def test_barras_agrupadas_com_poucos_valores_sao_rotuladas(self):
        dados = pd.DataFrame({
            "Perfil": ["M1", "M2", "M3", "M1", "M2", "M3"],
            "Estatística": ["Média"] * 3 + ["Mediana"] * 3,
            "Nota": [595.7, 708.2, 575.1, 580.0, 700.0, 560.0],
        })
        fig = px.bar(dados, x="Perfil", y="Nota",
                     color="Estatística", barmode="group")
        antes = [list(tr.y) for tr in fig.data]
        melhorar_figura(fig)
        self.assertEqual([list(tr.y) for tr in fig.data], antes)
        self.assertTrue(all(tr.texttemplate == "%{text}" for tr in fig.data))
        self.assertEqual(sum(len(tr.text) for tr in fig.data), 6)

    def test_pilhas_e_graficos_densos_continuam_sem_numeros(self):
        pilha = pd.DataFrame({
            "Ano": ["2019", "2020", "2019", "2020"],
            "Faixa": ["A", "A", "B", "B"],
            "Percentual": [20.0, 25.0, 80.0, 75.0],
        })
        fig = px.bar(pilha, x="Ano", y="Percentual",
                     color="Faixa", barmode="relative")
        melhorar_figura(fig)
        self.assertTrue(all(tr.text is None for tr in fig.data))
        self.assertTrue(all(tr.texttemplate is None for tr in fig.data))
        denso = px.bar(x=[str(x) for x in range(20)],
                       y=list(range(20)))
        melhorar_figura(denso)
        self.assertIsNone(denso.data[0].texttemplate)

    def test_valores_pequenos_preservam_casas_decimais(self):
        fig = px.bar(pd.DataFrame({
            "Ano": ["2019", "2024"],
            "Percentual (%)": [0.0014, 0.0004],
            "Tipo": ["A", "B"],
        }), x="Ano", y="Percentual (%)", color="Tipo")
        melhorar_figura(fig)
        self.assertEqual([t.text[0] for t in fig.data], ["0,0014%", "0,0004%"])

    def test_nao_sobrescreve_textos_anteriores_e_e_idempotente(self):
        df = pd.DataFrame({"C": ["C1", "C2"], "Nota": [100.0, 120.0]})
        fig = px.bar(df, x="C", y="Nota", text="Nota")
        texto_antes = list(fig.data[0].text)
        melhorar_figura(fig)
        self.assertEqual(list(fig.data[0].text), texto_antes)
        snapshot = fig.to_json()
        melhorar_figura(fig)
        self.assertEqual(fig.data[0].texttemplate, fig.data[0].texttemplate)
        self.assertEqual(list(fig.data[0].text), texto_antes)


if __name__ == "__main__":
    unittest.main()
