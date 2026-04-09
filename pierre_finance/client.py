import requests
import logging

class PierreClient:
    BASE_URL = "https://www.pierre.finance/tools/api"

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, **kwargs):
        # O endpoint já começa com / se vier da definição, mas garantimos a consistência
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.BASE_URL}{path}"
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            
            # Se der 401, tenta sem o prefixo 'Bearer ' como fallback de segurança
            if response.status_code == 401:
                logging.warning(f"⚠️ 401 na API Pierre com Bearer. Tentando sem prefixo...")
                alt_headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
                response = requests.request(method, url, headers=alt_headers, **kwargs)

            response.raise_for_status()
            res_json = response.json()
            
            # A API do Pierre retorna os dados dentro de uma chave 'data'
            if isinstance(res_json, dict) and res_json.get("success"):
                return res_json.get("data")
            
            return res_json
            
        except requests.RequestException as e:
            status = getattr(e.response, 'status_code', 'N/A')
            logging.error(f"❌ Erro na API Pierre (Status {status}): {e}")
            return {"error": str(e), "status_code": status}

    def get_accounts(self):
        """Retorna lista de contas e saldos."""
        return self._request("GET", "/get-accounts")

    def get_transactions(self, **params):
        """Retorna histórico de transações."""
        # Se format não for passado, usamos raw para o sync interno
        if "format" not in params:
            params["format"] = "raw"
        return self._request("GET", "/get-transactions", params=params)

    def get_balance(self):
        """Retorna saldo consolidado."""
        return self._request("GET", "/get-balance")

    def get_bill_summary(self, account_id=None):
        """Retorna resumo da fatura atual."""
        params = {}
        if account_id:
            params["accountId"] = account_id
        return self._request("GET", "/get-bill-summary", params=params)

    def manual_update(self):
        """Força a sincronização dos bancos conectados no Pierre."""
        return self._request("POST", "/manual-update")
