#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Executor conservador para reprocessamento ENEM (Windows/Linux).

NÃO corrige indicadores. Exige manifesto de scripts já corrigidos; faz backup,
execução sequencial, logs por indicador, retomada e parada de dependentes após erro.
Uso: python executar_indicadores_lote.py --verificar
     python -u executar_indicadores_lote.py --executar
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
INDDIR = ROOT / 'src' / 'indicadores'
MANIFEST = ROOT / 'manifesto_indicadores_corrigidos.json'
STATE = ROOT / 'logs_reprocessamento' / 'estado_execucao.json'

# Ordem: 001..054; o recorte 980 vem imediatamente depois do IND-034.
# São independentes do número de arquivos presentes. Os arquivos só são executados
# quando estão explicitamente aprovados no manifesto, com SHA-256 correspondente.
DEPEND = {
    2: [1], 3: [1, 2], 4: [1, 2, 3], 5: [1, 2, 3, 4],
    6: [1, 5], 7: [1, 6], 8: [6, 7], 9: [8], 10: [9],
    11: [9, 10], 12: [11], 13: [12], 14: [13],
    15: [14], 16: [14, 15], 17: [14, 15], 18: [17], 19: [17, 18],
    20: [19], 21: [20], 22: [20, 21], 23: [22],
    24: [7, 20], 25: [7, 20], 26: [21], 27: [20],
    28: [21], 29: [28], 30: [27], 31: [30],
    32: [31], 33: [31], 34: [31], 35: [31, 32],
    36: [31, 35], 37: [31], 38: [31], 39: [30],
    40: [1], 41: [40], 42: [41], 43: [41],
    44: [9, 43], 45: [43], 46: [45], 47: [45],
    48: [45], 49: [45], 50: [45], 51: [45],
    52: [2], 53: [40], 54: [53],
    '34_980': [34],
}

def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')

def load_json(path, default):
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8-sig'))
    return default

