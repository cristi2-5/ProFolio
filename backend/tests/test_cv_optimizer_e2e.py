"""
CV Optimizer E2E Tests — Phase 4 Epic 3

End-to-end tests covering the full Phase 4 stack:
  - PDF export: optimize → export CV → validate bytes
  - PDF export: cover letter generate → export → validate bytes
  - NO_FABRICATION: prompt contains all mandatory rules
  - changes_summary: field present in optimized response
  - user_motivation: threaded into cover letter prompt
  - PDF paragraph split: real newlines, not escaped \\n
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from openai import AsyncOpenAI

from app.agents.cv_optimizer import CVOptimizerAgent
from app.utils.pdf_export import CVPDFExporter, PDFExportError

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_cv_data():
    """Minimal CV data used across all E2E tests."""
    return {
        "personal_info": {
            "full_name": "Ana Popescu",
            "email": "ana@example.ro",
            "phone": "+40 721 000 000",
            "location": "Bucharest, Romania",
        },
        "summary": "Software engineer cu 4 ani experienta in backend Python si REST APIs.",
        "experience": [
            {
                "role": "Backend Developer",
                "company": "Softwave SRL",
                "duration": "2020-2024",
                "description": "Dezvoltat microservicii Python/FastAPI, integrat OAuth2, mentinut PostgreSQL.",
            }
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        "technologies": ["Git", "Linux", "Redis"],
        "education": [
            {
                "degree": "Licenta Informatica",
                "institution": "Universitatea Bucuresti",
                "year": "2020",
            }
        ],
    }


@pytest.fixture
def optimized_cv_with_changes(sample_cv_data):
    """Simulated optimized CV response including changes_summary and optimized_keywords."""
    return {
        **sample_cv_data,
        "summary": (
            "Senior Python/FastAPI engineer cu expertise in microservicii, "
            "cloud-native deployments si CI/CD pipelines."
        ),
        "skills": [
            "Python",
            "FastAPI",
            "PostgreSQL",
            "Docker",
            "REST APIs",
            "Kubernetes",
        ],
        "optimized_keywords": ["microservicii", "CI/CD", "cloud-native", "Kubernetes"],
        "changes_summary": [
            "Actualizat summary pentru a include 'cloud-native' si 'CI/CD' din JD",
            "Reordonat skills: Kubernetes adaugat pe locul 6 (exista implicit in tech stack)",
            "Reformulat bullet experience sa includa 'microservicii' din JD",
        ],
    }


@pytest.fixture
def sample_job_description():
    return """
    Senior Python Developer — CloudFirst SRL

    Cerinte:
    - 3+ ani Python, FastAPI sau Django
    - Experienta cu microservicii si Kubernetes
    - CI/CD pipelines (GitLab CI, GitHub Actions)
    - PostgreSQL si Redis
    - Cunostinte cloud-native architecture
    """


@pytest.fixture
def mock_openai_optimized_response(optimized_cv_with_changes):
    """Mock OpenAI response returning a properly structured optimized CV."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps(optimized_cv_with_changes)
    return mock_response


@pytest.fixture
def mock_openai_cover_letter_response():
    """Mock OpenAI response for cover letter with real newlines."""
    letter = (
        "Stimate Recrutor,\n\n"
        "Va scriu cu interes pentru pozitia de Senior Python Developer la CloudFirst SRL. "
        "Cu 4 ani de experienta in FastAPI si microservicii, sunt convins ca pot contribui "
        "la obiectivele echipei.\n\n"
        "In rolul meu curent la Softwave SRL am livrat sisteme REST scalabile si am "
        "implementat fluxuri CI/CD care au redus timpul de deployment cu 40%%.\n\n"
        "Cu stima,\nAna Popescu"
    )
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = letter
    return mock_response


