"""
📈 Investment Handler - Gestão Completa de Investimentos
Gerencia investimentos, rentabilidade, metas e patrimônio
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from database.database import get_db
from models import (
    Usuario, Investment, InvestmentSnapshot, InvestmentGoal, 
    PatrimonySnapshot
)
from sqlalchemy import func, and_, desc

logger = logging.getLogger(__name__)

# Estados da conversa
ADDING_INVESTMENT_NAME, ADDING_INVESTMENT_TYPE, ADDING_INVESTMENT_VALUE = range(3)
ADDING_GOAL_NAME, ADDING_GOAL_VALUE, ADDING_GOAL_DATE = range(3, 6)


# ==================== /investimentos - Lista investimentos ====================

async def investimentos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todos os investimentos do usuário"""
    user_id = update.effective_user.id
    
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        
        if not usuario:
            await update.message.reply_text("❌ Usuário não encontrado.")
            return
        
        # Buscar investimentos ativos
        investments = (
            db.query(Investment)
            .filter(and_(Investment.id_usuario == usuario.id, Investment.ativo == True))
            .order_by(Investment.valor_atual.desc())
            .all()
        )
        
        if not investments:
            message = (
                "📈 *Seus Investimentos*\n\n"
                "Você ainda não tem investimentos cadastrados\\.\n\n"
                "💡 Use /adicionar\\_investimento para começar\\!"
            )
            keyboard = [
                [InlineKeyboardButton("➕ Adicionar Investimento", callback_data="inv_add")],
            ]
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2"
            )
            return
        
        # Calcular totais
        total = sum(float(inv.valor_atual) for inv in investments)
        
        # Montar mensagem
        message = f"📈 *Seus Investimentos*\n\n"
        message += f"💰 *Total:* R$ {total:,.2f}\\n\\n".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Emojis por tipo
        emojis = {
            "CDB": "💎",
            "LCI": "🏠",
            "LCA": "🌾",
            "POUPANCA": "🐷",
            "TESOURO": "🏛",
            "ACAO": "📊",
            "FUNDO": "📦",
            "COFRINHO": "🪙",
            "OUTRO": "💰"
        }
        
        for inv in investments:
            emoji = emojis.get(inv.tipo, "💰")
            valor_fmt = f"R$ {float(inv.valor_atual):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            # Calcular rentabilidade se tiver snapshots
            rentabilidade = ""
            if inv.snapshots:
                ultimo_snapshot = sorted(inv.snapshots, key=lambda x: x.data_snapshot, reverse=True)[0]
                if ultimo_snapshot.rentabilidade_percentual:
                    rent_pct = float(ultimo_snapshot.rentabilidade_percentual)
                    emoji_trend = "📈" if rent_pct > 0 else "📉"
                    rentabilidade = f" {emoji_trend} \\+{rent_pct:.2f}\\%" if rent_pct > 0 else f" {emoji_trend} {rent_pct:.2f}\\%"
            
            message += f"{emoji} *{inv.nome}*\n"
            message += f"   └ {valor_fmt}{rentabilidade}\n"
            
            if inv.banco:
                message += f"   └ 🏦 {inv.banco}\n"
            
            message += "\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Dashboard", callback_data="inv_dashboard"),
                InlineKeyboardButton("🎯 Metas", callback_data="inv_goals")
            ],
            [
                InlineKeyboardButton("➕ Adicionar", callback_data="inv_add"),
                InlineKeyboardButton("💰 Patrimônio", callback_data="inv_patrimony")
            ]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkdownV2"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar investimentos: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Erro ao buscar investimentos. Tente novamente."
        )
    finally:
        db.close()


# ==================== /dashboard_investimentos - Dashboard ====================

