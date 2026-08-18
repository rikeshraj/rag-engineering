"""
Chains

Sequential prompt chains where the output of one step
feeds into the next.

Example chain: RAG with query rewriting
    Step 1: rewrite query    → better_query
    Step 2: rag_qa           → final_answer  (uses better_query)

Why chains?
Single prompts have limits. A multi-step chain can:
- Rewrite a vague query before retrieval (better recall)
- Summarize long context before answering (fits context window)
- Grade its own answer and retry if quality is low
- Break complex tasks into simpler subtasks

This is the foundation of agentic behavior (Project 16).
"""

from dataclasses import dataclass, field
from typing import Callable

from templates import PromptTemplate, RenderedPrompt


# ------------------------------------------------------------------
# Chain step
# ------------------------------------------------------------------

@dataclass
class ChainStep:
    """
    A single step in a chain.

    template    : the PromptTemplate to render
    input_map   : how to map chain state → template variables
                  key = template variable name
                  value = key in chain state dict OR a callable

    Example:
        ChainStep(
            template=RAG_QA,
            input_map={
                "question": "rewritten_query",  # from previous step output
                "context":  "context",           # from chain inputs
            }
        )
    """
    template: PromptTemplate
    input_map: dict[str, str | Callable]
    output_key: str = "output"   # key to store this step's output in state

    def resolve_inputs(self, state: dict) -> dict:
        """
        Build the variable dict for this step from chain state.
        Supports direct key lookup or callable transformation.
        """
        resolved = {}
        for var_name, source in self.input_map.items():
            if callable(source):
                resolved[var_name] = source(state)
            elif source in state:
                resolved[var_name] = state[source]
            else:
                raise KeyError(
                    f"Chain step '{self.template.name}' needs '{source}' "
                    f"in chain state, but it's not there. "
                    f"Current state keys: {list(state.keys())}"
                )
        return resolved


# ------------------------------------------------------------------
# Chain result
# ------------------------------------------------------------------

@dataclass
class ChainResult:
    """Result of running a full chain."""
    chain_name: str
    steps_executed: int
    final_output: str
    step_outputs: list[dict] = field(default_factory=list)
    state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chain_name":     self.chain_name,
            "steps_executed": self.steps_executed,
            "final_output":   self.final_output,
            "step_outputs":   self.step_outputs,
        }


# ------------------------------------------------------------------
# Chain
# ------------------------------------------------------------------

class PromptChain:
    """
    A sequential chain of prompt steps.

    Each step renders a template, sends it to an LLM,
    and stores the output in a shared state dict.
    Subsequent steps can read from that state.

    Usage:
        chain = PromptChain(
            name="rag_with_rewrite",
            steps=[
                ChainStep(
                    template=QUERY_REWRITE,
                    input_map={"query": "question"},
                    output_key="rewritten_query",
                ),
                ChainStep(
                    template=RAG_QA,
                    input_map={
                        "question": "rewritten_query",
                        "context":  "context",
                    },
                    output_key="answer",
                ),
            ]
        )
        result = await chain.run(
            llm_fn=my_llm_function,
            question="what is rag?",
            context="RAG stands for...",
        )
    """

    def __init__(self, name: str, steps: list[ChainStep], description: str = ""):
        self.name = name
        self.steps = steps
        self.description = description

    async def run(
        self,
        llm_fn: Callable,
        **initial_inputs,
    ) -> ChainResult:
        """
        Execute the chain.

        llm_fn: async function that takes a RenderedPrompt
                and returns the LLM's response string.
                Signature: async def llm_fn(prompt: RenderedPrompt) -> str

        initial_inputs: the starting data (question, context, etc.)
        """
        # State accumulates inputs + outputs as chain progresses
        state: dict = dict(initial_inputs)
        step_outputs = []

        for i, step in enumerate(self.steps):
            # 1. Resolve inputs for this step from current state
            try:
                inputs = step.resolve_inputs(state)
            except KeyError as e:
                raise ValueError(f"Chain '{self.name}' step {i+1} failed: {e}")

            # 2. Render the template
            rendered = step.template.render(**inputs)

            # 3. Call the LLM
            output = await llm_fn(rendered)

            # 4. Store output in state
            state[step.output_key] = output
            step_outputs.append({
                "step":          i + 1,
                "template":      step.template.name,
                "output_key":    step.output_key,
                "output_preview": output[:200] + "..." if len(output) > 200 else output,
            })

        # Final output is the last step's output
        last_output_key = self.steps[-1].output_key
        final_output = state.get(last_output_key, "")

        return ChainResult(
            chain_name=self.name,
            steps_executed=len(self.steps),
            final_output=final_output,
            step_outputs=step_outputs,
            state=state,
        )


# ------------------------------------------------------------------
# Pre-built chains
# ------------------------------------------------------------------

def build_rag_with_rewrite_chain() -> PromptChain:
    """
    Two-step chain:
    1. Rewrite the query to improve retrieval
    2. Answer using RAG QA template

    The rewritten query is used for retrieval (done externally),
    and the original context is used for answering.
    """
    from library import QUERY_REWRITE, RAG_QA
    return PromptChain(
        name="rag_with_rewrite",
        description="Rewrites query first, then answers using RAG",
        steps=[
            ChainStep(
                template=QUERY_REWRITE,
                input_map={"query": "question"},
                output_key="rewritten_query",
            ),
            ChainStep(
                template=RAG_QA,
                input_map={
                    "question": "rewritten_query",
                    "context":  "context",
                },
                output_key="answer",
            ),
        ],
    )


def build_summarize_then_answer_chain() -> PromptChain:
    """
    Two-step chain for long documents:
    1. Summarize the context to fit the window
    2. Answer the question using the summary
    """
    from library import SUMMARIZE, RAG_QA
    return PromptChain(
        name="summarize_then_answer",
        description="Summarizes long context before answering",
        steps=[
            ChainStep(
                template=SUMMARIZE,
                input_map={
                    "document":      "context",
                    "max_sentences": lambda state: state.get("max_sentences", 3),
                },
                output_key="summary",
            ),
            ChainStep(
                template=RAG_QA,
                input_map={
                    "question": "question",
                    "context":  "summary",
                },
                output_key="answer",
            ),
        ],
    )


CHAIN_REGISTRY: dict[str, PromptChain] = {
    "rag_with_rewrite":      build_rag_with_rewrite_chain(),
    "summarize_then_answer": build_summarize_then_answer_chain(),
}
