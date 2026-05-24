# Agent Evals

LLM evaluation suite for the 3 semantic agents in ProFolio
(CV Profiler, CV Optimizer, Interview Coach). Follows Anthropic's
[Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
methodology: **multi-layered grading** combining deterministic checks
with LLM-as-judge.

> **Job Scanner is intentionally excluded.** It's deterministic
> regex-based matching — covered by `backend/tests/test_job_scanner.py`.
> Adding LLM evals there would be category error.

---

## Layout

```
backend/evals/
  conftest.py            ← session-level setup, fixture loaders
  pytest.ini             ← isolated from tests/conftest.py autouse fixtures
  deterministic/         ← always-on, no LLM, runs every PR
  deepeval/              ← LLM-as-judge (Phase 3, lands later)
  promptfoo/             ← prompt-variant HTML reports (Phase 4, lands later)
  fixtures/              ← CV/JD/pair fixtures (Phase 2, lands later)
  reports/               ← gitignored eval output
```

---

## Running locally

```bash
cd backend

# Deterministic only — no API key required (uses mock mode).
pytest evals/ -c evals/pytest.ini -v -m "eval and not llm_judge"

# Future (Phase 3): full LLM-judge layer.
# Requires a real OPENAI_API_KEY (Gemini key works — we use the
# OpenAI-compatible Gemini endpoint).
export OPENAI_API_KEY="<your-gemini-key>"
pytest evals/ -c evals/pytest.ini -v -m "llm_judge"
```

---

## CI

Two jobs in `.github/workflows/ci.yml`:

| Job | When | Cost |
|---|---|---|
| `evals-deterministic` | Every PR, after `backend-ci` | Free (mock mode, ~30s) |
| `evals-llm` *(Phase 3+)* | `main` + manual `workflow_dispatch` | Free-tier Gemini, ~5min |

The split keeps PR feedback fast and reserves quota for merge candidates.

---

## Markers

- `@pytest.mark.eval` — every eval test opts in. Lets the regular
  `pytest tests/` invocation skip them.
- `@pytest.mark.llm_judge` — subset that calls a real LLM. Auto-applied
  to everything under `deepeval/` by `conftest.pytest_collection_modifyitems`.

---

## Adding fixtures (Phase 2 onward)

CV fixtures: hand-crafted JSON files under `fixtures/cvs/` matching
`ParsedCVData`. Use synthetic emails (`@example.com`) — no PII.

JD fixtures: raw text files under `fixtures/jds/`. Keep each under
~400 tokens to stay below the agent's truncation threshold.

Canonical pairings live in `fixtures/pairs.yaml` with a
`schema_version` field — bump it whenever Pydantic schemas evolve so
`test_*_schema_fingerprint_is_recorded` fails loudly.

---

## Phase status

| Phase | Status | Description |
|---|---|---|
| **1 — Scaffolding + deterministic** | ✅ Shipped | This commit. Schema fingerprints, keyword coverage, fabrication detector pinning, prompt-injection sanitizer pinning. |
| **2 — Fixtures + calibration** | ⏳ Pending | Hand-craft 10 CVs + 5 JDs; run full eval once; user labels 20 rows in a calibration MD; thresholds derived. |
| **3 — DeepEval LLM-judge** | ⏳ Pending | Gemini `DeepEvalBaseLLM` wrapper + 4 test files (one per agent output type). |
| **4 — Promptfoo** | ⏳ Pending | Custom Python providers calling real agent code. YAML configs + HTML report. |
| **5 — Polish** | ⏳ Pending | Cost-summary printer, adversarial fixtures, docs cross-links. |

---

## Methodology notes

- **Multi-layered grading**: deterministic = floor (every PR); LLM-judge =
  ceiling (main only). Both must pass before a result is trusted.
- **Same-model judge caveat**: Phase 3 uses Gemini Flash for both the
  agent-under-test and the judge — known weakness (judge shares the
  model's blind spots). Documented; deterministic metrics are the
  authoritative bar.
- **pass@1 by default**: with `temperature ≤ 0.4` variance is low. We
  do not run pass@k for cost reasons. Flaky metrics get
  `@pytest.mark.flaky_repeat(3)` ad-hoc.
- **Free-tier safe**: ~120 LLM calls per full eval run (15 pairs × 4
  agents × ~2 calls), well under Gemini Flash daily quota.

---

## References

- [Anthropic — Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [DeepEval docs](https://docs.confident-ai.com/docs/getting-started)
- [Promptfoo docs](https://www.promptfoo.dev/docs/getting-started/)
- Project plan: `~/.claude/plans/nu-hai-sa-facem-playful-donut.md`
- Strategy doc: `docs/agent-evals-strategy.md`
