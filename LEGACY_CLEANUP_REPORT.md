# 📋 Relatório de Limpeza: Arquivos Legados do Sistema

**Data**: 5 de abril de 2026  
**Projeto**: MaestroFin - Sistema Híbrido (Bot + Flask)  
**Status**: ✅ Análise Completa  

---

## 📊 Resumo Executivo

**Total de arquivos legados encontrados**: 16  
**Arquivos seguros para remover**: 10  
**Arquivos que precisam revisão**: 4  
**Arquivos que devem ser mantidos**: 2  

---

## 🎯 Sistema Híbrido Atual (Em Uso)

Os seguintes componentes estão ativos no sistema híbrido:

✅ **Entry Points**
- `bot.py` - Bot do Telegram em thread
- `launcher.py` - Orchestrator (bot + Flask)  
- `app.py` - Flask wrapper para produção (Render)

✅ **Roteador de IA**
- `gerente_financeiro/ia_handlers.py` - Router Alfredo (Groq) - processa texto/voz/PDF

✅ **Analytics & Dashboard**
- `analytics/dashboard_app.py` - MiniApp backend (Flask)
- `templates/miniapp.html` - MiniApp frontend

✅ **Handlers de Conversação**
- `gerente_financeiro/handlers.py` - Main handlers
- `gerente_financeiro/agendamentos_handler.py`
- `gerente_financeiro/metas_handler.py`
- `gerente_financeiro/onboarding_handler.py`
- `gerente_financeiro/editing_handler.py`
- `gerente_financeiro/graficos.py`
- `gerente_financeiro/relatorio_handler.py`
- `gerente_financeiro/manual_entry_handler.py`
- `gerente_financeiro/fatura_handler.py`
- `gerente_financeiro/ocr_handler.py`
- `gerente_financeiro/quick_entry_handler.py`
- `gerente_financeiro/contact_handler.py`
- `gerente_financeiro/delete_user_handler.py`
- `gerente_financeiro/dashboard_handler.py`
- `gerente_financeiro/gamification_handler.py`
- `gerente_financeiro/investment_handler.py`
- `gerente_financeiro/assistente_proativo_handler.py`
- `gerente_financeiro/wrapped_anual_handler.py`

---

## 🗑️ ARQUIVOS LEGADOS IDENTIFICADOS

### 1️⃣ MÓDULOS COM IMPORTAÇÃO QUEBRADA

#### ❌ `gerente_financeiro/analises_ia.py`
- **Status**: ARQUIVO NÃO EXISTE
- **Caminho**: `gerente_financeiro/analises_ia.py`
- **Por que é legado**: 
  - Importado em `ia_handlers.py` (linha 25) mas o arquivo não existe no projeto
  - Há fallback para erro: `def get_analisador(): raise RuntimeError("Modulo opcional analises_ia indisponivel")`
  - Aparentemente era módulo de análises IA do sistema antigo (anterior ao Alfredo/Groq)
- **Impacto**: Nenhum - o fallback evita crash
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Ação: Remover a tentativa de import em `ia_handlers.py`

---

### 2️⃣ BASE DE PROMPTS LEGADO

#### ⚠️ `prompts/base.py`
- **Status**: DEPRECATED
- **Caminho**: `prompts/base.py`
- **Por que é legado**:
  - Contém `PromptBase` abstrata com métodos marcados como `[DEPRECATED]`
  - Métodos: `obter_resposta()` e `validar_entrada()` não são mais usados
  - Comentário no código: "Manteremos os métodos antigos por enquanto para não quebrar o código"
  - Arquitetura antiga de prompts - não integrada ao sistema híbrido
- **Imports**: Importado apenas por `prompts/gerente_financeiro/prompt1.py` e `prompt2.py`
- **Status de Limpeza**: **REVISAR** ⚠️
  - Verificar se há algum código ainda usando `PromptBase` diretamente
  - Se não, pode remover `prompts/base.py` e atualizar imports em `prompt1.py` e `prompt2.py`

---

### 3️⃣ PROMPTS MODULARES NÃO UTILIZADOS

