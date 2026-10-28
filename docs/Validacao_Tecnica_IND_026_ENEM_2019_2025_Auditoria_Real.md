# Validação técnica — IND-026 | Concordância por competência (Kappa ponderado quadrático) | ENEM 2019–2025

**Projeto:** Projeto Integrador IV — UNIVESP
**Data desta auditoria:** 22/10/2026
**Fontes examinadas:** CSV e JSON gerados pelo processamento local; saídas de referência de indicadores anteriores; código e testes sintéticos da implementação.
**Status:** **Aprovado na auditoria computacional dos resultados agregados**, com **23.346 verificações aprovadas e 0 falhas**. Permanece `draft`; divulgação pública não aprovada.
**Escopo:** sete edições (2019–2025), Brasil e 27 UFs por edição, mais consolidado histórico; 1.120 linhas do CSV.

## 1. Objetivo e definição metodológica

O IND-026 mede a **concordância ordinal entre primeiro e segundo avaliador, competência a competência (C1–C5)**, por meio do Kappa de Cohen ponderado **quadraticamente**. A população é `POP_EVALUATOR`, limitada a registros com cinco pares de notas de competências completos e válidos. O histórico utiliza momentos estatísticos combinados; não é a média simples dos Kappas anuais.

Para cada par de notas `X` (AV1) e `Y` (AV2):

\[
\kappa_{quad}=1-\frac{\mathbb{E}[(X-Y)^2]}{\mathbb{E}[X^2]+\mathbb{E}[Y^2]-2\mathbb{E}[X]\mathbb{E}[Y]}.
\]

A fórmula equivale a ponderar a distância quadrática das notas na escala de 0 a 200 pontos. O indicador registra `null`/indefinido quando o desacordo esperado é zero. **Kappa ponderado não é equivalente ao percentual de notas exatamente iguais:** diferenças pequenas recebem penalidade menor. Não serve para identificar erro ou conduta de um avaliador.

## 2. Resultados nacionais observados

| Ano/período | N pares completos | Kappa C1 | Kappa C2 | Kappa C3 | Kappa C4 | Kappa C5 |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 3.779.355 | 0,488906 | 0,605042 | 0,566172 | 0,577088 | 0,787430 |
| 2020 | 2.674.914 | 0,516528 | 0,651624 | 0,608316 | 0,614656 | 0,736609 |
| 2021 | 2.378.379 | 0,682217 | 0,787189 | 0,677665 | 0,740239 | 0,820838 |
| 2022 | 2.493.442 | 0,701608 | 0,805033 | 0,727723 | 0,758343 | 0,828763 |
| 2023 | 2.822.643 | 0,644908 | 0,702132 | 0,656514 | 0,699531 | 0,780877 |
| 2024 | 3.167.955 | 0,697933 | 0,720570 | 0,695361 | 0,738393 | 0,812010 |
| 2025 | 3.457.555 | 0,687151 | 0,720560 | 0,693113 | 0,725214 | 0,808737 |
| 2019–2025 | 20.774.243 | 0,649937 | 0,720405 | 0,661277 | 0,703662 | 0,799495 |

No histórico, **C5 possui o maior Kappa ponderado (0,799495)**, enquanto **C1 possui o menor (0,649937)**. Isso é um resultado descritivo do indicador e **não** significa que a C5 tenha necessariamente a maior proporção de notas idênticas. Em todos os recortes fornecidos, a cobertura de cinco pares foi de 100% da `POP_EVALUATOR`.

## 3. Procedimentos e resultados da auditoria

Foram testados `CSV × JSON`, unicidade das chaves `período/UF/competência`, 1.120 linhas, presença de C1–C5 em todos os 224 recortes, oito períodos, 27 UFs, faixa de Kappa de `[-1, 1]`, coerência do status de Kappa definido ou indefinido, porcentagens de concordância exata entre 0 e 100, contagens de pares e cobertura, soma das 27 UFs, soma de sete anos para o histórico, supressão de percentuais capazes de reconstruir contagens positivas inferiores a 30, e metadados.

Os **224 denominadores** e totais pareados foram cotejados com os dados de referência dos **IND-020 e IND-021**, inclusive todas as competências do IND-021. Como controle adicional, a média e o desvio-padrão das diferenças absolutas do IND-021 permitiram calcular a discordância quadrática observada aproximada (`média² + desvio_padrão²`); o desacordo esperado inferido a partir dos Kappas permaneceu no intervalo matematicamente admissível em todos os recortes/competências. **Esse controle é de plausibilidade, não uma reestimativa independente do Kappa**.

