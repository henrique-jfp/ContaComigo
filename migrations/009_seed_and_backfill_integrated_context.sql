-- Migration: seed canonico de gamificacao + backfill patrimonial inicial.
-- Data: 2026-04-06

-- 1) Seed/Upsert dos niveis canonicos.
INSERT INTO xp_level_definitions (level, level_name, required_xp, tier, description, sort_order)
VALUES
(1, 'Caderneta Zerada', 0, 'bronze', 'Iniciante', 1),
(2, 'Anotador de Plantao', 200, 'bronze', 'Iniciante', 2),
(3, 'Controlador de Gastos', 500, 'bronze', 'Iniciante', 3),
(4, 'Orcamentario Jr.', 1000, 'bronze', 'Iniciante', 4),
(5, 'Cacador de Sobras', 2000, 'silver', 'Intermediario', 5),
(6, 'Arquivista do Real', 3500, 'silver', 'Intermediario', 6),
(7, 'Analista de Bolso', 5500, 'silver', 'Intermediario', 7),
(8, 'Planejador Ativo', 8000, 'silver', 'Intermediario', 8),
(9, 'Mestre do Fluxo', 12000, 'gold', 'Avancado', 9),
(10, 'Guardiao do Patrimonio', 18000, 'gold', 'Avancado', 10),
(11, 'CFO Pessoal', 25000, 'gold', 'Avancado', 11),
(12, 'Arquiteto Financeiro', 35000, 'gold', 'Avancado', 12),
(13, 'Visionario de Mercado', 50000, 'diamond', 'Elite', 13),
(14, 'Oraculo do Budget', 70000, 'diamond', 'Elite', 14),
(15, 'Alfredo Humano', 95000, 'legend', 'Lenda', 15),
(16, 'Alem do Budget', 130000, 'infinite', 'Infinito', 16)
ON CONFLICT (level) DO UPDATE
SET
    level_name = EXCLUDED.level_name,
    required_xp = EXCLUDED.required_xp,
    tier = EXCLUDED.tier,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order;

-- 2) Seed/Upsert de missoes canonicas.
INSERT INTO missions (mission_key, name, description, mission_type, xp_reward, bonus_multiplier, unlock_level, sort_order, active)
VALUES
('caffeine_tracker', 'Caffeine Tracker', 'Registre 3 gastos hoje via texto, voz ou foto.', 'daily', 30, 1.0000, 0, 10, TRUE),
('olho_vivo', 'Olho Vivo', 'Verifique o dashboard e leia o card do Alfredo.', 'daily', 15, 1.0000, 0, 20, TRUE),
('clique_rapido', 'Clique Rapido', 'Registre um gasto via audio (voz para texto).', 'daily', 20, 1.0000, 0, 30, TRUE),
('pergunta_dia', 'Pergunta do Dia', 'Faca uma pergunta ao Alfredo sobre seus gastos ou padroes.', 'daily', 18, 1.0000, 0, 40, TRUE),
('semana_limpa', 'Semana Limpa', 'Registre pelo menos 1 gasto em 5 dias diferentes durante a semana.', 'weekly', 80, 1.0000, 0, 50, TRUE),
('detetive_nota', 'Detetive da Nota', 'Use OCR de foto em pelo menos 2 notas fiscais na semana.', 'weekly', 60, 1.0000, 0, 60, TRUE),
('estrategista_metas', 'Estrategista de Metas', 'Faca check-in em pelo menos 1 meta financeira ativa.', 'weekly', 50, 1.0000, 0, 70, TRUE),
('fatura_detonada', 'Fatura Detonada', 'Importe e categorize um extrato ou PDF de fatura.', 'weekly', 90, 1.0000, 0, 80, TRUE),
('semana_azul', 'Semana Azul', 'Gaste menos do que entrou na semana.', 'weekly', 100, 1.0000, 0, 90, TRUE),
('primeiro_passo', 'Primeiro Passo', 'Registre seu primeiro gasto no ContaComigo.', 'special', 50, 1.0000, 0, 100, TRUE),
('semana_sem_enrolacao', 'Semana Sem Enrolacao', 'Complete 7 dias de streak sem quebrar.', 'special', 50, 1.0000, 0, 110, TRUE),
('mes_chave_ouro', 'Mes Fechado com Chave de Ouro', 'Feche o mes com saldo positivo e 20+ lancamentos.', 'special', 250, 1.0000, 0, 120, TRUE),
('curador_portfolio', 'Curador do Portfolio', 'Adicione pelo menos 3 investimentos.', 'special', 120, 1.0000, 0, 130, TRUE)
ON CONFLICT (mission_key) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    mission_type = EXCLUDED.mission_type,
    xp_reward = EXCLUDED.xp_reward,
    bonus_multiplier = EXCLUDED.bonus_multiplier,
    unlock_level = EXCLUDED.unlock_level,
    sort_order = EXCLUDED.sort_order,
    active = TRUE;

