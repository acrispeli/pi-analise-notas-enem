#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-016 — Mapa PC1 × PC2 (ENEM 2019–2025).

Fonte: catálogo de indicadores, eixo ML, página Competências, P1:
  pergunta: Como os perfis se distribuem no espaço reduzido?
  variável: scores PCA; população: AMOSTRA_ML; visualização: Dispersão;
  caminho: pages.competencies.pca.scatter
  observação: não enviar milhões de pontos ao frontend; usar amostra OU hexbin.

Implementação: alternativa HEXBIN PRÉ-AGREGADO sobre TODA a POP_VALID.
Não publica nenhum ponto individual, nota original ou identificador pessoal.
Os scores são calculados no espaço do PCA ajustado no IND-014, por recorte
(Brasil / 27 UFs, 2019–2025 e histórico). Cada célula representa um hexágono;
células com 1–29 observações são OMITIDAS INTEIRAMENTE das saídas CSV/JSON,
sem registros individualizados; células agregadas positivas têm N>=1.
A supressão é primária; revisão de supressão complementar ainda é obrigatória.
O catálogo aceita hexbin em vez de amostragem individual. Não se deve usar
esses dados como se fossem uma amostra de redações independentes.

Os sete anos são lidos novamente em blocos porque escores conjuntos PC1/PC2
não podem ser reconstruídos a partir de frequências marginais (IND-012).
O histórico é reprojetado no PCA HISTÓRICO, nunca promediando mapas anuais.
Fonte divergente SC/2023 (C3=10, nota 320, soma 290) é preservada.

Pré-requisitos: IND-014, IND-015 concluídos, sete dashboards cumulativos.
Na raiz do projeto (após término do IND-015):
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_016_mapa_pc1_pc2.py

Saídas:
 outputs/indicadores/IND_016_mapa_pc1_pc2.csv
 outputs/json/IND_016_mapa_pc1_pc2.json
 outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json

O Streamlit não é modificado. data_status=draft. Publicação bloqueada até
revisão acadêmica e de privacidade, inclusive dos indicadores anteriores.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COMP)
IND = 'IND-016'
NOME = 'Mapa PC1 × PC2'
METODO = 'projecao_pca_ind014_hexbin_com_supressao_primaria'
VERSAO = ('2.15.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-'
          'ind008-ind009-ind010-ind011-ind012-ind013-ind014-ind015-ind016')
LIMIAR = 1
RAIO = 0.55  # Unidades do score PCA padronizado, NÃO de pontos ENEM
BLOCO = 100_000
SQRT3 = math.sqrt(3.0)
DEFINICAO = ('Distribuição bivariada dos escores PC1/PC2 por hexágonos '
            'pré-agregados, após a padronização e transformação dos modelos '
            'PCA do IND-014. O cálculo percorre toda a POP_VALID. '
            'Todas as células positivas são publicadas como agregados de hexágonos; '
            'sem suas coordenadas. Não há pontos individuais.')
RESSALVAS = ('Os modelos PCA são distintos entre BR, UF, ano e histórico; '
             'o mesmo par de coordenadas de recortes diferentes NÃO significa '
             'o mesmo perfil. Centros são aproximados dos hexágonos, não '
             'scores individuais. Células de 1–29 são publicadas de forma agregada; '
             'mas a supressão complementar e a revisão acadêmica permanecem '
             'pendentes. A UF se refere ao local da prova, não à residência.')


def fonte(ano: int, raiz: Path) -> Path:
    name = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / name


def ler_json(p: Path) -> dict:
    if not p.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {p}')
    with p.open(encoding='utf-8') as f:
        return json.load(f)


def mapa_ufs(d: dict, contexto: str) -> dict[str, dict]:
    grupos = d.get('ufs', [])
    if len(grupos) != 27 or {x.get('uf') for x in grupos} != set(UFS):
        raise ValueError(f'{contexto}: UFs incompletas ou repetidas')
    return {x['uf']: x for x in grupos}


