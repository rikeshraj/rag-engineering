"""
Prompt Engineering Toolkit — Main Application

Routes:
    GET  /health                    → health check
    GET  /templates                 → list all templates
    GET  /templates/{name}          → get template details
    POST /render                    → render template (no LLM call)
    POST /run                       → render + send to LLM
    GET  /chains                    → list all chains
    POST /chains/{name}/run         → run a prompt chain
"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Query, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from library import get_template, list_templates, TEMPLATE_REGISTRY
from chains import CHAIN_REGISTRY
from models import (
    RenderRequest, RunRequest, RunChainRequest,
    RenderedPromptResponse, RunResponse, ChainRunResponse,
    TemplateInfo, HealthResponse,
)


# ------------------------------------------------------------------
# LLM call helper — uses providers from Project 10 if available,
# otherwise falls back to the built-in mock
# ------------------------------------------------------------------

async def call_llm(
    rendered,
    provider: str = "mock",
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> tuple[str, dict]:
    """
    Send a RenderedPrompt to an LLM. Returns (response_text, metadata).
    Tries to import from the LLM Gateway (Project 10) if available,
    falls back to a simple mock.
    """
    try:
        # Try using the providers module from Project 10
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "llm-gateway"))
        from providers import get_provider
        p = get_provider(provider)
        result = await p.complete(
            messages=rendered.messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=rendered.system,
        )
        return result.content, result.to_dict()
    except (ImportError, ModuleNotFoundError):
        pass

    # Built-in mock fallback
    import asyncio
    await asyncio.sleep(0.05)
    last = rendered.messages[-1]["content"]
    content = f"[Mock] Response to: {last[:80]}"
    meta = {
        "model": model or "mock-llm-v1",
        "provider": provider,
        "input_tokens": len(last) // 4,
        "output_tokens": len(content) // 4,
        "latency_ms": 50.0,
    }
    return content, meta


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Prompt Toolkit started. {len(TEMPLATE_REGISTRY)} templates, "
          f"{len(CHAIN_REGISTRY)} chains.")
    yield


app = FastAPI(
    title="Prompt Engineering Toolkit",
    description=(
        "A library of reusable prompt templates for RAG and LLM tasks. "
        "Supports rendering, LLM execution, and sequential prompt chains."
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
    techniques = list({t.technique for t in TEMPLATE_REGISTRY.values()})
    return HealthResponse(
        status="ok",
        total_templates=len(TEMPLATE_REGISTRY),
        total_chains=len(CHAIN_REGISTRY),
        techniques=sorted(techniques),
    )


# ------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------

@app.get("/templates", response_model=list[TemplateInfo], tags=["Templates"])
def get_templates(
    tag: str | None = Query(default=None, description="Filter by tag"),
    _: str = Security(verify_api_key),
):
    """List all available templates, optionally filtered by tag."""
    return list_templates(tag=tag)


@app.get("/templates/{name}", response_model=TemplateInfo, tags=["Templates"])
def get_template_detail(
    name: str,
    _: str = Security(verify_api_key),
):
    """Get full details for a specific template."""
    try:
        template = get_template(name)
        return template.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ------------------------------------------------------------------
# Render (no LLM call)
# ------------------------------------------------------------------

@app.post(
    "/render",
    response_model=RenderedPromptResponse,
    tags=["Templates"],
)
def render_template(
    body: RenderRequest,
    _: str = Security(verify_api_key),
):
    """
    Render a template with variables — returns the final prompt
    without calling any LLM. Useful for previewing prompts before use.
    """
    try:
        template = get_template(body.template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        rendered = template.render(**body.variables)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Render error: {e}")

    return RenderedPromptResponse(**rendered.to_dict())


# ------------------------------------------------------------------
# Run (render + LLM call)
# ------------------------------------------------------------------

@app.post(
    "/run",
    response_model=RunResponse,
    tags=["Templates"],
)
async def run_template(
    body: RunRequest,
    _: str = Security(verify_api_key),
):
    """
    Render a template and send it to an LLM.
    Returns both the rendered prompt and the model's response.
    """
    try:
        template = get_template(body.template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        rendered = template.render(**body.variables)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    response_text, meta = await call_llm(
        rendered,
        provider=body.provider,
        model=body.model,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    return RunResponse(
        template_name=template.name,
        technique=template.technique,
        rendered_user=rendered.user_content(),
        llm_response=response_text,
        provider=meta.get("provider", body.provider),
        model=meta.get("model", "unknown"),
        input_tokens=meta.get("input_tokens", 0),
        output_tokens=meta.get("output_tokens", 0),
        latency_ms=meta.get("latency_ms", 0.0),
    )


# ------------------------------------------------------------------
# Chains
# ------------------------------------------------------------------

@app.get("/chains", tags=["Chains"])
def list_chains(_: str = Security(verify_api_key)):
    """List all available prompt chains."""
    return [
        {
            "name":        name,
            "description": chain.description,
            "steps":       len(chain.steps),
            "step_names":  [s.template.name for s in chain.steps],
        }
        for name, chain in CHAIN_REGISTRY.items()
    ]


@app.post(
    "/chains/{chain_name}/run",
    response_model=ChainRunResponse,
    tags=["Chains"],
)
async def run_chain(
    chain_name: str,
    body: RunChainRequest,
    _: str = Security(verify_api_key),
):
    """
    Run a multi-step prompt chain.
    Each step's output feeds into the next step's inputs.
    """
    if chain_name not in CHAIN_REGISTRY:
        available = ", ".join(CHAIN_REGISTRY.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Chain '{chain_name}' not found. Available: {available}",
        )

    chain = CHAIN_REGISTRY[chain_name]

    async def llm_fn(rendered):
        text, _ = await call_llm(
            rendered,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
        return text

    try:
        result = await chain.run(llm_fn=llm_fn, **body.variables)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ChainRunResponse(**result.to_dict())