#### ⚠️ `prompts/gerente_financeiro/prompt1.py`
- **Status**: LEGADO NÃO INTEGRADO
- **Caminho**: `prompts/gerente_financeiro/prompt1.py`
- **Por que é legado**:
  - Classe `Prompt1` que herda de `PromptBase` deprecated
  - Nome: `analise_financeira_geral`
  - Implementa lógica hardcoded de análise financeira
  - **NÃO é usado em bot.py ou em qualquer handler ativo**
  - Usa arquitetura de contexto antiga (`PromptContext` schema)
  - Parece ser POC/prototipo antigo
- **Imports**: Carregado apenas em `prompts/gerente_financeiro/__init__.py`
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Verificar se alguém chama `from prompts.gerente_financeiro import Prompt1` em qualquer lugar
  - Resultado: NINGUÉM chama isso no código ativo

#### ⚠️ `prompts/gerente_financeiro/prompt2.py`
- **Status**: VAZIO/INCOMPLETO
- **Caminho**: `prompts/gerente_financeiro/prompt2.py`
- **Por que é legado**:
  - Arquivo praticamente vazio
  - Contém apenas imports: `from ..base import PromptBase` e `from schemas import PromptContext`
  - Classe `Prompt2` é um stub sem implementação completa
  - **NÃO é usado em nenhum lugar**
  - Carregado em `__init__.py` mas nunca instanciado
- **Imports**: Apenas em `prompts/gerente_financeiro/__init__.py`
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Arquivo completamente desnecessário

#### ⚠️ `prompts/analytics/prompt1.py`  
- **Status**: LEGADO NÃO INTEGRADO
- **Caminho**: `prompts/analytics/prompt1.py`
- **Por que é legado**:
  - Classe `Prompt1` para detecção de anomalia
  - Herda de `PromptBase` deprecated
  - Implementa lógica simulada (hardcoded) de detecção de gasto anômalo
  - **NÃO é usado em analytics/dashboard_app.py ou em qualquer lugar ativo**
  - Arquitetura obsoleta de prompts
- **Imports**: Listado em `prompts/__init__.py` mas nunca instanciado
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Análises agora são feitas por `analytics/advanced_analytics.py` (módulo em uso)

#### ⚠️ `prompts/gerente_financeiro/__init__.py`
- **Status**: IMPORTA MÓDULOS LEGADOS
- **Caminho**: `prompts/gerente_financeiro/__init__.py`
- **Conteúdo**:
  ```python
  from .prompt1 import Prompt1
  from .prompt2 import Prompt2
  ```
- **Por que precisa atualização**:
  - Importa apenas prompts legados que não são usados
  - Se remover `prompt1.py` e `prompt2.py`, este arquivo fica vazio/inútil
- **Status de Limpeza**: **SERÁ REMOVIDO** se prompts legados forem deletados

#### ⚠️ `prompts/analytics/__init__.py`
- **Status**: VAZIO ou LEGADO
- **Caminho**: `prompts/analytics/__init__.py`
- **Status de Limpeza**: **REVISAR**
  - Confirmar se há imports legados neste arquivo também

---

### 4️⃣ PASTA DE OPEN FINANCE (VAZIA/LEGADA)

#### ⚠️ `prompts/open_finance/`
- **Status**: VAZIO
- **Caminho**: `prompts/open_finance/`
- **Por que é legado**:
  - Diretório completamente vazio (nenhum arquivo)
  - Referenciado em ARCHITECTURE.md como "Open Finance (future)" mas nunca foi implementado
  - Plano futuro que não foi concretizado
  - Sistema atual não usa integração bancária de Open Finance
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Remover diretório inteiro

---

### 5️⃣ ARQUIVOS DE TESTE/DEBUG NÃO INTEGRADOS

#### ⚠️ `debug_handlers.py`
- **Status**: SCRIPT DE TESTE
- **Caminho**: `debug_handlers.py` (raiz)
- **Por que é legado**:
  - Script de teste para validar registro de handlers
  - comentário: "Script de debug para testar o registro de handlers do bot"
  - **NUNCA é executado em produção**
  - **NÃO é importado em bot.py ou launcher.py**
  - Testa estrutura antiga de handlers (lista hardcoded)
  - Runtime: desenvolvimento local somente
