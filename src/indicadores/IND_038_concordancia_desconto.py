#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-038 — Concordância no desconto | Projeto Integrador IV — UNIVESP.

Definição do catálogo: ``AV1 e AV2 descontam a mesma competência?``
População POP_NEAR_EVALUATOR = redações com situação final válida (1), nota
final no intervalo [900, 980], e notas e situações válidas nos DOIS avaliadores
(AV1/AV2) para todas as cinco competências.

Para cada C1..C5: desconto_i(AVj) := NU_NOTA_COMPi_AVj < 200.
Tabela AV1 x AV2 em quatro células (não/não, não/sim, sim/não, sim/sim).
Kappa de Cohen com pesos quadráticos, nas duas categorias {não, sim}.
IMPORTANTE: com apenas duas categorias, kappa ponderado quadrático é
algebricamente igual ao kappa de Cohen simples.

Fontes: 2019–2024: COMPETENCIAS_REDACAO_<ano>.csv mais geo do mesmo ano:
  MICRODADOS_ENEM_<ano>.csv (2019–2023), PARTICIPANTES_2024.csv (2024),
  vinculadas por NU_INSCRICAO (apenas arquivos DA MESMA EDIÇÃO).
  2025: RESULTADOS_2025.csv tem UF, competências finais e AV1/AV2 juntos;
  NÃO vincular ao PARTICIPANTES_2025 por NU_SEQUENCIAL.

Saídas:
  outputs/json/IND_038_concordancia_desconto.json
  outputs/indicadores/IND_038_concordancia_desconto.csv
  outputs/json/dashboard_enem_<ano>.json
       pages.high_performance.reviewer_agreement (array de 28*5 células)
       quality.ind038_validation (controle técnico)

O gerador aceita cópias byte a byte idênticas de CSV e pede escolha explícita
para cópias divergentes. Não cria .bak e não exporta NU_INSCRICAO.
O status de publicação permanece draft (revisões acadêmica/contextual pendentes).

Exemplos:
  python src/indicadores/IND_038_concordancia_desconto.py --autoteste
  python src/indicadores/IND_038_concordancia_desconto.py --anos 2024 --sobrescrever
  python src/indicadores/IND_038_concordancia_desconto.py --sobrescrever
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import json
import math
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MG','MS','MT',
       'PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
FINAIS = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
AV1 = tuple(f'NU_NOTA_COMP{i}_AV1' for i in range(1, 6))
AV2 = tuple(f'NU_NOTA_COMP{i}_AV2' for i in range(1, 6))
CAMPOS_AVALIADORES = [
    'TP_STATUS_REDACAO','NU_NOTA_REDACAO',*FINAIS,
    'TP_STATUS_REDACAO_AV1','TP_STATUS_REDACAO_AV2',
    'NU_NOTA_AV1','NU_NOTA_AV2',*AV1,*AV2,
]
CAMPOS_CSV = ('ano','uf','competencia','n_pop_near','n_near_evaluator',
              'av1_nao_av2_nao','av1_nao_av2_sim','av1_sim_av2_nao',
              'av1_sim_av2_sim','concordancia_percentual','kappa_ponderado',
              'kappa_status','suprimido','motivo_supressao')
MIN_CELULA = 30
# Controle independente já auditado para POP_NEAR. --sem-controle-populacao
# é reservado ao teste sintético. 2025 exige a fonte real quando disponível.
POP_NEAR_REFERENCIA = {2019:172548, 2020:183343, 2021:163747,
                       2022:197083, 2023:288602, 2024:291111, 2025:173533}


def log(mensagem: str) -> None:
    print(mensagem, flush=True)


def raiz_projeto() -> Path:
    arq = Path(__file__).resolve()
    if arq.parent.name.lower() == 'indicadores' and arq.parent.parent.name.lower() == 'src':
        return arq.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                    fontes_explicitas: dict[str, Path] | None = None) -> dict[str, Path]:
    ignorar = {'.venv','venv','.git','outputs','__pycache__','node_modules',
               '.pytest_cache','.mypy_cache'}
    fontes_explicitas = {k.upper(): v for k,v in (fontes_explicitas or {}).items()}
    fontes: dict[str,Path] = {}
    for nome, indicado in fontes_explicitas.items():
        if nome not in nomes:
            raise ValueError(f'Fonte explícita não usada neste processamento: {nome}')
        caminho = Path(indicado).expanduser()
        if not caminho.is_absolute():
            caminho = base / caminho
        caminho = caminho.resolve()
        if not caminho.is_file():
            raise FileNotFoundError(f'Fonte explícita inexistente: {caminho}')
        fontes[nome] = caminho
        log(f'  Fonte explícita {nome}: {caminho}')
    for diretorio, pastas, arquivos in os.walk(base):
        pastas[:] = sorted(p for p in pastas if p.lower() not in ignorar)
        for arquivo in sorted(arquivos):
            nome = arquivo.upper()
            if nome not in nomes or nome in fontes_explicitas:
                continue
            caminho = Path(diretorio) / arquivo
            if nome not in fontes:
                fontes[nome] = caminho
            elif fontes[nome].resolve() != caminho.resolve():
                if filecmp.cmp(fontes[nome], caminho, shallow=False):
                    log(f'  CSV idêntico encontrado para {nome}; usando {fontes[nome]}.')
                else:
                    opcao = ('--competencias-2024' if nome=='COMPETENCIAS_REDACAO_2024.CSV'
                             else '--participantes-2024' if nome=='PARTICIPANTES_2024.CSV'
                             else '--fonte-avaliadores' if nome.startswith('COMPETENCIAS_REDACAO_')
                             else '--fonte-geografia')
                    raise ValueError(f'Arquivos com o mesmo nome e conteúdo diferente: {nome}: '
                                     f'{fontes[nome]} / {caminho}. Informe {opcao} <caminho>.')
    return fontes


