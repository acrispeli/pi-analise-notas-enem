#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-040 — Perfil socioeconômico descritivo do ENEM (2019–2025).

Frequências e proporções por Q001..Q023, em POP_SOCIO (TODOS os registros
presentes no arquivo do questionário; respostas em branco são uma categoria).
UF = UF de aplicação da prova; BR = Brasil. Processamento em blocos, sem junções
individuais nem exportação de registros individuais.

ATENÇÃO: 2019–2023 e 2024–2025 utilizam questionários de versões diferentes.
Q007, por exemplo, era trabalho doméstico em 2019 e é RENDA em 2024.
NÃO agrega distribuições Q001..Q023 no histórico sem harmonização validada.

Fontes: 2019–2023 MICRODADOS_ENEM_YYYY.csv;
        2024–2025 PARTICIPANTES_YYYY.csv (NÃO RESULTADOS_YYYY).

Uso (na raiz do projeto):
  python src/indicadores/IND_040_perfil_socioeconomico.py
  python src/indicadores/IND_040_perfil_socioeconomico.py --anos 2024
  python src/indicadores/IND_040_perfil_socioeconomico.py --somente-modulo
  python src/indicadores/IND_040_perfil_socioeconomico.py --sobrescrever

Requer pandas; jsonschema é opcional. Os JSONs permanecem DRAFT.
Não execute ao mesmo tempo que outro indicador atualizando dashboards.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import pandas as pd

