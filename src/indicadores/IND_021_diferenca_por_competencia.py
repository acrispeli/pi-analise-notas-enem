#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-021 — Diferença absoluta AV1×AV2 por competência (C1–C5).

Fonte: 2019–2024: COMPETENCIAS_REDACAO_{ano}.csv + UF do participante,
  unidas por NU_INSCRICAO/NU_ANO. Em 2024, UF vem exclusivamente de
  PARTICIPANTES_2024.csv; NÃO tentar juntar com RESULTADOS_2024 (NU_SEQUENCIAL).
  2025: RESULTADOS_2025.csv contém avaliações e SG_UF_PROVA na mesma linha.

Denominador de origem: POP_EVALUATOR do IND-020, notas totais AV1 e AV2 válidas.
Denominador das 5 competências: subconjunto pareado completo, com todas as
  NU_NOTA_COMP1..5_AV1/AV2 presentes/válidas em [0,200]. Se houver ausência,
  o script divulga os denominadores e não imputa valores: N_COMP <= N_EVALUATOR.
Todos os cálculos são exatos sobre as distribuições de valores observados;
  nenhum registro individual ou identificador é exportado.

Executar APÓS IND-020, não em paralelo a outros scripts:
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_021_diferenca_por_competencia.py
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
import sqlite3
import tempfile

import numpy as np
import pandas as pd
import IND_020_diferenca_total_av1_av2 as base

ANOS=base.ANOS
UFS=base.UFS
IND='IND-021'
NOME='Diferença por competência'
METODO='abs_nota_competencia_av1_av2_pop_evaluator_cinco_pares_completos'
VERSAO='2.20.0-'+'-'.join(f'ind{i:03d}' for i in range(1,22))
MIN_N=30
BLOCO=100_000
COMPETENCIAS=tuple(f'C{i}' for i in range(1,6))
AV_COLS=tuple(f'NU_NOTA_COMP{i}_AV{j}' for i in range(1,6) for j in (1,2))
NOTAS=(
  'Diferenças absolutas por competência são medidas exploratórias de concordância '
  'AV1×AV2, não avaliações de desempenho de corretores nem prova de erro. '
  'A POP_EVALUATOR tem as duas notas totais presentes (IND-020); o IND-021 '
  'usa, dentro dela, casos completos nas dez notas de competências. Não se '
  'imputam notas de competências ausentes. Todas as cinco competências usam '
  'o mesmo denominador dentro de cada recorte, que pode ser inferior à '
  'POP_EVALUATOR; verificar cobertura. UF é local de prova, não residência. '
  'Modelos históricos somam participações, não pessoas únicas. '
  'Somente estatísticas agregadas de grupos com n>=30 são exportadas. '
  'Status draft; revisão acadêmica e privacidade complementar pendentes.')

class Distribuicao:
    """Estatísticas exatas de valores discretos (com suporte a décimas)."""
    __slots__=('n','s','s2','freq')
    def __init__(self):
        self.n=0;self.s=0.;self.s2=0.;self.freq=Counter()
    def adicionar(self,valores):
        x=np.asarray(valores,dtype=np.float64)
        if not len(x):return
        if not np.isfinite(x).all() or np.any((x<0)|(x>200)):
            raise ValueError('Diferença por competência fora de [0,200]')
        x=np.round(x,8)
        self.n+=len(x);self.s+=float(x.sum());self.s2+=float(np.dot(x,x))
        u,ns=np.unique(x,return_counts=True)
        self.freq.update({float(v):int(n) for v,n in zip(u,ns)})
    def quantil(self,q):
        if self.n==0:raise ValueError('Distribuição vazia')
        h=(self.n-1)*q;lo=math.floor(h);hi=math.ceil(h);f=h-lo
        val_lo=val_hi=None;cum=0
        for v,n in sorted(self.freq.items()):
            cum+=n
            if val_lo is None and cum>lo:val_lo=v
            if cum>hi:val_hi=v;break
        return round(float(val_lo*(1-f)+val_hi*f),6)
    def unir(self,alvo):
        alvo.n+=self.n;alvo.s+=self.s;alvo.s2+=self.s2
        alvo.freq.update(self.freq)
    def resumo(self):
        if self.n<MIN_N:raise ValueError(f'Grupo com {self.n} pares, abaixo do mínimo {MIN_N}')
        q1=self.quantil(.25);md=self.quantil(.5);q3=self.quantil(.75)
        p90=self.quantil(.90);iqr=q3-q1
        baixo=min((v for v in self.freq if v>=q1-1.5*iqr),default=min(self.freq))
        alto=max((v for v in self.freq if v<=q3+1.5*iqr),default=max(self.freq))
        var=max(0.,self.s2/self.n-(self.s/self.n)**2)
        return {'n_pares_validos':self.n,'media':round(self.s/self.n,6),
          'mediana':md,'p25':q1,'p75':q3,'p90':p90,
          'desvio_padrao':round(math.sqrt(var),6),'ddof':0,
          'minimo':min(self.freq),'maximo':max(self.freq),
          'boxplot':{'q1':q1,'mediana':md,'q3':q3,'iqr':round(iqr,6),
                     'bigode_inferior':baixo,'bigode_superior':alto,
                     'criterio':'Tukey_1.5_IQR; extremos observados sem pontos individuais'},
          'sem_dados_individuais':True}

