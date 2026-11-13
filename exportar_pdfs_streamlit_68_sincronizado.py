#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exporta PDFs dos 68 indicadores da redação ENEM (Brasil), por dois recortes.

Recortes padrão: Todos os anos (2019–2025) e 2024; UF sempre Brasil.
Captura 68 indicadores em cada recorte, expansores abertos, com detalhes extras
C1–C5 do IND-012 e as duas variantes do IND-034 quando disponíveis.
Gera PDF por captura, volumes por página, dois relatórios gerais, CSV e índice.
Correção: seleciona os rótulos visíveis das duas variantes do IND-034.

Recomendado: executar em um segundo terminal do VS Code com o Streamlit local
aberto no primeiro. O site público também é aceito por --url, mas pode demorar
mais ou ter diferenças de versão. Não altera dados, código nem Git do projeto.

Exemplos:
  python exportar_pdfs_streamlit_68.py --raiz D:\\pi-analise-notas-enem --indicadores 12 --visivel
  python exportar_pdfs_streamlit_68.py --raiz D:\\pi-analise-notas-enem
  python exportar_pdfs_streamlit_68.py --raiz D:\\pi-analise-notas-enem --url https://enem-redacao-univesp-pi4.streamlit.app/

Dependências: python -m pip install playwright pypdf
Navegador: Edge local; alternativa: python -m playwright install chromium.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import html
import json
import os
import shutil
import re
from pathlib import Path
import sys
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.error import URLError
from zipfile import ZipFile, ZIP_DEFLATED

NAVEGACAO = {
    'overview': 'Visão geral',
    'competencies': 'Competências',
    'evaluators': 'Avaliadores',
    'high_performance': 'Alto desempenho',
    'socioeconomic': 'Contexto socioeconômico',
    'ml': 'Padrões por ML',
    'temporal': 'Evolução temporal',
    'methodology': 'Metodologia',
}


def slug(txt: str, limite: int = 58) -> str:
    txt = ''.join(c for c in unicodedata.normalize('NFD', txt)
                  if unicodedata.category(c) != 'Mn').lower()
    return re.sub(r'[^a-z0-9]+', '_', txt).strip('_')[:limite]


def interpretar_anos(valores: list[str]) -> list[str]:
    result = []
    for x in valores:
        for valor in x.split(','):
            valor = valor.strip().lower()
            if valor in ('todos', 'historico', 'histórico', 'todos-os-anos'):
                result.append('Todos os anos')
            elif valor in ('2019-2025', '2019:2025', 'cada', 'individuais'):
                result.extend(str(ano) for ano in range(2019, 2026))
            elif re.fullmatch(r'20(19|2[0-5])', valor):
                result.append(valor)
            else:
                raise ValueError(f'Ano inválido: {valor!r}. Use todos, 2019-2025 ou 2019 ... 2025.')
    return list(dict.fromkeys(result))


def interpretar_ids(valores: list[str] | None) -> set[int] | None:
    if not valores:
        return None
    result = set()
    for x in valores:
        for parte in x.split(','):
            parte = parte.strip().upper().replace('IND-', '')
            if '-' in parte:
                inicio, fim = parte.split('-', 1)
                if not (inicio.isdigit() and fim.isdigit()):
                    raise ValueError(f'Indicador inválido: {parte}')
                result.update(range(int(inicio), int(fim)+1))
            elif parte.isdigit():
                result.add(int(parte))
            else:
                raise ValueError(f'Indicador inválido: {parte}')
    return result


def carregar_pistas_pedagogicas(raiz: Path) -> dict[int, str]:
    """Lê descrições literais do indicador sem executar a aplicação."""
    import ast
    arquivo = raiz / 'leitura_acessivel_68.py'
    if not arquivo.is_file():
        return {}
    arvore = ast.parse(arquivo.read_text(encoding='utf-8-sig'), filename=str(arquivo))
    for bloco in arvore.body:
        if isinstance(bloco, ast.Assign) and any(
                isinstance(alvo, ast.Name) and alvo.id == 'GUIAS' for alvo in bloco.targets):
            return {int(n): str(txt[0]) for n, txt in ast.literal_eval(bloco.value).items()}
    return {}


def carregar_catalogo(raiz: Path) -> list[dict]:
    path = raiz / 'docs' / 'catalogo_navegacao_68.json'
    if not path.is_file():
        raise FileNotFoundError(f'Arquivo obrigatório não encontrado: {path}.\nPasse --raiz com a pasta do projeto.')
    catalogo = json.loads(path.read_text(encoding='utf-8-sig'))
    itens = catalogo['indicadores']
    if len(itens) != 68 or len({x['numero'] for x in itens}) != 68:
        raise ValueError('O catálogo precisa ter 68 indicadores únicos.')
    if any(i['pagina'] not in NAVEGACAO for i in itens):
        raise ValueError('O catálogo usa uma página não reconhecida.')
    return itens


