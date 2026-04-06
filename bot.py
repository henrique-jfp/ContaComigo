import logging
import warnings
import google.generativeai as genai
import os
import re
import functools
from datetime import time, datetime
from telegram import Update
from telegram.warnings import PTBUserWarning
import threading
from flask import Flask, jsonify
import inspect

# 🔐 CARREGAR SECRET FILES PRIMEIRO
try:
    from secret_loader import setup_environment
    setup_environment()
    logging.info("✅ Secret Files carregado com sucesso")
except ImportError:
    logging.warning("⚠️ secret_loader não encontrado")
except Exception as e:
    logging.error(f"❌ Erro ao carregar Secret Files: {e}")

# Suprimir warnings do python-telegram-bot

# Suprimir warnings do python-telegram-bot
warnings.filterwarnings("ignore", category=PTBUserWarning, module="telegram")

# 🚀 INICIALIZAR OCR
try:
    from gerente_financeiro.ocr_handler import setup_google_credentials
    setup_success = setup_google_credentials()
    if setup_success:
        logging.info("✅ OCR: Credenciais Google Vision configuradas")
    else:
        logging.warning("⚠️ OCR: Usando apenas fallback Gemini")
except Exception as ocr_init_error:
    logging.error(f"❌ OCR: Erro na inicialização - {ocr_init_error}")

# Inicializar Analytics
try:
    if os.getenv('DATABASE_URL'):  # Render
        from analytics.bot_analytics_postgresql import get_analytics, track_command
        analytics = get_analytics()
        logging.info("✅ Analytics PostgreSQL integrado (RENDER)")
    else:  # Local
        from analytics.bot_analytics import BotAnalytics, track_command
        analytics = BotAnalytics()
        logging.info("✅ Analytics SQLite integrado (LOCAL)")
    
    ANALYTICS_ENABLED = True
except ImportError as e:
    ANALYTICS_ENABLED = False
    logging.warning(f"⚠️ Analytics não disponível: {e}")

