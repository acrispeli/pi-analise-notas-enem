#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-026 — Concordância ordinal AV1 × AV2 por competência, ENEM 2019–2025.

Kappa de Cohen ponderado QUADRATICAMENTE, calculado exatamente por momentos
suficientes de todas as participações completas da POP_EVALUATOR.

Fontes: 2019–2023 COMPLEMENTO COMPETENCIAS_REDACAO_AAAA.csv +
MICRODADOS_ENEM_AAAA.csv; 2024 COMPETENCIAS_REDACAO_2024.csv +
PARTICIPANTES_2024.csv; 2025 RESULTADOS_2025.csv.

Requer execução anterior de IND-021 para cotejar população pareada e,
para integrar dashboards, IND-025 concluído. NÃO execute em paralelo
com outros indicadores que modifiquem os mesmos dashboards.

Comandos, na raiz do projeto:
  python src/indicadores/IND_026_concordancia_competencias.py
  python src/indicadores/IND_026_concordancia_competencias.py --somente-modulo
  python src/indicadores/IND_026_concordancia_competencias.py --sobrescrever

Não exporta inscrições, matrizes individuais nem marginais com células raras.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
import pandas as pd
import IND_020_diferenca_total_av1_av2 as base

ANOS = tuple(range(2019, 2026))
UFS = tuple(base.UFS)
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
AV_COLS = tuple(f'NU_NOTA_COMP{i}_AV{j}' for i in range(1,6) for j in (1,2))
IND = 'IND-026'
ARQUIVO = 'IND_026_concordancia_competencias'
MIN_N = 30
VERSAO = '2.25.0-' + '-'.join(f'ind{i:03d}' for i in range(1,27))
METODO = 'cohen_kappa_ponderado_quadratico_por_competencia_momentos_exatos'
NOTAS = (
    'Kappa de Cohen ponderado quadrático por competência para pares AV1/AV2 completos '
    'em C1–C5 dentro da POP_EVALUATOR (duas notas totais válidas). Os pesos de '
    'discordância são (nota_AV1 - nota_AV2)^2/200^2, mantendo a distância real '
    'entre categorias numéricas ordenadas. Calculado sobre toda a população elegível '
    'sem amostragem, a partir dos momentos e produtos cruzados. '
    'Kappa é indefinido se o desacordo esperado for zero; não forçar a zero/um. '
    'Não compara desempenho nem identifica erros de um corretor; medidas de concordância '
    'dependem também da distribuição de notas. UF indica local de prova. '
    'O histórico soma participações de edições, não pessoas únicas, e é uma '
    'concordância ponderada pelo volume, não média de Kappas anuais. '
    'Somente estatísticas agregadas com ao menos 30 pares por recorte; '
    'percentual de concordância exata suprimido quando revelaria células positivas menores que 30; '
    'sem marginais/células de contingência exportadas. '
    'Status draft; revisão acadêmica, comparabilidade entre anos e privacidade pendentes.'
)


def ler_json(p: Path) -> dict:
    with p.open('r', encoding='utf-8') as f: return json.load(f)


def recorte(periodo: dict, uf: str) -> dict:
    return periodo['brasil'] if uf == 'BR' else next(v for v in periodo['ufs'] if v['uf'] == uf)


