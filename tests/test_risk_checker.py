"""Tests for the risk checker service."""
import pytest
from app.services.risk_checker import check_sql, lint_sql


def test_safe_select():
    report = check_sql("SELECT id, name FROM users WHERE id = 1;")
    assert report.overall_level == "safe"
    assert not report.items


def test_drop_table_is_critical():
    report = check_sql("DROP TABLE users;")
    assert report.overall_level == "critical"
    rules = [i.rule for i in report.items]
    assert "NO_DROP_TABLE" in rules


def test_truncate_is_high():
    report = check_sql("TRUNCATE TABLE orders;")
    assert report.overall_level in ("high", "critical")
    rules = [i.rule for i in report.items]
    assert "NO_TRUNCATE" in rules


def test_delete_without_where():
    report = check_sql("DELETE FROM users;")
    rules = [i.rule for i in report.items]
    assert "DELETE_WITHOUT_WHERE" in rules


def test_delete_with_where_is_safe():
    report = check_sql("DELETE FROM users WHERE id = 5;")
    rules = [i.rule for i in report.items]
    assert "DELETE_WITHOUT_WHERE" not in rules


def test_update_without_where():
    report = check_sql("UPDATE users SET name = 'x';")
    rules = [i.rule for i in report.items]
    assert "UPDATE_WITHOUT_WHERE" in rules


def test_update_with_where_is_safe():
    report = check_sql("UPDATE users SET name = 'x' WHERE id = 1;")
    rules = [i.rule for i in report.items]
    assert "UPDATE_WITHOUT_WHERE" not in rules


def test_select_star():
    report = check_sql("SELECT * FROM products;")
    rules = [i.rule for i in report.items]
    assert "SELECT_STAR" in rules


def test_drop_database_is_critical():
    report = check_sql("DROP DATABASE mydb;")
    assert report.overall_level == "critical"


def test_grant_all_is_high():
    report = check_sql("GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';")
    rules = [i.rule for i in report.items]
    assert "NO_GRANT_ALL" in rules


def test_into_outfile_is_critical():
    report = check_sql("SELECT * INTO OUTFILE '/tmp/dump.csv' FROM users;")
    assert report.overall_level == "critical"


def test_multiple_issues_highest_wins():
    sql = "DROP TABLE users; DELETE FROM orders;"
    report = check_sql(sql)
    assert report.overall_level == "critical"


def test_on_update_current_timestamp_not_flagged():
    """ON UPDATE CURRENT_TIMESTAMP is a column option, not a DML UPDATE statement."""
    sql = """CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );"""
    report = check_sql(sql)
    rules = [i.rule for i in report.items]
    assert "UPDATE_WITHOUT_WHERE" not in rules


def test_lint_valid_sql():
    warnings = lint_sql("SELECT id FROM users WHERE id = 1;")
    # No unmatched parens
    paren_warnings = [w for w in warnings if "parentheses" in w.lower()]
    assert not paren_warnings


def test_lint_unmatched_parens():
    warnings = lint_sql("SELECT id FROM users WHERE (id = 1;")
    paren_warnings = [w for w in warnings if "parentheses" in w.lower()]
    assert paren_warnings
