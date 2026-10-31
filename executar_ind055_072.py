#!/usr/bin/env python3
"""Executor unificado e sequencial, sem paralelismo. Não executa sem autorização explícita."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'src/indicadores'
ORDER=(69,70,64,65,66,67,68,55,56,57,58,59,60,61,62,63,71,72)


def paths():
    return {i:next(SRC.glob(f'IND_{i:03d}_*.py')) for i in ORDER}


def backup(root,stamp):
    dest=root/'backups_lote3';dest.mkdir(exist_ok=True)
    out=dest/f'saidas_antes_IND055_072_{stamp}.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        n=0
        for folder,glob in [('outputs/json','*.json'),('outputs/indicadores','*.csv')]:
            for p in (root/folder).glob(glob):
                if p.name.startswith('IND_') or p.name.startswith('dashboard_enem_'):
                    z.write(p,p.relative_to(root));n+=1
    print('BACKUP:',out,'arquivos=',n,flush=True)


def main():
    p=argparse.ArgumentParser(description='IND-055 a IND-072 | execução SEM paralelismo')
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--verificar',action='store_true')
    m.add_argument('--executar',action='store_true')
    p.add_argument('--confirmar-lote2-concluido',action='store_true',help='Obrigatório para --executar')
    p.add_argument('--permitir-pendencias',action='store_true',help='Pula indicadores sem dependência disponível')
    p.add_argument('--apenas',help='Ex.: 64,65,66')
    p.add_argument('--sobrescrever',action='store_true')
    p.add_argument('--raiz',type=Path,default=ROOT)
    args=p.parse_args()
    root=args.raiz.resolve()
    if args.executar and not args.confirmar_lote2_concluido:
        p.error('A execução exige --confirmar-lote2-concluido; nunca rode em paralelo ao Lote 2')
    fila=list(ORDER)
    if args.apenas:
        selected={int(v) for v in args.apenas.split(',')}
        if not selected.issubset(ORDER):p.error('IDs fora do pacote')
        fila=[i for i in ORDER if i in selected]
    names=paths()
    print('FILA:', ','.join(f'{x:03d}' for x in fila),flush=True)
    checks={};blocking=[]
    for i in fila:
        cmd=[sys.executable,str(names[i]),'--verificar','--raiz',str(root)]
        r=subprocess.run(cmd,cwd=root,text=True,capture_output=True)
        try:res=json.loads(r.stdout.strip().splitlines()[-1]);status=res['status']
        except Exception:status='erro_verificacao';res={'detalhe':r.stderr or r.stdout}
        checks[i]=status
        if r.returncode or 'bloqueado' in status:blocking.append(i)
        print(f'IND-{i:03d}: {status}',flush=True)
    if args.verificar:
        print(f'PRÉ-CHECAGEM: {len(fila)-len(blocking)} prontos, {len(blocking)} pendentes. Nenhum indicador executado.')
        return 0
    if blocking and not args.permitir_pendencias:
        print('IMPEDIDO: pendências',blocking,'— use --permitir-pendencias para pular dependentes explicitamente')
        return 2
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup(root,stamp)
    logs=root/'logs_lote3';logs.mkdir(exist_ok=True)
    sucessos=[];pulados=[]
    for i in fila:
        if i in blocking:
            pulados.append(i);continue
        cmd=[sys.executable,'-u',str(names[i]),'--executar','--raiz',str(root)]
        if args.sobrescrever:cmd.append('--sobrescrever')
        fname=logs/f'IND_{i:03d}_{stamp}.log'
        print(f'INICIANDO IND-{i:03d}: {fname.name}',flush=True);t=time.monotonic()
        with fname.open('w',encoding='utf-8') as f:
            f.write('Comando='+str(cmd)+'\n');f.flush()
            r=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
        print(f'IND-{i:03d}: {"OK" if r.returncode==0 else "ERRO"} ({int(time.monotonic()-t)}s)',flush=True)
        if r.returncode:
            print('Interrompido. Inspecione:',fname,flush=True)
            return r.returncode
        sucessos.append(i)
    print('FIM. Sucessos=',len(sucessos),'pulados=',pulados,'| revisão acadêmica pendente')
    return 0

if __name__=='__main__':raise SystemExit(main())
