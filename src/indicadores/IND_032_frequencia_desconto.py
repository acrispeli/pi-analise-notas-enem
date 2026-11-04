#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-032 | Frequência de desconto por competência — ENEM 2019–2025.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores v2.

POP_NEAR = redações com TP_STATUS_REDACAO=1, nota válida e
900 <= NU_NOTA_REDACAO <= 980 (inclusive; não inclui nota 1000).

Para cada C1..C5: n_com_desconto = COUNT(NU_NOTA_COMPi < 200)
                  frequencia = n_com_desconto / n_near.
São cinco eventos binários INDEPENDENTES; percentuais C1..C5 não somam 100%.

Fontes esperadas:
  2019–2023: MICRODADOS_ENEM_<ANO>.csv (mesma linha para UF e notas)
  2024: PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv
        junção EXCLUSIVA por NU_INSCRICAO, usando SQLite temporário
  2025: RESULTADOS_2025.csv (UF e competências no mesmo arquivo)

As saídas públicas NÃO divulgam contagem/percentual de células binárias
menores que 30, nem de seu complemento, e aplicam supressão secundária
para impedir reconstrução por BR - soma(UFs). A avaliação de privacidade
cruzada com outros indicadores continua obrigatória antes de publicar.

Uso (na raiz do repositório):
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_032_frequencia_desconto.py --anos 2024 --sobrescrever
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_032_frequencia_desconto.py --sobrescrever
  .\\.venv\\Scripts\\python.exe src\\indicadores\\IND_032_frequencia_desconto.py --anos 2024 --competencias-2024 data/raw/2024/competencias_redacao/COMPETENCIAS_REDACAO_2024.csv --sobrescrever

Saídas:
  outputs/json/IND_032_frequencia_desconto.json
  outputs/indicadores/IND_032_frequencia_desconto.csv
  outputs/json/dashboard_enem_<ano>.json (se existente)

Não cria arquivos .bak por padrão; operações de escrita são atômicas.
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

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MG','MS','MT',
       'PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
NOTAS_COMP = tuple(f'NU_NOTA_COMP{i}' for i in range(1, 6))
N_MINIMO = 1
CONTROLE_POP_NEAR = {
    2019: 172_548, 2020: 183_343, 2021: 163_747, 2022: 197_083,
    2023: 288_602, 2024: 291_111, 2025: 173_533,
}
# O dashboard 2024 não substitui a fonte individual para o IND-032.


def log(msg: str) -> None:
    print(msg, flush=True)


def raiz_projeto() -> Path:
    arq = Path(__file__).resolve()
    if arq.parent.name.lower() == 'indicadores' and arq.parent.parent.name.lower() == 'src':
        return arq.parents[2]
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
    with caminho.open('rb') as f:
        tem_bom = f.read(3) == b'\xef\xbb\xbf'
    encoding = 'utf-8-sig' if tem_bom else 'latin-1'
    cabecalho = pd.read_csv(caminho, sep=';', encoding=encoding, nrows=0)
    existentes = {str(c).strip().lstrip('\ufeff') for c in cabecalho.columns}
    faltantes = sorted(set(colunas) - existentes)
    if faltantes:
        raise ValueError(f'{caminho.name}: faltam colunas {faltantes}.')
    with pd.read_csv(caminho, sep=';', encoding=encoding, dtype='string',
                     usecols=colunas, chunksize=tamanho,
                     keep_default_na=False, na_filter=False, low_memory=False) as leitor:
        for df in leitor:
            df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
            yield df


def notas_numericas(x: pd.Series, nome: str) -> pd.Series:
    valores = pd.to_numeric(x.astype('string').str.strip().str.replace(',', '.', regex=False),
                            errors='coerce')
    # isfinite evita aceitar strings convertidas em inf.
    import numpy as np
    if (~np.isfinite(valores)).any():
        raise ValueError(f'{nome}: nota ausente, não numérica ou infinita.')
    return valores.astype('float64')


