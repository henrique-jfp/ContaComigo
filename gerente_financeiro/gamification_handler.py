# gerente_financeiro/gamification_handler.py
import logging
from sqlalchemy.orm import Session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database import get_db
from models import Usuario, Lancamento
from .gamification_service import LEVELS, award_xp
from .gamification_utils import give_xp_for_action, touch_user_interaction
from datetime import datetime, timedelta
from sqlalchemy import func
import random

logger = logging.getLogger(__name__)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎮 PERFIL GAMER ULTRA PERSONALIZADO - Sistema viciante!"""
    user_id = update.effective_user.id
    db: Session = next(get_db())
    try:
        await touch_user_interaction(user_id, context)
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario:
            await update.message.reply_text("❌ Usuário não encontrado. Use /start para começar sua jornada!")
            return

        # 🎯 DADOS PERSONALIZADOS
        nome_display = update.effective_user.first_name or usuario.nome_completo.split(' ')[0] if usuario.nome_completo else "Champion"
        level_info = LEVELS.get(usuario.level, {})
        next_level_info = LEVELS.get(usuario.level + 1)
        
        # 🎨 EMOJIS DINÂMICOS BASEADOS NO NÍVEL
        level_emojis = {
            1: "🌱", 2: "🌿", 3: "🌳", 4: "🦅", 5: "⚡", 
            6: "🔥", 7: "💎", 8: "🌟", 9: "👑", 10: "🚀"
        }
        user_emoji = level_emojis.get(usuario.level, "🏆")
        
        # 📊 BARRA DE PROGRESSO ANIMADA
        if next_level_info:
            xp_atual = usuario.xp
            xp_necessario = next_level_info["xp_necessario"]
            xp_anterior = LEVELS.get(usuario.level, {}).get("xp_necessario", 0)
            
            # Progresso no nível atual
            xp_progresso = xp_atual - xp_anterior
            xp_meta = xp_necessario - xp_anterior
            
            progresso_percent = int((xp_progresso / xp_meta) * 100) if xp_meta > 0 else 100
            progresso_bars = progresso_percent // 10
            
            # 🎨 BARRA VISUAL ÉPICA
            filled_bar = "🟩" * progresso_bars
            empty_bar = "⬜" * (10 - progresso_bars)
            progress_bar = filled_bar + empty_bar
            
            xp_faltante = xp_necessario - xp_atual
            progress_text = f"📊 PROGRESSO PARA NÍVEL {usuario.level + 1}\n{progress_bar} {progresso_percent}%\n💫 Faltam apenas {xp_faltante} XP para subir!"
        else:
            progress_text = f"👑 NÍVEL MÁXIMO ALCANÇADO!\n⭐ {usuario.xp} XP - Você é uma LENDA!"
        
        # 🔥 STREAK VISUAL
        streak_visual = ""
        if usuario.streak_dias >= 30:
            streak_visual = "🔥💎 STREAK DIAMANTE! 💎🔥"
        elif usuario.streak_dias >= 14:
            streak_visual = "🔥⚡ STREAK DE FOGO! ⚡🔥"
        elif usuario.streak_dias >= 7:
            streak_visual = "🔥 STREAK QUENTE! 🔥"
        elif usuario.streak_dias >= 3:
            streak_visual = "📈 STREAK CRESCENDO! 📈"
        else:
            streak_visual = "🌱 COMEÇANDO O STREAK 🌱"
        
        # 💰 ESTATÍSTICAS DETALHADAS
        total_transacoes = db.query(func.count(Lancamento.id)).filter(
            Lancamento.id_usuario == usuario.id
        ).scalar() or 0
        
        # Transações esta semana
        uma_semana_atras = datetime.now() - timedelta(days=7)
        transacoes_semana = db.query(func.count(Lancamento.id)).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.data_transacao >= uma_semana_atras
        ).scalar() or 0
        
        # 🏆 CONQUISTAS PERSONALIZADAS
        conquistas_desbloqueadas = []
        conquistas_proximas = []
        
        # Sistema de conquistas baseado em dados reais
        if total_transacoes >= 100:
            conquistas_desbloqueadas.append("💰 Mestre das Finanças (100+ transações)")
        elif total_transacoes >= 50:
            conquistas_desbloqueadas.append("📊 Analista Financeiro (50+ transações)")
        elif total_transacoes >= 10:
            conquistas_desbloqueadas.append("📝 Iniciante Dedicado (10+ transações)")
        else:
            conquistas_proximas.append(f"📝 Registre {10 - total_transacoes} transações para 'Iniciante Dedicado'")
            
        if usuario.streak_dias >= 30:
            conquistas_desbloqueadas.append("🔥 Streak Master (30 dias)")
        elif usuario.streak_dias >= 7:
            conquistas_desbloqueadas.append("📈 Consistente (7+ dias)")
        else:
            conquistas_proximas.append(f"🔥 Mantenha por {7 - usuario.streak_dias} dias para 'Consistente'")
            
        if usuario.level >= 5:
            conquistas_desbloqueadas.append("⚡ Elite Player (Nível 5+)")
        elif usuario.level >= 3:
            conquistas_desbloqueadas.append("🌳 Veterano (Nível 3+)")
        else:
            conquistas_proximas.append("⚡ Continue ganhando XP para chegar ao Elite!")
        
        # 🎮 TÍTULO ÉPICO BASEADO NO DESEMPENHO
        if total_transacoes > 100 and usuario.streak_dias > 30:
            titulo_especial = "🏆 LENDÁRIO DO CONTROLE FINANCEIRO"
        elif total_transacoes > 50 and usuario.streak_dias > 14:
            titulo_especial = "💎 MESTRE DAS FINANÇAS"
        elif usuario.level >= 5:
            titulo_especial = "⚡ ESPECIALISTA FINANCEIRO"
        elif usuario.streak_dias >= 7:
            titulo_especial = "🔥 DEDICADO FINANCEIRO"
        else:
            titulo_especial = "🌱 APRENDIZ EM ASCENSÃO"
        
        # 🎲 FRASE MOTIVACIONAL ALEATÓRIA
        frases_motivacionais = [
            "💪 Você está dominando suas finanças!",
            "🚀 Rumo ao próximo nível!",
            "⭐ Cada transação te deixa mais forte!",
            "🔥 Seu streak está pegando fogo!",
            "💎 Transforme dados em diamantes!",
            "🏆 Champions controlam o dinheiro!",
            "⚡ Energia financeira em alta!"
        ]
        frase_motivacional = random.choice(frases_motivacionais)
        
        # 🎨 MENSAGEM ÉPICA PERSONALIZADA
        mensagem = (
            f"╭─────────────────────╮\n"
            f"│  🎮 SEU PERFIL GAMER  │\n"
            f"╰─────────────────────╯\n\n"
            f"{user_emoji} <b>{nome_display.upper()}</b>\n"
            f"🏅 {titulo_especial}\n"
            f"🏆 Nível {usuario.level} - {level_info.get('titulo', 'Novato')}\n"
            f"⭐ <b>{usuario.xp:,} XP</b> acumulados\n"
            f"📊 <b>{total_transacoes}</b> transações registradas\n"
            f"📅 <b>{transacoes_semana}</b> esta semana\n\n"
            f"{streak_visual}\n"
            f"🔥 <b>{usuario.streak_dias} DIAS</b> consecutivos\n\n"
            f"{progress_text}\n\n"
        )
        
        # 🏆 SEÇÃO DE CONQUISTAS
        if conquistas_desbloqueadas:
            mensagem += "🏆 <b>CONQUISTAS DESBLOQUEADAS:</b>\n"
            for conquista in conquistas_desbloqueadas[-3:]:  # Últimas 3
                mensagem += f"✅ {conquista}\n"
            mensagem += "\n"
        
        if conquistas_proximas:
            mensagem += "🎯 <b>PRÓXIMAS CONQUISTAS:</b>\n"
            for conquista in conquistas_proximas[:2]:  # 2 primeiras
                mensagem += f"🎯 {conquista}\n"
            mensagem += "\n"
        
        mensagem += f"💭 {frase_motivacional}\n\n"
        mensagem += "🎮 <b>Use os botões abaixo para explorar mais!</b>"
        
        # 🎨 TECLADO INTERATIVO ÉPICO
        keyboard = [
            [
                InlineKeyboardButton("🏆 Rankings Globais", callback_data="show_rankings"),
                InlineKeyboardButton("📊 Estatísticas Pro", callback_data="show_stats")
            ],
            [
                InlineKeyboardButton("💎 Sistema de Recompensas", callback_data="show_rewards"),
                InlineKeyboardButton("🏅 Conquistas", callback_data="show_achievements")
            ],
            [
                InlineKeyboardButton("🎯 Desafios Diários", callback_data="show_challenges")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(mensagem, reply_markup=reply_markup)
        try:
            await give_xp_for_action(user_id, "PERFIL_VISUALIZADO", context)
        except Exception:
            logger.debug("Falha ao conceder XP de perfil (nao critico).")

    finally:
        db.close()

async def show_rankings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🏆 RANKINGS GLOBAIS SUPER COMPETITIVOS - Sistema viciante!"""
    user_id = update.effective_user.id
    db: Session = next(get_db())
    try:
        await touch_user_interaction(user_id, context)
        # Ranking de XP Global
        top_10_xp = db.query(Usuario).order_by(Usuario.xp.desc()).limit(10).all()
        
        # 🎨 HEADER ÉPICO
        ranking_str = (
            "╭─────────────────────╮\n"
            "│ 🏆 HALL DA FAMA 🏆 │\n"
            "╰─────────────────────╯\n\n"
            "🔥 <b>TOP PLAYERS DO MUNDO!</b> 🔥\n\n"
        )
        
        # 🏆 TROFÉUS ESPECIAIS
        trophy_emojis = ["🥇", "🥈", "🥉"]
        
        for i, u in enumerate(top_10_xp):
            level_info = LEVELS.get(u.level, {})
            
            # Emoji especial para posições
            if i < 3:
                emoji = trophy_emojis[i]
                rank_style = "<b>"
                rank_end = "</b>"
            else:
                emoji = f"🔹 {i+1}º"
                rank_style = ""
                rank_end = ""
            
            nome = u.nome_completo.split(' ')[0] if u.nome_completo else f"Player{u.id}"
            
            # 🌟 DESTAQUE ESPECIAL PARA O USUÁRIO
            if u.telegram_id == user_id:
                ranking_str += f"{emoji} {rank_style}⭐ {nome} (VOCÊ!) ⭐{rank_end}\n"
                ranking_str += f"     🏆 Nível {u.level} | ⭐ {u.xp:,} XP | 🔥 {u.streak_dias} dias\n\n"
            else:
                ranking_str += f"{emoji} {rank_style}{nome}{rank_end}\n"
                ranking_str += f"     🏆 Nível {u.level} | ⭐ {u.xp:,} XP | 🔥 {u.streak_dias} dias\n\n"

        # 📊 POSIÇÃO DO USUÁRIO SE NÃO ESTIVER NO TOP 10
        todos_usuarios = db.query(Usuario.telegram_id, Usuario.xp).order_by(Usuario.xp.desc()).all()
        try:
            posicao = [u.telegram_id for u in todos_usuarios].index(user_id) + 1
            usuario_atual = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
            
            if posicao > 10:
                ranking_str += "⬇️ ─────────────────── ⬇️\n\n"
                ranking_str += f"🎯 <b>SUA POSIÇÃO: #{posicao}</b>\n"
                ranking_str += f"🏆 Nível {usuario_atual.level} | ⭐ {usuario_atual.xp:,} XP\n"
                ranking_str += f"📈 Continue subindo no ranking!\n\n"
        except (ValueError, AttributeError):
            ranking_str += "\n🎯 <b>Sua posição aparecerá aqui quando ganhar XP!</b>\n\n"

        ranking_str += "═══════════════════════\n\n"
        ranking_str += "💵 <b>RANKING SEMANAL DE ECONOMIA</b>\n"
        ranking_str += "🚧 Em desenvolvimento! Grandes novidades chegando!\n\n"
        ranking_str += "💡 <i>Dica: Use /perfil para ver seu progresso detalhado!</i>"

        await update.message.reply_html(ranking_str)
        try:
            await give_xp_for_action(user_id, "RANKING_VISUALIZADO", context)
        except Exception:
            logger.debug("Falha ao conceder XP de ranking (nao critico).")

    finally:
        db.close()

