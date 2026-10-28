#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-037 | Concentração de descontos — Projeto Integrador IV UNIVESP.

Catálogo de Indicadores ENEM 2019–2025 v2:
  POP_NEAR: TP_STATUS_REDACAO=1; 900 <= NU_NOTA_REDACAO <= 980.
  Ocorrência: Q de Cochran sobre I(Ci < 200), i=1..5.
  Magnitude: Friedman sobre perdas Li = 200 - Ci (dados pareados).
  Pós-testes: McNemar exato (ocorrência) e Wilcoxon pareado com
  aproximação normal e correção de empates (magnitude), aplicando Holm
  SEPARADAMENTE às 10 comparações de cada família de hipóteses.

OBSERVAÇÕES:
  - As cinco competências vêm da MESMA redação: NUNCA usar testes para
    amostras independentes ou agregar os p-valores das UFs para obter BR.
  - Os testes detectam diferenças de distribuição/frequência, não causas,
    erros de correção nem importância pedagógica. POP_NEAR é selecionada
    pela soma C1..C5, o que condiciona mecanicamente essas comparações.
  - As distribuições contêm empates; Wilcoxon usa aproximação assintótica.
  - Política revisada: uma máscara exata rara (1..29 redações) NÃO
    oculta o recorte inteiro; máscaras exatas não são exportadas.
    Testes agregados são divulgados para recortes com N >= 30;
    contagens diretas pequenas e complementares são ocultadas em campos
    detalhados. Anonimização não elimina a revisão de privacidade cruzada.

Fontes:
  2019–2023: MICRODADOS_ENEM_<ano>.csv (nota e UF na mesma linha).
  2024: PARTICIPANTES_2024.csv e COMPETENCIAS_REDACAO_2024.csv,
        unidos exclusivamente por NU_INSCRICAO em SQLite temporário.
  2025: RESULTADOS_2025.csv quando presente (não fabrica resultados).

Saídas:
  outputs/json/IND_037_concentracao_descontos.json
  outputs/indicadores/IND_037_concentracao_descontos.csv
  outputs/json/dashboard_enem_<ano>.json, em
       pages.high_performance.tests e quality.ind037_validation.

Uso:
  python src/indicadores/IND_037_concentracao_descontos.py --autoteste
  python src/indicadores/IND_037_concentracao_descontos.py --anos 2024 --sobrescrever
  python src/indicadores/IND_037_concentracao_descontos.py --sobrescrever

Os arquivos .bak não são criados. Escrita de JSON/CSV atômica.
Dependências: numpy, pandas, scipy (instalados no ambiente do projeto).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
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
from scipy.stats import chi2, norm, binom

ANOS = tuple(range(2019, 2026))
UFS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG',
       'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR',
       'RS', 'SC', 'SE', 'SP', 'TO')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
COLUNAS_C = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
PARES = tuple((a, b) for a in range(5) for b in range(a + 1, 5))
MIN_N = 30
ALFA = 0.05
POLITICA_DIVULGACAO = 'testes_agregados_sem_bloqueio_mascara_rara_v2'
POP_NEAR_REFERENCIA = {
    2019: 172_548, 2020: 183_343, 2021: 163_747,
    2022: 197_083, 2023: 288_602, 2024: 291_111,
    2025: 173_533,
}
CAMPOS_CSV = (
    'ano', 'uf', 'n_near', 'familia', 'teste', 'competencia_a',
    'competencia_b', 'estatistica', 'p_valor', 'p_ajustado_holm',
    'significativo_5pct', 'n_pares_informativos', 'status_teste',
    'status_publicacao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    arq = Path(__file__).resolve()
    if arq.parent.name.lower() == 'indicadores' and arq.parent.parent.name.lower() == 'src':
        return arq.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                     fontes_explicitas: dict[str, Path] | None = None) -> dict[str, Path]:
    """Aceita CSVs duplicados byte a byte idênticos; rejeita cópias diferentes."""
    ignorados = {'.git', '.venv', 'venv', '__pycache__', 'outputs',
                 '.pytest_cache', 'node_modules', '.mypy_cache'}
    encontrados: dict[str, Path] = {}
    fontes_explicitas = fontes_explicitas or {}
    for nome, indicado in fontes_explicitas.items():
        chave = nome.upper()
        if chave not in nomes:
            raise ValueError(f'Fonte explícita não solicitada para os anos selecionados: {chave}.')
        caminho = Path(indicado).expanduser()
        if not caminho.is_absolute():
            caminho = base / caminho
        caminho = caminho.resolve()
        if not caminho.is_file():
            raise FileNotFoundError(f'Arquivo indicado não encontrado: {caminho}.')
        encontrados[chave] = caminho
        log(f'  Fonte selecionada para {chave}: {caminho}')

    for pasta, diretorios, arquivos in os.walk(base):
        diretorios[:] = sorted(d for d in diretorios if d.lower() not in ignorados)
        for nome in sorted(arquivos):
            chave = nome.upper()
            if chave not in nomes or chave in fontes_explicitas:
                continue
            caminho = Path(pasta) / nome
            if chave in encontrados and encontrados[chave].resolve() != caminho.resolve():
                anterior = encontrados[chave]
                if filecmp.cmp(anterior, caminho, shallow=False):
                    log(f'  Cópias idênticas de {chave}; usando {anterior}.')
                    continue
                opcao = ('--competencias-2024' if chave == 'COMPETENCIAS_REDACAO_2024.CSV'
                         else '--participantes-2024' if chave == 'PARTICIPANTES_2024.CSV'
                         else '(revise as fontes diferentes)')
                raise ValueError(f'Fontes diferentes com mesmo nome {chave}: '
                                 f'{anterior} e {caminho}. Selecione explicitamente com {opcao}.')
            encontrados[chave] = caminho
    return encontrados


def ler_blocos(caminho: Path, colunas: list[str], bloco: int):
    with caminho.open('rb') as f:
        encoding = 'utf-8-sig' if f.read(3) == b'\xef\xbb\xbf' else 'latin-1'
    cabecalho = pd.read_csv(caminho, sep=';', encoding=encoding, nrows=0)
    disponiveis = {str(c).strip().lstrip('\ufeff') for c in cabecalho.columns}
    faltando = sorted(set(colunas) - disponiveis)
    if faltando:
        raise ValueError(f'{caminho.name}: colunas necessárias ausentes: {faltando}.')
    with pd.read_csv(caminho, sep=';', encoding=encoding, dtype='string',
                     usecols=colunas, chunksize=bloco, na_filter=False,
                     keep_default_na=False, low_memory=False) as partes:
        for df in partes:
            df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
            yield df


def numerico(coluna: pd.Series, nome: str) -> np.ndarray:
    serie = coluna.astype('string').str.strip().str.replace(',', '.', regex=False)
    valores = pd.to_numeric(serie, errors='coerce').to_numpy(dtype='float64')
    if not np.isfinite(valores).all():
        raise ValueError(f'{nome}: nota ausente, não numérica ou infinita em redação elegível.')
    return valores


