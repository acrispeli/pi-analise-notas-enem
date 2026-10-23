#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-031 — Perda por competência nas redações próximas de 1000 (ENEM 2019–2025).

Definição do catálogo: POP_NEAR = redações válidas com nota de 900 a 980,
INCLUINDO os dois limites; perda em Ck = 200 - NU_NOTA_COMPk.

Resultados por edição/UF e no histórico 2019–2025: matriz de faixas de nota
por competência, com perda média e mediana, e resumo da população POP_NEAR.
Processa todos os microdados elegíveis, sem amostragem.

Executar na raiz do projeto, após o IND-030:
  python src/indicadores/IND_031_perda_competencias.py
  python src/indicadores/IND_031_perda_competencias.py --somente-modulo
  python src/indicadores/IND_031_perda_competencias.py --sobrescrever

Requer pandas e numpy. Usa IND-001, IND-006 e IND-008 como controles de QA.
Não processar em paralelo com scripts que atualizem dashboards.
NÃO divulgar publicamente antes de revisão acadêmica/de privacidade cruzada.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split())
GEOS = ('BR', *UFS)
COL_COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COL_COMP)
INDICADOR = 'IND-031'
ARQUIVO = 'IND_031_perda_competencias'
MIN_N = 30
NOTA_MIN, NOTA_MAX = 900, 980
# As quatro primeiras faixas são [início, fim); a última é a nota 980 exata.
FAIXAS = ((900, 920), (920, 940), (940, 960), (960, 980), (980, 980))
METODO = 'perda_200_menos_competencia_media_mediana_por_faixa_pop_near'
NOTA_METODOLOGICA = (
    'POP_NEAR = POP_VALID (TP_STATUS_REDACAO=1, nota válida [0,1000]) com '
    '900 <= NU_NOTA_REDACAO <= 980. A nota 1000 não participa. '
    'Cada perda é 200 - nota da competência, entre 0 e 200 pontos. '
    'As primeiras faixas são [900,920), [920,940), [940,960), [960,980); '
    'a última contém a nota 980. Faixas adjacentes pequenas são mescladas, '
    'e recortes com 1 a 29 redações são suprimidos. Medianas calculadas '
    'por frequências exatas; histórico recalculado a partir de todas as '
    'participações, sem média de médias/medianas anuais. '
    'UF indica local de prova, não residência; histórico soma participações, '
    'não pessoas únicas. Sem registros individualizados. Resultados draft: '
    'a proteção interna NÃO substitui revisão de inferência entre BR, UFs, '
    'anos, IND-008, IND-030 e demais tabelas já divulgadas.'
)


@dataclass
class Estatistica:
    n: int = 0
    somas: list[float] = field(default_factory=lambda: [0.0] * 5)
    somas_notas: float = 0.0
    frequencias: list[Counter] = field(default_factory=lambda: [Counter() for _ in range(5)])

    def incluir(self, nota: np.ndarray, competencias: np.ndarray) -> None:
        if len(nota) == 0:
            return
        perdas = 200.0 - competencias
        self.n += len(nota)
        self.somas_notas += float(np.sum(nota, dtype=np.float64))
        for i in range(5):
            self.somas[i] += float(np.sum(perdas[:, i], dtype=np.float64))
            valores, quantidades = np.unique(perdas[:, i], return_counts=True)
            self.frequencias[i].update({float(x): int(q) for x, q in zip(valores, quantidades)})

    def acumular(self, outro: 'Estatistica') -> None:
        self.n += outro.n
        self.somas_notas += outro.somas_notas
        for i in range(5):
            self.somas[i] += outro.somas[i]
            self.frequencias[i].update(outro.frequencias[i])

    def copia(self) -> 'Estatistica':
        e = Estatistica()
        e.acumular(self)
        return e

    def validar(self, contexto: str) -> None:
        if not self.n:
            return
        if any(sum(c.values()) != self.n for c in self.frequencias):
            raise ValueError(f'{contexto}: frequências das perdas não fecham')
        if any(s < -0.01 or s > 200 * self.n + 0.01 for s in self.somas):
            raise ValueError(f'{contexto}: perda fora do intervalo [0,200]')
        if not np.isclose(sum(self.somas), 1000 * self.n - self.somas_notas,
                          rtol=0, atol=max(0.01, self.n * 1e-7)):
            raise ValueError(f'{contexto}: perdas não correspondem a 1000 - nota total')


