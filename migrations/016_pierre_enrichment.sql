-- Migration 016: Pierre Enrichment Fields
-- Objetivo: Suportar sincronização de limites e lembretes da API Pierre

ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS external_id VARCHAR UNIQUE;
ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS periodo VARCHAR DEFAULT 'monthly';
ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS recorrente BOOLEAN DEFAULT TRUE;
ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;

ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS external_id VARCHAR UNIQUE;
ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS origem_externa VARCHAR;
ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status VARCHAR;
