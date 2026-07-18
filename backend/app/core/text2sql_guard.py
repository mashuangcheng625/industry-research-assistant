"""Text2SQL safety guard.

This module is the P1-1 replacement for the previous keyword-regex
``Text2SQLService.validate_sql`` implementation. It never trusts
substring matching against ``DROP``, ``DELETE``, ``--`` and friends:

* The input SQL is parsed into an AST by :mod:`sqlglot` (default) or by
  :mod:`pglast` (a libpg_query binding) when running in dual-engine mode.
* The AST is then walked to enforce:
    - exactly one SELECT statement is allowed at top level. CTEs are
      only allowed if they themselves contain SELECT.
    - DDL/DML/explain/COPY/DO/CALL/MERGE/procedural nodes are rejected
      before any whitelist check.
    - every referenced table is on the table allow-list and every
      referenced column is allowed for that table (or for ``*``).
    - system schemas (``pg_catalog``, ``information_schema``,
      ``pg_*``) and any un-recognised schema are rejected.
    - a hard ``max_rows`` cap is enforced either by reading an explicit
      LIMIT clause or by appending one. ``UNION ALL`` that targets
      non-allow-listed tables is rejected during the same walk.
* The guard returns a structured :class:`GuardResult` and never raises
  for known-bad input. Parser exceptions and explicit empty input also
  map to deterministic error codes, which the test suite can assert.

The module imports :mod:`sqlglot` eagerly and imports :mod:`pglast`
lazily. The default backend is sqlglot because pglast links against
libpg_query and is only needed when the dual-engine cross-check is on
(set ``backend='dual'`` or ``TEXT2SQL_GUARD_BACKEND=dual``).
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import sqlglot
    from sqlglot import exp
    _SQLGLOT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by tests in degraded env
    sqlglot = None  # type: ignore[assignment]
    exp = None  # type: ignore[assignment]
    _SQLGLOT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Allow-list
# ---------------------------------------------------------------------------

# Built from the SQLAlchemy models in ``backend/app/models/industry_data.py``.
# If those models change, regenerate this table by importing them and reading
# ``__table__.columns``. For now we keep the explicit frozen mapping so the
# guard is safe to use without SQLAlchemy side effects at import time.
ALLOWED_TABLES: Dict[str, FrozenSet[str]] = {
    "industry_stats": frozenset({
        "id", "industry_name", "metric_name", "metric_value", "unit",
        "year", "quarter", "month", "region", "source", "source_url",
        "notes", "created_at", "updated_at",
    }),
    "company_data": frozenset({
        "id", "company_name", "stock_code", "industry", "sub_industry",
        "revenue", "net_profit", "gross_margin", "market_cap",
        "employees", "market_share", "year", "quarter", "data_source",
        "extra_data", "created_at", "updated_at",
    }),
    "policy_data": frozenset({
        "id", "policy_name", "policy_number", "department", "level",
        "publish_date", "effective_date", "expiry_date", "category",
        "industry", "summary", "key_points", "full_text_url",
        "impact_level", "affected_entities", "created_at", "updated_at",
    }),
}

ALLOWED_SCHEMAS: FrozenSet[str] = frozenset({"public"})


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

GUARD_OK = "OK"
GUARD_EMPTY = "EMPTY"
GUARD_PARSE_FAIL = "PARSE_FAIL"
GUARD_MULTI_STATEMENT = "MULTI_STATEMENT"
GUARD_DDL_DENIED = "DDL_DENIED"
GUARD_DML_DENIED = "DML_DENIED"
GUARD_EXPLAIN_DENIED = "EXPLAIN_DENIED"
GUARD_PROCEDURAL_DENIED = "PROCEDURAL_DENIED"
GUARD_COPY_DENIED = "COPY_DENIED"
GUARD_COMMENT_DENIED = "COMMENT_DENIED"
GUARD_SYSTEM_SCHEMA_DENIED = "SYSTEM_SCHEMA_DENIED"
GUARD_TABLE_NOT_ALLOWED = "TABLE_NOT_ALLOWED"
GUARD_COLUMN_NOT_ALLOWED = "COLUMN_NOT_ALLOWED"
GUARD_ROW_CAP_EXCEEDED = "ROW_CAP_EXCEEDED"


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    code: str
    message: str
    sql_normalized: Optional[str] = None
    backend: str = "sqlglot"
    column_violations: Tuple[str, ...] = field(default_factory=tuple)
    table_violations: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Lex-level helpers
# ---------------------------------------------------------------------------

# Token-level classification. The alternation pattern matches a SQL string
# literal, a double-quoted identifier or a comment - in priority order. We
# iterate the matches and use captured groups to decide whether the
# substring was a comment (always rejected) or a string/identifier (allowed
# content that may itself contain ``--`` characters).
_COMMENT_SCAN = re.compile(
    r"""
    '(?:''|[^'])*'                  |   # group 1: SQL string literal
    "(?:"\\.|[^"\\])*"              |   # group 2: SQL identifier
    (--[^\n\r]*|/\*[\s\S]*?\*/)          # group 3: comment (no capture - presence is enough)
    """,
    re.VERBOSE,
)


def _has_forbidden_substring(sql: str) -> bool:
    """Identify common system-schema tokens outside string literals. We do
    not lean on this; it is a cheap belt to the AST-level suspenders."""

    forbidden = (
        "INFORMATION_SCHEMA",
        "PG_CATALOG",
        "PG_STAT",
        "PG_CLASS",
        "PG_ROLES",
        "PG_SLEEP",
        "PG_READ_FILE",
        "PG_WRITE_FILE",
        "WAITFOR",
        "BENCHMARK(",
        "DBMS_",
        "UTL_HTTP",
        "LOAD_FILE",
        "OUTFILE",
    )

    cleaned_parts = []
    last = 0
    for m in _COMMENT_SCAN.finditer(sql):
        cleaned_parts.append(sql[last:m.start()])
        token = m.group(0)
        # Keep strings/identifiers (replace with spaces) but drop comments.
        if token.startswith(("'", '"')):
            cleaned_parts.append(" ")
        last = m.end()
    cleaned_parts.append(sql[last:])
    upper = "".join(cleaned_parts).upper()
    return any(token in upper for token in forbidden)


def _contains_comment(sql: str) -> bool:
    """Return True if ``sql`` contains a SQL comment anywhere outside a
    string literal. ``-- ``, ``/*`` etc. that appear *inside* a string are
    ignored because the pattern consumes the literal first."""

    pos = 0
    while True:
        m = _COMMENT_SCAN.search(sql, pos)
        if not m:
            return False
        matched = m.group(0)
        if matched.startswith("'") or matched.startswith('"'):
            pos = m.end()
            continue
        return True


# ---------------------------------------------------------------------------
# SQLGuard
# ---------------------------------------------------------------------------


class SQLGuard:
    """Stateless SQL safety guard.

    Use :meth:`check` to validate a SQL string. ``backend`` accepts
    ``"sqlglot"`` (default) or ``"dual"`` (sqlglot + pglast cross-check).
    """

    def __init__(
        self,
        max_rows: int = 100,
        allowed_tables: Optional[Dict[str, FrozenSet[str]]] = None,
        backend: str = "sqlglot",
    ) -> None:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        if backend not in ("sqlglot", "dual"):
            raise ValueError("backend must be 'sqlglot' or 'dual'")
        self.max_rows = int(max_rows)
        self.backend = backend
        self.allowed_tables: Dict[str, FrozenSet[str]] = (
            {k: set(v) for k, v in allowed_tables.items()}
            if allowed_tables is not None
            else {k: set(v) for k, v in ALLOWED_TABLES.items()}
        )
        self._pglast_lock = threading.Lock()
        self._pglast_warned = False

    # --- public ----------------------------------------------------------

    def check(self, sql: str) -> GuardResult:
        if not sql or not sql.strip():
            return GuardResult(
                ok=False,
                code=GUARD_EMPTY,
                message="SQL 语句为空",
                backend=self.backend,
            )

        # 1. Lex-level: comments (string-blind).
        if _contains_comment(sql):
            return GuardResult(
                ok=False,
                code=GUARD_COMMENT_DENIED,
                message="SQL 中不允许注释或字面量外的破折号",
                backend=self.backend,
            )

        # 2. Lex-level: forbidden substrings (system schemas, time-spending
        #    functions). cheap belt to AST-level suspenders.
        if _has_forbidden_substring(sql):
            return GuardResult(
                ok=False,
                code=GUARD_SYSTEM_SCHEMA_DENIED,
                message="SQL 命中了被禁用的系统表或时间消耗函数",
                backend=self.backend,
            )

        if not _SQLGLOT_AVAILABLE:
            return GuardResult(
                ok=False,
                code=GUARD_PARSE_FAIL,
                message="sqlglot 未安装；guard 不可用",
                backend="sqlglot",
            )

        # 3. Parse once with sqlglot.
        try:
            statements = sqlglot.parse(sql, dialect="postgres")
        except sqlglot.errors.ParseError as exc:
            return GuardResult(
                ok=False,
                code=GUARD_PARSE_FAIL,
                message=f"SQL 无法解析: {exc}",
                backend="sqlglot",
            )
        if not statements:
            return GuardResult(
                ok=False,
                code=GUARD_PARSE_FAIL,
                message="SQL 解析返回空",
                backend="sqlglot",
            )
        if len(statements) > 1:
            return GuardResult(
                ok=False,
                code=GUARD_MULTI_STATEMENT,
                message="不允许多条 SQL 语句",
                backend="sqlglot",
            )

        parsed: exp.Expression = statements[0]

        # 4. Optional pglast cross-check.
        if self.backend == "dual":
            pglast_result = self._check_pglast(sql)
            if isinstance(pglast_result, GuardResult) and not pglast_result.ok:
                return pglast_result

        # 5. Type check (must be SELECT / UNION / CTE-with-select-only).
        cte_aliases: List[str] = []
        if not self._is_select_only(parsed, cte_aliases):
            return GuardResult(
                ok=False,
                code=self._type_violation_code(parsed),
                message="仅允许顶层 SELECT（含递归 CTE / UNION）",
                backend="sqlglot",
            )

        # Also pick up CTE aliases that sqlglot flattened into the Select
        # (the ``with_`` arg). This catches WITH ... chained over nested
        # SELECTs the recursion above may have missed.
        for alias in self._collect_cte_aliases(parsed):
            if alias not in cte_aliases:
                cte_aliases.append(alias)

        # 5b. sqlglot can swallow WITH ... DELETE/UPDATE etc. into a
        #     Select when the dialect's grammar falls back. Walk the tree
        #     for any forbidden operation type *anywhere* - even deeply
        #     nested in a CTE.
        forbidden_op_code = self._find_forbidden_operation(parsed)
        if forbidden_op_code is not None:
            return GuardResult(
                ok=False,
                code=forbidden_op_code,
                message="SQL 在子句或 CTE 中包含被禁用的操作",
                backend="sqlglot",
            )

        # 6. Whitelist walk.
        table_violations: List[str] = []
        column_violations: List[str] = []
        try:
            self._walk_for_whitelist(parsed, cte_aliases, table_violations, column_violations)
        except _SchemaViolation as exc:
            return GuardResult(
                ok=False,
                code=exc.code,
                message=str(exc),
                backend="sqlglot",
            )

        if table_violations:
            return GuardResult(
                ok=False,
                code=GUARD_TABLE_NOT_ALLOWED,
                message="引用了未在白名单内的表",
                backend="sqlglot",
                table_violations=tuple(table_violations),
            )
        if column_violations:
            return GuardResult(
                ok=False,
                code=GUARD_COLUMN_NOT_ALLOWED,
                message="引用了未在白名单内的列",
                backend="sqlglot",
                column_violations=tuple(column_violations),
            )

        # 7. Row cap.
        limit_value = self._extract_limit(parsed)
        if limit_value is not None and limit_value > self.max_rows:
            return GuardResult(
                ok=False,
                code=GUARD_ROW_CAP_EXCEEDED,
                message=f"显式 LIMIT {limit_value} 超过 max_rows={self.max_rows}",
                backend="sqlglot",
            )

        normalized = self._append_limit_if_missing(sql, parsed)
        return GuardResult(
            ok=True,
            code=GUARD_OK,
            message="通过",
            sql_normalized=normalized,
            backend="sqlglot",
        )

    # --- sqlglot traversal -----------------------------------------------

    def _is_select_only(self, node: "exp.Expression", cte_aliases: List[str]) -> bool:
        if isinstance(node, exp.Select):
            return True
        if isinstance(node, exp.Union):
            for child in node.expressions:
                if not self._is_select_only(child, cte_aliases):
                    return False
            return True
        if isinstance(node, exp.With):
            for cte in (node.args.get("expressions") or []):
                alias = (cte.alias_or_name or cte.name or "").lower()
                if alias:
                    cte_aliases.append(alias)
                inner = cte.args.get("query")
                if inner is None or not self._is_select_only(inner, cte_aliases):
                    return False
            final = node.args.get("this") or node.args.get("query")
            return final is not None and self._is_select_only(final, cte_aliases)
        return False

    def _collect_cte_aliases(self, parsed: "exp.Expression") -> List[str]:
        """Walk the parsed Select / Union for any ``WITH <alias> AS (...)``
        clauses and accumulate the alias names. Sqlglot persists the
        original With node under ``with_``; CTE unions and nested SELECTs
        can carry their own copies."""

        aliases: List[str] = []
        for with_node in parsed.find_all(exp.With):
            for cte in (with_node.args.get("expressions") or []):
                alias = (cte.alias_or_name or cte.name or "").lower()
                if alias:
                    aliases.append(alias)
        return aliases

    def _type_violation_code(self, node: "exp.Expression") -> str:
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Merge)):
            return GUARD_DML_DENIED
        if isinstance(node, (exp.Create, exp.Alter, exp.Drop, exp.TruncateTable)):
            return GUARD_DDL_DENIED
        if isinstance(node, exp.Copy):
            return GUARD_COPY_DENIED
        if isinstance(node, exp.Command):
            head = self._command_head(node).upper()
            if head.startswith("EXPLAIN"):
                return GUARD_EXPLAIN_DENIED
            if head.startswith("COPY"):
                return GUARD_COPY_DENIED
            if head in ("DO", "CALL", "VACUUM", "ANALYZE"):
                return GUARD_PROCEDURAL_DENIED
            return GUARD_DDL_DENIED
        if isinstance(node, exp.CTE):
            return GUARD_DML_DENIED
        # Unknown but not select.
        return GUARD_DDL_DENIED

    @staticmethod
    def _find_forbidden_operation(root: "exp.Expression") -> Optional[str]:
        """Walk the AST and return a guard code if any forbidden operation
        appears anywhere in the tree. Used as a defense in depth for CTEs
        that sqlglot may mis-parse as plain Select."""

        forbidden_dml = (exp.Insert, exp.Update, exp.Delete, exp.Merge)
        forbidden_ddl = (exp.Create, exp.Alter, exp.Drop, exp.TruncateTable)
        for node in root.walk():
            if isinstance(node, forbidden_dml):
                return GUARD_DML_DENIED
            if isinstance(node, forbidden_ddl):
                return GUARD_DDL_DENIED
            if isinstance(node, exp.Copy):
                return GUARD_COPY_DENIED
            if isinstance(node, exp.Command):
                head = SQLGuard._command_head(node).upper()
                if head.startswith("EXPLAIN"):
                    return GUARD_EXPLAIN_DENIED
                if head.startswith("COPY"):
                    return GUARD_COPY_DENIED
                if head in ("DO", "CALL", "VACUUM", "ANALYZE"):
                    return GUARD_PROCEDURAL_DENIED
                # any other Command inside a Select is suspect
                return GUARD_DDL_DENIED
        return None

    @staticmethod
    def _command_head(node: "exp.Command") -> str:
        this = node.this
        if isinstance(this, str):
            return this.split()[0] if this else ""
        if this is not None:
            return (getattr(this, "name", "") or str(this)).split()[0]
        return ""

    def _walk_for_whitelist(
        self,
        root: "exp.Expression",
        cte_aliases: List[str],
        table_violations: List[str],
        column_violations: List[str],
    ) -> None:
        # ---- tables: skip CTE aliases; everything else must be whitelisted ----
        seen_tables: List["exp.Table"] = []
        for table in root.find_all(exp.Table):
            seen_tables.append(table)
            if not table.name:
                continue
            if table.name.lower() in cte_aliases:
                continue
            self._check_table(table, table_violations)

        # ---- columns: scope-aware, walks each SELECT independently ----
        if isinstance(root, exp.Union):
            scopes = list(root.expressions)
        else:
            scopes = [root]
        for scope in scopes:
            self._resolve_columns_in_scope(
                scope, seen_tables, cte_aliases, column_violations
            )

    @staticmethod
    def _collect_scope_tables(
        scope: "exp.Expression", cte_aliases: List[str]
    ) -> List[str]:
        """Return the lower-case names of base tables reachable from this
        SELECT scope. Excludes CTE aliases and subquery inner FROMs."""

        tables: List[str] = []
        if not isinstance(scope, exp.Select):
            return tables
        # sqlglot uses ``from_`` (trailing underscore) as the args key
        # in the Select expression; fall back to ``from`` for safety.
        from_clause = scope.args.get("from_") or scope.args.get("from")
        if from_clause is None:
            return tables
        for table in from_clause.find_all(exp.Table):
            if not table.name:
                continue
            name = table.name.lower()
            # ignore subquery aliases returned by sqlglot as Table instances
            if name in cte_aliases:
                continue
            tables.append(name)
        return tables

    def _resolve_columns_in_scope(
        self,
        scope: "exp.Expression",
        seen_tables: List["exp.Table"],
        cte_aliases: List[str],
        column_violations: List[str],
    ) -> None:
        scope_tables = self._collect_scope_tables(scope, cte_aliases)
        whitelist_from = [t for t in scope_tables if t in self.allowed_tables]

        def _handle_column(col: "exp.Column") -> None:
            column_name = col.name
            owner = (col.table or "").lower()
            if column_name == "*":
                return
            if not owner:
                if len(whitelist_from) == 1:
                    only = whitelist_from[0]
                    allowed = self.allowed_tables[only]
                    if column_name in allowed:
                        return
                column_violations.append(f"(unqualified).{column_name}")
                return
            allowed = self.allowed_tables.get(owner)
            if allowed is None:
                # owner table itself wasn't whitelisted; table violation
                # was already raised.
                return
            if column_name not in allowed:
                column_violations.append(f"{owner}.{column_name}")

        if isinstance(scope, exp.Select):
            self._walk_columns_stopping_at_subselects(scope, _handle_column)
            for sub in scope.find_all(exp.Subquery):
                inner = sub.this
                if isinstance(inner, exp.Select):
                    self._resolve_columns_in_scope(
                        inner, seen_tables, cte_aliases, column_violations
                    )
            return
        # non-Select scope (shouldn't happen because we filtered earlier)
        for col in scope.find_all(exp.Column):
            _handle_column(col)

    @staticmethod
    def _walk_columns_stopping_at_subselects(node, handler) -> None:
        """Walk the tree yielding only ``exp.Column`` nodes that live in
        the current SELECT scope. Do NOT descend into nested
        ``Subquery`` or ``With`` bodies - those have their own scope and
        own column resolution. Avoid descending into ``Union`` branches
        too because each branch is a separate scope."""

        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, exp.Column):
                handler(current)
                continue
            if isinstance(current, (exp.Subquery, exp.With, exp.Union)):
                continue
            for child in current.iter_expressions():
                if child is not None:
                    stack.append(child)

    def _resolve_union_branches(
        self,
        union_node: "exp.Union",
        seen_tables: List["exp.Table"],
        cte_aliases: List[str],
        column_violations: List[str],
    ) -> None:
        for branch in union_node.expressions:
            if isinstance(branch, exp.Select):
                self._resolve_columns_in_scope(
                    branch, seen_tables, cte_aliases, column_violations
                )
            elif isinstance(branch, exp.Union):
                self._resolve_union_branches(
                    branch, seen_tables, cte_aliases, column_violations
                )

    def _check_table(
        self,
        table: "exp.Table",
        violations: List[str],
    ) -> None:
        if table.catalog:
            raise _SchemaViolation(
                GUARD_SYSTEM_SCHEMA_DENIED,
                f"跨 catalog 引用被禁止: {table.catalog}.{table.db or ''}.{table.name}",
            )
        if table.db and table.db.lower() not in ALLOWED_SCHEMAS:
            raise _SchemaViolation(
                GUARD_SYSTEM_SCHEMA_DENIED,
                f"引用了非白名单 schema: {table.db}",
            )
        name = (table.name or "").lower()
        if not name:
            return
        if name not in self.allowed_tables:
            violations.append(f"{table.db + '.' if table.db else ''}{table.name}")

    # --- limit -----------------------------------------------------------

    @staticmethod
    def _extract_limit(node: "exp.Expression") -> Optional[int]:
        limit = node.args.get("limit")
        if limit is None:
            return None
        value = getattr(limit, "expression", None) or getattr(limit, "this", None)
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _append_limit_if_missing(self, original_sql: str, parsed: "exp.Expression") -> str:
        if self._extract_limit(parsed) is not None:
            return original_sql
        # DO $$ ... $$ ...; bodies contain semicolons, but the parser kept
        # them as a single Command. In that case we refuse to normalise.
        if isinstance(parsed, exp.Command):
            return original_sql
        stripped = original_sql.rstrip().rstrip(";").rstrip()
        return f"{stripped} LIMIT {self.max_rows}"

    # --- pglast cross-check (lazy import) --------------------------------

    def _check_pglast(self, sql: str):
        try:
            import pglast  # type: ignore
        except ImportError:
            if not self._pglast_warned:
                logger.warning("pglast 未安装，跳过双引擎交叉验证")
                self._pglast_warned = True
            return None

        with self._pglast_lock:
            try:
                pglast.parse_sql(sql)
            except Exception as exc:
                return GuardResult(
                    ok=False,
                    code=GUARD_PARSE_FAIL,
                    message=f"pglast 解析失败: {exc}",
                    backend="pglast",
                )
        return True


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _SchemaViolation(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def default_guard() -> SQLGuard:
    return SQLGuard()


__all__ = [
    "ALLOWED_TABLES",
    "ALLOWED_SCHEMAS",
    "GUARD_OK",
    "GUARD_EMPTY",
    "GUARD_PARSE_FAIL",
    "GUARD_MULTI_STATEMENT",
    "GUARD_DDL_DENIED",
    "GUARD_DML_DENIED",
    "GUARD_EXPLAIN_DENIED",
    "GUARD_PROCEDURAL_DENIED",
    "GUARD_COPY_DENIED",
    "GUARD_COMMENT_DENIED",
    "GUARD_SYSTEM_SCHEMA_DENIED",
    "GUARD_TABLE_NOT_ALLOWED",
    "GUARD_COLUMN_NOT_ALLOWED",
    "GUARD_ROW_CAP_EXCEEDED",
    "GuardResult",
    "SQLGuard",
    "default_guard",
]
