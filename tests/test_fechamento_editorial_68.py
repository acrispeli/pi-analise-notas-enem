# -*- coding: utf-8 -*-
"""Testes sintéticos do fechamento editorial, sem reler microdados."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finalizar_metadados_editoriais_68 import (
    ajustar_conteudo, executar, fontes_publicas,
)


class TesteFechamentoEditorial68(unittest.TestCase):
    def test_apenas_status_e_review_previstos_sao_alterados(self):
        origem = {
            "indicator_id": "IND-064",
            "status": "draft",
            "meta": {"data_status": "draft", "analysis_version": "2.4"},
            "review": "pendente_revisao_academica_e_privacidade_contextual",
            "results": [
                {"ano": 2024, "status": "ok", "media": 658.9658},
                {"ano": 2025, "status": "nao_aplicavel", "motivo": "sem notas"},
                {"ano": 2023, "status": "draft", "media": 642.81},
            ],
            "method_note": "A série não demonstra causalidade.",
        }
        dados = json.dumps(origem, ensure_ascii=False, indent=2).encode("utf-8")
        resultado, contagens = ajustar_conteudo(dados)
        final = json.loads(resultado)
        self.assertEqual(contagens["status_rascunho"], 3)
        self.assertEqual(contagens["revisao_editorial"], 1)
        self.assertEqual(final["status"], "consolidado_para_apresentacao")
        self.assertEqual(final["meta"]["data_status"], "consolidado_para_apresentacao")
        self.assertEqual(final["review"], "aprovacao_editorial_pelo_responsavel")
        self.assertEqual(final["results"][0], origem["results"][0])
        self.assertEqual(final["results"][1], origem["results"][1])
        self.assertEqual(final["results"][2]["status"], "consolidado_para_apresentacao")
        self.assertEqual(final["results"][2]["media"], 642.81)
        self.assertEqual(final["method_note"], origem["method_note"])

    def test_mantem_textos_e_numeros_e_e_idempotente(self):
        txt = (b'{"status":"draft","review":"pendente_revisao_academica_e_privacidade_contextual",'
               b'"observacoes":"draft e revisao pendente no historico",'
               b'"n":6,"media":100.5,"publicacao_autorizada":false}')
        novo, c = ajustar_conteudo(txt)
        self.assertEqual(c["status_rascunho"], 1)
        self.assertIn(b'"n":6', novo)
        self.assertIn(b'"publicacao_autorizada":false', novo)
        self.assertIn(b'draft e revisao pendente no historico', novo)
        repeticao, c2 = ajustar_conteudo(novo)
        self.assertEqual(repeticao, novo)
        self.assertEqual(sum(c2.values()), 0)

    def test_modo_previa_nao_grava_arquivos(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            base = raiz / "outputs" / "json"
            base.mkdir(parents=True)
            fonte = base / "IND_002_nota_media.json"
            fonte.write_text('{"meta":{"data_status":"draft"},"results":[{"n":10}]}',
                             encoding="utf-8")
            dashboard = base / "dashboard_enem_2024.json"
            dashboard.write_text('{"meta":{"status":"draft"}}', encoding="utf-8")
            self.assertEqual(len(fontes_publicas(raiz)), 2)
            arquivos, contagens = executar(raiz, aplicar=False)
            self.assertEqual(arquivos, 2)
            self.assertEqual(contagens["status_rascunho"], 2)
            self.assertIn('"draft"', fonte.read_text())
            with patch("finalizar_metadados_editoriais_68.conferir_branch"):
                arquivos, _ = executar(raiz, aplicar=True)
            self.assertEqual(arquivos, 2)
            self.assertIn("consolidado_para_apresentacao", fonte.read_text())
            restantes, _ = executar(raiz, aplicar=False)
            self.assertEqual(restantes, 0)

    def test_catalogo_sem_pendencias_administrativas_em_restricoes(self):
        raiz = Path(__file__).resolve().parents[1]
        catalogo = json.loads((raiz / "docs/catalogo_navegacao_68.json").read_text(encoding="utf-8"))
        self.assertEqual(len(catalogo["indicadores"]), 68)
        import re
        marcador = re.compile(r"\b(?:confirmar|pendentes?|revisão|revisao)\b", re.I)
        self.assertEqual(
            [x["id"] for x in catalogo["indicadores"]
             if marcador.search(str(x.get("restricoes") or ""))],
            [],
        )


if __name__ == "__main__":
    unittest.main()
