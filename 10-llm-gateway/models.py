"""
Models — Pydantic request/response models for the LLM Gateway.
"""

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Shared
# ------------------------------------------------------------------

class Message(BaseModel):
    """A single message in a conversation."""
    role: str = Field(
        description="Message role: 'user' or 'assistant'",
        pattern="^(user|assistant)$",
    )
    content: str = Field(min_length=1)


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class CompleteRequest(BaseModel):
    """Body for POST /complete"""
    messages: list[Message] = Field(
        min_length=1,
        description="Conversation history. Last message is the current turn.",
    )
    provider: str = Field(
        default="mock",
        description="LLM provider: 'anthropic' or 'mock'",
    )
    model: str | None = Field(
        default=None,
        description="Model to use. Defaults to provider's default model.",
    )
    system: str | None = Field(
        default=None,
        max_length=10000,
        description="System prompt (instructions for the model's behavior)",
    )
    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=8192,
        description="Maximum tokens in the response",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Sampling temperature. 0=deterministic, 1=creative",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "user", "content": "What is RAG in AI?"}
                ],
                "provider": "mock",
                "system": "You are a helpful AI assistant. Be concise.",
                "max_tokens": 512,
                "temperature": 0.7,
            }
        }
    }


class TokenCountRequest(BaseModel):
    """Body for POST /tokens/count"""
    text: str = Field(min_length=1)
    model: str = Field(default="cl100k_base")


class CostEstimateRequest(BaseModel):
    """Body for POST /tokens/cost"""
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------

class CostBreakdown(BaseModel):
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str = "USD"


class CompleteResponse(BaseModel):
    """Response for POST /complete"""
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost: dict
    cached: bool
    stop_reason: str
    request_id: int


class TokenCountResponse(BaseModel):
    text_length: int
    token_count: int
    model: str


class UsageSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_errors: int
    avg_latency_ms: float
    by_model: dict


class HealthResponse(BaseModel):
    status: str
    providers: list[str]
    total_requests: int
    total_cost_usd: float
