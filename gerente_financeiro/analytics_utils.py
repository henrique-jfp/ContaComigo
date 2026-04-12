import logging
import functools

ANALYTICS_ENABLED = True  # Ajuste conforme necessário

# Exemplo de função de tracking (substitua pelo seu analytics real)
def track_command_usage(user_id, username, command, success=True):
    logging.info(f"[Analytics] Usuário: {username} (ID: {user_id}) usou /{command} - Sucesso: {success}")

# Decorator centralizado

def track_analytics(command_name):
    """Decorator para tracking de comandos"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            if ANALYTICS_ENABLED and hasattr(update, 'effective_user') and update.effective_user:
                user_id = update.effective_user.id
                username = getattr(update.effective_user, 'username', None) or getattr(update.effective_user, 'first_name', 'Usuário')
                try:
                    track_command_usage(
                        user_id=user_id,
                        username=username,
                        command=command_name,
                        success=True
                    )
                    logging.info(f"📊 Analytics: {username} usou /{command_name}")
                except Exception as e:
                    logging.error(f"❌ Erro no analytics: {e}")
            # Executa o handler com proteção contra falhas de rede/Telegram
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                # Evita que exceções de rede (ex: telegram.error.TimedOut) derrubem o loop
                try:
                    import telegram
                    if hasattr(telegram, 'error') and isinstance(e, telegram.error.TimedOut):
                        logging.warning(f"Handler {command_name} timed out: {e}")
                        # Não re-lançamos: o update é consumido e o bot continua responsivo
                        return None
                except Exception:
                    # Fallback: se não conseguimos identificar o tipo, apenas logamos
                    pass
                logging.exception(f"Unhandled exception in handler {command_name}: {e}")
                return None
        return wrapper
    return decorator
