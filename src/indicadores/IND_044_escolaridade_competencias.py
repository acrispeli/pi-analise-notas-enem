#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-044 — Escolaridade dos responsáveis × competências C1–C5.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores ENEM 2019–2025 v2.

Objetivo: médias e medianas das notas das competências C1–C5 por Q001
(pai/homem responsável) e Q002 (mãe/mulher responsável), por ano e UF da
prova, na população POP_SOCIO_VALID (a mesma do IND-043).

2019–2023: MICRODADOS_ENEM_<ano>.csv com UF, Q001/Q002 e notas finais.
2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv, vinculados
      exclusivamente por NU_INSCRICAO (SQLite temporário).
2025: INDISPONÍVEL para a vinculação pública de Q001/Q002 com C1–C5,
      conforme o catálogo. Não usar NU_SEQUENCIAL como chave substituta.

O IND-043 é OBRIGATÓRIO como referência para categorias, rótulos e N
agregados de cada Q001/Q002, UF e ano. Não se inferem notas individuais
ou estatísticas de competências a partir de médias da nota total do IND-043.

Saídas (sem backups .bak):
  outputs/json/IND_044_escolaridade_competencias.json
  outputs/indicadores/IND_044_escolaridade_competencias.csv
  outputs/json/dashboard_enem_<ano>.json
    pages.socioeconomic.parent_education_competencies
    quality.ind044_validation

Proteção de publicação: se uma categoria possuir uma célula com 1–29
redações em qualquer UF/BR, oculta-se essa categoria em todo o ano
para ambos os níveis geográficos da questão. Também se oculta uma
categoria complementar em toda a geografia para evitar reconstrução
pelo total agregado de competências (IND-009). A revisão de privacidade
cruzada permanece pendente; status de todos os resultados: draft.

A agregação de notas usa histogramas esparsos, sem armazenar microdados.
Quantis Hyndman–Fan tipo 7; desvio-padrão populacional (ddof=0).

Uso na raiz do projeto:
  python src/indicadores/IND_044_escolaridade_competencias.py --autoteste
  python src/indicadores/IND_044_escolaridade_competencias.py --anos 2024 --sobrescrever
  python src/indicadores/IND_044_escolaridade_competencias.py --sobrescrever

Dependências: numpy e pandas (ambiente de análise do projeto).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import filecmp
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG',
       'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR',
       'RS', 'SC', 'SE', 'SP', 'TO')
QUESTOES = ('Q001', 'Q002')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
NOTAS_COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
CODIGOS = set('ABCDEFGH')
MIN_N = 30
RESPONSAVEIS = {'Q001': 'Pai ou homem responsável',
                'Q002': 'Mãe ou mulher responsável'}
CAMPOS_CSV = (
    'ano', 'uf', 'questao', 'responsavel', 'codigo_escolaridade',
    'descricao_categoria', 'ordem', 'competencia', 'n_redacoes',
    'media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'percentual_total_validas', 'suprimido', 'motivo_supressao',
)


def log(mensagem: str) -> None:
    print(mensagem, flush=True)


def raiz_projeto() -> Path:
    local = Path(__file__).resolve()
    if local.parent.name.lower() == 'indicadores' and local.parent.parent.name.lower() == 'src':
        return local.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                     escolhas: dict[str, Path] | None = None) -> dict[str, Path]:
    """Permite cópias idênticas; rejeita versões divergentes sem caminho explícito."""
    nomes = {x.upper() for x in nomes}
    escolhas = {k.upper(): Path(v) for k, v in (escolhas or {}).items()}
    ignorar = {'.git', '.venv', 'venv', 'outputs', '__pycache__',
               'node_modules', '.pytest_cache', '.mypy_cache'}
    resultado: dict[str, Path] = {}
    for nome, informado in escolhas.items():
        if nome not in nomes:
            raise ValueError(f'Fonte explícita não solicitada: {nome}.')
        arquivo = informado.expanduser()
        if not arquivo.is_absolute():
            arquivo = base / arquivo
        arquivo = arquivo.resolve()
        if not arquivo.is_file():
            raise FileNotFoundError(f'Fonte indicada não existe: {arquivo}')
        resultado[nome] = arquivo
        log(f'  Fonte selecionada para {nome}: {arquivo}')
    for pasta, dirs, arquivos in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d.lower() not in ignorar)
        for nome in sorted(arquivos):
            chave = nome.upper()
            if chave not in nomes or chave in escolhas:
                continue
            arquivo = Path(pasta) / nome
            anterior = resultado.get(chave)
            if anterior is None:
                resultado[chave] = arquivo
            elif anterior.resolve() != arquivo.resolve():
                if filecmp.cmp(anterior, arquivo, shallow=False):
                    log(f'  Cópias idênticas de {chave}; usando {anterior}.')
                else:
                    flag = ('--competencias-2024' if chave == 'COMPETENCIAS_REDACAO_2024.CSV'
                            else '--participantes-2024' if chave == 'PARTICIPANTES_2024.CSV'
                            else 'uma fonte única (revise as cópias)')
                    raise ValueError(f'Fontes diferentes para {chave}: {anterior} e {arquivo}. '
                                     f'Escolha explicitamente com {flag}.')
    return resultado


