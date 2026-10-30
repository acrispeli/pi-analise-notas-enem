#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-052 — UF da prova × desempenho na redação | PI IV — UNIVESP.

Catálogo 2019–2025 v2, pages.socioeconomic.uf_performance.
Dados: SG_UF_PROVA, TP_STATUS_REDACAO, NU_NOTA_REDACAO e NU_NOTA_COMP1..5.
2019–2023: MICRODADOS_ENEM_<ano>.csv; 2024–2025: RESULTADOS_<ano>.csv.
Todas as variáveis estão NA MESMA LINHA da fonte anual: nenhum join socioeconômico.

População operacional: TP_STATUS_REDACAO=1, nota total em [0,1000] e
competências C1..C5 em [0,200], todas numéricas e finitas. Corresponde à
seleção POP_SOCIO_VALID usada nos módulos IND-045–051 para 2019–2024;
em 2025, é a população de redações válidas diretamente em RESULTADOS_2025.
A referência independente IND-002 confere N e média por UF/BR de 2019–2025.

Saídas: outputs/json/IND_052_uf_prova_desempenho.json,
        outputs/indicadores/IND_052_uf_prova_desempenho.csv,
        pages.socioeconomic.uf_performance nos dashboards já existentes.
Status 'draft' até processar microdados reais e concluir revisão acadêmica.

Exemplos na raiz do projeto:
  python src/indicadores/IND_052_uf_prova_desempenho.py --autoteste
  python src/indicadores/IND_052_uf_prova_desempenho.py --anos 2025 --sobrescrever
  python src/indicadores/IND_052_uf_prova_desempenho.py --sobrescrever
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd

try:
    import IND_045_tipo_escola_nota as ind45
except ImportError as e:
    raise SystemExit('IND-052 requer IND_045_tipo_escola_nota.py na mesma pasta src/indicadores.') from e

ANOS = tuple(range(2019, 2026))
UFS = ind45.UFS
COMPETENCIAS = ind45.NOTAS_COMP
CAMPOS = ('NU_NOTA_REDACAO', *COMPETENCIAS)
ROTULOS = dict(zip(CAMPOS, ('TOTAL', 'C1', 'C2', 'C3', 'C4', 'C5')))
LIMIAR = ind45.LIMIAR
CAMPOS_CSV = (
    'ano', 'uf', 'abrangencia', 'arquivo_fonte', 'populacao', 'competencia',
    'n_redacoes', 'percentual_nacional', 'media', 'mediana', 'q1', 'q3', 'iqr',
    'desvio_padrao', 'suprimido', 'motivo_supressao',
)
ESTATS = ('media', 'mediana', 'q1', 'q3', 'iqr', 'desvio_padrao')


def log(msg: str) -> None:
    print(msg, flush=True)


def nome_fonte(ano: int) -> str:
    if ano not in ANOS:
        raise ValueError(f'Ano não suportado: {ano}')
    return f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023 else f'RESULTADOS_{ano}.CSV'


class Grupo:
    """Histogramas exatos por UF, total e competências; não armazena identificadores."""
    def __init__(self) -> None:
        self.n = 0
        self.hist = {col: Counter() for col in CAMPOS}
        self.n_soma_divergente = 0

    def adicionar(self, valores: np.ndarray) -> None:
        if valores.ndim != 2 or valores.shape[1] != len(CAMPOS):
            raise ValueError('Esperados seis vetores: nota total e C1..C5.')
        if not np.isfinite(valores).all():
            raise ValueError('Nota não finita na população selecionada.')
        self.n += len(valores)
        for k, col in enumerate(CAMPOS):
            pontos, frequencias = np.unique(valores[:, k], return_counts=True)
            self.hist[col].update({float(x): int(n) for x, n in zip(pontos, frequencias)})
        self.n_soma_divergente += int(np.count_nonzero(~np.isclose(
            valores[:, 1:].sum(axis=1), valores[:, 0], atol=1e-6, rtol=0)))

    def juntar(self, outro: 'Grupo') -> None:
        self.n += outro.n
        for col in CAMPOS:
            self.hist[col].update(outro.hist[col])
        self.n_soma_divergente += outro.n_soma_divergente

    def conferir(self) -> None:
        for col in CAMPOS:
            if sum(self.hist[col].values()) != self.n:
                raise ValueError(f'Histograma {col} não fecha N={self.n}.')


