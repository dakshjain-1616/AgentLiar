"""Custom exceptions for AgentLiar Detector."""

from typing import Any


class AgentLiarError(Exception):
    """Base exception for all AgentLiar errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(AgentLiarError):
    """Raised when there's a configuration error."""

    pass


class VerificationError(AgentLiarError):
    """Raised when a verification check fails."""

    def __init__(
        self,
        message: str,
        check_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.check_name = check_name


class LLMError(AgentLiarError):
    """Raised when there's an error with LLM API calls."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"status_code={self.status_code}")
        if self.response_body:
            parts.append(f"response={self.response_body[:200]}")
        return " | ".join(parts)


class FileCheckError(VerificationError):
    """Raised when file verification fails."""

    pass


class TestCheckError(VerificationError):
    """Raised when test verification fails."""

    pass


class ScopeCheckError(VerificationError):
    """Raised when scope verification fails."""

    pass


class ReportError(AgentLiarError):
    """Raised when report generation fails."""

    pass
