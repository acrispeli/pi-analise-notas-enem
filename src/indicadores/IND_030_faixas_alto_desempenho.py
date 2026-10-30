#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-030 — Faixas de notas de alto desempenho, ENEM 2019–2025.

POP_HIGH = POP_VALID (TP_STATUS_REDACAO=1, nota numérica válida [0,1000])
           E NU_NOTA_REDACAO >= 900.

A distribuição começa com as cinco faixas [900,920), [920,940), [940,960),
[960,980) e [980,1000]. A última agrega a nota 1000 para evitar publicar
contagens raras já identificadas no IND-008. As faixas são mescladas quando
necessário para fechar os totais; todas as faixas originais são preservadas.

Uso na raiz do projeto:
  python src/indicadores/IND_030_faixas_alto_desempenho.py
  python src/indicadores/IND_030_faixas_alto_desempenho.py --somente-modulo
  python src/indicadores/IND_030_faixas_alto_desempenho.py --sobrescrever

Executar sem outros processos que atualizem os dashboards simultaneamente.
Não altera o Streamlit nem os indicadores anteriores.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split())
ID = 'IND-030'
ARQUIVO = 'IND_030_faixas_alto_desempenho'
MIN_N = 1
LIMITES = ((900, 920), (920, 940), (940, 960), (960, 980), (980, 1000))
METODO = 'contagens_exatas_pop_high_com_agregacao_adaptativa_privacidade'
NOTAS = (
    'POP_HIGH: POP_VALID e nota de redação no intervalo inclusivo [900,1000]. '
    'Percentuais das faixas calculados sobre POP_HIGH do recorte, e percentual '
    'de alto desempenho sobre POP_VALID. Faixas de 20 pontos, com 1000 agrupado '
    'em 980–1000. Faixas adjacentes podem ser unidas para evitar exposição de '
    'contagens positivas entre 1 e 29. Isso impede reconstrução apenas dentro '
    'do próprio recorte, mas não garante supressão complementar entre recortes '
    'ou com indicadores anteriores (IND-008 já publica contagens pequenas). '
    'A publicação pública exige auditoria de inferência por cruzamento. '
    'UF de aplicação, não residência; o histórico soma participações, não pessoas. '
    'Dados preliminares, sujeitos à revisão acadêmica e de privacidade.'
)


def origem(raiz: Path, ano: int) -> Path:
    arquivo = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / arquivo


def ler_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f'Arquivo necessário não encontrado: {path}')
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def gravar_json(path: Path, dados: dict) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def grupo(periodo: dict, uf: str) -> dict:
    if uf == 'BR':
        return periodo['brasil']
    return next(r for r in periodo['ufs'] if r['uf'] == uf)


def versao_para_dashboard(atual: str) -> str:
    # Identificadores existentes são preservados; não declarar IND-028/029 se ausentes.
    ids = list(dict.fromkeys(re.findall(r'ind\d{3}', atual or '')))
    if 'ind030' not in ids:
        ids.append('ind030')
    return '2.30.0-' + '-'.join(ids)


def carregar_referencias(raiz: Path) -> dict:
    arquivos = {1: 'IND_001_redacoes_validas.json',
                6: 'IND_006_distribuicao_notas.json',
                8: 'IND_008_notas_1000.json'}
    refs = {}
    for num, nome in arquivos.items():
        data = ler_json(raiz / 'outputs' / 'json' / nome)
        if data.get('indicator', {}).get('id') != f'IND-{num:03d}':
            raise ValueError(f'{nome}: identificador de indicador incorreto')
        if [x.get('ano') for x in data.get('years', [])] != list(ANOS):
            raise ValueError(f'{nome}: anos incompletos ou fora de ordem')
        for p in (*data['years'], data.get('historical', {})):
            if {r.get('uf') for r in p.get('ufs', [])} != set(UFS):
                raise ValueError(f'{nome}: faltam UFs')
        refs[num] = data
    return refs


def verificar_dashboard(d: dict, ano: int) -> None:
    if d.get('meta', {}).get('year') != ano:
        raise ValueError(f'Dashboard {ano}: ano incorreto')
    pages = d.get('pages', {})
    for page in ('overview', 'high_performance', 'temporal', 'methodology'):
        if not isinstance(pages.get(page), dict):
            raise ValueError(f'Dashboard {ano}: página {page} ausente')
    if d.get('quality', {}).get('ind027_validation', {}).get('status') != 'ok':
        raise ValueError(f'Dashboard {ano}: processe o IND-027 antes do IND-030')
    if d.get('meta', {}).get('data_status') != 'draft':
        raise ValueError(f'Dashboard {ano}: status inesperado (exigido draft)')