def iniciar():
    return {u:{'n_evaluator':0,'n_comp':0,
             'comps':{c:Distribuicao() for c in COMPETENCIAS}}
            for u in ('BR',*UFS)}

def adicionar(grupos,ufs,matrizes,total_elig,ano):
    """Cada bloco usa UMA máscara de completude para as cinco competências."""
    if len(ufs)!=len(total_elig) or matrizes.shape!=(len(ufs),5):
        raise AssertionError('Incompatibilidade de dimensões')
    if not np.isin(ufs,UFS).all():raise ValueError(f'{ano}: UF ausente ou desconhecida')
    for uf in np.unique(ufs):
        mask=ufs==uf
        for u in ('BR',uf):
            g=grupos[u]
            g['n_evaluator']+=int(np.sum(total_elig[mask]))
            g['n_comp']+=int(np.sum(mask))
            data=matrizes[mask]
            for j,c in enumerate(COMPETENCIAS):g['comps'][c].adicionar(data[:,j])

def validar_requisitos(raiz):
    jdir=raiz/'outputs'/'json'
    mod=jdir/'IND_020_diferenca_total_av1_av2.json'
    if not mod.is_file():raise FileNotFoundError('É necessário concluir IND-020 antes de IND-021: '+str(mod))
    p20=base.ler_json(mod)
    if p20.get('indicator',{}).get('id')!='IND-020' or p20.get('meta',{}).get('data_status')!='draft':
        raise ValueError('Módulo IND-020 inválido')
    if len(p20.get('years',[]))!=7:raise ValueError('IND-020 não cobre todos os anos')
    dashboards={}
    for ano in ANOS:
        p=jdir/f'dashboard_enem_{ano}.json'
        if not p.is_file():raise FileNotFoundError(str(p))
        d=base.ler_json(p)
        if d.get('meta',{}).get('year')!=ano or d['meta'].get('data_status')!='draft':
            raise ValueError(f'{ano}: dashboard incompleto/inválido')
        if d.get('quality',{}).get('ind020_validation',{}).get('status')!='ok':
            raise ValueError(f'{ano}: IND-020 ainda não está integrado')
        if 'ind021_validation' in d['quality'] or 'by_competency' in d.get('pages',{}).get('evaluators',{}):
            raise ValueError(f'{ano}: IND-021 já registrado; não sobrescrever')
        for pth in ('evaluators','methodology','temporal'):
            if not isinstance(d.get('pages',{}).get(pth),dict):raise ValueError(f'{ano}: página {pth} ausente')
        dashboards[ano]=d
    for ano in ANOS:
        geo,aval=base.fonte_ano(raiz,ano)
        for p in (geo,aval):
            if p is not None and not p.is_file():raise FileNotFoundError(str(p))
    return p20,dashboards

def acumular_bloco(grupos,historico,ufs,total,comps,ano):
    # todas as linhas recebidas são POP_EVALUATOR; comps (n,10) com np.nan para ausentes.
    valid=np.isfinite(comps).all(axis=1)
    if len(ufs)!=len(total) or len(comps)!=len(total):raise AssertionError('Bloco incompatível')
    if len(total) and not np.all(total):raise AssertionError('Bloco não elegível')
    if len(ufs) and not np.isin(ufs,UFS).all():raise ValueError(f'{ano}: UF inválida na POP_EVALUATOR')
    diff=np.abs(comps[valid,0::2]-comps[valid,1::2]);validufs=ufs[valid]
    for g in (grupos,historico):
        g['BR']['n_evaluator']+=len(total)
        for uf in np.unique(ufs):g[uf]['n_evaluator']+=int(np.sum(ufs==uf))
        g['BR']['n_comp']+=len(diff)
        for uf in np.unique(validufs):g[uf]['n_comp']+=int(np.sum(validufs==uf))
        for u in ('BR',*np.unique(validufs)):
            data=diff if u=='BR' else diff[validufs==u]
            for j,c in enumerate(COMPETENCIAS):g[u]['comps'][c].adicionar(data[:,j])
    return int(len(total)),int(len(diff))

