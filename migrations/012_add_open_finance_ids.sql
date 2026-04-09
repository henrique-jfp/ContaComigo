-- Migration 012: Add external_id to contas and lancamentos for Open Finance sync
ALTER TABLE contas ADD COLUMN external_id VARCHAR(100) UNIQUE NULL;
ALTER TABLE lancamentos ADD COLUMN external_id VARCHAR(100) UNIQUE NULL;