| Verificação | Resultado |
|---|---|
| Linhas CSV | 1.120 / 1.120 |
| Períodos × territórios × competências | 8 × 28 × 5 |
| Denominador igual aos IND-020 e IND-021 | 224 de 224 |
| Cinco pares completos iguais aos do IND-021 | 224 de 224 |
| Kappa e percentuais dentro de seus domínios | Sem violações |
| Supressão de concordância exata e células raras | Sem violações detectadas |
| CSV/JSON e soma dos recortes | Sem divergências |
| Verificações automáticas deste indicador | **23.346** |
| Falhas automáticas | **0** |

## 4. Verificação do algoritmo e testes sintéticos

Executei novamente a suíte sintética do IND-026, com **aprovação**. Foram cobertos: concordância perfeita com marginais variáveis (Kappa=1), oposição ordinal equilibrada (Kappa=-1), marginal constante e igual (indefinido), categorias constantes diferentes (Kappa=0), grupos insuficientes, supressão do percentual de concordância exata, junções, agregações, sete anos, preservação estrutural de dashboards e comparação numérica da implementação de Kappa com `sklearn.metrics.cohen_kappa_score(weights='quadratic')`.

O uso de momentos `∑X`, `∑Y`, `∑X²`, `∑Y²` e `∑XY` é matematicamente suficiente para Kappa quadrático. Entretanto, **os momentos/marginais originais não são publicados nos arquivos recebidos**; assim, não foi possível recalcular independentemente os 1.120 valores de Kappa a partir dos microdados originais. A validação empírica comprova coerência dos agregados fornecidos e compatibilidade com os indicadores anteriores.

## 5. Privacidade e interpretação

Nenhum par individual ou matriz de confusão é exportado nos arquivos examinados. O percentual de concordância exata é acompanhado da indicação de supressão; não foram detectadas contagens positivas recuperáveis inferiores a 30. O histórico representa participações acumuladas, não indivíduos únicos. Diferenças de Kappa entre anos também podem refletir alterações das distribuições marginais das notas; requerem revisão de comparabilidade.

## 6. Limitações e pendências para divulgação

1. A auditoria recebeu **saídas agregadas** (CSV/JSON), referências agregadas anteriores e scripts/testes. **Os microdados individuais originais de 2019–2025 não foram reprocessados de forma independente nesta sessão.** A checagem do comportamento dos algoritmos foi feita em dados sintéticos.
2. **Os sete dashboards atualizados após IND-026 não foram fornecidos para a auditoria atual.** A presença do nome de cada dashboard na lista `dashboard_files` **não comprova** a integração final nem a preservação dos indicadores anteriores em arquivos reais. Os testes de integração foram sintéticos.
3. Os resultados permanecem `draft`, sujeitos a revisão metodológica/estatística, acadêmica, comparabilidade interanual e avaliação de privacidade complementar antes de publicação.
4. Para aprovação empírica integral, executar um recálculo independente, ao menos amostral e preferencialmente completo, diretamente dos microdados e conferir os sete dashboards finais.

## 7. Rastreabilidade dos arquivos auditados

| Arquivo | SHA-256 |
|---|---|
| `IND_026_concordancia_competencias.csv` | `ee65ba02c9ce47c558f0e5005908f6f10c57ff434aabe2bad2972879120f87f4` |
| `IND_026_concordancia_competencias.json` | `490d632373ed4178312cb5385f8982f07bc602a6d7d1899a7c6d426702f3b0f4` |
| `IND_020_diferenca_total_av1_av2.json` (referência) | `e57e61a6ee4db5d85b0720ddd18c64d664835fb78ebf947cab683df692c09d21` |
| `IND_021_diferenca_por_competencia.json` (referência) | `4d65c37bb6b4d08f1cf8eadf5705115a7a9c22549f8ce21bb4057b3be6aaa435` |

**Arquivos de auditoria reproduzível:** `auditar_ind024_025_026.py` e `auditoria_IND024_025_026_resultados.json` (separados deste relatório). Os contadores representam asserções automatizadas, podendo haver várias asserções sobre o mesmo recorte; não correspondem a registros individuais distintos.

## 8. Parecer técnico

**IND-026: APROVADO COMPUTACIONALMENTE PARA USO INTERNO E DISCUSSÃO ACADÊMICA**, nos limites dos CSV/JSON agregados recebidos e dos testes executados (**23.346 verificações sem falhas**). **NÃO APROVADO AINDA PARA PUBLICAÇÃO IRRESTRITA**; dependem de revisão acadêmica, verificação independente dos microdados e auditoria dos dashboards finais.
