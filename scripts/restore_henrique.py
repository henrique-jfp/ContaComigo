
import asyncio
import sys
import os
from sqlalchemy.orm import Session

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Usuario, Lancamento
from pierre_finance.sync import sincronizar_carga_inicial

async def restore_henrique():
    db = next(get_db())
    try:
        user_id = 42 # Seu ID atual
        usuario = db.query(Usuario).get(user_id)
        if not usuario:
            print(f"Usuário {user_id} não encontrado.")
            return

        print(f"🚀 Restaurando carga inicial para {usuario.nome_completo} (ID: {user_id})...")
        res = await sincronizar_carga_inicial(usuario, db)
        print(f"Resultado da Restauração: {res}")
        
        count = db.query(Lancamento).filter(Lancamento.id_usuario == user_id).count()
        print(f"📊 Total de lançamentos recuperados: {count}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(restore_henrique())
