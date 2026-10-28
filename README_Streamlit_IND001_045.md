# Streamlit ENEM — IND-001 a IND-045 (Projeto Integrador IV, UNIVESP)

**Atualização de 28/10/2026**. Preserva as telas legadas de IND-001 a IND-031 e IND-040/041 e amplia duas páginas:

- **Alto desempenho:** IND-032 (frequência), IND-033 (participação nas perdas), IND-034 (competência única), IND-035 (combinações de descontos), IND-036 (Apriori), IND-037 (Q de Cochran/Friedman e pós-testes), IND-038 (concordância entre AV1/AV2 e kappa) e IND-039 (heatmap de nota × competência). IND-030 e IND-031 continuam na mesma página.
- **Contexto socioeconômico:** IND-042 (renda × competências), IND-043 (escolaridade dos responsáveis × nota total), IND-044 (escolaridade × competências) e IND-045 (tipo de escola × nota). IND-040/041 permanecem na mesma página.

## Arquivos para a raiz do repositório

| Arquivo | Ação |
|---|---|
| `visualizador.py` | Substituir pelo atualizado |
| `painel_indicadores_recentes.py` | Substituir; suporta os novos blocos, inclusive o formato em lista do IND-038 |
| `painel_visualizacoes_novas.py` | **Adicionar**; implementa gráficos e tabelas IND-032–039 / IND-042–045 |
| `painel_dados_enem.py` | A mesma versão preservada do último ZIP analisado; não requer alteração |
| `testes_streamlit_ind032_045.py` | Adicionar para verificação local |
| `requirements_visualizador.txt` | Dependências existentes preservadas |
| `streamlit_app/visualizador.py` | Ponto de entrada preservado, sem mudança funcional |
| `streamlit_app/requirements.txt` | Dependências existentes preservadas |

**Não substitua** os arquivos em `outputs/json/` ou `outputs/indicadores/` com este pacote; mantenha os resultados que você já processou. Os gráficos utilizam os blocos incorporados a `outputs/json/dashboard_enem_2019.json` a `dashboard_enem_2025.json`. JSONs individuais, separados dos dashboards, não são carregados automaticamente: se um indicador não está integrado ao dashboard de um ano, a página informa indisponibilidade e não copia dados de 2024.

## Instalação e execução (PowerShell)

```powershell
cd D:\pi-analise-notas-enem
.\.venv\Scripts\python.exe -m pip install -r streamlit_app\requirements.txt
.\.venv\Scripts\python.exe testes_streamlit_ind032_045.py --ano 2024
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

O ponto de entrada em Streamlit Community Cloud pode continuar `streamlit_app/visualizador.py`. Ele chama o `visualizador.py` da raiz do repositório e reconhece os novos módulos por importação.

## Filtros e critérios

- Selecione um **ano específico** para visualizar os IND-032–039 e IND-042–045 em abas; Brasil/UF é aplicado ao ano escolhido.
- Para **Todos os anos**, os gráficos exibem apenas séries verdadeiramente comparáveis e disponibilidade de dados. Não há estimativa para anos ausentes.
- No IND-038, o JSON do dashboard contém uma **lista de linhas por UF e competência**, não o bloco `brasil/by_uf`; essa particularidade é tratada pelo leitor atualizado.
- As faixas de renda mudam de valores monetários no tempo. IND-045 usa `TP_ESCOLA` em 2019–2023 e `Q023` em 2024, com conceitos não diretamente comparáveis. A interface evita misturar esses grupos numa série única.
- IND-036 e IND-037 mostram as políticas revistas de divulgação. IND-039 exibe agregados com contagens de 1–29. **A versão permanece `draft`:** publicar externamente requer revisão acadêmica e de divulgação; anonimização da origem, isoladamente, não garante anonimato de quaisquer cruzamentos.
- Valores `p=0` do IND-037 são mostrados como limites numéricos, não como probabilidade literalmente zero.

## Testes realizados neste pacote

- Compilação Python dos 4 módulos de aplicação e do script de teste.
- Leitura de dashboard real de 2024 com **Brasil, São Paulo, Acre e Roraima**: **110 verificações funcionais aprovadas**, de 12 a 13 figuras Plotly por recorte.
- Simulação de execução da navegação principal nas páginas Alto desempenho, Contexto socioeconômico e Metodologia.
- Testes de acesso aos dados em 2019–2025 usando os arquivos disponíveis no ambiente de geração. Onde não havia resultados novos no dashboard, a interface mostrou indisponibilidade sem importar informações de outro ano.

**Limite de teste:** o ambiente de geração não tinha o pacote Streamlit instalado; a integração da aplicação foi executada com uma interface simulada e com Plotly real, não em navegador. Recomenda-se conferir a aparência e os filtros executando `streamlit run` no computador.
