#!/usr/bin/env python3
"""Read trusted CloudFormation outputs on stdin; emit public verifier configuration."""

import base64
import json
import re
import sys
import urllib.request


def configuration(outputs, fetch):
    values = {entry["OutputKey"]: entry["OutputValue"] for entry in outputs}
    authority = values["Authority"]
    client_id = values["UserPoolClientId"]
    if not re.fullmatch(
        r"https://cognito-idp\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9-]+_[A-Za-z0-9]+",
        authority,
    ):
        raise ValueError("Unrecognized trusted Cognito authority")
    if not re.fullmatch(r"[a-z0-9]+", client_id):
        raise ValueError("Invalid Cognito client ID")
    snapshot = fetch(authority + "/.well-known/jwks.json")
    keys = snapshot["keys"]
    if not keys or len({key["kid"] for key in keys}) != len(keys):
        raise ValueError("Missing or duplicate signing keys")
    public = []
    for key in keys:
        if (
            key.get("kty") != "RSA"
            or key.get("alg") != "RS256"
            or key.get("use") != "sig"
        ):
            raise ValueError("Unexpected signing key")
        for field in ("kid", "n", "e"):
            if not isinstance(key.get(field), str) or not key[field]:
                raise ValueError("Invalid public key")
        for field in ("n", "e"):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", key[field]):
                raise ValueError("Invalid RSA integer encoding")
        modulus = int.from_bytes(
            base64.urlsafe_b64decode(key["n"] + "=" * (-len(key["n"]) % 4)), "big"
        )
        exponent = int.from_bytes(
            base64.urlsafe_b64decode(key["e"] + "=" * (-len(key["e"]) % 4)), "big"
        )
        if (
            modulus.bit_length() < 2048
            or modulus % 2 == 0
            or exponent < 3
            or exponent % 2 == 0
        ):
            raise ValueError("Invalid RSA signing key")
        public.append(
            {field: key[field] for field in ("kid", "kty", "alg", "use", "n", "e")}
        )
    return {
        "COGNITO_AUTHORITY": authority,
        "COGNITO_CLIENT_ID": client_id,
        "COGNITO_JWKS_JSON": json.dumps({"keys": public}, separators=(",", ":")),
    }


def fetch(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


if __name__ == "__main__":
    json.dump(configuration(json.load(sys.stdin), fetch), sys.stdout)
