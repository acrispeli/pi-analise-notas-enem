# -*- coding: utf-8 -*-
"""Regressão da liberação pública condicional dos perfis materiais V2."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from publicacao_segura_v2 import (
    PERFIS_V2, MODELO_V2, MINIMO_PUBLICACAO, preparar_doc_publico_v2,
)

RAIZ = Path(__file__).resolve().parents[1]


class TestePublicacaoSeguraV2(unittest.TestCase):
    def _modelo(self, numero, registros):
        return {
            "indicator_id": f"IND-{numero:03d}",
            "modelo_referencia": MODELO_V2,
            "publicacao_autorizada": True,
            "results": registros,
        }

    def test_sem_autorizacao_ou_modelo_incorreto_nao_exibe(self):
        x = self._modelo(57, [{"ano": 2024, "n_high_900_1000": 50}])
        x["publicacao_autorizada"] = False
        self.assertIsNone(preparar_doc_publico_v2(x, 57)[0])
        x["publicacao_autorizada"] = True
        x["modelo_referencia"] = "MODELO_ANTIGO"
        self.assertIsNone(preparar_doc_publico_v2(x, 57)[0])

    def test_ind057_omite_numerador_pequeno_e_preserva_original(self):
        reg = [
            {"ano": 2024, "cluster": "C1", "n_notas_validas": 500,
             "n_high_900_1000": 100, "n_near_900_980": 100,
             "percentual_high": 20.0},
            {"ano": 2024, "cluster": "C3", "n_notas_validas": 500,
             "n_high_900_1000": 6, "n_near_900_980": 6,
             "percentual_high": 1.2},
        ]
        raw = self._modelo(57, reg)
        protegido, ocultas = preparar_doc_publico_v2(raw, 57)
        self.assertEqual(ocultas, 1)
        self.assertEqual(len(protegido["results"]), 1)
        self.assertEqual(protegido["results"][0]["cluster"], "C1")
        self.assertEqual(len(raw["results"]), 2)

    def test_ind058_omite_subcontagem_pequena_com_denominador_grande(self):
        reg = [
            {"ano": 2024, "cluster": "C1", "n_near_cluster": 80,
             "n_com_competencia_valida": 80, "n_com_desconto": 65,
             "frequencia_desconto": 0.81},
            {"ano": 2024, "cluster": "C2", "n_near_cluster": 80,
             "n_com_competencia_valida": 80, "n_com_desconto": 3,
             "frequencia_desconto": 0.0375},
        ]
        protegido, ocultas = preparar_doc_publico_v2(self._modelo(58, reg), 58)
        self.assertEqual(ocultas, 1)
        self.assertEqual(len(protegido["results"]), 1)
        self.assertNotIn("0.0375", str(protegido))

    def test_dados_reais_seis_indicadores_tem_liberacao_condicional(self):
        arquivos = {
            55: "IND_055_perfil_socio_nota.json",
            56: "IND_056_perfil_socio_competencias.json",
            57: "IND_057_perfil_socio_alto_desempenho.json",
            58: "IND_058_perfil_socio_perdas.json",
            59: "IND_059_perfil_socio_divergencia.json",
            68: "IND_068_evolucao_perfis_socioeconomicos.json",
        }
        self.assertEqual(set(arquivos), PERFIS_V2)
        ocultos = {}
        for ind, nome in arquivos.items():
            with self.subTest(indicador=ind):
                with (RAIZ / "outputs" / "json" / nome).open(encoding="utf-8") as file:
                    doc = json.load(file)
                self.assertIs(doc["publicacao_autorizada"], True)
                self.assertEqual(doc["status"], "apresentacao_publica_com_ressalvas")
                self.assertIn("revisao_academica_formal_pendente", doc["review"])
                self.assertEqual(doc["modelo_referencia"], MODELO_V2)
                visivel, ocultas[ind] = preparar_doc_publico_v2(doc, ind)
                self.assertIsNotNone(visivel)
                for registro in visivel["results"]:
                    for chave, val in registro.items():
                        if (chave == "n" or chave.startswith("n_")) and isinstance(val, int):
                            self.assertGreaterEqual(val, MINIMO_PUBLICACAO)
        self.assertGreater(ocultos[57], 0)
        self.assertGreater(ocultos[58], 0)
        for numero in (55, 56, 59, 68):
            self.assertEqual(ocultos[numero], 0)

    def test_duas_rotas_aplicam_a_protecao(self):
        for nome in ("painel_paginas_contrato_68.py", "painel_catalogo_68.py"):
            with self.subTest(rota=nome):
                codigo = (RAIZ / nome).read_text(encoding="utf-8")
                self.assertIn("preparar_doc_publico_v2(doc, escolha)", codigo)
                self.assertIn("mostrar_aviso_publicacao_v2(st, escolha, ocultas)", codigo)


if __name__ == "__main__":
    unittest.main()
