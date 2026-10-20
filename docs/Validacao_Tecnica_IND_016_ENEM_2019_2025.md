# Validação técnica — IND-016: Mapa PC1 × PC2

**Projeto Integrador IV — UNIVESP**  
**Dados:** ENEM 2019–2025, Brasil e 27 UFs por `SG_UF_PROVA` (local da aplicação da prova)  
**Indicador:** IND-016 — Mapa PC1 × PC2  
**Data da auditoria:** 18 de outubro de 2026  
**Situação técnica:** **APROVADO PARA ANÁLISE INTERNA**  
**Situação de divulgação:** `draft`; **não publicar** até revisão acadêmica, avaliação de privacidade e supressão complementar.

## 1. Objetivo e escopo

Examinar a distribuição agregada dos escores PC1 × PC2 de redações válidas, projetadas sobre modelos de análise de componentes principais ajustados individualmente para cada ano/UF/Brasil e para o período histórico. O gráfico previsto é uma dispersão/densidade de **hexágonos agregados (hexbin)**, em substituição à exposição de pontos individuais. A implementação calcula os hexágonos sobre a população `POP_VALID` inteira e omite os hexágonos com frequências positivas de 1 a 29 observações. O raio utilizado é 0,55 em unidades de escores PCA.

A auditoria verifica a consistência matemática, estrutural e entre arquivos **dos agregados produzidos**. Os microdados individuais originais não foram disponibilizados neste ambiente; portanto **não** se pode afirmar que todos os escores ou atribuições individuais aos hexágonos tenham sido recalculados independentemente.

## 2. Materiais conferidos

- `IND_016_mapa_pc1_pc2.csv` — 12.235 linhas de dados.
- `IND_016_mapa_pc1_pc2.json` — anos de 2019 a 2025, histórico nacional e 27 UFs.
- `dashboard_enem_2024.json` — versão cumulativa `2.15.0-ind001-...-ind016`.
- `IND_014_variancia_explicada_pca.json` — modelos PCA, autovalores e bases estatísticas.
- `IND_015_loadings_pca.json` — coeficientes PCA e população dos modelos.
- `04_resultados_analises.schema.json` — contrato estrutural de dashboard v1.0.0.

Auditoria reproduzível: `auditoria_IND016.py`; resultado detalhado em `auditoria_IND016_resultados.json`.

## 3. Síntese quantitativa da auditoria

| Medida | Resultado |
|---|---:|
| Verificações automatizadas | **316.804** |
| Divergências detectadas | **0** |
| Modelos/recortes analisados | **224** |
| Hexágonos publicados nos arquivos agregados e individualmente conferidos | **12.235** |
| Anos de microdados | **7** |
| Recortes geográficos | **Brasil + 27 UFs** |
| Recortes temporais | **7 anos + histórico 2019–2025** |

**Distribuição dos controles automatizados:**

| Categoria | Verificações |
|---|---:|
| Estrutura CSV | 73.413 |
| Estrutura modular | 685 |
| Metadados | 19 |
| Dashboard | 6.953 |
| Privacidade e limiares | 25.378 |
| Método | 5 |
| Exclusividade das chaves CSV | 12.235 |
| Valores CSV | 36.705 |
| Referências IND-014/015 | 1.590 |
| Reconciliação populacional | 716 |
| Qualidade da fonte | 14 |
| Exclusividade dos hexágonos JSON | 12.235 |
| Geometria dos hexágonos | 24.470 |
| Proporções e percentuais | 24.470 |
| Correspondência CSV–JSON | 97.881 |
| Preservação de indicadores anteriores | 34 |
| JSON Schema v1.0.0 | 1 |
| **Total** | **316.804** |

Os testes verificaram, entre outros: identificadores, cobertura regional/temporal, igualdade dos denominadores com IND-014/015, consistência dos centros calculados a partir de coordenadas axiais, frequência mínima de 30 por célula exibida, `n_exibidas + n_suprimidas = n_validas`, limites de 1 a 29 observações por hexágono suprimido, porcentagens calculadas sobre o denominador correto, igualdade dos pontos em CSV/JSON e correspondência do dashboard de 2024 com os módulos de origem.

## 4. Resultados nacionais anuais

| Ano | Redações válidas | Hexágonos exibidos | Hexágonos suprimidos | Redações em células suprimidas |
|---|---:|---:|---:|---:|
| 2019 | 3.779.356 | 89 | 18 | 108 |
| 2020 | 2.674.914 | 71 | 17 | 156 |
| 2021 | 2.293.797 | 82 | 16 | 146 |
| 2022 | 2.363.615 | 77 | 24 | 218 |
| 2023 | 2.704.814 | 73 | 16 | 131 |
| 2024 | 3.002.710 | 72 | 21 | 223 |
| 2025 | 3.245.696 | 76 | 21 | 170 |

Os tamanhos e quantidades de hexágonos de diferentes recortes não são diretamente aditivos: os respectivos modelos PCA são diferentes, e o mapa histórico foi construído em um espaço PCA recalculado para toda a população consolidada.

### 4.1. Resultado de 2024 — Brasil