def calc_banda(valores: pd.Series) -> tuple[int, ...]:
    """Categorias sem perder notas intermediárias (ex.: 910)."""
    return tuple(int(((valores >= lo) & ((valores <= hi) if hi == 1000 else (valores < hi))).sum())
                 for lo, hi in LIMITES)


def mesclar_faixas(contagens: tuple[int, ...], minimo: int = MIN_N) -> tuple[list[dict], str]:
    """Nunca expõe célula pequena nem a nota 1000 separadamente.

    Cada bin publicado tem N=0 ou N>=minimo; se total positivo<minimo,
    nenhuma faixa nem total POP_HIGH é publicado.
    """
    if len(contagens) != len(LIMITES) or any(not isinstance(n, int) or n < 0 for n in contagens):
        raise ValueError('Cinco contagens de faixa inteiras e não negativas são obrigatórias')
    n = sum(contagens)
    if 0 < n < minimo:
        return [], 'suprimido_grupo_pequeno'
    arr = [{'limite_inferior': lo, 'limite_superior': hi, 'quantidade': v}
           for (lo, hi), v in zip(LIMITES, contagens)]
    while len(arr) > 1:
        pequenos = [i for i, item in enumerate(arr) if 0 < item['quantidade'] < minimo]
        if not pequenos:
            break
        i = pequenos[0]
        vizinhos = [j for j in (i-1, i+1) if 0 <= j < len(arr)]
        # Fundir com vizinho menor: minimiza perda de detalhamento por massa agregada.
        j = min(vizinhos, key=lambda j: (arr[j]['quantidade'], j))
        k = min(i, j)
        arr[k] = {'limite_inferior': arr[k]['limite_inferior'],
                  'limite_superior': arr[k+1]['limite_superior'],
                  'quantidade': arr[k]['quantidade'] + arr[k+1]['quantidade']}
        del arr[k+1]
    if any(0 < item['quantidade'] < minimo for item in arr):
        return [], 'suprimido_grupo_pequeno'
    result = []
    for item in arr:
        lo, hi, qtd = item['limite_inferior'], item['limite_superior'], item['quantidade']
        result.append({'faixa': f'{lo}–{hi}' if hi == 1000 else f'{lo}–<{hi}',
                       'limite_inferior': lo, 'limite_superior': hi,
                       'superior_inclusivo': hi == 1000,
                       'quantidade': qtd,
                       'proporcao': round(qtd / n, 8) if n else None,
                       'percentual': round(100*qtd / n, 4) if n else None})
    return result, 'agregado_para_privacidade' if len(arr) != len(LIMITES) else 'ok'


def construir_recorte(n_validas: int, contagens: tuple[int, ...]) -> dict:
    if n_validas < 0 or any(n < 0 for n in contagens):
        raise ValueError('Contagens negativas')
    n_high = sum(contagens)
    if n_high > n_validas:
        raise ValueError('POP_HIGH excede POP_VALID')
    bandas, situacao = mesclar_faixas(contagens)
    suprimido = situacao == 'suprimido_grupo_pequeno'
    return {'populacao': 'POP_HIGH', 'n_validas': int(n_validas),
            'n_high': None if suprimido else n_high,
            'percentual_high_sobre_validas': None if suprimido or not n_validas else round(100*n_high/n_validas, 4),
            'status_publicacao': situacao, 'faixas': bandas,
            'total_faixas_fecha_pop_high': None if suprimido else sum(x['quantidade'] for x in bandas) == n_high,
            'sem_dados_individuais': True}