class MomentosKappa:
    """Exato para pesos quadráticos: não é necessário guardar as notas individuais.

    A concordância esperada é calculada sob independência das duas marginais:
    E[(X-Y)^2] = E[X^2]+E[Y^2]-2 E[X]E[Y].
    A discordância observada é E[(X-Y)^2]. Kappa=1 - Dobs/Dexp.
    A divisão por 200**2 dos pesos se cancela na razão, portanto não
    altera o resultado. Isso corresponde aos pesos quadráticos de Cohen.
    """
    __slots__ = ('n','sx','sy','sx2','sy2','sxy','iguais')
    def __init__(self):
        self.n=0;self.sx=0.;self.sy=0.;self.sx2=0.;self.sy2=0.;self.sxy=0.;self.iguais=0

    def adicionar(self, x: np.ndarray, y: np.ndarray) -> None:
        x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
        if x.shape!=y.shape:raise AssertionError('AV1 e AV2 com tamanhos distintos')
        if not len(x):return
        if not (np.isfinite(x).all() and np.isfinite(y).all()):
            raise ValueError('Notas não finitas no acumulador')
        if (x<0).any() or (x>200).any() or (y<0).any() or (y>200).any():
            raise ValueError('Notas de competência fora de [0,200]')
        self.n+=len(x)
        self.sx+=float(x.sum());self.sy+=float(y.sum())
        self.sx2+=float(np.dot(x,x));self.sy2+=float(np.dot(y,y))
        self.sxy+=float(np.dot(x,y));self.iguais+=int(np.count_nonzero(x==y))

    def combinar(self, fonte: 'MomentosKappa') -> None:
        for k in self.__slots__:setattr(self,k,getattr(self,k)+getattr(fonte,k))

    def resultado(self) -> dict:
        if self.n<MIN_N:raise ValueError(f'Grupo insuficiente para Kappa: n={self.n} (<{MIN_N})')
        n=self.n
        obs=max(0.,(self.sx2+self.sy2-2*self.sxy)/n)
        exp=(self.sx2+self.sy2)/n-2*(self.sx/n)*(self.sy/n)
        # Somatório dos quadrados não é negativo; zeros numéricos muito pequenos
        # são arredondamento de ponto flutuante, não concordância negativa.
        if exp<0 and abs(exp)<1e-8: exp=0.
        if exp<0:raise AssertionError(f'Discordância esperada negativa ({exp})')
        # Caso ambas as distribuições sejam constantes e idênticas, exp=0,
        # Kappa é indefinido (mesmo se concordância bruta = 100%).
        k=None if exp<=1e-10 else 1-obs/exp
        if k is not None and not -1.000001<=k<=1.000001:
            raise AssertionError(f'Kappa fora do intervalo [-1,1]: {k}')
        # Um percentual exato, associado ao denominador divulgado, pode
        # permitir reconstituir uma contagem rara de acordos ou desacordos.
        # Por isso a taxa bruta só é exibida quando ambas as células
        # positivas têm N >= 30, ou quando a célula é zero.
        discordantes=n-self.iguais
        mostrar_pct=not (0<self.iguais<MIN_N or 0<discordantes<MIN_N)
        return {'n_pares_validos':n,
                'kappa_ponderado_quadratico':None if k is None else round(float(k),6),
                'situacao':'indefinido_sem_discordancia_esperada' if k is None else 'ok',
                'percentual_concordancia_exata':round(self.iguais*100/n,6) if mostrar_pct else None,
                'percentual_exato_suprimido':not mostrar_pct,
                'ponderacao':'quadratica_por_distancia_numerica',
                'sem_dados_individuais':True}


def novo_grupo() -> dict:
    return {'n_pop_evaluator':0,'n_completos':0,
            'competencias':{c:MomentosKappa() for c in COMPETENCIAS}}


def criar_grupos() -> dict:
    return {u:novo_grupo() for u in ('BR',*UFS)}


def adicionar_grupos(grupos:dict, ufs:np.ndarray, valores:np.ndarray,
                    completos:np.ndarray, ano:int) -> None:
    """Todas as linhas de valores são elegíveis em POP_EVALUATOR."""
    if len(ufs)!=len(valores) or len(ufs)!=len(completos) or valores.shape[1]!=10:
        raise AssertionError('Dimensões de entrada inválidas')
    if not np.isin(ufs,UFS).all():raise ValueError(f'{ano}: UF inválida')
    for uf in np.unique(ufs):
        quais=ufs==uf
        completos_uf=quais&completos
        notas=valores[completos_uf]
        for nome in ('BR',str(uf)):
            g=grupos[nome]
            g['n_pop_evaluator']+=int(quais.sum())
            g['n_completos']+=len(notas)
            for i,c in enumerate(COMPETENCIAS):
                g['competencias'][c].adicionar(notas[:,i*2],notas[:,i*2+1])


def referencia_21(raiz:Path):
    p=raiz/'outputs'/'json'/'IND_021_diferenca_por_competencia.json'
    if not p.is_file():raise FileNotFoundError(f'IND-021 necessário: {p}')
    x=ler_json(p)
    if x.get('indicator',{}).get('id')!='IND-021' or [v.get('ano') for v in x.get('years',[])]!=list(ANOS):
        raise ValueError('IND-021 inválido ou incompleto')
    return x


