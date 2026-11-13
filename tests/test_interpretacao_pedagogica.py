# -*- coding: utf-8 -*-
import unittest

from interpretacao_regras_enem import resumir_indicador


class InterpretacaoTestes(unittest.TestCase):
    def setUp(self):
        self.meta = {'titulo': 'Nota da redação', 'pergunta': 'Qual foi o desempenho médio?', 'pagina': 'overview'}
        self.serie = {'years': [
            {'ano': 2019, 'brasil': {'media': 600.0, 'n_validas': 200}, 'ufs': [{'uf': 'SP', 'media': 590, 'n_validas': 100}]},
            {'ano': 2024, 'brasil': {'media': 680.0, 'n_validas': 200}, 'ufs': [{'uf': 'SP', 'media': 670, 'n_validas': 100}]},
        ]}
        self.v2 = {'results': [
            {'ano': 2019, 'cluster': 'C1', 'media': 600, 'n': 100},
            {'ano': 2019, 'cluster': 'C2', 'media': 700, 'n': 100},
            {'ano': 2024, 'cluster': 'C1', 'media': 620, 'n': 100},
            {'ano': 2024, 'cluster': 'C2', 'media': 740, 'n': 100},
            {'ano': 2025, 'cluster': 'C1', 'status': 'nao_aplicavel'},
        ]}

    def test_ano_sem_filtro_compara_extremos(self):
        txt = resumir_indicador(55, self.v2, self.meta, None, 'BR')['texto']
        self.assertIn('2019 a 2024', txt)
        self.assertIn('100,00', txt)
        self.assertIn('120,00', txt)

    def test_filtro_ano_nao_mistura_edicoes(self):
        txt = resumir_indicador(55, self.v2, self.meta, 2024, 'BR')['texto']
        self.assertIn('2024',txt)
        self.assertNotIn('2019',txt)
        self.assertIn('740,00',txt)

    def test_sem_vinculo_socio_2025(self):
        txt = resumir_indicador(55, self.v2, self.meta, 2025, 'BR')['nota']
        self.assertIn('2025',txt)
        self.assertIn('não',txt)

    def test_uf_v2_nao_inventa_estadual(self):
        txt = resumir_indicador(55,self.v2,self.meta,None,'SP')['texto']
        self.assertIn('nacionais',txt)
        self.assertNotIn('740,00',txt)

    def test_generico_periodo_nao_mostra_ano_2024_como_historico(self):
        txt = resumir_indicador(9,{},self.meta,None,'BR',678.9)['texto']
        self.assertNotIn('678,90',txt)
        self.assertIn('mesma medida',txt)

    def test_nota_media_anual_e_historica(self):
        anual = resumir_indicador(2,self.serie,self.meta,2024,'BR')['texto']
        historico = resumir_indicador(2,self.serie,self.meta,None,'BR')['texto']
        self.assertIn('680,00',anual)
        self.assertNotIn('600,00',anual)
        self.assertIn('600,00',historico)
        self.assertIn('680,00',historico)

    def test_serie_por_uf_so_usa_uf(self):
        txt = resumir_indicador(2,self.serie,self.meta,None,'SP')['texto']
        self.assertIn('590,00',txt)
        self.assertNotIn('600,00',txt)

    def test_celula_menor_trinta_nao_gera_numero(self):
        doc={'results':[{'ano':2024,'cluster':'C3','competencia':'C5',
                         'n_com_competencia_valida':10,'n_com_desconto':9,'frequencia_desconto':0.9}]}
        txt = resumir_indicador(58,doc,self.meta,2024,'BR')['texto']
        self.assertIn('tamanho pequeno',txt)
        self.assertNotIn('90,0%',txt)

    def test_nota_ausente_nao_vira_zero(self):
        doc={'years':[{'ano':2024,'brasil':{'media':None,'n_validas':200}}]}
        txt=resumir_indicador(2,doc,self.meta,2024,'BR')['texto']
        self.assertNotIn('0,00 pontos',txt)

    def test_rubricas_e_limites(self):
        meta={'pagina':'competencies','pergunta':'Quais competências têm mais dificuldades?'}
        result=resumir_indicador(13,{},meta,2024,'BR')
        self.assertIn('competências',result['pedagogia'])
        self.assertIn('não',result['nota'])


if __name__=='__main__':unittest.main()