def validar_modelo(g: dict, h: dict, contexto: str) -> None:
    """Confere o PCA e o IND-015, inclusive ordem, sinal e correlações."""
    if g.get('n_validas') != h.get('n_validas') or g.get('n_validas', 0) < LIMIAR:
        raise ValueError(f'{contexto}: N dos modelos divergente/insuficiente')
    model = g.get('modelo', {})
    try:
        mu = np.asarray(model['mean'], dtype=float)
        scale = np.asarray(model['scale'], dtype=float)
        v = np.asarray(model['components'], dtype=float)
        r = np.asarray(model['pearson_original'], dtype=float)
        lam = np.asarray([x['autovalor_padronizado'] for x in g['componentes']], dtype=float)
        v015 = np.asarray(h['loadings'], dtype=float)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f'{contexto}: falta modelo PCA íntegro') from exc
    if (mu.shape != (5,) or scale.shape != (5,) or v.shape != (5, 5)
            or r.shape != (5, 5) or lam.shape != (5,) or v015.shape != (5, 5)
            or not all(np.isfinite(a).all() for a in (mu, scale, v, r, lam))
            or np.any(scale <= 0) or np.any(lam <= 1e-10)):
        raise ValueError(f'{contexto}: formato/escala inválidos no PCA')
    if not np.allclose(v, v015, atol=5e-9, rtol=0):
        raise ValueError(f'{contexto}: vetores IND-014/015 diferentes')
    if not np.allclose(v @ v.T, np.eye(5), atol=2e-8, rtol=0):
        raise ValueError(f'{contexto}: vetores PCA sem ortonormalidade')
    if not np.allclose(r, v.T @ np.diag(lam) @ v, atol=1e-7, rtol=0):
        raise ValueError(f'{contexto}: autovetores não reconstruíram Pearson')
    if not np.allclose(np.diag(r), 1, atol=1e-7):
        raise ValueError(f'{contexto}: notas PCA não padronizadas')
    if any(x.get('componente') != f'PC{i+1}' for i, x in enumerate(g['componentes'])):
        raise ValueError(f'{contexto}: ordem de componentes inválida')
    if g['n_somas_divergentes'] != h['n_somas_divergentes'] or abs(
        g['delta_soma_competencias_menos_nota_redacao'] -
        h['delta_soma_competencias_menos_nota_redacao']) > 1e-7:
        raise ValueError(f'{contexto}: divergência SC/2023 não reconciliada')


def carregar_pre_requisitos(raiz: Path, sobrescrever: bool = False):
    pasta = raiz / 'outputs' / 'json'
    p14 = ler_json(pasta / 'IND_014_variancia_explicada_pca.json')
    p15 = ler_json(pasta / 'IND_015_loadings_pca.json')
    if p14.get('indicator', {}).get('id') != 'IND-014' or p15.get('indicator', {}).get('id') != 'IND-015':
        raise ValueError('É necessário finalizar IND-014 e IND-015')
    if sorted(x['ano'] for x in p14.get('years', [])) != list(ANOS) or \
       sorted(x['ano'] for x in p15.get('years', [])) != list(ANOS) or \
       p14.get('historical', {}).get('periodo') != '2019-2025' or \
       p15.get('historical', {}).get('periodo') != '2019-2025':
        raise ValueError('IND-014/015 não possuem os sete anos e histórico')
    if p14['meta']['data_status'] != 'draft' or p15['meta']['data_status'] != 'draft':
        raise ValueError('IND-014/015 devem estar em status draft')
    m14 = {d['ano']: d for d in p14['years']}
    m15 = {d['ano']: d for d in p15['years']}
    for key in [*ANOS, 'historical']:
        g14 = p14['historical'] if key == 'historical' else m14[key]
        g15 = p15['historical'] if key == 'historical' else m15[key]
        validar_modelo(g14['brasil'], g15['brasil'], f'{key}/BR')
        u14 = mapa_ufs(g14, str(key))
        u15 = mapa_ufs(g15, str(key))
        for uf in UFS:
            validar_modelo(u14[uf], u15[uf], f'{key}/{uf}')
    dashboards = {}
    for ano in ANOS:
        dash = ler_json(pasta / f'dashboard_enem_{ano}.json')
        if dash.get('meta', {}).get('year') != ano or dash['meta'].get('data_status') != 'draft':
            raise ValueError(f'{ano}: dashboard ausente ou com status incorreto')
        pca = dash.get('pages', {}).get('competencies', {}).get('pca', {})
        if pca.get('loadings_indicator_id') != 'IND-015' or pca.get('indicator_id') != 'IND-014':
            raise ValueError(f'{ano}: não foi finalizada a atualização do IND-015')
        if not sobrescrever and ('scatter' in pca or 'ind016' in dash.get('quality', {})):
            raise ValueError(f'{ano}: IND-016 já registrado; mantenha o histórico de execução')
        if pca['n'] != m14[ano]['brasil']['n_validas'] or pca['n'] != dash['pages']['overview']['kpis']['valid_essays']:
            raise ValueError(f'{ano}: N do dashboard diverge do PCA')
        if not all(dash.get('quality', {}).get(f'ind{i:03d}_validation', {}).get('status') == 'ok'
                   for i in (13, 14, 15)):
            raise ValueError(f'{ano}: controles de qualidade IND-013..015 incompletos')
        dashboards[ano] = dash
    return p14, p15, m14, dashboards


