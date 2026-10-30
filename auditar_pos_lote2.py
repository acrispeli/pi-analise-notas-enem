#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria consolidada, SOMENTE leitura, do Lote 2 (IND-021,022,024,025,026,029,033,053,054).

Executar na raiz de pi-analise-notas-enem:
    python auditar_pos_lote2.py

Não executa indicadores, não instala pacotes e não modifica CSV/JSON/dashboards.
Verifica os arquivos locais gerados, os fechamentos aritméticos, o registro dos
blocos no dashboard e, se presente, o backup pré-Lote 2 de 20261030_095805.
Imprime alertas e falhas e salva relatório próprio em auditorias_lote2/.
Limites: não reprocessa microdados; não substitui revisão acadêmica/privacidade.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
IDS = (21,22,24,25,26,29,33,53,54)
UFS = set('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split())
PERIODOS = {str(ano) for ano in range(2019, 2026)}
BLOCKS = {
 21: ('evaluators','by_competency'),
 22: ('evaluators','official_discrepancy'),
 24: ('evaluators','third_reviewer_rate'),
 25: ('evaluators','panel_rate'),
 26: ('evaluators','weighted_kappa'),
 29: ('evaluators','anomalies'),
 33: ('high_performance','loss_share'),
 53: ('ml','socio_mca'),
 54: ('ml','socio_clusters'),
}

falhas, alertas, checagens, resultados = [], [], Counter(), {}

def fail(msg):
    falhas.append(msg)
    if len(falhas) <= 35:
        print('FALHA:',msg)

def warn(msg):
    alertas.append(msg)
    if len(alertas) <= 30:
        print('ALERTA:', msg)

def ok(test='verificacoes'):
    checagens[test]+=1

def num(value):
    if value is None or str(value).strip().lower() in ('','none','null','nan'):
        return None
    try:
        v=float(str(value).replace(',','.'))
        if not math.isfinite(v): return None
        return v
    except (TypeError, ValueError): return None

def approx(a,b,tol=0.015):
    a,b=num(a),num(b)
    return a is not None and b is not None and abs(a-b)<=tol

def count(value, label):
    v=num(value)
    if v is None or v<0 or not v.is_integer():
        fail(f'{label}: contagem inteira não negativa inválida: {value!r}')
        return None
    ok('contagens_validas')
    return int(v)

def load_csv(path):
    with path.open('r',encoding='utf-8-sig',newline='') as fh:
        reader=csv.DictReader(fh,delimiter=';')
        head=reader.fieldnames or []
        rows=list(reader)
    if not head or not rows:
        raise ValueError('CSV vazio ou sem cabeçalho')
    if any(None in x for x in rows):
        raise ValueError('CSV possui colunas extras não identificadas')
    return head, rows

def check_fraction(row, a,b,label,tol=0.02):
    x,y=num(row.get(a)),num(row.get(b))
    if x is not None and y is not None and not approx(y,x*100,tol):
        fail(f'{label}: {b} diverge de 100 × {a}')
    elif x is not None and y is not None: ok('percentuais')

def groups(rows,keys):
    g=defaultdict(list)
    for row in rows: g[tuple(row.get(k) for k in keys)].append(row)
    return g

def geography(rows, idn):
    field='periodo' if 'periodo' in rows[0] else 'ano'
    by=groups(rows,(field,))
    for period,chunk in sorted(by.items()):
        ufs={r.get('uf') for r in chunk}
        if ufs and ufs != UFS|{'BR'}:
            fail(f'IND-{idn:03} {period[0]}: geografia incompleta ({len(ufs)} de 28)')
        else: ok('geografia_completa')

def reconcile_geo(rows,idn,fields):
    by=groups(rows,('periodo',))
    for (period,),rs in by.items():
        br=next((r for r in rs if r['uf']=='BR'),None)
        ufrows=[r for r in rs if r['uf']!='BR']
        if br is None or len(ufrows)!=27:
            fail(f'IND-{idn:03}/{period}: linhas BR/UF inconsistentes')
            continue
        for f in fields:
            vals=[count(r.get(f),f'IND-{idn:03}/{period}/{r["uf"]}/{f}') for r in ufrows]
            target=count(br.get(f),f'IND-{idn:03}/{period}/BR/{f}')
            if None not in vals and target is not None:
                if sum(vals)!=target:
                    fail(f'IND-{idn:03}/{period}/{f}: soma UF={sum(vals)}, BR={target}')
                else: ok('ufs_fecham_brasil')

def check_evaluator(data,idn):
    if idn in (21,26):
        for (p,uf), rows in groups(data,('periodo','uf')).items():
            cs=[r.get('competencia') for r in rows]
            if set(cs)!={'C1','C2','C3','C4','C5'} or len(cs)!=5:
                fail(f'IND-{idn:03}/{p}/{uf}: deveria haver C1..C5 exatas')
            else: ok('cinco_competencias')
        if idn==26:
            for r in data:
                for k in ('percentual_concordancia_exata','percentual_cobertura'):
                    v=num(r.get(k))
                    if v is not None and not 0<=v<=100.000001: fail(f'IND-026/{r.get("periodo")}/{r.get("uf")}/{k}: percentual fora de 0-100')
                kap=num(r.get('kappa_ponderado_quadratico'))
                if kap is not None and not -1.001 <= kap <=1.001: fail(f'IND-026/{r.get("periodo")}/{r.get("uf")}: kappa fora de -1..1')
        else:
            for r in data:
                if num(r.get('n_pares_validos')) is not None and num(r.get('n_pop_evaluator')) is not None:
                    if num(r['n_pares_validos'])>num(r['n_pop_evaluator']): fail('IND-021: pares excedem população')
    elif idn==22:
        for r in data:
            a,b,c=map(lambda k:num(r.get(k)),('n_discrepancia_confirmada','n_sem_discrepancia_confirmada','n_indeterminada'))
            t=num(r.get('n_pop_evaluator'))
            if None not in (a,b,c,t):
                if a+b+c !=t: fail(f'IND-022/{r["periodo"]}/{r["uf"]}: partição não fecha')
                else: ok('particao_discrepancias')
                p=num(r.get('percentual_discrepancia_confirmada_pop_evaluator'))
                if p is not None and t and not approx(p,100*a/t,0.015): fail('IND-022: percentual divergente')
        reconcile_geo(data,idn,('n_pop_evaluator','n_discrepancia_confirmada','n_sem_discrepancia_confirmada','n_indeterminada'))
    elif idn in (24,25):
        suffix='av3' if idn==24 else 'av4'
        for r in data:
            a,b,t=[num(r.get(k)) for k in ('n_com_'+suffix,'n_sem_'+suffix,'n_pop_all')]
            if None not in (a,b,t):
                if a+b!=t: fail(f'IND-{idn:03}/{r["periodo"]}/{r["uf"]}: com + sem ≠ POP_ALL')
                else: ok('particao_revisores')
                pct=num(r.get('percentual_com_'+suffix))
                if pct is not None and t and not approx(pct,100*a/t,0.015): fail(f'IND-{idn:03}: percentual incoerente')
        reconcile_geo(data,idn,('n_pop_all','n_com_'+suffix,'n_sem_'+suffix))
    elif idn==29:
        for r in data:
            n=num(r.get('n_amostra_ml_evaluator'))
            s=num(r.get('n_sinalizados_amostra'))
            p=num(r.get('percentual_sinalizados_amostra'))
            if n is not None and s is not None:
                if s>n: fail(f'IND-029/{r["periodo"]}/{r["uf"]}: sinalizados excedem amostra')
                elif p is not None and n and not approx(p,100*s/n,0.02): fail('IND-029: percentual sinalizado incoerente')
                else: ok('amostra_atipicos')
        # Não se somam as amostras por UF para igualar BR: modelos amostrais distintos.

def check_033(rows):
    for (yr,uf),rr in groups(rows,('ano','uf')).items():
        cc=[r.get('competencia') for r in rr]
        if len(cc)!=5 or set(cc)!=set('C1 C2 C3 C4 C5'.split()):
            fail(f'IND-033/{yr}/{uf}: faltam competências')
            continue
        ns={r.get('n_near') for r in rr}; ds={r.get('total_pontos_perdidos') for r in rr}
        if len(ns)!=1 or len(ds)!=1:
            fail(f'IND-033/{yr}/{uf}: denominadores diferentes entre competências')
            continue
        n=count(next(iter(ns)),f'IND-033/{yr}/{uf}/n_near')
        total=num(next(iter(ds)))
        if total is None or total<0:
            fail(f'IND-033/{yr}/{uf}: perda total inválida');continue
        sums=[num(r.get('soma_pontos_perdidos')) for r in rr]
        if None in sums:
            fail(f'IND-033/{yr}/{uf}: perdas ausentes');continue
        if not approx(sum(sums),total,0.025): fail(f'IND-033/{yr}/{uf}: soma das cinco perdas != total')
        else:ok('perdas_somam_total')
        if total>0:
            for r in rr:
                if not approx(r.get('participacao_perda_total'),float(r['soma_pontos_perdidos'])/total,0.00002):
                    fail(f'IND-033/{yr}/{uf}/{r["competencia"]}: fração de perda divergente')
                check_fraction(r,'participacao_perda_total','percentual_participacao',f'IND-033/{yr}/{uf}',0.02)
                if n and not approx(r.get('media_perda'),num(r['soma_pontos_perdidos'])/n,0.015):
                    fail(f'IND-033/{yr}/{uf}/{r["competencia"]}: média divergente')
        if any(str(r.get('suprimido','')).strip().lower()=='true' for r in rr):
            warn(f'IND-033/{yr}/{uf}: linha ainda marcada como suprimida')
    for yr,rr in groups(rows,('ano',)).items():
        br={r['competencia']:r for r in rr if r['uf']=='BR'}
        for comp in ('C1','C2','C3','C4','C5'):
            u=[r for r in rr if r['competencia']==comp and r['uf']!='BR']
            if len(u)!=27 or comp not in br: fail(f'IND-033/{yr}/{comp}: UFs incompletas');continue
            v=sum(num(r['soma_pontos_perdidos']) or 0 for r in u)
            if not approx(v,br[comp]['soma_pontos_perdidos'],0.025):
                fail(f'IND-033/{yr}/{comp}: perdas UF não fecham com BR')
            else:ok('perdas_ufs_fecham')

def check_053(rows):
    combos=groups(rows,('modelo','dimensao'))
    for (model,dim),rr in combos.items():
        nvals={r.get('n_amostra') for r in rr}
        if len(nvals)!=1:fail(f'IND-053/{model}/{dim}: tamanho de amostra instável')
        for r in rr:
            if r.get('tipo_linha')=='variavel':
                v=num(r.get('contribuicao_pct'))
                if v is None or v<0 or v>100.001:fail(f'IND-053/{model}: contribuição inválida')
            if r.get('tipo_linha')=='categoria':
                n=num(r.get('frequencia_categoria'))
                if n is not None and n<0: fail(f'IND-053/{model}: frequência negativa')
        ok('linhas_mca')

def check_054(rows):
    for model,rr in groups(rows,('modelo',)).items():
        models= [x for x in rr if x.get('tipo_linha')=='selecao_k']
        ks={x.get('k_selecionado') for x in rr if x.get('k_selecionado')}
        if len(ks)>1:fail(f'IND-054/{model[0]}: k selecionado inconsistente')
        if not models:warn(f'IND-054/{model[0]}: métricas seleção de k não presentes no CSV')
        centroids= [x for x in rr if x.get('tipo_linha')=='centroide']
        clusters={x.get('cluster') for x in centroids if x.get('cluster')}
        if clusters:
            selected=next(iter(ks),None)
            if selected and len(clusters)!=int(float(selected)):
                fail(f'IND-054/{model[0]}: k selecionado difere do nº de clusters')
            amounts={x['cluster']:num(x.get('n_cluster')) for x in centroids}
            ns={x.get('n_amostra') for x in centroids}
            if len(ns)==1 and all(x is not None for x in amounts.values()):
                n=num(next(iter(ns)))
                if n is not None and not approx(sum(amounts.values()),n,0.01):
                    fail(f'IND-054/{model[0]}: clusters não somam amostra')
                else:ok('clusters_somam_amostra')
        ok('modelos_cluster')

def get_block(obj,sections):
    try:
        p=obj['pages']
        for x in sections:p=p[x]
        return p
    except (KeyError,TypeError):return None

def main():
    print('AUDITORIA PÓS-LOTE 2 — SOMENTE LEITURA (arquivos atuais; sem microdados)')
    print('Raiz:',ROOT)
    csvs,js,paths={}, {}, {}
    for idn in IDS:
        c=list((ROOT/'outputs'/'indicadores').glob(f'IND_{idn:03}_*.csv'))
        j=list((ROOT/'outputs'/'json').glob(f'IND_{idn:03}_*.json'))
        if len(c)!=1 or len(j)!=1:
            fail(f'IND-{idn:03}: era esperado 1 CSV e 1 JSON em outputs; encontrados {len(c)} CSV, {len(j)} JSON')
            continue
        try:
            h,r=load_csv(c[0]); obj=json.loads(j[0].read_text(encoding='utf-8-sig'))
            if not isinstance(obj,dict):raise ValueError('JSON não é objeto')
            csvs[idn]=r;js[idn]=obj;paths[idn]=(c[0],j[0]);
            print(f'IND-{idn:03}: CSV {len(r)} linhas / {len(h)} colunas; JSON válido')
            ok('arquivos_csv_json')
        except (OSError,ValueError,UnicodeError,csv.Error) as e:fail(f'IND-{idn:03}: CSV/JSON inválidos: {e}')
    for idn in IDS:
        rows=csvs.get(idn)
        if not rows:continue
        try:
            if idn in (21,22,24,25,26,29):
                periods={r.get('periodo') for r in rows}
                if not PERIODOS.issubset(periods):fail(f'IND-{idn:03}: anos incompletos: {sorted(PERIODOS-periods)}')
                else:ok('anos_presentes')
                geography(rows,idn)
                check_evaluator(rows,idn)
            elif idn==33:
                geography(rows,idn)
                check_033(rows)
                if {r.get('ano') for r in rows}!=PERIODOS:fail('IND-033: faltam anos')
            elif idn==53:
                if not PERIODOS.issubset({r.get('ano') for r in rows}):warn('IND-053: falta ano no CSV; verificar disponibilidade real das fontes')
                check_053(rows)
            elif idn==54:
                if not PERIODOS.issubset({r.get('ano') for r in rows}):warn('IND-054: falta ano no CSV; verificar disponibilidade real das fontes')
                check_054(rows)
        except (KeyError,TypeError,ValueError,ZeroDivisionError) as e:
            fail(f'IND-{idn:03}: exceção durante auditoria: {e}')
    # Validação cruzada: mesmos avaliadores e denominadores nos IND-021/022/026.
    if all(i in csvs for i in (21,22,26)):
        aa={(r['periodo'],r['uf'],r['competencia']):r for r in csvs[21]}
        bb={(r['periodo'],r['uf']):r for r in csvs[22]}
        cc={(r['periodo'],r['uf'],r['competencia']):r for r in csvs[26]}
        for k,a in aa.items():
            b=bb.get(k[:2]); c=cc.get(k)
            if b is None or c is None:
                fail(f'IND-021/022/026/{k}: chave não encontrada para reconciliação')
                continue
            fields=(('n_pop_evaluator','n_pop_evaluator','n_pop_evaluator'),
                    ('n_pares_validos','n_pop_evaluator','n_pares_completos'))
            for fa,fb,fc in fields:
                va,vb,vc=num(a.get(fa)),num(b.get(fb)),num(c.get(fc))
                if None not in (va,vb,vc):
                    if va!=vb or va!=vc:
                        fail(f'IND-021/022/026/{k}: {fa}/{fb}/{fc} divergem ({va}/{vb}/{vc})')
                    else:ok('avaliadores_cruzados')
    print('Verificando presença dos módulos nos dashboards 2019–2025 ...')
    count_dashboard=Counter()
    for year in range(2019,2026):
        d=ROOT/'outputs'/'json'/f'dashboard_enem_{year}.json'
        if not d.is_file():fail(f'Dashboard ausente: {d.name}');continue
        try:obj=json.loads(d.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError) as e:fail(f'Dashboard {year} inválido: {e}');continue
        for idn in IDS:
            if idn not in js:continue
            block=get_block(obj,BLOCKS[idn])
            if block is None:
                # Se o indicador não suporta esse ano, documentar sem inventar disponibilidade.
                warn(f'Dashboard {year}: pages.{".".join(BLOCKS[idn])} do IND-{idn:03} ausente')
            else:
                count_dashboard[idn]+=1;ok('integracao_dashboard')
    print('Dashboards presentes:', ' '.join(f'{x:03}={count_dashboard[x]}/7' for x in IDS if x in js))
    # O backup pré-lote dá uma linha de base real, sem reprocessar nada.
    bdir=ROOT/'backups_lote2'
    backup=bdir/'saidas_antes_lote2_20261030_095805.zip'
    if not backup.is_file():
        choices=sorted(bdir.glob('saidas_antes_lote2_*.zip')) if bdir.is_dir() else []
        backup=choices[0] if choices else None
    if backup and backup.is_file():
        try:
            with zipfile.ZipFile(backup) as z:
                archived=z.namelist()
                for idn in IDS:
                    if idn not in paths:continue
                    p=paths[idn][0]
                    relative=p.relative_to(ROOT).as_posix()
                    match=next((name for name in archived if name.replace('\\','/').endswith(relative)),None)
                    if match is None:
                        warn(f'Backup {backup.name}: CSV IND-{idn:03} ausente');continue
                    old=z.read(match);new=p.read_bytes()
                    if old==new:
                        print(f'Comparação IND-{idn:03}: CSV idêntico ao backup (sem alteração de conteúdo)')
                    else:
                        oldrows=list(csv.DictReader(io.StringIO(old.decode('utf-8-sig')),delimiter=';'))
                        fresh=csvs[idn]
                        flags=('suprimido','sinalizacao_suprimida')
                        def nflags(rs):return sum(str(x.get(k,'')).lower()=='true' for x in rs for k in flags)
                        print(f'Comparação IND-{idn:03}: alterado; linhas {len(oldrows)} → {len(fresh)}, flags de supressão {nflags(oldrows)} → {nflags(fresh)}')
                    ok('comparacoes_backup')
            print('Backup original encontrado:',backup.name)
        except (OSError,zipfile.BadZipFile,ValueError,UnicodeDecodeError) as e:
            warn(f'Não foi possível comparar backup: {e}')
    else:
        warn('Backup pré-Lote 2 não localizado; comparação anterior/posterior não realizada')
    # Log de execução comprova finalizações, independentemente do conteúdo das saídas.
    logdir=ROOT/'logs_lote2'
    for idn in IDS:
        matches=sorted(logdir.glob(f'IND_{idn:03}_*.log')) if logdir.is_dir() else []
        if matches:
            last=matches[-1]
            try:
                txt=last.read_text(encoding='utf-8-sig',errors='replace')
                if 'Traceback (most recent call last)' in txt:
                    warn(f'IND-{idn:03}: último log contém traceback: {last.name}')
                else:ok('log_sem_traceback')
            except OSError as e:warn(f'Log {last.name}: {e}')
        else:warn(f'IND-{idn:03}: log não localizado')
    summary={'versao':'1.1','gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'tipo':'auditoria_arquivos_sem_recálculo_microdados',
        'indicadores_presentes':sorted(csvs),'linhas_csv':{str(x):len(v) for x,v in csvs.items()},
        'checagens':dict(checagens),'falhas':falhas,'alertas':alertas,
        'integracao_dashboard':{str(x):int(v) for x,v in count_dashboard.items()},
        'backup_comparado':backup.name if backup and backup.is_file() else None,
        'parecer':'FALHAS_DETECTADAS' if falhas else 'SEM_FALHAS_NAS_CHECAGENS_EXECUTADAS',
        'limites':['Auditoria sobre CSV/JSON já produzidos, não recálculo independente dos microdados.',
                  'Não demonstra por si só validade estatística, comparabilidade de clusters, privacidade ou aprovação acadêmica.']}
    out=ROOT/'auditorias_lote2'
    try:
        out.mkdir(exist_ok=True)
        loc=out/'auditoria_pos_lote2.json'
        loc.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('RELATÓRIO:',loc)
    except OSError as e:warn(f'Relatório não salvo: {e}')
    print('FIM: indicadores presentes=',len(csvs),'/9; checagens=',sum(checagens.values()),
          '; falhas=',len(falhas),'; alertas=',len(alertas))
    print('PARECER:',summary['parecer'],'— revisão metodológica e de privacidade ainda pendentes')
    return 1 if falhas else 0

if __name__=='__main__':
    raise SystemExit(main())
