"""
Metas Financeiras - MaestroFin
=============================

Fluxo de metas com plano mensal, acompanhamento visual e lembretes mensais.
"""

import logging
import re
from html import escape as html_escape
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import google.generativeai as genai
from sqlalchemy import and_, extract, func
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from database.database import (
    criar_novo_objetivo,
    deletar_objetivo_por_id,
    get_db,
    get_or_create_user,
    listar_objetivos_usuario,
)
from gerente_financeiro.menu_botoes import BOTAO_METAS
from gerente_financeiro.gamification_utils import give_xp_for_action
from gerente_financeiro.states import (
    ASK_OBJETIVO_DESCRICAO,
    ASK_OBJETIVO_MENU,
    ASK_OBJETIVO_PRAZO,
    ASK_OBJETIVO_VALOR,
)
from models import Categoria, Lancamento, MetaConfirmacao, Objetivo, Usuario

logger = logging.getLogger(__name__)

PROGRESS_STEPS = 10


# =========================================================================
# CALCULOS E APOIO
# =========================================================================


def _format_currency(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _progress_bar(percentual: float) -> str:
    percent = max(0.0, min(100.0, percentual))
    filled = int(percent // (100 / PROGRESS_STEPS))
    empty = PROGRESS_STEPS - filled
    return "▓" * filled + "░" * empty


_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "a"}


def _sanitize_html(texto: str) -> str:
    if not texto:
        return ""

    tokens = re.split(r"(<[^>]+>)", texto)
    partes = []
    for token in tokens:
        if token.startswith("<") and token.endswith(">"):
            tag = re.sub(r"[</> ]", "", token.split(" ", 1)[0]).lower()
            if tag in _ALLOWED_TAGS:
                partes.append(token)
            else:
                partes.append(html_escape(token))
        else:
            partes.append(token)
    return "".join(partes)


def _meses_entre_datas(inicio: datetime.date, fim: datetime.date) -> int:
    dias = (fim - inicio).days
    return max(1, int(round(dias / 30)))


def calcular_poupanca_media(usuario_id: int, meses: int = 3) -> float:
    """Calcula a media de poupanca mensal do usuario."""
    db = next(get_db())
    try:
        hoje = datetime.now()
        economia_total = 0.0
        meses_com_dados = 0

        for i in range(meses):
            mes_ref = hoje - timedelta(days=i * 30)

            receitas = (
                db.query(func.sum(Lancamento.valor))
                .filter(
                    and_(
                        Lancamento.id_usuario == usuario_id,
                        Lancamento.tipo == "Entrada",
                        extract("year", Lancamento.data_transacao) == mes_ref.year,
                        extract("month", Lancamento.data_transacao) == mes_ref.month,
                    )
                )
                .scalar()
                or 0
            )

            despesas = (
                db.query(func.sum(Lancamento.valor))
                .filter(
                    and_(
                        Lancamento.id_usuario == usuario_id,
                        Lancamento.tipo == "Saída",
                        extract("year", Lancamento.data_transacao) == mes_ref.year,
                        extract("month", Lancamento.data_transacao) == mes_ref.month,
                    )
                )
                .scalar()
                or 0
            )

            if receitas > 0:
                economia_total += float(receitas) - float(despesas)
                meses_com_dados += 1

        return economia_total / meses_com_dados if meses_com_dados > 0 else 0.0
    finally:
        db.close()


def analisar_categorias_cortaveis(usuario_id: int) -> List[Dict]:
    """Identifica categorias onde o usuario pode economizar."""
    db = next(get_db())
    try:
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year

        categorias_cortaveis = [
            "Restaurante/Delivery",
            "Lazer",
            "Entretenimento",
            "Assinaturas",
            "Compras",
            "Bares",
            "Viagens",
        ]

        sugestoes = []

        for nome_cat in categorias_cortaveis:
            gasto_mes = (
                db.query(func.sum(Lancamento.valor))
                .join(Categoria, Lancamento.id_categoria == Categoria.id)
                .filter(
                    and_(
                        Lancamento.id_usuario == usuario_id,
                        Lancamento.tipo == "Saída",
                        Categoria.nome.ilike(f"%{nome_cat}%"),
                        extract("year", Lancamento.data_transacao) == ano_atual,
                        extract("month", Lancamento.data_transacao) == mes_atual,
                    )
                )
                .scalar()
                or 0
            )

            if gasto_mes > 0:
                gasto_mes = float(gasto_mes)
                sugestoes.append(
                    {
                        "categoria": nome_cat,
                        "gasto_atual": gasto_mes,
                        "economia_30": gasto_mes * 0.3,
                        "economia_50": gasto_mes * 0.5,
                    }
                )

        sugestoes.sort(key=lambda x: x["economia_50"], reverse=True)
        return sugestoes[:5]
    finally:
        db.close()


def gerar_plano_base(usuario_id: int, valor_meta: float, prazo_meses: int) -> Dict:
    poupanca_atual = calcular_poupanca_media(usuario_id, meses=3)
    necessario_mes = valor_meta / prazo_meses if prazo_meses > 0 else valor_meta
    deficit = max(0.0, necessario_mes - poupanca_atual)
    categorias_cortaveis = analisar_categorias_cortaveis(usuario_id)
    return {
        "poupanca_atual": poupanca_atual,
        "necessario_mes": necessario_mes,
        "deficit": deficit,
        "categorias_cortaveis": categorias_cortaveis,
    }


def gerar_plano_ia(
    descricao: str,
    valor_meta: float,
    prazo_meses: int,
    plano: Dict,
) -> str:
    necessario_mes = plano["necessario_mes"]
    poupanca_atual = plano["poupanca_atual"]
    deficit = plano["deficit"]

    if not config.GEMINI_API_KEY:
        return (
            f"<b>Plano sugerido:</b> Economize {_format_currency(necessario_mes)}/mês. "
            f"Sua média atual é {_format_currency(poupanca_atual)}/mês. "
            f"{'Ajuste gastos para cobrir o déficit.' if deficit > 0 else 'Você está no caminho certo!'}"
        )

    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        prompt = (
            "Você é um planejador financeiro. Gere um plano curto e elegante em HTML (sem markdown). "
            "Use no máximo 6 linhas e bullets com '•'. "
            "Inclua: valor mensal, dicas práticas e um incentivo.\n"
            f"Meta: {descricao}. Valor total: {_format_currency(valor_meta)}. "
            f"Prazo: {prazo_meses} meses. Valor por mês: {_format_currency(necessario_mes)}. "
            f"Poupança média atual: {_format_currency(poupanca_atual)}. "
            f"Déficit mensal: {_format_currency(deficit)}."
        )
        resposta = model.generate_content(prompt)
        texto = (resposta.text or "").strip()
        return texto if texto else ""
    except Exception as exc:
        logger.warning("Falha ao gerar plano com IA: %s", exc)
        return (
            f"<b>Plano sugerido:</b> Economize {_format_currency(necessario_mes)}/mês. "
            f"Sua média atual é {_format_currency(poupanca_atual)}/mês. "
            f"{'Ajuste gastos para cobrir o déficit.' if deficit > 0 else 'Você está no caminho certo!'}"
        )


# =========================================================================
# MENU E CRIACAO
# =========================================================================


async def metas_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("➕ Criar nova meta", callback_data="metas_criar"),
            InlineKeyboardButton("📋 Ver minhas metas", callback_data="metas_listar"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="metas_cancelar")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        "🎯 <b>Metas Financeiras</b>\n\n"
        "Aqui voce transforma sonhos em metas reais, com plano mensal e progresso visual.\n\n"
        "O que deseja fazer agora?",
        reply_markup=reply_markup,
    )
    return ASK_OBJETIVO_MENU


