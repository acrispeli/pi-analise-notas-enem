# Correção do reprocessamento — Lote 1 (IND-001/054)

## Motivo
O lote verificou 23 hashes, mas os scripts bloquearam o reprocessamento por já existirem saídas antigas.
O executor atual **já suporta** argumentos por indicador via `manifesto_indicadores_corrigidos.json`, então não é necessário substituir `executar_indicadores_lote.py`.

## Arquivos a copiar
Copie **somente**:
- `manifesto_indicadores_corrigidos.json` para a raiz do repositório;
- `src/indicadores/IND_016_mapa_pc1_pc2.py` para `src/indicadores/`;
- `src/indicadores/IND_020_diferenca_total_av1_av2.py` para `src/indicadores/`.

Outros scripts não são alterados. O manifesto passa `--sobrescrever` somente para os 21 scripts que o suportam. IND-001 e IND-034/980 mantêm os argumentos anteriores (`[]` e `--integrar`).

## Validação e execução
Primeiro execute o modo `--verificar` com os mesmos 23 identificadores. Somente depois do resultado `OK` em todos, execute `--executar` **sem IND-001** (já concluído).
Os scripts 016/020 passam a aceitar `--sobrescrever` e atualizar seus blocos, mantendo os outros indicadores nos dashboards.
O backup prévio está em `backups_reprocessamento/saidas_antes_20261029_213926.zip`. O executor cria outro automaticamente quando `--executar` é iniciado novamente.

## Precauções
- Não apagar CSV/JSON/dashboards existentes.
- Não usar `git add .` até decidir o que deve ser versionado.
- Se qualquer script falhar durante a execução, conservar logs e backup; resultados anteriores podem permanecer inalterados ou parcialmente atualizados por indicador.
- Esta alteração corrige o mecanismo de sobrescrita, não constitui homologação dos resultados reais.
