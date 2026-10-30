#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-054 — Clusters socioeconômicos (MCA → K-Means), PI IV UNIVESP.

Catálogo ENEM 2019–2025 v2: AMOSTRA_SOCIO_ML, pages.ml.socio_clusters.
Modelos anuais independentes + núcleo harmonizado 14 conceitos (somente com
2019–2023 e 2024–2025 presentes no mesmo processamento).
Não utiliza notas, NU_INSCRICAO ou junções; não exporta rótulos individuais.

DEPENDÊNCIAS: numpy, pandas, scipy, scikit-learn e scripts IND-053 CORRIGIDO
(e IND-045, exigido pelo IND-053) na mesma pasta src/indicadores.

Exemplos no terminal na raiz do projeto:
  python src/indicadores/IND_054_clusters_socioeconomicos.py --autoteste
  python src/indicadores/IND_054_clusters_socioeconomicos.py --sobrescrever
  python src/indicadores/IND_054_clusters_socioeconomicos.py --anos 2024 2025 --somente-modulo --sobrescrever

Este script recalcula a MCA na mesma amostra reprodutível do IND-053,
porque o IND-053 não exporta escores de indivíduos. Confronta metadados
quando houver IND-053 e N de fonte contra IND-040; nenhum dado identificável
é escrito. A saída é DRAFT até auditoria/homologação.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score,
                             davies_bouldin_score, silhouette_score)

try:
    import IND_053_dimensoes_socioeconomicas as ind53
except ImportError as exc:
    raise SystemExit('Coloque o IND-053 corrigido em src/indicadores, junto ao IND-054.') from exc

ANOS = ind53.ANOS
NOME = 'IND_054_clusters_socioeconomicos'
LIMIAR = 30
CAMPOS_CSV = ('modelo', 'ano', 'tipo_linha', 'cluster', 'n_amostra',
              'n_cluster', 'percentual_cluster', 'k_selecionado', 'k_avaliado',
              'silhouette', 'davies_bouldin', 'calinski_harabasz',
              'ari_estabilidade', 'eixo', 'centroide', 'variavel', 'categoria',
              'prevalencia_grupo_faixa_pct', 'prevalencia_amostra_faixa_pct',
              'diferenca_aproximada_pp', 'observacao')


def log(msg: str) -> None:
    print(msg, flush=True)


def projetar_escores_mca(dados: pd.DataFrame, n_eixos: int) -> tuple[np.ndarray, dict, pd.DataFrame]:
    """Projeta indivíduos no espaço MCA do IND-053 sem exportar coordenadas.

    F_ie = sum_{j ativos do individuo} G_je / (q * sqrt(lambda_e)),
    com G = coordenadas principais das categorias do IND-053.
    A mesma consolidação de categorias raras do IND-053 é repetida.
    """
    if n_eixos < 1 or n_eixos > 6:
        raise ValueError('Quantidade de eixos deve estar entre 1 e 6.')
    agrupado, _ = ind53._unificar_raros(dados, LIMIAR)
    try:
        modelo = ind53.ajustar_mca(agrupado, n_eixos, LIMIAR)
    except OverflowError as exc:
        raise RuntimeError('IND-053 desatualizado: utilize a versão corrigida do overflow int8.') from exc
    dimensoes = modelo['dimensoes']
    if len(dimensoes) < 2:
        raise ValueError('MCA produziu menos de duas dimensões não nulas; impossível agrupar.')
    q = modelo['n_variaveis_ativas']
    x = np.empty((len(agrupado), len(dimensoes)), dtype='float64')
    for e, d in enumerate(dimensoes):
        lam = float(d['autovalor'])
        if not lam > 0:
            raise ValueError('Autovalor MCA não positivo.')
        mapas: dict[str, dict[str, float]] = {}
        for item in d['categorias']:
            mapas.setdefault(item['variavel'], {})[item['categoria']] = float(item['coordenada'])
        projecao = np.zeros(len(agrupado), dtype='float64')
        for coluna, categorias in mapas.items():
            values = agrupado[coluna].map(categorias)
            if values.isna().any():
                raise AssertionError(f'Modalidade de {coluna} sem coordenada MCA.')
            projecao += values.to_numpy(dtype='float64')
        projecao /= q * math.sqrt(lam)
        # Confere fórmula de projeção com a própria inércia MCA.
        if not np.isclose(np.var(projecao, ddof=0), lam, atol=5e-5, rtol=3e-4):
            raise AssertionError(f'Inércia não reconciliada no eixo MCA-{e+1}.')
        if abs(float(projecao.mean())) > 5e-4:
            raise AssertionError('Escores MCA não centralizados.')
        x[:, e] = projecao
    if not np.isfinite(x).all():
        raise AssertionError('Escores de MCA não finitos.')
    return x, modelo, agrupado