def ler_blocos(arquivo: Path, colunas: list[str], bloco: int):
    with arquivo.open('rb') as f:
        encoding = 'utf-8-sig' if f.read(3) == b'\xef\xbb\xbf' else 'latin-1'
    colunas_originais = pd.read_csv(arquivo, sep=';', encoding=encoding, nrows=0).columns
    faltantes = sorted(set(colunas) - set(str(x).strip().lstrip('\ufeff') for x in colunas_originais))
    if faltantes:
        raise ValueError(f'{arquivo.name}: colunas ausentes {faltantes}')
    with pd.read_csv(arquivo, sep=';', encoding=encoding, dtype='string',
                     usecols=colunas, chunksize=bloco, na_filter=False,
                     keep_default_na=False, low_memory=False) as leitor:
        for parte in leitor:
            parte.columns = [str(c).strip().lstrip('\ufeff') for c in parte.columns]
            yield parte


def notas_validas(coluna: pd.Series, nome: str, minimo: float,
                   maximo: float) -> np.ndarray:
    texto = coluna.astype('string').str.strip().str.replace(',', '.', regex=False)
    valores = pd.to_numeric(texto, errors='coerce').to_numpy(dtype='float64')
    if not np.isfinite(valores).all() or ((valores < minimo) | (valores > maximo)).any():
        raise ValueError(f'{nome}: nota ausente/não numérica/fora de [{minimo},{maximo}] '
                         'em redação com TP_STATUS_REDACAO=1.')
    return valores


def selecionar_validas(df: pd.DataFrame) -> pd.DataFrame:
    validas = df.loc[df['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')].copy()
    if validas.empty:
        return validas
    validas['__nota_total'] = notas_validas(validas['NU_NOTA_REDACAO'],
                                            'NU_NOTA_REDACAO', 0, 1000)
    for c in NOTAS_COMP:
        validas[c] = notas_validas(validas[c], c, 0, 200)
    return validas


def codigo_escolaridade(value: Any) -> str:
    txt = '' if value is None else str(value).strip().upper()
    if not txt or txt in ('NAN', 'NULL', '<NA>'):
        return 'SEM_RESPOSTA'
    return txt if txt in CODIGOS else 'CODIGO_NAO_RECONHECIDO'


class Grupo:
    """Agrega histogramas esparsos das notas, contagens e diferenças de soma."""
    def __init__(self) -> None:
        self.n = 0
        self.hist = [Counter() for _ in range(5)]
        self.n_soma_divergente = 0
        self.delta_soma = 0.0

    def adicionar(self, notas: np.ndarray, totais: np.ndarray) -> None:
        if notas.ndim != 2 or notas.shape[1] != 5 or len(notas) != len(totais):
            raise ValueError('Grupo recebeu matriz de competências e totais incompatíveis.')
        self.n += len(notas)
        for i in range(5):
            valores, freq = np.unique(notas[:, i], return_counts=True)
            self.hist[i].update({float(v): int(n) for v, n in zip(valores, freq)})
        deltas = notas.sum(axis=1) - totais
        self.n_soma_divergente += int(np.count_nonzero(~np.isclose(deltas, 0, rtol=0, atol=1e-6)))
        self.delta_soma += float(math.fsum(deltas.tolist()))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        for i in range(5):
            self.hist[i].update(outro.hist[i])
        self.n_soma_divergente += outro.n_soma_divergente
        self.delta_soma += outro.delta_soma


def adicionar_lote(agregado: dict, df: pd.DataFrame) -> None:
    if df.empty:
        return
    ufs = df['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError('SG_UF_PROVA ausente ou inválida em POP_SOCIO_VALID.')
    notas = df[list(NOTAS_COMP)].to_numpy(dtype='float64')
    totais = df['__nota_total'].to_numpy(dtype='float64')
    for questao in QUESTOES:
        # Não ordenar Q001/Q002 como escala conjunta: são duas marginais.
        codes = df[questao].map(codigo_escolaridade)
        # indices de groupby são posicionais em DataFrame temporário.
        grupos = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codes.to_numpy()})
        for (uf, codigo), indices in grupos.groupby(['uf', 'codigo'], sort=False).indices.items():
            agregado[(str(uf), questao, str(codigo))].adicionar(notas[indices], totais[indices])


