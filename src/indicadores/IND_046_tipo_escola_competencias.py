#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-046 — Tipo de escola/ trajetória escolar × competências C1–C5.

Projeto Integrador IV — UNIVESP | Catálogo ENEM 2019–2025 v2.

Saída: médias, medianas, quartis (HF7), IQR, DP populacional e N por
categoria × competência × UF/BR × ano; pages.socioeconomic.school_type_competencies.
População: POP_SOCIO_VALID, idêntica à do IND-045, conferida por categoria.

2019–2023: MICRODADOS_ENEM_<ano>.csv; TP_ESCOLA e notas na mesma linha.
2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv; junção
      exclusivamente por NU_INSCRICAO com unicidade e correspondência obrigatórias.
2025: indisponível para associação escola × competência (sem chave comum pública).

CRÍTICO: TP_ESCOLA e Q023 têm significados e categorias diferentes.
          Suprimir EXATAMENTE as categorias que o IND-045 suprime, inclusive
          a categoria complementar. Não utilizar valores suprimidos para inferência.
          Resultados 'draft': revisão cruzada de privacidade ainda necessária.

Pré-requisitos: src/indicadores/IND_045_tipo_escola_nota.py e
                outputs/json/IND_045_tipo_escola_nota.json (real).

Execução na raiz do projeto:
  python src/indicadores/IND_046_tipo_escola_competencias.py --autoteste
  python src/indicadores/IND_046_tipo_escola_competencias.py --anos 2024 --sobrescrever
  python src/indicadores/IND_046_tipo_escola_competencias.py --sobrescrever

Saídas:
  outputs/json/IND_046_tipo_escola_competencias.json
  outputs/indicadores/IND_046_tipo_escola_competencias.csv
  outputs/json/dashboard_enem_<ano>.json (bloco school_type_competencies)

Dependências: numpy, pandas, biblioteca padrão, módulo IND-045 da mesma pasta.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
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
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
LIMIAR = ind45.LIMIAR
CAMPOS_CSV = (
    'ano', 'uf', 'variavel_origem', 'conceito', 'codigo_escola',
    'descricao_categoria', 'ordem', 'competencia', 'n_redacoes', 'media',
    'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'percentual_total_validas', 'suprimido', 'motivo_supressao',
)


def log(texto: str) -> None:
    print(texto, flush=True)


class Grupo:
    """Histogramas exatos por competência, sem guardar redações individuais."""

    def __init__(self) -> None:
        self.n = 0
        self.hist = [Counter() for _ in range(5)]
        self.soma_total = 0.0
        self.n_soma_divergente = 0

    def adicionar(self, notas: np.ndarray, totais: np.ndarray) -> None:
        if notas.ndim != 2 or notas.shape[1] != 5 or len(notas) != len(totais):
            raise ValueError('Matriz de C1–C5 e notas finais desalinhadas.')
        self.n += len(notas)
        if not len(notas):
            return
        for j in range(5):
            valores, freq = np.unique(notas[:, j], return_counts=True)
            self.hist[j].update({float(v): int(n) for v, n in zip(valores, freq)})
        self.soma_total += float(math.fsum(totais.tolist()))
        desvios = notas.sum(axis=1) - totais
        self.n_soma_divergente += int(np.count_nonzero(
            ~np.isclose(desvios, 0, atol=1e-6, rtol=0)))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        for j in range(5):
            self.hist[j].update(outro.hist[j])
        self.soma_total += outro.soma_total
        self.n_soma_divergente += outro.n_soma_divergente


