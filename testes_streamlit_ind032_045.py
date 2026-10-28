#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do carregamento e dos gráficos IND-032..039 e IND-042..045.

Uso na raiz do projeto:
  python testes_streamlit_ind032_045.py
  python testes_streamlit_ind032_045.py --ano 2024

Os dados permanecem locais; nenhuma leitura de microdados é feita.
"""
from __future__ import annotations
import argparse
import json
from contextlib import nullcontext
from pathlib import Path

from painel_indicadores_recentes import bloco, recorte
from painel_visualizacoes_novas import alto_desempenho_novos, socioeconomico_novos


class _Coluna:
    def __init__(self, ui): self.ui = ui
    def __enter__(self): return self.ui
    def __exit__(self, *args): return False
    def metric(self, *args, **kwargs): self.ui.metric(*args, **kwargs)


class _UIFalsa:
    """Simula componentes Streamlit sem abrir o navegador; Plotly continua real."""
    def __init__(self): self.graficos = 0; self.tabelas = 0; self.avisos = 0
    def tabs(self, nomes): return [nullcontext() for _ in nomes]
    def columns(self, colunas): return [_Coluna(self) for _ in range(len(colunas) if isinstance(colunas, list) else colunas)]
    def expander(self, *args, **kwargs): return nullcontext()
    def radio(self, titulo, opcoes, *args, **kwargs): return opcoes[0]
    def selectbox(self, titulo, opcoes, *args, **kwargs): return opcoes[0]
    def metric(self, *args, **kwargs): pass
    def markdown(self, *args, **kwargs): pass
    def caption(self, *args, **kwargs): pass
    def divider(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): self.avisos += 1
    def dataframe(self, *args, **kwargs): self.tabelas += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ano', type=int, default=2024)
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    arquivo = args.raiz/'outputs'/'json'/f'dashboard_enem_{args.ano}.json'
    if not arquivo.is_file():
        parser.error(f'Dashboard não localizado: {arquivo}')
    with arquivo.open(encoding='utf-8-sig') as arq:
        doc = json.load(arq)
    assert doc.get('meta', {}).get('year') == args.ano, 'Ano do dashboard incorreto'
    checks = 0
    if args.ano == 2024:
        for ind in (32,33,34,35,36,37,38,39,42,43,44,45):
            assert bloco(doc, ind) is not None, f'IND-{ind:03d} não integrado em 2024'
            checks += 1
    for uf in ('BR', 'SP', 'AC', 'RR'):
        for ind in (32,33,34,35,36,37,38,39,42,43,44,45):
            r = recorte(doc, ind, uf)
            if r is None:
                if args.ano == 2024:
                    raise AssertionError(f'IND-{ind:03d}/{uf} sem recorte em 2024')
                continue
            assert r.get('uf') == uf, f'IND-{ind:03d}/{uf} com UF incorreta'
            if ind == 38:
                assert len(r['competencias']) == 5, 'IND-038 deve trazer cinco competências'
            checks += 1
        tela = _UIFalsa()
        def plot(fig, altura=335):
            assert len(fig.data), 'Gráfico Plotly vazio'
            tela.graficos += 1
        alto_desempenho_novos(tela, plot, args.ano, uf, {args.ano: doc})
        socioeconomico_novos(tela, plot, args.ano, uf, {args.ano: doc})
        if args.ano == 2024:
            assert tela.graficos >= 10, f'Poucos gráficos em {uf}: {tela.graficos}'
        checks += tela.graficos
        print(f'{args.ano}/{uf}: {tela.graficos} gráficos renderizados, {tela.tabelas} tabelas.')
    print(f'Validação concluída: {checks} verificações aprovadas.')

if __name__ == '__main__': main()
