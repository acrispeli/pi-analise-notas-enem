# -*- coding: utf-8 -*-
r"""Visualizador ENEM 2019–2025 | IND-001 a IND-022.

Instalar: .\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
Executar: .\.venv\Scripts\python.exe -m streamlit run visualizador.py
Apenas JSONs cumulativos agregados, nunca os microdados individuais.
"""
from __future__ import annotations

from pathlib import Path
from html import escape
import math
from plotly.colors import sample_colorscale
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from painel_dados_enem import (
    ANOS, UFS, NOMES_UF, localizar_dashboards, carregar_json, obter_recorte,
    serie_anual, agrupar_frequencias_niveis, classes_redacao, quantidade_segura,
    obter_hexbin_ind016, validar_hexbin_ind016,
    validar_avaliadores,
)

st.set_page_config(page_title='Redação no ENEM | Panorama', page_icon='📘', layout='wide', initial_sidebar_state='expanded')
ROOT = Path(__file__).resolve().parent
COR = '#2563A6'
COR_SEC = '#7D9CB8'
TEXTO = '#1C3447'
ESCALA = ['#DCE8F1', '#A8C7DA', '#588DAF', '#2563A6', '#193E64']

st.markdown('''<style>
:root {--primary-color:#2563A6}
.block-container {max-width:1180px; padding-top:1.2rem; padding-bottom:3rem}
[data-testid="stSidebar"] {background:#F6F9FC; min-width:230px; max-width:270px}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.42rem}
[data-testid="stMainBlockContainer"] {min-width:0}
h1,h2,h3,h4 {letter-spacing:-.024em;line-height:1.2}
h1 {font-size:clamp(1.85rem,3vw,2.65rem)!important}
[data-testid="stMetric"] {border:1px solid rgba(120,145,170,.2);border-radius:11px;padding:15px 17px;min-width:0}
[data-testid="stMetricLabel"] {white-space:normal!important;overflow:visible!important;line-height:1.2}
[data-testid="stMetricLabel"] p {white-space:normal!important;overflow-wrap:anywhere!important;font-size:.92rem!important}
[data-testid="stMetricValue"] {min-width:0}
[data-testid="stMetricValue"] > div {font-size:clamp(1.35rem,2.1vw,1.95rem)!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere!important;line-height:1.15}
[data-testid="stPlotlyChart"] {border:1px solid rgba(120,145,170,.16);border-radius:12px;padding:8px;max-width:100%;min-width:0}
[data-testid="stPlotlyChart"] .js-plotly-plot {max-width:100%}
hr {border-color:rgba(120,145,170,.20)}
header [data-testid="stToolbar"] {right:1rem}
/* O menu impresso é uma cópia estática da navegação.
   Não depende da visibilidade da sidebar interativa do Streamlit. */
.print-nav-espelho {display:none!important}
@media print {
 @page {size:A4 landscape;margin:10mm}
 /* A barra lateral dinâmica pode ser ocultada pelo próprio Streamlit ao imprimir. */
 [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
 header,[data-testid="stToolbar"],footer {display:none!important}
 [data-testid="stApp"],[data-testid="stAppViewContainer"] {overflow:visible!important}
 /* Reserva 61 mm para o menu e evita sobrepor os gráficos. */
 [data-testid="stMain"] {
   width:calc(100% - 61mm)!important;max-width:calc(100% - 61mm)!important;
   min-width:0!important;margin-left:61mm!important;overflow:visible!important;
 }
 .block-container,[data-testid="stMainBlockContainer"] {
   width:100%!important;max-width:100%!important;min-width:0!important;
   padding:0!important;margin:0!important;
 }
 .print-nav-espelho {
   display:block!important;position:fixed!important;left:0!important;top:0!important;
   width:54mm!important;height:100vh!important;box-sizing:border-box!important;
   padding:5mm 3mm 4mm 2mm!important;border-right:1px solid #c7d2df!important;
   background:white!important;color:#23384d!important;z-index:100!important;
   font-family:Arial,sans-serif!important;font-size:9pt!important;
   line-height:1.35!important;overflow:hidden!important;
   -webkit-print-color-adjust:exact;print-color-adjust:exact;
 }
 .print-nav-espelho .print-nav-marca {font-size:15pt;font-weight:700;margin-bottom:2mm;line-height:1.1}
 .print-nav-espelho .print-nav-subtitulo {font-size:8pt;color:#53687d;margin-bottom:4mm}
 .print-nav-espelho .print-nav-titulo {font-size:8pt;letter-spacing:.6px;color:#53687d;
   border-top:1px solid #c7d2df;padding-top:3mm;margin-bottom:2mm}
 .print-nav-espelho .print-nav-item {font-size:8.5pt;padding:1.2mm 2mm;
   border-left:2.5px solid transparent;margin-bottom:.4mm;white-space:normal}
 .print-nav-espelho .print-nav-item.ativa {font-weight:700;border-left-color:#2563a6!important;
   background:#eef4f9!important;color:#173e63!important}
 .print-nav-espelho .print-nav-recorte {margin-top:4mm;border-top:1px solid #c7d2df;
   padding-top:3mm;font-size:8.5pt;overflow-wrap:anywhere}
 .print-nav-espelho .print-nav-fim {font-size:7.7pt;color:#53687d;margin-top:3mm}
 [data-testid="stPlotlyChart"] {max-width:100%!important;overflow:visible!important;break-inside:avoid}
 [data-testid="stPlotlyChart"] .js-plotly-plot {max-width:100%!important}
 [data-testid="stMetric"] {break-inside:avoid}
 [data-testid="stMetricValue"] > div {font-size:1.45rem!important}
 h1,h2,h3,h4 {break-after:avoid}
}
@media (max-width:760px) {
 [data-testid="stMetricValue"] > div {font-size:1.35rem!important}
 .block-container {padding-left:1rem;padding-right:1rem}
}
</style>''', unsafe_allow_html=True)

PAGINAS = [
    'Visão geral', 'Notas e distribuição', 'Competências', 'Relações e PCA',
    'Perfis de redação', 'Evolução temporal',
    'Avaliação entre corretores', 'Alto desempenho', 'Contexto socioeconômico',
    'Modelos futuros', 'Metodologia',
]

def imprimir_menu_lateral(pagina_atual: str, recorte: str) -> None:
    """Menu estático exibido somente na impressão, sem alterar a navegação interativa.

    A cópia existe porque várias versões do Streamlit removem a sidebar no modo
    de impressão. O CSS posiciona a cópia à esquerda, inclusive em PDFs de
    múltiplas páginas, enquanto reserva largura para os gráficos.
    """
    itens = ''.join(
        '<div class="print-nav-item{}">{}</div>'.format(
            ' ativa' if nome == pagina_atual else '', escape(nome)
        ) for nome in PAGINAS
    )
    html = (
        '<aside class="print-nav-espelho" aria-label="Menu lateral para impressão">'
        '<div class="print-nav-marca">Redação no ENEM</div>'
        '<div class="print-nav-subtitulo">Painel de indicadores · UNIVESP</div>'
        '<div class="print-nav-titulo">NAVEGAÇÃO</div>'
        f'{itens}'
        '<div class="print-nav-recorte"><strong>Recorte da impressão</strong><div>'
        f'{escape(recorte)}</div></div>'
        '<div class="print-nav-fim">Indicadores disponíveis: IND-001 a IND-022</div>'
        '<div class="print-nav-fim">Projeto Integrador IV · UNIVESP</div>'
        '</aside>'
    )
    st.markdown(html, unsafe_allow_html=True)


