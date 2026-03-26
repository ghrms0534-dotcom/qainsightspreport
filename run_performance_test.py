
from pathlib import Path
import runpy
import sys

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
runpy.run_path(str(BASE_DIR / "scripts" / "run_pipeline.py"), run_name="__main__")