def ler_ano(arquivo: Path, ano: int, bloco: int) -> tuple[dict[str, Grupo], dict]:
    """Lê apenas colunas necessárias, sem junção e em blocos de memória."""
    if bloco <= 0:
        raise ValueError('O tamanho de bloco deve ser positivo.')
    grupos: dict[str, Grupo] = defaultdict(Grupo)
    totais = {'linhas_lidas': 0, 'status_valido': 0, 'linhas_rejeitadas_status': 0,
              'n_soma_competencias_divergente': 0, 'metodo': 'mesma_linha_sem_join',
              'ano': ano, 'arquivo_fonte': arquivo.name}
    cols = ['SG_UF_PROVA', 'TP_STATUS_REDACAO', *CAMPOS]
    for parte in ind45.ler_blocos(arquivo, cols, bloco):
        totais['linhas_lidas'] += len(parte)
        validas = ind45.selecionar_validas(parte)
        totais['status_valido'] += len(validas)
        totais['linhas_rejeitadas_status'] += len(parte) - len(validas)
        if validas.empty:
            continue
        ufs = validas['SG_UF_PROVA'].astype('string').str.strip().str.upper()
        if (~ufs.isin(UFS)).any():
            amostras = sorted(set(ufs.loc[~ufs.isin(UFS)].astype(str).tolist()))[:3]
            raise ValueError(f'{ano}: SG_UF_PROVA não reconhecida em redação válida: {amostras}')
        arr = validas[['__nota_total', *COMPETENCIAS]].to_numpy(dtype='float64')
        # Agrupar por UF, sem replicar cada linha para o Brasil neste estágio.
        indices = pd.Series(np.arange(len(validas))).groupby(ufs.reset_index(drop=True)).indices
        for uf, pos in indices.items():
            grupos[str(uf)].adicionar(arr[pos])
    brasil = Grupo()
    for uf in UFS:
        brasil.juntar(grupos[uf])
    grupos['BR'] = brasil
    for grupo in grupos.values():
        grupo.conferir()
    if brasil.n != totais['status_valido']:
        raise ValueError(f'{ano}: soma de UFs não fecha a população válida.')
    totais['n_validas'] = brasil.n
    totais['n_soma_competencias_divergente'] = brasil.n_soma_divergente
    return dict(grupos), totais


def ler_ind002(base: Path, caminho: Path | None = None) -> dict[int, dict]:
    p = caminho or base / 'outputs' / 'json' / 'IND_002_nota_media.json'
    if not p.is_absolute():
        p = base / p
    if not p.is_file():
        raise FileNotFoundError('IND-002 necessário para conciliar N/média: ' + str(p))
    doc = json.loads(p.read_text(encoding='utf-8-sig'))
    if doc.get('meta', {}).get('indicator_id') != 'IND-002' or not isinstance(doc.get('years'), list):
        raise ValueError('Referência não corresponde ao JSON do IND-002.')
    return {int(obj['ano']): obj for obj in doc['years']}


def ler_ind045_opcional(base: Path, caminho: Path | None = None) -> dict | None:
    p = caminho or base / 'outputs' / 'json' / 'IND_045_tipo_escola_nota.json'
    if not p.is_absolute():
        p = base / p
    if not p.is_file():
        if caminho is not None:
            raise FileNotFoundError('IND-045 explicitamente indicado não encontrado: ' + str(p))
        return None
    doc = json.loads(p.read_text(encoding='utf-8-sig'))
    if doc.get('indicator_id') != 'IND-045' or doc.get('population') != 'POP_SOCIO_VALID':
        raise ValueError('Referência opcional deve ser IND-045/POP_SOCIO_VALID.')
    return doc


