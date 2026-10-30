#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-049 — Ocupação dos responsáveis × nota da redação | UNIVESP.

Catálogo ENEM 2019–2025 v2: pages.socioeconomic.parent_occupation.
População POP_SOCIO_VALID (mesma do IND-045), nota total de redação.

Q003 = ocupação do pai/homem responsável; Q004 = ocupação da mãe/mulher
responsável. Categorias originais A..E (grupos ocupacionais 1..5), F
('Não sei'), SEM_RESPOSTA e CODIGO_NAO_RECONHECIDO. Cada pergunta é um
recorte separado, nunca um 'grau ocupacional' calculado dos dois pais.

2019–2023: Q003/Q004 e notas em MICRODADOS_ENEM_<ano>.csv.
2024: Q003/Q004 em PARTICIPANTES_2024.csv; notas em
COMPETENCIAS_REDACAO_2024.csv; join por NU_INSCRICAO única.
2025: associação indisponível nas fontes públicas deste projeto.

Aviso sobre dicionário: 2019–2024 rotulam Q004 como 'Numérica', mas listam
as categorias A..F. O script lê as respostas como texto e INTERROMPE ao
encontrar valores numéricos, em vez de presumir conversão 1..6 para A..F.

Saídas: outputs/json/IND_049_ocupacao_responsaveis_nota.json;
        outputs/indicadores/IND_049_ocupacao_responsaveis_nota.csv;
        outputs/json/dashboard_enem_<ano>.json (bloco parent_occupation).

Privacidade: suprime categorias com N=1..29 em qualquer UF para BR e todas
as UFs naquele ano/pergunta; uma categoria complementar suficientemente
numerosa também é suprimida. Se não existe complemento seguro, suprime todas.
Situação 'draft' até auditoria real e privacidade cruzada com outros indicadores.

Executar na raiz do repositório:
  python src/indicadores/IND_049_ocupacao_responsaveis_nota.py --autoteste
  python src/indicadores/IND_049_ocupacao_responsaveis_nota.py --anos 2024 --sobrescrever
  python src/indicadores/IND_049_ocupacao_responsaveis_nota.py --sobrescrever

