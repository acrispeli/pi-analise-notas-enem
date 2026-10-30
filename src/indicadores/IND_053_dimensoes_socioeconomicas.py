#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-053 — Dimensões socioeconômicas (MCA) | Projeto Integrador IV — UNIVESP.

Catálogo ENEM 2019–2025 v2: pages.ml.socio_mca; AMOSTRA_SOCIO_ML.
MCA descritiva de 23 perguntas Q001..Q023 por edição (modelos NÃO alinhados).
Modelo complementar de núcleo comum: 14 conceitos harmonizados, MCA única
nas amostras selecionadas de dois ou mais anos cobrindo as duas versões.
Não usa notas, inscrições, nem junções com resultados, inclusive em 2025.
2019–23: MICRODADOS_ENEM_<ano>.csv; 2024–25: PARTICIPANTES_<ano>.csv.

Requer numpy, pandas, scipy e IND_045_tipo_escola_nota.py (leitura de CSV).
Exemplos (na raiz do repositório):
  python src/indicadores/IND_053_dimensoes_socioeconomicas.py --autoteste
  python src/indicadores/IND_053_dimensoes_socioeconomicas.py --anos 2024 2025 --somente-modulo --sobrescrever
  python src/indicadores/IND_053_dimensoes_socioeconomicas.py --sobrescrever

Saídas: outputs/json/IND_053_dimensoes_socioeconomicas.json
        outputs/indicadores/IND_053_dimensoes_socioeconomicas.csv
        dashboard_enem_<ano>.json -> pages.ml.socio_mca (se existente).
Status DRAFT: autoteste sintético não equivale à homologação com microdados.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

try:
    import IND_045_tipo_escola_nota as ind45
except ImportError as exc:
    raise SystemExit('Instale IND_045_tipo_escola_nota.py em src/indicadores, junto do IND-053.') from exc

ANOS = tuple(range(2019, 2026))
QUESTOES = tuple(f'Q{i:03d}' for i in range(1, 24))
NOME = 'IND_053_dimensoes_socioeconomicas'
LIMIAR = 30
AUSENTE = 'SEM_RESPOSTA'
INVALIDO = 'CODIGO_NAO_RECONHECIDO'
OUTRAS = 'OUTRAS_CATEGORIAS'
# Domínios exatos dos dicionários ENEM 2019–2025 (Q005 é numérico 1–20).
# As cinco edições 2019–23 compartilham os domínios indicados em HIST;
# 2024–25 compartilham REC. Homônimos Qxxx NÃO são harmonizados por nome.
DOMINIOS_HIST = {
    'Q001':'ABCDEFGH','Q002':'ABCDEFGH','Q003':'ABCDEF','Q004':'ABCDEF',
    'Q006':'ABCDEFGHIJKLMNOPQ','Q007':'ABCD','Q008':'ABCDE','Q009':'ABCDE',
    'Q010':'ABCDE','Q011':'ABCDE','Q012':'ABCDE','Q013':'ABCDE',
    'Q014':'ABCDE','Q015':'ABCDE','Q016':'ABCDE','Q017':'ABCDE',
    'Q018':'AB','Q019':'ABCDE','Q020':'AB','Q021':'AB',
    'Q022':'ABCDE','Q023':'AB',
}
DOMINIOS_REC = {
    'Q001':'ABCDEFGH','Q002':'ABCDEFGH','Q003':'ABCDEF','Q004':'ABCDEF',
    'Q006':'AB','Q007':'ABCDEFGHIJKLMNOPQ','Q008':'ABCD','Q009':'ABCD',
    'Q010':'ABCD','Q011':'ABCD','Q012':'ABCD','Q013':'ABCD',
    'Q014':'AB','Q015':'AB','Q016':'AB','Q017':'AB',
    'Q018':'ABCD','Q019':'AB','Q020':'AB','Q021':'ABCDE',
    'Q022':'ABCDE','Q023':'ABCDEF',
}

