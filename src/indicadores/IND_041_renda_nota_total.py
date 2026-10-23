#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-041 | Renda familiar declarada x nota total da redação (ENEM 2019-2025).

Projeto Integrador IV - UNIVESP.

População: redações com TP_STATUS_REDACAO == 1 e NU_NOTA_REDACAO válida.
Geografia: SG_UF_PROVA (local da prova), Brasil (BR) e 27 UFs.
Medidas: N, média, mediana, Q1, Q3, IQR e percentual por renda.

Fontes:
  2019-2023: MICRODADOS_ENEM_<ano>.csv (Q006 + resultado no mesmo arquivo).
  2024: PARTICIPANTES_2024.csv (Q007/UF) ligado por NU_INSCRICAO a
        COMPETENCIAS_REDACAO_2024.csv (status e nota).
  2025: indisponível para cruzamento, pois PARTICIPANTES e RESULTADOS
        públicos não têm chave de ligação individual compartilhada.

A renda NÃO declarada integra o denominador de redações válidas e aparece
separadamente. Quantidades pequenas, inclusive 2020/RR com 16 casos de
renda ausente, NÃO provocam erro nem são eliminadas. A pequena amostra é
assinalada para cautela estatística, sem supressão automática.

Uso (executar na raiz do repositório):
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_041_renda_nota_total.py --anos 2020 --sobrescrever
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_041_renda_nota_total.py --sobrescrever
    .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_041_renda_nota_total.py --base D:\\dados_enem --anos 2024

Saídas (relativas à raiz do projeto ou ao --saida):
    outputs/json/IND_041_renda_nota_total.json
    outputs/indicadores/IND_041_renda_nota_total.csv

Tenta integrar pages.socioeconomic.income_total nos dashboards anuais
EXISTENTES, sem substituir outros indicadores. Use --somente-modulo para
não modificar dashboards. Dados individuais nunca entram nas saídas.

Esta é uma implementação completa reconstruída a partir do escopo e das
fontes do projeto, não uma cópia byte a byte do arquivo anterior.
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
import sqlite3
import sys
import tempfile
from typing import Any

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = (
    'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
    'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
)
CODIGOS = tuple('ABCDEFGHIJKLMNOPQ')
SEM_RENDA = 'SEM_RESPOSTA'
RENDA_INVALIDA = 'CODIGO_NAO_RECONHECIDO'

# Referências conferidas no inventário de validação dos registros do projeto.
# Estas contagens são controle de integridade dos arquivos integrais,
# não estimativas da amostra ou metas artificiais.
CONTROLE_BR = {
    2019: 3_779_356, 2020: 2_674_914, 2021: 2_293_797,
    2022: 2_363_615, 2023: 2_704_814, 2024: 3_002_710,
}

# Interpretação monetária confirmada no dicionário oficial do ENEM 2024.
# Não transplantar os mesmos R$ a edições anteriores: os cortes se alteram.
ROTULOS_2024 = {
    'A': 'Nenhuma renda',
    'B': 'Até R$ 1.412,00',
    'C': 'R$ 1.412,01 a R$ 2.118,00',
    'D': 'R$ 2.118,01 a R$ 2.824,00',
    'E': 'R$ 2.824,01 a R$ 3.530,00',
    'F': 'R$ 3.530,01 a R$ 4.236,00',
    'G': 'R$ 4.236,01 a R$ 5.648,00',
    'H': 'R$ 5.648,01 a R$ 7.060,00',
    'I': 'R$ 7.060,01 a R$ 8.472,00',
    'J': 'R$ 8.472,01 a R$ 9.884,00',
    'K': 'R$ 9.884,01 a R$ 11.296,00',
    'L': 'R$ 11.296,01 a R$ 12.708,00',
    'M': 'R$ 12.708,01 a R$ 14.120,00',
    'N': 'R$ 14.120,01 a R$ 16.944,00',
    'O': 'R$ 16.944,01 a R$ 21.180,00',
    'P': 'R$ 21.180,01 a R$ 28.240,00',
    'Q': 'Acima de R$ 28.240,00',
}


