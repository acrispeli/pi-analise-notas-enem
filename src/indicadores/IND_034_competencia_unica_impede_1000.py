#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-034 — Competência única que impede 1000 | ENEM 2019–2025.

Catálogo de Indicadores ENEM 2019–2025 v2 / Projeto Integrador IV — UNIVESP.

POP_NEAR: TP_STATUS_REDACAO=1, 0 <= NU_NOTA_REDACAO <= 1000,
          900 <= NU_NOTA_REDACAO <= 980 (ambos inclusivos).

Evento IND-034: EXATAMENTE UMA das cinco NU_NOTA_COMP1..5 < 200.
Um caso assim é classificado pela única competência com desconto. Os casos
com duas ou mais competências abaixo de 200 NÃO entram no numerador.

NÃO derivar do IND-031/032/033: os agregados marginais não informam quais
competências têm desconto na MESMA redação. Este código lê microdados.

2019–23: MICRODADOS_ENEM_<ano>.csv, com status, nota, C1..C5 e UF na mesma linha.
2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv;
      junção exclusivamente por NU_INSCRICAO usando SQLite temporário.
2025: RESULTADOS_2025.csv, se disponível, com as mesmas colunas necessárias.

Gera:
  outputs/json/IND_034_competencia_unica_impede_1000.json
  outputs/indicadores/IND_034_competencia_unica_impede_1000.csv
  outputs/json/dashboard_enem_<ano>.json (pages.high_performance.single_blocker)

Não cria .bak; escrita atômica por arquivo. Resultados draft: revisão acadêmica
+ revisão de privacidade cruzada antes de divulgação pública.

Exemplos:
  python src/indicadores/IND_034_competencia_unica_impede_1000.py --anos 2024 --sobrescrever
  python src/indicadores/IND_034_competencia_unica_impede_1000.py --sobrescrever
  python src/indicadores/IND_034_competencia_unica_impede_1000.py --autoteste
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import filecmp
from datetime import datetime, timezone
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
COLUNAS_COMPETENCIAS = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
MIN_N = 1
# Controle cruzado do IND-031/IND-032, por edição; use --sem-controle-populacao
# apenas para ensaios sintéticos, nunca para divulgação dos resultados reais.
POP_NEAR_REFERENCIA = {
    2019: 172_548, 2020: 183_343, 2021: 163_747,
    2022: 197_083, 2023: 288_602, 2024: 291_111,
    2025: 173_533,
}
CAMPOS_CSV = (
    'ano', 'uf', 'competencia', 'n_near', 'n_competencia_unica',
    'n_casos_com_uma_unica_competencia', 'percentual_entre_casos_unicos',
    'percentual_na_pop_near', 'suprimido', 'motivo_supressao',
)


def log(mensagem: str) -> None:
    print(mensagem, flush=True)


def raiz_projeto() -> Path:
    atual = Path(__file__).resolve()
    if atual.parent.name.lower() == 'indicadores' and atual.parent.parent.name.lower() == 'src':
        return atual.parents[2]
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


def ler_blocos(caminho: Path, colunas: list[str], tamanho: int):
    with caminho.open('rb') as arquivo:
        utf8_bom = arquivo.read(3) == b'\xef\xbb\xbf'
    encoding = 'utf-8-sig' if utf8_bom else 'latin-1'
    cabecalho = pd.read_csv(caminho, sep=';', encoding=encoding, nrows=0)
    existentes = {str(c).strip().lstrip('\ufeff') for c in cabecalho.columns}
    faltantes = sorted(set(colunas) - existentes)
    if faltantes:
        raise ValueError(f'{caminho.name}: colunas necessárias ausentes: {faltantes}.')
    with pd.read_csv(caminho, sep=';', encoding=encoding, usecols=colunas,
                     dtype='string', chunksize=tamanho, na_filter=False,
                     keep_default_na=False, low_memory=False) as leitor:
        for bloco in leitor:
            bloco.columns = [str(c).strip().lstrip('\ufeff') for c in bloco.columns]
            yield bloco


