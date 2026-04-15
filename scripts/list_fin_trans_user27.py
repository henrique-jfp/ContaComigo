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

USER_ID = 27
OUT_PATH = f'output/financeiro_transferencias_user_{USER_ID}.csv'
CATS_LOWER = {'financeiro', 'transferências', 'transferencias'}


def main():
    db = next(get_db())
    try:
        rows = (
            db.query(Lancamento)
              .join(Categoria, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .filter(func.lower(Categoria.nome).in_(list(CATS_LOWER)))
              .order_by(Lancamento.data_transacao.desc())
              .all()
        )

        Path('output').mkdir(exist_ok=True)
        with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['id', 'descricao', 'valor', 'data_transacao', 'categoria_nome'])
            for l in rows:
                dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
                valor = float(l.valor) if getattr(l, 'valor', None) is not None else 0.0
                cat_name = (l.categoria.nome if getattr(l, 'categoria', None) else '')
                w.writerow([l.id, (l.descricao or '').strip(), valor, dt, cat_name])

        print(f"Exported {len(rows)} rows to {OUT_PATH}")
        print("Sample:")
        for i, l in enumerate(rows[:50], start=1):
            dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
            print(f"{i:>3}. id={l.id} | {dt} | R$ {float(l.valor):,.2f} | { (l.descricao or '')[:80] }")

    finally:
        db.close()


if __name__ == '__main__':
    main()