def preparar_lote(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    elegiveis = df['TP_STATUS_REDACAO'].astype('string').str.strip().eq('1')
    validas = df.loc[elegiveis].copy()
    if validas.empty:
        return validas, 0
    validas['nota_total'] = notas_numericas(validas['NU_NOTA_REDACAO'], 'NU_NOTA_REDACAO')
    if (~validas['nota_total'].between(0, 1000)).any():
        raise ValueError('TP_STATUS_REDACAO=1 com nota total fora de [0,1000].')
    n_validas = len(validas)
    near = validas.loc[validas['nota_total'].between(900, 980)].copy()
    if near.empty:
        return near, n_validas
    for c in NOTAS_COMP:
        near[c] = notas_numericas(near[c], c)
        if (~near[c].between(0, 200)).any():
            raise ValueError(f'{c}: nota de competência fora de [0,200].')
    return near, n_validas


def novo_contador() -> dict[str, Any]:
    return {'n': 0, 'sim': [0]*5, 'divergencia_soma': 0}


def incrementar(contagem: dict[str, dict], uf: str, flags: tuple[int,...],
                 n: int, soma_divergente: int = 0) -> None:
    for geo in ('BR', uf):
        dest = contagem[geo]
        dest['n'] += n
        for i, v in enumerate(flags):
            dest['sim'][i] += v*n
        dest['divergencia_soma'] += soma_divergente


def acumular_df(contagem: dict, near: pd.DataFrame) -> None:
    if near.empty:
        return
    near = near.copy()
    near['uf'] = near['SG_UF_PROVA'].astype('string').str.strip().str.upper()
    if (~near['uf'].isin(UFS)).any():
        raise ValueError('SG_UF_PROVA inválida em POP_NEAR.')
    import numpy as np
    notas = near[list(NOTAS_COMP)].to_numpy(dtype='float64')
    flags = (notas < 200).astype('int8')
    diverge = ~np.isclose(notas.sum(axis=1), near['nota_total'].to_numpy(dtype='float64'),
                         atol=1e-6, rtol=0)
    if diverge.any():
        log(f'  Alerta de origem: {int(diverge.sum())} redações próximas com soma C1-C5 != nota total.')
    # Agrupa vetores de cinco eventos binários (máximo 32 combinações por UF).
    temporario = pd.DataFrame(flags, columns=list(COMPETENCIAS))
    temporario['uf'] = near['uf'].to_numpy()
    temporario['diverge'] = diverge.astype('int8')
    grouped = temporario.groupby(['uf',*COMPETENCIAS], observed=True, sort=False).agg(
        n=('uf','size'), divergentes=('diverge','sum'))
    for (uf,*bits), linha in grouped.iterrows():
        incrementar(contagem,str(uf),tuple(int(b) for b in bits),int(linha['n']),
                    int(linha['divergentes']))


def contar_anos_mesma_linha(arquivo: Path, tamanho: int) -> tuple[dict, int]:
    contagem = defaultdict(novo_contador)
    n_validas = 0
    cols = ['TP_STATUS_REDACAO','NU_NOTA_REDACAO','SG_UF_PROVA',*NOTAS_COMP]
    for bloco in ler_blocos(arquivo,cols,tamanho):
        near, n = preparar_lote(bloco)
        n_validas += n
        acumular_df(contagem,near)
    return dict(contagem), n_validas


def contar_2024(participantes: Path, competencias: Path, tamanho: int) -> tuple[dict, int,dict]:
    """Join 2024 apenas por NU_INSCRICAO; não usa posição ou NU_SEQUENCIAL."""
    contagem = defaultdict(novo_contador)
    with tempfile.TemporaryDirectory(prefix='enem_ind032_') as diretorio:
        con = sqlite3.connect(str(Path(diretorio)/'associacao.sqlite3'))
        try:
            con.execute('PRAGMA journal_mode=OFF')
            con.execute('PRAGMA synchronous=OFF')
            con.execute('CREATE TABLE participantes (id TEXT PRIMARY KEY, uf TEXT NOT NULL) WITHOUT ROWID')
            con.execute('CREATE TABLE near_vistos (id TEXT PRIMARY KEY) WITHOUT ROWID')
            con.execute('CREATE TEMP TABLE lote_near (id TEXT, c1 INT, c2 INT, c3 INT, c4 INT, c5 INT, diff INT)')
            n_participantes = 0
            for bloco in ler_blocos(participantes,['NU_INSCRICAO','SG_UF_PROVA'],tamanho):
                ids = bloco['NU_INSCRICAO'].astype('string').str.strip().tolist()
                ufs = bloco['SG_UF_PROVA'].astype('string').str.strip().str.upper().tolist()
                if any(not x for x in ids) or any(x not in UFS for x in ufs):
                    raise ValueError('PARTICIPANTES_2024: inscrição vazia ou UF inválida.')
                try:
                    con.executemany('INSERT INTO participantes VALUES (?,?)',zip(ids,ufs))
                except sqlite3.IntegrityError as e:
                    raise ValueError('PARTICIPANTES_2024: NU_INSCRICAO duplicada.') from e
                n_participantes += len(ids)
            con.commit()
            log(f'  2024: {n_participantes:,} participantes indexados por inscrição.')
            n_validas = 0
            n_near_vinculadas = 0
            n_somas_divergentes = 0
            cols = ['NU_INSCRICAO','TP_STATUS_REDACAO','NU_NOTA_REDACAO',*NOTAS_COMP]
            for bloco in ler_blocos(competencias,cols,tamanho):
                near,n = preparar_lote(bloco)
                n_validas += n
                if near.empty:
                    continue
                ids = near['NU_INSCRICAO'].astype('string').str.strip().tolist()
                if any(not x for x in ids):
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição vazia em POP_NEAR.')
                import numpy as np
                notas = near[list(NOTAS_COMP)].to_numpy(dtype='float64')
                flags = (notas<200).astype('int8')
                divergencias = ~np.isclose(notas.sum(axis=1),near['nota_total'].to_numpy(),
                                           atol=1e-6,rtol=0)
                n_somas_divergentes += int(divergencias.sum())
                try:
                    con.executemany('INSERT INTO near_vistos VALUES (?)',((v,) for v in ids))
                except sqlite3.IntegrityError as e:
                    raise ValueError('COMPETENCIAS_REDACAO_2024: inscrição duplicada em POP_NEAR.') from e
                con.execute('DELETE FROM lote_near')
                con.executemany('INSERT INTO lote_near VALUES (?,?,?,?,?,?,?)',
                                ((ids[i],*map(int,flags[i]),int(divergencias[i]))
                                 for i in range(len(ids))))
                total = int(con.execute('SELECT COUNT(*) FROM lote_near l JOIN participantes p ON p.id=l.id').fetchone()[0])
                if total != len(ids):
                    raise ValueError(f'2024: {len(ids)-total} redações POP_NEAR sem correspondente em PARTICIPANTES_2024.')
                for uf,c1,c2,c3,c4,c5,n_linhas,n_diff in con.execute('''
                   SELECT p.uf,l.c1,l.c2,l.c3,l.c4,l.c5,COUNT(*),SUM(l.diff)
                   FROM lote_near l JOIN participantes p ON p.id=l.id
                   GROUP BY p.uf,l.c1,l.c2,l.c3,l.c4,l.c5'''):
                    incrementar(contagem,uf,(c1,c2,c3,c4,c5),int(n_linhas),int(n_diff))
                n_near_vinculadas += len(ids)
                con.commit()
            return dict(contagem), n_validas, {
                'metodo':'join_NU_INSCRICAO','n_participantes':n_participantes,
                'n_pop_near_vinculadas':n_near_vinculadas,
                'n_somas_competencias_divergentes':(None if 0 < n_somas_divergentes < N_MINIMO
                                                    else n_somas_divergentes),
                'n_near_sem_correspondencia':0,
            }
        finally:
            con.close()


def grupos_suprimidos(contagem: dict[str,dict]) -> tuple[dict[tuple[str,int],str],dict]:
    """Protege N pequeno, evento e complemento; mais 1 UF se só 1 suprimida.

    Resultado público não contém totais secretos, nem em metadados.
    Nota: privacidade cruzada com outros indicadores requer revisão adicional.
    """
    mascaras: dict[tuple[str,int],str] = {}
    primarias = 0
    complementares = 0
    for uf in ('BR',*UFS):
        bruto = contagem.get(uf,novo_contador())
        n = bruto['n']
        for i in range(5):
            sim = bruto['sim'][i]
            nao = n-sim
            if (0<n<N_MINIMO) or (0<sim<N_MINIMO) or (0<nao<N_MINIMO):
                mascaras[(uf,i)] = 'primaria'
                primarias += 1
    for i in range(5):
        ocultas = [uf for uf in UFS if (uf,i) in mascaras]
        if len(ocultas)==1:
            candidatas = [uf for uf in UFS if (uf,i) not in mascaras and
                          contagem.get(uf,novo_contador())['n']>=N_MINIMO]
            if candidatas:
                escolhida = max(candidatas,key=lambda uf:contagem[uf]['n'])
                mascaras[(escolhida,i)] = 'complementar'
                complementares += 1
            else:
                # Sem complemento estadual disponível: ocultar o Brasil também.
                mascaras[('BR',i)] = 'complementar'
                complementares += 1
    # Não publicar BR se a contagem de uma competência for pequena, mesmo
    # quando as UFs individualmente não forem pequenas.
    return mascaras, {'supressoes_primarias':primarias,
                      'supressoes_complementares':complementares,
                      'celulas_suprimidas':len(mascaras),
                      'regra':'sem supressão automática por n<30; agregados são publicados'}


def construir_recortes(ano: int, contagem: dict, n_validas: int,
                        controlar_pop: bool = True) -> tuple[dict,dict]:
    for uf in ('BR',*UFS):
        contagem.setdefault(uf,novo_contador())
    n_near = contagem['BR']['n']
    ufs_sem_pop_publicavel = [uf for uf in UFS if 0 < contagem[uf]['n'] < N_MINIMO]
    if ufs_sem_pop_publicavel:
        raise ValueError(f'{ano}: recortes com N POP_NEAR menor que {N_MINIMO}: '
                         f'{ufs_sem_pop_publicavel}. Agregue o recorte antes de publicar.')
    if sum(contagem[uf]['n'] for uf in UFS) != n_near:
        raise ValueError(f'{ano}: total BR de POP_NEAR não fecha com 27 UFs.')
    for i in range(5):
        if sum(contagem[uf]['sim'][i] for uf in UFS) != contagem['BR']['sim'][i]:
            raise ValueError(f'{ano}: C{i+1} BR não fecha com UFs.')
    if controlar_pop and n_near != CONTROLE_POP_NEAR[ano]:
        raise ValueError(f'{ano}: POP_NEAR={n_near:,} difere da referência '
                         f'{CONTROLE_POP_NEAR[ano]:,} (IND-031).')
    if n_near>n_validas:
        raise ValueError(f'{ano}: POP_NEAR maior que POP_VALID.')
    mascaras,qa_privacidade=grupos_suprimidos(contagem)
    recortes = {}
    for uf in ('BR',*UFS):
        bruto = contagem[uf]
        n = bruto['n']
        itens = []
        for i,c in enumerate(COMPETENCIAS):
            motivo = mascaras.get((uf,i))
            ocultar = bool(motivo)
            sim = bruto['sim'][i]
            itens.append({
                'competencia':c,
                'n_redacoes':n,
                'n_com_desconto':None if ocultar else sim,
                'n_sem_desconto':None if ocultar else n-sim,
                'frequencia_desconto':None if ocultar or not n else round(sim/n,8),
                'percentual_desconto':None if ocultar or not n else round(100*sim/n,6),
                'suprimido':ocultar,
                'motivo_supressao':motivo,
            })
        recortes[uf] = {
            'uf':uf,'populacao':'POP_NEAR','intervalo_nota':[900,980],
            'n_validas':n_validas if uf=='BR' else None,
            'n_near':n,'status_publicacao':'revisao_privacidade_pendente',
            'resumo_competencias':itens,
            'n_somas_competencias_divergentes':(
                None if 0 < bruto['divergencia_soma'] < N_MINIMO else bruto['divergencia_soma']),
            'diagnostico_soma_suprimido':0 < bruto['divergencia_soma'] < N_MINIMO,
            'sem_dados_individuais':True,
        }
    return recortes,qa_privacidade


def comparar_ind031(raiz: Path, ano: int, recortes: dict) -> str:
    dash = raiz/'outputs'/'json'/f'dashboard_enem_{ano}.json'
    if not dash.is_file():
        return 'nao_verificado_dashboard_ausente'
    doc = json.loads(dash.read_text(encoding='utf-8-sig'))
    bloco = doc.get('pages',{}).get('high_performance',{}).get('loss_by_competency',{})
    if not isinstance(bloco,dict) or bloco.get('indicator_id')!='IND-031':
        return 'nao_verificado_ind031_ausente'
    if recortes['BR']['n_near'] != bloco['brasil']['n_near']:
        raise ValueError(f'{ano}: N POP_NEAR BR diverge de IND-031.')
    for item in bloco['by_uf']:
        uf = item['uf']
        if recortes[uf]['n_near'] != item['n_near']:
            raise ValueError(f'{ano}: POP_NEAR/{uf} diverge de IND-031.')
    return 'aprovado'


def salvar_json(caminho: Path, obj: Any) -> None:
    caminho.parent.mkdir(parents=True,exist_ok=True)
    nome = None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=caminho.parent,
                                         prefix=caminho.name+'.',suffix='.tmp',delete=False) as f:
            nome=Path(f.name)
            json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
        os.replace(nome,caminho)
    finally:
        if nome:
            nome.unlink(missing_ok=True)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True,exist_ok=True)
    campos=['ano','uf','competencia','n_redacoes','n_com_desconto','n_sem_desconto',
            'frequencia_desconto','percentual_desconto','suprimido','motivo_supressao']
    nome=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8-sig',newline='',dir=caminho.parent,
                                         prefix=caminho.name+'.',suffix='.tmp',delete=False) as f:
            nome=Path(f.name)
            writer=csv.DictWriter(f,delimiter=';',fieldnames=campos,extrasaction='ignore')
            writer.writeheader()
            writer.writerows(linhas)
        os.replace(nome,caminho)
    finally:
        if nome:
            nome.unlink(missing_ok=True)