def acumular(grupos: dict, df: pd.DataFrame, ano: int) -> None:
    if df.empty:
        return
    ufs = df['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError(f'{ano}: UF da prova inválida/ausente.')
    codigos = df['__escola'].map(lambda v: ind45.codigo_escola(v, ano))
    total = df['__nota_total'].to_numpy(dtype='float64')
    notas = df[list(NOTAS_COMP)].to_numpy(dtype='float64')
    estrutura = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codigos.to_numpy()})
    for (uf, cod), indices in estrutura.groupby(['uf', 'codigo'], sort=False).indices.items():
        grupos[(str(uf), str(cod))].adicionar(notas[indices], total[indices])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if ano not in range(2019, 2024):
        raise ValueError('TP_ESCOLA só é aplicável a 2019–2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    campos = ['SG_UF_PROVA', 'TP_ESCOLA', 'TP_STATUS_REDACAO',
              'NU_NOTA_REDACAO', *NOTAS_COMP]
    for parte in ind45.ler_blocos(arquivo, campos, bloco):
        validas = ind45.selecionar_validas(parte)
        n_validas += len(validas)
        if not validas.empty:
            validas['__escola'] = validas['TP_ESCOLA']
            acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {
        'metodo': 'mesma_linha', 'variavel_origem': 'TP_ESCOLA',
    }


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Join exato; rejeita linhas duplicadas e falta de pareamento."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind046_') as pasta:
        db = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes('
                       'id TEXT PRIMARY KEY, uf TEXT NOT NULL, escola TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE vistos(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            total_participantes = 0
            for parte in ind45.ler_blocos(
                    participantes, ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q023'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                escola = parte['Q023'].astype('string').str.strip().tolist()
                if any(not s for s in ids) or any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?)', zip(ids, ufs, escola))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from erro
                total_participantes += len(ids)
            db.commit()
            log(f'  2024: {total_participantes:,} participantes indexados.')
            validas_total = 0
            vinculadas_total = 0
            campos = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *NOTAS_COMP]
            for parte in ind45.ler_blocos(competencias, campos, bloco):
                validas = ind45.selecionar_validas(parte)
                validas_total += len(validas)
                if validas.empty:
                    continue
                ids = validas['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not s for s in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia.')
                try:
                    db.executemany('INSERT INTO vistos VALUES (?)', ((s,) for s in ids))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição válida duplicada.') from erro
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                encontrados = db.execute('''SELECT l.pos, p.uf, p.escola
                    FROM lote AS l INNER JOIN participantes AS p ON l.id=p.id''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                atributos = [None] * len(ids)
                for pos, uf, escola in encontrados:
                    atributos[pos] = (uf, escola)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [x[0] for x in atributos]
                validas['__escola'] = [x[1] for x in atributos]
                acumular(grupos, validas, 2024)
                vinculadas_total += len(ids)
                db.commit()
            return dict(grupos), validas_total, {
                'metodo': 'join_NU_INSCRICAO',
                'n_participantes': total_participantes,
                'n_redacoes_validas_vinculadas': vinculadas_total,
                'n_validas_sem_correspondencia': 0,
                'chave_unica_participantes': True,
                'chave_unica_redacoes_validas': True,
                'variavel_origem': 'Q023',
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    brasil = defaultdict(Grupo)
    for (uf, codigo), grupo in grupos.items():
        if uf not in UFS:
            raise ValueError(f'UF não reconhecida: {uf}')
        brasil[('BR', codigo)].combinar(grupo)
    return {**grupos, **brasil}


def ler_referencia(base: Path, caminho: Path | None) -> dict:
    arq = caminho or base/'outputs'/'json'/'IND_045_tipo_escola_nota.json'
    if caminho is not None and not arq.is_absolute():
        arq = base / arq
    if not arq.is_file():
        raise FileNotFoundError('IND-045 deve ser executado antes: ' + str(arq))
    ref = json.loads(arq.read_text(encoding='utf-8-sig'))
    if ref.get('indicator_id') != 'IND-045' or ref.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência incompatível: esperado JSON oficial do IND-045.')
    return ref


def conferir_e_montar(ano: int, grupos: dict, n_validas: int,
                       referencia: dict) -> tuple[dict, dict]:
    ref_ano = referencia.get('years', {}).get(str(ano), {})
    if ref_ano.get('status') != 'ok':
        raise ValueError(f'IND-045/{ano} não está disponível para conciliar IND-046.')
    ref = ref_ano.get('recortes', {})
    if set(ref) != {'BR', *UFS}:
        raise ValueError(f'IND-045/{ano}: Brasil + 27 UFs são obrigatórios.')
    if ref_ano.get('n_brasil') != n_validas:
        raise ValueError(f'{ano}: N BR do IND-046 ({n_validas}) != IND-045 '
                         f'({ref_ano.get("n_brasil")}).')
    variavel = 'TP_ESCOLA' if ano < 2024 else 'Q023'
    codigos = [* (ind45.HIST_ESCOLA if ano < 2024 else ind45.Q023_ESCOLA),
               ind45.SEM_RESPOSTA, ind45.INVALIDO]
    for uf in ('BR', *UFS):
        esperado = ref[uf]
        if esperado['n_pop_socio_valid'] != sum(
                grupos.get((uf, c), Grupo()).n for c in codigos):
            raise ValueError(f'{ano}/{uf}: categorias não fecham com N do IND-045.')
        if esperado.get('variavel_origem') != variavel:
            raise ValueError(f'{ano}/{uf}: variável de escola não coincide com IND-045.')
        cats = esperado['categories']
        if [c['codigo_escola'] for c in cats] != codigos:
            raise ValueError(f'{ano}/{uf}: ordem/códigos diferem do IND-045.')
        for c in cats:
            codigo = c['codigo_escola']
            g = grupos.get((uf, codigo), Grupo())
            if any(sum(h.values()) != g.n for h in g.hist):
                raise ValueError(f'{ano}/{uf}/{codigo}: histograma não fecha com N.')
            if not c['suprimido']:
                if g.n != c['n_redacoes']:
                    raise ValueError(f'{ano}/{uf}/{codigo}: N difere do IND-045.')
                if 0 < g.n < LIMIAR:
                    raise ValueError(f'{ano}/{uf}/{codigo}: grupo pequeno não suprimido!')
                if g.n and not math.isclose(g.soma_total/g.n, c['media'], abs_tol=0.00015,
                                            rel_tol=0):
                    raise ValueError(f'{ano}/{uf}/{codigo}: média da nota difere do IND-045.')
            else:
                if c['n_redacoes'] is not None or c['media'] is not None:
                    raise ValueError(f'{ano}/{uf}/{codigo}: IND-045 não suprimiu estatísticas.')
    inesperados = {(uf, c) for (uf, c), g in grupos.items()
                   if c not in codigos or uf not in {'BR', *UFS}}
    if inesperados:
        raise ValueError(f'{ano}: grupos inesperados {inesperados}.')
    motivos_ref = ref_ano['validacao']['categorias_suprimidas_globalmente']
    for c in codigos:
        motivos = {ref[uf]['categories'][codigos.index(c)]['motivo_supressao']
                   for uf in ('BR', *UFS)}
        if motivos != {motivos_ref.get(c)}:
            raise ValueError(f'{ano}/{c}: supressão geográfica incoerente com IND-045.')
        if any(0 < grupos.get((uf, c), Grupo()).n < LIMIAR for uf in ('BR', *UFS)) \
                and c not in motivos_ref:
            raise ValueError(f'{ano}/{c}: risco de publicação de grupo de N<30.')

    resultados = {}
    qtd_suprimidas = 0
    for uf in ('BR', *UFS):
        rec = ref[uf]
        itens = []
        for categoria in rec['categories']:
            cod = categoria['codigo_escola']
            g = grupos.get((uf, cod), Grupo())
            oculto = bool(categoria['suprimido'])
            qtd_suprimidas += int(oculto)
            competencias = {}
            for pos, chave in enumerate(COMPETENCIAS):
                competencias[chave] = (
                    {'n_redacoes': None, **{stat: None for stat in
                        ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')}}
                    if oculto else {'n_redacoes': g.n,
                                    **ind45.estatisticas(g.hist[pos], g.n)})
            itens.append({
                'codigo_escola': cod,
                'descricao_categoria': categoria['descricao_categoria'],
                'ordem': categoria['ordem'],
                'n_redacoes': None if oculto else g.n,
                'percentual_total_validas': None if oculto else categoria['percentual_total_validas'],
                'suprimido': oculto,
                'motivo_supressao': categoria['motivo_supressao'],
                'competencias': competencias,
            })
        resultados[uf] = {
            'uf': uf, 'population': 'POP_SOCIO_VALID',
            'variavel_origem': variavel, 'conceito': rec['conceito'],
            'n_pop_socio_valid': rec['n_pop_socio_valid'],
            'categories': itens,
            'status_publicacao': 'draft_revisao_academica_privacidade_cruzada_pendente',
        }
    if qtd_suprimidas != ref_ano['validacao']['n_celulas_geograficas_suprimidas']:
        raise ValueError(f'{ano}: total de células suprimidas não coincide com IND-045.')
    divergencias = sum(grupos.get(('BR', c), Grupo()).n_soma_divergente for c in codigos)
    if divergencias != ref_ano['validacao']['n_soma_competencias_divergente']:
        raise ValueError(f'{ano}: divergência C1+...+C5 vs nota total difere do IND-045.')
    validacao = {
        'n_pop_socio_valid_brasil': n_validas,
        'indicador_referencia': 'IND-045',
        'populacao_categorias_e_medias_totais_conferidas': True,
        'histogramas_c1_c5_reconciliados': True,
        'supressao_identica_ao_ind045': True,
        'n_redacoes_com_soma_competencias_divergente': divergencias,
        'categorias_suprimidas_globalmente': motivos_ref,
        'categorias_geograficas_suprimidas': qtd_suprimidas,
        'revisao_privacidade_cruzada_pendente': True,
    }
    return resultados, validacao


def linhas_csv(anos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(anos.items(), key=lambda par: int(par[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            recorte = obj['recortes'][uf]
            for cat in recorte['categories']:
                for comp, valores in cat['competencias'].items():
                    linhas.append({
                        'ano': int(ano), 'uf': uf,
                        'variavel_origem': recorte['variavel_origem'],
                        'conceito': recorte['conceito'],
                        'codigo_escola': cat['codigo_escola'],
                        'descricao_categoria': cat['descricao_categoria'],
                        'ordem': cat['ordem'], 'competencia': comp,
                        'n_redacoes': valores['n_redacoes'],
                        'media': valores['media'], 'mediana': valores['mediana'],
                        'q1': valores['q1'], 'q3': valores['q3'],
                        'iqr': valores['iqr'], 'desvio_padrao': valores['desvio_padrao'],
                        'percentual_total_validas': cat['percentual_total_validas'],
                        'suprimido': cat['suprimido'],
                        'motivo_supressao': cat['motivo_supressao'],
                    })
    return linhas


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as fh:
            temp = Path(fh.name)
            gravador = csv.DictWriter(fh, delimiter=';', fieldnames=CAMPOS_CSV)
            gravador.writeheader()
            gravador.writerows(linhas)
        temp.replace(caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def integrar_dashboards(saida: Path, processados: dict[str, dict]) -> None:
    preparados = []
    for texto, obj in sorted(processados.items(), key=lambda par: int(par[0])):
        if obj.get('status') != 'ok':
            continue
        ano = int(texto)
        arquivo = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not arquivo.is_file():
            log(f'  Dashboard {ano} não encontrado; bloco não integrado.')
            continue
        doc = json.loads(arquivo.read_text(encoding='utf-8-sig'))
        socio = doc.get('pages', {}).get('socioeconomic')
        if not isinstance(socio, dict):
            raise ValueError(f'{arquivo.name}: pages.socioeconomic ausente/inválido.')
        # Prova de que o dashboard realmente usa o mesmo IND-045.
        total = socio.get('school_type_total')
        if not isinstance(total, dict) or total.get('indicator_id') != 'IND-045':
            raise ValueError(f'{arquivo.name}: integre IND-045 antes do IND-046.')
        rec = obj['recortes']
        socio['school_type_competencies'] = {
            'indicator_id': 'IND-046', 'status': 'draft', 'year': ano,
            'population': 'POP_SOCIO_VALID',
            'source_variable': obj['variavel_origem'],
            'concept': obj['conceito'],
            'comparability_across_years': 'not_directly_comparable_2019_2023_vs_2024',
            'national': rec['BR'], 'states': {uf: rec[uf] for uf in UFS},
            'method': 'média e mediana de C1–C5 por escola/UF, quartis e N',
            'privacy_note': 'Supressões herdadas do IND-045; revisão cruzada pendente.',
        }
        doc.setdefault('quality', {})['ind046_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-046: TP_ESCOLA 2019–2023 e Q023 2024 não são equivalentes; '
                 'supressões do IND-045 mantidas; revisão cruzada pendente.')
        avisos = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in avisos:
            avisos.append(aviso)
        preparados.append((arquivo, doc))
    for arquivo, doc in preparados:
        ind45.salvar_json(arquivo, doc)
        log(f'  Dashboard {arquivo.name} atualizado sem .bak.')


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_path: Path | None = None,
             escolhas: dict[str, Path] | None = None) -> dict:
    base = base.resolve()
    saida = saida.resolve()
    destino_json = saida/'outputs'/'json'/'IND_046_tipo_escola_competencias.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_046_tipo_escola_competencias.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-046 já existe. Use --sobrescrever.')
    referencia = ler_referencia(base, referencia_path)
    necessarias = set()
    for ano in anos:
        if ano <= 2023:
            necessarias.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            necessarias.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = ind45.localizar_fontes(base, necessarias, escolhas)
    if necessarias - set(fontes):
        raise FileNotFoundError('Microdados ausentes: '+', '.join(sorted(necessarias - set(fontes))))
    anteriores = {}
    if sobrescrever and destino_json.is_file():
        anterior = json.loads(destino_json.read_text(encoding='utf-8-sig'))
        if anterior.get('indicator_id') != 'IND-046':
            raise ValueError('Arquivo JSON existente não pertence ao IND-046.')
        anteriores = anterior.get('years', {})
    anos_doc = dict(anteriores)
    novos = {}
    for ano in anos:
        log(f'IND-046 | {ano}: escola × C1–C5 na POP_SOCIO_VALID...')
        if ano == 2025:
            if referencia.get('years', {}).get('2025', {}).get('status') != 'indisponivel':
                raise ValueError('IND-045/2025 não confirma indisponibilidade de associação.')
            obj = {
                'ano': 2025, 'status': 'indisponivel',
                'reason': 'Sem chave pública comum entre trajetória escolar e notas C1–C5 em 2025.',
                'recortes': {},
            }
        else:
            if ano == 2024:
                grupos, n_validas, diag = ler_2024(
                    fontes['PARTICIPANTES_2024.CSV'],
                    fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            else:
                grupos, n_validas, diag = ler_mesma_linha(
                    fontes[f'MICRODADOS_ENEM_{ano}.CSV'], ano, bloco)
            if diag.get('n_redacoes_validas_vinculadas', n_validas) != n_validas:
                raise ValueError(f'{ano}: junção não reconciliada.')
            recortes, validacao = conferir_e_montar(
                ano, criar_brasil(grupos), n_validas, referencia)
            variavel = 'TP_ESCOLA' if ano < 2024 else 'Q023'
            conceito = 'Tipo de escola do ensino médio' if ano < 2024 else 'Trajetória escolar autodeclarada'
            obj = {
                'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
                'variavel_origem': variavel, 'conceito': conceito,
                'n_brasil': n_validas, 'diagnostico_fonte': diag,
                'validacao': validacao, 'recortes': recortes,
            }
            log(f'  BR={n_validas:,}; categorias geográficas suprimidas='
                f'{validacao["categorias_geograficas_suprimidas"]}; validação IND-045 OK.')
        novos[str(ano)] = obj
        anos_doc[str(ano)] = obj
    modulo = {
        'indicator_id': 'IND-046', 'titulo': 'Tipo de escola × competências C1–C5',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(ano) for ano, obj in anos_doc.items()
                                 if obj.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'population': 'TP_STATUS_REDACAO=1; nota 0..1000 e C1..C5 em 0..200',
            '2019_2023_source_variable': 'TP_ESCOLA',
            '2024_source_variable': 'Q023',
            'comparability': 'TP_ESCOLA ≠ Q023; evitar comparações como categorias equivalentes',
            'statistics': 'média/mediana/Q1/Q3/IQR/DP populacional por competência, categoria, UF e ano',
            'quantiles': 'Hyndman–Fan tipo 7; histogramas exatos',
            'reference': 'IND-045 para N, médias totais e regras de supressão',
            '2024_join': 'NU_INSCRICAO, com unicidade e pareamento completo de redações válidas',
            '2025': 'indisponível por inexistência de chave pública de vínculo',
            'privacy': ('herda supressão anual global por categoria e complemento de IND-045; '
                        'revisão de risco cruzado com demais indicadores ainda pendente'),
            'notes': ['Resultados descritivos, não causais.',
                      'TP_ESCOLA=1 indica não respondeu, não escola pública.',
                      'Q023=F não frequentou o ensino médio, não é resposta ausente.',
                      'UF da prova não indica necessariamente residência.',
                      'Ano mede participações, não candidatos únicos.',
                      'Status draft até homologação acadêmica e revisão de privacidade.'],
        },
        'years': anos_doc,
    }
    # Cálculos e conciliações terminam antes de qualquer gravação.
    ind45.salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas_csv(anos_doc))
    if not somente_modulo:
        integrar_dashboards(saida, novos)
    log(f'IND-046 concluído (draft). JSON: {destino_json} | CSV: {destino_csv}')
    return modulo


def autoteste() -> None:
    """Testa estatística exata, supressões, reconciliação realista e join 2024."""
    rng = np.random.default_rng(46)
    for _ in range(80):
        valores = rng.choice([0., 40., 80., 120., 160., 200.],
                             size=int(rng.integers(1, 100)))
        h = Counter(float(v) for v in valores)
        s = ind45.estatisticas(h, len(valores))
        assert abs(s['media']-valores.mean()) < 0.00011
        assert abs(s['mediana']-np.median(valores)) < 0.00011
        for p, chave in ((.25, 'q1'), (.75, 'q3')):
            assert abs(s[chave]-np.quantile(valores, p, method='linear')) < 0.00011
    with tempfile.TemporaryDirectory(prefix='teste_ind046_') as pasta:
        base = Path(pasta)
        data = base/'data'/'raw'
        data.mkdir(parents=True)
        (base/'outputs'/'json').mkdir(parents=True)
        linhas_2019 = []
        linhas_2024 = []
        for pos_uf, uf in enumerate(UFS):
            for k in range(100):
                categoria_2019 = '1' if k < 50 else '2' if k < 90 else '3'
                categoria_2024 = 'A' if k < 50 else 'B' if k < 90 else 'C'
                notas = [float(x) for x in [80+20*(k%5), 100, 120, 140, 160]]
                total = int(sum(notas))
                comum = {
                    'NU_INSCRICAO': str(900000+pos_uf*100+k),
                    'SG_UF_PROVA': uf, 'TP_STATUS_REDACAO': '1',
                    'NU_NOTA_REDACAO': str(total),
                    **{col: str(notas[j]) for j, col in enumerate(NOTAS_COMP)},
                }
                linhas_2019.append({**comum, 'TP_ESCOLA': categoria_2019})
                linhas_2024.append({**comum, 'Q023': categoria_2024})
        df19 = pd.DataFrame(linhas_2019)
        df24 = pd.DataFrame(linhas_2024)
        df19.drop(columns='NU_INSCRICAO').to_csv(
            data/'MICRODADOS_ENEM_2019.csv', index=False, sep=';')
        df24[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q023']].iloc[::-1].to_csv(
            data/'PARTICIPANTES_2024.csv', index=False, sep=';')
        df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *NOTAS_COMP]].to_csv(
            data/'COMPETENCIAS_REDACAO_2024.csv', index=False, sep=';')
        # Construir referência IND-043 sintética e depois produzir o IND-045
        # com o código REAL desse indicador. Assim a conciliação de IND-046
        # não depende de expectativas introduzidas pelo próprio IND-046.
        ref43 = {'indicator_id': 'IND-043', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano, df in ((2019, df19), (2024, df24)):
            rec = {}
            for uf in ('BR', *UFS):
                grupo = df if uf == 'BR' else df.loc[df['SG_UF_PROVA'] == uf]
                n = len(grupo)
                media = round(pd.to_numeric(grupo['NU_NOTA_REDACAO']).mean(), 4)
                rec[uf] = {'n_pop_socio_valid': n, 'questions': {'Q001': {
                    'categories': [{'n_redacoes': n, 'media': media}],
                }}}
            ref43['years'][str(ano)] = {'status': 'ok', 'recortes': rec}
        ind45.salvar_json(base/'outputs'/'json'/'IND_043_escolaridade_responsaveis_nota.json', ref43)
        for ano in (2019, 2024):
            ind45.salvar_json(base/'outputs'/'json'/f'dashboard_enem_{ano}.json', {
                'pages': {'socioeconomic': {'sentinela': 'preservar'}},
                'quality': {'sentinela': 'preservar'}, 'meta': {'warnings': []},
            })
        ind45.executar(base, base, (2019, 2024, 2025), 61, True, False)
        obj = executar(base, base, (2019, 2024, 2025), 73, True, False)
        assert obj['years']['2025']['status'] == 'indisponivel'
        assert obj['years']['2024']['validacao']['supressao_identica_ao_ind045']
        assert obj['years']['2019']['recortes']['BR']['variavel_origem'] == 'TP_ESCOLA'
        assert obj['years']['2024']['recortes']['BR']['variavel_origem'] == 'Q023'
        for ano in (2019, 2024):
            for uf in ('BR', 'SP', 'AC'):
                cats = obj['years'][str(ano)]['recortes'][uf]['categories']
                assert all(set(x['competencias']) == set(COMPETENCIAS) for x in cats)
                assert any(x['suprimido'] for x in cats)
                assert any(not x['suprimido'] and x['n_redacoes'] > 0 for x in cats)
                assert all(all(v['media'] is None for v in x['competencias'].values())
                           for x in cats if x['suprimido'])
            doc = json.loads((base/'outputs'/'json'/f'dashboard_enem_{ano}.json').read_text())
            assert doc['pages']['socioeconomic']['sentinela'] == 'preservar'
            assert doc['pages']['socioeconomic']['school_type_total']['indicator_id'] == 'IND-045'
            assert doc['pages']['socioeconomic']['school_type_competencies']['indicator_id'] == 'IND-046'
        with (base/'outputs'/'indicadores'/'IND_046_tipo_escola_competencias.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            dados = list(csv.DictReader(fh, delimiter=';'))
            assert len(dados) == 28 * (6+8) * 5
            assert not any('NU_INSCRICAO' in r for r in dados)
            assert all(not r['media'] for r in dados if r['suprimido'] == 'True')
        # Troca de bloco/ordem de leitura não altera o resultado numérico.
        g_a, n_a, _ = ler_2024(data/'PARTICIPANTES_2024.csv',
                              data/'COMPETENCIAS_REDACAO_2024.csv', 31)
        g_b, n_b, _ = ler_2024(data/'PARTICIPANTES_2024.csv',
                              data/'COMPETENCIAS_REDACAO_2024.csv', 427)
        assert n_a == n_b == len(df24)
        assert all(g_a[k].n == g_b[k].n and g_a[k].hist == g_b[k].hist for k in g_a)
        # A redação válida sem chave correspondente precisa causar falha.
        sem = df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *NOTAS_COMP]].copy()
        sem.loc[0, 'NU_INSCRICAO'] = 'SEM_CORRESPONDENCIA'
        sem.to_csv(data/'COMPETENCIAS_REDACAO_INCOMPLETA_2024.csv', index=False, sep=';')
        try:
            ler_2024(data/'PARTICIPANTES_2024.csv',
                     data/'COMPETENCIAS_REDACAO_INCOMPLETA_2024.csv', 53)
        except ValueError as erro:
            assert 'sem vínculo' in str(erro)
        else:
            raise AssertionError('Join inválido não foi rejeitado.')
        assert not list(base.rglob('*.bak'))
    log('AUTOTESTE IND-046 APROVADO: estatísticas, join 2024, supressão, '
        'reconciliação IND-045, CSV/JSON, 2025 e dashboards.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-046 — Tipo de escola × C1–C5')
    parser.add_argument('--base', type=Path, default=ind45.raiz_projeto())
    parser.add_argument('--saida', type=Path, default=ind45.raiz_projeto())
    parser.add_argument('--referencia-ind045', type=Path, default=None)
    parser.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    parser.add_argument('--bloco', type=int, default=100_000)
    parser.add_argument('--sobrescrever', action='store_true')
    parser.add_argument('--somente-modulo', action='store_true')
    parser.add_argument('--competencias-2024', type=Path, default=None)
    parser.add_argument('--participantes-2024', type=Path, default=None)
    parser.add_argument('--autoteste', action='store_true')
    args = parser.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(ano not in ANOS for ano in anos):
        parser.error('--anos deve conter valores entre 2019 e 2025.')
    if args.bloco < 1:
        parser.error('--bloco deve ser positivo.')
    fontes = {}
    if args.competencias_2024 is not None:
        fontes['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        fontes['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.referencia_ind045, fontes)
    except (OSError, ValueError, KeyError, sqlite3.DatabaseError,
            json.JSONDecodeError) as erro:
        print(f'ERRO IND-046: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