# Mapeamento conceitual explícito. Não se compara o ordinal das categorias
# antes de harmonizar os domínios A–E históricos com A–D/A–B recentes.
# Renda, internet/Wi-Fi, computador/notebook, freezer e tipo de escola NÃO
# integram o modelo conjunto por diferenças nas perguntas/categorias.
NUCLEO = {
    'escolaridade_pai': ('Q001', 'Q001', 'mesmo'),
    'escolaridade_mae': ('Q002', 'Q002', 'mesmo'),
    'ocupacao_pai': ('Q003', 'Q003', 'mesmo'),
    'ocupacao_mae': ('Q004', 'Q004', 'mesmo'),
    'moradores_domicilio': ('Q005', 'Q005', 'moradores'),
    'banheiros': ('Q008', 'Q009', 'contagem'),
    'quartos': ('Q009', 'Q010', 'contagem'),
    'carros': ('Q010', 'Q011', 'contagem'),
    'motocicletas': ('Q011', 'Q012', 'contagem'),
    'geladeiras': ('Q012', 'Q013', 'contagem'),
    'maquina_lavar': ('Q014', 'Q015', 'presenca'),
    'microondas': ('Q016', 'Q016', 'presenca'),
    'aspirador': ('Q018', 'Q017', 'mesmo'),
    'celulares_domicilio': ('Q022', 'Q022', 'presenca'),
}
CAMPOS_CSV = (
    'modelo', 'ano', 'dimensao', 'variavel', 'categoria', 'tipo_linha',
    'n_amostra', 'autovalor', 'inercia_pct', 'contribuicao_pct',
    'coordenada', 'frequencia_categoria',
)


def log(msg: str) -> None:
    print(msg, flush=True)


def fonte_ano(ano: int) -> str:
    if ano not in ANOS:
        raise ValueError(f'Indisponível: ano {ano}.')
    return (f'MICRODADOS_ENEM_{ano}.CSV' if ano <= 2023
            else f'PARTICIPANTES_{ano}.CSV')


def faixa_moradores(valor: Any) -> str:
    txt = '' if valor is None else str(valor).strip()
    if not txt:
        return AUSENTE
    if not re.fullmatch(r'\d+(?:[.,]0+)?', txt):
        return INVALIDO
    numero = int(re.split('[.,]', txt)[0])
    if not 1 <= numero <= 20:
        return INVALIDO
    if numero <= 4:
        return str(numero)
    if numero <= 6:
        return '5_6'
    if numero <= 9:
        return '7_9'
    return '10_20'


def codigo_nativo(valor: Any, campo: str, ano: int) -> str:
    if campo == 'Q005':
        return faixa_moradores(valor)
    txt = '' if valor is None else str(valor).strip().upper()
    if not txt or txt in ('NAN', 'NULL', 'NONE', '<NA>'):
        return AUSENTE
    dominio = DOMINIOS_HIST if ano <= 2023 else DOMINIOS_REC
    return txt if txt in dominio[campo] else INVALIDO


def codigo_nucleo(valor: str, tipo: str, ano: int) -> str:
    if valor in (AUSENTE, INVALIDO):
        return valor
    if tipo in ('mesmo', 'moradores'):
        return valor
    if tipo == 'presenca':
        if valor == 'A':
            return 'NAO'
        if valor in 'BCDE':
            return 'SIM'
        return INVALIDO
    if tipo == 'contagem':
        if valor == 'A':
            return '0'
        if valor == 'B':
            return '1'
        if valor == 'C':
            return '2'
        if valor == 'D' or (ano <= 2023 and valor == 'E'):
            return '3_OU_MAIS'
        return INVALIDO
    raise ValueError('Harmonização não implementada: ' + tipo)


