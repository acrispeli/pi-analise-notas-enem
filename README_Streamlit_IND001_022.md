# Streamlit — Panorama da Redação no ENEM (IND-001 a IND-022)

**Projeto Integrador IV — UNIVESP**  
**Dados:** ENEM 2019–2025 · sete dashboards JSON cumulativos · situação `draft`  
**Escopo:** interface de visualização, sem recálculo dos microdados do INEP

## 1. Melhorias da versão

Esta versão foi elaborada após a revisão dos **sete PDFs enviados** pelo grupo (Visão geral, Notas, Competências, Relações e PCA, Perfis, Evolução temporal e Avaliação entre corretores).

| Aspecto observado | Mudança |
|---|---|
| Valores numéricos truncados nos cartões (ex.: `20.0...`) | Cartões da Visão geral passam a usar **duas colunas**, números em fonte responsiva e rótulos que podem quebrar linha |
| Gráficos parcialmente cortados à direita ao salvar PDF | Ajustes responsivos em gráficos Plotly, margens, tipografia e regra de **impressão em A4 horizontal** sem barra lateral |
| Evolução temporal impressa em aproximadamente 16 páginas | Organizada em **cinco abas**: Notas, Competências, Relações/PCA, Perfis e Correção; nenhum cálculo anterior removido |
| Avaliação entre corretores vazia | **IND-020, IND-021 e IND-022** integrados em quatro abas: diferença total, por competência, discrepâncias e série anual |
| Risco de confundir populações | Introduzida explicação explícita da diferença entre `POP_VALID` e `POP_EVALUATOR` |
| IND-016 mapa agregado | Preservado o mapa hexagonal agregado, com alerta de revisão de privacidade e seleção histórica/anual/UF |
| Indicadores futuros | Páginas **Alto desempenho, Contexto socioeconômico e Modelos futuros** continuam preparadas e vazias |

### A página Avaliação entre corretores

**IND-020 — Diferença total AV1 × AV2:** quantidade de avaliações pareadas, média, mediana, P90, histograma de percentual por classe e evolução por ano. As classes do histograma podem ter diferentes larguras; as alturas representam **percentual de avaliações**, não densidade por ponto.

**IND-021 — Diferença por competência:** C1–C5, gráfico de diferença média, boxplots gerados a partir de **quartis agregados** (sem pontos individuais), tabela de médias/medianas/P90 e série histórica de cinco linhas.

**IND-022 — Critério de discrepância do edital de 2024:** porcentagem e contagem de discrepâncias, classificações confirmadas/indeterminadas e proporções de cada critério. **Os três motivos podem se sobrepor.** Regra de 2024 aplicada de forma padronizada às sete edições, não como certificação de que todos os editais possuíam as mesmas regras.

Antes de renderizar os três indicadores, o código verifica os denominadores, o fechamento das classes dos histogramas, a presença das cinco competências e a partição dos casos. Se detectar inconsistência ou ausência de arquivos, **não apresenta números parciais como se fossem completos**.

## 2. Instalação no Windows (PowerShell)

1. Aguarde o término de quaisquer scripts de indicadores e interrompa o Streamlit em execução (`Ctrl+C`).
2. Faça backup dos arquivos `visualizador.py` e `painel_dados_enem.py` que estão na **raiz do projeto**, em `D:\pi-analise-notas-enem`.
3. Extraia o ZIP e copie **os arquivos `visualizador.py`, `painel_dados_enem.py` e `requirements_visualizador.txt` diretamente para essa raiz**. Não coloque os arquivos dentro de `src\indicadores`.
4. Mantenha seus sete arquivos existentes em `outputs\json\dashboard_enem_2019.json` até `dashboard_enem_2025.json`. **Nenhum indicador precisa ser recalculado.**
5. Execute no PowerShell, a partir da raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

6. No navegador, clique em **Atualizar dados** na lateral ou utilize o atalho `R` do Streamlit após a substituição. Abra **Avaliação entre corretores**.

**Importante:** o ZIP contém o **código atualizado** e testes. Não substitui os dashboards completos produzidos no seu computador. Se uma edição ou UF não for encontrada, a visualização correspondente ficará indisponível: **não** será preenchida artificialmente com dados de 2024.

### Arquivos do pacote

- `visualizador.py` — interface Streamlit IND-001…022;
- `painel_dados_enem.py` — leitura e validação dos recortes;
- `requirements_visualizador.txt` — dependências;
- `testes_visualizador_001_022.py` — testes reais dos recortes, usando o dashboard 2024 que já está na pasta outputs/json;
- `testes_renderizacao_001_022.py` — testes dos gráficos sem abrir o navegador;
- `README_Streamlit_IND001_022.md` — este documento;
- `REVISAO_VISUAL_PDFS_ENEM.md` — observações sobre os sete PDFs e limites de teste.

## 3. Testes opcionais

```powershell
.\.venv\Scripts\python.exe testes_visualizador_001_022.py
.\.venv\Scripts\python.exe testes_renderizacao_001_022.py
```

Os testes locais efetuados durante o desenvolvimento foram realizados com o dashboard **real de 2024** e com os módulos completos IND-020/021/022 disponíveis neste ambiente. A validação dos arquivos do computador do usuário depende da execução local.

## 4. Visualização, filtros e exportação de PDF

- O menu lateral contém as páginas; os filtros superiores começam em **Todos os anos** e **Todos os estados (Brasil)**.
- **Todos os anos** utiliza agregados históricos já computados. Não é média aritmética das médias anuais nem concatenação de PCA/K-Means de recortes diferentes.
- Em `Evolução temporal`, escolha uma das cinco abas; a impressão do navegador mostra a aba **ativa** (isso ajuda a evitar PDFs extremamente longos). Para arquivar todas as abas, salve uma impressão por aba.
- Para imprimir, escolha **A4, orientação horizontal/paisagem, escala 100% ou “ajustar à página”**, desabilite cabeçalhos/rodapés do navegador se desejar. O navegador/driver de impressão ainda pode alterar o layout; confira a prévia antes de salvar.
- As legendas e títulos descrevem os gráficos; quando o PDF fica visualmente cortado, isso pode refletir a conversão para impressão, e não dados ausentes.

## 5. Cautelas científicas e publicação

- A UF refere-se ao **local de prova**, não residência.
- O histórico contém **participações**, não pessoas únicas.
- `POP_VALID` define redações válidas; `POP_EVALUATOR` define avaliações com os dois totais válidos. Em 2024, os totais são diferentes e ambos são corretos dentro das respectivas populações.
- Diferenças absolutas entre AV1 e AV2 não provam erros. Os dados não identificam qual avaliador tem razão.
- O indicador 22 aplica os **limiares estritos** do edital de 2024 a todas as edições por comparabilidade. Sua taxa **não é uma taxa oficial publicada pelo INEP**.
- O mapa PCA IND-016 é formado por hexágonos agregados com supressão primária. Não contém pontos individuais, mas ainda requer revisão de privacidade complementar antes da publicação externa.
- Todos os resultados permanecem em **estado `draft`**. A ausência de identificadores nos microdados públicos não substitui a revisão da publicação de agregados e de eventuais deduções entre filtros.
- Os JSONs existentes são usados localmente. Nunca compartilhe arquivos de microdados brutos junto com o Streamlit.

**Status de teste:** verificação computacional dos recortes e gráficos concluída; **a interface final ainda deve ser aberta e conferida no navegador Windows da equipe**.