ANOS = tuple(range(2019, 2026))
UFS = tuple('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split())
GEOS = ('BR', *UFS)
QUESTOES = tuple(f'Q{i:03d}' for i in range(1, 24))
INDICADOR = 'IND-040'
ARQUIVO = 'IND_040_perfil_socioeconomico'
MIN_N = 1
SEM_RESPOSTA = '__SEM_RESPOSTA_FISICA__'
AGREGADAS = '__CATEGORIAS_AGREGADAS__'
METODO = 'frequencias_pop_socio_br_uf_por_questao_agregacao_complementar_por_ano'

# Descrições curtas dos respectivos dicionários. NÃO representam equivalência
# temporal: no histórico, códigos iguais não são somados sem harmonização.
ROTULOS_ANTIGOS = (
    'Escolaridade do pai/responsável', 'Escolaridade da mãe/responsável',
    'Ocupação do pai/responsável', 'Ocupação da mãe/responsável',
    'Moradores do domicílio', 'Renda mensal familiar',
    'Empregado(a) doméstico(a)', 'Banheiros', 'Quartos', 'Carros',
    'Motocicletas', 'Geladeiras', 'Freezer', 'Máquina de lavar roupa',
    'Secadora de roupa', 'Micro-ondas', 'Lava-louças', 'Aspirador de pó',
    'Televisão em cores', 'DVD', 'TV por assinatura', 'Celular', 'Telefone fixo',
)
ROTULOS_ATUAIS = (
    'Escolaridade do pai/responsável', 'Escolaridade da mãe/responsável',
    'Ocupação do pai/responsável', 'Ocupação da mãe/responsável',
    'Moradores do domicílio', 'Possui renda própria', 'Renda mensal familiar',
    'Serviços de empregado(a) doméstico(a)', 'Banheiros', 'Quartos',
    'Carros', 'Motocicletas', 'Geladeiras', 'Freezer independente',
    'Máquina de lavar roupa', 'Micro-ondas', 'Aspirador de pó',
    'Televisão', 'TV por assinatura', 'Internet via Wi-Fi',
    'Computador/notebook', 'Celular', 'Trajetória escolar no Ensino Médio',
)
assert len(ROTULOS_ANTIGOS) == len(ROTULOS_ATUAIS) == len(QUESTOES)

NOTA = (
    'POP_SOCIO é composta por todos os registros da fonte de questionário, '
    'inclusive os que deixaram questões em branco: o denominador de cada '
    'distribuição é o total dessa fonte no recorte. Branco físico é categoria '
    'distinta, não se confunde com códigos de Não sei/Não informado. '
    'Até 2023 o questionário segue versão antiga e a partir de 2024 versão '
    'reformulada. Ex.: Q006 era renda familiar em 2019–2023 e Q007 passou a '
    'representar renda familiar em 2024–2025. A série histórica contém apenas '
    'contagens de participações socioeconômicas, sem somar códigos de perguntas '
    'incompatíveis. A nomenclatura de categoria preserva o código de origem, '
    'não interpreta códigos como grandezas numéricas. '
    'Uma agregação de categorias por questão/ano é aplicada simultaneamente '
    'a BR e todas as UFs, até toda contagem positiva divulgada ser >=30. '
    'Categorias agrupadas NÃO são semanticamente homogêneas. '
    'Isso não substitui a revisão de privacidade cruzada com outros indicadores. '
    'Não se estabelece relação causal nem representação de todas as pessoas '
    'inscritas além da cobertura efetiva dos arquivos. UF de prova, não residência. '
    'Histórico conta participações, não indivíduos únicos. '
    'Resultados DRAFT; revisão acadêmica e de divulgação pública pendentes.'
)


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise FileNotFoundError(f'Arquivo obrigatório ausente: {caminho}')
    with caminho.open(encoding='utf-8') as f:
        return json.load(f)


def gravar_json(caminho: Path, obj: dict) -> None:
    with caminho.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def fonte(raiz: Path, ano: int) -> Path:
    nome = (f'MICRODADOS_ENEM_{ano}.csv' if ano <= 2023
            else f'PARTICIPANTES_{ano}.csv')
    return raiz / 'data' / 'raw' / str(ano) / nome


def versao_questionario(ano: int) -> str:
    return '2019-2023' if ano <= 2023 else '2024-2025'


def rotulo(ano: int, questao: str) -> str:
    i = QUESTOES.index(questao)
    return (ROTULOS_ANTIGOS if ano <= 2023 else ROTULOS_ATUAIS)[i]


def referencias(raiz: Path, anos: tuple[int, ...]) -> dict[int, dict[str, int]]:
    """Confronta a abrangência da fonte socioeconômica com POP_ALL/IND-001."""
    d = ler_json(raiz / 'outputs' / 'json' / 'IND_001_redacoes_validas.json')
    if d.get('indicator', {}).get('id') != 'IND-001':
        raise ValueError('Referência IND-001 com identificador incorreto')
    result = {}
    for p in d.get('years', []):
        y = p.get('ano')
        if y in anos:
            ufs = {r['uf']: int(r['total_registros']) for r in p['ufs']}
            if set(ufs) != set(UFS):
                raise ValueError(f'IND-001 {y}: UFs ausentes')
            result[y] = {'BR': int(p['brasil']['total_registros']), **ufs}
            if result[y]['BR'] != sum(ufs.values()):
                raise ValueError(f'IND-001 {y}: BR não iguala 27 UFs')
    if set(result) != set(anos):
        raise ValueError('IND-001: ano(s) de referência faltando')
    return result


def _contagem_vazia() -> dict[str, dict[str, Counter]]:
    return {uf: {q: Counter() for q in QUESTOES} for uf in GEOS}


def ler_ano(raiz: Path, ano: int, bloco: int,
            esperado: dict[str, int]) -> tuple[dict[str, int], dict, dict]:
    caminho = fonte(raiz, ano)
    if not caminho.is_file():
        raise FileNotFoundError(f'{ano}: fonte do questionário não encontrada: {caminho}')
    n = Counter({uf: 0 for uf in GEOS})
    contagens = _contagem_vazia()
    total_chunks = 0
    try:
        iterador = pd.read_csv(
            caminho, sep=';', encoding='utf-8-sig', encoding_errors='replace',
            dtype=str, keep_default_na=False, na_filter=False,
            usecols=['SG_UF_PROVA', *QUESTOES],
            chunksize=bloco, on_bad_lines='error', low_memory=False,
        )
        for df in iterador:
            total_chunks += 1
            uf = df['SG_UF_PROVA'].str.strip().str.upper()
            invalidas = ~uf.isin(UFS)
            if invalidas.any():
                exemplos = sorted(uf[invalidas].drop_duplicates().head(5).tolist())
                raise ValueError(f'{ano}: UF inválida/ausente na fonte socioeconômica: {exemplos}')
            n['BR'] += len(df)
            n.update({str(k): int(v) for k, v in uf.value_counts().items()})
            for q in QUESTOES:
                categorias = df[q].str.strip()
                categorias = categorias.mask(categorias.eq(''), SEM_RESPOSTA)
                contagens['BR'][q].update(categorias.value_counts().to_dict())
                pares = pd.DataFrame({'uf': uf, 'codigo': categorias})
                por_uf = pares.groupby(['uf', 'codigo'], sort=False).size()
                for (geo, codigo), quantidade in por_uf.items():
                    contagens[str(geo)][q][str(codigo)] += int(quantidade)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f'{ano}: leitura de {caminho.name} falhou: {exc}') from exc

    if dict(n) != esperado:
        diferencas = {u: (int(n[u]), esperado[u]) for u in GEOS if n[u] != esperado[u]}
        raise ValueError(
            f'{ano}: POP_SOCIO da fonte difere dos registros IND-001 em {diferencas}. '
            'Conferir integridade, versão dos CSVs e fonte PARTICIPANTES (2024+).'
        )
    for q in QUESTOES:
        if sum(contagens['BR'][q].values()) != n['BR']:
            raise AssertionError(f'{ano}/{q}: distribuição BR não fecha')
        for categoria, total in contagens['BR'][q].items():
            if sum(contagens[u][q][categoria] for u in UFS) != total:
                raise AssertionError(f'{ano}/{q}/{categoria}: UFs não fecham com BR')
    return dict(n), contagens, {'ano': ano, 'arquivo': caminho.name,
                                'linhas': n['BR'], 'blocos': total_chunks,
                                'versao_questionario': versao_questionario(ano),
                                'comparacao_pop_all_ind001': 'ok'}


