"""A DeepEval judge backed by the same Groq models Atlas runs on.

DeepEval's metrics (G-Eval, Faithfulness, …) need an LLM judge; by default that is an
OpenAI model. Atlas runs on Groq's free tier, so the judge is a ``DeepEvalBaseLLM``
over ``atlas.core.agents.base.chat`` — which also gives every judge call the LLM
bulkhead, retries and Langfuse tracing the product's own calls get.

When DeepEval passes a pydantic ``schema`` it expects an instance back. Free-tier
models don't always return the exact shape, so the judge is defensive: it sends the
FULL schema (including ``$defs`` — truncating it once hid the verdict item shape), gives
long claim lists room to finish, accepts a bare array where the schema has a single
list field, salvages a reply cut off mid-array, and retries once with the validation
error before giving up.

The judge runs on the SMALL model by default (``ATLAS_EVAL_JUDGE_MODEL`` overrides):
Groq rate-limits per model, and a judge sharing the agent's daily token budget once
starved the very run it was grading.
"""

from __future__ import annotations

import asyncio
import json
import os

from deepeval.models import DeepEvalBaseLLM
from pydantic import ValidationError

from atlas.config import get_settings
from atlas.core.agents.base import chat, extract_json, salvage_json_array

_ATTEMPTS = 2


def _single_list_field(schema) -> str | None:
    """Name of the only field when the schema is ``{field: [...]}`` (e.g. Verdicts)."""
    props = schema.model_json_schema().get("properties", {})
    if len(props) == 1:
        name, spec = next(iter(props.items()))
        if spec.get("type") == "array":
            return name
    return None


def _parse(text: str, schema):
    data = extract_json(text, default=None)
    field = _single_list_field(schema)
    if data is None and field:
        data = salvage_json_array(text)  # reply cut off mid-array: keep complete items
    if isinstance(data, list) and field:
        data = {field: data}
    return schema.model_validate(data if isinstance(data, dict) else {})


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, model: str | None = None) -> None:
        super().__init__(model or os.environ.get("ATLAS_EVAL_JUDGE_MODEL")
                         or get_settings().summarizer_model)

    def load_model(self):
        return self

    def get_model_name(self) -> str:
        return f"groq/{self.name}"

    def supports_json_mode(self) -> bool:
        return False

    def generate(self, prompt: str, schema=None, **_: object):
        if schema is None:
            return chat(prompt, temperature=0.0, run_name="eval.deepeval", max_tokens=4096,
                        reasoning_effort="low", model=self.name)
        spec = json.dumps(schema.model_json_schema())
        ask = (f"{prompt}\n\nReturn ONLY one JSON object (no prose, no code fence) that "
               f"validates against this JSON schema:\n{spec}")
        error: Exception | None = None
        for _attempt in range(_ATTEMPTS):
            text = chat(ask, temperature=0.0, run_name="eval.deepeval", max_tokens=6144,
                        reasoning_effort="low", model=self.name)
            try:
                return _parse(text, schema)
            except ValidationError as exc:
                error = exc
                ask = (f"{ask}\n\nYour previous reply did not validate ({str(exc)[:300]}). "
                       "Reply again with ONLY the JSON object.")
        raise error  # type: ignore[misc]

    async def a_generate(self, prompt: str, schema=None, **kwargs: object):
        return await asyncio.to_thread(self.generate, prompt, schema)
