# -*- coding: utf-8 -*-
"""Camada de acabamento visual, preservando os dados e módulos existentes.

Projeto Integrador IV — UNIVESP.

Instalada após st.set_page_config() no visualizador.py, esta camada:
- padroniza eixos, números, rótulos e cores dos gráficos Plotly;
- corrige o eixo temporal quando há apenas uma edição;
- disponibiliza versões didáticas explícitas de IND-002/003/004/005/007/008
  onde o módulo do catálogo antigo ainda é o responsável pela renderização;
- não modifica JSONs, cálculos ou a lógica dos perfis socioeconômicos.

A camada não substitui uma revisão do código-fonte mais recente de cada gráfico.
"""
from __future__ import annotations

import functools
import json
import math
import re
from pathlib import Path
from typing import Any

PALETA_COMP = {
    'C1': '#22577A', 'C2': '#298E95', 'C3': '#B47B20',
    'C4': '#805AA4', 'C5': '#B64A62',
}
COR_PRINCIPAL = '#21689B'
COR_SECUNDARIA = '#639AB8'
ANOS = set(range(2019, 2026))


def _numeros(valor: Any) -> list[float]:
    """Obtém apenas números finitos; preserva os elementos originais da figura."""
    if valor is None:
        return []
    try:
        valores = list(valor)
    except (TypeError, ValueError):
        valores = [valor]
    saida = []
    for v in valores:
        if v is None or isinstance(v, (list, tuple, dict)):
            continue
        try:
            numero = float(v)
        except (ValueError, TypeError):
            continue
        if math.isfinite(numero):
            saida.append(numero)
    return saida


def _anos_eixo(valores: Any) -> list[int]:
    if valores is None:
        return []
    try:
        numeros = list(valores)
    except (TypeError, ValueError):
        return []
    if not numeros or len(numeros) > 100:
        return []
    try:
        anos = [int(v) for v in numeros]
        if all(float(v) == y and y in ANOS for v, y in zip(numeros, anos)):
            return anos
    except (TypeError, ValueError):
        pass
    return []


def _titulo_eixo(fig, nome: str) -> str:
    obj = getattr(fig.layout, nome, None)
    try:
        return str(obj.title.text or '')
    except (AttributeError, ValueError):
        return ''


def _eh_percentual(txt: str) -> bool:
    return bool(re.search(r'percent|participa[cç][aã]o\s*\(%\)|\(\s*%\s*\)|%\b', txt, re.I))


def _rotular_barras_compactas(fig, *, limite_vertical: int = 8) -> bool:
    """Inclui rótulos em colunas/barras curtas, inclusive múltiplos traços.

    Plotly Express cria um traço por competência quando usa color='competencia'.
    O acabamento antigo exigia um único traço e não rotulava C1–C5.
    Não rotula gráficos empilhados, normalizados ou visualmente densos.
    """
    tracos = list(fig.data)
    if not tracos or any(t.type != 'bar' for t in tracos):
        return False
    if getattr(fig.layout, 'barnorm', None):
        return False
    orientacoes = {getattr(t, 'orientation', None) or 'v' for t in tracos}
    if len(orientacoes) != 1:
        return False
    horizontal = 'h' in orientacoes
    limite = 12 if horizontal else limite_vertical
    series = []
    for tr in tracos:
        valores = tr.x if horizontal else tr.y
        categorias = tr.y if horizontal else tr.x
        if valores is None or categorias is None:
            return False
        valores, categorias = list(valores), list(categorias)
        if not valores or len(valores) != len(categorias):
            return False
        numericos = []
        for valor in valores:
            try:
                numero = float(valor)
                if not math.isfinite(numero):
                    return False
            except (TypeError, ValueError, OverflowError):
                return False
            numericos.append(numero)
        series.append((tr, categorias, numericos))
    total = sum(len(valores) for _, _, valores in series)
    if total > limite:
        return False

    # Mesmo barmode='relative' (padrão do Plotly Express), C1–C5 são
    # barras INDEPENDENTES se cada categoria aparece em apenas um traço.
    # Se duas séries ocupam a mesma categoria em modo stack/relative,
    # evitar rótulos sobrepostos nas pilhas.
    barmode = str(getattr(fig.layout, 'barmode', None) or '')
    if barmode in ('stack', 'relative') and len(series) > 1:
        categorias = [str(cat) for _, xs, _ in series for cat in xs]
        if len(categorias) != len(set(categorias)):
            return False

    candidatos = {id(tr) for tr, _, _ in series
                  if getattr(tr, 'texttemplate', None) is None
                  and getattr(tr, 'text', None) is None}
    if not candidatos:
        return False
    eixo = _titulo_eixo(fig, 'xaxis' if horizontal else 'yaxis')
    sufixo = '%' if _eh_percentual(eixo) else ''
    for tr, _, valores in series:
        if id(tr) not in candidatos:
            continue
        textos = []
        for n in valores:
            # Formatação individual: bins de 0,0004% não devem virar 0,0%,
            # e valores de 23% não devem receber quatro casas decimais.
            magnitude = abs(n)
            casas = (0 if n.is_integer() else
                     4 if magnitude < .01 else
                     3 if magnitude < .1 else
                     2 if magnitude < 1 else 1)
            rotulo = (f'{n:,.{casas}f}'.replace(',', 'X')
                      .replace('.', ',').replace('X', '.') + sufixo)
            textos.append(rotulo)
        tr.update(text=textos, texttemplate='%{text}', textposition='outside',
                  textfont=dict(size=11, color='#25394B'), cliponaxis=False)
    margem = fig.layout.margin
    if horizontal:
        atual = margem.r if margem and margem.r else 0
        fig.update_layout(margin=dict(r=max(100, atual)))
    else:
        atual = margem.t if margem and margem.t else 0
        fig.update_layout(margin=dict(t=max(82, atual)))
    return True


