#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-034 | Recorte adicional de redações com nota FINAL = 980 (Brasil).

Preserva o IND-034 original (POP_NEAR=900..980). A classificação por competência
usa SOMENTE os campos finais NU_NOTA_COMP1..5, que já incorporam o procedimento
de correção do Inep. AV1/AV2/AV3/AV4 são usados exclusivamente para auditar
qual trajetória de avaliação é compatível com os campos finais, sem imputar
notas individuais nem determinar arbitrariamente um par no caso de empate.

Execução na raiz do projeto:
  python src/indicadores/IND_034_recorte_980_final.py --autoteste
  python src/indicadores/IND_034_recorte_980_final.py
  python src/indicadores/IND_034_recorte_980_final.py --integrar

O recorte inicial é BR, por privacidade (não publica células de UF ou interseções
competência x percurso). Os resultados permanecem draft até auditoria real.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

ANOS=tuple(range(2019,2026))
COMP=tuple(f'C{i}' for i in range(1,6))
FIN=tuple(f'NU_NOTA_COMP{i}' for i in range(1,6))
PARES={'AV1_AV2':(1,2),'AV1_AV3':(1,3),'AV2_AV3':(2,3)}
ROTAS=('AV1_AV2','AV1_AV3','AV2_AV3','BANCA_AV4',
       'MULTIPLOS_PARES_COMPATIVEIS','AV1_AV2_COM_AV3_PRESENTE',
       'NAO_RECONCILIADO','SEM_DETALHE_SUFICIENTE')
MIN_N=30
ARQUIVO='IND_034_recorte_980_final'
CAMPOS=['TP_STATUS_REDACAO','NU_NOTA_REDACAO',*FIN]
for _av in (1,2,3,4):
    CAMPOS.extend([f'TP_STATUS_REDACAO_AV{_av}', f'NU_NOTA_AV{_av}'])
    CAMPOS.extend(f'NU_NOTA_COMP{i}_AV{_av}' for i in range(1,6))


def raiz():
    p=Path(__file__).resolve()
    return p.parents[2] if p.parent.name=='indicadores' and p.parent.parent.name=='src' else Path.cwd()


def numero(s):
    return pd.to_numeric(s.astype('string').str.strip().str.replace(',','.',regex=False),
                         errors='coerce').to_numpy(dtype='float64')


def optional_numero(s):
    return pd.to_numeric(s.astype('string').str.strip().str.replace(',','.',regex=False),
                         errors='coerce').to_numpy(dtype='float64')


def preencher_matriz(df, av):
    cols=[f'NU_NOTA_COMP{i}_AV{av}' for i in range(1,6)]
    return np.column_stack([optional_numero(df[c]) for c in cols])


def presenca(df,av):
    nota=df[f'NU_NOTA_AV{av}'].astype('string').str.strip().ne('').to_numpy()
    status=df[f'TP_STATUS_REDACAO_AV{av}'].astype('string').str.strip().ne('').to_numpy()
    return nota | status


def equivalente(a,b):
    return np.isfinite(a).all(axis=1) & np.isclose(a,b,atol=1.e-6,rtol=0).all(axis=1)


def identificar_rotas(df,final):
    """Audita compatibilidade dos vetores finais; não reconstrói decisão administrativa."""
    n=len(df)
    if not n: return np.empty(0,dtype=object),np.zeros(0,dtype=bool)
    mats={av:preencher_matriz(df,av) for av in (1,2,3,4)}
    tem3=presenca(df,3)
    tem4=presenca(df,4)
    matches={k:equivalente((mats[i]+mats[j])/2,final) for k,(i,j) in PARES.items()}
    banca_compativel=equivalente(mats[4],final)
    rotas=np.empty(n,dtype=object)
    inconsistencias=np.zeros(n,dtype=bool)
    for z in range(n):
        if tem4[z]:
            rotas[z]='BANCA_AV4' if banca_compativel[z] else 'NAO_RECONCILIADO'
            inconsistencias[z]=not banca_compativel[z]
        elif tem3[z]:
            possiveis=[k for k in ('AV1_AV3','AV2_AV3') if matches[k][z]]
            if len(possiveis)==1:
                rotas[z]=possiveis[0]
            elif len(possiveis)==2:
                rotas[z]='MULTIPLOS_PARES_COMPATIVEIS'
            elif matches['AV1_AV2'][z]:
                rotas[z]='AV1_AV2_COM_AV3_PRESENTE'
            elif any(np.isfinite(mats[av][z]).sum()<5 for av in (1,2,3)):
                rotas[z]='SEM_DETALHE_SUFICIENTE'
            else:
                rotas[z]='NAO_RECONCILIADO'; inconsistencias[z]=True
        elif matches['AV1_AV2'][z]:
            rotas[z]='AV1_AV2'
        elif not(np.isfinite(mats[1][z]).all() and np.isfinite(mats[2][z]).all()):
            rotas[z]='SEM_DETALHE_SUFICIENTE'
        else:
            rotas[z]='NAO_RECONCILIADO'; inconsistencias[z]=True
    return rotas,inconsistencias


