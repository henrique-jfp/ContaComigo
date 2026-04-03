from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

# Definição dos textos dos botões para usarmos também nas regex dos Handlers
BOTAO_GERENTE = "🤖 Maestro"
BOTAO_LANCAMENTO = "💳 Lançamento"
BOTAO_EDITAR = "✍️ Editar"
BOTAO_DASHBOARD = "📊 Resumo Geral"
BOTAO_DASHSTATUS = "🌡️ Status Mês"
BOTAO_RELATORIO = "📈 Relatório"
BOTAO_PATRIMONIO = "🏛️ Patrimônio"
BOTAO_INVEST = "💰 Investimentos"
BOTAO_METAS = "🎯 Metas"
BOTAO_CONFIG = "⚙️ Ajustes"
BOTAO_HELP = "ℹ️ Ajuda"
BOTAO_ALERTA = "🔔 Lembretes"

def obter_teclado_painel():
    """
    Gera um painel de controle (Menu Rápido) para ficar sempre ativo no lugar do teclado text.
    """
    botoes = [
        [BOTAO_GERENTE, BOTAO_LANCAMENTO, BOTAO_EDITAR],
        [BOTAO_DASHBOARD, BOTAO_DASHSTATUS, BOTAO_RELATORIO],
        [BOTAO_PATRIMONIO, BOTAO_INVEST, BOTAO_METAS],
        [BOTAO_CONFIG, BOTAO_HELP, BOTAO_ALERTA]
    ]
    return ReplyKeyboardMarkup(
        botoes, 
        resize_keyboard=True, 
        is_persistent=True, 
        input_field_placeholder="🎹 Escolha um Painel de Controle..."
    )

async def toggle_painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia a mensagem com o ReplyKeyboardMarkup."""
    await update.message.reply_html(
        "🎛️ <b>Painel de Controle Ativado!</b>\n\n"
        "Seu teclado agora possui atalhos com botões diretos.\n"
        "<i>(Dica: Se preferir o teclado normal, você pode minimizar esse painel apertando no ícone do teclado ao lado do clipe inferior.)</i>",
        reply_markup=obter_teclado_painel()
    )
