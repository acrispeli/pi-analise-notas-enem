# -*- coding: utf-8 -*-
"""Testes autocontidos; `python -m unittest discover -s tests -p test_leitura_acessivel_68.py`."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leitura_acessivel_68 import GUIAS, texto_leigo, mostrar_leitura_acessivel
from graficos_educacionais_68 import dados_visuais, resumo_expresso, mostrar_grafico_didatico


class SimuladorStreamlit:
    def __init__(self):self.events=[]
    def __getattr__(self,name):
        if name=='expander':return lambda *args,**kwargs:self
        def fn(*args,**kwargs):self.events.append((name,args,kwargs))
        return fn
    def __enter__(self):return self
    def __exit__(self,*args):return None


class TestePedagogia(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.raiz=Path(self.tmp.name)
        (self.raiz/'outputs/json').mkdir(parents=True)
        for year,valid,total,pp in [
            (2019,100,200,{'p25':400,'p50':500,'p75':700,'p90':850,'p95':900}),
            (2024,120,160,{'p25':480,'p50':600,'p75':780,'p90':900,'p95':940}),
        ]:
            doc={'meta':{'year':year,'data_status':'draft'},'pages':{'overview':{
                'kpis':{'valid_essays':valid},
                'ind001':{'denominator':total,'by_uf':[{'uf':'SP','total_registros':total//2,'redacoes_validas':valid//2}]},
                'ind002':{'mean_score':580,'n':valid,'by_uf':[{'uf':'SP','mean_score':560,'n':valid//2}]},
                'ind003':{'median_score':pp['p50'],'n':valid,'by_uf':[{'uf':'SP','median_score':pp['p50'],'n':valid//2}]},
                'ind004':{'std_score':100,'n':valid,'by_uf':[{'uf':'SP','std_score':110,'n':valid//2}]},
                'ind005':{'n':valid,'percentiles':pp,'by_uf':[{'uf':'SP','n':valid//2,'percentiles':pp}]},
                'essay_status':{'categories':[{'rotulo':'Sem problemas','quantidade':valid,'requer_revisao_privacidade':False},
                                                {'rotulo':'Demais','quantidade':total-valid,'requer_revisao_privacidade':False}],
                                'by_uf':[{'uf':'SP','categories':[{'rotulo':'Sem problemas','quantidade':5,'requer_revisao_privacidade':True}]}]}
            }}}
            (self.raiz/'outputs/json'/f'dashboard_enem_{year}.json').write_text(json.dumps(doc),encoding='utf-8')

    def tearDown(self):self.tmp.cleanup()

    def test_os_68_tem_leitura_individual(self):
        esperados=set(range(1,73))-{60,61,62,63}
        self.assertEqual(set(GUIAS),esperados)
        for n in esperados:
            g=texto_leigo(n,{},None,'BR')
            self.assertTrue(g['oque'] and g['como'] and g['pedag'])

    def test_ind001_ano_uf_e_serie(self):
        br=dados_visuais(self.raiz,1,None,'BR')
        self.assertEqual(len(br),2)
        self.assertEqual(br[0]['pct'],50)
        self.assertEqual(br[-1]['pct'],75)
        self.assertEqual(dados_visuais(self.raiz,1,2024,'SP')[0]['validas'],60)
        self.assertEqual(dados_visuais(self.raiz,1,2025,'BR'),[])
        self.assertIn('pontos percentuais',resumo_expresso(self.raiz,1,None,'BR')['texto'])

    def test_ind005_nao_media_de_percentis(self):
        s=dados_visuais(self.raiz,5,None,'BR')
        self.assertEqual([r['p90'] for r in s],[850,900])
        self.assertIn('P25',resumo_expresso(self.raiz,5,2024,'BR')['texto'])

    def test_nao_exibir_celula_pequena_status(self):
        self.assertEqual(dados_visuais(self.raiz,7,2024,'SP'),[])
        self.assertEqual(len(dados_visuais(self.raiz,7,2024,'BR')),1)

    def test_graficos_funcionam_sem_servidor(self):
        st=SimuladorStreamlit()
        for n in (1,2,3,4,5,7):
            self.assertTrue(mostrar_grafico_didatico(st,self.raiz,n,2024,'BR'),n)
        self.assertTrue(any(n=='plotly_chart' for n,_,_ in st.events))

    def test_texto_sem_ia_e_sem_expor_microdados(self):
        st=SimuladorStreamlit()
        mostrar_leitura_acessivel(st,1,{}, {},2024,'BR',resumo_especifico={'texto':'Teste observado','nota':'Cautela'})
        self.assertTrue(any('Teste observado' in str(a) for n,a,k in st.events if n=='write'))
        self.assertTrue(any('regras transparentes' in str(a) for n,a,k in st.events if n=='caption'))


if __name__=='__main__':unittest.main()
