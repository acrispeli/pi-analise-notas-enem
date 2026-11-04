# -*- coding: utf-8 -*-
"""Testes com os JSONs reais extraídos do ZIP (sem executar microdados)."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from painel_revisao_geral_68 import (renderizar_historico_geral,renderizar_resultados_gerais,
                                     ler_dicionario_questoes,_recorte_ano,mostrar_legenda_questoes,
                                     mostrar_historico_socio_seguro)
from painel_socio_040_055_059 import renderizar_ind040

ROOT=Path(__file__).resolve().parents[1]
class FakeSt:
    def __init__(self):self.charts=[];self.notices=[];self.tables=[];self.expanders=[];self.text=[]
    def selectbox(self,label,options,**kwargs):
        opts=list(options)
        return opts[kwargs.get('index',0)]
    def expander(self,label,**kwargs):
        self.expanders.append(label);return self
    def __enter__(self):return self
    def __exit__(self,*exc):pass
    def plotly_chart(self,fig,**kwargs):
        assert len(fig.data)>0,(fig.layout.title.text if fig.layout.title else 'sem titulo')
        self.charts.append(fig)
    def info(self,s,*a,**kw):self.notices.append(str(s))
    def warning(self,s,*a,**kw):self.notices.append(str(s))
    def error(self,s,*a,**kw):raise AssertionError(s)
    def caption(self,s,*a,**kw):self.text.append(str(s))
    def markdown(self,s,*a,**kw):self.text.append(str(s))
    def metric(self,*args,**kw):pass
    def dataframe(self,df,**kwargs):self.tables.append(df)
    def json(self,obj,**kwargs):pass


def doc(ind):
    files=list((ROOT/'outputs/json').glob(f'IND_{ind:03d}_*.json'))
    selected=next((p for p in files if 'recorte_980' not in p.name and 'dashboard_' not in p.name),None)
    if selected is None:raise ValueError(ind)
    return json.loads(selected.read_text(encoding='utf-8-sig'))

class TestRevisao(unittest.TestCase):
    def test_dicionario_renda_versao(self):
        d19=ler_dicionario_questoes(ROOT,2019)
        d24=ler_dicionario_questoes(ROOT,2024)
        self.assertEqual(len(d19),25);self.assertEqual(len(d24),23)
        self.assertIn('renda mensal',d19['Q006']['pergunta'])
        self.assertIn('renda mensal',d24['Q007']['pergunta'])
        self.assertIn('telefone fixo',d19['Q023']['pergunta'])
        self.assertIn('escola',d24['Q023']['pergunta'].lower())
    def test_series_todos_anos(self):
        for ind in range(6,40):
            with self.subTest(ind=ind):
                st=FakeSt(); d=doc(ind)
                self.assertTrue(renderizar_historico_geral(st,ROOT,d,ind,None,'BR'))
                self.assertTrue(st.charts or st.notices or st.tables or st.expanders)
    def test_edicao_2024_brasil(self):
        for ind in range(6,40):
            with self.subTest(ind=ind):
                st=FakeSt();d=doc(ind)
                self.assertTrue(renderizar_historico_geral(st,ROOT,d,ind,2024,'BR'))
                self.assertTrue(st.charts or st.notices or st.tables or st.expanders)
    def test_edicao_2024_sao_paulo(self):
        for ind in range(6,40):
            with self.subTest(ind=ind):
                st=FakeSt();d=doc(ind)
                self.assertTrue(renderizar_historico_geral(st,ROOT,d,ind,2024,'SP'))
                self.assertTrue(st.charts or st.notices or st.tables or st.expanders)
    def test_sem_uf_nao_usa_brasil(self):
        for ind in (64,65,66,67,69,70,71,72):
            with self.subTest(ind=ind):
                st=FakeSt();d=doc(ind)
                self.assertTrue(renderizar_resultados_gerais(st,d,ind,None,'SP'))
                self.assertFalse(st.charts)
    def test_temporais_metodologia(self):
        for ind in (64,65,66,67,69,70,71,72):
            with self.subTest(ind=ind):
                st=FakeSt();d=doc(ind)
                self.assertTrue(renderizar_resultados_gerais(st,d,ind,None,'BR'))
                self.assertTrue(st.charts or st.tables or st.notices)
    def test_temporais_2024(self):
        for ind in (64,65,66,67,69,70,71,72):
            with self.subTest(ind=ind):
                st=FakeSt();d=doc(ind)
                self.assertTrue(renderizar_resultados_gerais(st,d,ind,2024,'BR'))
    def test_pergunta_ind040(self):
        for ano in (2019,2020,2021,2022,2023,2024,2025):
            with self.subTest(ano=ano):
                st=FakeSt();d=doc(40)
                self.assertEqual(renderizar_ind040(st,d,ano,'BR'),ano)
                self.assertTrue(st.charts)
                self.assertTrue(any('Texto da pergunta' in x for x in st.text))
    def test_questao_escola_historica_nao_errada(self):
        meta={'numero':45,'variaveis':'Q023, score'}
        st=FakeSt();mostrar_legenda_questoes(st,ROOT,meta,2019)
        self.assertTrue(any('não a trajetória escolar' in s for s in st.text))
    def test_historicos_socio_seguros(self):
        for ind in (50,52):
            for uf in ('BR','SP'):
                with self.subTest(ind=ind,uf=uf):
                    st=FakeSt()
                    self.assertTrue(mostrar_historico_socio_seguro(st,ROOT,ind,2024,uf))
                    self.assertTrue(st.charts)
    def test_dicionario_demografico(self):
        st=FakeSt()
        mostrar_legenda_questoes(st,ROOT,
              {'numero':51,'variaveis':'TP_SEXO, TP_FAIXA_ETARIA, TP_COR_RACA'},2024)
        self.assertTrue(any('TP_COR_RACA' in linha for linha in st.text))

    def test_2024_sp_ind040(self):
        st=FakeSt()
        self.assertEqual(renderizar_ind040(st,doc(40),2024,'SP'),2024)
        self.assertTrue(st.charts)

if __name__=='__main__':unittest.main()
