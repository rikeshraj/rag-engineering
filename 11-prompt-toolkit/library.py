"""
Library

Pre-built prompt templates for common RAG and LLM tasks.

Templates included:
    rag_qa              — standard RAG question answering
    rag_qa_cot          — RAG + chain-of-thought reasoning
    rag_qa_few_shot     — RAG + few-shot examples
    summarize           — document summarization
    summarize_bullets   — bullet-point summary
    extract_json        — structured data extraction to JSON
    classify            — text classification with labels
    query_rewrite       — rewrite a query for better retrieval
    answer_grading      — grade an answer for faithfulness
    hypothetical_doc    — HyDE: generate a hypothetical answer for retrieval

Techniques demonstrated:
    standard        — direct question + context
    chain-of-thought — "think step by step" reasoning
    few-shot        — examples embedded in prompt
    extraction      — structured output (JSON)
    classification  — assign label from fixed set
    hyde            — Hypothetical Document Embeddings
"""

from templates import PromptTemplate, TemplateVariable


# ------------------------------------------------------------------
# RAG Question Answering
# ------------------------------------------------------------------

RAG_QA = PromptTemplate(
    name="rag_qa",
    version="1.0.0",
    description="Standard RAG question answering using retrieved context.",
    technique="standard",
    tags=["rag", "qa", "retrieval"],
    system="""You are a helpful assistant that answers questions using only \
the provided context. If the context does not contain enough information \
to answer the question, say so clearly. Do not make up information.""",
    user="""\
Context:
{{ context }}

Question: {{ question }}

Answer based only on the context above:""",
    variables=[
        TemplateVariable(
            name="context",
            description="Retrieved document chunks, concatenated",
            required=True,
            example="RAG stands for Retrieval-Augmented Generation...",
        ),
        TemplateVariable(
            name="question",
            description="The user's question",
            required=True,
            example="What does RAG stand for?",
        ),
    ],
)


# ------------------------------------------------------------------
# RAG + Chain-of-Thought
# ------------------------------------------------------------------

RAG_QA_COT = PromptTemplate(
    name="rag_qa_cot",
    version="1.0.0",
    description=(
        "RAG question answering with chain-of-thought reasoning. "
        "The model thinks step by step before giving the final answer."
    ),
    technique="chain-of-thought",
    tags=["rag", "qa", "chain-of-thought", "reasoning"],
    system="""You are a careful, analytical assistant. When answering questions, \
you first reason through the evidence step by step, then give your final answer. \
Use only the provided context — do not use outside knowledge.""",
    user="""\
Context:
{{ context }}

Question: {{ question }}

Let's think step by step:
1. What does the context tell us about this question?
2. What is directly stated vs what is implied?
3. What is the most accurate answer based on the context?

Reasoning:
[think through the above steps]

Final Answer:""",
    variables=[
        TemplateVariable(
            name="context",
            description="Retrieved document chunks",
            required=True,
        ),
        TemplateVariable(
            name="question",
            description="The user's question",
            required=True,
        ),
    ],
)


# ------------------------------------------------------------------
# RAG + Few-Shot
# ------------------------------------------------------------------

RAG_QA_FEW_SHOT = PromptTemplate(
    name="rag_qa_few_shot",
    version="1.0.0",
    description=(
        "RAG QA with few-shot examples showing the expected answer format. "
        "Examples guide the model on length, style, and citation behavior."
    ),
    technique="few-shot",
    tags=["rag", "qa", "few-shot", "examples"],
    system="""You are a precise assistant. Answer questions using only the \
provided context. Follow the format shown in the examples.""",
    user="""\
Here are examples of good answers:

{% for ex in examples %}
Context: {{ ex.context }}
Question: {{ ex.question }}
Answer: {{ ex.answer }}

{% endfor %}
---
Now answer this:

Context:
{{ context }}

Question: {{ question }}

Answer:""",
    variables=[
        TemplateVariable(
            name="context",
            description="Retrieved document chunks",
            required=True,
        ),
        TemplateVariable(
            name="question",
            description="The user's question",
            required=True,
        ),
        TemplateVariable(
            name="examples",
            description="Few-shot examples: list of {context, question, answer}",
            required=False,
            default=[],
        ),
    ],
    examples=[
        {
            "context": "The Eiffel Tower was built between 1887 and 1889.",
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was built between 1887 and 1889.",
        },
        {
            "context": "Python was created by Guido van Rossum and first released in 1991.",
            "question": "Who created Python?",
            "answer": "Python was created by Guido van Rossum.",
        },
    ],
)


