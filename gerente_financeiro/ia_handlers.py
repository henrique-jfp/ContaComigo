"""
🤖 Handlers para Análises Inteligentes com IA
==============================================

Comandos do bot que usam IA para análises avançadas de gastos.

Autor: Henrique Freitas
Data: 17/11/2025
"""

import logging
import json
import asyncio
import re
import os
from html import escape
from urllib.parse import quote
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler
from sqlalchemy import and_, extract, func
from database.database import get_db, get_or_create_user
from models import Lancamento, Usuario, Categoria, Agendamento, Objetivo
import config

try:
    from .analises_ia import get_analisador
except ModuleNotFoundError:
    def get_analisador():
        raise RuntimeError("Modulo opcional analises_ia indisponivel neste ambiente")

logger = logging.getLogger(__name__)

_FORMAS_PAGAMENTO_VALIDAS = {"Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"}


def _normalizar_forma_pagamento(valor: str | None) -> str:
    raw = str(valor or "").strip().lower()
    mapa = {
        "pix": "Pix",
        "credito": "Crédito",
        "crédito": "Crédito",
        "debito": "Débito",
        "débito": "Débito",
        "boleto": "Boleto",
        "dinheiro": "Dinheiro",
        "nao_informado": "Nao_informado",
        "não informado": "Nao_informado",
        "nao informado": "Nao_informado",
        "n/a": "Nao_informado",
        "": "Nao_informado",
    }
    return mapa.get(raw, "Nao_informado")


def _get_webapp_url(tab: str | None = None, draft: dict | None = None) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:5000").rstrip("/")
    url = f"{base_url}/webapp"
    params: list[str] = []
    if tab:
        params.append(f"tab={quote(tab, safe='')}")
    if draft:
        params.append(f"draft={quote(json.dumps(draft, ensure_ascii=False), safe='')}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


def _inferir_tipo_lancamento(texto_usuario: str, categoria: str, tipo_ia: str | None = None) -> str:
    tipo_raw = str(tipo_ia or "").strip().lower()
    if tipo_raw in {"entrada", "receita"}:
        return "Entrada"
    if tipo_raw in {"saida", "saída", "despesa"}:
        return "Saída"

    texto = f"{texto_usuario} {categoria}".lower()
    sinais_entrada = ["receita", "entrada", "recebi", "ganhei", "salario", "salário", "venda", "reembolso"]
    sinais_saida = ["despesa", "saida", "saída", "gastei", "paguei", "compra", "debito", "débito"]

    tem_entrada = any(s in texto for s in sinais_entrada)
    tem_saida = any(s in texto for s in sinais_saida)

    if tem_entrada and not tem_saida:
        return "Entrada"
    if tem_saida and not tem_entrada:
        return "Saída"
    return "Saída"


def _normalizar_data_lancamento(valor_data: str | None) -> str:
    raw = str(valor_data or "").strip()
    if not raw:
        return datetime.now().strftime("%d/%m/%Y")
    if raw.lower() == "hoje":
        return datetime.now().strftime("%d/%m/%Y")

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
        return raw

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return datetime.now().strftime("%d/%m/%Y")

    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except ValueError:
        return datetime.now().strftime("%d/%m/%Y")


_ALFREDO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "registrar_lancamento",
            "description": "Registra um lançamento financeiro de entrada ou saída.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor": {"type": "number"},
                    "categoria": {"type": "string"},
                    "forma_pagamento": {
                        "type": "string",
                        "enum": ["Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"],
                    },
                },
                "required": ["descricao", "valor", "categoria", "forma_pagamento"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_despesa",
            "description": "Prepara um agendamento de despesa recorrente com validação explícita de valor, data de início e frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "Descricao curta do compromisso financeiro. Ex.: 'Bike', 'Academia', 'Internet'.",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da parcela/evento. Extraia o numero exato citado pelo usuario (32 significa 32, nunca 12).",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro evento em YYYY-MM-DD. Converta datas brasileiras (DD/MM/AAAA) para YYYY-MM-DD.",
                    },
                    "frequencia": {
                        "type": "string",
                        "description": "Frequencia do agendamento: unico, semanal ou mensal. Se nao informado, usar mensal.",
                    },
                    "parcelas": {
                        "type": "number",
                        "description": "Quantidade de meses ou vezes (numero inteiro esperado). Se nao informado, assuma nulo/infinito.",
                    },
                },
                "required": ["descricao", "valor", "data", "frequencia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_receita",
            "description": "Prepara um agendamento de receita recorrente com validação explícita de valor, data de início e frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "Descricao curta da receita. Ex.: 'Salário', 'Freela fixo', 'Aluguel recebido'.",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da receita recorrente.",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro recebimento em YYYY-MM-DD.",
                    },
                    "frequencia": {
                        "type": "string",
                        "description": "Frequencia do agendamento: unico, semanal ou mensal. Se nao informado, usar mensal.",
                    },
                    "parcelas": {
                        "type": "number",
                        "description": "Quantidade de meses ou vezes (inteiro). Se nao informado, assuma nulo/infinito.",
                    },
                },
                "required": ["descricao", "valor", "data", "frequencia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_meta",
            "description": "Cria uma meta financeira para o usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor_alvo": {"type": "number"},
                },
                "required": ["descricao", "valor_alvo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "responder_duvida_financeira",
            "description": "Responde dúvidas financeiras gerais e sobre os dados do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pergunta": {"type": "string"},
                },
                "required": ["pergunta"],
            },
        },
    },
]


