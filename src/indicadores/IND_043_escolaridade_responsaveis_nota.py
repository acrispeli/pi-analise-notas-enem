#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""IND-043 | Escolaridade dos responsáveis × nota total da redação.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores ENEM 2019–2025 v2.0.

Por ano (2019–2024), Brasil e UF da prova, compara N, média e mediana da
redação válida segundo Q001 (escolaridade do pai/homem responsável) e Q002
(escolaridade da mãe/mulher responsável). Exporta também Q1, Q3, IQR, DP e %.
Os dois questionários são analisados SEPARADAMENTE; nunca cruzados entre si.

2019–2023: MICRODADOS_ENEM_<ano>.csv, mesmo registro.
2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv, com junção
      estrita por NU_INSCRICAO (sem NU_SEQUENCIAL/posição de linha).
2025: indisponível, pois falta chave pública entre fontes de socioeconomia
      e resultado individual.

Categoria H = 'Não sei' (RESPOSTA VÁLIDA do questionário, mas não grau de
escolaridade). Branco físico e código não reconhecido são categorias distintas.
Não exclui pequenos grupos; sinaliza-os. Antes de publicar, revisar privacidade
complementar e estabilidade das estatísticas. Não permite conclusão causal.

Comandos no PowerShell (raiz do projeto):
  .\.venv\Scripts\python.exe src\indicadores\IND_043_escolaridade_responsaveis_nota.py --anos 2024 --sobrescrever
  .\.venv\Scripts\python.exe src\indicadores\IND_043_escolaridade_responsaveis_nota.py --sobrescrever

Saídas: outputs/json/IND_043_escolaridade_responsaveis_nota.json
        outputs/indicadores/IND_043_escolaridade_responsaveis_nota.csv
        pages.socioeconomic.parent_education_total nos dashboards existentes.
Requer pandas; lê microdados em blocos e usa SQLite temporário na junção 2024.
Não utiliza algoritmos de aprendizado de máquina.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
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
QUESTOES = ('Q001','Q002')
CODIGOS = tuple('ABCDEFGH')
SEM_RESPOSTA = 'SEM_RESPOSTA'
CODIGO_INVALIDO = 'CODIGO_NAO_RECONHECIDO'
CATEGORIAS = (*CODIGOS, SEM_RESPOSTA, CODIGO_INVALIDO)
ROTULOS = {
    'A': 'Nunca estudou',
    'B': 'Não completou a 4ª série/5º ano do Ensino Fundamental',
    'C': 'Completou a 4ª série/5º ano, mas não completou a 8ª série/9º ano do Ensino Fundamental',
    'D': 'Completou a 8ª série/9º ano do Ensino Fundamental, mas não completou o Ensino Médio',
    'E': 'Completou o Ensino Médio, mas não completou a Faculdade',
    'F': 'Completou a Faculdade, mas não completou a Pós-graduação',
    'G': 'Completou a Pós-graduação',
    'H': 'Não sei',
    SEM_RESPOSTA: 'Resposta em branco / não informada',
    CODIGO_INVALIDO: 'Código não reconhecido',
}
RESPONSAVEIS = {'Q001': 'Pai ou homem responsável', 'Q002': 'Mãe ou mulher responsável'}
CONTROLE_POP = {2019: 3_779_356, 2020: 2_674_914, 2021: 2_293_797,
                2022: 2_363_615, 2023: 2_704_814, 2024: 3_002_710}
Hist = dict[tuple[str, str, str], Counter]


def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    p = Path(__file__).resolve()
    if p.parent.name.lower() == 'indicadores' and p.parent.parent.name.lower() == 'src':
        return p.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str]) -> dict[str, Path]:
    ignoradas = {'.git', '.venv', 'venv', '__pycache__', 'outputs', '.pytest_cache',
                 'node_modules', '.mypy_cache'}
    achadas: dict[str, Path] = {}
    for raiz, dirs, arquivos in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in ignoradas]
        for nome in arquivos:
            chave = nome.upper()
            if chave in nomes:
                novo = Path(raiz) / nome
                if chave in achadas and achadas[chave].resolve() != novo.resolve():
                    raise ValueError(f'Fontes duplicadas para {chave}: {achadas[chave]} / {novo}. Use --base.')
                achadas[chave] = novo
        if len(achadas) == len(nomes):
            break
    return achadas