def numerico(serie: pd.Series, nome: str) -> np.ndarray:
    texto = serie.astype('string').str.strip().str.replace(',', '.', regex=False)
    valores = pd.to_numeric(texto, errors='coerce').to_numpy(dtype='float64')
    if not np.isfinite(valores).all():
        raise ValueError(f'{nome}: nota vazia, não numérica ou não finita em registro elegível.')
    return valores


def selecionar_near(bloco: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    validas = bloco.loc[bloco['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')].copy()
    n_validas = len(validas)
    if not n_validas:
        return validas, 0
    nota = numerico(validas['NU_NOTA_REDACAO'], 'NU_NOTA_REDACAO')
    if ((nota < 0) | (nota > 1000)).any():
        raise ValueError('NU_NOTA_REDACAO fora de 0..1000 em TP_STATUS_REDACAO=1.')
    validas['__total'] = nota
    near = validas.loc[(nota >= 900) & (nota <= 980)].copy()
    return near, n_validas


def classificar(near: pd.DataFrame) -> np.ndarray:
    """1..5 = única competência com desconto; -1 = duas ou mais; 0 = nenhuma.

    Recusa soma de competências diferente da nota final no universo POP_NEAR.
    Essa checagem não pode ser substituída por uma tolerância ampla nem por
    um filtro silencioso, pois afetaria a definição do indicador.
    """
    if near.empty:
        return np.empty(0, dtype='int8')
    comps = np.column_stack([numerico(near[c], c) for c in COLUNAS_COMPETENCIAS])
    if ((comps < 0) | (comps > 200)).any():
        raise ValueError('Competência fora de 0..200 em POP_NEAR.')
    totais = near['__total'].to_numpy(dtype='float64')
    divergentes = ~np.isclose(comps.sum(axis=1), totais, rtol=0, atol=1e-6)
    if divergentes.any():
        raise ValueError(f'{int(divergentes.sum())} redação(ões) POP_NEAR com '
                         'soma C1..C5 diferente da nota final; investigar fonte.')
    flags = comps < 200
    quantidades = flags.sum(axis=1)
    if (quantidades == 0).any():
        raise ValueError('POP_NEAR contém redação sem qualquer desconto, '
                         'incompatível com soma exata e nota <= 980.')
    return np.where(quantidades == 1,
                    np.argmax(flags, axis=1) + 1, -1).astype('int8')


def novo_contador() -> dict[str, Any]:
    return {'n': 0, 'unicas': [0, 0, 0, 0, 0], 'multiplas': 0}


def acrescentar(contagens: dict, uf: str, classe: int, n: int) -> None:
    if uf not in UFS:
        raise ValueError(f'UF da prova inválida em POP_NEAR: {uf!r}.')
    for destino in ('BR', uf):
        c = contagens[destino]
        c['n'] += int(n)
        if 1 <= classe <= 5:
            c['unicas'][classe - 1] += int(n)
        elif classe == -1:
            c['multiplas'] += int(n)
        else:
            raise ValueError(f'Classe inesperada: {classe}.')


def acumular_near(contagens: dict, near: pd.DataFrame) -> None:
    if near.empty:
        return
    ufs = near['SG_UF_PROVA'].astype('string').str.strip().str.upper().to_numpy()
    if not pd.Series(ufs).isin(UFS).all():
        raise ValueError('SG_UF_PROVA ausente ou inválida em POP_NEAR.')
    classes = classificar(near)
    dados = pd.DataFrame({'uf': ufs, 'classe': classes})
    for (uf, classe), n in dados.groupby(['uf', 'classe'], sort=False).size().items():
        acrescentar(contagens, str(uf), int(classe), int(n))


def contar_mesma_linha(caminho: Path, tamanho: int) -> tuple[dict, int, dict]:
    contagens = defaultdict(novo_contador)
    n_validas = 0
    cols = ['TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', 'SG_UF_PROVA', *COLUNAS_COMPETENCIAS]
    for bloco in ler_blocos(caminho, cols, tamanho):
        near, n = selecionar_near(bloco)
        n_validas += n
        acumular_near(contagens, near)
    return dict(contagens), n_validas, {'metodo': 'mesma_linha'}


def contar_2024(participantes: Path, competencias: Path, tamanho: int) -> tuple[dict, int, dict]:
    contagens = defaultdict(novo_contador)
    with tempfile.TemporaryDirectory(prefix='enem_ind034_') as pasta:
        db = sqlite3.connect(str(Path(pasta) / 'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE near_vistos(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(id TEXT, classe INTEGER)')
            n_participantes = 0
            for bloco in ler_blocos(participantes, ['NU_INSCRICAO', 'SG_UF_PROVA'], tamanho):
                ids = bloco['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = bloco['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(not v for v in ids) or any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    db.executemany('INSERT INTO participantes VALUES (?, ?)', zip(ids, ufs))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from exc
                n_participantes += len(ids)
            db.commit()
            log(f'  2024: {n_participantes:,} inscrições de participantes indexadas.')

            n_validas = 0
            n_near_vinculadas = 0
            cols = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *COLUNAS_COMPETENCIAS]
            for bloco in ler_blocos(competencias, cols, tamanho):
                near, n = selecionar_near(bloco)
                n_validas += n
                if near.empty:
                    continue
                ids = near['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not v for v in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em POP_NEAR.')
                classes = classificar(near)
                try:
                    db.executemany('INSERT INTO near_vistos VALUES (?)', ((v,) for v in ids))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição repetida em POP_NEAR.') from exc
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?, ?)',
                               ((ident, int(classe)) for ident, classe in zip(ids, classes)))
                vinculadas = int(db.execute('''SELECT COUNT(*) FROM lote l
                    INNER JOIN participantes p ON l.id=p.id''').fetchone()[0])
                if vinculadas != len(ids):
                    raise ValueError(f'2024: {len(ids)-vinculadas} redações POP_NEAR '
                                     'sem correspondente na fonte de participantes.')
                for uf, classe, qtd in db.execute('''SELECT p.uf, l.classe, COUNT(*)
                   FROM lote l JOIN participantes p ON l.id=p.id
                   GROUP BY p.uf, l.classe'''):
                    acrescentar(contagens, str(uf), int(classe), int(qtd))
                n_near_vinculadas += vinculadas
                db.commit()
            return dict(contagens), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'n_participantes': n_participantes,
                'n_pop_near_vinculadas': n_near_vinculadas,
                'n_near_sem_correspondencia': 0,
            }
        finally:
            db.close()


