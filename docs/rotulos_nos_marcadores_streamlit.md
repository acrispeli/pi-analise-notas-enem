# Rótulos fixos nos marcadores de séries curtas (Streamlit)

## Comportamento

- Linhas com até **8 pontos por série** e até **3 séries** exibem o valor junto à bolinha (não apenas no eixo ou no hover).
- Valores são apenas formatados para exibição em **pt-BR** (vírgula decimal, ponto de milhar); as notas e contagens originais nos JSONs não são modificadas.
- A primeira série recebe rótulos acima dos pontos, a segunda abaixo e a terceira à direita, diminuindo a chance de sobreposição.
- **Implementação atualizada:** os valores são anotações do layout Plotly, fixadas às coordenadas de cada bolinha; a primeira versão com `lines+markers+text` passou nos testes, mas não apareceu no navegador do usuário em `localhost:8502`. Anotações independem do texto interno do traço.
- Gráficos densos, como os cinco percentis P25–P95 mostrados simultaneamente, seguem com hover e legenda; não são preenchidos com textos que se sobrepõem.
- Ausências seguem vazias. O hover permanece ativo.

## Onde foi aplicado

- `graficos_educacionais_68.py`: históricos dos IND-002, 003 e 004.
- `painel_socio_040_055_059.py`: históricos de perfis materiais M1–M3 dos IND-055, 056, 057, 058 e 059 (respeitando o máximo de 3 séries).
- `painel_revisao_geral_68.py`: outros gráficos de linha curtos do catálogo, automaticamente pelo método comum `_tracar`; séries longas/densas permanecem inalteradas.
- `painel_paginas_contrato_68.py`: séries curtas do visualizador genérico de reserva.
- `rotulos_marcadores_plotly.py`: regra compartilhada e testável.

## Validação local

Na branch `feat/rotulos-marcadores-streamlit-20261114`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_rotulos_marcadores_plotly.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_graficos_didaticos_consolidados.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app\visualizador.py --server.port 8501
```

**Após atualizar o branch, reiniciar o servidor em porta NOVA (ex.: 8503) para evitar reutilizar um processo Python com módulos antigos.** Conferir visualmente **IND-002** em Todos os anos (2019–2025) e **IND-055** em Contexto socioeconômico. O gráfico deve manter seus valores, cores, título e hover e acrescentar rótulos junto aos marcadores. Também conferir um gráfico denso como IND-005 para garantir legibilidade.

## Publicação e relatórios

O código fica na branch de desenvolvimento até aprovação da PR; a aplicação pública, vinculada à `main`, não é alterada enquanto não houver merge.

Os PDFs já gerados continuam válidos. Para incluir os rótulos nesses documentos será necessária **nova captura**, pois `--retomar` reaproveita os PDFs existentes. Isso é opcional e não deve ser confundido com alteração das estatísticas.
