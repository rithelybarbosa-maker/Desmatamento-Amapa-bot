# ⏰ CRON.md — Configuração dos Agendamentos

Guia completo para configurar os agendamentos externos (cron-job.org) e entender os jobs internos do bot.

---

## Por que o Cron é Necessário?

O **Render Free Tier hiberna** automaticamente qualquer serviço que não receba uma requisição HTTP por **mais de 15 minutos**. Quando o serviço hiberna:

- O bot **para de monitorar** focos de calor
- O bot **para de responder** a comandos no Telegram
- O processo Python é **encerrado completamente**

Para evitar isso, o **cron-job.org** faz um ping HTTP (`GET`) na URL do bot a cada **5 minutos**, mantendo o serviço acordado indefinidamente.

> 💡 O primeiro acesso após uma hibernação pode demorar **10-30 segundos** — o Render precisa inicializar o container.

---

## ⚙️ Configuração no cron-job.org

### Passo a passo

1. Acesse https://cron-job.org e crie uma conta gratuita (ou faça login)
2. No painel, clique em **Create cronjob**
3. Preencha o formulário:

| Campo | Valor |
|---|---|
| **URL** | `https://amapa-focos-bot.onrender.com` |
| **Título** | `Focos AP — Keep Alive` |
| **Expressão CRON** | `*/5 * * * *` |
| **Método HTTP** | `GET` |
| **Fuso horário** | `America/Belem (UTC-3)` |
| **Status** | ✅ Ativo |

4. Clique em **Salvar (Create)**

### O que significa `*/5 * * * *`?

```
┌──────── minuto (*/5 = a cada 5 minutos)
│ ┌────── hora (*)
│ │ ┌──── dia do mês (*)
│ │ │ ┌── mês (*)
│ │ │ │ ┌ dia da semana (*)
* * * * *
```

A expressão `*/5 * * * *` faz o job executar nos minutos 0, 5, 10, 15, 20... de cada hora, todos os dias.

---

## 🧪 Como Testar Manualmente

1. Acesse https://cron-job.org e abra o painel
2. Clique no job **Focos AP — Keep Alive**
3. Clique em **Run now**
4. Aguarde 2-5 segundos e verifique o resultado

✅ **Resultado esperado:** `200 OK` com tempo de resposta < 5 segundos
❌ **Resultado problemático:** `503 Service Unavailable` (bot hibernou ou crashou)

---

## 📊 Como Verificar o Histórico de Execuções

1. Acesse o job no cron-job.org
2. Clique na aba **Execution History**
3. Você verá uma tabela com:
   - Data e hora de cada execução
   - Código HTTP retornado
   - Tempo de resposta em milissegundos
   - Status (sucesso/falha)

> Execuções com código `200` indicam que o bot estava vivo e respondeu corretamente.

---

## 🚨 O que Fazer se Retornar 503

O código `503 Service Unavailable` indica que o bot está **hibernado ou com erro**.

### Diagnóstico

1. Acesse o painel do Render: https://dashboard.render.com
2. Abra o serviço `amapa-focos-bot`
3. Verifique o status: se estiver **Suspended**, aguarde o wake-up
4. Verifique a aba **Logs** por erros fatais

### Correção

```
Render → amapa-focos-bot → Manual Deploy → Deploy latest commit
```

Se o build falhar:
```
Render → amapa-focos-bot → Manual Deploy → Clear Build Cache and Deploy
```

Após o deploy:
1. Aguarde o status ficar **Live** (verde)
2. Acesse https://amapa-focos-bot.onrender.com
3. Execute o job manualmente no cron-job.org para confirmar `200 OK`

---

## 🌿 Job do Bot de Desmatamento (Separado)

Se você também operar o bot de desmatamento, configure um segundo job:

| Campo | Valor |
|---|---|
| **URL** | `https://desmatamento-amapa-bot.onrender.com` |
| **Título** | `Desmatamento AP — Keep Alive` |
| **Expressão CRON** | `*/5 * * * *` |
| **Método** | `GET` |

---

## 🔄 Agendador Interno do Bot (job_queue)

Além do cron externo, o próprio bot possui jobs internos gerenciados pelo `job_queue` do `python-telegram-bot`:

| Job | Intervalo | Função |
|---|---|---|
| `monitoring_job` | A cada 15 minutos *(configurável via `MONITORING_INTERVAL`)* | Consulta a NASA FIRMS API, salva novos focos, envia alertas |
| `polling_health_job` | A cada 60 segundos | Atualiza o heartbeat do watchdog para evitar reinício falso |
| `cleanup_old_kmls` | Ao final de cada `monitoring_job` | Remove arquivos KML e mapas HTML com mais de 48 horas |

> ⚠️ Esses jobs rodam **dentro do event loop** do Python. Se o bot hibernar no Render, eles também param. Por isso o keep-alive externo é essencial.

---

## 📌 Limites do Plano Gratuito do cron-job.org

| Limite | Valor |
|---|---|
| Jobs simultâneos | 5 |
| Frequência mínima | 1 minuto |
| Precisão de execução | ±segundos (sem garantia exata) |
| Histórico de execuções | 30 dias |

O plano gratuito é mais que suficiente para manter 2 bots (focos + desmatamento) com ping a cada 5 minutos.

---

*Para problemas relacionados ao keep-alive ou hibernação do Render, consulte [TROUBLESHOOTING.md](TROUBLESHOOTING.md).*
