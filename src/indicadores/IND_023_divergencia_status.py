#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-023 — Divergência de situação entre AV1 e AV2 (ENEM 2019–2025).

Fonte principal: IND-022 já validado, que contou EXATAMENTE o gatilho
TP_STATUS_REDACAO_AV1 != TP_STATUS_REDACAO_AV2 entre status preenchidos,
na POP_EVALUATOR (IND-020). Não faz recontagem fictícia de microdados.

Modos:
  --modo agregados [padrão]: indicador completo em KPI por ano/UF/histórico,
      reutilizando contagens reais IND-022; matriz detalhada indisponível.
  --modo matriz: lê novamente os microdados para contar o cruzamento de códigos
      de status AV1×AV2, com supressão integral de matrizes com células raras.
      Cada matriz é conferida, por ano e por UF, contra o IND-022.

Em ambos, publica CSV+JSON modular e atualiza 7 dashboards cumulativos,
a menos que --somente-modulo. Nunca publica identificadores individuais.
Não executar em paralelo a outros scripts que escrevam os dashboards.

PowerShell (na raiz do projeto):
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_023_divergencia_status.py
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_023_divergencia_status.py --modo matriz
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
import pandas as pd
import IND_020_diferenca_total_av1_av2 as base
import IND_022_discrepancia_oficial as ind22

ANOS=base.ANOS
UFS=base.UFS
IND='IND-023'
METODO='taxa_status_av1_av2_na_pop_evaluator_a_partir_ind022_auditado'
VERSAO='2.22.0-'+'-'.join(f'ind{i:03d}' for i in range(1,24))
MIN_N=30
BLOCO=100_000
ARQUIVO='IND_023_divergencia_status'
NOTAS=('Compara exclusivamente TP_STATUS_REDACAO_AV1 com TP_STATUS_REDACAO_AV2 '
       'entre participações da POP_EVALUATOR (duas notas totais AV1/AV2 válidas). '
       'Status ausente não é classificado como igual. A taxa principal usa como '
       'denominador a POP_EVALUATOR; a taxa entre pares de status conhecidos '
       'é adicional e requer apresentar a cobertura. Contagens do IND-022 '
       'são a fonte exata já calculada do motivo status divergente. A matriz '
       'de transições detalhadas só é gerada a partir dos microdados no modo '
       'matriz, podendo ser inteiramente retida se houver células positivas <30. '
       'Códigos de status sem validação interanual não são agregados em matriz '
       'histórica. Divergência de situação não significa erro do avaliador nem '
       'mede a nota final; UF é local de prova. Histórico soma participações, '
       'não pessoas únicas. Uso exploratório, data_status=draft; revisão '
       'acadêmica e privacidade complementar pendentes.')
FIELDS=('n_pop_evaluator','n_pares_status_preenchidos','n_status_divergentes',
        'n_status_iguais','n_status_nao_comparaveis')


def ler_json(p):
    with Path(p).open('r',encoding='utf-8') as f: return json.load(f)


def obter_recorte(periodo,uf):
    if uf=='BR':return periodo['brasil']
    return next(x for x in periodo['ufs'] if x['uf']==uf)


def resumo_022(g):
    n=int(g['n_pop_evaluator']);pares=int(g['n_status_par_preenchido'])
    diff=int(g['n_criterio_status_divergente']);unk=int(g['n_status_criterio_desconhecido'])
    if n<MIN_N:raise ValueError(f'Recorte com n={n}<30; publicação bloqueada')
    if any(x<0 for x in (n,pares,diff,unk)) or pares+unk!=n or diff>pares:
        raise ValueError(f'Inconsistência nos contadores de status do IND-022: {g}')
    iguais=pares-diff
    r={'n_pop_evaluator':n,'n_pares_status_preenchidos':pares,
       'n_status_divergentes':diff,'n_status_iguais':iguais,
       'n_status_nao_comparaveis':unk,
       'percentual_divergencia_pop_evaluator':round(100*diff/n,6),
       'percentual_divergencia_pares_comparaveis':round(100*diff/pares,6) if pares else None,
       'percentual_cobertura_status':round(100*pares/n,6),
       'percentual_iguais_pares_comparaveis':round(100*iguais/pares,6) if pares else None,
       'populacao':'POP_EVALUATOR',
       'matriz_status':{'status':'nao_calculada_requer_microdados',
                       'celulas':[], 'nota':'Contagem cruzada não pode ser inferida do IND-022.'},
       'sem_dados_individuais':True}
    return r