COMP = {
    'C1':'Domínio da escrita formal',
    'C2':'Compreensão da proposta',
    'C3':'Argumentação',
    'C4':'Coesão textual',
    'C5':'Proposta de intervenção',
}


def pt_int(v):
    try:return f'{int(v):,}'.replace(',', '.')
    except (TypeError, ValueError):return '—'

def pt(v, casas=1):
    try:return f'{float(v):,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):return '—'

def bloco(titulo, desc, codigo=None):
    st.markdown(f'#### {titulo}')
    st.caption(desc + (f'  ·  {codigo}' if codigo else ''))

def grafico(fig, altura=335):
    fig.update_layout(
        height=altura, autosize=True, margin=dict(t=20,b=78,l=43,r=23),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Arial, sans-serif', size=12),
        colorway=ESCALA[::-1], legend=dict(orientation='h',y=-.29,x=0),
        hoverlabel=dict(namelength=-1),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor='rgba(120,145,170,.25)')
    fig.update_yaxes(gridcolor='rgba(120,145,170,.12)', zeroline=False, automargin=True)
    fig.update_xaxes(automargin=True)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

def grafico_bar(df, x, y, rotulo=None, orient='v', altura=335, title_color=None):
    fig=px.bar(df, x=x, y=y, orientation=orient, text_auto=False)
    fig.update_traces(marker_color=title_color or COR,hovertemplate='%{x}: %{y:,.2f}<extra></extra>')
    grafico(fig,altura)

def linha(df,x,y, label=None, h=340):
    fig=px.line(df,x=x,y=y,markers=True)
    fig.update_traces(line=dict(width=2.5,color=COR),marker=dict(size=7))
    grafico(fig,h)

def sem_dados():
    st.info('Não há dados agregados disponíveis para este recorte. Confira se o JSON cumulativo do ano selecionado foi gerado.')

def privacidade(mensagem='Este gráfico permanece reservado para revisão de privacidade e supressão complementar antes de divulgação externa.'):
    st.info(mensagem)

def obter(ind):
    try:return obter_recorte(referencia,anual,ind,ano,uf)
    except (KeyError, ValueError):return None

def selec_uf(row):
    return row.get('uf') if isinstance(row,dict) else None

def stat(ind, key):
    a=obter(ind)
    return a.get(key) if a else None

def score_periodo():
    d=obter(1) or {}
    return d.get('redacoes_validas'),d.get('total_registros'),d.get('percentual_validas')

def nome_escopo():
    return f"{'2019–2025' if ano is None else ano} · {'Brasil' if uf=='BR' else NOMES_UF[uf]}"

def boas_vindas():
    st.title('Panorama da redação no ENEM')
    st.caption('Uma leitura acessível dos resultados agregados das redações, de 2019 a 2025.')
    st.markdown('---')
    n,total,pct=score_periodo()
    media=stat(2,'mean_score')
    mediana=stat(3,'median_score')
    desv=stat(4,'std_score')
    # Duas colunas evitam corte de números longos na versão impressa.
    col=st.columns(2)
    col[0].metric('Redações válidas',pt_int(n),help='Participações com redação válida, não pessoas únicas')
    col[1].metric('Nota média',pt(media,1),help='Média da redação (0 a 1.000 pontos)')
    col=st.columns(2)
    col[0].metric('Mediana',pt(mediana,0),help='Metade das redações tem nota até este valor')
    col[1].metric('Desvio-padrão',pt(desv,1),help='Dispersão das notas em torno da média')
    st.caption(f"Recorte: **{nome_escopo()}**. {'Participações totais: '+pt_int(total)+'.' if total else ''} "
               'A UF representa o local da prova, não a residência.')
    x=obter(6)
    if x:
        bloco('Onde se concentram as notas?', 'Distribuição das notas totais, em faixas de 100 pontos. Cada coluna mostra a quantidade de redações naquela faixa.', 'IND-006')
        histograma_notas(x)
    bloco('Como as notas mudaram ao longo dos anos?', 'Série anual das notas médias do ENEM no recorte geográfico selecionado. O consolidado não é uma edição isolada.', 'IND-002')
    evolução_simplificada(2,'mean_score','Nota média')
    a=obter(5)
    if a:
        bloco('Faixas de desempenho', 'Os percentis mostram como as notas se distribuem, sem identificar os participantes.', 'IND-005')
        graf_percentis(a)


def histograma_notas(d):
    bins=d.get('bins') or []
    if not bins:return sem_dados()
    # Agrega de modo contíguo quando uma faixa positiva contém menos de 30.
    grupos=[{'faixa':str(v.get('faixa','')),'quantidade':int(v.get('quantidade',0))} for v in bins]
    i=0
    while i<len(grupos):
        if 0<grupos[i]['quantidade']<30 and len(grupos)>1:
            if i+1<len(grupos):
                grupos[i+1]['faixa']=grupos[i]['faixa']+' + '+grupos[i+1]['faixa']
                grupos[i+1]['quantidade']+=grupos[i]['quantidade']; grupos.pop(i)
            else:
                grupos[i-1]['faixa']+=' + '+grupos[i]['faixa']
                grupos[i-1]['quantidade']+=grupos[i]['quantidade'];grupos.pop(i);i-=1
        else:i+=1
    if any(0<r['quantidade']<30 for r in grupos):return privacidade()
    df=pd.DataFrame(grupos)
    fig=px.bar(df,x='faixa',y='quantidade')
    fig.update_traces(marker_color=COR,hovertemplate='%{x}<br>%{y:,.0f} redações<extra></extra>')
    fig.update_layout(xaxis_title='Nota total (pontos)',yaxis_title='Redações')
    fig.update_xaxes(tickangle=-25)
    grafico(fig)


def graf_percentis(d):
    p=d.get('percentiles') or {}
    if not p:return sem_dados()
    df=pd.DataFrame([{'Percentil':k.upper(),'Nota':p.get(k)} for k in ('p25','p50','p75','p90','p95') if p.get(k) is not None])
    fig=px.line(df,x='Percentil',y='Nota',markers=True)
    fig.update_traces(line_color=COR,marker=dict(size=9))
    fig.update_yaxes(range=[0,1000],title='Pontos')
    grafico(fig,315)


def evolução_simplificada(ind, campo, ylabel):
    lista=serie_anual(referencia,arquivos,ind,uf,ler_cached)
    df=pd.DataFrame([{'Ano':str(row['year']),ylabel:row[campo]} for row in lista if row.get(campo) is not None])
    if df.empty:return sem_dados()
    fig=px.line(df,x='Ano',y=ylabel,markers=True)
    fig.update_traces(line_color=COR,line_width=2.5,marker=dict(size=7))
    fig.update_layout(yaxis_title=ylabel)
    grafico(fig)
    if len(df)<len(ANOS): st.caption('A série da UF está incompleta: há dashboards anuais não encontrados na pasta outputs/json.')