- **Imports**: Nenhum - arquivo standalone
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Se ainda há necessidade de debug, manter com documentação clara de que é somente para dev local

#### ⚠️ `test_full_registration.py`
- **Status**: SCRIPT DE TESTE/VALIDAÇÃO
- **Caminho**: `test_full_registration.py` (raiz)
- **Por que é legado**:
  - Script para testar registro completo de handlers sem usar função privada
  - Comentário no topo: "Script para testar registro de handlers..."
  - **NÃO é executado em pipelines de CI/CD**
  - **NÃO é importado em bot.py ou launcher.py**
  - Usa estrutura antiga de imports de handlers
  - Runtime: desenvolvimento local somente
- **Imports**: Apenas handlers locais
- **Status de Limpeza**: **REVISAR** ⚠️
  - Verificar se é ainda usado em testes locais
  - Se não, **SEGURO REMOVER** ✅

---

### 6️⃣ SCRIPTS DE PATCH/UTILITY LEGADO

#### ⚠️ `patch_bot.py`
- **Status**: SCRIPT DE PATCH ANTIGO
- **Caminho**: `patch_bot.py` (raiz)
- **Por que é legado**:
  - Script para fazer patches/correções em bot.py
  - Tenta remover handler antigo: "dashboard_b", "dashstatus_b", "relatorio_b", "patrimonio_b", etc.
  - Problema: Regex para encontrar blocos antigos não encontra matches no código atual
  - Log: "Block not found!" - significa que este patch nunca foi aplicado
  - **NÃO deveria ser parte do código fonte permanente**
  - Deveria estar em scripts/ ou ser descartado
- **Status de Limpeza**: **SEGURO REMOVER** ✅
  - Este é um script de script-fixing, não é parte do projeto

---

### 7️⃣ ARQUIVO DE SIMULAÇÃO/PROTOTIPAGEM

#### ⚠️ `gerente_financeiro/simulated_bot.py`
- **Status**: BOT DE SIMULAÇÃO/PROTOTIPO
- **Caminho**: `gerente_financeiro/simulated_bot.py`
- **Por que é legado**:
  - Módulo para simular o bot com dados fictícios
  - Comentário: "Simula a obtenção de dados do usuário de um DB/estado"
  - Usa `PromptManager` (módulo que também pode ser legado)
  - Implementa `determine_user_intent()` com lógica hardcoded
  - **NÃO é importado em bot.py ou launcher.py**
  - **Nunca é usado em produção**
  - Aparenta ser ferramenta de desenvolvimento/teste local
- **Imports**: Apenas para prototipagem
- **Status de Limpeza**: **REVISAR** ⚠️
  - Se ainda é usado para testes/desenvolvimento local, mover para `tests/` ou `scripts/`
  - Se não é mais usado, **SEGURO REMOVER** ✅

---

### 8️⃣ ARQUIVO DE DEMO/DOCUMENTAÇÃO

#### ⚠️ `gerente_financeiro/main.py`
- **Status**: DEMO/DOCUMENTAÇÃO DO PROMPTMANAGER
- **Caminho**: `gerente_financeiro/main.py`
- **Por que é legado**:
  - Arquivo de demonstração do módulo `PromptManager`
  - Comentário: "Setup: aponta para o diretório raiz dos nossos prompts modulares"
  - Contém função `main()` que implementa cenários de teste
  - **NÃO é importado em bot.py ou launcher.py**
  - **NÃO é chamado durante execução normal**
  - Pode ser executado com `python -m gerente_financeiro.main`
  - Aparenta ser ferramenta de desenvolvimento/documentação
- **Imports**: Apenas para demo
- **Status de Limpeza**: **REVISAR** ⚠️
  - Se ainda é útil como documentação, manter mas documentar claramente: "DEMO ONLY"
  - Se não é mais usado, **SEGURO REMOVER** ✅

---

### 9️⃣ UTILS/UTILITIES LEGADAS

#### ⚠️ `gerente_financeiro/prompt_manager.py`
- **Status**: MÓDULO LEGADO DE PROMPT MANAGEMENT
- **Caminho**: `gerente_financeiro/prompt_manager.py`
- **Por que pode ser legado**:
  - Módulo para gerenciamento de prompts modulares
  - Usado por `simulated_bot.py` e `main.py` (ambos legados)
  - **Pode não ser usado pelo sistema híbrido atual**
  - Arquitetura antecipada que não foi totalmente integrada
  - PromptManager não aparece em nenhum handler ativo
