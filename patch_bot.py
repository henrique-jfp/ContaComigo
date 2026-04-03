import re

with open('bot.py', 'r') as f:
    content = f.read()

old_block = """        ("dashboard_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_DASHBOARD}$"), cmd_dashboard)),
        ("dashstatus_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_DASHSTATUS}$"), cmd_dashstatus)),
        ("relatorio_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_RELATORIO}$"), relatorio_handler.callback)),
        ("patrimonio_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_PATRIMONIO}$"), patrimonio_command)),
        ("invest_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_INVEST}$"), investimentos_command)),
        ("metas_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_METAS}$"), listar_wishlist_command)),
        ("help_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_HELP}$"), help_command)),
        ("alerta_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_ALERTA}$"), schedule_alerts)),"""

new_block = """        ("invest_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_INVEST}$"), investimentos_command)),
        ("metas_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_METAS}$"), listar_wishlist_command)),
        ("agendamentos_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_AGENDAMENTOS}$"), agendamento_start)),
        ("ranking_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_RANKING}$"), show_rankings)),
        ("nivel_b", lambda: MessageHandler(filters.Regex(f"^{BOTAO_NIVEL}$"), show_profile)),"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('bot.py', 'w') as f:
        f.write(content)
    print("Success")
else:
    print("Block not found!")
