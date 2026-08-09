# 🤖 AI_CONTEXT — Amapá Focos de Calor Bot

## Propósito deste Documento

Este arquivo é a **memória permanente do projeto**. Qualquer IA (ou desenvolvedor) deve ler este arquivo antes de modificar, depurar ou recriar qualquer parte do sistema. Ele contém todas as decisões de arquitetura, variáveis críticas, URLs e comportamentos esperados do bot.

> ⚠️ Leia este arquivo **inteiro** antes de fazer qualquer alteração no código.

---

## 🏗️ Arquitetura Completa

```
[NASA FIRMS API] → firms_client.py → database.py (SQLite)
                                    ↓
[cron-job.org] → amapa-focos-bot.onrender.com (health check HTTP)
                                    ↓
                            main.py (polling loop)
                                    ↓
                         telegram_bot.py → [Telegram API]
                                    ↓
                      municipalities.py (geocoding)
                      quartels.py (distância)
                      kml_generator.py (KML)
                      map_generator.py (HTML map)
```

### Fluxo de dados resumido

1. `main.py` inicia o **health server** (ThreadingHTTPServer) em thread separada.
2. `main.py` inicia o **watchdog** em thread separada.
3. `main.py` inicia o `Application` do `python-telegram-bot` com `run_polling`.
4. O `job_queue` agenda `monitoring_job` (a cada 15 min) e `polling_health_job` (a cada 60s).
5. `monitoring_job` chama `firms_client.py` → armazena novos focos no SQLite → envia alertas via `telegram_bot.py`.
6. O cron-job.org faz GET na URL do Render a cada 5 minutos para evitar hibernação.

---

## 🔧 Decisões Técnicas Críticas

### 1. Watchdog (HARD_TIMEOUT = 300s)
O watchdog roda em uma **thread separada** e monitora o timestamp do último heartbeat. Se o heartbeat não for atualizado em 300 segundos, o watchdog entende que o event loop Python está travado e chama `os._exit(2)` para **forçar reinício imediato** pelo Render.

> ⚠️ Não use `sys.exit()` aqui — ele pode ser capturado por handlers de exceção. `os._exit()` termina o processo incondicionalmente.

### 2. polling_health_job (a cada 60s)
Esta job roda dentro do `job_queue` do `python-telegram-bot` e atualiza o heartbeat do watchdog a cada 60 segundos. Se esta job parar de rodar (event loop travado), o watchdog detecta e reinicia.

> ⚠️ Garantir que `polling_health_job` sempre chame `_update_heartbeat()` ao final, mesmo em caso de exceção.

### 3. drop_pending_updates = False
O `run_polling` usa `drop_pending_updates=False`. Isso garante que **comandos enviados enquanto o bot estava dormindo/reiniciando** sejam processados quando o bot acordar. Mudar para `True` causa perda de mensagens pendentes.

### 4. shapely é OPCIONAL
O `municipalities.py` usa `shapely` para geocodificação reversa precisa (ponto dentro de polígono). Porém, `shapely` **não está** em `requirements.txt` porque consome memória excessiva no Render Free Tier (>512MB RAM → crash). O código usa um **fallback automático de centróides matemáticos** quando `shapely` não está instalado.

> ⛔ NÃO adicione `shapely` ou `geopandas` ao `requirements.txt`.

### 5. Health Check Server (ThreadingHTTPServer)
Roda em thread separada na porta `$PORT` (10000 no Render, 8080 local). Responde às seguintes rotas:
- `GET /` → `200 OK` com mensagem de status
- `GET /health` → JSON com diagnóstico detalhado (uptime, focos, heartbeat, etc.)
- `GET /logs` → Últimas 100 linhas do log do dia atual

### 6. Render Free Tier + cron-job.org
O **Render Free Tier hiberna** o serviço após **15 minutos sem requisição HTTP**. O cron-job.org faz um `GET` na URL do bot a cada **5 minutos** para manter o processo vivo.

> Se o cron-job.org parar, o bot hiberna e para de monitorar. Verifique em https://cron-job.org.

---

## 📁 Arquivos Críticos

> ⚠️ Não altere estes arquivos sem entender completamente o impacto:

