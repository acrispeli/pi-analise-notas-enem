import { useState } from 'react';
import { COR, CORES, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Cartao, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarNota, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';
import { NOMES_UF } from '../lib/ufs.ts';

type CategoriaPerfil = { codigo?: string; rotulo?: string; quantidade?: number; percentual?: number; requires_privacy_review?: boolean };
type Questao = { questao?: string; tema?: string; categorias?: CategoriaPerfil[]; tem_agregacao_para_privacidade?: boolean };
type FaixaRenda = { codigo_renda?: string; faixa_renda?: string; descricao_faixa?: string; ordem?: number; n_redacoes?: number; media?: number; n_pequeno?: boolean; competencias?: Record<string, { media?: number; n_redacoes?: number }> };
type FaixaEscola = { codigo_escolaridade?: string; descricao_categoria?: string; ordem?: number; n_redacoes?: number; media?: number; n_pequeno?: boolean; suprimido?: boolean };
type CatCompetencia = {
  codigo_escolaridade?: string;
  descricao_categoria?: string;
  ordem?: number;
  n_redacoes?: number;
  suprimido?: boolean;
  competencias?: Record<string, { media?: number; mediana?: number; n_redacoes?: number }>;
};
type EscolaCompetencias = { questions?: Record<string, { responsavel?: string; categories?: CatCompetencia[] }> };
type TipoEscola = { categories?: (FaixaEscola & { codigo_escola?: string })[]; conceito?: string; source_variable?: string };
type Medida = { n_redacoes?: number; media?: number };
type CatMedidas = FaixaEscola & { medidas?: Record<string, Medida> };
type BlocoMedidas = {
  concept?: string;
  method?: string;
  privacy_note?: string;
  source_variable?: string;
  comparability_across_years?: string;
  national?: { categories?: CatMedidas[]; comparacao_sim_menos_nao?: Record<string, { diferenca_medias_sim_menos_nao?: number; status?: string }> };
  states?: Record<string, { categories?: CatMedidas[]; comparacao_sim_menos_nao?: Record<string, { diferenca_medias_sim_menos_nao?: number; status?: string }> }>;
};
type BlocoOcupacao = {
  privacy_note?: string;
  national?: Record<string, { responsavel?: string; categories?: FaixaEscola[] }>;
  states?: Record<string, Record<string, { responsavel?: string; categories?: FaixaEscola[] }>>;
};
type BlocoDemo = {
  privacy_note?: string;
  method?: string;
  national?: { dimensoes?: Record<string, { categories?: FaixaEscola[] }> };
  states?: Record<string, { dimensoes?: Record<string, { categories?: FaixaEscola[] }> }>;
};
type MetricaUf = { media?: number; n_redacoes?: number; suprimido?: boolean };
type CorteUf = { uf?: string; suprimido?: boolean; metricas?: Record<string, MetricaUf> };
type BlocoUf = { interpretation?: string; privacy_note?: string; national?: CorteUf; states?: Record<string, CorteUf> };

type Socio = {
  status?: string;
  profile?: {
    versao_questionario?: string;
    brasil?: { questoes?: Questao[]; n_participacoes?: number };
    ufs?: { uf: string; questoes?: Questao[] }[];
  };
  income_total?: { national?: Renda; states?: Record<string, Renda>; source_question?: string };
  income_competencies?: { national?: Renda; states?: Record<string, Renda> };
  parent_education_total?: { national?: Escola; states?: Record<string, Escola> };
  parent_education_competencies?: { national?: EscolaCompetencias; states?: Record<string, EscolaCompetencias> };
  school_type_total?: { national?: TipoEscola; states?: Record<string, TipoEscola>; source_variable?: string };
  school_type_competencies?: BlocoMedidas;
  internet_performance?: BlocoMedidas;
  computer_performance?: BlocoMedidas;
  parent_occupation?: BlocoOcupacao;
  household_size?: BlocoMedidas;
  demographics?: BlocoDemo;
  uf_performance?: BlocoUf;
};
type Renda = { faixas?: FaixaRenda[]; categories?: FaixaRenda[] };
type Escola = { questions?: Record<string, { responsavel?: string; categories?: FaixaEscola[] }> };

export default function Socioeconomico() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const pedido = useDados<Socio>(todos ? null : `/data/${ano}/socioeconomic.json`);
  const [questao, setQuestao] = useState('Q001');
  const [guardiao, setGuardiao] = useState<'Q001' | 'Q002'>('Q001');
  const [ocupacao, setOcupacao] = useState('pai_ou_responsavel_masculino');
  const [dimensao, setDimensao] = useState('TP_SEXO');

  if (todos) {
    return (
      <div>
        <h1>Questionário</h1>
        <p className="nota">C1 escrita formal · C2 tema · C3 argumentação · C4 coesão · C5 proposta de intervenção</p>
        <Aviso>Escolha um ano. O questionário muda entre as edições e não é somado.</Aviso>
      </div>
    );
  }
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;

  const doc = pedido.dados;
  const perfil = uf === 'BR' ? doc.profile?.brasil : porUf(doc.profile?.ufs, uf);
  const questoes = perfil?.questoes ?? [];
  const escolhida = questoes.find((item) => item.questao === questao) ?? questoes[0];
  const temCruzamento = Boolean(doc.income_total && doc.income_competencies && doc.parent_education_total);
  const renda = uf === 'BR' ? doc.income_total?.national : doc.income_total?.states?.[uf];
  const rendaComp = uf === 'BR' ? doc.income_competencies?.national : doc.income_competencies?.states?.[uf];
  const escola = uf === 'BR' ? doc.parent_education_total?.national : doc.parent_education_total?.states?.[uf];

  return (
    <div>
      <h1>Questionário</h1>
      <p className="nota">C1 escrita formal · C2 tema · C3 argumentação · C4 coesão · C5 proposta de intervenção</p>
      <p className="nota">Versão do questionário: {doc.profile?.versao_questionario ?? 'não disponível'}.</p>
      <section className="painel" data-visual="perfil">
        <h2>Como se distribuem as respostas do questionário?</h2>
        {questoes.length && escolhida ? (
          <>
            <label className="seletor">
              Pergunta
              <select value={escolhida.questao} onChange={(evento) => setQuestao(evento.target.value)}>
                {questoes.map((item) => (
                  <option key={item.questao} value={item.questao}>
                    {item.questao} — {item.tema}
                  </option>
                ))}
              </select>
            </label>
            <UmGrafico identificador="perfil-grafico" figura={graficoPerfil(escolhida, limiar)} />
            <p className="nota">
              Os rótulos são os códigos publicados no questionário.
              {escolhida.tem_agregacao_para_privacidade ? ' Há categorias reunidas por proteção de privacidade.' : ''}
            </p>
          </>
        ) : (
          <p className="indisponivel">não disponível</p>
        )}
      </section>
      {temCruzamento ? (
        <>
          <Grafico identificador="renda-nota" titulo="Qual é a nota média em cada faixa de renda?" figura={graficoRenda(renda, limiar)} nota="Renda familiar declarada. Passe o cursor para ler a faixa. Os valores são os desta edição." />
          <Grafico identificador="renda-competencia" titulo="Como a média de cada competência varia com a renda?" figura={graficoRendaCompetencia(rendaComp, limiar)} />
          <section className="painel" data-visual="escolaridade">
            <h2>Qual é a nota média segundo a escolaridade dos responsáveis?</h2>
            <label className="seletor">
              Responsável
              <select value={guardiao} onChange={(evento) => setGuardiao(evento.target.value as 'Q001' | 'Q002')}>
                <option value="Q001">{escola?.questions?.Q001?.responsavel ?? 'Q001'}</option>
                <option value="Q002">{escola?.questions?.Q002?.responsavel ?? 'Q002'}</option>
              </select>
            </label>
            <UmGrafico identificador="escolaridade-grafico" figura={graficoEscola(escola?.questions?.[guardiao]?.categories, limiar)} />
          </section>
          <EscolaridadeCompetencias doc={doc} uf={uf} guardiao={guardiao} definirGuardiao={setGuardiao} limiar={limiar} />
          <TipoEscolaGrafico doc={doc} uf={uf} limiar={limiar} />
        </>
      ) : (
        <>
          <Aviso>Em 2025 não há cruzamento da nota com renda, escolaridade ou tipo de escola.</Aviso>
        </>
      )}
      <IndicadoresNovos doc={doc} uf={uf} limiar={limiar} ocupacao={ocupacao} definirOcupacao={setOcupacao} dimensao={dimensao} definirDimensao={setDimensao} />
    </div>
  );
}