def preparar_near(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    selecionadas = df.loc[df['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')].copy()
    if selecionadas.empty:
        return selecionadas, 0
    total = numerico(selecionadas['NU_NOTA_REDACAO'], 'NU_NOTA_REDACAO')
    if ((total < 0) | (total > 1000)).any():
        raise ValueError('Redação válida com nota total fora de [0,1000].')
    n_validas = len(selecionadas)
    selecionadas['__nota_total'] = total
    perto = selecionadas.loc[(total >= 900) & (total <= 980)].copy()
    return perto, n_validas


def perdas_de_near(near: pd.DataFrame) -> np.ndarray:
    """Extrai matriz N x 5 de perdas inteiras; verifica soma com nota final."""
    if near.empty:
        return np.empty((0, 5), dtype=np.int16)
    notas = np.column_stack([numerico(near[col], col) for col in COLUNAS_C])
    if ((notas < 0) | (notas > 200)).any():
        raise ValueError('Nota em competência fora do intervalo [0,200].')
    total = near['__nota_total'].to_numpy(dtype='float64')
    erradas = ~np.isclose(notas.sum(axis=1), total, rtol=0, atol=1e-6)
    if erradas.any():
        raise ValueError(f'{int(erradas.sum())} redação(ões) da POP_NEAR com '
                         'soma C1..C5 diferente da nota final; investigar fonte.')
    perdas = 200.0 - notas
    if not np.all(np.isclose(perdas, np.rint(perdas), rtol=0, atol=1e-6)):
        raise ValueError('IND-037 espera pontuações inteiras nas competências; '
                         'houve pontuação fracionária não suportada pela distribuição de diferenças.')
    perdas = np.rint(perdas).astype(np.int16)
    if ((perdas < 0) | (perdas > 200)).any():
        raise ValueError('Perdas fora de [0,200].')
    return perdas


@dataclass
class Acumulador:
    n: int = 0
    soma_perdas: np.ndarray = field(default_factory=lambda: np.zeros(5, dtype=np.int64))
    descontos: np.ndarray = field(default_factory=lambda: np.zeros(5, dtype=np.int64))
    mascaras: np.ndarray = field(default_factory=lambda: np.zeros(32, dtype=np.int64))
    postos: np.ndarray = field(default_factory=lambda: np.zeros(5, dtype=np.float64))
    empates_friedman: int = 0
    soma_quadrados_ocorrencias_linha: int = 0
    diferencas: np.ndarray = field(default_factory=lambda: np.zeros((10, 401), dtype=np.int64))
    total_perdas_por_nota: int = 0

    def adicionar(self, perdas: np.ndarray) -> None:
        if perdas.ndim != 2 or perdas.shape[1] != 5:
            raise ValueError('Esperada matriz de perdas [n,5].')
        if not len(perdas):
            return
        self.n += len(perdas)
        self.soma_perdas += np.sum(perdas, axis=0, dtype=np.int64)
        flags = (perdas > 0).astype(np.uint8)
        self.descontos += np.sum(flags, axis=0, dtype=np.int64)
        mask = flags @ np.array([1, 2, 4, 8, 16], dtype=np.uint8)
        self.mascaras += np.bincount(mask.astype(int), minlength=32)
        por_linha = np.sum(flags, axis=1, dtype=np.int64)
        self.soma_quadrados_ocorrencias_linha += int(np.dot(por_linha, por_linha))
        self.total_perdas_por_nota += int(np.sum(perdas, dtype=np.int64))
        # Postos pareados 1..5, incluindo postos médios nos empates.
        # Grupo empatado com t observações adiciona (t^3-t) à correção.
        maior = np.sum(perdas[:, :, None] > perdas[:, None, :], axis=2)
        tamanhos = np.sum(perdas[:, :, None] == perdas[:, None, :], axis=2)
        ranks = 1.0 + maior + 0.5 * (tamanhos - 1)
        self.postos += np.sum(ranks, axis=0, dtype=np.float64)
        self.empates_friedman += int(np.sum(tamanhos.astype('int64') ** 2 - 1, dtype=np.int64))
        for pos, (i, j) in enumerate(PARES):
            delta = perdas[:, i].astype(np.int32) - perdas[:, j].astype(np.int32)
            self.diferencas[pos] += np.bincount(delta + 200, minlength=401)

    def somar(self, outro: 'Acumulador') -> None:
        self.n += outro.n
        self.soma_perdas += outro.soma_perdas
        self.descontos += outro.descontos
        self.mascaras += outro.mascaras
        self.postos += outro.postos
        self.empates_friedman += outro.empates_friedman
        self.soma_quadrados_ocorrencias_linha += outro.soma_quadrados_ocorrencias_linha
        self.diferencas += outro.diferencas
        self.total_perdas_por_nota += outro.total_perdas_por_nota


def acumular_ufs(agregados: dict[str, Acumulador], ufs: np.ndarray,
                 perdas: np.ndarray) -> None:
    if len(ufs) != len(perdas):
        raise ValueError('Comprimentos diferentes na UF e na matriz de perdas.')
    if not pd.Series(ufs).isin(UFS).all():
        raise ValueError('SG_UF_PROVA ausente/inválida em POP_NEAR.')
    for uf in np.unique(ufs):
        agregados[uf].adicionar(perdas[ufs == uf])


def ler_mesma_linha(caminho: Path, bloco: int) -> tuple[dict, int, dict]:
    agregados = defaultdict(Acumulador)
    validas = 0
    cols = ['TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', 'SG_UF_PROVA', *COLUNAS_C]
    for parte in ler_blocos(caminho, cols, bloco):
        perto, n = preparar_near(parte)
        validas += n
        if not perto.empty:
            ufs = perto['SG_UF_PROVA'].astype('string').str.strip().str.upper().to_numpy()
            acumular_ufs(agregados, ufs, perdas_de_near(perto))
    return dict(agregados), validas, {'metodo': 'mesma_linha', 'fonte': caminho.name}


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    agregados = defaultdict(Acumulador)
    n_validas = 0
    n_vinculadas = 0
    with tempfile.TemporaryDirectory(prefix='enem_ind037_') as tmp:
        bd = sqlite3.connect(str(Path(tmp) / 'juncoes.sqlite3'))
        try:
            bd.execute('PRAGMA synchronous=OFF')
            bd.execute('PRAGMA journal_mode=OFF')
            bd.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL) WITHOUT ROWID')
            bd.execute('CREATE TABLE near_vistos(id TEXT PRIMARY KEY) WITHOUT ROWID')
            bd.execute('CREATE TEMP TABLE lote(id TEXT, c1 INTEGER, c2 INTEGER, c3 INTEGER, '
                       'c4 INTEGER, c5 INTEGER)')
            contagem_part = 0
            for parte in ler_blocos(participantes, ['NU_INSCRICAO', 'SG_UF_PROVA'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(not x for x in ids) or any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrições ausentes ou UFs inválidas.')
                try:
                    bd.executemany('INSERT INTO participantes VALUES (?, ?)', zip(ids, ufs))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from exc
                contagem_part += len(ids)
            bd.commit()
            log(f'  Participantes 2024 indexados: {contagem_part:,}')
            cols = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COLUNAS_C]
            for parte in ler_blocos(competencias, cols, bloco):
                perto, n = preparar_near(parte)
                n_validas += n
                if perto.empty:
                    continue
                ids = perto['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not x for x in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: NU_INSCRICAO vazia na POP_NEAR.')
                perdas = perdas_de_near(perto)
                try:
                    bd.executemany('INSERT INTO near_vistos VALUES (?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: NU_INSCRICAO duplicada na POP_NEAR.') from exc
                bd.execute('DELETE FROM lote')
                bd.executemany('INSERT INTO lote VALUES (?,?,?,?,?,?)',
                               ((ident, *map(int, perda)) for ident, perda in zip(ids, perdas)))
                consulta = '''SELECT p.uf, l.c1, l.c2, l.c3, l.c4, l.c5
                              FROM lote l JOIN participantes p ON p.id=l.id'''
                resultado = bd.execute(consulta).fetchall()
                if len(resultado) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(resultado)} redação(ões) '
                                     'POP_NEAR sem inscrição correspondente em participantes.')
                tabela = pd.DataFrame.from_records(resultado, columns=['uf', *COMPETENCIAS])
                acumular_ufs(agregados, tabela['uf'].to_numpy(),
                             tabela[list(COMPETENCIAS)].to_numpy(dtype=np.int16))
                n_vinculadas += len(resultado)
                bd.commit()
            return dict(agregados), n_validas, {
                'metodo': 'join_NU_INSCRICAO_SQLite',
                'n_participantes': contagem_part,
                'n_pop_near_vinculadas': n_vinculadas,
                'n_near_sem_correspondencia': 0,
            }
        finally:
            bd.close()


