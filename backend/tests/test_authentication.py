import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.authentication as authentication
from app.core.config import Settings
from app.db.models import User

ISSUER = "https://identity.example.test/realms/ida/"
AUDIENCE = "intelligent-data-agent-api"
JWKS_URL = "https://identity.example.test/realms/ida/keys"


def make_key_pair() -> tuple[Any, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update(
        {"kid": "test-signing-key", "alg": "RS256", "use": "sig", "key_ops": ["verify"]}
    )
    return private_key, public_jwk


def make_token(private_key: Any, key_id: str = "test-signing-key", **overrides: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "oidc-user-123",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )


def make_settings() -> Settings:
    return Settings(
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_jwks_url=JWKS_URL,
        oidc_algorithms=["RS256"],
    )


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def scalar(self, _: Any) -> User | None:
        return self.user


@pytest.mark.asyncio
async def test_valid_token_preserves_exact_issuer_including_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = make_key_pair()

    async def load_jwks(*_: Any, **__: Any) -> dict[str, dict[str, Any]]:
        return {jwk["kid"]: jwk}

    monkeypatch.setattr(authentication, "_fetch_jwks", load_jwks)
    claims = await authentication.verify_bearer_token(make_token(private_key), make_settings())

    assert claims["iss"] == ISSUER
    assert claims["sub"] == "oidc-user-123"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://identity.example.test/realms/ida"},
        {"aud": "another-api"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
async def test_invalid_token_claims_are_rejected(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any]
) -> None:
    private_key, jwk = make_key_pair()

    async def load_jwks(*_: Any, **__: Any) -> dict[str, dict[str, Any]]:
        return {jwk["kid"]: jwk}

    monkeypatch.setattr(authentication, "_fetch_jwks", load_jwks)

    with pytest.raises(HTTPException) as error:
        await authentication.verify_bearer_token(
            make_token(private_key, **overrides), make_settings()
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _, jwk = make_key_pair()
    other_private_key, _ = make_key_pair()

    async def load_jwks(*_: Any, **__: Any) -> dict[str, dict[str, Any]]:
        return {jwk["kid"]: jwk}

    monkeypatch.setattr(authentication, "_fetch_jwks", load_jwks)

    with pytest.raises(HTTPException) as error:
        await authentication.verify_bearer_token(make_token(other_private_key), make_settings())

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_key_rotation_refreshes_jwks_for_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, jwk = make_key_pair()
    calls = 0

    async def load_jwks(*_: Any, refresh: bool = False) -> dict[str, dict[str, Any]]:
        nonlocal calls
        calls += 1
        return {jwk["kid"]: jwk} if refresh else {"old-key": {}}

    monkeypatch.setattr(authentication, "_fetch_jwks", load_jwks)
    claims = await authentication.verify_bearer_token(
        make_token(private_key, key_id=jwk["kid"]), make_settings()
    )

    assert calls == 2
    assert claims["sub"] == "oidc-user-123"


@pytest.mark.asyncio
async def test_current_user_requires_a_provisioned_active_iss_sub_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def verified_claims(_: str) -> dict[str, str]:
        return {"iss": ISSUER, "sub": "oidc-user-123"}

    monkeypatch.setattr(authentication, "verify_bearer_token", verified_claims)
    monkeypatch.setattr(authentication, "get_settings", make_settings)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
    user = User(
        email="user@example.invalid",
        display_name="Mapped user",
        identity_issuer=ISSUER,
        identity_subject="oidc-user-123",
        is_active=True,
    )

    result = await authentication.get_current_user(
        credentials, cast(AsyncSession, FakeSession(user))
    )

    assert result.identity_issuer == ISSUER
    assert result.identity_subject == "oidc-user-123"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [
        None,
        User(
            email="inactive@example.invalid",
            display_name="Inactive user",
            identity_issuer=ISSUER,
            identity_subject="oidc-user-123",
            is_active=False,
        ),
    ],
)
async def test_current_user_rejects_unprovisioned_or_inactive_identity(
    monkeypatch: pytest.MonkeyPatch, user: User | None
) -> None:
    async def verified_claims(_: str) -> dict[str, str]:
        return {"iss": ISSUER, "sub": "oidc-user-123"}

    monkeypatch.setattr(authentication, "verify_bearer_token", verified_claims)
    monkeypatch.setattr(authentication, "get_settings", make_settings)

    with pytest.raises(HTTPException) as error:
        await authentication.get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token"),
            cast(AsyncSession, FakeSession(user)),
        )

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "identity_not_provisioned"


def test_jwks_rejects_duplicate_kid_and_non_signing_keys() -> None:
    _, jwk = make_key_pair()
    with pytest.raises(HTTPException) as duplicate_error:
        authentication._parse_jwks({"keys": [jwk, jwk]}, ["RS256"])
    assert duplicate_error.value.status_code == 503

    for unusable_key in (
        {**jwk, "use": "enc"},
        {**jwk, "key_ops": ["sign"]},
        {**jwk, "alg": "PS256"},
    ):
        with pytest.raises(HTTPException) as error:
            authentication._parse_jwks({"keys": [unusable_key]}, ["RS256"])
        assert error.value.status_code == 503


def test_oidc_must_be_configured() -> None:
    with pytest.raises(HTTPException) as error:
        authentication._oidc_settings(
            Settings(
                _env_file=None,
                oidc_issuer="",
                oidc_audience="",
                oidc_jwks_url="",
            )
        )
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_protected_api_requires_bearer_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/query-runs", json={"question": "private query"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "authentication_required"
