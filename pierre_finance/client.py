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
            # Tenta com Bearer primeiro (padrão fornecido)
            response = requests.request(method, url, headers=self.headers, **kwargs)
            
            # Se der 401, tenta sem o prefixo 'Bearer ' (algumas APIs simplificadas preferem assim)
            if response.status_code == 401:
                logging.warning(f"⚠️ 401 na API Pierre com Bearer. Tentando sem prefixo...")
                alt_headers = {"Authorization": self.api_key.strip()}
                response = requests.request(method, url, headers=alt_headers, **kwargs)

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            status = getattr(e.response, 'status_code', 'N/A')
            logging.error(f"❌ Erro na API Pierre (Status {status}): {e}")
            return {"error": str(e), "status_code": status}

    def get_accounts(self):
        """Retorna lista de contas e saldos."""
        return self._request("GET", "/get-accounts")

    def get_transactions(self, **params):
        """Retorna histórico de transações."""
        return self._request("GET", "/get-transactions", params=params)