def codificar_escolaridade(valor: Any) -> str:
    if valor is None or pd.isna(valor):
        return SEM_RESPOSTA
    x = str(valor).strip().upper()
    if x in {'', 'NULL', 'NONE', 'NAN', 'NA', 'N/A', '(VAZIO)'}:
        return SEM_RESPOSTA
    return x if x in CODIGOS else CODIGO_INVALIDO


def ler_blocos(caminho: Path, colunas: list[str], bloco: int):
    with caminho.open('rb') as f:
        cab = f.read(3)
    encoding = 'utf-8-sig' if cab == b'\xef\xbb\xbf' else 'latin-1'
    try:
        hdr = pd.read_csv(caminho, sep=';', encoding=encoding, nrows=0)
    except Exception as e:
        raise ValueError(f'Erro de leitura do cabeçalho de {caminho.name}: {e}') from e
    presentes = {str(c).strip().lstrip('\ufeff') for c in hdr.columns}
    faltantes = sorted(set(colunas) - presentes)
    if faltantes:
        raise ValueError(f'{caminho.name}: faltam colunas {faltantes}. Cabeçalho={sorted(presentes)}')
    for df in pd.read_csv(caminho, sep=';', encoding=encoding, usecols=colunas,
                          dtype='string', chunksize=bloco, low_memory=False,
                          na_filter=False, keep_default_na=False):
        df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
        yield df


def preparar_notas(parte: pd.DataFrame) -> pd.DataFrame:
    elegiveis = parte['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')
    df = parte.loc[elegiveis].copy()
    if df.empty:
        df['nota'] = pd.Series(dtype='float64')
        return df
    x = df['NU_NOTA_REDACAO'].astype('string').str.strip().str.replace(',', '.', regex=False)
    notas = pd.to_numeric(x, errors='coerce')
    invalidas = notas.isna() | (notas < 0) | (notas > 1000) | ~notas.map(math.isfinite)
    if invalidas.any():
        raise ValueError(f'Existem {int(invalidas.sum())} redações com status 1 e nota inválida.')
    df['nota'] = notas.astype('float64')
    return df