def validar_contagens(contagens: dict, ano: int, n_validas: int,
                       controlar_pop: bool) -> None:
    for uf in ('BR', *UFS):
        contagens.setdefault(uf, novo_contador())
        c = contagens[uf]
        if c['n'] != sum(c['unicas']) + c['multiplas']:
            raise ValueError(f'{ano}/{uf}: não fecha a divisão únicos/múltiplos.')
        if 0 < c['n'] < MIN_N:
            raise ValueError(f'{ano}/{uf}: POP_NEAR com N={c["n"]} < {MIN_N}; '
                             'necessária agregação geográfica antes da divulgação.')
    br = contagens['BR']
    if br['n'] > n_validas:
        raise ValueError(f'{ano}: POP_NEAR maior que POP_VALID.')
    if br['n'] != sum(contagens[uf]['n'] for uf in UFS):
        raise ValueError(f'{ano}: POP_NEAR do Brasil não fecha com 27 UFs.')
    for i, cod in enumerate(COMPETENCIAS):
        if br['unicas'][i] != sum(contagens[uf]['unicas'][i] for uf in UFS):
            raise ValueError(f'{ano}/{cod}: Brasil não fecha com UFs.')
    if br['multiplas'] != sum(contagens[uf]['multiplas'] for uf in UFS):
        raise ValueError(f'{ano}: casos de múltiplas competências não fecham.')
    if controlar_pop and br['n'] != POP_NEAR_REFERENCIA[ano]:
        raise ValueError(f'{ano}: n_near={br["n"]:,} difere do controle '
                         f'{POP_NEAR_REFERENCIA[ano]:,} (IND-031/032).')


