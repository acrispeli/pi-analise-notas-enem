#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-039 — Mapa nota × competência | Projeto Integrador IV — UNIVESP.

Referência: Catálogo de Indicadores ENEM 2019–2025 v2, IND-039.
Pergunta: como o padrão de perdas em C1–C5 muda de 900 a 1000?
População: POP_HIGH = redações TP_STATUS_REDACAO=1 e nota em [900,1000].
Faixas: [900,920), [920,940), [940,960), [960,980), [980,1000].
Cada faixa × competência produz:
  - n_com_desconto = quantidade de redações com Ci < 200;
  - percentual_com_desconto = 100 * n_com_desconto / n_com_competencias_validas;
  - perda_media = sum(200-Ci) / n_com_competencias_validas.
Apenas redações com 5 competências numéricas em [0,200] entram no
DENOMINADOR das métricas de C1–C5. A população POP_HIGH, o número de notas
inválidas e as divergências soma(C1..C5) vs nota final são auditados.
Divergências de soma são preservadas, não corrigidas ou excluídas.

Fontes:
 - 2019..2023 MICRODADOS_ENEM_<ano>.csv (UF, nota, C1..C5 na mesma linha);
 - 2024 COMPETENCIAS_REDACAO_2024.csv + PARTICIPANTES_2024.csv,
        associados EXCLUSIVAMENTE pela inscrição da mesma edição (SQLite);
 - 2025 RESULTADOS_2025.csv (UF, nota, C1..C5 na mesma linha).

Saídas:
 outputs/json/IND_039_mapa_nota_competencia.json
 outputs/indicadores/IND_039_mapa_nota_competencia.csv
 outputs/json/dashboard_enem_<ano>.json
      pages.high_performance.score_competency_heatmap
      quality.ind039_validation

O gerador aceita fontes duplicadas byte a byte idênticas, mas exige uma
escolha explícita caso cópias diferentes tenham o mesmo nome. Sem .bak.
POLÍTICA DE DIVULGAÇÃO REVISADA: resultados agregados por ano, UF, faixa
 e competência SEM supressão automática de células de 1 a 29. Isso elimina
 a ocultação formal de faixas cujas contagens eram dedutíveis de POP_HIGH.
 Não são publicados registros individuais. A divulgação pública permanece
 sujeita à avaliação acadêmica e de riscos por cruzamento entre indicadores.

Uso:
 python src/indicadores/IND_039_mapa_nota_competencia.py --autoteste
 python src/indicadores/IND_039_mapa_nota_competencia.py --anos 2024 --sobrescrever
 python src/indicadores/IND_039_mapa_nota_competencia.py --sobrescrever