async def dashboard_investimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra dashboard completo com rentabilidade"""
    # Pode ser callback ou command
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        user_id = update.effective_user.id
        is_callback = False
    
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        
        if not usuario:
            text = "❌ Usuário não encontrado."
            if is_callback:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Buscar investimentos com snapshots
        investments = (
            db.query(Investment)
            .filter(and_(Investment.id_usuario == usuario.id, Investment.ativo == True))
            .all()
        )
        
        if not investments:
            text = (
                "📊 *Dashboard de Investimentos*\n\n"
                "Você ainda não tem investimentos cadastrados\\."
            )
            if is_callback:
                await query.edit_message_text(text, parse_mode="MarkdownV2")
            else:
                await update.message.reply_text(text, parse_mode="MarkdownV2")
            return
        
        # Calcular métricas
        total_atual = sum(float(inv.valor_atual) for inv in investments)
        total_investido = sum(float(inv.valor_inicial or 0) for inv in investments)
        rentabilidade_total = total_atual - total_investido
        rent_pct = (rentabilidade_total / total_investido * 100) if total_investido > 0 else 0
        
        # Buscar rentabilidade do último mês
        um_mes_atras = date.today() - timedelta(days=30)
        snapshots_mes = (
            db.query(InvestmentSnapshot)
            .join(Investment)
            .filter(
                and_(
                    Investment.id_usuario == usuario.id,
                    InvestmentSnapshot.data_snapshot >= um_mes_atras
                )
            )
            .all()
        )
        
        rent_mes = sum(float(s.rentabilidade_periodo or 0) for s in snapshots_mes)
        
        # Montar dashboard
        message = "📊 *Dashboard de Investimentos*\n\n"
        
        message += f"💰 *Patrimônio Investido*\n"
        message += f"   Total Aplicado: R$ {total_investido:,.2f}\n".replace(",", "X").replace(".", ",").replace("X", ".")
        message += f"   Valor Atual: R$ {total_atual:,.2f}\n\n".replace(",", "X").replace(".", ",").replace("X", ".")
        
        emoji_trend = "📈" if rentabilidade_total >= 0 else "📉"
        message += f"{emoji_trend} *Rentabilidade Total*\n"
        # Escapar caracteres especiais do MarkdownV2 (incluindo +, -)
        rent_pct_str = f"{rent_pct:+.2f}".replace("+", "\\+").replace("-", "\\-")
        message += f"   R$ {abs(rentabilidade_total):,.2f} \\({rent_pct_str}\\%\\)\n\n".replace(",", "X").replace(".", ",").replace("X", ".")
        
        if rent_mes != 0:
            emoji_mes = "📈" if rent_mes >= 0 else "📉"
            message += f"{emoji_mes} *Último Mês*\n"
            message += f"   R$ {abs(rent_mes):,.2f}\n\n".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Top 3 investimentos
        top_investments = sorted(investments, key=lambda x: float(x.valor_atual), reverse=True)[:3]
        
        message += "🏆 *Top Investimentos*\n"
        for i, inv in enumerate(top_investments, 1):
            valor_fmt = f"R$ {float(inv.valor_atual):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            message += f"{i}\\. {inv.nome}: {valor_fmt}\n"
        
        # Distribuição por tipo
        tipos_dist = {}
        for inv in investments:
            tipos_dist[inv.tipo] = tipos_dist.get(inv.tipo, 0) + float(inv.valor_atual)
        
        if len(tipos_dist) > 1:
            message += "\n📦 *Distribuição*\n"
            for tipo, valor in sorted(tipos_dist.items(), key=lambda x: x[1], reverse=True)[:3]:
                pct = (valor / total_atual * 100) if total_atual > 0 else 0
                message += f"   {tipo}: {pct:.1f}\\%\n"
        
        keyboard = [
            [InlineKeyboardButton("📈 Ver Investimentos", callback_data="inv_list")],
            [InlineKeyboardButton("💰 Patrimônio Total", callback_data="inv_patrimony")],
        ]
        
        if is_callback:
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2"
            )
        
    except Exception as e:
        logger.error(f"❌ Erro no dashboard: {e}", exc_info=True)
        text = "❌ Erro ao gerar dashboard."
        if is_callback:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
    finally:
        db.close()


# ==================== /patrimonio - Patrimônio total ====================

async def patrimonio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra patrimônio total (contas + investimentos)"""
    # Pode ser callback ou command
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        user_id = update.effective_user.id
        is_callback = False
    
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        
        if not usuario:
            text = "❌ Usuário não encontrado."
            if is_callback:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Buscar investimentos
        investments = (
            db.query(Investment)
            .filter(and_(Investment.id_usuario == usuario.id, Investment.ativo == True))
            .all()
        )
        total_investimentos = sum(float(inv.valor_atual) for inv in investments)
        total_patrimonio = total_investimentos
        
        # Buscar último snapshot para comparar
        ultimo_snapshot = (
            db.query(PatrimonySnapshot)
            .filter(PatrimonySnapshot.id_usuario == usuario.id)
            .order_by(PatrimonySnapshot.mes_referencia.desc())
            .first()
        )
        
        variacao = None
        variacao_pct = None
        if ultimo_snapshot:
            variacao = total_patrimonio - float(ultimo_snapshot.total_patrimonio)
            if float(ultimo_snapshot.total_patrimonio) > 0:
                variacao_pct = (variacao / float(ultimo_snapshot.total_patrimonio)) * 100
        
        # Montar mensagem
        message = "💎 *Seu Patrimônio*\n\n"
        message += f"📈 *Investimentos*\n"
        message += f"   R$ {total_investimentos:,.2f}\n\n".replace(",", "X").replace(".", ",").replace("X", ".")
        message += f"━━━━━━━━━━━━━━━━━━━━\n"
        message += f"💰 *TOTAL*: R$ {total_patrimonio:,.2f}\n".replace(",", "X").replace(".", ",").replace("X", ".")
        
        if variacao is not None:
            emoji_var = "📈" if variacao >= 0 else "📉"
            sinal = "\\+" if variacao >= 0 else "\\-"  # Escapar + e -
            message += f"{emoji_var} {sinal}R$ {abs(variacao):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            if variacao_pct is not None:
                # Escapar caracteres especiais do MarkdownV2
                variacao_pct_str = f"{variacao_pct:+.2f}".replace("+", "\\+").replace("-", "\\-")
                message += f" \\({variacao_pct_str}\\%\\)"
            
            message += f" desde {ultimo_snapshot.mes_referencia.strftime('%m/%Y')}\n"
        
        # Histórico dos últimos 6 meses
        seis_meses_atras = date.today() - timedelta(days=180)
        snapshots_historico = (
            db.query(PatrimonySnapshot)
            .filter(and_(
                PatrimonySnapshot.id_usuario == usuario.id,
                PatrimonySnapshot.mes_referencia >= seis_meses_atras
            ))
            .order_by(PatrimonySnapshot.mes_referencia.desc())
            .limit(6)
            .all()
        )
        
        if snapshots_historico:
            message += "\n📊 *Evolução \\(últimos 6 meses\\)*\n"
            for snapshot in reversed(snapshots_historico):
                mes_fmt = snapshot.mes_referencia.strftime("%m/%Y")
                valor_fmt = f"R$ {float(snapshot.total_patrimonio):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                if snapshot.variacao_mensal:
                    var = float(snapshot.variacao_mensal)
                    emoji_var = "📈" if var >= 0 else "📉"
                    var_fmt = f"{var:+,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    message += f"{mes_fmt}: {valor_fmt} {emoji_var} {var_fmt}\n"
                else:
                    message += f"{mes_fmt}: {valor_fmt}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📈 Investimentos", callback_data="inv_list"),
                InlineKeyboardButton("💳 Contas", callback_data="inv_accounts")
            ],
            [InlineKeyboardButton("📊 Dashboard", callback_data="inv_dashboard")],
        ]
        
        if is_callback:
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="MarkdownV2"
            )
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular patrimônio: {e}", exc_info=True)
        text = "❌ Erro ao calcular patrimônio."
        if is_callback:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
    finally:
        db.close()


