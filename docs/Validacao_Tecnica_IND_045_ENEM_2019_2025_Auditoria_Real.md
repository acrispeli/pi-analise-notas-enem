# Validação técnica IND-045 — Tipo/trajetória escolar × nota da redação

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 27/10/2026
**Escopo:** auditoria de agregados publicados em CSV e JSON, dashboard de 2024 e referências cruzadas.
**Publicação:** `draft`; revisão acadêmica e de privacidade cruzada pendente.

## 1. Materiais auditados

- `IND_045_tipo_escola_nota.csv`
- `IND_045_tipo_escola_nota.json` (extraído do ZIP enviado, sem modificar a origem)
- `dashboard_enem_2024.json` enviado
- Módulos correlatos IND-030, IND-031, IND-032, IND-033 e IND-035 quando aplicáveis. Também o `IND_043_escolaridade_responsaveis_nota.json` para indicadores socioeconômicos.

## 2. Parecer computacional

- **22,576 verificações agregadas executadas**; **22,576 aprovadas** e **0 falhas de testes individuais** (além de alertas e achados identificados por busca de risco).
- **0 erros**, **0 alertas** e **0 notas**.
- **1,064 registros CSV** confrontados com **1,064 registros equivalentes do JSON**.
- **168 recortes** e **6 anos processados**.
- CSVs, JSONs e dashboards são derivados do mesmo processamento em muitos casos: as verificações entre eles **não constituem recálculo independente dos microdados**.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `CSV_JSON_valores` | 18,088 | 0 |
| `escola_n_min` | 1,008 | 0 |
| `escola_percentual` | 1,008 | 0 |
| `escola_quantis` | 532 | 0 |
| `escola_iqr` | 532 | 0 |
| `escola_valores_limites` | 532 | 0 |
| `uf_chave` | 168 | 0 |
| `tipo_escola_N_vs_43` | 168 | 0 |
| `escola_variavel_origem` | 168 | 0 |
| `escola_categorias_somam_N` | 140 | 0 |
| `escola_media_ponderada_vs_43` | 140 | 0 |
| `escola_supressao` | 56 | 0 |
| `ano_status_ok` | 6 | 0 |
| `recortes_28` | 6 | 0 |
| `fechamento_27_ufs` | 6 | 0 |
| `pop_ano_vs_br` | 6 | 0 |

### Resumo anual

| Ano | Status no JSON | Brasil: denominador |
|---|---|---:|
| 2019 | `ok` | 3,779,356 |
| 2020 | `ok` | 2,674,914 |
| 2021 | `ok` | 2,293,797 |
| 2022 | `ok` | 2,363,615 |
| 2023 | `ok` | 2,704,814 |
| 2024 | `ok` | 3,002,710 |
| 2025 | `indisponivel` | — |

### Método e verificações próprias do indicador

2019–2023: TP_ESCOLA; 2024: Q023. Estatísticas de nota total, médias ponderadas, quantis, categorias, somatórios e comparação com IND-043.
**2025:** ausência declarada de vínculo público entre questionário socioeconômico e notas; indisponibilidade preservada.

## 4. Achados específicos

Nenhuma divergência detectada nos testes programáticos descritos. Isso **não equivale** a aprovação metodológica ou de privacidade para publicação.

## 5. Limites e recomendações

- O projeto utiliza o limiar operacional de 30 observações. A ausência de células pequenas isoladas não garante impossibilidade de reconstrução por diferenças ou cruzamentos entre indicadores.
- O `dashboard_enem_2024.json` enviado cobre apenas 2024. A integração dos demais anos não pôde ser testada contra seus dashboards atualizados.
- Não foram anexados os microdados originais de todas as edições; portanto não se confirmou a seleção individual, a integridade da junção ou a reprodução integral do cálculo.
- Verificar o tratamento de `2025` conforme disponibilidade real e compatibilidade das fontes por indicador.
- Os resultados são participações anuais, não indivíduos únicos. UF refere-se ao local da prova.
- Manter os resultados como **rascunho (`draft`)** até correções indicadas, revisão estatística, revisão de privacidade cruzada e aprovação acadêmica.

## 6. Conclusão

**Conferência agregada tecnicamente coerente para os testes executados**, sem equivaler à validação independente dos microdados ou à autorização de publicação.

---
*Gerado automaticamente pelo script `Validar_Indicadores_032_039_044_045.py`. Sem modificar arquivos-fonte.*