def processar_ano(raiz: Path, ano: int, bloco: int) -> dict:
    caminho = origem(raiz, ano)
    if not caminho.is_file():
        raise FileNotFoundError(f'{ano}: microdados não encontrados: {caminho}')
    contagens = {uf: [0]*5 for uf in ('BR', *UFS)}
    validas = Counter({uf: 0 for uf in ('BR', *UFS)})
    perfeitas = Counter({uf: 0 for uf in ('BR', *UFS)})
    qa = Counter()
    for df in pd.read_csv(caminho, sep=';', encoding='utf-8-sig', encoding_errors='replace',
                          usecols=['SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO'],
                          dtype=str, keep_default_na=False, na_filter=False,
                          chunksize=bloco, on_bad_lines='error'):
        uf = df['SG_UF_PROVA'].str.strip().str.upper()
        st = df['TP_STATUS_REDACAO'].str.strip().eq('1')
        nota_txt = df['NU_NOTA_REDACAO'].str.strip()
        nota = pd.to_numeric(nota_txt.str.replace(',', '.', regex=False), errors='coerce')
        valido = st & nota.between(0, 1000)
        high = valido & nota.ge(900)
        mil = high & nota.eq(1000)
        qa['linhas'] += len(df)
        qa['validas'] += int(valido.sum())
        qa['high'] += int(high.sum())
        qa['1000'] += int(mil.sum())
        qa['status1_sem_nota'] += int((st & nota_txt.eq('')).sum())
        qa['status1_nota_invalida'] += int((st & nota_txt.ne('') & ~nota.between(0,1000)).sum())
        qa['validas_sem_uf'] += int((valido & uf.eq('')).sum())
        qa['validas_uf_invalida'] += int((valido & ~uf.isin(UFS) & uf.ne('')).sum())
        validas['BR'] += int(valido.sum())
        perfeitas['BR'] += int(mil.sum())
        for uf_code, n in uf[valido].value_counts().items():
            if uf_code in UFS:
                validas[str(uf_code)] += int(n)
        for uf_code, n in uf[mil].value_counts().items():
            if uf_code in UFS:
                perfeitas[str(uf_code)] += int(n)
        serie_high = nota[high]
        uf_high = uf[high]
        br_counts = calc_banda(serie_high)
        for i, n in enumerate(br_counts):
            contagens['BR'][i] += n
        for uf_code in uf_high.unique():
            if uf_code not in UFS:
                continue
            uf_counts = calc_banda(serie_high[uf_high.eq(uf_code)])
            for i, n in enumerate(uf_counts):
                contagens[str(uf_code)][i] += n
    if qa['linhas'] <= 0 or qa['status1_sem_nota'] or qa['status1_nota_invalida']:
        raise ValueError(f'{ano}: fonte vazia ou nota de redação inválida com status 1')
    if qa['validas_sem_uf'] or qa['validas_uf_invalida']:
        raise ValueError(f'{ano}: existem redações válidas sem UF válida')
    if sum(validas[x] for x in UFS) != qa['validas']:
        raise ValueError(f'{ano}: POP_VALID: soma 27 UFs não fecha')
    if sum(contagens['BR']) != qa['high'] or sum(sum(contagens[x]) for x in UFS) != qa['high']:
        raise ValueError(f'{ano}: POP_HIGH: somas não fecham')
    if contagens['BR'][-1] < perfeitas['BR']:
        raise ValueError(f'{ano}: número de notas 1000 excede última faixa')
    resultados = {'brasil': construir_recorte(validas['BR'], tuple(contagens['BR'])),
                  'ufs': [{'uf': uf, **construir_recorte(validas[uf],tuple(contagens[uf]))} for uf in UFS],
                  'qualidade':{'status':'ok','soma_27_ufs_igual_brasil': True,
                              'faixas_internas_fecham':True,
                              'recortes_suprimidos':sum(0 < sum(contagens[uf]) < MIN_N for uf in ('BR',*UFS)),
                              'recortes_faixas_mescladas':sum(
                                  construir_recorte(validas[uf],tuple(contagens[uf]))['status_publicacao'] == 'agregado_para_privacidade'
                                  for uf in ('BR',*UFS)),
                              'sem_identificadores':True},
                  'ano':ano,'arquivo_fonte':caminho.name}
    # Dados de conferência ficam apenas em memória, nunca no JSON ou CSV.
    internos={'val':dict(validas), 'mil':dict(perfeitas),
              'bands': {uf:tuple(contagens[uf]) for uf in ('BR',*UFS)},
              'linhas':qa['linhas']}
    return resultados, internos


