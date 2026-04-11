import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_bare_min():
    token = os.getenv("BRAPI_TOKEN")
    ticker = "MXRF11"
    # Teste 1: Com Header (Recomendado pela doc que o usuário passou)
    url = f"https://brapi.dev/api/quote/{ticker}"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"--- Teste 1: Bare Minimum com Header ---")
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        print(f"JSON: {resp.json()}")
    else:
        print(f"Erro: {resp.text}")

    # Teste 2: Sem Token (Apenas para ver se o erro muda)
    print(f"\n--- Teste 2: Sem Token ---")
    resp = requests.get(url)
    print(f"Status: {resp.status_code}")
    print(f"Erro: {resp.text}")

if __name__ == "__main__":
    test_bare_min()