def grupo(periodo: dict, uf: str) -> dict:
    if uf == 'BR':
        return periodo['brasil']
    return next(x for x in periodo['ufs'] if x['uf'] == uf)


def ler_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f'Arquivo obrigatório não encontrado: {path}')
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def gravar_json(path: Path, documento: dict) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(documento, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def fonte(raiz: Path, ano: int) -> Path:
    arquivo = (f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023
               else f'RESULTADOS_{ano}.csv')
    return raiz / 'data' / 'raw' / str(ano) / arquivo


def versao(atual: str) -> str:
    ids = list(dict.fromkeys(re.findall(r'ind\d{3}', atual or '')))
    if 'ind031' not in ids:
        ids.append('ind031')
    return '2.31.0-' + '-'.join(ids)


def carregar_referencias(raiz: Path) -> dict:
    arquivos = {
        1: 'IND_001_redacoes_validas.json',
        6: 'IND_006_distribuicao_notas.json',
        8: 'IND_008_notas_1000.json',
    }
    refs = {}
    for n, nome in arquivos.items():
        doc = ler_json(raiz / 'outputs' / 'json' / nome)
        if doc.get('indicator', {}).get('id') != f'IND-{n:03d}':
            raise ValueError(f'{nome}: indicador incorreto')
        if [x.get('ano') for x in doc.get('years', [])] != list(ANOS):
            raise ValueError(f'{nome}: faltam edições de 2019 a 2025')
        for p in (*doc['years'], doc.get('historical', {})):
            if len(p.get('ufs', [])) != 27 or {x['uf'] for x in p['ufs']} != set(UFS):
                raise ValueError(f'{nome}: UFs ausentes ou repetidas')
        refs[n] = doc
    return refs


def indice_faixa(nota: pd.Series) -> np.ndarray:
    # Nota 980 vai exclusivamente à quinta faixa.
    return np.minimum(((nota.to_numpy(dtype=np.float64) - NOTA_MIN) // 20).astype('int64'), 4)


def iniciar_matriz() -> dict[str, list[Estatistica]]:
    return {uf: [Estatistica() for _ in FAIXAS] for uf in GEOS}


def somar_estatisticas(arr: list[Estatistica]) -> Estatistica:
    total = Estatistica()
    for e in arr:
        total.acumular(e)
    return total


def processar_ano(raiz: Path, ano: int, bloco: int) -> tuple[dict, dict]:
    arquivo = fonte(raiz, ano)
    if not arquivo.is_file():
        raise FileNotFoundError(f'{ano}: {arquivo}')
    matriz = iniciar_matriz()
    validas, perfeitas = Counter(), Counter()
    qa = Counter()
    for df in pd.read_csv(
        arquivo, sep=';', encoding='utf-8-sig', encoding_errors='replace',
        usecols=list(COLUNAS), dtype=str, keep_default_na=False, na_filter=False,
        chunksize=bloco, on_bad_lines='error',
    ):
        uf = df['SG_UF_PROVA'].str.strip().str.upper()
        status = df['TP_STATUS_REDACAO'].str.strip().eq('1')
        nota_txt = df['NU_NOTA_REDACAO'].str.strip()
        nota = pd.to_numeric(nota_txt.str.replace(',', '.', regex=False), errors='coerce')
        valid = status & nota.between(0, 1000)
        perto = valid & nota.between(NOTA_MIN, NOTA_MAX)
        mil = valid & nota.eq(1000)
        qa['linhas'] += len(df)
        qa['validas'] += int(valid.sum())
        qa['near'] += int(perto.sum())
        qa['notas_1000'] += int(mil.sum())
        qa['status1_sem_nota'] += int((status & nota_txt.eq('')).sum())
        qa['status1_nota_invalida'] += int((status & nota_txt.ne('') & ~nota.between(0,1000)).sum())
        qa['validas_uf_invalida'] += int((valid & ~uf.isin(UFS)).sum())
        for codigo, quantidade in uf[valid].value_counts().items():
            if codigo in UFS:
                validas[str(codigo)] += int(quantidade)
        for codigo, quantidade in uf[mil].value_counts().items():
            if codigo in UFS:
                perfeitas[str(codigo)] += int(quantidade)
        if not perto.any():
            continue
        dados = df.loc[perto, list(COL_COMP)].copy()
        comp = dados.apply(lambda s: pd.to_numeric(s.str.strip().str.replace(',', '.', regex=False),
                                                   errors='coerce'))
        notas = nota.loc[perto]
        geografia = uf.loc[perto]
        if comp.isna().any().any() or not comp.ge(0).all().all() or not comp.le(200).all().all():
            raise ValueError(f'{ano}: competência ausente ou fora de [0,200] em POP_NEAR')
        if not np.allclose(comp.sum(axis=1).to_numpy(dtype=np.float64),
                           notas.to_numpy(dtype=np.float64), rtol=0, atol=1e-7):
            raise ValueError(f'{ano}: soma C1..C5 não coincide com nota final em POP_NEAR')
        if not geografia.isin(UFS).all():
            raise ValueError(f'{ano}: POP_NEAR com UF inválida')
        compacto = comp.copy()
        compacto['UF'] = geografia.to_numpy()
        compacto['NOTA'] = notas.to_numpy(dtype=np.float64)
        compacto['FAIXA'] = indice_faixa(notas)
        for (sigla, indice), sub in compacto.groupby(['UF', 'FAIXA'], sort=False):
            matriz[str(sigla)][int(indice)].incluir(
                sub['NOTA'].to_numpy(dtype=np.float64),
                sub[list(COL_COMP)].to_numpy(dtype=np.float64),
            )
    if qa['linhas'] <= 0 or qa['status1_sem_nota'] or qa['status1_nota_invalida']:
        raise ValueError(f'{ano}: fonte vazia ou registros status=1 com nota inválida')
    if qa['validas_uf_invalida']:
        raise ValueError(f'{ano}: redações válidas com UF ausente/inválida')
    if sum(validas.values()) != qa['validas'] or sum(perfeitas.values()) != qa['notas_1000']:
        raise ValueError(f'{ano}: soma de UFs difere do Brasil (válidas ou notas 1000)')
    # Brasil é obtido pela soma das 27 UFs, evitando duas passagens pelos dados.
    for idx in range(5):
        for sigla in UFS:
            matriz['BR'][idx].acumular(matriz[sigla][idx])
    validas['BR'] = qa['validas']
    perfeitas['BR'] = qa['notas_1000']
    if sum(x.n for x in matriz['BR']) != qa['near']:
        raise ValueError(f'{ano}: soma POP_NEAR não confere')
    for sigla in GEOS:
        for idx, e in enumerate(matriz[sigla]):
            e.validar(f'{ano}/{sigla}/faixa{idx}')
    return {'matriz': matriz, 'validas': validas, 'perfeitas': perfeitas,
            'linhas': qa['linhas'], 'near': qa['near'], 'arquivo': arquivo.name}, dict(qa)


def mediana_contador(cont: Counter, n: int) -> float | None:
    if n == 0:
        return None
    if sum(cont.values()) != n:
        raise AssertionError('Histograma não fecha para mediana')
    alvos = ((n - 1) // 2, n // 2)  # índices zero-based
    achados = []
    acumulado = 0
    for valor, freq in sorted(cont.items()):
        proximo = acumulado + freq
        while len(achados) < 2 and acumulado <= alvos[len(achados)] < proximo:
            achados.append(valor)
        acumulado = proximo
        if len(achados) == 2:
            break
    if len(achados) != 2:
        raise AssertionError('Mediana incompleta')
    return round((achados[0] + achados[1]) / 2, 6)


def componentes(e: Estatistica) -> list[dict]:
    if e.n <= 0:
        return []
    return [
        {'competencia': f'C{i+1}',
         'media_perda': round(e.somas[i] / e.n, 6),
         'mediana_perda': mediana_contador(e.frequencias[i], e.n),
         'soma_pontos_perdidos': round(e.somas[i], 6),
         'n_redacoes': e.n}
        for i in range(5)
    ]


def ajustar_faixas(arr: list[Estatistica]) -> tuple[list[dict], str]:
    """Agrupa faixas adjacentes até toda faixa publicada ter N=0 ou N>=30."""
    total = sum(x.n for x in arr)
    if 0 < total < MIN_N:
        return [], 'suprimido_recorte_pequeno'
    atual = [{'lo': lo, 'hi': hi, 'estat': e.copia()}
             for (lo, hi), e in zip(FAIXAS, arr)]
    while len(atual) > 1:
        indices = [i for i, x in enumerate(atual) if 0 < x['estat'].n < MIN_N]
        if not indices:
            break
        i = indices[0]
        vizinhos = [k for k in (i-1, i+1) if 0 <= k < len(atual)]
        k = min(vizinhos, key=lambda j: (atual[j]['estat'].n, j))
        a = min(i, k)
        e = atual[a]['estat'].copia()
        e.acumular(atual[a+1]['estat'])
        atual[a] = {'lo': atual[a]['lo'], 'hi': atual[a+1]['hi'], 'estat': e}
        atual.pop(a+1)
    if any(0 < x['estat'].n < MIN_N for x in atual):
        raise AssertionError('Faixa pequena não foi agregada')
    resultado = []
    for x in atual:
        lo, hi, e = x['lo'], x['hi'], x['estat']
        label = str(lo) if lo == hi else (f'{lo}–{hi}' if hi == NOTA_MAX else f'{lo}–<{hi}')
        resultado.append({'faixa': label, 'limite_inferior': lo,
                          'limite_superior': hi, 'superior_inclusivo': hi == NOTA_MAX,
                          'n_redacoes': e.n, 'competencias': componentes(e)})
    return resultado, ('faixas_mescladas' if len(atual) != len(arr) else 'ok')


def recorte(entrada: dict, geo: str) -> dict:
    arr = entrada['matriz'][geo]
    total = somar_estatisticas(arr)
    if total.n > entrada['validas'][geo]:
        raise AssertionError('POP_NEAR não pode exceder POP_VALID')
    faixas, status = ajustar_faixas(arr)
    suprimido = status == 'suprimido_recorte_pequeno'
    return {'populacao': 'POP_NEAR', 'intervalo_nota': [NOTA_MIN, NOTA_MAX],
            'n_validas': int(entrada['validas'][geo]),
            'n_near': None if suprimido else total.n,
            'status_publicacao': status,
            'resumo_competencias': [] if suprimido else componentes(total),
            'faixas': faixas,
            'n_redacoes_faixas_fecha_near': None if suprimido else sum(f['n_redacoes'] for f in faixas) == total.n,
            'sem_dados_individuais': True}


def periodo(entrada: dict, ano: int | None) -> dict:
    doc = {'brasil': recorte(entrada, 'BR'),
           'ufs': [{'uf': uf, **recorte(entrada, uf)} for uf in UFS],
           'qualidade': {'status': 'ok',
                         'soma_27_ufs_igual_brasil': sum(sum(x.n for x in entrada['matriz'][uf]) for uf in UFS)
                                                    == sum(x.n for x in entrada['matriz']['BR']),
                         'faixas_internas_fecham': True,
                         'recortes_suprimidos': sum(0 < sum(x.n for x in entrada['matriz'][uf]) < MIN_N for uf in GEOS),
                         'recortes_mesclados': sum(recorte(entrada, uf)['status_publicacao']=='faixas_mescladas' for uf in GEOS)}}
    if ano is None:
        doc['periodo'] = '2019-2025'
    else:
        doc['ano'] = ano
        doc['arquivo_fonte'] = entrada['arquivo']
    if not doc['qualidade']['soma_27_ufs_igual_brasil']:
        raise ValueError(f'{ano}: UFs não fecham Brasil')
    return doc


def conferir_controles(entrada: dict, refs: dict, indice: int | None) -> None:
    p1 = refs[1]['historical'] if indice is None else refs[1]['years'][indice]
    p6 = refs[6]['historical'] if indice is None else refs[6]['years'][indice]
    p8 = refs[8]['historical'] if indice is None else refs[8]['years'][indice]
    for uf in GEOS:
        n = entrada['validas'][uf]
        if n != int(grupo(p1, uf)['redacoes_validas']) or n != int(grupo(p6, uf)['n_validas']) or n != int(grupo(p8, uf)['n_validas']):
            raise ValueError(f'{indice}/{uf}: POP_VALID não confere com IND-001/006/008')
        if entrada['perfeitas'][uf] != int(grupo(p8, uf)['n_notas_1000']):
            raise ValueError(f'{indice}/{uf}: notas 1000 não conferem com IND-008')
        hist = grupo(p6, uf)['faixas']
        high = hist[-1]
        if int(high['limite_inferior']) != 900 or int(high['limite_superior']) != 1000:
            raise ValueError(f'{indice}/{uf}: faixa 900–1000 do IND-006 mudou')
        if sum(x.n for x in entrada['matriz'][uf]) > int(high['quantidade']):
            raise ValueError(f'{indice}/{uf}: POP_NEAR excede POP_HIGH do IND-006')


def historico(anuais: list[dict]) -> dict:
    acumulado = {'matriz': iniciar_matriz(), 'validas': Counter(),
                 'perfeitas': Counter(), 'linhas': 0, 'near': 0, 'arquivo': '2019–2025'}
    for ano in anuais:
        acumulado['linhas'] += ano['linhas']
        acumulado['near'] += ano['near']
        for geo in GEOS:
            acumulado['validas'][geo] += ano['validas'][geo]
            acumulado['perfeitas'][geo] += ano['perfeitas'][geo]
            for i in range(5):
                acumulado['matriz'][geo][i].acumular(ano['matriz'][geo][i])
    for geo in GEOS:
        for i, e in enumerate(acumulado['matriz'][geo]):
            e.validar(f'historico/{geo}/faixa{i}')
    return acumulado


def validar_dashboard(doc: dict, ano: int) -> None:
    if doc.get('meta', {}).get('year') != ano:
        raise ValueError(f'dashboard {ano}: meta.year incompatível')
    for secao in ('high_performance', 'temporal', 'methodology'):
        if not isinstance(doc.get('pages', {}).get(secao), dict):
            raise ValueError(f'dashboard {ano}: pages.{secao} ausente')
    if not isinstance(doc.get('quality'), dict):
        raise ValueError(f'dashboard {ano}: quality ausente')
    if doc['quality'].get('ind030_validation', {}).get('status') != 'ok' or 'score_bands' not in doc['pages']['high_performance']:
        raise ValueError(f'dashboard {ano}: execute o IND-030 antes do IND-031')


def atualizar_dashboard(doc: dict, p: dict, anos: list[dict], hist: dict, hora: str) -> dict:
    novo = deepcopy(doc)
    alto = novo['pages']['high_performance']
    alto['loss_by_competency'] = {
        'indicator_id': INDICADOR, 'population': 'POP_NEAR', 'method': METODO,
        'brasil': deepcopy(p['brasil']), 'by_uf': deepcopy(p['ufs']),
        'privacy_note': NOTA_METODOLOGICA,
    }
    alto['status'] = 'partial'
    alto['reason'] = 'IND-030 e IND-031 disponíveis; demais indicadores de alto desempenho pendentes'
    novo['pages']['temporal']['ind031'] = {
        'indicator_id': INDICADOR, 'population': 'POP_NEAR',
        'national_by_year': [{'year': a['ano'], **deepcopy(a['brasil'])} for a in anos],
        'period_total': deepcopy(hist['brasil']), 'period_by_uf': deepcopy(hist['ufs']),
        'note': 'Médias ponderadas por N e medianas recalculadas por frequências no histórico.',
    }
    novo['pages']['methodology']['ind031'] = {
        'definition': 'Perda média e mediana em cada competência de redações com nota de 900 a 980',
        'population': 'POP_NEAR = POP_VALID e 900 <= NU_NOTA_REDACAO <= 980',
        'method': METODO, 'source_indicators': ['IND-001', 'IND-006', 'IND-008'],
        'geography': 'SG_UF_PROVA', 'minimum_published_cell': MIN_N,
        'limitations': NOTA_METODOLOGICA,
    }
    novo['quality']['ind031_validation'] = {
        'status': 'ok', 'population': 'POP_NEAR',
        'n_near_brasil': p['brasil']['n_near'],
        'soma_27_ufs_igual_brasil': p['qualidade']['soma_27_ufs_igual_brasil'],
        'perdas_somam_distancia_1000': True,
        'recortes_suprimidos': p['qualidade']['recortes_suprimidos'],
        'recortes_faixas_mescladas': p['qualidade']['recortes_mesclados'],
        'revisao_academica_pendente': True,
        'revisao_privacidade_complementar_pendente': True,
    }
    novo['meta']['analysis_version'] = versao(doc.get('meta', {}).get('analysis_version', ''))
    novo['meta']['generated_at'] = hora
    novo['meta']['data_status'] = 'draft'
    aviso = 'IND-031: perdas C1–C5 em POP_NEAR 900–980; revisão acadêmica e privacidade cruzada pendentes.'
    if aviso not in novo['meta'].setdefault('warnings', []):
        novo['meta']['warnings'].append(aviso)
    return novo


def linhas_csv(periodos: list[dict], hist: dict) -> list[dict]:
    out = []
    for p in [*periodos, hist]:
        periodo_atual = str(p.get('ano', '2019-2025'))
        for geo in GEOS:
            r = grupo(p, geo)
            grupos = [('POP_NEAR_TOTAL', r['n_near'], r['resumo_competencias'])]
            grupos.extend((f['faixa'], f['n_redacoes'], f['competencias']) for f in r['faixas'])
            if r['status_publicacao'] == 'suprimido_recorte_pequeno':
                grupos = [('SUPRIMIDA', None, [])]
            for faixa, n, comps in grupos:
                if not comps:
                    out.append({'indicador_id': INDICADOR, 'periodo': periodo_atual,
                                'uf': geo, 'populacao': 'POP_NEAR', 'faixa': faixa,
                                'competencia': None, 'n_redacoes': n,
                                'media_perda': None, 'mediana_perda': None,
                                'soma_pontos_perdidos': None,
                                'status_publicacao': r['status_publicacao']})
                else:
                    for c in comps:
                        out.append({'indicador_id': INDICADOR, 'periodo': periodo_atual,
                                    'uf': geo, 'populacao': 'POP_NEAR', 'faixa': faixa,
                                    'competencia': c['competencia'], 'n_redacoes': n,
                                    'media_perda': c['media_perda'],
                                    'mediana_perda': c['mediana_perda'],
                                    'soma_pontos_perdidos': c['soma_pontos_perdidos'],
                                    'status_publicacao': r['status_publicacao']})
    if len(out) < 224:
        raise AssertionError('IND-031: CSV não contempla todos os recortes')
    return out


def executar(raiz: Path, bloco: int = 100_000, somente_modulo: bool = False,
             sobrescrever: bool = False) -> dict:
    raiz = raiz.resolve()
    if bloco < 1:
        raise ValueError('--bloco deve ser inteiro positivo')
    refs = carregar_referencias(raiz)
    dir_json = raiz / 'outputs' / 'json'
    dir_csv = raiz / 'outputs' / 'indicadores'
    destinos = [dir_json / f'{ARQUIVO}.json', dir_csv / f'{ARQUIVO}.csv']
    antigos, hashes = {}, {}
    if not somente_modulo:
        for ano in ANOS:
            path = dir_json / f'dashboard_enem_{ano}.json'
            doc = ler_json(path)
            validar_dashboard(doc, ano)
            if not sobrescrever and ('loss_by_competency' in doc['pages']['high_performance'] or
                                     'ind031_validation' in doc['quality']):
                raise FileExistsError(f'IND-031 já consta no dashboard de {ano}; use --sobrescrever')
            antigos[ano] = doc
            hashes[ano] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not sobrescrever:
        for caminho in destinos:
            if caminho.exists():
                raise FileExistsError(f'{caminho} já existe; use --sobrescrever')

    processados, modulos_ano, source_qa = [], [], {}
    for idx, ano in enumerate(ANOS):
        print(f'IND-031 | processando {ano}', flush=True)
        entrada, qa = processar_ano(raiz, ano, bloco)
        conferir_controles(entrada, refs, idx)
        if entrada['linhas'] != int(refs[1]['years'][idx]['brasil']['total_registros']):
            raise ValueError(f'{ano}: registros lidos não coincidem com IND-001')
        processados.append(entrada)
        m = periodo(entrada, ano)
        modulos_ano.append(m)
        source_qa[str(ano)] = {'arquivo': entrada['arquivo'],
                               'n_linhas': entrada['linhas'],
                               'n_validas': qa['validas'],
                               'n_pop_near': qa['near'],
                               'notas_1000_conferidas_ind008': True,
                               'competencias_validas_e_soma_conferidas': True}
        print(f'  POP_VALID={qa["validas"]:,}; POP_NEAR={qa["near"]:,}', flush=True)
    somatorio = historico(processados)
    conferir_controles(somatorio, refs, None)
    hist = periodo(somatorio, None)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    aversao = versao(next(iter(antigos.values()))['meta'].get('analysis_version', '')) if antigos else '2.31.0-ind031'
    modulo = {
        'meta': {'indicator_id': INDICADOR, 'module_schema_version': 'ind031-module-1.0.0',
                 'analysis_version': aversao,
                 'dataset_version': 'enem-2019-2025-csv-publico',
                 'generated_at': gerado, 'data_status': 'draft',
                 'source_indicators': ['IND-001', 'IND-006', 'IND-008'],
                 'population_definition': 'POP_NEAR = POP_VALID e 900 <= nota <= 980',
                 'geographic_dimension': 'SG_UF_PROVA', 'method': METODO,
                 'minimum_group_count': MIN_N, 'source_qa': source_qa,
                 'publication_status': 'draft; revisão acadêmica e privacidade cruzada pendentes',
                 'notes': NOTA_METODOLOGICA},
        'indicator': {'id': INDICADOR, 'name': 'Perda por competência',
                      'unit': 'pontos', 'dashboard_json_path': 'pages.high_performance.loss_by_competency',
                      'visualization': 'heatmap/barras'},
        'years': modulos_ano, 'historical': hist,
        'dashboard_files': [f'dashboard_enem_{ano}.json' for ano in ANOS],
    }
    csv_rows = linhas_csv(modulos_ano, hist)
    novos = {} if somente_modulo else {
        ano: atualizar_dashboard(antigos[ano], modulos_ano[i], modulos_ano, hist, gerado)
        for i, ano in enumerate(ANOS)
    }
    for ano, doc in novos.items():
        if doc['quality'].get('ind030_validation', {}).get('status') != 'ok':
            raise AssertionError(f'{ano}: bloco do IND-030 foi alterado')
        for schema in (raiz / '04_resultados_analises.schema.json',
                       raiz / 'docs' / '04_resultados_analises.schema.json'):
            if schema.is_file():
                try:
                    import jsonschema
                except ImportError:
                    break
                jsonschema.validate(doc, ler_json(schema))
                break
    json.dumps(modulo, allow_nan=False)
    for d in novos.values():
        json.dumps(d, allow_nan=False)

    out = raiz / 'outputs'
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out, prefix='.ind031_stage_') as staging:
        tmp = Path(staging)
        staged = []
        fmod, fcsv = tmp / destinos[0].name, tmp / destinos[1].name
        gravar_json(fmod, modulo)
        with fcsv.open('w', encoding='utf-8-sig', newline='') as f:
            wr = csv.DictWriter(f, fieldnames=list(csv_rows[0]), delimiter=';')
            wr.writeheader()
            wr.writerows(csv_rows)
        staged.extend(((fmod, destinos[0]), (fcsv, destinos[1])))
        for ano, doc in novos.items():
            temp = tmp / f'dashboard_enem_{ano}.json'
            gravar_json(temp, doc)
            staged.append((temp, dir_json / temp.name))
        for ano in antigos:
            arquivo = dir_json / f'dashboard_enem_{ano}.json'
            if hashlib.sha256(arquivo.read_bytes()).hexdigest() != hashes[ano]:
                raise RuntimeError(f'Dashboard {ano} alterado durante a execução; nenhuma saída gravada')
        # Snapshot dos arquivos que serão substituídos; recuperação se a gravação falhar.
        backup = {}
        for _, destino in staged:
            if destino.exists():
                bk = tmp / f'{len(backup)}_{destino.name}.bak'
                bk.write_bytes(destino.read_bytes())
                backup[destino] = bk
        concluido = []
        try:
            for src, dest in staged:
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(src, dest)
                concluido.append(dest)
        except Exception:
            for dest in reversed(concluido):
                if dest in backup:
                    os.replace(backup[dest], dest)
                else:
                    dest.unlink(missing_ok=True)
            raise
    print(f'IND-031 concluído: 224 recortes e {len(csv_rows)} linhas CSV; '
          + ('dashboards atualizados.' if novos else 'dashboards preservados.'), flush=True)
    return modulo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=Path(__file__).resolve().parents[2],
                    help='raiz do repositório; padrão = dois níveis acima do script')
    ap.add_argument('--bloco', type=int, default=100_000,
                    help='quantidade de linhas por bloco de leitura')
    ap.add_argument('--somente-modulo', action='store_true',
                    help='gera apenas CSV/JSON, sem atualizar os dashboards')
    ap.add_argument('--sobrescrever', action='store_true',
                    help='permite substituir arquivos do próprio IND-031')
    args = ap.parse_args()
    executar(args.base, args.bloco, args.somente_modulo, args.sobrescrever)


if __name__ == '__main__':
    main()
