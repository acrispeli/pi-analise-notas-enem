# -*- coding: utf-8 -*-
"""Navegação pelas oito páginas do catálogo ENEM.

O módulo lê agregados dos JSONs. A aprovação editorial pela equipe para
apresentação é independente dos metadados históricos de processamento.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px

from painel_catalogo_68 import _seis_perfis
from publicacao_segura_v2 import preparar_doc_publico_v2, mostrar_aviso_publicacao_v2
from leitura_acessivel_68 import mostrar_leitura_acessivel as mostrar_interpretacao
from graficos_educacionais_68 import mostrar_grafico_didatico, resumo_expresso
from painel_revisao_geral_68 import (renderizar_historico_geral, renderizar_resultados_gerais,
                                       mostrar_legenda_questoes, mostrar_historico_socio_seguro,
                                       mostrar_glossario_visual)

CATALOGO_REL = Path('docs/catalogo_navegacao_68.json')
V2 = frozenset({55, 56, 57, 58, 59, 68})
MODELO_V2 = 'V2_MCA10_KMeans3_e31f55489e16f296'
EXCLUIDOS = frozenset({60, 61, 62, 63})
ROTAS = ('overview', 'competencies', 'evaluators', 'high_performance',
         'socioeconomic', 'ml', 'temporal', 'methodology')
TITULOS_ROTAS = {
    'overview': 'Visão geral',
    'competencies': 'Competências',
    'evaluators': 'Avaliadores',
    'high_performance': 'Alto desempenho',
    'socioeconomic': 'Contexto socioeconômico',
    'ml': 'Padrões por ML',
    'temporal': 'Evolução temporal',
    'methodology': 'Metodologia',
}

def exibir_detalhe_perfis_materiais(numero: int) -> bool:
    """A metodologia M1–M3 é pertinente somente aos indicadores V2."""
    return numero in V2


def ler_catalogo(raiz: Path) -> dict:
    with (raiz / CATALOGO_REL).open(encoding='utf-8-sig') as f:
        d = json.load(f)
    ids = [x['numero'] for x in d['indicadores']]
    if len(ids) != 68 or len(set(ids)) != 68 or any(i in EXCLUIDOS for i in ids):
        raise ValueError('Catálogo interno não contém exatamente os 68 IDs esperados')
    rotas = [x['rota'] for x in d['paginas']]
    if tuple(rotas) != ROTAS or set(x['pagina'] for x in d['indicadores']) != set(rotas):
        raise ValueError('Páginas do catálogo não correspondem ao contrato')
    return d


def fontes_indicador(raiz: Path, numero: int) -> list[Path]:
    """Prioriza outputs/json; aceita modelo V2 fixo sem depender do status antigo."""
    if numero < 1 or numero > 72 or numero in EXCLUIDOS:
        return []
    principal = sorted((raiz / 'outputs/json').glob(f'IND_{numero:03d}_*.json'))
    if numero in V2:
        # Evita aceitar acidentalmente a versão de outro modelo como V2.
        for candidato in principal:
            try:
                with candidato.open(encoding='utf-8-sig') as f:
                    metadados = json.load(f)
                if metadados.get('modelo_referencia') == MODELO_V2:
                    return [candidato]
            except (OSError, ValueError, TypeError):
                continue
        secundarios = sorted((raiz / 'outputs/rascunho_ponte_v2/json').glob(f'IND_{numero:03d}_*.json'))
        return [p for p in secundarios if _verificar_v2(p)]
    if numero == 1:
        principal.sort(key=lambda p: (p.name != 'IND_001_redacoes_validas.json', p.name))
    elif numero == 34:
        principal.sort(key=lambda p: (p.name != 'IND_034_competencia_unica_impede_1000.json', p.name))
    return principal


def _verificar_v2(path: Path) -> bool:
    try:
        with path.open(encoding='utf-8-sig') as f:
            d = json.load(f)
        return d.get('modelo_referencia') == MODELO_V2
    except (OSError, ValueError, TypeError):
        return False


def _caminho_contrato(d: dict | None, caminho: str) -> Any:
    if not isinstance(d, dict) or not caminho:
        return None
    atual = d
    for nome in caminho.split('.'):
        if isinstance(atual, dict) and nome in atual:
            atual = atual[nome]
        else:
            return None
    return atual


def _valor_contrato(referencia: dict | None, anual: dict | None,
                    numero: int, caminho: str, ano: int | None):
    if ano is not None:
        return _caminho_contrato(anual, caminho), 'edição selecionada'
    # Não apresentar o JSON de referência 2024 como se fosse 2019–2025.
    if numero <= 54 and referencia:
        temporal = referencia.get('pages', {}).get('temporal', {})
        trecho = temporal if numero == 1 else temporal.get(f'ind{numero:03d}')
        if isinstance(trecho, dict) and isinstance(trecho.get('national_by_year'), list):
            return trecho, 'série histórica declarada no contrato'
    if caminho.startswith('pages.temporal.') and referencia:
        return _caminho_contrato(referencia, caminho), 'série temporal agregada'
    return None, None


def _kpi_por_uf(anual: dict | None, numero: int, uf: str, caminho: str):
    """Usa valor local somente se há registro explícito por UF no contrato."""
    if not isinstance(anual, dict):
        return None
    page = anual.get('pages',{}).get('overview',{})
    ind = page.get(f'ind{numero:03d}',{})
    if not isinstance(ind,dict):
        return None
    lista = ind.get('by_uf')
    if not isinstance(lista,list):
        return None
    registro = next((r for r in lista if isinstance(r,dict) and r.get('uf')==uf),None)
    if registro is None:
        return None
    atributo = caminho.rsplit('.',1)[-1]
    aliases = {'valid_essays':'redacoes_validas','perfect_scores':'notas_1000'}
    coluna = atributo if atributo in registro else aliases.get(atributo)
    if coluna and coluna in registro:
        return registro[coluna]
    return registro


def _filtrar_registros(linhas: list[dict], ano: int | None, uf: str):
    df = pd.DataFrame(linhas)
    if df.empty:
        return df, None
    coluna_ano = next((k for k in ('ano', 'year') if k in df.columns), None)
    if ano is not None and coluna_ano:
        df = df[df[coluna_ano].astype(str) == str(ano)]
    coluna_uf = next((k for k in ('uf', 'SG_UF_PROVA') if k in df.columns), None)
    if uf != 'BR':
        if coluna_uf:
            df = df[df[coluna_uf].astype(str) == uf]
        else:
            return df.iloc[0:0].copy(), 'Esta fonte não oferece recorte por UF; selecione Brasil.'
    return df, None


def _linhas_dado(valor, uf: str):
    """Extrai dados tabulares de estrutura agregada, respeitando UF quando existe."""
    if isinstance(valor, list) and all(isinstance(x, dict) for x in valor):
        return valor
    if not isinstance(valor, dict):
        return []
    if uf != 'BR':
        for nome in ('by_uf', 'ufs', 'states', 'by_state'):
            lista = valor.get(nome)
            if isinstance(lista, list):
                return [x for x in lista if isinstance(x, dict) and str(x.get('uf', x.get('SG_UF_PROVA', ''))) == uf]
        for nome in ('national', 'brasil', 'national_summary'):
            if nome in valor:
                return []
    for nome in ('results','national_by_year','bins','summary','explained_variance',
                 'clusters','competencies','by_uf','series','rows','records','categorias',
                 'annual','years','questoes'):
        lista = valor.get(nome)
        if isinstance(lista, list) and all(isinstance(x, dict) for x in lista):
            return lista
    if uf == 'BR':
        for nome in ('brasil', 'national', 'national_summary'):
            trecho = valor.get(nome)
            if isinstance(trecho, dict):
                return _linhas_dado(trecho, uf)
    return []


def _dados_tabela(linhas: list[dict]) -> pd.DataFrame:
    """Não representa estruturas aninhadas como medidas comparáveis."""
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    colunas = [c for c in df.columns if df[c].map(
        lambda x: not isinstance(x, (dict, list, set))
    ).all()]
    return df[colunas].head(1500)


def _grafico_indicador(st, df: pd.DataFrame, visual: str):
    if df.empty:
        return False
    colunas = list(df.columns)
    x = next((c for c in ('ano','year','competencia','componente','cluster','cluster_referencia',
                         'faixa','faixa_nota','faixa_renda','categoria','questao','uf') if c in colunas), None)
    pref = ('media','mean_score','nota_media','percentual_amostra','percentual','percentual_high',
            'frequencia_desconto','quantidade','n','n_amostra','value','variancia_explicada_pct')
    y = next((c for c in pref if c in colunas and pd.to_numeric(df[c], errors='coerce').notna().any()), None)
    if not x or not y or x == y:
        return False
    chart = df[[x, y]].copy()
    chart[y] = pd.to_numeric(chart[y],errors='coerce')
    chart = chart.dropna(subset=[y]).head(150)
    if chart.empty:
        return False
    if 'linha' in visual.lower() or 'área' in visual.lower() or x in ('ano','year'):
        fig = px.line(chart, x=x, y=y, markers=True)
    elif 'heatmap' in visual.lower() and {'cluster','competencia'}.issubset(colunas):
        t = df.copy(); t[y] = pd.to_numeric(t[y],errors='coerce')
        t = t.pivot_table(index='competencia',columns='cluster',values=y,aggfunc='mean')
        fig = px.imshow(t,aspect='auto',labels={'color':y})
    else:
        fig = px.bar(chart, x=x, y=y)
    fig.update_layout(xaxis_title=x.replace('_',' ').title(), yaxis_title=y.replace('_',' ').title())
    st.plotly_chart(fig, use_container_width=True)
    return True


def _mostrar_objeto(st, valor, meta: dict, ano: int | None, uf: str):
    if valor is None:
        return False
    if isinstance(valor, (int, float, str, bool)):
        st.metric(meta['titulo'], valor)
        return True
    if not isinstance(valor, (dict, list)):
        return False
    # Em recorte de UF, proibir implicitamente apresentar resultado nacional.
    if uf != 'BR' and isinstance(valor, dict):
        for campo_uf in ('states', 'ufs', 'by_uf', 'by_state'):
            mapa_uf = valor.get(campo_uf)
            if isinstance(mapa_uf, dict):
                valor_uf = mapa_uf.get(uf)
                if not isinstance(valor_uf, dict):
                    st.info(f'Esta fonte não possui resultado para a UF {uf}.')
                    return True
                valor = valor_uf
                break
        por_uf = _linhas_dado(valor, uf)
        if not por_uf and any(k in valor for k in ('brasil','national','national_summary','by_uf','states','ufs')):
            st.info('O JSON consultado não fornece esta informação para a UF selecionada.')
            return True
        if por_uf:
            valor = por_uf
        else:
            st.info('O resultado não declara recorte por UF; selecione Brasil.')
            return True
    linhas = _linhas_dado(valor, uf)
    if linhas:
        tabela, aviso = _filtrar_registros(linhas, ano, uf)
        if aviso:
            st.info(aviso)
            return True
        if tabela.empty:
            st.info('Sem resultados para o recorte solicitado.')
            return True
        t = _dados_tabela(tabela.to_dict('records'))
        if not t.empty:
            _grafico_indicador(st, t, meta['visual'])
            st.dataframe(t.head(500), hide_index=True, use_container_width=True)
            if len(tabela) > 500:
                st.caption('Tabela limitada às primeiras 500 linhas agregadas.')
            return True
    if isinstance(valor, dict):
        escalares = [(k,v) for k,v in valor.items() if isinstance(v,(int,float)) and not isinstance(v,bool)]
        if escalares and uf=='BR':
            for k,v in escalares[:3]:
                st.metric(k.replace('_',' ').title(), v)
            extras = [{'Campo':k,'Valor':str(v)[:240]} for k,v in valor.items() if isinstance(v,(str,int,float,bool))]
            if extras:
                st.dataframe(pd.DataFrame(extras),hide_index=True,use_container_width=True)
            return True
        # Dado aninhado: exibimos seus subcampos sem inventar medidas.
        indice = [{'Campo':k,'Tipo':type(v).__name__,
                   'Registros':len(v) if isinstance(v,(list,dict)) else '—'}
                  for k,v in valor.items()]
        st.dataframe(pd.DataFrame(indice),hide_index=True,use_container_width=True)
        st.caption('Estrutura agregada aninhada. Consulte a visualização temática existente para gráficos especializados.')
        return True
    return False


def _abrir_json(path: Path) -> dict:
    with path.open(encoding='utf-8-sig') as f:
        d = json.load(f)
    if not isinstance(d,dict):
        raise ValueError('Fonte JSON não é um objeto')
    return d


def pagina_contrato_68(st, raiz: Path, rota: str, ano: int | None, uf: str,
                       referencia: dict | None, anual: dict | None) -> None:
    catalogo = ler_catalogo(raiz)
    pagina = next(x for x in catalogo['paginas'] if x['rota'] == rota)
    itens = [x for x in catalogo['indicadores'] if x['pagina'] == rota]
    st.title(pagina['titulo'])
    st.caption(pagina['objetivo'])
    st.caption(f'{len(itens)} indicadores nesta página · Rota prevista: `{pagina["url"]}` · Catálogo ENEM v2')
    if not itens:
        st.info('Nenhum indicador previsto nesta página.')
        return
    itens_por_id = {x['numero']:x for x in itens}
    escolha = st.selectbox('Indicador do catálogo',list(itens_por_id),
                          format_func=lambda i:f'IND-{i:03d} · {itens_por_id[i]["titulo"]}',
                          key=f'contrato_ind_{rota}')
    meta = itens_por_id[escolha]
    st.subheader(f'IND-{escolha:03d} · {meta["titulo"]}')
    if meta.get('pergunta'):
        st.markdown(f'**Pergunta que buscamos responder:** {meta["pergunta"]}')
    st.caption('Selecione o resultado e abra “Entenda este resultado” para ver uma explicação simples.')
    # INICIO: EXPLICACAO_PERFIS_MATERIAIS_V2
    # Mostrar a metodologia material apenas quando o indicador utiliza
    # os perfis M1–M3; evitar repeti-la em renda, escolaridade ou qualidade.
    if exibir_detalhe_perfis_materiais(escolha):
        from metodologia_perfis_materiais import exibir_metodologia_perfis
        exibir_metodologia_perfis(st, raiz)
    # FIM: EXPLICACAO_PERFIS_MATERIAIS_V2
    with st.expander('Detalhes técnicos do indicador'):
        st.caption(f'Método: {meta["metodo"] or "não informado"} · População: {meta["populacao"] or "ver fonte"} · Visual previsto: {meta["visual"] or "tabela"}')
    if meta.get('restricoes'):
        st.caption('Nota de harmonização: '+ meta['restricoes'])
    if 40 <= escolha <= 52:
        mostrar_legenda_questoes(st, raiz, meta, ano)
    mostrar_glossario_visual(st, escolha)
    opcoes = fontes_indicador(raiz, escolha)
    if not opcoes:
        st.error('O indicador não possui fonte JSON nesta instalação.')
        return
    origem = (st.selectbox('Variante do resultado',opcoes,format_func=lambda p: ('Complemento: redações com 980 pontos' if escolha == 34 and 'recorte_980' in p.name
                                                 else 'Principal: competência única que impede 1000' if escolha == 34
                                                 else p.name),
                           key=f'contrato_var_{rota}_{escolha}')
              if len(opcoes)>1 else opcoes[0])
    if len(opcoes)>1:
        st.caption('Existem resultados complementares legítimos para este mesmo ID; escolha a variante desejada.')
    try:
        doc = _abrir_json(origem)
    except (OSError,ValueError) as exc:
        st.error(f'Falha na leitura de {origem.name}: {exc}')
        return
    # Valida publicação e omite células pequenas ANTES de qualquer visual,
    # interpretação ou inspeção de registros no navegador público.
    if escolha in V2:
        doc, ocultas = preparar_doc_publico_v2(doc, escolha)
        if doc is None:
            st.warning(
                'Os resultados deste indicador aguardam liberação explícita '
                'para divulgação externa ou a fonte não corresponde ao modelo V2. '
                'A descrição metodológica permanece disponível.'
            )
            return
        mostrar_aviso_publicacao_v2(st, escolha, ocultas)
    st.caption('Fonte: `'+str(origem.relative_to(raiz))+'`')
    st.caption('Apresentação editorial: validada pela equipe do projeto. Metadados de processamento preservados no JSON de origem.')
    edicao_da_fonte = doc.get('ano', doc.get('year'))
    if edicao_da_fonte is None and isinstance(doc.get('meta'), dict):
        edicao_da_fonte = doc['meta'].get('year')
    if ano is None and edicao_da_fonte is not None:
        st.caption(f'A fonte selecionada é específica da edição {edicao_da_fonte}; o filtro global continua “Todos os anos”.')
    if ano is not None and edicao_da_fonte is not None and str(edicao_da_fonte) != str(ano):
        st.warning(f'O arquivo escolhido corresponde a {edicao_da_fonte}, mas o filtro está em {ano}. Ajuste o filtro ou selecione a fonte do ano correto.')
        return
    # Variante complementar do IND-034: 980 pontos (esquema distinto da principal).
    if escolha == 34 and origem.name == 'IND_034_recorte_980_final.json':
        from painel_revisao_geral_68 import renderizar_variante_980
        renderizar_variante_980(st, doc, ano, uf)
        mostrar_interpretacao(st, escolha, doc, meta, ano, uf)
        return
    # Visuais especializados nos campos internos dos JSONs IND-053/054.
    if escolha in (53, 54):
        from painel_ml_didatico_53_54 import renderizar_ml_didatico
        if renderizar_ml_didatico(st, doc, escolha, ano, uf):
            mostrar_interpretacao(st, escolha, doc, meta, ano, uf)
            return
    if escolha == 54:
        st.info('O IND-054 histórico utiliza o modelo original. Os perfis materiais V2 são definidos na ponte revisada dos IND-055–059/068; seus rótulos não são equivalentes aos do IND-054.')
    # Gráficos didáticos baseados em medidas anuais já calculadas, apenas se
    # a variante principal estiver escolhida. Não preenche anos sem dados.
    if escolha in (1, 2, 3, 4, 5, 7, 8) and origem == opcoes[0]:
        if mostrar_grafico_didatico(st, raiz, escolha, ano, uf):
            resumo = resumo_expresso(raiz, escolha, ano, uf)
            mostrar_interpretacao(st, escolha, doc, meta, ano, uf,
                                  resumo_especifico=resumo)
            with st.expander('Fonte e contrato do gráfico'):
                st.json({'indicador':meta['id'], 'json_path':meta.get('json_path'),
                         'fonte_principal':origem.name,'fonte_grafica':'dashboard_enem_<ano>.json',
                         'filtros':{'ano':ano,'uf':uf}})
            return
    # Visualizadores especializados para IND-040 e perfis materiais V2.
    # O bloco é idempotente e dispensa reprocessamento de microdados.
    if escolha == 40:
        from painel_socio_040_055_059 import renderizar_ind040
        ano_visual = renderizar_ind040(st, doc, ano, uf)
        if ano_visual:
            mostrar_interpretacao(st, escolha, doc, meta,
                                  ano_visual if type(ano_visual) is int else ano, uf)
            return
    if escolha in (55,56,57,58,59):
        from painel_socio_040_055_059 import renderizar_v2
        if renderizar_v2(st,doc,escolha,ano,uf):
            if uf=='BR' and (ano is None or ano in range(2019,2025)):
                mostrar_interpretacao(st,escolha,doc,meta,ano,uf)
            return
    if escolha in V2:
        _seis_perfis(st,doc,escolha,ano,uf)
        # None representa Todos os anos: resumo compara as edicoes disponiveis.
        # O grafico detalhado pode mostrar separadamente uma edicao selecionada.
        mostrar_interpretacao(st, escolha, doc, meta, ano, uf)
        return
    # IND-041..052: os JSONs socioeconomicos usam national/states em
    # dicionarios e categorias aninhadas; evitar a visualizacao generica.
    if 41 <= escolha <= 52 and origem == opcoes[0]:
        from painel_socio_041_052 import renderizar_socio
        if renderizar_socio(st, raiz, escolha, ano, uf):
            if escolha in (50,52):
                mostrar_historico_socio_seguro(st, raiz, escolha, ano, uf)
            mostrado = ano if ano is not None else getattr(st, 'session_state', {}).get(f'socio_edicao_{escolha}')
            mostrar_interpretacao(st, escolha, doc, meta, mostrado, uf)
            return
    # Dados anuais e históricos detalhados: IND-006..039, IND-064..072.
    # Prioriza os campos reais dos JSONs, antes da tabela genérica do contrato.
    if origem == opcoes[0] and (6 <= escolha <= 39 or 64 <= escolha <= 72):
        if renderizar_historico_geral(st,raiz,doc,escolha,ano,uf) or \
           renderizar_resultados_gerais(st,doc,escolha,ano,uf):
            mostrar_interpretacao(st,escolha,doc,meta,ano,uf)
            return
    caminho = meta.get('json_path','')
    # Variantes complementares não devem ser trocadas silenciosamente pelo
    # módulo principal do contrato, especialmente o recorte 980 do IND-034.
    if len(opcoes)>1 and origem != opcoes[0]:
        valor, proveniencia = None, None
        st.caption('Variante complementar selecionada: a fonte será lida diretamente, sem substituição pelo resultado principal do contrato.')
    else:
        valor, proveniencia = _valor_contrato(referencia,anual,escolha,caminho,ano)
    if valor is not None:
        if uf != 'BR' and isinstance(valor,(int,float,str,bool)):
            local = _kpi_por_uf(anual, escolha, uf, caminho)
            if local is None:
                st.info('Este KPI do contrato é nacional e não há medida local comprovada para a UF selecionada.')
                return
            valor = local
        st.caption(f'Visualização baseada no contrato JSON `{caminho}` · {proveniencia}.')
        if _mostrar_objeto(st,valor,meta,ano,uf):
            mostrar_interpretacao(st, escolha, doc, meta, ano, uf, valor)
            with st.expander('Contrato e metadados técnicos'):
                st.json({'json_path':caminho,'indicador':meta['id'],'fonte':origem.name,
                         'filtros':meta['filtros'],'populacao':meta['populacao']})
            return
    elif ano is None and rota not in ('temporal','methodology'):
        st.info('Selecione uma edição no filtro de ano para usar a visualização prevista no contrato anual; resultados não serão atribuídos a outros anos.')
    # Saída individual agregada, inclusive 064–072 ou módulos ainda não anexados ao dashboard cumulativo.
    if isinstance(doc.get('results'),list):
        valor = doc['results']
    else:
        valor = doc
    if not _mostrar_objeto(st,valor,meta,ano,uf):
        st.info('Este resultado não dispõe de gráfico automático neste recorte. A explicação do indicador continua disponível abaixo.')
    mostrar_interpretacao(st, escolha, doc, meta, ano, uf, valor)
    with st.expander('Contrato e proveniência'):
        st.json({'json_path':caminho,'indicador':meta['id'],'fonte':origem.name,
                 'filtros':meta['filtros'],'populacao':meta['populacao'],
                 'metodo':meta['metodo'],'observacoes':meta['observacoes']})
    st.caption('Consulta exploratória das saídas agregadas; ausência de dados não é interpretada como zero. Grupos pequenos exigem avaliação contextual de publicação.')
