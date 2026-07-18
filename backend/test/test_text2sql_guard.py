"""Parameterized safety tests for :mod:`app.core.text2sql_guard`.

The test suite is intentionally aggressive: it asserts both the
positive cases (legitimate SELECTs from the whitelisted industry
schema) and the negative cases (every category of adversarial input
the previous regex guard would have missed). Sqlglot's grammar
fall-backs are exercised too - the guard must remain deterministic
even when sqlglot parses a statement as a Command or flattens a CTE.

The tests run against :class:`SQLGuard` directly without spinning up
a database. Wire-up with :class:`Text2SQLService` is covered by a
separate, smaller test in :mod:`test_security_boundaries`.
"""

from __future__ import annotations

import pytest

from app.core.text2sql_guard import (
    ALLOWED_TABLES,
    GUARD_COMMENT_DENIED,
    GUARD_COPY_DENIED,
    GUARD_DDL_DENIED,
    GUARD_DML_DENIED,
    GUARD_EMPTY,
    GUARD_EXPLAIN_DENIED,
    GUARD_MULTI_STATEMENT,
    GUARD_OK,
    GUARD_PARSE_FAIL,
    GUARD_PROCEDURAL_DENIED,
    GUARD_ROW_CAP_EXCEEDED,
    GUARD_SYSTEM_SCHEMA_DENIED,
    GUARD_TABLE_NOT_ALLOWED,
    GUARD_COLUMN_NOT_ALLOWED,
    SQLGuard,
    default_guard,
)


# ---------------------------------------------------------------------------
# Helper guards
# ---------------------------------------------------------------------------


@pytest.fixture
def guard() -> SQLGuard:
    return SQLGuard(max_rows=50)


# ---------------------------------------------------------------------------
# Positive cases - legitimate SELECTs against the whitelist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        # plain single-table SELECT
        "SELECT industry_name FROM industry_stats LIMIT 5",
        "SELECT industry_name, metric_value FROM industry_stats WHERE year = 2024",
        # column with table prefix
        "SELECT industry_stats.industry_name, industry_stats.metric_value FROM industry_stats",
        # JOIN with two whitelisted tables
        (
            "SELECT s.industry_name, c.company_name FROM industry_stats s "
            "JOIN company_data c ON s.year = c.year LIMIT 10"
        ),
        # aggregate + GROUP BY
        (
            "SELECT industry_name, COUNT(*) FROM industry_stats "
            "GROUP BY industry_name"
        ),
        # HAVING
        (
            "SELECT industry_name, AVG(metric_value) FROM industry_stats "
            "GROUP BY industry_name HAVING AVG(metric_value) > 80"
        ),
        # ORDER BY whitelisted column (within cap)
        "SELECT id FROM industry_stats ORDER BY id LIMIT 40",
        # subquery in WHERE
        (
            "SELECT * FROM industry_stats WHERE year IN "
            "(SELECT year FROM industry_stats WHERE year > 2020)"
        ),
        # UNION of whitelisted tables (independent scopes)
        (
            "SELECT industry_name FROM industry_stats UNION "
            "SELECT company_name FROM company_data"
        ),
        # nested CTE
        (
            "WITH a AS (SELECT * FROM industry_stats), "
            "b AS (SELECT * FROM a) SELECT * FROM b LIMIT 50"
        ),
        # CTE referencing whitelist
        (
            "WITH x AS (SELECT industry_name FROM industry_stats) "
            "SELECT * FROM x"
        ),
        # CROSS JOIN
        (
            "SELECT a.industry_name, b.industry_name FROM industry_stats a "
            "CROSS JOIN industry_stats b LIMIT 10"
        ),
        # CASE / NULLIF / CAST
        (
            "SELECT CASE WHEN year > 2020 THEN 'recent' ELSE 'old' END "
            "FROM industry_stats"
        ),
        (
            "SELECT NULLIF(industry_name, '') FROM industry_stats"
        ),
        "SELECT CAST(metric_value AS INT) FROM industry_stats",
        # JSON path
        "SELECT extra_data->>'key' FROM company_data LIMIT 5",
        # LIKE / BETWEEN
        (
            "SELECT industry_name FROM industry_stats "
            "WHERE industry_name LIKE '%芯片%' LIMIT 20"
        ),
        "SELECT metric_value FROM industry_stats WHERE year BETWEEN 2020 AND 2025",
        # multiline statement
        (
            "SELECT\n  industry_name,\n  COUNT(*)\nFROM industry_stats\n"
            "WHERE year = 2024\nGROUP BY industry_name"
        ),
    ],
)
def test_positive_selects_pass(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    assert result.ok, f"{sql!r} unexpectedly rejected: {result.code} {result.message}"
    assert result.code == GUARD_OK
    assert result.backend == "sqlglot"
    assert result.sql_normalized is not None
    # every positive case must enforce the row cap by either keeping the
    # explicit LIMIT or appending one.
    assert "LIMIT" in result.sql_normalized.upper()


# ---------------------------------------------------------------------------
# DDL/DML rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,code",
    [
        ("DROP TABLE industry_stats", GUARD_DDL_DENIED),
        ("CREATE TABLE foo (id INT)", GUARD_DDL_DENIED),
        ("ALTER TABLE industry_stats ADD COLUMN foo INT", GUARD_DDL_DENIED),
        ("TRUNCATE TABLE industry_stats", GUARD_DDL_DENIED),
        ("DELETE FROM policy_data", GUARD_DML_DENIED),
        ("UPDATE industry_stats SET metric_value = 0", GUARD_DML_DENIED),
        (
            "INSERT INTO company_data (company_name) VALUES ('x')",
            GUARD_DML_DENIED,
        ),
    ],
)
def test_ddl_dml_rejected(guard: SQLGuard, sql: str, code: str) -> None:
    result = guard.check(sql)
    assert not result.ok
    assert result.code == code


