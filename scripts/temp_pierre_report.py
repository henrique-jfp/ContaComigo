
import sys
import os
import json
from datetime import datetime

# Adiciona o diretório atual ao path para importar pierre_finance
sys.path.append(os.getcwd())

from pierre_finance.client import PierreClient

def generate_report(api_key):
    client = PierreClient(api_key)
    
    print("--- FETCHING PIERRE DATA ---")
    
    accounts = client.get_accounts()
    balance = client.get_balance()
    transactions = client.get_transactions(limit=20)
    bill_summary = client.get_bill_summary()
    
    report = {
        "pierre_accounts": accounts,
        "pierre_balance": balance,
        "pierre_transactions": transactions,
        "pierre_bill_summary": bill_summary
    }
    
    return report

if __name__ == "__main__":
    api_key = "sk-ueZlVRGjhNChMD7EyGq7ZoMPnQETLLWB"
    try:
        data = generate_report(api_key)
        print("--- REPORT DATA START ---")
        print(json.dumps(data, indent=2))
        print("--- REPORT DATA END ---")
    except Exception as e:
        print(f"Error: {e}")
