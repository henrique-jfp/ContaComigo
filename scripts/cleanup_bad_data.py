
from database.database import get_db
from models import Lancamento, Usuario
from sqlalchemy import text

def cleanup_bad_transactions():
    db = next(get_db())
    try:
        # Buscar ID do usuário 6157591255
        user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
        if not user:
            print("Usuário não encontrado.")
            return

        # Deletar lançamentos suspeitos (criados hoje que caíram em outros meses)
        print(f"Limpando transações do usuário {user.id}...")
        result = db.query(Lancamento).filter(
            Lancamento.id_usuario == user.id,
            Lancamento.id >= 25787
        ).delete(synchronize_session=False)
        
        db.commit()
        print(f"Sucesso! {result} transações removidas.")
    except Exception as e:
        db.rollback()
        print(f"Erro na limpeza: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_bad_transactions()
