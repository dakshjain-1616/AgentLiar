"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from agentliar.config import Settings, get_settings, reload_settings


class TestSettings:
    """Test Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()

        assert settings.openrouter_model == "openai/gpt-4o-mini"
        assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert settings.openrouter_timeout == 30
        assert settings.openrouter_max_retries == 3
        assert settings.log_level == "INFO"
        assert settings.log_format == "text"
        assert settings.confidence_threshold == 70.0

    def test_weight_defaults(self) -> None:
        """Test default check weights."""
        settings = Settings()

        assert settings.file_check_weight == 0.25
        assert settings.test_check_weight == 0.25
        assert settings.scope_check_weight == 0.25
        assert settings.llm_judge_weight == 0.25

    def test_weight_validation(self) -> None:
        """Test weight validation."""
        # Valid weights
        settings = Settings(file_check_weight=0.5)
        assert settings.file_check_weight == 0.5

        # Invalid weights should raise validation error
        with pytest.raises(ValidationError):
            Settings(file_check_weight=1.5)

        with pytest.raises(ValidationError):
            Settings(file_check_weight=-0.1)

    def test_timeout_validation(self) -> None:
        """Test timeout validation."""
        # Valid timeout
        settings = Settings(openrouter_timeout=60)
        assert settings.openrouter_timeout == 60

        # Invalid timeouts
        with pytest.raises(ValidationError):
            Settings(openrouter_timeout=400)  # > 300

        with pytest.raises(ValidationError):
            Settings(openrouter_timeout=3)  # < 5

    def test_model_validation(self) -> None:
        """Test model validation accepts any string."""
        # Should accept any model string
        settings = Settings(openrouter_model="custom/model")
        assert settings.openrouter_model == "custom/model"

    def test_get_total_weight(self) -> None:
        """Test total weight calculation."""
        settings = Settings()
        assert settings.get_total_weight() == 1.0

        # Custom weights
        settings = Settings(
            file_check_weight=0.3,
            test_check_weight=0.3,
            scope_check_weight=0.2,
            llm_judge_weight=0.2,
        )
        assert settings.get_total_weight() == 1.0


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings(self) -> None:
        """Test get_settings returns Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_caches_result(self) -> None:
        """Test get_settings caches the result."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings_clears_cache(self) -> None:
        """Test reload_settings clears the cache."""
        settings1 = get_settings()
        settings2 = reload_settings()

        # Should be different instances
        assert settings1 is not settings2
        # But equal values
        assert settings1.openrouter_model == settings2.openrouter_model


class TestEnvironmentVariables:
    """Test environment variable loading."""

    @patch.dict(os.environ, {"OPENROUTER_MODEL": "anthropic/claude-3.5-sonnet"})
    def test_env_var_loading(self) -> None:
        """Test settings load from environment variables."""
        settings = reload_settings()
        assert settings.openrouter_model == "anthropic/claude-3.5-sonnet"

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_log_level_from_env(self) -> None:
        """Test log level from environment."""
        settings = reload_settings()
        assert settings.log_level == "DEBUG"

    @patch.dict(os.environ, {"FILE_CHECK_WEIGHT": "0.4"})
    def test_weight_from_env(self) -> None:
        """Test weight from environment."""
        settings = reload_settings()
        assert settings.file_check_weight == 0.4

    @patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "80.0"})
    def test_threshold_from_env(self) -> None:
        """Test threshold from environment."""
        settings = reload_settings()
        assert settings.confidence_threshold == 80.0
