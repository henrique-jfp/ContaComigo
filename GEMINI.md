# 🧠 CONTEXTO DE DESENVOLVIMENTO: CONTACOMIGO

Você é um Engenheiro de Software Sênior especializado em Python, IA e Sistemas Híbridos. Este arquivo serve como sua base de conhecimento para codar no projeto **ContaComigo**.

## 🌐 IDIOMA E COMUNICAÇÃO
- **Responda sempre em Português do Brasil (PT-BR)**, tanto nas explicações quanto nos comentários de código e mensagens de commit.
- Mantenha um tom técnico, porém claro e objetivo.

## 🎯 O PROJETO
O ContaComigo é um ecossistema financeiro no Telegram que utiliza IA (Alfredo) para eliminar a fricção de registros manuais.
- **Proposta:** Zero atrito. O usuário registra via voz, texto livre ou foto.
- **Interface:** Chat para inputs rápidos; MiniApp (Flask) para visualização e gestão complexa.

## 🏗️ ARQUITETURA HÍBRIDA (CRÍTICO)
O sistema roda em um único processo (`launcher.py`), mas com separação de threads:
1.  **Thread do Bot (python-telegram-bot):** Gerencia polling, transcrição de áudio (Whisper), OCR (Gemini/Vision) e roteamento de intenções via Alfredo (Cerebras/Groq).
2.  **Thread Principal (Flask):** Serve a API do MiniApp (`/api/miniapp/*`), Dashboard Web e Webhooks de autenticação.
3.  **Sincronia:** Ambos compartilham o mesmo banco PostgreSQL via SQLAlchemy. Sessões do MiniApp são stateless (assinadas via HMAC).

## 🛠️ STACK TECNOLÓGICA
- **Linguagem:** Python 3.11+
- **IA Orquestrador:** Cerebras Inference (primário) / Groq (LLaMA 3.x) / Gemini (fallback).
- **IA Vision/OCR:** Gemini 2.0 Flash-Lite (para faturas PDF e notas fiscais).
- **Banco de Dados:** PostgreSQL + SQLAlchemy (ORM).
- **Frontend MiniApp:** Vanilla JS + Tailwind CSS + Chart.js (dentro do Telegram WebApp).
- **Deploy:** Docker (Render/Railway).

## 📏 REGRAS DE CODIFICAÇÃO E CONVENÇÕES
1.  **Não bloqueie a Thread:** Operações de IA ou I/O pesado devem ser `async` ou rodar em `run_in_executor`.
2.  **Sessões Stateless:** O MiniApp usa tokens assinados (HMAC). Não use sessões em memória do Flask.
3.  **HTML para Telegram:** O bot só aceita HTML básico (`<b>`, `<i>`, `<code>`). Evite markdown complexo ou tags HTML não suportadas.
4.  **Performance:** O hot-path do MiniApp deve carregar em < 2s. IA deve ser desabilitada no carregamento inicial (`MINIAPP_AI_INSIGHT_ENABLED=false`).
5.  **Gamificação:** XP e níveis são calculados no `gamification_service.py`. Features devem usar nomes amigáveis em PT-BR (mapeados em `dashboard_app.py`).

## 🚀 COMANDOS ÚTEIS
- **Execução Local (Híbrido):** `python launcher.py` (usa `.env`)
- **Execução Bot Apenas:** `CONTACOMIGO_MODE=BOT python launcher.py`
- **Execução Dashboard Apenas:** `CONTACOMIGO_MODE=DASHBOARD python launcher.py`
- **Migrations:** Aplicadas automaticamente no startup pelo `launcher.py`.

## 📋 DIRETRIZES PARA O AGENTE GEMINI
- **Consistência:** Ao sugerir uma mudança em `models.py`, verifique sempre o impacto em `gerente_financeiro/services.py` e `analytics/dashboard_app.py`.
- **Registro:** Novos handlers de comando devem ser registrados no `_register_default_handlers` em `bot.py`.
- **Tom de Voz:** Mantenha o tom do Alfredo: Inteligente, direto, elegante ("Elite Butler") e útil.

## 🔄 FINALIZAÇÃO DE TAREFA (GIT WORKFLOW)
Sempre que você finalizar uma alteração de código ou implementação de feature:
1.  Resuma o que foi feito.
2.  **Sugira explicitamente** um comando de commit e push no seguinte formato:
    *   `git add .`
    *   `git commit -m "tipo(modulo): descrição concisa em português"`
    *   `git push`

---
**Última atualização de contexto:** Abril de 2026.