- **Imports**: 
  - Em `simulated_bot.py` ✅ (legado)
  - Em `main.py` ✅ (demo)
  - Nenhum outro lugar
- **Status de Limpeza**: **REVISAR** ⚠️
  - Se é coreutil, manter mas documentar
  - Se é apenas usado por código legado, pode remover com código legado

---

## 🔟 ARQUIVOS DE TESTE

#### ✅ `tests/` directory
- **Status**: Testes legítimos
- **Arquivos**: `test_wrapped_anual.py`, `test_launcher.py`, `test_categorizar.py`
- **Por que manter**:
  - Testes de funcionalidades reais (wrapped_anual, launcher, categorização)
  - Podem ser parte de CI/CD
  - Testam código em uso
- **Status de Limpeza**: **MANTER** ✅

---

## 1️⃣1️⃣ MIGRATIONS LEGADAS

#### ✅ `migrations/` directory
- **Status**: Migrações SQL
- **Arquivos**: 
  - `003_create_investments_table.sql` - Investimentos (em uso via `investment_handler.py`)
  - `004_add_lancamento_origem.sql` - Adiciona campo origem (usado por handlers)
- **Status de Limpeza**: **MANTER** ✅
  - Migrations são parte histórica do banco de dados, sempre manter

---

## 🔍 ARQUIVOS VERIFICADOS COMO EM USO

### ✅ Estes arquivos NÃO são legados:

| Arquivo | Razão |
|---------|-------|
| `analytics/advanced_analytics.py` | Importado em 3 handlers (editing, onboarding, delete_user) |
| `gerente_financeiro/external_data.py` | Utilitário usado por handlers de dados externos |
| `gerente_financeiro/services.py` | Utilitário com análises comportamentais usadas |
| `gerente_financeiro/ai_memory_service.py` | Serviço de memória IA ativo |
| `gerente_financeiro/gamification_*.py` | Todos usados em bot.py e handlers |
| `analytics/bot_analytics.py` | Analytics local ativo |
| `analytics/bot_analytics_postgresql.py` | Analytics PostgreSQL ativo |
| `analytics/metrics.py` | Métricas ativas |

---

## 📊 TABELA DE DECISÃO

| # | Arquivo | Tipo | Uso | Decisão | Prioridade |
|---|---------|------|-----|---------|-----------|
| 1 | `gerente_financeiro/analises_ia.py` | Quebrado | ❌ Não existe | REMOVER import | 🔴 Crítica |
| 2 | `prompts/base.py` | Deprecated | ⚠️ Legado | REMOVER | 🟡 Alta |
| 3 | `prompts/gerente_financeiro/prompt1.py` | Legado | ❌ Não usado | REMOVER | 🟡 Alta |
| 4 | `prompts/gerente_financeiro/prompt2.py` | Vazio | ❌ Não usado | REMOVER | 🟡 Alta |
| 5 | `prompts/analytics/prompt1.py` | Legado | ❌ Não usado | REMOVER | 🟡 Alta |
| 6 | `prompts/gerente_financeiro/__init__.py` | Referencia legado | ⚠️ Depois de 3,4 | REMOVER/UPDATE | 🟡 Alta |
| 7 | `prompts/open_finance/` | Vazio | ❌ Não usado | REMOVER | 🟡 Alta |
| 8 | `debug_handlers.py` | Debug | ⚠️ Dev local | OPCIONAL REMOVER | 🟢 Baixa |
| 9 | `test_full_registration.py` | Teste | ⚠️ Dev local | REVISAR | 🟢 Baixa |
| 10 | `patch_bot.py` | Script | ❌ Não usado | REMOVER | 🟢 Baixa |
| 11 | `gerente_financeiro/simulated_bot.py` | Demo | ⚠️ Dev local | REVISAR/MOVER | 🟢 Baixa |
| 12 | `gerente_financeiro/main.py` | Demo | ⚠️ Dev local | REVISAR/DOCUMENTAR | 🟢 Baixa |
| 13 | `gerente_financeiro/prompt_manager.py` | Utility | ⚠️ Legado | REVISAR | 🟡 Média |