def track_analytics(command_name):
    """Decorator avançado para tracking de comandos"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, context):
            if ANALYTICS_ENABLED and update.effective_user:
                user_id = update.effective_user.id
                username = update.effective_user.username or update.effective_user.first_name or "Usuário"
                
                start_time = datetime.now()
                success = True
                error_details = None
                
                try:
                    # Executar comando
                    result = await func(update, context)
                    
                    # Calcular tempo de execução
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    
                    # Registrar sucesso
                    analytics.track_command_usage(
                        user_id=user_id,
                        username=username,
                        command=command_name,
                        success=True,
                        execution_time_ms=int(execution_time)
                    )
                    
                    # track_daily_user() removido - método não existe
                    
                    logging.info(f"📊 Analytics: {username} usou /{command_name} ({execution_time:.0f}ms)")
                    return result
                    
                except Exception as e:
                    success = False
                    error_details = str(e)
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    
                    # Registrar falha
                    analytics.track_command_usage(
                        user_id=user_id,
                        username=username,
                        command=command_name,
                        success=False,
                        execution_time_ms=int(execution_time)
                    )
                    
                    # Log detalhado do erro
                    if hasattr(analytics, 'log_error'):
                        import traceback
                        analytics.log_error(
                            error_type=type(e).__name__,
                            error_message=str(e),
                            stack_trace=traceback.format_exc(),
                            user_id=user_id,
                            username=username,
                            command=command_name
                        )
                    
                    logging.error(f"❌ Erro no comando /{command_name}: {e}")
                    raise  # Re-propagar o erro
                    
            else:
                # Executar sem analytics
                return await func(update, context)
                
        return wrapper
    return decorator

# Health check server
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "service": "ContaComigo Bot"})

@health_app.route('/')
def home():
    return jsonify({
        "service": "ContaComigo Bot",
        "status": "running",
        "version": "3.1.0"
    })

from sqlalchemy.orm import Session, joinedload
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, ApplicationBuilder, ContextTypes
)

# --- IMPORTS DO PROJETO ---
import config
from database.database import get_db, popular_dados_iniciais, criar_tabelas
from models import *
from alerts import schedule_alerts
from jobs import configurar_jobs
from gerente_financeiro.menu_botoes import BOTAO_LANCAMENTO, BOTAO_GERENTE, BOTAO_EDITAR, BOTAO_CONFIG, BOTAO_FATURA, BOTAO_GRAFICOS, BOTAO_AGENDAMENTOS, BOTAO_METAS, BOTAO_RANKING, BOTAO_NIVEL, BOTAO_CANCELAR, BOTAO_CONTATO, toggle_painel_command

# --- IMPORTS DOS HANDLERS (AGORA ORGANIZADOS) ---
from gerente_financeiro.handlers import (

    create_gerente_conversation_handler, 
    create_cadastro_email_conversation_handler,
    handle_action_button_callback,
    help_callback,  
    help_command,
    cancel,
    painel_notificacoes
)
from gerente_financeiro.agendamentos_handler import (
    agendamento_start, agendamento_conv, agendamento_menu_callback, cancelar_agendamento_callback
)
from gerente_financeiro.metas_handler import (
    metas_conv, metas_callbacks, metas_start
)
from gerente_financeiro.onboarding_handler import configurar_conv, start_onboarding, configurar_start
from gerente_financeiro.editing_handler import edit_conv
from gerente_financeiro.graficos import grafico_conv
from gerente_financeiro.relatorio_handler import relatorio_handler
from gerente_financeiro.manual_entry_handler import manual_entry_conv, manual_entry_start
from gerente_financeiro.fatura_handler import fatura_conv, fatura_start, fatura_receive_file, fatura_confirm
from gerente_financeiro.ocr_handler import ocr_action_processor, ocr_iniciar_como_subprocesso
from gerente_financeiro.quick_entry_handler import quick_action_handler
from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
from gerente_financeiro.contact_handler import contact_conv, contact_start
from gerente_financeiro.delete_user_handler import delete_user_conv
from gerente_financeiro.dashboard_handler import (
    cmd_dashboard, cmd_dashstatus, dashboard_callback_handler
)
from gerente_financeiro.gamification_handler import show_profile, show_rankings, handle_gamification_callback
from gerente_financeiro.gamification_utils import touch_user_interaction

# 📈 INVESTMENT HANDLER
from gerente_financeiro.investment_handler import get_investment_handlers

# 🤖 ASSISTENTE PROATIVO
from gerente_financeiro.assistente_proativo_handler import teste_assistente_handler

# 🎊 WRAPPED ANUAL
from gerente_financeiro.wrapped_anual_handler import meu_wrapped_handler



# --- COMANDOS DE DEBUG (REMOVER EM PRODUÇÃO) ---
@track_analytics("debugocr")
async def debug_ocr_command(update, context):
    """Comando específico para debug do OCR /lancamento"""
    try:
        user_id = update.effective_user.id
        
        message = f"""🔍 **DEBUG OCR LANCAMENTO**

👤 **User ID**: {user_id}

🌍 **Environment Check**:
• GEMINI_API_KEY: {'✅ SET' if os.getenv('GEMINI_API_KEY') else '❌ NOT SET'}
• GOOGLE_VISION: {'✅ SET' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or os.getenv('GOOGLE_VISION_CREDENTIALS_JSON') else '❌ NOT SET'}
• RENDER: {'✅ YES' if os.getenv('RENDER') else '❌ NO (LOCAL)'}

📦 **Module Check**:"""

        # Testar importações
        try:
            import google.generativeai as genai
            message += "\n• Gemini: ✅ OK"
        except Exception as e:
            message += f"\n• Gemini: ❌ {str(e)[:30]}"
        
        try:
            from google.cloud import vision
            message += "\n• Google Vision: ✅ OK"
        except Exception as e:
            message += f"\n• Google Vision: ❌ {str(e)[:30]}"
        
        try:
            from PIL import Image
            message += "\n• PIL: ✅ OK"
        except Exception as e:
            message += f"\n• PIL: ❌ {str(e)[:30]}"

        message += f"""