def notas():
    st.title('Notas e distribuição')
    st.caption('Entenda quantidades, tendência central, dispersão e situações de redação.')
    bloco('Redações válidas', 'Quantidade de participações com redação válida em relação a todas as participações registradas.', 'IND-001')
    n,total,pct=score_periodo()
    c=st.columns(3);c[0].metric('Redações válidas',pt_int(n));c[1].metric('Total de registros',pt_int(total));c[2].metric('Percentual de válidas',pt(pct,1)+'%' if pct is not None else '—')
    bloco('Nota média', 'Nota média de todas as redações válidas do recorte. As médias históricas são ponderadas pelo número de redações.', 'IND-002')
    st.metric('Média (0–1.000)',pt(stat(2,'mean_score'),1))
    bloco('Mediana da redação', 'Valor que divide as redações ordenadas ao meio, reduzindo o efeito de notas extremas.', 'IND-003')
    st.metric('Mediana',pt(stat(3,'median_score'),0))
    bloco('Dispersão das notas', 'O desvio-padrão indica o quanto as notas se espalham em torno da média.', 'IND-004')
    st.metric('Desvio-padrão',pt(stat(4,'std_score'),1))
    bloco('Percentis de nota', 'P25, P50, P75, P90 e P95 indicam os pontos abaixo dos quais estão respectivamente 25%, 50%, 75%, 90% e 95% das redações.', 'IND-005')
    a=obter(5)
    if a:graf_percentis(a)
    else:sem_dados()
    bloco('Distribuição das notas', 'Contagem das redações por faixas de pontuação da prova de redação (0 a 1.000).', 'IND-006')
    a=obter(6)
    if a:histograma_notas(a)
    else:sem_dados()
    bloco('Situações da redação', 'Participações com redação sem problemas e outras situações oficiais, agrupadas para evitar exposição de categorias raras.', 'IND-007')
    a=obter(7)
    if a:
        rows=classes_redacao(a.get('categories'))
        if not rows or any(0<r['quantidade']<30 for r in rows):privacidade()
        else:
            fig=px.pie(pd.DataFrame(rows),names='categoria',values='quantidade',hole=.67,color_discrete_sequence=[COR,COR_SEC])
            fig.update_traces(textposition='outside',textinfo='percent+label')
            grafico(fig)
    else:sem_dados()
    bloco('Redações com nota 1.000', 'Quantidade de redações com a pontuação máxima. Valores raros não são apresentados individualmente.', 'IND-008')
    a=obter(8)
    if a:
        n=a.get('perfect_scores')
        seguro=quantidade_segura(n)
        if seguro is None: privacidade('A quantidade neste recorte é inferior a 30 e permanece oculta até a revisão de privacidade.')
        else:st.metric('Redações nota 1.000',pt_int(seguro))
    else:sem_dados()


def competencia_resumo(i, campo):
    d=obter(i)
    if not d:return []
    return d.get('summary',d.get('national_summary',[]))

def graf_comp_lista(lista,campo,ymax=200):
    df=pd.DataFrame([{'Competência':v.get('competency'),'Pontos':v.get(campo)} for v in lista if v.get(campo) is not None])
    if df.empty:return sem_dados()
    fig=px.bar(df,x='Competência',y='Pontos')
    fig.update_traces(marker_color=COR,hovertemplate='%{x}: %{y:.1f} pontos<extra></extra>')
    fig.update_yaxes(range=[0,ymax],title='Pontos')
    grafico(fig)

def comp_levels():
    d=obter(12)
    if not d:return sem_dados()
    summary=d.get('summary',d.get('national_summary',[]))
    rows=[]
    for entry in summary:
        grupo=agrupar_frequencias_niveis(entry.get('levels',[]))
        if not grupo:continue
        den=sum(x['quantidade'] for x in grupo)
        for f in grupo:
            rows.append({'Competência':entry['competency'],'Faixa':f['faixa'],'Percentual':100*f['quantidade']/den if den else 0})
    if not rows:return privacidade()
    df=pd.DataFrame(rows)
    # Faixas podem diferir entre competências por fusão protetiva.
    fig=px.bar(df,x='Competência',y='Percentual',color='Faixa',barmode='stack',color_discrete_sequence=ESCALA)
    fig.update_yaxes(range=[0,100],title='Participação (%)')
    grafico(fig,385)
    st.caption('As faixas são agrupadas para evitar a divulgação de frequências pequenas; detalhes por nota exata não são publicados.')

def competencias():
    st.title('As cinco competências')
    st.caption('Cada competência vale até 200 pontos. Leia os resultados como padrões agregados, não como diagnóstico individual.')
    with st.expander('O que significa cada competência?',expanded=False):
        for c,d in COMP.items():st.markdown(f'**{c}** — {d}.')
    bloco('Média das competências', 'Pontuação média em cada competência. Permite observar diferenças no desempenho agregado.', 'IND-009')
    graf_comp_lista(competencia_resumo(9,'mean_score'),'mean_score')
    bloco('Mediana das competências', 'Nota central de cada competência, calculada diretamente das frequências observadas.', 'IND-010')
    graf_comp_lista(competencia_resumo(10,'median_score'),'median_score')
    bloco('Variação do desempenho', 'Desvio-padrão por competência: valores maiores indicam maior dispersão das notas.', 'IND-011')
    a=competencia_resumo(11,'std_score')
    graf_comp_lista(a,'std_score',80)
    bloco('Amplitude entre quartis', 'Intervalo interquartil (P75 menos P25) de cada competência, uma medida robusta de dispersão.', 'IND-011')
    graf_comp_lista(a,'iqr_score',150)
    bloco('Faixas de pontuação por competência', 'Proporção de notas em faixas agrupadas, sem expor níveis raros.', 'IND-012')
    comp_levels()


def heatmap(matriz, titulo_eixo='Competência', labels=('C1','C2','C3','C4','C5'), zmin=None,zmax=None, reversa=False):
    if not matriz:return sem_dados()
    fig=go.Figure(data=go.Heatmap(
        z=matriz,x=list(labels),y=list(labels),zmin=zmin,zmax=zmax,
        colorscale='Blues' if not reversa else 'RdBu',
        text=[[pt(k,2) for k in row] for row in matriz],
        texttemplate='%{text}',textfont=dict(size=10),hovertemplate='%{y} × %{x}: %{z:.3f}<extra></extra>',
    ))
    fig.update_layout(xaxis_title=titulo_eixo,yaxis_title=titulo_eixo)
    grafico(fig,385)

def matriz_ind15(d):
    x=d.get('loadings')
    if not x:return None
    fig=go.Figure(data=go.Heatmap(z=x,x=list(COMP),y=[f'PC{i}' for i in range(1,len(x)+1)],
       colorscale='RdBu',zmid=0,zmin=-1,zmax=1,
       text=[[pt(y,2) for y in row] for row in x],texttemplate='%{text}',
       hovertemplate='%{y} × %{x}: %{z:.3f}<extra></extra>'))
    grafico(fig,395)

