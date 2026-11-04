#!/usr/bin/env python3
"""Instala apenas após conclusão do Lote 2. --verificar é somente leitura."""
from __future__ import annotations
import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'pacote_ind055_072/src/indicadores'

def digest(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def main():
    p=argparse.ArgumentParser()
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--verificar',action='store_true')
    m.add_argument('--instalar',action='store_true')
    p.add_argument('--confirmar-lote2-concluido',action='store_true')
    p.add_argument('--raiz',type=Path,default=ROOT)
    args=p.parse_args();root=args.raiz.resolve()
    current=root/'src/indicadores'
    if not current.is_dir():p.error('Repositório inválido')
    if args.instalar and not args.confirmar_lote2_concluido:
        p.error('Não instalar enquanto o Lote 2 estiver em execução')
    files=sorted(SRC.glob('IND_0[5-7][0-9]_*.py'))+[SRC/'_ind055_072_core.py']
    files=[f for f in files if f.name.startswith(('IND_055','IND_056','IND_057','IND_058','IND_059','IND_060','IND_061','IND_062','IND_063','IND_064','IND_065','IND_066','IND_067','IND_068','IND_069','IND_070','IND_071','IND_072','_ind055'))]
    if len(files)!=19:p.error('Esperados 18 scripts + núcleo; encontrados '+str(len(files)))
    existing=[]
    for f in files:
        dest=current/f.name
        status='NOVO' if not dest.exists() else 'JÁ INSTALADO' if digest(f)==digest(dest) else 'DIFERENTE'
        print(f.name,status)
        if status=='DIFERENTE':existing.append(dest)
    if existing:
        print('BLOQUEADO: arquivos homônimos diferentes requerem revisão manual:',[x.name for x in existing]);return 2
    if args.verificar:
        print('VERIFICAÇÃO CONCLUÍDA. Nenhum arquivo alterado.');return 0
    if any((current/f.name).exists() for f in files):
        print('Alguns arquivos já instalados serão preservados. Checado hash.')
    for f in files:
        d=current/f.name
        if not d.exists():shutil.copyfile(f,d)
    print('INSTALAÇÃO CONCLUÍDA: scripts apenas; nenhum indicador executado.')
    return 0

if __name__=='__main__':raise SystemExit(main())
