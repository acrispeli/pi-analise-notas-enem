#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-029: padrões atípicos de divergência entre AV1 e AV2 (2019–2025).

Algoritmo: Isolation Forest (contamination='auto'), sobre:
  [AV1_TOTAL - AV2_TOTAL, |C1_AV1-C1_AV2|, ..., |C5_AV1-C5_AV2|].
Fonte e universo: mesmos pares completos de POP_EVALUATOR e mesma amostra
bottom-k determinística do IND-028; amostra é por recorte BR/UF e período.

Exemplos, da raiz do projeto (somente após terminar o IND-028):
  python src/indicadores/IND_029_avaliacoes_atipicas.py
  python src/indicadores/IND_029_avaliacoes_atipicas.py --somente-modulo
  python src/indicadores/IND_029_avaliacoes_atipicas.py --sobrescrever

Atípico NÃO significa erro, fraude, irregularidade ou responsabilidade de corretor.
"""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
from sklearn.ensemble import IsolationForest
import IND_028_perfis_divergencia as prev

BASE = prev.base
ANOS = prev.ANOS
UFS = prev.UFS
GRUPOS = prev.GRUPOS
AV_COLS = prev.AV_COLS
IND = 'IND-029'
ARQUIVO = 'IND_029_avaliacoes_atipicas'
METODO = 'isolation_forest_contamination_auto_bottom_k_seis_atributos'
VERSAO = '2.28.0-' + '-'.join(f'ind{i:03d}' for i in range(1, 30))
SEED_AMOSTRA = prev.SEED
SEED_MODELO = 42
MIN_N = 30
N_ESTIMATORS = 100
ATRIBUTOS = ('delta_total_av1_menos_av2', *(f'abs_delta_C{i}' for i in range(1, 6)))
LIMIARES = (0.45, 0.50, 0.55)
NOTAS = (
    'Detecção exploratória de padrões estatisticamente atípicos usando Isolation Forest. '
    'Atributos: diferença ASSINADA da nota total (AV1−AV2) e diferenças ABSOLUTAS '
    'das cinco competências. Não significa erro de correção, fraude nem identifica '
    'avaliador individual: AV1/AV2 são apenas posições no fluxo. A população é '
    'AMOSTRA_ML_EVALUATOR da POP_EVALUATOR com cinco pares completos, idêntica à '
    'amostra bottom-k do IND-028 em cada recorte. Modelo independente por ano/UF '
    'e por consolidado histórico, sem extrapolar frequências amostrais à população. '
    'contamination="auto" usa decisão por score_samples<-0.5, correspondente '
    'a escore de anomalia (-score_samples)>0.5; escore maior significa mais '
    'atípico. Limiar não é calibração de uma probabilidade real de erro. '
    'As cinco faixas de distribuição têm tamanho aproximadamente igual por ranking; '
    'empates podem cruzar suas fronteiras. Taxas de limiares alternativos representam '
    'sensibilidade de corte sobre o MESMO modelo, não validação de estabilidade. '
    'Valores de células de 1 a 29 são suprimidos; nenhuma saída inclui notas, '
    'escores ou identificadores individuais. UF é da prova. Histórico agrega '
    'participações, não pessoas únicas. Dados draft: revisão acadêmica e '
    'de privacidade complementar pendentes.'
)


def ler_json(p: Path) -> dict:
    return prev.ler_json(p)


def gravar_json(p: Path, obj: dict) -> None:
    prev.salvar_json(p, obj)


def recorte(periodo: dict, uf: str) -> dict:
    return prev.recorte(periodo, uf)


class Amostra6:
    """Mantém as 6 colunas dos menores hashes; n conta TODA a população elegível."""
    def __init__(self, cap: int):
        if cap < 1:
            raise ValueError('cap deve ser positivo')
        self.cap = cap
        self.n = 0
        self.prior = np.empty(0, dtype=np.uint64)
        self.x = np.empty((0, 6), dtype=np.float64)

    def adicionar(self, valores: np.ndarray, chaves: np.ndarray) -> None:
        valores = np.asarray(valores, dtype=np.float64)
        chaves = np.asarray(chaves, dtype=np.uint64)
        if valores.shape != (len(chaves), 6) or not np.isfinite(valores).all():
            raise ValueError('Amostra: formato inválido ou valores não finitos')
        if np.any(np.abs(valores[:, 0]) > 1000) or np.any((valores[:, 1:] < 0) | (valores[:, 1:] > 200)):
            raise ValueError('Amostra: diferenças fora dos limites de nota')
        self.n += len(chaves)
        if not len(chaves):
            return
        if len(chaves) > self.cap:
            ix = np.argpartition(chaves, self.cap - 1)[:self.cap]
            chaves, valores = chaves[ix], valores[ix]
        chaves = np.concatenate([self.prior, chaves])
        valores = np.concatenate([self.x, valores], axis=0)
        if len(chaves) > self.cap:
            ix = np.argpartition(chaves, self.cap - 1)[:self.cap]
            chaves, valores = chaves[ix], valores[ix]
        ix = np.argsort(chaves, kind='stable')
        self.prior, self.x = chaves[ix], valores[ix]


def grupos_vazios(cap_br: int, cap_uf: int) -> dict:
    return {u: Amostra6(cap_br if u == 'BR' else cap_uf) for u in GRUPOS}


def acumular(grupos: dict, ufs: np.ndarray, x: np.ndarray, prior: np.ndarray) -> None:
    if x.shape != (len(ufs), 6) or len(ufs) != len(prior):
        raise ValueError('Entradas de acumulação desalinhadas')
    if not np.isin(ufs, UFS).all():
        raise ValueError('UF ausente ou desconhecida')
    grupos['BR'].adicionar(x, prior)
    for uf in np.unique(ufs):
        mask = ufs == uf
        grupos[str(uf)].adicionar(x[mask], prior[mask])


def referencias(raiz: Path) -> tuple[dict, dict, int, int]:
    r21 = prev.ref_ind021(raiz)
    arquivo = raiz/'outputs/json/IND_028_perfis_divergencia.json'
    if not arquivo.is_file():
        raise FileNotFoundError(f'IND-028 é pré-requisito: {arquivo}')
    r28 = ler_json(arquivo)
    meta = r28.get('meta', {})
    if r28.get('indicator', {}).get('id') != 'IND-028' or [y.get('ano') for y in r28.get('years', [])] != list(ANOS):
        raise ValueError('IND-028 inválido ou sem todos os anos')
    if not isinstance(r28.get('historical'), dict):
        raise ValueError('IND-028 sem histórico')
    if meta.get('seed') != SEED_AMOSTRA or meta.get('method') != prev.METODO:
        raise ValueError('IND-028 deve utilizar amostragem bottom-k compatível')
    cap_br, cap_uf = int(meta['sample_cap_br']), int(meta['sample_cap_uf'])
    if cap_br < MIN_N or cap_uf < MIN_N:
        raise ValueError('IND-028 utilizou amostra com capacidade inferior a 30')
    for p21, p28 in zip([*r21['years'],r21['historical']], [*r28['years'],r28['historical']]):
        for uf in GRUPOS:
            a, b = recorte(p21,uf), recorte(p28,uf)
            if b['n_pop_evaluator_comp_completa'] != a['n_competencias_pareadas']:
                raise ValueError(f'IND-028 e IND-021 discordam no denominador: {uf}')
    return r21, r28, cap_br, cap_uf


def dashboards_existentes(raiz: Path) -> dict:
    docs = prev.carregar_dashboards(raiz)  # Verifica IND-027 e os blocos principais.
    for ano, d in docs.items():
        v = d['quality'].get('ind028_validation', {})
        if v.get('status') not in ('ok', 'partial') or d['pages']['evaluators'].get('divergence_clusters', {}).get('indicator_id') != 'IND-028':
            raise ValueError(f'IND-028 não está integrado ao dashboard {ano}')
    return docs


def processar_ano(raiz: Path, ano: int, grupos: dict, hist: dict, bloco: int, tmp: Path) -> dict:
    geo, aval = BASE.fonte_ano(raiz, ano)
    cols = (['NU_INSCRICAO','NU_ANO'] if geo else ['NU_ANO','SG_UF_PROVA']) + [
        'NU_NOTA_AV1','NU_NOTA_AV2',*AV_COLS]
    qa = {'fonte':aval.name, 'geografia':geo.name if geo else aval.name,
          'juncao':'NU_INSCRICAO+NU_ANO' if geo else 'mesma_linha',
          'n_linhas_fonte':0, 'n_pop_evaluator':0,
          'n_cinco_pares_completos':0, 'n_incompletos':0,
          'n_elegiveis_sem_join':0,'n_uf_invalidas':0}
    db = None
    try:
        if geo:
            db = sqlite3.connect(tmp/f'geo_ind029_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['n_linhas_geografia'] = BASE.construir_geo(db,geo,ano,bloco)
        print(f'IND-029 | {ano}: {aval.name}',flush=True)
        for df in BASE.ler_blocos(aval,cols,bloco):
            inicio = qa['n_linhas_fonte']
            qa['n_linhas_fonte'] += len(df)
            if df['NU_ANO'].str.strip().ne(str(ano)).any():
                raise ValueError(f'{ano}: NU_ANO diferente do esperado')
            if db is not None:
                chaves = df['NU_INSCRICAO'].str.strip()
                if chaves.eq('').any():
                    raise ValueError(f'{ano}: NU_INSCRICAO vazia')
                try:
                    db.executemany('INSERT INTO vistos VALUES (?)', ((x,) for x in chaves.tolist()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f'{ano}: NU_INSCRICAO duplicada') from exc
            s1, s2 = df['NU_NOTA_AV1'].str.strip(), df['NU_NOTA_AV2'].str.strip()
            ambos = s1.ne('') & s2.ne('')
            if not ambos.any():
                continue
            v1 = BASE.digitos(s1[ambos]); v2 = BASE.digitos(s2[ambos])
            if not (v1.between(0,1000) & v2.between(0,1000)).all():
                raise ValueError(f'{ano}: nota total AV1/AV2 inválida')
            candidatos = df.loc[ambos]
            qa['n_pop_evaluator'] += len(candidatos)
            raw = candidatos[list(AV_COLS)].apply(lambda s:s.str.strip())
            completo = raw.ne('').all(axis=1).to_numpy()
            numero = np.column_stack([BASE.digitos(raw[c]).to_numpy(dtype=np.float64) for c in AV_COLS])
            invalido = (((~np.isfinite(numero)) & (raw.to_numpy() != '')) |
                        (np.isfinite(numero) & ((numero < 0) | (numero > 200))))
            if invalido.any():
                raise ValueError(f'{ano}: notas das competências inválidas')
            ok = completo & np.isfinite(numero).all(axis=1)
            qa['n_incompletos'] += int((~ok).sum())
            qa['n_cinco_pares_completos'] += int(ok.sum())
            if not ok.any():
                continue
            validos = candidatos.loc[ok]
            mat = numero[ok]
            total = (v1.to_numpy(dtype=np.float64) - v2.to_numpy(dtype=np.float64))[ok]
            features = np.column_stack((total, np.abs(mat[:, ::2] - mat[:, 1::2])))
            if db is not None:
                ids = validos['NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY, ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)', ((v,i) for i,v in enumerate(ids)))
                    found = db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g ON g.key=l.key AND g.ano=?',(ano,)).fetchall()
                finally:
                    db.execute('DROP TABLE lote')
                if len(found) != len(ids):
                    qa['n_elegiveis_sem_join'] += len(ids)-len(found)
                    raise ValueError(f'{ano}: avaliações sem junção geográfica')
                ufs = np.empty(len(ids),dtype='<U3')
                for p,uf in found:
                    ufs[int(p)] = str(uf).strip().upper()
            else:
                ufs = validos['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            qa['n_uf_invalidas'] += int((~np.isin(ufs,UFS)).sum())
            if qa['n_uf_invalidas']:
                raise ValueError(f'{ano}: UF inválida')
            idx = (inicio + np.flatnonzero(ambos.to_numpy())[ok]).astype(np.uint64)
            prioridades = prev.splitmix64(idx,ano,SEED_AMOSTRA)
            acumular(grupos,ufs,features,prioridades)
            acumular(hist,ufs,features,prioridades)
        if grupos['BR'].n != qa['n_cinco_pares_completos'] or sum(grupos[u].n for u in UFS) != grupos['BR'].n:
            raise AssertionError(f'{ano}: somas de denominadores não conferem')
        print(f'  pares completos={grupos["BR"].n:,}',flush=True)
        return qa
    finally:
        if db is not None:
            db.close()


def contagem_publicavel(qtd: int, n: int, minimo: int) -> bool:
    return (qtd == 0 or qtd >= minimo) and (n-qtd == 0 or n-qtd >= minimo)


def percentil(x: np.ndarray, q: float) -> float:
    return round(float(np.quantile(x,q)), 8)


def avaliar(a: Amostra6, n_estimators: int, min_n: int, seed: int) -> dict:
    n = len(a.x)
    if n != min(a.n,a.cap):
        raise AssertionError('Amostra não contém o número esperado')
    ret = {'n_pop_evaluator_comp_completa':int(a.n),
           'n_amostra_ml_evaluator':n,
           'fracao_amostrada':round(n/a.n,10) if a.n else None,
           'populacao':'AMOSTRA_ML_EVALUATOR',
           'amostragem':'bottom_k_deterministico_mesma_amostra_ind028',
           'n_estimators':n_estimators,'contamination':'auto',
           'features':list(ATRIBUTOS),
           'limiar_escore_auto':0.5,
           'n_sinalizados_auto':None,'percentual_sinalizados_auto':None,
           'escore_anomalia':'-score_samples (maior = mais atipico)',
           'score_summary':None,'histograma_quintis':[],
           'sensibilidade_limites':[],
           'media_atributos_amostra':None,'media_atributos_sinalizados':None,
           'sem_dados_individuais':True}
    if n < max(min_n,30):
        ret['situacao'] = 'indisponivel_amostra_inferior_30'
        return ret
    modelo = IsolationForest(n_estimators=n_estimators,max_samples='auto',
                            contamination='auto',random_state=seed,n_jobs=1)
    modelo.fit(a.x)
    scores = -modelo.score_samples(a.x)
    if not np.isfinite(scores).all():
        raise ArithmeticError('Escore não finito')
    ret['media_atributos_amostra'] = {c:round(float(v),6) for c,v in zip(ATRIBUTOS,a.x.mean(axis=0))}
    ret['score_summary'] = {name:percentil(scores,q) for name,q in
                            [('min',0),('p05',.05),('p25',.25),('p50',.5),
                             ('p75',.75),('p95',.95),('max',1)]}
    ret['score_summary']['media'] = round(float(scores.mean()),8)
    ret['sample_size_modelo'] = min(n,256)
    ret['model_offset'] = round(float(modelo.offset_),8)
    # Faixas de quintis por rank, sem dados por indivíduo. Cada contagem >=30.
    if n >= 5*min_n:
        s_ord = np.sort(scores, kind='stable')
        for i, ids in enumerate(np.array_split(np.arange(n),5),1):
            lo,hi = int(ids[0]),int(ids[-1])
            ret['histograma_quintis'].append({
                'quintil':f'Q{i}', 'n_amostra':len(ids),
                'percentual_amostra':round(100*len(ids)/n,6),
                'escore_min':round(float(s_ord[lo]),8),
                'escore_max':round(float(s_ord[hi]),8)})
    mascara = scores > 0.5  # sklearn: decision_function = score_samples - offset_, offset_=-0.5
    n_auto = int(mascara.sum())
    visivel = contagem_publicavel(n_auto,n,min_n)
    ret['sinalizacao_suprimida'] = not visivel
    if visivel:
        ret['n_sinalizados_auto'] = n_auto
        ret['percentual_sinalizados_auto'] = round(100*n_auto/n,6)
        if n_auto >= min_n:
            ret['media_atributos_sinalizados'] = {
                c:round(float(v),6) for c,v in zip(ATRIBUTOS,a.x[mascara].mean(axis=0))}
    # Proteção complementar: a subtração de dois limiares publicados
    # também não pode revelar grupos positivos com menos de 30 casos.
    counts_publicados = [n_auto] if visivel else []
    # Limite 0.50 primeiro, depois vizinhos; prioridade ao limiar primário.
    calculados = {cutoff:int(np.count_nonzero(scores > cutoff)) for cutoff in LIMIARES}
    permitidos = {}
    for cutoff in (0.50,0.45,0.55):
        qty = calculados[cutoff]
        permitido = contagem_publicavel(qty,n,min_n)
        if permitido:
            permitido = all(abs(qty - v) == 0 or abs(qty - v) >= min_n
                            for v in counts_publicados)
        permitidos[cutoff] = permitido
        if permitido: counts_publicados.append(qty)
    for cutoff in LIMIARES:
        qty = calculados[cutoff]
        permitido = permitidos[cutoff]
        ret['sensibilidade_limites'].append({
            'limiar_escore':cutoff,
            'n_sinalizados_amostra':qty if permitido else None,
            'percentual_amostra':round(100*qty/n,6) if permitido else None,
            'suprimido':not permitido})
    ret['situacao'] = 'ok' if visivel else 'parcial_sinalizacao_suprimida'
    return ret


def compilar(grupos: dict, periodo: int|str, r21: dict, r28: dict,
             n_estimators: int, min_n: int) -> dict:
    def montar(uf: str) -> dict:
        a = grupos[uf]
        r021 = recorte(r21,uf)
        r028 = recorte(r28,uf)
        if a.n != r021['n_competencias_pareadas'] or a.n != r028['n_pop_evaluator_comp_completa']:
            raise ValueError(f'{periodo}/{uf}: base diverge de IND-021/028')
        if len(a.x) != r028['n_amostra_ml_evaluator']:
            raise ValueError(f'{periodo}/{uf}: tamanho da amostra diverge de IND-028')
        r = avaliar(a,n_estimators,min_n,SEED_MODELO)
        r['n_pop_evaluator'] = int(r021['n_pop_evaluator'])
        r['cobertura_competencias_pct'] = r021['percentual_cobertura_competencias']
        return r
    br = montar('BR')
    uf = [{'uf':u,**montar(u)} for u in UFS]
    if sum(g['n_pop_evaluator_comp_completa'] for g in uf) != br['n_pop_evaluator_comp_completa']:
        raise AssertionError('Soma das 27 UFs diferente do Brasil')
    ret = {'brasil':br,'ufs':uf,'qualidade':{
        'status':'ok' if all(g['situacao']=='ok' for g in [br,*uf]) else 'partial',
        'soma_27_ufs_igual_brasil':True,
        'base_igual_ind021_ind028':True,
        'recortes_sinalizacao_suprimida':sum(g['sinalizacao_suprimida'] for g in [br,*uf] if 'sinalizacao_suprimida' in g),
        'limiar_minimo_publicacao':min_n}}
    if isinstance(periodo,int):ret['ano']=periodo
    else: ret['periodo']=str(periodo)
    return ret


def atualizar_dashboard(d:dict,p:dict,anos:list[dict],historico:dict,gerado:str) -> dict:
    d=deepcopy(d)
    d['pages']['evaluators']['anomalies']={
        'indicator_id':IND, 'method':METODO,'population':'AMOSTRA_ML_EVALUATOR',
        'brasil':deepcopy(p['brasil']), 'by_uf':deepcopy(p['ufs']), 'notes':NOTAS}
    d['pages']['evaluators']['status']='partial'
    d['pages']['evaluators']['reason']='IND-020 a IND-029 disponíveis; demais análises pendentes'
    d['pages']['temporal']['ind029']={
        'indicator_id':IND,'population':'AMOSTRA_ML_EVALUATOR',
        'national_by_year':[{'year':a['ano'],**deepcopy(a['brasil'])} for a in anos],
        'period_total':deepcopy(historico['brasil']),
        'period_by_uf':deepcopy(historico['ufs']),
        'note':'Isolation Forest ajustado de modo independente para cada recorte. Escores não calibrados para comparação direta entre modelos.'}
    d['pages']['methodology']['ind029']={
        'definition':'Isolation Forest para divergências atípicas entre as notas AV1 e AV2.',
        'input_features':list(ATRIBUTOS), 'population':'AMOSTRA_ML_EVALUATOR',
        'method':METODO, 'contamination':'auto','seed_model':SEED_MODELO,
        'anomaly_threshold':0.5, 'threshold_source':'sklearn offset_=-0.5',
        'limitations':NOTAS}
    d['quality']['ind029_validation']={
        'status':p['qualidade']['status'],'source_indicator':'IND-028/IND-021',
        'n_amostra_brasil':p['brasil']['n_amostra_ml_evaluator'],
        'n_pop_evaluator_comp_completa_brasil':p['brasil']['n_pop_evaluator_comp_completa'],
        'soma_27_ufs_igual_brasil':True,
        'recortes_sinalizacao_suprimida':p['qualidade']['recortes_sinalizacao_suprimida'],
        'n_registros_individuais_exportados':0,
        'revisao_academica_pendente':True,'revisao_privacidade_pendente':True}
    d['meta']['analysis_version']=VERSAO
    d['meta']['generated_at']=gerado
    d['meta']['data_status']='draft'
    aviso='IND-029: Isolation Forest exploratório sobre divergências AV1/AV2; atípico não significa erro/fraude; revisão acadêmica e de privacidade pendentes.'
    if aviso not in d['meta'].setdefault('warnings',[]):
        d['meta']['warnings'].append(aviso)
    return d


def executar(raiz:Path,bloco:int=100_000,n_estimators:int=N_ESTIMATORS,
             min_n:int=MIN_N,somente_modulo:bool=False,sobrescrever:bool=False)->dict:
    if min(bloco,n_estimators,min_n)<1 or min_n<30:
        raise ValueError('bloco, n_estimators>0 e mínimo de privacidade>=30')
    r21,r28,cap_br,cap_uf=referencias(raiz)
    prev.validar_fontes(raiz)
    dashes={} if somente_modulo else dashboards_existentes(raiz)
    j=raiz/'outputs/json';c=raiz/'outputs/indicadores'
    destinos=[j/f'{ARQUIVO}.json',c/f'{ARQUIVO}.csv']
    if not sobrescrever:
        for p in destinos:
            if p.exists(): raise FileExistsError(f'Arquivo existente: {p}; use --sobrescrever')
        for ano,d in dashes.items():
            if 'ind029_validation' in d['quality'] or 'anomalies' in d['pages']['evaluators']:
                raise FileExistsError(f'IND-029 já integrado ao dashboard {ano}')
    hashes=({ano:hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
            for ano in ANOS} if not somente_modulo else {})
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    annual=[];historico=grupos_vazios(cap_br,cap_uf);qas={}
    with tempfile.TemporaryDirectory(prefix='ind029_sql_',dir=out) as tmp:
        for i,ano in enumerate(ANOS):
            grupos=grupos_vazios(cap_br,cap_uf)
            qas[str(ano)]=processar_ano(raiz,ano,grupos,historico,bloco,Path(tmp))
            p=compilar(grupos,ano,r21['years'][i],r28['years'][i],n_estimators,min_n)
            p['qualidade_fonte']=qas[str(ano)]
            annual.append(p)
    hist=compilar(historico,'2019-2025',r21['historical'],r28['historical'],n_estimators,min_n)
    for uf in GRUPOS:
        if sum(recorte(p,uf)['n_pop_evaluator_comp_completa'] for p in annual)!=recorte(hist,uf)['n_pop_evaluator_comp_completa']:
            raise AssertionError(f'{uf}: soma histórica incorreta')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    modulo={
        'meta':{'indicator_id':IND,'module_schema_version':'ind029-module-1.0.0',
                'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
                'generated_at':gerado,'data_status':'draft','source_indicator':'IND-028/IND-021',
                'population_definition':'AMOSTRA_ML_EVALUATOR da POP_EVALUATOR com cinco pares completos',
                'geographic_dimension':'SG_UF_PROVA','method':METODO,
                'model_seed':SEED_MODELO,'sample_seed':SEED_AMOSTRA,
                'sample_cap_br':cap_br,'sample_cap_uf':cap_uf,
                'n_estimators':n_estimators,'contamination':'auto',
                'anomaly_score_threshold':0.5,'minimum_group_count':min_n,
                'source_qa':qas,
                'publication_status':'draft; revisão acadêmica e de privacidade pendentes',
                'notes':NOTAS},
        'indicator':{'id':IND,'name':'Avaliações atípicas',
                     'unit':'anomaly_summary',
                     'dashboard_json_path':'pages.evaluators.anomalies',
                     'visualization':'Distribuição/tabela agregada'},
        'years':annual,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    novos={ano:atualizar_dashboard(dashes[ano],annual[i],annual,hist,gerado)
           for i,ano in enumerate(ANOS)} if not somente_modulo else {}
    for ano,d in novos.items():
        if d['meta']['year']!=ano or d['pages']['evaluators']['divergence_clusters']['indicator_id']!='IND-028':
            raise ValueError(f'{ano}: IND-028 não preservado')
        for schema in (raiz/'04_resultados_analises.schema.json',raiz/'docs/04_resultados_analises.schema.json'):
            if schema.is_file():
                try: import jsonschema
                except ImportError:break
                jsonschema.validate(d,ler_json(schema));break
    linhas=[]
    for periodo in (*annual,hist):
        tag=str(periodo.get('ano','2019-2025'))
        for uf,r in [('BR',periodo['brasil']),*((v['uf'],v) for v in periodo['ufs'])]:
            row={'indicador_id':IND,'periodo':tag,'uf':uf,
                 'abrangencia':'BR' if uf=='BR' else 'UF',
                 'situacao':r['situacao'],'n_pop_evaluator':r['n_pop_evaluator'],
                 'n_completos':r['n_pop_evaluator_comp_completa'],
                 'n_amostra_ml_evaluator':r['n_amostra_ml_evaluator'],
                 'n_estimators':n_estimators,'contamination':'auto',
                 'limiar_escore_auto':0.5,
                 'n_sinalizados_amostra':r.get('n_sinalizados_auto'),
                 'percentual_sinalizados_amostra':r.get('percentual_sinalizados_auto'),
                 'sinalizacao_suprimida':r.get('sinalizacao_suprimida'),
                 'score_p05':(r.get('score_summary') or {}).get('p05'),
                 'score_p50':(r.get('score_summary') or {}).get('p50'),
                 'score_p95':(r.get('score_summary') or {}).get('p95'),
                 'metodo':METODO}
            for key,val in zip(ATRIBUTOS,(r.get('media_atributos_amostra') or {}).values()):
                row[f'media_{key}']=val
            # Colunas fixas também quando o recorte não é ajustável.
            for key in ATRIBUTOS:
                row.setdefault(f'media_{key}',None)
            linhas.append(row)
    json.dumps(modulo,ensure_ascii=False,allow_nan=False)
    with tempfile.TemporaryDirectory(prefix='.ind029_stage_',dir=out) as tmp:
        st=Path(tmp);srcj=st/f'{ARQUIVO}.json';srcc=st/f'{ARQUIVO}.csv'
        gravar_json(srcj,modulo)
        with srcc.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
            writer.writeheader();writer.writerows(linhas)
        gravacoes=[(srcj,destinos[0]),(srcc,destinos[1])]
        for ano,d in novos.items():
            p=st/f'dashboard_enem_{ano}.json';gravar_json(p,d)
            gravacoes.append((p,j/p.name))
        for ano in ANOS:
            if not somente_modulo and hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()!=hashes[ano]:
                raise RuntimeError(f'Dashboard {ano} alterado durante processamento; nada foi escrito')
        for src,dst in gravacoes:
            dst.parent.mkdir(parents=True,exist_ok=True)
            os.replace(src,dst)
    n_ok=sum(recorte(p,u)['situacao']=='ok' for p in (*annual,hist) for u in GRUPOS)
    print(f'IND-029 concluído: {len(linhas)} recortes, {n_ok} com sinalização divulgável.',flush=True)
    print('Arquivos:',*map(str,destinos),sep='\n  ')
    return modulo


def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path.cwd())
    ap.add_argument('--bloco',type=int,default=100_000)
    ap.add_argument('--n-estimators',type=int,default=N_ESTIMATORS)
    ap.add_argument('--somente-modulo',action='store_true',help='não modifica dashboards')
    ap.add_argument('--sobrescrever',action='store_true')
    args=ap.parse_args()
    executar(args.base.resolve(),args.bloco,args.n_estimators,
             somente_modulo=args.somente_modulo,sobrescrever=args.sobrescrever)


if __name__=='__main__':
    main()
