#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-019 — Qualidade do clustering (ENEM 2019–2025).

Catálogo: qualidade do K-Means; AMOSTRA_ML; Silhouette, Davies–Bouldin,
Calinski–Harabasz; pages.competencies.clusters.quality.

Reconstitui EXATAMENTE a amostra determinística bottom-k do IND-017 lendo os
microdados novamente; NÃO refaz nem substitui os centroides do IND-017.
Confronta suas atribuições amostrais com tamanhos, centroides e inércia já
publicados no IND-017. Calcula DB e CH sobre toda a AMOSTRA_ML; Silhouette
é estimado em até 800 elementos da própria amostra (parâmetro ajustável,
random_state explícito) para limitar custo quadrático. Quanto maior
Silhouette e CH, melhor; quanto MENOR Davies–Bouldin, melhor.

Por padrão compara também k=2..8 para os 8 recortes nacionais BR (7 anos +
histórico), com n_init=20 e seed 42 — orientação do guia metodológico ML-02.
É análise ALTERNATIVA: não altera os agrupamentos originais do IND-017/018.
Para comparar todos os 224 recortes, use --comparacao todos; para pular,
--comparacao nenhuma. Cada comparação exige k clusters com >=30 observações.

Ressalvas: IND-017 foi treinado originalmente com n_init=5 e seed=17017;
isso diverge dos parâmetros INICIAIS RECOMENDADOS pelo guia (n_init>=20,
seed=42) e deve permanecer explícito. Comparações nacionais não validam k
estadual; métricas internas não demonstram estabilidade ou interpretabilidade.
P1..Pk são locais; SG_UF_PROVA é UF da prova; amostra e indicadores draft.
Nenhum registro individual ou membro da amostra é exportado.