@pytest.fixture
def cv_optimizer_agent():
    """CVOptimizerAgent with mocked OpenAI client (non-development mode)."""
    with patch("app.agents.cv_optimizer.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-test-key"
        agent = CVOptimizerAgent()
        mock_client = MagicMock(spec=AsyncOpenAI)
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        agent.client = mock_client
        return agent


# ---------------------------------------------------------------------------
# Group 1: NO_FABRICATION — prompt engineering (Phase 4 US 3.1)
# ---------------------------------------------------------------------------


class TestNoFabricationPrompts:
    """Verify that the new NO_FABRICATION rules are present in all prompts."""

    def test_cv_system_prompt_has_no_fabrication_block(self, cv_optimizer_agent):
        """System prompt must contain the mandatory NO_FABRICATION header."""
        prompt = cv_optimizer_agent._build_cv_optimization_system_prompt()
        assert "NO_FABRICATION" in prompt, "System prompt missing NO_FABRICATION block"

    def test_cv_system_prompt_forbids_inventing_experience(self, cv_optimizer_agent):
        """System prompt must explicitly forbid inventing experience."""
        prompt = cv_optimizer_agent._build_cv_optimization_system_prompt()
        assert (
            "MUST NOT invent" in prompt or "NOT invent" in prompt
        ), "System prompt does not explicitly forbid inventing experience"

    def test_cv_system_prompt_requires_changes_summary(self, cv_optimizer_agent):
        """System prompt must require changes_summary field in JSON output."""
        prompt = cv_optimizer_agent._build_cv_optimization_system_prompt()
        assert (
            "changes_summary" in prompt
        ), "System prompt does not require changes_summary field"

    def test_cv_user_prompt_labels_cv_as_source_of_truth(
        self, cv_optimizer_agent, sample_cv_data, sample_job_description
    ):
        """User prompt must indicate the CV is the ONLY source of truth."""
        prompt = cv_optimizer_agent._build_cv_optimization_user_prompt(
            sample_cv_data,
            sample_job_description,
            "Senior Python Developer",
            "CloudFirst",
        )
        assert (
            "ONLY source of truth" in prompt or "source of truth" in prompt.lower()
        ), "User prompt does not label CV as single source of truth"

    def test_cover_letter_system_prompt_has_no_fabrication(self, cv_optimizer_agent):
        """Cover letter system prompt must contain NO_FABRICATION rules."""
        prompt = cv_optimizer_agent._build_cover_letter_system_prompt()
        assert (
            "NO_FABRICATION" in prompt
        ), "Cover letter system prompt missing NO_FABRICATION block"

    def test_cover_letter_system_prompt_forbids_inventing_achievements(
        self, cv_optimizer_agent
    ):
        """Cover letter system prompt must explicitly forbid inventing achievements."""
        prompt = cv_optimizer_agent._build_cover_letter_system_prompt()
        assert (
            "NOT invent" in prompt or "do NOT invent" in prompt.lower()
        ), "Cover letter system prompt does not forbid inventing achievements"


# ---------------------------------------------------------------------------
# Group 2: changes_summary field (Phase 4 US 3.1)
# ---------------------------------------------------------------------------


class TestChangesSummaryField:
    """Verify changes_summary is preserved and propagated through the stack."""

    @pytest.mark.asyncio
    async def test_optimize_cv_returns_changes_summary(
        self,
        cv_optimizer_agent,
        sample_cv_data,
        sample_job_description,
        mock_openai_optimized_response,
    ):
        """optimize_cv_for_job must return a dict containing changes_summary."""
        cv_optimizer_agent.client.chat.completions.create.return_value = (
            mock_openai_optimized_response
        )
        result = await cv_optimizer_agent.optimize_cv_for_job(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )
        assert isinstance(result, dict), "Result must be a dict"
        assert (
            "changes_summary" in result
        ), "Optimized CV response missing changes_summary field"
        assert isinstance(
            result["changes_summary"], list
        ), "changes_summary must be a list"
        assert (
            len(result["changes_summary"]) > 0
        ), "changes_summary must have at least one entry"

    @pytest.mark.asyncio
    async def test_optimize_cv_returns_optimized_keywords(
        self,
        cv_optimizer_agent,
        sample_cv_data,
        sample_job_description,
        mock_openai_optimized_response,
    ):
        """optimize_cv_for_job should return optimized_keywords from JD."""
        cv_optimizer_agent.client.chat.completions.create.return_value = (
            mock_openai_optimized_response
        )
        result = await cv_optimizer_agent.optimize_cv_for_job(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )
        assert "optimized_keywords" in result, "Missing optimized_keywords in result"
        assert len(result["optimized_keywords"]) > 0


# ---------------------------------------------------------------------------
# Group 3: user_motivation threading (Phase 4 US 3.2)
# ---------------------------------------------------------------------------


class TestUserMotivationThreading:
    """Verify user_motivation is correctly injected into cover letter prompts."""

    def test_user_motivation_appears_in_prompt_when_provided(
        self, cv_optimizer_agent, sample_cv_data, sample_job_description
    ):
        """When user_motivation is given, it must appear in the user prompt."""
        motivation = "Sunt pasionat de cloud-native si vreau sa contribui la proiectele CloudFirst."
        prompt = cv_optimizer_agent._build_cover_letter_user_prompt(
            sample_cv_data,
            sample_job_description,
            "Senior Python Developer",
            "CloudFirst SRL",
            "Ana Popescu",
            user_motivation=motivation,
        )
        assert (
            motivation in prompt
        ), "user_motivation not found in cover letter user prompt"

    def test_user_motivation_absent_when_not_provided(
        self, cv_optimizer_agent, sample_cv_data, sample_job_description
    ):
        """When user_motivation is None, the PERSONAL MOTIVATION section must not appear."""
        prompt = cv_optimizer_agent._build_cover_letter_user_prompt(
            sample_cv_data,
            sample_job_description,
            "Senior Python Developer",
            "CloudFirst SRL",
            "Ana Popescu",
            user_motivation=None,
        )
        assert (
            "PERSONAL MOTIVATION" not in prompt
        ), "PERSONAL MOTIVATION section appeared in prompt even with None motivation"

    @pytest.mark.asyncio
    async def test_generate_cover_letter_with_motivation(
        self,
        cv_optimizer_agent,
        sample_cv_data,
        sample_job_description,
        mock_openai_cover_letter_response,
    ):
        """generate_cover_letter with user_motivation calls API and returns text."""
        cv_optimizer_agent.client.chat.completions.create.return_value = (
            mock_openai_cover_letter_response
        )
        motivation = "CloudFirst e lider in cloud-native Romania — vreau sa fac parte din echipa."
        result = await cv_optimizer_agent.generate_cover_letter(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
            user_name="Ana Popescu",
            user_motivation=motivation,
        )
        assert isinstance(result, str)
        assert len(result) >= 200, "Cover letter too short"
        # Verify motivation was injected into the prompt
        call_args = cv_optimizer_agent.client.chat.completions.create.call_args
        user_prompt = call_args.kwargs["messages"][1]["content"]
        assert motivation in user_prompt, "user_motivation not in API call prompt"


# ---------------------------------------------------------------------------
# Group 4: PDF Export — CV (Phase 4 US 3.3)
# ---------------------------------------------------------------------------


class TestCVPDFExport:
    """Validate CV PDF export produces valid, non-empty bytes."""

    @pytest.fixture
    def exporter(self):
        return CVPDFExporter()

    def test_export_cv_returns_bytes(self, exporter, optimized_cv_with_changes):
        """export_cv_to_pdf must return a non-empty bytes object."""
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv=optimized_cv_with_changes,
            user_name="Ana Popescu",
        )
        assert isinstance(pdf_data, bytes), "PDF output must be bytes"
        assert len(pdf_data) > 0, "PDF output is empty"

    def test_export_cv_with_job_target_header(
        self, exporter, optimized_cv_with_changes
    ):
        """export_cv_to_pdf with job_title+company_name must produce valid PDF."""
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv=optimized_cv_with_changes,
            user_name="Ana Popescu",
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )
        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 1000, "PDF with job header seems too small"

    def test_export_cv_pdf_starts_with_pdf_header(
        self, exporter, optimized_cv_with_changes
    ):
        """PDF bytes must start with the PDF magic bytes %PDF."""
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv=optimized_cv_with_changes,
            user_name="Ana Popescu",
            job_title="Python Dev",
            company_name="TestCorp",
        )
        assert (
            pdf_data[:4] == b"%PDF"
        ), "Output is not a valid PDF (missing %PDF header)"

    def test_export_cv_with_empty_optimized_cv(self, exporter):
        """export_cv_to_pdf with empty CV dict must still produce valid PDF."""
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv={},
            user_name="Test User",
        )
        assert len(pdf_data) > 0

    def test_export_cv_with_optimized_keywords_section(
        self, exporter, optimized_cv_with_changes
    ):
        """PDF must include ATS keywords section when optimized_keywords is provided."""
        # This test validates the _add_cv_optimized_keywords method executes without error
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv=optimized_cv_with_changes,
            user_name="Ana Popescu",
            job_title="Python Dev",
            company_name="CloudFirst",
        )
        # If ATS keywords section caused an error, pdf_data would be empty or exception raised
        assert len(pdf_data) > 1000


