#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 Dashboard Handler - ContaComigo
Handler para integração do dashboard com o bot do Telegram
"""

import os
# Importar analytics
try:
    from analytics.bot_analytics import BotAnalytics
    from analytics.advanced_analytics import advanced_analytics
    analytics = BotAnalytics()
    ANALYTICS_ENABLED = True
except ImportError:
    ANALYTICS_ENABLED = False


from .analytics_utils import track_analytics

import logging
import requests
import traceback
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from .gamification_utils import give_xp_for_action, touch_user_interaction
from database.database import get_db, get_or_create_user
from .monetization import ensure_user_plan_state, plan_allows_feature, upgrade_prompt_for_feature

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('dashboard_handler.log')
    ]
)
logger = logging.getLogger(__name__)

class DashboardHandler:
    """Handler para funcionalidades do dashboard"""
    
    def __init__(self, dashboard_url: str = None):
        # 🚀 CORREÇÃO: Usar variável de ambiente para a URL base do dashboard.
        # Isso torna o código portátil e configurável para qualquer ambiente.
        # Fallback para localhost para desenvolvimento local.
        self.dashboard_url = os.getenv(
            'DASHBOARD_BASE_URL', 
            'http://localhost:5000'
        )
        if dashboard_url: # Permite sobrescrever, se necessário
            self.dashboard_url = dashboard_url
        else:
            logger.info(f"✅ URL do Dashboard configurada para: {self.dashboard_url}")
    
    def verificar_dashboard_online(self) -> bool:
        """Verifica se o dashboard está online"""
        try:
            # ⚠️ Desabilitar verificação para URLs localhost (não funciona no Railway)
            if 'localhost' in self.dashboard_url or '127.0.0.1' in self.dashboard_url:
                logger.warning("⚠️ Dashboard configurado para localhost - verificação desabilitada no Railway")
                return False
            
            response = requests.get(f"{self.dashboard_url}/api/status", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao verificar dashboard: {e}")
            return False
    
    async def gerar_link_dashboard(self, user_id: int) -> dict:
        """Gera link temporário para acesso ao dashboard"""
        try:
            response = requests.get(
                f"{self.dashboard_url}/api/gerar-token/{user_id}", 
                timeout=8
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Erro na API: Status {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Erro ao gerar link do dashboard: {e}")
            return None

async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /dashboard - Gera link para acessar o dashboard web"""
    loading_msg = None
    try:
        logger.info(f"Comando /dashboard iniciado para usuário {update.effective_user.id}")
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        await touch_user_interaction(user_id, context)

        db = next(get_db())
        try:
            usuario_db = get_or_create_user(db, user_id, update.effective_user.full_name)
            ensure_user_plan_state(db, usuario_db, commit=True)
            gate = plan_allows_feature(db, usuario_db, "dashboard_full")
            if not gate.allowed:
                text, keyboard = upgrade_prompt_for_feature("dashboard_full")
                await update.effective_message.reply_html(text, reply_markup=keyboard)
                return
        finally:
            db.close()
        
        # Enviar mensagem de carregamento - usar effective_message para compatibilidade
        try:
            loading_msg = await update.effective_message.reply_text(
                "🔄 Gerando seu link personalizado do dashboard...",
                parse_mode='HTML'
            )
            logger.info("Mensagem de carregamento enviada")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de carregamento: {e}")
            # Fallback: tentar o método alternativo
            loading_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 Gerando seu link personalizado do dashboard...",
                parse_mode='HTML'
            )
            logger.info("Mensagem de carregamento enviada via fallback")
        
        dashboard_handler = DashboardHandler()
        
        # Verificar se dashboard está online
        logger.info("Verificando se dashboard está online...")
        dashboard_online = dashboard_handler.verificar_dashboard_online()
        logger.info(f"Dashboard online: {dashboard_online}")
        
        if not dashboard_online:
            logger.warning("Dashboard está offline")
            await loading_msg.edit_text(
                "❌ <b>Dashboard Indisponível</b>\n\n"
                "O dashboard web está temporariamente fora do ar.\n"
                "Tente novamente em alguns minutos.\n\n"
                "💡 <i>Você pode usar /relatorio para ver seus dados em formato texto.</i>",
                parse_mode='HTML'
            )
            return
        
        version_tag = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        webapp_url = f"{dashboard_handler.dashboard_url}/webapp?v={version_tag}"
        keyboard = [
            [InlineKeyboardButton("🧩 Abrir Miniapp", web_app=WebAppInfo(url=webapp_url))],
            [InlineKeyboardButton("❌ Fechar", callback_data="delete_message")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await loading_msg.edit_text(
            "🧩 <b>Miniapp ContaComigo</b>\n\n"
            "Tudo rapido continua no chat. O resto agora fica no miniapp.\n\n"
            "Abra para acessar: Historico, Editar, Agendamentos, Metas e Gerente IA.\n\n"
            "⚡ Atualizacao automatica a cada 7s.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        try:
            await give_xp_for_action(user_id, "DASHBOARD_VISUALIZADO", context)
        except Exception:
            logger.debug("Falha ao conceder XP do dashboard (nao critico).")
        logger.info("Comando /dashboard executado com sucesso")
        
    except Exception as e:
        logger.error(f"Erro no comando /dashboard: {e}")
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        try:
            if loading_msg:
                await loading_msg.edit_text(
                    "❌ <b>Erro Interno</b>\n\n"
                    "Ocorreu um erro inesperado.\n"
                    "Tente novamente em alguns minutos.\n\n"
                    "💡 <i>Use /relatorio como alternativa.</i>",
                    parse_mode='HTML'
                )
            else:
                # Se não conseguiu criar loading_msg, usar context.bot
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ <b>Erro Interno</b>\n\n"
                         "Ocorreu um erro inesperado.\n"
                         "Tente novamente em alguns minutos.\n\n"
                         "💡 <i>Use /relatorio como alternativa.</i>",
                    parse_mode='HTML'
                )
        except Exception as edit_error:
            logger.error(f"Erro ao editar mensagem de erro: {edit_error}")
            # Se não conseguir editar, enviar nova mensagem via context.bot
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Erro inesperado. Tente novamente.",
                    parse_mode='HTML'
                )
            except Exception as reply_error:
                logger.error(f"Erro ao enviar mensagem de erro: {reply_error}")

async def cmd_dashstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /dashstatus - Verifica status do dashboard"""
    loading_msg = await update.message.reply_text(
        "🔍 Verificando status do dashboard..."
    )
    
    dashboard_handler = DashboardHandler()
    
    # Verificar se dashboard está online
    online = dashboard_handler.verificar_dashboard_online()
    
    if online:
        try:
            response = requests.get(f"{dashboard_handler.dashboard_url}/api/status", timeout=5)
            status_data = response.json() if response.status_code == 200 else {}
            
            uptime = status_data.get('uptime', 'N/A')
            version = status_data.get('version', 'N/A')
            active_sessions = status_data.get('active_sessions', 0)
            
            keyboard = [
                [InlineKeyboardButton("🌐 Acessar Dashboard", url=dashboard_handler.dashboard_url)],
                [InlineKeyboardButton("📱 Ver Demo", url=f"{dashboard_handler.dashboard_url}/dashboard/demo")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(
                f"✅ <b>Dashboard Online</b>\n\n"
                f"🌐 <b>URL:</b> {dashboard_handler.dashboard_url}\n"
                f"⚡ <b>Status:</b> Funcionando\n"
                f"⏱️ <b>Uptime:</b> {uptime}\n"
                f"🔧 <b>Versão:</b> {version}\n"
                f"👥 <b>Sessões Ativas:</b> {active_sessions}\n\n"
                f"📊 O dashboard está funcionando normalmente!",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            await loading_msg.edit_text(
                f"⚠️ <b>Dashboard com Problemas</b>\n\n"
                f"O dashboard está online mas com problemas.\n"
                f"Erro: {str(e)[:100]}...\n\n"
                f"💡 <i>Tente usar /dashboard em alguns minutos.</i>",
                parse_mode='HTML'
            )
    else:
        await loading_msg.edit_text(
            "❌ <b>Dashboard Offline</b>\n\n"
            "O dashboard web não está respondendo.\n"
            "Possíveis causas:\n"
            "• Serviço temporariamente indisponível\n"
            "• Manutenção em andamento\n"
            "• Problema de conectividade\n\n"
            "💡 <i>Tente novamente em alguns minutos ou use /relatorio.</i>",
            parse_mode='HTML'
        )

@track_analytics("dashboard")
async def dashboard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para callbacks dos botões do dashboard"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "dashboard_new_link":
        # Regenerar link
        await cmd_dashboard(update, context)
    elif query.data == "delete_message":
        # Deletar mensagem
        await query.delete_message()
