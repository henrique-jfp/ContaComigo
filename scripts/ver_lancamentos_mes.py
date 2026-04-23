from database.database import get_db
from models import Lancamento, Categoria
from sqlalchemy import func
from datetime import datetime, timezone
import argparse
import json


def ver_lancamentos_mes(user_id: int, year: int, month: int, output_json: bool = False):
    db = next(get_db())
    try:
        # intervalo do mês
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        # transações do mês com nome da categoria (quando existir)
        tx_rows = (
            db.query(
                Lancamento.id,
                Lancamento.data_transacao,
                Lancamento.descricao,
                Lancamento.valor,
                Lancamento.id_categoria,
                Categoria.nome.label('categoria_nome'),
            )
            .outerjoin(Categoria, Lancamento.id_categoria == Categoria.id)
            .filter(Lancamento.id_usuario == user_id)
            .filter(Lancamento.data_transacao >= start)
            .filter(Lancamento.data_transacao < end)
            .order_by(Lancamento.data_transacao)
            .all()
        )

        # total geral do mês
        total_month = db.query(func.coalesce(func.sum(Lancamento.valor), 0)) \
            .filter(Lancamento.id_usuario == user_id) \
            .filter(Lancamento.data_transacao >= start) \
            .filter(Lancamento.data_transacao < end) \
            .scalar() or 0

        # agrupa por categoria
        cats = {}
        transactions = []
        for r in tx_rows:
            tx = {
                'id': int(r[0]),
                'date': r[1].strftime('%Y-%m-%d'),
                'description': r[2] or '',
                'amount': float(r[3]),
                'category_id': int(r[4]) if r[4] is not None else None,
                'category_name': r[5] if r[5] is not None else 'Uncategorized',
            }
            transactions.append(tx)

            key = (tx['category_id'], tx['category_name'])
            if key not in cats:
                cats[key] = {'total_amount': 0.0, 'count': 0}
            cats[key]['total_amount'] += tx['amount']
            cats[key]['count'] += 1

        # monta lista de categorias com porcentagem
        categories = []
        total_val = float(total_month)
        for (cat_id, cat_name), v in cats.items():
            pct = (v['total_amount'] / total_val * 100) if total_val > 0 else 0.0
            categories.append({
                'category_id': cat_id,
                'category_name': cat_name,
                'total_amount': round(v['total_amount'], 2),
                'count': v['count'],
                'percentage': round(pct, 2),
            })

        # ordena por total_amount desc
        categories.sort(key=lambda x: x['total_amount'], reverse=True)

        result = {
            'user_id': user_id,
            'year': year,
            'month': month,
            'total_month': round(total_val, 2),
            'categories': categories,
            'transactions': transactions,
        }

        if output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # saída legível
            print('=' * 70)
            print(f"Resumo mês {year}-{month:02} — total: R$ {result['total_month']:.2f}")
            print('-' * 70)
            idx = 1
            for c in categories:
                print(f"{idx}) {c['category_name']}: R$ {c['total_amount']:.2f} — {c['percentage']:.2f}% ({c['count']} lanç.)")
                idx += 1
            if not categories:
                print('Nenhum lançamento encontrado no período.')
            print('-' * 70)
            print('Lista de lançamentos:')
            for t in transactions:
                cat = t['category_name'] or 'Uncategorized'
                print(f"{t['date']} | R$ {t['amount']:.2f} | {t['description']} | {cat}")
            print('=' * 70)

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()


def _parse_args():
    p = argparse.ArgumentParser(description='Relatório mensal de lançamentos por categoria')
    p.add_argument('--user_id', type=int, default=46, help='ID do usuário (default: 46)')
    p.add_argument('--year', type=int, required=True, help='Ano (ex: 2026)')
    p.add_argument('--month', type=int, required=True, help='Mês (1-12)')
    p.add_argument('--json', action='store_true', help='Imprime saída em JSON')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    ver_lancamentos_mes(args.user_id, args.year, args.month, output_json=args.json)
