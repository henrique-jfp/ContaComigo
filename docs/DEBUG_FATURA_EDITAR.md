# Debug: Botão "Editar Fatura" Não Abre

## Problema Relatado
- Usuário clica em "✏️ Editar" após processar PDF de fatura
- Botão não responde (Telegram mostra timeout ou sem reação)
- Logs não mostram o erro claramente

## Fluxo Esperado
```
1. Usuário: Envia PDF de fatura (/fatura ou botão)
   ↓
2. Bot: fatura_receive_file() processa PDF
   ↓
3. Bot: Retorna FATURA_CONFIRMATION_STATE com 3 botões:
   - ✅ Confirmar e Salvar (fatura_salvar)
   - ✏️ Editar (fatura_editar_inline)
   - ❌ Cancelar (fatura_cancelar)
   ↓
4. Usuário: Clica em "✏️ Editar"
   ↓
5. Telegram: Envia callback_query.data = "fatura_editar_inline"
   ↓
6. Bot Handler (fatura_confirm): 
   - Recebe callback
   - Responde com query.answer() em <5s (Telegram requirement)
   - Gera token de draft
   - Envia nova mensagem com botão web_app
   ↓
7. Usuário: Vê "Abrir Editor da Fatura" button com MiniApp link
```

## Possíveis Causas

### 1. **ConversationHandler Não Está no Estado Correto**
**Sintoma:** Telegram mostra BOT_RESPONSE_TIMEOUT (user vê ⏳)

**Por quê?** 
- ConversationHandler saiu do estado FATURA_CONFIRMATION_STATE antes do callback chegar
- Callback pattern não casando com `^fatura_`
- ConversationHandler não pode encontrar handler para o callback

**Debug:**
```bash
# Ver logs de:
# - "Processando fatura_editar_inline"
# - "Dados de fatura expirados" (se cache perdido)
# - "ERRO NO FATURA_CONFIRM" (se exceção)
```

### 2. **URL Gerada Está Inválida**
**Sintoma:** Botão aparece, mas não abre MiniApp

**Por quê?**
- `DASHBOARD_BASE_URL` não configurada ou inválida
- Fallback `RENDER_EXTERNAL_URL` não funcionando
- URL não tem HTTPS (Telegram bloqueia non-HTTPS web_app)

**Debug:**
```bash
# Ver logs de "URL do editor gerada"
# Verificar que URL tem HTTPS e parametros válidos
```

### 3. **Exceção Silenciosa**
**Sintoma:** Sem resposta, sem erro no chat

**Por quê?**
- `query.answer()` falha
- `_get_fatura_webapp_url()` lança exceção
- Database queries falham

**Debug:**
```bash
# Ver logs de:
# - "Falha ao responder callback"
# - "ERRO NO FATURA_CONFIRM"
# - Stack traces completos
```

### 4. **Context/User Data Perdidos**
**Sintoma:** "❌ Dados da fatura expiraram"

**Por quê?**
- `context.user_data` foi limpo
- Conversation state resetou
- User tem múltiplas conversas ativas

**Debug:**
```bash
# Ver logs de:
# - "Dados de fatura expirados: transacoes=X, conta_id=Y"
# - Confirmar se values existem em context.user_data
```

## Solução de Problemas Passo a Passo

### Passo 1: Confirmar Que o Callback Chega
O handler `debug_all_callbacks` em `bot.py` registra TODOS os callbacks:
```python
# Ver logs de "DEBUG_CALLBACK: data=fatura_editar_inline from_user=USERID"
```

**Se NÃO aparecer:**
- Problema está no Telegram ou no regist do bot
- User está em estado errado

**Se aparecer:**
- Problema está no handler ou context

### Passo 2: Verificar Resposta do Callback
Localize no log:
```
INFO: fatura_confirm: action=fatura_editar_inline, user=USERID
INFO: Processando fatura_editar_inline para user=USERID
```

**Se aparecer:** Handler está sendo chamado ✅
**Se NÃO:** Callback não casou com pattern `^fatura_`

### Passo 3: Verificar Dados de Fatura
Localize:
```
INFO: Dados de fatura expirados: transacoes=True, conta_id=123
```

**Se `transacoes=False` ou `conta_id=None`:**
- Cache foi perdido (possível sessão múltipla)
- User precisa enviar PDF novamente

**Se `transacoes=True` e `conta_id=123`:**
- Dados estão OK ✅

### Passo 4: Verificar URL Gerada
Localize:
```
INFO: URL do editor gerada: https://...webapp?page=fatura_editor... (truncado)
```

**Se HTTPS e tem parametros:** URL OK ✅
**Se HTTP e não-localhost:** Telegram vai recusar
**Se falta parametros:** Função tem bug

### Passo 5: Verificar Envio de Botão
Localize:
```
INFO: Enviando botão de editor para user=USERID
INFO: Botão de editor enviado com sucesso
```

**Se ambos aparecem:** Tudo funcionou ✅
**Se "Enviando..." mas não "com sucesso":** Exceção durante reply_text

## Logs Relevantes para Coletar

Se o problema persiste, execute e colete:

```bash
# 1. Tail dos logs em tempo real
tail -f debug_logs/bot.log | grep -i "fatura\|callback\|error"

# 2. Ao testar, procure por:
# - "DEBUG_CALLBACK: data=fatura_editar_inline"
# - "fatura_confirm: action=fatura_editar_inline"
# - "Processando fatura_editar_inline"
# - "URL do editor gerada"
# - "Botão de editor enviado com sucesso"
# - "ERRO NO FATURA_CONFIRM"

# 3. Export dos últimos 1000 logs
tail -n 1000 debug_logs/bot.log > fatura_debug.log
```

## Checklist de Verificação

- [ ] `DEBUG_CALLBACK` aparece com `fatura_editar_inline`?
- [ ] `fatura_confirm: action=fatura_editar_inline` aparece?
- [ ] `Dados de fatura expirados: transacoes=True`?
- [ ] `URL do editor gerada: https://...`?
- [ ] `Botão de editor enviado com sucesso`?
- [ ] Botão com "Abrir Editor da Fatura" aparece no Telegram?
- [ ] Clicando no botão, MiniApp abre?

## Próximos Passos Se Ainda Não Funcionar

1. **Coletar logs completos** durante o teste
2. **Verificar `DASHBOARD_BASE_URL`** / `RENDER_EXTERNAL_URL`
3. **Testar URL manualmente** no navegador
4. **Verificar se há ConversationHandler em conflito** atrapalhando a rota
5. **Ativar debug verbose** em python-telegram-bot

## Commits Relacionados

- `f25dba2`: Adicionado global handler para fatura callbacks
- `ae211cf`: Melhorado error handling e logging
- `cc4b2e9`: Corrigido indentação do fatura_confirm

---
**Última atualização:** 5 de abril de 2026
