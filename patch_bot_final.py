import sys

with open('bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add the message handlers for the common commands to command_builders
OLD = "        (\"/dashboard\", lambda: CommandHandler(\"dashboard\", cmd_dashboard)),"
NEW = """        ("/dashboard", lambda: CommandHandler("dashboard", cmd_dashboard)),
        ("dashboard_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_DASHBOARD}$"), cmd_dashboard)),
        ("dashstatus_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_DASHSTATUS}$"), cmd_dashstatus)),
        ("relatorio_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_RELATORIO}$"), relatorio_handler.callback)),
        ("patrimonio_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_PATRIMONIO}$"), patrimonio_command)),
        ("invest_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_INVEST}$"), investimentos_command)),
        ("metas_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_METAS}$"), listar_wishlist_command)),
        ("help_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_HELP}$"), help_command)),
        ("alerta_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_ALERTA}$"), schedule_alerts)),"""

if OLD in text and "BOTAO_DASHBOARD" not in text[text.find(OLD):]:
    text = text.replace(OLD, NEW)
    
with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("bot.py patched")
