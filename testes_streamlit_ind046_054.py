# -*- coding: utf-8 -*-
"""Testes offline para os IND-046..054 e extensão 980: python testes_streamlit_ind046_054.py.

Não exige Streamlit instalado e não precisa dos microdados reais.
"""
from __future__ import annotations
import importlib
from copy import deepcopy

p = importlib.import_module('painel_indicadores_046_054')
a = importlib.import_module('painel_visualizacoes_novas')

class FakeSt:
    def __init__(self):
        self.mensagens = []
        self.chaves = []
        self.figuras = []
    def __enter__(self): return self
    def __exit__(self, typ, val, tb): return False
    def _gravar(self, *args, **kwargs):
        self.mensagens.append(str(args))
        return self
    def __getattr__(self, method):
        if method in {'info', 'warning', 'caption', 'title', 'markdown', 'metric', 'dataframe', 'divider'}:
            return self._gravar
        if method in {'radio', 'selectbox'}:
            def selecionar(label, options, **kw):
                self.chaves.append(kw.get('key'))
                return list(options)[0]
            return selecionar
        if method == 'expander': return lambda *args, **kw: self
        if method == 'tabs': return lambda labels: [self for _ in labels]
        if method == 'columns':
            return lambda n: [self] * (n if isinstance(n, int) else len(n))
        raise AttributeError(method)
    def plot(self, fig, altura):
        assert fig is not None and altura >= 300
        self.figuras.append(fig)


def construir_dashboard(ano):
    categorias = [{'codigo_escola':'A', 'codigo_acesso': 'A', 'codigo_computador':'A',
                   'codigo_ocupacao':'A', 'codigo_faixa_moradores':'1', 'codigo_categoria':'1',
                   'descricao_categoria':'Grupo A', 'n_redacoes':1000,'media':800,
                   'mediana':800,'suprimido':False,
                   'competencias':{'C1': {'media':160,'mediana':160,'n_redacoes':1000}},
                   'medidas':{'C0':{'media':800,'mediana':800,'n_redacoes':1000},
                              'C1':{'media':160,'mediana':160,'n_redacoes':1000}}}]
    rec = {'n_pop_socio_valid': 1000, 'categories': categorias,
           'dimensoes': {'TP_SEXO': {'categories':categorias}},
           'comparacao_sim_menos_nao': {'C0': {'diferenca_medias_sim_menos_nao': 30}}}
    socio = {}
    for i in range(46,53):
        chave = p.CHAVES[i][1]
        if i == 49:
            nat = {'pai_ou_responsavel_masculino': rec, 'mae_ou_responsavel_feminino': rec}
        elif i == 52:
            nat = {'n_redacoes': 1000, 'metricas': {'TOTAL':{'media':800,'mediana':800}}}
        else:
            nat = rec
        socio[chave] = {'indicator_id':f'IND-{i:03d}', 'national':nat,
                       'states':{'SP':deepcopy(nat)}, 'source_variable':'Q020'}
    dim = {'eixo': 1,'autovalor': .3, 'inercia_pct': 15,
           'contribuicoes_variaveis_pct':{'Q001': 60, 'Q002': 40},
           'categorias':[{'variavel':'Q001','categoria':'A','frequencia':800,
                          'contribuicao_pct': 60,'coordenada': 1.5}]}
    mca = {'n_amostra':1500, 'n_variaveis_ativas': 23,
           'n_categorias_ativas':120, 'dimensoes':[dim]}
    km = {'n_amostra':1500, 'k_selecionado':2,
          'metricas_k_escolhido':{'silhouette':.33},
          'clusters':[{'cluster':'C1', 'n_amostra':1000,
                       'participacao_aprox_pct':65,
                       'perfil_exploratorio':[{'variavel':'Q001','categoria':'B',
                       'prevalencia_grupo_aprox_pct':60,'diferenca_aprox_pp':20}]},
                      {'cluster':'C2', 'n_amostra':500,
                       'participacao_aprox_pct':35, 'perfil_exploratorio':[]}],
          'diagnosticos_k':[{'k':2,'status':'avaliado','silhouette':.33}]}
    extra980 = {'n_980_total':200, 'resumo_competencias': [
        {'competencia':'C1','n_980_competencia':150,
         'percentual_entre_980_classificadas':75.0,'suprimido':False}],
        'percursos_avaliacao':[{'percurso':'AV1_AV2','n_redacoes':200,'suprimido':False}]}
    return {'pages':{
        'socioeconomic':socio,
        'ml':{'socio_mca': {'indicator_id':'IND-053','modelo_ano':mca,
                          'modelo_nucleo_conjunto':mca},
              'socio_clusters': {'indicator_id':'IND-054','modelo_ano':km,
                                 'modelo_nucleo_conjunto':km}},
        'high_performance':{'single_blocker':{
            'indicator_id':'IND-034',
            'recorte_980_nota_final_brasil': extra980,
            'national': {'n_casos_com_uma_unica_competencia':800,
                         'resumo_competencias':[{'competencia':'C1','n_competencia_unica':600}]}
        }}}}


