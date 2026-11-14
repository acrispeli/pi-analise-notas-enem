# -*- coding: utf-8 -*-
"""Visualizações contextualizadas do catálogo ENEM 68 (sem recálculo dos microdados).

Trabalha exclusivamente com agregações publicadas nos JSONs do projeto. Nunca
imputa anos, estados, métricas ou associações individuais ausentes. As séries
são descritivas, e a comparação de agrupamentos independentes é restringida.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from rotulos_marcadores_plotly import (rotular_marcadores,
                                       rotular_historico_competencias)

CORES_COMPETENCIAS = {
    'C1': '#2667A9', 'C2': '#D97706', 'C3': '#1F8A70',
    'C4': '#7C5DB5', 'C5': '#C44E52',
}

# Chave: indicador -> (campo preexistente, título, unidade)
SERIES = {
    1: ('n_validas', 'Redações válidas', 'redações'),
    2: ('media', 'Nota média da redação', 'pontos (0–1000)'),
    3: ('mediana', 'Mediana da redação', 'pontos (0–1000)'),
    4: ('desvio_padrao', 'Desvio-padrão da nota', 'pontos'),
    5: ('iqr', 'Intervalo interquartil da nota', 'pontos'),
    6: ('media', 'Nota média das redações válidas', 'pontos (0–1000)'),
    7: ('redacoes_status_1', 'Redações com status válido', 'redações'),
    8: ('percentual', 'Redações com nota 1000', '% das redações válidas'),
    9: ('competencias.media', 'Médias por competência', 'pontos (0–200)'),
    10: ('competencias.mediana', 'Medianas por competência', 'pontos (0–200)'),
    11: ('competencias.desvio_padrao', 'Dispersão das competências', 'pontos'),
    12: ('n_validas', 'Redações válidas (distribuição por nível no detalhe)', 'redações'),
    13: ('pares.spearman', 'Correlação de Spearman por par de competências', 'coeficiente (−1 a 1)'),
    14: ('componentes.percentual_explicado', 'Variância explicada por componente PCA', '%'),
    15: ('n_validas', 'Redações analisadas pela PCA', 'redações'),
    16: ('n_redacoes_exibidas', 'Redações nos hexágonos representados', 'redações'),
    17: ('k', 'Quantidade de grupos K-Means por edição', 'grupos'),
    18: ('n_validas', 'Redações atribuídas aos grupos', 'redações'),
    19: ('silhouette', 'Coeficiente Silhouette', 'coeficiente'),
    20: ('media', 'Divergência absoluta média AV1 × AV2', 'pontos'),
    21: ('competencias.media', 'Diferença absoluta média por competência', 'pontos'),
    22: ('percentual_discrepancia_confirmada_pop_evaluator', 'Discrepância confirmada segundo critério aplicado', '% da POP_EVALUATOR'),
    23: ('percentual_divergencia_pares_comparaveis', 'Divergência de situação entre os corretores', '% dos pares comparáveis'),
    24: ('percentual_com_av3', 'Registros com evidência de AV3', '% da POP_ALL'),
    25: ('percentual_com_av4', 'Registros com evidência de banca AV4', '% da POP_ALL'),
    26: ('competencias.kappa_ponderado_quadratico', 'Concordância por competência', 'Kappa quadrático'),
    27: ('icc_concordancia_absoluta', 'ICC de concordância absoluta AV1 × AV2', 'coeficiente'),
    28: ('k_efetivo', 'Número de grupos de divergência por edição', 'grupos'),
    29: ('percentual_sinalizados_auto', 'Avaliações atípicas na amostra', '% amostral'),
    30: ('percentual_high_sobre_validas', 'Redações com 900–1000 pontos', '% da POP_VALID'),
    31: ('n_near', 'Redações na faixa de análise 900–980', 'redações'),
    32: ('n_near', 'Redações na população 900–980', 'redações'),
    33: ('total_pontos_perdidos', 'Pontos perdidos nas redações 900–980', 'pontos (soma)'),
    34: ('percentual_casos_unicos_na_pop_near', 'Uma única competência com desconto', '% da POP_NEAR'),
    35: ('n_near', 'Redações consideradas nas combinações de descontos', 'redações'),
    36: ('n_near', 'Redações consideradas nas regras de associação', 'redações'),
    37: ('n_near', 'Redações na análise de concentração', 'redações'),
    38: ('n_near_evaluator', 'Redações com avaliações comparáveis', 'redações'),
    39: ('n_high', 'Redações com 900–1000 pontos', 'redações'),
}

ANUAL = {
    6: ('faixas','faixa','percentual','Distribuição das notas da redação','% da POP_VALID'),
    7: ('categorias','rotulo','percentual','Situação da redação','% dos registros'),
    9: ('competencias','competencia','media','Nota média por competência','pontos (0–200)'),
    10: ('competencias','competencia','mediana','Mediana por competência','pontos (0–200)'),
    11: ('competencias','competencia','desvio_padrao','Desvio-padrão por competência','pontos'),
    14: ('componentes','componente','percentual_explicado','Variância explicada pela PCA','%'),
    17: ('clusters','cluster_id','percentual_amostra','Distribuição dos perfis na amostra','% da amostra ML'),
    18: ('clusters','cluster_id','percentual','Redações atribuídas aos perfis','% da POP_VALID'),
    20: ('histograma','faixa','percentual','Divergência total AV1 × AV2 por faixa','% da POP_EVALUATOR'),
    21: ('competencias','competencia','media','Diferença absoluta média por competência','pontos'),
    26: ('competencias','competencia','kappa_ponderado_quadratico','Kappa por competência','coeficiente'),
    28: ('clusters','cluster_id','percentual_amostra','Perfis de divergência na amostra','% da amostra'),
    30: ('faixas','faixa','percentual','Redações com 900–1000 pontos por faixa','% da POP_HIGH'),
    31: ('resumo_competencias','competencia','media_perda','Pontos perdidos por competência em média','pontos'),
    32: ('resumo_competencias','competencia','percentual_desconto','Redações com desconto por competência','% da POP_NEAR'),
    33: ('resumo_competencias','competencia','percentual_participacao','Participação na perda total por competência','% dos pontos perdidos'),
    34: ('resumo_competencias','competencia','n_competencia_unica','Casos de competência única descontada','redações'),
    35: ('combinacoes','combinacao','percentual_pop_near','Combinações de competências com desconto','% da POP_NEAR'),
    38: ('competencias','competencia','concordancia_percentual','Concordância sobre desconto por competência','% dos pares comparáveis'),
}

METRICAS_TEMPORAIS = {
    64: [('media','Média da redação','pontos'),('mediana','Mediana da redação','pontos')],
    65: [('media','Média por competência','pontos (0–200)')],
    66: [('perda_media','Perda média','pontos'),('frequencia_desconto','Frequência de desconto','proporção [0,1]')],
    67: [('diferenca_media_absoluta','Divergência média AV1 × AV2','pontos'),('percentual_discrepancia_confirmada','Discrepância confirmada','%')],
    68: [('percentual_amostra','Participação de cada perfil material','% da amostra')],
    69: [('taxa_esquerda_pct','Correspondências na junção','% dos registros da fonte esquerda')],
}

AVISOS = {
    7:'O denominador inclui registros da fonte, não apenas redações válidas.',
    12:'Valores de nível são pontuações observadas de cada competência; a distribuição é diferente de uma média.',
    13:'Correlação não indica causalidade. Os coeficientes não devem ser interpretados como pontos de nota.',
    14:'A PCA é recalculada por recorte. Percentuais explicados podem ser comparados; o sinal e o significado detalhado dos eixos podem mudar.',
    15:'Os sinais dos vetores da PCA são arbitrários; compare as competências dentro de uma mesma edição, não os sinais entre anos.',
    16:'O mapa representa centros de hexágonos agregados, jamais redações individuais; é um resumo da projeção PCA deste recorte.',
    17:'P1…Pk são perfis calculados separadamente para cada recorte. Os rótulos não identificam um mesmo grupo entre anos.',
    18:'Os perfis são estimados por recorte; não presuma correspondência entre identificadores de edições diferentes.',
    19:'Métricas internas de agrupamento não demonstram a existência de um agrupamento único ou correto. A estabilidade não é garantida.',
    20:'O histograma tem faixas de larguras diferentes. As alturas indicam porcentagem de avaliações, não densidade.',
    22:'Critério de 2024 aplicado às edições para comparabilidade; não é uma taxa oficial retrospectiva do INEP. Motivos de discrepância podem se sobrepor.',
    23:'A divergência de status é uma medida diferente da diferença de notas.',
    24:'Presença de nota ou status AV3 é uma evidência indireta de terceira correção, não o registro administrativo de convocação.',
    25:'AV4 representa banca colegiada, não um quarto avaliador individual.',
    26:'Kappa ponderado quadrático mede concordância. Valores podem ser negativos; não são percentuais.',
    27:'ICC mede concordância absoluta, não a quantidade de pontos de diferença.',
    28:'Os agrupamentos foram obtidos por amostras independentes; nomes P1…Pk não formam trajetórias individuais ou grupos fixos.',
    29:'Sinalização por Isolation Forest é exploratória: atípico não significa erro ou fraude. Limiares podem variar.',
    30:'O percentual de alto desempenho usa POP_VALID; a distribuição entre faixas usa POP_HIGH. São denominadores diferentes.',
    31:'Desconto = 200 menos a nota da competência; POP_NEAR considera redações na faixa indicada pelo indicador.',
    32:'Uma redação pode receber descontos em várias competências; percentuais não devem ser somados.',
    33:'Participações indicam fatias do total de pontos perdidos, não percentuais de redações.',
    35:'Interseções inclusivas: uma redação pode entrar em várias combinações. Não somar as barras.',
    36:'Suporte, confiança e lift são medidas de regras associativas; não implicam causalidade.',
    37:'Os testes estatísticos avaliam distribuições e concordância de descontos; significância não implica causalidade.',
    38:'A concordância apresentada é entre os primeiros avaliadores sobre a presença de desconto.',
    39:'As faixas do eixo vertical são notas totais; as colunas representam as cinco competências.',
}

COMPETENCIAS = {
    'C1':'Domínio da modalidade escrita formal da língua portuguesa',
    'C2':'Compreensão da proposta e aplicação de conceitos de várias áreas',
    'C3':'Seleção, relação e organização de argumentos',
    'C4':'Mecanismos linguísticos de coesão e argumentação',
    'C5':'Proposta de intervenção respeitando os direitos humanos',
}


def _numerico(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def _titular(ind):
    return f'IND-{ind:03d}'


def _recorte_ano(d:dict, ind:int, uf:str):
    """[(ano,reg)] com UF verificada na mesma fonte, sem fallback nacional."""
    anos=d.get('years')
    if isinstance(anos,dict):
        it=[(int(k),v) for k,v in anos.items() if str(k).isdigit() and isinstance(v,dict)]
    elif isinstance(anos,list):
        it=[(int(y['ano']),y) for y in anos if isinstance(y,dict) and str(y.get('ano','')).isdigit()]
    else:
        return []
    saida=[]
    for a,item in sorted(it):
        if isinstance(item.get('recortes'),dict):
            rec=item['recortes'].get(uf)
        elif uf=='BR':
            rec=item.get('brasil') or item.get('national')
        else:
            items=item.get('ufs')
            rec=(next((v for v in items if isinstance(v,dict) and v.get('uf')==uf),None)
                 if isinstance(items,list) else None)
        if isinstance(rec,dict) and not rec.get('suprimido'):
            saida.append((a,rec))
    return saida


def _pontos_series(ind:int, anos:list[tuple[int,dict]]):
    cfg=SERIES.get(ind)
    if not cfg:return [],''
    path,label,unidade=cfg
    tabela=[]
    if path.startswith('competencias.') or path.startswith('pares.') or path.startswith('componentes.'):
        bucket,metric=path.split('.')
        for ano,rec in anos:
            for r in (rec.get(bucket,{}).items() if isinstance(rec.get(bucket),dict) else rec.get(bucket,[])):
                if isinstance(r,tuple) and len(r)==2 and isinstance(r[1],dict):
                    r={'competencia':r[0],**r[1]}
                if not isinstance(r,dict):continue
                eixo=r.get('competencia') or r.get('componente')
                if bucket=='pares':eixo=f"{r.get('competencia_a')} × {r.get('competencia_b')}"
                if eixo and _numerico(r.get(metric)):
                    tabela.append({'Ano':str(ano),'Série':eixo,'Valor':r[metric]})
    else:
        for ano,rec in anos:
            if _numerico(rec.get(path)):
                tabela.append({'Ano':str(ano),'Valor':rec[path]})
    return tabela,f'{label} · {unidade}'


def _tracar(st,fig,titulo:str,unidade:str,altura=390):
    # Rótulos específicos podem ter reservado uma margem maior antes
    # desta função; não reduzi-la (IND-006 e IND-009).
    topo_reservado = (getattr(fig.layout.margin, 't', None) or 0)
    fig.update_layout(title=titulo,height=altura,
                      margin=dict(l=25,r=25,t=max(65, topo_reservado),b=55),
                      legend_title_text='Série',yaxis_title=unidade)
    # Rótulos fixos apenas em séries de linha curtas; gráficos densos
    # mantêm hover para evitar a sobreposição de dezenas de números.
    rotular_marcadores(fig, casas=None)
    st.plotly_chart(fig,use_container_width=True)


def _historico(st,ind,anos):
    pts,etiqueta=_pontos_series(ind,anos)
    if len(set(p['Ano'] for p in pts))<2:
        st.info('Não há pelo menos duas edições válidas para comparação histórica desta medida.')
        return False
    df=pd.DataFrame(pts)
    unidade=etiqueta.split(' · ')[-1]
    if 'Série' in df and df['Série'].nunique()>1:
        df['Série']=df['Série'].map(lambda x: f'{x} · {COMPETENCIAS[x][:34]}' if x in COMPETENCIAS else x)
        opcoes=list(df['Série'].dropna().unique())
        # Evitar dezenas de linhas para os 10 pares de correlação
        if len(opcoes)>5:
            selecao=st.selectbox('Par ou componente para evolução',opcoes,key=f'hist_ind{ind:03d}_serie')
            df=df.loc[df['Série']==selecao]
        fig=px.line(df,x='Ano',y='Valor',color='Série',markers=True,
                    color_discrete_map={k + ' · ' + v[:34]: CORES_COMPETENCIAS[k]
                                        for k,v in COMPETENCIAS.items()})
    else:
        fig=px.line(df,x='Ano',y='Valor',markers=True)
    if ind == 9:
        # C1–C5: 35 anotações pequenas, deslocadas para evitar colisões.
        rotular_historico_competencias(fig, casas=1)
    _tracar(st,fig,'Evolução histórica · '+etiqueta,unidade,
            altura=520 if ind == 9 else 390)
    if ind in (14,15,16,17,18,28,29):
        st.caption(AVISOS.get(ind,''))
    return True


def _selecionar_ano(st,ind,ano,anos):
    disp=[a for a,_ in anos]
    if not disp:return None
    if ano is not None:return int(ano) if int(ano) in disp else None
    return st.selectbox('Edição para visualizar os detalhes',disp,index=len(disp)-1,
                        key=f'geral_ind{ind:03d}_ano')


def _tabela_dados(st,lista,nome='Tabela de dados'):
    if not lista:return
    df=pd.DataFrame(lista)
    simples=[k for k in df.columns if df[k].map(lambda v:not isinstance(v,(dict,list,set))).all()]
    if simples:
        with st.expander(nome):
            st.dataframe(df[simples].head(200),hide_index=True,use_container_width=True)


def _mapa_centroides(st, ind: int, rec: dict) -> bool:
    """Mostra o PERFIL dos grupos, sem confundir percentual amostral e média."""
    clusters = rec.get('clusters', [])
    if not isinstance(clusters, list) or not clusters:
        return False
    registros = []
    for c in clusters:
        if not isinstance(c, dict):
            continue
        ident = str(c.get('cluster_id', c.get('cluster', '?')))
        centros = (c.get('centro_competencias', []) if ind == 17
                   else c.get('centro_por_competencia', []))
        chave = 'nota_media_centro' if ind == 17 else 'diferenca_media_pontos'
        if isinstance(centros, list) and centros:
            for row in centros:
                if isinstance(row, dict) and row.get('competencia') in COMPETENCIAS and _numerico(row.get(chave)):
                    registros.append({'Grupo': ident, 'Competência': row['competencia'],
                                      'Pontos': float(row[chave])})
        else:
            valores = c.get('centro_pontos' if ind == 17 else 'centro_divergencias_pontos', [])
            for competencia, valor in zip(COMPETENCIAS, valores):
                if _numerico(valor):
                    registros.append({'Grupo': ident, 'Competência': competencia, 'Pontos': float(valor)})
    if not registros:
        return False
    df = pd.DataFrame(registros)
    grade = df.pivot_table(index='Grupo', columns='Competência', values='Pontos', aggfunc='first')
    grade = grade.reindex(sorted(grade.index), axis=0).reindex(list(COMPETENCIAS), axis=1)
    if grade.isna().all(axis=None):
        return False
    titulo = ('Notas médias dos centróides de cada perfil' if ind == 17
              else 'Diferença absoluta média AV1 × AV2 nos centróides')
    fig = px.imshow(grade, text_auto='.1f', aspect='auto', zmin=0,
                    zmax=200 if ind == 17 else None, color_continuous_scale='Blues',
                    labels={'x':'Competência','y':'Perfil de agrupamento','color':'Pontos'})
    _tracar(st, fig, titulo, 'Perfil', altura=max(360, 135 + 58 * len(grade)))
    st.caption(('Cada célula é a pontuação média no centro do grupo (escala 0–200); '
                'não representa a nota de todos os integrantes.' if ind == 17 else
                'Cada célula representa a divergência absoluta média no centro do grupo, '
                'em pontos. Valores maiores não demonstram erro ou viés de avaliadores.') +
               ' P1, P2 etc. são identificadores definidos no recorte e não equivalem automaticamente entre edições.')
    tamanhos = pd.DataFrame([{'Grupo': c.get('cluster_id', '?'),
                              'Participação (%)': c.get('percentual_amostra'),
                              'N da amostra': c.get('n_amostra')}
                             for c in clusters if isinstance(c, dict)])
    tamanhos = tamanhos.dropna(subset=['Participação (%)'])
    if not tamanhos.empty:
        with st.expander('Participação e tamanho dos grupos na amostra'):
            chart = px.bar(tamanhos, x='Grupo', y='Participação (%)', hover_data=['N da amostra'],
                           title='Representatividade amostral de cada grupo')
            _tracar(st, chart, 'Participação dos perfis', '% da amostra')
            st.dataframe(tamanhos, hide_index=True, use_container_width=True)
    return True


def _quartis_por_competencia(st, ind: int, rec: dict) -> bool:
    """Intervalos Q1–Q3 de agregados, sem fabricar observações individuais."""
    rows = rec.get('competencias', [])
    if not isinstance(rows, list):
        return False
    d=[]
    for r in rows:
        if not isinstance(r,dict):
            continue
        comp=r.get('competencia')
        q1=r.get('p25',r.get('q1'))
        q3=r.get('p75',r.get('q3'))
        med=r.get('mediana',r.get('mediana_controle'))
        media=r.get('media',r.get('media_controle'))
        if comp in COMPETENCIAS and all(_numerico(v) for v in (q1,q3,med)) and q1<=q3:
            d.append({'competencia':comp,'Q1':float(q1),'Q3':float(q3),
                      'Mediana':float(med),'Média':float(media) if _numerico(media) else None})
    if not d:
        return False
    fig=go.Figure()
    for r in d:
        fig.add_trace(go.Scatter(x=[r['Q1'],r['Q3']], y=[r['competencia']]*2,
                      mode='lines', line={'color':CORES_COMPETENCIAS[r['competencia']], 'width':12},
                      showlegend=False, hovertemplate=f"{r['competencia']} · Q1–Q3: {r['Q1']:.1f}–{r['Q3']:.1f} pontos<extra></extra>"))
    fig.add_trace(go.Scatter(x=[r['Mediana'] for r in d],y=[r['competencia'] for r in d],
                     mode='markers',name='Mediana',marker={'symbol':'diamond','color':'#151515','size':10},
                     hovertemplate='Mediana: %{x:.1f} pontos<extra></extra>'))
    if any(r['Média'] is not None for r in d):
        fig.add_trace(go.Scatter(x=[r['Média'] for r in d],y=[r['competencia'] for r in d],
                     mode='markers',name='Média',marker={'symbol':'circle-open','color':'#151515','size':12},
                     hovertemplate='Média: %{x:.1f} pontos<extra></extra>'))
    fig.update_xaxes(title_text='Pontos (0–200)',range=[0,200])
    fig.update_layout(yaxis={'categoryorder':'array','categoryarray':['C5','C4','C3','C2','C1']})
    _tracar(st,fig,'Faixa interquartil (Q1–Q3), mediana e média das competências','Competência',altura=420)
    st.caption('As faixas indicam do primeiro ao terceiro quartil; os símbolos representam mediana e média. '
               'São estatísticas agregadas, não um boxplot construído a partir de redações individuais.')
    _tabela_dados(st, d, 'Tabela de quartis e medidas de tendência central')
    return True


def renderizar_variante_980(st, doc: dict, ano: int | None, uf: str) -> bool:
    """IND-034 complementar: entre redações com 980, competência que ficou com 180."""
    if uf != 'BR':
        st.info('A variante complementar 980 não declara recorte por UF. Selecione Brasil.')
        return True
    years = doc.get('years', {})
    if not isinstance(years,dict):
        st.error('Estrutura da variante 980 não reconhecida.')
        return True
    disponiveis = sorted(int(k) for k in years if str(k).isdigit())
    if not disponiveis:
        st.info('Não há edições disponíveis na variante 980.')
        return True
    hist=[{'Edição':str(y),'Redações com 980 pontos':years[str(y)].get('n_980_total')}
          for y in disponiveis if _numerico(years[str(y)].get('n_980_total'))]
    st.markdown('#### Complemento do IND-034 — redações com exatamente 980 pontos')
    st.caption('Uma redação com nota 980 pode ter 200 pontos em quatro competências e 180 em uma. '
               'O gráfico mostra em qual competência ocorreu esse desconto de 20 pontos, na população classificada.')
    if len(hist)>1:
        with st.expander('Histórico de redações com 980 pontos'):
            f=px.line(pd.DataFrame(hist),x='Edição',y='Redações com 980 pontos',markers=True)
            _tracar(st,f,'Redações com 980 pontos em cada edição','redações')
    escolhido=ano if ano is not None else st.selectbox('Edição do recorte 980',disponiveis,
                                      index=disponiveis.index(2024) if 2024 in disponiveis else len(disponiveis)-1,
                                      key='ind034_980_ano')
    if escolhido not in disponiveis:
        st.info(f'A variante não contém dados para {escolhido}.')
        return True
    rec=years[str(escolhido)]
    dados=pd.DataFrame(rec.get('resumo_competencias',[]))
    col='percentual_entre_980_classificadas'
    if not {'competencia',col,'n_980_competencia'}.issubset(dados.columns):
        st.info('Dados de competência incompletos nesta edição.')
        return True
    dados=dados.copy().dropna(subset=[col]);dados['competencia']=dados['competencia'].astype(str)
    fig=px.bar(dados,x='competencia',y=col,color='competencia',
               color_discrete_map=CORES_COMPETENCIAS, text_auto='.1f',
               hover_data={'n_980_competencia':True},
               labels={'competencia':'Competência com 180 pontos',col:'% entre as redações de 980 classificadas'})
    fig.update_layout(showlegend=False)
    _tracar(st,fig,f'Competência com desconto de 20 pontos · ENEM {escolhido}',
            '% das redações com 980 classificadas')
    st.metric('Redações com 980 pontos', f"{int(rec.get('n_980_total',0)):,}".replace(',','.'))
    st.caption('Denominador: redações de 980 pontos classificadas com quatro competências em 200 e uma em 180. '
               'Uma barra mais alta não identifica a causa do desconto nem uma dificuldade individual.')
    _tabela_dados(st,dados.to_dict('records'),'Tabela do recorte 980')
    return True


def _anual_basico(st,ind,rec):
    cfg=ANUAL.get(ind)
    if ind in (17,28) and _mapa_centroides(st, ind, rec):
        return True
    if ind in (11,21) and _quartis_por_competencia(st,ind,rec):
        if ind == 11:
            st.caption('O desvio-padrão complementa o intervalo Q1–Q3; a diferença entre essas métricas é explicada na tabela.')
        else:
            st.caption('AV1 × AV2: os quartis representam diferenças absolutas entre as duas avaliações por competência.')
        return True
    if ind==12:
        comp=st.selectbox('Competência para distribuição de níveis',list(COMPETENCIAS),key='ind012_comp')
        row=next((x for x in rec.get('competencias',[]) if x.get('competencia')==comp),{})
        dados=row.get('niveis',[])
        cfg=('niveis','pontuacao','percentual','Notas observadas da '+comp,'% de redações válidas')
        rec={'niveis':dados}
    if ind==13:
        labels=rec.get('labels',[])
        matriz=rec.get('spearman')
        if labels and isinstance(matriz,list) and len(labels)==len(matriz):
            fig=px.imshow(pd.DataFrame(matriz,index=labels,columns=labels),zmin=-1,zmax=1,
                          color_continuous_scale='RdBu',text_auto='.2f',title='Correlação de Spearman entre competências')
            _tracar(st,fig,'Correlação de Spearman','coeficiente')
            st.caption('C1–C5: '+ ' · '.join(f'{k}: {v}' for k,v in COMPETENCIAS.items()))
            return True
    if ind==15:
        matriz=rec.get('loadings')
        if isinstance(matriz,list) and len(matriz)==5 and len(matriz[0])==5:
            df=pd.DataFrame(matriz,index=list(COMPETENCIAS),columns=[f'PC{i}' for i in range(1,6)])
            fig=px.imshow(df,zmin=-1,zmax=1,color_continuous_scale='RdBu',text_auto='.2f')
            _tracar(st,fig,'Coeficientes das competências nas componentes principais','peso PCA')
            return True
    if ind==16:
        pontos=rec.get('pontos',[])
        if pontos:
            df=pd.DataFrame(pontos)
            df=df[pd.to_numeric(df.get('quantidade'),errors='coerce')>0]
            if not df.empty:
                fig=px.scatter(df,x='pc1',y='pc2',size='quantidade',color='quantidade',
                               hover_data={'quantidade':True},size_max=40,
                               labels={'pc1':'PC1 (coordenada padronizada)','pc2':'PC2 (coordenada padronizada)',
                                       'quantidade':'Redações no hexágono'})
                _tracar(st,fig,'Centros de hexágonos agregados · PC1 × PC2','PC2')
                st.caption('A visualização mostra o centro e a massa de cada hexágono agregado, não as observações individuais.')
                return True
    if ind==19:
        comparacao=rec.get('comparacao_k',{})
        dados=comparacao.get('candidatos',[]) if isinstance(comparacao,dict) else comparacao
        if dados:
            df=pd.DataFrame(dados)
            col=next((k for k in ('silhouette','silhouette_score','davies_bouldin') if k in df),None)
            kcol=next((k for k in ('k','n_clusters') if k in df),None)
            if col and kcol:
                fig=px.line(df,x=kcol,y=col,markers=True)
                _tracar(st,fig,'Qualidade interna por quantidade de grupos',col)
                _tabela_dados(st,dados)
                return True
    if ind==22:
        rows=[('Confirmada','n_discrepancia_confirmada'),('Sem discrepância confirmada','n_sem_discrepancia_confirmada'),('Indeterminada','n_indeterminada')]
        dados=[{'Classificação':a,'Quantidade':rec[b]} for a,b in rows if _numerico(rec.get(b))]
        if dados:
            fig=px.bar(pd.DataFrame(dados),x='Classificação',y='Quantidade')
            _tracar(st,fig,'Classificação da discrepância entre avaliadores','avaliações')
            st.caption('As três classes são categorias de resultado; os motivos de discrepância se sobrepõem e não são classes disjuntas.')
            return True
    if ind==23:
        rows=[('Status iguais',rec.get('n_status_iguais')),('Status divergentes',rec.get('n_status_divergentes'))]
        dados=[{'Situação':a,'Quantidade':b} for a,b in rows if _numerico(b)]
        if dados:
            fig=px.bar(pd.DataFrame(dados),x='Situação',y='Quantidade')
            _tracar(st,fig,'Comparação de situação entre AV1 e AV2','pares de avaliações')
            return True
    if ind==26:
        competencias=rec.get('competencias',{})
        if isinstance(competencias,dict) and competencias:
            rows=[{'Competência':c,'Kappa quadrático':r.get('kappa_ponderado_quadratico'),
                   'N pares':r.get('n_pares_validos')} for c,r in competencias.items()
                  if isinstance(r,dict) and _numerico(r.get('kappa_ponderado_quadratico'))]
            if rows:
                fig=px.bar(pd.DataFrame(rows),x='Competência',y='Kappa quadrático',
                           hover_data=['N pares'])
                _tracar(st,fig,'Concordância entre avaliadores por competência','Kappa ponderado')
                return True
    if ind==29:
        dados=rec.get('sensibilidade_limites',[])
        if dados:
            df=pd.DataFrame([x for x in dados if isinstance(x,dict) and not x.get('suprimido')])
            if {'limiar_escore','percentual_amostra'}.issubset(df.columns):
                fig=px.line(df,x='limiar_escore',y='percentual_amostra',markers=True,
                            labels={'limiar_escore':'Limiar do escore','percentual_amostra':'Amostra sinalizada (%)'})
                _tracar(st,fig,'Sensibilidade da sinalização ao limiar','% da amostra')
                return True
    if ind==36:
        regras=rec.get('rules',[])
        if regras:
            df=pd.DataFrame(regras)
            df=df.dropna(subset=['lift','confianca_percentual','suporte_percentual'])
            if not df.empty:
                df['Regra']=[f"{'+'.join(v)} → {'+'.join(t)}" for v,t in zip(df['antecedente'],df['consequente'])]
                fig=px.scatter(df,x='confianca_percentual',y='lift',size='n_ambos',
                               hover_name='Regra',color='suporte_percentual',size_max=28,
                               labels={'confianca_percentual':'Confiança (%)','lift':'Lift',
                                       'suporte_percentual':'Suporte (%)'})
                fig.add_hline(y=1,line_dash='dash')
                _tracar(st,fig,'Regras de associação entre descontos','lift')
                _tabela_dados(st,regras)
                return True
    if ind==37:
        testes=rec.get('tests',{})
        ocorrencia=testes.get('ocorrencia',{}) if isinstance(testes,dict) else {}
        magnitude=testes.get('magnitude',{}) if isinstance(testes,dict) else {}
        if ocorrencia and magnitude:
            p1=ocorrencia.get('p_valor')
            p2=magnitude.get('p_valor')
            w=magnitude.get('kendall_w')
            resultados=[]
            if _numerico(p1): resultados.append('Q de Cochran · p ' + ('<0,001' if p1 < 0.001 else f'= {p1:.3g}'))
            if _numerico(p2): resultados.append('Friedman · p ' + ('<0,001' if p2 < 0.001 else f'= {p2:.3g}'))
            if _numerico(w): resultados.append(f'W de Kendall = {w:.3f}')
            if resultados:
                st.caption(' | '.join(resultados))
            st.caption('Q de Cochran compara frequências de desconto; Friedman compara magnitudes; '
                       'W de Kendall resume o tamanho de efeito. Um p-valor muito pequeno não descreve a magnitude '
                       'nem demonstra relação causal.')
        linhas=ocorrencia.get('frequencias_por_competencia',[])
        if linhas:
            df=pd.DataFrame([r for r in linhas if isinstance(r,dict) and not r.get('suprimido')])
            if {'competencia','percentual'}.issubset(df.columns) and not df.empty:
                fig=px.bar(df,x='competencia',y='percentual')
                _tracar(st,fig,'Ocorrência de descontos por competência','% da POP_NEAR')
                with st.expander('Resultados dos testes pareados'):
                    st.json(testes,expanded=False)
                return True
    if ind==37:
        tests=rec.get('tests',{})
        if tests:
            st.caption('Testes estatísticos registrados no JSON da edição selecionada:')
            st.json(tests,expanded=False)
            return True
    if ind==39:
        faixas=rec.get('faixas',[])
        registros=[]
        for row in faixas:
            for c in row.get('competencias',[]):
                if _numerico(c.get('percentual_com_desconto')):
                    registros.append({'Faixa':row.get('faixa'),'Competência':c.get('competencia'),
                                      'Percentual':c.get('percentual_com_desconto')})
        if registros:
            df=pd.DataFrame(registros)
            piv=df.pivot(index='Faixa',columns='Competência',values='Percentual')
            fig=px.imshow(piv,zmin=0,zmax=100,text_auto='.1f',
                          labels={'color':'Redações com desconto (%)'})
            _tracar(st,fig,'Frequência de desconto por faixa da nota final','% das redações na faixa')
            return True
    if not cfg:return False
    campo,x,y,titulo,unidade=cfg
    dados=rec.get(campo,[])
    if not isinstance(dados,list) or not dados:return False
    df=pd.DataFrame([r for r in dados if isinstance(r,dict) and not r.get('suprimido')])
    if not {x,y}.issubset(df.columns):return False
    df[y]=pd.to_numeric(df[y],errors='coerce')
    df=df.dropna(subset=[y,x]).copy()
    if df.empty:return False
    if ind==35 and 'tipo' in df:
        tipo=st.selectbox('Tipo de combinação',['par','trio'],key='geral_ind035_tipo')
        df=df.loc[df['tipo']==tipo]
    if df.empty:
        st.info('Não há valores exibíveis neste recorte.'); return True
    df[x]=df[x].astype(str)
    if x == 'competencia':
        fig=px.bar(df.head(60),x=x,y=y,color=x,color_discrete_map=CORES_COMPETENCIAS)
        fig.update_layout(showlegend=False)
    else:
        fig=px.bar(df.head(60),x=x,y=y)
    if x in ('competencia','cluster_id'):
        fig.update_xaxes(categoryorder='array',categoryarray=sorted(df[x].unique()))
    if ind == 6:
        # O histograma possui dez faixas fixas: habilitar rótulos para
        # todas elas, sem ampliar o limite dos demais indicadores.
        from visualizacao_final_enem import _rotular_barras_compactas
        _rotular_barras_compactas(fig, limite_vertical=10)
    _tracar(st,fig,titulo,unidade,altura=410 if len(df)<15 else 480)
    if ind == 20:
        st.caption('As faixas possuem larguras diferentes: cada barra representa o percentual de pares na sua própria faixa, não uma densidade por ponto.')
    if x=='competencia':
        with st.expander('O que significa cada competência?'):
            for k,v in COMPETENCIAS.items():st.markdown(f'**{k}:** {v}')
    _tabela_dados(st,dados)
    return True


def _tabela_tecnica(st,ind,rec):
    fields=[(k,v) for k,v in rec.items() if _numerico(v) and ('n_' in k or 'percentual' in k or k in {'media','mediana','k'})]
    if fields:
        with st.expander('Denominadores e medidas complementares'):
            st.dataframe(pd.DataFrame([{'Campo do JSON':k,'Valor informado':v} for k,v in fields[:22]]),
                         use_container_width=True,hide_index=True)


def _mostrar_ano(st,ind,ano,rec):
    st.markdown(f'#### Detalhamento por edição · {ano}')
    feito=_anual_basico(st,ind,rec)
    if not feito:
        path,label,unidade=SERIES.get(ind,('','',''))
        if path and '.' not in path and _numerico(rec.get(path)):
            st.metric(label,f'{rec[path]:,.2f}'.replace(',','X').replace('.',',').replace('X','.'))
        else:
            st.info('Não há uma série categórica segura para este indicador; consulte o detalhamento técnico.')
    _tabela_tecnica(st,ind,rec)
    if ind in AVISOS:st.caption(AVISOS[ind])


def renderizar_historico_geral(st,raiz:Path,doc:dict,ind:int,ano:int|None,uf:str)->bool:
    if ind not in SERIES:return False
    anos=_recorte_ano(doc,ind,uf)
    if not anos:
        st.info(f'O IND-{ind:03d} não contém resultados disponíveis para {uf} neste conjunto de dados.')
        return True
    disponiveis=[a for a,_ in anos]
    if ano is not None and ano not in disponiveis:
        st.info(f'O IND-{ind:03d} não possui dados válidos para {ano} / {uf}.')
        return True
    if ano is None:
        st.markdown('#### Comparação histórica · anos disponíveis')
        _historico(st,ind,anos)
    elif len(anos)>1:
        with st.expander('Comparar todos os anos (2019–2025)',expanded=False):
            _historico(st,ind,anos)
    escolhido=_selecionar_ano(st,ind,ano,anos)
    if escolhido is not None:
        rec=dict(anos)[escolhido]
        _mostrar_ano(st,ind,escolhido,rec)
    st.caption('UF refere-se ao local de aplicação da prova. A série soma participações por edição, não acompanha as mesmas pessoas. '
               'Não foram estimados anos ou recortes faltantes.')
    return True


def _linhas_results(doc):
    return [x for x in doc.get('results',[]) if isinstance(x,dict) and x.get('status') not in ('nao_aplicavel','indisponivel')]


def renderizar_resultados_gerais(st,doc:dict,ind:int,ano:int|None,uf:str)->bool:
    """IND-064..072: seleção exata de linhas; não cria recortes estaduais."""
    if ind not in range(64,73):return False
    if uf != 'BR':
        st.info('Este módulo contém agregações nacionais, sem distribuição por UF. Selecione Brasil.')
        return True
    dados=_linhas_results(doc)
    if not dados:
        st.info('Não há resultados disponíveis para este indicador.');return True
    df=pd.DataFrame(dados)
    if ind==72:
        if 'tamanho_bytes' in df:
            topo=df.nlargest(20,'tamanho_bytes').copy()
            topo['Tamanho (MB)']=topo['tamanho_bytes']/1_000_000
            topo['Arquivo'] = topo['arquivo'].map(lambda x: Path(str(x)).name)
            fig=px.bar(topo,x='Tamanho (MB)',y='Arquivo',orientation='h',
                       labels={'arquivo':'Arquivo de origem'},title='20 maiores arquivos da proveniência')
            fig.update_yaxes(categoryorder='total ascending')
            _tracar(st,fig,'Arquivos por tamanho','MB')
        with st.expander('Inventário de arquivos e verificações SHA-256'):
            st.dataframe(df,hide_index=True,use_container_width=True)
        st.caption('Os hashes verificam versões dos arquivos, não representam notas ou resultados educacionais.')
        return True
    if ind==71:
        if 'celulas_positivas_1_a_29' in df:
            sub=df.loc[pd.to_numeric(df['celulas_positivas_1_a_29'],errors='coerce')>=0].copy()
            if not sub.empty:
                sub['Indicador']=sub['indicador_origem'].astype(str)
                fig=px.bar(sub,x='Indicador',y='celulas_positivas_1_a_29',
                           labels={'celulas_positivas_1_a_29':'Células com 1–29 registros'})
                _tracar(st,fig,'Diagnóstico de células pequenas por fonte','número de células')
        _tabela_dados(st,dados,'Diagnóstico por fonte')
        st.caption('São contagens de células na auditoria, não contagens de candidatos. Não constitui identificação individual.')
        return True
    if 'ano' in df:
        df['ano']=pd.to_numeric(df['ano'],errors='coerce')
        df=df.dropna(subset=['ano']).copy()
    if ano is not None and not df.empty and 'ano' in df and ano not in df['ano'].values:
        st.info(f'Sem resultados para a edição {ano}.');return True
    if ind==70:
        fontes=sorted(set(str(x) for x in df['fonte'].dropna()))
        escolhida=st.selectbox('Fonte de dados analisada',fontes,key='geral_ind070_fonte')
        df=df.loc[df['fonte'].astype(str)==escolhida].copy()
        variables=sorted(set(str(x) for x in df['variavel'].dropna()))
        if not variables:
            st.info('Sem variáveis disponíveis para esta fonte.');return True
        variavel=st.selectbox('Variável para comparar valores ausentes',variables,key='geral_ind070_variavel')
        df=df.loc[df['variavel'].astype(str)==variavel].copy()
        if df.empty:
            st.info('Sem valores para a combinação solicitada.');return True
        fig=px.line(df,x='ano',y='percentual_ausente',markers=True,
                    labels={'ano':'Edição ENEM','percentual_ausente':'Ausentes (%)'})
        _tracar(st,fig,f'Ausência de {variavel} · {escolhida}','% de registros da fonte')
        _tabela_dados(st,df.to_dict('records'),'Detalhamento dos valores ausentes')
        st.caption('A comparação mantém a mesma variável e a mesma fonte; mudanças de disponibilidade e significado entre edições exigem cautela.')
        return True
    if ind==68:
        # O visual principal de 068 é mantido no módulo de perfis V2 já aprovado.
        return False
    if ind in METRICAS_TEMPORAIS:
        campos=METRICAS_TEMPORAIS[ind]
        fonte=df.copy()  # A comparação mostra todos os anos; o recorte selecionado é destacado no texto.
        serie='competencia' if 'competencia' in fonte else 'cluster_referencia' if 'cluster_referencia' in fonte else None
        if ind==66 and 'frequencia_desconto' in fonte:
            fonte['frequencia_desconto']=pd.to_numeric(fonte['frequencia_desconto'],errors='coerce')*100
            campos=[('perda_media','Perda média por competência','pontos'),('frequencia_desconto','Frequência de desconto','%')]
        escolha=st.selectbox('Medida exibida',list(range(len(campos))),
                              format_func=lambda i:campos[i][1],key=f'geral_ind{ind:03d}_metrica') if len(campos)>1 else 0
        nome,label,unidade=campos[escolha]
        if nome not in fonte or fonte.empty:
            st.info('Medida não disponível para este recorte.');return True
        if serie and ind in (65,66):
            fig=px.line(fonte,x='ano',y=nome,color=serie,markers=True)
        else:
            fig=px.line(fonte,x='ano',y=nome,markers=True)
        _tracar(st,fig,label,unidade)
        if ind==69:st.caption('A taxa refere-se à fonte esquerda declarada no JSON. Percentual elevado não substitui a verificação de chaves ausentes, duplicadas e não vinculáveis.')
        if ind in (64,65,66,67):st.caption('Série de edições independentes do ENEM; as diferenças não demonstram causalidade. Denominadores variam por indicador.')
        if ano is not None and 'ano' in fonte:
            ed=fonte.loc[fonte['ano']==ano].copy()
            if not ed.empty:
                st.caption(f'Edição selecionada: {ano}. O gráfico preserva as demais edições para comparação.')
                _tabela_dados(st,ed.to_dict('records'),'Dados da edição selecionada')
        _tabela_dados(st,fonte.to_dict('records'))
        return True
    return False


def ler_dicionario_questoes(raiz:Path, ano:int)->dict:
    """Rótulos de códigos da documentação INEP fornecida no arquivo DICIONARIOS.xlsx."""
    arquivo=raiz/'docs'/'dicionario_questoes_enem_2019_2025.json'
    try:
        d=json.loads(arquivo.read_text(encoding='utf-8'))
        return d['anos'].get(str(ano),{})
    except (OSError,KeyError,ValueError,TypeError):
        return {}


def mostrar_legenda_questoes(st, raiz:Path, meta:dict, ano:int|None)->None:
    """Mostra perguntas realmente correspondentes ao questionário daquela edição.

    Até 2023 Q023 é telefone fixo, não tipo de escola. Nunca se mostra
    automaticamente um significado incompatível com a versão histórica.
    """
    ind=int(meta.get('numero',str(meta.get('id','0'))[-3:]))
    if ind==40:return # IND-040 mostra diretamente cada pergunta/alternativa.
    if ano is None:
        st.caption('Questionários 2019–2023 e 2024–2025 têm versões diferentes. '
                   'Selecione uma edição para consultar o texto oficial das perguntas '
                   'e o código correspondente. Letras iguais não representam sempre a mesma faixa.')
        return
    fonte=str(meta.get('variaveis') or '')
    codigos=re.findall(r'Q\d{3}',fonte)
    if ind==51 and ano is not None:
        try:
            var=json.loads((raiz/'docs/dicionario_questoes_enem_2019_2025.json').read_text(encoding='utf-8'))
            variaveis=var.get('variaveis',{}).get(str(ano),{})
        except (OSError,ValueError,TypeError):
            variaveis={}
        with st.expander(f'Categorias de sexo, faixa etária e cor/raça — dicionário {ano}'):
            for codigo in ('TP_SEXO','TP_FAIXA_ETARIA','TP_COR_RACA'):
                reg=variaveis.get(codigo,{})
                if reg:
                    st.markdown(f'**{codigo}:** {reg.get("pergunta") or "Variável categórica"}')
                    st.caption(' · '.join(f'{chave} = {val}' for chave,val in reg.get('respostas',{}).items()))
            st.caption('São categorias descritivas declaradas no arquivo INEP; nenhuma interpretação biográfica é feita.')
    if not codigos:return
    ano=int(ano)
    if ano<=2023:
        substituicoes={41:{'Q007':'Q006'},42:{'Q007':'Q006'},
                       47:{'Q020':'Q025'},48:{'Q021':'Q024'}}
        codigos=[substituicoes.get(ind,{}).get(x,x) for x in codigos]
        if ind in (45,46):
            st.caption('O código Q023 no questionário de 2019–2023 descreve telefone fixo, '
                       'não a trajetória escolar. Não foi usado como legenda de escola.')
            return
    questoes=ler_dicionario_questoes(raiz,ano)
    linhas=[(codigo,questoes[codigo]) for codigo in dict.fromkeys(codigos) if codigo in questoes]
    if not linhas:return
    with st.expander(f'Perguntas originais do questionário ENEM {ano} — significado das variáveis'):
        for codigo,p in linhas:
            st.markdown(f'**{codigo} — {p.get("pergunta") or "Descrição indisponível"}**')
            opcoes=p.get('respostas') or {}
            if opcoes:
                texto='; '.join(f'{k}: {v}' for k,v in opcoes.items())
                st.caption(texto)
        st.caption('Transcrição de DICIONARIOS.xlsx, incluído nas fontes do projeto. '
                   'Os limites de renda mudam entre edições; códigos não são grandezas numéricas.')


def mostrar_historico_socio_seguro(st,raiz:Path,ind:int,ano:int|None,uf:str)->bool:
    """Evolução adicional somente quando a identidade do recorte está comprovada.

    IND-050: Q005, mesma pergunta e códigos/alternativas oficiais da edição;
    IND-052: mesma métrica de nota total por UF da prova, sem normalizações.
    """
    if ind not in (50,52):return False
    from painel_socio_041_052 import anos_com_dados,carregar_recorte
    anos=anos_com_dados(raiz,ind)
    if len(anos)<2:return False
    if ind==52:
        dados=[]
        for a in anos:
            for regiao in ({'BR',uf} if uf!='BR' else {'BR'}):
                fonte,erro=carregar_recorte(raiz,52,a,regiao)
                if fonte and not erro:
                    medida=(fonte.get('dados') or {}).get('metricas',{}).get('TOTAL',{})
                    if _numerico(medida.get('media')):
                        dados.append({'Ano':str(a),'Recorte':regiao,'Nota média':medida['media'],
                                      'N redações':medida.get('n_redacoes')})
        if len(set(r['Ano'] for r in dados))<2:return False
        with st.expander('Comparar nota média por UF em todos os anos',expanded=ano is None):
            df=pd.DataFrame(dados)
            fig=px.line(df,x='Ano',y='Nota média',color='Recorte',markers=True,
                        hover_data=['N redações'])
            _tracar(st,fig,'Série da nota total por local da prova','pontos (0–1000)')
            st.caption('Uma mesma UF representa o local de prova, não necessariamente o domicílio. '
                       'As edições têm participantes distintos e notas de redação comparáveis como estatísticas descritivas.')
        return True
    dicionario=ler_dicionario_questoes(raiz,ano or 2024)
    q=dicionario.get('Q005',{})
    if not q:return False
    opcoes=list(q.get('respostas') or {})
    if not opcoes:return False
    with st.expander('Comparar nota por número de moradores em anos compatíveis',expanded=ano is None):
        categoria=st.selectbox('Categoria de número de moradores',opcoes,
             format_func=lambda k:f'{k} — {q["respostas"][k]}',key='geral_ind050_historico')
        referencia=q['respostas'][categoria]
        pergunta=q['pergunta']
        serie=[]
        for a in anos:
            info=ler_dicionario_questoes(raiz,a).get('Q005',{})
            def eq(x,y):return re.sub(r'[\s.]+$', '',str(x or '')).casefold()==re.sub(r'[\s.]+$','',str(y or '')).casefold()
            if not (eq(info.get('pergunta'),pergunta) and eq(info.get('respostas',{}).get(categoria),referencia)):
                continue
            fonte,err=carregar_recorte(raiz,50,a,uf)
            if err or not fonte:continue
            dados=(fonte.get('dados') or {}).get('categories',[])
            cat=next((r for r in dados if str(r.get('codigo_faixa_moradores'))==str(categoria)),None)
            if cat and _numerico(cat.get('media')):
                serie.append({'Ano':str(a),'Nota média':cat['media'],'N redações':cat.get('n_redacoes')})
        if len(serie)<2:
            st.info('Não existem duas edições com esta pergunta, alternativa e nota comparáveis.');return True
        fig=px.line(pd.DataFrame(serie),x='Ano',y='Nota média',markers=True,
                    hover_data=['N redações'])
        _tracar(st,fig,f'Nota média · {referencia}','pontos (0–1000)')
        st.caption('Mesma pergunta e mesma alternativa no dicionário, por edição. '
                   'Não é uma comparação das mesmas pessoas; a associação não prova causalidade.')
    return True


def mostrar_glossario_visual(st, ind:int)->None:
    """Legenda acadêmica concisa para a leitura dos indicadores selecionados."""
    comp=(9<=ind<=19 or ind in (21,26,31,32,33,34,35,36,37,38,39,
                                   42,44,46,53,56,58,65,66))
    avaliador=(20<=ind<=29 or ind in (38,59,67))
    if not (comp or avaliador):return
    with st.expander('Glossário — como interpretar as siglas do indicador'):
        if comp:
            st.markdown('**Competências oficiais da redação (C1–C5)**')
            for k,v in COMPETENCIAS.items():st.caption(f'{k}: {v}. Escala usual: 0–200 pontos.')
            if ind in (14,15,16,53):
                st.caption('PC1, PC2 etc. são componentes principais/variáveis latentes do método, '
                           'e não competências oficiais da correção. MCA e PCA são análises diferentes.')
        if avaliador:
            st.markdown('**Avaliações da redação**')
            st.caption('AV1 e AV2: primeiro e segundo avaliadores; AV3: terceiro avaliador quando aplicável; '
                       'AV4: nota da banca colegiada, não de um quarto corretor isolado.')
            st.caption('Diferença absoluta: distância em pontos entre notas; não indica qual correção está certa.')
        if ind in (17,18,28,53):
            st.caption('P1…Pk são agrupamentos por análise de dados, não rótulos oficiais do INEP. '
                       'M1–M3 são os perfis materiais do modelo V2, distintos desses agrupamentos.')
