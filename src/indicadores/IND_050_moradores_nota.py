#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-050 — Moradores no domicílio × nota da redação | PI IV — UNIVESP.

Catálogo ENEM 2019–2025 v2, pages.socioeconomic.household_size.
População POP_SOCIO_VALID do IND-045; indicador descritivo, não causal.
Q005: número de moradores (inclui participante), códigos 1–20 em 2019–2024.
Faixas fixas 1, 2, 3, 4, 5–6, 7–9, 10–20; ausente e inválido à parte.
Não interpretar 20 como '20 ou mais' sem evidência de top-code.
2019–2023: MICRODADOS_ENEM_<ano>.csv, mesma linha.
2024: PARTICIPANTES_2024 + COMPETENCIAS_REDACAO_2024, por NU_INSCRICAO
      única, em SQLite temporário, sem expor IDs nos agregados.
2025: vínculo socioeconômico × nota indisponível nas fontes do projeto.

Outputs: outputs/json/IND_050_moradores_nota.json,
         outputs/indicadores/IND_050_moradores_nota.csv,
         outputs/json/dashboard_enem_<ano>.json (household_size).

Estado DRAFT até processamento real, conferência e privacidade cruzada.
Proteção: N=1..29 por categoria em qualquer UF -> supressão nacional +
por UF da categoria; complementar segura em todas as UFs afetadas, ou
supressão de todas as categorias se não houver alternativa.

Comandos na raiz do repositório:
  python src/indicadores/IND_050_moradores_nota.py --autoteste
  python src/indicadores/IND_050_moradores_nota.py --anos 2024 --sobrescrever
  python src/indicadores/IND_050_moradores_nota.py --sobrescrever
