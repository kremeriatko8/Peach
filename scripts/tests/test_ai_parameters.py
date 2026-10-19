import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "ai_parameters", Path(__file__).resolve().parents[1] / "validate-ai-parameters.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def parameters():
    return {
        "ImageUri": "example/peach@sha256:" + "a" * 64,
        "FrontendOrigins": "https://example.cloudfront.net",
        "InferenceResourceArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0",
        "InputUsdPerMillion": "0.06",
        "OutputUsdPerMillion": "0.24",
        "CognitoAuthority": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST",
        "CognitoClientId": "client",
        "CognitoJwksJson": '{"keys":[{"kid":"test"}]}',
    }


def test_valid_disabled_configuration():
    module.validate(parameters())


@pytest.mark.parametrize(
    "key,value",
    [
        ("ParserEnabled", "true"),
        ("ParserModel", "anthropic.claude-opus-5-5"),
        ("FrontendOrigins", "*"),
        ("FrontendOrigins", "http://example.com"),
        ("ImageUri", "image:latest"),
        ("InputUsdPerMillion", "nan"),
        ("OutputUsdPerMillion", "inf"),
        ("InputUsdPerMillion", "0"),
        ("CognitoClientId", ""),
        ("CognitoJwksJson", '{"keys":[]}'),
        ("CognitoJwksJson", "x" * 5000),
        (
            "InferenceResourceArn",
            "arn:aws:bedrock-mantle:us-east-1:123456789012:project/other",
        ),
        ("CognitoClientId", "x" * 5000),
    ],
)
def test_invalid_configuration_fails_closed(key, value):
    with pytest.raises(ValueError):
        module.validate({**parameters(), key: value})
