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
from html import escape
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler
from sqlalchemy import and_, extract
from database.database import get_db, get_or_create_user, buscar_lancamentos_usuario
from models import Lancamento, Usuario, Categoria, Agendamento, Objetivo
import config

try:
    from .analises_ia import get_analisador
except ModuleNotFoundError:
    def get_analisador():
        raise RuntimeError("Modulo opcional analises_ia indisponivel neste ambiente")

logger = logging.getLogger(__name__)


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
                },
                "required": ["descricao", "valor", "categoria"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_despesa",
            "description": "Agenda uma despesa futura com frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor": {"type": "number"},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD."},
                    "frequencia": {"type": "string", "description": "unico, semanal, mensal"},
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
            ultimos = buscar_lancamentos_usuario(telegram_user_id=update.effective_user.id, limit=1)
            if not ultimos:
                await update.message.reply_html(
                    "🔎 <b>Nenhum lançamento encontrado</b>\n\n"
                    "Você ainda não tem lançamentos registrados no seu banco."
                )
                return ConversationHandler.END

            await update.message.reply_html(_formatar_lancamento_card(ultimos[0]))
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

        system_prompt = (
            "Você é Alfredo, um Despachante Financeiro. "
            "Sempre escolha UMA tool quando houver intenção acionável. "
            "Use responder_duvida_financeira para perguntas gerais. "
            "Responda em português do Brasil usando HTML simples para Telegram. "
            "Nunca use markdown com asteriscos. "
            "Não invente valores, datas, categorias ou lançamentos ausentes. "
            "Se faltar dado no contexto ou no banco, diga claramente que não encontrou a informação."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_usuario},
        ]

        completion = await _groq_chat_completion_async(messages, tools=_ALFREDO_TOOLS, tool_choice="auto")
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
            descricao = str(args.get("descricao") or "Lançamento")
            valor = float(args.get("valor") or 0)
            categoria = str(args.get("categoria") or "Outros")
            if valor <= 0:
                await update.message.reply_text("❌ Preciso de um valor maior que zero para registrar o lançamento.")
                return ConversationHandler.END

            tipo = "Saída"
            if valor < 0:
                tipo = "Entrada"
                valor = abs(valor)

            id_categoria = _resolve_categoria_id(db, categoria)
            lanc = Lancamento(
                id_usuario=usuario_db.id,
                descricao=descricao,
                valor=valor,
                tipo=tipo,
                data_transacao=datetime.utcnow(),
                id_categoria=id_categoria,
                origem="alfredo",
            )
            db.add(lanc)
            db.commit()
            await update.message.reply_text(f"✅ Lançamento de R$ {valor:.2f} em {escape(categoria)} registrado!")
            return ConversationHandler.END

        if fn_name == "agendar_despesa":
            descricao = str(args.get("descricao") or "Despesa agendada")
            valor = float(args.get("valor") or 0)
            data_str = str(args.get("data") or "").strip()
            frequencia = str(args.get("frequencia") or "mensal").strip().lower()

            if valor <= 0 or not data_str:
                await update.message.reply_text("❌ Para agendar, preciso de descrição, valor e data (YYYY-MM-DD).")
                return ConversationHandler.END

            try:
                data_primeiro = datetime.fromisoformat(data_str).date()
            except ValueError:
                await update.message.reply_text("❌ Data inválida. Use o formato YYYY-MM-DD.")
                return ConversationHandler.END

            ag = Agendamento(
                id_usuario=usuario_db.id,
                descricao=descricao,
                valor=valor,
                tipo="Saída",
                frequencia=frequencia if frequencia in {"unico", "semanal", "mensal"} else "mensal",
                data_primeiro_evento=data_primeiro,
                proxima_data_execucao=data_primeiro,
                ativo=True,
                parcela_atual=0,
            )
            db.add(ag)
            db.commit()
            await update.message.reply_text(f"✅ Despesa '{escape(descricao)}' agendada para {data_primeiro.strftime('%d/%m/%Y')} ({ag.frequencia}).")
            return ConversationHandler.END

        if fn_name == "criar_meta":
            descricao = str(args.get("descricao") or "Meta")
            valor_alvo = float(args.get("valor_alvo") or 0)
            if valor_alvo <= 0:
                await update.message.reply_text("❌ Preciso de um valor alvo maior que zero para criar a meta.")
                return ConversationHandler.END

            hoje = datetime.utcnow().date()
            meta = Objetivo(
                id_usuario=usuario_db.id,
                descricao=descricao,
                valor_meta=valor_alvo,
                valor_atual=0,
                data_meta=datetime(hoje.year, 12, 31).date(),
            )
            db.add(meta)
            db.commit()
            await update.message.reply_text(f"🎯 Meta '{escape(descricao)}' criada com alvo de R$ {valor_alvo:.2f}.")
            return ConversationHandler.END

        if fn_name == "responder_duvida_financeira":
            pergunta = str(args.get("pergunta") or texto_usuario)
            contextual_messages = [
                {
                    "role": "system",
                    "content": (
                        "Responda em português do Brasil, objetivo e útil. "
                        "Use apenas os dados informados no contexto financeiro. "
                        "Não invente números, contas ou transações. "
                        "Se um dado não estiver disponível, diga que não encontrou no banco. "
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
