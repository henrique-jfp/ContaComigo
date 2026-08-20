import asyncio
from database.database import get_db
from models import Usuario
from pierre_finance.sync import _upsert_bill_summaries

async def main():
    db = next(get_db())
    user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
    if user:
        await _upsert_bill_summaries(db, user)
        db.commit()
        print("Sync complete.")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
