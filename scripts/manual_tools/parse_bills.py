import sys
from database.database import get_db
from models import Usuario
from pierre_finance.client import PierreClient

db = next(get_db())
user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
if not user or not user.pierre_api_key:
    sys.exit(0)

client = PierreClient(user.pierre_api_key)
data = client.get_bill_summary()

for account in data.get("accounts", []):
    for bill in account.get("bills", []):
        print(f"Conta: {account.get('accountId')} | Due: {bill.get('dueDate')} | Amount: {bill.get('totalAmount')}")
