# gerente_financeiro/gamification_service.py
import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from models import Usuario

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES DE GAMIFICAÇÃO ---

XP_ACTIONS = {
    # 📝 LANÇAMENTOS E REGISTROS
    "LANCAMENTO_MANUAL": 10,           # Registrar transação manualmente
    "LANCAMENTO_OCR": 25,             # Usar OCR para extrair dados de cupom
    "FATURA_PROCESSADA": 50,          # Processar PDF de fatura completa
    "EDICAO_LANCAMENTO": 5,           # Editar/corrigir uma transação
    "ITEM_LANCAMENTO": 3,             # Adicionar item específico
    
    # 💬 INTELIGÊNCIA E ANÁLISE  
    "PERGUNTA_IA_SIMPLES": 5,         # Pergunta básica para IA
    "PERGUNTA_IA_COMPLEXA": 15,       # Análise complexa/insights
    "CONVERSA_IA_LONGA": 25,          # Sessão longa com IA (5+ interações)
    
    # 📊 VISUALIZAÇÕES E RELATÓRIOS
    "GRAFICO_GERADO": 15,             # Gerar qualquer gráfico
    "RELATORIO_MENSAL": 30,           # Relatório mensal completo
    "RELATORIO_PERSONALIZADO": 25,    # Relatório com filtros específicos
    "DASHBOARD_ACESSADO": 8,          # Acessar dashboard web
    
    # 🎯 PLANEJAMENTO E METAS
    "META_CRIADA": 20,                # Criar nova meta financeira
    "META_APORTE_CONFIRMADO": 25,     # Confirmar aporte mensal da meta
    "META_ATINGIDA": 100,             # Atingir uma meta
    "META_SUPERADA": 150,             # Superar meta em mais de 10%
    "AGENDAMENTO_CRIADO": 15,         # Criar novo agendamento
    "AGENDAMENTO_EXECUTADO": 10,      # Agendamento executado com sucesso
    
    # ⚙️ CONFIGURAÇÕES E FERRAMENTAS
    "PERFIL_ATUALIZADO": 10,          # Atualizar dados pessoais
    "CONTA_CADASTRADA": 15,           # Cadastrar nova conta/cartão
    "CATEGORIA_PERSONALIZADA": 8,     # Criar categoria personalizada
    "BACKUP_DADOS": 20,               # Fazer backup dos dados
    "CONFIGURACAO_ALTERADA": 5,      # Alterar configurações do bot
    
    # 🎮 SISTEMA SOCIAL E GAMIFICAÇÃO
    "RANKING_VISUALIZADO": 3,         # Ver ranking global
    "INTERACAO_BOT": 2,               # Interacao geral com o bot (com cooldown)
    "PERFIL_COMPARTILHADO": 10,       # Compartilhar perfil (futuro)
    "CONQUISTA_DESBLOQUEADA": 25,     # Desbloquear nova conquista
    "PRIMEIRA_INTERACAO_DIA": 15,     # Primeira interação do dia (streak)
    "SEQUENCIA_MANTIDA": 5,           # Manter sequência diária
    
    # 🔥 BÔNUS ESPECIAIS
    "USUARIO_NOVO": 50,               # Bônus de boas-vindas
    "PRIMEIRA_SEMANA": 100,           # Completar primeira semana
    "PRIMEIRO_MES": 250,              # Completar primeiro mês
    "FEEDBACK_DADO": 20,              # Dar feedback sobre o bot
    "BUG_REPORTADO": 30,              # Reportar bug útil
    "SUGESTAO_ACEITA": 50,            # Sugestão implementada
}

LEVELS = {
    1: {"xp_necessario": 0, "titulo": "Novato Financeiro", "multiplicador": 1.0},
    2: {"xp_necessario": 300, "titulo": "Aprendiz Organizado", "multiplicador": 1.1},
    3: {"xp_necessario": 800, "titulo": "Economista Iniciante", "multiplicador": 1.2},
    4: {"xp_necessario": 1500, "titulo": "Controlador Experiente", "multiplicador": 1.3},
    5: {"xp_necessario": 2500, "titulo": "Especialista Financeiro", "multiplicador": 1.4},
    6: {"xp_necessario": 4000, "titulo": "Mestre das Finanças", "multiplicador": 1.5},
    7: {"xp_necessario": 6000, "titulo": "Guru dos Investimentos", "multiplicador": 1.6},
    8: {"xp_necessario": 9000, "titulo": "Lenda do Controle", "multiplicador": 1.7},
    9: {"xp_necessario": 13000, "titulo": "Imperador Financeiro", "multiplicador": 1.8},
    10: {"xp_necessario": 18000, "titulo": "ContaComigo Supremo", "multiplicador": 2.0},
}

STREAK_BONUS = {
    3: 100,
    7: 200,
    30: 500,
}

