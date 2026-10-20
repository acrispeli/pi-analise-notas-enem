#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-020 — Diferença total AV1×AV2 (ENEM 2019–2025).

Fonte exata por período:
  2019–2023: data/raw/{ano}/COMPETENCIAS_REDACAO_{ano}.csv
    JOIN por NU_INSCRICAO+NU_ANO com MICRODADOS_ENEM_{ano}.csv (SG_UF_PROVA).
  2024: COMPETENCIAS_REDACAO_2024.csv JOIN PARTICIPANTES_2024.csv
    por NU_INSCRICAO+NU_ANO. NUNCA juntar com RESULTADOS_2024 (NU_SEQUENCIAL).
  2025: RESULTADOS_2025.csv (UF e notas AV1/AV2 na mesma base).

POP_EVALUATOR: duas notas de avaliadores AV1/AV2 numericamente válidas em
[0,1000], independentemente de TP_STATUS_REDACAO e POP_VALID. Medida:
abs(NU_NOTA_AV1 - NU_NOTA_AV2) em pontos (0..1000).

Exporta contagens por classes adaptativas (todas positivas >=30), média,
mediana, p25/p75/p90, min/máx, desvio padrão populacional ddof=0,
Brasil/27 UFs/anos e histórico independente (participações, não pessoas).
Nenhum NU_INSCRICAO, NU_SEQUENCIAL ou dados individuais são exportados.
As classes podem diferir por recorte após coalescência para privacidade.

Pré-requisito: IND-019 finalizado e todos os dashboards atualizados.
Não executar simultaneamente a outros indicadores que alterem dashboards.
Executar: .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_020_diferenca_total_av1_av2.py
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

ANOS = tuple(range(2019,2026))
UFS = ('AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT',
       'PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO')
IND = 'IND-020'
NOME = 'Diferença total AV1×AV2'
METODO = 'distribuicao_abs_nota_total_av1_av2_pop_evaluator'
VERSAO = '2.19.1-'+'-'.join(f'ind{i:03d}' for i in range(1,21))
MIN_N = 30
BLOCO = 100_000
BASE_BINS = ((0.,0.),(0.,20.),(20.,40.),(40.,60.),(60.,80.),
             (80.,100.),(100.,120.),(120.,160.),(160.,200.),
             (200.,300.),(300.,400.),(400.,600.),(600.,1000.))
NOTAS = ('POP_EVALUATOR requer ambas as notas AV1 e AV2 disponíveis; '
    'não equivale a POP_VALID. Diferença absoluta não identifica avaliadores, '
    'não demonstra erro nem viés individual. Classes de frequência com '
    'coalescência adaptativa para garantir N>=30 nas células positivas; '
    'comparação de histogramas entre recortes requer considerar os limites '
    'das classes. As UFs são da aplicação, não residência. Dados 2019–2024 '
    'do complemento de redação unidos à localização por NU_INSCRICAO e NU_ANO; '
    'RESULTADOS_2024 contém NU_SEQUENCIAL, que NÃO é chave de associação. '
    'Histórico soma participações e não pessoas únicas. status=draft, '
    'revisão acadêmica e de privacidade complementar pendentes.')


def ler_json(p: Path):
    with p.open('r',encoding='utf-8') as f:return json.load(f)


def fonte_ano(raiz:Path,ano:int):
    d=raiz/'data'/'raw'/str(ano)
    if ano<2025:
        geo=d/(f'PARTICIPANTES_{ano}.csv' if ano==2024 else f'MICRODADOS_ENEM_{ano}.csv')
        aval=d/f'COMPETENCIAS_REDACAO_{ano}.csv'
        return geo,aval
    return None,d/'RESULTADOS_2025.csv'


