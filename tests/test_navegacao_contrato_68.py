"""Testes sintéticos sem microdados; executar: python tests/test_navegacao_contrato_68.py"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from painel_paginas_contrato_68 import (
    ler_catalogo, fontes_indicador, _caminho_contrato,
    _valor_contrato, _filtrar_registros, _kpi_por_uf, ROTAS, MODELO_V2,
)


class TestesCatalogo(unittest.TestCase):
    def test_68_indicadores_oito_paginas(self):
        cat = ler_catalogo(RAIZ)
        ids = {x['numero'] for x in cat['indicadores']}
        self.assertEqual(ids, set(range(1,73))-{60,61,62,63})
        self.assertEqual([p['rota'] for p in cat['paginas']], list(ROTAS))
        self.assertEqual(sum(x['pagina']=='socioeconomic' for x in cat['indicadores']), 18)
        self.assertEqual(sum(x['pagina']=='ml' for x in cat['indicadores']), 2)

    def test_variantes_e_preferencia_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'outputs/json').mkdir(parents=True)
            (root/'outputs/rascunho_ponte_v2/json').mkdir(parents=True)
            for n in ('IND_001_dashboard_2019.json','IND_001_redacoes_validas.json',
                      'IND_034_competencia_unica_impede_1000.json','IND_034_recorte_980_final.json'):
                (root/'outputs/json'/n).write_text('{}',encoding='utf-8')
            self.assertTrue(fontes_indicador(root,1)[0].name.endswith('redacoes_validas.json'))
            self.assertEqual(len(fontes_indicador(root,34)),2)
            def criar(nome, path, ref):
                path.write_text(json.dumps({'modelo_referencia':ref,'publicacao_autorizada':False}),encoding='utf-8')
            principal=root/'outputs/json/IND_055_perfil_socio_nota.json'
            rascunho=root/'outputs/rascunho_ponte_v2/json/IND_055_perfil_socio_nota.json'
            criar('',principal,'MODELO_ANTIGO')
            criar('',rascunho,MODELO_V2)
            self.assertEqual(fontes_indicador(root,55),[rascunho])
            criar('',principal,MODELO_V2)
            self.assertEqual(fontes_indicador(root,55),[principal])
            self.assertEqual(fontes_indicador(root,60),[])

    def test_contrato_nao_finge_2024_ser_todos_os_anos(self):
        ref={'pages':{'overview':{'kpis':{'mean_score':658}},'temporal':{'ind002':{'national_by_year':[{'year':2019,'mean_score':592},{'year':2024,'mean_score':658}]}}}}
        val,orig=_valor_contrato(ref,None,2,'pages.overview.kpis.mean_score',None)
        self.assertEqual(len(val['national_by_year']),2)
        val,orig=_valor_contrato(ref,None,3,'pages.overview.kpis.median_score',None)
        self.assertIsNone(val)
        val,orig=_valor_contrato(ref,None,2,'pages.overview.kpis.mean_score',2025)
        self.assertIsNone(val)
        val,orig=_valor_contrato(ref,ref,2,'pages.overview.kpis.mean_score',2024)
        self.assertEqual(val,658)

    def test_kpi_local_explicito_por_uf(self):
        anual={'pages':{'overview':{'ind002':{'by_uf':[{'uf':'SP','mean_score':650},{'uf':'RJ','mean_score':630}]}}}}
        self.assertEqual(_kpi_por_uf(anual,2,'SP','pages.overview.kpis.mean_score'),650)
        self.assertIsNone(_kpi_por_uf(anual,2,'MG','pages.overview.kpis.mean_score'))

    def test_sem_uf_nao_simula_recorte_local(self):
        rows=[{'ano':2024,'cluster':'C1','media':500}]
        df,msg=_filtrar_registros(rows,2024,'SP')
        self.assertTrue(df.empty)
        self.assertIn('UF',msg)


if __name__=='__main__':
    unittest.main(verbosity=2)
