#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-035 — Combinações de perdas (pares e trios) | ENEM 2019–2025.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores ENEM v2.

POP_NEAR: TP_STATUS_REDACAO=1, nota final válida no intervalo fechado
[900, 980] e cinco notas de competências entre 0 e 200.

Para cada conjunto S de DUAS ou TRÊS competências, conta as redações nas
quais TODAS as competências de S receberam menos de 200 pontos.

INTERSEÇÃO INCLUSIVA: outras competências também podem ter desconto.
Ex.: uma redação com perdas em C1, C2 e C3 participa das interseções
C1+C2, C1+C3, C2+C3 e C1+C2+C3. Os percentuais não somam 100%.

É necessário ler microdados: a frequência conjunta NÃO é derivável das
margens do IND-032, nem das médias/somas do IND-031.

Fontes:
  2019–2023: MICRODADOS_ENEM_<ano>.csv, na mesma linha.
  2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv; junção
        por NU_INSCRICAO via SQLite temporário (sem dados pessoais exportados).
  2025: RESULTADOS_2025.csv, caso disponível, com status, nota, C1–C5, UF.

Saídas:
  outputs/json/IND_035_combinacoes_perdas.json
  outputs/indicadores/IND_035_combinacoes_perdas.csv
  outputs/json/dashboard_enem_<ano>.json
     pages.high_performance.co_loss_patterns
     quality.ind035_validation

Privacidade: suprime todos os 20 conjuntos de um recorte geográfico se
alguma de suas contagens ou complemento estiver em 1..29; enquanto o
nacional permanecer publicável, também suprime um segundo estado para
impedir recuperação direta por subtração BR - soma(UFs). Revisão de
privacidade cruzada com IND-031/032/034 ainda é obrigatória.

Não cria backups .bak; utiliza escrita atômica. Resultados status=draft.

Exemplos (na raiz do projeto):
  python src/indicadores/IND_035_combinacoes_perdas.py --autoteste
  python src/indicadores/IND_035_combinacoes_perdas.py --anos 2024 --sobrescrever
  python src/indicadores/IND_035_combinacoes_perdas.py --sobrescrever
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
MIN_N = 30
POP_NEAR_REFERENCIA = {
    2019: 172_548, 2020: 183_343, 2021: 163_747,
    2022: 197_083, 2023: 288_602, 2024: 291_111,
    2025: 173_533,
}
# 10 pares + 10 trios. Chave é composta pelos bits C1..C5, sem ordenação
# dependente dos dados (os mesmos 20 conjuntos em todos os anos/UFs).
CONJUNTOS = tuple(
    (tuple(COMPETENCIAS[i] for i in indices), sum(1 << i for i in indices))
    for tam in (2, 3) for indices in combinations(range(5), tam)
)
CAMPOS_CSV = (
    'ano', 'uf', 'n_near', 'tipo', 'combinacao', 'competencias',
    'n_redacoes_com_desconto_conjunto', 'percentual_pop_near',
    'suprimido', 'motivo_supressao',
)


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


def contagem_conjunto(histograma: np.ndarray, mascara: int) -> int:
    return int(sum(int(histograma[x]) for x in range(32) if (x & mascara) == mascara))


def validar_histogramas(hist: dict, ano: int, n_validas: int,
                         controlar_pop: bool) -> None:
    for uf in ('BR', *UFS):
        hist.setdefault(uf, novo_histograma())
        if int(hist[uf][0]) != 0:
            raise ValueError(f'{ano}/{uf}: máscara sem descontos indevida em POP_NEAR.')
        n = int(hist[uf].sum())
        if hist[uf].shape != (32,) or (hist[uf] < 0).any():
            raise ValueError(f'{ano}/{uf}: histograma inválido.')
        if 0 < n < MIN_N:
            raise ValueError(f'{ano}/{uf}: recorte POP_NEAR com N pequeno; '
                             'somente consolidar geografia após revisão de privacidade.')
        # Inclusões obrigatórias: trio <= cada um de seus pares, par <= margens.
        for codigos, mask in CONJUNTOS:
            intersecao = contagem_conjunto(hist[uf], mask)
            if not 0 <= intersecao <= n:
                raise ValueError(f'{ano}/{uf}: contagem conjunta inválida.')
            if len(codigos) == 3:
                for par in combinations(codigos, 2):
                    parmask = sum(1 << (int(c[1:]) - 1) for c in par)
                    if intersecao > contagem_conjunto(hist[uf], parmask):
                        raise ValueError(f'{ano}/{uf}: trio maior que par associado.')
    if int(hist['BR'].sum()) > n_validas:
        raise ValueError(f'{ano}: POP_NEAR maior que total de redações válidas.')
    if not np.array_equal(hist['BR'], sum((hist[uf] for uf in UFS), start=novo_histograma())):
        raise ValueError(f'{ano}: máscaras das 27 UFs não fecham com Brasil.')
    if controlar_pop and int(hist['BR'].sum()) != POP_NEAR_REFERENCIA[ano]:
        raise ValueError(f'{ano}: POP_NEAR={int(hist["BR"].sum()):,} '
                         f'difere de IND-031 ({POP_NEAR_REFERENCIA[ano]:,}).')


