-- Migration 013: Add missing Pierre (Open Finance) synchronization fields to usuarios table
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pierre_sync_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pierre_initial_sync_done BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS last_pierre_sync_at TIMESTAMP;
