#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-024 | Frequência observada de terceiro avaliador, ENEM 2019–2025.

Regra do catálogo: AV3 = (NU_NOTA_AV3 preenchida) OU
(TP_STATUS_REDACAO_AV3 preenchido), entre POP_ALL.

Uso (na raiz D:\\pi-analise-notas-enem):
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_024_terceiro_avaliador.py
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_024_terceiro_avaliador.py --somente-modulo
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_024_terceiro_avaliador.py --sobrescrever

Os sete CSVs complementares e geográficos originais são necessários. Nenhum
número do AV3 é inventado a partir dos indicadores anteriores. Não utilizar
com outro script que altere dashboards simultaneamente.
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

ANOS=tuple(range(2019,2026))
UFS=tuple(base.UFS)
MIN_N=30
IND='IND-024'
NOME='Terceiro avaliador'
ARQUIVO='IND_024_terceiro_avaliador'
METODO='presenca_nota_ou_status_av3_sobre_pop_all'
VERSAO='2.23.0-'+'-'.join(f'ind{x:03d}' for x in range(1,25))
NOTAS=(
    'Proxy de convocação: nota AV3 ou status AV3 preenchido (OU inclusivo), '
    'contando cada participação uma vez. Não é a razão sobre POP_EVALUATOR, '
    'POP_VALID nem a discrepância oficial do IND-022. Nota zero conta como '
    'preenchida. A presença do campo indica evidência de avaliação AV3, '
    'não comprova o registro administrativo da convocação. UF é de prova. '
    'O histórico agrega participações, não pessoas únicas. Nenhum ID ou '
    'registro individual é exportado. Contagens positivas inferiores a 30 '
    'na medida ou no complemento bloqueiam a publicação do recorte (e a '
    'execução, para impedir reconstruções). Resultados draft, aguardando '
    'revisão metodológica, acadêmica e de privacidade complementar.'
)


def ler_json(path:Path):
    with path.open('r',encoding='utf-8') as f:
        return json.load(f)


def recorte(periodo,uf):
    if uf=='BR':return periodo['brasil']
    return next(v for v in periodo['ufs'] if v['uf']==uf)


def referencias_pop_all(raiz:Path):
    path=raiz/'outputs'/'json'/'IND_007_situacao_redacao.json'
    if not path.is_file():raise FileNotFoundError(f'IND-007 obrigatório para validar POP_ALL: {path}')
    x=ler_json(path)
    if x.get('indicator',{}).get('id')!='IND-007':
        raise ValueError('IND-007 inválido')
    if len(x.get('years',[]))!=len(ANOS) or [v['ano'] for v in x['years']]!=list(ANOS):
        raise ValueError('IND-007 anos incompletos ou fora de ordem')
    pop={}
    for ano,p in zip(ANOS,x['years']):
        br=int(p['brasil']['total_registros'])
        ufs={u:int(recorte(p,u)['total_registros']) for u in UFS}
        if br!=sum(ufs.values()) or br<1:
            raise ValueError(f'IND-007: POP_ALL {ano} não reconcilia com 27 UFs')
        pop[ano]={'BR':br,**ufs}
    for u in ('BR',*UFS):
        if int(recorte(x['historical'],u)['total_registros'])!=sum(pop[ano][u] for ano in ANOS):
            raise ValueError(f'IND-007 histórico POP_ALL {u} não reconcilia')
    return pop


def fontes_ok(raiz:Path):
    for ano in ANOS:
        geo,ava=base.fonte_ano(raiz,ano)
        for path in (geo,ava):
            if path is not None and not path.is_file():
                raise FileNotFoundError(f'Microdados necessários não encontrados: {path}')
        cols=('NU_NOTA_AV3','TP_STATUS_REDACAO_AV3')
        cols=(('NU_INSCRICAO','NU_ANO') if geo else ('SG_UF_PROVA', 'NU_ANO'))+cols
        base.validar_cabecalho(ava,cols)
        if geo is not None:
            base.validar_cabecalho(geo,('NU_INSCRICAO','NU_ANO','SG_UF_PROVA'))


