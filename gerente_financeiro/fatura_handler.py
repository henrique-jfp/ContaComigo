import json
import logging
import os
import re
import uuid
import asyncio
import time
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse

import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from database.database import get_db, get_or_create_user
from models import Conta
from .services import salvar_transacoes_generica, limpar_cache_usuario
from .fatura_draft_store import create_fatura_draft, set_pending_editor_token
from .states import (
    FATURA_AWAIT_FILE,
    FATURA_CONFIRMATION_STATE,
    FATURA_TRAIN_CONSENT,
    FATURA_TRAIN_BANK,
)
from .gamification_utils import give_xp_for_action, touch_user_interaction
from .monetization import ensure_user_plan_state, plan_allows_feature, upgrade_prompt_for_feature

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_MB = int(os.getenv("FATURA_MAX_PDF_SIZE_MB", "100"))
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
MAX_PDF_PARSE_SECONDS = int(os.getenv("FATURA_PARSE_TIMEOUT_SECONDS", "300"))


def _fmt_brl(value: float) -> str:
    normalized = f"{abs(float(value)):.2f}".replace(".", ",")
    return f"R$ {normalized}"


def _compact_desc(text: str, max_len: int = 42) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "..."


def _get_fatura_webapp_url(page: str, token: str) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5000"
    base_url = str(base_url).strip().rstrip("/")

    # Telegram exige HTTPS fora de localhost para abrir web_app.
    if not base_url.startswith(("http://", "https://")):
        if base_url.startswith(("localhost", "127.0.0.1")):
            base_url = f"http://{base_url}"
        else:
            base_url = f"https://{base_url}"

    parsed = urlparse(base_url)
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        base_url = base_url.replace("http://", "https://", 1)

    params = {
        "entry": "fatura_edit",
        "page": page,
        "fatura_token": token,
        "v": str(int(time.time())),
    }
    return f"{base_url}/webapp?{urlencode(params)}"

