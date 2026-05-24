"""Reportlab-based PDF generators for CV Profiler evals.

The CV Profiler agent parses PDF/DOCX into structured JSON. Its evals
need real PDF inputs — but committing binaries to git is bad practice
(diff-unfriendly, AV-flagged, easy to drift from text content). So we
generate small PDFs on-the-fly in-memory from a small dictionary of
realistic CV bodies.

Pattern lifted from ``backend/tests/test_cv_profiler_edge_cases.py``
where the same approach is used for malformed-input fixtures.

Usage::

    from backend.evals.fixtures.golden_pdfs import GOLDEN_CV_BODIES, build_pdf

    pdf_path = build_pdf(tmp_path, body=GOLDEN_CV_BODIES["python_backend"])
"""

from __future__ import annotations

from pathlib import Path


# ----------------------------------------------------------------------
# Golden bodies — the *text* the CV Profiler should extract from each PDF.
# Phase 3 evals will compare the parsed JSON output against the
# expectations encoded alongside each body in ``EXPECTED_FIELDS``.
# ----------------------------------------------------------------------


GOLDEN_CV_BODIES: dict[str, str] = {
    "python_backend": """Andrei Popescu
andrei.popescu@example.com | +40 700 000 020 | Cluj-Napoca, Romania

Summary
Backend engineer with 5 years building Python services on FastAPI and PostgreSQL.

Experience
Acme Logistics — Senior Backend Engineer — 2021 to Present
Owned the order-processing FastAPI service handling 2k RPS. Designed
the idempotency layer that cut duplicate-charge incidents by 95%.
Stack: Python, FastAPI, PostgreSQL, Redis, Docker.

DataFlow SRL — Backend Developer — 2019 to 2021
Built data ingestion pipelines in Python. Migrated a Django monolith
to 6 FastAPI services. Set up Prometheus monitoring.

Education
BSc Computer Science — Technical University of Cluj-Napoca — 2019

Skills
Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, Prometheus, Git
""",
    "react_frontend": """Maria Ionescu
maria.ionescu@example.com | +40 700 000 021 | Bucharest, Romania

Summary
Frontend developer with 2 years professional React experience.

Experience
WebStart SRL — Frontend Developer — 2023 to Present
Built and maintained React components for an e-commerce dashboard.
Migrated 3 legacy class components to hooks. Wrote unit tests in Vitest.
Stack: React, JavaScript, TypeScript, Vitest, CSS.

Education
BSc Computer Science — University of Bucharest — 2023

Skills
JavaScript, TypeScript, React, HTML, CSS, Vitest, Git
""",
    "devops_sre": """Mihai Stoica
mihai.stoica@example.com | +40 700 000 022 | Iași, Romania

Summary
SRE with 9 years operating Kubernetes platforms at scale.

Experience
PayBridge — Staff SRE — 2021 to Present
Designed the multi-region active-active topology on AWS EKS.
Cut MTTR from 47 minutes to 9 minutes via runbook automation in Go.
Stack: Kubernetes, Terraform, AWS, Go, Prometheus, ArgoCD.

CloudFirst SRL — DevOps Engineer — 2018 to 2021
Migrated 12 microservices to ArgoCD GitOps. Built a Helm chart library.
Stack: Kubernetes, ArgoCD, Helm, Docker.

Education
BSc Computer Engineering — Gheorghe Asachi Technical University — 2018

Certifications
CKA, AWS Certified DevOps Engineer Professional, Terraform Associate

Skills
Kubernetes, Terraform, AWS, Docker, Go, Bash, Prometheus, Linux
""",
}


# Expected field bounds for each body — Phase 3 evals will assert that
# the parsed result respects these. We use sets and ranges instead of
# exact equality to accommodate normal LLM variance (e.g. "Python" vs
# "Python 3.x" should both count as the same skill).
EXPECTED_FIELDS: dict[str, dict] = {
    "python_backend": {
        "skill_subset": {"Python", "FastAPI", "PostgreSQL"},
        "years_range": (4, 7),
        "min_experiences": 2,
    },
    "react_frontend": {
        "skill_subset": {"React", "JavaScript"},
        "years_range": (1, 3),
        "min_experiences": 1,
    },
    "devops_sre": {
        "skill_subset": {"Kubernetes", "Terraform", "AWS", "Docker"},
        "years_range": (7, 11),
        "min_experiences": 2,
    },
}


def build_pdf(target_dir: Path, *, body: str, filename: str = "cv.pdf") -> Path:
    """Render ``body`` into a single-page PDF in ``target_dir``.

    Uses reportlab line-by-line drawing so the text is extractable by
    pypdf (which the CV Profiler uses internally). Lazy-imports
    reportlab so this module is cheap to import in non-Profiler tests.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    target = target_dir / filename
    c = canvas.Canvas(str(target), pagesize=letter)
    width, height = letter

    # Draw text line by line starting from the top of the page.
    # 72pt margin top + bottom; line height ~14pt at 11pt font.
    x_margin = 72
    y_position = height - 72
    line_height = 14

    c.setFont("Helvetica", 11)
    for line in body.splitlines():
        if y_position < 72:
            # Page overflow — start a new page.
            c.showPage()
            c.setFont("Helvetica", 11)
            y_position = height - 72
        c.drawString(x_margin, y_position, line)
        y_position -= line_height

    c.showPage()
    c.save()
    return target
