#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-014 — Variância explicada por PCA das competências C1–C5 (ENEM 2019–2025).

Catálogo: ML / Competências / P0; NU_NOTA_COMP1..5; POP_VALID/AMOSTRA_ML;
StandardScaler → PCA; explained_variance_ratio_; barras;
pages.competencies.pca.explained_variance.

PADRONIZAÇÃO E PCA EXATAS, SEM AMOSTRAGEM:
  Os microdados são percorridos em blocos, calculando N, soma(X) e XᵀX por UF.
  A matriz de covariância da população é Q/N - μμᵀ. Após a padronização
  z=(x-μ)/σ (desvio-padrão populacional, ddof=0), diagonaliza-se a matriz
  de correlação com numpy.linalg.eigh. Esse cálculo equivale matematicamente
  a StandardScaler().fit_transform(X), seguido de PCA(n_components=5).fit(Z),
  salvo precisão de ponto flutuante e convenção do sinal dos autovetores.
  Não são criadas pontuações individualizadas nem exportados microdados.

As cinco componentes, variâncias explicadas, acumuladas e autovalores são
publicados. O modelo (médias, escalas e vetores de componentes) é mantido no
JSON modular para o IND-015/IND-016, mas loadings e scores ainda não são
publicados no dashboard pelo IND-014.

A redação de SC/2023 com C3=10, soma C1–C5=290 e nota total=320 é
preservada como observada e registrada nos metadados de qualidade.
Divergências de soma não alteram a população. Notas inválidas bloqueiam
exportação. Correlaciona-se a matriz obtida com Pearson do IND-013 e as
marginais do IND-012, além de IND-001, IND-002, IND-009 e IND-011.

Pré-requisito: IND-013 concluído e dashboards cumulativos atualizados.
Executar na raiz do repositório:
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_014_variancia_explicada_pca.py

Saídas:
 outputs/indicadores/IND_014_variancia_explicada_pca.csv (1.120 linhas)
 outputs/json/IND_014_variancia_explicada_pca.json
 outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

O Streamlit não é modificado. Resultados permanecem data_status=draft.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
LABELS = tuple(f'C{i}' for i in range(1, 6))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COMP)
INDICADOR = 'IND-014'
VERSAO = ('2.13.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-'
          'ind008-ind009-ind010-ind011-ind012-ind013-ind014')
METODO = 'standardscaler_ddof0_pca_exata_momentos_eigh_pop_valid'
DEFINICAO = ('Proporção da variância padronizada de NU_NOTA_COMP1..5 explicada '
            'por PC1..PC5 entre redações válidas; StandardScaler com ddof=0, '
            'PCA de cinco componentes e explained_variance_ratio_.')
HISTORICO = ('PCA 2019–2025 ajustada novamente sobre todas as participações '
             'consolidadas por momentos de primeira e segunda ordem; não é '
             'média das PCAs anuais. O PCA de cada ano e UF é ajustado em seu '
             'próprio recorte; comparações de componentes entre recortes exigem '
             'considerar que suas direções podem diferir. Não há amostragem. '
             'SG_UF_PROVA é o local da prova, não o de residência.')
CUIDADOS = ('PCA é exploratória; não é pontuação oficial do ENEM e não demonstra '
            'causalidade. Os sinais dos autovetores são arbitrários e são '
            'orientados deterministicamente para a maior carga em módulo. '
            'Interpretação detalhada dos loadings pertence ao IND-015. '
            'Resultados internos em data_status=draft até revisão acadêmica '
            'e de privacidade dos indicadores anteriores.')
BLOCO = 100_000
LIMIAR = 30
TOL = 1e-6


def fonte(ano: int, raiz: Path) -> Path:
    nome = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {caminho}')
    with caminho.open(encoding='utf-8') as fp:
        return json.load(fp)


def mapa_ufs(doc: dict) -> dict[str, dict]:
    itens = doc.get('ufs', [])
    if len(itens) != 27 or {x.get('uf') for x in itens} != set(UFS):
        raise ValueError('Referência sem as 27 UFs distintas')
    return {x['uf']: x for x in itens}


