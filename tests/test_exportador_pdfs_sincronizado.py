# -*- coding: utf-8 -*-
"""Testes offline: não permitir PDF do indicador com explicação anterior."""
import tempfile
import unittest
from pathlib import Path
from exportar_pdfs_streamlit_68_sincronizado import (
    _itens_ausentes, carregar_pistas_pedagogicas, esperar_indicador_estavel,
)

CODIGO = 'IND-003'
TITULO = 'Mediana da redação'
PERGUNTA = 'Qual foi a nota mediana?'
PISTA = 'É a nota que fica no meio quando as redações válidas são colocadas em ordem de pontuação.'


def texto_correto():
    return (f'{CODIGO} · {TITULO}\nPergunta que buscamos responder: {PERGUNTA}\n'
            'O que está sendo contado ou comparado?\n' + PISTA)


class LocatorFalso:
    def __init__(self, tela, seletor):
        self.tela, self.seletor = tela, seletor

    @property
    def first(self):
        return self

    def count(self):
        if 'stException' in self.seletor:
            return 0
        if 'stSkeleton' in self.seletor:
            return self.tela.atual.get('skeletons', 0)
        return 1

    def get_attribute(self, _):
        return self.tela.atual.get('estado', 'notRunning')

    def inner_text(self, **_):
        return self.tela.atual.get('texto', '')


class CabecalhoFalso:
    def __init__(self, tela, padrao):
        self.tela, self.padrao = tela, padrao

    def count(self):
        return int(bool(self.padrao.search(self.tela.atual.get('titulo', ''))))


class PaginaFalsa:
    def __init__(self, etapas):
        self.etapas, self.posicao = etapas, 0

    @property
    def atual(self):
        return self.etapas[min(self.posicao, len(self.etapas)-1)]

    def locator(self, seletor):
        return LocatorFalso(self, seletor)

    def get_by_role(self, papel, name):
        return CabecalhoFalso(self, name)

    def wait_for_timeout(self, _):
        self.posicao += 1


class TestesSincronizacaoExportador(unittest.TestCase):
    def test_aceita_apenas_pergunta_e_explicacao_corretas(self):
        self.assertEqual(_itens_ausentes(texto_correto(), CODIGO, TITULO, PERGUNTA, PISTA), [])
        ruim = texto_correto().replace(PISTA, 'Texto da nota média do indicador anterior.')
        self.assertIn('explicação específica',
                      _itens_ausentes(ruim, CODIGO, TITULO, PERGUNTA, PISTA))
        ruim = texto_correto().replace(PERGUNTA, 'Qual a média?')
        self.assertIn('pergunta',
                      _itens_ausentes(ruim, CODIGO, TITULO, PERGUNTA, PISTA))

    def test_espera_rerun_e_tres_leituras_estaveis(self):
        titulo = f'{CODIGO} · {TITULO}'
        errado = texto_correto().replace(PISTA, 'Explicação anterior')
        tela = PaginaFalsa([
            {'estado': 'running', 'skeletons': 1, 'titulo': titulo, 'texto': errado},
            {'estado': 'notRunning', 'titulo': titulo, 'texto': errado},
            {'estado': 'notRunning', 'titulo': titulo, 'texto': texto_correto()},
            {'estado': 'notRunning', 'titulo': titulo, 'texto': texto_correto()},
            {'estado': 'notRunning', 'titulo': titulo, 'texto': texto_correto()},
        ])
        lido = esperar_indicador_estavel(tela, CODIGO, TITULO, PERGUNTA, PISTA)
        self.assertIn(PISTA, lido)
        self.assertEqual(tela.posicao, 4)

    def test_bloqueia_pagina_desatualizada(self):
        tela = PaginaFalsa([{'titulo': f'{CODIGO} · {TITULO}',
                             'texto': 'Explicação do indicador anterior'}])
        with self.assertRaisesRegex(RuntimeError, 'não estabilizou'):
            esperar_indicador_estavel(tela, CODIGO, TITULO, PERGUNTA, PISTA, timeout_ms=1)

    def test_ast_le_guia_sem_executar_modulo(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / 'leitura_acessivel_68.py'
            arq.write_text("GUIAS = {3: ('Mediana da redação.', 'Como ler', 'Pedagógica')}\n"
                           "raise RuntimeError('não deve executar')\n", encoding='utf-8')
            self.assertEqual(carregar_pistas_pedagogicas(Path(d))[3], 'Mediana da redação.')


if __name__ == '__main__':
    unittest.main()
