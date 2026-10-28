# -*- coding: utf-8 -*-
"""Gráficos agregados IND-032..039 e IND-042..045, sem microdados.

A navegação e os filtros pertencem a visualizador.py. Esta camada utiliza
somente os recortes anuais realmente integrados aos dashboards. Nenhum dado
indisponível é inferido ou copiado de outra edição.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from painel_indicadores_recentes import bloco, recorte

COMPETENCIAS = ('C1', 'C2', 'C3', 'C4', 'C5')
CORES = ['#193E64', '#2563A6', '#588DAF', '#88B0C9', '#B8D2E1']


def _numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _valor(x, nd=2):
    if not _numero(x):
        return '—'
    return f'{x:,.{nd}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _contagem(x):
    return f'{int(x):,}'.replace(',', '.') if _numero(x) else '—'


def _indisponivel(st, codigo, ano):
    st.info(f'IND-{codigo:03d}: resultados não disponíveis para {ano}. '
            'Verifique se o dashboard deste ano foi atualizado. Não utilizamos dados de outro ano como substituição.')


def _tabela(st, linhas, nome='Dados agregados'):
    if linhas:
        with st.expander(f'{nome} · tabela completa'):
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)


def _barras(st, plot, linhas, x, y, titulo_y=None, horizontal=False):
    dados = pd.DataFrame([r for r in linhas if _numero(r.get(y))])
    if dados.empty:
        st.info('Não há valores divulgáveis neste recorte.')
        return
    if horizontal:
        fig = px.bar(dados, x=y, y=x, orientation='h', color_discrete_sequence=['#2563A6'])
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    else:
        fig = px.bar(dados, x=x, y=y, color_discrete_sequence=['#2563A6'])
    fig.update_layout(yaxis_title=titulo_y or y, xaxis_title=None)
    plot(fig, 370 if not horizontal else max(330, len(dados) * 29))


def _heatmap(st, plot, linhas, linha, coluna, valor, titulo, limite=None, anotacoes=False):
    df = pd.DataFrame([r for r in linhas if _numero(r.get(valor))])
    if df.empty:
        st.info('Não há valores divulgáveis para formar a matriz.')
        return
    tab = df.pivot_table(index=linha, columns=coluna, values=valor, aggfunc='first', sort=False)
    tab = tab.reindex(columns=[c for c in COMPETENCIAS if c in tab.columns])
    valores = tab.to_numpy(dtype=float)
    fig = go.Figure(go.Heatmap(
        z=valores, x=list(tab.columns), y=list(tab.index),
        colorscale=[[0, '#EDF4F8'], [0.4, '#9FC4D8'], [1, '#1C5280']],
        zmin=0, zmax=limite, colorbar={'title': titulo},
        hovertemplate='%{y}<br>%{x}: %{z:.2f}<extra></extra>',
    ))
    if anotacoes and len(tab.index) <= 8:
        for iy, faixa in enumerate(tab.index):
            for ix, comp in enumerate(tab.columns):
                v = valores[iy, ix]
                if math.isfinite(v):
                    fig.add_annotation(x=comp, y=faixa, text=f'{v:.1f}', showarrow=False,
                                       font={'color': '#12293D', 'size': 11})
    fig.update_layout(yaxis={'autorange': 'reversed'}, xaxis_title='Competências', yaxis_title=None)
    plot(fig, max(360, 78 * len(tab.index)))
    _tabela(st, linhas)


def _comp_linhas(rec, chave, col, campo='competencia'):
    return [{'Competência': q.get(campo), col: q.get(chave),
             'Redações': q.get('n_redacoes'), 'Suprimido': bool(q.get('suprimido'))}
            for q in (rec.get('resumo_competencias') or [])]


def _mostrar_032(st, plot, rec):
    st.metric('Redações na faixa 900–980', _contagem(rec.get('n_near')))
    dados = _comp_linhas(rec, 'percentual_desconto', 'Com desconto (%)')
    _barras(st, plot, dados, 'Competência', 'Com desconto (%)', 'Redações com desconto (%)')
    _tabela(st, dados, 'Frequência de descontos')
    st.caption('Desconto: competência abaixo de 200 pontos; denominador POP_NEAR. '
               'Uma redação pode registrar descontos em várias competências.')


def _mostrar_033(st, plot, rec):
    st.metric('Total de pontos perdidos', _contagem(rec.get('total_pontos_perdidos')))
    dados = _comp_linhas(rec, 'percentual_participacao', 'Participação (%)')
    _barras(st, plot, dados, 'Competência', 'Participação (%)', 'Participação nos pontos perdidos (%)')
    _tabela(st, dados, 'Participação na perda total')
    st.caption('A soma das participações das cinco competências corresponde aproximadamente a 100%, '
               'sujeita ao arredondamento; não representa o percentual de redações.')


def _mostrar_034(st, plot, rec):
    st.metric('Redações com apenas uma competência descontada',
              _contagem(rec.get('n_casos_com_uma_unica_competencia')))
    dados = _comp_linhas(rec, 'n_competencia_unica', 'Redações')
    _barras(st, plot, dados, 'Competência', 'Redações', 'Redações (competência única)')
    _tabela(st, dados, 'Competência única')
    st.caption('Competência única com nota abaixo de 200 dentro da POP_NEAR; '
               'não equivale automaticamente a uma redação de 980 pontos.')


def _mostrar_035(st, plot, rec):
    comb = rec.get('combinacoes') or []
    tipos = sorted({r.get('tipo') for r in comb if r.get('tipo') in ('par', 'trio')})
    if not tipos:
        st.info('Nenhuma combinação disponível.'); return
    escolha = st.radio('Tipo de combinação', tipos, horizontal=True, key='ind035_tipo')
    dados = [{'Combinação': r.get('combinacao') or '+'.join(r.get('competencias', [])),
              'Redações': r.get('n_redacoes_com_desconto_conjunto'),
              'Percentual (%)': r.get('percentual_pop_near'),
              'Suprimido': bool(r.get('suprimido'))}
             for r in comb if r.get('tipo') == escolha]
    _barras(st, plot, dados, 'Combinação', 'Percentual (%)', 'POP_NEAR (%)', horizontal=True)
    _tabela(st, dados, 'Combinações inclusivas')
    st.caption('As combinações são interseções inclusivas: uma redação com C1, C2 e C3 descontadas '
               'participa de C1+C2, C1+C3 e C2+C3. Não somar as frequências.')


def _mostrar_036(st, plot, rec, modulo):
    regras = rec.get('rules') or []
    r = rec.get('resumo_apriori') or {}
    col1, col2, col3 = st.columns(3)
    col1.metric('Redações POP_NEAR', _contagem(rec.get('n_near')))
    col2.metric('Regras selecionadas', _contagem(r.get('regras_selecionadas')))
    col3.metric('Itemsets frequentes', _contagem(r.get('itemsets_frequentes')))
    if not regras:
        st.info('Nenhuma regra atendeu aos limiares neste recorte (ou o recorte está indisponível).'); return
    dados = []
    for regra in regras:
        dados.append({
            'Regra': f"{'+'.join(regra.get('antecedente', []))} → {'+'.join(regra.get('consequente', []))}",
            'Suporte (%)': regra.get('suporte_percentual'),
            'Confiança (%)': regra.get('confianca_percentual'),
            'Lift': regra.get('lift'),
            'Leverage': regra.get('leverage'),
            'Ocorrências': regra.get('n_ambos'),
        })
    df = pd.DataFrame(dados)
    plotdf = df.dropna(subset=['Lift', 'Confiança (%)', 'Suporte (%)', 'Ocorrências'])
    if not plotdf.empty:
        fig = px.scatter(plotdf, x='Confiança (%)', y='Lift', size='Ocorrências',
                         hover_name='Regra', color='Suporte (%)',
                         color_continuous_scale=['#B8D2E1', '#2563A6', '#193E64'],
                         size_max=26)
        fig.add_hline(y=1, line_dash='dot', line_color='#7D9CB8')
        fig.update_layout(xaxis_title='Confiança (%)', yaxis_title='Lift (1 = ausência de associação)')
        plot(fig, 430)
    _tabela(st, dados, 'Regras Apriori')
    parametros = modulo.get('parameters') or {}
    st.caption('Apriori não supervisionado. Suporte mínimo: '
               f"{_valor(100*parametros.get('min_suporte', 0), 1)}%; confiança mínima: "
               f"{_valor(100*parametros.get('min_confianca', 0), 1)}%; "
               f"lift mínimo: {_valor(parametros.get('min_lift'),2)}. "
               'Lift próximo de 1 indica associação fraca; regras não são relações causais.')


def _p_format(p):
    if p is None:
        return '—'
    if not _numero(p):
        return '—'
    if p == 0:
        return '< 1e-300 (limite numérico)'
    return f'{p:.3e}'


def _mostrar_037(st, plot, rec):
    testes = rec.get('tests') or {}
    ocorrencia = testes.get('ocorrencia') or {}
    magnitude = testes.get('magnitude') or {}
    if not testes:
        st.info('Os testes estão indisponíveis neste recorte.'); return
    c1, c2, c3 = st.columns(3)
    c1.metric('Q de Cochran', _valor(ocorrencia.get('estatistica'),2))
    c2.metric('Friedman', _valor(magnitude.get('estatistica'),2))
    c3.metric('W de Kendall', _valor(magnitude.get('kendall_w'),3))
    st.caption('Q de Cochran: ocorrência pareada de descontos. Friedman: magnitude pareada das perdas. '
               'Kendall W é medida de tamanho de efeito. Significância não significa causalidade.')
    oc = [{'Competência': q.get('competencia'), 'Com desconto (%)':q.get('percentual'),
           'Redações com desconto':q.get('n_com_desconto')}
          for q in ocorrencia.get('frequencias_por_competencia') or []]
    mg = [{'Competência': q.get('competencia'), 'Perda média (pontos)':q.get('media_perda')}
          for q in magnitude.get('perdas_por_competencia') or []]
    co, cm = st.columns(2)
    with co:
        st.markdown('**Ocorrência de desconto**')
        _barras(st, plot, oc, 'Competência', 'Com desconto (%)')
    with cm:
        st.markdown('**Magnitude dos descontos**')
        _barras(st, plot, mg, 'Competência', 'Perda média (pontos)')
    familia = st.radio('Pós-testes (famílias Holm separadas)',
                       ['Ocorrência · McNemar', 'Magnitude · Wilcoxon'],
                       horizontal=True, key='ind037_familia')
    chave = 'pos_testes_ocorrencia' if familia.startswith('Ocorrência') else 'pos_testes_magnitude'
    linhas = [{
        'Comparação': f"{t.get('competencia_a')} × {t.get('competencia_b')}",
        'Teste': t.get('teste'), 'p bruto': _p_format(t.get('p_valor')),
        'p Holm': _p_format(t.get('p_ajustado_holm')),
        'Significativo (5%)': t.get('significativo_5pct'),
        'Pares informativos': t.get('n_pares_informativos')
    } for t in testes.get(chave) or []]
    if linhas:
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    st.caption('Os valores exibidos como p < 1e-300 representam subfluxo numérico, não probabilidade exatamente zero. '
               'Dez comparações ajustadas separadamente por família com Holm; efeito sujeito à seleção por nota 900–980.')


def _mostrar_038(st, plot, rec):
    competencias = rec.get('competencias') or []
    st.metric('Redações com duas avaliações válidas', _contagem(rec.get('n_near_evaluator')))
    dados = [{'Competência': c.get('competencia'), 'Kappa': c.get('kappa_ponderado'),
              'Concordância (%)': c.get('concordancia_percentual'),
              'Discordância (%)': c.get('discordancia_percentual'),
              'Suprimido': bool(c.get('suprimido'))} for c in competencias]
    linhas = [r for r in dados if _numero(r['Kappa'])]
    if linhas:
        _barras(st, plot, linhas, 'Competência', 'Kappa', 'Kappa de Cohen (binário)')
        _tabela(st, dados, 'Concordância entre avaliadores')
    opcoes = [c.get('competencia') for c in competencias if isinstance(c.get('matriz_concordancia'), dict)]
    if opcoes:
        escolhida = st.selectbox('Matriz de concordância · competência', opcoes, key='ind038_comp')
        linha = next(c for c in competencias if c.get('competencia') == escolhida)
        mat = linha['matriz_concordancia']
        z = [[mat['av1_nao_av2_nao'], mat['av1_nao_av2_sim']],
             [mat['av1_sim_av2_nao'], mat['av1_sim_av2_sim']]]
        fig = go.Figure(go.Heatmap(z=z, x=['AV2: sem desconto', 'AV2: com desconto'],
                                   y=['AV1: sem desconto', 'AV1: com desconto'],
                                   colorscale='Blues', text=z, texttemplate='%{text}',
                                   hovertemplate='%{y} / %{x}<br>Redações: %{z}<extra></extra>'))
        fig.update_layout(yaxis={'autorange': 'reversed'})
        plot(fig, 345)
    st.caption('Concordância binária para Ci < 200 nas notas dos avaliadores AV1/AV2, '
               'não nas competências finais. Kappa binário ponderado quadrático equivale ao kappa simples. '
               'Concordância não comprova correção ou erro individual.')


def _mostrar_039(st, plot, rec):
    st.metric('Redações 900–1000', _contagem(rec.get('n_high')))
    faixas = rec.get('faixas') or []
    metrica = st.radio('Métrica do mapa', ['Com desconto (%)', 'Perda média (pontos)'],
                       horizontal=True, key='ind039_metrica')
    campo = 'percentual_com_desconto' if metrica.startswith('Com') else 'perda_media'
    dados = [{'Faixa': f.get('faixa'), 'Competência': c.get('competencia'),
              'Valor': c.get(campo), 'Redações na faixa':f.get('n_na_faixa'),
              'Redações com C1–C5 válidas':f.get('n_com_competencias_validas')}
             for f in faixas for c in f.get('competencias') or []]
    _heatmap(st, plot, dados, 'Faixa', 'Competência', 'Valor', metrica,
             limite=100 if metrica.startswith('Com') else None, anotacoes=True)
    st.caption('POP_HIGH inclui 900–1000 e a nota 1000 entra na última faixa. '
               'O denominador dos percentuais considera C1–C5 válidas. '
               'Contagens pequenas podem aparecer agregadas; evite generalizações sobre grupos raros.')


NOVOS_ALTO = [
    (32, 'Frequência · 032', _mostrar_032),
    (33, 'Participação · 033', _mostrar_033),
    (34, 'Competência única · 034', _mostrar_034),
    (35, 'Combinações · 035', _mostrar_035),
    (36, 'Apriori · 036', _mostrar_036),
    (37, 'Testes · 037', _mostrar_037),
    (38, 'Concordância · 038', _mostrar_038),
    (39, 'Mapa · 039', _mostrar_039),
]


def alto_desempenho_novos(st, plot, ano, uf, dashboards: Mapping[int, dict]):
    """Seção inserida abaixo dos gráficos IND-030/031 existentes."""
    st.divider()
    st.markdown('### Investigações do alto desempenho · IND-032 a IND-039')
    if ano is None:
        st.caption('O período completo exibe somente séries anuais calculadas por edição. '
                   'Selecione um ano para explorar os oito indicadores e os dados por UF.')
        serie = []
        for yy, dash in sorted(dashboards.items()):
            r = recorte(dash, 32, uf)
            if r:
                for x in r.get('resumo_competencias', []):
                    if _numero(x.get('percentual_desconto')):
                        serie.append({'Ano': str(yy), 'Competência': x.get('competencia'),
                                      'Com desconto (%)': x['percentual_desconto']})
        if serie:
            fig = px.line(pd.DataFrame(serie), x='Ano', y='Com desconto (%)', color='Competência',
                          markers=True, color_discrete_sequence=CORES)
            fig.update_layout(yaxis_title='POP_NEAR com desconto (%)')
            plot(fig, 390)
        serie2 = []
        for yy, dash in sorted(dashboards.items()):
            b = recorte(dash, 36, uf)
            c = recorte(dash, 37, uf)
            serie2.append({'Ano': str(yy),
                           'Regras Apriori': (b.get('resumo_apriori') or {}).get('regras_selecionadas') if b else None,
                           'W de Kendall': ((c.get('tests') or {}).get('magnitude') or {}).get('kendall_w') if c else None})
        df = pd.DataFrame(serie2)
        if df[['Regras Apriori', 'W de Kendall']].notna().any().any():
            st.dataframe(df, hide_index=True, use_container_width=True)
        return
    d = dashboards.get(ano)
    if not d:
        _indisponivel(st, 32, ano)
        return
    abas = st.tabs([item[1] for item in NOVOS_ALTO])
    for aba, (ind, _, render) in zip(abas, NOVOS_ALTO):
        with aba:
            r = recorte(d, ind, uf)
            mod = bloco(d, ind)
            if not r:
                _indisponivel(st, ind, ano)
                continue
            if ind == 36:
                render(st, plot, r, mod or {})
            else:
                render(st, plot, r)


def _renda_matriz(rec):
    rows = []
    for c in rec.get('categories') or []:
        codigo = c.get('codigo_renda')
        if not codigo:
            continue
        for nome, valores in (c.get('competencias') or {}).items():
            rows.append({'Faixa de renda': codigo, 'Descrição': c.get('descricao_faixa'),
                         'Competência': nome, 'Média': valores.get('media'),
                         'Mediana': valores.get('mediana'), 'Redações': valores.get('n_redacoes')})
    return rows


def _mostrar_042(st, plot, rec):
    rows = _renda_matriz(rec)
    st.metric('Redações válidas', _contagem(rec.get('n_pop_socio_valid')))
    metrica = st.radio('Estatística', ['Média', 'Mediana'], horizontal=True, key='ind042_stat')
    _heatmap(st, plot, rows, 'Faixa de renda', 'Competência', metrica,
             'Pontos por competência (0–200)', limite=200)
    st.caption('As faixas A–Q seguem os limites monetários de cada edição; '
               'as letras não garantem limites comparáveis entre anos. '
               'Renda informada no questionário não é variável causal isolada.')


def _questoes(rec):
    value = rec.get('questions') or rec.get('questoes') or {}
    return value if isinstance(value, dict) else {}


def _mostrar_043(st, plot, rec):
    questoes = _questoes(rec)
    if not questoes:
        st.info('Escolaridade dos responsáveis não disponível para este recorte.'); return
    q = st.radio('Responsável', list(questoes),
                 format_func=lambda k: 'Pai / responsável (Q001)' if k == 'Q001' else 'Mãe / responsável (Q002)',
                 horizontal=True, key='ind043_q')
    grupo = questoes[q]
    rows = [{'Categoria': x.get('codigo_escolaridade'),
             'Descrição': x.get('descricao_categoria'), 'Redações':x.get('n_redacoes'),
             'Nota média':x.get('media'), 'Suprimido':bool(x.get('suprimido'))}
            for x in grupo.get('categories') or []]
    _barras(st, plot, rows, 'Categoria', 'Nota média', 'Nota total média (0–1000)')
    _tabela(st, rows, 'Escolaridade × nota total')
    st.caption('Escolaridade autodeclarada no questionário. Respostas como “Não sei” '
               'não correspondem a níveis de escolaridade; observar as descrições.')


def _mostrar_044(st, plot, rec):
    questoes = _questoes(rec)
    if not questoes:
        st.info('Dados de competências por escolaridade indisponíveis.'); return
    q = st.radio('Responsável', list(questoes),
                 format_func=lambda k: 'Pai / responsável (Q001)' if k == 'Q001' else 'Mãe / responsável (Q002)',
                 horizontal=True, key='ind044_q')
    grupo = questoes[q]
    rows = []
    for c in grupo.get('categories') or []:
        for comp, v in (c.get('competencias') or {}).items():
            rows.append({'Escolaridade':c.get('codigo_escolaridade'),
                         'Descrição': c.get('descricao_categoria'),
                         'Competência': comp, 'Média':v.get('media'),
                         'Mediana':v.get('mediana'), 'Redações':c.get('n_redacoes')})
    metrica = st.radio('Estatística', ['Média', 'Mediana'], horizontal=True, key='ind044_stat')
    _heatmap(st, plot, rows, 'Escolaridade', 'Competência', metrica,
             'Pontos por competência (0–200)', limite=200)
    st.caption('Comparação descritiva. Categorias sem escolaridade conhecida e '
               'categorias suprimidas devem ser interpretadas separadamente.')


def _mostrar_045(st, plot, rec, mod):
    cats = rec.get('categories') or []
    rows = [{'Categoria': c.get('codigo_escola'), 'Descrição': c.get('descricao_categoria'),
             'Redações': c.get('n_redacoes'), 'Média': c.get('media'),
             'Mediana':c.get('mediana'), 'Suprimido':bool(c.get('suprimido'))}
            for c in cats]
    st.metric('Redações válidas', _contagem(rec.get('n_pop_socio_valid')))
    _barras(st, plot, rows, 'Categoria', 'Média', 'Nota total média (0–1000)')
    _tabela(st, rows, 'Tipo de escola')
    st.caption(f"Variável de origem: {mod.get('source_variable', 'não informada')}. "
               'TP_ESCOLA (2019–2023) e Q023 (2024) não são conceitos equivalentes. '
               'Não construa uma série de evolução por categoria entre esses períodos.')


NOVOS_SOCIO = [
    (42, 'Renda × competências · 042', _mostrar_042),
    (43, 'Escolaridade × nota · 043', _mostrar_043),
    (44, 'Escolaridade × competências · 044', _mostrar_044),
    (45, 'Tipo de escola × nota · 045', _mostrar_045),
]


def socioeconomico_novos(st, plot, ano, uf, dashboards: Mapping[int, dict]):
    st.divider()
    st.markdown('### Cruzamentos socioeconômicos · IND-042 a IND-045')
    if ano is None:
        st.info('Selecione uma edição para analisar os cruzamentos. '
                'A renda muda de limites monetários e a variável de escola muda de conceito entre os anos.')
        linhas = []
        for yy, dash in sorted(dashboards.items()):
            linha = {'Ano': yy}
            for ind in (42, 43, 44, 45):
                linha[f'IND-{ind:03d}'] = 'Disponível' if recorte(dash, ind, uf) else 'Indisponível'
            linhas.append(linha)
        if linhas:
            st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
        return
    d = dashboards.get(ano)
    if not d:
        _indisponivel(st, 42, ano)
        return
    tabs = st.tabs([item[1] for item in NOVOS_SOCIO])
    for tab, (ind, _, render) in zip(tabs, NOVOS_SOCIO):
        with tab:
            r = recorte(d, ind, uf)
            mod = bloco(d, ind)
            if not r:
                _indisponivel(st, ind, ano)
                continue
            if ind == 45:
                render(st, plot, r, mod or {})
            else:
                render(st, plot, r)