def carregar_referencias(raiz: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    pasta = raiz / 'outputs' / 'json'
    nomes = {1: 'redacoes_validas', 2: 'nota_media', 9: 'media_competencias',
             11: 'dispersao_competencias', 12: 'distribuicao_niveis_competencias',
             13: 'correlacao_competencias'}
    refs = {}
    for num, nome in nomes.items():
        p = pasta / f'IND_{num:03d}_{nome}.json'
        doc = ler_json(p)
        if doc.get('indicator', {}).get('id') != f'IND-{num:03d}':
            raise ValueError(f'{p.name}: ID incorreto')
        if sorted(x.get('ano') for x in doc.get('years', [])) != list(ANOS):
            raise ValueError(f'{p.name}: sete anos ausentes ou repetidos')
        for grupo in [*doc['years'], doc['historical']]:
            mapa_ufs(grupo)
        refs[num] = doc
    dashboards = {}
    for ano in ANOS:
        p = pasta / f'dashboard_enem_{ano}.json'
        dash = ler_json(p)
        if dash.get('meta', {}).get('year') != ano or dash['meta'].get('data_status') != 'draft':
            raise ValueError(f'{p.name}: ano/status incompatível')
        c = dash.get('pages', {}).get('competencies', {})
        if c.get('status') != 'ok' or not all(k in c for k in
                ('summary', 'dispersion', 'level_distribution', 'correlation')):
            raise ValueError(f'{p.name}: IND-013 ainda não concluído')
        if not all(dash.get('quality', {}).get(f'ind{num:03d}_validation', {}).get('status') == 'ok'
                   for num in (9, 10, 11, 12, 13)):
            raise ValueError(f'{p.name}: qualidade de IND-009..013 incompleta')
        if len(c['summary']) != 5 or len(c['correlation']['pearson']) != 5:
            raise ValueError(f'{p.name}: competências/correlações incompletas')
        dashboards[ano] = dash
    return refs, dashboards


class Momentos:
    """Estatísticas suficientes para PCA linear, sem microdados em memória."""
    __slots__ = ('n', 's', 'q', 'total_registros', 'divergentes', 'delta')

    def __init__(self) -> None:
        self.n = 0
        self.s = np.zeros(5, dtype=np.float64)
        self.q = np.zeros((5, 5), dtype=np.float64)
        self.total_registros = 0
        self.divergentes = 0
        self.delta = 0.0

    def adicionar(self, x: np.ndarray) -> None:
        if x.ndim != 2 or x.shape[1] != 5 or not np.isfinite(x).all():
            raise ValueError('Valores C1–C5 inválidos no bloco')
        self.n += len(x)
        self.s += np.sum(x, axis=0, dtype=np.float64)
        self.q += x.T @ x

    def mesclar(self, outro: 'Momentos') -> None:
        self.n += outro.n
        self.s += outro.s
        self.q += outro.q
        self.total_registros += outro.total_registros
        self.divergentes += outro.divergentes
        self.delta += outro.delta


def ajustar_pca(m: Momentos) -> dict:
    """Equivalente a StandardScaler + sklearn.PCA sem formar a matriz N×5.

    O sklearn utiliza explained_variance_ com ddof=1; por isso os autovalores
    da correlação populacional são multiplicados por N/(N-1) para a saída
    explained_variance. As razões e vetores não dependem desse fator.
    """
    if m.n < LIMIAR:
        raise ValueError(f'POP_VALID com {m.n} registros: menor que {LIMIAR}')
    mu = m.s / m.n
    cov = m.q / m.n - np.outer(mu, mu)
    cov = (cov + cov.T) / 2
    variancias = np.diag(cov).copy()
    if not np.isfinite(cov).all() or np.any(variancias <= 1e-12):
        raise ValueError('PCA requer variância positiva nas cinco competências')
    sd = np.sqrt(variancias)
    corr = cov / np.outer(sd, sd)
    corr = (corr + corr.T) / 2
    np.fill_diagonal(corr, 1.0)
    if not np.isfinite(corr).all() or np.any(np.abs(corr) > 1.0 + 1e-7):
        raise ValueError('Matriz de correlações inválida')
    eigvals, eigvecs = np.linalg.eigh(corr)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    if np.any(eigvals < -1e-8):
        raise ValueError('Matriz de correlação semidefinida positiva violada')
    eigvals = np.maximum(eigvals, 0.0)
    if not math.isclose(float(np.sum(eigvals)), 5.0, rel_tol=1e-8, abs_tol=1e-8):
        raise ValueError('Soma de autovalores da matriz padronizada deve ser 5')
    # Convenção de sinal estável, útil para o próximo IND-015.
    for k in range(5):
        j = int(np.argmax(np.abs(eigvecs[:, k])))
        if eigvecs[j, k] < 0:
            eigvecs[:, k] *= -1
    ratio = eigvals / eigvals.sum()
    if np.any(np.diff(ratio) > 1e-10) or not np.isclose(ratio.sum(), 1, atol=1e-10):
        raise ValueError('Razões de variância não normalizadas')
    cumulative = np.cumsum(ratio)
    pcs = []
    for i in range(5):
        pcs.append({'componente': f'PC{i+1}', 'ordem': i+1,
                    'variancia_explicada': round(float(ratio[i]), 10),
                    'percentual_explicado': round(float(ratio[i]*100), 6),
                    'variancia_acumulada': round(float(cumulative[i]), 10),
                    'percentual_acumulado': round(float(cumulative[i]*100), 6),
                    'autovalor_padronizado': round(float(eigvals[i]), 10),
                    'explained_variance': round(float(eigvals[i] * m.n / (m.n-1)), 10)})
    degeneradas = any(abs(eigvals[k]-eigvals[k+1]) <= 1e-9 for k in range(4))
    return {
        'n_validas': m.n, 'n_componentes': 5, 'componentes': pcs,
        'labels': list(LABELS),
        'modelo': {
            'competencias': list(LABELS), 'variaveis': list(COMP),
            'mean': [round(float(v), 10) for v in mu],
            'scale': [round(float(v), 10) for v in sd],
            # Uma linha por PC; mesmo sentido de sklearn.PCA.components_.
            'components': [[round(float(v), 10) for v in eigvecs[:, k]] for k in range(5)],
            'pearson_original': [[round(float(v), 10) for v in row] for row in corr],
            'singular_values': [round(math.sqrt(float(x) * m.n), 6) for x in eigvals],
            'sinal_convencao': 'maior coeficiente absoluto de cada componente positivo',
            'autovalores_repetidos': bool(degeneradas),
            'populacao_ajuste': 'POP_VALID completa; sem amostragem',
        },
        'n_somas_divergentes': m.divergentes,
        'delta_soma_competencias_menos_nota_redacao': round(m.delta, 6),
        'total_registros': m.total_registros,
    }


def processar_ano(ano: int, raiz: Path, bloco: int = BLOCO) -> dict:
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f'Fonte ausente: {caminho}')
    momentos = {uf: Momentos() for uf in UFS}
    qa = Counter()
    for parte in pd.read_csv(caminho, sep=';', usecols=list(COLUNAS), dtype=str,
                             keep_default_na=False, na_filter=False,
                             encoding='utf-8-sig', encoding_errors='replace',
                             chunksize=bloco, on_bad_lines='error'):
        uf = parte['SG_UF_PROVA'].str.strip().str.upper()
        status = parte['TP_STATUS_REDACAO'].str.strip()
        nota_str = parte['NU_NOTA_REDACAO'].str.strip()
        nota = pd.to_numeric(nota_str.str.replace(',', '.', regex=False), errors='coerce')
        st1 = status.eq('1')
        ok_nota = nota.notna() & nota.between(0, 1000)
        validas = st1 & ok_nota
        qa['registros'] += len(parte)
        qa['status1'] += int(st1.sum())
        qa['validas'] += int(validas.sum())
        qa['status1_sem_nota'] += int((st1 & nota_str.eq('')).sum())
        qa['status1_nota_invalida'] += int((st1 & nota_str.ne('') & ~ok_nota).sum())
        qa['validas_sem_uf'] += int((validas & uf.eq('')).sum())
        qa['validas_uf_desconhecida'] += int((validas & ~uf.isin(UFS) & uf.ne('')).sum())
        totais = uf.value_counts().to_dict()
        for sigla, qtd in totais.items():
            if sigla in momentos:
                momentos[sigla].total_registros += int(qtd)
            else:
                qa['registros_uf_nao_reconhecida'] += int(qtd)
        if not bool(validas.any()):
            continue
        raw = parte.loc[validas, list(COMP)].apply(lambda s: s.str.strip())
        valores = raw.apply(lambda s: pd.to_numeric(s.str.replace(',', '.', regex=False), errors='coerce'))
        completos = valores.notna() & valores.ge(0) & valores.le(200)
        for i, c in enumerate(COMP, 1):
            qa[f'c{i}_ausente'] += int(raw[c].eq('').sum())
            qa[f'c{i}_invalida'] += int((raw[c].ne('') & ~completos[c]).sum())
        linha_ok = completos.all(axis=1)
        qa['validas_competencias_incompletas'] += int((~linha_ok).sum())
        if not bool(linha_ok.any()):
            continue
        notas = valores.loc[linha_ok].to_numpy(dtype=np.float64)
        siglas = uf.loc[validas].loc[linha_ok].to_numpy()
        totais_validos = nota.loc[validas].loc[linha_ok].to_numpy(dtype=np.float64)
        delta = np.sum(notas, axis=1) - totais_validos
        discrep = np.abs(delta) > 1e-6
        qa['validas_soma_competencias_divergente'] += int(discrep.sum())
        for sigla in np.unique(siglas):
            if sigla not in momentos:
                continue  # O total inválido bloqueará a exportação ao fim.
            mask = siglas == sigla
            m = momentos[str(sigla)]
            m.adicionar(notas[mask])
            m.divergentes += int(np.count_nonzero(discrep[mask]))
            m.delta += float(np.sum(delta[mask][discrep[mask]]))
    if qa['registros'] < 1:
        raise ValueError(f'{ano}: CSV vazio')
    if qa['status1'] != qa['validas'] + qa['status1_sem_nota'] + qa['status1_nota_invalida']:
        raise ValueError(f'{ano}: TP_STATUS_REDACAO=1 não reconciliado')
    erros = []
    for campo in ('status1_sem_nota', 'status1_nota_invalida', 'validas_sem_uf',
                  'validas_uf_desconhecida', 'validas_competencias_incompletas',
                  'registros_uf_nao_reconhecida'):
        if qa[campo]:
            erros.append(f'{campo}={qa[campo]}')
    for i in range(1, 6):
        for campo in ('ausente', 'invalida'):
            if qa[f'c{i}_{campo}']:
                erros.append(f'c{i}_{campo}={qa[f"c{i}_{campo}"]}')
    if erros:
        raise ValueError(f'{ano}: integridade da fonte inválida: {", ".join(erros)}')
    if sum(m.n for m in momentos.values()) != qa['validas'] or \
       sum(m.total_registros for m in momentos.values()) != qa['registros'] or \
       sum(m.divergentes for m in momentos.values()) != qa['validas_soma_competencias_divergente']:
        raise ValueError(f'{ano}: divergência de totais entre Brasil e UFs')
    br_m = Momentos()
    for m in momentos.values():
        br_m.mesclar(m)
    estados = [{'uf': sigla, **ajustar_pca(momentos[sigla])} for sigla in UFS]
    br = ajustar_pca(br_m)
    return {'ano': ano, 'arquivo_fonte': caminho.name, 'brasil': br, 'ufs': estados,
            'qualidade': {
                'status': 'ok', 'status1_sem_nota': qa['status1_sem_nota'],
                'status1_nota_invalida': qa['status1_nota_invalida'],
                'validas_sem_uf': qa['validas_sem_uf'],
                'validas_uf_desconhecida': qa['validas_uf_desconhecida'],
                'validas_competencias_incompletas': qa['validas_competencias_incompletas'],
                'validas_soma_competencias_divergente': qa['validas_soma_competencias_divergente'],
                'delta_soma_competencias_menos_nota_redacao': br['delta_soma_competencias_menos_nota_redacao'],
                'situacao_soma_competencias':
                    'divergencias_na_fonte' if qa['validas_soma_competencias_divergente'] else 'ok',
                'soma_27_ufs_igual_brasil': True, 'sem_amostragem': True,
                'standard_scaler_ddof': 0, 'pca_componentes': 5,
                'soma_variancia_explicada_igual_1': True,
                'validado_contra_ind001_ind002_ind009_ind011_ind012_ind013': False,
                'metodo': METODO}, '_momentos': momentos}


