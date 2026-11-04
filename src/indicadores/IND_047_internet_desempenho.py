#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-047 — Internet no domicílio × desempenho da redação | UNIVESP PI IV.

Catálogo ENEM 2019–2025 v2: pages.socioeconomic.internet_performance.
População POP_SOCIO_VALID, referência obrigatória IND-045 para N e QA.

2019–2023: Q025, acesso à internet no domicílio, microdados na mesma linha.
2024: Q020, acesso a internet via Wi-Fi, junção PARTICIPANTES_2024 com
      COMPETENCIAS_REDACAO_2024 por NU_INSCRICAO única.
2025: sem chave pública comum entre questionário e competências: indisponível.
Q025 ≠ Q020; NÃO fundir ou comparar tendências como conceitos idênticos.
Categorias: A=Não, B=Sim, SEM_RESPOSTA e CODIGO_NAO_RECONHECIDO.

Para cada categoria/UF/ano: N, média/mediana/Q1/Q3/IQR/DP da nota total
(C0) e das competências C1..C5; diferença B-A e d padronizado apenas como
associação descritiva. Histogramas exatos, quantis Hyndman–Fan tipo 7.

Controles: validação de notas/UF; 2024 com pareamento completo/unicidade;
conciliação UF/BR, população e discrepâncias com IND-045; supressão de
células pequenas (N=1..29) anual por categoria em todas as UFs e complemento;
resultados 'draft' até revisão cruzada de privacidade e homologação.

Execução, a partir da raiz do repositório:
  python src/indicadores/IND_047_internet_desempenho.py --autoteste
  python src/indicadores/IND_047_internet_desempenho.py --anos 2024 --sobrescrever
  python src/indicadores/IND_047_internet_desempenho.py --sobrescrever

Saídas:
  outputs/json/IND_047_internet_desempenho.json
  outputs/indicadores/IND_047_internet_desempenho.csv
  outputs/json/dashboard_enem_<ano>.json (bloco internet_performance)

