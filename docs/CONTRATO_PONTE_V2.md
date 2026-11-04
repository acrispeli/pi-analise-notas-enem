# Contrato de integração — ponte socioeconômica V2 (IND-055..063 e IND-068)

## Estado e escopo

**Situação atual:** *CANDIDATA; auditoria técnica concluída; revisão acadêmica, seleção por notas e privacidade contextual ainda pendentes.* Não há aprovação automática nem liberação de indicadores a partir deste pacote.

O IND-054 histórico é um modelo distinto, com 14 conceitos ativos, treinamento conjunto e K original = 2; não deve ser substituído nem descrito como se gerasse os três clusters V2. O modelo alternativo V2 usa 10 variáveis ativas de condições domiciliares e bens, mantém quatro perguntas relativas a escolaridade/ocupação dos responsáveis como descritivas, usa três dimensões MCA e K-Means K = 3, amostra determinística n = 104.752 em 2019–2025.

A V2 foi reproduzida e teve pontes individuais locais auditadas, preservando os registros e notas da candidata V1, com exceção deliberada do campo `cluster_ref`. Os arquivos estão exclusivamente em `data/derived/candidata_ponte_socio_v2_individual/`.

## Contratos coexistentes

- Original: `data/derived/manifesto_ponte_socio_cluster.json`, esquema `ponte-socio-cluster-fixo-v1`. Não criar falsamente com referência à V2.
- **V2 homologada, SOMENTE após decisões externas:** `data/derived/manifesto_ponte_socio_v2_homologada.json`, esquema `ponte-socio-10-ativas-homologada-v2`. O manifesto aponta para as pontes originais da candidata V2, inclui SHA256, contagens, tipo e identificador de modelo e três pareceres fundamentados, e só pode ser criado pelo comando explicitamente solicitado com pareceres concluídos.
- Candidata V2: `data/derived/candidata_ponte_socio_v2_individual/manifesto_candidato_v2.json`; seu status **deve permanecer** `candidato_nao_aprovado` para manter a trilha de auditoria.

No código compartilhado adaptado, `bridge_manifest()` verifica a V2 homologada, se houver, e recusa qualquer estado inconsistente. Se não houver, aplica o contrato original sem inferir aprovação da candidata. `bridge_data()` verifica hash do arquivo real, unicidade por edição, UF e ano, campos de notas e limites. Em 2025, `join_qa = nao_aplicavel_sem_notas`: não existe vínculo individual legitimo de nota × questionário e jamais deve ser escrito `join_qa = ok` como se essa junção tivesse ocorrido.

## Deliberações pendentes

1. **Metodologia:** revisar o significado dos grupos à luz dos dicionários; C3 é pequeno (3,67% da amostra); comparar K=3 com alternativas (K=4 melhor Davies-Bouldin); diferenciar padrões de bens da classe social/renda.
2. **Representatividade:** confrontar distribuição da amostra e da população (marginais de 23 Q com Q005 harmonizada), verificar seleção distinta dos que têm redação válida e explicitar que 15 mil por edição não são amostra probabilística garantida para todas as inferências.
3. **Privacidade contextual/cruzada:** avaliar possíveis grupos pequenos e diferenciação de indivíduos cruzando indicadores por ano, UF, cluster, nota e competência. Não usar limite fixo isolado como garantia. A política do projeto não suprime automaticamente todas as células pequenas; qualquer divulgação requer exame de risco específico.

A decisão externa (doc `PARECER_PONTE_V2_MODELO.json`) deve indicar responsável, data e fundamentação substantiva em cada dimensão. Não preencher campos de aprovação apenas para fazer o executor funcionar. Os dados pseudonimizados continuam restritos ao computador do projeto; não incluir em ZIPs, Git, dashboards nem documentação pública.

## Etapas de integração

1. Extrair o pacote na raiz do repositório.
2. `python integrar_ponte_v2.py --verificar` — somente leitura, hashes e metadados; não altera código.
3. `python integrar_ponte_v2.py --preparar-revisao` — produz `docs/RELATORIO_PRE_INTEGRACAO_PONTE_V2.json` com **apenas agregados** e ressalvas; **não aprova**.
4. Registrar pareceres externos e revisão de privacidade antes de prosseguir.
5. `python integrar_ponte_v2.py --instalar-codigo` — substituição **explícita e com backup** do núcleo compartilhado após verificação de seu hash; sem manifesto homologado, os dez indicadores seguem bloqueados.
6. **Somente após aprovação real:** preencher parecer com fundamentação, salvar como `docs/PARECER_PONTE_V2_DECISAO.json` e executar `python integrar_ponte_v2.py --homologar-com-parecer docs/PARECER_PONTE_V2_DECISAO.json`. Esse modo reexecuta auditoria independente e registra o manifesto LOCAL; não executa indicadores.
7. Pré-checar IND-055..063/068; posteriormente processar sequencialmente com backup. Auditar cada saída e seus cruzamentos antes de compartilhar/publicar resultados.

A instalação por si só não produz nenhum resultado novo; IND-001..054, 064..067 e 069..072 permanecem inalterados.

## Questões abertas documentadas

- Potencial viés de seleção por cobertura de redações válidas, que difere por cluster e edição.
- K=3 selecionado por Silhouette, mas K=4 venceu em Davies-Bouldin.
- Dados de 2025 utilizáveis apenas para tendências de composição dos grupos, não para nota × cluster.
- Resultados de Random Forest (IND-060..063) devem ser descritos como associações preditivas na amostra, não efeitos causais. Em revisão posterior considerar divisão temporal para testar generalização entre edições.
