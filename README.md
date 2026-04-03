<div align="center">
  <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
  <img src="https://img.shields.io/badge/AI-Gemini_2.5_Flash-F4B400?style=for-the-badge&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="Postgres" />
</div>

<h1 align="center">💸 MaestroFin: Seu Gerente Financeiro Pessoal com IA</h1>

> **Controle financeiro sem atrito. Envie áudios, tire fotos de notas fiscais ou mande mensagens em texto natural. A IA faz o resto.**

---

## 🎯 **O que é o MaestroFin?**

O **MaestroFin** é um assistente financeiro no Telegram projetado para acabar com a fricção no registro de despesas. 
Diferente de aplicativos tradicionais de planilhas onde você precisa navegar em menus e formulários, aqui basta agir naturalmente:
- Gravou um áudio dizendo: *"Gastei 55 reais de Uber hoje"*? Ele entende, categoriza e salva.
- Mandou a foto da nota fiscal do mercado? Ele lê item a item e extrai os valores usando Visão Computacional.
- Quer saber para onde o dinheiro está indo? Pergunte ao seu Gerente VDM integrado e receba uma análise baseada no seu **próprio perfil comportamental**.

Tudo isso acompanhado de **Dashboards Web**, relatórios em **PDF**, **Integração Open Finance** e um sistema de **Gamificação** para te manter motivado.

---

## ✨ **Funcionalidades & Superpoderes**

### 🎙️ Lançamento via Áudio Sem Fricção (Zero-Shot)
Graças à infraestrutura multimodal do **Gemini 2.5 Flash**, basta enviar um áudio nativo (voz) para o bot narrando o seu gasto. A IA transcreve, deduz data, categoria, forma de pagamento e nome do estabelecimento em segundos. Sem precisar digitar comandos!

### 🧠 Memória Semântica Evolutiva (Frictionless Memory)
O bot **aprende quem você é**. Periodicamente, um Job em background analisa suas últimas dezenas de transações e a forma como você conversa, criando um **Perfil Psicológico Financeiro**. Nas próximas conversas, a IA já sabe se você tem dificuldade em economizar com delivery, ou se prefere respostas curtas ou explicativas. *Cada usuário tem uma experiência 100% exclusiva e personalizada*.

### 📸 Leitura Automática de Notas (Smart OCR)
Seja enviando um `.pdf` ou tirando uma foto da notinha do mercado, o sistema utiliza o robusto **Google Vision API** (com fallback para Gemini Vision) para ler CNPJ, valor total, itens e preencher a despesa perfeitamente por você.

### 💼 Gerente VDM (Voz, Dados e Mentoria)
Converse livremente usando Linguagem Natural. O bot cruza o seu histórico financeiro com a expertise de um consultor de investimentos para te entregar Insights (dicas acionáveis), listar faturas ou ajudar no seu planejamento.

### 🎮 Gamificação, Metas & Open Finance
- **Níveis e XP:** Ganhe pontos ao registrar gastos, cumprir o orçamento mensal e manter as streaks de acessos.
- **Lista de Desejos (Wishlist):** Adicione metas de médio prazo e o app acompanha a sua evolução.
- **Sincronização Bank-Level:** Arquitetura adaptada para integração com serviços Open Finance.
- **Relatórios Premium:** Gere e exporte relatórios PDF maravilhosos ou acesse seu Dashboard Web com gráficos interativos.

---

## 🛠️ **Arquitetura & Tecnologias**

O projeto é inteiramente em Python moderno e assíncrono.
- **`python-telegram-bot (v22+)`**: Coração assíncrono para os fluxos de conversa (`ConversationHandler`).
- **`google-generativeai`**: Alimentando a engine conversacional, áudio e OCR reverso com a família Gemini (Flash 1.5 e 2.5).
- **`google-cloud-vision`**: Extração determinística de textos em notas fiscais de altíssima precisão.
- **`SQLAlchemy (2.0+)` & `PostgreSQL`**: ORM para gerir a complexa árvore relacional de Usuários, Transações, Objetivos e Análises de Perfil.
- **`Jinja2` & `WeasyPrint`**: Para renderização de HTML em relatórios PDF luxuosos.
- **Jobs Internos (`APScheduler`)**: Rotinas de verificação semanal e remapeamento de memória/perfil via IA em background.

---

## 🚀 **Como Rodar Localmente**

### 1. Pré-requisitos
- Python 3.12+
- PostgreSQL 14+
- Credenciais da API do Telegram (BotFather)
- Credenciais do Google Cloud Vision (`.json`) e Gemini (`API Key`)

### 2. Instalação e Configuração

```bash
# Clone o repositório
git clone https://github.com/henrique-jfp/MaestroFin.git
cd MaestroFin

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # no Linux/Mac
# ou .venv\Scripts\activate no Windows

# Instale as dependências
pip install -r requirements.txt

# Configure o arquivo .env contendo chaves
cp .env.example .env
# Defina as variáveis TELEGRAM_TOKEN, GEMINI_API_KEY, DATABASE_URL, etc.
```

### 3. Executando

```bash
# Rode assim para que as rotinas assíncronas do telegram-bot e background jobs subam juntas
python bot.py
```

Pronto. Mande um `/start` para o seu bot no Telegram e aproveite sua vida financeira resolvida.

---

## ⚙️ **Estrutura de Pastas de Destacar**
- `/gerente_financeiro/audio_handler.py`: Módulo responsável pela leitura de `filters.VOICE` com processamento Gemini 2.5 Flash nativo de bytes de áudio.
- `/gerente_financeiro/ai_memory_service.py`: Serviço de memória semântica e atualização de perfil comportamental.
- `/gerente_financeiro/ocr_handler.py`: Onde a mágica de ler PDFs e imagens ganha vida combinada com validadores de OCR.
- `/gerente_financeiro/prompt_manager.py`: O Roteador Jinja2 que engloba ferramentas como skills, regras de negócio e limites para a persona do bot.

---

## 📜 **Licenciamento**

> **⚠️ ATENÇÃO:** Este projeto usa **Licença Dupla (Dual License)**

| Tipo de Uso | Status | Detalhes |
|------------|--------|----------|
| 🎓 **Portfolio/Educação** | ✅ **GRATUITO** | Visualizar código, estudar, demonstrar em entrevistas, rodar na máquina local |
| 💼 **Empresas/Comercial** | 💰 **PAGO** | Produção, white-label, monetização, integração comercial |

💌 **Licenciamento Comercial:** henriquejfp.dev@gmail.com

---

## 📞 **Contato & Autoria**

Desenvolvido com 🧠 e muito ☕ por **Henrique**.

- 💼 **LinkedIn**: [henrique-jfp](https://linkedin.com/in/henrique-jfp)
- 💬 **Teste o Bot**: [@MaestroFinBot](https://t.me/MaestroFinBot)

<div align="center">

### ⭐ Se esse projeto expandiu seus horizontes do que dá pra fazer com IA, deixa uma estrela! ⭐

</div>
