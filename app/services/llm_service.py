"""LLM service — wraps OpenAI-compatible API with a mock fallback."""
from __future__ import annotations
import uuid
from typing import List, Dict, Optional

from app.config import settings
from app.services.dialect_service import get_system_prompt

# ---------------------------------------------------------------------------
# Mock SQL templates used when LLM_MOCK_MODE is enabled
# ---------------------------------------------------------------------------

_MOCK_DDL_MYSQL = """\
-- Generated (mock) DDL for MySQL
CREATE TABLE IF NOT EXISTS `example_table` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `name`       VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

_MOCK_DDL_POSTGRESQL = """\
-- Generated (mock) DDL for PostgreSQL
CREATE TABLE IF NOT EXISTS "example_table" (
    "id"         SERIAL PRIMARY KEY,
    "name"       VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMP DEFAULT NOW(),
    "updated_at" TIMESTAMP DEFAULT NOW()
);
"""

_MOCK_DDL_SQLITE = """\
-- Generated (mock) DDL for SQLite
CREATE TABLE IF NOT EXISTS "example_table" (
    "id"         INTEGER PRIMARY KEY AUTOINCREMENT,
    "name"       TEXT NOT NULL,
    "created_at" TEXT DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_MOCK_DML = """\
-- Generated (mock) DML
SELECT id, name, created_at
FROM example_table
WHERE id = 1;

INSERT INTO example_table (name) VALUES ('sample_record');

UPDATE example_table
SET name = 'updated_record'
WHERE id = 1;
"""

_MOCK_MAINTENANCE = """\
-- Generated (mock) maintenance script
ANALYZE TABLE example_table;
OPTIMIZE TABLE example_table;
"""

_MOCK_MAP = {
    ("ddl", "mysql"): _MOCK_DDL_MYSQL,
    ("ddl", "postgresql"): _MOCK_DDL_POSTGRESQL,
    ("ddl", "sqlite"): _MOCK_DDL_SQLITE,
    ("dml", "mysql"): _MOCK_DML,
    ("dml", "postgresql"): _MOCK_DML,
    ("dml", "sqlite"): _MOCK_DML,
    ("maintenance", "mysql"): _MOCK_MAINTENANCE,
    ("maintenance", "postgresql"): "-- VACUUM ANALYZE example_table;\n",
    ("maintenance", "sqlite"): "-- VACUUM;\n",
}


def _mock_response(prompt: str, dialect: str, script_type: str) -> str:
    """Return a canned mock SQL response."""
    sql = _MOCK_MAP.get((script_type, dialect), _MOCK_DDL_MYSQL)
    # Insert a comment with the original prompt
    return f"-- Request: {prompt[:120]}\n{sql}"


# ---------------------------------------------------------------------------
# OpenAI client (lazy init)
# ---------------------------------------------------------------------------

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(
            api_key=settings.llm_api_key or "sk-mock",
            base_url=settings.llm_base_url,
        )
    return _openai_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_sql(
    prompt: str,
    dialect: str,
    script_type: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, str]:
    """
    Generate SQL from a natural language prompt.

    Returns a dict with keys:
      - "sql": the generated SQL (or empty string if clarification needed)
      - "needs_clarification": bool
      - "clarification_question": str or empty
    """
    use_mock = settings.llm_mock_mode or not settings.llm_api_key

    if use_mock:
        sql = _mock_response(prompt, dialect, script_type)
        return {"sql": sql, "needs_clarification": False, "clarification_question": ""}

    # Build messages
    system_msg = get_system_prompt(dialect, script_type)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_msg}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": prompt})

    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.2,
            max_tokens=2048,
        )
        content = response.choices[0].message.content or ""
    except Exception as exc:
        # Fallback to mock on any API error
        return {"sql": _mock_response(prompt, dialect, script_type), "needs_clarification": False, "clarification_question": ""}

    # Check if the model requested clarification
    if content.strip().startswith("CLARIFY:"):
        question = content.strip().removeprefix("CLARIFY:").strip()
        return {"sql": "", "needs_clarification": True, "clarification_question": question}

    return {"sql": content.strip(), "needs_clarification": False, "clarification_question": ""}


def new_session_id() -> str:
    return uuid.uuid4().hex