def validar_contra_fontes(p: dict, interno: dict, refs: dict, periodo: str) -> None:
    for uf in ('BR', *UFS):
        r1 = grupo(refs[1], uf)
        r6 = grupo(refs[6], uf)
        r8 = grupo(refs[8], uf)
        if interno['val'][uf] != r1['redacoes_validas'] or interno['val'][uf] != r6['n_validas'] or interno['val'][uf] != r8['n_validas']:
            raise ValueError(f'{periodo}/{uf}: POP_VALID diverge dos IND-001/006/008')
        ultima = r6['faixas'][-1]
        if int(ultima['limite_inferior']) != 900 or int(ultima['limite_superior']) != 1000 or not ultima['superior_inclusivo']:
            raise ValueError(f'{periodo}/{uf}: última faixa do IND-006 inesperada')
        if sum(interno['bands'][uf]) != ultima['quantidade']:
            raise ValueError(f'{periodo}/{uf}: notas >=900 diferem do IND-006')
        if interno['mil'][uf] != r8['n_notas_1000']:
            raise ValueError(f'{periodo}/{uf}: notas 1000 diferem do IND-008')
        resumo = grupo(p,uf)
        if resumo['n_validas'] != interno['val'][uf]:
            raise AssertionError(f'{periodo}/{uf}: POP_VALID incorreta no módulo')
        if resumo['n_high'] is not None and resumo['n_high'] != ultima['quantidade']:
            raise AssertionError(f'{periodo}/{uf}: POP_HIGH incorreta no módulo')


def consolidar_historico(anos: list[dict], internos: list[dict], refs: dict) -> tuple[dict,dict]:
    vals = {uf:sum(z['val'][uf] for z in internos) for uf in ('BR',*UFS)}
    mils = {uf:sum(z['mil'][uf] for z in internos) for uf in ('BR',*UFS)}
    bands={uf:tuple(sum(z['bands'][uf][i] for z in internos) for i in range(5))
           for uf in ('BR',*UFS)}
    hist={'periodo':'2019-2025',
          'brasil':construir_recorte(vals['BR'], bands['BR']),
          'ufs':[{'uf':uf,**construir_recorte(vals[uf],bands[uf])} for uf in UFS],
          'qualidade':{'status':'ok','historico_recalculado_das_contagens':True,
                      'soma_27_ufs_igual_brasil':True}}
    priv={'val':vals,'mil':mils,'bands':bands}
    validar_contra_fontes(hist,priv,{i:r['historical'] for i,r in refs.items()},'2019-2025')
    if any(sum(z['val'][uf] for z in internos)!=vals[uf] for uf in ('BR',*UFS)):
        raise AssertionError('Histórico não fecha')
    return hist,priv


def atualizar_dashboard(d: dict, ano: dict, anos: list[dict], hist: dict, gerado: str) -> dict:
    novo = deepcopy(d)
    high = novo['pages']['high_performance']
    high['score_bands'] = {'indicator_id':ID,'population':'POP_HIGH','method':METODO,
                           'brasil':deepcopy(ano['brasil']), 'by_uf':deepcopy(ano['ufs']),
                           'privacy_note':NOTAS}
    high['status']='partial'
    high['reason']='IND-030 disponível; demais indicadores de alto desempenho pendentes'
    novo['pages']['temporal']['ind030']={
        'indicator_id':ID,'population':'POP_HIGH',
        'national_by_year':[{'year':p['ano'],**deepcopy(p['brasil'])} for p in anos],
        'period_total':deepcopy(hist['brasil']), 'period_by_uf':deepcopy(hist['ufs']),
        'note':'O histórico soma contagens e recalcula os percentuais, sem médias de porcentagens.'}
    novo['pages']['methodology']['ind030']={
        'definition':'Distribuição das redações válidas de 900 a 1000 pontos',
        'population':'POP_HIGH = TP_STATUS_REDACAO=1 e nota válida no intervalo [900,1000]',
        'source_indicator':['IND-001','IND-006','IND-008'],
        'method':METODO,'geography':'SG_UF_PROVA','minimum_published_cell':MIN_N,
        'score_bands':'900–<920, 920–<940, 940–<960, 960–<980, 980–1000; mesclagem adaptativa',
        'limitations':NOTAS}
    novo['quality']['ind030_validation']={
        'status':'ok','source_indicators':['IND-001','IND-006','IND-008'],
        'n_validas_brasil':ano['brasil']['n_validas'],
        'n_high_brasil':ano['brasil']['n_high'],
        'faixas_fecham':ano['qualidade']['faixas_internas_fecham'],
        'soma_27_ufs_igual_brasil':True,
        'recortes_suprimidos':ano['qualidade']['recortes_suprimidos'],
        'recortes_mesclados':ano['qualidade']['recortes_faixas_mescladas'],
        'revisao_academica_pendente':True,'revisao_privacidade_complementar_pendente':True}
    novo['meta']['analysis_version']=versao_para_dashboard(d.get('meta',{}).get('analysis_version',''))
    novo['meta']['generated_at']=gerado
    novo['meta']['data_status']='draft'
    aviso='IND-030: faixas 900–1000 (POP_HIGH) validadas computacionalmente; revisão acadêmica e supressão cruzada de contagens pequenas pendentes.'
    if aviso not in novo['meta'].setdefault('warnings',[]):
        novo['meta']['warnings'].append(aviso)
    return novo