# Limites monetários anuais no dicionário de cada edição. As letras
# permanecem ordenadas A..Q, mas os valores nominais variam por edição.
# Referência: dicionários oficiais anuais dos Microdados ENEM 2019-2024.
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


def brl(valor: Decimal) -> str:
    return 'R$ ' + f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


# Estatísticas derivadas de histogramas de nota exata: a mediana e os
# quartis não são aproximações por intervalos artificiais de pontuação.
Hist = dict[tuple[str, str], Counter]


def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    caminho = Path(__file__).resolve()
    # Quando copiado em src/indicadores, sobem-se duas pastas.
    if caminho.parent.name.lower() == 'indicadores' and caminho.parent.parent.name.lower() == 'src':
        return caminho.parents[2]
    return Path.cwd().resolve()


def achar_arquivos(base: Path, nomes: set[str]) -> dict[str, Path]:
    """Procura por basename (case-insensitive) sem descer em .venv/.git/outputs."""
    encontrados: dict[str, Path] = {}
    ignorar = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
                'node_modules', 'outputs', '.mypy_cache'}
    for diretorio, dirs, arquivos in os.walk(base):
        dirs[:] = [x for x in dirs if x.lower() not in ignorar]
        for nome in arquivos:
            chave = nome.upper()
            if chave in nomes:
                anterior = encontrados.get(chave)
                atual = Path(diretorio) / nome
                if anterior is not None and anterior.resolve() != atual.resolve():
                    raise ValueError(
                        f'Duas cópias da mesma fonte foram encontradas:\n'
                        f'  {anterior}\n  {atual}\n'
                        'Use --base apontando para uma árvore não ambígua.'
                    )
                encontrados[chave] = atual
        if len(encontrados) == len(nomes):
            break
    return encontrados


