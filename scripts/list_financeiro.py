import sys
from pathlib import Path
from sqlalchemy import func

# Garantir que o root do projeto esteja no sys.path quando o script
# for executado a partir da pasta `scripts/`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento, Categoria
import csv


def main():
    db = next(get_db())
    # Filtrar por usuário específico
    USER_ID = 25
    try:
        rows = (
            db.query(Lancamento)
              .join(Categoria, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .filter(func.lower(Categoria.nome) == 'financeiro')
              .order_by(Lancamento.data_transacao.desc())
              .all()
        )

        out_path = 'output/financeiro_lancamentos.csv'
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['id', 'descricao', 'valor', 'data_transacao', 'id_categoria'])
            for l in rows:
                dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
                valor = float(l.valor) if getattr(l, 'valor', None) is not None else 0.0
                w.writerow([l.id, (l.descricao or '').strip(), valor, dt, l.id_categoria])

        print(f"Exported {len(rows)} rows to {out_path}")
        # Print first 20 rows as sample
        for i, l in enumerate(rows[:20], start=1):
            dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
            print(f"{i:>3}. id={l.id} | {dt} | {valor_display(l)} | { (l.descricao or '')[:80] }")

    finally:
        db.close()


def valor_display(l):
    try:
        return f"R$ {float(l.valor):,.2f}"
    except Exception:
        return str(l.valor)


if __name__ == '__main__':
    main()
