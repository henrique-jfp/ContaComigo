"""
🎯 Wishlist Inteligente - MaestroFin
====================================

Sistema avançado de planejamento de compras/objetivos com análise de viabilidade,
sugestões de economia e priorização automática.

Substitui o sistema de metas antigo (/novameta, /metas) por um sistema mais inteligente
que não apenas define o objetivo, mas ENSINA COMO atingi-lo.

Autor: Henrique Freitas
Data: 18/11/2025
Versão: 3.3.0
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, extract, desc
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, 
    CallbackQueryHandler, MessageHandler, filters
)

from database.database import get_db, get_or_create_user
from models import Usuario, Lancamento, Objetivo, Categoria

logger = logging.getLogger(__name__)

# Estados da conversa
(
    ASK_WISHLIST_ITEM,
    ASK_WISHLIST_VALOR,
    ASK_WISHLIST_PRAZO,
    ESCOLHER_OPCAO_VIABILIDADE
) = range(4)


# ============================================================================
# ANÁLISE DE VIABILIDADE E SUGESTÕES
# ============================================================================

def calcular_poupanca_media(usuario_id: int, meses: int = 3) -> float:
    """Calcula a média de poupança mensal do usuário"""
    db = next(get_db())
    try:
        hoje = datetime.now()
        data_inicio = hoje - timedelta(days=meses * 30)
        
        economia_total = 0
        meses_com_dados = 0
        
        for i in range(meses):
            mes_ref = hoje - timedelta(days=i * 30)
            
            receitas = db.query(func.sum(Lancamento.valor)).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo == 'Entrada',
                    extract('year', Lancamento.data_transacao) == mes_ref.year,
                    extract('month', Lancamento.data_transacao) == mes_ref.month
                )
            ).scalar() or 0
            
            despesas = db.query(func.sum(Lancamento.valor)).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo == 'Saída',
                    extract('year', Lancamento.data_transacao) == mes_ref.year,
                    extract('month', Lancamento.data_transacao) == mes_ref.month
                )
            ).scalar() or 0
            
            if receitas > 0:
                economia_total += (float(receitas) - float(despesas))
                meses_com_dados += 1
        
        return economia_total / meses_com_dados if meses_com_dados > 0 else 0
    finally:
        db.close()


def analisar_categorias_cortaveis(usuario_id: int) -> List[Dict]:
    """Identifica categorias onde o usuário pode economizar"""
    db = next(get_db())
    try:
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year
        
        # Categorias não essenciais (que podem ser reduzidas)
        categorias_cortaveis = [
            'Delivery', 'Restaurante', 'Lazer', 'Entretenimento',
            'Assinaturas', 'Streaming', 'Shopping', 'Eletrônicos'
        ]
        
        sugestoes = []
        
        for nome_cat in categorias_cortaveis:
            gasto_mes = db.query(func.sum(Lancamento.valor)).join(
                Categoria, Lancamento.id_categoria == Categoria.id
            ).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo == 'Saída',
                    Categoria.nome.ilike(f'%{nome_cat}%'),
                    extract('year', Lancamento.data_transacao) == ano_atual,
                    extract('month', Lancamento.data_transacao) == mes_atual
                )
            ).scalar() or 0
            
            if gasto_mes > 0:
                gasto_mes = float(gasto_mes)
                # Sugerir redução de 30-50%
                economia_30 = gasto_mes * 0.3
                economia_50 = gasto_mes * 0.5
                
                sugestoes.append({
                    'categoria': nome_cat,
                    'gasto_atual': gasto_mes,
                    'reducao_30': economia_30,
                    'reducao_50': economia_50
                })
        
        # Ordenar por potencial de economia (maior primeiro)
        sugestoes.sort(key=lambda x: x['reducao_50'], reverse=True)
        
        return sugestoes[:5]  # Top 5
    finally:
        db.close()


def gerar_plano_viabilidade(
    usuario_id: int,
    valor_desejado: float,
    prazo_meses: int
) -> Dict:
    """
    Gera análise completa de viabilidade e opções para atingir o objetivo
    """
    poupanca_atual = calcular_poupanca_media(usuario_id, meses=3)
    necessario_por_mes = valor_desejado / prazo_meses if prazo_meses > 0 else valor_desejado
    
    # Verificar viabilidade
    deficit = necessario_por_mes - poupanca_atual
    viavel = deficit <= 0
    
    # Buscar oportunidades de economia
    categorias_cortaveis = analisar_categorias_cortaveis(usuario_id)
    
    # Calcular economia potencial
    economia_potencial_30 = sum(c['reducao_30'] for c in categorias_cortaveis)
    economia_potencial_50 = sum(c['reducao_50'] for c in categorias_cortaveis)
    
    # Gerar opções
    opcoes = []
    
    # Opção 1: Cortar gastos (se viável)
    if economia_potencial_30 >= deficit:
        opcoes.append({
            'tipo': 'cortar_gastos',
            'nome': 'Cortar gastos (redução moderada 30%)',
            'viavel': True,
            'descricao': f'Reduzindo 30% em {len(categorias_cortaveis)} categorias',
            'economia_mensal': economia_potencial_30,
            'categorias': categorias_cortaveis,
            'percentual_reducao': 30
        })
    
    if economia_potencial_50 >= deficit:
        opcoes.append({
            'tipo': 'cortar_gastos_agressivo',
            'nome': 'Cortar gastos (redução agressiva 50%)',
            'viavel': True,
            'descricao': f'Reduzindo 50% em {len(categorias_cortaveis)} categorias',
            'economia_mensal': economia_potencial_50,
            'categorias': categorias_cortaveis,
            'percentual_reducao': 50
        })
    
    # Opção 2: Estender prazo
    prazo_alternativo = int((valor_desejado / (poupanca_atual + economia_potencial_30)) if (poupanca_atual + economia_potencial_30) > 0 else 999)
    if prazo_alternativo < 99:
        opcoes.append({
            'tipo': 'estender_prazo',
            'nome': f'Estender prazo para {prazo_alternativo} meses',
            'viavel': True,
            'descricao': f'Com economia leve (30%), atingível em {prazo_alternativo} meses',
            'prazo_meses': prazo_alternativo,
            'economia_mensal_necessaria': valor_desejado / prazo_alternativo
        })
    
    # Opção 3: Aumentar receita
    receita_extra_necessaria = deficit - economia_potencial_30 if deficit > economia_potencial_30 else 0
    if receita_extra_necessaria > 0:
        opcoes.append({
            'tipo': 'aumentar_receita',
            'nome': f'Aumentar receita em R$ {receita_extra_necessaria:.2f}/mês',
            'viavel': None,  # Depende do usuário
            'descricao': 'Freelance, trabalhos extras ou venda de itens',
            'receita_extra': receita_extra_necessaria
        })
    
    return {
        'viavel_sem_mudancas': viavel,
        'poupanca_atual': poupanca_atual,
        'necessario_por_mes': necessario_por_mes,
        'deficit': deficit if deficit > 0 else 0,
        'opcoes': opcoes,
        'categorias_cortaveis': categorias_cortaveis
    }


# ============================================================================
# HANDLERS DA CONVERSA
# ============================================================================

async def wishlist_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia a conversa de wishlist"""
    await update.message.reply_html(
        "🎯 <b>Lista de Desejos Inteligente</b>\n\n"
        "Vou te ajudar a planejar sua próxima conquista!\n\n"
        "💡 <b>Qual é o seu próximo sonho financeiro?</b>\n"
        "<i>(ex: Notebook novo, Viagem para Europa, Carro)</i>"
    )
    return ASK_WISHLIST_ITEM