-- 3) Seed de user_missions para usuarios existentes sem duplicar.
INSERT INTO user_missions (id_usuario, id_mission, progress, current_value, target_value, status)
SELECT
    u.id,
    m.id,
    0,
    0,
    CASE m.mission_key
        WHEN 'caffeine_tracker' THEN 3
        WHEN 'olho_vivo' THEN 1
        WHEN 'clique_rapido' THEN 1
        WHEN 'pergunta_dia' THEN 1
        WHEN 'semana_limpa' THEN 5
        WHEN 'detetive_nota' THEN 2
        WHEN 'estrategista_metas' THEN 1
        WHEN 'fatura_detonada' THEN 1
        WHEN 'semana_azul' THEN 1
        WHEN 'primeiro_passo' THEN 1
        WHEN 'semana_sem_enrolacao' THEN 7
        WHEN 'mes_chave_ouro' THEN 1
        WHEN 'curador_portfolio' THEN 3
        ELSE 1
    END,
    'active'
FROM usuarios u
CROSS JOIN missions m
WHERE m.active = TRUE
ON CONFLICT (id_usuario, id_mission) DO NOTHING;

-- 4) Backfill inicial de patrimonio mensal com base em lancamentos (saldo acumulado por mes).
WITH monthly_balance AS (
    SELECT
        l.id_usuario,
        date_trunc('month', l.data_transacao)::date AS mes_ref,
        SUM(
            CASE
                WHEN lower(coalesce(l.tipo, '')) IN ('entrada', 'receita') THEN COALESCE(l.valor, 0)
                ELSE -ABS(COALESCE(l.valor, 0))
            END
        ) AS net_mes
    FROM lancamentos l
        JOIN usuarios u ON u.id = l.id_usuario
    GROUP BY l.id_usuario, date_trunc('month', l.data_transacao)::date
),
running_balance AS (
    SELECT
        id_usuario,
        mes_ref,
        SUM(net_mes) OVER (PARTITION BY id_usuario ORDER BY mes_ref ROWS UNBOUNDED PRECEDING) AS saldo_acumulado
    FROM monthly_balance
),
with_variation AS (
    SELECT
        id_usuario,
        mes_ref,
        saldo_acumulado,
        saldo_acumulado - LAG(saldo_acumulado) OVER (PARTITION BY id_usuario ORDER BY mes_ref) AS variacao_mensal,
        CASE
            WHEN COALESCE(LAG(saldo_acumulado) OVER (PARTITION BY id_usuario ORDER BY mes_ref), 0) = 0 THEN NULL
            ELSE LEAST(
                999.99,
                GREATEST(
                    -999.99,
                    ((saldo_acumulado - LAG(saldo_acumulado) OVER (PARTITION BY id_usuario ORDER BY mes_ref))
                    / NULLIF(LAG(saldo_acumulado) OVER (PARTITION BY id_usuario ORDER BY mes_ref), 0)) * 100
                )
            )
        END AS variacao_percentual
    FROM running_balance
)
INSERT INTO patrimony_snapshots (
    id_usuario,
    total_contas,
    total_investimentos,
    total_patrimonio,
    variacao_mensal,
    variacao_percentual,
    mes_referencia
)
SELECT
    id_usuario,
    saldo_acumulado,
    0,
    saldo_acumulado,
    variacao_mensal,
    variacao_percentual,
    mes_ref
FROM with_variation
ON CONFLICT (id_usuario, mes_referencia) DO UPDATE
SET
    total_contas = EXCLUDED.total_contas,
    total_investimentos = EXCLUDED.total_investimentos,
    total_patrimonio = EXCLUDED.total_patrimonio,
    variacao_mensal = EXCLUDED.variacao_mensal,
    variacao_percentual = EXCLUDED.variacao_percentual;
