#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-042 | Renda familiar x competências C1–C5 da redação (ENEM 2019–2025).

Projeto Integrador IV — UNIVESP. Implementação baseada no catálogo v2.0.

Objetivo: comparar N, média e mediana das notas FINAIS de C1 a C5 por
categoria A–Q de renda familiar, por ano, Brasil e 27 UFs de prova.

Fontes: 2019–2023 MICRODADOS_ENEM_ano.csv (Q006 e notas no mesmo registro).
        2024 PARTICIPANTES_2024.csv (Q007 e SG_UF_PROVA) +
             COMPETENCIAS_REDACAO_2024.csv (C1–C5 finais e situação),
             junção unicamente por NU_INSCRICAO (máscara compartilhada).
        2025 INDISPONÍVEL: PARTICIPANTES e RESULTADOS não possuem chave
             pública de relacionamento individual. NÃO cruzar por posição.

População: TP_STATUS_REDACAO=1 e NU_NOTA_REDACAO em [0,1000]. Verifica que
as cinco notas finais por competência estão em [0,200], sem imputação.
Categorias de renda não declarada ou inválida não são excluídas. Pequenas
contagens são assinaladas para cautela estatística, sem bloqueio automático.
Não são publicados registros individuais, IDs nem tabelas de coocorrências.

Comandos (na raiz do projeto):
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_042_renda_competencias.py --anos 2024 --sobrescrever
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_042_renda_competencias.py --sobrescrever
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_042_renda_competencias.py --somente-modulo --sobrescrever

Saídas: outputs/json/IND_042_renda_competencias.json
        outputs/indicadores/IND_042_renda_competencias.csv
        pages.socioeconomic.income_competencies em dashboards existentes.

Requer: pandas. O programa lê os CSVs em blocos e usa SQLite temporário na
junção 2024. Não usa aprendizagem de máquina: é estatística descritiva.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
       'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO')
CODIGOS = tuple('ABCDEFGHIJKLMNOPQ')
SEM_RENDA = 'SEM_RESPOSTA'
RENDA_INVALIDA = 'CODIGO_NAO_RECONHECIDO'
CATEGORIAS = (*CODIGOS, SEM_RENDA, RENDA_INVALIDA)
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
COLUNAS_COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
POPULACAO_BR_REFERENCIA = {
    2019: 3_779_356, 2020: 2_674_914, 2021: 2_293_797,
    2022: 2_363_615, 2023: 2_704_814, 2024: 3_002_710,
}
BASE_RENDA_ANO = {
    2019: Decimal('998.00'), 2020: Decimal('1045.00'),
    2021: Decimal('1100.00'), 2022: Decimal('1212.00'),
    2023: Decimal('1320.00'), 2024: Decimal('1412.00'),
}
MULTIPLICADORES = {
    'B': Decimal('1'), 'C': Decimal('1.5'), 'D': Decimal('2'),
    'E': Decimal('2.5'), 'F': Decimal('3'), 'G': Decimal('4'),
    'H': Decimal('5'), 'I': Decimal('6'), 'J': Decimal('7'),
    'K': Decimal('8'), 'L': Decimal('9'), 'M': Decimal('10'),
    'N': Decimal('12'), 'O': Decimal('15'), 'P': Decimal('20'),
}

# Frequências de notas FINAIS exatas por (UF, faixa, competência).
Hist = dict[tuple[str, str, str], Counter]


def log(texto: str) -> None:
    print(texto, flush=True)


def raiz_projeto() -> Path:
    atual = Path(__file__).resolve()
    if atual.parent.name.lower() == 'indicadores' and atual.parent.parent.name.lower() == 'src':
        return atual.parents[2]
    return Path.cwd().resolve()


def achar_arquivos(base: Path, nomes: set[str]) -> dict[str, Path]:
    ignorar = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
               'node_modules', '.mypy_cache', 'outputs'}
    encontrados: dict[str, Path] = {}
    for diretorio, dirs, arquivos in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in ignorar]
        for nome in arquivos:
            chave = nome.upper()
            if chave in nomes:
                novo = Path(diretorio) / nome
                antigo = encontrados.get(chave)
                if antigo is not None and antigo.resolve() != novo.resolve():
                    raise ValueError(f'Fontes duplicadas: {antigo} e {novo}. Ajuste --base.')
                encontrados[chave] = novo
        if len(encontrados) == len(nomes):
            break
    return encontrados