def calcular_supressoes(contagens: dict) -> tuple[dict[tuple[str, int], str], dict]:
    """Proteção primária + complementar de linhas/colunas para evento único.

    Não disponibiliza n_unicos da UF se alguma classe estiver oculta. Assim,
    nenhuma contagem pequena pode ser obtida subtraindo-se C1..C5 de n_unicos.
    Se uma UF tiver classe oculta, outra UF deve ter a MESMA classe oculta,
    impedindo n_BR - soma(n_ufs) de revelar o valor. Quando não for possível,
    a classe nacional também é oculta. Revisão cruzada permanece necessária.
    """
    mascaras: dict[tuple[str, int], str] = {}
    primarias = 0
    secundarias = 0
    for geo in ('BR', *UFS):
        c = contagens[geo]
        for i, numero in enumerate(c['unicas']):
            if 0 < numero < MIN_N:
                mascaras[(geo, i)] = 'primaria_n_1_a_29'
                primarias += 1
        # Protege complemento pequeno (casos com 2+ descontos), se houver.
        # Como n_near é publicável por outros indicadores, ocultar também duas
        # categorias positivas é necessário para que n_multiplas não seja deduzido.
        if 0 < c['multiplas'] < MIN_N:
            candidatas = sorted(range(5), key=lambda i: c['unicas'][i], reverse=True)
            for i in candidatas[:2]:
                if (geo, i) not in mascaras:
                    mascaras[(geo, i)] = 'complementar_multiplo_pequeno'
                    secundarias += 1
    # O complemento geográfico deve ser aplicado por competência; não vazar
    # o valor através da igualdade total nacional = soma dos 27 estados.
    for i in range(5):
        ocultas = [uf for uf in UFS if (uf, i) in mascaras]
        if len(ocultas) == 1 and ('BR', i) not in mascaras:
            elegiveis = [uf for uf in UFS if (uf, i) not in mascaras
                         and contagens[uf]['unicas'][i] >= MIN_N]
            if elegiveis:
                outra = max(elegiveis, key=lambda uf: contagens[uf]['unicas'][i])
                mascaras[(outra, i)] = 'complementar_geografica'
                secundarias += 1
            else:
                mascaras[('BR', i)] = 'complementar_brasil'
                secundarias += 1
    return mascaras, {
        'celulas_primarias_suprimidas': primarias,
        'celulas_complementares_suprimidas': secundarias,
        'celulas_suprimidas': len(mascaras),
        'limiar_n': MIN_N,
        'revisao_privacidade_cruzada_pendente': True,
    }