def comparar_grupo(g: dict, refs: dict[int, dict], contexto: str,
                   hist: bool = False) -> None:
    n = g['n_validas']
    for k in (1, 2, 9, 11, 12, 13):
        ref = refs[k]
        esperadas = ref.get('redacoes_validas') if k == 1 else ref.get('n_validas')
        if n != esperadas:
            raise ValueError(f'{contexto}: N={n} difere IND-{k:03d} N={esperadas}')
        if not hist and g['total_registros'] != ref['total_registros']:
            raise ValueError(f'{contexto}: POP_ALL difere de IND-{k:03d}')
    for k in (9, 11, 12, 13):
        r = refs[k]
        if g['n_somas_divergentes'] != r['n_somas_divergentes'] or \
            abs(g['delta_soma_competencias_menos_nota_redacao'] -
                float(r['delta_soma_competencias_menos_nota_redacao'])) > 1e-5:
            raise ValueError(f'{contexto}: exceção da origem difere IND-{k:03d}')
    corr = g['modelo']['pearson_original']
    prior_pearson = refs[13]['pearson']
    for i, lab in enumerate(LABELS):
        c9, c11, c12 = (refs[k]['competencias'][i] for k in (9, 11, 12))
        if any(c['competencia'] != lab for c in (c9, c11, c12)):
            raise ValueError(f'{contexto}/{lab}: ordem de competências incorreta')
        media = g['modelo']['mean'][i]
        sd = g['modelo']['scale'][i]
        if abs(media - float(c9['media'])) > 0.00006:
            raise ValueError(f'{contexto}/{lab}: média não conciliada com IND-009')
        if abs(sd - float(c11['desvio_padrao'])) > 0.00006:
            raise ValueError(f'{contexto}/{lab}: desvio não conciliado com IND-011')
        levels = c12['niveis']
        soma = math.fsum(float(e['pontuacao']) * e['quantidade'] for e in levels)
        soma2 = math.fsum(float(e['pontuacao'])**2 * e['quantidade'] for e in levels)
        if abs(soma - n * media) > max(0.01, 3e-9*n) or \
           abs(soma2 - n * (media*media+sd*sd)) > max(0.15, 3e-7*n):
            raise ValueError(f'{contexto}/{lab}: primeiro/segundo momento difere de IND-012')
        for j in range(5):
            if abs(corr[i][j] - corr[j][i]) > 1e-8:
                raise ValueError(f'{contexto}: matriz Pearson não simétrica')
            r = prior_pearson[i][j]
            if r is None or abs(corr[i][j] - r) > 2e-5:
                raise ValueError(f'{contexto}: PCA/Pearson não corresponde ao IND-013 ({lab},C{j+1})')
    for i, pc in enumerate(g['componentes']):
        if pc['componente'] != f'PC{i+1}' or pc['ordem'] != i+1:
            raise ValueError(f'{contexto}: componentes fora de ordem')
    if not math.isclose(sum(x['variancia_explicada'] for x in g['componentes']), 1, abs_tol=1e-8):
        raise ValueError(f'{contexto}: percentuais não somam 100%')
    if abs(g['componentes'][-1]['variancia_acumulada'] - 1) > 1e-8:
        raise ValueError(f'{contexto}: acumulado final diferente de 100%')


