import json
import logging
import os
import re
import asyncio
from datetime import datetime

import google.generativeai as genai
import requests
try:
    from google.api_core.exceptions import ResourceExhausted
except Exception:  # pragma: no cover - fallback em ambientes sem api_core
    ResourceExhausted = None
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

import config
from database.database import get_db, get_or_create_user
from models import Categoria, Conta, Lancamento, Subcategoria
from .gamification_utils import give_xp_for_action, touch_user_interaction
from .menu_botoes import (
    BOTAO_AGENDAMENTOS,
    BOTAO_CANCELAR,
    BOTAO_CONFIG,
    BOTAO_CONTATO,
    BOTAO_EDITAR,
    BOTAO_FATURA,
    BOTAO_GERENTE,
    BOTAO_GRAFICOS,
    BOTAO_LANCAMENTO,
    BOTAO_METAS,
    BOTAO_NIVEL,
    BOTAO_RANKING,
)

logger = logging.getLogger(__name__)

_BOTOES_MENU = {
    BOTAO_LANCAMENTO,
    BOTAO_GERENTE,
    BOTAO_EDITAR,
    BOTAO_CONFIG,
    BOTAO_FATURA,
    BOTAO_GRAFICOS,
    BOTAO_AGENDAMENTOS,
    BOTAO_METAS,
    BOTAO_RANKING,
    BOTAO_NIVEL,
    BOTAO_CANCELAR,
    BOTAO_CONTATO,
}


def _get_webapp_url(tab: str | None = None) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:5000").rstrip("/")
    url = f"{base_url}/webapp"
    if tab:
        url = f"{url}?tab={tab}"
    return url


def _normalize_tipo(tipo: str) -> str:
    return "Entrada" if str(tipo).strip().lower() == "entrada" else "Saída"


def _should_ignore_text(text: str) -> bool:
    if not text:
        return True
    if text.startswith("/"):
        return True
    if text in _BOTOES_MENU:
        return True
    return False


def _parse_json_response(text: str) -> dict | None:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _quick_payload_valido(dados: dict) -> bool:
    if not isinstance(dados, dict):
        return False
    descricao = str(dados.get("descricao", "") or dados.get("nome_estabelecimento", "")).strip()
    try:
        valor = float(str(dados.get("valor", "0")).replace(",", "."))
    except (ValueError, TypeError):
        valor = 0
    if valor <= 0 and not descricao:
        return False
    return True


def _is_quota_error(err: Exception) -> bool:
    if ResourceExhausted and isinstance(err, ResourceExhausted):
        return True
    msg = str(err).lower()
    return "quota" in msg or "resource_exhausted" in msg or "429" in msg


def _build_categoria_contexto(db: Session) -> str:
    categorias = db.query(Categoria).options().all()
    linhas = []
    for cat in categorias:
        subcats = [sub.nome for sub in cat.subcategorias]
        linhas.append(f"- {cat.nome}: ({', '.join(subcats)})")
    return "\n".join(linhas)


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
        logger.error("Falha ao processar frase com Groq: %s", exc, exc_info=True)
        return None


def _resolve_categoria_ids(db: Session, dados: dict) -> tuple[int | None, int | None]:
    id_categoria = None
    id_subcategoria = None

    cat_sugerida = dados.get("categoria_sugerida")
    sub_sugerida = dados.get("subcategoria_sugerida")

    if cat_sugerida:
        categoria_obj = db.query(Categoria).filter(func.lower(Categoria.nome) == func.lower(cat_sugerida)).first()
        if categoria_obj:
            id_categoria = categoria_obj.id

    if sub_sugerida and id_categoria:
        subcategoria_obj = db.query(Subcategoria).filter(
            and_(Subcategoria.id_categoria == id_categoria, func.lower(Subcategoria.nome) == func.lower(sub_sugerida))
        ).first()
        if subcategoria_obj:
            id_subcategoria = subcategoria_obj.id

    return id_categoria, id_subcategoria


def _format_categoria_str(dados: dict) -> str:
    categoria = dados.get("categoria_sugerida") or "N/A"
    subcategoria = dados.get("subcategoria_sugerida") or "N/A"
    if subcategoria and subcategoria != "N/A":
        return f"{categoria} / {subcategoria}"
    return categoria


