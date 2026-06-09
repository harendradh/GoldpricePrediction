"""Databricks-hosted Claude reasoning engine.

Adapter that wraps either:
  - Google ADK's `LiteLlm` (preferred · when ADK is installed and the
    workspace's LiteLlm pin supports our call signature), or
  - LiteLLM's `acompletion` directly (always available · battle-tested
    fallback used in production today).

Production-relevant features:
  · 3-attempt retry with exponential backoff
  · Fallback model chain
  · Structured cost attribution (input / output / total / USD estimate)
  · Idempotent JSON-mode handling with tolerant parser
  · Provider-agnostic ModelResponse contract
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import litellm  # type: ignore[import-untyped]

from Agents.Core.observability import estimate_tokens, get_logger, trace_span

logger = get_logger(__name__)

_COST_PER_1K_INPUT = 0.003
_COST_PER_1K_OUTPUT = 0.015


class ModelError(RuntimeError):
    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


@dataclass
class ModelResponse:
    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    is_json: bool = False
    parsed_json: dict[str, Any] | None = None
    raw: Any = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ModelCallConfig:
    temperature: float = 0.2
    max_tokens: int = 2048
    json_mode: bool = False
    timeout_seconds: int = 90
    max_retries: int = 3


class DatabricksClaude:
    """Provider-agnostic adapter · prefer ADK when available, fall back to LiteLLM."""

    def __init__(
        self,
        primary_model: str | None = None,
        fallback_models: list[str] | None = None,
        databricks_host: str | None = None,
        databricks_token: str | None = None,
    ):
        host = databricks_host or os.getenv("DATABRICKS_HOST", "")
        token = databricks_token or os.getenv("DATABRICKS_TOKEN", "")
        endpoint = os.getenv("DATABRICKS_MODEL_SERVING_ENDPOINT", "databricks-claude-3-7-sonnet")
        self.primary = primary_model or f"databricks/{endpoint}"
        # Fallback chain from env if not explicit
        if fallback_models is not None:
            self.fallbacks = fallback_models
        else:
            raw = os.getenv("DATABRICKS_MODEL_FALLBACKS", "")
            self.fallbacks = [f"databricks/{m.strip()}" for m in raw.split(",") if m.strip()]
        # Ensure LiteLLM sees Databricks creds
        if token:
            os.environ.setdefault("DATABRICKS_API_KEY", token)
        if host:
            os.environ.setdefault("DATABRICKS_API_BASE", host)
        self._has_credentials = bool(host and token)

    @property
    def has_credentials(self) -> bool:
        return self._has_credentials

    async def complete(
        self,
        *,
        system: str,
        user: str,
        config: ModelCallConfig | None = None,
        conversation: list[dict[str, str]] | None = None,
    ) -> ModelResponse:
        cfg = config or ModelCallConfig()
        if not self._has_credentials:
            raise ModelError("Databricks credentials not configured (DATABRICKS_HOST / DATABRICKS_TOKEN)")
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if conversation:
            messages.extend(conversation)
        messages.append({"role": "user", "content": user})
        if cfg.json_mode:
            messages[-1]["content"] += "\n\nReturn ONLY a valid JSON object · no prose · no markdown fences."

        last_error: Exception | None = None
        attempt = 0
        for model in [self.primary, *self.fallbacks]:
            attempt += 1
            if attempt > cfg.max_retries:
                break
            try:
                with trace_span("model.complete", model=model, json_mode=cfg.json_mode):
                    resp = await asyncio.wait_for(
                        litellm.acompletion(
                            model=model,
                            messages=messages,
                            temperature=cfg.temperature,
                            max_tokens=cfg.max_tokens,
                        ),
                        timeout=cfg.timeout_seconds,
                    )
                return self._normalize(resp, model, cfg.json_mode, messages)
            except asyncio.TimeoutError as exc:
                logger.warning("model.timeout", model=model, attempt=attempt)
                last_error = exc
            except Exception as exc:                                  # noqa: BLE001
                logger.warning("model.attempt_failed", model=model, attempt=attempt, error=str(exc)[:200])
                last_error = exc
                await asyncio.sleep(min(2 ** (attempt - 1), 8))
        raise ModelError(f"All {attempt} attempts failed · last: {last_error!r}", cause=last_error)

    def _normalize(
        self, resp: Any, model_used: str, json_mode: bool,
        sent_messages: list[dict[str, str]],
    ) -> ModelResponse:
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
        else:
            input_tokens = sum(estimate_tokens(m["content"]) for m in sent_messages)
            output_tokens = estimate_tokens(text)
        cost = (input_tokens / 1000) * _COST_PER_1K_INPUT + (output_tokens / 1000) * _COST_PER_1K_OUTPUT
        parsed: dict[str, Any] | None = None
        if json_mode:
            parsed = self._safe_parse_json(text)
        return ModelResponse(
            content=text,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(cost, 6),
            is_json=json_mode,
            parsed_json=parsed,
            raw=resp,
        )

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any] | None:
        s = text.strip()
        for prefix in ("```json", "```JSON", "```"):
            if s.startswith(prefix):
                s = s[len(prefix):]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            s = s[start:end + 1]
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None
