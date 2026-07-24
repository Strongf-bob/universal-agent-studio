from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

import httpx
import pytest
from universal_agent_kernel.contracts.generated import (
    CredentialReference,
    Identifier,
)
from universal_agent_kernel.domain import ModelRequest
from universal_agent_kernel.models.openai_compatible import (
    EnvironmentCredentialStore,
    OpenAICompatibleGateway,
    ProviderGatewayError,
)

SECRET = "test-provider-secret-that-must-never-leak"


def _credential(value: str = "openai-compatible") -> CredentialReference:
    return CredentialReference(credential_ref=Identifier(root=value))


@pytest.fixture(autouse=True)
def provider_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UAS_TEST_PROVIDER_KEY", SECRET)


def _request() -> ModelRequest:
    return ModelRequest(
        profile_id="byok-planner",
        model="compatible-model",
        input={"question": "What is 19 × 23?"},
        locale="en-US",
    )


def _response(
    arguments: str = '{"operation":"multiply","left":19,"right":23}',
) -> bytes:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "builtin-calculator",
                                    "arguments": arguments,
                                }
                            }
                        ]
                    }
                }
            ]
        }
    ).encode()


def test_base_url_requires_allowlisted_https_or_loopback() -> None:
    credential = _credential()
    store = EnvironmentCredentialStore(
        {"openai-compatible": "UAS_TEST_PROVIDER_KEY"}
    )

    with pytest.raises(ValueError, match="provider_url_https_required"):
        OpenAICompatibleGateway(
            base_url="http://provider.example/v1",
            allowed_origins={"https://provider.example"},
            credential=credential,
            credential_store=store,
        )
    with pytest.raises(ValueError, match="provider_url_not_allowlisted"):
        OpenAICompatibleGateway(
            base_url="https://other.example/v1",
            allowed_origins={"https://provider.example"},
            credential=credential,
            credential_store=store,
        )

    gateway = OpenAICompatibleGateway(
        base_url="http://127.0.0.1:11434/v1",
        allowed_origins={"http://127.0.0.1:11434"},
        credential=credential,
        credential_store=store,
    )
    assert "127.0.0.1" in repr(gateway)


@pytest.mark.asyncio
async def test_structured_tool_call_uses_environment_credential_without_leak(
) -> None:
    captured_authorization = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_authorization
        captured_authorization = request.headers["authorization"]
        return httpx.Response(200, content=_response())

    gateway = OpenAICompatibleGateway(
        base_url="https://provider.example/v1",
        allowed_origins={"https://provider.example"},
        credential=_credential(),
        credential_store=EnvironmentCredentialStore(
            {"openai-compatible": "UAS_TEST_PROVIDER_KEY"}
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.complete(_request())

    assert result.tool_id == "builtin-calculator"
    assert result.arguments == {
        "operation": "multiply",
        "left": 19,
        "right": 23,
    }
    assert captured_authorization == f"Bearer {SECRET}"
    assert SECRET not in repr(gateway)


@pytest.mark.asyncio
async def test_provider_failures_are_safe_and_retryable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            content=b'{"error":{"message":"raw upstream incident detail"}}',
        )

    gateway = OpenAICompatibleGateway(
        base_url="https://provider.example/v1",
        allowed_origins={"https://provider.example"},
        credential=_credential(),
        credential_store=EnvironmentCredentialStore(
            {"openai-compatible": "UAS_TEST_PROVIDER_KEY"}
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderGatewayError) as caught:
        await gateway.complete(_request())

    envelope = caught.value.to_error_envelope()
    assert envelope == {
        "code": "model_provider_unavailable",
        "message_key": "errors.model_provider_unavailable",
        "retryable": True,
        "details": {},
    }
    assert "raw upstream" not in str(caught.value)


@pytest.mark.asyncio
async def test_response_limit_and_structured_arguments_fail_closed() -> None:
    responses = iter(
        [
            httpx.Response(200, content=b"x" * 1025),
            httpx.Response(200, content=_response("not-json")),
        ]
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return next(responses)

    gateway = OpenAICompatibleGateway(
        base_url="https://provider.example/v1",
        allowed_origins={"https://provider.example"},
        credential=_credential(),
        credential_store=EnvironmentCredentialStore(
            {"openai-compatible": "UAS_TEST_PROVIDER_KEY"}
        ),
        max_response_bytes=1024,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderGatewayError, match="model_response_too_large"):
        await gateway.complete(_request())
    with pytest.raises(ProviderGatewayError, match="model_response_invalid"):
        await gateway.complete(_request())


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (
        os.getenv("UAS_BYOK_SMOKE_BASE_URL")
        and os.getenv("UAS_BYOK_SMOKE_API_KEY")
        and os.getenv("UAS_BYOK_SMOKE_MODEL")
    ),
    reason="BYOK smoke environment is not configured",
)
async def test_opt_in_byok_smoke() -> None:
    os.environ["UAS_BYOK_SMOKE_CREDENTIAL"] = os.environ[
        "UAS_BYOK_SMOKE_API_KEY"
    ]
    base_url = os.environ["UAS_BYOK_SMOKE_BASE_URL"]
    parts = urlsplit(base_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    gateway = OpenAICompatibleGateway(
        base_url=base_url,
        allowed_origins={origin},
        credential=_credential("byok-smoke"),
        credential_store=EnvironmentCredentialStore(
            {"byok-smoke": "UAS_BYOK_SMOKE_CREDENTIAL"}
        ),
    )
    result = await gateway.complete(
        ModelRequest(
            profile_id="byok-smoke",
            model=os.environ["UAS_BYOK_SMOKE_MODEL"],
            input={"question": "Return a multiply tool call for 19 and 23."},
            locale="en-US",
        )
    )
    assert result.tool_id == "builtin-calculator"