def iterar_csv(caminho: Path, colunas: list[str], bloco: int):
    with caminho.open('rb') as f:
        codificacao = 'utf-8-sig' if f.read(3)==b'\xef\xbb\xbf' else 'latin-1'
    cabecalho = pd.read_csv(caminho, sep=';', encoding=codificacao, nrows=0)
    faltando = sorted(set(colunas)-set(cabecalho.columns))
    if faltando:
        raise ValueError(f'{caminho.name}: variáveis obrigatórias ausentes: {faltando}')
    with pd.read_csv(caminho, sep=';', encoding=codificacao, dtype='string',
                     usecols=colunas, chunksize=bloco, na_filter=False,
                     keep_default_na=False, low_memory=False) as leitor:
        for parte in leitor:
            yield parte


def numeros(coluna: pd.Series) -> np.ndarray:
    return pd.to_numeric(coluna.astype('string').str.strip().str.replace(',', '.',regex=False),
                         errors='coerce').to_numpy(dtype=np.float64)


def selecionar_near(parte: pd.DataFrame) -> tuple[pd.DataFrame,int]:
    validas = parte['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')
    nota = numeros(parte['NU_NOTA_REDACAO'])
    fora = validas.to_numpy() & (~np.isfinite(nota) | (nota < 0) | (nota > 1000))
    if fora.any():
        raise ValueError('Redação de situação final 1 com nota final inválida (0..1000).')
    filtro = validas.to_numpy() & (nota >= 900) & (nota <= 980)
    near = parte.loc[filtro].copy()
    near['__nota_final'] = nota[filtro]
    return near, int(validas.sum())


def classificar_near(near: pd.DataFrame) -> tuple[np.ndarray,np.ndarray,np.ndarray,int]:
    """Retorna categoria 0 elegível / 1 status / 2 incompleta / 3 inconsistente.

    Mascara de bits para cada avaliador quando elegível, -1 em excluídos.
    A ocorrência de nota < 200 é determinada separadamente em AV1 e AV2.
    """
    n=len(near)
    if not n:
        return (np.empty(0,dtype=np.int8),np.empty(0,dtype=np.int16),
                np.empty(0,dtype=np.int16),0)
    final=np.column_stack([numeros(near[x]) for x in FINAIS])
    validas_final=np.isfinite(final).all(axis=1) & (final>=0).all(axis=1) & (final<=200).all(axis=1)
    incons_final=int(np.count_nonzero(
        ~validas_final | (np.abs(np.nansum(final,axis=1)-near['__nota_final'].to_numpy())>1e-6)))
    sts1=near['TP_STATUS_REDACAO_AV1'].astype('string').str.strip().eq('1').to_numpy()
    sts2=near['TP_STATUS_REDACAO_AV2'].astype('string').str.strip().eq('1').to_numpy()
    categoria=np.where(sts1 & sts2, 0, 1).astype(np.int8)
    a1=np.column_stack([numeros(near[x]) for x in AV1])
    a2=np.column_stack([numeros(near[x]) for x in AV2])
    totais=np.column_stack([numeros(near[x]) for x in ('NU_NOTA_AV1','NU_NOTA_AV2')])
    completo=(np.isfinite(a1).all(axis=1) & np.isfinite(a2).all(axis=1)
              & np.isfinite(totais).all(axis=1)
              & (a1>=0).all(axis=1) & (a1<=200).all(axis=1)
              & (a2>=0).all(axis=1) & (a2<=200).all(axis=1)
              & (totais>=0).all(axis=1) & (totais<=1000).all(axis=1))
    categoria=np.where((categoria==0) & ~completo,2,categoria)
    soma1=a1.sum(axis=1)
    soma2=a2.sum(axis=1)
    coerencia=(np.abs(soma1-totais[:,0])<=1e-6)&(np.abs(soma2-totais[:,1])<=1e-6)
    categoria=np.where((categoria==0)&~coerencia,3,categoria)
    mascara1=np.full(n,-1,dtype=np.int16)
    mascara2=np.full(n,-1,dtype=np.int16)
    valido=categoria==0
    pesos=np.array([1,2,4,8,16],dtype=np.int16)
    mascara1[valido]=((a1[valido]<200).astype(np.int16) @ pesos)
    mascara2[valido]=((a2[valido]<200).astype(np.int16) @ pesos)
    return categoria,mascara1,mascara2,incons_final


@dataclass
class Acumulador:
    n_near: int=0
    n_elegiveis: int=0
    excl_status: int=0
    excl_notas: int=0
    excl_inconsistencia: int=0
    incoerencias_finais: int=0
    matrizes: np.ndarray=field(default_factory=lambda:np.zeros((5,2,2),dtype=np.int64))

    def adicionar(self, classe: int, a: int, b: int, n: int, divergencias_finais: int=0) -> None:
        self.n_near+=n
        self.incoerencias_finais+=divergencias_finais
        if classe==1:
            self.excl_status+=n
        elif classe==2:
            self.excl_notas+=n
        elif classe==3:
            self.excl_inconsistencia+=n
        elif classe==0:
            self.n_elegiveis+=n
            for i in range(5):
                self.matrizes[i, (a>>i)&1, (b>>i)&1]+=n
        else:
            raise ValueError(f'Classe de elegibilidade inválida: {classe}')

    def somar(self, other: 'Acumulador') -> None:
        self.n_near+=other.n_near
        self.n_elegiveis+=other.n_elegiveis
        self.excl_status+=other.excl_status
        self.excl_notas+=other.excl_notas
        self.excl_inconsistencia+=other.excl_inconsistencia
        self.incoerencias_finais+=other.incoerencias_finais
        self.matrizes+=other.matrizes


