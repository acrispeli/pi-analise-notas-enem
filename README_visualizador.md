# Visualizador local de indicadores ENEM

Painel exploratório em Streamlit, independente do dashboard oficial. Mostra **IND-001** e **IND-002** para 2019–2025, Brasil e 27 UFs, com evolução temporal, rankings e tabelas para download.

## Arquivos necessários

Copie `visualizador.py` e `requirements_visualizador.txt` para a **raiz** de `D:\pi-analise-notas-enem` (ao lado de `.gitignore` e `src`). O programa acessa os JSONs já produzidos:

```text
pi-analise-notas-enem/
├── visualizador.py
├── requirements_visualizador.txt
├── outputs/
│   └── json/
│       ├── IND_001_redacoes_validas.json
│       └── IND_002_nota_media.json
└── src/
    └── indicadores/
```

Os CSVs de microdados não são usados pelo visualizador.

## Instalação e execução no PowerShell do VS Code

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

O terminal mostrará um endereço local como `http://localhost:8501`. Pressione `Ctrl+C` no terminal para encerrar.

## Como usar

- No menu lateral, escolha um **ano**, ou `2019–2025 (consolidado)`.
- Escolha **Brasil** ou uma **UF de aplicação**.
- Consulte os quatro painéis: visão geral, evolução, comparação entre UFs, método e qualidade.
- O botão **Atualizar leitura dos JSONs** relê os arquivos após novos cálculos. A leitura também é atualizada quando o arquivo é modificado.
- Os botões de download exportam apenas as tabelas agregadas visualizadas.

## Limites e cuidados

- Os arquivos de entrada ainda estão marcados como `draft` (validação técnica, não publicação acadêmica).
- O total consolidado entre 2019 e 2025 conta **participações**, não pessoas únicas.
- A média consolidada é **ponderada pelo número de redações válidas**.
- A dimensão geográfica é `SG_UF_PROVA`, isto é, UF de aplicação, não de residência.
- Para 2025 não há junção individual entre a base de participantes e a base de resultados; ela não é necessária para esses dois indicadores.

O painel é um instrumento de conferência local, não deve substituir os JSONs oficiais que serão consumidos pela interface da equipe.
