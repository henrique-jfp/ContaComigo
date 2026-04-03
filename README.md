<div align="center">
  <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
  <img src="https://img.shields.io/badge/AI-Gemini_2.5_Flash-F4B400?style=for-the-badge&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="Postgres" />
</div>

<h1 align="center">MaestroFin</h1>

> **Assistente financeiro no Telegram com IA multimodal, OCR e automacao de lancamentos.**

---

## Visao geral

O **MaestroFin** eh um bot no Telegram para controle financeiro pessoal com foco em **baixo atrito**.
O usuario registra gastos por texto, audio ou foto e recebe analises em linguagem natural.

Principais entradas:
- Texto natural: "Gastei 55 reais no mercado".
- Audio (mensagem de voz): transcricao e extracao automatica.
- Foto/PDF de nota fiscal: OCR com validacao.

Saidas:
- Insights personalizados.
- Relatorios em PDF.
- Dashboard web.

---

## Funcionalidades

- **Lançamento por audio (frictionless):** processa `filters.VOICE` com Gemini 2.5 Flash.
- **OCR robusto:** Google Vision com fallback para Gemini Vision.
- **Memoria comportamental:** resumo semanal do perfil do usuario para personalizar respostas.
- **Conversa natural:** analises e comandos por linguagem humana.
- **Gamificacao:** XP, niveis e streaks.
- **Metas e agendamentos:** objetivos financeiros e despesas recorrentes.
- **Dashboard e relatorios:** HTML e PDF.

---

## Stack principal

- **Python 3.12+**
- **python-telegram-bot 22.x**
- **google-generativeai** (Gemini)
- **google-cloud-vision**
- **SQLAlchemy 2.x**
- **PostgreSQL**
- **Jinja2 + WeasyPrint**

---

## Arquitetura (resumo)

Para detalhes, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

- [bot.py](bot.py): ponto de entrada do bot.
- [gerente_financeiro/handlers.py](gerente_financeiro/handlers.py): fluxo principal.
- [gerente_financeiro/audio_handler.py](gerente_financeiro/audio_handler.py): audio e Gemini.
- [gerente_financeiro/ocr_handler.py](gerente_financeiro/ocr_handler.py): OCR.
- [gerente_financeiro/ai_memory_service.py](gerente_financeiro/ai_memory_service.py): memoria comportamental.
- [gerente_financeiro/prompt_manager.py](gerente_financeiro/prompt_manager.py): prompts e templates.

---

## Como rodar localmente

### Requisitos

- Python 3.12+
- PostgreSQL 14+
- Credenciais do Telegram e Google (Vision/Gemini)

### Instalacao

```bash
git clone https://github.com/henrique-jfp/MaestroFin.git
cd MaestroFin

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Variaveis de ambiente

Defina as variaveis abaixo (arquivo `.env` em dev ou variaveis do sistema):

```
TELEGRAM_TOKEN=
GEMINI_API_KEY=
GEMINI_MODEL_NAME=gemini-2.5-flash
DATABASE_URL=
GOOGLE_APPLICATION_CREDENTIALS=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
SENDER_EMAIL=
EMAIL_RECEIVER=
PIX_KEY=
```

Observacoes:
- `GEMINI_MODEL_NAME` aceita valores listados em [config.py](config.py).
- `GOOGLE_APPLICATION_CREDENTIALS` pode ser caminho absoluto ou relativo.

### Executando

```bash
python bot.py
```

Abra o bot no Telegram e envie `/start`.

---

## Jobs e memoria comportamental

O job `job_atualizar_perfis_ia` roda semanalmente e atualiza o campo `perfil_ia`.
Veja [gerente_financeiro/ai_memory_service.py](gerente_financeiro/ai_memory_service.py).

---

## Licenciamento

Este projeto usa **Licenca Dupla (Dual License)**:

| Tipo de uso | Status | Detalhes |
|---|---|---|
| Portfolio/Educacao | Gratuito | Estudar, demonstrar, rodar localmente |
| Comercial | Pago | Producao, white-label, monetizacao |

Contato para licenca comercial: **henriquejfp.dev@gmail.com**

---

## Contato

- Telegram: [@MaestroFinBot](https://t.me/MaestroFinBot)
- LinkedIn: [henrique-jfp](https://linkedin.com/in/henrique-jfp)

---

<div align="center">

Se o projeto ajudou, deixe uma estrela.

</div>
