import sys
from pathlib import Path
from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento, Categoria

USER_ID = 31

def main():
    db = next(get_db())
    try:
        total = (
            db.query(func.coalesce(func.sum(Lancamento.valor), 0))
              .join(Categoria, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .filter(func.lower(Categoria.nome).like('%transfer%'))
              .scalar()
        )
        print(f"TOTAL:{float(total):.2f}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
