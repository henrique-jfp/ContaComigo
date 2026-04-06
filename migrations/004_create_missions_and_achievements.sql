-- Migracao: Criar tabelas para sistema de Missoes e Gamificacao avancada
-- 2026-04-05

CREATE TABLE IF NOT EXISTS missions (
    id SERIAL PRIMARY KEY,
    mission_key VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    mission_type VARCHAR(20) NOT NULL,
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
    progress INTEGER DEFAULT 0,
    current_value INTEGER DEFAULT 0,
    target_value INTEGER DEFAULT 0,
    claimed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
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
    permanent_multiplier FLOAT DEFAULT 0.0,
    badges TEXT,
    unlocked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, achievement_key)
);

CREATE TABLE IF NOT EXISTS xp_level_definitions (
    id SERIAL PRIMARY KEY,
    level INTEGER NOT NULL UNIQUE,
    level_name VARCHAR(100) NOT NULL,
    required_xp INTEGER NOT NULL,
    tier VARCHAR(20) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_missions' AND column_name = 'user_id'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_missions_user_id ON user_missions(user_id)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_missions' AND column_name = 'id_usuario'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_missions_id_usuario ON user_missions(id_usuario)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_missions' AND column_name = 'mission_id'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_missions_mission_id ON user_missions(mission_id)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_missions' AND column_name = 'id_mission'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_missions_id_mission ON user_missions(id_mission)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_achievements' AND column_name = 'user_id'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_achievements' AND column_name = 'id_usuario'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_user_achievements_id_usuario ON user_achievements(id_usuario)';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_missions_status ON user_missions(status);
CREATE INDEX IF NOT EXISTS idx_xp_level_definitions_level ON xp_level_definitions(level);

INSERT INTO xp_level_definitions (level, level_name, required_xp, tier, description) VALUES
(1, 'Caderneta Zerada', 0, 'bronze', 'Iniciante'),
(2, 'Anotador de Plantao', 200, 'bronze', 'Iniciante'),
(3, 'Controlador de Gastos', 500, 'bronze', 'Iniciante'),
(4, 'Orcamentario Jr.', 1000, 'bronze', 'Iniciante'),
(5, 'Cacador de Sobras', 2000, 'silver', 'Intermediario'),
(6, 'Arquivista do Real', 3500, 'silver', 'Intermediario'),
(7, 'Analista de Bolso', 5500, 'silver', 'Intermediario'),
(8, 'Planejador Ativo', 8000, 'silver', 'Intermediario'),
(9, 'Mestre do Fluxo', 12000, 'gold', 'Avancado'),
(10, 'Guardiao do Patrimonio', 18000, 'gold', 'Avancado'),
(11, 'CFO Pessoal', 25000, 'gold', 'Avancado'),
(12, 'Arquiteto Financeiro', 35000, 'gold', 'Avancado'),
(13, 'Visionario de Mercado', 50000, 'diamond', 'Elite'),
(14, 'Oraculo do Budget', 70000, 'diamond', 'Elite'),
(15, 'Alfredo Humano', 95000, 'legend', 'Lenda'),
(16, 'Alem do Budget', 130000, 'infinite', 'Infinito')
ON CONFLICT (level) DO NOTHING;

INSERT INTO missions (mission_key, name, description, mission_type, xp_reward, bonus_multiplier, sort_order) VALUES
('caffeine_tracker', 'Caffeine Tracker', 'Registre 3 gastos hoje via texto, voz ou foto.', 'daily', 30, 1.0, 1),
('olho_vivo', 'Olho Vivo', 'Verifique o dashboard e leia o card do Alfredo.', 'daily', 15, 1.0, 2),
('clique_rapido', 'Clique Rapido', 'Registre um gasto via audio (voz para texto).', 'daily', 20, 1.05, 3),
('pergunta_dia', 'Pergunta do Dia', 'Faca uma pergunta ao Alfredo sobre seus gastos ou padroes.', 'daily', 18, 1.0, 4),
('semana_limpa', 'Semana Limpa', 'Registre pelo menos 1 gasto em 5 dias diferentes na semana.', 'weekly', 80, 1.2, 5),
('detetive_nota', 'Detetive da Nota', 'Use OCR de foto em pelo menos 2 notas fiscais na semana.', 'weekly', 60, 1.0, 6),
('estrategista_metas', 'Estrategista de Metas', 'Faca check-in em pelo menos 1 meta financeira ativa.', 'weekly', 50, 1.0, 7),
('fatura_detonada', 'Fatura Detonada', 'Importe e categorize um extrato ou PDF de fatura.', 'weekly', 90, 1.0, 8),
('semana_azul', 'Semana Azul', 'Gaste menos do que entrou na semana (Alfredo verifica automaticamente).', 'weekly', 100, 1.0, 9),
('primeiro_passo', 'Primeiro Passo', 'Registre seu primeiro gasto no ContaComigo.', 'special', 50, 1.0, 10),
('semana_sem_enrolacao', 'Semana Sem Enrolacao', '7 dias de streak sem quebrar.', 'special', 50, 1.0, 11),
('mes_chave_ouro', 'Mes com Chave de Ouro', 'Feche o mes com saldo positivo E com 20+ lancamentos registrados.', 'special', 250, 1.0, 12),
('curador_portfolio', 'Curador do Portfolio', 'Adicione pelo menos 3 investimentos e visualize o patrimonio liquido.', 'special', 120, 1.0, 13)
ON CONFLICT (mission_key) DO NOTHING;
