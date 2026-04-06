"""SQL migration runner with version tracking for Postgres/SQLite backends."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _file_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _ensure_schema_migrations_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    checksum VARCHAR(64) NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def apply_sql_migrations(engine: Engine, migrations_dir: str | Path) -> dict:
    """Apply SQL migrations in lexicographic order with idempotent tracking."""
    migrations_path = Path(migrations_dir)
    result = {"applied": [], "skipped": [], "drift": []}

    if not migrations_path.exists():
        logger.info("Diretorio de migrations nao encontrado: %s", migrations_path)
        return result

    files = sorted(p for p in migrations_path.glob("*.sql") if p.is_file())
    if not files:
        logger.info("Nenhuma migration SQL encontrada em %s", migrations_path)
        return result

    _ensure_schema_migrations_table(engine)

    with engine.connect() as conn:
        applied_rows = conn.execute(text("SELECT filename, checksum FROM schema_migrations")).fetchall()
    applied = {row[0]: row[1] for row in applied_rows}

    for path in files:
        filename = path.name
        sql_content = path.read_text(encoding="utf-8")
        checksum = _file_checksum(sql_content)

        if filename in applied:
            if applied[filename] == checksum:
                result["skipped"].append(filename)
                continue
            result["drift"].append(filename)
            raise RuntimeError(
                f"Migration drift detectado em '{filename}'. "
                "O arquivo foi alterado apos ser aplicado; crie uma nova migration."
            )

        logger.info("Aplicando migration %s", filename)
        with engine.begin() as tx:
            tx.execute(text(sql_content))
            tx.execute(
                text(
                    """
                    INSERT INTO schema_migrations (filename, checksum)
                    VALUES (:filename, :checksum)
                    """
                ),
                {"filename": filename, "checksum": checksum},
            )
        result["applied"].append(filename)

    logger.info(
        "Migrations SQL finalizadas | aplicadas=%s ignoradas=%s",
        len(result["applied"]),
        len(result["skipped"]),
    )
    return result