def validar_referencias(dados: list[dict], hist: dict, refs: dict[int, dict]) -> None:
    indices = {k: {r['ano']: r for r in doc['years']} for k, doc in refs.items()}
    for d in dados:
        ano = d['ano']
        r = {k: v[ano] for k, v in indices.items()}
        comparar_grupo(d['brasil'], {k: v['brasil'] for k, v in r.items()}, f'{ano}/BR')
        por_uf = {k: mapa_ufs(v) for k, v in r.items()}
        for g in d['ufs']:
            comparar_grupo(g, {k: m[g['uf']] for k, m in por_uf.items()}, f"{ano}/{g['uf']}")
        for k in (9, 11, 12, 13):
            if d['qualidade']['validas_soma_competencias_divergente'] != \
                    r[k]['qualidade']['validas_soma_competencias_divergente']:
                raise ValueError(f'{ano}: contagem de exceções difere de IND-{k:03d}')
        d['qualidade']['validado_contra_ind001_ind002_ind009_ind011_ind012_ind013'] = True
    hist_ref = {k: v['historical'] for k, v in refs.items()}
    comparar_grupo(hist['brasil'], {k: v['brasil'] for k, v in hist_ref.items()}, 'HIST/BR', True)
    map_hist = {k: mapa_ufs(v) for k, v in hist_ref.items()}
    for g in hist['ufs']:
        comparar_grupo(g, {k: v[g['uf']] for k, v in map_hist.items()}, f"HIST/{g['uf']}", True)


