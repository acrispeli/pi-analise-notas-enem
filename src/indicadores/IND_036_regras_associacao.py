#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-036 — Regras de associação de descontos (Apriori) | ENEM 2019–2025.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores ENEM v2.

Universo POP_NEAR: TP_STATUS_REDACAO=1, nota final entre 900 e 980
(inclusive), e competências C1–C5 válidas de 0 a 200, cuja soma
reproduza a nota total. Transação = conjunto de competências com Ci < 200.

Apriori encontra conjuntos frequentes e produz regras A -> B, A e B
não vazios e disjuntos. Suporte = N(A união B)/N_near;
confiança = N(A união B)/N(A); lift = confiança / (N(B)/N_near).
Lift > 1 indica associação positiva, não causalidade ou erro de correção.
A seleção por nota 900..980 condiciona as frequências e associações.

Fontes:
  2019-2023: MICRODADOS_ENEM_<ano>.csv, mesma linha.
  2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv,
        vinculados por NU_INSCRICAO em SQLite temporário.
  2025: RESULTADOS_2025.csv, se existir com todas as variáveis.

Saídas:
  outputs/json/IND_036_regras_associacao.json
  outputs/indicadores/IND_036_regras_associacao.csv
  outputs/json/dashboard_enem_<ano>.json, campo
    pages.high_performance.association_rules + quality.ind036_validation.

As regras de associação são análise exploratória não supervisionada.
Política de divulgação revisada: uma combinação EXATA rara (1..29)
não bloqueia todo o Brasil/UF. São divulgadas apenas regras agregadas
cujos itemsets, antecedente e consequente tenham >=30 observações,
além do suporte percentual mínimo. Recortes com N_near 1..29 continuam
ocultos, com supressão territorial complementar quando aplicável.
A revisão de privacidade cruzada e acadêmica continua pendente.
Sem arquivos de backup .bak; arquivos substituídos atomicamente.

Uso:
  python src/indicadores/IND_036_regras_associacao.py --autoteste
  python src/indicadores/IND_036_regras_associacao.py --anos 2024 --sobrescrever
  python src/indicadores/IND_036_regras_associacao.py --sobrescrever
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
import csv
import filecmp
import json
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
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
COLUNAS_C = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
MIN_N = 30  # Critério de frequência mínima dos itemsets e de N do recorte.
POLITICA_DIVULGACAO = 'regras_agregadas_sem_bloqueio_mascara_rara_v2'
POP_NEAR_REFERENCIA = {
    2019: 172_548, 2020: 183_343, 2021: 163_747,
    2022: 197_083, 2023: 288_602, 2024: 291_111,
    2025: 173_533,
}

def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    local = Path(__file__).resolve()
    if local.parent.name.lower() == 'indicadores' and local.parent.parent.name.lower() == 'src':
        return local.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                    fontes_explicitas: dict[str, Path] | None = None) -> dict[str, Path]:
    """Localiza fontes sem escolher silenciosamente entre arquivos diferentes.

    - Cópias byte a byte idênticas são intercambiáveis e permitidas.
    - Cópias diferentes exigem uma escolha explícita via linha de comando.
    - Fonte explícita tem prioridade e dispensa comparar outras cópias desse nome.
    """
    ignorados = {'.git', '.venv', 'venv', '__pycache__', 'outputs', '.pytest_cache',
                 'node_modules', '.mypy_cache'}
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
            raise FileNotFoundError(f'Fonte indicada para {chave} não encontrada: {caminho}.')
        encontrados[chave] = caminho
        log(f'  Fonte selecionada para {chave}: {caminho}')

    for raiz, pastas, arquivos in os.walk(base):
        pastas[:] = sorted(p for p in pastas if p.lower() not in ignorados)
        for nome in sorted(arquivos):
            chave = nome.upper()
            if chave not in nomes or chave in fontes_explicitas:
                continue
            caminho = Path(raiz) / nome
            if chave in encontrados and encontrados[chave].resolve() != caminho.resolve():
                anterior = encontrados[chave]
                # filecmp sem cache superficial: compara todo o conteúdo de modo exato.
                if filecmp.cmp(anterior, caminho, shallow=False):
                    log(f'  Arquivos idênticos para {chave}; usando {anterior}.')
                    continue
                dica = (' Use --competencias-2024 <caminho> para escolher a fonte.'
                        if chave == 'COMPETENCIAS_REDACAO_2024.CSV' else
                        ' Use a opção de fonte explícita correspondente ou revise os arquivos.')
                raise ValueError(f'Fontes diferentes com o mesmo nome {chave}: '
                                 f'{anterior} e {caminho}.{dica}')
            encontrados[chave] = caminho
    return encontrados


def ler_blocos(caminho: Path, colunas: list[str], bloco: int):
    with caminho.open('rb') as arq:
        encoding = 'utf-8-sig' if arq.read(3) == b'\xef\xbb\xbf' else 'latin-1'
    cabecalho = pd.read_csv(caminho, sep=';', encoding=encoding, nrows=0)
    existentes = set(str(c).strip().lstrip('\ufeff') for c in cabecalho.columns)
    faltantes = sorted(set(colunas) - existentes)
    if faltantes:
        raise ValueError(f'{caminho.name}: colunas ausentes: {faltantes}.')
    with pd.read_csv(caminho, sep=';', encoding=encoding, usecols=colunas,
                     dtype='string', chunksize=bloco, na_filter=False,
                     keep_default_na=False, low_memory=False) as leitor:
        for dados in leitor:
            dados.columns = [str(c).strip().lstrip('\ufeff') for c in dados.columns]
            yield dados


def numerico(coluna: pd.Series, nome: str) -> np.ndarray:
    serie = coluna.astype('string').str.strip().str.replace(',', '.', regex=False)
    numeros = pd.to_numeric(serie, errors='coerce').to_numpy(dtype='float64')
    if not np.isfinite(numeros).all():
        raise ValueError(f'{nome}: existe nota ausente, não numérica ou infinita em população elegível.')
    return numeros


