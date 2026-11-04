# -*- coding: utf-8 -*-
"""Interpretações pedagógicas DETERMINÍSTICAS de indicadores ENEM (dados agregados).

Sem API, IA generativa, microdados ou escrita em resultados. Textos gerados com
regras por indicador; nenhuma afirmação numérica é produzida sem fonte verificável.
"""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

V2 = frozenset({55, 56, 57, 58, 59, 68})
# Chaves C1/C2/C3 são códigos internos dos dados, não rótulos públicos.
NOMES_PERFIS = {
    'C1': 'perfil material M1 (menor disponibilidade relativa de bens domésticos)',
    'C2': 'perfil material M2 (maior disponibilidade relativa de bens domésticos)',
    'C3': 'perfil material M3 (restrições materiais mais acentuadas)',
}
COMP = {f'C{i}': f'competência {i}' for i in range(1, 6)}
FOCO_DIDATICO = {
    'C1': 'uso da modalidade escrita formal da língua portuguesa',
    'C2': 'compreensão do tema e mobilização de repertório',
    'C3': 'seleção e organização de argumentos',
    'C4': 'coesão e articulação linguística das ideias',
    'C5': 'elaboração da proposta de intervenção',
}

# Apenas métricas e unidades com significado verificado. Não inferir a unidade
# de uma coluna arbitrária como 'n', 'percentual' ou 'valor'.
SERIES_CONHECIDAS = {
    2: ('media', 'nota média de redação', 'pontos', 'n_validas'),
    20: ('media', 'diferença absoluta média entre duas avaliações', 'pontos', 'n_avaliacoes_pareadas'),
    24: ('percentual_com_av3', 'proporção com registro de terceira avaliação', '%', 'n_pop_all'),
    25: ('percentual_com_av4', 'proporção com registro de banca (AV4)', '%', 'n_pop_all'),
    30: ('percentual_high_sobre_validas', 'proporção de redações com 900 pontos ou mais', '%', 'n_validas'),
}

PEDAGOGIA = {
    'overview': (
        'Para uma leitura pedagógica, combine essa medida com a distribuição das notas, a mediana e o tamanho da população. Uma média isolada pode esconder diferenças importantes entre os participantes.',
        'Uma estatística agregada descreve o grupo observado; não resume a trajetória de cada estudante.'),
    'competencies': (
        'Relacione o resultado aos critérios de correção da redação e observe quais competências concentram maior dificuldade relativa. Isso pode orientar discussões sobre práticas de leitura, argumentação e revisão textual, sem diagnosticar alunos individualmente.',
        'As cinco competências são dimensões da rubrica; correlação e agrupamentos não comprovam que uma habilidade provoque outra.'),
    'evaluators': (
        'Use o indicador para discutir a consistência da correção e os procedimentos de avaliação. Divergência entre notas é uma informação sobre o processo, não uma prova automática de erro ou injustiça.',
        'Diferenças entre avaliadores não demonstram, isoladamente, favorecimento, viés ou qualidade individual de uma correção.'),
    'high_performance': (
        'Observe quais padrões aparecem nas redações com notas elevadas e em quais competências ocorrem descontos. Frequência de um desconto e quantidade de pontos perdidos são medidas distintas.',
        'O recorte contempla redações de alto desempenho, não representa necessariamente todos os participantes; grupos pequenos merecem cautela.'),
    'socioeconomic': (
        'As diferenças podem suscitar reflexões sobre condições de estudo, acesso a recursos e oportunidades educacionais. Evite interpretar um perfil estatístico como capacidade ou destino individual.',
        'As relações são descritivas e não causais. Versões do questionário, recortes amostrais e ausência de respostas afetam a comparabilidade.'),
    'ml': (
        'Leia componentes e grupos como ferramentas de síntese: eles ajudam a identificar padrões, mas não substituem a análise das variáveis que contribuíram para cada resultado.',
        'PCA, MCA e clustering são métodos exploratórios; os agrupamentos não são categorias naturais nem equivalem a classes sociais.'),
    'temporal': (
        'Compare edições usando a mesma definição de população e de indicador. Ao interpretar uma mudança, considere que a composição de participantes pode variar de um ano para outro.',
        'Uma série de edições não acompanha necessariamente os mesmos estudantes; variação observada não significa evolução individual nem causa identificada.'),
    'methodology': (
        'Este resultado ajuda a verificar se as bases, os recortes e as regras de cálculo sustentam as comparações. Antes de discutir desempenho, confira cobertura, junções, valores ausentes e versões das fontes.',
        'Qualidade e proveniência são condições para interpretar dados, não indicadores de aprendizagem dos participantes.'),
}


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def _fmt(value: float, digits: int = 1) -> str:
    return f'{value:,.{digits}f}'.replace(',', '#').replace('.', ',').replace('#', '.')