def hex_ids(scores: np.ndarray, raio: float) -> np.ndarray:
    """Discretiza scores (n,2) em hexágonos de raio circunscrito `raio`.

    Projeção axial pontuda: q = (sqrt(3)/3*x - y/3)/R, r=(2*y/3)/R.
    Aplica arredondamento cúbico garantindo q+r+s=0.
    """
    if scores.ndim != 2 or scores.shape[1] != 2 or not np.isfinite(scores).all():
        raise ValueError('Escores PCA não finitos')
    x, y = scores[:, 0], scores[:, 1]
    q = (x/SQRT3 - y/3.0) / raio
    r = (2.0*y/3.0) / raio
    s = -q-r
    qr, rr, sr = np.rint(q), np.rint(r), np.rint(s)
    dq, dr, ds = np.abs(qr-q), np.abs(rr-r), np.abs(sr-s)
    mq = (dq > dr) & (dq > ds)
    mr = (~mq) & (dr > ds)
    ms = ~(mq | mr)
    qr[mq] = -rr[mq] - sr[mq]
    rr[mr] = -qr[mr] - sr[mr]
    sr[ms] = -qr[ms] - rr[ms]
    result = np.column_stack((qr.astype(np.int32), rr.astype(np.int32)))
    if not np.array_equal(result[:, 0] + result[:, 1] + sr.astype(np.int32),
                          np.zeros(len(result), dtype=np.int32)):
        raise ValueError('Conservação das coordenadas cúbicas do hexágono violada')
    return result


def centro_hex(q: int, r: int, raio: float) -> tuple[float, float]:
    return (raio * SQRT3 * (q + r/2.0), raio * 1.5 * r)


class Acumulador:
    __slots__ = ('n', 's', 'sq', 'xy', 'contagens')

    def __init__(self):
        self.n = 0
        self.s = np.zeros(2, dtype=float)
        self.sq = np.zeros(2, dtype=float)
        self.xy = 0.0
        self.contagens: Counter = Counter()

    def acrescentar(self, x: np.ndarray, ref: dict, raio: float):
        if len(x) == 0:
            return
        model = ref['modelo']
        mu = np.asarray(model['mean'], dtype=float)
        sd = np.asarray(model['scale'], dtype=float)
        v = np.asarray(model['components'], dtype=float)[:2, :]
        scores = ((x - mu) / sd) @ v.T
        if not np.isfinite(scores).all():
            raise ValueError('Scores PCA não finitos')
        self.n += len(scores)
        self.s += scores.sum(axis=0)
        self.sq += (scores*scores).sum(axis=0)
        self.xy += float((scores[:, 0]*scores[:, 1]).sum())
        ids = hex_ids(scores, raio)
        coords, cnts = np.unique(ids, axis=0, return_counts=True)
        self.contagens.update({tuple(map(int, pair)): int(n)
                               for pair, n in zip(coords, cnts)})