def verificar_referencias(ano: int, grupos: dict[str, Grupo],
                         ind002: dict[int, dict], ind045: dict | None) -> dict:
    if ano not in ind002:
        raise ValueError(f'IND-002 não contém {ano}.')
    ref = ind002[ano]
    ufs_ref = {obj['uf']: obj for obj in ref.get('ufs', [])}
    if set(ufs_ref) != set(UFS):
        raise ValueError(f'{ano}: IND-002 não contém as 27 UFs da prova.')
    if sum(grupos[uf].n for uf in UFS) != grupos['BR'].n:
        raise ValueError(f'{ano}: N Brasil difere da soma das UFs.')
    n_ref_brasil = ref['brasil']['n_validas']
    if n_ref_brasil != grupos['BR'].n:
        raise ValueError(f'{ano}: N Brasil IND-052={grupos["BR"].n}, IND-002={n_ref_brasil}.')
    for uf in ('BR', *UFS):
        g = grupos[uf]
        esperado = ref['brasil'] if uf == 'BR' else ufs_ref[uf]
        if esperado['n_validas'] != g.n:
            raise ValueError(f'{ano}/{uf}: N difere do IND-002.')
        media = ind45.estatisticas(g.hist['NU_NOTA_REDACAO'], g.n)['media']
        media_ref = esperado['media']
        if (media is None) != (media_ref is None):
            raise ValueError(f'{ano}/{uf}: tratamento de ausência difere do IND-002.')
        if media is not None and not math.isclose(media, float(media_ref), abs_tol=.00011, rel_tol=0):
            raise ValueError(f'{ano}/{uf}: média difere do IND-002: {media} != {media_ref}.')
    checado045 = False
    if ind045 is not None and ano <= 2024:
        entrada = ind045.get('years', {}).get(str(ano), {})
        if entrada.get('status') != 'ok':
            raise ValueError(f'{ano}: referência IND-045 não disponível.')
        for uf in ('BR', *UFS):
            ref_uf = entrada['recortes'][uf]['n_pop_socio_valid']
            if ref_uf != grupos[uf].n:
                raise ValueError(f'{ano}/{uf}: N diverge de IND-045: {grupos[uf].n} vs {ref_uf}.')
        qa_ref = entrada.get('validacao', {}).get('n_soma_competencias_divergente')
        if qa_ref is not None and qa_ref != grupos['BR'].n_soma_divergente:
            raise ValueError(f'{ano}: diagnóstico soma C1–C5 difere IND-045.')
        checado045 = True
    return {
        'n_conferido_ind002_por_uf_brasil': True,
        'media_total_conferida_ind002_por_uf_brasil': True,
        'populacao_conferida_ind045': checado045,
        'n_brasil': grupos['BR'].n,
        'n_soma_competencias_divergente': grupos['BR'].n_soma_divergente,
        'soma_ufs_confere': True,
        'revisao_privacidade_cruzada_pendente': True,
    }


def montar_recortes(grupos: dict[str, Grupo]) -> tuple[dict, dict]:
    """Política conservadora: se uma UF tiver N=1..29, ocultar TODAS as UFs.

    Dessa forma, o total BR público não permite recuperar uma UF pequena por
    subtração de 26 estados visíveis. A revisão cruzada continua obrigatória.
    """
    pequenos = [uf for uf in UFS if 0 < grupos[uf].n < LIMIAR]
    br_pequeno = 0 < grupos['BR'].n < LIMIAR
    recortes = {}
    for uf in ('BR', *UFS):
        grupo = grupos[uf]
        ocultar = br_pequeno or (uf != 'BR' and bool(pequenos))
        motivo = ('total_brasil_abaixo_limiar' if br_pequeno else
                  'supressao_global_ufs_por_celula_pequena' if ocultar else None)
        metricas = {}
        for col in CAMPOS:
            stats = (ind45.estatisticas(grupo.hist[col], grupo.n) if not ocultar
                     else {s: None for s in ESTATS})
            metricas[ROTULOS[col]] = {
                'competencia': ROTULOS[col],
                'n_redacoes': None if ocultar else grupo.n,
                **stats,
                'suprimido': ocultar,
                'motivo_supressao': motivo,
            }
        n_br = grupos['BR'].n
        recortes[uf] = {
            'uf': uf, 'abrangencia': 'Brasil' if uf == 'BR' else 'UF da prova',
            'n_redacoes': None if ocultar else grupo.n,
            'percentual_nacional': None if ocultar or not n_br else round(100*grupo.n/n_br, 6),
            'metricas': metricas, 'suprimido': ocultar,
            'motivo_supressao': motivo,
        }
    qa = {'n_ufs_com_celulas_pequenas': len(pequenos),
          'ufs_suprimidas_globalmente': bool(pequenos or br_pequeno),
          'n_ufs_visiveis': sum(not recortes[uf]['suprimido'] for uf in UFS),
          'politica': ('Se existe UF com N=1..29, todas as UFs são ocultadas; '
                      'BR visível apenas se N>=30; revisão cruzada pendente.')}
    return recortes, qa


