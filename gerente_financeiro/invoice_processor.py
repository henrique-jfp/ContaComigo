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
    categoria_sugerida: str = Field(..., description="Categoria principal sugerida")
    confianca: float = Field(..., ge=0.0, le=1.0, description="Nível de confiança da extração")

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
        
        # Modelo Gemini 2.0 Flash Lite (Equilíbrio perfeito entre precisão, custo e cota)
        self.model_name = "gemini-2.0-flash-lite"
        self.model = genai.GenerativeModel(self.model_name)

    async def extract_from_file(self, file_bytes: bytes, mime_type: str = "application/pdf") -> Optional[InvoiceSchema]:
        """Extrai dados estruturados de um arquivo de fatura (PDF ou Imagem)."""
        
        hoje = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        Você é um Especialista em Extração de Dados Bancários com meta de 100% de acurácia.
        Data hoje: {hoje}. Ano referência: 2026.

        REGRAS DE OURO PARA 98%+ DE PRECISÃO:
        1. ASSOCIAÇÃO RÍGIDA: Cada 'valor' deve estar vinculado à sua 'data' e 'descrição' exatas na mesma linha/bloco. Proibido repetir o mesmo valor para datas diferentes ou vice-versa.
        2. DESCRIÇÃO COMPLETA: Extraia o nome INTEGRAL do estabelecimento. Se houver endereços (ex: SBS Quadra 4...), mantenha-os se fizerem parte da identificação única.
        3. INTELIGÊNCIA TEMPORAL: 
           - Datas DD/MM devem ser convertidas para YYYY-MM-DD.
           - Se hoje é Abril/2026, uma data '15/03' é obrigatoriamente '2026-03-15'.
           - Ignore itens com datas futuras ao fechamento da fatura.
        4. FILTRO DE TOTARES: Nunca extraia "Total", "Subtotal", "Saldo Anterior" ou "Pagamento" como se fossem compras.
        5. PARCELAMENTO: Se houver "02/10", extraia "2/10" no campo parcela e mantenha o nome da loja limpo.

        JSON OBRIGATÓRIO (APENAS O OBJETO):
        {{
            "data": "Data de fechamento (YYYY-MM-DD)",
            "valor_total": float (valor final a pagar),
            "estabelecimento": "Banco emissor",
            "itens": [
                {{
                    "data": "YYYY-MM-DD",
                    "descricao": "NOME COMPLETO LOJA",
                    "valor": float (negativo para despesa),
                    "parcela": "x/y ou null"
                }}
            ],
            "categoria_sugerida": "string",
            "confianca": float
        }}
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
                    texto_pdf += page.get_text("text")
                doc.close()

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
            # Remover possíveis comentários ou lixo antes de dar parse
            clean_json = re.sub(r'//.*', '', clean_json) # remove comentários de linha única
            
            json_data = json.loads(clean_json)
            return InvoiceSchema(**json_data)
        except Exception as e:
            logger.error(f"Erro ao decodificar JSON da IA: {e} | Texto: {text[:500]}")
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
