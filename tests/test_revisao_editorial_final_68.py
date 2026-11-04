# -*- coding: utf-8 -*-
"""Testes rápidos da integração final com dados agregados locais."""
from __future__ import annotations
import json
import unittest
from pathlib import Path

from painel_paginas_contrato_68 import fontes_indicador, ler_catalogo
from painel_revisao_geral_68 import renderizar_variante_980, _recorte_ano, _anual_basico
from interpretacao_regras_enem import resumir_indicador
from orientacoes_pedagogicas_68 import ACOES

RAIZ = Path(__file__).resolve().parents[1]

class _St:
    def __init__(self): self.plots=[]
    def plotly_chart(self, fig, *args, **kwargs): self.plots.append(fig)
    def caption(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): raise AssertionError(str(args))
    def warning(self, *args, **kwargs): pass
    def metric(self, *args, **kwargs): pass
    def dataframe(self, *args, **kwargs): pass
    def markdown(self, *args, **kwargs): pass
    def json(self, *args, **kwargs): pass
    def selectbox(self, name, opts, **kwargs): return opts[kwargs.get('index',0)]
    def expander(self, *args, **kwargs): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False

class TesteEditorialFinal68(unittest.TestCase):
    def fonte(self, ind, variante=None):
        fontes=fontes_indicador(RAIZ,ind)
        if variante:
            fontes=[x for x in fontes if variante in x.name]
        self.assertTrue(fontes, f'Sem JSON para IND-{ind:03d}')
        return json.loads(fontes[0].read_text(encoding='utf-8-sig'))

    def test_catalogo_e_fontes(self):
        ids=[i['numero'] for i in ler_catalogo(RAIZ)['indicadores']]
        self.assertEqual(len(ids),68)
        self.assertEqual(len(ACOES),68)
        for i in ids:self.fonte(i)

    def test_v2_na_mesma_pasta(self):
        for i in (55,56,57,58,59,68):
            fontes=fontes_indicador(RAIZ,i)
            self.assertEqual(fontes[0].parent,(RAIZ/'outputs/json'))
            self.assertEqual(self.fonte(i).get('modelo_referencia'),
                            'V2_MCA10_KMeans3_e31f55489e16f296')

    def test_variante_980(self):
        self.assertEqual(len(fontes_indicador(RAIZ,34)),2)
        d=self.fonte(34,'recorte_980_final');st=_St()
        self.assertTrue(renderizar_variante_980(st,d,2024,'BR'))
        self.assertTrue(st.plots)
        self.assertIn('980',resumir_indicador(34,d,{},2024,'BR')['texto'])

    def test_graficos_especializados(self):
        for i in (11,17,21,28,37):
            with self.subTest(ind=i):
                doc=self.fonte(i)
                anos=dict(_recorte_ano(doc,i,'BR'))
                self.assertIn(2024,anos)
                st=_St()
                self.assertTrue(_anual_basico(st,i,anos[2024]))
                self.assertTrue(st.plots)

    def test_ind012_interpretacao_observada(self):
        d=self.fonte(12)
        r=resumir_indicador(12,d,{'_competencia_atual':'C1'},2024,'BR')
        self.assertIn('120 pontos',r['texto'])
        self.assertIn('37,04%',r['texto'])

if __name__=='__main__': unittest.main()