def ler_mesma_linha(arquivo: Path, bloco: int) -> tuple[dict, int, dict]:
    grupos = defaultdict(Grupo)
    n_validas = 0
    colunas = ['SG_UF_PROVA', 'Q001', 'Q002', 'TP_STATUS_REDACAO',
               'NU_NOTA_REDACAO', *NOTAS_COMP]
    for parte in ler_blocos(arquivo, colunas, bloco):
        validas = selecionar_validas(parte)
        n_validas += len(validas)
        adicionar_lote(grupos, validas)
    return dict(grupos), n_validas, {'metodo': 'mesma_linha', 'fonte': arquivo.name}


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Faz join 2024 via NU_INSCRICAO, sem unir dados por posição/sequência."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind044_') as pasta:
        db = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes (id TEXT PRIMARY KEY, uf TEXT NOT NULL, '
                       'q1 TEXT NOT NULL, q2 TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE vistas (id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote (pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ler_blocos(participantes, ['NU_INSCRICAO', 'SG_UF_PROVA',
                                                    'Q001', 'Q002'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                q1 = parte['Q001'].astype('string').str.strip().tolist()
                q2 = parte['Q002'].astype('string').str.strip().tolist()
                if any(not v for v in ids) or any(v not in UFS for v in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?,?)',
                                   zip(ids, ufs, q1, q2))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from exc
                n_participantes += len(ids)
            db.commit()
            log(f'  2024: participantes indexados: {n_participantes:,}')
            n_validas = 0
            n_vinculadas = 0
            colunas = ['NU_INSCRICAO', 'TP_STATUS_REDACAO',
                       'NU_NOTA_REDACAO', *NOTAS_COMP]
            for parte in ler_blocos(competencias, colunas, bloco):
                validas = selecionar_validas(parte)
                n_validas += len(validas)
                if validas.empty:
                    continue
                ids = validas['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not v for v in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em redação válida.')
                try:
                    db.executemany('INSERT INTO vistas VALUES (?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: NU_INSCRICAO duplicada em redação válida.') from exc
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?, ?)', enumerate(ids))
                linhas = db.execute('''SELECT l.pos, p.uf, p.q1, p.q2
                                      FROM lote l JOIN participantes p ON l.id=p.id''').fetchall()
                if len(linhas) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(linhas)} redações válidas '
                                     'sem vínculo em PARTICIPANTES_2024.')
                # Mesmo que o join reordene as linhas, a posição explícita
                # garante alinhamento exato de UF/Q001/Q002 às notas.
                atributos = [None] * len(ids)
                for pos, uf, q1, q2 in linhas:
                    atributos[pos] = (uf, q1, q2)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [x[0] for x in atributos]
                validas['Q001'] = [x[1] for x in atributos]
                validas['Q002'] = [x[2] for x in atributos]
                adicionar_lote(grupos, validas)
                n_vinculadas += len(linhas)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'n_participantes': n_participantes,
                'n_redacoes_validas_vinculadas': n_vinculadas,
                'n_validas_sem_correspondencia': 0,
                'chave_unica_participantes': True,
                'chave_unica_redacoes_validas': True,
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    brasil = defaultdict(Grupo)
    for (uf, q, cod), item in grupos.items():
        if uf not in UFS:
            raise ValueError(f'UF inesperada: {uf}')
        brasil[('BR', q, cod)].combinar(item)
    return {**grupos, **brasil}


def quantil_hf7(hist: Counter, p: float) -> float:
    """Quantil exato de distribuição discreta/numérica via histograma ordenado."""
    if not 0 <= p <= 1:
        raise ValueError('p deve estar entre 0 e 1.')
    n = sum(hist.values())
    if not n:
        raise ValueError('Não existe quantil para N=0.')
    valores = sorted(hist)
    acumuladas = np.cumsum([hist[v] for v in valores], dtype='int64')

    def posicao(indice: int) -> float:
        return float(valores[int(np.searchsorted(acumuladas, indice + 1, side='left'))])

    rank = (n - 1) * p
    esquerda = int(math.floor(rank))
    direita = min(esquerda + 1, n - 1)
    peso = rank - esquerda
    return posicao(esquerda) * (1 - peso) + posicao(direita) * peso