def validar_requisitos(raiz:Path):
    jdir=raiz/'outputs'/'json'
    mod=jdir/'IND_019_qualidade_clustering.json'
    if not mod.is_file():raise FileNotFoundError('Execute e finalize IND-019 antes do IND-020: '+str(mod))
    m19=ler_json(mod)
    if m19.get('indicator',{}).get('id')!='IND-019' or m19.get('meta',{}).get('data_status')!='draft':
        raise ValueError('IND-019 modular inválido')
    dashboards={}
    for ano in ANOS:
        path=jdir/f'dashboard_enem_{ano}.json'
        if not path.is_file():raise FileNotFoundError(str(path))
        d=ler_json(path)
        if d.get('meta',{}).get('year')!=ano or d['meta'].get('data_status')!='draft':
            raise ValueError(f'{ano}: metadados do dashboard inválidos')
        if d.get('quality',{}).get('ind019_validation',{}).get('status')!='ok':
            raise ValueError(f'{ano}: IND-019 ainda não integrado ao dashboard')
        if 'ind020_validation' in d['quality'] or 'total_difference' in d['pages']['evaluators']:
            raise ValueError(f'{ano}: IND-020 já existe: não sobrescrever execução anterior')
        if not isinstance(d['pages'].get('temporal'),dict) or not isinstance(d['pages'].get('methodology'),dict):
            raise ValueError(f'{ano}: estrutura do dashboard incompleta')
        dashboards[ano]=d
    for ano in ANOS:
        geo,aval=fonte_ano(raiz,ano)
        for p in (geo,aval):
            if p is not None and not p.is_file():raise FileNotFoundError(f'Fonte do IND-020 ausente: {p}')
    return dashboards


def codificacao_csv(p:Path)->str:
    """Leitura segura de colunas ASCII em arquivos ENEM UTF-8 BOM/Latin-1.

    As fontes utilizadas aqui contêm APENAS cabeçalhos e valores necessários
    em ASCII (NU_INSCRICAO, NU_ANO, SG_UF_PROVA e NU_NOTA_AV1/AV2).
    Latin-1 é uma decodificação total de bytes para arquivos sem BOM, inclusive
    quando o restante do arquivo contém caracteres CP1252 ou UTF-8; nenhum
    campo textual não ASCII é selecionado, comparado ou exportado.
    """
    with p.open('rb') as f:
        return 'utf-8-sig' if f.read(3)==b'\xef\xbb\xbf' else 'latin-1'


def ler_blocos(p:Path,colunas:list[str],bloco:int):
    return pd.read_csv(p,sep=';',dtype=str,usecols=colunas,keep_default_na=False,
        na_filter=False,encoding=codificacao_csv(p),encoding_errors='strict',
        on_bad_lines='error',chunksize=bloco)


def validar_cabecalho(p:Path,campos:tuple[str,...]):
    with p.open('r',encoding=codificacao_csv(p),newline='') as f:
        nomes=next(csv.reader(f,delimiter=';'))
    falta=set(campos)-set(nomes)
    if falta:raise ValueError(f'{p.name}: faltam colunas {sorted(falta)}')
    if len(nomes)!=len(set(nomes)):raise ValueError(f'{p.name}: cabeçalhos duplicados')


def digitos(ser:pd.Series)->pd.Series:
    return pd.to_numeric(ser.str.strip().str.replace(',','.',regex=False),errors='coerce')


