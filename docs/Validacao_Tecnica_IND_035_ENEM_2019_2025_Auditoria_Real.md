# Validação técnica IND-035 — Combinações de perdas por competência

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 27/10/2026
**Escopo:** auditoria de agregados publicados em CSV e JSON, dashboard de 2024 e referências cruzadas.
**Publicação:** `draft`; revisão acadêmica e de privacidade cruzada pendente.

## 1. Materiais auditados

- `IND_035_combinacoes_perdas.csv`
- `IND_035_combinacoes_perdas.json`
- `dashboard_enem_2024.json` enviado
- Módulos correlatos IND-030, IND-031, IND-032, IND-033 e IND-035 quando aplicáveis.

## 2. Parecer computacional

- **57,163 verificações agregadas executadas**; **57,163 aprovadas** e **0 falhas de testes individuais** (além de alertas e achados identificados por busca de risco).
- **0 erros**, **0 alertas** e **0 notas**.
- **3,920 registros CSV** confrontados com **3,920 registros equivalentes do JSON**.
- **196 recortes** e **7 anos processados**.
- CSVs, JSONs e dashboards são derivados do mesmo processamento em muitos casos: as verificações entre eles **não constituem recálculo independente dos microdados**.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `CSV_JSON_valores` | 39,200 | 0 |
| `itemsets_formato` | 3,920 | 0 |
| `itemset_monotonicidade` | 3,890 | 0 |
| `itemset_supressao` | 2,360 | 0 |
| `trio_le_par` | 2,340 | 0 |
| `itemset_intervalo` | 1,560 | 0 |
| `itemset_min_n` | 1,560 | 0 |
| `itemset_percentual` | 1,560 | 0 |
| `uf_chave` | 196 | 0 |
| `pop_near_contra_IND032` | 196 | 0 |
| `itemsets_20` | 196 | 0 |
| `itemset_supressao_integral` | 118 | 0 |
| `pop_near_2024_vs_31` | 28 | 0 |
| `ano_status_ok` | 7 | 0 |
| `recortes_28` | 7 | 0 |
| `fechamento_27_ufs` | 7 | 0 |
| `pop_ano_vs_br` | 7 | 0 |

### Resumo anual

| Ano | Status no JSON | Brasil: denominador |
|---|---|---:|
| 2019 | `ok` | 172,548 |
| 2020 | `ok` | 183,343 |
| 2021 | `ok` | 163,747 |
| 2022 | `ok` | 197,083 |
| 2023 | `ok` | 288,602 |
| 2024 | `ok` | 291,111 |
| 2025 | `ok` | 173,533 |

### Método e verificações próprias do indicador

Dez pares e dez trios INCLUSIVOS de competências descontadas; monotonicidade de subconjuntos, percentuais e confrontação com IND-032/036.

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