def acumular_parte(aggs: dict[str,Acumulador], ufs: np.ndarray,
                   classes: np.ndarray,m1: np.ndarray,m2: np.ndarray,
                   incons_final: np.ndarray) -> None:
    if not(len(ufs)==len(classes)==len(m1)==len(m2)==len(incons_final)):
        raise ValueError('Vetores para acumular resultados com comprimentos diferentes.')
    for uf in np.unique(ufs):
        if uf not in UFS:
            raise ValueError(f'SG_UF_PROVA inválida entre redações POP_NEAR: {uf!r}')
        sel=ufs==uf
        combos=pd.DataFrame({'classe':classes[sel], 'm1':m1[sel],
                             'm2':m2[sel], 'inc':incons_final[sel]})
        # 'inc' é contagem por redação, nunca valor identificador.
        for (categoria,a,b), qtd in combos.groupby(['classe','m1','m2'],sort=False).size().items():
            subtotal=int(combos.loc[(combos['classe']==categoria)&(combos['m1']==a)&(combos['m2']==b),'inc'].sum())
            aggs[uf].adicionar(int(categoria),int(a),int(b),int(qtd),subtotal)


def ler_geografia_indexada(conexao: sqlite3.Connection, arquivo: Path,
                           ano: int, bloco: int) -> dict:
    """2019–23: indexar somente POP_NEAR; 2024: indexar participantes inteiros."""
    colunas = ['NU_INSCRICAO','SG_UF_PROVA']
    if ano <= 2023:
        colunas+=['TP_STATUS_REDACAO','NU_NOTA_REDACAO']
    n=0
    por_uf={uf:0 for uf in UFS}
    for parte in iterar_csv(arquivo,colunas,bloco):
        if ano <= 2023:
            parte,nval=selecionar_near(parte)
        if parte.empty:
            continue
        ids=parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
        ufs=parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
        if any(not i for i in ids) or any(uf not in UFS for uf in ufs):
            raise ValueError(f'{arquivo.name}: inscrição/UF inválida em universo vinculado.')
        try:
            conexao.executemany('INSERT INTO geografia VALUES (?,?)',zip(ids,ufs))
        except sqlite3.IntegrityError as exc:
            raise ValueError(f'{arquivo.name}: NU_INSCRICAO duplicada no universo vinculado.') from exc
        n+=len(ids)
        for uf, count in pd.Series(ufs).value_counts().items():
            por_uf[str(uf)]+=int(count)
        conexao.commit()
    return {'n_geografia_indexada':n,'n_near_geografico_por_uf':por_uf if ano<=2023 else None}