class Acumulador:
    __slots__=('n','soma','soma2','min','max','freq')
    def __init__(self):
        self.n=0;self.soma=0.;self.soma2=0.
        self.min=math.inf;self.max=-math.inf;self.freq=Counter()
    def add(self,valores):
        x=np.asarray(valores,dtype=np.float64)
        if not len(x):return
        if not np.isfinite(x).all() or (x<0).any() or (x>1000).any():
            raise ValueError('Diferença AV1/AV2 inválida')
        x=np.round(x,8) # evita chaves de floats espúrias; notas de origem mantidas
        self.n+=len(x);self.soma+=float(x.sum());self.soma2+=float(np.dot(x,x))
        self.min=min(self.min,float(np.min(x)));self.max=max(self.max,float(np.max(x)))
        valores,counts=np.unique(x,return_counts=True)
        self.freq.update({float(v):int(n) for v,n in zip(valores,counts)})
    def quantil(self,q:float):
        if not self.n:return None
        h=(self.n-1)*q
        lo=int(math.floor(h));hi=int(math.ceil(h));alfa=h-lo
        # Recalcular diretamente as estatísticas de ordem, sem arrays individuais.
        def order_at(idx):
            total=0
            for v,c in sorted(self.freq.items()):
                total+=c
                if total>idx:return v
            raise AssertionError('Percentil fora da distribuição')
        a=order_at(lo);b=order_at(hi)
        return round(a*(1-alfa)+b*alfa,6)
    def merge(self,out:'Acumulador'):
        out.n+=self.n;out.soma+=self.soma;out.soma2+=self.soma2
        out.min=min(out.min,self.min);out.max=max(out.max,self.max)
        out.freq.update(self.freq)


def histograma(a:Acumulador)->list[dict]:
    if a.n<MIN_N:raise ValueError(f'POP_EVALUATOR n={a.n} inferior a {MIN_N}')
    # (low,high,count), primeiro intervalo contém apenas zero, demais (low,high].
    bases=[]
    for i,(lo,hi) in enumerate(BASE_BINS):
        c=sum(n for v,n in a.freq.items() if ((v==0) if i==0 else (lo<v<=hi)))
        bases.append([lo,hi,c,i==0])
    if sum(b[2] for b in bases)!=a.n:raise AssertionError('Classes não cobrem a população')
    # Combina classes adjacentes até não restar célula positiva com n<30.
    # Também combina zeros isolados para evitar interpretações enganosas.
    i=0
    while i<len(bases):
        if 0<bases[i][2]<MIN_N:
            if len(bases)==1:raise ValueError('Não é possível proteger célula')
            if i<len(bases)-1:
                bases[i:i+2]=[[bases[i][0],bases[i+1][1],bases[i][2]+bases[i+1][2],bases[i][3] or bases[i+1][3]]]
            else:
                bases[i-1:i+1]=[[bases[i-1][0],bases[i][1],bases[i-1][2]+bases[i][2],bases[i-1][3] or bases[i][3]]]
                i=max(0,i-1)
        else:i+=1
    # Classes de zero com valor 0 são omitidas para não expandir payload.
    bins=[]
    for lo,hi,c,incl_zero in bases:
        if not c:continue
        exato=(lo==hi==0)
        bins.append({'limite_inferior':lo,'limite_superior':hi,
            'inferior_inclusivo':incl_zero,
            'superior_inclusivo':True,
            'faixa':'0' if exato else f'{lo:g}–{hi:g}',
            'n_redacoes':int(c),'proporcao':round(c/a.n,10),
            'percentual':round(c/a.n*100,6)})
    if sum(x['n_redacoes'] for x in bins)!=a.n or any(0<x['n_redacoes']<MIN_N for x in bins):
        raise AssertionError('Falha de supressão adaptativa')
    return bins


def resumo(a:Acumulador)->dict:
    if a.n<MIN_N:raise ValueError(f'POP_EVALUATOR n={a.n} inferior ao limiar {MIN_N}')
    v=max(0.,a.soma2/a.n-(a.soma/a.n)**2)
    bins=histograma(a)
    return {'n_avaliacoes_pareadas':a.n,'populacao':'POP_EVALUATOR',
        'metrica':'abs(NU_NOTA_AV1 - NU_NOTA_AV2)',
        'media':round(a.soma/a.n,6),'mediana':a.quantil(0.5),
        'p25':a.quantil(0.25),'p75':a.quantil(0.75),'p90':a.quantil(0.9),
        'desvio_padrao':round(math.sqrt(v),6),'ddof':0,
        'minimo':a.min,'maximo':a.max,
        'n_classes_histograma':len(bins),'soma_histograma':sum(b['n_redacoes'] for b in bins),
        'classes_variaveis_por_privacidade':True,
        'histograma':bins,'sem_dados_individuais':True}


