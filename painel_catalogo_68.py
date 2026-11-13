# -*- coding: utf-8 -*-
"""Catálogo interno de 68 indicadores: somente saídas agregadas locais.

Não utiliza microdados, aplica autorização e proteção de células pequenas
na apresentação V2 e não confunde IND-054 com clusters V2.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px

from publicacao_segura_v2 import preparar_doc_publico_v2, mostrar_aviso_publicacao_v2

EXCLUIDOS = frozenset({60, 61, 62, 63})
V2 = frozenset({55, 56, 57, 58, 59, 68})
IDS = tuple(n for n in range(1, 73) if n not in EXCLUIDOS)
NOMES = {
    55: 'Nota da redação por perfil material',
    56: 'Competências por perfil material',
    57: 'Notas elevadas por perfil material',
    58: 'Descontos nas competências (900–980)',
    59: 'Divergência entre avaliadores por perfil',
    68: 'Evolução temporal dos perfis materiais',
}
# Rótulos apenas de APRESENTAÇÃO; C1/C2/C3 seguem intactos nos JSONs.
# O prefixo M distingue perfis materiais das competências C1–C5 e dos
# agrupamentos de desempenho P1–P4 dos IND-017/018.
PERFIS = {
    'C1': 'M1 · Menor disponibilidade de bens',
    'C2': 'M2 · Maior disponibilidade de bens',
    'C3': 'M3 · Restrições materiais acentuadas',
}
CORES_PERFIS = {'M1':'#2667A9','M2':'#D97706','M3':'#1F8A70'}
DESCRICAO_PERFIS = ('M1: menor disponibilidade relativa de bens domésticos; '
                     'M2: maior disponibilidade relativa de bens; '
                     'M3: restrições materiais mais acentuadas. '
                     'São agrupamentos de uma amostra, não níveis de competência nem classes sociais.')


def _tabela_com_rotulos_materiais(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara só a tabela mostrada; não altera números nem códigos de origem."""
    tabela = df.copy()
    origem = 'cluster' if 'cluster' in tabela.columns else 'cluster_referencia'
    if origem in tabela.columns:
        tabela['Perfil material'] = tabela[origem].map(PERFIS).fillna(tabela[origem])
        # O status técnico da linha (rascunho histórico do processamento)
        # não representa a autorização atual de apresentação do indicador.
        tabela = tabela.drop(columns=['cluster', 'cluster_referencia',
                                      'Perfil', 'status'], errors='ignore')
        outras = [c for c in tabela.columns if c != 'Perfil material']
        return tabela[['Perfil material', *outras]]
    return tabela.drop(columns=['Perfil'], errors='ignore')


def fontes_do_indicador(raiz: Path, ind: int) -> list[Path]:
    """Retorna TODAS as variantes, preservando IND-001/034; preferência explícita."""
    if ind not in IDS:
        return []
    base = raiz / 'outputs' / 'json'
    arquivos = sorted(base.glob(f'IND_{ind:03d}_*.json'))
    if not arquivos and ind in V2:
        arquivos = sorted((raiz / 'outputs/rascunho_ponte_v2/json').glob(f'IND_{ind:03d}_*.json'))
    if ind == 1:
        arquivos.sort(key=lambda p: (p.name != 'IND_001_redacoes_validas.json', p.name))
    if ind == 34:
        arquivos.sort(key=lambda p: (p.name != 'IND_034_competencia_unica_impede_1000.json', p.name))
    return arquivos


def inventario(raiz: Path) -> dict[int, list[Path]]:
    return {i: fontes_do_indicador(raiz, i) for i in IDS}


def abrir_json(path: Path) -> dict:
    with path.open(encoding='utf-8-sig') as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f'O arquivo {path.name} não contém objeto JSON')
    return value


def linhas_agrupadas(doc: dict) -> list[dict]:
    for campo in ('results', 'dados', 'records', 'rows'):
        registros = doc.get(campo)
        if isinstance(registros, list) and all(isinstance(r, dict) for r in registros):
            return registros
    return []


def _filtrar_linhas(registros: list[dict], ano: int | None, uf: str) -> pd.DataFrame:
    df = pd.DataFrame(registros)
    if df.empty:
        return df
    ano_col = next((c for c in ('ano', 'year') if c in df.columns), None)
    if ano is not None and ano_col:
        df = df.loc[df[ano_col].astype(str) == str(ano)]
    uf_col = next((c for c in ('uf', 'SG_UF_PROVA') if c in df.columns), None)
    if uf != 'BR' and uf_col:
        df = df.loc[df[uf_col].astype(str) == uf]
    return df