def relacoes():
    st.title('Relações entre competências e PCA')
    st.caption('Ferramentas estatísticas para compreender quais competências variam juntas e quais padrões resumem os resultados.')
    bloco('Correlação entre competências', 'Coeficiente de Spearman: valores próximos de 1 representam associação positiva forte entre as pontuações.', 'IND-013')
    a=obter(13)
    if a:
        forma=st.radio('Métrica',options=['Spearman','Pearson'],horizontal=True,key='forma_correlacao')
        heatmap(a.get(forma.lower()),zmin=-1,zmax=1)
    else:sem_dados()
    bloco('Quanto cada componente principal explica?', 'A PCA resume as cinco competências em cinco componentes. A variância explicada mede quanto da variação total cada PC representa.', 'IND-014')
    a=obter(14)
    if a:
        rows=[{'Componente':v.get('componente'),'Percentual':v.get('percentual_explicado')} for v in a.get('explained_variance',[])]
        if rows:
            fig=px.bar(pd.DataFrame(rows),x='Componente',y='Percentual');fig.update_traces(marker_color=COR)
            fig.update_layout(yaxis_title='Variância explicada (%)');grafico(fig)
        else:sem_dados()
    else:sem_dados()
    bloco('Peso das competências nos componentes', 'Os loadings mostram como cada competência contribui para a direção de cada componente. O sinal pode mudar de um recorte para outro.', 'IND-015')
    a=obter(15)
    if a:matriz_ind15(a)
    else:sem_dados()
    bloco('Mapa de concentração nos eixos PC1 e PC2', 'Representação agregada da distribuição das redações nas duas primeiras componentes principais.', 'IND-016')
    mapa_pca_agregado()


def mapa_pca_agregado():
    """Mostra apenas hexágonos pré-agregados e já liberados pelo IND-016.

    Não estima pontos individuais, não reagrupa anos/UFs e não tenta deduzir
    as contagens dos hexágonos omitidos. A publicação externa segue pendente.
    """
    rec = obter_hexbin_ind016(referencia, anual, ano, uf)
    pontos, erro = validar_hexbin_ind016(rec)
    if erro:
        st.info(erro + ' Confira o dashboard agregado correspondente ao filtro.')
        return

    raio = float(rec['raio_hex'])
    densidades = [math.log10(p['count']) for p in pontos]
    menor, maior = min(densidades), max(densidades)
    intervalo = max(maior - menor, 1e-12)
    fig = go.Figure()
    for p,log_n in zip(pontos,densidades):
        nivel = (log_n-menor)/intervalo
        cor = sample_colorscale('Blues', nivel)[0]
        theta = [math.pi/2 + i*math.pi/3 for i in range(7)]
        xs = [p['pc1']+raio*math.cos(t) for t in theta]
        ys = [p['pc2']+raio*math.sin(t) for t in theta]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode='lines', fill='toself',
            fillcolor=cor, line={'color':'rgba(255,255,255,0.8)','width':0.8},
            name='',showlegend=False, hoveron='fills',
            hovertemplate=(f"<b>Hexágono agregado</b><br>{pt_int(p['count'])} redações"
                           f"<br>PC1: {p['pc1']:.2f}<br>PC2: {p['pc2']:.2f}<extra></extra>"),
        ))
    # Barra quantitativa: cor = log10(contagem), mas marcadores exibem
    # valores absolutos. Não introduz qualquer ponto de participante.
    marcas=[x for x in range(1,9) if menor <= x <= maior]
    fig.add_trace(go.Scatter(
        x=[None,None],y=[None,None],mode='markers',showlegend=False,hoverinfo='skip',
        marker=dict(color=[menor,maior],colorscale='Blues',cmin=menor,cmax=maior,
                    showscale=True,size=1,colorbar=dict(title='Redações',
                    tickmode='array',tickvals=marcas,
                    ticktext=[pt_int(10**i) for i in marcas],len=.8,thickness=12))
    ))
    fig.update_layout(
        height=480,margin=dict(t=10,b=48,l=15,r=10),
        paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(title='Componente principal 1 (PC1)',showgrid=False,zeroline=True,
                   zerolinecolor='rgba(100,110,120,0.2)',constrain='domain'),
        yaxis=dict(title='Componente principal 2 (PC2)',showgrid=False,zeroline=True,
                   zerolinecolor='rgba(100,110,120,0.2)',scaleanchor='x',scaleratio=1),
        font=dict(family='Arial, sans-serif',size=12),
        hoverlabel=dict(namelength=-1),
    )
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    st.caption(
        f"**{pt_int(rec['n_hexagonos_exibidos'])} hexágonos exibidos** · "
        f"{pt(float(rec['fracao_coberta'])*100,4)}% das redações do recorte · "
        f"{pt_int(rec['n_hexagonos_suprimidos'])} hexágonos omitidos. "
        'Tons mais escuros representam maior concentração de redações. '
        'Cada hexágono reúne várias redações; nenhum ponto individual é exibido.'
    )
    st.caption(
        'A PCA foi ajustada separadamente para cada ano, UF e histórico. '
        'As coordenadas de recortes diferentes não devem ser sobrepostas nem '
        'interpretadas como uma trajetória individual.'
    )
    if rec.get('status_privacidade') != 'aprovado_publicacao':
        st.caption(
            'Aviso de publicação: o mapa está disponível para exploração interna, '
            'mas a revisão de privacidade complementar ainda está pendente. '
            'A visualização não significa aprovação para divulgação externa.'
        )


def perfis():
    st.title('Perfis de desempenho')
    st.caption('Aprendizado de máquina exploratório para organizar padrões das cinco competências.')
    a=obter(17);b=obter(18);c=obter(19)
    bloco('Características dos perfis', 'O K-Means organiza redações da amostra de treinamento segundo a similaridade de suas notas C1–C5. O centro é uma média de grupo, não uma nota oficial.', 'IND-017')
    if a and a.get('clusters'):
        rows=[]
        for cluster in a['clusters']:
            for comp, val in zip(COMP,cluster.get('centro_pontos',[])):
                rows.append({'Competência':comp,'Pontos':val,'Perfil':cluster['cluster_id']})
        if rows:
            fig=px.line(pd.DataFrame(rows),x='Competência',y='Pontos',color='Perfil',markers=True,color_discrete_sequence=ESCALA[::-1])
            fig.update_layout(yaxis_title='Pontuação média do centro (0–200)')
            fig.update_yaxes(range=[0,200]);grafico(fig,370)
    else:sem_dados()
    bloco('Quantas redações pertencem a cada perfil?', 'O IND-018 atribui todas as redações válidas aos centros obtidos pelo IND-017. Estes percentuais são populacionais, não percentuais da amostra de treinamento.', 'IND-018')
    if b and b.get('clusters'):
        df=pd.DataFrame([{'Perfil':x['cluster_id'],'Percentual (%)':x['percentual'],'Redações':x['n_redacoes']} for x in b['clusters']])
        fig=px.bar(df,x='Perfil',y='Percentual (%)',custom_data=['Redações'])
        fig.update_traces(marker_color=COR,hovertemplate='%{x}<br>%{y:.2f}%<br>%{customdata[0]:,.0f} redações<extra></extra>')
        grafico(fig)
    else:sem_dados()
    bloco('Qualidade dos agrupamentos', 'Silhouette maior indica grupos mais bem separados; Davies–Bouldin menor e Calinski–Harabasz maior são preferíveis dentro do mesmo recorte.', 'IND-019')
    if c:
        cols=st.columns(3)
        cols[0].metric('Silhouette',pt(c.get('silhouette'),3))
        cols[1].metric('Davies–Bouldin',pt(c.get('davies_bouldin'),3))
        cols[2].metric('Calinski–Harabasz',pt(c.get('calinski_harabasz'),0))
        comp=c.get('comparacao_k') or {}
        candidatos=[x for x in comp.get('candidatos',[]) if x.get('status')=='ok']
        bloco('Comparação de diferentes números de grupos', 'Compara soluções alternativas entre dois e oito grupos. A maior Silhouette não define, sozinha, o melhor número de perfis para fins pedagógicos.', 'IND-019')
        if candidatos:
            df=pd.DataFrame([{'Grupos (k)':str(x['k']),'Silhouette':x['silhouette']} for x in candidatos])
            fig=px.line(df,x='Grupos (k)',y='Silhouette',markers=True)
            fig.update_traces(line_color=COR,marker_size=8)
            grafico(fig)
            with st.expander('Ver também as demais métricas por número de grupos'):
                outro=pd.DataFrame([{'k':x['k'],'Davies–Bouldin':x['davies_bouldin'],'Calinski–Harabasz':x['calinski_harabasz']} for x in candidatos])
                st.dataframe(outro,hide_index=True,use_container_width=True)
        else:
            st.info('A comparação de k=2..8 está disponível para o Brasil; para UFs, a execução padrão calcula a qualidade do modelo existente com k=4.')
        st.caption('Os perfis são reajustados separadamente em cada UF e ano. P1 de um recorte não é necessariamente o mesmo P1 de outro. Quatro perfis continuam uma hipótese exploratória.')
    else:sem_dados()