def construir_grupo(ac: Acumulador, ref: dict, raio: float, contexto: str) -> dict:
    n = ref['n_validas']
    if ac.n != n or sum(ac.contagens.values()) != n:
        raise ValueError(f'{contexto}: os hexágonos não reconciliam com POP_VALID: {ac.n}/{n}')
    # Independentemente do histograma, scores PCA devem possuir média≈0,
    # covariância diagonal com autovalores da matriz padronizada.
    medias = ac.s / n
    cov = np.array([[ac.sq[0]/n-medias[0]**2, ac.xy/n-medias[0]*medias[1]],
                    [ac.xy/n-medias[0]*medias[1], ac.sq[1]/n-medias[1]**2]])
    lam = [c['autovalor_padronizado'] for c in ref['componentes'][:2]]
    if not np.allclose(medias, 0, atol=4e-6, rtol=0) or \
       not np.allclose(np.diag(cov), lam, atol=5e-5, rtol=0) or \
       abs(cov[0,1]) > 4e-5:
        raise ValueError(f'{contexto}: momentos PC1/PC2 divergentes do IND-014: média {medias}, cov {cov}')
    pontos = []
    n_suprimidos = 0
    celulas_suprimidas = 0
    for (q, r), freq in sorted(ac.contagens.items()):
        if freq < LIMIAR:
            n_suprimidos += freq
            celulas_suprimidas += 1
            continue  # Sem coordenadas ou contagem individual da célula
        cx, cy = centro_hex(q, r, raio)
        pontos.append({'q': q, 'r': r, 'pc1': round(cx, 7), 'pc2': round(cy, 7),
                       'quantidade': freq,
                       'proporcao_populacao': round(freq/n, 10),
                       'percentual_populacao': round(100*freq/n, 6)})
    n_exibidos = sum(p['quantidade'] for p in pontos)
    if n_exibidos + n_suprimidos != n or any(p['quantidade'] < LIMIAR for p in pontos):
        raise ValueError(f'{contexto}: supressão incongruente')
    return {'n_validas': n, 'eixos': ['PC1', 'PC2'],
            'variancia_explicada': [ref['componentes'][k]['variancia_explicada'] for k in (0,1)],
            'raio_hex': raio, 'pontos': pontos,
            'n_hexagonos_exibidos': len(pontos), 'n_hexagonos_suprimidos': celulas_suprimidas,
            'n_redacoes_exibidas': n_exibidos, 'n_redacoes_suprimidas': n_suprimidos,
            'fracao_coberta': round(n_exibidos/n, 9),
            'sem_pontos_individuais': True, 'status_privacidade': 'revisao_complementar_pendente',
            'n_somas_divergentes': ref['n_somas_divergentes'],
            'delta_soma_competencias_menos_nota_redacao': ref['delta_soma_competencias_menos_nota_redacao']}


