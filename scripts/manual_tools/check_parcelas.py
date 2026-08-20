import sys
from database.database import get_db
from models import Usuario, ParcelamentoItem

db = next(get_db())
user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()

parcelas = db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == user.id, ParcelamentoItem.parcela_atual < ParcelamentoItem.total_parcelas).all()
total_future = sum(float(p.valor_parcela) * (p.total_parcelas - p.parcela_atual) for p in parcelas)
print(f"Total future installments: {total_future}")

for p in parcelas:
    print(f"Desc: {p.descricao} | Valor: {p.valor_parcela} | Atual: {p.parcela_atual}/{p.total_parcelas} | Conta: {p.id_conta}")

db.close()
