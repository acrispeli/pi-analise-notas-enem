from pathlib import Path
import runpy
import sys

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

runpy.run_path(
    str(RAIZ / "visualizador.py"),
    run_name="__main__"
)