def montar_recortes(contagens: dict, mascaras: dict) -> dict:
    recortes = {}
    # Limite nacional depende dos recortes estaduais, portanto preservamos
    # n_single BR apenas quando não há classes nacionais ocultas e nenhum
    # complemento regional pequeno passível de reconstrução por diferença.
    complemento_uf_pequeno = any(0 < contagens[uf]['multiplas'] < MIN_N for uf in UFS)
    for uf in ('BR', *UFS):
        bruto = contagens[uf]
        n = bruto['n']
        n_single = sum(bruto['unicas'])
        tem_mascara = any((uf, i) in mascaras for i in range(5))
        n_single_publico = None if (tem_mascara or (0 < n_single < MIN_N)
                                    or (uf == 'BR' and complemento_uf_pequeno)) else n_single
        itens = []
        for i, cod in enumerate(COMPETENCIAS):
            motivo = mascaras.get((uf, i))
            ocultar = motivo is not None
            qtd = bruto['unicas'][i]
            itens.append({
                'competencia': cod,
                'n_competencia_unica': None if ocultar else qtd,
                'percentual_entre_casos_unicos': (
                    None if ocultar or not n_single_publico else round(100 * qtd / n_single_publico, 6)),
                'percentual_na_pop_near': (
                    None if ocultar or not n else round(100 * qtd / n, 6)),
                'suprimido': ocultar,
                'motivo_supressao': motivo,
            })
        recortes[uf] = {
            'uf': uf,
            'populacao': 'POP_NEAR',
            'intervalo_nota': [900, 980],
            'n_near': n,
            'n_casos_com_uma_unica_competencia': n_single_publico,
            'percentual_casos_unicos_na_pop_near': (
                None if n_single_publico is None or not n else round(100 * n_single_publico / n, 6)),
            'resumo_competencias': itens,
            'status_publicacao': 'revisao_academica_e_privacidade_cruzada_pendente',
            'sem_dados_individuais': True,
        }
    return recortes


def comparar_ind031(pasta_saida: Path, ano: int, contagens: dict,
                    n_validas: int) -> str:
    caminho = pasta_saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
    if not caminho.exists():
        return 'nao_verificado_dashboard_ausente'
    painel = carregar_json(caminho)
    hp = painel.get('pages', {}).get('high_performance', {})
    if not isinstance(hp, dict):
        raise ValueError(f'{ano}: pages.high_performance inválido.')
    bloco = hp.get('loss_by_competency')
    if not isinstance(bloco, dict) or bloco.get('indicator_id') != 'IND-031':
        return 'nao_verificado_ind031_ausente'
    if bloco['brasil']['n_near'] != contagens['BR']['n']:
        raise ValueError(f'{ano}: POP_NEAR BR incompatível com IND-031.')
    itens = {x['uf']: x for x in bloco.get('by_uf', [])}
    if set(itens) != set(UFS):
        raise ValueError(f'{ano}: IND-031 não contém as 27 UFs.')
    for uf in UFS:
        if itens[uf]['n_near'] != contagens[uf]['n']:
            raise ValueError(f'{ano}/{uf}: POP_NEAR incompatível com IND-031.')
    n_referencia = painel.get('pages', {}).get('overview', {}).get('kpis', {}).get('valid_essays')
    if n_referencia is not None and n_referencia != n_validas:
        raise ValueError(f'{ano}: total POP_VALID difere do dashboard.')
    return 'aprovado'


def carregar_json(caminho: Path) -> dict:
    with caminho.open('r', encoding='utf-8-sig') as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f'{caminho}: JSON precisa conter um objeto.')
    return obj


def salvar_json(caminho: Path, conteudo: Any) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent,
                                         prefix=caminho.name + '.', suffix='.tmp',
                                         delete=False) as f:
            temporario = Path(f.name)
            json.dump(conteudo, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        os.replace(temporario, caminho)
    finally:
        if temporario:
            temporario.unlink(missing_ok=True)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name + '.',
                                         suffix='.tmp', delete=False) as f:
            temporario = Path(f.name)
            escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=';', extrasaction='ignore')
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(temporario, caminho)
    finally:
        if temporario:
            temporario.unlink(missing_ok=True)