def testar():
    dash = construir_dashboard(2024)
    assert all(p.modulo(dash, i)['indicator_id'] == f'IND-{i:03d}' for i in range(46, 55))
    assert p.recorte(dash, 49, 'SP').get('pai_ou_responsavel_masculino')
    assert p.recorte(dash, 51, 'BR')['dimensoes'].get('TP_SEXO')
    assert p.recorte(dash, 53, 'SP')['modelo_ano']
    assert not p.modulo({'pages':{'socioeconomic':{'internet_performance': {'indicator_id':'IND-048'}}}}, 47)
    assert p.recorte(dash, 46, 'AM') is None
    anos = {2024: dash, 2025:{'pages':{'socioeconomic':{'uf_performance': deepcopy(dash['pages']['socioeconomic']['uf_performance'])}}}}
    assert len(p.disponibilidade(anos)) == 2
    assert p.disponibilidade(anos)[1]['IND-047'] == 'Não integrado'
    for ano, uf in [(2024,'BR'), (2024,'SP'), (None,'BR'), (None,'SP'), (2025,'BR')]:
        st = FakeSt()
        p.pagina_indicadores_novos(st, st.plot, ano, uf, anos)
        assert st.mensagens, (ano, uf)
        if ano == 2024: assert st.figuras, (ano, uf)
    # Exercita os gráficos por indicador (os selectboxes não fazem alterações nos dados).
    for i in range(46,52):
        st = FakeSt()
        r = p.recorte(dash, i)
        mod = p.modulo(dash, i)
        if i == 46: p._mostrar_046(st, st.plot, r, mod)
        elif i in (47,48): p._mostrar_047_048(st, st.plot, r, mod, i)
        else: {49:p._mostrar_049, 50:p._mostrar_050, 51:p._mostrar_051}[i](st,st.plot,r,mod)
        assert st.figuras, i
    st = FakeSt()
    p._mostrar_052(st, st.plot, dash, 'SP')
    assert st.figuras
    st = FakeSt()
    p._mostrar_mca(st, st.plot, p.modulo(dash,53)['modelo_ano'], 'MCA')
    p._mostrar_clusters(st, st.plot, p.modulo(dash,54)['modelo_ano'], 'Clusters')
    assert len(st.figuras) >= 3
    st = FakeSt()
    a._mostrar_034(st, st.plot, dash['pages']['high_performance']['single_blocker']['national'],
                   dash['pages']['high_performance']['single_blocker'], 'SP')
    assert len(st.figuras) >= 2
    assert any('980' in x for x in st.mensagens)
    print('AUTOTESTES PAINEL IND-046..054 E IND-034/980: APROVADOS')

if __name__ == '__main__':
    testar()