def processar_fontes(raiz: Path, m14: dict, p14: dict, raio: float, bloco: int):
    hist_ref = p14['historical']
    hist_ufs = mapa_ufs(hist_ref, 'HIST')
    hist_acc = {'BR': Acumulador(), **{u: Acumulador() for u in UFS}}
    resultados = []
    for ano in ANOS:
        anual_ref = m14[ano]
        refs_uf = mapa_ufs(anual_ref, str(ano))
        anual_acc = {'BR': Acumulador(), **{u: Acumulador() for u in UFS}}
        qa = Counter()
        arquivo = fonte(ano, raiz)
        if not arquivo.is_file():
            raise FileNotFoundError(f'Arquivo bruto ausente: {arquivo}')
        print(f'IND-016 | {ano}: transformando C1–C5 em PC1/PC2 e agregando hexágonos...', flush=True)
        for parte in pd.read_csv(arquivo, sep=';', usecols=list(COLUNAS), dtype=str,
                                 keep_default_na=False, na_filter=False,
                                 encoding='utf-8-sig', encoding_errors='replace',
                                 chunksize=bloco, on_bad_lines='error'):
            uf = parte['SG_UF_PROVA'].str.strip().str.upper()
            st = parte['TP_STATUS_REDACAO'].str.strip().eq('1')
            nota_str = parte['NU_NOTA_REDACAO'].str.strip()
            nota = pd.to_numeric(nota_str.str.replace(',', '.', regex=False), errors='coerce')
            valida = st & nota.notna() & nota.between(0, 1000)
            qa['total_registros'] += len(parte)
            qa['status1_sem_nota'] += int((st & nota_str.eq('')).sum())
            qa['status1_nota_invalida'] += int((st & nota_str.ne('') & ~(nota.notna() & nota.between(0,1000))).sum())
            qa['validas_sem_uf'] += int((valida & uf.eq('')).sum())
            qa['validas_uf_desconhecida'] += int((valida & ~uf.isin(UFS) & uf.ne('')).sum())
            qa['validas'] += int(valida.sum())
            if not bool(valida.any()):
                continue
            raw = parte.loc[valida, list(COMP)].apply(lambda s: s.str.strip())
            valores = raw.apply(lambda s: pd.to_numeric(s.str.replace(',', '.', regex=False), errors='coerce'))
            validas_comp = valores.notna() & valores.ge(0) & valores.le(200)
            boas = validas_comp.all(axis=1)
            qa['validas_competencias_incompletas'] += int((~boas).sum())
            if not bool(boas.any()):
                continue
            x = valores.loc[boas].to_numpy(dtype=float)
            siglas = uf.loc[valida].loc[boas].to_numpy(dtype=str)
            nota_total = nota.loc[valida].loc[boas].to_numpy(dtype=float)
            delta = x.sum(axis=1) - nota_total
            divergentes = np.abs(delta) > 1e-6
            qa['n_somas_divergentes'] += int(np.count_nonzero(divergentes))
            qa['delta_soma'] += float(delta[divergentes].sum())
            # Todo registro entra nos mapas BR anual e histórico.
            anual_acc['BR'].acrescentar(x, anual_ref['brasil'], raio)
            hist_acc['BR'].acrescentar(x, hist_ref['brasil'], raio)
            for uf_val in np.unique(siglas):
                if uf_val not in refs_uf:
                    continue  # Erro será identificado ao final, antes de salvar
                mask = siglas == uf_val
                a = x[mask]
                anual_acc[uf_val].acrescentar(a, refs_uf[uf_val], raio)
                hist_acc[uf_val].acrescentar(a, hist_ufs[uf_val], raio)
        expected = anual_ref['brasil']
        for key in ('status1_sem_nota', 'status1_nota_invalida', 'validas_sem_uf',
                    'validas_uf_desconhecida', 'validas_competencias_incompletas'):
            if qa[key]:
                raise ValueError(f'{ano}: inválido ({key}={qa[key]}); nada será exportado')
        if qa['total_registros'] != expected['total_registros'] or qa['validas'] != expected['n_validas']:
            raise ValueError(f'{ano}: POP_ALL/POP_VALID diverge do IND-014')
        if qa['n_somas_divergentes'] != expected['n_somas_divergentes'] or \
           abs(qa['delta_soma'] - expected['delta_soma_competencias_menos_nota_redacao']) > 1e-5:
            raise ValueError(f'{ano}: divergência de soma C1–C5 incompatível com IND-014')
        br = construir_grupo(anual_acc['BR'], anual_ref['brasil'], raio, f'{ano}/BR')
        estados = [{'uf': u, **construir_grupo(anual_acc[u], refs_uf[u], raio, f'{ano}/{u}')}
                   for u in UFS]
        if sum(g['n_validas'] for g in estados) != br['n_validas']:
            raise ValueError(f'{ano}: soma das UFs não fecha Brasil')
        resultados.append({'ano': ano, 'arquivo_fonte': arquivo.name, 'brasil': br,
                           'ufs': estados,
                           'qualidade': {'status': 'ok', 'total_registros': qa['total_registros'],
                                         'validas': qa['validas'], 'n_somas_divergentes': qa['n_somas_divergentes'],
                                         'delta_soma': qa['delta_soma'],
                                         'total_hexagonos_exibidos': sum(g['n_hexagonos_exibidos'] for g in [br,*estados]),
                                         'total_hexagonos_suprimidos': sum(g['n_hexagonos_suprimidos'] for g in [br,*estados])}})
        print(f'  válidas={br["n_validas"]:,} | hexágonos BR visíveis={len(br["pontos"]):,} '
              f'| células BR suprimidas={br["n_hexagonos_suprimidos"]:,}', flush=True)
    hist_br = construir_grupo(hist_acc['BR'], hist_ref['brasil'], raio, 'HIST/BR')
    hist_estados = [{'uf': u, **construir_grupo(hist_acc[u], hist_ufs[u], raio, f'HIST/{u}')}
                    for u in UFS]
    if sum(x['n_validas'] for x in hist_estados) != hist_br['n_validas']:
        raise ValueError('HIST: UFs não fecham Brasil')
    hist = {'periodo': '2019-2025', 'brasil': hist_br, 'ufs': hist_estados,
            'qualidade': {'status': 'ok', 'reprojecao_pca_historica': True,
                          'validas': hist_br['n_validas']}}
    return resultados, hist