def _caixa_selectbox(page, label: str, *, timeout_ms: int = 180000):
    """Espera pela renderizacao REAL do widget (e nao pelo esqueleto Streamlit).

    O HTML Streamlit moderno cria primeiro um wrapper `st-key-...` contendo
    apenas `stSkeleton`, que desaparece quando o controle chega do servidor.
    """
    chaves = {
        'Ano': 'ano_filtro',
        'Local da prova': 'uf_filtro',
    }
    # Primeiro identificamos pelo widget key estavel; e fallback textual
    # para seletores internos que nao possuem chave conhecida.
    if label in chaves:
        seletores = [
            f'[class~="st-key-{chaves[label]}"] [data-testid="stSelectbox"]',
            f'[data-testid="stSelectbox"]',
        ]
    else:
        seletores = ['[data-testid="stSelectbox"]']

    limite = time.monotonic() + timeout_ms / 1000
    proximo_aviso = time.monotonic() + 15
    while time.monotonic() < limite:
        try:
            for css in seletores:
                caixas = page.locator(css)
                if label in chaves and css.startswith('[class~='):
                    if caixas.count() and caixas.first.is_visible():
                        return caixas.first
                else:
                    # Garante correspondencia de rotulo (nao qualquer selectbox).
                    caixas = caixas.filter(has=page.get_by_text(label, exact=True))
                    if caixas.count() and caixas.first.is_visible():
                        return caixas.first
            # Falha explicita para erros do aplicativo que nunca carregarao.
            if page.locator('[data-testid="stException"]').count():
                err = page.locator('[data-testid="stException"]').first.inner_text(timeout=3000)
                raise RuntimeError(f'O Streamlit apresentou um erro: {err[:500]}')
        except RuntimeError:
            raise
        except Exception:
            pass
        agora = time.monotonic()
        if agora >= proximo_aviso:
            n_esqueletos = page.locator('[data-testid="stSkeleton"]').count()
            n_selects = page.locator('[data-testid="stSelectbox"]').count()
            print(f'  Aguardando filtro {label!r} ficar pronto: '
                  f'{n_esqueletos} campos carregando, {n_selects} seletores visiveis...',
                  flush=True)
            proximo_aviso = agora + 15
        page.wait_for_timeout(500)

    n_esqueletos = page.locator('[data-testid="stSkeleton"]').count()
    n_selects = page.locator('[data-testid="stSelectbox"]').count()
    estado = page.locator('[data-testid="stApp"]').first.get_attribute('data-test-script-state')
    raise RuntimeError(
        f'O filtro {label!r} nao terminou de carregar em {timeout_ms//1000} segundos. '
        f'Esqueletos na pagina: {n_esqueletos}; selectboxes: {n_selects}; '
        f'estado do script: {estado}. Veja a imagem de diagnostico. '
        'Se continuar carregando, confira o terminal do Streamlit.'
    )


def esperar_filtros(page, timeout_ms: int = 180000):
    """Espera pelos dois filtros reais, sem depender de um sleep fixo."""
    print('  Aguardando o Streamlit terminar de renderizar Ano e UF...', flush=True)
    _caixa_selectbox(page, 'Ano', timeout_ms=timeout_ms)
    _caixa_selectbox(page, 'Local da prova', timeout_ms=timeout_ms)
    print('  Filtros visiveis. Iniciando selecao.', flush=True)


def _controle_selectbox(caixa, label: str):
    """Suporta o select clássico BaseWeb e o combobox das versões novas."""
    possibilidades = (
        '[data-baseweb="select"]',
        '[role="combobox"]',
        '[aria-haspopup="listbox"]',
        'input[aria-autocomplete]',
        'input',
    )
    for css in possibilidades:
        item = caixa.locator(css)
        if item.count() and item.first.is_visible():
            return item.first
    # Antes de falhar, oferece um diagnóstico útil da estrutura do widget.
    trecho = caixa.evaluate('(el) => el.outerHTML.slice(0, 2000)')
    raise RuntimeError(
        f'Controle do filtro {label!r} não encontrado; HTML do widget: {trecho}'
    )


def selectbox(page, label: str, opcao: str, *, prefixo=False):
    """Seleciona opções em diferentes implementações do st.selectbox.

    Não muda o código do aplicativo. Faz cliques reais pelo Playwright.
    """
    caixa = _caixa_selectbox(page, label)
    controle = _controle_selectbox(caixa, label)
    atual = (controle.get_attribute('value') or controle.inner_text(timeout=5000) or caixa.inner_text()).strip()
    padrao_alvo = re.compile(r'^\s*'+re.escape(opcao) + (r'(?:\s|·|$)' if prefixo else r'\s*$'))
    if padrao_alvo.search(atual):
        return

    controle.click(timeout=20000)
    # A lista pode ser desenhada por BaseWeb ou por um portal fora do widget.
    candidatos = [
        page.get_by_role('option').filter(has_text=padrao_alvo),
        page.locator('[role="listbox"] [role="option"]').filter(has_text=padrao_alvo),
        page.locator('[data-baseweb="popover"]').get_by_text(padrao_alvo),
    ]
    for candidato in candidatos:
        try:
            candidato.first.click(timeout=3500)
            return
        except Exception:
            continue

    # Fallback para selectboxes que permitem digitar e filtrar opções.
    caixa = _caixa_selectbox(page, label)
    campo = caixa.locator('input')
    if campo.count():
        try:
            campo.first.fill(opcao, timeout=3000)
            page.wait_for_timeout(350)
            page.get_by_role('option').filter(has_text=padrao_alvo).first.click(timeout=3000)
            return
        except Exception:
            try:
                campo.first.press('Escape', timeout=2000)
            except Exception:
                pass
    raise RuntimeError(
        f'Não foi possível escolher {opcao!r} no filtro {label!r}. '
        f'Opções visíveis: {page.locator("[role=option]").all_inner_texts()[:18]!r}'
    )


def aplicar_filtros(page, ano: str, uf: str):
    selectbox(page, 'Ano', ano)
    page.wait_for_timeout(450)
    if uf == 'BR':
        selectbox(page, 'Local da prova', 'Todos os estados (Brasil)')
    else:
        # O rótulo completo contém a UF entre parênteses.
        caixa = _caixa_selectbox(page, 'Local da prova')
        controle = _controle_selectbox(caixa, 'Local da prova')
        atual = (controle.inner_text(timeout=5000) or '').strip()
        if re.search(r'\('+re.escape(uf)+r'\)\s*$', atual):
            return
        controle.click(timeout=18000)
        op = page.get_by_role('option').filter(has_text=re.compile(r'\('+re.escape(uf)+r'\)\s*$'))
        op.first.click(timeout=15000)


