"""
Templates

Core prompt template system built on Jinja2.

Why Jinja2 for prompts?
- Variables: {{ question }}, {{ context }}
- Conditionals: {% if examples %}...{% endif %}
- Loops: {% for ex in examples %}...{% endfor %}
- Filters: {{ text | upper }}, {{ list | join(", ") }}
- Inheritance: extend a base template, override blocks

This is far more powerful than f-strings — you can build
complex prompts with conditionals and loops while keeping
the template readable and editable without touching Python code.

Key concepts demonstrated:
- Few-shot prompting: include examples in the prompt
- Chain-of-thought: "think step by step" instructions
- Role separation: system vs user messages
- Template versioning: track which version produced a result
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class TemplateVariable:
    """Metadata for a single template variable."""
    name: str
    description: str
    required: bool = True
    default: Any = None
    example: Any = None


@dataclass
class RenderedPrompt:
    """
    The output of rendering a template.
    Contains the final messages list ready to send to an LLM.
    """
    template_name: str
    template_version: str
    system: str | None
    messages: list[dict]        # [{"role": "user", "content": "..."}]
    variables_used: dict        # the values that were substituted
    technique: str              # few-shot, chain-of-thought, rag, etc.

    def to_dict(self) -> dict:
        return {
            "template_name":    self.template_name,
            "template_version": self.template_version,
            "system":           self.system,
            "messages":         self.messages,
            "variables_used":   self.variables_used,
            "technique":        self.technique,
        }

    def user_content(self) -> str:
        """Return the last user message content."""
        for msg in reversed(self.messages):
            if msg["role"] == "user":
                return msg["content"]
        return ""


# ------------------------------------------------------------------
# Template
# ------------------------------------------------------------------

class PromptTemplate:
    """
    A reusable, versioned prompt template.

    Templates are Jinja2 strings with named variables.
    They render to a RenderedPrompt with system + messages.

    Parameters:
        name        : unique identifier (e.g. "rag_qa")
        version     : semantic version (e.g. "1.0.0")
        description : what this template is for
        system      : optional Jinja2 string for the system prompt
        user        : Jinja2 string for the user message
        variables   : list of TemplateVariable definitions
        technique   : prompting technique used
        tags        : searchable labels
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        user: str,
        system: str | None = None,
        variables: list[TemplateVariable] | None = None,
        technique: str = "standard",
        tags: list[str] | None = None,
        examples: list[dict] | None = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.system = system
        self.user = user
        self.variables = variables or []
        self.technique = technique
        self.tags = tags or []
        self.examples = examples or []  # few-shot examples

        self._jinja_env = self._build_env()

    def _build_env(self):
        """
        Build a Jinja2 environment with safe settings.

        undefined=StrictUndefined raises an error if a variable
        is used in the template but not provided — prevents silent
        failures where missing variables render as empty strings.
        """
        try:
            from jinja2 import Environment, StrictUndefined
            return Environment(
                undefined=StrictUndefined,
                trim_blocks=True,     # remove newline after block tags
                lstrip_blocks=True,   # remove leading whitespace before block tags
            )
        except ImportError:
            return None  # fall back to simple string formatting

    def _render_jinja(self, template_str: str, variables: dict) -> str:
        """Render a Jinja2 template string with variables."""
        if self._jinja_env is None:
            # Fallback: simple {{ var }} replacement without Jinja2
            result = template_str
            for key, value in variables.items():
                result = result.replace("{{ " + key + " }}", str(value))
                result = result.replace("{{" + key + "}}", str(value))
            return result

        template = self._jinja_env.from_string(template_str)
        return template.render(**variables)

    def validate_variables(self, provided: dict) -> list[str]:
        """
        Check that all required variables are provided.
        Returns list of missing variable names (empty if all good).
        """
        missing = []
        for var in self.variables:
            if var.required and var.name not in provided:
                if var.default is None:
                    missing.append(var.name)
        return missing

    def render(self, **kwargs) -> RenderedPrompt:
        """
        Render the template with provided variable values.

        Raises ValueError if required variables are missing.
        All optional variables are included with their defaults
        so Jinja2 can reference them in conditionals without error.
        """
        # Start with defaults for ALL variables (required and optional)
        # Use a sentinel to distinguish "no default" from "default is None"
        _MISSING = object()
        variables = {}
        for var in self.variables:
            default = var.default if var.default is not None else (
                None if not var.required else _MISSING
            )
            if default is not _MISSING:
                variables[var.name] = var.default  # includes None defaults

        # Override with any provided values
        variables.update(kwargs)

        # Check required variables are present
        missing = []
        for var in self.variables:
            if var.required and var.name not in variables:
                missing.append(var.name)

        if missing:
            raise ValueError(
                f"Template '{self.name}' is missing required variables: "
                f"{', '.join(missing)}"
            )

        # If the examples variable is empty/not provided, use built-in examples
        if self.examples and not variables.get("examples"):
            variables["examples"] = self.examples

        # Render system prompt
        rendered_system = None
        if self.system:
            rendered_system = self._render_jinja(self.system, variables)

        # Render user message
        rendered_user = self._render_jinja(self.user, variables)

        messages = [{"role": "user", "content": rendered_user}]

        return RenderedPrompt(
            template_name=self.name,
            template_version=self.version,
            system=rendered_system,
            messages=messages,
            variables_used=variables,
            technique=self.technique,
        )

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "version":     self.version,
            "description": self.description,
            "technique":   self.technique,
            "tags":        self.tags,
            "variables": [
                {
                    "name":        v.name,
                    "description": v.description,
                    "required":    v.required,
                    "default":     v.default,
                    "example":     v.example,
                }
                for v in self.variables
            ],
            "system_preview": (self.system or "")[:100] + "..."
                              if self.system and len(self.system) > 100
                              else self.system,
            "user_preview":  self.user[:100] + "..."
                             if len(self.user) > 100
                             else self.user,
        }
