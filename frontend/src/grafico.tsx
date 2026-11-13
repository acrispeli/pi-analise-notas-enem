import { useEffect, useId, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
import { LeituraPedagogica } from './LeituraPedagogica.tsx';

const Plot = createPlotlyComponent(Plotly);

const CONFIG = {
  displayModeBar: 'hover' as const,
  responsive: true,
  displaylogo: false,
  scrollZoom: false,
  toImageButtonOptions: {
    format: 'png' as const,
    filename: 'grafico-redacao-enem',
    height: 800,
    width: 1280,
    scale: 1,
  },
};

export type Figura = {
  data: object[];
  layout?: object;
  altura?: number;
};

const LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Segoe UI, system-ui, sans-serif', size: 12, color: '#26394d' },
  margin: { t: 30, r: 30, b: 100, l: 68, autoexpand: true },
  legend: { orientation: 'h', yanchor: 'top', y: -0.28, x: 0, xanchor: 'left' },
  xaxis: { gridcolor: '#e6ebf2', zerolinecolor: '#d5dbe3', automargin: true, title: { standoff: 14 } },
  yaxis: { gridcolor: '#e6ebf2', zerolinecolor: '#d5dbe3', automargin: true, title: { standoff: 12 } },
  hovermode: 'closest',
  separators: ',.',
  autosize: true,
};

function eixo(base: object, extra: object | undefined): object {
  if (!extra) return base;
  const acrescentado = extra as { title?: object };
  const origem = base as { title?: object };
  return {
    ...base,
    ...extra,
    title: { ...origem.title, ...acrescentado.title },
  };
}

function layoutFigura(extra: object | undefined, altura: number): object {
  const sobre = (extra ?? {}) as { xaxis?: object; yaxis?: object; margin?: object };
  return {
    ...LAYOUT,
    ...sobre,
    height: altura,
    xaxis: eixo(LAYOUT.xaxis, sobre.xaxis),
    yaxis: eixo(LAYOUT.yaxis, sobre.yaxis),
    margin: { ...LAYOUT.margin, ...sobre.margin },
  };
}

export function Grafico({
  titulo,
  figura,
  nota,
  identificador,
  embutido = false,
}: {
  titulo: string;
  figura: Figura | null;
  nota?: string;
  identificador: string;
  embutido?: boolean;
}) {
  const [ampliado, setAmpliado] = useState(false);
  const botaoAbrir = useRef<HTMLButtonElement>(null);
  const botaoFechar = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const tituloId = useId();
  const nome = titulo || 'Visualização dos resultados';

  useEffect(() => {
    if (!ampliado) return;
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    botaoFechar.current?.focus();
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') {
        evento.preventDefault();
        setAmpliado(false);
      }
      if (evento.key !== 'Tab') return;
      const elementos = Array.from(
        modalRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])') ?? [],
      ).filter((item) => item.getClientRects().length > 0);
      if (elementos.length === 0) return;
      const primeiro = elementos[0];
      const ultimo = elementos[elementos.length - 1];
      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
    };
    window.addEventListener('keydown', aoTeclar);
    return () => {
      window.removeEventListener('keydown', aoTeclar);
      document.body.style.overflow = overflowAnterior;
      botaoAbrir.current?.focus();
    };
  }, [ampliado]);

  function desenhar(altura: number) {
    return figura ? (
      <Plot
        data={figura.data}
        layout={layoutFigura(figura.layout, altura)}
        config={CONFIG}
        useResizeHandler
        style={{ width: '100%', height: altura }}
      />
    ) : <p className="indisponivel">Dados não disponíveis neste recorte.</p>;
  }

  const controles = figura ? (
    <div className="grafico-acoes">
      <button ref={botaoAbrir} className="botao-leve" type="button" onClick={() => setAmpliado(true)}
        aria-label={'Ampliar gráfico: ' + nome}>
        Ampliar gráfico ↗
      </button>
    </div>
  ) : null;

  const corpo = (
    <>
      <div className="grafico-canvas" role="group" aria-label={'Gráfico interativo: ' + nome}>
        {desenhar(figura?.altura ?? 360)}
      </div>
      {nota ? <p className="nota">{nota}</p> : null}
      <LeituraPedagogica identificador={identificador} />
    </>
  );

  const ampliacao = ampliado && figura ? (
    <div className="grafico-overlay" onMouseDown={(evento) => {
      if (evento.target === evento.currentTarget) setAmpliado(false);
    }}>
      <div className="grafico-modal" ref={modalRef} role="dialog" aria-modal="true" aria-labelledby={tituloId}>
        <div className="painel-cabecalho">
          <h2 id={tituloId}>{nome}</h2>
          <button type="button" className="botao-leve" ref={botaoFechar} onClick={() => setAmpliado(false)}>Fechar ✕</button>
        </div>
        <div className="grafico-canvas">{desenhar(Math.max(560, figura.altura ?? 360))}</div>
        {nota ? <p className="nota">{nota}</p> : null}
        <p className="nota">Passe o cursor sobre os dados para visualizar os valores. Use a barra de ferramentas do gráfico para ampliar, redefinir ou exportar a imagem.</p>
      </div>
    </div>
  ) : null;

  if (embutido) {
    return (
      <>
        <div className="grafico-embutido" data-visual={identificador}>{controles}{corpo}</div>
        {ampliacao}
      </>
    );
  }
  return (
    <>
      <section className="painel" data-visual={identificador}>
        <div className="painel-cabecalho">
          {titulo ? <h2>{titulo}</h2> : <span />}
          {controles}
        </div>
        {corpo}
      </section>
      {ampliacao}
    </>
  );
}

export const COR = '#176590';
export const CORES = [
  '#176590', '#c45a3d', '#16806d', '#8056a1', '#b28725',
  '#5469b2', '#b24272', '#416b76', '#a76b37', '#4c8752', '#7855a5',
];

export function barra(x: (string | number)[], y: (number | null)[], horizontal = false): Figura {
  return {
    data: [
      {
        type: 'bar',
        x: horizontal ? y : x,
        y: horizontal ? x : y,
        orientation: horizontal ? 'h' : 'v',
        marker: { color: COR },
        hovertemplate: horizontal ? '%{y}<br>%{x}<extra></extra>' : '%{x}<br>%{y}<extra></extra>',
      },
    ],
  };
}
