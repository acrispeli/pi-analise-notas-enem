# Relatório de validação técnica — IND-006

**Projeto:** Projeto Integrador IV — UNIVESP  
**Indicador:** IND-006 — Distribuição das notas da redação  
**Período:** ENEM 2019–2025  
**Data:** 17/10/2026 (Brasil)  
**Decisão:** Aprovado para análise técnica interna; publicação pública depende de revisão de células pequenas e aprovação acadêmica.

## 1. Escopo e resultado

- **29.348 verificações automatizadas, sem divergências** nos arquivos agregados e cruzamentos.
- **224 grupos** (Brasil + 27 UFs × sete anos + histórico) e **2.240 linhas de CSV**.
- Conferência completa do CSV contra o JSON do indicador, de contagens agregadas por Brasil/UF/ano e consolidação histórica.
- Cruzamento das quantidades, somas de notas, médias, medianas, desvios-padrão e percentis com os arquivos dos indicadores IND-001 a IND-005.
- Conferência do `dashboard_enem_2024.json` contra o JSON do IND-006 e o JSON Schema 1.0.0.
- **100 cenários simulados adicionais** e **1.700 verificações independentes** de frequências, média, desvio-padrão e percentis com NumPy, todas aprovadas.
- Os microdados brutos não foram reprocessados independentemente nesta auditoria.

## 2. Distribuição nacional — 2024

| Faixa | Quantidade | Percentual |
|---|---:|---:|
| `0–<100` | 454 | 0.0151% |
| `100–<200` | 1.445 | 0.0481% |
| `200–<300` | 23.557 | 0.7845% |
| `300–<400` | 119.179 | 3.9690% |
| `400–<500` | 335.920 | 11.1872% |
| `500–<600` | 594.011 | 19.7825% |
| `600–<700` | 682.487 | 22.7290% |
| `700–<800` | 479.746 | 15.9771% |
| `800–<900` | 474.788 | 15.8120% |
| `900–1000` | 291.123 | 9.6953% |

**Total 2024:** 3.002.710 redações válidas, sem diferença entre soma das faixas e total do IND-001. A classe mais frequente foi `600–<700` (682.487 redações; 22,7290%).

## 3. Distribuição anual e consolidado histórico

| Ano | N válido | Faixa mais frequente | Percentual da faixa |
|---|---:|---|---:|
| 2019 | 3.779.356 | `500–<600` | 28.0552% |
| 2020 | 2.674.914 | `500–<600` | 25.0501% |
| 2021 | 2.293.797 | `500–<600` | 26.2365% |
| 2022 | 2.363.615 | `600–<700` | 23.6773% |
| 2023 | 2.704.814 | `500–<600` | 21.3785% |
| 2024 | 3.002.710 | `600–<700` | 22.7290% |
| 2025 | 3.245.696 | `600–<700` | 23.8227% |
| **2019–2025** | **20.064.902** | **`500–<600`** | **23.8501%** |

Os valores históricos foram verificados como **somas das contagens anuais em cada faixa**, recalculando as porcentagens com base no total histórico. Esse N representa **participações nas edições**, e não pessoas únicas.

## 4. Regras de cálculo e testes

- Dez faixas mutuamente exclusivas `[0,100)`, `[100,200)`, …, `[800,900)`, `[900,1000]`, incluindo 0 e 1000.
- Quantidades inteiras não negativas, proporções `quantidade/N` e percentuais `100 × quantidade/N`, com tolerância ao arredondamento.
- Brasil = soma das 27 UFs em cada faixa e em cada ano.
- Histórico = soma das sete edições em cada faixa do Brasil e de cada UF.
- Compatibilidade entre os percentis dos IND-005 e a localização da distribuição no histograma (teste de intervalo, não recálculo exato a partir de classes).
- O dashboard inclui `pages.overview.score_distribution`, `pages.temporal.ind006` e mantém os indicadores anteriores.
- O JSON Schema usado é **permissivo para dados internos dos histogramas**; testes adicionais avaliaram sua semântica e estrutura.

## 5. Pontos a resolver antes de publicação

O dashboard de 2024 informa `quality.suppression.min_group_n = 30` e `suppressed_cells = 0`. A auditoria encontrou **246 células estaduais de histograma com contagens positivas entre 1 e 29**, incluindo **34 na edição de 2024**.

| Período | Células UF × faixa com 1–29 registros |
|---|---:|
| 2019 | 29 |
| 2020 | 32 |
| 2021 | 44 |
| 2022 | 46 |
| 2023 | 32 |
| 2024 | 34 |
| 2025 | 23 |
| 2019-2025 | 6 |

Exemplos de 2024: AC (0–<100: 7), AC (100–<200: 22), AL (0–<100: 22), AM (0–<100: 25), AP (0–<100: 4), AP (100–<200: 10).

**Ação necessária:** verificar se a regra do limiar de 30 também se aplica a cada célula do histograma e, caso se aplique, suprimir/combinar faixas pequenas antes de divulgar o painel ao público. A ocultação isolada pode ser reversível por subtração do total: avaliar supressão complementar. O campo `suppressed_cells=0` pode estar refletindo apenas o escopo original do IND-001 e precisa ser esclarecido para a nova distribuição.

## 6. Limitações e decisão final

- O controle desta auditoria usa os dados agregados gerados e enviados; sem nova leitura dos arquivos `data/raw` de 2019 a 2025.
- O status do dashboard permanece `draft`, pendente de revisão acadêmica.
- UFs indicam **locais de aplicação** da prova, não residência.
- Não confundir consistência matemática com autorização de publicação de células pequenas.

**Decisão:** cálculo e integração do IND-006 **validados tecnicamente para análise interna**. **Publicação externa pendente de revisão de divulgação e aprovação acadêmica.**

## 7. Arquivos analisados

- `IND_006_distribuicao_notas.csv`
- `IND_006_distribuicao_notas.json`
- `dashboard_enem_2024.json`
- `IND_001_redacoes_validas.json` até `IND_005_percentis_redacao.json` para os cruzamentos.