def obter_dashboards(raiz:Path, exigir_ind025:bool=True) -> dict:
    dados={}
    for ano in ANOS:
        p=raiz/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not p.is_file():raise FileNotFoundError(str(p))
        d=ler_json(p)
        if d.get('meta',{}).get('year')!=ano or d['meta'].get('data_status')!='draft':
            raise ValueError(f'Dashboard {ano} inválido/incompleto')
        if exigir_ind025 and d.get('quality',{}).get('ind025_validation',{}).get('status')!='ok':
            raise ValueError(f'Conclua IND-025 antes de integrar IND-026 ({ano})')
        for sec in ('evaluators','temporal','methodology'):
            if not isinstance(d.get('pages',{}).get(sec),dict):
                raise ValueError(f'Falta pages.{sec} no dashboard {ano}')
        dados[ano]=d
    return dados


def verificar_fontes(raiz:Path) -> None:
    for ano in ANOS:
        geo,aval=base.fonte_ano(raiz,ano)
        for p in (geo,aval):
            if p is not None and not p.is_file():raise FileNotFoundError(f'Fonte {ano}: {p}')
        cols=('NU_NOTA_AV1','NU_NOTA_AV2',*AV_COLS)
        cols=(('NU_INSCRICAO','NU_ANO') if geo else ('NU_ANO','SG_UF_PROVA'))+cols
        base.validar_cabecalho(aval,cols)
        if geo is not None:base.validar_cabecalho(geo,('NU_INSCRICAO','NU_ANO','SG_UF_PROVA'))