async def award_xp(db: Session, user_id: int, action: str, context, custom_amount: int = None) -> dict:
    """
    Concede XP a um usuário com multiplicadores de nível e streak.
    
    Returns:
        dict: {"xp_gained": int, "level_up": bool, "new_level": int, "streak_bonus": int}
    """
    base_xp = custom_amount or XP_ACTIONS.get(action, 0)
    if base_xp == 0:
        return {"xp_gained": 0, "level_up": False, "new_level": 0, "streak_bonus": 0}

    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return {"xp_gained": 0, "level_up": False, "new_level": 0, "streak_bonus": 0}

    # 🎯 APLICAR MULTIPLICADORES
    level_info = LEVELS.get(usuario.level, {"multiplicador": 1.0})
    level_multiplier = level_info.get("multiplicador", 1.0)
    
    # 🔥 MULTIPLICADOR DE STREAK
    streak_multiplier = 1.0
    if usuario.streak_dias >= 30:
        streak_multiplier = 2.0  # +100% XP
    elif usuario.streak_dias >= 14:
        streak_multiplier = 1.5  # +50% XP
    elif usuario.streak_dias >= 7:
        streak_multiplier = 1.25 # +25% XP
    
    # 🧮 CALCULAR XP FINAL
    final_xp = int(base_xp * level_multiplier * streak_multiplier)
    streak_bonus = final_xp - int(base_xp * level_multiplier) if streak_multiplier > 1.0 else 0
    
    # 💰 APLICAR XP
    old_xp = usuario.xp
    usuario.xp += final_xp
    
    # 📊 VERIFICAR LEVEL UP
    old_level = usuario.level
    new_level = old_level
    level_up = False
    
    # Verificar se subiu múltiplos níveis
    while new_level < 10:  # Máximo nível 10
        next_level_info = LEVELS.get(new_level + 1)
        if next_level_info and usuario.xp >= next_level_info["xp_necessario"]:
            new_level += 1
            level_up = True
        else:
            break
    
    usuario.level = new_level
    db.commit()
    
    # 📢 NOTIFICAÇÃO DE XP
    action_names = {
        "LANCAMENTO_MANUAL": "registrar transação",
        "LANCAMENTO_OCR": "usar OCR automático",
        "FATURA_PROCESSADA": "processar fatura completa",
        "PERGUNTA_IA_SIMPLES": "usar IA do Gerente",
        "PERGUNTA_IA_COMPLEXA": "análise avançada com IA",
        "GRAFICO_GERADO": "gerar gráfico",
        "RELATORIO_MENSAL": "gerar relatório",
        "META_CRIADA": "criar meta financeira",
        "META_ATINGIDA": "atingir sua meta",
        "AGENDAMENTO_CRIADO": "criar agendamento",
        "DASHBOARD_ACESSADO": "acessar dashboard",
        "PRIMEIRA_INTERACAO_DIA": "manter sequência diária"
    }
    
    action_display = action_names.get(action, action.lower().replace("_", " "))
    
    # 🎉 NOTIFICAÇÃO DETALHADA
    notification = f"⭐ +{final_xp} XP por {action_display}!"
    
    if level_multiplier > 1.0:
        notification += f"\n🏆 +{int((level_multiplier - 1) * 100)}% bonus de nível!"
    
    if streak_bonus > 0:
        notification += f"\n🔥 +{streak_bonus} XP bonus de streak ({usuario.streak_dias} dias)!"
    
    # Enviar notificação de XP (silenciosa)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=notification,
            disable_notification=True  # Notificação silenciosa
        )
    except:
        pass  # Falha silenciosa se não conseguir enviar
    
    # 🎉 NOTIFICAÇÃO DE LEVEL UP (com som)
    if level_up:
        level_info = LEVELS.get(new_level, {"titulo": "Champion"})
        mensagem_levelup = (
            f"🎉🚀 **LEVEL UP!** 🚀🎉\n\n"
            f"**PARABÉNS!** Você alcançou o **Nível {new_level}**!\n"
            f"🏅 Agora você é um(a) **{level_info['titulo']}**!\n\n"
            f"💫 **Novos benefícios desbloqueados:**\n"
            f"⚡ +{int((level_info.get('multiplicador', 1.0) - 1) * 100)}% XP em todas as ações!\n"
            f"🎯 Acesso a funcionalidades exclusivas!\n\n"
            f"🔥 **Continue dominando suas finanças!**"
        )
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=mensagem_levelup,
                parse_mode='Markdown'
            )
        except:
            pass
    
    logger.info(f"XP concedido: Usuário {user_id} | Ação: {action} | XP: +{final_xp} | Level: {old_level}->{new_level}")
    
    return {
        "xp_gained": final_xp,
        "level_up": level_up,
        "new_level": new_level,
        "streak_bonus": streak_bonus,
        "old_xp": old_xp,
        "new_xp": usuario.xp
    }

async def check_and_update_streak(db: Session, user_id: int, context) -> None:
    """
    Verifica e atualiza a sequência de logins diários do usuário.
    """
    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return

    hoje = date.today()
    ultimo_login = usuario.ultimo_login

    if ultimo_login == hoje: # Já fez login hoje
        return

    # Conceder XP pela primeira interação do dia
    await award_xp(db, user_id, "PRIMEIRA_INTERACAO_DIA", context)

    if ultimo_login == hoje - timedelta(days=1): # Continua a sequência
        usuario.streak_dias += 1
        bonus = STREAK_BONUS.get(usuario.streak_dias)
        if bonus:
            usuario.xp += bonus
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔥 **SEQUÊNCIA DE {usuario.streak_dias} DIAS!**\n\nVocê ganhou +{bonus} XP de bônus por sua consistência! Continue assim!",
                parse_mode='Markdown'
            )
    else: # Quebrou a sequência
        usuario.streak_dias = 1
    
    usuario.ultimo_login = hoje
    db.commit()