def gerar_csv(anos: list[dict], historico: dict) -> list[dict]:
    linhas=[]
    for p in (*anos, historico):
        periodo=str(p.get('ano','2019-2025'))
        for uf in ('BR',*UFS):
            rec=grupo(p,uf)
            bandas=rec['faixas'] if rec['faixas'] else [{'faixa':'SUPRIMIDA','limite_inferior':None,
                                                          'limite_superior':None,'quantidade':None,
                                                          'percentual':None,'proporcao':None}]
            for b in bandas:
                linhas.append({'indicador_id':ID,'periodo':periodo,'uf':uf,
                               'abrangencia':'BRASIL' if uf=='BR' else 'UF',
                               'populacao':'POP_HIGH','n_validas':rec['n_validas'],
                               'n_high':rec['n_high'],
                               'percentual_high_sobre_validas':rec['percentual_high_sobre_validas'],
                               'faixa':b['faixa'],'limite_inferior':b['limite_inferior'],
                               'limite_superior':b['limite_superior'],
                               'quantidade':b['quantidade'],'percentual_na_pop_high':b['percentual'],
                               'status_publicacao':rec['status_publicacao'],
                               'metodo':METODO})
    if len(linhas)<224:
        raise AssertionError('O CSV precisa conter ao menos 224 linhas de recorte')
    return linhas


