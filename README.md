# Panorama da Redação no ENEM — Projeto Integrador IV (UNIVESP)

Projeto acadêmico de análise exploratória dos microdados do **Exame Nacional do Ensino Médio (ENEM), edições de 2019 a 2025**, com foco nas notas da redação, nas competências avaliadas, na concordância entre avaliadores, em perfis socioeconômicos e na evolução dos indicadores ao longo do tempo.

O projeto reúne **68 indicadores selecionados**, técnicas de estatística e aprendizado de máquina e um painel interativo desenvolvido em **Python, Streamlit e Plotly**. Os indicadores **IND-060 a IND-063** não integram o catálogo atual de visualização.

> **Estado do projeto:** protótipo acadêmico em desenvolvimento e revisão. Os resultados são análises elaboradas pelo projeto a partir de dados públicos, **não indicadores oficiais publicados pelo INEP**. Alguns gráficos, inclusive o IND-012, ainda necessitam de validação visual. Os arquivos de resultados podem registrar o estado `draft`.

## Objetivo

Tornar dados agregados sobre a redação do ENEM mais acessíveis a estudantes, professores e pesquisadores, com gráficos, filtros por edição e unidade federativa de aplicação da prova e interpretações pedagógicas acompanhadas de limitações metodológicas.

## Organização dos indicadores

| Área do painel | Indicadores | Tema |
|---|---|---|
| Visão geral | IND-001–008 | Quantidades, médias, percentis, distribuição e situações da redação |
| Competências | IND-009–019 | C1–C5, correlações, PCA e perfis de desempenho |
| Avaliadores | IND-020–029 | Divergências, concordância e padrões atípicos de avaliação |
| Alto desempenho | IND-030–039 | Redações com notas elevadas e perdas de pontos |
| Contexto socioeconômico | IND-040–052 e 055–059 | Questionário socioeconômico, renda, escolaridade e perfis materiais |
| Padrões por ML | IND-053–054 | Dimensões e agrupamentos socioeconômicos |
| Evolução temporal | IND-064–068 | Tendências ao longo das edições |
| Metodologia | IND-069–072 | Qualidade, integração e proveniência dos dados |

## Como executar o painel localmente

Requisitos: Python compatível com as dependências descritas em `requirements_visualizador.txt` e acesso aos **JSONs agregados** utilizados pela aplicação.

No Windows / PowerShell, na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
$env:ENEM_MODO_INTERNO = "1"
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

O Streamlit exibirá o endereço local no terminal. O modo `ENEM_MODO_INTERNO` habilita páginas de trabalho e **não representa autorização para divulgação pública**. Consulte os arquivos de documentação antes de considerar uma implantação aberta.

**Dados necessários:** o painel utiliza resultados agregados de `outputs/json/`, incluindo os arquivos `dashboard_enem_2019.json` a `dashboard_enem_2025.json` e diversos arquivos `IND_*.json`. Se esses arquivos não estiverem incluídos no clone, será necessário obtê-los por um processo de distribuição previamente aprovado ou gerá-los com a cadeia local de processamento; não substitua uma edição ausente por dados de outra.

## Estrutura do código

```text
pi-analise-notas-enem/
├── visualizador.py                 # Entrada da interface Streamlit
├── painel_*.py                    # Componentes do painel e carregamento
├── graficos_educacionais_68.py   # Visualizações educacionais
├── leitura_acessivel_68.py       # Interpretações por regras
├── src/
│   ├── indicadores/              # Algoritmos dos indicadores
│   └── preparacao/               # Inventário e validação das bases
├── docs/                         # Catálogo e contratos de dados
├── tests/                        # Testes automatizados
├── outputs/json/                 # Resultados agregados (se distribuídos)
└── requirements_visualizador.txt # Dependências da interface
```

Há módulos adicionais no projeto em evolução. O catálogo vigente e sua distribuição por páginas estão em `docs/catalogo_navegacao_68.json`; a documentação técnica de integração está em `docs/`.

## Metodologia e limites de interpretação

- As análises são **exploratórias e descritivas**. Diferenças e associações entre variáveis não demonstram causalidade.
- A dimensão geográfica corresponde à **UF de realização da prova**, não necessariamente à residência do participante.
- O consolidado histórico contabiliza **participações em edições diferentes**, não indivíduos únicos acompanhados longitudinalmente.
- Algumas questões socioeconômicas, alternativas e faixas monetárias mudaram entre 2019 e 2025. Comparações exigem harmonização documentada.
- Algumas fontes públicas de 2025 não permitem o mesmo vínculo individual entre questionário e nota disponível em outras edições. Cruzamentos incompatíveis são declarados indisponíveis.
- As análises com PCA, MCA, K-Means e detecção de observações atípicas são técnicas estatísticas exploratórias; seus agrupamentos não devem ser interpretados como diagnóstico ou classificação definitiva de pessoas.
- As interpretações pedagógicas do painel são baseadas em **regras transparentes**, e não em um serviço de IA generativa.
- Os resultados devem passar por revisão acadêmica e de adequação à divulgação antes de publicação externa.

## Fontes dos dados

Os dados de origem são os **microdados públicos e documentação técnica do INEP**, incluindo o complemento de notas detalhadas dos avaliadores da redação. Os microdados brutos e eventuais dados intermediários individuais **não devem ser versionados neste repositório**. Consulte as informações e dicionários disponíveis no portal oficial do INEP.

## Testes e contribuições

Os testes encontram-se em `tests/` e em alguns scripts de validação mantidos na raiz. Uma execução geral pode ser iniciada com:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Alguns testes dependem de módulos e resultados locais que não fazem parte de uma distribuição reduzida. Antes de contribuir, confirme a compatibilidade do ambiente e execute os testes diretamente relacionados aos arquivos modificados.

## Situação e uso responsável

Este repositório documenta um **Projeto Integrador IV da UNIVESP**. Seu conteúdo não deve ser apresentado como resultado oficial do INEP nem como aplicação validada para decisões individuais sobre estudantes ou professores. A eventual publicação pública do painel, dos arquivos agregados e a definição de uma licença de reutilização exigem avaliação específica pela equipe do projeto.
