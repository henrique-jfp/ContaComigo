from database.database import get_db
from models import Lancamento, Categoria
from sqlalchemy import func

def checar_categorias():
    db = next(get_db())
    try:
        # Busca todas as categorias e a contagem de lançamentos
        resultados = (
            db.query(Categoria.id, Categoria.nome, func.count(Lancamento.id))
            .outerjoin(Lancamento, Lancamento.id_categoria == Categoria.id)
            .group_by(Categoria.id, Categoria.nome)
            .order_by(func.count(Lancamento.id).desc())
            .all()
        )

        print("="*60)
        print(f"{'ID':<4} | {'CATEGORIA':<35} | {'LANÇAMENTOS'}")
        print("="*60)

        for r in resultados:
            print(f"{r[0]:<4} | {r[1]:<35} | {r[2]}")

        # Conta também os lançamentos que ficaram Órfãos (Sem Categoria)
        sem_cat = db.query(Lancamento).filter(Lancamento.id_categoria == None).count()

        print("-" * 60)
        print(f"{'N/A':<4} | {'SEM CATEGORIA (NULL)':<35} | {sem_cat}")
        print("="*60)

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    checar_categorias()