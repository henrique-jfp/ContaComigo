import sys
with open('gerente_financeiro/onboarding_handler.py', 'r', encoding='utf-8') as f:
    text = f.read()

import_str = "from gerente_financeiro.menu_botoes import obter_teclado_painel\n"
if "obter_teclado_painel" not in text:
    text = import_str + text

OLD = "await update.message.reply_html(welcome_text)"
NEW = "await update.message.reply_html(welcome_text, reply_markup=obter_teclado_painel())"

if OLD in text:
    text = text.replace(OLD, NEW)

with open('gerente_financeiro/onboarding_handler.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patch aplicado CORRETAMENTE")
