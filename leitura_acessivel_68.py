# -*- coding: utf-8 -*-
"""Textos didáticos para os 68 indicadores; não modifica resultados agregados.

Distingue explicação do conceito, leitura do resultado, aplicação pedagógica e
limites. Os resumos numéricos usam regras já existentes, sem IA generativa.
"""
from __future__ import annotations
from typing import Any

# A ordem é: O que mede? | Como ler? | Para refletir sobre ensino/aprendizagem?
GUIAS = {
 1: (
  'Conta registros de redação que atendem aos critérios desta análise: situação da redação igual a 1 ("Sem problemas") e nota final preenchida, numérica e entre 0 e 1.000. A comparação percentual usa como total todos os registros disponíveis na base de resultados.',
  'Imagine 100 registros: se 70 atendem aos critérios, são 70 redações válidas e 30 outros registros. "Outros" não quer dizer necessariamente "redações inválidas": podem existir diferentes situações registradas. Redação válida também não significa texto sem erros de português.',
  'Antes de comparar notas entre anos, vale perguntar quantas redações efetivamente entraram nas contas. Uma mudança na participação pode alterar o perfil dos textos analisados.'),
 2: ('É a soma das notas das redações válidas dividida pela quantidade de redações válidas.',
     'Uma média de 650 pontos não significa que a maioria tenha tirado exatamente 650. A média pode ser influenciada por notas muito altas ou muito baixas.',
     'Compare a média com a mediana (IND-003) e a distribuição (IND-006) antes de pensar em dificuldades de aprendizagem.'),
 3: ('É a nota que fica no meio quando as redações válidas são colocadas em ordem de pontuação.',
     'Uma mediana de 640 significa que aproximadamente metade das notas ficou em 640 ou abaixo e metade em 640 ou acima.',
     'Média e mediana juntas ajudam a entender se o desempenho geral ficou concentrado ou foi puxado por notas extremas.'),
 4: ('Mostra o quanto as notas normalmente se espalham em torno da média. O nome estatístico é desvio-padrão.',
     'Quanto maior esse número, mais diferentes tendem a ser as notas do grupo. Não é uma nota da redação, nem a diferença entre a maior e a menor.',
     'Uma turma ou conjunto com notas muito variadas pode precisar de estratégias de aprendizagem diversificadas.'),
 5: ('Divide a distribuição das notas em pontos de referência: P25, P50, P75, P90 e P95.',
     'P25: aproximadamente 25% das redações tiveram nota igual ou inferior ao valor indicado. P50: 50%, a mediana. P75: 75%. P90: 90%. P95: 95%. Não são percentuais de acertos.',
     'Observe a distância entre P25 e P75 para perceber como se distribui a metade central das notas. Notas empatadas podem tornar as proporções aproximadas.'),
 6: ('Conta quantas redações válidas ficaram em cada faixa de notas.',
     'A barra mais alta indica uma faixa com mais redações; não significa a maior nota. Verifique sempre os limites de cada faixa e se o eixo apresenta quantidade ou porcentagem.',
     'Ajuda a identificar regiões de concentração das notas e a evitar conclusões baseadas apenas na média.'),
 7: ('Mostra as diferentes situações registradas na base para a redação, como "Sem problemas", "Anulada" ou "Em branco", de acordo com os códigos disponíveis.',
     'Compare a quantidade de cada situação com o total de registros; a situação administrativa não equivale à nota obtida por quem teve redação válida.',
     'É útil para discutir por que nem toda inscrição ou registro entra na análise das notas, sem atribuir motivos individuais.'),
 8: ('Conta quantas redações válidas receberam exatamente 1.000 pontos.',
     'Uma quantidade pequena pode representar uma fração muito pequena do total. Nunca confunda o número de notas máximas com a porcentagem correspondente.',
     'Pode motivar a discussão da rubrica de avaliação, mas casos raros não representam a experiência da maioria dos estudantes.'),
 9: ('Calcula a nota média, separadamente, em cada uma das cinco competências da redação, avaliadas de 0 a 200 pontos.',
     'C1 é escrita formal; C2, compreensão do tema e repertório; C3, argumentação; C4, coesão; C5, proposta de intervenção. Uma média menor indica menos pontos nessa parte da rubrica, não um diagnóstico individual.',
     'Ajuda a escolher temas para oficinas de escrita, revisão, argumentação e intervenção.'),
 10: ('Mostra a nota mediana de cada competência da redação.',
      'A mediana divide as pontuações daquela competência em duas metades aproximadas e sofre menos influência de valores extremos que a média.',
      'Compare com a média por competência para compreender melhor o desempenho típico.'),
 11: ('Mostra o quanto as pontuações variam dentro de cada competência.',
      'Quanto maior a dispersão, mais diferentes são as notas naquela competência. Não significa que ela seja necessariamente "mais difícil" para todas as pessoas.',
      'Diferenças de dispersão podem orientar atividades com diferentes níveis de apoio.'),
 12: ('Conta redações em cada pontuação ou nível observado nas cinco competências.',
      'Cada barra representa o percentual de redações válidas naquela pontuação e naquela competência. Barra alta indica frequência, não um nível ideal.',
      'Ajuda a perceber em quais competências certas faixas de pontuação se concentram.'),
 13: ('Compara se as pontuações de duas competências costumam aumentar ou diminuir juntas.',
      'Uma correlação positiva indica que notas altas em uma frequentemente acompanham notas altas em outra. Uma negativa sugere sentidos opostos; valor próximo de zero indica associação linear ou monotônica fraca, conforme o método.',
      'Pode gerar perguntas sobre habilidades que caminham juntas, mas não mostra que uma competência causa outra.'),
 14: ('Resume quanta variação das cinco competências é representada por cada componente da análise PCA.',
      'PC1, PC2 e seguintes são combinações matemáticas das competências. Uma componente com 70% explica aproximadamente 70% da variação considerada pelo modelo, não 70% das redações.',
      'É uma forma de resumir padrões gerais, não uma nova nota oficial do ENEM.'),
 15: ('Mostra quais competências têm mais peso em cada componente da PCA.',
      'Pesos maiores em valor absoluto indicam maior contribuição. O sinal positivo ou negativo depende da orientação do componente e não é elogio nem punição.',
      'Ajuda a traduzir quais aspectos da redação aparecem juntos no resumo estatístico.'),
 16: ('Representa, em dois eixos de PCA, uma visão resumida dos padrões de competências.',
      'Pontos ou áreas próximas indicam perfis semelhantes nas dimensões representadas; os eixos não são notas de 0 a 1.000.',
      'O gráfico convida a observar diversidade de combinações de desempenho, sem classificar estudantes individualmente.'),
 17: ('Agrupa redações com combinações parecidas de notas nas cinco competências usando um método de agrupamento.',
      'Cada perfil representa um padrão médio de pontuações, não uma categoria oficial de estudantes. Os grupos de competências não são os perfis materiais M1–M3.',
      'Permite discutir diferentes caminhos para desenvolver a redação: intervenção, argumentação, coesão e outros aspectos.'),
 18: ('Indica quantas redações foram atribuídas aos grupos de perfis de competências.',
      'O grupo maior reúne mais registros segundo aquele modelo; isso não significa melhor desempenho.',
      'Observe o tamanho dos grupos junto aos perfis do IND-017, sempre considerando a população e o método de atribuição.'),
 19: ('Apresenta medidas que ajudam a julgar se os grupos criados pelo algoritmo são relativamente distintos.',
      'Valores de qualidade não são notas escolares. Uma separação estatística maior não significa que os perfis sejam uma verdade definitiva.',
      'Mostra por que um agrupamento precisa ser examinado criticamente antes de orientar qualquer interpretação educativa.'),
 20: ('Mede a diferença absoluta entre as notas totais atribuídas pelos dois primeiros avaliadores quando há um par de avaliações utilizável.',
      'Uma diferença de 40 pontos significa que as duas notas ficaram 40 pontos distantes, sem informar qual avaliador deu a maior.',
      'Pode apoiar discussões sobre consistência de correção, sem concluir automaticamente que alguém errou.'),
 21: ('Mede a distância entre as notas dos dois primeiros avaliadores, separada por competência.',
      'Uma distância maior em uma competência aponta maior diferença entre as duas avaliações naquele critério, não a causa da diferença.',
      'Ajuda a discutir como descritores e critérios podem ser interpretados durante uma correção.'),
 22: ('Conta situações em que as diferenças entre avaliações atendem a critérios de discrepância calculados pela pesquisa.',
      'O cálculo toma o edital de 2024 como referência para comparar anos. Isso não significa que todas as edições tenham seguido exatamente a mesma regra operacional.',
      'Permite discutir a necessidade de procedimentos de revisão de notas sem afirmar decisões reais da banca com base apenas na simulação.'),
 23: ('Compara se os dois avaliadores registraram a mesma situação da redação.',
      'A divergência de situação é diferente de uma simples diferença numérica de nota.',
      'Ajuda a observar a consistência de classificações sem indicar erro ou responsabilidade individual.'),
 24: ('Mostra a frequência de registros de terceiro avaliador (AV3) na base.',
      'O denominador deste indicador é o total de registros da base (POP_ALL), não apenas o conjunto de redações válidas nem o de pares de avaliadores.',
      'Ajuda a compreender que alguns textos passam por etapas extras de avaliação; a presença de AV3, sozinha, não informa a razão.'),
 25: ('Mostra a frequência de registros de banca/quarta avaliação (AV4) na base.',
      'O denominador é o total de registros da base (POP_ALL). A presença de banca não significa automaticamente erro grave na redação.',
      'Torna mais fácil conversar sobre etapas de revisão no processo de avaliação.'),
 26: ('Resume a concordância entre os dois primeiros avaliadores em cada competência, considerando também o acaso.',
      'Um índice mais alto sugere maior concordância dentro do critério empregado; não é a porcentagem simples de notas idênticas.',
      'Permite discutir a importância de critérios comuns e formação de avaliadores.'),
 27: ('Resume o grau de concordância entre as notas totais atribuídas pelos dois primeiros avaliadores.',
      'Correlação e concordância não são a mesma coisa: duas séries de notas podem variar juntas mesmo que uma costume ser maior.',
      'É uma visão complementar às diferenças em pontos dos IND-020 e IND-021.'),
 28: ('Agrupa padrões de divergência entre avaliadores por semelhanças nas cinco competências.',
      'Os grupos são construções estatísticas, não rótulos de certo ou errado para os avaliadores.',
      'Pode mostrar se certas combinações de diferenças se repetem, sem revelar causas.'),
 29: ('Identifica padrões estatísticos de avaliação considerados pouco comuns pelo algoritmo.',
      'Atípico significa diferente do padrão esperado pelo modelo; não significa fraude, erro comprovado ou injustiça.',
      'Estimula a reflexão sobre limites dos algoritmos e a necessidade de análise humana.'),
 30: ('Mostra quantas redações válidas ficaram nas faixas de alto desempenho, de 900 a 1.000 pontos.',
      'Compare a quantidade por faixa e seu percentual entre as redações válidas; 900 pontos e 1.000 pontos não são a mesma categoria.',
      'Ajuda a entender como se distribuem as notas altas, sem tratar os demais textos como sem valor pedagógico.'),
 31: ('Mostra, entre redações de 900 a 980 pontos, quantos pontos faltaram para atingir 200 em cada competência.',
      'Por exemplo, uma nota 160 em C4 representa uma perda de 40 pontos nessa competência. O tamanho da perda é diferente de quantas vezes houve perda.',
      'Ajuda a discutir aspectos que ainda podem ser aprimorados mesmo em redações com nota elevada.'),
 32: ('Conta quantas vezes há desconto de pontos em cada competência nas redações de 900 a 980 pontos.',
      'O desconto aparece quando a competência fica abaixo de 200; frequência de ocorrência não diz, sozinha, quantos pontos foram perdidos.',
      'Ajuda a diferenciar dificuldades mais frequentes de perdas mais intensas.'),
 33: ('Mostra a parcela da soma total de pontos perdidos que pertence a cada competência no recorte de alto desempenho.',
      'Uma competência pode concentrar muitos pontos perdidos mesmo não sendo aquela em que o desconto ocorre mais vezes.',
      'Compare com o IND-032 para não confundir frequência e intensidade.'),
 34: ('Conta redações em que apenas uma competência ficou abaixo de 200 pontos, impedindo a nota máxima.',
      'Se quatro competências receberam 200 e uma ficou em 180, aquela única diferença impede alcançar 1.000. Há também uma variante específica para a nota 980.',
      'Pode orientar atividades de aperfeiçoamento focadas em um critério, sem simplificar toda a qualidade do texto a esse critério.'),
 35: ('Identifica pares ou trios de competências que apresentam descontos ao mesmo tempo.',
      'Duas perdas que aparecem juntas não indicam que uma causou a outra. Combinações podem se sobrepor.',
      'Mostra que uma mesma redação pode precisar de aprimoramento em mais de um aspecto.'),
 36: ('Procura associações frequentes entre descontos em competências nas redações de alto desempenho.',
      'Uma regra estatística do tipo "quando A ocorre, B também aparece em muitos casos" não é uma previsão garantida nem uma causa.',
      'Ajuda a levantar hipóteses pedagógicas que precisam ser confrontadas com a leitura de textos reais.'),
 37: ('Compara, por testes estatísticos, a concentração de perdas entre competências nas redações do recorte estudado.',
      'Um resultado estatisticamente significativo não significa, necessariamente, uma diferença grande ou importante para o ensino.',
      'Use a magnitude da diferença junto ao teste, e não apenas o valor de significância.'),
 38: ('Compara se os avaliadores concordaram sobre haver ou não desconto em cada competência.',
      'Concordar sobre a existência de desconto é diferente de atribuir exatamente a mesma nota.',
      'Contribui para refletir sobre a consistência dos critérios de avaliação.'),
 39: ('Relaciona a faixa da nota total com os resultados das cinco competências no grupo de alto desempenho.',
      'Cada célula do mapa representa uma combinação de faixa e competência. Cor mais intensa pode indicar maior valor ou frequência, conforme a legenda.',
      'Permite comparar padrões de pontuação de forma visual sem identificar participantes.'),
 40: ('Resume as respostas do questionário socioeconômico, como condições do domicílio e características declaradas.',
      'As categorias são respostas agregadas, não diagnóstico individual. Algumas perguntas e alternativas mudam entre 2019–2023 e 2024–2025.',
      'Pode apoiar reflexões sobre diversidade de contextos de estudo, respeitando diferenças entre edições.'),
 41: ('Compara a nota total da redação entre faixas de renda declaradas no questionário.',
      'Uma diferença de médias entre faixas de renda mostra associação entre grupos; não prova que renda por si só causou a nota.',
      'Estimula conversas sobre oportunidades educacionais sem atribuir capacidades aos estudantes por sua renda.'),
 42: ('Compara as notas de C1 a C5 entre faixas de renda declaradas.',
      'Verifique quais competências são comparadas e lembre que cada uma vai de 0 a 200 pontos.',
      'Pode sugerir questões de acesso a diferentes oportunidades de leitura e escrita, sem criar estereótipos.'),
 43: ('Compara a nota total conforme a escolaridade declarada dos responsáveis.',
      'São médias ou distribuições de grupos, não a trajetória de cada aluno. Não se pode concluir causalidade.',
      'Ajuda a discutir desigualdades de acesso e apoio à aprendizagem de maneira respeitosa.'),
 44: ('Relaciona a escolaridade dos responsáveis ao desempenho em cada uma das competências.',
      'Um grupo pode ter diferenças em algumas competências e pouca diferença em outras. Leia a escala de 0 a 200.',
      'Incentiva reflexão sobre repertório, práticas de escrita e oportunidades educacionais.'),
 45: ('Compara a nota total por categorias relacionadas ao tipo de escola.',
      'A variável TP_ESCOLA usada em 2019–2023 não é conceitualmente equivalente à pergunta Q023 usada em 2024. Evite tratá-las como uma mesma série.',
      'Pode motivar reflexões sobre diferenças entre contextos escolares, sem julgar escolas ou alunos a partir de médias.'),
 46: ('Compara as notas das cinco competências entre categorias relacionadas ao tipo de escola.',
      'A comparação depende da forma como o tipo de escola foi definido em cada edição; nem sempre as categorias são diretamente equivalentes.',
      'Ajuda a pensar em estratégias de ensino da escrita contextualizadas, sem rankings simplistas.'),
 47: ('Compara desempenho da redação entre grupos definidos pelas informações de acesso à internet.',
      'A associação não demonstra que ter internet seja a causa do desempenho. Verifique o significado das categorias na edição selecionada.',
      'Pode gerar perguntas sobre acesso a materiais digitais, estudo e produção textual.'),
 48: ('Compara desempenho entre grupos definidos pelas respostas sobre computador no domicílio.',
      'Ter ou não ter computador é uma informação sobre condições materiais, não uma medida de habilidade de escrita.',
      'Ajuda a discutir desigualdades de recursos para atividades educacionais.'),
 49: ('Compara notas entre categorias de ocupação declarada dos responsáveis.',
      'A classificação é feita com base no questionário e pode mudar entre edições; não indica mérito ou capacidade de uma família.',
      'É uma oportunidade para discutir diversidade social sem estereótipos.'),
 50: ('Compara notas conforme a quantidade de moradores declarados no domicílio.',
      'Uma média por tamanho de domicílio não revela como é a rotina de estudo de nenhuma pessoa.',
      'Pode orientar reflexões sobre condições de estudo, sem supor causalidade.'),
 51: ('Compara resultados agregados de subgrupos demográficos definidos nas fontes.',
      'Veja quais variáveis e categorias compõem o grupo antes de comparar valores. Médias não representam cada indivíduo.',
      'Ajuda a reconhecer diferenças de contexto sem transformar grupos em rótulos de capacidade.'),
 52: ('Mostra notas da redação segundo a unidade da federação em que a prova foi realizada.',
      'UF da prova não é necessariamente a UF de residência. Também não permite, sozinha, afirmar que uma rede de ensino é melhor que outra.',
      'Pode servir de ponto de partida para estudar diferenças regionais, considerando composição e tamanho dos grupos.'),
 53: ('Resume respostas socioeconômicas categóricas em poucas dimensões, por análise de correspondências múltiplas (MCA).',
      'Os eixos são combinações estatísticas de respostas, não notas de redação ou uma escala de mérito social.',
      'É uma maneira de observar padrões de condições de vida sem reduzir uma pessoa a um único número.'),
 54: ('Cria grupos exploratórios de respostas socioeconômicas por um modelo histórico de agrupamento.',
      'Os grupos H1, H2 etc. pertencem ao modelo original, diferente dos perfis materiais M1–M3 criados na revisão V2. Não compare seus números como se fossem os mesmos grupos.',
      'Ajuda a discutir diversidade de perfis de participação, mas não classifica habilidades individuais.'),
 55: ('Compara a nota média de redação entre três perfis materiais definidos estatisticamente na V2.',
      'M1: menor disponibilidade relativa de bens domésticos; M2: maior disponibilidade relativa; M3: restrições materiais mais acentuadas. São perfis da amostra, não classes sociais oficiais.',
      'Pode ajudar a discutir desigualdades de oportunidades sem confundir perfil socioeconômico com competência C1–C5.'),
 56: ('Compara as médias das cinco competências entre os perfis materiais M1, M2 e M3.',
      'C1 a C5 são critérios de avaliação; M1 a M3 são grupos de condições materiais. São coisas diferentes.',
      'Permite identificar perguntas pedagógicas sobre argumentação, coesão e intervenção, sem diagnosticar indivíduos.'),
 57: ('Mostra a proporção de redações com 900 pontos ou mais dentro de cada perfil material.',
      'Uma porcentagem maior indica mais redações de alto desempenho proporcionalmente naquele grupo, não necessariamente maior quantidade absoluta.',
      'Pode suscitar debate sobre oportunidades, evitando explicações causais apressadas.'),
 58: ('Mostra descontos por competência nas redações de alto desempenho de cada perfil material.',
      'Frequência de desconto e pontos perdidos são medidas diferentes. Alguns grupos têm poucos registros, exigindo cautela adicional.',
      'Ajuda a formular questões sobre aspectos da escrita que aparecem em diferentes contextos.'),
 59: ('Compara a divergência de notas entre avaliadores conforme os perfis materiais.',
      'Uma distância maior entre notas não informa qual avaliador está correto nem prova tratamento desigual.',
      'Pode estimular uma discussão cuidadosa sobre consistência da correção e limites da análise.'),
 64: ('Acompanha a evolução das notas totais da redação nas edições disponíveis.',
      'Compare valores de anos diferentes observando alterações na população, no exame e na disponibilidade de dados. Uma subida entre dois anos não descreve a trajetória de cada estudante.',
      'Ajuda a perceber mudanças históricas e levantar perguntas para investigar, não afirmar causas.'),
 65: ('Acompanha mudanças nas notas das cinco competências ao longo das edições disponíveis.',
      'C1–C5 mantêm significados próprios; cada linha representa uma competência. Diferenças de pontuação podem ter múltiplas explicações.',
      'Ajuda a pensar em quais aspectos da produção textual merecem investigação histórica.'),
 66: ('Acompanha a participação de redações quase máximas nas edições disponíveis.',
      'Leia a faixa de notas usada no indicador e a população de referência em cada ano; não confunda 980 com 1.000.',
      'Pode contribuir para discussões sobre desempenho elevado e sua distribuição temporal.'),
 67: ('Mostra como medidas de divergência entre avaliadores variam ao longo dos anos.',
      'Mudanças nas taxas ou distâncias não demonstram sozinhas melhora ou piora da correção; verifique população e procedimento.',
      'Ajuda a discutir acompanhamento da consistência do processo avaliativo.'),
 68: ('Compara como os perfis materiais M1, M2 e M3 aparecem na amostra de diferentes edições.',
      'As porcentagens descrevem a composição de uma amostra, não a distribuição socioeconômica de todo o país. Em 2025 há perfis, mas não vínculo validado com notas.',
      'Pode apoiar o debate sobre diversidade das condições materiais entre participantes, sem atribuir desempenho ao perfil.'),
 69: ('Mostra a proporção de registros que puderam ser associados entre bases de informações diferentes.',
      'Uma taxa alta indica maior correspondência técnica entre bases, não que as notas sejam melhores ou que os dados sejam perfeitos.',
      'Explica por que algumas análises usam menos registros que outras.'),
 70: ('Mostra a quantidade ou porcentagem de informações ausentes nas bases analisadas.',
      'Um campo vazio significa ausência de informação, não necessariamente resposta negativa ou valor zero.',
      'Ajuda a entender por que certos resultados são calculados com grupos menores.'),
 71: ('Quantifica células com poucos registros em tabelas agregadas dos indicadores.',
      'Uma célula pequena indica menor base de observações naquela categoria e pode produzir estimativas instáveis; não é uma contagem de redações com nota baixa.',
      'Ajuda a distinguir volume de dados, qualidade das estimativas e rastreabilidade da pesquisa.'),
 72: ('Informa a origem das bases, as versões dos resultados e detalhes de processamento.',
      'É a ficha de procedência do painel: permite verificar de que arquivos e critérios veio um número. Não é indicador de desempenho escolar.',
      'Ajuda a conferir se duas análises podem ser comparadas com segurança.'),
}

