import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_params():
    token = os.getenv("BRAPI_TOKEN")
    ticker = "MXRF11"
    headers = {"Authorization": f"Bearer {token}"}
    
    params_list = [
        {"modules": "financials"},
        {"modules": "summaryProfile"},
        {"modules": "defaultKeyStatistics"},
        {"dividends": "true"},
        {"fundamental": "true"}
    ]
    
    for p in params_list:
        url = f"https://brapi.dev/api/quote/{ticker}"
        print(f"--- Testando parâmetro: {p} ---")
        resp = requests.get(url, headers=headers, params=p)
        print(f"Status: {resp.status_code}")
        if not resp.ok:
            print(f"Erro: {resp.text}")
        print("-" * 30)

if __name__ == "__main__":
    test_params()
