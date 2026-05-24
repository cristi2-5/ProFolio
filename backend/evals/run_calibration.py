"""Calibration runner — execute the LLM agents against sampled fixtures.

The output is a Markdown report ready for human labeling. The reviewer
reads ~10 rows of (input, output excerpt, deterministic score) and marks
PASS / FAIL / BORDERLINE in the ``verdict`` column. Thresholds for Phase 3
LLM-judge evals are then derived from the labeled scores.

Why a script (not a pytest test):
    - We want a Markdown side-effect, not a pass/fail. Tests don't write
      review artifacts cleanly.
    - We sample fixtures (5 of 15 pairs × 2 agents) so the review is
      ~10 rows — manageable in 30-45 min.
    - The script runs once, manually, after Phase 2 lands.

Free-tier reality check
    Observed Gemini free-tier limits during the first run:
      - ``gemini-2.5-flash`` — 5 RPM (one call per 12 s)
      - ``gemini-2.0-flash`` — daily quota of zero on this account
      - ``gemini-1.5-flash`` — 404 (model retired)

    To stay safely under the per-minute cap we run sequentially with a
    13 s delay between LLM calls (5 RPM headroom is 12 s; +1 s buffer).
    We also skip the Interview Coach in this script — its happy path
    makes three LLM calls per pair, which would triple the wall clock
    and the quota burn. Phase 3 will eval the coach via DeepEval where
    we can micro-batch and cache aggressively.

Usage::

    cd backend
    export OPENAI_API_KEY="<real Gemini key>"   # script aborts on mock keys
    python -m evals.run_calibration

The report is written incrementally — every row is flushed to disk so a
mid-run quota crash never loses prior work. Re-running just regenerates
the same file (timestamped by date).
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

# Local imports — script is meant to be run with ``python -m evals.run_calibration``
# from ``backend/``.
from evals.conftest import (
    REPORTS_DIR,
    iter_pairs,
    load_cv_fixture,
    load_jd_fixture,
)
from app.agents.cv_optimizer import CVOptimizerAgent


logger = logging.getLogger("evals.calibration")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ----------------------------------------------------------------------
# Sampling — minimal viable set
# ----------------------------------------------------------------------


# Five canonical pairs spanning the strong/partial/weak spectrum. We
# need at least one of each case-band so the labeled scores span the
# full range — without weak anchors the derived threshold collapses to
# near-1.0 and the eval becomes useless.
SAMPLED_PAIR_IDS: tuple[str, ...] = (
    "mid_backend_python__senior_python_backend",  # strong
    "senior_devops__devops_sre",                  # strong
    "senior_java__senior_python_backend",         # partial
    "mid_backend_python__ml_engineer",            # partial
    "junior_data_analyst__senior_python_backend", # weak
)


# Two agents per pair → 10 rows total. Interview Coach is intentionally
# excluded — see module docstring.
AGENTS_PER_PAIR: tuple[str, ...] = ("optimize_cv", "cover_letter")


# Sleep between LLM calls. ``gemini-2.5-flash`` allows 5 RPM, so the
# tightest gap is 12 s. We add 1 s of buffer for clock skew + slow
# server-side accounting. Total wall clock for 5 pairs × 2 calls = 10
# calls × 13 s ≈ 2 min 10 s.
INTER_CALL_DELAY_S: float = 13.0


# ----------------------------------------------------------------------
# Lightweight deterministic baseline metrics
# ----------------------------------------------------------------------


def _keyword_set(text: str) -> set[str]:
    """Lowercase token set — same regex shape used in ``test_keyword_coverage.py``."""
    import re

    return {m.group(0).lower() for m in re.finditer(r"[A-Za-z][A-Za-z0-9+.#\-]{2,}", text)}


def jd_keyword_coverage(optimized_payload: Any, jd_text: str) -> float:
    """Fraction of JD's tech-looking tokens visible in the optimizer output."""
    flat = _keyword_set(str(optimized_payload))
    jd_tokens = _keyword_set(jd_text)
    tech_jd = {
        t for t in jd_tokens
        if t[0:1].isupper() or any(t.endswith(suf) for suf in ("js", "sql", "db", ".net", "++"))
    }
    if not tech_jd:
        return 1.0
    return len(tech_jd & flat) / len(tech_jd)


def cover_letter_personalization(letter: str, company: str, job_title: str) -> float:
    """1.0 if both company and job title appear in the letter, 0.0 otherwise."""
    if not letter:
        return 0.0
    blob = letter.lower()
    hits = int(company.lower() in blob) + int(job_title.lower() in blob)
    return hits / 2


# ----------------------------------------------------------------------
# Per-agent runners — sequential, throttled, fault-tolerant
# ----------------------------------------------------------------------


async def run_optimizer(cv: dict, jd: str, job_title: str, company: str) -> tuple[float, str]:
    agent = CVOptimizerAgent()
    result = await agent.optimize_cv_for_job(
        parsed_cv=cv, job_description=jd, job_title=job_title, company_name=company
    )
    score = jd_keyword_coverage(result, jd)
    excerpt = (result.get("summary") or "")[:300]
    return score, excerpt


async def run_cover_letter(cv: dict, jd: str, job_title: str, company: str) -> tuple[float, str]:
    agent = CVOptimizerAgent()
    letter = await agent.generate_cover_letter(
        parsed_cv=cv,
        job_description=jd,
        job_title=job_title,
        company_name=company,
        user_name=cv.get("full_name") or "Applicant",
    )
    score = cover_letter_personalization(letter, company, job_title)
    excerpt = letter[:300] if letter else ""
    return score, excerpt