def atualizar_dashboards(raiz: Path, anos_modificados: dict[str,dict]) -> None:
    destino = raiz/'outputs'/'json'
    for texto,ano_obj in sorted(anos_modificados.items()):
        if ano_obj.get('status')!='ok':
            continue
        ano = int(texto)
        arq = destino/f'dashboard_enem_{ano}.json'
        if not arq.exists():
            log(f'  Dashboard {ano} ausente; integração não realizada.')
            continue
        d = json.loads(arq.read_text(encoding='utf-8-sig'))
        hp = d.get('pages',{}).get('high_performance')
        if not isinstance(hp,dict):
            raise ValueError(f'{arq.name}: pages.high_performance não é objeto.')
        rec = ano_obj['recortes']
        hp['discount_frequency'] = {
            'indicator_id':'IND-032', 'population':'POP_NEAR',
            'method':'mean(NU_NOTA_COMPi < 200), 900 <= nota_total <= 980',
            'year':ano,'status':'draft',
            'brasil':rec['BR'],
            'by_uf':[rec[uf] for uf in UFS],
            'privacy_note':('Células pequenas e complementares são ocultadas. '
                            'Revisão acadêmica e privacidade cruzada pendentes.'),
        }
        hp['status']='partial'
        hp['reason']='IND-030, IND-031 e IND-032 disponíveis; demais indicadores de alto desempenho pendentes.'
        qa=d.setdefault('quality',{})
        qa['ind032_validation']={
            'status':'ok_agregados','population':'POP_NEAR',
            'n_near_brasil':rec['BR']['n_near'],
            'soma_27_ufs_igual_brasil':True,
            'ind031':ano_obj['controle_ind031'],
            **ano_obj['privacidade'],
            'revisao_academica_e_privacidade_cruzada_pendente':True,
        }
        meta=d.setdefault('meta',{})
        warns=meta.setdefault('warnings',[])
        aviso=('IND-032: frequências de desconto por competência sobre POP_NEAR; '
               'supressão primária e complementar aplicada; revisão cruzada pendente.')
        if aviso not in warns:
            warns.append(aviso)
        salvar_json(arq,d)
        log(f'  Dashboard {ano}: IND-032 integrado (sem gerar .bak).')


