#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-048 — Computador/notebook no domicílio × desempenho da redação.

Projeto Integrador IV — UNIVESP | Catálogo ENEM 2019–2025 v2.
Rota JSON: pages.socioeconomic.computer_performance.
População POP_SOCIO_VALID, conferida com IND-045 por UF/BR.

2019–2023: Q024 (computador), mesma linha em MICRODADOS_ENEM_<ano>.csv.
2024: Q021 (computador/notebook), em PARTICIPANTES_2024.csv; união
      com COMPETENCIAS_REDACAO_2024.csv por NU_INSCRICAO única.
2025: sem chave pública que permita associar participantes a notas: indisponível.
Códigos oficiais em ambas as edições: A=Não, B=Um, C=Dois,
D=Três, E=Quatro ou mais; faltantes e inválidos separados.

Para cada ano × UF/BR × categoria × medida (C0..C5), publica N,
percentual, média, mediana, quartis HF7 exatos, IQR e DP populacional.
Não interpreta diferenças entre categorias como causalidade e não afirma
que 'computador' e 'computador/notebook' sejam formulações idênticas.

Privacidade: supressão primária N=1..29 por categoria em todas as UFs
no ano + categoria complementar, ou todas as categorias se necessário.
Resultados 'draft' até validação real e revisão cruzada de privacidade.

Execução (na raiz do projeto):
  python src/indicadores/IND_048_computador_desempenho.py --autoteste
  python src/indicadores/IND_048_computador_desempenho.py --anos 2024 --sobrescrever
  python src/indicadores/IND_048_computador_desempenho.py --sobrescrever

