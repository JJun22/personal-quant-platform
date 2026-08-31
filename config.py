"""
全域設定：路徑、預設參數。
之後要換 Postgres / 真實交易所資料，只需要改這裡跟對應的 loader/repository 實作。
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "storage" / "data"          # parquet market data
REGISTRY_DB_PATH = PROJECT_ROOT / "storage" / "registry.sqlite3"
REPORTS_DIR = PROJECT_ROOT / "storage" / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# V0 只鎖定這個 symbol / base timeframe，之後擴充改這裡
DEFAULT_SYMBOL = "BTC/USDT"
BASE_TIMEFRAME = "1m"

# 成本模型預設值（Phase 3 cost stress 會用倍數去乘這些）
DEFAULT_COMMISSION_BPS = 5.0   # 每邊 0.05%
DEFAULT_SLIPPAGE_BPS = 2.0     # 每邊 0.02%

RANDOM_SEED = 42