async def ask_wishlist_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o nome do item e pergunta o valor"""
    context.user_data['wishlist_item'] = update.message.text
    
    await update.message.reply_html(
        f"💰 <b>Quanto custa: {update.message.text}?</b>\n\n"
        "Digite o valor aproximado:\n"
        "<i>(ex: 4500 ou 4500.00)</i>"
    )
    return ASK_WISHLIST_VALOR


async def ask_wishlist_prazo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o valor e pergunta o prazo"""
    try:
        valor = float(update.message.text.replace(',', '.').replace('R$', '').strip())
        context.user_data['wishlist_valor'] = valor
        
        await update.message.reply_html(
            f"📅 <b>Em quanto tempo quer conseguir?</b>\n\n"
            "Digite o número de meses:\n"
            "<i>(ex: 6 para 6 meses, 12 para 1 ano)</i>"
        )
        return ASK_WISHLIST_PRAZO
    except ValueError:
        await update.message.reply_text(
            "❌ Valor inválido! Digite apenas números (ex: 4500)"
        )
        return ASK_WISHLIST_VALOR


async def analisar_e_apresentar_opcoes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Analisa viabilidade e apresenta opções ao usuário"""
    try:
        prazo_meses = int(update.message.text.strip())
        if prazo_meses <= 0:
            await update.message.reply_text(
                "❌ O prazo deve ser maior que zero! Digite novamente:"
            )
            return ASK_WISHLIST_PRAZO
        
        context.user_data['wishlist_prazo'] = prazo_meses
        
        # Buscar dados do usuário
        user = update.effective_user
        db = next(get_db())
        try:
            usuario_db = get_or_create_user(db, user.id, user.full_name)
            
            item = context.user_data['wishlist_item']
            valor = context.user_data['wishlist_valor']
            
            await update.message.reply_text(
                "🤖 Analisando sua situação financeira...\n"
                "Isso pode levar alguns segundos... ⏳"
            )
            
            # Gerar análise de viabilidade
            analise = gerar_plano_viabilidade(usuario_db.id, valor, prazo_meses)
            
            # Salvar análise no contexto
            context.user_data['analise_viabilidade'] = analise
            
            # Formatar mensagem
            mensagem = f"""