async def metas_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "metas_criar":
        await query.edit_message_text(
            "🎯 <b>Nova meta</b>\n\n"
            "Descreva sua meta: \n"
            "<i>(ex: Viagem para Europa, Notebook novo)</i>",
            parse_mode="HTML",
        )
        return ASK_OBJETIVO_DESCRICAO

    if query.data == "metas_listar":
        await query.edit_message_text("📋 Carregando suas metas...", parse_mode="HTML")
        await metas_listar(update, context, edit=False)
        return ASK_OBJETIVO_MENU

    await query.edit_message_text("Operacao cancelada.")
    context.user_data.clear()
    return ConversationHandler.END


async def metas_ask_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["meta_descricao"] = update.message.text.strip()
    await update.message.reply_html(
        "💰 <b>Qual o valor total da sua meta?</b>\n\n"
        "Digite apenas numeros.\n"
        "<i>(ex: 4500 ou 4500.00)</i>"
    )
    return ASK_OBJETIVO_VALOR


async def metas_ask_prazo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        valor = float(update.message.text.replace("R$", "").replace(".", "").replace(",", ".").strip())
        if valor <= 0:
            raise ValueError("valor invalido")
        context.user_data["meta_valor"] = valor

        await update.message.reply_html(
            "📅 <b>Em quantos meses voce quer atingir?</b>\n\n"
            "Digite o numero de meses.\n"
            "<i>(ex: 6 para 6 meses, 12 para 1 ano)</i>"
        )
        return ASK_OBJETIVO_PRAZO
    except ValueError:
        await update.message.reply_text("❌ Valor invalido. Digite apenas numeros.")
        return ASK_OBJETIVO_VALOR


