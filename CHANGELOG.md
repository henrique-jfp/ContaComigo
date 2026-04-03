# Changelog - Maestro Financeiro

## [3.4.0] - 2026-04-03

### 🎯 Metas Financeiras (Nova Experiencia)

#### ✨ Novos Recursos
- **/metas renovado**: cria metas com fluxo guiado e plano mensal calculado por IA.
- **Progresso visual**: barra de avance, percentual e valor atualizado por meta.
- **Check-in mensal**: job automatico pergunta se o usuario conseguiu guardar o valor do mes.
- **Confirmacao mensal**: atualiza o progresso com um clique.

#### 🔄 Substituicoes
- ❌ **Removido**: sistema de wishlist.
- ✅ **Adicionado**: `gerente_financeiro/metas_handler.py` com novo fluxo.

#### 🔧 Modificacoes
- `bot.py` - registro de handlers atualizado para /metas.
- `jobs.py` - job mensal para check-in de metas.
- `models.py` - nova tabela de confirmacoes mensais de metas.

## [3.3.0] - 2025-11-18

### 🎯 Wishlist Inteligente - Substituição do Sistema de Metas

#### ✨ Novos Recursos
- **Análise de Viabilidade Financeira**: Sistema que analisa se seus objetivos são atingíveis com seu padrão atual
- **Sugestões Personalizadas de Economia**: IA identifica categorias cortáveis e calcula economia potencial
- **Múltiplas Opções de Plano**:
  - 📉 **Cortar Gastos Moderado**: Redução de 30% em categorias não essenciais
  - 📉 **Cortar Gastos Agressivo**: Redução de 50% para metas urgentes
  - 📅 **Estender Prazo**: Calcula prazo alternativo viável
  - 💼 **Aumentar Receita**: Sugere quanto de renda extra é necessário
- **Cálculo de Poupança Real**: Analisa seus últimos 3 meses para determinar capacidade de economizar
- **Priorização Automática**: Ordena categorias por potencial de economia

#### 🔄 Substituições
- ❌ **Removido**: `gerente_financeiro/metas_handler.py` (sistema de metas simples)
- ✅ **Adicionado**: `gerente_financeiro/wishlist_handler.py` (sistema inteligente com IA)

#### 📦 Comandos
- `/wishlist` - Criar novo desejo com análise de viabilidade completa
- `/metas` - Listar desejos com indicadores de progresso inteligentes (mantido por compatibilidade)

#### 🧠 Funcionalidades Inteligentes
- **Análise de Categorias Cortáveis**: Identifica automaticamente onde você pode economizar
- **Cálculo de Economia Potencial**: Mostra quanto pode economizar reduzindo gastos em cada categoria
- **Planos de Ação Personalizados**: Gera plano específico baseado na opção escolhida
- **Alertas de Viabilidade**: Indica se a meta é atingível antes mesmo de criar

#### 🔧 Modificações
- `bot.py` - Substituídos imports e handlers de metas por wishlist
- `VERSION` - Atualizado para 3.3.0

---

## [3.2.0] - 2025-11-18

### 🎊 Wrapped Financeiro Anual - Retrospectiva Épica

#### ✨ Novos Recursos
- **Retrospectiva Anual Completa**: Resumo financeiro do ano com estatísticas e curiosidades
- **Execução Automática**: Job configurado para 31/dezembro às 13h
- **Comando Manual**: `/meu_wrapped` para gerar o wrapped a qualquer momento

#### 📦 Arquivos Adicionados
- `gerente_financeiro/wrapped_anual.py` - Sistema de geração do wrapped
- `gerente_financeiro/wrapped_anual_handler.py` - Handler do comando

#### 🔧 Modificações
- `jobs.py` - Adicionado job anual do wrapped (31/dez 13h)
- `bot.py` - Registrado handler `/meu_wrapped`

---

## [3.1.0] - 2025-11-18

### 🤖 Assistente Proativo - Alertas Inteligentes

#### ✨ Novos Recursos
- **Análise Proativa de Gastos**: Sistema que monitora automaticamente padrões financeiros
- **3 Tipos de Alertas Inteligentes**:
  - 🔴 **Gastos Elevados**: Alerta quando gastos estão 30%+ acima da média histórica
  - 💰 **Assinaturas Duplicadas**: Detecta serviços similares e calcula economia potencial  
  - 🎯 **Metas em Risco**: Notifica quando metas estão 15%+ atrasadas
- **Job Automático**: Roda diariamente às 20h analisando todos os usuários ativos
- **Comando de Teste**: `/teste_assistente` para análise manual imediata

#### 📦 Arquivos Adicionados
- `gerente_financeiro/assistente_proativo.py` - Core do sistema de análise
- `gerente_financeiro/assistente_proativo_handler.py` - Handler do comando de teste

#### 🔧 Modificações
- `jobs.py` - Adicionado job diário do assistente proativo (20h)
- `bot.py` - Registrado handler `/teste_assistente`

---

## [2.0.0] - 2025-11-18

### 🚀 Major Features
- **Non-blocking Async Execution**: Refactored `/sincronizar` to use `asyncio.run_in_executor()` for non-blocking bank synchronization
  - Multiple users can now sync simultaneously without blocking other commands
  - Event loop remains responsive during heavy operations
  - Solves critical concurrency issue affecting user experience

### ✨ Improvements
REMOVIDO: Integração Pluggy/Open Finance
  - Ensures no accounts are hidden on subsequent pages (fixes missing "Cofrinho" accounts)
- **Investment Detection**: Automatic detection of investments in checking accounts via `automaticallyInvestedBalance`
- **Architecture**: Moved synchronous blocking operations to separate threads following python-telegram-bot best practices

### 🐛 Bug Fixes
- Fixed `ZeroDivisionError` in report template when financial data is zero
- Fixed `UnboundLocalError` in PDF generation error handling
- Removed duplicate exception handling that was masking original errors
- Improved error messaging and user feedback

### 🧹 Chores
Removidos arquivos de teste obsoletos (`test_gemini_model.py`)
- Removed deprecated migration scripts (`apply_migration_*.py`)
- Removed obsolete documentation files (bugfix and configuration guides consolidated into main docs)
- Cleaned up `__pycache__` directories
- Code cleanup and refactoring

---

## [1.0.0] - Previous Release

### Features
REMOVIDO: Integração Open Finance OAuth
- Telegram bot with comprehensive financial management
- Transaction categorization and analytics
- Investment tracking
- Financial reports and gamification
- OCR for receipt processing

---

## Release Notes

### v2.0.0 - Breaking Changes / Important Updates
- **Concurrency**: Bot now handles multiple simultaneous user requests without blocking
- **Scalability**: Can handle N concurrent users making requests
- **Reliability**: Improved error handling and recovery

### Migration Guide
No migration required. This is a drop-in improvement that maintains backward compatibility.

---

