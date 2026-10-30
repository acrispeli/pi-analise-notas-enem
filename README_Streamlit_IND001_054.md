# Streamlit ENEM — atualização IND-046 a IND-054 e IND-034/980

## Objetivo

Esta entrega atualiza **somente a camada de apresentação** do visualizador ENEM 2019–2025 do Projeto Integrador IV — UNIVESP. Mantém os indicadores já exibidos (IND-001 a IND-045), acrescenta a seção **Novos indicadores · 046–054** e o complemento **IND-034 · nota final 980** dentro de Alto desempenho.

## Arquivos alterados e novos

Copiar estes **três arquivos**, a partir da pasta raiz do ZIP, para a **raiz** de `D:\pi-analise-notas-enem\`:

| Arquivo | Ação |
|---|---|
| `visualizador.py` | Substituir a versão anterior, mantendo um backup |
| `painel_visualizacoes_novas.py` | Substituir a versão anterior, mantendo um backup |
| `painel_indicadores_046_054.py` | Adicionar como arquivo novo |

O arquivo `testes_streamlit_ind046_054.py` é opcional na raiz para executar os testes. O arquivo `painel_dados_enem.py` e `painel_indicadores_recentes.py` **não foram modificados por esta entrega**; devem continuar presentes no seu repositório.

**Importante:** se você realizou mudanças manuais em `visualizador.py` ou `painel_visualizacoes_novas.py` desde a última atualização IND-045, faça uma comparação antes de substituir. Os arquivos deste pacote partem da versão IND-045 enviada anteriormente neste projeto.

## Antes de publicar os gráficos

Os novos scripts indicadores precisam ter concluído o processamento dos microdados e integrado seus respectivos blocos aos arquivos locais `outputs/json/dashboard_enem_2019.json` até `dashboard_enem_2025.json`. **Copiar somente os arquivos Python de visualização NÃO produz os dados dos indicadores.**

- **IND-046 a IND-051:** `pages.socioeconomic` nos dashboards correspondentes de 2019 a 2024; sem associação válida em 2025 nas fontes usadas no projeto.
- **IND-052:** `pages.socioeconomic.uf_performance` de 2019 a 2025, inclusive em 2025.
- **IND-053:** `pages.ml.socio_mca` com MCA anual e modelo de núcleo harmonizado quando gerado. Utilizar a versão corrigida do IND-053 para evitar o `OverflowError` do `int8`.
- **IND-054:** `pages.ml.socio_clusters` com K-Means anual e agrupamento harmonizado, quando calculado.
- **IND-034/980:** `pages.high_performance.single_blocker.recorte_980_nota_final_brasil`, integrado pelo script complementar **com `--integrar`**. O IND-034 original permanece intacto.

O visualizador **não** substitui dados ausentes por resultados de outros anos, e não lê microdados individuais. Módulos ainda não integrados apresentam mensagem de indisponibilidade.

## Testar sem abrir o Streamlit

No PowerShell, com a `.venv` ativa, dentro da raiz do repositório:

```powershell
python testes_streamlit_ind046_054.py
```

Resultado esperado: `AUTOTESTES PAINEL IND-046..054 E IND-034/980: APROVADOS`.

## Testar a aplicação localmente

```powershell
python -m streamlit run visualizador.py
```

No menu lateral, abra **Novos indicadores · 046–054**. Há quatro abas: Cruzamentos socioeconômicos, UF da prova, MCA e Clusters. Use o filtro **Ano** para gráficos de uma edição ou **Todos os anos** para disponibilidade, série IND-052 e modelos harmonizados já existentes.

Na página **Alto desempenho**, escolha um ano, abra a aba **Competência única · 034** e procure o gráfico **Recorte exclusivo: redações com nota final 980**. O filtro de UF não modifica esse recorte, pois ele foi gerado apenas para o Brasil.

## Publicação no GitHub e Streamlit Community Cloud

Depois de revisar os arquivos e verificar a execução local, adicione **somente** os três arquivos de visualização, o teste e os dashboards de dados efetivamente atualizados ao Git. Faça commit e push. A aplicação do Streamlit Community Cloud vinculada à branch `main` poderá então atualizar a interface usando os JSONs enviados.

> Se os indicadores já foram calculados localmente mas seus `dashboard_enem_*.json` não foram enviados ao GitHub, os respectivos gráficos continuarão indisponíveis na aplicação publicada.

## Transparência e metodologia

- Os IND-046 a IND-051 não criam estimativas para 2025. Variáveis socioeconômicas diferentes entre edições não são harmonizadas implicitamente.
- O IND-052 analisa **UF da prova**, que pode não ser UF de residência.
- A MCA mede **inércia**, não variância PCA; os grupos C1–Ck do IND-054 **não são** as competências C1–C5 da redação e **não correspondem** diretamente de um ano para outro.
- O recorte 980 emprega as notas finais `NU_NOTA_COMP1..5` e não recalcula a avaliação definitiva a partir dos avaliadores.
- Os arquivos dos indicadores podem conter valores `null` (supressões existentes). Esta atualização **não modifica a política de divulgação ou as regras de supressão dos indicadores**; a discussão sobre grupos de menos de 30 registros ficará para outra etapa, conforme solicitado.
- Os indicadores podem apresentar `draft`: processamento concluído não significa necessariamente homologação final.
