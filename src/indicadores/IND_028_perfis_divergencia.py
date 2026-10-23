#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-028: perfis exploratórios de divergência AV1×AV2 por K-Means (2019–2025).

Fonte: |NU_NOTA_COMP{i}_AV1 - NU_NOTA_COMP{i}_AV2| para i=1..5.
Universo: pares completos dentro de POP_EVALUATOR, conforme IND-021.
Amostragem: bottom-k determinístico sem reposição por ano e UF (BR inclusive),
com nova seleção de todas as participações para o consolidado histórico.

Execução, na raiz do repositório:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_028_perfis_divergencia.py
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_028_perfis_divergencia.py --somente-modulo

Não executar simultaneamente a outros indicadores que atualizem dashboards.
Os perfis amostrais NÃO representam automaticamente prevalências populacionais,
e rótulos P1..Pk NÃO são categorias comparáveis entre anos/UFs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
from sklearn.cluster import KMeans
import IND_020_diferenca_total_av1_av2 as base

ANOS = tuple(range(2019, 2026))
UFS = tuple(base.UFS)
GRUPOS = ('BR', *UFS)
IND = 'IND-028'
ARQUIVO = 'IND_028_perfis_divergencia'
METODO = 'amostragem_bottom_k_padronizacao_amostral_ddof0_kmeans_divergencias_absolutas_c1_c5'
VERSAO = '2.27.0-' + '-'.join(f'ind{i:03d}' for i in range(1, 29))
COMP = tuple(f'C{i}' for i in range(1, 6))
AV_COLS = tuple(f'NU_NOTA_COMP{i}_AV{av}' for i in range(1, 6) for av in (1,2))
MIN_N = 30
SEED = 28028
CAP_BR = 4000
CAP_UF = 2000
K_ALVO = 4
N_INIT = 20
MAX_ITER = 500
NOTAS = (
    'Agrupamento não supervisionado exploratório de |AV1-AV2| por competência C1–C5, '
    'em casos completos da POP_EVALUATOR (mesma base do IND-021). '
    'Amostragem bottom-k pseudoaleatória determinística por (ano, posição na fonte), '
    'sem reposição, independente por recorte BR/UF e com nova seleção histórica. '
    'Padronização com média e desvio-padrão ddof=0 da própria amostra do recorte; '
    'variáveis constantes recebem escala 1. k-alvo=4 é escolha exploratória, '
    'não número ótimo comprovado: reduzir k se houver clusters com menos de 30 casos. '
    'As frequências e os centroides são AMOSTRAIS; não descrevem a distribuição '
    'exata da população. P1..Pk são identificadores locais por soma crescente de '
    'divergências; não equivalem automaticamente entre anos ou UFs. '
    'Diferença não atribui erro a um avaliador. UF é de prova. Histórico acumula '
    'participações, não indivíduos únicos. Sem IDs, notas ou registros individuais '
    'nas saídas. Classificação draft até revisão metodológica e de privacidade.'
)


def ler_json(p: Path) -> dict:
    with p.open(encoding='utf-8') as f:
        return json.load(f)


def salvar_json(p: Path, obj: dict) -> None:
    with p.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n')


def recorte(p: dict, uf: str) -> dict:
    if uf == 'BR':
        return p['brasil']
    return next(x for x in p['ufs'] if x['uf'] == uf)


def splitmix64(posicoes: np.ndarray, ano: int, seed: int) -> np.ndarray:
    """Prioridade de 64 bits por edição e posição da linha; independe de --bloco."""
    mask = np.uint64(0xFFFFFFFFFFFFFFFF)
    with np.errstate(over='ignore'):
        x = (np.asarray(posicoes, dtype=np.uint64) ^
             (np.uint64(ano) << np.uint64(32)) ^ np.uint64(seed)) & mask
        x = (x + np.uint64(0x9E3779B97F4A7C15)) & mask
        x = ((x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)) & mask
        x = ((x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)) & mask
        return x ^ (x >> np.uint64(31))


