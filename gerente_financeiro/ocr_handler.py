import os
import logging
import json
import re
import asyncio
from datetime import datetime, timedelta
import io
import traceback
from pathlib import Path

from urllib.parse import quote
from pdf2image import convert_from_bytes
from PIL import Image
import google.generativeai as genai
from google.cloud import vision
import requests
try:
    from google.api_core.exceptions import ResourceExhausted
except Exception:  # pragma: no cover - fallback em ambientes sem api_core
    ResourceExhausted = None
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session, joinedload 
from sqlalchemy import and_, func 

import config
from database.database import get_or_create_user, get_db
from models import Lancamento, ItemLancamento, Categoria, Subcategoria, Usuario
from .gamification_utils import give_xp_for_action
from .states import OCR_CONFIRMATION_STATE

# Configurar logging específico para OCR com arquivo dedicado
def setup_ocr_logging():
    """Configurar logging específico para OCR com arquivo separado"""
    debug_logs_dir = Path("debug_logs")
    debug_logs_dir.mkdir(exist_ok=True)
    
    # Arquivo de log específico para OCR
    ocr_log_file = debug_logs_dir / f"ocr_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Handler específico para OCR
    ocr_handler = logging.FileHandler(ocr_log_file, encoding='utf-8')
    ocr_handler.setLevel(logging.DEBUG)
    
    # Formato mais detalhado
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ocr_handler.setFormatter(formatter)
    
    # Logger específico para OCR
    ocr_logger = logging.getLogger('OCR_DETAILED')
    ocr_logger.setLevel(logging.DEBUG)
    ocr_logger.addHandler(ocr_handler)
    
    return ocr_logger, ocr_log_file

# Logger principal e detalhado
logger = logging.getLogger(__name__)
ocr_detailed_logger, current_ocr_log = setup_ocr_logging()


def _is_quota_error(err: Exception) -> bool:
    if ResourceExhausted and isinstance(err, ResourceExhausted):
        return True
    msg = str(err).lower()
    return "quota" in msg or "resource_exhausted" in msg or "429" in msg


