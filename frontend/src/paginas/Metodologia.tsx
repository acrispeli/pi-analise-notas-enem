import { useState } from 'react';
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
  const [busca, setBusca] = useState('');
  const { ano } = useFiltros();
  const edicao = ano === 'todos' ? '2024' : ano;
  const pedido = useDados<Record<string, unknown>>(`/data/${edicao}/methodology.json`);
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;

  const todos = indicadores(pedido.dados);
  const termo = busca.trim().toLocaleLowerCase('pt-BR');
  // Uma consulta por código exato deve priorizar o próprio indicador,
  // mesmo que seu código seja citado na descrição de outros indicadores.
  const exatos = termo
    ? todos.filter((bloco) => bloco.id.toLocaleLowerCase('pt-BR') === termo)
    : [];
  const blocos = !termo
    ? todos
    : exatos.length
      ? exatos
      : todos.filter((bloco) =>
          bloco.id.toLocaleLowerCase('pt-BR').includes(termo) ||
          bloco.campos.some(([rotulo, texto]) => (rotulo + ' ' + texto).toLocaleLowerCase('pt-BR').includes(termo))
        );
  return (
    <div>
      <h1>Método</h1>
      {ano === 'todos' ? (
        <p className="nota">O texto é o de 2024. Cada ano tem o próprio texto. Escolha o ano para ler o daquela edição.</p>
      ) : (
        <p className="nota">Como os números de {edicao} foram calculados.</p>
      )}
      <p className="nota">
        Indicadores preliminares (draft) são apresentados para fins acadêmicos. Contagens agregadas pequenas podem ser exibidas;
        médias e outras métricas com menos de cinco observações ficam indisponíveis quando o denominador é conhecido.
        A ausência de um valor não deve ser interpretada como zero.
      </p>
      <label className="busca-indicador" htmlFor="busca-metodo">
        Buscar por indicador, definição ou assunto
        <input
          id="busca-metodo"
          type="search"
          placeholder="Ex.: IND-020, competências, amostragem…"
          value={busca}
          onChange={(evento) => setBusca(evento.target.value)}
        />
      </label>
      <p className="nota" aria-live="polite">
        {blocos.length} de {todos.length} indicadores encontrados. Selecione um indicador para consultar os detalhes.
      </p>
      {blocos.length === 0 ? <p className="indisponivel">Nenhum indicador corresponde à pesquisa.</p> : null}
      {blocos.map((bloco) => (
        <details key={bloco.id + (termo ? '-pesquisa' : '')} className="metodo" open={termo ? true : undefined}>
          <summary>{bloco.id} · Definição e metodologia</summary>
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
            <p className="indisponivel">Informação metodológica não disponível.</p>
          )}
        </details>
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
