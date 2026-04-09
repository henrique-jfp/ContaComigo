import os
import sys

# Mock env
os.environ['TELEGRAM_TOKEN'] = '123:abc'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['GEMINI_API_KEY'] = 'test'

try:
    print("Simulating full initialization...")
    import bot
    import jobs
    from database.database import get_db
    db = next(get_db())
    print("DB session OK")
    jobs.configurar_jobs(None) # Simulating job config
    print("Jobs configuration OK")
    print("✅ All good!")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
