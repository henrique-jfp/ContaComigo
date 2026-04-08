# 🗺️ MAPA DE FUNCIONALIDADES - CONTACOMIGO

Este documento mapeia as funcionalidades ativas do ecossistema ContaComigo, detalhando os arquivos responsáveis pela lógica de backend e interface de frontend.

---

## 1. 🧠 Alfredo: Inteligência Artificial & Roteamento
O "cérebro" do sistema, responsável por entender linguagem natural (texto/voz), rotear intenções e gerar insights financeiros profundos.

*   **Backend (Lógica & Handlers):**
    *   `gerente_financeiro/ia_handlers.py`: Roteador principal, integração com Groq (Tools/Function Calling).
    *   `gerente_financeiro/prompt_manager.py`: Gerenciador de templates de prompts dinâmicos.
    *   `gerente_financeiro/prompts.py`: Definições estáticas de personas e prompts.
    *   `gerente_financeiro/prompts/`: Diretório com templates Jinja2 (`main_analysis.j2`, etc) e regras de skills.
    *   `gerente_financeiro/services.py`: Função `preparar_contexto_financeiro_completo` que alimenta a IA.
    *   `gerente_financeiro/ai_memory_service.py`: Criação do perfil psicológico-financeiro do usuário.

---

## 2. 📸 Lançamento por OCR (Visão Computacional)
Extração automática de dados de fotos de notas fiscais e cupons.

*   **Backend:**
    *   `gerente_financeiro/ocr_handler.py`: Lógica de integração com Google Vision API e fallback para Gemini 2.5 Flash.
    *   `models.py`: Modelos `ItemLancamento` para salvar os detalhes da nota.

---

## 3. 🧾 Importação Universal de Faturas (PDF)
Leitura e explosão de lançamentos a partir de PDFs de faturas de qualquer banco.

*   **Backend:**
    *   `gerente_financeiro/fatura_handler.py`: Handler de recepção do arquivo e parsing via Gemini.
    *   `gerente_financeiro/fatura_draft_store.py`: Armazenamento temporário (Rascunho) antes da confirmação.
*   **Frontend (MiniApp):**
    *   `templates/miniapp.html`: Editor de fatura para correção manual de lançamentos antes do salvamento.

---

## 4. 📱 MiniApp: Dashboard & Gestão Web
Interface visual rica dentro do Telegram para visualização de gráficos e edições complexas.

*   **Backend:**
    *   `analytics/dashboard_app.py`: Endpoints da API do MiniApp e autenticação via Telegram InitData.
    *   `gerente_financeiro/dashboard_handler.py`: Comando `/dashboard` e geração de URL com token.
*   **Frontend:**
    *   `templates/miniapp.html`: Interface Single Page Application (SPA).
    *   `static/dashboard.css`: Estilização principal.
    *   `templates/dashboard/`: Templates auxiliares (404, 500, index).

---

## 5. 🎮 Gamificação: RPG Financeiro (XP & Missões)
Sistema de engajamento que transforma finanças em um jogo.

*   **Backend:**
    *   `gerente_financeiro/gamification_handler.py`: Exibição do perfil gamer e rankings no chat.
    *   `gerente_financeiro/gamification_service.py`: Facade de acesso ao sistema de pontos.
    *   `gerente_financeiro/gamification_missions_service.py`: Lógica core de níveis (LEVELS) e regras de missões.
    *   `gerente_financeiro/gamification_utils.py`: Decorators (`@track_xp`) e helpers para conceder XP em outros handlers.
*   **Frontend (MiniApp):**
    *   `templates/miniapp.html`: Aba de Missões e visualização do progresso de nível.

---

## 6. 🤖 Assistente Proativo (Alertas & Notificações)
Detecção automática de padrões de gastos elevados e lembretes de contas.

*   **Backend:**
    *   `gerente_financeiro/assistente_proativo.py`: Algoritmos de detecção de anomalias e categorias infladas.
    *   `gerente_financeiro/assistente_proativo_handler.py`: Handler de comando para testes.
    *   `jobs.py`: Agendamento das tarefas diárias de análise.

---

## 7. 📊 Relatórios Executivos (PDF)
Geração de documentos profissionais com análise de saúde financeira.

*   **Backend:**
    *   `gerente_financeiro/relatorio_handler.py`: Orquestrador da geração do relatório.
    *   `gerente_financeiro/pdf_generator.py`: Engine ReportLab para desenho do layout "Private Bank".
    *   `gerente_financeiro/services.py`: Funções `gerar_grafico_para_relatorio` e `gerar_contexto_relatorio`.
*   **Frontend (Templates de Render):**
    *   `templates/relatorio_clean.html`: Estrutura base de dados.
    *   `templates/relatorio_inspiracao.html`: Layout visual rico.

---

## 8. 🎊 Wrapped Anual
Retrospectiva emocionante de final de ano (Estilo Spotify Wrapped).

*   **Backend:**
    *   `gerente_financeiro/wrapped_anual.py`: Lógica de agregação de dados do ano inteiro e curiosidades.
    *   `gerente_financeiro/wrapped_anual_handler.py`: Comando `/meu_wrapped`.

---

## 9. 📈 Gestão de Investimentos & Patrimônio
Controle de ativos e evolução do patrimônio líquido.

*   **Backend:**
    *   `gerente_financeiro/investment_handler.py`: CRUD de ativos, rentabilidade e metas de investimento.
    *   `gerente_financeiro/external_data.py`: Integração com APIs financeiras (Selic, IPCA, Cotações).

---

## 10. 💎 Monetização & Planos (Paywall)
Gestão de acessos Free vs Premium.

*   **Backend:**
    *   `gerente_financeiro/monetization.py`: Controle de quotas, integração com Mercado Pago e verificação de plano.
    *   `whitelist.txt`: Lista de usuários com acesso vitalício/beta.

---

## ⚙️ Infraestrutura & Base
*   **Entry Points:** `bot.py` (Threads do Bot), `app.py` (Flask), `launcher.py` (Orquestrador).
*   **Banco de Dados:** `models.py` (SQLAlchemy), `database/database.py` (Pool/Sessions).
*   **Configuração:** `config.py` e `.env`.