🔬 **Credential Files**:"""
        
        # Verificar arquivos de credenciais
        cred_files = [
            'credenciais/credentials.json',
            'credenciais/googlevision2.json'
        ]
        
        for cred_file in cred_files:
            if os.path.exists(cred_file):
                size = os.path.getsize(cred_file)
                message += f"\n• {cred_file}: ✅ ({size} bytes)"
            else:
                message += f"\n• {cred_file}: ❌ NOT FOUND"

        message += f"""

📱 **Como testar**:
1. Envie /lancamento
2. Envie uma foto de nota fiscal
3. Se der erro, envie o print do erro
4. Execute /debuglogs para ver logs detalhados

🎯 **Status**: Sistema de debug ativo"""

        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"🚨 **ERRO DEBUG OCR**: {str(e)}")

@track_analytics("debuglogs")
async def debug_logs_command(update, context):
    """Mostrar logs recentes de erro do OCR"""
    try:
        import glob
        
        # Procurar arquivos de log recentes
        log_files = glob.glob('debug_logs/ocr_debug_*.log')
        if not log_files:
            await update.message.reply_text("📝 Nenhum log de debug encontrado. Execute /debugocr primeiro.")
            return
        
        # Pegar o log mais recente
        latest_log = max(log_files, key=os.path.getctime)
        
        try:
            with open(latest_log, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # Limitar tamanho da mensagem
            if len(log_content) > 3500:
                log_content = log_content[-3500:]
                log_content = "...\n" + log_content
            
            message = f"📝 **LOG DEBUG OCR**\n```\n{log_content}\n```"
            
        except Exception as e:
            message = f"❌ Erro ao ler log: {str(e)}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"🚨 **ERRO LOGS**: {str(e)}")

@track_analytics("dashboarddebug")
async def debug_dashboard(update, context):
    """Comando de debug do dashboard"""
    try:
        user_id = update.effective_user.id
        
        # Testar dashboard
        import requests
        try:
            response = requests.get("http://localhost:5001/api/status", timeout=3)
            if response.status_code == 200:
                dashboard_status = "✅ Online"
                data = response.json()
                status_info = f"Status: {data.get('status', 'unknown')}"
            else:
                dashboard_status = "❌ Erro HTTP"
                status_info = f"Código: {response.status_code}"
        except Exception as e:
            dashboard_status = "❌ Offline"
            status_info = f"Erro: {str(e)[:50]}"
        
        message = f"""🔍 **DEBUG DASHBOARD**

📊 **Dashboard**: {dashboard_status}
{status_info}

👤 **User ID**: {user_id}

🌐 **URLs**:
• Dashboard: http://localhost:5000
• Demo: http://localhost:5000/dashboard"""

        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"🚨 **ERRO DEBUG**: {str(e)}")

# --- CONFIGURAÇÃO INICIAL ---
warnings.filterwarnings("ignore", category=PTBUserWarning)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Handler Fantasma: Registro Dinâmico com Auto-Detecção e Hotpatch ---
def auto_register_command(application, command_name):
    def decorator(func):
        handler = CommandHandler(command_name, func)
        application.add_handler(handler)
        print(f"💥 Handler /{command_name} registrado via auto_register_command!")
        return func
    return decorator


