#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria consolidada, somente leitura, das pendências do Lote 1 do ENEM.

Execute na raiz do repositorio (branch de correcao):
    python auditar_pendencias_lote1.py

Compara dados atuais com HEAD, sem sobrescrever arquivos nem criar relatórios.
"""
from __future__ import annotations

import csv
import io
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()
PROBLEMAS = []
AVISOS = []


def say(text=''):
    print(text)


def mark(level, detail):
    (PROBLEMAS if level == 'ERRO' else AVISOS).append(detail)
    say(f'  [{level}] {detail}')


def table_csv(path):
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as fh:
        r = csv.DictReader(fh, delimiter=';')
        return list(r)


def git_csv(path):
    data = subprocess.check_output(['git', 'show', 'HEAD:'+str(path).replace('\\', '/')])
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')), delimiter=';'))


def paths(stem):
    p = Path('outputs/indicadores') / (stem+'.csv')
    if not p.exists():
        raise FileNotFoundError(p)
    return git_csv(p), table_csv(p)


def map_by(rows, columns, title):
    result = {}
    duplicates = 0
    for r in rows:
        key = tuple(r.get(c, '') for c in columns)
        if key in result:
            duplicates += 1
        result[key] = r
    if duplicates:
        mark('ERRO', f'{title}: {duplicates} chaves repetidas')
    return result


def compare(a, b, columns, title):
    ma = map_by(a, columns, title+' (HEAD)')
    mb = map_by(b, columns, title+' (atual)')
    new, deleted, common = mb.keys()-ma.keys(), ma.keys()-mb.keys(), ma.keys() & mb.keys()
    say(f'  Antes={len(a)}  Agora={len(b)}  Novas={len(new)}  Removidas={len(deleted)}  Comuns={len(common)}')
    return ma, mb, new, deleted, common


def number(s):
    return float(s) if s not in ('', None) else None


def integer(s):
    return int(s) if s not in ('', None) else None


def check_031():
    title='IND-031'
    say('\n'+title+' — perdas por competência')
    a,b=paths('IND_031_perda_competencias')
    ma,mb,new,deleted,common=compare(a,b,['periodo','uf','faixa','competencia'],title)
    changes=[k for k in common if any(ma[k].get(c)!=mb[k].get(c) for c in ('n_redacoes','media_perda','mediana_perda','soma_pontos_perdidos'))]
    small=sum(1 for k in new if (integer(mb[k].get('n_redacoes')) or 0) in range(1,30))
    empty=[(r.get('periodo'),r.get('uf'),r.get('faixa'),r.get('n_redacoes')) for r in b if any(not r.get(c) for c in ('competencia','media_perda','mediana_perda','soma_pontos_perdidos'))]
    empty_pos=[x for x in empty if integer(x[3]) not in (None,0)]
    invalid=[]
    for idx,r in enumerate(b,2):
        n=integer(r.get('n_redacoes'))
        if n is None or n < 0:
            invalid.append(idx)
            continue
        for col in ('media_perda','mediana_perda'):
            x=number(r.get(col))
            if x is not None and not (math.isfinite(x) and 0 <= x <= 200):
                invalid.append(idx)
        s=number(r.get('soma_pontos_perdidos'))
        if s is not None and (not math.isfinite(s) or s<0 or s>n*200):
            invalid.append(idx)
    say(f'  Novas linhas com N=1..29: {small}; linhas antigas com métricas alteradas: {len(changes)}')
    say(f'  Linhas com vazios: {len(empty)}; vazios com N>0: {len(empty_pos)}; linhas inválidas: {len(set(invalid))}')
    if empty:
        say(f'  Vazios (até 3): {empty[:3]}')
    if deleted or changes or empty_pos or invalid:
        mark('AVISO','IND-031: revisar remoções, alterações ou valores inválidos (veja contagens acima)')


def check_036():
    title='IND-036'
    say('\n'+title+' — Apriori / regras de associação')
    a,b=paths('IND_036_regras_associacao')
    ma,mb,new,deleted,common=compare(a,b,['ano','uf','antecedente','consequente','itemset'],title)
    numeric=['n_near','n_antecedente','n_consequente','n_ambos','suporte','suporte_percentual','confianca','confianca_percentual','lift','leverage']
    changes=[k for k in common if any(ma[k].get(c)!=mb[k].get(c) for c in numeric)]
    small=[k for k in new if 1<=(integer(mb[k].get('n_ambos')) or 0)<=29]
    wrong=[]
    for i,r in enumerate(b,2):
        try:
            n,na,nc,na_b=[int(r[k]) for k in ('n_near','n_antecedente','n_consequente','n_ambos')]
            if not (0<na_b<=min(na,nc) and max(na,nc)<=n):
                wrong.append(i); continue
            support=na_b/n
            conf=na_b/na
            lift=conf/(nc/n)
            lev=support-(na/n)*(nc/n)
            expected={'suporte':support,'suporte_percentual':100*support,'confianca':conf,
                      'confianca_percentual':100*conf,'lift':lift,'leverage':lev}
            if any(abs(float(r[c])-v)> (1e-5 if 'percentual' in c else 1e-7) for c,v in expected.items()):
                wrong.append(i)
        except (ValueError,TypeError,ZeroDivisionError,KeyError):
            wrong.append(i)
    say(f'  Novas com n_ambos 1..29: {len(small)}; antigas alteradas: {len(changes)}; erros matemáticos: {len(wrong)}')
    for k in sorted(deleted):
        r=ma[k]
        say(f'  Regra REMOVIDA: ano={r.get("ano")} UF={r.get("uf")} {r.get("antecedente")} -> {r.get("consequente")}; n_ambos={r.get("n_ambos")}; suporte={r.get("suporte")}; confiança={r.get("confianca")}')
        nov_grp=[mb[z] for z in new if z[:2]==k[:2]]
        say(f'    Novas regras para o mesmo ano/UF: {len(nov_grp)}')
    if deleted:
        mark('AVISO','IND-036: regra antiga removida; conferir efeito de ranking/top-N e critérios antes de homologar')
    if small:
        mark('AVISO',f'IND-036: {len(small)} regras novas com n_ambos de 1 a 29; revisar limiares de Apriori e privacidade')
    if changes or wrong:
        mark('ERRO','IND-036: houve divergências matemáticas ou alterações de valores prévios')


def check_037():
    title='IND-037'
    say('\n'+title+' — testes de concentração de descontos')
    a,b=paths('IND_037_concentracao_descontos')
    ma,mb,new,deleted,common=compare(a,b,['ano','uf','familia','teste','competencia_a','competencia_b'],title)
    filled=lost=other_changes=0
    for k in common:
        for col in ('estatistica','p_valor','p_ajustado_holm','significativo_5pct','n_pares_informativos','status_teste'):
            before=ma[k].get(col,'')
            after=mb[k].get(col,'')
            if not before and after: filled+=1
            elif before and not after: lost+=1
            elif before!=after: other_changes+=1
    wrong=[]
    for i,r in enumerate(b,2):
        try:
            p=number(r.get('p_valor'))
            padj=number(r.get('p_ajustado_holm'))
            if p is not None and (not math.isfinite(p) or not 0<=p<=1):wrong.append(i)
            if padj is not None and (not math.isfinite(padj) or not 0<=padj<=1):wrong.append(i)
            if p is not None and padj is not None and padj+1e-9<p:wrong.append(i)
        except ValueError:
            wrong.append(i)
    say(f'  Campos preenchidos: {filled}; campos que ficaram vazios: {lost}; outras alterações: {other_changes}; p-valores inválidos: {len(set(wrong))}')
    if new or deleted or lost or wrong:
        mark('AVISO','IND-037: revisar linhas novas/removidas, novos vazios ou p-valores inválidos')


def check_040():
    title='IND-040'
    say('\n'+title+' — perfil socioeconômico')
    a,b=paths('IND_040_perfil_socioeconomico')
    ma,mb,new,deleted,common=compare(a,b,['periodo','uf','questao','categoria'],title)
    small=sum(1 for k in new if 1<=(integer(mb[k].get('quantidade')) or 0)<=29)
    changed=[k for k in common if any(ma[k].get(c)!=mb[k].get(c) for c in ('n_pop_socio','quantidade','proporcao','percentual'))]
    errors=[]; empty_groups=[]; group_totals={}
    groups=defaultdict(list)
    for r in b:
        groups[(r['periodo'],r['uf'],r['questao'])].append(r)
    for k,rr in groups.items():
        try:
            if any(x.get('quantidade','')=='' for x in rr):
                empty_groups.append(k)
                continue
            n_values={int(x['n_pop_socio']) for x in rr}
            if len(n_values)!=1:
                errors.append(('denominador_inconstante',k)); continue
            n=next(iter(n_values)); total=sum(int(x['quantidade']) for x in rr)
            if n!=total:
                errors.append(('soma_diferente_do_denominador',k))
            group_totals[k]=n
        except (ValueError,KeyError):
            errors.append(('invalid_number',k))
    percent_errors=[]
    for i,r in enumerate(b,2):
        if r.get('quantidade','')=='' or r.get('n_pop_socio','')=='':continue
        try:
            n=int(r['n_pop_socio']); count=int(r['quantidade'])
            if n>0:
                if not 0<=count<=n:percent_errors.append(i)
                elif abs(float(r['percentual']) - 100*count/n)>0.001:percent_errors.append(i)
                elif abs(float(r['proporcao']) - count/n)>0.00001:percent_errors.append(i)
        except (ValueError,KeyError):
            percent_errors.append(i)
    say(f'  Novas categorias com N=1..29: {small}; chaves anteriores com valores alterados: {len(changed)}')
    say(f'  Grupos com soma exata: {len(group_totals)}; grupos sem dados completos: {len(empty_groups)}; somas inválidas: {len(errors)}; percentuais inválidos: {len(percent_errors)}')
    if deleted:
        say('  Categorias antigas removidas (até 5): '+repr(sorted(deleted)[:5]))
    if changed:
        say('  Categorias antigas alteradas (até 5): '+repr(sorted(changed)[:5]))
    if deleted or changed:
        mark('AVISO','IND-040: revisar remoção/alteração de categorias antigas por agrupamentos desfeitos')
    if errors or percent_errors:
        mark('ERRO','IND-040: divergência de contagem por questão/UF/ano ou percentual')


def check_jsons():
    say('\nJSONs modificados — sintaxe')
    paths=subprocess.check_output(['git','diff','--name-only','--','outputs/json'],text=True).splitlines()
    broken=[]
    import json
    for name in paths:
        if not name.endswith('.json'):continue
        try:
            with open(name,encoding='utf-8-sig') as f:
                json.load(f)
        except (ValueError,OSError) as e:
            broken.append((name,str(e)[:80]))
    say(f'  Arquivos JSON verificados: {sum(x.endswith(".json") for x in paths)}; inválidos: {len(broken)}')
    if broken:
        mark('ERRO','JSON(s) inválido(s): '+repr(broken[:3]))


def main():
    if not (ROOT/'outputs/indicadores').is_dir():
        sys.exit('Execute na raiz do repositório (pasta com outputs/indicadores).')
    say('AUDITORIA CONSOLIDADA — LOTE 1 (somente leitura)')
    for test in (check_031,check_036,check_037,check_040,check_jsons):
        try:
            test()
        except Exception as e:
            mark('ERRO',f'{test.__name__}: {type(e).__name__}: {e}')
    say('\nRESUMO')
    say(f'  Alertas que requerem análise: {len(AVISOS)}')
    say(f'  Problemas detectados: {len(PROBLEMAS)}')
    say('  Nenhum arquivo foi modificado.')
    if PROBLEMAS:
        sys.exit(1)
    say('  Este teste não substitui validação independente dos microdados nem revisão de privacidade.')


if __name__=='__main__':
    main()