# ------------------------------------------------------------------
# Summarization
# ------------------------------------------------------------------

SUMMARIZE = PromptTemplate(
    name="summarize",
    version="1.0.0",
    description="Summarize a document into a concise paragraph.",
    technique="standard",
    tags=["summarization", "compression"],
    system="You are an expert at distilling complex documents into clear, \
accurate summaries. Preserve key facts and main ideas.",
    user="""\
Summarize the following document in {{ max_sentences }} sentences or fewer.
Focus on the most important information.

Document:
{{ document }}

Summary:""",
    variables=[
        TemplateVariable(
            name="document",
            description="The text to summarize",
            required=True,
        ),
        TemplateVariable(
            name="max_sentences",
            description="Maximum sentences in the summary",
            required=False,
            default=3,
            example=3,
        ),
    ],
)


SUMMARIZE_BULLETS = PromptTemplate(
    name="summarize_bullets",
    version="1.0.0",
    description="Summarize a document as bullet points.",
    technique="standard",
    tags=["summarization", "bullets", "list"],
    system="You are an expert summarizer. Extract the key points from \
documents as a clear, scannable bullet list.",
    user="""\
Extract the {{ num_bullets }} most important points from this document as bullet points.
Each bullet should be one concise sentence.

Document:
{{ document }}

Key points:
•""",
    variables=[
        TemplateVariable(
            name="document",
            description="The text to summarize",
            required=True,
        ),
        TemplateVariable(
            name="num_bullets",
            description="Number of bullet points to generate",
            required=False,
            default=5,
            example=5,
        ),
    ],
)


# ------------------------------------------------------------------
# Structured Extraction
# ------------------------------------------------------------------

EXTRACT_JSON = PromptTemplate(
    name="extract_json",
    version="1.0.0",
    description=(
        "Extract structured information from text and return as JSON. "
        "Provide a JSON schema describing what to extract."
    ),
    technique="extraction",
    tags=["extraction", "json", "structured-output"],
    system="""You are a precise data extraction assistant. Extract information \
from text and return ONLY valid JSON matching the provided schema. \
Do not include any explanation or markdown — output raw JSON only.""",
    user="""\
Extract the following information from the text below.

Schema:
{{ schema }}

Text:
{{ text }}

Return ONLY the JSON object, no other text:""",
    variables=[
        TemplateVariable(
            name="text",
            description="Text to extract information from",
            required=True,
        ),
        TemplateVariable(
            name="schema",
            description="JSON schema describing fields to extract",
            required=True,
            example='{"name": "string", "email": "string", "company": "string"}',
        ),
    ],
)


# ------------------------------------------------------------------
# Classification
# ------------------------------------------------------------------

CLASSIFY = PromptTemplate(
    name="classify",
    version="1.0.0",
    description="Classify text into one of the provided labels.",
    technique="classification",
    tags=["classification", "labeling"],
    system="""You are a precise classifier. Assign exactly one label from \
the provided list. Output ONLY the label — no explanation.""",
    user="""\
Classify the following text into exactly one of these labels:
{{ labels | join(", ") }}

{% if examples %}
Examples:
{% for ex in examples %}
Text: {{ ex.text }}
Label: {{ ex.label }}

{% endfor %}
{% endif %}
Text to classify:
{{ text }}

Label:""",
    variables=[
        TemplateVariable(
            name="text",
            description="Text to classify",
            required=True,
        ),
        TemplateVariable(
            name="labels",
            description="List of valid labels",
            required=True,
            example=["positive", "negative", "neutral"],
        ),
        TemplateVariable(
            name="examples",
            description="Optional few-shot examples [{text, label}]",
            required=False,
            default=[],
        ),
    ],
)


# ------------------------------------------------------------------
# Query Rewriting
# ------------------------------------------------------------------