def _delta(value: float, digits: int = 1) -> str:
    return ('+' if value > 0 else '') + _fmt(value, digits)


def _year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (ValueError, TypeError):
        return None
    return n if 2019 <= n <= 2025 else None


def _rows(doc: dict, year: int | None) -> list[dict]:
    raw = doc.get('results', [])
    if not isinstance(raw, list):
        return []
    bad = {'nao_aplicavel', 'erro', 'suprimido', 'suppressed', 'indisponivel'}
    return [r for r in raw if isinstance(r, dict)
            and str(r.get('status', '')).lower() not in bad
            and (year is None or _year(r.get('ano')) == year)]


def _size_ok(row: dict, column: str) -> bool:
    # Quando n existe, nunca narrar números de células com 1..29 unidades.
    v = _num(row.get(column))
    return v is not None and v >= 30


def _result(achado: str, orientacao: str, ressalva: str, recorte: str = '') -> dict:
    return {'texto': achado, 'pedagogia': orientacao, 'nota': ressalva, 'recorte': recorte}


def _indisponivel(ano: int | None, uf: str) -> dict:
    tema = f'na edição {ano}' if ano else 'no período disponível'
    if uf != 'BR':
        return _result('A fonte de perfis V2 contém somente dados nacionais; não há resultados separados por UF.',
                       'Selecione Brasil para consultar o indicador sem atribuir valores nacionais ao estado escolhido.',
                       'Não é correto apresentar uma média nacional como se representasse uma UF.', 'Recorte estadual indisponível')
    return _result(f'Não encontrei registros comparáveis {tema} para produzir uma conclusão numérica segura.',
                   'Confira se o período escolhido apresenta a população e a métrica previstas no catálogo.',
                   'Em 2025 não há vínculo público validado entre os perfis socioeconômicos e as notas de redação; dado ausente não significa zero.', 'Sem comparação válida')


def _pair_by_year(lines: list[dict], year: int, measure: str, nkey: str) -> dict[str, float]:
    ret = {}
    for r in lines:
        k = r.get('cluster')
        v = _num(r.get(measure))
        if _year(r.get('ano')) == year and k in NOMES_PERFIS and v is not None and _size_ok(r, nkey):
            ret[k] = v
    return ret


def _endpoints(groups: dict[int, dict]) -> tuple[int, int] | None:
    years = sorted(y for y, values in groups.items() if len(values) >= 2)
    return (years[0], years[-1]) if len(years) >= 2 else None


def _text_measure(a: float, b: float, unidade: str) -> str:
    delta = b-a
    label = 'ponto percentual' if unidade == '%' else 'ponto'
    label += 's' if abs(delta) != 1 else ''
    return f'{_delta(delta, 1)} {label}'