function EscolaridadeCompetencias({
  doc,
  uf,
  guardiao,
  definirGuardiao,
  limiar,
}: {
  doc: Socio;
  uf: string;
  guardiao: 'Q001' | 'Q002';
  definirGuardiao: (valor: 'Q001' | 'Q002') => void;
  limiar: number;
}) {
  const bloco = uf === 'BR' ? doc.parent_education_competencies?.national : doc.parent_education_competencies?.states?.[uf];
  if (!bloco) return <Grafico identificador="ind044" titulo="Como a escolaridade dos responsáveis se relaciona com cada competência?" figura={null} />;
  const pergunta = bloco.questions?.[guardiao];
  return (
    <section className="painel" data-visual="ind044">
      <h2>Como a escolaridade dos responsáveis se relaciona com cada competência?</h2>
      <label className="seletor">
        Responsável
        <select value={guardiao} onChange={(evento) => definirGuardiao(evento.target.value as 'Q001' | 'Q002')}>
          <option value="Q001">{bloco.questions?.Q001?.responsavel ?? 'Q001'}</option>
          <option value="Q002">{bloco.questions?.Q002?.responsavel ?? 'Q002'}</option>
        </select>
      </label>
      <UmGrafico identificador="ind044-grafico" figura={graficoEscolaCompetencias(pergunta?.categories, limiar)} />
      <p className="nota">Nota de 0 a 200. Grupo pequeno demais não entra como zero.</p>
    </section>
  );
}