def coarsening_global(geo: dict[str, Counter], minimo: int = MIN_N
                      ) -> tuple[dict[str, Counter], set[str]]:
    """Agrupa códigos GLOBALMENTE em todas as UFs para prevenir inferência BR−UF.

    Se uma categoria for rara em qualquer UF, agrupa-a em OUTRAS em BR+27 UFs.
    Se o próprio conjunto OUTRAS tiver 1..29 numa UF, agrega a categoria
    remanescente de menor frequência nacional, repetindo até fechar.
    A política vale inclusive para ausência física de resposta.
    """
    if set(geo) != set(GEOS):
        raise ValueError('Conjunto geográfico incompleto')
    todos = set().union(*(set(geo[u]) for u in GEOS))
    raros = {cat for cat in todos
             if any(0 < geo[u][cat] < minimo for u in UFS)}
    separadas = set(todos) - raros
    while separadas and any(
        0 < sum(geo[u][c] for c in raros) < minimo for u in UFS
    ):
        doadora = min(separadas, key=lambda c: (geo['BR'][c], c))
        separadas.remove(doadora)
        raros.add(doadora)
    resultado = {}
    for u in GEOS:
        novo = Counter({cat: geo[u][cat] for cat in sorted(separadas) if geo[u][cat]})
        if raros:
            n = sum(geo[u][cat] for cat in raros)
            if n:
                novo[AGREGADAS] = n
        if sum(novo.values()) != sum(geo[u].values()):
            raise AssertionError(f'Agregação com perda de contagens: {u}')
        if any(0 < c < minimo for c in novo.values()):
            raise AssertionError(f'Célula pequena após coarsening: {u}')
        resultado[u] = novo
    for cat in set().union(*(set(resultado[u]) for u in GEOS)):
        if resultado['BR'][cat] != sum(resultado[u][cat] for u in UFS):
            raise AssertionError(f'Coarsening com diferença BR/UF na categoria {cat}')
    return resultado, raros


