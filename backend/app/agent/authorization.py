from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

import sqlglot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.db.models import Permission, UserRole
from app.sql.validator import BLOCKED_FUNCTIONS


class AuthorizationError(ValueError):
    """Raised when a query is outside the current user's permissions."""


@dataclass(frozen=True)
class AuthorizationPolicy:
    resource: str
    row_filter: str | None = None
    column_masks: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def load_policies(
    session: AsyncSession, user_id: UUID | str | None
) -> list[AuthorizationPolicy]:
    if user_id is None:
        return []
    try:
        normalized_user_id = user_id if isinstance(user_id, UUID) else UUID(user_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AuthorizationError("User identity is not a valid UUID") from exc
    rows = (
        await session.scalars(
            select(Permission)
            .join(UserRole, UserRole.role_id == Permission.role_id)
            .where(UserRole.user_id == normalized_user_id, Permission.action == "read")
        )
    ).all()
    return [
        AuthorizationPolicy(
            resource=row.resource,
            row_filter=row.row_filter,
            column_masks=row.column_masks or {},
        )
        for row in rows
    ]


def _policy_for(
    resource: str, policies: list[AuthorizationPolicy]
) -> AuthorizationPolicy | None:
    normalized = resource.lower()
    matching = [
        policy
        for policy in policies
        if policy.resource.lower() in {normalized, "analytics.*", "*"}
    ]
    if not matching:
        return None

    signatures = {
        (policy.row_filter, tuple(sorted((policy.column_masks or {}).items())))
        for policy in matching
    }
    if len(signatures) > 1:
        raise AuthorizationError(f"Conflicting authorization policies for {resource}")

    return next(
        (policy for policy in matching if policy.resource.lower() == normalized),
        matching[0],
    )


def _resource(table: exp.Table) -> str:
    return f"{table.db or 'analytics'}.{table.name}".lower()


def _parse_single_expression(value: str, error_message: str) -> exp.Expression:
    try:
        statements = sqlglot.parse(value, read="postgres")
    except ParseError as exc:
        raise AuthorizationError(error_message) from exc
    if len(statements) != 1 or statements[0] is None:
        raise AuthorizationError(error_message)
    return statements[0]


def _base_table_sources(scope: Scope) -> dict[str, tuple[str, exp.Table]]:
    sources: dict[str, tuple[str, exp.Table]] = {}
    for alias, source in scope.sources.items():
        if isinstance(source, exp.Table):
            sources[alias.lower()] = (_resource(source), source)
    return sources


def _qualify_row_filter(row_filter: str, alias: str) -> exp.Expression:
    predicate = _parse_single_expression(
        row_filter, "Row authorization policy is invalid"
    )
    if any(
        isinstance(node, (exp.Select, exp.Subquery, exp.Union, exp.Table, exp.DML))
        for node in predicate.walk()
    ):
        raise AuthorizationError("Row authorization policy must be a scalar predicate")
    if any(
        isinstance(node, exp.Func)
        and (node.name or type(node).__name__).upper() in BLOCKED_FUNCTIONS
        for node in predicate.walk()
    ):
        raise AuthorizationError("Row authorization policy uses a blocked function")
    for column in predicate.find_all(exp.Column):
        if column.table:
            if column.table.lower() != alias.lower():
                raise AuthorizationError("Row authorization policy references another table")
        else:
            column.set("table", exp.Identifier(this=alias))
    return predicate


def _column_policy(
    scope: Scope,
    column: exp.Column,
    policies: list[AuthorizationPolicy],
) -> AuthorizationPolicy | None:
    sources = _base_table_sources(scope)
    if column.table:
        source = sources.get(column.table.lower())
        if source is None:
            return None
        return _policy_for(source[0], policies)

    candidates = [
        policy
        for resource, _table in sources.values()
        if (policy := _policy_for(resource, policies)) is not None
        and column.name in (policy.column_masks or {})
    ]
    if len(candidates) > 1:
        raise AuthorizationError(f"Ambiguous protected column: {column.name}")
    if len(sources) == 1:
        resource, _table = next(iter(sources.values()))
        return _policy_for(resource, policies)
    return candidates[0] if candidates else None


def _scope_nodes(root: exp.Expression) -> list[exp.Expression]:
    """Walk one query scope without descending into nested SELECT scopes."""
    nodes: list[exp.Expression] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        children = list(node.iter_expressions())
        stack.extend(
            child
            for child in reversed(children)
            if not isinstance(child, (exp.Select, exp.Subquery, exp.Union))
        )
    return nodes


def _apply_column_masks(
    scope: Scope,
    policies: list[AuthorizationPolicy],
) -> None:
    sources = _base_table_sources(scope)
    masked_sources = [
        policy
        for resource, _table in sources.values()
        if (policy := _policy_for(resource, policies)) is not None
        and policy.column_masks
    ]
    projections = scope.expression.expressions
    projection_columns = {
        id(node)
        for projection in projections
        for node in _scope_nodes(projection)
        if isinstance(node, exp.Column)
    }
    for column in scope.columns:
        if id(column) in projection_columns:
            continue
        policy = _column_policy(scope, column, policies)
        if policy and column.name in (policy.column_masks or {}):
            raise AuthorizationError(
                f"Masked column cannot be used outside the result projection: {column.name}"
            )
    for projection in projections:
        projection_nodes = _scope_nodes(projection)
        if any(isinstance(node, exp.Star) for node in projection_nodes):
            if masked_sources:
                raise AuthorizationError("SELECT * is not allowed on a masked dataset")
            continue
        for column in [node for node in projection_nodes if isinstance(node, exp.Column)]:
            policy = _column_policy(scope, column, policies)
            mask = (policy.column_masks or {}).get(column.name) if policy else None
            if mask is None:
                continue
            replacement = _parse_single_expression(
                mask.replace("{column}", column.sql(dialect="postgres")),
                "Column authorization policy is invalid",
            )
            if any(
                isinstance(node, (exp.Select, exp.Subquery, exp.Table, exp.DML))
                for node in replacement.walk()
            ):
                raise AuthorizationError("Column authorization policy must be scalar")
            if any(
                isinstance(node, exp.Func)
                and (node.name or type(node).__name__).upper() in BLOCKED_FUNCTIONS
                for node in replacement.walk()
            ):
                raise AuthorizationError("Column authorization policy uses a blocked function")
            column.replace(replacement)


def authorize_read_query(
    sql: str,
    policies: list[AuthorizationPolicy] | None = None,
    *,
    user_id: UUID | str | None = None,
    allow_anonymous: bool = False,
) -> str:
    if user_id is None and not allow_anonymous:
        raise AuthorizationError("User identity is required for query authorization")
    query = _parse_single_expression(sql, "SQL cannot be parsed for authorization")
    if not isinstance(query, (exp.Select, exp.Union)):
        raise AuthorizationError("Only SELECT queries can be authorized")
    effective_policies = policies or []
    for scope in traverse_scope(query):
        for table in scope.tables:
            source = scope.sources.get(table.alias_or_name.lower())
            if isinstance(source, Scope):
                continue
            resource = _resource(table)
            policy = _policy_for(resource, effective_policies)
            if user_id is not None and policy is None:
                raise AuthorizationError(f"User is not authorized to read {resource}")
            if policy is None or not policy.row_filter:
                continue
            alias = table.alias_or_name
            filter_expression = _qualify_row_filter(policy.row_filter, alias)
            joins = scope.expression.args.get("joins") or []
            matching_join = next(
                (
                    join
                    for join in joins
                    if isinstance(join.this, exp.Table)
                    and join.this.alias_or_name.lower() == alias.lower()
                ),
                None,
            )
            if any(join.args.get("side") == "FULL" for join in joins):
                raise AuthorizationError("Row-filtered sources cannot use FULL JOIN")
            if any(
                join.args.get("side") == "RIGHT"
                and (
                    matching_join is None
                    or matching_join.args.get("side") != "RIGHT"
                )
                for join in joins
            ):
                raise AuthorizationError("Row-filtered sources cannot use RIGHT JOIN")
            if matching_join is not None and matching_join.args.get("side") == "LEFT":
                existing_on = matching_join.args.get("on")
                if existing_on is None:
                    matching_join.set("on", filter_expression)
                elif not any(filter_expression == node for node in existing_on.walk()):
                    matching_join.set(
                        "on", exp.and_(existing_on, filter_expression, copy=False)
                    )
                continue
            existing_where = scope.expression.args.get("where")
            if existing_where is None:
                scope.expression.set("where", exp.Where(this=filter_expression))
            elif any(filter_expression == node for node in existing_where.this.walk()):
                continue
            else:
                existing_where.set(
                    "this", exp.and_(existing_where.this, filter_expression, copy=False)
                )
        _apply_column_masks(scope, effective_policies)
    return query.sql(dialect="postgres")