- **3.002.710** redações válidas.
- **72** hexágonos exibidos; **21** hexágonos omitidos por supressão primária.
- **3.002.487** redações representadas nas células exibidas.
- **223** redações em células suprimidas.
- Cobertura: **99,9925734%**.
- Hexágono de maior frequência: `(q=-1, r=0)`, centro `(PC1=-0,9526279; PC2=0)`, **327.466** redações, **10,905682%** do total nacional válido.
- Hexágono da origem `(q=0, r=0)`: **241.819** redações (**8,053358%**).
- Os dados exibidos não contêm pontos individuais nem identificadores de pessoas.

Para as **27 UFs de 2024**, os totais somados são **1.355 hexágonos exibidos, 724 suprimidos, 6.066 observações distribuídas entre os hexágonos suprimidos**. Esses números **não** devem ser subtraídos da distribuição nacional: cada UF usa sua própria PCA e hexágonos próprios.

### 4.2. Resultado histórico — Brasil, 2019–2025

- **20.064.902 participações com redações válidas**, não pessoas distintas.
- **88** hexágonos exibidos e **15** suprimidos.
- **20.064.733** participações nos hexágonos exibidos e **169** nos suprimidos.
- Cobertura: **99,9991577%**.
- A reprojeção foi feita no modelo histórico, não por soma ou média de mapas anuais.

## 5. Compatibilidade com os indicadores anteriores

- Correspondência exata de `n_validas` para os 224 recortes entre IND-016, IND-014 e IND-015.
- Variâncias explicadas de PC1 e PC2 iguais às do IND-014 para cada recorte.
- Matrizes de loadings e correlações PCA do dashboard de 2024 preservadas, de acordo com IND-015.
- Seções anteriores e estados de validação dos indicadores 001–015 presentes no dashboard de 2024.
- `pages.competencies.pca.scatter` contém os hexágonos de 2024 para Brasil e as 27 UFs.
- `pages.temporal.ind016` contém resumo anual e mapas históricos nacional/estaduais.
- `pages.methodology.ind016` explicita fonte, método, limiar, falta de amostragem, limitações de comparabilidade e bloqueio de publicação.
- Contrato JSON Schema v1.0.0 satisfeito.

A ocorrência anômala isolada de **SC/2023** foi preservada: competência C3 = 10 e diferença −30 entre soma das competências e nota total. Há exatamente uma divergência histórica, reportada nos recortes pertinentes, sem ajuste ou exclusão silenciosa.

## 6. Limitações metodológicas e ressalvas de privacidade

1. **Microdados não disponíveis:** não foi possível reprojetar independentemente as redações nem reproduzir de forma autônoma as atribuições PC1/PC2 aos hexágonos; a validação dos dados reais está limitada aos agregados recebidos e às referências IND-014/015. As checagens internas de momentos dos escores são relatadas pelo script produtor, mas não foram refeitas a partir dos registros individuais.
2. **Supressão complementar pendente:** ocultar células de 1–29 redações não elimina, por si só, risco de inferência indireta. O agregado informa o total de redações suprimidas; a divulgação cruzada por UF/ano deve passar por revisão especializada.
3. **Campo legado potencialmente ambíguo:** `quality.suppression.suppressed_cells = 0` do dashboard se refere ao controle legado do IND-001, **não** ao IND-016. Para 2024 o IND-016 informa expressamente **21 células nacionais suprimidas**. Recomenda-se rotular o escopo desse campo antes de publicar um painel geral, evitando a interpretação falsa de inexistência de células suprimidas.
4. **Comparabilidade limitada:** cada combinação de ano/UF/Brasil possui uma PCA específica; coordenadas iguais entre mapas diferentes não representam necessariamente o mesmo perfil. Sinais e orientações das componentes são convencionais.
5. **Unidade histórica:** participações em edições do ENEM, não pessoas únicas.
6. **Escopo do dashboard:** foi disponibilizado e auditado integralmente apenas o dashboard cumulativo de **2024**, não os outros seis arquivos cumulativos.
7. **Status de divulgação:** os artefatos continuam `draft`. A aprovação técnica para uso interno não equivale a aprovação acadêmica, de privacidade ou de divulgação pública.

## 7. Conclusão e encaminhamento

**Aprovado tecnicamente para uso interno — IND-016.** Nos **316.804 testes de consistência dos artefatos agregados** não foram encontradas divergências. A integração com os IND-014 e IND-015 e com o dashboard de 2024 permanece íntegra.

Próxima execução recomendada: **IND-017 — Perfis de competências (K-Means)**; em seguida, **IND-018 — Tamanho dos clusters**. Os scripts estão preparados, mas exigem execução com os microdados no ambiente do projeto e posterior validação dos resultados reais. Não executar atualizações simultâneas dos dashboards cumulativos.

---

**Artefatos de auditoria:** `auditoria_IND016.py` e `auditoria_IND016_resultados.json`, produzidos a partir dos três arquivos recebidos e dos módulos IND-014/015 disponíveis. Os dados originais dos participantes não foram disponibilizados ao auditor.