def serializar_distribuicao(ano: int, q: str, c: Counter, n: int,
                            agrupadas: set[str]) -> dict:
    if sum(c.values()) != n:
        raise AssertionError(f'{ano}/{q}: soma de categoria não coincide com população')
    # O percentual usa sempre POP_SOCIO, não apenas os que responderam à questão.
    categorias = []
    for codigo in sorted(c, key=lambda s: (s == AGREGADAS, s == SEM_RESPOSTA, s)):
        qtd = int(c[codigo])
        if not qtd:
            continue
        categorias.append({
            'codigo': codigo,
            'rotulo': ('Categorias consolidadas por configuração analítica'
                       if codigo == AGREGADAS else
                       'Sem resposta física' if codigo == SEM_RESPOSTA else codigo),
            'quantidade': qtd,
            'proporcao': round(qtd / n, 8) if n else None,
            'percentual': round(100 * qtd / n, 4) if n else None,
        })
    return {
        'questao': q,
        'tema': rotulo(ano, q),
        'versao_questionario': versao_questionario(ano),
        'populacao': 'POP_SOCIO',
        'denominador': n,
        'categorias': categorias,
        'categorias_originais_agrupadas': sorted(agrupadas),
        'tem_agregacao_para_privacidade': bool(agrupadas),
        'soma_categorias_fecha': sum(x['quantidade'] for x in categorias) == n,
    }


def montar_ano(ano: int, totais: dict[str, int], bruto: dict
              ) -> dict:
    final = {geo: {} for geo in GEOS}
    agrupamentos = 0
    for q in QUESTOES:
        por_uf = {uf: bruto[uf][q] for uf in GEOS}
        transformado, agrupadas = coarsening_global(por_uf)
        agrupamentos += int(bool(agrupadas))
        for u in GEOS:
            final[u][q] = serializar_distribuicao(
                ano, q, transformado[u], totais[u], agrupadas)
    def conteudo_geo(u: str) -> dict:
        return {'populacao': 'POP_SOCIO', 'n_participacoes': totais[u],
                'questoes': [final[u][q] for q in QUESTOES],
                'sem_registros_individuais': True}
    return {'ano': ano, 'versao_questionario': versao_questionario(ano),
            'brasil': conteudo_geo('BR'),
            'ufs': [{'uf': u, **conteudo_geo(u)} for u in UFS],
            'qualidade': {'status': 'ok',
                          'soma_27_ufs_igual_brasil': sum(totais[u] for u in UFS) == totais['BR'],
                          'questoes_processadas': len(QUESTOES),
                          'questoes_com_agregacao_nacional': agrupamentos,
                          'nenhuma_celula_divulgada_positiva_menor_30': not any(
                              0 < cat['quantidade'] < 30
                              for u in GEOS for q in QUESTOES
                              for cat in final[u][q]['categorias']),
                          'supressao_automatica_n_menor_30': False,
                          'identidades_individuais_exportadas': 0}}


def montar_historico(periodos: list[dict]) -> dict:
    """Apenas populações: perguntas distintas não são somadas artificialmente."""
    por_uf = {u: sum(next(p['brasil'] if u == 'BR' else
                              next(x for x in p['ufs'] if x['uf'] == u)
                              for p in periodos)['n_participacoes']
                      for p in periodos) for u in GEOS}
    # A compreensão acima mantém explicitamente a natureza somativa de
    # participações; nenhuma distribuição de respostas é adicionada.
    ano_min = min(p['ano'] for p in periodos)
    ano_max = max(p['ano'] for p in periodos)
    return {'periodo': f'{ano_min}-{ano_max}',
            'status': 'sem_distribuicao_agregada_sem_harmonizacao',
            'motivo': 'Q001..Q023 apresentam versões diferentes no período; não somar códigos sem harmonização.',
            'brasil': {'n_participacoes': por_uf['BR'], 'questoes': []},
            'ufs': [{'uf': u, 'n_participacoes': por_uf[u], 'questoes': []} for u in UFS],
            'qualidade': {'soma_27_ufs_igual_brasil':
                          sum(por_uf[u] for u in UFS) == por_uf['BR']}}


def group(periodo: dict, uf: str) -> dict:
    return periodo['brasil'] if uf == 'BR' else next(x for x in periodo['ufs'] if x['uf'] == uf)


