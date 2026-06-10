"""
LLM Gateway — Main Application

Routes:
    GET  /health              → health check + usage summary
    POST /complete            → single LLM completion
    POST /complete/stream     → streaming LLM completion (SSE)
    POST /tokens/count        → count tokens in text
    POST /tokens/cost         → estimate cost for token counts
    GET  /usage               → full usage summary + per-model breakdown
    GET  /usage/recent        → recent request log
    DELETE /usage             → clear usage log
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from auth import verify_api_key
from models import (
    CompleteRequest, CompleteResponse,
    TokenCountRequest, TokenCountResponse,
    CostEstimateRequest, CostBreakdown,
    UsageSummaryResponse, HealthResponse,
)
from providers import get_provider, PROVIDERS
from tokens import count_tokens_exact, estimate_cost
from tracker import RequestTracker


# ------------------------------------------------------------------
# Shared state
# ------------------------------------------------------------------

tracker = RequestTracker(max_records=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"LLM Gateway started. Providers: {list(PROVIDERS.keys())}")
    yield


app = FastAPI(
    title="LLM Gateway",
    description=(
        "A unified gateway for LLM providers. "
        "Supports completions, streaming, token counting, and cost tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    summary = tracker.summary()
    return HealthResponse(
        status="ok",
        providers=list(PROVIDERS.keys()),
        total_requests=summary["total_requests"],
        total_cost_usd=summary["total_cost_usd"],
    )


# ------------------------------------------------------------------
# Complete
# ------------------------------------------------------------------

@app.post(
    "/complete",
    response_model=CompleteResponse,
    tags=["Completions"],
)
async def complete(
    body: CompleteRequest,
    _: str = Security(verify_api_key),
):
    """
    Send a conversation to an LLM and get a completion.

    Messages follow the standard chat format:
        [{"role": "user", "content": "..."}, ...]

    Supports an optional system prompt for model instructions.
    Tracks tokens and cost automatically.
    """
    try:
        provider = get_provider(body.provider)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    messages = [m.model_dump() for m in body.messages]

    try:
        result = await provider.complete(
            messages=messages,
            model=body.model,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            system=body.system,
        )
    except Exception as e:
        tracker.log_error(body.provider, body.model or "unknown", str(e))
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")

    record = tracker.log(result)

    return CompleteResponse(
        **result.to_dict(),
        request_id=record.request_id,
    )


@app.post(
    "/complete/stream",
    tags=["Completions"],
    response_class=StreamingResponse,
)
async def complete_stream(
    body: CompleteRequest,
    _: str = Security(verify_api_key),
):
    """
    Stream a completion using Server-Sent Events (SSE).

    Response is a stream of SSE events:
        data: {"token": "Hello"}
        data: {"token": " world"}
        data: [DONE]

    SSE (Server-Sent Events) is a standard for one-way streaming
    from server to client over HTTP. The client reads the stream
    incrementally — each token arrives as it's generated.

    Why streaming matters for UX:
    A 200-token response might take 3 seconds to generate.
    Without streaming: user waits 3s then sees everything at once.
    With streaming: user sees tokens appear word-by-word immediately.
    """
    try:
        provider = get_provider(body.provider)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    messages = [m.model_dump() for m in body.messages]

    async def event_generator():
        """
        Yields SSE-formatted strings.
        SSE format: "data: {json}\n\n"
        The double newline signals end of each event.
        """
        full_content = []
        try:
            async for token in provider.stream(
                messages=messages,
                model=body.model,
                max_tokens=body.max_tokens,
                temperature=body.temperature,
                system=body.system,
            ):
                full_content.append(token)
                event = json.dumps({"token": token})
                yield f"data: {event}\n\n"

            # Final event — signals stream is complete
            yield "data: [DONE]\n\n"

        except Exception as e:
            error_event = json.dumps({"error": str(e)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ------------------------------------------------------------------
# Token counting + cost estimation
# ------------------------------------------------------------------

@app.post(
    "/tokens/count",
    response_model=TokenCountResponse,
    tags=["Tokens"],
)
def count_tokens(
    body: TokenCountRequest,
    _: str = Security(verify_api_key),
):
    """Count tokens in text using tiktoken (or approximation if unavailable)."""
    count = count_tokens_exact(body.text, body.model)
    return TokenCountResponse(
        text_length=len(body.text),
        token_count=count,
        model=body.model,
    )


@app.post(
    "/tokens/cost",
    response_model=CostBreakdown,
    tags=["Tokens"],
)
def estimate_cost_endpoint(
    body: CostEstimateRequest,
    _: str = Security(verify_api_key),
):
    """Estimate cost for a given number of input and output tokens."""
    cost = estimate_cost(body.input_tokens, body.output_tokens, body.model)
    if "note" in cost:
        raise HTTPException(
            status_code=404,
            detail=cost["note"],
        )
    return CostBreakdown(**cost)


# ------------------------------------------------------------------
# Usage tracking
# ------------------------------------------------------------------

@app.get(
    "/usage",
    response_model=UsageSummaryResponse,
    tags=["Usage"],
)
def get_usage(_: str = Security(verify_api_key)):
    """Full usage summary: total tokens, cost, per-model breakdown."""
    return UsageSummaryResponse(**tracker.summary())


@app.get(
    "/usage/recent",
    tags=["Usage"],
)
def get_recent_usage(
    n: int = 20,
    _: str = Security(verify_api_key),
):
    """Return the n most recent requests."""
    return {"requests": tracker.recent(n)}


@app.delete(
    "/usage",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Usage"],
)
def clear_usage(_: str = Security(verify_api_key)):
    """Clear usage log and reset counters."""
    tracker.clear()
