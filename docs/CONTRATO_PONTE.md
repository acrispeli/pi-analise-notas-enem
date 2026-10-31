# Ponte por participante exigida para IND-055–063 e IND-068

## Por que não existe automaticamente?

O IND-054 exporta o resultado agregado de MCA+K-Means por ano e do núcleo harmonizado, mas não divulga as etiquetas de cluster de cada participante. Os IDs `C1`, `C2` etc. de modelos **anuais** são locais, NÃO comparáveis temporalmente.

Logo, não é correto simplesmente relacionar os dados por UF/ano ou juntar as estatísticas do IND-054 com as notas de outra base. Deve-se **reconstituir/validar a projeção em um modelo fixo** com as mesmas categorias, MCA, centroides, seed e amostra publicados e só então associar por inscrição legítima.

## Pré-requisitos

1. Validar taxa de junção, exclusividade das inscrições e `NU_ANO` com IND-069, 2019–2024.
2. Reconstruir o modelo `pooled_core_clusters` (14 conceitos harmonizados) do IND-054 e validar `k`, dimensões, centroides, regras de categorias raras e N contra o JSON real antes de projetar novas linhas.
3. Aplicar a transformação e os centroides FIXOS a cada participante, nunca recalculando um modelo independente para cada ano e chamando o cluster `C1` de equivalente.
4. Juntar escores reais/competências da mesma edição por `NU_INSCRICAO` validado. 2019–2023: MICRODADOS e, quando necessário, COMPETENCIAS; 2024: PARTICIPANTES e COMPETENCIAS; 2025: **sem ligação com notas**.
5. Amostrar de modo determinístico quando necessário; documentar se o recorte representa apenas amostra e não todos os participantes.

Este pacote **não inclui uma implementação de reprojeção de todos os participantes**: a validação de equivalência dos centroides e das modalidades exige as versões reais corrigidas do IND-053/054 após o Lote 2 e as fontes originais. A etapa deve ser preparada e auditada antes do reprocessamento dos indicadores dependentes.

## Estrutura exigida, apenas LOCAL (não versionar no Git)

`data/derived/ponte_<ano>.csv` (delimitador `;`, UTF-8):

`ano;id_registro;uf;cluster_ref;nota_redacao;c1;c2;c3;c4;c5;av1;av2;Q001;Q002;...`

`id_registro` é identificador pseudônimo **único por ano**, preferivelmente hash irreversível do identificador de origem e do ano. As informações são necessárias apenas na ponte local e **não devem aparecer nos CSVs/JSONs de indicadores**. Para 2025 são permitidos apenas `ano,id_registro,uf,cluster_ref,Q...` — sem notas. Para IND-059 AV1/AV2 devem existir e ser provenientes de corretores da mesma redação, não dados inferidos.

Manifesto de controle em `data/derived/manifesto_ponte_socio_cluster.json`:

```json
{
  "schema_version": "ponte-socio-cluster-fixo-v1",
  "modelo_referencia": "IND-054:pooled_core_clusters:HASH_REAL_VALIDADO",
  "validacao_mca_clusters": "aprovado",
  "anos": {
    "2019": {
      "arquivo": "data/derived/ponte_2019.csv",
      "sha256": "SHA256_REAL_DO_ARQUIVO",
      "n_registros": 0,
      "join_qa": "ok",
      "unicidade_qa": "ok"
    }
  }
}
```

O manifesto é um **contrato**, não um atestado automático de validade. Declarações falsas ou pontes construídas com clusters inventados invalidam os resultados.

## Regras de proteção

- Não publicar, commitar ou enviar a terceiros as pontes por participante.
- Não publicar modelos/predições/IDs individuais; os CSVs produzidos são agregados.
- Comparações de clusters são exploratórias/descritivas, não causais.
- IND-055 a 063 e IND-068 não devem gerar números quando o modelo de origem não puder ser reproduzido.
