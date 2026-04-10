# models.py
# models.py
from datetime import datetime, timezone, time
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey, BigInteger, Boolean, Date, Time, JSON, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    nome_completo = Column(String, nullable=True)
    perfil_investidor = Column(String, nullable=True)
    horario_notificacao = Column(Time, default=time(hour=9, minute=0))
    email_notificacao = Column(String, nullable=True)
    alerta_gastos_ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    pierre_api_key = Column(String, nullable=True)  # Feature Secreta: Open Finance

    # --- CAMPOS DE GAMIFICAÇÃO ---
    perfil_ia = Column(String, nullable=True)
    data_ultima_analise_perfil = Column(DateTime, nullable=True)
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    streak_dias = Column(Integer, default=0, nullable=False)
    ultimo_login = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    plan = Column(String(20), default='trial', nullable=False)
    trial_expires_at = Column(DateTime, nullable=True)
    premium_expires_at = Column(DateTime, nullable=True)
    subscription_id = Column(String(100), nullable=True)
    
    lancamentos = relationship("Lancamento", back_populates="usuario", cascade="all, delete-orphan")
    contas = relationship("Conta", back_populates="usuario", cascade="all, delete-orphan")
    objetivos = relationship("Objetivo", back_populates="usuario", cascade="all, delete-orphan")
    agendamentos = relationship("Agendamento", back_populates="usuario", cascade="all, delete-orphan")
    conquistas = relationship("ConquistaUsuario", back_populates="usuario", cascade="all, delete-orphan")
    investments = relationship("Investment", back_populates="usuario", cascade="all, delete-orphan")
    investment_goals = relationship("InvestmentGoal", back_populates="usuario", cascade="all, delete-orphan")
    patrimony_snapshots = relationship("PatrimonySnapshot", back_populates="usuario", cascade="all, delete-orphan")
    xp_events = relationship("XpEvent", back_populates="usuario", cascade="all, delete-orphan")
    xp_daily_counters = relationship("XpDailyCounter", back_populates="usuario", cascade="all, delete-orphan")
    monthly_gamification_awards = relationship("MonthlyGamificationAward", back_populates="usuario", cascade="all, delete-orphan")
    plan_usage_monthly = relationship("UserPlanUsageMonthly", back_populates="usuario", cascade="all, delete-orphan")
    saldos_conta = relationship("SaldoConta", back_populates="usuario", cascade="all, delete-orphan")
    faturas_cartao = relationship("FaturaCartao", back_populates="usuario", cascade="all, delete-orphan")
    parcelamentos_item = relationship("ParcelamentoItem", back_populates="usuario", cascade="all, delete-orphan")


