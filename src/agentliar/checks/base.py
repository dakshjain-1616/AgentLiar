"""Base class for verification checks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agentliar.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CheckResult:
    """Result of a verification check."""

    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate score is in valid range."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "score": self.score,
            "message": self.message,
            "details": self.details,
            "evidence": self.evidence,
        }


class BaseCheck(ABC):
    """Abstract base class for all verification checks."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"agentliar.checks.{name}")

    @abstractmethod
    async def run(
        self,
        task_description: str,
        claim: dict[str, Any],
        file_changes: dict[str, Any],
    ) -> CheckResult:
        """Run the verification check.

        Args:
            task_description: Original task description
            claim: Agent's claim about task completion
            file_changes: Dictionary of file changes made

        Returns:
            CheckResult with verification outcome
        """
        pass

    def _log_start(self, **kwargs: Any) -> None:
        """Log check start."""
        self.logger.info(f"{self.name}_started", **kwargs)

    def _log_complete(self, result: CheckResult) -> None:
        """Log check completion."""
        self.logger.info(
            f"{self.name}_completed",
            passed=result.passed,
            score=result.score,
            message=result.message,
        )
