"""
Sistema de Alertas e Notificações - ContaComigo
"""
import logging
from datetime import datetime, time, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
from database.database import get_db
from models import Usuario, Objetivo, Agendamento

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

async def enviar_lembretes_usuario(context: ContextTypes.DEFAULT_TYPE):
    """Job disparado no horário específico do usuário para enviar os lembretes de agendamentos."""
    job = context.job
    user_id = job.data['user_id']
    agendamentos_ids = job.data['agendamentos_ids']
    
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario or not usuario.alerta_gastos_ativo:
            return
            
        agendamentos = db.query(Agendamento).filter(Agendamento.id.in_(agendamentos_ids), Agendamento.ativo == True).all()
        if not agendamentos:
            return
            
        texto = "🔔 <b>Lembrete de Agendamentos</b>\n\nVocê tem compromissos programados para hoje:\n\n"
        
        keyboard = []
        for ag in agendamentos:
            tipo_emoji = "🟢" if ag.tipo == "Entrada" else "🔴"
            texto += f"{tipo_emoji} <b>{ag.descricao}</b>\n"
            texto += f"💰 R$ {ag.valor:.2f}\n\n"
            
            # Botão de dar baixa (Registrar)
            btn_text = f"✅ Dar baixa: {ag.descricao[:15]}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ag_baixa_{ag.id}")])
            
        texto += "<i>Toque nos botões abaixo para registrar no seu fluxo de caixa:</i>"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete para {user_id}: {e}", exc_info=True)
    finally:
        db.close()

async def agendar_notificacoes_diarias(context: ContextTypes.DEFAULT_TYPE):
    """Agenda notificações diárias rodando todo dia na madrugada para todos os usuários."""
    try:
        logger.info("📅 Executando agendamento diário de notificações...")
        
        db = next(get_db())
        hoje = datetime.now().date()
        
        # Buscar agendamentos que vencem HOJE ou já passaram e ainda estão ativos
        agendamentos_hoje = db.query(Agendamento).join(Usuario).filter(
            Agendamento.proxima_data_execucao <= hoje,
            Agendamento.ativo == True,
            Usuario.alerta_gastos_ativo == True
        ).all()
        
        # Agrupar por usuário
        agendamentos_por_usuario = {}
        for ag in agendamentos_hoje:
            user = ag.usuario
            if user.id not in agendamentos_por_usuario:
                agendamentos_por_usuario[user.id] = {
                    'telegram_id': user.telegram_id,
                    'horario': user.horario_notificacao or time(hour=9, minute=0),
                    'agendamentos_ids': []
                }
            agendamentos_por_usuario[user.id]['agendamentos_ids'].append(ag.id)
            
        # Para cada usuário, criar um job rodando no horário específico DELE
        agora = datetime.now()
        for user_data in agendamentos_por_usuario.values():
            horario = user_data['horario']
            
            # Montar o datetime de quando enviar hoje
            target_time = datetime.combine(hoje, horario)
            
            # Se o horário já passou, envia daqui a 1 minuto
            if target_time <= agora:
                target_time = agora + timedelta(minutes=1)
                
            context.job_queue.run_once(
                enviar_lembretes_usuario,
                when=target_time,
                data={
                    'user_id': user_data['telegram_id'],
                    'agendamentos_ids': user_data['agendamentos_ids']
                },
                name=f"lembrete_{user_data['telegram_id']}_{hoje.strftime('%Y%m%d')}"
            )
            
        logger.info(f"✅ Agendamento diário concluído: {len(agendamentos_por_usuario)} usuários notificados para hoje.")
        
    except Exception as e:
        logger.error(f"❌ Erro no agendamento diário: {e}", exc_info=True)
    finally:
        if 'db' in locals():
            db.close()