def fechar_agregados(agregados: dict[str, Acumulador],
                     ano: int, n_validas: int, _teste: bool = False) -> dict[str, Acumulador]:
    for uf in UFS:
        agregados.setdefault(uf, Acumulador())
    br = Acumulador()
    for uf in UFS:
        aux = agregados[uf]
        if aux.n < 0 or int(aux.mascaras.sum()) != aux.n:
            raise ValueError(f'{ano}/{uf}: histograma de máscaras não fecha.')
        if aux.n > n_validas or aux.n != int(aux.diferencas[0].sum()):
            raise ValueError(f'{ano}/{uf}: contagem de diferenças pareadas não fecha.')
        if aux.n and (aux.mascaras[0] != 0 or
                      int(aux.soma_perdas.sum()) != aux.total_perdas_por_nota):
            raise ValueError(f'{ano}/{uf}: perdas/nota incompatíveis.')
        br.somar(aux)
    agregados['BR'] = br
    if br.n > n_validas:
        raise ValueError(f'{ano}: POP_NEAR maior que população válida.')
    if not _teste and ano in POP_NEAR_REFERENCIA and br.n != POP_NEAR_REFERENCIA[ano]:
        raise ValueError(f'{ano}: POP_NEAR={br.n:,} diverge da referência '
                         f'IND-031={POP_NEAR_REFERENCIA[ano]:,}. Verifique as fontes.')
    for uf in ('BR', *UFS):
        a = agregados[uf]
        if int(a.descontos.sum()) != int(sum(int(a.mascaras[m]) * m.bit_count()
                                               for m in range(32))):
            raise ValueError(f'{ano}/{uf}: margens de descontos não fecham.')
        if any(int(a.diferencas[p].sum()) != a.n for p in range(10)):
            raise ValueError(f'{ano}/{uf}: distribuição de diferenças incompleta.')
    return agregados


def cochran_q(a: Acumulador) -> dict:
    n, k = a.n, 5
    if n < MIN_N:
        return {'estatistica': None, 'gl': k - 1, 'p_valor': None,
                'status': 'n_insuficiente'}
    totais = a.descontos.astype(np.float64)
    soma = float(totais.sum())
    denominador = k * soma - float(a.soma_quadrados_ocorrencias_linha)
    if denominador <= 0:
        return {'estatistica': None, 'gl': k - 1, 'p_valor': None,
                'status': 'sem_variabilidade_intra_redacao'}
    numerador = (k - 1) * (k * float(np.dot(totais, totais)) - soma * soma)
    q = max(0.0, numerador / denominador)
    return {'estatistica': round(q, 8), 'gl': k - 1,
            'p_valor': float(chi2.sf(q, k - 1)), 'status': 'ok'}


def friedman(a: Acumulador) -> dict:
    n, k = a.n, 5
    if n < MIN_N:
        return {'estatistica': None, 'gl': k - 1, 'p_valor': None,
                'kendall_w': None, 'status': 'n_insuficiente'}
    correcao = 1.0 - a.empates_friedman / (n * (k ** 3 - k))
    if correcao <= 1e-12:
        return {'estatistica': None, 'gl': k - 1, 'p_valor': None,
                'kendall_w': None, 'status': 'todos_valores_empatados'}
    total_postos = a.postos
    estat = (12.0 / (n * k * (k + 1)) * float(np.dot(total_postos, total_postos))
            - 3.0 * n * (k + 1)) / correcao
    estat = max(0.0, estat)
    w = min(1.0, max(0.0, estat / (n * (k - 1))))
    return {'estatistica': round(estat, 8), 'gl': k - 1,
            'p_valor': float(chi2.sf(estat, k - 1)),
            'kendall_w': round(w, 8), 'correcao_empates': round(correcao, 10),
            'status': 'ok'}


def holm(pvals: list[float]) -> list[float]:
    """Holm step-down (monotonicidade assegurada), por família de 10."""
    if not pvals:
        return []
    if any((not math.isfinite(p) or p < 0 or p > 1) for p in pvals):
        raise ValueError('p-valores inválidos no ajuste de Holm.')
    m = len(pvals)
    ordem = sorted(range(m), key=lambda i: pvals[i])
    saida = [1.0] * m
    maior = 0.0
    for pos, indice in enumerate(ordem):
        maior = min(1.0, max(maior, (m - pos) * pvals[indice]))
        saida[indice] = maior
    return saida