def indicadores_anteriores_ok(raiz:Path):
    j=raiz/'outputs'/'json'
    x=j/'IND_023_divergencia_status.json'
    if not x.is_file() or ler_json(x).get('indicator',{}).get('id')!='IND-023':
        raise ValueError('IND-023 precisa estar integrado antes do IND-024')
    dash={}
    for ano in ANOS:
        p=j/f'dashboard_enem_{ano}.json'
        if not p.is_file():raise FileNotFoundError(str(p))
        d=ler_json(p)
        if d.get('meta',{}).get('year')!=ano or d['meta'].get('data_status')!='draft':
            raise ValueError(f'{ano}: dashboard inválido ou não draft')
        if d.get('quality',{}).get('ind023_validation',{}).get('status')!='ok':
            raise ValueError(f'{ano}: IND-023 não integrado')
        for sec in ('evaluators','methodology','temporal'):
            if not isinstance(d.get('pages',{}).get(sec),dict):
                raise ValueError(f'{ano}: ausência da seção {sec}')
        dash[ano]=d
    return dash


def nota_presente_validar(s:pd.Series,ano:int)->np.ndarray:
    texto=s.str.strip()
    mask=texto.ne('')
    valores=pd.to_numeric(texto[mask].str.replace(',','.',regex=False),errors='coerce')
    if not (valores.notna() & valores.between(0,1000) & np.isfinite(valores.to_numpy(dtype=float))).all():
        raise ValueError(f'{ano}: NU_NOTA_AV3 preenchida fora de [0,1000] ou não numérica')
    return mask.to_numpy(dtype=bool)


def status_presente_validar(s:pd.Series,ano:int)->np.ndarray:
    texto=s.str.strip()
    mask=texto.ne('')
    # O código deve ser inteiro positivo; não inferimos equivalência entre
    # categorias de status de anos diferentes.
    valores=pd.to_numeric(texto[mask].str.replace(',','.',regex=False),errors='coerce')
    if not (valores.notna() & (valores>0) & (valores==np.floor(valores))).all():
        raise ValueError(f'{ano}: TP_STATUS_REDACAO_AV3 preenchido com código inválido')
    return mask.to_numpy(dtype=bool)


