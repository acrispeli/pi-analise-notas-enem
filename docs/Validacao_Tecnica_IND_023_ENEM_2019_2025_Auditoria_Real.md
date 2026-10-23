# Validação técnica independente — IND-023 (ENEM 2019–2025)

**Projeto Integrador IV — UNIVESP**  
**Indicador:** IND-023 — Divergência de status AV1 × AV2  
**Auditoria dos arquivos reais recebidos:** 20/10/2026  
**Resultado:** **APROVADO NOS AGREGADOS** — 8.559 verificações, 0 falhas  
**Status editorial:** `draft`; aprovação acadêmica e avaliação de privacidade pendentes.

## 1. Arquivos e escopo

Recebidos e auditados:

- `IND_023_divergencia_status.csv` — 224 recortes por ano/UF, inclusive histórico;
- `IND_023_divergencia_status.json` — JSON modular com sete anos, histórico e 27 UFs;
- `dashboard_enem_2024.json` — integração da página de avaliadores, série histórica, qualidade, metodologia e versão.

Também foram consultados, como referências de reconciliação, os módulos anteriores já disponíveis nesta sessão:

- `IND_022_discrepancia_oficial.json`: `n_criterio_status_divergente`, `n_status_par_preenchido`, `n_status_criterio_desconhecido` e `n_pop_evaluator`;
- `IND_020_diferenca_total_av1_av2.json`: população pareada `n_avaliacoes_pareadas`.

O universo é **7 edições (2019–2025) + o consolidado histórico × (Brasil + 27 UFs)** = **224 recortes**. O histórico soma *participações* (não indivíduos únicos). A UF é o **local de prova**.

## 2. Procedimentos de auditoria

1. CSV com 224 linhas, chaves de período/UF completas, sem duplicidade e correspondentes ao JSON.
2. Reconciliação campo a campo das cinco contagens e quatro percentuais no CSV contra o JSON modular.
3. Recálculo independente dos percentuais com tolerância de 0,000000501 ponto percentual, compatível com arredondamento em seis casas decimais.
4. Verificação das identidades: `n_pop_evaluator = n_pares_status_preenchidos + n_status_nao_comparaveis` e `n_pares_status_preenchidos = n_status_divergentes + n_status_iguais`.
5. Soma das 27 UFs igual ao Brasil, separadamente em cada ano e histórico, para as cinco contagens.
6. Soma dos sete anos igual ao histórico para Brasil e cada uma das 27 UFs, para as cinco contagens.
7. Conferência integral de 224 recortes contra o gatilho de divergência de situação no IND-022 e contra a população do IND-020.
8. Conferência da projeção no dashboard real de **2024** (Brasil/27 UFs, séries anuais e total/27 UFs históricos), da qualidade, metodologia, origem e sinalização `draft`.
9. Verificação de que não há matriz detalhada artificialmente publicada nem registros individuais exportados pelo IND-023.
10. Verificação de que nenhum campo de contagem agregado positivo tem valor de 1 a 29 no arquivo recebido. Isso não substitui a avaliação de privacidade global do projeto.

**Resultado automatizado: 8.559 checagens aprovadas; nenhuma falha.** Script independente: `auditoria_IND023.py`; saída máquina: `auditoria_IND023_resultados.json`.

## 3. Resultados nacionais auditados

| Ano | População pareada (`POP_EVALUATOR`) | Pares com status diferentes | Taxa de divergência (%) |
|---|---:|---:|---:|
| 2019 | 3.779.355 | 20.178 | 0,533901 |
| 2020 | 2.674.914 | 18.877 | 0,705705 |
| 2021 | 2.378.379 | 20.956 | 0,881104 |
| 2022 | 2.493.442 | 45.276 | 1,815803 |
| 2023 | 2.822.643 | 60.912 | 2,157977 |
| 2024 | 3.167.955 | 49.778 | 1,571298 |
| 2025 | 3.457.555 | 61.639 | 1,782734 |
| **2019–2025** | **20.774.243** | **277.616** | **1,336347** |