function TipoEscolaGrafico({ doc, uf, limiar }: { doc: Socio; uf: string; limiar: number }) {
  const bloco = uf === 'BR' ? doc.school_type_total?.national : doc.school_type_total?.states?.[uf];
  return (
    <Grafico
      identificador="ind045"
      titulo="Qual é a nota média segundo a trajetória escolar declarada?"
      figura={graficoEscola(bloco?.categories, limiar)}
      nota="Trajetória declarada no ensino médio. A pergunta muda entre os anos e as respostas não são somadas."
    />
  );
}

function UmGrafico({ figura, identificador }: { figura: Figura | null; identificador: string }) {
  return <Grafico identificador={identificador} titulo="" figura={figura} embutido />;
}

function graficoPerfil(questao: Questao, limiar: number): Figura | null {
  const linhas = [];
  for (const categoria of questao.categorias ?? []) {
    const n = contagemPublicavel(categoria.quantidade, limiar, categoria);
    const pct = numero(categoria.percentual);
    if (n === null || pct === null) continue;
    linhas.push({ rotulo: categoria.rotulo || categoria.codigo || '', pct });
  }
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: linhas.map((item) => item.rotulo), x: linhas.map((item) => item.pct), marker: { color: COR }, hovertemplate: '%{y}: %{x:.1f}%<extra></extra>' }],
    altura: Math.max(280, linhas.length * 32),
    layout: { margin: { l: 220 }, xaxis: { title: { text: 'Participações (%)' } } },
  };
}

function faixasRenda(renda: Renda | undefined, limiar: number): { codigo: string; descricao: string; media: number | null; competencias?: FaixaRenda['competencias']; ordem: number }[] {
  const lista = [...(renda?.faixas ?? renda?.categories ?? [])].sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0));
  return lista.map((faixa) => ({
    codigo: faixa.faixa_renda || faixa.codigo_renda || '',
    descricao: faixa.descricao_faixa || '',
    media: metricaPublicavel(faixa.media, faixa.n_redacoes, limiar, faixa),
    competencias: faixa.competencias,
    ordem: faixa.ordem ?? 0,
  }));
}

function graficoRenda(renda: Renda | undefined, limiar: number): Figura | null {
  const linhas = faixasRenda(renda, limiar).filter((item) => item.media !== null && item.codigo);
  if (!linhas.length) return null;
  return {
    data: [{
      type: 'bar',
      x: linhas.map((item) => item.codigo),
      y: linhas.map((item) => item.media),
      customdata: linhas.map((item) => item.descricao),
      marker: { color: COR },
      hovertemplate: '%{x}<br>%{customdata}<br>%{y:.1f}<extra></extra>',
    }],
    altura: 360,
    layout: { xaxis: { title: { text: 'Faixa de renda' } }, yaxis: { title: { text: 'Nota média' }, range: [0, 1000] } },
  };
}

