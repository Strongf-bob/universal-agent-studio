"""Bounded OpenAI-compatible BYOK adapter behind ModelGatewayPort."""

from __future__ import annotations

import ipaddress
import json
import os
from collections.abc import Mapping, Set
from typing import cast
from urllib.parse import SplitResult, urlsplit

import httpx

from universal_agent_kernel.contracts.generated import CredentialReference
from universal_agent_kernel.domain import (
    ModelExecutionError,
    ModelRequest,
    ToolRequest,
)


class EnvironmentCredentialStore:
    """Resolve explicit credential references without exposing arbitrary env vars."""

    def __init__(self, environment_names: Mapping[str, str]) -> None:
        self._environment_names = dict(environment_names)

    def resolve(self, reference: CredentialReference) -> str:
        environment_name = self._environment_names.get(
            reference.credential_ref.root
        )
        if environment_name is None:
            raise ProviderGatewayError(
                "model_credential_unavailable",
                retryable=False,
            )
        value = os.getenv(environment_name)
        if value is None or not value.strip():
            raise ProviderGatewayError(
                "model_credential_unavailable",
                retryable=False,
            )
        return value


class ProviderGatewayError(ModelExecutionError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        self.retryable = retryable
        super().__init__(code)

    def to_error_envelope(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message_key": f"errors.{self.code}",
            "retryable": self.retryable,
            "details": {},
        }


def _origin(parts: SplitResult) -> str:
    host = parts.hostname
    if host is None:
        raise ValueError("provider_url_invalid")
    formatted_host = f"[{host}]" if ":" in host else host
    if parts.port is None:
        return f"{parts.scheme}://{formatted_host}"
    return f"{parts.scheme}://{formatted_host}:{parts.port}"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validated_base_url(base_url: str, allowed_origins: Set[str]) -> str:
    parts = urlsplit(base_url)
    if (
        parts.scheme not in {"http", "https"}
        or parts.hostname is None
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("provider_url_invalid")
    if parts.scheme != "https" and not _is_loopback(parts.hostname):
        raise ValueError("provider_url_https_required")
    if _origin(parts) not in allowed_origins:
        raise ValueError("provider_url_not_allowlisted")
    return base_url.rstrip("/")


class OpenAICompatibleGateway:
    def __init__(
        self,
        *,
        base_url: str,
        allowed_origins: Set[str],
        credential: CredentialReference,
        credential_store: EnvironmentCredentialStore,
        allowed_tools: Set[str] = frozenset({"builtin-calculator"}),
        timeout_seconds: float = 30,
        max_response_bytes: int = 1_048_576,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("provider_timeout_invalid")
        if max_response_bytes < 256:
            raise ValueError("provider_response_limit_invalid")
        self.base_url = _validated_base_url(base_url, allowed_origins)
        self.credential = credential
        self.credential_store = credential_store
        self.allowed_tools = frozenset(allowed_tools)
        self.timeout = httpx.Timeout(timeout_seconds)
        self.limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        )
        self.max_response_bytes = max_response_bytes
        self.transport = transport

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleGateway("
            f"base_url={self.base_url!r}, "
            f"credential_ref={self.credential.credential_ref.root!r})"
        )

    def _payload(self, request: ModelRequest) -> dict[str, object]:
        return {
            "model": request.model,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "input": dict(request.input),
                            "locale": request.locale,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "builtin-calculator",
                        "description": "Perform one typed arithmetic operation.",
                        "parameters": {
                            "type": "object",
                            "required": ["operation", "left", "right"],
                            "properties": {
                                "operation": {
                                    "enum": [
                                        "add",
                                        "subtract",
                                        "multiply",
                                        "divide",
                                    ]
                                },
                                "left": {"type": "number"},
                                "right": {"type": "number"},
                            },
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": "required",
            "temperature": 0,
        }

    async def _read_response(self, response: httpx.Response) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > self.max_response_bytes:
                raise ProviderGatewayError(
                    "model_response_too_large",
                    retryable=False,
                )
        return bytes(body)

    def _provider_error(self, status_code: int) -> ProviderGatewayError:
        if status_code in {401, 403}:
            return ProviderGatewayError(
                "model_provider_authentication_failed",
                retryable=False,
            )
        if status_code == 429:
            return ProviderGatewayError(
                "model_provider_rate_limited",
                retryable=True,
            )
        if status_code >= 500:
            return ProviderGatewayError(
                "model_provider_unavailable",
                retryable=True,
            )
        return ProviderGatewayError(
            "model_provider_rejected_request",
            retryable=False,
        )

    def _tool_request(self, body: bytes) -> ToolRequest:
        try:
            document = json.loads(body)
            choice = document["choices"][0]
            tool_call = choice["message"]["tool_calls"][0]["function"]
            name = tool_call["name"]
            arguments = json.loads(tool_call["arguments"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderGatewayError(
                "model_response_invalid",
                retryable=False,
            ) from error
        if (
            not isinstance(name, str)
            or name not in self.allowed_tools
            or not isinstance(arguments, dict)
        ):
            raise ProviderGatewayError(
                "model_response_invalid",
                retryable=False,
            )
        return ToolRequest(
            tool_id=name,
            arguments=cast(dict[str, object], arguments),
        )

    async def complete(self, request: ModelRequest) -> ToolRequest:
        credential = self.credential_store.resolve(self.credential)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {credential}",
                        "Content-Type": "application/json",
                    },
                    json=self._payload(request),
                ) as response:
                    if not response.is_success:
                        raise self._provider_error(response.status_code)
                    body = await self._read_response(response)
        except ProviderGatewayError:
            raise
        except httpx.TimeoutException as error:
            raise ProviderGatewayError(
                "model_provider_timeout",
                retryable=True,
            ) from error
        except httpx.HTTPError as error:
            raise ProviderGatewayError(
                "model_provider_unavailable",
                retryable=True,
            ) from error
        finally:
            credential = ""
        return self._tool_request(body)