class UserPlanUsageMonthly(Base):
    __tablename__ = 'user_plan_usage_monthly'
    __table_args__ = (
        UniqueConstraint('id_usuario', 'ano', 'mes', name='uq_user_plan_usage_monthly_user_period'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    ano = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False, index=True)
    lancamentos_count = Column(Integer, default=0, nullable=False)
    ocr_count = Column(Integer, default=0, nullable=False)
    ia_questions_count = Column(Integer, default=0, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    usuario = relationship("Usuario", back_populates="plan_usage_monthly")

class Conquista(Base):
    __tablename__ = 'conquistas'
    id = Column(String, primary_key=True) # Ex: 'primeiro_passo', 'fotografo'
    nome = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    xp_recompensa = Column(Integer, nullable=False)

class ConquistaUsuario(Base):
    __tablename__ = 'conquistas_usuario'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    id_conquista = Column(String, ForeignKey('conquistas.id'), nullable=False)
    data_conquista = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="conquistas")
    conquista = relationship("Conquista")


class Objetivo(Base):
    __tablename__ = 'objetivos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    descricao = Column(String, nullable=False)
    valor_meta = Column(Numeric(12, 2), nullable=False)
    valor_atual = Column(Numeric(12, 2), default=0.0)
    data_meta = Column(Date, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="objetivos")
    confirmacoes = relationship("MetaConfirmacao", back_populates="objetivo", cascade="all, delete-orphan")


class MetaConfirmacao(Base):
    __tablename__ = 'metas_confirmacoes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False, index=True)
    id_objetivo = Column(Integer, ForeignKey('objetivos.id'), nullable=False, index=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    valor_confirmado = Column(Numeric(12, 2), nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario")
    objetivo = relationship("Objetivo", back_populates="confirmacoes")

# --- TABELA DE CONTAS REFORMULADA ---
class Conta(Base):
    __tablename__ = 'contas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    nome = Column(String, nullable=False) # Ex: "Nubank", "Inter Gold"
    tipo = Column(String, nullable=False) # "Conta Corrente", "Cartão de Crédito", "Carteira Digital", "Outro"
    external_id = Column(String, unique=True, nullable=True) # ID Único da API Open Finance
    
    # Campos específicos para Cartão de Crédito
    dia_fechamento = Column(Integer, nullable=True)
    dia_vencimento = Column(Integer, nullable=True)
    limite_cartao = Column(Numeric(12, 2), nullable=True)
    email_notificacao = Column(String, nullable=True)
    
    usuario = relationship("Usuario", back_populates="contas")
    lancamentos = relationship("Lancamento", back_populates="conta", cascade="all, delete-orphan")
    saldos = relationship("SaldoConta", back_populates="conta", cascade="all, delete-orphan")
    faturas = relationship("FaturaCartao", back_populates="conta", cascade="all, delete-orphan")
    parcelamentos = relationship("ParcelamentoItem", back_populates="conta", cascade="all, delete-orphan")

class Categoria(Base):
    __tablename__ = 'categorias'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, unique=True, nullable=False)
    
    subcategorias = relationship("Subcategoria", back_populates="categoria", cascade="all, delete-orphan")
    lancamentos = relationship("Lancamento", back_populates="categoria")

class Subcategoria(Base):
    __tablename__ = 'subcategorias'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False)
    id_categoria = Column(Integer, ForeignKey('categorias.id'), nullable=False)
    
    categoria = relationship("Categoria", back_populates="subcategorias")
    lancamentos = relationship("Lancamento", back_populates="subcategoria")

class Lancamento(Base):
    __tablename__ = 'lancamentos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    descricao = Column(String)
    valor = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String, nullable=False)
    data_transacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Zero setup: forma de pagamento simplificada e obrigatória.
    forma_pagamento = Column(String, nullable=False, default="Nao_informado")
    origem = Column(String, nullable=True)  # manual, texto, audio, ocr, miniapp, open_finance
    documento_fiscal = Column(String, nullable=True)
    external_id = Column(String, unique=True, nullable=True) # ID Único da API Open Finance
    
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    id_categoria = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    id_subcategoria = Column(Integer, ForeignKey('subcategorias.id'), nullable=True)
    id_conta = Column(Integer, ForeignKey('contas.id'), nullable=True)
    
    usuario = relationship("Usuario", back_populates="lancamentos")
    categoria = relationship("Categoria", back_populates="lancamentos")
    subcategoria = relationship("Subcategoria", back_populates="lancamentos")
    conta = relationship("Conta", back_populates="lancamentos")
    itens = relationship("ItemLancamento", back_populates="lancamento", cascade="all, delete-orphan")

class ItemLancamento(Base):
    __tablename__ = 'itens_lancamento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_lancamento = Column(Integer, ForeignKey('lancamentos.id'), nullable=False)
    nome_item = Column(String, nullable=False)
    quantidade = Column(Numeric(10, 3))
    valor_unitario = Column(Numeric(10, 2))
    
    lancamento = relationship("Lancamento", back_populates="itens")

class Agendamento(Base):
    __tablename__ = 'agendamentos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    descricao = Column(String, nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    tipo = Column(String, nullable=False)
    
    id_categoria = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    id_subcategoria = Column(Integer, ForeignKey('subcategorias.id'), nullable=True)
    
    data_primeiro_evento = Column(Date, nullable=False)
    frequencia = Column(String, nullable=False)
    
    total_parcelas = Column(Integer, nullable=True)
    parcela_atual = Column(Integer, default=0)
    
    proxima_data_execucao = Column(Date, nullable=False, index=True)
    ativo = Column(Boolean, default=True, index=True)
    
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="agendamentos")
    categoria = relationship("Categoria")
    subcategoria = relationship("Subcategoria")

