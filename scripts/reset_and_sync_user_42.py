
import asyncio
import sys
import os
from sqlalchemy.orm import Session

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Usuario, Lancamento, ParcelamentoItem, FaturaCartao, Conta
from pierre_finance.sync import sincronizar_carga_inicial

async def reset_and_sync():
    db = next(get_db())
    try:
        user_id = 42
        usuario = db.query(Usuario).get(user_id)
        if not usuario:
            print(f"❌ Usuário {user_id} não encontrado.")
            return

        print(f"🧹 Limpando todos os dados do usuário {usuario.nome_completo} para reinício total...")
        
        # Deletar lançamentos
        db.query(Lancamento).filter(Lancamento.id_usuario == user_id).delete()
        # Deletar parcelamentos
        db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == user_id).delete()
        # Deletar faturas
        db.query(FaturaCartao).filter(FaturaCartao.id_usuario == user_id).delete()
        # Deletar contas (exceto a digital central)
        db.query(Conta).filter(
            Conta.id_usuario == user_id, 
            Conta.nome != "ContaComigo Digital"
        ).delete()
        
        # Resetar flag de sincronização
        usuario.pierre_initial_sync_done = False
        usuario.last_pierre_sync_at = None
        
        db.commit()
        print("✅ Banco de dados limpo com sucesso.")

        print(f"🚀 Iniciando CARGA INICIAL (90 dias) via Open Finance...")
        res = await sincronizar_carga_inicial(usuario, db)
        print(f"📊 Resultado da Sincronização: {res}")
        
        total_l = db.query(Lancamento).filter(Lancamento.id_usuario == user_id).count()
        print(f"✨ Total de lançamentos no banco agora: {total_l}")

    except Exception as e:
        print(f"❌ Erro no processo: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reset_and_sync())
