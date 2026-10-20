#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-015 — Loadings PCA, ENEM 2019–2025, Brasil e 27 UFs.

Catálogo: eixo ML, página competencies, indicador "Loadings PCA", prioridade P0.
Pergunta: Quais competências definem PC1, PC2, PC3?
Variáveis: NU_NOTA_COMP1..5; POP_VALID/AMOSTRA_ML.
Método: coeficientes dos componentes PCA; visual Heatmap/barras.
Destino: pages.competencies.pca.loadings.

Este indicador *reaproveita o PCA completo calculado pelo IND-014*, sem reler os
microdados. O IND-014 usa StandardScaler(ddof=0), PCA exata sobre momentos,
com uma matriz de autovetores (5 PCs x 5 competências), equivalente a
sklearn.PCA.components_. Em particular:
  - "loadings" / "coeficiente_pca": peso assinado da competência no autovetor
    (mesmo significado de sklearn.PCA.components_, norma L2=1 por componente);
  - "correlacao_competencia_pc": corr(z da competência, score da PC), igual a
    coeficiente_pca * sqrt(autovalor da matriz de correlação padronizada);
  - "contribuicao_pct": 100 * coeficiente_pca^2 (soma = 100% em cada PC).
Os três números NÃO são intercambiáveis. A orientação dos sinais vem do IND-014;
ela é convencional, não possui interpretação causal. PCs quase degeneradas
podem ter orientação instável. Cada ano, UF e histórico são modelos separados;
comparar PC1 de recortes diferentes não garante a mesma direção. O histórico
é um único PCA consolidado ajustado no IND-014, não uma média anual.

Pré-requisito: executar IND-014 e terminar de atualizar os sete dashboards.
Na raiz do repositório:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_015_loadings_pca.py

Saídas:
  outputs/indicadores/IND_015_loadings_pca.csv (5.600 linhas)
  outputs/json/IND_015_loadings_pca.json
  outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

