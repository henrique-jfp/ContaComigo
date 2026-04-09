import os
import sys

# Mock env vars
os.environ['TELEGRAM_TOKEN'] = '123:abc'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['GEMINI_API_KEY'] = 'test'
os.environ['GROQ_API_KEY'] = 'test'
os.environ['MERCADOPAGO_ACCESS_TOKEN'] = 'test'

try:
    print("Testing bot application creation...")
    from bot import create_application
    app = create_application()
    print("✅ create_application() passed!")
except Exception as e:
    print(f"❌ create_application() failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