def evolucao():
    st.title('Evolução temporal')
    st.caption('Como os resultados variaram entre 2019 e 2025. Selecione o assunto abaixo; a UF é mantida em todas as séries.')
    aba_notas,aba_comp,aba_pca,aba_perfis,aba_correcao=st.tabs([
        'Notas e redações','Competências','Relações e PCA','Perfis','Correção',
    ])
    with aba_notas:
        # Visão histórica por indicadores, sempre respeitando a UF selecionada.
        blocos=[
            (1,'Participações com redação válida','Quantas redações válidas ocorreram em cada edição.','redacoes_validas','Redações'),
            (2,'Nota média ao longo dos anos','Média anual de todas as redações válidas.','mean_score','Média'),
            (3,'Mediana ao longo dos anos','Ponto central da distribuição de cada edição.','median_score','Mediana'),
            (4,'Desvio-padrão por ano','Dispersão da pontuação total em cada edição.','std_score','Desvio-padrão'),
            (8,'Redações com nota máxima','Evolução do número de redações com 1.000 pontos, sujeito a restrições de privacidade.','perfect_scores','Redações'),
        ]
        for i,titulo,desc,campo,lbl in blocos:
            bloco(titulo,desc,f'IND-{i:03d}')
            if i==8:
                rows=serie_anual(referencia,arquivos,8,uf,ler_cached)
                if not rows:sem_dados();continue
                if any(quantidade_segura(r.get('perfect_scores')) is None for r in rows):
                    privacidade('A série contém pelo menos uma quantidade positiva inferior a 30; o gráfico temporal não é mostrado para evitar dedução de células pequenas.')
                    continue
            evolução_simplificada(i,campo,lbl)
        bloco('Percentis ao longo do tempo', 'Compara P25, mediana (P50) e P75 de cada edição.','IND-005')
        rows=serie_anual(referencia,arquivos,5,uf,ler_cached)
        faixas=[]
        for r in rows:
            for p in ('p25','p50','p75'):
                v=(r.get('percentiles') or {}).get(p)
                if v is not None:faixas.append({'Ano':str(r['year']),'Percentil':p.upper(),'Pontos':v})
        if faixas:
            fig=px.line(pd.DataFrame(faixas),x='Ano',y='Pontos',color='Percentil',markers=True,color_discrete_sequence=ESCALA[::-1]);grafico(fig)
        else:sem_dados()
        bloco('Composição das faixas de notas', 'Participação percentual de cada faixa na distribuição anual de notas.', 'IND-006')
        rows=serie_anual(referencia,arquivos,6,uf,ler_cached)
        hist=[];inseguro=False
        for r in rows:
            for b in r.get('bins',[]):
                if 0<int(b.get('quantidade',0))<30:inseguro=True
                hist.append({'Ano':str(r['year']),'Faixa':b['faixa'],'Participação (%)':b['percentual']})
        if inseguro:privacidade('Alguns anos apresentam faixas com menos de 30 redações. A comparação detalhada dessas faixas fica indisponível nesta prévia.')
        elif hist:
            fig=px.bar(pd.DataFrame(hist),x='Ano',y='Participação (%)',color='Faixa',barmode='stack',color_discrete_sequence=ESCALA*2)
            grafico(fig,410)
        else:sem_dados()
        bloco('Situações da redação por ano', 'Compara participações sem problemas e as demais situações de redação, agrupadas.', 'IND-007')
        cats=[]
        for r in serie_anual(referencia,arquivos,7,uf,ler_cached):
            for e in classes_redacao(r.get('categories')):
                cats.append({'Ano':str(r['year']),**e})
        if cats and not any(0<e['quantidade']<30 for e in cats):
            catdf=pd.DataFrame(cats)
            den=catdf.groupby('Ano')['quantidade'].transform('sum')
            catdf['Participação (%)']=catdf['quantidade']/den*100
            fig=px.bar(catdf,x='Ano',y='Participação (%)',color='categoria',barmode='stack',color_discrete_sequence=[COR,COR_SEC])
            grafico(fig)
        else:privacidade()
    with aba_comp:
        # Cada indicador específico pode ser consultado nas outras páginas. Expor
        # séries aqui apenas quando comparações entre anos preservam o significado.
        bloco('Médias das competências ao longo dos anos', 'Notas médias anuais das cinco competências (C1–C5).', 'IND-009')
        rows=[]
        for r in serie_anual(referencia,arquivos,9,uf,ler_cached):
            for c in r.get('summary',[]):rows.append({'Ano':str(r['year']),'Competência':c['competency'],'Pontos':c['mean_score']})
        if rows:
            fig=px.line(pd.DataFrame(rows),x='Ano',y='Pontos',color='Competência',markers=True,color_discrete_sequence=ESCALA[::-1]);grafico(fig)
        else:sem_dados()
        bloco('Medianas das competências', 'Notas centrais das cinco competências em cada edição.', 'IND-010')
        rows=[]
        for r in serie_anual(referencia,arquivos,10,uf,ler_cached):
            for c in r.get('summary',[]):rows.append({'Ano':str(r['year']),'Competência':c['competency'],'Pontos':c['median_score']})
        if rows:
            fig=px.line(pd.DataFrame(rows),x='Ano',y='Pontos',color='Competência',markers=True,color_discrete_sequence=ESCALA[::-1]);grafico(fig)
        else:sem_dados()
        bloco('Dispersão das competências', 'Desvio-padrão anual das notas de C1 a C5.', 'IND-011')
        rows=[]
        for r in serie_anual(referencia,arquivos,11,uf,ler_cached):
            for c in r.get('summary',[]):rows.append({'Ano':str(r['year']),'Competência':c['competency'],'Pontos':c['std_score']})
        if rows:
            fig=px.line(pd.DataFrame(rows),x='Ano',y='Pontos',color='Competência',markers=True,color_discrete_sequence=ESCALA[::-1]);grafico(fig)
        else:sem_dados()
        bloco('Distribuição dos níveis por competência', 'As distribuições completas estão disponíveis na página Competências para o ano ou histórico escolhido.', 'IND-012')
        st.caption('Para evitar células raras, a visualização detalhada utiliza faixas de nota agregadas na página Competências.')
    with aba_pca:
        bloco('Associação entre competências no tempo', 'Exemplo: correlação de Spearman entre C1 e C2 ao longo dos anos.', 'IND-013')
        rows=[]
        for r in serie_anual(referencia,arquivos,13,uf,ler_cached):
            m=r.get('spearman')
            if m:rows.append({'Ano':str(r['year']),'Correlação C1 × C2':m[0][1]})
        if rows:linha(pd.DataFrame(rows),'Ano','Correlação C1 × C2')
        else:sem_dados()
        bloco('Variância explicada da PC1', 'Percentual de variação das competências resumido pela primeira componente principal.', 'IND-014')
        rows=[]
        for r in serie_anual(referencia,arquivos,14,uf,ler_cached):
            if r.get('explained_variance'):rows.append({'Ano':str(r['year']),'Variância explicada (%)':r['explained_variance'][0]['percentual_explicado']})
        if rows:linha(pd.DataFrame(rows),'Ano','Variância explicada (%)')
        else:sem_dados()
        bloco('Contribuições da PCA por edição', 'Os loadings são recalculados em cada recorte; sinais e orientações podem variar, e não devem ser comparados diretamente sem alinhamento.', 'IND-015')
        st.caption('Confira os coeficientes PC1–PC5 do recorte escolhido na página Relações e PCA.')
        bloco('Distribuição agregada PC1×PC2', 'Hexágonos representam quantidades de redações semelhantes na projeção PCA. Os modelos são próprios de cada ano e UF.', 'IND-016')
        mapa_pca_agregado()
    with aba_perfis:
        bloco('Perfis da redação no tempo', 'Cada ano utiliza seu próprio K-Means. Os rótulos P1–P4 não representam necessariamente os mesmos grupos em anos diferentes.', 'IND-017')
        st.caption('Para comparar trajetórias pedagógicas entre anos é necessário alinhar os modelos; consulte os perfis isolados na página Perfis de redação.')
        bloco('Distribuição dos clusters no tempo', 'Percentuais populacionais existem por edição, mas comparar P1–P4 diretamente entre anos pode produzir interpretações enganosas.', 'IND-018')
        st.caption('As distribuições individuais de cada recorte aparecem em Perfis de redação.')
        bloco('Qualidade do K-Means por edição', 'Comparação da Silhouette dos modelos de cada ano. Essa é uma métrica interna de separação e não uma nota da prova.', 'IND-019')
        rows=[]
        for r in serie_anual(referencia,arquivos,19,uf,ler_cached):
            if r.get('silhouette') is not None:rows.append({'Ano':str(r['year']),'Silhouette':r['silhouette']})
        if rows:linha(pd.DataFrame(rows),'Ano','Silhouette')
        else:sem_dados()

    with aba_correcao:
        grafico_temporal_avaliadores()