class Amostra:
    """Mantém os cap registros de menor prioridade, sem armazenar IDs."""
    def __init__(self, cap: int):
        if cap < 1:
            raise ValueError('Capacidade de amostra deve ser positiva')
        self.cap = cap
        self.n = 0
        self.prior = np.empty(0, dtype=np.uint64)
        self.x = np.empty((0, 5), dtype=np.float64)

    def adicionar(self, pontos: np.ndarray, chaves: np.ndarray) -> None:
        pontos = np.asarray(pontos, dtype=np.float64)
        chaves = np.asarray(chaves, dtype=np.uint64)
        if pontos.shape != (len(chaves), 5) or not np.isfinite(pontos).all():
            raise ValueError('Amostra: dimensões inválidas ou notas não finitas')
        if np.any((pontos < 0) | (pontos > 200)):
            raise ValueError('Divergência por competência fora de 0–200')
        self.n += len(chaves)
        if not len(chaves):
            return
        if len(chaves) > self.cap:
            idx = np.argpartition(chaves, self.cap - 1)[:self.cap]
            chaves, pontos = chaves[idx], pontos[idx]
        prioridades = np.concatenate((self.prior, chaves))
        valores = np.concatenate((self.x, pontos))
        if len(prioridades) > self.cap:
            idx = np.argpartition(prioridades, self.cap - 1)[:self.cap]
            prioridades, valores = prioridades[idx], valores[idx]
        ordem = np.argsort(prioridades, kind='stable')
        self.prior, self.x = prioridades[ordem], valores[ordem]


def grupos_vazios(cap_br: int, cap_uf: int) -> dict:
    return {uf: Amostra(cap_br if uf == 'BR' else cap_uf) for uf in GRUPOS}


def acumular(grupos: dict, ufs: np.ndarray, diferencas: np.ndarray, prioridades: np.ndarray) -> None:
    if len(ufs) != len(prioridades) or diferencas.shape != (len(ufs), 5):
        raise AssertionError('Bloco não alinha notas e UFs')
    if not np.isin(ufs, UFS).all():
        raise ValueError('SG_UF_PROVA inválida entre as avaliações elegíveis')
    grupos['BR'].adicionar(diferencas, prioridades)
    for uf in np.unique(ufs):
        m = ufs == uf
        grupos[str(uf)].adicionar(diferencas[m], prioridades[m])


def ref_ind021(raiz: Path) -> dict:
    p = raiz/'outputs/json/IND_021_diferenca_por_competencia.json'
    if not p.is_file():
        raise FileNotFoundError(f'IND-021 é pré-requisito: {p}')
    doc = ler_json(p)
    if doc.get('indicator', {}).get('id') != 'IND-021' or [x.get('ano') for x in doc.get('years', [])] != list(ANOS):
        raise ValueError('IND-021 não cobre 2019–2025')
    if not doc.get('historical'):
        raise ValueError('IND-021 deve conter consolidado histórico')
    return doc


def carregar_dashboards(raiz: Path) -> dict:
    docs = {}
    for ano in ANOS:
        p = raiz/'outputs/json'/f'dashboard_enem_{ano}.json'
        d = ler_json(p)
        if d.get('meta', {}).get('year') != ano or d['meta'].get('data_status') != 'draft':
            raise ValueError(f'Dashboard {ano} com ano ou status inválidos')
        if d.get('quality', {}).get('ind027_validation', {}).get('status') != 'ok':
            raise ValueError(f'Execute o IND-027 antes do IND-028; dashboard {ano} incompleto')
        for nome in ('evaluators', 'temporal', 'methodology'):
            if not isinstance(d.get('pages', {}).get(nome), dict):
                raise ValueError(f'Falta pages.{nome} no dashboard {ano}')
        docs[ano] = d
    return docs


def validar_fontes(raiz: Path) -> None:
    for ano in ANOS:
        geo, aval = base.fonte_ano(raiz, ano)
        if not aval.is_file() or (geo is not None and not geo.is_file()):
            raise FileNotFoundError(f'Arquivos de entrada ausentes: {ano} — {geo} / {aval}')
        cols = (['NU_INSCRICAO', 'NU_ANO'] if geo else ['NU_ANO', 'SG_UF_PROVA']) + [
            'NU_NOTA_AV1', 'NU_NOTA_AV2', *AV_COLS]
        base.validar_cabecalho(aval, tuple(cols))
        if geo is not None:
            base.validar_cabecalho(geo, ('NU_INSCRICAO', 'NU_ANO', 'SG_UF_PROVA'))


