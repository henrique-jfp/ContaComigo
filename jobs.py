"""
Sistema de Jobs e Tarefas Agendadas - MaestroFin
"""
import logging
from datetime import datetime, time
from telegram.ext import ContextTypes
from alerts import agendar_notificacoes_diarias, checar_objetivos_semanal
from gerente_financeiro.assistente_proativo import job_assistente_proativo
from gerente_financeiro.wrapped_anual import job_wrapped_anual

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
        
        # Job semanal aos sábados às 10:00 - Verificar objetivos
        job_queue.run_daily(
            checar_objetivos_semanal,
            time=time(hour=10, minute=0),
            days=(6,),  # Sábado
            name="checar_metas_semanalmente"
        )
        

        
        # Job diário às 20:00 - Assistente Proativo (alertas inteligentes)
        job_queue.run_daily(
            job_assistente_proativo,
            time=time(hour=20, minute=0),
            name="assistente_proativo_diario"
        )
        
        # Job anual 31/dez às 13:00 - Wrapped Financeiro do Ano
        from apscheduler.triggers.cron import CronTrigger
        job_queue.run_daily(
            job_wrapped_anual,
            time=time(hour=13, minute=0),
            days=(30,),  # Dia 31 (0-indexed, então 30 = 31)
            name="wrapped_anual_31_dezembro"
        )
        
        logger.info("✅ Jobs agendados configurados com sucesso:")
        logger.info("   📅 Notificações diárias: 01:00")
        logger.info("   🎯 Verificação de metas: Sábado 10:00")

        logger.info("   🤖 Assistente Proativo: 20:00 (alertas inteligentes)")
        logger.info("   🎊 Wrapped Anual: 31/dez 13:00 (retrospectiva do ano)")
        
    except Exception as e:
        logger.error(f"❌ Erro ao configurar jobs: {e}")
