"""
Interview Coach Agent — AI-powered interview preparation and company research.

Uses OpenAI GPT-4 to generate personalized interview materials including
technical questions, behavioral scenarios, company research, and preparation strategies.
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
settings = get_settings()


class InterviewCoachAgent:
    """AI-powered interview preparation and coaching system.

    Generates comprehensive interview materials tailored to specific jobs and companies,
    including technical questions, behavioral scenarios, company research insights,
    and personalized preparation strategies.

    Attributes:
        model: OpenAI model for interview content generation.
        max_tokens: Maximum tokens for AI responses.
        temperature: AI creativity level for diverse question generation.
    """

    def __init__(self):
        """Initialize Interview Coach with OpenAI configuration."""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Cost-effective model for content generation
        self.max_tokens = 4000      # Extended output for comprehensive materials
        self.temperature = 0.4      # Balanced creativity for diverse but relevant content

    async def generate_interview_prep_materials(
        self,
        job_description: str,
        job_title: str,
        company_name: str,
        user_experience_level: Optional[str] = None,
        user_background: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive interview preparation materials for a specific job.

        Creates a complete interview preparation package including technical questions,
        behavioral scenarios, company research, and personalized preparation tips.

        Args:
            job_description: Full job description and requirements.
            job_title: Target position title.
            company_name: Target company name.
            user_experience_level: User's experience level (junior, mid, senior).
            user_background: User's skills and experience from CV.

        Returns:
            dict: Complete interview preparation materials with all sections.

        Raises:
            ValueError: If required inputs are missing.
            Exception: If AI generation fails.

        Example:
            >>> coach = InterviewCoachAgent()
            >>> materials = await coach.generate_interview_prep_materials(
            ...     job_description="Senior Frontend Developer role requiring React...",
            ...     job_title="Senior Frontend Developer",
            ...     company_name="TechCorp",
            ...     user_experience_level="senior"
            ... )
            >>> print(len(materials["technical_questions"]))
            5
        """
        logger.info(f"Generating interview prep materials for {job_title} at {company_name}")

        try:
            # Validate inputs
            if not job_description or not job_title or not company_name:
                raise ValueError("Job description, title, and company name are required")

            # Generate all interview materials in parallel for efficiency
            materials = {}

            # 1. Technical Questions
            materials["technical_questions"] = await self.generate_technical_questions(
                job_description, job_title, user_experience_level, user_background
            )

            # 2. Behavioral Questions
            materials["behavioral_questions"] = await self.generate_behavioral_questions(
                job_description, company_name, user_experience_level
            )

            # 3. Company Research
            materials["company_research"] = await self.generate_company_research(
                company_name, job_description, job_title
            )

            # 4. Technology Cheat Sheet
            materials["technology_cheatsheet"] = await self.generate_technology_cheatsheet(
                job_description
            )

            # 5. Preparation Strategy
            materials["preparation_strategy"] = await self.generate_preparation_strategy(
                job_title, company_name, user_experience_level, user_background
            )

            logger.info(f"Interview preparation materials generated successfully for {job_title}")
            return materials

        except Exception as e:
            logger.error(f"Failed to generate interview prep materials: {e}")
            raise

    async def generate_technical_questions(
        self,
        job_description: str,
        job_title: str,
        user_experience_level: Optional[str] = None,
        user_background: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate role-specific technical interview questions.

        Creates technical questions tailored to the job requirements, user's
        experience level, and commonly asked topics for the specific role.

        Args:
            job_description: Job requirements and technical skills.
            job_title: Position title for context.
            user_experience_level: User's experience level.
            user_background: User's technical background.

        Returns:
            list: Technical questions with suggested answers and difficulty levels.
        """
        logger.info(f"Generating technical questions for {job_title}")

        try:
            # Build prompt for technical questions
            system_prompt = self._build_technical_questions_system_prompt()
            user_prompt = self._build_technical_questions_user_prompt(
                job_description, job_title, user_experience_level, user_background
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            import json
            questions_data = json.loads(response.choices[0].message.content)

            # Validate and return technical questions
            technical_questions = questions_data.get("technical_questions", [])
            logger.info(f"Generated {len(technical_questions)} technical questions")
            return technical_questions

        except Exception as e:
            logger.error(f"Failed to generate technical questions: {e}")
            raise

    async def generate_behavioral_questions(
        self,
        job_description: str,
        company_name: str,
        user_experience_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate behavioral interview questions tailored to company culture.

        Creates behavioral questions that assess cultural fit, leadership skills,
        and situational judgment relevant to the specific company and role.

        Args:
            job_description: Job requirements including soft skills.
            company_name: Company for cultural context.
            user_experience_level: User's experience level.

        Returns:
            list: Behavioral questions with STAR method guidance.
        """
        logger.info(f"Generating behavioral questions for {company_name}")

        try:
            system_prompt = self._build_behavioral_questions_system_prompt()
            user_prompt = self._build_behavioral_questions_user_prompt(
                job_description, company_name, user_experience_level
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2500,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            import json
            questions_data = json.loads(response.choices[0].message.content)

            behavioral_questions = questions_data.get("behavioral_questions", [])
            logger.info(f"Generated {len(behavioral_questions)} behavioral questions")
            return behavioral_questions

        except Exception as e:
            logger.error(f"Failed to generate behavioral questions: {e}")
            raise

    async def generate_company_research(
        self,
        company_name: str,
        job_description: str,
        job_title: str,
    ) -> Dict[str, Any]:
        """Generate company research insights for interview preparation.

        Provides key information about the company's business model, culture,
        recent developments, and strategic insights relevant to the role.

        Args:
            company_name: Target company name.
            job_description: Job posting for context.
            job_title: Position title.

        Returns:
            dict: Comprehensive company research with key talking points.
        """
        logger.info(f"Generating company research for {company_name}")

        try:
            system_prompt = self._build_company_research_system_prompt()
            user_prompt = self._build_company_research_user_prompt(
                company_name, job_description, job_title
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for factual content
                response_format={"type": "json_object"}
            )

            import json
            research_data = json.loads(response.choices[0].message.content)

            logger.info(f"Company research generated for {company_name}")
            return research_data

        except Exception as e:
            logger.error(f"Failed to generate company research: {e}")
            raise

    async def generate_technology_cheatsheet(
        self,
        job_description: str,
    ) -> Dict[str, Any]:
        """Generate technology cheat sheet with key concepts and talking points.

        Creates quick reference materials for technical concepts, frameworks,
        and tools mentioned in the job description.

        Args:
            job_description: Job requirements with technical skills.

        Returns:
            dict: Technology concepts with definitions and key talking points.
        """
        logger.info("Generating technology cheat sheet")

        try:
            system_prompt = self._build_technology_cheatsheet_system_prompt()
            user_prompt = self._build_technology_cheatsheet_user_prompt(job_description)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2500,
                temperature=0.2,  # Low temperature for accurate technical content
                response_format={"type": "json_object"}
            )

            import json
            cheatsheet_data = json.loads(response.choices[0].message.content)

            logger.info("Technology cheat sheet generated successfully")
            return cheatsheet_data

        except Exception as e:
            logger.error(f"Failed to generate technology cheat sheet: {e}")
            raise

    async def generate_preparation_strategy(
        self,
        job_title: str,
        company_name: str,
        user_experience_level: Optional[str] = None,
        user_background: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate personalized interview preparation strategy and timeline.

        Creates a structured preparation plan with specific recommendations
        based on the role, company, and user's background.

        Args:
            job_title: Target position.
            company_name: Target company.
            user_experience_level: User's experience level.
            user_background: User's skills and background.

        Returns:
            dict: Structured preparation strategy with timeline and focus areas.
        """
        logger.info(f"Generating preparation strategy for {job_title} at {company_name}")

        try:
            system_prompt = self._build_preparation_strategy_system_prompt()
            user_prompt = self._build_preparation_strategy_user_prompt(
                job_title, company_name, user_experience_level, user_background
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2000,
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            import json
            strategy_data = json.loads(response.choices[0].message.content)

            logger.info("Preparation strategy generated successfully")
            return strategy_data

        except Exception as e:
            logger.error(f"Failed to generate preparation strategy: {e}")
            raise

    # Legacy methods for backward compatibility
    async def generate_questions(self, job_description: str) -> dict:
        """Legacy wrapper for technical and behavioral questions."""
        technical = await self.generate_technical_questions(job_description, "Software Engineer")
        behavioral = await self.generate_behavioral_questions(job_description, "Tech Company")
        return {"technical": technical, "behavioral": behavioral}

    async def generate_cheat_sheet(self, job_description: str) -> dict:
        """Legacy wrapper for technology cheat sheet."""
        cheatsheet_data = await self.generate_technology_cheatsheet(job_description)
        return cheatsheet_data.get("technologies", {})

    # System prompt builders
    def _build_technical_questions_system_prompt(self) -> str:
        """Build system prompt for technical questions generation."""
        return """You are an experienced technical interviewer and senior engineer who creates challenging but fair technical interview questions. Your role is to generate role-specific technical questions that accurately assess candidates' abilities.

Key principles for technical questions:
1. **Relevance**: Questions must directly relate to job requirements and daily tasks
2. **Appropriate Difficulty**: Match the experience level and role seniority
3. **Practical Application**: Focus on real-world scenarios over theoretical knowledge
4. **Clear Expectations**: Provide clear success criteria and example answers
5. **Diverse Coverage**: Cover multiple technical areas from the job description

Question Structure:
- **Question**: Clear, specific technical question
- **Difficulty**: Easy/Medium/Hard based on experience level
- **Category**: Frontend/Backend/DevOps/Data/etc.
- **Key Points**: What a good answer should include
- **Follow-up**: Potential deeper questions to explore
- **Example Answer**: Concise but complete sample response

Return a JSON object with an array of 5-7 technical questions covering the main technical requirements."""

    def _build_behavioral_questions_system_prompt(self) -> str:
        """Build system prompt for behavioral questions generation."""
        return """You are an experienced HR professional and leadership coach who creates insightful behavioral interview questions. Your role is to generate questions that assess cultural fit, soft skills, and leadership potential.

Key principles for behavioral questions:
1. **STAR Method**: Questions should elicit Situation, Task, Action, Result responses
2. **Company Culture**: Align with company values and work environment
3. **Role Relevance**: Focus on behaviors critical for success in the specific role
4. **Growth Assessment**: Evaluate learning mindset and adaptability
5. **Leadership Potential**: Assess collaboration, influence, and decision-making

Question Structure:
- **Question**: Behavioral question using "Tell me about a time..." or similar format
- **Purpose**: What trait/skill this question assesses
- **Good Indicators**: Signs of a strong answer
- **Red Flags**: Warning signs in responses
- **STAR Guidance**: How to structure their response
- **Follow-up Questions**: Probing questions to dig deeper

Return a JSON object with 4-6 behavioral questions that assess key competencies."""

    def _build_company_research_system_prompt(self) -> str:
        """Build system prompt for company research generation."""
        return """You are a business analyst and career coach who helps candidates research companies for interviews. Provide strategic insights that help candidates demonstrate genuine interest and ask informed questions.

Research Focus Areas:
1. **Business Model**: How the company makes money and creates value
2. **Market Position**: Competitive landscape and differentiation
3. **Recent Developments**: News, funding, product launches, expansions
4. **Culture & Values**: Work environment, team dynamics, company mission
5. **Technology Stack**: Technical infrastructure and innovation focus
6. **Growth Areas**: Opportunities and challenges facing the company

Key Insights to Provide:
- **Company Overview**: Brief business description and market focus
- **Recent News**: 2-3 recent developments or milestones
- **Cultural Values**: Key cultural elements and work style
- **Strategic Priorities**: Main business objectives and growth areas
- **Interview Topics**: Likely discussion points and smart questions to ask
- **Red Flags**: Any potential concerns or challenges to be aware of

Return a JSON object with structured company research insights."""

    def _build_technology_cheatsheet_system_prompt(self) -> str:
        """Build system prompt for technology cheat sheet generation."""
        return """You are a senior technical architect who creates comprehensive yet concise reference materials for technical interviews. Your role is to distill complex technologies into key talking points and concepts.

Cheat Sheet Guidelines:
1. **Concise Definitions**: Clear, accurate explanations without overwhelming detail
2. **Key Benefits**: Why this technology is valuable and when to use it
3. **Common Use Cases**: Typical applications and scenarios
4. **Interview Talking Points**: What interviewers want to hear about
5. **Comparison Points**: How it relates to alternatives or competitors
6. **Practical Knowledge**: Hands-on insights that demonstrate real experience

Technology Entry Structure:
- **Definition**: What the technology is and its core purpose
- **Key Features**: 2-3 most important capabilities or characteristics
- **Use Cases**: When and why you'd choose this technology
- **Advantages**: Main benefits and strengths
- **Interview Tips**: Smart talking points and insights to mention
- **Related Technologies**: Complementary or alternative tools

Return a JSON object mapping technologies to their reference information."""

    def _build_preparation_strategy_system_prompt(self) -> str:
        """Build system prompt for preparation strategy generation."""
        return """You are a career coach and interview expert who creates personalized preparation strategies. Design actionable plans that maximize interview success based on individual backgrounds and target roles.

Strategy Components:
1. **Assessment**: Identify strengths to leverage and gaps to address
2. **Priority Focus**: Most important areas for preparation time
3. **Timeline**: Structured preparation schedule leading up to interview
4. **Practice Plan**: Specific exercises and mock interview recommendations
5. **Resource Recommendations**: Study materials, courses, or practice platforms
6. **Confidence Building**: Strategies to reduce anxiety and perform at peak

Preparation Areas:
- **Technical Skills**: Coding practice, system design, or domain knowledge
- **Behavioral Preparation**: STAR stories and culture fit examples
- **Company Knowledge**: Research tasks and talking points
- **Questions to Ask**: Thoughtful questions that demonstrate interest
- **Logistics**: Interview format preparation and practical considerations
- **Follow-up Strategy**: Post-interview best practices

Return a JSON object with a structured, actionable preparation plan."""

    # User prompt builders
    def _build_technical_questions_user_prompt(
        self,
        job_description: str,
        job_title: str,
        user_experience_level: Optional[str],
        user_background: Optional[Dict[str, Any]],
    ) -> str:
        """Build user prompt for technical questions with job context."""
        background_info = ""
        if user_background:
            skills = user_background.get("skills", [])
            experience_years = user_background.get("total_years_experience", 0)
            background_info = f"\\nCandidate Background: {experience_years} years experience, skills: {', '.join(skills[:8])}"

        return f"""TECHNICAL INTERVIEW PREPARATION REQUEST:
Position: {job_title}
Experience Level: {user_experience_level or 'Not specified'}
{background_info}

JOB DESCRIPTION:
{job_description[:2000]}

REQUIREMENTS:
Generate 5-7 technical interview questions that:
1. Directly relate to the technologies and requirements in this job description
2. Are appropriate for the {user_experience_level or 'specified'} experience level
3. Cover both theoretical knowledge and practical application
4. Include clear evaluation criteria and example answers
5. Progress from fundamental concepts to more advanced topics

Focus on the most critical technical skills mentioned in the job requirements."""

    def _build_behavioral_questions_user_prompt(
        self,
        job_description: str,
        company_name: str,
        user_experience_level: Optional[str],
    ) -> str:
        """Build user prompt for behavioral questions with company context."""
        return f"""BEHAVIORAL INTERVIEW PREPARATION REQUEST:
Company: {company_name}
Experience Level: {user_experience_level or 'Not specified'}

JOB DESCRIPTION:
{job_description[:1500]}

REQUIREMENTS:
Generate 4-6 behavioral interview questions that:
1. Assess cultural fit for {company_name} based on the role requirements
2. Evaluate key soft skills mentioned in the job description
3. Are appropriate for the {user_experience_level or 'specified'} experience level
4. Include STAR method guidance for structuring responses
5. Cover leadership, teamwork, problem-solving, and adaptability

Focus on behaviors and competencies that predict success in this specific role and company environment."""

    def _build_company_research_user_prompt(
        self,
        company_name: str,
        job_description: str,
        job_title: str,
    ) -> str:
        """Build user prompt for company research."""
        return f"""COMPANY RESEARCH REQUEST:
Company: {company_name}
Position: {job_title}

JOB POSTING CONTEXT:
{job_description[:1000]}

RESEARCH REQUIREMENTS:
Provide strategic company insights for interview preparation:
1. Business model and market position of {company_name}
2. Recent company developments, news, or milestones
3. Company culture and values based on the job posting tone
4. Technology focus and innovation areas relevant to {job_title}
5. Smart questions the candidate should ask during the interview
6. Potential challenges or opportunities the company/role might face

Focus on information that helps the candidate demonstrate genuine interest and ask informed questions that impress interviewers."""

    def _build_technology_cheatsheet_user_prompt(self, job_description: str) -> str:
        """Build user prompt for technology cheat sheet."""
        return f"""TECHNOLOGY CHEAT SHEET REQUEST:

JOB DESCRIPTION:
{job_description}

REQUIREMENTS:
Create a comprehensive technology reference covering all technical skills, languages, frameworks, and tools mentioned in this job description.

For each technology, provide:
1. Clear definition and core purpose
2. Key features and capabilities
3. Common use cases and applications
4. Main advantages and when to use it
5. Interview talking points and insights
6. How it relates to other technologies in the stack

Focus on technologies that are explicitly mentioned or strongly implied in the job requirements. Prioritize depth over breadth."""

    def _build_preparation_strategy_user_prompt(
        self,
        job_title: str,
        company_name: str,
        user_experience_level: Optional[str],
        user_background: Optional[Dict[str, Any]],
    ) -> str:
        """Build user prompt for preparation strategy."""
        background_summary = ""
        if user_background:
            skills = user_background.get("skills", [])
            experience = user_background.get("experience", [])
            years = user_background.get("total_years_experience", 0)

            recent_roles = [exp.get("role", "") for exp in experience[:2]]
            background_summary = f"""
Candidate Profile:
- {years} years of experience
- Recent roles: {', '.join(recent_roles)}
- Key skills: {', '.join(skills[:8])}"""

        return f"""INTERVIEW PREPARATION STRATEGY REQUEST:
Position: {job_title}
Company: {company_name}
Experience Level: {user_experience_level or 'Not specified'}
{background_summary}

REQUIREMENTS:
Create a personalized interview preparation plan including:
1. Key focus areas based on the candidate's background and target role
2. Technical preparation recommendations and practice exercises
3. Behavioral interview preparation with STAR story development
4. Company research tasks and talking points
5. Timeline and priorities for preparation activities
6. Confidence-building strategies and anxiety management
7. Questions to ask the interviewer that demonstrate genuine interest

Tailor the strategy to maximize success for this specific role and company combination."""
