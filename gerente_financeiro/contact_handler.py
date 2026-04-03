# gerente_financeiro/contact_handler.py

import logging
import os

# Importar analytics (dual system: PostgreSQL para Render, SQLite para local)
try:
    if os.getenv('DATABASE_URL'):  # Render
        from analytics.bot_analytics_postgresql import get_analytics, track_command
        analytics = get_analytics()
        logging.info("✅ Contact Handler: Analytics PostgreSQL carregado")
    else:  # Local
        from analytics.bot_analytics import BotAnalytics
        analytics = BotAnalytics()
        logging.info("✅ Contact Handler: Analytics SQLite carregado")
    
    ANALYTICS_ENABLED = True
except ImportError as e:
    ANALYTICS_ENABLED = False
    logging.warning(f"⚠️ Contact Handler: Analytics não disponível - {e}")

def track_analytics(command_name):
    """Decorator para tracking de comandos"""
    import functools
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, context):
            if ANALYTICS_ENABLED and update.effective_user:
                user_id = update.effective_user.id
                username = update.effective_user.username or update.effective_user.first_name or "Usuário"
                
                try:
                    if hasattr(analytics, 'track_command_usage'):
                        # SQLite
                        analytics.track_command_usage(
                            user_id=user_id,
                            username=username,
                            command=command_name,
                            success=True
                        )
                    else:
                        # PostgreSQL
                        analytics.track_command(
                            user_id=user_id,
                            username=username,
                            command=command_name
                        )
                    logging.info(f"📊 Analytics: {username} usou /{command_name}")
                except Exception as e:
                    logging.error(f"❌ Erro no analytics: {e}")
            
            return await func(update, context)
        return wrapper
    return decorator
from .analytics_utils import track_analytics

import logging
import smtplib
import asyncio  # <-- Importação necessária para a correção
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)

import config
from .handlers import cancel
from .states import MENU_CONTATO, AWAIT_SUBJECT, AWAIT_BODY
from email.utils import formataddr

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str, sender_name: str, sender_id: int) -> bool:
    """Função para enviar o e-mail com a mensagem do usuário."""
    
    logger.info(f"🚀 Iniciando envio de email para {sender_name} (ID: {sender_id})")
    
    # --- CORREÇÃO APLICADA ---
    # Usamos variáveis distintas para clareza e correção.
    login_user = config.EMAIL_HOST_USER             # Usuário de login da Brevo (ex: 911b48001@smtp-brevo.com)
    login_password = config.EMAIL_HOST_PASSWORD     # Senha/Chave SMTP da Brevo
    sender_address = config.SENDER_EMAIL            # E-mail do remetente (ex: contacomigo@gmail.com)
    receiver_address = config.EMAIL_RECEIVER        # E-mail do destinatário
    
    logger.info(f"📧 Configurações de email carregadas:")
    logger.info(f"   - Login user: {'✓ Configurado' if login_user else '❌ AUSENTE'}")
    logger.info(f"   - Login password: {'✓ Configurado' if login_password else '❌ AUSENTE'}")
    logger.info(f"   - Sender address: {'✓ Configurado' if sender_address else '❌ AUSENTE'}")
    logger.info(f"   - Receiver address: {'✓ Configurado' if receiver_address else '❌ AUSENTE'}")
    
    # Verifica se todas as variáveis necessárias estão configuradas
    if not all([login_user, login_password, sender_address, receiver_address]):
        missing_vars = []
        if not login_user: missing_vars.append("EMAIL_HOST_USER")
        if not login_password: missing_vars.append("EMAIL_HOST_PASSWORD")  
        if not sender_address: missing_vars.append("SENDER_EMAIL")
        if not receiver_address: missing_vars.append("EMAIL_RECEIVER")
        
        logger.error(f"❌ Variáveis de email não configuradas: {', '.join(missing_vars)}")
        logger.error("📋 Verifique se essas variáveis estão definidas no Render Environment")
        return False

    # Monta o corpo do e-mail com as informações do usuário do Telegram
    full_body = (
        f"<b>Nova mensagem recebida via ContaComigo</b><br><br>"
        f"<b>De:</b> {sender_name} (ID do Telegram: {sender_id})<br>"
        f"<b>Assunto:</b> {subject}<br>"
        f"--------------------------------------------------<br><br>"
        f"{body.replace(chr(10), '<br>')}" # Converte quebras de linha em <br> para HTML
    )

    # Cria o objeto do e-mail
    msg = MIMEMultipart()
    
    # Define os cabeçalhos do e-mail
    # O 'From' usa o SENDER_EMAIL, que é o endereço que o destinatário verá
    msg['From'] = formataddr(('ContaComigo Bot', sender_address))
    msg['To'] = formataddr(('Desenvolvedor', receiver_address))
    msg['Subject'] = f"Contato via Bot: {subject}"
    
    # Anexa o corpo do e-mail como HTML
    msg.attach(MIMEText(full_body, 'html', 'utf-8'))

    try:
        logger.info("📡 Conectando ao servidor SMTP da Brevo...")
        # Conecta-se ao servidor SMTP da Brevo
        server = smtplib.SMTP('smtp-relay.brevo.com', 587)
        logger.info("🔐 Iniciando conexão TLS...")
        server.starttls() # Inicia a conexão segura
        
        logger.info("🔑 Fazendo login no servidor SMTP...")
        # --- PONTO CRÍTICO DA CORREÇÃO ---
        # Faz o login usando as credenciais de autenticação da Brevo
        server.login(login_user, login_password)
        logger.info("✅ Login no SMTP realizado com sucesso!")
        
        # Converte a mensagem para string para envio
        text = msg.as_string()
        
        logger.info("📤 Enviando email...")
        # Envia o e-mail
        # 'from_addr' deve ser o e-mail do remetente verificado na sua conta Brevo
        server.sendmail(
            from_addr=sender_address, 
            to_addrs=receiver_address, 
            msg=text
        )
        
        server.quit()
        logger.info(f"✅ E-mail enviado com sucesso via Brevo de {sender_id} para {receiver_address}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Erro de autenticação ao enviar e-mail via Brevo: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Falha geral ao enviar e-mail via Brevo: {e}", exc_info=True)
        return False