def ler_complemento(competencias: Path, geografia: Path, ano: int,
                    bloco: int) -> tuple[dict,int,dict]:
    acumulado={uf:Acumulador() for uf in UFS}
    with tempfile.TemporaryDirectory(prefix=f'enem_ind038_{ano}_') as temp:
        db=sqlite3.connect(str(Path(temp)/'local.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE geografia(id TEXT PRIMARY KEY,uf TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE near_ids(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(id TEXT NOT NULL,cat INTEGER NOT NULL, '
                       'm1 INTEGER NOT NULL,m2 INTEGER NOT NULL,inc INTEGER NOT NULL)')
            diag=ler_geografia_indexada(db,geografia,ano,bloco)
            log(f'  {ano}: {diag["n_geografia_indexada"]:,} inscrições geográficas indexadas.')
            n_validas=0
            qtd_vinculada=0
            for parte in iterar_csv(competencias,['NU_INSCRICAO',*CAMPOS_AVALIADORES],bloco):
                near,n_valid=selecionar_near(parte)
                n_validas+=n_valid
                if near.empty:
                    continue
                ids=near['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not id_ for id_ in ids):
                    raise ValueError(f'{competencias.name}: inscrição vazia em POP_NEAR.')
                classes,m1,m2,n_inc=classificar_near(near)
                # Marcar por linha, de modo que a verificação geográfica por UF também feche.
                notas_finais=np.column_stack([numeros(near[x]) for x in FINAIS])
                ftotal=near['__nota_final'].to_numpy()
                incoerente=(~np.isfinite(notas_finais).all(axis=1)
                            | (notas_finais<0).any(axis=1)
                            | (notas_finais>200).any(axis=1)
                            | (np.abs(np.nansum(notas_finais,axis=1)-ftotal)>1e-6))
                assert int(incoerente.sum())==n_inc
                try:
                    db.executemany('INSERT INTO near_ids VALUES (?)', ((id_,) for id_ in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f'{competencias.name}: inscrição duplicada em POP_NEAR.') from exc
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?,?,?,?)',
                               ((ident,int(cat),int(a),int(b),int(inc))
                                for ident,cat,a,b,inc in zip(ids,classes,m1,m2,incoerente)))
                vinculados=int(db.execute('SELECT COUNT(*) FROM lote l JOIN geografia g ON g.id=l.id').fetchone()[0])
                if vinculados!=len(ids):
                    raise ValueError(f'{ano}: {len(ids)-vinculados} redações POP_NEAR sem geo em '
                                     f'{geografia.name}; NÃO usar associação por posição de linha.')
                for uf,cat,a,b,n,div in db.execute('''
                    SELECT g.uf,l.cat,l.m1,l.m2,COUNT(*),SUM(l.inc)
                    FROM lote l JOIN geografia g ON g.id=l.id
                    GROUP BY g.uf,l.cat,l.m1,l.m2'''):
                    acumulado[uf].adicionar(int(cat),int(a),int(b),int(n),int(div))
                qtd_vinculada+=vinculados
                db.commit()
            diag.update({'metodo':'NU_INSCRICAO_ano_igual_SQLite',
                         'n_near_vinculada':qtd_vinculada,
                         'n_near_sem_geo':0})
            return acumulado,n_validas,diag
        finally:
            db.close()


def ler_resultados_2025(arquivo: Path, bloco: int) -> tuple[dict,int,dict]:
    acumulado={uf:Acumulador() for uf in UFS}
    validas=0
    for parte in iterar_csv(arquivo,['SG_UF_PROVA',*CAMPOS_AVALIADORES],bloco):
        near,n=selecionar_near(parte)
        validas+=n
        if near.empty:
            continue
        classes,m1,m2,n_inc=classificar_near(near)
        finais=np.column_stack([numeros(near[x]) for x in FINAIS])
        ft=near['__nota_final'].to_numpy()
        inc=(~np.isfinite(finais).all(axis=1) | (finais<0).any(axis=1) |
             (finais>200).any(axis=1) | (np.abs(np.nansum(finais,axis=1)-ft)>1e-6)).astype('int8')
        assert int(inc.sum())==n_inc
        ufs=near['SG_UF_PROVA'].astype('string').str.strip().str.upper().to_numpy()
        acumular_parte(acumulado,ufs,classes,m1,m2,inc)
    return acumulado,validas,{'metodo':'mesma_linha_RESULTADOS_2025_sem_juncao'}


def fechar(aggs: dict[str,Acumulador],ano: int,n_validas: int,
           controlar_pop: bool=True,geo: dict|None=None) -> dict[str,Acumulador]:
    br=Acumulador()
    for uf in UFS:
        a=aggs[uf]
        if a.n_near!=(a.n_elegiveis+a.excl_status+a.excl_notas+a.excl_inconsistencia):
            raise ValueError(f'{ano}/{uf}: denominadores não fecham.')
        if any(int(a.matrizes[i].sum()) != a.n_elegiveis for i in range(5)):
            raise ValueError(f'{ano}/{uf}: matrizes com denominadores inconsistentes.')
        if geo and geo.get('n_near_geografico_por_uf') is not None:
            if a.n_near!=geo['n_near_geografico_por_uf'][uf]:
                raise ValueError(f'{ano}/{uf}: POP_NEAR difere na fonte geográfica e complemento.')
        br.somar(a)
    aggs['BR']=br
    if br.n_near>n_validas:
        raise ValueError(f'{ano}: POP_NEAR maior que redações válidas.')
    if controlar_pop and br.n_near!=POP_NEAR_REFERENCIA[ano]:
        raise ValueError(f'{ano}: POP_NEAR BR={br.n_near:,} difere do IND-031 '
                         f'({POP_NEAR_REFERENCIA[ano]:,}).')
    return aggs


def kappa_binario(tabela: np.ndarray) -> dict:
    """Kappa ponderado quadrático para rótulos 0/1; 2 categorias => kappa simples."""
    if tabela.shape!=(2,2) or (tabela<0).any():
        raise ValueError('Matriz 2x2 inválida.')
    n=int(tabela.sum())
    if n==0:
        return {'kappa_ponderado':None,'concordancia_percentual':None,
                'discordancia_percentual':None,'status':'sem_avaliacoes_pareadas'}
    p=tabela.astype('float64')/n
    obs=float(p[0,0]+p[1,1])
    e=float(p.sum(axis=1)@p.sum(axis=0))
    # Discordância ponderada: distância quadrática 0 quando igual, 1 quando diferente.
    dobs=1-obs
    dexp=1-e
    if dexp<=1e-14:
        kappa=None
        status='indefinido_sem_variacao_marginal'
    else:
        kappa=float((dexp-dobs)/dexp)
        if not(-1.0000001<=kappa<=1.0000001):
            raise ValueError('Kappa fora de [-1,1].')
        status='ok'
    return {'kappa_ponderado':None if kappa is None else round(kappa,8),
            'concordancia_percentual':round(100*obs,6),
            'discordancia_percentual':round(100*dobs,6), 'status':status}


def supressoes(aggs: dict[str,Acumulador]) -> dict[tuple[str,int],str]:
    """Não exportar contagem positiva 1..29; complementação UF se necessário."""
    ocultar={}
    for uf in ('BR',*UFS):
        for i in range(5):
            tab=aggs[uf].matrizes[i]
            if any(0<int(x)<MIN_CELULA for x in tab.flat):
                ocultar[(uf,i)]='celula_positiva_inferior_30'
    # Não revelar uma única UF omitida por diferença com o agregado nacional.
    for i in range(5):
        estaduais=[uf for uf in UFS if (uf,i) in ocultar]
        if len(estaduais)==1 and ('BR',i) not in ocultar:
            visiveis=[uf for uf in UFS if (uf,i) not in ocultar
                      and aggs[uf].n_elegiveis>=MIN_CELULA]
            if visiveis:
                segundo=max(visiveis,key=lambda uf:(aggs[uf].n_elegiveis,uf))
                ocultar[(segundo,i)]='complementar_geografica'
            else:
                ocultar[('BR',i)]='complementar_nacional'
    return ocultar


def montar_recortes(aggs: dict[str,Acumulador]) -> tuple[dict,dict]:
    ocultar=supressoes(aggs)
    recortes={}
    for uf in ('BR',*UFS):
        a=aggs[uf]
        linhas=[]
        for i,cod in enumerate(COMPETENCIAS):
            motivo=ocultar.get((uf,i))
            tab=a.matrizes[i]
            k=kappa_binario(tab)
            linhas.append({
                'uf':uf,'competencia':cod,'n_pop_near':a.n_near,
                'n_near_evaluator':a.n_elegiveis,
                'matriz_concordancia':(None if motivo else {
                    'av1_nao_av2_nao':int(tab[0,0]),
                    'av1_nao_av2_sim':int(tab[0,1]),
                    'av1_sim_av2_nao':int(tab[1,0]),
                    'av1_sim_av2_sim':int(tab[1,1])}),
                'concordancia_percentual':None if motivo else k['concordancia_percentual'],
                'discordancia_percentual':None if motivo else k['discordancia_percentual'],
                'kappa_ponderado':None if motivo else k['kappa_ponderado'],
                'kappa_status':'suprimido' if motivo else k['status'],
                'suprimido':bool(motivo), 'motivo_supressao':motivo,
            })
        recortes[uf]={
            'uf':uf,'n_pop_near':a.n_near,'n_near_evaluator':a.n_elegiveis,
            'n_excluidos_por_status':a.excl_status,
            'n_excluidos_por_notas_ausentes_ou_invalidas':a.excl_notas,
            'n_excluidos_por_soma_av1_av2_inconsistente':a.excl_inconsistencia,
            'n_notas_finais_com_soma_competencias_divergente':a.incoerencias_finais,
            'competencias':linhas,
            'status_publicacao':'draft_revisao_academica_e_privacidade_cruzada_pendente',
        }
    return recortes,{
        'min_celula_positiva':MIN_CELULA,
        'n_matrizes_suprimidas':len(ocultar),
        'n_supressoes_primarias':sum(v=='celula_positiva_inferior_30' for v in ocultar.values()),
        'n_supressoes_complementares':sum(v.startswith('complementar') for v in ocultar.values()),
        'revisao_privacidade_cruzada_pendente':True,
    }


def carregar_json(arquivo: Path) -> dict:
    with arquivo.open('r',encoding='utf-8-sig') as f:
        obj=json.load(f)
    if not isinstance(obj,dict):
        raise ValueError(f'{arquivo.name}: objeto JSON inválido.')
    return obj


def controlar_ind031(saida: Path,ano: int,aggs: dict[str,Acumulador]) -> str:
    caminho=saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
    if not caminho.exists():
        return 'nao_verificado_dashboard_ausente'
    data=carregar_json(caminho)
    hp=data.get('pages',{}).get('high_performance',{})
    ind31=hp.get('loss_by_competency') if isinstance(hp,dict) else None
    if not isinstance(ind31,dict) or ind31.get('indicator_id')!='IND-031':
        return 'nao_verificado_IND031_ausente'
    recortes={'BR':ind31['brasil']}
    recortes.update({x['uf']:x for x in ind31.get('by_uf',[])})
    if set(recortes)!={'BR',*UFS}:
        raise ValueError(f'{ano}: IND-031 sem os 28 recortes.')
    for uf,registro in recortes.items():
        if int(registro['n_near'])!=aggs[uf].n_near:
            raise ValueError(f'{ano}/{uf}: POP_NEAR não confere com IND-031.')
    return 'aprovado_28_recortes'


def salvar_json(arquivo: Path,data: dict) -> None:
    arquivo.parent.mkdir(parents=True,exist_ok=True)
    temporario=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=arquivo.parent,
                                         prefix=arquivo.name+'.',suffix='.tmp',
                                         delete=False) as f:
            temporario=Path(f.name)
            json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
        os.replace(temporario,arquivo)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def salvar_csv(arquivo: Path,linhas: list[dict]) -> None:
    arquivo.parent.mkdir(parents=True,exist_ok=True)
    temporario=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',
                                         dir=arquivo.parent,prefix=arquivo.name+'.',
                                         suffix='.tmp',delete=False) as f:
            temporario=Path(f.name)
            writer=csv.DictWriter(f,delimiter=';',fieldnames=CAMPOS_CSV,
                                  extrasaction='ignore')
            writer.writeheader()
            writer.writerows(linhas)
        os.replace(temporario,arquivo)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def linhas_csv(todos: dict) -> list[dict]:
    linhas=[]
    for ano,obj in sorted(todos.items(),key=lambda kv:int(kv[0])):
        if obj.get('status')!='ok':
            continue
        for uf in ('BR',*UFS):
            for linha in obj['recortes'][uf]['competencias']:
                mat=linha['matriz_concordancia'] or {}
                linhas.append({
                    'ano':int(ano), 'uf':uf, 'competencia':linha['competencia'],
                    'n_pop_near':linha['n_pop_near'],
                    'n_near_evaluator':linha['n_near_evaluator'],
                    **{ch:mat.get(ch) for ch in (
                        'av1_nao_av2_nao','av1_nao_av2_sim',
                        'av1_sim_av2_nao','av1_sim_av2_sim')},
                    'concordancia_percentual':linha['concordancia_percentual'],
                    'kappa_ponderado':linha['kappa_ponderado'],
                    'kappa_status':linha['kappa_status'],
                    'suprimido':linha['suprimido'],
                    'motivo_supressao':linha['motivo_supressao'],
                })
    return linhas