def versao_dashboard(s: str) -> str:
    ids = list(dict.fromkeys(re.findall(r'ind\d{3}', s or '')))
    if 'ind040' not in ids:
        ids.append('ind040')
    return '2.40.0-' + '-'.join(ids)


def verificar_dashboard(doc: dict, ano: int) -> None:
    if doc.get('meta', {}).get('year') != ano:
        raise ValueError(f'Dashboard {ano}: meta.year incorreto')
    if doc.get('meta', {}).get('data_status') != 'draft':
        raise ValueError(f'Dashboard {ano}: somente dados draft são aceitos')
    for secao in ('socioeconomic', 'temporal', 'methodology'):
        if not isinstance(doc.get('pages', {}).get(secao), dict):
            raise ValueError(f'Dashboard {ano}: pages.{secao} ausente')
    if doc.get('quality', {}).get('indicator_validation', {}).get('status') != 'ok':
        raise ValueError(f'Dashboard {ano}: execute IND-001 antes do IND-040')


def atualizar_dashboard(doc: dict, p: dict, periodos: list[dict],
                       hist: dict, gerado: str) -> dict:
    novo = deepcopy(doc)
    page = novo['pages']['socioeconomic']
    page['profile'] = {
        'indicator_id': INDICADOR, 'populacao': 'POP_SOCIO',
        'ano': p['ano'], 'versao_questionario': p['versao_questionario'],
        'brasil': deepcopy(p['brasil']), 'ufs': deepcopy(p['ufs']),
        'observacao': 'Frequências descritivas; histórico por pergunta não harmonizado.',
    }
    page['status'] = 'ok'
    if page.get('reason') == 'indicadores_ainda_nao_implementados':
        page.pop('reason')
    novo['pages']['temporal']['ind040'] = {
        'indicator_id': INDICADOR,
        'yearly_population': [{'ano': r['ano'],
                               'n_pop_socio': r['brasil']['n_participacoes'],
                               'versao_questionario': r['versao_questionario']}
                              for r in periodos],
        'historico': {'periodo': hist['periodo'],
                      'n_participacoes': hist['brasil']['n_participacoes'],
                      'distribuicoes_harmonizadas': False},
        'comparabilidade': 'Questões não agregadas ao longo do tempo sem harmonização.'}
    novo['pages']['methodology']['ind040'] = {
        'indicator_id': INDICADOR, 'population': 'POP_SOCIO',
        'source': fonte(Path('.'), p['ano']).name,
        'questionnaire_version': p['versao_questionario'],
        'method': METODO, 'privacy_minimum_count': MIN_N,
        'notes': NOTA, 'data_status': 'draft',
    }
    novo['quality']['ind040_validation'] = {
        'status': 'ok', 'populacao': 'POP_SOCIO',
        'n_brasil': p['brasil']['n_participacoes'],
        'questoes_processadas': len(QUESTOES),
        'questoes_com_agregacao': p['qualidade']['questoes_com_agregacao_nacional'],
        'soma_27_ufs_igual_brasil': True,
        'nenhuma_celula_positiva_inferior_30': True,
        'historico_questoes_nao_harmonizado': True,
        'revisao_academica_pendente': True,
        'revisao_privacidade_complementar_pendente': True,
    }
    novo['meta']['generated_at'] = gerado
    novo['meta']['analysis_version'] = versao_dashboard(doc['meta'].get('analysis_version', ''))
    novo['meta']['data_status'] = 'draft'
    nome = fonte(Path('.'), p['ano']).name
    if nome not in novo['meta'].setdefault('source_files', []):
        novo['meta']['source_files'].append(nome)
    aviso = ('IND-040: questionários 2019–2023 e 2024–2025 diferem; '
             'categorias agregadas por privacidade; revisão acadêmica e divulgação pendentes.')
    if aviso not in novo['meta'].setdefault('warnings', []):
        novo['meta']['warnings'].append(aviso)
    return novo


