from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

# Definição dos textos dos botões para usarmos também nas regex dos Handlers
BOTAO_LANCAMENTO = "💳 Lançamento"
BOTAO_GERENTE = "🤖 Gerente"
BOTAO_EDITAR = "✍️ Editar"
BOTAO_CONFIG = "⚙️ Ajustes"

BOTAO_FATURA = "🧾 Fatura"
BOTAO_GRAFICOS = "📊 Gráficos"
BOTAO_AGENDAMENTOS = "📅 Agendamentos"
BOTAO_METAS = "🎯 Metas"

BOTAO_RANKING = "🏆 Ranking"
BOTAO_NIVEL = "⭐ Seu Nível"
BOTAO_CANCELAR = "❌ Cancelar"
BOTAO_CONTATO = "💬 Fale com o Dev"

def obter_teclado_painel():
    """
    Gera um painel de controle (Menu Rápido) vertical com 4 linhas e 3 colunas.
    """
    botoes = [
        [BOTAO_LANCAMENTO, BOTAO_GERENTE, BOTAO_EDITAR],
        [BOTAO_CONFIG, BOTAO_FATURA, BOTAO_GRAFICOS],
        [BOTAO_AGENDAMENTOS, BOTAO_METAS, BOTAO_RANKING],
        [BOTAO_NIVEL, BOTAO_CANCELAR, BOTAO_CONTATO]
    ]
    return ReplyKeyboardMarkup(
        botoes, 
        resize_keyboard=True, 
        is_persistent=True, 
        input_field_placeholder="🎹 Escolha um Atalho..."
    )

async def toggle_painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia a mensagem com o ReplyKeyboardMarkup."""
    await update.message.reply_html(
        "🎛️ <b>Painel de Controle Atualizado!</b>\n\n"
        "Seu teclado agora possui novos atalhos com botões diretos.\n"
        "<i>(Dica: Se preferir o teclado normal, você pode minimizar esse painel apertando no ícone do teclado ao lado do clipe inferior.)</i>",
        reply_markup=obter_teclado_painel()
    )
