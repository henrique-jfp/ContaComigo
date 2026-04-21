"""
Sistema de Alertas e Notificações - ContaComigo
"""
import logging
from datetime import datetime, time, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session
from sqlalchemy import or_
from dateutil.relativedelta import relativedelta
from database.database import get_db
from models import Usuario, Objetivo, Agendamento, Lembrete, Lancamento, MetaConfirmacao
from gerente_financeiro.gamification_utils import give_xp_for_action

logger = logging.getLogger(__name__)

def _format_currency(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _avancar_data_recorrente(data_base: date, frequencia: str | None) -> date | None:
    freq = str(frequencia or "unico").lower()
    if freq == "semanal":
        return data_base + timedelta(days=7)
    if freq == "mensal":
        return data_base + relativedelta(months=1)
    return None


def _processar_expiracao_lembretes(db: Session, hoje: date) -> None:
    lembretes = (
        db.query(Lembrete)
        .filter(
            Lembrete.ativo == True,
            Lembrete.proxima_data_execucao < hoje,
        )
        .all()
    )
    houve_alteracao = False

    for lembrete in lembretes:
        proxima = _avancar_data_recorrente(lembrete.proxima_data_execucao, lembrete.frequencia)
        if proxima is None:
            lembrete.ativo = False
            lembrete.status = "vencido"
        else:
            lembrete.parcela_atual = int(lembrete.parcela_atual or 0) + 1
            if lembrete.total_parcelas and lembrete.parcela_atual >= lembrete.total_parcelas:
                lembrete.ativo = False
                lembrete.status = "vencido"
            else:
                lembrete.proxima_data_execucao = proxima
                lembrete.status = "ativo"
        houve_alteracao = True

    if houve_alteracao:
        db.commit()


def _formatar_bloco_agendamento(ag: Agendamento, contexto: str) -> str:
    tipo_emoji = "🟢" if ag.tipo == "Entrada" else "🔴"
    linhas = [f"{tipo_emoji} <b>{ag.descricao}</b>"]
    if getattr(ag, "valor", None) is not None:
        linhas.append(f"💰 <code>{_format_currency(float(ag.valor or 0))}</code>")
    linhas.append(f"📅 {contexto}")
    return "\n".join(linhas)


def _formatar_bloco_lembrete(lembrete: Lembrete, contexto: str) -> str:
    tipo_emoji = "🟢" if str(lembrete.tipo or "").lower() in {"receita", "entrada"} else "🔔"
    linhas = [f"{tipo_emoji} <b>{lembrete.descricao}</b>"]
    if getattr(lembrete, "valor", None) is not None:
        linhas.append(f"💰 <code>{_format_currency(float(lembrete.valor or 0))}</code>")
    linhas.append(f"📅 {contexto}")
    return "\n".join(linhas)


async def enviar_lembretes_usuario(context: ContextTypes.DEFAULT_TYPE):
    """Job disparado no horário específico do usuário para enviar lembretes do dia e de amanhã."""
    job = context.job
    user_id = job.data['user_id']
    agendamentos_hoje_ids = job.data.get('agendamentos_hoje_ids', [])
    agendamentos_amanha_ids = job.data.get('agendamentos_amanha_ids', [])
    lembretes_hoje_ids = job.data.get('lembretes_hoje_ids', [])
    lembretes_amanha_ids = job.data.get('lembretes_amanha_ids', [])
    
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario or not usuario.alerta_gastos_ativo:
            return

        agendamentos_hoje = db.query(Agendamento).filter(Agendamento.id.in_(agendamentos_hoje_ids), Agendamento.ativo == True).all() if agendamentos_hoje_ids else []
        agendamentos_amanha = db.query(Agendamento).filter(Agendamento.id.in_(agendamentos_amanha_ids), Agendamento.ativo == True).all() if agendamentos_amanha_ids else []
        lembretes_hoje = db.query(Lembrete).filter(Lembrete.id.in_(lembretes_hoje_ids), Lembrete.ativo == True).all() if lembretes_hoje_ids else []
        lembretes_amanha = db.query(Lembrete).filter(Lembrete.id.in_(lembretes_amanha_ids), Lembrete.ativo == True).all() if lembretes_amanha_ids else []

        if not any([agendamentos_hoje, agendamentos_amanha, lembretes_hoje, lembretes_amanha]):
            return

        secoes: list[str] = ["🔔 <b>Agenda do Alfredo</b>"]
        keyboard = []

        if agendamentos_amanha or lembretes_amanha:
            linhas = ["", "⏳ <b>Vence amanhã</b>"]
            for ag in agendamentos_amanha:
                linhas.append(_formatar_bloco_agendamento(ag, "Agendamento para amanhã"))
                linhas.append("")
            for lembrete in lembretes_amanha:
                linhas.append(_formatar_bloco_lembrete(lembrete, "Lembrete para amanhã"))
                linhas.append("")
            secoes.append("\n".join(linhas).strip())

        if agendamentos_hoje or lembretes_hoje:
            linhas = ["", "🚨 <b>Vence hoje</b>"]
            for ag in agendamentos_hoje:
                linhas.append(_formatar_bloco_agendamento(ag, "Agendamento para hoje"))
                linhas.append("")
                btn_text = f"✅ Dar baixa: {ag.descricao[:15]}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ag_baixa_{ag.id}")])
            for lembrete in lembretes_hoje:
                linhas.append(_formatar_bloco_lembrete(lembrete, "Lembrete para hoje"))
                linhas.append("")
            secoes.append("\n".join(linhas).strip())

        texto = "\n\n".join(secao for secao in secoes if secao).strip()
        if keyboard:
            texto += "\n\n<i>Toque nos botões abaixo para registrar os agendamentos de hoje no seu fluxo de caixa.</i>"

        await context.bot.send_message(
            chat_id=user_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete para {user_id}: {e}", exc_info=True)
    finally:
        db.close()

async def agendar_notificacoes_diarias(context: ContextTypes.DEFAULT_TYPE):
    """Agenda notificações diárias rodando todo dia na madrugada para todos os usuários."""
    try:
        logger.info("📅 Executando agendamento diário de notificações...")
        
        db = next(get_db())
        hoje = datetime.now().date()
        amanha = hoje + timedelta(days=1)

        _processar_expiracao_lembretes(db, hoje)

        agendamentos_relevantes = db.query(Agendamento).join(Usuario).filter(
            or_(
                Agendamento.proxima_data_execucao <= hoje,
                Agendamento.proxima_data_execucao == amanha,
            ),
            Agendamento.ativo == True,
            Usuario.alerta_gastos_ativo == True,
            Usuario.notif_lembretes == True
        ).all()

        lembretes_relevantes = db.query(Lembrete).join(Usuario).filter(
            Lembrete.proxima_data_execucao.in_([hoje, amanha]),
            Lembrete.ativo == True,
            Usuario.alerta_gastos_ativo == True,
            Usuario.notif_lembretes == True
        ).all()

        notificacoes_por_usuario = {}
        for ag in agendamentos_relevantes:
            user = ag.usuario
            if user.id not in notificacoes_por_usuario:
                notificacoes_por_usuario[user.id] = {
                    'telegram_id': user.telegram_id,
                    'horario': user.horario_notificacao or time(hour=9, minute=0),
                    'agendamentos_hoje_ids': [],
                    'agendamentos_amanha_ids': [],
                    'lembretes_hoje_ids': [],
                    'lembretes_amanha_ids': [],
                }
            chave = 'agendamentos_amanha_ids' if ag.proxima_data_execucao == amanha else 'agendamentos_hoje_ids'
            notificacoes_por_usuario[user.id][chave].append(ag.id)

        for lembrete in lembretes_relevantes:
            user = lembrete.usuario
            if user.id not in notificacoes_por_usuario:
                notificacoes_por_usuario[user.id] = {
                    'telegram_id': user.telegram_id,
                    'horario': user.horario_notificacao or time(hour=9, minute=0),
                    'agendamentos_hoje_ids': [],
                    'agendamentos_amanha_ids': [],
                    'lembretes_hoje_ids': [],
                    'lembretes_amanha_ids': [],
                }
            chave = 'lembretes_hoje_ids' if lembrete.proxima_data_execucao == hoje else 'lembretes_amanha_ids'
            notificacoes_por_usuario[user.id][chave].append(lembrete.id)

        agora = datetime.now()
        for user_data in notificacoes_por_usuario.values():
            horario = user_data['horario']
            target_time = datetime.combine(hoje, horario)
            if target_time <= agora:
                target_time = agora + timedelta(minutes=1)
                
            context.job_queue.run_once(
                enviar_lembretes_usuario,
                when=target_time,
                data={'user_id': user_data['telegram_id'], **user_data},
                name=f"lembrete_{user_data['telegram_id']}_{hoje.strftime('%Y%m%d')}"
            )
            
        logger.info(f"✅ Agendamento diário concluído: {len(notificacoes_por_usuario)} usuários notificados para hoje/amanhã.")
        
    except Exception as e:
        logger.error(f"❌ Erro no agendamento diário: {e}", exc_info=True)
    finally:
        if 'db' in locals():
            db.close()

def _progress_bar(percentual: float) -> str:
    PROGRESS_STEPS = 10
    percent = max(0.0, min(100.0, percentual))
    filled = int(percent // (100 / PROGRESS_STEPS))
    empty = PROGRESS_STEPS - filled
    return "▓" * filled + "░" * empty

def _meses_entre_datas(inicio: date, fim: date) -> int:
    dias = (fim - inicio).days
    return max(1, int(round(dias / 30)))

async def job_metas_mensal(context: ContextTypes.DEFAULT_TYPE) -> None:
    hoje = datetime.now().date()
    if hoje.day != 1:
        return
    db = next(get_db())
    try:
        objetivos = db.query(Objetivo).join(Usuario).filter(Objetivo.data_meta >= hoje).all()
        for obj in objetivos:
            if float(obj.valor_atual or 0) >= float(obj.valor_meta) or not obj.data_meta:
                continue
            confirmacao = db.query(MetaConfirmacao).filter(
                MetaConfirmacao.id_objetivo == obj.id, MetaConfirmacao.ano == hoje.year, MetaConfirmacao.mes == hoje.month
            ).first()
            if confirmacao:
                continue
            prazo_meses = _meses_entre_datas(obj.criado_em.date(), obj.data_meta)
            aporte = float(obj.valor_meta) / prazo_meses if prazo_meses > 0 else float(obj.valor_meta)
            percentual = float(obj.valor_atual or 0) / float(obj.valor_meta) * 100
            texto = (
                "📅 <b>Check-in mensal da sua meta</b>\n\n"
                f"🎯 <b>{obj.descricao}</b>\n"
                f"{_progress_bar(percentual)} <b>{percentual:.1f}%</b>\n"
                f"💵 Valor sugerido do mês: <b>{_format_currency(aporte)}</b>\n\n"
                "Você conseguiu guardar esse valor este mês?"
            )
            keyboard = [
                [InlineKeyboardButton("✅ Sim, consegui", callback_data=f"meta_confirm_{obj.id}_{hoje.year}_{hoje.month}"),
                 InlineKeyboardButton("❌ Ainda não", callback_data=f"meta_skip_{obj.id}_{hoje.year}_{hoje.month}")]
            ]
            await context.bot.send_message(chat_id=obj.usuario.telegram_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db.close()

async def metas_confirmacao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) < 5: return
    _, acao, obj_id, ano, mes = parts
    db = next(get_db())
    try:
        objetivo = db.query(Objetivo).filter(Objetivo.id == int(obj_id)).first()
        if not objetivo: return
        confirmacao_existente = db.query(MetaConfirmacao).filter(
            MetaConfirmacao.id_objetivo == int(obj_id), MetaConfirmacao.ano == int(ano), MetaConfirmacao.mes == int(mes)
        ).first()
        if confirmacao_existente:
            await query.edit_message_text("✅ Este mês já foi registrado.")
            return
        prazo_meses = _meses_entre_datas(objetivo.criado_em.date(), objetivo.data_meta) if objetivo.data_meta else 1
        aporte = float(objetivo.valor_meta) / prazo_meses if prazo_meses > 0 else float(objetivo.valor_meta)
        if acao == "confirm":
            objetivo.valor_atual = min(float(objetivo.valor_meta), float(objetivo.valor_atual or 0) + aporte)
            db.add(MetaConfirmacao(id_usuario=objetivo.id_usuario, id_objetivo=objetivo.id, ano=int(ano), mes=int(mes), valor_confirmado=aporte))
            msg_status = "✅ Progresso atualizado!"
        else:
            db.add(MetaConfirmacao(id_usuario=objetivo.id_usuario, id_objetivo=objetivo.id, ano=int(ano), mes=int(mes), valor_confirmado=0.0))
            msg_status = "Entendido. Seguimos acompanhando sua meta."
        db.commit()
        percentual = float(objetivo.valor_atual or 0) / float(objetivo.valor_meta) * 100
        mensagem = f"{msg_status}\n\n🎯 <b>{objetivo.descricao}</b>\n{_progress_bar(percentual)} <b>{percentual:.1f}%</b>\n💰 {_format_currency(float(objetivo.valor_atual))} / {_format_currency(float(objetivo.valor_meta))}"
        await query.edit_message_text(mensagem, parse_mode="HTML")
        if acao == "confirm":
            await give_xp_for_action(query.from_user.id, "META_CHECKIN", context)
            if float(objetivo.valor_atual or 0) >= float(objetivo.valor_meta):
                await give_xp_for_action(query.from_user.id, "META_ATINGIDA", context)
    finally:
        db.close()

# --- FUNÇÃO DE BAIXA DE AGENDAMENTOS ---
async def dar_baixa_agendamento_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    agendamento_id = int(query.data.split('_')[-1])
    db = next(get_db())
    try:
        from dateutil.relativedelta import relativedelta
        ag = db.query(Agendamento).join(Usuario).filter(Agendamento.id == agendamento_id, Usuario.telegram_id == query.from_user.id).first()
        if not ag or not ag.ativo:
            await query.edit_message_text("❌ Agendamento não encontrado ou já desativado.")
            return
        novo_lancamento = Lancamento(
            id_usuario=ag.id_usuario, descricao=ag.descricao, valor=ag.valor, tipo=ag.tipo, data_transacao=datetime.now(),
            forma_pagamento="Nao_informado", id_categoria=ag.id_categoria, id_subcategoria=ag.id_subcategoria, origem="agendamento"
        )
        db.add(novo_lancamento)
        ag.parcela_atual = (ag.parcela_atual or 0) + 1
        if ag.total_parcelas and ag.parcela_atual >= ag.total_parcelas:
            ag.ativo = False
            status_msg = f"✅ <b>{ag.descricao}</b> registrado! Este foi o último evento deste agendamento."
        else:
            if ag.frequencia == 'mensal': ag.proxima_data_execucao = ag.proxima_data_execucao + relativedelta(months=1)
            elif ag.frequencia == 'semanal': ag.proxima_data_execucao = ag.proxima_data_execucao + timedelta(days=7)
            else: ag.ativo = False
            status_msg = f"✅ <b>{ag.descricao}</b> registrado!\nPróximo agendado para: {ag.proxima_data_execucao.strftime('%d/%m/%Y')}." if ag.ativo else f"✅ <b>{ag.descricao}</b> registrado!"
        db.commit()
        try: await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_TEXTO", context) 
        except Exception: pass
        await query.edit_message_text(status_msg, parse_mode='HTML')
    finally:
        db.close()