def melhorar_figura(fig):
    """Ajustes não destrutivos em figuras Plotly, sem alterar nenhum valor numérico."""
    if fig is None or not hasattr(fig, 'data') or not hasattr(fig, 'update_layout'):
        return fig

    # Reservar espaço para anotações sobre os pontos, inclusive na impressão.
    tem_rotulos_fixos = bool(getattr(fig.layout, 'annotations', None))
    fig.update_layout(
        separators=',.',
        font=dict(family='Arial, sans-serif', size=13, color='#25394B'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hoverlabel=dict(namelength=-1),
        legend=dict(font=dict(size=12)),
        margin=dict(l=66, r=36, t=76 if tem_rotulos_fixos else 52, b=84),
    )
    fig.update_xaxes(automargin=True, showline=True, linecolor='#CCD6DF', ticks='outside')
    fig.update_yaxes(automargin=True, gridcolor='#E7EDF2', zeroline=False)

    barras = [tr for tr in fig.data if tr.type == 'bar']
    # Evita rótulos em barras empilhadas/agrupadas densas. Números continuam no hover.
    simples = len(barras) == 1 and str(getattr(fig.layout, 'barmode', '') or '') not in ('stack', 'relative')
    if simples:
        tr = barras[0]
        horiz = getattr(tr, 'orientation', None) == 'h'
        # Troca colunas por barras horizontais APENAS para uma série com
        # categorias muito extensas ou um ranking de UFs; mantém os valores,
        # customdata e hover de cada observação na mesma ordem.
        if not horiz and tr.x is not None and tr.y is not None:
            categorias = [str(v) for v in tr.x]
            siglas_uf = len(categorias) >= 20 and all(
                re.fullmatch(r'[A-Z]{2}', v) for v in categorias)
            extensas = (3 <= len(categorias) <= 15 and
                        max(map(len, categorias), default=0) >= 38 and
                        not all(re.search(r'\d', v) for v in categorias))
            if (siglas_uf or extensas) and len(_numeros(tr.y)) == len(categorias):
                valores = tuple(tr.y)
                rotulos = tuple(tr.x)
                anterior_x = _titulo_eixo(fig, 'xaxis')
                anterior_y = _titulo_eixo(fig, 'yaxis')
                tr.update(x=valores, y=rotulos, orientation='h')
                fig.update_xaxes(type='linear', title_text=anterior_y)
                fig.update_yaxes(type='category', title_text=anterior_x,
                                 categoryorder='total ascending' if siglas_uf else 'trace',
                                 autorange='reversed' if not siglas_uf else True)
                fig.update_layout(height=max(450, 25*len(categorias)+150),
                                  margin=dict(l=155, r=85, t=58, b=60))
                horiz = True
        numericos = _numeros(tr.x if horiz else tr.y)
        valores_eixo = tr.x if horiz else tr.y
        total_pontos = len(valores_eixo) if valores_eixo is not None else 0
        if 1 <= total_pontos <= 12 and len(numericos) == total_pontos and getattr(tr, 'text', None) is None:
            if all(abs(x - round(x)) < 1e-7 for x in numericos):
                casas = 0
            else:
                positivos = [abs(x) for x in numericos if x != 0]
                menor = min(positivos) if positivos else 1
                casas = 4 if menor < .01 else 3 if menor < .1 else 2 if menor < 1 else 1
            modelo = f'%{{{"x" if horiz else "y"}:,.{casas}f}}'
            titulo = _titulo_eixo(fig, 'xaxis' if horiz else 'yaxis')
            if _eh_percentual(titulo):
                modelo += '%'
            tr.update(texttemplate=modelo, textposition='outside', cliponaxis=False)
            fig.update_layout(margin=dict(l=75, r=80 if horiz else 38, t=68, b=85))
        if numericos and min(numericos) >= 0:
            if horiz:
                if fig.layout.xaxis.range is None:
                    fig.update_xaxes(rangemode='tozero')
            else:
                if fig.layout.yaxis.range is None:
                    fig.update_yaxes(rangemode='tozero')
        # Rankings de UFs: barra horizontal por estado, maior valor deve aparecer no topo.
        if horiz and tr.y is not None and len(tr.y) >= 15:
            nomes = [str(v) for v in tr.y]
            if len(nomes) == len(set(nomes)) and all(re.fullmatch('[A-Z]{2}', v) for v in nomes):
                if fig.layout.yaxis.categoryorder in (None, 'trace'):
                    fig.update_yaxes(categoryorder='total ascending')

    # Abrange as cinco colunas coloridas do IND-009 e outras barras curtas.
    # Atua depois do caso simples para não duplicar rótulos preexistentes.
    _rotular_barras_compactas(fig)

    # Evita intervalos fracionários no eixo temporal de anos (2019–2025).
    x_anos = []
    tem_ano_numerico = False
    for trace in fig.data:
        anos = _anos_eixo(getattr(trace, 'x', None))
        if anos:
            x_anos.extend(anos)
            tem_ano_numerico = tem_ano_numerico or any(not isinstance(v, str) for v in trace.x)
    if x_anos and len(set(x_anos)) <= 7:
        exclusivos = sorted(set(x_anos))
        if len(exclusivos) == 1 and all(t.type == 'bar' for t in fig.data):
            # Em gráfico de ano único não há interpolação entre anos.
            for trace in fig.data:
                if _anos_eixo(getattr(trace, 'x', None)):
                    trace.x = tuple(str(v) for v in trace.x)
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=[str(exclusivos[0])])
        elif tem_ano_numerico:
            fig.update_xaxes(tickmode='array', tickvals=exclusivos,
                             ticktext=[str(y) for y in exclusivos], dtick=1)

    for trace in fig.data:
        # Cor das cinco competências consistente entre as páginas do projeto.
        nome = str(getattr(trace, 'name', '') or '').strip()
        comp = re.match(r'^(C[1-5])(?:\b|\s*[-:–])', nome, flags=re.I)
        if comp:
            # O nome completo permanece disponível no glossário de C1–C5.
            # Legendas extensas eram cortadas nas comparações históricas.
            trace.update(name=comp.group(1).upper())
            cor = PALETA_COMP[comp.group(1).upper()]
            if trace.type == 'scatter':
                trace.update(line=dict(color=cor), marker=dict(color=cor))
            elif trace.type == 'bar':
                trace.update(marker_color=cor)
        if trace.type == 'heatmap':
            valores = getattr(trace, 'z', None)
            try:
                arr = [float(v) for row in valores for v in row if v is not None and math.isfinite(float(v))]
                celulas = sum(len(row) for row in valores)
            except (TypeError, ValueError):
                arr = [];celulas = 0
            if arr and celulas <= 36 and getattr(trace, 'texttemplate', None) is None:
                trace.update(texttemplate='%{z:.2f}', textfont=dict(size=11))
            if arr and min(arr) < 0 < max(arr) and getattr(trace, 'zmid', None) is None:
                trace.update(zmid=0)

    return fig


