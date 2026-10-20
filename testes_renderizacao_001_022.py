"""Smoke de gráficos reais, sem iniciar o Streamlit. Executar após fixture existir."""
import ast, math
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from painel_dados_enem import *

class MockStreamlit:
    def __init__(self):self.plots=0;self.messages=0
    def __getattr__(self,k):
        if k=='columns':return lambda n:[self for _ in range(n)]
        if k=='tabs':return lambda names:[self for _ in names]
        if k=='cache_data':return lambda *args,**kwargs:(lambda f:f)
        if k in ('expander','sidebar'):return lambda *a,**kw:self
        if k=='radio':return lambda *args,**kwargs:'Spearman'
        if k=='plotly_chart':return self.plotly_chart
        return lambda *a,**kw:None
    def plotly_chart(self, fig,*a,**kw):
        assert fig.data and fig.layout,('gráfico vazio',self.plots)
        self.plots+=1
        # Plotly aceita e serializa boxplots agregados sem observações brutas.
        if any(tr.type=='box' for tr in fig.data):
            assert all(len(tr.q1)==1 and len(tr.median)==1 and len(tr.q3)==1 for tr in fig.data)
            assert not any(tr.boxpoints for tr in fig.data)
    def __enter__(self):return self
    def __exit__(self,*a):return False

path=Path(__file__).with_name('visualizador.py')
parsed=ast.parse(path.read_text(encoding='utf8'))
funs=[x for x in parsed.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
module=compile(ast.Module(body=funs,type_ignores=[]),str(path),'exec')
st=MockStreamlit()
namespace=dict(st=st,pd=pd,px=px,go=go,math=math,Path=Path,sample_colorscale=sample_colorscale,
         COR='#2563A6',COR_SEC='#7D9CB8',ESCALA=['#DCE8F1','#A8C7DA','#588DAF','#2563A6','#193E64'],
         ANOS=ANOS,UFS=UFS,NOMES_UF=NOMES_UF,obter_recorte=obter_recorte,serie_anual=serie_anual,
         validar_avaliadores=validar_avaliadores,
         agrupar_frequencias_niveis=agrupar_frequencias_niveis,classes_redacao=classes_redacao,
         quantidade_segura=quantidade_segura,obter_hexbin_ind016=obter_hexbin_ind016,
         validar_hexbin_ind016=validar_hexbin_ind016,
         COMP={'C1':'Escrita','C2':'Proposta','C3':'Argumentação','C4':'Coesão','C5':'Intervenção'})
exec(module,namespace)
fixture=Path(__file__).with_name('dashboard_enem_2024.json')
if not fixture.exists():
    fixture=Path(__file__).parent/'outputs'/'json'/'dashboard_enem_2024.json'
ref=carregar_json(fixture)
namespace.update(referencia=ref,arquivos={2024:fixture},ler_cached=carregar_json)
for ano,uf in [(None,'BR'),(2024,'BR'),(None,'SP'),(2024,'SP')]:
    namespace.update(ano=ano,uf=uf,anual=ref if ano==2024 else None)
    for name in ('boas_vindas','notas','competencias','relacoes','perfis','evolucao','avaliadores','metodologia'):
        namespace[name]()
    print('OK',ano,uf)
print('Gráficos renderizados (teste simulado):',st.plots)
