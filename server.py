from pathlib import Path
import runpy

APP = Path(__file__).resolve().parent / 'V123' / 'server.py'
runpy.run_path(str(APP), run_name='__main__')
