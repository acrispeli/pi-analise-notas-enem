# Validação técnica IND-047 — Internet × desempenho

**Projeto:** Projeto Integrador IV — UNIVESP  
**Período:** ENEM 2019–2025  
**Data da auditoria:** 29/10/2026  
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — sem reprocessamento independente dos microdados`  
**Escopo:** conferência independente dos **arquivos agregados entregues** em `Validacao.zip`; não constitui reprocessamento dos microdados originais.

## 1. Materiais auditados

- `IND_047_internet_desempenho.json` — JSON do indicador.
- `IND_047_internet_desempenho.csv` — CSV do indicador, delimitador `;` e UTF-8.
- `dashboard_enem_2024.json` — integração de 2024 quando aplicável.
- Referências complementares fornecidas no projeto: IND-045, IND-002 e IND-040, conforme o caso; IND-053 e IND-054 são comparados entre si.
- SHA-256 das entradas no `Manifesto_SHA256_Entradas.json`.

## 2. Parecer computacional

- **41,928 verificações aprovadas**; **0 falha(s)**; **0 alerta(s)**; **0 verificações condicionais não efetuadas**.
- **4,032 linhas de dados no CSV**.
- Anos com resultados: **2019, 2020, 2021, 2022, 2023, 2024**.
- Os testes verificam a consistência da informação efetivamente entregue, não substituem auditoria independente das fontes.

## 3. Critérios e resultados

Conferiu seis medidas (nota total e C1–C5), Q025 2019–2023 vs Q020 2024, categoria A/B, percentuais, N e consistência dos resultados.

| Grupo de verificações | Executadas | Erros | Alertas |
|---|---:|---:|---:|
| `2025_indisponivel` | 1 | 0 | 0 |
| `anos` | 1 | 0 | 0 |
| `categoria_exclusiva` | 672 | 0 | 0 |
| `csv_chave_unica` | 4,032 | 0 | 0 |
| `csv_json_chave` | 4,032 | 0 | 0 |
| `csv_json_desvio_padrao` | 1,680 | 0 | 0 |
| `csv_json_iqr` | 1,680 | 0 | 0 |
| `csv_json_media` | 1,680 | 0 | 0 |
| `csv_json_mediana` | 1,680 | 0 | 0 |
| `csv_json_n_redacoes` | 3,360 | 0 | 0 |
| `csv_json_percentual` | 3,360 | 0 | 0 |
| `csv_json_q1` | 1,680 | 0 | 0 |
| `csv_json_q3` | 1,680 | 0 | 0 |
| `csv_json_quantidade_linhas` | 1 | 0 | 0 |
| `csv_json_suprimido` | 4,032 | 0 | 0 |
| `csv_linhas` | 1 | 0 | 0 |
| `csv_sem_identificadores` | 1 | 0 | 0 |
| `dashboard_brasil` | 1 | 0 | 0 |
| `dashboard_indicador` | 1 | 0 | 0 |
| `dashboard_quality_presente` | 1 | 0 | 0 |
| `dashboard_ufs` | 1 | 0 | 0 |
| `desvio_nao_negativo` | 1,680 | 0 | 0 |
| `fechamento_categorias` | 112 | 0 | 0 |
| `fechamento_ufs` | 6 | 0 | 0 |
| `geografia` | 168 | 0 | 0 |
| `id` | 1 | 0 | 0 |
| `intervalo_media` | 1,680 | 0 | 0 |
| `iqr` | 1,680 | 0 | 0 |
| `medidas_esperadas` | 672 | 0 | 0 |
| `n_categoria_medida` | 3,360 | 0 | 0 |
| `n_categoria_valido` | 560 | 0 | 0 |
| `n_ref_recorte` | 168 | 0 | 0 |
| `n_referencia_ind045` | 6 | 0 | 0 |
| `n_referencia_ind052` | 6 | 0 | 0 |
| `ordem_quantis` | 1,680 | 0 | 0 |
| `percentual` | 560 | 0 | 0 |
| `recortes_28` | 6 | 0 | 0 |
| `variavel_ano` | 6 | 0 | 0 |

### Quantidade anual de referência

| Ano | N reportado no módulo |
|---|---:|
| 2019 | 3,779,356 |
| 2020 | 2,674,914 |
| 2021 | 2,293,797 |
| 2022 | 2,363,615 |
| 2023 | 2,704,814 |
| 2024 | 3,002,710 |

Para IND-034 o N corresponde a redações com **980** pontos; para IND-053/054 corresponde à **amostra de treinamento**; para os indicadores 046–052 corresponde às redações válidas de cada edição.

## 4. Achados específicos

Nenhuma divergência detectada nos testes executados.

**Ano 2025:** indisponível para cruzamentos individuais questionário × redação; essa indisponibilidade não configura falha.


## 5. Limites e recomendações

- Não foram entregues os microdados individuais originais; esta auditoria verifica resultados já produzidos, não reconstrói a seleção linha a linha nem valida sozinha a correção matemática do processamento inicial.
- CSV, JSON e dashboard podem derivar do mesmo script. A concordância entre eles detecta erros de exportação, mas não prova uma reprodução independente.
- As marcas de revisão de privacidade e supressões que já existem nas saídas foram registradas como características da versão analisada, não como falhas automáticas por n<30.
- Os resultados apresentados nos arquivos-fonte permanecem em estado `draft`, independentemente desta conferência.

- Recomenda-se conferência da plausibilidade dos resultados com amostras dos microdados, especialmente junções 2024, variações dos questionários, notas definitivas por competência e replicação das MCA/clusterizações.
- **Sem um critério fixo de supressão por n<30 nesta auditoria:** células pequenas não foram automaticamente classificadas como erro; eventuais mascaramentos presentes nas saídas continuam sendo comportamentos dos scripts originais e não foram removidos.

## 6. Conclusão

**CONFERÊNCIA AGREGADA APROVADA — sem reprocessamento independente dos microdados.** A aprovação agregada significa que os controles listados passaram, não que a análise esteja homologada em todas as dimensões.

---
*Relatório gerado por `auditar_resultados.py`; arquivos fornecidos não foram modificados.*
