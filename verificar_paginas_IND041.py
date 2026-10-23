# -*- coding: utf-8 -*-
r"""Diagnóstico local do Streamlit: valida arquivos e blocos agregados, sem importar Streamlit.

Execute na raiz do projeto após a instalação:
  .\.venv\Scripts\python.exe verificar_paginas_IND041.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FUNCOES = {
    "Alto desempenho": "pagina_alto_desempenho",
    "Contexto socioeconômico": "pagina_socioeconomica",
}
MODULOS = {
    "IND-030": ("high_performance", "score_bands"),
    "IND-031": ("high_performance", "loss_by_competency"),
    "IND-040": ("socioeconomic", "profile"),
    "IND-041": ("socioeconomic", "income_total"),
}


def main() -> int:
    erros = []
    visual = RAIZ / "visualizador.py"
    auxiliar = RAIZ / "painel_indicadores_recentes.py"
    base = RAIZ / "painel_dados_enem.py"

    for p in [visual, auxiliar, base]:
        if not p.is_file():
            erros.append(f"Falta arquivo na raiz do projeto: {p.name}")
    if visual.exists():
        src = visual.read_text(encoding="utf-8")
        try:
            ast.parse(src)
        except SyntaxError as exc:
            erros.append(f"Erro de sintaxe no visualizador: {exc}")
        for rotulo, func in FUNCOES.items():
            if f"elif pagina=='{rotulo}':{func}()" not in src:
                erros.append(f"Página '{rotulo}' ainda não aponta para {func} (versão antiga?).")
        if "Versão IND-041 · páginas Alto desempenho" not in src:
            erros.append("Não foi encontrado o selo de versão da nova interface no visualizador.")
        if "print-nav-espelho" not in src:
            erros.append("A impressão com menu lateral não está presente.")

    total = 0
    for ano in range(2019, 2025):
        caminho = RAIZ / "outputs" / "json" / f"dashboard_enem_{ano}.json"
        if not caminho.exists():
            erros.append(f"Falta dashboard para {ano}: {caminho}")
            continue
        try:
            dash = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            erros.append(f"Não foi possível ler {ano}: {exc}")
            continue
        if dash.get("meta", {}).get("year") != ano:
            erros.append(f"Ano interno do dashboard {ano} não corresponde ao arquivo.")
        for indicador, (pagina, chave) in MODULOS.items():
            bloco = dash.get("pages", {}).get(pagina, {}).get(chave)
            if not isinstance(bloco, dict) or bloco.get("indicator_id") != indicador:
                erros.append(f"{ano}: módulo {indicador} ausente no dashboard.")
            else:
                total += 1
        if ano == 2020:
            try:
                rr = dash['pages']['socioeconomic']['income_total']['states']['RR']
                if rr['n_renda_nao_informada'] != 16:
                    erros.append("2020/RR: contagem de 16 registros sem renda diverge.")
            except (KeyError, TypeError):
                erros.append("2020/RR: recorte do IND-041 não encontrado.")

    print(f"IND-041 | Módulos localizados: {total}/24 (6 anos x 4 indicadores)")
    if erros:
        print(f"FALHOU: {len(erros)} pendência(s)")
        for erro in erros:
            print(f"  - {erro}")
        print("Reinstale a atualização, confira o caminho da raiz e reinicie o Streamlit.")
        return 1
    print("APROVADO: navegação para Alto desempenho e Contexto socioeconômico, "
          "6 dashboards, IND-030/031/040/041 e menu de impressão.")
    print("Abra a sidebar do Streamlit e procure 'Versão IND-041 · páginas Alto desempenho ...'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
