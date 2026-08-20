import sys
from database.database import get_db
from models import Usuario
from pierre_finance.client import PierreClient

db = next(get_db())
user = db.query(Usuario).filter(Usuario.telegram_id == 6157591255).first()
if not user or not user.pierre_api_key:
    print("No user or API key")
    sys.exit(0)

client = PierreClient(user.pierre_api_key)
print("=== PIERRE API - GET BILL SUMMARY ===")
try:
    res = client.get_bill_summary()
    print(res)
except Exception as e:
    print("Error:", e)
    
print("=== PIERRE API - GET BILLS ===")
try:
    res2 = client.get_bills()
    print(res2)
except Exception as e:
    print("Error:", e)

db.close()