def classificar_lote(lote):
    """Não contabiliza notas intermediárias de avaliadores como notas finais."""
    sel=(lote['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1').to_numpy()
         & np.isclose(numero(lote['NU_NOTA_REDACAO']),980.0,rtol=0,atol=1e-6))
    df=lote.loc[sel]
    if df.empty:
        return np.empty(0,dtype='int8'),np.empty(0,dtype=object),0
    final=np.column_stack([numero(df[c]) for c in FIN])
    if not np.isfinite(final).all() or (final<0).any() or (final>200).any():
        raise ValueError('Redação 980 com notas finais de competência inválidas.')
    if not np.isclose(final.sum(axis=1),980,rtol=0,atol=1e-6).all():
        raise ValueError('Redação 980 com soma das competências finais diferente de 980.')
    padrao=(np.isclose(final,200,atol=1e-6).sum(axis=1)==4)
    c180=np.isclose(final,180,atol=1e-6)
    padrao&=(c180.sum(axis=1)==1)
    idx=np.where(padrao,c180.argmax(axis=1)+1,0).astype('int8')
    rotas,anomalias=identificar_rotas(df,final)
    return idx,rotas,int(anomalias.sum())


def contagem_segura(contagens:dict[str,int], total:int):
    """Não libera células 1..29, nem permite reconstituí-las por complemento."""
    if total<MIN_N:
        return {'n_total':None,'categorias':{k:None for k in contagens},'suprimidas':list(contagens)}
    ocultas={k for k,n in contagens.items() if 0<n<MIN_N}
    if ocultas:
        candidatas=[k for k,n in contagens.items() if k not in ocultas and n>=MIN_N]
        if candidatas:
            # Complemento protege a reconstrução por diferença do total.
            ocultas.add(max(candidatas,key=lambda k:contagens[k]))
        else:
            # Não expor o total se uma única célula desconhecida for dedutível.
            return {'n_total':None,'categorias':{k:None for k in contagens},'suprimidas':list(contagens)}
    return {'n_total':total,'categorias':{k:(None if k in ocultas else int(n))
                                           for k,n in contagens.items()},
            'suprimidas':sorted(ocultas)}


def caminho_fonte(base,ano):
    if ano==2025:return base/'data'/'raw'/'2025'/'RESULTADOS_2025.csv'
    return base/'data'/'raw'/str(ano)/f'COMPETENCIAS_REDACAO_{ano}.csv'


def ler_lotes(path,bloco):
    if not path.is_file():raise FileNotFoundError(f'Microdados obrigatórios não encontrados: {path}')
    with path.open('rb') as f:enc='utf-8-sig' if f.read(3)==b'\xef\xbb\xbf' else 'latin-1'
    cols=pd.read_csv(path,sep=';',encoding=enc,nrows=0).columns.tolist()
    faltantes=sorted(set(CAMPOS)-set(cols))
    if faltantes:raise ValueError(f'{path.name}: faltam colunas para auditoria da nota definitiva: {faltantes}')
    for lote in pd.read_csv(path,sep=';',encoding=enc,dtype='string',usecols=CAMPOS,
                            chunksize=bloco,na_filter=False,keep_default_na=False,
                            low_memory=False):
        yield lote