QUERY_REWRITE = PromptTemplate(
    name="query_rewrite",
    version="1.0.0",
    description=(
        "Rewrite a user query to improve retrieval quality. "
        "Expands abbreviations, adds context, clarifies ambiguity."
    ),
    technique="query-expansion",
    tags=["retrieval", "query", "rewriting", "expansion"],
    system="""You are a search query optimizer. Rewrite queries to be more \
specific and retrieval-friendly. Expand abbreviations, add relevant \
keywords, and remove ambiguity. Return ONLY the rewritten query.""",
    user="""\
Original query: {{ query }}

{% if context %}
Conversation context: {{ context }}
{% endif %}

Rewrite this query to improve document retrieval. Make it more specific \
and include relevant keywords. Output ONLY the rewritten query:""",
    variables=[
        TemplateVariable(
            name="query",
            description="The original user query",
            required=True,
            example="how does rag work",
        ),
        TemplateVariable(
            name="context",
            description="Optional conversation context for disambiguation",
            required=False,
            default=None,
        ),
    ],
)


# ------------------------------------------------------------------
# Answer Grading (for RAG evaluation)
# ------------------------------------------------------------------

ANSWER_GRADING = PromptTemplate(
    name="answer_grading",
    version="1.0.0",
    description=(
        "Grade an LLM answer for faithfulness to source context. "
        "Used in RAG evaluation pipelines."
    ),
    technique="evaluation",
    tags=["evaluation", "grading", "faithfulness", "rag"],
    system="""You are an expert evaluator assessing LLM answer quality. \
Be strict and objective.""",
    user="""\
You are evaluating whether an answer is faithful to the source context.

Context (ground truth):
{{ context }}

Question: {{ question }}

Answer to evaluate:
{{ answer }}

Evaluate on these criteria:
1. FAITHFULNESS: Is every claim in the answer supported by the context?
2. COMPLETENESS: Does the answer address the question fully?
3. HALLUCINATION: Does the answer include information not in the context?

Respond with a JSON object:
{
  "faithfulness_score": <0-10>,
  "completeness_score": <0-10>,
  "hallucination_detected": <true/false>,
  "issues": ["list of specific problems, or empty"],
  "verdict": "<pass|fail>",
  "explanation": "<one sentence summary>"
}""",
    variables=[
        TemplateVariable(
            name="context",
            description="The retrieved context used to generate the answer",
            required=True,
        ),
        TemplateVariable(
            name="question",
            description="The original question",
            required=True,
        ),
        TemplateVariable(
            name="answer",
            description="The LLM answer to evaluate",
            required=True,
        ),
    ],
)


# ------------------------------------------------------------------
# HyDE — Hypothetical Document Embeddings
# ------------------------------------------------------------------

HYPOTHETICAL_DOC = PromptTemplate(
    name="hypothetical_doc",
    version="1.0.0",
    description=(
        "Generate a hypothetical document that would answer a query. "
        "Used in HyDE retrieval: embed the hypothetical doc instead of "
        "the query, then search for real documents similar to the hypothetical."
    ),
    technique="hyde",
    tags=["retrieval", "hyde", "hypothetical", "embedding"],
    system="""You are a document generator. Write realistic-sounding document \
excerpts that would contain the answer to the given question. \
Write as if it were an actual document, not a direct answer.""",
    user="""\
Write a short document excerpt (2-3 sentences) that would contain the \
answer to this question. Write it as a factual passage, not as a \
direct answer to the question.

Question: {{ question }}

Document excerpt:""",
    variables=[
        TemplateVariable(
            name="question",
            description="The question to generate a hypothetical document for",
            required=True,
            example="What are the main components of a RAG system?",
        ),
    ],
)


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

TEMPLATE_REGISTRY: dict[str, PromptTemplate] = {
    t.name: t for t in [
        RAG_QA,
        RAG_QA_COT,
        RAG_QA_FEW_SHOT,
        SUMMARIZE,
        SUMMARIZE_BULLETS,
        EXTRACT_JSON,
        CLASSIFY,
        QUERY_REWRITE,
        ANSWER_GRADING,
        HYPOTHETICAL_DOC,
    ]
}


def get_template(name: str) -> PromptTemplate:
    """Get a template from the registry by name."""
    if name not in TEMPLATE_REGISTRY:
        available = ", ".join(TEMPLATE_REGISTRY.keys())
        raise ValueError(
            f"Template '{name}' not found. Available: {available}"
        )
    return TEMPLATE_REGISTRY[name]


def list_templates(tag: str | None = None) -> list[dict]:
    """List all templates, optionally filtered by tag."""
    templates = list(TEMPLATE_REGISTRY.values())
    if tag:
        templates = [t for t in templates if tag in t.tags]
    return [t.to_dict() for t in templates]