def _resumo_55_57_59(numero: int, doc: dict, ano: int | None) -> dict:
    info = {
        55: ('media','n','nota média de redação','pontos',
             'Uma diferença de médias sugere desigualdade de resultados entre perfis materiais na amostra, mas não descreve cada estudante.'),
        57: ('percentual_high','n_notas_validas','participação de redações com 900 pontos ou mais','%',
             'Compare proporções dentro de cada perfil, em vez de comparar apenas quantidades absolutas de redações.'),
        59: ('media_diferenca_absoluta','n_pareadas','intensidade média da divergência entre as duas avaliações','pontos',
             'Uma diferença absoluta maior não informa qual avaliador atribuiu a nota mais alta, nem indica a causa da divergência.'),
    }[numero]
    col, ncol, nome, unidade, orientacao = info
    lines = _rows(doc, ano)
    years = sorted({_year(r.get('ano')) for r in lines if _year(r.get('ano'))})
    by = {y: _pair_by_year(lines,y,col,ncol) for y in years}
    if ano is not None:
        vals = by.get(ano, {})
        if len(vals) < 2:
            return _indisponivel(ano,'BR')
        high, low = max(vals,key=vals.get), min(vals,key=vals.get)
        gap = vals[high]-vals[low]
        unit_word = '%' if unidade=='%' else ' pontos'
        achado = (f'Na edição de {ano}, {NOMES_PERFIS[high]} registrou a maior {nome} '
                  f'({_fmt(vals[high], 2)}{unit_word}), enquanto {NOMES_PERFIS[low]} ficou em '
                  f'{_fmt(vals[low], 2)}{unit_word}. A distância foi de {_fmt(gap, 2)} '
                  f'{"pontos percentuais" if unidade=="%" else "pontos"}.')
        return _result(achado, orientacao,
                       'Comparação descritiva de participantes da amostra com registros válidos; não comprova causalidade, viés de avaliação ou representatividade populacional.',
                       f'ENEM {ano} · Brasil · amostra V2')
    ends = _endpoints(by)
    if not ends:
        return _indisponivel(None,'BR')
    first,last=ends
    end=by[last]
    high,low=max(end,key=end.get),min(end,key=end.get)
    if high not in by[first] or low not in by[first]:
        return _indisponivel(None,'BR')
    g0=by[first][high]-by[first][low]
    g1=end[high]-end[low]
    unit_word='pontos percentuais' if unidade=='%' else 'pontos'
    achado=(f'Observando as edições de {first} a {last}, {NOMES_PERFIS[high]} e '
            f'{NOMES_PERFIS[low]} apresentam diferenças na {nome}. '
            f'Entre esses mesmos perfis, a distância era de {_fmt(g0, 2)} {unit_word} em {first} '
            f'e de {_fmt(g1, 2)} {unit_word} em {last} '
            f'(mudança de {_delta(g1-g0, 2)} {unit_word}). '
            'Essa comparação usa os extremos da série, não afirma que a mudança foi contínua nos anos intermediários.')
    return _result(achado, orientacao,
                   'As edições não constituem acompanhamento longitudinal dos mesmos estudantes; a associação com perfis materiais não prova causalidade.',
                   f'Série {first}–{last} · Brasil · amostra V2')


def _competence_groups(lines: list[dict], year: int) -> dict[str, dict[str, float]]:
    groups = defaultdict(dict)
    for r in lines:
        comp, cluster = r.get('competencia'), r.get('cluster')
        v=_num(r.get('media'))
        if _year(r.get('ano')) == year and comp in COMP and cluster in NOMES_PERFIS and v is not None and _size_ok(r,'n'):
            groups[comp][cluster] = v
    return dict(groups)


def _resumo_56(doc: dict, ano: int | None) -> dict:
    lines = _rows(doc, ano)
    years = sorted({_year(r.get('ano')) for r in lines if _year(r.get('ano'))})
    groups={y:_competence_groups(lines,y) for y in years}
    years=[y for y in years if any(len(g)>=2 for g in groups[y].values())]
    if not years:return _indisponivel(ano,'BR')
    chosen=ano if ano is not None else years[-1]
    diffs=[(max(g.values())-min(g.values()),key,g) for key,g in groups[chosen].items() if len(g)>=2]
    if not diffs:return _indisponivel(ano,'BR')
    gap,comp,group=max(diffs,key=lambda x:x[0])
    hi,lo=max(group,key=group.get),min(group,key=group.get)
    achado=(f'Na edição de {chosen}, a maior distância entre os perfis ocorreu na {COMP[comp]}: '
            f'{NOMES_PERFIS[hi]} obteve {_fmt(group[hi],1)} pontos, enquanto '
            f'{NOMES_PERFIS[lo]} obteve {_fmt(group[lo],1)} pontos '
            f'(diferença de {_fmt(gap,1)} pontos na escala de 0 a 200).')
    if ano is None and len(years)>=2:
        first=years[0]
        base=groups[first].get(comp,{})
        if hi in base and lo in base:
            old_gap=base[hi]-base[lo]
            achado+=(f' Para os mesmos perfis nessa competência, a distância era '
                     f'{_fmt(old_gap,1)} pontos em {first} e {_fmt(gap,1)} em {chosen}. '
                     'Isso descreve os extremos, não uma progressão regular.')
    return _result(achado,
                   f'A {COMP[comp]} trata de {FOCO_DIDATICO[comp]}. Essa leitura pode inspirar atividades de revisão e produção textual, mas a diferença média não permite diagnosticar a dificuldade individual de quem integra cada perfil.',
                   'Amostra V2, comparação descritiva, sem vínculo causal entre bens domésticos e domínio de uma competência. Os perfis M1–M3 não são níveis de competência; C1–C5 identificam os critérios oficiais de correção da redação.',
                   f'{"Série " +str(years[0])+"–"+str(years[-1]) if ano is None else "ENEM "+str(ano)} · Brasil')


