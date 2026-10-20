# Correção do mapa IND-016 — Streamlit, ENEM 2019–2025

## Problema corrigido

1. A versão anterior bloqueava o mapa sempre que `status_privacidade` era diferente de `aprovado_publicacao`, inclusive na exploração interna.
2. Para o filtro de **ano específico + Brasil**, a versão anterior consultava `pages.temporal.ind016.national_by_year`, que contém **somente resumo**, sem `points`.
3. A versão anterior representaria os hexágonos como círculos em um gráfico de dispersão. A nova versão desenha **hexágonos verdadeiros**, com dimensões baseadas no `raio_hex` já publicado.

## O que mudou

**Dois arquivos são substituídos**, sem reprocessamento de microdados:

- `visualizador.py`: desenha os hexágonos com Plotly, legenda de intensidade (escala logarítmica), informações resumidas e nota de revisão de privacidade. A página **Relações e PCA** e a página **Evolução temporal** exibem o IND-016.
- `painel_dados_enem.py`: `obter_hexbin_ind016()` usa a fonte correta em cada caso e `validar_hexbin_ind016()` impede mostrar dados inconsistentes ou células abaixo do limiar de 30 redações.

| Filtros | Fonte do gráfico |
|---|---|
| Todos os anos + Brasil | `pages.temporal.ind016.period_total` |
| Todos os anos + UF | `pages.temporal.ind016.period_by_uf` |
| Ano específico + Brasil | `pages.competencies.pca.scatter.brasil` do `dashboard_enem_ANO.json` |
| Ano específico + UF | `pages.competencies.pca.scatter.by_uf` do `dashboard_enem_ANO.json` |

**Atenção:** os quatro tipos de recorte são PCA ajustadas independentemente. Não misture coordenadas de diferentes modelos em um único gráfico. “Todos os anos” mostra a PCA histórica própria, não uma soma de mapas anuais.

A nova versão **não exibe nenhuma linha individual de participante**. Apenas células que já aparecem na saída agregada do IND-016 são desenhadas. São mantidas as supressões primárias (contagens inferiores a 30), mas **a revisão de privacidade complementar permanece pendente para publicação externa**. Portanto, usar esta versão para análise interna ou demonstração restrita não constitui aprovação para tornar o painel público.

## Instalação no projeto local (PowerShell)

1. Aguarde a conclusão dos scripts de indicadores que estejam escrevendo os dashboards.
2. Feche o Streamlit em execução (`Ctrl+C`).
3. Faça uma cópia de segurança dos arquivos na raiz de `D:\pi-analise-notas-enem`:

```powershell
Copy-Item .\visualizador.py .\visualizador_backup.py
Copy-Item .\painel_dados_enem.py .\painel_dados_enem_backup.py
```

4. Extraia o ZIP e **substitua somente** `visualizador.py` e `painel_dados_enem.py` no diretório raiz (ao lado de `outputs`). O ZIP também contém documentação e testes; os outros arquivos podem ser mantidos.
5. Execute:

```powershell
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

Se for a primeira instalação do Streamlit, instale as dependências:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
```

6. No navegador, selecione **Relações e PCA** no menu à esquerda. O mapa aparece após os gráficos IND-013, IND-014 e IND-015. Escolha o **Ano** e o **Local da prova** no topo. O mesmo mapa também aparece na página **Evolução temporal**.

Se não aparecer após atualizar os arquivos, pressione **Atualizar dados** no menu lateral para limpar o cache do Streamlit. Confira se `outputs/json` contém o dashboard anual correspondente ao filtro.

## Testes executados

Usando o dashboard real de 2024 e o JSON modular agregado do IND-016:

- 737 verificações específicas de segurança, consistência e leitura;
- 1.241 verificações da interface anterior preservadas;
- 124 gráficos renderizados no teste isolado com substituto de Streamlit (sem servidor web);
- validação de **224 recortes agregados** do IND-016 (2019–2025 + histórico; Brasil + 27 UFs);
- Brasil/2024: **72 hexágonos exibidos**, 21 omitidos; 3.002.487 redações representadas das 3.002.710 válidas;
- histórico nacional: **88 hexágonos exibidos**;
- sem acesso à execução real do Streamlit em Windows: conferir o layout no navegador local.

**IND-020 e IND-021 não são exibidos.** Os indicadores IND-001 a IND-019 e as demais páginas foram mantidos.