Executar, após IND-018 e sem outras execuções concorrentes:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_019_qualidade_clustering.py
"""
from __future__ import annotations
import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

import IND_017_perfis_competencias as I17

ANOS = I17.ANOS
UFS = I17.UFS
COMP = I17.COMP
COLUNAS = I17.COLUNAS
IND = 'IND-019'
NOME = 'Qualidade do clustering'
METODO = 'avaliacao_kmeans_amostra_ml_ind017_silhouette_db_ch'
VERSAO = '2.18.0-' + '-'.join(f'ind{i:03d}' for i in range(1,20))
BLOCO = 100_000
SIL_MAX = 800
SEED_SIL = 42
SEED_COMPARE = 42
N_INIT_COMPARE = 20
MIN_CLUSTER = 30
RESSALVAS = ('Métricas internas calculadas sobre AMOSTRA_ML reconstituída, NÃO '
    'sobre POP_VALID. Silhouette usa subamostra determinística da amostra ML, '
    'conforme silhouette_sample_n; Davies-Bouldin e Calinski-Harabasz usam toda '
    'a AMOSTRA_ML. k=4 é hipótese exploratória e não é automaticamente validado '
    'pelas métricas; avaliar estabilidade e interpretabilidade. Comparações '
    'k=2..8 empregam modelos ALTERNATIVOS com n_init=20 e seed=42, enquanto '
    'o IND-017 empregou n_init=5 e seed=17017; não substituí-los sem nova '
    'execução coordenada dos IND-017 e IND-018. Modelos e rótulos P1..Pk '
    'não equivalem entre recortes. SG_UF_PROVA é UF de realização da prova, '
    'não residência. Dados internos draft; revisão acadêmica/privacidade pendente.')


def ler_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {path}')
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def mapear_uf(p: dict, ctx: str) -> dict:
    a = p.get('ufs', [])
    if len(a) != 27 or {x.get('uf') for x in a} != set(UFS):
        raise ValueError(f'{ctx}: esperado 27 UFs distintas')
    return {x['uf']: x for x in a}


def carregar_pre_requisitos(raiz: Path):
    jdir = raiz/'outputs'/'json'
    modules = {}
    for num, nome in ((14,'variancia_explicada_pca'),
                      (17,'perfis_competencias'),(18,'tamanho_clusters')):
        m = ler_json(jdir/f'IND_{num:03d}_{nome}.json')
        if m.get('indicator',{}).get('id') != f'IND-{num:03d}' or m.get('meta',{}).get('data_status') != 'draft':
            raise ValueError(f'IND-{num:03d}: metadados inválidos/draft ausente')
        if len(m.get('years',[])) != 7 or {p.get('ano') for p in m['years']} != set(ANOS):
            raise ValueError(f'IND-{num:03d}: faltam anos')
        if m.get('historical',{}).get('periodo') != '2019-2025':
            raise ValueError(f'IND-{num:03d}: falta histórico')
        modules[num] = m
    m14,m17,m18 = modules[14],modules[17],modules[18]
    cap = int(m17['meta']['max_sample_per_group'])
    seed = int(m17['meta']['random_seed'])
    if cap < 100 or seed < 0 or m17['meta'].get('method') != I17.METODO:
        raise ValueError('IND-017: método de amostragem desconhecido')
    if not m18['meta'].get('no_sampling_for_counts') or m18['meta'].get('train_sample_reference') != 'IND-017':
        raise ValueError('IND-018: referência da amostra incorreta')
    periods = {}
    ix = {n:{p['ano']:p for p in m['years']} for n,m in modules.items()}
    for p in (*ANOS,'historical'):
        g = {n:(m['historical'] if p=='historical' else ix[n][p]) for n,m in modules.items()}
        maps = {n:mapear_uf(v,f'{p}/IND-{n:03d}') for n,v in g.items()}
        periods[p] = {}
        for uf in ('BR',*UFS):
            r14 = g[14]['brasil'] if uf=='BR' else maps[14][uf]
            r17 = g[17]['brasil'] if uf=='BR' else maps[17][uf]
            r18 = g[18]['brasil'] if uf=='BR' else maps[18][uf]
            ctx = f'{p}/{uf}'
            n = int(r14['n_validas'])
            if not (r17.get('n_validas') == r18.get('n_validas') == n):
                raise ValueError(f'{ctx}: POP_VALID diverge em IND-014/017/018')
            mu = np.asarray(r14['modelo']['mean'],dtype=np.float64)
            sd = np.asarray(r14['modelo']['scale'],dtype=np.float64)
            mu17 = np.asarray(r17['padronizacao']['mean'],dtype=np.float64)
            sd17 = np.asarray(r17['padronizacao']['scale'],dtype=np.float64)
            if (mu.shape != (5,) or sd.shape != (5,) or np.any(sd<=0) or
                not np.isfinite(mu).all() or not np.isfinite(sd).all() or
                not np.allclose(mu,mu17,atol=3e-7,rtol=0) or
                not np.allclose(sd,sd17,atol=3e-7,rtol=0)):
                raise ValueError(f'{ctx}: escalas IND-014 e IND-017 divergentes')
            k = r17.get('k')
            if (not isinstance(k,int) or not 2<=k<=8 or r18.get('k')!=k or
                len(r17.get('clusters',[])) !=k or len(r18.get('clusters',[])) !=k):
                raise ValueError(f'{ctx}: número de grupos divergente')
            ids = [f'P{i}' for i in range(1,k+1)]
            if [c['cluster_id'] for c in r17['clusters']] !=ids or [c['cluster_id'] for c in r18['clusters']] !=ids:
                raise ValueError(f'{ctx}: clusters fora de ordem')
            centros = np.array([c['centro_padronizado'] for c in r17['clusters']],dtype=np.float64)
            if centros.shape!=(k,5) or not np.isfinite(centros).all():
                raise ValueError(f'{ctx}: centroides inválidos')
            if r17.get('max_amostra_por_grupo') != cap or r17.get('semente_base') != seed:
                raise ValueError(f'{ctx}: IND-017 não usa a mesma amostra/seed')
            if (r17.get('n_amostra_ml') != min(cap,n) or
                sum(c['n_amostra'] for c in r17['clusters']) != r17['n_amostra_ml'] or
                any(c['n_amostra'] < MIN_CLUSTER for c in r17['clusters'])):
                raise ValueError(f'{ctx}: amostra IND-017 inconsistente')
            if (r18.get('n_amostra_ml_treino') != r17['n_amostra_ml'] or
                sum(c['n_redacoes'] for c in r18['clusters']) != n or
                any(a['n_amostra_treino']!=b['n_amostra'] or
                    a['n_redacoes']<MIN_CLUSTER for a,b in zip(r18['clusters'],r17['clusters']))):
                raise ValueError(f'{ctx}: IND-018 não coincide com IND-017')
            if r17.get('n_somas_divergentes')!=r14.get('n_somas_divergentes') or abs(
                float(r17.get('delta_soma_competencias_menos_nota_redacao',0))-
                float(r14.get('delta_soma_competencias_menos_nota_redacao',0))) > 1e-5:
                raise ValueError(f'{ctx}: exceção de soma de competências divergente')
            periods[p][uf] = {'n':n,'mu':mu,'sd':sd,'k':k,'centros':centros,
                'r14':r14,'r17':r17,'r18':r18,'cap':cap,'seed':seed}
        if sum(periods[p][u]['n'] for u in UFS)!=periods[p]['BR']['n']:
            raise ValueError(f'{p}: soma das UFs difere de BR')
    for uf in ('BR',*UFS):
        if sum(periods[y][uf]['n'] for y in ANOS)!=periods['historical'][uf]['n']:
            raise ValueError(f'Histórico/{uf}: soma dos anos divergente')
    dashboards={}
    for ano in ANOS:
        dash=ler_json(jdir/f'dashboard_enem_{ano}.json')
        if dash.get('meta',{}).get('year')!=ano or dash['meta'].get('data_status')!='draft':
            raise ValueError(f'Dashboard {ano}: metadados inválidos')
        q=dash.get('quality',{})
        if q.get('ind017_validation',{}).get('status')!='ok' or q.get('ind018_validation',{}).get('status')!='ok':
            raise ValueError(f'Dashboard {ano}: IND-017 ou IND-018 ausente')
        cl=dash['pages']['competencies'].get('clusters',{})
        if cl.get('indicator_id')!='IND-017' or cl.get('sizes',{}).get('indicator_id')!='IND-018':
            raise ValueError(f'Dashboard {ano}: seções de clusters incompletas')
        if 'quality' in cl or 'ind019_validation' in q or 'ind019' in dash['pages']['temporal']:
            raise ValueError(f'Dashboard {ano}: IND-019 já existente; não sobrescrever')
        if dash['pages']['overview']['kpis']['valid_essays']!=periods[ano]['BR']['n']:
            raise ValueError(f'Dashboard {ano}: N difere do IND-014')
        dashboards[ano] = dash
    return m14,m17,m18,periods,dashboards,cap,seed


def extrair_amostras(raiz:Path, periods:dict, cap:int, seed:int, bloco:int):
    anual={};historico={uf:I17.Amostra(cap) for uf in ('BR',*UFS)}
    for ano in ANOS:
        atual={uf:I17.Amostra(cap) for uf in ('BR',*UFS)}
        arq=I17.fonte(ano,raiz)
        if not arq.is_file(): raise FileNotFoundError(f'Falta microdado: {arq}')
        qa={'total_registros':0,'validas':0,'status1_sem_nota':0,
            'status1_nota_invalida':0,'validas_sem_uf':0,
            'validas_uf_desconhecida':0,'validas_competencias_incompletas':0,
            'n_somas_divergentes':0,'delta_total':0.0}
        discrep_ufs={uf:[0,0.] for uf in UFS}
        print(f'IND-019 | {ano}: reconstituindo AMOSTRA_ML...',flush=True)
        for df in pd.read_csv(arq,sep=';',usecols=list(COLUNAS),dtype=str,
                keep_default_na=False,na_filter=False,encoding='utf-8-sig',
                encoding_errors='replace',on_bad_lines='error',chunksize=bloco):
            offset=qa['total_registros'];qa['total_registros']+=len(df)
            uf=df['SG_UF_PROVA'].str.strip().str.upper()
            status=df['TP_STATUS_REDACAO'].str.strip().eq('1')
            sn=df['NU_NOTA_REDACAO'].str.strip()
            nota=pd.to_numeric(sn.str.replace(',','.',regex=False),errors='coerce')
            valid=status & nota.notna() & nota.between(0,1000)
            qa['validas']+=int(valid.sum())
            qa['status1_sem_nota']+=int((status & sn.eq('')).sum())
            qa['status1_nota_invalida']+=int((status & sn.ne('') & ~nota.between(0,1000)).sum())
            qa['validas_sem_uf']+=int((valid & uf.eq('')).sum())
            qa['validas_uf_desconhecida']+=int((valid & uf.ne('') & ~uf.isin(UFS)).sum())
            if not bool(valid.any()): continue
            raw=df.loc[valid,list(COMP)].apply(lambda c:c.str.strip())
            dados=raw.apply(lambda c:pd.to_numeric(c.str.replace(',','.',regex=False),errors='coerce'))
            good=dados.notna().all(axis=1)&dados.ge(0).all(axis=1)&dados.le(200).all(axis=1)
            qa['validas_competencias_incompletas']+=int((~good).sum())
            if not bool(good.any()):continue
            x=dados.loc[good].to_numpy(dtype=np.float64)
            siglas=uf.loc[valid].loc[good].to_numpy(dtype=str)
            notas=nota.loc[valid].loc[good].to_numpy(dtype=np.float64)
            delta=x.sum(axis=1)-notas
            bad=np.abs(delta)>1e-6
            qa['n_somas_divergentes']+=int(np.count_nonzero(bad))
            qa['delta_total']+=float(delta[bad].sum())
            rowids=offset+np.flatnonzero(valid.to_numpy())[good.to_numpy()]
            prior=I17.splitmix64(rowids,ano,seed)
            atual['BR'].adicionar(x,prior);historico['BR'].adicionar(x,prior)
            for u in np.unique(siglas):
                if u not in atual:continue
                ix=siglas==u
                atual[u].adicionar(x[ix],prior[ix]);historico[u].adicionar(x[ix],prior[ix])
                discrep_ufs[u][0]+=int(np.count_nonzero(bad[ix]))
                discrep_ufs[u][1]+=float(delta[ix & bad].sum())
        for fld in ('status1_sem_nota','status1_nota_invalida','validas_sem_uf',
                    'validas_uf_desconhecida','validas_competencias_incompletas'):
            if qa[fld]: raise ValueError(f'{ano}: dados inválidos: {fld}={qa[fld]}')
        br=periods[ano]['BR']['r14']
        if qa['validas']!=br['n_validas'] or (br.get('total_registros') is not None
                and qa['total_registros']!=br['total_registros']):
            raise ValueError(f'{ano}: população microdados/IND-014 divergente')
        if qa['n_somas_divergentes']!=br['n_somas_divergentes'] or abs(
                qa['delta_total']-float(br['delta_soma_competencias_menos_nota_redacao']))>1e-5:
            raise ValueError(f'{ano}: exceção SC/2023 não reproduzida')
        for u in UFS:
            re=periods[ano][u]['r14']
            if (discrep_ufs[u][0]!=re['n_somas_divergentes'] or abs(
                discrep_ufs[u][1]-float(re['delta_soma_competencias_menos_nota_redacao']))>1e-5):
                raise ValueError(f'{ano}/{u}: divergências das competências não reproduzidas')
        if any(atual[u].n!=periods[ano][u]['n'] for u in ('BR',*UFS)):
            raise ValueError(f'{ano}: amostras não cobrem POP_VALID por UF')
        anual[ano]=atual
        print(f'  {qa["validas"]:,} redações válidas; amostra BR={len(atual["BR"].x):,}',flush=True)
    if any(historico[u].n!=periods['historical'][u]['n'] for u in ('BR',*UFS)):
        raise ValueError('Histórico: N não confere com IND-014')
    return anual,historico


def indice_silhouette(z,labels,max_n:int,seed:int)->tuple[float,int]:
    if max_n<2:raise ValueError('silhouette-max precisa ser >= 2')
    n=min(len(z),max_n)
    if len(set(labels))<2 or len(set(labels))>=len(z):
        raise ValueError('Silhouette indefinida para rótulos')
    # O sklearn avalia aleatoriamente os dados (quando há sample_size).
    # Escolha determinística; até 5 tentativas caso um cluster raro desapareça.
    if n==len(z):
        return float(silhouette_score(z,labels,metric='euclidean')),n
    for tentativa in range(5):
        rng=np.random.RandomState(seed+tentativa)
        idx=rng.permutation(len(z))[:n]
        lab=labels[idx]
        if 2<=len(np.unique(lab))<n:
            return float(silhouette_score(z[idx],lab,metric='euclidean')),n
    raise ValueError('Subamostra Silhouette não possui pelo menos dois clusters')


def calcular_metricas(z,labels,max_n:int,seed:int)->dict:
    s,n=indice_silhouette(z,labels,max_n,seed)
    db=float(davies_bouldin_score(z,labels))
    ch=float(calinski_harabasz_score(z,labels))
    if not all(np.isfinite([s,db,ch])) or not (-1-1e-8<=s<=1+1e-8 and db>=0 and ch>0):
        raise ValueError('Métricas de clustering fora dos intervalos válidos')
    return {'silhouette':round(s,9), 'silhouette_sample_n':n,
            'davies_bouldin':round(db,9), 'calinski_harabasz':round(ch,9)}


def comparar_k(z:np.ndarray,silmax:int,seed_sil:int)->dict:
    candidatos=[]
    for k in range(2,9):
        if len(z)<k*MIN_CLUSTER or np.unique(z,axis=0).shape[0]<k:
            candidatos.append({'k':k,'status':'insuficiente'});continue
        model=KMeans(n_clusters=k,init='k-means++',n_init=N_INIT_COMPARE,
                max_iter=500,random_state=SEED_COMPARE,algorithm='lloyd',tol=0.0)
        labs=model.fit_predict(z)
        rr=I17.reconciliar_centroides(z,labs,k)
        if rr is None:
            candidatos.append({'k':k,'status':'grupo_vazio'});continue
        centros,labs,counts,passos=rr
        if np.min(counts)<MIN_CLUSTER:
            candidatos.append({'k':k,'status':'cluster_amostral_menor_30'});continue
        inert=float(np.sum((z-centros[labs])**2))
        met=calcular_metricas(z,labs,silmax,seed_sil)
        candidatos.append({'k':k,'status':'ok','n_init':N_INIT_COMPARE,
            'random_state':SEED_COMPARE,'n_clusters':k,
            'min_cluster_amostra':int(np.min(counts)),
            'inercia_por_redacao':round(inert/len(z),9),
            'iteracoes_refinamento':passos,**met})
    v=[a for a in candidatos if a['status']=='ok']
    return {'k_testados':list(range(2,9)),'n_init':N_INIT_COMPARE,
            'seed':SEED_COMPARE,'candidatos':candidatos,
            'k_maior_silhouette':max(v,key=lambda q:q['silhouette'])['k'] if v else None,
            'k_menor_davies_bouldin':min(v,key=lambda q:q['davies_bouldin'])['k'] if v else None,
            'k_maior_calinski_harabasz':max(v,key=lambda q:q['calinski_harabasz'])['k'] if v else None,
            'nota':'k sugeridos por índices isolados; NÃO constituem escolha definitiva nem teste de estabilidade'}


def avaliar_grupo(ac:I17.Amostra,ref:dict,ctx:str,silmax:int,comparacao:bool)->dict:
    if ac.n!=ref['n'] or len(ac.x)!=ref['r17']['n_amostra_ml']:
        raise ValueError(f'{ctx}: N/amostra determinística difere do IND-017')
    z=(ac.x-ref['mu'])/ref['sd']
    if not np.isfinite(z).all():raise ValueError(f'{ctx}: z-score não finito')
    centers=ref['centros']
    dsq=np.sum((z[:,None,:]-centers[None,:,:])**2,axis=2)
    labels=np.argmin(dsq,axis=1)
    sizes=np.bincount(labels,minlength=ref['k'])
    if list(map(int,sizes))!=[c['n_amostra'] for c in ref['r17']['clusters']]:
        raise ValueError(f'{ctx}: classificações amostrais NÃO reproduzem IND-017')
    medias=np.vstack([z[labels==j].mean(axis=0) for j in range(ref['k'])])
    if not np.allclose(medias,centers,atol=5e-8,rtol=0):
        raise ValueError(f'{ctx}: centroides IND-017 não são médias da amostra original')
    inertia=float(np.sum(dsq[np.arange(len(z)),labels]))
    if abs(inertia-ref['r17']['inercia_amostra'])>max(0.002,5e-7*inertia):
        raise ValueError(f'{ctx}: inércia não reproduz IND-017')
    metrics=calcular_metricas(z,labels,silmax,SEED_SIL)
    gr={'n_validas':ref['n'],'n_amostra_ml':len(z),'k':ref['k'],
        'k_alvo':ref['r17']['k_alvo'], 'min_cluster_amostra':int(min(sizes)),
        'cluster_n_amostral':[int(c) for c in sizes],
        'inercia_por_redacao_amostral':round(inertia/len(z),9),
        'algoritmo_original':'sklearn.cluster.KMeans',
        'n_init_original':ref['r17']['n_init'],
        'random_seed_original':ref['r17']['semente_base'],
        'centroides_iguais_medias':True,'amostra_reconstituida_ind017':True,
        'nenhum_registro_individual_exportado':True,
        **metrics}
    if comparacao:
        gr['comparacao_k']=comparar_k(z,silmax,SEED_SIL)
    return gr


def processar_metricas(anual:dict,historico:dict,refs:dict,silmax:int,comparacao:str):
    out=[]
    for per in (*ANOS,'historical'):
        am=historico if per=='historical' else anual[per]
        print(f'IND-019 | {per}: calculando métricas de 28 modelos...',flush=True)
        groups={}
        for uf in ('BR',*UFS):
            compare=(comparacao=='todos' or (comparacao=='brasil' and uf=='BR'))
            groups[uf]=avaliar_grupo(am[uf],refs[per][uf],f'{per}/{uf}',silmax,compare)
        if per=='historical':
            item={'periodo':'2019-2025','brasil':groups['BR'],
                  'ufs':[{'uf':u,**groups[u]} for u in UFS],
                  'qualidade':{'status':'ok','amostra_historica_independente':True}}
        else:
            item={'ano':per,'arquivo_fonte':I17.fonte(per,Path('.')).name,
                  'brasil':groups['BR'],
                  'ufs':[{'uf':u,**groups[u]} for u in UFS],
                  'qualidade':{'status':'ok'}}
        out.append(item)
        print(f'  BR: k={groups["BR"]["k"]} | Sil={groups["BR"]["silhouette"]:.4f} | '
              f'DB={groups["BR"]["davies_bouldin"]:.4f} | '
              f'CH={groups["BR"]["calinski_harabasz"]:.1f}',flush=True)
    return out[:7],out[7]


def resumo(g:dict)->dict:
    # Inclui comparação, quando disponível, sem índices ou linhas individuais.
    return deepcopy(g)


def atualizar_dashboard(ano:dict,anos:list[dict],hist:dict,original:dict,gerado:str,silmax:int,comparacao:str)->dict:
    d=deepcopy(original)
    d['pages']['competencies']['clusters']['quality']={
        'indicator_id':IND,'population':'AMOSTRA_ML',
        'method':METODO,'brasil':resumo(ano['brasil']),
        'by_uf':[{'uf':u['uf'],**resumo(u)} for u in ano['ufs']],
        'note':RESSALVAS}
    d['pages']['temporal']['ind019']={
        'indicator_id':IND,
        'national_by_year':[{'year':p['ano'],**resumo(p['brasil'])} for p in anos],
        'period_total':resumo(hist['brasil']),
        'period_by_uf':[{'uf':u['uf'],**resumo(u)} for u in hist['ufs']],
        'historical_note':'Métricas de modelo treinado com amostra histórica independente; não é média de métricas anuais.'}
    d['pages']['methodology']['ind019']={
        'definition':'Qualidade interna dos clusters K-Means IND-017, avaliada na AMOSTRA_ML reconstituída.',
        'method':METODO,'catalog_population':'AMOSTRA_ML',
        'source_indicators':['IND-014','IND-017','IND-018'],
        'source_file':ano['arquivo_fonte'],
        'silhouette_max_n':silmax,
        'silhouette_random_seed':SEED_SIL,
        'silhouette_subsampling':'randomização determinística sem reposição DENTRO da amostra de treinamento',
        'davies_bouldin_calinski_harabasz':'calculados em toda a AMOSTRA_ML',
        'comparacao_k_2_8':comparacao,
        'alternative_k_n_init':N_INIT_COMPARE,'alternative_k_seed':SEED_COMPARE,
        'original_k_n_init':ano['brasil']['n_init_original'],
        'original_k_seed':ano['brasil']['random_seed_original'],
        'limitations':RESSALVAS}
    d['quality']['ind019_validation']={
        'status':'ok','source_indicator':'IND-017',
        'n_amostra_ml_brasil':ano['brasil']['n_amostra_ml'],
        'k_brasil':ano['brasil']['k'],
        'amostra_igual_ind017':True,'inercia_centroides_iguais_ind017':True,
        'silhouette_sample_n':ano['brasil']['silhouette_sample_n'],
        'comparacao_k':comparacao,
        'nenhum_dado_individual_exportado':True,
        'revisao_academica_pendente':True,
        'estabilidade_nao_avaliada':True,'k_4_nao_validado_automaticamente':True}
    # Preserva todos os indicadores anteriores. Atualiza apenas metadados gerais.
    d['meta']['analysis_version']=VERSAO
    d['meta']['generated_at']=gerado
    d['meta']['data_status']='draft'
    aviso=('IND-019: silhouette (subamostra determinística da AMOSTRA_ML), '
        'Davies-Bouldin e Calinski-Harabasz medem separação interna dos clusters; '
        'comparação k=2..8 não comprova k ótimo e estabilidade não foi examinada. '
        'IND-017 usa n_init=5, diferente do n_init>=20 recomendado pelo guia; '
        'revisão acadêmica/privacidade pendentes.')
    if aviso not in d['meta'].setdefault('warnings',[]):d['meta']['warnings'].append(aviso)
    return d


def linhas_csv(anos,hist):
    rows=[]
    for p in [*anos,hist]:
        periodo=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*[(u['uf'],u) for u in p['ufs']]]:
            rows.append({'indicador_id':IND,'periodo':periodo,
                'abrangencia':'BR' if uf=='BR' else 'UF', 'uf':uf,
                'n_validas':g['n_validas'],'n_amostra_ml':g['n_amostra_ml'],
                'k':g['k'],'silhouette':g['silhouette'],
                'silhouette_sample_n':g['silhouette_sample_n'],
                'davies_bouldin':g['davies_bouldin'],
                'calinski_harabasz':g['calinski_harabasz'],
                'inercia_por_redacao_amostral':g['inercia_por_redacao_amostral'],
                'min_cluster_amostra':g['min_cluster_amostra'],
                'amostra_reconstituida_ind017':g['amostra_reconstituida_ind017'],
                'comparacao_k_2_8_executada':'comparacao_k' in g,
                'method':METODO})
    if len(rows)!=8*28:raise ValueError('CSV: 224 linhas esperadas')
    return rows


def salvar_json(path:Path,data:dict):
    with path.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')


def salvar_csv(path:Path,rows:list[dict]):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';')
        wr.writeheader();wr.writerows(rows)


def validar_schema(d:dict,raiz:Path):
    for k in ('meta','filters','quality','pages'):
        if k not in d:raise ValueError(f'Dashboard não possui {k}')
    for candidato in (raiz/'docs'/'04_resultados_analises.schema.json',
                      raiz/'docs'/'metodologia'/'04_resultados_analises.schema.json',
                      raiz/'04_resultados_analises.schema.json'):
        if candidato.is_file():
            import jsonschema
            jsonschema.validate(d,ler_json(candidato))
            return 'JSON Schema v1.0.0'
    return 'estrutura mínima; JSON Schema local indisponível'


def executar(raiz:Path,bloco:int=BLOCO,silmax:int=SIL_MAX,comparacao:str='brasil'):
    if bloco<1 or silmax<2 or comparacao not in ('brasil','todos','nenhuma'):
        raise ValueError('Parâmetros: bloco>=1, silhouette-max>=2, comparacao brasil/todos/nenhuma')
    m14,m17,m18,refs,dashes,cap,seed=carregar_pre_requisitos(raiz)
    anos_am,hist_am=extrair_amostras(raiz,refs,cap,seed,bloco)
    anos,hist=processar_metricas(anos_am,hist_am,refs,silmax,comparacao)
    rows=linhas_csv(anos,hist)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    dashes_novos={p['ano']:atualizar_dashboard(p,anos,hist,dashes[p['ano']],gerado,silmax,comparacao) for p in anos}
    checks={validar_schema(d,raiz) for d in dashes_novos.values()}
    mod={'meta':{
        'indicator_id':IND,'module_schema_version':'ind019-module-1.0.0',
        'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
        'generated_at':gerado,'data_status':'draft',
        'source_files':{str(p['ano']):p['arquivo_fonte'] for p in anos},
        'source_indicator_files':['IND_014_variancia_explicada_pca.json',
                                   'IND_017_perfis_competencias.json',
                                   'IND_018_tamanho_clusters.json'],
        'population_definition':'AMOSTRA_ML do IND-017, reconstituída sobre microdados 2019–2025',
        'geographic_dimension':'SG_UF_PROVA','method':METODO,
        'sample_selection':'mesma prioridade bottom-k (splitmix64) do IND-017',
        'max_sample_per_group':cap,'sample_seed':seed,
        'silhouette_max_n':silmax,'silhouette_seed':SEED_SIL,
        'other_metrics':'toda a AMOSTRA_ML',
        'comparacao_k':comparacao,'k_candidatos':list(range(2,9)),
        'n_init_comparacao':N_INIT_COMPARE,'seed_comparacao':SEED_COMPARE,
        'n_init_ind017_original':m17['years'][0]['brasil']['n_init'],
        'source_discrepancies':m14['meta'].get('source_discrepancies',{}),
        'publication_status':'draft; revisão acadêmica e privacidade pendentes',
        'notes':RESSALVAS},
        'indicator':{'id':IND,'name':NOME,'unit':'indices_qualidade',
            'dashboard_json_path':'pages.competencies.clusters.quality',
            'visualization':'KPI/tabela'},
        'years':anos,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    json.dumps(mod,allow_nan=False)
    pasta=raiz/'outputs';csv_dir=pasta/'indicadores';json_dir=pasta/'json'
    csv_dir.mkdir(parents=True,exist_ok=True);json_dir.mkdir(parents=True,exist_ok=True)
    # Staging de TODOS os arquivos + validação, antes de substituir qualquer um.
    with tempfile.TemporaryDirectory(prefix='.ind019_stage_',dir=pasta) as tmp:
        td=Path(tmp)
        salvar_csv(td/'IND_019_qualidade_clustering.csv',rows)
        salvar_json(td/'IND_019_qualidade_clustering.json',mod)
        for ano in ANOS:salvar_json(td/f'dashboard_enem_{ano}.json',dashes_novos[ano])
        with (td/'IND_019_qualidade_clustering.csv').open(encoding='utf-8-sig') as f:
            if sum(1 for _ in csv.DictReader(f,delimiter=';'))!=len(rows):
                raise ValueError('CSV gerado incompleto')
        if ler_json(td/'IND_019_qualidade_clustering.json')['indicator']['id']!=IND:
            raise ValueError('JSON modular inválido')
        for ano in ANOS:
            if ler_json(td/f'dashboard_enem_{ano}.json')['quality']['ind019_validation']['status']!='ok':
                raise ValueError(f'Dashboard {ano} incompleto')
        arquivos=[('IND_019_qualidade_clustering.csv',csv_dir),
                  ('IND_019_qualidade_clustering.json',json_dir),
                  *[(f'dashboard_enem_{ano}.json',json_dir) for ano in ANOS]]
        for nome,dest in arquivos:os.replace(td/nome,dest/nome)
    print('\nIND-019 CONCLUÍDO',flush=True)
    print('  224 modelos avaliados; CSV com 224 linhas; JSON modular e 7 dashboards',flush=True)
    print('  Comparação k=2..8: '+comparacao+'; '+', '.join(sorted(checks)),flush=True)
    print('  Nenhum registro individual exportado; data_status=draft',flush=True)


def main():
    p=argparse.ArgumentParser(description='IND-019: qualidade do K-Means IND-017')
    p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--bloco',type=int,default=BLOCO)
    p.add_argument('--silhouette-max',type=int,default=SIL_MAX)
    p.add_argument('--comparacao',choices=['brasil','todos','nenhuma'],default='brasil')
    o=p.parse_args()
    executar(o.raiz.resolve(),bloco=o.bloco,silmax=o.silhouette_max,comparacao=o.comparacao)

if __name__=='__main__':main()
