import sys
import os
import asyncio
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import SessionLocal
from models import Usuario
from pierre_finance.sync import sincronizar_incremental

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == 22).first()
        if not user:
            print("❌ Nenhum usuário com chave Pierre.")
            return
            
        print(f"🔄 Sincronizando usuário {user.id} ({user.telegram_id})...")
        # Vamos forçar um sync incremental (últimas 48h)
        # Note que o sincronizar_incremental agora também chama o enriquecimento
        novos = await sincronizar_incremental(user, db)
        print(f"✅ Sync finalizado. {novos} novas transações processadas.")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