# Versão 2.3.1 - Fix Syntax & Payload
async def _parse_fatura_pdf_with_gemini(file_bytes: bytes) -> Tuple[List[Dict], int, str, float]:
    import config
    # 🕵️ DEBUG DE CHAVE API (Mostra apenas pontas para segurança)
    api_key_debug = config.GEMINI_API_KEY or ""
    masked_key = f"{api_key_debug[:4]}...{api_key_debug[-4:]}" if len(api_key_debug) > 8 else "NAO_CONFIGURADA"
    logger.info(f"🔑 [DEBUG] Chave API Ativa: {masked_key} | Modelo: {config.GEMINI_MODEL_NAME}")

    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    # A configuração global já deve estar feita em config.py, mas reforçamos aqui
    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
    except Exception as e:
        logger.warning(f"Erro ao re-configurar genai no fatura_handler: {e}")

    # Priorizar modelos com maior cota no Free Tier para processamento de arquivos
    # gemini-2.0-flash é o melhor custo-benefício disponível.
    preferred_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]
    
    current_model = getattr(config, "GEMINI_MODEL_NAME", "gemini-2.0-flash")
    if current_model not in preferred_models:
        model_name = preferred_models[0]
    else:
        model_name = current_model

    logger.info(f"Usando modelo {model_name} para extração de fatura (config original: {current_model})")
    model = genai.GenerativeModel(model_name)
    
    prompt = f"""
    Você é um extrator de dados de faturas de cartão de crédito especialista e rigoroso.
    DATA ATUAL DO SISTEMA: {datetime.now().strftime('%d/%m/%Y')} (Considere que estamos em ABRIL de 2026).
    
    Analise o texto da fatura e extraia APENAS as compras e créditos REAIS do mês de ABRIL de 2026.
    
    REGRAS DE OURO (NÃO DESCUMPRA):
    1. IGNORE qualquer linha que diga "Total da Fatura", "Saldo Anterior", "Pagamento Efetuado", "Encargos", "Juros" ou "IOF" como se fosse uma compra. 
    2. Extraia APENAS itens que tenham uma DATA de compra clara e um ESTABELECIMENTO.
    3. Se o texto extraído via OCR/PDF estiver bagunçado, use sua inteligência para associar a DATA correta ao VALOR correto.
    4. O valor deve ser NEGATIVO para despesas (ex: -50.00) e POSITIVO para estornos ou pagamentos identificados (ex: 100.00).
    5. Se a data vier apenas como "DD/MM", assuma SEMPRE o ano de 2026.
    6. Se encontrar parcelamentos como "Loja X 02/10", extraia a descrição "Loja X" e a parcela "2/10".
    
    FORMATO JSON OBRIGATÓRIO:
    {{
        "banco": "Nome do Banco",
        "total_fatura": 0.0,
        "transacoes": [
            {{
                "data": "2026-04-DD",
                "descricao": "NOME REAL DO ESTABELECIMENTO",
                "valor": -123.45,
                "parcela": "1/12"
            }}
        ],
        "ignoradas": 0
    }}
    """
    
    pdf_part = {
        "mime_type": "application/pdf",
        "data": file_bytes
    }
    
    # 1. TENTATIVA DE EXTRAÇÃO LOCAL (Custo Zero / Ganho de Cota)
    texto_extraido_local = ""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # Preserva estrutura de colunas com "blocks"
            blocks = page.get_text("blocks")
            for b in sorted(blocks, key=lambda x: (x[1], x[0])):
                texto_extraido_local += f"{b[4]}\n"
        doc.close()
    except Exception as e:
        logger.warning(f"Falha na extração local de texto: {e}")

    # 2. ESTRATÉGIA DE EXTRAÇÃO (Otimização de Quota)
    text = None
    
    # Se temos texto extraído localmente, usamos o modo CHAT (Cota centenas de vezes maior)
    if len(texto_extraido_local.strip()) > 200:
        logger.info(f"📄 PDF pesquisável detectado ({len(texto_extraido_local)} chars). Usando modo TEXT-ONLY.")
        
        # Tenta modelos na ordem de melhor custo-benefício para chat
        models_chat = ["gemini-2.5-flash-lite", "gemini-1.5-flash"]
        for m_name in models_chat:
            try:
                logger.info(f"🤖 Tentando chat com {m_name}...")
                curr_model = genai.GenerativeModel(m_name)
                # No modo chat, passamos o texto como string, não o arquivo binário
                response = await curr_model.generate_content_async(f"{prompt}\n\nTEXTO DA FATURA:\n{texto_extraido_local[:12000]}")
                if response and hasattr(response, 'text') and response.text:
                    text = response.text
                    logger.info(f"✅ Sucesso via {m_name} (Modo Texto)!")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Modelo {m_name} falhou no chat: {e}")
                continue

    # 3. FALLBACK MULTIMODAL (Para PDFs que são imagens ou se o chat falhou)
    if not text:
        logger.info("📸 PDF parece ser imagem ou extração de texto falhou. Usando modo MULTIMODAL (Cota de Arquivo).")
        pdf_part = {"mime_type": "application/pdf", "data": file_bytes}
        models_file = ["gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-2.0-flash"]
        
        for m_name in models_file:
            try:
                logger.info(f"🤖 Tentando multimodal com {m_name}...")
                curr_model = genai.GenerativeModel(m_name)
                response = await curr_model.generate_content_async([prompt, pdf_part])
                if response and hasattr(response, 'text') and response.text:
                    text = response.text
                    logger.info(f"✅ Sucesso com multimodal {m_name}!")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Modelo {m_name} falhou no modo arquivo: {e}")
                continue

    # 4. FAILOVER FINAL (Vision OCR + Groq)
    if not text:
        logger.warning("❌ Todos os modelos Gemini falharam. Iniciando FAILOVER FINAL (Vision OCR + Groq)...")
        try:
            from .ocr_handler import ocr_fallback_gemini 
            texto_ocr = await ocr_fallback_gemini(file_bytes)
            from .ai_service import _groq_chat_completion_async
            messages = [
                {"role": "system", "content": "Você é um extrator financeiro de alta precisão. Use o texto do OCR para identificar compras. Retorne apenas JSON."},
                {"role": "user", "content": f"{prompt}\n\nTEXTO OCR:\n{texto_ocr[:8000]}"}
            ]
            groq_resp = await _groq_chat_completion_async(messages)
            if isinstance(groq_resp, dict) and "choices" in groq_resp:
                text = groq_resp["choices"][0]["message"]["content"]
                logger.info("✅ Sucesso no Failover Vision + Groq!")
        except Exception as fail_e:
            logger.error(f"Falha total no processamento: {fail_e}")
            raise RuntimeError("IA indisponível. Limites excedidos em todos os provedores.")

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("A IA não retornou um JSON válido.")
        
    data = json.loads(match.group(0))
    
    transacoes_finais = []
    ano_atual = datetime.now().year
    
    for t in data.get("transacoes", []):
        try:
            data_str = str(t.get("data", ""))
            dt_obj = None
            
            # Tenta diversos formatos de data de forma resiliente
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
                try:
                    dt_obj = datetime.strptime(data_str, fmt)
                    # Se for DD/MM, adiciona o ano atual
                    if fmt == "%d/%m":
                        dt_obj = dt_obj.replace(year=ano_atual)
                    break
                except:
                    continue
            
            if not dt_obj:
                raise ValueError(f"Formato de data desconhecido: {data_str}")

            transacoes_finais.append({
                "descricao": str(t.get("descricao", "Sem descrição")),
                "valor": float(t.get("valor", 0.0)),
                "data_transacao": dt_obj,
                "forma_pagamento": "Crédito",
                "origem": f"fatura_pdf_{str(data.get('banco', 'generico')).lower().replace(' ', '_')}",
                "parcela": t.get("parcela")
            })
        except Exception as e:
            logger.warning(f"Erro ao processar transação individual da fatura: {t} - {e}")
            continue
            
    banco = str(data.get("banco", "Desconhecido"))
    try:
        total = float(data.get("total_fatura", 0.0))
    except (ValueError, TypeError):
        total = 0.0
    ignoradas = int(data.get("ignoradas", 0))
    
    return transacoes_finais, ignoradas, banco, total


