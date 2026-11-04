#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria focalizada dos alertas IND-031, IND-036 e IND-040 (somente leitura).

Execute na raiz do repositorio: python auditar_alertas_finais_lote1.py
Lê CSV/JSON/código atuais e versões HEAD via git. Não grava resultados.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ERROS = []
AVISOS = []


def dados(nome):
    caminho = 'outputs/indicadores/' + nome + '.csv'
    original = subprocess.check_output(['git', 'show', 'HEAD:' + caminho]).decode('utf-8-sig')
    with open(caminho, encoding='utf-8-sig', newline='') as f:
        atual = list(csv.DictReader(f, delimiter=';'))
    antigo = list(csv.DictReader(io.StringIO(original), delimiter=';'))
    return antigo, atual


def registrar(tipo, mensagem):
    print('  [' + tipo + '] ' + mensagem)
    (ERROS if tipo == 'ERRO' else AVISOS).append(mensagem)


def chave_031(r):
    return r.get('periodo'), r.get('uf'), r.get('faixa'), r.get('competencia')


def auditar_031():
    print('\nIND-031 — conservacao das contagens e perdas apos desagregacao')
    antes, depois = dados('IND_031_perda_competencias')
    ab = {chave_031(r): r for r in antes}
    de = {chave_031(r): r for r in depois}
    removidas = set(ab) - set(de)
    alteradas = {k for k in ab.keys() & de.keys() if any(ab[k].get(c) != de[k].get(c)
                 for c in ('n_redacoes', 'media_perda', 'mediana_perda', 'soma_pontos_perdidos'))}
    antigos_totais = {(r['periodo'],r['uf'],r['competencia']):r for r in antes
                      if r['faixa']=='POP_NEAR_TOTAL' and r['competencia'] in ('C1','C2','C3','C4','C5')}
    novos_totais = {(r['periodo'],r['uf'],r['competencia']):r for r in depois
                     if r['faixa']=='POP_NEAR_TOTAL' and r['competencia'] in ('C1','C2','C3','C4','C5')}
    divergencias_totais=[]
    for k in antigos_totais.keys() & novos_totais.keys():
        a,d=antigos_totais[k],novos_totais[k]
        if a.get('n_redacoes') != d.get('n_redacoes') or abs(float(a['soma_pontos_perdidos'])-float(d['soma_pontos_perdidos'])) > 0.001:
            divergencias_totais.append(k)

    faixas=defaultdict(list)
    for r in depois:
        if r['competencia'] in ('C1','C2','C3','C4','C5') and r['faixa']!='POP_NEAR_TOTAL':
            faixas[(r['periodo'],r['uf'],r['competencia'])].append(r)
    inconsistencias=[]
    for k, resumo in novos_totais.items():
        rr=faixas.get(k,[])
        if not rr:
            inconsistencias.append((k, 'sem faixas'));continue
        if sum(int(x['n_redacoes']) for x in rr) != int(resumo['n_redacoes']):
            inconsistencias.append((k, 'N nao fecha'))
        if abs(sum(float(x['soma_pontos_perdidos']) for x in rr)-float(resumo['soma_pontos_perdidos']))>0.001:
            inconsistencias.append((k,'somas de perdas nao fecham'))
    print(f'  Chaves antigas removidas={len(removidas)}; chaves comuns alteradas={len(alteradas)}')
    print(f'  Resumos antigos preservados: {len(antigos_totais.keys() & novos_totais.keys())-len(divergencias_totais)}; divergentes={len(divergencias_totais)}')
    print(f'  Resumos atuais com faixas consistentes={len(novos_totais)-len(set(k for k,_ in inconsistencias))}; inconsistentes={len(set(k for k,_ in inconsistencias))}')
    if divergencias_totais:
        registrar('ERRO', 'IND-031: resumos POP_NEAR_TOTAL mudaram: '+repr(divergencias_totais[:4]))
    if inconsistencias:
        registrar('ERRO', 'IND-031: N ou soma de perda por faixa nao fecha: '+repr(inconsistencias[:4]))
    if removidas or alteradas:
        print('  Nota: linhas antigas de faixas agregadas podem mudar quando as faixas sao desmembradas.')