def registrar_diagnostico_filtros(page, pasta: Path, recorte: str):
    """Guarda HTML e PNG apenas em caso de falha; sem alterar o Streamlit."""
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f'DIAGNOSTICO_FILTROS_{slug(recorte)}'
    try:
        (destino.with_suffix('.html')).write_text(page.content(), encoding='utf-8')
    except Exception:
        pass
    try:
        page.screenshot(path=str(destino.with_suffix('.png')), full_page=False, timeout=12000)
    except Exception:
        pass
    print('Diagnóstico da tela: '+str(destino)+'.png/.html', flush=True)


def navegar_pagina(page, nome: str):
    radio = page.locator('[data-testid="stSidebar"] [data-testid="stRadio"]').first
    radio.wait_for(state='visible', timeout=180000)
    radio.get_by_text(nome, exact=True).click(timeout=30000)
    page.get_by_role('heading', name=nome, exact=True).first.wait_for(state='visible', timeout=180000)


def navegar_indicador(page, numero: int):
    codigo = f'IND-{numero:03d}'
    selectbox(page, 'Indicador do catálogo', codigo, prefixo=True)
    page.get_by_role('heading', name=re.compile('^'+re.escape(codigo)+r'\s*·')).first.wait_for(
        state='visible', timeout=180000)


def expandir_expanders(page, limite=90) -> tuple[int, int]:
    """Clica de verdade nos <summary> para garantir que o conteudo seja renderizado.
    Retorna (abertos, fechados restantes)."""
    abertos = 0
    for _ in range(limite):
        fechados = page.locator('[data-testid="stExpander"] details:not([open])')
        if fechados.count() == 0:
            break
        resumo = fechados.first.locator('summary').first
        try:
            resumo.click(timeout=8000, force=True)
            abertos += 1
            page.wait_for_timeout(80)
        except Exception:
            break
    restantes = page.locator('[data-testid="stExpander"] details:not([open])').count()
    return abertos, restantes


def carregar_componentes_preguicosos(page):
    """Rola a página para ativar Plotly e componentes que carregam sob demanda."""
    page.evaluate('''async () => {
      const pausa = ms => new Promise(resolve => setTimeout(resolve, ms));
      const candidatos = [document.scrollingElement,
        document.querySelector('[data-testid="stMain"]'),
        document.querySelector('[data-testid="stMainBlockContainer"]')]
        .filter(Boolean);
      for (const el of candidatos) {
        if (!el || el.scrollHeight <= el.clientHeight) continue;
        const max = el.scrollHeight - el.clientHeight;
        const passo = Math.max(650, el.clientHeight * 0.8);
        for (let y=0; y < max; y += passo) {
          el.scrollTop = y;
          await pausa(40);
        }
        el.scrollTop = max;
        await pausa(80);
        el.scrollTop = 0;
      }
      window.scrollTo(0,0);
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
    }''')


def abas_disponiveis(page) -> list[str]:
    # St.tabs usa elementos role=tab. Para painéis com abas, cada aba pede sua impressão.
    tabs = page.locator('[data-testid="stTabs"] [role="tab"]')
    return [x.strip() for x in tabs.all_text_contents() if x.strip()]


def caminho_disponivel(destino: Path) -> bool:
    if not destino.is_file() or destino.stat().st_size < 1500:
        return False
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(destino), strict=False).pages) >= 1
    except Exception:
        return False


def esperar_conteudo_pronto(page, timeout_ms: int = 120000):
    """Nao imprime um grafico/tabela que ainda esta como esqueleto na area principal."""
    limite = time.monotonic() + timeout_ms/1000
    ultimo_aviso = time.monotonic() + 15
    seletor = '[data-testid="stMain"] [data-testid="stSkeleton"]:visible'
    while time.monotonic() < limite:
        if page.locator(seletor).count() == 0:
            # Pequena estabilizacao para nao capturar uma transicao de rerun.
            page.wait_for_timeout(450)
            if page.locator(seletor).count() == 0:
                return
        if page.locator('[data-testid="stException"]').count():
            erro = page.locator('[data-testid="stException"]').first.inner_text(timeout=3000)
            raise RuntimeError(f'O Streamlit apresentou erro durante a renderizacao: {erro[:500]}')
        if time.monotonic() > ultimo_aviso:
            print('  Aguardando graficos e tabelas terminarem de carregar...', flush=True)
            ultimo_aviso = time.monotonic() + 15
        page.wait_for_timeout(500)
    raise RuntimeError('Ha componentes da area principal ainda carregando; PDF nao gerado. '
                       'Veja os avisos no terminal do Streamlit.')


# O Streamlit implementa a rolagem dentro de <main data-testid="stMain">.
# Sem estes estilos, o Chromium imprime apenas a porcao inicialmente visivel.
ESTILO_IMPRESSAO = r"""
html, body, #root, #root > div,
[data-testid="stApp"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    overflow: visible !important;
    overflow-y: visible !important;
    position: static !important;
}
html, body, #root { margin: 0 !important; padding: 0 !important; }
[data-testid="stApp"], [data-testid="stAppViewContainer"],
[data-testid="stMain"] { display: block !important; width: 100% !important; }
[data-testid="stMainBlockContainer"] {
    width: 100% !important;
    max-width: none !important;
    box-sizing: border-box !important;
    padding: 8px 12px !important;
    margin: 0 auto !important;
}
[data-testid="stSidebar"], [data-testid="stHeader"],
[data-testid="stSkillsNudgeAnchor"], [data-testid="stSkillsNudge"],
[data-testid="stAppIframeResizerAnchor"],
[data-testid="stBottom"], [data-testid="portal"],
#stFloatingOverlayPortal, [data-testid="stToolbar"] {
    display: none !important;
}
/* Nao corte SVGs e graficos na troca de folhas. */
[data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"],
[data-testid="stPyplotGlobalUse"], .js-plotly-plot {
    break-inside: avoid !important;
    page-break-inside: avoid !important;
}
"""


