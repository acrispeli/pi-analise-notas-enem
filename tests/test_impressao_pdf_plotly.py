# -*- coding: utf-8 -*-
"""Regressão visual: gráficos Plotly não devem extrapolar o PDF."""
import unittest

from exportar_pdfs_streamlit_68_sincronizado import (
    ESTILO_IMPRESSAO, preparar_impressao_sem_cortes, restaurar_impressao,
    largura_imprimivel_css, ultima_pagina_so_rodape,
    grafico_historico_tem_todos_anos,
)


class TestesImpressaoPdf(unittest.TestCase):
    def test_css_oculta_apenas_nota_editorial_marcada(self):
        self.assertIn('[data-exportador-nota-editorial="1"]', ESTILO_IMPRESSAO)
        self.assertIn('break-inside: avoid', ESTILO_IMPRESSAO)

    def test_largura_calculada_pela_folha_e_nao_pelo_viewport(self):
        largura = largura_imprimivel_css('A4', True, 0.80)
        self.assertGreater(largura, 1100)
        self.assertLess(largura, 1400)
        self.assertLess(largura_imprimivel_css('A4', False, 0.80), largura)
        self.assertGreater(largura_imprimivel_css('A3', True, 0.80), largura)

    def test_rejeita_rodape_isolado_e_eixo_historico_incompleto(self):
        class Pagina:
            def __init__(self, texto):
                self.texto = texto

            def extract_text(self):
                return self.texto

        class Leitor:
            def __init__(self, paginas):
                self.pages = [Pagina(s) for s in paginas]

        rodape = ('Projeto Integrador IV — UNIVESP · Dados agregados · '
                  'Versão de apresentação · Validação editorial declarada '
                  'pela equipe · Análises não oficiais do INEP. 4 / 4')
        leitor = Leitor(['IND-002 · Nota média', 'Nota média (pontos): 2019 2020 2021 2022 2023',
                         'Explicação pedagógica', rodape])
        self.assertTrue(ultima_pagina_so_rodape(leitor))
        self.assertFalse(grafico_historico_tem_todos_anos(leitor, 'IND-002'))
        completo = Leitor(['IND-002 · Nota média',
                          'Nota média (pontos): 2019 2020 2021 2022 2023 2024 2025',
                          'Explicação pedagógica'])
        self.assertFalse(ultima_pagina_so_rodape(completo))
        self.assertTrue(grafico_historico_tem_todos_anos(completo, 'IND-002'))

    def test_titulos_atuais_dos_quatro_graficos_historicos(self):
        class Pagina:
            def __init__(self, texto):
                self.texto = texto

            def extract_text(self):
                return self.texto

        class Leitor:
            def __init__(self, paginas):
                self.pages = [Pagina(t) for t in paginas]

        rotulos = '2019 2020 2021 2022 2023 2024 2025'
        titulos = {
            'IND-002': 'Nota média (pontos)',
            'IND-003': 'Nota mediana (pontos)',
            'IND-004': 'Dispersão das notas (desvio-padrão) (pontos)',
            'IND-005': 'Nota de referência\\nP25 P50 P75 P90 P95',
        }
        for codigo, titulo in titulos.items():
            with self.subTest(indicador=codigo):
                pdf = Leitor(['Cabeçalho e filtros', titulo + '\\n' + rotulos,
                              'Leitura pedagógica'])
                self.assertTrue(grafico_historico_tem_todos_anos(pdf, codigo))
                # Não basta mencionar o intervalo 2019–2025 em uma legenda:
                # os rótulos devem estar na página do próprio gráfico.
                incompleto = Leitor(['2019 2020 2021 2022 2023',
                                     titulo + '\\n2024 2025'])
                self.assertFalse(grafico_historico_tem_todos_anos(incompleto, codigo))
                incompleto = Leitor([titulo + '\\n2019 2020 2021 2022 2023 2024'])
                self.assertFalse(grafico_historico_tem_todos_anos(incompleto, codigo))

    def test_nao_aprova_grafico_de_quantidade_em_lugar_de_notas(self):
        class Pagina:
            def __init__(self, texto):
                self.texto = texto

            def extract_text(self):
                return self.texto

        class Leitor:
            def __init__(self, texto):
                self.pages = [Pagina(texto)]

        # Reproduz o que foi encontrado nos quatro PDFs enviados:
        # o eixo Y estava marcado com N para IND-003, 004 e 005.
        texto = '2019 2020 2021 2022 2023 2024 2025\\nN\\n2,2M 3M 3,8M'
        for codigo in ('IND-003', 'IND-004', 'IND-005'):
            with self.subTest(indicador=codigo):
                self.assertFalse(
                    grafico_historico_tem_todos_anos(Leitor(texto), codigo)
                )
        # O IND-005 não é válido com apenas a curva de IQR; deve mostrar
        # todos os cinco percentis. Não basta haver ano e eixo de nota.
        self.assertFalse(grafico_historico_tem_todos_anos(
            Leitor('Nota de referência\\n2019 2020 2021 2022 2023 2024 2025'),
            'IND-005'
        ))

    def test_ultimo_ano_permanece_no_pdf_a4(self):
        try:
            from playwright.sync_api import sync_playwright
            from pypdf import PdfReader
        except ImportError:
            self.skipTest('Playwright/pypdf não instalados')
        import tempfile
        from pathlib import Path
        with sync_playwright() as playwright:
            navegador = None
            for parametros in ({'channel': 'msedge', 'headless': True},
                               {'headless': True}):
                try:
                    navegador = playwright.chromium.launch(**parametros)
                    break
                except Exception:
                    continue
            if navegador is None:
                self.skipTest('Sem navegador Chromium')
            try:
                pagina = navegador.new_page(viewport={'width': 1560, 'height': 970})
                anos = ''.join(
                    f'<text x="{80+i*230}" y="180" font-size="20">'
                    f'{2019+i}</text>' for i in range(7))
                pagina.set_content(
                    '<div data-testid="stMainBlockContainer" '
                    'style="width:1560px"><div data-testid="stPlotlyChart">'
                    '<div class="js-plotly-plot" style="width:1516px">'
                    '<svg class="main-svg" width="1516" height="240">'
                    + anos + '</svg></div></div></div>')
                etiqueta = pagina.add_style_tag(content=ESTILO_IMPRESSAO)
                info = preparar_impressao_sem_cortes(pagina, 'A4', True, 0.80)
                self.assertLess(info['larguraPaginaCss'], 1400)
                with tempfile.TemporaryDirectory() as pasta:
                    arquivo = Path(pasta) / 'grafico.pdf'
                    pagina.pdf(path=str(arquivo), format='A4',
                               landscape=True, scale=0.80,
                               margin={'top':'12mm', 'bottom':'14mm',
                                       'left':'10mm', 'right':'10mm'})
                    texto = ' '.join(p.extract_text() or ''
                                     for p in PdfReader(str(arquivo)).pages)
                    for ano in range(2019, 2026):
                        self.assertIn(str(ano), texto)
                etiqueta.evaluate("el => el.remove()")
                restaurar_impressao(pagina)
            finally:
                navegador.close()

    def test_plotly_grande_cabe_na_pagina_e_estado_e_restaurado(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright não instalado')
        with sync_playwright() as playwright:
            navegador = None
            for argumentos in ({'channel': 'msedge', 'headless': True},
                               {'headless': True}):
                try:
                    navegador = playwright.chromium.launch(**argumentos)
                    break
                except Exception:
                    continue
            if navegador is None:
                self.skipTest('Edge/Chromium não disponível para teste visual')
            try:
                pagina = navegador.new_page(viewport={'width': 600, 'height': 700})
                pagina.set_content("""
                <div data-testid="stPlotlyChart" style="width:420px;position:relative">
                    <div class="js-plotly-plot" style="width:900px">
                        <svg class="main-svg" width="900" height="240"></svg>
                    </div>
                </div>
                <div data-testid="stCaptionContainer">
                    Projeto Integrador IV — UNIVESP · Dados agregados ·
                    Versão de apresentação · Validação editorial declarada
                    pela equipe · Análises não oficiais do INEP.
                </div>""")
                etiqueta = pagina.add_style_tag(content=ESTILO_IMPRESSAO)
                diagnostico = preparar_impressao_sem_cortes(pagina)
                self.assertEqual(diagnostico['graficos'], 1)
                self.assertEqual(len(diagnostico['ajustados']), 1)
                self.assertTrue(diagnostico['notaEditorialNoRodape'])
                self.assertLess(float(
                    pagina.locator('.js-plotly-plot').evaluate(
                        "(el) => el.style.zoom")), 1.0)
                self.assertTrue(pagina.locator(
                    '[data-exportador-nota-editorial="1"]').count())
                etiqueta.evaluate("el => el.remove()")
                restaurar_impressao(pagina)
                self.assertEqual(pagina.locator('.js-plotly-plot').evaluate(
                    "(el) => el.style.zoom"), '')
                self.assertEqual(pagina.locator(
                    '[data-exportador-nota-editorial]').count(), 0)
            finally:
                navegador.close()


if __name__ == '__main__':
    unittest.main()
