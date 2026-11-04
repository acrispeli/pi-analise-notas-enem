# -*- coding: utf-8 -*-
"""Visuais específicos IND-041..IND-052 para o painel Streamlit.

Somente lê dashboards agregados já existentes. Não recalcula notas, não faz
junção individual, não modifica JSONs e não supõe harmonização de categorias
socioeconômicas entre edições. A UF é sempre a UF de aplicação da prova.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CAMINHOS = {
    41: 'income_total', 42: 'income_competencies',
    43: 'parent_education_total', 44: 'parent_education_competencies',
    45: 'school_type_total', 46: 'school_type_competencies',
    47: 'internet_performance', 48: 'computer_performance',
    49: 'parent_occupation', 50: 'household_size',
    51: 'demographics', 52: 'uf_performance',
}
DESCRICAO_COMP = {
    'C1': 'C1 · Escrita formal', 'C2': 'C2 · Proposta',
    'C3': 'C3 · Argumentação', 'C4': 'C4 · Coesão',
    'C5': 'C5 · Intervenção',
}
CORES_COMPETENCIAS = {
    'C1 · Escrita formal':'#2667A9',
    'C2 · Proposta':'#D97706',
    'C3 · Argumentação':'#1F8A70',
    'C4 · Coesão':'#7C5DB5',
    'C5 · Intervenção':'#C44E52'}


def anos_com_dados(raiz: Path, numero: int) -> list[int]:
    """Determina anos disponíveis pelo módulo presente no dashboard, sem usar 2024 como substituto."""
    assert numero in CAMINHOS
    encontrados = []
    for ano in range(2019, 2026):
        caminho = raiz / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            continue
        # Os cruzamentos com notas não são vinculáveis aos questionários em 2025.
        if ano == 2025 and numero != 52:
            continue
        encontrados.append(ano)
    return encontrados


def carregar_recorte(raiz: Path, numero: int, ano: int, uf: str) -> tuple[dict | None, str | None]:
    """Obtém o recorte explícito do dashboard anual, nunca o país como fallback de UF."""
    if numero not in CAMINHOS:
        return None, 'Indicador fora do escopo deste módulo.'
    if ano not in anos_com_dados(raiz, numero):
        return None, f'O IND-{numero:03d} não possui resultado disponível para {ano}.'
    caminho = raiz / 'outputs/json' / f'dashboard_enem_{ano}.json'
    with caminho.open('r', encoding='utf-8-sig') as f:
        dashboard = json.load(f)
    bloco = dashboard.get('pages', {}).get('socioeconomic', {}).get(CAMINHOS[numero])
    if not isinstance(bloco, dict):
        return None, f'O IND-{numero:03d} não consta no dashboard {ano}.'
    if uf == 'BR':
        dados = bloco.get('national')
    else:
        estados = bloco.get('states')
        dados = estados.get(uf) if isinstance(estados, dict) else None
    if not isinstance(dados, dict):
        return None, f'Não há recorte explícito da UF {uf} no IND-{numero:03d}/{ano}.'
    return {'bloco': bloco, 'dados': dados, 'ano': ano, 'uf': uf}, None


def _numero(x: Any) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    try:
        n = float(x)
    except (ValueError, TypeError):
        return None
    return n if pd.notna(n) else None


def categorias_grupo(dados: dict, numero: int, subgrupo: str | None = None) -> list[dict]:
    """Extrai categorias publicadas e seu esquema sem ignorar níveis aninhados."""
    if numero in (43, 44):
        q = dados.get('questions', dados.get('questoes', {}))
        dados = q.get(subgrupo, {}) if isinstance(q, dict) else {}
    elif numero == 49:
        dados = dados.get(subgrupo, {})
    elif numero == 51:
        dados = dados.get('dimensoes', {}).get(subgrupo, {})
    categorias = dados.get('categories', dados.get('categorias', []))
    if not isinstance(categorias, list):
        return []
    return sorted((c for c in categorias if isinstance(c, dict)),
                  key=lambda c: (c.get('ordem', 999), str(c.get('codigo_categoria', ''))))


def subgrupos(dados: dict, numero: int) -> dict[str, str]:
    if numero in (43, 44):
        grupos = dados.get('questions', dados.get('questoes', {}))
        return {str(k): str(v.get('responsavel') or k) for k, v in grupos.items() if isinstance(v, dict)}
    if numero == 49:
        return {k: str(v.get('responsavel') or k) for k, v in dados.items() if isinstance(v, dict) and isinstance(v.get('categories'), list)}
    if numero == 51:
        return {k: k for k, v in dados.get('dimensoes', {}).items() if isinstance(v, dict)}
    return {}


def tabela_medias(categorias: list[dict], numero: int) -> pd.DataFrame:
    """Tabula categorias na ordem documental, preservando N e identificação de grupos pequenos."""
    tabela = []
    for idx, c in enumerate(categorias):
        # Não forçar publicação de valores explicitamente suprimidos no JSON.
        if c.get('suprimido') is True:
            continue
        codigo = next((str(c[k]) for k in ('codigo_renda','codigo_escolaridade','codigo_escola',
                   'codigo_acesso','codigo_computador','codigo_ocupacao','codigo_faixa_moradores',
                   'codigo_categoria','faixa_renda') if k in c and c[k] is not None), str(idx+1))
        descricao = str(c.get('descricao_faixa') or c.get('descricao_categoria') or codigo)
        if numero in (41,42) and codigo not in [chr(x) for x in range(ord('A'),ord('Q')+1)]:
            # Renda não informada não é uma faixa ordenável de renda.
            continue
        if numero in (47,48):
            medidas = c.get('medidas', {})
            medidas_total = medidas.get('C0', {}) if isinstance(medidas, dict) else {}
            media = _numero(medidas_total.get('media'))
            mediana = _numero(medidas_total.get('mediana'))
        else:
            media, mediana = _numero(c.get('media')), _numero(c.get('mediana'))
        n = _numero(c.get('n_redacoes'))
        if n is None and numero in (47,48):
            n = _numero(c.get('medidas', {}).get('C0', {}).get('n_redacoes'))
        tabela.append({'ordem':int(c.get('ordem', idx)), 'Codigo':codigo,
                       'Descrição':descricao, 'Redações':int(n) if n is not None else None,
                       'Média':media,'Mediana':mediana,
                       'Q1':_numero(c.get('q1')),'Q3':_numero(c.get('q3')),
                       'n_pequeno':bool(c.get('n_pequeno', False)), '_categoria':c})
    return pd.DataFrame(tabela).sort_values('ordem') if tabela else pd.DataFrame()


def tabela_competencias(categorias: list[dict], numero: int) -> pd.DataFrame:
    linhas=[]
    for i,c in enumerate(categorias):
        if c.get('suprimido') is True:
            continue
        codigo = next((str(c[k]) for k in ('codigo_renda','codigo_escolaridade','codigo_escola',
                   'codigo_acesso','codigo_computador','codigo_ocupacao','codigo_faixa_moradores',
                   'codigo_categoria','faixa_renda') if k in c and c[k] is not None), str(i+1))
        if numero in (42,) and codigo not in [chr(x) for x in range(ord('A'),ord('Q')+1)]:
            continue
        medidas = c.get('competencias',c.get('medidas',{}))
        if not isinstance(medidas,dict):
            continue
        for competencia in DESCRICAO_COMP:
            detalhe=medidas.get(competencia,{})
            if not isinstance(detalhe,dict):
                continue
            media = _numero(detalhe.get('media'))
            if media is None:continue
            linhas.append({'Codigo':codigo, 'Descrição':str(c.get('descricao_faixa') or c.get('descricao_categoria') or codigo),
                           'Competência':competencia,'Média':media,'ordem':int(c.get('ordem',i)),
                           'Redações':int(detalhe['n_redacoes']) if _numero(detalhe.get('n_redacoes')) is not None else None})
    return pd.DataFrame(linhas)


def _figura_categorias(tabela:pd.DataFrame, numero:int):
    d=tabela.dropna(subset=['Média']).copy().sort_values('ordem')
    if d.empty:return None
    if numero==41:
        d['Faixa'] = d['Codigo']
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=d['Faixa'],y=d['Média'],mode='lines+markers',name='Média',
                     customdata=d[['Descrição','Redações']].fillna('—').to_numpy(),
                     hovertemplate='Faixa %{x}: %{customdata[0]}<br>Média: %{y:.1f} pontos<br>Redações: %{customdata[1]}<extra></extra>'))
        if d['Mediana'].notna().any():
            fig.add_trace(go.Scatter(x=d['Faixa'],y=d['Mediana'],mode='lines+markers',name='Mediana',
                     hovertemplate='Faixa %{x}<br>Mediana: %{y:.0f} pontos<extra></extra>'))
        fig.update_layout(xaxis_title='Faixas de renda da edição (A–Q)',yaxis_title='Nota da redação (0–1000)')
    elif numero==50:
        fig=px.line(d,x='Descrição',y='Média',markers=True,hover_data=['Redações'],
                    labels={'Descrição':'Número de moradores','Média':'Nota média (0–1000)'})
    else:
        d['Categoria']=d['Descrição']
        fig=px.bar(d, y='Categoria',x='Média',orientation='h',hover_data=['Codigo','Redações'],
                   labels={'Categoria':'Categoria declarada','Média':'Nota média (0–1000)'})
        fig.update_layout(yaxis={'categoryorder':'array','categoryarray':d['Categoria'].tolist()[::-1]})
    fig.update_layout(height=max(360, min(720, 75+int(len(d))*32)),
                      margin=dict(t=30,b=75,l=30,r=20))
    return fig


def _figura_competencias(df:pd.DataFrame,numero:int):
    if df.empty:return None
    df=df.copy()
    df['Competência']=df['Competência'].map(DESCRICAO_COMP)
    df=df.sort_values('ordem')
    if numero==42:
        fig=px.line(df,x='Codigo',y='Média',color='Competência',markers=True,
                    color_discrete_map=CORES_COMPETENCIAS,
                    hover_data=['Descrição','Redações'],
                    labels={'Codigo':'Faixas de renda da edição','Média':'Média por competência (0–200)'})
    else:
        df['Categoria']=df['Descrição']
        graf=df.pivot_table(index='Competência',columns='Categoria',values='Média',aggfunc='first')
        fig=px.imshow(graf,aspect='auto',text_auto='.1f',
                      labels={'x':'Categoria declarada','y':'Competência','color':'Média (0–200)'})
    fig.update_layout(height=430 if numero==42 else 500,margin=dict(t=40,b=100,l=70,r=30))
    return fig


def _renderizar_052(st, recorte:dict, raiz:Path, uf:str):
    bloco=recorte['bloco'];dados=recorte['dados']
    if uf=='BR':
        linhas=[]
        for sigla, valor in bloco.get('states',{}).items():
            if not isinstance(valor,dict) or valor.get('suprimido') is True:continue
            medida=valor.get('metricas',{}).get('TOTAL',{})
            media=_numero(medida.get('media'))
            if media is not None:
                linhas.append({'UF':sigla,'Média':media,'Redações':valor.get('n_redacoes')})
        t=pd.DataFrame(linhas)
        if t.empty:
            st.info('Não existem médias estaduais divulgáveis para este recorte.')
            return
        t=t.sort_values('Média',ascending=False)
        fig=px.bar(t,x='Média',y='UF',orientation='h',hover_data=['Redações'],
                   labels={'Média':'Média da redação (pontos, 0–1000)','UF':'UF de aplicação da prova'})
        fig.update_layout(height=820, yaxis={'categoryorder':'array',
                          'categoryarray':t['UF'].tolist()[::-1]})
        media_br=_numero(dados.get('metricas',{}).get('TOTAL',{}).get('media'))
        if media_br is not None:
            fig.add_vline(x=media_br,line_dash='dash',annotation_text=f'Brasil: {media_br:.1f} pontos')
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(t,hide_index=True,use_container_width=True)
    else:
        t=pd.DataFrame([{'Competência':c,'Média':_numero(dados.get('metricas',{}).get(c,{}).get('media'))}
                         for c in DESCRICAO_COMP])
        st.caption(f'Redações válidas na UF da prova: {dados.get("n_redacoes", "—")}')
        total=_numero(dados.get('metricas',{}).get('TOTAL',{}).get('media'))
        if total is not None:st.metric('Média total da redação',f'{total:.1f} pontos')
        fig=px.bar(t,x='Competência',y='Média',labels={'Média':'Pontos por competência (0–200)'})
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(t,hide_index=True,use_container_width=True)
    st.caption('UF refere-se ao local de aplicação da prova, não ao local de residência. Comparações descritivas não explicam as causas das diferenças.')


def renderizar_socio(st, raiz:Path, numero:int, ano:int|None, uf:str) -> bool:
    """Exibe gráfico e tabela para IND-041..052. Retorna True se assumiu a renderização."""
    if numero not in CAMINHOS:return False
    anos=anos_com_dados(raiz,numero)
    if not anos:
        st.warning('Os dashboards agregados necessários não foram encontrados.')
        return True
    if ano is None:
        st.info('O filtro global está em “Todos os anos”. Para este cruzamento, as definições de categorias e sua disponibilidade podem mudar entre edições. Selecione uma edição abaixo; não juntaremos faixas de renda ou escolaridade não equivalentes.')
        preferido=2024 if 2024 in anos else anos[-1]
        ano_efetivo=st.selectbox('Edição para esta visualização',anos,index=anos.index(preferido),
                                 key=f'socio_edicao_{numero}')
    else:
        ano_efetivo=ano
    recorte,erro=carregar_recorte(raiz,numero,ano_efetivo,uf)
    if erro:
        st.info(erro)
        return True
    st.caption(f'Dados agregados da edição {ano_efetivo} · '+('Brasil' if uf=='BR' else f'UF da prova: {uf}')+
               ' · Fonte: dashboard_enem_'+str(ano_efetivo)+'.json')
    dados=recorte['dados']
    if numero==52:
        _renderizar_052(st,recorte,raiz,uf)
        return True
    grupos=subgrupos(dados,numero)
    selecionado=None
    if grupos:
        opcoes=list(grupos)
        selecionado=st.selectbox('Detalhamento do indicador',opcoes,
                     format_func=lambda k:f'{k} · {grupos[k]}' if k!=grupos[k] else k,
                     key=f'socio_detalhe_{numero}_{ano_efetivo}')
    categorias=categorias_grupo(dados,numero,selecionado)
    if not categorias:
        st.info('Este recorte não oferece categorias agregadas para o indicador.')
        return True
    df=tabela_medias(categorias,numero)
    comp=tabela_competencias(categorias,numero)
    if numero in (42,44,46):
        fig=_figura_competencias(comp,numero)
        tabela=comp.drop(columns='ordem') if not comp.empty else pd.DataFrame()
    else:
        fig=_figura_categorias(df,numero)
        tabela=df.drop(columns=['ordem','_categoria','n_pequeno'],errors='ignore') if not df.empty else pd.DataFrame()
    if fig is not None:
        st.plotly_chart(fig,use_container_width=True)
    else:
        st.info('A fonte não possui medidas numéricas para montar este gráfico.')
    if not tabela.empty:
        st.dataframe(tabela,hide_index=True,use_container_width=True)
    if numero in (41,42):
        pergunta=recorte['bloco'].get('source_question')
        if pergunta:
            st.caption(f'Questão de renda na fonte da edição {ano_efetivo}: {pergunta}.')
        st.caption('As letras das faixas de renda representam intervalos monetários diferentes conforme o ano. Leia as descrições na tabela; “renda não informada” não é posicionada como faixa monetária.')
        fora = []
        codigos_validos={chr(c) for c in range(ord('A'),ord('Q')+1)}
        for c in categorias:
            codigo=str(c.get('codigo_renda',c.get('faixa_renda','')))
            if codigo in codigos_validos:
                continue
            extra={'Código':codigo,
                   'Descrição':c.get('descricao_faixa','Sem faixa de renda'),
                   'Redações':c.get('n_redacoes')}
            if numero==41:
                extra['Média']=c.get('media')
                extra['Mediana']=c.get('mediana')
            else:
                for comp in DESCRICAO_COMP:
                    extra[f'Média {comp}']=c.get('competencias',{}).get(comp,{}).get('media')
            fora.append(extra)
        if fora:
            st.caption('Respostas fora das faixas A–Q, mantidas separadamente para não criar uma ordem de renda artificial:')
            st.dataframe(pd.DataFrame(fora),hide_index=True,use_container_width=True)
    if numero in (43,44,45,46,47,48,49,50,51):
        st.caption('As categorias correspondem às respostas do questionário da edição selecionada. Mudanças de pergunta/códigos entre anos podem impedir comparações diretas.')
    if not df.empty and df['n_pequeno'].any():
        st.warning('Algumas categorias têm poucos registros; suas estimativas podem variar bastante. Essa observação não elimina os dados automaticamente.')
    st.caption('Os dados descrevem associações entre características declaradas e desempenho; não demonstram relações de causa e efeito.')
    return True