def executar(base: Path, saida: Path, anos: tuple[int,...], bloco: int,
             somente_modulo: bool, sobrescrever: bool, sem_controle: bool,
             pular_2025_ausente: bool = True,
             fontes_explicitas: dict[str, Path] | None = None) -> dict:
    base,saida=base.resolve(),saida.resolve()
    arq_json=saida/'outputs'/'json'/'IND_032_frequencia_desconto.json'
    arq_csv=saida/'outputs'/'indicadores'/'IND_032_frequencia_desconto.csv'
    if not sobrescrever and (arq_json.exists() or arq_csv.exists()):
        raise FileExistsError('Saída IND-032 já existe; use --sobrescrever.')
    faltas:set[str]=set()
    for ano in anos:
        if ano<=2023:
            faltas.add(f'MICRODADOS_ENEM_{ano}.CSV')
        elif ano==2024:
            faltas.update({'PARTICIPANTES_2024.CSV','COMPETENCIAS_REDACAO_2024.CSV'})
        else:
            faltas.add('RESULTADOS_2025.CSV')
    fontes=localizar_fontes(base,faltas,fontes_explicitas)
    missing=sorted((faltas - set(fontes)) - ({'RESULTADOS_2025.CSV'} if pular_2025_ausente else set()))
    if missing:
        raise FileNotFoundError(f'Fontes ausentes em {base}: {missing}. Use --base para apontar o local correto.')
    anteriores:dict[str,dict]={}
    if sobrescrever and arq_json.exists():
        anterior=json.loads(arq_json.read_text(encoding='utf-8-sig'))
        if anterior.get('indicator_id')!='IND-032':
            raise ValueError('JSON existente pertence a outro indicador.')
        anteriores=dict(anterior.get('years',{}))
    dados_anos=dict(anteriores)
    processados:dict[str,dict]={}
    for ano in anos:
        log(f'IND-032 | {ano}: calculando frequência de Ci < 200 em POP_NEAR...')
        if ano==2025 and 'RESULTADOS_2025.CSV' not in fontes:
            dados_anos[str(ano)]={'ano':ano,'status':'indisponivel',
              'reason':'RESULTADOS_2025.csv ausente; não é possível calcular frequência exata.',
              'recortes':{}}
            processados[str(ano)]=dados_anos[str(ano)]
            log('  2025 indisponível: fonte não localizada. Nenhum percentual foi estimado.')
            continue
        if ano==2024:
            cont,n_validas,diag=contar_2024(fontes['PARTICIPANTES_2024.CSV'],
                   fontes['COMPETENCIAS_REDACAO_2024.CSV'],bloco)
            fonte='PARTICIPANTES_2024.csv + COMPETENCIAS_REDACAO_2024.csv'
        else:
            nome=(f'MICRODADOS_ENEM_{ano}.CSV' if ano<=2023 else 'RESULTADOS_2025.CSV')
            cont,n_validas=contar_anos_mesma_linha(fontes[nome],bloco)
            fonte=nome.lower()
            diag={'metodo':'mesma_linha'}
        rec,qa_priv=construir_recortes(ano,cont,n_validas,not sem_controle)
        contr=comparar_ind031(saida,ano,rec)
        if diag.get('n_pop_near_vinculadas',rec['BR']['n_near'])!=rec['BR']['n_near']:
            raise ValueError(f'{ano}: n_pop_near_vinculadas diferente de n_near.')
        dado={
            'ano':ano,'status':'ok','fonte':fonte,'population':'POP_NEAR',
            'n_validas_brasil':n_validas,'n_near_brasil':rec['BR']['n_near'],
            'diagnostico_fonte':diag,'controle_ind031':contr,
            'privacidade':qa_priv,'recortes':rec,
        }
        dados_anos[str(ano)]=dado
        processados[str(ano)]=dado
        log(f'  {ano}: N_near={rec["BR"]["n_near"]:,}; privacidade={qa_priv["celulas_suprimidas"]} células ocultas; IND-031={contr}')
    linhas=[]
    for y,d in sorted(dados_anos.items(),key=lambda x:int(x[0])):
        if d.get('status')!='ok':
            continue
        for uf in ('BR',*UFS):
            for r in d['recortes'][uf]['resumo_competencias']:
                linhas.append({'ano':int(y),'uf':uf,**r})
    modulo={
        'indicator_id':'IND-032',
        'titulo':'Frequência de desconto por competência',
        'status':'draft','gerado_em_utc':datetime.now(timezone.utc).isoformat(),
        'anos_solicitados':list(anos),
        'anos_disponiveis':sorted(int(y) for y,v in dados_anos.items() if v.get('status')=='ok'),
        'population':'POP_NEAR','geography':'SG_UF_PROVA',
        'methodology':{
            'selection':'TP_STATUS_REDACAO=1 e nota final válida em [900,980], inclusivo',
            'rule':'Frequencia_Ci = count(NU_NOTA_COMPi < 200) / n_POP_NEAR',
            'variables':list(NOTAS_COMP),'denominator':'N de redações em POP_NEAR para ano e UF',
            'scope':'Brasil e 27 UFs da prova; por ano (sem estimar 2025 quando falta fonte)',
            'interpretation':'C1..C5 não são categorias mutuamente exclusivas; percentuais não somam 100%',
            'privacy':('Suprimir se N do recorte, n_com_desconto ou n_sem_desconto está em 1..29; '
                       'aplicar pelo menos uma supressão complementar por competência e ano quando necessário.'),
            'no_backup':True,
            'limitations':[
                'POP_NEAR coincide com IND-031: inclui nota 980, exclui 1000.',
                'Dados agregados não permitem reconstituir esta frequência sem microdados.',
                'Ano 2025 exige RESULTADOS_2025.csv com UF, nota total, status e C1..C5.',
                'Os resultados históricos acumulados não são exportados automaticamente, por cautela contra reconstrução de células suprimidas.',
                'Resultados draft; revisão acadêmica e avaliação de privacidade cruzada necessárias.',
            ],
        },
        'years':dados_anos,
    }
    salvar_json(arq_json,modulo)
    salvar_csv(arq_csv,linhas)
    log(f'IND-032 | JSON: {arq_json}')
    log(f'IND-032 | CSV: {arq_csv}')
    if not somente_modulo:
        atualizar_dashboards(saida,processados)
    log('IND-032 | Concluído.')
    return modulo


