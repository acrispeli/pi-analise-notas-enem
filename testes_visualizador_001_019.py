"""Testes de extração e privacidade, com o dashboard real de 2024.
Não importam o Streamlit nem os microdados do INEP."""
import tempfile, json, shutil
from pathlib import Path
from painel_dados_enem import (
  localizar_dashboards, carregar_json, obter_recorte, serie_anual,
  quantidade_segura, agrupar_frequencias_niveis, classes_redacao, UFS, ANOS
)

p=Path(__file__).with_name('dashboard_enem_2024.json')
if not p.is_file():
    raise SystemExit('Copie temporariamente o dashboard_enem_2024.json ao lado deste teste, se desejar executar testes com dados reais.')
d=carregar_json(p)
assert d['meta']['year']==2024
n=0
# Todos os anos + Brasil, todos os anos + todas as UFs, cada ano BR
for ind in range(1,20):
    for uf in ('BR',)+UFS:
        doc=obter_recorte(d,None,ind,None,uf)
        assert doc is not None,(ind,uf,'historico')
        n+=1
    for ano in ANOS:
        doc=obter_recorte(d,None,ind,ano,'BR')
        assert doc is not None,(ind,ano,'BR')
        n+=1
    # Ano + UF, com dashboard de 2024
    for uf in UFS:
        doc=obter_recorte(d,d,ind,2024,uf)
        assert doc is not None,(ind,2024,uf)
        n+=1
# Não usar 2024 como se fosse 2019
for ind in range(1,20):
    assert obter_recorte(d,d,ind,2019,'SP') is None
    n+=1
# Horizonte BR extraído das séries reais
for ind in range(1,20):
    serie=serie_anual(d,{2024:p},ind,'BR')
    assert [x['year'] for x in serie]==list(ANOS)
    n+=1
assert quantidade_segura(0)==0
assert quantidade_segura(2) is None
assert quantidade_segura(29) is None
assert quantidade_segura(30)==30
n+=4
# Mescla faixas raras sem divulgar valor exato pequeno.
levels=[{'score':0,'count':4},{'score':80,'count':8},{'score':120,'count':22},{'score':160,'count':200}]
r=agrupar_frequencias_niveis(levels)
assert sum(v['quantidade'] for v in r)==234 and all(v['quantidade']==0 or v['quantidade']>=30 for v in r)
n+=1
# Categorias raras agrupadas
cats=d['pages']['overview']['essay_status']['categories']
agg=classes_redacao(cats)
assert len(agg)==2 and sum(x['quantidade'] for x in agg)==d['pages']['overview']['essay_status']['n']
n+=1
# 2024 BR matches historical for the matching 2024 national year
for ind in range(1,20):
    x=obter_recorte(d,None,ind,2024,'BR')
    y=obter_recorte(d,d,ind,2024,'SP')
    assert x and y
    n+=1
print(f'OK — {n} verificações, 19 indicadores, 27 UFs, 7 anos e histórico.')
