# -*- coding: utf-8 -*-
"""Leituras pedagógicas de IND-053/054, sem transformar modelos anuais em séries comparáveis.

Todas as medidas e categorias vêm dos JSONs agregados existentes.
Não faz junções, não lê registros individuais e não altera os resultados.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import plotly.express as px


def anos_disponiveis(documento: dict) -> list[int]:
    return sorted(int(k) for k, v in documento.get('years', {}).items()
                  if str(k).isdigit() and isinstance(v, dict))


def dados_edicao(documento: dict, numero: int, ano: int) -> dict:
    por_ano = documento.get('years', {}).get(str(ano), {})
    campo = 'mca' if numero == 53 else 'modelo'
    resultado = por_ano.get(campo, {})
    return resultado if isinstance(resultado, dict) else {}


def tabela_eixos(documento: dict, ano: int) -> pd.DataFrame:
    dados = dados_edicao(documento, 53, ano)
    linhas = []
    for eixo in dados.get('dimensoes', []):
        if isinstance(eixo, dict) and isinstance(eixo.get('inercia_pct'), (int, float)):
            linhas.append({'Dimensão': 'Dimensão ' + str(eixo.get('eixo', '?')),
                           'Inércia (%)': float(eixo['inercia_pct'])})
    return pd.DataFrame(linhas)


def tabela_grupos(documento: dict, ano: int) -> pd.DataFrame:
    dados = dados_edicao(documento, 54, ano)
    linhas = []
    for idx, grupo in enumerate(dados.get('clusters', []), start=1):
        if not isinstance(grupo, dict):
            continue
        n = grupo.get('n_amostra')
        if not isinstance(n, (int, float)):
            continue
        linhas.append({'Agrupamento': f'H{idx}', 'Redações?': None,
                       'Participantes na amostra': int(n),
                       'Participação aproximada (%)': grupo.get('participacao_aprox_pct')})
    df = pd.DataFrame(linhas)
    # O IND-054 é alimentado pelo questionário e não permite afirmar
    # que cada registro corresponde a uma redação.
    if 'Redações?' in df.columns:
        df = df.drop(columns=['Redações?'])
    return df


def _ano_para_exibir(st, documento: dict, ano: int | None, numero: int) -> int | None:
    anos = anos_disponiveis(documento)
    if not anos:
        st.info('A fonte não fornece resultados por edição.')
        return None
    if ano is not None:
        if ano not in anos:
            st.info(f'Não há resultado da edição {ano} nesta fonte.')
            return None
        return ano
    st.info('Você selecionou “Todos os anos”. Os modelos deste indicador foram ajustados separadamente em cada edição. Para evitar uma comparação enganosa entre agrupamentos ou dimensões, escolha abaixo uma edição para explorar. Esta escolha vale somente para este indicador.')
    default = 2024 if 2024 in anos else anos[-1]
    return st.selectbox('Edição do modelo a visualizar', anos,
                        index=anos.index(default), key=f'ml_modelo_explorar_{numero}')


def _painel_053(st, doc: dict, ano: int):
    model = dados_edicao(doc, 53, ano)
    df = tabela_eixos(doc, ano)
    if df.empty:
        st.info('A fonte não apresenta as dimensões calculadas para esta edição.')
        return
    st.subheader(f'Dimensões encontradas — {ano}')
    st.write('A técnica MCA reúne respostas do questionário em eixos que ajudam a enxergar padrões. Cada barra mostra quanto das diferenças observadas nas respostas é resumido por uma dimensão. Não é uma porcentagem da nota da redação.')
    fig = px.bar(df, x='Dimensão', y='Inércia (%)', text='Inércia (%)',
                 title='Quanto cada dimensão resume das diferenças entre respostas')
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(yaxis_title='Inércia explicada (%)', xaxis_title=None)
    fig.update_yaxes(range=[0, max(1, df['Inércia (%)'].max() * 1.25)])
    st.plotly_chart(fig, use_container_width=True)
    n = model.get('n_amostra')
    if isinstance(n, int):
        st.caption(f'Amostra utilizada nesta edição: {n:,} participantes do questionário.'.replace(',', '.'))
    axes = model.get('dimensoes', [])
    if not axes:
        return
    ids = [int(a.get('eixo', i+1)) for i,a in enumerate(axes) if isinstance(a, dict)]
    escolhido = st.selectbox('Entenda quais perguntas contribuíram para a dimensão', ids,
                             key=f'ml_dimensao_53_{ano}')
    eixo = next((a for a in axes if isinstance(a,dict) and a.get('eixo') == escolhido), None)
    contribs = eixo.get('contribuicoes_variaveis_pct', {}) if eixo else {}
    itens = [(str(q),float(v)) for q,v in contribs.items() if isinstance(v,(int,float))]
    itens = sorted(itens,key=lambda x:x[1],reverse=True)[:10]
    if itens:
        d = pd.DataFrame(itens,columns=['Questão do questionário','Contribuição (%)'])
        fig2 = px.bar(d.sort_values('Contribuição (%)'), x='Contribuição (%)',
                      y='Questão do questionário', orientation='h',
                      title=f'Perguntas que mais formaram a dimensão {escolhido}')
        st.plotly_chart(fig2,use_container_width=True)
        st.caption('Os códigos Q001, Q002 etc. identificam perguntas do questionário. Consulte o dicionário da edição para conhecer seu significado. A contribuição não mede efeito sobre a nota.')
    st.warning('As dimensões são características estatísticas do questionário, não habilidades da redação. Os modelos anuais são independentes e o questionário mudou entre edições; não suponha que a “Dimensão 1” tem o mesmo significado em todos os anos.')


def _painel_054(st, doc: dict, ano: int):
    model = dados_edicao(doc, 54, ano)
    df = tabela_grupos(doc, ano)
    if df.empty:
        st.info('A fonte não apresenta a composição dos agrupamentos para esta edição.')
        return
    st.subheader(f'Agrupamentos encontrados — {ano}')
    st.write('O algoritmo reuniu participantes que responderam de maneira semelhante ao questionário. As barras mostram quantos participantes da amostra ficaram em cada grupo; isso não representa classes sociais oficiais nem notas de redação.')
    fig = px.bar(df, x='Agrupamento', y='Participantes na amostra',
                 text='Participantes na amostra',title='Tamanho dos grupos nesta edição')
    fig.update_traces(textposition='outside')
    fig.update_layout(xaxis_title=None,yaxis_title='Participantes da amostra')
    fig.update_yaxes(range=[0, max(1, df['Participantes na amostra'].max()*1.22)])
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.caption('As participações são aproximadas e vêm arredondadas da fonte. H1, H2 etc. identificam apenas os grupos do modelo histórico desta edição; não correspondem aos perfis materiais M1–M3 da V2.')
    grupos = [g for g in model.get('clusters',[]) if isinstance(g,dict)]
    opcoes = [f'H{i}' for i in range(1,len(grupos)+1)]
    if opcoes:
        escolhido = st.selectbox('Quais respostas distinguem um grupo?',opcoes,key=f'ml_perfil_54_{ano}')
        idx=int(escolhido[1:])-1
        perfis=grupos[idx].get('perfil_exploratorio',[])
        linhas=[]
        for item in perfis:
            if isinstance(item,dict):
                linhas.append({'Questão':item.get('variavel'),
                               'Resposta (código)':item.get('categoria'),
                               'No grupo, aprox. (%)':item.get('prevalencia_grupo_aprox_pct'),
                               'Na amostra, aprox. (%)':item.get('prevalencia_amostra_aprox_pct')})
        if linhas:
            st.dataframe(pd.DataFrame(linhas),hide_index=True,use_container_width=True)
            st.caption('Esta tabela mostra quais respostas aparecem com mais frequência no grupo do que na amostra. Sem traduzir as categorias pelo dicionário correto da edição, não é seguro dar nomes sociais a H1/H2.')
    st.warning('A análise é exploratória e baseada em amostra. Os agrupamentos mudam entre modelos anuais: H1 de 2019 não é necessariamente H1 de 2024. O modelo histórico do IND-054 é distinto da V2 e não deve ser usado para caracterizar os perfis materiais M1–M3.')


def renderizar_ml_didatico(st: Any, documento: dict, numero: int,
                           ano: int | None, uf: str) -> bool:
    """Retorna True para encaminhar IND-053/054 à visualização especializada."""
    if numero not in (53,54):
        return False
    if uf != 'BR':
        st.info('O modelo foi calculado sobre a amostra nacional do questionário. Este JSON não permite reconstruir uma análise independente para a UF selecionada. Escolha “Todos os estados (Brasil)” para visualizar os resultados.')
        return True
    if numero == 54:
        st.info('Modelo histórico do IND-054: os grupos H1/H2 são exploratórios e não equivalem aos três perfis materiais M1–M3 empregados nos IND-055–059 e IND-068.')
        if ano is None:
            st.warning('No agrupamento conjunto original, praticamente toda a amostra ficou em um único grupo e outro grupo refletiu registros incompletos. Por isso esse resultado conjunto não é adequado como perfil socioeconômico interpretável. A visualização abaixo usa apenas o modelo anual escolhido.')
    escolha = _ano_para_exibir(st, documento, ano, numero)
    if escolha is None:
        return True
    if numero == 53:
        _painel_053(st,documento,escolha)
    else:
        _painel_054(st,documento,escolha)
    return True
