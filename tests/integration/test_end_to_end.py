"""End-to-end integration tests for AgentLiar."""

import json

import pytest

from agentliar.api import Verifier, verify
from agentliar.engine import VerificationEngine
from agentliar.scorer import ConfidenceScorer


class TestEndToEndVerification:
    """Test complete verification workflows."""

    @pytest.mark.asyncio
    async def test_simple_task_verification(self) -> None:
        """Test a simple complete task."""
        task = "Create a hello world function in Python"

        claim = {
            "summary": "Created hello_world function",
            "files_modified": ["hello.py"],
        }

        file_changes = {
            "files": {
                "hello.py": "def hello_world():\n    print('Hello, World!')\n    return 'Hello, World!'"
            }
        }

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        assert result.score > 70
        assert result.passed
        assert len(result.check_results) == 4

    @pytest.mark.asyncio
    async def test_complex_task_verification(self) -> None:
        """Test a complex task with multiple files."""
        task = """Build a calculator module:
1. Create calculator.py with add, subtract, multiply, divide
2. Create test_calculator.py with unit tests
3. All functions should handle edge cases"""

        claim = {
            "summary": "Calculator module with tests implemented",
            "files_modified": ["calculator.py", "test_calculator.py"],
            "tests_added": ["test_calculator.py"],
            "tests_passed": 8,
        }

        file_changes = {
            "files": {
                "calculator.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""",
                "test_calculator.py": """
import pytest
from calculator import add, subtract, multiply, divide

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-2, 3) == -6

def test_divide():
    assert divide(6, 2) == 3
    assert divide(5, 2) == 2.5

def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(5, 0)
"""
            }
        }

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        assert result.score >= 80
        assert result.passed
        assert result.check_results["test_check"].passed

    @pytest.mark.asyncio
    async def test_incomplete_task_detection(self) -> None:
        """Test detection of incomplete tasks."""
        task = """Build a complete REST API:
1. User endpoints (CRUD)
2. Authentication
3. Input validation
4. Error handling
5. Tests for all endpoints"""

        claim = {
            "summary": "REST API implemented",
            "files_modified": ["api.py"],
        }

        file_changes = {
            "files": {
                "api.py": """
def get_users():
    return []

# TODO: implement other endpoints
"""
            }
        }

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        assert result.score < 70
        assert not result.passed


class TestReportGeneration:
    """Test report generation workflows."""

    @pytest.mark.asyncio
    async def test_json_report_generation(self) -> None:
        """Test JSON report generation."""
        task = "Create a simple function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"func.py": "def func(): pass"}}

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        # Generate JSON report
        json_report = result.generate_report(format="json")

        # Parse and verify
        data = json.loads(json_report)
        assert "passed" in data
        assert "score" in data
        assert "check_results" in data

    @pytest.mark.asyncio
    async def test_markdown_report_generation(self) -> None:
        """Test Markdown report generation."""
        task = "Create a simple function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"func.py": "def func(): pass"}}

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        # Generate Markdown report
        md_report = result.generate_report(format="markdown")

        assert "# AgentLiar Verification Report" in md_report
        assert str(result.score) in md_report

    @pytest.mark.asyncio
    async def test_console_report_generation(self) -> None:
        """Test console report generation."""
        task = "Create a simple function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"func.py": "def func(): pass"}}

        verifier = Verifier()
        result = await verifier.verify(task, claim, file_changes)

        # Generate console report
        console_report = result.generate_report(format="console")

        assert "AGENTLIAR" in console_report.upper()
        assert str(result.score) in console_report


class TestConvenienceFunction:
    """Test the convenience verify function."""

    @pytest.mark.asyncio
    async def test_verify_function(self) -> None:
        """Test the standalone verify function."""
        task = "Create hello function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"hello.py": "def hello(): return 'hi'"}}

        result = await verify(task, claim, file_changes)

        assert isinstance(result.score, float)
        assert hasattr(result, 'passed')
        assert hasattr(result, 'check_results')


class TestEngineIntegration:
    """Test VerificationEngine integration."""

    @pytest.mark.asyncio
    async def test_engine_runs_all_checks(self) -> None:
        """Test that engine runs all checks."""
        engine = VerificationEngine()

        task = "Create a function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"func.py": "def func(): pass"}}

        result = await engine.verify(task, claim, file_changes)

        assert "results" in result
        assert "file_check" in result["results"]
        assert "test_check" in result["results"]
        assert "scope_check" in result["results"]
        assert "llm_judge" in result["results"]

    @pytest.mark.asyncio
    async def test_engine_selective_checks(self) -> None:
        """Test running selective checks."""
        engine = VerificationEngine()

        task = "Create a function"
        claim = {"summary": "Done"}
        file_changes = {"files": {"func.py": "def func(): pass"}}

        result = await engine.verify(
            task, claim, file_changes,
            enabled_checks=["file_check", "scope_check"]
        )

        assert len(result["results"]) == 2
        assert "file_check" in result["results"]
        assert "scope_check" in result["results"]
        assert "test_check" not in result["results"]


class TestScorerIntegration:
    """Test ConfidenceScorer integration."""

    def test_scorer_with_all_passing(self) -> None:
        """Test scorer with all passing checks."""
        from agentliar.checks.base import CheckResult

        results = {
            "file_check": CheckResult("file_check", True, 1.0, "Good"),
            "test_check": CheckResult("test_check", True, 1.0, "Good"),
            "scope_check": CheckResult("scope_check", True, 1.0, "Good"),
            "llm_judge": CheckResult("llm_judge", True, 1.0, "Good"),
        }

        scorer = ConfidenceScorer()
        score = scorer.calculate(results)

        assert score.score == 100.0
        assert score.passed
        assert score.confidence_level == "high"

    def test_scorer_with_mixed_results(self) -> None:
        """Test scorer with mixed results."""
        from agentliar.checks.base import CheckResult

        results = {
            "file_check": CheckResult("file_check", True, 1.0, "Good"),
            "test_check": CheckResult("test_check", False, 0.0, "Bad"),
            "scope_check": CheckResult("scope_check", True, 0.8, "OK"),
            "llm_judge": CheckResult("llm_judge", True, 0.9, "Good"),
        }

        scorer = ConfidenceScorer()
        score = scorer.calculate(results)

        assert 0 < score.score < 100
        assert len(score.breakdown) == 4


class TestErrorHandling:
    """Test error handling in integration."""

    @pytest.mark.asyncio
    async def test_empty_task_description(self) -> None:
        """Test handling of empty task."""
        verifier = Verifier()

        # Should handle gracefully
        result = await verifier.verify("", {"summary": "Done"}, {"files": {}})

        # Should still return a result
        assert hasattr(result, 'score')

    @pytest.mark.asyncio
    async def test_empty_claim(self) -> None:
        """Test handling of empty claim."""
        verifier = Verifier()

        result = await verifier.verify("Task", {}, {"files": {}})

        assert hasattr(result, 'score')

    @pytest.mark.asyncio
    async def test_none_file_changes(self) -> None:
        """Test handling of None file_changes."""
        verifier = Verifier()

        result = await verifier.verify("Task", {"summary": "Done"}, None)

        assert hasattr(result, 'score')
