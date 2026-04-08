"""
PDF Export Utility — Professional CV and cover letter PDF generation.

Creates formatted PDF documents from optimized CV data and cover letters
using ReportLab for professional presentation.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable

logger = logging.getLogger(__name__)


class PDFExportError(Exception):
    """Custom exception for PDF export errors."""
    pass


class CVPDFExporter:
    """Professional PDF generator for CVs and cover letters.

    Generates clean, ATS-friendly PDF documents with proper formatting,
    typography, and layout for job applications.

    Attributes:
        page_size: PDF page dimensions (default: A4).
        margins: Page margins in inches.
        styles: ReportLab paragraph styles for consistent formatting.
    """

    def __init__(self, page_size=A4):
        """Initialize PDF exporter with formatting configuration."""
        self.page_size = page_size
        self.margins = {
            "left": 0.75 * inch,
            "right": 0.75 * inch,
            "top": 0.75 * inch,
            "bottom": 0.75 * inch,
        }
        self._setup_styles()

    def _setup_styles(self):
        """Configure paragraph and text styles for professional appearance."""
        self.styles = getSampleStyleSheet()

        # Custom styles for CV sections
        self.styles.add(ParagraphStyle(
            name='CVTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6,
            alignment=1,  # Center alignment
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceBefore=12,
            spaceAfter=6,
            borderWidth=0,
            borderColor=colors.HexColor('#bdc3c7'),
            borderPadding=0,
        ))

        self.styles.add(ParagraphStyle(
            name='ContactInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1,  # Center alignment
            spaceAfter=12,
        ))

        self.styles.add(ParagraphStyle(
            name='JobTitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=6,
            spaceAfter=3,
            leftIndent=0,
        ))

        self.styles.add(ParagraphStyle(
            name='CompanyName',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=3,
            leftIndent=0,
        ))

        self.styles.add(ParagraphStyle(
            name='ExperienceDetails',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6,
            leftIndent=20,
            bulletIndent=10,
        ))

        self.styles.add(ParagraphStyle(
            name='Skills',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=3,
        ))

    def export_cv_to_pdf(
        self,
        optimized_cv: Dict[str, Any],
        user_name: str,
        job_title: Optional[str] = None,
        company_name: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> bytes:
        """Generate professional PDF from optimized CV data.

        Args:
            optimized_cv: Structured CV data with optimized content.
            user_name: User's full name for the CV header.
            job_title: Target job title — shown as a subtitle in the header.
            company_name: Target company name — shown in the header subtitle.
            filename: Optional filename (used for metadata only).

        Returns:
            bytes: PDF document as binary data.

        Raises:
            PDFExportError: If PDF generation fails.

        Example:
            >>> exporter = CVPDFExporter()
            >>> pdf_data = exporter.export_cv_to_pdf(
            ...     optimized_cv=optimized_data,
            ...     user_name="John Doe",
            ...     job_title="Senior Python Developer",
            ...     company_name="TechCorp"
            ... )
            >>> with open("resume.pdf", "wb") as f:
            ...     f.write(pdf_data)
        """
        logger.info(f"Generating CV PDF for {user_name}")

        try:
            # Create in-memory buffer for PDF
            buffer = io.BytesIO()

            # Create PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                leftMargin=self.margins["left"],
                rightMargin=self.margins["right"],
                topMargin=self.margins["top"],
                bottomMargin=self.margins["bottom"],
                title=f"Resume - {user_name}",
                author=user_name,
                creator="Auto-Apply CV Optimizer",
            )

            # Build PDF content
            story = []
            self._add_cv_header(story, optimized_cv, user_name)
            self._add_cv_job_target(story, job_title, company_name)
            self._add_cv_summary(story, optimized_cv)
            self._add_cv_experience(story, optimized_cv)
            self._add_cv_skills(story, optimized_cv)
            self._add_cv_education(story, optimized_cv)
            self._add_cv_optimized_keywords(story, optimized_cv)

            # Generate PDF
            doc.build(story)

            # Get PDF binary data
            pdf_data = buffer.getvalue()
            buffer.close()

            logger.info(f"CV PDF generated successfully: {len(pdf_data)} bytes")
            return pdf_data

        except Exception as e:
            logger.error(f"Failed to generate CV PDF: {e}")
            raise PDFExportError(f"PDF generation failed: {e}")

    def export_cover_letter_to_pdf(
        self,
        cover_letter_text: str,
        user_name: str,
        job_title: str,
        company_name: str,
        filename: Optional[str] = None,
    ) -> bytes:
        """Generate professional cover letter PDF.

        Args:
            cover_letter_text: Generated cover letter content.
            user_name: Applicant's full name.
            job_title: Target job position.
            company_name: Target company.
            filename: Optional filename (used for metadata only).

        Returns:
            bytes: PDF document as binary data.

        Raises:
            PDFExportError: If PDF generation fails.
        """
        logger.info(f"Generating cover letter PDF for {job_title} at {company_name}")

        try:
            # Create in-memory buffer for PDF
            buffer = io.BytesIO()

            # Create PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,  # Use letter size for cover letters
                leftMargin=1 * inch,
                rightMargin=1 * inch,
                topMargin=1 * inch,
                bottomMargin=1 * inch,
                title=f"Cover Letter - {user_name}",
                author=user_name,
                creator="Auto-Apply CV Optimizer",
            )

            # Build cover letter content
            story = []
            self._add_cover_letter_header(story, user_name)
            self._add_cover_letter_date(story)
            self._add_cover_letter_recipient(story, company_name, job_title)
            self._add_cover_letter_body(story, cover_letter_text)
            self._add_cover_letter_footer(story, user_name)

            # Generate PDF
            doc.build(story)

            # Get PDF binary data
            pdf_data = buffer.getvalue()
            buffer.close()

            logger.info(f"Cover letter PDF generated successfully: {len(pdf_data)} bytes")
            return pdf_data

        except Exception as e:
            logger.error(f"Failed to generate cover letter PDF: {e}")
            raise PDFExportError(f"Cover letter PDF generation failed: {e}")

    def _add_cv_header(self, story: list, cv_data: Dict[str, Any], user_name: str):
        """Add CV header with name and contact information."""
        # User name as title
        story.append(Paragraph(user_name, self.styles['CVTitle']))

        # Contact information
        personal_info = cv_data.get("personal_info", {})
        contact_parts = []

        if personal_info.get("email"):
            contact_parts.append(personal_info["email"])
        if personal_info.get("phone"):
            contact_parts.append(personal_info["phone"])
        if personal_info.get("location"):
            contact_parts.append(personal_info["location"])
        if personal_info.get("linkedin"):
            contact_parts.append(f"LinkedIn: {personal_info['linkedin']}")

        if contact_parts:
            contact_text = " • ".join(contact_parts)
            story.append(Paragraph(contact_text, self.styles['ContactInfo']))

        story.append(Spacer(1, 0.2 * inch))

    def _add_cv_job_target(
        self,
        story: list,
        job_title: Optional[str],
        company_name: Optional[str],
    ):
        """Add ATS optimization target header (job + company) to CV PDF.

        Shows the recruiter immediately which position this CV was optimized for.
        Only rendered when both job_title and company_name are provided.
        """
        if not job_title or not company_name:
            return

        target_style = ParagraphStyle(
            name='JobTargetHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2980b9'),
            alignment=1,  # Center
            spaceAfter=8,
            fontName='Helvetica-Oblique',
        )
        target_text = f"✦ ATS-Optimized for: {job_title} at {company_name} ✦"
        story.append(Paragraph(target_text, target_style))
        story.append(HRFlowable(
            width="100%", thickness=1.5,
            color=colors.HexColor('#2980b9'), spaceAfter=8,
        ))
        story.append(Spacer(1, 0.05 * inch))

    def _add_cv_optimized_keywords(self, story: list, cv_data: Dict[str, Any]):
        """Add ATS keywords section at the bottom of the CV PDF.

        Lists keywords that were integrated from the job description,
        useful for the candidate to review before submission.
        """
        keywords = cv_data.get("optimized_keywords", [])
        if not keywords:
            return

        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("ATS KEYWORDS INTEGRATED", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
        story.append(Spacer(1, 0.1 * inch))

        kw_text = " • ".join(str(k) for k in keywords)
        kw_style = ParagraphStyle(
            name='KeywordsStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#27ae60'),
            spaceAfter=6,
        )
        story.append(Paragraph(kw_text, kw_style))


    def _add_cv_summary(self, story: list, cv_data: Dict[str, Any]):
        """Add professional summary section."""
        summary = cv_data.get("summary", "")
        if summary:
            story.append(Paragraph("PROFESSIONAL SUMMARY", self.styles['SectionHeader']))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
            story.append(Spacer(1, 0.1 * inch))

            # Handle both string and list formats
            if isinstance(summary, list):
                summary = " ".join(summary)
            elif isinstance(summary, str):
                summary = summary.strip()

            story.append(Paragraph(summary, self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))

    def _add_cv_experience(self, story: list, cv_data: Dict[str, Any]):
        """Add work experience section with formatting."""
        experience = cv_data.get("experience", [])
        if experience:
            story.append(Paragraph("WORK EXPERIENCE", self.styles['SectionHeader']))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
            story.append(Spacer(1, 0.1 * inch))

            for exp in experience:
                if isinstance(exp, dict):
                    # Job title and dates
                    title = exp.get("role", "Position")
                    dates = exp.get("duration", "")
                    if dates:
                        title_line = f"{title} • {dates}"
                    else:
                        title_line = title

                    story.append(Paragraph(title_line, self.styles['JobTitle']))

                    # Company name
                    company = exp.get("company", "")
                    if company:
                        story.append(Paragraph(company, self.styles['CompanyName']))

                    # Job description/responsibilities
                    description = exp.get("description", "")
                    if description:
                        if isinstance(description, list):
                            for item in description:
                                story.append(Paragraph(f"• {item}", self.styles['ExperienceDetails']))
                        else:
                            story.append(Paragraph(description, self.styles['ExperienceDetails']))

                    story.append(Spacer(1, 0.15 * inch))

    def _add_cv_skills(self, story: list, cv_data: Dict[str, Any]):
        """Add skills section with categories."""
        skills = cv_data.get("skills", [])
        technologies = cv_data.get("technologies", [])

        if skills or technologies:
            story.append(Paragraph("SKILLS & TECHNOLOGIES", self.styles['SectionHeader']))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
            story.append(Spacer(1, 0.1 * inch))

            # Combine skills and technologies
            all_skills = []
            if skills:
                all_skills.extend(skills if isinstance(skills, list) else [skills])
            if technologies:
                all_skills.extend(technologies if isinstance(technologies, list) else [technologies])

            if all_skills:
                # Group skills in a readable format
                skills_text = " • ".join(all_skills)
                story.append(Paragraph(skills_text, self.styles['Skills']))
                story.append(Spacer(1, 0.15 * inch))

    def _add_cv_education(self, story: list, cv_data: Dict[str, Any]):
        """Add education section."""
        education = cv_data.get("education", [])
        if education:
            story.append(Paragraph("EDUCATION", self.styles['SectionHeader']))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
            story.append(Spacer(1, 0.1 * inch))

            for edu in education:
                if isinstance(edu, dict):
                    degree = edu.get("degree", "")
                    institution = edu.get("institution", "")
                    year = edu.get("year", "")

                    if degree and institution:
                        edu_line = f"{degree} - {institution}"
                        if year:
                            edu_line += f" ({year})"
                        story.append(Paragraph(edu_line, self.styles['Normal']))

                story.append(Spacer(1, 0.1 * inch))

    def _add_cover_letter_header(self, story: list, user_name: str):
        """Add cover letter header with user name."""
        story.append(Paragraph(user_name, self.styles['CVTitle']))
        story.append(Spacer(1, 0.3 * inch))

    def _add_cover_letter_date(self, story: list):
        """Add current date to cover letter."""
        current_date = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(current_date, self.styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

    def _add_cover_letter_recipient(self, story: list, company_name: str, job_title: str):
        """Add recipient information to cover letter."""
        story.append(Paragraph("Dear Hiring Manager,", self.styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

    def _add_cover_letter_body(self, story: list, cover_letter_text: str):
        """Add cover letter body content, splitting on real newlines."""
        # Split on double newline (real \n\n), also handle single newlines as paragraph breaks
        paragraphs = [
            p.strip()
            for p in cover_letter_text.replace('\r\n', '\n').split('\n\n')
            if p.strip()
        ]

        # Fallback: if no double-newline found, split on single newlines
        if len(paragraphs) == 1:
            paragraphs = [
                p.strip()
                for p in cover_letter_text.replace('\r\n', '\n').split('\n')
                if p.strip()
            ]

        for paragraph in paragraphs:
            story.append(Paragraph(paragraph, self.styles['Normal']))
            story.append(Spacer(1, 0.15 * inch))

    def _add_cover_letter_footer(self, story: list, user_name: str):
        """Add cover letter closing and signature."""
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Sincerely,", self.styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(user_name, self.styles['Normal']))


# Global exporter instance
pdf_exporter = CVPDFExporter()