def _format_quick_card(dados: dict) -> str:
    descricao = dados.get("descricao") or dados.get("nome_estabelecimento") or "Lançamento"
    try:
        valor = float(str(dados.get("valor", "0")).replace(",", "."))
    except (ValueError, TypeError):
        valor = 0.0
    tipo = _normalize_tipo(dados.get("tipo_transacao", "Saída"))
    data_str = dados.get("data") or datetime.now().strftime("%d/%m/%Y")
    forma_pagamento = dados.get("forma_pagamento") or "Nao informado"
    conta_nome = dados.get("forma_pagamento_conta") or "Conta nao definida"
    categoria_str = _format_categoria_str(dados)

    tipo_emoji = "🟢" if tipo == "Entrada" else "🔴"
    return (
        "🧾 <b>Resumo do Lançamento</b>\n\n"
        f"📌 <b>Descrição:</b> {descricao}\n"
        f"{tipo_emoji} <b>Valor:</b> <code>R$ {valor:.2f}</code> ({tipo})\n"
        f"📅 <b>Data:</b> {data_str}\n"
        f"💳 <b>Pagamento:</b> {forma_pagamento}\n"
        f"🏦 <b>Conta:</b> {conta_nome}\n"
        f"🏷️ <b>Categoria:</b> {categoria_str}\n\n"
        "Confirma o salvamento?"
    )