def _normalizar_validacao(txt: str) -> str:
    txt=''.join(c for c in unicodedata.normalize('NFD',txt)
                if unicodedata.category(c)!='Mn')
    return re.sub(r'\s+', ' ', txt).casefold()


def _itens_ausentes(texto: str, codigo: str, titulo: str,
                   pergunta: str, pista: str) -> list[str]:
    """Detecta conteúdo anterior apesar do cabeçalho aparentemente atualizado."""
    normal = _normalizar_validacao(texto)
    itens = [
        ('título', f'{codigo} · {titulo}' if titulo else ''),
        ('pergunta', pergunta),
        ('explicação específica', pista[:72]),
        ('leitura pedagógica', 'O que está sendo contado ou comparado?'),
    ]
    return [nome for nome, valor in itens
            if valor and _normalizar_validacao(valor) not in normal]


def reabrir_leitura_pedagogica(page) -> bool:
    """Reabre somente o guia específico se um rerun o recolapsou.

    Mantém a verificação de título, pergunta e texto do indicador; não
    considera o painel pronto se o guia continuar ausente.
    """
    fechados = page.locator(
        '[data-testid="stMain"] [data-testid="stExpander"] '
        'details:not([open]) summary'
    ).filter(has_text='Entenda este resultado · explicação simples')
    if fechados.count() == 0:
        return False
    fechados.first.click(timeout=6000)
    return True


def esperar_indicador_estavel(page, codigo: str, titulo: str = '',
                              pergunta: str = '', pista: str = '',
                              timeout_ms: int = 120000) -> str:
    """Exige cabeçalho, pergunta, guia, script ocioso e 3 leituras estáveis."""
    if not codigo:
        return ''
    fim = time.monotonic() + timeout_ms / 1000
    anterior = None
    iguais = 0
    diagnostico = 'aguardando renderização'
    if titulo:
        esperado = re.compile(r'^' + re.escape(codigo) + r'\s*·\s*' +
                              re.escape(titulo) + r'\s*$')
    else:
        esperado = re.compile(r'^' + re.escape(codigo) + r'\s*·')
    while time.monotonic() < fim:
        erros = page.locator('[data-testid="stException"]')
        if erros.count():
            raise RuntimeError('Erro do Streamlit: ' +
                               erros.first.inner_text(timeout=3000)[:500])
        try:
            app = page.locator('[data-testid="stApp"]')
            estado = (app.first.get_attribute('data-test-script-state')
                      if app.count() else None)
            esqueletos = page.locator(
                '[data-testid="stMain"] [data-testid="stSkeleton"]:visible').count()
            cabecalho = page.get_by_role('heading', name=esperado).count() > 0
            texto = page.locator('[data-testid="stMain"]').inner_text(timeout=3000)
            ausentes = _itens_ausentes(texto, codigo, titulo, pergunta, pista)
            # A abertura feita antes da impressão pode ser desfeita por um
            # rerun. Se isso ocorreu, recupere o expander e confira novamente
            # o texto específico; nunca dispense essa verificação.
            if (estado in (None, '', 'notRunning', 'idle') and
                    esqueletos == 0 and cabecalho and
                    'leitura pedagógica' in ausentes and
                    reabrir_leitura_pedagogica(page)):
                print(f'  {codigo}: leitura pedagógica recolapsada; reabrindo o painel.',
                      flush=True)
                anterior = None
                iguais = 0
                page.wait_for_timeout(350)
                continue
            pronto = (estado in (None, '', 'notRunning', 'idle') and
                      esqueletos == 0 and cabecalho and not ausentes)
            atual = _normalizar_validacao(texto) if pronto else None
            iguais = iguais + 1 if pronto and atual == anterior else (1 if pronto else 0)
            anterior = atual
            diagnostico = (f'estado={estado}, esqueletos={esqueletos}, '
                           f'cabeçalho={cabecalho}, ausentes={ausentes}')
            if iguais >= 3:
                print(f'  Conteúdo sincronizado: {codigo} · título, pergunta e leitura confirmados.',
                      flush=True)
                return texto
        except RuntimeError:
            raise
        except Exception as exc:
            anterior = None
            iguais = 0
            diagnostico = str(exc)
        page.wait_for_timeout(500)
    raise RuntimeError(
        f'Captura bloqueada: {codigo} não estabilizou. {diagnostico}. '
        'Se o cabeçalho estiver correto e a explicação faltar, confira se '
        'o painel "Entenda este resultado" foi renderizado e se há aviso '
        'de fonte ausente; a captura não foi aprovada.')