# ---------------------------------------------------------------------------
# Multi-statement rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE industry_stats",
        "SELECT 1; SELECT 2",
        "SELECT 1;\nDROP TABLE industry_stats",
        "SELECT 1; -- innocent comment\nDROP TABLE industry_stats",
    ],
)
def test_multi_statement_rejected(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    if "comment" in sql:
        # comment is rejected first if present
        assert result.code in (GUARD_COMMENT_DENIED, GUARD_MULTI_STATEMENT)
    else:
        assert result.code == GUARD_MULTI_STATEMENT


# ---------------------------------------------------------------------------
# Comment rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 -- trailing comment",
        "SELECT 1 --two-dashes",
        "SELECT 1 /* inline block */",
        "SELECT 1 /* multi\nline */ FROM industry_stats",
        "SELECT 1 FROM industry_stats LIMIT 10; -- evil trailing",
        "SELECT 1 FROM industry_stats -- mid-statement\nWHERE year=2024",
    ],
)
def test_comments_rejected(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    assert result.code == GUARD_COMMENT_DENIED


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM industry_stats WHERE industry_name = 'foo -- bar'",
        "SELECT * FROM industry_stats WHERE industry_name = 'DROP TABLE'",
        "SELECT * FROM industry_stats WHERE industry_name = 'a /* b */ c'",
        # the keyword ``DROP`` inside a literal must NOT be lex-rejected
        "SELECT * FROM industry_stats WHERE source = 'INFORMATION_SCHEMA'",
    ],
)
def test_string_literals_with_dangerous_text_pass(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    assert result.ok, f"got {result.code}: {result.message}"


# ---------------------------------------------------------------------------
# System schema rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM pg_catalog.pg_user",
        "SELECT pg_sleep(10)",
        "SELECT * FROM pg_class",
        # function calls that scan file system
        "SELECT * FROM pg_read_file('/etc/passwd')",
        "SELECT 1 FROM users",
    ],
)
def test_system_or_unknown_table_rejected(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    if "users" in sql:
        # unknown table but lex-level clean: TABLE_NOT_ALLOWED
        assert result.code == GUARD_TABLE_NOT_ALLOWED
    else:
        # system schema / dangerous function: SYSTEM_SCHEMA_DENIED
        assert result.code == GUARD_SYSTEM_SCHEMA_DENIED


# ---------------------------------------------------------------------------
# EXPLAIN / COPY / DO block rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,code",
    [
        ("EXPLAIN SELECT * FROM industry_stats", GUARD_EXPLAIN_DENIED),
        ("EXPLAIN ANALYZE SELECT * FROM industry_stats", GUARD_EXPLAIN_DENIED),
        ("COPY industry_stats TO '/tmp/x'", GUARD_COPY_DENIED),
        (
            "DO $$ BEGIN RAISE NOTICE 'foo'; END $$",
            GUARD_PROCEDURAL_DENIED,
        ),
    ],
)
def test_explain_copy_do_rejected(guard: SQLGuard, sql: str, code: str) -> None:
    result = guard.check(sql)
    # when sqlglot falls back to a Command for some of the above, the
    # top-level type check rejects first.
    assert result.code in (code, GUARD_PARSE_FAIL)
    if result.code == code:
        return
    # sqlglot's parser may outright refuse the syntax; treat that as
    # an acceptable rejection.
    assert not result.ok


