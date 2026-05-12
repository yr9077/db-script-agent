"""Tests for the dialect service."""
import pytest
from app.services.dialect_service import get_dialect_hints, get_system_prompt, adapt_sql_for_dialect


def test_mysql_hints():
    hints = get_dialect_hints("mysql")
    assert hints["auto_increment"] == "AUTO_INCREMENT"
    assert hints["quote_char"] == "`"


def test_postgresql_hints():
    hints = get_dialect_hints("postgresql")
    assert hints["auto_increment"] == "SERIAL"
    assert hints["bool_type"] == "BOOLEAN"


def test_sqlite_hints():
    hints = get_dialect_hints("sqlite")
    assert hints["auto_increment"] == "AUTOINCREMENT"
    assert hints["string_type"] == "TEXT"


def test_unknown_dialect_falls_back_to_mysql():
    hints = get_dialect_hints("oracle")
    assert hints["quote_char"] == "`"


def test_system_prompt_contains_dialect():
    prompt = get_system_prompt("postgresql", "ddl")
    assert "POSTGRESQL" in prompt.upper()


def test_system_prompt_contains_script_type():
    prompt = get_system_prompt("mysql", "dml")
    assert "SELECT" in prompt or "INSERT" in prompt or "DML" in prompt.upper()


def test_adapt_mysql_to_postgresql():
    sql = "CREATE TABLE `users` (id INT AUTO_INCREMENT PRIMARY KEY) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
    result = adapt_sql_for_dialect(sql, "mysql", "postgresql")
    assert "SERIAL" in result
    assert "AUTO_INCREMENT" not in result


def test_adapt_mysql_to_sqlite():
    sql = "CREATE TABLE `users` (id INT AUTO_INCREMENT PRIMARY KEY);"
    result = adapt_sql_for_dialect(sql, "mysql", "sqlite")
    assert "AUTOINCREMENT" in result
    assert "AUTO_INCREMENT" not in result


def test_adapt_same_dialect_is_noop():
    sql = "SELECT * FROM users;"
    result = adapt_sql_for_dialect(sql, "mysql", "mysql")
    assert result == sql
