from database.database import get_db
from models import Usuario, Conta
from gerente_financeiro.reconciliation_service import ReconciliationService

def init_digital_accounts():
    db = next(get_db())
    try:
        usuarios = db.query(Usuario).all()
        print(f"Verificando {len(usuarios)} usuários...")
        for user in usuarios:
            ReconciliationService.get_or_create_digital_account(db, user.id)
        print("✅ Todas as Contas Digitais foram inicializadas.")
    finally:
        db.close()

if __name__ == "__main__":
    init_digital_accounts()