def _linha_temporal(st, df: pd.DataFrame, coluna: str, titulo: str, percentual: bool = False):
    if df.empty or coluna not in df.columns or 'ano' not in df.columns:
        st.info('Não há dados agregados para o recorte solicitado.')
        return
    graf = df.copy()
    graf['ano'] = graf['ano'].astype(str)
    graf['Perfil'] = graf['cluster'].map(PERFIS).fillna(graf['cluster'])
    if percentual:
        graf[coluna] = pd.to_numeric(graf[coluna], errors='coerce')
    fig = px.line(graf, x='ano', y=coluna, color='Perfil', markers=True,
                  color_discrete_map={v:CORES_PERFIS[k] for k,v in [('M1',PERFIS['C1']),('M2',PERFIS['C2']),('M3',PERFIS['C3'])]},
                  labels={'ano':'Edição do ENEM', coluna:titulo})
    st.plotly_chart(fig, use_container_width=True)


def _barras_por_cluster(st, df: pd.DataFrame, coluna: str, titulo: str):
    if df.empty or coluna not in df.columns or 'cluster' not in df.columns:
        st.info('Dados indisponíveis para o recorte.')
        return
    t = df.copy()
    t['Perfil'] = t['cluster'].map(PERFIS).fillna(t['cluster'])
    fig = px.bar(t, x='Perfil', y=coluna, color='Perfil', text_auto='.1f',
                 color_discrete_map={v:CORES_PERFIS[k] for k,v in [('M1',PERFIS['C1']),('M2',PERFIS['C2']),('M3',PERFIS['C3'])]},
                 labels={coluna:titulo}, category_orders={'Perfil':list(PERFIS.values())})
    fig.update_layout(showlegend=False, xaxis_title='Perfil socioeconômico')
    st.plotly_chart(fig, use_container_width=True)


def _seis_perfis(st, doc: dict, ind: int, ano: int | None, uf: str):
    if uf != 'BR':
        st.info('Este indicador usa uma amostra nacional. Selecione “Todos os estados (Brasil)” para consultá-lo; não há recortes por UF nesta fonte.')
        return
    originais = [r for r in linhas_agrupadas(doc) if str(r.get('status', '')).lower() != 'nao_aplicavel']
    df = pd.DataFrame(originais)
    if df.empty:
        st.warning('Nenhuma linha aplicável foi encontrada.')
        return
    if ind == 68:
        d = df.copy()
        d['cluster'] = d['cluster_referencia']
        if ano is None:
            _linha_temporal(st, d, 'percentual_amostra', 'Participação na amostra (%)')
        else:
            d = d.loc[d['ano'].astype(str) == str(ano)]
            _barras_por_cluster(st, d, 'percentual_amostra', 'Participação na amostra (%)')
        st.caption('Distribuições amostrais, não estimativas censitárias. Em 2025 não há notas vinculadas.')
        st.dataframe(_tabela_com_rotulos_materiais(d.head(100)), hide_index=True, use_container_width=True)
        st.caption(DESCRICAO_PERFIS)
        return
    if ano is None:
        if ind in (55, 57, 59):
            alvo = {55: ('media', 'Nota média (0–1000)'),
                    57: ('percentual_high', 'Redações com 900 pontos ou mais (%)'),
                    59: ('media_diferenca_absoluta','Diferença média absoluta (pontos)')}[ind]
            _linha_temporal(st, df, *alvo)
        else:
            st.info('Para comparar competências, escolha uma edição abaixo.')
        anos = sorted(set(int(x) for x in df['ano'].dropna() if str(x).isdigit()))
        escolhido = st.selectbox('Edição para tabela detalhada', anos, index=len(anos)-1,
                                 key=f'catalogo_ano_{ind}')
    else:
        escolhido = ano
    recorte = df.loc[df['ano'].astype(str) == str(escolhido)].copy()
    if recorte.empty:
        st.info(f'Este resultado não está disponível para {escolhido}.')
        return
    if ind == 55:
        _barras_por_cluster(st, recorte, 'media', 'Nota média de redação (0–1000)')
    elif ind == 56:
        recorte['Perfil'] = recorte['cluster'].map(PERFIS)
        fig = px.bar(recorte, x='competencia', y='media', color='Perfil', barmode='group',
                     labels={'competencia':'Competência', 'media':'Pontuação média (0–200)'})
        st.plotly_chart(fig, use_container_width=True)
    elif ind == 57:
        _barras_por_cluster(st, recorte, 'percentual_high', 'Redações com 900+ (%)')
    elif ind == 58:
        recorte['Perfil'] = recorte['cluster'].map(PERFIS)
        # A fonte armazena frequência como razão [0,1], não percentual.
        recorte['Frequência (%)'] = pd.to_numeric(recorte['frequencia_desconto'],errors='coerce')*100
        fig = px.bar(recorte, x='competencia', y='Frequência (%)', color='Perfil', barmode='group')
        st.plotly_chart(fig, use_container_width=True)
        st.caption('Amostras de alto desempenho: verifique o tamanho do grupo para avaliar a estabilidade das estimativas.')
    elif ind == 59:
        _barras_por_cluster(st, recorte, 'media_diferenca_absoluta', 'Diferença média absoluta entre avaliadores')
    st.dataframe(_tabela_com_rotulos_materiais(recorte), hide_index=True, use_container_width=True)
    st.caption(DESCRICAO_PERFIS + ' Comparações descritivas da amostra não demonstram causalidade. C1–C5, quando exibidas no eixo de competências, referem-se exclusivamente à matriz de correção da redação.')


