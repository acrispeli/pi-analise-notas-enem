import { useFiltros } from './filtros.tsx';
import { rotuloUf } from './filtros.tsx';
import { useDados } from './useDados.ts';

type Guia = {
  oque: string;
  como: string;
  pedagogia: string;
  cuidado?: string;
  glossario?: string;
  acao?: string;
};
type Guias = { natureza: string; fonte: string; indicadores: Record<string, Guia> };

// Chaves internas da interface: mantém associação explícita com o catálogo científico.
// Identificadores como "ind044-grafico" são associados automaticamente ao IND-044.
const CODIGOS: Record<string, number> = {
  histograma: 6, situacao: 7, 'ranking-uf': 52,
  'resumo-evolucao': 64, 'serie-questionario': 40,
  medias: 9, niveis: 12, correlacao: 13, variancia: 14,
  loadings: 15, hexbin: 16, perfis: 17,
  'diferenca-total': 20, 'diferenca-competencia': 21,
  kappa: 26, 'perfis-divergencia': 28,
  'faixas-900': 30, perda: 31,
  'perfil-grafico': 40, 'renda-nota': 41, 'renda-competencia': 42,
  'escolaridade-grafico': 43,
  'serie-validas': 1, 'serie-notas': 64, 'serie-desvio': 4,
  'serie-mil': 8, 'serie-competencias': 65,
  'serie-quase': 66, 'serie-divergencia': 67, 'serie-perfis': 68,
};

function numeroIndicador(identificador: string): number | null {
  if (CODIGOS[identificador]) return CODIGOS[identificador];
  const match = /^ind0?(\d{2,3})(?:-|$)/.exec(identificador);
  return match ? Number(match[1]) : null;
}

export function LeituraPedagogica({ identificador }: { identificador: string }) {
  const indicador = numeroIndicador(identificador);
  const { ano, uf } = useFiltros();
  const { dados } = useDados<Guias>(indicador === null ? null : '/data/guias-pedagogicos.json');
  const guia = indicador !== null ? dados?.indicadores[String(indicador)] : undefined;
  if (!guia || indicador === null) return null;
  const codigo = 'IND-' + String(indicador).padStart(3, '0');
  return (
    <details className="leitura-pedagogica" data-indicador={codigo}>
      <summary>Entenda este resultado · {codigo}</summary>
      <div className="leitura-pedagogica-corpo">
        <p className="nota">Recorte selecionado: {ano === 'todos' ? '2019–2025' : ano} · {rotuloUf(uf)}.
          A explicação a seguir descreve o indicador; não substitui a leitura dos valores no gráfico.</p>
        <h3>O que está sendo medido?</h3>
        <p>{guia.oque}</p>
        <h3>Como interpretar?</h3>
        <p>{guia.como}</p>
        {guia.glossario ? <p className="leitura-glossario"><strong>Glossário:</strong> {guia.glossario}</p> : null}
        <h3>O que isso pode ensinar?</h3>
        <p>{guia.pedagogia}</p>
        {guia.acao ? <><h3>Sugestão pedagógica</h3><p>{guia.acao}</p></> : null}
        <h3>Cuidados antes de concluir</h3>
        <p>{guia.cuidado ? guia.cuidado + ' ' : ''}
          São estatísticas agregadas; comparações não demonstram causalidade.
          Valores ausentes não representam zero e as edições podem ter populações distintas.</p>
        <p className="nota">Fonte editorial: leitura_acessivel_68.py e orientacoes_pedagogicas_68.py (Streamlit do projeto).
          Texto determinístico, sem geração por IA em tempo de consulta.</p>
      </div>
    </details>
  );
}
