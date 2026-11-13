# -*- coding: utf-8 -*-
"""Testes da divulgação dos agregados V2 sem supressão por n pequeno."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from publicacao_segura_v2 import (
    PERFIS_V2, MODELO_V2, LIMIAR_AVISO_AMOSTRA,
    preparar_doc_publico_v2, mostrar_aviso_publicacao_v2,
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
        x = self._modelo(57, [{"ano": 2024, "n_high_900_1000": 6}])
        x["publicacao_autorizada"] = False
        self.assertIsNone(preparar_doc_publico_v2(x, 57)[0])
        x["publicacao_autorizada"] = True
        x["modelo_referencia"] = "MODELO_ANTIGO"
        self.assertIsNone(preparar_doc_publico_v2(x, 57)[0])

    def test_ind057_mantem_numerador_pequeno_e_preserva_original(self):
        reg = [
            {"ano": 2024, "cluster": "C1", "n_notas_validas": 500,
             "n_high_900_1000": 100, "n_near_900_980": 100,
             "percentual_high": 20.0},
            {"ano": 2024, "cluster": "C3", "n_notas_validas": 500,
             "n_high_900_1000": 6, "n_near_900_980": 6,
             "percentual_high": 1.2},
        ]
        raw = self._modelo(57, reg)
        publico, pequenas = preparar_doc_publico_v2(raw, 57)
        self.assertEqual(pequenas, 1)
        self.assertEqual(len(publico["results"]), 2)
        self.assertEqual(publico["results"][1]["n_high_900_1000"], 6)
        self.assertEqual(len(raw["results"]), 2)

    def test_ind058_mantem_subcontagem_pequena_e_denominador_zero(self):
        reg = [
            {"ano": 2024, "cluster": "C1", "n_near_cluster": 80,
             "n_com_competencia_valida": 80, "n_com_desconto": 3,
             "frequencia_desconto": 0.0375},
            {"ano": 2020, "cluster": "C3", "n_near_cluster": 0,
             "n_com_competencia_valida": 0, "n_com_desconto": 0,
             "frequencia_desconto": None, "perda_media": None},
        ]
        publico, pequenas = preparar_doc_publico_v2(self._modelo(58, reg), 58)
        self.assertEqual(pequenas, 2)
        self.assertEqual(len(publico["results"]), 2)
        self.assertEqual(publico["results"][0]["frequencia_desconto"], 0.0375)
        self.assertIsNone(publico["results"][1]["frequencia_desconto"])
        self.assertIsNone(publico["results"][1]["perda_media"])

    def test_dados_reais_68_indicadores_v2_sem_supressao_por_n(self):
        arquivos = {
            55: "IND_055_perfil_socio_nota.json",
            56: "IND_056_perfil_socio_competencias.json",
            57: "IND_057_perfil_socio_alto_desempenho.json",
            58: "IND_058_perfil_socio_perdas.json",
            59: "IND_059_perfil_socio_divergencia.json",
            68: "IND_068_evolucao_perfis_socioeconomicos.json",
        }
        self.assertEqual(set(arquivos), PERFIS_V2)
        pequenos_por_indicador = {}
        for ind, nome in arquivos.items():
            with self.subTest(indicador=ind):
                with (RAIZ / "outputs" / "json" / nome).open(encoding="utf-8") as file:
                    doc = json.load(file)
                self.assertIs(doc["publicacao_autorizada"], True)
                self.assertEqual(doc["status"], "apresentacao_publica_autorizada")
                self.assertEqual(doc["review"], "aprovacao_editorial_pelo_responsavel")
                self.assertEqual(doc["modelo_referencia"], MODELO_V2)
                publico, pequenos_por_indicador[ind] = preparar_doc_publico_v2(doc, ind)
                self.assertIsNotNone(publico)
                aplicaveis = [
                    r for r in doc["results"] if isinstance(r, dict)
                    and r.get("status") not in ("nao_aplicavel", "indisponivel")
                ]
                self.assertEqual(publico["results"], aplicaveis)
                for registro in publico["results"]:
                    self.assertFalse({
                        "NU_INSCRICAO", "CPF", "NOME", "ID_PESSOA"
                    }.intersection(registro))
        self.assertEqual(pequenos_por_indicador[57], 6)
        self.assertEqual(pequenos_por_indicador[58], 34)
        self.assertEqual(sum(pequenos_por_indicador.values()), 40)
        self.assertEqual(LIMIAR_AVISO_AMOSTRA, 30)

    def test_aviso_de_criticidade_sem_omitir_ou_promover_causalidade(self):
        class Stub:
            def __init__(self):
                self.avisos = []

            def caption(self, texto):
                self.avisos.append(str(texto))

            def warning(self, texto):
                self.avisos.append(str(texto))

        st = Stub()
        mostrar_aviso_publicacao_v2(st, 55, 0)
        self.assertEqual(len(st.avisos), 1)
        self.assertIn("autorizada pelo responsável", st.avisos[0])
        mostrar_aviso_publicacao_v2(st, 58, 34)
        self.assertIn("inferiores a 30", st.avisos[-1])
        self.assertIn("mantidos", st.avisos[-1])
        self.assertNotIn("omitidos", st.avisos[-1])

    def test_duas_rotas_aplicam_preparacao_e_aviso(self):
        for nome in ("painel_paginas_contrato_68.py", "painel_catalogo_68.py"):
            with self.subTest(rota=nome):
                codigo = (RAIZ / nome).read_text(encoding="utf-8")
                self.assertIn("preparar_doc_publico_v2(doc, escolha)", codigo)
                self.assertIn("mostrar_aviso_publicacao_v2(st, escolha, pequenas)", codigo)


if __name__ == "__main__":
    unittest.main()
