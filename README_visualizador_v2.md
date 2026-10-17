# Visualizador local ENEM — versão 2 (IND-001 a IND-004)

Este é um instrumento exploratório independente da interface oficial da equipe. Ele lê somente arquivos JSON **agregados** produzidos pela camada analítica; não relê os microdados do INEP.

## Instalação / atualização

1. Antes de substituir o arquivo, faça uma cópia de `visualizador.py` (por exemplo, `visualizador_anterior.py`) caso tenha alterações suas.
2. Extraia o arquivo `visualizador.py` do ZIP na **raiz** do repositório `D:\pi-analise-notas-enem`, substituindo o arquivo antigo. Não altere nem apague a pasta `outputs/`.
3. No PowerShell do VS Code, execute:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_visualizador.txt
.\.venv\Scripts\python.exe -m streamlit run visualizador.py
```

Se já estiver aberto, use o botão **Atualizar leitura dos JSONs** no menu lateral ou recarregue a página.

## Quais arquivos o painel lê?

Os arquivos obrigatórios permanecem:

- `outputs/json/IND_001_redacoes_validas.json`
- `outputs/json/IND_002_nota_media.json`

Arquivos opcionais, identificados assim que o script do indicador os cria:

- `outputs/json/IND_003_mediana_redacao.json` — acrescenta mediana ao painel, gráficos e tabelas.
- `outputs/json/IND_004_desvio_padrao_redacao.json` — acrescenta desvio-padrão populacional (`ddof=0`) ao painel, gráficos e tabelas.

**Você não precisa alterar o `visualizador.py` quando recalcular um desses quatro indicadores:** basta atualizar os JSONs usando os scripts e clicar em Atualizar leitura dos JSONs. O programa verifica as contagens e coerência básica antes de exibir módulos adicionais.

Se o IND-004 ainda não foi executado, o visualizador funciona normalmente com IND-001 a IND-003; nenhum valor de desvio-padrão é inventado.

## A partir do IND-005

O programa detecta novos arquivos com padrão `outputs/json/IND_###_*.json` e mostra seus nomes em **Método e qualidade**, mas **não cria automaticamente gráficos especializados**. A estrutura de um indicador de distribuição, por exemplo, difere de uma média; para cada novo tipo, precisamos integrar a visualização adequada após validar o JSON real. Os indicadores 001 a 004 já estão prontos para visualização.

## Cuidados

- Os resultados continuam como `draft`, sujeitos à revisão acadêmica.
- O consolidado conta participações, não pessoas únicas.
- A dimensão `SG_UF_PROVA` indica UF de aplicação, não residência.
- Visualizar dados não equivale a auditar o cálculo original.
- O painel é local e independente do dashboard definitivo.