🎯 <b>Análise: {item}</b>
💰 Valor: R$ {valor:,.2f}
📅 Prazo desejado: {prazo_meses} meses

━━━━━━━━━━━━━━━━━━━━
📊 <b>SITUAÇÃO ATUAL</b>
━━━━━━━━━━━━━━━━━━━━

💵 Sua poupança média: <code>R$ {analise['poupanca_atual']:.2f}/mês</code>
💡 Você precisa economizar: <code>R$ {analise['necessario_por_mes']:.2f}/mês</code>

"""
            
            if analise['viavel_sem_mudancas']:
                mensagem += "✅ <b>BOA NOTÍCIA!</b> Sua meta é viável sem mudanças! 🎉\n\n"
            else:
                deficit = analise['deficit']
                mensagem += f"⚠️ <b>ATENÇÃO:</b> Faltam <b>R$ {deficit:.2f}/mês</b> para atingir sua meta.\n\n"
            
            # Apresentar opções
            if analise['opcoes']:
                mensagem += "━━━━━━━━━━━━━━━━━━━━\n"
                mensagem += "💡 <b>COMO VIABILIZAR:</b>\n"
                mensagem += "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                keyboard = []
                for idx, opcao in enumerate(analise['opcoes'][:3], 1):  # Máximo 3 opções
                    emoji = "✅" if opcao['viavel'] else "⚠️"
                    mensagem += f"<b>Opção {idx}️⃣:</b> {opcao['nome']}\n"
                    mensagem += f"   {opcao['descricao']}\n\n"
                    
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{emoji} Opção {idx}: {opcao['nome'][:30]}...",
                            callback_data=f"wishlist_opcao_{idx}"
                        )
                    ])
                
                keyboard.append([
                    InlineKeyboardButton("❌ Cancelar", callback_data="wishlist_cancelar")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_html(
                    mensagem + "\n<b>Escolha uma opção para ver os detalhes:</b>",
                    reply_markup=reply_markup
                )
                
                return ESCOLHER_OPCAO_VIABILIDADE
            else:
                await update.message.reply_html(
                    mensagem + "\n❌ Não consegui encontrar opções viáveis no momento.\n"
                    "Tente aumentar o prazo ou o valor."
                )
                context.user_data.clear()
                return ConversationHandler.END
                
        finally:
            db.close()
            
    except ValueError:
        await update.message.reply_text(
            "❌ Valor inválido! Digite apenas o número de meses (ex: 6)"
        )
        return ASK_WISHLIST_PRAZO


async def processar_opcao_escolhida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a opção escolhida e cria a meta"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "wishlist_cancelar":
        await query.edit_message_text("❌ Operação cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Extrair número da opção
    opcao_idx = int(query.data.split('_')[-1]) - 1
    
    analise = context.user_data.get('analise_viabilidade')
    if not analise or opcao_idx >= len(analise['opcoes']):
        await query.edit_message_text("❌ Erro: opção inválida.")
        context.user_data.clear()
        return ConversationHandler.END
    
    opcao = analise['opcoes'][opcao_idx]
    item = context.user_data['wishlist_item']
    valor = context.user_data['wishlist_valor']
    prazo_original = context.user_data['wishlist_prazo']
    
    # Ajustar prazo se necessário
    if opcao['tipo'] == 'estender_prazo':
        prazo_final = opcao['prazo_meses']
    else:
        prazo_final = prazo_original
    
    # Criar meta no banco de dados
    user = query.from_user
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        from database.database import criar_novo_objetivo
        data_meta = datetime.now() + timedelta(days=prazo_final * 30)
        
        resultado = criar_novo_objetivo(
            usuario_db.telegram_id,
            item,
            valor,
            data_meta.date()
        )
        
        if isinstance(resultado, Objetivo):
            # Gerar plano de ação detalhado
            mensagem_final = f"""
