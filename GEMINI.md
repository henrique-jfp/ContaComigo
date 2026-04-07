# Gemini Context: ContaComigo Core

## Variáveis de Ambiente Cruciais
- `CONTACOMIGO_MODE`: Define se é `LOCAL_DEV` ou `PRODUCTION`.
- `MINIAPP_AI_INSIGHT_ENABLED`: Deve ser `false` por padrão para manter o sistema leve.

## Padrões de Nomenclatura
- Handlers de conversa terminam em `_conv`.
- Funções de processamento de IA começam com `processar_`.
- Alfredo deve ser tratado como uma persona de "mordomo eficiente".

## Integrações Ativas
- **Google Vision:** Usado em `ocr_handler.py`.
- **Groq/LLaMA:** Usado para roteamento rápido de intenções.
- **MiniApp:** Frontend em `templates/miniapp.html`.