# -*- coding: utf-8 -*-
"""Leitura sem Streamlit dos indicadores IND-023..031 e IND-040..041.

Não lê microdados, não altera dashboard e não preenche resultados ausentes.
"""
from __future__ import annotations

from collections.abc import Mapping

INDICADORES = {
    23: ('evaluators', 'status_disagreement'),
    24: ('evaluators', 'third_reviewer'),
    25: ('evaluators', 'panel_details'),
    26: ('evaluators', 'weighted_kappa'),
    27: ('evaluators', 'icc'),
    28: ('evaluators', 'divergence_clusters'),
    29: ('evaluators', 'anomalies'),
    30: ('high_performance', 'score_bands'),
    31: ('high_performance', 'loss_by_competency'),
    40: ('socioeconomic', 'profile'),
    41: ('socioeconomic', 'income_total'),
}
FAIXAS_RENDA = tuple('ABCDEFGHIJKLMNOPQ')


def bloco(dashboard: Mapping | None, indicador: int) -> dict | None:
    """Retorna módulo publicado no dashboard da edição ou None, sem fallback entre anos."""
    if not isinstance(dashboard, Mapping) or indicador not in INDICADORES:
        return None
    pagina, chave = INDICADORES[indicador]
    pagina_obj = dashboard.get('pages', {}).get(pagina, {})
    obj = pagina_obj.get(chave)
    if not isinstance(obj, dict) or obj.get('indicator_id') != f'IND-{indicador:03d}':
        return None
    return obj


def recorte(dashboard: Mapping | None, indicador: int, uf: str = 'BR') -> dict | None:
    """Devolve exatamente o recorte BR/UF salvo na edição selecionada."""
    obj = bloco(dashboard, indicador)
    if obj is None:
        return None
    if indicador == 41:
        if uf == 'BR':
            return obj.get('national')
        return obj.get('states', {}).get(uf)
    if indicador == 40:
        if uf == 'BR':
            return obj.get('brasil')
        ufs = obj.get('ufs', [])
    else:
        if uf == 'BR':
            return obj.get('brasil')
        ufs = obj.get('by_uf', [])
    if isinstance(ufs, Mapping):
        return ufs.get(uf)
    return next((r for r in ufs if isinstance(r, dict) and r.get('uf') == uf), None)


def validar_renda(obj: dict | None) -> list[str]:
    """Checagens internas mínimas para impedir gráfico baseado em um recorte incompleto."""
    if not isinstance(obj, dict):
        return ['Recorte do IND-041 ausente.']
    erros = []
    categorias = obj.get('categories') or []
    codigos = [r.get('codigo_renda') for r in categorias]
    if codigos[:17] != list(FAIXAS_RENDA):
        erros.append('Categorias A–Q ausentes ou fora de ordem.')
    n = obj.get('n_redacoes_validas')
    if not isinstance(n, int) or n < 0:
        erros.append('Denominador de redações inválido.')
    else:
        soma = sum(int(r.get('n_redacoes', 0)) for r in categorias)
        if soma != n:
            erros.append(f'Categorias ({soma}) não fecham com redações válidas ({n}).')
        if obj.get('n_renda_declarada', 0) + obj.get('n_renda_nao_informada', 0) != n:
            # Código inválido tem contador separado, mas resultados enviados são zero.
            if (obj.get('n_renda_declarada',0) + obj.get('n_renda_nao_informada',0) +
                    obj.get('n_codigo_renda_invalido',0)) != n:
                erros.append('Declarada + ausente + inválida não fecha com população.')
    for r in categorias:
        count = int(r.get('n_redacoes', 0))
        for campo in ('media', 'mediana', 'q1', 'q3', 'desvio_padrao'):
            x = r.get(campo)
            if count > 0 and (not isinstance(x, (int, float)) or not (0 <= x <= 1000)):
                erros.append(f'{r.get("codigo_renda")}: {campo} fora de 0–1000.')
        if count > 0 and r.get('q1') is not None and r.get('q3') is not None:
            if r['q1'] > r['q3']:
                erros.append(f'{r.get("codigo_renda")}: quartis invertidos.')
    return erros


def linhas_renda(obj: dict) -> list[dict]:
    """Tabela ordenada; mantém falta de resposta mas não mistura com renda zero."""
    rows = []
    for r in obj.get('categories', []):
        n = int(r.get('n_redacoes', 0))
        rows.append({
            'faixa': str(r.get('codigo_renda', '')),
            'descricao': str(r.get('descricao_faixa', '')),
            'n': n,
            'media': r.get('media'),
            'mediana': r.get('mediana'),
            'q1': r.get('q1'), 'q3': r.get('q3'),
            'iqr': r.get('iqr'),
            'desvio_padrao': r.get('desvio_padrao'),
            'percentual': r.get('percentual_total_validas'),
            'n_pequeno': n < 30,
        })
    return rows


def serie_renda(dashboards: Mapping[int, dict], uf: str = 'BR') -> list[dict]:
    """Série somente das edições com cruzamento observável.

    Letras A..Q são ordenadas dentro de cada edição, não grupos monetários de
    limites constantes ao longo dos anos. Não agrega medianas nem quartis.
    """
    out = []
    for ano, dashboard in sorted(dashboards.items()):
        ind = bloco(dashboard, 41)
        if not ind or ind.get('status') not in ('draft','ok'):
            continue
        obj = recorte(dashboard, 41, uf)
        if validar_renda(obj):
            continue
        cat = {r['codigo_renda']: r for r in obj['categories']}
        if not all(k in cat for k in ('A','Q')):
            continue
        a, q = cat['A'], cat['Q']
        if a.get('media') is None or q.get('media') is None:
            continue
        out.append({
            'ano': int(ano), 'n': obj['n_redacoes_validas'],
            'faixa_a_media': a['media'], 'faixa_q_media': q['media'],
            'diferenca_q_a': round(q['media'] - a['media'], 4),
            'a_descricao': a.get('descricao_faixa'),
            'q_descricao': q.get('descricao_faixa'),
        })
    return out


def serie_metrica(dashboards: Mapping[int, dict], indicador: int, campo: str, uf: str) -> list[dict]:
    """Série anual de uma estatística preservando o denominador de cada indicador."""
    rows = []
    for ano, d in sorted(dashboards.items()):
        r = recorte(d, indicador, uf)
        if r and isinstance(r.get(campo), (int, float)):
            rows.append({'Ano': str(ano), 'Valor': r[campo]})
    return rows
