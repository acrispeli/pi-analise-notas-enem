import { Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';

type Ml = { status?: string; reason?: string };

export default function PadroesMl() {
  const { ano } = useFiltros();
  const edicao = ano === 'todos' ? '2024' : ano;
  const pedido = useDados<Ml>(`/data/${edicao}/ml.json`);
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;
  const motivo = pedido.dados.reason || 'indicadores_ainda_nao_implementados';
  return (
    <div data-visual="ml">
      <h1>Padrões por ML</h1>
      <p className="construcao">em construção</p>
      <p className="nota">Motivo publicado: {motivo}. Os indicadores 053 a 063 não foram criados.</p>
    </div>
  );
}