def iniciar_grupos():return {uf:Acumulador() for uf in ('BR',*UFS)}


def adicionar_grupos(grupos:dict,uf:np.ndarray,notas:np.ndarray,ano:str):
    if len(uf)!=len(notas):raise AssertionError('UF/nota comprimentos diferentes')
    if not len(notas):return
    invalid=~np.isin(uf,UFS)
    if invalid.any():raise ValueError(f'{ano}: UF desconhecida para redação com AV1 e AV2')
    grupos['BR'].add(notas)
    for u in np.unique(uf):
        grupos[u].add(notas[uf==u])


def construir_geo(db:sqlite3.Connection,p:Path,ano:int,bloco:int)->int:
    validar_cabecalho(p,('NU_INSCRICAO','NU_ANO','SG_UF_PROVA'))
    db.execute('CREATE TABLE geo (key TEXT PRIMARY KEY, uf TEXT NOT NULL, ano INTEGER NOT NULL) WITHOUT ROWID')
    db.execute('CREATE TABLE vistos (key TEXT PRIMARY KEY) WITHOUT ROWID')
    n=0
    for df in ler_blocos(p,['NU_INSCRICAO','NU_ANO','SG_UF_PROVA'],bloco):
        key=df['NU_INSCRICAO'].str.strip()
        year=df['NU_ANO'].str.strip()
        uf=df['SG_UF_PROVA'].str.strip().str.upper()
        if key.eq('').any() or year.ne(str(ano)).any():
            raise ValueError(f'{ano}: chave/NU_ANO irregular na base geográfica')
        rows=list(zip(key.tolist(),uf.tolist(),[ano]*len(df)))
        try:db.executemany('INSERT INTO geo VALUES (?,?,?)',rows)
        except sqlite3.IntegrityError as e:raise ValueError(f'{ano}: NU_INSCRICAO repetido na base geográfica') from e
        n+=len(df)
    db.commit()
    return n