function graficoRendaCompetencia(renda: Renda | undefined, limiar: number): Figura | null {
  const base = faixasRenda(renda, limiar).filter((item) => item.codigo && item.competencias);
  if (!base.length) return null;
  const data = ['C1', 'C2', 'C3', 'C4', 'C5'].map((codigo, indice) => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: codigo,
    x: base.map((item) => item.codigo),
    y: base.map((item) => {
      const celula = item.competencias?.[codigo];
      if (!celula) return null;
      return metricaPublicavel(celula.media, celula.n_redacoes, limiar);
    }),
    line: { color: CORES[indice % CORES.length] },
    connectgaps: false,
  }));
  if (data.every((traco) => (traco.y as (number | null)[]).every((valor) => valor === null))) return null;
  return {
    data,
    altura: 440,
    layout: {
      margin: { b: 100 },
      yaxis: { title: { text: 'Nota média da competência' }, range: [0, 200] },
      xaxis: { title: { text: 'Faixa de renda' } },
    },
  };
}

function graficoEscola(categorias: FaixaEscola[] | undefined, limiar: number): Figura | null {
  if (!categorias?.length) return null;
  const linhas = [...categorias]
    .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
    .map((item) => ({
      nome: item.descricao_categoria || item.codigo_escolaridade || '',
      media: metricaPublicavel(item.media, item.n_redacoes, limiar, item),
    }))
    .filter((item) => item.media !== null && item.nome);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.media), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.1f}<extra></extra>' }],
    altura: 360,
    layout: { margin: { b: 128 }, yaxis: { title: { text: 'Nota média' }, range: [0, 1000] }, xaxis: { tickangle: -35 } },
  };
}

function graficoEscolaCompetencias(categorias: CatCompetencia[] | undefined, limiar: number): Figura | null {
  if (!categorias?.length) return null;
  const linhas = [...categorias]
    .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
    .map((item) => ({
      nome: item.descricao_categoria || item.codigo_escolaridade || '',
      valores: ['C1', 'C2', 'C3', 'C4', 'C5'].map((codigo) => {
        if (item.suprimido) return null;
        const celula = item.competencias?.[codigo];
        if (!celula) return null;
        return metricaPublicavel(celula.media, celula.n_redacoes ?? item.n_redacoes, limiar, item);
      }),
    }))
    .filter((item) => item.nome && item.valores.some((valor) => valor !== null));
  if (!linhas.length) return null;
  const y = linhas.map((item) => item.nome);
  const x = ['C1', 'C2', 'C3', 'C4', 'C5'];
  const z = linhas.map((item) => item.valores);
  if (z.every((linha) => linha.every((valor) => valor === null))) return null;
  const texto = z.map((linha) => linha.map((valor) => (valor === null ? '' : formatarNota(valor))));
  return {
    data: [{ type: 'heatmap', x, y, z, text: texto, texttemplate: '%{text}', colorscale: 'Blues', zmin: 0, zmax: 200, hovertemplate: '%{y} · %{x}: %{z:.1f}<extra></extra>' }],
    altura: Math.max(420, y.length * 28),
    layout: { margin: { l: 220, b: 48 } },
  };
}

const RESPONSAVEL: Record<string, string> = {
  pai_ou_responsavel_masculino: 'Pai ou homem responsável',
  mae_ou_responsavel_feminino: 'Mãe ou mulher responsável',
};

const DIMENSOES: Record<string, string> = {
  TP_SEXO: 'Sexo',
  TP_FAIXA_ETARIA: 'Faixa etária',
  TP_COR_RACA: 'Cor ou raça',
};

