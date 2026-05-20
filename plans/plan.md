# AgentLiar Detector — Task Completion Verifier

## Goal
Build a complete, production-ready system to detect when coding agents falsely claim task completion. Performs 4 independent verification checks and returns a confidence score (0-100) with evidence.

## Research Summary
- **OpenRouter Model IDs (April 2026)**: `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`, `openai/gpt-4o-mini` — verified valid
- **GitHub Actions**: Composite action structure with action.yml metadata, inputs/outputs, runs.steps
- **Python Packaging**: pyproject.toml with setuptools, pytest, mypy, ruff
- **LLM Judge Pattern**: Structured output with JSON schema validation, timeout/retry logic essential

## Approach

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    AgentLiar Detector                        │
├─────────────────────────────────────────────────────────────┤
│  Input: Task description + Agent claim + File changes      │
│                          ↓                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Verification Engine                       │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │ File Check  │ │ Test Check  │ │ Scope Check │     │   │
│  │  │  (local)    │ │  (local)    │ │  (local)    │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │        Second Opinion (LLM Judge)                │ │   │
│  │  │   OpenRouter: claude-3.5-sonnet / gpt-4o         │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Confidence Scorer (weighted aggregation)      │   │
│  │         Report Generator (JSON/Markdown)            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Delivery Modes
1. **CLI Tool**: `agentliar verify --task-file task.md --claim-file claim.json`
2. **Python Library**: `from agentliar import Verifier; result = verifier.verify(...)`
3. **GitHub Action**: Composite action for CI/CD integration
4. **Slash Command Hook**: `/verify` style integration endpoint

## Subtasks

### Phase 1: Core Foundation
1. **Project structure setup** — pyproject.toml, src layout, config files
   - Expected: `/home/daksh/may20/projects/agentliar/pyproject.toml`, `/home/daksh/may20/projects/agentliar/src/agentliar/__init__.py`
   - Verify: `pip install -e .` succeeds

2. **Configuration system** — Pydantic settings, env file support
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/config.py`, `.env.example`
   - Verify: Config loads from env vars and files

3. **Logging and error handling** — structured logging, custom exceptions
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/exceptions.py`, `/home/daksh/may20/projects/agentliar/src/agentliar/logging_config.py`
   - Verify: Logs are structured and exceptions are catchable

### Phase 2: Verification Checks
4. **File verification check** — Compare changed files against task requirements
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/checks/file_check.py`
   - Verify: Detects missing expected files, unexpected new files, file content mismatches

5. **Test integrity check** — Detect trivially passing tests, pre-existing pass states
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/checks/test_check.py`
   - Verify: Detects empty test bodies, tests that pass without assertions, skipped tests

6. **Scope check** — Detect silent task narrowing
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/checks/scope_check.py`
   - Verify: Compares claimed completion against original task scope

7. **Second opinion LLM judge** — Call external model via OpenRouter
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/checks/llm_judge.py`
   - Verify: Structured JSON output, timeout/retry logic, clear failure states

### Phase 3: Integration & Aggregation
8. **Verification engine** — Orchestrate all checks, aggregate results
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/engine.py`
   - Verify: Runs checks in parallel where possible, handles partial failures

9. **Confidence scorer** — Weighted aggregation of check results
   - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/scorer.py`
   - Verify: 0-100 score calculation, configurable weights

10. **Report generator** — JSON and Markdown output formats
    - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/report.py`
    - Verify: Valid JSON schema, readable Markdown with evidence

### Phase 4: Delivery Modes
11. **CLI implementation** — Click-based command line interface
    - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/cli.py`
    - Verify: `agentliar --help` works, all commands functional

