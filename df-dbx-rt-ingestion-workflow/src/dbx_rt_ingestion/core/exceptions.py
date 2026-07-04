"""Standardized error hierarchy.

Every framework error carries a stable ``error_code`` (used by alerting and
runbooks) and a ``context`` dict with structured diagnostic detail. Application
code should raise the most specific subclass available.
"""

from __future__ import annotations

from typing import Any


class FrameworkError(Exception):
    """Base class for all framework errors."""

    error_code: str = "DFX-0000"

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_type": type(self).__name__,
            "message": self.message,
            "context": self.context,
        }

    def __str__(self) -> str:
        base = f"[{self.error_code}] {self.message}"
        return f"{base} | context={self.context}" if self.context else base


class ConfigurationError(FrameworkError):
    """Invalid, missing, or unresolvable configuration."""

    error_code = "DFX-1000"


class SpecValidationError(ConfigurationError):
    """Application specification failed schema/semantic validation."""

    error_code = "DFX-1001"


class SecretResolutionError(ConfigurationError):
    """A ${secret:...} placeholder could not be resolved."""

    error_code = "DFX-1002"


class AuthenticationError(FrameworkError):
    """Authentication provider construction or handshake failure."""

    error_code = "DFX-2000"


class SourceError(FrameworkError):
    """Streaming source construction or read failure."""

    error_code = "DFX-3000"


class ParserError(FrameworkError):
    """Parser construction or parse-time failure."""

    error_code = "DFX-4000"


class SchemaError(FrameworkError):
    """Schema resolution failure."""

    error_code = "DFX-5000"


class SchemaCompatibilityError(SchemaError):
    """Schema evolution violates the configured compatibility mode."""

    error_code = "DFX-5001"


class SinkError(FrameworkError):
    """Sink construction or write failure."""

    error_code = "DFX-6000"


class PipelineError(FrameworkError):
    """Pipeline orchestration failure."""

    error_code = "DFX-7000"


class RetryExhaustedError(PipelineError):
    """All retry attempts were consumed without success."""

    error_code = "DFX-7001"


class QualityError(FrameworkError):
    """Data quality rule compilation or enforcement failure."""

    error_code = "DFX-8000"
