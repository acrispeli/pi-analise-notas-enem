#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria de leitura dos IND-064..067 e 069..072 do ENEM/UNIVESP.

Não lê microdados; não altera CSV/JSON/dashboards. Audita integridade, cálculo
interno, séries derivadas, cobertura e hashes. O relatório fica fora de outputs.
Não substitui recálculo independente, auditoria metodológica ou de privacidade.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

IDS = (69, 70, 64, 65, 66, 67, 71, 72)
ANOS = tuple(range(2019, 2026))
COLUNAS_PEQUENAS = {'quantidade', 'n_redacoes_bin', 'n_com_desconto', 'n_sem_desconto',
                    'n_ambos', 'n_com_av3', 'n_sem_av3', 'n_com_av4', 'n_sem_av4', 'n_cluster'}

class Auditoria:
    def __init__(self, root):
        self.root = root
        self.failures = []
        self.alerts = []
        self.count = 0
        self.summary = {}
        self.docs = {}
        self.rows = {}

    def assert_(self, test, description):
        self.count += 1
        if not test:
            self.failures.append(description)

    def alert(self, message):
        if message not in self.alerts:
            self.alerts.append(message)

    def locate(self, ident, suffix):
        folder = self.root / ('outputs/indicadores' if suffix == 'csv' else 'outputs/json')
        items = sorted(folder.glob(f'IND_{ident:03d}_*.{suffix}'))
        self.assert_(len(items) == 1, f'IND-{ident:03d}: esperado 1 {suffix}, encontrados {len(items)}')
        return items[0] if len(items) == 1 else None

    @staticmethod
    def csvread(path):
        with path.open('r', encoding='utf-8-sig', newline='') as fp:
            reader = csv.DictReader(fp, delimiter=';')
            if not reader.fieldnames:
                raise ValueError('CSV sem cabeçalho')
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError('CSV com cabeçalhos duplicados')
            data = list(reader)
            if any(None in r for r in data):
                raise ValueError('CSV com excesso de colunas')
        return data

    @staticmethod
    def number(value):
        if value is None or value == '':
            return None
        num = float(value)
        if not math.isfinite(num):
            raise ValueError(f'Número não finito: {value!r}')
        return num

    @staticmethod
    def integer(value):
        val = Auditoria.number(value)
        if val is None:
            return None
        if int(val) != val:
            raise ValueError(f'Contagem fracionária: {val}')
        return int(val)

    @staticmethod
    def close(a, b, tol=1e-6):
        a, b = Auditoria.number(a), Auditoria.number(b)
        if a is None or b is None:
            return a is None and b is None
        return abs(a-b) <= tol + 1e-9 * max(abs(a), abs(b))

    @staticmethod
    def text(value):
        if value is None:
            return ''
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def read_indicator(self, ident):
        pathc = self.locate(ident, 'csv')
        pathj = self.locate(ident, 'json')
        if not (pathc and pathj):
            return
        try:
            rows = self.csvread(pathc)
            doc = json.loads(pathj.read_text(encoding='utf-8-sig'))
            jsonrows = doc['results']
            self.assert_(isinstance(jsonrows, list) and bool(jsonrows), f'IND-{ident:03d}: resultados JSON vazios')
            self.assert_(len(rows) == len(jsonrows), f'IND-{ident:03d}: CSV/JSON divergem em N linhas')
            self.assert_(doc.get('indicator_id') == f'IND-{ident:03d}', f'IND-{ident:03d}: ID incorreto')
            self.assert_(doc.get('status') == 'draft', f'IND-{ident:03d}: status inesperado')
            if rows and jsonrows:
                expected_fields = set().union(*(r.keys() for r in jsonrows))
                self.assert_(set(rows[0]) == expected_fields, f'IND-{ident:03d}: colunas CSV/JSON diferentes')
                for i, (r, j) in enumerate(zip(rows, jsonrows), 1):
                    self.assert_(set(j).issubset(set(r)), f'IND-{ident:03d}: linha {i} com coluna JSON ausente no CSV')
                    for key, value in j.items():
                        self.assert_(r.get(key) == self.text(value),
                                     f'IND-{ident:03d}: linha {i}, coluna {key}: CSV != JSON')
            self.rows[ident] = rows
            self.docs[ident] = doc
            self.summary[f'IND-{ident:03d}'] = {'linhas_csv': len(rows), 'colunas_csv': len(rows[0]) if rows else 0,
                                                 'csv': pathc.name, 'json': pathj.name}
            print(f'IND-{ident:03d}: {len(rows)} linhas, CSV/JSON lidos')
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.assert_(False, f'IND-{ident:03d}: falha ao ler arquivos: {type(exc).__name__}: {exc}')

    def find_source(self, ident):
        path = self.locate(ident, 'csv')
        if path is None:
            return []
        try:
            return self.csvread(path)
        except Exception as exc:
            self.assert_(False, f'Fonte IND-{ident:03d}: {exc}')
            return []

    @staticmethod
    def source_year(r):
        period = str(r.get('periodo', r.get('ano', '')))
        return int(period) if re.fullmatch(r'20\d\d', period) else None

    def source_br(self, ident):
        return [r for r in self.find_source(ident)
                if r.get('uf', 'BR') == 'BR' and self.source_year(r) in ANOS]

    def check_069(self):
        rows = self.rows.get(69, [])
        yearrows = {int(r['ano']): r for r in rows if str(r.get('ano', '')).isdigit()}
        self.assert_(len(rows) == 7 and set(yearrows) == set(ANOS), 'IND-069: cobertura 2019–2025')
        for year in ANOS:
            r = yearrows.get(year)
            if not r: continue
            status = r.get('status')
            if year == 2025:
                self.assert_(status == 'nao_aplicavel', 'IND-069: 2025 não deve presumir vínculo por inscrição')
                continue
            self.assert_(status == 'ok', f'IND-069/{year}: junção indisponível ou status {status}')
            if status != 'ok': continue
            try:
                def n(x): return self.integer(r[x])
                m, l, rr = n('matched'), n('left_only'), n('right_only')
                ld, rd = n('esq_n_distintas'), n('dir_n_distintas')
                self.assert_(m >= 0 and l >= 0 and rr >= 0, f'IND-069/{year}: contagem negativa')
                self.assert_(m+l == ld and m+rr == rd, f'IND-069/{year}: partições de junção não fecham')
                self.assert_(m <= min(ld, rd), f'IND-069/{year}: matches acima das chaves distintas')
                for pref in ('esq', 'dir'):
                    self.assert_(n(f'{pref}_n_lidas') == n(f'{pref}_n_distintas') +
                                 n(f'{pref}_n_chaves_vazias') + n(f'{pref}_n_duplicadas'),
                                 f'IND-069/{year}: reconciliação de chaves {pref}')
                    self.assert_(n(f'{pref}_n_ano_divergente') == 0, f'IND-069/{year}: ano divergente {pref}')
                    self.assert_(n(f'{pref}_n_chaves_vazias') == 0 and n(f'{pref}_n_duplicadas') == 0,
                                 f'IND-069/{year}: duplicação/vazios {pref}')
                self.assert_(self.close(r['taxa_esquerda_pct'], 100*m/ld if ld else None, 0.000002),
                             f'IND-069/{year}: taxa de junção inconsistente')
                if m < ld or m < rd:
                    self.alert(f'IND-069/{year}: existem chaves sem par; exige interpretação dos recortes')
            except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
                self.assert_(False, f'IND-069/{year}: {exc}')

    def check_070(self):
        rows = self.rows.get(70, [])
        keys = set()
        years = set()
        for i, r in enumerate(rows, 1):
            try:
                ano = self.integer(r['ano'])
                years.add(ano)
                if r['status'] != 'ok':
                    self.alert(f'IND-070/{ano}: registro de indisponibilidade: {r.get("motivo", "")[:120]}')
                    continue
                key = (ano, r['fonte'], r['populacao'], r['variavel'])
                self.assert_(key not in keys, f'IND-070: variável duplicada {key}')
                keys.add(key)
                total, missing = self.integer(r['n_linhas']), self.integer(r['n_ausentes'])
                self.assert_(total is not None and total > 0 and missing is not None and 0 <= missing <= total,
                             f'IND-070/{i}: denominador/ausência inválidos')
                if total:
                    self.assert_(self.close(r['percentual_ausente'], 100*missing/total, 0.000002),
                                 f'IND-070/{i}: percentual não confere')
            except (KeyError, ValueError, TypeError) as exc:
                self.assert_(False, f'IND-070/{i}: {exc}')
        self.assert_(years == set(ANOS), f'IND-070: anos representados {sorted(years)}')
        self.assert_(bool(keys), 'IND-070: nenhum registro válido')

    def check_temporals(self):
        plans = {
            64: (2, 3, ('n_validas', 'media', 'mediana')),
            65: (9, 10, ('n_validas', 'media', 'mediana')),
            66: (31, 32, ('n_near', 'perda_media', 'frequencia_desconto', 'n_com_desconto')),
            67: (20, 22, ('n_pareadas', 'diferenca_media_absoluta', 'diferenca_mediana_absoluta',
                          'percentual_discrepancia_confirmada', 'n_indeterminada')),
        }
        for ind, (a_id, b_id, metrics) in plans.items():
            results = self.rows.get(ind, [])
            a = self.source_br(a_id)
            b = self.source_br(b_id)
            ai = {}
            bi = {}
            for r in a:
                if ind == 66 and r.get('faixa') != 'POP_NEAR_TOTAL': continue
                key = (self.source_year(r), r.get('competencia')) if ind in (65, 66) else (self.source_year(r),)
                if ind == 67 and key in ai:
                    for col in ('n_avaliacoes_pareadas', 'media', 'mediana'):
                        self.assert_(r[col] == ai[key][col], f'IND-020/{key}: histograma inconsistente na fonte')
                ai[key] = r
            for r in b:
                key = (self.source_year(r), r.get('competencia')) if ind in (65, 66) else (self.source_year(r),)
                bi[key] = r
            required = {(year, comp) for year in ANOS for comp in ('C1','C2','C3','C4','C5')} if ind in (65,66) else {(year,) for year in ANOS}
            found = set()
            for i,r in enumerate(results,1):
                try:
                    key = (self.integer(r['ano']), r.get('competencia')) if ind in (65,66) else (self.integer(r['ano']),)
                    self.assert_(key not in found, f'IND-{ind:03d}: chave duplicada {key}')
                    found.add(key)
                    self.assert_(key in required, f'IND-{ind:03d}: chave fora de escopo {key}')
                    if r.get('status') != 'ok':
                        self.alert(f'IND-{ind:03d}/{key}: série com status {r.get("status")}')
                        continue
                    s, t = ai[key], bi[key]
                    expected = (
                        {'n_validas': s['n_validas'], 'media': s['nota_media'], 'mediana': t['nota_mediana']} if ind == 64 else
                        {'n_validas': s['n_validas'], 'media': s['media'], 'mediana': t['mediana']} if ind == 65 else
                        {'n_near': s['n_redacoes'], 'perda_media': s['media_perda'],
                         'frequencia_desconto': t['frequencia_desconto'], 'n_com_desconto': t['n_com_desconto']} if ind == 66 else
                        {'n_pareadas': s['n_avaliacoes_pareadas'], 'diferenca_media_absoluta': s['media'],
                         'diferenca_mediana_absoluta': s['mediana'],
                         'percentual_discrepancia_confirmada': t['percentual_discrepancia_confirmada_pop_evaluator'],
                         'n_indeterminada': t['n_indeterminada']}
                    )
                    for k in metrics:
                        self.assert_(self.close(r[k], expected[k]), f'IND-{ind:03d}/{key}: {k} difere da fonte')
                    denominator_a = s['n_validas'] if ind in (64,65) else s['n_redacoes'] if ind == 66 else s['n_avaliacoes_pareadas']
                    denominator_b = t['n_validas'] if ind in (64,65) else t['n_redacoes'] if ind == 66 else t['n_pop_evaluator']
                    self.assert_(self.close(denominator_a, denominator_b), f'IND-{ind:03d}/{key}: N das fontes diverge')
                except (KeyError, ValueError, TypeError) as exc:
                    self.assert_(False, f'IND-{ind:03d}/linha {i}: {exc}')
            self.assert_(found == required, f'IND-{ind:03d}: cobertura das chaves ano/competência incompleta')

    def check_071(self):
        rows = self.rows.get(71, [])
        actual = {r.get('fonte_csv'):r for r in rows}
        self.assert_(len(rows) == len(actual), 'IND-071: fontes repetidas')
        expected = {}
        for path in sorted((self.root/'outputs/indicadores').glob('IND_*.csv')):
            if path.name.startswith('IND_071_'):continue
            m = re.match(r'IND_(\d{3})_',path.name)
            if not m:continue
            with path.open('r', encoding='utf-8-sig', newline='') as fp:
                reader = csv.DictReader(fp,delimiter=';')
                cols = [c for c in (reader.fieldnames or []) if c in COLUNAS_PEQUENAS]
                if not cols:continue
                nrows = positive = zeros = small = 0
                minimum = None
                for r in reader:
                    nrows += 1
                    for col in cols:
                        try:val = int(r.get(col,''))
                        except (TypeError,ValueError):continue
                        if val == 0:zeros += 1
                        if val > 0:
                            positive += 1
                            if val < 30:
                                small += 1
                                minimum = val if minimum is None else min(minimum,val)
                expected[path.name] = (nrows,positive,zeros,small,minimum)
        self.assert_(set(actual)==set(expected), 'IND-071: inventário de CSVs diverge das fontes auditáveis')
        for name,(n,p,z,s,minimum) in expected.items():
            r=actual.get(name)
            if not r:continue
            for col,val in [('n_linhas',n),('celulas_contadas_positivas',p),('contagens_zero',z),
                            ('celulas_positivas_1_a_29',s),('menor_contagem_positiva',minimum)]:
                self.assert_(self.close(r.get(col),val),f'IND-071/{name}: {col} inconsistente')
            self.assert_(r.get('tratamento')=='auditoria_sem_supressao_automatica',
                         f'IND-071/{name}: política de divulgação alterada')
        self.summary['IND-071']['grupos_pequenos_detectados'] = sum(s for _,_,_,s,_ in expected.values())
        if self.summary['IND-071']['grupos_pequenos_detectados']:
            self.alert('IND-071: existem agregados 1–29; revisão de privacidade cruzada obrigatória antes da publicação')

    @staticmethod
    def hashfile(path):
        h=hashlib.sha256()
        with path.open('rb') as fp:
            while chunk := fp.read(2*1024*1024): h.update(chunk)
        return h.hexdigest()

    def check_072(self):
        rows = self.rows.get(72, [])
        paths=[]
        for folder,pattern in [('outputs/json','*.json'),('outputs/indicadores','*.csv')]:
            for p in sorted((self.root/folder).glob(pattern)):
                if p.name.startswith(('IND_','dashboard_enem_')) and not p.name.startswith('IND_072'):
                    paths.append(p.relative_to(self.root).as_posix())
        declared={r.get('arquivo'):r for r in rows}
        self.assert_(len(declared) == len(rows), 'IND-072: arquivo duplicado na proveniência')
        self.assert_(set(paths)==set(declared), 'IND-072: inventário de saídas não representa o estado do projeto')
        for rel in paths:
            r = declared.get(rel)
            if not r:continue
            p = self.root/rel
            self.assert_(self.integer(r.get('tamanho_bytes'))==p.stat().st_size,
                         f'IND-072/{rel}: tamanho mudou após registro de proveniência')
            self.assert_(r.get('sha256')==self.hashfile(p),f'IND-072/{rel}: hash mudou após proveniência')
        self.assert_(bool(self.docs.get(72,{}).get('meta',{}).get('git_commit')),
                     'IND-072: hash do commit Git ausente')
        self.alert('IND-072: hashes registram arquivos gerados, mas não comprovam validade dos microdados de origem')

    def save(self):
        dest=self.root/'auditorias_lote3'
        dest.mkdir(parents=True, exist_ok=True)
        output=dest/'auditoria_pos_lote3.json'
        obj={'auditoria':'IND-064-067_069-072','executada_em_utc':datetime.now(timezone.utc).isoformat(),
             'escopo':'somente leitura de outputs CSV/JSON; sem recálculo dos microdados',
             'indicadores_presentes':len(self.docs),'indicadores_esperados':len(IDS),
             'checagens':self.count,'falhas':len(self.failures),'alertas':len(self.alerts),
             'detalhes_falhas':self.failures[:300], 'detalhes_alertas':self.alerts[:100],
             'resumo':self.summary,
             'parecer':'SEM_FALHAS_NAS_CHECAGENS_EXECUTADAS' if not self.failures else 'FALHAS_DETECTADAS',
             'limites':'sem auditoria de microdados, desempenho de modelos, metodologia ou privacidade cruzada; status draft'}
        output.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('RELATÓRIO:',output)
        print(f'FIM: indicadores={len(self.docs)}/{len(IDS)}; checagens={self.count}; falhas={len(self.failures)}; alertas={len(self.alerts)}')
        for item in self.failures[:12]:print('FALHA:',item)
        for item in self.alerts[:12]:print('ALERTA:',item)
        print('PARECER:',obj['parecer'],'— revisão metodológica/privacidade pendente')
        return 1 if self.failures else 0

    def run(self):
        print('AUDITORIA PÓS-LOTE 3 — SEM MICRODADOS; resultados mantidos em draft')
        print('RAIZ:',self.root)
        for ident in IDS:self.read_indicator(ident)
        for ident,action in [('IND-069',self.check_069),('IND-070',self.check_070),
                             ('IND-064/067',self.check_temporals),('IND-071',self.check_071),
                             ('IND-072',self.check_072)]:
            try:action()
            except Exception as exc:self.assert_(False, f'{ident}: auditoria não concluída: {type(exc).__name__}: {exc}')
        return self.save()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    raise SystemExit(Auditoria(args.raiz.resolve()).run())