def _clear_pending_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Limpa estados pendentes de fluxos antigos para evitar conflito de botões/menu.
    keys = [
        "novo_lancamento",
        "dados_audio",
        "dados_ocr",
        "fatura_transacoes",
        "fatura_conta_id",
        "fatura_origem_label",
        "fatura_training_bytes",
        "fatura_training_name",
        "fatura_training_size",
        "fatura_training_pages",
        "fatura_training_text",
        "dados_quick",
    ]
    for key in keys:
        context.user_data.pop(key, None)


def _groq_chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    payload = {
        "model": config.GROQ_MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        logger.error("Groq HTTP %s: %s", response.status_code, response.text[:2000])
    response.raise_for_status()
    return response.json()


async def _groq_chat_completion_async(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _groq_chat_completion, messages, tools, tool_choice)


def _groq_transcribe_voice(voice_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    files = {
        "file": ("voice.ogg", voice_bytes, mime_type),
    }
    data = {
        "model": "whisper-large-v3-turbo",
        "response_format": "json",
        "language": "pt",
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        files=files,
        data=data,
        timeout=60,
    )
    response.raise_for_status()
    return (response.json() or {}).get("text", "").strip()


async def _groq_transcribe_voice_async(voice_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _groq_transcribe_voice, voice_bytes, mime_type)


def _resolve_categoria_id(db, categoria_nome: str) -> int | None:
    if not categoria_nome:
        return None
    categoria = db.query(Categoria).filter(Categoria.nome.ilike(categoria_nome.strip())).first()
    return categoria.id if categoria else None


def _usuario_e_saldo(db, telegram_user) -> tuple[Usuario, float, float, float]:
    usuario_db = get_or_create_user(db, telegram_user.id, telegram_user.full_name)
    lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id).all()
    entradas = sum(float(l.valor or 0) for l in lancamentos if str(l.tipo).lower().startswith("entr"))
    saidas = sum(abs(float(l.valor or 0)) for l in lancamentos if not str(l.tipo).lower().startswith("entr"))
    saldo = entradas - saidas
    return usuario_db, saldo, entradas, saidas


def _formatar_valor_brasileiro(valor: float) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_resposta_html(texto: str) -> str:
    texto = (texto or "").strip().replace("\r\n", "\n")
    texto = re.sub(r"```(?:html|json|markdown|md)?\s*", "", texto, flags=re.IGNORECASE)
    texto = texto.replace("```", "")
    texto = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", texto, flags=re.MULTILINE)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", texto)
    texto = re.sub(r"^\s*[-*]\s+", "• ", texto, flags=re.MULTILINE)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _formatar_lancamento_card(lanc: Lancamento) -> str:
    descricao = escape(lanc.descricao or "Lançamento")
    categoria = escape(lanc.categoria.nome if lanc.categoria else "Sem categoria")
    pagamento = escape(lanc.forma_pagamento or "Não informado")
    tipo = escape(lanc.tipo or "Não informado")
    data_formatada = lanc.data_transacao.strftime("%d/%m/%Y")
    hora_formatada = lanc.data_transacao.strftime("%H:%M")
    valor = _formatar_valor_brasileiro(abs(float(lanc.valor or 0)))
    tipo_emoji = "🟢" if str(lanc.tipo).lower().startswith("entr") else "🔴"

    return (
        f"📌 <b>Seu último lançamento</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{tipo_emoji} <b>{descricao}</b>\n\n"
        f"<b>💰 Valor:</b> <code>{valor}</code>\n"
        f"<b>📅 Data:</b> {data_formatada} às {hora_formatada}\n"
        f"<b>📂 Categoria:</b> {categoria}\n"
        f"<b>💳 Pagamento:</b> {pagamento}\n"
        f"<b>🏷️ Tipo:</b> {tipo}"
    )


