# -*- coding: utf-8 -*-
"""Visualizador local do ENEM 2019–2025 (IND-001 a IND-004).

Abra na raiz do projeto com:
    .\\.venv\\Scripts\\python.exe -m streamlit run visualizador.py

Consome os JSONs modulares de outputs/json/, sem processar os CSVs do INEP.
IND-003 e IND-004 são opcionais: aparecem quando os resultados são gerados.
É um painel exploratório separado da interface oficial da equipe.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


RAIZ = Path(__file__).resolve().parent
PASTA_JSON = RAIZ / "outputs" / "json"
ARQ_001 = PASTA_JSON / "IND_001_redacoes_validas.json"
ARQ_002 = PASTA_JSON / "IND_002_nota_media.json"
OPCIONAIS = {
    "IND-003": {
        "path": PASTA_JSON / "IND_003_mediana_redacao.json",
        "label": "Mediana",
        "coluna": "Mediana",
        "campo": "mediana",
        "definicao": "Nota central da distribuição das redações válidas; a mediana histórica é calculada sobre a distribuição conjunta.",
    },
    "IND-004": {
        "path": PASTA_JSON / "IND_004_desvio_padrao_redacao.json",
        "label": "Desvio-padrão",
        "coluna": "Desvio-padrão",
        "campo": "desvio_padrao",
        "definicao": "Desvio-padrão populacional das notas válidas (ddof=0); o histórico combina todas as edições.",
    },
}

UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}
TODAS_UFS = set(UF_NOMES)
COR_PRINCIPAL = "#207b9a"
COR_DESTAQUE = "#ef9b42"
COR_CINZA = "#a6b5bf"


def inteiro(valor: int | None) -> str:
    return "—" if valor is None else f"{valor:,.0f}".replace(",", ".")


def decimal(valor: float | None, casas: int = 2) -> str:
    if valor is None:
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def conferir_integridade(d1: dict, d2: dict) -> list[int]:
    """Verifica as contagens essenciais; não substitui a validação acadêmica."""
    if d1.get("indicator", {}).get("id") != "IND-001":
        raise ValueError("O primeiro JSON não corresponde ao IND-001.")
    if d2.get("indicator", {}).get("id") != "IND-002":
        raise ValueError("O segundo JSON não corresponde ao IND-002.")

    anos1 = {x["ano"]: x for x in d1["years"]}
    anos2 = {x["ano"]: x for x in d2["years"]}
    if sorted(anos1) != list(range(2019, 2026)) or sorted(anos1) != sorted(anos2):
        raise ValueError("A série deve incluir 2019–2025 em ambos os JSONs.")

    for ano in sorted(anos1):
        um, dois = anos1[ano], anos2[ano]
        if um["brasil"]["redacoes_validas"] != dois["brasil"]["n_validas"]:
            raise ValueError(f"IND-001 e IND-002 usam quantidades diferentes em {ano}.")
        u1 = {item["uf"]: item for item in um["ufs"]}
        u2 = {item["uf"]: item for item in dois["ufs"]}
        if set(u1) != TODAS_UFS or set(u2) != TODAS_UFS:
            raise ValueError(f"Faltam UFs ou há UFs desconhecidas em {ano}.")
        for uf in TODAS_UFS:
            if u1[uf]["redacoes_validas"] != u2[uf]["n_validas"]:
                raise ValueError(f"Quantidades inconsistentes em {uf}/{ano}.")
        if sum(x["redacoes_validas"] for x in u1.values()) != um["brasil"]["redacoes_validas"]:
            raise ValueError(f"Soma estadual ≠ total do Brasil em {ano}.")
        if sum(x["n_validas"] for x in u2.values()) != dois["brasil"]["n_validas"]:
            raise ValueError(f"Soma estadual do IND-002 ≠ Brasil em {ano}.")

    total1 = d1["historical"]["brasil"]["redacoes_validas"]
    total2 = d2["historical"]["brasil"]["n_validas"]
    if total1 != total2 or total1 != sum(x["brasil"]["redacoes_validas"] for x in anos1.values()):
        raise ValueError("O consolidado histórico não reconcilia com os sete anos.")
    return sorted(anos1)


@st.cache_data(show_spinner=False)
def carregar_jsons(caminho1: str, caminho2: str, versao1: int, versao2: int):
    """Os horários de modificação invalidam o cache ao regenerar os JSONs."""
    with open(caminho1, encoding="utf-8") as arquivo:
        ind001 = json.load(arquivo)
    with open(caminho2, encoding="utf-8") as arquivo:
        ind002 = json.load(arquivo)
    anos = conferir_integridade(ind001, ind002)
    return ind001, ind002, anos


@st.cache_data(show_spinner=False)
def carregar_opcional(caminho: str, versao: int) -> dict:
    """Mantém o arquivo opcional sincronizado com alterações dos JSONs."""
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def conferir_opcional(doc: dict, ident: str, config: dict, ind001: dict, ind002: dict) -> None:
    """Confere estrutura, N e coerência; não reexecuta o cálculo nos microdados."""
    if doc.get("indicator", {}).get("id") != ident:
        raise ValueError(f"Identificador incorreto em {config['path'].name}.")
    anos1 = {x["ano"]: x for x in ind001["years"]}
    anos2 = {x["ano"]: x for x in ind002["years"]}
    anos = {x["ano"]: x for x in doc["years"]}
    if set(anos) != set(anos1):
        raise ValueError(f"{ident}: a série não contém os mesmos sete anos.")

    def comparar(a: dict, b: dict, c: dict, descricao: str):
        if c["n_validas"] != a["redacoes_validas"] or c["n_validas"] != b["n_validas"]:
            raise ValueError(f"{ident}: quantidade de redações divergente em {descricao}.")
        valor = c.get(config["campo"])
        if not isinstance(valor, (int, float)) or not (0 <= valor <= 1000):
            raise ValueError(f"{ident}: valor fora do intervalo esperado em {descricao}.")
        if ident == "IND-004":
            if abs(c["media"] - b["media"]) > 0.00011:
                raise ValueError(f"{ident}: média base divergente do IND-002 em {descricao}.")

    for ano in sorted(anos):
        base1, base2, dado = anos1[ano], anos2[ano], anos[ano]
        comparar(base1["brasil"], base2["brasil"], dado["brasil"], str(ano))
        u1 = {x["uf"]: x for x in base1["ufs"]}
        u2 = {x["uf"]: x for x in base2["ufs"]}
        u = {x["uf"]: x for x in dado["ufs"]}
        if len(dado["ufs"]) != 27 or set(u) != TODAS_UFS:
            raise ValueError(f"{ident}: UFs inválidas em {ano}.")
        for uf in TODAS_UFS:
            comparar(u1[uf], u2[uf], u[uf], f"{uf}/{ano}")
        if sum(x["n_validas"] for x in u.values()) != dado["brasil"]["n_validas"]:
            raise ValueError(f"{ident}: UFs não reconciliam com Brasil em {ano}.")

    h1, h2, h = ind001["historical"], ind002["historical"], doc["historical"]
    comparar(h1["brasil"], h2["brasil"], h["brasil"], "2019–2025")
    uh1 = {x["uf"]: x for x in h1["ufs"]}
    uh2 = {x["uf"]: x for x in h2["ufs"]}
    uh = {x["uf"]: x for x in h["ufs"]}
    if len(h["ufs"]) != 27 or set(uh) != TODAS_UFS:
        raise ValueError(f"{ident}: 27 UFs históricas ausentes ou duplicadas.")
    for uf in TODAS_UFS:
        comparar(uh1[uf], uh2[uf], uh[uf], f"{uf}/2019–2025")
    if sum(x["n_validas"] for x in uh.values()) != h["brasil"]["n_validas"]:
        raise ValueError(f"{ident}: UFs históricas não reconciliam com Brasil.")


def valor_opcional(doc: dict, config: dict, periodo: str, uf: str) -> float:
    if periodo == "2019–2025 (consolidado)":
        selecao = doc["historical"]
    else:
        selecao = next(x for x in doc["years"] if x["ano"] == int(periodo))
    resultado = selecao["brasil"] if uf == "BR" else next(x for x in selecao["ufs"] if x["uf"] == uf)
    return float(resultado[config["campo"]])


def complementar_serie(frame: pd.DataFrame, disponiveis: dict, uf: str) -> pd.DataFrame:
    frame = frame.copy()
    for identificador, documento in disponiveis.items():
        config = OPCIONAIS[identificador]
        frame[config["coluna"]] = [valor_opcional(documento, config, str(ano), uf) for ano in frame["Ano"]]
    return frame


def complementar_tabela(frame: pd.DataFrame, disponiveis: dict, periodo: str) -> pd.DataFrame:
    frame = frame.copy()
    for identificador, documento in disponiveis.items():
        config = OPCIONAIS[identificador]
        frame[config["coluna"]] = [valor_opcional(documento, config, periodo, uf) for uf in frame["UF"]]
    return frame


def dados_periodo(ind001: dict, ind002: dict, periodo: str, uf: str) -> dict:
    """Retorna um conjunto único de valores para Brasil ou UF e ano/histórico."""
    if periodo == "2019–2025 (consolidado)":
        x = ind001["historical"]
        y = ind002["historical"]
    else:
        ano = int(periodo)
        x = next(item for item in ind001["years"] if item["ano"] == ano)
        y = next(item for item in ind002["years"] if item["ano"] == ano)
    if uf == "BR":
        a, b = x["brasil"], y["brasil"]
    else:
        a = next(item for item in x["ufs"] if item["uf"] == uf)
        b = next(item for item in y["ufs"] if item["uf"] == uf)
    if a["redacoes_validas"] != b["n_validas"]:
        raise ValueError(f"Denominador diferente entre indicadores para {periodo}, {uf}.")
    return {
        "uf": uf,
        "periodo": periodo,
        "n": int(a["redacoes_validas"]),
        "total": int(a["total_registros"]) if "total_registros" in a else None,
        "percentual": a.get("percentual_validas"),
        "media": b["media"],
        "soma": b["soma_notas"],
    }


def serie_uf(ind001: dict, ind002: dict, uf: str) -> pd.DataFrame:
    linhas = []
    for ano in range(2019, 2026):
        item = dados_periodo(ind001, ind002, str(ano), uf)
        linhas.append({"Ano": ano, "Redações válidas": item["n"],
                       "Nota média": item["media"], "% válidas": item["percentual"]})
    return pd.DataFrame(linhas)


def tabela_ufs(ind001: dict, ind002: dict, periodo: str) -> pd.DataFrame:
    linhas = []
    for uf in sorted(TODAS_UFS):
        d = dados_periodo(ind001, ind002, periodo, uf)
        linhas.append({"UF": uf, "Estado": UF_NOMES[uf],
                       "Redações válidas": d["n"], "Nota média": d["media"],
                       "% válidas": d["percentual"]})
    return pd.DataFrame(linhas)


def grafico_linha(frame: pd.DataFrame, coluna: str, eixo_y: str):
    grafico = go.Figure()
    grafico.add_trace(go.Scatter(
        x=frame["Ano"], y=frame[coluna], mode="lines+markers+text",
        text=frame[coluna].apply(lambda x: decimal(x, 1) if coluna in ("Nota média", "Mediana", "Desvio-padrão") else ""),
        textposition="top center", name=coluna,
        line=dict(color=COR_PRINCIPAL, width=3),
        marker=dict(size=10, color=COR_PRINCIPAL),
        hovertemplate="Ano %{x}<br>Valor %{y:,.2f}<extra></extra>",
    ))
    grafico.update_layout(
        height=345, margin=dict(l=12, r=12, t=30, b=8),
        xaxis=dict(title="", tickmode="array", tickvals=list(range(2019, 2026))),
        yaxis=dict(title=eixo_y, rangemode="tozero" if coluna == "Redações válidas" else "normal"),
        hovermode="x unified", showlegend=False,
    )
    return grafico


def grafico_ranking(tabela: pd.DataFrame, coluna: str, selecionada: str, mostrar_todas: bool):
    tab = tabela.sort_values(coluna, ascending=False).copy()
    if not mostrar_todas:
        tab = tab.head(12)
        if selecionada != "BR" and selecionada not in set(tab["UF"]):
            tab = pd.concat([tab, tabela[tabela["UF"] == selecionada]], ignore_index=True)
    tab = tab.sort_values(coluna, ascending=True)
    cores = [COR_DESTAQUE if u == selecionada else COR_PRINCIPAL for u in tab["UF"]]
    figura = go.Figure(go.Bar(
        x=tab[coluna], y=tab["UF"], orientation="h", marker_color=cores,
        customdata=tab[["Estado", "Redações válidas", "Nota média"]].to_numpy(),
        hovertemplate=("%{customdata[0]} (%{y})<br>" +
                       ("Redações válidas: %{x:,.0f}" if coluna == "Redações válidas"
                        else f"{coluna}: %{{x:,.2f}}") +
                       "<br>N: %{customdata[1]:,.0f}<extra></extra>"),
    ))
    figura.update_layout(
        height=max(420, 30 * len(tab) + 85), margin=dict(l=12, r=15, t=15, b=15),
        xaxis_title="Redações válidas" if coluna == "Redações válidas" else f"{coluna} (pontos)",
        yaxis_title="", showlegend=False,
    )
    return figura


st.set_page_config(
    page_title="ENEM | Visualizador local", page_icon="📊",
    layout="wide", initial_sidebar_state="expanded",
)

st.title("ENEM · Painel exploratório")
st.caption("Projeto Integrador IV — análise local dos indicadores IND-001 a IND-004 · 2019 a 2025")

faltantes = [p for p in (ARQ_001, ARQ_002) if not p.is_file()]
if faltantes:
    st.error("Não encontrei os arquivos JSON necessários em `outputs/json/`.")
    st.code("\n".join(str(p) for p in faltantes), language="text")
    st.info("Execute primeiro os scripts IND-001 e IND-002, a partir da raiz do projeto.")
    st.stop()

try:
    ind1, ind2, anos = carregar_jsons(
        str(ARQ_001), str(ARQ_002), ARQ_001.stat().st_mtime_ns, ARQ_002.stat().st_mtime_ns,
    )
except (ValueError, KeyError, TypeError, json.JSONDecodeError) as erro:
    st.error(f"Os arquivos JSON precisam de revisão antes da visualização: {erro}")
    st.stop()

disponiveis = {}
for ident, config in OPCIONAIS.items():
    caminho = config["path"]
    if not caminho.is_file():
        continue  # Indicador ainda não executado: painel continua funcionando.
    try:
        documento = carregar_opcional(str(caminho), caminho.stat().st_mtime_ns)
        conferir_opcional(documento, ident, config, ind1, ind2)
        disponiveis[ident] = documento
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as erro:
        st.warning(f"O arquivo {caminho.name} existe, mas não foi carregado: {erro}")

outros_jsons = sorted(
    p for p in PASTA_JSON.glob("IND_[0-9][0-9][0-9]_*.json")
    if p.name not in {ARQ_001.name, ARQ_002.name, *(conf["path"].name for conf in OPCIONAIS.values())}
)

with st.sidebar:
    st.header("Filtros")
    periodo = st.selectbox(
        "Ano / período", [str(a) for a in reversed(anos)] + ["2019–2025 (consolidado)"],
        index=1, help="Consolidado = soma das participações e média ponderada, não pessoas únicas.",
    )
    opcoes_uf = ["BR", *sorted(TODAS_UFS)]
    uf = st.selectbox(
        "Abrangência geográfica", opcoes_uf,
        format_func=lambda v: "Brasil" if v == "BR" else f"{UF_NOMES[v]} ({v})",
    )
    st.divider()
    st.caption("Fonte geográfica: UF de aplicação da prova (`SG_UF_PROVA`), não UF de residência.")
    if st.button("Atualizar leitura dos JSONs", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("Somente dados agregados. Nenhum microdado é carregado neste painel.")
    st.caption("Indicadores detectados: " + ", ".join(["IND-001", "IND-002", *disponiveis]))

selecionado = dados_periodo(ind1, ind2, periodo, uf)
brasil = dados_periodo(ind1, ind2, periodo, "BR")
nome_local = "Brasil" if uf == "BR" else f"{UF_NOMES[uf]} ({uf})"

st.subheader(f"{nome_local} · {periodo}")
if ind1["meta"].get("data_status") != "approved" or ind2["meta"].get("data_status") != "approved":
    st.info("Resultados validados tecnicamente, mas ainda identificados como **draft** nos JSONs. Este painel não é a publicação oficial.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("IND-001 · Redações válidas", inteiro(selecionado["n"]))
col2.metric("IND-002 · Nota média", f"{decimal(selecionado['media'], 2)} pontos")
col3.metric("Redações válidas / registros", f"{decimal(selecionado['percentual'], 2)}%")
if uf == "BR":
    col4.metric("Abrangência", "Nacional")
else:
    diferenca = selecionado["media"] - brasil["media"]
    col4.metric("Diferença ante o Brasil", f"{decimal(diferenca, 2)} pts",
                delta=f"{decimal(diferenca, 2)} pts", delta_color="normal")

if disponiveis:
    colunas_extra = st.columns(len(disponiveis))
    for coluna, (ident, documento) in zip(colunas_extra, disponiveis.items()):
        config = OPCIONAIS[ident]
        pontuacao = valor_opcional(documento, config, periodo, uf)
        coluna.metric(f"{ident} · {config['label']}", f"{decimal(pontuacao, 2)} pontos")

aba1, aba2, aba3, aba4 = st.tabs([
    "Visão geral", "Evolução histórica", "Comparação entre UFs", "Método e qualidade",
])

with aba1:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown("#### Evolução da nota média")
        serie = serie_uf(ind1, ind2, uf)
        st.plotly_chart(grafico_linha(serie, "Nota média", "Pontos"), use_container_width=True)
    with c2:
        st.markdown("#### Evolução das redações válidas")
        st.plotly_chart(grafico_linha(serie, "Redações válidas", "Quantidade"), use_container_width=True)
    if uf != "BR":
        st.caption(f"A média nacional no período selecionado é {decimal(brasil['media'], 2)} pontos; "
                   f"a média de {nome_local} é {decimal(selecionado['media'], 2)} pontos.")
    if disponiveis:
        st.markdown("#### Evolução dos indicadores adicionais")
        serie_completa = complementar_serie(serie, disponiveis, uf)
        colunas = st.columns(len(disponiveis))
        for coluna, (ident, documento) in zip(colunas, disponiveis.items()):
            config = OPCIONAIS[ident]
            with coluna:
                st.plotly_chart(
                    grafico_linha(serie_completa, config["coluna"], "Pontos"),
                    use_container_width=True,
                )
    st.caption("As diferenças entre edições são descritivas: mudam o tema, a composição dos participantes e o contexto de aplicação.")

with aba2:
    st.markdown(f"#### Série anual · {nome_local}")
    serie = complementar_serie(serie_uf(ind1, ind2, uf), disponiveis, uf)
    dados_tabela = serie.copy()
    for coluna in ["Nota média", "Mediana", "Desvio-padrão"]:
        if coluna in dados_tabela:
            dados_tabela[coluna] = dados_tabela[coluna].round(2)
    st.dataframe(dados_tabela, hide_index=True, use_container_width=True)
    st.download_button(
        "Baixar série selecionada (CSV)",
        data=dados_tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"enem_serie_{uf}_2019_2025.csv", mime="text/csv",
    )
    hist = dados_periodo(ind1, ind2, "2019–2025 (consolidado)", uf)
    st.write(f"**Consolidado histórico:** {inteiro(hist['n'])} participações com redação válida; "
             f"**média ponderada:** {decimal(hist['media'], 2)} pontos.")
    st.caption("Não representa pessoas únicas: uma mesma pessoa pode ter participado de mais de uma edição.")

with aba3:
    st.markdown(f"#### Comparação das 27 UFs · {periodo}")
    tabela = complementar_tabela(tabela_ufs(ind1, ind2, periodo), disponiveis, periodo)
    opcoes = ["Nota média", "Redações válidas"] + [OPCIONAIS[k]["coluna"] for k in disponiveis]
    tipo = st.radio("Comparar", opcoes, horizontal=True)
    todas = st.checkbox("Mostrar todas as 27 UFs", value=False)
    st.plotly_chart(grafico_ranking(tabela, tipo, uf, todas), use_container_width=True)
    st.caption("Barras representam UFs de aplicação da prova. A UF escolhida nos filtros fica destacada em laranja, quando selecionada.")
    st.dataframe(tabela.sort_values(tipo, ascending=False), hide_index=True,
                 use_container_width=True)
    st.download_button(
        "Baixar comparação por UF (CSV)",
        data=tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"enem_comparacao_ufs_{periodo.replace('–', '-')}.csv",
        mime="text/csv",
    )

with aba4:
    st.markdown("#### Definição dos indicadores")
    st.write("**IND-001 — Redações válidas:** `TP_STATUS_REDACAO = 1` e "
             "`NU_NOTA_REDACAO` numérica entre 0 e 1000, inclusive.")
    st.write("**IND-002 — Nota média:** soma das notas finais das redações válidas "
             "dividida pelo número dessas redações.")
    st.write("**Consolidado de 2019–2025:** soma das redações válidas e média "
             "ponderada pela quantidade de redações em cada edição.")
    for ident, documento in disponiveis.items():
        config = OPCIONAIS[ident]
        st.write(f"**{ident} — {config['label']}:** {config['definicao']}")
    st.markdown("#### Fontes e status")
    fontes = [
        {"Indicador": "IND-001", "Arquivo": ARQ_001.name,
         "Status": ind1["meta"].get("data_status", "não informado"),
         "Gerado em (UTC)": ind1["meta"].get("generated_at", "")},
        {"Indicador": "IND-002", "Arquivo": ARQ_002.name,
         "Status": ind2["meta"].get("data_status", "não informado"),
         "Gerado em (UTC)": ind2["meta"].get("generated_at", "")},
    ]
    for ident, documento in disponiveis.items():
        fontes.append({"Indicador": ident, "Arquivo": OPCIONAIS[ident]["path"].name,
            "Status": documento["meta"].get("data_status", "não informado"),
            "Gerado em (UTC)": documento["meta"].get("generated_at", "")})
    st.dataframe(pd.DataFrame(fontes), hide_index=True, use_container_width=True)
    if outros_jsons:
        st.info("Novos JSONs encontrados (ainda sem gráficos específicos): " +
                ", ".join(p.name for p in outros_jsons))
        st.caption("O visualizador reconhece esses arquivos, mas indicadores com estruturas próprias "
                   "exigem um gráfico apropriado antes de serem incluídos na visualização.")
    st.success("Verificação local aprovada: as contagens anuais e estaduais dos indicadores carregados "
               "coincidem e as 27 UFs reconciliam com os totais nacionais.")
    st.warning("A conferência no visualizador não equivale à auditoria dos CSVs "
               "originais nem à aprovação acadêmica dos indicadores.")
    st.caption("O painel não tenta vincular PARTICIPANTES_2025 e RESULTADOS_2025; "
               "os indicadores 001 a 004 não exigem essa junção.")

st.divider()
st.caption("Visualizador exploratório local · Projeto Integrador IV — UNIVESP · "
           "Indicadores carregados: " + ", ".join(["IND-001", "IND-002", *disponiveis]) +
           " · Não substitui a interface final dos desenvolvedores.")
