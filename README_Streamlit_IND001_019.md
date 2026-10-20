# Visualizador de redações do ENEM — Streamlit (IND-001 a IND-019)

## Objetivo

Esta atualização substitui **apenas a interface local do Streamlit**. Não modifica os scripts, microdados, agregados ou métodos de cálculo dos indicadores. O visualizador usa somente os JSONs cumulativos `dashboard_enem_2019.json` ... `dashboard_enem_2025.json` gerados pelos indicadores.

O resultado foi pensado para leitura por professores de Língua Portuguesa, avaliadores e outros interessados, mas **a publicação externa definitiva ainda depende da revisão acadêmica e de privacidade dos dados**.

## Instalação no projeto Windows

1. **Pare o Streamlit anterior**, se estiver aberto (`Ctrl+C` no PowerShell). Não precisa interromper a execução dos indicadores, pois os novos arquivos do painel não sobrescrevem os JSONs.
2. Faça uma cópia de segurança do `visualizador.py` atual caso tenha feito alterações próprias.
3. Copie estes três arquivos para a raiz do projeto `D:\pi-analise-notas-enem`:

   - `visualizador.py` (substitui a interface anterior)
   - `painel_dados_enem.py` (novo módulo de leitura dos JSONs)
   - `requirements_visualizador.txt` (bibliotecas)

4. Confirme que a pasta `outputs/json/` contém os dashboards cumulativos. Não apague nem mova os arquivos de resultados.
5. No PowerShell aberto na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

## Páginas no menu lateral

- **Visão geral:** KPIs, histograma de notas, evolução da média e percentis (IND-001 a IND-006).
- **Notas e distribuição:** redações válidas, média, mediana, dispersão, percentis, histogramas, situações da redação, nota 1.000 (IND-001 a IND-008).
- **Competências:** média, mediana, desvio-padrão, IQR e faixas de notas C1–C5 (IND-009 a IND-012).
- **Relações e PCA:** correlações de Spearman/Pearson, variância explicada, loadings e indicação de mapa PCA (IND-013 a IND-016).
- **Perfis de redação:** centroides, participação da população válida por cluster, qualidade dos agrupamentos e comparação de k para o Brasil (IND-017 a IND-019).
- **Evolução temporal:** séries por ano das medidas compatíveis com comparação temporal e avisos para modelos que não devem ser comparados diretamente.
- **Páginas reservadas:** Avaliação entre corretores (IND-020/021 **não exibidos**), Alto desempenho, Contexto socioeconômico e Modelos futuros.
- **Metodologia:** dicionário interpretativo e limitações.

## Filtros globais

No topo da página aparecem os campos **Ano** e **Local da prova**.

Ao iniciar:

- **Todos os anos** usa os agregados históricos de 2019 a 2025 (incluindo modelos históricos próprios para PCA e K-Means), não a média ingênua de resultados anuais.
- **Todos os estados (Brasil)** usa o agregado nacional (`BR`), não a média simples das UFs.

Se selecionar uma UF e um ano, o programa exige o arquivo `dashboard_enem_<ano>.json` correspondente. **Não substitui dados ausentes por valores de outros anos.** Para séries de uma UF, mostra apenas anos cujos dashboards existem, sinalizando quando faltam arquivos.

Use o botão **Atualizar dados** na lateral para recarregar os arquivos se um indicador terminar de executá-los com o visualizador aberto.

## Fonte dos dados

```text
D:\pi-analise-notas-enem\
├── visualizador.py
├── painel_dados_enem.py
├── requirements_visualizador.txt
└── outputs\
    └── json\
        ├── dashboard_enem_2019.json
        ├── dashboard_enem_2020.json
        ├── dashboard_enem_2021.json
        ├── dashboard_enem_2022.json
        ├── dashboard_enem_2023.json
        ├── dashboard_enem_2024.json
        └── dashboard_enem_2025.json
```

O script também procura dashboards diretamente em `outputs/` ou na raiz, se não os encontrar em `outputs/json/`. Os arquivos IND-020 e IND-021 são **deliberadamente ignorados**.

## Política para a prévia externa

Os relatórios atuais estão marcados como `draft`. O visualizador não lê identificadores, respostas ou microdados; usa apenas agregados. Além disso:

- Contagens positivas de 1–29 são omitidas em visualizações específicas, ou agrupadas em faixas mais amplas.
- O indicador de notas 1.000 oculta quantidades positivas inferiores a 30.
- Situações de redação pouco frequentes são reunidas em "Outras situações".
- O mapa do IND-016 **não é publicado enquanto a supressão complementar dos hexágonos estiver pendente** (o título e sua explicação permanecem visíveis).
- A agregação no visualizador não substitui o controle sistemático de divulgações por diferenças entre tabelas, anos e UFs; a revisão formal de privacidade é obrigatória antes da publicação pública.

## Testes incluídos

Os arquivos `testes_visualizador_001_019.py` e `testes_renderizacao_visualizador.py` podem ser executados opcionalmente. Para executá-los isoladamente, copie o `dashboard_enem_2024.json` ao lado deles, junto com `painel_dados_enem.py`, e use:

```powershell
.\.venv\Scripts\python.exe testes_visualizador_001_019.py
.\.venv\Scripts\python.exe testes_renderizacao_visualizador.py
```

Os testes de renderização não são um teste visual de navegador e não substituem o teste manual com o Streamlit executando no Windows.

## Observações científicas

- A UF é `SG_UF_PROVA`, local de realização do exame, não UF de residência.
- O consolidado conta participações, não pessoas únicas.
- Médias, medianas, dispersões, correlações e percentis históricos são extraídos dos agregados oficiais do pipeline do projeto; **não são recalculados pelo painel**.
- Os perfis do IND-017 são ajustados separadamente em cada recorte. P1–P4 não devem ser comparados automaticamente entre recortes.
- A comparação nacional do IND-019 indicou melhor separação interna com `k=2` nos períodos examinados; `k=4` segue como hipótese exploratória para análise pedagógica, não como escolha estatisticamente comprovada.

## Atualização do IND-016 (mapa PCA agregado)

Esta distribuição contém a correção de leitura e exibição do IND-016. Os hexágonos (e não redações individuais) aparecem em **Relações e PCA** e **Evolução temporal**. Seleções específicas de ano são recuperadas dos dashboards anuais; “Todos os anos” utiliza o modelo histórico independente. Células abaixo de 30 redações permanecem omitidas. A visualização é apropriada para exploração interna; a revisão complementar de privacidade segue pendente antes de publicação externa. Consulte `README_CORRECAO_MAPA_IND016.md`.