def codificar_renda(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return SEM_RENDA
    texto = str(valor).strip().upper()
    if texto in {'', 'NULL', 'NONE', 'NAN', 'NA', 'N/A', '(VAZIO)'}:
        return SEM_RENDA
    if texto in CODIGOS:
        return texto
    return RENDA_INVALIDA


def sigla_uf(valor: Any) -> str:
    texto = '' if valor is None else str(valor).strip().upper()
    return texto if texto in UFS else ''


def rotulo_renda(ano: int, codigo: str) -> str:
    if codigo == SEM_RENDA:
        return 'Renda não informada'
    if codigo == RENDA_INVALIDA:
        return 'Código de renda não reconhecido'
    if codigo == 'A':
        return 'Nenhuma renda'
    if ano == 2024:
        return ROTULOS_2024.get(codigo, f'Faixa {codigo}')
    base = BASE_RENDA_ANO[ano]
    if codigo == 'B':
        return f'Até {brl(base)}'
    if codigo == 'Q':
        return f'Acima de {brl(base * Decimal(20))}'
    limite_anterior = 'B' if codigo == 'C' else CODIGOS[CODIGOS.index(codigo) - 1]
    minimo = base * MULTIPLICADORES[limite_anterior] + Decimal('0.01')
    maximo = base * MULTIPLICADORES[codigo]
    return f'De {brl(minimo)} até {brl(maximo)}'


def ordem_renda(codigo: str) -> int:
    if codigo in CODIGOS:
        return CODIGOS.index(codigo)
    return 17 if codigo == SEM_RENDA else 18


def encoding_csv(caminho: Path) -> str:
    with caminho.open('rb') as f:
        inicio = f.read(3)
    return 'utf-8-sig' if inicio == b'\xef\xbb\xbf' else 'latin-1'


def iterar_csv(caminho: Path, colunas: list[str], bloco: int):
    """Leitura estreita e em blocos, compatível com arquivos de muitos GB."""
    enc = encoding_csv(caminho)
    cabecalho = pd.read_csv(caminho, sep=';', encoding=enc, nrows=0)
    cab = [str(c).strip().lstrip('\ufeff') for c in cabecalho.columns]
    faltantes = sorted(set(colunas) - set(cab))
    if faltantes:
        raise ValueError(f'{caminho.name}: colunas ausentes: {faltantes}. Disponíveis: {cab}')
    for df in pd.read_csv(
        caminho, sep=';', encoding=enc, usecols=colunas,
        dtype='string', chunksize=bloco, low_memory=False,
        keep_default_na=False, na_filter=False,
    ):
        df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
        yield df


def notas_validas(df: pd.DataFrame) -> pd.DataFrame:
    mask = df['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')
    dados = df.loc[mask].copy()
    if dados.empty:
        return dados
    valores = dados['NU_NOTA_REDACAO'].astype('string').str.strip().str.replace(',', '.', regex=False)
    numero = pd.to_numeric(valores, errors='coerce')
    ruim = numero.isna() | (numero < 0) | (numero > 1000) | (~numero.map(math.isfinite))
    if ruim.any():
        raise ValueError(f'Há {int(ruim.sum())} redações com status 1 e nota inexistente/inválida.')
    dados['nota'] = numero.astype('float64')
    return dados


def agregar_lote(hist: Hist, lote: pd.DataFrame) -> int:
    """Agrega uma linha por UF/renda/nota; duplica apenas as contagens para BR."""
    if lote.empty:
        return 0
    if lote['uf'].isin(UFS).sum() != len(lote):
        raise ValueError('Redações válidas com SG_UF_PROVA inválida ou ausente: confira a fonte.')
    # Categoria de renda já normalizada na entrada.
    contagens = lote.groupby(['uf', 'renda', 'nota'], dropna=False, sort=False).size()
    for (uf, renda, nota), quantidade in contagens.items():
        n = int(quantidade)
        valor = float(nota)
        hist[(str(uf), str(renda))][valor] += n
        hist[('BR', str(renda))][valor] += n
    return len(lote)


def processar_antigo(ano: int, caminho: Path, bloco: int) -> tuple[Hist, int]:
    hist: Hist = defaultdict(Counter)
    total = 0
    colunas = ['TP_STATUS_REDACAO','NU_NOTA_REDACAO','SG_UF_PROVA','Q006']
    for parte in iterar_csv(caminho, colunas, bloco):
        validas = notas_validas(parte)
        if validas.empty:
            continue
        validas['uf'] = validas['SG_UF_PROVA'].astype('string').str.strip().str.upper()
        validas['renda'] = validas['Q006'].map(codificar_renda)
        total += agregar_lote(hist, validas[['uf','renda','nota']])
    return hist, total


def processar_2024(p_part: Path, p_comp: Path, bloco: int) -> tuple[Hist, int]:
    """Relacionamento exato por NU_INSCRICAO usando SQLite temporário.

    Não se relaciona PARTICIPANTES_2024 a RESULTADOS_2024: este último
    utiliza NU_SEQUENCIAL e não fornece chave pública correspondente.
    """
    hist: Hist = defaultdict(Counter)
    with tempfile.TemporaryDirectory(prefix='enem_ind041_') as pasta:
        banco = Path(pasta) / 'socio.sqlite3'
        con = sqlite3.connect(str(banco))
        try:
            con.execute('PRAGMA journal_mode=OFF')
            con.execute('PRAGMA synchronous=OFF')
            con.execute('PRAGMA temp_store=MEMORY')
            con.execute('CREATE TABLE socio (id TEXT PRIMARY KEY, uf TEXT NOT NULL, renda TEXT NOT NULL) WITHOUT ROWID')
            con.execute('CREATE TEMP TABLE lote (id TEXT NOT NULL, nota REAL NOT NULL)')
            total_part = 0
            for parte in iterar_csv(p_part, ['NU_INSCRICAO','SG_UF_PROVA','Q007'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip()
                if ids.eq('').any():
                    raise ValueError('PARTICIPANTES_2024 contém inscrição vazia.')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper()
                if (~ufs.isin(UFS)).any():
                    raise ValueError('PARTICIPANTES_2024 contém UF da prova desconhecida.')
                rendas = parte['Q007'].map(codificar_renda)
                try:
                    con.executemany('INSERT INTO socio(id,uf,renda) VALUES(?,?,?)',
                                    zip(ids.tolist(), ufs.tolist(), rendas.tolist()))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('NU_INSCRICAO duplicada em PARTICIPANTES_2024.') from exc
                total_part += len(parte)
                if total_part % (5 * bloco) < bloco:
                    log(f'  2024: participantes indexados={total_part:,}')
            con.commit()
            total = 0
            for parte in iterar_csv(
                p_comp, ['NU_INSCRICAO','TP_STATUS_REDACAO','NU_NOTA_REDACAO'], bloco
            ):
                validas = notas_validas(parte)
                if validas.empty:
                    continue
                ids = validas['NU_INSCRICAO'].astype('string').str.strip()
                if ids.eq('').any():
                    raise ValueError('COMPETENCIAS_REDACAO_2024 contém inscrição válida vazia.')
                con.execute('DELETE FROM lote')
                con.executemany('INSERT INTO lote(id,nota) VALUES(?,?)',
                                zip(ids.tolist(), validas['nota'].tolist()))
                resultados = con.execute('''
                    SELECT s.uf, s.renda, l.nota, COUNT(*)
                      FROM lote AS l INNER JOIN socio AS s ON s.id = l.id
                     GROUP BY s.uf, s.renda, l.nota
                ''').fetchall()
                encontrados = sum(int(row[3]) for row in resultados)
                if encontrados != len(validas):
                    raise ValueError(
                        f'2024: {len(validas) - encontrados} redações válidas não '
                        'encontradas em PARTICIPANTES_2024; ligação incompleta.'
                    )
                # Expandir contagens para o conjunto BR, mas nunca registros individuais.
                for uf, renda, nota, n in resultados:
                    n = int(n)
                    nota = float(nota)
                    hist[(uf, renda)][nota] += n
                    hist[('BR', renda)][nota] += n
                total += len(validas)
                if total % (5 * bloco) < bloco:
                    log(f'  2024: redações válidas vinculadas={total:,}')
            return hist, total
        finally:
            con.close()


def total_hist(c: Counter) -> int:
    return sum(c.values())


def percentil_hist(contagens: Counter, p: float) -> float | None:
    """Equivalente a np.percentile(lista_expandida, p) (interpolação linear)."""
    n = total_hist(contagens)
    if not n:
        return None
    posicao = (n - 1) * (p / 100.0)
    esq = math.floor(posicao)
    dir = math.ceil(posicao)
    a = None
    b = None
    acumulado = 0
    for valor, quantidade in sorted(contagens.items()):
        acumulado += quantidade
        if a is None and esq < acumulado:
            a = valor
        if dir < acumulado:
            b = valor
            break
    assert a is not None and b is not None
    return float(a + (b - a) * (posicao - esq))


def metricas(c: Counter) -> dict[str, int | float | None]:
    n = total_hist(c)
    if n == 0:
        return dict(n_redacoes=0, media=None, mediana=None, q1=None,
                    q3=None, iqr=None, desvio_padrao=None)
    media = math.fsum(nota * qtd for nota, qtd in c.items()) / n
    v = math.fsum(qtd * (nota - media) ** 2 for nota, qtd in c.items()) / n
    q1 = percentil_hist(c, 25)
    q3 = percentil_hist(c, 75)
    return dict(n_redacoes=n, media=round(media, 4),
                mediana=round(percentil_hist(c, 50), 4),
                q1=round(q1, 4), q3=round(q3, 4),
                iqr=round(q3 - q1, 4), desvio_padrao=round(math.sqrt(v), 4))


def gerar_recortes(ano: int, hist: Hist, total: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recortes = {}
    linhas: list[dict[str, Any]] = []
    br_soma = sum(total_hist(c) for (uf, _), c in hist.items() if uf == 'BR')
    if br_soma != total:
        raise ValueError(f'Controle interno {ano}: BR={br_soma}, válidas={total}.')
    for uf in ('BR', *UFS):
        por_codigo = {cod: hist.get((uf, cod), Counter())
                      for cod in (*CODIGOS, SEM_RENDA, RENDA_INVALIDA)}
        denominador = sum(total_hist(c) for c in por_codigo.values())
        com_renda = sum(total_hist(por_codigo[c]) for c in CODIGOS)
        sem_renda = total_hist(por_codigo[SEM_RENDA])
        invalidos = total_hist(por_codigo[RENDA_INVALIDA])
        faixas = []
        for codigo, contagens in por_codigo.items():
            n = total_hist(contagens)
            if n == 0 and codigo in (SEM_RENDA, RENDA_INVALIDA):
                continue
            estat = metricas(contagens)
            item = {
                'codigo_renda': codigo,
                'faixa_renda': codigo if codigo in CODIGOS else rotulo_renda(ano, codigo),
                'descricao_faixa': rotulo_renda(ano, codigo),
                'ordem': ordem_renda(codigo),
                **estat,
                'percentual_total_validas': round(100 * n / denominador, 6) if denominador else 0,
                'percentual_renda_declarada': (round(100 * n / com_renda, 6)
                                               if com_renda and codigo in CODIGOS else None),
                'n_pequeno': bool(0 < n < 30),  # Alerta descritivo, NÃO supressão.
            }
            faixas.append(item)
            linhas.append({'ano': ano, 'uf': uf, **item})
        fechamento = sum(int(x['n_redacoes']) for x in faixas)
        if fechamento != denominador:
            raise ValueError(f'{ano}/{uf}: soma das faixas {fechamento} != {denominador}')
        if 0 < sem_renda < 30:
            log(f'  AVISO {ano}/{uf}: {sem_renda} redações válidas com renda não informada; '
                'mantidas no controle (sem bloqueio).')
        recortes[uf] = {
            'uf': uf,
            'n_pop_socio_valid': denominador,
            'n_redacoes_validas': denominador,
            'n_renda_declarada': com_renda,
            'n_renda_nao_informada': sem_renda,
            'n_codigo_renda_invalido': invalidos,
            'percentual_renda_declarada': round(100 * com_renda / denominador, 6)
                                           if denominador else None,
            'categories': faixas,
            'faixas': faixas,
            'integridade': {'fechamento': True, 'n_total_faixas': fechamento},
        }
    soma_ufs = sum(recortes[uf]['n_pop_socio_valid'] for uf in UFS)
    if soma_ufs != total:
        raise ValueError(f'{ano}: soma das UFs ({soma_ufs}) != Brasil ({total})')
    controle = CONTROLE_BR.get(ano)
    if controle is not None and controle != total:
        raise ValueError(
            f'{ano}: população válida calculada ({total:,}) difere do inventário '
            f'oficial do projeto ({controle:,}). Confirme a versão completa da base.'
        )
    log(f'  {ano}: POP_SOCIO_VALID BR={total:,}; categorias públicas={len(CODIGOS)}')
    return recortes, linhas


def serializar_json(destino: Path, dados: Any) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', dir=destino.parent, suffix='.tmp',
        prefix=destino.name + '.', delete=False
    ) as tmp:
        arquivo_temporario = Path(tmp.name)
        json.dump(dados, tmp, ensure_ascii=False, indent=2, allow_nan=False)
        tmp.write('\n')
    try:
        arquivo_temporario.replace(destino)
    finally:
        arquivo_temporario.unlink(missing_ok=True)


def salvar_csv(destino: Path, linhas: list[dict[str, Any]]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    colunas = [
        'ano','uf','codigo_renda','faixa_renda','descricao_faixa','ordem',
        'n_redacoes','media','mediana','q1','q3','iqr','desvio_padrao',
        'percentual_total_validas','percentual_renda_declarada','n_pequeno',
    ]
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8-sig', newline='', dir=destino.parent,
        prefix=destino.name + '.', suffix='.tmp', delete=False
    ) as tmp:
        path_tmp = Path(tmp.name)
        w = csv.DictWriter(tmp, fieldnames=colunas, delimiter=';', extrasaction='ignore')
        w.writeheader()
        w.writerows(linhas)
    try:
        path_tmp.replace(destino)
    finally:
        path_tmp.unlink(missing_ok=True)


def atualizar_dashboards(raiz: Path, anos: dict[str, Any]) -> None:
    """Somente dashboards já existentes; nenhum arquivo de outro ano é inventado.

    Preserva integralmente as demais páginas/indicadores. O recorte nacional
    fica em national; os recortes estaduais, em states. Nenhuma linha individual.
    """
    diretorio = raiz / 'outputs' / 'json'
    for ano_texto, resultado in anos.items():
        if resultado.get('status') != 'ok':
            continue
        ano = int(ano_texto)
        arquivo = diretorio / f'dashboard_enem_{ano}.json'
        if not arquivo.exists():
            log(f'  Dashboard {ano} não existe: integração ignorada (módulo continua disponível).')
            continue
        with arquivo.open('r', encoding='utf-8-sig') as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError(f'{arquivo}: JSON não é um objeto; integração interrompida.')
        pages = doc.setdefault('pages', {})
        if not isinstance(pages, dict):
            raise ValueError(f'{arquivo}: campo pages não é um objeto.')
        socio = pages.setdefault('socioeconomic', {})
        if not isinstance(socio, dict):
            raise ValueError(f'{arquivo}: pages.socioeconomic não é um objeto.')
        rec = resultado['recortes']
        novo = {
            'indicator_id': 'IND-041', 'year': ano,
            'status': 'draft',
            'population': 'POP_SOCIO_VALID',
            'source_question': resultado['variavel_renda'],
            'national': rec['BR'],
            'states': {uf: rec[uf] for uf in UFS},
            'privacy_note': ('Contagens pequenas não foram automaticamente suprimidas. '
                             'Reavaliar o contexto antes de publicação externa.'),
        }
        # Cópia de segurança criada uma única vez: é possível voltar ao original.
        backup = arquivo.with_suffix(arquivo.suffix + '.bak_antes_ind041')
        if not backup.exists():
            import shutil
            shutil.copy2(arquivo, backup)
        socio['income_total'] = novo
        serializar_json(arquivo, doc)
        log(f'  Dashboard integrado: {arquivo}')


def executar(base: Path, anos: tuple[int, ...], bloco: int,
             somente_modulo: bool, sobrescrever: bool, saida: Path | None = None) -> None:
    raiz = (saida or raiz_projeto()).resolve()
    entrada = base.resolve()
    if not entrada.is_dir():
        raise ValueError(f'Pasta de bases não encontrada: {entrada}')
    json_path = raiz / 'outputs' / 'json' / 'IND_041_renda_nota_total.json'
    csv_path = raiz / 'outputs' / 'indicadores' / 'IND_041_renda_nota_total.csv'
    if not sobrescrever and (json_path.exists() or csv_path.exists()):
        raise FileExistsError('Saída IND-041 já existe. Use --sobrescrever para atualizá-la.')
    nomes = set()
    for ano in anos:
        if 2019 <= ano <= 2023:
            nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano == 2024:
            nomes.update({'PARTICIPANTES_2024.CSV', 'COMPETENCIAS_REDACAO_2024.CSV'})
    caminhos = achar_arquivos(entrada, nomes) if nomes else {}
    ausentes = sorted(nomes - set(caminhos))
    if ausentes:
        raise FileNotFoundError(
            f'Fontes faltando em {entrada}: {ausentes}. '
            'Use --base para apontar à pasta que contém os microdados.'
        )
    dados_anos: dict[str, Any] = {}
    linhas_csv: list[dict[str, Any]] = []
    for ano in anos:
        if ano == 2025:
            log('IND-041 | 2025: indisponível: arquivos públicos sem chave individual comum.')
            dados_anos[str(ano)] = {
                'ano': ano, 'status': 'indisponivel',
                'reason': ('PARTICIPANTES_2025 e RESULTADOS_2025 não dispõem '
                           'de chave pública individual compatível para renda x nota.'),
                'recortes': {},
            }
            continue
        log(f'IND-041 | {ano}: lendo renda e nota em POP_SOCIO_VALID...')
        if ano <= 2023:
            hist, total = processar_antigo(ano, caminhos[f'MICRODADOS_ENEM_{ano}.CSV'], bloco)
            renda = 'Q006'
        else:
            hist, total = processar_2024(
                caminhos['PARTICIPANTES_2024.CSV'],
                caminhos['COMPETENCIAS_REDACAO_2024.CSV'], bloco
            )
            renda = 'Q007'
        recortes, linhas = gerar_recortes(ano, hist, total)
        linhas_csv.extend(linhas)
        dados_anos[str(ano)] = {
            'ano': ano, 'status': 'ok', 'variavel_renda': renda,
            'fonte_nota': ('MICRODADOS_ENEM_' + str(ano) + '.csv' if ano <= 2023
                           else 'COMPETENCIAS_REDACAO_2024.csv'),
            'populacao': 'POP_SOCIO_VALID',
            'n_brasil': total,
            'categorias_renda_ordenadas': list(CODIGOS),
            'recortes': recortes,
        }
    modulo = {
        'indicator_id': 'IND-041',
        'titulo': 'Renda familiar x nota total da redação',
        'status': 'draft',
        'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'population': 'POP_SOCIO_VALID',
        'geography': 'SG_UF_PROVA',
        'methodology': {
            'selection': 'TP_STATUS_REDACAO = 1 e 0 <= NU_NOTA_REDACAO <= 1000',
            'income_2019_2023': 'Q006', 'income_2024': 'Q007',
            'percentile_method': 'linear; ponderado pelas frequências de notas exatas',
            'sd_method': 'desvio-padrão populacional',
            'missing_income': 'categoria própria, incluída no denominador',
            'small_n': 'informado como aviso; sem supressão automática',
            'no_link_2025': True,
            'cautions': [
                'Renda autorreferida e em faixas nominais de cada edição.',
                'Rótulos monetários respeitam a tabela de limites específica de cada ano.',
                'As UFs são locais de aplicação da prova, não residência.',
                'Participações de exames, não pessoas únicas.',
                'Pequenas contagens geram estimativas menos estáveis.',
                'Não interpretar associações observadas como causais.',
            ],
        },
        'years': dados_anos,
    }
    # Publicar módulo antes de alterar dashboards. Escrita atômica.
    serializar_json(json_path, modulo)
    salvar_csv(csv_path, linhas_csv)
    log(f'IND-041 | JSON: {json_path}')
    log(f'IND-041 | CSV: {csv_path}')
    if not somente_modulo:
        atualizar_dashboards(raiz, dados_anos)
    log('IND-041 | Finalizado.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-041: renda familiar x nota de redação.')
    parser.add_argument('--base', type=Path, default=raiz_projeto(),
                        help='Diretório contendo as bases do ENEM (busca recursiva).')
    parser.add_argument('--saida', type=Path, default=None,
                        help='Raiz alternativa para outputs/, útil para testes.')
    parser.add_argument('--anos', nargs='+', type=int, default=list(ANOS),
                        help='Anos selecionados; padrão 2019 a 2025.')
    parser.add_argument('--bloco', type=int, default=150_000,
                        help='Quantidade de linhas processadas por bloco.')
    parser.add_argument('--somente-modulo', action='store_true',
                        help='Não modificar os dashboards existentes.')
    parser.add_argument('--sobrescrever', action='store_true',
                        help='Permitir substituição dos arquivos IND-041 existentes.')
    args = parser.parse_args()
    if args.bloco <= 0:
        parser.error('--bloco deve ser positivo.')
    anos = tuple(sorted(set(args.anos)))
    if any(ano not in ANOS for ano in anos):
        parser.error(f'--anos aceita apenas {ANOS[0]}..{ANOS[-1]}.')
    try:
        executar(args.base, anos, args.bloco, args.somente_modulo,
                 args.sobrescrever, args.saida)
    except (ValueError, FileNotFoundError, FileExistsError, OSError,
            sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        print(f'ERRO IND-041: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