Requer src/indicadores/IND_045_tipo_escola_nota.py e
outputs/json/IND_045_tipo_escola_nota.json como referência real.
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
    'A': 'Não possui computador',
    'B': 'Um computador',
    'C': 'Dois computadores',
    'D': 'Três computadores',
    'E': 'Quatro ou mais computadores',
    'SEM_RESPOSTA': 'Não informou',
    'CODIGO_NAO_RECONHECIDO': 'Código não reconhecido',
}
LIMIAR = ind45.LIMIAR
CAMPOS_CSV = (
    'ano', 'uf', 'variavel_origem', 'conceito', 'codigo_computador',
    'descricao_categoria', 'ordem', 'medida', 'n_redacoes', 'media',
    'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao',
    'percentual_total_validas', 'suprimido', 'motivo_supressao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def conceito_ano(ano: int) -> str:
    return ('Quantidade de computadores no domicílio (Q024)'
            if ano < 2024 else
            'Quantidade de computadores/notebooks no domicílio (Q021)')


def variavel_ano(ano: int) -> str:
    return 'Q024' if ano < 2024 else 'Q021'


def codigo_computador(valor: Any) -> str:
    codigo = '' if valor is None else str(valor).strip().upper()
    if codigo in ('', '<NA>', 'NAN', 'NULL', 'NONE'):
        return 'SEM_RESPOSTA'
    return codigo if codigo in 'ABCDE' and len(codigo) == 1 else 'CODIGO_NAO_RECONHECIDO'


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
    codigos = validas['__computador'].map(codigo_computador)
    notas = validas[['__nota_total', *NOTAS_COMP]].to_numpy(dtype='float64')
    indices = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codigos.to_numpy()})
    for (uf, cod), linhas in indices.groupby(['uf', 'codigo'], sort=False).indices.items():
        grupos[(str(uf), str(cod))].adicionar(notas[linhas])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if ano < 2019 or ano > 2023:
        raise ValueError('Q024 para computadores é válido neste indicador apenas em 2019–2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    campos = ['SG_UF_PROVA', 'Q024', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]
    for parte in ind45.ler_blocos(arquivo, campos, bloco):
        validas = ind45.selecionar_validas(parte)
        n_validas += len(validas)
        if not validas.empty:
            validas['__computador'] = validas['Q024']
            acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {
        'metodo': 'mesma_linha', 'variavel_origem': 'Q024',
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
    with tempfile.TemporaryDirectory(prefix='enem_ind048_') as diretorio:
        db = sqlite3.connect(str(Path(diretorio) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes('
                       'id TEXT PRIMARY KEY, uf TEXT NOT NULL, computador TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE validas_vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ind45.ler_blocos(participantes,
                                           ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q021'], bloco):
                ids = identificadores(parte, 'PARTICIPANTES_2024')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                valores = parte['Q021'].astype('string').str.strip().tolist()
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
                    SELECT l.pos, p.uf, p.computador
                    FROM lote AS l JOIN participantes AS p ON p.id = l.id
                ''').fetchall()
                if len(encontrados) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(encontrados)} redações válidas sem vínculo.')
                atributos = [None] * len(ids)
                for pos, uf, computador in encontrados:
                    atributos[pos] = (uf, computador)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [x[0] for x in atributos]
                validas['__computador'] = [x[1] for x in atributos]
                acumular(grupos, validas, 2024)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'variavel_origem': 'Q021',
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
            raise ValueError(f'Categoria de computador inesperada: {cod}')
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
        raise ValueError(f'IND-045/{ano} não disponível para conciliação IND-048.')
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
            raise ValueError(f'{ano}/{geo}: N IND-048 {n} difere IND-045 {n_ref}.')
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
        complementares = [c for c in ('SEM_RESPOSTA', 'CODIGO_NAO_RECONHECIDO', 'E', 'D', 'C', 'B', 'A')
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
                'codigo_computador': codigo, 'descricao_categoria': descricao, 'ordem': ordem,
                'n_redacoes': None if oculto else grupo.n,
                'percentual_total_validas': (None if oculto or not total_geo
                    else round(100 * grupo.n / total_geo, 6)),
                'suprimido': oculto, 'motivo_supressao': motivo,
                'medidas': estat,
            })
        recortes[geo] = {
            'uf': geo, 'population': 'POP_SOCIO_VALID',
            'variavel_origem': variavel_ano(ano), 'conceito': conceito_ano(ano),
            'n_pop_socio_valid': total_geo, 'categories': categorias,
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
                    linhas.append({
                        'ano': int(ano), 'uf': uf, 'variavel_origem': rec['variavel_origem'],
                        'conceito': rec['conceito'],
                        'codigo_computador': cat['codigo_computador'],
                        'descricao_categoria': cat['descricao_categoria'], 'ordem': cat['ordem'],
                        'medida': medida, 'n_redacoes': est['n_redacoes'],
                        'media': est['media'], 'mediana': est['mediana'],
                        'q1': est['q1'], 'q3': est['q3'], 'iqr': est['iqr'],
                        'desvio_padrao': est['desvio_padrao'],
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
            raise ValueError(f'{arquivo.name}: integre IND-045 antes do IND-048.')
        rec = obj['recortes']
        socio['computer_performance'] = {
            'indicator_id': 'IND-048', 'status': 'draft', 'year': ano,
            'population': 'POP_SOCIO_VALID',
            'source_variable': obj['variavel_origem'], 'concept': obj['conceito'],
            'comparability_across_years': 'Q024_computador_2019_2023_vs_Q021_computador_notebook_2024',
            'national': rec['BR'], 'states': {uf: rec[uf] for uf in UFS},
            'method': 'N, percentuais, médias, medianas, quartis, IQR e DP em C0..C5 por A..E',
            'privacy_note': 'Supressão global da categoria anual + complemento; revisão cruzada pendente.',
        }
        documento.setdefault('quality', {})['ind048_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-048: Q024 (computadores, 2019–2023) vs Q021 (computadores/notebooks, 2024); ' \
                 'associação descritiva; supressão de pequenos grupos; revisão cruzada pendente.')
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
    destino_json = saida/'outputs'/'json'/'IND_048_computador_desempenho.json'
    destino_csv = saida/'outputs'/'indicadores'/'IND_048_computador_desempenho.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-048 já existe. Use --sobrescrever.')
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
        if doc.get('indicator_id') != 'IND-048':
            raise ValueError('JSON existente pertence a outro indicador.')
        anteriores = doc.get('years', {})
    todos = dict(anteriores)
    novos = {}
    for ano in anos:
        log(f'IND-048 | {ano}: computador × nota total e C1–C5...')
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
        'indicator_id': 'IND-048', 'titulo': 'Computador × desempenho na redação',
        'population': 'POP_SOCIO_VALID', 'status': 'draft',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, obj in todos.items() if obj.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'population': 'TP_STATUS_REDACAO=1, nota total 0..1000 e C1..C5 0..200',
            '2019_2023_variable': 'Q024 (computadores no domicílio)',
            '2024_variable': 'Q021 (computadores/notebooks no domicílio)',
            'categories': CATEGORIAS,
            'comparability': ('Códigos A-E correspondem a quantidades, mas a pergunta de 2024 '
                              'inclui notebook explicitamente; não afirmar equivalência integral.'),
            'statistics': 'N, percentual, média, mediana, Q1/Q3/IQR, DP populacional em C0..C5',
            'quantiles': 'Hyndman–Fan tipo 7 em histogramas exatos',
            'effect': 'Não se estimam efeitos causais nem contraste B-A binário.',
            'reference': 'IND-045 para N por UF/BR, média quando publicável e divergências',
            'join_2024': 'NU_INSCRICAO única; pareamento obrigatório de redações válidas',
            '2025': 'indisponível: sem chave pública comum entre questionário e notas',
            'privacy': 'categoria pequena (<30) oculta em BR/UF no ano inteiro + complementar; draft',
            'notes': [
                'C0 corresponde à nota total (0 a 1000); C1..C5 à escala 0..200.',
                'A = nenhum; B = um; C = dois; D = três; E = quatro ou mais.',
                'Quantidades são categorias ordinais; E é uma categoria aberta (4+).',
                'A associação não controla fatores de confusão como renda e escolaridade.',
                'Anos representam participações no exame, não pessoas únicas.',
                'UF representa local da prova, não necessariamente residência.',
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
        log(f'  Dashboard {arquivo.name}: bloco computer_performance integrado.')
    log(f'IND-048 concluído em draft. JSON: {destino_json} | CSV: {destino_csv}')
    return modulo


def autoteste() -> None:
    """Autoteste integral: estatísticas, domínios, pareamento, segurança e saídas."""
    rng = np.random.default_rng(48)
    for _ in range(70):
        arr = rng.choice(np.array([0., 40., 60., 100., 120., 160., 180., 200.]),
                         size=int(rng.integers(1, 130)))
        hist = Counter(float(x) for x in arr)
        est = ind45.estatisticas(hist, len(arr))
        assert abs(est['media']-arr.mean()) <= .000051
        assert abs(est['mediana']-np.median(arr)) <= .000051
        assert abs(est['q1']-np.quantile(arr, .25, method='linear')) <= .000051
        assert abs(est['q3']-np.quantile(arr, .75, method='linear')) <= .000051
        assert abs(est['desvio_padrao']-arr.std(ddof=0)) <= .000051
    for cod in 'ABCDE':
        assert codigo_computador(f' {cod.lower()} ') == cod
    for val in (None, '', '  ', pd.NA, '<NA>', 'NAN'):
        assert codigo_computador(val) == 'SEM_RESPOSTA'
    for val in ('F', '0', '5', 'sim', 'não'):
        assert codigo_computador(val) == 'CODIGO_NAO_RECONHECIDO'
    assert variavel_ano(2019) == 'Q024' and variavel_ano(2024) == 'Q021'
    assert len(CATEGORIAS) == 7
    with tempfile.TemporaryDirectory(prefix='autoteste_ind048_') as temp:
        raiz = Path(temp)
        raw = raiz/'data'/'raw'
        raw.mkdir(parents=True)
        out = raiz/'outputs'/'json'
        out.mkdir(parents=True)
        linhas2019, linhas2024 = [], []
        for pos_uf, uf in enumerate(UFS):
            for k in range(180):
                codigo = 'ABCDE'[k % 5]
                # Dois grupos pequenos SP: códigos não reconhecidos e não resposta.
                # Complemento E continua com pelo menos 30 em SP.
                if uf == 'SP' and k == 178:
                    codigo = 'Z'
                if uf == 'SP' and k == 179:
                    codigo = ''
                notas = [float(40 + 20*(k % 6)), 80., 100., 120., 140.]
                total = sum(notas)
                base_linha = {
                    'NU_INSCRICAO': str(8000000 + pos_uf*180 + k),
                    'SG_UF_PROVA': uf, 'TP_STATUS_REDACAO': '1',
                    'NU_NOTA_REDACAO': str(total),
                    **{c: str(notas[j]) for j, c in enumerate(NOTAS_COMP)},
                }
                linhas2019.append({**base_linha, 'Q024': codigo})
                linhas2024.append({**base_linha, 'Q021': codigo})
        df19, df24 = pd.DataFrame(linhas2019), pd.DataFrame(linhas2024)
        df19.drop(columns='NU_INSCRICAO').to_csv(
            raw/'MICRODADOS_ENEM_2019.csv', sep=';', index=False)
        df24[['NU_INSCRICAO', 'SG_UF_PROVA', 'Q021']].iloc[::-1].to_csv(
            raw/'PARTICIPANTES_2024.csv', sep=';', index=False)
        df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].to_csv(
            raw/'COMPETENCIAS_REDACAO_2024.csv', sep=';', index=False)

        referencia = {'indicator_id': 'IND-045', 'population': 'POP_SOCIO_VALID', 'years': {}}
        for ano, df in ((2019, df19), (2024, df24)):
            rec = {}
            for geo in ('BR', *UFS):
                parte = df if geo == 'BR' else df.loc[df['SG_UF_PROVA'] == geo]
                n = len(parte)
                rec[geo] = {
                    'n_pop_socio_valid': n,
                    'categories': [{'suprimido': False, 'n_redacoes': n,
                                    'media': round(pd.to_numeric(parte['NU_NOTA_REDACAO']).mean(), 4)}],
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
        ind45.salvar_json(out/'IND_045_tipo_escola_nota.json', referencia)
        result = executar(raiz, raiz, (2019, 2024, 2025), 53, True, False)
        assert result['indicator_id'] == 'IND-048'
        assert result['years']['2025']['status'] == 'indisponivel'
        assert result['years']['2019']['variavel_origem'] == 'Q024'
        assert result['years']['2024']['variavel_origem'] == 'Q021'
        assert result['anos_disponiveis'] == [2019, 2024]
        for ano in ('2019', '2024'):
            obj = result['years'][ano]
            assert obj['n_brasil'] == 4860
            assert obj['validacao']['n_por_uf_e_brasil_conferido']
            assert obj['validacao']['divergencias_conferidas_com_ind045']
            motivos = obj['validacao']['categorias_suprimidas_globalmente']
            assert motivos == {
                'SEM_RESPOSTA': 'primaria_grupo_pequeno_em_alguma_uf',
                'CODIGO_NAO_RECONHECIDO': 'primaria_grupo_pequeno_em_alguma_uf',
                'E': 'complementar_contra_inferencia_por_totais',
            }, motivos
            for uf in ('BR', *UFS):
                rec = obj['recortes'][uf]
                assert rec['n_pop_socio_valid'] == (4860 if uf == 'BR' else 180)
                assert rec['variavel_origem'] == ('Q024' if ano == '2019' else 'Q021')
                assert len(rec['categories']) == 7
                assert all(set(c['medidas']) == set(MEDIDAS) for c in rec['categories'])
                assert 'comparacao_sim_menos_nao' not in rec
                for cat in rec['categories']:
                    if cat['suprimido']:
                        assert cat['n_redacoes'] is None
                        assert cat['percentual_total_validas'] is None
                        assert all(x['media'] is None for x in cat['medidas'].values())
            dash = json.loads((out/f'dashboard_enem_{ano}.json').read_text())
            assert dash['pages']['socioeconomic']['sentinela'] == 'nao_apagar'
            assert dash['pages']['socioeconomic']['computer_performance']['indicator_id'] == 'IND-048'
            assert dash['quality']['sentinela']
        with (raiz/'outputs'/'indicadores'/'IND_048_computador_desempenho.csv').open(
                encoding='utf-8-sig', newline='') as fh:
            linhas = list(csv.DictReader(fh, delimiter=';'))
        assert len(linhas) == 2 * 28 * 7 * 6
        assert all('NU_INSCRICAO' not in linha for linha in linhas)
        assert all(not lin['media'] and not lin['n_redacoes']
                   for lin in linhas if lin['suprimido'] == 'True')

        # Caso sem supressão: médias/medianas comparadas diretamente com o pandas.
        df_limpo = df19.loc[~((df19['SG_UF_PROVA'] == 'SP') &
                            (df19['Q024'].isin(['', 'Z'])))].copy()
        grupos = defaultdict(Grupo)
        validas = ind45.selecionar_validas(df_limpo)
        validas['__computador'] = validas['Q024']
        acumular(grupos, validas, 2019)
        grupos = criar_brasil(grupos)
        ref_ok = json.loads(json.dumps(referencia))
        for geo in ('BR', *UFS):
            n = sum(grupos.get((geo, c), Grupo()).n for c in CATEGORIAS)
            ref_ok['years']['2019']['recortes'][geo]['n_pop_socio_valid'] = n
            total_hist = Counter()
            for c in CATEGORIAS:
                total_hist.update(grupos.get((geo,c),Grupo()).hist['C0'])
            ref_ok['years']['2019']['recortes'][geo]['categories'] = [
                {'suprimido': False, 'n_redacoes': n,
                 'media': ind45.estatisticas(total_hist, n)['media']}]
        ref_ok['years']['2019']['n_brasil'] = len(df_limpo)
        rec_ok, qa_ok = conferir_montar(2019, grupos, len(df_limpo), ref_ok)
        assert not qa_ok['categorias_suprimidas_globalmente']
        for categoria in 'ABCDE':
            grupo_sp = df_limpo.loc[(df_limpo['SG_UF_PROVA'] == 'SP') &
                                   (df_limpo['Q024'] == categoria)]
            notas = pd.to_numeric(grupo_sp['NU_NOTA_REDACAO'])
            cat = next(c for c in rec_ok['SP']['categories']
                       if c['codigo_computador'] == categoria)
            assert abs(cat['medidas']['C0']['media'] - notas.mean()) <= .00005
            assert abs(cat['medidas']['C0']['mediana'] - notas.median()) <= .00005
        ref_err = json.loads(json.dumps(ref_ok))
        ref_err['years']['2019']['recortes']['SP']['n_pop_socio_valid'] += 1
        try:
            conferir_montar(2019, grupos, len(df_limpo), ref_err)
        except ValueError as erro:
            assert 'difere IND-045' in str(erro)
        else:
            raise AssertionError('Divergência N com IND-045 não foi detectada.')

        # Pareamento robusto para blocos distintos.
        a, na, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                              raw/'COMPETENCIAS_REDACAO_2024.csv', 41)
        b, nb, _ = ler_2024(raw/'PARTICIPANTES_2024.csv',
                              raw/'COMPETENCIAS_REDACAO_2024.csv', 503)
        assert na == nb == 4860
        assert all(a[ch].n == b[ch].n and a[ch].hist == b[ch].hist for ch in a)
        incompleta = df24[['NU_INSCRICAO', 'TP_STATUS_REDACAO', *CAMPOS_NOTAS]].copy()
        incompleta.loc[0, 'NU_INSCRICAO'] = 'NAO_EXISTE'
        incompleta.to_csv(raw/'COMPETENCIAS_INCOMPLETAS.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_2024.csv', raw/'COMPETENCIAS_INCOMPLETAS.csv', 83)
        except ValueError as erro:
            assert 'sem vínculo' in str(erro)
        else:
            raise AssertionError('Chave sem vínculo não foi rejeitada.')
        repetidos = pd.read_csv(raw/'PARTICIPANTES_2024.csv', sep=';', dtype='string')
        pd.concat([repetidos, repetidos.iloc[[0]]], ignore_index=True).to_csv(
            raw/'PARTICIPANTES_DUPLICADOS_2024.csv', sep=';', index=False)
        try:
            ler_2024(raw/'PARTICIPANTES_DUPLICADOS_2024.csv',
                     raw/'COMPETENCIAS_REDACAO_2024.csv', 181)
        except ValueError as erro:
            assert 'duplicada' in str(erro)
        else:
            raise AssertionError('Duplicidade em participantes não foi rejeitada.')

        # Se todas categorias são pequenas na UF, não existe complemento >=30.
        pequenos = defaultdict(Grupo)
        for uf in UFS:
            for cod in CATEGORIAS:
                n = 1 if uf == 'SP' else 50
                arr = np.tile([600., 120., 120., 120., 120., 120.], (n, 1))
                pequenos[(uf, cod)].adicionar(arr)
        pequenos = criar_brasil(pequenos)
        ref_priv = json.loads(json.dumps(referencia))
        for geo in ('BR', *UFS):
            n = sum(pequenos.get((geo, c), Grupo()).n for c in CATEGORIAS)
            ref_priv['years']['2019']['recortes'][geo] = {
                'n_pop_socio_valid': n,
                'categories': [{'suprimido': False, 'n_redacoes': n, 'media': 600.}],
            }
        n_priv = sum(pequenos.get(('BR', c), Grupo()).n for c in CATEGORIAS)
        ref_priv['years']['2019']['n_brasil'] = n_priv
        rec_priv, qa_priv = conferir_montar(2019, pequenos, n_priv, ref_priv)
        assert len(qa_priv['categorias_suprimidas_globalmente']) == len(CATEGORIAS)
        assert all(cat['suprimido'] for cat in rec_priv['SP']['categories'])
        assert not list(raiz.rglob('*.bak'))
    log('AUTOTESTE IND-048 APROVADO: Q024/Q021, 7 categorias, estatísticas, '
        'privacidade, conciliação IND-045, join 2024, CSV/JSON, dashboards e 2025.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-048: Computador × desempenho')
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
        print(f'ERRO IND-048: {erro}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
