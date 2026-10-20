"""Camada de dados sem Streamlit. Lê somente dashboards agregados IND-001..022.

O consolidado histórico usa o `period_total/period_by_uf` já calculado
pelos indicadores, nunca média de médias nem soma de grupos K-Means locais.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ANOS = tuple(range(2019, 2026))
UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO")
NOMES_UF = {"AC":"Acre", "AL":"Alagoas", "AM":"Amazonas", "AP":"Amapá", "BA":"Bahia", "CE":"Ceará", "DF":"Distrito Federal", "ES":"Espírito Santo", "GO":"Goiás", "MA":"Maranhão", "MG":"Minas Gerais", "MS":"Mato Grosso do Sul", "MT":"Mato Grosso", "PA":"Pará", "PB":"Paraíba", "PE":"Pernambuco", "PI":"Piauí", "PR":"Paraná", "RJ":"Rio de Janeiro", "RN":"Rio Grande do Norte", "RO":"Rondônia", "RR":"Roraima", "RS":"Rio Grande do Sul", "SC":"Santa Catarina", "SE":"Sergipe", "SP":"São Paulo", "TO":"Tocantins"}

# Fontes anuais do JSON cumulativo. Nunca lê microdados individuais.
PATHS = {
  1: ("overview", "ind001"), 2:("overview","ind002"), 3:("overview","ind003"),
  4:("overview","ind004"), 5:("overview","ind005"), 6:("overview","score_distribution"),
  7:("overview","essay_status"), 8:("overview","ind008"), 9:("competencies","ind009"),
  10:("competencies","ind010"), 11:("competencies","dispersion"),
  12:("competencies","level_distribution"), 13:("competencies","correlation"),
  14:("competencies","pca"), 15:("competencies","pca"),
  16:("competencies","pca","scatter"), 17:("competencies","clusters"),
  18:("competencies","clusters","sizes"), 19:("competencies","clusters","quality"),
  20:("evaluators","total_difference"), 21:("evaluators","by_competency"),
  22:("evaluators","official_discrepancy")
}

def localizar_dashboards(raiz: Path) -> dict[int, Path]:
    encontrados = {}
    for pasta in (raiz / 'outputs' / 'json', raiz / 'outputs', raiz):
        for p in pasta.glob('dashboard_enem_20[12][0-9].json'):
            try:
                ano = int(p.stem.rsplit('_', 1)[-1])
            except ValueError:
                continue
            if ano in ANOS and ano not in encontrados:
                encontrados[ano] = p
    return encontrados

def carregar_json(caminho: Path) -> dict:
    with caminho.open(encoding='utf-8-sig') as arq:
        doc = json.load(arq)
    if not isinstance(doc, dict) or not isinstance(doc.get('pages'), dict):
        raise ValueError(f'Dashboard inválido: {caminho.name}')
    # Consome exclusivamente campos agregados IND-001..022 de PATHS.
    return doc

def buscar_uf(lista: list | None, uf: str) -> dict | None:
    return next((x for x in (lista or []) if isinstance(x,dict) and x.get('uf') == uf), None)

def temporal(ref: dict, indicador: int) -> dict | None:
    t = ref.get('pages',{}).get('temporal',{})
    return t if indicador == 1 else t.get(f'ind{indicador:03d}')

def obter_recorte(ref: dict, ano_doc: dict | None, indicador: int, ano: int | None, uf: str) -> dict | None:
    """Retorna um único recorte publicado. Sem interpolação, sem agregação ad hoc."""
    if indicador not in PATHS or (uf != 'BR' and uf not in UFS) or (ano is not None and ano not in ANOS):
        return None
    t = temporal(ref, indicador)
    if ano is None or uf == 'BR':
        if not t: return None
        if ano is None:
            return t.get('period_total') if uf=='BR' else buscar_uf(t.get('period_by_uf'), uf)
        return next((x for x in t.get('national_by_year',[]) if x.get('year')==ano), None)
    # Para UF num ano concreto, só dashboard daquele ano. Nunca usar 2024 como se fosse outro ano.
    if not ano_doc or ano_doc.get('meta',{}).get('year') != ano:
        return None
    p = ano_doc.get('pages',{})
    for seg in PATHS[indicador]:
        if not isinstance(p,dict): return None
        p=p.get(seg)
    if not isinstance(p, dict):return None
    return buscar_uf(p.get('by_uf'), uf)

def serie_anual(ref: dict, arquivos: dict[int, Path], indicador: int, uf: str, carregar=carregar_json) -> list[dict]:
    if uf=='BR':
        t=temporal(ref, indicador)
        return list(t.get('national_by_year',[])) if t else []
    resultado=[]
    for ano in ANOS:
        if ano not in arquivos:continue
        d=carregar(arquivos[ano])
        valor=obter_recorte(ref,d,indicador,ano,uf)
        if valor:resultado.append({'year':ano,**valor})
    return resultado

def quantidade_segura(n: Any, limiar: int = 30) -> int | None:
    """Omite valores positivos abaixo do limiar, não altera zeros."""
    try:v=int(n)
    except (TypeError,ValueError):return None
    return v if v == 0 or v >= limiar else None

def agrupar_frequencias_niveis(levels: list[dict], limiar: int = 30) -> list[dict] | None:
    """Agrega níveis C1..C5 em faixas e mescla pequenas faixas adjacentes.
    A aplicação não publica níveis exatos nem células positivas de 1..29.
    A política de publicação definitiva requer revisão complementar externa.
    """
    if not isinstance(levels,list):return None
    limites = ((0,79),(80,119),(120,159),(160,200))
    faixas = []
    for ini,fim in limites:
        qtd=sum(int(x.get('count',0)) for x in levels if ini <= int(x.get('score',-1)) <= fim)
        faixas.append({'inicio':ini,'fim':fim,'quantidade':qtd})
    i=0
    while i < len(faixas):
        if 0 < faixas[i]['quantidade'] < limiar and len(faixas)>1:
            if i+1<len(faixas):
                faixas[i+1]['inicio']=faixas[i]['inicio']
                faixas[i+1]['quantidade']+=faixas[i]['quantidade']
                faixas.pop(i)
            else:
                faixas[i-1]['fim']=faixas[i]['fim']
                faixas[i-1]['quantidade']+=faixas[i]['quantidade']
                faixas.pop(i)
                i-=1
        else:i+=1
    if any(0<x['quantidade']<limiar for x in faixas):return None
    return [{**x,'faixa':f"{x['inicio']}–{x['fim']}"} for x in faixas]

def classes_redacao(categories: list[dict] | None):
    """Categoria oficial 1 vs demais em bloco (não exibe códigos raros)."""
    if not categories:return []
    valid=sum(int(c.get('quantidade',0)) for c in categories if str(c.get('codigo'))=='1')
    other=sum(int(c.get('quantidade',0)) for c in categories if str(c.get('codigo'))!='1')
    return [{'categoria':'Sem problemas','quantidade':valid},{'categoria':'Outras situações','quantidade':other}]


def obter_hexbin_ind016(ref: dict, ano_doc: dict | None, ano: int | None, uf: str) -> dict | None:
    """Recupera as células AGREGADAS do IND-016, sem misturar PCA de anos/UFs.

    O temporal.national_by_year é um RESUMO SEM points; para uma edição
    concreta são obrigatórios os points do dashboard daquela mesma edição.
    Para 'Todos os anos', usa-se o PCA histórico ajustado separadamente.
    """
    if uf != 'BR' and uf not in UFS:
        return None
    if ano is None:
        historico = ref.get('pages', {}).get('temporal', {}).get('ind016', {})
        return (historico.get('period_total') if uf == 'BR'
                else buscar_uf(historico.get('period_by_uf'), uf))

    if ano not in ANOS or not ano_doc or ano_doc.get('meta', {}).get('year') != ano:
        return None
    scatter = (ano_doc.get('pages', {}).get('competencies', {})
               .get('pca', {}).get('scatter', {}))
    if scatter.get('indicator_id') != 'IND-016' or scatter.get('type') != 'hexbin':
        return None
    return scatter.get('brasil') if uf == 'BR' else buscar_uf(scatter.get('by_uf'), uf)


def validar_hexbin_ind016(recorte: dict | None, limiar: int = 30) -> tuple[list[dict], str | None]:
    """Valida as informações agregadas antes de renderizar.

    Falha fechada diante de inconsistências: nunca transforma uma contagem
    pequena em ponto, nunca infere células omitidas e nunca usa microdados.
    """
    import math
    if not isinstance(recorte, dict):
        return [], 'Recorte IND-016 indisponível.'
    if recorte.get('sem_pontos_individuais') is not True:
        return [], 'O recorte não confirma agregação dos dados.'
    pts = recorte.get('points')
    if not isinstance(pts, list) or not pts:
        return [], 'O recorte não contém hexágonos agregados.'
    raio = recorte.get('raio_hex')
    if not isinstance(raio, (int, float)) or not math.isfinite(raio) or raio <= 0:
        return [], 'Raio dos hexágonos inválido.'
    try:
        n = int(recorte['n_validas'])
        n_vis = int(recorte['n_redacoes_exibidas'])
        n_ocult = int(recorte['n_redacoes_suprimidas'])
        h_vis = int(recorte['n_hexagonos_exibidos'])
        h_ocult = int(recorte['n_hexagonos_suprimidos'])
        if min(n,n_vis,n_ocult,h_vis,h_ocult)<0 or n_vis + n_ocult != n or h_vis != len(pts):
            raise ValueError('totais inconsistentes')
        vistos=set(); soma=0; resultado=[]
        for p in pts:
            v=p.get('count')
            if isinstance(v, bool) or not isinstance(v, int) or v < limiar:
                raise ValueError('contagem pequena/inválida')
            x=float(p['pc1']); y=float(p['pc2'])
            q=p['hex_q']; r=p['hex_r']
            if not math.isfinite(x) or not math.isfinite(y) or not isinstance(q,int) or not isinstance(r,int):
                raise ValueError('coordenadas inválidas')
            if (q,r) in vistos:raise ValueError('células duplicadas')
            # Centros arredondados a 7 casas nos JSONs existentes.
            if abs(x-math.sqrt(3)*raio*(q+r/2))>2e-5 or abs(y-1.5*raio*r)>2e-5:
                raise ValueError('geometria inconsistente')
            vistos.add((q,r)); soma+=v
            resultado.append({'pc1':x,'pc2':y,'count':v,'hex_q':q,'hex_r':r})
        if soma != n_vis:
            raise ValueError('soma de hexágonos não corresponde ao total exibido')
    except (KeyError, ValueError, TypeError, OverflowError):
        return [], 'Os dados agregados do mapa apresentaram inconsistência; a exibição foi suspensa.'
    return resultado, None


def validar_avaliadores(ind020: dict | None, ind021: dict | None,
                       ind022: dict | None) -> list[str]:
    """Verifica fechamento entre os indicadores 20–22 para um mesmo recorte.

    Não modifica agregados nem calcula percentis; se houver inconsistência,
    a página deve suspender os gráficos e informar o problema.
    """
    erros = []
    if not all(isinstance(d,dict) for d in (ind020,ind021,ind022)):
        return ['Um ou mais indicadores IND-020/021/022 não estão presentes.']
    a,b,c=ind020,ind021,ind022
    try:
        n=int(a['n_avaliacoes_pareadas'])
        if n<30:erros.append('Quantidade de avaliações inferior ao limiar técnico.')
        if n!=int(b['n_pop_evaluator']) or n!=int(c['n_pop_evaluator']):
            erros.append('Populações pareadas incompatíveis entre indicadores.')
        if not 0<=int(b['n_competencias_pareadas'])<=n:
            erros.append('Cobertura inválida de competências.')
        cs=b['competencias']
        if [v['competencia'] for v in cs]!=['C1','C2','C3','C4','C5']:
            erros.append('A lista de competências não contém C1–C5 em ordem.')
        if any(int(v['n_pares_validos'])!=int(b['n_competencias_pareadas']) for v in cs):
            erros.append('Denominadores diferentes entre competências.')
        for x in cs:
            if not (0<=float(x['media'])<=200 and 0<=float(x['p25'])<=float(x['mediana'])<=float(x['p75'])<=float(x['p90'])<=200):
                erros.append('Estatísticas inconsistentes das competências.')
        if n!=sum(int(x.get('n_redacoes',0)) for x in a['histograma']):
            erros.append('O histograma das diferenças totais não fecha com a população.')
        if n!=sum(int(c[z]) for z in ('n_discrepancia_confirmada','n_sem_discrepancia_confirmada','n_indeterminada')):
            erros.append('As três classificações de discrepância não fecham.')
        if any(int(c[k])>int(c['n_discrepancia_confirmada']) for k in (
            'n_criterio_total_gt100','n_criterio_comp_gt80','n_criterio_status_divergente')):
            erros.append('Um motivo ultrapassa o número de discrepâncias confirmadas.')
        if abs(100*int(c['n_discrepancia_confirmada'])/n - float(c['percentual_discrepancia_confirmada_pop_evaluator']))>0.0001:
            erros.append('Percentual de discrepância incompatível com as contagens.')
        if a.get('sem_dados_individuais') is not True or b.get('sem_dados_individuais') is not True or c.get('sem_dados_individuais') is not True:
            erros.append('Nem todos os recortes confirmam a ausência de dados individuais.')
    except (KeyError,ValueError,TypeError,IndexError,ZeroDivisionError):
        erros.append('Campos necessários aos indicadores 20–22 estão ausentes ou inválidos.')
    return erros