def _pt(numero: Any, decimais: int = 1) -> str:
    try:
        return f'{float(numero):,.{decimais}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return '—'


def _pt_int(numero: Any) -> str:
    try:
        return f'{int(numero):,}'.replace(',', '.')
    except (ValueError, TypeError):
        return '—'


def _grafico_essencial_catalogo(st, raiz: Path, numero: int, ano: int | None, uf: str) -> bool:
    """Melhorias de IND-002..005, 007 e 008 no renderizador didático legado.

    Só atua se essas fontes estiverem disponíveis e o catálogo chamar a função.
    Para o código mais recente, o wrapper universal do Plotly continua atuando.
    """
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    if numero == 8:
        fonte = Path(raiz) / 'outputs' / 'json' / 'IND_008_notas_1000.json'
        if not fonte.is_file():
            return False
        try:
            with fonte.open(encoding='utf-8-sig') as f:
                doc = json.load(f)
            linhas = []
            for registro in doc.get('years', []):
                if not isinstance(registro, dict):
                    continue
                yr = int(registro['ano'])
                if ano is not None and yr != int(ano):
                    continue
                if uf == 'BR':
                    d = registro.get('brasil')
                else:
                    d = next((v for v in registro.get('ufs', [])
                              if isinstance(v, dict) and v.get('uf') == uf), None)
                if not isinstance(d, dict):
                    continue
                # A fonte sinaliza recortes cuja contagem não pode ser publicada.
                if d.get('requer_revisao_privacidade') is True or d.get('suprimido') is True:
                    continue
                total, validas, pct = (d.get('n_notas_1000'), d.get('n_validas'),
                                       d.get('percentual'))
                if any(isinstance(v, bool) or v is None for v in (total, validas, pct)):
                    continue
                total, validas, pct = int(total), int(validas), float(pct)
                if not (validas >= 30 and 0 <= total <= validas and 0 <= pct <= 100
                        and math.isfinite(pct)):
                    continue
                if uf != 'BR' and 0 < total < 30:
                    continue
                if total > 0 and pct == 0:
                    pct = 100 * total / validas
                linhas.append({'ano': yr, 'quantidade': total,
                               'validas': validas, 'pct': pct})
        except (OSError, ValueError, TypeError, KeyError, StopIteration, OverflowError):
            return False
        if not linhas:
            st.info('Não há resultados de notas 1.000 divulgáveis para este recorte. '
                    'Um resultado indisponível não equivale a zero.')
            return True
        linhas.sort(key=lambda r: r['ano'])
        if ano is not None:
            d = linhas[0]
            st.metric('Redações com nota 1.000', _pt_int(d['quantidade']))
            st.metric('Percentual entre as redações válidas', f'{_pt(d["pct"], 4)}%')
            st.caption(f'Denominador: {_pt_int(d["validas"])} redações válidas. '
                       'Um percentual próximo de zero não significa inexistência de casos.')
        else:
            df = pd.DataFrame(linhas)
            if len(df) >= 2:
                fig = px.line(df, x='ano', y='pct', markers=True,
                              labels={'ano': 'Edição do ENEM',
                                      'pct': 'Redações com nota 1.000 (% das válidas)'})
                fig.update_xaxes(tickmode='array', tickvals=df['ano'].tolist())
                fig.update_yaxes(tickformat='.4f', rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)
            tabela = pd.DataFrame([{
                'Edição': r['ano'], 'Redações nota 1.000': _pt_int(r['quantidade']),
                'Redações válidas': _pt_int(r['validas']),
                'Percentual das válidas': f'{_pt(r["pct"], 4)}%'
            } for r in linhas])
            st.dataframe(tabela, hide_index=True, use_container_width=True)
            st.caption('Cada edição tem seu próprio denominador. '
                       'Casos com restrição de divulgação não são exibidos.')
        return True

    if numero not in (2, 3, 4, 5, 7):
        return False
    try:
        from graficos_educacionais_68 import dados_visuais
        dados = dados_visuais(Path(raiz), numero, ano, uf)
    except (ImportError, KeyError, ValueError, TypeError, FileNotFoundError):
        return False
    if not dados:
        return False

    if numero in (2, 3, 4):
        rotulo = {2:'Nota média',3:'Mediana da redação',4:'Desvio-padrão das notas'}[numero]
        if ano is not None:
            v = dados[0]
            st.metric(rotulo, f'{_pt(v["valor"], 1)} pontos')
            st.caption(f'Redações válidas no recorte: {_pt_int(v.get("n"))}. '
                       'Um único ano não constitui uma série temporal.')
        else:
            dt = pd.DataFrame(dados)
            fig = px.line(dt, x='ano', y='valor', markers=True,
                          labels={'ano':'Edição do ENEM','valor':f'{rotulo} (pontos)'})
            fig.update_traces(line_width=3, marker_size=9)
            fig.update_xaxes(tickvals=sorted(dt['ano'].unique()))
            # Esta camada visual substitui a função didática do catálogo para
            # IND-002/003/004. Os rótulos devem ser aplicados AQUI, na figura
            # efetivamente renderizada, e não só no módulo didático original.
            from rotulos_marcadores_plotly import rotular_marcadores
            rotular_marcadores(fig, casas=1)
            st.plotly_chart(fig, use_container_width=True)
            st.caption('Cada ponto representa uma edição independente do ENEM.')
        return True

    if numero == 5:
        percentis = ['p25','p50','p75','p90','p95']
        if ano is None:
            df = pd.DataFrame(dados)
            if not all(p in df.columns for p in percentis):
                return False
            longo = df.melt(id_vars=['ano'], value_vars=percentis,
                            var_name='Percentil',value_name='Nota (pontos)')
            longo['Percentil'] = longo['Percentil'].str.upper()
            fig = px.line(longo, x='ano', y='Nota (pontos)', color='Percentil', markers=True)
            fig.update_yaxes(range=[0, 1000])
        else:
            d = dados[0]
            if not all(k in d for k in percentis):
                return False
            # A tabela de cinco valores permanece visível mesmo em capturas
            # estáticas nas quais o navegador recorte uma barra do Plotly.
            for coluna, chave in zip(st.columns(5), percentis):
                coluna.metric(chave.upper(), f'{_pt(d[chave], 0)} pontos')
            df = pd.DataFrame({'Percentil': [p.upper() for p in percentis],
                               'Nota (pontos)': [d[p] for p in percentis]})
            fig = px.bar(df, x='Percentil', y='Nota (pontos)', text='Nota (pontos)')
            fig.update_xaxes(type='category', categoryorder='array',
                             categoryarray=[p.upper() for p in percentis])
            fig.update_traces(texttemplate='%{y:,.0f}', textposition='outside', cliponaxis=False)
            fig.update_yaxes(range=[0, 1050])
        st.plotly_chart(fig, use_container_width=True)
        st.caption('P25, P50, P75, P90 e P95 representam cortes da distribuição das notas.')
        return True

    if numero == 7 and ano is not None:
        categorias = dados[0].get('categorias')
        if not categorias:
            return False
        df = pd.DataFrame(categorias).sort_values('n', ascending=True)
        fig = px.bar(df, x='n', y='status', orientation='h',
                     labels={'n':'Quantidade de registros', 'status':'Situação registrada'})
        fig.update_traces(texttemplate='%{x:,.0f}', textposition='outside', cliponaxis=False)
        fig.update_layout(height=max(360, 52*len(df)), margin=dict(l=180, r=80, b=60, t=40))
        st.plotly_chart(fig, use_container_width=True)
        return True
    return False


