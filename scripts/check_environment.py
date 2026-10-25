#!/usr/bin/env python3
import importlib.util, shutil, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
venv_python = root / ".venv" / "bin" / "python"
python = str(venv_python) if venv_python.exists() else sys.executable
print(f"Python: {subprocess.check_output([python, '-c', 'import sys; print(sys.version.split()[0])'], text=True).strip()} ({python})")
modules = [("FastAPI", "fastapi"), ("SQLAlchemy", "sqlalchemy"), ("Pillow", "PIL"), ("ReportLab", "reportlab")]
probe = "import importlib.util,sys; print('\\n'.join(f'{name}: {\"available\" if importlib.util.find_spec(module) else \"missing\"}' for name,module in [('FastAPI','fastapi'),('SQLAlchemy','sqlalchemy'),('Pillow','PIL'),('ReportLab','reportlab')]))"
print(subprocess.check_output([python, "-c", probe], text=True).strip())
for name in ["node", "npm", "ollama", "ffmpeg"]:
    print(f"{name}: {shutil.which(name) or 'not found'}")