def calcular_privacidade(hist: dict) -> tuple[dict[str, str], dict]:
    """Proteção conservadora por geografia, incluindo complemento e BR×UF.

    Oculta TODOS os pares/trios de uma UF quando qualquer interseção ou seu
    complemento tiver N=1..29. Se o nacional for publicado e existir alguma
    UF oculta, oculta também uma segunda UF (a de maior POP_NEAR entre as
    elegíveis), de modo que subtração BR - UFs não revele diretamente o
    resultado de uma única UF. Não substitui a revisão de privacidade cruzada.
    """
    suprimir: dict[str, str] = {}
    for uf in ('BR', *UFS):
        n = int(hist[uf].sum())
        if n == 0:
            continue
        for _, mascara in CONJUNTOS:
            v = contagem_conjunto(hist[uf], mascara)
            if 0 < v < MIN_N or 0 < n - v < MIN_N:
                suprimir[uf] = 'primaria_intersecao_ou_complemento_n_1_a_29'
                break
    if 'BR' not in suprimir:
        ausentes = [uf for uf in UFS if uf in suprimir]
        if len(ausentes) == 1:
            candidatos = [uf for uf in UFS if uf not in suprimir
                          and int(hist[uf].sum()) >= MIN_N]
            if candidatos:
                segundo = max(candidatos, key=lambda uf: (int(hist[uf].sum()), uf))
                suprimir[segundo] = 'complementar_geografica'
            else:
                suprimir['BR'] = 'complementar_brasil'
    return suprimir, {
        'limiar_n': MIN_N,
        'estrategia': 'supressao_integral_do_recorte_e_complementar_geografica',
        'recortes_primarios_suprimidos': sum(x.startswith('primaria') for x in suprimir.values()),
        'recortes_complementares_suprimidos': sum(x.startswith('complementar') for x in suprimir.values()),
        'celulas_suprimidas': len(suprimir) * len(CONJUNTOS),
        'revisao_academica_e_privacidade_cruzada_pendente': True,
    }


def montar_recortes(hist: dict, suprimir: dict[str, str]) -> dict:
    resultado = {}
    for uf in ('BR', *UFS):
        n = int(hist[uf].sum())
        motivo = suprimir.get(uf)
        linhas = []
        for comps, mask in CONJUNTOS:
            valor = contagem_conjunto(hist[uf], mask)
            linhas.append({
                'tipo': 'par' if len(comps) == 2 else 'trio',
                'combinacao': '+'.join(comps),
                'competencias': list(comps),
                'n_redacoes_com_desconto_conjunto': None if motivo else valor,
                'percentual_pop_near': (None if motivo or n == 0 else round(100 * valor / n, 6)),
                'suprimido': bool(motivo),
                'motivo_supressao': motivo,
            })
        resultado[uf] = {
            'uf': uf, 'populacao': 'POP_NEAR', 'intervalo_nota': [900, 980],
            'n_near': n, 'tipo_intersecao': 'inclusiva',
            'combinacoes': linhas,
            'sem_dados_individuais': True,
            'status_publicacao': 'revisao_academica_e_privacidade_cruzada_pendente',
        }
    return resultado


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


