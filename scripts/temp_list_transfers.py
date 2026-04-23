from database.database import get_db
from models import Lancamento, Categoria
import sys

def list_transfers(user_id):
    db = next(get_db())
    try:
        query = (
            db.query(Lancamento)
            .join(Categoria, Lancamento.id_categoria == Categoria.id)
            .filter(
                Lancamento.id_usuario == user_id,
                Categoria.nome.ilike('%Transfer%'),
                Lancamento.valor < 0
            )
            .order_by(Lancamento.data_transacao.desc())
            .all()
        )
        
        print(f"================================================================")
        print(f"DESPESAS DE TRANSFERÊNCIA - USUÁRIO {user_id}")
        print(f"Total de lançamentos: {len(query)}")
        print(f"Soma total: R$ {sum(l.valor for l in query):.2f}")
        print(f"----------------------------------------------------------------")
        for l in query:
            print(f"{l.data_transacao.strftime('%Y-%m-%d')} | R$ {abs(l.valor):>9.2f} | {l.descricao}")
        print(f"================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    user_id = 48
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    list_transfers(user_id)