def _resumo_58(doc: dict, ano: int | None) -> dict:
    lines = _rows(doc, ano)
    years=sorted({_year(r.get('ano')) for r in lines if _year(r.get('ano'))})
    if not years:return _indisponivel(ano,'BR')
    # Proteção conservadora: não produzir uma taxa composta que possa revelar
    # células pequenas ou seus complementos. Nenhuma célula é ocultada no JSON;
    # este módulo apenas opta por não resumi-la numericamente.
    if any(0 < (_num(r.get('n_com_competencia_valida')) or 0) < 30 for r in lines):
        return _result('Há resultados sobre a frequência de descontos nas cinco competências entre redações com notas de 900 a 980, mas alguns recortes têm tamanho pequeno. Por segurança, a interpretação automática não destaca percentuais desses grupos.',
                       'Na leitura pedagógica, compare primeiro **em quais competências** os descontos aparecem e diferencie a frequência de ocorrência da quantidade de pontos perdidos. Evite conclusões sobre perfis individuais.',
                       'A divulgação exige revisão contextual de células pequenas e complementos em outras tabelas. Não é seguro inferir que a maior frequência representa a maior perda de pontos.',
                       f'{"Série " + str(years[0])+"–"+str(years[-1]) if ano is None else "ENEM "+str(ano)} · revisão interna')
    grouped=defaultdict(lambda:[0.,0.])
    chosen=ano if ano is not None else years[-1]
    for r in lines:
        if _year(r.get('ano')) != chosen or r.get('competencia') not in COMP:
            continue
        n=_num(r.get('n_com_competencia_valida'))
        d=_num(r.get('n_com_desconto'))
        if n is None or d is None or n < 30 or not 0<=d<=n:
            continue
        grouped[r['competencia']][0]+=n
        grouped[r['competencia']][1]+=d
    vals={k:100*v[1]/v[0] for k,v in grouped.items() if v[0]>=30}
    if not vals:return _indisponivel(ano,'BR')
    highest=max(vals,key=vals.get)
    achado=f'Em {chosen}, a {COMP[highest]} apresentou a maior frequência agregada de desconto entre os perfis reunidos ({_fmt(vals[highest],1)}%).'
    if ano is None and len(years)>=2:
        first=years[0]
        p=[r for r in lines if _year(r.get('ano'))==first and r.get('competencia')==highest]
        den=sum(_num(r.get('n_com_competencia_valida')) or 0 for r in p)
        d=sum(_num(r.get('n_com_desconto')) or 0 for r in p)
        if den>=30:achado+=f' Em {first}, a frequência correspondente era {_fmt(100*d/den,1)}%.'
    return _result(achado,
                   'Para planejar atividades, pergunte que características textuais são verificadas nessa competência. Frequência do desconto não equivale à intensidade da perda.',
                   'Estatísticas da amostra de notas 900–980; interpretações dependem de auditoria de privacidade cruzada antes de qualquer publicação.',
                   f'{"Série "+str(years[0])+"–"+str(years[-1]) if ano is None else "ENEM "+str(ano)} · Brasil')