def linhas_csv(anos: dict[str, dict]) -> list[dict]:
    linhas = []
    for ano, obj in sorted(anos.items(), key=lambda x: int(x[0])):
        if obj.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = obj['recortes'][uf]
            for metrica in rec['metricas'].values():
                linhas.append({
                    'ano': int(ano), 'uf': uf, 'abrangencia': rec['abrangencia'],
                    'arquivo_fonte': obj['arquivo_fonte'], 'populacao': obj['population'],
                    'competencia': metrica['competencia'],
                    'n_redacoes': metrica['n_redacoes'],
                    'percentual_nacional': rec['percentual_nacional'],
                    **{campo: metrica[campo] for campo in ESTATS},
                    'suprimido': rec['suprimido'],
                    'motivo_supressao': rec['motivo_supressao'],
                })
    return linhas


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8-sig', newline='',
                                         dir=caminho.parent, prefix=caminho.name+'.',
                                         suffix='.tmp', delete=False) as f:
            tmp = Path(f.name)
            w = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=';', extrasaction='raise')
            w.writeheader()
            w.writerows(linhas)
        tmp.replace(caminho)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def preparar_dashboards(saida: Path, novos: dict[str, dict]) -> list[tuple[Path, dict]]:
    preparados = []
    for ano_str, obj in sorted(novos.items(), key=lambda x: int(x[0])):
        if obj['status'] != 'ok':
            continue
        ano = int(ano_str)
        caminho = saida / 'outputs' / 'json' / f'dashboard_enem_{ano}.json'
        if not caminho.is_file():
            log(f'  Dashboard {ano} ausente; módulo independente será mantido.')
            continue
        doc = json.loads(caminho.read_text(encoding='utf-8-sig'))
        socio = doc.get('pages', {}).get('socioeconomic')
        if not isinstance(socio, dict):
            raise ValueError(f'{caminho.name}: pages.socioeconomic não existe.')
        rec = obj['recortes']
        socio['uf_performance'] = {
            'indicator_id': 'IND-052', 'status': 'draft', 'year': ano,
            'population': obj['population'],
            'geography': 'SG_UF_PROVA', 'source_file': obj['arquivo_fonte'],
            'national': rec['BR'], 'states': {uf: rec[uf] for uf in UFS},
            'metrics': ['TOTAL', 'C1', 'C2', 'C3', 'C4', 'C5'],
            'interpretation': 'Descritivo: UF de aplicação, não residência; sem ranking causal.',
            'privacy_note': 'Supressão conservadora de UFs pequenas; revisão cruzada pendente.',
        }
        doc.setdefault('quality', {})['ind052_validation'] = {
            'status': 'ok_agregados', **obj['validacao'],
            'revisao_academica_pendente': True,
        }
        aviso = ('IND-052: UF da prova não implica UF de residência. '
                 'Desempenho é descritivo; avaliar N e dispersão, sem ranking causal.')
        warnings = doc.setdefault('meta', {}).setdefault('warnings', [])
        if aviso not in warnings:
            warnings.append(aviso)
        preparados.append((caminho, doc))
    return preparados