def imprimir_pdf(page, destino: Path, papel: str, paisagem: bool, espera: int,
                 codigo: str = '', competencia: str = '', titulo: str = '',
                 pergunta: str = '', pista: str = '') -> int:
    from pypdf import PdfReader
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Garante abertura dos paineis apos os ultimos reruns do Streamlit.
    esperar_conteudo_pronto(page)
    expandir_expanders(page)
    page.wait_for_timeout(200)
    carregar_componentes_preguicosos(page)
    esperar_conteudo_pronto(page)
    page.wait_for_timeout(espera)

    texto_pronto = esperar_indicador_estavel(page, codigo, titulo, pergunta, pista)
    conteudo_tela = _normalizar_validacao(
        texto_pronto if codigo else
        page.locator('[data-testid="stMain"]').inner_text(timeout=30000))
    verificacoes = []
    if codigo:
        verificacoes.append(codigo)
        if titulo:
            verificacoes.append(f'{codigo} · {titulo}')
        if pergunta:
            verificacoes.append(pergunta[:72])
        if pista:
            verificacoes.append(pista[:72])
    # A pergunta abaixo aparece dentro do expander de explicacao, nao apenas
    # no convite que existe no inicio do indicador.
    for sinal in ('O que está sendo contado ou comparado?', 'Denominadores e medidas complementares'):
        if _normalizar_validacao(sinal) in conteudo_tela:
            verificacoes.append(sinal)
    if codigo == 'IND-012':
        titulo_grafico = 'Notas observadas da ' + (competencia or 'C1')
        if _normalizar_validacao(titulo_grafico) not in conteudo_tela:
            raise RuntimeError('A distribuicao '+(competencia or '')+
                ' nao terminou de renderizar no navegador. Nao e seguro imprimir.')
        verificacoes.append(titulo_grafico)
        # A legenda do grafico e especifica de cada competencia, evitando
        # cinco PDFs iguais sem conteudo diferenciado.

    # Mantem o estilo de tela (Plotly), mas libera alturas/overflow do Streamlit
    # antes da paginacao. Insere CSS no documento da sessao de automacao.
    page.emulate_media(media='screen')
    estilo = page.add_style_tag(content=ESTILO_IMPRESSAO)
    try:
        page.wait_for_timeout(350)
        altura = page.evaluate("""() => {
            const main=document.querySelector('[data-testid="stMain"]');
            const doc=document.documentElement;
            return {
                body: document.body.scrollHeight, doc:doc.scrollHeight,
                main:main?.scrollHeight || 0, janela:window.innerHeight
            };
        }""")
        print('  Area preparada para impressao: '+str(altura), flush=True)

        page.pdf(
            path=str(destino), format=papel, landscape=paisagem,
            print_background=True, prefer_css_page_size=False,
            scale=0.85,
            margin={'top':'12mm','bottom':'14mm','left':'10mm','right':'10mm'},
            display_header_footer=True,
            header_template='<div></div>',
            footer_template=('<div style="font-size:8px;width:100%;text-align:center;'
                             'color:#666">Projeto Integrador IV - UNIVESP &nbsp;'
                             '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'),
        )
    finally:
        # O CSS de impressao nao pode ocultar a barra lateral na proxima captura.
        try:
            estilo.evaluate("elemento => elemento.remove()")
        except Exception:
            pass
    leitor=PdfReader(str(destino), strict=False)
    paginas=len(leitor.pages)
    texto_pdf=_normalizar_validacao(' '.join(
        pg.extract_text() or '' for pg in leitor.pages))
    ausentes=[sinal for sinal in verificacoes
             if _normalizar_validacao(sinal) not in texto_pdf]
    if paginas < 1 or ausentes:
        # Nao anuncia OK para um PDF que so capturou o cabecalho da pagina.
        destino_falho=destino.with_name(destino.stem+'_INCOMPLETO.pdf')
        destino.replace(destino_falho)
        raise RuntimeError(
            f'PDF incompleto ({paginas} pagina(s)): faltou {ausentes}. '
            f'Conferir {destino_falho}.')
    return paginas


def salvar_png(page, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(destino), full_page=True,
                    animations='disabled', timeout=120000)


def validar_url(url: str):
    endereco = urlsplit(url)
    local = endereco.hostname in ('localhost', '127.0.0.1', '::1')
    publico = endereco.hostname == 'enem-redacao-univesp-pi4.streamlit.app'
    if not (endereco.scheme in ('http', 'https') and (local or (publico and endereco.scheme == 'https'))):
        raise ValueError('Use o Streamlit local (http://localhost:8501) ou '
                         'https://enem-redacao-univesp-pi4.streamlit.app/.')
    try:
        with urlopen(url, timeout=22 if publico else 8) as resp:
            if resp.status >= 400:
                raise ValueError(f'HTTP {resp.status}')
    except (TimeoutError, URLError, OSError) as e:
        raise RuntimeError(f'Streamlit não acessível em {url}: {e}. '
                           'Se for local, inicie-o em outro terminal.') from e


def gerar_csv_html(raiz: Path, registros: list[dict]):
    raiz.mkdir(parents=True, exist_ok=True)
    with (raiz/'RESULTADOS.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=['recorte','tipo','pagina','indicador','variante','arquivo','folhas','status','erro'], delimiter=';')
        w.writeheader()
        w.writerows(registros)
    linhas=[]
    for r in registros:
        arq=r['arquivo']
        link=(f'<a href="{html.escape(arq, quote=True)}">Abrir PDF</a>' if arq else '')
        linhas.append('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in
                   (r['recorte'],r['tipo'],r['pagina'],r['indicador'],r['variante'],r['status'],r['folhas']))
                   +f'<td>{link}</td></tr>')
    s='''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
    <title>Exportações do Streamlit - ENEM</title><style>body{font:15px Arial,sans-serif;max-width:1500px;margin:auto;padding:24px}
    table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}
    tr:hover{background:#f2f4f7}</style><h1>PDFs do painel ENEM</h1>
    <p>Recortes: Todos os anos e 2024; local: Brasil. Expansores abertos. Tabelas interativas podem exibir apenas linhas renderizadas na tela. Veja RESULTADOS.csv para eventuais falhas.</p>
    <table><tr><th>Recorte</th><th>Tipo</th><th>Página</th><th>Indicador</th><th>Aba</th><th>Status</th><th>Folhas</th><th>PDF</th></tr>'''+ ''.join(linhas) + '</table></html>'
    (raiz/'INDICE.html').write_text(s,encoding='utf-8')