def _resumo_68(doc: dict, ano: int | None) -> dict:
    lines=_rows(doc,ano)
    by=defaultdict(dict)
    for r in lines:
        yr=_year(r.get('ano'))
        cl=r.get('cluster_referencia')
        value=_num(r.get('percentual_amostra'))
        if yr and cl in NOMES_PERFIS and value is not None and _size_ok(r,'n_amostra'):
            by[yr][cl]=value
    if ano is not None:
        vals=by.get(ano,{})
        if len(vals)<2:return _indisponivel(ano,'BR')
        largest=max(vals,key=vals.get)
        achado=(f'Em {ano}, {NOMES_PERFIS[largest]} foi o mais frequente na amostra, '
                f'representando {_fmt(vals[largest],2)}% dos registros classificados. '
                'Os percentuais descrevem a composição da amostra, não o rendimento escolar.')
    else:
        ends=_endpoints(by)
        if not ends:return _indisponivel(None,'BR')
        first,last=ends
        comps=[(abs(by[last][cl]-by[first][cl]),cl) for cl in NOMES_PERFIS
               if cl in by[first] and cl in by[last]]
        if not comps:return _indisponivel(None,'BR')
        _,cl=max(comps)
        a,b=by[first][cl],by[last][cl]
        achado=(f'Entre {first} e {last}, a maior alteração entre as participações dos perfis '
                f'na amostra ocorreu em {NOMES_PERFIS[cl]}: de {_fmt(a,2)}% para '
                f'{_fmt(b,2)}% ({_delta(b-a,2)} pontos percentuais). '
                'Esse é um contraste entre os anos extremos, não uma tendência necessariamente contínua.')
    return _result(achado,
                   'Essas diferenças ajudam a discutir a composição material dos grupos de participantes, e não classificam indivíduos em níveis de competência ou de mérito.',
                   'Perfis definidos por referência fixa V2 em amostra, não população inteira. Em 2025 não há ligação validada com notas; mudanças na composição não comprovam mudança social nacional.',
                   f'{"Série " + str(min(by))+"–"+str(max(by)) if ano is None else "ENEM "+str(ano)} · Brasil')


def _resumo_v2(numero: int, doc: dict, ano: int | None, uf: str) -> dict:
    if uf != 'BR':return _indisponivel(ano,uf)
    if numero==68:return _resumo_68(doc,ano)
    if numero==56:return _resumo_56(doc,ano)
    if numero==58:return _resumo_58(doc,ano)
    return _resumo_55_57_59(numero,doc,ano)


def _national_row(row: dict, uf: str) -> dict | None:
    if uf == 'BR':
        found=row.get('brasil')
        return found if isinstance(found,dict) else None
    opts=row.get('ufs')
    if isinstance(opts,list):
        return next((r for r in opts if isinstance(r,dict) and r.get('uf')==uf),None)
    return None


def _known_series(numero: int, doc: dict, ano: int | None, uf: str) -> dict | None:
    if numero not in SERIES_CONHECIDAS:return None
    field, label, unit, nfield=SERIES_CONHECIDAS[numero]
    entries=doc.get('years')
    if not isinstance(entries,list):return None
    by={}
    for r in entries:
        if not isinstance(r,dict):continue
        yr=_year(r.get('ano'))
        region=_national_row(r,uf)
        if yr and region:
            v=_num(region.get(field))
            n=_num(region.get(nfield))
            # Unavailable or suppressed counts are never silently zeros.
            if v is not None and n is not None and n>=30 and str(region.get('status_publicacao','ok')) not in ('suprimido','suppressed'):
                by[yr]=v
    if ano is not None:
        if ano not in by:
            return _result(f'Não há uma medida validada deste indicador para {ano} no recorte {uf}.',
                           'Experimente conferir os filtros e o período declarado no catálogo.',
                           'Dado indisponível não equivale a resultado zero.', f'{ano} · {uf}')
        v=by[ano]
        value=f'{_fmt(v,2)}%' if unit=='%' else f'{_fmt(v,2)} {unit}'
        return _result(f'Na edição de {ano}, a {label} foi de {value} no recorte {uf}. '
                       'Esse número representa o grupo definido para o indicador, não uma avaliação individual.',
                       PEDAGOGIA[('overview' if numero==2 else 'evaluators' if numero in (20,24,25) else 'high_performance')][0],
                       PEDAGOGIA[('overview' if numero==2 else 'evaluators' if numero in (20,24,25) else 'high_performance')][1],
                       f'ENEM {ano} · {uf} · fonte anual')
    years=sorted(by)
    if len(years)<2:
        return None
    first,last=years[0],years[-1]
    suffix='pontos percentuais' if unit=='%' else 'pontos'
    achado=(f'De {first} a {last}, a {label} no recorte {uf} passou de '
            f'{_fmt(by[first],2)}{("%" if unit=="%" else " pontos")} para '
            f'{_fmt(by[last],2)}{("%" if unit=="%" else " pontos")} '
            f'(diferença de {_delta(by[last]-by[first],2)} {suffix}). '
            'Os valores intermediários devem ser consultados no gráfico: a variação entre os extremos não implica movimento linear.')
    page='overview' if numero==2 else 'evaluators' if numero in (20,24,25) else 'high_performance'
    return _result(achado,PEDAGOGIA[page][0],
                   PEDAGOGIA[page][1]+' Compare a população e a metodologia entre edições antes de interpretar a mudança.',
                   f'Série {first}–{last} · {uf} · fonte anual')