def ranking_036(r):
    return (-float(r['lift']), -float(r['confianca']), -float(r['suporte']),r['antecedente'],r['consequente'])


def auditar_036():
    print('\nIND-036 — limite minimo, limiares e regra excluida do Top-N')
    antes, depois=dados('IND_036_regras_associacao')
    def chave(r):
        return (r['ano'],r['uf'],r['antecedente'],r['consequente'],r['itemset'])
    ma={chave(r):r for r in antes}; md={chave(r):r for r in depois}
    new=md.keys()-ma.keys(); removed=ma.keys()-md.keys()
    regras_pequenas=[r for r in depois if 1 <= int(r['n_ambos']) < 30]
    minimas={c:min(int(r[c]) for r in depois) for c in ('n_antecedente','n_consequente','n_ambos')}
    parametro=None
    caminho_json=Path('outputs/json/IND_036_regras_associacao.json')
    if caminho_json.exists():
        obj=json.loads(caminho_json.read_text(encoding='utf-8-sig'))
        parametro=obj.get('parameters',{}).get('min_contagem_itemset')
    codigo=Path('src/indicadores/IND_036_regras_associacao.py')
    fonte=codigo.read_text(encoding='utf-8-sig') if codigo.exists() else ''
    match=re.search(r'^MIN_N\s*=\s*(\d+)\b', fonte, flags=re.M)
    min_codigo=int(match.group(1)) if match else 'nao identificado'
    print('  Regras novas:',len(new),'| removidas:',len(removed),'| atuais com n_ambos 1..29:',len(regras_pequenas))
    print('  Menores contagens presentes (A, B, A+B):',minimas)
    print('  min_contagem_itemset declarado no JSON:',parametro,'| MIN_N no Python:',min_codigo)
    if isinstance(parametro,int) and any(int(r[c])<parametro for r in depois for c in ('n_antecedente','n_consequente','n_ambos')):
        registrar('ERRO',f'IND-036: ha regras com contagem abaixo do minimo {parametro} declarado no JSON.')
    elif parametro is None:
        registrar('AVISO','IND-036: parametro minimo nao encontrado no JSON; revisar metodologia.')
    if isinstance(min_codigo,int) and isinstance(parametro,int) and min_codigo!=parametro:
        registrar('AVISO',f'IND-036: minimo implementado ({min_codigo}) diferente do declarado ({parametro}).')
    default={'min_suporte':0.01,'min_confianca':0.30,'min_lift':1.0,'max_regras_por_recorte':30}
    p={**default,**(obj.get('parameters',{}) if caminho_json.exists() else {})}
    fora=[r for r in depois if float(r['suporte'])+1e-9<float(p['min_suporte']) or float(r['confianca'])+1e-9<float(p['min_confianca']) or float(r['lift'])+1e-9<float(p['min_lift'])]
    grupos=defaultdict(list)
    for r in depois: grupos[(r['ano'],r['uf'])].append(r)
    excedentes=[(k,len(v)) for k,v in grupos.items() if len(v)>int(p['max_regras_por_recorte'])]
    print('  Regras fora dos limiares percentuais/confiança/lift:',len(fora),'| grupos acima do Top-N:',len(excedentes))
    if fora or excedentes:
        registrar('ERRO','IND-036: limites de selecao nao cumpridos (ver quantidades acima).')
    for k in sorted(removed):
        r=ma[k]; g=grupos.get((r['ano'],r['uf']),[])
        pos=1+sum(ranking_036(x)<ranking_036(r) for x in g)
        print(f"  Excluida: {r['ano']}/{r['uf']} {r['antecedente']} -> {r['consequente']}; posicao frente as atuais={pos}; regras atuais neste grupo={len(g)}")
        if len(g)==int(p['max_regras_por_recorte']) and pos>len(g):
            print('  Hipotese sustentada: exclusao compativel com substituicao no Top-N.')
        else:
            registrar('AVISO','IND-036: exclusao nao explicada diretamente pela posicao Top-N; revisar ranking/limiares.')
    if regras_pequenas:
        registrar('AVISO','IND-036: avaliar estabilidade estatistica de regras com poucas ocorrencias e privacidade cruzada, mesmo se o minimo for alterado intencionalmente.')


