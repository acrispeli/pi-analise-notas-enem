# -*- coding: utf-8 -*-
"""Teste rápido e offline do bloco didático M1/M2/M3."""
from __future__ import annotations

import unittest
from pathlib import Path

from metodologia_perfis_materiais import (
    PERFIS, VARIAVEIS, carregar_perfis, tabela_respostas,
    resumo_amostra, exibir_metodologia_perfis,
)

RAIZ = Path(__file__).resolve().parents[1]


class StreamlitFalso:
    def __init__(self):
        self.titulos = []
        self.textos = []
        self.tabelas = []
        self.alertas = []

    def expander(self, titulo, **kwargs):
        self.titulos.append(titulo)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def markdown(self, texto):
        self.textos.append(texto)

    def caption(self, texto):
        self.textos.append(texto)

    def table(self, tabela):
        self.tabelas.append(tabela)

    def warning(self, mensagem):
        self.alertas.append(mensagem)


class TesteMetodologiaPerfisMateriais(unittest.TestCase):
    def test_cobertura_10_variaveis_3_perfis(self):
        dados, grupos = carregar_perfis(RAIZ)
        self.assertEqual(len(dados), 30)
        self.assertEqual(set(grupos), set(PERFIS))
        self.assertEqual(sum(grupos.values()), 104752)
        self.assertEqual(len(VARIAVEIS), 10)

    def test_tabela_explicativa_m3_nao_e_regra(self):
        tabela = tabela_respostas(RAIZ)
        self.assertEqual(tabela.shape, (10, 4))
        self.assertEqual(list(tabela.columns), ['Variável', *PERFIS])
        geladeira = tabela.loc[tabela['Variável'] == 'Geladeiras'].iloc[0]
        self.assertEqual(geladeira['M3'], '1 (51,07%)')
        detalhe = tabela_respostas(RAIZ, segunda=True)
        geladeira_detalhe = detalhe.loc[detalhe['Variável'] == 'Geladeiras'].iloc[0]
        self.assertIn('0 (48,47%)', geladeira_detalhe['M3'])

    def test_tamanhos_e_percentuais(self):
        grupos = resumo_amostra(RAIZ)
        self.assertEqual([grupos[p]['n'] for p in PERFIS], [66664, 34240, 3848])
        self.assertAlmostEqual(sum(grupos[p]['percentual'] for p in PERFIS), 100.0, delta=.01)

    def test_renderizacao_nao_muda_modelo(self):
        interface = StreamlitFalso()
        exibir_metodologia_perfis(interface, RAIZ)
        self.assertEqual(interface.titulos, ['Como foram definidos os três perfis socioeconômicos?'])
        self.assertEqual(len(interface.tabelas), 1)
        self.assertFalse(interface.alertas)
        texto = ' '.join(interface.textos)
        for termo in ('MCA', 'K-Means', 'K = 3', '2019–2025', 'não para formar os grupos'):
            self.assertIn(termo, texto)


if __name__ == '__main__':
    unittest.main()