def linhas_csv(anos: list[dict], hist: dict):
    linhas = []
    for d in [*anos, hist]:
        periodo = str(d.get('ano', '2019-2025'))
        for abrangencia, uf, g in [('BR', 'BR', d['brasil']), *[('UF', u['uf'], u) for u in d['ufs']]]:
            for pt in g['pontos']:
                linhas.append({'indicador_id': IND, 'periodo': periodo,
                               'abrangencia': abrangencia, 'uf': uf,
                               'hex_q': pt['q'], 'hex_r': pt['r'],
                               'pc1_centro': pt['pc1'], 'pc2_centro': pt['pc2'],
                               'quantidade': pt['quantidade'],
                               'proporcao_populacao': pt['proporcao_populacao'],
                               'percentual_populacao': pt['percentual_populacao'],
                               'n_validas': g['n_validas'],
                               'raio_hex': g['raio_hex'], 'limiar_publicacao': LIMIAR,
                               'modelo_pca': 'ajustado_no_recorte_ind014',
                               'tipo': 'hexbin_pre_agregado', 'metodo': METODO})
    if not linhas:
        raise ValueError('Nenhum hexágono com pelo menos 30 ocorrências; revise o raio')
    if any(int(l['quantidade']) < LIMIAR for l in linhas):
        raise ValueError('Célula pequena vazou para o CSV')
    return linhas


def item_dashboard(g: dict, incluir_pontos: bool = True):
    item = {k: deepcopy(g[k]) for k in ('n_validas', 'raio_hex', 'n_hexagonos_exibidos',
            'n_hexagonos_suprimidos', 'n_redacoes_exibidas', 'n_redacoes_suprimidas',
            'fracao_coberta', 'variancia_explicada', 'sem_pontos_individuais', 'status_privacidade')}
    if incluir_pontos:
        item['points'] = [{'pc1': p['pc1'], 'pc2': p['pc2'], 'count': p['quantidade'],
                           'hex_q': p['q'], 'hex_r': p['r']} for p in g['pontos']]
    return item