def processar_ano(raiz:Path,ano:int,grupos:dict,historico:dict,bloco:int,tmpdir:Path)->dict:
    geo,ava=fonte_ano(raiz,ano)
    cols=['NU_NOTA_AV1','NU_NOTA_AV2']
    if geo is not None:cols=['NU_INSCRICAO','NU_ANO',*cols]
    else:cols=['SG_UF_PROVA',*cols]
    validar_cabecalho(ava,tuple(cols))
    qa={'arquivo_avaliadores':ava.name,'arquivo_uf':geo.name if geo else ava.name,
        'metodo_uf':'join_por_NU_INSCRICAO_NU_ANO' if geo else 'mesma_linha_RESULTADOS_2025',
        'total_registros_avaliadores':0,'n_uma_ou_duas_notas_ausentes':0,
        'n_ambas_notas_preenchidas':0,'n_notas_invalidas':0,
        'n_avaliacoes_pareadas':0,'n_sem_uf_no_elegivel':0,'n_sem_juncao_no_elegivel':0}
    db=None
    indice=tmpdir/f'indices_{ano}.sqlite'
    # A criação do índice também deve ficar sob o try/finally: se falhar
    # antes do processamento das notas, a conexão precisa ser fechada no Windows.
    try:
        if geo is not None:
            db=sqlite3.connect(indice)
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['registros_base_uf']=construir_geo(db,geo,ano,bloco)
        print(f'IND-020 | {ano}: lendo {ava.name}...',flush=True)
        for df in ler_blocos(ava,cols,bloco):
            qa['total_registros_avaliadores']+=len(df)
            raw1=df['NU_NOTA_AV1'].str.strip()
            raw2=df['NU_NOTA_AV2'].str.strip()
            filled=raw1.ne('')&raw2.ne('')
            qa['n_uma_ou_duas_notas_ausentes']+=int((~filled).sum())
            qa['n_ambas_notas_preenchidas']+=int(filled.sum())
            a=digitos(raw1[filled]);b=digitos(raw2[filled])
            good=a.notna()&b.notna()&a.between(0,1000)&b.between(0,1000)
            qa['n_notas_invalidas']+=int((~good).sum())
            if not good.all():raise ValueError(f'{ano}: nota AV1/AV2 preenchida mas inválida')
            if db is None:
                siglas=df.loc[filled,'SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
                diferenca=np.abs(a.to_numpy(dtype=np.float64)-b.to_numpy(dtype=np.float64))
            else:
                keys=df['NU_INSCRICAO'].str.strip()
                year=df['NU_ANO'].str.strip()
                if keys.eq('').any() or year.ne(str(ano)).any():
                    raise ValueError(f'{ano}: NU_INSCRICAO/NU_ANO irregular em {ava.name}')
                try:db.executemany('INSERT INTO vistos VALUES (?)',[(v,) for v in keys.tolist()])
                except sqlite3.IntegrityError as e:raise ValueError(f'{ano}: NU_INSCRICAO duplicado no complemento') from e
                if not int(filled.sum()):continue
                eleg=list(zip(keys.loc[filled].tolist(),a.tolist(),b.tolist()))
                db.execute('CREATE TEMP TABLE lotes (key TEXT PRIMARY KEY, av1 REAL, av2 REAL) WITHOUT ROWID')
                db.executemany('INSERT INTO lotes VALUES (?,?,?)',eleg)
                # O INNER JOIN não é aceito silenciosamente: comparamos o número de linhas retornadas.
                rows=db.execute('SELECT l.av1,l.av2,g.uf FROM lotes l JOIN geo g ON l.key=g.key AND g.ano=?',(ano,)).fetchall()
                db.execute('DROP TABLE lotes')
                if len(rows)!=len(eleg):
                    qa['n_sem_juncao_no_elegivel']+=len(eleg)-len(rows)
                    raise ValueError(f'{ano}: {len(eleg)-len(rows)} registros POP_EVALUATOR sem correspondência geográfica; não descartar')
                if rows:
                    vs=np.asarray(rows,dtype=object)
                    diferenca=np.abs(vs[:,0].astype(np.float64)-vs[:,1].astype(np.float64))
                    siglas=vs[:,2].astype(str)
                else:
                    siglas=np.empty(0,dtype=str);diferenca=np.empty(0,dtype=float)
            if len(siglas):
                if np.any(~np.isin(siglas,UFS)):
                    qa['n_sem_uf_no_elegivel']+=int(np.sum(~np.isin(siglas,UFS)))
                    raise ValueError(f'{ano}: população avaliadores contém UF ausente/desconhecida')
                adicionar_grupos(grupos,siglas,diferenca,str(ano))
                adicionar_grupos(historico,siglas,diferenca,str(ano))
                qa['n_avaliacoes_pareadas']+=len(siglas)
        if db is not None:
            qa['n_distintos_complemento']=db.execute('SELECT count(*) FROM vistos').fetchone()[0]
            qa['n_avaliadores_sem_correspondencia_total']=db.execute(
                'SELECT count(*) FROM vistos v LEFT JOIN geo g ON v.key=g.key WHERE g.key IS NULL').fetchone()[0]
            qa['n_uf_sem_avaliadores_total']=qa['registros_base_uf']-db.execute(
                'SELECT count(*) FROM vistos v JOIN geo g ON v.key=g.key').fetchone()[0]
            # Ausência de correspondência é tolerada apenas para registros FORA de POP_EVALUATOR.
            qa['juncao_100pct_pop_evaluator']=qa['n_sem_juncao_no_elegivel']==0
        if qa['total_registros_avaliadores']!=(qa['n_uma_ou_duas_notas_ausentes']+qa['n_ambas_notas_preenchidas']):
            raise AssertionError('Denominadores inválidos')
        if qa['n_avaliacoes_pareadas']!=qa['n_ambas_notas_preenchidas']:
            raise AssertionError('Notas elegíveis não reconciliadas')
        if sum(grupos[u].n for u in UFS)!=grupos['BR'].n:
            raise AssertionError(f'{ano}: UFs não fecham com Brasil')
        print(f'  POP_EVALUATOR BR={grupos["BR"].n:,} | registros={qa["total_registros_avaliadores"]:,}',flush=True)
        return qa
    finally:
        if db is not None:
            db.close()
            # O diretório temporário externo será removido após o fechamento
            # de todas as conexões; evita WinError 32 em exceções anteriores.


def compilar_periodo(ano:int|str,grupos:dict,qa:dict|None=None):
    br=resumo(grupos['BR']);ufs=[{'uf':u,**resumo(grupos[u])} for u in UFS]
    if sum(v['n_avaliacoes_pareadas'] for v in ufs)!=br['n_avaliacoes_pareadas']:
        raise AssertionError('POP_EVALUATOR UFs != BR')
    o={'brasil':br,'ufs':ufs,'qualidade':{'status':'ok',
       'soma_27_ufs_igual_brasil':True,'celulas_positivas_inferiores_30':0}}
    if isinstance(ano,int):o.update({'ano':ano,'arquivo_fonte':fonte_ano(Path('.'),ano)[1].name,
        'qualidade_fonte':qa})
    else:o.update({'periodo':'2019-2025','qualidade_fonte':{
        'soma_pop_evaluator_7_anos':True,
        'participacoes_nao_pessoas_unicas':True}})
    return o


def linhas_csv(anos:list,historico:dict):
    rows=[]
    for p in (*anos,historico):
        periodo=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*[(v['uf'],v) for v in p['ufs']]]:
            for i,bin_ in enumerate(g['histograma'],start=1):
                rows.append({'indicador_id':IND,'periodo':periodo,
                    'abrangencia':'BR' if uf=='BR' else 'UF','uf':uf,
                    'populacao':'POP_EVALUATOR','n_avaliacoes_pareadas':g['n_avaliacoes_pareadas'],
                    'media':g['media'],'mediana':g['mediana'],
                    'p25':g['p25'],'p75':g['p75'],'p90':g['p90'],
                    'desvio_padrao':g['desvio_padrao'],'ddof':0,
                    'minimo':g['minimo'],'maximo':g['maximo'],
                    'bin_ordem':i,'faixa':bin_['faixa'],
                    'limite_inferior':bin_['limite_inferior'],
                    'limite_superior':bin_['limite_superior'],
                    'inferior_inclusivo':bin_['inferior_inclusivo'],
                    'superior_inclusivo':bin_['superior_inclusivo'],
                    'n_redacoes_bin':bin_['n_redacoes'],
                    'proporcao_bin':bin_['proporcao'],
                    'percentual_bin':bin_['percentual'],'metodo':METODO})
    return rows