# ---------------------------------------------------------------------------
# Row cap enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,cap,expect_ok",
    [
        ("SELECT id FROM industry_stats LIMIT 49", 50, True),
        ("SELECT id FROM industry_stats LIMIT 50", 50, True),
        ("SELECT id FROM industry_stats LIMIT 51", 50, False),
        ("SELECT id FROM industry_stats LIMIT 1000", 50, False),
    ],
)
def test_row_cap(sql: str, cap: int, expect_ok: bool) -> None:
    g = SQLGuard(max_rows=cap)
    r = g.check(sql)
    if expect_ok:
        assert r.ok, f"{sql!r} unexpected reject {r.code}"
    else:
        assert r.code == GUARD_ROW_CAP_EXCEEDED


def test_missing_limit_is_appended(guard: SQLGuard) -> None:
    r = guard.check("SELECT id FROM industry_stats")
    assert r.ok
    assert "LIMIT" in (r.sql_normalized or "").upper()
    # the cap is appended as the last token sequence
    assert r.sql_normalized.rstrip().endswith("LIMIT 50")


# ---------------------------------------------------------------------------
# Empty + parse failures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,code",
    [
        ("", GUARD_EMPTY),
        ("   \n   ", GUARD_EMPTY),
        # structurally broken
        ("SELEKT 1", GUARD_PARSE_FAIL),
        ("SELECT FROM", GUARD_PARSE_FAIL),
    ],
)
def test_empty_and_parse_fail(guard: SQLGuard, sql: str, code: str) -> None:
    r = guard.check(sql)
    assert r.code == code


# ---------------------------------------------------------------------------
# Defense in depth: WITH ... DELETE / subqueries with DML hints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql,code",
    [
        (
            "WITH x AS (DELETE FROM industry_stats RETURNING *) SELECT * FROM x",
            GUARD_DML_DENIED,
        ),
        (
            "WITH x AS (UPDATE industry_stats SET metric_value = 0) "
            "SELECT * FROM x",
            GUARD_DML_DENIED,
        ),
    ],
)
def test_cte_with_dml_rejected(guard: SQLGuard, sql: str, code: str) -> None:
    r = guard.check(sql)
    # Sqlglot parses the CTE-with-DML as a Select (fallback). The deep
    # AST walk should still surface the hidden DELETE/UPDATE.
    assert not r.ok
    assert r.code == code


