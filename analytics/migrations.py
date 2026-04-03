"""Migrações simples para o módulo de analytics.

Atualmente focado em converter colunas INTEGER para BIGINT
nas tabelas de analytics, evitando erro "integer out of range"
para IDs de usuários do Telegram e contadores.

Uso seguro em produção (idempotente) – só aplica ALTER se o
tipo atual ainda não for bigint.
"""

from __future__ import annotations

import os
import logging
from typing import List, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

BIGINT_TARGETS = [
    ("analytics_command_usage", ["user_id", "execution_time_ms"]),
    ("analytics_daily_users", ["user_id", "total_commands"]),
    ("analytics_error_logs", ["user_id"]),
]


def _normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def _get_engine(db_url: str) -> Engine:
    ssl_args = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': 1,
        'max_overflow': 0,
        'echo': False,
    }
    if 'render' in db_url.lower() or 'amazonaws' in db_url.lower():
        ssl_args['connect_args'] = {
            'sslmode': 'require',
            'connect_timeout': 10,
            'application_name': 'contacomigo_analytics_migration'
        }
    return create_engine(db_url, **ssl_args)


def _column_is_bigint(engine: Engine, table: str, column: str) -> bool:
    qry = text(
        """
        SELECT data_type 
        FROM information_schema.columns 
        WHERE table_name = :table AND column_name = :column
        """
    )
    with engine.connect() as conn:
        row = conn.execute(qry, {"table": table, "column": column}).fetchone()
        if not row:
            return False
        return str(row[0]).lower() in {"bigint", "bigserial"}


def _alter_column_bigint(engine: Engine, table: str, column: str) -> Tuple[bool, str]:
    try:
        if _column_is_bigint(engine, table, column):
            return False, "já era BIGINT"
        # Usar USING para evitar falhas de cast
        alter_sql = text(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT USING {column}::bigint"
        )
        with engine.begin() as conn:
            conn.execute(alter_sql)
        return True, "convertido"
    except Exception as e:
        return False, f"erro: {e}"  # não lança para não travar startup


def run_bigint_migration(db_url: str | None = None) -> List[Tuple[str, str, str]]:
    """Executa migração para BIGINT nas colunas alvo.

    Retorna lista de tuplas (tabela, coluna, status).
    """
    results: List[Tuple[str, str, str]] = []
    if not db_url:
        db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.warning("[MIGRATION] DATABASE_URL ausente – migração ignorada")
        return results

    try:
        db_url = _normalize_db_url(db_url)
        engine = _get_engine(db_url)
    except Exception as e:
        logger.error(f"[MIGRATION] Falha ao criar engine: {e}")
        return results

    for table, columns in BIGINT_TARGETS:
        for col in columns:
            changed, status = _alter_column_bigint(engine, table, col)
            results.append((table, col, status))
            if changed:
                logger.info(f"[MIGRATION] {table}.{col} -> BIGINT")
            else:
                logger.debug(f"[MIGRATION] {table}.{col} sem alteração ({status})")

    logger.info("[MIGRATION] Concluída")
    return results


if __name__ == "__main__":  # Execução manual opcional
    out = run_bigint_migration()
    for t, c, s in out:
        print(f"{t}.{c}: {s}")
