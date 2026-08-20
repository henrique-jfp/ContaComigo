import sys
from database.database import get_db
from models import Usuario
from pierre_finance.client import PierreClient

db = next(get_db())
user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
if not user or not user.pierre_api_key:
    sys.exit(0)

client = PierreClient(user.pierre_api_key)
transactions = client.get_bill_summary()
accounts = transactions.get('accounts', [])

print(f"Number of accounts in bill summary: {len(accounts)}")
for account in accounts:
    transactions = account.get('transactions', [])
    sum_pending = sum(t['amount'] for t in transactions if t.get('is_future_installment', False))
    sum_all = sum(t['amount'] for t in transactions)
    print(f"Account {account.get('accountId')}")
    print(f"Total in get_bill_summary: {sum_all}")
    print(f"Future installments in get_bill_summary: {sum_pending}")

db.close()
