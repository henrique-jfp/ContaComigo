import os
import time
from telegram import ReplyKeyboardMarkup, Update, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from urllib.parse import urlencode
from urllib.parse import urlparse

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
BOTAO_ATUALIZAR_MENU = "🔄"


def build_miniapp_url(source: str | None = None) -> str:
    """Gera URL canonica do MiniApp com marcador de origem e anti-cache."""
    base_url = os.getenv('DASHBOARD_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL') or 'http://localhost:5000'
    base_url = str(base_url).strip().rstrip('/')

    # Telegram bloqueia WebApp sem HTTPS (exceto localhost em dev).
    if not base_url.startswith(('http://', 'https://')):
        if base_url.startswith(('localhost', '127.0.0.1')):
            base_url = f'http://{base_url}'
        else:
            base_url = f'https://{base_url}'

    parsed = urlparse(base_url)
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1'):
        base_url = base_url.replace('http://', 'https://', 1)

    params = {
        'entry': source or 'bot',
        # Evita abrir webview antiga/cacheada em alguns clientes Telegram.
        'v': str(int(time.time())),
    }
    return f"{base_url}/webapp?{urlencode(params)}"

def obter_teclado_painel():
    """
    Gera um painel de controle com botões minimizados.
    """
    webapp_url = build_miniapp_url(source='keyboard')

    botoes = [
        [
            KeyboardButton("🚀 Abrir o App", web_app=WebAppInfo(url=webapp_url)), 
            KeyboardButton(BOTAO_ATUALIZAR_MENU),
            KeyboardButton(BOTAO_CONTATO)
        ]
    ]
    
    return ReplyKeyboardMarkup(
        botoes, 
        resize_keyboard=True, 
        is_persistent=True, 
        input_field_placeholder="Escolha: abrir o app ou falar com o dev"
    )

async def toggle_painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia a mensagem com o ReplyKeyboardMarkup resumido."""
    await update.message.reply_html(
        "🎛️ <b>Painel de Controle Atualizado!</b>\n\n"
        "O menu foi focado apenas nos atalhos principais.\n"
        "<i>(Dica: Clique em 'Abrir o App' para acessar os módulos de gerente e métricas em tempo real)</i>",
        reply_markup=obter_teclado_painel()
    )