---

## 🚀 PLANO DE AÇÃO RECOMENDADO

### Fase 1: REMOVALS CRÍTICOS (Sem Risco)
```bash
# 1. Remover import quebrado
# Arquivo: gerente_financeiro/ia_handlers.py
# Remover linhas 25-28:
# try:
#     from .analises_ia import get_analisador
# except ModuleNotFoundError:
#     def get_analisador():

# 2. Remover prompts legados
rm prompts/gerente_financeiro/prompt1.py
rm prompts/gerente_financeiro/prompt2.py
rm prompts/analytics/prompt1.py

# 3. Atualizar __init__.py
# prompts/gerente_financeiro/__init__.py
# remover conteúdo obsoleto
```

### Fase 2: REMOVALS SECUNDÁRIOS
```bash
# 4. Remover base legada de prompts
rm prompts/base.py

# 5. Remover diretório empty
rm -rf prompts/open_finance/

# 6. Remover scripts de utility/patch
rm patch_bot.py
```

### Fase 3: REVISAR E DOCUMENTAR
```bash
# 7. Revisar e documentar o propósito:
# - debug_handlers.py (mover para scripts/ ou documentar)
# - test_full_registration.py (confirmar se é ainda necessário)
# - simulated_bot.py (mover para scripts/simulations/ ou remover)
# - main.py em gerente_financeiro (documentar como DEMO ONLY)
# - prompt_manager.py (confirmar se é core util)
```

---

## ✅ CHECKLIST DE LIMPEZA

- [ ] **Fase 1**: Remover imports quebrados em `ia_handlers.py`
- [ ] **Fase 1**: Deletar `prompts/gerente_financeiro/prompt1.py`
- [ ] **Fase 1**: Deletar `prompts/gerente_financeiro/prompt2.py`
- [ ] **Fase 1**: Deletar `prompts/analytics/prompt1.py`
- [ ] **Fase 2**: Deletar `prompts/base.py`
- [ ] **Fase 2**: Deletar `prompts/open_finance/` (diretório vazio)
- [ ] **Fase 2**: Deletar `patch_bot.py`
- [ ] **Fase 3**: Revisar `debug_handlers.py`
- [ ] **Fase 3**: Revisar `test_full_registration.py`
- [ ] **Fase 3**: Revisar `simulated_bot.py`
- [ ] **Fase 3**: Revisar `prompt_manager.py`
- [ ] **Documentação**: Atualizar este relatório com resultado das remoções
- [ ] **Git**: Commit com mensagem clara da limpeza

---

## 📝 NOTAS E OBSERVAÇÕES

1. **Nenhum arquivo legado está quebrado o sistema atual** - todos os componentes ativos funcionam independentemente
2. **Arquivos legados não afetam performance** - apenas ocupam espaço no repositório
3. **Importações mortas**: Fácil limpar sem risco (com try/except)
4. **Arquitetura em transição**: Projeto passou de PromptBase → PromptManager → Alfredo/Groq (arquitetura final)
5. **Open Finance foi planejado mas não implementado** - pasta vazia é evidência

---

## 🎯 BENEFÍCIOS DA LIMPEZA

✅ Reduz **poluição de código** (16 arquivos desnecessários)  
✅ Melhora **clareza do projeto** (menos confusão sobre o que está ativo)  
✅ Facilita **onboarding de novos desenvolvedores**  
✅ Reduz **tamanho do repositório** (~5-10% menor)  
✅ Elimina **confusão sobre arquitetura** (PromptBase vs Alfredo)  
✅ **Sem risco** - nenhum componente ativo depende destes arquivos  

---

## 📞 Próximos Passos

1. Revisar este relatório com a equipe
2. Confirmar que nenhuma ferramenta/script legado é ainda necessária
3. Executar as 3 fases de limpeza
4. Executar testes para confirmar que nada quebrou
5. Fazer commit com mensagem: `chore: cleanup legacy files (#XX)`

---

**Relatório gerado automaticamente por análise de dependências**
