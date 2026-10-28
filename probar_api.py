from pathlib import Path
from runpy import run_path


if __name__ == "__main__":
    script = Path(__file__).parent / "generated_project" / "probar_api.py"
    run_path(script, run_name="__main__")