def histograma_diferencas_avaliadores(d):
    """Barras categóricas; faixas têm larguras variáveis, sem densidade implícita."""
    itens=d.get('histograma') or []
    if not itens:
        return sem_dados()
    dados=[]
    for x in itens:
        dados.append({'Faixa de diferença':x['faixa'],
                      'Participação (%)':float(x['percentual']),
                      'Redações':int(x['n_redacoes'])})
    df=pd.DataFrame(dados)
    fig=px.bar(df,x='Faixa de diferença',y='Participação (%)',custom_data=['Redações'])
    fig.update_traces(marker_color=COR,
         hovertemplate='%{x}<br>%{y:.2f}%<br>%{customdata[0]:,.0f} avaliações<extra></extra>')
    fig.update_layout(yaxis_title='Avaliações (%)',xaxis_title='Diferença absoluta na nota total (pontos)')
    fig.update_xaxes(tickangle=-30,categoryorder='array',categoryarray=df['Faixa de diferença'].tolist())
    grafico(fig,395)
    st.caption('Cada barra representa a porcentagem naquela faixa. As faixas têm larguras diferentes ' 
               '(agrupamento realizado na geração dos dados), portanto suas alturas **não representam densidade por ponto**.')


def graf_competencias_avaliadores(d):
    cs=d.get('competencias') or []
    if len(cs)!=5:
        return sem_dados()
    df=pd.DataFrame([{'Competência':x['competencia'],
                      'Diferença média (pontos)':float(x['media']),
                      'P90 (pontos)':float(x['p90']),
                      'Mediana':float(x['mediana'])} for x in cs])
    fig=px.bar(df,x='Competência',y='Diferença média (pontos)',custom_data=['P90 (pontos)','Mediana'])
    fig.update_traces(marker_color=COR,
          hovertemplate='%{x}<br>Média: %{y:.2f} pontos<br>P90: %{customdata[0]:.0f}<br>Mediana: %{customdata[1]:.0f}<extra></extra>')
    fig.update_yaxes(range=[0,60])
    grafico(fig)
    st.caption('A média considera o valor absoluto da diferença entre as duas notas; '
               'não informa qual avaliador atribuiu a maior pontuação.')


def boxplot_agregado_avaliadores(d):
    """Caixas a partir de quartis publicados; NÃO utiliza pontos sintéticos."""
    cs=d.get('competencias') or []
    if len(cs)!=5:
        return sem_dados()
    fig=go.Figure()
    for i,c in enumerate(cs):
        box=c.get('boxplot') or {}
        fig.add_trace(go.Box(
            name=c['competencia'],q1=[box['q1']],median=[box['mediana']],
            q3=[box['q3']],lowerfence=[box['bigode_inferior']],
            upperfence=[box['bigode_superior']],
            marker_color=ESCALA[::-1][i],fillcolor=ESCALA[::-1][i],
            boxpoints=False,showlegend=False,
            hovertemplate='%{y:.0f} pontos<extra></extra>',
        ))
    fig.update_layout(yaxis_title='Diferença absoluta (0–200 pontos)',xaxis_title='Competência',boxmode='group')
    fig.update_yaxes(range=[0,210])
    grafico(fig,385)
    st.caption('Boxplots **resumidos**, calculados com quartis e limites dos bigodes já agregados no IND-021. '
               'Não representam avaliações individuais e não exibem pontos extremos.')


