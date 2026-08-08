from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    sub: str
    username: str | None
    groups: list[str]
    role: str


@lru_cache
def get_jwks_client() -> PyJWKClient:
    if not settings.cognito_user_pool_id:
        raise RuntimeError("COGNITO_USER_POOL_ID is not configured")

    jwks_url = (
        f"{settings.cognito_issuer}/.well-known/jwks.json"
    )

    return PyJWKClient(jwks_url)


def decode_access_token(token: str) -> dict:
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={
                "verify_aud": False,
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

    if claims.get("token_use") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected a Cognito access token",
        )

    if claims.get("client_id") != settings.cognito_user_pool_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token was issued for another application",
        )

    return claims


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    claims = decode_access_token(credentials.credentials)

    raw_groups = claims.get("cognito:groups", [])

    groups = (
        [str(group) for group in raw_groups]
        if isinstance(raw_groups, list)
        else []
    )

    if "ADMIN" in groups:
        role = "ADMIN"
    elif "MANAGER" in groups:
        role = "MANAGER"
    else:
        role = "EMPLOYEE"

    return CurrentUser(
        sub=str(claims["sub"]),
        username=claims.get("username"),
        groups=groups,
        role=role,
    )


def require_roles(*allowed_roles: str):
    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:

        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this operation",
            )

        return user

    return dependency