def instalar_melhorias_visuais() -> None:
    """Instala ajustes visuais compartilhados; pode ser chamada repetidamente."""
    import streamlit as st
    if getattr(st, '_enem_visual_melhorado', False):
        return
    original = st.plotly_chart

    @functools.wraps(original)
    def _plotly_chart(fig, *args, **kwargs):
        try:
            melhorar_figura(fig)
        except Exception:
            # Manter a visualização funcionando em figuras de plugins incomuns.
            pass
        return original(fig, *args, **kwargs)

    st.plotly_chart = _plotly_chart
    st._enem_visual_melhorado = True

    # Ajuste dos poucos casos individuais para o renderizador didático legado.
    try:
        import painel_paginas_contrato_68 as painel
        original_didatico = painel.mostrar_grafico_didatico
        if not getattr(original_didatico, '_enem_corrigido', False):
            @functools.wraps(original_didatico)
            def _didatico(st_instance, raiz, numero, ano, uf):
                if numero in (2,3,4,5,7,8):
                    try:
                        if _grafico_essencial_catalogo(st_instance, Path(raiz), numero, ano, uf):
                            return True
                    except Exception:
                        pass
                return original_didatico(st_instance, raiz, numero, ano, uf)
            _didatico._enem_corrigido = True
            painel.mostrar_grafico_didatico = _didatico
    except (ImportError, AttributeError):
        pass

    st.markdown('''<style>
    [data-testid="stPlotlyChart"] {max-width:100%; overflow:visible;}
    [data-testid="stMetric"] {min-width:0;}
    [data-testid="stMetricLabel"] {white-space:normal;overflow-wrap:anywhere;}
    [data-testid="stMetricValue"] {overflow-wrap:anywhere;}
    @media (max-width:760px) {
      [data-testid="stPlotlyChart"] {padding:0!important;}
    }
    </style>''', unsafe_allow_html=True)
