# 🔥 Monitor de Focos de Calor — Estado do Amapá

Bot Telegram de monitoramento automático de focos de calor no estado do Amapá, integrado à NASA FIRMS API.

---

## 📋 Visão Geral

O **Monitor de Focos de Calor — Amapá** é um bot Telegram que verifica automaticamente a cada **15 minutos** se há novos focos de calor detectados por satélites no território do Amapá.

### Satélites monitorados

| Satélite | Fonte |
|---|---|
| VIIRS NOAA-20 | NASA FIRMS |
| VIIRS Suomi NPP | NASA FIRMS |
| MODIS Terra | NASA FIRMS |
| MODIS Aqua | NASA FIRMS |
| GOES | NASA FIRMS |

### O que acontece ao detectar um foco

1. **Identifica o município** onde o foco está localizado (geocodificação reversa offline)
2. **Calcula a distância** até o quartel do CBM/AP mais próximo (fórmula de Haversine)
3. **Classifica a intensidade** com base no FRP (Fire Radiative Power):
   - 🔴 **Alta** — FRP elevado
   - 🟡 **Média** — FRP moderado
   - 🟢 **Baixa** — FRP reduzido
4. **Envia alerta** no grupo Telegram com:
   - Arquivo KML para visualização em Google Earth / Earth Pro
   - Link direto para o Google Maps

---

## 📁 Estrutura de Pastas

```
bot/
├── main.py               ← Ponto de entrada. Inicia watchdog, health server, polling
├── config.py             ← Lê .env, define constantes
├── database.py           ← SQLite: focos, quartéis
├── firms_client.py       ← Conector NASA FIRMS API
├── telegram_bot.py       ← Handlers de comandos e envio de alertas
├── municipalities.py     ← Geocodificação reversa offline
├── quartels.py           ← Distância até quartéis (Haversine)
├── kml_generator.py      ← Geração de KML
├── map_generator.py      ← Geração de mapas HTML (Folium)
├── weather_client.py     ← Dados meteorológicos (opcional)
├── requirements.txt      ← Dependências
├── render.yaml           ← Config do Render
├── .env                  ← ⚠️ NUNCA suba para o GitHub!
├── .env.example          ← Modelo do .env
├── data/focos.db         ← Banco SQLite
├── logs/                 ← Logs diários
├── kml/                  ← KMLs gerados (limpos em 48h)
└── mapas/                ← Mapas HTML (limpos em 48h)
```

---

## 🔐 Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha os valores:

| Variável | Obrigatoriedade | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ Obrigatório | Token obtido no [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ Obrigatório | ID negativo do grupo Telegram (ex: `-1003861685068`) |
| `NASA_FIRMS_API_KEY` | ✅ Obrigatório | Gratuito em https://firms.modaps.eosdis.nasa.gov/api/ |
| `MONITORING_INTERVAL` | ⬜ Opcional | Intervalo em minutos (padrão: `15`) |
| `TIMEZONE` | ⬜ Opcional | Fuso horário (padrão: `America/Belem`) |
| `PORT` | ⬜ Opcional | Porta do health server (padrão: `8080` local / `10000` no Render) |

> ⚠️ **NUNCA** suba o arquivo `.env` para o GitHub. Ele já está no `.gitignore`.

---

## 🤖 Comandos do Telegram

| Comando | Descrição |
|---|---|
| `/start` | Mensagem de boas-vindas e lista de comandos |
| `/status` | Status atual do bot, última verificação e contagem de focos |
| `/hoje` | Focos detectados nas últimas 24 horas |
| `/ultimos` | Últimos focos registrados no banco de dados |
| `/municipio <nome>` | Focos em um município específico |
| `/satelite <nome>` | Focos detectados por um satélite específico |
| `/kml` | Gera e envia arquivo KML com os focos recentes |
| `/mapa` | Gera e envia mapa HTML interativo (Folium) |

---

## 🛠️ Instalação Local

```bash
# 1. Clonar o repositório
git clone https://github.com/rithelybarbosa-maker/amapa-focos-bot.git
cd amapa-focos-bot

# 2. Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com seus valores

# 5. Iniciar o bot
python main.py
```

---

## 🚀 Deploy

Consulte o arquivo **[DEPLOY.md](DEPLOY.md)** para instruções completas de deploy no Render.com.

---

## 🔧 Solução de Problemas

Consulte o arquivo **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** para diagnóstico e correção dos problemas mais comuns.

---

## 🧰 Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| **Python 3.11+** | Linguagem principal |
| **python-telegram-bot 21+** | Interface com a API do Telegram |
| **NASA FIRMS API** | Dados de focos de calor por satélite |
| **SQLite** | Banco de dados local (focos, quartéis) |
| **Render.com** | Hospedagem do bot (plano gratuito) |
| **cron-job.org** | Keep-alive periódico (previne hibernação) |

---

## 🔗 GitHub

- **Repositório:** https://github.com/rithelybarbosa-maker/amapa-focos-bot
- **Branch principal:** `main`

---

*Desenvolvido para monitoramento de emergências ambientais no Estado do Amapá — Corpo de Bombeiros Militar do Amapá (CBM/AP).*
