#!/bin/bash
# service_control.sh — Gerencia o serviço de monitoramento do bot de desmatamento no macOS (launchd)

PLIST_PATH="$HOME/Library/LaunchAgents/com.ap.desmatamentobot.plist"
LABEL="com.ap.desmatamentobot"

case "$1" in
    start)
        echo "🚀 Iniciando o bot de desmatamento no sistema..."
        launchctl bootstrap gui/$(id -u) "$PLIST_PATH" 2>/dev/null || launchctl load "$PLIST_PATH"
        echo "✅ Serviço ativado! O bot rodará em segundo plano permanentemente."
        ;;
    stop)
        echo "⏹️ Parando o bot de desmatamento..."
        launchctl bootout gui/$(id -u) "$PLIST_PATH" 2>/dev/null || launchctl unload "$PLIST_PATH"
        echo "✅ Serviço desativado."
        ;;
    status)
        echo "📊 Verificando status do bot..."
        PID=$(pgrep -f "desmatamento-bot/main.py")
        if [ -n "$PID" ]; then
            echo "🟢 O Bot de Desmatamento está ativo e rodando! (PID: $PID)"
            echo "Últimos logs:"
            tail -n 5 "/Users/rith/Library/CloudStorage/OneDrive-Pessoal/desmatamento-bot/logs/launchd_stderr.log" 2>/dev/null
        else
            echo "🔴 O Bot está desligado ou o sistema está hibernando."
        fi
        ;;
    restart)
        echo "🔄 Reiniciando o bot..."
        $0 stop
        sleep 1
        $0 start
        ;;
    *)
        echo "Uso: ./service_control.sh {start|stop|restart|status}"
        exit 1
        ;;
esac
