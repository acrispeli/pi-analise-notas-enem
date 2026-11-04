# -*- coding: utf-8 -*-
"""Explicação didática dos três perfis materiais V2 usados nos IND-055–059/068.

Apenas lê a tabela AGREGADA de respostas já calculadas; não treina modelos,
não lê microdados e não altera as saídas dos indicadores.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

ARQUIVO_RELATIVO = Path('docs/perfis_socio_v2_respostas_resumo.csv')
VARIAVEIS = (
    ('Moradores no domicilio', 'Moradores no domicílio'),
    ('Banheiros', 'Banheiros'),
    ('Quartos', 'Quartos'),
    ('Carros', 'Carros'),
    ('Motocicletas', 'Motocicletas'),
    ('Geladeiras', 'Geladeiras'),
    ('Maquina de lavar', 'Máquina de lavar roupas'),
    ('Micro-ondas', 'Micro-ondas'),
    ('Aspirador de po', 'Aspirador de pó'),
    ('Celulares no domicilio', 'Celulares no domicílio'),
)
PERFIS = ('M1', 'M2', 'M3')
NOMES = {
    'M1': 'Menor disponibilidade relativa de bens',
    'M2': 'Maior disponibilidade de bens',
    'M3': 'Restrições materiais mais acentuadas',
}
COLUNAS = (
    'Variavel', 'Perfil', 'N_total', 'Resposta_mais_frequente', 'Percentual_1',
    'Segunda_resposta', 'Percentual_2',
)


def _percentual(texto: str) -> Decimal:
    """O CSV fornecido usa separador ';' e vírgula decimal em pt-BR."""
    try:
        valor = Decimal(str(texto).replace(',', '.').strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError('Percentual inválido na caracterização dos perfis') from exc
    if not 0 <= valor <= 100:
        raise ValueError('Percentual fora de 0–100 na caracterização dos perfis')
    return valor


def carregar_perfis(raiz: Path) -> tuple[dict[tuple[str, str], dict], dict[str, int]]:
    """Lê e valida o resumo das dez variáveis x três perfis (30 registros)."""
    caminho = Path(raiz) / ARQUIVO_RELATIVO
    with caminho.open('r', encoding='utf-8-sig', newline='') as arq:
        leitor = csv.DictReader(arq, delimiter=';')
        if not leitor.fieldnames or set(leitor.fieldnames) != set(COLUNAS):
            raise ValueError('Cabeçalho inesperado no CSV de caracterização dos perfis')
        registros = list(leitor)
    esperado = {(v, perfil) for v, _ in VARIAVEIS for perfil in PERFIS}
    linhas: dict[tuple[str, str], dict] = {}
    tamanhos: dict[str, int] = {}
    for item in registros:
        chave = (item['Variavel'], item['Perfil'])
        if chave not in esperado or chave in linhas:
            raise ValueError(f'Variável/perfil ausente, duplicado ou inesperado: {chave}')
        try:
            n = int(item['N_total'])
        except (TypeError, ValueError) as exc:
            raise ValueError(f'N inválido para {chave}') from exc
        if n <= 0 or (chave[1] in tamanhos and tamanhos[chave[1]] != n):
            raise ValueError(f'Tamanho de amostra incoerente para {chave}')
        tamanhos[chave[1]] = n
        if not item['Resposta_mais_frequente'] or not item['Segunda_resposta']:
            raise ValueError(f'Respostas não informadas para {chave}')
        p1 = _percentual(item['Percentual_1'])
        p2 = _percentual(item['Percentual_2'])
        if p2 > p1 or p1 + p2 > Decimal('100.01'):
            raise ValueError(f'Frequências incoerentes para {chave}')
        linhas[chave] = {**item, 'N_total': n, 'p1': p1, 'p2': p2}
    if set(linhas) != esperado:
        raise ValueError(f'Tabela de perfis incompleta: esperado 30, encontrado {len(linhas)}')
    return linhas, tamanhos


def tabela_respostas(raiz: Path, segunda: bool = False) -> pd.DataFrame:
    """Dez linhas, com uma coluna por perfil e percentuais condicionais ao grupo."""
    linhas, _ = carregar_perfis(raiz)
    tabela = []
    for chave, rotulo in VARIAVEIS:
        r = {'Variável': rotulo}
        for perfil in PERFIS:
            x = linhas[(chave, perfil)]
            def formatar(resposta: str, pct: Decimal) -> str:
                resposta = resposta.replace('Nao', 'Não').replace('nenhum', 'nenhum')
                return f'{resposta} ({str(pct).replace(".", ",")}%)'
            texto = formatar(x['Resposta_mais_frequente'], x['p1'])
            if segunda:
                texto += f' | 2ª: {formatar(x["Segunda_resposta"], x["p2"])}'
            r[perfil] = texto
        tabela.append(r)
    return pd.DataFrame(tabela, columns=['Variável', *PERFIS])


def resumo_amostra(raiz: Path) -> dict[str, dict[str, object]]:
    _, tamanhos = carregar_perfis(raiz)
    total = sum(tamanhos.values())
    return {p: {
        'n': tamanhos[p],
        'percentual': round(100 * tamanhos[p] / total, 2),
        'nome': NOMES[p],
    } for p in PERFIS}


def exibir_metodologia_perfis(st, raiz: Path) -> None:
    """Exibe um único expansor na página/indicador ativo, sem duplicações."""
    with st.expander('Como foram definidos os três perfis socioeconômicos?', expanded=False):
        st.markdown(
            '**O que representam?** Os perfis M1, M2 e M3 sintetizam padrões de '
            'condições de moradia e disponibilidade de bens em uma **amostra nacional '
            'de 104.752 participações no ENEM (2019–2025)**. Não representam '
            'classes sociais oficiais nem faixas de renda. O agrupamento é descritivo.'
        )
        st.caption(
            'Estes são os perfis materiais de referência dos IND-055–059 e IND-068. '
            'Não são os perfis de notas dos IND-017/018 nem os agrupamentos '
            'históricos do IND-054; o IND-040 descreve o questionário, '
            'sem atribuir esses perfis a cada participante.'
        )
        st.markdown('**Dez variáveis utilizadas para formar os grupos:**')
        st.markdown(
            'Número de moradores; banheiros; quartos; carros; motocicletas; '
            'geladeiras; máquina de lavar roupas; micro-ondas; aspirador de pó; '
            'celulares no domicílio. As categorias do questionário foram harmonizadas '
            'entre edições, incluindo mudanças na numeração de algumas perguntas.'
        )
        st.markdown(
            '**Quatro variáveis suplementares:** escolaridade e ocupação do pai '
            'ou responsável e da mãe ou responsável (Q001–Q004). '
            'Foram usadas apenas para caracterização, **não para formar os grupos**. '
            'A renda familiar também não foi utilizada como variável ativa.'
        )
        st.markdown(
            '**Como o modelo funcionou?** '
            '**1. MCA (Análise de Correspondência Múltipla):** representa '
            'as categorias das dez variáveis em três dimensões estatísticas. '
            '**2. K-Means:** agrupa respostas semelhantes nesse espaço. '
            '**3. Escolha de K:** foram avaliadas alternativas entre 2 e 6 '
            'grupos pelo índice Silhouette em subamostra; a configuração '
            'selecionada foi **K = 3**. Silhouette mede separação entre grupos, '
            'não determina o nível social de um participante nem valida '
            'causalidade. Os nomes M1–M3 foram atribuídos após o agrupamento.'
        )
        try:
            perfis = resumo_amostra(raiz)
            tabela = tabela_respostas(raiz)
        except (OSError, ValueError, KeyError) as exc:
            st.warning(f'A tabela de caracterização não pôde ser exibida: {exc}')
            return
        st.markdown('**Os três perfis na amostra de treinamento**')
        for p in PERFIS:
            info = perfis[p]
            st.markdown(
                f'**{p} — {info["nome"]}:** '
                f'{info["n"]:,.0f} participações '.replace(',', '.')
                + f'({info["percentual"]:.2f}% da amostra).'.replace('.', ',')
            )
        st.markdown(
            '**Respostas mais frequentes de cada variável por perfil** '
            '(percentual *dentro* do grupo):'
        )
        st.table(tabela)
        st.caption(
            'A tabela mostra a resposta mais comum, não um critério obrigatório. '
            'Uma pessoa pode pertencer a um perfil sem apresentar a resposta predominante '
            'em cada variável. A caracterização combina as edições 2019–2025 e não '
            'se ajusta ao filtro de ano ou UF selecionado no painel.'
        )
        st.markdown(
            '**Exemplo de leitura:** em M3, a resposta mais comum para geladeiras '
            'foi possuir uma (51,07%), mas a segunda resposta mais frequente '
            'foi não possuir nenhuma (48,47%). Isso mostra a diversidade '
            'interna dos grupos; não significa que todos os participantes de M3 '
            'tenham as mesmas condições.'
        )
        st.markdown(
            '**Por que isso importa para a educação?** '
            'Os agrupamentos ajudam a examinar diferenças de desempenho em redação '
            'associadas às condições materiais. Podem apoiar perguntas pedagógicas '
            'sobre oportunidades de aprendizagem e acesso a recursos, mas **não '
            'medem diretamente a qualidade da escola ou a aprendizagem individual**. '
            'Associações com notas não demonstram relações de causa e efeito.'
        )
        st.caption(
            'Fonte: resumo agregado das respostas da ponte socioeconômica V2, '
            'modelo MCA (10 variáveis ativas) + K-Means (3 grupos). '
            'Não foram reprocessados microdados ou resultados dos indicadores.'
        )