def _groq_generate_content(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    payload = {
        "model": config.GROQ_MODEL_NAME,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "Responda apenas com um JSON valido, sem markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def _generate_with_groq(prompt: str) -> str | None:
    if not config.GROQ_API_KEY:
        return None
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _groq_generate_content, prompt)
    except Exception as exc:
        logger.error("Falha ao processar OCR com Groq: %s", exc, exc_info=True)
        return None


def _get_webapp_url(tab: str | None = None, draft: dict | None = None) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:5000").rstrip("/")
    url = f"{base_url}/webapp"
    params = []
    if tab:
        params.append(f"tab={quote(tab, safe='')}")
    if draft:
        params.append(f"draft={quote(json.dumps(draft, ensure_ascii=False), safe='')}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url

# Decorator para logging EXTREMAMENTE detalhado de funções OCR
def debug_ocr_function(func):
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        
        # Log no logger principal
        logger.info(f"🔍 [OCR-DEBUG] Iniciando {func_name}")
        
        # Log DETALHADO no logger específico
        ocr_detailed_logger.info(f"🚀 INICIANDO FUNÇÃO: {func_name}")
        ocr_detailed_logger.debug(f"� ARGUMENTOS: args={len(args)}, kwargs={list(kwargs.keys())}")
        
        # Informações do ambiente no início
        ocr_detailed_logger.debug(f"🌍 AMBIENTE:")
        ocr_detailed_logger.debug(f"   RENDER: {os.getenv('RENDER', 'False')}")
        ocr_detailed_logger.debug(f"   GOOGLE_APPLICATION_CREDENTIALS: {'SET' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else 'NOT_SET'}")
        ocr_detailed_logger.debug(f"   GOOGLE_VISION_CREDENTIALS_JSON: {'SET' if os.getenv('GOOGLE_VISION_CREDENTIALS_JSON') else 'NOT_SET'}")
        ocr_detailed_logger.debug(f"   GEMINI_API_KEY: {'SET' if os.getenv('GEMINI_API_KEY') else 'NOT_SET'}")
        
        start_time = datetime.now()
        try:
            ocr_detailed_logger.info(f"⚙️ EXECUTANDO: {func_name}")
            result = func(*args, **kwargs)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            # Log de sucesso
            logger.info(f"✅ [OCR-DEBUG] {func_name} concluído em {execution_time:.0f}ms")
            ocr_detailed_logger.info(f"✅ SUCESSO: {func_name} executado em {execution_time:.0f}ms")
            ocr_detailed_logger.debug(f"📄 RESULTADO: {type(result).__name__}")
            
            return result
        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            # Log de erro DETALHADO
            error_msg = str(e)
            error_type = type(e).__name__
            full_traceback = traceback.format_exc()
            
            logger.error(f"❌ [OCR-DEBUG] {func_name} falhou em {execution_time:.0f}ms: {error_msg}")
            
            ocr_detailed_logger.error(f"❌ ERRO: {func_name} falhou em {execution_time:.0f}ms")
            ocr_detailed_logger.error(f"🚨 TIPO DO ERRO: {error_type}")
            ocr_detailed_logger.error(f"📝 MENSAGEM: {error_msg}")
            ocr_detailed_logger.error(f"🔍 TRACEBACK COMPLETO:")
            ocr_detailed_logger.error(full_traceback)
            
            # Informações adicionais de contexto
            ocr_detailed_logger.error(f"🌍 CONTEXTO DO ERRO:")
            ocr_detailed_logger.error(f"   Função: {func_name}")
            ocr_detailed_logger.error(f"   Argumentos: {len(args)} args, {len(kwargs)} kwargs")
            ocr_detailed_logger.error(f"   Tempo até erro: {execution_time:.0f}ms")
            
            raise
    return wrapper

# Configurar credenciais do Google Vision
def setup_google_credentials():
    """🚀 CONFIGURAÇÃO ROBUSTA: Secret Files > Env Vars > Local Files"""
    try:
        logger.info("🔧 Configurando credenciais Google Vision...")
        
        # 🥇 RENDER: Primeira prioridade - Secret Files
        secret_file_path = '/etc/secrets/google_vision_credentials.json'
        if os.path.exists(secret_file_path):
            logger.info("🔐 RENDER SECRET FILES: Detectado google_vision_credentials.json")
            try:
                # Validar JSON do Secret File
                with open(secret_file_path, 'r') as f:
                    credentials_data = json.load(f)
                
                # Verificar campos obrigatórios
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                for field in required_fields:
                    if field not in credentials_data:
                        logger.error(f"❌ Campo '{field}' ausente no Secret File")
                        raise ValueError(f"Campo obrigatório '{field}' ausente")
                
                # Configurar variável de ambiente para Google Cloud
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = secret_file_path
                logger.info("✅ RENDER SECRET FILES: Credenciais configuradas com sucesso!")
                return True
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON inválido no Secret File: {e}")
            except Exception as e:
                logger.error(f"❌ Erro ao processar Secret File: {e}")
        
        # 🥈 RENDER: Segunda prioridade - JSON direto da variável
        google_creds_json = os.getenv('GOOGLE_VISION_CREDENTIALS_JSON')
        if google_creds_json:
            logger.info("📦 RENDER ENV VAR: Detectado GOOGLE_VISION_CREDENTIALS_JSON")
            try:
                # Criar arquivo temporário com as credenciais
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_creds_file = os.path.join(temp_dir, 'google_vision_render_creds.json')
                
                # Escrever credenciais no arquivo temporário
                with open(temp_creds_file, 'w') as f:
                    f.write(google_creds_json)
                
                # Verificar se o arquivo foi criado corretamente
                if os.path.exists(temp_creds_file):
                    file_size = os.path.getsize(temp_creds_file)
                    logger.info(f"✅ RENDER ENV VAR: Arquivo temporário criado ({file_size} bytes)")
                    
                    # Validar JSON
                    try:
                        with open(temp_creds_file, 'r') as f:
                            creds_data = json.load(f)
                        logger.info(f"✅ RENDER: JSON válido - projeto: {creds_data.get('project_id', 'N/A')}")
                        
                        # Configurar variável de ambiente
                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_creds_file
                        logger.info("✅ RENDER: Google Vision configurado com sucesso!")
                        return True
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ RENDER: JSON inválido: {e}")
                else:
                    logger.error("❌ RENDER: Arquivo temporário não foi criado")
                    
            except Exception as e:
                logger.error(f"❌ RENDER: Erro ao configurar credenciais JSON: {e}")
        else:
            logger.info("ℹ️ GOOGLE_VISION_CREDENTIALS_JSON não encontrada (normal para local)")
        
        # 🏠 LOCAL: Verificar variável de ambiente existente
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if os.path.exists(cred_path):
                logger.info(f"✅ LOCAL: Credenciais já configuradas: {cred_path}")
                return True
            else:
                logger.warning(f"⚠️ LOCAL: Caminho não existe: {cred_path}")
        
        # 🗂️ LOCAL: Tentar arquivos de credenciais locais
        base_dir = os.path.dirname(os.path.dirname(__file__))
        possible_paths = [
            os.path.join(base_dir, 'credenciais', 'google_vision_credentials.json'),
            os.path.join(base_dir, 'credenciais', 'service-account-key.json'), 
            os.path.join(base_dir, 'credenciais', 'credentials.json'),
        ]
        
        for credentials_path in possible_paths:
            if os.path.exists(credentials_path):
                # Validar se o JSON é válido
                try:
                    with open(credentials_path, 'r') as f:
                        creds_data = json.load(f)
                    
                    if creds_data.get('type') == 'service_account':
                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                        logger.info(f"✅ LOCAL: Credenciais válidas configuradas: {credentials_path}")
                        return True
                    else:
                        logger.warning(f"⚠️ Arquivo não é service account: {credentials_path}")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON inválido em {credentials_path}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao validar {credentials_path}: {e}")
                
        # ⚠️ Nenhuma credencial encontrada
        logger.warning("⚠️ Nenhuma credencial Google Vision encontrada")
        logger.info("� Sistema continuará com fallback Gemini apenas")
        return False
        
    except Exception as e:
        logger.error(f"❌ Erro crítico ao configurar credenciais: {e}")
        return False

# Configurar credenciais na inicialização
setup_google_credentials()

PROMPT_IA_OCR = """
**TAREFA:** Você é uma API especialista em analisar notas fiscais e comprovantes brasileiros para extrair e classificar os dados em um objeto JSON.
**REGRAS CRÍTICAS:**
- **SEMPRE** retorne um único objeto JSON válido, sem nenhum texto antes ou depois.
- Se um campo não for encontrado, retorne `null`.
**CONTEXTO DE CATEGORIAS DISPONÍVEIS:**
Use **EXATAMENTE** uma das seguintes categorias e suas respectivas subcategorias para classificar a transação.
{categorias_disponiveis}
**REGRAS DE EXTRAÇÃO:**
1. `documento_fiscal`: CNPJ/CPF do estabelecimento (apenas números).
2. `nome_estabelecimento`: Nome da loja/empresa. Para PIX, o nome do pagador. Para maquininhas (Cielo, Rede), use "Compra no Cartão".
3. `valor_total`: Valor final da transação.
4. `data` e `hora`: Data (dd/mm/yyyy) e hora (HH:MM:SS) da transação.
5. `forma_pagamento`: PIX, Crédito, Débito, Dinheiro, etc.
6. `tipo_transacao`: "Entrada" para recebimentos, "Saída" para compras.
7. `itens`: Uma lista de objetos com `nome_item`, `quantidade`, `valor_unitario`. Para comprovantes sem itens detalhados, retorne `[]`.
8. `categoria_sugerida`: Com base nos itens e no estabelecimento, escolha a MELHOR categoria da lista fornecida.
9. `subcategoria_sugerida`: Após escolher a categoria, escolha a MELHOR subcategoria correspondente da lista.
**EXEMPLO DE SAÍDA PERFEITA (FARMÁCIA):**
```json
{{
    "documento_fiscal": "12345678000199",
    "nome_estabelecimento": "DROGARIA PACHECO",
    "valor_total": 55.80,
    "data": "28/06/2025",
    "hora": "15:30:00",
    "forma_pagamento": "Crédito",
    "tipo_transacao": "Saída",
    "itens": [
        {{"nome_item": "DORFLEX", "quantidade": 1, "valor_unitario": 25.50}},
        {{"nome_item": "VITAMINA C", "quantidade": 1, "valor_unitario": 30.30}}
    ],
    "categoria_sugerida": "Saúde",
    "subcategoria_sugerida": "Farmácia"
}}
TEXTO EXTRAÍDO DO OCR PARA ANÁLISE:
{texto_ocr}
"""

async def _reply_with_summary(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """
    Gera e envia o resumo da transação lida pelo OCR. (Função sem alterações)
    """
    dados_ia = context.user_data.get('dados_ocr')
    if not dados_ia:
        return
    # ... (O código desta função permanece exatamente o mesmo que o seu original) ...
    tipo_atual = dados_ia.get('tipo_transacao', 'Saída')
    tipo_emoji = "🔴" if tipo_atual == 'Saída' else "🟢"
    doc = dados_ia.get('documento_fiscal') or "N/A"
    tipo_doc = "CNPJ" if len(str(doc)) == 14 else "CPF"
    categoria_sugerida = dados_ia.get('categoria_sugerida', 'N/A')
    subcategoria_sugerida = dados_ia.get('subcategoria_sugerida', 'N/A')
    categoria_str = f"{categoria_sugerida} / {subcategoria_sugerida}" if subcategoria_sugerida != 'N/A' else categoria_sugerida
    valor_float = float(dados_ia.get('valor_total', 0.0))

    itens_str = ""
    itens_lista = dados_ia.get('itens', [])
    if itens_lista:
        itens_formatados = []
        for item in itens_lista:
            nome = item.get('nome_item', 'N/A')
            qtd = item.get('quantidade', 1)
            val_unit = float(item.get('valor_unitario', 0.0))
            itens_formatados.append(f"  • {qtd}x {nome} - <code>R$ {val_unit:.2f}</code>")
        itens_str = "\n🛒 <b>Itens Comprados:</b>\n" + "\n".join(itens_formatados)

    msg = (
        f"🧾 <b>Resumo da Transação</b>\n\n"
        f"🏢 <b>Estabelecimento:</b> {dados_ia.get('nome_estabelecimento', 'N/A')}\n"
        f"🆔 <b>{tipo_doc}:</b> {doc}\n"
        f"📂 <b>Categoria Sugerida:</b> {categoria_str}\n"
        f"📅 <b>Data:</b> {dados_ia.get('data', 'N/A')} 🕒 <b>Hora:</b> {dados_ia.get('hora', 'N/A')}\n"
        f"💳 <b>Pagamento:</b> {dados_ia.get('forma_pagamento', 'N/A')}"
        f"{itens_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Tipo:</b> {tipo_atual} {tipo_emoji}\n"
        f"💰 <b>Valor Total:</b> <code>R$ {valor_float:.2f}</code>\n\n"
        f"✅ <b>Está tudo correto?</b>"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="ocr_salvar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="ocr_cancelar")],
        [InlineKeyboardButton("✍️ Editar no Miniapp", web_app=WebAppInfo(url=_get_webapp_url("editar", draft=dados_ia)))]
    ]

    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

@debug_ocr_function
async def ocr_iniciar_como_subprocesso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    🚨 VERSÃO COMPLETAMENTE REESCRITA - OCR Ultra Robusto
    """
    
    # 🔥 LOGS DETALHADOS PARA DEBUG
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"🚀 [LANCAMENTO-DEBUG] OCR iniciado por usuário: {username} (ID: {user_id})")
    
    # Log do ambiente
    logger.info(f"🔧 [LANCAMENTO-DEBUG] Ambiente: {'RENDER' if os.getenv('RENDER_SERVICE_NAME') else 'LOCAL'}")
    logger.info(f"🔧 [LANCAMENTO-DEBUG] Google Vision Creds: {'✅' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else '❌'}")
    logger.info(f"🔧 [LANCAMENTO-DEBUG] Gemini API: {'✅' if config.GEMINI_API_KEY else '❌'}")
    
    if update.message and update.message.document and update.message.document.mime_type == "application/pdf":
        await update.message.reply_text(
            "📄 PDF detectado! Vou tratar como <b>fatura</b> e importar os lancamentos em lote.",
            parse_mode="HTML",
        )
        from .fatura_handler import fatura_receive_file

        return await fatura_receive_file(update, context)

    message = await update.message.reply_text(
        "📸 Imagem recebida! Vou tratar como <b>lancamento</b> (PDF vira fatura).",
        parse_mode="HTML",
    )
    
    try:
        # ===== FASE 1: CAPTURA DO ARQUIVO =====
        logger.info("📥 FASE 1: Capturando arquivo do Telegram")
        
        is_photo = bool(update.message.photo)
        file_source = update.message.photo[-1] if is_photo else update.message.document
        
        logger.info(f"📄 Tipo de arquivo: {'Foto' if is_photo else 'Documento'}")
        
        if not is_photo and update.message.document:
            logger.info(f"📎 MIME Type: {update.message.document.mime_type}")
            logger.info(f"📎 Nome arquivo: {update.message.document.file_name}")
        
        await message.edit_text("📥 Baixando arquivo do Telegram...")
        
        telegram_file = await file_source.get_file()
        file_bytearray = await telegram_file.download_as_bytearray()
        file_bytes = bytes(file_bytearray)
        
        logger.info(f"✅ Arquivo baixado: {len(file_bytes)} bytes")
        
        # ===== FASE 2: PROCESSAMENTO DE PDF/IMAGEM =====
        logger.info("🔄 FASE 2: Processando arquivo para OCR")
        
        image_content_for_vision = None
        
        if not is_photo and file_source.mime_type == 'application/pdf':
            await message.edit_text("📄 Convertendo PDF para imagem...")
            logger.info("📄 Detectado PDF - convertendo...")
            
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, fmt='png', dpi=150)
                
                if not images:
                    logger.error("❌ Falha na conversão PDF->Imagem")
                    await message.edit_text("❌ PDF não pôde ser convertido.")
                    return ConversationHandler.END
                
                # Redimensionar se muito grande
                img = images[0]
                max_size = 2048
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                    logger.info(f"📏 PDF redimensionado: {img.size}")
                
                with io.BytesIO() as output:
                    img.save(output, format="PNG", optimize=True, quality=85)
                    image_content_for_vision = output.getvalue()
                    
                logger.info(f"✅ PDF convertido: {len(image_content_for_vision)} bytes")
                
            except Exception as pdf_error:
                logger.error(f"❌ Erro conversão PDF: {pdf_error}")
                await message.edit_text(f"❌ Erro ao processar PDF: {str(pdf_error)}")
                return ConversationHandler.END
        else:
            # Processar imagem direta com validações
            logger.info("🖼️ Processando imagem direta...")
            
            try:
                # Abrir com PIL para validação e otimização
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes))
                
                logger.info(f"📸 Imagem original: {img.size} - Modo: {img.mode} - Formato: {img.format}")
                
                # Converter para RGB se necessário
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                    logger.info("🎨 Convertido para RGB")
                
                # Redimensionar se muito grande (Google Vision tem limite)
                max_size = 2048
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                    logger.info(f"📏 Imagem redimensionada: {img.size}")
                
                # Salvar como JPEG otimizado
                with io.BytesIO() as output:
                    img.save(output, format="JPEG", optimize=True, quality=85)
                    image_content_for_vision = output.getvalue()
                
                logger.info(f"✅ Imagem processada: {len(image_content_for_vision)} bytes")
                
            except Exception as img_error:
                logger.error(f"❌ Erro ao processar imagem: {img_error}")
                await message.edit_text(f"❌ Formato de imagem não suportado: {str(img_error)}")
                return ConversationHandler.END
        
        # Verificar tamanho máximo (Google Vision limit: 20MB)
        max_size_bytes = 20 * 1024 * 1024  # 20MB
        if len(image_content_for_vision) > max_size_bytes:
            logger.error(f"❌ Imagem muito grande: {len(image_content_for_vision)} bytes > {max_size_bytes}")
            await message.edit_text("❌ Imagem muito grande. Use uma imagem menor.")
            return ConversationHandler.END
        
        if not image_content_for_vision:
            logger.error("❌ Conteúdo da imagem está vazio")
            await message.edit_text("❌ Arquivo não pôde ser processado.")
            return ConversationHandler.END
        
        # ===== FASE 3: OCR COM DUPLO FALLBACK =====
        logger.info("🔍 FASE 3: Executando OCR")
        await message.edit_text("🔎 Lendo texto da imagem...")
        
        texto_ocr = ""
        ocr_method_used = "Nenhum"
        gemini_quota_error = False
        
        # 🥇 MÉTODO 1: Google Vision (Primário)
        logger.info("🔍 Tentativa 1: Google Vision API")
        try:
            # Verificar se as credenciais foram configuradas corretamente
            creds_status = setup_google_credentials()
            if not creds_status:
                raise Exception("Credenciais Google Vision não configuradas")
            
            # Verificar se GOOGLE_APPLICATION_CREDENTIALS está definida
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not creds_path or not os.path.exists(creds_path):
                raise Exception(f"Arquivo de credenciais não encontrado: {creds_path}")
            
            logger.info(f"✅ Usando credenciais: {creds_path}")
            
            # Criar cliente com timeout
            logger.info("🔌 Criando cliente Google Vision...")
            client = vision.ImageAnnotatorClient()
            
            # Preparar imagem
            logger.info(f"📸 Preparando imagem para análise ({len(image_content_for_vision)} bytes)")
            vision_image = vision.Image(content=image_content_for_vision)
            
            # Fazer requisição com timeout
            logger.info("🚀 Enviando para Google Vision API...")
            await message.edit_text("🔎 Enviando para Google Vision API...")
            
            # Requisição síncrona (Google Vision não tem versão async nativa)
            import asyncio
            
            def make_vision_request():
                # Timeout manual simples: se demorar >25s levantamos exceção controlada
                import threading
                result_container = {}
                exc_container = {}
                def target():
                    try:
                        result_container['resp'] = client.document_text_detection(image=vision_image)
                    except Exception as e:  # pragma: no cover
                        exc_container['err'] = e
                t = threading.Thread(target=target, daemon=True)
                t.start()
                t.join(timeout=25)
                if t.is_alive():
                    raise TimeoutError("Google Vision demorou >25s (timeout interno)")
                if 'err' in exc_container:
                    raise exc_container['err']
                return result_container.get('resp')
            
            # Executar em thread pool para evitar blocking
            response = await asyncio.get_event_loop().run_in_executor(None, make_vision_request)
            logger.info("⏱️ Google Vision processamento concluído dentro do timeout interno")
            
            logger.info("📥 Resposta recebida do Google Vision")
            
            # Verificar erros na resposta
            if response.error.message:
                logger.error(f"❌ Google Vision API Error: {response.error.message}")
                raise Exception(f"Google Vision API: {response.error.message}")
            
            # Extrair texto
            texto_ocr = response.full_text_annotation.text if response.full_text_annotation else ""
            ocr_method_used = "Google Vision"
            
            logger.info(f"✅ Google Vision: {len(texto_ocr)} caracteres extraídos")
            
            if texto_ocr and len(texto_ocr.strip()) >= 10:
                logger.info("🎉 Google Vision SUCESSO!")
            else:
                logger.warning(f"⚠️ Google Vision: texto insuficiente ('{texto_ocr[:50]}...')")
                raise Exception("Texto extraído muito curto ou vazio")
            
        except Exception as vision_error:
            logger.warning(f"⚠️ Google Vision falhou: {vision_error}")
            
            # 🥈 MÉTODO 2: Gemini Vision (Fallback)
            logger.info("🔄 Tentativa 2: Gemini Vision (Fallback)")
            await message.edit_text("🔄 Tentando método alternativo (Gemini)...")
            
            try:
                if not config.GEMINI_API_KEY:
                    raise Exception("GEMINI_API_KEY não configurado")
                
                logger.info("🤖 Configurando Gemini...")
                raw_key = config.GEMINI_API_KEY
                genai.configure(api_key=raw_key.strip().strip("'\"").strip().strip())
                model = genai.GenerativeModel('gemini-2.5-flash')  # ✅ Modelo 2.5 (v1beta)
                
                # Converter para PIL Image
                logger.info("🖼️ Convertendo para PIL Image...")
                from PIL import Image
                pil_image = Image.open(io.BytesIO(image_content_for_vision))
                
                logger.info(f"✅ PIL Image: {pil_image.size} - Modo: {pil_image.mode}")
                
                # Converter para RGB se necessário
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                    logger.info("🎨 Convertido para RGB")
                
                prompt = """
                TAREFA: Extrair TODO o texto visível desta imagem de nota fiscal ou comprovante.
                
                INSTRUÇÕES:
                - Leia TODOS os números, valores, nomes, datas que conseguir
                - Mantenha a estrutura original do texto
                - Inclua estabelecimento, valor total, data, forma de pagamento
                - Se não conseguir ler NADA, retorne exatamente: ERRO_OCR
                
                RESPOSTA: Apenas o texto extraído, sem comentários.
                """
                
                logger.info("🚀 Enviando para Gemini Vision...")
                response = await model.generate_content_async([prompt, pil_image])
                texto_gemini = response.text.strip()
                
                logger.info(f"📥 Gemini Response: '{texto_gemini[:100]}...' (len: {len(texto_gemini)})")
                
                if texto_gemini and texto_gemini != 'ERRO_OCR' and len(texto_gemini) > 10:
                    texto_ocr = texto_gemini
                    ocr_method_used = "Gemini Vision"
                    logger.info(f"✅ Gemini Vision: {len(texto_ocr)} caracteres extraídos")
                else:
                    logger.warning(f"⚠️ Gemini Vision retornou: '{texto_gemini[:50]}...'")
                    
            except Exception as gemini_error:
                if _is_quota_error(gemini_error):
                    gemini_quota_error = True
                logger.error(f"❌ Gemini Vision falhou: {gemini_error}")
        
        # ===== VERIFICAÇÃO FINAL DO TEXTO =====
        logger.info(f"🔍 Verificação final: Método={ocr_method_used}, Tamanho={len(texto_ocr)}")
        
        if not texto_ocr or len(texto_ocr.strip()) < 10:
            logger.error(f"❌ OCR FALHOU: Texto insuficiente (tamanho: {len(texto_ocr)})")
            logger.error(f"Texto extraído: '{texto_ocr[:100] if texto_ocr else 'VAZIO'}'")
            
            quota_note = "\n🧠 <b>IA indisponivel:</b> limite diario atingido." if gemini_quota_error else ""
            await message.edit_text(
                "❌ <b>Falha na Leitura do OCR</b>\n\n"
                f"🔧 <b>Método testado:</b> {ocr_method_used}\n"
                f"� <b>Caracteres extraídos:</b> {len(texto_ocr)}\n"
                f"{quota_note}\n\n"
                "💡 <b>Soluções:</b>\n"
                "📸 Foto mais clara e bem iluminada\n"
                "� Zoom na parte importante da nota\n"
                "📝 Ou digite os dados manualmente:\n\n"
                "<code>Local: Nome do estabelecimento\n"
                "Valor: 25.50\n"
                "Data: 24/08/2025</code>",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        logger.info(f"✅ OCR SUCESSO: {len(texto_ocr)} caracteres - Método: {ocr_method_used}")
        
        # ===== FASE 4: PROCESSAMENTO COM IA =====
        logger.info("🧠 FASE 4: Analisando com IA")
        await message.edit_text(f"🧠 Texto extraído! Analisando com IA...\n<i>Método: {ocr_method_used}</i>", parse_mode='HTML')
        
        # Buscar categorias
        db: Session = next(get_db())
        try:
            categorias_db = db.query(Categoria).options(joinedload(Categoria.subcategorias)).all()
            categorias_formatadas = [
                f"- {cat.nome}: ({', '.join(sub.nome for sub in cat.subcategorias)})" for cat in categorias_db
            ]
            categorias_contexto = "\n".join(categorias_formatadas)
        finally:
            db.close()
        
        # Processar com IA
        raw_key = config.GEMINI_API_KEY
        genai.configure(api_key=raw_key.strip().strip("'\"").strip().strip())
        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        prompt = PROMPT_IA_OCR.format(texto_ocr=texto_ocr, categorias_disponiveis=categorias_contexto)
        
        try:
            ia_response = await model.generate_content_async(prompt)
            response_text = ia_response.text
        except Exception as ia_error:
            logger.error(f"❌ IA (Gemini) falhou ao analisar OCR: {ia_error}")
            if _is_quota_error(ia_error) or config.GROQ_API_KEY:
                response_text = await _generate_with_groq(prompt)
            if not response_text:
                if _is_quota_error(ia_error):
                    await message.edit_text(
                        "⚠️ Limite diario da IA atingido para analise do OCR."
                        " Tente novamente em alguns minutos ou lance manualmente.",
                        parse_mode="HTML",
                    )
                else:
                    await message.edit_text("❌ IA não conseguiu processar os dados. Tente novamente.")
                return ConversationHandler.END
        
        # Extrair JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            logger.error(f"❌ IA não retornou JSON válido: {response_text[:200]}...")
            await message.edit_text("❌ IA não conseguiu processar os dados. Tente novamente.")
            return ConversationHandler.END
        
        json_str = json_match.group(0)
        
        try:
            dados_ia = json.loads(json_str)
            logger.info("✅ Dados da IA processados com sucesso")
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON inválido da IA: {e}\nJSON: {json_str[:200]}...")
            await message.edit_text("❌ IA retornou dados inválidos. Tente novamente.")
            return ConversationHandler.END
        
        # Processar valor
        valor_bruto = dados_ia.get('valor_total')
        valor_str = str(valor_bruto or '0').replace(',', '.')
        dados_ia['valor_total'] = float(valor_str) if valor_str else 0.0
        
        # Armazenar dados
        context.user_data['dados_ocr'] = dados_ia
        
        logger.info(f"✅ PROCESSO COMPLETO: {dados_ia.get('nome_estabelecimento', 'N/A')} - R${dados_ia['valor_total']}")
        
        # ===== FASE 5: MOSTRAR RESUMO =====
        await message.delete()
        await _reply_with_summary(update, context)
        
        return OCR_CONFIRMATION_STATE
        
    except Exception as e:
        logger.error(f"💥 ERRO CRÍTICO no OCR: {type(e).__name__}: {e}", exc_info=True)
        
        # 🚨 LOGS DETALHADOS PARA RENDER DEBUG
        user_info = f"User: {username} (ID: {user_id})"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Log completo do erro
        import traceback
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'user_info': user_info,
            'timestamp': timestamp,
            'traceback': traceback.format_exc()
        }
        
        # Salvar no analytics se disponível
        try:
            from analytics.bot_analytics_postgresql import get_session, ErrorLogs
            if os.getenv('DATABASE_URL'):
                session = get_session()
                error_log = ErrorLogs(
                    user_id=user_id,
                    username=username,
                    command='lancamento_ocr',
                    error_type=type(e).__name__,
                    error_message=str(e)[:500],  # Limitar tamanho
                    timestamp=datetime.now()
                )
                session.add(error_log)
                session.commit()
                session.close()
                logger.info(f"✅ Erro OCR registrado no banco: {type(e).__name__}")
        except Exception as db_error:
            logger.warning(f"⚠️ Não foi possível salvar erro no banco: {db_error}")
        
        # Imprimir erro completo no console (para logs do Render)
        print(f"\n{'='*60}")
        print(f"💥 ERRO OCR DETALHADO - {timestamp}")
        print(f"{'='*60}")
        print(f"🔢 Tipo: {type(e).__name__}")
        print(f"📝 Mensagem: {e}")
        print(f"👤 {user_info}")
        print(f"📍 Traceback:")
        print(traceback.format_exc())
        print(f"{'='*60}\n")
        
        try:
            await message.edit_text(
                f"💥 <b>Erro Crítico no OCR</b>\n\n"
                f"🚨 <b>Tipo:</b> {type(e).__name__}\n"
                f"📝 <b>Detalhes:</b> {str(e)[:100]}...\n\n"
                f"👤 <b>Usuário:</b> {username}\n"
                f"🕒 <b>Timestamp:</b> {timestamp}\n\n"
                "💡 Tente enviar outra imagem ou digite os dados manualmente.\n"
                "🔧 O erro foi registrado no sistema.",
                parse_mode='HTML'
            )
        except Exception as msg_error:
            logger.error(f"❌ Falha ao editar mensagem de erro: {msg_error}")
            
        return ConversationHandler.END

def _to_float_safe(value, default: float = 0.0) -> float:
    try:
        return float(str(value if value is not None else default).replace(',', '.'))
    except (TypeError, ValueError):
        return float(default)


def _normalize_ocr_tipo(raw_tipo: str) -> str:
    base = str(raw_tipo or '').strip().lower()
    if base in {'entrada', 'receita', 'income'}:
        return 'Receita'
    return 'Despesa'


def _normalize_forma_pagamento(value) -> str:
    raw = str(value or '').strip().lower()
    if raw in {'pix'}:
        return 'Pix'
    if raw in {'credito', 'crédito', 'cartao de credito', 'cartão de crédito', 'cartao', 'cartão'}:
        return 'Crédito'
    if raw in {'debito', 'débito', 'cartao de debito', 'cartão de débito'}:
        return 'Débito'
    if raw in {'boleto'}:
        return 'Boleto'
    if raw in {'dinheiro', 'especie', 'espécie'}:
        return 'Dinheiro'
    return 'Nao_informado'


def _sanitize_ocr_payload(dados: dict) -> dict:
    payload = dict(dados or {})
    payload['valor_total'] = _to_float_safe(payload.get('valor_total'), 0.0)
    payload['forma_pagamento'] = _normalize_forma_pagamento(payload.get('forma_pagamento'))
    payload['tipo_transacao'] = _normalize_ocr_tipo(payload.get('tipo_transacao'))

    itens_sanitizados = []
    for item in payload.get('itens', []) or []:
        nome = str(item.get('nome_item') or 'Item desconhecido').strip()
        qtd = _to_float_safe(item.get('quantidade', 1), 1.0)
        valor_unit = _to_float_safe(item.get('valor_unitario', 0), 0.0)
        itens_sanitizados.append({
            'nome_item': nome,
            'quantidade': qtd,
            'valor_unitario': valor_unit,
        })
    payload['itens'] = itens_sanitizados

    return payload


async def ocr_action_processor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processa a ação do botão de confirmação do OCR.
    Esta função não retorna um estado, apenas realiza a ação (salvar, etc.).
    """
    query = update.callback_query
    action = query.data
    dados = context.user_data.get('dados_ocr')
    if not dados and action != 'ocr_cancelar':
        await query.answer("Erro: Dados da sessão perdidos.", show_alert=True)
        return False

    if action == "ocr_toggle_type":
        dados['tipo_transacao'] = 'Receita' if _normalize_ocr_tipo(dados.get('tipo_transacao')) == 'Despesa' else 'Despesa'
        context.user_data['dados_ocr'] = dados
        await _reply_with_summary(query, context)
        return None  # Permanece no mesmo estado, apenas atualiza a mensagem

    if action == "ocr_cancelar":
        context.user_data.pop('dados_ocr', None)
        return True

    if action == "ocr_salvar":
        await query.edit_message_text("💾 Verificando e salvando no banco de dados...")
        db: Session = next(get_db())
        try:
            dados = _sanitize_ocr_payload(dados)
            context.user_data['dados_ocr'] = dados

            # Lógica de verificação de duplicidade e salvamento (sem alterações)
            user_info = query.from_user
            usuario_db = get_or_create_user(db, user_info.id, user_info.full_name)
            data_str = dados.get('data', datetime.now().strftime('%d/%m/%Y'))
            hora_str = dados.get('hora', '00:00:00')
            try:
                data_obj = datetime.strptime(f"{data_str} {hora_str}", '%d/%m/%Y %H:%M:%S')
            except ValueError:
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
            doc_fiscal = re.sub(r'\D', '', str(dados.get('documento_fiscal', ''))) or None
            time_window_start = data_obj - timedelta(minutes=5)
            time_window_end = data_obj + timedelta(minutes=5)
            existing_lancamento = db.query(Lancamento).filter(
                and_(
                    Lancamento.id_usuario == usuario_db.id,
                    Lancamento.valor == dados.get('valor_total'),
                    Lancamento.documento_fiscal == doc_fiscal,
                    Lancamento.data_transacao.between(time_window_start, time_window_end)
                )
            ).first()
            if existing_lancamento:
                await query.edit_message_text("⚠️ Transação Duplicada! Operação cancelada.", parse_mode='Markdown')
                return False

            # Lógica de encontrar categoria/subcategoria (sem alterações)
            id_categoria, id_subcategoria = None, None
            if cat_sugerida := dados.get('categoria_sugerida'):
                categoria_obj = db.query(Categoria).filter(func.lower(Categoria.nome) == func.lower(cat_sugerida)).first()
                if categoria_obj:
                    id_categoria = categoria_obj.id
            if sub_sugerida := dados.get('subcategoria_sugerida'):
                if id_categoria:
                    subcategoria_obj = db.query(Subcategoria).filter(and_(Subcategoria.id_categoria == id_categoria, func.lower(Subcategoria.nome) == func.lower(sub_sugerida))).first()
                    if subcategoria_obj:
                        id_subcategoria = subcategoria_obj.id

            # Criação do lançamento e itens (sem alterações)
            novo_lancamento = Lancamento(
                id_usuario=usuario_db.id,
                data_transacao=data_obj,
                descricao=dados.get('nome_estabelecimento'),
                valor=dados.get('valor_total'),
                tipo=dados.get('tipo_transacao', 'Despesa'),
                forma_pagamento=dados.get('forma_pagamento', 'Nao_informado'),
                documento_fiscal=doc_fiscal,
                id_categoria=id_categoria,
                id_subcategoria=id_subcategoria,
                origem="ocr",
            )
            for item_data in dados.get('itens', []):
                valor_unit_str = str(item_data.get('valor_unitario', '0')).replace(',', '.')
                valor_unit = float(valor_unit_str) if valor_unit_str else 0.0
                qtd_str = str(item_data.get('quantidade', '1')).replace(',', '.')
                qtd = float(qtd_str) if qtd_str else 1.0
                novo_item = ItemLancamento(
                    nome_item=item_data.get('nome_item', 'Item desconhecido'),
                    quantidade=qtd,
                    valor_unitario=valor_unit
                )
                novo_lancamento.itens.append(novo_item)

            db.add(novo_lancamento)
            db.commit()
            try:
                await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_OCR", context)
            except Exception:
                logger.debug("Falha ao conceder XP do OCR (nao critico).")

            # Mensagem de sucesso será enviada pelo handler principal
            context.user_data.pop('dados_ocr', None)
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao salvar no banco (ocr_action_handler): {e}", exc_info=True)
            await query.edit_message_text("❌ Falha ao salvar no banco de dados. O erro foi registrado.")
            return False
        finally:
            db.close()
    return None

# 🚨 MÉTODO FALLBACK MELHORADO - OCR com Gemini Vision
async def ocr_fallback_gemini(image_content):
    """🔄 Método alternativo ultra robusto usando Gemini Vision"""
    try:
        logger.info("🔄 INICIANDO FALLBACK - Gemini Vision")
        
        if not config.GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY não configurado para fallback")
            return None
        
        # Configurar Gemini
        raw_key = config.GEMINI_API_KEY
        genai.configure(api_key=raw_key.strip().strip("'\"").strip().strip())
        model = genai.GenerativeModel('gemini-2.5-flash')  # ✅ Modelo 2.5 (v1beta)
        logger.info("✅ Gemini configurado")
        
        # Converter bytes para PIL Image com validação
        import PIL.Image
        import io
        
        try:
            image = PIL.Image.open(io.BytesIO(image_content))
            logger.info(f"✅ Imagem PIL criada: {image.size} - Modo: {image.mode}")
            
            # Converter para RGB se necessário
            if image.mode != 'RGB':
                image = image.convert('RGB')
                logger.info("🔄 Imagem convertida para RGB")
                
        except Exception as img_error:
            logger.error(f"❌ Erro ao processar imagem PIL: {img_error}")
            return None
        
        # Prompt otimizado para OCR
        prompt = """
        🎯 TAREFA CRÍTICA: Extrair TODO o texto desta imagem de documento/nota fiscal.

        📋 INSTRUÇÕES ESPECÍFICAS:
        - Leia TODOS os textos visíveis: números, valores, nomes, datas
        - Inclua: estabelecimento, CNPJ, valor total, data, forma pagamento
        - Mantenha estrutura e pontuação originais
        - NÃO invente informações que não estão visíveis
        - Se a imagem estiver ilegível, retorne: ERRO_OCR

        ⚡ RESPOSTA: Apenas o texto extraído, sem explicações.
        """
        
        logger.info("🚀 Enviando para Gemini Vision...")
        
        # Enviar para Gemini Vision com timeout
        response = await model.generate_content_async([prompt, image])
        
        if not response or not response.text:
            logger.warning("⚠️ Gemini Vision retornou resposta vazia")
            return None
            
        texto_extraido = response.text.strip()
        
        logger.info(f"📝 Gemini Vision Response: '{texto_extraido[:100]}...' (Total: {len(texto_extraido)} chars)")
        
        # Validação rigorosa do texto extraído
        if texto_extraido and texto_extraido != 'ERRO_OCR' and len(texto_extraido) > 15:
            
            # Verificar se contém informações úteis
            useful_patterns = [
                r'\d+[.,]\d{2}',  # Valores monetários
                r'\d{2}[/.-]\d{2}[/.-]\d{2,4}',  # Datas
                r'CNPJ|CPF|\d{2}\.\d{3}\.\d{3}',  # Documentos
                r'[A-Za-z]{3,}',  # Palavras com pelo menos 3 letras
            ]
            
            useful_content = any(re.search(pattern, texto_extraido, re.IGNORECASE) for pattern in useful_patterns)
            
            if useful_content:
                logger.info(f"✅ Gemini Vision SUCESSO: {len(texto_extraido)} caracteres úteis extraídos")
                return texto_extraido
            else:
                logger.warning(f"⚠️ Gemini Vision: texto sem conteúdo útil: '{texto_extraido[:50]}...'")
                return None
        else:
            logger.warning(f"⚠️ Gemini Vision falhou: '{texto_extraido}' (len: {len(texto_extraido)})")
            return None
            
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO no fallback Gemini Vision: {type(e).__name__}: {e}", exc_info=True)
        return None