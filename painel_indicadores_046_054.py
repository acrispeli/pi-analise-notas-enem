# -*- coding: utf-8 -*-
"""Painéis agregados IND-046..054, lidos exclusivamente dos dashboards cumulativos.

Não calcula indicadores nem importa microdados: somente apresenta resultados existentes.
Não substitui anos indisponíveis e não altera o que foi suprimido nos JSONs.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CHAVES = {
    46: ('socioeconomic', 'school_type_competencies'),
    47: ('socioeconomic', 'internet_performance'),
    48: ('socioeconomic', 'computer_performance'),
    49: ('socioeconomic', 'parent_occupation'),
    50: ('socioeconomic', 'household_size'),
    51: ('socioeconomic', 'demographics'),
    52: ('socioeconomic', 'uf_performance'),
    53: ('ml', 'socio_mca'),
    54: ('ml', 'socio_clusters'),
}
NOMES = {
    46: 'Tipo de escola × C1–C5',
    47: 'Internet × desempenho',
    48: 'Computadores × desempenho',
    49: 'Ocupação dos responsáveis',
    50: 'Moradores × desempenho',
    51: 'Subgrupos demográficos',
    52: 'UF da prova × desempenho',
    53: 'Dimensões socioeconômicas · MCA',
    54: 'Clusters socioeconômicos · K-Means',
}
COMP = ('C1', 'C2', 'C3', 'C4', 'C5')
MEDIDAS = {'TOTAL': 'Nota total', 'C1': 'Competência 1', 'C2': 'Competência 2',
           'C3': 'Competência 3', 'C4': 'Competência 4', 'C5': 'Competência 5'}
CORES = ['#193E64', '#2563A6', '#588DAF', '#88B0C9', '#B8D2E1']


def numero(valor):
    return (isinstance(valor, (float, int)) and not isinstance(valor, bool)
            and math.isfinite(valor))


def formato(valor, casas=1):
    if not numero(valor):
        return '—'
    return f'{valor:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def modulo(dashboard: Mapping | None, indicador: int) -> dict | None:
    """Valida o identificador antes de apresentar um módulo existente."""
    if not isinstance(dashboard, Mapping) or indicador not in CHAVES:
        return None
    pagina, chave = CHAVES[indicador]
    pages = dashboard.get('pages') or {}
    bloco = (pages.get(pagina) or {}).get(chave) if isinstance(pages, Mapping) else None
    if isinstance(bloco, dict) and bloco.get('indicator_id') == f'IND-{indicador:03d}':
        return bloco
    return None


def recorte(dashboard: Mapping | None, indicador: int, uf: str = 'BR') -> dict | None:
    obj = modulo(dashboard, indicador)
    if obj is None:
        return None
    if indicador in (53, 54):
        return obj  # Os modelos são nacionais; sem recorte geográfico individual.
    if uf == 'BR':
        valor = obj.get('national')
    else:
        valor = (obj.get('states') or {}).get(uf)
    return valor if isinstance(valor, dict) else None


def disponibilidade(dashboards: Mapping[int, dict], uf='BR') -> list[dict]:
    """Não confunde dado indisponível com zero ou resultado de outro ano."""
    return [{'Ano': a, **{f'IND-{i:03d}': 'Disponível' if recorte(d, i, uf)
                          else 'Não integrado' for i in CHAVES}}
            for a, d in sorted(dashboards.items())]


def _sem_dados(st, ind, ano):
    st.info(f'IND-{ind:03d} não integrado ao dashboard de {ano}. '
            'É necessário executar o indicador nos microdados e enviar o dashboard atualizado ao GitHub.')


def _tabela(st, linhas, titulo='Tabela agregada'):
    if linhas:
        with st.expander(titulo):
            st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)


def _barras(st, plot, rows, x, y, label=None, horizontal=False):
    df = pd.DataFrame([r for r in rows if numero(r.get(y))])
    if df.empty:
        st.info('Sem estatísticas disponíveis para este recorte (ou campos suprimidos na origem).')
        return
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation='h', color_discrete_sequence=[CORES[1]])
        altura = max(330, 26 * len(df) + 90)
    else:
        fig = px.bar(df, x=x, y=y, color_discrete_sequence=[CORES[1]])
        altura = 360
    fig.update_layout(xaxis_title=None if not horizontal else label or y,
                      yaxis_title=label or y if not horizontal else None)
    plot(fig, altura)


def _mapa_calor(st, plot, linhas, indice, valor, maximo):
    df = pd.DataFrame([r for r in linhas if numero(r.get(valor))])
    if df.empty:
        st.info('Sem médias/medianas publicadas nas categorias deste recorte.')
        return
    tab = df.pivot_table(index=indice, columns='Competência', values=valor, aggfunc='first')
    tab = tab.reindex(columns=[x for x in COMP if x in tab.columns])
    if tab.empty:
        return
    fig = go.Figure(go.Heatmap(z=tab.to_numpy(float), x=list(tab.columns), y=list(tab.index),
                               zmin=0, zmax=maximo, colorscale='Blues',
                               hovertemplate='%{y} | %{x}: %{z:.1f} pontos<extra></extra>'))
    fig.update_layout(yaxis={'autorange': 'reversed'}, xaxis_title='Competência', yaxis_title=None)
    plot(fig, max(350, 40 * len(tab) + 100))


def _categorias(rec, codigo, estat='media'):
    return [{'Categoria': c.get(codigo), 'Descrição': c.get('descricao_categoria'),
             'Redações': c.get('n_redacoes'), 'Média': c.get('media'),
             'Mediana': c.get('mediana'), 'Q1': c.get('q1'), 'Q3': c.get('q3'),
             'Suprimido na origem': c.get('suprimido', False)}
            for c in (rec.get('categories') or [])]


def _competencias(rec, codigo, chave='competencias'):
    linhas = []
    for cat in rec.get('categories') or []:
        for nome, dados in (cat.get(chave) or {}).items():
            if nome not in COMP or not isinstance(dados, dict):
                continue
            linhas.append({'Categoria': str(cat.get(codigo)),
                           'Descrição': cat.get('descricao_categoria'),
                           'Competência': nome, 'Média': dados.get('media'),
                           'Mediana': dados.get('mediana'), 'Redações': dados.get('n_redacoes')})
    return linhas


def _mostrar_046(st, plot, rec, mod):
    st.metric('Redações válidas', formato(rec.get('n_pop_socio_valid'), 0))
    st.caption(f"Variável de origem: {mod.get('source_variable', 'não identificada')}. "
               'TP_ESCOLA (2019–2023) e Q023 (2024) não são diretamente equivalentes.')
    linhas = _competencias(rec, 'codigo_escola')
    estat = st.radio('Estatística por competência', ['Média', 'Mediana'], horizontal=True, key='ind046_stat')
    _mapa_calor(st, plot, linhas, 'Categoria', estat, 200)
    _tabela(st, linhas, 'Competências por tipo de escola')


def _mostrar_047_048(st, plot, rec, mod, ind):
    st.metric('Redações válidas', formato(rec.get('n_pop_socio_valid'), 0))
    st.caption(f"Fonte: {mod.get('source_variable', '—')}. "
               + ('2019–2023: acesso à internet; 2024: Wi-Fi no domicílio. Não comparar diretamente.'
                  if ind == 47 else
                  '2019–2023 e 2024 utilizam perguntas com formulações distintas.'))
    medida = st.selectbox('Nota ou competência', list(MEDIDAS),
                          format_func=lambda k: MEDIDAS[k], key=f'ind{ind:03d}_medida')
    estat = st.radio('Estatística', ['Média', 'Mediana'], horizontal=True, key=f'ind{ind:03d}_stat')
    cod = 'codigo_acesso' if ind == 47 else 'codigo_computador'
    rows = []
    for c in rec.get('categories') or []:
        valores = (c.get('medidas') or {}).get('C0' if medida == 'TOTAL' else medida) or {}
        rows.append({'Categoria': c.get(cod), 'Descrição': c.get('descricao_categoria'),
                     'Redações': valores.get('n_redacoes'),
                     'Média': valores.get('media'), 'Mediana': valores.get('mediana'),
                     'Suprimido na origem': c.get('suprimido', False)})
    _barras(st, plot, rows, 'Categoria', estat, 'Pontos · escala 0–1000' if medida == 'TOTAL' else 'Pontos · escala 0–200')
    _tabela(st, rows)
    if ind == 47:
        delta = (rec.get('comparacao_sim_menos_nao') or {}).get('C0' if medida == 'TOTAL' else medida) or {}
        x = delta.get('diferenca_medias_sim_menos_nao')
        if numero(x):
            st.metric('Diferença de médias · Sim − Não', f'{formato(x, 2)} pontos')
            st.caption('Associação descritiva, não efeito causal.')


def _mostrar_049(st, plot, rec, mod):
    grupos = {k: v for k, v in rec.items() if isinstance(v, dict) and 'categories' in v}
    if not grupos:
        st.info('Não há categorias ocupacionais disponíveis neste recorte.')
        return
    q = st.radio('Responsável', list(grupos), format_func=lambda k: 'Pai/responsável masculino (Q003)' if k in ('pai_ou_responsavel_masculino', 'Q003') else 'Mãe/responsável feminino (Q004)',
                 horizontal=True, key='ind049_responsavel')
    linhas = _categorias(grupos[q], 'codigo_ocupacao')
    st.metric('Redações válidas', formato(grupos[q].get('n_pop_socio_valid'), 0))
    _barras(st, plot, linhas, 'Categoria', 'Média', 'Nota total média (0–1000)')
    _tabela(st, linhas, 'Grupos de ocupação')
    st.caption('Grupos A–E são ocupações autodeclaradas; F corresponde a “não sei”.')


def _mostrar_050(st, plot, rec, mod):
    linhas = _categorias(rec, 'codigo_faixa_moradores')
    st.metric('Redações válidas', formato(rec.get('n_pop_socio_valid'), 0))
    estat = st.radio('Estatística', ['Média', 'Mediana'], horizontal=True, key='ind050_stat')
    _barras(st, plot, linhas, 'Categoria', estat, 'Nota total (0–1000)')
    _tabela(st, linhas, 'Moradores por domicílio')
    st.caption('Q005 inclui o próprio participante. A faixa 10–20 é fechada, não significa “20 ou mais”.')


def _mostrar_051(st, plot, rec, mod):
    grupos = rec.get('dimensoes') or {}
    if not grupos:
        st.info('Subgrupos demográficos ainda não disponíveis neste recorte.')
        return
    nomes = {'TP_SEXO': 'Sexo', 'TP_FAIXA_ETARIA': 'Faixa etária', 'TP_COR_RACA': 'Cor/raça'}
    var = st.selectbox('Dimensão demográfica', list(grupos),
                       format_func=lambda k: nomes.get(k, k), key='ind051_dimensao')
    linhas = _categorias(grupos[var], 'codigo_categoria')
    st.metric('Redações válidas', formato(rec.get('n_pop_socio_valid'), 0))
    _barras(st, plot, linhas, 'Categoria', 'Média', 'Nota total média (0–1000)')
    _tabela(st, linhas, 'Categorias demográficas')
    st.caption('Comparação descritiva de populações autodeclaradas; categorias e disponibilidade variam por edição.')


def _mostrar_052(st, plot, dash, uf):
    mod = modulo(dash, 52)
    if not mod:
        st.info('IND-052 não integrado a este dashboard.')
        return
    escolha = st.selectbox('Nota ou competência', list(MEDIDAS),
                           format_func=lambda k: MEDIDAS[k], key='ind052_medida')
    metrica = 'TOTAL' if escolha == 'TOTAL' else escolha
    estat = st.radio('Estatística', ['Média', 'Mediana'], horizontal=True, key='ind052_stat')
    linhas = []
    for codigo, rec in [('BR', mod.get('national') or {}), *((mod.get('states') or {}).items())]:
        nota = (rec.get('metricas') or {}).get(metrica) or {}
        linhas.append({'UF': codigo, 'Redações': rec.get('n_redacoes'),
                       'Média': nota.get('media'), 'Mediana': nota.get('mediana'),
                       'Suprimido na origem': rec.get('suprimido', False)})
    regional = next((r for r in linhas if r['UF'] == uf), None)
    if regional:
        a, b = st.columns(2)
        a.metric('Redações válidas · recorte selecionado', formato(regional.get('Redações'), 0))
        b.metric(f'{estat} · {MEDIDAS[escolha]}', formato(regional.get(estat), 2))
    tabela = [r for r in linhas if r['UF'] != 'BR']
    _barras(st, plot, tabela, 'UF', estat, 'Pontuação', horizontal=True)
    _tabela(st, linhas, 'Brasil e 27 UFs')
    st.caption('UF refere-se ao local de aplicação da prova. Diferenças descritivas não indicam causalidade. '
               'O indicador contempla 2025 quando processado.')


def _mostrar_mca(st, plot, modelo, titulo):
    if not isinstance(modelo, dict):
        st.info('Modelo MCA ainda não integrado ou não calculado para esta edição.')
        return
    st.markdown(f'#### {titulo}')
    col = st.columns(3)
    col[0].metric('Participantes da amostra', formato(modelo.get('n_amostra'), 0))
    col[1].metric('Variáveis ativas', formato(modelo.get('n_variaveis_ativas'), 0))
    col[2].metric('Categorias ativas', formato(modelo.get('n_categorias_ativas'), 0))
    dimensoes = modelo.get('dimensoes') or []
    if not dimensoes:
        st.info('Eixos da MCA não disponíveis.'); return
    eixos = [{'Eixo': f"Dimensão {d.get('eixo')}", 'Inércia (%)': d.get('inercia_pct'),
             'Autovalor': d.get('autovalor')} for d in dimensoes]
    _barras(st, plot, eixos, 'Eixo', 'Inércia (%)', 'Inércia MCA (%)')
    st.caption('Inércia da MCA não é a variância explicada da PCA. O sinal das coordenadas é arbitrário.')
    eixo = st.selectbox('Contribuições e coordenadas do eixo', range(len(dimensoes)),
                        format_func=lambda i: f"Dimensão {dimensoes[i].get('eixo')}",
                        key='ind053_eixo')
    d = dimensoes[eixo]
    linhas = [{'Variável': k, 'Contribuição (%)': v}
              for k, v in (d.get('contribuicoes_variaveis_pct') or {}).items()]
    _barras(st, plot, linhas[:15], 'Variável', 'Contribuição (%)', 'Participação no eixo (%)', horizontal=True)
    categorias = [{'Variável': c.get('variavel'), 'Categoria': c.get('categoria'),
                   'Frequência': c.get('frequencia'), 'Contribuição (%)': c.get('contribuicao_pct'),
                   'Coordenada': c.get('coordenada')} for c in d.get('categorias') or []]
    _tabela(st, categorias, 'Coordenadas e contribuições de todas as categorias')
    _tabela(st, eixos, 'Indicadores de inércia')


def _mostrar_clusters(st, plot, modelo, titulo):
    if not isinstance(modelo, dict):
        st.info('Modelo K-Means ainda não integrado ou não calculado para esta edição.'); return
    st.markdown(f'#### {titulo}')
    metricas = modelo.get('metricas_k_escolhido') or {}
    col = st.columns(3)
    col[0].metric('Participantes da amostra', formato(modelo.get('n_amostra'), 0))
    col[1].metric('K escolhido', formato(modelo.get('k_selecionado'), 0))
    col[2].metric('Silhouette', formato(metricas.get('silhouette'), 3))
    linhas = [{'Cluster': c.get('cluster'), 'Participantes': c.get('n_amostra'),
              'Participação aproximada (%)': c.get('participacao_aprox_pct')}
             for c in modelo.get('clusters') or []]
    _barras(st, plot, linhas, 'Cluster', 'Participantes', 'Participantes na amostra')
    _tabela(st, linhas, 'Distribuição dos clusters')
    diagnosticos = [{'K': x.get('k'), 'Situação': x.get('status'),
                     'Silhouette': x.get('silhouette'), 'Davies–Bouldin': x.get('davies_bouldin'),
                     'Calinski–Harabasz': x.get('calinski_harabasz'),
                     'ARI de estabilidade': x.get('ari_estabilidade')}
                    for x in modelo.get('diagnosticos_k') or []]
    _tabela(st, diagnosticos, 'Diagnóstico de escolha do K')
    perfis = [{'Cluster': c.get('cluster'), 'Variável': x.get('variavel'),
              'Categoria': x.get('categoria'), 'Prevalência no cluster (aprox. %)': x.get('prevalencia_grupo_aprox_pct'),
              'Diferença aproximada (p.p.)': x.get('diferenca_aprox_pp')}
             for c in modelo.get('clusters') or [] for x in c.get('perfil_exploratorio') or []]
    _tabela(st, perfis, 'Perfis exploratórios (margens agregadas)')
    st.caption('C1, C2 etc. são rótulos locais do K-Means e NÃO equivalem às competências da redação. '
               'Os clusters de anos distintos não têm correspondência automática. '
               'A amostra não representa necessariamente o peso populacional de cada edição.')


def pagina_indicadores_novos(st, plot, ano: int | None, uf: str,
                            dashboards: Mapping[int, dict]) -> None:
    st.title('Novos indicadores · IND-046 a IND-054')
    st.caption('Cruzamentos socioeconômicos, UF da prova, análise de correspondência múltipla e clusters. '
               'O painel lê somente os JSONs agregados integrados aos dashboards.')
    socio, geo, mca, clusters = st.tabs(['Contexto socioeconômico · 046–051',
                                        'UF da prova · 052', 'MCA · 053', 'Clusters · 054'])
    if ano is None:
        with socio:
            st.info('Escolha um ano para comparar as categorias. O significado de várias perguntas mudou em 2024.')
            st.dataframe(pd.DataFrame(disponibilidade(dashboards, uf)), hide_index=True,
                         use_container_width=True)
        with geo:
            dados = []
            for yy, dash in sorted(dashboards.items()):
                r = recorte(dash, 52, uf)
                med = (r.get('metricas') or {}).get('TOTAL') if r else None
                if isinstance(med, dict) and numero(med.get('media')):
                    dados.append({'Ano': str(yy), 'Nota média': med['media'],
                                  'Redações': r.get('n_redacoes')})
            if dados:
                df = pd.DataFrame(dados)
                fig = px.line(df, x='Ano', y='Nota média', markers=True,
                              color_discrete_sequence=[CORES[1]])
                fig.update_layout(yaxis_title='Nota média total (pontos)')
                plot(fig, 350)
                _tabela(st, dados, 'Evolução anual da UF selecionada')
            else:
                _sem_dados(st, 52, '2019–2025')
        for ind, aba, chave, func in ((53, mca, 'modelo_nucleo_conjunto', _mostrar_mca),
                                      (54, clusters, 'modelo_nucleo_conjunto', _mostrar_clusters)):
            with aba:
                modelo = next(((modulo(d, ind) or {}).get(chave)
                               for _, d in sorted(dashboards.items())
                               if (modulo(d, ind) or {}).get(chave)), None)
                if modelo:
                    treino = modelo.get('years_in_training') or []
                    abrangencia = f'{min(treino)}–{max(treino)}' if treino else 'edições disponíveis'
                    func(st, plot, modelo,
                         f'IND-{ind:03d} · núcleo harmonizado conjunto ({abrangencia})')
                else:
                    st.info(f'IND-{ind:03d}: modelo conjunto ainda não integrado. '
                            'Para os modelos anuais, escolha um ano no filtro superior.')
        return
    dash = dashboards.get(ano)
    with socio:
        if not dash:
            st.info(f'Não há dashboard de {ano}.')
        else:
            opcoes = list(range(46, 52))
            escolha = st.selectbox('Indicador socioeconômico', opcoes,
                                   format_func=lambda i: f'IND-{i:03d} · {NOMES[i]}', key='ind046_051_escolha')
            mod, r = modulo(dash, escolha), recorte(dash, escolha, uf)
            if r is None:
                _sem_dados(st, escolha, ano)
            else:
                st.markdown(f'### IND-{escolha:03d} · {NOMES[escolha]}')
                if escolha == 46:
                    _mostrar_046(st, plot, r, mod)
                elif escolha in (47, 48):
                    _mostrar_047_048(st, plot, r, mod, escolha)
                else:
                    {49: _mostrar_049, 50: _mostrar_050, 51: _mostrar_051}[escolha](st, plot, r, mod)
                st.caption('Dados processados por edição. Valores suprimidos nos arquivos de origem '
                           'não são reconstruídos pelo visualizador.')
    with geo:
        if dash and modulo(dash, 52):
            _mostrar_052(st, plot, dash, uf)
        else:
            _sem_dados(st, 52, ano)
    with mca:
        mod = modulo(dash, 53)
        if mod:
            if uf != 'BR':
                st.info('A MCA utiliza amostras nacionais; o filtro de UF não se aplica a este gráfico.')
            _mostrar_mca(st, plot, mod.get('modelo_ano'), f'IND-053 · MCA anual {ano}')
        else:
            _sem_dados(st, 53, ano)
    with clusters:
        mod = modulo(dash, 54)
        if mod:
            if uf != 'BR':
                st.info('O K-Means utiliza amostras nacionais; o filtro de UF não se aplica a este gráfico.')
            _mostrar_clusters(st, plot, mod.get('modelo_ano'), f'IND-054 · K-Means anual {ano}')
        else:
            _sem_dados(st, 54, ano)