def auditar_040():
    print('\nIND-040 — decomposicao de categorias agrupadas e fechamento territorial')
    antes, depois=dados('IND_040_perfil_socioeconomico')
    def grupo(r):return (r['periodo'],r['uf'],r['questao'])
    aa=defaultdict(dict); bb=defaultdict(dict)
    for r in antes:
        if r['questao']:aa[grupo(r)][r['categoria']]=r
    for r in depois:
        if r['questao']:bb[grupo(r)][r['categoria']]=r
    faltantes=[]; total_div=[]; decomposicao=[]
    for k,old in aa.items():
        current=bb.get(k,{})
        if not current:
            faltantes.append(k);continue
        soma_old=sum(int(x['quantidade']) for x in old.values() if x['quantidade'])
        soma_new=sum(int(x['quantidade']) for x in current.values() if x['quantidade'])
        if soma_old!=soma_new:total_div.append((k,soma_old,soma_new))
        agg=old.get('__CATEGORIAS_AGREGADAS__')
        if agg and '__CATEGORIAS_AGREGADAS__' not in current:
            novos=sum(int(x['quantidade']) for cat,x in current.items() if cat not in old and x['quantidade'])
            esperado=int(agg['quantidade'])
            if novos!=esperado:decomposicao.append((k,esperado,novos))
    recortes=defaultdict(dict)
    for k,r in bb.items():recortes[(k[0],k[2])][k[1]]=r
    territorio=[]
    for k,uf_map in recortes.items():
        if 'BR' not in uf_map:continue
        br=uf_map['BR']; states={}
        for uf, cats in uf_map.items():
            if uf=='BR':continue
            for cat,r in cats.items():states[cat]=states.get(cat,0)+int(r['quantidade'])
        for cat,r in br.items():
            if int(r['quantidade']) != states.get(cat,0): territorio.append((k,cat,int(r['quantidade']),states.get(cat,0)))
        for cat,valor in states.items():
            if cat not in br and valor!=0:territorio.append((k,cat,'ausente BR',valor))
    no_data=[r for r in depois if not r.get('questao') and not r.get('quantidade')]
    print('  Grupos antigos comparados:',len(aa),'| grupos ausentes:',len(faltantes),'| totais divergentes:',len(total_div))
    print('  Agregacoes anteriores que nao se reconciliam com categorias novas:',len(decomposicao))
    print('  Divergencias BR x soma das UFs por categoria:',len(territorio))
    print('  Linhas de metadados sem questao/quantidade:',len(no_data))
    for descricao,x in [('grupos ausentes',faltantes),('somas por grupo',total_div),('decomposicao de agregadas',decomposicao),('territorio',territorio)]:
        if x:registrar('ERRO','IND-040: '+descricao+' - exemplos '+repr(x[:3]))
    if no_data and len(no_data)==28:
        print('  28 linhas historicas sem distribuicao por questao: compatíveis com estrutura declarada, sem validar semantica.')


def main():
    print('AUDITORIA FOCALIZADA — LOTE 1 | SOMENTE LEITURA')
    for tarefa in (auditar_031,auditar_036,auditar_040):
        try: tarefa()
        except Exception as ex:
            registrar('ERRO',f'{tarefa.__name__}: {type(ex).__name__}: {ex}')
    print('\nRESUMO: erros=',len(ERROS),'| avisos=',len(AVISOS))
    print('Nenhuma saida foi alterada; os avisos de privacidade nao sao aprovacao de publicacao.')
    if ERROS:
        print('ATENCAO: ha criterios contraditorios ou somas invalidas; NAO homologar ainda.')
    else:
        print('Fechamentos avaliados sem erros; revisar avisos antes de homologar.')


if __name__ == '__main__':
    main()
