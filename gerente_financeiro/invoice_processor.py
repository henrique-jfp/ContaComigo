import os
import json
import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

import google.generativeai as genai
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

import config
from models import Lancamento, ItemLancamento, Categoria, Usuario, Subcategoria
from database.database import get_db

logger = logging.getLogger(__name__)

# --- ESQUEMAS DE VALIDAÇÃO PYDANTIC ---

class InvoiceItemSchema(BaseModel):
    descricao: str = Field(..., description="Nome do estabelecimento ou item")
    valor: float = Field(..., description="Valor monetário (negativo para despesas, positivo para créditos/estornos)")
    data: Optional[str] = Field(None, description="Data da transação específica (YYYY-MM-DD)")
    parcela: Optional[str] = Field(None, description="Informação de parcela se houver (ex: 1/12)")

class InvoiceSchema(BaseModel):
    data: str = Field(..., description="Data de emissão ou vencimento do documento (YYYY-MM-DD)")
    valor_total: float = Field(..., description="Valor total consolidado do documento")
    estabelecimento: str = Field(..., description="Nome do emissor (ex: Banco Inter) ou local de compra")
    itens: List[InvoiceItemSchema] = Field(default_factory=list, description="Lista detalhada de transações")
    categoria_sugerida: Optional[str] = Field("Outros", description="Categoria principal sugerida")
    confianca: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="Nível de confiança da extração")

    @field_validator('data')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            # Tentar limpar formatos comuns antes de validar
            clean_v = re.sub(r'[^\d-]', '', v)
            if len(clean_v) == 8: # YYYYMMDD
                 clean_v = f"{clean_v[:4]}-{clean_v[4:6]}-{clean_v[6:]}"
            
            datetime.strptime(clean_v, "%Y-%m-%d")
            return clean_v
        except Exception:
            # Se falhar, retorna a data atual formatada para não quebrar o processamento
            return datetime.now().strftime("%Y-%m-%d")

# --- PROCESSADOR UNIVERSAL ---

