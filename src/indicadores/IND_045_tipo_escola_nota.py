#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-045 — Tipo de escola × nota da redação (Projeto Integrador IV / UNIVESP).

Catálogo ENEM 2019–2025 v2 | pages.socioeconomic.school_type_total
População: POP_SOCIO_VALID, igual à usada no IND-043 (TP_STATUS_REDACAO=1,
nota final 0..1000, C1..C5 válidas em 0..200). Geografia: SG_UF_PROVA.

IMPORTANTE — NÃO HARMONIZAR SEM FUNDAMENTAÇÃO:
  2019–2023: TP_ESCOLA = tipo de escola do ensino médio; códigos 1–4.
  2024: Q023 = trajetória escolar declarada; códigos A–F, incluindo bolsa.
  Esses conceitos/categorias NÃO são diretamente comparáveis entre anos.
  Q023 em 2019–2023 pergunta sobre telefone fixo, NÃO tipo de escola.
  2025: sem chave pública comum de vínculo entre a trajetória e a redação;
        ano indisponível neste indicador.

Resultados: N, média, mediana, Q1, Q3, IQR, desvio-padrão populacional por
categoria × UF × ano, e percentuais da POP_SOCIO_VALID. Quantis exatos HF7.

2019–23: MICRODADOS_ENEM_<ano>.csv, notas e TP_ESCOLA na mesma linha.
2024: PARTICIPANTES_2024.csv (Q023, UF, NU_INSCRICAO) +
      COMPETENCIAS_REDACAO_2024.csv (nota, status, competências, inscrição),
      unidos por NU_INSCRICAO em SQLite temporário, com checagem de unicidade.

Validação cruzada obrigatória: IND_043_escolaridade_responsaveis_nota.json,
com N por BR/UF e média total reconstruída a partir de Q001.

Arquivos de saída (sem .bak):
  outputs/json/IND_045_tipo_escola_nota.json
  outputs/indicadores/IND_045_tipo_escola_nota.csv
  outputs/json/dashboard_enem_<ano>.json (bloco school_type_total)

Para executar:
  python src/indicadores/IND_045_tipo_escola_nota.py --autoteste
  python src/indicadores/IND_045_tipo_escola_nota.py --anos 2024 --sobrescrever
  python src/indicadores/IND_045_tipo_escola_nota.py --sobrescrever

Proteção de publicação: suprime em todas as UFs/BR cada código que tiver
célula 1..29 em alguma UF; oculta uma categoria complementar no ano para
não revelar células suprimidas por diferença de totais nacionais/estaduais.
Mesmo assim, revisão de privacidade cruzada com OUTROS indicadores segue
obrigatória. Status das saídas: draft, não homologado para publicação pública.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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

ANOS = tuple(range(2019, 2026))
UFS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG',
       'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR',
       'RS', 'SC', 'SE', 'SP', 'TO')
NOTAS_COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
LIMIAR = 30
HIST_ESCOLA = {
    '1': 'Não respondeu', '2': 'Pública', '3': 'Privada', '4': 'Exterior',
}
Q023_ESCOLA = {
    'A': 'Somente escola pública',
    'B': 'Parte pública e parte privada sem bolsa integral',
    'C': 'Parte pública e parte privada com bolsa integral',
    'D': 'Somente escola privada sem bolsa integral',
    'E': 'Somente escola privada com bolsa integral',
    'F': 'Não frequentou ensino médio',
}
SEM_RESPOSTA = 'SEM_RESPOSTA'
INVALIDO = 'CODIGO_NAO_RECONHECIDO'
CAMPOS_CSV = (
    'ano', 'uf', 'variavel_origem', 'conceito', 'codigo_escola',
    'descricao_categoria', 'ordem', 'n_redacoes', 'media', 'mediana', 'q1',
    'q3', 'iqr', 'desvio_padrao', 'percentual_total_validas',
    'suprimido', 'motivo_supressao',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    p = Path(__file__).resolve()
    if p.parent.name.lower() == 'indicadores' and p.parent.parent.name.lower() == 'src':
        return p.parents[2]
    return Path.cwd().resolve()


def localizar_fontes(base: Path, nomes: set[str],
                    escolhas: dict[str, Path] | None = None) -> dict[str, Path]:
    """Aceita arquivos homônimos byte a byte idênticos, rejeita divergentes."""
    nomes = {x.upper() for x in nomes}
    escolhas = {x.upper(): Path(p) for x, p in (escolhas or {}).items()}
    ignorados = {'.git', '.venv', 'venv', 'outputs', '__pycache__',
                 'node_modules', '.pytest_cache', '.mypy_cache'}
    encontrados: dict[str, Path] = {}
    for nome, indicado in escolhas.items():
        if nome not in nomes:
            raise ValueError(f'Fonte explícita não solicitada: {nome}')
        origem = indicado.expanduser()
        if not origem.is_absolute():
            origem = base / origem
        origem = origem.resolve()
        if not origem.is_file():
            raise FileNotFoundError(f'Fonte selecionada não encontrada: {origem}')
        encontrados[nome] = origem
        log(f'  Fonte selecionada para {nome}: {origem}')
    for pasta, dirs, arquivos in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d.lower() not in ignorados)
        for nome in sorted(arquivos):
            chave = nome.upper()
            if chave not in nomes or chave in escolhas:
                continue
            novo = Path(pasta)/nome
            anterior = encontrados.get(chave)
            if anterior is None:
                encontrados[chave] = novo
            elif anterior.resolve() != novo.resolve():
                if filecmp.cmp(anterior, novo, shallow=False):
                    log(f'  Cópias idênticas de {chave}; usando {anterior}')
                else:
                    flag = ('--competencias-2024' if chave == 'COMPETENCIAS_REDACAO_2024.CSV'
                            else '--participantes-2024' if chave == 'PARTICIPANTES_2024.CSV'
                            else 'revise as cópias')
                    raise ValueError(f'Fontes diferentes para {chave}: {anterior} e {novo}. '
                                     f'Selecione com {flag}.')
    return encontrados


