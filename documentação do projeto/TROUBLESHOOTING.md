# 🔧 TROUBLESHOOTING.md — Solução de Problemas

Guia de diagnóstico e correção para os problemas mais comuns do Monitor de Focos de Calor — Amapá.

---

## Problema 1 — Bot Não Responde no Telegram

### Sintoma
Você envia `/status` (ou qualquer comando) no Telegram, mas não recebe resposta.

### Possíveis Causas
- O Render hibernou o bot por inatividade
- Há um webhook ativo conflitando com o modo polling
- O bot não está adicionado ao chat como **administrador**

### Diagnóstico

**Passo 1 — Verificar se o serviço está vivo:**
```
GET https://amapa-focos-bot.onrender.com
```
- Se retornar `200 OK` → serviço está vivo, problema pode ser webhook ou permissão
- Se retornar `503` → serviço hibernou ou crashou → vá para o **Problema 2**

**Passo 2 — Verificar webhook:**
```
GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```
Verifique se o campo `url` está vazio. Se houver uma URL, há um webhook ativo conflitando.

**Passo 3 — Ver updates pendentes:**
```
GET https://api.telegram.org/bot<TOKEN>/getUpdates
```

### Correção

**1. Deletar o webhook:**
```
GET https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true
```

**2. Acordar o Render:**
```
GET https://amapa-focos-bot.onrender.com
```

**3. Aguardar 30 segundos e reenviar `/status` no Telegram.**

---

## Problema 2 — Render Retorna 503

### Sintoma
- O cron-job.org reporta `503 Service Unavailable`
- Ou a URL https://amapa-focos-bot.onrender.com retorna erro 503

### Causa
O bot crashou por erro fatal (ex: memória, exceção não tratada) ou está em processo de hibernação.

### Diagnóstico
1. Acesse https://dashboard.render.com
2. Abra o serviço `amapa-focos-bot`
3. Clique na aba **Logs**
4. Procure por mensagens de erro como:
   - `MemoryError`
   - `Exception in thread`
   - `Killed` (processo eliminado por uso excessivo de memória)

### Correção

```
Render → amapa-focos-bot → Manual Deploy → Deploy latest commit
```

Se o erro persistir após o deploy:
```
Render → amapa-focos-bot → Manual Deploy → Clear Build Cache and Deploy
```

---

## Problema 3 — Watchdog Mata o Processo (Exit Status 2)

### Sintoma
O log mostra:
```
WATCHDOG: Event loop travado há 300s — forçando reinício (os._exit(2))
```

### Causa
O `polling_health_job` (que roda a cada 60s dentro do `job_queue`) não estava atualizando o heartbeat do watchdog. Isso faz o watchdog interpretar que o event loop Python está travado.

### Correção
Garantir que `polling_health_job` chama `_update_heartbeat()` ao final de sua execução, mesmo em caso de exceção:

```python
async def polling_health_job(context):
    try:
        # ... lógica do job ...
    except Exception as e:
        logger.error(f"polling_health_job error: {e}")
    finally:
        _update_heartbeat()  # ← sempre atualizar, mesmo em erro
```

> ✅ **Já corrigido** na versão atual do código. Se o problema ocorrer novamente, verifique se o arquivo `main.py` foi revertido acidentalmente.

---

## Problema 4 — Bot Não Recebe Mensagens (TELEGRAM age Crescendo)

### Sintoma
No log, o campo `TELEGRAM age` continua aumentando (ex: `TELEGRAM age: 180s`, `240s`...) mas `polling_task=VIVO`.

### Causa
- `drop_pending_updates=True` foi ativado, descartando mensagens pendentes
- **Ou** há um webhook ativo bloqueando as atualizações do polling

### Correção

**1. Verificar a configuração do `run_polling`:**

Certifique-se de que em `main.py` o `run_polling` usa:
```python
application.run_polling(drop_pending_updates=False)
```

**2. Deletar qualquer webhook ativo:**
```
GET https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true
```

**3. Reiniciar o bot** via Manual Deploy no Render.

---

## Problema 5 — NASA FIRMS Retorna HTML (Erro de Autenticação)

### Sintoma
O log mostra:
```
[VIIRS_NOAA20] API retornou HTML — possível erro de autenticação
```

### Causa
A `NASA_FIRMS_API_KEY` está inválida, expirada ou incorreta.

