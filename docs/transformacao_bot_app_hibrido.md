# Transformação ContaComigo: Bot → Híbrido (Bot + MiniApp)

Data: 2026-04-04

## Objetivo
Migrar as funcionalidades mais visuais e operacionais do bot para o MiniApp, mantendo o bot como camada de entrada rápida, suporte e ações sensíveis.

## Estrutura atual
### Continua no bot
- Lançamento manual
- OCR / fatura
- Notificações
- Ajuda / contato / suporte

### Migrou ou está no MiniApp
- Histórico de lançamentos
- Metas
- Gerente IA (Alfredo)
- Agendamentos
- Edição visual de lançamentos
- Configurações / onboarding básico

## Telas do MiniApp
- Histórico
- Metas
- Editar lançamentos
- Configurações / onboarding
- Alfredo
- Agendamentos

## APIs do MiniApp
- Autenticação Telegram WebApp
- Listagem de histórico
- Edição / exclusão de lançamentos
- Lista / cria / edita / exclui agendamentos
- Lista / cria / edita / exclui metas
- Chat do Alfredo com fallback Gemini → Groq
- Configurações do usuário
- Lista / cria / edita / exclui contas e cartões

## Pendências para completar a migração
- Lançamento manual com fluxo visual completo
- OCR de imagem/PDF com revisão no MiniApp
- Notificações em formato de central dentro do app
- Ajuda / suporte com layout próprio no MiniApp
- Relatórios e gráficos mais profundos
- Perfil / ranking / gamificação em tela própria
- Wrapped anual no MiniApp

## Decisões de arquitetura
- Bot fica como entrada rápida e contingência
- MiniApp concentra a experiência principal do usuário
- APIs do dashboard servem tanto telas de leitura quanto edição
- Fallback de IA: Gemini como primário, Groq como reserva

## Próximos passos sugeridos
1. Completar o fluxo de lançamento manual no MiniApp.
2. Levar OCR/fatura para a interface visual.
3. Criar central de notificações no app.
4. Consolidar perfil, ranking e relatórios no MiniApp.
5. Reduzir ainda mais a dependência do bot para navegação diária.