function IndicadoresNovos({
  doc,
  uf,
  limiar,
  ocupacao,
  definirOcupacao,
  dimensao,
  definirDimensao,
}: {
  doc: Socio;
  uf: string;
  limiar: number;
  ocupacao: string;
  definirOcupacao: (valor: string) => void;
  dimensao: string;
  definirDimensao: (valor: string) => void;
}) {
  const escola = uf === 'BR' ? doc.school_type_competencies?.national : doc.school_type_competencies?.states?.[uf];
  const internet = uf === 'BR' ? doc.internet_performance?.national : doc.internet_performance?.states?.[uf];
  const computador = uf === 'BR' ? doc.computer_performance?.national : doc.computer_performance?.states?.[uf];
  const casa = uf === 'BR' ? doc.household_size?.national : doc.household_size?.states?.[uf];
  const ocupacoes = uf === 'BR' ? doc.parent_occupation?.national : doc.parent_occupation?.states?.[uf];
  const demo = uf === 'BR' ? doc.demographics?.national : doc.demographics?.states?.[uf];
  const diff = internet?.comparacao_sim_menos_nao?.C0;
  const diferenca = diff?.status === 'ok' ? numero(diff.diferenca_medias_sim_menos_nao) : null;
  const chavesOcupacao = Object.keys(ocupacoes ?? {});
  const ocupacaoAtiva = chavesOcupacao.includes(ocupacao) ? ocupacao : chavesOcupacao[0];
  const chavesDemo = Object.keys(demo?.dimensoes ?? {});
  const demoAtiva = chavesDemo.includes(dimensao) ? dimensao : chavesDemo[0];

  return (
    <>
      {doc.school_type_competencies ? (
        <Grafico
          identificador="ind046"
          titulo="Como a trajetória escolar declarada se relaciona com cada competência?"
          figura={graficoEscolaCompetencias(escola?.categories as CatCompetencia[] | undefined, limiar)}
          nota="Trajetória declarada no ensino médio. A pergunta muda entre os anos e as respostas não são somadas."
        />
      ) : null}
      {doc.internet_performance ? (
        <>
          <Grafico
            identificador="ind047"
            titulo="A nota média muda com o acesso à internet no domicílio?"
            figura={graficoEscola(comoNota(internet?.categories, 'C0'), limiar)}
            nota="Wi-Fi declarado em casa. A diferença descreve os grupos e não é causa da nota."
          />
          {diferenca !== null ? (
            <div className="grade">
              <Cartao rotulo="Pontos a mais de quem tem internet" valor={formatarNota(diferenca)} detalhe="Diferença entre as médias, sim menos não." />
            </div>
          ) : null}
          <Grafico
            identificador="ind047-competencias"
            titulo="Como a média de cada competência muda com o acesso à internet?"
            figura={graficoEscolaCompetencias(comoCompetencias(internet?.categories), limiar)}
          />
        </>
      ) : null}
      {doc.computer_performance ? (
        <>
          <Grafico
            identificador="ind048"
            titulo="A nota média muda com a quantidade de computadores no domicílio?"
            figura={graficoEscola(comoNota(computador?.categories, 'C0'), limiar)}
            nota="Computadores ou notebooks declarados em casa."
          />
          <Grafico
            identificador="ind048-competencias"
            titulo="Como a média de cada competência muda com a quantidade de computadores?"
            figura={graficoEscolaCompetencias(comoCompetencias(computador?.categories), limiar)}
          />
        </>
      ) : null}
      {doc.parent_occupation && ocupacaoAtiva ? (
        <section className="painel" data-visual="ind049">
          <h2>Qual é a nota média segundo a ocupação dos responsáveis?</h2>
          <label className="seletor">
            Responsável
            <select value={ocupacaoAtiva} onChange={(evento) => definirOcupacao(evento.target.value)}>
              {chavesOcupacao.map((chave) => (
                <option key={chave} value={chave}>{RESPONSAVEL[ocupacoes?.[chave]?.responsavel ?? ''] ?? RESPONSAVEL[chave] ?? chave}</option>
              ))}
            </select>
          </label>
          <UmGrafico identificador="ind049-grafico" figura={graficoEscola(ocupacoes?.[ocupacaoAtiva]?.categories, limiar)} />
          <p className="nota">Pai e mãe aparecem separados. O nome do grupo é o do questionário.</p>
        </section>
      ) : null}
      {doc.household_size ? (
        <Grafico
          identificador="ind050"
          titulo="Qual é a nota média segundo o número de moradores?"
          figura={graficoEscola(comoNota(casa?.categories, 'media'), limiar)}
          nota="Quantidade de moradores declarada, incluindo quem fez a prova."
        />
      ) : null}
      {doc.demographics && demoAtiva ? (
        <section className="painel" data-visual="ind051">
          <h2>Qual é a nota média em cada grupo?</h2>
          <label className="seletor">
            Grupo
            <select value={demoAtiva} onChange={(evento) => definirDimensao(evento.target.value)}>
              {chavesDemo.map((chave) => (
                <option key={chave} value={chave}>{DIMENSOES[chave] ?? chave}</option>
              ))}
            </select>
          </label>
          <UmGrafico identificador="ind051-grafico" figura={graficoEscola(demo?.dimensoes?.[demoAtiva]?.categories, limiar)} />
          <p className="nota">Um grupo por vez. Este seletor não muda as outras páginas.</p>
        </section>
      ) : null}
      {doc.uf_performance ? <DesempenhoUf bloco={doc.uf_performance} uf={uf} limiar={limiar} /> : null}
    </>
  );
}