def integrar_dashboard(saida: Path,processados: dict) -> None:
    for ch,obj in sorted(processados.items(),key=lambda kv:int(kv[0])):
        if obj.get('status')!='ok':
            continue
        ano=int(ch)
        caminho=saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not caminho.exists():
            log(f'  Aviso: dashboard {ano} ausente, integração não efetuada.')
            continue
        data=carregar_json(caminho)
        hp=data.get('pages',{}).get('high_performance')
        if not isinstance(hp,dict):
            raise ValueError(f'{ano}: pages.high_performance ausente.')
        # Catálogo exige ARRAY no caminho reviewer_agreement.
        hp['reviewer_agreement']=[dict({'indicator_id':'IND-038','ano':ano},**linha)
                                  for uf in ('BR',*UFS)
                                  for linha in obj['recortes'][uf]['competencias']]
        data.setdefault('quality',{})['ind038_validation']={
            'status':'ok_agregados', 'n_pop_near_brasil':obj['n_pop_near_brasil'],
            'n_near_evaluator_brasil':obj['n_near_evaluator_brasil'],
            'denominadores_ufs_fecham_brasil':True,
            'controle_IND031':obj['controle_ind031'],
            'fonte':obj['fonte'], 'metodo':'kappa_quadratico_binario',
            'privacidade':obj['privacidade'],
            'revisao_academica_e_privacidade_cruzada_pendente':True,
        }
        avisos=data.setdefault('meta',{}).setdefault('warnings',[])
        aviso=('IND-038: concordância binária dos avaliadores em POP_NEAR_EVALUATOR; '
               'validação acadêmica e divulgação contextual pendentes.')
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json(caminho,data)
        log(f'  Dashboard {ano} integrado; nenhuma cópia .bak criada.')


