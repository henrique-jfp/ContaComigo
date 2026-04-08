<div align="center">
  <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
  <img src="https://img.shields.io/badge/IA-Groq_LLaMA_3.x-FF6B35?style=for-the-badge" alt="Groq" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="Postgres" />
  <img src="https://img.shields.io/badge/Dashboard-Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Architecture-Hybrid-9C27B0?style=for-the-badge" alt="Hybrid" />
</div>

<h1 align="center">ContaComigo</h1>

> **Assistente financeiro inteligente no Telegram com arquitetura híbrida, automação completa de lançamentos e dashboard web em tempo real.**

---

## 📋 Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura Híbrida](#-arquitetura-híbrida)
3. [Componentes Principais](#-componentes-principais)
4. [Fluxo de Dados](#-fluxo-de-dados)
5. [Tecnologias](#-tecnologias)
6. [Funcionalidades](#-funcionalidades)
7. [Performance & Confiabilidade](#-performance--confiabilidade)
8. [Deployment](#-deployment)
9. [Desenvolvimento Local](#-desenvolvimento-local)

---

## 🎯 Visão Geral

**ContaComigo** é um ecossistema financeiro completo construído em torno do Telegram, oferecendo aos usuários uma forma intuitiva e frictionless de registrar, analisar e planejar suas finanças pessoais.

### Proposta de Valor

- **Zero Setup & Zero Atrito:** Fim dos comandos complexos. O chat é apenas para interações naturais (voz, texto, foto), enquanto configurações e visualizações moram no MiniApp.
- **IA Inteligente:** Router Alfredo (Groq) com function-calling para decisões automáticas
- **Dashboard Web:** MiniApp otimizada para carregamento instantâneo
- **OCR & Parsing Universal:** Leitura multimodal nativa (Gemini 2.5 Flash) capaz de extrair dados de notas físicas e faturas em PDF de QUALQUER banco.
- **Análises em Tempo Real:** Insights personalizados e alertas proativos
- **Assistente Proativo:** Notificações diárias de contas a pagar com botão "✅ Dar baixa" direto no chat.
- **Gamificação Viciante:** Transforme o controle financeiro em um jogo de RPG com missões, XP, rankings e níveis.
- **Escalável:** Arquitetura híbrida que suporta milhares de usuários simultâneos

---

## 🏗️ Arquitetura Híbrida

```
┌─────────────────────────────────────────────────────────────────┐
│                      MODO HÍBRIDO (LOCAL_DEV)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  THREAD 1 (Bot Telegram)        │  MAIN PROCESS (Flask Dashboard) │
│  ────────────────────────       │  ────────────────────────────── │
│  • Polling (getUpdates)         │  • Flask app (Port: $PORT)      │
│  • Handlers por tipo de media   │  • /api/miniapp/* endpoints    │
│  • Alfredo router (Groq)        │  • /api/telegram/auth          │
│  • OCR, audio, processamento    │  • WebApp view                  │
│  • Background jobs (APScheduler)│  • Static files + templates    │
│  ────────────────────────       │  ────────────────────────────── │
│  Runs: Thread(target=bot)       │  Runs: python launcher.py       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                          ↓
                   Compartilhado
                          ↓
              ┌──────────────────────┐
              │ PostgreSQL Database  │
              │ • Usuários           │
              │ • Transações         │
              │ • Sessões            │
              │ • Analytics          │
              └──────────────────────┘
```

### Por que Híbrido?

1. **Responsividade:** Bot em thread permite que o Flask não fique bloqueado por polling
2. **Separação de Responsabilidades:** Telegram (I/O bound) vs Web (CPU bound)
3. **Escalabilidade:** Ambos podem falhar independentemente sem derrubar o outro
4. **Debugging:** Fácil de rastrear problemas em cada camada

### Fluxo de Inicialização

1. **Startup (`__main__`):**
   - Carrega variáveis de ambiente
   - Inicializa banco de dados (migrations SQL)
   - Configura OCR (Google Vision credentials)
   - Inicia thread do bot (modo `LOCAL_DEV`)
   - Inicia Flask app no main thread

2. **Bot Thread:**
   - `ApplicationBuilder` com Groq token
   - Registra handlers padrão (text, voice, photo, pdf, callbacks)
   - **NOVO:** Global callbacks para handlers que iniciam fora de ConversationHandler
     - Ex: `CallbackQueryHandler(fatura_confirm, pattern="^fatura_")` para PDF faturas
   - Inicia `app.run_polling()`

3. **Main Thread:**
   - Registra rotas Flask (`/api/telegram/auth`, `/api/miniapp/*`, `/webapp`)
   - Inicia APScheduler para jobs agendados
   - Executa `app.run(host='0.0.0.0', port=8080)`

---

## 🔧 Componentes Principais

### 1. Bot Telegram (`gerente_financeiro/`)

#### **a) Roteador Alfredo (`ia_handlers.py`)**

Router inteligente que usa Groq LLaMA 3.x com function-calling:

```python
# Exemplo de chamada
await processar_mensagem_com_alfredo(update, context)
# Alfredo decide entre:
# - process_manual_entry: "Gastei 50 no mercado"
# - process_voice_input: Transcricao de áudio
# - process_question: "Quanto gastei com comida?"
# - process_goal_update: "Quero economizar 1000"
```

**Responsabilidades:**
- Classificação de intenção do usuário
- Chamada a handlers apropriados
- Logging de analytics
- Fallback para handlers legacy (se necessário)

#### **b) Handlers por Tipo de Mídia**

| Handler | Entrada | Processamento | Saída |
|---------|---------|---------------|-------|
| **Text** | Mensagem de texto livre | NLP com Alfredo → extração de valor, categoria, data | Confirmar ou corrigir |
| **Voice** | `filters.VOICE` | Transcrição (Telegram API) → Gemini/Groq | Lançamento criado |
| **Photo** | `filters.PHOTO` | OCR (Google Vision/Gemini) → detecção de nota fiscal | Validação manual |
| **Document** | PDFs | Google Vision OCR + PDF parsing | Importação de fatura |
| **Callback** | Botões inline | Validação de token + contexto | Resposta inline |

#### **c) OCR Robusto (`ocr_handler.py`)**

```
Foto/PDF recebida
       ↓
Google Vision (primary)
       ↓ (falha)
Gemini Vision (fallback)
       ↓
Extração: valor, descrição, data, fornecedor
       ↓
Validação com Gemini
       ↓
Persistência no DB
```

#### **d) Botões MiniApp com URL Normalization**

- **Instância única de verdade** para URL geração (`build_miniapp_url`, `_get_fatura_webapp_url`)
- **Normalization robusta:**
  - Detect env fallback: `RENDER_EXTERNAL_URL` se `DASHBOARD_BASE_URL` não houver
  - **HTTPS enforcement** para non-localhost (Telegram WebApp requirement)
  - Query params: cache-bust `v=timestamp` + page routing
- **Keyboard integration:** Botões inline respeitam timeouts Telegram (<15s)
- **Fatura edits:** Global `CallbackQueryHandler` captura callbacks mesmo fora de ConversationHandler

#### **e) Handlers Específicos**

- **manual_entry_handler:** Conversa passo-a-passo para registrar gastos
- **editing_handler:** Modificação de transações (valor, categoria, data)
- **metas_handler:** Criação/ atualização de metas com check-in mensal
- **agendamentos_handler:** Configuração de parcelas e recorrências
- **relatorio_handler:** Geração de relatórios em PDF
- **gamification_handler:** Cálculo de XP, levels, streaks
  - **NEW:** Feature names em português legível (não mais technical actions)
  - Mapeamento automático: `LANCAMENTO_CRIADO` → `Lançamentos realizados`
  - Display no game profile com contadores de interações
- **investment_handler:** Portfólio de investimentos e patrimônio líquido

### 2. MiniApp (`templates/miniapp.html` + `analytics/dashboard_app.py`)

#### **Frontend Otimizado**

```html
<!-- Telegram WebApp Integration -->
<script src="https://telegram.org/js/telegram-web-app.js"></script>

<!-- Features -->
- Telegram WebApp API (`Telegram.WebApp.initData` validation)
- Sessões stateless: base64(user_id|exp_ts|hmac_sig)
- Auto re-auth em 401: refresh de token + retry
- Non-blocking UI: abre imediatamente, carrega data em background
```

**Endpoints Otimizados:**

| Endpoint | Método | Descrição | Cache |
|----------|--------|-----------|-------|
| `/api/telegram/auth` | POST | Valida `initData`, cria sessão sign | 5min |
| `/api/miniapp/overview` | GET | Visão geral: saldo, gastos, metas | 2min |
| `/api/miniapp/history` | GET | Histórico paginado de transações | 1min |
| `/api/miniapp/configuracoes` | GET | Perfil e preferências de notificação | 10min |
| `/api/miniapp/metas` | GET | Metas, progresso, check-in | 5min |
| `/api/miniapp/agendamentos` | GET | Recorrências, parecel próximas | 2min |

> No modo Zero Setup, o MiniApp não expõe endpoint de contas/cartões (`/api/miniapp/contas`).

#### **Performance Strategies**

1. **Disable IA on Hot Path:** `MINIAPP_AI_INSIGHT_ENABLED=false` (default)
   - Overview não chama Gemini/Groq por padrão
   - Fallback local para texto de insight
   - Reduz latência de 30s → <2s

2. **Sessões Stateless:**
   - Não dependem de in-memory dict
   - Sobrevivem restarts e multi-instance deploys
   - HMAC-SHA256 validation na cada requisição
   - Expiração automática em token

3. **UI Não-Bloqueante:**
   ```javascript
   // ❌ Antes: bloqueava UI
   await Promise.allSettled([loadHome(), loadHistory(), loadConfig()])
   
   // ✅ Agora: abre imediatamente
   Promise.allSettled([loadHome(), loadHistory(), loadConfig()])  // fire-and-forget
   switchTabByName('home')  // UI disponível NOW
   ```

4. **Auto Re-auth:**
   ```javascript
   // Se receber 401
   if (response.status === 401) {
     await reauthenticateSession()  // refresh silencioso
     return fetch(...) // retry
   }
   ```

#### **Alfredo Cards (IA Insights)**

- **Visibilidade garantida:** Dark gradient background override para CSS `.glass-card`
- **Renderização em dois lugares:**
  - Home insight: Análise do dia (saldo, padrão de gasto)
  - Game profile: Nota motivacional personalizada
- **Color scheme:** Radial gradient + linear background com white text para contraste em todos os temas
- Carregamento lazy com placeholder

### 3. Backend Flask (`analytics/dashboard_app.py`)

```python
# Session Management
def _miniapp_session_secret():
    """Derive HMAC key from env"""
    return os.getenv('MINIAPP_SESSION_SECRET', TELEGRAM_TOKEN).encode()

def _create_miniapp_session(user_id):
    """Generate signed stateless token"""
    exp_ts = int(time.time()) + SESSION_LIFETIME
    payload = f"{user_id}|{exp_ts}"
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return base64.b64encode(f"{payload}|{sig}".encode()).decode()

def _get_session(session_id):
    """Validate signed token"""
    try:
        decoded = base64.b64decode(session_id.encode()).decode()
        payload, sig = decoded.rsplit('|', 1)
        user_id, exp_ts = payload.split('|')
        
        expected_sig = hmac.new(...).hexdigest()
        assert sig == expected_sig, "Invalid signature"
        assert int(exp_ts) > time.time(), "Expired"
        
        return {'user_id': int(user_id), 'exp_ts': int(exp_ts)}
    except:
        return None

# Feature Names Mapping (Gamification)
def _friendly_feature_name(action: str):
    """Map technical action keys to user-readable Portuguese labels"""
    mapping = {
        'PRIMEIRA_INTERACAO_DIA': 'Primeira interação do dia',
        'INTERACAO_BOT': 'Uso do bot no chat',
        'LANCAMENTO_CRIADO': 'Lançamentos realizados',
        'LANCAMENTO_EDITADO': 'Edições de transações',
        'MONTH_TURN_BLUE': 'Mês fechado no azul',
        'STREAK_DIAS': 'Dias de registro consecutivo',
        # ... (13 total mappings)
    }
    return mapping.get(action, action)
```

### 4. Analytics PostgreSQL

```sql
-- Tabelas principais
- users: ID, username, perfil e preferências
- lancamentos: ID, user_id, valor, categoria, data, criado_em
- transacoes_agendadas: parcelas, frequência, status
- analytics_events: comando, sucesso, tempo_execução
- metas: user_id, alvo, período, progresso
- investimentos: portfólio, cotações atualizadas
```

---

## 📊 Fluxo de Dados

### Caso 1: Entrada de Texto (`"Gastei 50 no mercado"`)

```
1. Telegram → bot.py (thread)
   Message recebida

2. dispatch_message_handler()
   Tipo: TEXT → processar_mensagem_com_alfredo

3. Alfredo (Groq)
   Intent: MANUAL_ENTRY
   Campos: valor=50, categoria=Alimentação, data=hoje

4. Persistência
   INSERT lancamentos(user_id, valor, categoria, data)

5. Response
   ✅ "Lançamento registrado: R$50 em Alimentação"

6. Analytics
   track_command('manual_entry', success=True, time_ms=234)
```

### Caso 2: Entrada de Foto (Nota Fiscal)

```
1. Telegram → bot.py (thread)
   Photo recebida

2. photo_handler()
   Download => save to /tmp

3. OCR
   Google Vision (primary)
      ↓ (falha com timeout)
   Gemini Vision Pro (fallback)
   => {valor: 87.50, descricao: "Mercado X", data: 05/04}

4. Exibir para Confirmação
   "Achei: R$87.50 em Mercado X. Confirma?"
   [Botão: Confirmar] [Botão: Editar] [Botão: Cancelar]

5. Usuário clica: Confirmar
   callback_handler() => INSERT

6. Response
   ✅ Transação salva + emoji de celebração
```

### Caso 3: Dashboard Web Load

```
1. Usuário clica em "Dashboard" no MiniApp
   GET /webapp

2. Telegram.WebApp.initData validation
   POST /api/telegram/auth
   → cria sessão signed

3. Frontend carrega com non-blocking flow:
   
   UI abre imediatamente (sem spinner)
       ↓
   Background: Promise.allSettled([
     GET /api/miniapp/overview        (2s)
     GET /api/miniapp/history         (1s)
     GET /api/miniapp/configuracoes   (0.5s)
   ])
   
4. Conforme cada requisição completa:
   - Overview: renderiza cards principais
   - History: popula tabela com transações
   - Config: aplica preferências de perfil e notificação

5. Usuário vê:
   - Instantâneo: Layout + menus + abas vazias
   - 0.5s: Configurações
   - 1s: Histórico de transações
   - 2s: Cards de overview (saldo, gastos mês)
```

---

## 🛠️ Tecnologias

### Backend

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| **Runtime** | Python 3.11+ | Core da aplicação |
| **Web Framework** | Flask 2.x | API REST + dashboard |
| **Bot Framework** | python-telegram-bot 22.x | Integração Telegram |
| **Database** | PostgreSQL 14+ | Persistência |
| **ORM** | SQLAlchemy 2.x | Query builder |
| **ASGI** | gunicorn | Production server |
| **Jobs** | APScheduler | Tarefas agendadas |
| **PDF** | ReportLab | Geração de relatórios |

### IA & Vision

| Serviço | Provedor | Uso |
|---------|----------|-----|
| **Router** | Groq (LLaMA 3.x) | Classificação de intenção |
| **Vision** | Google Vision API | OCR primary |
| **Fallback Vision** | Gemini 2.5 Flash | OCR fallback |
| **Analytics** | PostgreSQL + pandas | Insights |

### Frontend

| Tecnologia | Uso |
|-----------|-----|
| **HTML5** | Estrutura |
| **CSS3 + Tailwind** | Styling responsive |
| **Chart.js** | Gráficos em tempo real |
| **Telegram WebApp API** | Integração com Telegram |
| **Vanilla JavaScript** | Lógica frontend |

### Infrastructure

| Componente | Opção |
|-----------|-------|
| **Deployment** | Docker (Render.com) |
| **CI/CD** | GitHub Actions (futura) |
| **Monitoring** | Logs JSON (Render) |
| **Secrets** | Environment variables |

---

## 🚀 Funcionalidades

### 🤖 Zero Setup & Chat Inteligente

- [x] **Lançamentos sem Atrito:** Aceita texto livre, áudios (transcritos via Groq Whisper), fotos de notas fiscais (OCR) e faturas em PDF.
- [x] **O Cérebro do Alfredo (AI-First):** Motor de inteligência que prioriza o processamento via LLM (Groq/Gemini). Diferente de bots comuns, o Alfredo possui visão periférica de todo o seu mês, analisando padrões, sugerindo cortes e respondendo com a sofisticação de um mordomo financeiro de elite.
- [x] **Contexto Rico:** A IA agora recebe o breakdown completo de categorias, gastos de ontem, metas ativas e histórico expandido (20+ transações) em cada interação.
- [x] **Microlearning:** Manuais curtos e temáticos acessíveis pelo chat, substituindo "textões" de ajuda engessados.

### 📱 MiniApp (Sua Central de Controle)

- [x] **Dashboard em Tempo Real:** Gráficos interativos de fluxo de caixa, despesas por categoria e evolução patrimonial.
- [x] **Gestão Completa:** Edição rápida de histórico de lançamentos, gestão de cartões/contas e personalização de perfil de investidor.
- [x] **Controle de Notificações:** Toggle em tempo real para ativar/desativar lembretes automáticos.

### 🎮 Gamificação (O Jogo da Riqueza)

- [x] **XP e Níveis:** De "Caderneta Zerada" (Nível 1) a "Além do Budget" (Nível 16+).
- [x] **Missões e Conquistas:** Missões Diárias (ex: *Caffeine Tracker*), Semanais (ex: *Semana Azul*) e bônus permanentes por consistência (Streaks).
- [x] **Ranking Global:** Competição em tempo real mostrando os líderes de XP do mês (com premiação mensal automática).

### 🔔 Assistente Proativo & Planejamento

- [x] **Agendamentos com 1-Clique:** Notificações automáticas na madrugada para contas do dia, com botão nativo "✅ Dar baixa".
- [x] **Metas Inteligentes:** A IA calcula o aporte necessário e o bot faz o check-in mensalmente para garantir seu progresso.
- [x] **Wrapped Anual:** Retrospectiva automatizada todo dia 31 de dezembro mostrando as curiosidades do ano.

### Relatórios & Visualização

- [x] **Gráficos:** Pizza, barras, linha, área, composições
- [x] **Dashboard Web:** Tempo real com MiniApp
- [x] **Relatórios PDF:** Mensais, customizáveis
- [x] **Wrapped Anual:** Retrospectiva automatizada

### Engajamento

- [x] **Gamificação:** XP, níveis, ranking, streaks
  - Tela de perfil gamer completa com resgate de missões
  - Alfredo cards baseados no momento do usuário
- [x] **Notificações:** Diárias (vencimentos de contas), check-in de metas, e alertas
- [x] **Suporte:** Fluxo de contato integrado

---

## ⚡ Performance & Confiabilidade

### Otimizações de Performance

#### 1. **IA Hot Path Disabled by Default**
```bash
MINIAPP_AI_INSIGHT_ENABLED=false  # Default em produção
```
- Desativa chamadas a Gemini/Groq em `/api/miniapp/overview`
- Reduz latência de 30s → <2s
- Fallback local para texto genérico
- Pode ser ativado se performance melhorar

#### 2. **Sessões Stateless**
- Baseado em HMAC-SHA256
- Não requer lookup em banco
- Válido em múltiplas instâncias
- Expiração automática (4 horas)

#### 3. **UI Não-Bloqueante**
```javascript
// MiniApp abre instantaneamente
// Dados carregan em background
// Se uma chamada falha, não bloqueia UI
```

#### 4. **Query Optimization**
- Índices em `user_id`, `data`, `categoria`
- Paginação em histórico (limit 20)
- Caching com TTL em endpoints

### Confiabilidade

#### 1. **Optional Imports com Fallback**
```python
# Se análises_ia falhar, bot continua rodando
try:
    from .analises_ia import get_analisador
except:
    def get_analisador():
        raise RuntimeError("Analytics IA disabled")
```

#### 2. **Auto Re-authentication**
```javascript
// Se sessão expirar (401)
if (response.status === 401) {
    await reauthenticateSession()  // silencioso
    return fetch(...)  // retry automático
}
```

#### 3. **Error Handling**
- Logging estruturado em JSON
- Graceful degradation
- User-friendly error messages
- Retry automático em I/O

#### 4. **Database Failover**
- Connection pooling (SQLAlchemy)
- Migrations automáticas na inicialização
- Rollback em caso de erro

---

## 📦 Deployment

### 1. Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Variables
export TELEGRAM_TOKEN="..."
export GROQ_API_KEY="..."
export DATABASE_URL="postgresql://..."
export CONTACOMIGO_MODE=LOCAL_DEV

# Run
python app.py  # ou: python launcher.py
```

### 2. Production (Render.com)

```bash
# Dockerfile automaticamente detecta requirements.txt
# push para main branch → Render rebuild

# Environment variables
TELEGRAM_TOKEN
GROQ_API_KEY
GOOGLE_VISION_CREDENTIALS_JSON  # base64 encoded
DATABASE_URL  # PostgreSQL
MINIAPP_AI_INSIGHT_ENABLED=false
CONTACOMIGO_MODE=PRODUCTION
```

### 3. Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["gunicorn", "-c", "gunicorn_config.py", "launcher:app"]
```

### 4. Variáveis de Ambiente

```bash
# Telegram
TELEGRAM_TOKEN              # Required: Bot token
TELEGRAM_WEBHOOK_BASE       # Optional: para webhook (unused - polling)

# IA/APIs
GROQ_API_KEY               # Router Alfredo
GEMINI_API_KEY             # Fallback Vision
GOOGLE_VISION_CREDENTIALS_JSON  # OCR primary

# Database
DATABASE_URL               # PostgreSQL connection

# App Config
CONTACOMIGO_MODE          # LOCAL_DEV ou PRODUCTION
MINIAPP_AI_INSIGHT_ENABLED # true/false (default false)
SESSION_LIFETIME           # segundos (default 14400)

# Emails
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
SENDER_EMAIL
EMAIL_RECEIVER
PIX_KEY
```

---

## 💻 Desenvolvimento Local

### Setup Inicial

```bash
# 1. Clone e setup
git clone https://github.com/henrique-jfp/ContaComigoApp.git
cd MaestroFin
python -m venv venv
source venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Variáveis (.env)
cat > .env << EOF
TELEGRAM_TOKEN=YOUR_TOKEN
GROQ_API_KEY=YOUR_KEY
GEMINI_API_KEY=YOUR_KEY
GOOGLE_VISION_CREDENTIALS_JSON='{"type":"service_account",...}'
DATABASE_URL=postgresql://user:pass@localhost:5432/contacomigo
CONTACOMIGO_MODE=LOCAL_DEV
EOF

# 4. Database (local PostgreSQL)
createdb contacomigo
python -c "from database.database import create_tables; create_tables()"

# 5. Run
python app.py
```

### Estrutura de Pastas

```
MaestroFin/
├── bot.py                         # Entry point bot
├── app.py                         # Entry point Flask
├── launcher.py                    # Orchestrator (bot + Flask)
├── requirements.txt               # Dependencies
│
├── gerente_financeiro/            # Bot logic
│   ├── ia_handlers.py            # Alfredo router
│   ├── handlers.py               # Main dispatcher
│   ├── ocr_handler.py            # Vision integration
│   ├── manual_entry_handler.py   # Guided entry
│   ├── editing_handler.py        # Transaction edit
│   ├── metas_handler.py          # Goals
│   ├── agendamentos_handler.py   # Recurring
│   ├── investments_handler.py    # Portfolio
│   ├── relatorio_handler.py      # PDF reports
│   ├── gamification_*.py         # XP/levels
│   └── ...
│
├── analytics/                     # Dashboard backend
│   ├── dashboard_app.py          # Flask routes
│   ├── bot_analytics_postgresql.py  # Analytics
│   └── metrics.py
│
├── templates/                     # Frontend
│   ├── miniapp.html              # MiniApp UI
│   ├── dashboard_*.html          # Dashboard views
│   └── ...
│
├── database/                      # DB layer
│   ├── database.py               # SQLAlchemy setup
│   └── models.py                 # ORM models
│
├── migrations/                    # SQL migrations
│   ├── 002_create_pluggy_tables.sql
│   ├── 003_create_investments_table.sql
│   └── 004_add_lancamento_origem.sql
│
├── open_finance/                  # Open Finance (future)
│   ├── pluggy_client.py
│   └── ...
│
└── static/                        # CSS/assets
    └── dashboard_*.css
```

### Debug & Logs

```bash
# Ver logs em tempo real
tail -f debug_logs/bot.log

# Debug OCR
/debugocr  # comando no Telegram

# Debug Dashboard
/dashboarddebug  # comando no Telegram

# Logs estruturados (Render)
# Aparecem em JSON no Render dashboard
```

---

##  Correções Recentes (Abril 2026)

### Operação "Alfredo Super Inteligente" - 08 de Abril de 2026
**Problema:** Alfredo estava se comportando de forma "fria" e limitada, respondendo com resumos locais estáticos que bloqueavam a inteligência da IA.
**Solução:**
- **AI-First Architecture:** Removidas interceptações locais para saldo, metas e gastos. Agora, a IA processa essas perguntas com contexto total.
- **Contexto Enriquecido:** Adicionado breakdown de categorias do mês atual, gastos de ontem e prazos de metas no prompt do sistema.
- **Nova Persona:** Refinado o tom de voz para ser mais profissional, empático e "mordomo financeiro".
- **Formatação Premium:** Implementado uso mandatório de `<code>` para valores e `<b>` para destaques, garantindo legibilidade superior no Telegram.
- **Robustez em Metas:** Adicionado suporte a `data_meta` via IA e maior flexibilidade no reconhecimento de valores alvo.

**Status:** ✅ Implantado e 100% Operacional

### Commit `f25dba2` - Estabilização de callbacks de fatura
**Problema:** Botões MiniApp e botão de editar fatura não respondiam (BOT_RESPONSE_TIMEOUT)
**Causa Raiz:** 
- PDFs de fatura processados fora de ConversationHandler
- Callbacks inline (`fatura_editar_inline`) não tinham rota global
- Telegram enfileira resposta indefinidamente se handler não encontrado (~15s timeout)

**Solução:**
- Adicionado global `CallbackQueryHandler(fatura_confirm, pattern="^fatura_")` em `bot.py`
- URL normalization robusta em `build_miniapp_url()` e `_get_fatura_webapp_url()`
- HTTPS enforcement para non-localhost (Telegram WebApp requirement)
- Fallback para `RENDER_EXTERNAL_URL` se `DASHBOARD_BASE_URL` não definida

**Status:** ✅ Resolvido e testado

### Commit `a0a25c9` - Visibilidade de Alfredo cards e feature names
**Problema 1:** Comentários do Alfredo invisíveis em todos os lugares
**Causa Raiz:** `.glass-card` CSS forcing light backgrounds mesmo em cards que precisam de dark theme

**Solução 1:**
- Criado `.alfredo-card` CSS variant com dark gradient background
- Aplicado em dois cards: home insight + game profile note
- Texto branco com contraste garantido

**Problema 2:** Feature names técnicos na tela de game profile
**Causa Raiz:** API retornava raw `XpEvent.action` keys (ex: `LANCAMENTO_CRIADO`, `INTERACAO_BOT`)

**Solução 2:**
- Adicionada função `_friendly_feature_name()` em `dashboard_app.py`
- Mapeamento de 13+ actions para labels em português legível
- API retorna `feature` (friendly), `raw_feature` (technical), `interactions` (count)
- Frontend exibe nome legível ao usuário

**Status:** ✅ Implementado e validado

---

## �📈 Roadmap & Próximas Features

- [ ] Web scraping para sincronização de contas bancárias
- [ ] Machine learning para categorização automática
- [ ] Export em múltiplos formatos (CSV, Excel)
- [ ] Integração com CRM
- [ ] Dark mode para MiniApp
- [ ] PWA (Progressive Web App)
- [ ] Backup automático em cloud

---

## 📄 Licença

[LICENSE](LICENSE)

## 🤝 Contribuições

Issues e PRs são bem-vindos!

## 📞 Suporte

- **Telegram:** Use o comando `/contato` no bot
- **GitHub Issues:** Para bugs e feature requests

---

**Última atualização:** 08 de abril de 2026  
**Versão:** 2.1 (Alfredo Intelligence Update)
:** 2.1 (Alfredo Intelligence Update)