def selecionar_near(lote: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    elegiveis = lote['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')
    validas = lote.loc[elegiveis].copy()
    if validas.empty:
        return validas, 0
    nota = numerico(validas['NU_NOTA_REDACAO'], 'NU_NOTA_REDACAO')
    if ((nota < 0) | (nota > 1000)).any():
        raise ValueError('Nota total fora do intervalo [0,1000] para TP_STATUS_REDACAO=1.')
    validas['__nota_total'] = nota
    near = validas.loc[(nota >= 900) & (nota <= 980)].copy()
    return near, len(validas)


def gerar_mascaras(near: pd.DataFrame) -> np.ndarray:
    """Retorna um bitmask 1..31 por redação, verificando C1+..+C5 = total."""
    if near.empty:
        return np.empty(0, dtype=np.uint8)
    notas = np.column_stack([numerico(near[col], col) for col in COLUNAS_C])
    if ((notas < 0) | (notas > 200)).any():
        raise ValueError('Nota de competência fora de [0,200] em POP_NEAR.')
    total = near['__nota_total'].to_numpy(dtype='float64')
    soma_invalida = ~np.isclose(notas.sum(axis=1), total, rtol=0, atol=1e-6)
    if soma_invalida.any():
        raise ValueError(f'{int(soma_invalida.sum())} redação(ões) POP_NEAR com '
                         'soma C1..C5 diferente da nota total; investigar fonte.')
    flags = (notas < 200).astype(np.uint8)
    bitmask = flags @ np.array([1, 2, 4, 8, 16], dtype=np.uint8)
    if (bitmask == 0).any():
        raise ValueError('POP_NEAR com cinco competências de 200 pontos: '
                         'incompatível com nota final 900..980.')
    return bitmask


def novo_histograma() -> np.ndarray:
    return np.zeros(32, dtype=np.int64)


def adicionar_histograma(hist: dict, uf: str, contagens: np.ndarray) -> None:
    if uf not in UFS:
        raise ValueError(f'UF da prova inválida em POP_NEAR: {uf!r}.')
    if contagens.shape != (32,) or (contagens < 0).any():
        raise ValueError('Histograma de máscaras de descontos inválido.')
    hist['BR'] += contagens
    hist[uf] += contagens


def acumular_near(hist: dict, near: pd.DataFrame) -> None:
    if near.empty:
        return
    ufs = near['SG_UF_PROVA'].astype('string').str.strip().str.upper().to_numpy()
    if not pd.Series(ufs).isin(UFS).all():
        raise ValueError('SG_UF_PROVA ausente ou inválida em POP_NEAR.')
    masks = gerar_mascaras(near)
    for uf in np.unique(ufs):
        cont = np.bincount(masks[ufs == uf].astype(int), minlength=32)
        adicionar_histograma(hist, str(uf), cont)


def ler_mesma_linha(caminho: Path, bloco: int) -> tuple[dict, int, dict]:
    hist = defaultdict(novo_histograma)
    n_validas = 0
    cols = ['TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', 'SG_UF_PROVA', *COLUNAS_C]
    for parte in ler_blocos(caminho, cols, bloco):
        near, n = selecionar_near(parte)
        n_validas += n
        acumular_near(hist, near)
    return dict(hist), n_validas, {'metodo': 'mesma_linha'}


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Vincula 2024 por NU_INSCRICAO; rejeita duplicatas e falta de vínculo."""
    hist = defaultdict(novo_histograma)
    with tempfile.TemporaryDirectory(prefix='enem_ind035_') as pasta:
        banco = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            banco.execute('PRAGMA journal_mode=OFF')
            banco.execute('PRAGMA synchronous=OFF')
            banco.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL) WITHOUT ROWID')
            banco.execute('CREATE TABLE near_vistos(id TEXT PRIMARY KEY) WITHOUT ROWID')
            banco.execute('CREATE TEMP TABLE lote(id TEXT NOT NULL, mascara INTEGER NOT NULL)')
            n_participantes = 0
            for parte in ler_blocos(participantes, ['NU_INSCRICAO', 'SG_UF_PROVA'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(not x for x in ids) or any(x not in UFS for x in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    banco.executemany('INSERT INTO participantes VALUES (?,?)', zip(ids, ufs))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from exc
                n_participantes += len(ids)
            banco.commit()
            log(f'  Participantes 2024 indexados: {n_participantes:,}')

            n_validas = 0
            n_near_vinculadas = 0
            cols = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COLUNAS_C]
            for parte in ler_blocos(competencias, cols, bloco):
                near, n = selecionar_near(parte)
                n_validas += n
                if near.empty:
                    continue
                ids = near['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not x for x in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em POP_NEAR.')
                masks = gerar_mascaras(near)
                try:
                    banco.executemany('INSERT INTO near_vistos VALUES (?)', ((x,) for x in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: NU_INSCRICAO repetida em POP_NEAR.') from exc
                banco.execute('DELETE FROM lote')
                banco.executemany('INSERT INTO lote VALUES (?,?)',
                                  ((ident, int(mascara)) for ident, mascara in zip(ids, masks)))
                vinculadas = int(banco.execute('''SELECT COUNT(*) FROM lote l
                    JOIN participantes p ON p.id=l.id''').fetchone()[0])
                if vinculadas != len(ids):
                    raise ValueError(f'2024: {len(ids)-vinculadas} redações POP_NEAR '
                                     'não vinculadas a PARTICIPANTES_2024.csv.')
                for uf, mascara, qtd in banco.execute('''SELECT p.uf, l.mascara, COUNT(*)
                    FROM lote l JOIN participantes p ON p.id=l.id
                    GROUP BY p.uf, l.mascara'''):
                    tmp = np.zeros(32, dtype=np.int64)
                    tmp[int(mascara)] = int(qtd)
                    adicionar_histograma(hist, str(uf), tmp)
                n_near_vinculadas += vinculadas
                banco.commit()
            return dict(hist), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'n_participantes': n_participantes,
                'n_pop_near_vinculadas': n_near_vinculadas,
                'n_near_sem_correspondencia': 0,
            }
        finally:
            banco.close()



# Parâmetros pré-especificados, alteráveis por CLI. Os limiares não são
# p-valores nem garantem estabilidade ou significância das associações.
SUPORTE_PADRAO = 0.01
CONFIANCA_PADRAO = 0.30
LIFT_PADRAO = 1.00
MAX_REGRAS_PADRAO = 30
CAMPOS_CSV = (
    'ano', 'uf', 'n_near', 'antecedente', 'consequente', 'itemset',
    'n_antecedente', 'n_consequente', 'n_ambos',
    'suporte', 'suporte_percentual', 'confianca', 'confianca_percentual',
    'lift', 'leverage', 'status_publicacao',
)


def rotulos(mascara: int) -> list[str]:
    return [cod for i, cod in enumerate(COMPETENCIAS) if mascara & (1 << i)]


def conta_itemset(hist: np.ndarray, mascara: int) -> int:
    """Suporte absoluto inclusivo do itemset, sem percorrer microdados."""
    if mascara < 0 or mascara > 31:
        raise ValueError('Máscara de itemset inválida.')
    return int(sum(int(hist[bits]) for bits in range(32) if (bits & mascara) == mascara))


def n_near(hist: np.ndarray) -> int:
    return int(hist.sum())


def validar_histogramas_036(hists: dict, ano: int, n_validas: int,
                            controlar_pop: bool = True) -> None:
    """Fecha BR/UF máscara a máscara, inclusive zeros."""
    for uf in ('BR', *UFS):
        hists.setdefault(uf, novo_histograma())
        hist = hists[uf]
        if hist.shape != (32,) or (hist < 0).any():
            raise ValueError(f'{ano}/{uf}: histograma inválido.')
        if int(hist[0]) != 0:
            raise ValueError(f'{ano}/{uf}: redação sem desconto na POP_NEAR.')
        if n_near(hist) > n_validas:
            raise ValueError(f'{ano}/{uf}: POP_NEAR maior que a população válida.')
    combinado = np.zeros(32, dtype='int64')
    for uf in UFS:
        combinado += hists[uf]
    if not np.array_equal(combinado, hists['BR']):
        raise ValueError(f'{ano}: soma das 27 UFs difere do Brasil em alguma máscara.')
    if controlar_pop and ano in POP_NEAR_REFERENCIA:
        esperado = POP_NEAR_REFERENCIA[ano]
        observado = n_near(hists['BR'])
        if esperado != observado:
            raise ValueError(f'{ano}: POP_NEAR={observado} diverge de IND-031={esperado}.')


def apriori_frequentes(hist: np.ndarray, min_suporte: float) -> dict[int, int]:
    """Apriori por junção/pruning, com suportes obtidos do histograma de 32 máscaras.

    Só são frequentes itemsets com suporte >= min_suporte e N >= MIN_N.
    A restrição MIN_N é independente do limiar percentual.
    """
    n = n_near(hist)
    if n == 0:
        return {}
    import math
    minimo = max(MIN_N, math.ceil(min_suporte * n - 1e-10))
    suporte_cache: dict[int, int] = {}

    def suporte(m: int) -> int:
        if m not in suporte_cache:
            suporte_cache[m] = conta_itemset(hist, m)
        return suporte_cache[m]

    anterior = {1 << i for i in range(5) if suporte(1 << i) >= minimo}
    encontrados = {m: suporte(m) for m in anterior}
    tamanho = 2
    while anterior and tamanho <= 5:
        # Apriori: só pode ser frequente um k-itemset cujos (k-1)-subsets
        # sejam todos frequentes. Anti-monotonicidade dos suportes.
        candidatos = set()
        candidatos_lista = sorted(anterior)
        for a, b in combinations(candidatos_lista, 2):
            candidato = a | b
            if candidato.bit_count() != tamanho:
                continue
            if all((candidato & ~(1 << i)) in anterior
                   for i in range(5) if candidato & (1 << i)):
                candidatos.add(candidato)
        atual = {m for m in candidatos if suporte(m) >= minimo}
        encontrados.update({m: suporte(m) for m in atual})
        anterior = atual
        tamanho += 1
    return encontrados


def extrair_regras(hist: np.ndarray, min_suporte: float,
                   min_confianca: float, min_lift: float,
                   max_regras: int) -> tuple[list[dict], dict]:
    n = n_near(hist)
    frequentes = apriori_frequentes(hist, min_suporte)
    candidatas: list[dict] = []
    for conjunto, n_ambos in sorted(frequentes.items()):
        if conjunto.bit_count() < 2:
            continue
        # Todos os antecedentes não vazios e próprios de um itemset
        for ant in range(1, 32):
            if ant == conjunto or ant & conjunto != ant:
                continue
            cons = conjunto ^ ant
            n_ant = frequentes.get(ant)
            n_cons = frequentes.get(cons)
            # Anti-monotonicidade: os subconjuntos de conjuntos frequentes
            # também são frequentes; se não, é erro da implementação.
            if n_ant is None or n_cons is None or not n_ant or not n_cons:
                raise ValueError('Apriori: suporte de subconjunto ausente.')
            confianca = n_ambos / n_ant
            sup_consequente = n_cons / n
            lift = confianca / sup_consequente
            sup = n_ambos / n
            if (sup + 1e-12 < min_suporte or
                    confianca + 1e-12 < min_confianca or
                    lift + 1e-12 < min_lift):
                continue
            itens_a = rotulos(ant)
            itens_b = rotulos(cons)
            candidatas.append({
                'antecedente': itens_a,
                'consequente': itens_b,
                'itemset': rotulos(conjunto),
                'n_antecedente': n_ant,
                'n_consequente': n_cons,
                'n_ambos': n_ambos,
                'suporte': round(sup, 10),
                'suporte_percentual': round(100 * sup, 6),
                'confianca': round(confianca, 10),
                'confianca_percentual': round(100 * confianca, 6),
                'lift': round(lift, 10),
                'leverage': round(sup - (n_ant / n) * (n_cons / n), 10),
            })
    # Seleção estável, priorizando lift, depois confiança e suporte.
    candidatas.sort(key=lambda r: (
        -r['lift'], -r['confianca'], -r['suporte'],
        '+'.join(r['antecedente']), '+'.join(r['consequente'])
    ))
    dados = {
        'itemsets_frequentes': len(frequentes),
        'regras_que_atendem_limiares': len(candidatas),
        'regras_selecionadas': min(len(candidatas), max_regras),
        'truncamento_por_max_regras': len(candidatas) > max_regras,
    }
    return candidatas[:max_regras], dados


def supressao_territorial(hists: dict) -> tuple[dict[str, str], dict]:
    """Política revisada: NÃO ocultar toda UF/BR por máscara exata rara.

    Motivo: a divulgação é composta somente pelas regras agregadas
    frequentes; a distribuição das 31 máscaras exatas não é exportada.
    A restrição de >=30 observações continua aplicada a cada itemset
    participante das regras Apriori, inclusive A, B e A união B.

    Grupos com 1..29 redações são ocultos integralmente. Se exatamente
    uma UF for ocultada, outra UF (ou BR) é ocultada complementarmente.
    Isso não certifica proteção contra inferência por cruzamento com
    outros indicadores, por isso o status público permanece draft.
    """
    ocultos: dict[str, str] = {}
    for uf in ('BR', *UFS):
        n = n_near(hists[uf])
        if 0 < n < MIN_N:
            ocultos[uf] = 'primaria_pop_near_pequena'
    if 'BR' not in ocultos:
        primarios = [u for u in UFS if u in ocultos]
        if len(primarios) == 1:
            candidatos = [u for u in UFS if u not in ocultos and n_near(hists[u]) >= MIN_N]
            if candidatos:
                outro = max(candidatos, key=lambda u: (n_near(hists[u]), u))
                ocultos[outro] = 'complementar_geografica'
            else:
                ocultos['BR'] = 'complementar_nacional'
    return ocultos, {
        'minimo_contagem_divulgavel': MIN_N,
        'versao_politica_divulgacao': POLITICA_DIVULGACAO,
        'criterio': ('nao_ocultar_recorte_por_mascara_exata_rara; divulgar_apenas_'
                     'regras_com_antecedente_consequente_uniao_n_maior_igual_30'),
        'bloqueio_integral_por_mascara_exata_rara': False,
        'mascaras_exatas_exportadas': False,
        'recortes_suprimidos_primarios': sum(m.startswith('primaria') for m in ocultos.values()),
        'recortes_suprimidos_complementares': sum(m.startswith('complementar') for m in ocultos.values()),
        'revisao_privacidade_cruzada_pendente': True,
    }


def montar_recortes(hists: dict, min_suporte: float, min_confianca: float,
                    min_lift: float, max_regras: int) -> tuple[dict, dict]:
    ocultos, priv = supressao_territorial(hists)
    recortes = {}
    for uf in ('BR', *UFS):
        n = n_near(hists[uf])
        motivo = ocultos.get(uf)
        # Jamais serializar regras/candidatos em recortes ocultos. O N_near
        # isolado é um denominador já disponibilizado pelo IND-031.
        if motivo:
            regras = []
            resumo = {'itemsets_frequentes': None, 'regras_que_atendem_limiares': None,
                      'regras_selecionadas': None, 'truncamento_por_max_regras': None}
        else:
            regras, resumo = extrair_regras(hists[uf], min_suporte,
                                            min_confianca, min_lift, max_regras)
            # Defesa adicional: nenhum suporte absoluto pequeno nas regras.
            if any(min(int(r[c]) for c in ('n_antecedente', 'n_consequente', 'n_ambos')) < MIN_N
                   for r in regras):
                raise ValueError(f'{uf}: regra com itemset abaixo de {MIN_N}.')
        recortes[uf] = {
            'uf': uf, 'populacao': 'POP_NEAR', 'intervalo_nota': [900, 980],
            'n_near': n, 'suprimido': bool(motivo),
            'motivo_supressao': motivo, 'resumo_apriori': resumo,
            'rules': regras, 'n_registros_individuais_exportados': 0,
            'status_publicacao': 'revisao_academica_e_privacidade_cruzada_pendente',
        }
    priv['regras_publicadas_neste_arquivo'] = sum(len(x['rules']) for x in recortes.values())
    return recortes, priv


def carregar_json(caminho: Path) -> dict:
    with caminho.open('r', encoding='utf-8-sig') as arq:
        dados = json.load(arq)
    if not isinstance(dados, dict):
        raise ValueError(f'{caminho}: JSON não contém objeto.')
    return dados


def comparar_ind031_032(saida: Path, ano: int, hist: dict) -> dict:
    """Cruza POP_NEAR com IND-031 e, se disponível, margens do IND-032."""
    caminho = saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
    if not caminho.exists():
        return {'ind031': 'nao_verificado_dashboard_ausente',
                'ind032': 'nao_verificado_dashboard_ausente'}
    painel = carregar_json(caminho)
    hp = painel.get('pages', {}).get('high_performance', {})
    if not isinstance(hp, dict):
        raise ValueError(f'{ano}: pages.high_performance não é um objeto.')
    estados = {v['uf']: v for v in hp.get('loss_by_competency', {}).get('by_uf', [])}
    ind031 = hp.get('loss_by_competency')
    ctrl31 = 'nao_disponivel'
    if isinstance(ind031, dict) and ind031.get('indicator_id') == 'IND-031':
        if int(ind031['brasil']['n_near']) != int(hist['BR'].sum()) or set(estados) != set(UFS):
            raise ValueError(f'{ano}: POP_NEAR diverge do IND-031.')
        for uf in UFS:
            if int(estados[uf]['n_near']) != int(hist[uf].sum()):
                raise ValueError(f'{ano}/{uf}: POP_NEAR diverge do IND-031.')
        ctrl31 = 'aprovado'
    ind032 = hp.get('discount_frequency')
    ctrl32 = 'nao_disponivel'
    if isinstance(ind032, dict) and ind032.get('indicator_id') == 'IND-032':
        blocos = {'BR': ind032['brasil']}
        blocos.update({v['uf']: v for v in ind032.get('by_uf', [])})
        if set(blocos) != {'BR', *UFS}:
            raise ValueError(f'{ano}: IND-032 incompleto (BR + UFs).')
        for uf, trecho in blocos.items():
            if int(trecho['n_near']) != int(hist[uf].sum()):
                raise ValueError(f'{ano}/{uf}: população difere do IND-032.')
            for item in trecho.get('resumo_competencias', []):
                cod = str(item.get('competencia'))
                if cod in COMPETENCIAS and item.get('n_com_desconto') is not None:
                    i = int(cod[1:]) - 1
                    margem = sum(int(hist[uf][mask]) for mask in range(32) if mask & (1 << i))
                    if int(item['n_com_desconto']) != margem:
                        raise ValueError(f'{ano}/{uf}/{cod}: margem difere do IND-032.')
        ctrl32 = 'aprovado'
    validas = painel.get('pages', {}).get('overview', {}).get('kpis', {}).get('valid_essays')
    if validas is not None and int(validas) < int(hist['BR'].sum()):
        raise ValueError(f'{ano}: POP_VALID dashboard menor que POP_NEAR.')
    return {'ind031': ctrl31, 'ind032': ctrl32}



def controle_ind035(saida: Path, ano: int, hists: dict) -> str:
    """Confere frequências conjuntas com IND-035 quando estiver no dashboard."""
    caminho = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
    if not caminho.exists():
        return 'dashboard_ausente'
    doc = carregar_json(caminho)
    hp = doc.get('pages', {}).get('high_performance', {})
    ind035 = hp.get('co_loss_patterns') if isinstance(hp, dict) else None
    if not isinstance(ind035, dict) or ind035.get('indicator_id') != 'IND-035':
        return 'nao_disponivel'
    recortes = {'BR': ind035['brasil']}
    recortes.update({item['uf']: item for item in ind035.get('by_uf', [])})
    if set(recortes) != {'BR', *UFS}:
        raise ValueError(f'{ano}: IND-035 não possui os 28 recortes geográficos.')
    n_conferidas = 0
    for uf, rec in recortes.items():
        if int(rec['n_near']) != n_near(hists[uf]):
            raise ValueError(f'{ano}/{uf}: POP_NEAR difere do IND-035.')
        for item in rec.get('combinacoes', []):
            if item.get('suprimido') or item.get('n_redacoes_com_desconto_conjunto') is None:
                continue
            keys = item.get('competencias', [])
            mascara = sum(1 << (int(c[1:]) - 1) for c in keys)
            if len(keys) not in (2, 3) or len(set(keys)) != len(keys):
                raise ValueError('IND-035: combinação inválida.')
            observado = conta_itemset(hists[uf], mascara)
            if observado != int(item['n_redacoes_com_desconto_conjunto']):
                raise ValueError(f'{ano}/{uf}/{keys}: divergência frente ao IND-035.')
            n_conferidas += 1
    return f'aprovado_{n_conferidas}_contagens'


def salvar_json_atomico(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix=caminho.name+'.', suffix='.tmp',
                                         delete=False) as arq:
            temporario = Path(arq.name)
            json.dump(dados, arq, ensure_ascii=False, allow_nan=False, indent=2)
            arq.write('\n')
        os.replace(temporario, caminho)
    finally:
        if temporario:
            temporario.unlink(missing_ok=True)


def salvar_csv_atomico(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as arq:
            temporario = Path(arq.name)
            w = csv.DictWriter(arq, fieldnames=CAMPOS_CSV,
                               delimiter=';', extrasaction='ignore')
            w.writeheader()
            w.writerows(linhas)
        os.replace(temporario, caminho)
    finally:
        if temporario:
            temporario.unlink(missing_ok=True)


def integrar_dashboards(saida: Path, processados: dict, parametros: dict) -> None:
    for chave, obj in sorted(processados.items(), key=lambda p: int(p[0])):
        if obj.get('status') != 'ok':
            continue
        ano = int(chave)
        caminho = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not caminho.exists():
            log(f'  Dashboard {ano} ausente; integração ignorada.')
            continue
        doc = carregar_json(caminho)
        hp = doc.get('pages', {}).get('high_performance')
        if not isinstance(hp, dict):
            raise ValueError(f'{caminho.name}: páginas high_performance ausentes.')
        hp['association_rules'] = {
            'indicator_id': 'IND-036', 'status': 'draft', 'year': ano,
            'population': 'POP_NEAR', 'algorithm': 'Apriori',
            'parameters': parametros, 'brasil': obj['recortes']['BR'],
            'by_uf': [obj['recortes'][uf] for uf in UFS],
            'publication_note': 'Revisão acadêmica e de privacidade cruzada obrigatórias.',
        }
        hp['status'] = 'partial'
        hp['reason'] = ('IND-036 integrado como draft; avaliação acadêmica e '
                        'privacidade cruzada pendentes.')
        doc.setdefault('quality', {})['ind036_validation'] = {
            'status': 'ok_agregados', 'n_near_brasil': obj['n_near_brasil'],
            'soma_27_ufs_igual_brasil': True,
            'pop_near_e_soma_competencias_validadas': True,
            'controles': obj['controles'],
            'privacidade': obj['privacidade'],
            'algoritmo': 'apriori_itemsets_frequentes_regras',
            'revisao_academica_e_privacidade_pendente': True,
        }
        aviso = ('IND-036: política revisada de divulgação de regras agregadas, sem supressão '
                 'integral por máscaras raras; análise não causal, revisão acadêmica/privacidade pendentes.')
        avisos = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json_atomico(caminho, doc)
        log(f'  Dashboard {ano} integrado (sem arquivos .bak).')


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             exigir_2025: bool, min_suporte: float,
             min_confianca: float, min_lift: float,
             max_regras: int, _teste: bool = False,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base = base.resolve()
    saida = saida.resolve()
    arq_json = saida/'outputs'/'json'/'IND_036_regras_associacao.json'
    arq_csv = saida/'outputs'/'indicadores'/'IND_036_regras_associacao.csv'
    if not sobrescrever and (arq_json.exists() or arq_csv.exists()):
        raise FileExistsError('IND-036 já existe: use --sobrescrever para atualizar.')
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
        raise FileNotFoundError('Fontes ausentes: '+', '.join(faltantes))
    anteriores = {}
    if sobrescrever and arq_json.exists():
        antigo = carregar_json(arq_json)
        if antigo.get('indicator_id') != 'IND-036':
            raise ValueError('JSON existente não corresponde ao IND-036.')
        anteriores = dict(antigo.get('years', {}))
        antigos_parametros = antigo.get('parameters', {})
        novos_parametros = {
            'min_suporte': min_suporte, 'min_confianca': min_confianca,
            'min_lift': min_lift, 'max_regras_por_recorte': max_regras,
            'min_contagem_itemset': MIN_N,
            'politica_divulgacao': POLITICA_DIVULGACAO,
        }
        if antigos_parametros != novos_parametros and any(
                int(y) not in anos for y in anteriores):
            raise ValueError('Parâmetros ou política de divulgação diferentes da execução anterior. '
                             'Reprocesse TODOS os anos já presentes no JSON com --sobrescrever '
                             'para não misturar resultados de políticas distintas. '
                             'Não é necessário apagar arquivos.')
    todos = dict(anteriores)
    processados = {}
    for ano in anos:
        log(f'IND-036 | {ano} — Apriori de descontos na POP_NEAR...')
        if ano == 2025 and 'RESULTADOS_2025.CSV' not in fontes:
            obj = {'ano': ano, 'status': 'indisponivel', 'recortes': {},
                   'reason': 'RESULTADOS_2025.csv ausente; regras não estimadas.'}
            todos[str(ano)] = processados[str(ano)] = obj
            log('  2025: indisponível, sem resultados artificiais.')
            continue
        if ano == 2024:
            hist, n_validas, diagnostico = ler_2024(
                fontes['PARTICIPANTES_2024.CSV'],
                fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            nome = f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023 else 'RESULTADOS_2025.CSV'
            hist, n_validas, diagnostico = ler_mesma_linha(fontes[nome], bloco)
            fonte = fontes[nome].name
        validar_histogramas_036(hist, ano, n_validas, not _teste)
        ctrl31_32 = comparar_ind031_032(saida, ano, hist) if not _teste else {
            'ind031': 'autoteste_sem_base_real', 'ind032': 'autoteste_sem_base_real'}
        ctrl35 = controle_ind035(saida, ano, hist) if not _teste else 'autoteste_sem_base_real'
        recortes, privacidade = montar_recortes(hist, min_suporte,
                                                min_confianca, min_lift, max_regras)
        if diagnostico.get('n_pop_near_vinculadas', n_near(hist['BR'])) != n_near(hist['BR']):
            raise ValueError('POP_NEAR vinculada diverge do total Brasil.')
        obj = {
            'ano': ano, 'status': 'ok', 'fonte': fonte,
            'population': 'POP_NEAR', 'n_validas_brasil': n_validas,
            'n_near_brasil': n_near(hist['BR']),
            'diagnostico_fonte': diagnostico,
            'controles': {**ctrl31_32, 'ind035': ctrl35},
            'privacidade': privacidade, 'recortes': recortes,
        }
        todos[str(ano)] = processados[str(ano)] = obj
        log(f'  POP_NEAR BR={obj["n_near_brasil"]:,}; regras liberadas='
            f'{privacidade["regras_publicadas_neste_arquivo"]:,}; '
            f'recortes ocultos={privacidade["recortes_suprimidos_primarios"] + privacidade["recortes_suprimidos_complementares"]}.')
    parametros = {
        'min_suporte': min_suporte, 'min_confianca': min_confianca,
        'min_lift': min_lift, 'max_regras_por_recorte': max_regras,
        'min_contagem_itemset': MIN_N,
        'politica_divulgacao': POLITICA_DIVULGACAO,
    }
    linhas = []
    for chave, obj in sorted(todos.items(), key=lambda p: int(p[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = obj['recortes'][uf]
            for regra in rec['rules']:
                linhas.append({
                    'ano': int(chave), 'uf': uf, 'n_near': rec['n_near'],
                    'antecedente': '+'.join(regra['antecedente']),
                    'consequente': '+'.join(regra['consequente']),
                    'itemset': '+'.join(regra['itemset']),
                    'n_antecedente': regra['n_antecedente'],
                    'n_consequente': regra['n_consequente'],
                    'n_ambos': regra['n_ambos'], 'suporte': regra['suporte'],
                    'suporte_percentual': regra['suporte_percentual'],
                    'confianca': regra['confianca'],
                    'confianca_percentual': regra['confianca_percentual'],
                    'lift': regra['lift'], 'leverage': regra['leverage'],
                    'status_publicacao': rec['status_publicacao'],
                })
    modulo = {
        'indicator_id': 'IND-036', 'titulo': 'Regras de associação de descontos',
        'status': 'draft', 'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(a) for a, obj in todos.items() if obj.get('status') == 'ok'),
        'population': 'POP_NEAR', 'geography': 'SG_UF_PROVA',
        'algorithm': 'Apriori', 'parameters': parametros,
        'methodology': {
            'selection': 'TP_STATUS_REDACAO=1, 900 <= nota final <= 980, C1..C5 completas, soma exata',
            'transaction': 'item Ci quando NU_NOTA_COMPi < 200',
            'itemset_support': 'n_itemset / n_near',
            'confidence': 'n(antecedente U consequente) / n(antecedente)',
            'lift': 'confidence / (n_consequente / n_near)',
            'leverage': 'support(antecedente U consequente) - support(antecedente)*support(consequente)',
            'multiple_consequents_allowed': True,
            '2024_join': 'NU_INSCRICAO via SQLite temporário',
            'privacy': ('Política revisada: não ocultar UF/BR por qualquer máscara exata rara; '
                        'exportar somente regras de itemsets frequentes com pelo menos 30 '
                        'ocorrências, ocultando recortes com POP_NEAR de 1 a 29'),
            'cautions': [
                'As regras são associações descritivas, não causais.',
                'A seleção POP_NEAR condiciona as associações e induz dependências estruturais.',
                'Lift e confiança não indicam erro de correção.',
                'A seleção de limiares e a escolha do top-N afetam o resultado.',
                'UF corresponde ao local de realização da prova, não à residência.',
                'Série temporal conta participações, não pessoas únicas.',
                'Sem 2025 com fonte real, não se calculam resultados para esse ano.',
                'A nova divulgação não publica histograma de máscaras exatas ou transações individuais.',
                'Não há garantia de impossibilidade de inferência por cruzamento entre recortes e indicadores.',
                'Revisão acadêmica, estabilidade e privacidade cruzada são necessárias antes de publicação.',
            ],
        },
        'years': todos,
    }
    salvar_json_atomico(arq_json, modulo)
    salvar_csv_atomico(arq_csv, linhas)
    log(f'JSON: {arq_json}\nCSV: {arq_csv}')
    if not somente_modulo:
        integrar_dashboards(saida, processados, parametros)
    log('IND-036 concluído (status: draft).')
    return modulo


def autoteste() -> None:
    """Valida Apriori, fórmulas, privacidade, leituras, junção e escrita."""
    from tempfile import TemporaryDirectory
    hist = np.zeros(32, dtype=np.int64)
    hist[1] = hist[3] = hist[7] = hist[31] = 100
    frequentes = apriori_frequentes(hist, 0.05)
    assert len(frequentes) == 31
    assert frequentes[3] == 300 and frequentes[7] == 200
    regras, detalhes = extrair_regras(hist, 0.05, 0.2, 1.0, 300)
    regra = next(r for r in regras if r['antecedente'] == ['C2'] and r['consequente'] == ['C3'])
    assert regra['n_antecedente'] == 300
    assert regra['n_consequente'] == 200
    assert regra['n_ambos'] == 200
    assert abs(regra['confianca'] - 2/3) < 1e-8
    assert abs(regra['lift'] - 4/3) < 1e-8
    assert detalhes['regras_que_atendem_limiares'] >= 1
    # Uma máscara exata rara NÃO deve ocultar recorte com N_near suficiente.
    hist_raro = hist.copy()
    hist_raro[7] = 1
    geo = {u: np.zeros(32, dtype=np.int64) for u in ('BR', *UFS)}
    for uf in UFS:
        geo[uf] = hist.copy()
    geo['SP'] = hist_raro.copy()
    geo['BR'] = sum((geo[u] for u in UFS), start=np.zeros(32, dtype=np.int64))
    escondidos, _ = supressao_territorial(geo)
    assert not escondidos, 'Máscara rara não deve ocultar automaticamente o estado.'
    rec, priv = montar_recortes(geo, 0.05, 0.2, 1.0, 30)
    assert not rec['SP']['suprimido'] and rec['SP']['rules']
    assert rec['BR']['rules'] and not rec['BR']['suprimido']
    assert priv['bloqueio_integral_por_mascara_exata_rara'] is False
    for r in rec['SP']['rules']:
        assert min(r['n_antecedente'], r['n_consequente'], r['n_ambos']) >= 30
    # Uma UF com POP_NEAR <30 continua ocultada, com complemento geográfico.
    geo_peq = {u: hist.copy() for u in ('BR', *UFS)}
    geo_peq['SP'] = np.zeros(32, dtype=np.int64)
    geo_peq['SP'][1] = 5
    geo_peq['BR'] = sum((geo_peq[u] for u in UFS), start=np.zeros(32, dtype=np.int64))
    escondidos_peq, _ = supressao_territorial(geo_peq)
    assert escondidos_peq['SP'] == 'primaria_pop_near_pequena'
    assert len(escondidos_peq) == 2 and 'BR' not in escondidos_peq
    rec_peq, _ = montar_recortes(geo_peq, 0.05, 0.2, 1.0, 30)
    assert rec_peq['SP']['suprimido'] and not rec_peq['SP']['rules']
    assert rec_peq['BR']['rules']
    # Fonte com soma de competências e nota reais, incluindo uma redação 1000
    # que não pertence à POP_NEAR.
    dados = pd.DataFrame({
        'TP_STATUS_REDACAO': ['1'] * 5,
        'NU_NOTA_REDACAO': ['980', '960', '940', '900', '1000'],
        'SG_UF_PROVA': ['SP', 'SP', 'RJ', 'RJ', 'SP'],
        'NU_NOTA_COMP1': ['180', '180', '180', '180', '200'],
        'NU_NOTA_COMP2': ['200', '180', '180', '180', '200'],
        'NU_NOTA_COMP3': ['200', '200', '180', '180', '200'],
        'NU_NOTA_COMP4': ['200', '200', '200', '180', '200'],
        'NU_NOTA_COMP5': ['200', '200', '200', '180', '200'],
    })
    near, validas = selecionar_near(dados)
    assert validas == 5 and gerar_mascaras(near).tolist() == [1, 3, 7, 31]
    # Autoteste 2024 SQLite e integração sintética (fora do repositório).
    with TemporaryDirectory(prefix='teste_ind036_') as pasta:
        raiz = Path(pasta)
        (raiz/'bases').mkdir()
        (raiz/'outputs'/'json').mkdir(parents=True)
        em2019 = pd.concat([dados.iloc[:4]] * 30, ignore_index=True)
        em2019.to_csv(raiz/'bases'/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        h19, val19, _ = ler_mesma_linha(raiz/'bases'/'MICRODADOS_ENEM_2019.csv', 17)
        assert val19 == 120 and n_near(h19['BR']) == 120
        comp = pd.concat([dados.iloc[:4]] * 30, ignore_index=True)
        inscricoes = [str(9000 + i) for i in range(len(comp))]
        p24 = comp[['SG_UF_PROVA']].copy()
        p24.insert(0, 'NU_INSCRICAO', inscricoes)
        c24 = comp.drop(columns='SG_UF_PROVA').copy()
        c24.insert(0, 'NU_INSCRICAO', inscricoes)
        p24.to_csv(raiz/'bases'/'PARTICIPANTES_2024.csv', sep=';', index=False)
        c24.to_csv(raiz/'bases'/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        h24, val24, diag24 = ler_2024(raiz/'bases'/'PARTICIPANTES_2024.csv',
                                     raiz/'bases'/'COMPETENCIAS_REDACAO_2024.csv', 17)
        assert n_near(h24['BR']) == 120 and val24 == 120
        assert diag24['n_pop_near_vinculadas'] == 120
        painel = {
            'pages': {'high_performance': {'outro_indicador': {'preservar': True}}},
            'quality': {'outro_controle': {'preservar': True}},
            'meta': {'warnings': []},
        }
        caminho24 = raiz/'outputs'/'json'/'dashboard_enem_2024.json'
        salvar_json_atomico(caminho24, painel)
        gerado = executar(raiz, raiz, (2024,), 17, False, False, False,
                          0.05, 0.30, 1.00, 10, _teste=True)
        assert gerado['years']['2024']['n_near_brasil'] == 120
        depois = carregar_json(caminho24)
        hp = depois['pages']['high_performance']
        assert hp['association_rules']['indicator_id'] == 'IND-036'
        assert hp['outro_indicador']['preservar']
        assert depois['quality']['outro_controle']['preservar']
        assert not list((raiz/'outputs').rglob('*.bak*'))
        assert (raiz/'outputs'/'indicadores'/'IND_036_regras_associacao.csv').exists()
        assert (raiz/'outputs'/'json'/'IND_036_regras_associacao.json').exists()
        # JSON e CSV coerentes mesmo se regras forem ocultas em UFs pequenas.
        esperadas = sum(len(r['rules']) for r in gerado['years']['2024']['recortes'].values())
        with (raiz/'outputs'/'indicadores'/'IND_036_regras_associacao.csv').open(
                encoding='utf-8-sig', newline='') as arq:
            assert len(list(csv.DictReader(arq, delimiter=';'))) == esperadas
    log('Autoteste IND-036: Apriori, suporte/confiança/lift, fontes 2019/2024, '
        'divulgação agregada revisada, integração e CSV/JSON aprovados.')


def main() -> None:
    p = argparse.ArgumentParser(description='IND-036 — Regras de associação (Apriori)')
    p.add_argument('--base', type=Path, default=raiz_projeto())
    p.add_argument('--saida', type=Path, default=raiz_projeto())
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    p.add_argument('--bloco', type=int, default=100_000,
                   help='Registros lidos por bloco, para limitar uso de memória.')
    p.add_argument('--min-suporte', type=float, default=SUPORTE_PADRAO)
    p.add_argument('--min-confianca', type=float, default=CONFIANCA_PADRAO)
    p.add_argument('--min-lift', type=float, default=LIFT_PADRAO)
    p.add_argument('--max-regras', type=int, default=MAX_REGRAS_PADRAO)
    p.add_argument('--sobrescrever', action='store_true')
    p.add_argument('--somente-modulo', action='store_true',
                   help='Não alterar dashboards; gerar somente CSV e JSON do indicador.')
    p.add_argument('--exigir-2025', action='store_true',
                   help='Exigir RESULTADOS_2025.csv em vez de marcar indisponível.')
    p.add_argument('--autoteste', action='store_true',
                   help='Testar sem microdados reais.')
    p.add_argument('--competencias-2024', type=Path, default=None,
                   help='Selecionar CSV de competências de 2024 quando houver versões diferentes.')
    p.add_argument('--participantes-2024', type=Path, default=None,
                   help='Selecionar CSV de participantes de 2024 quando houver versões diferentes.')
    args = p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(a not in ANOS for a in anos):
        p.error('Informe anos entre 2019 e 2025.')
    if args.bloco <= 0 or args.max_regras < 1:
        p.error('--bloco e --max-regras devem ser positivos.')
    import math
    if (not 0 < args.min_suporte <= 1 or
            not 0 <= args.min_confianca <= 1 or
            not math.isfinite(args.min_lift) or args.min_lift < 0):
        p.error('Limiares: 0 < suporte <= 1; 0 <= confiança <= 1; lift >= 0 finito.')
    escolhas: dict[str, Path] = {}
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.exigir_2025,
                 args.min_suporte, args.min_confianca, args.min_lift,
                 args.max_regras, fontes_explicitas=escolhas)
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        print(f'ERRO IND-036: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