def juntar_por_pagina(raiz: Path, registros: list[dict]):
    from pypdf import PdfWriter
    grupos={}
    for r in registros:
        if r['status'] not in ('OK','JÁ EXISTIA') or r['tipo'] == 'VOLUME':
            continue
        grupos.setdefault((r['recorte'],r['pagina']),[]).append(r)
    volumes=[]
    for (recorte,pagina),linhas in grupos.items():
        destino = raiz/recorte/'VOLUMES'/f'{pagina}.pdf'
        writer=PdfWriter()
        for r in linhas:
            caminho=raiz/r['arquivo']
            if caminho.is_file():
                writer.append(str(caminho))
        try:
            if len(writer.pages) == 0:
                continue
            destino.parent.mkdir(parents=True,exist_ok=True)
            with destino.open('wb') as f:writer.write(f)
            volumes.append({'recorte':recorte,'tipo':'VOLUME','pagina':pagina,'indicador':'',
                'variante':'','arquivo':str(destino.relative_to(raiz).as_posix()),
                'folhas':len(writer.pages),'status':'OK','erro':''})
            print(f'  Volume {recorte}/{pagina}: {len(writer.pages)} folhas')
        except Exception as e:
            volumes.append({'recorte':recorte,'tipo':'VOLUME','pagina':pagina,'indicador':'',
                'variante':'','arquivo':'','folhas':0,'status':'ERRO','erro':str(e)[:300]})
        finally:
            writer.close()
    return volumes


def juntar_relatorio_por_recorte(raiz: Path, registros: list[dict]):
    """Gera um PDF navegável por recorte com todos os indicadores já impressos.

    O PDF geral é apenas uma consolidação dos arquivos individuais, sem gráficos
    ou números recalculados. Um marcador por indicador/variante facilita a busca.
    """
    from pypdf import PdfWriter
    grupos = {}
    for r in registros:
        if (r['tipo'] == 'INDICADOR' and r['status'] in ('OK', 'JÁ EXISTIA')
                and r['arquivo']):
            grupos.setdefault(r['recorte'], []).append(r)
    gerais = []
    for recorte, itens in grupos.items():
        destino = raiz / recorte / f'RELATORIO_COMPLETO_{recorte}.pdf'
        writer = PdfWriter()
        try:
            for r in itens:
                origem = raiz / r['arquivo']
                if not origem.is_file():
                    continue
                inicio = len(writer.pages)
                writer.append(str(origem))
                etiqueta = r['indicador'] + (f" · {r['variante']}" if r['variante'] else '')
                writer.add_outline_item(etiqueta, inicio)
            if len(writer.pages) == 0:
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            with destino.open('wb') as f:
                writer.write(f)
            gerais.append({
                'recorte': recorte, 'tipo': 'RELATÓRIO', 'pagina': 'todas',
                'indicador': '', 'variante': '',
                'arquivo': destino.relative_to(raiz).as_posix(),
                'folhas': len(writer.pages), 'status': 'OK', 'erro': ''
            })
            print(f'  Relatório completo {recorte}: {len(writer.pages)} folhas — {destino}')
        except Exception as e:
            gerais.append({
                'recorte': recorte, 'tipo': 'RELATÓRIO', 'pagina': 'todas',
                'indicador': '', 'variante': '', 'arquivo': '',
                'folhas': 0, 'status': 'ERRO', 'erro': str(e)[:400]
            })
        finally:
            writer.close()
    return gerais