def consolidar_historico(dados: list[dict]) -> dict:
    juntos = {uf: Momentos() for uf in UFS}
    for d in dados:
        for uf in UFS:
            juntos[uf].mesclar(d['_momentos'][uf])
    br_m = Momentos()
    for m in juntos.values():
        br_m.mesclar(m)
    estados = [{'uf': uf, **ajustar_pca(juntos[uf])} for uf in UFS]
    br = ajustar_pca(br_m)
    return {'periodo': '2019-2025', 'brasil': br, 'ufs': estados,
            'qualidade': {'status': 'ok', 'soma_27_ufs_igual_brasil': True,
                          'historico_recalculado_momentos': True,
                          'sem_media_de_pc_anuais': True, 'sem_amostragem': True,
                          'metodo': METODO}}


def linhas_csv(dados: list[dict], hist: dict) -> list[dict]:
    linhas = []
    for d in [*dados, hist]:
        periodo = str(d['ano']) if 'ano' in d else d['periodo']
        origem = d.get('arquivo_fonte', '2019-2025')
        for abrangencia, uf, grupo in [('BR', 'BR', d['brasil']),
                                      *[('UF', u['uf'], u) for u in d['ufs']]]:
            for pc in grupo['componentes']:
                linhas.append({'indicador_id': INDICADOR, 'periodo': periodo,
                               'abrangencia': abrangencia, 'uf': uf,
                               'componente': pc['componente'], 'ordem': pc['ordem'],
                               'n_validas': grupo['n_validas'],
                               'variancia_explicada': pc['variancia_explicada'],
                               'percentual_explicado': pc['percentual_explicado'],
                               'variancia_acumulada': pc['variancia_acumulada'],
                               'percentual_acumulado': pc['percentual_acumulado'],
                               'autovalor_padronizado': pc['autovalor_padronizado'],
                               'explained_variance': pc['explained_variance'],
                               'populacao': 'POP_VALID', 'amostragem': 'nao',
                               'metodo': METODO, 'arquivo_fonte': origem})
    if len(linhas) != 8 * 28 * 5:
        raise ValueError(f'Esperadas 1.120 linhas, obtidas {len(linhas)}')
    return linhas