def executar(base: Path, saida: Path, anos: tuple[int, ...], bloco: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_ind002: Path | None = None,
             referencia_ind045: Path | None = None,
             escolhas: dict[str, Path] | None = None) -> dict:
    base, saida = base.resolve(), saida.resolve()
    destino_json = saida / 'outputs' / 'json' / 'IND_052_uf_prova_desempenho.json'
    destino_csv = saida / 'outputs' / 'indicadores' / 'IND_052_uf_prova_desempenho.csv'
    if not sobrescrever and (destino_json.exists() or destino_csv.exists()):
        raise FileExistsError('IND-052 já existe; utilize --sobrescrever para atualizar.')
    if bloco <= 0 or any(ano not in ANOS for ano in anos):
        raise ValueError('Parâmetros de edição/bloco inválidos.')
    ind002 = ler_ind002(base, referencia_ind002)
    ind045 = ler_ind045_opcional(base, referencia_ind045)
    nomes = {nome_fonte(ano) for ano in anos}
    fontes = ind45.localizar_fontes(base, nomes, escolhas)
    faltantes = sorted(nomes - set(fontes))
    if faltantes:
        raise FileNotFoundError('Arquivos de entrada não localizados: '+', '.join(faltantes))
    anteriores = {}
    if destino_json.is_file() and sobrescrever:
        prev = json.loads(destino_json.read_text(encoding='utf-8-sig'))
        if prev.get('indicator_id') != 'IND-052':
            raise ValueError('O JSON existente não pertence ao IND-052.')
        anteriores = prev.get('years', {})
    todos, novos = dict(anteriores), {}
    for ano in anos:
        fonte = fontes[nome_fonte(ano)]
        log(f'IND-052 | {ano} | {fonte.name} | sem junção socioeconômica...')
        grupos, diag = ler_ano(fonte, ano, bloco)
        if 0 < grupos['BR'].n < LIMIAR:
            raise ValueError(f'{ano}: N nacional inferior a {LIMIAR}; publicação do ano bloqueada.')
        validacao = verificar_referencias(ano, grupos, ind002, ind045)
        recortes, privacidade = montar_recortes(grupos)
        validacao['privacidade'] = privacidade
        obj = {
            'ano': ano, 'status': 'ok', 'population': 'POP_SOCIO_VALID',
            'population_definition': 'status redação=1; nota 0..1000; C1..C5 0..200, na mesma base',
            'arquivo_fonte': fonte.name, 'n_brasil': grupos['BR'].n,
            'diagnostico_fonte': diag, 'validacao': validacao, 'recortes': recortes,
        }
        todos[str(ano)] = novos[str(ano)] = obj
        log(f'  N Brasil={grupos["BR"].n:,}; 27 UFs verificadas; '
            f'IND-002 OK; IND-045={validacao["populacao_conferida_ind045"]}.')
    modulo = {
        'indicator_id': 'IND-052', 'titulo': 'UF da prova × desempenho',
        'status': 'draft', 'population': 'POP_SOCIO_VALID',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(k) for k, v in todos.items() if v.get('status') == 'ok'),
        'geography': 'SG_UF_PROVA', 'json_path': 'pages.socioeconomic.uf_performance',
        'methodology': {
            'sources_2019_2023': 'MICRODADOS_ENEM_<ano>.csv',
            'sources_2024_2025': 'RESULTADOS_<ano>.csv',
            'join': 'nenhum; UF e notas na mesma linha, inclusive 2025',
            'population': 'TP_STATUS_REDACAO=1; NU_NOTA_REDACAO em 0..1000; C1–C5 em 0..200',
            'population_note': ('POP_SOCIO_VALID é o rótulo de contrato do catálogo; '
                                'este indicador não usa questionário nem vínculo socioeconômico.'),
            'statistics': 'N, % do Brasil, média, mediana, Q1, Q3, IQR e desvio-padrão populacional',
            'metrics': ['TOTAL', 'C1', 'C2', 'C3', 'C4', 'C5'],
            'quantiles': 'Hyndman–Fan tipo 7 (histogramas exatos)',
            'reference': 'IND-002: N e média total BR/27 UFs, 2019–2025; IND-045: N opcional 2019–2024',
            'privacy': 'N=1..29 por UF implica ocultar todas as UFs no ano; status draft',
            'interpretation': [
                'UF da prova não equivale à UF de residência nem identifica causalidade.',
                'Desempenho por UF requer contexto demográfico e socioeconômico e exposição de N e IQR.',
                'Não montar rankings simplistas a partir das médias.',
                'Cada ano representa participações, não pessoas únicas.',
                'Diferença entre competência final e soma pode ocorrer; reportar diagnóstico.',
                'Referência IND-002 tem notas arredondadas a quatro casas.',
                'Revisar privacidade cruzada com outros indicadores antes da publicação.',
            ],
        },
        'years': todos,
    }
    dashboards = [] if somente_modulo else preparar_dashboards(saida, novos)
    ind45.salvar_json(destino_json, modulo)
    salvar_csv(destino_csv, linhas_csv(todos))
    for caminho, doc in dashboards:
        ind45.salvar_json(caminho, doc)
        log(f'  Dashboard {caminho.name}: uf_performance integrado.')
    log(f'IND-052 concluído em draft: {destino_json} | {destino_csv}')
    return modulo