12. **Python library wrapper** — Clean public API
    - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/api.py`
    - Verify: `from agentliar import Verifier; v = Verifier(); v.verify(...)` works

13. **GitHub Action** — Composite action with action.yml
    - Expected: `/home/daksh/may20/projects/agentliar/action.yml`, `.github/workflows/example.yml`
    - Verify: Action metadata valid, inputs/outputs defined

14. **Slash command hook** — FastAPI endpoint for integration
    - Expected: `/home/daksh/may20/projects/agentliar/src/agentliar/server.py`
    - Verify: POST endpoint accepts verification requests

### Phase 5: Testing & Quality
15. **Unit tests** — pytest suite with 90%+ coverage
    - Expected: `/home/daksh/may20/projects/agentliar/tests/` with test files for each module
    - Verify: `pytest` passes, coverage report generated

16. **Adversarial tests** — False completion cases
    - Expected: `/home/daksh/may20/projects/agentliar/tests/adversarial/`
    - Verify: Tests detect deliberately misleading claims

17. **Integration tests** — End-to-end verification scenarios
    - Expected: `/home/daksh/may20/projects/agentliar/tests/integration/`
    - Verify: Full pipeline runs successfully

18. **Tooling config** — ruff, mypy, pytest configuration
    - Expected: `/home/daksh/may20/projects/agentliar/pyproject.toml` (tool sections)
    - Verify: `ruff check .`, `mypy src/`, `pytest` all pass

### Phase 6: Documentation
19. **README.md** — Complete documentation with Mermaid diagram
    - Expected: `/home/daksh/may20/projects/agentliar/README.md`
    - Verify: All commands in README are runnable, diagram matches code

20. **Example files** — Sample task, claim, and config files
    - Expected: `/home/daksh/may20/projects/agentliar/examples/`
    - Verify: Examples are valid and demonstrate usage

## Deliverables

| File Path | Description |
|-----------|-------------|
| `/home/daksh/may20/projects/agentliar/pyproject.toml` | Package metadata and tool config |
| `/home/daksh/may20/projects/agentliar/src/agentliar/` | Main source package |
| `/home/daksh/may20/projects/agentliar/src/agentliar/__init__.py` | Package exports |
| `/home/daksh/may20/projects/agentliar/src/agentliar/config.py` | Configuration management |
| `/home/daksh/may20/projects/agentliar/src/agentliar/exceptions.py` | Custom exceptions |
| `/home/daksh/may20/projects/agentliar/src/agentliar/logging_config.py` | Structured logging |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/` | Verification check implementations |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/file_check.py` | File alignment check |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/test_check.py` | Test integrity check |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/scope_check.py` | Scope narrowing check |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/llm_judge.py` | LLM second opinion |
| `/home/daksh/may20/projects/agentliar/src/agentliar/checks/__init__.py` | Check exports |
| `/home/daksh/may20/projects/agentliar/src/agentliar/engine.py` | Verification orchestration |
| `/home/daksh/may20/projects/agentliar/src/agentliar/scorer.py` | Confidence scoring |
| `/home/daksh/may20/projects/agentliar/src/agentliar/report.py` | Report generation |
| `/home/daksh/may20/projects/agentliar/src/agentliar/cli.py` | Command line interface |
| `/home/daksh/may20/projects/agentliar/src/agentliar/api.py` | Public Python API |
| `/home/daksh/may20/projects/agentliar/src/agentliar/server.py` | HTTP server for slash commands |
| `/home/daksh/may20/projects/agentliar/action.yml` | GitHub Action metadata |
| `/home/daksh/may20/projects/agentliar/.github/workflows/` | Example workflow files |
| `/home/daksh/may20/projects/agentliar/tests/` | Test suite |
| `/home/daksh/may20/projects/agentliar/tests/unit/` | Unit tests |
| `/home/daksh/may20/projects/agentliar/tests/adversarial/` | Adversarial false-completion tests |
| `/home/daksh/may20/projects/agentliar/tests/integration/` | Integration tests |
| `/home/daksh/may20/projects/agentliar/.env.example` | Example environment variables |
| `/home/daksh/may20/projects/agentliar/examples/` | Usage examples |
| `/home/daksh/may20/projects/agentliar/README.md` | Complete documentation |

## Evaluation Criteria
- All 4 verification checks implemented and functional
- Confidence score (0-100) accurately reflects verification results
- CLI, library, GitHub Action, and server all functional
- Test coverage ≥ 90%
- All linting (ruff) and type checking (mypy) pass
- README commands are real and runnable
- No hardcoded secrets
- Valid model references only (anthropic/claude-3.5-sonnet, openai/gpt-4o, openai/gpt-4o-mini)

## Notes
- OpenRouter API key available at `/home/daksh/.neo/integrations/openrouter.env`
- OpenAI API key available at `/home/daksh/.neo/integrations/openai.env`
- No GPU required — this is an API-based tool
- All network calls must have timeout (30s default) and retry (3 attempts with exponential backoff)
