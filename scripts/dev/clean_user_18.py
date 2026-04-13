import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import SessionLocal
from models import Usuario, Lancamento, Conta, SaldoConta, FaturaCartao, ParcelamentoItem

def clean_user_data(uid):
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == uid).first()
        if not user:
            print(f"❌ Usuário ID {uid} não encontrado.")
            return

        print(f"🧹 Limpando dados do usuário: {user.nome_completo} (ID: {uid})")
        
        n_lan = db.query(Lancamento).filter(Lancamento.id_usuario == uid).delete()
        n_sal = db.query(SaldoConta).filter(SaldoConta.id_usuario == uid).delete()
        n_fat = db.query(FaturaCartao).filter(FaturaCartao.id_usuario == uid).delete()
        n_par = db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == uid).delete()
        n_con = db.query(Conta).filter(Conta.id_usuario == uid).delete()
        
        user.pierre_initial_sync_done = False
        user.last_pierre_sync_at = None
        
        db.commit()
        print(f"✅ Limpeza concluída!")
        print(f"   - Lançamentos removidos: {n_lan}")
        print(f"   - Contas removidas: {n_con}")
        print(f"   - Saldos removidos: {n_sal}")
        print(f"   - Faturas removidas: {n_fat}")
        print(f"   - Parcelamentos removidos: {n_par}")
        print(f"   - Estado de sync Pierre: Resetado")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro durante a limpeza: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_user_data(22)
