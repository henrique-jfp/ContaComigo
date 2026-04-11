# miniapp-e2e-validator

## Objetivo
Testar o carregamento, a renderização e o layout visual do frontend do MiniApp (Flask + Tailwind + Chart.js) diretamente no ambiente hospedado, garantindo boa performance, renderização correta e ausência de quebras visuais ou erros de console.

## Quando usar
- "testa o miniapp"
- "valida a interface"
- "olha o dashboard"
- "vê se o frontend quebrou"
- "confere o visual depois do deploy"
- "verifica mudanças em templates, static ou rotas Flask"

Também usar após alterações em: `templates/`, `static/`, rotas Flask, componentes visuais, Chart.js, Tailwind ou autenticação do Telegram WebApp.

## Workflow obrigatório

### 1. Verificação de deploy
- Use o MCP do Render para confirmar se o último deploy foi concluído com sucesso.
- Recupere a URL pública da aplicação.

### 2. Acesso e injeção de sessão
- Use MCP Browser/Playwright para abrir a URL do MiniApp.
- Simule a autenticação do Telegram WebApp com token HMAC válido ou de teste.
- Injete sessão por query parameters, headers, cookies ou local state conforme o fluxo real.

### 3. Validação estrutural e de performance
- Meça tempo de carregamento — deve ser inferior a 2 segundos.
- Inspecione o DOM para confirmar elementos essenciais renderizados.
- Verifique: containers Tailwind, canvas Chart.js, dados injetados pelo Flask, ausência de erros no console, ausência de falhas de network relevantes.

### 4. Validação visual
- Gere screenshot da página renderizada.
- Analise: layout quebrado ou desalinhado, gráficos ausentes, cores erradas, sobreposição de texto, problemas de spacing, cortes de conteúdo, problemas em viewport móvel.

### 5. Relatório
- Se erro 500: cruzar com logs do Render imediatamente.
- Se falha visual: identificar a div, classe, template ou asset responsável.
- Entregar relatório com: tempo de carregamento, status do deploy, erros de console, erros de backend, problemas visuais, feedback estético.

## Regras
- Sempre validar ambiente hospedado, não local.
- Sempre cruzar falhas visuais com DOM, console e logs.
- Sempre analisar versão desktop e, quando relevante, viewport móvel.
- Sempre apontar o elemento exato afetado quando identificar quebra.

## Referências
- `references/render-log-triage.md`
- `references/ui-checklist.md`
- `references/performance-checklist.md`