def wilcoxon_por_histograma(hist: np.ndarray) -> dict:
    """Wilcoxon signed-rank pareado, zeros excluídos, normal/ties, sem continuidade.

    Histograma das diferenças (Li - Lj), índices [0..400] = [-200..200].
    Retorna teste assintótico bicaudal. A hipótese requer simetria das
    diferenças para interpretação como teste de localização.
    """
    if hist.shape != (401,) or (hist < 0).any():
        raise ValueError('Histograma de diferenças inválido.')
    frequencias_abs = np.array([int(hist[200 - d]) + int(hist[200 + d])
                                for d in range(1, 201)], dtype=np.int64)
    n_ef = int(frequencias_abs.sum())
    if n_ef == 0:
        return {'estatistica': None, 'p_valor': 1.0, 'n_pares_informativos': 0,
                'status': 'sem_diferencas_pareadas'}
    acumuladas = 0
    w_mais = 0.0
    soma_empates = 0
    for distancia, qtd in enumerate(frequencias_abs, 1):
        t = int(qtd)
        if t == 0:
            continue
        posto_medio = acumuladas + (t + 1) / 2.0
        w_mais += int(hist[200 + distancia]) * posto_medio
        soma_empates += t ** 3 - t
        acumuladas += t
    esperado = n_ef * (n_ef + 1) / 4.0
    variancia = (n_ef * (n_ef + 1) * (2 * n_ef + 1) / 24.0
                 - soma_empates / 48.0)
    if variancia <= 0:
        raise ValueError('Variância Wilcoxon não positiva com pares informativos.')
    z = (w_mais - esperado) / math.sqrt(variancia)
    p = min(1.0, float(2 * norm.sf(abs(z))))
    return {'estatistica': round(min(w_mais, n_ef*(n_ef+1)/2 - w_mais), 4),
            'z': round(z, 8), 'p_valor': p,
            'n_pares_informativos': n_ef, 'status': 'ok_aproximacao_normal'}


def mcnemar_exato(hist: np.ndarray, i: int, j: int) -> dict:
    """McNemar exato bicaudal via distribuição binomial de discordâncias."""
    b = sum(int(hist[m]) for m in range(32)
            if (m & (1 << i)) and not (m & (1 << j)))
    c = sum(int(hist[m]) for m in range(32)
            if (m & (1 << j)) and not (m & (1 << i)))
    discordantes = b + c
    if not discordantes:
        return {'estatistica': None, 'p_valor': 1.0,
                'n_pares_informativos': 0, 'status': 'sem_pares_discordantes'}
    # Como n é grande, scipy.stats.binom.cdf calcula a cauda exatamente na
    # distribuição binomial, sem iterar pelo total de redações.
    p = min(1.0, float(2.0 * binom.cdf(min(b, c), discordantes, 0.5)))
    estatistica = (abs(b-c)-1)**2 / discordantes if abs(b-c) > 1 else 0.0
    return {'estatistica': round(estatistica, 8), 'p_valor': p,
            'n_pares_informativos': discordantes,
            'discordantes_a_sim_b_nao': b,
            'discordantes_a_nao_b_sim': c,
            'status': 'ok_exato'}


def testar_recorte(a: Acumulador) -> dict:
    ocorrencia = cochran_q(a)
    magnitude = friedman(a)
    pares_ocorrencia = []
    pares_magnitude = []
    for p, (i, j) in enumerate(PARES):
        mc = mcnemar_exato(a.mascaras, i, j)
        mc.update({'competencia_a': COMPETENCIAS[i], 'competencia_b': COMPETENCIAS[j],
                   'teste': 'mcnemar_exato', 'familia': 'ocorrencia'})
        pares_ocorrencia.append(mc)
        wi = wilcoxon_por_histograma(a.diferencas[p])
        wi.update({'competencia_a': COMPETENCIAS[i], 'competencia_b': COMPETENCIAS[j],
                   'teste': 'wilcoxon_assintotico_empates', 'familia': 'magnitude'})
        pares_magnitude.append(wi)
    for pares in (pares_ocorrencia, pares_magnitude):
        ajustados = holm([t['p_valor'] for t in pares])
        for item, valor in zip(pares, ajustados):
            item['p_ajustado_holm'] = valor
            item['significativo_5pct'] = valor < ALFA
    return {
        'ocorrencia': {
            'teste': 'Q_de_Cochran', 'frequencias_por_competencia': [
                {'competencia': COMPETENCIAS[i], 'n_com_desconto': int(a.descontos[i]),
                 'percentual': round(100 * int(a.descontos[i]) / a.n, 6)}
                for i in range(5)],
            **ocorrencia,
            'significativo_5pct': (ocorrencia['p_valor'] < ALFA
                                  if ocorrencia['p_valor'] is not None else None),
        },
        'magnitude': {
            'teste': 'Friedman', 'perdas_por_competencia': [
                {'competencia': COMPETENCIAS[i], 'media_perda':
                 round(int(a.soma_perdas[i]) / a.n, 6),
                 'soma_pontos_perdidos': int(a.soma_perdas[i])}
                for i in range(5)],
            **magnitude,
            'significativo_5pct': (magnitude['p_valor'] < ALFA
                                  if magnitude['p_valor'] is not None else None),
        },
        'pos_testes_ocorrencia': pares_ocorrencia,
        'pos_testes_magnitude': pares_magnitude,
    }


def supressao_territorial(agregados: dict[str, Acumulador]) -> tuple[dict[str, str], dict]:
    """Não ocultar BR/UF somente por existência de máscara exata rara.

    Nenhum histograma de 32 máscaras ou diferenças individuais é exportado.
    Testes estatísticos agregados podem ser calculados para n >= 30.
    Um recorte de 1..29 redações permanece indisponível, com proteção
    geográfica complementar quando há uma única UF primariamente oculta.
    Estatísticas inferenciais não substituem avaliação de privacidade cruzada.
    """
    ocultos: dict[str, str] = {}
    for uf in ('BR', *UFS):
        if 0 < agregados[uf].n < MIN_N:
            ocultos[uf] = 'primaria_n_pop_near_pequeno'
    if 'BR' not in ocultos:
        excluidos = [uf for uf in UFS if uf in ocultos]
        if len(excluidos) == 1:
            disponiveis = [uf for uf in UFS if uf not in ocultos
                           and agregados[uf].n >= MIN_N]
            if disponiveis:
                segundo = max(disponiveis, key=lambda uf: (agregados[uf].n, uf))
                ocultos[segundo] = 'complementar_geografica'
            else:
                ocultos['BR'] = 'complementar_nacional'
    return ocultos, {
        'min_n_divulgavel': MIN_N,
        'versao_politica_divulgacao': POLITICA_DIVULGACAO,
        'politica': ('nao_suprimir_recorte_por_mascara_exata_rara; '
                    'proteger_contagens_detalhadas_menores_30_e_complementos'),
        'bloqueio_integral_por_mascara_exata_rara': False,
        'mascaras_exatas_exportadas': False,
        'supressoes_primarias': sum(m.startswith('primaria') for m in ocultos.values()),
        'supressoes_complementares': sum(m.startswith('complementar') for m in ocultos.values()),
        'revisao_privacidade_cruzada_pendente': True,
    }