def processar_ano(path,bloco):
    total=0;comp={k:0 for k in COMP};rotas={k:0 for k in ROTAS};outros=0;inconsistencias=0
    for lote in ler_lotes(path,bloco):
        idx,caminhos,nerr=classificar_lote(lote)
        total+=len(idx); outros+=int((idx==0).sum()); inconsistencias+=nerr
        v,c=np.unique(idx,return_counts=True)
        for i,n in zip(v,c):
            if i:comp[f'C{int(i)}']+=int(n)
        for k,n in zip(*np.unique(caminhos,return_counts=True)):
            rotas[str(k)]+=int(n)
    n_classificados=sum(comp.values())
    if n_classificados+outros!=total or sum(rotas.values())!=total:
        raise AssertionError('Não houve fechamento das contagens do recorte 980.')
    pub_comp=contagem_segura(comp,n_classificados)
    pub_rotas=contagem_segura(rotas,total)
    # Outros perfis positivos pequenos poderiam ser revelados por n980 - soma(C1..C5).
    if 0<outros<MIN_N:
        divulgadas=[k for k,v in pub_comp['categorias'].items() if v is not None and v>=MIN_N]
        if divulgadas:
            k=max(divulgadas,key=lambda z:pub_comp['categorias'][z])
            pub_comp['categorias'][k]=None
            pub_comp['suprimidas']=sorted(set(pub_comp['suprimidas'])|{k})
    linhas=[]
    for c in COMP:
        v=pub_comp['categorias'][c]
        linhas.append({'competencia':c,'n_980_competencia':v,
                       'percentual_entre_980_classificadas':round(100*v/n_classificados,6)
                          if v is not None and n_classificados else None,
                       'suprimido':v is None})
    # Oculta contagens que poderiam revelar o complemento pequeno por diferença.
    publicar_total = total>=MIN_N and not (0<outros<MIN_N or 0<n_classificados<MIN_N)
    publicar_outros = (outros==0 or outros>=MIN_N) and not (0<n_classificados<MIN_N)
    return {'status':'draft','n_980_total':total if publicar_total else None,
            'n_980_padrao_4x200_1x180':(pub_comp['n_total'] if outros==0 or outros>=MIN_N else None),
            'n_980_outros_perfis':outros if publicar_outros else None,
            'n_percursos_nao_reconciliados':inconsistencias if inconsistencias==0 or inconsistencias>=MIN_N else None,
            'resumo_competencias':linhas,
            'percursos_avaliacao':[
                {'percurso':k,'n_redacoes':pub_rotas['categorias'][k],
                 'suprimido':pub_rotas['categorias'][k] is None}
                for k in ROTAS],
            'privacidade':{'limiar':MIN_N,'complemento_competencias':pub_comp['suprimidas'],
                          'complemento_percursos':pub_rotas['suprimidas'],
                          'sem_cruzamento_percurso_competencia':True,
                          'ufs_nao_publicadas':True},
            'qa':{'soma_competencias_fechou':True,'total_percursos_fechou':True,
                  'fonte_colunas_finais':list(FIN),'soma_final_igual_980':True}}


def gravar_atomico_json(path:Path,conteudo):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,
                                         prefix='.tmp_ind034_',suffix='.json',
                                         delete=False) as f:
            tmp=Path(f.name);json.dump(conteudo,f,ensure_ascii=False,indent=2,allow_nan=False)
        os.replace(tmp,path)
    finally:
        if tmp and tmp.exists():tmp.unlink()