def agregar_lote(hist: Hist, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    if (~df['uf'].isin(UFS)).any():
        raise ValueError('SG_UF_PROVA não reconhecida em redação válida.')
    for pergunta in QUESTOES:
        cont = df.groupby(['uf', pergunta, 'nota'], dropna=False, sort=False).size()
        for (uf, codigo, nota), n in cont.items():
            hist[(str(uf), pergunta, str(codigo))][float(nota)] += int(n)
            hist[('BR', pergunta, str(codigo))][float(nota)] += int(n)
    return len(df)


def processar_2019_2023(ano: int, arquivo: Path, bloco: int) -> tuple[Hist, int, dict]:
    hist: Hist = defaultdict(Counter)
    total = 0
    for parte in ler_blocos(arquivo, ['TP_STATUS_REDACAO','NU_NOTA_REDACAO',
                                       'SG_UF_PROVA',*QUESTOES], bloco):
        df = preparar_notas(parte)
        if df.empty:
            continue
        df['uf'] = df['SG_UF_PROVA'].astype('string').str.strip().str.upper()
        for q in QUESTOES:
            df[q] = df[q].map(codificar_escolaridade)
        total += agregar_lote(hist, df[['uf','Q001','Q002','nota']])
    return hist, total, {'metodo': 'mesma_linha', 'n_redacoes_validas': total}


def processar_2024(part: Path, comp: Path, bloco: int) -> tuple[Hist, int, dict]:
    """Junção robusta: UNIQUE em ambos os lados, checagem de correspondência.

    Apenas as notas de redações válidas são colocadas na tabela temporária.
    Preserva identificadores SOMENTE dentro do SQLite temporário apagado ao final.
    """
    hist: Hist = defaultdict(Counter)
    with tempfile.TemporaryDirectory(prefix='enem_ind043_') as pasta:
        db = Path(pasta) / 'temporario.sqlite3'
        con = sqlite3.connect(str(db))
        try:
            con.execute('PRAGMA journal_mode=OFF')
            con.execute('PRAGMA synchronous=OFF')
            con.execute('PRAGMA temp_store=MEMORY')
            con.execute('CREATE TABLE socio (id TEXT PRIMARY KEY, uf TEXT NOT NULL, '
                        'q001 TEXT NOT NULL, q002 TEXT NOT NULL) WITHOUT ROWID')
            con.execute('CREATE TABLE vistos (id TEXT PRIMARY KEY) WITHOUT ROWID')
            con.execute('CREATE TEMP TABLE lote (id TEXT, nota REAL)')
            n_part = 0
            for parte in ler_blocos(part, ['NU_INSCRICAO','SG_UF_PROVA',*QUESTOES], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip()
                if ids.eq('').any():
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO vazia.')
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper()
                if (~ufs.isin(UFS)).any():
                    raise ValueError('PARTICIPANTES_2024: SG_UF_PROVA inválida.')
                qa = parte['Q001'].map(codificar_escolaridade)
                qb = parte['Q002'].map(codificar_escolaridade)
                try:
                    con.executemany('INSERT INTO socio VALUES (?,?,?,?)',
                                    zip(ids.tolist(), ufs.tolist(), qa.tolist(), qb.tolist()))
                except sqlite3.IntegrityError as e:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from e
                n_part += len(parte)
            con.commit()
            log(f'  2024: participantes indexados: {n_part:,}')
            total = 0
            for parte in ler_blocos(comp, ['NU_INSCRICAO','TP_STATUS_REDACAO',
                                            'NU_NOTA_REDACAO'], bloco):
                df = preparar_notas(parte)
                if df.empty:
                    continue
                ids = df['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not id_ for id_ in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em válida.')
                try:
                    con.executemany('INSERT INTO vistos VALUES (?)', ((v,) for v in ids))
                except sqlite3.IntegrityError as e:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição duplicada em válida.') from e
                con.execute('DELETE FROM lote')
                con.executemany('INSERT INTO lote VALUES (?,?)',
                                zip(ids, df['nota'].tolist()))
                vinculadas = int(con.execute('SELECT COUNT(*) FROM lote l '
                                             'JOIN socio s ON l.id=s.id').fetchone()[0])
                if vinculadas != len(df):
                    raise ValueError(f'2024: {len(df)-vinculadas} redações válidas sem '
                                     'correspondência em PARTICIPANTES_2024.')
                for q, col in [('Q001','q001'), ('Q002','q002')]:
                    linhas = con.execute(f'''
                        SELECT s.uf, s.{col}, l.nota, COUNT(*)
                        FROM lote l JOIN socio s ON l.id=s.id
                        GROUP BY s.uf, s.{col}, l.nota
                    ''').fetchall()
                    for uf, codigo, nota, n in linhas:
                        hist[(uf,q,codigo)][float(nota)] += int(n)
                        hist[('BR',q,codigo)][float(nota)] += int(n)
                total += len(df)
                con.commit()
            log(f'  2024: redações válidas vinculadas: {total:,}')
            return hist, total, {'metodo': 'join_NU_INSCRICAO',
                                 'n_participantes': n_part,
                                 'n_redacoes_validas_vinculadas': total,
                                 'n_validas_sem_correspondencia': 0,
                                 'chave_unica_participantes': True,
                                 'chave_unica_redacoes_validas': True}
        finally:
            con.close()


def n_hist(c: Counter) -> int:
    return sum(c.values())


def quantil_hist(c: Counter, pct: float) -> float | None:
    """Percentil linear H-F 7, exato sobre notas observadas e frequências."""
    n = n_hist(c)
    if n == 0:
        return None
    pos = (n-1) * pct / 100
    i = math.floor(pos)
    j = math.ceil(pos)
    v1 = v2 = None
    soma = 0
    for valor, quantidade in sorted(c.items()):
        soma += quantidade
        if v1 is None and i < soma:
            v1 = float(valor)
        if j < soma:
            v2 = float(valor)
            break
    if v1 is None or v2 is None:
        raise ValueError('Falha no cálculo do percentil.')
    return v1 + (v2-v1)*(pos-i)


def metricas(c: Counter) -> dict[str, Any]:
    n = n_hist(c)
    if not n:
        return {'n_redacoes': 0, 'media': None, 'mediana': None, 'q1': None,
                'q3': None, 'iqr': None, 'desvio_padrao': None}
    media = math.fsum(float(v)*f for v,f in c.items())/n
    v = math.fsum(f*(float(x)-media)**2 for x,f in c.items())/n
    q1 = quantil_hist(c,25)
    q3 = quantil_hist(c,75)
    return {'n_redacoes': n, 'media': round(media,4),
            'mediana': round(quantil_hist(c,50),4),
            'q1': round(q1,4), 'q3': round(q3,4),
            'iqr': round(q3-q1,4), 'desvio_padrao': round(math.sqrt(v),4)}


def gerar_recortes(ano: int, hist: Hist, total: int,
                    verificar_populacao: bool = True) -> tuple[dict, list[dict]]:
    recortes = {}
    linhas_csv: list[dict] = []
    for uf in ('BR',*UFS):
        perguntas = {}
        for pergunta in QUESTOES:
            por_codigo = {codigo: hist.get((uf,pergunta,codigo), Counter())
                          for codigo in CATEGORIAS}
            denominador = sum(n_hist(c) for c in por_codigo.values())
            n_conhecidos = sum(n_hist(por_codigo[c]) for c in 'ABCDEFG')
            n_nao_sei = n_hist(por_codigo['H'])
            n_brancos = n_hist(por_codigo[SEM_RESPOSTA])
            n_invalidos = n_hist(por_codigo[CODIGO_INVALIDO])
            categorias = []
            for ordem,codigo in enumerate(CATEGORIAS):
                contagem = por_codigo[codigo]
                n = n_hist(contagem)
                if n == 0 and codigo in (SEM_RESPOSTA,CODIGO_INVALIDO):
                    continue
                est = metricas(contagem)
                item = {'codigo_escolaridade': codigo,
                        'descricao_categoria': ROTULOS[codigo],
                        'ordem': ordem,
                        'eh_nivel_escolaridade': codigo in 'ABCDEFG',
                        'resposta_nao_sei': codigo == 'H',
                        **est,
                        'percentual_total_validas': round(100*n/denominador,6)
                                                   if denominador else None,
                        'n_pequeno': bool(0 < n < 30)}
                categorias.append(item)
                linhas_csv.append({'ano':ano,'uf':uf,'questao':pergunta,
                                   'responsavel':RESPONSAVEIS[pergunta],**item})
            if sum(x['n_redacoes'] for x in categorias) != denominador:
                raise ValueError(f'{ano}/{uf}/{pergunta}: categorias não fecham.')
            perguntas[pergunta] = {
                'questao': pergunta, 'responsavel': RESPONSAVEIS[pergunta],
                'n_redacoes_validas': denominador,
                'n_escolaridade_conhecida': n_conhecidos,
                'n_resposta_nao_sei': n_nao_sei,
                'n_resposta_em_branco': n_brancos,
                'n_codigo_invalido': n_invalidos,
                'percentual_escolaridade_conhecida':
                    round(100*n_conhecidos/denominador,6) if denominador else None,
                'categories': categorias,
                'integridade': {'soma_categorias': denominador,
                                'categorias_fecham': True},
            }
        if perguntas['Q001']['n_redacoes_validas'] != perguntas['Q002']['n_redacoes_validas']:
            raise ValueError(f'{ano}/{uf}: denominadores de Q001 e Q002 diferem.')
        recortes[uf] = {'uf':uf, 'n_pop_socio_valid':perguntas['Q001']['n_redacoes_validas'],
                        'n_redacoes_validas':perguntas['Q001']['n_redacoes_validas'],
                        'questions': perguntas, 'questoes': perguntas}
    if recortes['BR']['n_redacoes_validas'] != total:
        raise ValueError(f'{ano}: N Brasil {recortes["BR"]["n_redacoes_validas"]} != {total}')
    if sum(recortes[uf]['n_redacoes_validas'] for uf in UFS) != total:
        raise ValueError(f'{ano}: soma das UFs != Brasil.')
    if verificar_populacao and total != CONTROLE_POP[ano]:
        raise ValueError(f'{ano}: {total:,} redações válidas != população de referência '
                         f'{CONTROLE_POP[ano]:,}. Verifique a completude da fonte.')
    log(f'  {ano}: Brasil={total:,} redações válidas; Q001 e Q002 fecham.')
    return recortes, linhas_csv


def comparar_ind041(ano: int, recortes: dict, raiz: Path) -> str:
    arq = raiz/'outputs'/'json'/'IND_041_renda_nota_total.json'
    if not arq.is_file():
        return 'nao_verificado_ind041_ausente'
    with arq.open(encoding='utf-8-sig') as f:
        doc = json.load(f)
    ref = doc.get('years',{}).get(str(ano))
    if not ref or ref.get('status') != 'ok':
        return 'nao_verificado_ano_ausente_no_ind041'
    for uf in ('BR',*UFS):
        atual = recortes[uf]
        anterior = ref['recortes'][uf]
        n = atual['n_redacoes_validas']
        if n != anterior['n_pop_socio_valid']:
            raise ValueError(f'IND-041: N divergente para {ano}/{uf}.')
        for q in QUESTOES:
            itens = atual['questions'][q]['categories']
            media_ponderada = sum(float(x['media'])*x['n_redacoes']
                                  for x in itens if x['n_redacoes'])/n if n else None
            # Compare rounded category means against rounded pooled IND-041 means.
            if n:
                referencia = sum(float(x['media'])*x['n_redacoes']
                                 for x in anterior['categories'] if x['n_redacoes'])/n
                if abs(media_ponderada - referencia) > 0.00015:
                    raise ValueError(f'IND-041: média ponderada divergente em {ano}/{uf}/{q}.')
    return 'aprovado'


def salvar_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     suffix='.tmp',prefix=path.name+'.',delete=False) as f:
        tmp = Path(f.name)
        json.dump(doc,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def salvar_csv(path: Path, linhas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    campos = ['ano','uf','questao','responsavel','codigo_escolaridade','descricao_categoria',
              'ordem','eh_nivel_escolaridade','resposta_nao_sei','n_redacoes','media','mediana',
              'q1','q3','iqr','desvio_padrao','percentual_total_validas','n_pequeno']
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',newline='',dir=path.parent,
                                     suffix='.tmp',prefix=path.name+'.',delete=False) as f:
        tmp = Path(f.name)
        wr = csv.DictWriter(f,delimiter=';',fieldnames=campos,extrasaction='ignore')
        wr.writeheader()
        wr.writerows(linhas)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def atualizar_dashboards(raiz: Path, anos: dict) -> None:
    """Atualiza SOMENTE dashboards existentes e mantém outros indicadores."""
    d = raiz/'outputs'/'json'
    for ano_texto, dados in anos.items():
        if dados.get('status') != 'ok':
            continue
        ano = int(ano_texto)
        caminho = d/f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            log(f'  Dashboard de {ano} não encontrado; integração ignorada.')
            continue
        with caminho.open(encoding='utf-8-sig') as f:
            doc = json.load(f)
        if not isinstance(doc,dict) or not isinstance(doc.get('pages'),dict):
            raise ValueError(f'{caminho.name}: estrutura pages inválida.')
        socio = doc['pages'].setdefault('socioeconomic',{})
        if not isinstance(socio,dict):
            raise ValueError(f'{caminho.name}: pages.socioeconomic inválido.')
        rec = dados['recortes']
        bloco = {'indicator_id':'IND-043', 'year':ano,'status':'draft',
                 'population':'POP_SOCIO_VALID',
                 'source_questions':list(QUESTOES),
                 'national':rec['BR'],
                 'states':{uf:rec[uf] for uf in UFS},
                 'privacy_note': ('Contagens pequenas apenas sinalizadas. '
                                  'Revisar privacidade cruzada antes de divulgação.')}
        backup = caminho.with_suffix(caminho.suffix+'.bak_antes_ind043')
        if not backup.exists():
            shutil.copy2(caminho,backup)
        socio['parent_education_total'] = bloco
        salvar_json(caminho,doc)
        log(f'  Dashboard {ano}: IND-043 integrado com backup.')


def executar(base: Path, anos: tuple[int,...], bloco: int, somente_modulo: bool,
             sobrescrever: bool, saida: Path | None = None,
             sem_controle_populacao: bool = False) -> None:
    raiz = (saida or raiz_projeto()).resolve()
    arquivo_json = raiz/'outputs'/'json'/'IND_043_escolaridade_responsaveis_nota.json'
    arquivo_csv = raiz/'outputs'/'indicadores'/'IND_043_escolaridade_responsaveis_nota.csv'
    if not sobrescrever and (arquivo_json.exists() or arquivo_csv.exists()):
        raise FileExistsError('Saída IND-043 existente; use --sobrescrever.')
    fontes_esperadas: set[str] = set()
    for ano in anos:
        if ano <= 2023:
            fontes_esperadas.add(f'MICRODADOS_ENEM_{ano}.CSV')
        if ano == 2024:
            fontes_esperadas.update({'PARTICIPANTES_2024.CSV','COMPETENCIAS_REDACAO_2024.CSV'})
    caminhos = localizar_fontes(base.resolve(),fontes_esperadas) if fontes_esperadas else {}
    faltando = sorted(fontes_esperadas-set(caminhos))
    if faltando:
        raise FileNotFoundError(f'Arquivos ausentes em {base}: {faltando}. Use --base.')
    # --sobrescrever com --anos parcial não apaga anos anteriormente processados.
    anteriores: dict[str, Any] = {}
    if sobrescrever and arquivo_json.exists():
        with arquivo_json.open(encoding='utf-8-sig') as f:
            anterior = json.load(f)
        if anterior.get('indicator_id') != 'IND-043':
            raise ValueError('JSON existente não pertence ao IND-043.')
        anteriores = dict(anterior.get('years', {}))
    anos_dados: dict[str, Any] = anteriores
    anos_atualizados: dict[str, Any] = {}
    for ano in anos:
        if ano == 2025:
            anos_dados[str(ano)] = {'ano':ano,'status':'indisponivel',
                'reason': 'Sem chave pública para unir PARTICIPANTES_2025 a RESULTADOS_2025.',
                'recortes':{}}
            anos_atualizados[str(ano)] = anos_dados[str(ano)]
            log('  2025: cruzamento de escolaridade e nota indisponível (sem chave).')
            continue
        log(f'IND-043 | {ano}: iniciando Q001/Q002 × nota válida...')
        if ano <= 2023:
            hist,total,qa = processar_2019_2023(
                ano,caminhos[f'MICRODADOS_ENEM_{ano}.CSV'],bloco)
            fonte = f'MICRODADOS_ENEM_{ano}.csv'
        else:
            hist,total,qa = processar_2024(caminhos['PARTICIPANTES_2024.CSV'],
                                          caminhos['COMPETENCIAS_REDACAO_2024.CSV'],bloco)
            fonte = 'PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        rec,linhas = gerar_recortes(ano,hist,total,not sem_controle_populacao)
        status_confronto = comparar_ind041(ano,rec,raiz)
        log(f'  Confronto IND-041: {status_confronto}')
        anos_dados[str(ano)] = {'ano':ano,'status':'ok',
            'fonte':fonte,'populacao':'POP_SOCIO_VALID','n_brasil':total,
            'questoes':list(QUESTOES),'diagnostico_juncao':qa,
            'controle_ind041':status_confronto,'recortes':rec}
        anos_atualizados[str(ano)] = anos_dados[str(ano)]
    # Reconstituir CSV a partir do módulo consolidado, sem repetir linhas.
    linhas_csv: list[dict] = []
    for chave_ano, dados_ano in sorted(anos_dados.items(), key=lambda x: int(x[0])):
        if dados_ano.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            for pergunta in QUESTOES:
                itens = dados_ano['recortes'][uf]['questions'][pergunta]['categories']
                for item in itens:
                    linhas_csv.append({'ano':int(chave_ano),'uf':uf,
                        'questao':pergunta,'responsavel':RESPONSAVEIS[pergunta],**item})
    modulo = {
      'indicator_id':'IND-043',
      'titulo':'Escolaridade dos responsáveis × nota total da redação',
      'status':'draft','gerado_em_utc':datetime.now(timezone.utc).isoformat(),
      'anos_solicitados':list(anos),'anos_disponiveis':sorted(int(y) for y,d in anos_dados.items() if d.get('status')=='ok'),'population':'POP_SOCIO_VALID',
      'geography':'SG_UF_PROVA',
      'methodology':{
        'selection':'TP_STATUS_REDACAO=1 e 0<=NU_NOTA_REDACAO<=1000',
        'Q001':'Escolaridade do pai/homem responsável',
        'Q002':'Escolaridade da mãe/mulher responsável',
        'categories':'A–G níveis de escolaridade; H=Não sei; branco físico separado; código inválido separado',
        'quantile_method':'Hyndman-Fan tipo 7, interpolação linear sobre notas exatas',
        'sd_method':'desvio-padrão populacional',
        'n_small':'0 < N < 30: alerta, não supressão automática',
        'no_link_2025':True,
        'cautions':['Escolaridade é autorreferida pelo participante.',
                    'A categoria H não é nível ordinal de escolaridade.',
                    'Q001 e Q002 são marginais independentes, sem cruzamento entre si.',
                    'UF é local de aplicação da prova, não residência.',
                    'Série histórica conta participações, não pessoas únicas.',
                    'Associação descritiva não estabelece causalidade.',
                    'Revisão acadêmica e de privacidade contextual pendentes.']
      },'years':anos_dados}
    salvar_json(arquivo_json,modulo)
    salvar_csv(arquivo_csv,linhas_csv)
    log(f'IND-043 | JSON: {arquivo_json}')
    log(f'IND-043 | CSV: {arquivo_csv}')
    if not somente_modulo:
        atualizar_dashboards(raiz,anos_atualizados)
    log('IND-043 | Concluído.')


def main() -> None:
    parser = argparse.ArgumentParser(description='IND-043: escolaridade dos responsáveis × nota da redação.')
    parser.add_argument('--base',type=Path,default=raiz_projeto(),
                        help='Pasta com as bases, busca recursiva sem outputs.')
    parser.add_argument('--saida',type=Path,default=None,help='Raiz alternativa de outputs (testes).')
    parser.add_argument('--anos',nargs='+',type=int,default=list(ANOS))
    parser.add_argument('--bloco',type=int,default=100_000)
    parser.add_argument('--somente-modulo',action='store_true')
    parser.add_argument('--sobrescrever',action='store_true')
    parser.add_argument('--sem-controle-populacao',action='store_true',
                        help='SOMENTE para testes com arquivos sintéticos; não usar nas bases reais.')
    args = parser.parse_args()
    anos = tuple(sorted(set(args.anos)))
    if not anos or any(a not in ANOS for a in anos):
        parser.error(f'Anos permitidos: {ANOS[0]}–{ANOS[-1]}.')
    if args.bloco < 1:
        parser.error('--bloco deve ser >= 1.')
    try:
        executar(args.base,anos,args.bloco,args.somente_modulo,args.sobrescrever,
                 args.saida,args.sem_controle_populacao)
    except (ValueError,FileNotFoundError,FileExistsError,OSError,sqlite3.DatabaseError,
            json.JSONDecodeError) as e:
        print(f'ERRO IND-043: {e}',file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
