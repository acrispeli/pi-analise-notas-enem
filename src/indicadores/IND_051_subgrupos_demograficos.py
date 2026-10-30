#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-051 — Subgrupos demográficos × nota da redação | PI IV — UNIVESP.

Catálogo ENEM 2019–2025 v2: pages.socioeconomic.demographics.
População POP_SOCIO_VALID, a mesma do IND-045.
Dimensões independentes: TP_SEXO, TP_FAIXA_ETARIA e TP_COR_RACA.
Métrica: N, percentual, média, mediana, Q1, Q3, IQR e desvio-padrão
populacional da nota total. Recortes: Brasil e 27 UFs da prova.

2019–2023: MICRODADOS_ENEM_<ano>.csv (uma linha contém atributos e notas).
2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv, join 1:1
      por NU_INSCRICAO em SQLite temporário, sem publicar identificadores.
2025: sem chave pública comum para associação socioeconômica × nota.

As 20 faixas etárias oficiais são agregadas em 10 grupos analíticos
sem sobreposição, além de ausência/inválido. Cor/raça código 6 só é válido
em 2021–2024. Sexo representa a variável publicada TP_SEXO, sem inferir
identidade de gênero; cor/raça é a declaração do participante.

A supressão opera separadamente em cada dimensão: uma categoria com N=1..29
em qualquer UF/BR é suprimida em todos os recortes do ano, com categoria
complementar global segura; se impossível, suprime-se toda a dimensão.
Status: draft até auditoria de privacidade cruzada e validação com dados reais.

Uso (na raiz do projeto):
  python src/indicadores/IND_051_subgrupos_demograficos.py --autoteste
  python src/indicadores/IND_051_subgrupos_demograficos.py --anos 2024 --sobrescrever
  python src/indicadores/IND_051_subgrupos_demograficos.py --sobrescrever
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd

import IND_045_tipo_escola_nota as ind45

ANOS = ind45.ANOS
UFS = ind45.UFS
NOTAS_COMP = ind45.NOTAS_COMP
CAMPOS_NOTAS = ('NU_NOTA_REDACAO', *NOTAS_COMP)
LIMIAR = ind45.LIMIAR
VARIAVEIS = ('TP_SEXO', 'TP_FAIXA_ETARIA', 'TP_COR_RACA')
SEM_RESPOSTA = 'SEM_RESPOSTA'
INVALIDO = 'CODIGO_NAO_RECONHECIDO'

CATEGORIAS = {
    'TP_SEXO': {
        'M': 'Masculino', 'F': 'Feminino',
        SEM_RESPOSTA: 'Sem informação', INVALIDO: 'Código não reconhecido',
    },
    'TP_FAIXA_ETARIA': {
        '1': 'Menor de 17 anos', '2': '17 anos', '3': '18 anos', '4': '19 anos',
        '5_9': '20 a 24 anos', '10_11': '25 a 30 anos',
        '12_13': '31 a 40 anos', '14_15': '41 a 50 anos',
        '16_17': '51 a 60 anos', '18_20': '61 anos ou mais',
        SEM_RESPOSTA: 'Sem informação', INVALIDO: 'Código não reconhecido',
    },
    'TP_COR_RACA': {
        '0': 'Não declarada', '1': 'Branca', '2': 'Preta',
        '3': 'Parda', '4': 'Amarela', '5': 'Indígena',
        '6': 'Não dispõe da informação (a partir de 2021)',
        SEM_RESPOSTA: 'Sem informação', INVALIDO: 'Código não reconhecido',
    },
}

CAMPOS_CSV = (
    'ano', 'uf', 'dimensao', 'codigo_categoria', 'descricao_categoria', 'ordem',
    'n_redacoes', 'percentual_total_validas', 'media', 'mediana', 'q1', 'q3',
    'iqr', 'desvio_padrao', 'suprimido', 'motivo_supressao',
)
ESTATS = ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')


def log(msg: str) -> None:
    print(msg, flush=True)


def texto_codigo(v: Any) -> str:
    if v is None:
        return ''
    txt = str(v).strip().upper()
    if txt in ('NAN', 'NULL', 'NONE', '<NA>'):
        return ''
    return txt


def numero_codigo(txt: str) -> int | None:
    if not re.fullmatch(r'\d+(?:[.,]0+)?', txt):
        return None
    return int(txt.split('.')[0].split(',')[0])