def _register_default_handlers(application: Application, safe_mode: bool = False) -> None:
    """Registra em um único ponto os handlers necessários para o bot."""

    def add(handler, name: str) -> None:
        try:
            application.add_handler(handler)
            logger.debug("Handler %s registrado", name)
        except Exception as exc:
            if safe_mode:
                logger.warning("⚠️ Handler %s indisponível: %s", name, exc)
            else:
                raise

    def build_and_add(name: str, builder) -> None:
        try:
            handler = builder()
        except Exception as exc:
            if safe_mode:
                logger.warning("⚠️ Falha ao construir %s: %s", name, exc)
                return
            raise
        add(handler, name)

    logger.info("🔧 Registrando handlers padrão do bot...")

    # Handlers críticos em grupo prioritário para não serem engolidos por outros catch-alls.
    application.add_handler(CommandHandler("start", start_onboarding), group=-1)
    application.add_handler(CommandHandler("configurar", configurar_start), group=-1)
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Document.MimeType("application/pdf"),
            fatura_receive_file,
        ),
        group=-1,
    )
    # OCR/Alfredo NAO entram no grupo -1 para nao vazar estado de conversas ativas.
    # Eles sao registrados ao final como fallback do grupo 0.

    conversation_builders = [
        ("configurar_conv", lambda: configurar_conv),
        ("gerente_conv", create_gerente_conversation_handler),
        ("cadastro_email_conv", create_cadastro_email_conversation_handler),
        ("manual_entry_conv", lambda: manual_entry_conv),
        ("delete_user_conv", lambda: delete_user_conv),
        ("contact_conv", lambda: contact_conv),
        ("grafico_conv", lambda: grafico_conv),
        ("metas_conv", lambda: metas_conv),
        ("agendamento_conv", lambda: agendamento_conv),
        ("edit_conv", lambda: edit_conv),
        ("fatura_conv", lambda: fatura_conv),
    ]
    


    for name, builder in conversation_builders:
        build_and_add(name, builder)

    print("DEBUG: Criando lista command_builders")
    command_builders = [
        ("relatorio_handler", lambda: relatorio_handler),
        ("/help", lambda: CommandHandler("help", help_command)),
        ("/alerta", lambda: CommandHandler("alerta", schedule_alerts)),
        ("/agendar", lambda: CommandHandler("agendar", agendamento_start)),
        ("/notificacoes", lambda: CommandHandler("notificacoes", painel_notificacoes)),
        ("/perfil", lambda: CommandHandler("perfil", show_profile)),
        ("/ranking", lambda: CommandHandler("ranking", show_rankings)),
        ("/dashboard", lambda: CommandHandler("dashboard", cmd_dashboard)),
        ("cancelar_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_CANCELAR}$"), cancel)),
        ("lancamento_b", lambda: MessageHandler(filters.Regex(f"^{re.escape(BOTAO_LANCAMENTO)}$"), manual_entry_start)),
        ("fatura_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_FATURA}$"), fatura_start)),
        ("agendamentos_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_AGENDAMENTOS}$"), agendamento_start)),
        ("ranking_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_RANKING}$"), show_rankings)),
        ("nivel_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_NIVEL}$"), show_profile)),
        ("contato_b", lambda: MessageHandler(filters.Regex(f"^{re.escape(BOTAO_CONTATO)}$"), contact_start)),
        ("/painel", lambda: CommandHandler("painel", toggle_painel_command)),
        ("/dashstatus", lambda: CommandHandler("dashstatus", cmd_dashstatus)),
        ("/dashboarddebug", lambda: CommandHandler("dashboarddebug", debug_dashboard)),
        ("/debugocr", lambda: CommandHandler("debugocr", debug_ocr_command)),
        ("/debuglogs", lambda: CommandHandler("debuglogs", debug_logs_command)),
        ("/teste_assistente", lambda: teste_assistente_handler),
        ("/meu_wrapped", lambda: meu_wrapped_handler),
        # ❌ REMOVIDO: ("/importar", ...) - função importar_of não estava definida em lugar nenhum
        # Texto/voz/foto sao registrados como fallback no grupo 0 ao final da funcao.
        # ("confirmar_importacao_callback", lambda: CallbackQueryHandler(confirmar_callback, pattern="^confirmar_importacao$")),  # Removido: confirmar_callback não existe mais
        # ("cancelar_importacao_callback", lambda: CallbackQueryHandler(cancelar_callback, pattern="^cancelar_importacao$")),  # Removido: cancelar_callback não existe mais
    ]
    

    
    # Adicionar handlers de investimentos
    try:
        investment_handlers = get_investment_handlers()
        for handler in investment_handlers:
            application.add_handler(handler)
        logger.info("✅ Handlers de investimentos registrados: /investimentos, /dashboard_investimentos, /patrimonio")
    except Exception as e:
        logger.error(f"❌ Erro ao registrar handlers de investimentos: {e}", exc_info=True)

    for name, builder in command_builders:
        print(f"DEBUG: Tentando registrar comando: {name}")
        build_and_add(name, builder)
        print(f"DEBUG: Comando {name} registrado com sucesso")

    callback_builders = [
        ("help_callback", lambda: CallbackQueryHandler(help_callback, pattern="^help_")),
        ("analise_callback", lambda: CallbackQueryHandler(handle_action_button_callback, pattern="^analise_")),
        ("metas_delete_callback", lambda: metas_callbacks[0]),
        ("metas_confirm_callback", lambda: metas_callbacks[1]),
        # Necessario para fluxo de fatura iniciado por handler global de PDF (fora da ConversationHandler).
        ("fatura_callback", lambda: CallbackQueryHandler(fatura_confirm, pattern="^fatura_")),
        ("agendamento_menu_callback", lambda: CallbackQueryHandler(agendamento_menu_callback, pattern="^agendamento_")),
        ("cancelar_agendamento_callback", lambda: CallbackQueryHandler(cancelar_agendamento_callback, pattern="^ag_cancelar_")),
        ("gamificacao_callback", lambda: CallbackQueryHandler(handle_gamification_callback, pattern="^(show_rankings|show_stats|show_rewards)$")),
        ("dashboard_callback", lambda: CallbackQueryHandler(dashboard_callback_handler, pattern="^dashboard_")),
        ("quick_callback", lambda: CallbackQueryHandler(quick_action_handler, pattern="^quick_")),
        ("ocr_callback", lambda: CallbackQueryHandler(ocr_action_processor, pattern="^ocr_")),
    ]
    


    for name, builder in callback_builders:
        build_and_add(name, builder)

    # Fallbacks finais de mensagem (grupo 0): so devem rodar se nenhum ConversationHandler capturar.
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.IMAGE),
            ocr_iniciar_como_subprocesso,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.TEXT & ~filters.COMMAND),
            processar_mensagem_com_alfredo,
        )
    )
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.VOICE, processar_mensagem_com_alfredo)
    )

    async def touch_interaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user:
            return
        try:
            await touch_user_interaction(user.id, context)
        except Exception:
            pass

    application.add_handler(
        MessageHandler(filters.ALL, touch_interaction_handler),
        group=99,
    )
    application.add_handler(
        CallbackQueryHandler(touch_interaction_handler, pattern=r".*"),
        group=99,
    )