def proteger_contagens_detalhadas(testes: dict, n: int) -> int:
    """Oculta contagens diretas positivas 1..29, incluindo complementos.

    Não altera testes calculados: os valores estatísticos e p-valores
    continuam os mesmos. A proteção restringe só campos exportados.
    Retorna número de conjuntos de campos protegidos (para auditoria).
    Não é uma certificação de impossibilidade de inferência cruzada.
    """
    protegidos = 0
    for c in testes['ocorrencia']['frequencias_por_competencia']:
        qtd = int(c['n_com_desconto'])
        # O complemento n-qtd é a quantidade SEM desconto.
        if 0 < qtd < MIN_N or 0 < n - qtd < MIN_N:
            c['n_com_desconto'] = None
            c['percentual'] = None
            c['suprimido'] = True
            protegidos += 1
        else:
            c['suprimido'] = False
    for t in testes['pos_testes_ocorrencia']:
        b = int(t.get('discordantes_a_sim_b_nao', 0))
        c = int(t.get('discordantes_a_nao_b_sim', 0))
        info = int(t['n_pares_informativos'])
        if any(0 < x < MIN_N for x in (b, c, info)):
            # Suprimir conjuntamente evita reconstruir b ou c via b+c.
            for k in ('discordantes_a_sim_b_nao', 'discordantes_a_nao_b_sim',
                      'n_pares_informativos'):
                t[k] = None
            t['contagens_suprimidas'] = True
            protegidos += 1
        else:
            t['contagens_suprimidas'] = False
    for t in testes['pos_testes_magnitude']:
        info = int(t['n_pares_informativos'])
        if 0 < info < MIN_N:
            t['n_pares_informativos'] = None
            t['contagens_suprimidas'] = True
            protegidos += 1
        else:
            t['contagens_suprimidas'] = False
    return protegidos


def montar_recortes(agregados: dict[str, Acumulador]) -> tuple[dict, dict]:
    ocultos, privacidade = supressao_territorial(agregados)
    recortes = {}
    campos_protegidos = 0
    for uf in ('BR', *UFS):
        a = agregados[uf]
        motivo = ocultos.get(uf)
        testes = None if motivo or a.n == 0 else testar_recorte(a)
        if testes is not None:
            campos_protegidos += proteger_contagens_detalhadas(testes, a.n)
        recortes[uf] = {
            'uf': uf, 'populacao': 'POP_NEAR', 'intervalo_nota': [900, 980],
            'n_near': a.n, 'suprimido': bool(motivo), 'motivo_supressao': motivo,
            'tests': testes, 'status_publicacao':
            'revisao_academica_e_privacidade_cruzada_pendente',
            'n_registros_individuais_exportados': 0,
        }
    privacidade['conjuntos_campos_detalhados_protegidos'] = campos_protegidos
    privacidade['recortes_com_testes'] = sum(r['tests'] is not None for r in recortes.values())
    return recortes, privacidade


def carregar_json(caminho: Path) -> dict:
    with caminho.open('r', encoding='utf-8-sig') as arq:
        obj = json.load(arq)
    if not isinstance(obj, dict):
        raise ValueError(f'{caminho}: JSON não é objeto.')
    return obj


def controlar_ind031_032(saida: Path, ano: int,
                         agregados: dict[str, Acumulador]) -> dict:
    """Conferência numérica independente com referências do dashboard, se presentes."""
    caminho = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
    if not caminho.exists():
        return {'ind031': 'dashboard_ausente', 'ind032': 'dashboard_ausente'}
    painel = carregar_json(caminho)
    high = painel.get('pages', {}).get('high_performance', {})
    ind031 = high.get('loss_by_competency') if isinstance(high, dict) else None
    res31 = 'nao_disponivel'
    if isinstance(ind031, dict) and ind031.get('indicator_id') == 'IND-031':
        partes = {'BR': ind031['brasil']}
        partes.update({r['uf']: r for r in ind031.get('by_uf', [])})
        if set(partes) != {'BR', *UFS}:
            raise ValueError(f'{ano}: IND-031 sem 28 recortes completos.')
        for uf, r in partes.items():
            a = agregados[uf]
            if int(r['n_near']) != a.n:
                raise ValueError(f'{ano}/{uf}: POP_NEAR diverge do IND-031.')
            resumos = r.get('resumo_competencias', [])
            for c in resumos:
                i = int(c['competencia'][1:]) - 1
                soma = c.get('soma_pontos_perdidos')
                if soma is not None and abs(float(soma) - int(a.soma_perdas[i])) > 1e-6:
                    raise ValueError(f'{ano}/{uf}/C{i+1}: soma de perdas difere do IND-031.')
        res31 = 'aprovado_n_pop_e_somas'
    ind032 = high.get('discount_frequency') if isinstance(high, dict) else None
    res32 = 'nao_disponivel'
    if isinstance(ind032, dict) and ind032.get('indicator_id') == 'IND-032':
        partes = {'BR': ind032['brasil']}
        partes.update({r['uf']: r for r in ind032.get('by_uf', [])})
        if set(partes) != {'BR', *UFS}:
            raise ValueError(f'{ano}: IND-032 sem 28 recortes completos.')
        for uf, r in partes.items():
            a = agregados[uf]
            if int(r['n_near']) != a.n:
                raise ValueError(f'{ano}/{uf}: POP_NEAR diverge do IND-032.')
            for c in r.get('resumo_competencias', []):
                cod = c.get('competencia')
                if cod in COMPETENCIAS and c.get('n_com_desconto') is not None:
                    i = int(cod[1:]) - 1
                    if int(c['n_com_desconto']) != int(a.descontos[i]):
                        raise ValueError(f'{ano}/{uf}/{cod}: frequência difere do IND-032.')
        res32 = 'aprovado_n_pop_e_frequencias'
    return {'ind031': res31, 'ind032': res32}


