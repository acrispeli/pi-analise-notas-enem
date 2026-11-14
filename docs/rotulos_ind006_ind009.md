# Rótulos dos indicadores IND-006 e IND-009

## Escopo

- **IND-006 — Distribuição das notas:** exibir percentuais sobre as dez colunas do histograma de faixas fixas, inclusive valores muito pequenos (por exemplo, 0,0004%). A exceção vale somente para esse indicador; demais gráficos mantêm o limite padrão de oito colunas.
- **IND-009 — Média das competências C1–C5:** exibir as notas diretamente nos marcadores das cinco curvas de 2019 a 2025 (até 35 valores), com fonte compacta, fundo branco semitransparente e deslocamentos diferentes por competência. A altura foi ampliada para 520 px para favorecer legibilidade.
- Dados numéricos, eixos, série temporal e hover permanecem iguais aos das fontes JSON.
- Em telas menores, as anotações do IND-009 podem ficar mais densas. O usuário pode ampliar o gráfico do Plotly para inspecionar e continuar utilizando o hover.

## Alterações

- `rotulos_marcadores_plotly.py`: função especializada `rotular_historico_competencias`; a regra geral para até três curvas continua intacta.
- `visualizacao_final_enem.py`: parâmetro `limite_vertical` no rotulador de colunas; formatação individual para percentuais pequenos, evitando 0,0% quando existe um valor pequeno não zero e evitando quatro casas desnecessárias em 24%.
- `painel_revisao_geral_68.py`: aplica as duas exceções nos renderizadores efetivos IND-006 e IND-009, antes da camada de acabamento.
- `tests/test_rotulos_ind006_ind009.py`: cinco testes (dados sintéticos, JSONs reais, 10 colunas, 35 pontos, valores preservados e gráfico inadequado).

## Verificação antes de publicar

No Windows, atualizar a branch e executar os testes:

```powershell
git fetch origin
git switch --track origin/feat/rotulos-ind006-ind009-20261114
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_rotulos_ind006_ind009.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_rotulos_barras_plotly.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app\visualizador.py --server.port 8506
```

Abrir `http://localhost:8506` e conferir:
- **Visão geral → IND-006 → Detalhamento por edição (2025):** percentuais visíveis nas dez colunas.
- **Competências → IND-009 → Todos os anos:** valores junto aos marcadores de C1–C5; verificar legibilidade em 2019–2025.

A `main` e o aplicativo público não são alterados até testes, inspeção visual e merge. Os PDFs finais anteriores continuam válidos, mas não incorporam estes novos rótulos sem recaptura.