def executar(raiz: Path, bloco: int = 100_000, somente_modulo: bool = False,
             sobrescrever: bool = False) -> dict:
    raiz=raiz.resolve()
    if bloco < 1:
        raise ValueError('--bloco deve ser >= 1')
    refs=carregar_referencias(raiz)
    jdir=raiz/'outputs/json'
    csvdir=raiz/'outputs/indicadores'
    saidas=[jdir/f'{ARQUIVO}.json',csvdir/f'{ARQUIVO}.csv']
    dashboards={}
    hashes={}
    if not somente_modulo:
        for ano in ANOS:
            f=jdir/f'dashboard_enem_{ano}.json'
            d=ler_json(f)
            verificar_dashboard(d,ano)
            if not sobrescrever and (d['quality'].get('ind030_validation') is not None or
                                     'score_bands' in d['pages']['high_performance']):
                raise FileExistsError(f'IND-030 já aparece no dashboard {ano}. Use --sobrescrever')
            dashboards[ano]=d
            hashes[ano]=hashlib.sha256(f.read_bytes()).hexdigest()
    if not sobrescrever:
        for f in saidas:
            if f.exists():
                raise FileExistsError(f'IND-030 já existe: {f}; use --sobrescrever')
    anos=[]
    internos=[]
    qa={}
    for ano in ANOS:
        print(f'IND-030 | {ano}: {origem(raiz,ano).name}',flush=True)
        p,priv=processar_ano(raiz,ano,bloco)
        validar_contra_fontes(p,priv,{k:v['years'][ano-2019] for k,v in refs.items()},str(ano))
        if priv['linhas'] != refs[1]['years'][ano-2019]['brasil']['total_registros']:
            raise ValueError(f'{ano}: linhas de fonte diferem do IND-001')
        anos.append(p); internos.append(priv)
        qa[str(ano)]={'arquivo':p['arquivo_fonte'],'linhas_lidas':priv['linhas'],
                      'n_validas':priv['val']['BR'], 'n_high':sum(priv['bands']['BR']),
                      'n_notas_1000_conferidas':True}
        print(f'  POP_VALID={priv["val"]["BR"]:,}  POP_HIGH={sum(priv["bands"]["BR"]):,}',flush=True)
    hist,_=consolidar_historico(anos,internos,refs)
    gerado=datetime.now(timezone.utc).isoformat(timespec='seconds')
    meta_versao=versao_para_dashboard(next(iter(dashboards.values()))['meta'].get('analysis_version','')) if dashboards else '2.30.0-ind030'
    modulo={'meta':{'indicator_id':ID,'module_schema_version':'ind030-module-1.0.0',
                    'analysis_version':meta_versao,
                    'dataset_version':'enem-2019-2025-csv-publico',
                    'generated_at':gerado,'data_status':'draft',
                    'source_indicators':['IND-001','IND-006','IND-008'],
                    'population_definition':'POP_HIGH = POP_VALID e 900 <= NU_NOTA_REDACAO <= 1000',
                    'geographic_dimension':'SG_UF_PROVA','method':METODO,
                    'minimum_published_cell':MIN_N,
                    'source_qa':qa,
                    'publication_status':'draft; revisão acadêmica e de privacidade cruzada pendentes',
                    'notes':NOTAS},
            'indicator':{'id':ID,'name':'Faixas 900–1000','unit':'redacoes',
                         'dashboard_json_path':'pages.high_performance.score_bands',
                         'visualization':'barras'},
            'years':anos,'historical':hist,
            'dashboard_files':[f'dashboard_enem_{ano}.json' for ano in ANOS]}
    linhas=gerar_csv(anos,hist)
    novos={} if somente_modulo else {ano:atualizar_dashboard(dashboards[ano],anos[i],anos,hist,gerado)
                                       for i,ano in enumerate(ANOS)}
    for ano,d in novos.items():
        if d['quality'].get('ind027_validation',{}).get('status') != 'ok':
            raise AssertionError(f'{ano}: IND-027 foi alterado')
        for candidato in (raiz/'04_resultados_analises.schema.json',
                          raiz/'docs/04_resultados_analises.schema.json'):
            if candidato.is_file():
                try:
                    import jsonschema
                except ImportError:
                    break
                jsonschema.validate(d,ler_json(candidato))
                break
    json.dumps(modulo,allow_nan=False)
    # Todas as saídas são construídas antes de modificar um arquivo de destino.
    out=raiz/'outputs'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind030_stage_',dir=out) as staging:
        tmp=Path(staging)
        stages=[]
        js=tmp/saidas[0].name
        cs=tmp/saidas[1].name
        gravar_json(js,modulo)
        with cs.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(linhas[0]),delimiter=';')
            writer.writeheader();writer.writerows(linhas)
        stages.extend([(js,saidas[0]),(cs,saidas[1])])
        for ano,d in novos.items():
            f=tmp/f'dashboard_enem_{ano}.json'
            gravar_json(f,d)
            stages.append((f,jdir/f.name))
        for ano in ANOS:
            if not somente_modulo and hashlib.sha256((jdir/f'dashboard_enem_{ano}.json').read_bytes()).hexdigest()!=hashes[ano]:
                raise RuntimeError(f'Dashboard {ano} foi alterado durante o processamento; nenhuma saída gravada')
        # Backup temporário para reversão se a gravação de um dos arquivos falhar.
        backups=[]
        for _,dest in stages:
            if dest.exists():
                bk=tmp/(str(len(backups))+'_'+dest.name+'.backup')
                bk.write_bytes(dest.read_bytes())
                backups.append((dest,bk))
        concluidos=[]
        try:
            for origem_stage,dest in stages:
                dest.parent.mkdir(parents=True,exist_ok=True)
                os.replace(origem_stage,dest)
                concluidos.append(dest)
        except Exception:
            for destino in reversed(concluidos):
                backup=next((bk for dd,bk in backups if dd==destino),None)
                if backup:
                    os.replace(backup,destino)
                else:
                    destino.unlink(missing_ok=True)
            raise
    print(f'IND-030 concluído: 224 recortes, {len(linhas)} linhas CSV, módulo JSON.' +
          (' Dashboards 2019–2025 atualizados.' if not somente_modulo else ' Dashboards não modificados.'))
    return modulo


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=Path(__file__).resolve().parents[2],help='raiz do projeto')
    ap.add_argument('--bloco',type=int,default=100_000,help='linhas por bloco de leitura')
    ap.add_argument('--somente-modulo',action='store_true',help='gera CSV e JSON, sem atualizar dashboards')
    ap.add_argument('--sobrescrever',action='store_true',help='atualiza IND-030 já existente')
    a=ap.parse_args()
    executar(a.base,a.bloco,a.somente_modulo,a.sobrescrever)


if __name__=='__main__':
    main()