# ---------------------------------------------------------------------------
# Group 5: PDF Export — Cover Letter (Phase 4 US 3.3)
# ---------------------------------------------------------------------------


class TestCoverLetterPDFExport:
    """Validate cover letter PDF export produces valid, non-empty bytes."""

    @pytest.fixture
    def exporter(self):
        return CVPDFExporter()

    @pytest.fixture
    def sample_cover_letter(self):
        return (
            "Stimate Recrutor,\n\n"
            "Va scriu pentru pozitia de Python Developer.\n\n"
            "Cu stima,\nAna Popescu"
        )

    def test_export_cover_letter_returns_bytes(self, exporter, sample_cover_letter):
        """export_cover_letter_to_pdf must return non-empty bytes."""
        pdf_data = exporter.export_cover_letter_to_pdf(
            cover_letter_text=sample_cover_letter,
            user_name="Ana Popescu",
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )
        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 0

    def test_export_cover_letter_pdf_magic_bytes(self, exporter, sample_cover_letter):
        """Cover letter PDF must start with %PDF magic bytes."""
        pdf_data = exporter.export_cover_letter_to_pdf(
            cover_letter_text=sample_cover_letter,
            user_name="Ana Popescu",
            job_title="Developer",
            company_name="TestCorp",
        )
        assert pdf_data[:4] == b"%PDF"

    def test_export_cover_letter_paragraph_split_real_newlines(self, exporter):
        """Paragraphs separated by real \\n\\n must each render as separate paragraphs."""
        # This tests the bug fix: was splitting on '\\n\\n' (escaped), now splits on real '\n\n'
        multi_para_letter = (
            "Paragraph one text here.\n\n"
            "Paragraph two text here.\n\n"
            "Sincerely,\nAna Popescu"
        )
        # Must not raise exception and must produce valid PDF
        pdf_data = exporter.export_cover_letter_to_pdf(
            cover_letter_text=multi_para_letter,
            user_name="Ana Popescu",
            job_title="Developer",
            company_name="TestCorp",
        )
        assert pdf_data[:4] == b"%PDF"
        assert len(pdf_data) > 500

    def test_export_cover_letter_single_block_fallback(self, exporter):
        """Single-line cover letter text (no double newlines) must also produce PDF."""
        single_block = (
            "Dear Hiring Manager, I am interested in this position. Sincerely, Ana."
        )
        pdf_data = exporter.export_cover_letter_to_pdf(
            cover_letter_text=single_block,
            user_name="Ana Popescu",
            job_title="Developer",
            company_name="TestCorp",
        )
        assert pdf_data[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Group 6: Full E2E flow — optimize → changes_summary → export PDF
# ---------------------------------------------------------------------------


class TestFullE2EFlow:
    """Integration flow: agent optimize → PDF export → validate bytes."""

    @pytest.mark.asyncio
    async def test_optimize_then_export_cv_pdf(
        self,
        cv_optimizer_agent,
        sample_cv_data,
        sample_job_description,
        mock_openai_optimized_response,
    ):
        """Full E2E: optimize CV → export PDF → validate PDF bytes > 0."""
        # Step 1: optimize CV
        cv_optimizer_agent.client.chat.completions.create.return_value = (
            mock_openai_optimized_response
        )
        optimized = await cv_optimizer_agent.optimize_cv_for_job(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )

        assert "changes_summary" in optimized
        assert len(optimized["changes_summary"]) > 0

        # Step 2: export to PDF
        exporter = CVPDFExporter()
        pdf_data = exporter.export_cv_to_pdf(
            optimized_cv=optimized,
            user_name="Ana Popescu",
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )

        # Step 3: validate PDF
        assert pdf_data[:4] == b"%PDF", "E2E: Result is not a valid PDF"
        assert len(pdf_data) > 1000, "E2E: PDF seems too small"

    @pytest.mark.asyncio
    async def test_generate_cover_letter_then_export_pdf(
        self,
        cv_optimizer_agent,
        sample_cv_data,
        sample_job_description,
        mock_openai_cover_letter_response,
    ):
        """Full E2E: generate cover letter → export PDF → validate bytes."""
        # Step 1: generate cover letter
        cv_optimizer_agent.client.chat.completions.create.return_value = (
            mock_openai_cover_letter_response
        )
        cover_letter = await cv_optimizer_agent.generate_cover_letter(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
            user_name="Ana Popescu",
            user_motivation="Sunt pasionat de proiectele cloud-native ale CloudFirst.",
        )

        assert isinstance(cover_letter, str)
        assert len(cover_letter) >= 200

        # Step 2: export to PDF
        exporter = CVPDFExporter()
        pdf_data = exporter.export_cover_letter_to_pdf(
            cover_letter_text=cover_letter,
            user_name="Ana Popescu",
            job_title="Senior Python Developer",
            company_name="CloudFirst SRL",
        )

        # Step 3: validate PDF
        assert pdf_data[:4] == b"%PDF", "E2E: Cover letter result is not a valid PDF"
        assert len(pdf_data) > 500, "E2E: Cover letter PDF too small"