class OrcamentoCategoria(Base):
    __tablename__ = 'orcamentos_categoria'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    id_categoria = Column(Integer, ForeignKey('categorias.id', ondelete='CASCADE'), nullable=False)
    valor_limite = Column(Numeric(12, 2), nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario")
    categoria = relationship("Categoria")

# ==================== MODELS DE INVESTIMENTOS ====================


class Investment(Base):
    """Investimentos do usuário"""
    __tablename__ = 'investments'
    
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    # id_account removido
    
    # Informações básicas
    nome = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False)  # CDB, LCI, LCA, POUPANCA, TESOURO, ACAO, FUNDO, COFRINHO, OUTRO
    banco = Column(String(255))
    
    # Valores
    valor_inicial = Column(Numeric(15, 2), default=0)
    valor_atual = Column(Numeric(15, 2), nullable=False)
    
    # Rentabilidade
    taxa_contratada = Column(Numeric(5, 4))  # Ex: 100% CDI = 1.0000
    indexador = Column(String(50))  # CDI, IPCA, SELIC, PREFIXADO
    data_aplicacao = Column(Date)
    data_vencimento = Column(Date)
    
    # Controle
    ativo = Column(Boolean, default=True)
    fonte = Column(String(50), default='MANUAL')  # MANUAL
    
    # Metadata
    observacoes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="investments")
    snapshots = relationship("InvestmentSnapshot", back_populates="investment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Investment(id={self.id}, nome={self.nome}, valor=R${self.valor_atual})>"


class InvestmentSnapshot(Base):
    """Histórico de valores dos investimentos"""
    __tablename__ = 'investment_snapshots'
    
    id = Column(Integer, primary_key=True, index=True)
    id_investment = Column(Integer, ForeignKey('investments.id', ondelete='CASCADE'), nullable=False)
    
    # Valores no momento do snapshot
    valor = Column(Numeric(15, 2), nullable=False)
    rentabilidade_periodo = Column(Numeric(15, 2))  # Quanto rendeu desde último snapshot
    rentabilidade_percentual = Column(Numeric(5, 2))  # % de rendimento
    
    # Comparações
    cdi_periodo = Column(Numeric(5, 4))  # CDI acumulado no período
    ipca_periodo = Column(Numeric(5, 4))  # IPCA acumulado no período
    
    # Metadata
    data_snapshot = Column(Date, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    investment = relationship("Investment", back_populates="snapshots")
    
    def __repr__(self):
        return f"<InvestmentSnapshot(investment={self.id_investment}, data={self.data_snapshot}, valor=R${self.valor})>"


class InvestmentGoal(Base):
    """Metas de investimento"""
    __tablename__ = 'investment_goals'
    
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    
    # Meta
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text)
    valor_alvo = Column(Numeric(15, 2), nullable=False)
    prazo = Column(Date)
    
    # Progresso
    valor_atual = Column(Numeric(15, 2), default=0)
    concluida = Column(Boolean, default=False)
    data_conclusao = Column(DateTime)
    
    # Configurações
    aporte_mensal_sugerido = Column(Numeric(15, 2))
    tipo_investimento_sugerido = Column(String(50))  # CONSERVADOR, MODERADO, ARROJADO
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="investment_goals")
    
    def __repr__(self):
        return f"<InvestmentGoal(id={self.id}, titulo={self.titulo}, progresso={self.valor_atual}/{self.valor_alvo})>"


class PatrimonySnapshot(Base):
    """Snapshot patrimonial mensal"""
    __tablename__ = 'patrimony_snapshots'
    
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    
    # Valores consolidados
    total_contas = Column(Numeric(15, 2), default=0)  # Saldo em contas correntes/poupança
    total_investimentos = Column(Numeric(15, 2), default=0)  # Soma de todos investimentos
    total_patrimonio = Column(Numeric(15, 2), nullable=False)  # Soma total
    
    # Variação
    variacao_mensal = Column(Numeric(15, 2))  # Diferença para mês anterior
    variacao_percentual = Column(Numeric(5, 2))  # % de crescimento
    
    # Metadata
    mes_referencia = Column(Date, nullable=False)  # Primeiro dia do mês
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="patrimony_snapshots")
    
    def __repr__(self):
        return f"<PatrimonySnapshot(usuario={self.id_usuario}, mes={self.mes_referencia}, total=R${self.total_patrimonio})>"


class XpEvent(Base):
    """Eventos de gamificação para histórico de interações e ranking."""
    __tablename__ = 'xp_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    xp_base = Column(Integer, nullable=False, default=0)
    xp_gained = Column(Integer, nullable=False, default=0)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    usuario = relationship("Usuario", back_populates="xp_events")


class XpDailyCounter(Base):
    """Contador diário por ação para aplicar limites de XP por feature."""
    __tablename__ = 'xp_daily_counters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    day_ref = Column(Date, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)
    xp_gained = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="xp_daily_counters")


class MonthlyGamificationAward(Base):
    """Marca bônus/penalidade mensal já aplicada para não duplicar pontos."""
    __tablename__ = 'monthly_gamification_awards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    ano_ref = Column(Integer, nullable=False, index=True)
    mes_ref = Column(Integer, nullable=False, index=True)
    ajuste_xp = Column(Integer, nullable=False, default=0)
    motivo = Column(String, nullable=False, default='monthly_balance')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    usuario = relationship("Usuario", back_populates="monthly_gamification_awards")


# --- SISTEMA DE MISSÕES E GAMIFICAÇÃO AVANÇADA ---

