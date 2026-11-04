"""Testes de integração com dados SINTÉTICOS; não processam microdados reais."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/indicadores'))
import _ind055_072_core as c

class TesteSintetico(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='enem_lote3_teste_')
        self.root=Path(self.temp.name)
        for x in ['outputs/json','outputs/indicadores','src/indicadores','data/raw/2019','data/raw/2024','data/derived']:
            (self.root/x).mkdir(parents=True,exist_ok=True)
    def tearDown(self):self.temp.cleanup()
    def escrever(self,ind,rows):
        p=self.root/'outputs/indicadores'/f'IND_{ind:03d}_teste.csv'
        with p.open('w',encoding='utf8',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');wr.writeheader();wr.writerows(rows)
    def test_temporais_e_qualidade(self):
        rows02=[];rows03=[];rows09=[];rows10=[];rows31=[];rows32=[];rows20=[];rows22=[]
        for year in (2019,2020):
            rows02.append({'periodo':year,'uf':'BR','n_validas':100,'nota_media':600})
            rows03.append({'periodo':year,'uf':'BR','n_validas':100,'nota_mediana':620})
            for comp in ['C1','C2','C3','C4','C5']:
                rows09.append({'periodo':year,'uf':'BR','competencia':comp,'n_validas':100,'media':120})
                rows10.append({'periodo':year,'uf':'BR','competencia':comp,'n_validas':100,'mediana':120})
                rows31.append({'periodo':year,'uf':'BR','competencia':comp,'faixa':'POP_NEAR_TOTAL','n_redacoes':12,'media_perda':20})
                rows32.append({'ano':year,'uf':'BR','competencia':comp,'n_redacoes':12,'frequencia_desconto':.5,'n_com_desconto':6})
            rows20.append({'periodo':year,'uf':'BR','n_avaliacoes_pareadas':100,'media':50,'mediana':40,'bin_ordem':1})
            rows22.append({'periodo':year,'uf':'BR','n_pop_evaluator':100,'percentual_discrepancia_confirmada_pop_evaluator':10,'n_indeterminada':2})
        for id,r in [(2,rows02),(3,rows03),(9,rows09),(10,rows10),(31,rows31),(32,rows32),(20,rows20),(22,rows22)]:self.escrever(id,r)
        for id in [64,65,66,67]:
            result=c.temporal(id,self.root)
            assert result['results'] and result['indicator_id']==f'IND-{id:03d}'
            self.assertEqual([x for x in result['results'] if x.get('status')=='ok'][0]['ano'],2019)
            c.write_results(id,self.root,result,False)
        r=c.small_071(self.root)
        self.assertTrue(any(x['celulas_positivas_1_a_29']>0 for x in r['results']))
        c.write_results(71,self.root,r,False)
        doc=c.provenance_072(self.root)
        self.assertGreater(len(doc['results']),0)
        c.write_results(72,self.root,doc,False)
    def test_join_e_ausentes(self):
        def raw(ano,arquivo,rows):
            dir=self.root/f'data/raw/{ano}'
            dir.mkdir(parents=True,exist_ok=True)
            p=dir/arquivo
            with p.open('w',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows)
        raw(2019,'MICRODADOS_ENEM_2019.csv',[{'NU_INSCRICAO':i,'NU_ANO':2019,'NU_NOTA_REDACAO':500 if i!=3 else ''} for i in (1,2,3)])
        raw(2019,'COMPETENCIAS_REDACAO_2019.csv',[{'NU_INSCRICAO':i,'NU_ANO':2019} for i in (2,3,4)])
        raw(2024,'PARTICIPANTES_2024.csv',[{'NU_INSCRICAO':i,'Q001':'A'} for i in (2,4)])
        raw(2024,'COMPETENCIAS_REDACAO_2024.csv',[{'NU_INSCRICAO':i} for i in (4,5)])
        raw(2024,'RESULTADOS_2024.csv',[{'NU_NOTA_REDACAO':500,'TP_STATUS_REDACAO':1}])
        jd=c.join_069(self.root,[2019,2024,2025],block=100)
        self.assertEqual(jd['results'][0]['matched'],2)
        self.assertEqual(jd['results'][1]['matched'],1)
        self.assertEqual(jd['results'][2]['status'],'nao_aplicavel')
        missing=c.missing_070(self.root,[2019,2024],block=100)
        self.assertTrue(any(r['n_ausentes']==1 for r in missing['results']))
        self.assertEqual(c.check_prereqs(55,self.root)['status'],'bloqueado_por_dependencia')
    def preparar_ponte(self):
        rng=np.random.default_rng(2026)
        manifest={'schema_version':c.BRIDGE_VERSION,'modelo_referencia':'IND-054:pooled_core_clusters:hash_validado',
                  'validacao_mca_clusters':'aprovado','anos':{}}
        for ano,nn in [(2019,230),(2024,245),(2025,20)]:
            df=pd.DataFrame({'ano':ano,'id_registro':[str(ano*10000+i) for i in range(nn)],
                             'uf':rng.choice(['SP','AC'],size=nn),
                             'cluster_ref':rng.choice(['C1','C2'],size=nn),
                             'Q001':rng.choice(['A','B','C'],size=nn),
                             'Q002':rng.choice(['A','B','C'],size=nn)})
            if ano!=2025:
                df['nota_redacao']=rng.choice(np.arange(0,1001,20),size=nn)
                for i in range(1,6):df[f'c{i}']=rng.choice(np.arange(0,201,20),size=nn)
                df['av1']=rng.choice(np.arange(0,1001,20),size=nn)
                df['av2']=rng.choice(np.arange(0,1001,20),size=nn)
            p=self.root/f'data/derived/ponte_{ano}.csv';df.to_csv(p,sep=';',index=False)
            manifest['anos'][str(ano)]={'arquivo':p.relative_to(self.root).as_posix(),
                                         'n_registros':nn,'sha256':c.sha(p),
                                         'join_qa':'ok','unicidade_qa':'ok'}
        (self.root/'data/derived/manifesto_ponte_socio_cluster.json').write_text(json.dumps(manifest))
    def test_cruzamentos_modelos_e_perfis(self):
        self.preparar_ponte()
        for id in [55,56,57,58,59]:
            doc=c.cluster_cross(id,self.root)
            self.assertTrue(any(r['ano']==2019 for r in doc['results']))
            self.assertTrue(any(r['ano']==2025 and r['status']=='nao_aplicavel' for r in doc['results']))
        d=c.temporal_clusters_068(self.root)
        self.assertTrue(any(r.get('ano')==2025 and r.get('status')=='ok' for r in d['results']))
        from importlib.util import find_spec
        if find_spec('sklearn') is not None and find_spec('joblib') is not None:
            d=c.ml_model(60,self.root)
            self.assertTrue(d['results'][0]['n_teste']>=50)
            imp=c.ml_model(62,self.root)
            self.assertTrue(imp['results'])
            q=c.ml_model(63,self.root)
            self.assertTrue(q['results'])
            models=c.ml_model(61,self.root)
            self.assertEqual(len(models['results']),5)

if __name__=='__main__':unittest.main(verbosity=2)
