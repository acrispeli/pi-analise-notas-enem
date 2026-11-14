# -*- coding: utf-8 -*-
"""Regressões de apresentação dos indicadores IND-005, IND-008 e C1–C5."""
import json
import tempfile
import unittest
from pathlib import Path

import plotly.graph_objects as go

from interpretacao_regras_enem import resumir_indicador
from visualizacao_final_enem import _grafico_essencial_catalogo, melhorar_figura


class StreamlitFalso:
    def __init__(self):
        self.metricas = []
        self.graficos = []
        self.tabelas = []
        self.avisos = []

    def metric(self, nome, valor, **kwargs):
        self.metricas.append((nome, str(valor)))

    def columns(self, n):
        return [self for _ in range(n)]

    def plotly_chart(self, figura, **kwargs):
        self.graficos.append(figura)

    def dataframe(self, tabela, **kwargs):
        self.tabelas.append(tabela)

    def caption(self, texto):
        pass

    def info(self, texto):
        self.avisos.append(texto)


class TestesCorrecaoVisualPrioritaria(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.json_dir = self.raiz / 'outputs' / 'json'
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.painel = StreamlitFalso()
        self.notas = {
            'years': [
                {'ano': 2019, 'brasil': {
                    'n_validas': 3779356, 'n_notas_1000': 53,
                    'percentual': 0.0014, 'requer_revisao_privacidade': False}},
                {'ano': 2024, 'brasil': {
                    'n_validas': 3002710, 'n_notas_1000': 12,
                    'percentual': 0.0004, 'requer_revisao_privacidade': False},
                 'ufs': [{'uf': 'SP', 'n_validas': 476463, 'n_notas_1000': 2,
                          'percentual': 0.0004, 'requer_revisao_privacidade': True}]}
            ],
        }
        (self.json_dir / 'IND_008_notas_1000.json').write_text(
            json.dumps(self.notas), encoding='utf-8'
        )

    def test_ind005_cinco_percentis_visiveis(self):
        dashboard = {
            'meta': {'year': 2024, 'data_status': 'draft'},
            'pages': {'overview': {'ind005': {
                'n': 3002710,
                'percentiles': {'p25': 540, 'p50': 640, 'p75': 800,
                                'p90': 880, 'p95': 920}
            }}}
        }
        (self.json_dir / 'dashboard_enem_2024.json').write_text(
            json.dumps(dashboard), encoding='utf-8'
        )
        resultado = _grafico_essencial_catalogo(self.painel, self.raiz, 5, 2024, 'BR')
        self.assertTrue(resultado)
        self.assertEqual([x[0] for x in self.painel.metricas],
                         ['P25', 'P50', 'P75', 'P90', 'P95'])
        self.assertIn(('P95', '920 pontos'), self.painel.metricas)
        figura = self.painel.graficos[0]
        self.assertEqual(list(figura.data[0].x), ['P25', 'P50', 'P75', 'P90', 'P95'])

    def test_renderer_real_ind002_003_004_exibe_rotulos_nas_bolinhas(self):
        # Regressão da camada que substitui o gráfico didático padrão.
        # A captura do localhost mostrava a legenda "Cada ponto representa",
        # que só é emitida por _grafico_essencial_catalogo.
        medias = [592.9, 590.2, 636.4, 652.4, 644.8, 659.0, 618.7]
        for i, ano in enumerate(range(2019, 2026)):
            documento = {
                'meta': {'year': ano,
                         'data_status': 'consolidado_para_apresentacao'},
                'pages': {'overview': {
                    'ind002': {'n': 1000, 'mean_score': medias[i]},
                    'ind003': {'n': 1000, 'median_score': 580.0 + i * 10},
                    'ind004': {'n': 1000, 'std_score': 140.0 + i},
                }},
            }
            (self.json_dir / f'dashboard_enem_{ano}.json').write_text(
                json.dumps(documento), encoding='utf-8'
            )
        for numero in (2, 3, 4):
            with self.subTest(indicador=numero):
                painel = StreamlitFalso()
                resultado = _grafico_essencial_catalogo(
                    painel, self.raiz, numero, None, 'BR'
                )
                self.assertTrue(resultado)
                self.assertEqual(len(painel.graficos), 1)
                fig = painel.graficos[0]
                self.assertEqual(len(fig.layout.annotations), 7)
                self.assertEqual(list(fig.data[0].x), list(range(2019, 2026)))
                for ano, valor, anotacao in zip(
                        fig.data[0].x, fig.data[0].y, fig.layout.annotations):
                    self.assertEqual(anotacao.x, ano)
                    self.assertEqual(float(anotacao.y), float(valor))
                    self.assertFalse(anotacao.showarrow)
                    self.assertTrue(anotacao.text)
                    self.assertIn(',', anotacao.text)
                if numero == 2:
                    self.assertEqual(
                        [a.text for a in fig.layout.annotations],
                        ['592,9', '590,2', '636,4', '652,4', '644,8',
                         '659,0', '618,7']
                    )
                # O wrapper visual instalado no Streamlit não pode apagar
                # as anotações antes de passar a figura ao navegador.
                melhorar_figura(fig)
                self.assertEqual(len(fig.layout.annotations), 7)
                self.assertGreaterEqual(fig.layout.margin.t, 72)
                self.assertEqual(
                    len(fig.to_plotly_json()['layout']['annotations']), 7
                )

    def test_ind008_2024_nao_arredonda_para_zero(self):
        resultado = _grafico_essencial_catalogo(self.painel, self.raiz, 8, 2024, 'BR')
        self.assertTrue(resultado)
        self.assertIn(('Redações com nota 1.000', '12'), self.painel.metricas)
        self.assertIn(('Percentual entre as redações válidas', '0,0004%'),
                      self.painel.metricas)
        resumo = resumir_indicador(8, self.notas, {}, 2024, 'BR')['texto']
        self.assertIn('12 redações', resumo)
        self.assertIn('0,0004%', resumo)
        self.assertNotIn('0,00%', resumo)

    def test_ind008_historico_tem_contagens_e_precisao(self):
        resultado = _grafico_essencial_catalogo(self.painel, self.raiz, 8, None, 'BR')
        self.assertTrue(resultado)
        self.assertEqual(len(self.painel.tabelas), 1)
        self.assertEqual(list(self.painel.graficos[0].data[0].x), [2019, 2024])
        resumo = resumir_indicador(8, self.notas, {}, None, 'BR')['texto']
        self.assertIn('2019', resumo)
        self.assertIn('2024', resumo)
        self.assertIn('0,0014%', resumo)
        self.assertIn('0,0004%', resumo)
        self.assertNotIn('0,00%', resumo)

    def test_ind008_uf_com_celula_pequena_nao_exibe_numero(self):
        resultado = _grafico_essencial_catalogo(self.painel, self.raiz, 8, 2024, 'SP')
        self.assertTrue(resultado)
        self.assertFalse(self.painel.metricas)
        self.assertTrue(self.painel.avisos)
        resumo = resumir_indicador(8, self.notas, {}, 2024, 'SP')['texto']
        self.assertIn('Não há resultado', resumo)
        self.assertNotIn('0,0004%', resumo)

    def test_legendas_de_competencias_nao_sao_truncadas(self):
        figura = go.Figure()
        figura.add_trace(go.Scatter(x=[2019, 2024], y=[130, 140],
                                    name='C1 · Domínio da modalidade escrita formal'))
        figura.add_trace(go.Scatter(x=[2019, 2024], y=[140, 150],
                                    name='C2 · Compreensão da proposta'))
        melhorar_figura(figura)
        self.assertEqual([t.name for t in figura.data], ['C1', 'C2'])


if __name__ == '__main__':
    unittest.main()
