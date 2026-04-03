import os

def insert_after(filepath, search, replace):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if replace not in content:
        content = content.replace(search, search + "\n" + replace)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

# 1. gerente_financeiro/handlers.py
insert_after('gerente_financeiro/handlers.py', 
    'entry_points=[CommandHandler("gerente", start_gerente)',
    ', MessageHandler(filters.Regex(r"^🤖 Maestro$"), start_gerente)]')
insert_after('gerente_financeiro/handlers.py',
    'import re',
    'from telegram.ext import MessageHandler\n')

# 2. gerente_financeiro/manual_entry_handler.py
insert_after('gerente_financeiro/manual_entry_handler.py',
    'entry_points=[CommandHandler(\'lancamento\', manual_entry_start)',
    ', MessageHandler(filters.Regex(r"^💳 Lançamento$"), manual_entry_start)]')
insert_after('gerente_financeiro/manual_entry_handler.py',
    'from telegram.ext import (',
    '    MessageHandler,')

# 3. gerente_financeiro/editing_handler.py
insert_after('gerente_financeiro/editing_handler.py',
    'entry_points=[CommandHandler(\'editar\', start_editing)',
    ', MessageHandler(filters.Regex(r"^✍️ Editar$"), start_editing)]')
insert_after('gerente_financeiro/editing_handler.py',
    'from telegram.ext import (',
    '    MessageHandler,')

# 4. gerente_financeiro/onboarding_handler.py
insert_after('gerente_financeiro/onboarding_handler.py',
    'CommandHandler(\'configurar\', configurar_start),',
    '        MessageHandler(filters.Regex(r"^⚙️ Ajustes$"), configurar_start),')

