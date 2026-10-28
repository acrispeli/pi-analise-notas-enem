# Validação técnica IND-036 — Regras de associação de descontos (Apriori)

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 28/10/2026
**Escopo:** revalidação dos arquivos agregados corrigidos (CSV e JSON), confrontos entre indicadores e integração ao dashboard de 2024.
**Publicação:** `draft`; revisão metodológica e de divulgação pendente.

## 1. Materiais auditados

- `IND_036_regras_associacao.csv` — SHA-256: `ad0df357e0ce9e824086fa66c6f0285c799bfe3f5ba7dda50db6cb4575866ace`
- `IND_036_regras_associacao.json` — SHA-256: `6f35d86eb2efb82a33fcb82f3948e55431ef87900a7e511e442d250f611b932b`
- `dashboard_enem_2024.json` — SHA-256: `5c1cd4489708d980b9f185d2d53426cb3df5c64987c80d97a7eab8cb0ac0a40d`
- Arquivos correlatos IND-036/037/039, confrontados entre si; em 2024, referências IND-030/031/032/035 presentes no dashboard.
- `Validar_Reprocessamento_IND_036_037_039.py` e `Resumo_Revalidacao_IND_036_037_039.json`.

## 2. Parecer computacional

- **38.269 verificações específicas IND-036 realizadas; 38.269 aprovadas; 0 falhas**.
- A auditoria conjunta de IND-036, IND-037 e IND-039 totalizou **150.825 verificações**, com **5.498 conferências compartilhadas** entre indicadores e **0 falhas**. As conferências compartilhadas não foram duplicadas na contagem específica deste documento.
- **2.091 regras** validadas e 2.091 linhas de CSV conferidas.
- **196 recortes geográficos anuais** (7 edições × 28 recortes), com BR e 27 UFs em cada ano.
- CSV, JSON e blocos do dashboard de 2024 estão consistentes nas verificações realizadas. Os dados derivam, em grande medida, do mesmo processamento, portanto essa conferência não constitui recálculo independente dos microdados.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `036.csv_valores` | 20.910 | 0 |
| `036.confianca` | 2.091 | 0 |
| `036.csv_chaves` | 2.091 | 0 |
| `036.itens` | 2.091 | 0 |
| `036.leverage` | 2.091 | 0 |
| `036.lift` | 2.091 | 0 |
| `036.limiares` | 2.091 | 0 |
| `036.n_rules` | 2.091 | 0 |
| `036.suporte` | 2.091 | 0 |
| `036.max_regras` | 196 | 0 |
| `036.n_selecionadas` | 196 | 0 |
| `036.regras_disponiveis` | 196 | 0 |
| `036.N` | 7 | 0 |
| `036.ano_status` | 7 | 0 |
| `036.n_ano_rules` | 7 | 0 |
| `036.uf_soma` | 7 | 0 |
| `036.ufs` | 7 | 0 |
| `036.anos` | 1 | 0 |
| `036.csv_n` | 1 | 0 |
| `036.dashboard_br` | 1 | 0 |
| `036.dashboard_id` | 1 | 0 |
| `036.dashboard_quality` | 1 | 0 |
| `036.dashboard_ufs` | 1 | 0 |
| `036.schema` | 1 | 0 |
| `036.status` | 1 | 0 |

**Total específico IND-036: 38.269 verificações, 0 falhas.**

### Resumo anual

| Ano | Status no JSON | POP_NEAR Brasil | Regras no Brasil | Regras no ano (BR + UFs) |
|---|---|---:|---:|---:|
| 2019 | `ok` | 172.548 | 4 | 195 |
| 2020 | `ok` | 183.343 | 13 | 373 |
| 2021 | `ok` | 163.747 | 13 | 370 |
| 2022 | `ok` | 197.083 | 12 | 345 |
| 2023 | `ok` | 288.602 | 14 | 362 |
| 2024 | `ok` | 291.111 | 8 | 204 |
| 2025 | `ok` | 173.533 | 8 | 242 |

