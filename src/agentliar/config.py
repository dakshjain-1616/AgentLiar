"""Configuration management with Pydantic settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenRouter Configuration
    openrouter_api_key: str = Field(
        default="",
        description="OpenRouter API key for LLM judge",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Default model for LLM judge",
    )
    openrouter_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for OpenRouter API calls in seconds",
    )
    openrouter_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retries for OpenRouter API calls",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "text"] = Field(
        default="text",
        description="Log output format",
    )

    # Verification Configuration
    file_check_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for file verification check",
    )
    test_check_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for test integrity check",
    )
    scope_check_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for scope narrowing check",
    )
    llm_judge_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for LLM judge check",
    )

    # Confidence Scoring
    confidence_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum confidence score for passing verification",
    )

    @field_validator("openrouter_model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model field is a non-empty provider/model slug."""
        if "/" not in v or not v.strip():
            raise ValueError("Model must be in 'provider/model' format")
        return v

    @field_validator("file_check_weight", "test_check_weight", "scope_check_weight", "llm_judge_weight")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Validate weight is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")
        return v

    def get_total_weight(self) -> float:
        """Calculate total weight of all checks."""
        return (
            self.file_check_weight
            + self.test_check_weight
            + self.scope_check_weight
            + self.llm_judge_weight
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings from environment (clears cache)."""
    get_settings.cache_clear()
    return get_settings()