def codigo_demografico(v: Any, variavel: str, ano: int) -> str:
    """Valida códigos do dicionário antes de qualquer agregação."""
    if variavel not in VARIAVEIS:
        raise ValueError(f'Dimensão desconhecida: {variavel}')
    txt = texto_codigo(v)
    if not txt:
        return SEM_RESPOSTA
    if variavel == 'TP_SEXO':
        return txt if txt in ('M', 'F') else INVALIDO
    n = numero_codigo(txt)
    if n is None:
        return INVALIDO
    if variavel == 'TP_COR_RACA':
        permitido = range(0, 6) if ano < 2021 else range(0, 7)
        return str(n) if n in permitido else INVALIDO
    if n is None or n not in range(1, 21):
        return INVALIDO
    if n <= 4:
        return str(n)
    if n <= 9:
        return '5_9'
    if n <= 11:
        return '10_11'
    if n <= 13:
        return '12_13'
    if n <= 15:
        return '14_15'
    if n <= 17:
        return '16_17'
    return '18_20'


class Grupo:
    """Agrega histograma exato da nota, sem reter registros individuais."""
    def __init__(self) -> None:
        self.n = 0
        self.hist: Counter[float] = Counter()
        self.n_soma_divergente = 0

    def adicionar(self, notas: np.ndarray, comp: np.ndarray) -> None:
        if len(notas) != len(comp):
            raise ValueError('Notas e competências desalinhadas.')
        self.n += len(notas)
        if len(notas):
            valores, freqs = np.unique(notas, return_counts=True)
            self.hist.update({float(x): int(f) for x, f in zip(valores, freqs)})
            self.n_soma_divergente += int(np.count_nonzero(
                ~np.isclose(comp.sum(axis=1), notas, atol=1e-6, rtol=0)))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        self.hist.update(outro.hist)
        self.n_soma_divergente += outro.n_soma_divergente


