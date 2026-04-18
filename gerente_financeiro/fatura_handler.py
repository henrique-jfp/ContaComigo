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

    api_key_debug = config.GEMINI_API_KEY or ""
    masked_key = f"{api_key_debug[:4]}...{api_key_debug[-4:]}" if len(api_key_debug) > 8 else "NAO_CONFIGURADA"
    logger.info(f"🔑 [DEBUG] Chave API Ativa: {masked_key} | Modelo: {config.GEMINI_MODEL_NAME}")

    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
    except Exception as e:
        logger.warning(f"Erro ao re-configurar genai no fatura_handler: {e}")

    ano_atual = datetime.now().year
    mes_atual = datetime.now().month
    current_model = getattr(config, "GEMINI_MODEL_NAME", "gemini-2.5-flash")
    model_candidates = []
    for candidate in [
        current_model,
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ]:
        if candidate and candidate not in model_candidates:
            model_candidates.append(candidate)

    logger.info("Pipeline de fatura: Gemini multimodal direto -> UniversalInvoiceExtractor")

    prompt = f"""
    Você é um extrator universal de faturas de cartão de crédito.
    Leia o PDF de QUALQUER banco/cartão e retorne SOMENTE JSON válido.

    DATA DE REFERÊNCIA: {datetime.now().strftime('%d/%m/%Y')}
    MÊS DE REFERÊNCIA PRINCIPAL: {mes_atual:02d}/{ano_atual}

    REGRAS:
    1. Extraia compras, estornos e créditos reais da fatura aberta.
    2. Ignore totais, saldo anterior, limite, pagamento efetuado, pagamento recebido, encargos, juros, IOF e blocos de resumo.
    3. Para compras, use valor NEGATIVO. Para estornos/créditos, use valor POSITIVO.
    4. Se a data vier como DD/MM, complete com o ano {ano_atual}.
    5. Se houver parcelamento como 02/10, retorne isso em "parcela".
    6. A descrição deve ser o estabelecimento real, nunca o nome do banco.
    7. Se tiver dúvida entre manter ou remover uma linha, só mantenha se houver data + valor + estabelecimento plausível.

    JSON OBRIGATÓRIO:
    {{
        "banco": "Nome do Banco",
        "total_fatura": 0.0,
        "transacoes": [
            {{
                "data": "{ano_atual}-{mes_atual:02d}-01",
                "descricao": "ESTABELECIMENTO",
                "valor": -123.45,
                "parcela": null
            }}
        ],
        "ignoradas": 0
    }}
    """

    def _parse_json_response(text: str) -> dict | None:
        if not text:
            return None
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return None
        raw_json = re.sub(r',\s*([\]\}])', r'\1', match.group(0))
        try:
            return json.loads(raw_json)
        except Exception:
            return None

    def _parse_data_fatura(raw_data: str) -> datetime | None:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d/%m"):
            try:
                dt = datetime.strptime(str(raw_data), fmt)
                if fmt == "%d/%m":
                    dt = dt.replace(year=ano_atual)
                elif dt.year < 100:
                    dt = dt.replace(year=2000 + dt.year)
                return dt
            except Exception:
                continue
        return None

    def _normalizar_resultado_bruto(data: dict, origem_prefixo: str) -> Tuple[List[Dict], int, str, float]:
        transacoes_finais: List[Dict] = []
        ignoradas_count = int(data.get("ignoradas", 0) or 0)
        banco = str(data.get("banco", "Desconhecido") or "Desconhecido")
        total_pdf = float(data.get("total_fatura", 0.0) or 0.0)
        blacklist = [
            "total",
            "pagamento efetuado",
            "saldo anterior",
            "limite",
            "demonstrativo",
            "fatura anterior",
            "saldo a pagar",
            "pagamento recebido",
            "crédito de pagamento",
            "credito de pagamento",
            "saldo do período",
            "saldo do periodo",
            "valor do pagamento",
            "pagamento por debito",
        ]

        for item in data.get("transacoes", []):
            try:
                descricao = str(item.get("descricao", "") or "").strip()
                if not descricao:
                    ignoradas_count += 1
                    continue
                if any(term in descricao.lower() for term in blacklist):
                    ignoradas_count += 1
                    continue

                valor = float(item.get("valor", 0.0) or 0.0)
                if abs(valor) < 0.009:
                    ignoradas_count += 1
                    continue

                dt_obj = _parse_data_fatura(item.get("data"))
                if not dt_obj:
                    ignoradas_count += 1
                    continue

                parcela = item.get("parcela")
                transacoes_finais.append({
                    "descricao": descricao,
                    "valor": valor,
                    "data_transacao": dt_obj,
                    "forma_pagamento": "Crédito",
                    "origem": f"{origem_prefixo}_{banco.lower().replace(' ', '_')}",
                    "parcela": parcela,
                })
            except Exception as item_exc:
                logger.warning("Erro ao normalizar item bruto da fatura: %s | item=%s", item_exc, item)
                ignoradas_count += 1

        deduped: List[Dict] = []
        seen: set[tuple[str, str, float, str]] = set()
        for item in transacoes_finais:
            key = (
                item["data_transacao"].strftime("%Y-%m-%d"),
                str(item["descricao"]).strip().lower(),
                round(float(item["valor"]), 2),
                str(item.get("parcela") or ""),
            )
            if key in seen:
                ignoradas_count += 1
                continue
            seen.add(key)
            deduped.append(item)

        return deduped, ignoradas_count, banco, total_pdf

    def _resultado_parece_valido(transacoes: List[Dict], total_pdf: float) -> bool:
        if not transacoes:
            return False
        if len(transacoes) > 300:
            logger.warning("Resultado rejeitado por excesso de transações: %s", len(transacoes))
            return False

        total_debito = sum(abs(float(t["valor"])) for t in transacoes if float(t["valor"]) < 0)
        if total_pdf > 0 and total_debito > total_pdf * 1.7:
            logger.warning(
                "Resultado rejeitado: débitos extraídos muito acima do total do PDF (extraído=%s, pdf=%s)",
                total_debito,
                total_pdf,
            )
            return False
        return True

    pdf_part = {"mime_type": "application/pdf", "data": file_bytes}

    for model_name in model_candidates:
        try:
            logger.info("🤖 Tentando extração multimodal direta com %s", model_name)
            response = await genai.GenerativeModel(model_name).generate_content_async(
                [prompt, pdf_part],
                generation_config={"response_mime_type": "application/json"},
            )
            json_data = _parse_json_response(getattr(response, "text", "") or "")
            if not json_data:
                logger.warning("Resposta do Gemini sem JSON utilizável com %s", model_name)
                continue
            transacoes, ignoradas, banco, total_pdf = _normalizar_resultado_bruto(json_data, "fatura_pdf")
            if _resultado_parece_valido(transacoes, total_pdf):
                logger.info("✅ Extração multimodal direta funcionou com %s (%s transações)", model_name, len(transacoes))
                return transacoes, ignoradas, banco, total_pdf
            logger.warning("Resultado do Gemini com %s foi descartado por baixa confiabilidade estrutural.", model_name)
        except Exception as exc:
            logger.warning("Falha na extração multimodal direta com %s: %s", model_name, exc)

    from .invoice_processor import UniversalInvoiceExtractor

    extractor = UniversalInvoiceExtractor()
    logger.info("🧩 Fallback para parser local do UniversalInvoiceExtractor")
    texto_pdf = extractor._extract_pdf_text(file_bytes)
    regex_invoice = extractor._build_regex_invoice_schema(texto_pdf)
    if not regex_invoice or not regex_invoice.itens:
        raise RuntimeError("Não foi possível extrair transações desta fatura. O PDF foi lido, mas nenhum lançamento confiável foi encontrado.")

    total_pdf = float(regex_invoice.valor_total or 0.0)
    transacoes_finais: List[Dict] = []
    ignoradas_count = 0
    for item in regex_invoice.itens:
        try:
            dt_obj = datetime.strptime(item.data or regex_invoice.data, "%Y-%m-%d")
            transacoes_finais.append({
                "descricao": str(item.descricao).strip(),
                "valor": float(item.valor),
                "data_transacao": dt_obj,
                "forma_pagamento": "Crédito",
                "origem": "fatura_regex",
                "parcela": item.parcela
            })
        except Exception as e:
            logger.warning("Erro ao processar item do parser local da fatura: %s", e)
            ignoradas_count += 1

    if not _resultado_parece_valido(transacoes_finais, total_pdf):
        raise RuntimeError("A fatura foi lida, mas os dados extraídos ficaram incoerentes com o total do PDF.")

    return transacoes_finais, ignoradas_count, regex_invoice.estabelecimento, total_pdf

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
        "Envie sua fatura de cartão de crédito em PDF para importar os lançamentos.\n"
        "O sistema agora extrai datas individuais e parcelamentos com alta precisão."
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
        "📄 PDF detectado! Extraindo lançamentos com IA visual...\n"
        "Isso pode levar alguns segundos."
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
            await process_msg.edit_text(
                f"❌ <b>Erro no Processamento IA</b>\n\nOcorreu uma falha ao analisar o PDF. Verifique se o arquivo está legível.",
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
            "❌ Não identifiquei transações válidas nesta fatura.\n"
            "Verifique se o arquivo contém compras detalhadas e tente novamente."
        )
        return ConversationHandler.END

    context.user_data["fatura_transacoes"] = transacoes
    context.user_data["fatura_ignoradas"] = ignoradas
    context.user_data["fatura_origem_label"] = origem_label
    context.user_data["fatura_valor_total_pdf"] = total_pdf

    db = next(get_db())
    try:
        context.user_data["fatura_conta_id"] = 0

        total_pdf = context.user_data.get("fatura_valor_total_pdf")
        # Soma algébrica (despesas são negativas, créditos positivos)
        saldo_extraido = sum(float(t["valor"]) for t in transacoes)
        
        ajuste_pdf = 0.0
        # Ajuste automático apenas se a diferença for pequena (possíveis centavos de arredondamento)
        # Se a diferença for grande, é melhor NÃO ajustar para não poluir com valores mágicos.
        if isinstance(total_pdf, (int, float)):
            diferenca = round(float(total_pdf) + float(saldo_extraido), 2) # saldo_extraido já é negativo para despesas
            if 0.01 <= abs(diferenca) < 5.00:
                data_ajuste = max((t["data_transacao"] for t in transacoes), default=datetime.now())
                transacoes.append({
                    "data_transacao": data_ajuste,
                    "descricao": "Ajuste de centavos (Fatura)",
                    "valor": -diferenca,
                    "forma_pagamento": "Crédito",
                    "origem": "fatura_ajuste_pdf",
                })
                context.user_data["fatura_ajuste_pdf"] = abs(diferenca)
                context.user_data["fatura_transacoes"] = transacoes
        
        total = len(transacoes)
        total_debito = sum(-t["valor"] for t in transacoes if t["valor"] < 0)
        total_credito = sum(t["valor"] for t in transacoes if t["valor"] > 0)
        ajuste_pdf_abs = context.user_data.get("fatura_ajuste_pdf")

        preview_lines = []
        # Sort transactions by date for the preview
        sorted_transacoes = sorted(transacoes, key=lambda x: x["data_transacao"])
        for item in sorted_transacoes[:10]:
            data = item["data_transacao"].strftime("%d/%m")
            valor_label = _fmt_brl(item["valor"])
            parcela = f" ({item['parcela']})" if item.get('parcela') else ""
            desc = _compact_desc(f"{item.get('descricao', '')}{parcela}")
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
        origem_label = context.user_data.get("fatura_origem_label", "Desconhecido")

        resumo_linhas = [
            f"🧾 <b>Resumo da Fatura ({origem_label})</b>",
            "",
            f"📌 <b>Transações detectadas:</b> <code>{total}</code>",
            f"↩️ <b>Itens ignorados:</b> <code>{ignoradas}</code>",
            f"💸 <b>Total débitos:</b> <code>{_fmt_brl(total_debito)}</code>",
            f"💰 <b>Total créditos:</b> <code>{_fmt_brl(total_credito)}</code>",
        ]
        if isinstance(total_pdf, (int, float)):
            resumo_linhas.append(f"🧮 <b>Total no PDF:</b> <code>{_fmt_brl(total_pdf)}</code>")
        if isinstance(ajuste_pdf_abs, (int, float)) and ajuste_pdf_abs >= 0.01:
            resumo_linhas.append(f"⚖️ <b>Ajuste aplicado:</b> <code>{_fmt_brl(ajuste_pdf_abs)}</code>")
        
        resumo_linhas.extend([
            "",
            "🔥 <b>Maiores gastos</b>",
            maiores_text,
            "",
            "👀 <b>Preview de lançamentos</b>",
            preview_text,
            "",
            "━━━━━━━━━━━━━━━━━━",
            "✅ <b>Ação:</b> Importar lançamentos?",
            "Toque em <b>Editar</b> para revisar antes de salvar.",
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
                logger.error(f"❌ Transações não encontradas no user_data para o usuário {query.from_user.id}. Dados perdidos.")
                await query.edit_message_text(
                    "❌ <b>Dados da fatura perdidos.</b>\n\n"
                    "Infelizmente o sistema reiniciou ou a sessão expirou. Por favor, envie o PDF novamente para processar.",
                    parse_mode="HTML"
                )
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