def executar(base: Path,saida: Path,anos: tuple[int,...],bloco: int,
             sobrescrever: bool=False,somente_modulo: bool=False,
             exigir_2025: bool=False,sem_controle_populacao: bool=False,
             fontes_explicitas: dict[str,Path]|None=None) -> dict:
    base=base.resolve()
    saida=saida.resolve()
    output=saida/'outputs'/'json'/'IND_038_concordancia_desconto.json'
    output_csv=saida/'outputs'/'indicadores'/'IND_038_concordancia_desconto.csv'
    if not sobrescrever and (output.exists() or output_csv.exists()):
        raise FileExistsError('IND-038 já existe: para atualizar, use --sobrescrever.')
    nomes=set()
    for ano in anos:
        if ano<=2023:
            nomes.update({f'MICRODADOS_ENEM_{ano}.CSV',f'COMPETENCIAS_REDACAO_{ano}.CSV'})
        elif ano==2024:
            nomes.update({'PARTICIPANTES_2024.CSV','COMPETENCIAS_REDACAO_2024.CSV'})
        else:
            nomes.add('RESULTADOS_2025.CSV')
    fontes=localizar_fontes(base,nomes,fontes_explicitas)
    faltando=nomes-set(fontes)-({ 'RESULTADOS_2025.CSV'} if not exigir_2025 else set())
    if faltando:
        raise FileNotFoundError(f'Fontes ausentes: {sorted(faltando)}. Verifique --base.')
    anteriores={}
    if sobrescrever and output.exists():
        antigo=carregar_json(output)
        if antigo.get('indicator_id')!='IND-038':
            raise ValueError('O JSON de saída existente pertence a outro indicador.')
        anteriores=dict(antigo.get('years',{}))
    todos=dict(anteriores)
    processados={}
    for ano in anos:
        log(f'IND-038 | {ano}: concordância AV1/AV2 na POP_NEAR...')
        if ano==2025 and 'RESULTADOS_2025.CSV' not in fontes:
            obj={'ano':ano,'status':'indisponivel', 'motivo':'RESULTADOS_2025.csv ausente',
                 'recortes':{}}
            todos[str(ano)]=processados[str(ano)]=obj
            log('  2025 indisponível, sem estimativas.')
            continue
        if ano==2025:
            agregados,n_validas,diagnostico=ler_resultados_2025(fontes['RESULTADOS_2025.CSV'],bloco)
            fonte='RESULTADOS_2025.csv'
        else:
            arq_av=f'COMPETENCIAS_REDACAO_{ano}.CSV'
            arq_geo=('PARTICIPANTES_2024.CSV' if ano==2024 else
                     f'MICRODADOS_ENEM_{ano}.CSV')
            agregados,n_validas,diagnostico=ler_complemento(
                fontes[arq_av],fontes[arq_geo],ano,bloco)
            fonte=f'{arq_av}+{arq_geo}'
        fechar(agregados,ano,n_validas,not sem_controle_populacao,diagnostico)
        controle=controlar_ind031(saida,ano,agregados)
        recortes,privacidade=montar_recortes(agregados)
        br=agregados['BR']
        obj={
            'ano':ano,'status':'ok','population':'POP_NEAR_EVALUATOR',
            'fonte':fonte,'n_validas_brasil':n_validas,
            'n_pop_near_brasil':br.n_near,
            'n_near_evaluator_brasil':br.n_elegiveis,
            'n_excluidos_status_brasil':br.excl_status,
            'n_excluidos_notas_brasil':br.excl_notas,
            'n_excluidos_soma_av_brasil':br.excl_inconsistencia,
            'n_anomalias_soma_competencias_finais':br.incoerencias_finais,
            'diagnostico_fonte':diagnostico,'controle_ind031':controle,
            'privacidade':privacidade,'recortes':recortes,
        }
        todos[str(ano)]=processados[str(ano)]=obj
        log(f'  POP_NEAR={br.n_near:,}; AV1+AV2 elegíveis={br.n_elegiveis:,}; '
            f'matrizes suprimidas={privacidade["n_matrizes_suprimidas"]}.')
    modulo={
        'indicator_id':'IND-038','titulo':'Concordância no desconto',
        'status':'draft','gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'anos_solicitados':list(anos),
        'anos_disponiveis':sorted(int(y) for y,v in todos.items() if v.get('status')=='ok'),
        'population':'POP_NEAR_EVALUATOR', 'geography':'SG_UF_PROVA',
        'methodology':{
            'universe':'TP_STATUS_REDACAO=1; 900<=NU_NOTA_REDACAO<=980',
            'denominator':'POP_NEAR com status AV1=AV2=1, totais e C1..C5 válidos',
            'completeness':'NU_NOTA_AV1 e AV2 devem ser iguais à soma das 5 notas de cada avaliador',
            'binary_discount':'NU_NOTA_COMPi_AVj < 200',
            'matrix_order':'linhas AV1 não,sim; colunas AV2 não,sim',
            'metric':'kappa_ponderado_quadratico_binario_igual_kappa_simples',
            'kappa_zero_denominator':'retorna null se os marginais não apresentam variabilidade',
            'join_2019_2024':'NU_INSCRICAO no mesmo ano via SQLite temporário',
            'join_2025':'mesma_linha RESULTADOS_2025.csv, sem link a participantes',
            'privacy':'tabelas com contagens positivas menores que 30 omitidas; complemento geográfico',
            'cautions':[
                'Kappa quantifica concordância além do acaso sob marginais observadas; não é causal.',
                'Kappa binário ponderado quadrático coincide com kappa não ponderado.',
                'As avaliações AV1/AV2 não são as notas finais por competência.',
                'Apenas POP_NEAR_EVALUATOR: não extrapolar para redações fora de 900–980.',
                'Diferenças de prevalência de descontos alteram interpretação do kappa.',
                'Não afirmar que uma discordância implica erro do avaliador.',
                'UF representa local da prova; anos contam participações, não pessoas únicas.',
                'A publicação requer avaliação acadêmica e revisão contextual dos recortes.',
            ],
        },
        'years':todos,
    }
    salvar_json(output,modulo)
    salvar_csv(output_csv,linhas_csv(todos))
    if not somente_modulo:
        integrar_dashboard(saida,processados)
    log(f'IND-038 concluído. JSON: {output} | CSV: {output_csv}')
    return modulo