def linhas_csv(periodos: list[dict], historico: dict) -> list[dict]:
    saida = []
    for periodo in periodos:
        for uf in GEOS:
            bloco = group(periodo, uf)
            for q in bloco['questoes']:
                for cat in q['categorias']:
                    saida.append({
                        'indicador_id': INDICADOR, 'periodo': str(periodo['ano']),
                        'uf': uf, 'versao_questionario': periodo['versao_questionario'],
                        'questao': q['questao'], 'tema': q['tema'],
                        'categoria': cat['codigo'], 'rotulo_categoria': cat['rotulo'],
                        'n_pop_socio': bloco['n_participacoes'],
                        'quantidade': cat['quantidade'],
                        'proporcao': cat['proporcao'], 'percentual': cat['percentual'],
                        'tem_agregacao_para_privacidade': q['tem_agregacao_para_privacidade'],
                        'status': 'draft',
                    })
    # Não publica históricos numéricos por Q sem mapeamento semântico validado.
    for uf in GEOS:
        h = group(historico, uf)
        saida.append({'indicador_id': INDICADOR,
                      'periodo': historico['periodo'], 'uf': uf,
                      'versao_questionario': 'nao_harmonizado',
                      'questao': None, 'tema': 'Distribuições históricas não harmonizadas',
                      'categoria': None, 'rotulo_categoria': None,
                      'n_pop_socio': h['n_participacoes'],
                      'quantidade': None, 'proporcao': None, 'percentual': None,
                      'tem_agregacao_para_privacidade': None,
                      'status': 'historico_sem_distribuicao_por_questao'})
    return saida


