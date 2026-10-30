#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IND-033 | Participação de cada competência na perda total até 1000 — ENEM.

Projeto Integrador IV — UNIVESP | Catálogo de Indicadores ENEM 2019–2025 v2.

População: POP_NEAR, redações válidas com nota final de 900 a 980,
inclusive, já selecionadas e auditadas pelo IND-031.

Definição por redação: perda_i = 200 - NU_NOTA_COMPi; perda_total = sum(perda_i).
Participação ponderada por ano/UF:
    share_i = sum(perda_i) / sum(perda_1 + ... + perda_5).

Esta é a média dos percentuais individuais ponderada pela perda total de
cada redação. NÃO é a média aritmética dos percentuais individuais.
A soma das cinco participações equivale a 100% (sem arredondamento).

O IND-031 já contém as somas exatas das perdas para a mesma população,
por competência, ano e UF. Portanto este gerador deriva o IND-033 dos
agregados IND-031 sem nova leitura de microdados ou nova junção em 2024.
A validade das somas e das relações nota/competências depende da validação
prévia do IND-031; este script verifica adicionalmente seus fechamentos.

Fontes:
  outputs/json/dashboard_enem_<ano>.json
  pages.high_performance.loss_by_competency (IND-031).

Saídas:
  outputs/json/IND_033_participacao_perda_total.json
  outputs/indicadores/IND_033_participacao_perda_total.csv
  outputs/json/dashboard_enem_<ano>.json  [pages.high_performance.loss_share]

Uso na raiz do repositório:
  python src/indicadores/IND_033_participacao_perda_total.py --anos 2024 --sobrescrever
  python src/indicadores/IND_033_participacao_perda_total.py --sobrescrever
  python src/indicadores/IND_033_participacao_perda_total.py --anos 2024 --somente-modulo --sobrescrever

2025 será registrado como indisponível enquanto não houver dashboard
contendo IND-031 real. A ausência de outros anos solicitados gera erro.
Não cria arquivos .bak. A escrita é atômica por arquivo, sem backup.
Resultados em fase draft: revisão acadêmica e de privacidade cruzada pendentes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import tempfile
from typing import Any

ANOS = tuple(range(2019, 2026))
UFS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS',
       'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC',
       'SE', 'SP', 'TO')
COMPETENCIAS = tuple(f'C{i}' for i in range(1, 6))
MIN_N = 30
CAMPOS_CSV = (
    'ano', 'uf', 'competencia', 'n_near', 'soma_pontos_perdidos',
    'total_pontos_perdidos', 'participacao_perda_total',
    'percentual_participacao', 'media_perda', 'suprimido', 'motivo_supressao',
)


def raiz_projeto() -> Path:
    arq = Path(__file__).resolve()
    if arq.parent.name.lower() == 'indicadores' and arq.parent.parent.name.lower() == 'src':
        return arq.parents[2]
    return Path.cwd().resolve()


def carregar_json(caminho: Path) -> dict:
    with caminho.open('r', encoding='utf-8-sig') as f:
        documento = json.load(f)
    if not isinstance(documento, dict):
        raise ValueError(f'{caminho}: documento JSON inválido (objeto esperado).')
    return documento