def estatisticas_hist(hist: Counter, n: int) -> dict:
    if n == 0:
        return {k: None for k in ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')}
    if sum(hist.values()) != n:
        raise ValueError('Histograma de notas não fecha com N da categoria.')
    media = math.fsum(float(v) * int(q) for v, q in hist.items()) / n
    variancia = math.fsum((float(v) - media) ** 2 * int(q) for v, q in hist.items()) / n
    q1, mediana, q3 = (quantil_hf7(hist, p) for p in (0.25, 0.5, 0.75))
    return {
        'media': round(media, 4), 'mediana': round(mediana, 4),
        'q1': round(q1, 4), 'q3': round(q3, 4),
        'iqr': round(q3 - q1, 4),
        'desvio_padrao': round(math.sqrt(max(0.0, variancia)), 4),
    }


def ler_referencia(base: Path, fornecida: Path | None = None) -> dict:
    origem = fornecida or base/'outputs'/'json'/'IND_043_escolaridade_responsaveis_nota.json'
    origem = origem if origem.is_absolute() else base / origem if fornecida else origem
    if not origem.is_file():
        raise FileNotFoundError('Referência IND-043 não encontrada em '
                                f'{origem}. Execute o IND-043 antes ou informe --referencia-ind043.')
    with origem.open('r', encoding='utf-8-sig') as f:
        ref = json.load(f)
    if ref.get('indicator_id') != 'IND-043' or ref.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('A referência fornecida não é o IND-043 POP_SOCIO_VALID.')
    return ref


def conferir_e_montar(ano: int, grupos: dict, n_validas: int,
                       referencia: dict) -> tuple[dict, dict]:
    year = referencia.get('years', {}).get(str(ano), {})
    if year.get('status') != 'ok':
        raise ValueError(f'IND-043/{ano} está indisponível; não foi possível reconciliar IND-044.')
    esperado = year.get('recortes', {})
    if set(esperado) != {'BR', *UFS}:
        raise ValueError(f'IND-043/{ano}: esperado Brasil + 27 UFs.')
    if n_validas != esperado['BR']['n_pop_socio_valid']:
        raise ValueError(f'{ano}: POP_SOCIO_VALID={n_validas:,} difere '
                         f'do IND-043 ({esperado["BR"]["n_pop_socio_valid"]:,}).')
    # Validar TODOS os grupos antes de construir resultados públicos.
    for uf in ('BR', *UFS):
        refuf = esperado[uf]
        for q in QUESTOES:
            estrutura = refuf['questions'][q]
            categorias = {c['codigo_escolaridade']: c for c in estrutura['categories']}
            if len(categorias) != len(estrutura['categories']):
                raise ValueError(f'IND-043/{ano}/{uf}/{q}: códigos duplicados.')
            publicados = {cod for (geo, ques, cod), grupo in grupos.items()
                          if geo == uf and ques == q and grupo.n > 0}
            if not publicados.issubset(categorias):
                raise ValueError(f'{ano}/{uf}/{q}: categorias ausentes no IND-043: '
                                 f'{sorted(publicados - set(categorias))}')
            n = 0
            for cod, refc in categorias.items():
                grupo = grupos.get((uf, q, cod), Grupo())
                n += grupo.n
                if grupo.n != refc['n_redacoes']:
                    raise ValueError(f'{ano}/{uf}/{q}/{cod}: N={grupo.n} difere '
                                     f'do IND-043 ({refc["n_redacoes"]}).')
                if any(sum(grupo.hist[i].values()) != grupo.n for i in range(5)):
                    raise ValueError(f'{ano}/{uf}/{q}/{cod}: C1–C5 não fecham com N.')
                if grupo.n:
                    media_comp = sum(
                        math.fsum(v * c for v, c in grupo.hist[i].items())
                        for i in range(5)) / grupo.n
                    # Diferença explícita C1+...+C5 - nota final, registrada
                    # sem alterar valores (exceção conhecida em 2023).
                    previsto = refc['media'] + grupo.delta_soma / grupo.n
                    if not math.isclose(media_comp, previsto, abs_tol=0.00015, rel_tol=0):
                        raise ValueError(f'{ano}/{uf}/{q}/{cod}: média total calculada '
                                         'das cinco competências não coincide com IND-043 '
                                         'após considerar divergências da fonte.')
            if n != refuf['n_pop_socio_valid']:
                raise ValueError(f'{ano}/{uf}/{q}: soma das categorias não fecha com população.')
    if any((q not in QUESTOES or uf not in ('BR', *UFS))
           for uf, q, cod in grupos):
        raise ValueError('Grupos adicionais inesperados na origem.')

    # Supressão coerente geograficamente: qualquer categoria com N de 1..29
    # em BR/UF fica suprimida globalmente (para aquela pergunta/ano).
    # Uma segunda categoria é suprimida em toda a geografia para evitar
    # inferência pelo agregado de competências de um recorte/IND-009.
    motivos: dict[str, dict[str, str]] = {}
    for q in QUESTOES:
        categorias_pequenas = {
            cat for uf in ('BR', *UFS)
            for cat, g in ((c['codigo_escolaridade'], grupos.get(
                (uf, q, c['codigo_escolaridade']), Grupo()))
                for c in esperado[uf]['questions'][q]['categories'])
            if 0 < g.n < MIN_N
        }
        sup = {cod: 'primaria_grupo_pequeno_em_alguma_uf' for cod in categorias_pequenas}
        if categorias_pequenas:
            # H é resposta 'não sei', não é escolaridade ordinal. Seu bloqueio
            # mantém completas as categorias de escolaridade A–G sempre que possível.
            codigos_nacionais = [c['codigo_escolaridade'] for c in
                                 esperado['BR']['questions'][q]['categories']]
            preferencias = ['H', 'A', 'E', 'F', 'G', 'D', 'C', 'B']
            complemento = next((c for c in preferencias if c in codigos_nacionais
                                and c not in sup and grupos.get(('BR', q, c), Grupo()).n >= MIN_N), None)
            if complemento is None:
                raise ValueError(f'{ano}/{q}: não há categoria para supressão complementar.')
            sup[complemento] = 'complementar_contra_inferencia_por_totais'
        motivos[q] = sup

    recortes = {}
    total_suprimidas = 0
    for uf in ('BR', *UFS):
        n_uf = esperado[uf]['n_pop_socio_valid']
        perguntas = {}
        for q in QUESTOES:
            itens = []
            for refc in esperado[uf]['questions'][q]['categories']:
                cod = refc['codigo_escolaridade']
                grupo = grupos.get((uf, q, cod), Grupo())
                motivo = motivos[q].get(cod)
                oculto = motivo is not None
                if oculto:
                    total_suprimidas += 1
                comp = {
                    c: ({'n_redacoes': None, **{k: None for k in
                          ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')}}
                        if oculto else {'n_redacoes': grupo.n,
                                        **estatisticas_hist(grupo.hist[i], grupo.n)})
                    for i, c in enumerate(COMPETENCIAS)
                }
                itens.append({
                    'codigo_escolaridade': cod,
                    'descricao_categoria': refc['descricao_categoria'],
                    'ordem': refc['ordem'],
                    'eh_nivel_escolaridade': refc['eh_nivel_escolaridade'],
                    'resposta_nao_sei': refc['resposta_nao_sei'],
                    'n_redacoes': None if oculto else grupo.n,
                    'percentual_total_validas': None if oculto or not n_uf else round(100*grupo.n/n_uf, 6),
                    'suprimido': oculto,
                    'motivo_supressao': motivo,
                    'competencias': comp,
                })
            perguntas[q] = {
                'questao': q,
                'responsavel': RESPONSAVEIS[q],
                'n_redacoes_validas': n_uf,
                'categories': itens,
                'status_publicacao': 'draft_revisao_academica_privacidade_cruzada_pendente',
            }
        recortes[uf] = {'uf': uf, 'n_pop_socio_valid': n_uf,
                        'population': 'POP_SOCIO_VALID', 'questions': perguntas}
    # Contagem de divergências uma única vez: Brasil, Q001 (não somar Q002).
    total_divergencias = sum(grupos.get(('BR', 'Q001', c['codigo_escolaridade']), Grupo()).n_soma_divergente
                            for c in esperado['BR']['questions']['Q001']['categories'])
    controle = {
        'n_pop_socio_valid_brasil': n_validas,
        'indicador_referencia': 'IND-043',
        'populacao_e_categorias_uf_br_conferidas': True,
        'medias_c1_c5_conferidas_com_nota_total_ind043': True,
        'n_redacoes_com_soma_competencias_divergente': total_divergencias,
        'categorias_suprimidas_globalmente': motivos,
        'categorias_geograficas_suprimidas': total_suprimidas,
        'revisao_privacidade_cruzada_pendente': True,
    }
    return recortes, controle


def salvar_json(caminho: Path, conteudo: Any) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix=caminho.name+'.', suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            json.dump(conteudo, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write('\n')
        os.replace(temp, caminho)
    finally:
        if temp:
            temp.unlink(missing_ok=True)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            writer = csv.DictWriter(f, delimiter=';', fieldnames=CAMPOS_CSV,
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(linhas)
        os.replace(temp, caminho)
    finally:
        if temp:
            temp.unlink(missing_ok=True)


def linhas_csv(dados: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(dados.items(), key=lambda x: int(x[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            for q in QUESTOES:
                for cat in obj['recortes'][uf]['questions'][q]['categories']:
                    for c in COMPETENCIAS:
                        linhas.append({
                            'ano': int(ano), 'uf': uf, 'questao': q,
                            'responsavel': RESPONSAVEIS[q],
                            'codigo_escolaridade': cat['codigo_escolaridade'],
                            'descricao_categoria': cat['descricao_categoria'],
                            'ordem': cat['ordem'], 'competencia': c,
                            'n_redacoes': cat['n_redacoes'],
                            **{k: cat['competencias'][c][k] for k in
                               ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')},
                            'percentual_total_validas': cat['percentual_total_validas'],
                            'suprimido': cat['suprimido'],
                            'motivo_supressao': cat['motivo_supressao'],
                        })
    return linhas


def integrar_dashboards(saida: Path, novos: dict[str, dict]) -> None:
    for texto, dados in sorted(novos.items(), key=lambda x: int(x[0])):
        if dados.get('status') != 'ok':
            continue
        ano = int(texto)
        arquivo = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not arquivo.is_file():
            log(f'  Dashboard {ano} ausente; integração ignorada.')
            continue
        doc = json.loads(arquivo.read_text(encoding='utf-8-sig'))
        pagina = doc.get('pages', {}).get('socioeconomic')
        if not isinstance(pagina, dict):
            raise ValueError(f'{arquivo.name}: pages.socioeconomic ausente ou inválida.')
        rec = dados['recortes']
        pagina['parent_education_competencies'] = {
            'indicator_id': 'IND-044', 'status': 'draft',
            'population': 'POP_SOCIO_VALID', 'year': ano,
            'source_questions': ['Q001', 'Q002'],
            'national': rec['BR'],
            'states': {uf: rec[uf] for uf in UFS},
            'method': 'média e mediana C1..C5 por Q001/Q002 e UF; POP_SOCIO_VALID',
            'privacy_note': ('Grupos e categorias complementares suprimidos; '
                             'revisão acadêmica e de privacidade cruzada pendentes.'),
        }
        doc.setdefault('quality', {})['ind044_validation'] = {
            'status': 'ok_agregados', **dados['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-044: escolaridade dos responsáveis × competências C1–C5; '
                 'supressão complementar aplicada e revisão de privacidade cruzada pendente.')
        warns = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in warns:
            warns.append(aviso)
        salvar_json(arquivo, doc)
        log(f'  Dashboard {ano} integrado sem .bak.')


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_path: Path | None = None,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base = base.resolve()
    saida = saida.resolve()
    arq_json = saida/'outputs'/'json'/'IND_044_escolaridade_competencias.json'
    arq_csv = saida/'outputs'/'indicadores'/'IND_044_escolaridade_competencias.csv'
    if not sobrescrever and (arq_json.exists() or arq_csv.exists()):
        raise FileExistsError('IND-044 já existe. Use --sobrescrever para atualizar.')
    referencia = ler_referencia(base, referencia_path)
    nomes = set()
    for ano in anos:
        if ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = localizar_fontes(base, nomes, fontes_explicitas)
    faltantes = sorted(nomes - set(fontes))
    if faltantes:
        raise FileNotFoundError('Fontes necessárias não encontradas: '+', '.join(faltantes))
    anteriores = {}
    if sobrescrever and arq_json.exists():
        anterior = json.loads(arq_json.read_text(encoding='utf-8-sig'))
        if anterior.get('indicator_id') != 'IND-044':
            raise ValueError('Arquivo JSON pré-existente não pertence ao IND-044.')
        anteriores = dict(anterior.get('years', {}))
    todos = dict(anteriores)
    processados: dict[str, dict] = {}
    for ano in anos:
        log(f'IND-044 | {ano}: escolaridade × C1–C5 em POP_SOCIO_VALID...')
        if ano == 2025:
            dados = {'ano': ano, 'status': 'indisponivel',
                     'reason': 'Fontes públicas sem chave comum para vincular escolaridade Q001/Q002 e C1–C5.',
                     'recortes': {}}
            todos[str(ano)] = processados[str(ano)] = dados
            log('  2025 indisponível: nenhuma estatística foi estimada.')
            continue
        if ano == 2024:
            grupos, n_validas, diag = ler_2024(fontes['PARTICIPANTES_2024.CSV'],
                                               fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            key = f'MICRODADOS_ENEM_{ano}.CSV'
            grupos, n_validas, diag = ler_mesma_linha(fontes[key], bloco)
            fonte = fontes[key].name
        grupos = criar_brasil(grupos)
        recortes, controle = conferir_e_montar(ano, grupos, n_validas, referencia)
        if diag.get('n_redacoes_validas_vinculadas', n_validas) != n_validas:
            raise ValueError(f'{ano}: redações válidas vinculadas não fecham com POP_SOCIO_VALID.')
        dados = {'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
                 'fonte': fonte, 'n_brasil': n_validas,
                 'diagnostico_juncao': diag, 'validacao': controle,
                 'recortes': recortes}
        todos[str(ano)] = processados[str(ano)] = dados
        log(f'  {ano}: N BR={n_validas:,}; categorias geográficas suprimidas='
            f'{controle["categorias_geograficas_suprimidas"]}; IND-043=aprovado.')
    modulo = {
        'indicator_id': 'IND-044',
        'titulo': 'Escolaridade dos responsáveis × competências da redação',
        'status': 'draft', 'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(y) for y, d in todos.items() if d.get('status') == 'ok'),
        'population': 'POP_SOCIO_VALID', 'geography': 'SG_UF_PROVA',
        'methodology': {
            'Q001': 'Escolaridade do pai/homem responsável',
            'Q002': 'Escolaridade da mãe/mulher responsável',
            'categories': 'A–G nível escolar; H não sei; SEM_RESPOSTA separado; categoria inválida separada',
            'selection': 'TP_STATUS_REDACAO=1 e nota total válida em [0,1000], C1..C5 válidas em [0,200]',
            'statistics': 'média, mediana, quartis, IQR e desvio-padrão populacional para C1..C5',
            'quantile_method': 'Hyndman-Fan tipo 7, sobre notas exatas',
            'source_2024': 'PARTICIPANTES_2024 + COMPETENCIAS_REDACAO_2024 por NU_INSCRICAO',
            'reference': 'IND-043 para contagens/categorias e coerência com nota total',
            'privacy': 'supressão global da categoria se célula pequena em alguma UF + outra categoria complementar',
            'interpretation': 'análise descritiva de associação, não inferência causal',
            '2025': 'indisponível por ausência de vínculo público entre as fontes',
            'cautions': [
                'Q001 e Q002 são marginais separadas, não se somam como participantes distintos.',
                'H (Não sei) não é escolaridade ordinal.',
                'UF de prova não corresponde necessariamente à residência.',
                'Histórico conta participações anuais, não indivíduos únicos.',
                'Dados em status draft; revisão acadêmica e privacidade cruzada pendentes.',
            ],
        },
        'years': todos,
    }
    salvar_json(arq_json, modulo)
    salvar_csv(arq_csv, linhas_csv(todos))
    if not somente_modulo:
        integrar_dashboards(saida, processados)
    log(f'IND-044 concluído. JSON: {arq_json} | CSV: {arq_csv}')
    return modulo


def autoteste() -> None:
    """Autoteste pequeno, com duas perguntas, histogramas, joins e dashboard."""
    import shutil
    with tempfile.TemporaryDirectory(prefix='teste_ind044_') as rootstr:
        raiz = Path(rootstr)
        (raiz/'bases').mkdir()
        (raiz/'outputs/json').mkdir(parents=True)
        linhas = []
        for i in range(140):
            uf = 'SP' if i < 70 else 'RJ'
            q1 = 'A' if i % 2 == 0 else 'H'
            q2 = 'B' if i % 2 == 0 else 'G'
            notas = [120 + (i % 3)*20, 160, 200, 160, 180]
            linhas.append({
                'NU_INSCRICAO': str(i+10000), 'SG_UF_PROVA': uf,
                'Q001': q1, 'Q002': q2, 'TP_STATUS_REDACAO': '1',
                'NU_NOTA_REDACAO': str(sum(notas)),
                **{NOTAS_COMP[j]: str(notas[j]) for j in range(5)},
            })
        df = pd.DataFrame(linhas)
        micro = raiz/'bases/MICRODADOS_ENEM_2019.csv'
        df.to_csv(micro, sep=';', index=False)
        part = raiz/'bases/PARTICIPANTES_2024.csv'
        comp = raiz/'bases/COMPETENCIAS_REDACAO_2024.csv'
        df[['NU_INSCRICAO','SG_UF_PROVA','Q001','Q002']].iloc[::-1].to_csv(part, sep=';', index=False)
        df[['NU_INSCRICAO','TP_STATUS_REDACAO','NU_NOTA_REDACAO',*NOTAS_COMP]].to_csv(comp, sep=';', index=False)
        copia = raiz/'bases/competencias_redacao/COMPETENCIAS_REDACAO_2024.csv'
        copia.parent.mkdir()
        shutil.copyfile(comp, copia)
        check = localizar_fontes(raiz, {'COMPETENCIAS_REDACAO_2024.CSV'})
        assert check['COMPETENCIAS_REDACAO_2024.CSV'] == comp
        # Preparação sintética do IND-043, contendo todas as 27 UFs.
        grupos, validas, _ = ler_mesma_linha(micro, 29)
        grupos = criar_brasil(grupos)
        ref = {'indicator_id': 'IND-043', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano in (2019, 2024):
            recortes = {}
            for uf in ('BR', *UFS):
                qs = {}
                n = sum(grupos.get((uf,'Q001',c),Grupo()).n for c in ['A','H'])
                for q in QUESTOES:
                    cats=[]
                    for ord_, cod in enumerate('ABCDEFGH'):
                        g=grupos.get((uf,q,cod),Grupo())
                        if g.n:
                            nt=sum(math.fsum(v*qq for v,qq in g.hist[k].items()) for k in range(5)) / g.n
                            med=round(nt,4)
                        else:
                            med=None
                        cats.append({'codigo_escolaridade': cod,
                                     'descricao_categoria': f'Categoria {cod}',
                                     'ordem':ord_, 'eh_nivel_escolaridade':cod in 'ABCDEFG',
                                     'resposta_nao_sei':cod=='H', 'n_redacoes':g.n,
                                     'media':med})
                    qs[q]={'categories':cats}
                recortes[uf]={'n_pop_socio_valid':n,'questions':qs}
            ref['years'][str(ano)]={'status':'ok','recortes':recortes}
        caminho_ref = raiz/'outputs/json/IND_043_escolaridade_responsaveis_nota.json'
        salvar_json(caminho_ref, ref)
        for ano in (2019,2024):
            salvar_json(raiz/f'outputs/json/dashboard_enem_{ano}.json',
                        {'pages': {'socioeconomic':{'outro_indicador':'preservar'}},
                         'quality':{'outro_controle':'preservar'}, 'meta':{'warnings':[]}})
        modulo=executar(raiz, raiz, (2019,2024,2025), 27, False, False)
        assert modulo['years']['2019']['n_brasil']==140
        assert modulo['years']['2024']['n_brasil']==140
        assert modulo['years']['2025']['status']=='indisponivel'
        for ano in (2019,2024):
            br=modulo['years'][str(ano)]['recortes']['BR']['questions']['Q001']['categories']
            categoria_a=next(x for x in br if x['codigo_escolaridade']=='A')
            assert not categoria_a['suprimido']
            assert categoria_a['competencias']['C1']['n_redacoes']==70
            assert categoria_a['competencias']['C2']['media']==160
            doc=json.loads((raiz/f'outputs/json/dashboard_enem_{ano}.json').read_text())
            assert doc['pages']['socioeconomic']['parent_education_competencies']['indicator_id']=='IND-044'
            assert doc['pages']['socioeconomic']['outro_indicador']=='preservar'
            assert doc['quality']['outro_controle']=='preservar'
        assert not list(raiz.rglob('*.bak*'))
        with (raiz/'outputs/indicadores/IND_044_escolaridade_competencias.csv').open(
                encoding='utf-8-sig',newline='') as f:
            assert len(list(csv.DictReader(f,delimiter=';')))==2*28*2*8*5
        log('Autoteste IND-044 aprovado: estatísticas, categorias, 2024/NU_INSCRICAO, '
            'cópias idênticas, JSON/CSV, 2025 indisponível e dashboards.')


def main() -> None:
    p = argparse.ArgumentParser(description='IND-044 — Escolaridade × competências C1–C5')
    p.add_argument('--base', type=Path, default=raiz_projeto(),
                   help='Raiz de busca dos microdados CSV e IND-043')
    p.add_argument('--saida', type=Path, default=raiz_projeto(),
                   help='Pasta raiz dos outputs; padrão: raiz do projeto')
    p.add_argument('--referencia-ind043', type=Path, default=None)
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    p.add_argument('--bloco', type=int, default=100_000)
    p.add_argument('--sobrescrever', action='store_true')
    p.add_argument('--somente-modulo', action='store_true',
                   help='Não atualizar dashboards')
    p.add_argument('--competencias-2024', type=Path, default=None,
                   help='Selecionar cópia de competências caso existam versões diferentes')
    p.add_argument('--participantes-2024', type=Path, default=None,
                   help='Selecionar cópia de participantes caso existam versões diferentes')
    p.add_argument('--autoteste', action='store_true')
    a = p.parse_args()
    if a.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(a.anos)))
    if not anos or any(y not in ANOS for y in anos):
        p.error('Use --anos com valores entre 2019 e 2025.')
    if a.bloco < 1:
        p.error('--bloco precisa ser positivo.')
    escolhas = {}
    if a.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = a.competencias_2024
    if a.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = a.participantes_2024
    try:
        executar(a.base, a.saida, anos, a.bloco, a.sobrescrever,
                 a.somente_modulo, a.referencia_ind043, escolhas)
    except (OSError, ValueError, KeyError, sqlite3.DatabaseError,
            json.JSONDecodeError) as exc:
        print(f'ERRO IND-044: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
