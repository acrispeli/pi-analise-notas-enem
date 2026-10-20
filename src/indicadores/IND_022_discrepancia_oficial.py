#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-022 — Discrepância AV1×AV2 conforme critério do edital ENEM 2024 §14.5.3.

Critérios: |AV1-AV2|>100 na nota total OU alguma |Cj_AV1-Cj_AV2|>80
OU divergência de situação TP_STATUS_REDACAO_AV1/AV2. Limiares são estritos.
Usa POP_EVALUATOR do IND-020 (pares totais válidos), sem presumir valores
para campos faltantes. Lógica de três estados: sim/não/indeterminado.

2019–2024: COMPETENCIAS_REDACAO_ano + UF de MICRODADOS_ENEM_ano,
exceto 2024, que usa PARTICIPANTES_2024; chave NU_INSCRICAO/NU_ANO.
2025: RESULTADOS_2025 contém notas e SG_UF_PROVA na mesma linha.

Executar SOMENTE após IND-021 finalizado e auditado:
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_022_discrepancia_oficial.py

O critério citado é do edital ENEM 2024. Sua aplicação a 2019–2023 e 2025
neste script é uma padronização analítica; não comprova que o texto normativo
específico de cada edição seja idêntico ao do edital de 2024.
"""
from __future__ import annotations
import argparse
import csv
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
import pandas as pd
import IND_020_diferenca_total_av1_av2 as base

ANOS=base.ANOS
UFS=base.UFS
IND='IND-022'
NOME='Discrepância oficial (critério ENEM 2024)'
METODO='regra_edital_2024_total_gt100_ou_comp_gt80_ou_status_divergente'
VERSAO='2.21.0-'+'-'.join(f'ind{i:03d}' for i in range(1,23))
BLOCO=100_000
MIN_N=30
COMP_COLS=tuple(f'NU_NOTA_COMP{i}_AV{j}' for i in range(1,6) for j in (1,2))
STATUS_COLS=('TP_STATUS_REDACAO_AV1','TP_STATUS_REDACAO_AV2')
NOTAS=(
 'Critério operativo do edital ENEM 2024, item 14.5.3: |nota AV1−AV2|>100 '
 'OU qualquer |competência AV1−AV2|>80 OU situação divergente. '
 'Limiares estritos: diferenças exatamente 100 ou 80, isoladamente, '
 'não disparam a regra. Entre 2019–2023 e 2025 trata-se de aplicação '
 'padronizada do critério de 2024, sem certificar identidade normativa '
 'de todos os editais. Denominador POP_EVALUATOR (notas totais AV1 e AV2 '
 'válidas), que difere da população de redações válidas. A ausência '
 'de informação não é interpretada como concordância: há categoria '
 'indeterminada quando nenhum critério foi comprovado e algum '
 'permanece desconhecido. Contagens de motivos podem se sobrepor. '
 'A UF representa o local de prova, não residência. '
 'O histórico reúne participações, não pessoas únicas. '
 'Saída contém apenas agregados e fica em draft até revisão acadêmica '
 'e revisão de privacidade complementar; não é taxa oficial publicada pelo INEP.')

FIELDS=('n_pop_evaluator','n_discrepancia_confirmada','n_sem_discrepancia_confirmada',
        'n_indeterminada','n_criterio_total_gt100','n_criterio_comp_gt80',
        'n_criterio_status_divergente','n_comp_criterio_desconhecido',
        'n_status_criterio_desconhecido','n_comp_cinco_pares_completos',
        'n_status_par_preenchido','n_criterios_multiplos')


def grupos_vazios():
    return {uf:{k:0 for k in FIELDS} for uf in ('BR',*UFS)}


def codificar_status(ser:pd.Series,ano:int,nome:str):
    """Códigos categóricos numéricos; vazios são desconhecidos, não zero."""
    v=ser.str.strip()
    preenchido=v.ne('')
    # Códigos dos dicionários são números inteiros. Comparação por código.
    digit=v.str.fullmatch(r'\d+')
    if (~digit.fillna(False)&preenchido).any():
        raise ValueError(f'{ano}: {nome} tem status não numérico preenchido')
    codigo=v.where(preenchido,'').str.lstrip('0').replace('', '0')
    # Preenchimento é mantido separado de '0' para não confundir faltantes.
    if any(int(x)>999 for x in codigo[preenchido].unique()):
        raise ValueError(f'{ano}: {nome} contém código de situação fora de faixa')
    return codigo.to_numpy(dtype=str),preenchido.to_numpy(dtype=bool)


def calcular_regras(total1:np.ndarray,total2:np.ndarray,comps:np.ndarray,
                    status1:np.ndarray,status2:np.ndarray,
                    status1_ok:np.ndarray,status2_ok:np.ndarray):
    """Retorna máscaras vetoriais; missing = conhecimento insuficiente.

    C pode ser VERDADEIRO mesmo com outros pares de competência ausentes,
    desde que algum par observado já ultrapasse 80. S só se ambos informados.
    """
    n=len(total1)
    if total1.shape!=total2.shape or comps.shape!=(n,10):
        raise AssertionError('Bloco malformado: dimensões AV1/AV2/C1-C5')
    if len(status1)!=n or len(status2)!=n or len(status1_ok)!=n or len(status2_ok)!=n:
        raise AssertionError('Bloco malformado: situações')
    t=np.abs(total1-total2)>100
    diffs=np.abs(comps[:,0::2]-comps[:,1::2])
    c=np.any(diffs>80,axis=1)
    c_completo=np.isfinite(diffs).all(axis=1)
    c_desconhecido=~c & ~c_completo
    s_completo=status1_ok & status2_ok
    s=(status1!=status2) & s_completo
    s_desconhecido=~s_completo
    sim=t|c|s
    indef=(~sim)&(c_desconhecido|s_desconhecido)
    nao=(~sim)&(~indef)
    assert np.all((sim.astype(int)+nao.astype(int)+indef.astype(int))==1)
    return {'sim':sim,'nao':nao,'indef':indef,'t':t,'c':c,'s':s,
            'c_desconhecido':c_desconhecido,'s_desconhecido':s_desconhecido,
            'c_completo':c_completo,'s_completo':s_completo,
            'multi':t.astype(int)+c.astype(int)+s.astype(int)>=2}


def acumular(grupos,ufs,flags):
    if not len(ufs):return
    if not np.isin(ufs,UFS).all():raise ValueError('UF ausente ou desconhecida em POP_EVALUATOR')
    campos={'n_discrepancia_confirmada':'sim','n_sem_discrepancia_confirmada':'nao',
            'n_indeterminada':'indef','n_criterio_total_gt100':'t',
            'n_criterio_comp_gt80':'c','n_criterio_status_divergente':'s',
            'n_comp_criterio_desconhecido':'c_desconhecido',
            'n_status_criterio_desconhecido':'s_desconhecido',
            'n_comp_cinco_pares_completos':'c_completo',
            'n_status_par_preenchido':'s_completo',
            'n_criterios_multiplos':'multi'}
    for u in ('BR',*np.unique(ufs)):
        mask=np.ones(len(ufs),dtype=bool) if u=='BR' else ufs==u
        g=grupos[u]
        g['n_pop_evaluator']+=int(mask.sum())
        for k,f in campos.items():g[k]+=int(np.sum(flags[f][mask]))


def validar_requisitos(raiz:Path):
    j=raiz/'outputs'/'json'
    p20=j/'IND_020_diferenca_total_av1_av2.json'
    p21=j/'IND_021_diferenca_por_competencia.json'
    for p in (p20,p21):
        if not p.is_file():raise FileNotFoundError('Execute e valide IND-020 e IND-021 antes do IND-022: '+str(p))
    m20=base.ler_json(p20);m21=base.ler_json(p21)
    if m20.get('indicator',{}).get('id')!='IND-020' or m21.get('indicator',{}).get('id')!='IND-021':
        raise ValueError('Dependências IND-020/IND-021 inválidas')
    if len(m20.get('years',[]))!=7 or len(m21.get('years',[]))!=7:
        raise ValueError('Dependências sem sete anos')
    originais={}
    for ano in ANOS:
        p=j/f'dashboard_enem_{ano}.json'
        if not p.is_file():raise FileNotFoundError(str(p))
        d=base.ler_json(p)
        if d.get('meta',{}).get('year')!=ano or d.get('meta',{}).get('data_status')!='draft':
            raise ValueError(f'{ano}: metadados do dashboard inválidos')
        if d.get('quality',{}).get('ind021_validation',{}).get('status')!='ok':
            raise ValueError(f'{ano}: aguarde IND-021 integrar o dashboard')
        if 'ind022_validation' in d['quality'] or 'official_discrepancy' in d.get('pages',{}).get('evaluators',{}):
            raise ValueError(f'{ano}: IND-022 já executado, não sobrescrever')
        for k in ('evaluators','temporal','methodology'):
            if not isinstance(d.get('pages',{}).get(k),dict):
                raise ValueError(f'{ano}: página {k} ausente')
        originais[ano]=d
        geo,aval=base.fonte_ano(raiz,ano)
        for x in (geo,aval):
            if x is not None and not x.is_file():raise FileNotFoundError(str(x))
    return m20,m21,originais


def processar_ano(raiz:Path,ano:int,grupos,historico,bloco:int,tmp:Path):
    geo,p=base.fonte_ano(raiz,ano)
    campos=['NU_NOTA_AV1','NU_NOTA_AV2',*COMP_COLS,*STATUS_COLS]
    campos=(['SG_UF_PROVA'] if geo is None else ['NU_INSCRICAO','NU_ANO'])+campos
    base.validar_cabecalho(p,tuple(campos))
    qa={'n_fonte':0,'n_fora_pop_evaluator':0,'n_pop_evaluator':0,
        'n_elegiveis_sem_join':0,'n_elegiveis_sem_uf':0,
        'n_comp_preenchidas_invalidas':0,'n_status_preenchidos_invalidos':0,
        'arquivo_avaliacoes':p.name,'arquivo_uf':(geo or p).name,
        'join':'NU_INSCRICAO_NU_ANO' if geo else 'SG_UF_PROVA_mesma_linha'}
    db=None
    try:
        if geo is not None:
            db=sqlite3.connect(tmp/f'ind022_geo_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['n_geografia']=base.construir_geo(db,geo,ano,bloco)
        print(f'IND-022 | {ano}: calculando discrepância AV1/AV2...',flush=True)
        for df in base.ler_blocos(p,campos,bloco):
            qa['n_fonte']+=len(df)
            if db is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any() or df['NU_ANO'].str.strip().ne(str(ano)).any():
                    raise ValueError(f'{ano}: chave de inscrição/ano inválida')
                try:db.executemany('INSERT INTO vistos VALUES (?)',((v,) for v in keys.tolist()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f'{ano}: inscrição duplicada no arquivo de avaliações') from exc
            av1=base.digitos(df['NU_NOTA_AV1'])
            av2=base.digitos(df['NU_NOTA_AV2'])
            validas1=df['NU_NOTA_AV1'].str.strip().ne('')
            validas2=df['NU_NOTA_AV2'].str.strip().ne('')
            tem_ambas=validas1&validas2
            if (((~av1[tem_ambas].between(0,1000))|(~av2[tem_ambas].between(0,1000))).any()):
                raise ValueError(f'{ano}: nota total AV1/AV2 preenchida inválida')
            qa['n_fora_pop_evaluator']+=int((~tem_ambas).sum())
            if not tem_ambas.any():continue
            e=df.loc[tem_ambas]
            n=len(e);qa['n_pop_evaluator']+=n
            raw=e[list(COMP_COLS)].apply(lambda x:x.str.strip())
            num=np.column_stack([base.digitos(raw[c]).to_numpy(dtype=float) for c in COMP_COLS])
            txt=raw.to_numpy()
            invalidas=((~np.isfinite(num))&(txt!=''))|(np.isfinite(num)&((num<0)|(num>200)))
            if np.any(invalidas):
                qa['n_comp_preenchidas_invalidas']+=int(np.sum(np.any(invalidas,axis=1)))
                raise ValueError(f'{ano}: competência preenchida inválida')
            # Não imputar zero em campos vazios: NA mantém situação desconhecida.
            s1,v1=codificar_status(e[STATUS_COLS[0]],ano,STATUS_COLS[0]);s2,v2=codificar_status(e[STATUS_COLS[1]],ano,STATUS_COLS[1])
            t1=av1[tem_ambas].to_numpy(dtype=float)
            t2=av2[tem_ambas].to_numpy(dtype=float)
            flags=calcular_regras(t1,t2,num,s1,s2,v1,v2)
            if geo is None:
                uf=e['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            else:
                insc=e['NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY, ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)',((v,i) for i,v in enumerate(insc)))
                    pares=db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g ON g.key=l.key AND g.ano=?',(ano,)).fetchall()
                finally:
                    db.execute('DROP TABLE lote')
                if len(pares)!=n:
                    qa['n_elegiveis_sem_join']+=n-len(pares)
                    raise ValueError(f'{ano}: faltam {n-len(pares)} UFs na junção por inscrição')
                uf=np.empty(n,dtype='<U3')
                for i,u in pares:uf[int(i)]=str(u).strip().upper()
            if not np.isin(uf,UFS).all():
                qa['n_elegiveis_sem_uf']+=int(np.sum(~np.isin(uf,UFS)))
                raise ValueError(f'{ano}: UF inválida em POP_EVALUATOR')
            acumular(grupos,uf,flags);acumular(historico,uf,flags)
        if qa['n_fonte']!=qa['n_fora_pop_evaluator']+qa['n_pop_evaluator']:
            raise AssertionError(f'{ano}: população não fecha com a fonte')
        if qa['n_pop_evaluator']!=grupos['BR']['n_pop_evaluator']:
            raise AssertionError(f'{ano}: avaliações pareadas não fecham')
        if sum(grupos[u]['n_pop_evaluator'] for u in UFS)!=grupos['BR']['n_pop_evaluator']:
            raise AssertionError(f'{ano}: soma UF diferente do Brasil')
        print(f'  n elegíveis={qa["n_pop_evaluator"]:,} | discrepâncias confirmadas={grupos["BR"]["n_discrepancia_confirmada"]:,} | indeterminadas={grupos["BR"]["n_indeterminada"]:,}',flush=True)
        return qa
    finally:
        if db is not None:db.close()


def resumo(g:dict):
    n=g['n_pop_evaluator'];sim=g['n_discrepancia_confirmada']
    nao=g['n_sem_discrepancia_confirmada'];inc=g['n_indeterminada']
    if n<MIN_N:raise ValueError(f'Grupo POP_EVALUATOR inferior a {MIN_N}: {n}')
    if n!=sim+nao+inc:raise AssertionError('Partição sim/não/indeterminado não fecha')
    if any(g[k]>n or g[k]<0 for k in g):raise AssertionError('Contagem inválida')
    if any(g[k]>sim for k in ('n_criterio_total_gt100','n_criterio_comp_gt80','n_criterio_status_divergente','n_criterios_multiplos')):
        raise AssertionError('Motivos excedem casos confirmados')
    determ=sim+nao
    return {**g,'n_classificaveis':determ,
       'percentual_discrepancia_confirmada_pop_evaluator':round(100*sim/n,6),
       'percentual_sem_discrepancia_confirmada_pop_evaluator':round(100*nao/n,6),
       'percentual_indeterminada_pop_evaluator':round(100*inc/n,6),
       'percentual_discrepancia_nos_classificaveis':round(100*sim/determ,6) if determ else None,
       'limite_inferior_discrepancia_pct':round(100*sim/n,6),
       'limite_superior_discrepancia_pct':round(100*(sim+inc)/n,6),
       'populacao':'POP_EVALUATOR','sem_dados_individuais':True}


def periodo(ano,grupos,qa=None):
    br=resumo(grupos['BR'])
    ufs=[{'uf':uf,**resumo(grupos[uf])} for uf in UFS]
    for k in FIELDS:
        if sum(x[k] for x in ufs)!=br[k]:raise AssertionError(f'{ano}: UFs não fecham {k}')
    result={'brasil':br,'ufs':ufs,'qualidade':{'status':'ok',
       'soma_27_ufs_igual_brasil':True,'min_group_n':MIN_N,
       'particao_sim_nao_indeterminado':True,'motivos_nao_exclusivos':True}}
    if isinstance(ano,int):result.update({'ano':ano,'qualidade_fonte':qa})
    else:result.update({'periodo':'2019-2025','qualidade_fonte':{'participacoes_nao_pessoas':True}})
    return result


def csv_linhas(anos,historico):
    out=[]
    for p in (*anos,historico):
        periodo_=str(p.get('ano','2019-2025'))
        for u,g in [('BR',p['brasil']), *((x['uf'],x) for x in p['ufs'])]:
            row={'indicador_id':IND,'periodo':periodo_,'abrangencia':'BR' if u=='BR' else 'UF',
                 'uf':u,'populacao':'POP_EVALUATOR',**{k:g[k] for k in FIELDS},
                 'n_classificaveis':g['n_classificaveis'],
                 'percentual_discrepancia_confirmada_pop_evaluator':g['percentual_discrepancia_confirmada_pop_evaluator'],
                 'percentual_indeterminada_pop_evaluator':g['percentual_indeterminada_pop_evaluator'],
                 'percentual_discrepancia_nos_classificaveis':g['percentual_discrepancia_nos_classificaveis'],
                 'limite_inferior_discrepancia_pct':g['limite_inferior_discrepancia_pct'],
                 'limite_superior_discrepancia_pct':g['limite_superior_discrepancia_pct'],
                 'metodo':METODO}
            out.append(row)
    if len(out)!=224:raise AssertionError('CSV não tem 224 recortes')
    return out


def dashboard(ano,anos,historico,d,gerado):
    x=deepcopy(d);p=next(p for p in anos if p['ano']==ano)
    ev=x['pages']['evaluators'];ev['status']='partial'
    ev['reason']='IND-020 a IND-022 disponíveis; os demais indicadores de avaliadores ainda pendentes'
    ev['official_discrepancy']={'indicator_id':IND,'population':'POP_EVALUATOR',
       'method':METODO,'brasil':deepcopy(p['brasil']),'by_uf':deepcopy(p['ufs']),
       'notes':NOTAS}
    x['pages']['temporal']['ind022']={
       'indicator_id':IND,'national_by_year':[{'year':z['ano'],**deepcopy(z['brasil'])} for z in anos],
       'period_total':deepcopy(historico['brasil']),'period_by_uf':deepcopy(historico['ufs']),
       'note':NOTAS}
    x['pages']['methodology']['ind022']={
       'definition':'Discrepância segundo o critério do edital ENEM 2024, item 14.5.3.',
       'population':'POP_EVALUATOR',
       'criteria':['abs(NU_NOTA_AV1 - NU_NOTA_AV2) > 100',
           'qualquer abs(NU_NOTA_COMPi_AV1 - NU_NOTA_COMPi_AV2) > 80',
           'TP_STATUS_REDACAO_AV1 != TP_STATUS_REDACAO_AV2, se ambos presentes'],
       'missing_data':'Três resultados: confirmada, não confirmada, indeterminada; motivos não exclusivos',
       'source_files':{'avaliacoes':p['qualidade_fonte']['arquivo_avaliacoes'],
           'geografia':p['qualidade_fonte']['arquivo_uf']},
       'join':p['qualidade_fonte']['join'],
       'normative_scope':'regra ENEM 2024 aplicada analiticamente a 2019–2025',
       'minimum_group_n':MIN_N,'limitations':NOTAS}
    x['quality']['ind022_validation']={'status':'ok','source_indicator':'IND-021',
       'method':METODO,'n_pop_evaluator_brasil':p['brasil']['n_pop_evaluator'],
       'n_confirmadas_brasil':p['brasil']['n_discrepancia_confirmada'],
       'n_indeterminadas_brasil':p['brasil']['n_indeterminada'],
       'soma_27_ufs_igual_brasil':True,'n_registros_individuais_exportados':0,
       'revisao_academica_pendente':True,'revisao_privacidade_complementar_pendente':True}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso='IND-022: discrepância calculada pelo critério do edital de 2024, aplicado aos demais anos para comparabilidade; motivos sobrepostos e casos indeterminados; revisão acadêmica/privacidade pendentes.'
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x


def executar(raiz:Path,bloco:int=BLOCO):
    if bloco<1:raise ValueError('bloco precisa ser >=1')
    m20,m21,originais=validar_requisitos(raiz)
    refs20={p['ano']:p for p in m20['years']}
    refs21={p['ano']:p for p in m21['years']}
    historico=grupos_vazios();periodos=[];qa={}
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ind022_sql_',dir=out) as tmp:
        for ano in ANOS:
            g=grupos_vazios()
            qa[ano]=processar_ano(raiz,ano,g,historico,bloco,Path(tmp))
            for uf in ('BR',*UFS):
                n=g[uf]['n_pop_evaluator']
                g20=refs20[ano]['brasil'] if uf=='BR' else next(x for x in refs20[ano]['ufs'] if x['uf']==uf)
                g21=refs21[ano]['brasil'] if uf=='BR' else next(x for x in refs21[ano]['ufs'] if x['uf']==uf)
                if n!=g20['n_avaliacoes_pareadas'] or n!=g21['n_pop_evaluator']:
                    raise ValueError(f'{ano}/{uf}: POP_EVALUATOR difere dos IND-020/021')
                if g[uf]['n_comp_cinco_pares_completos']!=g21['n_competencias_pareadas']:
                    raise ValueError(f'{ano}/{uf}: cobertura C1-C5 difere do IND-021')
            periodos.append(periodo(ano,g,qa[ano]))
    hist=periodo('2019-2025',historico)
    for uf in ('BR',*UFS):
        g=hist['brasil'] if uf=='BR' else next(x for x in hist['ufs'] if x['uf']==uf)
        m=m20['historical']['brasil'] if uf=='BR' else next(x for x in m20['historical']['ufs'] if x['uf']==uf)
        if g['n_pop_evaluator']!=m['n_avaliacoes_pareadas']:
            raise ValueError(f'Histórico/{uf}: POP_EVALUATOR diverge do IND-020')
        for k in FIELDS:
            if g[k]!=sum((p['brasil'] if uf=='BR' else next(x for x in p['ufs'] if x['uf']==uf))[k] for p in periodos):
                raise AssertionError(f'Histórico/{uf}: {k} não fecha')
    linhas=csv_linhas(periodos,hist)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    dashboards={ano:dashboard(ano,periodos,hist,originais[ano],gerado) for ano in ANOS}
    schemas={base.validar_schema(d,raiz) for d in dashboards.values()}
    modulo={'meta':{
      'indicator_id':IND,'module_schema_version':'ind022-module-1.0.0',
      'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
      'generated_at':gerado,'data_status':'draft',
      'source_files':{str(ano):{'avaliacoes':qa[ano]['arquivo_avaliacoes'],
                               'geografia':qa[ano]['arquivo_uf']} for ano in ANOS},
      'population_definition':'POP_EVALUATOR do IND-020, com 3 estados de classificação',
      'geographic_dimension':'SG_UF_PROVA','method':METODO,
      'source_indicator_files':['IND_020_diferenca_total_av1_av2.json','IND_021_diferenca_por_competencia.json'],
      'normative_reference':'Edital ENEM 2024, item 14.5.3',
      'normative_scope':'Aplicação padronizada do critério 2024 aos anos 2019–2025, sem afirmar identidade normativa por edição',
      'source_qa':{str(a):qa[a] for a in ANOS},
      'publication_status':'draft; revisão acadêmica e privacidade complementar pendentes',
      'notes':NOTAS},
      'indicator':{'id':IND,'name':NOME,'unit':'redacoes_e_percentual',
            'dashboard_json_path':'pages.evaluators.official_discrepancy',
            'visualization':'KPI'},
      'years':periodos,'historical':hist,
      'dashboard_files':[f'dashboard_enem_{a}.json' for a in ANOS]}
    json.dumps(modulo,allow_nan=False)
    csvdir=out/'indicadores';jsondir=out/'json'
    csvdir.mkdir(parents=True,exist_ok=True);jsondir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind022_stage_',dir=out) as tmp:
        td=Path(tmp)
        fn='IND_022_discrepancia_oficial.csv';jn='IND_022_discrepancia_oficial.json'
        with (td/fn).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
            writer.writeheader();writer.writerows(linhas)
        base.gravar_json(td/jn,modulo)
        for ano in ANOS:base.gravar_json(td/f'dashboard_enem_{ano}.json',dashboards[ano])
        with (td/fn).open('r',encoding='utf-8-sig',newline='') as f:
            if sum(1 for _ in csv.DictReader(f,delimiter=';'))!=224:
                raise AssertionError('CSV incompleto')
        if base.ler_json(td/jn)['indicator']['id']!=IND:raise AssertionError('JSON modular inválido')
        for ano in ANOS:
            if base.ler_json(td/f'dashboard_enem_{ano}.json')['quality']['ind022_validation']['status']!='ok':
                raise AssertionError('Dashboard inválido')
        for src,dest in [(fn,csvdir),(jn,jsondir),
                         *((f'dashboard_enem_{a}.json',jsondir) for a in ANOS)]:
            os.replace(td/src,dest/src)
    print('\nIND-022 CONCLUÍDO: CSV, JSON modular e sete dashboards',flush=True)
    print(f'  POP_EVALUATOR no histórico: {hist["brasil"]["n_pop_evaluator"]:,}',flush=True)
    print(f'  Discrepâncias confirmadas: {hist["brasil"]["n_discrepancia_confirmada"]:,}',flush=True)
    print(f'  Indeterminadas: {hist["brasil"]["n_indeterminada"]:,}',flush=True)
    print(f'  Recortes: 224; linhas CSV: {len(linhas)}; schemas: {sorted(schemas)}',flush=True)
    print('  Apenas agregados; status draft; sem alterações no Streamlit',flush=True)


def main():
    ap=argparse.ArgumentParser(description='IND-022 discrepância oficial AV1/AV2 (critério do edital 2024)')
    ap.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--bloco',type=int,default=BLOCO)
    args=ap.parse_args()
    executar(args.raiz.resolve(),args.bloco)

if __name__=='__main__':main()