def ler_blocos(arquivo: Path, colunas: list[str], bloco: int):
    with arquivo.open('rb') as f:
        codificacao = 'utf-8-sig' if f.read(3) == b'\xef\xbb\xbf' else 'latin-1'
    col_existentes = pd.read_csv(arquivo, sep=';', encoding=codificacao, nrows=0).columns
    faltam = sorted(set(colunas) - set(str(x).strip().lstrip('\ufeff') for x in col_existentes))
    if faltam:
        raise ValueError(f'{arquivo.name}: colunas faltantes {faltam}')
    with pd.read_csv(arquivo, sep=';', encoding=codificacao,
                     dtype='string', usecols=colunas, chunksize=bloco,
                     keep_default_na=False, na_filter=False, low_memory=False) as leitor:
        for df in leitor:
            df.columns = [str(x).strip().lstrip('\ufeff') for x in df.columns]
            yield df


def notas_numericas(col: pd.Series, nome: str, low: float, high: float) -> np.ndarray:
    vals = pd.to_numeric(col.astype('string').str.strip().str.replace(',', '.', regex=False),
                         errors='coerce').to_numpy(dtype='float64')
    if not np.isfinite(vals).all() or ((vals < low) | (vals > high)).any():
        raise ValueError(f'{nome}: notas ausentes/não numéricas/fora de [{low},{high}] '
                         'em redações válidas.')
    return vals


def selecionar_validas(df: pd.DataFrame) -> pd.DataFrame:
    validas = df.loc[df['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')].copy()
    if validas.empty:
        return validas
    validas['__nota_total'] = notas_numericas(validas['NU_NOTA_REDACAO'], 'NU_NOTA_REDACAO', 0, 1000)
    for c in NOTAS_COMP:
        validas[c] = notas_numericas(validas[c], c, 0, 200)
    return validas


def codigo_escola(valor: Any, ano: int) -> str:
    txt = '' if valor is None else str(valor).strip().upper()
    if not txt or txt in ('NAN', 'NULL', '<NA>'):
        return SEM_RESPOSTA
    permitidos = HIST_ESCOLA if ano < 2024 else Q023_ESCOLA
    # Número decimal lido como string '2.0' deve ter mesma semântica de '2'.
    if ano < 2024 and txt.endswith('.0') and txt[:-2] in HIST_ESCOLA:
        txt = txt[:-2]
    return txt if txt in permitidos else INVALIDO


class Grupo:
    """Histograma exato esparso, sem manter as notas individuais."""
    def __init__(self) -> None:
        self.hist = Counter()
        self.n = 0
        self.n_soma_diferente = 0
        self.delta_soma = 0.0

    def adicionar(self, notas: np.ndarray, competencias: np.ndarray) -> None:
        if len(notas) != len(competencias):
            raise ValueError('Notas e competências desalinhadas.')
        self.n += len(notas)
        if not len(notas):
            return
        valores, quantidade = np.unique(notas, return_counts=True)
        self.hist.update({float(v): int(n) for v, n in zip(valores, quantidade)})
        diffs = competencias.sum(axis=1) - notas
        self.n_soma_diferente += int(np.count_nonzero(~np.isclose(diffs, 0, atol=1e-6, rtol=0)))
        self.delta_soma += float(math.fsum(diffs.tolist()))

    def combinar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        self.hist.update(outro.hist)
        self.n_soma_diferente += outro.n_soma_diferente
        self.delta_soma += outro.delta_soma


