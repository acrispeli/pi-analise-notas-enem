#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pré-auditoria consolidada ENEM Lote 2, somente leitura, sem dependências adicionais.

Verifica disponibilidade, volume e marcas explícitas de supressão nos 32 CSVs ainda
não revisados pelo Lote 1. Não valida metodologias nem substitui a privacidade cruzada.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORRIGIDOS = {1,16,20,23,30,31,32,34,35,36,37,38,40,44,45,46,47,48,49,50,51,52}
RESTANTES = tuple(i for i in range(1,55) if i not in CORRIGIDOS)
MARCAS = re.compile(r"(?:suprimid|suprim[ia]|ocultad|mascarad|suppressed|1_a_29_suprimid)", re.I)
SINAL = re.compile(r"^(?:1|true|sim|yes)$", re.I)
INTEIRO = re.compile(r"^\+?\d+$")


def numero_coluna(c: str) -> bool:
    c = c.lower().strip()
    if c in {'n','quantidade','frequencia','contagem','n_amostra','n_redacoes','n_pares','n_grupo'}:
        return True
    return c.startswith(('n_', 'quantidade_', 'contagem_', 'frequencia_')) or c.endswith(('_quantidade','_contagem','_frequencia'))


def inspecionar(ident: int) -> dict:
    prefixo = f'IND_{ident:03d}_'
    fontes = sorted((ROOT/'src'/'indicadores').glob(prefixo+'*.py'))
    csvs = sorted((ROOT/'outputs'/'indicadores').glob(prefixo+'*.csv'))
    # IND-009 possui variante CORRIGIDO no ZIP: manter o arquivo realmente presente.
    res = {'n':ident, 'scripts':len(fontes), 'arquivos':len(csvs), 'linhas':0,
           'linhas_com_marca':0, 'celulas_com_marca':0,'contagens_1_29':0,
           'linhas_com_vazios':0,'colunas_marca':set(), 'erros':[]}
    if not fontes:res['erros'].append('SEM SCRIPT')
    if not csvs:res['erros'].append('SEM CSV')
    for path in csvs:
        try:
            with path.open('r', encoding='utf-8-sig', newline='') as arquivo:
                # Todos os CSVs deste projeto têm delimitador ';'.
                reader = csv.DictReader(arquivo, delimiter=';')
                colunas = reader.fieldnames or []
                if len(colunas) < 2:
                    res['erros'].append(f'{path.name}: CABEÇALHO')
                    continue
                cols_num = [c for c in colunas if numero_coluna(c)]
                cols_marca = [c for c in colunas if 'suprim' in c.lower() or 'ocult' in c.lower() or 'mascar' in c.lower()]
                res['colunas_marca'].update(cols_marca)
                for row in reader:
                    res['linhas']+=1
                    if any(v is None or not v.strip() for v in row.values()):
                        res['linhas_com_vazios']+=1
                    marcada = False
                    for campo,valor in row.items():
                        if campo is None or valor is None:continue
                        v=valor.strip()
                        eh_marca = MARCAS.search(v) is not None
                        if (campo in cols_marca and SINAL.match(v)) or eh_marca:
                            # Descarta somente os alertas metodológicos de revisão
                            # quando não se referem a célula/linha efetivamente oculta.
                            res['celulas_com_marca']+=1
                            marcada=True
                    if marcada:res['linhas_com_marca']+=1
                    for campo in cols_num:
                        v=(row.get(campo) or '').strip()
                        if INTEIRO.fullmatch(v) and 1 <= int(v) <= 29:
                            res['contagens_1_29']+=1
        except Exception as exc:
            res['erros'].append(f'{path.name}: {type(exc).__name__}: {str(exc)[:70]}')
    return res


def main() -> int:
    print('LOTE 2 | PRÉ-AUDITORIA DE SAÍDAS (somente leitura)')
    print('Referência: 32 indicadores ainda fora do Lote 1. Não reprocessa dados.')
    print(f"{'IND':>4} {'CSV':>3} {'LINHAS':>8} {'MARCAS(L)':>10} {'CONTAGENS1-29':>14} {'LINHAS_VAZIAS':>14}  AVISOS")
    print('-'*85)
    totais={'linhas':0,'linhas_com_marca':0,'contagens_1_29':0}
    falhas=[]
    marcados=[]
    for ident in RESTANTES:
        r=inspecionar(ident)
        for k in totais:totais[k]+=r[k]
        if r['linhas_com_marca']:marcados.append(ident)
        if r['erros']:falhas.append(ident)
        print(f"{ident:04d} {r['arquivos']:>3} {r['linhas']:>8} {r['linhas_com_marca']:>10} {r['contagens_1_29']:>14} {r['linhas_com_vazios']:>14}  {', '.join(r['erros']) or '-'}")
    print('-'*85)
    print('INDICADORES COBERTOS:',len(RESTANTES))
    print('LINHAS CSV:',totais['linhas'])
    print('LINHAS COM INDÍCIO EXPLÍCITO DE SUPRESSÃO:',totais['linhas_com_marca'])
    print('CONTAGENS POSITIVAS 1..29 EM CAMPOS NUMÉRICOS (ocorrências):',totais['contagens_1_29'])
    print('INDICADORES COM MARCA:', ', '.join(f'{i:03}' for i in marcados) or 'nenhum')
    print('INDICADORES COM ARQUIVOS AUSENTES/ERROS:', ', '.join(f'{i:03}' for i in falhas) or 'nenhum')
    print('\nATENÇÃO: ausência de marca explícita NÃO comprova ausência de supressão.')
    print('Os limites de treinamento/validade estatística de PCA, MCA, K-Means e Kappa são avaliados separadamente.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
