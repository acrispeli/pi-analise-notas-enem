import { useEffect, useRef, useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { rotuloUf, useFiltros } from './filtros.tsx';

const ROTAS = [
  { caminho: '/visao-geral', rotulo: 'Visão geral', numero: '01', descricao: 'Panorama das notas, situações das redações e diferenças entre as UFs de realização da prova.' },
  { caminho: '/competencias', rotulo: 'Competências', numero: '02', descricao: 'As cinco competências avaliadas na redação e os padrões exploratórios identificados nas notas.' },
  { caminho: '/avaliadores', rotulo: 'Corretores', numero: '03', descricao: 'Concordância, diferenças de avaliação e participação de corretores adicionais.' },
  { caminho: '/alto-desempenho', rotulo: 'Notas altas', numero: '04', descricao: 'Como se distribuem as redações de alto desempenho e em quais competências surgem descontos.' },
  { caminho: '/socioeconomico', rotulo: 'Questionário', numero: '05', descricao: 'Respostas declaradas no questionário e associações descritivas com o desempenho.' },
  { caminho: '/evolucao', rotulo: 'Evolução', numero: '06', descricao: 'Comparações das edições de 2019 a 2025 e tendências observadas nos indicadores.' },
  { caminho: '/metodologia', rotulo: 'Método', numero: '07', descricao: 'Definições, populações, cálculos e limites dos indicadores publicados.' },
  { caminho: '/padroes-ml', rotulo: 'Perfis', numero: '08', descricao: 'Agrupamentos exploratórios e técnicas estatísticas aplicadas aos dados de redação.' },
] as const;

export function Layout() {
  const { ano, uf, definirAno, definirUf, anos, ufs, statusDados } = useFiltros();
  const { pathname, search } = useLocation();
  const [menuAberto, setMenuAberto] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const conteudoRef = useRef<HTMLElement>(null);
  const atual = ROTAS.find((rota) => rota.caminho === pathname) ?? ROTAS[0];

  useEffect(() => {
    setMenuAberto(false);
    setCopiado(false);
    document.title = atual.rotulo + ' | Redação no ENEM · UNIVESP';
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [pathname, atual.rotulo]);

  async function copiarLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <div className="app">
      <a href="#conteudo" className="atalho-conteudo">Ir para o conteúdo principal</a>
      <button
        type="button"
        className="menu-mobile"
        aria-controls="menu-painel"
        aria-expanded={menuAberto}
        onClick={() => setMenuAberto((aberto) => !aberto)}
      >
        {menuAberto ? 'Fechar menu ×' : '☰ Abrir menu · Redação no ENEM'}
      </button>

      <aside id="menu-painel" className={'menu' + (menuAberto ? ' aberto' : '')}>
        <div className="marca-bloco">
          <span className="marca-etiqueta">UNIVESP · PROJETO INTEGRADOR IV</span>
          <p className="marca">Redação <span>no ENEM</span></p>
          <p className="menu-nota">Painel acadêmico · 2019 a 2025</p>
        </div>
        <p className="menu-titulo">Explorar os resultados</p>
        <nav aria-label="Seções do painel">
          {ROTAS.map((rota) => (
            <NavLink
              key={rota.caminho}
              to={{ pathname: rota.caminho, search }}
              className={({ isActive }) => 'menu-link' + (isActive ? ' ativo' : '')}
              onClick={() => setMenuAberto(false)}
            >
              <span className="menu-indice" aria-hidden="true">{rota.numero}</span>
              <span>{rota.rotulo}</span>
            </NavLink>
          ))}
        </nav>
        <p className="menu-rodape">
          Análise descritiva e exploratória para fins educacionais. Não é uma publicação oficial do Inep.
        </p>
      </aside>

      <div className="miolo">
        <header className="topo">
          <div className="topo-apresentacao">
            <p className="topo-eyebrow">Painel interativo · ENEM 2019–2025</p>
            <p className="topo-titulo">Explore os resultados das redações</p>
            <p className="topo-subtitulo">Notas, competências, avaliações e contexto socioeconômico em uma leitura acessível.</p>
          </div>
          <div className="filtros" role="group" aria-label="Filtros do painel">
            <label htmlFor="filtro-ano">
              Ano da edição
              <select id="filtro-ano" value={ano} onChange={(evento) => definirAno(evento.target.value)} data-filtro="ano">
                <option value="todos">Todos os anos</option>
                {anos.map((item) => <option key={item} value={String(item)}>{item}</option>)}
              </select>
            </label>
            <label htmlFor="filtro-uf">
              UF de realização da prova
              <select id="filtro-uf" value={uf} onChange={(evento) => definirUf(evento.target.value)} data-filtro="uf">
                {ufs.map((codigo) => (
                  <option key={codigo} value={codigo}>{rotuloUf(codigo)}</option>
                ))}
              </select>
            </label>
          </div>
        </header>

        <div className="contexto">
          <div>
            <p className="contexto-legenda">Recorte selecionado</p>
            <div className="contexto-valor" aria-live="polite">
              {ano === 'todos' ? '2019–2025' : ano} · {rotuloUf(uf)}
              <small>A UF indica onde a prova foi feita; cada linha corresponde a uma participação, não necessariamente a uma pessoa distinta.</small>
            </div>
          </div>
          <div className="contexto-acoes">
            {statusDados === 'draft' ? <span className="selo-status">Resultados preliminares</span> : null}
            <button className="botao-leve" type="button" onClick={copiarLink} aria-live="polite">
              {copiado ? '✓ Link copiado' : 'Copiar link deste recorte'}
            </button>
          </div>
        </div>

        <div className="pagina-orientacao">
          <span>Seção {atual.numero} de 08</span>
          <p>{atual.descricao}</p>
        </div>

        <main id="conteudo" ref={conteudoRef} tabIndex={-1}>
          <Outlet />
        </main>

        <footer className="rodape-site">
          Projeto Integrador IV — UNIVESP · Painel acadêmico e exploratório.
          Resultados descritivos não demonstram relações de causa e efeito.
        </footer>
      </div>
    </div>
  );
}

export function Estado({ carregando, erro }: { carregando: boolean; erro: boolean }) {
  if (carregando) return <p className="estado" role="status">Carregando os dados do recorte…</p>;
  if (erro) return <p className="estado erro" role="alert">Não foi possível carregar os dados deste recorte. Verifique o ano e a UF selecionados e tente novamente.</p>;
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
  return <p className="aviso" role="note">{children}</p>;
}
