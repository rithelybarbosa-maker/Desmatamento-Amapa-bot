"""
config.py — Configurações centrais do bot de monitoramento de desmatamento
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Área de monitoramento: Estado do Amapá ──────────────────────────────────
# Bounding box: (lon_min, lat_min, lon_max, lat_max)
AMAPA_BBOX = {
    "lon_min": -54.0,
    "lat_min": -1.3,
    "lon_max": -49.7,
    "lat_max":  4.5,
}
AMAPA_BBOX_STR = (
    f"{AMAPA_BBOX['lon_min']},"
    f"{AMAPA_BBOX['lat_min']},"
    f"{AMAPA_BBOX['lon_max']},"
    f"{AMAPA_BBOX['lat_max']}"
)

# ─── Monitoramento ────────────────────────────────────────────────────────────
MONITORING_INTERVAL_MIN = int(os.getenv("MONITORING_INTERVAL", 30))
MONITORING_INTERVAL_SEC = MONITORING_INTERVAL_MIN * 60

# ─── Fuso horário ─────────────────────────────────────────────────────────────
TIMEZONE = os.getenv("TIMEZONE", "America/Belem")

# ─── Diretórios ───────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
DATA_DIR       = BASE_DIR / "data"
KML_DIR        = BASE_DIR / "kml"
MAPAS_DIR      = BASE_DIR / "mapas"
LOGS_DIR       = BASE_DIR / "logs"
DB_PATH        = DATA_DIR / "desmatamento.db"
MUNICIPIOS_GEO = DATA_DIR / "amapa_municipios.geojson"
UCS_TIS_GEO    = DATA_DIR / "amapa_areas_protegidas.geojson"

# Cria diretórios necessários
for _dir in [DATA_DIR, KML_DIR, MAPAS_DIR, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─── Logging ──────────────────────────────────────────────────────────────────
def setup_logging():
    from datetime import datetime

    log_file = LOGS_DIR / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Silencia logs verbosos de bibliotecas externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def validate_config() -> list[str]:
    """Retorna lista de erros de configuração (vazia se tudo OK)."""
    errors = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        errors.append("TELEGRAM_BOT_TOKEN não configurado no arquivo .env")
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID.startswith("-10012345"):
        errors.append("TELEGRAM_CHAT_ID não configurado no arquivo .env")
    return errors
