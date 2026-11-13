# -*- coding: utf-8 -*-
"""Testes locais sem microdados para a auditoria pré-entrega do Streamlit."""
import json
import tempfile
import unittest
from pathlib import Path

from auditar_streamlit_entrega import auditar_indicador


class TesteAuditoriaEntrega(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.raiz = Path(self.pasta.name)
        (self.raiz / "outputs/json").mkdir(parents=True)
        self.indicador = {
            "numero": 2, "pagina": "overview", "titulo": "Nota média",
            "restricoes": "Confirmar domínio antes de publicar",
        }

    def fonte(self, conteudo):
        arquivo = self.raiz / "outputs/json/IND_002_nota_media.json"
        arquivo.write_text(conteudo, encoding="utf-8")
        return arquivo

    def test_fonte_ausente_e_falha(self):
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["estado"], "ERRO")
        self.assertIn("Fonte JSON", linha["observacoes"])

    def test_json_invalido_e_falha(self):
        self.fonte("{invalido")
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["estado"], "ERRO")
        self.assertIn("Falha ao ler", linha["observacoes"])

    def test_id_incompatível_e_falha(self):
        self.fonte(json.dumps({"meta": {"indicator_id": "IND-003"}}))
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["estado"], "ERRO")
        self.assertIn("difere", linha["observacoes"])

    def test_rascunho_e_restricao_sao_alertas_nao_falsas_falhas(self):
        self.fonte(json.dumps({
            "meta": {"indicator_id": "IND-002", "data_status": "draft"},
            "anos": [2019, 2025],
        }))
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["estado"], "OK")
        self.assertEqual(linha["status_dados"], "draft")
        self.assertTrue(linha["pendencia_catalogo"])
        self.assertIn("rascunho", linha["observacoes"])

    def test_status_draft_na_raiz_do_json_v2_tambem_e_contado(self):
        self.fonte(json.dumps({
            "indicator_id": "IND-002",
            "status": "draft",
            "publicacao_autorizada": False,
        }))
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["status_dados"], "draft")
        self.assertEqual(linha["publicacao_autorizada"], "false")
        self.assertEqual(linha["estado"], "OK")

    def test_nao_autorizado_na_fonte_e_sinalizado(self):
        self.fonte(json.dumps({
            "indicator_id": "IND-002", "publicacao_autorizada": False,
        }))
        linha = auditar_indicador(self.raiz, self.indicador)
        self.assertEqual(linha["estado"], "OK")
        self.assertEqual(linha["publicacao_autorizada"], "false")
        self.assertIn("não autorizam", linha["observacoes"])


if __name__ == "__main__":
    unittest.main()