✅ <b>Meta criada com sucesso!</b>

🎯 <b>{item}</b>
💰 Valor: R$ {valor:,.2f}
📅 Prazo: {prazo_final} meses
💵 Economize: R$ {valor/prazo_final:.2f}/mês

━━━━━━━━━━━━━━━━━━━━
📋 <b>SEU PLANO DE AÇÃO:</b>
━━━━━━━━━━━━━━━━━━━━

"""
            
            if opcao['tipo'] in ['cortar_gastos', 'cortar_gastos_agressivo']:
                mensagem_final += f"<b>Estratégia:</b> Reduzir gastos em {opcao['percentual_reducao']}%\n\n"
                mensagem_final += "<b>Onde cortar:</b>\n"
                for cat in opcao['categorias'][:3]:
                    reducao = cat[f'reducao_{opcao["percentual_reducao"]}']
                    mensagem_final += f"  • {cat['categoria']}: -R$ {reducao:.2f}/mês\n"
                
                mensagem_final += f"\n💰 <b>Total economizado:</b> R$ {opcao['economia_mensal']:.2f}/mês\n"
                
            elif opcao['tipo'] == 'estender_prazo':
                mensagem_final += f"<b>Estratégia:</b> Prazo estendido\n"
                mensagem_final += f"Com economia moderada, você atinge em {prazo_final} meses!\n"
                
            elif opcao['tipo'] == 'aumentar_receita':
                mensagem_final += f"<b>Estratégia:</b> Aumentar receita\n"
                mensagem_final += f"Busque R$ {opcao['receita_extra']:.2f}/mês em:\n"
                mensagem_final += "  • Freelances\n"
                mensagem_final += "  • Trabalhos extras\n"
                mensagem_final += "  • Venda de itens não usados\n"
            
            mensagem_final += "\n━━━━━━━━━━━━━━━━━━━━\n"
            mensagem_final += "💡 Use /metas para acompanhar seu progresso!\n"
            mensagem_final += "🎮 Cada aporte te dá +25 XP!"
            
            await query.edit_message_text(mensagem_final, parse_mode='HTML')
            
        else:
            await query.edit_message_text(
                f"❌ Erro ao criar meta: {resultado}"
            )
    
    except Exception as e:
        logger.error(f"❌ Erro ao processar opção wishlist: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Erro ao criar meta. Tente novamente mais tarde."
        )
    finally:
        db.close()
        context.user_data.clear()
    
    return ConversationHandler.END


async def cancel_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a conversa de wishlist"""
    await update.message.reply_text("❌ Operação cancelada.")
    context.user_data.clear()
    return ConversationHandler.END


# ============================================================================
# LISTA DE METAS (SUBSTITUINDO /metas ANTIGO)
# ============================================================================

