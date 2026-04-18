# Explicação dos prompts em gerente_financeiro/prompts

Este documento descreve cada arquivo dentro de `gerente_financeiro/prompts`, o propósito de cada prompt/template, e o que pode acontecer caso você altere ou delete o arquivo. Use este guia antes de modificar qualquer prompt em produção.

> Observação: muitos desses arquivos são usados como *templates* (Jinja2 `.j2`) ou instruções para a IA; alterar o texto ou as regras pode mudar o comportamento do assistente (`Alfredo`) de forma não-linear. Teste mudanças em um ambiente de desenvolvimento antes do deploy.

## Arquivos no nível raiz

- `main_analysis.j2`
  - O que é: template Jinja2 usado para montar a análise principal que será enviada ao modelo. Provavelmente combina contexto (dados do usuário, extratos, métricas) e instruções estilísticas.
  - Para que serve: gera o prompt final que o modelo irá processar para produzir a análise principal (resumo, insights, recomendações).
  - Se alterar: mudanças no texto, nas variáveis ou na ordem dos blocos alteram diretamente o conteúdo e o tom das respostas; pode introduzir variações de qualidade ou perda de informação esperada.
  - Se deletar: o fluxo que monta análises ficará sem template — isso causa erro ao renderizar o prompt (ex.: KeyError/TemplateNotFound) ou força o uso de um fallback indesejado.

- `PROMPT_ALFREDO_APRIMORADO.md`
  - O que é: documentação/arquivo de prompt principal que define a persona e instruções de alto nível para o assistente "Alfredo" (tom, comportamentos proibidos, limites, objetivos).
  - Para que serve: serve como referência ou como *system prompt* para orientar respostas (usar formato, nivel de detalhe, restrições de segurança, templates a aplicar).
  - Se alterar: mudanças amortecem de forma ampla — por exemplo, alterar o tom (mais formal/informal) mudará todas as respostas; remover restrições pode permitir outputs indesejados.
  - Se deletar: se o sistema carregar esse arquivo como base, a persona pode voltar ao padrão, causando respostas menos alinhadas; porém se houver fallback interno, o sistema não quebrará, apenas perde o comportamento refinado.

## Pasta `rules`

- `rules/formatting_html.md`
  - O que é: regras sobre como formatar respostas em HTML (tags permitidas, sanitização, estruturas esperadas).
  - Para que serve: garante que o output em HTML esteja seguro (por exemplo, apenas `<b>`, `<i>`, `<code>`), e que templates gerados sejam compatíveis com o renderer do Telegram/MiniApp.
  - Se alterar: afrouxar regras pode gerar HTML inválido ou inseguro; restringir demais pode perder recursos visuais necessários (tabelas, listas). Alterações mandam efeito imediato no formato das mensagens enviadas.
  - Se deletar: renderer pode receber HTML livre — risco de quebra de UI ou conteúdo bloqueado; também pode fazer o sistema deixar de sanitizar e abrir risco de XSS em painéis web.

- `rules/function_calling.md`
  - O que é: instruções sobre como estruturar chamadas de função / outputs estruturados (ex.: JSON, nomes de campos, contratos para function-calling de modelos que suportam isso).
  - Para que serve: padroniza a forma de pedir ao modelo que retorne objetos acionáveis (ex.: `{ "action": "...", "params": {...} }`) de modo que o orquestrador saiba quando invocar funções internas.
  - Se alterar: mudar campos ou formato quebra a compatibilidade com o código que consome essas respostas (p.ex. `prompt_manager` ou `ia_service`), causando falhas no parsing ou ações incorretas.
  - Se deletar: o sistema perde o contrato esperado e possivelmente deixará de executar ações automáticas, ou falhará ao interpretar respostas estruturadas.

## Pasta `skills`

- `skills/comparative_analysis.md`
  - O que é: prompt para análises comparativas (ex.: comparação entre opções de investimento, contas, meses).
  - Para que serve: direciona o modelo a comparar critérios, pontuar diferenças, e sugerir escolhas.
  - Se alterar: alterar instruções de comparação (ex.: métricas consideradas) muda os critérios e pode tornar recomendações inconsistentes com o restante do sistema.
  - Se deletar: funcionalidade de comparativos pode sumir ou cair em fallback genérico.

- `skills/function_call_query.j2`
  - O que é: template que provavelmente estrutura queries para function-calling (preenche parâmetros antes de enviar ao modelo).
  - Para que serve: gera payloads consistentes para chamadas estruturadas; converte contexto em argumentos para funções.
  - Se alterar: mudanças no formato causado pelo template podem gerar incompatibilidade com funções que recebem esses parâmetros.
  - Se deletar: função que constrói chamadas programáticas perde suporte — erros no runtime.

- `skills/lists_rankings.md`
  - O que é: prompt que instrui o modelo a criar listas ordenadas, rankings e classificações (ex.: top investimentos, prioridades).
  - Para que serve: padroniza formato de saída (listas numeradas, critérios, escores).
  - Se alterar: pequenas mudanças afetam apenas a aparência; mudanças de métrica/critério afetam o ranking real.
  - Se deletar: endpoints que esperam um ranking formatado podem falhar ou receber texto livre.

- `skills/payment_account_analysis.md`
  - O que é: prompt focado em analisar contas de pagamento/fluxo de caixa.
  - Para que serve: extrai insights financeiros específicos (receitas, despesas recorrentes, anomalias).
  - Se alterar: cuidado — alterar quais métricas são consideradas pode gerar recomendações financeiras incorretas.
  - Se deletar: relatórios e insights financeiros específicos desaparecem.