**Brasil 2024:** 3.118.177 pares com status iguais, 49.778 com status diferentes, 0 status não comparáveis na população analisada. Cobertura de status **100%** nessa população. A taxa de concordância exata de status entre pares comparáveis é **98,428702%**.

**Histórico:** 20.496.627 pares iguais e 277.616 divergentes na população elegível. A taxa histórica de **1,336347%** é ponderada pela quantidade de participações; **não** é a média aritmética simples das sete taxas anuais.

O maior percentual anual foi o de **2023 (2,157977%)** e o menor foi o de **2019 (0,533901%)**. Essa oscilação, por si só, não demonstra efeito da mudança da banca, dos temas ou da formação dos avaliadores.

**Recortes estaduais 2024:** a maior taxa foi a do Amazonas (**2,674922%**) e a menor, a de Santa Catarina (**0,946479%**). A comparação reflete redações agrupadas pelo local de aplicação da prova e não qualifica o desempenho dos avaliadores de uma região.

## 4. Integração ao dashboard de 2024

Confirmados:

- `meta.analysis_version` inclui IND-023 e `meta.data_status = draft`;
- `pages.evaluators.status_disagreement`: valores nacionais e das 27 UFs de 2024;
- `pages.temporal.ind023`: sete pontos anuais nacionais e consolidados histórico nacional/UF;
- `quality.ind023_validation`: população, status preenchidos, divergentes, origem IND-022 e sinalizadores de revisão;
- `pages.methodology.ind023`: definição, denominadores, tratamento de ausências e limitações;
- reconciliação de `pages.evaluators.official_discrepancy` (IND-022) e `total_difference` (IND-020).

O dashboard completo inclui componentes anteriores, mas a auditoria atual restringiu a comparação profunda ao IND-023 e a seus vínculos com IND-020/022. **Os demais seis dashboards reais não foram fornecidos neste envio**, e não se declara validação de integração neles.

## 5. Pendências e limites

**O KPI do IND-023 está validado em nível de agregados, mas a matriz detalhada AV1 × AV2 não foi calculada.** Todos os 224 recortes informam `matriz_status.status = nao_calculada_requer_microdados` com `celulas = []`. A matriz depende da execução do script em `--modo matriz` com leitura dos microdados originais, seguida de reconciliação e supressão de células raras. Não é possível derivar a distribuição dos pares de códigos de status somente dos totais recebidos.

Como os valores do IND-023 foram derivados diretamente dos contadores já existentes do IND-022, a checagem cruzada confirma **consistência e reprodução**, mas **não constitui recálculo independente de cada avaliação original**. Isso limita a força da afirmação de validação.

As taxas não são divulgadas aqui como estatísticas oficiais calculadas pelo Inep. O status permanece `draft` até revisão acadêmica, avaliação de privacidade e validação dos dados com os microdados, se requerida. A ausência de células 1–29 entre as contagens principais não certifica automaticamente a publicação de outros indicadores ou da matriz detalhada.

## 6. Execução da auditoria

Salve `auditoria_IND023.py` na raiz do projeto (com `outputs/json` e `outputs/indicadores`) e execute:

```powershell
.\.venv\Scripts\python.exe auditoria_IND023.py --base .
```

O programa busca os módulos IND-020/022 para a conferência adicional e gera `auditoria_IND023_resultados.json`. O script usa apenas a biblioteca padrão do Python; não modifica dashboards nem microdados.

## Parecer

**IND-023: APROVADO NOS AGREGADOS COM RESSALVA.** Os 224 recortes e a integração de 2024 conferem integralmente com CSV, JSON, IND-020 e IND-022. A **matriz de situações** e a **validação de integração dos outros seis dashboards reais** permanecem pendentes. A visualização Streamlit continua na edição anterior, até IND-022, e não foi atualizada nesta auditoria.
