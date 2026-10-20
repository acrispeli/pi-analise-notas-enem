"""Testes da camada de leitura de agregados reais (sem servidor Streamlit).

Execução local: python testes_visualizador_001_022.py
Fixture: dashboard_enem_2024.json ao lado do teste, APENAS durante a validação.
"""
from pathlib import Path
import json
from painel_dados_enem import (
    ANOS,UFS,carregar_json,obter_recorte,serie_anual,validar_avaliadores,
    quantidade_segura,obter_hexbin_ind016,validar_hexbin_ind016,
)

fixture=Path(__file__).parent/'dashboard_enem_2024.json'
if not fixture.exists():
    fixture=Path(__file__).parent/'outputs'/'json'/'dashboard_enem_2024.json'
if not fixture.exists():
    raise SystemExit('Para este teste, coloque temporariamente dashboard_enem_2024.json ao lado do script.')
r=carregar_json(fixture)
assert r['meta']['year']==2024
checks=0
for i in range(1,23):
    for uf in ('BR',)+UFS:
        assert obter_recorte(r,None,i,None,uf) is not None,(i,'historico',uf);checks+=1
    for year in ANOS:
        assert obter_recorte(r,None,i,year,'BR') is not None,(i,year,'BR');checks+=1
    for uf in UFS:
        assert obter_recorte(r,r,i,2024,uf) is not None,(i,2024,uf);checks+=1
    assert obter_recorte(r,r,i,2020,'SP') is None;checks+=1
    v=serie_anual(r,{2024:fixture},i,'BR')
    assert [e['year'] for e in v]==list(ANOS);checks+=1
for y in [None,*ANOS]:
    for uf in ('BR',)+UFS:
        if y not in (None,2024) and uf!='BR':continue
        vals=[obter_recorte(r,r if y==2024 else None,i,y,uf) for i in (20,21,22)]
        assert not validar_avaliadores(*vals),(y,uf,validar_avaliadores(*vals));checks+=1
        a,b,c=vals
        assert a['n_avaliacoes_pareadas']==b['n_pop_evaluator']==c['n_pop_evaluator'];checks+=1
        assert sum(z['n_redacoes'] for z in a['histograma'])==a['n_avaliacoes_pareadas'];checks+=1
        assert c['n_discrepancia_confirmada']+c['n_sem_discrepancia_confirmada']+c['n_indeterminada']==a['n_avaliacoes_pareadas'];checks+=1
        assert len(b['competencias'])==5;checks+=1
for uf in ('BR','SP'):
    pontos,e=validar_hexbin_ind016(obter_hexbin_ind016(r,r,2024,uf))
    assert e is None and pontos;checks+=1
assert quantidade_segura(29) is None
assert quantidade_segura(30)==30
checks+=2
# Teste negativo de integridade sem alterar o documento real.
for i in (20,21,22):
    assert obter_recorte(r,r,i,2019,'SP') is None;checks+=1
v20,v21,v22=[obter_recorte(r,r,i,2024,'BR') for i in (20,21,22)]
for bad in ({**v20,'n_avaliacoes_pareadas':v20['n_avaliacoes_pareadas']-1},None):
    assert validar_avaliadores(bad,v21,v22);checks+=1
print(f'OK: {checks:,} verificações, IND-001..022, 27 UFs, 7 anos + histórico, recortes com fonte.')