def item_dashboard(g: dict) -> dict:
    # PCA loadings/vetores do modelo aguardam o IND-015, que usará o JSON modular.
    return {'n': g['n_validas'],
            'explained_variance': deepcopy(g['componentes']),
            'sample_mode': 'POP_VALID_completa_sem_amostragem'}


def construir_dashboard(d: dict, dados: list[dict], hist: dict,
                         anterior: dict, gerado: str) -> dict:
    ano = d['ano']
    dash = deepcopy(anterior)
    p = dash['pages']['competencies']
    br = d['brasil']
    if dash['pages']['overview']['kpis']['valid_essays'] != br['n_validas']:
        raise ValueError(f'{ano}: N do dashboard não confere com IND-014')
    if p['correlation']['n'] != br['n_validas']:
        raise ValueError(f'{ano}: população IND-013 incompatível')
    if {g['uf']: g['n'] for g in p['correlation']['by_uf']} != \
       {g['uf']: g['n_validas'] for g in d['ufs']}:
        raise ValueError(f'{ano}: população das 27 UFs não confere com IND-013')
    # A estrutura pca é compartilhada com futuros IND-015 e IND-016.
    pca = p.setdefault('pca', {})
    pca['indicator_id'] = INDICADOR
    pca['population'] = 'POP_VALID'
    pca['method'] = METODO
    pca['labels'] = list(LABELS)
    pca['n'] = br['n_validas']
    pca['explained_variance'] = deepcopy(br['componentes'])
    pca['by_uf'] = [{'uf': u['uf'], **item_dashboard(u)} for u in d['ufs']]
    pca['fit_note'] = 'PCA exata para cada recorte; n_components=5; não há amostragem'
    dash['pages']['temporal']['ind014'] = {
        'indicator_id': INDICADOR, 'population': 'POP_VALID', 'method': METODO,
        'national_by_year': [{'year': x['ano'], **item_dashboard(x['brasil'])} for x in dados],
        'period_total': item_dashboard(hist['brasil']),
        'period_by_uf': [{'uf': x['uf'], **item_dashboard(x)} for x in hist['ufs']],
        'historical_note': HISTORICO}
    dash['pages']['methodology']['ind014'] = {
        'definition': DEFINICAO, 'population': 'POP_VALID',
        'source_file': d['arquivo_fonte'], 'geographic_dimension': 'SG_UF_PROVA',
        'method': METODO,
        'standardization': 'StandardScaler equivalente: (x-média)/std(ddof=0)',
        'algorithm': 'PCA n_components=5 via autodecomposição da correlação padronizada',
        'sample_size': br['n_validas'], 'sampling': 'não há amostragem; base completa',
        'explained_variance': 'razão dos autovalores da matriz padronizada',
        'n_components': 5, 'historical_note': HISTORICO, 'limitations': CUIDADOS}
    dash['quality']['ind014_validation'] = deepcopy(d['qualidade'])
    dash['meta']['analysis_version'] = VERSAO
    dash['meta']['generated_at'] = gerado
    dash['meta']['data_status'] = 'draft'
    warnings = dash['meta'].setdefault('warnings', [])
    texto = ('IND-014: variância explicada por PCA exata (base válida completa); '
             'revisão acadêmica de PCA e privacidade dos demais indicadores pendentes.')
    if texto not in warnings:
        warnings.append(texto)
    if br['n_somas_divergentes']:
        texto = (f"IND-014/{ano}: {br['n_somas_divergentes']} registro(s) com "
                 'soma C1–C5 divergente da nota total, sem imputação/exclusão.')
        if texto not in warnings:
            warnings.append(texto)
    return dash


