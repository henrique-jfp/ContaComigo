import sys
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento, Categoria

USER_ID = 31


def month_bounds_now_utc():
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month


def main():
    start, end = month_bounds_now_utc()
    db = next(get_db())
    try:
        total = (
            db.query(func.coalesce(func.sum(Lancamento.valor), 0))
              .join(Categoria, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .filter(func.lower(Categoria.nome).like('%transfer%'))
              .filter(Lancamento.data_transacao >= start)
              .filter(Lancamento.data_transacao < end)
              .scalar()
        )
        print(f"TOTAL_CURRENT_MONTH:{float(total):.2f}")
    finally:
        db.close()


if __name__ == '__main__':
    main()
