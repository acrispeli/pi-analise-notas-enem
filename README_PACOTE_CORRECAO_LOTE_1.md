# Correção seletiva do limiar de 30 — Lote 1

**Projeto Integrador IV — UNIVESP | revisão inicial em 29/10/2026**

Este pacote contém **23 arquivos Python corrigidos e verificados em ensaios sintéticos**. **Não representa a correção de todos os 54 indicadores.**

## O que foi modificado

- A regra de supressão automática por quantidade de 1 a 29 registros foi desativada nos indicadores entregues, restaurando contagens, faixas e categorias, quando aplicável.
- As interfaces dos arquivos foram preservadas, incluindo o IND-045 e os módulos IND-046 a IND-052.
- O recorte 980 mantém a nota **final** da competência e tratamento AV1/AV2/AV3/AV4.
- O IND-037 mantém mínimo de 30 **apenas para testes inferenciais**, distinto da publicação de contagens agregadas.
- O IND-053 e o IND-054 **não** foram alterados; suas restrições atuais de raridade e tamanho de cluster fazem parte da modelagem, não somente da divulgação.
- Indicadores que apenas geram avisos também não foram substituídos indiscriminadamente.

## Limites da verificação

- **15 autotestes de indicadores com dados sintéticos** e **9 ensaios focais de N=1** passaram, além de validação sintática de todos os arquivos do pacote.
- **Não houve reprocessamento dos microdados reais** ou homologação científica final.
- Permanecem indicadores fora do Lote 1: bloqueios condicionais, versões alternativas e estudos ML. **Não os inclua na execução noturna sem revisão.**
- O valor de N=1 pode ser estatisticamente instável mesmo quando o agregado é permitido. Um DP amostral com N=1 continua indefinido; p-valores seguem as regras específicas dos testes.
- A anonimização dos microdados públicos não garante risco zero de identificação por cruzamento. Este pacote elimina uma regra geral do projeto, não substitui análise contextual de divulgação.

## Instalação no projeto Windows

1. Já existe o backup `4872de5` na branch `backup-pre-revisao-supressoes` e o trabalho está na branch `correcao-supressoes-ind001-054`. Confira antes de substituir arquivos.
2. Extraia os arquivos **preservando a estrutura de pastas** para `D:\pi-analise-notas-enem`, substituindo apenas os scripts que o pacote contém. Não copie `src` para dentro de `src`.
3. Coloque `executar_indicadores_lote.py` e `manifesto_indicadores_corrigidos.json` diretamente na raiz do repositório.
4. **Antes de reprocessar, rode a verificação de hashes:**

```powershell
python executar_indicadores_lote.py --verificar --apenas 1,16,20,23,30,31,32,34,34/980,35,36,37,38,40,44,45,46,47,48,49,50,51,52
```

5. Somente se a verificação listar todos os scripts como OK, execute seletivamente (ainda não recomendado antes de concluir a auditoria dos dependentes fora do pacote):

```powershell
python -u executar_indicadores_lote.py --executar --apenas 1,16,20,23,30,31,32,34,34/980,35,36,37,38,40,44,45,46,47,48,49,50,51,52
```

O executor guarda backup das saídas, registra logs individuais, é sequencial e não faz `git push`. Se algum script falhar, os dependentes presentes na fila são bloqueados.

## Atenção sobre dependências

Para uma reconstrução integral sem supressões, também precisamos atualizar os indicadores condicionais fora deste lote. Em particular o IND-033 ainda requer validação. Os modelos IND-017 a 019, IND-028/029 e IND-053/054 exigem análise estatística de estabilidade antes de alterar limites de 30. **Não declare os 54 indicadores corrigidos ou homologados com esta entrega.**

## Próximo passo, um comando por vez

Após extrair o pacote, rode apenas o comando `--verificar`, envie o resultado e só então decidiremos o reprocessamento.