def construir_dashboard(d: dict, anos: list[dict], hist: dict, anterior: dict, gerado: str, sobrescrever: bool = False):
    ano = d['ano']
    dash = deepcopy(anterior)
    pca = dash['pages']['competencies']['pca']
    if not sobrescrever and 'scatter' in pca:
        raise ValueError(f'{ano}: resultado IND-016 já existe')
    pca['scatter'] = {'indicator_id': IND, 'type': 'hexbin', 'axes': ['PC1','PC2'],
                      'n': d['brasil']['n_validas'],
                      'privacy_threshold': LIMIAR,
                      'brasil': item_dashboard(d['brasil']),
                      'by_uf': [{'uf': u['uf'], **item_dashboard(u)} for u in d['ufs']],
                      'note': RESSALVAS}
    dash['pages']['temporal']['ind016'] = {
        'indicator_id': IND, 'type': 'hexbin',
        'national_by_year': [{'year': x['ano'], **item_dashboard(x['brasil'], False)} for x in anos],
        'period_total': item_dashboard(hist['brasil']),
        'period_by_uf': [{'uf': u['uf'], **item_dashboard(u)} for u in hist['ufs']],
        'historical_note': ('Escores históricos reprojetados sobre a PCA histórica; '
                            'não são médias/concatenações de mapas dos PCAs anuais.')}
    dash['pages']['methodology']['ind016'] = {
        'definition': DEFINICAO, 'population': 'POP_VALID completa',
        'catalog_population': 'AMOSTRA_ML; alternativa hexbin pré-agregado permitida',
        'geographic_dimension': 'SG_UF_PROVA', 'source_file': d['arquivo_fonte'],
        'method': METODO, 'source_pca': 'IND-014', 'source_loadings': 'IND-015',
        'hex_radius_pc_score': d['brasil']['raio_hex'],
        'privacy_threshold': LIMIAR, 'sampling': 'não; agregação hexagonal de todos os registros',
        'primary_suppression': 'células com 1–29 omitidas sem coordenadas/contagens específicas',
        'suppression_review': 'complementar pendente; não publicar', 'limitations': RESSALVAS}
    dash['quality']['ind016_validation'] = {
        'status': 'ok', 'n_validas': d['brasil']['n_validas'],
        'sem_pontos_individuais': True, 'soma_bins_igual_pop_valid': True,
        'scores_media_zero_covariancia_autovalores': True,
        'soma_27_ufs_igual_brasil': True, 'source_indicator': 'IND-014',
        'n_somas_divergentes': d['brasil']['n_somas_divergentes'],
        'delta_soma_competencias_menos_nota_redacao': d['brasil']['delta_soma_competencias_menos_nota_redacao'],
        'hexagonos_brasil_suprimidos': d['brasil']['n_hexagonos_suprimidos'],
        'redacoes_brasil_em_hexagonos_suprimidos': d['brasil']['n_redacoes_suprimidas'],
        'revisao_privacidade_obrigatoria': True, 'supressao_complementar_pendente': True,
        'metodo': METODO}
    dash['meta']['analysis_version'] = VERSAO
    dash['meta']['generated_at'] = gerado
    dash['meta']['data_status'] = 'draft'
    warnings = dash['meta'].setdefault('warnings', [])
    av = ('IND-016: mapa PC1×PC2 em hexbin agregado; células 1–29 omitidas; '
          'supressão complementar e revisão acadêmica/privacidade pendentes.')
    if av not in warnings:
        warnings.append(av)
    if d['brasil']['n_somas_divergentes']:
        av = (f'IND-016/{ano}: {d["brasil"]["n_somas_divergentes"]} exceção(ões) de soma '
              'C1–C5 preservadas e documentadas.')
        if av not in warnings:
            warnings.append(av)
    return dash


def validar_dashboard(doc: dict, raiz: Path):
    for key in ('meta','filters','quality','pages'):
        if key not in doc:
            raise ValueError(f'Dashboard sem campo {key}')
    candidatos = [raiz / 'docs' / '04_resultados_analises.schema.json',
                  raiz / 'docs' / 'metodologia' / '04_resultados_analises.schema.json',
                  raiz / '04_resultados_analises.schema.json']
    schema = next((p for p in candidatos if p.is_file()), None)
    if schema is None:
        return 'validação estrutural sem JSON Schema local'
    try:
        import jsonschema
    except ImportError as exc:
        raise ImportError('jsonschema é necessário para validar o JSON Schema') from exc
    jsonschema.validate(doc, ler_json(schema))
    return 'JSON Schema v1.0.0'


