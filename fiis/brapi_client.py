import os
import requests
import logging
import time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class BrapiClient:
    BASE_URL = "https://brapi.dev/api"
    
    # Cache em memória: {ticker: {"data": dict, "timestamp": float}}
    _cache = {}
    CACHE_TTL = 900  # 15 minutos

    def __init__(self):
        self.token = os.getenv("BRAPI_TOKEN")
        self.session = requests.Session()
        
        # Configuração de Headers
        headers = {"User-Agent": "ContaComigo-Bot/1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)
        
        # Configuração de Resiliência (Auto-Retry)
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_from_cache(self, ticker: str) -> dict | None:
        if ticker in self._cache:
            entry = self._cache[ticker]
            if time.time() - entry["timestamp"] < self.CACHE_TTL:
                return entry["data"]
            else:
                del self._cache[ticker]
        return None

    def _save_to_cache(self, ticker: str, data: dict):
        self._cache[ticker] = {
            "data": data,
            "timestamp": time.time()
        }

    def get_fii(self, ticker: str) -> dict | None:
        """
        Retorna dados completos de um FII.
        """
        ticker = ticker.upper().strip()
        
        # Tenta cache
        cached = self._get_from_cache(ticker)
        if cached:
            return cached

        try:
            params = {
                "modules": "financials,summaryProfile,defaultKeyStatistics",
                "dividends": "true",
                "fundamental": "true"
            }
            url = f"{self.BASE_URL}/quote/{ticker}"
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                return None
            
            result = data["results"][0]
            
            # Formatação básica e cálculo de P/VP
            price = result.get("regularMarketPrice", 0)
            book_value = result.get("bookValue", 0)
            pvp = price / book_value if book_value and book_value > 0 else 0
            
            # Adiciona P/VP aos dados para facilitar
            result["pvp"] = pvp
            
            self._save_to_cache(ticker, result)
            return result

        except Exception as e:
            logger.error(f"❌ Erro ao buscar FII {ticker} na Brapi: {e}")
            return None

    def get_fiis_em_lote(self, tickers: list[str]) -> dict[str, dict]:
        """
        Busca dados de múltiplos FIIs em uma única chamada.
        Retorna dict de {ticker: dados}
        """
        if not tickers:
            return {}

        results_dict = {}
        tickers_to_fetch = []
        
        for t in tickers:
            t = t.upper().strip()
            cached = self._get_from_cache(t)
            if cached:
                results_dict[t] = cached
            else:
                tickers_to_fetch.append(t)
        
        if not tickers_to_fetch:
            return results_dict

        try:
            # Brapi aceita múltiplos tickers separados por vírgula
            tickers_str = ",".join(tickers_to_fetch)
            params = {
                "modules": "financials,summaryProfile",
                "dividends": "true",
                "fundamental": "true"
            }
            url = f"{self.BASE_URL}/quote/{tickers_str}"
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            for res in data.get("results", []):
                t = res.get("symbol", "").upper()
                if t:
                    # Cálculo P/VP básico se disponível
                    price = res.get("regularMarketPrice", 0)
                    book_value = res.get("bookValue", 0)
                    res["pvp"] = price / book_value if book_value and book_value > 0 else 0
                    
                    self._save_to_cache(t, res)
                    results_dict[t] = res
            
            return results_dict

        except Exception as e:
            logger.error(f"❌ Erro ao buscar FIIs em lote na Brapi: {e}")
            return results_dict

    def buscar_fiis_por_criterio(self, dy_minimo: float = 0.08, pvp_maximo: float = 1.15) -> list[dict]:
        """
        Busca FIIs que atendem critérios mínimos de qualidade.
        """
        try:
            params = {
                "type": "fii",
                "sortBy": "dividendYield",
                "sortOrder": "desc",
                "limit": 100
            }
            url = f"{self.BASE_URL}/quote/list"
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            stocks = data.get("stocks", [])
            
            filtered = []
            for s in stocks:
                dy = s.get("dividendYield", 0) / 100.0  # Brapi retorna em % (ex: 12.5)
                # brapi list não retorna bookValue, precisaríamos buscar detalhes.
                # Para simplificar na busca inicial, filtramos só por DY.
                if dy >= dy_minimo:
                    filtered.append(s)
            
            return filtered[:50]

        except Exception as e:
            logger.error(f"❌ Erro ao listar FIIs na Brapi: {e}")
            return []