def decimal_positivo(valor: Any, rotulo: str) -> Decimal:
    """Rejeita nulos, NaN, infinitos, negativos e booleanos."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f'{rotulo}: valor numérico ausente ou inválido: {valor!r}.')
    try:
        dec = Decimal(str(valor))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f'{rotulo}: número inválido: {valor!r}.') from e
    if not dec.is_finite() or dec < 0:
        raise ValueError(f'{rotulo}: valor negativo ou não finito: {valor!r}.')
    return dec


def inteiro_nao_negativo(valor: Any, rotulo: str) -> int:
    d = decimal_positivo(valor, rotulo)
    if d != d.to_integral_value():
        raise ValueError(f'{rotulo}: quantidade não inteira: {valor!r}.')
    return int(d)


def perdas_por_competencia(recorte: dict, ano: int, uf: str) -> tuple[int, dict[str, Decimal]]:
    contexto = f'IND-031/{ano}/{uf}'
    if not isinstance(recorte, dict):
        raise ValueError(f'{contexto}: recorte inválido.')
    if recorte.get('populacao') != 'POP_NEAR' or recorte.get('intervalo_nota') != [900, 980]:
        raise ValueError(f'{contexto}: população ou intervalo diferente de POP_NEAR [900,980].')
    n = inteiro_nao_negativo(recorte.get('n_near'), f'{contexto}/n_near')
    itens = recorte.get('resumo_competencias')
    if not isinstance(itens, list) or len(itens) != 5:
        raise ValueError(f'{contexto}: são necessárias exatamente cinco competências.')
    perdas = {}
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError(f'{contexto}: competência com formato inválido.')
        cod = item.get('competencia')
        if cod not in COMPETENCIAS or cod in perdas:
            raise ValueError(f'{contexto}: competência inválida/duplicada: {cod!r}.')
        if inteiro_nao_negativo(item.get('n_redacoes'), f'{contexto}/{cod}/n_redacoes') != n:
            raise ValueError(f'{contexto}/{cod}: denominador incompatível com POP_NEAR.')
        perda = decimal_positivo(item.get('soma_pontos_perdidos'),
                                 f'{contexto}/{cod}/soma_pontos_perdidos')
        if perda > Decimal(200) * n:
            raise ValueError(f'{contexto}/{cod}: perda maior que 200 por redação.')
        perdas[cod] = perda
        if n:
            media = decimal_positivo(item.get('media_perda'), f'{contexto}/{cod}/media_perda')
            if abs(media - perda / n) > Decimal('0.00002'):
                raise ValueError(f'{contexto}/{cod}: média e soma de perdas inconsistentes.')
        elif perda:
            raise ValueError(f'{contexto}/{cod}: grupo vazio com perdas positivas.')

    total = sum(perdas.values(), Decimal(0))
    # Cada nota entre 900 e 980 fica de 20 a 100 pontos abaixo de 1000.
    # Para dados coerentes, soma(perdas_i) = soma(1000 - nota_final).
    if n and not (Decimal(20)*n <= total <= Decimal(100)*n):
        raise ValueError(f'{contexto}: perda total incompatível com notas de 900 a 980.')
    if n == 0 and total:
        raise ValueError(f'{contexto}: perda positiva em grupo vazio.')

    # Auditoria adicional: as somas por faixas do IND-031 devem fechar.
    faixas = recorte.get('faixas')
    if faixas is not None:
        if not isinstance(faixas, list):
            raise ValueError(f'{contexto}: faixas não são lista.')
        if sum(inteiro_nao_negativo(f.get('n_redacoes'), f'{contexto}/faixa/n')
               for f in faixas) != n:
            raise ValueError(f'{contexto}: somatório das faixas difere de n_near.')
        for cod in COMPETENCIAS:
            total_faixas = Decimal(0)
            for faixa in faixas:
                campos = faixa.get('competencias')
                if not isinstance(campos, list):
                    raise ValueError(f'{contexto}: faixa sem competências.')
                # O IND-031 pode representar uma faixa com N=0 por lista vazia.
                # Ela não contribui para as perdas, mas precisa continuar no
                # somatório de N, validado acima. Não aceitar essa exceção
                # quando houver redações: continuam obrigatórias C1..C5.
                n_faixa = inteiro_nao_negativo(
                    faixa.get('n_redacoes'), f'{contexto}/faixa/n')
                if n_faixa == 0 and not campos:
                    continue
                encontrados = [x for x in campos if x.get('competencia') == cod]
                if len(encontrados) != 1:
                    raise ValueError(f'{contexto}/{cod}: faixa com competência ausente/duplicada.')
                total_faixas += decimal_positivo(encontrados[0].get('soma_pontos_perdidos'),
                                                f'{contexto}/{cod}/faixas')
            if total_faixas != perdas[cod]:
                raise ValueError(f'{contexto}/{cod}: soma das faixas difere da soma geral.')
    return n, perdas


def avaliar_fonte(ano: int, origem: dict) -> tuple[dict, dict]:
    """Lê e audita a saída IND-031; mantém Decimal apenas internamente."""
    if origem.get('meta', {}).get('year') != ano:
        raise ValueError(f'{ano}: ano do dashboard não corresponde ao arquivo.')
    bloco = (origem.get('pages', {}).get('high_performance', {})
             .get('loss_by_competency'))
    if not isinstance(bloco, dict) or bloco.get('indicator_id') != 'IND-031':
        raise ValueError(f'{ano}: indicador IND-031 ausente em pages.high_performance.loss_by_competency.')
    validacao = origem.get('quality', {}).get('ind031_validation', {})
    if isinstance(validacao, dict) and validacao:
        if validacao.get('perdas_somam_distancia_1000') is False:
            raise ValueError(f'{ano}: o IND-031 declara divergência entre perdas e distância até 1000.')
        if validacao.get('status') not in (None, 'ok', 'ok_agregados'):
            raise ValueError(f'{ano}: validação do IND-031 não está aprovada.')

    brasil = bloco.get('brasil')
    ufs = bloco.get('by_uf')
    if not isinstance(ufs, list) or len(ufs) != len(UFS):
        raise ValueError(f'{ano}: IND-031 deve conter as 27 UFs uma vez cada.')
    mapa = {'BR': brasil}
    for r in ufs:
        if not isinstance(r, dict):
            raise ValueError(f'{ano}: recorte por UF inválido.')
        uf = r.get('uf')
        if uf not in UFS or uf in mapa:
            raise ValueError(f'{ano}: UF inválida ou duplicada em IND-031: {uf!r}.')
        mapa[uf] = r
    if set(mapa) != {'BR', *UFS}:
        raise ValueError(f'{ano}: faltam UFs em IND-031.')
    bruto = {uf: perdas_por_competencia(mapa[uf], ano, uf) for uf in ('BR', *UFS)}
    n_br, per_br = bruto['BR']
    if sum(bruto[uf][0] for uf in UFS) != n_br:
        raise ValueError(f'{ano}: população BR não fecha com 27 UFs.')
    for cod in COMPETENCIAS:
        if sum((bruto[uf][1][cod] for uf in UFS), Decimal(0)) != per_br[cod]:
            raise ValueError(f'{ano}/{cod}: perdas no Brasil não fecham com as 27 UFs.')
    if validacao and validacao.get('n_near_brasil') is not None:
        if inteiro_nao_negativo(validacao['n_near_brasil'], f'{ano}/quality/n_near') != n_br:
            raise ValueError(f'{ano}: N_BR diferente da validação IND-031.')

    return bruto, {'ind031': 'aprovado_agregados',
                   'soma_27_ufs_igual_brasil': True,
                   'cinco_competencias_presentes': True,
                   'perdas_faixas_fecham': True,
                   'populacao': 'POP_NEAR',
                   'metodo': 'derivacao_exata_dos_totais_ind031'}


def calcular_recortes(bruto: dict, ano: int) -> tuple[dict, dict]:
    """Exibe agregados sem ocultar os recortes de 1 a 29 redações.

    A proteção cruzada NÃO está resolvida: os dados-base IND-031 também são
    divulgados, e requerem avaliação conjunta de privacidade.
    """
    pequenas = []
    ocultas = set()
    complementares = []

    recortes = {}
    for uf in ('BR', *UFS):
        n, perdas = bruto[uf]
        total = sum(perdas.values(), Decimal(0))
        motivo = ('primaria_n_menor_30' if uf in pequenas else
                  'complementar' if uf in complementares else None)
        # Recortes vazios são exibidos sem participações (não dividimos por zero).
        oculto = uf in ocultas
        resumo = []
        for cod in COMPETENCIAS:
            perda = perdas[cod]
            resumo.append({
                'competencia': cod,
                'n_redacoes': None if oculto else n,
                'soma_pontos_perdidos': None if oculto else float(perda),
                'total_pontos_perdidos': None if oculto else float(total),
                'participacao_perda_total': None if oculto or total == 0 else round(float(perda / total), 9),
                'percentual_participacao': None if oculto or total == 0 else round(float(100*perda / total), 6),
                'media_perda': None if oculto or n == 0 else round(float(perda / n), 6),
                'suprimido': oculto,
                'motivo_supressao': motivo,
            })
        if not oculto and total and abs(sum(it['percentual_participacao'] for it in resumo)-100) > 0.00001:
            raise ValueError(f'{ano}/{uf}: participações arredondadas não somam aproximadamente 100%.')
        recortes[uf] = {
            'uf': uf, 'populacao': 'POP_NEAR', 'intervalo_nota': [900, 980],
            'n_near': None if oculto else n,
            'total_pontos_perdidos': None if oculto else float(total),
            'resumo_competencias': resumo,
            'status_publicacao': 'revisao_academica_e_privacidade_pendente',
            'suprimido': oculto,
            'motivo_supressao': motivo,
            'sem_dados_individuais': True,
        }
    return recortes, {
        'n_recortes_suprimidos': len(ocultas),
        'n_supressoes_primarias': len(pequenas),
        'n_supressoes_complementares': len(complementares),
        'revisao_privacidade_cruzada_pendente': True,
    }


def salvar_json_atomico(arquivo: Path, payload: dict) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=arquivo.parent, encoding='utf-8',
                                         prefix=arquivo.name+'.', suffix='.tmp',
                                         delete=False) as f:
            temporario = Path(f.name)
            json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write('\n')
        os.replace(temporario, arquivo)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def salvar_csv_atomico(arquivo: Path, linhas: list[dict]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=arquivo.parent, encoding='utf-8-sig',
                                         newline='', prefix=arquivo.name+'.',
                                         suffix='.tmp', delete=False) as f:
            temporario = Path(f.name)
            escritor = csv.DictWriter(f, fieldnames=CAMPOS_CSV, delimiter=';',
                                      extrasaction='ignore')
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(temporario, arquivo)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def preparar_dashboard(doc: dict, ano: int, dado: dict) -> dict:
    pagina = doc.get('pages', {}).get('high_performance')
    if not isinstance(pagina, dict):
        raise ValueError(f'{ano}: pages.high_performance ausente ou inválido.')
    rec = dado['recortes']
    pagina['loss_share'] = {
        'indicator_id': 'IND-033',
        'population': 'POP_NEAR',
        'year': ano,
        'status': 'draft',
        'method': 'sum(200-Ci) / sum_j sum(200-Cj), por ano/UF; derivado de IND-031',
        'brasil': rec['BR'],
        'by_uf': [rec[uf] for uf in UFS],
        'privacy_note': ('Participações derivadas das perdas do IND-031; publicação '
                         'sujeita a revisão acadêmica e de privacidade cruzada.'),
    }
    qualidade = doc.setdefault('quality', {})
    qualidade['ind033_validation'] = {
        **dado['validacao'], **dado['privacidade'],
        'status': 'ok_agregados',
        'n_near_brasil': rec['BR']['n_near'],
        'soma_participacoes_aproximadamente_100': True,
        'revisao_academica_pendente': True,
    }
    avisos = doc.setdefault('meta', {}).setdefault('warnings', [])
    aviso = ('IND-033: participação ponderada na perda total derivada do IND-031; '
             'revisão acadêmica e de privacidade cruzada pendentes.')
    if aviso not in avisos:
        avisos.append(aviso)
    return doc


def executar(base: Path, saida: Path, anos: tuple[int, ...],
             sobrescrever: bool = False, somente_modulo: bool = False,
             exigir_2025: bool = False) -> dict:
    base = base.resolve()
    saida = saida.resolve()
    caminho_json = saida/'outputs'/'json'/'IND_033_participacao_perda_total.json'
    caminho_csv = saida/'outputs'/'indicadores'/'IND_033_participacao_perda_total.csv'
    if not sobrescrever and (caminho_json.exists() or caminho_csv.exists()):
        raise FileExistsError('Os resultados do IND-033 já existem. Use --sobrescrever.')

    # Permite reprocessar apenas 2024 sem apagar anos previamente gerados.
    anteriores = {}
    if sobrescrever and caminho_json.exists():
        velho = carregar_json(caminho_json)
        if velho.get('indicator_id') != 'IND-033':
            raise ValueError('Arquivo de saída existente não pertence ao IND-033.')
        anteriores = dict(velho.get('years', {}))

    dados_anos = dict(anteriores)
    processados = {}
    dashboards_para_atualizar = {}
    for ano in anos:
        arq = base/'outputs'/'json'/f'dashboard_enem_{ano}.json'
        print(f'IND-033 | {ano} | fonte: {arq.name}', flush=True)
        if not arq.is_file():
            if ano == 2025 and not exigir_2025:
                processados[str(ano)] = {
                    'ano': ano, 'status': 'indisponivel',
                    'reason': 'Dashboard 2025 com IND-031 ainda não encontrado; nenhum resultado estimado.',
                    'recortes': {},
                }
                dados_anos[str(ano)] = processados[str(ano)]
                continue
            raise FileNotFoundError(f'Fonte IND-031 não encontrada: {arq}.')
        original = carregar_json(arq)
        bruto, qa = avaliar_fonte(ano, original)
        recortes, privacidade = calcular_recortes(bruto, ano)
        dado = {
            'ano': ano, 'status': 'ok', 'population': 'POP_NEAR',
            'fonte': f'dashboard_enem_{ano}.json / IND-031',
            'n_near_brasil': recortes['BR']['n_near'],
            'validacao': qa, 'privacidade': privacidade,
            'recortes': recortes,
        }
        dados_anos[str(ano)] = dado
        processados[str(ano)] = dado
        if not somente_modulo:
            alvo = saida/'outputs'/'json'/f'dashboard_enem_{ano}.json'
            if not alvo.exists():
                print(f'  Aviso: dashboard de destino ausente; apenas módulo e CSV receberão o ano {ano}.')
            else:
                dashboard_destino = carregar_json(alvo)
                if dashboard_destino.get('meta', {}).get('year') != ano:
                    raise ValueError(f'{alvo}: ano do dashboard de destino incorreto.')
                dashboards_para_atualizar[alvo] = preparar_dashboard(dashboard_destino, ano, dado)
        br = recortes['BR']
        print(f'  POP_NEAR={br["n_near"]:,}; perda agregada={br["total_pontos_perdidos"]:,.0f}; '
              f'UFs suprimidas={privacidade["n_recortes_suprimidos"]}.', flush=True)

    linhas = []
    for ano_txt, dado in sorted(dados_anos.items(), key=lambda par: int(par[0])):
        if dado.get('status') != 'ok':
            continue
        for uf in ('BR', *UFS):
            rec = dado['recortes'][uf]
            for item in rec['resumo_competencias']:
                linhas.append({'ano': int(ano_txt), 'uf': uf,
                               'competencia': item['competencia'],
                               'n_near': rec['n_near'],
                               **item})

    modulo = {
        'indicator_id': 'IND-033',
        'titulo': 'Participação de cada competência na perda total até 1000',
        'status': 'draft',
        'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'anos_solicitados': list(anos),
        'anos_disponiveis': sorted(int(a) for a, d in dados_anos.items()
                                  if d.get('status') == 'ok'),
        'population': 'POP_NEAR', 'geography': 'SG_UF_PROVA',
        'methodology': {
            'fonte': 'IND-031 (perdas exatas acumuladas por competência em POP_NEAR)',
            'selecao_herdada': 'TP_STATUS_REDACAO=1; 900<=NU_NOTA_REDACAO<=980',
            'perda_competencia': 'loss_i = 200 - NU_NOTA_COMPi',
            'participacao': 'sum(loss_i)/sum(loss_1+loss_2+loss_3+loss_4+loss_5)',
            'agregacao': 'razao_dos_totais = media_das_participacoes_individuais_ponderada_pela_perda_total',
            'denominador': 'Total de pontos perdidos nas 5 competências, ano e UF',
            'média_simples_individual_calculada': False,
            'ind031_requerido': True,
            'nao_ler_microdados_novamente': True,
            'ano_2025': 'calculável quando IND-031/2025 estiver disponível',
            'privacidade': 'Não suprime automaticamente agregados com 1..29 redações; '
                           'proteção cruzada com IND-031 e outros indicadores pendente.',
            'cautelas': [
                'O percentual é participação no total da perda, não proporção de redações com desconto (IND-032).',
                'Os cinco percentuais do mesmo ano/UF somam 100%, sujeitos a arredondamento.',
                'Participações estaduais não devem ser promediadas sem ponderação pelos pontos perdidos.',
                'Consistência de notas individuais e de junções é herdada do IND-031, não revalidada aqui.',
                'Status draft até revisão acadêmica e de privacidade cruzada.',
            ],
        },
        'years': dados_anos,
    }
    # Fontes e estruturas validadas em memória antes de qualquer alteração em disco.
    salvar_json_atomico(caminho_json, modulo)
    salvar_csv_atomico(caminho_csv, linhas)
    for arquivo, payload in dashboards_para_atualizar.items():
        salvar_json_atomico(arquivo, payload)
        print(f'  Dashboard integrado: {arquivo.name}', flush=True)
    print(f'IND-033 | Concluído. JSON={caminho_json} | CSV={caminho_csv}', flush=True)
    return modulo


def main() -> None:
    p = argparse.ArgumentParser(description='IND-033 | Participação na perda total, POP_NEAR (900–980)')
    p.add_argument('--base', type=Path, default=raiz_projeto(),
                   help='Raiz que contém outputs/json/dashboard_enem_*.json com IND-031')
    p.add_argument('--saida', type=Path, default=None,
                   help='Raiz de saída (por padrão, igual a --base)')
    p.add_argument('--anos', type=int, nargs='+', default=list(ANOS),
                   help='Anos desejados entre 2019 e 2025')
    p.add_argument('--sobrescrever', action='store_true')
    p.add_argument('--somente-modulo', action='store_true',
                   help='Não modifica os dashboards existentes')
    p.add_argument('--exigir-2025', action='store_true',
                   help='Falha se não houver dashboard 2025 com IND-031')
    args = p.parse_args()
    anos = tuple(sorted(set(args.anos)))
    if not anos or not set(anos) <= set(ANOS):
        p.error('Informe apenas anos entre 2019 e 2025.')
    executar(args.base, args.saida or args.base, anos, args.sobrescrever,
             args.somente_modulo, args.exigir_2025)


if __name__ == '__main__':
    main()
