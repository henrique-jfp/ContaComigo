"""
Sistema de Alertas e Notificações - ContaComigo
"""
import logging
from datetime import datetime, time
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
from database.database import get_db
from models import Usuario, Objetivo

logger = logging.getLogger(__name__)

async def schedule_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para configurar alertas personalizados"""
    await update.message.reply_text(
        "🔔 *Sistema de Alertas*\n\n"
        "Em breve você poderá configurar:\n"
        "• Alertas de gastos por categoria\n"
        "• Lembretes de metas financeiras\n"
        "• Notificações de vencimentos\n\n"
        "Sistema em desenvolvimento! 🚧",
        parse_mode='Markdown'
    )

async def checar_objetivos_semanal(context: ContextTypes.DEFAULT_TYPE):
    """Verifica objetivos semanalmente"""
    try:
        logger.info("🎯 Iniciando verificação semanal de objetivos...")
        
        db: Session = next(get_db())
        
        # Buscar todos os usuários com objetivos ativos
        hoje = datetime.now().date()
        usuarios_com_objetivos = (
            db.query(Usuario)
            .join(Objetivo)
            .filter(Objetivo.data_meta >= hoje)
            .distinct()
            .all()
        )
        
        for usuario in usuarios_com_objetivos:
            try:
                # Aqui poderia enviar mensagem sobre progresso dos objetivos
                logger.info(f"📊 Verificando objetivos do usuário {usuario.telegram_id}")
                
                # Por enquanto só registra no log
                # Futuramente enviará mensagens personalizadas
                
            except Exception as e:
                logger.error(f"❌ Erro ao verificar objetivos do usuário {usuario.telegram_id}: {e}")
                continue
        
        db.close()
        logger.info("✅ Verificação semanal de objetivos concluída")
        
    except Exception as e:
        logger.error(f"❌ Erro na verificação semanal de objetivos: {e}")

async def agendar_notificacoes_diarias(context: ContextTypes.DEFAULT_TYPE):
    """Agenda notificações diárias"""
    try:
        logger.info("📅 Executando agendamento diário de notificações...")
        
        # Por enquanto só registra no log
        # Futuramente enviará lembretes personalizados
        
        logger.info("✅ Agendamento diário concluído")
        
    except Exception as e:
        logger.error(f"❌ Erro no agendamento diário: {e}")