def test_subquery_with_delete_attempt(guard: SQLGuard) -> None:
    # Sqlglot's parser refuses to place a DELETE inside an IN list, but
    # we still want the guard to fail closed if a future sqlglot version
    # accepts it. Today this hits the PARSE_FAIL path.
    sql = (
        "SELECT * FROM industry_stats WHERE id IN "
        "(DELETE FROM industry_stats RETURNING id)"
    )
    r = guard.check(sql)
    assert not r.ok
    assert r.code in (GUARD_DML_DENIED, GUARD_PARSE_FAIL)


# ---------------------------------------------------------------------------
# Column whitelist
# ---------------------------------------------------------------------------


def test_column_legitimate(guard: SQLGuard) -> None:
    sql = "SELECT industry_name, metric_value FROM industry_stats"
    r = guard.check(sql)
    assert r.ok


def test_column_not_in_whitelist(guard: SQLGuard) -> None:
    sql = "SELECT industry_name, password FROM industry_stats"
    r = guard.check(sql)
    assert r.code == GUARD_COLUMN_NOT_ALLOWED
    assert any("password" in v for v in r.column_violations)


def test_qualified_column_owner_not_in_whitelist(guard: SQLGuard) -> None:
    # referencing a column from a table that itself is not on the
    # allow-list: the table violation surfaces first.
    sql = "SELECT users.password FROM users"
    r = guard.check(sql)
    assert not r.ok
    assert r.code == GUARD_TABLE_NOT_ALLOWED


def test_order_by_unknown_column(guard: SQLGuard) -> None:
    sql = "SELECT industry_name FROM industry_stats ORDER BY password"
    r = guard.check(sql)
    assert r.code == GUARD_COLUMN_NOT_ALLOWED


# ---------------------------------------------------------------------------
# Dual-backend cross-check
# ---------------------------------------------------------------------------


def test_dual_backend_with_matching_inputs() -> None:
    g = SQLGuard(max_rows=50, backend="dual")
    r = g.check("SELECT industry_name FROM industry_stats")
    assert r.ok


def test_dual_backend_pglast_rejects_when_sqlglot_would_pass(monkeypatch) -> None:
    """If pglast disagrees with sqlglot and reports an unsafe statement,
    the guard returns the pglast verdict. This test monkey-patches the
    pglast bridge to return a forced rejection."""

    class FakeGuard(SQLGuard):
        def __init__(self) -> None:
            super().__init__(max_rows=50, backend="dual")

        def _check_pglast(self_inner, sql: str):  # noqa: D401
            from app.core.text2sql_guard import GuardResult, GUARD_PARSE_FAIL

            return GuardResult(
                ok=False,
                code=GUARD_PARSE_FAIL,
                message="forced pglast disagreement",
                backend="pglast",
            )

    g = FakeGuard()
    r = g.check("SELECT 1 FROM industry_stats")
    assert r.code == GUARD_PARSE_FAIL
    assert r.backend == "pglast"


def test_invalid_backend_argument() -> None:
    with pytest.raises(ValueError):
        SQLGuard(backend="unknown")


def test_invalid_max_rows_argument() -> None:
    with pytest.raises(ValueError):
        SQLGuard(max_rows=0)
    with pytest.raises(ValueError):
        SQLGuard(max_rows=-5)


# ---------------------------------------------------------------------------
# Whitelist contract - schema drift safety net
# ---------------------------------------------------------------------------


def test_allowed_tables_contain_only_known_models() -> None:
    """If someone breaks the contract by removing one of the model
    tables, this test fires."""

    assert set(ALLOWED_TABLES) == {
        "industry_stats",
        "company_data",
        "policy_data",
    }
    # Every allow-listed column must contain the ``id`` primary key.
    for table, cols in ALLOWED_TABLES.items():
        assert "id" in cols, f"{table} allow-list missing primary key"
        # and at least one semantic column beyond id/created_at/updated_at
        semantic = cols - {"id", "created_at", "updated_at"}
        assert semantic, f"{table} allow-list only contains bookkeeping columns"


def test_default_guard_uses_default_max() -> None:
    g = default_guard()
    assert g.max_rows > 0
    assert g.backend == "sqlglot"
