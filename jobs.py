"""
Sistema de Jobs e Tarefas Agendadas - ContaComigo
"""
import logging
from datetime import datetime, time
from telegram.ext import ContextTypes
from alerts import agendar_notificacoes_diarias
from gerente_financeiro.assistente_proativo import job_assistente_proativo, job_resumo_semanal
from gerente_financeiro.wrapped_anual import job_wrapped_anual
from gerente_financeiro.ai_memory_service import job_atualizar_perfis_ia
from alerts import job_metas_mensal
from gerente_financeiro.gamification_missions_service import (
    reset_daily_missions_for_all_users,
    reset_weekly_missions_for_all_users,
    apply_monthly_performance_awards,
)
from database.database import get_db
from models import Usuario
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from gerente_financeiro.monetization import (
    build_trial_usage_summary,
    downgrade_expired_trials_to_free,
    trial_users_expiring_in,
)
from pierre_finance.sync import sincronizar_incremental
from pierre_finance.categorizador_llm import pipeline_categorizacao_pos_ingestao
from fiis.alertas import enviar_alertas_fii

logger = logging.getLogger(__name__)

async def job_sincronizar_pierre_incremental_all_users(context: ContextTypes.DEFAULT_TYPE):
    """Job que sincroniza Open Finance para todos os usuários com chave configurada."""
    logger.info("🔄 Iniciando job de sincronização Open Finance...")
    db = next(get_db())
    try:
        usuarios = db.query(Usuario).filter(Usuario.pierre_api_key.isnot(None)).all()
        for usuario in usuarios:
            try:
                await sincronizar_incremental(usuario, db)
                await pipeline_categorizacao_pos_ingestao(db, usuario.id)
            except Exception as e:
                logger.error(f"Falha ao sincronizar Open Finance para usuário {usuario.id}: {e}")
    finally:
        db.close()
    logger.info("✅ Job de sincronização Open Finance finalizado.")




