"""Tests for test integrity check."""

from typing import Any

import pytest

from agentliar.checks.test_check import CheckResult, TestCheck


class TestTestCheck:
    """Test TestCheck class."""

    @pytest.fixture
    def test_check(self) -> TestCheck:
        """Create a TestCheck instance."""
        return TestCheck()

    @pytest.mark.asyncio
    async def test_no_tests_neutral(self, test_check: TestCheck) -> None:
        """Test that no tests gives neutral score."""
        task = "Simple task"
        claim = {"summary": "Done"}
        changes: dict[str, Any] = {"files": {}}

        result = await test_check.run(task, claim, changes)

        assert isinstance(result, CheckResult)
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_claimed_but_no_tests(self, test_check: TestCheck) -> None:
        """Test detection of claimed tests without files."""
        task = "Simple task"
        claim = {
            "summary": "Done",
            "tests_added": ["test_main.py"],
            "tests_passed": 5,
        }
        changes: dict[str, Any] = {"files": {}}

        result = await test_check.run(task, claim, changes)

        assert not result.passed
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_test_body(self, test_check: TestCheck) -> None:
        """Test detection of empty test bodies."""
        task = "Create tests"
        claim = {"summary": "Done", "tests_added": ["test_main.py"]}
        changes = {"files": {
            "test_main.py": """
def test_something():
    pass
"""
        }}

        result = await test_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0
        assert result.details["trivial_tests"] > 0

    @pytest.mark.asyncio
    async def test_no_assertions(self, test_check: TestCheck) -> None:
        """Test detection of tests without assertions."""
        task = "Create tests"
        claim = {"summary": "Done"}
        changes = {"files": {
            "test_main.py": """
def test_something():
    x = 1 + 1
"""
        }}

        result = await test_check.run(task, claim, changes)

        assert not result.passed or result.score < 1.0

    @pytest.mark.asyncio
    async def test_valid_tests_pass(self, test_check: TestCheck) -> None:
        """Test that valid tests pass."""
        task = "Create tests"
        claim = {"summary": "Done", "tests_added": ["test_main.py"]}
        changes = {"files": {
            "test_main.py": """
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    result = 5 - 3
    assert result == 2
"""
        }}

        result = await test_check.run(task, claim, changes)

        assert result.passed
        assert result.score == 1.0
        assert result.details["assertion_count"] >= 2

    @pytest.mark.asyncio
    async def test_skipped_tests(self, test_check: TestCheck) -> None:
        """Test detection of skipped tests."""
        task = "Create tests"
        claim = {"summary": "Done"}
        changes = {"files": {
            "test_main.py": """
import pytest

@pytest.mark.skip
def test_skipped():
    assert True

def test_normal():
    assert True
"""
        }}

        result = await test_check.run(task, claim, changes)

        assert result.details["skipped_tests"] == 1


class TestIsTestFile:
    """Test test file detection."""

    @pytest.fixture
    def test_check(self) -> TestCheck:
        return TestCheck()

    def test_test_prefix(self, test_check: TestCheck) -> None:
        """Test test_ prefix detection."""
        assert test_check._is_test_file("test_main.py")
        assert test_check._is_test_file("test_utils.py")

    def test_test_suffix(self, test_check: TestCheck) -> None:
        """Test _test suffix detection."""
        assert test_check._is_test_file("main_test.py")
        assert test_check._is_test_file("utils_test.py")

    def test_tests_directory(self, test_check: TestCheck) -> None:
        """Test tests/ directory detection."""
        assert test_check._is_test_file("tests/test_main.py")
        assert test_check._is_test_file("test/test_utils.py")

    def test_non_test_files(self, test_check: TestCheck) -> None:
        """Test non-test files are not detected."""
        assert not test_check._is_test_file("main.py")
        assert not test_check._is_test_file("utils.py")
        assert not test_check._is_test_file("README.md")


class TestAnalyzeTestFunction:
    """Test test function analysis."""

    @pytest.fixture
    def test_check(self) -> TestCheck:
        return TestCheck()

    def test_empty_body(self, test_check: TestCheck) -> None:
        """Test empty body detection."""
        code = """
def test_empty():
    pass
"""
        import ast
        tree = ast.parse(code)
        func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]

        analysis = test_check._analyze_test_function(func)

        assert analysis["is_trivial"]
        assert "pass" in analysis["trivial_reason"].lower()

    def test_ellipsis_body(self, test_check: TestCheck) -> None:
        """Test ellipsis body detection."""
        code = """
def test_ellipsis():
    ...
"""
        import ast
        tree = ast.parse(code)
        func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]

        analysis = test_check._analyze_test_function(func)

        assert analysis["is_trivial"]

    def test_with_assertions(self, test_check: TestCheck) -> None:
        """Test proper assertion counting."""
        code = """
def test_with_asserts():
    assert True
    assert 1 == 1
    self.assertEqual(1, 1)
"""
        import ast
        tree = ast.parse(code)
        func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]

        analysis = test_check._analyze_test_function(func)

        assert analysis["assertions"] >= 2
        assert not analysis["is_trivial"]

    def test_skip_decorator(self, test_check: TestCheck) -> None:
        """Test skip decorator detection."""
        code = """
import pytest

@pytest.mark.skip
def test_skipped():
    assert True
"""
        import ast
        tree = ast.parse(code)
        func = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)][0]

        analysis = test_check._analyze_test_function(func)

        assert analysis["is_skipped"]