def save_json(path, obj):
    path.parent.mkdir(exist_ok=True, parents=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def get_candidates():
    if not INDDIR.is_dir():
        raise SystemExit(f'Pasta de scripts não encontrada: {INDDIR}. Coloque este executor na raiz do projeto.')
    scriptmap = {}
    for i in range(1, 55):
        possible = sorted(INDDIR.glob(f'IND_{i:03}_*.py'))
        possible = [p for p in possible if not p.name.endswith('_CORRIGIDO.py') and p.name != 'IND_034_recorte_980_final.py']
        if len(possible) == 0:
            alt = sorted(INDDIR.glob(f'IND_{i:03}_*_CORRIGIDO.py'))
            possible = alt if len(alt) == 1 else []
        if len(possible) == 1:
            scriptmap[str(i)] = possible[0]
        elif len(possible) > 1:
            raise SystemExit(f'Versões ambíguas para IND-{i:03}: {[p.name for p in possible]}')
    p980 = INDDIR / 'IND_034_recorte_980_final.py'
    if p980.is_file(): scriptmap['34_980'] = p980
    return scriptmap

def parse_only(spec, all_keys):
    if not spec: return list(all_keys)
    wanted = []
    for part in spec.split(','):
        p = part.strip().lower().replace('ind-', '').replace('ind_', '')
        if not p: continue
        if p in ('34/980', '034/980', '034_980', '34_980'):
            key='34_980'
        else:
            try: key=str(int(p))
            except ValueError: raise SystemExit(f'ID inválido em --apenas: {part}')
        if key not in all_keys:
            raise SystemExit(f'IND-{key} não encontrado em src/indicadores; instalação incompleta.')
        if key not in wanted: wanted.append(key)
    return wanted

def order(keys):
    return sorted(keys, key=lambda k: (int(str(k).split('_')[0]), 1 if k == '34_980' else 0))

def create_backup():
    stamp=dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = ROOT / 'backups_reprocessamento'
    folder.mkdir(parents=True, exist_ok=True)
    target=folder / f'saidas_antes_{stamp}.zip'
    sources = []
    for directory in (ROOT/'outputs'/'indicadores', ROOT/'outputs'/'json'):
        if directory.exists():
            sources.extend(sorted(directory.glob('IND_*.csv')))
            sources.extend(sorted(directory.glob('IND_*.json')))
            sources.extend(sorted(directory.glob('dashboard_enem_*.json')))
    if not sources:
        raise RuntimeError('Nenhum CSV/JSON anterior encontrado; backup não criado. Verifique a raiz do projeto.')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for p in sources:
            z.write(p, arcname=p.relative_to(ROOT))
    print(f'BACKUP: {target} ({len(sources)} arquivos)', flush=True)
    return str(target)

def main():
    parser = argparse.ArgumentParser(description='Executor noturno controlado do projeto ENEM.')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--verificar', action='store_true', help='Simula a fila e verifica hashes, sem executar nem alterar nada.')
    modes.add_argument('--executar', action='store_true', help='Executa scripts homologados no manifesto.')
    parser.add_argument('--apenas', help='IDs em sequência por vírgula: 16,20,23,34,34/980,45,46')
    parser.add_argument('--retomar', action='store_true', help='Ignora sucessos anteriores com o mesmo hash e a mesma linha de comando.')
    parser.add_argument('--parar-no-erro', action='store_true', help='Interrompe o lote no primeiro erro.')
    parser.add_argument('--sem-backup', action='store_true', help='Pula backup apenas se já existir backup externo confiável.')
    args = parser.parse_args()
    scripts=get_candidates()
    entries=load_json(MANIFEST, {})
    if not isinstance(entries, dict) or not isinstance(entries.get('scripts'), dict):
        raise SystemExit('Manifesto ausente/inválido. Não executar versões não verificadas.')
    wanted=order(parse_only(args.apenas, scripts.keys()))
    if not wanted: raise SystemExit('Nenhum script selecionado.')
    valid={}; invalid={}
    for k in wanted:
        p=scripts[k]
        rec=entries['scripts'].get(k)
        if not isinstance(rec,dict) or not isinstance(rec.get('sha256'),str):
            invalid[k]='SEM VERSÃO CORRIGIDA APROVADA NO MANIFESTO'
        elif (expected := rec['sha256'].lower()) != digest(p).lower():
            invalid[k]='HASH ALTERADO: arquivo difere da versão conferida'
        else:
            valid[k]=p
    print(f'Projeto: {ROOT}\nPython: {sys.executable}\nFila: {len(wanted)} indicadores', flush=True)
    for k in wanted:
        label = f'IND-{k.replace("_", "/").zfill(3)}' if k != '34_980' else 'IND-034/980'
        print(f'  {label:<13} {scripts[k].name} | {"OK" if k in valid else invalid[k]}', flush=True)
    if args.verificar:
        print('VERIFICAÇÃO CONCLUÍDA. Nenhum indicador executado.', flush=True)
        return 0 if not invalid else 2
    if invalid:
        print('ERRO: existem scripts sem hash aprovado. Não iniciarei execuções parciais.', flush=True)
        return 2
    logdir=ROOT/'logs_reprocessamento'
    logdir.mkdir(exist_ok=True)
    status=load_json(STATE, {'historico':{}, 'ultima_execucao':{}})
    if not args.sem_backup:
        backup=create_backup()
    else:
        backup='backup externo informado pelo usuário'
    timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    results=[]; bad={}
    with (logdir/f'resumo_{timestamp}.csv').open('w',newline='',encoding='utf-8-sig') as csvfile:
        writer=csv.DictWriter(csvfile,fieldnames=['id','script','inicio','fim','segundos','status','codigo_saida','log'])
        writer.writeheader()
        for key in wanted:
            p=valid[key]
            rec=entries['scripts'][key]
            arglist=rec.get('args', [])
            if not isinstance(arglist,list) or not all(isinstance(x,str) for x in arglist):
                raise RuntimeError(f'Argumentos inválidos para IND-{key}')
            deps=DEPEND.get(key, [])
            # Dependências excluídas da fila são consideradas previamente existentes;
            # se houver falha na execução atual, dependentes serão ignorados.
            blocked=[str(d) for d in deps if str(d) in bad]
            cmd=[sys.executable,'-u',str(p),*arglist]
            signature=hashlib.sha256(json.dumps([digest(p),cmd[3:]],sort_keys=True).encode()).hexdigest()
            success_old=status['historico'].get(key,{})
            if blocked:
                st='BLOQUEADO_DEPENDENCIA'; code=''; duration=0; logfile=''
                bad[key]=st
            elif args.retomar and success_old.get('signature')==signature and success_old.get('status')=='OK':
                st='JA_EXECUTADO';code='';duration=0;logfile=''
            else:
                begin=now();started=time.monotonic()
                logfile=logdir/f'IND_{key.replace("_", "_")}_{timestamp}.log'
                print(f'[{begin}] INICIANDO {key}: {p.name} (log: {logfile.name})',flush=True)
                with logfile.open('w', encoding='utf-8') as log:
                    log.write(f'Start={begin}\nCommand={cmd!r}\nBackup={backup}\n\n')
                    log.flush()
                    proc=subprocess.Popen(cmd,cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
                    try: code=proc.wait()
                    except KeyboardInterrupt:
                        proc.terminate();code=proc.wait();raise
                duration=int(time.monotonic()-started)
                st='OK' if code==0 else 'ERRO'
                print(f'[{now()}] {key}: {st} | {duration}s | saída {code}',flush=True)
                status['historico'][key]={'status':st,'signature':signature,'arquivo':p.name,'concluido':now()}
                save_json(STATE,status)
                if code!=0:bad[key]=st
            record={'id':key,'script':p.name,'inicio':locals().get('begin',''), 'fim':now(),
                    'segundos':duration,'status':st,'codigo_saida':code,
                    'log':str(logfile) if logfile else ''}
            writer.writerow(record);csvfile.flush()
            results.append(record)
            if bad and args.parar_no_erro:break
    status['ultima_execucao']={'quando':now(),'backup':backup,'itens':results,
                                'falhas':list(bad)}
    save_json(STATE,status)
    print(f'FIM. Sucessos={sum(x["status"] in ("OK","JA_EXECUTADO") for x in results)} '
          f'Falhas/bloqueios={sum(x["status"] in ("ERRO","BLOQUEADO_DEPENDENCIA") for x in results)} '
          f'Consulte {logdir}',flush=True)
    return 1 if bad else 0

if __name__=='__main__':
    sys.exit(main())
