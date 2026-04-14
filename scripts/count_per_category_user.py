import sys
from pathlib import Path
from sqlalchemy import func

# Garantir import do projeto
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento, Categoria
import csv

USER_ID = 25
OUT_PATH = f'output/counts_user_{USER_ID}.csv'


def main():
    db = next(get_db())
    try:
        # Contagem por categoria (somente lançamentos do usuário)
        rows = (
            db.query(Categoria.id, Categoria.nome, func.count(Lancamento.id).label('cnt'))
              .join(Lancamento, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .group_by(Categoria.id, Categoria.nome)
              .order_by(func.count(Lancamento.id).desc())
              .all()
        )

        # Contagem de lançamentos sem categoria
        sem_cat = db.query(func.count(Lancamento.id)).filter(Lancamento.id_usuario == USER_ID, Lancamento.id_categoria == None).scalar() or 0

        # Salvar CSV
        Path('output').mkdir(exist_ok=True)
        with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['categoria_id', 'categoria_nome', 'count'])
            for r in rows:
                w.writerow([r[0], r[1], r[2]])
            if sem_cat:
                w.writerow(['NULL', 'SEM CATEGORIA', sem_cat])

        # Imprimir resumo
        total = sum(r[2] for r in rows) + (sem_cat or 0)
        print(f"User {USER_ID} - total lançamentos contabilizados: {total}")
        print("="*50)
        for r in rows:
            print(f"{r[0]:<4} | {r[1]:<35} | {r[2]}")
        if sem_cat:
            print(f"{'N/A':<4} | {'SEM CATEGORIA':<35} | {sem_cat}")
        print("="*50)
        print(f"CSV salvo em: {OUT_PATH}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
