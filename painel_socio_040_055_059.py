# -*- coding: utf-8 -*-
"""Gráficos especializados dos IND-040 e IND-055..059.

Usa exclusivamente os JSONs agregados, sem recalcular microdados ou
interpolar edições. Os perfis materiais M1–M3 são amostrais e nacionais.
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path
import re
from contextlib import nullcontext

from painel_revisao_geral_68 import ler_dicionario_questoes
import plotly.express as px

from painel_catalogo_68 import DESCRICAO_PERFIS

MODELO_V2 = 'V2_MCA10_KMeans3_e31f55489e16f296'
MAPA_PERFIS = {'C1':'M1', 'C2':'M2', 'C3':'M3'}
PERFIS_ORDEM = ('M1','M2','M3')
COMPETENCIAS = ('C1','C2','C3','C4','C5')


def _numero(n):
    return f'{int(n):,}'.replace(',', '.')


def _categorias_ordenadas(linhas: list[dict]) -> list[dict]:
    """Categorias físicas numéricas em ordem 0, 1, 2, ...; as demais, ordem da fonte."""
    if all(str(x.get('codigo', '')).isdigit() for x in linhas):
        return sorted(linhas, key=lambda x: int(x['codigo']))
    numeros = [x for x in linhas if str(x.get('codigo', '')).isdigit()]
    demais = [x for x in linhas if not str(x.get('codigo', '')).isdigit()]
    if numeros:
        return sorted(numeros, key=lambda x: int(x['codigo'])) + demais
    return linhas


def _recorte_ind040(doc: dict, ano: int, uf: str) -> tuple[dict | None, dict | None, str | None]:
    anos = doc.get('years', [])
    edicao = next((x for x in anos if int(x.get('ano', -1)) == int(ano)), None)
    if edicao is None:
        return None, None, f'IND-040: não há resultados para {ano}.'
    if uf == 'BR':
        return edicao, edicao.get('brasil'), None
    recorte = next((x for x in edicao.get('ufs', []) if x.get('uf') == uf), None)
    if recorte is None:
        return edicao, None, f'IND-040: a edição {ano} não traz dados para a UF {uf}.'
    return edicao, recorte, None


def renderizar_ind040(st, doc: dict, ano: int | None, uf: str) -> bool:
    """Mostra uma edição e uma pergunta; sem somar categorias de questionários diferentes."""
    anos = sorted({int(y['ano']) for y in doc.get('years', []) if 'ano' in y})
    if not anos:
        st.info('O IND-040 não possui edições disponíveis neste arquivo.'); return True
    if ano is None:
        st.info('O IND-040 apresenta a distribuição de uma edição por vez: as perguntas e as categorias mudaram entre edições.')
        escolhido = st.selectbox('Edição do questionário socioeconômico', anos,
                                 index=len(anos)-1, key='ind040_edicao')
    else:
        escolhido = int(ano)
    edicao, recorte, erro = _recorte_ind040(doc, escolhido, uf)
    if erro:
        st.info(erro); return True
    if not isinstance(recorte, dict):
        st.info('Não foi possível recuperar o questionário do recorte.'); return True
    perguntas = recorte.get('questoes', [])
    if not perguntas:
        st.info('Esta edição não contém distribuições por pergunta.'); return True
    titulos = {p['questao']: f"{p['questao']} · {p.get('tema', 'Pergunta')}" for p in perguntas}
    selecionada = st.selectbox('Pergunta do questionário', list(titulos),
                               format_func=lambda codigo: titulos[codigo], key=f'ind040_pergunta_{escolhido}')
    pergunta = next(p for p in perguntas if p['questao'] == selecionada)
    dicionario=ler_dicionario_questoes(Path(__file__).resolve().parent,escolhido)
    detalhes=dicionario.get(selecionada,{})
    if detalhes.get('pergunta'):
        st.caption('**Texto da pergunta no dicionário ENEM '+str(escolhido)+':** '
                    +detalhes['pergunta'])
    else:
        st.warning('A descrição integral da pergunta não foi encontrada no dicionário; apenas o tema é exibido.')
    cats = _categorias_ordenadas(pergunta.get('categorias', []))
    if not cats:
        st.info('A pergunta não possui categorias neste recorte.'); return True
    denominador = int(pergunta.get('denominador', recorte.get('n_participacoes', 0)))
    total = sum(int(item['quantidade']) for item in cats)
    if denominador <= 0 or total != denominador:
        st.error('Não foi possível validar a soma das categorias contra o denominador da fonte.'); return True
    st.metric('Participações no recorte (questionário)', _numero(recorte['n_participacoes']))
    st.caption(f'ENEM {escolhido} · {"Brasil" if uf == "BR" else "UF da prova: " + uf} · '
               f'Pergunta {selecionada}: {pergunta.get("tema", "")} · Denominador da pergunta: {_numero(denominador)}')
    tabela = pd.DataFrame([{
        'Código': str(item['codigo']),
        'Rótulo na fonte': str(item.get('rotulo') or item['codigo']),
        'Significado da resposta': detalhes.get('respostas',{}).get(str(item['codigo']),
                                  'Categoria agregada ou sem descrição individual no dicionário'),
        'Quantidade': int(item['quantidade']),
        'Percentual (%)': float(item['percentual']),
    } for item in cats])
    grafico = px.bar(tabela, x='Código', y='Percentual (%)',
                     hover_data={'Significado da resposta':True,'Quantidade':':,','Percentual (%)':':.2f'},
                     labels={'Código':'Categoria de resposta'},
                     title=f'Distribuição das respostas — {selecionada} ({escolhido})')
    grafico.update_layout(xaxis={'type':'category'}, margin=dict(t=60,b=65))
    st.plotly_chart(grafico,use_container_width=True)
    st.dataframe(tabela, hide_index=True, use_container_width=True)
    # Não inferir equivalência entre edições apenas porque os códigos Q e A/B são iguais.
    # Uma evolução só aparece quando pergunta, versão e texto de CADA alternativa
    # são explicitamente equivalentes no dicionário da própria edição.
    def normalizar(s):
        return re.sub(r'[\s.]+$', '', str(s or '').strip()).casefold()
    linhas_comp=[]
    base={str(c['codigo']):normalizar(detalhes.get('respostas',{}).get(str(c['codigo'])))
          for c in cats}
    if detalhes.get('pergunta') and base and all(base.values()):
        for a in anos:
            ep,rr,err=_recorte_ind040(doc,a,uf)
            if err or not rr or ep.get('versao_questionario')!=edicao.get('versao_questionario'):
                continue
            pe=next((q for q in rr.get('questoes',[]) if q.get('questao')==selecionada),None)
            dd=ler_dicionario_questoes(Path(__file__).resolve().parent,a).get(selecionada,{})
            if not pe or normalizar(dd.get('pergunta'))!=normalizar(detalhes.get('pergunta')):
                continue
            cc=pe.get('categorias',[])
            nomes={str(q['codigo']):normalizar(dd.get('respostas',{}).get(str(q['codigo']))) for q in cc}
            if nomes!=base:continue
            for item in cc:
                linhas_comp.append({'Ano':str(a),'Código':str(item['codigo']),
                                    'Percentual (%)':float(item['percentual'])})
    if len(set(r['Ano'] for r in linhas_comp))>=2 and hasattr(st,'expander'):
        with (st.expander('Comparar edições com pergunta e alternativas equivalentes')
              if hasattr(st,'expander') else nullcontext()):
            cdf=pd.DataFrame(linhas_comp)
            serie=px.line(cdf,x='Ano',y='Percentual (%)',color='Código',markers=True,
                          title='Distribuição desta pergunta nas edições comparáveis')
            serie.update_layout(yaxis_title='% das participações no questionário')
            st.plotly_chart(serie,use_container_width=True)
            st.caption('Comparação restrita a edições com versão, pergunta e todas as alternativas equivalentes. '
                       'Não corresponde a acompanhamento das mesmas pessoas.')
    else:
        st.caption('Não existe série segura com duas ou mais edições contendo pergunta e todas as '
                   'alternativas equivalentes no dicionário consultado. A comparação não foi forçada.')
    st.caption('Os códigos exibidos são os informados na fonte. Consulte o dicionário do INEP '
               'para o significado exato de cada alternativa; não interprete A, B, C etc. como quantidades ou níveis equivalentes entre perguntas/anos. '
               'As frequências contabilizam participações, não pessoas únicas no histórico.')
    if pergunta.get('tem_agregacao_para_privacidade') or pergunta.get('categorias_originais_agrupadas'):
        st.warning('A fonte agrupa algumas categorias desta pergunta. Elas podem reunir respostas de significados diferentes.')
    st.caption('Este indicador descreve o questionário e não relaciona, por si só, as respostas às notas da redação.')
    return escolhido  # permite a explicação acessível registrar a edição efetivamente exibida


def _dados_v2(doc: dict, ind: int) -> pd.DataFrame:
    if doc.get('modelo_referencia') != MODELO_V2 or doc.get('publicacao_autorizada') is not False:
        return pd.DataFrame()
    registros = [r for r in doc.get('results', []) if isinstance(r, dict)
                 and str(r.get('status', '')).lower() != 'nao_aplicavel'
                 and r.get('cluster') in MAPA_PERFIS]
    tabela = pd.DataFrame(registros)
    if tabela.empty:
        return tabela
    tabela['Perfil'] = tabela['cluster'].map(MAPA_PERFIS)
    tabela['ano'] = pd.to_numeric(tabela['ano'],errors='coerce')
    return tabela


def _tabela_competencias(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    grade = df.pivot(index='competencia',columns='Perfil',values=coluna)
    return grade.reindex(index=list(COMPETENCIAS),columns=list(PERFIS_ORDEM))


def _mapa_calor(st, df: pd.DataFrame, coluna: str, titulo: str, minimo: int, maximo: int) -> None:
    grade = _tabela_competencias(df, coluna)
    if grade.isna().any().any():
        st.warning('A matriz está incompleta; gráfico omitido para evitar interpretações erradas.')
        return
    fig=px.imshow(grade, text_auto='.1f', aspect='auto', zmin=minimo, zmax=maximo,
                  labels={'x':'Perfil material','y':'Competência da redação','color':titulo},
                  title=titulo)
    fig.update_layout(margin=dict(t=65,b=45))
    st.plotly_chart(fig,use_container_width=True)


def renderizar_v2(st, doc: dict, ind: int, ano: int | None, uf: str) -> bool:
    """Especialização dos indicadores V2 055–059; nunca calcula dados estaduais."""
    if ind not in (55,56,57,58,59):
        return False
    if uf != 'BR':
        st.info('Os perfis M1–M3 resultam de uma amostra nacional. Não há resultado validado por UF nesta fonte; selecione Brasil.')
        return True
    if doc.get('modelo_referencia') != MODELO_V2 or doc.get('publicacao_autorizada') is not False:
        st.warning('Esta fonte não corresponde ao modelo V2 interno validado; gráfico indisponível.')
        return True
    df = _dados_v2(doc, ind)
    if df.empty:
        st.info('Não há observações aplicáveis neste indicador.'); return True
    disponiveis = sorted(int(a) for a in df['ano'].dropna().unique())
    if ano is not None and int(ano) not in disponiveis:
        st.info(f'IND-{ind:03d}: não há cruzamento validado para {ano}. '
                'Em 2025, os perfis socioeconômicos não têm vinculação individual validada com as notas da redação.')
        return True
    st.caption('Amostra nacional, perfis de referência fixos M1–M3. Resultados internos e descritivos; sem inferência causal.')
    if ano is None:
        if ind in (55,57,59):
            coluna,titulo = {
                55:('media','Nota média da redação (0–1000)'),
                57:('percentual_high','Redações válidas com 900–1000 (%)'),
                59:('media_diferenca_absoluta','Diferença absoluta média AV1 × AV2 (pontos)'),
            }[ind]
            tendencia=px.line(df, x='ano',y=coluna,color='Perfil',markers=True,
                              category_orders={'Perfil':list(PERFIS_ORDEM)},
                              labels={'ano':'Edição do ENEM',coluna:titulo},
                              title='Evolução por perfil material (amostra)')
            tendencia.update_xaxes(dtick=1)
            st.plotly_chart(tendencia,use_container_width=True)
        elif ind in (56,58):
            comp=st.selectbox('Competência para a evolução histórica',list(COMPETENCIAS),
                              key=f'ind{ind:03d}_comp_historico')
            serie=df.loc[df['competencia']==comp].copy()
            if ind==56:
                coluna,titulo='media','Nota média na competência (0–200)'
            else:
                medida=st.selectbox('Medida histórica de desconto',
                        ['Frequência de desconto (%)','Pontos perdidos em média'],
                        key='ind058_tipo_historico')
                if medida=='Frequência de desconto (%)':
                    coluna,titulo='frequencia_desconto','Frequência de desconto (%)'
                    serie[coluna]=pd.to_numeric(serie[coluna],errors='coerce')*100
                else:
                    coluna,titulo='perda_media','Pontos perdidos em média'
            fig=px.line(serie,x='ano',y=coluna,color='Perfil',markers=True,
                        labels={'ano':'Edição do ENEM',coluna:titulo},
                        title=f'Evolução de {comp} por perfil material (amostra)')
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig,use_container_width=True)
            st.caption('Séries de edições diferentes e amostrais, não acompanhamento individual. '
                       'O perfil de referência é fixo no modelo V2, mas a composição da amostra muda.')
        escolhido=st.selectbox('Edição para detalhamento',disponiveis,index=len(disponiveis)-1,
                               key=f'ind{ind:03d}_ano_detalhe')
    else:
        escolhido=int(ano)
    dados=df.loc[df['ano']==escolhido].copy()
    if dados.empty:
        st.info(f'Sem registros aplicáveis para {escolhido}.'); return True
    dados['Perfil'] = pd.Categorical(dados['Perfil'],categories=list(PERFIS_ORDEM),ordered=True)
    if ind==55:
        medio=dados.melt(id_vars=['Perfil','n','q1','q3'],value_vars=['media','mediana'],
                         var_name='Estatística',value_name='Nota (0–1000)')
        medio['Estatística']=medio['Estatística'].map({'media':'Média','mediana':'Mediana'})
        fig=px.bar(medio,x='Perfil',y='Nota (0–1000)',color='Estatística',barmode='group',
                   hover_data={'n':True,'q1':True,'q3':True},
                   title=f'Notas da redação por perfil — {escolhido}')
        st.plotly_chart(fig,use_container_width=True)
        st.caption('Q1 e Q3 (quartis) e o número de redações válidas da amostra constam da tabela e do detalhamento do gráfico.')
    elif ind==56:
        _mapa_calor(st,dados,'media',f'Nota média por competência — {escolhido} (0–200)',0,200)
    elif ind==57:
        fig=px.bar(dados,x='Perfil',y='percentual_high',
                   hover_data={'n_notas_validas':True,'n_high_900_1000':True},
                   labels={'percentual_high':'Percentual de redações válidas (%)'},
                   title=f'Redações válidas com 900–1000 pontos — {escolhido}')
        fig.update_layout(yaxis_ticksuffix='%')
        st.plotly_chart(fig,use_container_width=True)
        st.caption('Cada percentual usa como denominador as redações válidas da própria amostra e do próprio perfil (não todos os participantes).')
    elif ind==58:
        dados['Frequência (%)']=pd.to_numeric(dados['frequencia_desconto'],errors='coerce')*100
        _mapa_calor(st,dados,'Frequência (%)',f'Frequência de desconto por competência — {escolhido} (%)',0,100)
        _mapa_calor(st,dados,'perda_media',f'Pontos perdidos, em média, por competência — {escolhido}',0,200)
        st.warning('O grupo de notas próximas a 1.000 é amostral e pode conter células pequenas. '
                   'Frequência de desconto e média de pontos perdidos são métricas distintas.')
    elif ind==59:
        comparacao=dados.melt(id_vars=['Perfil','n_pareadas'],
                              value_vars=['media_diferenca_absoluta','mediana_diferenca_absoluta',
                                          'p90_diferenca_absoluta'],
                              var_name='Estatística',value_name='Diferença absoluta (pontos)')
        comparacao['Estatística']=comparacao['Estatística'].map({
            'media_diferenca_absoluta':'Média','mediana_diferenca_absoluta':'Mediana',
            'p90_diferenca_absoluta':'P90'})
        fig=px.bar(comparacao,x='Perfil',y='Diferença absoluta (pontos)',
                   color='Estatística',barmode='group',hover_data=['n_pareadas'],
                   title=f'Diferenças absolutas AV1 × AV2 — {escolhido}')
        st.plotly_chart(fig,use_container_width=True)
        st.caption('Diferença absoluta não indica qual avaliador está correto e não comprova viés ou discriminação.')
    colunas_uteis=[c for c in dados.columns if c not in ('cluster','status','observacao','modelo_referencia')]
    st.dataframe(dados[colunas_uteis],hide_index=True,use_container_width=True)
    st.caption(DESCRICAO_PERFIS+' As edições representam amostras de participações, não acompanhamento das mesmas pessoas.')
    return True