def _geral(numero: int, doc: dict, meta: dict, ano: int | None, uf: str, valor: Any) -> dict:
    known=_known_series(numero,doc,ano,uf)
    if known:return known
    page=str(meta.get('pagina','overview'))
    pedag, cuidado=PEDAGOGIA.get(page,PEDAGOGIA['methodology'])
    question=str(meta.get('pergunta') or meta.get('titulo') or 'a medida do indicador').strip()
    where=f'na edição de {ano}' if ano is not None else 'entre as edições disponíveis'
    intro=f'Este indicador permite investigar {question[0].lower()+question[1:] if question else "o resultado"}'
    if question.endswith('?'):intro=intro[:-1]
    intro+=f' {where}, considerando o recorte {uf}.'
    # KPI somente se ele foi fornecido pela visualização, e não é 'Todos os anos'.
    if ano is not None and isinstance(valor,(int,float)) and not isinstance(valor,bool):
        v=_num(valor)
        if v is not None:
            intro+=f' O valor exibido é {_fmt(v,2)} (consulte a unidade no contrato).'
    if ano is None:
        intro+=' Compare edições apenas quando a fonte definir a mesma medida e uma população compatível; este módulo não calculou uma diferença numérica sem série inequívoca.'
    return _result(intro,pedag,cuidado+' Ausência de dado não é zero; confira sempre a fonte e os filtros.',
                   f'{"Todos os anos" if ano is None else "ENEM "+str(ano)} · {uf} · leitura orientada')


def resumir_indicador(numero: int, doc: dict, meta: dict, ano: int | None, uf: str,
                      valor_visualizado: Any = None) -> dict:
    """Retorna evidência, leitura e ressalva. Sem conclusões além dos dados."""
    if not isinstance(doc,dict):doc={}
    if not isinstance(meta,dict):meta={}
    if numero in V2:return _resumo_v2(numero,doc,ano,uf)
    return _geral(numero,doc,meta,ano,uf,valor_visualizado)


def mostrar_interpretacao(st, numero: int, doc: dict, meta: dict, ano: int | None,
                          uf: str, valor_visualizado: Any = None) -> None:
    resumo=resumir_indicador(numero,doc,meta,ano,uf,valor_visualizado)
    with st.expander('Entenda este resultado · leitura pedagógica automática', expanded=(numero in V2)):
        if resumo.get('recorte'):st.caption(resumo['recorte'])
        st.markdown('**O que os dados mostram**')
        st.write(resumo['texto'])
        st.markdown('**Como interpretar pedagogicamente**')
        st.write(resumo['pedagogia'])
        st.markdown('**Cuidados e limitações**')
        st.caption(resumo['nota'])
        if ano is None and numero in (56,58):
            st.caption('A interpretação considera a série histórica; o gráfico de competências pode mostrar uma edição detalhada selecionada à parte.')
        st.caption('Texto produzido por regras estatísticas a partir de JSONs agregados. Não é IA generativa, e resultados internos não estão automaticamente autorizados para publicação.')
