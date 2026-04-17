
import sys
import os
import json
from datetime import datetime

# Adiciona o diretório atual ao path para importar pierre_finance
sys.path.append(os.getcwd())

from pierre_finance.client import PierreClient

def sum_april_expenses(api_key):
    client = PierreClient(api_key)
    
    # Buscando transações de Abril/2026
    # O Pierre costuma usar YYYY-MM-DD
    transactions = client.get_transactions(
        startDate="2026-04-01", 
        endDate="2026-04-30",
        limit=500
    )
    
    total_despesas = 0.0
    count = 0
    
    if isinstance(transactions, list):
        for tx in transactions:
            # No Pierre, despesas costumam vir com amount positivo e type DEBIT 
            # ou amount negativo dependendo da conta.
            # Baseado no log anterior, despesas de cartão vinham com amount positivo (ex: 6.00) 
            # e tipo DEBIT ou status POSTED.
            # Vamos filtrar pelo tipo DEBIT e ignorar TRANSFER se possível, 
            # ou simplesmente somar valores que representam saída.
            
            amount = float(tx.get("amount", 0))
            # No Pierre 'DEBIT' é saída. 
            if tx.get("type") == "DEBIT":
                # Se o valor for negativo no JSON (como vimos em alguns casos de BANK), 
                # pegamos o valor absoluto para a soma de despesas, 
                # ou se for positivo (como no CREDIT), somamos direto.
                total_despesas += abs(amount)
                count += 1
    
    return total_despesas, count

if __name__ == "__main__":
    api_key = "sk-ueZlVRGjhNChMD7EyGq7ZoMPnQETLLWB"
    try:
        total, count = sum_april_expenses(api_key)
        print("--- PIERRE STATS START ---")
        print(f"Total Abril: {total}")
        print(f"Transações: {count}")
        print("--- PIERRE STATS END ---")
    except Exception as e:
        print(f"Error: {e}")