# Avisos adicionais somente onde há uma restrição específica, além das ressalvas gerais.
CUIDADOS = {
 1: 'O total do denominador corresponde aos registros da base de resultados analisada, não a todos os inscritos, e o consolidado histórico soma participações, não pessoas únicas.',
 5: 'Os percentis são calculados sobre redações válidas. Não some percentis de anos diferentes nem calcule a média de percentis para produzir o resultado do período.',
 8: 'Notas máximas são eventos raros: compare quantidade, proporção e denominador para evitar extrapolar resultados.',
 17: 'Os grupos foram obtidos por amostragem/modelo; proporções amostrais não equivalem automaticamente a proporções da população.',
 18: 'Os nomes dos grupos podem mudar de um recorte para outro; o tamanho não define mérito.',
 22: 'Os critérios de 2024 foram aplicados retrospectivamente para comparação; não representam necessariamente decisões históricas de cada edição.',
 24: 'AV3 foi identificada por nota ou situação preenchida; isso não comprova o motivo administrativo do encaminhamento.',
 25: 'AV4 foi identificada por nota ou situação preenchida; não atribua motivos individuais.',
 29: 'O algoritmo identifica padrões pouco comuns, não práticas irregulares.',
 34: 'A variante "recorte 980" é complementar ao indicador principal; confira qual fonte foi selecionada.',
 40: 'Algumas perguntas e códigos do questionário mudam em 2024; não trate categorias diferentes como uma única série sem harmonização.',
 45: 'TP_ESCOLA (2019–2023) e Q023 (2024) não são a mesma variável.',
 54: 'O modelo histórico e o modelo material V2 não devem ser comparados diretamente. Há limitações de interpretação do agrupamento original.',
 55: 'Resultados agregados de uma amostra com notas disponíveis em 2019–2024; não há ligação validada com notas de 2025.',
 56: 'M1–M3 são perfis materiais, não níveis de escrita. Sem comparação causal.',
 57: 'Percentuais de grupos distintos devem ser lidos com seus denominadores próprios.',
 58: 'Com amostras pequenas, os percentuais podem oscilar bastante; compare sempre os denominadores e as medidas de desconto.',
 59: 'Diferença entre notas não comprova viés, erro nem discriminação.',
 68: 'Composição de amostra, não tendência da população brasileira. 2025 não foi vinculado às notas.',
 71: 'Contagens pequenas podem implicar incerteza elevada e exigem leitura contextual do tamanho do grupo.',
}

