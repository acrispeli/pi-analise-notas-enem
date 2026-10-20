#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-018 — Tamanho dos clusters, ENEM 2019–2025.

Catálogo: IND-018 / ML / competências / Tamanho dos clusters / P1.
Pergunta: "Qual a participação de cada perfil?".
População: POP_VALID; regra COUNT e % por cluster, sem amostragem para COUNT.
JSON: pages.competencies.clusters.sizes; gráfico: barras.

Pré-requisito: IND-017 concluído para os sete anos (que por sua vez depende
             dos IND-014, IND-015 e IND-016). NÃO executar em paralelo com
             outros scripts que gravam dashboards cumulativos.

Metodologia: atribuir C1..C5 de cada redação válida ao centro K-Means mais
próximo no espaço padronizado do seu modelo IND-017, minimizando a distância
quadrática euclidiana (argmin, empate pelo menor cluster_id). Cada recorte
(ano/BR, ano/UF, histórico/BR, histórico/UF) usa SEU PRÓPRIO modelo.
Os perfis amostrais IND-017 não são treinados novamente. O histórico não é
soma direta dos clusters anuais (centros distintos).

IMPORTANTE: P1...Pk de recortes diferentes não identificam automaticamente
perfis equivalentes. Percentuais IND-018 referem-se a POP_VALID, enquanto os
percentuais de IND-017 se referem a AMOSTRA_ML. Nenhuma linha individual é
exportada. Qualquer cluster populacional com menos de 30 participantes bloqueia
toda a exportação; revisão acadêmica e disclosure continuam necessárias.

Execute na raiz do projeto após IND-017:
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_018_tamanho_clusters.py
Saídas:
    outputs/indicadores/IND_018_tamanho_clusters.csv
    outputs/json/IND_018_tamanho_clusters.json
    outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json
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

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
LABELS = tuple(f'C{i}' for i in range(1, 6))
COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COMP)
IND = 'IND-018'
NOME = 'Tamanho dos clusters'
METODO = 'atribuicao_kmeans_centros_ind017_pop_valid_completa'
VERSAO = ('2.17.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-'
          'ind009-ind010-ind011-ind012-ind013-ind014-ind015-ind016-ind017-ind018')
BLOCO = 100_000
MIN_PUB = 30
EPS = 1e-5
DEFINICAO = ('Contagem absoluta e percentual de redações válidas POP_VALID por perfil '
            'K-Means fixo do IND-017 (C1..C5 padronizadas pelo IND-014), '
            'com atribuição de todas as participações sem nova amostragem.')
RESSALVAS = ('Modelos treinados em AMOSTRA_ML (IND-017), mas tamanhos calculados '
            'sobre POP_VALID completa. P1..Pk são rótulos locais: não comparar '
            'automaticamente entre UFs, anos ou histórico. As classes não são '
            'oficiais do ENEM, e a escolha de k requer avaliação no IND-019. '
            'SG_UF_PROVA é UF de aplicação, não residência. Histórico reúne '
            'participações, não pessoas únicas; modelos históricos são próprios. '
            'Células com N de 1 a 29 não são exportadas. Status draft: '
            'revisão acadêmica e privacidade complementar pendentes.')


def fonte(ano: int, raiz: Path) -> Path:
    nome = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / nome


def ler_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {path}')
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def indexar_ufs(periodo: dict, contexto: str) -> dict[str,dict]:
    lista = periodo.get('ufs', [])
    if len(lista) != 27 or {u.get('uf') for u in lista} != set(UFS):
        raise ValueError(f'{contexto}: lista das 27 UFs incompleta/duplicada')
    return {u['uf']: u for u in lista}