def processar_ano(raiz:Path,ano:int,pop:dict[str,int],bloco:int,tmpdir:Path):
    geo,ava=base.fonte_ano(raiz,ano)
    qa={'arquivo_av3':ava.name,'arquivo_geografia':geo.name if geo else ava.name,
        'juncao':'NU_INSCRICAO+NU_ANO' if geo else 'mesma_linha',
        'linhas_fonte':0,'linhas_geografia':None,'n_candidatos_av3':0,
        'n_candidatos_sem_uf':0,'n_candidatos_sem_juncao':0}
    por_uf=Counter()
    uf_fonte_2025=Counter()
    db=None
    try:
        if geo is not None:
            db=sqlite3.connect(tmpdir/f'geo_ind024_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['linhas_geografia']=base.construir_geo(db,geo,ano,bloco)
            if qa['linhas_geografia']!=pop['BR']:
                raise ValueError(f'{ano}: fonte geográfica não cobre POP_ALL de IND-007')
            # O denominador por UF também precisa coincidir com a fonte
            # geográfica, não apenas o total nacional.
            resumo_geo=dict(db.execute('SELECT uf, COUNT(*) FROM geo GROUP BY uf').fetchall())
            if set(resumo_geo)-set(UFS):
                raise ValueError(f'{ano}: UF desconhecida na fonte geográfica')
            for uf in UFS:
                if int(resumo_geo.get(uf,0))!=pop[uf]:
                    raise ValueError(f'{ano}/{uf}: fonte geográfica diverge de POP_ALL IND-007')
        cols=(['NU_INSCRICAO','NU_ANO'] if geo else ['SG_UF_PROVA','NU_ANO'])+[
            'NU_NOTA_AV3','TP_STATUS_REDACAO_AV3']
        print(f'IND-024 | {ano}: {ava.name}',flush=True)
        for df in base.ler_blocos(ava,cols,bloco):
            qa['linhas_fonte']+=len(df)
            if df['NU_ANO'].str.strip().ne(str(ano)).any():
                raise ValueError(f'{ano}: NU_ANO incompatível na fonte AV3')
            n=nota_presente_validar(df['NU_NOTA_AV3'],ano)
            s=status_presente_validar(df['TP_STATUS_REDACAO_AV3'],ano)
            mask=n|s  # união, evita contagem duplicada; zero é nota preenchida
            count=int(mask.sum())
            qa['n_candidatos_av3']+=count
            if geo is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any():raise ValueError(f'{ano}: NU_INSCRICAO vazia na fonte AV3')
                # Detectar inscrições repetidas mesmo entre participantes sem AV3.
                try:
                    db.executemany('INSERT INTO vistos VALUES (?)',((k,) for k in keys.tolist()))
                except sqlite3.IntegrityError as e:
                    raise ValueError(f'{ano}: inscrição repetida na fonte AV3') from e
                if not count:continue
                ids=keys[mask].tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?)',((k,) for k in ids))
                    rows=db.execute('SELECT g.uf,COUNT(*) FROM lote l JOIN geo g ON l.key=g.key AND g.ano=? GROUP BY g.uf',(ano,)).fetchall()
                finally:db.execute('DROP TABLE lote')
                n_encontrados=sum(int(q) for _,q in rows)
                if n_encontrados!=count:
                    qa['n_candidatos_sem_juncao']+=count-n_encontrados
                    raise ValueError(f'{ano}: participantes com AV3 sem correspondência geográfica')
                for uf,q in rows:
                    uf=str(uf).strip().upper()
                    if uf not in UFS:
                        qa['n_candidatos_sem_uf']+=int(q)
                        raise ValueError(f'{ano}: UF inválida no AV3')
                    por_uf[uf]+=int(q)
            else:
                uf_todas=df['SG_UF_PROVA'].str.strip().str.upper()
                for u,q in uf_todas.value_counts().to_dict().items():
                    if u not in UFS:
                        raise ValueError(f'{ano}: UF inválida na fonte, inclusive registros sem AV3')
                    uf_fonte_2025[u]+=int(q)
                uf=uf_todas[mask]
                counts=uf.value_counts().to_dict()
                for u,q in counts.items():
                    if u not in UFS:
                        qa['n_candidatos_sem_uf']+=int(q)
                        raise ValueError(f'{ano}: UF inválida no AV3')
                    por_uf[u]+=int(q)
        if qa['linhas_fonte']!=pop['BR']:
            raise ValueError(f'{ano}: fonte AV3 com {qa["linhas_fonte"]} linhas, POP_ALL IND-007={pop["BR"]}')
        if geo is None:
            for uf in UFS:
                if uf_fonte_2025[uf]!=pop[uf]:
                    raise ValueError(f'{ano}/{uf}: UF da fonte difere de POP_ALL IND-007')
        if sum(por_uf.values())!=qa['n_candidatos_av3']:
            raise AssertionError(f'{ano}: soma UFs do AV3 difere do Brasil')
        for u in UFS:
            if por_uf[u]>pop[u]:
                raise ValueError(f'{ano}/{u}: participantes com AV3 excedem POP_ALL')
        print('  POP_ALL BR={:,} | com AV3={:,} ({:.4f}%)'.format(
            pop['BR'],qa['n_candidatos_av3'],100*qa['n_candidatos_av3']/pop['BR']),flush=True)
        return por_uf,qa
    finally:
        if db is not None:db.close()


def resumo(n:int,marcados:int):
    n=int(n);marcados=int(marcados)
    if n<=0 or not 0<=marcados<=n:
        raise ValueError('Denominador ou numerador de AV3 inválido')
    outros=n-marcados
    # Bloqueia publicação de células pequenas e sua inferência via complemento.
    if 0<marcados<MIN_N or 0<outros<MIN_N:
        raise ValueError(f'Célula pequena detectada: com AV3={marcados}; sem AV3={outros}; N={n}')
    return {'n_pop_all':n,'n_com_av3':marcados,'n_sem_av3':outros,
            'percentual_com_av3':round(marcados*100/n,6),
            'populacao':'POP_ALL', 'criterio':'NU_NOTA_AV3 OU TP_STATUS_REDACAO_AV3 preenchido',
            'sem_dados_individuais':True}


def compilar(ano:int|str,pop:dict[str,int],numeradores:Counter,qa:dict|None=None):
    d={'brasil':resumo(pop['BR'],sum(numeradores[u] for u in UFS)),
       'ufs':[{'uf':u,**resumo(pop[u],numeradores[u])} for u in UFS],
       'qualidade':{'status':'ok','soma_27_ufs_igual_brasil':True,
                   'celulas_positivas_inferiores_30':0}}
    for col in ('n_pop_all','n_com_av3','n_sem_av3'):
        if sum(g[col] for g in d['ufs'])!=d['brasil'][col]:
            raise AssertionError(f'{ano}/{col}: soma UFs diferente de Brasil')
    if isinstance(ano,int):d['ano']=ano;d['qualidade_fonte']=qa
    else:d['periodo']=str(ano)
    return d


