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
    valor: float = Field(..., description="Valor monetário (negativo para despesas)")

class InvoiceSchema(BaseModel):
    data: str = Field(..., description="Data da transação (YYYY-MM-DD)")
    valor_total: float = Field(..., description="Valor total consolidado")
    estabelecimento: str = Field(..., description="Nome do local de compra")
    itens: List[InvoiceItemSchema] = Field(default_factory=list, description="Detalhamento da fatura")
    categoria_sugerida: str = Field(..., description="Categoria sugerida (ex: Alimentação, Transporte)")
    confianca: float = Field(..., ge=0.0, le=1.0, description="Nível de confiança da extração")

    @field_validator('data')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("A data deve estar no formato YYYY-MM-DD")

# --- PROCESSADOR UNIVERSAL ---

class UniversalInvoiceExtractor:
    """
    Serviço de extração e persistência universal de faturas.
    Utiliza Gemini 2.5 Flash Lite para análise visual e textual.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key.strip().strip("'\""))
        
        # Modelo 2.5 Flash Lite (Otimizado para extração e baixo custo)
        self.model_name = "gemini-2.5-flash-lite"
        self.model = genai.GenerativeModel(self.model_name)

    async def extract_from_file(self, file_bytes: bytes, mime_type: str = "application/pdf") -> Optional[InvoiceSchema]:
        """Extrai dados estruturados de um arquivo de fatura (PDF ou Imagem)."""
        
        prompt = """
        Você é um sistema especialista em extração de faturas financeiras de alta precisão.
        Analise o documento fornecido e extraia as transações principais.
        
        REGRAS CRÍTICAS:
        1. Identifique o estabelecimento principal e a data da transação.
        2. Se houver múltiplos itens, liste-os no campo 'itens'.
        3. O 'valor_total' deve ser a soma dos itens de compra e encargos.
        4. Use valores NEGATIVOS para despesas e POSITIVOS para créditos/estornos.
        5. JUROS, IOF e MULTAS devem ser extraídos como despesas normais.
        6. IGNORE itens de sumário como "Saldo Anterior", "Pagamento Efetuado" ou "Total da Fatura".
        7. Sugira uma categoria baseada no estabelecimento (ex: Restaurante -> Alimentação).
        8. Retorne APENAS o JSON no formato abaixo, sem markdown ou explicações.

        ESQUEMA JSON:
        {
            "data": "YYYY-MM-DD",
            "valor_total": float,
            "estabelecimento": "string",
            "itens": [{"descricao": "string", "valor": float}],
            "categoria_sugerida": "string",
            "confianca": float (0.0 a 1.0)
        }
        """

        text = None
        try:
            # 1. TENTATIVA COM GEMINI (MULTIMODAL)
            content = [
                prompt,
                {"mime_type": mime_type, "data": file_bytes}
            ]
            response = await self.model.generate_content_async(content)
            if response and hasattr(response, 'text'):
                text = response.text
        except Exception as e:
            logger.warning(f"⚠️ Gemini falhou no InvoiceProcessor: {e}. Tentando Failover Groq...")

        # 2. FAILOVER PARA GROQ (TEXT-BASED) SE GEMINI FALHAR
        if not text:
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                texto_pdf = ""
                for page in doc:
                    texto_pdf += page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                doc.close()

                from .ai_service import _groq_chat_completion_async
                messages = [
                    {"role": "system", "content": "Você é um extrator financeiro de alta precisão. Extraia os dados para JSON."},
                    {"role": "user", "content": f"{prompt}\n\nTEXTO DA FATURA:\n{texto_pdf[:8000]}"}
                ]
                groq_resp = await _groq_chat_completion_async(messages)
                if isinstance(groq_resp, dict) and "choices" in groq_resp:
                    text = groq_resp["choices"][0]["message"]["content"]
                    logger.info("✅ Sucesso no Failover Groq dentro do InvoiceProcessor!")
            except Exception as fe:
                logger.error(f"❌ Falha total na extração (Gemini & Groq): {fe}")
                return None

        # 3. PARSE E VALIDAÇÃO DO JSON
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if not match:
                logger.error(f"IA não retornou JSON válido. Resposta: {text[:200]}...")
                return None

            json_data = json.loads(match.group(0))
            return InvoiceSchema(**json_data)
        except Exception as e:
            logger.error(f"Erro ao decodificar JSON da IA: {e}")
            return None

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
