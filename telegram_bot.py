"""
telegram_bot.py — Handlers de comandos e envio de alertas via Telegram Bot API
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import database as db
import kml_generator as kml_gen
import map_generator as map_gen
from config import TELEGRAM_CHAT_ID
from protected_areas import get_nearby_protected_areas

logger = logging.getLogger(__name__)


# ─── Formatação ───────────────────────────────────────────────────────────────

def _get_local_time_info(datahora_str: str) -> tuple[str, str, int]:
    """Retorna o horário local formatado (HH:MM), a descrição do fuso e a diferença de tempo."""
    import pytz
    from config import TIMEZONE
    try:
        dt_utc = datetime.fromisoformat(datahora_str)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
            
        tz_local = pytz.timezone(TIMEZONE)
        dt_local = dt_utc.astimezone(tz_local)
        
        dt_now = datetime.now(tz_local)
        diff = dt_now - dt_local
        elapsed_minutes = max(0, int(diff.total_seconds() // 60))
        
        utc_offset = dt_local.utcoffset()
        offset_hours = int(utc_offset.total_seconds() // 3600) if utc_offset else 0
        offset_str = f"UTC{offset_hours:+d}"
        
        fuso_name = "Brasília" if "Sao_Paulo" in TIMEZONE or "Belem" in TIMEZONE else tz_local.zone.split('/')[-1]
        fuso_label = f"{offset_str} ({fuso_name})"
        
        return dt_local.strftime("%H:%M"), fuso_label, elapsed_minutes
    except Exception:
        return datahora_str[11:16], "UTC-3 (Brasília)", 0


def _format_date(datahora_str: str) -> str:
    try:
        dt = datetime.fromisoformat(datahora_str)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return datahora_str[:10]


def build_alert_message(alerta: dict) -> str:
    """Monta a mensagem do alerta formatada em Markdown."""
    a = dict(alerta) if hasattr(alerta, "keys") else alerta

    gid       = a.get("gid_deter")
    classe    = a.get("classe_label", "Alerta")
    area      = a.get("area_ha", 0.0)
    datahora  = a.get("data_deteccao", "")
    mun       = a.get("municipio", "Amapá")
    sat       = a.get("satelite", "Desconhecido")
    lat       = a.get("latitude_centro", 0.0)
    lon       = a.get("longitude_centro", 0.0)

    hora_local, fuso_label, _ = _get_local_time_info(datahora)
    data_br = _format_date(datahora)

    # Determina o emoji de alerta principal conforme a gravidade
    if "Desmatamento" in classe:
        alerta_emoji = "🚨"
    elif "Mineração" in classe:
        alerta_emoji = "🔴"
    else:
        alerta_emoji = "⚠️"

    # Proximidade com áreas protegidas (UCs / TIs)
    nearby_areas = get_nearby_protected_areas(lat, lon, threshold_km=10.0)
    protected_txt = ""
    if nearby_areas:
        protected_txt = "\n\n⚠️ *ÁREA SENSÍVEL PRÓXIMA*"
        for area_info in nearby_areas:
            # Destaque se estiver muito próximo
            alerta_uc = "🚨" if area_info["distancia"] <= 2.0 else "•"
            protected_txt += (
                f"\n{alerta_uc} *Tipo:* {area_info['tipo']}\n"
                f"  *Nome:* {area_info['nome']}\n"
                f"  *Distância:* {area_info['distancia']} km"
            )

    maps_url = f"https://maps.google.com/?q={lat},{lon}"

    msg = (
        f"{alerta_emoji} *ALERTA DE {classe.upper()}*\n\n"
        f"📍 *Município:* {mun}\n"
        f"📋 *Tipo:* {classe}\n"
        f"📐 *Área:* `{area:.1f}` hectares\n"
        f"🛰 *Satélite:* {sat}\n"
        f"📅 *Detecção:* {data_br}\n"
        f"🕒 *Horário Local:* {hora_local}\n"
        f"🌎 *Fuso:* {fuso_label}"
        f"{protected_txt}\n\n"
        f"🗺️ [Abrir no Google Maps]({maps_url})"
    )
    return msg


def _alerta_row_to_line(alerta) -> str:
    """Retorna uma linha de resumo do alerta."""
    a = dict(alerta) if hasattr(alerta, "keys") else alerta
    data_br = _format_date(a.get("data_deteccao", ""))
    
    classe = a.get("classe_label", "Alerta")
    emoji = "🔴" if "Desmatamento" in classe else "⚠️"
    if "Mineração" in class:
        emoji = "⛏️"

    return (
        f"{emoji} *{a.get('municipio', '?')}* — {classe} — "
        f"`{a.get('area_ha', 0.0):.1f} ha` — {data_br}"
    )


# ─── Envio de alertas automáticos ────────────────────────────────────────────

async def send_deforestation_alert(app: Application, alerta: dict) -> bool:
    """Envia alerta de desmatamento contendo mensagem detalhada e anexo KML."""
    a = dict(alerta) if hasattr(alerta, "keys") else alerta
    chat_id = TELEGRAM_CHAT_ID

    gid = a.get("gid_deter")
    alerta_id = a.get("id")

    try:
        text = build_alert_message(a)

        # Botão inline do Maps
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📍 Google Maps",
                url=f"https://maps.google.com/?q={a.get('latitude_centro',0)},{a.get('longitude_centro',0)}"
            )],
        ])

        # Envia a mensagem com os detalhes
        sent_msg = await app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )

        if alerta_id and sent_msg:
            db.update_telegram_message_id(alerta_id, sent_msg.message_id)

        # Gera e envia KML individual
        kml_path = kml_gen.generate_kml_single(a)
        if kml_path and kml_path.exists():
            caption = (
                f"📎 *KML do alerta* (DETER GID: {gid})\n"
                f"_Abra no Google Earth, AlpineQuest ou QGIS para ver o polígono_"
            )
            with open(kml_path, "rb") as kml_file:
                await app.bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(kml_file, filename=kml_path.name),
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_to_message_id=sent_msg.message_id if sent_msg else None,
                )

        logger.info(f"Alerta de desmatamento enviado com sucesso: DETER GID={gid}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar alerta de desmatamento: {e}", exc_info=True)
        return False


# ─── Handlers de comandos ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de boas-vindas do bot de desmatamento."""
    msg = (
        "🌳 *Bot de Monitoramento de Desmatamento — Amapá*\n\n"
        "Monito alertas oficiais do INPE (DETER) para detectar "
        "desmatamento, degradação florestal e mineração ilegal no estado.\n\n"
        "*Comandos disponíveis:*\n"
        "/ultimos — Últimos 10 alertas detectados\n"
        "/hoje — Resumo dos alertas de hoje\n"
        "/semana — Resumo dos alertas da última semana\n"
        "/municipio \\<nome\\> — Alertas de um município específico\n"
        "/tipo \\<nome\\> — Alertas filtrados por tipo\n"
        "/kml — Download KML consolidado das últimas 24h\n"
        "/mapa — Mapa interativo HTML das últimas 24h\n"
        "/status — Status do monitoramento\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_ultimos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra os últimos 10 alertas."""
    alertas = db.get_last_alertas(10)

    if not alertas:
        await update.message.reply_text("ℹ️ Nenhum alerta registrado ainda.")
        return

    lines = ["🌳 *ÚLTIMOS 10 ALERTAS DE DESMATAMENTO*\n"]
    for i, a in enumerate(alertas, 1):
        lines.append(f"{i}. {_alerta_row_to_line(a)}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumo estatístico do dia."""
    alertas = db.get_alertas_today()
    
    total_area = sum(a["area_ha"] for a in alertas)
    total_count = len(alertas)

    # Agrupa por classe
    resumo_classe = {}
    for a in alertas:
        c = a["classe_label"]
        resumo_classe[c] = resumo_classe.get(c, 0.0) + a["area_ha"]

    hoje = datetime.now().strftime("%d/%m/%Y")
    
    msg = (
        f"📊 *RESUMO DO DIA — {hoje}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌳 *Total de Alertas:* {total_count}\n"
        f"📐 *Área Afetada:* `{total_area:.1f}` hectares\n\n"
        f"*Distribuição por Tipo:*"
    )

    if resumo_classe:
        for classe, area in resumo_classe.items():
            msg += f"\n  • {classe}: `{area:.1f}` ha"
    else:
        msg += "\n  ✅ _Nenhum alerta registrado hoje._"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumo estatístico dos últimos 7 dias."""
    # Como o banco tem datahora em ISO 8601, filtramos manualmente
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    with db.get_connection() as conn:
        alertas = conn.execute(
            "SELECT * FROM alertas WHERE data_deteccao >= ? ORDER BY data_deteccao DESC", (since,)
        ).fetchall()

    total_area = sum(a["area_ha"] for a in alertas)
    total_count = len(alertas)

    # Agrupa por município
    muns = {}
    for a in alertas:
        m = a["municipio"] or "Indefinido"
        muns[m] = muns.get(m, 0.0) + a["area_ha"]

    top_muns = sorted(muns.items(), key=lambda x: -x[1])[:5]
    top_txt = "\n".join(f"  • {m}: `{area:.1f}` ha" for m, area in top_muns)

    msg = (
        f"📊 *RESUMO SEMANAL (ÚLTIMOS 7 DIAS)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌳 *Total de Alertas:* {total_count}\n"
        f"📐 *Área Total:* `{total_area:.1f}` hectares\n\n"
        f"*Municípios mais afetados:*\n"
    )
    if top_muns:
        msg += top_txt
    else:
        msg += "  ✅ _Nenhum alerta registrado nos últimos 7 dias._"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_municipio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ℹ️ Uso: `/municipio <nome>`\nExemplo: `/municipio macapa`", parse_mode=ParseMode.MARKDOWN)
        return

    nome = " ".join(context.args)
    alertas = db.get_alertas_by_municipio(nome)

    if not alertas:
        await update.message.reply_text(f"ℹ️ Nenhum alerta encontrado para *{nome}*.", parse_mode=ParseMode.MARKDOWN)
        return

    lines = [f"🌳 *ALERTAS EM {nome.upper()}* ({len(alertas)} registros)\n"]
    for i, a in enumerate(alertas[:20], 1):
        lines.append(f"{i}. {_alerta_row_to_line(a)}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Uso: `/tipo <nome>`\nExemplo: `/tipo desmatamento`\n\n"
            "*Tipos comuns:* Desmatamento, Degradação, Mineração",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    nome = " ".join(context.args)
    alertas = db.get_alertas_by_tipo(nome)

    if not alertas:
        await update.message.reply_text(f"ℹ️ Nenhum alerta encontrado para o tipo *{nome}*.", parse_mode=ParseMode.MARKDOWN)
        return

    lines = [f"🌳 *ALERTAS DE TIPO {nome.upper()}* ({len(alertas)} registros)\n"]
    for i, a in enumerate(alertas[:20], 1):
        lines.append(f"{i}. {_alerta_row_to_line(a)}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_kml(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Gerando KML dos alertas das últimas 24h...")
    alertas = db.get_alertas_24h()

    if not alertas:
        await update.message.reply_text("ℹ️ Nenhum alerta de desmatamento nas últimas 24 horas.")
        return

    kml_path = kml_gen.generate_kml_24h(alertas)
    if not kml_path or not kml_path.exists():
        await update.message.reply_text("❌ Erro ao gerar o arquivo KML.")
        return

    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    caption = (
        f"📎 *KML — Alertas de Desmatamento Amapá*\n"
        f"Últimas 24h • {len(alertas)} alertas • {hoje}\n"
        f"_Compatível com Google Earth, QGIS e AlpineQuest_"
    )

    with open(kml_path, "rb") as f:
        await update.message.reply_document(
            document=InputFile(f, filename=kml_path.name),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_mapa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Gerando mapa interativo...")
    alertas = db.get_alertas_24h()

    if not alertas:
        await update.message.reply_text("ℹ️ Nenhum alerta de desmatamento nas últimas 24 horas para mapear.")
        return

    mapa_path = map_gen.generate_map(alertas)
    if not mapa_path or not mapa_path.exists():
        await update.message.reply_text("❌ Erro ao gerar o mapa.")
        return

    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    caption = (
        f"🗺️ *Mapa Interativo — Desmatamento Amapá*\n"
        f"Últimas 24h • {len(alertas)} alertas • {hoje}\n"
        f"_Abra o arquivo HTML no navegador de internet do celular ou PC_"
    )

    with open(mapa_path, "rb") as f:
        await update.message.reply_document(
            document=InputFile(f, filename=mapa_path.name),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from deter_client import check_api_connection
    from config import MONITORING_INTERVAL_MIN, validate_config

    erros = validate_config()
    config_ok = len(erros) == 0

    api_ok, api_msg = check_api_connection()

    # Estatísticas simples
    with db.get_connection() as conn:
        total_focos = conn.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
        focos_today = conn.execute(
            "SELECT COUNT(*), SUM(area_ha) FROM alertas WHERE data_deteccao LIKE ?", 
            (f"{datetime.now().strftime('%Y-%m-%d')}%",)
        ).fetchone()

    status_config = "✅ OK" if config_ok else f"❌ {'; '.join(erros)}"
    status_api    = "✅ OK" if api_ok else f"❌ {api_msg}"

    msg = (
        f"⚙️ *STATUS DO SISTEMA — DESMATAMENTO*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Configuração: {status_config}\n"
        f"🌐 INPE DETER API: {status_api}\n"
        f"⏱️ Intervalo: {MONITORING_INTERVAL_MIN} minutos\n\n"
        f"*Estatísticas do Banco:*\n"
        f"  Total de alertas gravados: {total_focos}\n"
        f"  Alertas hoje: {focos_today[0]}\n"
        f"  Área afetada hoje: `{focos_today[1] or 0.0:.1f}` hectares"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ─── Registro de handlers ─────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("ultimos",   cmd_ultimos))
    app.add_handler(CommandHandler("hoje",      cmd_hoje))
    app.add_handler(CommandHandler("semana",    cmd_semana))
    app.add_handler(CommandHandler("municipio", cmd_municipio))
    app.add_handler(CommandHandler("tipo",      cmd_tipo))
    app.add_handler(CommandHandler("kml",       cmd_kml))
    app.add_handler(CommandHandler("mapa",      cmd_mapa))
    app.add_handler(CommandHandler("status",    cmd_status))
    logger.info("Handlers de comando do desmatamento registrados")
