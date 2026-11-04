# -*- coding: utf-8 -*-
"""Testes de regressão sobre os dashboards agregados distribuídos no projeto."""
from pathlib import Path
import sys
import unittest

RAIZ=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ))

from painel_socio_041_052 import (
    carregar_recorte, categorias_grupo, subgrupos, tabela_medias,
    tabela_competencias, anos_com_dados, renderizar_socio,
)


class StreamlitSimulado:
    def __init__(self):
        self.figuras=[]
        self.avisos=[]
        self.tabelas=[]

    def selectbox(self, titulo, opcoes, **kw):
        return list(opcoes)[kw.get('index',0)]

    def plotly_chart(self, figura, **kw):
        assert len(figura.data)>=1
        self.figuras.append(figura)

    def dataframe(self, tabela, **kw):
        self.tabelas.append(tabela)

    def info(self, mensagem):self.avisos.append(mensagem)
    def warning(self, mensagem):self.avisos.append(mensagem)
    def caption(self, mensagem):pass
    def metric(self, *args, **kw):pass


class TestesSocio(unittest.TestCase):
    def test_fontes_2019_2025_nao_inventadas(self):
        self.assertEqual(anos_com_dados(RAIZ,41),list(range(2019,2025)))
        self.assertEqual(anos_com_dados(RAIZ,52),list(range(2019,2026)))
        dado,erro=carregar_recorte(RAIZ,41,2025,'BR')
        self.assertIsNone(dado)
        self.assertIn('2025',erro)

    def test_uf_sp_nao_substituida_por_brasil(self):
        br,erro=carregar_recorte(RAIZ,41,2024,'BR')
        self.assertIsNone(erro)
        sp,erro=carregar_recorte(RAIZ,41,2024,'SP')
        self.assertIsNone(erro)
        self.assertEqual(br['dados']['uf'],'BR')
        self.assertEqual(sp['dados']['uf'],'SP')
        self.assertNotEqual(br['dados']['categories'][0]['media'],sp['dados']['categories'][0]['media'])

    def test_medias_renda_2024_valores_arquivo(self):
        recorte,erro=carregar_recorte(RAIZ,41,2024,'BR')
        self.assertIsNone(erro)
        df=tabela_medias(categorias_grupo(recorte['dados'],41),41)
        self.assertEqual(list(df['Codigo']),[chr(c) for c in range(65,82)])
        self.assertAlmostEqual(df.iloc[0]['Média'],580.484)
        self.assertAlmostEqual(df.iloc[-1]['Média'],784.2097)
        self.assertIn('Nenhuma renda',df.iloc[0]['Descrição'])

    def test_doze_indicadores_brasil_sp_e_rr(self):
        for indicador in range(41,53):
            for uf in ('BR','SP','RR'):
                with self.subTest(indicador=indicador,uf=uf):
                    recorte,erro=carregar_recorte(RAIZ,indicador,2024,uf)
                    self.assertIsNone(erro)
                    if indicador==52:
                        self.assertIn('metricas',recorte['dados'])
                        continue
                    grupos=subgrupos(recorte['dados'],indicador)
                    cats=categorias_grupo(recorte['dados'],indicador,next(iter(grupos),None))
                    self.assertTrue(cats)
                    if indicador in (42,44,46):
                        self.assertFalse(tabela_competencias(cats,indicador).empty)
                    else:
                        self.assertFalse(tabela_medias(cats,indicador).empty)

    def test_construcao_graficos_todos_indicadores(self):
        for ind in range(41,53):
            for uf in ('BR','SP'):
                with self.subTest(indicador=ind,uf=uf):
                    falso=StreamlitSimulado()
                    ok=renderizar_socio(falso,RAIZ,ind,2024,uf)
                    self.assertTrue(ok)
                    self.assertTrue(falso.figuras,f'Gráfico ausente IND-{ind:03d}, UF={uf}')
                    self.assertTrue(falso.tabelas)

    def test_todos_os_anos_mostra_edicao_explicitamente(self):
        falso=StreamlitSimulado()
        self.assertTrue(renderizar_socio(falso,RAIZ,41,None,'BR'))
        self.assertTrue(any('Todos os anos' in msg for msg in falso.avisos))
        self.assertTrue(falso.figuras)

    def test_ind_052_2025_e_ind_041_2025_ausente(self):
        valido=StreamlitSimulado()
        self.assertTrue(renderizar_socio(valido,RAIZ,52,2025,'SP'))
        self.assertTrue(valido.figuras)
        indisponivel=StreamlitSimulado()
        self.assertTrue(renderizar_socio(indisponivel,RAIZ,41,2025,'BR'))
        self.assertFalse(indisponivel.figuras)
        self.assertTrue(any('2025' in msg for msg in indisponivel.avisos))


if __name__=='__main__':
    unittest.main()
