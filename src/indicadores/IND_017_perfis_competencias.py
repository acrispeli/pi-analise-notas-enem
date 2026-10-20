#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-017 — Perfis de competências (K-Means), ENEM 2019–2025.

Catálogo: ML / competencies / Perfis de competências / P1.
Pergunta: Existem grupos naturais de desempenho?
Variáveis: C1..C5 ou PCs; população de ajuste: AMOSTRA_ML.
Método: StandardScaler -> (PCA opcional) -> K-Means.
Visual: Perfis/centroides; JSON: pages.competencies.clusters.

Escolha metodológica explícita, NÃO determinada pelo catálogo:
    k-alvo=4, cinco competências em z-score (escala, média e desvio DD0 do
    IND-014), KMeans sklearn com n_init=5, amostra determinística sem reposição
    de até 4.000 redações por BR/UF/ano e BR/UF/histórico. Não realiza PCA
    opcional para preservar interpretação direta de C1..C5. A seleção é feita
    pela menor chave pseudoaleatória SplitMix64 derivada de (ano, linha), sem
    armazenar milhões de registros em memória. O histórico é reamostrado sobre
    TODAS as participações, e seu modelo é ajustado separadamente.

Nenhum dado individual, identificador ou membro da amostra é exportado.
Os tamanhos apresentados são TAMANHOS DA AMOSTRA, não da POP_VALID.
IND-018 atribuirá, separadamente, os centros a toda a POP_VALID; o IND-019
avaliará o agrupamento (Silhouette, Davies–Bouldin, Calinski–Harabasz).
A convergência é exigida (tol=0) e, se necessário, concluída por passos
de Lloyd, garantindo centros iguais às médias de suas atribuições finais.
Se um cluster da amostra tiver menos de 30 observações, o método refaz K-Means
com k menor até 2; se mesmo k=2 produzir contagem pequena, a exportação
inteira é bloqueada. 'k efetivo' é documentado por recorte.

Pré-requisitos: IND-014, IND-015, IND-016 e dashboards dos sete anos completos.
NÃO executar simultaneamente ao IND-016 (os dashboards são cumulativos).

Na raiz do repositório:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_017_perfis_competencias.py

Arquivos produzidos:
  outputs/indicadores/IND_017_perfis_competencias.csv
  outputs/json/IND_017_perfis_competencias.json
  outputs/json/dashboard_enem_{2019..2025}.json

