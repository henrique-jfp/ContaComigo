-- Migration: monetizacao freemium (trial + free + premium)
-- Data: 2026-04-06

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'trial';

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS trial_expires_at TIMESTAMP;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS premium_expires_at TIMESTAMP;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS subscription_id VARCHAR(100);

UPDATE usuarios
SET
    plan = COALESCE(plan, 'trial'),
    trial_expires_at = COALESCE(trial_expires_at, (CURRENT_TIMESTAMP + INTERVAL '15 day'))
WHERE plan IS NULL OR trial_expires_at IS NULL;

CREATE TABLE IF NOT EXISTS user_plan_usage_monthly (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    lancamentos_count INTEGER NOT NULL DEFAULT 0,
    ocr_count INTEGER NOT NULL DEFAULT 0,
    ia_questions_count INTEGER NOT NULL DEFAULT 0,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_plan_usage_monthly_user_period UNIQUE (id_usuario, ano, mes)
);

CREATE INDEX IF NOT EXISTS idx_user_plan_usage_monthly_user ON user_plan_usage_monthly (id_usuario);
CREATE INDEX IF NOT EXISTS idx_user_plan_usage_monthly_period ON user_plan_usage_monthly (ano, mes);