def atualizar_dashboards(saida: Path, anos: dict[str, dict]) -> None:
    for ano_txt, dados in sorted(anos.items()):
        if dados['status'] != 'ok':
            continue
        ano = int(ano_txt)
        caminho = saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.exists():
            log(f'  Dashboard {ano} ausente; integração ignorada.')
            continue
        painel = carregar_json(caminho)
        hp = painel.get('pages', {}).get('high_performance')
        if not isinstance(hp, dict):
            raise ValueError(f'{caminho.name}: falta pages.high_performance.')
        recortes = dados['recortes']
        hp['single_blocker'] = {
            'indicator_id': 'IND-034',
            'population': 'POP_NEAR',
            'method': 'exatamente uma NU_NOTA_COMPi < 200 por redação, nota em [900,980]',
            'year': ano,
            'status': 'draft',
            'brasil': recortes['BR'],
            'by_uf': [recortes[uf] for uf in UFS],
            'privacy_note': ('Supressão primária e complementar nos recortes; '
                             'não publicar sem revisão cruzada com outros indicadores.'),
        }
        hp['status'] = 'partial'
        hp['reason'] = ('IND-034 disponível em fase draft; demais indicadores de alto '
                        'desempenho e revisão acadêmica/privacidade pendentes.')
        painel.setdefault('quality', {})['ind034_validation'] = {
            'status': 'ok_agregados',
            'population': 'POP_NEAR',
            'n_near_brasil': recortes['BR']['n_near'],
            'soma_27_ufs_igual_brasil': True,
            'casos_com_uma_competencia_ou_varias_fecham_pop_near': True,
            'soma_competencias_confere_com_nota_na_pop_near': True,
            'controle_ind031': dados['controle_ind031'],
            **dados['privacidade'],
            'revisao_academica_e_privacidade_cruzada_pendente': True,
        }
        avisos = painel.setdefault('meta', {}).setdefault('warnings', [])
        aviso = ('IND-034: competência única que impede 1000 em POP_NEAR; '
                 'células pequenas e complementares ocultas; revisão cruzada pendente.')
        if aviso not in avisos:
            avisos.append(aviso)
        salvar_json(caminho, painel)
        log(f'  Dashboard {ano} atualizado (sem arquivo .bak).')