O Streamlit não é alterado; data_status=draft até revisões acadêmicas e de
privacidade dos indicadores anteriores. Nenhum dado individual é exportado.
"""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
LABELS = tuple(f'C{i}' for i in range(1, 6))
VARIAVEIS = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
INDICADOR = 'IND-015'
VERSAO = ('2.14.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-'
          'ind008-ind009-ind010-ind011-ind012-ind013-ind014-ind015')
METODO = 'coeficientes_autovetores_pca_ind014_e_correlacoes_escores'
DEFINICAO = ('Coeficientes assinados de PCA.components_ (5 x 5), correlações entre '
            'competências padronizadas e escores das componentes, e participação '
            'quadrática de cada competência na direção de cada PC. Os PCs foram '
            'ajustados no IND-014 sobre a população válida completa; sem amostragem.')
NOTA = ('Autovetores têm orientação arbitrária: IND-014 fixa o maior coeficiente '
        'absoluto como positivo. Os modelos são ajustados separadamente por ano, '
        'UF e histórico; PCk pode representar direções distintas entre recortes. '
        'Com autovalores próximos ou repetidos, a direção individual não é estável. '
        'Associação não implica causalidade. Cada observação histórica é uma '
        'participação no ENEM, não uma pessoa única.')
PRECISAO = 10


def ler_json(p: Path) -> dict:
    if not p.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {p}')
    with p.open('r', encoding='utf-8') as fp:
        return json.load(fp)


def mapa_uf(grupo: dict, contexto: str) -> dict[str, dict]:
    ufs = grupo.get('ufs')
    if not isinstance(ufs, list) or len(ufs) != 27 or {x.get('uf') for x in ufs} != set(UFS):
        raise ValueError(f'{contexto}: faltam UFs ou existem UFs repetidas')
    return {x['uf']: x for x in ufs}


def validar_grupo_pca(g: dict, contexto: str) -> None:
    """Revalida algebraicamente o modelo salvo, independente da rotina IND-014."""
    n = g.get('n_validas')
    if not isinstance(n, int) or n < 30:
        raise ValueError(f'{contexto}: N válido insuficiente')
    pcs = g.get('componentes')
    model = g.get('modelo', {})
    if not isinstance(pcs, list) or len(pcs) != 5:
        raise ValueError(f'{contexto}: cinco PCs ausentes')
    if model.get('competencias') != list(LABELS) or model.get('variaveis') != list(VARIAVEIS):
        raise ValueError(f'{contexto}: ordem ou nomes de competências incompatíveis')
    if model.get('sinal_convencao') != 'maior coeficiente absoluto de cada componente positivo':
        raise ValueError(f'{contexto}: convenção de sinais divergente')
    try:
        v = np.asarray(model['components'], dtype=float)
        r = np.asarray(model['pearson_original'], dtype=float)
        lambdas = np.asarray([pc['autovalor_padronizado'] for pc in pcs], dtype=float)
        ratios = np.asarray([pc['variancia_explicada'] for pc in pcs], dtype=float)
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError(f'{contexto}: matriz do modelo ilegível') from exc
    if v.shape != (5, 5) or r.shape != (5, 5) or not all(
            np.all(np.isfinite(x)) for x in (v, r, lambdas, ratios)):
        raise ValueError(f'{contexto}: dimensão ou número não finito no modelo PCA')
    if any(pc.get('componente') != f'PC{k+1}' or pc.get('ordem') != k+1
           for k, pc in enumerate(pcs)):
        raise ValueError(f'{contexto}: ordem PC1..PC5 inválida')
    if not np.allclose(v @ v.T, np.eye(5), atol=1e-7, rtol=0):
        raise ValueError(f'{contexto}: coeficientes não ortonormais')
    if not np.allclose(r, r.T, atol=1e-8, rtol=0) or \
       not np.allclose(np.diag(r), 1, atol=1e-8, rtol=0):
        raise ValueError(f'{contexto}: Pearson não é matriz de correlação')
    if np.any(lambdas < -1e-8) or np.any(np.diff(lambdas) > 1e-8) or \
       abs(float(lambdas.sum()) - 5.0) > 1e-7:
        raise ValueError(f'{contexto}: autovalores incompatíveis com a padronização')
    if not np.allclose(r @ v.T, v.T * lambdas, atol=2e-7, rtol=0):
        raise ValueError(f'{contexto}: vetores não correspondem à matriz de correlação')
    if not np.allclose(v.T @ np.diag(lambdas) @ v, r, atol=2e-7, rtol=0):
        raise ValueError(f'{contexto}: PCA não reconstrói Pearson')
    if not np.allclose(ratios, lambdas / 5, atol=2e-8, rtol=0):
        raise ValueError(f'{contexto}: variância explicada incoerente com autovalores')
    if abs(float(ratios.sum()) - 1.0) > 1e-8:
        raise ValueError(f'{contexto}: variância explicada não soma 100%')
    for k in range(5):
        if v[k, int(np.argmax(np.abs(v[k]))) ] < -1e-9:
            raise ValueError(f'{contexto}: sinal de PC{k+1} não atende à convenção')
        if abs(pcs[k]['variancia_acumulada'] - float(sum(ratios[:k+1]))) > 2e-8:
            raise ValueError(f'{contexto}: variância acumulada incompatível')
    if not isinstance(g.get('n_somas_divergentes'), int):
        raise ValueError(f'{contexto}: controle de divergência da fonte ausente')


def loadings_grupo(g: dict, contexto: str) -> dict:
    validar_grupo_pca(g, contexto)
    v = np.asarray(g['modelo']['components'], dtype=float)
    lam = np.asarray([x['autovalor_padronizado'] for x in g['componentes']], dtype=float)
    pesos_corr = v * np.sqrt(np.maximum(lam, 0))[:, None]
    if np.any(np.abs(pesos_corr) > 1 + 1e-6):
        raise ValueError(f'{contexto}: correlação competência-PC fora de [-1,1]')
    contributions = 100 * v*v
    if not np.allclose(np.sum(contributions, axis=1), 100, atol=1e-7):
        raise ValueError(f'{contexto}: contribuições por PC não totalizam 100%')
    linhas_pc = []
    for i, pc in enumerate(g['componentes']):
        ordem = np.argsort(-np.abs(v[i]), kind='stable')
        itens = []
        for j in range(5):
            itens.append({
                'competencia': LABELS[j], 'variavel': VARIAVEIS[j],
                'coeficiente_pca': round(float(v[i, j]), PRECISAO),
                'coeficiente_absoluto': round(float(abs(v[i, j])), PRECISAO),
                'correlacao_competencia_pc': round(float(pesos_corr[i, j]), PRECISAO),
                'contribuicao_pct': round(float(contributions[i, j]), 8)
            })
        linhas_pc.append({
            'componente': f'PC{i+1}', 'ordem': i+1,
            'autovalor_padronizado': pc['autovalor_padronizado'],
            'variancia_explicada': pc['variancia_explicada'],
            'percentual_explicado': pc['percentual_explicado'],
            'competencia_dominante': LABELS[int(ordem[0])],
            'competencias_por_peso_absoluto': [LABELS[int(j)] for j in ordem],
            'coeficientes': itens,
        })
    quase_repetidos = bool(any(abs(lam[k]-lam[k+1]) < 1e-6 for k in range(4)))
    return {
        'n_validas': g['n_validas'],
        'competencias': list(LABELS), 'componentes': linhas_pc,
        'loadings': [[round(float(t), PRECISAO) for t in row] for row in v],
        'correlacoes_componentes': [[round(float(t), PRECISAO) for t in row] for row in pesos_corr],
        'contribuicoes_pct': [[round(float(t), 8) for t in row] for row in contributions],
        'autovalores_repetidos_ou_proximos': quase_repetidos,
        'possui_componente_variancia_quase_zero': bool(np.any(lam < 1e-7)),
        'n_somas_divergentes': g['n_somas_divergentes'],
        'delta_soma_competencias_menos_nota_redacao': g['delta_soma_competencias_menos_nota_redacao'],
    }


def comparar_resultados(a: dict, b: dict, contexto: str) -> None:
    if a['n_validas'] != b.get('n_validas'):
        raise ValueError(f'{contexto}: denominadores divergem do IND-014')
    if a['n_somas_divergentes'] != b['n_somas_divergentes'] or abs(
            a['delta_soma_competencias_menos_nota_redacao'] -
            float(b['delta_soma_competencias_menos_nota_redacao'])) > 1e-8:
        raise ValueError(f'{contexto}: ressalva da fonte divergente')


def carregar_prerequisitos(raiz: Path) -> tuple[dict, dict[int, dict]]:
    pasta = raiz / 'outputs' / 'json'
    modelo = ler_json(pasta / 'IND_014_variancia_explicada_pca.json')
    if modelo.get('indicator', {}).get('id') != 'IND-014':
        raise ValueError('Referência PCA não corresponde ao IND-014')
    if modelo.get('meta', {}).get('data_status') != 'draft' or \
       'ind014' not in modelo.get('meta', {}).get('analysis_version', ''):
        raise ValueError('IND-014 não foi concluído na versão esperada')
    anos = modelo.get('years', [])
    if not isinstance(anos, list) or sorted(x.get('ano') for x in anos) != list(ANOS):
        raise ValueError('IND-014 sem sete anos distintos')
    if modelo.get('historical', {}).get('periodo') != '2019-2025':
        raise ValueError('Consolidado histórico IND-014 ausente')
    dashboards = {}
    for ano in ANOS:
        dash = ler_json(pasta / f'dashboard_enem_{ano}.json')
        if dash.get('meta', {}).get('year') != ano or dash['meta'].get('data_status') != 'draft':
            raise ValueError(f'{ano}: dashboard incorreto ou não está em rascunho')
        if 'ind014' not in dash['meta'].get('analysis_version', ''):
            raise ValueError(f'{ano}: executar IND-014 antes do IND-015')
        pca = dash.get('pages', {}).get('competencies', {}).get('pca', {})
        if pca.get('indicator_id') != 'IND-014' or \
           not isinstance(pca.get('explained_variance'), list) or \
           len(pca.get('by_uf', [])) != 27:
            raise ValueError(f'{ano}: PCA do dashboard incompleta')
        if dash.get('quality', {}).get('ind014_validation', {}).get('status') != 'ok':
            raise ValueError(f'{ano}: IND-014 ainda não validado no dashboard')
        if 'loadings' in pca or 'ind015' in dash.get('pages', {}).get('temporal', {}):
            raise ValueError(f'{ano}: IND-015 já registrado; não sobrescrever outra execução')
        dashboards[ano] = dash
    return modelo, dashboards


def gerar_resultados(modelo: dict, dashboards: dict[int, dict]) -> tuple[list[dict], dict, dict]:
    dados = []
    h = modelo['historical']
    todas_referencias = [*modelo['years'], h]
    for ref in todas_referencias:
        ident = str(ref['ano']) if 'ano' in ref else '2019-2025'
        por_uf = mapa_uf(ref, ident)
        br = loadings_grupo(ref['brasil'], ident + '/BR')
        grupos = [{'uf': uf, **loadings_grupo(por_uf[uf], ident + '/' + uf)} for uf in UFS]
        if sum(u['n_validas'] for u in grupos) != br['n_validas']:
            raise ValueError(f'{ident}: soma da população estadual não coincide com BR')
        if sum(u['n_somas_divergentes'] for u in grupos) != br['n_somas_divergentes']:
            raise ValueError(f'{ident}: ressalvas estaduais não coincidem com BR')
        if abs(sum(float(u['delta_soma_competencias_menos_nota_redacao']) for u in grupos) -
               float(br['delta_soma_competencias_menos_nota_redacao'])) > 1e-6:
            raise ValueError(f'{ident}: deltas estaduais não coincidem com BR')
        out = {'ano': ref['ano'], 'arquivo_fonte': ref['arquivo_fonte'],
               'brasil': br, 'ufs': grupos} if 'ano' in ref else \
              {'periodo': '2019-2025', 'brasil': br, 'ufs': grupos}
        dados.append(out)
    hist = dados[-1]
    anos = dados[:-1]
    for uf in ('BR', *UFS):
        def pegar(d):
            return d['brasil'] if uf == 'BR' else next(x for x in d['ufs'] if x['uf'] == uf)
        n_hist = pegar(hist)['n_validas']
        if n_hist != sum(pegar(d)['n_validas'] for d in anos):
            raise ValueError(f'{uf}: N histórico não é soma das sete edições')
        if pegar(hist)['n_somas_divergentes'] != sum(pegar(d)['n_somas_divergentes'] for d in anos):
            raise ValueError(f'{uf}: contagem de ressalvas históricas inválida')
        if abs(float(pegar(hist)['delta_soma_competencias_menos_nota_redacao']) -
               sum(float(pegar(d)['delta_soma_competencias_menos_nota_redacao']) for d in anos)) > 1e-6:
            raise ValueError(f'{uf}: soma histórica de diferenças inválida')
    for d in anos:
        ano = d['ano']
        dash = dashboards[ano]
        pca = dash['pages']['competencies']['pca']
        refer = next(x for x in modelo['years'] if x['ano'] == ano)
        if pca['n'] != d['brasil']['n_validas'] or \
           dash['pages']['overview']['kpis']['valid_essays'] != d['brasil']['n_validas']:
            raise ValueError(f'{ano}: total de redações do dashboard diverge')
        if pca['explained_variance'] != refer['brasil']['componentes']:
            raise ValueError(f'{ano}: variância explicada no dashboard difere do modelo')
        m = {x['uf']: x for x in pca['by_uf']}
        if set(m) != set(UFS):
            raise ValueError(f'{ano}: PCA por UF ausente ou repetida')
        for u in refer['ufs']:
            if m[u['uf']]['n'] != u['n_validas'] or \
               m[u['uf']]['explained_variance'] != u['componentes']:
                raise ValueError(f'{ano}/{u["uf"]}: PCA do dashboard incompatível')
    return anos, hist, {d['ano']: d for d in anos}


def linhas_csv(anos: list[dict], hist: dict, modelo: dict) -> list[dict]:
    out = []
    for d in [*anos, hist]:
        periodo = str(d.get('ano', '2019-2025'))
        origem = d.get('arquivo_fonte', '2019-2025')
        for abrangencia, uf, grupo in [('BR', 'BR', d['brasil']),
                                        *[('UF', x['uf'], x) for x in d['ufs']]]:
            for c in grupo['componentes']:
                for x in c['coeficientes']:
                    out.append({
                        'indicador_id': INDICADOR, 'periodo': periodo,
                        'abrangencia': abrangencia, 'uf': uf,
                        'componente': c['componente'], 'ordem': c['ordem'],
                        'competencia': x['competencia'], 'variavel': x['variavel'],
                        'n_validas': grupo['n_validas'],
                        'coeficiente_pca': x['coeficiente_pca'],
                        'coeficiente_absoluto': x['coeficiente_absoluto'],
                        'correlacao_competencia_pc': x['correlacao_competencia_pc'],
                        'contribuicao_pct': x['contribuicao_pct'],
                        'variancia_explicada': c['variancia_explicada'],
                        'percentual_explicado': c['percentual_explicado'],
                        'autovalor_padronizado': c['autovalor_padronizado'],
                        'autovalores_proximos': grupo['autovalores_repetidos_ou_proximos'],
                        'populacao': 'POP_VALID', 'amostragem': 'nao',
                        'metodo': METODO, 'arquivo_fonte': origem,
                    })
    if len(out) != 8 * 28 * 5 * 5:
        raise ValueError(f'IND-015: esperado 5.600 linhas, encontradas {len(out)}')
    return out


def item_temporal(g: dict) -> dict:
    return {'n': g['n_validas'], 'loadings': deepcopy(g['loadings']),
            'correlacoes_componentes': deepcopy(g['correlacoes_componentes']),
            'contribuicoes_pct': deepcopy(g['contribuicoes_pct']),
            'autovalores_repetidos_ou_proximos': g['autovalores_repetidos_ou_proximos']}


def construir_dashboard(d: dict, anos: list[dict], hist: dict, atual: dict, gerado: str) -> dict:
    ano = d['ano']
    dash = deepcopy(atual)
    pca = dash['pages']['competencies']['pca']
    br = d['brasil']
    # pca.indicator_id permanece IND-014 porque explained_variance pertence ao 014.
    pca['loadings_indicator_id'] = INDICADOR
    pca['loadings'] = deepcopy(br['loadings'])
    pca['loading_correlations'] = deepcopy(br['correlacoes_componentes'])
    pca['loading_contributions_pct'] = deepcopy(br['contribuicoes_pct'])
    pca['loading_rows'] = [f'PC{i}' for i in range(1, 6)]
    pca['loading_columns'] = list(LABELS)
    pca['loadings_note'] = ('Coeficientes = sklearn.PCA.components_, não correlações; '
                            'ver loading_correlations. Sinais convencionais e PCs locais.')
    for item in pca['by_uf']:
        u = next(x for x in d['ufs'] if x['uf'] == item['uf'])
        item['loadings'] = deepcopy(u['loadings'])
        item['loading_correlations'] = deepcopy(u['correlacoes_componentes'])
        item['loading_contributions_pct'] = deepcopy(u['contribuicoes_pct'])
        item['autovalores_repetidos_ou_proximos'] = u['autovalores_repetidos_ou_proximos']
    dash['pages']['temporal']['ind015'] = {
        'indicator_id': INDICADOR, 'population': 'POP_VALID',
        'national_by_year': [{'year': x['ano'], **item_temporal(x['brasil'])} for x in anos],
        'period_total': item_temporal(hist['brasil']),
        'period_by_uf': [{'uf': x['uf'], **item_temporal(x)} for x in hist['ufs']],
        'historical_note': NOTA}
    dash['pages']['methodology']['ind015'] = {
        'definition': DEFINICAO, 'population': 'POP_VALID',
        'source_file': d['arquivo_fonte'], 'geographic_dimension': 'SG_UF_PROVA',
        'algorithm': 'reaproveitamento dos 5 autovetores do IND-014; sem nova PCA',
        'method': METODO, 'sampling': 'não há amostragem',
        'source_indicator': 'IND-014',
        'loadings_definition': 'coeficiente assinado em PCA.components_ (norma unitária)',
        'correlation_definition': 'coeficiente * sqrt(autovalor da correlação)',
        'contribution_definition': '100 * coeficiente^2 por componente',
        'cautions': NOTA}
    qa = dash['quality']['ind014_validation']
    dash['quality']['ind015_validation'] = {
        'status': 'ok', 'source_indicator': 'IND-014',
        'sem_leitura_nova_microdados': True,
        'ortogonalidade_reconstrucao_pearson': True,
        'contribuicoes_somam_100_por_pc': True,
        'sinal_convencional': True,
        'n_validas': br['n_validas'],
        'validas_soma_competencias_divergente': qa['validas_soma_competencias_divergente'],
        'delta_soma_competencias_menos_nota_redacao': qa['delta_soma_competencias_menos_nota_redacao'],
        'autovalores_repetidos_ou_proximos': br['autovalores_repetidos_ou_proximos'],
        'metodo': METODO,
    }
    if dash['quality']['ind015_validation']['validas_soma_competencias_divergente'] != \
       br['n_somas_divergentes']:
        raise ValueError(f'{ano}: exceção SC/2023 não conciliada')
    dash['meta']['analysis_version'] = VERSAO
    dash['meta']['generated_at'] = gerado
    dash['meta']['data_status'] = 'draft'
    alertas = dash['meta'].setdefault('warnings', [])
    aviso = ('IND-015: PCA loadings calculados dos autovetores IND-014; '
             'orientações/significados de PCk podem variar entre recortes. '
             'Revisão acadêmica e privacidade pendentes.')
    if aviso not in alertas:
        alertas.append(aviso)
    if br['autovalores_repetidos_ou_proximos']:
        aviso = f'IND-015/{ano}: autovalores quase repetidos; loadings individuais exigem cautela.'
        if aviso not in alertas:
            alertas.append(aviso)
    return dash


def validar_dashboard(doc: dict, raiz: Path) -> str:
    if not {'meta', 'filters', 'quality', 'pages'}.issubset(doc):
        raise ValueError('Dashboard sem campos essenciais')
    if 'NU_INSCRICAO' in json.dumps(doc, ensure_ascii=False):
        raise ValueError('Identificador individual proibido no dashboard')
    candidatos = [raiz / 'docs' / '04_resultados_analises.schema.json',
                  raiz / 'docs' / 'metodologia' / '04_resultados_analises.schema.json',
                  raiz / '04_resultados_analises.schema.json']
    schema = next((p for p in candidatos if p.is_file()), None)
    if schema is None:
        return 'estrutura essencial (schema não localizado)'
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError('Instale jsonschema para validar o dashboard') from exc
    jsonschema.validate(doc, ler_json(schema))
    return 'JSON Schema v1.0.0'


def salvar_json(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix('.json.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    temp.replace(p)


def salvar_csv(p: Path, linhas: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix('.csv.tmp')
    with temp.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)
    temp.replace(p)


def executar(raiz: Path) -> None:
    modelo, dashboards = carregar_prerequisitos(raiz)
    anos, hist, _ = gerar_resultados(modelo, dashboards)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    atualizados = {d['ano']: construir_dashboard(d, anos, hist, dashboards[d['ano']], gerado)
                   for d in anos}
    schemas = {validar_dashboard(x, raiz) for x in atualizados.values()}
    output = {
        'meta': {
            'indicator_id': INDICADOR, 'module_schema_version': 'ind015-module-1.0.0',
            'analysis_version': VERSAO, 'dataset_version': 'enem-2019-2025-csv-publico',
            'generated_at': gerado, 'data_status': 'draft',
            'source_files': modelo['meta']['source_files'],
            'source_indicator_file': 'IND_014_variancia_explicada_pca.json',
            'population_definition': DEFINICAO, 'geographic_dimension': 'SG_UF_PROVA',
            'method': METODO, 'notes': NOTA, 'sem_nova_leitura_microdados': True,
            'source_discrepancies': modelo['meta'].get('source_discrepancies', {}),
        },
        'indicator': {'id': INDICADOR, 'name': 'Loadings PCA', 'unit': 'coeficiente',
                      'dashboard_json_path': 'pages.competencies.pca.loadings'},
        'years': anos, 'historical': hist,
        'dashboard_files': [f'dashboard_enem_{ano}.json' for ano in ANOS]
    }
    csv_rows = linhas_csv(anos, hist, modelo)
    json.dumps(output, ensure_ascii=False, allow_nan=False)
    out = raiz / 'outputs'
    salvar_csv(out / 'indicadores' / 'IND_015_loadings_pca.csv', csv_rows)
    salvar_json(out / 'json' / 'IND_015_loadings_pca.json', output)
    for ano in ANOS:
        salvar_json(out / 'json' / f'dashboard_enem_{ano}.json', atualizados[ano])
    print('IND-015 concluído:', flush=True)
    print('  IND_015_loadings_pca.csv: 5.600 linhas', flush=True)
    print('  IND_015_loadings_pca.json', flush=True)
    print('  dashboard_enem_2019.json ... dashboard_enem_2025.json atualizados', flush=True)
    print('  Modelo de origem: IND-014; sem reler microdados; sem amostragem', flush=True)
    print('  Contrato: ' + ', '.join(sorted(schemas)), flush=True)
    for d in anos:
        pc1 = d['brasil']['componentes'][0]
        ps = ', '.join(f"{x['competencia']}={x['coeficiente_pca']:+.4f}"
                       for x in pc1['coeficientes'])
        print(f"  {d['ano']} | PC1 ({pc1['percentual_explicado']:.2f}%): {ps}", flush=True)
    print('  data_status=draft | revisão acadêmica/privacidade ainda pendente', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-015 — coeficientes PCA (loadings) C1–C5')
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parents[2],
                        help='Raiz do projeto contendo outputs/json (padrão: dois níveis acima)')
    args = parser.parse_args()
    executar(args.raiz.resolve())


if __name__ == '__main__':
    main()