Requer IND_045_tipo_escola_nota.py na mesma pasta e seu JSON real no projeto.
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
MEDIDAS = ('C0', 'C1', 'C2', 'C3', 'C4', 'C5')
CAMPOS_NOTAS = ('NU_NOTA_REDACAO', *NOTAS_COMP)
CATEGORIAS = {
    'A': 'Não',
    'B': 'Sim',
    'SEM_RESPOSTA': 'Não informou',
    'CODIGO_NAO_RECONHECIDO': 'Código não reconhecido',
}
LIMIAR = ind45.LIMIAR
CAMPOS_CSV = (
    'ano', 'uf', 'variavel_origem', 'conceito', 'codigo_acesso',
    'descricao_categoria', 'ordem', 'medida', 'n_redacoes', 'media',
    'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'percentual_total_validas', 'suprimido', 'motivo_supressao',
    'diferenca_medias_sim_menos_nao', 'diferenca_medianas_sim_menos_nao',
    'd_padronizado_sim_menos_nao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def conceito_ano(ano: int) -> str:
    return ('Acesso à internet no domicílio' if ano < 2024
            else 'Acesso à internet via Wi-Fi no domicílio')


def variavel_ano(ano: int) -> str:
    return 'Q025' if ano < 2024 else 'Q020'


def codigo_acesso(valor: Any) -> str:
    codigo = '' if valor is None else str(valor).strip().upper()
    if codigo in ('', '<NA>', 'NAN', 'NULL', 'NONE'):
        return 'SEM_RESPOSTA'
    return codigo if codigo in ('A', 'B') else 'CODIGO_NAO_RECONHECIDO'


class Grupo:
    """Acumula apenas frequências das notas, sem microdados individuais."""
    def __init__(self) -> None:
        self.n = 0
        self.hist = {medida: Counter() for medida in MEDIDAS}
        self.n_soma_divergente = 0

    def adicionar(self, notas: np.ndarray) -> None:
        if notas.ndim != 2 or notas.shape[1] != 6:
            raise ValueError('Matriz de desempenho precisa conter nota total e C1..C5.')
        self.n += len(notas)
        if not len(notas):
            return
        for j, medida in enumerate(MEDIDAS):
            valores, frequencias = np.unique(notas[:, j], return_counts=True)
            self.hist[medida].update({float(v): int(f) for v, f in zip(valores, frequencias)})
        divergentes = ~np.isclose(notas[:, 1:].sum(axis=1), notas[:, 0],
                                  rtol=0, atol=1e-6)
        self.n_soma_divergente += int(np.count_nonzero(divergentes))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        for medida in MEDIDAS:
            self.hist[medida].update(outro.hist[medida])
        self.n_soma_divergente += outro.n_soma_divergente


def acumular(grupos: dict, validas: pd.DataFrame, ano: int) -> None:
    if validas.empty:
        return
    ufs = validas['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError(f'{ano}: UF da prova ausente ou inválida.')
    codigos = validas['__internet'].map(codigo_acesso)
    notas = validas[['__nota_total', *NOTAS_COMP]].to_numpy(dtype='float64')
    indices = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codigos.to_numpy()})
    for (uf, cod), linhas in indices.groupby(['uf', 'codigo'], sort=False).indices.items():
        grupos[(str(uf), str(cod))].adicionar(notas[linhas])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if ano < 2019 or ano > 2023:
        raise ValueError('Q025 para acesso à internet é válido neste indicador apenas em 2019–2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    campos = ['SG_UF_PROVA', 'Q025', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]
    for parte in ind45.ler_blocos(arquivo, campos, bloco):
        validas = ind45.selecionar_validas(parte)
        n_validas += len(validas)
        if not validas.empty:
            validas['__internet'] = validas['Q025']
            acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {
        'metodo': 'mesma_linha', 'variavel_origem': 'Q025',
        'n_redacoes_validas_processadas': n_validas,
    }


def identificadores(df: pd.DataFrame, nome: str) -> list[str]:
    codigos = df['NU_INSCRICAO'].astype('string').str.strip().tolist()
    if any(not s or s.upper() in ('NAN', 'NULL', '<NA>', 'NONE') for s in codigos):
        raise ValueError(f'{nome}: NU_INSCRICAO vazia/inválida.')
    return codigos


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Pareamento estrito em SQLite temporário; sem join posicional."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind047_') as diretorio:
        db = sqlite3.connect(str(Path(diretorio) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes('
                       'id TEXT PRIMARY KEY, uf TEXT NOT NULL, internet TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE validas_vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ind45.ler_blocos(participantes,
                                           ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q020'], bloco):
                ids = identificadores(parte, 'PARTICIPANTES_2024')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                valores = parte['Q020'].astype('string').str.strip().tolist()
                if any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: UF ausente/inválida.')
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?)', zip(ids, ufs, valores))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from erro
                n_participantes += len(ids)
            db.commit()
            log(f'  2024: {n_participantes:,} participantes indexados.')
            n_validas = 0
            for parte in ind45.ler_blocos(competencias,
                                           ['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS], bloco):
                validas = ind45.selecionar_validas(parte)
                n_validas += len(validas)
                if validas.empty:
                    continue
                ids = identificadores(validas, 'COMPETENCIAS_REDACAO_2024')
                try:
                    db.executemany('INSERT INTO validas_vistas VALUES (?)', ((v,) for v in ids))
                except sqlite3.IntegrityError as erro:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição válida duplicada.') from erro
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                encontrados = db.execute('''
                    SELECT l.pos, p.uf, p.internet
                    FROM lote AS l JOIN participantes AS p ON p.id = l.id
                ''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                atributos = [None] * len(ids)
                for pos, uf, internet in encontrados:
                    atributos[pos] = (uf, internet)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [x[0] for x in atributos]
                validas['__internet'] = [x[1] for x in atributos]
                acumular(grupos, validas, 2024)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'variavel_origem': 'Q020',
                'n_participantes_indexados': n_participantes,
                'n_redacoes_validas_vinculadas': n_validas,
                'n_validas_sem_correspondencia': 0,
                'inscricoes_unicas_participantes': True,
                'inscricoes_unicas_redacoes_validas': True,
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    total = defaultdict(Grupo)
    for (uf, cod), grupo in grupos.items():
        if uf not in UFS:
            raise ValueError(f'UF não reconhecida: {uf}')
        if cod not in CATEGORIAS:
            raise ValueError(f'Categoria de internet inesperada: {cod}')
        total[('BR', cod)].combinar(grupo)
    return {**grupos, **total}


def ler_referencia(base: Path, caminho: Path | None) -> dict:
    arquivo = caminho or (base / 'outputs' / 'json' / 'IND_045_tipo_escola_nota.json')
    if caminho is not None and not arquivo.is_absolute():
        arquivo = base / arquivo
    if not arquivo.is_file():
        raise FileNotFoundError(f'IND-045 necessário para conciliação da população: {arquivo}')
    referencia = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if referencia.get('indicator_id') != 'IND-045' or referencia.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência incompatível: esperado JSON IND-045/POP_SOCIO_VALID.')
    return referencia


def conferir_montar(ano: int, grupos: dict, n_validas: int, ref: dict) -> tuple[dict, dict]:
    ref_ano = ref.get('years', {}).get(str(ano), {})
    if ref_ano.get('status') != 'ok':
        raise ValueError(f'IND-045/{ano} não disponível para conciliação IND-047.')
    if ref_ano.get('n_brasil') != n_validas:
        raise ValueError(f'{ano}: N Brasil {n_validas} difere IND-045 ({ref_ano.get("n_brasil")}).')
    referencia_ufs = ref_ano.get('recortes', {})
    if set(referencia_ufs) != {'BR', *UFS}:
        raise ValueError(f'{ano}: IND-045 deve conter BR e 27 UFs.')
    if (ref_ano.get('diagnostico_fonte', {}).get('n_redacoes_validas_vinculadas', n_validas)
            != n_validas):
        raise ValueError(f'{ano}: referência IND-045 não confirma vínculo completo.')

    for geo in ('BR', *UFS):
        n = sum(grupos.get((geo, codigo), Grupo()).n for codigo in CATEGORIAS)
        n_ref = referencia_ufs[geo]['n_pop_socio_valid']
        if n != n_ref:
            raise ValueError(f'{ano}/{geo}: N IND-047 {n} difere IND-045 {n_ref}.')
        # Conciliação de médias totais quando o IND-045 não suprimiu categorias.
        ref_cats = referencia_ufs[geo]['categories']
        if all(not c['suprimido'] for c in ref_cats):
            media_ref = (math.fsum(c['n_redacoes'] * c['media']
                                  for c in ref_cats if c['n_redacoes']) / n_ref) if n_ref else 0
            soma = math.fsum(float(nota) * freq
                             for codigo in CATEGORIAS
                             for nota, freq in grupos.get((geo, codigo), Grupo()).hist['C0'].items())
            media = soma / n if n else 0
            if not math.isclose(media, media_ref, rel_tol=0, abs_tol=.00015):
                raise ValueError(f'{ano}/{geo}: média total difere IND-045 ({media}, {media_ref}).')
    divergencias = sum(grupos.get(('BR', c), Grupo()).n_soma_divergente for c in CATEGORIAS)
    divergencias_ref = ref_ano.get('validacao', {}).get('n_soma_competencias_divergente')
    if divergencias_ref is None or divergencias != divergencias_ref:
        raise ValueError(f'{ano}: divergências C1..C5 vs nota total ({divergencias}) '
                         f'diferem IND-045 ({divergencias_ref}).')
    for (uf, codigo), grupo in grupos.items():
        if uf not in {'BR', *UFS} or codigo not in CATEGORIAS:
            raise ValueError(f'Grupo inesperado: {uf}/{codigo}')
        if any(sum(grupo.hist[m].values()) != grupo.n for m in MEDIDAS):
            raise ValueError(f'{ano}/{uf}/{codigo}: histograma não fecha com N.')

    # Supressão anual e geograficamente uniforme: evita publicação de grupo
    # pequeno na UF e recuperação por Brasil = soma das UFs.
    pequenos = {c for c in CATEGORIAS if any(
        0 < grupos.get((uf, c), Grupo()).n < LIMIAR for uf in ('BR', *UFS))}
    motivos = {c: 'primaria_grupo_pequeno_em_alguma_uf' for c in pequenos}
    if pequenos:
        # O complemento precisa contar pelo menos 30 ocorrências em cada UF
        # afetada por célula pequena: uma categoria vazia não a protege.
        afetadas = [uf for uf in UFS if any(
            0 < grupos.get((uf, c), Grupo()).n < LIMIAR for c in pequenos)]
        complementares = [c for c in ('SEM_RESPOSTA', 'CODIGO_NAO_RECONHECIDO', 'A', 'B')
                          if c not in motivos and grupos.get(('BR', c), Grupo()).n >= LIMIAR
                          and all(grupos.get((uf, c), Grupo()).n >= LIMIAR for uf in afetadas)]
        if complementares:
            motivos[complementares[0]] = 'complementar_contra_inferencia_por_totais'
        else:
            # Não há complemento seguro para todas as UFs afetadas;
            # ocultar todas as categorias é a opção conservadora.
            for c in CATEGORIAS:
                motivos.setdefault(c, 'complementar_sem_categoria_segura')

    recortes = {}
    total_suprimidos = 0
    for geo in ('BR', *UFS):
        total_geo = referencia_ufs[geo]['n_pop_socio_valid']
        categorias = []
        for ordem, (codigo, descricao) in enumerate(CATEGORIAS.items()):
            grupo = grupos.get((geo, codigo), Grupo())
            motivo = motivos.get(codigo)
            oculto = motivo is not None
            total_suprimidos += int(oculto)
            if oculto:
                estat = {m: {'n_redacoes': None, **{k: None for k in
                          ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')}}
                         for m in MEDIDAS}
            else:
                estat = {m: {'n_redacoes': grupo.n,
                             **ind45.estatisticas(grupo.hist[m], grupo.n)}
                         for m in MEDIDAS}
            categorias.append({
                'codigo_acesso': codigo, 'descricao_categoria': descricao, 'ordem': ordem,
                'n_redacoes': None if oculto else grupo.n,
                'percentual_total_validas': (None if oculto or not total_geo
                    else round(100 * grupo.n / total_geo, 6)),
                'suprimido': oculto, 'motivo_supressao': motivo,
                'medidas': estat,
            })
        por_codigo = {cat['codigo_acesso']: cat for cat in categorias}
        comparacao = {}
        for m in MEDIDAS:
            a, b = por_codigo['A'], por_codigo['B']
            va, vb = a['medidas'][m], b['medidas'][m]
            pode = (not a['suprimido'] and not b['suprimido']
                    and a['n_redacoes'] >= LIMIAR and b['n_redacoes'] >= LIMIAR)
            delta_media = round(vb['media'] - va['media'], 4) if pode else None
            delta_mediana = round(vb['mediana'] - va['mediana'], 4) if pode else None
            dp = None
            if pode:
                na, nb = a['n_redacoes'], b['n_redacoes']
                variancia = ((na * va['desvio_padrao'] ** 2 +
                              nb * vb['desvio_padrao'] ** 2) / (na + nb))
                if variancia > 0:
                    dp = round(delta_media / math.sqrt(variancia), 4)
            comparacao[m] = {
                'medida': m, 'grupo_referencia': 'A', 'grupo_comparado': 'B',
                'n_nao': a['n_redacoes'] if pode else None,
                'n_sim': b['n_redacoes'] if pode else None,
                'diferenca_medias_sim_menos_nao': delta_media,
                'diferenca_medianas_sim_menos_nao': delta_mediana,
                'd_padronizado_sim_menos_nao': dp,
                'status': 'ok' if pode else 'nao_calculado_por_supressao_ou_amostra_insuficiente',
            }
        recortes[geo] = {
            'uf': geo, 'population': 'POP_SOCIO_VALID',
            'variavel_origem': variavel_ano(ano), 'conceito': conceito_ano(ano),
            'n_pop_socio_valid': total_geo, 'categories': categorias,
            'comparacao_sim_menos_nao': comparacao,
            'status_publicacao': 'draft_revisao_academica_privacidade_cruzada_pendente',
        }

    validacao = {
        'referencia_populacao': 'IND-045',
        'n_pop_socio_valid_brasil': n_validas,
        'n_por_uf_e_brasil_conferido': True,
        'media_total_conferida_quando_referencia_sem_supressao': True,
        'n_soma_competencias_divergente': divergencias,
        'divergencias_conferidas_com_ind045': True,
        'histogramas_seis_medidas_reconciliados': True,
        'categorias_suprimidas_globalmente': motivos,
        'n_celulas_geograficas_suprimidas': total_suprimidos,
        'revisao_privacidade_cruzada_pendente': True,
    }
    return recortes, validacao


def linhas_csv(todos: dict) -> list[dict]:
    linhas = []
    for ano, obj in sorted(todos.items(), key=lambda item: int(item[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = obj['recortes'][uf]
            for cat in rec['categories']:
                for medida in MEDIDAS:
                    est = cat['medidas'][medida]
                    delta = rec['comparacao_sim_menos_nao'][medida]
                    linhas.append({
                        'ano': int(ano), 'uf': uf, 'variavel_origem': rec['variavel_origem'],
                        'conceito': rec['conceito'], 'codigo_acesso': cat['codigo_acesso'],
                        'descricao_categoria': cat['descricao_categoria'], 'ordem': cat['ordem'],
                        'medida': medida, 'n_redacoes': est['n_redacoes'],
                        'media': est['media'], 'mediana': est['mediana'],
                        'q1': est['q1'], 'q3': est['q3'], 'iqr': est['iqr'],
                        'desvio_padrao': est['desvio_padrao'],
                        'percentual_total_validas': cat['percentual_total_validas'],
                        'suprimido': cat['suprimido'],
                        'motivo_supressao': cat['motivo_supressao'],
                        **{k: delta[k] for k in (
                            'diferenca_medias_sim_menos_nao',
                            'diferenca_medianas_sim_menos_nao',
                            'd_padronizado_sim_menos_nao')},
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
            writer = csv.DictWriter(fh, fieldnames=CAMPOS_CSV,
                                    delimiter=';', extrasaction='raise')
            writer.writeheader()
            writer.writerows(linhas)
        temp.replace(caminho)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def preparar_dashboards(saida: Path, novos: dict[str, dict]) -> list[tuple[Path, dict]]:
    """Valida todos os dashboards antes de alterar qualquer um deles."""
    preparados = []
    for ano_str, obj in sorted(novos.items(), key=lambda item: int(item[0])):
        if obj.get('status') != 'ok':
            continue
        ano = int(ano_str)
        arquivo = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not arquivo.is_file():
            log(f'  Dashboard {ano} não encontrado; bloco não integrado.')
            continue
        documento = json.loads(arquivo.read_text(encoding='utf-8-sig'))
        socio = documento.get('pages', {}).get('socioeconomic')
        if not isinstance(socio, dict):
            raise ValueError(f'{arquivo.name}: pages.socioeconomic não é objeto.')
        bloco45 = socio.get('school_type_total')
        if not isinstance(bloco45, dict) or bloco45.get('indicator_id') != 'IND-045':
            raise ValueError(f'{arquivo.name}: integre IND-045 antes do IND-047.')
        rec = obj['recortes']
        socio['internet_performance'] = {
            'indicator_id': 'IND-047', 'status': 'draft', 'year': ano,
            'population': 'POP_SOCIO_VALID',
            'source_variable': obj['variavel_origem'], 'concept': obj['conceito'],
            'comparability_across_years': 'Q025_2019_2023_not_equivalent_to_Q020_wifi_2024',
            'national': rec['BR'], 'states': {uf: rec[uf] for uf in UFS},
            'method': 'N, médias, medianas, quartis e diferença descritiva B-A em C0..C5',
            'privacy_note': 'Supressão global da categoria anual + complemento; revisão cruzada pendente.',
        }
        documento.setdefault('quality', {})['ind047_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-047: Q025 (internet, 2019–2023) difere de Q020 (Wi-Fi, 2024); '
                 'efeito apenas descritivo; supressão de pequenos grupos; revisão cruzada pendente.')
        avisos = documento.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in avisos:
            avisos.append(aviso)
        preparados.append((arquivo, documento))
    return preparados


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_path: Path | None = None,
             escolhas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    destino_json = saida/'outputs'/'json'/'IND_047_internet_desempenho.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_047_internet_desempenho.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-047 já existe. Use --sobrescrever.')
    ref = ler_referencia(base, referencia_path)
    necessarias = set()
    for ano in anos:
        if ano <= 2023:
            necessarias.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            necessarias.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    fontes = ind45.localizar_fontes(base, necessarias, escolhas)
    faltantes = sorted(necessarias - set(fontes))
    if faltantes:
        raise FileNotFoundError(f'Fontes ausentes: {faltantes}. Informe --base ou fontes explícitas.')

    anteriores = {}
    if sobrescrever and destino_json.is_file():
        doc = json.loads(destino_json.read_text(encoding='utf-8-sig'))
        if doc.get('indicator_id') != 'IND-047':
            raise ValueError('JSON existente pertence a outro indicador.')
        anteriores = doc.get('years', {})
    todos = dict(anteriores)
    novos = {}
    for ano in anos:
        log(f'IND-047 | {ano}: internet × nota total e C1–C5...')
        if ano == 2025:
            if ref.get('years', {}).get('2025', {}).get('status') != 'indisponivel':
                raise ValueError('IND-045/2025 não confirma indisponibilidade de vínculo.')
            obj = {
                'ano': ano, 'status': 'indisponivel',
                'reason': ('Questionário socioeconômico e redação de 2025 não têm '
                           'chave pública comum de vinculação nos dados usados.'),
                'recortes': {},
            }
        else:
            if ano == 2024:
                grupos, n_validas, diagnostico = ler_2024(
                    fontes['PARTICIPANTES_2024.CSV'],
                    fontes['COMPETENCIAS_REDACAO_2024.CSV'], bloco)
            else:
                grupos, n_validas, diagnostico = ler_mesma_linha(
                    fontes[f'MICRODADOS_ENEM_{ano}.CSV'], ano, bloco)
            if diagnostico.get('n_redacoes_validas_vinculadas', n_validas) != n_validas:
                raise ValueError(f'{ano}: correspondências válidas não fecham.')
            recortes, validacao = conferir_montar(
                ano, criar_brasil(grupos), n_validas, ref)
            obj = {
                'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
                'variavel_origem': variavel_ano(ano), 'conceito': conceito_ano(ano),
                'n_brasil': n_validas, 'diagnostico_fonte': diagnostico,
                'validacao': validacao, 'recortes': recortes,
            }
            log(f'  N BR={n_validas:,}; supressões geográficas='
                f'{validacao["n_celulas_geograficas_suprimidas"]}; IND-045 reconciliado.')
        novos[str(ano)] = obj
        todos[str(ano)] = obj

    modulo = {
        'indicator_id': 'IND-047', 'titulo': 'Internet × desempenho na redação',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, obj in todos.items() if obj.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'population': 'TP_STATUS_REDACAO=1, nota total 0..1000 e C1..C5 0..200',
            '2019_2023_variable': 'Q025 (acesso à internet no domicílio)',
            '2024_variable': 'Q020 (acesso à internet via Wi-Fi no domicílio)',
            'categories': CATEGORIAS,
            'comparability': 'não harmonizar Q025 e Q020 como a mesma definição temporal',
            'statistics': 'média, mediana, Q1/Q3/IQR, DP populacional, N, percentual; B-A',
            'quantiles': 'Hyndman–Fan tipo 7 em histogramas exatos',
            'effect': 'diferença de médias/medianas (B-A) e d padronizado descritivo, sem causalidade',
            'reference': 'IND-045 para N total por UF/BR, soma de competências e média quando publicável',
            'join_2024': 'NU_INSCRICAO única, pareamento obrigatório de todas as redações válidas',
            '2025': 'indisponível: sem chave pública comum entre questionário e notas',
            'privacy': 'categoria pequena (<30) oculta em BR/UF no ano inteiro + complementar; draft',
            'notes': [
                'C0 é nota total 0..1000, C1..C5 estão na escala 0..200.',
                'Diferença B-A não controla renda, escolaridade ou outros confundidores.',
                'Anos representam participações no exame, não pessoas únicas.',
                'UF é local da prova, não necessariamente residência.',
                'Revisão de privacidade cruzada com outros indicadores é obrigatória.',
            ],
        },
        'years': todos,
    }
    # Evitar falhas de esquema em dashboards após gravar o módulo.
    preparados = [] if somente_modulo else preparar_dashboards(saida, novos)
    ind45.salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas_csv(todos))
    for arquivo, doc in preparados:
        ind45.salvar_json(arquivo, doc)
        log(f'  Dashboard {arquivo.name}: bloco internet_performance integrado.')
    log(f'IND-047 concluído em draft. JSON: {destino_json} | CSV: {destino_csv}')
    return modulo


def autoteste() -> None:
    """Teste integral sem microdados reais: equidade, join, privacidade e exportação."""
    rng = np.random.default_rng(47)
    for _ in range(70):
        arr = rng.choice(np.array([0., 40., 60., 100., 120., 160., 180., 200.]),
                         size=int(rng.integers(1, 130)))
        hist = Counter(float(x) for x in arr)
        stats = ind45.estatisticas(hist, len(arr))
        assert abs(stats['media'] - arr.mean()) <= .000051
        assert abs(stats['mediana'] - np.median(arr)) <= .000051
        assert abs(stats['q1'] - np.quantile(arr, .25, method='linear')) <= .000051
        assert abs(stats['q3'] - np.quantile(arr, .75, method='linear')) <= .000051
        assert abs(stats['desvio_padrao'] - arr.std(ddof=0)) <= .000051
    assert codigo_acesso('A') == 'A' and codigo_acesso(' b ') == 'B'
    assert codigo_acesso('') == 'SEM_RESPOSTA'
    assert codigo_acesso('C') == 'CODIGO_NAO_RECONHECIDO'
    assert variavel_ano(2019) == 'Q025' and variavel_ano(2024) == 'Q020'
    with tempfile.TemporaryDirectory(prefix='autoteste_ind047_') as temp:
        raiz = Path(temp)
        raw = raiz/'data'/'raw'
        raw.mkdir(parents=True)
        out = raiz/'outputs'/'json'
        out.mkdir(parents=True)
        linhas2019, linhas2024 = [], []
        for pos_uf, uf in enumerate(UFS):
            for k in range(100):
                # A/B com N >= 30 em cada UF; grupo C inválido com N=1 em SP;
                # deve provocar ocultação global do código inválido e complementar.
                codigo = ('C' if uf == 'SP' and k == 99 else
                          'A' if k < 42 else 'B')
                notas = [float(40 + 20*(k % 6)), 80., 100., 120., 140.]
                total = sum(notas)
                base = {
                    'NU_INSCRICAO': str(8000000 + pos_uf*100 + k),
                    'SG_UF_PROVA': uf, 'TP_STATUS_REDACAO': '1',
                    'NU_NOTA_REDACAO': str(total),
                    **{c: str(notas[j]) for j, c in enumerate(NOTAS_COMP)},
                }
                linhas2019.append({**base, 'Q025': codigo})
                linhas2024.append({**base, 'Q020': codigo})
        df19, df24 = pd.DataFrame(linhas2019), pd.DataFrame(linhas2024)
        df19.drop(columns='NU_INSCRICAO').to_csv(
            raw/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        df24[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q020']].iloc[::-1].to_csv(
            raw/'PARTICIPANTES_2024.csv', sep=';', index=False)
        df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].to_csv(
            raw/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)

        # Cria referência com N e médias calculados diretamente dos registros
        # sintéticos, sem derivar N das agregações do IND-047.
        referencia = {'indicator_id': 'IND-045', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano, df in ((2019, df19), (2024, df24)):
            rec = {}
            for geo in ('BR', *UFS):
                parte = df if geo == 'BR' else df.loc[df['SG_UF_PROVA'] == geo]
                n = len(parte)
                media = round(pd.to_numeric(parte['NU_NOTA_REDACAO']).mean(), 4)
                rec[geo] = {
                    'n_pop_socio_valid': n,
                    'categories': [{'suprimido': False, 'n_redacoes': n, 'media': media}],
                }
            referencia['years'][str(ano)] = {
                'status': 'ok', 'n_brasil': len(df), 'recortes': rec,
                'validacao': {'n_soma_competencias_divergente': 0},
            }
            ind45.salvar_json(out/f'dashboard_enem_{ano}.json', {
                'pages': {'socioeconomic': {
                    'school_type_total': {'indicator_id': 'IND-045'},
                    'sentinela': 'nao_apagar'}},
                'quality': {'sentinela': True}, 'meta': {'warnings': []},
            })
        referencia['years']['2025'] = {'status': 'indisponivel'}
        ref_path = out/'IND_045_tipo_escola_nota.json'
        ind45.salvar_json(ref_path, referencia)
        resultado = executar(raiz, raiz, (2019, 2024, 2025), 53, True, False)
        assert resultado['years']['2025']['status'] == 'indisponivel'
        assert resultado['years']['2019']['variavel_origem'] == 'Q025'
        assert resultado['years']['2024']['variavel_origem'] == 'Q020'
        assert resultado['anos_disponiveis'] == [2019, 2024]
        for ano in ('2019', '2024'):
            ano_result = resultado['years'][ano]
            assert ano_result['n_brasil'] == 2700
            for uf in ('BR', *UFS):
                r = ano_result['recortes'][uf]
                assert r['n_pop_socio_valid'] == (2700 if uf == 'BR' else 100)
                assert len(r['categories']) == 4
                assert r['variavel_origem'] == ('Q025' if ano == '2019' else 'Q020')
                assert all(set(c['medidas']) == set(MEDIDAS) for c in r['categories'])
                for cat in r['categories']:
                    if cat['suprimido']:
                        assert cat['n_redacoes'] is None
                        assert cat['percentual_total_validas'] is None
                        assert all(x['media'] is None for x in cat['medidas'].values())
                assert r['comparacao_sim_menos_nao']['C0']['status'] == 'ok'
            assert not ano_result['validacao']['categorias_suprimidas_globalmente']
            dash = json.loads((out/f'dashboard_enem_{ano}.json').read_text())
            assert dash['pages']['socioeconomic']['sentinela'] == 'nao_apagar'
            assert dash['pages']['socioeconomic']['internet_performance']['indicator_id'] == 'IND-047'
            assert dash['quality']['sentinela']
        with (raiz/'outputs'/'indicadores'/'IND_047_internet_desempenho.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            linhas = list(csv.DictReader(fh, delimiter=';'))
        assert len(linhas) == 2 * 28 * 4 * 6
        assert all('NU_INSCRICAO' not in l for l in linhas)
        assert all(not l['media'] and not l['n_redacoes']
                   for l in linhas if l['suprimido'] == 'True')
        # Caso sem supressão e com diferença descritiva realmente calculável.
        df_ab = df19.loc[~((df19['SG_UF_PROVA'] == 'SP') & (df19['Q025'] == 'C'))].copy()
        g = defaultdict(Grupo)
        v = ind45.selecionar_validas(df_ab)
        v['__internet'] = v['Q025']
        acumular(g, v, 2019)
        g = criar_brasil(g)
        ref_ab = json.loads(json.dumps(referencia))
        for geo in ('BR', *UFS):
            ref_ab['years']['2019']['recortes'][geo]['n_pop_socio_valid'] = sum(
                g.get((geo, c), Grupo()).n for c in CATEGORIAS)
            n = ref_ab['years']['2019']['recortes'][geo]['n_pop_socio_valid']
            h = g.get((geo, 'A'), Grupo()).hist['C0'] + g.get((geo, 'B'), Grupo()).hist['C0']
            ref_ab['years']['2019']['recortes'][geo]['categories'] = [
                {'suprimido': False, 'n_redacoes': n,
                 'media': ind45.estatisticas(h, n)['media']}]
        ref_ab['years']['2019']['n_brasil'] = len(df_ab)
        rec_ab, qa = conferir_montar(2019, g, len(df_ab), ref_ab)
        assert not qa['categorias_suprimidas_globalmente']
        assert rec_ab['SP']['comparacao_sim_menos_nao']['C0']['status'] == 'ok'
        # B-A deve coincidir com a diferença independente das médias reais.
        serie = df_ab.loc[df_ab['SG_UF_PROVA'] == 'SP']
        media_a = pd.to_numeric(serie.loc[serie['Q025'] == 'A', 'NU_NOTA_REDACAO']).mean()
        media_b = pd.to_numeric(serie.loc[serie['Q025'] == 'B', 'NU_NOTA_REDACAO']).mean()
        delta = rec_ab['SP']['comparacao_sim_menos_nao']['C0']['diferenca_medias_sim_menos_nao']
        assert abs(delta - round(media_b-media_a, 4)) <= .0001
        assert rec_ab['BR']['comparacao_sim_menos_nao']['C2']['diferenca_medias_sim_menos_nao'] == 0
        # Detecção de N incompatível (não deve gerar resultados válidos).
        ref_errado = json.loads(json.dumps(ref_ab))
        ref_errado['years']['2019']['recortes']['SP']['n_pop_socio_valid'] += 1
        try:
            conferir_montar(2019, g, len(df_ab), ref_errado)
        except ValueError as erro:
            assert 'difere IND-045' in str(erro)
        else:
            raise AssertionError('Divergência com IND-045 não foi detectada.')
        # A ordem e o tamanho dos blocos não podem afetar a junção 2024.
        a, na, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 41)
        b, nb, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                             raw/'COMPETENCIAS_REDACAO_2024.csv', 503)
        assert na == nb == 2700
        assert all(a[ch].n == b[ch].n and a[ch].hist == b[ch].hist for ch in a)
        incompleta = df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].copy()
        incompleta.loc[0, 'NU_INSCRICAO'] = 'NAO_EXISTE'
        incompleta.to_csv(raw/'COMPETENCIAS_INCOMPLETAS.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv',
                     raw/'COMPETENCIAS_INCOMPLETAS.csv', 29)
        except ValueError as erro:
            assert 'sem vínculo' in str(erro)
        else:
            raise AssertionError('Junção faltante não foi rejeitada.')
        # Duplicidade na tabela de participantes deve ser rejeitada.
        repetidos = pd.read_csv(raw/'PARTICIPANTES_2024.csv', sep=';', dtype='string')
        pd.concat([repetidos, repetidos.iloc[[0]]], ignore_index=True).to_csv(
            raw/'PARTICIPANTES_DUPLICADOS_2024.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_DUPLICADOS_2024.csv',
                     raw/'COMPETENCIAS_REDACAO_2024.csv', 257)
        except ValueError as erro:
            assert 'duplicada' in str(erro)
        else:
            raise AssertionError('Inscrição duplicada não foi rejeitada.')
        # Com grupos pequenos em A e B na mesma UF e sem complemento seguro,
        # todas as categorias devem ser suprimidas no ano inteiro.
        pequenos = defaultdict(Grupo)
        for uf in UFS:
            for cat in ('A', 'B'):
                n = 1 if uf == 'SP' else 50
                matriz = np.tile([600., 120., 120., 120., 120., 120.], (n, 1))
                pequenos[(uf, cat)].adicionar(matriz)
        pequenos = criar_brasil(pequenos)
        ref_seg = json.loads(json.dumps(referencia))
        for geo in ('BR', *UFS):
            n = sum(pequenos.get((geo, c), Grupo()).n for c in CATEGORIAS)
            ref_seg['years']['2019']['recortes'][geo] = {
                'n_pop_socio_valid': n,
                'categories': [{'suprimido': False, 'n_redacoes': n, 'media': 600.}],
            }
        n_seg = sum(pequenos.get(('BR', c), Grupo()).n for c in CATEGORIAS)
        ref_seg['years']['2019']['n_brasil'] = n_seg
        rec_seg, qa_seg = conferir_montar(2019, pequenos, n_seg, ref_seg)
        assert not qa_seg['categorias_suprimidas_globalmente']
        assert all(not cat['suprimido'] and cat['n_redacoes'] == 1
                   for cat in rec_seg['SP']['categories'] if cat['codigo_acesso'] in ('A','B'))
        assert all(v['diferenca_medias_sim_menos_nao'] is not None
                   for v in rec_seg['SP']['comparacao_sim_menos_nao'].values())
        assert not list(raiz.rglob('*.bak'))
    log('AUTOTESTE IND-047 APROVADO: médias/quantis, Q025/Q020, comparação B-A, '
        'supressão complementar, população/IND-045, join 2024, CSV/JSON, 2025 e dashboards.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-047: Internet × desempenho')
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
        parser.error('--anos deve conter valores de 2019 a 2025.')
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
        print(f'ERRO IND-047: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