async def metas_criar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        prazo_meses = int(update.message.text.strip())
        if prazo_meses <= 0:
            raise ValueError("prazo invalido")

        descricao = context.user_data.get("meta_descricao")
        valor_meta = context.user_data.get("meta_valor")
        if not descricao or valor_meta is None:
            await update.message.reply_text("❌ Dados incompletos. Tente novamente.")
            return ConversationHandler.END

        user = update.effective_user
        db = next(get_db())
        try:
            usuario_db = get_or_create_user(db, user.id, user.full_name)
        finally:
            db.close()

        data_meta = datetime.now().date() + timedelta(days=prazo_meses * 30)
        resultado = criar_novo_objetivo(user.id, descricao, valor_meta, data_meta)

        if resultado == "DUPLICATE":
            await update.message.reply_html(
                "⚠️ <b>Ja existe uma meta com essa descricao.</b>\n"
                "Tente um nome diferente."
            )
            context.user_data.clear()
            return ConversationHandler.END

        if not isinstance(resultado, Objetivo):
            await update.message.reply_text("❌ Erro ao criar meta. Tente novamente.")
            context.user_data.clear()
            return ConversationHandler.END

        plano = gerar_plano_base(usuario_db.id, valor_meta, prazo_meses)
        plano_texto = _sanitize_html(gerar_plano_ia(descricao, valor_meta, prazo_meses, plano))

        necessario_mes = plano["necessario_mes"]

        mensagem = (
            "✅ <b>Meta criada com sucesso!</b>\n\n"
            f"🎯 <b>{descricao}</b>\n"
            f"💰 Valor total: <code>{_format_currency(valor_meta)}</code>\n"
            f"📅 Prazo: <b>{prazo_meses} meses</b>\n"
            f"💵 Valor mensal: <b>{_format_currency(necessario_mes)}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🧠 <b>Plano da IA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )

        mensagem += plano_texto or (
            f"<b>Plano sugerido:</b> Economize {_format_currency(necessario_mes)}/mês."
        )

        mensagem += "\n\n📌 Use /metas para acompanhar o progresso."

        await update.message.reply_html(mensagem)

        await give_xp_for_action(user.id, "META_CRIADA", context)
    except ValueError:
        await update.message.reply_text("❌ Prazo invalido. Digite apenas o numero de meses.")
        return ASK_OBJETIVO_PRAZO
    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def metas_listar(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    user = update.effective_user
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        objetivos = listar_objetivos_usuario(usuario_db.telegram_id)
    finally:
        db.close()

    if not objetivos:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "📋 <b>Voce ainda nao tem metas.</b>\n\n"
                "Crie sua primeira meta e receba um plano mensal automatizado."
            ),
            parse_mode="HTML",
        )
        return

    header = (
        "🎯 <b>Painel de Metas</b>\n"
        "Progresso atualizado e plano mensal sob medida.\n"
    )
    await context.bot.send_message(chat_id=user.id, text=header, parse_mode="HTML")

    hoje = datetime.now().date()

    for obj in objetivos:
        valor_meta = float(obj.valor_meta)
        valor_atual = float(obj.valor_atual or 0)
        percentual = (valor_atual / valor_meta * 100) if valor_meta > 0 else 0
        barra = _progress_bar(percentual)

        if obj.data_meta:
            prazo_meses = _meses_entre_datas(obj.criado_em.date(), obj.data_meta)
            dias_restantes = (obj.data_meta - hoje).days
            meses_restantes = max(1, int(round(dias_restantes / 30)))
            prazo_label = f"{obj.data_meta.strftime('%d/%m/%Y')} ({meses_restantes} meses restantes)"
        else:
            prazo_meses = 1
            meses_restantes = 0
            prazo_label = "Sem prazo definido"

        necessario_mes = (valor_meta / prazo_meses) if prazo_meses > 0 else valor_meta

        status = "✅ Meta atingida" if percentual >= 100 else "⏳ Em andamento"

        mensagem = (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>{obj.descricao}</b>\n"
            f"{barra} <b>{percentual:.1f}%</b>\n"
            f"💰 {_format_currency(valor_atual)} / {_format_currency(valor_meta)}\n"
            f"📅 Prazo: {prazo_label}\n"
            f"💵 Plano mensal: <b>{_format_currency(necessario_mes)}</b>\n"
            f"🔖 Status: {status}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = [
            [InlineKeyboardButton("🗑️ Remover", callback_data=f"meta_delete_{obj.id}")],
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text=mensagem,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def metas_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    try:
        meta_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Meta invalida.")
        return

    sucesso = deletar_objetivo_por_id(meta_id, query.from_user.id)
    if sucesso:
        await query.edit_message_text("✅ Meta removida com sucesso.")
    else:
        await query.edit_message_text("❌ Nao foi possivel remover essa meta.")


# =========================================================================
# JOB MENSAL
# =========================================================================


async def job_metas_mensal(context: ContextTypes.DEFAULT_TYPE) -> None:
    hoje = datetime.now().date()
    if hoje.day != 1:
        return

    db = next(get_db())
    try:
        objetivos = (
            db.query(Objetivo)
            .join(Usuario)
            .filter(Objetivo.data_meta >= hoje)
            .all()
        )

        for obj in objetivos:
            if float(obj.valor_atual or 0) >= float(obj.valor_meta):
                continue

            if not obj.data_meta:
                continue

            confirmacao = (
                db.query(MetaConfirmacao)
                .filter(
                    MetaConfirmacao.id_objetivo == obj.id,
                    MetaConfirmacao.ano == hoje.year,
                    MetaConfirmacao.mes == hoje.month,
                )
                .first()
            )
            if confirmacao:
                continue

            prazo_meses = _meses_entre_datas(obj.criado_em.date(), obj.data_meta)
            aporte = float(obj.valor_meta) / prazo_meses if prazo_meses > 0 else float(obj.valor_meta)

            percentual = float(obj.valor_atual or 0) / float(obj.valor_meta) * 100
            barra = _progress_bar(percentual)

            texto = (
                "📅 <b>Check-in mensal da sua meta</b>\n\n"
                f"🎯 <b>{obj.descricao}</b>\n"
                f"{barra} <b>{percentual:.1f}%</b>\n"
                f"💵 Valor sugerido do mes: <b>{_format_currency(aporte)}</b>\n\n"
                "Voce conseguiu guardar esse valor este mes?"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Sim, consegui",
                        callback_data=f"meta_confirm_{obj.id}_{hoje.year}_{hoje.month}",
                    ),
                    InlineKeyboardButton(
                        "❌ Ainda nao",
                        callback_data=f"meta_skip_{obj.id}_{hoje.year}_{hoje.month}",
                    ),
                ]
            ]

            await context.bot.send_message(
                chat_id=obj.usuario.telegram_id,
                text=texto,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    finally:
        db.close()


async def metas_confirmacao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 5:
        await query.edit_message_text("❌ Confirmacao invalida.")
        return

    _, acao, obj_id, ano, mes = parts

    try:
        objetivo_id = int(obj_id)
        ano = int(ano)
        mes = int(mes)
    except ValueError:
        await query.edit_message_text("❌ Confirmacao invalida.")
        return

    db = next(get_db())
    try:
        objetivo = db.query(Objetivo).filter(Objetivo.id == objetivo_id).first()
        if not objetivo:
            await query.edit_message_text("❌ Meta nao encontrada.")
            return

        confirmacao_existente = (
            db.query(MetaConfirmacao)
            .filter(
                MetaConfirmacao.id_objetivo == objetivo_id,
                MetaConfirmacao.ano == ano,
                MetaConfirmacao.mes == mes,
            )
            .first()
        )
        if confirmacao_existente:
            await query.edit_message_text("✅ Este mes ja foi registrado.")
            return

        if objetivo.data_meta:
            prazo_meses = _meses_entre_datas(objetivo.criado_em.date(), objetivo.data_meta)
        else:
            prazo_meses = 1
        aporte = float(objetivo.valor_meta) / prazo_meses if prazo_meses > 0 else float(objetivo.valor_meta)

        if acao == "confirm":
            novo_valor = min(float(objetivo.valor_meta), float(objetivo.valor_atual or 0) + aporte)
            objetivo.valor_atual = novo_valor
            valor_confirmado = aporte
            mensagem_status = "✅ Progresso atualizado!"
        else:
            valor_confirmado = 0.0
            mensagem_status = "Entendido. Seguimos acompanhando sua meta."

        confirmacao = MetaConfirmacao(
            id_usuario=objetivo.id_usuario,
            id_objetivo=objetivo.id,
            ano=ano,
            mes=mes,
            valor_confirmado=valor_confirmado,
        )
        db.add(confirmacao)
        db.commit()

        percentual = float(objetivo.valor_atual or 0) / float(objetivo.valor_meta) * 100
        barra = _progress_bar(percentual)

        mensagem = (
            f"{mensagem_status}\n\n"
            f"🎯 <b>{objetivo.descricao}</b>\n"
            f"{barra} <b>{percentual:.1f}%</b>\n"
            f"💰 {_format_currency(float(objetivo.valor_atual))} / {_format_currency(float(objetivo.valor_meta))}"
        )
        await query.edit_message_text(mensagem, parse_mode="HTML")

        if acao == "confirm":
            await give_xp_for_action(query.from_user.id, "META_APORTE_CONFIRMADO", context)
            if float(objetivo.valor_atual or 0) >= float(objetivo.valor_meta):
                await give_xp_for_action(query.from_user.id, "META_ATINGIDA", context)
    finally:
        db.close()


async def metas_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operacao cancelada.")
    context.user_data.clear()
    return ConversationHandler.END


metas_conv = ConversationHandler(
    entry_points=[
        CommandHandler("metas", metas_start),
        MessageHandler(filters.Regex(f"^{BOTAO_METAS}$"), metas_start),
    ],
    states={
        ASK_OBJETIVO_MENU: [
            CallbackQueryHandler(metas_menu_callback, pattern="^metas_")
        ],
        ASK_OBJETIVO_DESCRICAO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, metas_ask_valor)
        ],
        ASK_OBJETIVO_VALOR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, metas_ask_prazo)
        ],
        ASK_OBJETIVO_PRAZO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, metas_criar)
        ],
    },
    fallbacks=[
        CommandHandler(["cancelar", "cancel", "sair", "parar"], metas_cancel),
        MessageHandler(filters.Regex(r"(?i)^/?\s*(cancelar|cancel|sair|parar)$"), metas_cancel),
    ],
    per_message=False,
    per_user=True,
    per_chat=True,
)

metas_callbacks = [
    CallbackQueryHandler(metas_delete_callback, pattern="^meta_delete_"),
    CallbackQueryHandler(metas_confirmacao_callback, pattern="^meta_(confirm|skip)_"),
]
