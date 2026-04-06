-- Migração: Corrige precisão dos multiplicadores de missões e conquistas
-- Data: 2026-04-06
-- Objetivo: permitir valores fracionários como 1.05 e 0.05 sem truncamento.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'missions'
          AND column_name = 'bonus_multiplier'
    ) THEN
        ALTER TABLE missions
            ALTER COLUMN bonus_multiplier TYPE NUMERIC(10,4)
            USING COALESCE(bonus_multiplier, 1.0)::NUMERIC(10,4);

        ALTER TABLE missions
            ALTER COLUMN bonus_multiplier SET DEFAULT 1.0000;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'user_achievements'
          AND column_name = 'permanent_multiplier'
    ) THEN
        ALTER TABLE user_achievements
            ALTER COLUMN permanent_multiplier TYPE NUMERIC(10,4)
            USING COALESCE(permanent_multiplier, 0.0)::NUMERIC(10,4);

        ALTER TABLE user_achievements
            ALTER COLUMN permanent_multiplier SET DEFAULT 0.0000;
    END IF;
END $$;