def autoteste() -> None:
    """Valida cálculos com NumPy independente, anos e origens distintas, QA e privacidade."""
    from contextlib import redirect_stdout
    import io

    rng = np.random.default_rng(5206)
    with tempfile.TemporaryDirectory(prefix='enem_ind052_teste_') as pasta:
        base = Path(pasta)
        (base/'outputs'/'json').mkdir(parents=True)
        (base/'outputs'/'indicadores').mkdir(parents=True)
        refs = []
        amostras = {}
        for ano in (2019, 2024, 2025):
            nome = nome_fonte(ano).replace('.CSV', '.csv')
            arquivo = base / nome
            dados = []
            for idx, uf in enumerate(UFS):
                for j in range(60):
                    # Dispersão não simétrica: útil para detectar erro de mediana e Q1/Q3.
                    notas_c = [int(rng.integers(0, 11))*20 for _ in range(5)]
                    score = sum(notas_c)
                    dados.append({'SG_UF_PROVA': uf.lower() if j % 2 else uf,
                                  'TP_STATUS_REDACAO': '1',
                                  'NU_NOTA_REDACAO': str(score),
                                  **{c: str(x) for c,x in zip(COMPETENCIAS, notas_c)}})
                # Participante com status diferente: deve ser excluído.
                dados.append({'SG_UF_PROVA': uf, 'TP_STATUS_REDACAO': '2',
                              'NU_NOTA_REDACAO': '',
                              **{c:'' for c in COMPETENCIAS}})
            rng.shuffle(dados)
            with arquivo.open('w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, delimiter=';', fieldnames=[
                    'SG_UF_PROVA', 'TP_STATUS_REDACAO', *CAMPOS])
                w.writeheader();w.writerows(dados)
            validas = [r for r in dados if r['TP_STATUS_REDACAO'] == '1']
            amostras[ano] = validas
            def referência(lista: list[dict]) -> dict:
                xs = [float(r['NU_NOTA_REDACAO']) for r in lista]
                return {'n_validas': len(xs), 'media': round(float(np.mean(xs)),4) if xs else None}
            refs.append({'ano':ano, 'brasil': referência(validas),
                         'ufs':[{'uf':uf, **referência([r for r in validas
                                         if r['SG_UF_PROVA'].upper() == uf])} for uf in UFS]})
            dash = {'meta':{'warnings':[]},'quality':{},
                    'pages':{'socioeconomic':{'ind050_dummy':{'keep':True}}}}
            ind45.salvar_json(base/'outputs'/'json'/f'dashboard_enem_{ano}.json', dash)
        ind45.salvar_json(base/'outputs'/'json'/'IND_002_nota_media.json',
                         {'meta':{'indicator_id':'IND-002'},'years':refs})
        with redirect_stdout(io.StringIO()):
            doc = executar(base, base, (2019,2024,2025), 31, False, False)
        assert doc['anos_disponiveis'] == [2019, 2024, 2025]
        for ano in (2019,2024,2025):
            obj = doc['years'][str(ano)]
            assert obj['n_brasil'] == 1620
            assert obj['diagnostico_fonte']['linhas_lidas'] == 1647
            assert obj['diagnostico_fonte']['n_soma_competencias_divergente'] == 0
            assert len(obj['recortes']) == 28
            assert obj['validacao']['n_conferido_ind002_por_uf_brasil']
            br = obj['recortes']['BR']['metricas']['TOTAL']
            notas = np.array([float(r['NU_NOTA_REDACAO']) for r in amostras[ano]])
            assert br['n_redacoes'] == len(notas)
            assert math.isclose(br['media'],np.mean(notas),abs_tol=.000051)
            assert math.isclose(br['mediana'],np.median(notas),abs_tol=.000051)
            assert math.isclose(br['q1'],np.quantile(notas,.25),abs_tol=.000051)
            assert math.isclose(br['q3'],np.quantile(notas,.75),abs_tol=.000051)
            assert math.isclose(br['desvio_padrao'],np.std(notas,ddof=0),abs_tol=.000051)
            uf = UFS[0]
            dados_uf = [r for r in amostras[ano] if r['SG_UF_PROVA'].upper() == uf]
            comp1 = np.array([float(r[COMPETENCIAS[0]]) for r in dados_uf])
            obj_c1 = obj['recortes'][uf]['metricas']['C1']
            assert obj_c1['n_redacoes'] == 60
            assert math.isclose(obj_c1['media'],float(np.mean(comp1)),abs_tol=.000051)
            assert math.isclose(obj_c1['mediana'],float(np.median(comp1)),abs_tol=.000051)
            assert not obj['recortes'][uf]['suprimido']
            assert math.isclose(obj['recortes'][uf]['percentual_nacional'],100*60/1620,abs_tol=1e-6)
            arq = base/'outputs'/'json'/f'dashboard_enem_{ano}.json'
            atual = json.loads(arq.read_text(encoding='utf-8'))
            assert atual['pages']['socioeconomic']['ind050_dummy']['keep'] is True
            assert atual['pages']['socioeconomic']['uf_performance']['indicator_id']=='IND-052'
        with (base/'outputs'/'indicadores'/'IND_052_uf_prova_desempenho.csv').open(
                encoding='utf-8-sig', newline='') as f:
            linhas = list(csv.DictReader(f, delimiter=';'))
        assert len(linhas) == 3*28*6
        assert all(not r['uf'].startswith('NU_') for r in linhas)
        assert not any('NU_INSCRICAO' in str(x) for x in (doc, linhas))
        # Processamento incremental preserva anos anteriores e não modifica dashboards.
        anterior=json.loads((base/'outputs'/'json'/'dashboard_enem_2019.json').read_text())
        with redirect_stdout(io.StringIO()):
            doc2=executar(base,base,(2025,),17,True,True)
        assert doc2['anos_disponiveis'] == [2019,2024,2025]
        assert json.loads((base/'outputs'/'json'/'dashboard_enem_2019.json').read_text())==anterior
        # Referência adulterada => falha explícita (não escreve resultado).
        errado=json.loads((base/'outputs'/'json'/'IND_002_nota_media.json').read_text())
        errado['years'][-1]['ufs'][0]['n_validas'] += 1
        arq_erro=base/'ref_errada.json'
        ind45.salvar_json(arq_erro,errado)
        try:
            with redirect_stdout(io.StringIO()):
                executar(base,base,(2025,),100,True,True,referencia_ind002=arq_erro)
        except ValueError as e:
            assert 'IND-002' in str(e)
        else:
            raise AssertionError('Não rejeitou divergência na referência.')
        # Política conservadora contra recuperação por diferença dos totais.
        grupos={uf:Grupo() for uf in ('BR',*UFS)}
        pequenos=np.array([[200.,40.,40.,40.,40.,40.]])
        grupos[UFS[0]].adicionar(pequenos)
        grupos[UFS[1]].adicionar(np.tile(pequenos,(40,1)))
        grupos['BR'].juntar(grupos[UFS[0]]);grupos['BR'].juntar(grupos[UFS[1]])
        rec,qa=montar_recortes(grupos)
        assert qa['ufs_suprimidas_globalmente']
        assert all(rec[uf]['n_redacoes'] is None for uf in UFS)
        assert rec['BR']['n_redacoes'] == 41
        assert all(rec[uf]['metricas']['TOTAL']['media'] is None for uf in UFS)
        # Células Brasil N<30 também são ocultadas.
        rec2,_=montar_recortes({uf:(grupos[UFS[0]] if uf in ('BR',UFS[0])
                                  else Grupo()) for uf in ('BR',*UFS)})
        assert rec2['BR']['n_redacoes'] is None
        # Verificação de notas inválidas e UF inválida.
        bad = base/'MICRODADOS_ENEM_2020.csv'
        with bad.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['SG_UF_PROVA','TP_STATUS_REDACAO',*CAMPOS],delimiter=';')
            writer.writeheader();writer.writerow({'SG_UF_PROVA':'SP','TP_STATUS_REDACAO':'1',
                         'NU_NOTA_REDACAO':'1001',**{c:'100' for c in COMPETENCIAS}})
        try:
            ler_ano(bad,2020,40)
        except ValueError as e:
            assert 'NU_NOTA_REDACAO' in str(e)
        else:
            raise AssertionError('Não rejeitou nota >1000.')
        bad2=base/'MICRODADOS_ENEM_2021.csv'
        with bad2.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['SG_UF_PROVA','TP_STATUS_REDACAO',*CAMPOS],delimiter=';')
            writer.writeheader();writer.writerow({'SG_UF_PROVA':'ZZ','TP_STATUS_REDACAO':'1',
                         'NU_NOTA_REDACAO':'500',**{c:'100' for c in COMPETENCIAS}})
        try:
            ler_ano(bad2,2021,40)
        except ValueError as e:
            assert 'SG_UF_PROVA' in str(e)
        else:
            raise AssertionError('Não rejeitou UF desconhecida.')
    log('AUTOTESTE IND-052 APROVADO | 2019, 2024, 2025 | 4.860 redações sintéticas válidas')