def autoteste() -> None:
    import tempfile as _tempfile
    # Kappa: tabela com acordo 80% e equilíbrio marginal => 0,6.
    t=np.array([[40,10],[10,40]],dtype=np.int64)
    k=kappa_binario(t)
    assert k['kappa_ponderado']==0.6 and k['concordancia_percentual']==80.0
    assert kappa_binario(np.array([[20,0],[0,20]]))['kappa_ponderado']==1.0
    assert kappa_binario(np.array([[0,20],[20,0]]))['kappa_ponderado']==-1.0
    assert kappa_binario(np.array([[100,0],[0,0]]))['kappa_ponderado'] is None
    with _tempfile.TemporaryDirectory(prefix='teste_ind038_') as temp:
        root=Path(temp)
        base=root/'dados';base.mkdir()
        saida=root/'outputs'/'json';saida.mkdir(parents=True)
        cols=['NU_INSCRICAO','SG_UF_PROVA',*CAMPOS_AVALIADORES]
        linhas=[]
        for uf in ('SP','RJ'):
            for categoria in range(4):
                for j in range(40):
                    s1=bool(categoria & 2)
                    s2=bool(categoria & 1)
                    av1=[180 if s1 else 200,200,200,200,200]
                    av2=[180 if s2 else 200,200,200,200,200]
                    linha={
                        'NU_INSCRICAO':str(100000+len(linhas)), 'SG_UF_PROVA':uf,
                        'TP_STATUS_REDACAO':'1','NU_NOTA_REDACAO':'960',
                        'TP_STATUS_REDACAO_AV1':'1','TP_STATUS_REDACAO_AV2':'1',
                        'NU_NOTA_AV1':str(sum(av1)),'NU_NOTA_AV2':str(sum(av2)),
                    }
                    linha.update({c:('160' if c=='NU_NOTA_COMP1' else '200') for c in FINAIS})
                    linha.update(dict(zip(AV1,map(str,av1))))
                    linha.update(dict(zip(AV2,map(str,av2))))
                    linhas.append(linha)
        # Duas redações sem notas completas para auditar denominadores.
        linhas[0]['TP_STATUS_REDACAO_AV2']='2'
        linhas[1]['NU_NOTA_AV1']=''
        with (base/'COMPETENCIAS_REDACAO_2024.csv').open('w',encoding='latin-1',newline='') as f:
            w=csv.DictWriter(f,fieldnames=[c for c in cols if c!='SG_UF_PROVA'],delimiter=';',extrasaction='ignore')
            w.writeheader();w.writerows(linhas)
        with (base/'PARTICIPANTES_2024.csv').open('w',encoding='latin-1',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['NU_INSCRICAO','SG_UF_PROVA'],delimiter=';',extrasaction='ignore')
            w.writeheader();w.writerows(linhas)
        pasta_dup=base/'competencias_redacao';pasta_dup.mkdir()
        (pasta_dup/'COMPETENCIAS_REDACAO_2024.csv').write_bytes(
            (base/'COMPETENCIAS_REDACAO_2024.csv').read_bytes())
        assert len(localizar_fontes(root,{'COMPETENCIAS_REDACAO_2024.CSV'}))==1
        fake={'pages':{'high_performance':{'outro_indicador':{'preservar':True}}},
              'quality':{'outro_controle':True},'meta':{'warnings':[]}}
        salvar_json(saida/'dashboard_enem_2024.json',fake)
        out=executar(root,root,(2024,),bloco=37,sobrescrever=True,
                     sem_controle_populacao=True)
        assert out['years']['2024']['n_pop_near_brasil']==320
        assert out['years']['2024']['n_near_evaluator_brasil']==318
        assert out['years']['2024']['n_excluidos_status_brasil']==1
        assert out['years']['2024']['n_excluidos_notas_brasil']==1
        row=out['years']['2024']['recortes']['BR']['competencias'][0]
        assert row['matriz_concordancia'] is not None
        assert sum(row['matriz_concordancia'].values())==318
        assert abs(row['kappa_ponderado'])<0.01
        dash=carregar_json(saida/'dashboard_enem_2024.json')
        assert len(dash['pages']['high_performance']['reviewer_agreement'])==140
        assert dash['pages']['high_performance']['outro_indicador']['preservar']
        assert dash['quality']['outro_controle']
        assert not list(root.rglob('*.bak*'))
        # 2025: mesma linha, sem cruzar identificadores de inscritos.
        with (base/'RESULTADOS_2025.csv').open('w',encoding='latin-1',newline='') as f:
            w=csv.DictWriter(f,fieldnames=[c for c in cols if c!='NU_INSCRICAO'],delimiter=';',extrasaction='ignore')
            w.writeheader();w.writerows(linhas)
        ac,n_valid,diag=ler_resultados_2025(base/'RESULTADOS_2025.csv',bloco=50)
        fechar(ac,2025,n_valid,controlar_pop=False)
        assert ac['BR'].n_near==320 and ac['BR'].n_elegiveis==318
        # 2019-23: vínculos só dos inscritos POP_NEAR na fonte geográfica.
        with (base/'MICRODADOS_ENEM_2019.csv').open('w',encoding='latin-1',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['NU_INSCRICAO','SG_UF_PROVA','TP_STATUS_REDACAO','NU_NOTA_REDACAO'],delimiter=';',extrasaction='ignore')
            w.writeheader();w.writerows(linhas)
        (base/'COMPETENCIAS_REDACAO_2019.csv').write_bytes(
            (base/'COMPETENCIAS_REDACAO_2024.csv').read_bytes())
        ac,n_valid,diag=ler_complemento(base/'COMPETENCIAS_REDACAO_2019.csv',
                    base/'MICRODADOS_ENEM_2019.csv',2019,bloco=51)
        fechar(ac,2019,n_valid,controlar_pop=False,geo=diag)
        assert ac['BR'].n_near==320 and ac['BR'].n_elegiveis==318
        # Duplicatas diferentes: erro acionável, nunca escolha aleatória.
        (pasta_dup/'COMPETENCIAS_REDACAO_2024.csv').write_text('diferente',encoding='utf-8')
        try:
            localizar_fontes(root,{'COMPETENCIAS_REDACAO_2024.CSV'})
        except ValueError as ex:
            assert '--competencias-2024' in str(ex)
        else:
            raise AssertionError('Fonte divergente deveria provocar erro.')
    log('Autoteste IND-038 aprovado: kappa, 2019/2024/2025, SQL, duplicatas, CSV/JSON e dashboard.')