def processar_ano(raiz,ano,grupos,historico,bloco,tempdir):
    geo,p=base.fonte_ano(raiz,ano)
    cols=['NU_NOTA_AV1','NU_NOTA_AV2',*AV_COLS]
    if geo is None:cols=['SG_UF_PROVA',*cols]
    else:cols=['NU_INSCRICAO','NU_ANO',*cols]
    base.validar_cabecalho(p,tuple(cols))
    qa={'arquivo_avaliacoes':p.name,'arquivo_geo':geo.name if geo else p.name,
        'metodo_geografia':'NU_INSCRICAO+NU_ANO' if geo else 'SG_UF_PROVA_na_mesma_linha',
        'n_linhas_fonte':0,'n_sem_nota_total_pareada':0,'n_pop_evaluator':0,
        'n_pares_comp_completos':0,'n_comp_incompletas':0,
        'n_comp_invalidas':0,'n_elegiveis_sem_uf':0,'n_elegiveis_sem_join':0}
    db=None
    try:
        if geo is not None:
            db=sqlite3.connect(tempdir/f'geo_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['registros_geo']=base.construir_geo(db,geo,ano,bloco)
            # A tabela "vistos" já é criada pela função construir_geo.
        print(f'IND-021 | {ano}: processando diferenças C1–C5...',flush=True)
        for df in base.ler_blocos(p,cols,bloco):
            qa['n_linhas_fonte']+=len(df)
            if db is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any() or df['NU_ANO'].str.strip().ne(str(ano)).any():
                    raise ValueError(f'{ano}: chave/NU_ANO inválido em {p.name}')
                try:db.executemany('INSERT INTO vistos VALUES (?)',((v,) for v in keys.tolist()))
                except sqlite3.IntegrityError as e:raise ValueError(f'{ano}: duplicidade NU_INSCRICAO no complemento') from e
            a=base.digitos(df['NU_NOTA_AV1']);b=base.digitos(df['NU_NOTA_AV2'])
            ra=df['NU_NOTA_AV1'].str.strip();rb=df['NU_NOTA_AV2'].str.strip()
            both=ra.ne('')&rb.ne('')
            if ((~a[both].between(0,1000))|(~b[both].between(0,1000))).any():
                raise ValueError(f'{ano}: nota total AV1/AV2 preenchida inválida')
            qa['n_sem_nota_total_pareada']+=int((~both).sum())
            if not both.any():continue
            e=df.loc[both]
            qa['n_pop_evaluator']+=len(e)
            raw=e[list(AV_COLS)].apply(lambda s:s.str.strip())
            completa=raw.ne('').all(axis=1).to_numpy()
            vals=np.stack([base.digitos(raw[c]).to_numpy(dtype=np.float64) for c in AV_COLS],axis=1)
            invalid=((~np.isfinite(vals)) & (raw.to_numpy()!='')) | (np.isfinite(vals) & ((vals<0)|(vals>200)))
            if np.any(invalid):
                qa['n_comp_invalidas']+=int(np.any(invalid,axis=1).sum())
                raise ValueError(f'{ano}: competência AV1/AV2 preenchida inválida')
            complete_mask=completa&np.isfinite(vals).all(axis=1)
            qa['n_comp_incompletas']+=int(np.sum(~complete_mask))
            qa['n_pares_comp_completos']+=int(np.sum(complete_mask))
            if db is None:
                ufs=e['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
                vv=vals
            else:
                ids=e['NU_INSCRICAO'].str.strip().tolist()
                # Associe dados numericamente validados usando a chave mascarada.
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY, ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)',[(v,i) for i,v in enumerate(ids)])
                    achados=db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g ON g.key=l.key AND g.ano=?',(ano,)).fetchall()
                finally:
                    db.execute('DROP TABLE lote')
                if len(achados)!=len(ids):
                    qa['n_elegiveis_sem_join']+=len(ids)-len(achados)
                    raise ValueError(f'{ano}: {len(ids)-len(achados)} avaliações elegíveis sem correspondência geográfica')
                ufs=np.empty(len(ids),dtype='<U3')
                for i,u in achados:ufs[int(i)]=str(u).strip().upper()
                vv=vals
            if len(ufs) and not np.isin(ufs,UFS).all():
                qa['n_elegiveis_sem_uf']+=int((~np.isin(ufs,UFS)).sum())
                raise ValueError(f'{ano}: UF inválida na POP_EVALUATOR')
            acumular_bloco(grupos,historico,ufs,np.ones(len(ufs),dtype=bool),
                            np.where(complete_mask[:,None],vv,np.nan),ano)
        if qa['n_linhas_fonte']!=qa['n_pop_evaluator']+qa['n_sem_nota_total_pareada']:
            raise AssertionError(f'{ano}: POP_EVALUATOR não fecha com a fonte')
        if qa['n_pop_evaluator']!=grupos['BR']['n_evaluator'] or qa['n_pares_comp_completos']!=grupos['BR']['n_comp']:
            raise AssertionError(f'{ano}: totais de elegíveis inconsistentes')
        if sum(grupos[u]['n_evaluator'] for u in UFS)!=grupos['BR']['n_evaluator']:
            raise AssertionError(f'{ano}: soma das UFs não fecha POP_EVALUATOR')
        if sum(grupos[u]['n_comp'] for u in UFS)!=grupos['BR']['n_comp']:
            raise AssertionError(f'{ano}: soma das UFs não fecha POP_EVALUATOR_COMP')
        print(f'  POP_EVALUATOR={qa["n_pop_evaluator"]:,} | pares C1–C5 completos={qa["n_pares_comp_completos"]:,}',flush=True)
        return qa
    finally:
        if db is not None:db.close()

def compilar_recorte(g):
    n=g['n_comp'];ne=g['n_evaluator']
    if not 0<=n<=ne:raise AssertionError('Denominadores inconsistentes')
    if n<MIN_N:raise ValueError(f'POP_EVALUATOR_COMP n={n}<30, saída bloqueada')
    comps=[{'competencia':c,**g['comps'][c].resumo()} for c in COMPETENCIAS]
    if any(v['n_pares_validos']!=n for v in comps):raise AssertionError('Denominador desigual em C1–C5')
    maiores=sorted(comps,key=lambda x:(-x['media'],x['competencia']))
    return {'n_pop_evaluator':ne,'n_competencias_pareadas':n,
        'percentual_cobertura_competencias':round(100*n/ne,6) if ne else 0,
        'population':'POP_EVALUATOR (casos completos C1-C5)',
        'competencias':comps,
        'competencia_maior_media_diferenca':maiores[0]['competencia'],
        'ordenacao_media_decrescente':[v['competencia'] for v in maiores],
        'medida':'abs(NU_NOTA_COMPi_AV1-NU_NOTA_COMPi_AV2)',
        'sem_dados_individuais':True}

def compilar_periodo(ano,grupos,qa=None):
    br=compilar_recorte(grupos['BR']);ufs=[{'uf':uf,**compilar_recorte(grupos[uf])} for uf in UFS]
    for k in ('n_pop_evaluator','n_competencias_pareadas'):
        if sum(v[k] for v in ufs)!=br[k]:raise AssertionError(f'{ano}: UFs não fecham {k}')
    p={'brasil':br,'ufs':ufs,'qualidade':{'status':'ok','n_ufs':27,'soma_uf_igual_brasil':True,
        'comparacao_5_competencias_mesmo_denominador':True,'minimo_n_30':True}}
    if isinstance(ano,int):
        p.update({'ano':ano,'arquivo_fonte':base.fonte_ano(Path('.'),ano)[1].name,'qualidade_fonte':qa})
    else:p.update({'periodo':'2019-2025','qualidade_fonte':{'participacoes_nao_pessoas':True}})
    return p

def linhas_csv(anos,hist):
    rows=[]
    for p in (*anos,hist):
        per=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*[(u['uf'],u) for u in p['ufs']]]:
            for c in g['competencias']:
                rows.append({'indicador_id':IND,'periodo':per,'abrangencia':'BR' if uf=='BR' else 'UF',
                    'uf':uf,'populacao':'POP_EVALUATOR (cinco pares completos)',
                    'n_pop_evaluator':g['n_pop_evaluator'],
                    'n_pares_validos':c['n_pares_validos'],
                    'cobertura_pct':g['percentual_cobertura_competencias'],
                    'competencia':c['competencia'],'media':c['media'],
                    'mediana':c['mediana'],'p25':c['p25'],'p75':c['p75'],'p90':c['p90'],
                    'desvio_padrao':c['desvio_padrao'],'minimo':c['minimo'],'maximo':c['maximo'],
                    'iqr':c['boxplot']['iqr'],
                    'bigode_inferior':c['boxplot']['bigode_inferior'],
                    'bigode_superior':c['boxplot']['bigode_superior'],
                    'metodo':METODO})
    return rows