def acumular(grupos: dict, validas: pd.DataFrame, ano: int) -> None:
    if validas.empty:
        return
    ufs = validas['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError(f'{ano}: SG_UF_PROVA ausente/inválida em redação válida.')
    notas = validas['__nota_total'].to_numpy(dtype='float64')
    competencias = validas[list(NOTAS_COMP)].to_numpy(dtype='float64')
    for dim in VARIAVEIS:
        codes = validas[dim].map(lambda x: codigo_demografico(x, dim, ano))
        indices = pd.DataFrame({'uf': ufs.to_numpy(), 'code': codes.to_numpy()})
        for (uf, code), positions in indices.groupby(['uf', 'code'], sort=False).indices.items():
            grupos[(dim, str(uf), str(code))].adicionar(notas[positions], competencias[positions])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if ano not in range(2019, 2024):
        raise ValueError('Mesma linha somente para 2019–2023.')
    grupos = defaultdict(Grupo)
    total = 0
    cols = ['SG_UF_PROVA', *VARIAVEIS, 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]
    for parte in ind45.ler_blocos(arquivo, cols, bloco):
        validas = ind45.selecionar_validas(parte)
        total += len(validas)
        acumular(grupos, validas, ano)
    return dict(grupos), total, {
        'metodo': 'mesma_linha', 'n_redacoes_validas_processadas': total,
        'variaveis': list(VARIAVEIS),
    }


def ids_inscricao(df: pd.DataFrame, fonte: str) -> list[str]:
    ids = df['NU_INSCRICAO'].astype('string').str.strip().tolist()
    if any(not x or x.upper() in ('NAN', 'NULL', 'NONE', '<NA>') for x in ids):
        raise ValueError(f'{fonte}: NU_INSCRICAO ausente/inválida.')
    return ids


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Junção obrigatória 1:1, validando duplicatas e vínculo de 100% das válidas."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind051_') as pasta:
        db = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes('
                       'id TEXT PRIMARY KEY, uf TEXT NOT NULL, sexo TEXT, idade TEXT, raca TEXT) '
                       'WITHOUT ROWID')
            db.execute('CREATE TABLE vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ind45.ler_blocos(
                    participantes, ['NU_INSCRICAO', 'SG_UF_PROVA', *VARIAVEIS], bloco):
                ids = ids_inscricao(parte, 'PARTICIPANTES_2024')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: UF ausente/inválida.')
                attrs = [parte[c].astype('string').fillna('').str.strip().tolist()
                         for c in VARIAVEIS]
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?,?,?)',
                                   zip(ids, ufs, *attrs))
                except sqlite3.IntegrityError as err:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from err
                n_participantes += len(ids)
            db.commit()
            log(f'  2024: {n_participantes:,} participantes indexados.')
            n_validas = 0
            for parte in ind45.ler_blocos(
                    competencias, ['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS], bloco):
                validas = ind45.selecionar_validas(parte)
                n_validas += len(validas)
                if validas.empty:
                    continue
                ids = ids_inscricao(validas, 'COMPETENCIAS_REDACAO_2024')
                try:
                    db.executemany('INSERT INTO vistas VALUES (?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as err:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: redação válida duplicada.') from err
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                encontrados = db.execute('''
                    SELECT l.pos, p.uf, p.sexo, p.idade, p.raca
                    FROM lote AS l JOIN participantes AS p ON p.id = l.id
                ''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                attrs2 = [None] * len(ids)
                for pos, uf, sexo, idade, raca in encontrados:
                    attrs2[pos] = (uf, sexo, idade, raca)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [a[0] for a in attrs2]
                for i, dim in enumerate(VARIAVEIS, start=1):
                    validas[dim] = [a[i] for a in attrs2]
                acumular(grupos, validas, 2024)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO', 'n_participantes_indexados': n_participantes,
                'n_redacoes_validas_vinculadas': n_validas, 'n_validas_sem_correspondencia': 0,
                'inscricoes_unicas_participantes': True,
                'inscricoes_unicas_redacoes_validas': True,
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    nacional = defaultdict(Grupo)
    for (dim, uf, cod), grupo in grupos.items():
        if dim not in CATEGORIAS or uf not in UFS or cod not in CATEGORIAS[dim]:
            raise ValueError(f'Grupo desconhecido: {dim}/{uf}/{cod}')
        nacional[(dim, 'BR', cod)].combinar(grupo)
    return {**grupos, **nacional}


def obter(grupos: dict, dim: str, uf: str, code: str) -> Grupo:
    return grupos.get((dim, uf, code), Grupo())


def ler_referencia(base: Path, caminho: Path | None = None) -> dict:
    arquivo = caminho or (base / 'outputs' / 'json' / 'IND_045_tipo_escola_nota.json')
    if caminho is not None and not arquivo.is_absolute():
        arquivo = base / arquivo
    if not arquivo.is_file():
        raise FileNotFoundError(f'IND-045 necessário para conciliação: {arquivo}')
    ref = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if ref.get('indicator_id') != 'IND-045' or ref.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência deve ser IND-045/POP_SOCIO_VALID.')
    return ref


def conferir_montar(ano: int, grupos: dict, n_validas: int, ref: dict) -> tuple[dict, dict]:
    ref_ano = ref.get('years', {}).get(str(ano), {})
    if ref_ano.get('status') != 'ok' or ref_ano.get('n_brasil') != n_validas:
        raise ValueError(f'{ano}: IND-045 não disponível ou N Brasil divergente.')
    ref_ufs = ref_ano.get('recortes', {})
    if set(ref_ufs) != {'BR', *UFS}:
        raise ValueError(f'{ano}: IND-045 sem BR + 27 UFs.')
    ref_div = ref_ano.get('validacao', {}).get('n_soma_competencias_divergente')
    if ref_div is None:
        raise ValueError(f'{ano}: IND-045 sem diagnóstico de competências.')
    for dim in VARIAVEIS:
        if sum(obter(grupos, dim, 'BR', c).n for c in CATEGORIAS[dim]) != n_validas:
            raise ValueError(f'{ano}/{dim}: N Brasil diverge IND-045.')
        divergencias = sum(obter(grupos, dim, 'BR', c).n_soma_divergente
                           for c in CATEGORIAS[dim])
        if divergencias != ref_div:
            raise ValueError(f'{ano}/{dim}: divergências C1–C5 diferem IND-045.')
    for uf in ('BR', *UFS):
        n_ref = ref_ufs[uf]['n_pop_socio_valid']
        for dim in VARIAVEIS:
            total = sum(obter(grupos, dim, uf, c).n for c in CATEGORIAS[dim])
            if total != n_ref:
                raise ValueError(f'{ano}/{uf}/{dim}: N {total} difere IND-045 {n_ref}.')
            hist = Counter()
            for cod in CATEGORIAS[dim]:
                grupo = obter(grupos, dim, uf, cod)
                if sum(grupo.hist.values()) != grupo.n:
                    raise ValueError(f'{ano}/{uf}/{dim}/{cod}: histograma difere N.')
                hist.update(grupo.hist)
            ref_cats = ref_ufs[uf]['categories']
            if n_ref and all(not x['suprimido'] for x in ref_cats):
                media_ref = math.fsum(x['n_redacoes'] * x['media'] for x in ref_cats
                                      if x['n_redacoes']) / n_ref
                media_calc = math.fsum(score * qtd for score, qtd in hist.items()) / total
                if not math.isclose(media_ref, media_calc, abs_tol=.00015, rel_tol=0):
                    raise ValueError(f'{ano}/{uf}/{dim}: média total difere IND-045.')

    # Supressões independentes por margem demográfica; status permanece draft.
    supressoes = {}
    recortes = {}
    total_suprimidos = 0
    for dim in VARIAVEIS:
        categorias = CATEGORIAS[dim]
        pequenos = {cod for cod in categorias if any(
            0 < obter(grupos, dim, uf, cod).n < LIMIAR for uf in ('BR', *UFS))}
        motivos = {cod: 'primaria_grupo_pequeno_em_alguma_uf' for cod in pequenos}
        if pequenos:
            afetadas = [uf for uf in ('BR', *UFS) if any(
                obter(grupos, dim, uf, cod).n > 0 for cod in pequenos)]
            candidatos = [cod for cod in reversed(tuple(categorias)) if cod not in pequenos
                          and obter(grupos, dim, 'BR', cod).n >= LIMIAR
                          and all(obter(grupos, dim, uf, cod).n >= LIMIAR for uf in afetadas)]
            if candidatos:
                motivos[candidatos[0]] = 'complementar_contra_inferencia_por_totais'
            else:
                for cod in categorias:
                    motivos.setdefault(cod, 'complementar_sem_categoria_segura')
        supressoes[dim] = motivos
        for uf in ('BR', *UFS):
            n_uf = ref_ufs[uf]['n_pop_socio_valid']
            if uf not in recortes:
                recortes[uf] = {'uf': uf, 'population': 'POP_SOCIO_VALID',
                               'n_pop_socio_valid': n_uf, 'dimensoes': {},
                               'status_publicacao': 'draft_privacidade_cruzada_pendente'}
            cats = []
            for ordem, (cod, descricao) in enumerate(categorias.items()):
                grupo = obter(grupos, dim, uf, cod)
                motivo = motivos.get(cod)
                oculto = motivo is not None
                est = (ind45.estatisticas(grupo.hist, grupo.n) if not oculto else
                       {campo: None for campo in ESTATS})
                cats.append({
                    'codigo_categoria': cod, 'descricao_categoria': descricao,
                    'ordem': ordem, 'n_redacoes': None if oculto else grupo.n,
                    'percentual_total_validas': None if oculto or n_uf == 0 else round(
                        100 * grupo.n / n_uf, 6),
                    **est, 'suprimido': oculto, 'motivo_supressao': motivo,
                })
                total_suprimidos += int(oculto)
            recortes[uf]['dimensoes'][dim] = {'variavel_origem': dim, 'categories': cats}
    return recortes, {
        'referencia_populacao': 'IND-045', 'n_pop_socio_valid_brasil': n_validas,
        'n_por_uf_e_brasil_conferido': True, 'soma_ufs_conferida': True,
        'medias_totais_conferidas_quando_referencia_sem_supressao': True,
        'divergencias_conferidas_com_ind045': True, 'histogramas_reconciliados': True,
        'categorias_suprimidas_globalmente_por_dimensao': supressoes,
        'n_celulas_geograficas_suprimidas': total_suprimidos,
        'revisao_privacidade_cruzada_pendente': True,
    }


def linhas_csv(todos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(todos.items(), key=lambda par: int(par[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            for dim in VARIAVEIS:
                for cat in obj['recortes'][uf]['dimensoes'][dim]['categories']:
                    linhas.append({
                        'ano': int(ano), 'uf': uf, 'dimensao': dim,
                        'codigo_categoria': cat['codigo_categoria'],
                        'descricao_categoria': cat['descricao_categoria'],
                        'ordem': cat['ordem'], 'n_redacoes': cat['n_redacoes'],
                        'percentual_total_validas': cat['percentual_total_validas'],
                        **{x: cat[x] for x in ESTATS},
                        'suprimido': cat['suprimido'],
                        'motivo_supressao': cat['motivo_supressao'],
                    })
    return linhas


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                'w', encoding='utf-8-sig', newline='', dir=caminho.parent,
                prefix=caminho.name + '.', suffix='.tmp', delete=False) as fh:
            temp = Path(fh.name)
            writer = csv.DictWriter(fh, fieldnames=CAMPOS_CSV, delimiter=';',
                                    extrasaction='raise')
            writer.writeheader()
            writer.writerows(linhas)
        temp.replace(caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def preparar_dashboards(saida: Path, novos: dict[str, dict]) -> list[tuple[Path, dict]]:
    preparados = []
    for ano, obj in sorted(novos.items(), key=lambda par: int(par[0])):
        if obj['status'] != 'ok':
            continue
        caminho = saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            log(f'  Dashboard {ano} não encontrado; somente módulo.')
            continue
        doc = json.loads(caminho.read_text(encoding='utf-8-sig'))
        socio = doc.get('pages', {}).get('socioeconomic')
        if not isinstance(socio, dict):
            raise ValueError(f'{caminho.name}: pages.socioeconomic ausente.')
        if socio.get('school_type_total', {}).get('indicator_id') != 'IND-045':
            raise ValueError(f'{caminho.name}: IND-045 necessário antes do IND-051.')
        socio['demographics'] = {
            'indicator_id': 'IND-051', 'status': 'draft', 'year': int(ano),
            'population': 'POP_SOCIO_VALID', 'national': obj['recortes']['BR'],
            'states': {uf: obj['recortes'][uf] for uf in UFS},
            'method': 'TP_SEXO, TP_FAIXA_ETARIA (10 grupos agregados), TP_COR_RACA; nota total',
            'privacy_note': 'Supressão de grupos <30, complementar; revisão cruzada pendente.',
        }
        doc.setdefault('quality', {})['ind051_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-051: relações de sexo, faixa etária e cor/raça com notas são '
                 'descritivas e não causais; status draft até revisão de privacidade cruzada.')
        avisos = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in avisos:
            avisos.append(aviso)
        preparados.append((caminho, doc))
    return preparados


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_path: Path | None = None,
             escolhas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    json_dest = saida / 'outputs' / 'json' / 'IND_051_subgrupos_demograficos.json'
    csv_dest = saida / 'outputs' / 'indicadores' / 'IND_051_subgrupos_demograficos.csv'
    if not sobrescrever and (json_dest.exists() or csv_dest.exists()):
        raise FileExistsError('IND-051 já existe; use --sobrescrever.')
    ref = ler_referencia(base, referencia_path)
    necessarias = set()
    for ano in anos:
        if ano < 2024:
            necessarias.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            necessarias.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = ind45.localizar_fontes(base, necessarias, escolhas)
    faltantes = sorted(necessarias - set(fontes))
    if faltantes:
        raise FileNotFoundError(f'Fontes ausentes: {faltantes}')
    anteriores = {}
    if sobrescrever and json_dest.exists():
        prev = json.loads(json_dest.read_text(encoding='utf-8-sig'))
        if prev.get('indicator_id') != 'IND-051':
            raise ValueError('JSON anterior não pertence ao IND-051.')
        anteriores = prev.get('years', {})
    todos, novos = dict(anteriores), {}
    for ano in anos:
        log(f'IND-051 | {ano} — subgrupos demográficos × nota...')
        if ano == 2025:
            if ref.get('years', {}).get('2025', {}).get('status') != 'indisponivel':
                raise ValueError('IND-045/2025 não confirma a indisponibilidade de vínculo.')
            obj = {'ano': ano, 'status': 'indisponivel', 'reason': (
                'Sem chave pública comum entre dados demográficos e nota da redação '
                'de 2025 nas fontes utilizadas.'), 'recortes': {}}
        else:
            if ano == 2024:
                grupos, n_validas, diag = ler_2024(
                    fontes['PARTICIPANTES_2024.CSV'],
                    fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            else:
                grupos, n_validas, diag = ler_mesma_linha(
                    fontes[f'MICRODADOS_ENEM_{ano}.CSV'], ano, bloco)
            recortes, val = conferir_montar(ano, criar_brasil(grupos), n_validas, ref)
            obj = {'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
                   'n_brasil': n_validas, 'variaveis_origem': list(VARIAVEIS),
                   'diagnostico_fonte': diag, 'validacao': val, 'recortes': recortes}
            log(f'  N Brasil={n_validas:,}; células suprimidas='
                f'{val["n_celulas_geograficas_suprimidas"]}; IND-045 conferido.')
        todos[str(ano)] = obj
        novos[str(ano)] = obj
    modulo = {
        'indicator_id': 'IND-051', 'titulo': 'Subgrupos demográficos',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, v in todos.items() if v.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'variables': list(VARIAVEIS), 'categories': CATEGORIAS,
            'age_grouping': ('Códigos 1,2,3,4 isolados; 5–9=20–24; 10–11=25–30; '
                             '12–13=31–40; 14–15=41–50; 16–17=51–60; 18–20=61+.'),
            'race_code_6': 'válido apenas em 2021–2024',
            'population': 'TP_STATUS_REDACAO=1, total 0..1000 e C1–C5 0..200',
            'statistics': 'N, percentual, média, mediana, Q1, Q3, IQR e DP populacional',
            'quantiles': 'Hyndman–Fan tipo 7, histograma exato do IND-045',
            'reference': 'IND-045 para N UF/BR, soma C1–C5 e média total',
            'join_2024': 'NU_INSCRICAO única, 100% das redações válidas vinculadas',
            '2025': 'indisponível para associação demográfica × redação',
            'privacy': 'N=1..29 suprimido globalmente por margem + complementar, draft',
            'notes': [
                'Sexo é TP_SEXO conforme dicionário, não identifica identidade de gênero.',
                'Cor/raça é declaração do participante, não inferência de terceiros.',
                'Sexo, idade e cor/raça são margens separadas, não interseções.',
                'A UF é de aplicação da prova, não necessariamente de residência.',
                'Ausências e códigos inválidos não são imputados.',
                'Diferenças descritivas não são efeitos causais.',
                'Revisão de privacidade cruzada necessária antes da publicação.',
            ],
        },
        'years': todos,
    }
    dashboards = [] if somente_modulo else preparar_dashboards(saida, novos)
    ind45.salvar_json(json_dest, modulo)
    salvar_csv(csv_dest, linhas_csv(todos))
    for caminho, doc in dashboards:
        ind45.salvar_json(caminho, doc)
        log(f'  Dashboard {caminho.name}: demographics integrado.')
    log(f'IND-051 concluído (draft): {json_dest} | {csv_dest}')
    return modulo


def autoteste() -> None:
    """Testa valores contra NumPy e múltiplos casos de auditoria com dados sintéticos."""
    rng = np.random.default_rng(51)
    for x, want in [('F', 'F'), (' m ', 'M'), ('', SEM_RESPOSTA),
                    ('X', INVALIDO)]:
        assert codigo_demografico(x, 'TP_SEXO', 2024) == want
    for x, want in [('1', '1'), ('2.0', '2'), ('04', '4'), ('5', '5_9'),
                    ('9', '5_9'), ('10', '10_11'), ('11', '10_11'),
                    ('12', '12_13'), ('13', '12_13'), ('14', '14_15'),
                    ('15', '14_15'), ('16', '16_17'), ('17', '16_17'),
                    ('18', '18_20'), ('20', '18_20'), ('0', INVALIDO),
                    ('21', INVALIDO), ('1.5', INVALIDO),
                    ('', SEM_RESPOSTA)]:
        assert codigo_demografico(x, 'TP_FAIXA_ETARIA', 2024) == want
    assert codigo_demografico('6', 'TP_COR_RACA', 2019) == INVALIDO
    assert codigo_demografico('6', 'TP_COR_RACA', 2020) == INVALIDO
    assert codigo_demografico('6', 'TP_COR_RACA', 2021) == '6'
    assert codigo_demografico('6', 'TP_COR_RACA', 2024) == '6'
    assert codigo_demografico('0', 'TP_COR_RACA', 2024) == '0'
    assert codigo_demografico('7', 'TP_COR_RACA', 2024) == INVALIDO
    for _ in range(12):
        notas = rng.choice(np.arange(0, 1001, 20).astype(float), size=100)
        est = ind45.estatisticas(Counter(notas), len(notas))
        assert abs(est['media'] - notas.mean()) < .00006
        assert abs(est['mediana'] - np.median(notas)) < .00006
        assert abs(est['q1'] - np.quantile(notas, .25)) < .00006
        assert abs(est['q3'] - np.quantile(notas, .75)) < .00006
        assert abs(est['desvio_padrao'] - notas.std(ddof=0)) < .00006

    with tempfile.TemporaryDirectory(prefix='teste_ind051_') as pasta:
        base = Path(pasta)
        raw, out = base / 'raw', base / 'outputs' / 'json'
        raw.mkdir()
        out.mkdir(parents=True)
        dados = []
        for idx_uf, uf in enumerate(UFS):
            for k in range(180):
                sexo = 'M' if k < 90 else ('F' if k < 179 else '')
                # Misturar grupos amplos e pequenos para testar supressão.
                idade = (str(3 if k < 32 else 4 if k < 64 else 7 if k < 103
                             else 11 if k < 135 else 15 if k < 166 else 20))
                raca = (str(1 if k < 43 else 2 if k < 83 else 3 if k < 135
                            else 4 if k < 150 else 5 if k < 160 else 0 if k < 173
                            else 6 if k < 177 else 9))
                comps = [float(20 * int(rng.integers(3, 10))) for _ in range(5)]
                dados.append({
                    'NU_INSCRICAO': str(951000000000 + idx_uf * 180 + k),
                    'SG_UF_PROVA': uf, 'TP_SEXO': sexo,
                    'TP_FAIXA_ETARIA': idade, 'TP_COR_RACA': raca,
                    'TP_STATUS_REDACAO': '1', 'NU_NOTA_REDACAO': str(sum(comps)),
                    **{c: str(comps[i]) for i, c in enumerate(NOTAS_COMP)},
                })
        df = pd.DataFrame(dados)
        df.drop(columns=['NU_INSCRICAO']).to_csv(
            raw / 'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        df[['NU_INSCRICAO', 'SG_UF_PROVA', *VARIAVEIS]].iloc[::-1].to_csv(
            raw / 'PARTICIPANTES_2024.csv', sep=';', index=False)
        df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].to_csv(
            raw / 'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        ref = {'indicator_id': 'IND-045', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano in (2019, 2024):
            rec = {}
            for uf in ('BR', *UFS):
                parte = df if uf == 'BR' else df.loc[df['SG_UF_PROVA'] == uf]
                rec[uf] = {'n_pop_socio_valid': len(parte), 'categories': [{
                    'suprimido': False, 'n_redacoes': len(parte),
                    'media': round(pd.to_numeric(parte['NU_NOTA_REDACAO']).mean(), 4),
                }]}
            ref['years'][str(ano)] = {
                'status': 'ok', 'n_brasil': len(df), 'recortes': rec,
                'validacao': {'n_soma_competencias_divergente': 0},
            }
            ind45.salvar_json(out / f'dashboard_enem_{ano}.json', {
                'pages': {'socioeconomic': {
                    'school_type_total': {'indicator_id': 'IND-045'},
                    'sentinela': 'preservar'}},
                'quality': {'sentinela': 1}, 'meta': {'warnings': []},
            })
        ref['years']['2025'] = {'status': 'indisponivel'}
        ind45.salvar_json(out / 'IND_045_tipo_escola_nota.json', ref)
        result = executar(base, base, (2019, 2024, 2025), 61, True, False)
        assert result['years']['2025']['status'] == 'indisponivel'
        assert result['anos_disponiveis'] == [2019, 2024]
        for ano in ('2019', '2024'):
            obj = result['years'][ano]
            assert obj['n_brasil'] == 4860
            assert obj['validacao']['n_por_uf_e_brasil_conferido']
            assert len(obj['recortes']) == 28
            for uf in ('BR', *UFS):
                rec = obj['recortes'][uf]
                assert rec['n_pop_socio_valid'] == (4860 if uf == 'BR' else 180)
                for dim in VARIAVEIS:
                    cats = rec['dimensoes'][dim]['categories']
                    assert len(cats) == len(CATEGORIAS[dim])
                    for cat in cats:
                        if cat['suprimido']:
                            assert all(cat[k] is None for k in ('n_redacoes', 'media', 'mediana', 'q1'))
                        else:
                            assert cat['n_redacoes'] == 0 or cat['n_redacoes'] >= LIMIAR
            for dim in VARIAVEIS:
                motivos = obj['validacao']['categorias_suprimidas_globalmente_por_dimensao'][dim]
                assert not motivos
            dashboard = json.loads((out / f'dashboard_enem_{ano}.json').read_text())
            assert dashboard['pages']['socioeconomic']['sentinela'] == 'preservar'
            assert dashboard['pages']['socioeconomic']['demographics']['indicator_id'] == 'IND-051'
            assert dashboard['quality']['sentinela'] == 1
        with (base / 'outputs' / 'indicadores' / 'IND_051_subgrupos_demograficos.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            linhas = list(csv.DictReader(fh, delimiter=';'))
        assert len(linhas) == 2 * 28 * sum(map(len, CATEGORIAS.values()))
        assert all('NU_INSCRICAO' not in linha for linha in linhas)
        assert all(not linha['n_redacoes'] and not linha['media']
                   for linha in linhas if linha['suprimido'] == 'True')
        # Verificar média, quartis e desvios em grupo grande da UF SP.
        amostra = df.loc[(df['SG_UF_PROVA'] == 'SP') & (df['TP_SEXO'] == 'M')]
        notas = pd.to_numeric(amostra['NU_NOTA_REDACAO']).to_numpy(dtype=float)
        cat = next(x for x in result['years']['2019']['recortes']['SP']
                   ['dimensoes']['TP_SEXO']['categories'] if x['codigo_categoria'] == 'M')
        assert not cat['suprimido']
        assert cat['n_redacoes'] == len(notas)
        assert abs(cat['media'] - notas.mean()) < .00006
        assert abs(cat['mediana'] - np.median(notas)) < .00006
        assert abs(cat['q1'] - np.quantile(notas, .25)) < .00006
        assert abs(cat['q3'] - np.quantile(notas, .75)) < .00006
        assert abs(cat['desvio_padrao'] - notas.std(ddof=0)) < .00006
        g, n, _ = ler_mesma_linha(raw / 'MICRODADOS_ENEM_2019.csv', 2019, 39)
        ruim = json.loads(json.dumps(ref))
        ruim['years']['2019']['recortes']['SP']['n_pop_socio_valid'] += 1
        try:
            conferir_montar(2019, criar_brasil(g), n, ruim)
        except ValueError as err:
            assert 'difere IND-045' in str(err)
        else:
            raise AssertionError('Referência IND-045 adulterada não foi detectada.')
        # Junção independente da ordem e tamanho do bloco.
        g1, n1, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 47)
        g2, n2, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 511)
        assert n1 == n2 == len(df)
        assert set(g1) == set(g2)
        assert all(g1[k].hist == g2[k].hist and g1[k].n == g2[k].n for k in g1)
        # Erro de redação sem vínculo.
        sem_vinculo = df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].copy()
        sem_vinculo.loc[0, 'NU_INSCRICAO'] = 'NAO_EXISTE'
        sem_vinculo.to_csv(raw/'SEM_VINCULO.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'SEM_VINCULO.csv', 83)
        except ValueError as err:
            assert 'sem vínculo' in str(err)
        else:
            raise AssertionError('Não detectou redação sem vínculo.')
        dup_notas = pd.concat([df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]],
                               df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].iloc[[0]]])
        dup_notas.to_csv(raw/'DUP_REDACOES.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'DUP_REDACOES.csv', 83)
        except ValueError as err:
            assert 'duplicada' in str(err)
        else:
            raise AssertionError('Não detectou redação duplicada.')
        dup_part = pd.concat([df[['NU_INSCRICAO', 'SG_UF_PROVA', *VARIAVEIS]],
                              df[['NU_INSCRICAO', 'SG_UF_PROVA', *VARIAVEIS]].iloc[[0]]])
        dup_part.to_csv(raw/'DUP_PARTICIPANTES.csv', sep=';', index=False)
        try:
            ler_2024(raw/'DUP_PARTICIPANTES.csv',
                     raw/'COMPETENCIAS_REDACAO_2024.csv', 83)
        except ValueError as err:
            assert 'duplicada' in str(err)
        else:
            raise AssertionError('Não detectou inscrição duplicada.')
        # Grupo 6 de cor/raça é válido em 2024, não em 2019.
        grupos_2019, _, _ = ler_mesma_linha(raw/'MICRODADOS_ENEM_2019.csv', 2019, 57)
        grupos_2024, _, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                                      raw/'COMPETENCIAS_REDACAO_2024.csv', 57)
        assert obter(criar_brasil(grupos_2019), 'TP_COR_RACA', 'BR', '6').n == 0
        assert obter(criar_brasil(grupos_2024), 'TP_COR_RACA', 'BR', '6').n == 27*4
        # Caso extremo real: em SP só existem duas categorias de 2 e 3
        # registros, sem qualquer alternativa segura para complemento.
        # Demais UFs têm 100 registros divididos entre as mesmas categorias.
        # Os 3 marginais compartilham N de cada UF, tal como num universo real.
        extremos = defaultdict(Grupo)
        for uf in UFS:
            for dim in VARIAVEIS:
                cod1, cod2 = list(CATEGORIAS[dim])[:2]
                qtd1, qtd2 = (2, 3) if uf == 'SP' else (50, 50)
                for cod, qtd in ((cod1, qtd1), (cod2, qtd2)):
                    extremos[(dim, uf, cod)].adicionar(
                        np.full(qtd, 600.), np.full((qtd, 5), 120.))
        extremos = criar_brasil(extremos)
        ref2 = json.loads(json.dumps(ref))
        for uf in ('BR', *UFS):
            total = sum(obter(extremos, 'TP_SEXO', uf, c).n
                        for c in CATEGORIAS['TP_SEXO'])
            ref2['years']['2019']['recortes'][uf] = {
                'n_pop_socio_valid': total, 'categories': [
                    {'suprimido': False, 'n_redacoes': total, 'media': 600.}],
            }
        n_ext = sum(obter(extremos, 'TP_SEXO', 'BR', c).n
                    for c in CATEGORIAS['TP_SEXO'])
        ref2['years']['2019']['n_brasil'] = n_ext
        rec_ext, qa_ext = conferir_montar(2019, extremos, n_ext, ref2)
        for dim in VARIAVEIS:
            motivos = qa_ext['categorias_suprimidas_globalmente_por_dimensao'][dim]
            assert not motivos
            assert all(not x['suprimido'] for x in rec_ext['SP']['dimensoes'][dim]['categories'])
            assert all(not x['suprimido'] for x in rec_ext['BR']['dimensoes'][dim]['categories'])
    log('AUTOTESTE IND-051 APROVADO: códigos/anos, N Brasil/UF, estatísticas, '
        'supressão, junção, duplicações, vínculo, CSV/JSON e indisponibilidade 2025.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-051: Subgrupos demográficos × redação')
    parser.add_argument('--base', type=Path, default=ind45.raiz_projeto())
    parser.add_argument('--saida', type=Path, default=ind45.raiz_projeto())
    parser.add_argument('--referencia-ind045', type=Path, default=None)
    parser.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    parser.add_argument('--bloco', type=int, default=100_000)
    parser.add_argument('--sobrescrever', action='store_true')
    parser.add_argument('--somente-modulo', action='store_true')
    parser.add_argument('--participantes-2024', type=Path, default=None)
    parser.add_argument('--competencias-2024', type=Path, default=None)
    parser.add_argument('--autoteste', action='store_true')
    args = parser.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(ano not in ANOS for ano in anos):
        parser.error('--anos deve conter somente 2019 a 2025.')
    if args.bloco < 1:
        parser.error('--bloco deve ser >=1.')
    escolhas = {}
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.referencia_ind045, escolhas)
    except (OSError, ValueError, KeyError, TypeError,
            sqlite3.DatabaseError, json.JSONDecodeError) as err:
        print(f'ERRO IND-051: {err}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
