
import asyncio
import sys
import os
from sqlalchemy.orm import Session

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Usuario, Lancamento
from pierre_finance.sync import sincronizar_carga_inicial

async def run_full_sync():
    db = next(get_db())
    try:
        user_id = 38
        usuario = db.query(Usuario).get(user_id)
        if not usuario:
            print(f"Usuário {user_id} não encontrado.")
            return

        print(f"Limpando lançamentos Open Finance antigos para re-sincronização total...")
        db.query(Lancamento).filter(
            Lancamento.id_usuario == user_id, 
            Lancamento.origem.like('open_finance%')
        ).delete()
        db.commit()

        print(f"Executando CARGA INICIAL (90 dias) para {usuario.nome_completo}...")
        res = await sincronizar_carga_inicial(usuario, db)
        print(f"Resultado: {res}")
        
        count = db.query(Lancamento).filter(
            Lancamento.id_usuario == user_id, 
            Lancamento.origem.like('open_finance%')
        ).count()
        print(f"Total final de lançamentos Open Finance no banco: {count}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_full_sync())