Dependência local: IND_045_tipo_escola_nota.py e JSON real do IND-045.
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
RESPONSAVEIS = {
    'pai_ou_responsavel_masculino': 'Q003',
    'mae_ou_responsavel_feminino': 'Q004',
}
CATEGORIAS = {
    'A': 'Grupo ocupacional 1',
    'B': 'Grupo ocupacional 2',
    'C': 'Grupo ocupacional 3',
    'D': 'Grupo ocupacional 4',
    'E': 'Grupo ocupacional 5',
    'F': 'Não sei',
    'SEM_RESPOSTA': 'Não informou',
    'CODIGO_NAO_RECONHECIDO': 'Código não reconhecido',
}
CAMPOS_CSV = (
    'ano', 'uf', 'responsavel', 'variavel_origem', 'codigo_ocupacao',
    'descricao_categoria', 'ordem', 'n_redacoes', 'percentual_total_validas',
    'media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'suprimido', 'motivo_supressao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def codigo_ocupacao(valor: Any) -> str:
    txt = '' if valor is None else str(valor).strip().upper()
    if txt in ('', 'NAN', 'NULL', 'NONE', '<NA>'):
        return 'SEM_RESPOSTA'
    return txt if txt in 'ABCDEF' and len(txt) == 1 else 'CODIGO_NAO_RECONHECIDO'


def conferir_codigos_nao_numericos(valores: pd.Series, campo: str, ano: int) -> None:
    """Q004 traz metadado 'numérica' inconsistente com categorias A..F.

    Um valor numérico exigiria verificar o CSV/dicionário em vez de mapear
    1..6 presumidamente para A..F e publicar grupos possivelmente errados.
    """
    serie = valores.astype('string').str.strip().str.upper()
    numericos = serie.str.fullmatch(r'\d+(?:[.,]0+)?').fillna(False)
    if numericos.any():
        amostra = sorted(set(serie.loc[numericos].tolist()))[:6]
        raise ValueError(f'{ano}/{campo}: respostas numéricas {amostra}; dicionário '
                         'lista categorias A–F. Conferir codificação real; '
                         'conversão numérica não autorizada.')


class Grupo:
    """Histograma exato da nota total e controle das competências; sem microdados."""
    def __init__(self) -> None:
        self.n = 0
        self.hist = Counter()
        self.n_soma_divergente = 0

    def adicionar(self, notas: np.ndarray, competencias: np.ndarray) -> None:
        if len(notas) != len(competencias):
            raise ValueError('Nota total e competências desalinhadas.')
        self.n += len(notas)
        if not len(notas):
            return
        vals, freqs = np.unique(notas, return_counts=True)
        self.hist.update({float(v): int(n) for v, n in zip(vals, freqs)})
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
    for responsavel, pergunta in RESPONSAVEIS.items():
        conferir_codigos_nao_numericos(validas[pergunta], pergunta, ano)
        codigos = validas[pergunta].map(codigo_ocupacao)
        indices = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codigos.to_numpy()})
        for (uf, codigo), posicoes in indices.groupby(['uf', 'codigo'], sort=False).indices.items():
            grupos[(responsavel, str(uf), str(codigo))].adicionar(notas[posicoes], competencias[posicoes])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if not (2019 <= ano <= 2023):
        raise ValueError('Formato de arquivo único permitido apenas para 2019–2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    colunas = ['SG_UF_PROVA', *RESPONSAVEIS.values(), 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]
    for parte in ind45.ler_blocos(arquivo, colunas, bloco):
        validas = ind45.selecionar_validas(parte)
        n_validas += len(validas)
        acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {
        'metodo': 'mesma_linha', 'variaveis_origem': ['Q003', 'Q004'],
        'n_redacoes_validas_processadas': n_validas,
    }


def ids_inscricao(df: pd.DataFrame, fonte: str) -> list[str]:
    ids = df['NU_INSCRICAO'].astype('string').str.strip().tolist()
    if any(not i or i.upper() in ('NAN', 'NONE', 'NULL', '<NA>') for i in ids):
        raise ValueError(f'{fonte}: NU_INSCRICAO vazia/inválida.')
    return ids


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Join 1:1 em SQLite; conserva ordem de linhas das redações válidas."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind049_') as pasta:
        db = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL, '
                       'q003 TEXT NOT NULL, q004 TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE redacoes_vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ind45.ler_blocos(
                    participantes, ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q003', 'Q004'], bloco):
                ids = ids_inscricao(parte, 'PARTICIPANTES_2024')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: UF da prova ausente/inválida.')
                q003 = parte['Q003'].astype('string').str.strip().tolist()
                q004 = parte['Q004'].astype('string').str.strip().tolist()
                # Segurança: todos os participantes também precisam ter codificação válida.
                conferir_codigos_nao_numericos(parte['Q003'], 'Q003', 2024)
                conferir_codigos_nao_numericos(parte['Q004'], 'Q004', 2024)
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?,?)',
                                   zip(ids, ufs, q003, q004))
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
                    db.executemany('INSERT INTO redacoes_vistas VALUES (?)', ((i,) for i in ids))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: redação válida duplicada.') from erro
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                encontrados = db.execute('''
                    SELECT l.pos, p.uf, p.q003, p.q004
                    FROM lote AS l JOIN participantes AS p ON p.id = l.id
                ''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                attrs = [None] * len(ids)
                for pos, uf, q003, q004 in encontrados:
                    attrs[pos] = (uf, q003, q004)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [a[0] for a in attrs]
                validas['Q003'] = [a[1] for a in attrs]
                validas['Q004'] = [a[2] for a in attrs]
                acumular(grupos, validas, 2024)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO', 'variaveis_origem': ['Q003', 'Q004'],
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
    for (responsavel, uf, codigo), grupo in grupos.items():
        if responsavel not in RESPONSAVEIS or uf not in UFS or codigo not in CATEGORIAS:
            raise ValueError(f'Grupo desconhecido: {responsavel}/{uf}/{codigo}')
        nacional[(responsavel, 'BR', codigo)].combinar(grupo)
    return {**grupos, **nacional}


def ler_referencia(base: Path, caminho: Path | None = None) -> dict:
    arquivo = caminho or (base/'outputs'/'json'/'IND_045_tipo_escola_nota.json')
    if caminho is not None and not arquivo.is_absolute():
        arquivo = base / arquivo
    if not arquivo.is_file():
        raise FileNotFoundError(f'IND-045 necessário para conciliação: {arquivo}')
    ref = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if ref.get('indicator_id') != 'IND-045' or ref.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência deve ser JSON IND-045/POP_SOCIO_VALID.')
    return ref


def obter_grupo(grupos: dict, resp: str, uf: str, codigo: str) -> Grupo:
    return grupos.get((resp, uf, codigo), Grupo())


def conferir_montar(ano: int, grupos: dict, n_validas: int, ref: dict) -> tuple[dict, dict]:
    ref_ano = ref.get('years', {}).get(str(ano), {})
    if ref_ano.get('status') != 'ok' or ref_ano.get('n_brasil') != n_validas:
        raise ValueError(f'{ano}: IND-045 não disponível ou N Brasil diverge.')
    ref_ufs = ref_ano.get('recortes', {})
    if set(ref_ufs) != {'BR', *UFS}:
        raise ValueError(f'{ano}: IND-045 não inclui BR + 27 UFs.')
    n_soma_ref = ref_ano.get('validacao', {}).get('n_soma_competencias_divergente')
    if n_soma_ref is None:
        raise ValueError(f'{ano}: IND-045 sem diagnóstico de soma de competências.')

    for resp in RESPONSAVEIS:
        if sum(obter_grupo(grupos, resp, 'BR', c).n for c in CATEGORIAS) != n_validas:
            raise ValueError(f'{ano}/{resp}: N Brasil difere IND-045.')
        divergentes = sum(obter_grupo(grupos, resp, 'BR', c).n_soma_divergente
                          for c in CATEGORIAS)
        if divergentes != n_soma_ref:
            raise ValueError(f'{ano}/{resp}: soma C1..C5 difere do IND-045.')
        for uf in ('BR', *UFS):
            total = sum(obter_grupo(grupos, resp, uf, c).n for c in CATEGORIAS)
            n_ref = ref_ufs[uf]['n_pop_socio_valid']
            if total != n_ref:
                raise ValueError(f'{ano}/{resp}/{uf}: N {total} difere IND-045 {n_ref}.')
            hist = Counter()
            for c in CATEGORIAS:
                grupo = obter_grupo(grupos, resp, uf, c)
                if sum(grupo.hist.values()) != grupo.n:
                    raise ValueError(f'{ano}/{resp}/{uf}/{c}: histograma difere N.')
                hist.update(grupo.hist)
            cats_ref = ref_ufs[uf]['categories']
            if n_ref and all(not cat['suprimido'] for cat in cats_ref):
                media_ref = math.fsum(cat['n_redacoes'] * cat['media']
                                     for cat in cats_ref if cat['n_redacoes']) / n_ref
                media_calc = math.fsum(nota * freq for nota, freq in hist.items()) / total
                if not math.isclose(media_ref, media_calc, abs_tol=.00015, rel_tol=0):
                    raise ValueError(f'{ano}/{resp}/{uf}: média total difere IND-045.')

    supressoes: dict[str, dict[str, str]] = {}
    recortes = {}
    total_suprimidos = 0
    for resp in RESPONSAVEIS:
        pequenas = {c for c in CATEGORIAS if any(
            0 < obter_grupo(grupos, resp, uf, c).n < LIMIAR
            for uf in ('BR', *UFS))}
        motivos = {c: 'primaria_grupo_pequeno_em_alguma_uf' for c in pequenas}
        if pequenas:
            afetadas = [uf for uf in UFS if any(
                0 < obter_grupo(grupos, resp, uf, c).n < LIMIAR for c in pequenas)]
            candidatos = [c for c in ('CODIGO_NAO_RECONHECIDO', 'SEM_RESPOSTA',
                                      'F', 'E', 'D', 'C', 'B', 'A')
                          if c not in motivos
                          and obter_grupo(grupos, resp, 'BR', c).n >= LIMIAR
                          and all(obter_grupo(grupos, resp, uf, c).n >= LIMIAR
                                  for uf in afetadas)]
            if candidatos:
                motivos[candidatos[0]] = 'complementar_contra_inferencia_por_totais'
            else:
                for c in CATEGORIAS:
                    motivos.setdefault(c, 'complementar_sem_categoria_segura')
        supressoes[resp] = motivos
        recortes[resp] = {}
        for uf in ('BR', *UFS):
            n_uf = ref_ufs[uf]['n_pop_socio_valid']
            cats = []
            for ordem, (codigo, descricao) in enumerate(CATEGORIAS.items()):
                grupo = obter_grupo(grupos, resp, uf, codigo)
                motivo = motivos.get(codigo)
                oculto = motivo is not None
                total_suprimidos += int(oculto)
                est = (ind45.estatisticas(grupo.hist, grupo.n) if not oculto else
                       {campo: None for campo in
                        ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')})
                cats.append({
                    'codigo_ocupacao': codigo, 'descricao_categoria': descricao,
                    'ordem': ordem, 'n_redacoes': None if oculto else grupo.n,
                    'percentual_total_validas': (None if oculto or not n_uf
                        else round(100 * grupo.n / n_uf, 6)),
                    **est, 'suprimido': oculto, 'motivo_supressao': motivo,
                })
            recortes[resp][uf] = {
                'uf': uf, 'responsavel': resp, 'variavel_origem': RESPONSAVEIS[resp],
                'population': 'POP_SOCIO_VALID', 'n_pop_socio_valid': n_uf,
                'categories': cats,
                'status_publicacao': 'draft_revisao_academica_privacidade_cruzada_pendente',
            }
    validacao = {
        'referencia_populacao': 'IND-045', 'n_pop_socio_valid_brasil': n_validas,
        'n_por_uf_e_brasil_conferido_ambos_responsaveis': True,
        'medias_totais_conferidas_quando_referencia_sem_supressao': True,
        'divergencias_conferidas_com_ind045': True,
        'histogramas_reconciliados': True,
        'categorias_suprimidas_globalmente_por_responsavel': supressoes,
        'n_celulas_geograficas_suprimidas': total_suprimidos,
        'revisao_privacidade_cruzada_pendente': True,
    }
    return recortes, validacao


def linhas_csv(todos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(todos.items(), key=lambda item: int(item[0])):
        if obj.get('status') != 'ok':
            continue
        for resp in RESPONSAVEIS:
            for uf in ('BR', *UFS):
                rec = obj['recortes'][resp][uf]
                for cat in rec['categories']:
                    linhas.append({
                        'ano': int(ano), 'uf': uf, 'responsavel': resp,
                        'variavel_origem': rec['variavel_origem'],
                        'codigo_ocupacao': cat['codigo_ocupacao'],
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
    """Pré-valida os dashboards, sem sobrescrever os outros indicadores."""
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
            raise ValueError(f'{caminho.name}: IND-045 necessário antes do IND-049.')
        socio['parent_occupation'] = {
            'indicator_id': 'IND-049', 'status': 'draft', 'year': int(ano),
            'population': 'POP_SOCIO_VALID',
            'national': {r: obj['recortes'][r]['BR'] for r in RESPONSAVEIS},
            'states': {uf: {r: obj['recortes'][r][uf] for r in RESPONSAVEIS} for uf in UFS},
            'method': 'Q003 e Q004 separadamente: N, média, mediana, Q1/Q3, IQR e DP',
            'privacy_note': 'Supressão + complemento por pergunta e ano; revisão cruzada pendente.',
        }
        doc.setdefault('quality', {})['ind049_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-049: relação descritiva, não causal; Q003/Q004 são '
                 'autodeclarações de grupos de ocupação; revisão de privacidade pendente.')
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
    destino_json = saida/'outputs'/'json'/'IND_049_ocupacao_responsaveis_nota.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_049_ocupacao_responsaveis_nota.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-049 já existe; use --sobrescrever.')
    referencia = ler_referencia(base, referencia_path)
    necessarias = set()
    for ano in anos:
        if ano < 2024:
            necessarias.add(f'MICRODADOS_ENEM_{ano}.CSV')
        if ano == 2024:
            necessarias.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = ind45.localizar_fontes(base, necessarias, escolhas)
    faltantes = sorted(necessarias - set(fontes))
    if faltantes:
        raise FileNotFoundError(f'Fontes ausentes: {faltantes}. Informe --base/arquivos.')

    anteriores = {}
    if sobrescrever and destino_json.is_file():
        prev = json.loads(destino_json.read_text(encoding='utf-8-sig'))
        if prev.get('indicator_id') != 'IND-049':
            raise ValueError('JSON anterior não pertence ao IND-049.')
        anteriores = prev.get('years', {})
    todos = dict(anteriores)
    novos = {}
    for ano in anos:
        log(f'IND-049 | {ano} — ocupação dos responsáveis × nota total...')
        if ano == 2025:
            if referencia.get('years', {}).get('2025', {}).get('status') != 'indisponivel':
                raise ValueError('IND-045/2025 não confirma indisponibilidade de vínculo.')
            obj = {'ano': ano, 'status': 'indisponivel', 'reason': (
                'Não existe chave pública comum entre questionário socioeconômico '
                'e notas da redação de 2025 nas fontes usadas pelo projeto.'), 'recortes': {}}
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
                'n_brasil': n_validas, 'variaveis_origem': ['Q003', 'Q004'],
                'diagnostico_fonte': diag, 'validacao': val, 'recortes': recortes,
            }
            log(f'  N Brasil={n_validas:,}; supressões={val["n_celulas_geograficas_suprimidas"]}; '
                'IND-045 reconciliado.')
        todos[str(ano)] = obj
        novos[str(ano)] = obj

    modulo = {
        'indicator_id': 'IND-049', 'titulo': 'Ocupação dos responsáveis × nota',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, v in todos.items() if v.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            '2019_2024_variables': RESPONSAVEIS,
            'categories': CATEGORIAS,
            'population': 'TP_STATUS_REDACAO=1; notas total 0..1000 e C1–C5 0..200',
            'method': 'Por pergunta, UF/BR e ano: n, porcentagem, média, mediana, quartis, IQR e DP populacional',
            'quantiles': 'Hyndman-Fan tipo 7 em histograma exato',
            'reference': 'IND-045: população, média total quando íntegra e soma competências',
            'join_2024': 'NU_INSCRICAO única, obrigatório para redações válidas',
            '2025': 'indisponível (sem vínculo público entre questionário e notas)',
            'comparability': 'A–E são grupos enumerados pelo questionário; não são renda nem classe social',
            'privacy': 'Supressão global por pergunta/ano em BR/UF quando 1<=N<30 + complementar; draft',
            'q004_dictionary_warning': ('Dicionários 2019–2024 declaram Q004 como numérica, '
                'mas listam A–F; códigos numéricos no CSV abortam o processamento.'),
            'notes': [
                'Q003 e Q004 analisados separadamente; sem cruzamento pai×mãe.',
                'F (“Não sei”) e ausência de resposta são grupos diferentes.',
                'As ocupações são autorrelatadas e referem-se ao trabalho atual ou último trabalho.',
                'Não inferir causalidade, tendência individual ou posição social.',
                'UF corresponde ao local de prova, não necessariamente moradia.',
                'Ano corresponde a inscrição/participação, não a pessoa única.',
                'Resultados exigem revisão acadêmica e de privacidade cruzada antes de publicação.',
            ],
        },
        'years': todos,
    }
    preparados = [] if somente_modulo else preparar_dashboards(saida, novos)
    ind45.salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas_csv(todos))
    for caminho, doc in preparados:
        ind45.salvar_json(caminho, doc)
        log(f'  Dashboard {caminho.name}: parent_occupation integrado.')
    log(f'IND-049 concluído (draft). JSON: {destino_json} | CSV: {destino_csv}')
    return modulo


def autoteste() -> None:
    """Exercita 2019 e 2024 sintéticos; sem gerar resultados reais."""
    rng = np.random.default_rng(49)
    for _ in range(60):
        arr = rng.choice(np.arange(0, 1001, 20).astype(float),
                         size=int(rng.integers(1, 90)))
        stats = ind45.estatisticas(Counter(arr), len(arr))
        assert abs(stats['media'] - arr.mean()) < .00006
        assert abs(stats['mediana'] - np.median(arr)) < .00006
        assert abs(stats['q1'] - np.quantile(arr, .25)) < .00006
        assert abs(stats['q3'] - np.quantile(arr, .75)) < .00006
        assert abs(stats['desvio_padrao'] - arr.std(ddof=0)) < .00006
    assert all(codigo_ocupacao(' '+c.lower()+' ') == c for c in 'ABCDEF')
    assert codigo_ocupacao('') == 'SEM_RESPOSTA'
    assert codigo_ocupacao(None) == 'SEM_RESPOSTA'
    assert codigo_ocupacao('1') == 'CODIGO_NAO_RECONHECIDO'
    try:
        conferir_codigos_nao_numericos(pd.Series(['A', '1']), 'Q004', 2024)
    except ValueError as exc:
        assert 'numéricas' in str(exc)
    else:
        raise AssertionError('Não detectou Q004 com valores numéricos.')
    with tempfile.TemporaryDirectory(prefix='teste_ind049_') as pasta:
        raiz = Path(pasta)
        raw = raiz/'data'/'raw'
        raw.mkdir(parents=True)
        out = raiz/'outputs'/'json'
        out.mkdir(parents=True)
        linhas = []
        for idx_uf, uf in enumerate(UFS):
            for k in range(180):
                q3 = 'ABCDE'[k % 5]
                q4 = 'ABCDE'[((k // 5) + idx_uf) % 5]
                # Dois grupos de privacidade pequena (1, 1) na UF SP.
                if uf == 'SP' and k == 178:
                    q3, q4 = 'F', 'F'
                if uf == 'SP' and k == 179:
                    q3, q4 = '', ''
                comps = [40 + 20 * (k % 6), 80, 100, 120, 140]
                linhas.append({
                    'NU_INSCRICAO': str(901000000000 + idx_uf * 180 + k),
                    'SG_UF_PROVA': uf, 'Q003': q3, 'Q004': q4,
                    'TP_STATUS_REDACAO': '1',
                    'NU_NOTA_REDACAO': str(sum(comps)),
                    **{c: str(comps[j]) for j, c in enumerate(NOTAS_COMP)},
                })
        df = pd.DataFrame(linhas)
        df.drop(columns=['NU_INSCRICAO']).to_csv(
            raw/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        df[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q003', 'Q004']].iloc[::-1].to_csv(
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
        result = executar(raiz, raiz, (2019, 2024, 2025), 53, True, False)
        assert result['years']['2025']['status'] == 'indisponivel'
        assert result['anos_disponiveis'] == [2019, 2024]
        for ano in ('2019', '2024'):
            obj = result['years'][ano]
            assert obj['n_brasil'] == len(df) == 4860
            assert obj['validacao']['n_por_uf_e_brasil_conferido_ambos_responsaveis']
            for resp in RESPONSAVEIS:
                assert len(obj['recortes'][resp]) == 28
                br = obj['recortes'][resp]['BR']
                assert br['n_pop_socio_valid'] == 4860
                assert len(br['categories']) == len(CATEGORIAS)
                motivos = obj['validacao']['categorias_suprimidas_globalmente_por_responsavel'][resp]
                assert motivos['F'] == 'primaria_grupo_pequeno_em_alguma_uf'
                assert motivos['SEM_RESPOSTA'] == 'primaria_grupo_pequeno_em_alguma_uf'
                assert any(v == 'complementar_contra_inferencia_por_totais'
                           for v in motivos.values())
                assert all(c['n_redacoes'] is None and c['media'] is None
                           for c in br['categories'] if c['suprimido'])
            doc = json.loads((out/f'dashboard_enem_{ano}.json').read_text())
            assert doc['pages']['socioeconomic']['sentinela'] == 'preservar'
            assert doc['pages']['socioeconomic']['parent_occupation']['indicator_id'] == 'IND-049'
            assert doc['quality']['sentinela'] == 1
        with (raiz/'outputs'/'indicadores'/'IND_049_ocupacao_responsaveis_nota.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            csv_rows = list(csv.DictReader(fh, delimiter=';'))
        assert len(csv_rows) == 2 * 2 * 28 * len(CATEGORIAS)
        assert all('NU_INSCRICAO' not in row for row in csv_rows)
        assert all(not row['n_redacoes'] and not row['media']
                   for row in csv_rows if row['suprimido'] == 'True')

        # Conferência direta de estatísticas publicadas, por pergunta e grupo.
        for resp, pergunta in RESPONSAVEIS.items():
            for cod in 'ABCDE':
                grupo_sp = df.loc[(df['SG_UF_PROVA'] == 'SP') & (df[pergunta] == cod)]
                notas = pd.to_numeric(grupo_sp['NU_NOTA_REDACAO']).to_numpy(dtype=float)
                cat = next(c for c in result['years']['2019']['recortes'][resp]['SP']['categories']
                           if c['codigo_ocupacao'] == cod)
                if not cat['suprimido']:
                    assert cat['n_redacoes'] == len(notas)
                    assert abs(cat['media'] - notas.mean()) < .00006
                    assert abs(cat['mediana'] - np.median(notas)) < .00006
                    assert abs(cat['q1'] - np.quantile(notas, .25)) < .00006
                    assert abs(cat['q3'] - np.quantile(notas, .75)) < .00006
        ref_incorreta = json.loads(json.dumps(ref))
        ref_incorreta['years']['2019']['recortes']['SP']['n_pop_socio_valid'] += 1
        g19, n19, _ = ler_mesma_linha(raw/'MICRODADOS_ENEM_2019.csv', 2019, 71)
        try:
            conferir_montar(2019, criar_brasil(g19), n19, ref_incorreta)
        except ValueError as exc:
            assert 'difere IND-045' in str(exc)
        else:
            raise AssertionError('Não detectou N incompatível com IND-045.')

        g1, n1, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 37)
        g2, n2, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 511)
        assert n1 == n2 == len(df)
        assert all(g1[k].hist == g2[k].hist and g1[k].n == g2[k].n for k in g1)

        inconsistentes = df[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].copy()
        inconsistentes.loc[0, 'NU_INSCRICAO'] = 'NAO_ENCONTRADA'
        inconsistentes.to_csv(raw/'SEM_VINCULO.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'SEM_VINCULO.csv', 57)
        except ValueError as exc:
            assert 'sem vínculo' in str(exc)
        else:
            raise AssertionError('Não detectou vínculo ausente.')
        repetidos = df[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q003', 'Q004']].copy()
        pd.concat([repetidos, repetidos.iloc[[0]]]).to_csv(
            raw/'DUPLICADOS.csv', sep=';', index=False)
        try:
            ler_2024(raw/'DUPLICADOS.csv', raw/'COMPETENCIAS_REDACAO_2024.csv', 103)
        except ValueError as exc:
            assert 'duplicada' in str(exc)
        else:
            raise AssertionError('Não detectou inscrição duplicada.')

        # A faixa pequena pode exigir supressão total se não houver complemento seguro.
        pequenos = defaultdict(Grupo)
        for uf in UFS:
            for resp in RESPONSAVEIS:
                for cod in CATEGORIAS:
                    n = 1 if uf == 'SP' else 50
                    notas = np.full(n, 600., dtype=float)
                    comps = np.full((n, 5), 120., dtype=float)
                    pequenos[(resp, uf, cod)].adicionar(notas, comps)
        pequenos = criar_brasil(pequenos)
        ref2 = json.loads(json.dumps(ref))
        for uf in ('BR', *UFS):
            n = sum(obter_grupo(pequenos, list(RESPONSAVEIS)[0], uf, c).n for c in CATEGORIAS)
            ref2['years']['2019']['recortes'][uf] = {
                'n_pop_socio_valid': n,
                'categories': [{'suprimido': False, 'n_redacoes': n, 'media': 600.}],
            }
        n = sum(obter_grupo(pequenos, list(RESPONSAVEIS)[0], 'BR', c).n for c in CATEGORIAS)
        ref2['years']['2019']['n_brasil'] = n
        rec_priv, val_priv = conferir_montar(2019, pequenos, n, ref2)
        assert all(len(val_priv['categorias_suprimidas_globalmente_por_responsavel'][r])
                   == len(CATEGORIAS) for r in RESPONSAVEIS)
        assert all(cat['suprimido'] for r in RESPONSAVEIS
                   for cat in rec_priv[r]['SP']['categories'])
    log('AUTOTESTE IND-049 APROVADO: categorias A–F, Q004 numérico rejeitado, '
        'estatísticas, N/UF/BR, supressão e complemento, join 2024, '
        'duplicatas, vínculo, CSV/JSON, dashboards e 2025 indisponível.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-049: Ocupação dos responsáveis × nota')
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
        print(f'ERRO IND-049: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
