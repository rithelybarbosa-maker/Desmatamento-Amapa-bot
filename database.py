"""
database.py — Gerenciamento do banco de dados SQLite para o bot de desmatamento
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Union

from config import DB_PATH

logger = logging.getLogger(__name__)


# ─── Conexão ─────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # melhor performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Inicialização ────────────────────────────────────────────────────────────

def initialize_db() -> None:
    """Cria as tabelas se não existirem e popula as áreas protegidas padrão."""
    with get_connection() as conn:
        conn.executescript("""
            -- Tabela de alertas de desmatamento (DETER)
            CREATE TABLE IF NOT EXISTS alertas (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                gid_deter           TEXT UNIQUE,           -- ID original do DETER (pode ser texto como '9_hist')
                classe              TEXT    NOT NULL,      -- Ex: DESMATAMENTO_CR
                classe_label        TEXT    NOT NULL,      -- Ex: Desmatamento com Solo Exposto
                area_ha             REAL    NOT NULL,      -- Área em hectares
                data_deteccao       TEXT    NOT NULL,      -- ISO 8601 data da passagem/detecção
                municipio           TEXT,
                uf                  TEXT    DEFAULT 'AP',
                latitude_centro     REAL,                  -- Lat do centróide
                longitude_centro    REAL,                  -- Lon do centróide
                geometria_wkt       TEXT,                  -- Polígono no formato WKT
                satelite            TEXT,                  -- Satélite detector
                enviado             INTEGER NOT NULL DEFAULT 0,
                telegram_message_id INTEGER,
                criado_em           TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            -- Índices para buscas frequentes
            CREATE INDEX IF NOT EXISTS idx_alertas_data      ON alertas(data_deteccao);
            CREATE INDEX IF NOT EXISTS idx_alertas_enviado   ON alertas(enviado);
            CREATE INDEX IF NOT EXISTS idx_alertas_municipio ON alertas(municipio);
            CREATE INDEX IF NOT EXISTS idx_alertas_gid       ON alertas(gid_deter);

            -- Tabela de Áreas Protegidas (Unidades de Conservação e Terras Indígenas)
            CREATE TABLE IF NOT EXISTS areas_protegidas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT    NOT NULL,
                tipo      TEXT    NOT NULL,   -- 'UC' (Unidade de Conservação) ou 'TI' (Terra Indígena)
                categoria TEXT,               -- Ex: RESEX, FLONA, ESEC, TI
                latitude  REAL    NOT NULL,   -- Centróide
                longitude REAL    NOT NULL,
                ativo     INTEGER NOT NULL DEFAULT 1
            );
        """)
            
    logger.info("Banco de dados do desmatamento inicializado")
    _seed_areas_protegidas()


def _seed_areas_protegidas() -> None:
    """Popula a tabela de áreas protegidas do Amapá se estiver vazia."""
    
    # Unidades de Conservação (Federais e Estaduais)
    ucs = [
        # (nome, tipo, categoria, lat, lon)
        ("PARNA Montanhas do Tumucumaque", "UC", "PARNA", 2.25, -53.00),
        ("PARNA do Cabo Orange", "UC", "PARNA", 3.83, -51.16),
        ("ESEC do Jari", "UC", "ESEC", -0.75, -52.25),
        ("ESEC de Maracá-Jipioca", "UC", "ESEC", 2.05, -50.50),
        ("FLONA do Amapá", "UC", "FLONA", 1.00, -51.80),
        ("REBIO do Lago Piratuba", "UC", "REBIO", 1.75, -50.10),
        ("RESEX do Rio Cajari", "UC", "RESEX", -0.80, -51.80),
        ("RDS do Rio Iratapuru", "UC", "RDS", 0.60, -52.50),
        ("APA do Rio Curiaú", "UC", "APA", 0.13, -51.03),
        ("FLOE do Amapá", "UC", "FLOE", 0.80, -51.50),
    ]

    # Terras Indígenas
    tis = [
        # (nome, tipo, categoria, lat, lon)
        ("TI Wajãpi", "TI", "TI", 0.85, -52.30),
        ("TI Uaçá", "TI", "TI", 3.50, -51.50),
        ("TI Juminã", "TI", "TI", 3.30, -51.80),
        ("TI Galibi", "TI", "TI", 3.90, -51.70),
    ]

    todas = ucs + tis

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM areas_protegidas").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO areas_protegidas (nome, tipo, categoria, latitude, longitude) VALUES (?,?,?,?,?)",
                todas,
            )
            logger.info(f"Inseridas {len(todas)} áreas protegidas (UCs/TIs) no banco de dados")


# ─── Operações de Alertas ─────────────────────────────────────────────────────

def alerta_exists(gid_deter: Union[int, str]) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM alertas WHERE gid_deter = ?", (str(gid_deter),)).fetchone()
        return row is not None


def insert_alerta(
    gid_deter: Union[int, str],
    classe: str,
    classe_label: str,
    area_ha: float,
    data_deteccao: str,
    municipio: str,
    uf: str,
    latitude_centro: float,
    longitude_centro: float,
    geometria_wkt: str,
    satelite: str,
) -> Optional[int]:
    """
    Insere um novo alerta de desmatamento. Retorna o ID inserido ou None se duplicado.
    """
    if alerta_exists(gid_deter):
        return None

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO alertas
                   (gid_deter, classe, classe_label, area_ha, data_deteccao, municipio, uf,
                    latitude_centro, longitude_centro, geometria_wkt, satelite, enviado)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (gid_deter, classe, classe_label, area_ha, data_deteccao, municipio, uf,
                 latitude_centro, longitude_centro, geometria_wkt, satelite),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def mark_sent(alerta_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE alertas SET enviado = 1 WHERE id = ?", (alerta_id,))


def update_telegram_message_id(alerta_id: int, message_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE alertas SET telegram_message_id = ? WHERE id = ?", (message_id, alerta_id))


def get_unsent_alertas() -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas WHERE enviado = 0 ORDER BY data_deteccao ASC"
        ).fetchall()


def get_last_alertas(n: int = 10) -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas ORDER BY data_deteccao DESC LIMIT ?", (n,)
        ).fetchall()


def get_alertas_today() -> list:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas WHERE data_deteccao LIKE ? ORDER BY data_deteccao DESC",
            (f"{today}%",),
        ).fetchall()


def get_alertas_24h() -> list:
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas WHERE data_deteccao >= ? ORDER BY data_deteccao DESC",
            (since,),
        ).fetchall()


def get_alertas_by_municipio(municipio: str) -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas WHERE LOWER(municipio) LIKE LOWER(?) ORDER BY data_deteccao DESC LIMIT 20",
            (f"%{municipio}%",),
        ).fetchall()


def get_alertas_by_tipo(classe_label: str) -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM alertas WHERE LOWER(classe_label) LIKE LOWER(?) ORDER BY data_deteccao DESC LIMIT 20",
            (f"%{classe_label}%",),
        ).fetchall()


# ─── Operações de Áreas Protegidas ────────────────────────────────────────────

def get_all_areas_protegidas() -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM areas_protegidas WHERE ativo = 1 ORDER BY tipo, nome"
        ).fetchall()