def graf_discrepancias_motivos(d):
    n=float(d['n_pop_evaluator'])
    campos=[
        ('Nota total > 100', 'n_criterio_total_gt100'),
        ('Alguma C1–C5 > 80', 'n_criterio_comp_gt80'),
        ('Situação divergente', 'n_criterio_status_divergente'),
    ]
    df=pd.DataFrame([{'Critério':label,'Percentual das avaliações':100*int(d[k])/n,
                      'Quantidade':int(d[k])} for label,k in campos])
    fig=px.bar(df,x='Percentual das avaliações',y='Critério',orientation='h',custom_data=['Quantidade'])
    fig.update_traces(marker_color=COR,
         hovertemplate='%{y}<br>%{x:.2f}%<br>%{customdata[0]:,.0f} avaliações<extra></extra>')
    fig.update_layout(xaxis_title='Participação no total de avaliações pareadas (%)',yaxis_title=None)
    fig.update_yaxes(categoryorder='array',categoryarray=list(reversed(df['Critério'].tolist())))
    fig.update_xaxes(range=[0,max(df['Percentual das avaliações'])*1.13])
    grafico(fig,310)
    st.caption('**Os motivos se sobrepõem.** Uma mesma redação pode satisfazer mais de um critério; '
               'não some as barras. Os limites são estritos: diferença de exatamente 100 ou 80 pontos, isoladamente, não aciona o critério.')


def serie_avaliadores(ind):
    return serie_anual(referencia,arquivos,ind,uf,ler_cached)


def grafico_temporal_avaliadores():
    # IND-020
    bloco('Evolução da diferença na nota total',
          'Diferença absoluta média, em pontos, entre as notas totais dos dois avaliadores.', 'IND-020')
    rows=[{'Ano':str(x['year']),'Diferença média (pontos)':x['media']} for x in serie_avaliadores(20)
          if x.get('media') is not None]
    if rows:
        linha(pd.DataFrame(rows),'Ano','Diferença média (pontos)')
    else:sem_dados()
    # IND-021
    bloco('Diferença média anual por competência',
          'Compare como a diferença média nas competências C1–C5 se altera entre as edições.', 'IND-021')
    rows=[]
    for r in serie_avaliadores(21):
        for c in r.get('competencias',[]):
            rows.append({'Ano':str(r['year']),'Competência':c['competencia'],
                         'Diferença média (pontos)':c['media']})
    if rows:
        df=pd.DataFrame(rows)
        fig=px.line(df,x='Ano',y='Diferença média (pontos)',color='Competência',markers=True,
                    color_discrete_sequence=ESCALA[::-1])
        fig.update_layout(yaxis_title='Diferença média (pontos)')
        grafico(fig,405)
    else:sem_dados()
    # IND-022
    bloco('Evolução do percentual de discrepâncias',
          'Parcela de avaliações pareadas que satisfaz pelo menos um dos critérios do edital de 2024. '
          'O mesmo critério foi aplicado aos demais anos apenas para comparabilidade.', 'IND-022')
    rows=[{'Ano':str(r['year']), 'Discrepâncias (%)':r['percentual_discrepancia_confirmada_pop_evaluator']}
          for r in serie_avaliadores(22)
          if r.get('percentual_discrepancia_confirmada_pop_evaluator') is not None]
    if rows:
        linha(pd.DataFrame(rows),'Ano','Discrepâncias (%)')
    else:sem_dados()
    st.caption('Variações ao longo dos anos não provam mudanças na qualidade dos avaliadores, no processo de correção '
               'ou na dificuldade do tema. Os percentuais são resultados do projeto, não taxas oficiais publicadas pelo INEP.')


def avaliadores():
    st.title('Avaliação entre corretores')
    st.caption('Compare as notas dos dois primeiros avaliadores da redação. Diferenças de pontuação não são, por si, erros de correção.')
    st.info('**População diferente da página de notas:** aqui são consideradas avaliações com ambas as notas totais '
            'dos dois primeiros avaliadores válidas (POP_EVALUATOR). É diferente da população de redações válidas (POP_VALID).')
    a,b,c=obter(20),obter(21),obter(22)
    erros=validar_avaliadores(a,b,c)
    if erros:
        st.warning('Os três indicadores ainda não estão integrados de forma consistente para o filtro escolhido. '
                   'Para evitar interpretações incorretas, os gráficos ficam suspensos.')
        for erro in erros:st.caption('• '+erro)
        st.caption('Confirme os sete arquivos outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json '
                   'e as versões completas dos IND-020, IND-021 e IND-022.')
        return

    aba20,aba21,aba22,aba_tempo=st.tabs([
        'Diferença total · IND-020','Por competência · IND-021',
        'Discrepâncias · IND-022','Evolução anual',
    ])
    with aba20:
        bloco('Quanto os dois avaliadores diferem na nota total?',
              'Distribuição e estatísticas da diferença absoluta entre as duas notas totais (escala 0–1.000).', 'IND-020')
        col=st.columns(2)
        col[0].metric('Avaliações pareadas',pt_int(a['n_avaliacoes_pareadas']))
        col[1].metric('Diferença média',pt(a['media'],2)+' pontos')
        col=st.columns(2)
        col[0].metric('Diferença mediana',pt(a['mediana'],0)+' pontos')
        col[1].metric('Percentil 90',pt(a['p90'],0)+' pontos')
        bloco('Distribuição das diferenças totais',
              'Percentual de avaliações em cada faixa de diferença entre AV1 e AV2. Os intervalos podem ter amplitudes distintas.', 'IND-020')
        histograma_diferencas_avaliadores(a)
        st.caption('A média do IND-020 não é a soma das médias do IND-021: diferenças positivas e negativas por competência '
                   'podem se compensar quando se calcula a diferença da nota total.')
    with aba21:
        bloco('Em quais competências os avaliadores mais diferem?',
              'Diferença absoluta média na nota de cada competência, entre 0 e 200 pontos.', 'IND-021')
        col=st.columns(2)
        col[0].metric('Avaliações com cinco pares completos',pt_int(b['n_competencias_pareadas']))
        col[1].metric('Cobertura das competências',pt(b['percentual_cobertura_competencias'],1)+'%')
        graf_competencias_avaliadores(b)
        bloco('Distribuição resumida das diferenças por competência',
              'Os boxplots indicam mediana, quartis e limites dos bigodes a partir dos resultados agregados.', 'IND-021')
        boxplot_agregado_avaliadores(b)
        with st.expander('Consultar média, mediana e P90 de cada competência'):
            st.dataframe(pd.DataFrame([{
                'Competência':x['competencia'],'Média (pontos)':x['media'],
                'Mediana (pontos)':x['mediana'],'P90 (pontos)':x['p90'],
                'Desvio-padrão':x['desvio_padrao']
                } for x in b['competencias']]),hide_index=True,use_container_width=True)
        st.caption('Uma competência com diferença média maior não é necessariamente mais subjetiva: '
                   'o indicador não identifica os motivos da divergência nem qual avaliador estaria correto.')
    with aba22:
        bloco('Qual parcela apresentou discrepância pelos critérios do ENEM 2024?',
              'Considera diferença total >100 pontos, diferença >80 em qualquer competência ou situação da redação diferente entre avaliadores.', 'IND-022')
        col=st.columns(2)
        col[0].metric('Com discrepância',pt(c['percentual_discrepancia_confirmada_pop_evaluator'],2)+'%')
        col[1].metric('Redações com discrepância',pt_int(c['n_discrepancia_confirmada']))
        col=st.columns(2)
        col[0].metric('Sem discrepância confirmada',pt_int(c['n_sem_discrepancia_confirmada']))
        col[1].metric('Classificação indeterminada',pt_int(c['n_indeterminada']))
        bloco('Quais critérios foram acionados?',
              'Contagem de cada motivo de discrepância, incluindo sobreposições.', 'IND-022')
        graf_discrepancias_motivos(c)
        st.caption('Critério do edital de **2024**, aplicado de maneira padronizada a 2019–2025 para comparação. '
                   'Não se afirma que os editais de todos os anos continham regras idênticas. '
                   'Estas taxas foram calculadas pelo estudo, não são índices oficiais divulgados pelo INEP.')
    with aba_tempo:
        st.markdown('#### O que mudou entre os anos?')
        st.caption('As três séries respeitam a UF selecionada; sempre usam recortes anuais originais, não médias dos modelos históricos.')
        grafico_temporal_avaliadores()


