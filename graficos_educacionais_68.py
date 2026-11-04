# -*- coding: utf-8 -*-
"""Gráficos explicativos 001–005 e 007, somente a partir dos dashboards anuais.

Nenhuma reestimativa de médias/percentis; lê medidas já calculadas.
Não substitui os gráficos especializados de outros indicadores.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px

NUMEROS = frozenset({1,2,3,4,5,7})


def _numero(v):
    if isinstance(v, bool):return None
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):return None


def _inteiro(v):
    x=_numero(v)
    return int(x) if x is not None and x.is_integer() and x>=0 else None


def _pt(v, digits=0):
    return f'{v:,.{digits}f}'.replace(',','X').replace('.',',').replace('X','.')


def _fonte_ano(raiz: Path, ano: int):
    filename=f'dashboard_enem_{ano}.json'
    for parent in (raiz/'outputs'/'json',raiz/'outputs',raiz):
        candidate=parent/filename
        if candidate.is_file():
            try:
                d=json.loads(candidate.read_text(encoding='utf-8-sig'))
                if (d.get('meta',{}).get('year') == ano and
                        d.get('meta',{}).get('data_status') in ('draft','internal','approved','published') and
                        isinstance(d.get('pages',{}).get('overview'),dict)):
                    return d
            except (OSError,ValueError,TypeError):pass
    return None


def _recorte(d: dict, numero: int, uf: str) -> dict | None:
    key='essay_status' if numero==7 else f'ind{numero:03d}'
    obj=d['pages']['overview'].get(key)
    if not isinstance(obj,dict):return None
    if uf=='BR':return obj
    return next((v for v in obj.get('by_uf',[]) if isinstance(v,dict) and v.get('uf')==uf),None)


def dados_visuais(raiz: Path, numero: int, ano: int | None, uf: str) -> list[dict]:
    """Extrai valores explícitos; nunca cria uma estimativa a partir de percentis ou médias."""
    if numero not in NUMEROS:return []
    anos=[ano] if ano is not None else list(range(2019,2026))
    out=[]
    for yr in anos:
        if yr is None:continue
        d=_fonte_ano(raiz,int(yr))
        if d is None:continue
        v=_recorte(d,numero,uf)
        if not v:continue
        if numero==1:
            if uf=='BR':
                total=_inteiro(v.get('denominator'))
                validas=_inteiro(d['pages']['overview'].get('kpis',{}).get('valid_essays'))
            else:
                total=_inteiro(v.get('total_registros'))
                validas=_inteiro(v.get('redacoes_validas'))
            if total is None or validas is None or total<30 or not 0<=validas<=total:continue
            out.append({'ano':int(yr),'validas':validas,'total':total,
                        'demais':total-validas,'pct':100*validas/total})
        elif numero in (2,3,4):
            k={2:'mean_score',3:'median_score',4:'std_score'}[numero]
            n=_inteiro(v.get('n')); med=_numero(v.get(k))
            if n is not None and n>=30 and med is not None and 0<=med<=1000:
                out.append({'ano':int(yr),'valor':med,'n':n})
        elif numero==5:
            n=_inteiro(v.get('n')); pp=v.get('percentiles')
            if n is None or n<30 or not isinstance(pp,dict):continue
            vals={k:_numero(pp.get(k)) for k in ('p25','p50','p75','p90','p95')}
            if any(x is None or not 0<=x<=1000 for x in vals.values()):continue
            if any(vals[a]>vals[b] for a,b in zip(('p25','p50','p75','p90'),('p50','p75','p90','p95'))):continue
            out.append({'ano':int(yr),'n':n,**vals})
        elif numero==7:
            if any(r.get('requer_revisao_privacidade') is True for r in v.get('categories',[]) if isinstance(r,dict)):
                # Não mostrar distribuição parcialmente suprimível/reconstruível.
                continue
            cats=[]
            for r in v.get('categories',[]):
                if not isinstance(r,dict):continue
                q=_inteiro(r.get('quantidade'))
                if q is None or (0<q<30):break
                cats.append({'status':str(r.get('rotulo','Sem legenda')),'n':q})
            else:
                if cats:out.append({'ano':int(yr),'categorias':cats})
    return out


def resumo_expresso(raiz: Path, numero: int, ano: int | None, uf: str) -> dict | None:
    dados=dados_visuais(raiz,numero,ano,uf)
    if not dados:return None
    a,b=dados[0],dados[-1]
    escopo='Brasil' if uf=='BR' else f'UF {uf}'
    if numero==1:
        if ano is not None:
            texto=(f'Em {a["ano"]}, {escopo} teve {_pt(a["validas"])} redações válidas '
                   f'entre {_pt(a["total"])} registros da base ({_pt(a["pct"],1)}%). '
                   f'Os outros {_pt(a["demais"])} registros não atenderam a todos os critérios deste indicador.')
        elif len(dados)>=2:
            texto=(f'Nas edições disponíveis de {a["ano"]} a {b["ano"]}, a proporção de registros com redação válida '
                   f'passou de {_pt(a["pct"],1)}% para {_pt(b["pct"],1)}% '
                   f'(diferença de {_pt(b["pct"]-a["pct"],1)} pontos percentuais). '
                   'A quantidade total de registros também varia entre edições; observe cada ano no gráfico.')
        else:return None
        return {'texto':texto,'nota':'O total é o número de registros da base analisada, não o total de todos os inscritos. Anos diferentes são conjuntos distintos de participantes.'}
    if numero in (2,3,4):
        label={2:'média',3:'mediana',4:'dispersão das notas (desvio-padrão)'}[numero]
        if ano is not None:
            texto=f'Em {ano}, o valor da {label} foi de {_pt(a["valor"],1)} pontos entre {_pt(a["n"])} redações válidas no recorte {escopo}.'
        elif len(dados)>=2:
            texto=(f'Entre {a["ano"]} e {b["ano"]}, o valor da {label} passou de {_pt(a["valor"],1)} para '
                   f'{_pt(b["valor"],1)} pontos. Confira os anos intermediários no gráfico; a evolução não precisa ter sido contínua.')
        else:return None
        return {'texto':texto,'nota':'Comparações entre anos não acompanham as mesmas pessoas. Para interpretar média ou mediana, observe também a dispersão.'}
    if numero==5:
        if ano is not None:
            texto=(f'Em {ano}, a nota de referência para o P25 foi {_pt(a["p25"])}; '
                   f'para o P50 (mediana), {_pt(a["p50"])}; para o P75, {_pt(a["p75"])}; '
                   f'para o P90, {_pt(a["p90"])}; e para o P95, {_pt(a["p95"])} pontos.')
        elif len(dados)>=2:
            texto=(f'Na primeira edição disponível ({a["ano"]}), a mediana (P50) era {_pt(a["p50"])} pontos; '
                   f'na última ({b["ano"]}), {_pt(b["p50"])}. Já o P90 passou de {_pt(a["p90"])} para '
                   f'{_pt(b["p90"])} pontos. A evolução dos demais percentis aparece nas linhas do gráfico.')
        else:return None
        return {'texto':texto,'nota':'Percentis são valores de corte calculados sobre redações válidas de cada edição. Não se deve fazer a média dos percentis anuais para criar um percentil do período inteiro.'}
    if numero==7 and ano is not None:
        items=a['categorias']
        if not items:return None
        maior=max(items,key=lambda r:r['n'])
        return {'texto':(f'Em {ano}, a situação mais frequente entre as categorias exibidas foi '
                         f'“{maior["status"]}”, com {_pt(maior["n"])} registros no recorte {escopo}.'),
                'nota':'A situação é um código do resultado da redação. Isso não informa por que cada participante recebeu essa classificação.'}
    return None


def mostrar_grafico_didatico(st, raiz: Path, numero: int, ano: int | None, uf: str) -> bool:
    """True se uma visualização segura substituiu a genérica do catálogo."""
    dados=dados_visuais(raiz,numero,ano,uf)
    if not dados:return False
    df=pd.DataFrame(dados)
    if numero==1:
        if ano is None and len(df)>=2:
            st.markdown('**Participação de redações válidas em cada edição**')
            fig=px.bar(df,x='ano',y='pct',text='pct',labels={'ano':'Edição','pct':'Redações válidas (%)'})
            fig.update_traces(texttemplate='%{text:.1f}%',textposition='outside')
            fig.update_yaxes(range=[0,110])
            st.plotly_chart(fig,use_container_width=True)
            st.caption('A altura das barras é uma porcentagem do total de registros de **cada ano**. Não mostra a porcentagem de todos os inscritos no ENEM.')
            st.dataframe(pd.DataFrame([{'Edição':r['ano'],'Válidas':r['validas'],'Total de registros':r['total'],'Válidas (%)':round(r['pct'],2)} for r in dados]),hide_index=True,use_container_width=True)
        else:
            r=dados[0]
            st.metric('Redações válidas',_pt(r['validas']))
            st.metric('Percentual entre os registros da base',f'{_pt(r["pct"],1)}%')
            fig=px.bar(x=['Redações válidas','Demais registros'],y=[r['validas'],r['demais']],
                       labels={'x':'Situação conforme o critério analítico','y':'Quantidade de registros'})
            fig.update_traces(texttemplate='%{y:,.0f}',textposition='outside')
            st.plotly_chart(fig,use_container_width=True)
            st.caption('“Demais registros” é uma contagem residual, não sinônimo de redações com erros nem necessariamente de textos escritos.')
        return True
    if numero in (2,3,4):
        label={2:'Nota média',3:'Nota mediana',4:'Dispersão das notas (desvio-padrão)'}[numero]
        if ano is None and len(df)>=2:
            fig=px.line(df,x='ano',y='valor',markers=True,labels={'ano':'Edição','valor':f'{label} (pontos)'})
            st.plotly_chart(fig,use_container_width=True)
            st.caption('Os pontos representam edições independentes; a linha ajuda a acompanhar valores, não as mesmas pessoas.')
        else:
            r=dados[0]
            st.metric(label,f'{_pt(r["valor"],1)} pontos')
            fig=px.bar(x=[str(r['ano'])],y=[r['valor']],labels={'x':'Edição','y':f'{label} (pontos)'})
            if numero in (2,3):fig.update_yaxes(range=[0,1000])
            st.plotly_chart(fig,use_container_width=True)
        return True
    if numero==5:
        keys=['p25','p50','p75','p90','p95']
        if ano is None and len(df)>=2:
            dfl=df.melt(id_vars='ano',value_vars=keys,var_name='Percentil',value_name='Nota de referência')
            dfl['Percentil']=dfl['Percentil'].str.upper()
            fig=px.line(dfl,x='ano',y='Nota de referência',color='Percentil',markers=True,
                        labels={'ano':'Edição'})
            fig.update_yaxes(range=[0,1000])
            st.plotly_chart(fig,use_container_width=True)
            st.caption('Cada linha acompanha um **percentil**, não uma redação. Compare os mesmos percentis entre edições.')
        else:
            r=dados[0]
            dfp=pd.DataFrame({'Percentil':[k.upper() for k in keys],'Nota (pontos)':[r[k] for k in keys]})
            fig=px.bar(dfp,x='Percentil',y='Nota (pontos)',text='Nota (pontos)')
            fig.update_traces(textposition='outside')
            fig.update_yaxes(range=[0,1050])
            st.plotly_chart(fig,use_container_width=True)
        st.caption('P25: ~25% das notas até esse valor; P50: metade; P75: ~75%; P90: ~90%; P95: ~95%. Notas iguais podem alterar a proporção exata.')
        return True
    if numero==7:
        if ano is None:
            st.info('Para ver cada situação da redação sem misturar edições, selecione um ano no filtro.')
            return False
        r=dados[0]
        tabela=pd.DataFrame(r['categorias']).sort_values('n',ascending=False)
        fig=px.bar(tabela,x='status',y='n',labels={'status':'Situação registrada','n':'Quantidade de registros'})
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig,use_container_width=True)
        st.caption('Categorias da edição selecionada. Gráficos só são mostrados quando não há marcação de revisão por células pequenas nesse recorte.')
        return True
    return False