async def _ask_for_conta(update_or_query, context: ContextTypes.DEFAULT_TYPE, contas: list[Conta]) -> None:
    botoes = []
    for conta in contas:
        emoji = "🏦" if conta.tipo == "Conta" else "💳"
        botoes.append(InlineKeyboardButton(f"{emoji} {conta.nome}", callback_data=f"quick_conta_{conta.id}"))
    teclado = InlineKeyboardMarkup([botoes[i:i + 2] for i in range(0, len(botoes), 2)])
    texto = "🏦 <b>Escolha a conta/cartao</b>\n\nSelecione de onde saiu/entrou o dinheiro."

    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)
    else:
        await update_or_query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def _send_quick_summary(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    dados = context.user_data.get("quick_lancamento")
    if not dados:
        return

    card_text = _format_quick_card(dados)
    webapp_url = _get_webapp_url("editar")
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="quick_confirm")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
        [InlineKeyboardButton("✍️ Editar no Miniapp", web_app=WebAppInfo(url=webapp_url))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(card_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text(card_text, parse_mode="HTML", reply_markup=reply_markup)


async def handle_quick_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if _should_ignore_text(text):
        return

    await touch_user_interaction(update.effective_user.id, context)

    if not config.GEMINI_API_KEY and not config.GROQ_API_KEY:
        await update.message.reply_text("❌ Nenhuma IA configurada (Gemini/Groq).")
        return

    status = await update.message.reply_text("🤖 Entendi. Estou montando seu lançamento...")

    db: Session = next(get_db())
    try:
        categorias_contexto = _build_categoria_contexto(db)
    finally:
        db.close()

    hoje_str = datetime.now().strftime("%d/%m/%Y")
    prompt = f"""
Voce e um assistente financeiro. O usuario enviou uma frase descrevendo um lancamento financeiro.
Retorne EXCLUSIVAMENTE um JSON valido, sem markdown, seguindo o schema abaixo.

Data de hoje: {hoje_str}

Campos obrigatorios:
{{
  "descricao": "string",
  "valor": float,
    "tipo_transacao": "Entrada" ou "Saída",
  "data": "DD/MM/AAAA",
  "forma_pagamento": "Pix, Debito, Credito, Dinheiro ou N/A",
  "categoria_sugerida": "string (usar lista)",
  "subcategoria_sugerida": "string (usar lista)"
}}

Categorias disponiveis:
{categorias_contexto}

Frase do usuario:
"{text}"
"""

    response_text = None
    try:
        if config.GEMINI_API_KEY:
            raw_key = config.GEMINI_API_KEY
            genai.configure(api_key=raw_key.strip().strip("'\"").strip())
            model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
            response = model.generate_content(prompt)
            response_text = response.text if response else None
    except Exception as e:
        logger.error("Falha ao processar frase com Gemini: %s", e, exc_info=True)
        if _is_quota_error(e) or config.GROQ_API_KEY:
            response_text = await _generate_with_groq(prompt)
        if not response_text:
            if _is_quota_error(e):
                await status.edit_text(
                    "⚠️ Limite diario da IA atingido. Tente novamente em alguns minutos ou use /lancamento."
                )
            else:
                await status.edit_text("❌ Nao consegui interpretar sua frase. Tente novamente.")
            return

    if not response_text:
        response_text = await _generate_with_groq(prompt)
        if not response_text:
            await status.edit_text("❌ Nao consegui interpretar sua frase. Tente novamente.")
            return

    dados_ia = _parse_json_response(response_text)
    if not dados_ia or not _quick_payload_valido(dados_ia):
        await status.edit_text("❌ Nao consegui entender. Tente algo como: 'Gastei 34,90 no iFood ontem'.")
        return

    context.user_data["quick_lancamento"] = dados_ia

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        contas = db.query(Conta).filter(Conta.id_usuario == usuario_db.id).all()
    finally:
        db.close()

    if not contas:
        await status.edit_text("❌ Nenhuma conta cadastrada. Use /configurar para adicionar.")
        context.user_data.pop("quick_lancamento", None)
        return

    if len(contas) == 1:
        dados_ia["id_conta"] = contas[0].id
        dados_ia["forma_pagamento_conta"] = contas[0].nome
        context.user_data["quick_lancamento"] = dados_ia
        await status.delete()
        await _send_quick_summary(update, context)
        return

    await status.delete()
    await _ask_for_conta(update, context, contas)


async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    action = query.data
    dados = context.user_data.get("quick_lancamento")

    if not dados and not action.startswith("quick_conta_"):
        await query.answer("Dados da sessao expiraram.", show_alert=True)
        return

    if action.startswith("quick_conta_"):
        conta_id = int(action.split("_")[-1])
        db = next(get_db())
        try:
            conta = db.query(Conta).filter(Conta.id == conta_id).first()
            if not conta:
                await query.answer("Conta invalida.", show_alert=True)
                return
            dados["id_conta"] = conta.id
            dados["forma_pagamento_conta"] = conta.nome
            context.user_data["quick_lancamento"] = dados
        finally:
            db.close()
        await _send_quick_summary(query, context)
        return

    if action == "quick_cancel":
        context.user_data.pop("quick_lancamento", None)
        await query.edit_message_text("❌ Lançamento cancelado.")
        return

    if action == "quick_confirm":
        await query.edit_message_text("💾 Salvando lançamento...")
        db = next(get_db())
        try:
            usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)

            data_str = dados.get("data") or datetime.now().strftime("%d/%m/%Y")
            try:
                data_obj = datetime.strptime(data_str, "%d/%m/%Y")
            except ValueError:
                data_obj = datetime.now()

            try:
                valor_float = float(str(dados.get("valor", "0")).replace(",", "."))
            except (ValueError, TypeError):
                valor_float = 0.0

            id_categoria, id_subcategoria = _resolve_categoria_ids(db, dados)
            novo_lancamento = Lancamento(
                id_usuario=usuario_db.id,
                descricao=dados.get("descricao") or dados.get("nome_estabelecimento") or "Lançamento",
                valor=valor_float,
                tipo=_normalize_tipo(dados.get("tipo_transacao", "Saída")),
                data_transacao=data_obj,
                forma_pagamento=dados.get("forma_pagamento_conta") or dados.get("forma_pagamento"),
                id_conta=dados.get("id_conta"),
                id_categoria=id_categoria,
                id_subcategoria=id_subcategoria,
            )
            db.add(novo_lancamento)
            db.commit()
            try:
                await give_xp_for_action(query.from_user.id, "LANCAMENTO_MANUAL", context)
            except Exception:
                logger.debug("Falha ao conceder XP do lancamento rapido (nao critico).")
            await query.edit_message_text("✅ Lançamento salvo com sucesso!")
        except Exception as e:
            db.rollback()
            logger.error("Erro ao salvar lancamento rapido: %s", e, exc_info=True)
            await query.edit_message_text("❌ Erro ao salvar. Tente novamente.")
        finally:
            db.close()
            context.user_data.pop("quick_lancamento", None)
        return