def validar_dashboard(doc: dict, raiz: Path) -> str:
    if not {'meta', 'filters', 'quality', 'pages'}.issubset(doc):
        raise ValueError('Dashboard sem campos essenciais')
    if 'NU_INSCRICAO' in json.dumps(doc, ensure_ascii=False):
        raise ValueError('Identificador individual proibido no dashboard')
    candidatos = [raiz / 'docs' / '04_resultados_analises.schema.json',
                  raiz / 'docs' / 'metodologia' / '04_resultados_analises.schema.json',
                  raiz / '04_resultados_analises.schema.json']
    encontrado = next((p for p in candidatos if p.is_file()), None)
    if encontrado is None:
        return 'estrutura essencial (schema não localizado)'
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError('jsonschema necessário para validação estrutural') from exc
    jsonschema.validate(doc, ler_json(encontrado))
    return 'JSON Schema v1.0.0'


def salvar_json(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as fp:
        json.dump(doc, fp, ensure_ascii=False, indent=2, allow_nan=False)
        fp.write('\n')
    tmp.replace(p)


def salvar_csv(p: Path, linhas: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)
    tmp.replace(p)


def executar(raiz: Path, bloco: int = BLOCO) -> None:
    # A checagem do IND-013 ocorre antes de começar a leitura dos arquivos brutos.
    refs, dashboards = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f'IND-014 | {ano}: processando {fonte(ano, raiz).name} ...', flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        p = d['brasil']['componentes']
        print(f"  válidas={d['brasil']['n_validas']:,} | "
              f"PC1={p[0]['percentual_explicado']:.4f}% "
              f"PC2={p[1]['percentual_explicado']:.4f}% "
              f"PC3={p[2]['percentual_explicado']:.4f}%", flush=True)
        if d['brasil']['n_somas_divergentes']:
            print(f"  AVISO FONTE: {d['brasil']['n_somas_divergentes']} divergência(s) "
                  'C1–C5 versus nota total preservadas', flush=True)
    hist = consolidar_historico(dados)
    validar_referencias(dados, hist, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    atualizados = {d['ano']: construir_dashboard(d, dados, hist, dashboards[d['ano']], gerado)
                   for d in dados}
    schemas = {validar_dashboard(x, raiz) for x in atualizados.values()}
    for d in dados:
        del d['_momentos']
    output = {
        'meta': {'indicator_id': INDICADOR, 'module_schema_version': 'ind014-module-1.0.0',
                 'analysis_version': VERSAO, 'dataset_version': 'enem-2019-2025-csv-publico',
                 'generated_at': gerado, 'data_status': 'draft',
                 'source_files': {str(d['ano']): d['arquivo_fonte'] for d in dados},
                 'population_definition': DEFINICAO, 'geographic_dimension': 'SG_UF_PROVA',
                 'method': METODO, 'historical_note': HISTORICO, 'cautions': CUIDADOS,
                 'comparison_ind001_ind002_ind009_ind011_ind012_ind013': 'aprovada',
                 'source_discrepancies': {
                     str(d['ano']): {'count': d['brasil']['n_somas_divergentes'],
                                     'delta_total': d['brasil']['delta_soma_competencias_menos_nota_redacao']}
                     for d in dados}},
        'indicator': {'id': INDICADOR, 'name': 'Variância explicada PCA', 'unit': 'proporcao',
                      'dashboard_json_path': 'pages.competencies.pca.explained_variance'},
        'years': dados, 'historical': hist,
        'dashboard_files': [f'dashboard_enem_{ano}.json' for ano in ANOS],
    }
    linhas = linhas_csv(dados, hist)
    json.dumps(output, ensure_ascii=False, allow_nan=False)
    out = raiz / 'outputs'
    salvar_csv(out / 'indicadores' / 'IND_014_variancia_explicada_pca.csv', linhas)
    salvar_json(out / 'json' / 'IND_014_variancia_explicada_pca.json', output)
    for ano in ANOS:
        salvar_json(out / 'json' / f'dashboard_enem_{ano}.json', atualizados[ano])
    print('\nIND-014 concluído:')
    print(f'  IND_014_variancia_explicada_pca.csv ({len(linhas):,} linhas)')
    print('  IND_014_variancia_explicada_pca.json')
    print('  dashboard_enem_2019.json ... dashboard_enem_2025.json atualizados')
    print('  Contrato: ' + ', '.join(sorted(schemas)))
    print('  data_status=draft | pendentes revisões acadêmica e de privacidade')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-014 — variância explicada PCA C1–C5')
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--bloco', type=int, default=BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error('--bloco deve ser positivo')
    executar(args.raiz.resolve(), args.bloco)


if __name__ == '__main__':
    main()