def processar_ano(raiz:Path,ano:int,por_ano:dict,historico:dict,bloco:int,tmp:Path) -> dict:
    geo,aval=base.fonte_ano(raiz,ano)
    cols=['NU_NOTA_AV1','NU_NOTA_AV2',*AV_COLS]
    cols=(['NU_INSCRICAO','NU_ANO'] if geo else ['NU_ANO','SG_UF_PROVA'])+cols
    qa={'fonte':aval.name,'geografia':geo.name if geo else aval.name,
        'juncao':'NU_INSCRICAO+NU_ANO' if geo else 'mesma_linha',
        'n_linhas_fonte':0,'n_elegiveis':0,'n_completos':0,'n_incompletos':0,
        'n_elegiveis_sem_join':0}
    db=None
    try:
        if geo:
            db=sqlite3.connect(tmp/f'geo_ind026_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['n_linhas_geo']=base.construir_geo(db,geo,ano,bloco)
        print(f'IND-026 | {ano}: lendo {aval.name}',flush=True)
        for df in base.ler_blocos(aval,cols,bloco):
            qa['n_linhas_fonte']+=len(df)
            if df['NU_ANO'].str.strip().ne(str(ano)).any():
                raise ValueError(f'{ano}: NU_ANO incompatível na fonte')
            if db is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any() or df['NU_ANO'].str.strip().ne(str(ano)).any():
                    raise ValueError(f'{ano}: inscrição/ano inválidos na fonte')
                try: db.executemany('INSERT INTO vistos VALUES (?)',((k,) for k in keys.tolist()))
                except sqlite3.IntegrityError as e:
                    raise ValueError(f'{ano}: inscrição duplicada na fonte') from e
            a=base.digitos(df['NU_NOTA_AV1']);b=base.digitos(df['NU_NOTA_AV2'])
            str_a=df['NU_NOTA_AV1'].str.strip();str_b=df['NU_NOTA_AV2'].str.strip()
            ambos=str_a.ne('')&str_b.ne('')
            if ((~a[ambos].between(0,1000))|(~b[ambos].between(0,1000))).any():
                raise ValueError(f'{ano}: nota total AV1/AV2 inválida')
            if not ambos.any(): continue
            e=df.loc[ambos]
            qa['n_elegiveis']+=len(e)
            raw=e[list(AV_COLS)].apply(lambda s:s.str.strip())
            presente=raw.ne('').all(axis=1).to_numpy(dtype=bool)
            valores=np.stack([base.digitos(raw[c]).to_numpy(dtype=np.float64)
                              for c in AV_COLS],axis=1)
            invalida=((~np.isfinite(valores))&(raw.to_numpy()!='')) | \
                     (np.isfinite(valores)&((valores<0)|(valores>200)))
            if invalida.any():raise ValueError(f'{ano}: notas de competência inválidas')
            completos=presente&np.isfinite(valores).all(axis=1)
            qa['n_completos']+=int(completos.sum())
            qa['n_incompletos']+=int((~completos).sum())
            if db is not None:
                ids=e['NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY,ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)',((k,i) for i,k in enumerate(ids)))
                    rows=db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g '
                                    'ON g.key=l.key AND g.ano=?',(ano,)).fetchall()
                finally:db.execute('DROP TABLE lote')
                if len(rows)!=len(ids):
                    qa['n_elegiveis_sem_join']+=len(ids)-len(rows)
                    raise ValueError(f'{ano}: elegíveis sem correspondência geográfica')
                ufs=np.empty(len(ids),dtype='<U3')
                for i,uf in rows:ufs[int(i)]=str(uf).strip().upper()
            else:
                ufs=e['SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            # Grava apenas estatísticas agregadas, sem expor identificadores.
            adicionar_grupos(por_ano,ufs,valores,completos,ano)
            adicionar_grupos(historico,ufs,valores,completos,ano)
        if qa['n_elegiveis']!=por_ano['BR']['n_pop_evaluator'] or qa['n_completos']!=por_ano['BR']['n_completos']:
            raise AssertionError(f'{ano}: totais por ano não conciliam')
        if sum(por_ano[u]['n_pop_evaluator'] for u in UFS)!=qa['n_elegiveis']:
            raise AssertionError(f'{ano}: soma das UFs não fecha')
        print(f'  POP_EVALUATOR={qa["n_elegiveis"]:,}; pares C1–C5 completos={qa["n_completos"]:,}',flush=True)
        return qa
    finally:
        if db is not None: db.close()


def compilar(recortes:dict,ano:int|str,referencia:dict) -> dict:
    def resumo(g):
        n=g['n_pop_evaluator'];pares=g['n_completos']
        if n<MIN_N or pares<MIN_N:
            raise ValueError(f'Grupo com menos de {MIN_N} observações pareadas: {n}, {pares}')
        return {'n_pop_evaluator':n,'n_cinco_pares_completos':pares,
                'percentual_cobertura':round(pares*100/n,6),
                'populacao':'POP_EVALUATOR (cinco pares completos)',
                'competencias':{c:g['competencias'][c].resultado() for c in COMPETENCIAS},
                'sem_dados_individuais':True}
    p={'brasil':resumo(recortes['BR']),
       'ufs':[{'uf':u,**resumo(recortes[u])} for u in UFS],
       'qualidade':{'status':'ok','soma_27_ufs_igual_brasil':True,'source_indicator':'IND-021'}}
    if isinstance(ano,int):p['ano']=ano
    else:p['periodo']=str(ano)
    for uf in ('BR',*UFS):
        g=recorte(p,uf);r=recorte(referencia,uf)
        if g['n_pop_evaluator']!=r['n_pop_evaluator'] or \
           g['n_cinco_pares_completos']!=r['n_competencias_pareadas']:
            raise ValueError(f'{ano}/{uf}: população/pares divergem do IND-021')
    for campo in ('n_pop_evaluator','n_cinco_pares_completos'):
        if sum(recorte(p,u)[campo] for u in UFS)!=p['brasil'][campo]:
            raise AssertionError(f'{ano}: soma UF de {campo} difere do Brasil')
    return p


def atualizar_dashboard(d:dict,p:dict,anos:list[dict],historico:dict,gerado:str)->dict:
    x=deepcopy(d);ev=x['pages']['evaluators']
    ev['weighted_kappa']={'indicator_id':IND,'population':'POP_EVALUATOR',
        'weighting':'quadratic','brasil':deepcopy(p['brasil']),
        'by_uf':deepcopy(p['ufs']), 'method':METODO,'note':NOTAS}
    ev['status']='partial'
    ev['reason']='IND-020 a IND-026 disponíveis; próximas análises podem estar pendentes'
    x['pages']['temporal']['ind026']={
        'indicator_id':IND,'population':'POP_EVALUATOR',
        'national_by_year':[{'year':z['ano'],**deepcopy(z['brasil'])} for z in anos],
        'period_total':deepcopy(historico['brasil']),
        'period_by_uf':deepcopy(historico['ufs']),
        'note':'Kappa histórico recalculado pelos momentos de todas as participações; não média simples dos Kappas.'}
    x['pages']['methodology']['ind026']={
        'definition':'Concordância ordinal AV1 × AV2 por competência C1–C5.',
        'population':'POP_EVALUATOR; pares completos C1–C5',
        'weight':'quadratic','method':METODO,
        'formula':'kappa=1 - E_obs[(X-Y)^2]/E_indep[(X-Y)^2]',
        'join':'NU_INSCRICAO+NU_ANO em 2019–2024; fonte direta em 2025',
        'minimum_pair_count':MIN_N,'limitations':NOTAS}
    x['quality']['ind026_validation']={
        'status':'ok','source_indicator':'IND-021',
        'n_pop_evaluator_brasil':p['brasil']['n_pop_evaluator'],
        'n_pares_completos_brasil':p['brasil']['n_cinco_pares_completos'],
        'soma_27_ufs_igual_brasil':True,'sem_amostragem':True,
        'individuos_exportados':0,'revisao_academica_pendente':True,
        'revisao_privacidade_complementar_pendente':True}
    x['meta']['analysis_version']=VERSAO
    x['meta']['generated_at']=gerado
    x['meta']['data_status']='draft'
    aviso='IND-026: Kappa de Cohen ponderado quadrático C1–C5 na POP_EVALUATOR; revisão acadêmica e de privacidade pendentes.'
    if aviso not in x['meta'].setdefault('warnings',[]):x['meta']['warnings'].append(aviso)
    return x


def gravar_json(path:Path,obj) -> None:
    with path.open('w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')


def executar(raiz:Path,bloco:int=100_000,somente_modulo:bool=False,sobrescrever:bool=False):
    if bloco<1:raise ValueError('--bloco deve ser positivo')
    ref=referencia_21(raiz)
    verificar_fontes(raiz)
    dashboards={} if somente_modulo else obter_dashboards(raiz,exigir_ind025=True)
    j=raiz/'outputs'/'json';c=raiz/'outputs'/'indicadores'
    destinos=[j/f'{ARQUIVO}.json',c/f'{ARQUIVO}.csv']
    if not sobrescrever:
        for p in destinos:
            if p.exists():raise FileExistsError(f'Arquivo IND-026 existente: {p} (use --sobrescrever)')
        for ano,d in dashboards.items():
            if 'ind026_validation' in d.get('quality',{}) or 'weighted_kappa' in d['pages']['evaluators']:
                raise FileExistsError(f'IND-026 já integrado no dashboard {ano}')
    hashes={ano:hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
            for ano in ANOS} if not somente_modulo else {}
    anos=[];historico_grupos=criar_grupos();qafontes={}
    out=raiz/'outputs';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ind026_geo_',dir=out) as tmp:
        for ano,r in zip(ANOS,ref['years']):
            grupos=criar_grupos()
            qa=processar_ano(raiz,ano,grupos,historico_grupos,bloco,Path(tmp))
            qa['pop_evaluator_confere_ind021']=True
            p=compilar(grupos,ano,r);p['qualidade_fonte']=qa
            anos.append(p);qafontes[str(ano)]=qa
    historico=compilar(historico_grupos,'2019-2025',ref['historical'])
    for uf in ('BR',*UFS):
        for campo in ('n_pop_evaluator','n_cinco_pares_completos'):
            if recorte(historico,uf)[campo]!=sum(recorte(p,uf)[campo] for p in anos):
                raise AssertionError(f'Histórico {uf}/{campo} difere da soma de anos')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    modulo={'meta':{'indicator_id':IND,'module_schema_version':'ind026-module-1.0.0',
        'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
        'generated_at':gerado,'data_status':'draft','source_indicator':'IND-021',
        'geographic_dimension':'SG_UF_PROVA',
        'population_definition':'POP_EVALUATOR, cinco pares AV1/AV2 de competências completos',
        'method':METODO,'weighting':'quadratic','minimum_group_count':MIN_N,
        'source_qa':qafontes,'publication_status':'draft; revisão acadêmica e privacidade pendentes',
        'notes':NOTAS},
        'indicator':{'id':IND,'name':'Concordância por competência','unit':'kappa',
           'dashboard_json_path':'pages.evaluators.weighted_kappa','visualization':'Barras'},
        'years':anos,'historical':historico,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    novos={ano:atualizar_dashboard(dashboards[ano],anos[i],anos,historico,gerado)
           for i,ano in enumerate(ANOS)} if not somente_modulo else {}
    for ano,d in novos.items():
        if d['meta']['year']!=ano or d['quality']['ind025_validation']['status']!='ok':
            raise ValueError(f'Integridade de dashboard {ano} não preservada')
        for caminho in (raiz/'04_resultados_analises.schema.json',
                        raiz/'docs'/'04_resultados_analises.schema.json'):
            if caminho.is_file():
                try:import jsonschema
                except ImportError:break
                jsonschema.validate(d,ler_json(caminho));break
    linhas=[]
    for p in (*anos,historico):
        periodo=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*((z['uf'],z) for z in p['ufs'])]:
            for cp,v in g['competencias'].items():
                linhas.append({'indicador_id':IND,'periodo':periodo,'abrangencia':'BR' if uf=='BR' else 'UF',
                    'uf':uf,'populacao':'POP_EVALUATOR','competencia':cp,
                    'n_pop_evaluator':g['n_pop_evaluator'],
                    'n_pares_completos':g['n_cinco_pares_completos'],
                    'percentual_cobertura':g['percentual_cobertura'],
                    'kappa_ponderado_quadratico':v['kappa_ponderado_quadratico'],
                    'situacao':v['situacao'],
                    'percentual_concordancia_exata':v['percentual_concordancia_exata'],
                    'metodo':METODO})
    if len(linhas)!=1120:raise AssertionError(f'Esperadas 1120 linhas CSV; obtidas {len(linhas)}')
    json.dumps(modulo,allow_nan=False)
    with tempfile.TemporaryDirectory(prefix='.ind026_stage_',dir=out) as tmp:
        td=Path(tmp);fjson=td/f'{ARQUIVO}.json';fcsv=td/f'{ARQUIVO}.csv'
        gravar_json(fjson,modulo)
        with fcsv.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';');w.writeheader();w.writerows(linhas)
        grava=[(fjson,destinos[0]),(fcsv,destinos[1])]
        for ano,d in novos.items():
            p=td/f'dashboard_enem_{ano}.json';gravar_json(p,d);grava.append((p,j/p.name))
        # Evitar sobrescrita por IND-024/025 ou outro processo em andamento.
        for ano in ANOS:
            if not somente_modulo:
                atual=hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
                if atual!=hashes[ano]:
                    raise RuntimeError(f'Dashboard {ano} mudou durante a execução. Nada foi gravado; rode após concluir outros indicadores.')
        for origem,destino in grava:
            destino.parent.mkdir(parents=True,exist_ok=True);os.replace(origem,destino)
    print(f'IND-026 concluído: 224 recortes; 5 competências por recorte; 1120 linhas CSV.')
    print('Saídas: '+str(destinos[0])+' | '+str(destinos[1]))
    if not somente_modulo:print('Dashboards 2019–2025 atualizados com IND-026 (blocos anteriores preservados).')
    return modulo


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path.cwd(),help='raiz do projeto')
    ap.add_argument('--bloco',type=int,default=100_000,help='linhas lidas por bloco')
    ap.add_argument('--somente-modulo',action='store_true',help='gerar somente CSV/JSON modular, sem alterar dashboards')
    ap.add_argument('--sobrescrever',action='store_true',help='substituir saídas próprias do IND-026 existentes')
    args=ap.parse_args()
    executar(args.base.resolve(),args.bloco,args.somente_modulo,args.sobrescrever)

if __name__=='__main__':main()