| Arquivo | Por que é crítico |
|---|---|
| `main.py` | Controla o ciclo de vida completo: watchdog, health server, polling |
| `config.py` | Todas as constantes e leitura do `.env` — erros aqui quebram tudo |
| `database.py` | Schema do SQLite — alterações podem corromper dados existentes |
| `telegram_bot.py` | Todos os handlers e lógica de envio de alertas |
| `firms_client.py` | Integração com a NASA FIRMS API — parsing do CSV/JSON |

---

## 🔑 Variáveis de Ambiente (Render)

Configure estas variáveis no painel do Render em **Environment Variables**:

| Variável | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do @FocosAp_bot (obtido no @BotFather) |
| `TELEGRAM_CHAT_ID` | `-1003861685068` |
| `NASA_FIRMS_API_KEY` | Chave FIRMS (gratuita em https://firms.modaps.eosdis.nasa.gov/api/) |
| `PORT` | `10000` |
| `PYTHON_VERSION` | `3.11.0` |

---

## 🌐 Comandos Importantes (API Telegram)

Use estes endpoints diretamente no navegador ou via `curl` para diagnóstico:

```bash
# Verificar se há webhook ativo (deve estar vazio para usar polling)
GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Deletar webhook (necessário se ocorrer conflito 409)
GET https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true

# Ver updates pendentes
GET https://api.telegram.org/bot<TOKEN>/getUpdates

# Verificar se o bot está vivo (deve retornar 200)
GET https://amapa-focos-bot.onrender.com

# Ver últimas 100 linhas de log
GET https://amapa-focos-bot.onrender.com/logs

# Diagnóstico detalhado (JSON)
GET https://amapa-focos-bot.onrender.com/health
```

---

## 🐛 Bugs Conhecidos

### Bug 1 — Render hiberna sem cron
**Sintoma:** Bot para de monitorar silenciosamente.
**Causa:** O cron-job.org está pausado ou foi deletado.
**Solução:** Acessar https://cron-job.org, verificar o job "Focos AP — Keep Alive" e reativar se necessário.

---

### Bug 2 — Conflito 409 (duas instâncias)
**Sintoma:** Log mostra `POLLING_ERROR: Conflict: terminated by other getUpdates request`.
**Causa:** Duas instâncias do bot com o mesmo `TELEGRAM_BOT_TOKEN` rodando ao mesmo tempo (ex: bot local + Render).
**Solução:** Garantir apenas 1 instância ativa. Em desenvolvimento, pare o bot local **antes** de fazer deploy ou **antes** de iniciar localmente enquanto o Render está rodando.

---

### Bug 3 — Watchdog falso positivo
**Sintoma:** Log mostra `WATCHDOG: Event loop travado` mas o bot parecia funcionar.
**Causa:** `polling_health_job` não estava chamando `_update_heartbeat()` após execução.
**Status:** ✅ **Já corrigido** na versão atual.

---

## ➕ Como Adicionar Novas Funcionalidades

### Novo comando Telegram
1. Crie a função `async def cmd_xxx(update, context)` em `telegram_bot.py`
2. Registre o handler em `register_handlers()` com `CommandHandler("xxx", cmd_xxx)`
3. Documente o comando na resposta do `/start`

### Nova fonte de dados (satélite)
1. Adicione a nova chave em `FIRMS_SOURCES` em `config.py`
2. Certifique-se de que `firms_client.py` consegue fazer parse do formato retornado

### Novo alerta automático
1. Modifique `monitoring_job()` em `main.py`
2. Use as funções de envio já existentes em `telegram_bot.py`

---

## 🚀 Como Fazer Deploy de Nova Versão

```bash
# 1. Commitar as alterações
git add .
git commit -m "descrição clara das mudanças"
git push
```

O **Render detecta automaticamente** o push no branch `main` e inicia um novo deploy.

- Verifique os logs em https://dashboard.render.com após **2-3 minutos**.
- O bot fica offline por ~30-60 segundos durante o deploy (tempo de build).

---

## 🔗 URLs Importantes

| Recurso | URL |
|---|---|
| Bot (health check) | https://amapa-focos-bot.onrender.com |
| GitHub | https://github.com/rithelybarbosa-maker/amapa-focos-bot |
| Render Dashboard | https://dashboard.render.com |
| NASA FIRMS API | https://firms.modaps.eosdis.nasa.gov/api/ |
| Cron-job.org | https://cron-job.org |
| Telegram @FocosAp_bot | https://t.me/FocosAp_bot |

---

*Última atualização: Agosto 2026*
