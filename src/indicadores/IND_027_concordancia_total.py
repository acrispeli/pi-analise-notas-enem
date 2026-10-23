#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-027 — Concordância absoluta das notas totais AV1/AV2 (ENEM 2019–2025).

Métricas: ICC(A,1) de McGraw & Wong (1996), two-way, absolute agreement,
single measurement, e correlação de Pearson. ICC(A,1) compartilha a expressão
numérica usual do ICC(2,1), mas o modelo adotado considera as funções AV1 e AV2
como dois avaliadores fixos. Estatísticas obtidas de todos os pares POP_EVALUATOR.

Exige IND-020 para conferência dos denominadores e IND-026 já integrado aos
sete dashboards para atualizar a interface. Não executar em paralelo com outros
indicadores que também escrevam os dashboards.

Uso na raiz do projeto:
  python src/indicadores/IND_027_concordancia_total.py
  python src/indicadores/IND_027_concordancia_total.py --somente-modulo
  python src/indicadores/IND_027_concordancia_total.py --sobrescrever
"""
from __future__ import annotations

import argparse
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
import IND_020_diferenca_total_av1_av2 as base

ANOS = tuple(range(2019, 2026))
UFS = tuple(base.UFS)
IND = 'IND-027'
ARQUIVO = 'IND_027_concordancia_total'
MIN_N = 30
VERSAO = '2.26.0-' + '-'.join(f'ind{i:03d}' for i in range(1,28))
METODO = 'icc_a1_two_way_absolute_agreement_single_e_pearson_momentos_exatos'
NOTAS = (
    'Coeficiente de correlação intraclasse de concordância absoluta, medida única, '
    'ICC(A,1) de modelo bidirecional com AV1 e AV2 tratados como funções fixas; '
    'mais correlação linear de Pearson. Os pares são as notas totais válidas de '
    'POP_EVALUATOR, sem restringir a redações com TP_STATUS_REDACAO=1. '
    'ICC penaliza diferença sistemática de nível entre avaliadores; Pearson mede '
    'associação e não concordância absoluta. ICC pode ser negativo ou indefinido; '
    'Pearson é indefinido se a variância de um avaliador é zero. Nenhum dos '
    'coeficientes atribui erro ou mede qualidade individual de corretores. '
    'A UF é o local de prova; consolidado 2019–2025 agrega participações, não '
    'pessoas únicas. A concordância histórica é recalculada sobre os momentos '
    'combinados, nunca a média dos ICCs anuais. Apenas estatísticas agregadas '
    'com pelo menos 30 pares; dados individuais não são exportados. '
    'Dados draft; revisão acadêmica, comparabilidade temporal e privacidade pendentes.'
)


def ler_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def gravar_json(path: Path, obj: dict) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def recorte(periodo: dict, uf: str) -> dict:
    if uf == 'BR':
        return periodo['brasil']
    return next(v for v in periodo['ufs'] if v['uf'] == uf)


def nao_negativo(v: float, escala: float = 1.0) -> float:
    tol = max(1e-8, 5e-12 * escala)
    if v < -tol:
        raise ArithmeticError(f'Soma de quadrados negativa além da tolerância: {v}')
    return max(0.0, v)


class MomentosConcordancia:
    """Acumulação O(1) por grupo, preservando pares X=AV1 e Y=AV2.

    ANOVA de duas vias, desenho completo n participantes x k=2 avaliadores:
      MSR=SS_sujeitos/(n-1), MSC=SS_avaliadores/(k-1),
      MSE=SS_residual/((n-1)(k-1)).
    ICC(A,1)=(MSR-MSE)/(MSR+(k-1)*MSE+k*(MSC-MSE)/n).
    """
    __slots__ = ('n', 'sx', 'sy', 'sx2', 'sy2', 'sxy')

    def __init__(self):
        self.n = 0
        self.sx = 0.0
        self.sy = 0.0
        self.sx2 = 0.0
        self.sy2 = 0.0
        self.sxy = 0.0

    def adicionar(self, x: np.ndarray, y: np.ndarray) -> None:
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        if x.shape != y.shape or x.ndim != 1:
            raise ValueError('AV1 e AV2 devem ter a mesma dimensão unidimensional')
        if not x.size:
            return
        if (not np.isfinite(x).all() or not np.isfinite(y).all() or
                (x < 0).any() or (x > 1000).any() or (y < 0).any() or (y > 1000).any()):
            raise ValueError('Notas AV1/AV2 inválidas fora de [0,1000]')
        self.n += int(x.size)
        self.sx += float(x.sum(dtype=np.float64))
        self.sy += float(y.sum(dtype=np.float64))
        self.sx2 += float(np.dot(x, x))
        self.sy2 += float(np.dot(y, y))
        self.sxy += float(np.dot(x, y))

    def combinar(self, outro: 'MomentosConcordancia') -> None:
        for campo in self.__slots__:
            setattr(self, campo, getattr(self, campo) + getattr(outro, campo))

    def resultado(self) -> dict:
        n = self.n
        if n < MIN_N:
            raise ValueError(f'Grupo com apenas {n} pares; mínimo {MIN_N}')
        # Decomposição ANOVA exata em termos de momentos.
        total = self.sx + self.sy
        ss_sujeitos = nao_negativo(
            0.5*(self.sx2+self.sy2+2*self.sxy)-total**2/(2*n),
            escala=self.sx2+self.sy2)
        ss_avaliadores = (self.sx-self.sy)**2/(2*n)
        ss_resid = nao_negativo(
            0.5*(self.sx2+self.sy2-2*self.sxy)-ss_avaliadores,
            escala=self.sx2+self.sy2)
        msr = ss_sujeitos/(n-1)
        msc = ss_avaliadores
        mse = ss_resid/(n-1)
        denom = msr + mse + 2*(msc-mse)/n
        if denom < -1e-8:
            raise ArithmeticError('Denominador ICC negativo: verificar fonte')
        icc = None if denom <= 1e-10 else (msr-mse)/denom
        # O estimador ANOVA de ICC(A,1) pode ficar ligeiramente abaixo de -1
        # em amostras com anticorrelação extrema; não truncar o estimador.
        if icc is not None and not math.isfinite(icc):
            raise ArithmeticError('ICC não finito')

        sxx = nao_negativo(self.sx2-self.sx**2/n, escala=self.sx2)
        syy = nao_negativo(self.sy2-self.sy**2/n, escala=self.sy2)
        sxy_c = self.sxy-self.sx*self.sy/n
        pearson = None if min(sxx, syy) <= 1e-10 else sxy_c/math.sqrt(sxx*syy)
        if pearson is not None and not -1.00001 <= pearson <= 1.00001:
            raise ArithmeticError(f'Pearson fora do intervalo [-1,1]: {pearson}')
        return {
            'n_pares_validos':n,
            'icc_concordancia_absoluta':None if icc is None else round(icc,6),
            'situacao_icc':'ok' if icc is not None else 'indefinido_sem_variacao',
            'correlacao_pearson':None if pearson is None else round(max(-1.0,min(1.0,pearson)),6),
            'situacao_pearson':'ok' if pearson is not None else 'indefinido_variancia_zero',
            'modelo':'ICC(A,1)',
            'concordancia':'absoluta',
            'unidade':'nota_total_0_1000',
            'sem_dados_individuais':True
        }


def criar_grupos() -> dict:
    return {u:MomentosConcordancia() for u in ('BR', *UFS)}


def acumular_por_uf(grupos:dict, ufs:np.ndarray, x:np.ndarray, y:np.ndarray, ano:int) -> None:
    if len(ufs) != len(x) or len(ufs) != len(y):
        raise AssertionError('Comprimento das notas e UFs difere')
    if not np.isin(ufs, UFS).all():
        raise ValueError(f'{ano}: UF ausente ou desconhecida')
    grupos['BR'].adicionar(x,y)
    for uf in np.unique(ufs):
        filtro = ufs == uf
        grupos[str(uf)].adicionar(x[filtro], y[filtro])


def validar_referencias(raiz:Path):
    path=raiz/'outputs/json/IND_020_diferenca_total_av1_av2.json'
    if not path.is_file():
        raise FileNotFoundError(f'IND-020 obrigatório para conferir população: {path}')
    r=ler_json(path)
    if r.get('indicator',{}).get('id')!='IND-020' or [p.get('ano') for p in r.get('years',[])]!=list(ANOS):
        raise ValueError('IND-020 ausente, inválido ou com anos incompletos')
    if 'historical' not in r:
        raise ValueError('IND-020 não possui histórico')
    return r


def carregar_dashboards(raiz:Path) -> dict:
    dados={}
    for ano in ANOS:
        path=raiz/'outputs/json'/f'dashboard_enem_{ano}.json'
        if not path.is_file():
            raise FileNotFoundError(f'Dashboard obrigatório: {path}')
        d=ler_json(path)
        if d.get('meta',{}).get('year')!=ano or d['meta'].get('data_status')!='draft':
            raise ValueError(f'Dashboard {ano} inválido')
        if d.get('quality',{}).get('ind026_validation',{}).get('status')!='ok':
            raise ValueError(f'IND-026 precisa estar integrado ao dashboard {ano}')
        for sec in ('evaluators','temporal','methodology'):
            if not isinstance(d.get('pages',{}).get(sec),dict):
                raise ValueError(f'Falta pages.{sec} no dashboard {ano}')
        dados[ano]=d
    return dados


def conferir_fontes(raiz:Path) -> None:
    for ano in ANOS:
        geo,aval=base.fonte_ano(raiz,ano)
        if not aval.is_file() or (geo is not None and not geo.is_file()):
            raise FileNotFoundError(f'Fonte de {ano} ausente: {geo} / {aval}')
        cols=['NU_NOTA_AV1','NU_NOTA_AV2']
        cols=(['NU_INSCRICAO','NU_ANO'] if geo else ['NU_ANO','SG_UF_PROVA'])+cols
        base.validar_cabecalho(aval, tuple(cols))
        if geo is not None:
            base.validar_cabecalho(geo, ('NU_INSCRICAO','NU_ANO','SG_UF_PROVA'))


def processar_ano(raiz:Path, ano:int, g:dict, hist:dict, bloco:int, tempdir:Path) -> dict:
    geo,aval=base.fonte_ano(raiz,ano)
    cols=(['NU_INSCRICAO','NU_ANO'] if geo else ['NU_ANO','SG_UF_PROVA'])+['NU_NOTA_AV1','NU_NOTA_AV2']
    qa={'arquivo_avaliadores':aval.name,
        'arquivo_geografia':geo.name if geo else aval.name,
        'juncao':'NU_INSCRICAO+NU_ANO' if geo else 'mesma_linha',
        'n_linhas_fonte':0,'n_notas_pareadas':0,'n_notas_incompletas':0,
        'n_invalidas':0,'n_elegiveis_sem_juncao':0}
    db=None
    try:
        if geo is not None:
            db=sqlite3.connect(tempdir/f'geo_ind027_{ano}.sqlite')
            db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
            db.execute('PRAGMA cache_size=-64000')
            qa['n_linhas_geografia']=base.construir_geo(db,geo,ano,bloco)
        print(f'IND-027 | {ano}: lendo {aval.name}',flush=True)
        for df in base.ler_blocos(aval,cols,bloco):
            qa['n_linhas_fonte']+=len(df)
            if df['NU_ANO'].str.strip().ne(str(ano)).any():
                raise ValueError(f'{ano}: NU_ANO incorreto')
            if db is not None:
                keys=df['NU_INSCRICAO'].str.strip()
                if keys.eq('').any():
                    raise ValueError(f'{ano}: NU_INSCRICAO vazia')
                try:
                    db.executemany('INSERT INTO vistos VALUES (?)',((k,) for k in keys.tolist()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f'{ano}: inscrição duplicada') from exc
            a=df['NU_NOTA_AV1'].str.strip();b=df['NU_NOTA_AV2'].str.strip()
            filled=a.ne('')&b.ne('')
            qa['n_notas_incompletas']+=int((~filled).sum())
            if not filled.any():
                continue
            x=base.digitos(a[filled]);y=base.digitos(b[filled])
            good=x.between(0,1000)&y.between(0,1000)
            qa['n_invalidas']+=int((~good).sum())
            if not good.all():
                raise ValueError(f'{ano}: há notas AV1/AV2 preenchidas porém inválidas')
            x=x.to_numpy(dtype=np.float64)
            y=y.to_numpy(dtype=np.float64)
            qa['n_notas_pareadas']+=len(x)
            if db is not None:
                ids=df.loc[filled,'NU_INSCRICAO'].str.strip().tolist()
                db.execute('CREATE TEMP TABLE lote (key TEXT PRIMARY KEY, ordem INTEGER NOT NULL) WITHOUT ROWID')
                try:
                    db.executemany('INSERT INTO lote VALUES (?,?)', ((k,i) for i,k in enumerate(ids)))
                    rows=db.execute('SELECT l.ordem,g.uf FROM lote l JOIN geo g ON g.key=l.key AND g.ano=?',
                                    (ano,)).fetchall()
                finally:
                    db.execute('DROP TABLE lote')
                if len(rows)!=len(ids):
                    qa['n_elegiveis_sem_juncao']+=len(ids)-len(rows)
                    raise ValueError(f'{ano}: {len(ids)-len(rows)} elegíveis sem UF')
                ufs=np.empty(len(ids),dtype='<U3')
                for pos, uf in rows:
                    ufs[int(pos)]=str(uf).strip().upper()
            else:
                ufs=df.loc[filled,'SG_UF_PROVA'].str.strip().str.upper().to_numpy(dtype=str)
            acumular_por_uf(g,ufs,x,y,ano)
            acumular_por_uf(hist,ufs,x,y,ano)
        if qa['n_notas_pareadas']!=g['BR'].n:
            raise AssertionError(f'{ano}: N nacional diverge do número processado')
        if sum(g[u].n for u in UFS)!=g['BR'].n:
            raise AssertionError(f'{ano}: soma de UFs diverge do Brasil')
        print(f'  Pares AV1/AV2: {g["BR"].n:,}',flush=True)
        return qa
    finally:
        if db is not None:
            db.close()


def compilar(grupos:dict, periodo:int|str, ref:dict) -> dict:
    def resumo(g:MomentosConcordancia):
        return {'n_pop_evaluator':g.n,'populacao':'POP_EVALUATOR',**g.resultado()}
    p={'brasil':resumo(grupos['BR']),
       'ufs':[{'uf':u,**resumo(grupos[u])} for u in UFS],
       'qualidade':{'status':'ok','soma_27_ufs_igual_brasil':True,
                   'conferencia_denominador_ind020':True,'minimo_grupo':MIN_N}}
    if isinstance(periodo,int):
        p['ano']=periodo
    else:
        p['periodo']=str(periodo)
    for uf in ('BR',*UFS):
        n=recorte(p,uf)['n_pop_evaluator']
        if n!=recorte(ref,uf)['n_avaliacoes_pareadas']:
            raise ValueError(f'{periodo}/{uf}: n={n} difere do IND-020 ({recorte(ref,uf)["n_avaliacoes_pareadas"]})')
    if sum(g['n_pop_evaluator'] for g in p['ufs'])!=p['brasil']['n_pop_evaluator']:
        raise AssertionError('Somatório UF não fecha')
    return p


def atualizar_dashboard(d:dict, p:dict, anos:list[dict], hist:dict, gerado:str) -> dict:
    novo=deepcopy(d)
    ev=novo['pages']['evaluators']
    ev['icc']={'indicator_id':IND,'population':'POP_EVALUATOR',
               'method':METODO,'model':'ICC(A,1)',
               'brasil':deepcopy(p['brasil']),'by_uf':deepcopy(p['ufs']),
               'note':NOTAS}
    ev['status']='partial'
    ev['reason']='IND-020 a IND-027 disponíveis; outras análises podem estar pendentes'
    novo['pages']['temporal']['ind027']={
        'indicator_id':IND,'population':'POP_EVALUATOR',
        'national_by_year':[{'year':y['ano'],**deepcopy(y['brasil'])} for y in anos],
        'period_total':deepcopy(hist['brasil']),
        'period_by_uf':deepcopy(hist['ufs']),
        'note':'ICC e Pearson do período recalculados de todos os pares; não média de coeficientes.'}
    novo['pages']['methodology']['ind027']={
        'definition':'Concordância da nota total do primeiro e segundo avaliadores',
        'population':'POP_EVALUATOR (ambas as notas totais válidas, 0–1000)',
        'method':METODO, 'model':'ICC(A,1)',
        'icc_formula':'(MSR-MSE)/(MSR+(k-1)*MSE+k*(MSC-MSE)/n), k=2',
        'correlation':'Pearson entre NU_NOTA_AV1 e NU_NOTA_AV2',
        'join':'NU_INSCRICAO+NU_ANO em 2019–2024; mesma linha em 2025',
        'minimum_pair_count':MIN_N,'limitations':NOTAS}
    novo['quality']['ind027_validation']={
        'status':'ok','source_indicator':'IND-020',
        'n_pop_evaluator_brasil':p['brasil']['n_pop_evaluator'],
        'soma_27_ufs_igual_brasil':True,
        'n_registros_individuais_exportados':0,'sem_amostragem':True,
        'revisao_academica_pendente':True,'revisao_privacidade_pendente':True}
    novo['meta']['analysis_version']=VERSAO
    novo['meta']['generated_at']=gerado
    novo['meta']['data_status']='draft'
    aviso='IND-027: ICC(A,1) absoluto e Pearson AV1/AV2 na POP_EVALUATOR; revisão acadêmica e de privacidade pendentes.'
    if aviso not in novo['meta'].setdefault('warnings',[]):
        novo['meta']['warnings'].append(aviso)
    return novo


def executar(raiz:Path,bloco:int=100_000,somente_modulo:bool=False,sobrescrever:bool=False) -> dict:
    if bloco<1:
        raise ValueError('--bloco deve ser positivo')
    ref=validar_referencias(raiz)
    conferir_fontes(raiz)
    dashboards={} if somente_modulo else carregar_dashboards(raiz)
    j=raiz/'outputs/json'
    c=raiz/'outputs/indicadores'
    destinos=[j/f'{ARQUIVO}.json',c/f'{ARQUIVO}.csv']
    if not sobrescrever:
        for path in destinos:
            if path.exists():
                raise FileExistsError(f'IND-027 já existe: {path}; use --sobrescrever')
        for ano,d in dashboards.items():
            if 'ind027_validation' in d['quality'] or 'icc' in d['pages']['evaluators']:
                raise FileExistsError(f'IND-027 já integrado no dashboard {ano}')
    hashes={ano:hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
            for ano in ANOS} if not somente_modulo else {}
    saidas=[]
    hist_grupos=criar_grupos()
    source_qa={}
    out=raiz/'outputs'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ind027_sql_',dir=out) as tmp:
        for ano,ref_periodo in zip(ANOS,ref['years']):
            grupos=criar_grupos()
            qa=processar_ano(raiz,ano,grupos,hist_grupos,bloco,Path(tmp))
            saida=compilar(grupos,ano,ref_periodo)
            saida['qualidade_fonte']=qa
            saidas.append(saida)
            source_qa[str(ano)]=qa
    hist=compilar(hist_grupos,'2019-2025',ref['historical'])
    for uf in ('BR',*UFS):
        n_anos=sum(recorte(p,uf)['n_pop_evaluator'] for p in saidas)
        if n_anos!=recorte(hist,uf)['n_pop_evaluator']:
            raise AssertionError(f'{uf}: histórico não coincide com anos')
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    modulo={
        'meta':{'indicator_id':IND,'module_schema_version':'ind027-module-1.0.0',
                'analysis_version':VERSAO,'dataset_version':'enem-2019-2025-csv-publico',
                'generated_at':gerado,'data_status':'draft',
                'source_indicator':'IND-020', 'geographic_dimension':'SG_UF_PROVA',
                'population_definition':'POP_EVALUATOR: ambas notas totais AV1/AV2 preenchidas e válidas em [0,1000]',
                'method':METODO,'icc_model':'ICC(A,1)','minimum_group_count':MIN_N,
                'source_qa':source_qa,
                'publication_status':'draft; revisão acadêmica e privacidade pendentes',
                'notes':NOTAS},
        'indicator':{'id':IND,'name':'Concordância total','unit':'icc',
                     'dashboard_json_path':'pages.evaluators.icc','visualization':'KPI'},
        'years':saidas,'historical':hist,
        'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    novos={ano:atualizar_dashboard(dashboards[ano],saidas[i],saidas,hist,gerado)
           for i,ano in enumerate(ANOS)} if not somente_modulo else {}
    for ano,d in novos.items():
        if d['meta']['year']!=ano or d['quality']['ind026_validation']['status']!='ok':
            raise ValueError(f'IND-026 não foi preservado no dashboard {ano}')
        for caminho in (raiz/'04_resultados_analises.schema.json',
                        raiz/'docs/04_resultados_analises.schema.json'):
            if caminho.is_file():
                try:
                    import jsonschema
                except ImportError:
                    break
                jsonschema.validate(d,ler_json(caminho))
                break
    linhas=[]
    for p in (*saidas,hist):
        periodo=str(p.get('ano','2019-2025'))
        for uf,g in [('BR',p['brasil']),*((z['uf'],z) for z in p['ufs'])]:
            linhas.append({
                'indicador_id':IND,'periodo':periodo,
                'abrangencia':'BR' if uf=='BR' else 'UF','uf':uf,
                'populacao':'POP_EVALUATOR','n_pares_validos':g['n_pares_validos'],
                'icc_concordancia_absoluta':g['icc_concordancia_absoluta'],
                'situacao_icc':g['situacao_icc'],
                'correlacao_pearson':g['correlacao_pearson'],
                'situacao_pearson':g['situacao_pearson'],
                'modelo':'ICC(A,1)','metodo':METODO})
    if len(linhas)!=224:
        raise AssertionError(f'Esperadas 224 linhas CSV; obtidas {len(linhas)}')
    json.dumps(modulo,allow_nan=False)
    with tempfile.TemporaryDirectory(prefix='.ind027_stage_',dir=out) as tmp:
        td=Path(tmp)
        fonte_json=td/f'{ARQUIVO}.json'
        fonte_csv=td/f'{ARQUIVO}.csv'
        gravar_json(fonte_json,modulo)
        with fonte_csv.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
            w.writeheader();w.writerows(linhas)
        gravacoes=[(fonte_json,destinos[0]),(fonte_csv,destinos[1])]
        for ano,d in novos.items():
            arquivo=td/f'dashboard_enem_{ano}.json'
            gravar_json(arquivo,d)
            gravacoes.append((arquivo,j/arquivo.name))
        # A checagem de hash protege contra indicadores concorrentes antes de gravar.
        for ano in ANOS:
            if not somente_modulo:
                atual=hashlib.sha256((j/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()
                if atual!=hashes[ano]:
                    raise RuntimeError(f'Dashboard {ano} modificado por outro processo. Nada foi gravado.')
        for origem,destino in gravacoes:
            destino.parent.mkdir(parents=True,exist_ok=True)
            os.replace(origem,destino)
    print('IND-027 concluído: 224 recortes, 224 linhas CSV e módulo JSON.')
    print('Saídas:',destinos[0],destinos[1])
    if not somente_modulo:
        print('Dashboards 2019–2025 atualizados; outros indicadores preservados.')
    return modulo


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path.cwd(),help='raiz do projeto')
    ap.add_argument('--bloco',type=int,default=100_000,help='tamanho de bloco CSV')
    ap.add_argument('--somente-modulo',action='store_true',help='não modifica dashboards')
    ap.add_argument('--sobrescrever',action='store_true',help='sobrescreve as saídas próprias do IND-027')
    a=ap.parse_args()
    executar(a.base.resolve(),a.bloco,a.somente_modulo,a.sobrescrever)


if __name__ == '__main__':
    main()
