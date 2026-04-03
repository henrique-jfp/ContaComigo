text = open('gerente_financeiro/onboarding_handler.py', 'r').read()
text = text.replace("from telegram.ext import CommandHandler, \n    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters                                                            )\n", "from telegram.ext import (\n    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters\n)\n")
with open('gerente_financeiro/onboarding_handler.py', 'w') as f:
    f.write(text)
