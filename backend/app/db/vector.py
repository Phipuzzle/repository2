from __future__ import annotations

from typing import Any

from sqlalchemy.types import UserDefinedType


class VectorType(UserDefinedType[list[float]]):
    """Map a Python float list to a native PostgreSQL pgvector column."""

    cache_ok = True

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def get_col_spec(self, **kwargs: Any) -> str:
        return f"VECTOR({self.dimension})"

    def bind_processor(self, dialect: Any) -> Any:
        def process(value: list[float] | None) -> str | None:
            if value is None:
                return None
            return "[" + ",".join(f"{float(item):.8f}" for item in value) + "]"

        return process

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        def process(value: str | None) -> list[float] | None:
            if value is None:
                return None
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1]
            return [float(item) for item in text.split(",") if item.strip()]

        return process
