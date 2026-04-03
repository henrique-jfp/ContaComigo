import sys

with open('bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

import_str = """from gerente_financeiro.menu_botoes import (
    toggle_painel_command, BOTAO_GERENTE, BOTAO_LANCAMENTO, BOTAO_EDITAR,
    BOTAO_DASHBOARD, BOTAO_DASHSTATUS, BOTAO_RELATORIO, BOTAO_PATRIMONIO,
    BOTAO_INVEST, BOTAO_METAS, BOTAO_CONFIG, BOTAO_HELP, BOTAO_ALERTA
)"""

if import_str not in text:
    # replace old import because it probably has toggle_painel_command only
    text = text.replace("from gerente_financeiro.menu_botoes import toggle_painel_command\n", "")
    text = import_str + "\n" + text

# We will just inject these using MessageHandler.
# Wait, some commands are inside conversation handlers (Gerente, Lançamento, Editar, Configurar).
# If I just put MessageHandler globally it won't trigger the conversation.
