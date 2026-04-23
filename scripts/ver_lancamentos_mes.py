import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no `sys.path` quando o script
# for executado diretamente a partir da pasta `scripts/`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

        def build_text_report(res):
            lines = []
            lines.append('=' * 70)
            lines.append(f"Resumo mês {year}-{month:02} — total: R$ {res['total_month']:.2f}")
            lines.append('-' * 70)

            # separa transações em receitas e despesas
            tx_income_by_cat = {}
            tx_expense_by_cat = {}
            for t in transactions:
                key = t['category_name'] or 'Uncategorized'
                if t['amount'] >= 0:
                    tx_income_by_cat.setdefault(key, []).append(t)
                else:
                    tx_expense_by_cat.setdefault(key, []).append(t)

            def summarize(tx_map):
                out = []
                for cat, txs in tx_map.items():
                    total = sum(x['amount'] for x in txs)
                    out.append({'category_name': cat, 'total_amount': round(total, 2), 'count': len(txs)})
                return out

            inc_summary = summarize(tx_income_by_cat)
            exp_summary = summarize(tx_expense_by_cat)

            # ordena receitas decrescente, despesas por valor (mais negativo primeiro)
            inc_summary.sort(key=lambda x: x['total_amount'], reverse=True)
            exp_summary.sort(key=lambda x: x['total_amount'])

            # cabeçalhos resumidos
            lines.append('RECEITAS:')
            if inc_summary:
                idx = 1
                for c in inc_summary:
                    lines.append(f"{idx}) {c['category_name']}: R$ {c['total_amount']:.2f} ({c['count']} lanç.)")
                    idx += 1
            else:
                lines.append('Nenhuma receita no período.')

            lines.append('-' * 70)
            lines.append('DESPESAS:')
            if exp_summary:
                idx = 1
                for c in exp_summary:
                    lines.append(f"{idx}) {c['category_name']}: R$ {c['total_amount']:.2f} ({c['count']} lanç.)")
                    idx += 1
            else:
                lines.append('Nenhuma despesa no período.')

            lines.append('-' * 70)

            # detalhes por categoria (receitas)
            for c in inc_summary:
                cat_name = c['category_name']
                lines.append(f"\nCategoria (Receita): {cat_name} — {c['count']} lanç. — R$ {c['total_amount']:.2f}")
                lines.append('-' * 40)
                for t in tx_income_by_cat.get(cat_name, []):
                    lines.append(f"{t['date']} | R$ {t['amount']:.2f} | {t['description']}")

            # detalhes por categoria (despesas)
            for c in exp_summary:
                cat_name = c['category_name']
                lines.append(f"\nCategoria (Despesa): {cat_name} — {c['count']} lanç. — R$ {c['total_amount']:.2f}")
                lines.append('-' * 40)
                for t in tx_expense_by_cat.get(cat_name, []):
                    lines.append(f"{t['date']} | R$ {t['amount']:.2f} | {t['description']}")

            lines.append('\n' + '=' * 70)
            return '\n'.join(lines)

        # se pedir JSON, tem a opção de imprimir/gravar JSON
        out_path = None
        # `args` não está disponível aqui — iremos confiar que o chamador
        # passará `output_json` e `out_path` via parâmetros quando necessário.
        # Para compatibilidade, apenas imprimimos em stdout quando não for
        # passado um arquivo de saída.
        if output_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(build_text_report(result))

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
    p.add_argument('--out', '-o', type=str, help='Caminho do arquivo de saída (texto). Ex: output/report.txt')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    # se foi passado --out, gravamos em arquivo texto; caso contrário, imprimimos
    if args.out:
        # gerar conteúdo textual e gravar
        # chamamos a função principal, mas capturamos a saída usando a mesma lógica
        # refatoramos levemente: chamar ver_lancamentos_mes e reusar construção de
        # resultado seria ideal; para minimizar mudanças, executamos o relatório
        # e redirecionamos a saída padrão para o arquivo.
        from io import StringIO
        import contextlib

        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            ver_lancamentos_mes(args.user_id, args.year, args.month, output_json=args.json)
        content = buf.getvalue()
        out_file = Path(args.out)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content, encoding='utf-8')
        print(f"Relatório salvo em: {out_file}")
    else:
        ver_lancamentos_mes(args.user_id, args.year, args.month, output_json=args.json)
