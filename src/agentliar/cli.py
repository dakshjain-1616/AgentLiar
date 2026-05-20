"""Command line interface for AgentLiar Detector."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentliar.config import get_settings, reload_settings
from agentliar.engine import VerificationEngine
from agentliar.exceptions import AgentLiarError
from agentliar.logging_config import configure_logging, get_logger
from agentliar.report import ReportGenerator, create_report
from agentliar.scorer import ConfidenceScorer

# Initialize console for rich output
console = Console()
logger = get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="agentliar")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to configuration file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool) -> None:
    """AgentLiar Detector - Verify agent task completion claims."""
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Configure logging
    configure_logging()

    # Load custom config if provided
    if config:
        # Set environment variable for config file
        import os
        os.environ["AGENTLIAR_CONFIG"] = config
        reload_settings()


@cli.command()
@click.option(
    "--task-file",
    "-t",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to task description file",
)
@click.option(
    "--claim-file",
    "-c",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to claim JSON file",
)
@click.option(
    "--changes-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to file changes JSON file (optional)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False),
    help="Directory to write reports to",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "markdown", "console", "all"], case_sensitive=False),
    default="console",
    help="Output format",
)
@click.option(
    "--checks",
    type=str,
    help="Comma-separated list of checks to run (default: all)",
)
@click.option(
    "--threshold",
    type=float,
    default=None,
    help="Confidence threshold (0-100, overrides config)",
)
@click.pass_context
def verify(
    ctx: click.Context,
    task_file: str,
    claim_file: str,
    changes_file: str | None,
    output_dir: str | None,
    fmt: str,
    checks: str | None,
    threshold: float | None,
) -> None:
    """Verify a task completion claim."""
    try:
        # Load inputs
        task_description = Path(task_file).read_text()
        claim = json.loads(Path(claim_file).read_text())

        # Load file changes if provided
        if changes_file:
            file_changes = json.loads(Path(changes_file).read_text())
        else:
            # Try to extract from claim
            file_changes = claim.get("file_changes", {"files": {}})

        # Parse enabled checks
        enabled_checks = None
        if checks:
            enabled_checks = [c.strip() for c in checks.split(",")]

        # Run verification
        result = asyncio.run(_run_verification(
            task_description,
            claim,
            file_changes,
            enabled_checks,
            threshold,
        ))

        # Output results
        _output_results(result, fmt, output_dir)

        # Exit with appropriate code
        if not result["confidence_score"].passed:
            sys.exit(1)

    except AgentLiarError as e:
        console.print(f"[red]Error: {e}[/red]")
        if ctx.obj.get("verbose"):
            raise
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if ctx.obj.get("verbose"):
            raise
        sys.exit(2)


async def _run_verification(
    task_description: str,
    claim: dict[str, Any],
    file_changes: dict[str, Any],
    enabled_checks: list[str] | None,
    threshold: float | None,
) -> dict[str, Any]:
    """Run verification and return results."""
    settings = get_settings()

    # Override threshold if provided
    if threshold is not None:
        settings.confidence_threshold = threshold

    # Create engine and run verification
    engine = VerificationEngine(settings)
    verification_results = await engine.verify(
        task_description,
        claim,
        file_changes,
        enabled_checks,
    )

    # Calculate confidence score
    scorer = ConfidenceScorer(settings)
    check_results = dict(verification_results["results"].items())
    # Convert dict results back to CheckResult objects for scorer
    from agentliar.checks.base import CheckResult
    check_result_objects = {}
    for name, r in check_results.items():
        check_result_objects[name] = CheckResult(
            check_name=r["check_name"],
            passed=r["passed"],
            score=r["score"],
            message=r["message"],
            details=r.get("details", {}),
            evidence=r.get("evidence", []),
        )

    confidence_score = scorer.calculate(check_result_objects)

    # Create report
    report = create_report(
        task_description=task_description,
        claim=claim,
        check_results=check_result_objects,
        confidence_score=confidence_score,
        metadata={
            "version": "0.1.0",
            "enabled_checks": enabled_checks or ["all"],
        },
    )

    return {
        "verification": verification_results,
        "confidence_score": confidence_score,
        "report": report,
    }


def _output_results(
    result: dict[str, Any],
    fmt: str,
    output_dir: str | None,
) -> None:
    """Output results in the specified format."""
    report = result["report"]
    generator = ReportGenerator()

    if fmt == "json":
        output = generator.generate_json(report)
        if output_dir:
            console.print(f"[green]JSON report written to {output_dir}/report.json[/green]")
        else:
            console.print(output)

    elif fmt == "markdown":
        output = generator.generate_markdown(report)
        if output_dir:
            console.print(f"[green]Markdown report written to {output_dir}/report.md[/green]")
        else:
            console.print(output)

    elif fmt == "all":
        if not output_dir:
            output_dir = "."
        paths = generator.generate_all(report, output_dir)
        console.print("[green]Reports written to:[/green]")
        for fmt_name, path in paths.items():
            console.print(f"  - {fmt_name}: {path}")

    else:  # console
        _print_console_report(report)


def _print_console_report(report: Any) -> None:
    """Print a rich console report."""
    score = report.confidence_score

    # Header panel
    header_text = Text()
    header_text.append("AgentLiar Verification Report\n", style="bold")
    header_text.append(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    console.print(Panel(header_text, border_style="blue"))

    # Score panel
    score_color = "green" if score.passed else "red"
    if score.score < 50:
        score_color = "red"
    elif score.score < 70:
        score_color = "yellow"

    score_text = Text()
    score_text.append("Confidence Score: ", style="bold")
    score_text.append(f"{score.score:.1f}/100\n", style=f"bold {score_color}")
    score_text.append("Status: ", style="bold")
    score_text.append(
        "PASSED" if score.passed else "FAILED",
        style=f"bold {score_color}",
    )
    score_text.append(f"\nLevel: {score.confidence_level.upper()}")

    console.print(Panel(score_text, title="Summary", border_style=score_color))

    # Check results table
    table = Table(title="Check Results")
    table.add_column("Check", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Message")

    for name, check_result in report.check_results.items():
        status = "✓" if check_result.passed else "✗"
        status_style = "green" if check_result.passed else "red"
        table.add_row(
            name.replace("_", " ").title(),
            f"{check_result.score:.2f}",
            f"[{status_style}]{status}[/{status_style}]",
            check_result.message[:50] + "..." if len(check_result.message) > 50 else check_result.message,
        )

    console.print(table)

    # Recommendations
    if score.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for i, rec in enumerate(score.recommendations, 1):
            console.print(f"  {i}. {rec}")

    # Footer
    console.print("\n[dim]Run with --format markdown or --format json for detailed output[/dim]")


@cli.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="AgentLiar Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("OpenRouter Model", settings.openrouter_model)
    table.add_row("OpenRouter Timeout", str(settings.openrouter_timeout))
    table.add_row("OpenRouter Max Retries", str(settings.openrouter_max_retries))
    table.add_row("Log Level", settings.log_level)
    table.add_row("Log Format", settings.log_format)
    table.add_row("Confidence Threshold", str(settings.confidence_threshold))
    table.add_row("File Check Weight", f"{settings.file_check_weight:.0%}")
    table.add_row("Test Check Weight", f"{settings.test_check_weight:.0%}")
    table.add_row("Scope Check Weight", f"{settings.scope_check_weight:.0%}")
    table.add_row("LLM Judge Weight", f"{settings.llm_judge_weight:.0%}")

    console.print(table)


@cli.command()
@click.argument("task_file", type=click.Path(exists=True, dir_okay=False))
def analyze(task_file: str) -> None:
    """Analyze a task file and show what would be checked."""
    task_description = Path(task_file).read_text()

    # Extract expected files
    from agentliar.checks.file_check import FileCheck
    file_check = FileCheck()
    expected_files = file_check._extract_expected_files(task_description)

    # Extract requirements
    from agentliar.checks.scope_check import ScopeCheck
    scope_check = ScopeCheck()
    requirements = scope_check._extract_requirements(task_description)

    console.print(Panel(f"Task Analysis: {task_file}", border_style="blue"))

    if expected_files:
        console.print("\n[bold]Expected Files:[/bold]")
        for f in expected_files:
            console.print(f"  • {f}")
    else:
        console.print("\n[dim]No specific files detected in task description[/dim]")

    if requirements:
        console.print("\n[bold]Detected Requirements:[/bold]")
        for i, req in enumerate(requirements[:10], 1):
            console.print(f"  {i}. {req[:80]}{'...' if len(req) > 80 else ''}")
    else:
        console.print("\n[dim]No specific requirements detected[/dim]")


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
