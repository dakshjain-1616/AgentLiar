"""FastAPI server for slash command integration."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agentliar.api import Verifier
from agentliar.config import get_settings
from agentliar.exceptions import AgentLiarError
from agentliar.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


# Request/Response models

class VerifyRequest(BaseModel):
    """Request model for verification endpoint."""

    task_description: str = Field(
        ...,
        description="Original task description",
        min_length=10,
    )
    claim: dict[str, Any] = Field(
        ...,
        description="Agent's claim about task completion",
    )
    file_changes: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of file changes made",
    )
    enabled_checks: list[str] | None = Field(
        default=None,
        description="List of checks to run (default: all)",
    )
    threshold: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Confidence threshold override",
    )


class VerifyResponse(BaseModel):
    """Response model for verification endpoint."""

    success: bool
    confidence_score: float = Field(..., ge=0, le=100)
    passed: bool
    confidence_level: str
    check_results: dict[str, dict[str, Any]]
    issues: list[dict[str, Any]]
    recommendations: list[str]
    metadata: dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    checks_available: list[str]
    configuration: dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    code: str | None = None


# FastAPI app

@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    # Startup
    configure_logging()
    logger.info("server_starting")
    yield
    # Shutdown
    logger.info("server_shutting_down")


app = FastAPI(
    title="AgentLiar Detector API",
    description="Verify agent task completion claims with confidence scoring",
    version="0.1.0",
    lifespan=lifespan,
)


# Exception handlers

@app.exception_handler(AgentLiarError)
async def agentliar_exception_handler(request: Request, exc: AgentLiarError) -> JSONResponse:
    """Handle AgentLiar exceptions."""
    logger.error(
        "api_error",
        error=str(exc),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error=str(exc),
            detail=str(exc.details) if hasattr(exc, "details") and exc.details is not None else None,
            code=type(exc).__name__,
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.error(
        "unexpected_error",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if get_settings().log_level == "DEBUG" else None,
            code="InternalError",
        ).dict(),
    )


# Endpoints

@app.get("/", response_model=dict)
async def root() -> dict[str, Any]:
    """Root endpoint with API info."""
    return {
        "name": "AgentLiar Detector API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "verify": "/verify",
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    settings = get_settings()

    # Check configuration
    config_status = {
        "openrouter_configured": bool(settings.openrouter_api_key),
        "model": settings.openrouter_model,
        "weights_valid": abs(settings.get_total_weight() - 1.0) < 0.001,
    }

    return {
        "status": "healthy" if config_status["weights_valid"] else "degraded",
        "version": "0.1.0",
        "checks_available": [
            "file_check",
            "test_check",
            "scope_check",
            "llm_judge",
        ],
        "configuration": config_status,
    }


@app.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest) -> dict[str, Any]:
    """Verify a task completion claim.

    This is the main endpoint for running verification checks.
    """
    logger.info(
        "verify_request",
        task_length=len(request.task_description),
        claim_keys=list(request.claim.keys()),
    )

    try:
        # Create verifier with optional threshold override
        settings = get_settings()
        if request.threshold is not None:
            settings.confidence_threshold = request.threshold

        verifier = Verifier(settings)

        # Run verification
        result = await verifier.verify(
            task_description=request.task_description,
            claim=request.claim,
            file_changes=request.file_changes or {"files": {}},
            enabled_checks=request.enabled_checks,
        )

        logger.info(
            "verify_completed",
            score=result.score,
            passed=result.passed,
        )

        return {
            "success": True,
            "confidence_score": result.score,
            "passed": result.passed,
            "confidence_level": result.confidence_score.confidence_level,
            "check_results": {
                name: {
                    "passed": r.passed,
                    "score": r.score,
                    "message": r.message,
                    "details": r.details,
                    "evidence": r.evidence,
                }
                for name, r in result.check_results.items()
            },
            "issues": result.issues,
            "recommendations": result.confidence_score.recommendations,
            "metadata": {
                "version": "0.1.0",
                "threshold": settings.confidence_threshold,
            },
        }

    except Exception as e:
        logger.error("verify_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/slash/verify")
async def slash_verify(request: Request) -> JSONResponse:
    """Slash command endpoint for integration with chat platforms.

    Accepts form-encoded data from slash commands.
    """
    try:
        # Parse form data
        form_data = await request.form()
        text_raw = form_data.get("text", "")
        user_id_raw = form_data.get("user_id", "unknown")
        channel_id_raw = form_data.get("channel_id", "unknown")
        text = text_raw if isinstance(text_raw, str) else ""
        user_id = user_id_raw if isinstance(user_id_raw, str) else "unknown"
        channel_id = channel_id_raw if isinstance(channel_id_raw, str) else "unknown"

        logger.info(
            "slash_command",
            user_id=user_id,
            channel_id=channel_id,
            text_length=len(text),
        )

        # Parse text as JSON if provided
        if text:
            import json
            try:
                data = json.loads(text)
                verify_request = VerifyRequest(**data)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "response_type": "ephemeral",
                        "text": "Invalid JSON in command text. Please provide valid JSON.",
                    },
                )
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        "response_type": "ephemeral",
                        "text": f"Invalid request: {str(e)}",
                    },
                )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "response_type": "ephemeral",
                    "text": "Please provide task data as JSON in the command text.",
                },
            )

        # Run verification
        result_data = await verify(verify_request)

        # Format response for slash command
        score = result_data["confidence_score"]
        passed = result_data["passed"]
        level = result_data["confidence_level"]

        emoji = "✅" if passed else "⚠️"
        status = "PASSED" if passed else "FAILED"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Verification {status}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence Score:*\n{score:.1f}/100",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Level:*\n{level.upper()}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Check Results:*",
                },
            },
        ]

        # Add check results
        for name, check in result_data["check_results"].items():
            status_emoji = "✓" if check["passed"] else "✗"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{name}*: {check['score']:.2f}",
                },
            })

        # Add recommendations if any
        if result_data["recommendations"]:
            recs = "\n".join(f"• {r}" for r in result_data["recommendations"][:3])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommendations:*\n{recs}",
                },
            })

        return JSONResponse(content={
            "response_type": "in_channel",
            "blocks": blocks,
        })

    except Exception as e:
        logger.error("slash_command_failed", error=str(e))
        return JSONResponse(
            status_code=500,
            content={
                "response_type": "ephemeral",
                "text": f"Verification failed: {str(e)}",
            },
        )


# Main entry point

def main() -> None:
    """Run the server."""
    import uvicorn

    settings = get_settings()
    configure_logging(settings)

    uvicorn.run(
        "agentliar.server:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