def _intencao_ultimo_lancamento(texto: str) -> bool:
    texto = (texto or "").lower()
    return any(
        frase in texto
        for frase in [
            "último lançamento",
            "ultimo lançamento",
            "ultimo lancamento",
            "última transação",
            "ultima transacao",
            "última compra",
            "ultima compra",
            "lançamento mais recente",
            "lancamento mais recente",
            "último gasto",
            "ultimo gasto",
        ]
    )


def _intencao_saldo(texto: str) -> bool:
    texto = (texto or "").lower()
    return any(p in texto for p in ["saldo", "quanto tenho", "meu saldo", "saldo total", "quanto sobrou"])


def _intencao_metas(texto: str) -> bool:
    texto = (texto or "").lower()
    return any(
        p in texto
        for p in [
            "meta ativa",
            "meta ativas",
            "metas ativas",
            "minhas metas",
            "quais metas",
            "tenho metas",
            "metas",
        ]
    )


def _buscar_ultimo_lancamento_sem_futuro(db, usuario_id: int) -> Lancamento | None:
    """
    Regra de prioridade:
    1) Busca o último inserido de hoje.
    2) Se não houver, busca o último inserido de ontem.
    3) Se não houver, busca o último inserido de qualquer dia <= hoje.
    Nunca retorna transações futuras.
    """
    agora = datetime.now()
    hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoje_fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)
    ontem_inicio = hoje_inicio - timedelta(days=1)
    ontem_fim = hoje_inicio - timedelta(microseconds=1)

    base = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao <= hoje_fim,
        )
        .order_by(Lancamento.id.desc())
    )

    hoje = base.filter(Lancamento.data_transacao >= hoje_inicio).first()
    if hoje:
        return hoje

    ontem = base.filter(
        Lancamento.data_transacao >= ontem_inicio,
        Lancamento.data_transacao <= ontem_fim,
    ).first()
    if ontem:
        return ontem

    return base.first()


def _formatar_metas_ativas(objetivos: list[Objetivo]) -> str:
    if not objetivos:
        return (
            "🎯 <b>Metas ativas</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Não encontrei metas ativas no seu banco neste momento."
        )

    linhas = ["🎯 <b>Metas ativas</b>", "━━━━━━━━━━━━━━━━━━", ""]
    for objetivo in objetivos[:8]:
        valor_meta = float(objetivo.valor_meta or 0)
        valor_atual = float(objetivo.valor_atual or 0)
        progresso = 0.0 if valor_meta <= 0 else min(100.0, max(0.0, (valor_atual / valor_meta) * 100.0))
        prazo = objetivo.data_meta.strftime("%d/%m/%Y") if objetivo.data_meta else "sem prazo"
        linhas.append(
            f"• <b>{escape(objetivo.descricao or 'Meta')}</b>\n"
            f"  { _formatar_valor_brasileiro(valor_atual) } de { _formatar_valor_brasileiro(valor_meta) }"
            f" ({progresso:.0f}%) | prazo: {escape(prazo)}"
        )
    return "\n".join(linhas)


