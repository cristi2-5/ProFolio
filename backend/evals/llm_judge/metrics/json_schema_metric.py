"""``JSONSchemaMetric`` — deterministic Pydantic round-trip metric.

DeepEval metrics are typically LLM-judge based, but the framework also
accepts pure-Python ``BaseMetric`` subclasses. Schema conformance is
the kind of thing we want a binary 0/1 verdict on, with zero quota
spend — perfect fit.

Pattern: instantiate with a Pydantic model class; metric passes when
``model.model_validate(json.loads(actual_output))`` succeeds.

Used in Phase 3 eval files to gate the LLM-judge metrics. If the
output isn't even valid JSON, there's no point asking the judge.
"""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel, ValidationError


class JSONSchemaMetric(BaseMetric):
    """Pass if ``actual_output`` round-trips through ``schema``.

    Args:
        schema: Pydantic ``BaseModel`` subclass to validate against.
        threshold: 1.0 (binary metric — always 1.0 or 0.0).
        name_suffix: appended to ``name`` for disambiguation when the
            same agent has multiple JSON outputs.
    """

    def __init__(
        self,
        schema: type[BaseModel],
        threshold: float = 1.0,
        name_suffix: str = "",
    ) -> None:
        self.schema = schema
        self.threshold = threshold
        self.name = f"JSONSchema[{schema.__name__}{name_suffix}]"
        # DeepEval expects these attributes after measure() runs.
        self.score: float = 0.0
        self.reason: str = ""
        self.success: bool = False
        # ``async_mode`` controls whether ``a_measure`` is required —
        # we expose both since DeepEval picks based on event loop.
        self.async_mode = True
        # Strict mode means the threshold must match exactly; we accept
        # the same value here so the metric is comparable to LLM-judge
        # metrics in the same suite.
        self.strict_mode = False
        # Evaluation cost — zero, this is deterministic.
        self.evaluation_cost = 0.0

    # ------------------------------------------------------------------
    # DeepEval BaseMetric hooks
    # ------------------------------------------------------------------

    def measure(self, test_case: LLMTestCase) -> float:
        raw = test_case.actual_output or ""
        try:
            parsed: Any = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError) as exc:
            self.score = 0.0
            self.reason = f"actual_output is not parseable JSON: {exc}"
            self.success = False
            return self.score

        try:
            self.schema.model_validate(parsed)
        except ValidationError as exc:
            self.score = 0.0
            # Surface only the first error — full validation reports
            # can be huge.
            first = (exc.errors() or [{"msg": str(exc)}])[0]
            loc = ".".join(str(p) for p in first.get("loc", []))
            self.reason = f"schema validation failed at '{loc}': {first.get('msg', '?')}"
            self.success = False
            return self.score

        self.score = 1.0
        self.reason = f"actual_output validates against {self.schema.__name__}"
        self.success = True
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        # No I/O happens here — async hook just delegates to sync.
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:  # noqa: D401 — DeepEval reads this attr for reports
        return self.name