"""
from __future__ import annotations

import argparse
import csv
import filecmp
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG',
       'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR',
       'RS', 'SC', 'SE', 'SP', 'TO')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
COL_C = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
LIMITES = (900, 920, 940, 960, 980, 1000)
FAIXAS = ('900–<920', '920–<940', '940–<960', '960–<980', '980–1000')
# Regra explícita de divulgação de agregados, adotada após revisão do projeto.
# NÃO equivale a certificação de anonimização nem elimina a revisão de riscos.
POLITICA_DIVULGACAO = 'agregada_sem_supressao_de_contagens_1_a_29'
VERSAO_POLITICA_DIVULGACAO = '2.0'
# Contagens nacionais independentes do IND-030 (não substituem confronto por UF).
POP_HIGH_REFERENCIA = {2019: 172601, 2020: 183371, 2021: 163769,
                       2022: 197115, 2023: 288662, 2024: 291123,
                       2025: 173543}
CAMPOS_CSV = ('ano', 'uf', 'faixa', 'limite_inferior', 'limite_superior',
              'superior_inclusivo', 'competencia', 'n_pop_high',
              'n_na_faixa', 'n_com_competencias_validas', 'n_com_desconto',
              'percentual_com_desconto', 'soma_pontos_perdidos',
              'perda_media', 'suprimido', 'motivo_supressao')


def log(s: str) -> None:
    print(s, flush=True)


def raiz_projeto() -> Path:
    arq = Path(__file__).resolve()
    if arq.parent.name.lower() == 'indicadores' and arq.parent.parent.name.lower() == 'src':
        return arq.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                     explicitas: dict[str, Path] | None = None) -> dict[str, Path]:
    ignorar = {'.venv','venv','.git','outputs','__pycache__','node_modules',
               '.pytest_cache','.mypy_cache'}
    explicitas = {k.upper(): v for k,v in (explicitas or {}).items()}
    fontes: dict[str, Path] = {}
    for nome, apontado in explicitas.items():
        if nome not in nomes:
            raise ValueError(f'Fonte explícita não solicitada para este(s) ano(s): {nome}.')
        arq = Path(apontado).expanduser()
        if not arq.is_absolute():
            arq = base / arq
        arq = arq.resolve()
        if not arq.is_file():
            raise FileNotFoundError(f'Fonte escolhida não encontrada: {arq}')
        fontes[nome] = arq
        log(f'  Fonte escolhida: {nome} = {arq}')
    for pasta, diretorios, arquivos in os.walk(base):
        diretorios[:] = sorted(x for x in diretorios if x.lower() not in ignorar)
        for nome_arq in sorted(arquivos):
            nome = nome_arq.upper()
            if nome not in nomes or nome in explicitas:
                continue
            caminho = Path(pasta)/nome_arq
            if nome in fontes and caminho.resolve() != fontes[nome].resolve():
                if filecmp.cmp(fontes[nome], caminho, shallow=False):
                    log(f'  CSV duplicado idêntico: {nome}; usando {fontes[nome]}.')
                    continue
                opcao = ('--competencias-2024' if nome == 'COMPETENCIAS_REDACAO_2024.CSV'
                         else '--participantes-2024' if nome == 'PARTICIPANTES_2024.CSV'
                         else '--fonte-ano')
                raise ValueError(f'Arquivos diferentes com mesmo nome {nome}: '
                                 f'{fontes[nome]} e {caminho}; selecione com {opcao} <caminho>.')
            fontes[nome] = caminho
    return fontes


def ler_blocos(arq: Path, colunas: list[str], bloco: int):
    with arq.open('rb') as f:
        cod = 'utf-8-sig' if f.read(3) == b'\xef\xbb\xbf' else 'latin-1'
    cab = pd.read_csv(arq, sep=';', encoding=cod, nrows=0)
    faltando = set(colunas) - set(str(x).strip().lstrip('\ufeff') for x in cab.columns)
    if faltando:
        raise ValueError(f'{arq.name}: colunas obrigatórias ausentes {sorted(faltando)}.')
    with pd.read_csv(arq, sep=';', encoding=cod, dtype='string', usecols=colunas,
                     chunksize=bloco, na_filter=False, keep_default_na=False,
                     low_memory=False) as leitor:
        for parte in leitor:
            parte.columns = [str(x).strip().lstrip('\ufeff') for x in parte.columns]
            yield parte


def numeros(serie: pd.Series) -> np.ndarray:
    return pd.to_numeric(serie.astype('string').str.strip().str.replace(',', '.',regex=False),
                         errors='coerce').to_numpy(dtype=np.float64)


def selecionar_high(parte: pd.DataFrame) -> tuple[pd.DataFrame,int]:
    validas = parte['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1').to_numpy()
    nota = numeros(parte['NU_NOTA_REDACAO'])
    ruins = validas & (~np.isfinite(nota) | (nota < 0) | (nota > 1000))
    if ruins.any():
        raise ValueError(f'{int(ruins.sum())} nota(s) finais inválidas com TP_STATUS_REDACAO=1.')
    filtro = validas & (nota >= 900) & (nota <= 1000)
    high = parte.loc[filtro].copy()
    high['__nota_final'] = nota[filtro]
    high['__faixa_ind039'] = np.searchsorted(LIMITES[1:-1], nota[filtro], side='right').astype('int8')
    return high, int(validas.sum())


def componentes_high(high: pd.DataFrame) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    """Retorna perdas N×5, sinalização de C1..C5 válidas e soma divergente.

    Usamos np.nan onde C inválida; preservamos o registro no denominador
    POP_HIGH, mas não nas estatísticas das cinco competências.
    """
    if high.empty:
        return np.empty((0, 5),float), np.empty(0,bool), np.empty(0,bool)
    comps = np.column_stack([numeros(high[c]) for c in COL_C])
    boas = (np.isfinite(comps).all(axis=1) & (comps >= 0).all(axis=1)
             & (comps <= 200).all(axis=1))
    dif = np.zeros(len(high),dtype=bool)
    nota = high['__nota_final'].to_numpy(dtype=np.float64)
    dif[boas] = ~np.isclose(comps[boas].sum(axis=1), nota[boas], atol=1e-6, rtol=0)
    perdas = 200.0 - comps
    perdas[~boas] = np.nan
    return perdas, boas, dif


@dataclass
class Acumulador:
    n_faixas: np.ndarray = field(default_factory=lambda: np.zeros(5,dtype=np.int64))
    n_validas_c: np.ndarray = field(default_factory=lambda: np.zeros(5,dtype=np.int64))
    n_inconsistentes: np.ndarray = field(default_factory=lambda: np.zeros(5,dtype=np.int64))
    n_desconto: np.ndarray = field(default_factory=lambda: np.zeros((5,5),dtype=np.int64))
    somas_perdas: np.ndarray = field(default_factory=lambda: np.zeros((5,5),dtype=np.float64))
    n_near: int = 0

    @property
    def n_high(self) -> int:
        return int(self.n_faixas.sum())

    def acumular(self, faixa: np.ndarray, perda: np.ndarray,
                boas: np.ndarray, divergentes: np.ndarray, notas: np.ndarray) -> None:
        if not (len(faixa)==len(perda)==len(boas)==len(divergentes)==len(notas)):
            raise ValueError('Vetores com tamanhos incompatíveis.')
        self.n_near += int(np.count_nonzero(notas <= 980))
        self.n_faixas += np.bincount(faixa, minlength=5)
        self.n_validas_c += np.bincount(faixa[boas], minlength=5)
        self.n_inconsistentes += np.bincount(faixa[divergentes], minlength=5)
        for j in range(5):
            seleciona = boas & (faixa==j)
            if not np.any(seleciona):
                continue
            valores = perda[seleciona]
            self.n_desconto[j] += np.count_nonzero(valores > 0,axis=0)
            self.somas_perdas[j] += np.sum(valores,axis=0,dtype=np.float64)

    def somar(self, a: 'Acumulador') -> None:
        self.n_faixas += a.n_faixas
        self.n_validas_c += a.n_validas_c
        self.n_inconsistentes += a.n_inconsistentes
        self.n_desconto += a.n_desconto
        self.somas_perdas += a.somas_perdas
        self.n_near += a.n_near


def acumular_parte(aggs: dict[str,Acumulador], ufs: np.ndarray, high: pd.DataFrame) -> None:
    if high.empty:
        return
    if len(ufs) != len(high) or not pd.Series(ufs).isin(UFS).all():
        raise ValueError('UF inválida ou ausente para uma redação POP_HIGH.')
    perdas, boas, diferentes = componentes_high(high)
    faixa = high['__faixa_ind039'].to_numpy(dtype=np.int8)
    nota = high['__nota_final'].to_numpy(dtype=np.float64)
    for uf in np.unique(ufs):
        filtro = ufs==uf
        aggs[str(uf)].acumular(faixa[filtro], perdas[filtro], boas[filtro],
                              diferentes[filtro], nota[filtro])


def ler_mesma_linha(arq: Path, bloco: int) -> tuple[dict,int,dict]:
    aggs = {uf:Acumulador() for uf in UFS}
    n_validas=0
    for parte in ler_blocos(arq,['SG_UF_PROVA','TP_STATUS_REDACAO',
                                  'NU_NOTA_REDACAO',*COL_C],bloco):
        high,n = selecionar_high(parte)
        n_validas += n
        if not high.empty:
            ufs = high['SG_UF_PROVA'].astype('string').str.strip().str.upper().to_numpy()
            acumular_parte(aggs, ufs, high)
    return aggs,n_validas,{'metodo':'mesma_linha','fonte':arq.name}


def ler_2024(comp: Path, participantes: Path, bloco: int) -> tuple[dict,int,dict]:
    """Indexa somente as redações POP_HIGH e associa UF por inscrição.

    Cada inscrição da POP_HIGH deve aparecer uma única vez na base de notas
    e uma única vez entre os participantes; não há junção por posição da linha.
    """
    aggs={uf:Acumulador() for uf in UFS}
    with tempfile.TemporaryDirectory(prefix='enem_ind039_') as tmp:
        db=sqlite3.connect(str(Path(tmp)/'chaves.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('''CREATE TABLE high (
                id TEXT PRIMARY KEY, nota REAL, faixa INTEGER,
                c1 REAL, c2 REAL, c3 REAL, c4 REAL, c5 REAL,
                uf TEXT DEFAULT NULL) WITHOUT ROWID''')
            db.execute('CREATE TEMP TABLE lote_part(id TEXT, uf TEXT)')
            n_validas=0
            n_high=0
            for parte in ler_blocos(comp,['NU_INSCRICAO','TP_STATUS_REDACAO',
                                          'NU_NOTA_REDACAO',*COL_C],bloco):
                high,n=selecionar_high(parte)
                n_validas+=n
                if high.empty:
                    continue
                ids=high['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not x for x in ids):
                    raise ValueError('2024: inscrição vazia em POP_HIGH.')
                notas=high['__nota_final'].to_numpy(dtype=float)
                faixas=high['__faixa_ind039'].to_numpy(dtype=np.int8)
                comps=np.column_stack([numeros(high[x]) for x in COL_C])
                try:
                    db.executemany('INSERT INTO high(id,nota,faixa,c1,c2,c3,c4,c5) '
                                   'VALUES (?,?,?,?,?,?,?,?)',
                                   ((ident,float(nota),int(faixa),
                                     *(None if not np.isfinite(x) else float(x) for x in c))
                                    for ident,nota,faixa,c in zip(ids,notas,faixas,comps)))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('2024: NU_INSCRICAO duplicada em POP_HIGH do complemento.') from exc
                n_high+=len(high)
                db.commit()
            log(f'  2024: {n_high:,} redações POP_HIGH indexadas para associação por inscrição.')
            n_participantes=0
            n_vinculadas=0
            for parte in ler_blocos(participantes,['NU_INSCRICAO','SG_UF_PROVA'],bloco):
                ids=parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs=parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(not x for x in ids):
                    raise ValueError('2024: inscrição vazia no arquivo PARTICIPANTES_2024.')
                db.execute('DELETE FROM lote_part')
                db.executemany('INSERT INTO lote_part VALUES (?,?)',zip(ids,ufs))
                # Join com chave e acesso por índice PRIMARY KEY na tabela high.
                combinados=db.execute('''SELECT h.id,p.uf,h.nota,h.faixa,
                          h.c1,h.c2,h.c3,h.c4,h.c5
                          FROM lote_part p JOIN high h ON p.id=h.id''').fetchall()
                if combinados:
                    uf_batch=[str(row[1]) for row in combinados]
                    if not all(uf in UFS for uf in uf_batch):
                        raise ValueError('2024: UF inválida no participante vinculado.')
                    for id_,uf,*_ in combinados:
                        atualizado=db.execute('UPDATE high SET uf=? WHERE id=? AND uf IS NULL',
                                              (uf,id_)).rowcount
                        if atualizado!=1:
                            raise ValueError('2024: participante repetido para mesma redação POP_HIGH.')
                    df=pd.DataFrame.from_records(combinados,columns=['NU_INSCRICAO','SG_UF_PROVA',
                          '__nota_final','__faixa_ind039',*COL_C])
                    # Constrói quadro da mesma forma que o arquivo de edição única.
                    acumular_parte(aggs,np.asarray(uf_batch,dtype=str),df)
                    n_vinculadas+=len(combinados)
                n_participantes+=len(parte)
                db.commit()
            if n_vinculadas!=n_high:
                raise ValueError(f'2024: {n_high-n_vinculadas} registros POP_HIGH sem participante vinculado.')
            return aggs,n_validas,{'metodo':'join_NU_INSCRICAO_SQLite',
                   'n_participantes_lidos':n_participantes,'n_high_vinculadas':n_vinculadas,
                   'n_high_sem_correspondencia':0}
        finally:
            db.close()


def fechar(aggs: dict[str,Acumulador], ano: int, validas: int,
           controlar_pop: bool=True) -> dict[str,Acumulador]:
    brasil=Acumulador()
    for uf in UFS:
        a=aggs[uf]
        if a.n_high < a.n_near or a.n_high > validas:
            raise ValueError(f'{ano}/{uf}: população inválida.')
        if np.any(a.n_validas_c > a.n_faixas) or np.any(a.n_inconsistentes > a.n_validas_c):
            raise ValueError(f'{ano}/{uf}: denominadores por faixa inconsistentes.')
        if np.any(a.n_desconto > a.n_validas_c[:,None]):
            raise ValueError(f'{ano}/{uf}: descontos superiores ao denominador.')
        if np.any(a.somas_perdas < -1e-6) or np.any(a.somas_perdas > 200*a.n_validas_c[:,None]+1e-6):
            raise ValueError(f'{ano}/{uf}: perdas incompatíveis com notas de competência 0..200.')
        brasil.somar(a)
    if brasil.n_high>validas:
        raise ValueError(f'{ano}: POP_HIGH excede o total de redações válidas.')
    if controlar_pop and brasil.n_high!=POP_HIGH_REFERENCIA[ano]:
        raise ValueError(f'{ano}: POP_HIGH={brasil.n_high:,} não coincide com '
                         f'IND-030={POP_HIGH_REFERENCIA[ano]:,}.')
    aggs['BR']=brasil
    return aggs


def carregar_json(arq: Path) -> dict:
    with arq.open('r',encoding='utf-8-sig') as f:
        dados=json.load(f)
    if not isinstance(dados,dict):
        raise ValueError(f'{arq}: JSON inválido.')
    return dados


def comparar_ind030_031(saida: Path, ano: int, aggs: dict[str,Acumulador]) -> dict:
    """Audita faixas IND-030 inclusive quando este agregou faixas de 20 pontos."""
    caminho=saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
    if not caminho.is_file():
        return {'ind030':'dashboard_ausente','ind031':'dashboard_ausente'}
    d=carregar_json(caminho)
    hp=d.get('pages',{}).get('high_performance',{})
    ind030=hp.get('score_bands') if isinstance(hp,dict) else None
    res30='nao_disponivel'
    if isinstance(ind030,dict) and ind030.get('indicator_id')=='IND-030':
        rec={'BR':ind030['brasil']}
        rec.update({r['uf']:r for r in ind030.get('by_uf',[])})
        if set(rec)!={'BR',*UFS}:
            raise ValueError(f'{ano}: IND-030 não possui as 27 UFs.')
        for uf,r in rec.items():
            a=aggs[uf]
            if int(r['n_high'])!=a.n_high:
                raise ValueError(f'{ano}/{uf}: POP_HIGH diferente do IND-030.')
            faixas=r.get('faixas',[])
            if sum(int(f['quantidade']) for f in faixas)!=a.n_high:
                raise ValueError(f'{ano}/{uf}: faixas do IND-030 não fecham.')
            for f in faixas:
                lo,hi=int(f['limite_inferior']),int(f['limite_superior'])
                if lo not in LIMITES or hi not in LIMITES or lo>=hi:
                    raise ValueError(f'{ano}/{uf}: intervalo IND-030 incompatível.')
                i,j=LIMITES.index(lo),LIMITES.index(hi)
                if int(sum(a.n_faixas[i:j]))!=int(f['quantidade']):
                    raise ValueError(f'{ano}/{uf}: faixas 20 pontos diferentes do IND-030.')
        res30='aprovado_n_high_faixas_uf'
    ind031=hp.get('loss_by_competency') if isinstance(hp,dict) else None
    res31='nao_disponivel'
    if isinstance(ind031,dict) and ind031.get('indicator_id')=='IND-031':
        rec={'BR':ind031['brasil']}
        rec.update({r['uf']:r for r in ind031.get('by_uf',[])})
        if set(rec)!={'BR',*UFS}:
            raise ValueError(f'{ano}: IND-031 sem as 27 UFs.')
        for uf,r in rec.items():
            if int(r['n_near'])!=aggs[uf].n_near:
                raise ValueError(f'{ano}/{uf}: POP_NEAR diferente do IND-031.')
        res31='aprovado_pop_near_uf'
    return {'ind030':res30,'ind031':res31}


def supressao(aggs: dict[str, Acumulador]) -> tuple[dict[tuple[str, int, int], str], dict]:
    """Política documentada: divulgar apenas agregados, sem limiar 1..29.

    A regra antiga ocultava faixas pequenas, mas seus N podiam ser deduzidos
    subtraindo as demais faixas de POP_HIGH (também presente no IND-030).
    Para não sugerir proteção inexistente, esta versão NÃO suprime esses N.
    Registros individuais nunca são exportados. A revisão de risco de
    cruzamento com outras publicações permanece obrigatória para divulgar.
    """
    n_faixas_pequenas = sum(
        0 < int(aggs[uf].n_faixas[f]) < 30
        for uf in ('BR', *UFS) for f in range(5)
    )
    n_celulas_pequenas = sum(
        0 < int(aggs[uf].n_desconto[f, c]) < 30
        for uf in ('BR', *UFS) for f in range(5) for c in range(5)
    )
    return {}, {
        'politica': POLITICA_DIVULGACAO,
        'versao_politica': VERSAO_POLITICA_DIVULGACAO,
        'supressao_automatica_1_a_29': False,
        'min_n': None,
        'celulas_primarias_suprimidas': 0,
        'celulas_complementares_suprimidas': 0,
        'faixas_com_n_1_a_29_divulgadas': n_faixas_pequenas,
        'contagens_desconto_1_a_29_divulgadas': n_celulas_pequenas,
        'exporta_registros_individuais': False,
        'revisao_privacidade_cruzada_pendente': True,
        'justificativa': (
            'Dados publicados somente como agregados por ano/UF/faixa/competencia. '
            'Nao se aplica supressao automatica de 1 a 29. A regra anterior '
            'permitia deducao de faixas a partir de totais publicos.'
        ),
    }


def montar_recortes(aggs: dict[str, Acumulador]) -> tuple[dict, dict]:
    """Mantém o contrato JSON anterior, sem marcações falsas de supressão."""
    ocultas, priv = supressao(aggs)
    assert not ocultas, 'A política de divulgação agregada não oculta células.'
    resultado = {}
    for uf in ('BR', *UFS):
        a = aggs[uf]
        faixas = []
        for f in range(5):
            n = int(a.n_faixas[f])
            nval = int(a.n_validas_c[f])
            comps = []
            for c, cod in enumerate(COMPETENCIAS):
                d = int(a.n_desconto[f, c])
                s = float(a.somas_perdas[f, c])
                comps.append({
                    'competencia': cod,
                    'n_com_desconto': d,
                    'percentual_com_desconto': round(100 * d / nval, 6) if nval else None,
                    'soma_pontos_perdidos': round(s, 6),
                    'perda_media': round(s / nval, 6) if nval else None,
                    'suprimido': False,
                    'motivo_supressao': None,
                })
            faixas.append({
                'faixa': FAIXAS[f],
                'limite_inferior': LIMITES[f],
                'limite_superior': LIMITES[f + 1],
                'superior_inclusivo': f == 4,
                'n_na_faixa': n,
                'n_com_competencias_validas': nval,
                'n_inconsistencias_soma': int(a.n_inconsistentes[f]),
                'competencias': comps,
            })
        resultado[uf] = {
            'uf': uf,
            'populacao': 'POP_HIGH',
            'intervalo_nota': [900, 1000],
            'n_high': a.n_high,
            'n_near': a.n_near,
            'n_competencias_invalidas': int((a.n_faixas - a.n_validas_c).sum()),
            'n_inconsistencias_soma': int(a.n_inconsistentes.sum()),
            'ha_competencias_invalidas': bool(np.any(a.n_faixas != a.n_validas_c)),
            'ha_inconsistencias_soma': bool(np.any(a.n_inconsistentes)),
            'faixas': faixas,
            'status_publicacao': 'draft_revisao_academica_privacidade_pendente',
        }
    return resultado, priv


def salvar_json(arq: Path, dados: dict) -> None:
    arq.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=arq.parent,
                                         prefix=arq.name+'.',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            json.dump(dados,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
        os.replace(temp,arq)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def salvar_csv(arq: Path, linhas: list[dict]) -> None:
    arq.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',dir=arq.parent,
                                         prefix=arq.name+'.',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            w=csv.DictWriter(f,fieldnames=CAMPOS_CSV,delimiter=';',extrasaction='ignore')
            w.writeheader();w.writerows(linhas)
        os.replace(temp,arq)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def gerar_linhas(todos: dict) -> list[dict]:
    linhas=[]
    for ano,obj in sorted(todos.items(),key=lambda t:int(t[0])):
        if obj.get('status')!='ok':
            continue
        for uf in ('BR',*UFS):
            r=obj['recortes'][uf]
            for faixa in r['faixas']:
                for c in faixa['competencias']:
                    linhas.append({'ano':int(ano),'uf':uf,'n_pop_high':r['n_high'],
                                   **{k:faixa[k] for k in ('faixa','limite_inferior','limite_superior',
                                                             'superior_inclusivo','n_na_faixa',
                                                             'n_com_competencias_validas')},
                                   **c})
    return linhas


def integrar_dashboards(saida: Path, processados: dict) -> None:
    for ano_txt,obj in sorted(processados.items(),key=lambda x:int(x[0])):
        if obj.get('status')!='ok':
            continue
        ano=int(ano_txt)
        arq=saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not arq.is_file():
            log(f'  Dashboard {ano} ausente no destino: integração ignorada.')
            continue
        d=carregar_json(arq)
        hp=d.get('pages',{}).get('high_performance')
        if not isinstance(hp,dict):
            raise ValueError(f'{arq.name}: pages.high_performance ausente.')
        hp['score_competency_heatmap']={
            'indicator_id':'IND-039','population':'POP_HIGH','year':ano,'status':'draft',
            'method':'% com Ci<200 e perda média Ci, por faixas 20 pontos de nota final',
            'brasil':obj['recortes']['BR'],
            'by_uf':[obj['recortes'][uf] for uf in UFS],
            'privacy_note':'Agregados sem supressão automática de 1 a 29; revisão cruzada com IND-030/031/032 pendente.',
            'publication_policy': POLITICA_DIVULGACAO}
        quality=d.setdefault('quality',{})
        quality['ind039_validation']={
            'status':'ok_agregados','n_high_brasil':obj['n_high_brasil'],
            'n_near_brasil':obj['n_near_brasil'],
            'n_competencias_invalidas_brasil':obj['recortes']['BR']['n_competencias_invalidas'],
            'n_inconsistencias_soma_brasil':obj['recortes']['BR']['n_inconsistencias_soma'],
            'controles':obj['controles'],'privacidade':obj['privacidade'],
            'revisao_academica_privacidade_pendente':True,
            'publication_policy': POLITICA_DIVULGACAO}
        aviso=('IND-039: mapa POP_HIGH 900–1000; agregados sem supressão automática 1..29; resultados preliminares, '
               'revisão acadêmica e de privacidade cruzada pendentes.')
        avisos=d.setdefault('meta',{}).setdefault('warnings',[])
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json(arq,d)
        log(f'  Dashboard {ano} integrado, sem criar .bak.')


def executar(base: Path,saida: Path,anos: tuple[int,...],bloco: int,
             sobrescrever: bool,somente_modulo: bool,exigir_2025: bool,
             controlar_pop: bool=True,
             explicitas: dict[str,Path] | None=None) -> dict:
    base,saida=base.resolve(),saida.resolve()
    out_json=saida/'outputs'/'json'/'IND_039_mapa_nota_competencia.json'
    out_csv=saida/'outputs'/'indicadores'/'IND_039_mapa_nota_competencia.csv'
    if not sobrescrever and (out_json.exists() or out_csv.exists()):
        raise FileExistsError('IND-039 já gerado. Utilize --sobrescrever.')
    nomes=set()
    for ano in anos:
        if ano<=2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano==2024:
            nomes.update({'COMPETENCIAS_REDACAO_2024.CSV','PARTICIPANTES_2024.CSV'})
        else:
            nomes.add('RESULTADOS_2025.CSV')
    fontes=localizar_fontes(base,nomes,explicitas)
    faltas=sorted(nomes-set(fontes)-(set() if exigir_2025 else {'RESULTADOS_2025.CSV'}))
    if faltas:
        raise FileNotFoundError('Arquivos de origem não localizados: '+', '.join(faltas))
    anteriores={}
    if sobrescrever and out_json.is_file():
        antigo=carregar_json(out_json)
        if antigo.get('indicator_id')!='IND-039':
            raise ValueError('JSON anterior não pertence ao IND-039.')
        anteriores=dict(antigo.get('years',{}))
        politica_anterior = antigo.get('publication_policy', {}).get('id')
        anos_nao_reprocessados = sorted(set(int(a) for a in anteriores) - set(anos))
        if politica_anterior != POLITICA_DIVULGACAO and anos_nao_reprocessados:
            raise ValueError(
                'A política de divulgação do IND-039 mudou. Reprocesse TODOS os anos '
                'já existentes com --sobrescrever para não misturar dados com e sem '
                'supressão no mesmo JSON. Anos pendentes: '
                + ', '.join(map(str, anos_nao_reprocessados))
            )
    todos=dict(anteriores)
    processados={}
    for ano in anos:
        log(f'IND-039 | {ano}: mapa nota × competência por faixas POP_HIGH...')
        if ano==2025 and 'RESULTADOS_2025.CSV' not in fontes:
            obj={'ano':ano,'status':'indisponivel',
                 'reason':'RESULTADOS_2025.csv não encontrado; não estimar resultados.',
                 'recortes':{}}
            todos[str(ano)]=processados[str(ano)]=obj
            continue
        if ano==2024:
            aggs,n_validas,diag=ler_2024(fontes['COMPETENCIAS_REDACAO_2024.CSV'],
                                          fontes['PARTICIPANTES_2024.CSV'],bloco)
            fonte='COMPETENCIAS_REDACAO_2024.csv + PARTICIPANTES_2024.csv'
        else:
            nome=f'MICRODADOS_ENEM_{ano}.CSV' if ano<2024 else 'RESULTADOS_2025.CSV'
            aggs,n_validas,diag=ler_mesma_linha(fontes[nome],bloco)
            fonte=fontes[nome].name
        aggs=fechar(aggs,ano,n_validas,controlar_pop)
        controles=comparar_ind030_031(saida,ano,aggs)
        recortes,priv=montar_recortes(aggs)
        obj={'ano':ano,'status':'ok','fonte':fonte,'population':'POP_HIGH',
             'n_validas_brasil':n_validas,'n_high_brasil':aggs['BR'].n_high,
             'n_near_brasil':aggs['BR'].n_near,'diagnostico_fonte':diag,
             'controles':controles,'privacidade':priv,'recortes':recortes}
        todos[str(ano)]=processados[str(ano)]=obj
        log(f'  POP_HIGH BR={aggs["BR"].n_high:,}; '
            f'inconsistências C1..C5={int(aggs["BR"].n_inconsistentes.sum())}; '
            f'controle IND-030={controles["ind030"]}; IND-031={controles["ind031"]}.')
    modulo={
        'indicator_id':'IND-039','titulo':'Mapa nota × competência','status':'draft',
        'gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'anos_solicitados':list(anos),
        'anos_disponiveis':sorted(int(ano) for ano,obj in todos.items() if obj.get('status')=='ok'),
        'population':'POP_HIGH','geography':'SG_UF_PROVA',
        'publication_policy': {'id': POLITICA_DIVULGACAO,
                               'version': VERSAO_POLITICA_DIVULGACAO,
                               'review_status': 'draft_revisao_academica_privacidade_pendente'},
        'methodology':{
            'selection':'TP_STATUS_REDACAO=1 e 900<=NU_NOTA_REDACAO<=1000',
            'score_bands':list(FAIXAS),
            'discount':'NU_NOTA_COMPi < 200',
            'mean_loss':'soma(200-NU_NOTA_COMPi) / n_com_competencias_validas da faixa',
            'percent_discount':'100*n_com_desconto / n_com_competencias_validas da faixa',
            'invalid_competencies':'não contribuem para médias/taxas; permanecem em POP_HIGH',
            'sum_mismatch':'auditada e preservada sem correção/imputação',
            '2024_join':'NU_INSCRICAO entre dados da mesma edição via SQLite temporário',
            'privacy':'agregados sem supressão automática de 1 a 29; revisão cruzada pendente',
            'cautions':[
                '900–<920, 920–<940, 940–<960, 960–<980, 980–1000 (1000 incluído).',
                'As médias e taxas de cada linha usam apenas redações com as cinco notas C1..C5 válidas.',
                'Pontuação 1000 tem desconto zero e participa da última faixa.',
                'UF da prova não significa necessariamente UF de residência.',
                'Comparação descritiva por faixa; não identifica causas ou falhas de correção.',
                '2019–2025 é série de participações, não de pessoas únicas.',
                'A divulgação de agregados de 1 a 29 foi escolhida no projeto; não é garantia de anonimização.',
                'A publicação depende de auditoria de privacidade cruzada e revisão acadêmica.',
            ],
        },'years':todos,
    }
    salvar_json(out_json,modulo)
    salvar_csv(out_csv,gerar_linhas(todos))
    log(f'JSON: {out_json}\nCSV: {out_csv}')
    if not somente_modulo:
        integrar_dashboards(saida,processados)
    log('IND-039 concluído. Resultados draft.')
    return modulo


def autoteste() -> None:
    """Testa limites de faixa, cálculo, duplicatas, junção e integração sintéticas."""
    from tempfile import TemporaryDirectory
    # Cinco faixas e nota 1000 na última faixa, sem desconto.
    notas=[900,919,920,939,940,959,960,979,980,999,1000]
    cs=[]
    for s in notas:
        x=[200]*5
        delta=1000-s
        for i in range(5):
            parcial=min(200,delta)
            x[i]-=parcial
            delta-=parcial
        cs.append(x)
    tab=pd.DataFrame({'TP_STATUS_REDACAO':['1']*len(notas),
                      'NU_NOTA_REDACAO':[str(n) for n in notas],
                      'SG_UF_PROVA':['SP']*len(notas),
                      **{COL_C[i]:[str(x[i]) for x in cs] for i in range(5)}})
    near,nvalid=selecionar_high(tab)
    assert nvalid==11 and len(near)==11
    assert near['__faixa_ind039'].tolist()==[0,0,1,1,2,2,3,3,4,4,4]
    vals,boas,dif=componentes_high(near)
    assert boas.all() and not dif.any()
    a=Acumulador()
    a.acumular(near['__faixa_ind039'].to_numpy(),vals,boas,dif,near['__nota_final'].to_numpy())
    assert a.n_high==11 and a.n_near==9
    assert int(a.n_desconto[4,0])==2
    assert a.somas_perdas[4,0]==21  # 980 =>20, 999=>1, 1000=>0
    assert int(a.n_faixas.sum())==11
    # Nova política: faixas pequenas não ficam mascaradas enquanto o total
    # é público; N positivo de 1 a 29 é explicitamente divulgado como agregado.
    aggs_raras = {uf: Acumulador() for uf in UFS}
    aggs_raras['SP'].acumular(near['__faixa_ind039'].to_numpy(), vals, boas,
                             dif, near['__nota_final'].to_numpy())
    aggs_raras = fechar(aggs_raras, 2019, nvalid, controlar_pop=False)
    rec_raros, politica = montar_recortes(aggs_raras)
    assert politica['supressao_automatica_1_a_29'] is False
    assert politica['faixas_com_n_1_a_29_divulgadas'] > 0
    assert sum(x['n_na_faixa'] for x in rec_raros['BR']['faixas']) == nvalid
    assert all(not cell['suprimido'] for faixa in rec_raros['SP']['faixas']
               for cell in faixa['competencias'])
    assert rec_raros['SP']['faixas'][4]['n_na_faixa'] == 3
    assert rec_raros['SP']['faixas'][4]['competencias'][0]['n_com_desconto'] == 2
    # A mesma fonte validada deve produzir totais por UF e BR.
    with TemporaryDirectory(prefix='teste_ind039_') as tmp:
        root=Path(tmp)
        raw=root/'data'/'raw'
        raw.mkdir(parents=True)
        (root/'outputs'/'json').mkdir(parents=True)
        massivo=pd.concat([tab]*25,ignore_index=True)
        massivo.loc[:149,'SG_UF_PROVA']='SP'
        massivo.loc[150:,'SG_UF_PROVA']='RJ'
        massivo.to_csv(raw/'MICRODADOS_ENEM_2019.csv',sep=';',index=False)
        g19,v19,_=ler_mesma_linha(raw/'MICRODADOS_ENEM_2019.csv',35)
        g19=fechar(g19,2019,v19,controlar_pop=False)
        assert g19['BR'].n_high==275 and g19['SP'].n_high+g19['RJ'].n_high==275
        # A leitura de 2024 usa o arquivo COMPETENCIAS separadamente da UF.
        pessoas=pd.DataFrame({'NU_INSCRICAO':[str(i+1000) for i in range(len(massivo))],
                              'SG_UF_PROVA':massivo['SG_UF_PROVA'].values})
        competencias=massivo.drop(columns=['SG_UF_PROVA']).copy()
        competencias.insert(0,'NU_INSCRICAO',pessoas['NU_INSCRICAO'])
        pessoas.to_csv(raw/'PARTICIPANTES_2024.csv',sep=';',index=False)
        competencias.to_csv(raw/'COMPETENCIAS_REDACAO_2024.csv',sep=';',index=False)
        sub=raw/'competencias_redacao'
        sub.mkdir()
        copia=sub/'COMPETENCIAS_REDACAO_2024.csv'
        copia.write_bytes((raw/'COMPETENCIAS_REDACAO_2024.csv').read_bytes())
        assert 'COMPETENCIAS_REDACAO_2024.CSV' in localizar_fontes(
            root,{'COMPETENCIAS_REDACAO_2024.CSV'})
        g24,v24,d24=ler_2024(raw/'COMPETENCIAS_REDACAO_2024.csv',
                              raw/'PARTICIPANTES_2024.csv',37)
        g24=fechar(g24,2024,v24,controlar_pop=False)
        assert g24['BR'].n_high==275 and d24['n_high_vinculadas']==275
        assert np.array_equal(g24['BR'].n_desconto,g19['BR'].n_desconto)
        # Confirma que a operação não apaga os demais indicadores.
        dash={'meta':{'year':2024,'warnings':[]},
              'pages':{'high_performance':{'score_bands':{'example':'preservar'}}},
              'quality':{'ind030_validation':{'example':'preservar'}}}
        salvar_json(root/'outputs'/'json'/'dashboard_enem_2024.json',dash)
        saida=executar(root,root,(2024,),37,False,False,False,controlar_pop=False)
        assert saida['years']['2024']['n_high_brasil']==275
        after=carregar_json(root/'outputs'/'json'/'dashboard_enem_2024.json')
        assert after['pages']['high_performance']['score_bands']['example']=='preservar'
        assert after['pages']['high_performance']['score_competency_heatmap']['indicator_id']=='IND-039'
        assert after['quality']['ind030_validation']['example']=='preservar'
        assert (root/'outputs'/'indicadores'/'IND_039_mapa_nota_competencia.csv').exists()
        assert saida['publication_policy']['id'] == POLITICA_DIVULGACAO
        assert after['pages']['high_performance']['score_competency_heatmap']['publication_policy'] == POLITICA_DIVULGACAO
        assert all(f['n_na_faixa'] is not None for f in saida['years']['2024']['recortes']['BR']['faixas'])
        # Simula versão antiga com políticas incompatíveis e evita mesclar anos.
        antigo = carregar_json(root/'outputs'/'json'/'IND_039_mapa_nota_competencia.json')
        antigo.pop('publication_policy', None)
        antigo['years']['2019'] = {'ano': 2019, 'status': 'ok'}
        salvar_json(root/'outputs'/'json'/'IND_039_mapa_nota_competencia.json', antigo)
        try:
            executar(root, root, (2024,), 37, True, True, False, controlar_pop=False)
        except ValueError as exc:
            assert 'Reprocesse TODOS os anos' in str(exc)
        else:
            raise AssertionError('Mistura de políticas de divulgação foi permitida.')
        assert not list(root.rglob('*.bak*'))
        copia.write_text('conteúdo diferente',encoding='utf8')
        try:
            localizar_fontes(root,{'COMPETENCIAS_REDACAO_2024.CSV'})
        except ValueError:
            pass
        else:
            raise AssertionError('Cópias divergentes deveriam bloquear o processamento.')
    log('Autoteste IND-039 corrigido aprovado: faixas, política de divulgação, '
        'bloqueio de mescla de versões, leitura 2019/2024, '
        'duplicatas, CSV/JSON e integração ao dashboard.')


def main() -> None:
    p=argparse.ArgumentParser(description='IND-039 — Mapa nota × competência, POP_HIGH')
    p.add_argument('--base',type=Path,default=raiz_projeto())
    p.add_argument('--saida',type=Path,default=raiz_projeto())
    p.add_argument('--anos',type=int,nargs='+',default=list(ANOS))
    p.add_argument('--bloco',type=int,default=100_000)
    p.add_argument('--sobrescrever',action='store_true')
    p.add_argument('--somente-modulo',action='store_true')
    p.add_argument('--exigir-2025',action='store_true')
    p.add_argument('--autoteste',action='store_true')
    p.add_argument('--competencias-2024',type=Path,default=None)
    p.add_argument('--participantes-2024',type=Path,default=None)
    args=p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos=tuple(sorted(set(args.anos)))
    if not anos or any(y not in ANOS for y in anos):
        p.error('Informe anos de 2019 até 2025.')
    if args.bloco<=0:
        p.error('--bloco precisa ser positivo.')
    explicitas={}
    if args.competencias_2024 is not None:
        explicitas['COMPETENCIAS_REDACAO_2024.CSV']=args.competencias_2024
    if args.participantes_2024 is not None:
        explicitas['PARTICIPANTES_2024.CSV']=args.participantes_2024
    try:
        executar(args.base,args.saida,anos,args.bloco,args.sobrescrever,
                 args.somente_modulo,args.exigir_2025,explicitas=explicitas)
    except (OSError,ValueError,sqlite3.DatabaseError,json.JSONDecodeError) as exc:
        print(f'ERRO IND-039: {exc}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__':
    main()