def main() -> None:
    p=argparse.ArgumentParser(description='IND-038 — Concordância no desconto AV1×AV2')
    p.add_argument('--base',type=Path,default=raiz_projeto())
    p.add_argument('--saida',type=Path,default=raiz_projeto())
    p.add_argument('--anos',nargs='+',type=int,default=list(ANOS))
    p.add_argument('--bloco',type=int,default=100_000)
    p.add_argument('--sobrescrever',action='store_true')
    p.add_argument('--somente-modulo',action='store_true')
    p.add_argument('--exigir-2025',action='store_true')
    p.add_argument('--sem-controle-populacao',action='store_true',
                   help='Apenas testes sintéticos: desativa controle IND-031 fixo.')
    p.add_argument('--competencias-2024',type=Path,default=None)
    p.add_argument('--participantes-2024',type=Path,default=None)
    p.add_argument('--fonte-avaliadores',type=Path,default=None,
                   help='Arquivo de avaliadores para 2019–2023 (somente com um ano em --anos).')
    p.add_argument('--fonte-geografia',type=Path,default=None,
                   help='Arquivo de geografia para 2019–2023 (somente com um ano em --anos).')
    p.add_argument('--autoteste',action='store_true')
    args=p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos=tuple(sorted(set(args.anos)))
    if not anos or any(ano not in ANOS for ano in anos):
        p.error('Informe anos entre 2019 e 2025.')
    if args.bloco<=0:
        p.error('--bloco deve ser positivo.')
    fontes={}
    if args.competencias_2024:
        fontes['COMPETENCIAS_REDACAO_2024.CSV']=args.competencias_2024
    if args.participantes_2024:
        fontes['PARTICIPANTES_2024.CSV']=args.participantes_2024
    if args.fonte_avaliadores or args.fonte_geografia:
        if len(anos)!=1 or anos[0] not in range(2019,2024):
            p.error('--fonte-avaliadores e --fonte-geografia requerem um ano de 2019 a 2023.')
        if args.fonte_avaliadores:
            fontes[f'COMPETENCIAS_REDACAO_{anos[0]}.CSV']=args.fonte_avaliadores
        if args.fonte_geografia:
            fontes[f'MICRODADOS_ENEM_{anos[0]}.CSV']=args.fonte_geografia
    try:
        executar(args.base,args.saida,anos,args.bloco,args.sobrescrever,
                 args.somente_modulo,args.exigir_2025,args.sem_controle_populacao,fontes)
    except (OSError,ValueError,sqlite3.DatabaseError,json.JSONDecodeError) as exc:
        print(f'ERRO IND-038: {exc}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__':
    main()