GLOSSARIO_RAPIDO = {
 1: 'Denominador = total usado como referência para calcular o percentual.',
 2: 'Média = soma dos valores dividida pelo número de observações.',
 3: 'Mediana = valor central da distribuição ordenada.',
 4: 'Desvio-padrão = medida de espalhamento das notas em torno da média.',
 5: 'Percentil = nota de referência para uma parte da distribuição; P90 não é 90% de acertos.',
 13: 'Correlação = relação de variação conjunta, não relação de causa e efeito.',
 14: 'PCA = técnica para resumir várias medidas em poucas dimensões.',
 19: 'Cluster = grupo criado por algoritmo de semelhança; não é categoria oficial.',
 26: 'Kappa = índice estatístico de concordância que considera o acaso.',
 27: 'ICC = índice de concordância das medidas.',
 36: 'Regra de associação = padrão frequente de coocorrência, não previsão certa.',
 53: 'MCA = técnica para resumir relações entre respostas a perguntas categóricas.',
 69: 'Taxa de junção = percentual de registros que correspondem entre bases.',
}

NUMERICOS_VERIFICADOS = frozenset(GUIAS)  # resumo contextual sempre que houver evidência agregada

from orientacoes_pedagogicas_68 import ACOES


def texto_leigo(numero: int, meta: dict, ano: int | None, uf: str) -> dict:
    if numero not in GUIAS:
        raise ValueError(f'Indicador {numero} não possui explicação revisada')
    oque, como, pedag = GUIAS[numero]
    return {'oque': oque, 'como': como, 'pedag': pedag,
            'cuidado': CUIDADOS.get(numero,''),
            'glossario': GLOSSARIO_RAPIDO.get(numero,''),
            'recorte': f'{"Todas as edições disponíveis" if ano is None else "ENEM " + str(ano)} · {"Brasil" if uf == "BR" else "UF " + uf}'}