def integrar(base,saida):
    destino=base/'outputs'/'json'/'IND_034_competencia_unica_impede_1000.json'
    if not destino.is_file():raise FileNotFoundError(f'IND-034 obrigatório para integrar: {destino}')
    ind=json.loads(destino.read_text(encoding='utf-8-sig'))
    if ind.get('indicator_id')!='IND-034':raise ValueError('JSON principal não é o IND-034')
    alteracoes=[]
    for ano,item in saida['years'].items():
        if ano not in ind.get('years',{}):raise ValueError(f'IND-034 sem ano {ano}')
        # Reconciliação com POP_NEAR já auditada; recorte 980 é subconjunto.
        perto=int(ind['years'][ano]['recortes']['BR']['n_near'])
        if item['n_980_total'] is not None and item['n_980_total']>perto:
            raise ValueError(f'{ano}: N(980) excede POP_NEAR do IND-034')
        ind['years'][ano]['recorte_980_nota_final']=item
        dpath=base/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if dpath.exists():
            d=json.loads(dpath.read_text(encoding='utf-8-sig'))
            perf=d.get('pages',{}).get('high_performance',{})
            bloco=perf.get('single_blocker',{})
            if not isinstance(bloco,dict) or bloco.get('indicator_id')!='IND-034':
                raise ValueError(f'{ano}: bloco single_blocker IND-034 não encontrado no dashboard')
            bloco['recorte_980_nota_final_brasil']=item
            alteracoes.append((dpath,d))
    # Valida todos os dashboards antes de modificar qualquer um.
    ind.setdefault('methodology',{})['supplement_980']=saida['methodology']
    gravar_atomico_json(destino,ind)
    print(f'  IND-034 integrado: {destino}',flush=True)
    for dpath,d in alteracoes:
        gravar_atomico_json(dpath,d)
        print(f'  Dashboard {dpath.name} integrado (somente BR).',flush=True)