def dashboard(ano,periodos,hist,d,gerado):
    x=deepcopy(d);p=next(a for a in periodos if a['ano']==ano)
    ev=x['pages']['evaluators']
    ev['status']='partial'
    ev['reason']='IND-020 e IND-021 disponíveis; demais indicadores de avaliadores pendentes'
    ev['by_competency']={'indicator_id':IND,'population':'POP_EVALUATOR',
       'method':METODO,'brasil':deepcopy(p['brasil']),'by_uf':deepcopy(p['ufs']),
       'notes':NOTAS}
    x['pages']['temporal']['ind021']={'indicator_id':IND,
        'national_by_year':[{'year':a['ano'],**deepcopy(a['brasil'])} for a in periodos],
        'period_total':deepcopy(hist['brasil']),
        'period_by_uf':deepcopy(hist['ufs']),'note':NOTAS}
    x['pages']['methodology']['ind021']={
       'definition':'Diferença absoluta entre AV1 e AV2 por competência C1–C5.',
       'population':'POP_EVALUATOR; casos completos com dez notas de competências',
       'eligibility':'Ambas as notas totais AV1/AV2 em [0,1000]; dez notas de competência em [0,200]',
       'method':METODO,'sources':{'avaliacoes':p['qualidade_fonte']['arquivo_avaliacoes'],
           'uf':p['qualidade_fonte']['arquivo_geo']},
       'join':p['qualidade_fonte']['metodo_geografia'],
       'difference':'abs(NU_NOTA_COMPi_AV1 - NU_NOTA_COMPi_AV2)',
       'percentiles':'Hyndman-Fan tipo 7, exato via distribuição de frequências',
       'standard_deviation_ddof':0,
       'boxplot':'Tukey 1.5 IQR com bigodes nos valores observados, sem exibir pontos individuais',
       'min_group_count':MIN_N,'limitations':NOTAS}
    x['quality']['ind021_validation']={
        'status':'ok','source_indicator':'IND-020', 'method':METODO,
        'n_pop_evaluator_brasil':p['brasil']['n_pop_evaluator'],
        'n_cinco_pares_completos_brasil':p['brasil']['n_competencias_pareadas'],
        'soma_27_ufs_igual_brasil':True,'minimo_n_30':True,
        'cinco_competencias_mesmo_denominador':True,
        'n_registros_individuais_exportados':0,'revisao_privacidade_pendente':True}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso=('IND-021: divergência absoluta AV1/AV2 em C1-C5, apenas pares completos '
           'na POP_EVALUATOR; comparação entre competências usa o mesmo denominador. '
           'Dados draft, revisão acadêmica e privacidade complementar pendentes.')
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x

