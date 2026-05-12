"""Risk checker — detects dangerous or non-compliant SQL patterns."""
from __future__ import annotations
import re
from typing import List

import sqlparse
from sqlparse.sql import Statement

from app.models.schemas import RiskItem, RiskReport

# Risk level ordering for comparison
_LEVEL_ORDER = {"safe": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

_RULES = [
    # (rule_id, pattern, level, message)
    (
        "NO_DROP_TABLE",
        r"\bDROP\s+TABLE\b",
        "critical",
        "DROP TABLE detected — this operation irreversibly destroys data.",
    ),
    (
        "NO_DROP_DATABASE",
        r"\bDROP\s+DATABASE\b",
        "critical",
        "DROP DATABASE detected — this will destroy the entire database.",
    ),
    (
        "NO_TRUNCATE",
        r"\bTRUNCATE\b",
        "high",
        "TRUNCATE detected — removes all rows without logging individual deletions.",
    ),
    (
        "DELETE_WITHOUT_WHERE",
        None,  # handled programmatically
        "high",
        "DELETE statement without a WHERE clause will remove all rows.",
    ),
    (
        "UPDATE_WITHOUT_WHERE",
        None,  # handled programmatically
        "high",
        "UPDATE statement without a WHERE clause will modify all rows.",
    ),
    (
        "NO_GRANT_ALL",
        r"\bGRANT\s+ALL\b",
        "high",
        "GRANT ALL detected — overly broad privilege assignment.",
    ),
    (
        "NO_INTO_OUTFILE",
        r"\bINTO\s+OUTFILE\b",
        "critical",
        "INTO OUTFILE detected — potential data exfiltration risk.",
    ),
    (
        "NO_LOAD_DATA_INFILE",
        r"\bLOAD\s+DATA\s+INFILE\b",
        "high",
        "LOAD DATA INFILE detected — can be exploited for file-system access.",
    ),
    (
        "COMMENT_INJECTION",
        r"(--|#|/\*.*?\*/)",
        "low",
        "SQL comment detected — verify it is not masking injection.",
    ),
    (
        "SELECT_STAR",
        r"\bSELECT\s+\*",
        "low",
        "SELECT * detected — prefer explicit column lists for clarity and performance.",
    ),
    (
        "NO_WHERE_ON_SELECT",
        r"\bSELECT\b(?!.*\bWHERE\b)",
        "low",
        "SELECT without WHERE — may perform a full-table scan.",
    ),
]


def _max_level(a: str, b: str) -> str:
    return a if _LEVEL_ORDER[a] >= _LEVEL_ORDER[b] else b


def _get_line(sql: str, match_start: int) -> int:
    return sql[:match_start].count("\n") + 1


def _check_dml_without_where(sql_upper: str, sql: str, keyword: str, rule_id: str, message: str) -> List[RiskItem]:
    """Detect DELETE/UPDATE without WHERE clause."""
    items: List[RiskItem] = []
    # Find all keyword occurrences
    for m in re.finditer(rf"\b{keyword}\b", sql_upper):
        start = m.start()
        # Skip "ON UPDATE ..." patterns (e.g. MySQL ON UPDATE CURRENT_TIMESTAMP)
        preceding = sql_upper[max(0, start - 10):start].strip()
        if preceding.endswith("ON"):
            continue
        # Extract the statement fragment from here
        fragment = sql_upper[start : start + 500]
        # Check if WHERE appears before the next statement delimiter
        next_stmt = re.search(r";|\Z", fragment)
        end = next_stmt.end() if next_stmt else len(fragment)
        stmt_fragment = fragment[:end]
        if not re.search(r"\bWHERE\b", stmt_fragment):
            items.append(
                RiskItem(
                    level="high",  # type: ignore[arg-type]
                    rule=rule_id,
                    message=message,
                    line=_get_line(sql, start),
                )
            )
    return items


def check_sql(sql: str) -> RiskReport:
    """Run all risk rules against the given SQL string and return a report."""
    items: List[RiskItem] = []
    overall = "safe"
    sql_upper = sql.upper()

    for rule_id, pattern, level, message in _RULES:
        if rule_id == "DELETE_WITHOUT_WHERE":
            found = _check_dml_without_where(sql_upper, sql, "DELETE", rule_id, message)
            items.extend(found)
            for f in found:
                overall = _max_level(overall, f.level)
            continue

        if rule_id == "UPDATE_WITHOUT_WHERE":
            found = _check_dml_without_where(sql_upper, sql, "UPDATE", rule_id, message)
            items.extend(found)
            for f in found:
                overall = _max_level(overall, f.level)
            continue

        if pattern is None:
            continue

        for m in re.finditer(pattern, sql_upper, re.DOTALL):
            items.append(
                RiskItem(
                    level=level,  # type: ignore[arg-type]
                    rule=rule_id,
                    message=message,
                    line=_get_line(sql, m.start()),
                )
            )
            overall = _max_level(overall, level)

    # Deduplicate by rule (keep first occurrence)
    seen_rules: set = set()
    deduped: List[RiskItem] = []
    for item in items:
        if item.rule not in seen_rules:
            deduped.append(item)
            seen_rules.add(item.rule)

    summary_parts = [f"[{i.level.upper()}] {i.message}" for i in deduped]
    summary = "\n".join(summary_parts) if summary_parts else "No risk issues detected."

    return RiskReport(
        overall_level=overall,  # type: ignore[arg-type]
        items=deduped,
        summary=summary,
    )


def lint_sql(sql: str) -> List[str]:
    """Parse and lint SQL using sqlparse; return list of warnings."""
    warnings: List[str] = []
    try:
        statements = sqlparse.parse(sql)
    except Exception:
        warnings.append("Could not parse SQL — check for syntax errors.")
        return warnings

    for i, stmt in enumerate(statements, 1):
        if not stmt.get_type():
            warnings.append(f"Statement {i}: Unknown statement type — may be invalid SQL.")
        # Check for unmatched parentheses
        depth = 0
        for token in stmt.flatten():
            if token.ttype is sqlparse.tokens.Punctuation:
                if token.value == "(":
                    depth += 1
                elif token.value == ")":
                    depth -= 1
        if depth != 0:
            warnings.append(f"Statement {i}: Unmatched parentheses detected.")

    return warnings
