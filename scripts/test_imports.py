import sys
import os

# Mocking some env vars for import test
os.environ['TELEGRAM_TOKEN'] = '123:abc'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['GEMINI_API_KEY'] = 'test'

try:
    print("Testing imports...")
    import bot
    import jobs
    import models
    from pierre_finance.handlers import get_pierre_conversation_handler, sincronizar_manual
    from pierre_finance.sync import sincronizar_open_finance
    print("✅ All imports passed!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
