"""
main.py — Entry point do Bot de Monitoramento de Desmatamento — Amapá
"""

import asyncio
import logging
import os
import sys
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from telegram.ext import Application
from telegram.request import HTTPXRequest

import database as db
from config import (
    TELEGRAM_BOT_TOKEN,
    MONITORING_INTERVAL_SEC,
    setup_logging,
    validate_config,
)
import deter_client
from municipalities import get_municipio, reload_municipios
from telegram_bot import register_handlers, send_deforestation_alert

logger = logging.getLogger(__name__)


# ─── Job de monitoramento ─────────────────────────────────────────────────────

async def monitoring_job(context) -> None:
    """
    Job principal executado a cada MONITORING_INTERVAL_SEC segundos.
    Busca novos alertas no DETER, salva no banco e envia para o Telegram.
    """
    logger.info("⏳ Iniciando verificação de novos alertas de desmatamento...")
    app = context.application

    try:
        # 1. Busca dados do DETER (pega alertas dos últimos 7 dias para cobrir delays)
        alertas = deter_client.fetch_deter_alerts(day_range=7)

        if not alertas:
            logger.info("Nenhum alerta retornado nesta verificação")
            return

        novos = 0
        for a in alertas:
            # 2. Determina o município
            mun = get_municipio(a["latitude_centro"], a["longitude_centro"])
            a["municipio"] = mun

            # 3. Insere no banco (retorna o ID inserido ou None se já existir)
            alerta_id = db.insert_alerta(
                gid_deter=a["gid_deter"],
                classe=a["classe"],
                classe_label=a["classe_label"],
                area_ha=a["area_ha"],
                data_deteccao=a["data_deteccao"],
                municipio=a["municipio"],
                uf=a["uf"],
                latitude_centro=a["latitude_centro"],
                longitude_centro=a["longitude_centro"],
                geometria_wkt=a["geometria_wkt"],
                satelite=a["satelite"]
            )
            
            if alerta_id is not None:
                novos += 1
                logger.info(
                    f"Novo alerta DETER GID={a['gid_deter']} cadastrado: {mun} | {a['classe_label']} | Area={a['area_ha']:.1f} ha"
                )

        if novos > 0:
            logger.info(f"✅ {novos} novo(s) alerta(s) de desmatamento inserido(s)")
        else:
            logger.info("✅ Nenhum alerta novo (todos já registrados)")

        # 4. Envia alertas pendentes no Telegram
        pendentes = db.get_unsent_alertas()
        if pendentes:
            logger.info(f"📤 Enviando {len(pendentes)} alerta(s) pendente(s)...")
            for alerta in pendentes:
                ok = await send_deforestation_alert(app, dict(alerta))
                if ok:
                    db.mark_sent(alerta["id"])
                    await asyncio.sleep(2.0)  # Evita flood do Telegram
                else:
                    logger.warning(f"Falha ao enviar alerta GID={alerta['gid_deter']}, tentará novamente")

    except Exception as e:
        logger.error(f"Erro no job de monitoramento: {e}", exc_info=True)


# ─── Inicialização ────────────────────────────────────────────────────────────

def print_banner() -> None:
    banner = """
╔══════════════════════════════════════════════════════╗
║  🌳  MONITOR DE DESMATAMENTO — ESTADO DO AMAPÁ   🌳  ║
║                                                      ║
║  Fonte dos Dados: INPE DETER (WFS GeoServer)         ║
║  Classes: Desmatamento, Degradação, Mineração        ║
║                                                      ║
║  Desenvolvido para monitoramento e fiscalização      ║
╚══════════════════════════════════════════════════════╝
"""
    print(banner)


def check_requirements() -> bool:
    required = [
        "telegram", "requests",
        "simplekml", "folium", "dotenv", "pytz",
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        logger.error(f"Bibliotecas não instaladas: {', '.join(missing)}")
        return False
    return True


async def post_init(application: Application) -> None:
    """Envia mensagem de startup do bot no canal de alertas."""
    try:
        from config import TELEGRAM_CHAT_ID
        if TELEGRAM_CHAT_ID:
            hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
            msg = (
                f"✅ *Bot de Monitoramento de Desmatamento iniciado*\n"
                f"🕐 {hoje}\n"
                f"⏱️ Verificação a cada {MONITORING_INTERVAL_SEC // 60} minutos\n"
                f"🛰️ Fonte: INPE DETER (GeoServer WFS)\n\n"
                f"_Use /status para ver o estado do sistema_"
            )
            await application.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.warning(f"Não foi possível enviar mensagem de startup: {e}")


# ─── Servidor de Health Check (Render) ────────────────────────────────────────

class HealthCheckHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Bot de Monitoramento de Desmatamento do Amapá está ativo! 🚀".encode("utf-8"))
        elif path == "/logs":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            try:
                from config import LOGS_DIR
                import glob
                log_files = glob.glob(str(LOGS_DIR / "bot_*.log"))
                if log_files:
                    latest_log = max(log_files, key=os.path.getmtime)
                    with open(latest_log, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    self.wfile.write(f"=== ÚLTIMOS LOGS ({os.path.basename(latest_log)}) ===\n\n".encode("utf-8"))
                    self.wfile.write("".join(lines[-100:]).encode("utf-8"))
                else:
                    self.wfile.write("Nenhum arquivo de log encontrado.".encode("utf-8"))
            except Exception as e:
                self.wfile.write(f"Erro ao ler logs: {e}".encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args) -> None:
        # Silencia logs HTTP para manter o console limpo
        pass


def run_health_server(port: int) -> None:
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Servidor de Health Check ativo na porta {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Erro no servidor de Health Check: {e}", exc_info=True)


def start_health_check_server() -> None:
    port = int(os.getenv("PORT", "8080"))
    thread = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    thread.start()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()
    print_banner()

    logger.info("Iniciando monitoramento de desmatamento...")
    start_health_check_server()

    if not check_requirements():
        sys.exit(1)

    erros = validate_config()
    if erros:
        logger.warning("⚠️ Configuração incompleta:")
        for e in erros:
            logger.warning(f"   • {e}")
        logger.warning("Configure o arquivo .env e reinicie.")

    # Inicializa banco de dados
    db.initialize_db()

    # Pré-carrega municípios
    logger.info("Carregando limites dos municípios...")
    reload_municipios()

    # Testa conexão com o DETER GeoServer
    ok, msg = deter_client.check_api_connection()
    if ok:
        logger.info(f"✅ {msg}")
    else:
        logger.warning(f"⚠️ {msg}")

    if not TELEGRAM_BOT_TOKEN or erros:
        logger.error("Token do Telegram ausente. Configure o arquivo .env.")
        sys.exit(1)

    req_config = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0, write_timeout=60.0)

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(req_config)
        .post_init(post_init)
        .build()
    )

    register_handlers(app)

    # Agenda o job de monitoramento
    app.job_queue.run_repeating(
        monitoring_job,
        interval=MONITORING_INTERVAL_SEC,
        first=15,
        name="deforestation_monitoring_job",
    )

    logger.info(f"✅ Bot iniciado! Monitoramento a cada {MONITORING_INTERVAL_SEC // 60} minutos.")
    app.run_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
