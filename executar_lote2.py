#!/usr/bin/env python3
"""Executor serial de indicadores revisados Lote 2; verifica hashes e faz backup antes da execução."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time, zipfile
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MANIFESTO=ROOT/'lote2_corrigidos'/'manifesto_lote2_subconjunto.json'
SRC=ROOT/'src'/'indicadores'
LOG_DIR=ROOT/'logs_lote2'
ORDENACAO=('021','022','024','025','026','029','033','053','054')

def sha(b:bytes)->str:return hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest()

def main()->int:
    a=argparse.ArgumentParser(description='Lote 2: verificar ou executar códigos versionados')
    modos=a.add_mutually_exclusive_group(required=True)
    modos.add_argument('--verificar',action='store_true')
    modos.add_argument('--executar',action='store_true')
    a.add_argument('--apenas',help='Indicadores separados por vírgulas, por exemplo 21,22,24')
    args=a.parse_args()
    if not MANIFESTO.is_file():raise FileNotFoundError('Pacote lote2_corrigidos ausente')
    manifest=json.loads(MANIFESTO.read_text(encoding='utf-8'))['scripts']
    filtrados={f'{int(v):03d}' for v in args.apenas.split(',')} if args.apenas else set(ORDENACAO)
    desconhecidos=filtrados-set(ORDENACAO)
    if desconhecidos:raise ValueError('Indicadores fora deste pacote: '+','.join(sorted(desconhecidos)))
    fila=[v for v in ORDENACAO if v in filtrados]
    for k in fila:
        p=SRC/manifest[k]['file']
        if not p.is_file() or sha(p.read_bytes())!=manifest[k]['updated_sha256']:
            print('ERRO: hash não confere para IND-'+k+'; reinstale/verifique antes de executar',file=sys.stderr)
            return 2
        print('IND-'+k,manifest[k]['file'],'| HASH OK',flush=True)
    if args.verificar:
        print('VERIFICAÇÃO CONCLUÍDA; nenhum indicador executado.');return 0
    outputs=ROOT/'outputs'
    dirs=[outputs/'indicadores',outputs/'json']
    backup_dir=ROOT/'backups_lote2';backup_dir.mkdir(exist_ok=True)
    ts=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=backup_dir/f'saidas_antes_lote2_{ts}.zip'
    with zipfile.ZipFile(backup,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        n=0
        for folder in dirs:
            if not folder.exists():continue
            for p in folder.glob('*.csv' if folder.name=='indicadores' else '*.json'):
                if folder.name=='json' and not (p.name.startswith('dashboard_enem_') or p.name.startswith('IND_')):continue
                if folder.name=='indicadores' and not p.name.startswith('IND_'):continue
                z.write(p,p.relative_to(ROOT).as_posix());n+=1
    print('BACKUP:',backup,f'({n} arquivos)',flush=True)
    LOG_DIR.mkdir(exist_ok=True)
    for k in fila:
        m=manifest[k];p=SRC/m['file'];cmd=[sys.executable,'-u',str(p),*m['args']]
        log=LOG_DIR/f'IND_{k}_{ts}.log'
        print('INICIANDO IND-'+k,'LOG:',log.name,flush=True)
        t0=time.monotonic()
        with log.open('w',encoding='utf-8') as f:
            f.write('Comando: '+repr(cmd)+'\n');f.flush()
            r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        tempo=round(time.monotonic()-t0)
        print(f'IND-{k}: '+('OK' if r.returncode==0 else 'ERRO')+f' | {tempo}s | código {r.returncode}',flush=True)
        if r.returncode:
            print('Interrompido para análise. Verifique o log: '+str(log),file=sys.stderr)
            return r.returncode or 1
    print(f'FIM. Sucessos={len(fila)}, falhas=0. Resultados permanecem draft.')
    return 0
if __name__=='__main__':raise SystemExit(main())
