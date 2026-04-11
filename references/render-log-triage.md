# Render log triage

Priorizar busca por:
- stack trace recente
- timeout
- thread blocked
- SQLAlchemyError
- falhas de rede
- erros de serialização
- falhas em Whisper, Cerebras e Gemini

Se houver 500 ou tela quebrada:
- conferir último deploy
- verificar exceções Flask
- verificar template faltando
- verificar erro em static asset
- verificar rota retornando payload inesperado
- correlacionar com horário exato da interação do Telegram ou do browser