def salvar_json_atomico(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix=caminho.name+'.', suffix='.tmp',
                                         delete=False) as f:
            tmp = Path(f.name)
            json.dump(dados, f, ensure_ascii=False, allow_nan=False, indent=2)
            f.write('\n')
        os.replace(tmp, caminho)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def salvar_csv_atomico(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as f:
            tmp = Path(f.name)
            escritor = csv.DictWriter(f, delimiter=';', fieldnames=CAMPOS_CSV,
                                      extrasaction='ignore')
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(tmp, caminho)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def atualizar_dashboards(saida: Path, alterados: dict[str, dict]) -> None:
    for chave, obj in sorted(alterados.items(), key=lambda t: int(t[0])):
        if obj.get('status') != 'ok':
            continue
        ano = int(chave)
        caminho = saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.exists():
            log(f'  Dashboard {ano} não encontrado; integração ignorada.')
            continue
        d = carregar_json(caminho)
        hp = d.get('pages', {}).get('high_performance')
        if not isinstance(hp, dict):
            raise ValueError(f'{caminho.name}: falta pages.high_performance.')
        hp['co_loss_patterns'] = {
            'indicator_id': 'IND-035',
            'population': 'POP_NEAR',
            'method': 'itemsets inclusivos; COUNT(all Ci<200, Ci em par/trio), nota final [900,980]',
            'year': ano,
            'status': 'draft',
            'brasil': obj['recortes']['BR'],
            'by_uf': [obj['recortes'][uf] for uf in UFS],
            'privacy_note': ('Supressão de grupos pequenos e de complementos por recorte; '
                             'revisão de privacidade cruzada ainda obrigatória.'),
        }
        hp['status'] = 'partial'
        hp['reason'] = 'IND-035 integrado (draft); demais indicadores e revisão acadêmica/privacidade pendentes.'
        qualidade = d.setdefault('quality', {})
        qualidade['ind035_validation'] = {
            'status': 'ok_agregados',
            'n_near_brasil': obj['n_near_brasil'],
            'soma_27_ufs_igual_brasil': True,
            'vinte_itemsets_pares_trios': True,
            'intersecoes_inclusivas': True,
            'soma_competencias_confere_com_nota': True,
            'controle': obj['controles'],
            **obj['privacidade'],
        }
        avisos = d.setdefault('meta', {}).setdefault('warnings', [])
        aviso = ('IND-035: coocorrência inclusiva de descontos entre pares/trios C1–C5; '
                 'revisão acadêmica e avaliação de privacidade cruzada pendentes.')
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json_atomico(caminho, d)
        log(f'  Dashboard {ano} integrado sem criar .bak.')


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             sem_controle_populacao: bool, exigir_2025: bool,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    destino_json = saida/'outputs'/'json'/'IND_035_combinacoes_perdas.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_035_combinacoes_perdas.csv'
    if (destino_json.exists() or destino_csv.exists()) and not sobrescrever:
        raise FileExistsError('IND-035 já existe; use --sobrescrever para atualizar.')
    nomes: set[str] = set()
    for ano in anos:
        if ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
        else:
            nomes.add('RESULTADOS_2025.CSV')
    fontes = localizar_fontes(base, nomes, fontes_explicitas)
    sem_fonte = sorted(nomes - set(fontes) - (set() if exigir_2025 else {'RESULTADOS_2025.CSV'}))
    if sem_fonte:
        raise FileNotFoundError('Fontes não encontradas: '+', '.join(sem_fonte)+'. Verifique --base.')
    anos_antigos: dict[str, dict] = {}
    if sobrescrever and destino_json.exists():
        antigo = carregar_json(destino_json)
        if antigo.get('indicator_id') != 'IND-035':
            raise ValueError('Arquivo JSON existente não pertence ao IND-035.')
        anos_antigos = dict(antigo.get('years', {}))
    dados_anos = dict(anos_antigos)
    processados: dict[str, dict] = {}
    for ano in anos:
        log(f'IND-035 | {ano}: contando pares/trios de descontos...')
        if ano == 2025 and 'RESULTADOS_2025.CSV' not in fontes:
            obj = {'ano': ano, 'status': 'indisponivel',
                   'reason': 'RESULTADOS_2025.csv ausente; combinações não podem ser estimadas.',
                   'recortes': {}}
            dados_anos[str(ano)] = processados[str(ano)] = obj
            log('  2025: indisponível, sem gerar estimativas.')
            continue
        if ano == 2024:
            hist, n_validas, diag = ler_2024(fontes['PARTICIPANTES_2024.CSV'],
                                             fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            nome = f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023 else 'RESULTADOS_2025.CSV'
            hist, n_validas, diag = ler_mesma_linha(fontes[nome], bloco)
            fonte = fontes[nome].name
        validar_histogramas(hist, ano, n_validas, not sem_controle_populacao)
        ctrl = comparar_ind031_032(saida, ano, hist)
        suprimir, privacidade = calcular_privacidade(hist)
        recortes = montar_recortes(hist, suprimir)
        if diag.get('n_pop_near_vinculadas', int(hist['BR'].sum())) != int(hist['BR'].sum()):
            raise ValueError(f'{ano}: contagem vinculada de 2024 difere de POP_NEAR.')
        obj = {
            'ano': ano, 'status': 'ok', 'fonte': fonte,
            'population': 'POP_NEAR', 'n_validas_brasil': n_validas,
            'n_near_brasil': int(hist['BR'].sum()),
            'diagnostico_fonte': diag, 'controles': ctrl,
            'privacidade': privacidade, 'recortes': recortes,
        }
        dados_anos[str(ano)] = processados[str(ano)] = obj
        log(f'  N_near BR={obj["n_near_brasil"]:,}; '
            f'itemsets mascarados={privacidade["celulas_suprimidas"]}; '
            f'IND-031={ctrl["ind031"]}; IND-032={ctrl["ind032"]}.')
    linhas = []
    for y, obj in sorted(dados_anos.items(), key=lambda x: int(x[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = obj['recortes'][uf]
            for item in rec['combinacoes']:
                linhas.append({
                    'ano': int(y), 'uf': uf, 'n_near': rec['n_near'],
                    'tipo': item['tipo'], 'combinacao': item['combinacao'],
                    'competencias': '|'.join(item['competencias']),
                    'n_redacoes_com_desconto_conjunto': item['n_redacoes_com_desconto_conjunto'],
                    'percentual_pop_near': item['percentual_pop_near'],
                    'suprimido': item['suprimido'],
                    'motivo_supressao': item['motivo_supressao'],
                })
    modulo = {
        'indicator_id': 'IND-035',
        'titulo': 'Combinações de perdas por competência',
        'status': 'draft', 'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(y) for y, v in dados_anos.items() if v.get('status') == 'ok'),
        'population': 'POP_NEAR', 'geography': 'SG_UF_PROVA',
        'methodology': {
            'selection': 'TP_STATUS_REDACAO=1, nota válida entre 900 e 980 inclusive',
            'rule': 'para cada par/trio S, COUNT(redações em que todas as Ci de S são < 200)',
            'itemsets': '10 pares e 10 trios, contagem inclusiva (outras competências podem ter desconto)',
            'denominator': 'n_near do mesmo ano e UF da prova',
            'not_mutually_exclusive': True,
            'not_derived_from_ind032': True,
            'microdata_2024_join': 'NU_INSCRICAO, SQLite temporário',
            'privacy': 'supressão integral de recortes com célula ou complemento pequeno, mais geográfica',
            'no_backup': True,
            'cautions': [
                'Percentuais dos 20 conjuntos NÃO somam 100%, pois conjuntos se sobrepõem.',
                'Coocorrência não implica causalidade nem prova erro de correção.',
                'Um conjunto com C1+C2 não exclui desconto em C3, C4 ou C5.',
                'UF corresponde ao local da prova, não necessariamente à residência.',
                '2025 depende da existência de RESULTADOS_2025.csv com todas as variáveis.',
                'Histórico conta participações, não pessoas únicas; não exportamos total histórico.',
                'Revisão acadêmica e de privacidade cruzada é obrigatória antes de publicação.',
            ],
        },
        'years': dados_anos,
    }
    salvar_json_atomico(destino_json, modulo)
    salvar_csv_atomico(destino_csv, linhas)
    log(f'JSON: {destino_json}\nCSV: {destino_csv}')
    if not somente_modulo:
        atualizar_dashboards(saida, processados)
    log('IND-035 finalizado (status: draft).')
    return modulo


def autoteste() -> None:
    import tempfile as _tempfile
    assert len(CONJUNTOS) == 20
    df = pd.DataFrame({
        'TP_STATUS_REDACAO': ['1']*5 + ['0'],
        'NU_NOTA_REDACAO': ['980', '960', '940', '900', '1000', '920'],
        'SG_UF_PROVA': ['SP', 'SP', 'RJ', 'RJ', 'SP', 'SP'],
        'NU_NOTA_COMP1': ['180', '180', '180', '180', '200', '200'],
        'NU_NOTA_COMP2': ['200', '180', '180', '180', '200', '200'],
        'NU_NOTA_COMP3': ['200', '200', '180', '180', '200', '200'],
        'NU_NOTA_COMP4': ['200', '200', '200', '180', '200', '200'],
        'NU_NOTA_COMP5': ['200', '200', '200', '180', '200', '200'],
    })
    # Quarta linha: cinco descontos de 180 = 900; quinta 1000 fora de POP_NEAR.
    near, nvalidas = selecionar_near(df)
    assert nvalidas == 5 and len(near) == 4
    assert gerar_mascaras(near).tolist() == [1, 3, 7, 31]
    c = defaultdict(novo_histograma)
    acumular_near(c, near)
    assert int(c['BR'].sum()) == 4
    assert contagem_conjunto(c['BR'], 3) == 3   # C1+C2: máscaras 3, 7, 31
    assert contagem_conjunto(c['BR'], 7) == 2   # C1+C2+C3: 7 e 31
    assert contagem_conjunto(c['SP'], 3) == 1
    assert contagem_conjunto(c['RJ'], 7) == 2
    # Divergência entre total e competências deve impedir resultado enganoso.
    ruim = near.copy()
    ruim.loc[ruim.index[0], 'NU_NOTA_COMP1'] = '160'
    try:
        gerar_mascaras(ruim)
        raise AssertionError('Deveria recusar soma de competências divergente.')
    except ValueError as exc:
        assert 'soma C1..C5' in str(exc)
    # Histograma público com N>=30 e um conjunto de 1..29 força supressão.
    grande = defaultdict(novo_histograma)
    for uf in UFS:
        h = np.zeros(32, dtype=np.int64)
        h[1] = 39
        h[3] = 40
        h[7] = 1 if uf == 'SP' else 40
        adicionar_histograma(grande, uf, h)
    validar_histogramas(grande, 2024, int(grande['BR'].sum()), False)
    ocultar, qa = calcular_privacidade(grande)
    assert 'SP' in ocultar and len(ocultar) >= 2
    assert 'BR' not in ocultar
    pub = montar_recortes(grande, ocultar)
    assert all(x['n_redacoes_com_desconto_conjunto'] is None for x in pub['SP']['combinacoes'])
    assert all(x['n_redacoes_com_desconto_conjunto'] is not None for x in pub['BR']['combinacoes'])
    assert qa['celulas_suprimidas'] >= 40
    # Testa leitura das fontes, junção SQLite, saída JSON/CSV e integração isolada.
    with _tempfile.TemporaryDirectory(prefix='teste_ind035_') as tmp:
        raiz = Path(tmp)
        ffontes = raiz/'bases'
        ffontes.mkdir()
        # Ensaio por leitura na mesma linha, usando a amostra sintética.
        df.to_csv(ffontes/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        h19, valid19, diag19 = ler_mesma_linha(ffontes/'MICRODADOS_ENEM_2019.csv', 2)
        assert int(h19['BR'].sum()) == 4 and valid19 == 5 and diag19['metodo'] == 'mesma_linha'
        # Ensaio de 2024: UF e notas propositalmente em arquivos diferentes.
        partic = df[['SG_UF_PROVA']].copy()
        partic.insert(0, 'NU_INSCRICAO', [str(100+i) for i in range(len(df))])
        comp = df.drop(columns='SG_UF_PROVA').copy()
        comp.insert(0, 'NU_INSCRICAO', [str(100+i) for i in range(len(df))])
        partic.to_csv(ffontes/'PARTICIPANTES_2024.csv', sep=';', index=False)
        comp.to_csv(ffontes/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        h24, valid24, diag24 = ler_2024(ffontes/'PARTICIPANTES_2024.csv',
                                         ffontes/'COMPETENCIAS_REDACAO_2024.csv', 2)
        assert valid24 == 5 and int(h24['BR'].sum()) == 4
        assert diag24['n_pop_near_vinculadas'] == 4
        # Testa publicação com 30+ registros por UF para respeitar limiar.
        massivo = pd.concat([df.iloc[:4]]*16, ignore_index=True)
        massivo.to_csv(ffontes/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        saida = raiz/'destino'
        mod = executar(raiz, saida, (2019,), 12, False, True, True, False)
        assert mod['years']['2019']['n_near_brasil'] == 64
        arq = saida/'outputs'/'json'/'IND_035_combinacoes_perdas.json'
        assert arq.exists()
        assert len(list(csv.DictReader((saida/'outputs'/'indicadores'/'IND_035_combinacoes_perdas.csv').open(encoding='utf-8-sig'),delimiter=';'))) == 28*20
        # Integração completa 2024; testa também controles IND-031/032 existentes.
        amostra24 = massivo.copy()
        ids24 = [str(9000+i) for i in range(len(amostra24))]
        participantes24 = amostra24[['SG_UF_PROVA']].copy()
        participantes24.insert(0, 'NU_INSCRICAO', ids24)
        competencias24 = amostra24.drop(columns='SG_UF_PROVA').copy()
        competencias24.insert(0, 'NU_INSCRICAO', ids24)
        participantes24.to_csv(ffontes/'PARTICIPANTES_2024.csv', sep=';', index=False)
        competencias24.to_csv(ffontes/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)
        hist24, nval24, _ = ler_2024(ffontes/'PARTICIPANTES_2024.csv',
                                     ffontes/'COMPETENCIAS_REDACAO_2024.csv', 15)
        def bloco_controle(uf):
            h = hist24.get(uf, novo_histograma())
            return {'uf': uf, 'n_near': int(h.sum()),
                    'resumo_competencias': [
                        {'competencia': cod, 'n_com_desconto': int(sum(
                            h[x] for x in range(32) if (x & (1 << i))))}
                        for i, cod in enumerate(COMPETENCIAS)]}
        hp = {'loss_by_competency': {'indicator_id': 'IND-031',
                                    'brasil': bloco_controle('BR'),
                                    'by_uf': [bloco_controle(uf) for uf in UFS]},
              'discount_frequency': {'indicator_id': 'IND-032',
                                     'brasil': bloco_controle('BR'),
                                     'by_uf': [bloco_controle(uf) for uf in UFS]},
              'indicador_preservado': {'conteudo': 'nao_alterar'}}
        painel = {'pages': {'high_performance': hp,
                            'overview': {'kpis': {'valid_essays': nval24}}},
                  'quality': {'outro_indicador': 'preservado'},
                  'meta': {'warnings': []}}
        dashboard24 = saida/'outputs'/'json'/'dashboard_enem_2024.json'
        salvar_json_atomico(dashboard24, painel)
        mod24 = executar(raiz, saida, (2024,), 15, True, False, True, False)
        assert mod24['years']['2019']['n_near_brasil'] == 64
        assert mod24['years']['2024']['n_near_brasil'] == 64
        assert mod24['years']['2024']['controles'] == {'ind031': 'aprovado', 'ind032': 'aprovado'}
        resultado_dashboard = carregar_json(dashboard24)
        assert resultado_dashboard['pages']['high_performance']['co_loss_patterns']['indicator_id'] == 'IND-035'
        assert resultado_dashboard['pages']['high_performance']['indicador_preservado']['conteudo'] == 'nao_alterar'
        assert resultado_dashboard['quality']['outro_indicador'] == 'preservado'
        assert not list((saida/'outputs'/'json').glob('*.bak*'))
    log('Autoteste IND-035: classificação, interseções, junção, privacidade, controles e integração aprovados.')


def main() -> None:
    p = argparse.ArgumentParser(description='IND-035 — Combinações de perdas por competência')
    p.add_argument('--base', type=Path, default=raiz_projeto(),
                   help='Diretório raiz onde procurar os microdados.')
    p.add_argument('--saida', type=Path, default=raiz_projeto(),
                   help='Raiz de escrita de outputs/json e outputs/indicadores.')
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    p.add_argument('--bloco', type=int, default=100_000)
    p.add_argument('--sobrescrever', action='store_true')
    p.add_argument('--somente-modulo', action='store_true',
                   help='Gerar CSV/JSON sem integrar dashboards existentes.')
    p.add_argument('--sem-controle-populacao', action='store_true',
                   help='Apenas testes sintéticos; não usar para publicação.')
    p.add_argument('--exigir-2025', action='store_true',
                   help='Falhar se o arquivo RESULTADOS_2025.csv não for localizado.')
    p.add_argument('--autoteste', action='store_true',
                   help='Executar teste interno, sem precisar dos microdados.')
    p.add_argument('--competencias-2024', type=Path, default=None,
                   help='Selecionar CSV de competências de 2024 quando houver versões diferentes.')
    p.add_argument('--participantes-2024', type=Path, default=None,
                   help='Selecionar CSV de participantes de 2024 quando houver versões diferentes.')
    args = p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(ano not in ANOS for ano in anos):
        p.error('--anos deve conter anos entre 2019 e 2025.')
    if args.bloco <= 0:
        p.error('--bloco precisa ser maior que zero.')
    escolhas: dict[str, Path] = {}
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.sem_controle_populacao, args.exigir_2025,
                 fontes_explicitas=escolhas)
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as e:
        print(f'ERRO IND-035: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