def atualizar_dashboard(d:dict,p:dict,anos:list[dict],hist:dict,gerado:str):
    x=deepcopy(d)
    ev=x['pages']['evaluators']
    # Destino exatamente como catálogo ('number'). Detalhamento em chave irmã.
    ev['third_reviewer_rate']=p['brasil']['percentual_com_av3']
    ev['third_reviewer']={'indicator_id':IND,'population':'POP_ALL',
        'brasil':deepcopy(p['brasil']), 'by_uf':deepcopy(p['ufs']),
        'method':METODO,'note':NOTAS}
    ev['status']='partial'
    ev['reason']='IND-020 a IND-024 agregados disponíveis; demais indicadores podem estar pendentes'
    x['pages']['temporal']['ind024']={'indicator_id':IND,'population':'POP_ALL',
        'national_by_year':[{'year':z['ano'],**deepcopy(z['brasil'])} for z in anos],
        'period_total':deepcopy(hist['brasil']),'period_by_uf':deepcopy(hist['ufs']),
        'note':'Taxa histórica é ponderada pelos registros POP_ALL, não média simples dos percentuais.'}
    x['pages']['methodology']['ind024']={
        'definition':'Frequência observada de campos do terceiro avaliador (AV3) preenchidos.',
        'population':'POP_ALL','denominator':'todos os registros por ano/UF, conforme IND-007',
        'numerator':'NU_NOTA_AV3 preenchida OU TP_STATUS_REDACAO_AV3 preenchido',
        'method':METODO,'join':'NU_INSCRICAO+NU_ANO em 2019-2024; fonte conjunta em 2025',
        'geography':'SG_UF_PROVA (UF de aplicação)',
        'minimum_positive_cell_count':MIN_N,'limitations':NOTAS}
    x['quality']['ind024_validation']={
        'status':'ok','source_indicator':'IND-007',
        'n_pop_all_brasil':p['brasil']['n_pop_all'],
        'n_av3_brasil':p['brasil']['n_com_av3'],
        'soma_27_ufs_igual_brasil':True,'fonte_linhas_igual_pop_all':True,
        'n_sem_juncao_av3':p['qualidade_fonte']['n_candidatos_sem_juncao'],
        'n_registros_individuais_exportados':0,'revisao_academica_pendente':True,
        'revisao_privacidade_complementar_pendente':True}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso=('IND-024: taxa de AV3 é preenchimento de nota OU status do terceiro avaliador '
           'dividido por POP_ALL (IND-007), não POP_EVALUATOR; revisão acadêmica e '
           'privacidade complementar pendentes.')
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x


def validar_dashboard(x:dict,ano:int,raiz:Path):
    if x.get('meta',{}).get('year')!=ano or x['meta'].get('data_status')!='draft':
        raise ValueError('Dashboard modificado inválido')
    for p in (raiz/'04_resultados_analises.schema.json',
              raiz/'docs'/'04_resultados_analises.schema.json'):
        if p.is_file():
            try:
                import jsonschema
            except ImportError:
                print('Aviso: jsonschema não instalado, validada apenas estrutura básica.')
                break
            jsonschema.validate(x,ler_json(p));break


def escrever_json(path:Path,x):
    with path.open('w',encoding='utf-8') as f:
        json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
        f.write('\n')