def atualizar_dashboard(ano:int,periodos:list,hist:dict,d:dict,gerado:str):
    x=deepcopy(d)
    p=next(v for v in periodos if v['ano']==ano)
    e=x['pages']['evaluators'];e['status']='partial'
    e['reason']='IND-020 disponível; demais indicadores de avaliadores pendentes'
    e['total_difference']={'indicator_id':IND,'population':'POP_EVALUATOR',
        'method':METODO,'brasil':deepcopy(p['brasil']),
        'by_uf':deepcopy(p['ufs']),'note':NOTAS}
    x['pages']['temporal']['ind020']={'indicator_id':IND,
        'national_by_year':[{'year':v['ano'],**deepcopy(v['brasil'])} for v in periodos],
        'period_total':deepcopy(hist['brasil']),
        'period_by_uf':deepcopy(hist['ufs']),
        'note':'Histórico agrega todas as participações elegíveis; frequências calculadas sobre o período completo.'}
    x['pages']['methodology']['ind020']={
        'definition':'Distribuição da diferença absoluta de notas totais entre AV1 e AV2.',
        'population':'POP_EVALUATOR',
        'eligibility':'duas notas totais AV1/AV2 não vazias e válidas em [0,1000]',
        'method':METODO,'source_files':{'geografia':p['qualidade_fonte']['arquivo_uf'],
           'avaliacoes':p['qualidade_fonte']['arquivo_avaliadores']},
        'join':p['qualidade_fonte']['metodo_uf'],
        'difference':'abs(NU_NOTA_AV1-NU_NOTA_AV2)',
        'percentiles':'Hyndman-Fan tipo 7 exato (frequências ponderadas)',
        'sd_ddof':0,'minimum_histogram_positive_cell':MIN_N,
        'histogram_coalescing':'união de classes adjacentes até todas as contagens positivas >=30',
        'limitations':NOTAS}
    x['quality']['ind020_validation']={'status':'ok','method':METODO,
        'population':'POP_EVALUATOR','n_brasil':p['brasil']['n_avaliacoes_pareadas'],
        'soma_27_ufs_igual_brasil':True,'histogramas_fecham':True,
        'celulas_positivas_inferiores_30':0,
        'n_elegiveis_sem_juncao':p['qualidade_fonte']['n_sem_juncao_no_elegivel'],
        'n_notas_invalidas':p['qualidade_fonte']['n_notas_invalidas'],
        'individuos_exportados':0,'revisao_privacidade_pendente':True,
        'metodo_uf':p['qualidade_fonte']['metodo_uf']}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso=('IND-020: diferença absoluta AV1×AV2 usa POP_EVALUATOR, não POP_VALID; '
           '2019–2024 requer junção por NU_INSCRICAO/NU_ANO com fonte geográfica. '
           'Classes de histogramas adaptadas a n>=30; privacidade complementar '
           'e revisão acadêmica pendentes.')
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x


