import os
import sys
from pathlib import Path

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(str(Path(__file__).parent))

from fiis.brapi_client import BrapiClient
from dotenv import load_dotenv

load_dotenv()

def test_brapi():
    client = BrapiClient()
    ticker = "MXRF11"
    print(f"--- Testando busca do FII: {ticker} ---")
    dados = client.get_fii(ticker)
    
    if dados:
        print(f"✅ Sucesso!")
        print(f"Ticker: {dados.get('symbol')}")
        print(f"Preço: {dados.get('regularMarketPrice')}")
        print(f"P/VP: {dados.get('pvp')}")
        print(f"Dividendos (parcial): {str(dados.get('dividendsData'))[:100]}...")
    else:
        print(f"❌ Falha: get_fii({ticker}) retornou None")

if __name__ == "__main__":
    test_brapi()
