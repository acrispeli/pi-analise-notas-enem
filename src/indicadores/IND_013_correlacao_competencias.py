#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-013 — Correlação de Spearman C1–C5; Pearson (sensibilidade).

Catálogo mestre: Competências / Correlação entre competências / P0;
variáveis NU_NOTA_COMP1..5, população POP_VALID; heatmap; JSON path
pages.competencies.correlation.

Analisa microdados completos por blocos, sem amostragem e sem guardar dados
individuais. Empates em Spearman são tratados por POSTOS MÉDIOS (rankdata
method='average'); o histórico 2019–2025 é calculado da DISTRIBUIÇÃO
CONJUNTA de todos os anos, nunca da média de coeficientes anuais.

A redação de SC/2023 com C3=10 e soma de competências 30 pontos menor do
que a nota total permanece incluída sem alterações; a divergência é
reconciliada com IND-009/011/012. Casos com competências ausentes ou fora
0–200 interrompem a execução. Não exporta tabelas de frequência conjunta,
pois poderiam expor células pequenas; mantém data_status='draft' por causa
das revisões acadêmicas e de privacidade dos indicadores anteriores.

Pré-requisito: IND-012 concluído, com os sete dashboards atualizados.
Executar a partir da raiz do repositório:
 .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_013_correlacao_competencias.py

