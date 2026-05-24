"""``NoFabricationGEval`` — strict NO_FABRICATION contract for CV Optimizer.

The CV Optimizer's system prompt forbids inventing skills, technologies,
experience, or qualifications not present in the candidate's input CV.
This GEval criterion mirrors that contract so the LLM judge can score
optimized outputs on the same axis users (and our deterministic
fabrication scan) care about.

Why GEval (not Hallucination/Faithfulness directly):
    Hallucination is a "fraction of unsupported claims" metric — fine
    for free-text outputs, but the optimizer returns structured JSON
    where the danger is specifically NEW SKILLS / TECHS appearing in
    the reordered output. GEval lets us spell out exactly what we
    care about so the judge focuses there.

    DeepEval's Hallucination + AnswerRelevancy still apply to the
    free-text fields (summary, bullet descriptions); we layer them on
    top in ``test_cv_optimizer_eval.py``.
"""

from __future__ import annotations

from typing import Any

from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams

from evals.llm_judge.judge import build_judge


def NoFabricationGEval(*, threshold: float, model: Any | None = None) -> GEval:
    """Construct a GEval metric enforcing the NO_FABRICATION contract.

    Args:
        threshold: pass threshold from ``thresholds.yaml``. Strict (≥ 0.9)
            because the contract is contractually non-negotiable — the
            agent's prompt explicitly forbids fabrication.
        model: judge to invoke. Defaults to ``GeminiJudge`` via
            ``build_judge()`` if not supplied.

    Returns:
        Configured ``GEval`` metric ready to be passed to ``assert_test``.
    """
    return GEval(
        name="NoFabrication",
        # Criteria are written in plain English; DeepEval embeds them
        # into a chain-of-thought prompt that walks the judge through
        # comparing the optimized output to the source CV (in CONTEXT).
        criteria=(
            "The ACTUAL_OUTPUT is an optimized CV in JSON form. The "
            "CONTEXT contains the candidate's original CV. Verify that "
            "EVERY skill, technology, tool, company, year, and achievement "
            "claimed in the ACTUAL_OUTPUT is also present (or directly "
            "implied) in the CONTEXT. "
            "Score 1.0 if no fabrication is detected. "
            "Score 0.5 if minor reordering or rephrasing introduces a "
            "term not in the CV but plausibly inferable. "
            "Score 0.0 if any clearly new skill, technology, or "
            "qualification appears in ACTUAL_OUTPUT that is absent from "
            "CONTEXT."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        threshold=threshold,
        model=model or build_judge(),
        # Verbose mode includes the judge's reasoning in failure
        # messages — invaluable when triaging a CI red.
        verbose_mode=False,
    )


def NotGenericGEval(*, threshold: float, model: Any | None = None) -> GEval:
    """Construct a GEval metric enforcing cover-letter personalization.

    Cover letters scored by ``cover_letter_personalization`` (deterministic)
    only check that company and title appear — necessary but trivial.
    This GEval enforces the harder property: the letter ties a specific
    CV achievement to a specific JD requirement.

    Args:
        threshold: pass threshold from ``thresholds.yaml``.
        model: judge to invoke. Defaults to ``GeminiJudge``.
    """
    return GEval(
        name="NotGeneric",
        criteria=(
            "The ACTUAL_OUTPUT is a cover letter. The INPUT contains "
            "the job description. The CONTEXT contains the candidate's "
            "background. "
            "Score 1.0 if the letter (a) names the specific company AND "
            "(b) ties at least one concrete achievement from CONTEXT to "
            "at least one specific requirement in INPUT. "
            "Score 0.5 if either condition is partially met (e.g. names "
            "company but uses generic claims). "
            "Score 0.0 if the letter could fit any candidate for any "
            "role — generic platitudes, template placeholders like "
            "``[Your Name]``, or no concrete linkage between background "
            "and JD."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        threshold=threshold,
        model=model or build_judge(),
        verbose_mode=False,
    )