- `skills/period_summaries.md`
  - O que é: prompt para gerar resumos por período (mensal, trimestral).
  - Para que serve: sintetiza transações e métricas em um breve resumo fácil de ler.
  - Se alterar: mudar o nível de detalhe altera usabilidade do resumo (p.ex. muito técnico vs muito raso).
  - Se deletar: histórico resumido não será gerado automaticamente.

- `skills/proactive_insights.md`
  - O que é: prompt que guia o modelo a produzir insights proativos (alertas, recomendações antes do usuário pedir).
  - Para que serve: alimentar ações proativas do assistente (p.ex. sugerir poupança quando gastos aumentam).
  - Se alterar: alterar triggers/limiares ou tom impacta a utilidade e a aceitação pelo usuário.
  - Se deletar: a camada proativa deixa de existir; o bot só responderá a solicitações explícitas.

- `skills/simple_predictive_analysis.md`
  - O que é: prompt para previsões simples (tendências baseadas em séries temporais ou heurísticas).
  - Para que serve: orientar previsões rápidas (p.ex. expectativa de saldo, tendência de gasto).
  - Se alterar: cuidado com suposições de modelo; mudar instruções pode gerar previsões fora do esperado.
  - Se deletar: previsões automatizadas não serão geradas.

- `skills/strategic_questions.md`
  - O que é: prompt que lista perguntas estratégicas a serem feitas ao usuário para obter contexto (ex.: prioridades, perfil de risco).
  - Para que serve: padronizar entrevistas guiadas pelo assistente para coletar requisitos.
  - Se alterar: mudanças no questionário afetam coleta de dados e decisões subsequentes.
  - Se deletar: o fluxo de coleta ficará menos estruturado.

## Pasta `system`

- `system/persona_alfredo.md`
  - O que é: definição formal da persona do assistente (valores, tom, exemplos, regras proibidas).
  - Para que serve: serve como `system prompt` primário que regula comportamento (escalonamento de respostas, estilo, limites legais).
  - Se alterar: impactos amplos — alterar diretrizes pode gerar respostas inconsistentes com a marca ou violar restrições legais/UX.
  - Se deletar: se usado ativamente, o assistente pode voltar a um comportamento genérico; se houver fallback, o risco é de perda de alinhamento.

## Pasta `templates`

- `templates/conversation_context.j2`
  - O que é: template para montar o contexto de conversa (mensagens anteriores, estado relevante, variáveis de sessão).
  - Para que serve: ajuda a manter coerência entre mensagens, fornece histórico resumido para o modelo.
  - Se alterar: cortar ou reordenar histórico pode fazer o modelo perder contexto ou repetir informações.
  - Se deletar: o fluxo conversacional pode perder coerência, principalmente em diálogos multi-turnos.

- `templates/insight_final.j2`
  - O que é: template que formata o insight final que será mostrado ao usuário (estrutura, títulos, recomendações finais).
  - Para que serve: garante consistência visual e textual do resultado final.
  - Se alterar: mudanças no layout ou no tom do insight final se refletem diretamente na experiência do usuário.
  - Se deletar: saída final pode ficar despadronizada; handlers que esperam campos específicos podem falhar.

- `templates/monthly_report_analysis.j2`
  - O que é: template para relatórios mensais detalhados (agrupamentos, gráficos, tabelas).
  - Para que serve: monta o conteúdo que alimenta o relatório mensal do usuário.
  - Se alterar: alterar seções ou variáveis impacta geração de relatórios e compatibilidade com renderers (WeasyPrint, PDF generator).
  - Se deletar: relatórios mensais podem não ser gerados ou ficam incompletos.

- `templates/structured_response.j2`
  - O que é: template que força uma resposta estruturada (JSON ou formato definido) para facilitar parsing automático.
  - Para que serve: importante para integrações onde o código espera campos e tipos bem definidos.
  - Se alterar: alterar chaves ou tipos quebra consumidores automatizados que confiam nesse formato.
  - Se deletar: perda de formato estruturado; integrações automáticas podem falhar.

## Recomendações gerais antes de alterar

- Teste localmente: crie um branch e execute fluxos end-to-end; verifique `gerente_financeiro/prompt_manager.py` e `gerente_financeiro/ia_service.py` para pontos de integração.
- Versão: mantenha cópias das versões antigas (git) antes de alterações significativas.
- Backward-compatibility: ao alterar formatos estruturados (JSON, campos), mantenha suporte ao formato antigo por um ciclo de deploy.
- Sanitização: nunca remova regras de `formatting_html.md` sem validar renderers; risco de XSS e mensagens quebradas.
- Pequenas mudanças iterativas: altere frases para melhorar clareza, evite alterar contratos (nomes de campos, chaves JSON) sem coordenação.

## Onde checar referências no código

- Verifique `gerente_financeiro/prompt_manager.py` e `gerente_financeiro/ia_service.py` para saber exatamente como cada prompt/template é carregado e renderizado.
- Procure por chamadas a Jinja (`Environment.get_template`) ou leitura direta de arquivos `.md`/`.j2`.

---

Arquivo gerado automaticamente: [gerente_financeiro/prompts/EXPLICACAO_PROMPTS.md](gerente_financeiro/prompts/EXPLICACAO_PROMPTS.md)

Se quiser, eu posso:

- 1) procurar referências exatas no código a cada arquivo e anexar linhas (mais preciso);
- 2) validar mudanças propostas em um branch de testes e rodar validações básicas.

Com qual opção quer que eu prossiga?