def executar(raiz,bloco=BLOCO):
    if bloco<1:raise ValueError('bloco deve ser >=1')
    p20,originais=validar_requisitos(raiz)
    ref={v['ano']:v for v in p20['years']}
    periodos=[];histgr=iniciar();qa={}
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ind021_sql_',dir=out) as tmp:
        for ano in ANOS:
            g=iniciar();qa[ano]=processar_ano(raiz,ano,g,histgr,bloco,Path(tmp))
            previsto=ref[ano]
            for uf in ('BR',*UFS):
                antigo=previsto['brasil'] if uf=='BR' else next(v for v in previsto['ufs'] if v['uf']==uf)
                esperado=antigo['n_avaliacoes_pareadas']
                if g[uf]['n_evaluator']!=esperado:
                    raise ValueError(f'{ano}/{uf}: POP_EVALUATOR={g[uf]["n_evaluator"]} difere IND-020={esperado}')
            periodos.append(compilar_periodo(ano,g,qa[ano]))
    hist=compilar_periodo('2019-2025',histgr)
    for uf in ('BR',*UFS):
        g=hist['brasil'] if uf=='BR' else next(v for v in hist['ufs'] if v['uf']==uf)
        h20=p20['historical']['brasil'] if uf=='BR' else next(v for v in p20['historical']['ufs'] if v['uf']==uf)
        if g['n_pop_evaluator']!=h20['n_avaliacoes_pareadas']:
            raise ValueError(f'Histórico/{uf}: POP_EVALUATOR diverge IND-020')
        for key in ('n_pop_evaluator','n_competencias_pareadas'):
            s=sum((p['brasil'] if uf=='BR' else next(v for v in p['ufs'] if v['uf']==uf))[key] for p in periodos)
            if g[key]!=s:raise AssertionError(f'Histórico/{uf}/{key}: soma divergente')
    rows=linhas_csv(periodos,hist)
    if len(rows)!=8*28*5:raise AssertionError('1120 registros esperados')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    ds={ano:dashboard(ano,periodos,hist,originais[ano],gerado) for ano in ANOS}
    checks={base.validar_schema(d,raiz) for d in ds.values()}
    modulo={'meta':{
         'indicator_id':IND,'module_schema_version':'ind021-module-1.0.0',
         'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
         'generated_at':gerado,'data_status':'draft',
         'source_files':{str(a):{'avaliacoes':qa[a]['arquivo_avaliacoes'],
                       'geo':qa[a]['arquivo_geo']} for a in ANOS},
         'population_definition':'POP_EVALUATOR (IND-020) com C1–C5 AV1/AV2 completos; N reduzido se faltantes',
         'source_indicator':'IND-020','geographic_dimension':'SG_UF_PROVA',
         'method':METODO,'minimum_group_count':MIN_N,'quantile_type':'Hyndman-Fan tipo 7',
         'quality_by_year':{str(a):qa[a] for a in ANOS},
         'publication_status':'draft; revisão acadêmica e privacidade complementar pendentes',
         'notes':NOTAS},
       'indicator':{'id':IND,'name':NOME,'unit':'pontos',
            'dashboard_json_path':'pages.evaluators.by_competency','visualization':'Boxplot'},
       'years':periodos,'historical':hist,
       'dashboard_files':[f'dashboard_enem_{a}.json' for a in ANOS]}
    json.dumps(modulo,allow_nan=False)
    csvdir=out/'indicadores';jsondir=out/'json'
    csvdir.mkdir(exist_ok=True,parents=True);jsondir.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix='.ind021_stage_',dir=out) as tmp:
        stage=Path(tmp);fn='IND_021_diferenca_por_competencia.csv';jn='IND_021_diferenca_por_competencia.json'
        with (stage/fn).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';')
            w.writeheader();w.writerows(rows)
        base.gravar_json(stage/jn,modulo)
        for ano in ANOS:base.gravar_json(stage/f'dashboard_enem_{ano}.json',ds[ano])
        with (stage/fn).open('r',encoding='utf-8-sig',newline='') as f:
            if sum(1 for _ in csv.DictReader(f,delimiter=';'))!=1120:raise AssertionError('CSV truncado')
        if base.ler_json(stage/jn)['indicator']['id']!='IND-021':raise AssertionError('JSON inválido')
        for ano in ANOS:
            if base.ler_json(stage/f'dashboard_enem_{ano}.json')['quality']['ind021_validation']['status']!='ok':
                raise AssertionError('Dashboard inválido')
        for src,dst in [(fn,csvdir),(jn,jsondir),
                        *[(f'dashboard_enem_{a}.json',jsondir) for a in ANOS]]:
            os.replace(stage/src,dst/src)
    print('\nIND-021 CONCLUÍDO: CSV, JSON modular, sete dashboards',flush=True)
    print(f'  POP_EVALUATOR histórico: {hist["brasil"]["n_pop_evaluator"]:,}',flush=True)
    print(f'  Pares completos históricos: {hist["brasil"]["n_competencias_pareadas"]:,}',flush=True)
    print(f'  Recortes: 224; linhas CSV: {len(rows)}; esquemas: {sorted(checks)}',flush=True)
    print('  Sem dados individuais; status=draft',flush=True)

def main():
    p=argparse.ArgumentParser(description='IND-021: diferenças AV1–AV2 por C1..C5, 2019–2025')
    p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--bloco',type=int,default=BLOCO)
    a=p.parse_args()
    executar(a.raiz.resolve(),a.bloco)

if __name__=='__main__':main()