def pagina_catalogo_68(st, raiz: Path, ano: int | None, uf: str) -> None:
    st.title('Catálogo consolidado · 68 indicadores')
    st.caption('Resultados agregados para consulta pública, com autorização editorial pelo responsável pelo projeto.')
    arquivos = inventario(raiz)
    disponiveis = sum(bool(x) for x in arquivos.values())
    st.metric('Indicadores com JSON disponível', f'{disponiveis}/68')
    if disponiveis != len(IDS):
        ausentes = [f'IND-{i:03d}' for i,p in arquivos.items() if not p]
        st.warning('Fontes ausentes: ' + ', '.join(ausentes))
    grupos = {
        '001–022 · Panorama, notas e competências': [i for i in IDS if i <= 22],
        '023–045 · Avaliação e desempenho': [i for i in IDS if 23 <= i <= 45],
        '046–054 · Contexto e MCA original': [i for i in IDS if 46 <= i <= 54],
        '055–059 · Perfis materiais e redação V2': [i for i in IDS if 55 <= i <= 59],
        '064–072 · Complementares e evolução': [i for i in IDS if 64 <= i <= 72],
    }
    area = st.selectbox('Área de análise', list(grupos), key='catalogo_grupo')
    escolha = st.selectbox('Indicador', grupos[area], key='catalogo_ind',
                          format_func=lambda i: f'IND-{i:03d} · {NOMES.get(i, arquivos[i][0].stem[8:].replace("_", " ") if arquivos[i] else "Sem fonte")}' )
    opcoes = arquivos[escolha]
    if not opcoes:
        st.error('Não há JSON agregado para este indicador.')
        return
    origem = st.selectbox('Conjunto de resultados', opcoes, format_func=lambda p:p.name,
                          key='catalogo_variante') if len(opcoes)>1 else opcoes[0]
    try:
        doc = abrir_json(origem)
    except (ValueError, OSError) as exc:
        st.error(f'Não foi possível carregar {origem.name}: {exc}')
        return
    if escolha in V2:
        doc, ocultas = preparar_doc_publico_v2(doc, escolha)
        if doc is None:
            st.warning(
                'Este indicador não tem resultados autorizados para publicação '
                'ou a fonte V2 não pôde ser validada.'
            )
            return
        mostrar_aviso_publicacao_v2(st, escolha, ocultas)
    st.caption(f'Fonte: `{origem.relative_to(raiz)}`')
    st.caption(f'Indicador: {doc.get("indicator_id", f"IND-{escolha:03d}")} · Apresentação pública autorizada · Fontes rastreáveis no histórico do projeto')
    if escolha in V2:
        _seis_perfis(st, doc, escolha, ano, uf)
        return
    st.info('Visualização genérica de inspeção. As páginas temáticas existentes mantêm as visualizações especializadas dos indicadores anteriores.')
    registros = linhas_agrupadas(doc)
    if registros:
        tabela = _filtrar_linhas(registros, ano, uf)
        if not tabela.empty:
            st.caption(f'{len(tabela)} linhas agregadas no recorte (exibindo até 500).')
            st.dataframe(tabela.head(500), hide_index=True, use_container_width=True)
        else:
            st.info('O filtro solicitado não possui linhas nesta fonte. Nenhum ano ou UF foi interpolado.')
    else:
        st.caption('JSON agregado com estrutura aninhada: metadados resumidos abaixo.')
        chaves = [{'Campo':k,'Tipo':type(v).__name__,
                   'Entradas':len(v) if isinstance(v,(dict,list)) else '—'}
                  for k,v in doc.items()]
        st.dataframe(pd.DataFrame(chaves), hide_index=True, use_container_width=True)
        with st.expander('Estrutura do indicador (campos superiores)'):
            st.write(list(doc.keys()))
    if ano is not None and not any(c in (registros[0] if registros else {}) for c in ('ano','year')):
        st.caption('O filtro global de ano não é aplicável à estrutura desta fonte.')
    if uf != 'BR' and not any(c in (registros[0] if registros else {}) for c in ('uf','SG_UF_PROVA')):
        st.caption('O filtro global de UF não é aplicável à estrutura desta fonte.')