def executar(base: Path, saida: Path, anos: tuple[int, ...], tamanho: int,
             sobrescrever: bool, somente_modulo: bool,
             sem_controle_populacao: bool, exigir_2025: bool,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    dir_json = saida / 'outputs' / 'json'
    destino_json = dir_json / 'IND_034_competencia_unica_impede_1000.json'
    destino_csv = saida / 'outputs' / 'indicadores' / 'IND_034_competencia_unica_impede_1000.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-034 já existe. Use --sobrescrever para regenerar.')
    nomes: set[str] = set()
    for ano in anos:
        if ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
        else:
            nomes.add('RESULTADOS_2025.CSV')
    fontes = localizar_fontes(base, nomes, fontes_explicitas)
    faltantes = nomes - set(fontes)
    permissao_ausente = {'RESULTADOS_2025.CSV'} if not exigir_2025 else set()
    faltas_graves = sorted(faltantes - permissao_ausente)
    if faltas_graves:
        raise FileNotFoundError('Fontes necessárias ausentes: '
                                + ', '.join(faltas_graves) + '. Use --base para informar a pasta.')

    anteriores: dict[str, dict] = {}
    if sobrescrever and destino_json.exists():
        antigo = carregar_json(destino_json)
        if antigo.get('indicator_id') != 'IND-034':
            raise ValueError('Saída JSON existente não pertence ao IND-034.')
        anteriores = dict(antigo.get('years', {}))
    dados_anos = dict(anteriores)
    processados: dict[str, dict] = {}
    for ano in anos:
        log(f'IND-034 | {ano}: classificando descontos únicos em POP_NEAR...')
        if ano == 2025 and 'RESULTADOS_2025.CSV' not in fontes:
            indisponivel = {
                'ano': ano,
                'status': 'indisponivel',
                'reason': 'RESULTADOS_2025.csv ausente; não é possível conhecer descontos conjuntos.',
                'recortes': {},
            }
            dados_anos[str(ano)] = processados[str(ano)] = indisponivel
            log('  2025 indisponível: não foram estimadas contagens ou proporções.')
            continue
        if ano == 2024:
            contagens, n_validas, diagnostico = contar_2024(
                fontes['PARTICIPANTES_2024.CSV'],
                fontes['COMPETENCIAS_REDACAO_2024.CSV'], tamanho)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            chave = (f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023
                     else 'RESULTADOS_2025.CSV')
            contagens, n_validas, diagnostico = contar_mesma_linha(fontes[chave], tamanho)
            fonte = fontes[chave].name
        validar_contagens(contagens, ano, n_validas, not sem_controle_populacao)
        controle = comparar_ind031(saida, ano, contagens, n_validas)
        mascaras, qa = calcular_supressoes(contagens)
        recortes = montar_recortes(contagens, mascaras)
        if (diagnostico.get('n_pop_near_vinculadas', contagens['BR']['n'])
                != contagens['BR']['n']):
            raise ValueError(f'{ano}: nem todas as redações POP_NEAR foram associadas à UF.')
        resultado = {
            'ano': ano,
            'status': 'ok',
            'fonte': fonte,
            'population': 'POP_NEAR',
            'n_validas_brasil': n_validas,
            'n_near_brasil': contagens['BR']['n'],
            'diagnostico_fonte': diagnostico,
            'controle_ind031': controle,
            'privacidade': qa,
            'recortes': recortes,
        }
        dados_anos[str(ano)] = processados[str(ano)] = resultado
        log(f'  N_near={contagens["BR"]["n"]:,}; '
            f'contagens de classes ocultas={qa["celulas_suprimidas"]}; '
            f'IND-031={controle}.')

    linhas: list[dict] = []
    for chave, ano_obj in sorted(dados_anos.items(), key=lambda par: int(par[0])):
        if ano_obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = ano_obj['recortes'][uf]
            for item in rec['resumo_competencias']:
                linhas.append({
                    'ano': int(chave), 'uf': uf,
                    'n_near': rec['n_near'],
                    'n_casos_com_uma_unica_competencia': rec['n_casos_com_uma_unica_competencia'],
                    **item,
                })
    modulo = {
        'indicator_id': 'IND-034',
        'titulo': 'Competência única que impede 1000',
        'status': 'draft',
        'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': sorted(set(int(y) for y in anos)),
        'anos_disponiveis': sorted(int(y) for y, obj in dados_anos.items() if obj.get('status') == 'ok'),
        'population': 'POP_NEAR',
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'selection': 'TP_STATUS_REDACAO=1; nota válida em [0,1000]; POP_NEAR=[900,980] inclusivo',
            'rule': 'filtrar redações com exatamente um Ci<200; contar qual competência',
            'denominator_1': 'casos com exatamente uma competência <200 no mesmo ano/UF',
            'denominator_2': 'total de redações em POP_NEAR no mesmo ano/UF',
            'mutually_exclusive': True,
            'excludes': 'redações com duas ou mais competências <200',
            'uses_raw_microdata': True,
            'privacy': ('suprimir categorias de 1 a 29 e aplicar complemento geográfico; '
                        'ocultar denominadores quando permitirem reidentificação por subtração'),
            'no_backup': True,
            'cautions': [
                'Uma competência única abaixo de 200 não equivale a afirmar erro do avaliador.',
                'As porcentagens entre casos únicos somam 100% apenas nos recortes totalmente divulgáveis.',
                'A UF corresponde ao local da prova, não necessariamente à residência.',
                '2025 exige RESULTADOS_2025.csv com status, nota final, C1–C5 e UF.',
                'Revisão acadêmica e avaliação de privacidade cruzada ainda necessárias.',
            ],
        },
        'years': dados_anos,
    }
    salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas)
    log(f'JSON: {destino_json}\nCSV: {destino_csv}')
    if not somente_modulo:
        atualizar_dashboards(saida, processados)
    log('IND-034 finalizado. Resultados permanecem em status draft.')
    return modulo