def _serializar_json(p: Path, doc: dict):
    with p.open('w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def _serializar_csv(p: Path, linhas: list[dict]):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)


def executar(raiz: Path, raio: float = RAIO, bloco: int = BLOCO, sobrescrever: bool = False):
    if raio <= 0 or not math.isfinite(raio) or bloco < 1:
        raise ValueError('Raio e bloco devem ser estritamente positivos')
    p14, p15, m14, dashboards = carregar_pre_requisitos(raiz, sobrescrever=sobrescrever)
    anos, hist = processar_fontes(raiz, m14, p14, raio, bloco)
    linhas = linhas_csv(anos, hist)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    atualizados = {ano: construir_dashboard(d, anos, hist, dashboards[ano], gerado, sobrescrever=sobrescrever)
                   for ano, d in [(d['ano'], d) for d in anos]}
    schemas = {validar_dashboard(dash, raiz) for dash in atualizados.values()}
    output = {
        'meta': {'indicator_id': IND, 'module_schema_version': 'ind016-module-1.0.0',
                 'analysis_version': VERSAO, 'dataset_version': 'enem-2019-2025-csv-publico',
                 'generated_at': gerado, 'data_status': 'draft',
                 'source_files': {str(d['ano']): d['arquivo_fonte'] for d in anos},
                 'population_definition': DEFINICAO,
                 'catalog_population': 'AMOSTRA_ML; opção hexbin pré-agregado utilizada',
                 'geographic_dimension': 'SG_UF_PROVA', 'method': METODO,
                 'hex_radius_pc_score': raio, 'suppression_threshold': LIMIAR,
                 'privacy_review_required': True, 'explanatory_notes': RESSALVAS,
                 'source_indicators': ['IND-014', 'IND-015'],
                 'source_discrepancies': p14['meta']['source_discrepancies']},
        'indicator': {'id': IND, 'name': NOME, 'unit': 'hexagonos',
                      'dashboard_json_path': 'pages.competencies.pca.scatter',
                      'output_type': 'points', 'visualization': 'Dispersão de hexágonos agregados'},
        'years': anos, 'historical': hist,
        'dashboard_files': [f'dashboard_enem_{ano}.json' for ano in ANOS]
    }
    json.dumps(output, ensure_ascii=False, allow_nan=False)
    # Gera todos os arquivos em staging antes de substituir quaisquer resultados.
    dir_json = raiz / 'outputs' / 'json'
    dir_csv = raiz / 'outputs' / 'indicadores'
    dir_json.mkdir(parents=True, exist_ok=True)
    dir_csv.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind016_staging_', dir=raiz / 'outputs') as work:
        pasta = Path(work)
        _serializar_csv(pasta / 'IND_016_mapa_pc1_pc2.csv', linhas)
        _serializar_json(pasta / 'IND_016_mapa_pc1_pc2.json', output)
        for ano in ANOS:
            _serializar_json(pasta / f'dashboard_enem_{ano}.json', atualizados[ano])
        arquivos = [('IND_016_mapa_pc1_pc2.csv', dir_csv),
                    ('IND_016_mapa_pc1_pc2.json', dir_json),
                    *[(f'dashboard_enem_{ano}.json', dir_json) for ano in ANOS]]
        for nome, destino in arquivos:
            os.replace(pasta / nome, destino / nome)
    print('\nIND-016 concluído:')
    print(f'  IND_016_mapa_pc1_pc2.csv ({len(linhas):,} hexágonos com >=30 redações)')
    print('  IND_016_mapa_pc1_pc2.json')
    print('  dashboard_enem_2019.json ... dashboard_enem_2025.json atualizados')
    print('  Contrato: ' + ', '.join(sorted(schemas)))
    print('  Sem dados individuais; células pequenas omitidas; supressão complementar pendente')
    print('  data_status=draft | revisão acadêmica e publicação pendentes')


def main():
    parser = argparse.ArgumentParser(description='IND-016 — mapa PCA PC1×PC2, hexbin protegido')
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--bloco', type=int, default=BLOCO)
    parser.add_argument('--raio', type=float, default=RAIO,
                        help='Raio dos hexágonos em unidades de score PCA (padrão 0.55)')
    parser.add_argument('--sobrescrever', action='store_true', help='Atualizar somente os blocos e resultados do IND-016 já existentes (use com backup).')
    args = parser.parse_args()
    executar(args.raiz.resolve(), args.raio, args.bloco, sobrescrever=args.sobrescrever)


if __name__ == '__main__':
    main()