# ==================== Callback Handlers ====================

async def investment_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler central para callbacks de investimento"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "inv_list":
        # Redireciona para lista de investimentos
        context.user_data['from_callback'] = True
        await investimentos_command(update, context)
    
    elif callback_data == "inv_dashboard":
        await dashboard_investimentos(update, context)
    
    elif callback_data == "inv_patrimony":
        await patrimonio_command(update, context)
    
    elif callback_data == "inv_add":
        await query.edit_message_text(
            "➕ Para adicionar um investimento manualmente, use:\n"
            "/adicionar_investimento"
        )
    
    elif callback_data == "inv_goals":
        await query.edit_message_text(
            "🎯 Para gerenciar metas de investimento, use:\n"
            "/metas_investimento"
        )
    
    elif callback_data == "inv_accounts":
        await query.edit_message_text(
            "💳 Para ver suas contas bancárias conectadas, use:\n"
            "/minhas_contas"
        )


# ==================== Exports ====================

def get_investment_handlers():
    """Retorna lista de handlers para registrar no bot"""
    return [
        CommandHandler("investimentos", investimentos_command),
        CommandHandler("dashboard_investimentos", dashboard_investimentos),
        CommandHandler("patrimonio", patrimonio_command),
        CallbackQueryHandler(investment_callback_handler, pattern="^inv_"),
    ]
