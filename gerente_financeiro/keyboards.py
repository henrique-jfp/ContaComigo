from telegram import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard():
    keyboard = [
        ["🤖 /gerente", "🧩 /dashboard"],
        ["📝 /lancamento", "🎯 /metas"],
        ["📈 /relatorio", "✍️ /editar"],
        ["⚙️ /configurar", "ℹ️ /help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