def construir_modelo(g14: dict, g17: dict, contexto: str) -> dict:
    if g14.get('n_validas') != g17.get('n_validas') or int(g17.get('n_validas',0)) < 30:
        raise ValueError(f'{contexto}: tamanhos POP_VALID IND-014/017 divergentes')
    m = g14.get('modelo', {})
    scaler = g17.get('padronizacao', {})
    try:
        mu = np.asarray(m['mean'], dtype=np.float64)
        sd = np.asarray(m['scale'], dtype=np.float64)
        ms = np.asarray(scaler['mean'], dtype=np.float64)
        ss = np.asarray(scaler['scale'], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as ex:
        raise ValueError(f'{contexto}: StandardScaler incompleto') from ex
    if any(v.shape != (5,) for v in (mu,sd,ms,ss)) or not all(np.isfinite(v).all() for v in (mu,sd,ms,ss)):
        raise ValueError(f'{contexto}: formato do StandardScaler inválido')
    if np.any(sd <= 0) or not np.allclose(mu, ms, atol=3e-7, rtol=0) or not np.allclose(sd, ss, atol=3e-7, rtol=0):
        raise ValueError(f'{contexto}: IND-014 e IND-017 possuem padronizações divergentes')
    if m.get('competencias') != list(LABELS) or m.get('variaveis') != list(COMP):
        raise ValueError(f'{contexto}: ordem de competências divergente')
    clusters = g17.get('clusters', [])
    k = g17.get('k')
    if not isinstance(k, int) or not 2 <= k <= 8 or len(clusters) != k:
        raise ValueError(f'{contexto}: clusters inválidos ou incompletos')
    if [c.get('cluster_id') for c in clusters] != [f'P{i}' for i in range(1,k+1)]:
        raise ValueError(f'{contexto}: ordem/IDs dos clusters inconsistentes')
    centros = np.asarray([c.get('centro_padronizado',[]) for c in clusters], dtype=np.float64)
    if centros.shape != (k,5) or not np.isfinite(centros).all():
        raise ValueError(f'{contexto}: centroides inválidos')
    if not all(len(c.get('centro_pontos',[]))==5 for c in clusters):
        raise ValueError(f'{contexto}: centroides não têm cinco competências')
    pontos = np.asarray([c['centro_pontos'] for c in clusters], dtype=np.float64)
    if not np.allclose(pontos, centros*sd+mu,atol=1e-4,rtol=0):
        raise ValueError(f'{contexto}: centróides em pontos divergem da padronização')
    n_am = g17.get('n_amostra_ml')
    if not isinstance(n_am,int) or not 2*MIN_PUB<=n_am<=g17['n_validas']:
        raise ValueError(f'{contexto}: população amostral IND-017 inválida')
    if sum(int(c.get('n_amostra',0)) for c in clusters) != n_am:
        raise ValueError(f'{contexto}: amostra IND-017 não fecha por cluster')
    if any(c['n_amostra'] < MIN_PUB for c in clusters):
        raise ValueError(f'{contexto}: grupo amostral IND-017 menor que {MIN_PUB}')
    if any(abs(c['percentual_amostra']-100*c['n_amostra']/n_am)>1e-4 for c in clusters):
        raise ValueError(f'{contexto}: percentual amostral IND-017 incorreto')
    if g17.get('percentuais_referem_se_a') != 'AMOSTRA_ML_nao_POP_VALID' or not g17.get('sem_dados_individuais'):
        raise ValueError(f'{contexto}: IND-017 não distingue proporção amostral/populacional')
    if g17.get('n_somas_divergentes') != g14.get('n_somas_divergentes') or abs(
      float(g17.get('delta_soma_competencias_menos_nota_redacao',0)) -
      float(g14.get('delta_soma_competencias_menos_nota_redacao',0))) > EPS:
        raise ValueError(f'{contexto}: exceção SC/2023 diverge entre IND-014/017')
    return {'n':int(g14['n_validas']), 'mu':mu, 'sd':sd, 'centros':centros,
            'clusters':clusters, 'k':k, 'n_amostra':n_am,
            'div':g14['n_somas_divergentes'],
            'delta':float(g14['delta_soma_competencias_menos_nota_redacao']),
            'total_registros':g14.get('total_registros')}


def carregar_pre_requisitos(raiz: Path):
    pasta=raiz/'outputs'/'json'
    m14=ler_json(pasta/'IND_014_variancia_explicada_pca.json')
    m17=ler_json(pasta/'IND_017_perfis_competencias.json')
    if m14.get('indicator',{}).get('id')!='IND-014' or m17.get('indicator',{}).get('id')!='IND-017':
        raise ValueError('IND-014 e IND-017 são pré-requisitos obrigatórios')
    if any(d.get('meta',{}).get('data_status')!='draft' for d in (m14,m17)):
        raise ValueError('Os módulos devem permanecer em draft')
    for mod in (m14,m17):
        if {p.get('ano') for p in mod.get('years',[])}!=set(ANOS) or len(mod.get('years',[]))!=7:
            raise ValueError('Módulo anterior não cobre exatamente os sete anos')
        if mod.get('historical',{}).get('periodo')!='2019-2025':
            raise ValueError('Módulo anterior sem histórico 2019–2025')
    m14years={p['ano']:p for p in m14['years']}
    m17years={p['ano']:p for p in m17['years']}
    ref={}
    for periodo in (*ANOS, 'historical'):
        a=m14['historical'] if periodo=='historical' else m14years[periodo]
        b=m17['historical'] if periodo=='historical' else m17years[periodo]
        aus=indexar_ufs(a, f'IND014/{periodo}')
        bus=indexar_ufs(b, f'IND017/{periodo}')
        ref[periodo]={}
        for uf in ('BR',*UFS):
            ga=a['brasil'] if uf=='BR' else aus[uf]
            gb=b['brasil'] if uf=='BR' else bus[uf]
            ref[periodo][uf]=construir_modelo(ga,gb,f'{periodo}/{uf}')
        if sum(ref[periodo][u]['n'] for u in UFS)!=ref[periodo]['BR']['n']:
            raise ValueError(f'{periodo}: soma nacional das UFs divergente')
    for uf in ('BR',*UFS):
        if sum(ref[ano][uf]['n'] for ano in ANOS)!=ref['historical'][uf]['n']:
            raise ValueError(f'Histórico/{uf}: N difere da soma dos sete anos')
    dashboards={}
    for ano in ANOS:
        dash=ler_json(pasta/f'dashboard_enem_{ano}.json')
        if dash.get('meta',{}).get('year')!=ano or dash['meta'].get('data_status')!='draft':
            raise ValueError(f'Dashboard {ano} inconsistente')
        if dash.get('quality',{}).get('ind017_validation',{}).get('status')!='ok':
            raise ValueError(f'{ano}: IND-017 não finalizado no dashboard')
        comp=dash.get('pages',{}).get('competencies',{})
        if comp.get('clusters',{}).get('indicator_id')!='IND-017':
            raise ValueError(f'{ano}: página clusters do IND-017 ausente')
        if 'sizes' in comp['clusters'] or 'ind018_validation' in dash.get('quality',{}):
            raise ValueError(f'{ano}: IND-018 já existe; não sobrescrever sem revisão')
        if dash['pages']['overview']['kpis'].get('valid_essays')!=ref[ano]['BR']['n']:
            raise ValueError(f'{ano}: denominador dashboard/IND-014 diverge')
        dashboards[ano]=dash
    return m14,ref,dashboards


def classificar(x:np.ndarray, ref:dict) -> np.ndarray:
    """Distância euclidiana ao centro na escala Z (argmin; empate por índice)."""
    x=np.asarray(x,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=5 or not np.isfinite(x).all():
        raise ValueError('C1..C5 ilegíveis na etapa de atribuição')
    z=(x-ref['mu'])/ref['sd']
    c=ref['centros']
    # Identidade algébrica equivalente a ((z[:,None,:]-c[None,:,:])**2).sum(axis=2).
    # Para segurança numérica em casos próximos, expressão direta em 5 dimensões.
    dist=np.sum((z[:,None,:]-c[None,:,:])**2, axis=2)
    if not np.isfinite(dist).all():
        raise ValueError('Distância não finita na atribuição')
    return np.argmin(dist,axis=1)


class Acumulador:
    def __init__(self,ref:dict):
        self.ref=ref
        self.cont=np.zeros(ref['k'],dtype=np.int64)
        self.n=0
    def adicionar(self,x:np.ndarray):
        ids=classificar(x,self.ref)
        self.cont+=np.bincount(ids,minlength=self.ref['k'])
        self.n+=len(x)
    def resultado(self,contexto:str) -> dict:
        if self.n!=self.ref['n'] or int(self.cont.sum())!=self.ref['n']:
            raise ValueError(f'{contexto}: atribuições {self.n} diferem do esperado {self.ref["n"]}')
        if np.any(self.cont < MIN_PUB):
            raise ValueError(f'{contexto}: cluster POP_VALID com contagem <{MIN_PUB}; '
                             'não exportar antes de decidir supressão complementar')
        n=self.n
        clusters=[]
        for i,c in enumerate(self.ref['clusters']):
            count=int(self.cont[i]); samples=int(c['n_amostra'])
            clusters.append({'cluster_id':c['cluster_id'],'rotulo':c['rotulo'],
               'n_redacoes':count, 'proporcao':round(count/n,10),
               'percentual':round(100*count/n,6),
               'n_amostra_treino':samples,
               'percentual_amostra_treino':c['percentual_amostra'],
               'centro_pontos':c['centro_pontos']})
        if sum(g['n_redacoes'] for g in clusters)!=n or abs(sum(g['percentual'] for g in clusters)-100)>1e-4:
            raise ValueError(f'{contexto}: proporções não fecham 100%')
        return {'n_validas':n,'n_amostra_ml_treino':self.ref['n_amostra'],
                'k':self.ref['k'],'clusters':clusters,'soma_clusters':n,
                'percentual_total':round(sum(g['percentual'] for g in clusters),6),
                'population':'POP_VALID','method':METODO,
                'modelo_origem':'IND-017','nenhum_dado_individual_exportado':True,
                'min_n_cluster_populacional':min(g['n_redacoes'] for g in clusters),
                'n_somas_divergentes':self.ref['div'],
                'delta_soma_competencias_menos_nota_redacao':self.ref['delta']}


def processar_microdados(raiz:Path, refs:dict, bloco:int):
    acumuladores_hist={u:Acumulador(refs['historical'][u]) for u in ('BR',*UFS)}
    anos=[]
    for ano in ANOS:
        ac={u:Acumulador(refs[ano][u]) for u in ('BR',*UFS)}
        arq=fonte(ano,raiz)
        if not arq.is_file():
            raise FileNotFoundError(f'Microdado de {ano} não encontrado: {arq}')
        qa={v:0 for v in ('total_registros','validas','status1_sem_nota',
             'status1_nota_invalida','validas_sem_uf','validas_uf_desconhecida',
             'validas_competencias_incompletas','n_somas_divergentes')}
        delta=0.0
        uf_div={u:[0,0.0] for u in UFS}
        print(f'IND-018 | {ano}: atribuição populacional...',flush=True)
        for frame in pd.read_csv(arq,sep=';',usecols=list(COLUNAS),dtype=str,
              keep_default_na=False,na_filter=False,encoding='utf-8-sig',
              encoding_errors='replace',on_bad_lines='error',chunksize=bloco):
            qa['total_registros']+=len(frame)
            ufs=frame['SG_UF_PROVA'].str.strip().str.upper()
            status=frame['TP_STATUS_REDACAO'].str.strip().eq('1')
            nota_txt=frame['NU_NOTA_REDACAO'].str.strip()
            nota=pd.to_numeric(nota_txt.str.replace(',','.',regex=False),errors='coerce')
            valid=status & nota.notna() & nota.between(0,1000)
            qa['validas']+=int(valid.sum())
            qa['status1_sem_nota']+=int((status & nota_txt.eq('')).sum())
            qa['status1_nota_invalida']+=int((status & nota_txt.ne('') & ~nota.between(0,1000)).sum())
            qa['validas_sem_uf']+=int((valid & ufs.eq('')).sum())
            qa['validas_uf_desconhecida']+=int((valid & ufs.ne('') & ~ufs.isin(UFS)).sum())
            if not bool(valid.any()):continue
            raw=frame.loc[valid,list(COMP)].apply(lambda col:col.str.strip())
            dados=raw.apply(lambda col:pd.to_numeric(col.str.replace(',','.',regex=False),errors='coerce'))
            ok=dados.notna().all(axis=1) & dados.ge(0).all(axis=1) & dados.le(200).all(axis=1)
            qa['validas_competencias_incompletas']+=int((~ok).sum())
            if not bool(ok.any()):continue
            x=dados.loc[ok].to_numpy(dtype=np.float64)
            siglas=ufs.loc[valid].loc[ok].to_numpy(dtype=str)
            notas=nota.loc[valid].loc[ok].to_numpy(dtype=np.float64)
            diferenca=x.sum(axis=1)-notas
            bad=np.abs(diferenca)>1e-6
            qa['n_somas_divergentes']+=int(bad.sum())
            delta+=float(diferenca[bad].sum())
            ac['BR'].adicionar(x)
            acumuladores_hist['BR'].adicionar(x)
            for u in np.unique(siglas):
                if u not in ac:
                    continue   # rejeitado no QA abaixo antes de exportação
                ix=siglas==u
                uf_div[u][0]+=int(np.count_nonzero(bad[ix]))
                uf_div[u][1]+=float(diferenca[ix & bad].sum())
                ac[u].adicionar(x[ix])
                acumuladores_hist[u].adicionar(x[ix])
        for tipo in ('status1_sem_nota','status1_nota_invalida','validas_sem_uf',
                     'validas_uf_desconhecida','validas_competencias_incompletas'):
            if qa[tipo]:raise ValueError(f'{ano}: microdados inválidos: {tipo}={qa[tipo]}')
        br=refs[ano]['BR']
        if qa['validas']!=br['n']:
            raise ValueError(f'{ano}: N válido não corresponde a IND-014/017')
        if br['total_registros'] is not None and qa['total_registros']!=br['total_registros']:
            raise ValueError(f'{ano}: POP_ALL diverge do IND-014')
        if qa['n_somas_divergentes']!=br['div'] or abs(delta-br['delta'])>EPS:
            raise ValueError(f'{ano}: divergências da soma C1..5 não conferem com IND-014/017')
        for u in UFS:
            if uf_div[u][0]!=refs[ano][u]['div'] or abs(uf_div[u][1]-refs[ano][u]['delta'])>EPS:
                raise ValueError(f'{ano}/{u}: exceção de soma das competências diverge')
        resultado_br=ac['BR'].resultado(f'{ano}/BR')
        resultado_ufs=[{'uf':u,**ac[u].resultado(f'{ano}/{u}')} for u in UFS]
        if sum(g['n_validas'] for g in resultado_ufs)!=resultado_br['n_validas']:
            raise ValueError(f'{ano}: soma das 27 UFs não fecha no Brasil')
        anos.append({'ano':ano,'arquivo_fonte':arq.name,'brasil':resultado_br,
                     'ufs':resultado_ufs,'qualidade':{
                         'status':'ok',**qa,
                         'delta_soma_competencias_menos_nota_redacao':delta}})
        print(f'  Brasil {resultado_br["n_validas"]:,} | k={resultado_br["k"]} | '
              f'clusteres: {[c["n_redacoes"] for c in resultado_br["clusters"]]}',flush=True)
    resultado_hist=acumuladores_hist['BR'].resultado('2019-2025/BR')
    hist_ufs=[{'uf':u,**acumuladores_hist[u].resultado(f'2019-2025/{u}')} for u in UFS]
    if sum(g['n_validas'] for g in hist_ufs)!=resultado_hist['n_validas']:
        raise ValueError('Histórico: soma UFs diferente Brasil')
    for u in ('BR',*UFS):
        anual=sum(d['brasil']['n_validas'] if u=='BR' else
                  next(g['n_validas'] for g in d['ufs'] if g['uf']==u) for d in anos)
        if anual!=acumuladores_hist[u].n:
            raise ValueError(f'Histórico/{u}: denominador diverge dos sete anos')
    historico={'periodo':'2019-2025','brasil':resultado_hist,'ufs':hist_ufs,
               'qualidade':{'status':'ok','n_validas':resultado_hist['n_validas'],
                            'modelo_historico_independente':True}}
    return anos,historico


def linhas_csv(anos:list[dict],hist:dict) -> list[dict]:
    res=[]
    for item in [*anos,hist]:
        periodo=str(item.get('ano','2019-2025'))
        for uf,g in [('BR',item['brasil']),*[(x['uf'],x) for x in item['ufs']]]:
            for c in g['clusters']:
                row={'indicador_id':IND,'periodo':periodo,
                     'abrangencia':'BR' if uf=='BR' else 'UF','uf':uf,
                     'cluster_id':c['cluster_id'],'n_validas':g['n_validas'],
                     'n_cluster_pop_valid':c['n_redacoes'],
                     'proporcao_pop_valid':c['proporcao'],
                     'percentual_pop_valid':c['percentual'],
                     'n_cluster_amostra_ml':c['n_amostra_treino'],
                     'percentual_cluster_amostra_ml':c['percentual_amostra_treino'],
                     'n_amostra_ml':g['n_amostra_ml_treino'],
                     'k':g['k'],'method':METODO}
                res.append(row)
    if len(res)!=sum(len(g['clusters']) for p in [*anos,hist] for g in [p['brasil'],*p['ufs']]):
        raise ValueError('Quantidade de linhas CSV não coincide com clusters')
    return res


def grupo_dashboard(g:dict) -> dict:
    return {k:deepcopy(g[k]) for k in ('n_validas','n_amostra_ml_treino','k','clusters',
                 'soma_clusters','percentual_total','population','method','modelo_origem',
                 'nenhum_dado_individual_exportado','min_n_cluster_populacional')}


def atualizar_dashboard(ano:dict,anos:list[dict],hist:dict,dash:dict,gerado:str) -> dict:
    out=deepcopy(dash)
    sizes={'indicator_id':IND,'population':'POP_VALID','method':METODO,
           'n':ano['brasil']['n_validas'], 'brasil':grupo_dashboard(ano['brasil']),
           'by_uf':[{'uf':g['uf'],**grupo_dashboard(g)} for g in ano['ufs']],
           'nota':RESSALVAS}
    out['pages']['competencies']['clusters']['sizes']=sizes
    out['pages']['temporal']['ind018']={
        'indicator_id':IND,
        'national_by_year':[{'year':d['ano'],**grupo_dashboard(d['brasil'])} for d in anos],
        'period_total':grupo_dashboard(hist['brasil']),
        'period_by_uf':[{'uf':g['uf'],**grupo_dashboard(g)} for g in hist['ufs']],
        'historical_note':'Atribuição histórica feita aos centros históricos, não somando perfis anuais.'}
    out['pages']['methodology']['ind018']={
        'definition':DEFINICAO,'method':METODO,'source_file':ano['arquivo_fonte'],
        'source_indicators':['IND-014','IND-017'],
        'training_population':'AMOSTRA_ML (IND-017)',
        'count_population':'POP_VALID inteira, sem amostragem',
        'classification':'centróide mais próximo na escala z-score C1..C5',
        'ties':'menor cluster_id P1..Pk',
        'min_cell_n':MIN_PUB,
        'limitations':RESSALVAS}
    out['quality']['ind018_validation']={
        'status':'ok','method':METODO,
        'n_validas_brasil':ano['brasil']['n_validas'],
        'soma_clusters_igual_pop_valid':True,
        'soma_27_ufs_igual_brasil':True,
        'min_cluster_n_30':True,
        'historico_proprio':True,
        'n_dados_individuais_exportados':0,
        'n_somas_divergentes':ano['brasil']['n_somas_divergentes'],
        'delta_soma_competencias_menos_nota_redacao':ano['brasil']['delta_soma_competencias_menos_nota_redacao'],
        'model_quality_indices':'IND-019 pendente'}
    out['meta']['analysis_version']=VERSAO
    out['meta']['generated_at']=gerado
    out['meta']['data_status']='draft'
    aviso=('IND-018: quantidades POP_VALID atribuídas a centroides K-Means do IND-017; '
           'rótulos P1..Pk variam por recorte, k requer avaliação no IND-019; '
           'revisão acadêmica e supressão complementar pendentes para publicação.')
    if aviso not in out['meta'].setdefault('warnings',[]):out['meta']['warnings'].append(aviso)
    return out


def validar_schema(doc:dict,raiz:Path):
    for key in ('meta','filters','quality','pages'):
        if key not in doc:raise ValueError(f'Dashboard não possui {key}')
    candidatos=[raiz/'docs'/'04_resultados_analises.schema.json',
                raiz/'docs'/'metodologia'/'04_resultados_analises.schema.json',
                raiz/'04_resultados_analises.schema.json']
    schema=next((p for p in candidatos if p.is_file()),None)
    if schema is None:return 'estrutura mínima; JSON Schema local não encontrado'
    import jsonschema
    jsonschema.validate(doc,ler_json(schema))
    return 'JSON Schema v1.0.0'


def gravar_json(path:Path,data:dict):
    with path.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def gravar_csv(path:Path,linhas:list[dict]):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
        writer.writeheader();writer.writerows(linhas)


def executar(raiz:Path,bloco:int=BLOCO):
    if not isinstance(bloco,int) or bloco<1:
        raise ValueError('bloco deve ser inteiro positivo')
    mod14,refs,dashes=carregar_pre_requisitos(raiz)
    anos,hist=processar_microdados(raiz,refs,bloco)
    rows=linhas_csv(anos,hist)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    atualizados={p['ano']:atualizar_dashboard(p,anos,hist,dashes[p['ano']],gerado) for p in anos}
    validadores={validar_schema(doc,raiz) for doc in atualizados.values()}
    modulo={'meta':{
       'indicator_id':IND,'module_schema_version':'ind018-module-1.0.0',
       'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
       'generated_at':gerado,'data_status':'draft',
       'source_files':{str(p['ano']):p['arquivo_fonte'] for p in anos},
       'source_indicator_file':'IND_017_perfis_competencias.json',
       'population_definition':DEFINICAO,
       'geographic_dimension':'SG_UF_PROVA',
       'method':METODO,
       'source_discrepancies':mod14['meta']['source_discrepancies'],
       'no_sampling_for_counts':True,
       'train_sample_reference':'IND-017',
       'minimum_cell_count':MIN_PUB,
       'notes':RESSALVAS},
       'indicator':{'id':IND,'name':NOME,'unit':'redacoes',
           'dashboard_json_path':'pages.competencies.clusters.sizes',
           'visualization':'Barras'},
       'years':anos,'historical':hist,
       'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    json.dumps(modulo,ensure_ascii=False,allow_nan=False)
    base=raiz/'outputs';out_csv=base/'indicadores';out_json=base/'json'
    out_csv.mkdir(parents=True,exist_ok=True)
    out_json.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind018_stage_',dir=base) as tmp:
        td=Path(tmp)
        gravar_csv(td/'IND_018_tamanho_clusters.csv',rows)
        gravar_json(td/'IND_018_tamanho_clusters.json',modulo)
        for a in ANOS:gravar_json(td/f'dashboard_enem_{a}.json',atualizados[a])
        # Comparação estrutural entre os artefatos serializados e objetos pré-validados.
        if len(list(csv.DictReader((td/'IND_018_tamanho_clusters.csv').open(encoding='utf-8-sig'),delimiter=';')))!=len(rows):
            raise ValueError('CSV gerado incompleto')
        if ler_json(td/'IND_018_tamanho_clusters.json')['indicator']['id']!=IND:
            raise ValueError('JSON modular gerado inválido')
        arquivos=[('IND_018_tamanho_clusters.csv',out_csv),
                  ('IND_018_tamanho_clusters.json',out_json),
                  *[(f'dashboard_enem_{a}.json',out_json) for a in ANOS]]
        # Todos os arquivos são escritos/validados em staging ANTES da substituição.
        for name,dest in arquivos:os.replace(td/name,dest/name)
    print('\nIND-018 CONCLUÍDO',flush=True)
    print(f'  CSV: {len(rows):,} linhas, sem redações individuais',flush=True)
    print('  JSON: IND_018_tamanho_clusters.json',flush=True)
    print('  Dashboards atualizados: 2019–2025',flush=True)
    print('  Schema: '+', '.join(sorted(validadores)),flush=True)
    print('  data_status=draft; IND-019 e revisão de privacidade pendentes',flush=True)


def main():
    parser=argparse.ArgumentParser(description='IND-018 tamanho populacional dos clusters K-Means')
    parser.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--bloco',type=int,default=BLOCO)
    opt=parser.parse_args()
    executar(opt.raiz.resolve(),bloco=opt.bloco)


if __name__=='__main__':main()
