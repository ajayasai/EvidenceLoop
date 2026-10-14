"""Bounded native token counting for Gemini's official compatibility endpoint.

Protocol references: https://ai.google.dev/api/tokens and
https://ai.google.dev/gemini-api/docs/openai . No SDK or credential discovery.
The native count is an estimate of compatibility-endpoint accounting; the extra
reservation does not replace StructuredProvider's returned-usage bound check.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from urllib.parse import urlsplit

import httpx

from .provider import ProviderConfig, ProviderError

COUNT_TIMEOUT_SECONDS = 2.0
MAX_REQUEST_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 16 * 1024
OFFICIAL_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError("nonfinite value")


def _local_schema_only(value, depth=0):
    if depth > 64:
        raise ProviderError("gemini_counter_unsupported_request")
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (not isinstance(item, str) or not item.startswith("#")):
                raise ProviderError("gemini_counter_unsupported_request")
            _local_schema_only(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _local_schema_only(item, depth + 1)


class GeminiTokenCounter:
    """Count identical text/schema input, then reserve a compatibility margin.

    Accepts only the text-only system/user structured bodies emitted by the
    bounded provider. Tools, files, images and unknown prompt-bearing fields fail
    closed. One counter HTTP request is made per invocation, never a retry.
    The caller must independently confirm free access and disabled billing.
    """

    def __init__(self, config: ProviderConfig, *,
                 transport: httpx.AsyncBaseTransport | None = None,
                 overhead_tokens: int = 512):
        config.require_enabled()
        parsed = urlsplit(config.base_url)
        if (config.base_url.rstrip("/") != OFFICIAL_BASE or parsed.query or parsed.fragment
                or not re.fullmatch(r"(?:models/)?gemini-[A-Za-z0-9._-]{1,100}", config.model)
                or not config.api_key or not re.fullmatch(r"[!-~]{1,4096}", config.api_key)
                or type(overhead_tokens) is not int or overhead_tokens not in {256, 512}
                or type(config.max_requests) is not int or config.max_requests < 1):
            raise ProviderError("invalid_gemini_counter_configuration")
        self.config = config
        self.transport = transport
        self.overhead_tokens = overhead_tokens
        self.requests_used = 0
        self._model = config.model.removeprefix("models/")
        self._url = "https://generativelanguage.googleapis.com/v1beta/models/" + self._model + ":countTokens"

    def _native_request(self, body: dict) -> bytes:
        allowed = {"model", "messages", "response_format", "max_tokens", "stream", "temperature", "reasoning_effort"}
        if (not isinstance(body, dict) or set(body) - allowed or body.get("model") != self.config.model
                or body.get("stream", False) is not False):
            raise ProviderError("gemini_counter_unsupported_request")
        messages = body.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= 4:
            raise ProviderError("gemini_counter_unsupported_request")
        contents, system = [], None
        for index, message in enumerate(messages):
            if (not isinstance(message, dict) or set(message) != {"role", "content"}
                    or not isinstance(message["content"], str)):
                raise ProviderError("gemini_counter_unsupported_request")
            part = {"text": message["content"]}
            if message["role"] == "system" and index == 0:
                system = {"parts": [part]}
            elif message["role"] == "user":
                contents.append({"role": "user", "parts": [part]})
            else:
                raise ProviderError("gemini_counter_unsupported_request")
        if not contents:
            raise ProviderError("gemini_counter_unsupported_request")
        response_format = body.get("response_format")
        if (not isinstance(response_format, dict) or set(response_format) != {"type", "json_schema"}
                or response_format.get("type") != "json_schema"):
            raise ProviderError("gemini_counter_unsupported_request")
        specification = response_format["json_schema"]
        if (not isinstance(specification, dict) or set(specification) - {"name", "strict", "schema"}
                or specification.get("strict") is not True or not isinstance(specification.get("schema"), dict)):
            raise ProviderError("gemini_counter_unsupported_request")
        schema = specification["schema"]
        _local_schema_only(schema)
        generation = {"responseMimeType": "application/json", "responseJsonSchema": schema}
        if "max_tokens" in body:
            if type(body["max_tokens"]) is not int or not 1 <= body["max_tokens"] <= 2200:
                raise ProviderError("gemini_counter_unsupported_request")
            generation["maxOutputTokens"] = body["max_tokens"]
        if "temperature" in body:
            value = body["temperature"]
            if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 2:
                raise ProviderError("gemini_counter_unsupported_request")
            generation["temperature"] = value
        # reasoning_effort changes output-generation policy, not input text.
        # Its output tokens remain subject to the provider's usage accounting.
        if "reasoning_effort" in body and body["reasoning_effort"] not in {"none", "minimal", "low", "medium", "high"}:
            raise ProviderError("gemini_counter_unsupported_request")
        request = {"model": "models/" + self._model, "contents": contents, "generationConfig": generation}
        if system is not None:
            request["systemInstruction"] = system
        try:
            raw = json.dumps({"generateContentRequest": request}, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise ProviderError("gemini_counter_unsupported_request") from None
        if len(raw) > MAX_REQUEST_BYTES:
            raise ProviderError("gemini_counter_request_too_large")
        return raw

    async def __call__(self, body: dict) -> int:
        raw = self._native_request(body)
        if self.requests_used >= self.config.max_requests:
            raise ProviderError("gemini_counter_quota_exhausted")
        self.requests_used += 1
        try:
            async with asyncio.timeout(COUNT_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(timeout=COUNT_TIMEOUT_SECONDS, transport=self.transport,
                                             trust_env=False, follow_redirects=False) as client:
                    async with client.stream("POST", self._url, content=raw,
                            headers={"Content-Type": "application/json", "x-goog-api-key": self.config.api_key}) as response:
                        if response.status_code == 429:
                            raise ProviderError("gemini_counter_quota_exhausted")
                        if response.status_code in {401, 403}:
                            raise ProviderError("gemini_counter_access_denied")
                        if response.status_code == 404:
                            raise ProviderError("gemini_counter_model_unavailable")
                        if response.status_code != 200:
                            raise ProviderError("token_counter_unavailable")
                        output = bytearray()
                        async for chunk in response.aiter_bytes():
                            output.extend(chunk)
                            if len(output) > MAX_RESPONSE_BYTES:
                                raise ProviderError("token_counter_invalid")
            result = json.loads(output, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            count = result.get("totalTokens") if isinstance(result, dict) else None
            if type(count) is not int or not 1 <= count <= 10_000_000:
                raise ProviderError("token_counter_invalid")
            return count + self.overhead_tokens
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderError("token_counter_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("token_counter_unavailable") from None
        except (ValueError, UnicodeError):
            raise ProviderError("token_counter_invalid") from None