def processar_ano(raiz: Path, ano: int, grupos: dict, hist: dict, bloco: int, tmp: Path) -> dict:
    geo, aval = base.fonte_ano(raiz, ano)
    cols = (['NU_INSCRICAO', 'NU_ANO'] if geo else ['NU_ANO', 'SG_UF_PROVA']) + [
        'NU_NOTA_AV1', 'NU_NOTA_AV2', *AV_COLS]
    qa = {'fonte': aval.name, 'geografia': geo.name if geo else aval.name,
          'juncao': 'NU_INSCRICAO+NU_ANO' if geo else 'mesma_linha',
          'n_linhas_fonte': 0, 'n_pop_evaluator': 0, 'n_cinco_pares_completos': 0,
          'n_pares_comp_incompletos': 0, 'n_notas_invalidas': 0,
          'n_elegiveis_sem_join': 0, 'n_uf_invalidas': 0}
    db = None
    try:
        if geo:
            db = sqlite3.connect(tmp/f'geo_ind028_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['n_linhas_geografia'] = base.construir_geo(db, geo, ano, bloco)
        print(f'IND-028 | {ano}: {aval.name}', flush=True)
        for df in base.ler_blocos(aval, cols, bloco):
            inicio = qa['n_linhas_fonte']
            qa['n_linhas_fonte'] += len(df)
            if df['NU_ANO'].str.strip().ne(str(ano)).any():
                raise ValueError(f'{ano}: NU_ANO incorreto no complemento')
            if db:
                keys = df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any():
                    raise ValueError(f'{ano}: inscrição vazia')
                try:
                    db.executemany('INSERT INTO vistos VALUES (?)', ((v,) for v in keys.tolist()))
                except sqlite3.IntegrityError as ex:
                    raise ValueError(f'{ano}: inscrição repetida') from ex
            a = df['NU_NOTA_AV1'].str.strip()
            b = df['NU_NOTA_AV2'].str.strip()
            ambos = a.ne('') & b.ne('')
            if not ambos.any():
                continue
            x = base.digitos(a[ambos]); y = base.digitos(b[ambos])
            if not (x.between(0, 1000) & y.between(0, 1000)).all():
                qa['n_notas_invalidas'] += 1
                raise ValueError(f'{ano}: nota total AV1/AV2 inválida')
            candidatos = df.loc[ambos]
            qa['n_pop_evaluator'] += len(candidatos)
            raw = candidatos[list(AV_COLS)].apply(lambda s: s.str.strip())
            completa = raw.ne('').all(axis=1).to_numpy()
            num = np.column_stack([base.digitos(raw[c]).to_numpy(dtype=np.float64) for c in AV_COLS])
            inv = ((~np.isfinite(num)) & (raw.to_numpy() != '')) | (
                np.isfinite(num) & ((num < 0) | (num > 200)))
            if np.any(inv):
                qa['n_notas_invalidas'] += int(np.any(inv, axis=1).sum())
                raise ValueError(f'{ano}: alguma nota de competência fora de [0,200]')
            cmask = completa & np.isfinite(num).all(axis=1)
            qa['n_pares_comp_incompletos'] += int((~cmask).sum())
            qa['n_cinco_pares_completos'] += int(cmask.sum())
            if not cmask.any():
                continue
            # A UF é associada apenas à amostra elegível completa; chave de inscrição
            # nunca é gravada em resultados ou no modelo.
            validos = candidatos.loc[cmask]
            mat = num[cmask]
            delta = np.abs(mat[:, ::2] - mat[:, 1::2])
            if db is not None:
                ids = validos['NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY, ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)', ((v, i) for i,v in enumerate(ids)))
                    encontrados = db.execute(
                        'SELECT l.ordem,g.uf FROM lote l JOIN geo g ON g.key=l.key AND g.ano=?',
                        (ano,)).fetchall()
                finally:
                    db.execute('DROP TABLE lote')
                if len(encontrados) != len(ids):
                    qa['n_elegiveis_sem_join'] += len(ids)-len(encontrados)
                    raise ValueError(f'{ano}: avaliações sem correspondência geográfica')
                ufs = np.empty(len(ids), dtype='<U3')
                for pos, uf in encontrados:
                    ufs[int(pos)] = str(uf).strip().upper()
            else:
                ufs = validos['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            qa['n_uf_invalidas'] += int((~np.isin(ufs, UFS)).sum())
            if qa['n_uf_invalidas']:
                raise ValueError(f'{ano}: UF inválida em avaliações elegíveis')
            # Retém o índice da linha no CSV, que não expõe nem depende do ID do aluno.
            indices = (inicio + np.flatnonzero(ambos.to_numpy())[cmask]).astype(np.uint64)
            prioridades = splitmix64(indices, ano, SEED)
            acumular(grupos, ufs, delta, prioridades)
            acumular(hist, ufs, delta, prioridades)
        if grupos['BR'].n != qa['n_cinco_pares_completos']:
            raise AssertionError(f'{ano}: totais amostrais divergentes')
        if sum(grupos[u].n for u in UFS) != grupos['BR'].n:
            raise AssertionError(f'{ano}: soma de UFs não fecha')
        print(f'  POP_EVALUATOR={qa["n_pop_evaluator"]:,}; completos={grupos["BR"].n:,}', flush=True)
        return qa
    finally:
        if db is not None:
            db.close()


def reconciliar(z: np.ndarray, labels: np.ndarray, k: int) -> tuple | None:
    """Alinha centróides às atribuições finais e protege contra centros vazios."""
    lbl = np.asarray(labels, dtype=np.int64).copy()
    for _ in range(1001):
        sizes = np.bincount(lbl, minlength=k)
        if len(sizes) != k or np.any(sizes == 0):
            return None
        centers = np.vstack([z[lbl == i].mean(axis=0) for i in range(k)])
        prox = np.argmin(((z[:, None, :] - centers[None, :, :])**2).sum(axis=2), axis=1)
        if np.array_equal(lbl, prox):
            return centers, lbl, sizes
        lbl = prox
    raise RuntimeError('Refinamento Lloyd não convergiu em 1000 iterações')


def ajustar(a: Amostra, k_alvo: int, min_n: int, seed: int, n_init: int) -> dict:
    n = len(a.x)
    if n != min(a.n, a.cap):
        raise AssertionError('Amostra: contagem diferente do esperado')
    result = {
        'n_pop_evaluator_comp_completa': int(a.n),
        'n_amostra_ml_evaluator': int(n),
        'fracao_amostrada': round(n/a.n, 10) if a.n else None,
        'populacao_ajuste': 'AMOSTRA_ML_EVALUATOR',
        'k_alvo': int(k_alvo), 'k_efetivo': None, 'clusters': [],
        'amostragem': 'bottom_k_deterministico_sem_reposicao',
        'padronizacao': None, 'inercia_amostra': None,
        'percentuais_referem_se_a': 'amostra_nao_pop_evaluator',
        'sem_dados_individuais': True,
        'n_init': int(n_init), 'limiar_minimo_cluster': int(min_n)
    }
    if n < max(min_n*2, 2):
        result['situacao'] = 'indisponivel_amostra_insuficiente'
        return result
    x = a.x
    if len(np.unique(x, axis=0)) < 2:
        result['situacao'] = 'indisponivel_sem_variabilidade'
        return result
    mu = x.mean(axis=0)
    sd = x.std(axis=0, ddof=0)
    constante = sd < 1e-12
    sd[constante] = 1.0
    z = (x-mu)/sd
    for k in range(min(k_alvo, n//min_n), 1, -1):
        if len(np.unique(x, axis=0)) < k:
            continue
        modelo = KMeans(n_clusters=k, random_state=seed, init='k-means++',
                        n_init=n_init, max_iter=MAX_ITER, tol=0.0, algorithm='lloyd')
        labels = modelo.fit_predict(z)
        r = reconciliar(z, labels, k)
        if r is None:
            continue
        centers, labels, counts = r
        if int(counts.min()) < min_n:
            continue
        inercia = float(np.sum((z-centers[labels])**2))
        if not np.isfinite(inercia):
            raise RuntimeError('Inércia K-Means não finita')
        centros_pontos = centers * sd + mu
        order = sorted(range(k), key=lambda j:(float(centros_pontos[j].sum()), *map(float,centros_pontos[j])))
        clusters = []
        for pos, j in enumerate(order, 1):
            clusters.append({
                'cluster_id': f'P{pos}', 'n_amostra': int(counts[j]),
                'percentual_amostra': round(100*int(counts[j])/n, 6),
                'centro_divergencias_pontos': [round(float(v), 6) for v in centros_pontos[j]],
                'soma_centro_divergencias': round(float(centros_pontos[j].sum()), 6),
                'centro_por_competencia': [
                    {'competencia': comp, 'diferenca_media_pontos': round(float(centros_pontos[j,ix]), 6)}
                    for ix,comp in enumerate(COMP)]
            })
        if sum(c['n_amostra'] for c in clusters) != n:
            raise AssertionError('Clusters não somam a amostra')
        result.update({
            'situacao': 'ok', 'k_efetivo': k,
            'k_reduzido_por_privacidade': bool(k < k_alvo),
            'padronizacao': {
                'media_amostra': [round(float(v), 9) for v in mu],
                'escala_amostra': [round(float(v), 9) for v in sd],
                'variavel_constante': [bool(v) for v in constante],
                'ddof': 0, 'fonte': 'AMOSTRA_ML_EVALUATOR'
            },
            'inercia_amostra': round(inercia, 8),
            'inercia_media_amostral': round(inercia/n, 8),
            'clusters': clusters,
            'centros_sao_medias_atribuidas': True
        })
        return result
    result['situacao'] = 'indisponivel_clusters_pequenos'
    return result


def compilar(grupos: dict, periodo: int | str, ref: dict,
             k: int, min_n: int, n_init: int) -> dict:
    def make(uf: str) -> dict:
        a = grupos[uf]
        esperado = recorte(ref, uf)
        if a.n != esperado['n_competencias_pareadas']:
            raise ValueError(f'{periodo}/{uf}: n={a.n} diverge do IND-021 ({esperado["n_competencias_pareadas"]})')
        seed = SEED + int.from_bytes(hashlib.sha256(f'{periodo}|{uf}'.encode()).digest()[:4], 'big')
        out = ajustar(a, k, min_n, seed, n_init)
        out['n_pop_evaluator'] = esperado['n_pop_evaluator']
        out['cobertura_competencias_pct'] = esperado['percentual_cobertura_competencias']
        return out
    br = make('BR')
    ufs = [{'uf': uf, **make(uf)} for uf in UFS]
    if sum(g['n_pop_evaluator_comp_completa'] for g in ufs) != br['n_pop_evaluator_comp_completa']:
        raise AssertionError(f'{periodo}: soma das UFs não bate')
    faltam = sum(g['situacao'] != 'ok' for g in [br,*ufs])
    ret = {'brasil':br, 'ufs':ufs, 'qualidade':{
        'status': 'ok' if faltam == 0 else 'partial',
        'soma_27_ufs_igual_brasil':True,
        'conferencia_denominadores_ind021':True,
        'recortes_indisponiveis':faltam, 'minimum_cluster_n':min_n}}
    if isinstance(periodo,int): ret['ano'] = periodo
    else: ret['periodo'] = str(periodo)
    return ret


def atualizar_dashboard(d:dict, p:dict, anos:list[dict], hist:dict, gerado:str) -> dict:
    novo=deepcopy(d)
    ev=novo['pages']['evaluators']
    ev['divergence_clusters']={
        'indicator_id':IND,'population':'AMOSTRA_ML_EVALUATOR',
        'method':METODO,'brasil':deepcopy(p['brasil']),
        'by_uf':deepcopy(p['ufs']),'notes':NOTAS}
    ev['status']='partial'
    ev['reason']='IND-020 a IND-028 disponíveis; demais análises podem estar pendentes'
    novo['pages']['temporal']['ind028']={
        'indicator_id':IND,'population':'AMOSTRA_ML_EVALUATOR',
        'national_by_year':[{'year':v['ano'],**deepcopy(v['brasil'])} for v in anos],
        'period_total':deepcopy(hist['brasil']), 'period_by_uf':deepcopy(hist['ufs']),
        'note':'Modelos independentes por recorte. Não comparar P1..Pk entre anos/UFs sem alinhar centroides.'}
    novo['pages']['methodology']['ind028']={
        'definition':'Agrupamento exploratório de perfis de divergência AV1/AV2 por competência.',
        'input_features':[f'|NU_NOTA_COMP{i}_AV1 - NU_NOTA_COMP{i}_AV2|' for i in range(1,6)],
        'population':'AMOSTRA_ML_EVALUATOR extraída dos pares completos da POP_EVALUATOR',
        'method':METODO,'n_init':N_INIT,'minimum_cluster_n':MIN_N,
        'limitations':NOTAS}
    novo['quality']['ind028_validation']={
        'status': 'ok' if p['qualidade']['recortes_indisponiveis']==0 else 'partial',
        'source_indicator':'IND-021',
        'n_pop_evaluator_comp_completa_brasil':p['brasil']['n_pop_evaluator_comp_completa'],
        'n_amostra_brasil':p['brasil']['n_amostra_ml_evaluator'],
        'soma_27_ufs_igual_brasil':True,
        'n_recortes_sem_cluster_publicavel':p['qualidade']['recortes_indisponiveis'],
        'n_registros_individuais_exportados':0,
        'revisao_academica_pendente':True,'revisao_privacidade_pendente':True}
    novo['meta']['analysis_version']=VERSAO
    novo['meta']['generated_at']=gerado
    novo['meta']['data_status']='draft'
    aviso='IND-028: K-Means sobre amostra de divergências C1–C5; perfis exploratórios, revisão acadêmica e privacidade pendentes.'
    if aviso not in novo['meta'].setdefault('warnings',[]):
        novo['meta']['warnings'].append(aviso)
    return novo


def executar(raiz:Path,bloco:int=100_000,cap_br:int=CAP_BR,cap_uf:int=CAP_UF,
             k:int=K_ALVO,n_init:int=N_INIT,min_cluster:int=MIN_N,
             somente_modulo:bool=False,sobrescrever:bool=False) -> dict:
    if min(bloco,cap_br,cap_uf,n_init,min_cluster)>=1 and 2<=k<=8:
        pass
    else:
        raise ValueError('Parâmetros inválidos: bloco/capacidades/n_init/min_cluster>0, k entre 2 e 8')
    if cap_br < min_cluster*2 or cap_uf < min_cluster*2:
        raise ValueError('As capacidades devem permitir pelo menos dois clusters seguros')
    referencia=ref_ind021(raiz)
    validar_fontes(raiz)
    dashboards={} if somente_modulo else carregar_dashboards(raiz)
    j=raiz/'outputs/json';c=raiz/'outputs/indicadores'
    destinos=[j/f'{ARQUIVO}.json', c/f'{ARQUIVO}.csv']
    if not sobrescrever:
        for p in destinos:
            if p.exists():
                raise FileExistsError(f'{p}: já existe; use --sobrescrever')
        for ano,d in dashboards.items():
            if 'ind028_validation' in d['quality'] or 'divergence_clusters' in d['pages']['evaluators']:
                raise FileExistsError(f'IND-028 já integrado ao dashboard {ano}')
    hashes=({ano:hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
             for ano in ANOS} if not somente_modulo else {})
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    annual=[];historico=grupos_vazios(cap_br,cap_uf);qas={}
    with tempfile.TemporaryDirectory(prefix='ind028_sql_',dir=out) as dirname:
        for ano,ref in zip(ANOS,referencia['years']):
            g=grupos_vazios(cap_br,cap_uf)
            qas[str(ano)]=processar_ano(raiz,ano,g,historico,bloco,Path(dirname))
            p=compilar(g,ano,ref,k,min_cluster,n_init)
            p['qualidade_fonte']=qas[str(ano)]
            annual.append(p)
    hist=compilar(historico,'2019-2025',referencia['historical'],k,min_cluster,n_init)
    for uf in GRUPOS:
        if sum(recorte(p,uf)['n_pop_evaluator_comp_completa'] for p in annual) != recorte(hist,uf)['n_pop_evaluator_comp_completa']:
            raise AssertionError(f'{uf}: total histórico diferente das participações anuais')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    modulo={
        'meta':{'indicator_id':IND,'module_schema_version':'ind028-module-1.0.0',
                'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
                'generated_at':gerado,'data_status':'draft','source_indicator':'IND-021',
                'population_definition':'AMOSTRA_ML_EVALUATOR de POP_EVALUATOR com cinco pares completos',
                'geographic_dimension':'SG_UF_PROVA','method':METODO,
                'k_target':k,'sample_cap_br':cap_br,'sample_cap_uf':cap_uf,
                'n_init':n_init,'minimum_cluster_n':min_cluster,'seed':SEED,
                'source_qa':qas, 'publication_status':'draft; revisão acadêmica e privacidade pendentes',
                'notes':NOTAS},
        'indicator':{'id':IND,'name':'Perfis de divergência','unit':'clusters',
                     'dashboard_json_path':'pages.evaluators.divergence_clusters',
                     'visualization':'Perfis'},
        'years':annual,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    novos={ano:atualizar_dashboard(dashboards[ano],annual[i],annual,hist,gerado)
           for i,ano in enumerate(ANOS)} if not somente_modulo else {}
    for ano,d in novos.items():
        if d['meta']['year']!=ano or d['quality']['ind027_validation']['status']!='ok':
            raise ValueError(f'IND-027 não foi preservado no dashboard {ano}')
        for sch in (raiz/'04_resultados_analises.schema.json',raiz/'docs/04_resultados_analises.schema.json'):
            if sch.is_file():
                try: import jsonschema
                except ImportError: break
                jsonschema.validate(d,ler_json(sch));break
    rows=[]
    for periodo in (*annual,hist):
        tag=str(periodo.get('ano','2019-2025'))
        for uf,g in [('BR',periodo['brasil']),*((v['uf'],v) for v in periodo['ufs'])]:
            # Mantém uma linha, mesmo quando k é indisponível, para auditar 224 recortes.
            clusters=g['clusters'] if g['clusters'] else [None]
            for cl in clusters:
                row={'indicador_id':IND,'periodo':tag,'uf':uf,'abrangencia':'BR' if uf=='BR' else 'UF',
                     'situacao':g['situacao'],'n_pop_evaluator':g['n_pop_evaluator'],
                     'n_pop_evaluator_comp_completa':g['n_pop_evaluator_comp_completa'],
                     'n_amostra_ml_evaluator':g['n_amostra_ml_evaluator'],
                     'k_alvo':g['k_alvo'],'k_efetivo':g['k_efetivo'],
                     'cluster_id':cl['cluster_id'] if cl else '',
                     'n_cluster_amostra':cl['n_amostra'] if cl else '',
                     'percentual_amostra':cl['percentual_amostra'] if cl else '',
                     'soma_centro_divergencias':cl['soma_centro_divergencias'] if cl else '',
                     'metodo':METODO}
                for i in range(1,6):
                    row[f'centro_delta_C{i}']=cl['centro_divergencias_pontos'][i-1] if cl else ''
                rows.append(row)
    json.dumps(modulo,allow_nan=False)
    with tempfile.TemporaryDirectory(prefix='.ind028_stage_',dir=out) as dirname:
        stage=Path(dirname)
        srcj=stage/f'{ARQUIVO}.json'; srcc=stage/f'{ARQUIVO}.csv'
        salvar_json(srcj,modulo)
        with srcc.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';')
            writer.writeheader();writer.writerows(rows)
        gravacoes=[(srcj,destinos[0]),(srcc,destinos[1])]
        for ano, d in novos.items():
            fn=stage/f'dashboard_enem_{ano}.json'
            salvar_json(fn,d)
            gravacoes.append((fn,j/fn.name))
        for ano in ANOS:
            if not somente_modulo and hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()!=hashes[ano]:
                raise RuntimeError(f'Dashboard {ano} foi alterado durante execução: nada foi gravado')
        for src,dest in gravacoes:
            dest.parent.mkdir(parents=True,exist_ok=True)
            os.replace(src,dest)
    ok=sum(recorte(p,u)['situacao']=='ok' for p in (*annual,hist) for u in GRUPOS)
    print(f'IND-028 concluído: {ok}/224 recortes com clusters; {len(rows)} linhas CSV.',flush=True)
    print('Arquivos:',*map(str,destinos),sep='\n  ')
    return modulo


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path.cwd())
    ap.add_argument('--bloco',type=int,default=100_000)
    ap.add_argument('--cap-br',type=int,default=CAP_BR)
    ap.add_argument('--cap-uf',type=int,default=CAP_UF)
    ap.add_argument('--k',type=int,default=K_ALVO)
    ap.add_argument('--n-init',type=int,default=N_INIT)
    ap.add_argument('--somente-modulo',action='store_true',help='não modifica dashboards')
    ap.add_argument('--sobrescrever',action='store_true')
    args=ap.parse_args()
    executar(args.base.resolve(),bloco=args.bloco,cap_br=args.cap_br,cap_uf=args.cap_uf,
             k=args.k,n_init=args.n_init,somente_modulo=args.somente_modulo,
             sobrescrever=args.sobrescrever)


if __name__ == '__main__':
    main()
