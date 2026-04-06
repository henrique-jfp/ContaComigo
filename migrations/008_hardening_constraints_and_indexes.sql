-- Migration: hardening de integridade e performance para fluxo integrado do Alfredo.
-- Data: 2026-04-06

-- 1) Ajuste de precisao (fallback) caso 007 ainda nao tenha sido aplicado.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'missions' AND column_name = 'bonus_multiplier'
          AND data_type <> 'numeric'
    ) THEN
        ALTER TABLE missions
            ALTER COLUMN bonus_multiplier TYPE NUMERIC(10,4)
            USING COALESCE(bonus_multiplier, 1.0)::NUMERIC(10,4);
        ALTER TABLE missions
            ALTER COLUMN bonus_multiplier SET DEFAULT 1.0000;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_achievements' AND column_name = 'permanent_multiplier'
          AND data_type <> 'numeric'
    ) THEN
        ALTER TABLE user_achievements
            ALTER COLUMN permanent_multiplier TYPE NUMERIC(10,4)
            USING COALESCE(permanent_multiplier, 0.0)::NUMERIC(10,4);
        ALTER TABLE user_achievements
            ALTER COLUMN permanent_multiplier SET DEFAULT 0.0000;
    END IF;
END $$;

-- 2) FKs essenciais para isolamento por usuario e cascata.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_lancamentos_id_usuario'
    ) THEN
        ALTER TABLE lancamentos
            ADD CONSTRAINT fk_lancamentos_id_usuario
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
            ON DELETE CASCADE
            NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_agendamentos_id_usuario'
    ) THEN
        ALTER TABLE agendamentos
            ADD CONSTRAINT fk_agendamentos_id_usuario
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
            ON DELETE CASCADE
            NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_objetivos_id_usuario'
    ) THEN
        ALTER TABLE objetivos
            ADD CONSTRAINT fk_objetivos_id_usuario
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
            ON DELETE CASCADE
            NOT VALID;
    END IF;
END $$;

-- 3) Dedupe preventivo para constraints unicas da gamificacao.
DELETE FROM xp_daily_counters a
USING xp_daily_counters b
WHERE a.id < b.id
  AND a.id_usuario = b.id_usuario
  AND a.action = b.action
  AND a.day_ref = b.day_ref;

DELETE FROM user_missions a
USING user_missions b
WHERE a.id < b.id
  AND a.id_usuario = b.id_usuario
  AND a.id_mission = b.id_mission;

-- 4) Constraints/indices para garantir consistencia e resposta rapida.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_xp_daily_counters_user_action_day'
    ) THEN
        ALTER TABLE xp_daily_counters
            ADD CONSTRAINT uq_xp_daily_counters_user_action_day
            UNIQUE (id_usuario, action, day_ref);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_missions_usuario_mission'
    ) THEN
        ALTER TABLE user_missions
            ADD CONSTRAINT uq_user_missions_usuario_mission
            UNIQUE (id_usuario, id_mission);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_lancamentos_usuario_data
    ON lancamentos (id_usuario, data_transacao DESC);

CREATE INDEX IF NOT EXISTS idx_lancamentos_usuario_tipo_data
    ON lancamentos (id_usuario, tipo, data_transacao DESC);

CREATE INDEX IF NOT EXISTS idx_metas_confirmacoes_usuario_data
    ON metas_confirmacoes (id_usuario, ano, mes);

CREATE INDEX IF NOT EXISTS idx_user_achievements_usuario_unlocked
    ON user_achievements (id_usuario, unlocked_at DESC);
