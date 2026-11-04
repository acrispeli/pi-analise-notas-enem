"""ENEM IND-055..072 | núcleo compartilhado; separa execução de preparação.

Sem acesso à internet nem escrita em dashboards por padrão. Nunca inventa vínculo
participante×cluster: análises supervisionadas exigem ponte validada externamente.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ANOS = range(2019, 2026)
UFS = set('AC AL AP AM BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()) | {'BR'}
BASES = {
    55: ('perfil_socio_nota','pages.socioeconomic.cluster_total'),
    56: ('perfil_socio_competencias','pages.socioeconomic.cluster_competencies'),
    57: ('perfil_socio_alto_desempenho','pages.socioeconomic.cluster_high_performance'),
    58: ('perfil_socio_perdas','pages.socioeconomic.cluster_losses'),
    59: ('perfil_socio_divergencia','pages.socioeconomic.cluster_reviewer_divergence'),
    60: ('modelo_nota_total','pages.ml.total_score_model'),
    61: ('modelos_competencias','pages.ml.competency_models'),
    62: ('importancia_permutacao_shap','pages.ml.feature_importance'),
    63: ('qualidade_modelo_subgrupos','pages.ml.model_subgroup_quality'),
    64: ('evolucao_nota','pages.temporal.total_score'),
    65: ('evolucao_competencias','pages.temporal.competencies'),
    66: ('evolucao_quase_1000','pages.temporal.high_performance'),
    67: ('evolucao_divergencias','pages.temporal.reviewers'),
    68: ('evolucao_perfis_socioeconomicos','pages.temporal.socio_clusters'),
    69: ('taxa_juncao','quality.join_diagnostics'),
    70: ('valores_ausentes','quality.missingness'),
    71: ('diagnostico_celulas_pequenas','quality.suppression'),
    72: ('versao_proveniencia','meta'),
}

class Pendencia(RuntimeError):
    """Pré-condição metodológica ou técnica não atendida: não cria resultados fictícios."""


def nome(ind):
    return f'IND_{ind:03d}_{BASES[ind][0]}'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path,chunk=2*1024*1024):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(chunk):h.update(block)
    return h.hexdigest()


def csv_path(root,ind):
    folder=root/'outputs/indicadores'
    items=sorted(folder.glob(f'IND_{ind:03d}_*.csv'))
    if len(items)!=1:
        raise Pendencia(f'IND-{ind:03d}: esperado 1 CSV, encontrados {len(items)} ({items})')
    return items[0]


def read_csv(root,ind):
    file=csv_path(root,ind)
    with file.open(encoding='utf-8-sig',newline='') as fp:
        return list(csv.DictReader(fp,delimiter=';'))


def as_float(value):
    return None if value is None or str(value).strip()=='' else float(value)


def as_int(value):
    return None if value is None or str(value).strip()=='' else int(float(value))


def recent_year(r):
    p=str(r.get('periodo',r.get('ano','')))
    return int(p) if re.fullmatch(r'20\d{2}',p) else None


def brasil_rows(root,ind):
    return [r for r in read_csv(root,ind) if r.get('uf','BR')=='BR' and recent_year(r) in ANOS]


def metric_rows(ind, rows, units, notes=None, status='draft'):
    return {'indicator_id':f'IND-{ind:03d}','slug':nome(ind),'status':status,
            'generated_at':now(),'dashboard_target':BASES[ind][1],
            'population_note':units,'method_note':notes or '',
            'scope':'2019–2025; participações e não pessoas únicas',
            'results':rows,'review':'pendente_revisao_academica_e_privacidade_contextual'}


def path_existing(root,ind):
    try:return csv_path(root,ind)
    except Pendencia:return None


def temporal(ind,root):
    rows=[]
    if ind==64:
        means={recent_year(r):r for r in brasil_rows(root,2)}
        medians={recent_year(r):r for r in brasil_rows(root,3)}
        for year in ANOS:
            a,b=means.get(year),medians.get(year)
            if not a or not b:
                rows.append({'ano':year,'status':'indisponivel','motivo':'IND-002/003 ausente'});continue
            na,nb=as_int(a['n_validas']),as_int(b['n_validas'])
            if na!=nb:raise ValueError(f'IND-064 {year}: denominadores IND-002/003 divergentes')
            rows.append({'ano':year,'status':'ok','n_validas':na,'media':as_float(a['nota_media']),
                         'mediana':as_float(b['nota_mediana'])})
    elif ind==65:
        means={(recent_year(r),r['competencia']):r for r in brasil_rows(root,9)}
        medians={(recent_year(r),r['competencia']):r for r in brasil_rows(root,10)}
        for year in ANOS:
            for comp in ('C1','C2','C3','C4','C5'):
                a,b=means.get((year,comp)),medians.get((year,comp))
                if not a or not b:
                    rows.append({'ano':year,'competencia':comp,'status':'indisponivel'});continue
                if as_int(a['n_validas'])!=as_int(b['n_validas']):
                    raise ValueError(f'IND-065 {year}/{comp}: denominadores diferentes')
                rows.append({'ano':year,'competencia':comp,'status':'ok','n_validas':as_int(a['n_validas']),
                             'media':as_float(a['media']),'mediana':as_float(b['mediana'])})
    elif ind==66:
        losses={(recent_year(r),r['competencia']):r for r in brasil_rows(root,31)
                if r.get('faixa')=='POP_NEAR_TOTAL' and r.get('competencia') in ('C1','C2','C3','C4','C5')}
        freq={(recent_year(r),r['competencia']):r for r in brasil_rows(root,32)}
        for year in ANOS:
            for comp in ('C1','C2','C3','C4','C5'):
                a,b=losses.get((year,comp)),freq.get((year,comp))
                if not a or not b:
                    rows.append({'ano':year,'competencia':comp,'status':'indisponivel'});continue
                n1,n2=as_int(a['n_redacoes']),as_int(b['n_redacoes'])
                if n1!=n2:raise ValueError(f'IND-066 {year}/{comp}: N POP_NEAR discordante')
                rows.append({'ano':year,'competencia':comp,'status':'ok','n_near':n1,
                             'perda_media':as_float(a['media_perda']),
                             'frequencia_desconto':as_float(b['frequencia_desconto']),
                             'n_com_desconto':as_int(b['n_com_desconto'])})
    elif ind==67:
        from20={}
        for r in brasil_rows(root,20):
            ano=recent_year(r)
            if ano not in from20:from20[ano]=r
            elif any(r[x]!=from20[ano][x] for x in ('n_avaliacoes_pareadas','media','mediana')):
                raise ValueError(f'IND-067 {ano}: estatísticas do histograma IND-020 divergentes')
        from22={recent_year(r):r for r in brasil_rows(root,22)}
        for year in ANOS:
            a,b=from20.get(year),from22.get(year)
            if not a or not b:
                rows.append({'ano':year,'status':'indisponivel'});continue
            if as_int(a['n_avaliacoes_pareadas'])!=as_int(b['n_pop_evaluator']):
                raise ValueError(f'IND-067 {year}: denominadores avaliadores divergem')
            rows.append({'ano':year,'status':'ok','n_pareadas':as_int(a['n_avaliacoes_pareadas']),
                         'diferenca_media_absoluta':as_float(a['media']),
                         'diferenca_mediana_absoluta':as_float(a['mediana']),
                         'percentual_discrepancia_confirmada':as_float(b['percentual_discrepancia_confirmada_pop_evaluator']),
                         'n_indeterminada':as_int(b['n_indeterminada']),
                         'alerta':'Critérios do edital de 2024 padronizados; não equivalem necessariamente aos editais históricos.'})
    else:raise ValueError('temporal id')
    return metric_rows(ind,rows,'POP_VALID_YEAR/POP_NEAR_YEAR/POP_EVALUATOR_YEAR, conforme indicador',
                       'Resultados derivados sem reler microdados; não há inferência causal.')


def localizar_raw(root,filename):
    # Apenas raw para evitar misturar saídas com fontes. Recusa duplicatas diferentes.
    dir=root/'data/raw'
    if not dir.is_dir():raise Pendencia('Pasta data/raw não encontrada')
    files=[p for p in dir.rglob('*') if p.is_file() and p.name.casefold()==filename.casefold()]
    if not files:raise Pendencia('Fonte ausente: '+filename)
    if len(files)>1:
        original=sha(files[0]);different=[p for p in files[1:] if sha(p)!=original]
        if different:raise Pendencia('Fontes duplicadas não idênticas: '+filename)
    return files[0]


def codificacao_fonte_csv(f):
    """Detecta UTF-8 ou Windows-1252 por amostra, sem modificar os bytes da fonte.

    Os microdados históricos podem conter texto acentuado em Windows-1252;
    outputs do projeto continuam UTF-8 e não usam esta função.
    """
    import codecs
    with Path(f).open('rb') as fp:
        amostra=fp.read(1024 * 1024)
    decoder=codecs.getincrementaldecoder('utf-8-sig')('strict')
    try:
        decoder.decode(amostra, final=False)
        return 'utf-8-sig'
    except UnicodeDecodeError:
        try:
            amostra.decode('cp1252')
        except UnicodeDecodeError as exc:
            raise Pendencia(f'Codificação CSV não reconhecida: {Path(f).name}') from exc
        return 'cp1252'


def indices_csv(f):
    with f.open(encoding=codificacao_fonte_csv(f), newline='') as fp:
        return next(csv.reader(fp,delimiter=';'))


def chaves_unicas(arquivo,ano,connection,table,block=200000):
    fields=indices_csv(arquivo)
    if 'NU_INSCRICAO' not in fields:raise Pendencia(f'{arquivo.name} sem NU_INSCRICAO')
    if 'NU_ANO' not in fields:cols=['NU_INSCRICAO']
    else:cols=['NU_INSCRICAO','NU_ANO']
    n=0;duplicatas=0;fora_ano=0;vazios=0
    for batch in pd.read_csv(arquivo,sep=';',encoding=codificacao_fonte_csv(arquivo),usecols=cols,
                             chunksize=block,dtype=str,low_memory=False):
        keys=batch['NU_INSCRICAO'].fillna('').astype(str).str.strip()
        years=batch['NU_ANO'].fillna('').astype(str).str.strip() if 'NU_ANO' in batch else None
        if years is not None:
            fora_ano+=int((years!=str(ano)).sum())
        vazios+=int((keys=='').sum())
        n+=len(batch)
        vals=[(s,) for s in keys if s]
        before=connection.total_changes
        connection.executemany(f'INSERT OR IGNORE INTO {table} (id) VALUES (?)',vals)
        inserted=connection.total_changes-before
        duplicatas+=len(vals)-inserted
        connection.commit()
    return {'n_lidas':n,'n_chaves_vazias':vazios,'n_duplicadas':duplicatas,
            'n_ano_divergente':fora_ano,'n_distintas':n-vazios-duplicatas}


def join_069(root,years,block):
    import sqlite3
    rows=[]
    with tempfile.TemporaryDirectory(prefix='ind069_',dir=None) as temp:
        conn=sqlite3.connect(str(Path(temp)/'join.sqlite3'))
        try:
            conn.execute('PRAGMA synchronous=OFF')
            conn.execute('CREATE TABLE L (id TEXT PRIMARY KEY) WITHOUT ROWID')
            conn.execute('CREATE TABLE R (id TEXT PRIMARY KEY) WITHOUT ROWID')
            for year in years:
                if year==2025:
                    rows.append({'ano':year,'status':'nao_aplicavel',
                                 'motivo':'Não existe identificador público validado para 2025'});continue
                left=f'MICRODADOS_ENEM_{year}.csv' if year<=2023 else f'PARTICIPANTES_{year}.csv'
                right=f'COMPETENCIAS_REDACAO_{year}.csv'
                try:
                    fa,fb=localizar_raw(root,left),localizar_raw(root,right)
                except Pendencia as e:
                    rows.append({'ano':year,'status':'indisponivel','motivo':str(e)});continue
                conn.execute('DELETE FROM L');conn.execute('DELETE FROM R');conn.commit()
                a=chaves_unicas(fa,year,conn,'L',block)
                b=chaves_unicas(fb,year,conn,'R',block)
                matched=conn.execute('SELECT COUNT(*) FROM L INNER JOIN R ON L.id=R.id').fetchone()[0]
                status='ok' if not(a['n_chaves_vazias'] or a['n_duplicadas'] or a['n_ano_divergente'] or b['n_chaves_vazias'] or b['n_duplicadas'] or b['n_ano_divergente']) else 'falha_unicidade_ou_ano'
                rows.append({'ano':year,'status':status,'fonte_esquerda':fa.name,'fonte_direita':fb.name,
                             'n_esquerda':a['n_lidas'],'n_direita':b['n_lidas'],
                             'matched':matched,'left_only':a['n_distintas']-matched,
                             'right_only':b['n_distintas']-matched,
                             'taxa_esquerda_pct':round(matched/a['n_distintas']*100,6) if a['n_distintas'] else None,
                             **{f'esq_{k}':v for k,v in a.items()},**{f'dir_{k}':v for k,v in b.items()}})
                if status!='ok':raise Pendencia(f'IND-069 {year}: chaves duplicadas, ausentes ou ano inconsistente')
        finally:
            conn.close()
    return metric_rows(69,rows,'JOIN_DIAGNOSTIC','Chaves não publicadas; SQLite temporário; junção anual sobre inscrição.')


def missing_070(root,years,block):
    """Ausência física em POP_ALL e POP_SOCIO, sem atribuir 'NÃO SEI' a missing."""
    rows=[]
    for year in years:
        sources=[(f'MICRODADOS_ENEM_{year}.csv','POP_ALL/POP_SOCIO')]
        if year>=2024:
            sources=[(f'RESULTADOS_{year}.csv','POP_ALL'),
                     (f'PARTICIPANTES_{year}.csv','POP_SOCIO')]
        for fname,population in sources:
            try:f=localizar_raw(root,fname)
            except Pendencia as e:
                rows.append({'ano':year,'status':'indisponivel','populacao':population,'motivo':str(e)});continue
            cols=indices_csv(f)
            notas=['NU_NOTA_REDACAO','TP_STATUS_REDACAO',*(f'NU_NOTA_COMP{i}' for i in range(1,6))]
            questions=[f'Q{i:03d}' for i in range(1,26 if year<=2023 else 24)]
            monitored=[c for c in (*notas,*questions) if c in cols]
            if not monitored:raise Pendencia(f'IND-070 {f.name}: nenhuma coluna de interesse')
            total=0;missing={c:0 for c in monitored}
            for batch in pd.read_csv(f,sep=';',dtype=str,usecols=monitored,encoding=codificacao_fonte_csv(f),chunksize=block):
                total+=len(batch)
                for col in monitored:
                    s=batch[col].fillna('').str.strip()
                    missing[col]+=int(s.eq('').sum())
            for col in monitored:
                rows.append({'ano':year,'fonte':f.name,'populacao':population,
                             'variavel':col,'n_linhas':total,'n_ausentes':missing[col],
                             'percentual_ausente':round(100*missing[col]/total,6) if total else None,
                             'status':'ok','observacao':'Ausência física; códigos NÃO SEI não são ausências'})
    return metric_rows(70,rows,'POP_ALL_FONTE e POP_SOCIO_FONTE',
        'Missing por arquivo e população, sem juntar implicitamente 2025 e sem imputar.')


def small_071(root,limit=30):
    rows=[];seen=set()
    canonical={'quantidade','n_redacoes_bin','n_com_desconto','n_sem_desconto','n_ambos',
               'n_com_av3','n_sem_av3','n_com_av4','n_sem_av4','n_cluster'}
    for path in sorted((root/'outputs/indicadores').glob('IND_*.csv')):
        match=re.match(r'IND_(\d{3})_',path.name)
        if not match or int(match.group(1))==71:continue
        with path.open(encoding='utf-8-sig',newline='') as fp:
            reader=csv.DictReader(fp,delimiter=';')
            cols=[c for c in (reader.fieldnames or []) if c in canonical]
            if not cols:continue
            n_rows=0;positives=0;zeros=0;small=0;min_small=None
            for r in reader:
                n_rows+=1
                for c in cols:
                    value=r.get(c,'')
                    try:n=int(value)
                    except (ValueError,TypeError):continue
                    if n==0:zeros+=1
                    if n>0:
                        positives+=1
                        if n<limit:
                            small+=1;min_small=n if min_small is None else min(min_small,n)
            rows.append({'fonte_csv':path.name,'indicador_origem':match.group(1),
                         'n_linhas':n_rows,'colunas_avaliadas':'|'.join(cols),
                         'celulas_contadas_positivas':positives,'contagens_zero':zeros,
                         'celulas_positivas_1_a_29':small,'menor_contagem_positiva':min_small,
                         'tratamento':'auditoria_sem_supressao_automatica',
                         'revisao_contextual':bool(small),'status':'draft'})
    return metric_rows(71,rows,'agregados existentes',
        f'Política do projeto: não suprimir n entre 1 e {limit-1} automaticamente; NÃO comprova anonimato.',
        status='draft')


def provenance_072(root):
    files=[]
    for folder,pattern in [('outputs/json','*.json'),('outputs/indicadores','*.csv')]:
        for p in sorted((root/folder).glob(pattern)):
            if p.name.startswith('IND_') or p.name.startswith('dashboard_enem_'):
                if p.name.startswith('IND_072'):continue
                files.append({'arquivo':p.relative_to(root).as_posix(),
                              'tamanho_bytes':p.stat().st_size,'sha256':sha(p),
                              'modificado_em_utc':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()})
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True)
    code=commit.stdout.strip() if commit.returncode==0 else None
    return {'indicator_id':'IND-072','status':'draft','generated_at':now(),
            'meta':{'schema_version':'1.0.0','analysis_version':'ind055-072-preparado-v1',
                    'git_commit':code,'python':sys.version.split()[0],
                    'data_version':'enem-2019-2025-publicado',
                    'sources_must_be_checked':'source files hashes in manifest only',
                    'no_individual_identifiers':True},'results':files,
            'review':'Verificar documentação e disponibilidade dos microdados antes da publicação.'}

# Contrato da ponte: ela deve ser produzida localmente, mediante join auditado,
# e permitir reatribuição a um modelo de clusters de referência FIXO. O IND-054
# apenas divulga centroides/agregados; não equivale a rótulos individuais.
COL_TARGET=['nota_redacao','c1','c2','c3','c4','c5']
BRIDGE_VERSION='ponte-socio-cluster-fixo-v1'



# Somente trabalho interno da pesquisa. NAO equivale a homologacao/publicacao.
ENV_RASCUNHO_V2='ENEM_V2_RASCUNHO_INTERNO'
SCHEMA_RASCUNHO_V2='ponte-socio-10-ativas-rascunho-interno-v2'

def _manifesto_v2_para_rascunho(root):
    """Lê a candidata V2 SEM alterar status de aprovacao e valida proveniencia."""
    if (root/'data/derived/manifesto_ponte_socio_v2_homologada.json').exists():
        raise Pendencia('Ja existe ponte homologada: use o executor normal em vez de rascunho')
    refpath=root/'data/derived/candidata_ponte_socio_v2/comparativo_modelos_agrupado.json'
    candpath=root/'data/derived/candidata_ponte_socio_v2_individual/manifesto_candidato_v2.json'
    if not refpath.is_file() or not candpath.is_file():
        raise Pendencia('Ponte V2 candidata e comparativo nao encontrados')
    ref=json.loads(refpath.read_text(encoding='utf-8-sig'))
    cand=json.loads(candpath.read_text(encoding='utf-8-sig'))
    if (ref.get('schema')!='comparativo-clusters-10-ativas-v1'
        or ref.get('status')!='exploratorio_nao_aprovado'
        or ref.get('amostra_comparavel_n')!=104752
        or ref.get('v2',{}).get('k')!=3
        or ref['v2'].get('cluster_sizes')!=[66664,34240,3848]):
        raise Pendencia('Comparativo V2 nao corresponde ao modelo previamente auditado')
    if (cand.get('schema_version')!='ponte-socio-10-ativas-candidata-v2'
        or cand.get('status')!='candidato_nao_aprovado'
        or cand.get('hash_comparacao_v2')!=sha(refpath)
        or cand.get('n_total')!=104752
        or cand.get('k')!=3
        or cand.get('cluster_sizes')!=ref['v2']['cluster_sizes']
        or cand.get('variaveis_ativas')!=ref.get('variaveis_ativas')
        or len(cand.get('variaveis_ativas',[]))!=10
        or len(cand.get('anos',{}))!=7):
        raise Pendencia('Manifesto candidato V2 divergente ou sem rastreabilidade')
    if cand.get('modelo_referencia')!='modelo_v2_reproduzido_do_comparativo_nao_IND054_oficial':
        raise Pendencia('Manifesto da candidata passou a declarar modelo oficial incorretamente')
    byyear={int(x['ano']):x for x in ref['v2']['distribuicao_anual']}
    counts=Counter()
    manifest={
        'schema_version':SCHEMA_RASCUNHO_V2,
        'status':'rascunho_interno_nao_homologado',
        'modelo_referencia':'V2_MCA10_KMeans3_'+sha(refpath)[:16],
        'validacao_mca_clusters':'reproducao_e_auditoria_tecnicas_conferidas',
        'aviso':'Nao divulgar nem interpretar como IND-054 oficial',
        'anos':{},
    }
    for year in range(2019,2026):
        item=cand['anos'].get(str(year),{})
        yr=byyear.get(year,{})
        if (not item or item.get('n_registros')!=yr.get('n')
            or item.get('clusters')!={k:v['n'] for k,v in yr.get('clusters',{}).items()}):
            raise Pendencia(f'{year}: contagens da candidata nao conferem com comparativo')
        source=(root/item.get('arquivo','')).resolve()
        allowed=(root/'data/derived/candidata_ponte_socio_v2_individual').resolve()
        if source.parent!=allowed or not source.is_file():
            raise Pendencia(f'{year}: arquivo da candidata fora do diretorio privado')
        if not re.fullmatch('[0-9a-f]{64}',str(item.get('sha256',''))):
            raise Pendencia(f'{year}: hash ausente ou malformado')
        counts.update(item['clusters'])
        if year==2025 and (item.get('notas_validas') is not None or item.get('av_pareadas') is not None):
            raise Pendencia('2025 nao possui vinculo de notas: proibida associacao artificial')
        manifest['anos'][str(year)]={
            'arquivo':item['arquivo'], 'sha256':item['sha256'],
            'n_registros':item['n_registros'],
            'join_qa':'nao_aplicavel_sem_notas' if year==2025 else 'ok',
            'unicidade_qa':'ok',
        }
    if [counts[f'C{i}'] for i in (1,2,3)]!=[66664,34240,3848]:
        raise Pendencia('Contagem total por cluster diverge da auditoria V2')
    return manifest

def bridge_manifest(root):
    if os.environ.get(ENV_RASCUNHO_V2)=='1':
        return _manifesto_v2_para_rascunho(root)
    """Aceita contrato original ou V2 homologada; NUNCA aceita manifesto candidato.

    A rota V2 só existe depois da decisão documentada externa. A validação dos
    hashes das pontes ocorre em bridge_data, em cada execução.
    """
    v2=root/'data/derived/manifesto_ponte_socio_v2_homologada.json'
    if v2.exists():
        obj=json.loads(v2.read_text(encoding='utf-8-sig'))
        if obj.get('schema_version')!='ponte-socio-10-ativas-homologada-v2' or obj.get('status')!='homologado_com_pareceres':
            raise Pendencia('Manifesto V2 presente mas não homologado: recusa de execução')
        if obj.get('validacao_mca_clusters')!='reproducao_e_auditoria_conferidas':
            raise Pendencia('Modelo V2 sem reconciliação técnica')
        if obj.get('modelo_tipo')!='MCA10_KMeans3_amostra_2019_2025':
            raise Pendencia('Tipo de modelo V2 incorreto')
        ref=root/'data/derived/candidata_ponte_socio_v2/comparativo_modelos_agrupado.json'
        cand=root/'data/derived/candidata_ponte_socio_v2_individual/manifesto_candidato_v2.json'
        if not ref.is_file() or not cand.is_file():
            raise Pendencia('Relatório e manifesto candidato V2 não encontrados')
        if obj.get('comparativo_sha256')!=sha(ref) or obj.get('candidato_sha256')!=sha(cand):
            raise Pendencia('Relatório ou candidato V2 modificados após homologação')
        expected_ref='V2_MCA10_KMeans3_'+sha(ref)[:16]
        if obj.get('modelo_referencia')!=expected_ref:
            raise Pendencia('Modelo de referência V2 não rastreável')
        original=json.loads(cand.read_text(encoding='utf-8-sig'))
        if original.get('status')!='candidato_nao_aprovado' or original.get('k')!=3:
            raise Pendencia('Manifesto de origem V2 não é candidato legítimo K=3')
        if original.get('n_total')!=104752 or len(original.get('anos',{}))!=7:
            raise Pendencia('Amostra modelo V2 diverge da referência validada')
        for y in range(2019,2026):
            item=obj.get('anos',{}).get(str(y),{})
            source=original['anos'].get(str(y),{})
            if (not item or item.get('arquivo')!=source.get('arquivo')
                or item.get('sha256')!=source.get('sha256')
                or item.get('n_registros')!=source.get('n_registros')
                or item.get('join_qa')!=('nao_aplicavel_sem_notas' if y==2025 else 'ok')
                or item.get('unicidade_qa')!='ok'):
                raise Pendencia(f'{y}: manifesto V2 sem rastreabilidade e QA completos')
        if obj['anos']['2025'].get('notas_validas') is not None or obj['anos']['2025'].get('av_pareadas') is not None:
            raise Pendencia('2025 deve permanecer sem notas associadas')
        decisions=obj.get('pareceres',{})
        for key in ('metodologia','representatividade','privacidade_cruzada'):
            p=decisions.get(key,{})
            if (p.get('status')!='aprovado_com_ressalvas'
                or not str(p.get('responsavel','')).strip()
                or not str(p.get('fundamentacao','')).strip()
                or not str(p.get('data','')).strip()):
                raise Pendencia(f'Parecer obrigatório ausente/incompleto: {key}')
        return obj
    # Compatibilidade retroativa: somente o contrato oficial original da V1.
    file=root/'data/derived/manifesto_ponte_socio_cluster.json'
    if not file.exists():
        raise Pendencia('Não há ponte homologada. Ponte V2 candidata não autoriza execução; '
                       'necessária homologação metodológica e privacidade cruzada.')
    obj=json.loads(file.read_text(encoding='utf-8-sig'))
    if obj.get('schema_version')!=BRIDGE_VERSION or not obj.get('modelo_referencia'):
        raise Pendencia('Manifesto original declara esquema ou modelo inválido')
    if obj.get('validacao_mca_clusters')!='aprovado':
        raise Pendencia('Manifesto original sem reconciliação MCA/KMeans IND-054')
    return obj


def bridge_data(root,years=tuple(range(2019,2025)),max_n=85000,require_score=True):
    m=bridge_manifest(root)
    data=[];salvage={}
    for year in years:
        item=m.get('anos',{}).get(str(year))
        if not item:
            salvage[year]='sem_ponte_validada';continue
        situacao_join=item.get('join_qa')
        if (item.get('unicidade_qa')!='ok'
            or (year==2025 and m.get('schema_version') in ('ponte-socio-10-ativas-homologada-v2',SCHEMA_RASCUNHO_V2)
                and not require_score and situacao_join!='nao_aplicavel_sem_notas')
            or (year!=2025 or require_score or m.get('schema_version') not in ('ponte-socio-10-ativas-homologada-v2',SCHEMA_RASCUNHO_V2))
               and situacao_join!='ok'):
            raise Pendencia(f'{year}: manifesto sem status de junção/unicidade coerente')
        path=(root/item.get('arquivo','')).resolve()
        if root.resolve() not in path.parents:
            raise Pendencia(f'{year}: ponte fora do repositório')
        if not path.is_file() or sha(path)!=item.get('sha256'):
            raise Pendencia(f'{year}: hash da ponte não confere')
        seen=set();n=0;parts=[]
        for chunk in pd.read_csv(path,sep=';',encoding='utf-8-sig',dtype={'id_registro':str},chunksize=50000):
            required={'id_registro','ano','uf','cluster_ref'} | (set(COL_TARGET) if require_score else set())
            if not required.issubset(chunk.columns):
                raise Pendencia(f'{year}: ponte sem colunas {sorted(required-set(chunk.columns))}')
            if not chunk['ano'].eq(year).all():raise Pendencia(f'{year}: registro fora do ano')
            if not set(chunk['uf'].dropna()).issubset(UFS-{'BR'}):
                raise Pendencia(f'{year}: UF inválida na ponte')
            if chunk['id_registro'].isna().any() or chunk['id_registro'].duplicated().any():
                raise Pendencia(f'{year}: ID ausente/duplicado dentro de bloco')
            ids=set(chunk['id_registro'])
            if not seen.isdisjoint(ids):raise Pendencia(f'{year}: participante duplicado entre blocos')
            seen.update(ids);n+=len(chunk)
            if chunk['cluster_ref'].isna().any() or not chunk['cluster_ref'].astype(str).str.fullmatch('C[1-9][0-9]*').all():
                raise Pendencia(f'{year}: cluster ausente/inválido')
            if require_score:
                for key,top in [('nota_redacao',1000),*((f'c{k}',200) for k in range(1,6))]:
                    s=pd.to_numeric(chunk[key],errors='coerce')
                    if s.notna().any() and not s.dropna().between(0,top).all():
                        raise Pendencia(f'{year}: {key} fora de domínio')
            # Primeiro faz teste de unicidade/hash de todo o arquivo, depois retém
            # amostra determinística para evitar volume excessivo de RAM.
            if len(chunk)>max_n:
                chunk=chunk.sample(n=max_n,random_state=year).copy()
            parts.append(chunk)
        if n!=int(item.get('n_registros',-1)):
            raise Pendencia(f'{year}: N do manifesto diverge do CSV')
        if not parts:salvage[year]='vazio';continue
        df=pd.concat(parts,ignore_index=True)
        if len(df)>max_n:
            df=df.sample(n=max_n,random_state=2026+year).reset_index(drop=True)
        df['ano']=year
        data.append(df)
        salvage[year]={'total_validado':n,'amostra_utilizada':len(df),'sha256':item['sha256']}
    if not data:raise Pendencia('Nenhum ano com ponte socioeconômica validada')
    return pd.concat(data,ignore_index=True),salvage,m


def _num(s):
    return pd.to_numeric(s,errors='coerce')


def group_stats(values):
    a=_num(values).dropna().to_numpy(dtype=float)
    if not len(a):return {'n':0,'media':None,'mediana':None,'q1':None,'q3':None,'iqr':None,'dp':None}
    q1,q3=np.quantile(a,[.25,.75])
    return {'n':int(len(a)),'media':round(float(a.mean()),6),
            'mediana':round(float(np.median(a)),6),
            'q1':round(float(q1),6),'q3':round(float(q3),6),
            'iqr':round(float(q3-q1),6),'dp':round(float(a.std(ddof=0)),6)}


def cluster_cross(ind,root):
    data,qa,m=bridge_data(root,require_score=True)
    if data['ano'].eq(2025).any():raise Pendencia('2025 não tem vínculo público nota×socioeconômico')
    rows=[]
    for (year,cluster), group in data.groupby(['ano','cluster_ref'],sort=True):
        base={'ano':int(year),'cluster':cluster,'n_amostra_socio':len(group),'status':'draft',
              'observacao':'Análise amostral; clusters de referência fixa; sem causalidade'}
        if ind==55:
            vals=group_stats(group['nota_redacao']);rows.append({**base,**vals})
        elif ind==56:
            for i in range(1,6):
                vals=group_stats(group[f'c{i}']);rows.append({**base,'competencia':f'C{i}',**vals})
        elif ind==57:
            scores=_num(group['nota_redacao']).dropna()
            total=len(scores);high=int(scores.ge(900).sum());near=int(scores.between(900,980).sum())
            rows.append({**base,'n_notas_validas':total,'n_high_900_1000':high,
                         'percentual_high':round(100*high/total,6) if total else None,
                         'n_near_900_980':near,
                         'percentual_near':round(100*near/total,6) if total else None})
        elif ind==58:
            scores=_num(group['nota_redacao']);sel=group.loc[scores.between(900,980)].copy()
            for i in range(1,6):
                c=_num(sel[f'c{i}']); losses=200-c.dropna()
                n=len(losses);desc=int((losses>0).sum())
                rows.append({**base,'competencia':f'C{i}','n_near_cluster':len(sel),
                             'n_com_competencia_valida':n,'n_com_desconto':desc,
                             'frequencia_desconto':round(desc/n,8) if n else None,
                             'perda_media':round(float(losses.mean()),6) if n else None})
        elif ind==59:
            if not {'av1','av2'}.issubset(group.columns):
                raise Pendencia('IND-059 exige av1 e av2 reais do mesmo participante na ponte')
            a,b=_num(group['av1']),_num(group['av2'])
            delta=(a-b).abs().loc[a.between(0,1000)&b.between(0,1000)]
            rows.append({**base,'populacao':'POP_SOCIO_EVALUATOR','n_pareadas':len(delta),
                         'media_diferenca_absoluta':round(float(delta.mean()),6) if len(delta) else None,
                         'mediana_diferenca_absoluta':round(float(delta.median()),6) if len(delta) else None,
                         'p90_diferenca_absoluta':round(float(delta.quantile(.9)),6) if len(delta) else None})
    for y in ANOS:
        if y==2025:rows.append({'ano':y,'status':'nao_aplicavel','motivo':'Sem vínculo público legítimo notas×socioeconômico'})
        elif y not in data['ano'].values:rows.append({'ano':y,'status':'indisponivel','motivo':'ponte não validada'})
    return metric_rows(ind,rows,'AMOSTRA_SOCIO_ML_COM_NOTAS_VALIDADA',
                       f'Não representa censitariamente a população; ponte {m["modelo_referencia"]} verificada. QA: {qa}')


def _feature_columns(df):
    # Variáveis de contexto: sem campos alvo/ID ou marcadores sensíveis demográficos.
    return sorted(c for c in df.columns if re.fullmatch(r'Q\d{3}',c))


def _fit_mldata(root,target='nota_redacao',sample_limit=50000,treinar=True):
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder
    except ImportError as e:
        raise Pendencia('Dependência ML ausente: scikit-learn') from e
    data,qa,manifest=bridge_data(root,max_n=sample_limit)
    columns=_feature_columns(data)
    if not columns:raise Pendencia('A ponte não contém variáveis Q001..Q023 para treinamento')
    if target not in data:raise Pendencia('Ponte sem alvo '+target)
    data=data.loc[_num(data[target]).between(0,1000 if target=='nota_redacao' else 200)].copy()
    if len(data)<200:raise Pendencia('Amostra válida com menos de 200 participantes')
    x=data[columns].fillna('__AUSENTE__').astype(str)
    y=_num(data[target]).to_numpy(float)
    idx_train,idx_test=train_test_split(np.arange(len(data)),test_size=.2,random_state=2026)
    enc=OneHotEncoder(handle_unknown='ignore',min_frequency=2)
    rf=RandomForestRegressor(n_estimators=120,max_depth=16,min_samples_leaf=5,
                             random_state=2026,n_jobs=1)
    pipe=Pipeline([('enc',enc),('rf',rf)])
    baseline=float(np.mean(y[idx_train]))
    metrics={'n_treino':int(len(idx_train)),'n_teste':int(len(idx_test)),
             'mae_baseline':round(float(mean_absolute_error(y[idx_test],np.full(len(idx_test),baseline))),6),
             'rmse_baseline':round(float(math.sqrt(mean_squared_error(y[idx_test],np.full(len(idx_test),baseline)))),6),
             'predicao_baseline':baseline,'target':target,
             'split':'train_test_80_20_seed_2026','features':columns,
             'modelo':'RandomForestRegressor_n_estimators120_max_depth16_min_samples_leaf5',
             'limite_amostra_por_ano':sample_limit}
    if treinar:
        pipe.fit(x.iloc[idx_train],y[idx_train])
        pred=pipe.predict(x.iloc[idx_test]);y_true=y[idx_test]
        error=y_true-pred
        metrics.update({'mae':round(float(np.mean(np.abs(error))),6),
                        'rmse':round(float(np.sqrt(np.mean(error**2))),6),
                        'r2':round(float(r2_score(y_true,pred)),6)})
        # CV utiliza amostra LIMITADA do treinamento, nunca o teste.
        from sklearn.model_selection import cross_val_score
        rng=np.random.default_rng(2026)
        idx_cv=rng.choice(idx_train,size=min(2500,len(idx_train)),replace=False)
        scores=cross_val_score(pipe,x.iloc[idx_cv],y[idx_cv],scoring='neg_mean_absolute_error',
                               cv=3,n_jobs=1)
        metrics['cv_mae_3fold']=round(float(-np.mean(scores)),6)
        metrics['cv_n']=int(len(idx_cv))
    return pipe, x, y, idx_train, idx_test, data,metrics,qa,manifest


def ml_model(ind,root):
    if ind==60:
        pipe,x,y,train,test,data,stats,qa,manifest=_fit_mldata(root)
        # Guardar só modelo/metadata, nunca informações individuais ou predições.
        try:import joblib
        except ImportError as e:raise Pendencia('joblib indisponível') from e
        model_path=(root/('outputs/modelos_rascunho_v2' if os.environ.get(ENV_RASCUNHO_V2)=='1' else 'outputs/modelos')/'IND_060_modelo_local.joblib')
        model_path.parent.mkdir(parents=True,exist_ok=True)
        joblib.dump({'modelo':pipe,'metricas':stats,'bridge_hashes':qa,
                     'referencia':manifest['modelo_referencia']},model_path,compress=3)
        return metric_rows(ind,[stats],'AMOSTRA_SOCIO_ML',
            'Baselines/holdout; não causal. O arquivo de modelo é local; não publicar como dados pessoais.')
    if ind==61:
        rows=[]
        for i in range(1,6):
            _,_,_,_,_,_,stats,_,_=_fit_mldata(root,f'c{i}')
            rows.append({'competencia':f'C{i}',**stats})
        return metric_rows(ind,rows,'AMOSTRA_SOCIO_ML','Cinco florestas treinadas separadamente; apenas questionário como entrada.')
    if ind in (62,63):
        try:import joblib
        except ImportError as e:raise Pendencia('joblib indisponível') from e
        saved=(root/('outputs/modelos_rascunho_v2' if os.environ.get(ENV_RASCUNHO_V2)=='1' else 'outputs/modelos')/'IND_060_modelo_local.joblib')
        if not saved.exists():raise Pendencia('IND-060 precisa ter sido treinado na mesma ponte antes de IND-062/063')
        model=joblib.load(saved)
        pipe,x,y,train,test,data,stats,qa,manifest=_fit_mldata(root,treinar=False)
        if model['bridge_hashes']!=qa or model['metricas']['features']!=stats['features']:
            raise Pendencia('IND-060: ponte ou características alteradas desde treino')
        # Usar somente o modelo salvo e o mesmo holdout, sem vazamento do treino.
        pipe=model['modelo']
        if ind==62:
            from sklearn.inspection import permutation_importance
            hold=x.iloc[test].head(1500);target=y[test][:len(hold)]
            p=permutation_importance(pipe,hold,target,n_repeats=3,random_state=2026,
                                     scoring='neg_mean_absolute_error',n_jobs=1)
            rows=[{'variavel':col,'importancia_media_mae':round(float(v),6),
                   'desvio_repeticoes':round(float(sd),6),'metodo':'permutacao_holdout'}
                  for col,v,sd in zip(x.columns,p.importances_mean,p.importances_std)]
            rows.sort(key=lambda r:-r['importancia_media_mae'])
            return metric_rows(ind,rows,'TEST_SET','Importância por permutação fora de amostra; SHAP opcional não executado; não causal.')
        y_hat=pipe.predict(x.iloc[test]);subdata=data.iloc[test].copy()
        subdata['_y']=y[test];subdata['_pred']=y_hat
        rows=[]
        for key in ['ano','uf']:
            if key not in subdata:continue
            for category,grp in subdata.groupby(key,sort=True):
                diff=(grp['_y']-grp['_pred']).to_numpy(dtype=float)
                n=len(diff)
                rows.append({'dimensao':key,'categoria':str(category),'n_teste':n,
                             'mae':round(float(np.mean(abs(diff))),6),
                             'rmse':round(float(np.sqrt(np.mean(diff**2))),6),
                             'r2':round(float(1-(diff**2).sum()/((grp['_y']-grp['_y'].mean())**2).sum()),6) if n>=2 and grp['_y'].var()>0 else None,
                             'status_estimativa':'amostra_pequena_instavel' if n<30 else 'ok'})
        return metric_rows(ind,rows,'TEST_SET','Auditoria por edição/UF sem usar grupo como alvo. Não avaliar vieses causais.')
    raise ValueError('ML id desconhecido')


def temporal_clusters_068(root):
    data,qa,m=bridge_data(root,years=tuple(ANOS),require_score=False)
    rows=[];reference=m['modelo_referencia']
    for year in ANOS:
        sel=data.loc[data['ano'].eq(year)]
        if sel.empty:
            rows.append({'ano':year,'status':'indisponivel','motivo':'Ponte de clusters fixa ausente'});continue
        for c,n in sorted(sel['cluster_ref'].value_counts().items()):
            rows.append({'ano':year,'cluster_referencia':c,'n_amostra':int(n),
                         'percentual_amostra':round(float(100*n/len(sel)),6),
                         'status':'ok','modelo_referencia':reference})
    return metric_rows(68,rows,'AMOSTRA_SOCIO_ML','Comparação só de clusters projetados no MESMO modelo fixo; sem comparabilidade caso ano ausente.')


def check_prereqs(ind,root):
    if 55<=ind<=63 or ind==68:
        try:
            m=bridge_manifest(root)
            return {'status':'pronto_para_processamento','modelo_referencia':m['modelo_referencia'],
                    'advertencia':'Ainda exige validação por ano e conferência de N no arquivo de ponte'}
        except Pendencia as e:
            return {'status':'bloqueado_por_dependencia','motivo':str(e)}
    if ind in (64,65,66,67):
        checks={64:(2,3),65:(9,10),66:(31,32),67:(20,22)}[ind]
        missing=[x for x in checks if not path_existing(root,x)]
        return {'status':'pronto_para_processamento' if not missing else 'bloqueado_por_dependencia',
                'faltam_csv':missing}
    if ind==69:
        return {'status':'pronto_com_raw' if (root/'data/raw').is_dir() else 'bloqueado_por_dependencia',
                'obs':'Validação de chaves NU_INSCRICAO e NU_ANO deve ocorrer antes de pontes'}
    if ind==70:
        return {'status':'pronto_com_raw' if (root/'data/raw').is_dir() else 'bloqueado_por_dependencia'}
    if ind in (71,72):return {'status':'pronto_para_processamento'}
    return {'status':'nao_implementado'}


def execute_indicator(ind,root,years,block,minimum):
    if ind in (64,65,66,67):return temporal(ind,root)
    if ind==68:return temporal_clusters_068(root)
    if ind==69:return join_069(root,years,block)
    if ind==70:return missing_070(root,years,block)
    if ind==71:return small_071(root,minimum)
    if ind==72:return provenance_072(root)
    if 55<=ind<=59:return cluster_cross(ind,root)
    if 60<=ind<=63:return ml_model(ind,root)
    raise ValueError(ind)


def write_atomic(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=path.parent,
                                    prefix='.ind_temp_',delete=False) as f:
        tmp=Path(f.name); f.write(content)
    os.replace(tmp,path)


def write_results(ind,root,doc,sobrescrever):
    stem=nome(ind)
    if os.environ.get(ENV_RASCUNHO_V2)=='1' and (55<=ind<=63 or ind==68):
        out=root/'outputs/rascunho_ponte_v2'
        jsonout=out/'json'/f'{stem}.json'
        csvout=out/'indicadores'/f'{stem}.csv'
        if doc.get('status')!='draft':
            raise Pendencia('Modo interno nao permite resultado homologado')
        doc['modo_execucao']='rascunho_interno_nao_publicar'
        doc['publicacao_autorizada']=False
        doc['modelo_referencia']='V2_MCA10_KMeans3_'+sha(root/'data/derived/candidata_ponte_socio_v2/comparativo_modelos_agrupado.json')[:16]
    else:
        jsonout=root/'outputs/json'/f'{stem}.json'
        csvout=root/'outputs/indicadores'/f'{stem}.csv'
    if not sobrescrever and (jsonout.exists() or csvout.exists()):
        raise FileExistsError(f'IND-{ind:03d}: saídas já existem, use --sobrescrever')
    rows=doc.get('results',[])
    if not isinstance(rows,list) or not rows:
        raise Pendencia(f'IND-{ind:03d}: resultado vazio; não escrever saída fictícia')
    fields=sorted(set().union(*(r.keys() for r in rows)))
    from io import StringIO
    sio=StringIO();writer=csv.DictWriter(sio,fieldnames=fields,delimiter=';',lineterminator='\n');writer.writeheader()
    for row in rows:
        writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    # Escrever CSV primeiro; JSON só após CSV completo. Executor faz backup antes.
    write_atomic(csvout,sio.getvalue())
    write_atomic(jsonout,json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('CSV:',csvout)
    print('JSON:',jsonout)


def main(ind):
    parser=argparse.ArgumentParser(description=f'ENEM IND-{ind:03d}: {BASES[ind][0]}')
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--verificar',action='store_true',help='Somente pré-condições; não processa')
    choice.add_argument('--executar',action='store_true',help='Processa o indicador explicitamente')
    parser.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--anos',default='2019,2020,2021,2022,2023,2024,2025')
    parser.add_argument('--bloco',type=int,default=150000)
    parser.add_argument('--min-group-n',type=int,default=30)
    parser.add_argument('--sobrescrever',action='store_true')
    args=parser.parse_args()
    root=args.raiz.resolve()
    if not (root/'src/indicadores').is_dir():parser.error('Raiz do projeto inválida')
    years=tuple(int(v.strip()) for v in args.anos.split(','))
    if not years or any(v not in ANOS for v in years) or len(set(years))!=len(years):parser.error('Anos inválidos')
    if args.bloco<100 or not (1<=args.min_group_n<=1000):parser.error('Limites inválidos')
    if args.verificar:
        result=check_prereqs(ind,root)
        print(json.dumps({'indicator':f'IND-{ind:03d}',**result},ensure_ascii=False))
        return 0 if not result['status'].startswith('bloqueado') else 2
    result=check_prereqs(ind,root)
    if result['status'].startswith('bloqueado'):
        raise Pendencia(str(result))
    doc=execute_indicator(ind,root,years,args.bloco,args.min_group_n)
    write_results(ind,root,doc,args.sobrescrever)
    return 0