def acumular(grupos: dict, df: pd.DataFrame, ano: int) -> None:
    if df.empty:
        return
    ufs = df['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~ufs.isin(UFS)).any():
        raise ValueError('UF da prova inválida ou ausente.')
    codes = df['__escola'].map(lambda v: codigo_escola(v, ano))
    total = df['__nota_total'].to_numpy(dtype='float64')
    comps = df[list(NOTAS_COMP)].to_numpy(dtype='float64')
    estrutura = pd.DataFrame({'uf': ufs.to_numpy(), 'codigo': codes.to_numpy()})
    for (uf, cod), pos in estrutura.groupby(['uf', 'codigo'], sort=False).indices.items():
        grupos[(str(uf), str(cod))].adicionar(total[pos], comps[pos])


def ler_mesma_linha(arquivo: Path, ano: int, bloco: int) -> tuple[dict, int, dict]:
    if ano >= 2024:
        raise ValueError('TP_ESCOLA só é utilizado no IND-045 de 2019 a 2023.')
    grupos = defaultdict(Grupo)
    n_validas = 0
    colunas = ['SG_UF_PROVA', 'TP_ESCOLA', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *NOTAS_COMP]
    for lote in ler_blocos(arquivo, colunas, bloco):
        validas = selecionar_validas(lote)
        n_validas += len(validas)
        if validas.empty:
            continue
        validas['__escola'] = validas['TP_ESCOLA']
        acumular(grupos, validas, ano)
    return dict(grupos), n_validas, {'metodo': 'mesma_linha', 'variavel_origem': 'TP_ESCOLA'}


def ler_2024(participantes: Path, competencias: Path, bloco: int) -> tuple[dict, int, dict]:
    """Junção 2024 por inscrição com preservação da posição de cada redação."""
    grupos = defaultdict(Grupo)
    with tempfile.TemporaryDirectory(prefix='enem_ind045_') as pasta:
        db = sqlite3.connect(str(Path(pasta)/'join.sqlite3'))
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE participantes(id TEXT PRIMARY KEY, uf TEXT NOT NULL, escola TEXT NOT NULL) WITHOUT ROWID')
            db.execute('CREATE TABLE vistas(id TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE lote(pos INTEGER PRIMARY KEY, id TEXT NOT NULL)')
            n_participantes = 0
            for parte in ler_blocos(participantes, ['NU_INSCRICAO', 'SG_UF_PROVA', 'Q023'], bloco):
                ids = parte['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = parte['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                escolas = parte['Q023'].astype('string').str.strip().tolist()
                if any(not v for v in ids) or any(uf not in UFS for uf in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    db.executemany('INSERT INTO participantes VALUES (?,?,?)', zip(ids, ufs, escolas))
                except sqlite3.IntegrityError as e:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from e
                n_participantes += len(ids)
            db.commit()
            log(f'  2024: {n_participantes:,} participantes indexados.')
            n_validas = 0
            n_vinculadas = 0
            cols = ['NU_INSCRICAO', 'TP_STATUS_REDACAO', 'NU_NOTA_REDACAO', *NOTAS_COMP]
            for parte in ler_blocos(competencias, cols, bloco):
                validas = selecionar_validas(parte)
                n_validas += len(validas)
                if validas.empty:
                    continue
                ids = validas['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not v for v in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em redação válida.')
                try:
                    db.executemany('INSERT INTO vistas VALUES (?)', ((v,) for v in ids))
                except sqlite3.IntegrityError as e:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição duplicada em redações válidas.') from e
                db.execute('DELETE FROM lote')
                db.executemany('INSERT INTO lote VALUES (?,?)', enumerate(ids))
                vinculadas = db.execute('''SELECT l.pos, p.uf, p.escola
                     FROM lote l INNER JOIN participantes p ON p.id=l.id''').fetchall()
                if len(vinculadas) != len(ids):
                    raise ValueError(f'2024: {len(ids)-len(vinculadas)} redações válidas sem correspondência.')
                attrs = [None]*len(ids)
                for pos, uf, escola in vinculadas:
                    attrs[pos] = (uf, escola)
                validas = validas.copy()
                validas['SG_UF_PROVA'] = [x[0] for x in attrs]
                validas['__escola'] = [x[1] for x in attrs]
                acumular(grupos, validas, 2024)
                n_vinculadas += len(ids)
                db.commit()
            return dict(grupos), n_validas, {
                'metodo': 'join_NU_INSCRICAO',
                'n_participantes': n_participantes,
                'n_redacoes_validas_vinculadas': n_vinculadas,
                'n_validas_sem_correspondencia': 0,
                'chave_unica_participantes': True,
                'chave_unica_redacoes_validas': True,
                'variavel_origem': 'Q023',
            }
        finally:
            db.close()


def criar_brasil(grupos: dict) -> dict:
    brasil = defaultdict(Grupo)
    for (uf, cod), item in grupos.items():
        if uf not in UFS:
            raise ValueError(f'UF inesperada: {uf}')
        brasil[('BR', cod)].combinar(item)
    return {**grupos, **brasil}


def quantil_hf7(hist: Counter, p: float) -> float:
    if not 0 <= p <= 1:
        raise ValueError('Percentil deve estar no intervalo [0,1].')
    n = sum(hist.values())
    if n == 0:
        raise ValueError('Não há quantis para N=0.')
    valores = sorted(hist)
    acumuladas = np.cumsum([hist[x] for x in valores], dtype=np.int64)
    def obter(rank: int) -> float:
        return float(valores[int(np.searchsorted(acumuladas, rank + 1, side='left'))])
    lugar = (n-1)*p
    i = int(math.floor(lugar))
    j = min(i+1,n-1)
    return (1-(lugar-i))*obter(i) + (lugar-i)*obter(j)


def estatisticas(hist: Counter, n: int) -> dict:
    if n == 0:
        return {key: None for key in ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')}
    if sum(hist.values()) != n:
        raise ValueError('N do histograma divergente da categoria.')
    media = math.fsum(float(v)*f for v, f in hist.items())/n
    var = math.fsum((float(v)-media)**2*f for v,f in hist.items())/n
    q1, med, q3 = [quantil_hf7(hist,p) for p in (0.25,0.5,0.75)]
    return {'media': round(media,4), 'mediana': round(med,4),
            'q1': round(q1,4), 'q3': round(q3,4),
            'iqr': round(q3-q1,4), 'desvio_padrao': round(math.sqrt(max(var,0)),4)}


def ler_referencia(base: Path, caminho: Path | None = None) -> dict:
    p = caminho or base/'outputs'/'json'/'IND_043_escolaridade_responsaveis_nota.json'
    if caminho is not None and not p.is_absolute():
        p = base/p
    if not p.is_file():
        raise FileNotFoundError('IND-043 é necessário para validar o mesmo universo de redações: '+str(p))
    doc = json.loads(p.read_text(encoding='utf-8-sig'))
    if doc.get('indicator_id') != 'IND-043' or doc.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência esperada: JSON do IND-043 com POP_SOCIO_VALID.')
    return doc


def conferir_montar(ano: int, grupos: dict, n_validas: int, referencia: dict) -> tuple[dict, dict]:
    referencia_ano = referencia.get('years',{}).get(str(ano),{})
    if referencia_ano.get('status') != 'ok':
        raise ValueError(f'IND-043/{ano} não está disponível para a validação do IND-045.')
    ref = referencia_ano['recortes']
    if set(ref) != {'BR',*UFS}:
        raise ValueError('IND-043: referência deveria conter Brasil e 27 UFs.')
    if ref['BR']['n_pop_socio_valid'] != n_validas:
        raise ValueError(f'{ano}: população válida={n_validas} difere IND-043 '
                         f'({ref["BR"]["n_pop_socio_valid"]}).')
    categorias_basicas = HIST_ESCOLA if ano < 2024 else Q023_ESCOLA
    codigos = [*categorias_basicas, SEM_RESPOSTA, INVALIDO]
    # Não criar uma escala fictícia entre TP_ESCOLA e Q023.
    variavel = 'TP_ESCOLA' if ano < 2024 else 'Q023'
    conceito = ('Tipo de escola do Ensino Médio (variável administrativa)'
                if ano < 2024 else 'Trajetória declarada entre escola pública/privada/bolsa')
    for uf in ('BR',*UFS):
        r = ref[uf]
        if r['n_pop_socio_valid'] != sum(grupos.get((uf,c),Grupo()).n for c in codigos):
            raise ValueError(f'{ano}/{uf}: soma categorias de escola != POP_SOCIO_VALID IND-043.')
        inesperados = [c for geo,c in grupos if geo == uf and c not in codigos]
        if inesperados:
            raise ValueError(f'{ano}/{uf}: códigos de escola inesperados: {inesperados}')
        # Q001 do IND-043 funciona como referência INDEPENDENTE da média
        # total: são outras categorias, mas a população é a mesma.
        qs = r['questions']['Q001']['categories']
        nref = sum(x['n_redacoes'] for x in qs)
        if nref != r['n_pop_socio_valid']:
            raise ValueError(f'{ano}/{uf}: Q001 IND-043 não fecha população.')
        soma_notas_ref = math.fsum(x['n_redacoes']*x['media'] for x in qs if x['n_redacoes'])
        soma_notas_escola = math.fsum(float(v)*n for c in codigos
                       for v,n in grupos.get((uf,c),Grupo()).hist.items())
        media_escola = soma_notas_escola/r['n_pop_socio_valid'] if r['n_pop_socio_valid'] else 0
        media_ref = soma_notas_ref/nref if nref else 0
        if not math.isclose(media_escola,media_ref,rel_tol=0,abs_tol=0.00015):
            raise ValueError(f'{ano}/{uf}: média escolar {media_escola} difere do IND-043 {media_ref}.')

    # Uma categoria pequena em qualquer UF torna a categoria inteira oculta,
    # inclusive BR, para impedir recuperação geográfica por subtração.
    # Uma segunda categoria é ocultada em todas as UFs como complemento.
    pequeno = {c for c in codigos if any(
        0 < grupos.get((uf,c),Grupo()).n < LIMIAR for uf in ('BR',*UFS))}
    motivos = {c:'primaria_grupo_pequeno_em_alguma_uf' for c in pequeno}
    if pequeno:
        elegiveis = [c for c in codigos if c not in pequeno
                     and grupos.get(('BR',c),Grupo()).n >= LIMIAR]
        if elegiveis:
            # Não ocultar categorias principais sempre que resposta não informada
            # for suficiente para cumprir a regra complementar.
            preferencia = [SEM_RESPOSTA, INVALIDO, '1', 'F', '4', 'C', 'B', 'E', 'D', '3', '2', 'A']
            complemento = next((c for c in preferencia if c in elegiveis), elegiveis[0])
            motivos[complemento] = 'complementar_contra_inferencia_por_totais'
        else:
            # Se todas as categorias estiverem ocultas, não é necessário complementar.
            if not all(grupos.get(('BR',c),Grupo()).n == 0 or c in motivos for c in codigos):
                raise ValueError(f'{ano}: não há categoria elegível para supressão complementar.')

    recortes = {}
    supressas = 0
    for uf in ('BR',*UFS):
        n_uf = ref[uf]['n_pop_socio_valid']
        cats = []
        for ordem,c in enumerate(codigos):
            g = grupos.get((uf,c),Grupo())
            motivo = motivos.get(c)
            suprimido = motivo is not None
            supressas += bool(suprimido)
            cats.append({
                'codigo_escola': c,
                'descricao_categoria': (categorias_basicas.get(c)
                     if c in categorias_basicas else
                     'Não informado' if c == SEM_RESPOSTA else 'Código não reconhecido'),
                'ordem': ordem,
                'n_redacoes': None if suprimido else g.n,
                **({k:None for k in ('media','mediana','q1','q3','iqr','desvio_padrao')}
                   if suprimido else estatisticas(g.hist,g.n)),
                'percentual_total_validas': None if suprimido or not n_uf
                    else round(100*g.n/n_uf,6),
                'suprimido': suprimido,
                'motivo_supressao': motivo,
            })
        recortes[uf] = {
            'uf': uf, 'population':'POP_SOCIO_VALID', 'variavel_origem':variavel,
            'conceito':conceito, 'n_pop_socio_valid':n_uf,
            'categories': cats,
            'status_publicacao':'draft_revisao_academica_privacidade_cruzada_pendente',
        }
    # Registros divergentes referem-se a uma redação; somados por BR apenas.
    divergencias = sum(grupos.get(('BR',c),Grupo()).n_soma_diferente for c in codigos)
    qa = {
        'populacao_e_medias_uf_br_conferidas_com_ind043':True,
        'referencia_ind043':'IND-043',
        'variavel_origem':variavel, 'conceito_harmonizavel_entre_anos':False,
        'n_pop_socio_valid_brasil':n_validas,
        'n_soma_competencias_divergente':divergencias,
        'categorias_suprimidas_globalmente':motivos,
        'n_celulas_geograficas_suprimidas':supressas,
        'revisao_privacidade_cruzada_pendente':True,
    }
    return recortes,qa


def salvar_json(caminho:Path,conteudo:Any)->None:
    caminho.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=caminho.parent,
                                         prefix=caminho.name+'.',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            json.dump(conteudo,f,indent=2,ensure_ascii=False,allow_nan=False)
            f.write('\n')
        os.replace(temp,caminho)
    finally:
        if temp:temp.unlink(missing_ok=True)


def salvar_csv(caminho:Path,linhas:list[dict])->None:
    caminho.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',dir=caminho.parent,
                                         prefix=caminho.name+'.',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            escritor=csv.DictWriter(f,fieldnames=CAMPOS_CSV,delimiter=';',extrasaction='ignore')
            escritor.writeheader();escritor.writerows(linhas)
        os.replace(temp,caminho)
    finally:
        if temp:temp.unlink(missing_ok=True)


def linhas_csv(todos:dict)->list[dict]:
    linhas=[]
    for ano,obj in sorted(todos.items(),key=lambda p:int(p[0])):
        if obj.get('status')!='ok':continue
        for uf in ('BR',*UFS):
            rec=obj['recortes'][uf]
            for cat in rec['categories']:
                linhas.append({'ano':int(ano),'uf':uf,
                    'variavel_origem':rec['variavel_origem'],'conceito':rec['conceito'],
                    **cat})
    return linhas


def integrar_dashboards(saida:Path,processados:dict[str,dict])->None:
    for chave,obj in sorted(processados.items(),key=lambda p:int(p[0])):
        if obj.get('status')!='ok':continue
        ano=int(chave)
        arq=saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        if not arq.is_file():
            log(f'  Dashboard {ano} ausente; integração ignorada.')
            continue
        doc=json.loads(arq.read_text(encoding='utf-8-sig'))
        socio=doc.get('pages',{}).get('socioeconomic')
        if not isinstance(socio,dict):
            raise ValueError(f'{arq.name}: pages.socioeconomic não é objeto.')
        rec=obj['recortes']
        socio['school_type_total']={
            'indicator_id':'IND-045','status':'draft',
            'population':'POP_SOCIO_VALID','year':ano,
            'source_variable':obj['variavel_origem'],
            'concept':obj['conceito'],
            'comparability_across_years':'not_directly_comparable_2019_2023_vs_2024',
            'national':rec['BR'],
            'states':{uf:rec[uf] for uf in UFS},
            'method':'média, mediana, Q1, Q3, IQR e N por categoria/UF',
            'privacy_note':'Supressão de grupos pequenos e complementar; revisão cruzada pendente.',
        }
        doc.setdefault('quality',{})['ind045_validation']={'status':'ok_agregados',**obj['validacao'],
            'revisao_academica_pendente':True}
        aviso=('IND-045: TP_ESCOLA (2019–2023) não é conceitualmente equivalente a '
               'Q023 (2024); categorias pequenas e complementares suprimidas; revisão cruzada pendente.')
        warns=doc.setdefault('meta',{}).setdefault('warnings',[])
        if aviso not in warns:warns.append(aviso)
        salvar_json(arq,doc)
        log(f'  Dashboard {ano} integrado sem .bak.')


def executar(base:Path,saida:Path,anos:tuple[int,...],bloco:int,
             sobrescrever:bool,somente_modulo:bool,
             referencia_path:Path|None=None,
             escolhas:dict[str,Path]|None=None)->dict:
    base,saida=base.resolve(),saida.resolve()
    out_json=saida/'outputs'/'json'/'IND_045_tipo_escola_nota.json'
    out_csv=saida/'outputs'/'indicadores'/'IND_045_tipo_escola_nota.csv'
    if (out_json.exists() or out_csv.exists()) and not sobrescrever:
        raise FileExistsError('IND-045 já existe, use --sobrescrever.')
    referencia=ler_referencia(base,referencia_path)
    nomes=set()
    for ano in anos:
        if ano<=2023:nomes.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano==2024:nomes.update({'PARTICIPANTES_2024.CSV','COMPETENCIAS_REDACAO_2024.CSV'})
    fontes=localizar_fontes(base,nomes,escolhas)
    faltantes=sorted(nomes-set(fontes))
    if faltantes:raise FileNotFoundError(f'Fontes ausentes: {faltantes}. Use --base.')
    anteriores={}
    if sobrescrever and out_json.is_file():
        doc=json.loads(out_json.read_text(encoding='utf-8-sig'))
        if doc.get('indicator_id')!='IND-045':
            raise ValueError('JSON existente não pertence ao IND-045.')
        anteriores=dict(doc.get('years',{}))
    todos=dict(anteriores)
    processados={}
    for ano in anos:
        log(f'IND-045 | {ano}: tipo de escola × nota em POP_SOCIO_VALID...')
        if ano==2025:
            obj={'ano':ano,'status':'indisponivel',
                 'reason':'Sem chave pública de vínculo de 2025 entre trajetória escolar e nota da redação.',
                 'recortes':{}}
            todos[str(ano)]=processados[str(ano)]=obj
            log('  2025 indisponível; nenhuma estatística estimada.')
            continue
        if ano==2024:
            grupos, n_validas,diag=ler_2024(fontes['PARTICIPANTES_2024.CSV'],
                                             fontes['COMPETENCIAS_REDACAO_2024.CSV'],bloco)
        else:
            grupos,n_validas,diag=ler_mesma_linha(fontes[f'MICRODADOS_ENEM_{ano}.CSV'],ano,bloco)
        grupos=criar_brasil(grupos)
        rec,qa=conferir_montar(ano,grupos,n_validas,referencia)
        if diag.get('n_redacoes_validas_vinculadas',n_validas)!=n_validas:
            raise ValueError(f'{ano}: junção de redações válidas não fecha.')
        var='Q023' if ano==2024 else 'TP_ESCOLA'
        conceito=('Trajetória escolar autodeclarada' if ano==2024
                  else 'Tipo de escola do ensino médio')
        obj={'ano':ano,'status':'ok','population':'POP_SOCIO_VALID',
             'variavel_origem':var,'conceito':conceito,
             'n_brasil':n_validas,'diagnostico_fonte':diag,
             'validacao':qa,'recortes':rec}
        todos[str(ano)]=processados[str(ano)]=obj
        log(f'  N BR={n_validas:,}; categorias globais ocultas: '
            f'{list(qa["categorias_suprimidas_globalmente"])}.')
    modulo={
        'indicator_id':'IND-045','titulo':'Tipo de escola × nota total',
        'population':'POP_SOCIO_VALID','status':'draft',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'anos_solicitados':list(anos),
        'anos_disponiveis':sorted(int(x) for x,d in todos.items() if d.get('status')=='ok'),
        'geography':'SG_UF_PROVA',
        'methodology':{
            'population':'TP_STATUS_REDACAO=1; nota 0..1000; C1..C5 em 0..200',
            '2019_2023_source_variable':'TP_ESCOLA',
            '2024_source_variable':'Q023',
            'comparability':'TP_ESCOLA ≠ Q023; não unir grupos de edições diferentes como equivalentes',
            'aggregation':'média, mediana, Q1, Q3, IQR, DP populacional, N, percentual por ano/UF/categoria',
            'quantiles':'Hyndman-Fan tipo 7',
            'reference':'IND-043 para POP_SOCIO_VALID e média da nota por UF',
            '2024_join':'NU_INSCRICAO com controle de unicidade e correspondência',
            '2025':'indisponível por ausência de chave pública de vínculo',
            'privacy':'supressão por categoria anual global BR/UF e complementar; revisão cruzada pendente',
            'notes':['O código TP_ESCOLA=1 significa não respondeu, não escola pública.',
                     'Q023=F significa não frequentou ensino médio, não é dado ausente.',
                     'Resultados descritivos, não causais.',
                     'Números dos anos são participações, não candidatos únicos.',
                     'UF da prova não implica UF de residência.'],
        },
        'years':todos,
    }
    salvar_json(out_json,modulo)
    salvar_csv(out_csv,linhas_csv(todos))
    log(f'JSON: {out_json}\nCSV: {out_csv}')
    if not somente_modulo:integrar_dashboards(saida,processados)
    log('IND-045 concluído em draft.')
    return modulo


def autoteste()->None:
    """Testes sintéticos: quantis, denominadores, Q023, join e dashboard."""
    import tempfile as _tempfile
    rng=np.random.default_rng(45)
    for _ in range(120):
        arr=rng.choice([0.,40.,120.,160.,200.,400.,600.,800.,960.,1000.],
                       size=int(rng.integers(1,70)),replace=True)
        h=Counter(float(v) for v in arr)
        x=estatisticas(h,len(arr))
        for p,k in [(0.25,'q1'),(0.5,'mediana'),(0.75,'q3')]:
            assert abs(x[k]-np.quantile(arr,p,method='linear'))<=0.00011
        assert abs(x['media']-arr.mean())<=0.00011
        assert abs(x['desvio_padrao']-arr.std(ddof=0))<=0.00011
    assert codigo_escola('1',2019)=='1'
    assert codigo_escola('A',2024)=='A'
    assert codigo_escola('F',2024)=='F'
    assert codigo_escola('',2024)==SEM_RESPOSTA
    assert codigo_escola('A',2019)==INVALIDO
    assert codigo_escola('2',2024)==INVALIDO
    # Célula pequena em uma UF: ocultar a categoria em todo o ano e
    # suprimir uma segunda categoria para impedir reconstrução por totais.
    grupos_t = defaultdict(Grupo)
    for uf in UFS:
        base = {'A': 40, 'B': 50, 'C': 1 if uf == 'SP' else 0}
        for code, qtd in base.items():
            if qtd:
                notas = np.full(qtd, 600., dtype='float64')
                comps = np.full((qtd, 5), 120., dtype='float64')
                grupos_t[(uf, code)].adicionar(notas, comps)
    grupos_t = criar_brasil(grupos_t)
    rec_ref_t = {}
    for uf in ('BR', *UFS):
        n = sum(grupos_t.get((uf, c), Grupo()).n for c in Q023_ESCOLA)
        rec_ref_t[uf] = {'n_pop_socio_valid': n, 'questions': {
            'Q001': {'categories': [{'n_redacoes': n, 'media': 600.0}]}}}
    ref_t = {'years': {'2024': {'status': 'ok', 'recortes': rec_ref_t}}}
    rec_t, qa_t = conferir_montar(2024, grupos_t, rec_ref_t['BR']['n_pop_socio_valid'], ref_t)
    assert 'C' in qa_t['categorias_suprimidas_globalmente']
    assert len(qa_t['categorias_suprimidas_globalmente']) >= 2
    assert rec_t['BR']['categories'][2]['n_redacoes'] is None
    assert rec_t['SP']['categories'][2]['media'] is None
    with _tempfile.TemporaryDirectory(prefix='teste_ind045_') as d:
        raiz=Path(d)
        (raiz/'data'/'raw'/'2024'/'competencias_redacao').mkdir(parents=True)
        (raiz/'outputs'/'json').mkdir(parents=True)
        linhas=[]
        for i in range(len(UFS)*40):
            uf=UFS[i//40]
            nota=int([600,640,680,720,760][i%5])
            # notas de competências somam nota total, no intervalo 0..200.
            comps=[nota/5]*5
            linhas.append({'NU_INSCRICAO':str(i+100),
                'SG_UF_PROVA':uf,'TP_ESCOLA':['1','2','3','4'][i%4],
                'Q023':list(Q023_ESCOLA)[i%6],
                'TP_STATUS_REDACAO':'1','NU_NOTA_REDACAO':str(nota),
                **{c:str(comps[j]) for j,c in enumerate(NOTAS_COMP)}})
        df=pd.DataFrame(linhas)
        df.drop(columns=['NU_INSCRICAO','Q023']).to_csv(
            raiz/'data'/'raw'/'2024'/'MICRODADOS_ENEM_2019.csv',sep=';',index=False)
        df[['NU_INSCRICAO','SG_UF_PROVA','Q023']].iloc[::-1].to_csv(
            raiz/'data'/'raw'/'2024'/'PARTICIPANTES_2024.csv',sep=';',index=False)
        df[['NU_INSCRICAO','TP_STATUS_REDACAO','NU_NOTA_REDACAO',*NOTAS_COMP]].to_csv(
            raiz/'data'/'raw'/'2024'/'COMPETENCIAS_REDACAO_2024.csv',sep=';',index=False)
        src=raiz/'data'/'raw'/'2024'/'COMPETENCIAS_REDACAO_2024.csv'
        dup=raiz/'data'/'raw'/'2024'/'competencias_redacao'/'COMPETENCIAS_REDACAO_2024.csv'
        dup.write_bytes(src.read_bytes())
        assert len(localizar_fontes(raiz,{'COMPETENCIAS_REDACAO_2024.CSV'}))==1
        g19,n19,_=ler_mesma_linha(raiz/'data'/'raw'/'2024'/'MICRODADOS_ENEM_2019.csv',2019,97)
        g24,n24,diag=ler_2024(raiz/'data'/'raw'/'2024'/'PARTICIPANTES_2024.csv',src,97)
        assert n19==n24==len(df)==len(UFS)*40
        assert diag['n_redacoes_validas_vinculadas']==len(df)
        assert sum(g.n for g in g24.values())==len(df)
        # referência sintética compatível com o contrato do IND-043
        def ind043_rec(uf,n):
            m=float(df['NU_NOTA_REDACAO'].astype(float).mean())
            return {'uf':uf,'n_pop_socio_valid':n,'questions':{
                'Q001':{'categories':[{'codigo_escolaridade':'A',
                    'n_redacoes':n,'media':m}]}}}
        ref={'indicator_id':'IND-043','population':'POP_SOCIO_VALID','years':{}}
        for ano in (2019,2024):
            ref['years'][str(ano)]={'status':'ok','recortes':{
                'BR':ind043_rec('BR',len(df)),
                **{uf:ind043_rec(uf,40) for uf in UFS}}}
        salvar_json(raiz/'outputs'/'json'/'IND_043_escolaridade_responsaveis_nota.json',ref)
        for ano in (2019,2024):
            salvar_json(raiz/'outputs'/'json'/f'dashboard_enem_{ano}.json',
                {'pages':{'socioeconomic':{'outro_indicador':'preservar'}},
                 'quality':{'outro_controle':'preservar'},'meta':{'warnings':[]}})
        out=executar(raiz,raiz,(2019,2024,2025),97,True,False)
        assert out['years']['2025']['status']=='indisponivel'
        assert out['years']['2019']['recortes']['BR']['variavel_origem']=='TP_ESCOLA'
        assert out['years']['2024']['recortes']['BR']['variavel_origem']=='Q023'
        for ano in (2019,2024):
            d=json.loads((raiz/'outputs'/'json'/f'dashboard_enem_{ano}.json').read_text())
            assert d['pages']['socioeconomic']['school_type_total']['indicator_id']=='IND-045'
            assert d['pages']['socioeconomic']['outro_indicador']=='preservar'
            assert d['quality']['outro_controle']=='preservar'
        assert not list(raiz.rglob('*.bak*'))
        with (raiz/'outputs'/'indicadores'/'IND_045_tipo_escola_nota.csv').open(
                encoding='utf-8-sig',newline='') as arq:
            assert len(list(csv.DictReader(arq,delimiter=';')))==28*(len(HIST_ESCOLA)+2+len(Q023_ESCOLA)+2)
    log('Autoteste IND-045 aprovado: quantis, TP_ESCOLA/Q023, join, duplicatas, 2025 e dashboard.')


def main()->None:
    p=argparse.ArgumentParser(description='IND-045 — Tipo de escola × nota total')
    p.add_argument('--base',type=Path,default=raiz_projeto())
    p.add_argument('--saida',type=Path,default=raiz_projeto())
    p.add_argument('--referencia-ind043',type=Path,default=None)
    p.add_argument('--anos',type=int,nargs='+',default=list(ANOS))
    p.add_argument('--bloco',type=int,default=100_000)
    p.add_argument('--sobrescrever',action='store_true')
    p.add_argument('--somente-modulo',action='store_true')
    p.add_argument('--competencias-2024',type=Path,default=None)
    p.add_argument('--participantes-2024',type=Path,default=None)
    p.add_argument('--autoteste',action='store_true')
    args=p.parse_args()
    if args.autoteste:
        autoteste();return
    anos=tuple(sorted(set(args.anos)))
    if not anos or any(y not in ANOS for y in anos):p.error('--anos: use 2019..2025.')
    if args.bloco<1:p.error('--bloco deve ser positivo.')
    escolhas={}
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV']=args.competencias_2024
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV']=args.participantes_2024
    try:
        executar(args.base,args.saida,anos,args.bloco,args.sobrescrever,
                 args.somente_modulo,args.referencia_ind043,escolhas)
    except (OSError,ValueError,KeyError,sqlite3.DatabaseError,json.JSONDecodeError) as erro:
        print(f'ERRO IND-045: {erro}',file=sys.stderr);sys.exit(1)


if __name__=='__main__':
    main()