def montar_periodo(fonte):
    out={'brasil':resumo_022(fonte['brasil']),
         'ufs':[{'uf':u,**resumo_022(obter_recorte(fonte,u))} for u in UFS],
         'qualidade':{'status':'ok','soma_27_ufs_igual_brasil':True,
                      'origem_contagens':'IND-022','minimum_group_count':MIN_N}}
    for campo in FIELDS:
        if sum(x[campo] for x in out['ufs'])!=out['brasil'][campo]:
            raise AssertionError(f'{campo}: soma UFs != Brasil')
    if 'ano' in fonte:out['ano']=int(fonte['ano'])
    else:out['periodo']='2019-2025'
    return out


def validar_consolidacao(anos,historico,m22,m20=None):
    for ano,p in zip(ANOS,anos):
        if p['ano']!=ano:raise AssertionError('Períodos fora da sequência 2019–2025')
    for uf in ('BR',*UFS):
        h=obter_recorte(historico,uf)
        for f in FIELDS:
            if h[f]!=sum(obter_recorte(p,uf)[f] for p in anos):
                raise AssertionError(f'Histórico {uf}/{f} não reconcilia')
        for p22,p23 in zip(m22['years'],anos):
            if obter_recorte(p22,uf)['n_criterio_status_divergente']!=obter_recorte(p23,uf)['n_status_divergentes']:
                raise AssertionError(f'Falha IND022×IND023: {uf} {p23["ano"]}')
        if m20:
            refs={p['ano']:p for p in m20['years']}
            for p23 in anos:
                n20=obter_recorte(refs[p23['ano']],uf)['n_avaliacoes_pareadas']
                if n20!=obter_recorte(p23,uf)['n_pop_evaluator']:
                    raise AssertionError(f'POP_EVALUATOR difere do IND-020: {uf}/{p23["ano"]}')
            if obter_recorte(m20['historical'],uf)['n_avaliacoes_pareadas']!=h['n_pop_evaluator']:
                raise AssertionError(f'Histórico IND-020 difere: {uf}')


def preparar(raiz,arquivo_022=None):
    path=Path(arquivo_022) if arquivo_022 else raiz/'outputs'/'json'/'IND_022_discrepancia_oficial.json'
    m22=ler_json(path)
    if m22.get('indicator',{}).get('id')!='IND-022' or m22.get('meta',{}).get('data_status')!='draft':
        raise ValueError('O arquivo IND-022 deve ser válido e draft')
    if len(m22.get('years',[]))!=7:raise ValueError('IND-022 não inclui sete anos')
    if [p['ano'] for p in m22['years']]!=list(ANOS):raise ValueError('IND-022 anos fora de ordem')
    m20path=raiz/'outputs'/'json'/'IND_020_diferenca_total_av1_av2.json'
    m20=ler_json(m20path) if m20path.is_file() else None
    if m20 is not None and m20.get('indicator',{}).get('id')!='IND-020':
        raise ValueError('Arquivo IND-020 inválido')
    anos=[montar_periodo(p) for p in m22['years']]
    hist=montar_periodo(m22['historical'])
    validar_consolidacao(anos,hist,m22,m20)
    return m22,anos,hist


def canonizar_status(df,ano):
    """Mesmo tratamento de zeros à esquerda/ausências empregado no IND-022."""
    cols=ind22.STATUS_COLS
    a,oka=ind22.codificar_status(df[cols[0]],ano,cols[0])
    b,okb=ind22.codificar_status(df[cols[1]],ano,cols[1])
    return a,b,oka & okb