def executar(raiz: Path, anos: tuple[int, ...] = ANOS, bloco: int = 100_000,
             somente_modulo: bool = False, sobrescrever: bool = False) -> dict:
    raiz = raiz.resolve()
    anos = tuple(sorted(set(anos)))
    if not anos or not set(anos).issubset(ANOS):
        raise ValueError('--anos deve conter edições de 2019 a 2025')
    if bloco < 1:
        raise ValueError('--bloco deve ser positivo')
    refs = referencias(raiz, anos)
    pasta_json = raiz / 'outputs' / 'json'
    pasta_csv = raiz / 'outputs' / 'indicadores'
    destinos = [pasta_json / f'{ARQUIVO}.json', pasta_csv / f'{ARQUIVO}.csv']
    originais, hashes = {}, {}
    if not somente_modulo:
        for ano in anos:
            arq = pasta_json / f'dashboard_enem_{ano}.json'
            original = ler_json(arq)
            verificar_dashboard(original, ano)
            if not sobrescrever and (
                'profile' in original['pages']['socioeconomic'] or
                'ind040_validation' in original['quality']
            ):
                raise FileExistsError(f'IND-040 já presente no dashboard {ano}; use --sobrescrever')
            originais[ano] = original
            hashes[ano] = hashlib.sha256(arq.read_bytes()).hexdigest()
    if not sobrescrever:
        for arq in destinos:
            if arq.exists():
                raise FileExistsError(f'{arq} existe; use --sobrescrever')
    periodos, qa = [], {}
    for ano in anos:
        print(f'IND-040 | lendo {ano} ({fonte(raiz, ano).name})', flush=True)
        n, contagens, qualidade_fonte = ler_ano(raiz, ano, bloco, refs[ano])
        periodos.append(montar_ano(ano, n, contagens))
        qa[str(ano)] = qualidade_fonte
        print(f'  POP_SOCIO Brasil: {n["BR"]:,} participações; '
              f'perguntas: {len(QUESTOES)}', flush=True)
    historico = montar_historico(periodos)
    gerado = datetime.now(timezone.utc).isoformat(timespec='seconds')
    versao = versao_dashboard(originais[anos[0]]['meta'].get('analysis_version', '')) \
        if originais else '2.40.0-ind040'
    modulo = {
        'meta': {
            'indicator_id': INDICADOR, 'module_schema_version': 'ind040-module-1.0.0',
            'analysis_version': versao, 'dataset_version': 'enem-2019-2025-csv-publico',
            'generated_at': gerado, 'data_status': 'draft',
            'population_definition': 'POP_SOCIO = registros da fonte de questionário do ano',
            'geographic_dimension': 'SG_UF_PROVA', 'method': METODO,
            'minimum_group_count': MIN_N,
            'questionnaire_versions': {'2019-2023': 'original', '2024-2025': 'reformulado'},
            'years_processed': list(anos), 'source_qa': qa,
            'publication_status': 'draft; revisão acadêmica e privacidade cruzada pendentes',
            'notes': NOTA,
        },
        'indicator': {
            'id': INDICADOR, 'name': 'Perfil socioeconômico descritivo',
            'unit': 'frequencias_proporcoes',
            'dashboard_json_path': 'pages.socioeconomic.profile',
            'visualization': 'barras/tabelas',
        },
        'years': periodos, 'historical': historico,
        'dashboard_files': [f'dashboard_enem_{a}.json' for a in anos],
    }
    novos = ({ano: atualizar_dashboard(originais[ano], periodos[i], periodos,
                                     historico, gerado)
              for i, ano in enumerate(anos)} if not somente_modulo else {})
    for ano, doc in novos.items():
        for schema in (raiz / '04_resultados_analises.schema.json',
                       raiz / 'docs' / '04_resultados_analises.schema.json'):
            if schema.is_file():
                try:
                    import jsonschema
                except ImportError:
                    break
                jsonschema.validate(doc, ler_json(schema))
                break
    json.dumps(modulo, allow_nan=False)
    for doc in novos.values():
        json.dumps(doc, allow_nan=False)
    rows = linhas_csv(periodos, historico)
    if not rows:
        raise AssertionError('IND-040 não gerou linhas CSV')
    (raiz / 'outputs').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ind040_stage_', dir=raiz / 'outputs') as stage:
        temp = Path(stage)
        a_json, a_csv = temp / destinos[0].name, temp / destinos[1].name
        gravar_json(a_json, modulo)
        with a_csv.open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        entradas = [(a_json, destinos[0]), (a_csv, destinos[1])]
        for ano, doc in novos.items():
            arq = temp / f'dashboard_enem_{ano}.json'
            gravar_json(arq, doc)
            entradas.append((arq, pasta_json / arq.name))
        for ano in originais:
            arq = pasta_json / f'dashboard_enem_{ano}.json'
            if hashlib.sha256(arq.read_bytes()).hexdigest() != hashes[ano]:
                raise RuntimeError(f'Dashboard {ano} alterado durante IND-040; nenhuma saída escrita')
        backups = {}
        for _, destino in entradas:
            if destino.exists():
                backup = temp / f'{len(backups)}_{destino.name}.bak'
                backup.write_bytes(destino.read_bytes())
                backups[destino] = backup
        concluidos = []
        try:
            for origem, destino in entradas:
                destino.parent.mkdir(parents=True, exist_ok=True)
                os.replace(origem, destino)
                concluidos.append(destino)
        except Exception:
            for destino in reversed(concluidos):
                if destino in backups:
                    os.replace(backups[destino], destino)
                else:
                    destino.unlink(missing_ok=True)
            raise
    print(f'IND-040 concluído: {len(anos)} ano(s), {len(rows)} linhas CSV; '
          f'dashboards {"atualizados" if novos else "preservados"}.', flush=True)
    return modulo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=Path(__file__).resolve().parents[2],
                    help='raiz do repositório (padrão: dois níveis acima de src/indicadores)')
    ap.add_argument('--anos', type=int, nargs='+', default=list(ANOS),
                    help='edições selecionadas, ex.: --anos 2024 ou --anos 2024 2025')
    ap.add_argument('--bloco', type=int, default=100_000,
                    help='linhas lidas por bloco')
    ap.add_argument('--somente-modulo', action='store_true',
                    help='gera apenas CSV e JSON, sem modificar dashboards')
    ap.add_argument('--sobrescrever', action='store_true',
                    help='permite substituição dos resultados IND-040 existentes')
    args = ap.parse_args()
    executar(args.base, tuple(args.anos), args.bloco,
             args.somente_modulo, args.sobrescrever)


if __name__ == '__main__':
    main()