def normalizar_lote(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    return pd.DataFrame({q: df[q].map(lambda v, q=q: codigo_nativo(v, q, ano)) for q in QUESTOES})


def preparar_nucleo(amostra: pd.DataFrame, ano: int) -> pd.DataFrame:
    colunas = {}
    for conceito, (antigo, recente, tipo) in NUCLEO.items():
        origem = antigo if ano <= 2023 else recente
        colunas[conceito] = amostra[origem].map(
            lambda x, t=tipo, a=ano: codigo_nucleo(x, t, a))
    return pd.DataFrame(colunas, index=amostra.index)


def amostrar_ano(arquivo: Path, ano: int, limite: int, bloco: int,
                 seed: int) -> tuple[pd.DataFrame, dict]:
    """Amostragem uniforme sem reposição: menores chaves aleatórias globais.

    Mantém no máximo `limite` registros; não armazena NU_INSCRICAO/nota.
    Mesma fonte, bloco e seed -> mesma amostra. N real é contado integralmente.
    """
    if limite < 100 or bloco < 1:
        raise ValueError('--amostra deve ser >=100 e --bloco deve ser >=1.')
    rng = np.random.default_rng(seed + ano)
    selecionados = pd.DataFrame(columns=QUESTOES)
    chaves = np.empty(0, dtype='float64')
    n_lidos = 0
    for parte in ind45.ler_blocos(arquivo, list(QUESTOES), bloco):
        n_lidos += len(parte)
        if parte.empty:
            continue
        valores = normalizar_lote(parte, ano).reset_index(drop=True)
        prioridades = rng.random(len(valores))
        # Pré-seleção reduz o custo do merge em arquivos muito grandes.
        if len(prioridades) > limite:
            escolhidos = np.argpartition(prioridades, limite - 1)[:limite]
            valores = valores.iloc[escolhidos].reset_index(drop=True)
            prioridades = prioridades[escolhidos]
        selecionados = pd.concat((selecionados, valores), ignore_index=True)
        chaves = np.concatenate((chaves, prioridades))
        if len(chaves) > limite:
            idx = np.argpartition(chaves, limite - 1)[:limite]
            selecionados = selecionados.iloc[idx].reset_index(drop=True)
            chaves = chaves[idx]
    if n_lidos == 0:
        raise ValueError(f'{arquivo.name}: arquivo sem participantes.')
    n_invalidos = {q: int(selecionados[q].eq(INVALIDO).sum()) for q in QUESTOES}
    # Falha explícita quando parte relevante dos códigos não segue os
    # dicionários (notadamente Q004 com tipo numérico incorreto na planilha).
    graves = {q: v for q,v in n_invalidos.items()
              if v > max(10, math.ceil(0.02*len(selecionados)))}
    if graves:
        raise ValueError(f'{ano}: códigos fora do dicionário em mais de 2% da amostra: {graves}. '
                         'Inspecione o CSV sem substituir categorias por suposição.')
    if len(selecionados) != min(limite, n_lidos):
        raise AssertionError('Amostragem não fechou a contagem esperada.')
    return selecionados.reset_index(drop=True), {
        'ano': ano, 'fonte': arquivo.name, 'populacao': 'POP_SOCIO',
        'n_fonte': n_lidos, 'n_amostra': len(selecionados),
        'fracao_amostral_pct': round(100*len(selecionados)/n_lidos, 5),
        'aleatorizacao': 'chaves_aleatorias_iid_prioridades_minimas',
        'seed_efetiva': seed + ano, 'ordem_csv_relevante': True,
        'sem_notas_sem_join': True,
        'codigos_invalidos_na_amostra_por_questao': {
            q: int(v)  # Auditoria agregada: não mascarar contagens pequenas.
            for q, v in n_invalidos.items()},
    }


def _unificar_raros(tabela: pd.DataFrame, min_n: int) -> tuple[pd.DataFrame, dict]:
    """Agrupa categorias raras; nunca publica categorias com 1..min_n-1.

    Se OUTRAS não alcança o limiar, absorve na categoria modal. Essas
    incorporações ficam registradas apenas em totais, sem códigos de origem.
    """
    tabela = tabela.copy()
    resumo: dict[str, int] = {}
    for coluna in tabela.columns:
        f = tabela[coluna].value_counts(dropna=False)
        raras = f[(f < min_n) & (f > 0)].index.tolist()
        n_agrupados = int(f.loc[raras].sum()) if raras else 0
        if raras:
            tabela[coluna] = tabela[coluna].where(~tabela[coluna].isin(raras), OUTRAS)
            pos = int((tabela[coluna] == OUTRAS).sum())
            if 0 < pos < min_n:
                # Sem grupo OUTRAS publicável, incorporar ao modal.
                f2 = tabela.loc[tabela[coluna] != OUTRAS, coluna].value_counts()
                if not f2.empty:
                    tabela.loc[tabela[coluna] == OUTRAS, coluna] = f2.index[0]
                else:
                    # Se N total < limiar, a análise inteira deve ser bloqueada.
                    raise ValueError('Amostra total abaixo do limiar de privacidade.')
        resumo[coluna] = n_agrupados
    return tabela, resumo


def ajustar_mca(dados: pd.DataFrame, n_componentes: int = 3,
                limiar: int = LIMIAR) -> dict:
    """MCA exata via decomposição espectral da matriz de Burt centralizada.

    Z: indicadora completa com q categorias ativas por indivíduo;
    p_j = contagem da categoria / n. Matriz de correspondências padronizada:
        S = (Z - 1 p^T) / sqrt(n*q*p_j)
    Calculamos S^T S sem matriz densa n×K, via csr(Z)^T csr(Z).
    Autovalores são inércias principais MCA, não variâncias PCA.
    Coordenadas principais de categorias: v_j sqrt(lambda*q/p_j).
    Contribuição da categoria ao eixo: v_j² (soma 1); sinal arbitrário
    orientado por categoria de maior |v_j| em cada eixo.
    """
    if n_componentes < 1:
        raise ValueError('Número de dimensões deve ser >=1.')
    if len(dados) < max(limiar, 100):
        raise ValueError('Amostra insuficiente para MCA e limiar de divulgação.')
    dados, raros = _unificar_raros(dados, limiar)
    ativos = [col for col in dados if dados[col].nunique() >= 2]
    excluidos = [col for col in dados if col not in ativos]
    if len(ativos) < 2:
        raise ValueError('Pelo menos duas variáveis não constantes são necessárias.')
    n = len(dados)
    q = len(ativos)
    categorias = []
    linhas, colunas = [], []
    for j, campo in enumerate(ativos):
        fator = pd.Categorical(dados[campo], categories=sorted(dados[campo].unique()))
        # Evita overflow de int8 ao somar offsets de mais de 127 categorias.
        codigo = fator.codes.astype(np.int64, copy=False)
        if (codigo < 0).any():
            raise ValueError('Categorias ausentes após normalização.')
        offset = len(categorias)
        for cat in fator.categories:
            categorias.append((campo, str(cat)))
        linhas.extend(range(n))
        colunas.extend((codigo + offset).tolist())
    k = len(categorias)
    z = sparse.csr_matrix((np.ones(len(linhas), dtype='float64'),
                           (linhas, colunas)), shape=(n, k))
    contagens = np.asarray(z.sum(axis=0)).ravel()
    p = contagens/n
    base = (z.T @ z).toarray()/n - np.outer(p, p)
    base /= q*np.sqrt(np.outer(p, p))
    base = (base + base.T)/2
    autovalores, vetores = np.linalg.eigh(base)
    ordem = np.argsort(autovalores)[::-1]
    autovalores = np.maximum(autovalores[ordem], 0)
    vetores = vetores[:, ordem]
    inercia_total = (k-q)/q
    trace_observado = float(np.trace(base))
    if not math.isclose(trace_observado, inercia_total, rel_tol=2e-8, abs_tol=1e-8):
        raise AssertionError(f'Inércia MCA inconsistente: {trace_observado} vs {inercia_total}.')
    dimensoes = []
    for eixo in range(min(n_componentes, len(autovalores))):
        auto = float(autovalores[eixo])
        if auto <= 1e-10:
            break
        vetor = vetores[:, eixo].copy()
        if vetor[np.argmax(np.abs(vetor))] < 0:
            vetor *= -1
        contribuicoes = 100*vetor**2
        coords = vetor*np.sqrt(auto*q/p)
        if not np.isclose(contribuicoes.sum(), 100, atol=1e-5):
            raise AssertionError('Contribuições de categorias não totalizam 100%.')
        vars_contrib = {}
        cat_linhas = []
        for i, (campo, cat) in enumerate(categorias):
            vars_contrib[campo] = vars_contrib.get(campo, 0.) + float(contribuicoes[i])
            cat_linhas.append({
                'variavel': campo, 'categoria': cat, 'frequencia': int(contagens[i]),
                'contribuicao_pct': round(float(contribuicoes[i]), 6),
                'coordenada': round(float(coords[i]), 6),
            })
        dimensoes.append({
            'eixo': eixo+1, 'autovalor': round(auto, 9),
            'inercia_pct': round(100*auto/inercia_total, 6),
            'contribuicoes_variaveis_pct': {k: round(v, 6) for k, v in
                                          sorted(vars_contrib.items(), key=lambda kv: -kv[1])},
            'categorias': cat_linhas,
        })
    return {
        'n_amostra': n, 'n_variaveis_ativas': q, 'n_categorias_ativas': k,
        'variaveis_inativas': excluidos,
        'variaveis_com_agregacao_de_raros': sum(1 for v in raros.values() if v > 0),
        'limiar_categoria': limiar,
        'inercia_total': round(inercia_total, 9),
        'inercia_acumulada_primeiros_eixos_pct': round(sum(x['inercia_pct'] for x in dimensoes), 6),
        'dimensoes': dimensoes,
        'algoritmo': 'MCA_inercia_exata_Burt_centralizada_eigh',
        'unidade_analise': 'resposta_anonima_amostrada',
        'observacao': 'Os autovalores representam inércia MCA; não são variância explicada de PCA.',
    }


def conferir_ind040(caminho: Path, controles: dict[int, dict]) -> dict:
    """Concilia N total das fontes com IND-040, sem confundir amostra e população."""
    if not caminho.exists():
        return {'status': 'pendente', 'motivo': f'IND-040 não encontrado: {caminho}'}
    doc = json.loads(caminho.read_text(encoding='utf-8-sig'))
    if doc.get('meta', {}).get('indicator_id') != 'IND-040':
        raise ValueError('Arquivo referência não corresponde ao IND-040.')
    ano_ref = {int(r['ano']): r for r in doc.get('years', [])}
    for ano, info in controles.items():
        if ano not in ano_ref:
            raise ValueError(f'IND-040 não contém {ano}.')
        esperado = int(ano_ref[ano]['brasil']['n_participacoes'])
        if esperado != info['n_fonte']:
            raise ValueError(f'IND-053 {ano}: N={info["n_fonte"]} ≠ IND-040 N={esperado}.')
    return {'status': 'ok', 'anos_conferidos': sorted(controles)}


def estrutura(anos: dict[int, dict], global_mca: dict | None, controles: dict,
              qa_referencia: dict, seed: int, limite: int) -> dict:
    return {
        'indicator_id': 'IND-053', 'slug': NOME,
        'title': 'Dimensões socioeconômicas — MCA',
        'module_schema_version': 'ind053-module-1.0.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_status': 'draft',
        'population': 'AMOSTRA_SOCIO_ML',
        'population_source': 'POP_SOCIO (todos os participantes da base de questionário)',
        'model_method': 'analise_de_correspondencia_multipla_MCA',
        'seed': seed, 'tamanho_maximo_amostra_por_ano': limite,
        'questions_native': list(QUESTOES),
        'core_harmonization': {
            'version': 'nucleo_14_conceitos_v1',
            'mapping': {c: {'2019_2023': a, '2024_2025': b, 'regra': t}
                        for c,(a,b,t) in NUCLEO.items()},
            'excluded_from_pooled_model': [
                'renda (Q006 histórico / Q007 recente: limites econômicos variáveis)',
                'internet geral Q025 / Wi-Fi Q020: conceitos distintos',
                'computador Q024 / computador/notebook Q021: conceitos distintos',
                'freezer (inclui segunda porta vs independente)',
                'tipo de escola Q023: somente versão recente',
            ],
            'rule': 'contagem A=0; B=1; C=2; D/E antigos=3+; D recentes=3+; '
                    'lavadora/micro-ondas/celular convertidos a ausência/presença; '
                    'Q005 em 7 faixas; sem comparação de moedas ou salários mínimos',
        },
        'years': {str(ano): item for ano,item in sorted(anos.items())},
        'pooled_core_mca': global_mca,
        'quality': {
            'annual_source': {str(ano): x for ano,x in sorted(controles.items())},
            'ind040_reconciliation': qa_referencia,
            'no_personal_ids_or_scores_exported': True,
            'join_diagnostics': {'status': 'nao_aplicavel', 'motivo': 'Questionário isolado, sem notas.'},
            'privacy': {'minimum_category_sample_size': LIMIAR,
                        'rare_categories_collapsed': True,
                        'cross_indicator_disclosure_review': 'pendente'},
            'caveats': [
                'MCA por ano usa 23 perguntas com significados distintos em 2019–23 e 2024–25; coordenadas não são comparáveis.',
                'MCA de núcleo harmonizado é um modelo conjunto: seus eixos são internos à amostra e não estimam causalidade.',
                'Amostras por ano de tamanhos similares não reproduzem automaticamente o peso populacional anual.',
                'A inércia MCA não é variância explicada de PCA; interpretar categoria e eixo após inspeção.',
                'As coordenadas de categorias nunca representam indivíduos e podem inverter sinal sem alterar o modelo.',
                'Não há relação individual com notas da redação, inclusive em 2025.',
            ],
        },
    }


def criar_csv(doc: dict) -> list[dict]:
    saida = []
    modelos = [(f'anual_{ano}', str(ano), r['mca']) for ano, r in doc['years'].items()]
    if doc['pooled_core_mca'] is not None:
        modelos.append(('nucleo_harmonizado_conjunto', '2019_2025', doc['pooled_core_mca']))
    for nome, ano, modelo in modelos:
        for d in modelo['dimensoes']:
            for var, valor in d['contribuicoes_variaveis_pct'].items():
                saida.append({'modelo': nome, 'ano': ano, 'dimensao': d['eixo'],
                              'variavel': var, 'categoria': '', 'tipo_linha': 'variavel',
                              'n_amostra': modelo['n_amostra'], 'autovalor': d['autovalor'],
                              'inercia_pct': d['inercia_pct'], 'contribuicao_pct': valor,
                              'coordenada': '', 'frequencia_categoria': ''})
            for cat in d['categorias']:
                saida.append({'modelo': nome, 'ano': ano, 'dimensao': d['eixo'],
                              'variavel': cat['variavel'], 'categoria': cat['categoria'],
                              'tipo_linha': 'categoria', 'n_amostra': modelo['n_amostra'],
                              'autovalor': d['autovalor'], 'inercia_pct': d['inercia_pct'],
                              'contribuicao_pct': cat['contribuicao_pct'],
                              'coordenada': cat['coordenada'],
                              'frequencia_categoria': cat['frequencia']})
    return saida


def salvar_json(caminho: Path, obj: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_name(caminho.name + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')
    temp.replace(caminho)


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + '.tmp')
    with tmp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=';', extrasaction='raise')
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(caminho)


def atualizar_dashboard(arquivo: Path, item: dict, conjunto: dict | None) -> bool:
    if not arquivo.exists():
        return False
    doc = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    if not isinstance(doc.get('pages'), dict):
        raise ValueError(f'Dashboard não contém pages: {arquivo}')
    doc['pages'].setdefault('ml', {})['socio_mca'] = {
        'indicator_id': 'IND-053', 'data_status': 'draft',
        'ano': item['ano'], 'modelo_ano': item['mca'],
        'modelo_nucleo_conjunto': conjunto,
        'nota': 'Modelos anuais não alinhados; eixos do conjunto são da amostra harmonizada.'}
    doc.setdefault('quality', {})['ind053_validation'] = {
        'status': 'draft', 'n_fonte': item['n_fonte'], 'n_amostra': item['n_amostra'],
        'sem_join': True, 'supressao_categoria_n': LIMIAR}
    salvar_json(arquivo, doc)
    return True


def executar(base: Path, saida: Path, anos: tuple[int,...], limite: int,
             bloco: int, seed: int, componentes: int, sobrescrever: bool,
             somente_modulo: bool, referencia: Path | None = None) -> dict:
    if not anos or any(a not in ANOS for a in anos):
        raise ValueError('Escolha de anos inválida.')
    if limite < 100 or bloco < 1 or componentes < 1 or componentes > 6:
        raise ValueError('Parâmetros de amostra/bloco/eixos inválidos.')
    caminho_json = saida/'outputs'/'json'/f'{NOME}.json'
    caminho_csv = saida/'outputs'/'indicadores'/f'{NOME}.csv'
    if not sobrescrever and (caminho_json.exists() or caminho_csv.exists()):
        raise FileExistsError('Saída já existente; confirme atualização com --sobrescrever.')
    nomes = {fonte_ano(x) for x in anos}
    fontes = ind45.localizar_fontes(base, nomes)
    faltam = sorted(nomes-set(fontes))
    if faltam:
        raise FileNotFoundError('Não foram encontradas as fontes: ' + ', '.join(faltam))
    registros: dict[int,dict] = {}
    controles: dict[int,dict] = {}
    nucleo_anos = []
    for ano in anos:
        log(f'IND-053: lendo {ano}, fonte {fontes[fonte_ano(ano)].name} ...')
        amostra, qa = amostrar_ano(fontes[fonte_ano(ano)], ano, limite, bloco, seed)
        if qa['n_amostra'] < 100:
            raise ValueError(f'{ano}: amostra insuficiente.')
        modelo = ajustar_mca(amostra, componentes)
        registros[ano] = {'ano': ano, 'status': 'draft', 'n_fonte': qa['n_fonte'],
                          'n_amostra': qa['n_amostra'], 'versao_questionario':
                          '2019-2023' if ano <=2023 else '2024-2025',
                          'mca': modelo}
        controles[ano] = qa
        nucleo = preparar_nucleo(amostra, ano)
        nucleo_anos.append(nucleo)
        log(f'  N fonte={qa["n_fonte"]:,}; amostra={len(amostra):,}; '
            f'variáveis MCA={modelo["n_variaveis_ativas"]}; eixos={len(modelo["dimensoes"])}')
    ref = referencia or (base/'outputs'/'json'/'IND_040_perfil_socioeconomico.json')
    if not ref.is_absolute():
        ref = base/ref
    qa_ref = conferir_ind040(ref, controles)
    if qa_ref['status'] != 'ok':
        log('  ATENÇÃO: IND-040 não encontrado; conciliação N pendente.')
    # Núcleo pooled só se as duas famílias de questionário estiverem presentes:
    # caso contrário, as coordenadas seriam apresentadas como harmonizadas sem
    # evidência de reconciliação entre versões.
    comparar = any(a <= 2023 for a in anos) and any(a >= 2024 for a in anos)
    combinado = None
    if comparar:
        combinado = ajustar_mca(pd.concat(nucleo_anos, ignore_index=True), componentes)
        combinado['years_in_training'] = list(anos)
        combinado['interpretation'] = ('Eixos comuns apenas para variáveis com recodificação explícita; '
                                      'amostra estratificada por ano, não ponderada pela população anual.')
    else:
        log('  MCA conjunta não produzida: seleção de anos contém uma única versão do questionário.')
    doc = estrutura(registros, combinado, controles, qa_ref, seed, limite)
    linhas_csv = criar_csv(doc)
    salvar_json(caminho_json, doc)
    salvar_csv(caminho_csv, linhas_csv)
    n_dash = 0
    if not somente_modulo:
        for ano, item in registros.items():
            p = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
            if atualizar_dashboard(p, item, combinado):
                n_dash += 1
    log(f'IND-053: JSON={caminho_json}; CSV={caminho_csv} ({len(linhas_csv):,} linhas).')
    log(f'IND-053: dashboards atualizados: {n_dash}; status DRAFT (revisão real pendente).')
    return doc


def autoteste() -> None:
    assert faixa_moradores('1') == '1'
    assert faixa_moradores('20') == '10_20'
    assert faixa_moradores('20.0') == '10_20'
    assert faixa_moradores('21') == INVALIDO
    assert codigo_nativo('', 'Q001', 2019) == AUSENTE
    assert codigo_nativo('b', 'Q003', 2024) == 'B'
    assert codigo_nativo('Z', 'Q003', 2024) == INVALIDO
    assert codigo_nativo('E', 'Q008', 2024) == INVALIDO
    assert codigo_nativo('E', 'Q008', 2019) == 'E'
    assert codigo_nativo('1', 'Q004', 2024) == INVALIDO
    assert codigo_nucleo('E', 'contagem', 2023) == '3_OU_MAIS'
    assert codigo_nucleo('D', 'contagem', 2024) == '3_OU_MAIS'
    assert codigo_nucleo('E', 'presenca', 2023) == 'SIM'
    assert NUCLEO['microondas'][0] == 'Q016' and NUCLEO['microondas'][1] == 'Q016'
    np_rng = np.random.default_rng(530)
    with tempfile.TemporaryDirectory(prefix='ind053_teste_') as temp:
        base = Path(temp)
        pasta = base/'raw'
        pasta.mkdir()
        ano_ids = (2019,2024,2025)
        n = 700
        totais = {}
        for ano in ano_ids:
            rows = {}
            for q in QUESTOES:
                if q == 'Q005':
                    rows[q] = np_rng.choice([1,2,3,4,5,7,10,20], size=n).astype(str)
                else:
                    dominio = DOMINIOS_HIST if ano <= 2023 else DOMINIOS_REC
                    opcoes = list(dominio[q])
                    pesos = np.array([2.0**(-k/3) for k in range(len(opcoes))])
                    pesos /= pesos.sum()
                    rows[q] = np_rng.choice(opcoes, size=n, p=pesos).astype(str)
            # Correlação real por construção: Q001/Q002 devem compartilhar padrões.
            rows['Q002'] = np.array(rows['Q001'], copy=True)
            rows['Q010'] = np.array(rows['Q009'], copy=True)
            rows['Q001'][0] = 'Z'  # codigo invalido raro agrupado, sem vazamento
            pd.DataFrame(rows).to_csv(pasta/fonte_ano(ano), sep=';', index=False)
            totais[ano] = n
        ref = {'meta':{'indicator_id':'IND-040'},'years':[
            {'ano': ano, 'brasil':{'n_participacoes':n}} for ano in ano_ids]}
        ref_file=base/'outputs'/'json'/'IND_040_perfil_socioeconomico.json'
        salvar_json(ref_file, ref)
        dados_2019, c = amostrar_ano(pasta/fonte_ano(2019), 2019, 500, 91, 44)
        dados_2019b, c2 = amostrar_ano(pasta/fonte_ano(2019), 2019, 500, 91, 44)
        pd.testing.assert_frame_equal(dados_2019, dados_2019b)
        assert c['n_fonte'] == 700 and c['n_amostra'] == 500
        assert dados_2019['Q001'].eq('Z').sum() == 0
        mc = ajustar_mca(dados_2019, 3)
        assert mc['n_variaveis_ativas'] == 23
        assert mc['dimensoes'][0]['autovalor'] >= mc['dimensoes'][1]['autovalor']
        assert math.isclose(sum(mc['dimensoes'][0]['contribuicoes_variaveis_pct'].values()),
                            100, abs_tol=.0002)
        assert all(x['frequencia'] >= LIMIAR for x in mc['dimensoes'][0]['categorias'])
        core_19 = preparar_nucleo(dados_2019, 2019)
        assert set(core_19) == set(NUCLEO)
        # Confere agregação D/E antigos vs D recente na harmonização.
        d_old = pd.DataFrame({q: ['A'] for q in QUESTOES})
        d_new = d_old.copy()
        d_old['Q008'] = ['E']; d_new['Q009'] = ['D']
        assert preparar_nucleo(d_old, 2019)['banheiros'][0] == '3_OU_MAIS'
        assert preparar_nucleo(d_new, 2024)['banheiros'][0] == '3_OU_MAIS'
        saida=base/'results'
        dash_dir=saida/'outputs'/'json'
        dash_dir.mkdir(parents=True)
        for ano in ano_ids:
            salvar_json(dash_dir/f'dashboard_enem_{ano}.json', {
                'meta': {'dataset_version': 'teste'},
                'pages': {'overview': {'preservar': True},'ml': {'pca': {'preservar': True}}},
                'quality': {'flag_outra': True},
            })
        doc=executar(base, saida, ano_ids, 550, 119, 2026, 3, False, False)
        assert len(doc['years']) == 3
        assert doc['quality']['ind040_reconciliation']['status'] == 'ok'
        assert doc['pooled_core_mca'] is not None
        assert doc['pooled_core_mca']['n_variaveis_ativas'] == len(NUCLEO)
        assert doc['pooled_core_mca']['n_amostra'] == 1650
        saida_csv = saida/'outputs'/'indicadores'/f'{NOME}.csv'
        saida_json = saida/'outputs'/'json'/f'{NOME}.json'
        assert saida_csv.is_file() and saida_json.is_file()
        with saida_csv.open(encoding='utf-8-sig', newline='') as f:
            csv_linhas=list(csv.DictReader(f, delimiter=';'))
        assert len(csv_linhas)>500
        for ano in ano_ids:
            p=dash_dir/f'dashboard_enem_{ano}.json'
            dj=json.loads(p.read_text(encoding='utf-8'))
            assert dj['pages']['overview']['preservar']
            assert dj['pages']['ml']['pca']['preservar']
            assert dj['pages']['ml']['socio_mca']['ano'] == ano
        try:
            executar(base, saida, ano_ids, 550, 119, 2026, 3, False, False)
        except FileExistsError:
            pass
        else:
            raise AssertionError('--sobrescrever obrigatório não foi aplicado.')
        ref['years'][0]['brasil']['n_participacoes'] = 701
        salvar_json(ref_file, ref)
        try:
            conferir_ind040(ref_file, {2019:{'n_fonte':700}})
        except ValueError:
            pass
        else:
            raise AssertionError('Divergência IND-040 não foi detectada.')
        # Rodada isolada 2025 só em módulo: não cria um núcleo conjunto
        antes=(dash_dir/'dashboard_enem_2025.json').read_bytes()
        parcial=executar(base, saida, (2025,), 250, 119, 2026, 2, True, True)
        assert parcial['pooled_core_mca'] is None
        assert antes == (dash_dir/'dashboard_enem_2025.json').read_bytes()
    log('AUTOTESTE IND-053 APROVADO | 2019, 2024, 2025 | '
        '2.100 participantes sintéticos | MCA anual + núcleo harmonizado')


def main() -> None:
    ap = argparse.ArgumentParser(description='IND-053 — Dimensões socioeconômicas (MCA)')
    ap.add_argument('--autoteste', action='store_true')
    ap.add_argument('--base', type=Path, default=ind45.raiz_projeto())
    ap.add_argument('--saida', type=Path, default=None)
    ap.add_argument('--anos', type=int, nargs='+', choices=ANOS, default=list(ANOS))
    ap.add_argument('--amostra', type=int, default=15_000,
                    help='Número máximo de participantes por ano (padrão: 15000)')
    ap.add_argument('--bloco', type=int, default=100_000)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--componentes', type=int, default=3, choices=range(1,7))
    ap.add_argument('--sobrescrever', action='store_true')
    ap.add_argument('--somente-modulo', action='store_true')
    ap.add_argument('--referencia-ind040', type=Path, default=None)
    args = ap.parse_args()
    if args.autoteste:
        autoteste()
    else:
        executar(args.base.resolve(), (args.saida or args.base).resolve(),
                 tuple(sorted(set(args.anos))), args.amostra, args.bloco,
                 args.seed, args.componentes, args.sobrescrever,
                 args.somente_modulo, args.referencia_ind040)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f'ERRO IND-053: {type(e).__name__}: {e}')
        sys.exit(1)
