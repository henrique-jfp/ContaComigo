import sys
from database.database import get_db
from models import Usuario, FaturaCartao

db = next(get_db())
user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
if not user or not user.pierre_api_key:
    sys.exit(0)

faturas = db.query(FaturaCartao).filter(FaturaCartao.id_usuario == user.id, FaturaCartao.id_conta == 261).order_by(FaturaCartao.data_vencimento.desc()).limit(5).all()
for f in faturas:
    print(f"Venc: {f.data_vencimento} | Valor: {f.valor_total} | Status: {f.status} | ExtID: {f.external_id}")

db.close()