function comoNota(categorias: CatMedidas[] | undefined, chave: 'C0' | 'media'): FaixaEscola[] | undefined {
  return categorias?.map((item) => ({
    descricao_categoria: item.descricao_categoria,
    ordem: item.ordem,
    n_redacoes: chave === 'C0' ? item.medidas?.C0?.n_redacoes ?? item.n_redacoes : item.n_redacoes,
    media: chave === 'C0' ? item.medidas?.C0?.media : item.media,
    suprimido: item.suprimido,
  }));
}

function comoCompetencias(categorias: CatMedidas[] | undefined): CatCompetencia[] | undefined {
  return categorias?.map((item) => {
    const competencias: NonNullable<CatCompetencia['competencias']> = {};
    for (const codigo of ['C1', 'C2', 'C3', 'C4', 'C5']) {
      const medida = item.medidas?.[codigo];
      if (medida) competencias[codigo] = medida;
    }
    return {
      descricao_categoria: item.descricao_categoria,
      ordem: item.ordem,
      n_redacoes: item.n_redacoes,
      suprimido: item.suprimido,
      competencias,
    };
  });
}

function DesempenhoUf({ bloco, uf, limiar }: { bloco: BlocoUf; uf: string; limiar: number }) {
  const nota = 'UF onde a prova foi feita, não onde a pessoa mora.';
  if (uf !== 'BR') {
    const corte = bloco.states?.[uf];
    return (
      <Grafico
        identificador="ind052"
        titulo="Qual é a média de cada competência nesta UF da prova?"
        figura={barrasCompetencia(corte, limiar)}
        nota={nota}
      />
    );
  }
  return (
    <Grafico
      identificador="ind052"
      titulo="Como as competências variam entre as UFs da prova?"
      figura={mapaUf(bloco.states, limiar)}
      nota={nota}
    />
  );
}

function barrasCompetencia(corte: CorteUf | undefined, limiar: number): Figura | null {
  if (!corte || corte.suprimido) return null;
  const codigos = ['C1', 'C2', 'C3', 'C4', 'C5'];
  const y = codigos.map((codigo) => {
    const item = corte.metricas?.[codigo];
    if (!item || item.suprimido) return null;
    return metricaPublicavel(item.media, item.n_redacoes, limiar, item);
  });
  if (y.every((valor) => valor === null)) return null;
  return {
    data: [{ type: 'bar', x: codigos, y, marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.1f}<extra></extra>' }],
    altura: 340,
    layout: { yaxis: { title: { text: 'Nota média' }, range: [0, 200] }, xaxis: { title: { text: 'Competência' } } },
  };
}

function mapaUf(estados: Record<string, CorteUf> | undefined, limiar: number): Figura | null {
  if (!estados) return null;
  const linhas = Object.values(estados).filter((item) => item.uf && !item.suprimido);
  const codigos = ['C1', 'C2', 'C3', 'C4', 'C5'];
  const y = linhas.map((item) => NOMES_UF[item.uf ?? ''] ?? item.uf ?? '');
  const z = linhas.map((item) => codigos.map((codigo) => {
    const celula = item.metricas?.[codigo];
    if (!celula || celula.suprimido) return null;
    return metricaPublicavel(celula.media, celula.n_redacoes, limiar, celula);
  }));
  if (!y.length || z.every((linha) => linha.every((valor) => valor === null))) return null;
  const texto = z.map((linha) => linha.map((valor) => (valor === null ? '' : formatarNota(valor))));
  return {
    data: [{ type: 'heatmap', x: codigos, y, z, text: texto, texttemplate: '%{text}', colorscale: 'Blues', zmin: 0, zmax: 200, hovertemplate: '%{y} · %{x}: %{z:.1f}<extra></extra>' }],
    altura: Math.max(520, y.length * 22),
    layout: { margin: { l: 140, b: 48 } },
  };
}
