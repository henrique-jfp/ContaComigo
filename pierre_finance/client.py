import requests
import logging

class PierreClient:
    BASE_URL = "https://pierre.finance/tools/api"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Erro na API Pierre: {e}")
            return {"error": str(e)}

    def get_accounts(self):
        """Retorna lista de contas e saldos."""
        return self._request("GET", "/get-accounts")

    def get_transactions(self, **params):
        """Retorna histórico de transações."""
        return self._request("GET", "/get-transactions", params=params)