def configurar_jobs(job_queue):
    """
    Configura todos os jobs agendados do sistema
    """
    # Job mensal: premiação dos 2 primeiros do ranking de XP
    async def job_gamification_monthly_xp_competition(context):
        from datetime import datetime
        if datetime.now().day != 1:
            return
        db = next(get_db())
        try:
            from gerente_financeiro.gamification_missions_service import award_monthly_xp_competition_premium
            premiados = award_monthly_xp_competition_premium(db)
            logger.info(f"🏆 Premiação mensal XP: {premiados} usuários receberam 1 mês de premium.")
        finally:
            db.close()

    try:
        logger.info("⚙️ Configurando jobs agendados...")
        job_queue.run_daily(
            job_gamification_monthly_xp_competition,
            time=time(hour=0, minute=20),
            name="gamification_monthly_xp_competition"
        )
        # Job diário às 01:00 - Agendamento de notificações
        job_queue.run_daily(
            agendar_notificacoes_diarias,
            time=time(hour=1, minute=0),
            name="agendador_mestre_diario"
        )
        
        # Job diário às 08:00 - Alertas de FIIs
        async def job_alertas_fii_diario(context: ContextTypes.DEFAULT_TYPE):
            await enviar_alertas_fii(context.application, lambda: next(get_db()))

        job_queue.run_daily(
            job_alertas_fii_diario,
            time=time(hour=8, minute=0),
            name="alertas_fii_diario"
        )

        # Job diario que roda no dia 1 - Check-in mensal de metas
        job_queue.run_daily(
            job_metas_mensal,
            time=time(hour=10, minute=0),
            name="metas_checkin_mensal"
        )
        
        # Job de sincronização Open Finance a cada 6 horas
        job_queue.run_repeating(
            job_sincronizar_pierre_incremental_all_users,
            interval=6 * 3600, # 6 horas em segundos
            first=60, # Começa 1 minuto após o boot
            name="open_finance_sync_repeating"
        )
        

        
        # Job semanal aos Domingos às 19:00 - Resumo Financeiro da Semana
        job_queue.run_daily(
            job_resumo_semanal,
            time=time(hour=19, minute=0),
            days=(6,), # 6 = Domingo
            name="resumo_semanal_domingo"
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

        async def job_trial_monetizacao(context: ContextTypes.DEFAULT_TYPE):
            db = next(get_db())
            try:
                # Alerta 72h (3 dias) - TRIAL
                users_72h = trial_users_expiring_in(db, days=3)
                for user in users_72h:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Faltam 72 horas para seu teste grátis expirar!</b>\n\n"
                                "O Alfredo está adorando te ajudar a organizar as contas. "
                                "Não deixe o ritmo cair! Assine o Premium para manter todos os recursos liberados."
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Seja Premium Agora", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Erro alerta 72h para {user.telegram_id}: {e}")

                # Alerta 72h (3 dias) - PREMIUM
                from gerente_financeiro.monetization import premium_users_expiring_in
                premium_72h = premium_users_expiring_in(db, days=3)
                for user in premium_72h:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Sua assinatura Premium expira em 72 horas!</b>\n\n"
                                "Garante a renovação para não perder acesso aos gráficos avançados e OCR ilimitado."
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Renovar Premium", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Erro alerta premium 72h para {user.telegram_id}: {e}")

                # Alerta 48h (2 dias) - TRIAL
                users_48h = trial_users_expiring_in(db, days=2)
                for user in users_48h:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Faltam 48 horas para seu teste grátis expirar!</b>\n\n"
                                "Ainda dá tempo de garantir sua assinatura Premium e continuar com "
                                "lançamentos ilimitados, OCR e a inteligência total do Alfredo."
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Seja Premium Agora", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Erro alerta 48h para {user.telegram_id}: {e}")

                # Alerta 48h (2 dias) - PREMIUM
                premium_48h = premium_users_expiring_in(db, days=2)
                for user in premium_48h:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Sua assinatura Premium expira em 48 horas!</b>\n\n"
                                "Não fique sem o Alfredo! Renove agora e mantenha seu dashboard completo ativo."
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Renovar Premium", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Erro alerta premium 48h para {user.telegram_id}: {e}")

                # Alerta 24h (1 dia) - TRIAL
                users_expiring_tomorrow = trial_users_expiring_in(db, days=1)
                for user in users_expiring_tomorrow:
                    resumo = build_trial_usage_summary(db, user)
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Faltam 24 horas para seu teste grátis expirar!</b>\n\n"
                                "Nestes 15 dias você:\n"
                                f"• Registrou {resumo['lancamentos']} lançamentos\n"
                                f"• Criou {resumo['metas']} metas\n"
                                f"• Usou o Alfredo {resumo['ia_questions']} vezes\n\n"
                                "Amanhã você escolhe: continua com tudo por R$ 12,90/mês "
                                "ou segue no free tier. Seus dados ficam intactos."
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Seja Premium Agora", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as send_err:
                        logger.warning("Falha ao enviar aviso de trial para %s: %s", user.telegram_id, send_err)
                
                # Alerta 24h (1 dia) - PREMIUM
                premium_24h = premium_users_expiring_in(db, days=1)
                for user in premium_24h:
                    try:
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "⏳ <b>Sua assinatura Premium expira em 24 horas!</b>\n\n"
                                "Amanhã você retornará ao plano Free. Renove hoje para manter todos os seus benefícios!"
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("💎 Renovar Premium", callback_data="plan_choose_premium_monthly")]
                            ])
                        )
                    except Exception as e:
                        logger.warning(f"Erro alerta premium 24h para {user.telegram_id}: {e}")

                users_expired = downgrade_expired_trials_to_free(db)
                for user in users_expired:
                    try:
                        keyboard = InlineKeyboardMarkup(
                            [
                                [InlineKeyboardButton("💎 Premium Mensal — R$ 12,90/mês", callback_data="plan_choose_premium_monthly")],
                                [InlineKeyboardButton("📅 Premium Anual — R$ 129,00/ano", callback_data="plan_choose_premium_annual")],
                                [InlineKeyboardButton("Continuar no Free Tier", callback_data="plan_choose_free")],
                            ]
                        )
                        await context.bot.send_message(
                            chat_id=user.telegram_id,
                            parse_mode="HTML",
                            text=(
                                "📊 <b>Seu trial encerrou. Como quer continuar?</b>\n\n"
                                "Escolha seu plano para seguir com o ContaComigo:"
                            ),
                            reply_markup=keyboard,
                        )
                    except Exception as send_err:
                        logger.warning("Falha ao enviar escolha de plano para %s: %s", user.telegram_id, send_err)
            finally:
                db.close()

        job_queue.run_daily(
            job_trial_monetizacao,
            time=time(hour=9, minute=0),
            name="trial_monetizacao_diario"
        )
        
        logger.info("✅ Jobs agendados configurados com sucesso:")
        logger.info("   📅 Notificações diárias: 01:00")
        logger.info("   🎯 Check-in de metas: dia 1, 10:00")

        logger.info("   🤖 Assistente Proativo: 20:00 (alertas inteligentes)")
        logger.info("   🎊 Wrapped Anual: 31/dez 13:00 (retrospectiva do ano)")
        logger.info("   🧭 Gamificação diário: 00:05")
        logger.info("   🗓️ Gamificação semanal: 00:10")
        logger.info("   📈 Gamificação mensal: dia 1, 00:15")
        logger.info("   💰 Monetização trial: 09:00")

        job_queue.run_daily(
            job_atualizar_perfis_ia,
            time=time(hour=4, minute=0),
            days=(0,),  # Domingo de madrugada
            name="job_atualizar_perfis_ia_semanal"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao configurar jobs: {e}")
