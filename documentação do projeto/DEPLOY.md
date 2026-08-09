# 🚀 DEPLOY.md — Guia Completo de Deploy

Guia passo a passo para publicar o Monitor de Focos de Calor — Amapá no **Render.com** com deploy automático via GitHub.

---

## 📋 Pré-requisitos

Antes de começar, garanta que você tem:

- ✅ Conta no **GitHub** (https://github.com)
- ✅ Conta no **Render.com** (https://render.com) — plano gratuito é suficiente
- ✅ Conta no **cron-job.org** (https://cron-job.org) — para manter o bot acordado

---

## 1️⃣ Configuração do GitHub

### Primeira vez (repositório novo)

```bash
# Inicializar repositório local
git init
git remote add origin https://github.com/rithelybarbosa-maker/amapa-focos-bot.git
git branch -M main
git push -u origin main
```

### Atualizar o repositório (versões futuras)

```bash
git add .
git commit -m "descrição clara do que foi alterado"
git push
```

> ⚠️ Certifique-se de que o `.gitignore` contém `.env` para nunca subir credenciais.

---

## 2️⃣ Configuração do Render

### Passo a passo completo

1. Acesse https://render.com e faça login com sua conta GitHub
2. No painel, clique em **New +** → **Web Service**
3. Na tela de conexão, selecione **Connect a repository**
4. Encontre e selecione o repositório **`amapa-focos-bot`**
5. Preencha as configurações do serviço:

| Campo | Valor |
|---|---|
| **Name** | `amapa-focos-bot` |
| **Region** | Oregon (US West) |
| **Branch** | `main` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance Type** | Free |

6. Role até a seção **Environment Variables** e adicione:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | *(seu token do @BotFather)* |
| `TELEGRAM_CHAT_ID` | *(ID negativo do grupo — ex: `-1003861685068`)* |
| `NASA_FIRMS_API_KEY` | *(sua chave FIRMS)* |
| `PORT` | `10000` |
| `PYTHON_VERSION` | `3.11.0` |

7. Em **Health Check Path**, configure: `/`
8. Clique em **Create Web Service**

O Render vai iniciar o primeiro build automaticamente. Aguarde de **2 a 5 minutos**.

---

## 3️⃣ Deploy Manual

Se precisar forçar um novo deploy sem alterar o código:

1. Acesse o painel do Render
2. Entre no serviço `amapa-focos-bot`
3. Clique em **Manual Deploy** → **Deploy latest commit**

---

## 4️⃣ Deploy Limpo (Resolver Bugs de Build)

Se o build estiver falhando por causa de cache de dependências corrompido:

1. Acesse o painel do Render
2. Entre no serviço `amapa-focos-bot`
3. Clique em **Manual Deploy** → **Clear Build Cache and Deploy**

> Use esta opção sempre que alterar o `requirements.txt` e o build falhar de forma inesperada.

---

## 5️⃣ Verificação Pós-Deploy

Após o deploy concluir com sucesso:

### Verificação 1 — Status no Render
- O painel deve mostrar o status **Live** (indicador verde)
- O log deve terminar com algo como `Bot iniciado com sucesso` ou `Application started`

### Verificação 2 — Health Check HTTP
Acesse no navegador:
```
https://amapa-focos-bot.onrender.com
```
Deve retornar:
```
Bot de Monitoramento Amapá Focos está ativo!
```

### Verificação 3 — Telegram
- Abra o grupo no Telegram
- Envie `/status` para o `@FocosAp_bot`
- O bot deve responder com o status atual em poucos segundos

---

## 6️⃣ Render YAML

O arquivo `render.yaml` já está incluído no repositório. Ele define a configuração do serviço como código:

```yaml
services:
  - type: web
    name: amapa-focos-bot
    runtime: python
    buildCommand: pip install --upgrade pip && pip install -r requirements.txt
    startCommand: python main.py
    plan: free
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: PORT
        value: 10000
    healthCheckPath: /
```

> As variáveis sensíveis (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NASA_FIRMS_API_KEY`) **não devem** estar no `render.yaml` — configure-as manualmente no painel do Render.

---

## 7️⃣ Atualização de Versão

Para publicar uma nova versão do bot, basta fazer `git push`:

```bash
git add .
git commit -m "feat: adiciona suporte ao satélite GOES-18"
git push
```

O Render detecta o push no branch `main` e inicia um novo deploy automaticamente. Nenhuma ação manual é necessária.

---

## 8️⃣ Rollback para Versão Anterior

Se um deploy introduzir um bug crítico:

1. Acesse o painel do Render
2. Entre no serviço `amapa-focos-bot`
3. Clique na aba **Deploys**
4. Encontre o deploy anterior (que estava funcionando)
5. Clique nos três pontos `...` ao lado dele
6. Selecione **Rollback to this deploy**

O Render volta para a versão anterior sem necessidade de alterar o código.

---

## 📌 Próximo Passo

Após o deploy, configure o **cron-job.org** para manter o bot acordado. Consulte o arquivo **[CRON.md](CRON.md)**.

---

*Para problemas de deploy, consulte [TROUBLESHOOTING.md](TROUBLESHOOTING.md).*
