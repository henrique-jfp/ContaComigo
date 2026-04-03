with open('gerente_financeiro/handlers.py', 'r', encoding='utf-8') as f:
    text = f.read()

OLD = """        import re
from telegram.ext import MessageHandler
"""
NEW = """        import re"""

text = text.replace(OLD, NEW)
text = "from telegram.ext import MessageHandler\n" + text

with open('gerente_financeiro/handlers.py', 'w', encoding='utf-8') as f:
    f.write(text)
