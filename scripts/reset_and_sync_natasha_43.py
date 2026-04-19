
import asyncio
import sys
import os
from sqlalchemy.orm import Session

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Usuario, Lancamento, ParcelamentoItem, FaturaCartao, Conta
from pierre_finance.sync import sincronizar_carga_inicial

async def reset_and_sync_natasha():
    db = next(get_db())
    try:
        user_id = 43 # ID da Natasha
        usuario = db.query(Usuario).get(user_id)
        if not usuario:
            print(f"❌ Usuário {user_id} não encontrado.")
            return

        print(f"🧹 Limpando dados da {usuario.nome_completo} para recarga com novas regras...")
        
        # Deletar dados transacionais
        db.query(Lancamento).filter(Lancamento.id_usuario == user_id).delete()
        db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == user_id).delete()
        db.query(FaturaCartao).filter(FaturaCartao.id_usuario == user_id).delete()
        
        # Deletar contas do Pierre (para recarregar mapeamento)
        db.query(Conta).filter(
            Conta.id_usuario == user_id, 
            Conta.nome != "ContaComigo Digital"
        ).delete()
        
        # Resetar flags
        usuario.pierre_initial_sync_done = False
        usuario.last_pierre_sync_at = None
        
        db.commit()
        print("✅ Limpeza concluída.")

        print(f"🚀 Iniciando nova CARGA INICIAL (90 dias) para {usuario.nome_completo}...")
        res = await sincronizar_carga_inicial(usuario, db)
        print(f"📊 Resultado: {res}")
        
        total = db.query(Lancamento).filter(Lancamento.id_usuario == user_id).count()
        print(f"✨ Sucesso! {total} lançamentos agora estão no banco com as novas regras.")

    except Exception as e:
        print(f"❌ Erro: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reset_and_sync_natasha())
