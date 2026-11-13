import type { ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { rotuloUf, useFiltros } from './filtros.tsx';

const ROTAS = [
  ['/visao-geral', 'Visão geral'],
  ['/competencias', 'Competências'],
  ['/avaliadores', 'Corretores'],
  ['/alto-desempenho', 'Notas altas'],
  ['/socioeconomico', 'Questionário'],
  ['/evolucao', 'Evolução'],
  ['/metodologia', 'Método'],
  ['/padroes-ml', 'Perfis'],
] as const;

export function Layout() {
  const { ano, uf, definirAno, definirUf, anos, ufs } = useFiltros();
  const { search } = useLocation();

  return (
    <div className="app">
      <aside className="menu">
        <p className="marca">Redação no ENEM</p>
        <p className="menu-nota">2019 a 2025</p>
        <nav>
          {ROTAS.map(([caminho, rotulo]) => (
            <NavLink key={caminho} to={{ pathname: caminho, search }} className={({ isActive }) => (isActive ? 'ativo' : '')}>
              {rotulo}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="miolo">
        <header className="topo">
          <label>
            Ano
            <select value={ano} onChange={(evento) => definirAno(evento.target.value)} data-filtro="ano">
              <option value="todos">Todos os anos</option>
              {anos.map((item) => (
                <option key={item} value={String(item)}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            UF da prova
            <select value={uf} onChange={(evento) => definirUf(evento.target.value)} data-filtro="uf">
              {ufs.map((codigo) => (
                <option key={codigo} value={codigo}>
                  {rotuloUf(codigo)}
                </option>
              ))}
            </select>
          </label>
          <p className="recorte">
            {ano === 'todos' ? '2019–2025' : ano} · {rotuloUf(uf)}
          </p>
        </header>
        <p className="limite">A UF é onde a prova foi feita. Cada linha é uma participação, não uma pessoa.</p>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function Estado({ carregando, erro }: { carregando: boolean; erro: boolean }) {
  if (carregando) return <p className="estado">Carregando…</p>;
  if (erro) return <p className="estado erro">Não foi possível carregar os dados deste recorte.</p>;
  return null;
}

export function Cartao({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe?: string }) {
  return (
    <article className="cartao">
      <p>{rotulo}</p>
      <strong>{valor}</strong>
      {detalhe ? <span>{detalhe}</span> : null}
    </article>
  );
}

export function Aviso({ children }: { children: ReactNode }) {
  return <p className="aviso">{children}</p>;
}
