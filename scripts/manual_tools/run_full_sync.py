import asyncio
from database.database import get_db
from models import Usuario
from pierre_finance.sync import sync_user_data_async

async def main():
    db = next(get_db())
    user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
    if user:
        await sync_user_data_async(db, user)
        print("Full sync complete.")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
