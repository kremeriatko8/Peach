"""Offline AI deployment checks. Never reads AWS credentials or calls AWS."""

import json
import math
import re
import sys
from pathlib import Path


def validate(params):
    if not re.fullmatch(r".+@sha256:[a-f0-9]{64}", params.get("ImageUri", "")):
        raise ValueError("Use an immutable image digest")
    origins = params.get("FrontendOrigins", "").split(",")
    if not origins or not all(
        re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?", o) for o in origins
    ):
        raise ValueError("Use exact HTTPS frontend origins")
    if params.get("ParserEnabled", "false") != "false":
        raise ValueError("Initial deployment must keep parser disabled")
    if not re.fullmatch(
        r"arn:aws:bedrock-mantle:us-east-1:[0-9]{12}:project/default",
        params.get("InferenceResourceArn", ""),
    ):
        raise ValueError("Use the existing default Mantle project ARN")
    for name in ("InputUsdPerMillion", "OutputUsdPerMillion"):
        rate = float(params.get(name, "nan"))
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Supply verified positive finite token rates")
    required = ("CognitoAuthority", "CognitoClientId", "CognitoJwksJson")
    if any(not params.get(key) for key in required):
        raise ValueError("Complete public Cognito configuration is required")
    if not params["CognitoAuthority"].startswith(
        "https://cognito-idp.us-east-1.amazonaws.com/"
    ):
        raise ValueError("Use the existing us-east-1 Cognito issuer")
    jwks = json.loads(params["CognitoJwksJson"])
    if not isinstance(jwks, dict) or not jwks.get("keys"):
        raise ValueError("Supply trusted public Cognito signing keys")
    environment = {
        "APP_ENV": "production",
        "COGNITO_AUTHORITY": params["CognitoAuthority"],
        "COGNITO_CLIENT_ID": params["CognitoClientId"],
        "COGNITO_JWKS_JSON": params["CognitoJwksJson"],
        "PARSER_MODEL": params.get("ParserModel", "anthropic.claude-opus-5-5"),
        "PARSER_ENABLED": "false",
        "PARSER_MAX_TOKENS": "2048",
        "PARSER_REQUESTS_PER_MINUTE": "3",
        "PARSER_INPUT_USD_PER_MILLION": params["InputUsdPerMillion"],
        "PARSER_OUTPUT_USD_PER_MILLION": params["OutputUsdPerMillion"],
    }
    if sum(len(k.encode()) + len(v.encode()) for k, v in environment.items()) > 4096:
        raise ValueError("Complete parser environment exceeds 4096 bytes")


def main():
    try:
        entries = json.loads(Path(sys.argv[1]).read_text())
        params = {p["ParameterKey"]: p["ParameterValue"] for p in entries}
        if len(params) != len(entries) or any(
            not isinstance(v, str) for v in params.values()
        ):
            raise ValueError("Use unique string-valued CloudFormation parameters")
        validate(params)
    except (ValueError, KeyError, TypeError, IndexError):
        sys.exit(
            "Invalid AI parameters; review digest, origins, disabled state, project, rates and Cognito"
        )


if __name__ == "__main__":
    main()