def autoteste():
    def row(c=1,rota='AV1_AV2',padrao=True):
        d={k:'' for k in CAMPOS}
        d['TP_STATUS_REDACAO']='1'; d['NU_NOTA_REDACAO']='980'
        fs=[200.]*5;fs[c-1]=180.
        if not padrao: fs=[190.,190.,200.,200.,200.]
        for i,val in enumerate(fs,1):d[f'NU_NOTA_COMP{i}']=str(val)
        mats={1:[200.]*5,2:[200.]*5,3:[200.]*5,4:list(fs)}
        if padrao:
            mats[2][c-1]=160.
            mats[3][c-1]=160.
        else:
            mats[2][0]=180.;mats[2][1]=180.
        if rota=='AV2_AV3':
            mats[1][c-1]=120.;mats[2][c-1]=200.;mats[3][c-1]=160.
        if rota=='MULTIPLOS_PARES_COMPATIVEIS':
            mats[1][c-1]=200.;mats[2][c-1]=200.;mats[3][c-1]=160.
        for k in (1,2,3,4):
            if k<=2 or (k==3 and rota in ('AV1_AV3','AV2_AV3','MULTIPLOS_PARES_COMPATIVEIS')) or (k==4 and rota=='BANCA_AV4'):
                d[f'NU_NOTA_AV{k}']=str(sum(mats[k]))
                d[f'TP_STATUS_REDACAO_AV{k}']='1'
                for i,v in enumerate(mats[k],1):d[f'NU_NOTA_COMP{i}_AV{k}']=str(v)
        return d
    dados=[row(1),row(2,rota='AV1_AV3'),row(3,rota='AV2_AV3'),
           row(4,rota='MULTIPLOS_PARES_COMPATIVEIS'),row(5,rota='BANCA_AV4'),
           row(3,padrao=False)]
    z=pd.DataFrame(dados)
    idx,rotas,err=classificar_lote(z)
    assert idx.tolist()==[1,2,3,4,5,0],(idx,rotas)
    assert rotas.tolist()==['AV1_AV2','AV1_AV3','AV2_AV3',
           'MULTIPLOS_PARES_COMPATIVEIS','BANCA_AV4','AV1_AV2'],rotas
    assert err==0
    x=contagem_segura({'C1':29,'C2':40,'C3':0,'C4':50,'C5':1},120)
    assert x['categorias']['C1'] is None and x['categorias']['C5'] is None
    assert sum(v is None for v in x['categorias'].values())>=3
    x=contagem_segura({'C1':1,'C2':0,'C3':0,'C4':0,'C5':0},1)
    assert x['n_total'] is None and all(v is None for v in x['categorias'].values())
    z.loc[0,'NU_NOTA_COMP3']='180'
    try:classificar_lote(z)
    except ValueError:pass
    else:raise AssertionError('Falta de controle da soma das notas definitivas.')
    # Integração real em arquivos temporários, inclusive teste de escrita CSV/JSON.
    with tempfile.TemporaryDirectory(prefix='autoteste_034_980_') as temp:
        src=Path(temp)/'COMPETENCIAS_REDACAO_2019.csv'
        pd.DataFrame(dados*40).to_csv(src,sep=';',index=False,encoding='utf-8-sig')
        agregado=processar_ano(src,1000)
        assert agregado['n_980_total']==240 and agregado['n_980_padrao_4x200_1x180']==200
        assert sum(int(v['n_980_competencia'] or 0) for v in agregado['resumo_competencias'] if not v['suprimido']) <= 200
    print('AUTOTESTE IND-034 (recorte 980) APROVADO | nota final + AV1/AV2/AV3/AV4 | privacidade')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--autoteste',action='store_true')
    ap.add_argument('--anos',nargs='+',type=int,default=list(ANOS))
    ap.add_argument('--bloco',type=int,default=100_000)
    ap.add_argument('--integrar',action='store_true',help='Incorpora recorte ao JSON IND-034 e dashboards já existentes.')
    ap.add_argument('--raiz',type=Path,default=None)
    args=ap.parse_args()
    if args.autoteste:autoteste();return
    if args.bloco<1000:ap.error('--bloco deve ser >= 1000')
    if len(set(args.anos))!=len(args.anos) or any(a not in ANOS for a in args.anos):
        ap.error('--anos inválidos/repetidos')
    base=args.raiz.resolve() if args.raiz else raiz()
    saida={'indicator_id':'IND-034','supplement_id':'IND-034-980',
        'titulo':'Recorte exclusivo da nota definitiva 980: competência limitante',
        'status':'draft', 'gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'population':'POP_980_FINAL','geography':'BR',
        'methodology':{'universe':'TP_STATUS_REDACAO=1 e NU_NOTA_REDACAO FINAL=980',
            'competence_source':'NU_NOTA_COMP1..5 definitivas; NÃO recalcular com AV1/AV2',
            'pathway':'AV1+AV2; AV1+AV3; AV2+AV3; banca AV4 conferidos por comparação do vetor de competências quando disponível; empates sinalizados',
            'pattern':'4 competências=200 e 1=180; outros perfis não atribuídos a uma competência',
            'publication':'Brasil por ano; supressão <30 e complementar; sem cruzamento por percurso ou UF',
            'privacy':'draft sujeito a revisão cruzada e acadêmica'},'years':{}}
    for ano in args.anos:
        path=caminho_fonte(base,ano)
        print(f'IND-034 | recorte 980 | {ano}: {path.name}',flush=True)
        item=processar_ano(path,args.bloco)
        item['ano']=ano;item['fonte']=path.name
        saida['years'][str(ano)]=item
        print(f'  N(980)={item["n_980_total"]}; casos padrão={item["n_980_padrao_4x200_1x180"]}; '
              f'percurso não reconciliado={item["n_percursos_nao_reconciliados"]}',flush=True)
    dest=base/'outputs'/'json'/f'{ARQUIVO}.json'
    csvpath=base/'outputs'/'indicadores'/f'{ARQUIVO}.csv'
    gravar_atomico_json(dest,saida)
    csvpath.parent.mkdir(parents=True,exist_ok=True)
    with csvpath.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['ano','uf','competencia','n_980_total','n_980_padrao_4x200_1x180',
                        'n_980_competencia','percentual_entre_980_classificadas','suprimido'],delimiter=';')
        w.writeheader()
        for ano,v in saida['years'].items():
            for c in v['resumo_competencias']:
                w.writerow({'ano':ano,'uf':'BR','competencia':c['competencia'],
                            'n_980_total':v['n_980_total'],
                            'n_980_padrao_4x200_1x180':v['n_980_padrao_4x200_1x180'],
                            'n_980_competencia':c['n_980_competencia'],
                            'percentual_entre_980_classificadas':c['percentual_entre_980_classificadas'],
                            'suprimido':c['suprimido']})
    print(f'  Recorte independente: {dest} / {csvpath}',flush=True)
    if args.integrar:integrar(base,saida)
    print('IND-034: RECORTE 980 CONCLUÍDO EM DRAFT (aguarda validação real e revisão de privacidade).')


if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,AssertionError) as exc:
        raise SystemExit(f'ERRO IND-034 recorte 980: {exc}') from exc