async def processar_mensagem_com_alfredo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteador sempre ativo: texto/voz -> Groq tools -> execução local."""
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    if not config.GROQ_API_KEY:
        await update.message.reply_text("❌ GROQ_API_KEY não configurada no servidor.")
        return ConversationHandler.END

    _clear_pending_context(context)

    texto_usuario = ""
    if update.message.voice:
        wait_msg = await update.message.reply_text("🎙️ Entendi seu áudio, processando com o Alfredo...")
        try:
            voice = update.message.voice
            tg_file = await voice.get_file()
            voice_bytes = bytes(await tg_file.download_as_bytearray())
            texto_usuario = await _groq_transcribe_voice_async(voice_bytes, voice.mime_type or "audio/ogg")
        except Exception as exc:
            logger.error("Falha ao transcrever áudio com Groq: %s", exc, exc_info=True)
            await wait_msg.edit_text("❌ Não consegui transcrever seu áudio. Tente novamente.")
            return ConversationHandler.END
        finally:
            try:
                await wait_msg.delete()
            except Exception:
                pass
    else:
        texto_usuario = (update.message.text or "").strip()

    if not texto_usuario:
        await update.message.reply_text("Não consegui entender sua mensagem. Pode tentar de novo?")
        return ConversationHandler.END

    db = next(get_db())
    try:
        usuario_db, saldo, entradas, saidas = _usuario_e_saldo(db, update.effective_user)

        texto_normalizado = texto_usuario.strip().lower()

        if _intencao_ultimo_lancamento(texto_normalizado):
            ultimo = _buscar_ultimo_lancamento_sem_futuro(db, usuario_db.id)
            if not ultimo:
                await update.message.reply_html(
                    "🔎 <b>Nenhum lançamento encontrado</b>\n\n"
                    "Você ainda não tem lançamentos registrados no seu banco."
                )
                return ConversationHandler.END

            await update.message.reply_html(_formatar_lancamento_card(ultimo))
            return ConversationHandler.END

        if _intencao_saldo(texto_normalizado):
            saldo_msg = (
                "💰 <b>Seu saldo atual</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Saldo:</b> <code>{_formatar_valor_brasileiro(saldo)}</code>\n"
                f"<b>Entradas acumuladas:</b> <code>{_formatar_valor_brasileiro(entradas)}</code>\n"
                f"<b>Saídas acumuladas:</b> <code>{_formatar_valor_brasileiro(saidas)}</code>"
            )
            await update.message.reply_html(saldo_msg)
            return ConversationHandler.END

        if _intencao_metas(texto_normalizado):
            objetivos_ativos = (
                db.query(Objetivo)
                .filter(
                    Objetivo.id_usuario == usuario_db.id,
                    func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0),
                )
                .order_by(Objetivo.criado_em.desc(), Objetivo.id.desc())
                .all()
            )
            await update.message.reply_html(_formatar_metas_ativas(objetivos_ativos))
            return ConversationHandler.END

        system_prompt = (
            "Você é Alfredo, um Despachante Financeiro. "
            "Sempre escolha UMA tool quando houver intenção acionável. "
            "Use responder_duvida_financeira para perguntas gerais. "
            "Responda ESTRITAMENTE à pergunta do usuário. "
            "Se ele perguntar de metas, fale SÓ de metas. "
            "Use o contexto financeiro apenas como base de conhecimento silenciosa, "
            "não repita os dados a menos que seja solicitado. "
            "Responda em português do Brasil usando HTML simples para Telegram. "
            "Nunca use markdown com asteriscos. "
            "Suas respostas devem ser curtas, diretas e escaneáveis para dispositivos móveis. "
            "NUNCA ultrapasse 3 parágrafos curtos. "
            "Prefira bullet points quando estiver listando informações. "
            "Não invente valores, datas, categorias ou lançamentos ausentes. "
            "Se faltar dado no contexto ou no banco, diga claramente que não encontrou a informação. "
            "Tente deduzir a forma de pagamento da mensagem do usuário. "
            "Se não houver indicação explícita, preencha obrigatoriamente como Nao_informado. "
            "\n### INSTRUÇÕES CRÍTICAS PARA NÚMERO E DATAS:\n"
            "- Para VALORES MONETÁRIOS: Extraia com máxima precisão. Não confunda dígitos (32 ≠ 12). "
            "- Para DATAS: Sempre use formato YYYY-MM-DD. Se o usuário disser '12/12/2026', converta para '2026-12-12'. "
            "- Para FREQUÊNCIA: Se não explicit, considere 'mensal' como padrão (não 'único'). "
            "- NUNCA aproxime números. Se está em dúvida, use o número EXATO mencionado. "
            "- Em agendamentos e metas, confirme sempre os dados antes de persistir. "
            "- Para receita recorrente, use a tool agendar_receita; para despesa recorrente, agendar_despesa."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_usuario},
        ]

        try:
            completion = await _groq_chat_completion_async(messages, tools=_ALFREDO_TOOLS, tool_choice="auto")
        except requests.HTTPError as groq_err:
            logger.warning("Falha na chamada Groq com tools; tentando fallback sem tools: %s", groq_err)
            completion = await _groq_chat_completion_async(messages)
        choice = ((completion or {}).get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            resposta_direta = (message.get("content") or "Não consegui processar agora. Tente novamente.").strip()
            await update.message.reply_html(_formatar_resposta_html(resposta_direta))
            return ConversationHandler.END

        tool_call = tool_calls[0]
        fn = (tool_call.get("function") or {})
        fn_name = fn.get("name")
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}

        if fn_name == "registrar_lancamento":
            descricao = str(args.get("descricao") or "Lançamento").strip()
            categoria = str(args.get("categoria") or "Outros").strip()
            forma_pagamento = _normalizar_forma_pagamento(args.get("forma_pagamento"))
            tipo_transacao = _inferir_tipo_lancamento(texto_usuario, categoria, args.get("tipo"))
            data_lancamento = _normalizar_data_lancamento(args.get("data"))
            try:
                valor = float(str(args.get("valor") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor = 0.0

            if valor <= 0:
                await update.message.reply_html(
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor maior que zero para preparar o lançamento."
                )
                return ConversationHandler.END

            dados_quick = {
                "acao": "registrar_lancamento",
                "descricao": descricao,
                "valor": valor,
                "categoria": categoria,
                "categoria_sugerida": categoria,
                "subcategoria_sugerida": "N/A",
                "forma_pagamento": forma_pagamento,
                "tipo_transacao": tipo_transacao,
                "data": data_lancamento,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick
            # Compatibilidade com quick_action_handler legado
            context.user_data["quick_lancamento"] = dados_quick

            preview = (
                "🧾 <b>Confirme o lançamento</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
                f"• <b>Tipo:</b> {escape(tipo_transacao)}\n"
                f"• <b>Data:</b> {escape(data_lancamento)}\n"
                f"• <b>Categoria:</b> {escape(categoria)}\n"
                f"• <b>Pagamento:</b> {escape(forma_pagamento)}"
            )
            webapp_url = _get_webapp_url("editar", draft=dados_quick)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", web_app=WebAppInfo(url=webapp_url))],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name in {"agendar_despesa", "agendar_receita"}:
            eh_receita = fn_name == "agendar_receita"
            descricao_default = "Receita agendada" if eh_receita else "Despesa agendada"
            descricao = str(args.get("descricao") or descricao_default).strip()
            try:
                valor = float(str(args.get("valor") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor = 0.0
            data_str = str(args.get("data") or "").strip()
            frequencia = str(args.get("frequencia") or "mensal").strip().lower()
            parcelas = args.get("parcelas")
            try:
                parcelas = int(parcelas) if parcelas is not None else None
            except (ValueError, TypeError):
                parcelas = None

            if valor <= 0 or not data_str:
                await update.message.reply_html(
                    "❌ <b>Dados incompletos</b>\n\n"
                    "Informe descrição, valor (&gt; 0) e data de início em <code>YYYY-MM-DD</code>."
                )
                return ConversationHandler.END

            try:
                data_primeiro = datetime.fromisoformat(data_str).date()
            except ValueError:
                await update.message.reply_html(
                    "❌ <b>Data inválida</b>\n\n"
                    "Use <code>YYYY-MM-DD</code> (ex.: <code>2026-12-12</code>)."
                )
                return ConversationHandler.END

            frequencia_normalizada = frequencia if frequencia in {"unico", "semanal", "mensal"} else "mensal"
            acao_agendamento = "agendar_receita" if eh_receita else "agendar_despesa"

            dados_quick = {
                "acao": acao_agendamento,
                "descricao": descricao,
                "valor": valor,
                "data": data_str,
                "frequencia": frequencia_normalizada,
                "parcelas": parcelas,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            parcelas_texto = "indefinido" if parcelas is None else str(parcelas)
            emoji = "💸" if eh_receita else "🗓️"
            titulo = "Confirme o agendamento de receita" if eh_receita else "Confirme o agendamento"
            preview = (
                f"{emoji} <b>{titulo}</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
                f"• <b>Início:</b> {data_primeiro.strftime('%d/%m/%Y')}\n"
                f"• <b>Frequência:</b> {escape(frequencia_normalizada)}\n"
                f"• <b>Parcelas:</b> {escape(parcelas_texto)}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", callback_data="quick_edit")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "criar_meta":
            descricao = str(args.get("descricao") or "Meta").strip()
            try:
                valor_alvo = float(str(args.get("valor_alvo") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor_alvo = 0.0
            data_meta_str = str(args.get("data_meta") or "").strip()

            if valor_alvo <= 0:
                await update.message.reply_html(
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor alvo maior que zero."
                )
                return ConversationHandler.END

            data_meta = None
            if data_meta_str:
                try:
                    data_meta = datetime.fromisoformat(data_meta_str).date()
                except ValueError:
                    await update.message.reply_html(
                        "❌ <b>Prazo inválido</b>\n\n"
                        "Use <code>YYYY-MM-DD</code> para data da meta."
                    )
                    return ConversationHandler.END

            dados_quick = {
                "acao": "criar_meta",
                "descricao": descricao,
                "valor_alvo": valor_alvo,
                "data_meta": data_meta_str if data_meta_str else None,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            prazo_txt = data_meta.strftime("%d/%m/%Y") if data_meta else "Sem prazo definido"
            preview = (
                "🎯 <b>Confirme a meta</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor alvo:</b> <code>{_formatar_valor_brasileiro(valor_alvo)}</code>\n"
                f"• <b>Prazo:</b> {escape(prazo_txt)}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", callback_data="quick_edit")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "responder_duvida_financeira":
            pergunta = str(args.get("pergunta") or texto_usuario)

            ultimos_lanc = (
                db.query(Lancamento)
                .filter(Lancamento.id_usuario == usuario_db.id)
                .order_by(Lancamento.id.desc())
                .limit(5)
                .all()
            )

            resumo_ultimos = []
            for lanc in ultimos_lanc:
                valor = float(lanc.valor or 0)
                sinal = "+" if str(lanc.tipo).lower().startswith("entr") else "-"
                resumo_ultimos.append(
                    f"{lanc.data_transacao.strftime('%d/%m/%Y')} | {lanc.descricao or 'Lançamento'} | {sinal}R$ {abs(valor):.2f}"
                )

            categorias_saida: dict[str, float] = {}
            for lanc in (
                db.query(Lancamento)
                .filter(Lancamento.id_usuario == usuario_db.id)
                .order_by(Lancamento.id.desc())
                .limit(120)
                .all()
            ):
                if str(lanc.tipo).lower().startswith("entr"):
                    continue
                chave = "Sem categoria"
                if getattr(lanc, "categoria", None) and lanc.categoria:
                    chave = lanc.categoria.nome or chave
                categorias_saida[chave] = categorias_saida.get(chave, 0.0) + abs(float(lanc.valor or 0))

            top_categorias = sorted(categorias_saida.items(), key=lambda x: x[1], reverse=True)[:5]
            resumo_categorias = [f"{nome}: R$ {valor:.2f}" for nome, valor in top_categorias]

            metas_ativas = (
                db.query(Objetivo)
                .filter(
                    Objetivo.id_usuario == usuario_db.id,
                    func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0),
                )
                .order_by(Objetivo.criado_em.desc(), Objetivo.id.desc())
                .limit(5)
                .all()
            )
            resumo_metas = [
                f"{(m.descricao or 'Meta')} ({float(m.valor_atual or 0):.2f}/{float(m.valor_meta or 0):.2f})"
                for m in metas_ativas
            ]

            contextual_messages = [
                {
                    "role": "system",
                    "content": (
                        "Responda ESTRITAMENTE à pergunta do usuário. "
                        "Se ele perguntar de metas, fale SÓ de metas. "
                        "Use o contexto financeiro apenas como base de conhecimento silenciosa, "
                        "não repita os dados a menos que seja solicitado. "
                        "Responda em português do Brasil, objetivo e útil. "
                        "Seja curto e escaneável para mobile. "
                        "NUNCA ultrapasse 3 parágrafos curtos e prefira bullet points. "
                        "Use apenas os dados informados no contexto financeiro. "
                        "Não invente números, contas ou transações. "
                        "Se um dado não estiver disponível, diga que não encontrou no banco. "
                        "Os números no contexto abaixo são dados reais do usuário e devem ser priorizados. "
                        "Use formatação curta amigável para Telegram em HTML simples."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Pergunta: {pergunta}\n"
                        f"Contexto financeiro atual do usuário:\n"
                        f"- Saldo: R$ {saldo:.2f}\n"
                        f"- Entradas acumuladas: R$ {entradas:.2f}\n"
                        f"- Saídas acumuladas: R$ {saidas:.2f}\n"
                        f"- Últimos lançamentos reais: {('; '.join(resumo_ultimos)) if resumo_ultimos else 'nenhum lançamento encontrado'}\n"
                        f"- Top categorias de gasto reais: {('; '.join(resumo_categorias)) if resumo_categorias else 'sem categorias suficientes'}\n"
                        f"- Metas ativas reais: {('; '.join(resumo_metas)) if resumo_metas else 'nenhuma meta ativa encontrada'}\n"
                    ),
                },
            ]
            answer_completion = await _groq_chat_completion_async(contextual_messages)
            answer = (((answer_completion or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
            answer = (answer or "Não consegui responder agora, tente novamente.").strip()
            await update.message.reply_html(_formatar_resposta_html(answer))
            return ConversationHandler.END

        await update.message.reply_text("Não consegui entender essa ação ainda. Tente reformular a mensagem.")
        return ConversationHandler.END
    except Exception as exc:
        logger.error("Erro no roteador Alfredo: %s", exc, exc_info=True)
        await update.message.reply_text("❌ Tive um problema ao processar sua mensagem. Tente novamente em instantes.")
        return ConversationHandler.END
    finally:
        db.close()


async def comando_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /insights - Análise inteligente dos gastos do mês
    """
    user = update.effective_user
    await update.message.reply_text("🤖 Analisando seus gastos com IA... Aguarde um momento.")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        # Buscar transações do mês atual
        hoje = datetime.now()
        transacoes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).all()
        
        if not transacoes:
            await update.message.reply_html(
                "📊 <b>Sem dados para análise</b>\n\n"
                "Você ainda não tem gastos registrados este mês.\n"
                "Use /lancamento para adicionar transações!"
            )
            return
        
        # Converter para formato dict
        transacoes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes
        ]
        
        # Gerar análise com IA
        analisador = get_analisador()
        analise = analisador.analisar_padrao_gastos(transacoes_dict, periodo_dias=30)
        
        await update.message.reply_html(
            f"🤖 <b>Análise Inteligente - {hoje.strftime('%B/%Y')}</b>\n\n"
            f"{analise}\n\n"
            f"💡 <i>Use /economia para receber sugestões personalizadas!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando insights: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao gerar a análise. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_economia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /economia [valor] - Sugestões de como economizar
    Exemplo: /economia 500
    """
    user = update.effective_user
    
    # Verificar se foi passado o valor meta
    meta_economia = 300.0  # Valor padrão
    if context.args:
        try:
            meta_economia = float(context.args[0].replace(',', '.'))
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido! Use: /economia 500 (para economizar R$ 500)"
            )
            return
    
    await update.message.reply_text(
        f"💡 Gerando sugestões para economizar R$ {meta_economia:.2f}..."
    )
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        # Buscar transações dos últimos 30 dias
        hoje = datetime.now()
        data_inicio = hoje - timedelta(days=30)
        
        transacoes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio
            )
        ).all()
        
        if not transacoes:
            await update.message.reply_html(
                "📊 <b>Sem dados para análise</b>\n\n"
                "Você ainda não tem gastos registrados.\n"
                "Use /lancamento para adicionar transações!"
            )
            return
        
        # Converter para formato dict
        transacoes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes
        ]
        
        # Gerar sugestões com IA
        analisador = get_analisador()
        sugestoes = analisador.sugerir_economia(transacoes_dict, meta_economia)
        
        await update.message.reply_html(
            f"💡 <b>Sugestões Personalizadas de Economia</b>\n"
            f"🎯 Meta: R$ {meta_economia:.2f}/mês\n\n"
            f"{sugestoes}\n\n"
            f"💪 <i>Pequenas mudanças fazem grande diferença!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando economia: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao gerar sugestões. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /comparar - Compara gastos do mês atual com o anterior
    """
    user = update.effective_user
    await update.message.reply_text("📊 Comparando seus gastos com o mês anterior...")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        hoje = datetime.now()
        
        # Mês atual
        transacoes_atual = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).all()
        
        # Mês anterior
        mes_anterior = hoje.replace(day=1) - timedelta(days=1)
        transacoes_anterior = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == mes_anterior.year,
                extract('month', Lancamento.data_transacao) == mes_anterior.month
            )
        ).all()
        
        if not transacoes_atual and not transacoes_anterior:
            await update.message.reply_html(
                "📊 <b>Sem dados para comparação</b>\n\n"
                "Você ainda não tem gastos registrados nos últimos 2 meses."
            )
            return
        
        # Converter para formato dict
        atual_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_atual
        ]
        
        anterior_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_anterior
        ]
        
        # Gerar comparação com IA
        analisador = get_analisador()
        comparacao = analisador.comparar_periodos(atual_dict, anterior_dict)
        
        mes_atual_nome = hoje.strftime('%B')
        mes_anterior_nome = mes_anterior.strftime('%B')
        
        await update.message.reply_html(
            f"📊 <b>Comparação de Gastos</b>\n"
            f"📅 {mes_anterior_nome} vs {mes_atual_nome}\n\n"
            f"{comparacao}\n\n"
            f"💡 <i>Use /insights para análise detalhada do mês atual!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando comparar: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao comparar períodos. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /alertas - Detecta gastos anormais ou suspeitos
    """
    user = update.effective_user
    await update.message.reply_text("🔍 Analisando padrões e procurando anomalias...")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        hoje = datetime.now()
        
        # Transações dos últimos 30 dias (recentes)
        data_inicio_recente = hoje - timedelta(days=30)
        transacoes_recentes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio_recente
            )
        ).all()
        
        # Histórico dos últimos 6 meses (para comparação)
        data_inicio_historico = hoje - timedelta(days=180)
        historico = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio_historico,
                Lancamento.data_transacao < data_inicio_recente
            )
        ).all()
        
        if not transacoes_recentes:
            await update.message.reply_html(
                "📊 <b>Sem dados recentes</b>\n\n"
                "Você não tem gastos registrados nos últimos 30 dias."
            )
            return
        
        if not historico:
            await update.message.reply_html(
                "📊 <b>Sem histórico para comparação</b>\n\n"
                "Preciso de pelo menos 2 meses de dados para detectar anomalias.\n"
                "Continue usando o bot e em breve terei insights para você!"
            )
            return
        
        # Converter para formato dict
        recentes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_recentes
        ]
        
        historico_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in historico
        ]
        
        # Detectar anomalias
        analisador = get_analisador()
        anomalias = analisador.detectar_anomalias(recentes_dict, historico_dict)
        
        if not anomalias:
            await update.message.reply_html(
                "✅ <b>Tudo Normal!</b>\n\n"
                "Não detectei nenhum gasto anormal nos últimos 30 dias.\n"
                "Seus gastos estão dentro do padrão esperado. 👍"
            )
        else:
            texto_alertas = "🚨 <b>Alertas Detectados</b>\n\n"
            texto_alertas += f"Encontrei <b>{len(anomalias)}</b> gasto(s) fora do padrão:\n\n"
            
            for idx, anomalia in enumerate(anomalias[:5], 1):  # Máximo 5 alertas
                t = anomalia['transacao']
                motivo = anomalia['motivo']
                severidade = anomalia['severidade']
                
                emoji = "🔴" if severidade == 'alta' else "🟡"
                
                texto_alertas += (
                    f"{emoji} <b>{idx}. {t['descricao']}</b>\n"
                    f"   Valor: R$ {t['valor']:.2f}\n"
                    f"   {motivo}\n\n"
                )
            
            if len(anomalias) > 5:
                texto_alertas += f"... e mais {len(anomalias) - 5} alertas.\n\n"
            
            texto_alertas += "💡 <i>Verifique se estes gastos estão corretos!</i>"
            
            await update.message.reply_html(texto_alertas)
        
    except Exception as e:
        logger.error(f"❌ Erro no comando alertas: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao analisar alertas. Tente novamente mais tarde."
        )
    finally:
        db.close()


# Handlers para registrar no bot
insights_handler = CommandHandler('insights', comando_insights)
economia_handler = CommandHandler('economia', comando_economia)
comparar_handler = CommandHandler('comparar', comando_comparar)
alertas_handler = CommandHandler('alertas', comando_alertas)
