"""
Tests for PDF Export Utility — Professional document generation.

Tests PDF generation for optimized CVs and cover letters with proper
formatting, error handling, and document structure validation.
"""

import io
import pytest
from unittest.mock import patch, Mock

from app.utils.pdf_export import CVPDFExporter, PDFExportError


class TestCVPDFExporter:
    """Test PDF export functionality."""

    @pytest.fixture
    def pdf_exporter(self):
        """Create PDF exporter instance."""
        return CVPDFExporter()

    @pytest.fixture
    def sample_optimized_cv(self):
        """Sample optimized CV data for PDF testing."""
        return {
            "personal_info": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0123",
                "location": "New York, NY",
                "linkedin": "linkedin.com/in/johndoe"
            },
            "summary": "Senior Frontend Developer with 5+ years of experience building scalable React applications and modern JavaScript frameworks.",
            "experience": [
                {
                    "role": "Senior Developer",
                    "company": "TechCorp Inc",
                    "duration": "2020-2023",
                    "description": "Led development of responsive web applications using React, TypeScript, and Node.js. Implemented automated testing and optimized application performance for 50% faster load times."
                },
                {
                    "role": "Frontend Developer",
                    "company": "StartupXYZ",
                    "duration": "2018-2020",
                    "description": ["Developed user interfaces using React and Redux", "Collaborated with design team on UX improvements", "Implemented responsive design principles"]
                }
            ],
            "skills": ["React", "TypeScript", "JavaScript", "Node.js", "Python"],
            "technologies": ["AWS", "Docker", "Git", "MongoDB", "Jest"],
            "education": [
                {
                    "degree": "Bachelor of Science in Computer Science",
                    "institution": "University of Technology",
                    "year": "2018"
                }
            ]
        }

    @pytest.fixture
    def sample_cover_letter(self):
        """Sample cover letter for PDF testing."""
        return """Dear Hiring Manager,

I am writing to express my strong interest in the Senior Frontend Developer position at InnovateTech. With over 5 years of experience developing scalable React applications and expertise in modern JavaScript frameworks, I am excited about the opportunity to contribute to your innovative team.

In my current role as Senior Developer at TechCorp Inc, I have successfully led the development of responsive web applications using React and TypeScript, directly aligning with your requirements. My experience includes implementing automated testing strategies that reduced bug reports by 40% and optimizing application performance to achieve 50% faster load times.

I am particularly drawn to InnovateTech's commitment to cutting-edge technology and innovation. Your focus on creating user-centric applications resonates with my passion for developing intuitive, high-performance web experiences that drive business results.

I would welcome the opportunity to discuss how my technical expertise and proven track record can contribute to InnovateTech's continued success. Thank you for considering my application.

Sincerely,
John Doe"""

    def test_pdf_exporter_initialization(self, pdf_exporter):
        """Test PDF exporter initialization."""
        assert pdf_exporter.page_size is not None
        assert "left" in pdf_exporter.margins
        assert "right" in pdf_exporter.margins
        assert "top" in pdf_exporter.margins
        assert "bottom" in pdf_exporter.margins
        assert pdf_exporter.styles is not None

    def test_setup_styles(self, pdf_exporter):
        """Test custom style setup."""
        # Verify custom styles are created
        assert "CVTitle" in pdf_exporter.styles
        assert "SectionHeader" in pdf_exporter.styles
        assert "ContactInfo" in pdf_exporter.styles
        assert "JobTitle" in pdf_exporter.styles
        assert "CompanyName" in pdf_exporter.styles
        assert "ExperienceDetails" in pdf_exporter.styles
        assert "Skills" in pdf_exporter.styles

        # Verify style properties
        cv_title = pdf_exporter.styles["CVTitle"]
        assert cv_title.fontSize == 18
        assert cv_title.alignment == 1  # Center

    def test_export_cv_to_pdf_success(self, pdf_exporter, sample_optimized_cv):
        """Test successful CV PDF generation."""
        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=sample_optimized_cv,
            user_name="John Doe"
        )

        # Verify PDF was generated
        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 1000  # Reasonable size for PDF
        assert pdf_data.startswith(b"%PDF")  # PDF magic number

    def test_export_cover_letter_to_pdf_success(self, pdf_exporter, sample_cover_letter):
        """Test successful cover letter PDF generation."""
        pdf_data = pdf_exporter.export_cover_letter_to_pdf(
            cover_letter_text=sample_cover_letter,
            user_name="John Doe",
            job_title="Senior Frontend Developer",
            company_name="InnovateTech"
        )

        # Verify PDF was generated
        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 1000
        assert pdf_data.startswith(b"%PDF")

    def test_export_cv_minimal_data(self, pdf_exporter):
        """Test CV PDF generation with minimal data."""
        minimal_cv = {
            "summary": "Brief summary",
            "experience": [],
            "skills": []
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=minimal_cv,
            user_name="Test User"
        )

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 500

    def test_export_cv_with_string_experience(self, pdf_exporter):
        """Test CV PDF with experience descriptions as strings."""
        cv_data = {
            "experience": [
                {
                    "role": "Developer",
                    "company": "Test Corp",
                    "duration": "2020-2023",
                    "description": "Single string description of work responsibilities and achievements."
                }
            ],
            "skills": ["Python", "JavaScript"]
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=cv_data,
            user_name="Test User"
        )

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 500

    def test_export_cv_with_list_experience(self, pdf_exporter):
        """Test CV PDF with experience descriptions as lists."""
        cv_data = {
            "experience": [
                {
                    "role": "Developer",
                    "company": "Test Corp",
                    "description": [
                        "First responsibility",
                        "Second achievement",
                        "Third project outcome"
                    ]
                }
            ]
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=cv_data,
            user_name="Test User"
        )

        assert isinstance(pdf_data, bytes)

    @patch("app.utils.pdf_export.SimpleDocTemplate")
    def test_export_cv_pdf_error_handling(self, mock_doc_class, pdf_exporter, sample_optimized_cv):
        """Test error handling in CV PDF generation."""
        # Mock SimpleDocTemplate to raise exception
        mock_doc_class.side_effect = Exception("PDF generation error")

        with pytest.raises(PDFExportError, match="PDF generation failed"):
            pdf_exporter.export_cv_to_pdf(
                optimized_cv=sample_optimized_cv,
                user_name="Test User"
            )

    @patch("app.utils.pdf_export.SimpleDocTemplate")
    def test_export_cover_letter_pdf_error_handling(self, mock_doc_class, pdf_exporter):
        """Test error handling in cover letter PDF generation."""
        mock_doc_class.side_effect = Exception("PDF generation error")

        with pytest.raises(PDFExportError, match="Cover letter PDF generation failed"):
            pdf_exporter.export_cover_letter_to_pdf(
                cover_letter_text="Test letter content",
                user_name="Test User",
                job_title="Developer",
                company_name="Test Corp"
            )

    def test_add_cv_header(self, pdf_exporter, sample_optimized_cv):
        """Test CV header generation."""
        story = []
        pdf_exporter._add_cv_header(story, sample_optimized_cv, "John Doe")

        assert len(story) > 0
        # Should have name, contact info, and spacer
        assert len(story) >= 3

    def test_add_cv_header_minimal_contact(self, pdf_exporter):
        """Test CV header with minimal contact information."""
        cv_data = {"personal_info": {"email": "test@example.com"}}
        story = []

        pdf_exporter._add_cv_header(story, cv_data, "Test User")
        assert len(story) > 0

    def test_add_cv_header_no_contact(self, pdf_exporter):
        """Test CV header with no contact information."""
        cv_data = {}
        story = []

        pdf_exporter._add_cv_header(story, cv_data, "Test User")
        assert len(story) > 0  # Should still add name and spacer

    def test_add_cv_summary_string(self, pdf_exporter):
        """Test CV summary addition as string."""
        cv_data = {"summary": "This is a professional summary."}
        story = []

        pdf_exporter._add_cv_summary(story, cv_data)
        assert len(story) > 0

    def test_add_cv_summary_list(self, pdf_exporter):
        """Test CV summary addition as list."""
        cv_data = {"summary": ["First part of summary.", "Second part of summary."]}
        story = []

        pdf_exporter._add_cv_summary(story, cv_data)
        assert len(story) > 0

    def test_add_cv_summary_empty(self, pdf_exporter):
        """Test CV summary addition when empty."""
        cv_data = {}
        story = []

        pdf_exporter._add_cv_summary(story, cv_data)
        # Should not add anything if no summary
        assert len(story) == 0

    def test_add_cv_experience(self, pdf_exporter, sample_optimized_cv):
        """Test CV experience section addition."""
        story = []
        pdf_exporter._add_cv_experience(story, sample_optimized_cv)

        assert len(story) > 0

    def test_add_cv_skills(self, pdf_exporter, sample_optimized_cv):
        """Test CV skills section addition."""
        story = []
        pdf_exporter._add_cv_skills(story, sample_optimized_cv)

        assert len(story) > 0

    def test_add_cv_skills_separate_technologies(self, pdf_exporter):
        """Test skills section with separate technologies."""
        cv_data = {
            "skills": ["Python", "JavaScript"],
            "technologies": ["AWS", "Docker"]
        }
        story = []

        pdf_exporter._add_cv_skills(story, cv_data)
        assert len(story) > 0

    def test_add_cv_skills_empty(self, pdf_exporter):
        """Test skills section when empty."""
        cv_data = {}
        story = []

        pdf_exporter._add_cv_skills(story, cv_data)
        assert len(story) == 0

    def test_add_cv_education(self, pdf_exporter, sample_optimized_cv):
        """Test CV education section addition."""
        story = []
        pdf_exporter._add_cv_education(story, sample_optimized_cv)

        assert len(story) > 0

    def test_add_cv_education_empty(self, pdf_exporter):
        """Test education section when empty."""
        cv_data = {}
        story = []

        pdf_exporter._add_cv_education(story, cv_data)
        assert len(story) == 0

    def test_add_cover_letter_components(self, pdf_exporter, sample_cover_letter):
        """Test cover letter component addition."""
        story = []

        # Test each component
        pdf_exporter._add_cover_letter_header(story, "John Doe")
        assert len(story) > 0

        pdf_exporter._add_cover_letter_date(story)
        assert len(story) > 1

        pdf_exporter._add_cover_letter_recipient(story, "Test Corp", "Developer")
        assert len(story) > 2

        pdf_exporter._add_cover_letter_body(story, sample_cover_letter)
        assert len(story) > 3

        pdf_exporter._add_cover_letter_footer(story, "John Doe")
        assert len(story) > 4

    def test_cover_letter_paragraph_splitting(self, pdf_exporter):
        """Test cover letter body paragraph splitting."""
        letter_text = "First paragraph content.\n\nSecond paragraph content.\n\nThird paragraph."
        story = []

        pdf_exporter._add_cover_letter_body(story, letter_text)
        # Should add multiple paragraphs with spacers
        assert len(story) > 3

    def test_pdf_export_with_filename(self, pdf_exporter, sample_optimized_cv):
        """Test PDF export with filename parameter."""
        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=sample_optimized_cv,
            user_name="John Doe",
            filename="test_resume.pdf"
        )

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 1000

    def test_global_exporter_instance(self):
        """Test global PDF exporter instance."""
        from app.utils.pdf_export import pdf_exporter

        assert isinstance(pdf_exporter, CVPDFExporter)
        assert pdf_exporter.styles is not None

    def test_export_with_unicode_content(self, pdf_exporter):
        """Test PDF export with Unicode characters."""
        cv_data = {
            "personal_info": {"full_name": "José García"},
            "summary": "Desarrollador con experiência en múltiples tecnologías",
            "skills": ["Python", "JavaScript", "São Paulo"]
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=cv_data,
            user_name="José García"
        )

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 500

    def test_export_large_content(self, pdf_exporter):
        """Test PDF export with large content."""
        large_cv = {
            "summary": "Very long summary " * 50,
            "experience": [
                {
                    "role": f"Position {i}",
                    "company": f"Company {i}",
                    "description": "Long description " * 20
                }
                for i in range(10)
            ],
            "skills": [f"Skill{i}" for i in range(50)]
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=large_cv,
            user_name="Test User"
        )

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 2000  # Should be larger PDF

    def test_export_empty_sections(self, pdf_exporter):
        """Test PDF export with various empty sections."""
        cv_data = {
            "summary": "",
            "experience": [],
            "skills": "",
            "technologies": None,
            "education": []
        }

        pdf_data = pdf_exporter.export_cv_to_pdf(
            optimized_cv=cv_data,
            user_name="Test User"
        )

        assert isinstance(pdf_data, bytes)
        # Should still generate a basic PDF with just the name