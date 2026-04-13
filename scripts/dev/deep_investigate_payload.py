import sys
import os
import json
import asyncio
import re

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import SessionLocal
from models import Usuario
from pierre_finance.client import PierreClient

def find_documents(obj, path=""):
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            if any(term in k.lower() for term in ["document", "cnpj", "cpf", "identity", "tax"]):
                if v:
                    results.append((new_path, v))
            results.extend(find_documents(v, new_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(find_documents(item, f"{path}[{i}]"))
    elif isinstance(obj, str):
        # Procura por sequências de 11 ou 14 dígitos
        digits = "".join(filter(str.isdigit, obj))
        if len(digits) in [11, 14]:
            results.append((f"{path} (regex_match)", obj))
    return results

async def main():
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == 22).first()
        if not user:
            print("❌ Usuário 22 não encontrado.")
            return
        
        client = PierreClient(user.pierre_api_key)
        res = client.get_transactions(limit=100) # Pega mais pra ter amostragem maior
        
        txs = []
        if isinstance(res, list): txs = res
        elif isinstance(res, dict): txs = res.get("data", [res])
        
        print(f"🔍 Analisando {len(txs)} transações do Henrique jfp...")
        
        if txs:
            print("\n--- PRIMEIRAS 5 TRANSAÇÕES COMPLETAS ---")
            for i in range(min(5, len(txs))):
                print(f"\n[TX {i}] {txs[i].get('description')}:")
                print(json.dumps(txs[i], indent=2, ensure_ascii=False))
        
        found_any = False
        for i, tx in enumerate(txs):
            docs = find_documents(tx)
            if docs:
                print(f"\n✅ Transação {i} ({tx.get('description')}):")
                for path, val in docs:
                    print(f"   - {path}: {val}")
                found_any = True
        
        if not found_any:
            print("\n❌ NENHUM dado de documento (CNPJ/CPF) encontrado em 100 transações.")
            print("Isso sugere que o banco/instituição do usuário não está enviando esses dados via Open Finance para o Pierre.")
            
            # Print de uma transação completa para conferência final
            if txs:
                print("\nExemplo de payload bruto:")
                print(json.dumps(txs[0], indent=2, ensure_ascii=False))
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