def executar(raiz:Path,bloco:int=100_000,somente_modulo:bool=False,sobrescrever:bool=False):
    if bloco<1:raise ValueError('bloco deve ser positivo')
    pop=referencias_pop_all(raiz)
    fontes_ok(raiz)
    dashboards={} if somente_modulo else indicadores_anteriores_ok(raiz)
    out=raiz/'outputs';j=out/'json';c=out/'indicadores'
    destinos=[j/f'{ARQUIVO}.json',c/f'{ARQUIVO}.csv']
    if not somente_modulo:destinos.extend(j/f'dashboard_enem_{ano}.json' for ano in ANOS)
    if not sobrescrever:
        # Bloqueio apenas para IND-024; os dashboards existentes têm de existir.
        for p in destinos[:2]:
            if p.exists():raise FileExistsError(f'IND-024 já existe: {p}. Use --sobrescrever se apropriado.')
        for ano,d in dashboards.items():
            if 'ind024_validation' in d.get('quality',{}) or 'third_reviewer_rate' in d['pages']['evaluators']:
                raise FileExistsError(f'IND-024 já integrado em {ano}; --sobrescrever necessário')
    anos=[];soma=Counter();qa_anos={}
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ind024_geo_',dir=out) as tmp:
        for ano in ANOS:
            numerador,qa=processar_ano(raiz,ano,pop[ano],bloco,Path(tmp))
            for u in UFS:soma[u]+=numerador[u]
            anos.append(compilar(ano,pop[ano],numerador,qa))
            qa_anos[str(ano)]=qa
    pop_h={u:sum(pop[y][u] for y in ANOS) for u in ('BR',*UFS)}
    hist=compilar('2019-2025',pop_h,soma)
    for u in ('BR',*UFS):
        for field in ('n_pop_all','n_com_av3','n_sem_av3'):
            if recorte(hist,u)[field]!=sum(recorte(p,u)[field] for p in anos):
                raise AssertionError(f'Histórico inconsistente: {u}/{field}')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    modulo={'meta':{'indicator_id':IND,'module_schema_version':'ind024-module-1.0.0',
        'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
        'generated_at':gerado,'data_status':'draft','source_indicator':'IND-007',
        'population_definition':'POP_ALL: todos os registros dos resultados',
        'geographic_dimension':'SG_UF_PROVA','method':METODO,'minimum_group_count':MIN_N,
        'source_qa':qa_anos,'publication_status':'draft; revisão acadêmica e privacidade complementar pendentes',
        'notes':NOTAS},
        'indicator':{'id':IND,'name':NOME,'unit':'percentual',
                     'dashboard_json_path':'pages.evaluators.third_reviewer_rate',
                     'visualization':'KPI'},
        'years':anos,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    novos={ano:atualizar_dashboard(dashboards[ano],anos[i],anos,hist,gerado)
           for i,ano in enumerate(ANOS)} if not somente_modulo else {}
    for ano,d in novos.items():validar_dashboard(d,ano,raiz)
    linhas=[]
    for p in (*anos,hist):
        periodo=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*((z['uf'],z) for z in p['ufs'])]:
            linhas.append({'indicador_id':IND,'periodo':periodo,'abrangencia':'BR' if uf=='BR' else 'UF',
                'uf':uf,'populacao':'POP_ALL','n_pop_all':g['n_pop_all'],
                'n_com_av3':g['n_com_av3'],'n_sem_av3':g['n_sem_av3'],
                'percentual_com_av3':g['percentual_com_av3'],'metodo':METODO})
    if len(linhas)!=224:raise AssertionError('IND-024: esperado 224 recortes')
    json.dumps(modulo,allow_nan=False)
    # Preparar integralmente antes de substituir qualquer destino.
    with tempfile.TemporaryDirectory(prefix='.ind024_stage_',dir=out) as tmp:
        td=Path(tmp)
        arquivo_json=td/f'{ARQUIVO}.json';arquivo_csv=td/f'{ARQUIVO}.csv'
        escrever_json(arquivo_json,modulo)
        with arquivo_csv.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
            w.writeheader();w.writerows(linhas)
        gravacoes=[(arquivo_json,destinos[0]),(arquivo_csv,destinos[1])]
        for ano,d in novos.items():
            origem=td/f'dashboard_enem_{ano}.json'
            escrever_json(origem,d)
            gravacoes.append((origem,j/origem.name))
        for origem,destino in gravacoes:
            destino.parent.mkdir(parents=True,exist_ok=True)
            os.replace(origem,destino)
    print(f'IND-024 concluído: {len(linhas)} recortes | BR histórico '
          f'N={hist["brasil"]["n_pop_all"]:,} | AV3={hist["brasil"]["n_com_av3"]:,} '
          f'({hist["brasil"]["percentual_com_av3"]:.4f}%)',flush=True)
    print('Saídas: '+str(destinos[0])+' | '+str(destinos[1]),flush=True)
    if not somente_modulo:print('Sete dashboards atualizados somente com blocos do IND-024.',flush=True)
    return modulo


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path.cwd(),help='raiz do projeto')
    ap.add_argument('--bloco',type=int,default=100_000,help='linhas por bloco')
    ap.add_argument('--somente-modulo',action='store_true',help='não alterar dashboards cumulativos')
    ap.add_argument('--sobrescrever',action='store_true',help='autoriza substituir saídas IND-024 existentes')
    args=ap.parse_args()
    executar(args.base.resolve(),args.bloco,args.somente_modulo,args.sobrescrever)

if __name__=='__main__':main()