class UniversalInvoiceExtractor:
    """
    Serviço de extração e persistência universal de faturas.
    Utiliza Gemini 2.0 Flash Lite para análise visual e textual de faturas e extratos.
    Otimizado para alto volume e precisão com baixo consumo de cota.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key.strip().strip("'\""))
        self.model_names = self._build_model_candidates()
        self.model_name = self.model_names[0] if self.model_names else None
        self.model = genai.GenerativeModel(self.model_name) if self.model_name else None

    def _build_model_candidates(self) -> List[str]:
        """Prioriza o modelo configurado no servidor e mantém fallbacks seguros."""
        configured = str(getattr(config, "GEMINI_MODEL_NAME", "") or "").strip()
        candidates = [
            configured,
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-latest",
        ]
        deduped: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in deduped:
                deduped.append(candidate)
        return deduped

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        """Extrai texto do PDF preservando linhas para o parser heurístico."""
        import fitz

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages: List[str] = []
        try:
            for page in doc:
                pages.append(page.get_text("text") or "")
        finally:
            doc.close()
        return "\n".join(pages)

    def _parse_amount_brl(self, raw_value: str) -> Optional[float]:
        cleaned = (raw_value or "").strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("R$", "").replace(" ", "")
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except Exception:
            return None

    def _normalize_invoice_date(self, raw_date: str, default_year: int) -> Optional[str]:
        raw = (raw_date or "").strip()
        if not raw:
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
            try:
                dt = datetime.strptime(raw, fmt)
                if fmt == "%d/%m":
                    dt = dt.replace(year=default_year)
                elif dt.year < 100:
                    dt = dt.replace(year=2000 + dt.year)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue
        return None

    def _extract_total_from_text(self, text: str) -> Optional[float]:
        lowered = text.lower()
        patterns = [
            r"total\s+(?:da\s+)?fatura[:\s]*r?\$?\s*([0-9\.\,]+)",
            r"valor\s+total[:\s]*r?\$?\s*([0-9\.\,]+)",
            r"total\s+a\s+pagar[:\s]*r?\$?\s*([0-9\.\,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                parsed = self._parse_amount_brl(match.group(1))
                if parsed is not None and parsed > 0:
                    return parsed
        return None

    def _extract_issuer_name(self, text: str) -> str:
        lowered = text.lower()
        issuers = [
            "nubank",
            "itaucard",
            "itaú",
            "itau",
            "bradesco",
            "santander",
            "caixa",
            "inter",
            "picpay",
            "c6 bank",
            "mercado pago",
            "banco do brasil",
        ]
        for issuer in issuers:
            if issuer in lowered:
                return issuer.title()
        return "Fatura de Cartão"

    def _extract_invoice_date_from_text(self, text: str, fallback_year: int) -> str:
        lowered = text.lower()
        patterns = [
            r"vencimento[:\s]*(\d{2}/\d{2}(?:/\d{2,4})?)",
            r"fechamento[:\s]*(\d{2}/\d{2}(?:/\d{2,4})?)",
            r"emiss[aã]o[:\s]*(\d{2}/\d{2}(?:/\d{2,4})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                normalized = self._normalize_invoice_date(match.group(1), fallback_year)
                if normalized:
                    return normalized
        return datetime.now().strftime("%Y-%m-%d")

    def _extract_items_with_regex(self, text: str) -> List[Dict[str, Any]]:
        """Parser determinístico para linhas no formato data + descrição + valor."""
        current_year = datetime.now().year
        items: List[Dict[str, Any]] = []
        blacklist = [
            "saldo anterior",
            "pagamento efetuado",
            "pagamento recebido",
            "encargos",
            "juros",
            "iof",
            "anuidade",
            "limite",
            "crédito liberado",
            "credito liberado",
            "total da fatura",
            "total a pagar",
            "valor do pagamento",
            "pagamento por debito",
            "demonstrativo",
            "fatura anterior",
        ]
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        date_pattern = re.compile(r"\b(\d{2}/\d{2}(?:/\d{2,4})?)\b")
        amount_pattern = re.compile(r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})")
        parcel_pattern = re.compile(r"\b(\d{1,2}/\d{1,2})\b")

        for line in lines:
            if len(line) < 8:
                continue
            lowered = line.lower()
            if any(term in lowered for term in blacklist):
                continue

            date_match = date_pattern.search(line)
            amount_matches = amount_pattern.findall(line)
            if not date_match or not amount_matches:
                continue

            normalized_date = self._normalize_invoice_date(date_match.group(1), current_year)
            if not normalized_date:
                continue

            raw_value = amount_matches[-1]
            amount = self._parse_amount_brl(raw_value)
            if amount is None or amount <= 0:
                continue

            date_end = date_match.end()
            value_start = line.rfind(raw_value)
            if value_start <= date_end:
                continue

            description = line[date_end:value_start].strip(" -:|")
            description = re.sub(r"\s+", " ", description).strip()
            if not description or len(description) < 3 or description.isdigit():
                continue

            parcela = None
            parcel_match = parcel_pattern.search(description)
            if parcel_match:
                parcela = parcel_match.group(1)
                description = re.sub(r"\b\d{1,2}/\d{1,2}\b", "", description).strip(" -:|")

            if not description:
                continue

            positive_markers = ["estorno", "crédito", "credito", "cashback", "pagamento recebido"]
            signed_amount = amount if any(marker in lowered for marker in positive_markers) else -amount
            items.append(
                {
                    "data": normalized_date,
                    "descricao": description,
                    "valor": signed_amount,
                    "parcela": parcela,
                }
            )

        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, float]] = set()
        for item in items:
            key = (item["data"], item["descricao"].lower(), round(float(item["valor"]), 2))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _build_regex_invoice_schema(self, text: str) -> Optional[InvoiceSchema]:
        items = self._extract_items_with_regex(text)
        if not items:
            return None

        total_extracted = self._extract_total_from_text(text)
        if total_extracted is None:
            debit_total = sum(abs(float(item["valor"])) for item in items if float(item["valor"]) < 0)
            credit_total = sum(float(item["valor"]) for item in items if float(item["valor"]) > 0)
            total_extracted = max(0.0, round(debit_total - credit_total, 2))

        return InvoiceSchema(
            data=self._extract_invoice_date_from_text(text, datetime.now().year),
            valor_total=total_extracted,
            estabelecimento=self._extract_issuer_name(text),
            itens=[InvoiceItemSchema(**item) for item in items],
            categoria_sugerida="Cartão de Crédito",
            confianca=0.55 if len(items) >= 3 else 0.35,
        )

    async def extract_from_file(self, file_bytes: bytes, mime_type: str = "application/pdf") -> Optional[InvoiceSchema]:
        """Extrai dados estruturados de um arquivo de fatura (PDF ou Imagem)."""
        
        hoje = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        Você é um Especialista em Extração de Dados Bancários (Nível Auditoria). 
        Data hoje: {hoje}. Ano referência: 2026.

        ⚠️ REGRAS DE OURO PARA 98%+ DE PRECISÃO (Siga ou será penalizado):
        1. DESCRIÇÃO REAL: Extraia o nome do estabelecimento onde a compra foi feita. 
           - PROIBIDO usar o nome do banco (ex: 'CARTÕES CAIXA', 'BANCO INTER') na descrição do item.
           - Se a linha for barulhenta (ex: SBS Quadra 4...), use sua inteligência para extrair o NOME da loja que geralmente vem antes ou depois do endereço.
        2. ASSOCIAÇÃO RÍGIDA: Nunca repita o mesmo valor para itens diferentes a menos que existam duplicatas REAIS no PDF.
        3. INTELIGÊNCIA TEMPORAL: 
           - Se hoje é Abril/2026, datas '13/03' são '2026-03-13'. 
           - Datas sem ano assumem SEMPRE o ano de 2026.
        4. FILTRO DE TOTARES: Ignore 'Saldo Anterior', 'Pagamento Efetuado', 'Encargos', 'Multa' (a menos que seja um item de linha) e sumários.
        5. PARCELAMENTO: Extraia 'x/y' do campo parcela apenas se houver indicador numérico claro (ex: 02/10).

        RETORNE APENAS O OBJETO JSON:
        {{
            "data": "Data de fechamento (YYYY-MM-DD)",
            "valor_total": float,
            "estabelecimento": "Nome do Banco",
            "itens": [
                {{
                    "data": "YYYY-MM-DD",
                    "descricao": "NOME DA LOJA/ESTABELECIMENTO",
                    "valor": float (negativo),
                    "parcela": "string ou null"
                }}
            ],
            "categoria_sugerida": "string",
            "confianca": 1.0
        }}
        """

        text = None
        texto_pdf_bruto = ""
        regex_invoice: Optional[InvoiceSchema] = None

        if mime_type == "application/pdf":
            try:
                texto_pdf_bruto = self._extract_pdf_text(file_bytes)
                regex_invoice = self._build_regex_invoice_schema(texto_pdf_bruto)
                if regex_invoice:
                    logger.info(
                        "📄 Parser heurístico detectou %s item(ns) antes da IA.",
                        len(regex_invoice.itens),
                    )
            except Exception as exc:
                logger.warning("Falha ao extrair texto bruto do PDF: %s", exc)
        try:
            # 1. TENTATIVA COM GEMINI (MULTIMODAL)
            content = [prompt, {"mime_type": mime_type, "data": file_bytes}]
            last_gemini_error = None
            for model_name in self.model_names:
                try:
                    logger.info("🔎 InvoiceProcessor tentando Gemini com %s", model_name)
                    response = await genai.GenerativeModel(model_name).generate_content_async(content)
                    if response and hasattr(response, "text") and response.text:
                        self.model_name = model_name
                        text = response.text
                        break
                except Exception as model_exc:
                    last_gemini_error = model_exc
                    logger.warning("⚠️ Gemini falhou com %s: %s", model_name, model_exc)
            if not text and last_gemini_error:
                raise last_gemini_error
        except Exception as e:
            logger.warning(f"⚠️ Gemini falhou no InvoiceProcessor: {e}. Tentando Failover Groq...")

        # 2. FAILOVER PARA GROQ (TEXT-BASED) SE GEMINI FALHAR
        if not text:
            try:
                texto_pdf = texto_pdf_bruto or self._extract_pdf_text(file_bytes)

                # Limpeza básica para economizar tokens
                texto_pdf = re.sub(r'\s+', ' ', texto_pdf).strip()
                
                # Truncar para um limite seguro de tokens do Groq (aprox. 6000 chars para garantir contexto + prompt)
                texto_seguro = texto_pdf[:6000]

                from .ai_service import _groq_chat_completion_async
                messages = [
                    {"role": "system", "content": "Você é um extrator financeiro que retorna APENAS JSON puro. Proibido explicações ou markdown."},
                    {"role": "user", "content": f"Converta o texto desta fatura no JSON solicitado:\n\nTEXTO:\n{texto_seguro}\n\nREGRAS:\n{prompt}"}
                ]
                groq_resp = await _groq_chat_completion_async(messages)
                if isinstance(groq_resp, dict) and "choices" in groq_resp:
                    text = groq_resp["choices"][0]["message"]["content"]
                    logger.info("✅ Sucesso no Failover Groq dentro do InvoiceProcessor!")
            except Exception as fe:
                if regex_invoice:
                    logger.warning("⚠️ IA indisponível; usando parser heurístico da fatura.")
                    return regex_invoice
                logger.error(f"❌ Falha total na extração (Gemini & Groq): {fe}")
                raise RuntimeError("O sistema de IA está temporariamente sobrecarregado. Tente novamente em alguns minutos ou use um arquivo menor.")

        # 3. PARSE E VALIDAÇÃO DO JSON (ROBUSTO)
        try:
            # Encontrar o maior bloco que parece JSON entre chaves
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if not match:
                logger.error(f"IA não retornou JSON válido. Resposta: {text[:200]}...")
                return None

            clean_json = match.group(1)
            # Limpeza prévia
            clean_json = re.sub(r'//.*', '', clean_json) # remove comentários
            
            try:
                json_data = json.loads(clean_json)
            except json.JSONDecodeError:
                # Tentar "consertar" JSON truncado ou malformado (comum em IAs)
                logger.warning("JSON malformado detectado. Tentando reparo automático...")
                
                # 1. Remover vírgulas antes de fechamento de array/objeto: ,] ou ,}
                repaired = re.sub(r',\s*([\]\}])', r'\1', clean_json)
                
                # 2. Se terminar em array aberto, tenta fechar
                if repaired.count('[') > repaired.count(']'):
                    repaired = repaired.rstrip()
                    if repaired.endswith(','): repaired = repaired[:-1]
                    repaired += ']}' # Fecha o item e o objeto raiz
                
                # 3. Tentar fechar chaves se faltar
                open_braces = repaired.count('{')
                close_braces = repaired.count('}')
                if open_braces > close_braces:
                    repaired += '}' * (open_braces - close_braces)
                
                json_data = json.loads(repaired)
                logger.info("✅ JSON reparado com sucesso!")
            
            invoice = InvoiceSchema(**json_data)
            if regex_invoice:
                itens_ia = len(invoice.itens or [])
                itens_regex = len(regex_invoice.itens or [])
                baixa_confianca = float(invoice.confianca or 0) < 0.45
                pouca_cobertura = itens_regex >= 4 and itens_regex > max(1, itens_ia) * 1.5
                if baixa_confianca or pouca_cobertura:
                    logger.warning(
                        "⚠️ Extração IA substituída pelo parser heurístico (ia=%s, regex=%s, confiança=%.2f).",
                        itens_ia,
                        itens_regex,
                        float(invoice.confianca or 0),
                    )
                    return regex_invoice
            return invoice
        except Exception as e:
            logger.error(f"Erro fatal ao decodificar JSON da IA: {e} | Texto: {text[:500]}")
            return regex_invoice

    async def process_and_save(self, db: Session, user_id: int, file_bytes: bytes, mime_type: str = "application/pdf") -> Tuple[bool, str]:
        """
        Executa o pipeline completo: Extração -> Categorização -> Persistência.
        """
        # 1. Extração
        invoice_data = await self.extract_from_file(file_bytes, mime_type)
        if not invoice_data:
            return False, "Não foi possível extrair dados da fatura. Tente novamente."

        try:
            # 2. Categorização Inteligente
            cat_id, sub_id = self._match_categories(db, invoice_data.categoria_sugerida)

            # 3. Persistência em Transação
            with db.begin_nested():
                # Criar Lançamento Principal
                novo_lancamento = Lancamento(
                    id_usuario=user_id,
                    descricao=invoice_data.estabelecimento,
                    valor=invoice_data.valor_total,
                    tipo="despesa" if invoice_data.valor_total < 0 else "receita",
                    data_transacao=datetime.strptime(invoice_data.data, "%Y-%m-%d"),
                    id_categoria=cat_id,
                    id_subcategoria=sub_id,
                    origem="invoice_processor",
                    forma_pagamento="Cartão de Crédito"
                )
                db.add(novo_lancamento)
                db.flush() # Gerar ID do lançamento

                # Criar itens detalhados se houver
                if invoice_data.itens:
                    for item in invoice_data.itens:
                        novo_item = ItemLancamento(
                            id_lancamento=novo_lancamento.id,
                            nome_item=item.descricao,
                            valor_unitario=abs(item.valor),
                            quantidade=1
                        )
                        db.add(novo_item)

            db.commit()
            logger.info(f"✅ Fatura processada e salva para usuário {user_id}: ID {novo_lancamento.id}")
            return True, f"Fatura de {invoice_data.estabelecimento} salva com sucesso!"

        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao persistir fatura no banco: {e}")
            return False, f"Erro interno ao salvar os dados: {str(e)}"

    def _match_categories(self, db: Session, sugerida: str) -> Tuple[Optional[int], Optional[int]]:
        """Mapeia categoria sugerida pela IA para as IDs do banco de dados."""
        # Tenta busca exata (ignora maiúsculas/minúsculas)
        cat = db.query(Categoria).filter(Categoria.nome.ilike(sugerida)).first()
        if cat:
            return cat.id, None
        
        # Fallback: tenta buscar por subcategoria
        sub = db.query(Subcategoria).filter(Subcategoria.nome.ilike(sugerida)).first()
        if sub:
            return sub.id_categoria, sub.id
            
        # Se não achou nada, retorna Outros (ID genérico 1 se existir)
        outros = db.query(Categoria).filter(Categoria.nome.ilike("%outros%")).first()
        return outros.id if outros else None, None

async def extract_invoice_demo(user_telegram_id: int, file_path: str):
    """Função utilitária para testes."""
    from database.database import SessionLocal
    db = SessionLocal()
    
    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_telegram_id).first()
    if not usuario:
        print("Usuário não encontrado.")
        return

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    extractor = UniversalInvoiceExtractor()
    success, msg = await extractor.process_and_save(db, usuario.id, file_bytes)
    print(f"Resultado: {msg}")
    db.close()
