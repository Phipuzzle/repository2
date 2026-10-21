from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class UnsafeQueryError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    limit: int


BLOCKED_FUNCTIONS = {
    "PG_SLEEP",
    "PG_READ_FILE",
    "PG_READ_BINARY_FILE",
    "PG_LS_DIR",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
    "SET_CONFIG",
    "NEXTVAL",
    "SETVAL",
    "LO_IMPORT",
    "LO_EXPORT",
    "DBLINK",
    "PG_ADVISORY_LOCK",
    "PG_ADVISORY_XACT_LOCK",
    "PG_NOTIFY",
    "PG_RELOAD_CONF",
    "LO_CREATE",
    "LO_UNLINK",
}
ALLOWED_TABLES = {"demo_orders", "demo_order_items", "demo_products", "demo_regions"}


def validate_read_query(sql: str, max_limit: int = 1000) -> ValidatedQuery:
    if not sql.strip():
        raise UnsafeQueryError("SQL must not be empty")
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except ParseError as exc:
        raise UnsafeQueryError("SQL syntax is invalid") from exc
    if len(statements) != 1 or statements[0] is None:
        raise UnsafeQueryError("Exactly one SQL statement is allowed")

    query = statements[0]
    if not isinstance(query, (exp.Select, exp.Union)):
        raise UnsafeQueryError("Only SELECT queries are allowed")
    if query.args.get("into") or query.args.get("locks") or query.args.get("fetch"):
        raise UnsafeQueryError("SELECT INTO, row locks, and FETCH are not allowed")
    if any(isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command)) for node in query.walk()):
        raise UnsafeQueryError("Data modification and DDL statements are not allowed")

    cte_names = {cte.alias_or_name.lower() for cte in query.find_all(exp.CTE)}
    for table in query.find_all(exp.Table):
        schema = table.db
        if not schema and table.name.lower() in cte_names:
            continue
        if (schema or "").lower() != "analytics" or table.name.lower() not in ALLOWED_TABLES:
            raise UnsafeQueryError(f"Table is not in the analytics allowlist: {table.sql()}")

    for node in query.walk():
        if isinstance(node, exp.Func):
            function_name = (node.name or type(node).__name__).upper()
            if function_name in BLOCKED_FUNCTIONS:
                raise UnsafeQueryError(f"Function is not allowed: {function_name}")

    limit = query.args.get("limit")
    if limit is None:
        query = query.limit(max_limit)
        applied_limit = max_limit
    else:
        limit_value = limit.expression
        if not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
            raise UnsafeQueryError("LIMIT must be an integer literal")
        applied_limit = int(limit_value.this)
        if applied_limit < 1:
            raise UnsafeQueryError("LIMIT must be greater than zero")
        if applied_limit > max_limit:
            applied_limit = max_limit
            query = query.limit(max_limit, copy=False)
    return ValidatedQuery(sql=query.sql(dialect="postgres"), limit=applied_limit)
