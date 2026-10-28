# Validação técnica IND-037 — Concentração de descontos: Q de Cochran, Friedman e pós-testes

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025, por Brasil e 27 UFs
**Estado do parecer:** `CONFERÊNCIA AGREGADA APROVADA — revisão acadêmica pendente`
**Data:** 28/10/2026
**Escopo:** revalidação dos arquivos agregados corrigidos (CSV e JSON), confrontos entre indicadores e integração ao dashboard de 2024.
**Publicação:** `draft`; revisão metodológica e de divulgação pendente.

## 1. Materiais auditados

- `IND_037_concentracao_descontos.csv` — SHA-256: `3018369b05f23691a82da48a1467c6c409dc706657a93b8ff35dc39f8ca68975`
- `IND_037_concentracao_descontos.json` — SHA-256: `0c84292e86b411625db6ab73fa0dcd06571933231784a9791c722b2aa015497f`
- `dashboard_enem_2024.json` — SHA-256: `5c1cd4489708d980b9f185d2d53426cb3df5c64987c80d97a7eab8cb0ac0a40d`
- Arquivos correlatos IND-036/037/039, confrontados entre si; em 2024, referências IND-030/031/032/035 presentes no dashboard.
- `Validar_Reprocessamento_IND_036_037_039.py` e `Resumo_Revalidacao_IND_036_037_039.json`.

## 2. Parecer computacional

- **41.936 verificações específicas IND-037 realizadas; 41.936 aprovadas; 0 falhas**.
- A auditoria conjunta de IND-036, IND-037 e IND-039 totalizou **150.825 verificações**, com **5.498 conferências compartilhadas** entre indicadores e **0 falhas**. As conferências compartilhadas não foram duplicadas na contagem específica deste documento.
- **392 testes globais** (Cochran e Friedman), **3.920 pós-testes** (McNemar e Wilcoxon) e 4.312 linhas de CSV conferidas.
- **196 recortes geográficos anuais** (7 edições × 28 recortes), com BR e 27 UFs em cada ano.
- CSV, JSON e blocos do dashboard de 2024 estão consistentes nas verificações realizadas. Os dados derivam, em grande medida, do mesmo processamento, portanto essa conferência não constitui recálculo independente dos microdados.

## 3. Critérios e resultados das verificações

| Grupo de verificações | Quantidade executada | Falhas registradas |
|---|---:|---:|
| `037.csv_valores` | 17.248 | 0 |
| `037.csv_N` | 4.312 | 0 |
| `037.csv_chaves` | 4.312 | 0 |
| `037.csv_status` | 4.312 | 0 |
| `037.holm` | 3.920 | 0 |
| `037.posthoc_sig` | 3.920 | 0 |
| `037.media_perda` | 980 | 0 |
| `037.percentual` | 929 | 0 |
| `037.dez_pares` | 392 | 0 |
| `037.omnibus_p` | 392 | 0 |
| `037.omnibus_sig` | 392 | 0 |
| `037.pares` | 392 | 0 |
| `037.kendall_w` | 196 | 0 |
| `037.testes_presentes` | 196 | 0 |
| `037.N` | 7 | 0 |
| `037.ano_status` | 7 | 0 |
| `037.n_recortes_testes` | 7 | 0 |
| `037.uf_soma` | 7 | 0 |
| `037.ufs` | 7 | 0 |
| `037.anos` | 1 | 0 |
| `037.csv_n` | 1 | 0 |
| `037.dashboard_br` | 1 | 0 |
| `037.dashboard_id` | 1 | 0 |
| `037.dashboard_quality` | 1 | 0 |
| `037.dashboard_ufs` | 1 | 0 |
| `037.schema` | 1 | 0 |
| `037.status` | 1 | 0 |

**Total específico IND-037: 41.936 verificações, 0 falhas.**

### Resumo anual

| Ano | Status no JSON | POP_NEAR Brasil | Recortes com testes | Grupos de campos detalhados protegidos |
|---|---|---:|---:|---:|
| 2019 | `ok` | 172.548 | 28 | 39 |
| 2020 | `ok` | 183.343 | 28 | 43 |
| 2021 | `ok` | 163.747 | 28 | 86 |
| 2022 | `ok` | 197.083 | 28 | 90 |
| 2023 | `ok` | 288.602 | 28 | 59 |
| 2024 | `ok` | 291.111 | 28 | 82 |
| 2025 | `ok` | 173.533 | 28 | 90 |

### Método e verificações próprias do indicador

- POP_NEAR: mesmas redações 900–980; cinco competências avaliadas como observações pareadas da mesma redação.
- Q de Cochran para ocorrência binária de desconto; Friedman para magnitude de perdas e W de Kendall como tamanho de efeito.
- McNemar exato e Wilcoxon pareado para os dez pares de competências de cada família; ajuste de Holm refeito separadamente em cada família; indicadores de significância conferidos a alfa de 0,05.
- Confronto das frequências e perdas por competência com o IND-039 e, em 2024, com os IND-031/032 do dashboard.

## 4. Achados específicos

**Nenhuma divergência computacional detectada nas verificações dos agregados.**

**Política de divulgação corrigida:** `testes_agregados_sem_bloqueio_mascara_rara_v2` — mantém testes para recortes com N adequado; campos de contagens detalhadas podem ser omitidos.

- Todos os 196 recortes (7 anos × Brasil + 27 UFs) apresentam resultados estatísticos, sem a supressão global antiga.
- Os p-valores numéricos exibidos como `0.0` refletem possíveis limites de precisão de ponto flutuante (underflow); não significam probabilidade matematicamente nula.
- Os valores de significância não devem ser confundidos com tamanho de efeito, causalidade ou problema na correção; a seleção de notas 900–980 impõe condicionamento estrutural.
- Campos detalhados de contagem omitidos são registrados na política de divulgação; isso não implica ausência de risco de reconstrução cruzada.

## 5. Limites e recomendações

- **Sem recálculo independente dos microdados originais:** não foi possível verificar novamente a seleção individual, a integridade integral das junções ou a execução a partir dos registros brutos.
- **Dashboard:** a integração foi comparada integralmente com o dashboard enviado de **2024** (Brasil e 27 UFs). Os dashboards reprocessados dos outros anos não foram objeto dessa conferência.
- **Conferências cruzadas:** incluem comparações com indicadores calculados de fontes relacionadas; como algumas saídas compartilham pipeline, a concordância não garante independência estatística.
- **2025:** os resultados fornecidos têm status `ok`; o parecer valida esses agregados recebidos, não certifica a origem independente dos microdados.
- **Divulgação:** o projeto registra decisão sobre supressão, mas a anonimização da fonte e a ausência de IDs nos agregados não garantem, isoladamente, proteção contra reconstrução ou identificação cruzada.
- **Interpretação:** Testes são pareados, e o Wilcoxon usa aproximação assintótica com empates; significância deve ser lida junto de magnitudes e tamanhos de efeito.
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

**IND-037: conferência agregada tecnicamente coerente, sem divergências nos testes executados.**
A alteração da política de divulgação foi identificada nos arquivos reprocessados. Este parecer substitui a interpretação dos resultados antigos em relação às regras de supressão, mas não autoriza automaticamente a publicação nem comprova validação independente desde os microdados.

---
*Parecer individual elaborado a partir da execução de `Validar_Reprocessamento_IND_036_037_039.py` sobre os arquivos corrigidos; sem alterar os arquivos-fonte.*
