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
    
    prompt = """
    Você é um extrator de dados de faturas de cartão de crédito especialista e infalível.
    Analise o documento PDF anexo e extraia as transações com precisão máxima.
    
    REGRAS CRÍTICAS:
    1. Identifique o nome do Banco ou Instituição emissora (ex: Nubank, Itaú, Bradesco, Inter, Santander, C6, etc).
    2. Identifique o "Valor Total" ou "Total da Fatura" atual.
    3. Extraia TODOS os lançamentos da fatura do mês atual.
    4. O valor deve ser NEGATIVO para compras/despesas e POSITIVO para estornos ou pagamentos.
    5. IGNORE pagamentos da fatura anterior (mas conte quantos itens foram ignorados na chave 'ignoradas').
    6. Se a descrição indicar um parcelamento (ex: "Compra 01/12", "Lojas X 2/5"), extraia apenas essa fração para a chave "parcela". Ex: "1/12". Caso contrário, deixe null.
    7. Retorne EXCLUSIVAMENTE um objeto JSON válido, sem nenhum texto extra (sem markdown ```json).
    
    FORMATO JSON OBRIGATÓRIO:
    {
        "banco": "Nome do Banco",
        "total_fatura": 1234.56,
        "transacoes": [
            {
                "data": "YYYY-MM-DD",
                "descricao": "NOME DO ESTABELECIMENTO",
                "valor": -150.50,
                "parcela": "1/12"
            }
        ],
        "ignoradas": 2
    }
    """
    
    pdf_part = {
        "mime_type": "application/pdf",
        "data": file_bytes
    }
    
    try:
        response = await model.generate_content_async([prompt, pdf_part])
        if not response or not hasattr(response, 'text'):
            raise ValueError("O Google Gemini não conseguiu gerar uma resposta.")
        text = response.text
    except Exception as gemini_exc:
        # 🚨 FORÇAR FAILOVER PARA QUALQUER ERRO
        logger.warning(f"⚠️ Gemini falhou ({type(gemini_exc).__name__}). Iniciando FAILOVER imediato para GROQ...")
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            texto_pdf = ""
            for page in doc:
                texto_pdf += page.get_text()
            doc.close()
            
            # Se não extraiu texto (PDF de imagem), tenta OCR
            if not texto_pdf or len(texto_pdf.strip()) < 20:
                logger.info("📸 PDF parece ser imagem. Tentando OCR do Google Vision como Plano C...")
                from .ocr_handler import ocr_fallback_gemini 
                texto_pdf = await ocr_fallback_gemini(file_bytes)

            # Truncar o texto para evitar erro 413 (Payload Too Large) no Groq
            texto_pdf_limitado = texto_pdf[:15000] if len(texto_pdf) > 15000 else texto_pdf

            logger.info(f"📄 Texto obtido ({len(texto_pdf)} chars, limitado para {len(texto_pdf_limitado)}). Enviando para Groq...")

            from .ai_service import _groq_chat_completion_async
            messages = [
                {"role": "system", "content": "Você é um extrator de faturas. Extraia os dados do texto e retorne APENAS um JSON válido."},
                {"role": "user", "content": f"{prompt}\n\nTEXTO DA FATURA (RESUMO):\n{texto_pdf_limitado}"}
            ]
            groq_resp = await _groq_chat_completion_async(messages)
            
            if isinstance(groq_resp, dict) and "choices" in groq_resp:
                text = groq_resp["choices"][0]["message"]["content"]
                logger.info("✅ Sucesso no Failover via Groq!")
            else:
                raise ValueError(f"Resposta inesperada do Groq: {groq_resp}")
        except Exception as failover_exc:
            logger.error(f"❌ Failover total falhou: {failover_exc}")
            raise RuntimeError(f"IA indisponível no momento. Gemini: {gemini_exc} | Failover: {failover_exc}")

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("A IA não retornou um JSON válido.")
        
    data = json.loads(match.group(0))
    
    transacoes_finais = []
    for t in data.get("transacoes", []):
        try:
            dt_obj = datetime.strptime(t["data"], "%Y-%m-%d")
            transacoes_finais.append({
                "descricao": str(t.get("descricao", "Sem descrição")),
                "valor": float(t.get("valor", 0.0)),
                "data_transacao": dt_obj,
                "forma_pagamento": "Crédito",
                "origem": f"fatura_pdf_{str(data.get('banco', 'generico')).lower().replace(' ', '_')}",
                "parcela": t.get("parcela")
            })
        except Exception as e:
            logger.warning(f"Erro ao converter data da transação da fatura: {t} - {e}")
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
