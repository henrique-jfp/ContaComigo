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
O sistema roda em um único processo, mas com separação de threads:
1.  **Thread do Bot (python-telegram-bot):** Gerencia polling, transcrição de áudio, OCR e roteamento de intenções via Alfredo (Groq).
2.  **Thread Principal (Flask):** Serve a API do MiniApp, Dashboard Web e Webhooks de autenticação.
3.  **Sincronia:** Ambos compartilham o mesmo banco PostgreSQL via SQLAlchemy.

## 🛠️ STACK TECNOLÓGICA
- **Linguagem:** Python 3.11+
- **IA Roteador:** Groq (LLaMA 3.x) para function calling.
- **IA Vision/Parsing:** Gemini 2.5 Flash (OCR de notas e faturas PDF).
- **Banco de Dados:** PostgreSQL + SQLAlchemy (ORM).
- **Frontend:** Vanilla JS + Tailwind CSS + Chart.js (dentro do Telegram WebApp).

## 📏 REGRAS DE CODIFICAÇÃO
1.  **Não bloqueie a Thread:** Operações de IA ou I/O pesado devem ser `async` ou rodar em `run_in_executor`.
2.  **Sessões Stateless:** O MiniApp usa tokens assinados (HMAC). Não use sessões em memória.
3.  **HTML para Telegram:** O bot só aceita HTML básico (`<b>`, `<i>`, `<code>`).
4.  **Performance:** O hot-path do MiniApp deve carregar em < 2s.

## 📋 DIRETRIZES PARA O GEMINI CLI
- **Idioma:** Todas as suas respostas, explicações e sugestões devem ser em **Português**.
- **Consistência:** Antes de sugerir uma mudança em `models.py`, verifique o impacto em `services.py`.
- **Registro:** Ao criar novos Handlers, registre-os no `_register_default_handlers` dentro de `bot.py`.
- **Tom de Voz:** Mantenha o tom do Alfredo: Inteligente, direto e útil.

## 🔄 FINALIZAÇÃO DE TAREFA (GIT WORKFLOW)
Sempre que você finalizar uma alteração de código ou implementação de feature:
1.  Resuma o que foi feito.
2.  **Sugira explicitamente** um comando de commit e push no seguinte formato:
    *   `git add .`
    *   `git commit -m "feat(modulo): descrição concisa em português"`
    *   `git push`

---
**Última atualização de contexto:** Abril de 2026.