### Método e verificações próprias do indicador

- POP_NEAR: redações válidas com nota final entre 900 e 980; cada transação contém competências C1–C5 com nota inferior a 200.
- Apriori: suportes de itemsets frequentes; regras com antecedente/consequente disjuntos; suporte, confiança, lift e leverage recalculados a partir das contagens exportadas.
- Verificações das condições `n_ambos <= n_antecedente`, `n_ambos <= n_consequente`, contagem mínima 30, `min_suporte >= 0,01`, `min_confianca >= 0,30`, `min_lift >= 1,00` e limite máximo de regras por recorte.
- Comparação das margens de competências com IND-037 e, em 2024, dos itemsets conjuntos com IND-035 disponível no dashboard.

## 4. Achados específicos

**Nenhuma divergência computacional detectada nas verificações dos agregados.**

**Política de divulgação corrigida:** `regras_agregadas_sem_bloqueio_mascara_rara_v2` — não oculta o recorte inteiro por máscara exata rara; exige contagens mínimas dos itemsets e das regras publicadas.

- As regras nacionais voltaram a ficar disponíveis para 2021–2025; a auditoria não encontrou recortes inteiros ocultos por máscaras raras.
- Os parâmetros observados são suporte mínimo 1%, confiança mínima 30%, lift mínimo 1 e até 30 regras por recorte; as associações com lift perto de 1 podem ter relevância prática pequena.
- A contagem mínima de 30 permanece como critério operacional de frequência, e não como garantia de anonimização.

## 5. Limites e recomendações

- **Sem recálculo independente dos microdados originais:** não foi possível verificar novamente a seleção individual, a integridade integral das junções ou a execução a partir dos registros brutos.
- **Dashboard:** a integração foi comparada integralmente com o dashboard enviado de **2024** (Brasil e 27 UFs). Os dashboards reprocessados dos outros anos não foram objeto dessa conferência.
- **Conferências cruzadas:** incluem comparações com indicadores calculados de fontes relacionadas; como algumas saídas compartilham pipeline, a concordância não garante independência estatística.
- **2025:** os resultados fornecidos têm status `ok`; o parecer valida esses agregados recebidos, não certifica a origem independente dos microdados.
- **Divulgação:** o projeto registra decisão sobre supressão, mas a anonimização da fonte e a ausência de IDs nos agregados não garantem, isoladamente, proteção contra reconstrução ou identificação cruzada.
- **Interpretação:** Padrões Apriori são descritivos, não relações de causa e efeito; os limiares e a seleção das regras alteram a leitura dos resultados.
- Resultados anuais representam participações, não necessariamente pessoas únicas; `SG_UF_PROVA` representa a UF de realização da prova.
- Manter o status `draft` até revisão acadêmica e decisão documentada sobre a divulgação.

### Procedimento para reprodução

Salve o script `Validar_Reprocessamento_IND_036_037_039.py` na raiz do repositório (ou indique a pasta com os arquivos) e execute:

```powershell
cd D:\pi-analise-notas-enem
.\.venv\Scripts\python.exe Validar_Reprocessamento_IND_036_037_039.py --pasta .
```

O validador apenas lê os arquivos de resultado e grava um resumo e um relatório conjuntos; não reprocessa microdados nem modifica dashboards.

## 6. Conclusão

**IND-036: conferência agregada tecnicamente coerente, sem divergências nos testes executados.**
A alteração da política de divulgação foi identificada nos arquivos reprocessados. Este parecer substitui a interpretação dos resultados antigos em relação às regras de supressão, mas não autoriza automaticamente a publicação nem comprova validação independente desde os microdados.

---
*Parecer individual elaborado a partir da execução de `Validar_Reprocessamento_IND_036_037_039.py` sobre os arquivos corrigidos; sem alterar os arquivos-fonte.*
