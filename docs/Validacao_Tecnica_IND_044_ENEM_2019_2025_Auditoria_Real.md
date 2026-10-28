# Validação técnica IND-044 — Escolaridade dos responsáveis × competências

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 27/10/2026
**Escopo:** auditoria de agregados publicados em CSV e JSON, dashboard de 2024 e referências cruzadas.
**Publicação:** `draft`; revisão acadêmica e de privacidade cruzada pendente.

## 1. Materiais auditados

- `IND_044_escolaridade_competencias.csv`
- `IND_044_escolaridade_competencias.json` (extraído do ZIP enviado, sem modificar a origem)
- `dashboard_enem_2024.json` enviado
- Módulos correlatos IND-030, IND-031, IND-032, IND-033 e IND-035 quando aplicáveis. Também o `IND_043_escolaridade_responsaveis_nota.json` para indicadores socioeconômicos.

## 2. Parecer computacional

- **361,768 verificações agregadas executadas**; **361,768 aprovadas** e **0 falhas de testes individuais** (além de alertas e achados identificados por busca de risco).
- **0 erros**, **0 alertas** e **0 notas**.
- **13,740 registros CSV** confrontados com **13,740 registros equivalentes do JSON**.
- **168 recortes** e **6 anos processados**.
- CSVs, JSONs e dashboards são derivados do mesmo processamento em muitos casos: as verificações entre eles **não constituem recálculo independente dos microdados**.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `CSV_JSON_valores` | 247,320 | 0 |
| `escolaridade_valor_limite` | 64,400 | 0 |
| `escolaridade_competencia_n` | 12,880 | 0 |
| `escolaridade_quantis_ordenados` | 12,880 | 0 |
| `escolaridade_iqr` | 12,880 | 0 |
| `escolaridade_contagem_vs_43` | 2,576 | 0 |
| `escolaridade_n_min` | 2,576 | 0 |
| `escolaridade_percentual` | 2,576 | 0 |
| `escolaridade_soma_medias_vs_43` | 2,576 | 0 |
| `categorias_vs_43` | 336 | 0 |
| `escolaridade_categorias_somam_N` | 224 | 0 |
| `escolaridade_supressao` | 172 | 0 |
| `uf_chave` | 168 | 0 |
| `escolaridade_N_vs_43` | 168 | 0 |
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

Q001 e Q002 por competência: quantis, desvio-padrão, N, percentuais, soma das médias C1–C5 versus IND-043 e supressões por categoria.
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