Requer IND_045_tipo_escola_nota.py e outputs/json/IND_045_tipo_escola_nota.json.
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
CATEGORIAS = {
    '1': '1 morador',
    '2': '2 moradores',
    '3': '3 moradores',
    '4': '4 moradores',
    '5_6': '5 a 6 moradores',
    '7_9': '7 a 9 moradores',
    '10_20': '10 a 20 (códigos disponíveis)',
    'SEM_RESPOSTA': 'Não informou',
    'CODIGO_NAO_RECONHECIDO': 'Código não reconhecido',
}
FAIXAS_NUMERICAS = ('1', '2', '3', '4', '5_6', '7_9', '10_20')
CAMPOS_CSV = (
    'ano', 'uf', 'variavel_origem', 'codigo_faixa_moradores',
    'descricao_categoria', 'ordem', 'n_redacoes', 'percentual_total_validas',
    'media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'suprimido', 'motivo_supressao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def faixa_moradores(valor: Any) -> str:
    """Agrupa códigos numéricos válidos, sem converter valores fracionários.

    Aceita 01 e 1.0 (códigos numericamente integrais). Não transforma
    20 em '20+', nem aceita 0, 21, negativo, fração ou texto arbitrário.
    """
    txt = '' if valor is None else str(valor).strip()
    if not txt or txt.upper() in ('NAN', 'NULL', 'NONE', '<NA>'):
        return 'SEM_RESPOSTA'
    if not re.fullmatch(r'\d+(?:[.,]0+)?', txt):
        return 'CODIGO_NAO_RECONHECIDO'
    codigo = int(txt.split('.')[0].split(',')[0])
    if not 1 <= codigo <= 20:
        return 'CODIGO_NAO_RECONHECIDO'
    if codigo <= 4:
        return str(codigo)
    if codigo <= 6:
        return '5_6'
    if codigo <= 9:
        return '7_9'
    return '10_20'


class Grupo:
    """Histograma exato da nota total; não retém registros individuais."""
    def __init__(self) -> None:
        self.n = 0
        self.hist: Counter[float] = Counter()
        self.n_soma_divergente = 0

    def adicionar(self, notas: np.ndarray, competencias: np.ndarray) -> None:
        if len(notas) != len(competencias):
            raise ValueError('Nota total e competências desalinhadas.')
        self.n += len(notas)
        if not len(notas):
            return
        valores, frequencias = np.unique(notas, return_counts=True)
        self.hist.update({float(v): int(n) for v, n in zip(valores, frequencias)})
        self.n_soma_divergente += int(np.count_nonzero(
            ~np.isclose(competencias.sum(axis=1), notas, atol=1e-6, rtol=0)))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        self.hist.update(outro.hist)
        self.n_soma_divergente += outro.n_soma_divergente


def acumular(grupos: dict, validas: pd.DataFrame, ano: int) -> None:
    if validas.empty:
        return
    ufs = validas['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError(f'{ano}: SG_UF_PROVA ausente ou inválida em redação válida.')
    notas = validas['__nota_total'].to_numpy(dtype='float64')
    competencias = validas[list(NOTAS_COMP)].to_numpy(dtype='float64')
    codigos = validas['Q005'].map(faixa_moradores)
    indices = pd.DataFrame({'uf': ufs.to_numpy(), 'faixa': codigos.to_numpy()})
    for (uf, faixa), posicoes in indices.groupby(['uf', 'faixa'], sort=False).indices.items():
        grupos[(str(uf), str(faixa))].adicionar(notas[posicoes], competencias[posicoes])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if not (2019 <= ano <= 2023):
        raise ValueError('Formato de arquivo único permitido apenas para 2019–2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    colunas = ['SG_UF_PROVA', 'Q005', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]
    for parte in ind45.ler_blocos(arquivo, colunas, bloco):
        validas = ind45.selecionar_validas(parte)
        n_validas += len(validas)
        acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {
        'metodo': 'mesma_linha', 'variavel_origem': 'Q005',
        'n_redacoes_validas_processadas': n_validas,
    }


def ids_inscricao(df: pd.DataFrame, fonte: str) -> list[str]:
    ids = df['NU_INSCRICAO'].astype('string').str.strip().tolist()
    if any(not x or x.upper() in ('NAN', 'NONE', 'NULL', '<NA>') for x in ids):
        raise ValueError(f'{fonte}: NU_INSCRICAO vazia/inválida.')
    return ids


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Junção 1:1 em SQLite, com controle de unicidade e 100% de vínculo."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind050_') as pasta:
        db = sqlite3.connect(str(Path(pasta)/'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL, '
                       'q005 TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE redacoes_vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ind45.ler_blocos(
                    participantes, ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q005'], bloco):
                ids = ids_inscricao(parte, 'PARTICIPANTES_2024')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: UF da prova ausente/inválida.')
                q005 = parte['Q005'].astype('string').str.strip().tolist()
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?)',
                                   zip(ids, ufs, q005))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from erro
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
                    db.executemany('INSERT INTO redacoes_vistas VALUES (?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: redação válida duplicada.') from erro
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                encontrados = db.execute('''
                    SELECT l.pos, p.uf, p.q005
                    FROM lote AS l JOIN participantes AS p ON p.id = l.id
                ''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                attrs = [None] * len(ids)
                for pos, uf, q005 in encontrados:
                    attrs[pos] = (uf, q005)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [a[0] for a in attrs]
                validas['Q005'] = [a[1] for a in attrs]
                acumular(grupos, validas, 2024)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO', 'variavel_origem': 'Q005',
                'n_participantes_indexados': n_participantes,
                'n_redacoes_validas_vinculadas': n_validas,
                'n_validas_sem_correspondencia': 0,
                'inscricoes_unicas_participantes': True,
                'inscricoes_unicas_redacoes_validas': True,
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    nacional = defaultdict(Grupo)
    for (uf, codigo), grupo in grupos.items():
        if uf not in UFS or codigo not in CATEGORIAS:
            raise ValueError(f'Grupo desconhecido: {uf}/{codigo}')
        nacional[('BR', codigo)].combinar(grupo)
    return {**grupos, **nacional}


def ler_referencia(base: Path, caminho: Path | None = None) -> dict:
    arquivo = caminho or (base/'outputs'/'json'/'IND_045_tipo_escola_nota.json')
    if caminho is not None and not arquivo.is_absolute():
        arquivo = base/arquivo
    if not arquivo.is_file():
        raise FileNotFoundError(f'IND-045 necessário para conciliação: {arquivo}')
    ref = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if ref.get('indicator_id') != 'IND-045' or ref.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência deve ser JSON IND-045/POP_SOCIO_VALID.')
    return ref


def obter_grupo(grupos: dict, uf: str, codigo: str) -> Grupo:
    return grupos.get((uf, codigo), Grupo())


def conferir_montar(ano: int, grupos: dict, n_validas: int,
                   ref: dict) -> tuple[dict, dict]:
    """Concilia denominadores/estatísticas; só depois aplica supressão."""
    ref_ano = ref.get('years', {}).get(str(ano), {})
    if ref_ano.get('status') != 'ok' or ref_ano.get('n_brasil') != n_validas:
        raise ValueError(f'{ano}: IND-045 não disponível ou N Brasil diverge.')
    ref_ufs = ref_ano.get('recortes', {})
    if set(ref_ufs) != {'BR', *UFS}:
        raise ValueError(f'{ano}: IND-045 não inclui BR + 27 UFs.')
    n_soma_ref = ref_ano.get('validacao', {}).get('n_soma_competencias_divergente')
    if n_soma_ref is None:
        raise ValueError(f'{ano}: IND-045 sem diagnóstico de soma de competências.')
    if sum(obter_grupo(grupos, 'BR', c).n for c in CATEGORIAS) != n_validas:
        raise ValueError(f'{ano}: N Brasil difere IND-045.')
    divergentes = sum(obter_grupo(grupos, 'BR', c).n_soma_divergente for c in CATEGORIAS)
    if divergentes != n_soma_ref:
        raise ValueError(f'{ano}: soma C1..C5 difere do IND-045.')
    totais_categoria = Counter()
    for uf in ('BR', *UFS):
        total = sum(obter_grupo(grupos, uf, c).n for c in CATEGORIAS)
        n_ref = ref_ufs[uf]['n_pop_socio_valid']
        if total != n_ref:
            raise ValueError(f'{ano}/{uf}: N {total} difere IND-045 {n_ref}.')
        hist = Counter()
        for cod in CATEGORIAS:
            grupo = obter_grupo(grupos, uf, cod)
            if sum(grupo.hist.values()) != grupo.n:
                raise ValueError(f'{ano}/{uf}/{cod}: histograma difere N.')
            hist.update(grupo.hist)
            if uf == 'BR':
                totais_categoria[cod] = grupo.n
        ref_cats = ref_ufs[uf]['categories']
        if n_ref and all(not cat['suprimido'] for cat in ref_cats):
            media_ref = math.fsum(cat['n_redacoes']*cat['media']
                                  for cat in ref_cats if cat['n_redacoes']) / n_ref
            media_calc = math.fsum(nota*freq for nota, freq in hist.items()) / total
            if not math.isclose(media_ref, media_calc, abs_tol=.00015, rel_tol=0):
                raise ValueError(f'{ano}/{uf}: média total difere IND-045.')
    if sum(obter_grupo(grupos, uf, c).n for uf in UFS for c in CATEGORIAS) != n_validas:
        raise ValueError(f'{ano}: soma de todas as UFs difere N Brasil.')

    pequenas = {c for c in CATEGORIAS if any(
        0 < obter_grupo(grupos, uf, c).n < LIMIAR for uf in ('BR', *UFS))}
    motivos = {c: 'primaria_grupo_pequeno_em_alguma_uf' for c in pequenas}
    if pequenas:
        afetadas = [uf for uf in UFS if any(
            0 < obter_grupo(grupos, uf, c).n < LIMIAR for c in pequenas)]
        preferencia = ('CODIGO_NAO_RECONHECIDO', 'SEM_RESPOSTA',
                      '10_20', '7_9', '5_6', '4', '3', '2', '1')
        candidatos = [c for c in preferencia if c not in motivos
                      and obter_grupo(grupos, 'BR', c).n >= LIMIAR
                      and all(obter_grupo(grupos, uf, c).n >= LIMIAR for uf in afetadas)]
        if candidatos:
            motivos[candidatos[0]] = 'complementar_contra_inferencia_por_totais'
        else:
            for c in CATEGORIAS:
                motivos.setdefault(c, 'complementar_sem_categoria_segura')

    recortes = {}
    total_suprimidos = 0
    for uf in ('BR', *UFS):
        n_uf = ref_ufs[uf]['n_pop_socio_valid']
        categorias = []
        for ordem, (codigo, descricao) in enumerate(CATEGORIAS.items()):
            grupo = obter_grupo(grupos, uf, codigo)
            motivo = motivos.get(codigo)
            oculto = motivo is not None
            total_suprimidos += int(oculto)
            est = (ind45.estatisticas(grupo.hist, grupo.n) if not oculto else
                   {campo: None for campo in
                    ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')})
            categorias.append({
                'codigo_faixa_moradores': codigo, 'descricao_categoria': descricao,
                'ordem': ordem, 'n_redacoes': None if oculto else grupo.n,
                'percentual_total_validas': None if oculto or not n_uf
                    else round(100*grupo.n/n_uf, 6),
                **est, 'suprimido': oculto, 'motivo_supressao': motivo,
            })
        recortes[uf] = {
            'uf': uf, 'variavel_origem': 'Q005', 'population': 'POP_SOCIO_VALID',
            'n_pop_socio_valid': n_uf, 'categories': categorias,
            'status_publicacao': 'draft_revisao_academica_privacidade_cruzada_pendente',
        }
    validacao = {
        'referencia_populacao': 'IND-045', 'n_pop_socio_valid_brasil': n_validas,
        'n_por_uf_e_brasil_conferido': True,
        'soma_ufs_conferida': True,
        'medias_totais_conferidas_quando_referencia_sem_supressao': True,
        'divergencias_conferidas_com_ind045': True,
        'histogramas_reconciliados': True,
        'categorias_suprimidas_globalmente': motivos,
        'n_celulas_geograficas_suprimidas': total_suprimidos,
        'revisao_privacidade_cruzada_pendente': True,
    }
    return recortes, validacao


def linhas_csv(todos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(todos.items(), key=lambda par: int(par[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = obj['recortes'][uf]
            for cat in rec['categories']:
                linhas.append({
                    'ano': int(ano), 'uf': uf, 'variavel_origem': 'Q005',
                    'codigo_faixa_moradores': cat['codigo_faixa_moradores'],
                    'descricao_categoria': cat['descricao_categoria'],
                    'ordem': cat['ordem'], 'n_redacoes': cat['n_redacoes'],
                    'percentual_total_validas': cat['percentual_total_validas'],
                    'media': cat['media'], 'mediana': cat['mediana'],
                    'q1': cat['q1'], 'q3': cat['q3'], 'iqr': cat['iqr'],
                    'desvio_padrao': cat['desvio_padrao'],
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
                prefix=caminho.name+'.', suffix='.tmp', delete=False) as fh:
            temp = Path(fh.name)
            writer = csv.DictWriter(fh, fieldnames=CAMPOS_CSV,
                                    delimiter=';', extrasaction='raise')
            writer.writeheader()
            writer.writerows(linhas)
        temp.replace(caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def preparar_dashboards(saida: Path, novos: dict[str, dict]) -> list[tuple[Path, dict]]:
    """Confere existência do IND-045 e preserva indicadores anteriores."""
    preparados = []
    for ano, obj in sorted(novos.items(), key=lambda par: int(par[0])):
        if obj['status'] != 'ok':
            continue
        caminho = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            log(f'  Dashboard {ano} não encontrado; módulo independente preservado.')
            continue
        doc = json.loads(caminho.read_text(encoding='utf-8-sig'))
        socio = doc.get('pages', {}).get('socioeconomic')
        if not isinstance(socio, dict):
            raise ValueError(f'{caminho.name}: pages.socioeconomic ausente.')
        anterior = socio.get('school_type_total')
        if not isinstance(anterior, dict) or anterior.get('indicator_id') != 'IND-045':
            raise ValueError(f'{caminho.name}: IND-045 necessário antes do IND-050.')
        socio['household_size'] = {
            'indicator_id': 'IND-050', 'status': 'draft', 'year': int(ano),
            'population': 'POP_SOCIO_VALID',
            'national': obj['recortes']['BR'],
            'states': {uf: obj['recortes'][uf] for uf in UFS},
            'method': ('Q005: tamanho do domicílio (inclui participante), faixas '
                       '1, 2, 3, 4, 5–6, 7–9, 10–20; notas totais'),
            'privacy_note': ('Supressão de grupos <30 e complementar, '
                             'revisão cruzada pendente.'),
        }
        qualidade = doc.setdefault('quality', {})
        qualidade['ind050_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-050: tamanho domiciliar declarado e nota da redação têm '
                 'relação apenas descritiva; revisões de top-code e privacidade pendentes.')
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
    destino_json = saida/'outputs'/'json'/'IND_050_moradores_nota.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_050_moradores_nota.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-050 já existe; use --sobrescrever.')
    referencia = ler_referencia(base, referencia_path)
    necessarias = set()
    for ano in anos:
        if ano < 2024:
            necessarias.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            necessarias.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = ind45.localizar_fontes(base, necessarias, escolhas)
    faltantes = sorted(necessarias - set(fontes))
    if faltantes:
        raise FileNotFoundError(f'Fontes ausentes: {faltantes}. Informe --base/arquivos.')

    anteriores = {}
    if sobrescrever and destino_json.is_file():
        prev = json.loads(destino_json.read_text(encoding='utf-8-sig'))
        if prev.get('indicator_id') != 'IND-050':
            raise ValueError('JSON anterior não pertence ao IND-050.')
        anteriores = prev.get('years', {})
    todos = dict(anteriores)
    novos = {}
    for ano in anos:
        log(f'IND-050 | {ano} — moradores × nota total...')
        if ano == 2025:
            if referencia.get('years', {}).get('2025', {}).get('status') != 'indisponivel':
                raise ValueError('IND-045/2025 não confirma indisponibilidade de vínculo.')
            obj = {'ano': ano, 'status': 'indisponivel', 'reason': (
                'Não existe chave pública comum entre questionário socioeconômico '
                'e notas da redação de 2025 nas fontes usadas pelo projeto.'),
                'recortes': {}}
        else:
            if ano == 2024:
                grupos, n_validas, diag = ler_2024(
                    fontes['PARTICIPANTES_2024.CSV'],
                    fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            else:
                grupos, n_validas, diag = ler_mesma_linha(
                    fontes[f'MICRODADOS_ENEM_{ano}.CSV'], ano, bloco)
            recortes, val = conferir_montar(ano, criar_brasil(grupos), n_validas, referencia)
            obj = {
                'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
                'n_brasil': n_validas, 'variavel_origem': 'Q005',
                'diagnostico_fonte': diag, 'validacao': val, 'recortes': recortes,
            }
            log(f'  N Brasil={n_validas:,}; supressões={val["n_celulas_geograficas_suprimidas"]}; '
                'IND-045 reconciliado.')
        todos[str(ano)] = obj
        novos[str(ano)] = obj

    modulo = {
        'indicator_id': 'IND-050', 'titulo': 'Moradores × nota da redação',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, v in todos.items() if v.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'variable': 'Q005',
            'question': 'Incluindo você, quantas pessoas moram atualmente em sua residência?',
            'code_domain': 'inteiros 1..20 conforme dicionários 2019–2024',
            'top_code': ('20 é o código máximo listado; sem prova de que signifique '
                         '20 ou mais. Não extrapolar.'),
            'bands': CATEGORIAS,
            'population': 'TP_STATUS_REDACAO=1; nota total 0..1000 e C1–C5 0..200',
            'method': 'N, percentual, média, mediana, quartis, IQR e DP populacional da nota total por faixa',
            'quantiles': 'Hyndman–Fan tipo 7 em histograma exato',
            'reference': 'IND-045: N de UF/BR, média total quando íntegra e soma das competências',
            'join_2024': 'NU_INSCRICAO única e obrigatória para redações válidas',
            '2025': 'indisponível (sem vínculo público questionário × nota)',
            'privacy': 'Resultados agregados publicados sem supressão automática por N<30; homologação acadêmica pendente',
            'notes': [
                'Q005 inclui a pessoa participante na contagem.',
                'Ausência de resposta e valores não reconhecidos não são imputados.',
                'Faixas fixas 1, 2, 3, 4, 5–6, 7–9 e 10–20 para edições 2019–2024.',
                '20 é um código documentado, não uma categoria inferida 20+.',
                'UF é de aplicação da prova, não necessariamente de residência.',
                'Diferenças de nota não constituem efeito causal do tamanho do domicílio.',
                'O módulo deve passar por revisão acadêmica e de privacidade cruzada.',
            ],
        },
        'years': todos,
    }
    preparados = [] if somente_modulo else preparar_dashboards(saida, novos)
    ind45.salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas_csv(todos))
    for caminho, doc in preparados:
        ind45.salvar_json(caminho, doc)
        log(f'  Dashboard {caminho.name}: household_size integrado.')
    log(f'IND-050 concluído (draft). JSON: {destino_json} | CSV: {destino_csv}')
    return modulo


def autoteste() -> None:
    """Testes sintéticos 2019 e 2024; não cria dados reais."""
    rng = np.random.default_rng(50)
    for _ in range(65):
        arr = rng.choice(np.arange(0, 1001, 20).astype(float),
                         size=int(rng.integers(1, 100)))
        stats = ind45.estatisticas(Counter(arr), len(arr))
        assert abs(stats['media'] - arr.mean()) < .00006
        assert abs(stats['mediana'] - np.median(arr)) < .00006
        assert abs(stats['q1'] - np.quantile(arr, .25)) < .00006
        assert abs(stats['q3'] - np.quantile(arr, .75)) < .00006
        assert abs(stats['desvio_padrao'] - arr.std(ddof=0)) < .00006
    # Verificar população: status não válido não entra nas médias nem nos N.
    subpop = pd.DataFrame({
        'TP_STATUS_REDACAO': ['1', '2'], 'NU_NOTA_REDACAO': ['600', ''],
        **{c: ['120', ''] for c in NOTAS_COMP},
    })
    assert len(ind45.selecionar_validas(subpop)) == 1
    for x, esperado in [('1', '1'), ('02', '2'), ('3.0', '3'), ('4,00', '4'),
                         ('5', '5_6'), ('6', '5_6'), ('7', '7_9'), ('9', '7_9'),
                         ('10', '10_20'), ('20', '10_20'),
                         ('', 'SEM_RESPOSTA'), (None, 'SEM_RESPOSTA'),
                         ('0', 'CODIGO_NAO_RECONHECIDO'),
                         ('21', 'CODIGO_NAO_RECONHECIDO'),
                         ('2.5', 'CODIGO_NAO_RECONHECIDO'),
                         ('A', 'CODIGO_NAO_RECONHECIDO'),
                         ('-1', 'CODIGO_NAO_RECONHECIDO')]:
        assert faixa_moradores(x) == esperado, (x, esperado)
    with tempfile.TemporaryDirectory(prefix='teste_ind050_') as pasta:
        raiz = Path(pasta)
        raw = raiz/'raw'
        out = raiz/'outputs'/'json'
        raw.mkdir()
        out.mkdir(parents=True)
        dados = []
        for idx_uf, uf in enumerate(UFS):
            for k in range(180):
                if k < 35:
                    q5 = '1'
                elif k < 71:
                    q5 = '2'
                elif k < 105:
                    q5 = '3'
                elif k < 135:
                    q5 = '4'
                elif k < 155:
                    q5 = '5' if k % 2 else '6'
                elif k < 171:
                    q5 = str(7 + k % 3)
                elif k < 175:
                    q5 = str(10 + k % 11)
                elif k < 178:
                    q5 = ''
                else:
                    q5 = '99'
                comps = [float(20*int(rng.integers(3, 10))) for _ in range(5)]
                dados.append({
                    'NU_INSCRICAO': str(905000000000 + idx_uf*180+k),
                    'SG_UF_PROVA': uf, 'Q005': q5, 'TP_STATUS_REDACAO': '1',
                    'NU_NOTA_REDACAO': str(sum(comps)),
                    **{c: str(comps[j]) for j, c in enumerate(NOTAS_COMP)},
                })
        df = pd.DataFrame(dados)
        df.drop(columns='NU_INSCRICAO').to_csv(
            raw/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        df[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q005']].iloc[::-1].to_csv(
            raw/'PARTICIPANTES_2024.csv', sep=';', index=False)
        df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].to_csv(
            raw/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        ref = {'indicator_id': 'IND-045', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano in (2019, 2024):
            rec = {}
            for uf in ('BR', *UFS):
                parte = df if uf == 'BR' else df[df['SG_UF_PROVA'] == uf]
                total = len(parte)
                rec[uf] = {
                    'n_pop_socio_valid': total,
                    'categories': [{'suprimido': False, 'n_redacoes': total,
                                    'media': round(pd.to_numeric(parte['NU_NOTA_REDACAO']).mean(), 4)}],
                }
            ref['years'][str(ano)] = {
                'status': 'ok', 'n_brasil': len(df), 'recortes': rec,
                'validacao': {'n_soma_competencias_divergente': 0},
            }
            ind45.salvar_json(out/f'dashboard_enem_{ano}.json', {
                'pages': {'socioeconomic': {
                    'school_type_total': {'indicator_id': 'IND-045'},
                    'sentinela': 'preservar'}},
                'quality': {'sentinela': 1}, 'meta': {'warnings': []},
            })
        ref['years']['2025'] = {'status': 'indisponivel'}
        ind45.salvar_json(out/'IND_045_tipo_escola_nota.json', ref)
        result = executar(raiz, raiz, (2019, 2024, 2025), 47, True, False)
        assert result['years']['2025']['status'] == 'indisponivel'
        assert result['anos_disponiveis'] == [2019, 2024]
        for ano in ('2019', '2024'):
            obj = result['years'][ano]
            assert obj['n_brasil'] == len(df) == 4860
            assert obj['validacao']['n_por_uf_e_brasil_conferido']
            assert len(obj['recortes']) == 28
            br = obj['recortes']['BR']
            assert br['n_pop_socio_valid'] == 4860
            assert len(br['categories']) == len(CATEGORIAS)
            motivos = obj['validacao']['categorias_suprimidas_globalmente']
            assert not motivos
            assert all(c['n_redacoes'] is None and c['media'] is None
                       for c in br['categories'] if c['suprimido'])
            doc = json.loads((out/f'dashboard_enem_{ano}.json').read_text())
            assert doc['pages']['socioeconomic']['sentinela'] == 'preservar'
            assert doc['pages']['socioeconomic']['household_size']['indicator_id'] == 'IND-050'
            assert doc['quality']['sentinela'] == 1
            assert doc['quality']['ind050_validation']['status'] == 'ok_agregados'
        with (raiz/'outputs'/'indicadores'/'IND_050_moradores_nota.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            linhas = list(csv.DictReader(fh, delimiter=';'))
        assert len(linhas) == 2*28*len(CATEGORIAS)
        assert all('NU_INSCRICAO' not in linha for linha in linhas)
        assert all(not linha['n_redacoes'] and not linha['media']
                   for linha in linhas if linha['suprimido'] == 'True')
        for codigo in ('1', '2', '3', '4'):
            parte = df.loc[(df['SG_UF_PROVA'] == 'SP') & (df['Q005'] == codigo)]
            notas = pd.to_numeric(parte['NU_NOTA_REDACAO']).to_numpy(dtype=float)
            cat = next(c for c in result['years']['2019']['recortes']['SP']['categories']
                       if c['codigo_faixa_moradores'] == codigo)
            if not cat['suprimido']:
                assert cat['n_redacoes'] == len(notas)
                assert abs(cat['media'] - notas.mean()) < .00006
                assert abs(cat['mediana'] - np.median(notas)) < .00006
                assert abs(cat['q1'] - np.quantile(notas, .25)) < .00006
                assert abs(cat['q3'] - np.quantile(notas, .75)) < .00006
        # Falha de N em referência precisa ser detectada.
        ruim = json.loads(json.dumps(ref))
        ruim['years']['2019']['recortes']['SP']['n_pop_socio_valid'] += 1
        g, n, _ = ler_mesma_linha(raw/'MICRODADOS_ENEM_2019.csv', 2019, 61)
        try:
            conferir_montar(2019, criar_brasil(g), n, ruim)
        except ValueError as exc:
            assert 'difere IND-045' in str(exc)
        else:
            raise AssertionError('Não detectou N incompatível com IND-045.')
        # Join invariante a diferentes tamanhos de lote.
        g1, n1, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 37)
        g2, n2, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 511)
        assert n1 == n2 == len(df)
        assert all(g1[k].hist == g2[k].hist and g1[k].n == g2[k].n for k in g1)
        # Vínculo ausente deve abortar.
        missing = df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].copy()
        missing.loc[0, 'NU_INSCRICAO'] = 'ID_AUSENTE'
        missing.to_csv(raw/'SEM_VINCULO.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'SEM_VINCULO.csv', 59)
        except ValueError as exc:
            assert 'sem vínculo' in str(exc)
        else:
            raise AssertionError('Não detectou falta de vínculo.')
        # Redações válidas duplicadas devem abortar.
        dup_notas = df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]]
        pd.concat([dup_notas, dup_notas.iloc[[0]]]).to_csv(
            raw/'DUP_REDACOES.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'DUP_REDACOES.csv', 97)
        except ValueError as exc:
            assert 'duplicada' in str(exc)
        else:
            raise AssertionError('Não detectou redação válida duplicada.')
        # Participantes duplicados devem abortar.
        duplicados = df[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q005']]
        pd.concat([duplicados, duplicados.iloc[[0]]]).to_csv(
            raw/'DUPLICADOS.csv', sep=';', index=False)
        try:
            ler_2024(raw/'DUPLICADOS.csv', raw/'COMPETENCIAS_REDACAO_2024.csv', 103)
        except ValueError as exc:
            assert 'duplicada' in str(exc)
        else:
            raise AssertionError('Não detectou duplicidade de inscrição.')
        # Cenário extremo: cada categoria é pequena em SP -> suprimir tudo.
        pequenos = defaultdict(Grupo)
        for uf in UFS:
            for cod in CATEGORIAS:
                qtd = 1 if uf == 'SP' else 50
                pequenos[(uf, cod)].adicionar(np.full(qtd, 600.),
                                              np.full((qtd, 5), 120.))
        pequenos = criar_brasil(pequenos)
        ref2 = json.loads(json.dumps(ref))
        for uf in ('BR', *UFS):
            total = sum(obter_grupo(pequenos, uf, c).n for c in CATEGORIAS)
            ref2['years']['2019']['recortes'][uf] = {
                'n_pop_socio_valid': total,
                'categories': [{'suprimido': False, 'n_redacoes': total, 'media': 600.}],
            }
        ref2['years']['2019']['n_brasil'] = sum(
            obter_grupo(pequenos, 'BR', c).n for c in CATEGORIAS)
        rec_priv, val_priv = conferir_montar(2019, pequenos,
                                            ref2['years']['2019']['n_brasil'], ref2)
        assert not val_priv['categorias_suprimidas_globalmente']
        assert all(not cat['suprimido'] and cat['n_redacoes'] == 1
                   for cat in rec_priv['SP']['categories'])
    log('AUTOTESTE IND-050 APROVADO: códigos 1–20, faixas estáveis, '
        'estatísticas, N por UF/BR, supressão complementar, junção 2024, '
        'duplicatas, vínculos, CSV/JSON, dashboards e 2025 indisponível.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-050: Moradores × nota da redação')
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
        parser.error('--bloco deve ser >= 1.')
    escolhas = {}
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.referencia_ind045, escolhas)
    except (OSError, ValueError, KeyError, sqlite3.DatabaseError,
            json.JSONDecodeError, TypeError) as erro:
        print(f'ERRO IND-050: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
