# Validação técnica IND-039 — Mapa nota × competência

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 28/10/2026
**Escopo:** revalidação dos arquivos agregados corrigidos (CSV e JSON), confrontos entre indicadores e integração ao dashboard de 2024.
**Publicação:** `draft`; revisão metodológica e de divulgação pendente.

## 1. Materiais auditados

- `IND_039_mapa_nota_competencia.csv` — SHA-256: `cddc99dd9f7164320da0810b217ec994234426c597dda97a40ba80c782c41c93`
- `IND_039_mapa_nota_competencia.json` — SHA-256: `c717852e2a49e9ebc2c786b2ae6b81157736ccf2dbca4ad085ac853eff744c33`
- `dashboard_enem_2024.json` — SHA-256: `5c1cd4489708d980b9f185d2d53426cb3df5c64987c80d97a7eab8cb0ac0a40d`
- Arquivos correlatos IND-036/037/039, confrontados entre si; em 2024, referências IND-030/031/032/035 presentes no dashboard.
- `Validar_Reprocessamento_IND_036_037_039.py` e `Resumo_Revalidacao_IND_036_037_039.json`.

## 2. Parecer computacional

- **65.122 verificações específicas IND-039 realizadas; 65.122 aprovadas; 0 falhas**.
- A auditoria conjunta de IND-036, IND-037 e IND-039 totalizou **150.825 verificações**, com **5.498 conferências compartilhadas** entre indicadores e **0 falhas**. As conferências compartilhadas não foram duplicadas na contagem específica deste documento.
- **4.900 células** de faixa × competência e 4.900 linhas de CSV conferidas.
- **196 recortes geográficos anuais** (7 edições × 28 recortes), com BR e 27 UFs em cada ano.
- CSV, JSON e blocos do dashboard de 2024 estão consistentes nas verificações realizadas. Os dados derivam, em grande medida, do mesmo processamento, portanto essa conferência não constitui recálculo independente dos microdados.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `039.csv_valores` | 34.300 | 0 |
| `039.count_range` | 4.900 | 0 |
| `039.csv_chaves` | 4.900 | 0 |
| `039.loss_range` | 4.900 | 0 |
| `039.media` | 4.900 | 0 |
| `039.percentual` | 4.900 | 0 |
| `039.5_comp` | 980 | 0 |
| `039.comps_len` | 980 | 0 |
| `039.limites` | 980 | 0 |
| `039.sem_supressao` | 980 | 0 |
| `039.perdas_faixa` | 979 | 0 |
| `039.5_faixas` | 196 | 0 |
| `039.c_soma` | 196 | 0 |
| `039.c_validas` | 196 | 0 |
| `039.completude` | 196 | 0 |
| `039.n_faixas` | 196 | 0 |
| `039.n_high` | 196 | 0 |
| `039.soma_inconsistente` | 196 | 0 |
| `039.N` | 7 | 0 |
| `039.ano_status` | 7 | 0 |
| `039.n_descontos_raros` | 7 | 0 |
| `039.n_faixas_raras` | 7 | 0 |
| `039.uf_soma` | 7 | 0 |
| `039.ufs` | 7 | 0 |
| `039.anos` | 1 | 0 |
| `039.csv_n` | 1 | 0 |
| `039.dashboard_br` | 1 | 0 |
| `039.dashboard_high` | 1 | 0 |
| `039.dashboard_id` | 1 | 0 |
| `039.dashboard_quality` | 1 | 0 |
| `039.dashboard_ufs` | 1 | 0 |
| `039.schema` | 1 | 0 |
| `039.status` | 1 | 0 |

**Total específico IND-039: 65.122 verificações, 0 falhas.**

### Resumo anual

| Ano | Status no JSON | POP_HIGH Brasil | POP_NEAR Brasil | Faixas N=1–29 divulgadas | Contagens de descontos N=1–29 divulgadas |
|---|---|---:|---:|---:|---:|
| 2019 | `ok` | 172.601 | 172.548 | 4 | 124 |
| 2020 | `ok` | 183.371 | 183.343 | 1 | 118 |
| 2021 | `ok` | 163.769 | 163.747 | 5 | 177 |
| 2022 | `ok` | 197.115 | 197.083 | 6 | 172 |
| 2023 | `ok` | 288.662 | 288.602 | 1 | 126 |
| 2024 | `ok` | 291.123 | 291.111 | 8 | 133 |
| 2025 | `ok` | 173.543 | 173.533 | 18 | 161 |

### Método e verificações próprias do indicador

- POP_HIGH: redações válidas com nota final entre 900 e 1000, inclusive; POP_NEAR usado como controle.
- Cinco faixas: `[900,920)`, `[920,940)`, `[940,960)`, `[960,980)` e `[980,1000]`; competência C1–C5 em cada faixa, totalizando 25 células por recorte.
- Validação dos denominadores, da quantidade de descontos, do percentual `100 × n_com_desconto / n_validas_c` e da perda média `soma(200-Ci) / n_validas_c`.
- Controles dos limites 0–200 de perda por competência, fechamento das cinco faixas, validade das cinco competências e correspondência com POP_NEAR dos IND-036/037; IND-030 e IND-031 em 2024.

## 4. Achados específicos

**Nenhuma divergência computacional detectada nas verificações dos agregados.**

**Política de divulgação corrigida:** `agregada_sem_supressao_de_contagens_1_a_29`, versão `2.0` — divulga contagens e estatísticas agregadas, sem ocultação automática por limiar 30.

- A política revisada publica explicitamente as contagens agregadas de 1 a 29 e evita a contradição de divulgar o total e ocultar uma única faixa recuperável por subtração.
- Na versão antiga, havia 37 casos de contagem supostamente oculta que era recuperável por totais publicados. Isso não representa erro nas métricas, mas incoerência na política anterior de divulgação.
- Em 2024, o JSON informa 8 faixas com contagem 1–29 e 133 contagens de desconto 1–29; tais valores são intencionalmente visíveis na nova política.
- A divulgação sem supressão automática não atesta ausência de risco de identificação por cruzamentos.

## 5. Limites e recomendações

- **Sem recálculo independente dos microdados originais:** não foi possível verificar novamente a seleção individual, a integridade integral das junções ou a execução a partir dos registros brutos.
- **Dashboard:** a integração foi comparada integralmente com o dashboard enviado de **2024** (Brasil e 27 UFs). Os dashboards reprocessados dos outros anos não foram objeto dessa conferência.
- **Conferências cruzadas:** incluem comparações com indicadores calculados de fontes relacionadas; como algumas saídas compartilham pipeline, a concordância não garante independência estatística.
- **2025:** os resultados fornecidos têm status `ok`; o parecer valida esses agregados recebidos, não certifica a origem independente dos microdados.
- **Divulgação:** o projeto registra decisão sobre supressão, mas a anonimização da fonte e a ausência de IDs nos agregados não garantem, isoladamente, proteção contra reconstrução ou identificação cruzada.
- **Interpretação:** O mapa é descritivo; as faixas não identificam causas do desempenho e os percentuais são condicionados às redações com cinco competências válidas.
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

**IND-039: conferência agregada tecnicamente coerente, sem divergências nos testes executados.**
A alteração da política de divulgação foi identificada nos arquivos reprocessados. Este parecer substitui a interpretação dos resultados antigos em relação às regras de supressão, mas não autoriza automaticamente a publicação nem comprova validação independente desde os microdados.

---
*Parecer individual elaborado a partir da execução de `Validar_Reprocessamento_IND_036_037_039.py` sobre os arquivos corrigidos; sem alterar os arquivos-fonte.*