def main():
    p=argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--anos',nargs='+',default=['todos','2024'],
                   help='Ex.: --anos todos 2024 OU --anos todos 2019-2025 OU --anos 2025')
    p.add_argument('--uf',default='BR',choices=['BR'],help='UF fixa: BR = Todos os estados (Brasil).')
    p.add_argument('--modo',choices=['ambos','paginas','indicadores'],default='indicadores',
                   help='Padrão: indicadores; opcionalmente acrescente PDF geral por página.')
    p.add_argument('--indicadores',nargs='*',help='Filtro para teste: --indicadores 12 ou 1-8 12')
    p.add_argument('--sem-detalhes-ind012',action='store_true',
                   help='Gerar só C1 no IND-012; padrão exporta C1, C2, C3, C4 e C5.')
    p.add_argument('--sem-variante-980',action='store_true',
                   help='Ignorar a variante 980 do IND-034; padrão exporta ambas.')
    p.add_argument('--abas',choices=['ativa','todas'],default='todas',
                   help='Imprimir aba ativa ou todas as abas do indicador (padrão: todas)')
    p.add_argument('--url',default='http://localhost:8501')
    p.add_argument('--espera',type=int,default=1200,help='Tempo extra (ms) após carregar cada gráfico')
    p.add_argument('--timeout-carregamento', type=int, default=240, help='Segundos para os filtros carregarem; padrão 240')
    p.add_argument('--papel',choices=['A4','A3'],default='A4')
    p.add_argument('--retrato',action='store_true',help='PDF em modo retrato; padrão paisagem para gráficos')
    p.add_argument('--png',action='store_true',help='Salvar PNG de página inteira junto com PDFs')
    p.add_argument('--sem-juntar',action='store_true',help='Não consolidar PDFs por página')
    p.add_argument('--zip',action='store_true',help='Compactar todos os arquivos ao final (pode ser grande)')
    p.add_argument('--saida',type=Path,help='Pasta de saída; padrão fora do repositório')
    p.add_argument('--retomar',action='store_true',help='Ignorar PDFs já existentes e válidos na pasta --saida')
    p.add_argument('--visivel',action='store_true',help='Mostrar o navegador durante a automação')
    p.add_argument('--listar',action='store_true',help='Listar 68 IDs sem abrir o navegador')
    p.add_argument('--raiz',type=Path,help='Raiz do repositório com docs/catalogo_navegacao_68.json; padrão: pasta atual')
    args=p.parse_args()
    raiz=(args.raiz or Path.cwd()).resolve()
    if not (raiz/'docs'/'catalogo_navegacao_68.json').is_file() and args.raiz is None:
        raiz=Path(__file__).resolve().parent
    try:
        catalogo=carregar_catalogo(raiz)
        pistas_pedagogicas=carregar_pistas_pedagogicas(raiz)
        anos=interpretar_anos(args.anos)
        ids=interpretar_ids(args.indicadores)
        if ids is not None and not ids.issubset({x['numero'] for x in catalogo}):
            raise ValueError('Um ou mais indicadores informados não estão no catálogo dos 68.')
        if args.espera < 200:
            raise ValueError('--espera deve ser pelo menos 200 ms')
        if args.timeout_carregamento < 30:
            raise ValueError('--timeout-carregamento deve ser pelo menos 30 segundos')
        uf=args.uf.upper()
        if uf not in ('BR', 'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
                      'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'):
            raise ValueError('UF inválida.')
        if args.listar:
            for item in catalogo:
                print(f'{item["id"]} | {NAVEGACAO[item["pagina"]]} | {item["titulo"]}')
            return 0
        validar_url(args.url)
        from playwright.sync_api import sync_playwright
        from pypdf import PdfReader  # verifica dependências antes de iniciar
    except ImportError as e:
        print('ERRO: Instale playwright e pypdf com python -m pip install playwright pypdf',file=sys.stderr)
        print(e,file=sys.stderr)
        return 2
    except (ValueError,FileNotFoundError,RuntimeError) as e:
        print('ERRO:',e,file=sys.stderr)
        return 2

    timestamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    saida=(args.saida or (raiz.parent/'ENEM_EXPORTACOES'/f'captura_{timestamp}')).resolve()
    if saida == raiz or raiz in saida.parents:
        print('ERRO: Selecione uma pasta de saída FORA do repositório para não poluir o Git.',file=sys.stderr)
        return 2
    saida.mkdir(parents=True,exist_ok=True)
    registros=[]
    indicadores={r:[] for r in NAVEGACAO}
    for i in catalogo:
        if ids is None or i['numero'] in ids:
            indicadores[i['pagina']].append(i)
    rotas=[r for r in NAVEGACAO if args.modo != 'indicadores' or indicadores[r]]
    quantidade=sum(len(v) for v in indicadores.values())
    print(f'Início. Recortes={anos}; indicadores por recorte={quantidade}; modo={args.modo}; UF=Brasil')
    print(f'Destino: {saida} (fora do repositório).')

    with sync_playwright() as playwright:
        try:
            navegador=playwright.chromium.launch(channel='msedge',headless=not args.visivel)
            print('Navegador: Microsoft Edge.')
        except Exception:
            try:
                navegador=playwright.chromium.launch(headless=not args.visivel)
                print('Navegador: Chromium Playwright.')
            except Exception as erro_padrao:
                navegador_sistema=(os.environ.get('ENEM_CHROMIUM_PATH')
                    or shutil.which('chromium') or shutil.which('chromium-browser'))
                if not navegador_sistema:
                    print('ERRO: Navegador não encontrado. Execute: python -m playwright install chromium',file=sys.stderr)
                    print(str(erro_padrao)[:450],file=sys.stderr)
                    return 2
                navegador=playwright.chromium.launch(executable_path=navegador_sistema,
                                                     headless=not args.visivel)
                print('Navegador: Chromium do sistema.')
        ctx=navegador.new_context(viewport={'width':1560,'height':970},device_scale_factor=1,
                                  locale='pt-BR')
        for ano in anos:
            recorte=('todos_2019_2025' if ano=='Todos os anos' else ano)+'_'+uf
            print('\n=== '+recorte+' ===',flush=True)
            page=ctx.new_page()
            page.set_default_timeout(30000)
            try:
                page.goto(args.url, wait_until='domcontentloaded',timeout=80000)
                page.locator('[data-testid="stSidebar"]').wait_for(state='visible',timeout=80000)
                esperar_filtros(page, timeout_ms=args.timeout_carregamento*1000)
                aplicar_filtros(page,ano,uf)
                page.wait_for_timeout(args.espera)
            except Exception as e:
                registros.append({'recorte':recorte,'tipo':'FILTRO','pagina':'','indicador':'',
                                  'variante':'','arquivo':'','folhas':0,'status':'ERRO','erro':str(e)[:360]})
                print(f'ERRO no filtro {recorte}: {e}',file=sys.stderr)
                registrar_diagnostico_filtros(page, saida, recorte)
                page.close()
                continue
            for n,rota in enumerate(rotas,1):
                grupo=NAVEGACAO[rota]
                pasta_grupo=f'{list(NAVEGACAO).index(rota)+1:02d}_{slug(grupo)}'
                try:
                    navegar_pagina(page,grupo)
                    page.wait_for_timeout(args.espera)
                except Exception as e:
                    registros.append({'recorte':recorte,'tipo':'PÁGINA','pagina':pasta_grupo,
                                      'indicador':'','variante':'','arquivo':'','folhas':0,
                                      'status':'ERRO','erro':'Navegação: '+str(e)[:300]})
                    print(' ERRO ao abrir página',grupo,e,file=sys.stderr)
                    continue

                tarefas=[]
                if args.modo in ('paginas','ambos'):
                    tarefas.append(('PÁGINA',None, f'PAGINA_{pasta_grupo}.pdf'))
                if args.modo in ('indicadores','ambos'):
                    for item in indicadores[rota]:
                        tarefas.append(('INDICADOR',item,f'{item["id"]}_{slug(item["titulo"])}.pdf'))
                for tipo,item,nome in tarefas:
                    codigo=item['id'] if item else ''
                    arquivo_rel=Path(recorte)/pasta_grupo/nome
                    destino=saida/arquivo_rel
                    if args.retomar and caminho_disponivel(destino):
                        folhas=len(PdfReader(str(destino),strict=False).pages)
                        registros.append({'recorte':recorte,'tipo':tipo,'pagina':pasta_grupo,
                            'indicador':codigo,'variante':'','arquivo':arquivo_rel.as_posix(),
                            'folhas':folhas,'status':'JÁ EXISTIA','erro':''})
                        print(f'  [{codigo or "PÁGINA"}] já existe.',flush=True)
                        continue
                    try:
                        if item is not None:
                            navegar_indicador(page,item['numero'])
                            page.wait_for_timeout(args.espera)
                            # Quando o recorte global é histórico, o gráfico comparativo
                            # continua mostrando todos os anos. Padronizamos o detalhe
                            # de uma edição em 2024, se o seletor existir.
                            if ano == 'Todos os anos' and page.get_by_text(
                                    'Edição para visualizar os detalhes', exact=True).count():
                                selectbox(page,'Edição para visualizar os detalhes','2024')
                                page.wait_for_timeout(args.espera)
                        competencias = (['C1','C2','C3','C4','C5'] if
                           not args.sem_detalhes_ind012 and item is not None and item['numero']==12
                           else [''])
                        # A variante 980 é exportada em PDF próprio, mas cada
                        # variante continua pertencendo ao mesmo IND-034.
                        variantes = ['']
                        if (item is not None and item['numero'] == 34 and
                                not args.sem_variante_980 and
                                page.get_by_text('Variante do resultado', exact=True).count()):
                            # O st.selectbox usa format_func para mostrar nomes amigaveis.
                            # A selecao no Playwright precisa clicar o TEXTO VISIVEL,
                            # nao os nomes de arquivo Path usados internamente.
                            variantes = [
                                'Principal: competência única que impede 1000',
                                'Complemento: redações com 980 pontos',
                            ]
                        for variante in variantes:
                            if variante:
                                selectbox(page, 'Variante do resultado', variante)
                                page.wait_for_timeout(args.espera)
                            for comp in competencias:
                                if comp:
                                    selectbox(page,'Competência para distribuição de níveis',comp)
                                    page.wait_for_timeout(args.espera)
                                expandir_expanders(page)
                                page.wait_for_timeout(150)
                                abas=abas_disponiveis(page) if args.abas=='todas' else []
                                opcoes_abas=abas if len(abas)>1 else ['']
                                for indice,aba in enumerate(opcoes_abas):
                                    arq=arquivo_rel
                                    if variante:
                                        sufixo='_980' if '980' in variante else '_padrao'
                                        arq=arq.with_name(arq.stem+sufixo+'.pdf')
                                    if comp:
                                        arq=arq.with_name(arq.stem+f'_{comp}.pdf')
                                    if aba:
                                        arq=arq.with_name(arq.stem+f'_ABA{indice+1:02d}_{slug(aba)}.pdf')
                                        tabs=page.locator('[data-testid="stTabs"] [role="tab"]')
                                        if indice >= tabs.count():
                                            raise RuntimeError('O conjunto de abas mudou durante a captura.')
                                        tabs.nth(indice).click(timeout=13000)
                                        page.wait_for_timeout(200)
                                        expandir_expanders(page)
                                    caminho=saida/arq
                                    if args.retomar and caminho_disponivel(caminho):
                                        nfolhas=len(PdfReader(str(caminho),strict=False).pages)
                                        status='JÁ EXISTIA'
                                    else:
                                        nfolhas=imprimir_pdf(
                                             page,caminho,args.papel,not args.retrato,args.espera,
                                             codigo,comp,
                                             titulo=item.get('titulo','') if item else '',
                                             pergunta=item.get('pergunta','') if item else '',
                                             pista=pistas_pedagogicas.get(item['numero'],'') if item else '')
                                        if args.png:
                                            salvar_png(page,caminho.with_suffix('.png'))
                                        status='OK'
                                    registros.append({'recorte':recorte,'tipo':tipo,'pagina':pasta_grupo,
                                        'indicador':codigo,'variante':' '.join(x for x in (('980' if '980' in variante else ('padrao' if variante else '')),comp,aba) if x),
                                        'arquivo':arq.as_posix(),
                                        'folhas':nfolhas,'status':status,'erro':''})
                                    gerar_csv_html(saida,registros)
                                    etiqueta='980' if '980' in variante else (comp or 'principal')
                                    print(f'  [{codigo or "PÁGINA"}] {etiqueta} {aba or ""}: '
                                          f'{nfolhas} folha(s) {status}',flush=True)
                    except Exception as e:
                        erro=str(e)[:500]
                        registros.append({'recorte':recorte,'tipo':tipo,'pagina':pasta_grupo,
                            'indicador':codigo,'variante':'','arquivo':'','folhas':0,
                            'status':'ERRO','erro':erro})
                        print(f'  ERRO {codigo or "PÁGINA"}: {erro}',file=sys.stderr,flush=True)
                        try:page.screenshot(path=str(saida/recorte/f'ERRO_{codigo or pasta_grupo}.png'),
                                            full_page=False,timeout=16000)
                        except Exception:pass
                gerar_csv_html(saida,registros)
            page.close()
        ctx.close()
        navegador.close()

    if not args.sem_juntar:
        registros.extend(juntar_por_pagina(saida,registros))
        registros.extend(juntar_relatorio_por_recorte(saida,registros))
    gerar_csv_html(saida,registros)
    if args.zip:
        compactado=saida.with_suffix('.zip')
        with ZipFile(compactado,'w',ZIP_DEFLATED,compresslevel=2) as z:
            for arq in saida.rglob('*'):
                if arq.is_file():
                    z.write(arq,arq.relative_to(saida))
        print('ZIP:',compactado)
    erros=[r for r in registros if r['status']=='ERRO']
    print(f'\nFINAL: {len(registros)} registros, {len(erros)} falhas. Pasta: {saida}')
    print(f'Índice para abrir no navegador: {saida/"INDICE.html"}')
    return 1 if erros else 0


if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:
        print('\nInterrompido pelo usuário. PDFs já criados permanecem na pasta de saída.',file=sys.stderr)
        sys.exit(130)