def futura(titulo, texto):
    st.title(titulo)
    st.caption(texto)
    st.markdown('---')
    st.info('Página preparada para os próximos indicadores. Nenhum resultado é exibido até passar pela validação técnica e pela integração ao painel.')


def metodologia():
    st.title('Sobre os dados e a metodologia')
    st.caption('Entenda o significado e as limitações do que aparece neste painel.')
    st.markdown('''**O que é analisado?** Redações do Exame Nacional do Ensino Médio (ENEM), nas edições de 2019 a 2025, agregadas por ano e unidade federativa de realização da prova.

**Todos os anos** representa o consolidado histórico calculado pelos indicadores, e não uma média simples dos valores anuais. São participações em exames, **não pessoas únicas**.

**Todos os estados (Brasil)** é o consolidado nacional. Ao escolher uma UF, os resultados dizem respeito ao **local de aplicação da prova (`SG_UF_PROVA`)**, e não necessariamente à residência ou à escola do participante.

**Notas e competências**: a nota total vai de 0 a 1.000 pontos, e cada competência de C1 a C5 vai até 200 pontos. A definição de redação válida segue os metadados dos indicadores.

**Perfis por inteligência artificial**: o IND-017 treinou modelos K-Means com amostras de até 4.000 redações por recorte. O IND-018 classificou todas as redações válidas nos perfis desses modelos. O IND-019 avaliou os agrupamentos; os resultados nacionais indicam que soluções com dois grupos tiveram melhor separação interna que quatro grupos, mas isso não determina sozinho a quantidade pedagogicamente adequada.

**Privacidade**: o IND-016 é exibido para **exploração interna** usando apenas hexágonos com pelo menos 30 redações; células menores já foram omitidas no processamento. A revisão de supressão complementar permanece pendente para publicação externa. Este visualizador oculta ou agrega informações potencialmente sensíveis, **mas não substitui uma auditoria formal de privacidade**.

**Situação acadêmica**: os JSONs podem ter status `draft`; validação computacional não significa aprovação para divulgação pública. Os indicadores IND-020, IND-021 e IND-022 são exibidos na página Avaliação entre corretores, apenas como resultados agregados em estado draft.''')
    with st.expander('Fontes locais utilizadas'):
        for y,p in sorted(arquivos.items()):st.write(f'{y}: `{p}`')
        st.write('Nenhum CSV de microdados é lido pelo visualizador.')
    with st.expander('Método de cada indicador (IND-001 a IND-022)'):
        m=referencia.get('pages',{}).get('methodology',{})
        for i in range(1,23):
            entry=m if i==1 else m.get(f'ind{i:03d}',{})
            if entry:
                with st.expander(f'IND-{i:03d}'):
                    for k in ['definition','calculation','population','method','limitations','cautions','privacy_note']:
                        if isinstance(entry.get(k),(str,int,float)):st.write(f'**{k}:** {entry[k]}')


@st.cache_data(show_spinner=False)
def _ler_cache(caminho: Path, versao: int):
    return carregar_json(caminho)

def ler_cached(caminho: Path):
    return _ler_cache(caminho, caminho.stat().st_mtime_ns)

# Navegação e filtros. Defaults reais: todos os anos e Brasil.
with st.sidebar:
    st.markdown('### Redação no ENEM')
    st.caption('Painel de indicadores · UNIVESP')
    st.markdown('---')
    st.caption('NAVEGAÇÃO')
    pagina=st.radio('Páginas',PAGINAS,label_visibility='collapsed',key='pagina_ativa')
    st.markdown('---')
    st.caption('Disponíveis: IND-001 a IND-022')
    st.caption('Em preparação: IND-023 em diante')
    if st.button('Atualizar dados', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

arquivos=localizar_dashboards(ROOT)
if not arquivos:
    st.error('Não encontrei os dashboards. Coloque este arquivo na raiz do projeto, junto à pasta outputs/json com dashboard_enem_2019.json ... dashboard_enem_2025.json.')
    st.stop()

ref_ano=2024 if 2024 in arquivos else next(reversed(sorted(arquivos)))
try:
    referencia=ler_cached(arquivos[ref_ano])
except (OSError,ValueError) as exc:
    st.error(f'Falha ao carregar o dashboard de referência ({ref_ano}): {exc}')
    st.stop()

cab1,cab2,cab3=st.columns([1.45,1.3,1.55])
with cab1:
    st.caption('FILTROS DA ANÁLISE')
    st.markdown('Os filtros valem para todas as páginas.')
with cab2:
    selecionado=st.selectbox('Ano',['Todos os anos']+[str(a) for a in ANOS],index=0,key='ano_filtro')
with cab3:
    opts=['Todos os estados (Brasil)']+[f'{NOMES_UF[c]} ({c})' for c in UFS]
    selecionada=st.selectbox('Local da prova',opts,index=0,key='uf_filtro')

ano=None if selecionado=='Todos os anos' else int(selecionado)
uf='BR' if selecionada.startswith('Todos os estados') else selecionada.rsplit('(',1)[-1][:-1]
anual=None
if ano is not None:
    if ano not in arquivos:
        st.warning(f'Para consultar o mapa de {ano}, é necessário o arquivo `dashboard_enem_{ano}.json` em outputs/json. Não exibirei dados de outro ano como substituição.')
    else:
        try:anual=ler_cached(arquivos[ano])
        except (OSError,ValueError) as exc:st.error(f'Falha ao carregar {ano}: {exc}')

st.caption(f'**Recorte atual:** {nome_escopo()}')
imprimir_menu_lateral(pagina, nome_escopo())
st.divider()
if pagina=='Visão geral':boas_vindas()
elif pagina=='Notas e distribuição':notas()
elif pagina=='Competências':competencias()
elif pagina=='Relações e PCA':relacoes()
elif pagina=='Perfis de redação':perfis()
elif pagina=='Evolução temporal':evolucao()
elif pagina=='Avaliação entre corretores':avaliadores()
elif pagina=='Alto desempenho':futura('Alto desempenho','Espaço reservado para análises futuras de alto desempenho.')
elif pagina=='Contexto socioeconômico':futura('Contexto socioeconômico','Espaço reservado para análises futuras de condições socioeconômicas.')
elif pagina=='Modelos futuros':futura('Modelos futuros','Espaço reservado para novas análises de aprendizado de máquina.')
elif pagina=='Metodologia':metodologia()

st.divider()
st.caption('Projeto Integrador IV — UNIVESP · Dados agregados · Versão de demonstração local · Revisões acadêmica e de privacidade pendentes.')