Os perfis P1..Pk são ordenados pela SOMA crescente dos cinco centros em pontos
ENEM, apenas como convenção exploratória; rótulos de UFs/anos diferentes NÃO
representam automaticamente os mesmos grupos nem níveis oficiais do ENEM.
Status de publicação: draft; revisão acadêmica e privacidade pendentes.
"""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
LABELS = tuple(f'C{i}' for i in range(1, 6))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COMP)
IND = 'IND-017'
NOME = 'Perfis de competências'
METODO = 'kmeans_cinco_competencias_padronizadas_amostra_prioridade_deterministica'
VERSAO = ('2.16.1-ind001-ind002-ind003-ind004-ind005-ind006-ind007-'
          'ind008-ind009-ind010-ind011-ind012-ind013-ind014-ind015-ind016-ind017')
K_PADRAO = 4
MAX_AMOSTRA = 4000
SEMENTE = 17017
MIN_CLUSTER = 30
BLOCO = 100_000
N_INIT = 5
MAX_ITER = 500
TOL_KMEANS = 0.0  # Não terminar antes de estabilizar as atribuições.
EPS = 1e-7
DEFINICAO = ('Agrupamento exploratório K-Means de C1–C5 em unidades de z-score, '
            'usando média e escala DD0 dos modelos IND-014 por ano/UF/BR/histórico. '
            'Amostra determinística sem reposição, selecionada independentemente '
            'por recorte; sem exportar pontos individuais.')
RESSALVAS = ('k=4 é hipótese exploratória a validar no IND-019, não número de perfis '
            'definido pelo ENEM. Centros não são notas oficiais nem implicam causalidade. '
            'P1..P4 ordenados por soma de centros locais: NÃO comparar rótulos '
            'automaticamente entre períodos/UFs. Percentuais referem-se apenas '
            'à amostra; proporções POP_VALID cabem ao IND-018. '
            'SG_UF_PROVA é local de prova, não residência. '
            'Amostra histórica conta participações, não pessoas únicas. '
            'Indicador interno draft; revisão acadêmica e privacidade pendentes.')


def fonte(ano: int, raiz: Path) -> Path:
    nome = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / nome


def ler_json(p: Path) -> dict:
    if not p.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {p}')
    with p.open('r', encoding='utf-8') as f:
        return json.load(f)


def mapa_ufs(d: dict, contexto: str) -> dict[str, dict]:
    grupos = d.get('ufs', [])
    if len(grupos) != 27 or {x.get('uf') for x in grupos} != set(UFS):
        raise ValueError(f'{contexto}: 27 UFs ausentes/duplicadas')
    return {x['uf']: x for x in grupos}


def validar_modelo(ref: dict, load: dict, contexto: str):
    if ref.get('n_validas') != load.get('n_validas') or ref.get('n_validas', 0) < 30:
        raise ValueError(f'{contexto}: POP_VALID IND-014/015 incompatível')
    m = ref.get('modelo', {})
    try:
        mu = np.asarray(m['mean'], dtype=np.float64)
        sd = np.asarray(m['scale'], dtype=np.float64)
        v = np.asarray(m['components'], dtype=np.float64)
        vl = np.asarray(load['loadings'], dtype=np.float64)
        lam = np.asarray([p['autovalor_padronizado'] for p in ref['componentes']], dtype=np.float64)
        r = np.asarray(m['pearson_original'], dtype=np.float64)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f'{contexto}: modelo PCA ilegível') from exc
    if any(a.shape != shape for a, shape in ((mu,(5,)),(sd,(5,)),(v,(5,5)),(vl,(5,5)),(lam,(5,)),(r,(5,5)))):
        raise ValueError(f'{contexto}: dimensões incompatíveis')
    if not all(np.isfinite(a).all() for a in (mu,sd,v,vl,lam,r)) or np.any(sd <= 0):
        raise ValueError(f'{contexto}: escalas e coeficientes inválidos')
    if m.get('competencias') != list(LABELS) or m.get('variaveis') != list(COMP):
        raise ValueError(f'{contexto}: ordem C1..C5 divergente')
    if not np.allclose(v, vl, rtol=0, atol=3e-8) or not np.allclose(v@v.T,np.eye(5),rtol=0,atol=5e-8):
        raise ValueError(f'{contexto}: IND-014 e IND-015 não coincidem')
    if not np.allclose(v.T@np.diag(lam)@v,r,rtol=0,atol=3e-7):
        raise ValueError(f'{contexto}: autovalores e Pearson divergentes')
    if ref.get('n_somas_divergentes') != load.get('n_somas_divergentes') or abs(
        ref.get('delta_soma_competencias_menos_nota_redacao',0) -
        load.get('delta_soma_competencias_menos_nota_redacao',0)) > EPS:
        raise ValueError(f'{contexto}: controle SC/2023 divergente')
    return mu, sd


def carregar_pre_requisitos(raiz: Path):
    pasta = raiz/'outputs'/'json'
    p14 = ler_json(pasta/'IND_014_variancia_explicada_pca.json')
    p15 = ler_json(pasta/'IND_015_loadings_pca.json')
    p16 = ler_json(pasta/'IND_016_mapa_pc1_pc2.json')
    if [p.get('indicator',{}).get('id') for p in (p14,p15,p16)] != ['IND-014','IND-015','IND-016']:
        raise ValueError('Execute IND-014, IND-015 e IND-016 antes do IND-017')
    if any(p.get('meta',{}).get('data_status') != 'draft' for p in (p14,p15,p16)):
        raise ValueError('Indicadores anteriores devem permanecer em draft')
    if any(sorted(d['ano'] for d in p.get('years',[])) != list(ANOS) or
           p.get('historical',{}).get('periodo') != '2019-2025'
           for p in (p14,p15,p16)):
        raise ValueError('IND-014..016: períodos incompletos')
    ano14 = {d['ano']:d for d in p14['years']}
    ano15 = {d['ano']:d for d in p15['years']}
    ano16 = {d['ano']:d for d in p16['years']}
    refs = {}
    for chave in (*ANOS,'historical'):
        a = p14['historical'] if chave=='historical' else ano14[chave]
        b = p15['historical'] if chave=='historical' else ano15[chave]
        c = p16['historical'] if chave=='historical' else ano16[chave]
        u14 = mapa_ufs(a,str(chave)); u15 = mapa_ufs(b,str(chave)); u16 = mapa_ufs(c,str(chave))
        ref = {}
        for uf in ('BR',*UFS):
            g14 = a['brasil'] if uf=='BR' else u14[uf]
            g15 = b['brasil'] if uf=='BR' else u15[uf]
            g16 = c['brasil'] if uf=='BR' else u16[uf]
            mu,sd = validar_modelo(g14,g15,f'{chave}/{uf}')
            if g16.get('n_validas') != g14['n_validas'] or not g16.get('sem_pontos_individuais'):
                raise ValueError(f'{chave}/{uf}: IND-016 diverge ou exporta pontos individuais')
            ref[uf] = {'n':g14['n_validas'], 'total_registros':g14.get('total_registros'), 'mu':mu, 'sd':sd,
                       'div':g14['n_somas_divergentes'],
                       'delta':g14['delta_soma_competencias_menos_nota_redacao']}
        refs[chave] = ref
    dashboards = {}
    for ano in ANOS:
        d=ler_json(pasta/f'dashboard_enem_{ano}.json')
        if d.get('meta',{}).get('year') != ano or d['meta'].get('data_status') != 'draft':
            raise ValueError(f'{ano}: dashboard não finalizado/draft')
        if d.get('quality',{}).get('ind016_validation',{}).get('status') != 'ok' or \
           d.get('pages',{}).get('competencies',{}).get('pca',{}).get('scatter',{}).get('indicator_id')!='IND-016':
            raise ValueError(f'{ano}: finalize o IND-016 antes de executar o IND-017')
        if 'clusters' in d['pages']['competencies'] or 'ind017' in d.get('quality',{}):
            raise ValueError(f'{ano}: IND-017 já registrado; não sobrescrever')
        if d['pages']['overview']['kpis']['valid_essays'] != refs[ano]['BR']['n']:
            raise ValueError(f'{ano}: POP_VALID do dashboard diverge do IND-014')
        dashboards[ano]=d
    return p14,p16,refs,dashboards


def splitmix64(ids: np.ndarray, ano: int, seed: int) -> np.ndarray:
    """Chave determinística para cada linha da fonte; independe do chunksize."""
    mask=np.uint64(0xFFFFFFFFFFFFFFFF)
    with np.errstate(over='ignore'):
        x=(ids.astype(np.uint64) ^ (np.uint64(ano)<<np.uint64(32)) ^ np.uint64(seed)) & mask
        x=(x+np.uint64(0x9E3779B97F4A7C15)) & mask
        z=x.copy()
        z=((z^(z>>np.uint64(30)))*np.uint64(0xBF58476D1CE4E5B9)) & mask
        z=((z^(z>>np.uint64(27)))*np.uint64(0x94D049BB133111EB)) & mask
        return z^(z>>np.uint64(31))


class Amostra:
    """Bottom-k estável com uma única matriz de (prioridade, notas C1..C5)."""
    __slots__=('n','prior','x','cap')
    def __init__(self, cap: int):
        self.n=0
        self.prior=np.empty(0,dtype=np.uint64)
        self.x=np.empty((0,5),dtype=np.float64)
        self.cap=cap
    def adicionar(self, notas: np.ndarray, prioridades: np.ndarray):
        if notas.shape != (len(prioridades),5) or not np.isfinite(notas).all():
            raise ValueError('Amostra: notas inválidas')
        self.n += len(notas)
        if not len(notas):return
        # Pré-seleção vetorizada no bloco reduz custo de memória.
        if len(prioridades)>self.cap:
            idx=np.argpartition(prioridades, self.cap-1)[:self.cap]
            prioridades=prioridades[idx]
            notas=notas[idx]
        keys=np.concatenate((self.prior,prioridades))
        points=np.concatenate((self.x,notas),axis=0)
        if len(keys)>self.cap:
            idx=np.argpartition(keys,self.cap-1)[:self.cap]
            keys,points=keys[idx],points[idx]
        ordenacao=np.argsort(keys,kind='stable')
        self.prior=keys[ordenacao]
        self.x=points[ordenacao]



def reconciliar_centroides(z: np.ndarray, rotulos: np.ndarray, k: int,
                            max_refinamentos: int = 1000):
    """Garante, por passos de Lloyd, que centros == médias dos seus membros.

    Mesmo com tol=0, se sklearn encerrar ao atingir max_iter, pode fazer
    uma atribuição final sem recalcular os centros (comportamento documentado
    pelo sklearn). A reconciliação completa essa convergência; nunca ignora a
    divergência nem relaxa os controles. Retorna None se surgir grupo vazio.
    """
    labels = np.asarray(rotulos, dtype=np.int64).copy()
    n = len(z)
    for passo in range(max_refinamentos + 1):
        cont = np.bincount(labels, minlength=k)
        if len(cont) != k or np.any(cont == 0):
            return None  # O chamador tentará k menor (privacidade/estabilidade).
        centros = np.vstack([z[labels == j].mean(axis=0) for j in range(k)])
        if not np.isfinite(centros).all():
            raise ValueError('K-Means: médias dos grupos não finitas')
        # Distâncias quadráticas euclidianas, idênticas ao critério K-Means.
        dist = np.sum((z[:, None, :] - centros[None, :, :]) ** 2, axis=2)
        proximos = np.argmin(dist, axis=1)
        if np.array_equal(proximos, labels):
            if int(cont.sum()) != n:
                raise ValueError('K-Means: atribuições não fecham a amostra')
            return centros, labels, cont, passo
        labels = proximos
    raise ValueError(f'K-Means: atribuições não estabilizaram após {max_refinamentos} refinamentos')


def ajustar_perfis(amostra: Amostra, ref: dict, contexto: str, k:int,
                   seed:int, min_cluster:int=MIN_CLUSTER) -> dict:
    """Ajusta K-Means e protege todos os clusters antes de qualquer exportação."""
    if amostra.n != ref['n']:
        raise ValueError(f'{contexto}: N amostrado {amostra.n} diverge do IND-014 {ref["n"]}')
    x=amostra.x
    n=len(x)
    n_unicos=len(np.unique(x,axis=0))
    if n < 2*min_cluster or n_unicos < 2:
        raise ValueError(f'{contexto}: amostra insuficiente para pelo menos dois grupos de N≥{min_cluster}')
    z=(x-ref['mu'])/ref['sd']
    if not np.isfinite(z).all():
        raise ValueError(f'{contexto}: dados padronizados inválidos')
    # Reprodutibilidade para o mesmo sample e semente (ordem determinística).
    k_alvo=k
    modelo=None
    labels=None
    tamanhos=None
    for k_teste in range(k_alvo,1,-1):
        if n < k_teste*min_cluster or n_unicos < k_teste:
            continue
        tentativa=KMeans(n_clusters=k_teste, init='k-means++', n_init=N_INIT,
                         max_iter=MAX_ITER, random_state=seed,
                         algorithm='lloyd', tol=TOL_KMEANS)
        rotulos=tentativa.fit_predict(z)
        # Auditoria independente do resultado que o sklearn efetivamente produziu.
        centro_original=np.asarray(tentativa.cluster_centers_,dtype=np.float64)
        inercia_original=float(np.sum((z-centro_original[rotulos])**2))
        if not np.isclose(inercia_original, tentativa.inertia_, atol=1e-6, rtol=1e-9):
            raise ValueError(f'{contexto}: inércia original do sklearn divergente')
        refinado=reconciliar_centroides(z,rotulos,k_teste)
        if refinado is None:
            continue  # Grupo vazio na reconciliação: experimentar k menor.
        c_teste,r_teste,cont,passos=refinado
        if np.min(cont)<min_cluster:
            continue  # Proteger clusters também APÓS a convergência final.
        inercia_teste=float(np.sum((z-c_teste[r_teste])**2))
        if inercia_teste>inercia_original+max(1e-6,1e-9*inercia_original):
            raise ValueError(f'{contexto}: refinamento elevou a inércia')
        modelo,labels,tamanhos=tentativa,r_teste,cont
        centers=c_teste
        inertia=inercia_teste
        iteracoes_refinamento=passos
        k=k_teste
        break
    if modelo is None:
        raise ValueError(f'{contexto}: nem k=2 produz grupos com ≥{min_cluster} '
                         'observações na amostra; nada será exportado')
    # Garantia exata: centro final corresponde às notas efetivamente atribuídas.
    medias=np.vstack([z[labels==j].mean(axis=0) for j in range(k)])
    if not np.allclose(centers,medias,atol=5e-8,rtol=0):
        raise ValueError(f'{contexto}: centróides finais incorretos')
    if abs(sum(tamanhos)-n)>0:
        raise ValueError(f'{contexto}: tamanhos dos clusters não fecham')
    centros_pontos=centers*ref['sd']+ref['mu']
    somas=centros_pontos.sum(axis=1)
    # Para desempate, usa vetor inteiro da média em pontos.
    order=sorted(range(k),key=lambda j:(float(somas[j]),*map(float,centros_pontos[j])))
    clusters=[]
    for pos, j in enumerate(order,1):
        clusters.append({'cluster_id':f'P{pos}', 'rotulo':f'Perfil {pos}',
                         'n_amostra':int(tamanhos[j]),
                         'percentual_amostra':round(float(100*tamanhos[j]/n),6),
                         'centro_padronizado':[round(float(v),9) for v in centers[j]],
                         'centro_pontos':[round(float(v),6) for v in centros_pontos[j]],
                         'soma_centros_pontos':round(float(somas[j]),6),
                         'centro_competencias':[
                             {'competencia':f'C{ci+1}',
                              'nota_media_centro':round(float(centros_pontos[j,ci]),6),
                              'z_centro':round(float(centers[j,ci]),9)}
                             for ci in range(5)]})
    if sum(c['n_amostra'] for c in clusters)!=n or abs(sum(c['percentual_amostra'] for c in clusters)-100)>1e-4:
        raise ValueError(f'{contexto}: a amostra não fecha por clusters')
    return {'n_validas':int(ref['n']), 'n_amostra_ml':int(n),
            'fracao_amostrada':round(float(n/ref['n']),10),
            'k':int(k), 'k_alvo':int(k_alvo), 'k_reduzido_por_privacidade':bool(k<k_alvo), 'max_amostra_por_grupo':int(amostra.cap), 'modelo_algoritmo':'sklearn.cluster.KMeans',
            'recurso_modelo':'5_competencias_padronizadas',
            'n_init':N_INIT, 'max_iter':MAX_ITER,
            'tol_kmeans':TOL_KMEANS,
            'iteracoes_refinamento':int(iteracoes_refinamento),
            'iteracoes_executadas':int(modelo.n_iter_),
            'inercia_amostra':round(inertia,8),
            'inercia_por_redacao_amostral':round(inertia/n,8),
            'padronizacao':{'mean':[round(float(v),10) for v in ref['mu']],
                           'scale':[round(float(v),10) for v in ref['sd']],
                           'ddof':0,'source':'IND-014'},
            'clusters':clusters,
            'amostragem':'bottom_k_deterministico_sem_reposicao',
            'semente_base':seed,'sem_dados_individuais':True,
            'limiar_minimo_cluster_amostra':min_cluster,
            'percentuais_referem_se_a':'AMOSTRA_ML_nao_POP_VALID',
            'n_somas_divergentes':int(ref['div']),
            'delta_soma_competencias_menos_nota_redacao':float(ref['delta'])}


def processar_fontes(raiz: Path, refs: dict, k:int,cap:int,seed:int,bloco:int):
    hist={uf:Amostra(cap) for uf in ('BR',*UFS)}
    anual=[]
    for ano in ANOS:
        ano_ac={uf:Amostra(cap) for uf in ('BR',*UFS)}
        ref=refs[ano]
        arq=fonte(ano,raiz)
        if not arq.is_file():raise FileNotFoundError(f'Microdado ausente: {arq}')
        qa={key:0 for key in ('total_registros','validas','status1_sem_nota',
            'status1_nota_invalida','validas_sem_uf','validas_uf_desconhecida',
            'validas_competencias_incompletas','n_somas_divergentes')}
        delta_total=0.0
        div_ufs={u:[0,0.0] for u in UFS}
        print(f'IND-017 | {ano}: extraindo amostras determinísticas...',flush=True)
        for bloco_df in pd.read_csv(arq,sep=';',usecols=list(COLUNAS),dtype=str,
                                    keep_default_na=False,na_filter=False,
                                    encoding='utf-8-sig',encoding_errors='replace',
                                    on_bad_lines='error',chunksize=bloco):
            offset=qa['total_registros']
            qa['total_registros']+=len(bloco_df)
            uf=bloco_df['SG_UF_PROVA'].str.strip().str.upper()
            status=bloco_df['TP_STATUS_REDACAO'].str.strip().eq('1')
            str_nota=bloco_df['NU_NOTA_REDACAO'].str.strip()
            nota=pd.to_numeric(str_nota.str.replace(',','.',regex=False),errors='coerce')
            valido=status & nota.notna() & nota.between(0,1000)
            qa['validas']+=int(valido.sum())
            qa['status1_sem_nota']+=int((status & str_nota.eq('')).sum())
            qa['status1_nota_invalida']+=int((status & str_nota.ne('') & ~nota.between(0,1000)).sum())
            qa['validas_sem_uf']+=int((valido & uf.eq('')).sum())
            qa['validas_uf_desconhecida']+=int((valido & uf.ne('') & ~uf.isin(UFS)).sum())
            if not bool(valido.any()):continue
            raw=bloco_df.loc[valido,list(COMP)].apply(lambda c:c.str.strip())
            dados=raw.apply(lambda c:pd.to_numeric(c.str.replace(',','.',regex=False),errors='coerce'))
            comp_ok=dados.notna().all(axis=1) & dados.ge(0).all(axis=1) & dados.le(200).all(axis=1)
            qa['validas_competencias_incompletas']+=int((~comp_ok).sum())
            if not bool(comp_ok.any()):continue
            x=dados.loc[comp_ok].to_numpy(dtype=np.float64)
            siglas=uf.loc[valido].loc[comp_ok].to_numpy(dtype=str)
            notas=nota.loc[valido].loc[comp_ok].to_numpy(dtype=np.float64)
            diferenca=x.sum(axis=1)-notas
            bad=np.abs(diferenca)>1e-6
            qa['n_somas_divergentes']+=int(bad.sum())
            delta_total+=float(diferenca[bad].sum())
            # Índices originais da fonte, não índices redefinidos por bloco.
            rowids=offset + np.flatnonzero(valido.to_numpy())[comp_ok.to_numpy()]
            chaves=splitmix64(rowids,ano,seed)
            ano_ac['BR'].adicionar(x,chaves)
            hist['BR'].adicionar(x,chaves)
            for u in np.unique(siglas):
                if u not in ref:continue  # rejeição pelo QA antes de salvar
                ix=siglas==u
                div_ufs[u][0]+=int(np.count_nonzero(bad[ix]))
                div_ufs[u][1]+=float(diferenca[ix & bad].sum())
                ano_ac[u].adicionar(x[ix],chaves[ix])
                hist[u].adicionar(x[ix],chaves[ix])
        if any(qa[key] for key in ('status1_sem_nota','status1_nota_invalida',
            'validas_sem_uf','validas_uf_desconhecida','validas_competencias_incompletas')):
            raise ValueError(f'{ano}: microdados com notas/UF/competências inválidas: {qa}')
        if qa['validas']!=ref['BR']['n']:
            raise ValueError(f'{ano}: POP_VALID diverge do IND-014')
        if ref['BR']['total_registros'] is not None and qa['total_registros']!=ref['BR']['total_registros']:
            raise ValueError(f'{ano}: POP_ALL diverge do IND-014')
        if qa['n_somas_divergentes']!=ref['BR']['div'] or abs(delta_total-ref['BR']['delta'])>1e-5:
            raise ValueError(f'{ano}: divergência SC/2023 não preservada no Brasil')
        for uf_val in UFS:
            if (div_ufs[uf_val][0] != ref[uf_val]['div'] or
                abs(div_ufs[uf_val][1]-ref[uf_val]['delta'])>1e-5):
                raise ValueError(f'{ano}/{uf_val}: divergência de soma por UF não preservada')
        ano_br=ajustar_perfis(ano_ac['BR'],ref['BR'],f'{ano}/BR',k,seed)
        uf_items=[{'uf':u,**ajustar_perfis(ano_ac[u],ref[u],f'{ano}/{u}',k,seed)} for u in UFS]
        if sum(g['n_validas'] for g in uf_items)!=ano_br['n_validas']:
            raise ValueError(f'{ano}: soma das UFs difere do Brasil')
        anual.append({'ano':ano,'arquivo_fonte':arq.name,'brasil':ano_br,
                      'ufs':uf_items,
                      'qualidade':{'status':'ok','total_registros':qa['total_registros'],
                                  'n_validas':qa['validas'],
                                  'n_somas_divergentes':qa['n_somas_divergentes'],
                                  'delta_soma_competencias_menos_nota_redacao':delta_total}})
        print(f'  N Brasil={ano_br["n_validas"]:,} | amostra={ano_br["n_amostra_ml"]:,} '
              f'| k={k}',flush=True)
    hist_br=ajustar_perfis(hist['BR'],refs['historical']['BR'],'2019-2025/BR',k,seed)
    hist_ufs=[{'uf':u,**ajustar_perfis(hist[u],refs['historical'][u],f'2019-2025/{u}',k,seed)} for u in UFS]
    if sum(g['n_validas'] for g in hist_ufs)!=hist_br['n_validas']:
        raise ValueError('Histórico: soma das UFs diverge Brasil')
    historico={'periodo':'2019-2025','brasil':hist_br,'ufs':hist_ufs,
               'qualidade':{'status':'ok','n_validas':hist_br['n_validas'],
                            'ajuste_proprio_historico':True}}
    return anual,historico


def linhas_csv(anos:list[dict],hist:dict):
    linhas=[]
    for periodo in [*anos,hist]:
        p=str(periodo.get('ano','2019-2025'))
        for uf,g in [('BR',periodo['brasil']),*[(i['uf'],i) for i in periodo['ufs']]]:
            for cluster in g['clusters']:
                linha={'indicador_id':IND,'periodo':p,
                    'abrangencia':'BR' if uf=='BR' else 'UF','uf':uf,
                    'cluster_id':cluster['cluster_id'],
                    'n_validas':g['n_validas'],'n_amostra_ml':g['n_amostra_ml'],
                    'n_cluster_amostra':cluster['n_amostra'],
                    'percentual_cluster_amostra':cluster['percentual_amostra'],
                    'soma_centros_pontos':cluster['soma_centros_pontos'],
                    'inercia_por_redacao_amostral':g['inercia_por_redacao_amostral'],
                    'k':g['k'],'limiar_minimo_cluster_amostra':MIN_CLUSTER,
                    'method':METODO}
                for j in range(5):
                    linha[f'centro_C{j+1}_pontos']=cluster['centro_pontos'][j]
                    linha[f'centro_C{j+1}_padronizado']=cluster['centro_padronizado'][j]
                linhas.append(linha)
    esperado=sum(len(g['clusters']) for d in [*anos,hist] for g in [d['brasil'],*d['ufs']])
    if len(linhas)!=esperado:
        raise ValueError('CSV não corresponde aos clusters de cada recorte')
    return linhas


def resumo_grupo(g:dict):
    return {key:deepcopy(g[key]) for key in ('n_validas','n_amostra_ml','k','k_alvo','k_reduzido_por_privacidade','clusters',
        'inercia_por_redacao_amostral','amostragem','limiar_minimo_cluster_amostra',
        'percentuais_referem_se_a','sem_dados_individuais')}


def atualizar_dashboard(ano:dict,anual:list[dict],hist:dict,dash:dict,gerado:str):
    out=deepcopy(dash)
    a=ano['ano']
    out['pages']['competencies']['clusters']={
        'indicator_id':IND,'method':'K-Means','features':list(LABELS),
        'population':'AMOSTRA_ML','source_population':'POP_VALID',
        'n':ano['brasil']['n_validas'],
        'brasil':resumo_grupo(ano['brasil']),
        'by_uf':[{'uf':g['uf'],**resumo_grupo(g)} for g in ano['ufs']],
        'note':RESSALVAS}
    out['pages']['temporal']['ind017']={
        'indicator_id':IND,
        'national_by_year':[{'year':d['ano'],**resumo_grupo(d['brasil'])} for d in anual],
        'period_total':resumo_grupo(hist['brasil']),
        'period_by_uf':[{'uf':g['uf'],**resumo_grupo(g)} for g in hist['ufs']],
        'historical_note':'Modelo histórico treinado de modo independente nos dados históricos; sem média de centroides anuais.'}
    out['pages']['methodology']['ind017']={
        'definition':DEFINICAO,'method':METODO,'source_file':ano['arquivo_fonte'],
        'catalog_population':'AMOSTRA_ML','feature_scaler':'IND-014 por recorte',
        'source_indicators':['IND-014','IND-015','IND-016'],
        'k_target':ano['brasil']['k_alvo'],'k_effective_by_group':'2..k_target conforme tamanho amostral',
        'n_clusters_national':ano['brasil']['k'],'n_init':N_INIT,
        'tol_kmeans':TOL_KMEANS,
        'max_sample_per_group':ano['brasil']['max_amostra_por_grupo'],
        'sample_selection':'bottom-k hash determinístico sem reposição',
        'cluster_minimum_sample':MIN_CLUSTER,
        'out_of_scope':'Não calcula proporções de POP_VALID (IND-018) nem índices de qualidade (IND-019)',
        'limitations':RESSALVAS}
    out['quality']['ind017_validation']={
        'status':'ok','source_indicator':'IND-014',
        'k':ano['brasil']['k'],
        'k_alvo':ano['brasil']['k_alvo'],
        'k_reduzido_brasil':ano['brasil']['k_reduzido_por_privacidade'],
        'n_amostra_ml_brasil':ano['brasil']['n_amostra_ml'],
        'n_validas_brasil':ano['brasil']['n_validas'],
        'soma_27_ufs_igual_brasil':True,
        'clusters_amostrais_min_n_30':True,
        'nenhum_registro_individual_exportado':True,
        'historico_ajustado_separadamente':True,
        'n_somas_divergentes':ano['brasil']['n_somas_divergentes'],
        'delta_soma_competencias_menos_nota_redacao':ano['brasil']['delta_soma_competencias_menos_nota_redacao'],
        'model_quality_indices':'IND-019 pendente',
        'method':METODO}
    out['meta']['analysis_version']=VERSAO
    out['meta']['generated_at']=gerado
    out['meta']['data_status']='draft'
    aviso=('IND-017: perfis K-Means treinados em amostras determinísticas; '
           'proporções amostrais NÃO equivalem às participações na POP_VALID; '
           'k-alvo escolhido (podendo ser reduzido para proteger células) requer validação metodológica pelo IND-019; não publicar antes de revisão.')
    if aviso not in out['meta'].setdefault('warnings',[]):out['meta']['warnings'].append(aviso)
    return out


def validar_schema(doc:dict,raiz:Path):
    for campo in ('meta','filters','quality','pages'):
        if campo not in doc:raise ValueError(f'Dashboard sem campo {campo}')
    candidatos=[raiz/'docs'/'04_resultados_analises.schema.json',
        raiz/'docs'/'metodologia'/'04_resultados_analises.schema.json',
        raiz/'04_resultados_analises.schema.json']
    schema=next((p for p in candidatos if p.exists()),None)
    if schema is None:return 'estrutura mínima; schema local ausente'
    import jsonschema
    jsonschema.validate(doc,ler_json(schema))
    return 'JSON Schema v1.0.0'


def gravar_json(p:Path,d:dict):
    with p.open('w',encoding='utf-8') as f:
        json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n')


def gravar_csv(p:Path,rows:list[dict]):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';')
        writer.writeheader();writer.writerows(rows)


def executar(raiz:Path, k:int=K_PADRAO,cap:int=MAX_AMOSTRA,
             seed:int=SEMENTE,bloco:int=BLOCO):
    if not isinstance(k,int) or k<2 or k>8:
        raise ValueError('k deve estar entre 2 e 8')
    if not isinstance(cap,int) or cap<2*MIN_CLUSTER or cap>50_000:
        raise ValueError(f'max_amostra deve ser ≥ {2*MIN_CLUSTER} e ≤ 50.000')
    if not isinstance(seed,int) or not 0<=seed<2**32 or bloco<1:
        raise ValueError('Semente deve ser uint32 e bloco positivo')
    p14,p16,refs,dashes=carregar_pre_requisitos(raiz)
    anos,hist=processar_fontes(raiz,refs,k,cap,seed,bloco)
    linhas=linhas_csv(anos,hist)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    atualizados={d['ano']:atualizar_dashboard(d,anos,hist,dashes[d['ano']],gerado) for d in anos}
    schemas={validar_schema(d,raiz) for d in atualizados.values()}
    modulo={'meta':{
        'indicator_id':IND,'module_schema_version':'ind017-module-1.0.0',
        'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
        'generated_at':gerado,'data_status':'draft',
        'source_files':{str(d['ano']):d['arquivo_fonte'] for d in anos},
        'population_definition':DEFINICAO,'geographic_dimension':'SG_UF_PROVA',
        'method':METODO,'max_sample_per_group':cap,'k':k,
        'tol_kmeans':TOL_KMEANS,
        'random_seed':seed,'k_choice':'k_alvo_fixo_hipotese_exploratoria_com_reducao_para_min30',
        'source_indicators':['IND-014','IND-015','IND-016'],
        'source_discrepancies':p14['meta']['source_discrepancies'],
        'publication_status':'draft; validacao academica e privacidade pendentes',
        'notes':RESSALVAS},
        'indicator':{'id':IND,'name':NOME,'unit':'perfis',
          'dashboard_json_path':'pages.competencies.clusters',
          'output_type':'clusters','visualization':'Perfis/centroides'},
        'years':anos,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    json.dumps(modulo,allow_nan=False)
    out=raiz/'outputs';dst_json=out/'json';dst_csv=out/'indicadores'
    dst_csv.mkdir(parents=True,exist_ok=True)
    dst_json.mkdir(parents=True,exist_ok=True)
    # Todos os resultados são validados e serializados em staging ANTES de substituir qualquer arquivo.
    with tempfile.TemporaryDirectory(prefix='.ind017_stage_',dir=out) as td:
        temp=Path(td)
        gravar_csv(temp/'IND_017_perfis_competencias.csv',linhas)
        gravar_json(temp/'IND_017_perfis_competencias.json',modulo)
        for ano in ANOS:gravar_json(temp/f'dashboard_enem_{ano}.json',atualizados[ano])
        arquivos=[('IND_017_perfis_competencias.csv',dst_csv),
                  ('IND_017_perfis_competencias.json',dst_json),
                  *[(f'dashboard_enem_{ano}.json',dst_json) for ano in ANOS]]
        for nome,dest in arquivos:os.replace(temp/nome,dest/nome)
    print('\nIND-017 CONCLUÍDO')
    print(f'  CSV: {len(linhas):,} linhas de centroides, sem redações individuais')
    print(f'  k-alvo={k}; k efetivo varia entre 2 e k-alvo se necessário')
    print('  JSON: IND_017_perfis_competencias.json')
    print('  Dashboards: 2019 ... 2025 atualizados cumulativamente')
    print('  JSON Schema: '+', '.join(sorted(schemas)))
    print('  data_status=draft; IND-018 e IND-019 ainda pendentes')


def main():
    parser=argparse.ArgumentParser(description='IND-017 perfis de competências, K-Means')
    parser.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--k',type=int,default=K_PADRAO)
    parser.add_argument('--max-amostra',type=int,default=MAX_AMOSTRA)
    parser.add_argument('--semente',type=int,default=SEMENTE)
    parser.add_argument('--bloco',type=int,default=BLOCO)
    opt=parser.parse_args()
    executar(opt.raiz.resolve(),k=opt.k,cap=opt.max_amostra,seed=opt.semente,bloco=opt.bloco)


if __name__=='__main__':main()