def main() -> None:
    p=argparse.ArgumentParser(description='IND-032 | Frequência de desconto, 900–980')
    p.add_argument('--base',type=Path,default=raiz_projeto(),help='Raiz de busca das fontes CSV')
    p.add_argument('--saida',type=Path,default=None,help='Raiz de saída, por padrão raiz do repositório')
    p.add_argument('--anos',type=int,nargs='+',default=list(ANOS))
    p.add_argument('--bloco',type=int,default=100_000)
    p.add_argument('--sobrescrever',action='store_true')
    p.add_argument('--somente-modulo',action='store_true',help='Não modifica dashboards existentes')
    p.add_argument('--sem-controle-populacao',action='store_true',help='Apenas testes com bases sintéticas')
    p.add_argument('--exigir-2025',action='store_true',help='Falha se RESULTADOS_2025.csv estiver ausente')
    p.add_argument('--competencias-2024',type=Path,default=None,
                   help='Escolhe explicitamente o CSV de competências de 2024 (se houver duplicatas).')
    p.add_argument('--participantes-2024',type=Path,default=None,
                   help='Escolhe explicitamente o CSV de participantes de 2024 (se houver duplicatas).')
    args=p.parse_args()
    anos=tuple(sorted(set(args.anos)))
    if not anos or not set(anos)<=set(ANOS):
        p.error('Informe anos de 2019 a 2025.')
    if args.bloco<=0:
        p.error('--bloco deve ser positivo.')
    escolhas = {}
    if args.competencias_2024 is not None:
        escolhas['COMPETENCIAS_REDACAO_2024.CSV'] = args.competencias_2024
    if args.participantes_2024 is not None:
        escolhas['PARTICIPANTES_2024.CSV'] = args.participantes_2024
    try:
        executar(args.base,args.saida or raiz_projeto(),anos,args.bloco,
                 args.somente_modulo,args.sobrescrever,args.sem_controle_populacao,
                 not args.exigir_2025, escolhas)
    except (OSError,ValueError,sqlite3.DatabaseError,json.JSONDecodeError) as e:
        print(f'ERRO IND-032: {e}',file=sys.stderr)
        sys.exit(1)


if __name__=='__main__':
    main()