### Diagnóstico
Teste a chave diretamente:
```
GET https://firms.modaps.eosdis.nasa.gov/api/country/csv/<SUA_CHAVE>/VIIRS_SNPP_NRT/BRA/1
```
- Se retornar CSV → chave válida, problema pode ser outra coisa
- Se retornar HTML com mensagem de erro → chave inválida ou expirada

### Correção
1. Acesse https://firms.modaps.eosdis.nasa.gov/api/
2. Gere uma nova chave de API (gratuita)
3. Atualize a variável `NASA_FIRMS_API_KEY` no Render:
   - Render → `amapa-focos-bot` → **Environment** → editar `NASA_FIRMS_API_KEY`
4. Após salvar, o Render reinicia automaticamente o serviço

---

## Problema 6 — Erro de Memória (Crash Silencioso)

### Sintoma
O bot reinicia frequentemente (a cada 5-15 minutos) sem mensagem de erro clara nos logs. O Render mostra `Exit: Killed`.

### Causa
Dependências pesadas como `geopandas` ou `shapely` estão consumindo mais de **512MB de RAM** — o limite do Render Free Tier. O sistema operacional encerra o processo.

### Diagnóstico
Verifique o `requirements.txt`:
```bash
grep -E "shapely|geopandas|fiona|pyproj" requirements.txt
```
Se alguma dessas bibliotecas aparecer, é a causa do problema.

### Correção
Remova as dependências pesadas do `requirements.txt`. O `municipalities.py` usa **fallback automático de centróides matemáticos** quando `shapely` não está disponível:

```python
try:
    from shapely.geometry import Point
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    # usa centróides como fallback
```

> ⛔ **NÃO adicione** `shapely`, `geopandas`, `fiona` ou `pyproj` ao `requirements.txt`.

---

## Problema 7 — Conflito 409 (Dois Processos com Mesmo Token)

### Sintoma
O log mostra repetidamente:
```
POLLING_ERROR: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

### Causa
Duas instâncias do bot estão rodando simultaneamente com o **mesmo `TELEGRAM_BOT_TOKEN`**:
- Bot rodando localmente no computador **E** bot rodando no Render
- **Ou** duas instâncias no Render (não deveria acontecer, mas pode ocorrer em deploys sobrepostos)

### Correção
1. **Em desenvolvimento:** pare o bot local antes de fazer deploy
   ```bash
   Ctrl+C  # no terminal onde main.py está rodando
   ```
2. **No Render:** verifique se há múltiplas instâncias do serviço

Para confirmar qual instância está respondendo:
```
GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

---

## 📋 Como Verificar os Logs

### Via Render (completo)
```
https://dashboard.render.com → amapa-focos-bot → Logs
```

### Via URL do bot (últimas 100 linhas)
```
GET https://amapa-focos-bot.onrender.com/logs
```

### Via URL do bot (diagnóstico JSON detalhado)
```
GET https://amapa-focos-bot.onrender.com/health
```
Retorna informações sobre: uptime, heartbeat, última verificação FIRMS, contagem de focos, status das threads.

### Localmente
```bash
tail -f logs/bot_$(date +%Y-%m-%d).log
```

---

## ✅ Checklist de Recuperação Rápida

Use esta lista quando o bot parar de funcionar:

- [ ] **Bot respondendo?**
  → `GET https://amapa-focos-bot.onrender.com` (deve retornar `200 OK`)

- [ ] **Webhook limpo?**
  → `GET https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true`

- [ ] **Cron-job ativo e retornando 200?**
  → Verificar em https://cron-job.org → "Focos AP — Keep Alive" → Execution History

- [ ] **Variáveis de ambiente corretas no Render?**
  → Render → `amapa-focos-bot` → **Environment** → checar `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NASA_FIRMS_API_KEY`

- [ ] **Último deploy sem erro?**
  → Render → `amapa-focos-bot` → aba **Deploys** → verificar status do último deploy

- [ ] **`requirements.txt` sem shapely/geopandas?**
  → `grep -E "shapely|geopandas" requirements.txt` (deve retornar vazio)

---

*Para dúvidas sobre deploy, consulte [DEPLOY.md](DEPLOY.md). Para entender a arquitetura, consulte [AI_CONTEXT.md](AI_CONTEXT.md).*