def validar_schema(d:dict,raiz:Path)->str:
    for p in (raiz/'docs'/'04_resultados_analises.schema.json',
              raiz/'docs'/'metodologia'/'04_resultados_analises.schema.json',
              raiz/'04_resultados_analises.schema.json'):
        if p.is_file():
            import jsonschema
            jsonschema.validate(d,ler_json(p));return 'JSON Schema v1.0.0'
    if set(('meta','filters','pages','quality'))-set(d):raise ValueError('Dashboard incompleto')
    return 'estrutura minima sem schema local'


def gravar_json(p:Path,d):
    with p.open('w',encoding='utf-8') as f:
        json.dump(d,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')


def executar(raiz:Path,bloco:int=BLOCO):
    if bloco<1:raise ValueError('bloco precisa ser >=1')
    originais=validar_requisitos(raiz)
    anos=[];historico=iniciar_grupos();qa={}
    with tempfile.TemporaryDirectory(prefix='ind020_sql_',dir=raiz/'outputs') as tmp:
        for ano in ANOS:
            per=iniciar_grupos()
            qa[ano]=processar_ano(raiz,ano,per,historico,bloco,Path(tmp))
            anos.append(compilar_periodo(ano,per,qa[ano]))
    hist=compilar_periodo('2019-2025',historico)
    for uf in ('BR',*UFS):
        nn=sum((p['brasil'] if uf=='BR' else next(v for v in p['ufs'] if v['uf']==uf))['n_avaliacoes_pareadas'] for p in anos)
        hh=hist['brasil'] if uf=='BR' else next(v for v in hist['ufs'] if v['uf']==uf)
        if nn!=hh['n_avaliacoes_pareadas']:raise AssertionError(f'{uf}: histórico diverge dos anos')
    csvrows=linhas_csv(anos,hist)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    dashboards={ano:atualizar_dashboard(ano,anos,hist,originais[ano],gerado) for ano in ANOS}
    checks={validar_schema(d,raiz) for d in dashboards.values()}
    modulo={'meta':{
        'indicator_id':IND,'module_schema_version':'ind020-module-1.0.0',
        'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
        'generated_at':gerado,'data_status':'draft',
        'source_files':{str(ano):{'geografia':qa[ano]['arquivo_uf'],
                                 'avaliadores':qa[ano]['arquivo_avaliadores']} for ano in ANOS},
        'population_definition':'POP_EVALUATOR = AV1 e AV2 totais presentes e válidos em [0,1000]',
        'geographic_dimension':'SG_UF_PROVA',
        'method':METODO,'minimum_positive_cell_count':MIN_N,
        'histogram_bins_base':BASE_BINS,'percentile_type':'Hyndman-Fan tipo 7',
        'source_indicator':'IND-019 (dashboards prévios)',
        'join_diagnostics_by_year':{str(ano):qa[ano] for ano in ANOS},
        'publication_status':'draft; revisão acadêmica e privacidade complementar pendentes',
        'notes':NOTAS},
        'indicator':{'id':IND,'name':NOME,'unit':'pontos',
            'dashboard_json_path':'pages.evaluators.total_difference','visualization':'Histograma/boxplot'},
        'years':anos,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    json.dumps(modulo,allow_nan=False)
    out=raiz/'outputs';csvdir=out/'indicadores';jsondir=out/'json'
    csvdir.mkdir(parents=True,exist_ok=True);jsondir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind020_stage_',dir=out) as tmp:
        td=Path(tmp)
        with (td/'IND_020_diferenca_total_av1_av2.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(csvrows[0]),delimiter=';')
            writer.writeheader();writer.writerows(csvrows)
        gravar_json(td/'IND_020_diferenca_total_av1_av2.json',modulo)
        for ano in ANOS:gravar_json(td/f'dashboard_enem_{ano}.json',dashboards[ano])
        with (td/'IND_020_diferenca_total_av1_av2.csv').open(encoding='utf-8-sig') as f:
            if sum(1 for _ in csv.DictReader(f,delimiter=';'))!=len(csvrows):
                raise AssertionError('CSV incompleto')
        if ler_json(td/'IND_020_diferenca_total_av1_av2.json')['indicator']['id']!=IND:
            raise AssertionError('JSON incompleto')
        for ano in ANOS:
            if ler_json(td/f'dashboard_enem_{ano}.json')['quality']['ind020_validation']['status']!='ok':
                raise AssertionError('Dashboard incompleto')
        for fn,dst in [('IND_020_diferenca_total_av1_av2.csv',csvdir),
                       ('IND_020_diferenca_total_av1_av2.json',jsondir),
                       *[(f'dashboard_enem_{ano}.json',jsondir) for ano in ANOS]]:
            os.replace(td/fn,dst/fn)
    print('\nIND-020 CONCLUÍDO: CSV, JSON modular, 7 dashboards',flush=True)
    print(f'  POP_EVALUATOR nacional histórico: {hist["brasil"]["n_avaliacoes_pareadas"]:,}',flush=True)
    print('  Recortes: 224; linhas CSV:',len(csvrows),' | ', ', '.join(sorted(checks)),flush=True)
    print('  Sem dados individuais, data_status=draft',flush=True)


def main():
    p=argparse.ArgumentParser(description='IND-020: diferenças totais AV1×AV2 (POP_EVALUATOR)')
    p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--bloco',type=int,default=BLOCO)
    opt=p.parse_args()
    executar(opt.raiz.resolve(),opt.bloco)

if __name__=='__main__':main()