def main() -> None:
    parser=argparse.ArgumentParser(description='IND-052 — UF da prova × desempenho')
    parser.add_argument('--autoteste',action='store_true',help='Executa testes sintéticos sem microdados reais')
    parser.add_argument('--base',type=Path,default=ind45.raiz_projeto(),help='Raiz do repositório, onde estão as fontes')
    parser.add_argument('--saida',type=Path,default=None,help='Raiz para outputs e dashboards; padrão: --base')
    parser.add_argument('--anos',type=int,nargs='+',choices=ANOS,default=list(ANOS))
    parser.add_argument('--bloco',type=int,default=100000,help='Registros lidos por lote')
    parser.add_argument('--sobrescrever',action='store_true')
    parser.add_argument('--somente-modulo',action='store_true',help='Não modifica dashboards existentes')
    parser.add_argument('--referencia-ind002',type=Path,default=None)
    parser.add_argument('--referencia-ind045',type=Path,default=None)
    parser.add_argument('--resultados-2024',type=Path,default=None)
    parser.add_argument('--resultados-2025',type=Path,default=None)
    args=parser.parse_args()
    if args.autoteste:
        autoteste()
        return
    escolhas={}
    if args.resultados_2024 is not None:
        escolhas['RESULTADOS_2024.CSV']=args.resultados_2024
    if args.resultados_2025 is not None:
        escolhas['RESULTADOS_2025.CSV']=args.resultados_2025
    executar(args.base, args.saida or args.base, tuple(sorted(set(args.anos))), args.bloco,
             args.sobrescrever, args.somente_modulo,
             args.referencia_ind002,args.referencia_ind045,escolhas)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        log(f'ERRO IND-052: {type(exc).__name__}: {exc}')
        sys.exit(1)
