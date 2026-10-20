"""Teste independente de extração do mapa IND-016 (sem servidor Streamlit).

Modo básico: copiar dashboard_enem_2024.json para esta mesma pasta.
Opcional: copiar IND_016_mapa_pc1_pc2.json (módulo do indicador) para conferir
224 recortes dos sete anos, 27 UFs e histórico.
"""
from pathlib import Path
import json
from painel_dados_enem import (UFS,carregar_json,obter_hexbin_ind016,validar_hexbin_ind016)

raiz = Path(__file__).resolve().parent
origem = raiz/'dashboard_enem_2024.json'
if not origem.exists():
    raise SystemExit('Coloque dashboard_enem_2024.json junto ao teste (ou copie-o temporariamente).')
ref = carregar_json(origem)
assert ref['meta']['year']==2024
checks = 0
for ano in (None, 2024):
    for uf in ('BR',)+UFS:
        rec = obter_hexbin_ind016(ref,ref,ano,uf)
        pontos,erro=validar_hexbin_ind016(rec)
        assert erro is None,(ano,uf,erro)
        assert len(pontos)==rec['n_hexagonos_exibidos']
        assert sum(p['count'] for p in pontos)==rec['n_redacoes_exibidas']
        assert rec['n_redacoes_exibidas']+rec['n_redacoes_suprimidas']==rec['n_validas']
        assert all(p['count']>=30 for p in pontos)
        checks += 5
    # proteção contra substituição silenciosa por ano errado
assert obter_hexbin_ind016(ref,ref,2023,'BR') is None
assert obter_hexbin_ind016(ref,ref,2019,'SP') is None
checks+=2
assert len(obter_hexbin_ind016(ref,ref,2024,'BR')['points'])==72
assert len(obter_hexbin_ind016(ref,ref,None,'BR')['points'])==88
checks+=2
rec=obter_hexbin_ind016(ref,ref,2024,'BR')
for change in (
    lambda p: p['points'][0].update(count=1),
    lambda p: p.update(n_redacoes_exibidas=20),
    lambda p: p.update(sem_pontos_individuais=False),
    lambda p: p['points'][0].update(pc1=1e12),
    lambda p: p['points'][0].update(hex_q=p['points'][1]['hex_q'],hex_r=p['points'][1]['hex_r']),
):
    trial=json.loads(json.dumps(rec)); change(trial)
    assert validar_hexbin_ind016(trial)[1] is not None
    checks += 1
# Avaliação de TODOS os anos a partir do JSON modular, sem microdados.
modular = raiz/'IND_016_mapa_pc1_pc2.json'
if modular.exists():
    data=json.loads(modular.read_text(encoding='utf8'))
    count=0
    for bloco in data['years']+[data['historical']]:
        for entrada in [bloco['brasil']]+bloco['ufs']:
            convertido=dict(entrada,points=[{**p,'count':p['quantidade'], 'hex_q':p['q'], 'hex_r':p['r']} for p in entrada['pontos']])
            pts,erro=validar_hexbin_ind016(convertido)
            assert erro is None,(bloco.get('ano','histórico'),entrada.get('uf','BR'),erro)
            assert len(pts)==entrada['n_hexagonos_exibidos']
            count+=1;checks+=2
    assert count==224
print(f'OK: {checks} verificações de extração, segurança e integridade IND-016.')
