# gerente_financeiro/gamification_utils.py
"""
Utilitários para integrar o sistema de gamificação em todos os handlers do bot.
Importe essas funções nos handlers que precisam dar XP.
"""

from database.database import get_db
from .gamification_service import award_xp, check_and_update_streak
import asyncio
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

_LAST_INTERACTION_XP: dict[int, datetime] = {}
_INTERACTION_COOLDOWN = timedelta(minutes=10)

async def give_xp_for_action(user_id: int, action: str, context, custom_amount: int = None):
    """
    Função auxiliar para dar XP por uma ação específica.
    
    Args:
        user_id (int): ID do usuário no Telegram
        action (str): Ação realizada (ver XP_ACTIONS no gamification_service.py)
        context: Context do Telegram
        custom_amount (int, optional): Quantidade personalizada de XP
    
    Usage:
        await give_xp_for_action(user_id, "LANCAMENTO_MANUAL", context)
        await give_xp_for_action(user_id, "META_ATINGIDA", context, 200)  # XP customizado
    """
    db: Session = next(get_db())
    try:
        # Atualizar streak diário (se necessário)
        await check_and_update_streak(db, user_id, context)
        
        # Conceder XP pela ação
        result = await award_xp(db, user_id, action, context, custom_amount)
        return result
    finally:
        db.close()

async def give_xp_silent(user_id: int, action: str, context, custom_amount: int = None):
    """
    Dar XP sem notificações (para ações muito frequentes).
    """
    db: Session = next(get_db())
    try:
        # Só dar XP, sem notificação
        from models import Usuario
        from .gamification_service import XP_ACTIONS, LEVELS
        
        base_xp = custom_amount or XP_ACTIONS.get(action, 0)
        if base_xp == 0:
            return
            
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario:
            return
            
        # Aplicar multiplicadores
        level_info = LEVELS.get(usuario.level, {"multiplicador": 1.0})
        final_xp = int(base_xp * level_info.get("multiplicador", 1.0))
        
        usuario.xp += final_xp
        db.commit()
        
        return {"xp_gained": final_xp}
    finally:
        db.close()

async def check_daily_streak(user_id: int, context):
    """
    Verificar e atualizar streak diário do usuário.
    Chame esta função no início de cada handler principal.
    """
    db: Session = next(get_db())
    try:
        await check_and_update_streak(db, user_id, context)
    finally:
        db.close()


async def touch_user_interaction(user_id: int, context) -> None:
    """Atualiza streak e concede XP leve por interacao com cooldown."""
    db: Session = next(get_db())
    try:
        await check_and_update_streak(db, user_id, context)

        now = datetime.utcnow()
        last = _LAST_INTERACTION_XP.get(user_id)
        if last and (now - last) < _INTERACTION_COOLDOWN:
            return

        await award_xp(db, user_id, "INTERACAO_BOT", context)
        _LAST_INTERACTION_XP[user_id] = now
    finally:
        db.close()

# === INTEGRAÇÃO FÁCIL COM DECORATORS ===

def track_xp(action: str, custom_amount: int = None):
    """
    Decorator para automaticamente dar XP em funções de handler.
    
    Usage:
        @track_xp("LANCAMENTO_MANUAL")
        async def handle_transaction(update, context):
            # Sua função normal
            pass
    """
    def decorator(func):
        async def wrapper(update, context):
            user_id = update.effective_user.id
            
            # Executar função original
            result = await func(update, context)
            
            # Dar XP após sucesso
            try:
                await give_xp_for_action(user_id, action, context, custom_amount)
            except Exception as e:
                # Log do erro, mas não interromper o fluxo
                import logging
                logging.getLogger(__name__).error(f"Erro ao dar XP: {e}")
            
            return result
        return wrapper
    return decorator

def track_xp_silent(action: str, custom_amount: int = None):
    """
    Decorator para dar XP sem notificações.
    """
    def decorator(func):
        async def wrapper(update, context):
            user_id = update.effective_user.id
            
            # Executar função original
            result = await func(update, context)
            
            # Dar XP silencioso após sucesso
            try:
                await give_xp_silent(user_id, action, context, custom_amount)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Erro ao dar XP silencioso: {e}")
            
            return result
        return wrapper
    return decorator

# === FUNÇÕES DE CONQUISTAS ===

async def check_achievements(user_id: int, context):
    """
    Verificar se o usuário desbloqueou novas conquistas.
    """
    db: Session = next(get_db())
    try:
        from models import Usuario, Lancamento
        from sqlalchemy import func
        
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario:
            return
        
        # Contar transações para conquistas
        total_transacoes = db.query(func.count(Lancamento.id)).filter(
            Lancamento.id_usuario == usuario.id
        ).scalar() or 0
        
        # Lista de conquistas para verificar
        conquistas_para_verificar = [
            (10, "PRIMEIRA_DEZENA", "🎉 Primeira Dezena! Você registrou 10 transações!"),
            (50, "MEIO_CENTENARIO", "🏆 Meio Centenário! 50 transações registradas!"),
            (100, "CENTENARIO", "💎 Centenário! 100 transações - Você é um Mestre!"),
        ]
        
        # Verificar conquistas de transações
        for milestone, achievement_id, message in conquistas_para_verificar:
            if total_transacoes >= milestone:
                # Verificar se já foi concedida (você pode implementar uma tabela de conquistas)
                # Por enquanto, dar XP bônus
                await give_xp_for_action(user_id, "CONQUISTA_DESBLOQUEADA", context)
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🏅 <b>CONQUISTA DESBLOQUEADA!</b>\n\n{message}\n\n⭐ +25 XP Bônus!",
                        parse_mode='HTML'
                    )
                except:
                    pass
                break  # Parar na primeira conquista não desbloqueada
        
    finally:
        db.close()

# === EXEMPLOS DE USO ===
"""
# No manual_entry_handler.py:
from .gamification_utils import give_xp_for_action, track_xp

@track_xp("LANCAMENTO_MANUAL")
async def process_manual_entry(update, context):
    # Sua lógica de lançamento manual
    pass

# Ou uso direto:
async def some_function(update, context):
    user_id = update.effective_user.id
    # Sua lógica...
    
    # Dar XP no final
    await give_xp_for_action(user_id, "GRAFICO_GERADO", context)

# No fatura_handler.py:
await give_xp_for_action(user_id, "FATURA_PROCESSADA", context)

# No handlers.py (para IA):
await give_xp_for_action(user_id, "PERGUNTA_IA_COMPLEXA", context)
"""