def mostrar_leitura_acessivel(st, numero: int, doc: dict, meta: dict,
                              ano: int | None, uf: str, valor_visualizado: Any = None,
                              resumo_especifico: dict | None = None) -> None:
    # Quando o painel exibe um ano/competência detalhada dentro do recorte global,
    # alinhar a interpretação à seleção efetivamente mostrada.
    if ano is None and numero in (11,12,17,21,28):
        ano_detalhado = getattr(st,'session_state',{}).get(f'geral_ind{numero:03d}_ano')
        if isinstance(ano_detalhado, int):
            ano = ano_detalhado
    if ano is None and numero == 34 and doc.get('supplement_id'):
        ano_detalhado = getattr(st,'session_state',{}).get('ind034_980_ano')
        if isinstance(ano_detalhado, int):
            ano = ano_detalhado
    guia = texto_leigo(numero, meta, ano, uf)
    if resumo_especifico is None and numero in NUMERICOS_VERIFICADOS:
        from interpretacao_regras_enem import resumir_indicador
        meta_atual=dict(meta)
        if numero == 12:
            meta_atual['_competencia_atual'] = getattr(st, 'session_state', {}).get('ind012_comp', 'C1')
        resumo_especifico = resumir_indicador(numero, doc, meta_atual, ano, uf, valor_visualizado)
    with st.expander('Entenda este resultado · explicação simples', expanded=(numero in (1,5))):
        st.caption(guia['recorte']+' · Explicação automática baseada em regras')
        st.markdown('**O que está sendo contado ou comparado?**')
        st.write(guia['oque'])
        st.markdown('**Como ler o resultado?**')
        st.write(guia['como'])
        if guia['glossario']:
            st.caption(guia['glossario'])
        if resumo_especifico and resumo_especifico.get('texto'):
            st.markdown('**O que os dados deste recorte mostram?**')
            st.write(resumo_especifico['texto'])
        st.markdown('**O que isso pode nos ensinar?**')
        st.write(guia['pedag'])
        if resumo_especifico and resumo_especifico.get('pedagogia') and resumo_especifico['pedagogia'] != guia['pedag']:
            st.write(resumo_especifico['pedagogia'])
        st.markdown('**Como usar esta leitura pedagogicamente?**')
        st.write(ACOES[numero])
        st.markdown('**Antes de tirar uma conclusão**')
        aviso = ('São dados de grupos de participantes, não uma avaliação de cada pessoa. '
                 'Diferenças e associações não provam relação de causa e efeito. '
                 'Um resultado ausente não deve ser interpretado como zero.')
        st.caption((guia['cuidado'] + ' ' if guia['cuidado'] else '') + aviso)
        if resumo_especifico and resumo_especifico.get('nota'):
            st.caption(resumo_especifico['nota'])
        st.caption('Texto gerado por regras transparentes sobre dados agregados; interpretação pedagógica indicativa, sem atribuição causal ou diagnóstico individual. Apresentação editorial aprovada pela equipe.')