async def handle_gamification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎮 SISTEMA DE CALLBACKS ULTRA INTERATIVO"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db: Session = next(get_db())
    
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario:
            await query.edit_message_text("❌ Usuário não encontrado.")
            return
        
        if query.data == "show_rankings":
            # 🏆 RANKINGS SUPER COMPETITIVOS
            top_10_xp = db.query(Usuario).order_by(Usuario.xp.desc()).limit(10).all()
            
            ranking_str = "🏆 <b>HALL DA FAMA GLOBAL</b> 🏆\n\n"
            
            for i, u in enumerate(top_10_xp):
                emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"🔹 {i+1}º"
                nome = u.nome_completo.split(' ')[0] if u.nome_completo else f"Player{u.id}"
                
                if u.telegram_id == user_id:
                    ranking_str += f"{emoji} <b>⭐ {nome} (VOCÊ!) ⭐</b>\n"
                    ranking_str += f"     🏆 Nível {u.level} | ⭐ {u.xp:,} XP\n\n"
                else:
                    ranking_str += f"{emoji} {nome}\n"
                    ranking_str += f"     🏆 Nível {u.level} | ⭐ {u.xp:,} XP\n\n"
            
            ranking_str += "💪 <b>Continue evoluindo para chegar ao topo!</b>"
            await query.edit_message_text(ranking_str, parse_mode='HTML')
            
        elif query.data == "show_stats":
            # 📊 ESTATÍSTICAS ULTRA DETALHADAS
            total_transacoes = db.query(func.count(Lancamento.id)).filter(
                Lancamento.id_usuario == usuario.id
            ).scalar() or 0
            
            # Transações última semana
            uma_semana_atras = datetime.now() - timedelta(days=7)
            transacoes_semana = db.query(func.count(Lancamento.id)).filter(
                Lancamento.id_usuario == usuario.id,
                Lancamento.data_transacao >= uma_semana_atras
            ).scalar() or 0
            
            # Transações último mês
            um_mes_atras = datetime.now() - timedelta(days=30)
            transacoes_mes = db.query(func.count(Lancamento.id)).filter(
                Lancamento.id_usuario == usuario.id,
                Lancamento.data_transacao >= um_mes_atras
            ).scalar() or 0
            
            nome_display = query.from_user.first_name or "Champion"
            
            stats_str = (
                f"╭─────────────────────╮\n"
                f"│ 📊 ESTATÍSTICAS PRO │\n"
                f"╰─────────────────────╯\n\n"
                f"👤 <b>{nome_display.upper()}</b>\n"
                f"🏆 Nível <b>{usuario.level}</b>\n"
                f"⭐ <b>{usuario.xp:,} XP</b> Total\n"
                f"🔥 Streak: <b>{usuario.streak_dias} dias</b>\n\n"
                f"📊 <b>HISTÓRICO DE ATIVIDADE:</b>\n"
                f"📝 Total: <b>{total_transacoes}</b> transações\n"
                f"📅 Esta semana: <b>{transacoes_semana}</b>\n"
                f"📆 Este mês: <b>{transacoes_mes}</b>\n\n"
                f"🎯 <b>PERFORMANCE:</b>\n"
                f"📈 Média semanal: <b>{transacoes_semana}</b> transações\n"
                f"⚡ Consistência: {'🔥 Excelente!' if usuario.streak_dias >= 7 else '📈 Melhorando!'}\n\n"
                f"💪 <b>Continue assim para dominar suas finanças!</b>"
            )
            
            await query.edit_message_text(stats_str, parse_mode='HTML')
            
        elif query.data == "show_rewards":
            # 💎 SISTEMA DE RECOMPENSAS ULTRA COMPLETO
            rewards_str = (
                f"╭─────────────────────╮\n"
                f"│ 💎 SISTEMA DE XP 💎 │\n"
                f"╰─────────────────────╯\n\n"
                f"🎯 <b>COMO GANHAR XP:</b>\n\n"
                
                f"📝 <b>LANÇAMENTOS & REGISTROS:</b>\n"
                f"• Registrar transação: <b>+10 XP</b>\n"
                f"• Registrar por áudio: <b>+15 XP</b>\n"
                f"• Usar OCR (foto/cupom): <b>+25 XP</b>\n"
                f"• Processar fatura PDF: <b>+50 XP</b>\n"
                f"• Editar transação: <b>+5 XP</b>\n"
                f"• Excluir transação: <b>+2 XP</b>\n\n"
                
                f"🤖 <b>INTELIGÊNCIA ARTIFICIAL:</b>\n"
                f"• Pergunta simples para IA: <b>+5 XP</b>\n"
                f"• Análise complexa: <b>+15 XP</b>\n"
                f"• Sessão longa (5+ perguntas): <b>+25 XP</b>\n\n"
                
                f"📊 <b>VISUALIZAÇÕES & RELATÓRIOS:</b>\n"
                f"• Gerar gráfico: <b>+15 XP</b>\n"
                f"• Relatório mensal: <b>+30 XP</b>\n"
                f"• Relatório personalizado: <b>+25 XP</b>\n"
                f"• Acessar dashboard web: <b>+8 XP</b>\n\n"
                
                f"🎯 <b>METAS & PLANEJAMENTO:</b>\n"
                f"• Criar meta: <b>+20 XP</b>\n"
                f"• Check-in mensal: <b>+35 XP</b>\n"
                f"• Atingir meta: <b>+200 XP</b>\n"
                f"• Bonus 100%: <b>+100 XP</b>\n"
                f"• Superar meta (10%+): <b>+150 XP</b>\n"
                f"• Criar agendamento: <b>+15 XP</b>\n\n"
                
                f"🔥 <b>MULTIPLICADORES ATIVOS:</b>\n"
                f"� Nível {usuario.level}: <b>+{int((LEVELS.get(usuario.level, {}).get('multiplicador', 1.0) - 1) * 100)}% XP</b>\n"
            )
            
            # Mostrar multiplicador de streak
            if usuario.streak_dias >= 30:
                rewards_str += f"💎 Streak {usuario.streak_dias} dias: <b>+100% XP BONUS!</b>\n"
            elif usuario.streak_dias >= 14:
                rewards_str += f"🔥 Streak {usuario.streak_dias} dias: <b>+50% XP BONUS!</b>\n"
            elif usuario.streak_dias >= 7:
                rewards_str += f"📈 Streak {usuario.streak_dias} dias: <b>+25% XP BONUS!</b>\n"
            else:
                rewards_str += f"🌱 Streak {usuario.streak_dias} dias: <b>Sem bonus ainda</b>\n"
            
            rewards_str += (
                f"\n� <b>BÔNUS ESPECIAIS:</b>\n"
                f"• Primeira interação do dia: <b>+15 XP</b>\n"
                f"• Primeira semana completa: <b>+100 XP</b>\n"
                f"• Primeiro mês completo: <b>+250 XP</b>\n"
                f"• Dar feedback útil: <b>+20 XP</b>\n\n"
                
                f"🎯 <b>PRÓXIMOS OBJETIVOS:</b>\n"
            )
            
            # Mostrar próximos bônus de streak
            if usuario.streak_dias < 7:
                rewards_str += f"📈 Mantenha por {7 - usuario.streak_dias} dias para +25% XP!\n"
            elif usuario.streak_dias < 14:
                rewards_str += f"🔥 Mantenha por {14 - usuario.streak_dias} dias para +50% XP!\n"
            elif usuario.streak_dias < 30:
                rewards_str += f"💎 Mantenha por {30 - usuario.streak_dias} dias para +100% XP!\n"
            else:
                rewards_str += f"👑 Você já tem o máximo bonus de streak!\n"
            
            rewards_str += f"\n💪 <b>Cada ação conta para sua evolução financeira!</b>"
            
            await query.edit_message_text(rewards_str, parse_mode='HTML')
            
        elif query.data == "show_achievements":
            # 🏅 SISTEMA DE CONQUISTAS
            total_transacoes = db.query(func.count(Lancamento.id)).filter(
                Lancamento.id_usuario == usuario.id
            ).scalar() or 0
            
            achievements_str = (
                f"╭─────────────────────╮\n"
                f"│ 🏅 SUAS CONQUISTAS 🏅│\n"
                f"╰─────────────────────╯\n\n"
            )
            
            # Conquistas desbloqueadas
            unlocked = []
            locked = []
            
            if total_transacoes >= 100:
                unlocked.append("💰 Mestre das Finanças (100+ transações)")
            else:
                locked.append(f"🔒 Mestre das Finanças ({total_transacoes}/100)")
                
            if usuario.streak_dias >= 30:
                unlocked.append("🔥 Streak Master (30+ dias)")
            else:
                locked.append(f"🔒 Streak Master ({usuario.streak_dias}/30)")
                
            if usuario.level >= 5:
                unlocked.append("⚡ Elite Player (Nível 5+)")
            else:
                locked.append(f"🔒 Elite Player (Nível {usuario.level}/5)")
            
            if unlocked:
                achievements_str += "✅ <b>DESBLOQUEADAS:</b>\n"
                for achievement in unlocked:
                    achievements_str += f"🏆 {achievement}\n"
                achievements_str += "\n"
            
            if locked:
                achievements_str += "🎯 <b>EM PROGRESSO:</b>\n"
                for achievement in locked:
                    achievements_str += f"📈 {achievement}\n"
                achievements_str += "\n"
            
            achievements_str += "💪 <b>Continue evoluindo para desbloquear mais!</b>"
            
            await query.edit_message_text(achievements_str, parse_mode='HTML')
            
        elif query.data == "show_challenges":
            # 🎯 DESAFIOS DIÁRIOS
            challenges_str = (
                f"╭─────────────────────╮\n"
                f"│ 🎯 DESAFIOS DIÁRIOS │\n"
                f"╰─────────────────────╯\n\n"
                f"🔥 <b>MISSÕES DE HOJE:</b>\n\n"
                f"📝 Registre 3 transações (+30 XP)\n"
                f"💬 Use a IA 2 vezes (+20 XP)\n"
                f"📊 Gere 1 gráfico (+15 XP)\n"
                f"🔥 Mantenha seu streak (+10 XP)\n\n"
                f"🎁 <b>BÔNUS SEMANAL:</b>\n"
                f"🏆 Complete 7 dias seguidos\n"
                f"💎 Ganhe <b>100 XP EXTRA!</b>\n\n"
                f"⏰ <b>Reinicia em:</b> Meia-noite\n\n"
                f"💪 <b>Aceite o desafio e domine suas finanças!</b>"
            )
            
            await query.edit_message_text(challenges_str, parse_mode='HTML')
            
    finally:
        db.close()
