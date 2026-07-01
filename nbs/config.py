from datetime import timezone, timedelta
from pathlib import Path
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LEDGER_PATH = DATA_DIR / "published.csv"
RUNS_DIR = ROOT / "runs"
def run_dir(date: str) -> Path: return RUNS_DIR / date
