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

*   **Planning Hub & Gestão de Agenda:**
    *   Centralização de orçamentos, limites de gastos e compromissos financeiros na aba **"Agenda"**.
    *   Interface unificada para planejamento de metas e controle de pagamentos recorrentes.
    *   Visualização clara de orçamentos versus realizado para cada categoria.

*   **Lembretes Proativos do Alfredo:**
    *   Sistema inteligente de notificações para vencimentos e alertas de orçamento.
    *   Criação e gerenciamento de lembretes diretamente pelo MiniApp ou via chat no Telegram.
    *   Fluxo de IA que entende e agenda compromissos financeiros automaticamente.

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

## 🏗️ Arquitetura de Infraestrutura

Atualmente, o ContaComigo opera em um modelo de **Servidor Local Híbrido** (HP Pavilion X360) para máxima performance com baixo custo operacional:

*   **Servidor:** Ubuntu Server 24.04 LTS hospedado localmente.
*   **Conectividade:** Exposto via **Cloudflare Tunnel** para o domínio `alfredo.henriquedejesus.dev`.
*   **Deploy Contínuo (CD):** Automatizado via **GitHub Webhooks**. O servidor detecta novos `push` no branch `main`, realiza o `pull` e reinicia o serviço automaticamente.
*   **Gerenciamento de Processos:** Controlado via `systemd` (`contacomigo.service`).

## 🛠️ Stack Técnica

*   **Linguagem Principal:** Python 3.12+
*   **Framework Web:** Flask
*   **API do Telegram:** `python-telegram-bot`
*   **Banco de Dados:** PostgreSQL (Supabase Managed)
*   **IA & OCR:** Google Gemini API, Groq, Cerebras, Google Cloud Vision.
*   **Integração Bancária:** Pierre API Client (`pierre_finance/client.py`)
*   **Frontend (MiniApp):** Flask Templates + Tailwind CSS + Chart.js.

## 🚀 Guia de Operação (Servidor Local)

### Gerenciamento do Serviço
O sistema é gerenciado via comandos padrão de Linux no servidor:

```bash
sudo systemctl status contacomigo   # Ver status
sudo systemctl restart contacomigo  # Reiniciar manualmente
sudo journalctl -u contacomigo -f   # Ver logs em tempo real
```

### Automação de Deploy
Para configurar o deploy automático:
1.  Configure o endpoint `/api/deploy/webhook` nas configurações do seu repositório no GitHub.
2.  Defina o `GITHUB_WEBHOOK_SECRET` no arquivo `.env` do servidor.

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, consulte o arquivo `CONTRIBUTING.md` (se existir) para diretrizes.

## 📄 Licença

Este projeto está licenciado sob a licença [MIT License] (LICENSE).

---
## 📜 Change Log

Consulte o [CHANGELOG.md](./CHANGELOG.md) para ver as últimas atualizações.
