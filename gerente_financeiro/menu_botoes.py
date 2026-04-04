import os
from telegram import ReplyKeyboardMarkup, Update, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes

# Definição dos textos dos botões para usarmos também nas regex dos Handlers (são conservados caso chamados na mão)
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
    Gera um painel de controle com botões minimizados.
    """
    url_base = os.getenv('DASHBOARD_BASE_URL', 'http://127.0.0.1:5000') # fallback simples
    webapp_url = f"{url_base}/webapp"

    botoes = [
        [KeyboardButton("🧩 Abrir o App", web_app=WebAppInfo(url=webapp_url)), KeyboardButton(BOTAO_CONTATO)]
    ]
    
    return ReplyKeyboardMarkup(
        botoes, 
        resize_keyboard=True, 
        is_persistent=True, 
        input_field_placeholder="Acesse o Miniapp..."
    )

async def toggle_painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia a mensagem com o ReplyKeyboardMarkup resumido."""
    await update.message.reply_html(
        "🎛️ <b>Painel de Controle Atualizado!</b>\n\n"
        "O menu foi focado apenas nos atalhos principais.\n"
        "<i>(Dica: Clique em 'Abrir o App' para acessar os módulos de gerente e métricas em tempo real)</i>",
        reply_markup=obter_teclado_painel()
    )
