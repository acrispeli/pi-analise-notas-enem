import { lazy, Suspense } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { ProvedorFiltros } from './filtros.tsx';
import { Layout } from './layout.tsx';

const VisaoGeral = lazy(() => import('./paginas/VisaoGeral.tsx'));
const Competencias = lazy(() => import('./paginas/Competencias.tsx'));
const Avaliadores = lazy(() => import('./paginas/Avaliadores.tsx'));
const AltoDesempenho = lazy(() => import('./paginas/AltoDesempenho.tsx'));
const Socioeconomico = lazy(() => import('./paginas/Socioeconomico.tsx'));
const Evolucao = lazy(() => import('./paginas/Evolucao.tsx'));
const Metodologia = lazy(() => import('./paginas/Metodologia.tsx'));
const PadroesMl = lazy(() => import('./paginas/PadroesMl.tsx'));

export default function App() {
  return (
    <BrowserRouter>
      <ProvedorFiltros>
        <Suspense fallback={<p className="estado">Carregando…</p>}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/visao-geral" replace />} />
              <Route path="/visao-geral" element={<VisaoGeral />} />
              <Route path="/competencias" element={<Competencias />} />
              <Route path="/avaliadores" element={<Avaliadores />} />
              <Route path="/alto-desempenho" element={<AltoDesempenho />} />
              <Route path="/socioeconomico" element={<Socioeconomico />} />
              <Route path="/evolucao" element={<Evolucao />} />
              <Route path="/metodologia" element={<Metodologia />} />
              <Route path="/padroes-ml" element={<PadroesMl />} />
              <Route path="*" element={
                <section className="painel pagina-nao-encontrada">
                  <h1>Página não encontrada</h1>
                  <p>O endereço informado não corresponde a uma seção do painel.</p>
                  <Link to="/visao-geral">Voltar à Visão geral</Link>
                </section>
              } />
            </Route>
          </Routes>
        </Suspense>
      </ProvedorFiltros>
    </BrowserRouter>
  );
}
