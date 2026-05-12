"""Dialect-specific SQL helpers for MySQL, PostgreSQL, and SQLite."""
from __future__ import annotations
from typing import Dict, Any


DIALECT_HINTS: Dict[str, Dict[str, Any]] = {
    "mysql": {
        "auto_increment": "AUTO_INCREMENT",
        "string_type": "VARCHAR",
        "bool_type": "TINYINT(1)",
        "json_type": "JSON",
        "current_timestamp": "CURRENT_TIMESTAMP",
        "engine_clause": "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
        "quote_char": "`",
        "placeholder": "%s",
        "limit_syntax": "LIMIT {offset}, {count}",
    },
    "postgresql": {
        "auto_increment": "SERIAL",
        "string_type": "VARCHAR",
        "bool_type": "BOOLEAN",
        "json_type": "JSONB",
        "current_timestamp": "NOW()",
        "engine_clause": "",
        "quote_char": '"',
        "placeholder": "$1",
        "limit_syntax": "LIMIT {count} OFFSET {offset}",
    },
    "sqlite": {
        "auto_increment": "AUTOINCREMENT",
        "string_type": "TEXT",
        "bool_type": "INTEGER",
        "json_type": "TEXT",
        "current_timestamp": "CURRENT_TIMESTAMP",
        "engine_clause": "",
        "quote_char": '"',
        "placeholder": "?",
        "limit_syntax": "LIMIT {count} OFFSET {offset}",
    },
}


def get_dialect_hints(dialect: str) -> Dict[str, Any]:
    """Return dialect-specific syntax hints for LLM prompts."""
    return DIALECT_HINTS.get(dialect, DIALECT_HINTS["mysql"])


def get_system_prompt(dialect: str, script_type: str) -> str:
    """Build a system prompt tailored to the given dialect and script type."""
    hints = get_dialect_hints(dialect)

    type_guidance = {
        "ddl": "CREATE TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX statements",
        "dml": "SELECT, INSERT, UPDATE, DELETE statements with proper WHERE clauses",
        "maintenance": "VACUUM, ANALYZE, OPTIMIZE, REINDEX, backup/restore helper scripts",
    }

    guidance = type_guidance.get(script_type, "SQL statements")

    prompt = f"""You are an expert database engineer specializing in {dialect.upper()} SQL.
Your task is to generate clean, production-ready SQL scripts based on the user's natural language description.

Dialect rules for {dialect.upper()}:
- Auto-increment syntax: {hints['auto_increment']}
- String type: {hints['string_type']}
- Boolean type: {hints['bool_type']}
- JSON type: {hints['json_type']}
- Current timestamp: {hints['current_timestamp']}
- Identifier quote character: {hints['quote_char']}
{"- Table engine: " + hints['engine_clause'] if hints['engine_clause'] else ""}

Script type focus: {guidance}

Rules:
1. Output ONLY valid {dialect.upper()} SQL — no explanations, markdown fences, or comments outside SQL.
2. Every DML statement that modifies data MUST include a WHERE clause unless operating on all rows is explicitly requested.
3. Wrap multi-statement scripts in a transaction (BEGIN/COMMIT) where appropriate.
4. Use descriptive names following snake_case convention.
5. If the request is ambiguous or missing required details, ask a single clarifying question instead of generating SQL.
   Format: CLARIFY: <your question>
"""
    return prompt


def adapt_sql_for_dialect(sql: str, source_dialect: str, target_dialect: str) -> str:
    """Simple best-effort adaptation of SQL between dialects."""
    if source_dialect == target_dialect:
        return sql

    result = sql

    if source_dialect == "mysql" and target_dialect == "postgresql":
        result = result.replace("AUTO_INCREMENT", "SERIAL")
        result = result.replace("`", '"')
        result = result.replace("TINYINT(1)", "BOOLEAN")
        result = result.replace("ENGINE=InnoDB", "")
        result = result.replace("DEFAULT CHARSET=utf8mb4", "")

    elif source_dialect == "postgresql" and target_dialect == "mysql":
        result = result.replace("SERIAL", "INT AUTO_INCREMENT")
        result = result.replace('"', "`")
        result = result.replace("BOOLEAN", "TINYINT(1)")
        result = result.replace("JSONB", "JSON")

    elif source_dialect == "mysql" and target_dialect == "sqlite":
        result = result.replace("AUTO_INCREMENT", "AUTOINCREMENT")
        result = result.replace("`", '"')
        result = result.replace("TINYINT(1)", "INTEGER")
        import re
        result = re.sub(r"\s*ENGINE=\w+.*?;", ";", result)

    return result
