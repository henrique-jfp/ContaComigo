from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

def obter_teclado_painel():
    """
    Gera um painel de controle (Menu Rápido) para ficar sempre ativo no lugar do teclado text.
    Os botões estão organizados por seções: IA/Entrada, Dashboards, Investimento/Metas, Ajuda/Config.
    """
    botoes = [
        ["/gerente", "/lancamento", "/editar"],
        ["/dashboard", "/dashstatus", "/relatorio"],
        ["/patrimonio", "/investimentos", "/metas"],
        ["/configurar", "/help", "/alerta"]
    ]
    return ReplyKeyboardMarkup(
        botoes, 
        resize_keyboard=True, 
        is_persistent=True, 
        input_field_placeholder="🎹 Seu Painel de Controle (ou digite...)"
    )

async def toggle_painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia a mensagem com o ReplyKeyboardMarkup."""
    await update.message.reply_html(
        "🎛️ <b>Painel de Controle Ativado!</b>\n\n"
        "Seu teclado agora possui atalhos diretos para os comandos do sistema, separados por categoria.\n"
        "<i>(Dica: Se preferir o teclado normal, você pode minimizar esse painel no botão do canto inferior direito.)</i>",
        reply_markup=obter_teclado_painel()
    )
