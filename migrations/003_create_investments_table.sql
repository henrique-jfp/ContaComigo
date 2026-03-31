-- Migration: Criar tabelas para gestão de investimentos
-- Data: 2025-11-18
-- Descrição: Adiciona tabelas para histórico de investimentos, rentabilidade e controle patrimonial

-- ==================== INVESTMENTS (Investimentos do Usuário) ====================
CREATE TABLE IF NOT EXISTS investments (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    -- id_account removido
    
    -- Informações básicas
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- CDB, LCI, LCA, POUPANCA, TESOURO, ACAO, FUNDO, COFRINHO, OUTRO
    banco VARCHAR(255),
    
    -- Valores
    valor_inicial NUMERIC(15, 2) DEFAULT 0,
    valor_atual NUMERIC(15, 2) NOT NULL,
    
    -- Rentabilidade
    taxa_contratada NUMERIC(5, 4), -- Ex: 100% CDI = 1.0000
    indexador VARCHAR(50), -- CDI, IPCA, SELIC, PREFIXADO
    data_aplicacao DATE,
    data_vencimento DATE,
    
    -- Controle
    ativo BOOLEAN DEFAULT TRUE,
    fonte VARCHAR(50) DEFAULT 'MANUAL',
    
    -- Metadata
    observacoes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_investments_usuario ON investments(id_usuario);
CREATE INDEX IF NOT EXISTS idx_investments_ativo ON investments(ativo);
CREATE INDEX IF NOT EXISTS idx_investments_tipo ON investments(tipo);

-- ==================== INVESTMENT_SNAPSHOTS (Histórico de Saldos) ====================
CREATE TABLE IF NOT EXISTS investment_snapshots (
    id SERIAL PRIMARY KEY,
    id_investment INTEGER NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    
    -- Valores no momento do snapshot
    valor NUMERIC(15, 2) NOT NULL,
    rentabilidade_periodo NUMERIC(15, 2), -- Quanto rendeu desde último snapshot
    rentabilidade_percentual NUMERIC(5, 2), -- % de rendimento
    
    -- Comparações
    cdi_periodo NUMERIC(5, 4), -- CDI acumulado no período
    ipca_periodo NUMERIC(5, 4), -- IPCA acumulado no período
    
    -- Metadata
    data_snapshot DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_snapshots_investment ON investment_snapshots(id_investment);
CREATE INDEX IF NOT EXISTS idx_snapshots_data ON investment_snapshots(data_snapshot);

-- ==================== INVESTMENT_GOALS (Metas de Investimento) ====================
CREATE TABLE IF NOT EXISTS investment_goals (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    
    -- Meta
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    valor_alvo NUMERIC(15, 2) NOT NULL,
    prazo DATE,
    
    -- Progresso
    valor_atual NUMERIC(15, 2) DEFAULT 0,
    concluida BOOLEAN DEFAULT FALSE,
    data_conclusao TIMESTAMP WITH TIME ZONE,
    
    -- Configurações
    aporte_mensal_sugerido NUMERIC(15, 2),
    tipo_investimento_sugerido VARCHAR(50), -- CONSERVADOR, MODERADO, ARROJADO
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_investment_goals_usuario ON investment_goals(id_usuario);
CREATE INDEX IF NOT EXISTS idx_investment_goals_concluida ON investment_goals(concluida);

-- ==================== PATRIMONY_SNAPSHOTS (Snapshot Patrimonial Mensal) ====================
CREATE TABLE IF NOT EXISTS patrimony_snapshots (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    
    -- Valores consolidados
    total_contas NUMERIC(15, 2) DEFAULT 0, -- Saldo em contas correntes/poupança
    total_investimentos NUMERIC(15, 2) DEFAULT 0, -- Soma de todos investimentos
    total_patrimonio NUMERIC(15, 2) NOT NULL, -- Soma total
    
    -- Variação
    variacao_mensal NUMERIC(15, 2), -- Diferença para mês anterior
    variacao_percentual NUMERIC(5, 2), -- % de crescimento
    
    -- Metadata
    mes_referencia DATE NOT NULL, -- Primeiro dia do mês
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(id_usuario, mes_referencia)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_patrimony_usuario ON patrimony_snapshots(id_usuario);
CREATE INDEX IF NOT EXISTS idx_patrimony_mes ON patrimony_snapshots(mes_referencia);

-- ==================== COMENTÁRIOS ====================
COMMENT ON TABLE investments IS 'Investimentos do usuário (manual)';
COMMENT ON TABLE investment_snapshots IS 'Histórico de valores dos investimentos para análise de rentabilidade';
COMMENT ON TABLE investment_goals IS 'Metas financeiras específicas para investimentos';
COMMENT ON TABLE patrimony_snapshots IS 'Snapshot mensal do patrimônio total do usuário';

COMMENT ON COLUMN investments.tipo IS 'Tipo de investimento: CDB, LCI, POUPANCA, TESOURO, ACAO, FUNDO, COFRINHO';
COMMENT ON COLUMN investments.fonte IS 'Origem dos dados: MANUAL (usuário)';
COMMENT ON COLUMN investment_snapshots.rentabilidade_periodo IS 'Quanto o investimento rendeu desde o último snapshot';
COMMENT ON COLUMN patrimony_snapshots.total_patrimonio IS 'Soma de saldo em contas + investimentos';

-- ==================== VERIFICAÇÃO ====================
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name IN ('investments', 'investment_snapshots', 'investment_goals', 'patrimony_snapshots')
    ) THEN
        RAISE NOTICE '✅ Tabelas de investimentos criadas com sucesso!';
    ELSE
        RAISE EXCEPTION '❌ Erro ao criar tabelas de investimentos';
    END IF;
END $$;
