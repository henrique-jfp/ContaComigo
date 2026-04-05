# models.py
# models.py
from datetime import datetime, timezone, time
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey, BigInteger, Boolean, Date, Time, JSON, Text
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

    # --- CAMPOS DE GAMIFICAÇÃO ---
    perfil_ia = Column(String, nullable=True)
    data_ultima_analise_perfil = Column(DateTime, nullable=True)
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    streak_dias = Column(Integer, default=0, nullable=False)
    ultimo_login = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    
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
    
    # Campos específicos para Cartão de Crédito
    dia_fechamento = Column(Integer, nullable=True)
    dia_vencimento = Column(Integer, nullable=True)
    limite_cartao = Column(Numeric(12, 2), nullable=True)
    email_notificacao = Column(String, nullable=True)
    
    usuario = relationship("Usuario", back_populates="contas")

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
    origem = Column(String, nullable=True)  # manual, texto, audio, ocr, miniapp
    documento_fiscal = Column(String, nullable=True)
    
    id_usuario = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    id_categoria = Column(Integer, ForeignKey('categorias.id'), nullable=True)
    id_subcategoria = Column(Integer, ForeignKey('subcategorias.id'), nullable=True)
    
    usuario = relationship("Usuario", back_populates="lancamentos")
    categoria = relationship("Categoria", back_populates="lancamentos")
    subcategoria = relationship("Subcategoria", back_populates="lancamentos")
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
