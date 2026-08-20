import asyncio
from database.database import get_db
from models import Usuario
from pierre_finance.sync import sincronizar_incremental

async def main():
    db = next(get_db())
    user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
    if user:
        await sincronizar_incremental(user, db)
        print("Incremental sync complete.")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
