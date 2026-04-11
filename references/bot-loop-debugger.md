# bot-loop-debugger

## Objetivo
Realizar testes de integração ponta a ponta ("full-loop") disparando comandos reais para o bot, coletando a resposta final recebida pelo usuário e cruzando esse comportamento com logs de produção/servidor para identificar falhas silenciosas, regressões, timeouts e erros de integração.

## Quando usar
- "teste o fluxo X do bot"
- "verifique por que o bot não respondeu"
- "debug de produção da feature Y"
- "investigue erro de comunicação no bot"
- "veja o que aconteceu no Telegram e nos logs"

## Workflow obrigatório

### 1. Disparo da ação
- Use o MCP do Telegram para enviar uma mensagem natural ou comando real diretamente ao bot de teste ou produção.
- Simule o comportamento do usuário final com inputs realistas, como `/start` ou "gastei 50 reais no mercado".

### 2. Coleta da resposta UI
- Aguarde até 10 segundos.
- Use o MCP do Telegram para ler a última resposta recebida do bot.
- Registre: se houve resposta, qual foi, se a formatação HTML/markup está correta, se pareceu genérica, truncada, errada ou ausente.

### 3. Auditoria de logs
- Acesse o MCP do Render logo após a interação.
- Busque os logs mais recentes do serviço Web e/ou Worker relevante.
- Procure especialmente por: stack traces, bloqueios por I/O síncrono, erros de SQLAlchemy, falhas em Whisper/Cerebras/Gemini, timeouts, retries, exceções de rede, falhas de serialização.

### 4. Cruzamento UI x backend
Compare o que o usuário viu no Telegram com o que aconteceu no backend.

Cenários comuns:
- **Silent failure**: bot responde algo genérico, mas log mostra erro real.
- **Timeout**: bot não responde, logs indicam bloqueio da thread principal.
- **Regressão funcional**: fluxo antes funcionava, agora quebra em etapa diferente.
- **Erro de formatação**: lógica executa, mas resposta enviada ao Telegram vem inválida.

### 5. Correção automática
- Identifique o arquivo e trecho com falha.
- Corrija seguindo os padrões do projeto.
- Exemplos: mover operações bloqueantes para `run_in_executor`, corrigir queries ORM, tratar exceções de integrações externas, ajustar serialização ou HTML da resposta.
- Explique: (A) erro real nos logs, (B) o que o usuário viu, (C) a correção aplicada.

## Regras
- Sempre priorize evidência observável em Telegram + logs, não suposição.
- Sempre registrar se houve ou não resposta visível ao usuário.
- Sempre cruzar horário/evento da interação com os logs correspondentes.
- Não concluir diagnóstico apenas com base na UI.

## Referências
- `references/telegram-debug-checklist.md`
- `references/render-log-triage.md`
- `references/common-failures.md`