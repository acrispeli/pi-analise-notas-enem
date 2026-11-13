import { Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';

const ROTULOS: Record<string, string> = {
  definition: 'Definição',
  calculation: 'Cálculo',
  population: 'População',
  catalog_population: 'População no catálogo',
  method: 'Método',
  geographic_dimension: 'Dimensão geográfica',
  geography: 'Geografia',
  source_file: 'Arquivo-fonte',
  aggregation: 'Agregação',
  limitations: 'Limites',
  historical_note: 'Histórico',
  precision: 'Precisão',
  sampling: 'Amostragem',
  primary_suppression: 'Supressão',
  suppression_review: 'Revisão da supressão',
  source_pca: 'PCA de origem',
  source_loadings: 'Loadings de origem',
  notes: 'Notas',
  questionnaire_version: 'Versão do questionário',
  privacy_minimum_count: 'Limiar de privacidade',
  minimum_published_cell: 'Menor célula publicada',
  source: 'Fonte',
  privacy_note: 'Privacidade',
};

export default function Metodologia() {
  const { ano } = useFiltros();
  const edicao = ano === 'todos' ? '2024' : ano;
  const pedido = useDados<Record<string, unknown>>(`/data/${edicao}/methodology.json`);
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;

  const blocos = indicadores(pedido.dados);
  return (
    <div>
      <h1>Método</h1>
      {ano === 'todos' ? (
        <p className="nota">O texto é o de 2024. Cada ano tem o próprio texto. Escolha o ano para ler o daquela edição.</p>
      ) : (
        <p className="nota">Como os números de {edicao} foram calculados.</p>
      )}
      {blocos.map((bloco) => (
        <article key={bloco.id} className="metodo">
          <h2>{bloco.id}</h2>
          {bloco.campos.length ? (
            <dl>
              {bloco.campos.map(([rotulo, texto]) => (
                <div key={rotulo}>
                  <dt>{rotulo}</dt>
                  <dd>{texto}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="indisponivel">não disponível</p>
          )}
        </article>
      ))}
    </div>
  );
}

function indicadores(doc: Record<string, unknown>): { id: string; campos: [string, string][] }[] {
  const saida = [{ id: 'IND-001', campos: campos(doc) }];
  const chaves = Object.keys(doc)
    .filter((chave) => /^ind\d+$/.test(chave))
    .sort((a, b) => Number(a.slice(3)) - Number(b.slice(3)));
  for (const chave of chaves) {
    const bloco = doc[chave];
    if (!bloco || typeof bloco !== 'object') continue;
    saida.push({ id: `IND-${chave.slice(3)}`, campos: campos(bloco as Record<string, unknown>) });
  }
  return saida;
}

function campos(bloco: Record<string, unknown>): [string, string][] {
  const lista: [string, string][] = [];
  for (const [chave, valor] of Object.entries(bloco)) {
    if (chave === 'status' || chave === 'indicator_id' || /^ind\d+$/.test(chave)) continue;
    if (typeof valor !== 'string' && typeof valor !== 'number') continue;
    const rotulo = ROTULOS[chave];
    if (!rotulo) continue;
    lista.push([rotulo, String(valor)]);
  }
  return lista;
}
