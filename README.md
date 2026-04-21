# 🚀 ContaComigo: Ecossistema Financeiro Híbrido no Telegram

ContaComigo é uma plataforma financeira inovadora que combina a conveniência de um **assistente de IA no Telegram** com um **dashboard web completo**, projetado para otimizar sua vida financeira com zero atrito. Através do nosso assistente "Alfredo", você gerencia suas finanças, obtém insights inteligentes e explora seu potencial financeiro com gamificação.

## ✨ Features Principais

*   **Alfredo: Assistente de IA Avançado:**
    *   Processamento de linguagem natural e áudio powered by **Groq/Cerebras** e **Gemini API**.
    *   Entendimento contextual para transações, faturas, e dúvidas financeiras.
    *   Respostas rápidas e inteligentes para otimizar seu dia a dia.

*   **Integração Open Finance (Aba "Contas"):**
    *   Sincronização segura e automática via Pierre API para uma visão consolidada.
    *   Interface integrada diretamente na navegação principal, eliminando fricção.
    *   Gestão de saldos, transações e faturas com visual unificado.

*   **MiniApp Premium (Visual Private Banking):**
    *   Interface sofisticada com tema **Premium Grená & Ouro**.
    *   Sidebar inteligente no desktop para navegação fluida e side-by-side.
    *   Gráficos de última geração:
        *   **Caminho do Dinheiro (Sankey SVG):** Visualização orgânica e dinâmica do fluxo financeiro.
        *   **Mapa de Calor (Heatmap):** Calendário real de gastos para identificação de padrões diários.
    *   Experiência "zero-friction" otimizada para dispositivos móveis e desktop.

*   **Gamificação Financeira (XP & Níveis):**
    *   Sistema de XP e níveis para incentivar o bom gerenciamento financeiro.
    *   Missões e desafios para aprendizado e engajamento.
    *   Rankings e recompensas para os usuários mais ativos e organizados.

*   **Dashboard Web Completo (Flask & Tailwind CSS):**
    *   Interface visual rica e profissional para análise detalhada de suas finanças.
    *   Visualização de gráficos, relatórios, metas e faturas.
    *   Ferramentas de gestão e configuração avançadas.
    *   Estilização moderna, incluindo um tema "Cyberpunk" (`dashboard_cyberpunk.css`).

*   **Processamento Inteligente de Faturas:**
    *   Envio de faturas em PDF por mensagem para extração automática de dados via OCR (Google Vision) e IA.
    *   Categorização automática de despesas e sugestões de melhorias.

## 🏗️ Arquitetura

ContaComigo opera em um **único processo orquestrado** (`launcher.py`), garantindo eficiência e escalabilidade, com uma separação clara de responsabilidades:

1.  **Thread do Bot (Telegram):** Responsável por interagir com o usuário via Telegram, processar comandos, gerenciar conversas (incluindo OCR e IA com Gemini), e executar ações em tempo real. Utiliza `python-telegram-bot`.
2.  **Thread Principal (Flask API):** Hospeda a API do MiniApp (`/api/miniapp/*`) e o Dashboard Web (definido em `analytics.dashboard_app`). Gerencia as requisições HTTP, serve a interface do usuário e se comunica com o backend.
3.  **Processos de Background/Jobs:** Tarefas agendadas para sincronização bancária (via Pierre API), geração de relatórios, e outras operações assíncronas.

O estado da aplicação e a sincronia são mantidos através de um banco de dados **PostgreSQL**. Sessões do MiniApp são stateless, utilizando HMAC para segurança.

## 🛠️ Stack Técnica

*   **Linguagem Principal:** Python 3.11+
*   **Framework Web:** Flask
*   **API do Telegram:** `python-telegram-bot`
*   **Banco de Dados:** PostgreSQL (com SQLAlchemy)
*   **IA & OCR:** Google Gemini API, Google Cloud Vision
*   **Integração Bancária:** Pierre API Client (`pierre_finance/client.py`)
*   **Frontend (Dashboard):** HTML, CSS (incluindo `dashboard.css` e `dashboard_cyberpunk.css`), JavaScript.
*   **Frontend (MiniApp):** Renderizado via `templates/miniapp.html`.
*   **Gerenciamento de Dependências:** Pip (`requirements.txt`)
*   **Orquestração:** Gunicorn (produção), Launcher script (`launcher.py` para desenvolvimento/execução híbrida).

## 🚀 Guia de Setup

Siga os passos abaixo para configurar e executar o ContaComigo em seu ambiente:

### 1. Pré-requisitos

*   Python 3.11 ou superior instalado.
*   Git instalado.
*   Um ambiente de banco de dados PostgreSQL acessível.
*   Credenciais para a API do Gemini e Google Cloud Vision.
*   Credenciais para a Pierre API.
*   Token para o Bot do Telegram.

### 2. Clonar o Repositório

```bash
git clone https://github.com/your-repo-url/ContaComigo.git
cd ContaComigo
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```dotenv
TELEGRAM_TOKEN="SEU_TELEGRAM_BOT_TOKEN"
DATABASE_URL="postgresql://user:password@host:port/dbname"
GEMINI_API_KEY="SUA_GEMINI_API_KEY"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/google/credentials.json" # Ou outra forma de credencial GCV
PIERRE_API_KEY="SUA_PIERRE_API_KEY"

# Opcional: Para desenvolvimento
PORT=10000
DEBUG=True
```

**Nota:** Para ambientes de produção (Render, Railway), configure estas variáveis através das configurações da plataforma.

### 5. Executar a Aplicação

*   **Modo Híbrido (Bot + Dashboard) - Desenvolvimento Local:**
    ```bash
    python launcher.py
    ```
    Ou, definindo o modo explicitamente:
    ```bash
    CONTACOMIGO_MODE=LOCAL_DEV python launcher.py
    ```

*   **Apenas Bot do Telegram:**
    ```bash
    CONTACOMIGO_MODE=BOT python launcher.py
    ```

*   **Apenas Dashboard Web:**
    ```bash
    CONTACOMIGO_MODE=DASHBOARD python launcher.py
    ```

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, consulte o arquivo `CONTRIBUTING.md` (se existir) para diretrizes.

## 📄 Licença

Este projeto está licenciado sob a licença [MIT License] (LICENSE).

---
## 📜 Change Log

Consulte o [CHANGELOG.md](./CHANGELOG.md) para ver as últimas atualizações.