async def listar_wishlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /metas - Lista todas as metas/desejos do usuário
    (Mantém o nome /metas por compatibilidade, mas agora usa lógica da wishlist)
    """
    user = update.effective_user
    db = next(get_db())
    
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        from database.database import listar_objetivos_usuario
        objetivos = listar_objetivos_usuario(usuario_db.telegram_id)
        
        if not objetivos:
            await update.message.reply_html(
                "📋 <b>Sua Wishlist está vazia!</b>\n\n"
                "Que tal adicionar seu primeiro desejo?\n"
                "Use /wishlist para começar! 🎯"
            )
            return
        
        await update.message.reply_html("🎯 <b>Sua Wishlist:</b>")
        
        for obj in objetivos:
            progresso = (float(obj.valor_atual) / float(obj.valor_meta)) * 100 if obj.valor_meta > 0 else 0
            blocos_cheios = int(progresso // 10)
            barra = "🟩" * blocos_cheios + "⬜" * (10 - blocos_cheios)
            
            # Calcular quanto falta
            falta = float(obj.valor_meta) - float(obj.valor_atual)
            
            # Calcular dias restantes
            hoje = datetime.now().date()
            dias_restantes = (obj.data_meta - hoje).days
            meses_restantes = max(1, dias_restantes // 30)
            
            # Quanto precisa economizar por mês
            necessario_mes = falta / meses_restantes if meses_restantes > 0 else falta
            
            mensagem = f"""
🎯 <b>{obj.descricao}</b>

💰 Progresso: <code>R$ {obj.valor_atual:.2f} / R$ {obj.valor_meta:.2f}</code>
{barra} {progresso:.1f}%

🎯 Faltam: <b>R$ {falta:.2f}</b>
📅 Prazo: {obj.data_meta.strftime('%d/%m/%Y')} ({dias_restantes} dias)
💵 Economize: <b>R$ {necessario_mes:.2f}/mês</b>
"""
            
            if progresso >= 100:
                mensagem += "\n🎉 <b>META ATINGIDA! PARABÉNS!</b> 🎉"
            elif dias_restantes < 0:
                mensagem += "\n⚠️ <b>Prazo vencido</b>"
            elif dias_restantes < 30:
                mensagem += "\n⏰ <b>Prazo próximo!</b> Acelere os aportes!"
            
            keyboard = [[
                InlineKeyboardButton("💰 Fazer Aporte", callback_data=f"aporte_meta_{obj.id}"),
                InlineKeyboardButton("🗑️ Remover", callback_data=f"deletar_meta_{obj.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(mensagem, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"❌ Erro ao listar wishlist: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Erro ao carregar suas metas. Tente novamente mais tarde."
        )
    finally:
        db.close()


# ============================================================================
# CALLBACK HANDLERS (APORTE E DELEÇÃO)
# ============================================================================

async def deletar_meta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para deletar uma meta"""
    query = update.callback_query
    await query.answer()
    
    try:
        meta_id = int(query.data.split('_')[-1])
        db = next(get_db())
        
        try:
            objetivo = db.query(Objetivo).filter(Objetivo.id == meta_id).first()
            
            if objetivo:
                nome_meta = objetivo.descricao
                db.delete(objetivo)
                db.commit()
                
                await query.edit_message_text(
                    f"✅ Meta '{nome_meta}' removida com sucesso!"
                )
            else:
                await query.edit_message_text("❌ Meta não encontrada.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erro ao deletar meta: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Erro ao remover meta. Tente novamente."
        )


# ============================================================================
# CONVERSATION HANDLER
# ============================================================================

wishlist_conv = ConversationHandler(
    entry_points=[CommandHandler('wishlist', wishlist_start)],
    states={
        ASK_WISHLIST_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wishlist_valor)],
        ASK_WISHLIST_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wishlist_prazo)],
        ASK_WISHLIST_PRAZO: [MessageHandler(filters.TEXT & ~filters.COMMAND, analisar_e_apresentar_opcoes)],
        ESCOLHER_OPCAO_VIABILIDADE: [CallbackQueryHandler(processar_opcao_escolhida, pattern='^wishlist_')],
    },
    fallbacks=[
        CommandHandler(['cancelar', 'cancel', 'sair', 'parar'], cancel_wishlist),
        MessageHandler(filters.Regex(r'(?i)^/?\s*(cancelar|cancel|sair|parar)$'), cancel_wishlist)
    ],
    per_message=False,
    per_user=True,
    per_chat=True
)
