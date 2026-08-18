"""
Models — Pydantic request/response models for the Prompt Toolkit API.
"""

from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    """Body for POST /render — render a template with variables."""
    template: str = Field(description="Template name from the library")
    variables: dict = Field(
        default_factory=dict,
        description="Variable values to substitute into the template",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "template": "rag_qa",
                "variables": {
                    "context": "RAG stands for Retrieval-Augmented Generation...",
                    "question": "What does RAG stand for?",
                },
            }
        }
    }


class RunRequest(BaseModel):
    """Body for POST /run — render + send to LLM."""
    template: str
    variables: dict = Field(default_factory=dict)
    provider: str = Field(default="mock")
    model: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)


class RunChainRequest(BaseModel):
    """Body for POST /chains/{name}/run"""
    variables: dict = Field(
        default_factory=dict,
        description="Initial inputs for the chain",
    )
    provider: str = Field(default="mock")
    model: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)


class RenderedPromptResponse(BaseModel):
    template_name: str
    template_version: str
    system: str | None
    messages: list[dict]
    variables_used: dict
    technique: str


class RunResponse(BaseModel):
    template_name: str
    technique: str
    rendered_user: str
    llm_response: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class ChainRunResponse(BaseModel):
    chain_name: str
    steps_executed: int
    final_output: str
    step_outputs: list[dict]


class TemplateInfo(BaseModel):
    name: str
    version: str
    description: str
    technique: str
    tags: list[str]
    variables: list[dict]
    system_preview: str | None
    user_preview: str


class HealthResponse(BaseModel):
    status: str
    total_templates: int
    total_chains: int
    techniques: list[str]
