"""Smoke test do corpo de cada gráfico usando substituto simples de Streamlit.
Testa dados reais do dashboard 2024 sem levantar servidor web."""
import ast
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from painel_dados_enem import ANOS,UFS,NOMES_UF,localizar_dashboards,carregar_json,obter_recorte,serie_anual,agrupar_frequencias_niveis,classes_redacao,quantidade_segura,obter_hexbin_ind016,validar_hexbin_ind016

class Fake:
 def __init__(self): self.plot_count=0;self.message_count=0
 def __getattr__(self,k):
  if k=='columns':return lambda n: [self for _ in range(n)]
  if k=='cache_data':return lambda *a,**b: (lambda f:f)
  if k in ('expander','sidebar'): return lambda *a,**b: self
  if k=='radio':return lambda *a,**b: 'Spearman'
  if k=='plotly_chart':return self.chart
  return lambda *a,**b:None
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def chart(self,f,*a,**kw):
  assert len(f.data)>0
  self.plot_count+=1

source=Path(__file__).with_name('visualizador.py').read_text(encoding='utf8')
module=ast.parse(source)
funcs=[x for x in module.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
loaded=compile(ast.Module(body=funcs,type_ignores=[]),'<funcoes_visuais>','exec')
st=Fake()
ns=dict(st=st,pd=pd,px=px,go=go,Path=Path,math=__import__("math"),sample_colorscale=sample_colorscale,obter_hexbin_ind016=obter_hexbin_ind016,validar_hexbin_ind016=validar_hexbin_ind016,COR='#2563A6',COR_SEC='#7D9CB8',ESCALA=['#DCE8F1','#A8C7DA','#588DAF','#2563A6','#193E64'],
         ANOS=ANOS,UFS=UFS,NOMES_UF=NOMES_UF,obter_recorte=obter_recorte,serie_anual=serie_anual,
         agrupar_frequencias_niveis=agrupar_frequencias_niveis,classes_redacao=classes_redacao,quantidade_segura=quantidade_segura,
         COMP={'C1':'Domínio da escrita formal','C2':'Compreensão','C3':'Argumentação','C4':'Coesão','C5':'Intervenção'})
exec(loaded,ns)
doc=carregar_json(Path(__file__).with_name('dashboard_enem_2024.json'))
ns['referencia']=doc
ns['arquivos']={2024:Path(__file__).with_name('dashboard_enem_2024.json')}
ns['ler_cached']=carregar_json
functions=['boas_vindas','notas','competencias','relacoes','perfis','evolucao','metodologia']
for ano,uf in [(None,'BR'),(2024,'BR'),(None,'SP'),(2024,'SP')]:
 ns['ano']=ano;ns['uf']=uf;ns['anual']=doc if ano==2024 else None
 for fn in functions:
  try:ns[fn]()
  except Exception as ex:
   import traceback
   print('ERRO',fn,ano,uf,type(ex).__name__,str(ex))
   traceback.print_exc()
   raise
 print('OK',ano,uf)
print('Gráficos gerados nos testes:',st.plot_count)
