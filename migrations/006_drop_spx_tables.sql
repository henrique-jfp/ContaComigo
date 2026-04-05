-- Remove legacy SPX tables that are no longer referenced by the application.
-- Safe for repeated execution.

DROP TABLE IF EXISTS entregas_spx;
DROP TABLE IF EXISTS metas_spx;
