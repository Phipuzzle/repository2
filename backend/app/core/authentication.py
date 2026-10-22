from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)
_jwks_cache: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
_jwks_locks: dict[str, asyncio.Lock] = {}
_jwks_refresh_after: dict[str, float] = {}
_MAX_JWKS_BYTES = 1_048_576
_MIN_JWKS_REFRESH_INTERVAL_SECONDS = 5
_ALLOWED_OIDC_ALGORITHMS = {
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
}


def _auth_error(
    code: str, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED
) -> HTTPException:
    headers = (
        {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    )
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers,
    )


def _oidc_settings(settings: Settings) -> tuple[str, str, str, list[str]]:
    issuer = settings.oidc_issuer
    audience = settings.oidc_audience
    jwks_url = settings.oidc_jwks_url
    algorithms = settings.oidc_algorithms
    if not issuer or not audience or not jwks_url or not algorithms:
        raise _auth_error(
            "oidc_not_configured",
            "JWT authentication requires OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if any(algorithm not in _ALLOWED_OIDC_ALGORITHMS for algorithm in algorithms):
        raise _auth_error(
            "oidc_invalid_configuration",
            "OIDC JWT algorithms must use an accepted asymmetric signing algorithm",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return issuer, audience, jwks_url, algorithms


async def _fetch_jwks(
    jwks_url: str, settings: Settings, *, refresh: bool = False
) -> dict[str, dict[str, Any]]:
    now = time.monotonic()
    cached = _jwks_cache.get(jwks_url)
    if not refresh and cached and now - cached[0] < settings.oidc_jwks_cache_seconds:
        return cached[1]

    lock = _jwks_locks.setdefault(jwks_url, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        cached = _jwks_cache.get(jwks_url)
        if refresh and cached and now < _jwks_refresh_after.get(jwks_url, 0):
            return cached[1]
        if not refresh and cached and now - cached[0] < settings.oidc_jwks_cache_seconds:
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                async with client.stream("GET", jwks_url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > _MAX_JWKS_BYTES:
                            raise _auth_error(
                                "oidc_keys_invalid",
                                "OIDC signing key response exceeds the size limit",
                                status.HTTP_503_SERVICE_UNAVAILABLE,
                            )
                payload = json.loads(body)
        except (httpx.HTTPError, ValueError) as exc:
            raise _auth_error(
                "oidc_keys_unavailable",
                "Unable to retrieve OIDC signing keys",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        _jwks_cache[jwks_url] = (time.monotonic(), _parse_jwks(payload, settings.oidc_algorithms))
        _jwks_refresh_after[jwks_url] = time.monotonic() + max(
            _MIN_JWKS_REFRESH_INTERVAL_SECONDS,
            min(max(settings.oidc_jwks_cache_seconds, 0), 30),
        )
        return _jwks_cache[jwks_url][1]


def _parse_jwks(payload: object, algorithms: list[str]) -> dict[str, dict[str, Any]]:
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        raise _auth_error(
            "oidc_keys_invalid",
            "OIDC signing key response is invalid",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    result: dict[str, dict[str, Any]] = {}
    seen_key_ids: set[str] = set()
    for item in keys:
        if not isinstance(item, dict) or not isinstance(item.get("kid"), str):
            continue
        key_id = item["kid"]
        if key_id in seen_key_ids:
            raise _auth_error(
                "oidc_keys_invalid",
                "OIDC signing key response contains duplicate key identifiers",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        seen_key_ids.add(key_id)
        if item.get("use") not in (None, "sig"):
            continue
        key_ops = item.get("key_ops")
        if key_ops is not None and (not isinstance(key_ops, list) or "verify" not in key_ops):
            continue
        key_algorithm = item.get("alg")
        if key_algorithm is not None and key_algorithm not in algorithms:
            continue
        key_type = item.get("kty")
        if key_type == "RSA":
            compatible = any(algorithm.startswith(("RS", "PS")) for algorithm in algorithms)
        elif key_type == "EC":
            compatible = any(algorithm.startswith("ES") for algorithm in algorithms)
        elif key_type == "OKP":
            compatible = "EdDSA" in algorithms
        else:
            compatible = False
        if not compatible:
            continue
        try:
            jwt.PyJWK.from_dict(
                item,
                algorithm=key_algorithm
                or next(
                    algorithm
                    for algorithm in algorithms
                    if (key_type == "RSA" and algorithm.startswith(("RS", "PS")))
                    or (key_type == "EC" and algorithm.startswith("ES"))
                    or (key_type == "OKP" and algorithm == "EdDSA")
                ),
            )
        except (jwt.PyJWTError, TypeError, ValueError):
            continue
        result[key_id] = item
    if not result:
        raise _auth_error(
            "oidc_keys_invalid",
            "OIDC signing key response contains no keyed public keys",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return result


async def verify_bearer_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    issuer, audience, jwks_url, algorithms = _oidc_settings(settings)
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _auth_error("invalid_token", "Bearer token is invalid") from exc

    algorithm = header.get("alg")
    key_id = header.get("kid")
    if not isinstance(algorithm, str) or algorithm not in algorithms or not isinstance(key_id, str):
        raise _auth_error("invalid_token", "Bearer token signing key is not accepted")

    keys = await _fetch_jwks(jwks_url, settings)
    jwk_data = keys.get(key_id)
    if jwk_data is None:
        keys = await _fetch_jwks(jwks_url, settings, refresh=True)
        jwk_data = keys.get(key_id)
    if jwk_data is None:
        raise _auth_error("invalid_token", "Bearer token signing key is unknown")

    try:
        signing_key = jwt.PyJWK.from_dict(jwk_data, algorithm=algorithm).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=algorithms,
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise _auth_error("invalid_token", "Bearer token validation failed") from exc
    if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
        raise _auth_error("invalid_token", "Bearer token has no valid subject")
    return claims


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error("authentication_required", "A Bearer token is required")
    claims = await verify_bearer_token(credentials.credentials)
    settings = get_settings()
    issuer = settings.oidc_issuer
    user = await session.scalar(
        select(User).where(
            User.identity_issuer == issuer,
            User.identity_subject == claims["sub"],
        )
    )
    if user is None or not user.is_active:
        raise _auth_error(
            "identity_not_provisioned",
            "This OIDC identity is not provisioned for the application",
            status.HTTP_403_FORBIDDEN,
        )
    return user