Saídas:
 outputs/indicadores/IND_013_correlacao_competencias.csv (2.240 pares)
 outputs/json/IND_013_correlacao_competencias.json
 outputs/json/dashboard_enem_2019.json ... dashboard_enem_2025.json
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple(sorted('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split()))
COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
LABELS = tuple(f'C{i}' for i in range(1, 6))
PARES = tuple((i, j) for i in range(5) for j in range(i + 1, 5))
COLUNAS = ('SG_UF_PROVA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COMP)
INDICADOR = 'IND-013'
VERSAO = '2.12.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010-ind011-ind012-ind013'
METODO = 'spearman_postos_medios_empates_e_pearson_pop_valid'
DEFINICAO = ('Correlação entre as notas numéricas observadas das competências C1–C5, '
            'para redações válidas (TP_STATUS_REDACAO=1 e NU_NOTA_REDACAO entre 0 e 1000). '
            'Spearman calculado pelos postos médios em empates; Pearson como sensibilidade.')
HISTORICO = ('O consolidado 2019–2025 soma as frequências CONJUNTAS observadas de cada par '
             'de competências nos sete anos e recalcula Spearman e Pearson sobre a distribuição '
             'conjunta. Não faz médias de coeficientes. São participações, não pessoas únicas; '
             'SG_UF_PROVA indica o local da prova, não a residência.')
PRIVACIDADE = ('Este indicador só exporta coeficientes de grupos com pelo menos 30 redações. '
               'Não publica contagens por combinação de notas. Mantêm-se as pendências de '
               'supressão primária e complementar dos indicadores anteriores.')
BLOCO = 100_000
LIMIAR = 30


def fonte(ano: int, raiz: Path) -> Path:
    nome = f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023 else f'RESULTADOS_{ano}.csv'
    return raiz / 'data' / 'raw' / str(ano) / nome


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f'Pré-requisito ausente: {caminho}')
    with caminho.open(encoding='utf-8') as fp:
        return json.load(fp)


def mapa_ufs(doc: dict) -> dict[str, dict]:
    itens = doc.get('ufs', [])
    if len(itens) != 27 or {x.get('uf') for x in itens} != set(UFS):
        raise ValueError('Referência sem as 27 UFs distintas')
    return {x['uf']: x for x in itens}


def carregar_referencias(raiz: Path) -> tuple[dict, dict]:
    pasta = raiz / 'outputs' / 'json'
    nomes = {1: 'redacoes_validas', 2: 'nota_media', 9: 'media_competencias',
             10: 'mediana_competencias', 11: 'dispersao_competencias',
             12: 'distribuicao_niveis_competencias'}
    refs: dict[int, dict] = {}
    for num, nome in nomes.items():
        p = pasta / f'IND_{num:03d}_{nome}.json'
        d = ler_json(p)
        if d.get('indicator', {}).get('id') != f'IND-{num:03d}':
            raise ValueError(f'{p.name}: ID de indicador divergente')
        if sorted(x.get('ano') for x in d.get('years', [])) != list(ANOS):
            raise ValueError(f'{p.name}: anos ausentes ou duplicados')
        for grupo in [*d['years'], d['historical']]:
            mapa_ufs(grupo)
        refs[num] = d
    for ano in ANOS:
        for num in (9, 11, 12):
            r = next(x for x in refs[num]['years'] if x['ano'] == ano)
            if 'n_somas_divergentes' not in r['brasil']:
                raise ValueError(f'{ano}: IND-{num:03d} não contém rastreio de divergências')
    dashboards = {}
    for ano in ANOS:
        d = ler_json(pasta / f'dashboard_enem_{ano}.json')
        if d.get('meta', {}).get('year') != ano or d['meta'].get('data_status') != 'draft':
            raise ValueError(f'Dashboard {ano}: ano ou status incompatível')
        c = d.get('pages', {}).get('competencies', {})
        if c.get('status') != 'ok' or any(k not in c for k in
                                        ('summary', 'dispersion', 'level_distribution',
                                         'ind009', 'ind010')):
            raise ValueError(f'Dashboard {ano}: aguarde a conclusão do IND-012')
        if len(c['summary']) != 5 or len(c['level_distribution']['national_summary']) != 5:
            raise ValueError(f'Dashboard {ano}: indicadores C1–C5 incompletos')
        if not all(d.get('quality', {}).get(f'ind{n:03d}_validation', {}).get('status') == 'ok'
                   for n in (9, 10, 11, 12)):
            raise ValueError(f'Dashboard {ano}: controles de qualidade anteriores ausentes')
        dashboards[ano] = d
    return refs, dashboards


def marginais_de_pares(conjuntos: list[Counter], n: int) -> list[Counter]:
    if len(conjuntos) != len(PARES):
        raise ValueError('São necessários exatamente 10 pares de competência')
    saida = [Counter() for _ in LABELS]
    for k, (i, j) in enumerate(PARES):
        joint = conjuntos[k]
        if sum(joint.values()) != n:
            raise ValueError(f'Par C{i+1}/C{j+1}: soma das frequências != n ({n})')
        ma, mb = Counter(), Counter()
        for (a, b), count in joint.items():
            if not 0 <= a <= 200 or not 0 <= b <= 200 or count < 1:
                raise ValueError(f'Par C{i+1}/C{j+1}: nota ou frequência inválida')
            ma[a] += count
            mb[b] += count
        for comp, freq in ((i, ma), (j, mb)):
            if saida[comp] and saida[comp] != freq:
                raise ValueError(f'C{comp+1}: marginais inconsistentes entre pares')
            saida[comp] = freq
    if any(sum(x.values()) != n for x in saida):
        raise ValueError('Uma ou mais competências sem o total esperado')
    return saida


def correlacao_ponderada(conjunto: Counter, n: int) -> tuple[float | None, float | None]:
    """Calcula Spearman (midranks) e Pearson exatos da distribuição conjunta.

    Entradas são (pontuacao_i, pontuacao_j):frequência; sem expansionar a amostra.
    Valores constantes produzem null (correlação indefinida), nunca zero.
    """
    if n < 1 or sum(conjunto.values()) != n:
        raise ValueError('Frequência conjunta vazia ou incompatível')
    fa: Counter = Counter()
    fb: Counter = Counter()
    for (a, b), qtd in conjunto.items():
        if qtd <= 0 or not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('Frequência conjunta contém valor inválido')
        fa[a] += qtd
        fb[b] += qtd
    media_a = math.fsum(v * c for v, c in fa.items()) / n
    media_b = math.fsum(v * c for v, c in fb.items()) / n
    va = math.fsum(c * (v - media_a) ** 2 for v, c in fa.items())
    vb = math.fsum(c * (v - media_b) ** 2 for v, c in fb.items())
    cov = math.fsum(c * (a - media_a) * (b - media_b) for (a, b), c in conjunto.items())
    pearson = cov / math.sqrt(va * vb) if va > 1e-20 and vb > 1e-20 else None

    def postos_medios(freq: Counter) -> dict[float, float]:
        acumulado = 0
        postos = {}
        for valor, count in sorted(freq.items()):
            # Empates ocupam as posições acumulado+1 ... acumulado+count.
            postos[valor] = acumulado + (count + 1) / 2
            acumulado += count
        if acumulado != n:
            raise ValueError('Total de postos incongruente')
        return postos

    pa, pb = postos_medios(fa), postos_medios(fb)
    centro = (n + 1) / 2
    vra = math.fsum(c * (pa[x] - centro) ** 2 for x, c in fa.items())
    vrb = math.fsum(c * (pb[y] - centro) ** 2 for y, c in fb.items())
    cr = math.fsum(c * (pa[x] - centro) * (pb[y] - centro)
                   for (x, y), c in conjunto.items())
    spearman = cr / math.sqrt(vra * vrb) if vra > 1e-20 and vrb > 1e-20 else None
    for metodo, valor in (('Pearson', pearson), ('Spearman', spearman)):
        if valor is not None and (not math.isfinite(valor) or abs(valor) > 1 + 1e-10):
            raise ValueError(f'{metodo} fora de [-1,+1]: {valor}')
    return (max(-1.0, min(1.0, spearman)) if spearman is not None else None,
            max(-1.0, min(1.0, pearson)) if pearson is not None else None)


def normalizar(v: float | None) -> float | None:
    if v is None:
        return None
    x = round(float(v), 6)
    return 0.0 if x == 0 else x


def resultado_grupo(n: int, conjuntos: list[Counter], total_registros: int | None = None,
                    divergentes: int = 0, delta: float = 0.0) -> dict:
    if n < LIMIAR:
        raise ValueError(f'POP_VALID inferior ao limiar de {LIMIAR}: {n}')
    marginais = marginais_de_pares(conjuntos, n)
    spearman = [[None] * 5 for _ in range(5)]
    pearson = [[None] * 5 for _ in range(5)]
    for i in range(5):
        # Variância constante produz correlação consigo mesma indefinida.
        variancia = len(marginais[i]) > 1
        spearman[i][i] = 1.0 if variancia else None
        pearson[i][i] = 1.0 if variancia else None
    pares = []
    for k, (i, j) in enumerate(PARES):
        s, p = correlacao_ponderada(conjuntos[k], n)
        sr, pr = normalizar(s), normalizar(p)
        spearman[i][j] = spearman[j][i] = sr
        pearson[i][j] = pearson[j][i] = pr
        pares.append({'competencia_a': LABELS[i], 'competencia_b': LABELS[j],
                      'n': n, 'spearman': sr, 'pearson': pr,
                      'diferenca_spearman_menos_pearson': normalizar(s - p) if s is not None and p is not None else None})
    r = {'n_validas': n, 'labels': list(LABELS), 'spearman': spearman,
         'pearson': pearson, 'pares': pares, 'pares_com_correlacao_indefinida':
         sum(x['spearman'] is None or x['pearson'] is None for x in pares),
         'n_somas_divergentes': int(divergentes),
         'delta_soma_competencias_menos_nota_redacao': round(float(delta), 6)}
    if total_registros is not None:
        r['total_registros'] = int(total_registros)
    return r


def processar_ano(ano: int, raiz: Path, bloco: int = BLOCO) -> dict:
    caminho = fonte(ano, raiz)
    if not caminho.is_file():
        raise FileNotFoundError(f'Fonte ausente: {caminho}')
    qa = Counter()
    todos_uf: Counter = Counter({uf: 0 for uf in UFS})
    n_uf: Counter = Counter({uf: 0 for uf in UFS})
    div_uf: Counter = Counter({uf: 0 for uf in UFS})
    delta_uf: Counter = Counter({uf: 0.0 for uf in UFS})
    joint_uf = {uf: [Counter() for _ in PARES] for uf in UFS}
    for parte in pd.read_csv(caminho, sep=';', usecols=list(COLUNAS), dtype=str,
                             keep_default_na=False, na_filter=False,
                             encoding='utf-8-sig', encoding_errors='replace',
                             chunksize=bloco, on_bad_lines='error'):
        uf = parte['SG_UF_PROVA'].str.strip().str.upper()
        status = parte['TP_STATUS_REDACAO'].str.strip()
        nt = parte['NU_NOTA_REDACAO'].str.strip()
        nota = pd.to_numeric(nt.str.replace(',', '.', regex=False), errors='coerce')
        st1 = status.eq('1')
        nota_ok = nota.notna() & nota.between(0, 1000)
        validas = st1 & nota_ok
        qa['registros'] += len(parte)
        qa['status1'] += int(st1.sum())
        qa['validas'] += int(validas.sum())
        qa['status1_sem_nota'] += int((st1 & nt.eq('')).sum())
        qa['status1_nota_invalida'] += int((st1 & nt.ne('') & ~nota_ok).sum())
        qa['validas_sem_uf'] += int((validas & uf.eq('')).sum())
        qa['validas_uf_desconhecida'] += int((validas & ~uf.isin(UFS) & uf.ne('')).sum())
        todos_uf.update({str(k): int(v) for k, v in uf.value_counts().items()})
        if not bool(validas.any()):
            continue
        crus = parte.loc[validas, list(COMP)].apply(lambda s: s.str.strip())
        valores = crus.apply(lambda s: pd.to_numeric(s.str.replace(',', '.', regex=False), errors='coerce'))
        completos = valores.notna() & valores.ge(0) & valores.le(200)
        for i, c in enumerate(COMP, 1):
            qa[f'c{i}_ausente'] += int(crus[c].eq('').sum())
            qa[f'c{i}_invalida'] += int((crus[c].ne('') & ~completos[c]).sum())
        linha_ok = completos.all(axis=1)
        qa['validas_competencias_incompletas'] += int((~linha_ok).sum())
        if not bool(linha_ok.any()):
            continue
        notas = valores.loc[linha_ok]
        ufs_validas = uf.loc[validas].loc[linha_ok]
        diferenca = notas.sum(axis=1) - nota.loc[validas].loc[linha_ok]
        divergencias = diferenca.abs() > 1e-6
        qa['validas_soma_competencias_divergente'] += int(divergencias.sum())
        n_uf.update({str(k): int(v) for k, v in ufs_validas.value_counts().items()})
        div_uf.update({str(k): int(v) for k, v in ufs_validas[divergencias].value_counts().items()})
        if bool(divergencias.any()):
            for sigla, val in diferenca.loc[divergencias].groupby(ufs_validas[divergencias]).sum().items():
                delta_uf[str(sigla)] += float(val)
        temp = notas.copy()
        temp['uf'] = ufs_validas
        # Frequências conjuntas em 10 pares. Os pares de notas permanecem
        # somente em memória e nunca são exportados para arquivo ou dashboard.
        for k, (i, j) in enumerate(PARES):
            for (sigla, a, b), qty in temp.groupby(['uf', COMP[i], COMP[j]], sort=False).size().items():
                joint_uf[str(sigla)][k][(float(a), float(b))] += int(qty)
    if qa['registros'] <= 0:
        raise ValueError(f'{ano}: arquivo vazio')
    if qa['status1'] != qa['validas'] + qa['status1_sem_nota'] + qa['status1_nota_invalida']:
        raise ValueError(f'{ano}: contagem TP_STATUS_REDACAO=1 não conciliada')
    inconsistencias = []
    for k in ('status1_sem_nota', 'status1_nota_invalida', 'validas_sem_uf',
              'validas_uf_desconhecida', 'validas_competencias_incompletas'):
        if qa[k]:
            inconsistencias.append(f'{k}={qa[k]}')
    for i in range(1, 6):
        for suffix in ('ausente', 'invalida'):
            if qa[f'c{i}_{suffix}']:
                inconsistencias.append(f'c{i}_{suffix}={qa[f"c{i}_{suffix}"]}')
    if inconsistencias:
        raise ValueError(f'{ano}: integridade inválida: {", ".join(inconsistencias)}')
    if sum(todos_uf.values()) != qa['registros'] or sum(todos_uf[u] for u in UFS) != qa['registros']:
        raise ValueError(f'{ano}: POP_ALL não corresponde à soma das UFs')
    if sum(n_uf[u] for u in UFS) != qa['validas']:
        raise ValueError(f'{ano}: POP_VALID não corresponde à soma das UFs')
    if sum(div_uf.values()) != qa['validas_soma_competencias_divergente']:
        raise ValueError(f'{ano}: divergências C1–C5 não reconciliadas por UF')
    estados, joint_br = [], [Counter() for _ in PARES]
    for uf_sigla in UFS:
        estados.append({'uf': uf_sigla,
                        **resultado_grupo(n_uf[uf_sigla], joint_uf[uf_sigla],
                                         todos_uf[uf_sigla], div_uf[uf_sigla], delta_uf[uf_sigla])})
        for k in range(len(PARES)):
            joint_br[k].update(joint_uf[uf_sigla][k])
    br = resultado_grupo(qa['validas'], joint_br, qa['registros'],
                         sum(div_uf.values()), sum(delta_uf.values()))
    return {'ano': ano, 'arquivo_fonte': caminho.name, 'brasil': br, 'ufs': estados,
            'qualidade': {'status': 'ok',
                          'status1_sem_nota': qa['status1_sem_nota'],
                          'status1_nota_invalida': qa['status1_nota_invalida'],
                          'validas_sem_uf': qa['validas_sem_uf'],
                          'validas_uf_desconhecida': qa['validas_uf_desconhecida'],
                          'validas_competencias_incompletas': qa['validas_competencias_incompletas'],
                          'validas_soma_competencias_divergente': qa['validas_soma_competencias_divergente'],
                          'delta_soma_competencias_menos_nota_redacao':
                          br['delta_soma_competencias_menos_nota_redacao'],
                          'situacao_soma_competencias':
                          'divergencias_na_fonte' if qa['validas_soma_competencias_divergente'] else 'ok',
                          'soma_27_ufs_igual_brasil': True, 'sem_amostragem': True,
                          'posto_spearman_empates': 'average', 'pearson_sensibilidade': True,
                          'frequencias_conjuntas_nao_publicadas': True,
                          'pares_indefinidos_brasil': br['pares_com_correlacao_indefinida'],
                          'metodo': METODO},
            '_joint_uf': joint_uf, '_joint_br': joint_br}


def validar_grupo(g: dict, conjuntos: list[Counter], refs: dict[int, dict], contexto: str,
                   historico: bool = False) -> None:
    n = g['n_validas']
    for k in (1, 2, 9, 10, 11, 12):
        esperado = refs[k].get('redacoes_validas') if k == 1 else refs[k].get('n_validas')
        if n != esperado:
            raise ValueError(f'{contexto}: N={n} difere do IND-{k:03d}: {esperado}')
        if not historico and g['total_registros'] != refs[k]['total_registros']:
            raise ValueError(f'{contexto}: total_registros difere do IND-{k:03d}')
    for k in (9, 11, 12):
        if g['n_somas_divergentes'] != refs[k]['n_somas_divergentes']:
            raise ValueError(f'{contexto}: exceção de origem difere de IND-{k:03d}')
        if abs(g['delta_soma_competencias_menos_nota_redacao'] -
               float(refs[k]['delta_soma_competencias_menos_nota_redacao'])) > 0.0001:
            raise ValueError(f'{contexto}: delta de origem difere de IND-{k:03d}')
    marginais = marginais_de_pares(conjuntos, n)
    for i, label in enumerate(LABELS):
        r12 = refs[12]['competencias'][i]
        r9 = refs[9]['competencias'][i]
        r11 = refs[11]['competencias'][i]
        if (r12.get('competencia') != label or r9.get('competencia') != label
                or r11.get('competencia') != label):
            raise ValueError(f'{contexto}: competências não estão na ordem C1–C5')
        f12 = Counter({float(x['pontuacao']): int(x['quantidade']) for x in r12['niveis']})
        if marginais[i] != f12:
            raise ValueError(f'{contexto}/{label}: marginais incompatíveis com IND-012')
        media = math.fsum(val * count for val, count in marginais[i].items()) / n
        variancia = math.fsum(count * (val - media)**2 for val, count in marginais[i].items()) / n
        if abs(round(media, 4) - float(r9['media'])) > 0.000051:
            raise ValueError(f'{contexto}/{label}: média diverge de IND-009')
        if abs(round(math.sqrt(variancia), 4) - float(r11['desvio_padrao'])) > 0.000051:
            raise ValueError(f'{contexto}/{label}: desvio diverge de IND-011')
    if g['labels'] != list(LABELS) or len(g['pares']) != 10:
        raise ValueError(f'{contexto}: matriz incompleta')
    for metodo in ('spearman', 'pearson'):
        matriz = g[metodo]
        if len(matriz) != 5 or any(len(linha) != 5 for linha in matriz):
            raise ValueError(f'{contexto}: matriz {metodo} não é 5x5')
        for i in range(5):
            for j in range(5):
                if matriz[i][j] != matriz[j][i]:
                    raise ValueError(f'{contexto}: matriz {metodo} não é simétrica')
                v = matriz[i][j]
                if v is not None and (not -1 <= v <= 1 or not math.isfinite(v)):
                    raise ValueError(f'{contexto}: coeficiente {metodo} fora do intervalo')


def validar_referencias(dados: list[dict], refs: dict) -> None:
    idx = {num: {x['ano']: x for x in d['years']} for num, d in refs.items()}
    for d in dados:
        ano = d['ano']
        ano_ref = {k: v[ano] for k, v in idx.items()}
        validar_grupo(d['brasil'], d['_joint_br'], {k: v['brasil'] for k, v in ano_ref.items()},
                       f'{ano}/BR')
        uf_ref = {k: mapa_ufs(v) for k, v in ano_ref.items()}
        for u in d['ufs']:
            sigla = u['uf']
            validar_grupo(u, d['_joint_uf'][sigla],
                           {k: v[sigla] for k, v in uf_ref.items()}, f'{ano}/{sigla}')
        for k in (9, 10, 11, 12):
            if (d['qualidade']['validas_soma_competencias_divergente'] !=
                    ano_ref[k]['qualidade']['validas_soma_competencias_divergente']):
                raise ValueError(f'{ano}: exceção de origem diverge de IND-{k:03d}')
        d['qualidade']['validado_contra_ind001_ind002_ind009_ind010_ind011_ind012'] = True


def consolidar_historico(dados: list[dict], refs: dict) -> dict:
    juntos = {uf: [Counter() for _ in PARES] for uf in UFS}
    for d in dados:
        for uf in UFS:
            for k in range(len(PARES)):
                juntos[uf][k].update(d['_joint_uf'][uf][k])
    estados = []
    nacional = [Counter() for _ in PARES]
    for uf in UFS:
        ed = [next(x for x in d['ufs'] if x['uf'] == uf) for d in dados]
        estados.append({'uf': uf,
                        **resultado_grupo(sum(x['n_validas'] for x in ed), juntos[uf],
                                         sum(x['total_registros'] for x in ed),
                                         sum(x['n_somas_divergentes'] for x in ed),
                                         sum(x['delta_soma_competencias_menos_nota_redacao'] for x in ed))})
        for k in range(len(PARES)):
            nacional[k].update(juntos[uf][k])
    b = [d['brasil'] for d in dados]
    br = resultado_grupo(sum(x['n_validas'] for x in b), nacional,
                         sum(x['total_registros'] for x in b),
                         sum(x['n_somas_divergentes'] for x in b),
                         sum(x['delta_soma_competencias_menos_nota_redacao'] for x in b))
    hist = {'periodo': '2019-2025', 'brasil': br, 'ufs': estados,
            'qualidade': {'status': 'ok', 'historico_distribuicao_conjunta': True,
                          'soma_27_ufs_igual_brasil': True,
                          'sem_media_de_correlacoes_anuais': True,
                          'pares_indefinidos_brasil': br['pares_com_correlacao_indefinida'],
                          'metodo': METODO}}
    refs_hist = {k: v['historical'] for k, v in refs.items()}
    validar_grupo(br, nacional, {k: v['brasil'] for k, v in refs_hist.items()}, 'HIST/BR', True)
    por_uf = {k: mapa_ufs(v) for k, v in refs_hist.items()}
    for u in estados:
        sigla = u['uf']
        validar_grupo(u, juntos[sigla], {k: v[sigla] for k, v in por_uf.items()}, f'HIST/{sigla}', True)
    return hist


def linhas_csv(dados: list[dict], historico: dict) -> list[dict]:
    linhas = []
    for d in [*dados, historico]:
        historico_ = 'periodo' in d
        period = d['periodo'] if historico_ else str(d['ano'])
        fontes = '2019-2025' if historico_ else d['arquivo_fonte']
        for abrangencia, uf, g in [('BR', 'BR', d['brasil']),
                                   *[('UF', u['uf'], u) for u in d['ufs']]]:
            for par in g['pares']:
                linhas.append({'indicador_id': INDICADOR, 'periodo': period,
                               'abrangencia': abrangencia, 'uf': uf,
                               'competencia_a': par['competencia_a'],
                               'competencia_b': par['competencia_b'],
                               'n_validas': g['n_validas'], 'spearman': par['spearman'],
                               'pearson': par['pearson'],
                               'diferenca_spearman_menos_pearson':
                               par['diferenca_spearman_menos_pearson'],
                               'populacao': 'POP_VALID', 'metodo': METODO,
                               'arquivo_fonte': fontes})
    if len(linhas) != 8 * 28 * 10:
        raise ValueError(f'CSV: esperadas 2.240 linhas; obtidas {len(linhas)}')
    return linhas


def item_dashboard(g: dict, incluir_pares: bool = False) -> dict:
    item = {'n': g['n_validas'], 'spearman': g['spearman'], 'pearson': g['pearson']}
    if incluir_pares:
        item['pairs'] = g['pares']
    return item


def construir_dashboard(d: dict, dados: list[dict], hist: dict, base: dict, gerado: str) -> dict:
    ano = d['ano']
    dash = deepcopy(base)
    p = dash['pages']['competencies']
    br = d['brasil']
    if dash['pages']['overview']['kpis']['valid_essays'] != br['n_validas']:
        raise ValueError(f'Dashboard {ano}: população não corresponde ao IND-001')
    if p['level_distribution']['n'] != br['n_validas']:
        raise ValueError(f'Dashboard {ano}: população não corresponde ao IND-012')
    if {x['uf']: x['n'] for x in p['level_distribution']['by_uf']} != \
            {x['uf']: x['n_validas'] for x in d['ufs']}:
        raise ValueError(f'Dashboard {ano}: UFs não correspondem ao IND-012')
    for i, c in enumerate(p['summary']):
        if c['competency'] != LABELS[i] or c['n'] != br['n_validas']:
            raise ValueError(f'Dashboard {ano}: resumo C1–C5 desordenado')
    p['correlation'] = {'indicator_id': INDICADOR, 'population': 'POP_VALID',
                        'geographic_dimension': 'SG_UF_PROVA', 'method': METODO,
                        'labels': list(LABELS), 'n': br['n_validas'],
                        'spearman': br['spearman'], 'pearson': br['pearson'],
                        'pairs': br['pares'],
                        'by_uf': [{'uf': x['uf'], **item_dashboard(x)} for x in d['ufs']],
                        'sensitivity': 'Pearson calculado para os mesmos pares e população',
                        'privacy_note': PRIVACIDADE}
    dash['pages']['temporal']['ind013'] = {
        'indicator_id': INDICADOR, 'population': 'POP_VALID', 'method': METODO,
        'labels': list(LABELS),
        'national_by_year': [{'year': x['ano'], **item_dashboard(x['brasil'], True)} for x in dados],
        'period_total': item_dashboard(hist['brasil'], True),
        'period_by_uf': [{'uf': x['uf'], **item_dashboard(x)} for x in hist['ufs']],
        'historical_note': HISTORICO}
    dash['pages']['methodology']['ind013'] = {
        'definition': DEFINICAO, 'population': 'POP_VALID',
        'source_file': d['arquivo_fonte'], 'geographic_dimension': 'SG_UF_PROVA',
        'method': METODO, 'main_metric': 'Spearman (Pearson aplicado aos postos médios em empates)',
        'sensitivity_metric': 'Pearson aplicado às pontuações originais',
        'pairs': 10, 'matrix_dimension': '5x5', 'rounding': 'seis casas decimais',
        'constant_scores': 'coeficiente indefinido: null, jamais 0',
        'integrity': ('Competências de 0 a 200; divergência de soma versus nota '
                      'total é preservada, rastreada e não imputada.'),
        'historical_note': HISTORICO, 'privacy_note': PRIVACIDADE}
    dash['quality']['ind013_validation'] = deepcopy(d['qualidade'])
    dash['meta']['analysis_version'] = VERSAO
    dash['meta']['generated_at'] = gerado
    dash['meta']['data_status'] = 'draft'
    avisos = dash['meta'].setdefault('warnings', [])
    msg = 'IND-013: Spearman com postos médios e Pearson de sensibilidade verificados; revisão acadêmica ainda pendente.'
    if msg not in avisos:
        avisos.append(msg)
    if br['n_somas_divergentes']:
        msg = (f"IND-013/{ano}: {br['n_somas_divergentes']} registro(s) com soma C1–C5 "
               'divergente da nota total, preservado(s) sem imputação ou exclusão.')
        if msg not in avisos:
            avisos.append(msg)
    return dash


def validar_dashboard(d: dict, raiz: Path) -> str:
    if not {'meta', 'filters', 'quality', 'pages'}.issubset(d):
        raise ValueError('Dashboard sem campos essenciais')
    if 'NU_INSCRICAO' in json.dumps(d, ensure_ascii=False):
        raise ValueError('Identificador individual proibido no dashboard')
    possiveis = (raiz / 'docs' / '04_resultados_analises.schema.json',
                 raiz / 'docs' / 'metodologia' / '04_resultados_analises.schema.json',
                 raiz / '04_resultados_analises.schema.json')
    p = next((x for x in possiveis if x.is_file()), None)
    if p is None:
        return 'estrutura essencial (schema não localizado)'
    try:
        import jsonschema
    except ImportError as ex:
        raise ImportError('jsonschema é obrigatório para validar o contrato') from ex
    jsonschema.validate(d, ler_json(p))
    return 'JSON Schema v1.0.0'


def salvar_json(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as fp:
        json.dump(doc, fp, ensure_ascii=False, indent=2, allow_nan=False)
        fp.write('\n')
    tmp.replace(p)


def salvar_csv(p: Path, linhas: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0]), delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)
    tmp.replace(p)


def executar(raiz: Path, bloco: int = BLOCO) -> None:
    refs, dashboards = carregar_referencias(raiz)
    dados = []
    for ano in ANOS:
        print(f'IND-013 | {ano}: processando {fonte(ano, raiz).name} ...', flush=True)
        d = processar_ano(ano, raiz, bloco)
        dados.append(d)
        r = d['brasil']['pares'][0]
        print(f"  válidas={d['brasil']['n_validas']:,} | C1×C2: Spearman={r['spearman']}, "
              f"Pearson={r['pearson']}", flush=True)
        if d['qualidade']['validas_soma_competencias_divergente']:
            print(f"  AVISO FONTE: {d['qualidade']['validas_soma_competencias_divergente']} "
                  'soma(s) de competências divergente(s), preservadas', flush=True)
    validar_referencias(dados, refs)
    hist = consolidar_historico(dados, refs)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    novos = {d['ano']: construir_dashboard(d, dados, hist, dashboards[d['ano']], gerado)
             for d in dados}
    contratos = {validar_dashboard(x, raiz) for x in novos.values()}
    for d in dados:
        d.pop('_joint_uf')
        d.pop('_joint_br')
    output = {
        'meta': {'indicator_id': INDICADOR, 'module_schema_version': 'ind013-module-1.0.0',
                 'analysis_version': VERSAO, 'dataset_version': 'enem-2019-2025-csv-publico',
                 'generated_at': gerado, 'data_status': 'draft',
                 'source_files': {str(d['ano']): d['arquivo_fonte'] for d in dados},
                 'population_definition': DEFINICAO, 'geographic_dimension': 'SG_UF_PROVA',
                 'method': METODO, 'historical_note': HISTORICO,
                 'privacy_note': PRIVACIDADE,
                 'comparison_ind001_ind002_ind009_ind010_ind011_ind012': 'aprovada',
                 'source_discrepancies': {
                     str(d['ano']): {'count': d['brasil']['n_somas_divergentes'],
                                     'delta_total': d['brasil']['delta_soma_competencias_menos_nota_redacao']}
                     for d in dados}},
        'indicator': {'id': INDICADOR, 'name': 'Correlação entre competências',
                      'unit': 'coeficiente', 'dashboard_json_path': 'pages.competencies.correlation'},
        'years': dados, 'historical': hist,
        'dashboard_files': [f'dashboard_enem_{ano}.json' for ano in ANOS]}
    linhas = linhas_csv(dados, hist)
    json.dumps(output, ensure_ascii=False, allow_nan=False)
    pasta = raiz / 'outputs'
    salvar_csv(pasta / 'indicadores' / 'IND_013_correlacao_competencias.csv', linhas)
    salvar_json(pasta / 'json' / 'IND_013_correlacao_competencias.json', output)
    for ano in ANOS:
        salvar_json(pasta / 'json' / f'dashboard_enem_{ano}.json', novos[ano])
    print('\nIND-013 concluído:')
    print(f'  IND_013_correlacao_competencias.csv ({len(linhas):,} linhas)')
    print('  IND_013_correlacao_competencias.json')
    print('  dashboard_enem_2019.json ... dashboard_enem_2025.json atualizados')
    print('  Contrato: ' + ', '.join(sorted(contratos)))
    print('  data_status=draft | pendentes revisões acadêmica e de privacidade')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-013 — Spearman C1–C5; Pearson sensibilidade')
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--bloco', type=int, default=BLOCO)
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error('--bloco deve ser positivo')
    executar(args.raiz.resolve(), args.bloco)


if __name__ == '__main__':
    main()
