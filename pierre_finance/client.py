import requests
import logging

class PierreClient:
    BASE_URL = "https://pierre.finance/tools/api"

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, **kwargs):
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{self.BASE_URL}{path}"
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            
            # Se der 401, tenta sem o prefixo 'Bearer ' como fallback
            if response.status_code == 401:
                logging.warning(f"⚠️ 401 na API Pierre com Bearer. Tentando sem prefixo...")
                alt_headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
                response = requests.request(method, url, headers=alt_headers, **kwargs)

            # Se ainda assim der erro, tenta capturar o corpo do erro antes de levantar exceção
            if not response.ok:
                try:
                    err_data = response.json()
                    logging.error(f"❌ Detalhes do erro Pierre: {err_data}")
                    return {"error": err_data.get("message") or err_data.get("error"), "type": err_data.get("type"), "status_code": response.status_code}
                except:
                    pass

            response.raise_for_status()
            res_json = response.json()
            
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

    def get_bill_summary(self, account_id=None, closing_day=None, **kwargs):
        """Retorna resumo da fatura atual."""
        params = kwargs.copy()
        if account_id:
            params["accountId"] = account_id
        if closing_day is not None:
            params["closingDay"] = closing_day
        return self._request("GET", "/get-bill-summary", params=params)

    def manual_update(self):
        """Força a sincronização dos bancos conectados no Pierre."""
        return self._request("POST", "/manual-update")

    def get_bills(self, account_id=None):
        """Retorna faturas de cartão de crédito vencidas/fechadas."""
        params = {}
        if account_id:
            params["accountId"] = account_id
        return self._request("GET", "/get-bills", params=params)

    def get_installments(self, start_date=None, end_date=None):
        """Retorna todas as parcelas no período."""
        params = {}
        if start_date: params["startDate"] = start_date
        if end_date: params["endDate"] = end_date
        return self._request("GET", "/get-installments", params=params)

    def manage_closing_date(self, payload: dict):
        """Gerencia datas de fechamento de cartões de crédito."""
        return self._request("POST", "/manage-closing-date", json=payload)

    def get_expensive_categories(self, start_date=None):
        """Retorna as categorias mais caras no período."""
        params = {}
        if start_date: params["startDate"] = start_date
        return self._request("GET", "/get-expensive-categories", params=params)

    def get_book(self, include_all_periods=False, **kwargs):
        """Obtém contexto financeiro e análises do usuário (Livro Caixa)."""
        params = kwargs.copy()
        if include_all_periods: params["includeAllPeriods"] = str(include_all_periods).lower()
        return self._request("GET", "/get-book", params=params)

    def get_memories(self, message=None):
        """Recupera ou adiciona memórias financeiras."""
        params = {}
        if message: params["message"] = message
        return self._request("GET", "/get-memories", params=params)

    def get_closing_dates(self):
        """Retorna a lista de datas de fechamento configuradas."""
        return self._request("POST", "/manage-closing-date", json={})

    def list_spending_limits(self, include_inactive=False):
        """Lista os limites de gastos."""
        params = {}
        if include_inactive: params["includeInactive"] = str(include_inactive).lower()
        return self._request("GET", "/list-spending-limits", params=params)

    def create_spending_limit(self, payload: dict):
        """Cria um limite de gastos."""
        return self._request("POST", "/create-spending-limit", json=payload)

    def update_spending_limit(self, payload: dict):
        """Atualiza um limite de gastos."""
        return self._request("PUT", "/update-spending-limit", json=payload)

    def delete_spending_limit(self, limit_id: str):
        """Exclui um limite de gastos."""
        return self._request("DELETE", "/delete-spending-limit", json={"limitId": limit_id})

    def list_payment_reminders(self, filter_status=None):
        """Lista lembretes de pagamento."""
        params = {}
        if filter_status: params["filter"] = filter_status
        return self._request("GET", "/list-payment-reminders", params=params)

    def create_payment_reminder(self, payload: dict):
        """Cria um lembrete de pagamento."""
        return self._request("POST", "/create-payment-reminder", json=payload)

    def update_payment_reminder(self, payload: dict):
        """Atualiza um lembrete de pagamento."""
        return self._request("PUT", "/update-payment-reminder", json=payload)

    def delete_payment_reminder(self, reminder_id: str, hard_delete=False):
        """Exclui um lembrete de pagamento."""
        payload = {"reminderId": reminder_id}
        if hard_delete: payload["hardDelete"] = True
        return self._request("DELETE", "/delete-payment-reminder", json=payload)
