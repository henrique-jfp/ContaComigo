import sys
from pathlib import Path
from sqlalchemy import func

# Garantir import do projeto
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento, Categoria, Subcategoria, Conta
import csv

USER_ID = 31
OUT_PATH = f'output/transferencias_user_{USER_ID}_details.csv'


def format_items(lanc):
    itens = getattr(lanc, 'itens', []) or []
    parts = []
    for it in itens:
        q = float(it.quantidade) if it.quantidade is not None else ''
        vu = float(it.valor_unitario) if it.valor_unitario is not None else ''
        parts.append(f"{it.nome_item}|{q}|{vu}")
    return '||'.join(parts)


def main():
    db = next(get_db())
    try:
        rows = (
            db.query(Lancamento)
              .join(Categoria, Lancamento.id_categoria == Categoria.id)
              .filter(Lancamento.id_usuario == USER_ID)
              .filter(func.lower(Categoria.nome).like('%transfer%'))
              .order_by(Lancamento.data_transacao.desc())
              .all()
        )

        Path('output').mkdir(exist_ok=True)
        with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([
                'id', 'descricao', 'valor', 'tipo', 'data_transacao', 'forma_pagamento',
                'origem', 'documento_fiscal', 'cnpj_contraparte', 'nome_contraparte', 'cnae', 'external_id',
                'categoria_nome', 'subcategoria_nome', 'conta_nome', 'itens'
            ])

            for l in rows:
                dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
                valor = float(l.valor) if getattr(l, 'valor', None) is not None else 0.0
                cat_name = (l.categoria.nome if getattr(l, 'categoria', None) else '')
                sub_name = (l.subcategoria.nome if getattr(l, 'subcategoria', None) else '')
                conta_name = (l.conta.nome if getattr(l, 'conta', None) else '')
                itens_str = format_items(l)
                w.writerow([
                    l.id, (l.descricao or '').strip(), valor, (l.tipo or ''), dt, (l.forma_pagamento or ''),
                    (l.origem or ''), (l.documento_fiscal or ''), (l.cnpj_contraparte or ''), (l.nome_contraparte or ''),
                    (l.cnae or ''), (l.external_id or ''), cat_name, sub_name, conta_name, itens_str
                ])

        print(f"Exported {len(rows)} rows to {OUT_PATH}")
        if rows:
            print("Sample:")
            for i, l in enumerate(rows[:30], start=1):
                dt = l.data_transacao.isoformat() if getattr(l, 'data_transacao', None) else ''
                print(f"{i:>3}. id={l.id} | {dt} | R$ {float(l.valor):,.2f} | { (l.descricao or '')[:80] }")

    finally:
        db.close()


if __name__ == '__main__':
    main()
