# Validação técnica — IND-007: Situação da redação (ENEM 2019–2025)

**Projeto:** Projeto Integrador IV — UNIVESP
**Indicador:** IND-007 — Situação da redação
**Escopo:** anos 2019–2025, Brasil, 27 UFs de aplicação e consolidado histórico.
**Data da auditoria:** 18/10/2026 (arquivos enviados pelo projeto)
**Estado:** APROVADO tecnicamente para análise interna; **NÃO LIBERADO para publicação** até supressão e revisão acadêmica.

## 1. Fontes e método de validação

- `IND_007_situacao_redacao.csv` — 2.016 linhas, separadas por ponto e vírgula e com codificação UTF-8 BOM.
- `IND_007_situacao_redacao.json` — módulo do indicador, oito períodos (7 anos + histórico), 28 unidades geográficas por período, 9 categorias por unidade.
- `dashboard_enem_2024.json` — integração do IND-007 ao dashboard de 2024.
- Reconciliados ainda os módulos `IND_001_redacoes_validas.json` e `IND_006_distribuicao_notas.json`, disponíveis no projeto.
- Validação formal do dashboard pelo arquivo `04_resultados_analises.schema.json` (v1.0.0).

**População de cálculo:** `POP_ALL`, todos os registros das bases, classificados por `TP_STATUS_REDACAO`. A categoria `NAO_INFORMADO` não equivale automaticamente a redação em branco ou ausência no exame.

## 2. Conclusão

- **39.379 verificações aprovadas; zero divergências.**
- 224 agrupamentos auditados (8 períodos × 28 recortes) e 2.016 linhas do CSV confrontadas com os JSONs.
- Fechamento da soma de nove categorias com todos os registros em cada recorte e ano.
- Conferência de proporções (8 casas decimais, com tolerância de arredondamento) e percentuais (4 casas decimais, com tolerância de arredondamento).
- Reconciliação da quantidade de redações `TP_STATUS_REDACAO = 1` com IND-001 e IND-006 para todas as UFs, anos e histórico.
- As contagens históricas foram recomputadas como a soma das edições, e não a média das porcentagens.
- As 27 UFs reproduzem a distribuição nacional de todos os nove status em cada período.
- JSON de 2024 com IND-001 a IND-007, incluindo indicadores anteriores preservados nas seções principais.
- Validação pelo JSON Schema v1.0.0 sem erros.

## 3. Brasil: resultados anuais

| Ano | Total de registros | Status 1 (sem problemas) | Status não informado |
|---|---:|---:|---:|
| 2019 | 5.095.171 | 3.779.356 | 1.172.126 |
| 2020 | 5.783.109 | 2.674.914 | 3.028.969 |
| 2021 | 3.389.832 | 2.293.797 | 1.011.453 |
| 2022 | 3.476.105 | 2.363.615 | 982.663 |
| 2023 | 3.933.955 | 2.704.814 | 1.111.312 |
| 2024 | 4.332.944 | 3.002.710 | 1.164.989 |
| 2025 | 4.810.772 | 3.245.696 | 1.353.217 |
| **2019–2025** | **30.821.888** | **20.064.902** | **9.824.729** |

## 4. Situação da redação no Brasil em 2024

| Código | Situação | Quantidade | Percentual sobre POP_ALL |
|---|---|---:|---:|
| 1 | Sem problemas | 3.002.710 | 69.2995% |
| 2 | Anulada | 2.432 | 0.0561% |
| 3 | Cópia Texto Motivador | 17.725 | 0.4091% |
| 4 | Em Branco | 89.786 | 2.0722% |
| 6 | Fuga ao tema | 33.357 | 0.7698% |
| 7 | Não atendimento ao tipo textual | 3.159 | 0.0729% |
| 8 | Texto insuficiente | 14.387 | 0.3320% |
| 9 | Parte desconectada | 4.399 | 0.1015% |
| NAO_INFORMADO | Status não informado | 1.164.989 | 26.8868% |

## 5. Privacidade e divulgação

Foram identificadas **112 células UF × situação com contagens positivas inferiores a 30** no total dos oito períodos (incluindo consolidado); **11** dessas células referem-se a 2024.

| Período | Células de 1 a 29 |
|---|---:|
| 2019 | 6 |
| 2020 | 5 |
| 2021 | 20 |
| 2022 | 38 |
| 2023 | 24 |
| 2024 | 11 |
| 2025 | 8 |

**Pendência:** aplicar política de supressão primária e, se necessário, complementar. Não basta esconder as células pequenas se os totais Brasil, históricos, percentuais ou outras saídas permitirem recuperá-las por subtração.
Também é necessário verificar se qualquer produto público já acessível expõe as contagens originais dessas células.

## 6. Limitações metodológicas

- Auditoria baseada em arquivos CSV e JSON gerados e fornecidos pelo projeto; os microdados brutos originais não foram reprocessados de forma independente.
- A interpretação dos rótulos oficiais deve respeitar os dicionários de cada edição do ENEM; o código 1 é “Sem problemas”, diferente de uma classificação de inscrição ou presença.
- `SG_UF_PROVA` indica a UF de aplicação da prova, não o estado de residência.
- O agregado 2019–2025 reúne registros de participação em edições do exame, não pessoas únicas.
- Os metadados permanecem com `data_status: draft`. A avaliação acadêmica e a revisão de privacidade são etapas distintas desta auditoria.

## 7. Recomendação

**Registrar o IND-007 como validado tecnicamente para uso interno, mantendo bloqueada a publicação pública da versão atual até revisão das células pequenas e aprovação acadêmica.**