def codificar_renda(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return SEM_RENDA
    txt = str(valor).strip().upper()
    if txt in {'', 'NULL', 'NONE', 'NAN', 'NA', 'N/A', '(VAZIO)'}:
        return SEM_RENDA
    return txt if txt in CODIGOS else RENDA_INVALIDA


def brl(valor: Decimal) -> str:
    return 'R$ ' + f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def rotulo_renda(ano: int, codigo: str) -> str:
    if codigo == SEM_RENDA:
        return 'Renda não informada'
    if codigo == RENDA_INVALIDA:
        return 'Código de renda não reconhecido'
    if codigo == 'A':
        return 'Nenhuma renda'
    base = BASE_RENDA_ANO[ano]
    if codigo == 'B':
        return f'Até {brl(base)}'
    if codigo == 'Q':
        return f'Acima de {brl(base * Decimal(20))}'
    anterior = CODIGOS[CODIGOS.index(codigo) - 1]
    return f'De {brl(base * MULTIPLICADORES[anterior] + Decimal("0.01"))} até {brl(base * MULTIPLICADORES[codigo])}'


def ordem_renda(cod: str) -> int:
    return CODIGOS.index(cod) if cod in CODIGOS else 17 if cod == SEM_RENDA else 18


def encoding_csv(caminho: Path) -> str:
    with caminho.open('rb') as f:
        return 'utf-8-sig' if f.read(3) == b'\xef\xbb\xbf' else 'latin-1'


def iterar_csv(caminho: Path, colunas: list[str], bloco: int):
    enc = encoding_csv(caminho)
    cab = pd.read_csv(caminho, sep=';', encoding=enc, nrows=0)
    campos = [str(x).strip().lstrip('\ufeff') for x in cab.columns]
    ausentes = sorted(set(colunas) - set(campos))
    if ausentes:
        raise ValueError(f'{caminho}: colunas ausentes {ausentes}; existentes: {campos}')
    for parte in pd.read_csv(
        caminho, sep=';', encoding=enc, usecols=colunas,
        dtype='string', chunksize=bloco, low_memory=False,
        na_filter=False, keep_default_na=False,
    ):
        parte.columns = [str(c).strip().lstrip('\ufeff') for c in parte.columns]
        yield parte


def preparar_validas(parte: pd.DataFrame) -> pd.DataFrame:
    valido = parte['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1').fillna(False)
    dados = parte.loc[valido].copy()
    if dados.empty:
        return dados
    numericas = ('NU_NOTA_REDACAO', *COLUNAS_COMP)
    for coluna in numericas:
        serie = dados[coluna].astype('string').str.strip().str.replace(',', '.', regex=False)
        num = pd.to_numeric(serie, errors='coerce').astype('float64')
        limite = 1000 if coluna == 'NU_NOTA_REDACAO' else 200
        invalida = (~num.map(math.isfinite)) | (num < 0) | (num > limite)
        if invalida.any():
            raise ValueError(f'{coluna}: {int(invalida.sum())} valores inválidos entre redações com status 1')
        dados[coluna] = num
    if 'SG_UF_PROVA' in dados:
        dados['uf'] = dados['SG_UF_PROVA'].astype('string').str.strip().str.upper()
        if (~dados['uf'].isin(UFS)).any():
            raise ValueError('Encontradas redações válidas com SG_UF_PROVA ausente ou desconhecida.')
    return dados


def agregar_lote(hist: Hist, lote: pd.DataFrame) -> int:
    if lote.empty:
        return 0
    for i, campo in enumerate(COLUNAS_COMP, 1):
        agrupamento = lote.groupby(['uf', 'renda', campo], sort=False, dropna=False).size()
        for (uf, renda, nota), n in agrupamento.items():
            chave = (str(uf), str(renda), f'C{i}')
            hist[chave][float(nota)] += int(n)
            hist[('BR', str(renda), f'C{i}')][float(nota)] += int(n)
    return len(lote)


def acumular_divergencias(lote: pd.DataFrame, diverg: dict[str, dict[str, float | int]]) -> None:
    if lote.empty:
        return
    delta = lote[list(COLUNAS_COMP)].sum(axis=1) - lote['NU_NOTA_REDACAO']
    mask = delta.abs() > 1e-6
    if not mask.any():
        return
    afetados = lote.loc[mask, ['uf']].copy()
    afetados['delta'] = delta.loc[mask]
    for uf, g in afetados.groupby('uf'):
        n = len(g)
        total = float(g['delta'].sum())
        for geo in ('BR', str(uf)):
            diverg[geo]['n'] += n
            diverg[geo]['soma_delta'] += total


def processar_2019_2023(ano: int, caminho: Path, bloco: int) -> tuple[Hist, int, dict]:
    hist: Hist = defaultdict(Counter)
    diverg = defaultdict(lambda: {'n': 0, 'soma_delta': 0.0})
    total = 0
    campos = ['SG_UF_PROVA', 'Q006', 'TP_STATUS_REDACAO',
              'NU_NOTA_REDACAO', *COLUNAS_COMP]
    for parte in iterar_csv(caminho, campos, bloco):
        validas = preparar_validas(parte)
        if validas.empty:
            continue
        validas['renda'] = validas['Q006'].map(codificar_renda)
        total += agregar_lote(hist, validas)
        acumular_divergencias(validas, diverg)
    return hist, total, dict(diverg)


def processar_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[Hist, int, dict]:
    """Vincula participantes e notas FINAIS usando chave pública mascarada.

    SQLite impede junções por ordem de linha, exige unicidade e verifica cada
    correspondência. Não exporta inscrições nem dados individuais.
    """
    hist: Hist = defaultdict(Counter)
    diverg = defaultdict(lambda: {'n': 0, 'soma_delta': 0.0})
    with tempfile.TemporaryDirectory(prefix='enem_ind042_') as pasta:
        db = Path(pasta) / 'chaves.sqlite3'
        con = sqlite3.connect(db)
        try:
            con.execute('PRAGMA journal_mode=OFF')
            con.execute('PRAGMA synchronous=OFF')
            con.execute('PRAGMA temp_store=MEMORY')
            con.execute('CREATE TABLE socio (id TEXT PRIMARY KEY, uf TEXT NOT NULL, renda TEXT NOT NULL) WITHOUT ROWID')
            con.execute('CREATE TABLE vistos (id TEXT PRIMARY KEY) WITHOUT ROWID')
            con.execute('CREATE TEMP TABLE lote (id TEXT NOT NULL, nota REAL NOT NULL, '
                        'c1 REAL NOT NULL, c2 REAL NOT NULL, c3 REAL NOT NULL, '
                        'c4 REAL NOT NULL, c5 REAL NOT NULL)')
            total_part = 0
            for parte in iterar_csv(participantes, ['NU_INSCRICAO','SG_UF_PROVA','Q007'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip()
                if ids.eq('').any():
                    raise ValueError('2024/PARTICIPANTES: NU_INSCRICAO vazia.')
                uf = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper()
                if (~uf.isin(UFS)).any():
                    raise ValueError('2024/PARTICIPANTES: SG_UF_PROVA inválida.')
                renda = parte['Q007'].map(codificar_renda)
                try:
                    con.executemany('INSERT INTO socio(id,uf,renda) VALUES(?,?,?)',
                                    zip(ids.tolist(), uf.tolist(), renda.tolist()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('2024/PARTICIPANTES: NU_INSCRICAO duplicada.') from exc
                total_part += len(parte)
            con.commit()
            log(f'  2024: {total_part:,} participantes indexados.')
            total = 0
            colunas = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COLUNAS_COMP]
            for parte in iterar_csv(competencias, colunas, bloco):
                validas = preparar_validas(parte)
                if validas.empty:
                    continue
                ids = validas['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not x for x in ids):
                    raise ValueError('2024/COMPETENCIAS: NU_INSCRICAO vazia em redação válida.')
                try:
                    con.executemany('INSERT INTO vistos(id) VALUES(?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('2024/COMPETENCIAS: NU_INSCRICAO duplicada entre redações válidas.') from exc
                con.execute('DELETE FROM lote')
                valores = list(zip(ids, validas['NU_NOTA_REDACAO'].tolist(),
                                  *(validas[c].tolist() for c in COLUNAS_COMP)))
                con.executemany('INSERT INTO lote VALUES (?,?,?,?,?,?,?)', valores)
                n_match = con.execute('SELECT COUNT(*) FROM lote l JOIN socio s ON s.id=l.id').fetchone()[0]
                if int(n_match) != len(validas):
                    raise ValueError(f'2024: {len(validas)-int(n_match)} redações válidas sem junção.')
                # A agregação reduz n_milhões para UF x categoria x nota x competência.
                for i in range(1, 6):
                    result = con.execute(f'''
                        SELECT s.uf, s.renda, l.c{i}, COUNT(*)
                        FROM lote l JOIN socio s ON s.id=l.id
                        GROUP BY s.uf, s.renda, l.c{i}
                    ''').fetchall()
                    for uf, renda, nota, n in result:
                        hist[(uf, renda, f'C{i}')][float(nota)] += int(n)
                        hist[('BR', renda, f'C{i}')][float(nota)] += int(n)
                result = con.execute('''
                    SELECT s.uf, COUNT(*), SUM(l.c1+l.c2+l.c3+l.c4+l.c5-l.nota)
                    FROM lote l JOIN socio s ON s.id=l.id
                    WHERE ABS(l.c1+l.c2+l.c3+l.c4+l.c5-l.nota)>0.000001
                    GROUP BY s.uf
                ''').fetchall()
                for uf, n, delta in result:
                    for geo in ('BR', uf):
                        diverg[geo]['n'] += int(n)
                        diverg[geo]['soma_delta'] += float(delta)
                total += len(validas)
                con.commit()
            log(f'  2024: {total:,} redações válidas vinculadas.')
            return hist, total, dict(diverg)
        finally:
            con.close()


def n_hist(counter: Counter) -> int:
    return int(sum(counter.values()))


def percentil_exato(contagens: Counter, pct: float) -> float | None:
    """Hyndman–Fan tipo 7 (interpolação linear), sem expandir milhões de linhas."""
    n = n_hist(contagens)
    if n == 0:
        return None
    pos = (n - 1) * pct / 100
    esq, dir = math.floor(pos), math.ceil(pos)
    acum, a, b = 0, None, None
    for valor, quantidade in sorted(contagens.items()):
        acum += int(quantidade)
        if a is None and esq < acum:
            a = float(valor)
        if dir < acum:
            b = float(valor)
            break
    if a is None or b is None:
        raise ArithmeticError('Erro interno no cálculo de percentil.')
    return a + (b-a) * (pos-esq)


def metricas(contagens: Counter) -> dict[str, int | float | None]:
    n = n_hist(contagens)
    if n == 0:
        return {'n_redacoes': 0, 'media': None, 'mediana': None, 'q1': None,
                'q3': None, 'iqr': None, 'desvio_padrao': None}
    media = math.fsum(float(nota) * qtd for nota, qtd in contagens.items()) / n
    var = math.fsum(qtd * (float(nota)-media)**2 for nota, qtd in contagens.items()) / n
    q1, q3 = percentil_exato(contagens, 25), percentil_exato(contagens, 75)
    return {'n_redacoes': n, 'media': round(media, 4),
            'mediana': round(percentil_exato(contagens, 50), 4),
            'q1': round(q1, 4), 'q3': round(q3, 4),
            'iqr': round(q3-q1, 4), 'desvio_padrao': round(math.sqrt(max(0.0,var)), 4)}


def gerar_recortes(ano: int, hist: Hist, total: int, diverg: dict,
                    controle_populacao: bool = True) -> dict[str, Any]:
    recortes: dict[str, Any] = {}
    for uf in ('BR', *UFS):
        categorias = []
        matriz = []
        contagem_total = sum(n_hist(hist.get((uf, renda, 'C1'), Counter()))
                             for renda in CATEGORIAS)
        n_decl = sum(n_hist(hist.get((uf, renda, 'C1'), Counter())) for renda in CODIGOS)
        n_aus = n_hist(hist.get((uf, SEM_RENDA, 'C1'), Counter()))
        n_inval = n_hist(hist.get((uf, RENDA_INVALIDA, 'C1'), Counter()))
        for codigo in CATEGORIAS:
            n = n_hist(hist.get((uf, codigo, 'C1'), Counter()))
            if n == 0 and codigo in (SEM_RENDA, RENDA_INVALIDA):
                continue
            por_comp: dict[str, dict] = {}
            for ci in COMPETENCIAS:
                stats = metricas(hist.get((uf, codigo, ci), Counter()))
                if stats['n_redacoes'] != n:
                    raise ValueError(f'{ano}/{uf}/{codigo}/{ci}: N divergente da C1.')
                por_comp[ci] = stats
                matriz.append({'codigo_renda': codigo, 'descricao_faixa': rotulo_renda(ano,codigo),
                               'ordem': ordem_renda(codigo), 'competencia': ci,
                               **stats, 'n_pequeno': bool(0 < n < 30)})
            categorias.append({
                'codigo_renda': codigo,
                'faixa_renda': codigo if codigo in CODIGOS else rotulo_renda(ano,codigo),
                'descricao_faixa': rotulo_renda(ano, codigo), 'ordem': ordem_renda(codigo),
                'n_redacoes': n, 'percentual_total_validas':
                    round(100*n/contagem_total, 6) if contagem_total else 0.0,
                'percentual_renda_declarada':
                    round(100*n/n_decl,6) if codigo in CODIGOS and n_decl else None,
                'n_pequeno': bool(0<n<30), 'competencias': por_comp,
            })
            if 0 < n < 30:
                log(f'  AVISO {ano}/{uf}/{codigo}: N={n}; manter com ressalva de estabilidade.')
        if sum(x['n_redacoes'] for x in categorias) != contagem_total:
            raise ValueError(f'{ano}/{uf}: categorias não fecham a população.')
        delta = diverg.get(uf, {'n':0,'soma_delta':0.0})
        recortes[uf] = {
            'uf': uf, 'n_pop_socio_valid': contagem_total,
            'n_redacoes_validas': contagem_total, 'n_renda_declarada': n_decl,
            'n_renda_nao_informada': n_aus, 'n_codigo_renda_invalido': n_inval,
            'percentual_renda_declarada':
                round(100*n_decl/contagem_total, 6) if contagem_total else None,
            'categories': categorias, 'matriz': matriz,
            'n_soma_competencias_divergente': int(delta['n']),
            'delta_soma_competencias_menos_nota_redacao': round(float(delta['soma_delta']), 4),
            'integridade': {'categorias_fecham': True, 'cinco_competencias_mesmo_N': True},
        }
    if recortes['BR']['n_pop_socio_valid'] != total:
        raise ValueError(f'{ano}: Brasil={recortes["BR"]["n_pop_socio_valid"]}, leitura={total}')
    if sum(recortes[uf]['n_pop_socio_valid'] for uf in UFS) != total:
        raise ValueError(f'{ano}: soma de UFs não coincide com Brasil.')
    if controle_populacao and POPULACAO_BR_REFERENCIA.get(ano) != total:
        raise ValueError(f'{ano}: N={total:,} difere do IND-001 esperado '
                         f'({POPULACAO_BR_REFERENCIA[ano]:,}). Confira as fontes.')
    n_diverg = recortes['BR']['n_soma_competencias_divergente']
    if n_diverg:
        log(f'  AVISO {ano}: {n_diverg} redação(ões) com soma C1–C5 ≠ nota final; '
            'valores originais preservados sem ajuste.')
    return recortes


def confrontar_ind041(ano: int, recortes: dict, ref: dict | None) -> str:
    if ref is None:
        return 'não_verificado_arquivo_ind041_ausente'
    dados = ref.get('years', {}).get(str(ano))
    if not dados or dados.get('status') != 'ok':
        return 'não_verificado_ano_ausente_ind041'
    for uf in ('BR',*UFS):
        esperado = dados['recortes'][uf]
        atual = recortes[uf]
        for campo in ('n_pop_socio_valid','n_renda_declarada','n_renda_nao_informada',
                      'n_codigo_renda_invalido'):
            if atual[campo] != esperado[campo]:
                raise ValueError(f'{ano}/{uf}/{campo}: IND-042={atual[campo]} '
                                 f'e IND-041={esperado[campo]}')
        faixas_ref = {x['codigo_renda']:x for x in esperado['categories']}
        for item in atual['categories']:
            codigo = item['codigo_renda']
            if item['n_redacoes'] != faixas_ref[codigo]['n_redacoes']:
                raise ValueError(f'{ano}/{uf}/{codigo}: N diverge do IND-041.')
            n = item['n_redacoes']
            if n:
                media_soma = sum(item['competencias'][c]['media'] for c in COMPETENCIAS)
                media_nota = faixas_ref[codigo]['media']
                # 2023 contém uma exceção de fonte (~30 pontos em apenas 1 registro).
                # Não ocultar a diferença: confrontar contabilização explícita.
                if ano != 2023 and abs(media_soma-media_nota) > .001:
                    raise ValueError(f'{ano}/{uf}/{codigo}: soma das médias C1–C5 '
                                     'diferente da média da nota total do IND-041.')
                if ano == 2023 and abs(media_soma-media_nota) > (30 / n + .002):
                    raise ValueError(f'{ano}/{uf}/{codigo}: diferença maior que a '
                                     'exceção conhecida de 2023, conferir microdados.')
    return 'aprovado'


def confrontar_ind009(ano: int, recortes: dict, raiz: Path) -> str:
    arq = raiz / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
    if not arq.is_file():
        return 'não_verificado_dashboard_ausente'
    with arq.open('r', encoding='utf-8-sig') as f:
        doc = json.load(f)
    competencias = doc.get('pages',{}).get('competencies',{})
    nacional = competencias.get('summary')
    estados = competencias.get('ind009',{}).get('by_uf',[])
    if not isinstance(nacional,list) or not isinstance(estados,list):
        return 'não_verificado_ind009_ausente'
    refs = {'BR': nacional}
    refs.update({x['uf']:x['summary'] for x in estados if 'uf' in x and 'summary' in x})
    if set(refs) != {'BR',*UFS}:
        return 'não_verificado_ind009_recortes_incompletos'
    for uf, tabela in refs.items():
        esperadas = {item['competency']:item for item in tabela}
        for ci in COMPETENCIAS:
            n = recortes[uf]['n_redacoes_validas']
            soma = math.fsum(item['competencias'][ci]['media']*item['n_redacoes']
                             for item in recortes[uf]['categories'])
            media = soma/n if n else 0
            referencia = float(esperadas[ci]['mean_score'])
            if abs(media-referencia) > .001:
                raise ValueError(f'{ano}/{uf}/{ci}: média ponderada IND-042={media:.4f} '
                                 f'difere do IND-009={referencia:.4f}.')
    return 'aprovado'


def csv_linhas(anos_dados: dict[str, Any]) -> list[dict[str, Any]]:
    linhas = []
    for chave in sorted(anos_dados, key=int):
        dado = anos_dados[chave]
        if dado.get('status') != 'ok':
            continue
        for uf in ('BR',*UFS):
            for categoria in dado['recortes'][uf]['categories']:
                for ci, stats in categoria['competencias'].items():
                    linhas.append({
                        'ano': int(chave), 'uf':uf,
                        'codigo_renda': categoria['codigo_renda'],
                        'faixa_renda': categoria['faixa_renda'],
                        'descricao_faixa': categoria['descricao_faixa'],
                        'ordem': categoria['ordem'], 'competencia': ci,
                        **stats, 'percentual_total_validas':
                            categoria['percentual_total_validas'],
                        'percentual_renda_declarada':
                            categoria['percentual_renda_declarada'],
                        'n_pequeno': categoria['n_pequeno'],
                    })
    return linhas


def salvar_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                     dir=caminho.parent, prefix=caminho.name+'.',
                                     suffix='.tmp', delete=False) as f:
        aux = Path(f.name)
        json.dump(dados, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    try:
        aux.replace(caminho)
    finally:
        aux.unlink(missing_ok=True)


def salvar_csv(caminho: Path, linhas: list[dict[str,Any]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    campos = ['ano','uf','codigo_renda','faixa_renda','descricao_faixa','ordem',
              'competencia','n_redacoes','media','mediana','q1','q3','iqr',
              'desvio_padrao','percentual_total_validas','percentual_renda_declarada','n_pequeno']
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig',
                                     newline='', dir=caminho.parent,
                                     prefix=caminho.name+'.', suffix='.tmp',
                                     delete=False) as f:
        aux = Path(f.name)
        writer = csv.DictWriter(f, delimiter=';', fieldnames=campos, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(linhas)
    try:
        aux.replace(caminho)
    finally:
        aux.unlink(missing_ok=True)


def atualizar_dashboards(raiz: Path, dados_anos: dict[str, Any],
                         anos_processados: tuple[int,...]) -> None:
    for ano in anos_processados:
        dados = dados_anos.get(str(ano), {})
        if dados.get('status') != 'ok':
            continue
        caminho = raiz / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.exists():
            log(f'  Dashboard {ano} ausente: módulo mantido, integração ignorada.')
            continue
        with caminho.open('r',encoding='utf-8-sig') as f:
            doc = json.load(f)
        socio = doc.setdefault('pages',{}).setdefault('socioeconomic',{})
        if not isinstance(socio, dict):
            raise ValueError(f'{ano}: pages.socioeconomic inválido no dashboard.')
        rec = dados['recortes']
        novo = {
            'indicator_id': 'IND-042', 'year': ano, 'status': 'draft',
            'population': 'POP_SOCIO_VALID',
            'source_question': dados['variavel_renda'],
            'competencies': list(COMPETENCIAS),
            'national': rec['BR'], 'states': {uf: rec[uf] for uf in UFS},
            'privacy_note': ('Células com n pequeno assinaladas sem supressão automática. '
                             'Avaliar inferência cruzada antes de divulgação pública.'),
        }
        # A integração não modifica nem recalcula qualquer indicador já presente.
        backup = caminho.with_suffix(caminho.suffix + '.bak_antes_ind042')
        if not backup.exists():
            shutil.copy2(caminho, backup)
        socio['income_competencies'] = novo
        qualidade = doc.setdefault('quality',{})
        if isinstance(qualidade,dict):
            qualidade['ind042_validation'] = {
                'status': 'ok_agregados',
                'n_pop_socio_valid_brasil': rec['BR']['n_pop_socio_valid'],
                'soma_27_ufs_igual_brasil': True,
                'cinco_competencias_mesmo_denominador': True,
                'ind041': dados['validacoes']['ind041'],
                'ind009': dados['validacoes']['ind009'],
                'n_somas_competencias_divergentes': rec['BR']['n_soma_competencias_divergente'],
                'revisao_academica_e_privacidade_pendente': True,
            }
        avisos = doc.get('meta',{}).get('warnings',[])
        novo_aviso = ('IND-042: renda x C1–C5, POP_SOCIO_VALID; '
                      'validação agregada realizada; revisão acadêmica e de privacidade pendente.')
        if isinstance(avisos,list) and novo_aviso not in avisos:
            avisos.append(novo_aviso)
        salvar_json(caminho, doc)
        log(f'  Dashboard {ano}: IND-042 integrado, backup criado/preservado.')


def executar(base: Path, anos: tuple[int,...], bloco: int,
             somente_modulo: bool, sobrescrever: bool,
             saida: Path|None=None, controle_populacao: bool=True) -> dict:
    raiz = (saida or raiz_projeto()).resolve()
    if not base.resolve().is_dir():
        raise FileNotFoundError(f'Pasta --base não existe: {base}')
    mod_json = raiz / 'outputs/json/IND_042_renda_competencias.json'
    mod_csv = raiz / 'outputs/indicadores/IND_042_renda_competencias.csv'
    if not sobrescrever and (mod_json.exists() or mod_csv.exists()):
        raise FileExistsError('Saída IND-042 existente: use --sobrescrever.')
    nomes = set()
    for ano in anos:
        if ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV','COMPETENCIAS_REDACAO_2024.CSV'})
    caminhos = achar_arquivos(base.resolve(), nomes) if nomes else {}
    faltantes = sorted(nomes-set(caminhos))
    if faltantes:
        raise FileNotFoundError(f'Fontes do ENEM ausentes: {faltantes}; ajuste --base.')
    ref41 = raiz / 'outputs/json/IND_041_renda_nota_total.json'
    dados41 = None
    if ref41.exists():
        with ref41.open('r',encoding='utf-8-sig') as f:
            dados41 = json.load(f)
    # Preserva anos previamente calculados caso --anos seja parcial.
    anteriores: dict[str,Any] = {}
    if sobrescrever and mod_json.exists():
        with mod_json.open('r',encoding='utf-8-sig') as f:
            antigos = json.load(f)
        if antigos.get('indicator_id') != 'IND-042':
            raise ValueError('Arquivo de saída antigo não pertence ao IND-042.')
        anteriores = dict(antigos.get('years',{}))
    dados_anos = anteriores
    for ano in anos:
        if ano == 2025:
            log('IND-042 | 2025: indisponível — sem chave individual socio×competências.')
            dados_anos[str(ano)] = {
                'ano':2025,'status':'indisponivel','recortes':{},
                'reason':'PARTICIPANTES_2025 e RESULTADOS_2025 não têm chave pública compartilhada.',
            }
            continue
        log(f'IND-042 | {ano}: lendo renda e notas finais C1–C5...')
        if ano <= 2023:
            hist,total,diverg = processar_2019_2023(
                ano, caminhos[f'MICRODADOS_ENEM_{ano}.CSV'],bloco)
            var_renda = 'Q006'
            fonte = f'MICRODADOS_ENEM_{ano}.csv'
        else:
            hist,total,diverg = processar_2024(
                caminhos['PARTICIPANTES_2024.CSV'],
                caminhos['COMPETENCIAS_REDACAO_2024.CSV'],bloco)
            var_renda = 'Q007'
            fonte = 'COMPETENCIAS_REDACAO_2024.csv'
        recortes = gerar_recortes(ano,hist,total,diverg,controle_populacao)
        s41 = confrontar_ind041(ano,recortes,dados41)
        s009 = confrontar_ind009(ano,recortes,raiz)
        log(f'  {ano}: Brasil N={total:,}; IND-041={s41}; IND-009={s009}.')
        dados_anos[str(ano)] = {
            'ano':ano,'status':'ok','populacao':'POP_SOCIO_VALID',
            'variavel_renda':var_renda,'fonte_competencias':fonte,
            'competencias':list(COMPETENCIAS),'n_brasil':total,
            'categorias_renda_ordenadas':list(CODIGOS),
            'validacoes':{'ind041':s41,'ind009':s009,
                           'populacao_br':bool(controle_populacao)},
            'recortes':recortes,
        }
    modulo = {
        'indicator_id':'IND-042',
        'titulo':'Renda familiar x competências da redação',
        'status':'draft','gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'anos_solicitados':list(anos),'anos_disponiveis':
            sorted(int(y) for y,d in dados_anos.items() if d.get('status')=='ok'),
        'population':'POP_SOCIO_VALID','geography':'SG_UF_PROVA',
        'methodology':{
            'selection':'TP_STATUS_REDACAO=1 e nota final total em [0,1000]',
            'scores':'NU_NOTA_COMP1..5 finais, cada uma no intervalo [0,200]',
            'income_2019_2023':'Q006','income_2024':'Q007',
            'join_2024':'NU_INSCRICAO entre PARTICIPANTES_2024 e COMPETENCIAS_REDACAO_2024',
            'percentile_method':'Hyndman-Fan tipo 7 exato por frequência',
            'standard_deviation':'populacional (ddof=0)',
            'missing_income':'categoria separada, incluída no denominador',
            'small_n':'sinalização sem exclusão automática',
            'comparison':'IND-041 (N/categoria) e IND-009 (média por competência), quando disponíveis',
            'no_link_2025':True,
            'cautions':['Renda autorreferida; cortes monetários mudam entre anos.',
                        'UF representa local de realização da prova.',
                        'Histórico soma participações, não pessoas únicas.',
                        'Pequenas contagens podem gerar estatísticas instáveis.',
                        'C1–C5 são notas finais, não diferenças AV1×AV2.',
                        'A análise é descritiva, não causal.',
                        'A publicação requer revisão acadêmica e de privacidade contextual.'],
        },
        'years': dados_anos,
    }
    salvar_json(mod_json,modulo)
    linhas = csv_linhas(dados_anos)
    salvar_csv(mod_csv,linhas)
    log(f'IND-042 | JSON: {mod_json} | CSV: {mod_csv} | linhas: {len(linhas):,}')
    if not somente_modulo:
        atualizar_dashboards(raiz,dados_anos,anos)
    log('IND-042 | Finalizado.')
    return modulo


def main() -> None:
    p=argparse.ArgumentParser(description='IND-042 — Renda familiar x competências.')
    p.add_argument('--base',type=Path,default=raiz_projeto(),
                   help='Diretório dos CSVs públicos (busca recursiva).')
    p.add_argument('--saida',type=Path,default=None,
                   help='Raiz alternativa para outputs; útil em testes.')
    p.add_argument('--anos',type=int,nargs='+',default=list(ANOS),
                   help='2019 a 2025, padrão todos.')
    p.add_argument('--bloco',type=int,default=150_000,
                   help='Tamanho do lote CSV (padrão 150000).')
    p.add_argument('--somente-modulo',action='store_true',
                   help='Não alterar os dashboards existentes.')
    p.add_argument('--sobrescrever',action='store_true',
                   help='Atualiza os outputs IND-042 preservando anos não solicitados.')
    p.add_argument('--sem-controle-populacao',action='store_true',
                   help='APENAS TESTES com CSVs pequenos: dispensa N de referência IND-001.')
    args=p.parse_args()
    if args.bloco<=0:
        p.error('--bloco precisa ser positivo.')
    anos=tuple(sorted(set(args.anos)))
    if not anos or any(x not in ANOS for x in anos):
        p.error('Anos aceitos: 2019 a 2025.')
    try:
        executar(args.base,anos,args.bloco,args.somente_modulo,args.sobrescrever,
                 args.saida,controle_populacao=not args.sem_controle_populacao)
    except (ValueError,FileNotFoundError,FileExistsError,OSError,sqlite3.DatabaseError,
            json.JSONDecodeError,ArithmeticError) as exc:
        print(f'ERRO IND-042: {exc}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__':
    main()