class XpLevelDefinition(Base):
    """Definições dos 16+ níveis com requisitos de XP."""
    __tablename__ = 'xp_level_definitions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, unique=True, nullable=False, index=True)
    level_name = Column(String, nullable=False)
    required_xp = Column(Integer, nullable=False, index=True)
    tier = Column(String, nullable=False)  # 'bronze', 'silver', 'gold', 'diamond', 'legend', 'infinite'
    description = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Mission(Base):
    """Definições de missões (diárias, semanais, especiais)."""
    __tablename__ = 'missions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    mission_type = Column(String, nullable=False, index=True)  # 'daily', 'weekly', 'special'
    xp_reward = Column(Integer, nullable=False)
    # Multiplicadores podem ser fracionários (ex.: 1.05)
    bonus_multiplier = Column(Numeric(10, 4), default=1.0)
    unlock_level = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user_missions = relationship("UserMission", back_populates="mission", cascade="all, delete-orphan")


class UserMission(Base):
    """Rastreamento de progresso de missão por usuário."""
    __tablename__ = 'user_missions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    id_mission = Column(Integer, ForeignKey('missions.id', ondelete='CASCADE'), nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Integer, default=0)  # 0-100 percentual
    current_value = Column(Integer, default=0)  # valor atual (ex: 2 de 3 gastos)
    target_value = Column(Integer, default=0)  # alvo (ex: 3 gastos)
    claimed_at = Column(DateTime, nullable=True)
    status = Column(String, default='active', index=True)  # 'active', 'completed', 'claimed', 'reset'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario")
    mission = relationship("Mission", back_populates="user_missions")


class UserAchievement(Base):
    """Conquistas desbloqueadas pelo usuário."""
    __tablename__ = 'user_achievements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    achievement_key = Column(String, nullable=False, index=True)
    achievement_name = Column(String, nullable=False)
    achievement_description = Column(Text, nullable=True)
    xp_reward = Column(Integer, default=0)
    # Bônus permanente pode ser fracionário (ex.: +0.05x)
    permanent_multiplier = Column(Numeric(10, 4), default=0.0)
    badges = Column(JSON, nullable=True)  # JSON array de badges/insígnias
    unlocked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    usuario = relationship("Usuario")


class SaldoConta(Base):
    __tablename__ = 'saldos_conta'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_conta = Column(Integer, ForeignKey('contas.id'), nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    saldo = Column(Numeric(15, 2), nullable=False)
    saldo_disponivel = Column(Numeric(15, 2), nullable=True)
    capturado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conta = relationship("Conta", back_populates="saldos")
    usuario = relationship("Usuario", back_populates="saldos_conta")


class FaturaCartao(Base):
    __tablename__ = 'faturas_cartao'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_conta = Column(Integer, ForeignKey('contas.id'), nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    external_id = Column(String, unique=True, nullable=True)
    valor_total = Column(Numeric(12, 2), nullable=False)
    data_vencimento = Column(Date, nullable=True)
    data_fechamento = Column(Date, nullable=True)
    status = Column(String, nullable=False, default='fechada')  # 'fechada', 'paga', 'em_aberto'
    mes_referencia = Column(Date, nullable=True)  # primeiro dia do mês da fatura
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conta = relationship("Conta", back_populates="faturas")
    usuario = relationship("Usuario", back_populates="faturas_cartao")


class ParcelamentoItem(Base):
    __tablename__ = 'parcelamentos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    id_conta = Column(Integer, ForeignKey('contas.id'), nullable=True)
    external_id = Column(String, unique=True, nullable=True)
    descricao = Column(String, nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    valor_parcela = Column(Numeric(12, 2), nullable=False)
    parcela_atual = Column(Integer, nullable=False)
    total_parcelas = Column(Integer, nullable=False)
    data_compra = Column(Date, nullable=True)
    data_proxima_parcela = Column(Date, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conta = relationship("Conta", back_populates="parcelamentos")
    usuario = relationship("Usuario", back_populates="parcelamentos_item")


# ==================== MODELS DE FIIs ====================

class CarteiraFII(Base):
    __tablename__ = 'carteira_fiis'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)           # Ex: KNRI11, XPML11
    quantidade_cotas = Column(Numeric(10, 2), nullable=False)
    preco_medio = Column(Numeric(10, 2), nullable=False)  # Preço médio de compra por cota
    data_entrada = Column(Date, nullable=True)            # Data da primeira compra
    ativo = Column(Boolean, default=True, nullable=False) # False = vendeu
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", backref="carteira_fiis")

    __table_args__ = (
        UniqueConstraint('id_usuario', 'ticker', name='uq_carteira_fii_usuario_ticker'),
    )


class HistoricoAlertaFII(Base):
    __tablename__ = 'historico_alertas_fii'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    tipo_alerta = Column(String(50), nullable=False)  # 'rendimento_pago', 'pvp_alto', 'vacancia_alta'
    valor_referencia = Column(Numeric(10, 4), nullable=True)  # valor que disparou o alerta
    enviado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario", backref="historico_alertas_fii")
