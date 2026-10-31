# Mapeamento de integração pós-validação

O campo `dashboard_target` dos JSONs reproduz os destinos previstos no catálogo; o executor NÃO modifica dashboards existentes. Para integração futura, validar cada bloco e consolidá-lo com backup, sem sobrescrever `pages` inteiras.

- 055 `pages.socioeconomic.cluster_total`
- 056 `pages.socioeconomic.cluster_competencies`
- 057 `pages.socioeconomic.cluster_high_performance`
- 058 `pages.socioeconomic.cluster_losses`
- 059 `pages.socioeconomic.cluster_reviewer_divergence`
- 060 `pages.ml.total_score_model`
- 061 `pages.ml.competency_models`
- 062 `pages.ml.feature_importance`
- 063 `pages.ml.model_subgroup_quality`
- 064 `pages.temporal.total_score`
- 065 `pages.temporal.competencies`
- 066 `pages.temporal.high_performance`
- 067 `pages.temporal.reviewers`
- 068 `pages.temporal.socio_clusters`
- 069 `quality.join_diagnostics`
- 070 `quality.missingness`
- 071 `quality.suppression` (**auditoria, não supressão**)
- 072 `meta`

Não ocultar `draft`, não mostrar ano indisponível como zero e não atribuir causalidade a diferenças entre grupos.