def salvar_json_atomico(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix=caminho.name+'.', suffix='.tmp',
                                         delete=False) as arq:
            temp = Path(arq.name)
            json.dump(dados, arq, ensure_ascii=False, allow_nan=False, indent=2)
            arq.write('\n')
        os.replace(temp, caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def salvar_csv_atomico(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as arq:
            temp = Path(arq.name)
            writer = csv.DictWriter(arq, fieldnames=CAMPOS_CSV, delimiter=';',
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(linhas)
        os.replace(temp, caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def linhas_csv(todos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(todos.items(), key=lambda item: int(item[0])):
        if obj.get('status') != 'ok':
            continue
        for uf, rec in obj['recortes'].items():
            testes = rec['tests']
            if testes is None:
                continue
            for familia, bloco in [('ocorrencia', testes['ocorrencia']),
                                   ('magnitude', testes['magnitude'])]:
                linhas.append({
                    'ano': int(ano), 'uf': uf, 'n_near': rec['n_near'],
                    'familia': familia, 'teste': bloco['teste'],
                    'estatistica': bloco['estatistica'], 'p_valor': bloco['p_valor'],
                    'significativo_5pct': bloco['significativo_5pct'],
                    'status_teste': bloco['status'],
                    'status_publicacao': rec['status_publicacao'],
                })
            for chave in ('pos_testes_ocorrencia', 'pos_testes_magnitude'):
                for teste in testes[chave]:
                    linhas.append({
                        'ano': int(ano), 'uf': uf, 'n_near': rec['n_near'],
                        'familia': teste['familia'], 'teste': teste['teste'],
                        'competencia_a': teste['competencia_a'],
                        'competencia_b': teste['competencia_b'],
                        'estatistica': teste['estatistica'], 'p_valor': teste['p_valor'],
                        'p_ajustado_holm': teste['p_ajustado_holm'],
                        'significativo_5pct': teste['significativo_5pct'],
                        'n_pares_informativos': teste['n_pares_informativos'],
                        'status_teste': teste['status'],
                        'status_publicacao': rec['status_publicacao'],
                    })
    return linhas


def integrar_dashboards(saida: Path, processados: dict, parametros: dict) -> None:
    for ano_texto, obj in sorted(processados.items(), key=lambda p: int(p[0])):
        if obj.get('status') != 'ok':
            continue
        ano = int(ano_texto)
        caminho = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            log(f'  Dashboard {ano} não encontrado; integração ignorada.')
            continue
        doc = carregar_json(caminho)
        hp = doc.get('pages', {}).get('high_performance')
        if not isinstance(hp, dict):
            raise ValueError(f'{caminho}: pages.high_performance não é objeto.')
        hp['tests'] = {
            'indicator_id': 'IND-037', 'status': 'draft', 'year': ano,
            'population': 'POP_NEAR', 'parameters': parametros,
            'brasil': obj['recortes']['BR'],
            'by_uf': [obj['recortes'][uf] for uf in UFS],
            'publication_note': 'Revisão acadêmica e de privacidade cruzada obrigatória.',
        }
        hp['status'] = 'partial'
        hp['reason'] = ('IND-037 integrado em rascunho; validação acadêmica '
                        'e privacidade cruzada pendentes.')
        doc.setdefault('quality', {})['ind037_validation'] = {
            'status': 'ok_agregados', 'n_near_brasil': obj['n_near_brasil'],
            'soma_27_ufs_igual_brasil': True,
            'recalculado_com_microdados': True,
            'metodos': 'cochran_q_friedman_mcnemar_wilcoxon_holm',
            'controles': obj['controles'], 'privacidade': obj['privacidade'],
            'revisao_academica_e_privacidade_pendente': True,
        }
        aviso = ('IND-037: testes pareados sobre POP_NEAR; política revisada de '
                 'divulgação de testes agregados; significância não implica '
                 'causalidade; revisão acadêmica e privacidade cruzada pendentes.')
        avisos = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json_atomico(caminho, doc)
        log(f'  Dashboard {ano} integrado sem arquivos .bak.')


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool, exigir_2025: bool,
             _teste: bool = False,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    out_json = saida/'outputs'/'json'/'IND_037_concentracao_descontos.json'
    out_csv = saida/'outputs'/'indicadores'/'IND_037_concentracao_descontos.csv'
    if not sobrescrever and (out_json.exists() or out_csv.exists()):
        raise FileExistsError('IND-037 já existe; utilize --sobrescrever.')
    nomes = set()
    for ano in anos:
        if ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
        else:
            nomes.add('RESULTADOS_2025.CSV')
    fontes = localizar_fontes(base, nomes, fontes_explicitas)
    faltantes = sorted(nomes - set(fontes) - (set() if exigir_2025 else {'RESULTADOS_2025.CSV'}))
    if faltantes:
        raise FileNotFoundError('Fontes ausentes: ' + ', '.join(faltantes))
    anteriores = {}
    if sobrescrever and out_json.is_file():
        antigo = carregar_json(out_json)
        if antigo.get('indicator_id') != 'IND-037':
            raise ValueError('JSON pré-existente não corresponde ao IND-037.')
        anteriores = dict(antigo.get('years', {}))
        parametros_anteriores = antigo.get('parameters', {})
        politica_anterior = parametros_anteriores.get('politica_divulgacao')
        if politica_anterior != POLITICA_DIVULGACAO and any(
                int(y) not in anos for y in anteriores):
            raise ValueError('Política de divulgação diferente da execução anterior. '
                             'Reprocesse TODOS os anos já presentes no JSON com '
                             '--sobrescrever para não misturar resultados de políticas '
                             'diferentes. Não é necessário apagar os arquivos.')
    todos = dict(anteriores)
    processados = {}
    for ano in anos:
        log(f'IND-037 | {ano} — concentração de descontos na POP_NEAR...')
        if ano == 2025 and 'RESULTADOS_2025.CSV' not in fontes:
            obj = {'ano': 2025, 'status': 'indisponivel', 'recortes': {},
                   'motivo': 'RESULTADOS_2025.csv não disponível; testes não calculados.'}
            todos[str(ano)] = processados[str(ano)] = obj
            log('  2025 indisponível — nenhum resultado estimado.')
            continue
        if ano == 2024:
            agregados, validas, diagnostico = ler_2024(
                fontes['PARTICIPANTES_2024.CSV'],
                fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            nome = f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023 else 'RESULTADOS_2025.CSV'
            agregados, validas, diagnostico = ler_mesma_linha(fontes[nome], bloco)
            fonte = fontes[nome].name
        agregados = fechar_agregados(agregados, ano, validas, _teste)
        controles = ({'ind031': 'autoteste', 'ind032': 'autoteste'} if _teste
                     else controlar_ind031_032(saida, ano, agregados))
        if (diagnostico.get('n_pop_near_vinculadas', agregados['BR'].n)
                != agregados['BR'].n):
            raise ValueError(f'{ano}: vínculo dos participantes não fecha com POP_NEAR.')
        recortes, privacidade = montar_recortes(agregados)
        obj = {
            'ano': ano, 'status': 'ok', 'fonte': fonte,
            'population': 'POP_NEAR', 'n_validas_brasil': validas,
            'n_near_brasil': agregados['BR'].n,
            'diagnostico_fonte': diagnostico,
            'controles': controles, 'privacidade': privacidade,
            'recortes': recortes,
        }
        todos[str(ano)] = processados[str(ano)] = obj
        n_calc = sum(r['tests'] is not None for r in recortes.values())
        log(f'  Brasil POP_NEAR={obj["n_near_brasil"]:,}; '
            f'recortes com testes={n_calc}; '
            f'ocultos={len(recortes)-n_calc} (inclui vazios).')
    parametros = {
        'alpha': ALFA, 'min_n': MIN_N,
        'politica_divulgacao': POLITICA_DIVULGACAO,
        'ocorrencia': 'Q_de_Cochran + McNemar_exato + Holm_10',
        'magnitude': 'Friedman_empates + Wilcoxon_pareado_normal_empates + Holm_10',
        'hipoteses_pareadas': True,
    }
    modulo = {
        'indicator_id': 'IND-037', 'titulo': 'Concentração de descontos',
        'status': 'draft', 'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(x) for x, v in todos.items() if v.get('status') == 'ok'),
        'population': 'POP_NEAR', 'geography': 'SG_UF_PROVA',
        'parameters': parametros,
        'methodology': {
            'selection': 'TP_STATUS_REDACAO=1 e 900<=NU_NOTA_REDACAO<=980',
            'discount_occurrence': 'I(NU_NOTA_COMPi<200) em C1..C5 da mesma redação',
            'discount_magnitude': 'Li=200-NU_NOTA_COMPi',
            'omnibus_occurrence': 'Q de Cochran, qui-quadrado assintótico gl=4',
            'omnibus_magnitude': 'Friedman com postos médios e correção de empates, gl=4',
            'effect_size': 'W de Kendall = qui-quadrado de Friedman / [N*(5-1)]',
            'posthoc_occurrence': 'McNemar exato bicaudal, 10 pares, Holm',
            'posthoc_magnitude': 'Wilcoxon signed-rank, zeros excluídos, ties, normal, 10 pares, Holm',
            'posthoc_families': 'Holm aplicado separadamente à ocorrência e magnitude',
            '2024_join': 'NU_INSCRICAO em SQLite temporário',
            'privacy': ('testes agregados para N>=30, independentemente de máscaras exatas raras; '
                        'supressão de contagens pequenas detalhadas e complementos; revisão cruzada pendente'),
            'cautions': [
                'Significância estatística não é causalidade, tamanho prático nem erro de correção.',
                'POP_NEAR é condicionada à nota total, soma das cinco competências; há dependência estrutural.',
                'McNemar e Wilcoxon são pareados; p-valores podem ser muito baixos com N elevado.',
                'Wilcoxon assintótico tem empates e depende da simetria das diferenças para interpretação de localização.',
                'As dez comparações por família recebem ajuste de Holm; famílias não são ajustadas conjuntamente.',
                'UF da prova não é UF de residência. Série anual conta participações, não pessoas únicas.',
                'Resultados públicos exigem revisão acadêmica, estabilidade e privacidade cruzada.',
                '2025 não é inferido na ausência de microdados.',
            ],
        },
        'years': todos,
    }
    salvar_json_atomico(out_json, modulo)
    salvar_csv_atomico(out_csv, linhas_csv(todos))
    log(f'JSON: {out_json}\nCSV: {out_csv}')
    if not somente_modulo:
        integrar_dashboards(saida, processados, parametros)
    log('IND-037 concluído em draft com política revisada; revisão acadêmica/privacidade pendente.')
    return modulo


def autoteste() -> None:
    """Confere fórmulas contra SciPy, leitura 2024, duplicatas e integração."""
    from scipy.stats import friedmanchisquare, wilcoxon
    from tempfile import TemporaryDirectory
    # Amostra com empates, postos e padrões diferentes por competência.
    matriz = np.array([
        [40, 0, 20, 0, 20],
        [20, 0, 40, 20, 0],
        [0, 40, 20, 0, 20],
        [20, 20, 20, 20, 0],
        [20, 0, 20, 0, 40],
        [40, 20, 0, 0, 20],
    ] * 40, dtype=np.int16)
    # Todas as redações têm soma de perdas 80 => nota 920.
    assert set(np.sum(matriz, axis=1).tolist()) == {80}
    a = Acumulador()
    a.adicionar(matriz[:101])
    a.adicionar(matriz[101:])
    assert a.n == 240 and int(a.mascaras.sum()) == 240
    f = friedman(a)
    f_ref = friedmanchisquare(*[matriz[:, i] for i in range(5)])
    assert np.isclose(f['estatistica'], f_ref.statistic, rtol=0, atol=1e-6)
    assert np.isclose(f['p_valor'], f_ref.pvalue, rtol=1e-9, atol=1e-12)
    q = cochran_q(a)
    flags = (matriz > 0).astype(np.int64)
    c = flags.sum(axis=0)
    r = flags.sum(axis=1)
    manual = (4 * (5 * int(np.dot(c, c)) - int(c.sum())**2)
              / (5 * int(c.sum()) - int(np.dot(r, r))))
    assert np.isclose(q['estatistica'], manual)
    for p, (i, j) in enumerate(PARES):
        dif = matriz[:, i].astype('int64') - matriz[:, j].astype('int64')
        resultado = wilcoxon_por_histograma(a.diferencas[p])
        if np.any(dif):
            ref = wilcoxon(dif, zero_method='wilcox', correction=False,
                           alternative='two-sided', method='approx')
            assert abs(resultado['p_valor'] - ref.pvalue) < 0.005, (i, j, resultado, ref)
    assert holm([0.01, 0.04, 0.004]) == [0.02, 0.04, 0.012]
    assert mcnemar_exato(a.mascaras, 0, 1)['p_valor'] <= 1.0
    # Máscara exata rara não pode mais ocultar o país ou o estado inteiro.
    pequeno_padrao = np.array([[20, 0, 20, 20, 20]] * 59 +
                              [[0, 20, 20, 20, 20]], dtype=np.int16)
    raro = Acumulador()
    raro.adicionar(pequeno_padrao)
    assert raro.n == 60 and any(0 < int(x) < MIN_N for x in raro.mascaras)
    geos = {uf: Acumulador() for uf in ('BR', *UFS)}
    geos['SP'] = raro
    geos['RJ'].adicionar(matriz[:60])
    geos['BR'].somar(raro)
    geos['BR'].somar(geos['RJ'])
    ocultos, metadados = supressao_territorial(geos)
    assert 'SP' not in ocultos and 'BR' not in ocultos
    assert not metadados['bloqueio_integral_por_mascara_exata_rara']
    recortes, _ = montar_recortes(geos)
    assert recortes['SP']['tests'] is not None
    assert recortes['BR']['tests'] is not None
    assert recortes['SP']['tests']['ocorrencia']['estatistica'] == cochran_q(raro)['estatistica']
    assert recortes['SP']['tests']['magnitude']['estatistica'] == friedman(raro)['estatistica']
    # Proteção de contagens diretas: se o complemento for menor que 30,
    # não exportar n_com_desconto, percentual, nem par discordante pequeno.
    assert any(c['suprimido'] for c in recortes['SP']['tests']['ocorrencia']['frequencias_por_competencia'])
    for item in recortes['SP']['tests']['ocorrencia']['frequencias_por_competencia']:
        assert item['n_com_desconto'] is None or not (0 < item['n_com_desconto'] < MIN_N)
    # Um recorte com N<30 ainda é ocultado, e seu complemento geográfico também.
    geos2 = {uf: Acumulador() for uf in ('BR', *UFS)}
    geos2['AC'].adicionar(pequeno_padrao[:5])
    geos2['SP'].adicionar(matriz)
    geos2['BR'].somar(geos2['AC'])
    geos2['BR'].somar(geos2['SP'])
    ocultos2, _ = supressao_territorial(geos2)
    assert ocultos2['AC'].startswith('primaria') and ocultos2['SP'] == 'complementar_geografica'
    with TemporaryDirectory(prefix='teste_ind037_') as pasta:
        root = Path(pasta)
        raw = root/'data'/'raw'/'2024'
        raw.mkdir(parents=True)
        (root/'outputs'/'json').mkdir(parents=True)
        tabela = pd.DataFrame({
            'TP_STATUS_REDACAO': ['1'] * len(matriz),
            'NU_NOTA_REDACAO': (1000 - matriz.sum(axis=1)).astype(str),
            'SG_UF_PROVA': ['SP'] * 120 + ['RJ'] * 120,
            **{COLUNAS_C[i]: (200 - matriz[:, i]).astype(str) for i in range(5)},
        })
        for nome, subset in [('MICRODADOS_ENEM_2019.csv', tabela)]:
            subset.to_csv(raw/nome, sep=';', index=False)
        h19, nv19, _ = ler_mesma_linha(raw/'MICRODADOS_ENEM_2019.csv', 71)
        fechar_agregados(h19, 2019, nv19, _teste=True)
        assert h19['BR'].n == 240
        part = pd.DataFrame({'NU_INSCRICAO': [str(100000+i) for i in range(len(tabela))],
                             'SG_UF_PROVA': tabela['SG_UF_PROVA'].values})
        comp = tabela.drop(columns='SG_UF_PROVA').copy()
        comp.insert(0, 'NU_INSCRICAO', part['NU_INSCRICAO'])
        part.to_csv(raw/'PARTICIPANTES_2024.csv', sep=';', index=False)
        comp.to_csv(raw/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        pasta2 = raw/'competencias_redacao'
        pasta2.mkdir()
        duplicado = pasta2/'COMPETENCIAS_REDACAO_2024.csv'
        duplicado.write_bytes((raw/'COMPETENCIAS_REDACAO_2024.csv').read_bytes())
        fontes = localizar_fontes(root, {'COMPETENCIAS_REDACAO_2024.CSV'})
        assert len(fontes) == 1
        h24, nv24, diag = ler_2024(raw/'PARTICIPANTES_2024.csv',
                                   raw/'COMPETENCIAS_REDACAO_2024.csv', 71)
        fechar_agregados(h24, 2024, nv24, _teste=True)
        assert nv24 == 240 and h24['BR'].n == 240
        assert diag['n_pop_near_vinculadas'] == 240
        doc = {'pages': {'high_performance': {'outro': {'preservado': True}}},
               'quality': {'outro': {'preservado': True}}, 'meta': {'warnings': []}}
        salvar_json_atomico(root/'outputs'/'json'/'dashboard_enem_2024.json', doc)
        resultado = executar(root, root, (2024,), 79, False, False, False, _teste=True)
        assert resultado['years']['2024']['n_near_brasil'] == 240
        painel = carregar_json(root/'outputs'/'json'/'dashboard_enem_2024.json')
        assert painel['pages']['high_performance']['tests']['indicator_id'] == 'IND-037'
        assert painel['pages']['high_performance']['outro']['preservado']
        assert painel['quality']['outro']['preservado']
        assert (root/'outputs'/'indicadores'/'IND_037_concentracao_descontos.csv').is_file()
        assert resultado['parameters']['politica_divulgacao'] == POLITICA_DIVULGACAO
        assert painel['pages']['high_performance']['tests']['parameters']['politica_divulgacao'] == POLITICA_DIVULGACAO
        # Simula existência de JSON da política antiga e tenta execução parcial.
        antigo_arq = root/'outputs'/'json'/'IND_037_concentracao_descontos.json'
        doc_antigo = carregar_json(antigo_arq)
        doc_antigo['parameters'].pop('politica_divulgacao')
        doc_antigo['years']['2019'] = {'ano': 2019, 'status': 'ok', 'recortes': {}}
        salvar_json_atomico(antigo_arq, doc_antigo)
        try:
            executar(root, root, (2024,), 79, True, True, False, _teste=True)
        except ValueError as erro:
            assert 'Reprocesse TODOS os anos' in str(erro)
        else:
            raise AssertionError('Mistura de políticas antigas e novas não foi bloqueada.')
        assert not list(root.rglob('*.bak*'))
        # Fonte divergente com mesmo nome deve ser rejeitada explicitamente.
        duplicado.write_text('diferente', encoding='utf-8')
        try:
            localizar_fontes(root, {'COMPETENCIAS_REDACAO_2024.CSV'})
        except ValueError as e:
            assert 'Fontes diferentes' in str(e)
        else:
            raise AssertionError('Duplicatas divergentes foram aceitas silenciosamente.')
    log('Autoteste IND-037 corrigido aprovado: Cochran Q, Friedman, Wilcoxon, Holm, '
        'máscara rara sem bloqueio integral, proteção de contagens pequenas, '
        'política versionada, duplicatas, 2019/2024, SQLite, CSV/JSON e dashboard.')


def main() -> None:
    p = argparse.ArgumentParser(description='IND-037 — Concentração de descontos')
    p.add_argument('--base', type=Path, default=raiz_projeto())
    p.add_argument('--saida', type=Path, default=raiz_projeto())
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    p.add_argument('--bloco', type=int, default=100_000,
                   help='Tamanho do lote na leitura dos microdados.')
    p.add_argument('--sobrescrever', action='store_true')
    p.add_argument('--somente-modulo', action='store_true',
                   help='Gerar CSV/JSON apenas; não alterar dashboards.')
    p.add_argument('--exigir-2025', action='store_true')
    p.add_argument('--autoteste', action='store_true')
    p.add_argument('--competencias-2024', type=Path, default=None,
                   help='Indicar CSV correto caso haja cópias diferentes em 2024.')
    p.add_argument('--participantes-2024', type=Path, default=None,
                   help='Indicar CSV correto caso haja cópias diferentes em 2024.')
    args = p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(ano not in ANOS for ano in anos):
        p.error('Use --anos com anos entre 2019 e 2025.')
    if args.bloco <= 0:
        p.error('--bloco deve ser positivo.')
    fontes = {}
    if args.competencias_2024 is not None:
        fontes['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        fontes['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.exigir_2025, fontes_explicitas=fontes)
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as erro:
        print(f'ERRO IND-037: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
