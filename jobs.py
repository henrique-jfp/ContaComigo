"""
Sistema de Jobs e Tarefas Agendadas - ContaComigo
"""
import logging
from datetime import datetime, time
from telegram.ext import ContextTypes
from alerts import agendar_notificacoes_diarias
from gerente_financeiro.assistente_proativo import job_assistente_proativo
from gerente_financeiro.wrapped_anual import job_wrapped_anual
from gerente_financeiro.ai_memory_service import job_atualizar_perfis_ia
from gerente_financeiro.metas_handler import job_metas_mensal
from gerente_financeiro.gamification_missions_service import (
    reset_daily_missions_for_all_users,
    reset_weekly_missions_for_all_users,
    apply_monthly_performance_awards,
)
from database.database import get_db

logger = logging.getLogger(__name__)




def configurar_jobs(job_queue):
    """Configura todos os jobs agendados do sistema"""
    try:
        logger.info("⚙️ Configurando jobs agendados...")
        
        # Job diário às 01:00 - Agendamento de notificações
        job_queue.run_daily(
            agendar_notificacoes_diarias,
            time=time(hour=1, minute=0),
            name="agendador_mestre_diario"
        )
        
        # Job diario que roda no dia 1 - Check-in mensal de metas
        job_queue.run_daily(
            job_metas_mensal,
            time=time(hour=10, minute=0),
            name="metas_checkin_mensal"
        )
        

        
        # Job diário às 20:00 - Assistente Proativo (alertas inteligentes)
        job_queue.run_daily(
            job_assistente_proativo,
            time=time(hour=20, minute=0),
            name="assistente_proativo_diario"
        )
        
        # Job diário que verifica se é 31/Dez para enviar o Wrapped
        async def wrapped_check(context):
            from datetime import datetime
            now = datetime.now()
            if now.month == 12 and now.day == 31:
                await job_wrapped_anual(context)

        job_queue.run_daily(
            wrapped_check,
            time=time(hour=13, minute=0),
            name="wrapped_anual_31_dezembro"
        )

        async def job_gamification_daily_reset(context):
            db = next(get_db())
            try:
                reset_daily_missions_for_all_users(db)
            finally:
                db.close()

        async def job_gamification_weekly_reset(context):
            from datetime import datetime
            if datetime.now().weekday() != 0:
                return
            db = next(get_db())
            try:
                reset_weekly_missions_for_all_users(db)
            finally:
                db.close()

        async def job_gamification_monthly_awards(context):
            from datetime import datetime
            if datetime.now().day != 1:
                return
            db = next(get_db())
            try:
                apply_monthly_performance_awards(db)
            finally:
                db.close()

        job_queue.run_daily(
            job_gamification_daily_reset,
            time=time(hour=0, minute=5),
            name="gamification_daily_reset"
        )

        job_queue.run_daily(
            job_gamification_weekly_reset,
            time=time(hour=0, minute=10),
            name="gamification_weekly_reset"
        )

        job_queue.run_daily(
            job_gamification_monthly_awards,
            time=time(hour=0, minute=15),
            name="gamification_monthly_awards"
        )
        
        logger.info("✅ Jobs agendados configurados com sucesso:")
        logger.info("   📅 Notificações diárias: 01:00")
        logger.info("   🎯 Check-in de metas: dia 1, 10:00")

        logger.info("   🤖 Assistente Proativo: 20:00 (alertas inteligentes)")
        logger.info("   🎊 Wrapped Anual: 31/dez 13:00 (retrospectiva do ano)")
        logger.info("   🧭 Gamificação diário: 00:05")
        logger.info("   🗓️ Gamificação semanal: 00:10")
        logger.info("   📈 Gamificação mensal: dia 1, 00:15")
        
    except Exception as e:
        logger.error(f"❌ Erro ao configurar jobs: {e}")

        job_queue.run_daily(
            job_atualizar_perfis_ia,
            time=time(hour=4, minute=0),
            days=(0,),  # Domingo de madrugada
            name="job_atualizar_perfis_ia_semanal"
        )
