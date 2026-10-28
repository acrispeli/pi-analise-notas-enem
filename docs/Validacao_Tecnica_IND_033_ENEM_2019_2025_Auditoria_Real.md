# Validação técnica IND-033 — Participação de cada competência na perda total

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 27/10/2026
**Escopo:** auditoria de agregados publicados em CSV e JSON, dashboard de 2024 e referências cruzadas.
**Publicação:** `draft`; revisão acadêmica e de privacidade cruzada pendente.

## 1. Materiais auditados

- `IND_033_participacao_perda_total.csv`
- `IND_033_participacao_perda_total.json`
- `dashboard_enem_2024.json` enviado
- Módulos correlatos IND-030, IND-031, IND-032, IND-033 e IND-035 quando aplicáveis.

## 2. Parecer computacional

- **14,571 verificações agregadas executadas**; **14,571 aprovadas** e **0 falhas de testes individuais** (além de alertas e achados identificados por busca de risco).
- **0 erros**, **0 alertas** e **0 notas**.
- **980 registros CSV** confrontados com **980 registros equivalentes do JSON**.
- **196 recortes** e **7 anos processados**.
- CSVs, JSONs e dashboards são derivados do mesmo processamento em muitos casos: as verificações entre eles **não constituem recálculo independente dos microdados**.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `CSV_JSON_valores` | 10,780 | 0 |
| `pontos_limites` | 980 | 0 |
| `media_perda_formula` | 980 | 0 |
| `participacao_formula` | 980 | 0 |
| `uf_chave` | 196 | 0 |
| `pop_near_contra_IND032` | 196 | 0 |
| `participacoes_somam_100` | 196 | 0 |
| `soma_pontos_5_competencias` | 196 | 0 |
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

Razão dos pontos perdidos por competência sobre o total de perdas C1..C5; soma das participações ~100%; comparação com IND-039.

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
