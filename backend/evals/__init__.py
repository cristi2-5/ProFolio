"""Agent evals — LLM-as-judge + deterministic checks.

Sibling of ``backend/tests/`` (not nested) to keep coverage thresholds,
autouse fixtures, and test collection cleanly separated.

Phase 1 ships only the deterministic layer. DeepEval + Promptfoo layers
land in Phase 3 + Phase 4.
"""