def _ordenar_rotulos(rotulos: np.ndarray, centroides: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """IDs do cluster por tamanho decrescente; não alinham anos distintos."""
    contagens = np.bincount(rotulos, minlength=len(centroides))
    ordem = sorted(range(len(centroides)),
                   key=lambda i: (-int(contagens[i]), tuple(np.round(centroides[i], 10))))
    renomear = np.empty(len(ordem), dtype='int32')
    for novo, antigo in enumerate(ordem):
        renomear[antigo] = novo
    return renomear[rotulos], centroides[ordem], [int(contagens[i]) for i in ordem]


def selecionar_k(x: np.ndarray, seed: int, max_k: int = 6,
                 teste_n: int = 1000) -> tuple[np.ndarray, dict]:
    """Seleciona K por silhouette amostrada, respeitando n>=30 por cluster.

    Davies-Bouldin (menor), Calinski-Harabasz (maior) e ARI para diagnóstico;
    nenhum é uma medida causal, nem rótulo de classe verdadeira.
    """
    if not np.isfinite(x).all() or x.ndim != 2 or x.shape[1] < 2:
        raise ValueError('Matriz de entrada ao K-Means inválida.')
    n = len(x)
    if n < 100:
        raise ValueError('Amostra insuficiente para validação de clusters (mínimo 100).')
    if max_k < 2 or teste_n < 100:
        raise ValueError('Parâmetros K ou tamanho do teste inválidos.')
    # Mesmos indivíduos no cálculo de silhouette de todos os K.
    rng = np.random.default_rng(seed + 300)
    idx = (rng.choice(n, size=min(teste_n, n), replace=False)
           if teste_n < n else np.arange(n))
    candidatas = []
    melhor = None
    for k in range(2, min(max_k, n // LIMIAR) + 1):
        km = KMeans(n_clusters=k, random_state=seed + 17,
                    n_init=20, max_iter=300, algorithm='lloyd')
        labels = km.fit_predict(x)
        tamanhos = np.bincount(labels, minlength=k)
        if int(tamanhos.min()) < LIMIAR:
            candidatas.append({'k': k, 'status': 'rejeitado_privacidade',
                               'motivo': 'cluster com menos de 30 participantes; N não exportado'})
            continue
        y_teste = labels[idx]
        if len(np.unique(y_teste)) < 2 or len(np.unique(y_teste)) == len(y_teste):
            candidatas.append({'k': k, 'status': 'rejeitado_amostra_metrica'})
            continue
        sil = float(silhouette_score(x[idx], y_teste, metric='euclidean'))
        db = float(davies_bouldin_score(x, labels))
        ch = float(calinski_harabasz_score(x, labels))
        km2 = KMeans(n_clusters=k, random_state=seed + 1017,
                     n_init=10, max_iter=300, algorithm='lloyd')
        labels2 = km2.fit_predict(x)
        ari = float(adjusted_rand_score(labels, labels2))
        linha = {'k': k, 'status': 'avaliado', 'silhouette': round(sil, 6),
                 'davies_bouldin': round(db, 6), 'calinski_harabasz': round(ch, 4),
                 'ari_estabilidade': round(ari, 6)}
        candidatas.append(linha)
        # Desempate intencional em favor do menor K.
        if melhor is None or sil > melhor[0] + 1e-7 or (abs(sil - melhor[0]) <= 1e-7 and k < melhor[1]):
            melhor = (sil, k, km, labels, linha)
    if melhor is None:
        raise ValueError('Nenhum K de 2 a max_k respeita o mínimo de 30 e a métrica de validação.')
    _, k, km, labels, metricas = melhor
    labels, centroides, tamanhos = _ordenar_rotulos(labels, km.cluster_centers_)
    assert len(labels) == n and sum(tamanhos) == n and min(tamanhos) >= LIMIAR
    resultado = {
        'k_selecionado': k, 'criterio': 'max_silhouette_amostrada_desempate_menor_k',
        'diagnosticos_k': candidatas, 'metricas_k_escolhido': metricas,
        'centroides': [[round(float(v), 6) for v in c] for c in centroides],
        'tamanhos': tamanhos, 'avaliacao_silhouette_n': int(len(idx)),
        'score_space': 'escores_principais_MCA_Euclidiano_sem_escalonamento_extra',
    }
    return labels, resultado


def perfis_publicaveis(dados: pd.DataFrame, labels: np.ndarray,
                       k: int, max_achados: int = 5) -> list[dict]:
    """Perfil agregado com percentuais aproximados, apenas margens divulgáveis.

    Não revela contagens pequenas; publica categoria quando há pelo menos
    30 no grupo, 30 no complemento e 30 fora do grupo, para bloquear
    reconstruções triviais de margens. Revisão cruzada ainda pendente.
    """
    n = len(dados)
    resultado = []
    for grupo in range(k):
        em = labels == grupo
        n_grupo = int(em.sum())
        achados = []
        for coluna in dados:
            f_global = dados[coluna].value_counts()
            f_grupo = dados.loc[em, coluna].value_counts()
            for categoria, numero in f_grupo.items():
                a = int(numero)
                tot = int(f_global[categoria])
                fora = tot - a
                if min(a, n_grupo - a, fora, n - n_grupo - fora) < LIMIAR:
                    continue
                p = a / n_grupo
                p_total = tot / n
                diferenca = 100 * (p - p_total)
                if diferenca < 5:
                    continue
                achados.append((diferenca, str(coluna), str(categoria), p, p_total))
        achados.sort(key=lambda t: (-t[0], t[1], t[2]))
        perfis = []
        for dif, variavel, categoria, p, pb in achados[:max_achados]:
            # Percentuais arredondados a 5 p.p. e SEM contagens por modalidade.
            p5 = int(round(20*p)*5)
            pb5 = int(round(20*pb)*5)
            perfis.append({'variavel': variavel, 'categoria': categoria,
                           'prevalencia_grupo_aprox_pct': p5,
                           'prevalencia_amostra_aprox_pct': pb5,
                           'diferenca_aprox_pp': p5 - pb5})
        resultado.append({'cluster': f'C{grupo+1}', 'caracteristicas': perfis})
    return resultado


def modelar(dados: pd.DataFrame, seed: int, eixos: int,
            max_k: int, teste_n: int) -> dict:
    x, mca, seguros = projetar_escores_mca(dados, eixos)
    rotulos, fit = selecionar_k(x, seed, max_k, teste_n)
    perfis = perfis_publicaveis(seguros, rotulos, fit['k_selecionado'])
    clusters = []
    for i, (tam, centro, perfil) in enumerate(zip(fit['tamanhos'], fit['centroides'], perfis)):
        clusters.append({'cluster': f'C{i+1}', 'n_amostra': tam,
                         'participacao_aprox_pct': int(round(20*tam/len(x))*5),
                         'centroide_mca': centro, 'perfil_exploratorio': perfil['caracteristicas']})
    return {
        'n_amostra': len(x), 'n_eixos': x.shape[1],
        'inercia_pct_eixos': [d['inercia_pct'] for d in mca['dimensoes']],
        'autovalores_mca': [d['autovalor'] for d in mca['dimensoes']],
        'n_variaveis_ativas': mca['n_variaveis_ativas'],
        'n_categorias_ativas': mca['n_categorias_ativas'],
        'k_selecionado': fit['k_selecionado'], 'criterio_k': fit['criterio'],
        'metricas_k_escolhido': fit['metricas_k_escolhido'],
        'diagnosticos_k': fit['diagnosticos_k'],
        'silhouette_sample_size': fit['avaliacao_silhouette_n'],
        'clusters': clusters,
        'method': 'MCA_escores_principais_KMeans',
        'cluster_ids_are_local_to_model': True,
        'no_individual_data_exported': True,
        'qualitative_profile_note': 'Categorias sobre-representadas; percentuais aproximados a 5 p.p.; sem nomes definitivos.',
    }


def validar_ind053(caminho: Path, anos: dict[int, dict], seed: int, limite: int,
                    eixos: int) -> dict:
    if not caminho.exists():
        return {'status': 'pendente', 'motivo': 'IND-053 não processado/encontrado.'}
    doc = json.loads(caminho.read_text(encoding='utf-8-sig'))
    if doc.get('indicator_id') != 'IND-053':
        raise ValueError('Referência apontada não é IND-053.')
    if doc.get('seed') != seed or doc.get('tamanho_maximo_amostra_por_ano') != limite:
        return {'status': 'parametros_diferentes',
                'motivo': 'Seed e/ou tamanho da amostra diferem; não é válido reconciliar os eixos.'}
    conf = []
    anos_ref = doc.get('years', {})
    for ano, info in anos.items():
        ref = anos_ref.get(str(ano))
        if ref is None:
            return {'status': 'pendente', 'motivo': f'IND-053 sem edição {ano}.'}
        if info['n_fonte'] != int(ref['n_fonte']) or info['n_amostra'] != int(ref['n_amostra']):
            raise ValueError(f'IND-054 {ano}: N diverge do IND-053.')
        a = [float(x['autovalor']) for x in ref['mca']['dimensoes'][:eixos]]
        b = info['modelo']['autovalores_mca']
        if len(a) < len(b) or not np.allclose(a[:len(b)], b, rtol=1e-6, atol=1e-7):
            raise ValueError(f'IND-054 {ano}: autovalores MCA divergem do IND-053; confira o bloco e a amostra.')
        conf.append(ano)
    return {'status': 'ok', 'anos_conferidos': conf}


def montar_documento(registros: dict[int, dict], combinado: dict | None,
                      qa: dict, qa_ref: dict, qa_053: dict,
                      seed: int, limite: int, eixos: int, max_k: int) -> dict:
    return {
        'indicator_id': 'IND-054', 'slug': NOME,
        'title': 'Clusters socioeconômicos — MCA + K-Means',
        'module_schema_version': 'ind054-module-1.0.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_status': 'draft', 'population': 'AMOSTRA_SOCIO_ML',
        'population_source': 'POP_SOCIO', 'model_method': 'MCA_mais_KMeans',
        'seed': seed, 'sample_limit_per_year': limite,
        'mca_dimensions': eixos, 'k_range': [2, max_k],
        'years': {str(a): item for a, item in sorted(registros.items())},
        'pooled_core_clusters': combinado,
        'harmonization': {
            'version': 'nucleo_14_conceitos_v1_reutilizado_IND053',
            'mapping': {c: {'2019_2023': a, '2024_2025': b, 'regra': regra}
                        for c, (a, b, regra) in ind53.NUCLEO.items()},
            'annual_models': '23 perguntas nativas; eixos e clusters não alinhados entre edições',
            'pooled_model': '14 conceitos recodificados; somente se ambas versões do questionário presentes',
        },
        'quality': {
            'annual_source': {str(a): r for a, r in sorted(qa.items())},
            'ind040_reconciliation': qa_ref,
            'ind053_reconciliation': qa_053,
            'privacy': {'minimum_cluster_size': LIMIAR,
                        'category_modalities_collapsed_below_n': LIMIAR,
                        'profile_percentages_rounded_to_5pp': True,
                        'cross_indicator_disclosure_review': 'pendente'},
            'no_personal_identifiers_scores_or_individual_assignments_exported': True,
            'join_diagnostics': {'status': 'nao_aplicavel', 'reason': 'questionário sem notas ou identificadores'},
            'caveats': [
                'Clusters são exploratórios, não classes socioeconômicas oficiais; nomes somente após inspeção.',
                'IDs C1, C2 etc. reordenados por tamanho e NÃO equivalentes entre anos e modelos.',
                'K selecionado pelo maior silhouette numa subamostra fixa por modelo, sujeito a K permitido e limiar de privacidade.',
                'ARI verifica estabilidade entre inicializações, não entre outras amostras ou diferentes edições.',
                'Silhouette, Davies-Bouldin e Calinski-Harabasz são métricas internas, não de validade causal.',
                'Eixos MCA são categóricos; percentuais de inércia não equivalem a variância PCA.',
                'Amostras equilibradas por edição no conjunto não representam pesos populacionais.',
                'Modelo conjunto usa conceitos harmonizados; domínios Qxxx diferem entre 2019–23 e 2024–25.',
                'Para projetar outros participantes, é preciso replicar a codificação, a MCA e os centroides; este módulo não expõe IDs.',
                'Sem relação com notas de redação inclusive em 2025.',
            ],
        },
    }


def gerar_csv(doc: dict) -> list[dict]:
    out = []
    modelos = [(f'anual_{ano}', str(ano), ano_item['modelo'])
               for ano, ano_item in doc['years'].items()]
    if doc['pooled_core_clusters'] is not None:
        modelos.append(('nucleo_harmonizado_conjunto', '2019_2025', doc['pooled_core_clusters']))
    for nome, ano, mod in modelos:
        for x in mod['diagnosticos_k']:
            if x['status'] == 'avaliado':
                out.append({'modelo': nome, 'ano': ano, 'tipo_linha': 'selecao_k',
                            'n_amostra': mod['n_amostra'], 'k_selecionado': mod['k_selecionado'], 'k_avaliado': x['k'],
                            'silhouette': x['silhouette'],
                            'davies_bouldin': x['davies_bouldin'],
                            'calinski_harabasz': x['calinski_harabasz'],
                            'ari_estabilidade': x['ari_estabilidade'],
                            'observacao': 'K avaliado; K final no JSON'})
        for c in mod['clusters']:
            comum = {'modelo': nome, 'ano': ano, 'cluster': c['cluster'],
                     'n_amostra': mod['n_amostra'], 'n_cluster': c['n_amostra'],
                     'percentual_cluster': c['participacao_aprox_pct'],
                     'k_selecionado': mod['k_selecionado']}
            for eixo, v in enumerate(c['centroide_mca'], 1):
                out.append({**comum, 'tipo_linha': 'centroide', 'eixo': eixo, 'centroide': v})
            for p in c['perfil_exploratorio']:
                out.append({**comum, 'tipo_linha': 'perfil',
                            'variavel': p['variavel'], 'categoria': p['categoria'],
                            'prevalencia_grupo_faixa_pct': p['prevalencia_grupo_aprox_pct'],
                            'prevalencia_amostra_faixa_pct': p['prevalencia_amostra_aprox_pct'],
                            'diferenca_aproximada_pp': p['diferenca_aprox_pp']})
    return out


def salvar_csv(caminho: Path, registros: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + '.tmp')
    with tmp.open('w', newline='', encoding='utf-8-sig') as fp:
        w = csv.DictWriter(fp, fieldnames=CAMPOS_CSV, delimiter=';', extrasaction='raise')
        w.writeheader()
        w.writerows(registros)
    tmp.replace(caminho)


def atualizar_dashboard(arquivo: Path, ano_item: dict,
                        combinado: dict | None) -> bool:
    if not arquivo.exists():
        return False
    doc = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if not isinstance(doc.get('pages'), dict):
        raise ValueError('Dashboard sem pages: ' + str(arquivo))
    doc['pages'].setdefault('ml', {})['socio_clusters'] = {
        'indicator_id': 'IND-054', 'data_status': 'draft',
        'ano': ano_item['ano'], 'modelo_ano': ano_item['modelo'],
        'modelo_nucleo_conjunto': combinado,
        'nota': 'C1…Ck são rótulos locais por modelo; não há alinhamento temporal automático.'}
    doc.setdefault('quality', {})['ind054_validation'] = {
        'status': 'draft', 'n_fonte': ano_item['n_fonte'],
        'n_amostra': ano_item['n_amostra'],
        'sem_join': True, 'min_n_cluster': LIMIAR,
    }
    ind53.salvar_json(arquivo, doc)
    return True


def executar(base: Path, saida: Path, anos: tuple[int, ...], limite: int,
             bloco: int, seed: int, eixos: int, max_k: int, teste_n: int,
             sobrescrever: bool, somente_modulo: bool,
             referencia_040: Path | None = None,
             referencia_053: Path | None = None) -> dict:
    if not anos or any(ano not in ANOS for ano in anos):
        raise ValueError('Seleção de anos inválida.')
    if limite < 100 or bloco < 1 or eixos not in range(2, 7) or max_k not in range(2, 11):
        raise ValueError('Parâmetros de amostra/bloco/eixos/K inválidos.')
    caminho_json = saida/'outputs'/'json'/f'{NOME}.json'
    caminho_csv = saida/'outputs'/'indicadores'/f'{NOME}.csv'
    if not sobrescrever and (caminho_json.exists() or caminho_csv.exists()):
        raise FileExistsError('Saída já existente. Para substituir use --sobrescrever.')
    nomes = {ind53.fonte_ano(ano) for ano in anos}
    fontes = ind53.ind45.localizar_fontes(base, nomes)
    faltantes = sorted(nomes - set(fontes))
    if faltantes:
        raise FileNotFoundError('Fontes ausentes: ' + ', '.join(faltantes))
    registros: dict[int, dict] = {}
    controles: dict[int, dict] = {}
    nucleos = []
    for ano in anos:
        fonte = fontes[ind53.fonte_ano(ano)]
        log(f'IND-054 | {ano}: amostrando {fonte.name}...')
        amostra, qa = ind53.amostrar_ano(fonte, ano, limite, bloco, seed)
        modelo = modelar(amostra, seed + ano, eixos, max_k, teste_n)
        registros[ano] = {'ano': ano, 'status': 'draft',
                          'n_fonte': qa['n_fonte'], 'n_amostra': qa['n_amostra'],
                          'versao_questionario': '2019-2023' if ano <= 2023 else '2024-2025',
                          'modelo': modelo}
        controles[ano] = qa
        nucleos.append(ind53.preparar_nucleo(amostra, ano))
        log(f'  N fonte={qa["n_fonte"]:,}; amostra={qa["n_amostra"]:,}; '
            f'K={modelo["k_selecionado"]}; '
            f'silhouette={modelo["metricas_k_escolhido"]["silhouette"]:.3f}')
    ref40 = referencia_040 or (base/'outputs'/'json'/'IND_040_perfil_socioeconomico.json')
    if not ref40.is_absolute():
        ref40 = base/ref40
    qa_040 = ind53.conferir_ind040(ref40, controles)
    if qa_040['status'] != 'ok':
        log('  ATENÇÃO: IND-040 não localizado; conciliação N pendente.')
    ref53 = referencia_053 or (base/'outputs'/'json'/'IND_053_dimensoes_socioeconomicas.json')
    if not ref53.is_absolute():
        ref53 = base/ref53
    qa_053 = validar_ind053(ref53, registros, seed, limite, eixos)
    if qa_053['status'] != 'ok':
        log(f'  ATENÇÃO: verificação IND-053 = {qa_053["status"]}.')
    juntar = any(a <= 2023 for a in anos) and any(a >= 2024 for a in anos)
    combinado = None
    if juntar:
        log('IND-054: ajustando núcleo harmonizado de 14 conceitos (MCA + K-Means)...')
        combinado = modelar(pd.concat(nucleos, ignore_index=True), seed + 54,
                            eixos, max_k, teste_n)
        combinado['years_in_training'] = list(anos)
        combinado['sampling_note'] = 'Até n por ano; mesmo peso amostral por edição.'
        log(f'  N conjunto={combinado["n_amostra"]:,}; '
            f'K={combinado["k_selecionado"]}')
    else:
        log('  Sem modelo conjunto: é necessário incluir ambos os questionários (<=2023 e >=2024).')
    doc = montar_documento(registros, combinado, controles, qa_040, qa_053,
                           seed, limite, eixos, max_k)
    linhas = gerar_csv(doc)
    ind53.salvar_json(caminho_json, doc)
    salvar_csv(caminho_csv, linhas)
    n_dash = 0
    if not somente_modulo:
        for ano, item in registros.items():
            arquivo = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
            if atualizar_dashboard(arquivo, item, combinado):
                n_dash += 1
    log(f'IND-054 concluído em DRAFT | JSON={caminho_json} | CSV={caminho_csv} '
        f'({len(linhas):,} linhas) | dashboards={n_dash}')
    return doc


def autoteste() -> None:
    rng = np.random.default_rng(548)
    with tempfile.TemporaryDirectory(prefix='ind054_teste_') as temp:
        base = Path(temp)
        pasta = base/'raw'
        pasta.mkdir()
        anos = (2019, 2024, 2025)
        n = 480
        for ano in anos:
            latente = np.repeat(np.arange(3), n//3)
            rng.shuffle(latente)
            tabela = {}
            for q in ind53.QUESTOES:
                if q == 'Q005':
                    tabela[q] = np.where(latente == 0, '2', np.where(latente == 1, '4', '8'))
                else:
                    dominio = ind53.DOMINIOS_HIST if ano <= 2023 else ind53.DOMINIOS_REC
                    opcoes = list(dominio[q])
                    # Três perfis parcialmente sobrepostos, sem força de separação artificial absoluta.
                    arr = np.array([opcoes[min(int(z), len(opcoes)-1)] for z in latente], dtype=object)
                    mudar = rng.random(n) < 0.16
                    arr[mudar] = rng.choice(opcoes[:min(4, len(opcoes))], size=mudar.sum())
                    tabela[q] = arr
            pd.DataFrame(tabela).to_csv(pasta/ind53.fonte_ano(ano), sep=';', index=False)
        ref40 = {'meta': {'indicator_id': 'IND-040'},
                 'years': [{'ano': a, 'brasil': {'n_participacoes': n}} for a in anos]}
        arq40 = base/'outputs'/'json'/'IND_040_perfil_socioeconomico.json'
        ind53.salvar_json(arq40, ref40)
        # Simula referência IND-053 com mesma amostra e parâmetros.
        ref_anos = {}
        for ano in anos:
            am, qa = ind53.amostrar_ano(pasta/ind53.fonte_ano(ano), ano, 370, 103, 2026)
            x, mc, _ = projetar_escores_mca(am, 3)
            assert len(x) == 370 and x.shape[1] == 3
            ref_anos[str(ano)] = {'n_fonte': qa['n_fonte'], 'n_amostra': qa['n_amostra'], 'mca': mc}
        arquivo53 = base/'outputs'/'json'/'IND_053_dimensoes_socioeconomicas.json'
        ind53.salvar_json(arquivo53, {
            'indicator_id': 'IND-053', 'seed': 2026,
            'tamanho_maximo_amostra_por_ano': 370, 'years': ref_anos})
        destino = base/'saida'
        for ano in anos:
            ind53.salvar_json(destino/'outputs'/'json'/f'dashboard_enem_{ano}.json',
                             {'pages': {'overview': {'preservado': 1},
                                        'ml': {'pca': {'preservado': 2},
                                               'socio_mca': {'preservado': 3}}},
                              'quality': {'preexistente': True}})
        doc = executar(base, destino, anos, 370, 103, 2026, 3, 5, 250, False, False,
                       referencia_040=arq40, referencia_053=arquivo53)
        assert doc['quality']['ind040_reconciliation']['status'] == 'ok'
        assert doc['quality']['ind053_reconciliation']['status'] == 'ok'
        assert doc['pooled_core_clusters']['n_amostra'] == 1110
        assert doc['pooled_core_clusters']['n_variaveis_ativas'] == len(ind53.NUCLEO)
        for mod in [r['modelo'] for r in doc['years'].values()] + [doc['pooled_core_clusters']]:
            assert 2 <= mod['k_selecionado'] <= 5
            assert sum(c['n_amostra'] for c in mod['clusters']) == mod['n_amostra']
            assert min(c['n_amostra'] for c in mod['clusters']) >= LIMIAR
            assert all(len(c['centroide_mca']) == 3 for c in mod['clusters'])
            for cl in mod['clusters']:
                assert all(p['prevalencia_grupo_aprox_pct'] in range(0, 101, 5)
                           for p in cl['perfil_exploratorio'])
        for ano in anos:
            dash = json.loads((destino/'outputs'/'json'/f'dashboard_enem_{ano}.json').read_text('utf-8'))
            assert dash['pages']['overview']['preservado'] == 1
            assert dash['pages']['ml']['pca']['preservado'] == 2
            assert dash['pages']['ml']['socio_mca']['preservado'] == 3
            assert dash['pages']['ml']['socio_clusters']['ano'] == ano
            assert dash['quality']['preexistente'] is True
        with (destino/'outputs'/'indicadores'/f'{NOME}.csv').open(encoding='utf-8-sig') as fp:
            assert len(list(csv.DictReader(fp, delimiter=';'))) > 20
        try:
            executar(base, destino, anos, 370, 103, 2026, 3, 5, 250, False, False)
        except FileExistsError:
            pass
        else:
            raise AssertionError('Sobrescrita sem consentimento não bloqueada.')
        antes = (destino/'outputs'/'json'/'dashboard_enem_2025.json').read_bytes()
        teste_parcial = executar(base, destino, (2025,), 180, 103, 2026, 3, 4, 150,
                                True, True, referencia_040=arq40, referencia_053=arquivo53)
        assert teste_parcial['pooled_core_clusters'] is None
        assert antes == (destino/'outputs'/'json'/'dashboard_enem_2025.json').read_bytes()
        # Reproduz o overflow com >128 modalidades após agrupamento seguro.
        # Duas categorias de ausência/erro presentes com n>=30 em cada campo.
        teste = {}
        n_grande = 2400
        for q in ind53.QUESTOES:
            if q == 'Q005':
                opcoes = ['1', '2', '3', '4', '5_6', '7_9', '10_20',
                          ind53.AUSENTE, ind53.INVALIDO]
            else:
                opcoes = list(ind53.DOMINIOS_HIST[q]) + [ind53.AUSENTE, ind53.INVALIDO]
            teste[q] = rng.choice(opcoes, size=n_grande)
        dados = pd.DataFrame(teste)
        try:
            x, m, _ = projetar_escores_mca(dados, 3)
            assert x.shape == (n_grande, 3), x.shape
            assert m['n_categorias_ativas'] > 128, m['n_categorias_ativas']
        except OverflowError as exc:
            raise AssertionError('IND-053 contém overflow int8; instale versão corrigida.') from exc
    log('AUTOTESTE IND-054 APROVADO | 2019, 2024, 2025 | '
        '1.440 participantes fictícios | MCA + K-Means | núcleo harmonizado | QA')


def main() -> None:
    ap = argparse.ArgumentParser(description='IND-054 — Clusters socioeconômicos (MCA + K-Means)')
    ap.add_argument('--autoteste', action='store_true')
    ap.add_argument('--base', type=Path, default=ind53.ind45.raiz_projeto())
    ap.add_argument('--saida', type=Path, default=None)
    ap.add_argument('--anos', type=int, nargs='+', choices=ANOS, default=list(ANOS))
    ap.add_argument('--amostra', type=int, default=15_000)
    ap.add_argument('--bloco', type=int, default=100_000)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--eixos', type=int, default=3, choices=range(2, 7))
    ap.add_argument('--max-k', type=int, default=6, choices=range(2, 11))
    ap.add_argument('--silhouette-amostra', type=int, default=1000)
    ap.add_argument('--sobrescrever', action='store_true')
    ap.add_argument('--somente-modulo', action='store_true')
    ap.add_argument('--referencia-ind040', type=Path, default=None)
    ap.add_argument('--referencia-ind053', type=Path, default=None)
    args = ap.parse_args()
    if args.autoteste:
        autoteste()
    else:
        executar(args.base.resolve(), (args.saida or args.base).resolve(),
                 tuple(sorted(set(args.anos))), args.amostra, args.bloco,
                 args.seed, args.eixos, args.max_k, args.silhouette_amostra,
                 args.sobrescrever, args.somente_modulo,
                 args.referencia_ind040, args.referencia_ind053)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        log(f'ERRO IND-054: {type(exc).__name__}: {exc}')
        sys.exit(1)