# --- FUNÇÕES PRINCIPAIS DO BOT ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga os erros e envia uma mensagem de erro genérica."""
    import traceback
    
    # Log detalhado do erro
    print(f"\n🚨 ERRO GLOBAL CAPTURADO:")
    print(f"Tipo: {type(context.error).__name__}")
    print(f"Mensagem: {str(context.error)}")
    print(f"Traceback:")
    print(traceback.format_exc())
    
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if hasattr(update, 'effective_message') and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Ocorreu um erro inesperado. Minha equipe já foi notificada.")
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
            print(f"❌ Erro ao enviar mensagem de erro: {e}")

def main() -> None:
    """Função principal que monta e executa o bot."""
    logger.info("Iniciando o bot...")

    # Verificação se as credenciais estão presentes
    if not config.TELEGRAM_TOKEN:
        logger.error("❌ Token do Telegram não configurado. Defina a variável de ambiente TELEGRAM_TOKEN.")
        return

    if not config.GEMINI_API_KEY:
        logger.error("❌ Chave da API do Gemini não configurada. Defina a variável de ambiente GEMINI_API_KEY.")
        return

    # Configuração do Banco de Dados
    try:
        criar_tabelas()
        db: Session = next(get_db())
        popular_dados_iniciais(db)
        db.close()
        logger.info("Banco de dados pronto.")
    except Exception as e:
        logger.critical(f"Falha crítica na configuração do banco de dados: {e}", exc_info=True)
        return

    # Configuração da API do Gemini
    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\"").strip().strip()) if config.GEMINI_API_KEY else None
        logger.info("API do Gemini configurada.")
    except Exception as e:
        logger.critical(f"Falha ao configurar a API do Gemini: {e}")
        return

    # Construção da Aplicação do Bot
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    logger.info("Aplicação do bot criada.")

    _register_default_handlers(application)
    application.add_error_handler(error_handler)
    logger.info("Todos os handlers adicionados com sucesso.")

    # Configuração e inicialização dos Jobs agendados
    job_queue = application.job_queue
    configurar_jobs(job_queue)
    logger.info("Jobs de metas e agendamentos configurados.")

    return application

