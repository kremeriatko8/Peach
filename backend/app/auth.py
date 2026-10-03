"""Verify access tokens against deployment-supplied public keys; never use the network."""

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    sub: str


class TokenVerifier:
    def __init__(self, authority: str, client_id: str, snapshot: str):
        if not authority.startswith("https://") or not client_id:
            raise ValueError("Missing trusted Cognito configuration")
        self.authority = authority
        self.client_id = client_id
        self.keys = {}
        for key in json.loads(snapshot)["keys"]:
            if key.get("kty") != "RSA" or key.get("use", "sig") != "sig":
                continue
            if key.get("alg", "RS256") != "RS256":
                continue
            kid = key.get("kid")
            if not isinstance(kid, str) or not kid or kid in self.keys:
                raise ValueError("Invalid or duplicate signing key")
            self.keys[kid] = jwt.PyJWK.from_dict(key, algorithm="RS256").key
        if not self.keys:
            raise ValueError("No trusted RSA signing keys")

    def verify(self, token: str) -> Principal:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or header.get("kid") not in self.keys:
            raise jwt.InvalidTokenError("Unknown signing key or algorithm")
        claims = jwt.decode(
            token,
            self.keys[header["kid"]],
            algorithms=["RS256"],
            issuer=self.authority,
            options={
                "require": ["exp", "iss", "token_use", "client_id", "sub"],
                "verify_aud": False,
            },
        )
        sub = claims["sub"]
        if (
            claims["token_use"] != "access"
            or claims["client_id"] != self.client_id
            or not isinstance(sub, str)
            or not sub.strip()
            or len(sub) > 128
        ):
            raise jwt.InvalidTokenError("Invalid access-token claims")
        return Principal(sub=sub)


@lru_cache(maxsize=1)
def get_verifier() -> TokenVerifier:
    settings = get_settings()
    return TokenVerifier(
        settings.cognito_authority, settings.cognito_client_id, settings.cognito_jwks_json
    )


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        verifier = get_verifier()
    except (ValueError, KeyError, TypeError, jwt.PyJWTError) as exc:
        raise HTTPException(
            status_code=503, detail="Authentication configuration unavailable"
        ) from exc
    try:
        return verifier.verify(credentials.credentials)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise unauthorized from exc


UserDep = Annotated[Principal, Depends(current_user)]
