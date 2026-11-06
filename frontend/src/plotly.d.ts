declare module 'plotly.js-dist-min' {
  const Plotly: object;
  export default Plotly;
}

declare module 'react-plotly.js/factory' {
  import type { ComponentType } from 'react';

  type Propriedades = {
    data: object[];
    layout?: object;
    config?: object;
    style?: object;
    useResizeHandler?: boolean;
  };

  export default function createPlotlyComponent(plotly: object): ComponentType<Propriedades>;
}