def acumular_matriz(contadores,ufs,a,b,ok):
    if not (len(ufs)==len(a)==len(b)==len(ok)):
        raise AssertionError('Vetores incompatíveis na matriz')
    validos=np.asarray(ok,dtype=bool)
    if not np.isin(ufs,UFS).all():raise ValueError('UF inválida em pares de status')
    frame=pd.DataFrame({'uf':np.asarray(ufs)[validos],
                        'av1':np.asarray(a)[validos],
                        'av2':np.asarray(b)[validos]})
    for (u,s1,s2),n in frame.groupby(['uf','av1','av2']).size().items():
        contadores[u][(str(s1),str(s2))]+=int(n)
        contadores['BR'][(str(s1),str(s2))]+=int(n)


def contar_matriz_ano(raiz,ano,bloco,tmpdir):
    """Leitura offline: AV1×AV2 status, somente dentro da POP_EVALUATOR."""
    geo,aval=base.fonte_ano(raiz,ano)
    if not aval.is_file():raise FileNotFoundError(str(aval))
    if geo is not None and not geo.is_file():raise FileNotFoundError(str(geo))
    cols=['NU_NOTA_AV1','NU_NOTA_AV2',*ind22.STATUS_COLS]
    cols=(['NU_INSCRICAO','NU_ANO'] if geo else ['SG_UF_PROVA'])+cols
    base.validar_cabecalho(aval,tuple(cols))
    counters={u:Counter() for u in ('BR',*UFS)}
    counts={'linhas_fonte':0,'n_pop_evaluator':0,'n_pares_status':0,'n_ausentes':0}
    db=None
    try:
        if geo is not None:
            db=sqlite3.connect(tmpdir/f'ind023_geo_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            counts['registros_geografia']=base.construir_geo(db,geo,ano,bloco)
        for df in base.ler_blocos(aval,cols,bloco):
            counts['linhas_fonte']+=len(df)
            if db is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any() or df['NU_ANO'].str.strip().ne(str(ano)).any():
                    raise ValueError(f'{ano}: NU_INSCRICAO/NU_ANO inválido')
                try:db.executemany('INSERT INTO vistos VALUES (?)',((v,) for v in keys.tolist()))
                except sqlite3.IntegrityError as exc:raise ValueError(f'{ano}: inscrição duplicada') from exc
            r1=df['NU_NOTA_AV1'].str.strip();r2=df['NU_NOTA_AV2'].str.strip()
            elegiveis=r1.ne('') & r2.ne('')
            if not elegiveis.any():continue
            a1=base.digitos(r1[elegiveis]);a2=base.digitos(r2[elegiveis])
            if not (a1.between(0,1000)&a2.between(0,1000)).all():
                raise ValueError(f'{ano}: nota total preenchida inválida')
            e=df.loc[elegiveis]
            counts['n_pop_evaluator']+=len(e)
            s1,s2,ok=canonizar_status(e,ano)
            counts['n_pares_status']+=int(ok.sum())
            counts['n_ausentes']+=int((~ok).sum())
            if db is None:
                u=e['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            else:
                insc=e['NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY,ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)',((key,i) for i,key in enumerate(insc)))
                    rows=db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g ON l.key=g.key AND g.ano=?',(ano,)).fetchall()
                finally:db.execute('DROP TABLE lote')
                if len(rows)!=len(e):raise ValueError(f'{ano}: junção incompleta para POP_EVALUATOR')
                u=np.empty(len(e),dtype='<U3')
                for i,sigla in rows:u[int(i)]=str(sigla).strip().upper()
            acumular_matriz(counters,u,s1,s2,ok)
        if counts['n_pares_status']!=sum(counters['BR'].values()):
            raise AssertionError('Matriz não fecha com os pares informados')
        if counts['n_pares_status']+counts['n_ausentes']!=counts['n_pop_evaluator']:
            raise AssertionError('Matriz: incompletos não fecham')
        return counters,counts
    finally:
        if db is not None:db.close()


def publicar_matriz(counter,expected):
    """Impede vazamento de pequenas células por complemento: matriz inteira é retida."""
    n=sum(counter.values())
    off=sum(v for (a,b),v in counter.items() if a!=b)
    if n!=expected['n_pares_status_preenchidos'] or off!=expected['n_status_divergentes']:
        raise ValueError('Recontagem da matriz difere do IND-022')
    if any(0<v<MIN_N for v in counter.values()):
        return {'status':'nao_publicada_celulas_raras', 'celulas':[],
                'nota':'Matriz inteira retida para impedir inferência de células pequenas.'}
    return {'status':'ok','celulas':[
                {'status_av1':a,'status_av2':b,'quantidade':int(n)}
                for (a,b),n in sorted(counter.items()) if n>0],
            'nota':'Códigos categóricos originais; interpretar segundo dicionário da respectiva edição.'}


def enriquecer_com_matrizes(raiz,anos,hist,bloco):
    if bloco<1:raise ValueError('Tamanho de bloco inválido')
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    qa={}
    with tempfile.TemporaryDirectory(prefix='ind023_sql_',dir=out) as tmp:
        for p in anos:
            ano=p['ano'];print(f'IND-023 | {ano}: lendo status AV1×AV2...',flush=True)
            counters,diag=contar_matriz_ano(raiz,ano,bloco,Path(tmp))
            qa[str(ano)]=diag
            if diag['n_pop_evaluator']!=p['brasil']['n_pop_evaluator'] or diag['n_pares_status']!=p['brasil']['n_pares_status_preenchidos']:
                raise ValueError(f'{ano}: denominadores diferem do IND-022')
            for uf in ('BR',*UFS):
                publicar=publicar_matriz(counters[uf],obter_recorte(p,uf))
                obter_recorte(p,uf)['matriz_status']=publicar
    hist['brasil']['matriz_status']={'status':'nao_aplicavel_historico',
        'celulas':[],'nota':'Códigos de situação podem mudar entre edições; a matriz histórica não é construída.'}
    for uf in UFS:
        obter_recorte(hist,uf)['matriz_status']=deepcopy(hist['brasil']['matriz_status'])
    return qa


def linhas_csv(anos,historico):
    linhas=[]
    for p in (*anos,historico):
        period=str(p.get('ano','2019-2025'))
        for uf in ('BR',*UFS):
            g=obter_recorte(p,uf)
            linhas.append({'indicador_id':IND,'periodo':period,
               'abrangencia':'BR' if uf=='BR' else 'UF','uf':uf,'populacao':'POP_EVALUATOR',
               **{k:g[k] for k in FIELDS},
               **{k:g[k] for k in ('percentual_divergencia_pop_evaluator',
                                  'percentual_divergencia_pares_comparaveis',
                                  'percentual_cobertura_status',
                                  'percentual_iguais_pares_comparaveis')},
               'status_matriz':g['matriz_status']['status'],'metodo':METODO})
    if len(linhas)!=224:raise AssertionError('CSV: esperadas 224 linhas')
    return linhas


def atualizar_dashboard(ano,d,anos,hist,gerado):
    x=deepcopy(d)
    p=next(p for p in anos if p['ano']==ano)
    ev=x['pages']['evaluators'];ev['status']='partial'
    ev['reason']='IND-020 a IND-023 disponíveis; restantes ainda pendentes'
    ev['status_disagreement']={'indicator_id':IND,'population':'POP_EVALUATOR',
        'method':METODO,'brasil':deepcopy(p['brasil']),'by_uf':deepcopy(p['ufs']),
        'notes':NOTAS}
    x['pages']['temporal']['ind023']={
        'indicator_id':IND,
        'national_by_year':[{'year':p['ano'],**deepcopy(p['brasil'])} for p in anos],
        'period_total':deepcopy(hist['brasil']),
        'period_by_uf':deepcopy(hist['ufs']),
        'note':NOTAS}
    x['pages']['methodology']['ind023']={
        'definition':'Proporção de pares com TP_STATUS_REDACAO_AV1 diferente de TP_STATUS_REDACAO_AV2',
        'population':'POP_EVALUATOR (IND-020)',
        'denominator_main':'n_pop_evaluator',
        'denominator_sensitivity':'n_pares_status_preenchidos',
        'source_indicator':'IND-022, n_criterio_status_divergente',
        'missing_status':'Pares com status incompleto não são contados como iguais nem como divergentes',
        'geography':'SG_UF_PROVA',
        'minimum_group_count':MIN_N,'limitations':NOTAS}
    x['quality']['ind023_validation']={
        'status':'ok','source_indicator':'IND-022',
        'n_pop_evaluator_brasil':p['brasil']['n_pop_evaluator'],
        'n_status_preenchidos_brasil':p['brasil']['n_pares_status_preenchidos'],
        'n_status_divergentes_brasil':p['brasil']['n_status_divergentes'],
        'soma_27_ufs_igual_brasil':True,
        'n_registros_individuais_exportados':0,
        'revisao_academica_pendente':True,'revisao_privacidade_complementar_pendente':True}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso='IND-023: divergência de situação AV1/AV2 sobre POP_EVALUATOR; matriz de situação pode requerer reprocessamento; privacidade e revisão acadêmica pendentes.'
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x


def executar(raiz,modo='agregados',bloco=BLOCO,somente_modulo=False,fonte_ind022=None,sobrescrever=False):
    raiz=Path(raiz).resolve()
    if modo not in ('agregados','matriz'):raise ValueError('Modo desconhecido')
    m22,anos,hist=preparar(raiz,fonte_ind022)
    qa={}
    if modo=='matriz':qa=enriquecer_com_matrizes(raiz,anos,hist,bloco)
    arquivos={}
    jdir=raiz/'outputs'/'json';cdir=raiz/'outputs'/'indicadores'
    if not somente_modulo:
        for ano in ANOS:
            p=jdir/f'dashboard_enem_{ano}.json'
            if not p.is_file():raise FileNotFoundError(f'Dashboard {ano} ausente: {p}')
            d=ler_json(p)
            if d.get('meta',{}).get('year')!=ano or d.get('meta',{}).get('data_status')!='draft':
                raise ValueError(f'Dashboard {ano}: metadados inválidos')
            if d.get('quality',{}).get('ind022_validation',{}).get('status')!='ok':
                raise ValueError(f'Dashboard {ano}: IND-022 ainda não integrado')
            fonte_ev=d.get('pages',{}).get('evaluators',{}).get('official_discrepancy',{})
            esperado=next(z for z in anos if z['ano']==ano)
            if fonte_ev.get('indicator_id')!='IND-022':
                raise ValueError(f'Dashboard {ano}: fonte de discrepância ausente/incorreta')
            for uf in ('BR',*UFS):
                original=fonte_ev.get('brasil') if uf=='BR' else next(
                    (z for z in fonte_ev.get('by_uf',[]) if z.get('uf')==uf),None)
                if original is None:
                    raise ValueError(f'Dashboard {ano}/{uf}: recorte IND-022 ausente')
                result=obter_recorte(esperado,uf)
                if (original.get('n_pop_evaluator')!=result['n_pop_evaluator']
                    or original.get('n_criterio_status_divergente')!=result['n_status_divergentes']
                    or original.get('n_status_par_preenchido')!=result['n_pares_status_preenchidos']):
                    raise ValueError(f'Dashboard {ano}/{uf}: contagens IND-022 divergentes do módulo')
            if ('ind023_validation' in d['quality'] or 'status_disagreement' in d['pages']['evaluators']) and not sobrescrever:
                raise ValueError(f'Dashboard {ano}: IND-023 já presente. Use --sobrescrever para atualizar.')
            arquivos[ano]=d
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    linhas=linhas_csv(anos,hist)
    modulo={'meta':{'indicator_id':IND,'module_schema_version':'ind023-module-1.0.0',
       'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
       'generated_at':gerado,'data_status':'draft',
       'source_indicator_files':['IND_022_discrepancia_oficial.json',
                                 'IND_020_diferenca_total_av1_av2.json'],
       'geographic_dimension':'SG_UF_PROVA',
       'population_definition':'POP_EVALUATOR: duas notas totais AV1/AV2 válidas, como IND-020',
       'method':METODO,'matrix_mode':modo,
       'source_qa':qa,'minimum_group_count':MIN_N,
       'publication_status':'draft; revisão acadêmica e privacidade complementar pendentes',
       'notes':NOTAS},
       'indicator':{'id':IND,'name':'Divergência de status AV1×AV2',
          'unit':'percentual','dashboard_json_path':'pages.evaluators.status_disagreement',
          'visualization':'KPI/matriz'},
       'years':anos,'historical':hist,
       'dashboard_files':[f'dashboard_enem_{a}.json' for a in ANOS]}
    json.dumps(modulo,allow_nan=False)
    dashboards={ano:atualizar_dashboard(ano,arquivos[ano],anos,hist,gerado) for ano in arquivos}
    for ano,d in dashboards.items():base.validar_schema(d,raiz)
    jdir.mkdir(parents=True,exist_ok=True);cdir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind023_stage_',dir=raiz/'outputs') as tmp:
        tmp=Path(tmp)
        with (tmp/(ARQUIVO+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';');w.writeheader();w.writerows(linhas)
        base.gravar_json(tmp/(ARQUIVO+'.json'),modulo)
        for ano,d in dashboards.items():base.gravar_json(tmp/f'dashboard_enem_{ano}.json',d)
        with (tmp/(ARQUIVO+'.csv')).open('r',encoding='utf-8-sig',newline='') as f:
            if sum(1 for _ in csv.DictReader(f,delimiter=';'))!=224:
                raise AssertionError('CSV incompleto')
        for name,target in ((ARQUIVO+'.csv',cdir),(ARQUIVO+'.json',jdir),
                            *((f'dashboard_enem_{ano}.json',jdir) for ano in dashboards)):
            os.replace(tmp/name,target/name)
    b2024=next(x for x in anos if x['ano']==2024)['brasil'];histb=hist['brasil']
    print(f'IND-023 CONCLUÍDO | modo={modo} | CSV 224 linhas | dashboards={len(dashboards)}',flush=True)
    print(f'  BR 2024: {b2024["n_status_divergentes"]:,} / {b2024["n_pop_evaluator"]:,} ({b2024["percentual_divergencia_pop_evaluator"]:.6f}%)',flush=True)
    print(f'  Histórico: {histb["n_status_divergentes"]:,} / {histb["n_pop_evaluator"]:,} ({histb["percentual_divergencia_pop_evaluator"]:.6f}%)',flush=True)
    print('  Status draft; não modifica Streamlit; não modifica IND-020/021/022',flush=True)
    return modulo


def main():
    ap=argparse.ArgumentParser(description='IND-023 — Divergência de status AV1×AV2')
    ap.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--modo',choices=['agregados','matriz'],default='agregados')
    ap.add_argument('--bloco',type=int,default=BLOCO)
    ap.add_argument('--somente-modulo',action='store_true',help='Não modificar os dashboards (para auditorias externas)')
    ap.add_argument('--fonte-ind022',type=Path,default=None,help='Arquivo IND-022 modular fora da pasta outputs/json')
    ap.add_argument('--sobrescrever',action='store_true',help='Permitir atualizar dashboards que já contêm IND-023')
    args=ap.parse_args()
    executar(args.raiz,args.modo,args.bloco,args.somente_modulo,args.fonte_ind022,args.sobrescrever)

if __name__=='__main__':main()