async def fatura_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await touch_user_interaction(update.effective_user.id, context)

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        ensure_user_plan_state(db, usuario_db, commit=True)
        gate = plan_allows_feature(db, usuario_db, "pdf_import")
        if not gate.allowed:
            text, keyboard = upgrade_prompt_for_feature("pdf_import")
            await update.message.reply_html(text, reply_markup=keyboard)
            return ConversationHandler.END
    finally:
        db.close()

    await update.message.reply_text(
        "Envie a fatura do Banco Inter em PDF para importar os lancamentos.\n"
        f"Limite de tamanho: {MAX_PDF_SIZE_MB}MB."
    )
    return FATURA_AWAIT_FILE


async def fatura_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db_plan = next(get_db())
    try:
        usuario_db = get_or_create_user(db_plan, update.effective_user.id, update.effective_user.full_name)
        ensure_user_plan_state(db_plan, usuario_db, commit=True)
        gate = plan_allows_feature(db_plan, usuario_db, "pdf_import")
        if not gate.allowed:
            text, keyboard = upgrade_prompt_for_feature("pdf_import")
            await update.message.reply_html(text, reply_markup=keyboard)
            return ConversationHandler.END
    finally:
        db_plan.close()

    document = update.message.document
    if not document or document.mime_type != "application/pdf":
        await update.message.reply_text("Envie um arquivo PDF valido.")
        return FATURA_AWAIT_FILE

    if document.file_size and document.file_size > MAX_PDF_SIZE_BYTES:
        await update.message.reply_text(
            "❌ Arquivo muito grande para importar aqui.\n"
            f"Tamanho maximo: {MAX_PDF_SIZE_MB}MB.\n"
            "Dica: se passar desse limite, exporte em partes (mesmo banco/cartao)."
        )
        return FATURA_AWAIT_FILE

    try:
        file_obj = await document.get_file()
        file_bytes = await file_obj.download_as_bytearray()
    except Exception:
        await update.message.reply_text(
            "❌ Nao consegui baixar esse PDF.\n"
            f"Tente enviar um arquivo menor que {MAX_PDF_SIZE_MB}MB."
        )
        return FATURA_AWAIT_FILE

    process_msg = await update.message.reply_text(
        "📄 PDF detectado! Estou processando a fatura.\n"
        "Se o arquivo for grande, pode demorar um pouco."
    )

    try:
        transacoes, ignoradas, origem_label, total_pdf = await asyncio.wait_for(
            _parse_fatura_pdf_with_gemini(bytes(file_bytes)),
            timeout=MAX_PDF_PARSE_SECONDS,
        )
    except asyncio.TimeoutError:
        await process_msg.edit_text(
            "⏱️ O processamento da fatura excedeu o tempo limite.\n"
            "Tente enviar novamente ou exportar em partes menores."
        )
        return FATURA_AWAIT_FILE
    except Exception as exc:
        logger.exception("Erro ao processar fatura PDF", exc_info=True)
        error_str = str(exc)
        
        if "password" in error_str.lower() or "senha" in error_str.lower() or "encrypted" in error_str.lower():
            await process_msg.edit_text(
                "🔒 Este PDF está protegido por senha.\n"
                "Remova a senha no app do banco e envie novamente."
            )
        else:
            # Mostrar o erro real para debug
            await process_msg.edit_text(
                f"❌ <b>Erro no Processamento</b>\n\n{error_str}",
                parse_mode="HTML"
            )
        return FATURA_AWAIT_FILE
    else:
        try:
            await process_msg.delete()
        except Exception:
            pass

    if not transacoes:
        await update.message.reply_text(
            "❌ Não consegui localizar as transações desta fatura.\n"
            "Verifique se o PDF é realmente uma fatura de cartão de crédito e tente novamente."
        )
        return ConversationHandler.END

    context.user_data["fatura_transacoes"] = transacoes
    context.user_data["fatura_ignoradas"] = ignoradas
    context.user_data["fatura_origem_label"] = origem_label
    context.user_data["fatura_valor_total_pdf"] = total_pdf

    db = next(get_db())
    try:
        # Modo Zero Setup: não depende mais de conta/cartão cadastrado.
        context.user_data["fatura_conta_id"] = 0

        total_pdf = context.user_data.get("fatura_valor_total_pdf")
        total_debito_extraido = sum(-float(t["valor"]) for t in transacoes if float(t["valor"]) < 0)
        ajuste_pdf = 0.0
        if isinstance(total_pdf, (int, float)):
            ajuste_pdf = round(float(total_pdf) - float(total_debito_extraido), 2)
            if abs(ajuste_pdf) >= 0.01:
                data_ajuste = max((t["data_transacao"] for t in transacoes), default=datetime.now())
                transacoes.append({
                    "data_transacao": data_ajuste,
                    "descricao": "AJUSTE FATURA (valor nao detalhado no PDF)",
                    "valor": -abs(ajuste_pdf),
                    "forma_pagamento": "Crédito",
                    "origem": "fatura_ajuste_pdf",
                })
                context.user_data["fatura_ajuste_pdf"] = abs(ajuste_pdf)
                context.user_data["fatura_transacoes"] = transacoes
        
        # Show summary directly with Confirm/Edit/Cancel buttons
        total = len(transacoes)
        total_debito = sum(-t["valor"] for t in transacoes if t["valor"] < 0)
        total_credito = sum(t["valor"] for t in transacoes if t["valor"] > 0)
        total_pdf = context.user_data.get("fatura_valor_total_pdf")
        ajuste_pdf_abs = context.user_data.get("fatura_ajuste_pdf")

        preview_lines = []
        for item in transacoes[:8]:
            data = item["data_transacao"].strftime("%d/%m")
            valor_label = _fmt_brl(item["valor"])
            desc = _compact_desc(item.get("descricao", ""))
            preview_lines.append(f"• {data} | {desc} | {valor_label}")

        top_debitos = sorted(
            [t for t in transacoes if float(t.get("valor", 0)) < 0],
            key=lambda t: abs(float(t.get("valor", 0))),
            reverse=True,
        )[:3]
        top_lines = []
        for item in top_debitos:
            top_lines.append(f"• {_compact_desc(item.get('descricao', ''), 34)} ({_fmt_brl(item['valor'])})")

        preview_text = "\n".join(preview_lines) if preview_lines else "• Sem itens para preview"
        maiores_text = "\n".join(top_lines) if top_lines else "• Sem debitos"
        origem_label = context.user_data.get("fatura_origem_label", "Inter")

        resumo_linhas = [
            f"🧾 <b>Resumo da Fatura ({origem_label})</b>",
            "",
            f"📌 <b>Transacoes detectadas:</b> <code>{total}</code>",
            f"↩️ <b>Ignoradas (pagamentos/estornos):</b> <code>{ignoradas}</code>",
            f"💸 <b>Total debitos:</b> <code>{_fmt_brl(total_debito)}</code>",
            f"💰 <b>Total creditos:</b> <code>{_fmt_brl(total_credito)}</code>",
        ]
        if isinstance(total_pdf, (int, float)):
            resumo_linhas.append(f"🧮 <b>Total no PDF:</b> <code>{_fmt_brl(total_pdf)}</code>")
        if isinstance(ajuste_pdf_abs, (int, float)) and ajuste_pdf_abs >= 0.01:
            resumo_linhas.append(f"⚖️ <b>Ajuste automatico aplicado:</b> <code>{_fmt_brl(ajuste_pdf_abs)}</code>")
        resumo_linhas.extend([
            "",
            "🔥 <b>Maiores gastos detectados</b>",
            maiores_text,
            "",
            "👀 <b>Preview de lancamentos</b>",
            preview_text,
            "",
            "━━━━━━━━━━━━━━━━━━",
            "✅ <b>Acao:</b> Importar lancamentos?",
            "Toque em <b>Editar</b> para revisar e corrigir antes de salvar.",
        ])
        resumo = "\n".join(resumo_linhas)

        keyboard = [
            [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="fatura_salvar")],
            [InlineKeyboardButton("✏️ Editar", callback_data="fatura_editar_inline")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="fatura_cancelar")],
        ]
        await update.message.reply_text(resumo, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return FATURA_CONFIRMATION_STATE
    finally:
        db.close()


async def fatura_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler para callbacks de confirmação de fatura.
    Trata: fatura_cancelar, fatura_editar_inline, fatura_salvar
    """
    query = update.callback_query
    
    # Responder ao callback imediatamente
    try:
        await query.answer()
    except Exception as e:
        logger.warning("Falha ao responder callback imediatamente: %s", e)

    # Processar ação
    try:
        action = query.data
        logger.info(f"fatura_confirm: action={action}, user={query.from_user.id}")
        
        if action == "fatura_cancelar":
            context.user_data.pop("fatura_transacoes", None)
            context.user_data.pop("fatura_conta_id", None)
            context.user_data.pop("fatura_ajuste_pdf", None)
            await query.edit_message_text("❌ Importacao cancelada.")
            return ConversationHandler.END

        if action == "fatura_editar_inline":
            logger.info("Processando fatura_editar_inline para user=%s", query.from_user.id)
            transacoes = context.user_data.get("fatura_transacoes", [])
            conta_id = context.user_data.get("fatura_conta_id")
            origem_label = context.user_data.get("fatura_origem_label", "Inter")

            if not transacoes:
                logger.warning("Dados de fatura expirados: transacoes=%s, conta_id=%s", bool(transacoes), conta_id)
                await query.edit_message_text("❌ Dados da fatura expiraram. Envie o PDF novamente.")
                return ConversationHandler.END

            conta_nome = "Sem conta"

            token = create_fatura_draft(
                telegram_user_id=query.from_user.id,
                conta_id=conta_id,
                conta_nome=conta_nome,
                transacoes=transacoes,
                origem_label=origem_label,
            )
            set_pending_editor_token(query.from_user.id, token)

            try:
                webapp_url = _get_fatura_webapp_url("fatura_editor", token)
                logger.info("URL do editor gerada: %s (truncado)", webapp_url[:80])
            except Exception as e:
                logger.error("Falha ao gerar webapp_url: %s", e, exc_info=True)
                raise

            # Evita problemas em alguns clientes ao tentar substituir o teclado inline por um botão web_app.
            await query.edit_message_text(
                "✅ Rascunho preparado. Vou te enviar o botao para abrir o editor no MiniApp.",
                parse_mode="HTML",
            )
            logger.info("Enviando botão de editor para user=%s", query.from_user.id)
            await query.message.reply_text(
                "📱 <b>Editar lancamentos da fatura</b>\n\n"
                "Toque no botao abaixo para abrir o editor.\n"
                "Se o Telegram nao abrir por esse botao, toque em <b>🚀 Abrir o App</b> no teclado que o editor abre automaticamente.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Abrir Editor da Fatura", web_app=WebAppInfo(url=webapp_url))],
                ]),
            )
            logger.info("Botão de editor enviado com sucesso")
            return FATURA_CONFIRMATION_STATE

        if action == "fatura_salvar":
            transacoes = context.user_data.get("fatura_transacoes", [])
            conta_id = context.user_data.get("fatura_conta_id", 0)
            if not transacoes:
                await query.edit_message_text("❌ Dados da fatura perdidos. Tente novamente.")
                return ConversationHandler.END

            db = next(get_db())
            try:
                conta_obj = db.query(Conta).filter(Conta.id == conta_id).first()
                conta_nome = conta_obj.nome if conta_obj else "Cartao de Credito"
                for item in transacoes:
                    item["forma_pagamento"] = "Crédito"

                usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
                tipo_origem = transacoes[0].get("origem", "fatura_pdf_generic") if transacoes else "fatura_pdf_generic"
                ok, msg, _stats = await salvar_transacoes_generica(
                    db, usuario_db, transacoes, conta_id, tipo_origem=tipo_origem
                )
                if ok:
                    try:
                        await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_PDF", context)
                    except Exception:
                        logger.debug("Falha ao conceder XP da fatura (nao critico).")
                    # Garante consistencia imediata no chat/miniapp apos importacao da fatura.
                    try:
                        limpar_cache_usuario(int(query.from_user.id))
                    except Exception:
                        logger.debug("Falha ao limpar cache do usuario apos importacao de fatura.")
                
                await query.edit_message_text(msg, parse_mode="HTML")
                return ConversationHandler.END
            finally:
                db.close()
                context.user_data.pop("fatura_transacoes", None)
                context.user_data.pop("fatura_conta_id", None)
                context.user_data.pop("fatura_ajuste_pdf", None)
                context.user_data.pop("fatura_origem_label", None)
                context.user_data.pop("fatura_pending_edit", None)

        # Ação desconhecida
        logger.warning(f"Acao desconhecida em fatura_confirm: {action}")
        await query.answer("Acao invalida", show_alert=True)
        return FATURA_CONFIRMATION_STATE
        
    except Exception as e:
        logger.error(f"ERRO NO FATURA_CONFIRM: action={query.data}, error={str(e)}", exc_info=True)
        try:
            await query.answer(f"❌ Erro: {str(e)[:50]}", show_alert=True)
        except Exception as e2:
            logger.error(f"Falha ao enviar erro ao user: {e2}")
        return FATURA_CONFIRMATION_STATE


async def fatura_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Importacao cancelada.")
    elif update.message:
        await update.message.reply_text("Importacao cancelada.")
    context.user_data.pop("fatura_transacoes", None)
    context.user_data.pop("fatura_conta_id", None)
    context.user_data.pop("fatura_origem_label", None)
    return ConversationHandler.END


fatura_conv = ConversationHandler(
    entry_points=[CommandHandler("fatura", fatura_start), MessageHandler(filters.Regex(r"^🧾 Fatura$"), fatura_start)],
    states={
        FATURA_AWAIT_FILE: [
            MessageHandler(filters.Document.MimeType("application/pdf"), fatura_receive_file)
        ],
        FATURA_CONFIRMATION_STATE: [
            CallbackQueryHandler(fatura_confirm, pattern="^fatura_")
        ],
    },
    fallbacks=[
        CommandHandler(["cancelar", "cancel", "sair", "parar"], fatura_cancel),
        MessageHandler(filters.Regex(r"(?i)^/?\s*(cancelar|cancel|sair|parar)$"), fatura_cancel),
    ],
    per_message=False,
    per_user=True,
    per_chat=True,
)