AGENT_RUNNERS = {
    "optimize_cv": run_optimizer,
    "cover_letter": run_cover_letter,
}


# ----------------------------------------------------------------------
# Main orchestration
# ----------------------------------------------------------------------


def _assert_real_api_key() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("test-") or "dummy" in api_key:
        print(
            "ERROR: calibration runner needs a real OPENAI_API_KEY (Gemini-compatible).\n"
            "Mock-prefixed keys (test-*, *dummy*) abort because the report would be useless.\n"
            "Set it locally:  export OPENAI_API_KEY=<real-key>",
            file=sys.stderr,
        )
        sys.exit(2)


def _metric_name(agent_label: str) -> str:
    return {
        "optimize_cv": "jd_keyword_coverage",
        "cover_letter": "personalization",
    }.get(agent_label, "?")


def _row(pair_id: str, case: str, agent: str, score: object, excerpt: str) -> dict:
    return {
        "pair_id": pair_id,
        "case": case,
        "agent": agent,
        "metric": _metric_name(agent),
        "score": f"{score:.2f}" if isinstance(score, (int, float)) else str(score),
        "excerpt": excerpt.replace("\n", " ").strip(),
    }


def render_markdown(rows: list[dict]) -> str:
    today = _dt.date.today().isoformat()
    seen_pairs: list[tuple[str, str]] = []
    seen_set: set[str] = set()
    for row in rows:
        if row["pair_id"] not in seen_set:
            seen_pairs.append((row["pair_id"], row["case"]))
            seen_set.add(row["pair_id"])

    header = textwrap.dedent(
        f"""
        # Calibration Run — {today}

        **What to do:** for each row, fill the `verdict` column with one of:

        - `PASS` — the output meets your bar for that agent
        - `FAIL` — clearly does not meet the bar
        - `BORDERLINE` — meh; would let it through with reservations

        The thresholds for Phase 3 LLM-judge evals are derived from your
        labels using `min(scores where verdict=='PASS') - 0.05`. Be honest:
        labeling everything PASS produces a useless threshold floor.

        After labeling, save this file and ping the implementer. The
        derived `thresholds.yaml` will be reviewed in PR before commit.

        ## Sampled pairs
        """
    ).strip()
    pair_lines = ["", "| pair_id | case | rationale |", "|---|---|---|"]
    for pair_id, case in seen_pairs:
        pair_lines.append(f"| `{pair_id}` | {case} | (see pairs.yaml) |")

    table_lines = [
        "",
        "## Rows to label",
        "",
        "| # | pair_id | agent | metric | score | output excerpt (first 300 chars) | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(rows, 1):
        excerpt = row["excerpt"].replace("|", "\\|")[:300]
        table_lines.append(
            f"| {i} | `{row['pair_id']}` | {row['agent']} | {row['metric']} | "
            f"{row['score']} | {excerpt} | |"
        )

    return "\n".join([header, *pair_lines, *table_lines, ""])


def _flush(rows: list[dict], out_path: Path) -> None:
    """Write the report so far — called after every row so we never lose data."""
    out_path.write_text(render_markdown(rows), encoding="utf-8")


async def main() -> None:
    _assert_real_api_key()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().isoformat()
    out_path = REPORTS_DIR / f"calibration_run_{today}.md"

    all_pairs = {p["id"]: p for p in iter_pairs()}
    if not all_pairs:
        raise RuntimeError(
            "pairs.yaml has no entries. Phase 2 fixtures missing — "
            "look in backend/evals/fixtures/."
        )

    rows: list[dict] = []
    first_call = True

    for pair_id in SAMPLED_PAIR_IDS:
        pair = all_pairs.get(pair_id)
        if not pair:
            logger.warning("Skipping unknown pair_id %s", pair_id)
            continue

        cv = load_cv_fixture(pair["cv"])
        jd = load_jd_fixture(pair["jd"])
        job_title = pair["jd"].replace("_", " ").title()
        company = f"Calibration Co — {pair['jd']}"
        case = pair.get("case", "?")

        for agent_label in AGENTS_PER_PAIR:
            if not first_call:
                logger.info(
                    "Sleeping %.0fs to respect 5 RPM ceiling …", INTER_CALL_DELAY_S
                )
                await asyncio.sleep(INTER_CALL_DELAY_S)
            first_call = False

            logger.info("Running %s on %s …", agent_label, pair_id)
            try:
                score, excerpt = await AGENT_RUNNERS[agent_label](
                    cv=cv, jd=jd, job_title=job_title, company=company
                )
                rows.append(_row(pair_id, case, agent_label, score, excerpt))
            except Exception as exc:  # noqa: BLE001 — intentionally broad: log + continue
                logger.warning("%s failed on %s: %s", agent_label, pair_id, exc)
                rows.append(
                    _row(
                        pair_id,
                        case,
                        agent_label,
                        "ERROR",
                        f"{type(exc).__name__}: {exc}",
                    )
                )

            # Flush after every row so a mid-run crash retains progress.
            _flush(rows, out_path)

    print(f"\n✅ Calibration report written to {out_path}")
    print(f"   {len(rows)} rows — open the file and fill the verdict column.\n")


if __name__ == "__main__":
    asyncio.run(main())