async def contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu de contato principal."""
    keyboard = [
        [InlineKeyboardButton("✍️ Enviar Mensagem", callback_data="contact_message")],
        [InlineKeyboardButton("☕ Pagar um Café (PIX)", callback_data="contact_pix")],
        [InlineKeyboardButton("❌ Fechar", callback_data="contact_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🙋‍♂️ <i><b>Desenvolvido com 💙 por Henrique de Jesus Freitas Pereira</b></i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 <b>Quer falar comigo?</b>\n\n"
        "Sinta-se à vontade para enviar uma sugestão, relatar um problema, mandar um alô ou até me oferecer um cafézinho ☕🙂\n\n "
        "Escolha uma opção abaixo:"
    )

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_html(text, reply_markup=reply_markup)

    return MENU_CONTATO


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a escolha do usuário no menu de contato."""
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "contact_message":
        context.user_data['contact_info'] = {}
        await query.edit_message_text(
            "✍️ <b>Vamos lá! Qual é o assunto da sua mensagem?</b>\n\n"
            "<i>Exemplos: Sugestão para o /gerente, Bug no OCR, Dúvida sobre metas...</i>",
            parse_mode='HTML'
        )
        return AWAIT_SUBJECT

    elif action == "contact_pix":
        logger.info("🏷️ Usuário solicitou informações do PIX")
        pix_key = config.PIX_KEY
        logger.info(f"   - PIX_KEY carregado: {'✓ Configurado' if pix_key else '❌ AUSENTE'}")
        
        if not pix_key:
            logger.error("❌ A variável PIX_KEY não está configurada no Render Environment")
            await query.edit_message_text("❤️ <b>Ops!</b> Parece que minha chave PIX tirou uma folga. Agradeço imensamente sua intenção!")
            return ConversationHandler.END

        logger.info("✅ PIX_KEY configurado corretamente, exibindo para usuário")
        text = (
            "❤️ <b>Gratidão pelo seu apoio!</b>\n\n"
            "Seu cafezinho faz toda a diferença para manter o ContaComigo ativo e em constante evolução. ☕💡\n\n"
            "👇 <b>Toque na chave abaixo para copiar:</b>\n\n"
            f"<code>{pix_key}</code>"
        )
        keyboard = [[InlineKeyboardButton("↩️ Voltar", callback_data="contact_back_to_menu")]]
        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return MENU_CONTATO

    elif action == "contact_close":
        await query.edit_message_text("✅ Ok, sem problemas! Se precisar, é só chamar.")
        return ConversationHandler.END
    
    elif action == "contact_back_to_menu":
        return await contact_start(update, context)


async def receive_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Salva o assunto e pede o corpo da mensagem."""
    context.user_data['contact_info']['subject'] = update.message.text
    await update.message.reply_html(
        "✅ <b>Assunto registrado com sucesso!</b>\n\n"
        "Agora me conte os detalhes da sua mensagem. Quanto mais informações você puder compartilhar, melhor poderei entender e ajudar.\n\n"
        "<i>Importante: Este canal é de envio único. Se quiser receber uma resposta, inclua um meio de contato (como seu e-mail) no corpo da mensagem.</i>"
    )
    return AWAIT_BODY


async def receive_body_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o corpo da mensagem, monta e envia o e-mail."""
    contact_info = context.user_data.get('contact_info', {})
    subject = contact_info.get('subject', 'Sem Assunto')
    body = update.message.text
    user = update.effective_user

    await update.message.reply_text("Enviando sua mensagem... 🚀")

    # --- CORREÇÃO APLICADA AQUI ---
    # Usando a forma moderna do asyncio para rodar a função síncrona 'send_email'
    # em uma thread separada, sem bloquear o bot.
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,  # Usa o executor de thread padrão
        send_email,  # A função a ser executada
        subject, body, user.full_name, user.id  # Os argumentos para a função
    )
    # -------------------------------

    if success:
        await update.message.reply_text("✅ Sua mensagem foi enviada com sucesso! Muito obrigado pelo seu feedback.")
    else:
        # A mensagem de erro agora é mais específica para o usuário.
        await update.message.reply_text("❌ Desculpe, ocorreu um erro no servidor de e-mails e não consegui enviar sua mensagem. Por favor, tente novamente mais tarde.")
        
    context.user_data.pop('contact_info', None)
    return ConversationHandler.END


# Cria o ConversationHandler com o fluxo aprimorado
contact_conv = ConversationHandler(
    entry_points=[CommandHandler('contato', contact_start), MessageHandler(filters.Regex("^💬 Fale com o Dev$"), contact_start)],
    states={
        MENU_CONTATO: [CallbackQueryHandler(menu_callback, pattern='^contact_')],
        AWAIT_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_subject)],
        AWAIT_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_body_and_send)],
    },
    fallbacks=[
        CommandHandler(['cancelar', 'cancel', 'sair', 'parar'], cancel),
        MessageHandler(filters.Regex(r'(?i)^/?\s*(cancelar|cancel|sair|parar)$'), cancel)
    ],
            per_message=False,  # False porque mistura MessageHandler e CallbackQueryHandler
    per_user=True,
    per_chat=True
)