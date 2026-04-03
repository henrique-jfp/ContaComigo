import sys
with open('bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

OLD = """        ("/dashboard", lambda: CommandHandler("dashboard", cmd_dashboard)),"""
NEW = """        ("/dashboard", lambda: CommandHandler("dashboard", cmd_dashboard)),
        ("/painel", lambda: CommandHandler("painel", toggle_painel_command)),"""

if OLD in text:
    text = text.replace(OLD, NEW)

import_str = "from gerente_financeiro.menu_botoes import toggle_painel_command\n"
if "toggle_painel_command" not in text:
    text = import_str + text

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patch do bot.py aplicado CORRETAMENTE")