def create_application_ultra_robust():
    """🔥 CRIA APLICAÇÃO BOT ULTRA-ROBUSTA - SEM TRAVAR"""
    logger.info("🚀 [ULTRA-ROBUST] Criando aplicação bot...")

    # Verificação rápida de credenciais
    if not config.TELEGRAM_TOKEN:
        logger.error("❌ Token do Telegram não configurado")
        return None

    if not config.GEMINI_API_KEY:
        logger.error("❌ Chave da API do Gemini não configurada") 
        return None

    # 🔥 CONFIGURAÇÃO BD ULTRA-ROBUSTA COM TIMEOUT
    try:
        logger.info("🗄️ Configurando banco de dados...")
        criar_tabelas()
        # 🔥 NOVA POPULAÇÃO ULTRA-ROBUSTA
        db: Session = next(get_db())
        db.close()
        logger.info("✅ Banco de dados pronto.")
    except Exception as db_error:
        logger.error(f"❌ Erro banco de dados: {db_error} - continuando")

    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\"").strip().strip()) if config.GEMINI_API_KEY else None
        logger.info("✅ API do Gemini configurada.")
    except Exception as e:
        logger.error(f"❌ Erro Gemini: {e} - continuando")

    # 🔥 CRIAÇÃO APLICAÇÃO ULTRA-ROBUSTA
    try:
        print("DEBUG: Criando ApplicationBuilder...")
        application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
        print("DEBUG: Application criada!")
        logger.info("✅ Aplicação do bot criada.")

        try:
            print("DEBUG: Chamando _register_default_handlers...")
            _register_default_handlers(application, safe_mode=True)
            print("DEBUG: _register_default_handlers concluída!")
            logger.info("✅ Handlers padrão adicionados.")
        except Exception as handler_error:
            print(f"DEBUG: Erro em _register_default_handlers: {handler_error}")
            logger.error(f"❌ Erro handlers: {handler_error}")

        # 🔥 ERROR HANDLER ULTRA-ROBUSTO
        application.add_error_handler(error_handler)

        # 🔥 JOBS ULTRA-ROBUSTOS (OPCIONAL)
        try:
            configurar_jobs(application.job_queue)
            logger.info("✅ Jobs agendados configurados.")
        except Exception as job_error:
            logger.warning(f"⚠️ Jobs falhou: {job_error} - continuando")
        

        
        logger.info("🎯 [ULTRA-ROBUST] Aplicação criada com SUCESSO!")
        return application
        
    except Exception as e:
        logger.error(f"❌ [ULTRA-ROBUST] Erro crítico criação: {e}")
        return None

def create_application():
    """Alias para create_application_ultra_robust para compatibilidade"""
    return create_application_ultra_robust()

def run_bot():  # pragma: no cover
    """(LEGADO) Execução via polling NÃO utilizada em produção.
    Mantido apenas para debug local isolado. Em produção usamos webhook através do unified_launcher_definitivo.
    """
    logger.warning("⚠️ run_bot() chamado - modo legado de polling. Use unified_launcher_definitivo para produção.")
    application = create_application()
    if application:
        application.run_polling()

if __name__ == '__main__':  # pragma: no cover
    run_bot()