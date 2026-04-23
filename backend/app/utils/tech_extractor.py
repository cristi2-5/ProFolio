"""
Technology Extractor — Deterministic extraction of technologies from JD text.

Used by the Interview Coach to build a reliable list of technologies
mentioned in a Job Description before handing off to the LLM for
concise definitions. Pure regex + curated catalog: no API calls, no
hallucinations, fully testable.

The catalog is intentionally conservative (well-known tech only) and
grouped by category so the LLM prompt can bucket definitions cleanly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

# ------------------------------------------------------------------
# Curated catalog
# ------------------------------------------------------------------
# Each entry maps the canonical display name → list of case-insensitive
# aliases that should match in text. We use word boundaries so "java"
# doesn't match "javascript" and "go" doesn't match "google".
#
# Keep aliases narrow; false positives hurt more than misses here since
# the LLM is the fallback for long-tail tech.
# ------------------------------------------------------------------

TechCatalog = Dict[str, Dict[str, Sequence[str]]]

CATALOG: TechCatalog = {
    "languages": {
        "Python": ["python"],
        "JavaScript": ["javascript", "js"],
        "TypeScript": ["typescript", "ts"],
        "Java": ["java"],
        "Kotlin": ["kotlin"],
        "Swift": ["swift"],
        "Go": ["golang", "go"],
        "Rust": ["rust"],
        "C++": [r"c\+\+", "cpp"],
        "C#": [r"c#", "csharp"],
        "C": [r"\bc\b(?!\+\+|#)"],
        "Ruby": ["ruby"],
        "PHP": ["php"],
        "Scala": ["scala"],
        "R": [r"\br\b"],
        "SQL": ["sql"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"],
        "Bash": ["bash", "shell scripting"],
    },
    "frontend": {
        "React": ["react", "react.js", "reactjs"],
        "Next.js": ["next.js", "nextjs", "next js"],
        "Vue.js": ["vue", "vue.js", "vuejs"],
        "Angular": ["angular", "angularjs"],
        "Svelte": ["svelte", "sveltekit"],
        "Tailwind CSS": ["tailwind", "tailwind css", "tailwindcss"],
        "Redux": ["redux"],
        "Webpack": ["webpack"],
        "Vite": ["vite"],
    },
    "backend": {
        "Node.js": ["node.js", "node", "nodejs"],
        "Express": ["express", "express.js", "expressjs"],
        "NestJS": ["nestjs", "nest.js"],
        "Django": ["django"],
        "Flask": ["flask"],
        "FastAPI": ["fastapi", "fast api"],
        "Spring Boot": ["spring boot", "springboot", "spring"],
        "Ruby on Rails": ["rails", "ruby on rails"],
        "Laravel": ["laravel"],
        "GraphQL": ["graphql"],
        "REST API": ["rest api", "restful api", "rest"],
        "gRPC": ["grpc"],
    },
    "databases": {
        "PostgreSQL": ["postgres", "postgresql"],
        "MySQL": ["mysql"],
        "SQLite": ["sqlite"],
        "MongoDB": ["mongodb", "mongo"],
        "Redis": ["redis"],
        "Elasticsearch": ["elasticsearch", "elastic search"],
        "DynamoDB": ["dynamodb"],
        "Cassandra": ["cassandra"],
    },
    "cloud": {
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure"],
        "GCP": ["gcp", "google cloud", "google cloud platform"],
        "Vercel": ["vercel"],
        "Netlify": ["netlify"],
        "Heroku": ["heroku"],
    },
    "devops": {
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Terraform": ["terraform"],
        "Ansible": ["ansible"],
        "Jenkins": ["jenkins"],
        "GitHub Actions": ["github actions"],
        "GitLab CI": ["gitlab ci", "gitlab-ci"],
        "CircleCI": ["circleci", "circle ci"],
        "CI/CD": ["ci/cd", r"ci\\cd", "continuous integration"],
        "Nginx": ["nginx"],
        "Linux": ["linux", "unix"],
        "Git": [r"\bgit\b"],
    },
    "data_ai": {
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch", "py torch"],
        "scikit-learn": ["scikit-learn", "sklearn"],
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "Apache Spark": ["spark", "apache spark"],
        "Kafka": ["kafka", "apache kafka"],
        "Airflow": ["airflow", "apache airflow"],
        "dbt": [r"\bdbt\b"],
        "Tableau": ["tableau"],
        "Power BI": ["power bi", "powerbi"],
        "LLM": ["llm", "large language model"],
        "OpenAI": ["openai", "gpt-4", "gpt-3.5"],
    },
    "mobile": {
        "React Native": ["react native"],
        "Flutter": ["flutter"],
        "iOS": ["ios"],
        "Android": ["android"],
    },
    "testing": {
        "Jest": ["jest"],
        "Pytest": ["pytest"],
        "Cypress": ["cypress"],
        "Playwright": ["playwright"],
        "Selenium": ["selenium"],
        "JUnit": ["junit"],
    },
    "methodologies": {
        "Agile": ["agile"],
        "Scrum": ["scrum"],
        "Kanban": ["kanban"],
        "TDD": [r"\btdd\b", "test-driven development"],
        "Microservices": ["microservices", "micro-services"],
        "Event-Driven Architecture": ["event-driven", "event driven"],
    },
}


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedTech:
    """A single technology mention found in the JD.

    Attributes:
        name: Canonical display name (e.g. "React", "PostgreSQL").
        category: Bucket from the catalog (e.g. "frontend", "databases").
        mentions: Number of times the tech appears in the JD.
    """

    name: str
    category: str
    mentions: int


# ------------------------------------------------------------------
# Compiled patterns (module-level cache)
# ------------------------------------------------------------------

def _compile_alias_pattern(alias: str) -> re.Pattern[str]:
    """Compile an alias into a case-insensitive regex.

    Aliases containing regex metacharacters are treated as raw regex.
    Plain aliases get explicit boundaries that prevent matching inside
    other tech tokens (e.g. "java" must not match "javascript", "Node"
    must not match "Node.js") while still allowing normal sentence
    punctuation like trailing periods and commas to follow the match.

    Boundary logic:
        left — no alnum/underscore directly before.
        right — no alnum/underscore/+/# directly after, and no "." or "-"
                 followed by a letter (which would indicate continuation
                 into a compound name like Node.js or scikit-learn).
    """
    if any(ch in alias for ch in r"\()[]{}|^$*?"):
        return re.compile(alias, re.IGNORECASE)

    escaped = re.escape(alias)
    left = r"(?<![A-Za-z0-9_])"
    right = (
        r"(?![A-Za-z0-9_+#])"          # no continuation into tech token
        r"(?!\.[A-Za-z0-9])"           # no ".js", ".py" suffix
        r"(?!-[A-Za-z])"               # no "-learn", "-cli" suffix
    )
    return re.compile(rf"{left}{escaped}{right}", re.IGNORECASE)


_COMPILED: List[Tuple[str, str, re.Pattern[str]]] = [
    (name, category, _compile_alias_pattern(alias))
    for category, entries in CATALOG.items()
    for name, aliases in entries.items()
    for alias in aliases
]


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def extract_technologies(
    text: str,
    *,
    max_results: int = 15,
) -> List[ExtractedTech]:
    """Extract technologies mentioned in JD text, ranked by frequency.

    Deterministic: same input → same output. Safe to use in tests without
    mocking. Returns at most ``max_results`` entries.

    Args:
        text: Free-form job description text.
        max_results: Cap on returned technologies (default 15).

    Returns:
        List of ExtractedTech ordered by mention count (desc), then
        alphabetically on ties. Empty list for empty input.
    """
    if not text:
        return []

    counts: Dict[str, int] = {}
    categories: Dict[str, str] = {}

    for name, category, pattern in _COMPILED:
        matches = pattern.findall(text)
        if not matches:
            continue
        counts[name] = counts.get(name, 0) + len(matches)
        # First category wins; the catalog is structured so each tech
        # appears in exactly one category anyway.
        categories.setdefault(name, category)

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0].lower()),
    )

    return [
        ExtractedTech(name=name, category=categories[name], mentions=count)
        for name, count in ranked[:max_results]
    ]


def group_by_category(techs: Iterable[ExtractedTech]) -> Dict[str, List[str]]:
    """Group extracted technologies by category.

    Used by prompt builders that want to show the LLM a clean bucketed
    list (e.g. "Languages: Python, Go — Frontend: React, ...").

    Args:
        techs: Iterable of ExtractedTech instances.

    Returns:
        Dict mapping category → list of tech names (preserving input order).
    """
    grouped: Dict[str, List[str]] = {}
    for tech in techs:
        grouped.setdefault(tech.category, []).append(tech.name)
    return grouped
