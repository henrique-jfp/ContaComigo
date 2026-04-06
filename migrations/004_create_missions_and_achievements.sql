-- Migração: Criar tabelas para sistema de Missões e Gamificação avançada
-- 2026-04-05

CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    mission_key VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    mission_type VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'special'
    xp_reward INTEGER NOT NULL,
    bonus_multiplier FLOAT DEFAULT 1.0,
    unlock_level INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_missions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    mission_id INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    progress INTEGER DEFAULT 0, -- 0-100
    current_value INTEGER DEFAULT 0, -- valor atual do progresso
    target_value INTEGER DEFAULT 0, -- valor alvo (ex: 3 gastos, 5 dias)
    claimed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'completed', 'claimed', 'reset'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, mission_id)
);

CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    achievement_key VARCHAR(50) NOT NULL,
    achievement_name VARCHAR(100) NOT NULL,
    achievement_description TEXT,
    xp_reward INTEGER DEFAULT 0,
    permanent_multiplier FLOAT DEFAULT 0.0, -- Ex: +0.05x multiplicador permanente
    badges TEXT, -- JSON array de insígnias
    unlocked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, achievement_key)
);

CREATE TABLE IF NOT EXISTS xp_level_definitions (
    id SERIAL PRIMARY KEY,
    level INTEGER NOT NULL UNIQUE,
    level_name VARCHAR(100) NOT NULL,
    required_xp INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL, -- 'bronze', 'silver', 'gold', 'diamond', 'legend', 'infinite'
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_missions_user_id ON user_missions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_missions_mission_id ON user_missions(mission_id);
CREATE INDEX IF NOT EXISTS idx_user_missions_status ON user_missions(status);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_xp_level_definitions_level ON xp_level_definitions(level);

-- Inserir definições de níveis
INSERT INTO xp_level_definitions (level, level_name, required_xp, tier, description) VALUES
(1, 'Caderneta Zerada', 0, 'bronze', 'Iniciante'),
(2, 'Anotador de Plantão', 200, 'bronze', 'Iniciante'),
(3, 'Controlador de Gastos', 500, 'bronze', 'Iniciante'),
(4, 'Orçamentário Jr.', 1000, 'bronze', 'Iniciante'),
(5, 'Caçador de Sobras', 2000, 'silver', 'Intermediário'),
(6, 'Arquivista do Real', 3500, 'silver', 'Intermediário'),
(7, 'Analista de Bolso', 5500, 'silver', 'Intermediário'),
(8, 'Planejador Ativo', 8000, 'silver', 'Intermediário'),
(9, 'Mestre do Fluxo', 12000, 'gold', 'Avançado'),
(10, 'Guardião do Patrimônio', 18000, 'gold', 'Avançado'),
(11, 'CFO Pessoal', 25000, 'gold', 'Avançado'),
(12, 'Arquiteto Financeiro', 35000, 'gold', 'Avançado'),
(13, 'Visionário de Mercado', 50000, 'diamond', 'Elite'),
(14, 'Oráculo do Budget', 70000, 'diamond', 'Elite'),
(15, 'Alfredo Humano', 95000, 'legend', 'Lenda'),
(16, 'Além do Budget', 130000, 'infinite', 'Infinito');

-- Inserir missões diárias
INSERT INTO missions (mission_key, name, description, mission_type, xp_reward, bonus_multiplier, sort_order) VALUES
('caffeine_tracker', 'Caffeine Tracker', 'Registre 3 gastos hoje via texto, voz ou foto.', 'daily', 30, 1.0, 1),
('olho_vivo', 'Olho Vivo', 'Verifique o dashboard e leia o card do Alfredo.', 'daily', 15, 1.0, 2),
('clique_rapido', 'Clique Rápido', 'Registre um gasto via áudio (voz para texto).', 'daily', 20, 1.05, 3),
('pergunta_dia', 'Pergunta do Dia', 'Faça uma pergunta ao Alfredo sobre seus gastos ou padrões.', 'daily', 18, 1.0, 4),

-- Inserir missões semanais
('semana_limpa', 'Semana Limpa', 'Registre pelo menos 1 gasto em 5 dias diferentes na semana.', 'weekly', 80, 1.2, 5),
('detetive_nota', 'Detetive da Nota', 'Use OCR de foto em pelo menos 2 notas fiscais na semana.', 'weekly', 60, 1.0, 6),
('estrategista_metas', 'Estrategista de Metas', 'Faça check-in em pelo menos 1 meta financeira ativa.', 'weekly', 50, 1.0, 7),
('fatura_detonada', 'Fatura Detonada', 'Importe e categorize um extrato ou PDF de fatura.', 'weekly', 90, 1.0, 8),
('semana_azul', 'Semana Azul', 'Gaste menos do que entrou na semana (Alfredo verifica automaticamente).', 'weekly', 100, 1.0, 9),

-- Inserir missões especiais
('primeiro_passo', 'Primeiro Passo', 'Registre seu primeiro gasto no ContaComigo.', 'special', 50, 1.0, 10),
('semana_sem_enrolacao', 'Semana Sem Enrolação', '7 dias de streak sem quebrar.', 'special', 50, 1.0, 11),
('mes_chave_ouro', 'Mês com Chave de Ouro', 'Feche o mês com saldo positivo E com 20+ lançamentos registrados.', 'special', 250, 1.0, 12),
('curador_portfolio', 'Curador do Portfólio', 'Adicione pelo menos 3 investimentos e visualize o patrimônio líquido.', 'special', 120, 1.0, 13);