def autoteste() -> None:
    """Verifica classificação, caso sem desconto, erro de soma e supressão."""
    entradas = [
        # 980 pontos, desconto somente em C1
        [180, 200, 200, 200, 200],
        # 960 pontos, desconto somente em C3
        [200, 200, 160, 200, 200],
        # 960 pontos, duas competências com desconto
        [180, 200, 180, 200, 200],
        # 900 pontos, desconto somente em C5
        [200, 200, 200, 200, 100],
    ]
    quadro = pd.DataFrame(entradas, columns=COLUNAS_COMPETENCIAS)
    quadro['__total'] = [980, 960, 960, 900]
    assert classificar(quadro).tolist() == [1, 3, -1, 5]
    try:
        quadro2 = quadro.copy()
        quadro2.loc[0, '__total'] = 960
        classificar(quadro2)
    except ValueError as exc:
        assert 'soma C1..C5' in str(exc)
    else:
        raise AssertionError('Diferença entre nota e competências deveria ser rejeitada.')
    c = defaultdict(novo_contador)
    for cls in [1, 3, -1, 5]:
        acrescentar(c, 'SP', cls, 1)
    assert c['SP']['n'] == 4 and c['SP']['unicas'] == [1, 0, 1, 0, 1]
    assert c['SP']['multiplas'] == 1 and c['BR']['n'] == 4
    # Verificar supressões com UFs e N representativos, não pela amostra N=4.
    c = defaultdict(novo_contador)
    for uf in UFS:
        acrescentar(c, uf, 1, 30)
        acrescentar(c, uf, 2, 30)
        acrescentar(c, uf, -1, 30)
    # Introduzir uma categoria pequena em uma UF via migração de 1 caso.
    c['SP']['unicas'][2] = 1
    c['SP']['multiplas'] -= 1
    c['BR']['unicas'][2] = 1
    c['BR']['multiplas'] -= 1
    validar_contagens(c, 2024, c['BR']['n'], False)
    mascaras, qa = calcular_supressoes(c)
    assert not mascaras and qa['celulas_primarias_suprimidas'] == 0
    publicado = montar_recortes(c, mascaras)
    assert publicado['SP']['resumo_competencias'][2]['n_competencia_unica'] == 1
    assert publicado['SP']['n_casos_com_uma_unica_competencia'] is not None
    log('Autoteste IND-034 aprovado: exclusividade, soma, fechamentos e privacidade.')


def main() -> None:
    p = argparse.ArgumentParser(description='IND-034 — Competência única que impede 1000')
    p.add_argument('--base', type=Path, default=raiz_projeto(), help='Raiz de busca das fontes CSV')
    p.add_argument('--saida', type=Path, default=raiz_projeto(), help='Raiz de saída')
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS))
    p.add_argument('--bloco', type=int, default=100_000, help='Tamanho dos lotes de leitura')
    p.add_argument('--sobrescrever', action='store_true', help='Regenerar JSON/CSV existentes')
    p.add_argument('--somente-modulo', action='store_true', help='Não atualizar dashboards')
    p.add_argument('--sem-controle-populacao', action='store_true',
                   help='Somente testes sintéticos; desabilita controle POP_NEAR fixo')
    p.add_argument('--exigir-2025', action='store_true',
                   help='Falhar caso RESULTADOS_2025.csv não esteja disponível')
    p.add_argument('--autoteste', action='store_true', help='Executar teste interno sem microdados')
    p.add_argument('--competencias-2024', type=Path, default=None,
                   help='Selecionar CSV de competências de 2024 quando houver versões diferentes.')
    p.add_argument('--participantes-2024', type=Path, default=None,
                   help='Selecionar CSV de participantes de 2024 quando houver versões diferentes.')
    args = p.parse_args()
    if args.autoteste:
        autoteste()
        return
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(y not in ANOS for y in anos):
        p.error('Informe anos inteiros entre 2019 e 2025.')
    if args.bloco <= 0:
        p.error('--bloco deve ser maior que zero.')
    escolhas: dict[str, Path] = {}
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base, args.saida, anos, args.bloco, args.sobrescrever,
                 args.somente_modulo, args.sem_controle_populacao, args.exigir_2025,
                 fontes_explicitas=escolhas)
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        print(f'ERRO IND-034: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
